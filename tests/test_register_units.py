"""Firmware-derived unit contracts; all I/O uses simulated register responses."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import Mock

from nlab_modbus.core.register_specs import decode_register_value
from nlab_modbus.devices.psu import PSUDevice
from nlab_modbus.devices.sipm import SiPMDevice
from nlab_modbus.maps.geiger_map import GEIGER_REGISTER_MAP
from nlab_modbus.maps.psu_map import PSU_REGISTER_MAP
from nlab_modbus.maps.sipm_map import SIPM_REGISTER_MAP


def simulated_client(input_words=None, holding_words=None):
    """Return protocol responses without opening a serial or TCP connection."""
    client = Mock()

    def response(words, *, address, count, device_id):
        return Mock(
            registers=[words.get(index, 0) for index in range(address, address + count)],
            isError=Mock(return_value=False),
        )

    client.read_input_registers.side_effect = lambda **kwargs: response(input_words or {}, **kwargs)
    client.read_holding_registers.side_effect = lambda **kwargs: response(
        holding_words or {}, **kwargs
    )
    return client


class RegisterUnitTests(unittest.TestCase):
    def test_existing_maps_match_supplied_firmware_metadata(self):
        # The fixture records the supplied source hash and register versions.
        # It contains metadata, not firmware code, and needs no Downloads file.
        fixture = json.loads(
            (Path(__file__).parent / "fixtures" / "modbus_register_units.json").read_text(
                encoding="utf-8"
            )
        )
        for board, register_map in (
            ("SIPM", SIPM_REGISTER_MAP),
            ("GM", GEIGER_REGISTER_MAP),
            ("HV", PSU_REGISTER_MAP),
        ):
            for name, spec in register_map.items():
                with self.subTest(board=board, register=name):
                    scale, unit = fixture["boards"][board][spec.reg_type.value][str(spec.address)]
                    self.assertEqual(spec.scale, scale)
                    self.assertEqual(spec.unit, unit)

    def test_sipm_setpoint_is_volts_for_decode_and_encode(self):
        device = SiPMDevice(simulated_client(holding_words={3: 4567}), 1)
        self.assertAlmostEqual(device.read("vout_set"), 45.67)
        self.assertEqual(device.read("vout_set", raw=True), 4567)
        self.assertEqual(device.encode(45.67, SIPM_REGISTER_MAP["vout_set"]), [4567])
        for raw, volts in ((1500, 15.0), (7800, 78.0)):
            with self.subTest(raw=raw):
                self.assertEqual(device.decode([raw], SIPM_REGISTER_MAP["vout_set"]), volts)
                self.assertEqual(device.encode(volts, SIPM_REGISTER_MAP["vout_set"]), [raw])

    def test_holding_bulk_reads_preserve_engineering_fractions(self):
        device = SiPMDevice(simulated_client(holding_words={3: 4567, 7: 2025, 9: 12}), 1)
        values = device.get_all_holding_registers()
        self.assertAlmostEqual(values["vout_set"], 45.67)
        self.assertAlmostEqual(values["sipm_comp_tref"], 20.25)
        self.assertAlmostEqual(values["vout_corr"], 0.12)
        raw = device.get_all_holding_registers(raw=True)
        self.assertEqual(raw["vout_set"], 4567)
        self.assertEqual(raw["sipm_comp_tref"], 2025)
        self.assertEqual(raw["vout_corr"], 12)
        self.assertTrue(all(isinstance(value, int) for value in raw.values()))

    def test_pmt_temperature_scales_once_in_single_and_block_reads(self):
        for word, expected in ((2500, 25.0), (0xFF06, -2.5), (0, 0.0)):
            with self.subTest(word=word):
                device = PSUDevice(simulated_client(input_words={15: word}), 1)
                self.assertEqual(device.read("pmt_temp"), expected)
                self.assertEqual(device.read_snapshot()["pmt_temp"], expected)
                raw = word if word < 0x8000 else word - 0x10000
                self.assertEqual(device.read("pmt_temp", raw=True), raw)
                self.assertEqual(device.read_snapshot(raw=True)["pmt_temp"], raw)

    def test_sipm_current_is_microamps_for_single_and_block_reads(self):
        for word, expected in ((120, 120), (0xFF9C, -100), (0, 0)):
            with self.subTest(word=word):
                device = SiPMDevice(simulated_client(input_words={4: word}), 1)
                self.assertEqual(device.get_sipm_current_ua(), expected)
                self.assertEqual(device.read_snapshot()["sipm_current_ua"], expected)
                self.assertEqual(device.read_snapshot(raw=True)["sipm_current_ua"], expected)

    def test_other_documented_physical_units_keep_their_scaling(self):
        cases = (
            (SIPM_REGISTER_MAP, "led_drv_duration_ns", 2, 20),
            (SIPM_REGISTER_MAP, "sipm_comp_tref", 0xFF06, -2.5),
            (GEIGER_REGISTER_MAP, "pwm_duty", 505, 50.5),
            (GEIGER_REGISTER_MAP, "dose_level_msvh", 17, 17),
            (GEIGER_REGISTER_MAP, "dose_msv", 32, 32),
            (PSU_REGISTER_MAP, "hv_current", 120, 120),
        )
        for register_map, name, word, expected in cases:
            with self.subTest(register=name):
                self.assertEqual(decode_register_value(word, register_map[name]), expected)


if __name__ == "__main__":
    unittest.main()

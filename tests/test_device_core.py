from __future__ import annotations

import math
import unittest

from fake_firmware import PASSWORD, FakeFirmwareClient

from nlab_modbus.core.base_modbus_device import BaseModbusDevice
from nlab_modbus.core.enums import DeviceType
from nlab_modbus.core.errors import DeviceUnavailable, PasswordRequired
from nlab_modbus.core.register_specs import RegisterType, temperature_register
from nlab_modbus.devices.psu import PSUDevice
from nlab_modbus.devices.sipm import SiPMDevice


def psu_client(inputs=16, holdings=12):
    """PSU tables as on deployed fw 0.3 (16 input / 12 holding registers)."""
    input_words = [0x0301, 0x0003] + [0] * (inputs - 2)
    holding_words = [1, 96, 0, 800] + [0] * (holdings - 4)
    if holdings > 11:
        holding_words[11] = PASSWORD & 0xFFFF
    password_address = 11 if holdings > 11 else None
    return FakeFirmwareClient(input_words, holding_words, protected={4, 5, 6, 7, 8, 9, 10}, password_address=password_address)


class TableLayoutTests(unittest.TestCase):
    def test_full_tables_are_read_in_one_transaction_each(self):
        client = psu_client()
        device = PSUDevice(client, 1)
        device.table_size(RegisterType.INPUT)
        device.table_size(RegisterType.HOLDING)
        client.requests.clear()

        inputs = device.read_snapshot(raw=True)
        holdings = device.get_all_holding_registers(raw=True)

        self.assertEqual(client.requests, [(0x04, 0, 16), (0x03, 0, 12)])
        self.assertEqual(inputs["hardware_version"], 0x0301)
        self.assertEqual(holdings["pwm_set_voltage"], 800)

    def test_shorter_firmware_tables_are_detected(self):
        client = psu_client(inputs=10, holdings=5)
        device = PSUDevice(client, 1)

        self.assertEqual(device.table_size(RegisterType.INPUT), 10)
        self.assertEqual(device.table_size(RegisterType.HOLDING), 5)
        self.assertEqual(len(device.read_snapshot()), 10)
        self.assertNotIn("pmt_temp", device.available_registers(RegisterType.INPUT))

    def test_identify_decodes_type_revision_and_firmware(self):
        identity = PSUDevice(psu_client(), 1).identify()

        self.assertEqual(identity.device_type, DeviceType.PSU)
        self.assertEqual(identity.hardware_revision, 1)
        self.assertEqual(identity.firmware, (0, 3))
        self.assertIsNone(identity.register_version)

    def test_identify_reads_register_version_and_serial_on_new_firmware(self):
        client = psu_client(inputs=20, holdings=14)
        client.inputs[16:19] = [0x0101, 0x1234, 0xABCD]

        identity = PSUDevice(client, 1).identify()

        self.assertEqual(identity.register_version, (1, 1))
        self.assertEqual(identity.serial_number, 0x1234ABCD)


class AccessorTests(unittest.TestCase):
    def test_accessors_are_generated_from_the_register_map(self):
        client = FakeFirmwareClient([0x0101, 2, 0, 4567], [1, 96, 0, 4000])
        device = SiPMDevice(client, 1)

        self.assertAlmostEqual(device.get_sipm_voltage_10mv(), 45.67)
        self.assertEqual(device.get_vout_set(raw=True), 4000)
        device.set_vout_set(45.5)
        self.assertEqual(client.holdings[3], 4550)
        self.assertFalse(hasattr(device, "set_hardware_version"))
        self.assertIn("SiPM output voltage setpoint", SiPMDevice.get_vout_set.__doc__)

    def test_explicit_methods_are_not_replaced(self):
        class Custom(BaseModbusDevice):
            REGISTER_MAP = SiPMDevice.REGISTER_MAP

            def get_vout_set(self):
                return "custom"

        self.assertEqual(Custom(FakeFirmwareClient([], []), 1).get_vout_set(), "custom")


class ErrorTests(unittest.TestCase):
    def test_locked_write_raises_password_required(self):
        client = psu_client()
        client.holdings[11] = 0  # wrong password locks the device
        device = PSUDevice(client, 1)

        with self.assertRaises(PasswordRequired) as raised:
            device.write("pid_p_vout", 20)
        self.assertEqual(raised.exception.code, 4)

    def test_missing_response_raises_device_unavailable(self):
        client = psu_client()
        client.offline = True

        with self.assertRaises(DeviceUnavailable):
            PSUDevice(client, 1).read("hv_voltage")

    def test_out_of_range_write_is_rejected_before_the_wire(self):
        client = psu_client()
        with self.assertRaisesRegex(ValueError, "register limits 50..1500"):
            PSUDevice(client, 1).write("pwm_set_voltage", 2000)
        self.assertEqual(client.requests, [])

    def test_missing_temperature_sensor_decodes_as_nan(self):
        spec = temperature_register(0)
        device = BaseModbusDevice(FakeFirmwareClient([], []), 1)

        self.assertTrue(math.isnan(device.decode([(-30000) & 0xFFFF], spec)))
        self.assertEqual(device.decode([(-30000) & 0xFFFF], spec, raw_mode=True), -30000)


if __name__ == "__main__":
    unittest.main()

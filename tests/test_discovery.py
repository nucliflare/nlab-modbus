from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from nlab_modbus.core.enums import DeviceType
from nlab_modbus.discovery.scan import (
    _usable_discovery_address,
    scan_local_modbus_devices,
    scan_remote_modbus_devices,
)


class _Response:
    def __init__(self, registers=None, error: bool = False):
        self.registers = registers or []
        self._error = error

    def isError(self) -> bool:
        return self._error


class _FakeClient:
    def __init__(self, responses: dict[int, object], connect: bool = True):
        self.responses = responses
        self.connect_result = connect
        self.transaction = SimpleNamespace()
        self.read_ids: list[int] = []
        self.closed = False

    def connect(self) -> bool:
        return self.connect_result

    def read_input_registers(self, *, address, count, device_id):
        self.read_ids.append(device_id)
        response = self.responses[device_id]
        if isinstance(response, Exception):
            raise response
        return response

    def close(self) -> None:
        self.closed = True


class DiscoveryTests(unittest.TestCase):
    @patch("nlab_modbus.discovery.scan.time.sleep")
    @patch("nlab_modbus.discovery.scan.list_ports.comports")
    @patch("nlab_modbus.discovery.scan.ModbusSerialClient")
    def test_local_scan_skips_in_use_port_and_closes_client(
        self,
        client_factory,
        comports,
        _sleep,
    ) -> None:
        client = _FakeClient(
            {
                1: _Response([0x0101]),
                2: OSError("device disappeared"),
                3: _Response(error=True),
            }
        )
        client_factory.return_value = client
        comports.return_value = [
            SimpleNamespace(device="COM1", description="test port"),
            SimpleNamespace(device="COM2", description="in use"),
        ]

        found = scan_local_modbus_devices(
            device_ids=[1, 1, 2, 3],
            exclude_ports={"COM2"},
        )

        self.assertEqual(client_factory.call_count, 1)
        self.assertEqual(client.read_ids, [1, 2, 3])
        self.assertTrue(client.closed)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["type"], DeviceType.SIPM)
        self.assertEqual(found[0]["hardware_id"], 0x0101)

    @patch("nlab_modbus.discovery.scan.ModbusTcpClient")
    def test_remote_scan_uses_requested_ids_and_returns_hardware_id(self, client_factory) -> None:
        client = _FakeClient(
            {
                4: _Response([0x0207]),
                7: _Response([0x9901]),
            }
        )
        client_factory.return_value = client

        found = scan_remote_modbus_devices("192.0.2.10", 5001, candidate_ids=[4, 7])

        self.assertEqual(client.read_ids, [4, 7])
        self.assertTrue(client.closed)
        self.assertEqual(
            found,
            [
                {
                    "type": DeviceType.GEIGER,
                    "device_id": 4,
                    "host": "192.0.2.10",
                    "port": 5001,
                    "hardware_id": 0x0207,
                }
            ],
        )

    def test_scan_rejects_out_of_range_device_ids(self) -> None:
        with self.assertRaisesRegex(ValueError, "1..254"):
            scan_local_modbus_devices(device_ids=[0])
        with self.assertRaisesRegex(ValueError, "1..254"):
            scan_remote_modbus_devices("192.0.2.10", 5001, candidate_ids=[255])

    @patch("nlab_modbus.discovery.scan.ModbusTcpClient")
    def test_cancelled_remote_scan_does_not_connect(self, client_factory) -> None:
        found = scan_remote_modbus_devices(
            "192.0.2.10",
            5001,
            candidate_ids=[1],
            should_stop=lambda: True,
        )

        self.assertEqual(found, [])
        client_factory.return_value.connect.assert_not_called()
        client_factory.return_value.close.assert_called_once()

    @patch("nlab_modbus.discovery.scan.ModbusTcpClient")
    def test_expected_probe_timeout_is_logged_without_traceback(self, client_factory) -> None:
        client_factory.return_value = _FakeClient({1: OSError("no response")})

        with self.assertLogs("nlab_modbus.discovery.scan", level="DEBUG") as captured:
            found = scan_remote_modbus_devices(
                "192.0.2.10",
                5001,
                candidate_ids=[1],
            )

        self.assertEqual(found, [])
        output = "\n".join(captured.output)
        self.assertIn("No response from 192.0.2.10:5001 id=1: no response", output)
        self.assertNotIn("Traceback", output)

    def test_unscoped_link_local_ipv6_is_not_a_remote_scan_target(self) -> None:
        self.assertTrue(_usable_discovery_address("192.168.10.128"))
        self.assertTrue(_usable_discovery_address("2001:db8::10"))
        self.assertFalse(_usable_discovery_address("fe80::21e:c0ff:fead:e4c7"))


if __name__ == "__main__":
    unittest.main()

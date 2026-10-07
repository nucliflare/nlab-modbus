from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from nlab_modbus.core.enums import DeviceType
from nlab_modbus.services.manager import DeviceManager


class _SerialClient:
    def __init__(self, **kwargs):
        self.comm_params = SimpleNamespace(host=kwargs["port"])
        self.closed = False

    def connect(self) -> bool:
        return True

    def close(self) -> None:
        self.closed = True


class ManagerConfigurationTests(unittest.TestCase):
    @patch("nlab_modbus.services.manager.time.sleep")
    @patch("nlab_modbus.services.manager.ModbusSerialClient", side_effect=_SerialClient)
    def test_open_port_rejects_incompatible_serial_configuration(
        self,
        _client_factory,
        _sleep,
    ) -> None:
        manager = DeviceManager()
        manager.connect_local("COM9", 1, DeviceType.SIPM, baudrate=115200)

        with self.assertRaisesRegex(ValueError, "already open"):
            manager.connect_local("COM9", 2, DeviceType.GEIGER, baudrate=9600)

        manager.close_all()

    @patch("nlab_modbus.services.manager.time.sleep")
    @patch("nlab_modbus.services.manager.ModbusSerialClient", side_effect=_SerialClient)
    def test_registered_address_rejects_a_different_device_type(
        self,
        _client_factory,
        _sleep,
    ) -> None:
        manager = DeviceManager()
        manager.connect_local("COM9", 1, DeviceType.SIPM)

        with self.assertRaisesRegex(ValueError, "already registered as SIPM"):
            manager.connect_local("COM9", 1, DeviceType.PSU)

        manager.close_all()


if __name__ == "__main__":
    unittest.main()

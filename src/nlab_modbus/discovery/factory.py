from pymodbus.client import ModbusSerialClient, ModbusTcpClient

from nlab_modbus.core.base_modbus_device import BaseModbusDevice
from nlab_modbus.core.enums import DeviceType
from nlab_modbus.devices.geiger import GeigerDevice
from nlab_modbus.devices.psu import PSUDevice
from nlab_modbus.devices.sipm import SiPMDevice

DEVICE_CLASS_BY_TYPE = {
    DeviceType.PSU: PSUDevice,
    DeviceType.SIPM: SiPMDevice,
    DeviceType.GEIGER: GeigerDevice,
}


def create_device(
    client: ModbusSerialClient | ModbusTcpClient,
    device_id: int,
    device_type: DeviceType,
) -> BaseModbusDevice:
    cls = DEVICE_CLASS_BY_TYPE[device_type]
    return cls(client, device_id)

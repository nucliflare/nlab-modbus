from nlab_modbus.core.base_modbus_device import BaseModbusDevice
from nlab_modbus.core.enums import DeviceType
from nlab_modbus.maps.psu_map import PSU_REGISTER_MAP


class PSUDevice(BaseModbusDevice):
    """PMT high-voltage supply: 50–1500 V PWM boost converter with PID control and
    current monitoring. ``get_<register>()``/``set_<register>()`` accessors are
    generated from PSU_REGISTER_MAP."""

    REGISTER_MAP = PSU_REGISTER_MAP
    DEVICE_TYPE = DeviceType.PSU

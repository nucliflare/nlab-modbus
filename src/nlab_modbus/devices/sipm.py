from nlab_modbus.core.base_modbus_device import BaseModbusDevice
from nlab_modbus.core.enums import DeviceType
from nlab_modbus.maps.sipm_map import SIPM_REGISTER_MAP


class SiPMDevice(BaseModbusDevice):
    """SiPM bias board: 15–78 V output in 10 mV steps, temperature compensation,
    calibration LED driver. ``get_<register>()``/``set_<register>()`` accessors
    are generated from SIPM_REGISTER_MAP."""

    REGISTER_MAP = SIPM_REGISTER_MAP
    DEVICE_TYPE = DeviceType.SIPM

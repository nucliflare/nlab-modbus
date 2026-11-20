from nlab_modbus.core.base_modbus_device import BaseModbusDevice
from nlab_modbus.core.enums import DeviceType
from nlab_modbus.maps import geiger_map


class GeigerDevice(BaseModbusDevice):
    """Geiger-Mueller probe: 50–650 V tube supply, pulse counting and dose rate
    from a two-segment calibration polynomial (see nlab_modbus.calibration).
    ``get_<register>()``/``set_<register>()`` accessors are generated from
    GEIGER_REGISTER_MAP."""

    REGISTER_MAP = geiger_map.GEIGER_REGISTER_MAP
    DEVICE_TYPE = DeviceType.GEIGER
    REGISTER_VERSION = geiger_map.REGISTER_VERSION

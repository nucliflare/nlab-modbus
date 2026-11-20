from nlab_modbus.core.base_modbus_device import BaseModbusDevice
from nlab_modbus.core.enums import DeviceType
from nlab_modbus.maps.geiger_map import GEIGER_REGISTER_MAP


class GeigerDevice(BaseModbusDevice):
    """Geiger-Mueller probe: 50–650 V tube supply, pulse counting and dose rate
    from a two-segment calibration polynomial (see nlab_modbus.calibration).
    ``get_<register>()``/``set_<register>()`` accessors are generated from
    GEIGER_REGISTER_MAP."""

    REGISTER_MAP = GEIGER_REGISTER_MAP
    DEVICE_TYPE = DeviceType.GEIGER

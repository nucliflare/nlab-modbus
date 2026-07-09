from enum import IntEnum


class DeviceType(IntEnum):
    """Device type identifier from the high byte of the hardware_version register.

    hardware_version register layout (uint16):
        high byte = device type  (this enum)
        low byte  = board revision

    firmware_version register layout (uint16):
        high byte = firmware major
        low byte  = firmware minor
    """

    SIPM   = 1   # 0x01xx
    GEIGER = 2   # 0x02xx
    PSU    = 3   # 0x03xx

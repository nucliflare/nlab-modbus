from enum import IntEnum


class DeviceType(IntEnum):
    """Modbus device type identifiers based on hardware_version register values."""

    SIPM = 257
    GEIGER = 513
    PSU = 769

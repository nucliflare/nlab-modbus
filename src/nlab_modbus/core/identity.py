"""Decoded identity of a connected board."""

from __future__ import annotations

from dataclasses import dataclass

from nlab_modbus.core.enums import DeviceType


@dataclass(frozen=True)
class DeviceIdentity:
    """Identity words read from the input registers.

    ``hardware_version`` = TYPE (high byte) | board revision (low byte),
    ``firmware_version`` = MAJOR | MINOR. Boards with pre-July 2026 firmware
    have no register-version or serial-number words; those fields are None.
    """

    type_code: int
    hardware_revision: int
    firmware: tuple[int, int]
    register_version: tuple[int, int] | None = None
    serial_number: int | None = None

    @classmethod
    def from_words(
        cls,
        hardware_version: int,
        firmware_version: int,
        register_version: int | None = None,
        serial_hi: int | None = None,
        serial_lo: int | None = None,
    ) -> DeviceIdentity:
        serial = None if serial_hi is None or serial_lo is None else (serial_hi << 16) | serial_lo
        return cls(
            type_code=(hardware_version >> 8) & 0xFF,
            hardware_revision=hardware_version & 0xFF,
            firmware=((firmware_version >> 8) & 0xFF, firmware_version & 0xFF),
            register_version=None if register_version is None else ((register_version >> 8) & 0xFF, register_version & 0xFF),
            serial_number=serial,
        )

    @property
    def device_type(self) -> DeviceType | None:
        try:
            return DeviceType(self.type_code)
        except ValueError:
            return None

    @property
    def type_name(self) -> str:
        device_type = self.device_type
        return device_type.name if device_type else f"unknown (type 0x{self.type_code:02X})"

    def __str__(self) -> str:
        parts = [f"{self.type_name} rev {self.hardware_revision}", f"fw {self.firmware[0]}.{self.firmware[1]}"]
        if self.register_version is not None:
            parts.append(f"registers v{self.register_version[0]}.{self.register_version[1]}")
        if self.serial_number is not None:
            parts.append(f"S/N {self.serial_number:08X}")
        return ", ".join(parts)

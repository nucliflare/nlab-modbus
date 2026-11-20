from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class RegisterType(Enum):
    """Modbus register class: HOLDING (read/write, FC03/06/16) or INPUT (read-only, FC04)."""

    HOLDING = "holding"
    INPUT = "input"


# Raw value the firmware reports when an I2C temperature sensor is missing (-300 degC).
SENSOR_UNAVAILABLE = -30000

_DTYPE_LIMITS = {"int16": (-0x8000, 0x7FFF), "uint16": (0, 0xFFFF), "bool": (0, 1)}


@dataclass(frozen=True)
class RegisterSpec:
    """One firmware register: location, wire type, limits and engineering scaling.

    The firmware always exchanges raw 16-bit counts. ``scale`` and ``unit``
    convert them to physical values: ``value = raw * scale``.

    Attributes:
        reg_type:    HOLDING or INPUT.
        address:     Zero-based register address.
        dtype:       Wire interpretation: "int16", "uint16" or "bool".
        min, max:    Raw limits. For holding registers these are the firmware's
                     write limits; writes outside them are rejected locally.
        scale, unit: Engineering conversion and display unit.
        persistent:  Saved to EEPROM by the firmware on every write (slower).
        password_protected: Requires the service password (firmware PASS flag).
        default:     Firmware default (holding registers only).
        unavailable: Raw value meaning "no reading" (decoded as NaN).
    """

    reg_type: RegisterType
    address: int
    dtype: str
    min: int
    max: int
    count: int = 1
    scale: float = 1.0
    unit: str | None = None
    password_protected: bool = False
    description: str = ""
    persistent: bool = False
    default: int | None = None
    unavailable: int | None = None

    @property
    def writable(self) -> bool:
        return self.reg_type is RegisterType.HOLDING


def holding_register(
    address: int,
    *,
    min: int,
    max: int,
    default: int,
    scale: float = 1.0,
    unit: str | None = None,
    eeprom: bool = False,
    password: bool = False,
    description: str = "",
) -> RegisterSpec:
    """Holding register as declared in the firmware ``modbus_hold_reg`` table."""
    return RegisterSpec(
        RegisterType.HOLDING, address, "int16", min, max,
        scale=scale, unit=unit, persistent=eeprom, password_protected=password,
        default=default, description=description,
    )


def input_register(
    address: int,
    *,
    dtype: str = "int16",
    scale: float = 1.0,
    unit: str | None = None,
    unavailable: int | None = None,
    description: str = "",
) -> RegisterSpec:
    """Read-only input register; limits follow the wire type."""
    low, high = _DTYPE_LIMITS[dtype]
    return RegisterSpec(
        RegisterType.INPUT, address, dtype, low, high,
        scale=scale, unit=unit, unavailable=unavailable, description=description,
    )


def temperature_register(address: int, *, scale: float = 0.01, description: str = "") -> RegisterSpec:
    """I2C temperature input that reports SENSOR_UNAVAILABLE when the sensor is absent."""
    return input_register(address, scale=scale, unit="degC", unavailable=SENSOR_UNAVAILABLE, description=description)


RegisterKey = tuple[RegisterType, int]


def build_register_index(register_map: dict[str, RegisterSpec]) -> dict[RegisterKey, tuple[str, RegisterSpec]]:
    """Return a (type, address) → (name, spec) lookup; reject duplicate addresses."""
    index: dict[RegisterKey, tuple[str, RegisterSpec]] = {}
    for name, spec in register_map.items():
        key = (spec.reg_type, spec.address)
        if key in index:
            raise ValueError(f"Duplicate register {key}: {index[key][0]!r} and {name!r}")
        index[key] = name, spec
    return index


def decode_register_value(raw_value: int, spec: RegisterSpec, *, raw: bool = False) -> int | float | bool:
    """Convert one raw 16-bit word to a value.

    int16 words are sign-extended. With ``raw=True`` the (sign-extended) count
    is returned unscaled; otherwise the scale is applied and the register's
    ``unavailable`` code decodes to NaN.
    """
    value = int(raw_value) & 0xFFFF
    if spec.dtype == "bool":
        return value if raw else bool(value)
    if spec.dtype == "int16" and value >= 0x8000:
        value -= 0x10000
    elif spec.dtype not in ("int16", "uint16"):
        raise NotImplementedError(f"Unsupported dtype: {spec.dtype}")
    if raw:
        return value
    if spec.unavailable is not None and value == spec.unavailable:
        return math.nan
    return value if spec.scale == 1.0 else value * spec.scale


def to_raw(value: float | int | bool, spec: RegisterSpec, *, raw: bool = False) -> int:
    """Convert a value (engineering, or raw counts if ``raw``) to a validated raw count."""
    if spec.dtype == "bool":
        count = 1 if value else 0
    elif raw:
        count = int(value)
    else:
        count = int(round(float(value) / spec.scale))
    if not spec.min <= count <= spec.max:
        raise ValueError(f"Raw value {count} is outside the register limits {spec.min}..{spec.max}")
    return count


def encode_register_value(value: float | int | bool, spec: RegisterSpec, *, raw: bool = False) -> int:
    """Convert a value to the unsigned 16-bit word sent on the wire."""
    return to_raw(value, spec, raw=raw) & 0xFFFF


def decode_register_block(
    registers: list[int],
    *,
    start_address: int,
    register_type: RegisterType,
    register_index: dict[RegisterKey, tuple[str, RegisterSpec]],
    raw: bool = False,
) -> dict[str, int | float | bool]:
    """Decode a contiguous block of raw words into ``{name: value}``; unknown addresses are skipped."""
    decoded: dict[str, int | float | bool] = {}
    for offset, word in enumerate(registers):
        match = register_index.get((register_type, start_address + offset))
        if match is not None:
            name, spec = match
            decoded[name] = decode_register_value(word, spec, raw=raw)
    return decoded

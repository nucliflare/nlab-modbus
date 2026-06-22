from dataclasses import dataclass
from enum import Enum


class RegisterType(Enum):
    """Modbus register class as defined by the Modbus spec.

    HOLDING registers are read/write; INPUT registers are read-only.
    The distinction determines which Modbus function code is used on the wire
    (FC03 for holding, FC04 for input).
    """

    HOLDING = "holding"
    INPUT = "input"


@dataclass(frozen=True)
class RegisterSpec:
    """Describes one Modbus register: its location, type, and scaling.

    Frozen so a register map can be a plain module-level dict without risk of
    accidental mutation at runtime. The scale and unit fields are purely for the
    application layer — the firmware always exchanges raw integer counts.

    Attributes:
        reg_type:  Whether this is a holding (R/W) or input (R-only) register.
        address:   Zero-based Modbus register address within the device.
        dtype:     Wire representation: "uint16", "int16", or "bool".
        min:       Minimum raw register value (used for encode-time validation).
        max:       Maximum raw register value (used for encode-time validation).
        count:     Number of consecutive registers this field occupies (almost
                   always 1 for these devices).
        scale:     Multiply raw counts by this to get engineering units.
                   Example: scale=0.01 means a raw value of 7500 → 75.00 V.
        unit:      Display unit string (e.g. "mV", "*C"). Informational only.
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


RegisterKey = tuple[RegisterType, int]


def build_register_index(register_map: dict[str, RegisterSpec]) -> dict[RegisterKey, tuple[str, RegisterSpec]]:
    """Build a (register_type, address) → (name, spec) lookup dict.

    Used by devices to decode a contiguous register block without iterating the
    full map. Raises ValueError if two specs share the same address within the
    same register type, which always indicates a map definition error.
    """
    index: dict[RegisterKey, tuple[str, RegisterSpec]] = {}

    for name, spec in register_map.items():
        key = (spec.reg_type, spec.address)

        if key in index:
            previous_name, previous_spec = index[key]
            raise ValueError(f"Duplicate register {key}: {previous_name!r} {previous_spec} and {name!r} {spec}")

        index[key] = name, spec

    return index


def decode_register_value(raw_value: int, spec: RegisterSpec) -> int | float:
    """Convert one raw Modbus register word to an engineering value.

    int16 registers are transmitted as unsigned 16-bit words by Modbus; values
    ≥ 0x8000 are re-interpreted as negative using two's complement before the
    scale factor is applied.
    """
    value = raw_value

    if spec.dtype == "int16" and value >= 0x8000:
        value -= 0x10000

    return value if spec.scale == 1.0 else value * spec.scale


def decode_register_block(
    registers: list[int],
    *,
    start_address: int,
    register_type: RegisterType,
    register_index: dict[RegisterKey, tuple[str, RegisterSpec]],
) -> dict[str, int | float]:
    """Decode a contiguous list of raw register words into named engineering values.

    Addresses not present in register_index are silently skipped so a single
    block read can span gaps in the register map without errors.

    Args:
        registers:       Raw 16-bit words as returned by pymodbus, in address order.
        start_address:   Modbus address of registers[0].
        register_type:   Whether these came from holding or input registers.
        register_index:  Pre-built lookup from build_register_index().

    Returns:
        Mapping of register name → scaled engineering value.
    """
    decoded: dict[str, int | float] = {}

    for offset, raw_value in enumerate(registers):
        address = start_address + offset
        key = (register_type, address)

        match = register_index.get(key)
        if match is None:
            continue

        name, spec = match
        decoded[name] = decode_register_value(raw_value, spec)

    return decoded

from dataclasses import dataclass
from enum import Enum


class RegisterType(Enum):
    HOLDING = "holding"
    INPUT = "input"


@dataclass(frozen=True)
class RegisterSpec:
    reg_type: RegisterType
    address: int
    dtype: str
    min: int
    max: int
    count: int = 1
    scale: float = 1.0
    unit: str | None = None


RegisterKey = tuple[RegisterType, int]


def build_register_index(register_map: dict[str, RegisterSpec]) -> dict[RegisterKey, tuple[str, RegisterSpec]]:
    index: dict[RegisterKey, tuple[str, RegisterSpec]] = {}

    for name, spec in register_map.items():
        key = (spec.reg_type, spec.address)

        if key in index:
            previous_name, previous_spec = index[key]
            raise ValueError(f"Duplicate register {key}: {previous_name!r} {previous_spec} and {name!r} {spec}")

        index[key] = name, spec

    return index


def decode_register_value(raw_value: int, spec: RegisterSpec) -> int | float:
    value = raw_value

    if spec.dtype == "int16" and value >= 0x8000:
        value -= 0x10000

    return value * spec.scale


def decode_register_block(
    registers: list[int],
    *,
    start_address: int,
    register_type: RegisterType,
    register_index: dict[RegisterKey, tuple[str, RegisterSpec]],
) -> dict[str, int | float]:
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

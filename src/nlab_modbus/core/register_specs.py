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

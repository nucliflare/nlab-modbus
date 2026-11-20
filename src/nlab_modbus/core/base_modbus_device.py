from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from pymodbus.exceptions import ModbusException

from nlab_modbus.core.enums import DeviceType
from nlab_modbus.core.errors import DeviceUnavailable, IllegalDataAddress, exception_response
from nlab_modbus.core.identity import DeviceIdentity
from nlab_modbus.core.register_specs import (
    RegisterSpec,
    RegisterType,
    build_register_index,
    decode_register_block,
    decode_register_value,
    encode_register_value,
)
from nlab_modbus.core.transport import Link

logger = logging.getLogger(__name__)


def _make_getter(name: str, spec: RegisterSpec) -> Callable:
    def getter(self, *, raw: bool = False):
        return self.read(name, raw=raw)

    getter.__name__ = f"get_{name}"
    getter.__doc__ = f"Read {name}: {spec.description}" + (f" [{spec.unit}]" if spec.unit else "")
    return getter


def _make_setter(name: str, spec: RegisterSpec) -> Callable:
    def setter(self, value, *, raw: bool = False) -> None:
        self.write(name, value, raw=raw)

    setter.__name__ = f"set_{name}"
    setter.__doc__ = f"Write {name}: {spec.description}" + (f" [{spec.unit}]" if spec.unit else "")
    return setter


class BaseModbusDevice:
    """Register-map driven access to one board on a Modbus RTU transport.

    Subclasses only declare ``REGISTER_MAP`` and ``DEVICE_TYPE``. For every
    register a ``get_<name>()`` method (and ``set_<name>()`` for holding
    registers) is generated from the map, so the accessors always match it.

    Reads of whole tables use one FC04/FC03 transaction. Older firmware has
    shorter tables than the map; the implemented length is detected on first
    use and only those registers are read.

    ``bus_lock`` serialises transactions; DeviceManager replaces it with the
    lock shared by every device on the same serial port or TCP endpoint.
    """

    REGISTER_MAP: dict[str, RegisterSpec] = {}
    DEVICE_TYPE: DeviceType | None = None
    REGISTER_VERSION: tuple[int, int] | None = None

    _register_index: dict = {}
    _map_sizes: dict[RegisterType, int] = {}

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        cls._register_index = build_register_index(cls.REGISTER_MAP)
        cls._map_sizes = {
            reg_type: 1 + max((s.address + s.count - 1 for s in cls.REGISTER_MAP.values() if s.reg_type is reg_type), default=-1)
            for reg_type in RegisterType
        }
        for name, spec in cls.REGISTER_MAP.items():
            if f"get_{name}" not in cls.__dict__:
                setattr(cls, f"get_{name}", _make_getter(name, spec))
            if spec.writable and f"set_{name}" not in cls.__dict__:
                setattr(cls, f"set_{name}", _make_setter(name, spec))

    def __init__(self, client: ModbusSerialClient | ModbusTcpClient, device_id: int):
        self.client = client
        self.device_id = device_id
        self.device_type: DeviceType | None = self.DEVICE_TYPE
        self.bus_lock: threading.RLock = threading.RLock()
        self._table_sizes: dict[RegisterType, int] = {}
        self.link: Link | None = None  # set by DeviceManager

    # ---- transactions (the only code that touches the wire) ------------

    def _execute(self, what: str, request: Callable[[], Any]) -> Any:
        with self.bus_lock:
            try:
                result = request()
            except (ModbusException, OSError) as exc:
                raise DeviceUnavailable(f"{self.connection_info()}: no response to {what}: {exc}") from exc
        if result.isError():
            code = getattr(result, "exception_code", None)
            if code is None:
                raise DeviceUnavailable(f"{self.connection_info()}: {what} failed: {result}")
            raise exception_response(code, f"{self.connection_info()}: {what} rejected")
        return result

    def read_block(self, reg_type: RegisterType, address: int, count: int) -> list[int]:
        """Read ``count`` raw words starting at ``address`` in one transaction."""
        what = f"{reg_type.value} read address={address} count={count}"
        if reg_type is RegisterType.INPUT:
            read = self.client.read_input_registers
        else:
            read = self.client.read_holding_registers
        result = self._execute(what, lambda: read(address=address, count=count, device_id=self.device_id))
        return list(result.registers)

    def read_raw_block(self, address: int, count: int = 1) -> list[int]:
        """Read raw input-register words (kept for API compatibility)."""
        return self.read_block(RegisterType.INPUT, address, count)

    def write_words(self, address: int, words: list[int]) -> None:
        """Write raw words to holding registers (FC06 for one word, FC16 otherwise)."""
        what = f"write address={address} count={len(words)}"
        if len(words) == 1:
            self._execute(what, lambda: self.client.write_register(address=address, value=int(words[0]), device_id=self.device_id))
        else:
            self._execute(what, lambda: self.client.write_registers(address=address, values=[int(w) for w in words], device_id=self.device_id))

    @contextmanager
    def bus_transaction(self):
        """Hold the bus lock across several transactions (reentrant)."""
        with self.bus_lock:
            yield self

    # ---- table layout ----------------------------------------------------

    def table_size(self, reg_type: RegisterType) -> int:
        """Number of registers of ``reg_type`` the connected firmware implements."""
        if reg_type not in self._table_sizes:
            self._table_sizes[reg_type] = self._detect_table_size(reg_type)
        return self._table_sizes[reg_type]

    def _detect_table_size(self, reg_type: RegisterType) -> int:
        size = self._map_sizes.get(reg_type, 0)
        if size == 0:
            return 0
        with self.bus_lock:
            if self._register_exists(reg_type, size - 1):
                return size
            # Older firmware: binary search for the last implemented address.
            low, high = 1, size - 1
            while low < high:
                middle = (low + high + 1) // 2
                if self._register_exists(reg_type, middle - 1):
                    low = middle
                else:
                    high = middle - 1
        logger.info("%s implements %d of %d %s registers (older firmware)", self.connection_info(), low, size, reg_type.value)
        return low

    def _register_exists(self, reg_type: RegisterType, address: int) -> bool:
        try:
            self.read_block(reg_type, address, 1)
        except IllegalDataAddress:
            return False
        return True

    def available_registers(self, reg_type: RegisterType | None = None) -> dict[str, RegisterSpec]:
        """Map entries implemented by the connected firmware (detects table sizes)."""
        return {
            name: spec
            for name, spec in self.REGISTER_MAP.items()
            if (reg_type is None or spec.reg_type is reg_type) and spec.address < self.table_size(spec.reg_type)
        }

    # ---- named access ---------------------------------------------------

    def read(self, name: str, *, raw: bool = False) -> Any:
        """Read one named register; ``raw=True`` returns the unscaled count."""
        spec = self._get_spec(name)
        words = self.read_block(spec.reg_type, spec.address, spec.count)
        return decode_register_value(words[0], spec, raw=raw)

    def write(self, name: str, value: Any, *, raw: bool = False) -> None:
        """Write one holding register. Values outside the firmware limits raise ValueError."""
        spec = self._get_spec(name)
        if not spec.writable:
            raise ValueError(f"Cannot write {name!r}: input registers are read-only")
        self.write_words(spec.address, [encode_register_value(value, spec, raw=raw)])

    def read_registers(self, reg_type: RegisterType, *, raw: bool = False) -> dict[str, Any]:
        """Read every implemented register of one type in a single transaction."""
        count = self.table_size(reg_type)
        if count == 0:
            return {}
        words = self.read_block(reg_type, 0, count)
        return decode_register_block(
            words, start_address=0, register_type=reg_type, register_index=self._register_index, raw=raw
        )

    def read_snapshot(self, *, raw: bool = False) -> dict[str, Any]:
        """All implemented input registers, read in one FC04 transaction."""
        return self.read_registers(RegisterType.INPUT, raw=raw)

    def get_all_input_registers(self, *, raw: bool = False) -> dict[str, Any]:
        return self.read_registers(RegisterType.INPUT, raw=raw)

    def get_all_holding_registers(self, *, raw: bool = False) -> dict[str, Any]:
        return self.read_registers(RegisterType.HOLDING, raw=raw)

    def identify(self) -> DeviceIdentity:
        """Read the identity words (and, on newer firmware, register version and serial)."""
        hardware, firmware = self.read_block(RegisterType.INPUT, 0, 2)
        version_spec = self.REGISTER_MAP.get("modbus_reg_version")
        if version_spec is None or version_spec.address + 2 >= self.table_size(RegisterType.INPUT):
            return DeviceIdentity.from_words(hardware, firmware)
        version, serial_hi, serial_lo = self.read_block(RegisterType.INPUT, version_spec.address, 3)
        return DeviceIdentity.from_words(hardware, firmware, version, serial_hi, serial_lo)

    # ---- codec (compatibility wrappers) ------------------------------------

    def decode(self, raw: list[int], spec: RegisterSpec, raw_mode: bool = False) -> Any:
        return decode_register_value(raw[0], spec, raw=raw_mode)

    def encode(self, value: Any, spec: RegisterSpec, raw_mode: bool = False) -> list[int]:
        return [encode_register_value(value, spec, raw=raw_mode)]

    def _get_spec(self, name: str) -> RegisterSpec:
        try:
            return self.REGISTER_MAP[name]
        except KeyError as exc:
            raise KeyError(f"Unknown register {name!r}") from exc

    def get_register_address(self, name: str) -> int:
        return self._get_spec(name).address

    # ---- connection -----------------------------------------------------

    def connect(self) -> None:
        with self.bus_lock:
            if not self.client.connect():
                raise DeviceUnavailable(f"Could not connect to {self.connection_info()}")

    def disconnect(self) -> None:
        with self.bus_lock:
            self.client.close()

    close = disconnect

    def __str__(self) -> str:
        return self.connection_info()

    def connection_info(self) -> str:
        """Human-readable endpoint, e.g. ``serial://COM3:1`` or ``192.168.10.128:5001:1``."""
        if isinstance(self.client, ModbusSerialClient):
            return f"serial://{self.client.comm_params.host}:{self.device_id}"
        if isinstance(self.client, ModbusTcpClient):
            params = self.client.comm_params
            return f"{params.host}:{params.port}:{self.device_id}"
        return f"{type(self.client).__name__}:{self.device_id}"

    def get_status(self) -> str:
        """Formatted dump of all implemented registers, for debugging."""
        with self.bus_transaction():
            holding = self.get_all_holding_registers()
            inputs = self.get_all_input_registers()
        lines = [f"Device {self.device_type.name if self.device_type else '?'}: {self.connection_info()}"]
        for title, values in (("holding", holding), ("input", inputs)):
            lines.append(f"== {title} registers ==")
            for name, value in values.items():
                unit = self.REGISTER_MAP[name].unit or ""
                lines.append(f"{name}: {value} {unit}".rstrip())
        return "\n".join(lines) + "\n"

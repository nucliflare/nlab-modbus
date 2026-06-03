import threading
from contextlib import contextmanager
from typing import Any

from pymodbus.client import ModbusSerialClient, ModbusTcpClient

from nlab_modbus.core.register_specs import RegisterSpec, RegisterType


class BaseModbusDevice:
    REGISTER_MAP: dict[str, RegisterSpec] = {}

    def __init__(self, client: ModbusSerialClient | ModbusTcpClient, device_id: int):
        self.client = client
        self.device_id = device_id
        self.device_type = None
        # Per-bus lock. Defaults to a private RLock so a standalone device
        # (constructed without a manager) is still internally consistent.
        # DeviceManager overwrites this with the lock shared by every device
        # on the same transport, so all traffic on one RS485 bus / one TCP
        # socket is serialized. RLock (not Lock) so composite operations that
        # hold the lock can still call the primitives without self-deadlock.
        self.bus_lock: threading.RLock = threading.RLock()

    # ---- concurrency control -------------------------------------------

    @contextmanager
    def bus_transaction(self):
        """Hold the bus lock across multiple primitive transactions.

        Use when a sequence of reads/writes must be coherent w.r.t. other
        devices on the same bus (e.g. an atomic snapshot, or read-modify-write
        of a holding register). Without this, individual frames are still
        atomic but another device may transmit between your transactions.

        Reentrant: the primitives below take the same lock, so nesting is safe.
        """
        with self.bus_lock:
            yield self

    # ---- high-level read/write -----------------------------------------

    def read(self, name: str) -> Any:
        spec = self._get_spec(name)
        raw = self.read_raw(name)
        return self.decode(raw, spec)

    def write(self, name: str, value: Any) -> None:
        spec = self._get_spec(name)
        raw = self.encode(value, spec)
        self.write_raw(name, raw)

    # ---- primitive transactions (the only methods that touch the wire) --

    def read_raw(self, name: str) -> list[int]:
        spec = self._get_spec(name)

        with self.bus_lock:
            if spec.reg_type == RegisterType.INPUT:
                result = self.client.read_input_registers(
                    address=spec.address,
                    count=spec.count,
                    device_id=self.device_id,
                )
            elif spec.reg_type == RegisterType.HOLDING:
                result = self.client.read_holding_registers(
                    address=spec.address,
                    count=spec.count,
                    device_id=self.device_id,
                )
            else:
                raise ValueError(f"Unsupported register type for {name!r}: {spec.reg_type}")

        if result.isError():
            raise RuntimeError(f"Failed to read {name!r}: {result}")

        return result.registers

    def read_raw_block(self, address: int, count: int = 1):
        with self.bus_lock:
            result_raw = self.client.read_input_registers(
                address=address,
                count=count,
                device_id=self.device_id,
            )
        # Preserve original behaviour (no isError check here), but you should
        # consider adding one — a timeout returns an ExceptionResponse whose
        # .registers access will raise an AttributeError downstream.
        return result_raw.registers

    def write_raw(self, name: str, registers: list[int]) -> None:
        spec = self._get_spec(name)

        if spec.reg_type != RegisterType.HOLDING:
            raise ValueError(f"Cannot write {name!r}: only holding registers are writable in Modbus")

        if len(registers) != spec.count:
            raise ValueError(f"Cannot write {name!r}: expected {spec.count} register(s), got {len(registers)}")

        with self.bus_lock:
            if spec.count == 1:
                result = self.client.write_register(
                    address=spec.address,
                    value=registers[0],
                    device_id=self.device_id,
                )
            else:
                result = self.client.write_registers(
                    address=spec.address,
                    values=registers,
                    device_id=self.device_id,
                )

        if result.isError():
            raise RuntimeError(f"Failed to write {name!r}: {result}")

    # ---- codec ----------------------------------------------------------

    def decode(self, raw: list[int], spec: RegisterSpec) -> Any:
        if spec.dtype == "uint16":
            return raw[0] * spec.scale

        if spec.dtype == "int16":
            value = raw[0]
            if value >= 0x8000:
                value -= 0x10000
            return value * spec.scale

        if spec.dtype == "bool":
            return bool(raw[0])

        raise NotImplementedError(f"Unsupported dtype for decoding: {spec.dtype}")

    def encode(self, value: Any, spec: RegisterSpec) -> list[int]:
        if spec.dtype == "uint16":
            raw_value = round((value) / spec.scale)
            if not 0 <= raw_value <= 0xFFFF:
                raise ValueError(f"Encoded uint16 value out of range: {raw_value}")
            return [raw_value]

        if spec.dtype == "int16":
            raw_value = round((value) / spec.scale)
            if not -0x8000 <= raw_value <= 0x7FFF:
                raise ValueError(f"Encoded int16 value out of range: {raw_value}")
            if raw_value < 0:
                raw_value += 0x10000
            return [raw_value]

        if spec.dtype == "bool":
            return [1 if value else 0]

        raise NotImplementedError(f"Unsupported dtype for encoding: {spec.dtype}")

    def _get_spec(self, name: str) -> RegisterSpec:
        try:
            return self.REGISTER_MAP[name]
        except KeyError as exc:
            raise KeyError(f"Unknown register {name!r}") from exc

    # ---- connection -----------------------------------------------------

    def connect(self) -> None:
        """Open connection to the Modbus device."""
        with self.bus_lock:
            if not self.client.connect():
                raise ConnectionError("Could not connect to Modbus device")

    def disconnect(self) -> None:
        """Close connection to the Modbus device."""
        with self.bus_lock:
            self.client.close()

    def close(self) -> None:
        """Alias for disconnect(), useful because PyModbus uses close()."""
        self.disconnect()

    def connection_info(self) -> str:
        if isinstance(self.client, ModbusSerialClient):
            return f"serial://{self.client.comm_params.host}:{self.device_id}"
        if isinstance(self.client, ModbusTcpClient):
            return f"{self.client.comm_params.host}:{self.client.comm_params.port}:{self.device_id}"
        return f"unknown://{type(self.client).__name__}"

    # ---- composite reads (issue many transactions) ---------------------

    def get_all_holding_registers(self) -> dict:
        """All holding register values, coherent w.r.t. other bus traffic."""
        result = {}
        with self.bus_transaction():
            for reg_name, spec in self.REGISTER_MAP.items():
                if spec.reg_type == RegisterType.HOLDING:
                    result[reg_name] = int(self.read(reg_name))
        return result

    def get_all_input_registers(self) -> dict:
        """All input register values, coherent w.r.t. other bus traffic."""
        result = {}
        with self.bus_transaction():
            for reg_name, spec in self.REGISTER_MAP.items():
                if spec.reg_type == RegisterType.INPUT:
                    result[reg_name] = self.read(reg_name)
        return result

    def get_status(self) -> str:
        lines = []
        with self.bus_transaction():
            if self.device_type is not None:
                lines.append(f"Device {self.device_type.name}: {self.connection_info()}")
            lines.append("== Status of holding registers ==")
            for i, (key, value) in enumerate(self.get_all_holding_registers().items(), start=1):
                lines.append(f"{i}. {key}: {value}")

            lines.append("")
            lines.append("== Status of input registers ==")
            for i, (key, value) in enumerate(self.get_all_input_registers().items(), start=1):
                lines.append(f"{i}. {key}: {value}")

        return "\n".join(lines) + "\n"

    def get_register_address(self, name):
        return self.REGISTER_MAP[name].address

from typing import Any

from pymodbus.client import ModbusSerialClient, ModbusTcpClient

from nlab_modbus.core.register_specs import RegisterSpec, RegisterType


class BaseModbusDevice:
    register_map: dict[str, RegisterSpec] = {}

    def __init__(self, client: ModbusSerialClient | ModbusTcpClient, device_id: int):
        self.client = client
        self.device_id = device_id
        self.device_type = None

    def read(self, name: str) -> Any:
        spec = self._get_spec(name)
        # self._ensure_readable(name, spec)

        raw = self.read_raw(name)
        return self.decode(raw, spec)

    def write(self, name: str, value: Any) -> None:
        spec = self._get_spec(name)
        # self._ensure_writable(name, spec)

        raw = self.encode(value, spec)
        self.write_raw(name, raw)

    def read_raw(self, name: str) -> list[int]:
        spec = self._get_spec(name)

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

    def write_raw(self, name: str, registers: list[int]) -> None:
        spec = self._get_spec(name)

        if spec.reg_type != RegisterType.HOLDING:
            raise ValueError(f"Cannot write {name!r}: only holding registers are writable in Modbus")

        if len(registers) != spec.count:
            raise ValueError(f"Cannot write {name!r}: expected {spec.count} register(s), got {len(registers)}")

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
            return self.register_map[name]
        except KeyError as exc:
            raise KeyError(f"Unknown register {name!r}") from exc

    def connect(self) -> None:
        """Open connection to the Modbus device."""
        if not self.client.connect():
            raise ConnectionError("Could not connect to Modbus device")

    def disconnect(self) -> None:
        """Close connection to the Modbus device."""
        self.client.close()

    def close(self) -> None:
        """Alias for disconnect(), useful because PyModbus uses close()."""
        self.disconnect()

    def connection_info(self) -> str:
        """Return a human-readable description of the client connection.

        Returns
        -------
        str
            ``"serial://<port>"`` for ModbusSerialClient or
            ``"<host>:<port>"`` for ModbusTcpClient.
        """
        from pymodbus.client import ModbusSerialClient, ModbusTcpClient

        if isinstance(self.client, ModbusSerialClient):
            return f"serial://{self.client.comm_params.host}:{self.device_id}"

        if isinstance(self.client, ModbusTcpClient):
            return f"{self.client.comm_params.host}:{self.client.comm_params.port}:{self.device_id}"

        return f"unknown://{type(self.client).__name__}"

    def get_all_holding_registers(self) -> dict:
        """
        Get all holding register values in the order defined in PSU_REGISTER_MAP.

        Returns:
            dict: A dictionary mapping register names to their current values.
        """
        result = {}
        for reg_name, spec in self.register_map.items():
            if spec.reg_type == RegisterType.HOLDING:
                result[reg_name] = self.read(reg_name)
        return result

    def get_all_input_registers(self) -> dict:
        """
        Get all input register values in the order defined in PSU_REGISTER_MAP.

        Returns:
            dict: A dictionary mapping register names to their current values.
        """
        result = {}
        for reg_name, spec in self.register_map.items():
            if spec.reg_type == RegisterType.INPUT:
                result[reg_name] = self.read(reg_name)
        return result

    def get_status(self) -> str:
        lines = []

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

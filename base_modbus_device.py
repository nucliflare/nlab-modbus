from register_specs import RegisterSpec, RegisterType


class BaseModbusDevice:
    register_map: dict[str, RegisterSpec] = {}

    def __init__(self, client, device_id: int):
        self.client = client
        self.device_id = device_id

    def read_raw(self, name: str) -> list[int]:
        spec = self.register_map[name]

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
            raise ValueError(f"Unsupported register type: {spec.reg_type}")

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

    def _get_spec(self, name: str) -> RegisterSpec:
        try:
            return self.register_map[name]
        except KeyError as exc:
            raise KeyError(f"Unknown register {name!r}") from exc

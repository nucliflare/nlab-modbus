"""In-memory stand-in for a board's Modbus tables, behaving like modbus_protocol.c."""

from __future__ import annotations

from types import SimpleNamespace

from pymodbus.exceptions import ModbusIOException
from pymodbus.pdu import ExceptionResponse

PASSWORD = -4345


class FakeFirmwareClient:
    """Answers FC03/FC04/FC06 from word lists sized like a firmware table.

    Reads past the table end return exception 2 (illegal address). Writes to
    registers listed in ``protected`` return exception 4 unless the holding
    word at ``password_address`` equals the firmware password. ``offline``
    makes every request raise like an unplugged cable.
    """

    def __init__(self, inputs, holdings, *, protected=(), password_address=None):
        self.inputs = list(inputs)
        self.holdings = list(holdings)
        self.protected = set(protected)
        self.password_address = password_address
        self.offline = False
        self.requests: list[tuple] = []

    def _check(self):
        if self.offline:
            raise ModbusIOException("No response received")

    def _read(self, table, function_code, address, count, device_id):
        self._check()
        self.requests.append((function_code, address, count))
        if count < 1 or address + count > len(table):
            return ExceptionResponse(function_code, exception_code=2, device_id=device_id)
        return SimpleNamespace(registers=list(table[address:address + count]), isError=lambda: False)

    def read_input_registers(self, *, address, count, device_id):
        return self._read(self.inputs, 0x04, address, count, device_id)

    def read_holding_registers(self, *, address, count, device_id):
        return self._read(self.holdings, 0x03, address, count, device_id)

    def write_register(self, *, address, value, device_id):
        self._check()
        self.requests.append((0x06, address, value))
        if address >= len(self.holdings):
            return ExceptionResponse(0x06, exception_code=2, device_id=device_id)
        if address in self.protected and self._locked():
            return ExceptionResponse(0x06, exception_code=4, device_id=device_id)
        self.holdings[address] = value
        return SimpleNamespace(isError=lambda: False)

    def _locked(self) -> bool:
        if self.password_address is None:
            return False
        word = self.holdings[self.password_address]
        return (word - 0x10000 if word >= 0x8000 else word) != PASSWORD

    def connect(self):
        return not self.offline

    def close(self):
        pass

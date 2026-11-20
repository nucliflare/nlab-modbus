"""Typed errors raised by device I/O, so callers never parse pymodbus messages."""

from __future__ import annotations


class ModbusDeviceError(RuntimeError):
    """Base class for all device communication errors."""


class DeviceUnavailable(ModbusDeviceError):
    """No (valid) response: timeout, closed port, unplugged cable, CRC failure."""


class ModbusExceptionResponse(ModbusDeviceError):
    """The device answered with a Modbus exception code."""

    code: int = 0

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class IllegalDataAddress(ModbusExceptionResponse):
    """Exception 2: the register does not exist in this firmware's table."""

    code = 2


class IllegalDataValue(ModbusExceptionResponse):
    """Exception 3: the firmware rejected the value (outside its limits)."""

    code = 3


class PasswordRequired(ModbusExceptionResponse):
    """Exception 4: the write needs the service password (device is locked)."""

    code = 4


_BY_CODE = {cls.code: cls for cls in (IllegalDataAddress, IllegalDataValue, PasswordRequired)}


def exception_response(code: int, message: str) -> ModbusExceptionResponse:
    """Return the most specific error class for a Modbus exception code."""
    cls = _BY_CODE.get(code, ModbusExceptionResponse)
    return cls(f"{message} (exception_code={code})", code)

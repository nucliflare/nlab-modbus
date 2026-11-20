"""Client construction and timing policy for the three ways to reach a board.

| Link                      | Baud                                   | Modbus address          |
|---------------------------|----------------------------------------|-------------------------|
| MicroUSB                  | firmware UART fixed at 115200          | always 1                |
| USB-RS485 adapter         | ``rs485_baud`` (default 9600)          | ``rs485_mb_addr``       |
| Digitizer ser2net gateway | fixed by ser2net.yaml (9600)           | ``rs485_mb_addr``       |

Every client is created here with ``retries=0``: a timed-out write may already
have been applied (EEPROM-backed writes reply 15-55 ms later than RAM-only
ones), so resending is left to the caller.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from pymodbus.framer import FramerType

# Scan order: 9600 is the firmware's RS-485 default (and works on the
# baud-agnostic MicroUSB bridge); 115200 covers re-configured RS-485 buses.
DEFAULT_BAUDRATES: tuple[int, ...] = (9600, 115200)
COMMON_BAUDRATES: tuple[int, ...] = (9600, 19200, 38400, 57600, 115200)
GATEWAY_BAUDRATE = 9600  # ser2net.yaml on the digitizer: 9600n81
GATEWAY_PORTS: tuple[int, ...] = (5001, 5002)
MDNS_NAME = "nucliflare"

# Raw frames are logged here at DEBUG, but only while enabled (off by default).
FRAME_LOGGER = "nlab_modbus.frames"
_frames = logging.getLogger(FRAME_LOGGER)
_frames.setLevel(logging.WARNING)

_LARGEST_FRAME = 8 + 5 + 2 * 32  # request + response bytes for a 32-register block
_PROBE_FRAME = 8 + 9  # request + response bytes for a 2-register identity read
_BITS_PER_BYTE = 11  # start + 8 data + stop + RTU inter-character slack


def response_timeout(baudrate: int) -> float:
    """Timeout for regular traffic: the largest block read or an EEPROM-backed write."""
    return round(0.15 + _LARGEST_FRAME * _BITS_PER_BYTE / baudrate, 2)


def probe_timeout(baudrate: int) -> float:
    """Short timeout for discovery probes (USB adapter latency + wire time)."""
    return round(0.05 + 1.5 * _PROBE_FRAME * _BITS_PER_BYTE / baudrate, 2)


def gateway_timeout(*, probe: bool = False) -> float:
    """Timeouts for RTU over TCP: the bus behind ser2net plus network latency."""
    return (probe_timeout if probe else response_timeout)(GATEWAY_BAUDRATE) + 0.02


@dataclass(frozen=True)
class Link:
    """Where a device is reached: a serial port at a baud rate, or a TCP gateway port."""

    kind: str  # "serial" or "tcp"
    address: str  # COM port / device path, or host
    port: int | None = None  # TCP port
    baudrate: int | None = None  # serial baud rate; the gateway fixes its own

    @property
    def key(self) -> tuple:
        """Transport identity: one client (and bus lock) per key."""
        return ("serial", self.address) if self.kind == "serial" else ("tcp", self.address, self.port)

    def __str__(self) -> str:
        if self.kind == "serial":
            return f"{self.address} @ {self.baudrate}"
        return f"{self.address}:{self.port}"


def set_frame_logging(enabled: bool) -> None:
    """Log every request (TX) and received chunk (RX) in hex on ``FRAME_LOGGER``."""
    _frames.setLevel(logging.DEBUG if enabled else logging.WARNING)


def frame_logging_enabled() -> bool:
    return _frames.isEnabledFor(logging.DEBUG)


def _hex(data: bytes) -> str:
    return " ".join(f"{byte:02X}" for byte in data)


def _frame_tracers(label: str) -> dict:
    """pymodbus trace hooks logging each request (TX) and each complete reply (RX) in hex.

    pymodbus reports the receive buffer as it grows, so RX is logged once, when
    the reply has been decoded; a partial reply is logged as incomplete before
    the next request.
    """
    pending = {"rx": b""}

    def flush_incomplete() -> None:
        if pending["rx"]:
            _frames.debug("%s RX %-10s %s", label, "incomplete", _hex(pending["rx"]))
            pending["rx"] = b""

    def trace_packet(sending: bool, data: bytes) -> bytes:
        if not _frames.isEnabledFor(logging.DEBUG):
            pending["rx"] = b""
        elif sending:
            flush_incomplete()
            header = f"id {data[0]} FC{data[1]:02d}" if len(data) > 1 else ""
            _frames.debug("%s TX %-10s %s", label, header, _hex(data))
        elif data:
            previous = pending["rx"]
            pending["rx"] = data if data.startswith(previous) else previous + data
        return data

    def trace_pdu(sending: bool, pdu):
        if not sending and pending["rx"] and _frames.isEnabledFor(logging.DEBUG):
            _frames.debug("%s RX %-10s %s", label, "", _hex(pending["rx"]))
            pending["rx"] = b""
        return pdu

    return {"trace_packet": trace_packet, "trace_pdu": trace_pdu}


def serial_client(port: str, baudrate: int, *, timeout: float | None = None) -> ModbusSerialClient:
    """RTU client on a local serial port, 8N1 (the only framing the firmware supports)."""
    client = ModbusSerialClient(
        port=port,
        framer=FramerType.RTU,
        baudrate=baudrate,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=response_timeout(baudrate) if timeout is None else timeout,
        retries=0,
        **_frame_tracers(port),
    )
    return client


def tcp_client(host: str, port: int, *, timeout: float | None = None) -> ModbusTcpClient:
    """RTU-over-TCP client for a ser2net gateway (raw RTU frames, not Modbus/TCP)."""
    client = ModbusTcpClient(
        host=host,
        port=port,
        framer=FramerType.RTU,
        timeout=gateway_timeout() if timeout is None else timeout,
        retries=0,
        **_frame_tracers(f"{host}:{port}"),
    )
    return client

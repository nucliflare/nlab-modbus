from __future__ import annotations

import logging
import queue
import time
from dataclasses import dataclass
from threading import Event
from typing import Any

from PySide6.QtCore import QThread, Signal

from nlab_modbus.core.base_modbus_device import BaseModbusDevice
from nlab_modbus.core.errors import DeviceUnavailable, PasswordRequired
from nlab_modbus.core.register_specs import RegisterType

logger = logging.getLogger(__name__)

# Writing these re-initialises the board's RS-485 port. Over RS-485 the
# firmware drops its reply and the next two frames, even though the write is
# applied; over MicroUSB the link is unaffected.
TRANSPORT_REGISTERS = frozenset({"rs485_mb_addr", "rs485_baud"})


@dataclass(frozen=True)
class RegisterWriteCommand:
    """Raw-count write queued by the GUI and executed by the polling thread."""

    register_id: int
    register_name: str
    new_value: int


@dataclass(frozen=True)
class ServiceUnlockCommand:
    """Write the service password, then verify it with a no-op protected write."""

    password: int


class DevicePollingThread(QThread):
    """Polls one device and executes its queued writes, all on one thread.

    Each cycle: a bounded batch of queued writes, one input-table read, and a
    holding-table read every ``holding_refresh_rate_ms``. Every transaction
    goes through ``device.bus_lock``, so devices sharing a bus take turns.
    """

    input_registers_updated = Signal(float, dict)
    holding_registers_updated = Signal(dict)

    write_succeeded = Signal(str)  # register name
    write_failed = Signal(str, str, bool)  # register name, message, password required
    transport_changed = Signal(str, int)  # register name, new raw value
    service_unlock_finished = Signal(bool)  # password accepted

    polling_failed = Signal(str)
    connection_lost = Signal(str)
    stopped = Signal()

    def __init__(
        self,
        device: BaseModbusDevice,
        refresh_rate_ms: int = 500,
        holding_refresh_rate_ms: int = 1000,
        max_consecutive_failures: int = 3,
        max_writes_per_cycle: int = 8,
        parent: Any | None = None,
    ) -> None:
        super().__init__(parent)
        self.device = device
        self.refresh_rate_ms = refresh_rate_ms
        self.holding_refresh_rate_ms = holding_refresh_rate_ms
        self.max_consecutive_failures = max(1, max_consecutive_failures)
        self.max_writes_per_cycle = max(1, max_writes_per_cycle)
        self._stop_event = Event()
        self._write_queue: queue.Queue[RegisterWriteCommand | ServiceUnlockCommand] = queue.Queue()
        self._last_holding_poll = 0.0
        self._consecutive_failures = 0
        self._t0 = time.perf_counter()

    # ---- lifecycle -------------------------------------------------------

    def run(self) -> None:
        logger.info("Polling %s every %d ms", self.device, self.refresh_rate_ms)
        self._t0 = time.perf_counter()
        self._last_holding_poll = time.monotonic()
        try:
            while not self._stop_event.is_set():
                started = time.monotonic()
                self._process_pending_writes()
                if self._stop_event.is_set():
                    break
                if self._poll_device_once():
                    self._consecutive_failures = 0
                else:
                    self._consecutive_failures += 1
                    if self._consecutive_failures >= self.max_consecutive_failures:
                        message = f"Device stopped responding after {self._consecutive_failures} consecutive polls"
                        logger.error("%s: %s", self.device, message)
                        self.connection_lost.emit(message)
                        break
                    continue
                if time.monotonic() - self._last_holding_poll >= self.holding_refresh_rate_ms / 1000:
                    self._poll_holding_registers()
                self._stop_event.wait(max(0.0, self.refresh_rate_ms / 1000 - (time.monotonic() - started)))
        finally:
            logger.info("Polling stopped for %s", self.device)
            self.stopped.emit()

    def stop(self) -> None:
        """Request shutdown; returns immediately (the current transaction finishes first)."""
        self._stop_event.set()

    def update_refresh_rate(self, new_value_ms: int) -> None:
        self.refresh_rate_ms = new_value_ms

    def update_holding_refresh_rate(self, new_value_ms: int) -> None:
        self.holding_refresh_rate_ms = new_value_ms

    # ---- write path --------------------------------------------------------

    def enqueue_write_command(self, register_id: int, register_name: str, new_value: int) -> None:
        """Queue a raw-count holding-register write (any thread)."""
        self._write_queue.put(RegisterWriteCommand(register_id, register_name, int(new_value)))

    def enqueue_service_unlock(self, password: int) -> None:
        """Queue a verified service-password unlock (any thread)."""
        self._write_queue.put(ServiceUnlockCommand(int(password)))

    def _process_pending_writes(self) -> None:
        """Run at most ``max_writes_per_cycle`` queued commands, then refresh holdings once."""
        wrote = False
        for _ in range(self.max_writes_per_cycle):
            if self._stop_event.is_set():
                return
            try:
                command = self._write_queue.get_nowait()
            except queue.Empty:
                break
            try:
                if isinstance(command, ServiceUnlockCommand):
                    self._unlock(command.password)
                elif command.register_name in TRANSPORT_REGISTERS:
                    self._write_transport_register(command)
                else:
                    self._write(command)
                wrote = True
            finally:
                self._write_queue.task_done()
        if wrote and not self._stop_event.is_set():
            self._poll_holding_registers()

    def _write(self, command: RegisterWriteCommand) -> bool:
        try:
            self.device.write(command.register_name, command.new_value, raw=True)
        except Exception as exc:
            password_required = isinstance(exc, PasswordRequired)
            if password_required:
                logger.warning("Write of %s rejected: service password required", command.register_name)
            else:
                logger.error("Write of %s failed: %s", command.register_name, exc)
            self.write_failed.emit(command.register_name, str(exc), password_required)
            return False
        self.write_succeeded.emit(command.register_name)
        return True

    def _write_transport_register(self, command: RegisterWriteCommand) -> None:
        """Write rs485_*, then check whether this link still reaches the board."""
        try:
            self.device.write(command.register_name, command.new_value, raw=True)
        except DeviceUnavailable:
            pass  # expected over RS-485: the reply is lost but the value is applied
        except Exception as exc:
            self.write_failed.emit(command.register_name, str(exc), isinstance(exc, PasswordRequired))
            return
        if self._link_still_answers():
            logger.info("%s: %s written; this link is unaffected", self.device, command.register_name)
            self.write_succeeded.emit(command.register_name)
            return
        logger.info("%s: %s changed; the old connection settings no longer work", self.device, command.register_name)
        self._stop_event.set()
        self.transport_changed.emit(command.register_name, command.new_value)

    def _link_still_answers(self, attempts: int = 3) -> bool:
        # Three tries: the firmware discards the two frames following the change.
        for _ in range(attempts):
            try:
                self.device.read_block(RegisterType.INPUT, 0, 1)
                return True
            except Exception:
                if self._stop_event.wait(0.05):
                    return False
        return False

    def _unlock(self, password: int) -> None:
        """Firmware accepts any pass_static value, so verify with a no-op protected write."""
        try:
            self.device.write("pass_static", password, raw=True)
            probe = next(
                name for name, spec in self.device.available_registers(RegisterType.HOLDING).items()
                if spec.password_protected
            )
            self.device.write(probe, self.device.read(probe, raw=True), raw=True)
        except PasswordRequired:
            logger.warning("%s: service password rejected", self.device)
            self.service_unlock_finished.emit(False)
            return
        except Exception as exc:
            logger.error("%s: service unlock failed: %s", self.device, exc)
            self.write_failed.emit("pass_static", str(exc), False)
            self.service_unlock_finished.emit(False)
            return
        logger.info("%s: service mode unlocked", self.device)
        self.service_unlock_finished.emit(True)

    # ---- read path ---------------------------------------------------------

    def _poll_holding_registers(self) -> None:
        self._last_holding_poll = time.monotonic()
        try:
            values = self.device.get_all_holding_registers(raw=True)
        except Exception as exc:
            logger.warning("Holding poll failed for %s: %s", self.device, exc)
            self.polling_failed.emit(str(exc))
            return
        self.holding_registers_updated.emit(values)

    def _poll_device_once(self) -> bool:
        """Read the input table in one transaction and emit it with a timestamp."""
        try:
            elapsed = time.perf_counter() - self._t0
            values = self.device.read_snapshot(raw=True)
        except Exception as exc:
            logger.warning("Polling failed for %s: %s", self.device, exc)
            self.polling_failed.emit(str(exc))
            return False
        self.input_registers_updated.emit(elapsed, values)
        return True

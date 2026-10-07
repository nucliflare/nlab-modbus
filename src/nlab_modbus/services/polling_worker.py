import logging
import queue
import time
from dataclasses import dataclass
from threading import Event
from typing import Any

from PySide6.QtCore import QThread, Signal

from nlab_modbus.core.base_modbus_device import BaseModbusDevice

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RegisterWriteCommand:
    """Immutable write request queued by the GUI and consumed by the polling thread.

    new_value is an engineering value (e.g. volts, °C) as displayed in the GUI.
    The device codec converts it to raw register counts via encode() at execution
    time.  Frozen to prevent accidental mutation while the command sits in the queue.
    """

    register_id: int
    register_name: str
    # Engineering value as shown in the GUI. The device's encode() converts
    # this to raw register counts. If your GUI already produces raw counts,
    # rename this to new_raw and switch _execute_write to write_raw (see note).
    new_value: float


class DevicePollingThread(QThread):
    """
    Polls one Modbus device in a background thread.

    Responsibilities:
    - periodically read input/holding register snapshots
    - emit fresh data to the GUI/controller
    - accept queued write commands from the GUI/controller
    - execute queued writes safely inside the polling loop
    - stop cleanly when requested

    Thread-safety: all device access (reads and writes) happens in this one
    thread and goes through device.bus_lock, so it is serialized against any
    other thread sharing the same bus. Writes are funneled through a queue so
    the GUI thread never touches the device directly.
    """

    input_registers_updated = Signal(float, dict)
    holding_registers_updated = Signal(dict)

    write_succeeded = Signal(str)
    write_failed = Signal(str)
    transport_changed = Signal(str)

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
        initial_input_values: dict[str, Any] | None = None,
        parent: Any | None = None,
    ) -> None:
        super().__init__(parent)

        self.device = device
        self.refresh_rate_ms = refresh_rate_ms
        self.holding_refresh_rate_ms = holding_refresh_rate_ms
        self.max_consecutive_failures = max(1, max_consecutive_failures)
        self.max_writes_per_cycle = max(1, max_writes_per_cycle)

        self._stop_event = Event()
        self._write_queue: queue.Queue[RegisterWriteCommand] = queue.Queue()
        self._last_holding_poll: float = 0.0
        self._consecutive_failures = 0
        self._input_values_cache = dict(initial_input_values or {})

    # ---- thread lifecycle ----------------------------------------------

    def run(self) -> None:
        """Main loop. Runs in the worker thread after .start()."""
        logger.info(
            "Starting polling thread for device %s with refresh rate %d ms",
            self.device,
            self.refresh_rate_ms,
        )
        self._t0 = time.perf_counter()
        self._last_holding_poll = time.monotonic()

        try:
            while not self._stop_event.is_set():
                loop_start = time.monotonic()

                self._process_pending_writes()
                if self._stop_event.is_set():
                    break
                input_poll_succeeded = self._poll_device_once()
                if input_poll_succeeded:
                    self._consecutive_failures = 0
                else:
                    self._consecutive_failures += 1
                    if self._consecutive_failures >= self.max_consecutive_failures:
                        message = (
                            f"Device stopped responding after "
                            f"{self._consecutive_failures} consecutive polls"
                        )
                        logger.error("%s: %s", self.device, message)
                        self.connection_lost.emit(message)
                        break

                now = time.monotonic()
                if input_poll_succeeded and now - self._last_holding_poll >= self.holding_refresh_rate_ms / 1000.0:
                    if not self._stop_event.is_set():
                        self._poll_holding_registers()
                    self._last_holding_poll = now

                elapsed = time.monotonic() - loop_start
                refresh_period_s = self.refresh_rate_ms / 1000.0
                sleep_time = max(0.0, refresh_period_s - elapsed)
                if sleep_time > 0:
                    self._stop_event.wait(sleep_time)
        finally:
            logger.info("Polling thread stopped for device %s", self.device)
            self.stopped.emit()

    def stop(self) -> None:
        """Request clean shutdown. Call from the GUI, then thread.wait()."""
        self._stop_event.set()

    def update_refresh_rate(self, new_value_ms: int) -> None:
        """Change the input register polling interval. Safe to call from any thread."""
        self.refresh_rate_ms = new_value_ms

    def update_holding_refresh_rate(self, new_value_ms: int) -> None:
        """Change the holding register polling interval. Safe to call from any thread."""
        self.holding_refresh_rate_ms = new_value_ms

    # ---- write path -----------------------------------------------------

    def enqueue_write_command(
        self,
        register_id: int,
        register_name: str,
        new_value: float,
    ) -> None:
        """Queue a holding-register write. Safe to call from the GUI thread."""
        logger.debug("Queueing write: id=%s name=%s value=%s", register_id, register_name, new_value)
        self._write_queue.put(
            RegisterWriteCommand(
                register_id=register_id,
                register_name=register_name,
                new_value=new_value,
            )
        )

    def _process_pending_writes(self) -> None:
        """Execute a bounded write batch, then read holding registers once.

        Runs inside the polling thread, so device access stays serialized. The
        holding-register sweep is deliberately outside the drain loop: doing it
        per-write would hammer a shared bus for no benefit. Bounding each batch
        prevents a busy editor from starving telemetry and disconnect checks.
        """
        did_write = False

        for _ in range(self.max_writes_per_cycle):
            if self._stop_event.is_set():
                break
            try:
                command = self._write_queue.get_nowait()
            except queue.Empty:
                break

            try:
                self._execute_write(command)
            except Exception as exc:
                error_str = f"{command.register_name}: {exc}"
                if "exception_code=4" in str(exc):
                    logger.warning("Write rejected (password?) for register %s", command.register_name)
                else:
                    logger.exception("Write failed for register %s", command.register_name)
                self.write_failed.emit(error_str)
            else:
                self.write_succeeded.emit(f"{command.register_name}: OK")
                did_write = True
                if command.register_name in {"rs485_mb_addr", "rs485_baud"}:
                    self._stop_event.set()
                    self.transport_changed.emit(command.register_name)
            finally:
                self._write_queue.task_done()

            if self._stop_event.is_set():
                break

        if did_write and not self._stop_event.is_set():
            self._poll_holding_registers()
            self._last_holding_poll = time.monotonic()

    def _execute_write(self, command: RegisterWriteCommand) -> None:
        """Write one raw register value to the device (no scaling)."""
        self.device.write(command.register_name, command.new_value, raw=True)

    # ---- read path ------------------------------------------------------

    def _poll_holding_registers(self) -> None:
        """Read all holding registers and emit the snapshot."""
        try:
            holding_values = self.device.get_all_holding_registers(raw=True)
        except Exception as exc:
            logger.exception("Holding poll failed for device %s", self.device)
            self.polling_failed.emit(str(exc))
            return
        self.holding_registers_updated.emit(holding_values)

    def _poll_device_once(self) -> bool:
        """Poll input registers once and emit a timestamped snapshot."""
        try:
            t_elapsed = time.perf_counter() - self._t0
            snapshot_reader = getattr(self.device, "read_snapshot", None)
            if callable(snapshot_reader):
                self._input_values_cache.update(snapshot_reader(raw=True))
                input_values = dict(self._input_values_cache)
            else:
                input_values = self.device.get_all_input_registers(raw=True)
        except Exception as exc:
            logger.warning("Polling failed for device %s: %s", self.device, exc)
            self.polling_failed.emit(str(exc))
            return False

        self.input_registers_updated.emit(t_elapsed, input_values)
        return True

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

    polling_failed = Signal(str)
    stopped = Signal()

    def __init__(
        self,
        device: BaseModbusDevice,
        refresh_rate_ms: int = 500,
        parent: Any | None = None,
    ) -> None:
        super().__init__(parent)

        self.device = device
        self.refresh_rate_ms = refresh_rate_ms

        self._stop_event = Event()
        self._write_queue: queue.Queue[RegisterWriteCommand] = queue.Queue()

    # ---- thread lifecycle ----------------------------------------------

    def run(self) -> None:
        """Main loop. Runs in the worker thread after .start()."""
        logger.info(
            "Starting polling thread for device %s with refresh rate %d ms",
            self.device,
            self.refresh_rate_ms,
        )
        self._t0 = time.perf_counter()

        try:
            while not self._stop_event.is_set():
                loop_start = time.monotonic()

                self._process_pending_writes()
                if self._stop_event.is_set():
                    break
                self._poll_device_once()

                elapsed = time.monotonic() - loop_start
                refresh_period_s = self.refresh_rate_ms / 1000.0
                sleep_time = max(0.0, refresh_period_s - elapsed)
                if sleep_time > 0:
                    # Returns immediately if stop() fires during the wait.
                    self._stop_event.wait(sleep_time)
        finally:
            logger.info("Polling thread stopped for device %s", self.device)
            self.stopped.emit()

    def stop(self) -> None:
        """Request clean shutdown. Call from the GUI, then thread.wait()."""
        self._stop_event.set()

    def update_refresh_rate(self, new_value_ms: int) -> None:
        # Read fresh each loop iteration in run(), so this takes effect next cycle.
        self.refresh_rate_ms = new_value_ms

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
        """Drain and execute all queued writes, then read holding regs back ONCE.

        Runs inside the polling thread, so device access stays serialized. The
        holding-register sweep is deliberately outside the drain loop: doing it
        per-write would hammer a shared bus for no benefit, and it only runs at
        all if at least one write actually succeeded.
        """
        did_write = False

        while not self._stop_event.is_set():
            try:
                command = self._write_queue.get_nowait()
            except queue.Empty:
                break

            try:
                self._execute_write(command)
            except Exception as exc:
                logger.exception("Write failed for register %s", command.register_name)
                self.write_failed.emit(f"{command.register_name}: {exc}")
            else:
                self.write_succeeded.emit(f"{command.register_name}: OK")
                did_write = True
            finally:
                self._write_queue.task_done()

        if did_write and not self._stop_event.is_set():
            try:
                holding_values = self.device.get_all_holding_registers()
            except Exception as exc:
                # A failed readback must NOT escape into run() and kill the loop.
                logger.exception("Holding readback failed for device %s", self.device)
                self.polling_failed.emit(str(exc))
            else:
                self.holding_registers_updated.emit(holding_values)

    def _execute_write(self, command: RegisterWriteCommand) -> None:
        """Perform one hardware write, going through the device's encode path.

        device.write() runs encode() then write_raw(), both under bus_lock, so
        a GUI engineering value (e.g. a voltage) is converted to raw counts
        correctly. If your GUI hands you raw register words instead, replace
        this with: self.device.write_raw(command.register_name, [int(command.new_value)])
        """
        self.device.write(command.register_name, command.new_value)

    # ---- read path ------------------------------------------------------

    def _poll_device_once(self) -> None:
        """Poll input registers once and emit a timestamped snapshot."""
        try:
            t_elapsed = time.perf_counter() - self._t0
            input_values = self.device.get_all_input_registers()
        except Exception as exc:
            logger.exception("Polling failed for device %s", self.device)
            self.polling_failed.emit(str(exc))
            return

        self.input_registers_updated.emit(t_elapsed, input_values)

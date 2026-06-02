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
    new_value: int


class DevicePollingThread(QThread):
    """
    Polls one Modbus device in a background thread.

    Responsibilities:
    - periodically read input/holding register snapshots
    - emit fresh data to the GUI/controller
    - accept queued write commands from the GUI/controller
    - execute queued writes safely inside the polling loop
    - stop cleanly when requested
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

    def run(self) -> None:
        """
        Main thread loop.

        This method runs in the worker thread after calling .start().
        """

        logger.info(
            "Starting polling thread for device %s with refresh rate %d ms",
            self.device,
            self.refresh_rate_ms,
        )
        self._t0 = time.perf_counter()
        refresh_period_s = self.refresh_rate_ms / 1000.0

        try:
            while not self._stop_event.is_set():
                loop_start = time.monotonic()

                self._process_pending_writes()
                self._poll_device_once()

                elapsed = time.monotonic() - loop_start
                sleep_time = max(0.0, refresh_period_s - elapsed)

                if sleep_time > 0:
                    self._stop_event.wait(sleep_time)

        finally:
            logger.info("Polling thread stopped for device %s", self.device)
            self.stopped.emit()

    def stop(self) -> None:
        """
        Request clean thread shutdown.

        Call this from the GUI/controller before app closes.
        """

        self._stop_event.set()

    def update_refresh_rate(self, new_value_ms):
        self.refresh_rate_ms = new_value_ms

    def enqueue_write_command(
        self,
        register_id: int,
        register_name: str,
        new_value: int,
    ) -> None:
        """
        Queue a holding-register write.

        Safe to call from the GUI thread.
        """

        print("Registering command:", register_id, register_name, new_value)
        command = RegisterWriteCommand(
            register_id=register_id,
            register_name=register_name,
            new_value=new_value,
        )

        self._write_queue.put(command)

    def _process_pending_writes(self) -> None:
        """
        Execute all currently queued write commands.

        This runs inside the polling thread, so device access remains serialized.
        """

        while not self._write_queue.empty():
            try:
                command = self._write_queue.get_nowait()
            except queue.Empty:
                return

            try:
                self._execute_write(command)
            except Exception as exc:
                logger.exception(
                    "Write failed for register %s",
                    command.register_name,
                )
                msg = f"{command.register_name}: {str(exc)}"
                self.write_failed.emit(msg)
            else:
                msg = f"{command.register_name}: OK"
                self.write_succeeded.emit(msg)
            finally:
                self._write_queue.task_done()
            holding_values = self.device.get_all_holding_registers()
            self.holding_registers_updated.emit(holding_values)

    def _execute_write(self, command: RegisterWriteCommand) -> None:
        """
        Perform one hardware write.

        Adapt this method to your BaseModbusDevice API.
        """

        self.device.write_raw(  ## use setter or raw register write
            command.register_name,
            [command.new_value],
        )

    def _poll_device_once(self) -> None:
        """
        Poll device once and emit fresh data.

        """

        try:
            t_elapsed = time.perf_counter() - self._t0
            input_values = self.device.get_all_input_registers()

        except Exception as exc:
            logger.exception("Polling failed for device %s", self.device)
            self.polling_failed.emit(str(exc))
            return

        self.input_registers_updated.emit(t_elapsed, input_values)

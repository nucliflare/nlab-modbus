"""Log capture for the GUI: a bounded history plus a thread-safe signal per record."""

from __future__ import annotations

import collections
import logging
import time
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QStatusBar

from nlab_modbus.core.transport import FRAME_LOGGER


@dataclass(frozen=True)
class LogEntry:
    """One log record, kept structured so the debug console can filter it."""

    created: float
    level: int
    source: str
    message: str

    @property
    def level_name(self) -> str:
        return logging.getLevelName(self.level)

    def line(self) -> str:
        stamp = time.strftime("%H:%M:%S", time.localtime(self.created))
        millis = int(self.created % 1 * 1000)
        source = self.source.removeprefix("nlab_modbus.")
        return f"{stamp}.{millis:03d}  {self.level_name:<8} {source} — {self.message}"


class _LogBridge(QObject):
    """Records are emitted from any thread; Qt queues them to the GUI thread."""

    log_record = Signal(object)  # LogEntry


class QtLogHandler(logging.Handler):
    """Keeps the last MAX_RECORDS entries and forwards each new one to the GUI."""

    MAX_RECORDS = 5000

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.bridge = _LogBridge()
        self._entries: collections.deque[LogEntry] = collections.deque(maxlen=self.MAX_RECORDS)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
            if record.exc_info:
                message += "\n" + logging.Formatter().formatException(record.exc_info)
            entry = LogEntry(record.created, record.levelno, record.name, message)
            self._entries.append(entry)
            self.bridge.log_record.emit(entry)
        except Exception:
            self.handleError(record)

    def entries(self) -> list[LogEntry]:
        return list(self._entries)

    def get_full_log(self) -> str:
        return "\n".join(entry.line() for entry in self._entries)

    def clear(self) -> None:
        self._entries.clear()


class LogStatusBar(QStatusBar):
    """Shows the latest log line; double-click opens the debug console."""

    open_console_requested = Signal()

    def __init__(self, log_handler: QtLogHandler, parent=None) -> None:
        super().__init__(parent)
        self._log_handler = log_handler
        self._min_level = logging.INFO
        log_handler.bridge.log_record.connect(self._on_log_record)

    def set_debug_mode(self, enabled: bool) -> None:
        self._min_level = logging.DEBUG if enabled else logging.INFO

    def _on_log_record(self, entry: LogEntry) -> None:
        # Raw frames are far too frequent for the status bar; the console shows them.
        if entry.level >= self._min_level and not entry.source.startswith(FRAME_LOGGER):
            self.showMessage(entry.line())

    def mouseDoubleClickEvent(self, event) -> None:
        self.open_console_requested.emit()

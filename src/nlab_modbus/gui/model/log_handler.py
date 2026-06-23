from __future__ import annotations

import collections
import logging
from datetime import datetime

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
)


class _LogBridge(QObject):
    """Thread-safe bridge: logging handler emits here, GUI connects to the signal."""

    log_record = Signal(str, int)  # (formatted message, level)


class QtLogHandler(logging.Handler):
    """Logging handler that buffers records and feeds them to the GUI.

    Attach to the root ``nlab_modbus`` logger once at app startup.  Records are
    kept in a bounded deque so the full-log dialog has history even if the user
    opens it late.
    """

    MAX_RECORDS = 2000

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.bridge = _LogBridge()
        self._records: collections.deque[str] = collections.deque(maxlen=self.MAX_RECORDS)
        self.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s — %(message)s", datefmt="%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._records.append(msg)
            self.bridge.log_record.emit(msg, record.levelno)
        except Exception:
            self.handleError(record)

    def get_full_log(self) -> str:
        return "\n".join(self._records)

    def clear(self) -> None:
        self._records.clear()


class LogStatusBar(QStatusBar):
    """Status bar that shows the latest log line and opens a log dialog on double-click."""

    def __init__(self, log_handler: QtLogHandler, parent=None) -> None:
        super().__init__(parent)
        self._log_handler = log_handler
        self._debug_mode = False
        self._min_level = logging.INFO
        self._log_dialog: LogDialog | None = None
        self._connect()

    def _connect(self) -> None:
        self._log_handler.bridge.log_record.connect(self._on_log_record)

    def set_debug_mode(self, enabled: bool) -> None:
        self._debug_mode = enabled
        self._min_level = logging.DEBUG if enabled else logging.INFO

    def _on_log_record(self, message: str, level: int) -> None:
        if level >= self._min_level:
            self.showMessage(message)

    def mouseDoubleClickEvent(self, event) -> None:
        if self._log_dialog is not None and self._log_dialog.isVisible():
            self._log_dialog.raise_()
            self._log_dialog.activateWindow()
            return
        self._log_dialog = LogDialog(self._log_handler, debug_mode=self._debug_mode, parent=self.window())
        self._log_dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._log_dialog.destroyed.connect(lambda: setattr(self, "_log_dialog", None))
        self._log_dialog.show()


class LogDialog(QDialog):
    """Modal dialog showing the full buffered log."""

    def __init__(self, log_handler: QtLogHandler, debug_mode: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Application Log")
        self.resize(800, 500)

        self._log_handler = log_handler

        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = self._text.font()
        font.setFamily("Consolas")
        font.setPointSize(9)
        self._text.setFont(font)

        self._refresh_text(debug_mode)

        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(self._on_clear)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_clear)
        btn_layout.addWidget(btn_close)

        layout = QVBoxLayout(self)
        layout.addWidget(self._text)
        layout.addLayout(btn_layout)

        self._log_handler.bridge.log_record.connect(self._on_live_record)

    def _refresh_text(self, debug_mode: bool) -> None:
        full = self._log_handler.get_full_log()
        if not debug_mode:
            lines = [ln for ln in full.splitlines() if "DEBUG" not in ln]
            full = "\n".join(lines)
        self._text.setPlainText(full)
        self._text.verticalScrollBar().setValue(self._text.verticalScrollBar().maximum())

    def _on_live_record(self, message: str, level: int) -> None:
        self._text.appendPlainText(message)

    def _on_clear(self) -> None:
        self._log_handler.clear()
        self._text.clear()

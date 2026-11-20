"""Debug console: live application log in its own window.

Entries arrive through QtLogHandler's signal and are appended in batches every
100 ms, so a burst (for example raw Modbus frames) cannot stall the GUI. The
view keeps at most ``QtLogHandler.MAX_RECORDS`` lines; filters re-render from
the handler's history.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from nlab_modbus.core.transport import FRAME_LOGGER, frame_logging_enabled, set_frame_logging
from nlab_modbus.gui import theme
from nlab_modbus.gui.help import DEBUG_CONSOLE_HELP, apply_help
from nlab_modbus.gui.model.log_handler import LogEntry, QtLogHandler

FLUSH_MS = 100
LEVELS = (("Debug", logging.DEBUG), ("Info", logging.INFO), ("Warning", logging.WARNING), ("Error", logging.ERROR))
SOURCES = (
    ("All sources", ()),
    ("Connections and polling", ("nlab_modbus.services", "nlab_modbus.core", "nlab_modbus.devices")),
    ("Discovery", ("nlab_modbus.discovery",)),
    ("GUI", ("nlab_modbus.gui",)),
    ("Modbus frames", (FRAME_LOGGER,)),
)
_SETTINGS = "debug_console/"


class DebugConsole(QWidget):
    """Top-level window showing the application log, filterable and saveable."""

    def __init__(self, handler: QtLogHandler, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("Debug console")
        self.resize(980, 560)
        self._handler = handler
        self._pending: list[LogEntry] = []

        self.level_select = QComboBox()
        for label, level in LEVELS:
            self.level_select.addItem(label, level)
        self.source_select = QComboBox()
        for label, prefixes in SOURCES:
            self.source_select.addItem(label, prefixes)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter text")
        self.filter_edit.setClearButtonEnabled(True)
        self.frames_check = QCheckBox("Modbus frames")
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setCheckable(True)
        self.clear_btn = QPushButton("Clear")
        self.copy_btn = QPushButton("Copy")
        self.save_btn = QPushButton("Save…")
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.view.setMaximumBlockCount(QtLogHandler.MAX_RECORDS)
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono.setFamilies(["Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Menlo", "Courier New", mono.family()])
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.view.setFont(mono)
        self.status_label = QLabel()

        controls = QHBoxLayout()
        for widget in (QLabel("Level"), self.level_select, QLabel("Source"), self.source_select, self.filter_edit, self.frames_check):
            controls.addWidget(widget)
        controls.addStretch(1)
        for widget in (self.pause_btn, self.clear_btn, self.copy_btn, self.save_btn):
            controls.addWidget(widget)
        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.view, 1)
        layout.addWidget(self.status_label)
        apply_help(self, DEBUG_CONSOLE_HELP)

        self._formats = self._level_formats()
        self._restore_settings()
        self.level_select.currentIndexChanged.connect(self._filters_changed)
        self.source_select.currentIndexChanged.connect(self._filters_changed)
        self.filter_edit.textChanged.connect(self._filters_changed)
        self.frames_check.toggled.connect(self._frames_toggled)
        self.pause_btn.toggled.connect(self._pause_toggled)
        self.clear_btn.clicked.connect(self.clear)
        self.copy_btn.clicked.connect(self._copy)
        self.save_btn.clicked.connect(self._save)
        handler.bridge.log_record.connect(self._on_entry)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._flush)
        self._timer.start(FLUSH_MS)
        self._render_all()

    # ---- filtering -----------------------------------------------------------

    def matches(self, entry: LogEntry) -> bool:
        if entry.level < self.level_select.currentData():
            return False
        prefixes = self.source_select.currentData()
        if prefixes and not entry.source.startswith(tuple(prefixes)):
            return False
        text = self.filter_edit.text().strip().casefold()
        return not text or text in entry.line().casefold()

    def _filters_changed(self) -> None:
        self._save_settings()
        self._render_all()

    def _level_formats(self) -> dict[int, QTextCharFormat]:
        c = theme.colors()
        formats = {}
        for level, color in (
            (logging.DEBUG, c.console_debug), (logging.INFO, c.console_text),
            (logging.WARNING, c.console_warning), (logging.ERROR, c.console_error),
        ):
            text_format = QTextCharFormat()
            text_format.setForeground(QColor(color))
            formats[level] = text_format
        return formats

    def _format_for(self, level: int) -> QTextCharFormat:
        for threshold in (logging.ERROR, logging.WARNING, logging.INFO):
            if level >= threshold:
                return self._formats[threshold]
        return self._formats[logging.DEBUG]

    # ---- rendering -------------------------------------------------------------

    def _on_entry(self, entry: LogEntry) -> None:
        self._pending.append(entry)
        if len(self._pending) > QtLogHandler.MAX_RECORDS:
            del self._pending[: len(self._pending) - QtLogHandler.MAX_RECORDS]

    def _flush(self) -> None:
        if self.pause_btn.isChecked():
            self._update_status()
            return
        if self._pending:
            entries, self._pending = self._pending, []
            self._append([entry for entry in entries if self.matches(entry)])
        self._update_status()

    def _render_all(self) -> None:
        self._pending.clear()
        self.view.clear()
        self._append([entry for entry in self._handler.entries() if self.matches(entry)])
        self._update_status()

    def _append(self, entries: list[LogEntry]) -> None:
        if not entries:
            return
        scrollbar = self.view.verticalScrollBar()
        follow = scrollbar.value() >= scrollbar.maximum() - 2
        cursor = QTextCursor(self.view.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.beginEditBlock()
        for entry in entries:
            if not self.view.document().isEmpty():
                cursor.insertBlock()
            cursor.insertText(entry.line(), self._format_for(entry.level))
        cursor.endEditBlock()
        if follow:
            scrollbar.setValue(scrollbar.maximum())

    def _update_status(self) -> None:
        document = self.view.document()
        text = f"{0 if document.isEmpty() else document.blockCount()} lines shown"
        if self.pause_btn.isChecked() and self._pending:
            text += f" · paused, {len(self._pending)} new"
        if frame_logging_enabled():
            text += " · logging Modbus frames"
        self.status_label.setText(text)

    # ---- actions ---------------------------------------------------------------

    def _frames_toggled(self, enabled: bool) -> None:
        set_frame_logging(enabled)
        if enabled and self.level_select.currentData() > logging.DEBUG:
            self.level_select.setCurrentIndex(0)  # frames are logged at debug level
        self._save_settings()
        self._update_status()

    def _pause_toggled(self, paused: bool) -> None:
        self.pause_btn.setText("Resume" if paused else "Pause")
        if not paused:
            self._flush()

    def clear(self) -> None:
        """Forget the log history and empty the view."""
        self._handler.clear()
        self._render_all()

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self.view.toPlainText())

    def _save(self) -> None:
        default = f"nlab-modbus-{time.strftime('%Y%m%d-%H%M%S')}.log"
        path, _ = QFileDialog.getSaveFileName(self, "Save log", default, "Log files (*.log);;All files (*)")
        if path:
            Path(path).write_text(self.view.toPlainText() + "\n", encoding="utf-8")

    # ---- settings --------------------------------------------------------------

    def _restore_settings(self) -> None:
        settings = QSettings("EWT", "nlab-modbus-gui")
        level = settings.value(_SETTINGS + "level", logging.INFO, type=int)
        self.level_select.setCurrentIndex(max(0, self.level_select.findData(level)))
        self.source_select.setCurrentIndex(max(0, min(settings.value(_SETTINGS + "source", 0, type=int), len(SOURCES) - 1)))
        self.frames_check.setChecked(frame_logging_enabled())
        geometry = settings.value(_SETTINGS + "geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def _save_settings(self) -> None:
        settings = QSettings("EWT", "nlab-modbus-gui")
        settings.setValue(_SETTINGS + "level", self.level_select.currentData())
        settings.setValue(_SETTINGS + "source", self.source_select.currentIndex())

    def closeEvent(self, event) -> None:
        """Remember the geometry; frame logging stops with the window."""
        QSettings("EWT", "nlab-modbus-gui").setValue(_SETTINGS + "geometry", self.saveGeometry())
        self.frames_check.setChecked(False)
        super().closeEvent(event)

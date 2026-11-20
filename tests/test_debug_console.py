from __future__ import annotations

import logging
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QAbstractButton, QAbstractItemView, QApplication, QComboBox, QLineEdit, QPlainTextEdit  # noqa: E402

from nlab_modbus.core.transport import FRAME_LOGGER, frame_logging_enabled, serial_client  # noqa: E402
from nlab_modbus.gui import debug_console  # noqa: E402
from nlab_modbus.gui.debug_console import DebugConsole  # noqa: E402
from nlab_modbus.gui.model.log_handler import QtLogHandler  # noqa: E402


class DebugConsoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        settings = QSettings(str(Path(folder.name) / "s.ini"), QSettings.Format.IniFormat)
        patcher = patch.object(debug_console, "QSettings", return_value=settings)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.handler = QtLogHandler()
        self.logger = logging.getLogger("nlab_modbus.test_console")
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(self.handler)
        self.addCleanup(self.logger.removeHandler, self.handler)
        self.console = DebugConsole(self.handler)
        self.addCleanup(self.console.close)

    def _flush(self) -> list[str]:
        deadline = time.monotonic() + 0.3  # > two flush intervals
        while time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        text = self.console.view.toPlainText()
        return text.splitlines() if text else []

    def test_opens_as_its_own_window(self):
        self.assertTrue(self.console.isWindow())

    def test_new_entries_appear_with_level_and_source(self):
        self.logger.info("COM3 connected")
        self.logger.error("write failed")

        lines = self._flush()

        self.assertTrue(any("INFO" in line and "test_console — COM3 connected" in line for line in lines))
        self.assertTrue(any("ERROR" in line and "write failed" in line for line in lines))

    def test_level_and_text_filters_rerender_history(self):
        self.logger.debug("probe id 4")
        self.logger.info("COM3 connected")
        self.logger.warning("192.168.10.128 slow")
        self._flush()

        self.console.level_select.setCurrentIndex(2)  # Warning
        self.assertEqual(len(self._flush()), 1)
        self.console.level_select.setCurrentIndex(0)  # Debug
        self.console.filter_edit.setText("com3")
        self.assertEqual([("COM3" in line) for line in self._flush()], [True])

    def test_pause_holds_new_lines_until_resumed(self):
        self.console.pause_btn.setChecked(True)
        self.logger.info("while paused")
        self.assertEqual(self._flush(), [])
        self.assertIn("paused, 1 new", self.console.status_label.text())

        self.console.pause_btn.setChecked(False)
        self.assertTrue(any("while paused" in line for line in self._flush()))

    def test_clear_and_save(self):
        self.logger.info("keep me")
        self._flush()
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "out.log"
            with patch.object(debug_console.QFileDialog, "getSaveFileName", return_value=(str(target), "")):
                self.console.save_btn.click()
            self.assertIn("keep me", target.read_text(encoding="utf-8"))
        self.console.clear()
        self.assertEqual(self._flush(), [])
        self.assertEqual(self.handler.entries(), [])

    def test_modbus_frames_switch_logs_hex_frames_and_stops_on_close(self):
        logging.getLogger(FRAME_LOGGER).addHandler(self.handler)
        self.addCleanup(logging.getLogger(FRAME_LOGGER).removeHandler, self.handler)
        transaction = serial_client("COM_TEST", 9600).transaction
        trace, trace_pdu = transaction.trace_packet, transaction.trace_pdu
        request, reply = bytes.fromhex("010400000002 71CB"), bytes.fromhex("010404030100 03EA01")

        trace(True, request)  # off: nothing logged
        self.console.frames_check.setChecked(True)
        trace(True, request)
        for end in (2, 6, len(reply)):  # serial replies arrive as a growing buffer
            trace(False, reply[:end])
        trace_pdu(False, object())  # reply decoded
        trace(True, request)
        trace(False, reply[:3])  # timeout: partial reply, then the next request
        trace(True, request)

        lines = self._flush()
        self.assertEqual(len(lines), 5)
        self.assertIn("COM_TEST TX id 1 FC04  01 04 00 00 00 02 71 CB", lines[0])
        self.assertIn("COM_TEST RX", lines[1])
        self.assertTrue(lines[1].endswith(" 01 04 04 03 01 00 03 EA 01"))  # one line for the whole reply
        self.assertIn("RX incomplete 01 04 04", lines[3])
        self.console.close()
        self.assertFalse(frame_logging_enabled())

    def test_every_control_explains_itself_in_help_mode(self):
        interactive = (QAbstractButton, QComboBox, QLineEdit, QPlainTextEdit, QAbstractItemView)
        undocumented = [
            name for name, widget in vars(self.console).items()
            if isinstance(widget, interactive) and not widget.whatsThis()
        ]
        self.assertEqual(undocumented, [])



@patch("nlab_modbus.gui.controller.main_controller.scan_remote_boards", return_value=[])
@patch("nlab_modbus.gui.controller.main_controller.scan_local_modbus_devices", return_value=[])
class MainWindowEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_f12_and_status_bar_open_one_console_window(self, *_scans):
        from nlab_modbus.gui.controller.main_controller import ModbusMainWindow

        window = ModbusMainWindow(log_handler=QtLogHandler())
        window._closing = True  # no scans needed
        self.addCleanup(window.deleteLater)
        window.show()

        self.assertEqual(window.action_debug_console.shortcut().toString(), "F12")
        window.action_debug_console.trigger()
        console = window._debug_console
        self.assertTrue(console.isVisible() and console.isWindow())
        console.close()
        window._log_status_bar.open_console_requested.emit()  # double-click on the status bar
        self.assertIs(window._debug_console, console)
        self.assertTrue(console.isVisible())
        console.close()


if __name__ == "__main__":
    unittest.main()

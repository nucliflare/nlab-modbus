from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pyqtgraph as pg  # noqa: E402
from PySide6.QtCore import QEvent, QPoint, Qt  # noqa: E402
from PySide6.QtGui import QHelpEvent  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractButton,
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QLineEdit,
    QTabWidget,
    QWhatsThis,
    QWidget,
)

from nlab_modbus.gui.controller.main_controller import ModbusMainWindow  # noqa: E402
from nlab_modbus.gui.generated.ui_device_tab import Ui_DeviceTab  # noqa: E402
from nlab_modbus.gui.generated.ui_main_window import Ui_MainWindow  # noqa: E402
from nlab_modbus.gui.help import DEVICE_TAB_HELP, MAIN_WINDOW_HELP, apply_help  # noqa: E402
from nlab_modbus.gui.model.register_tables import HoldingRegisterTableModel, RegisterRow  # noqa: E402
from nlab_modbus.maps.sipm_map import SIPM_REGISTER_MAP  # noqa: E402

INTERACTIVE = (QAbstractButton, QComboBox, QAbstractSpinBox, QLineEdit, QAbstractItemView, QTabWidget, pg.GraphicsView)


def _popup_text() -> str | None:
    """Text of the visible What's This popup, if any."""
    for widget in QApplication.topLevelWidgets():
        if widget.metaObject().className() == "QWhatsThat" and widget.isVisible():
            return "shown"
    return None


class HelpTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _check_ui(self, ui_class, texts):
        host = QWidget()
        ui = ui_class()
        ui.setupUi(host)
        self.assertEqual(apply_help(ui, texts), [], "help keys without a matching widget")
        undocumented = [
            name
            for name, widget in vars(ui).items()
            if isinstance(widget, INTERACTIVE) and not widget.whatsThis()
        ]
        self.assertEqual(undocumented, [], "interactive widgets without help text")

    def test_every_main_window_element_has_help(self):
        self._check_ui(Ui_MainWindow, MAIN_WINDOW_HELP)

    def test_every_device_tab_element_has_help(self):
        self._check_ui(Ui_DeviceTab, DEVICE_TAB_HELP)

    def test_register_rows_and_columns_explain_themselves(self):
        model = HoldingRegisterTableModel([RegisterRow.from_spec("vout_set", SIPM_REGISTER_MAP["vout_set"], 4567)])
        row_help = model.data(model.index(0, model.COL_VALUE), Qt.ItemDataRole.WhatsThisRole)
        header_help = model.headerData(model.COL_UNIT, Qt.Orientation.Horizontal, Qt.ItemDataRole.WhatsThisRole)

        self.assertIn("vout_set", row_help)
        self.assertIn("Limits: 15 … 78 V", row_help)
        self.assertIn("Saved to EEPROM", row_help)
        self.assertIn("Unit", header_help)


@patch("nlab_modbus.gui.controller.main_controller.scan_remote_boards", return_value=[])
@patch("nlab_modbus.gui.controller.main_controller.scan_local_modbus_devices", return_value=[])
class HelpModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.addCleanup(QWhatsThis.leaveWhatsThisMode)
        self.addCleanup(QWhatsThis.hideText)

    def _window(self) -> ModbusMainWindow:
        window = ModbusMainWindow()
        window._closing = True  # no scans or I/O needed
        self.addCleanup(window.deleteLater)
        window.show()
        return window

    def test_f1_toggles_help_mode(self, *_scans):
        window = self._window()

        self.assertEqual(window.action_help_mode.shortcut().toString(), "F1")
        window.action_help_mode.trigger()
        self.assertTrue(QWhatsThis.inWhatsThisMode())
        window.action_help_mode.trigger()
        self.assertFalse(QWhatsThis.inWhatsThisMode())

    def test_help_request_on_a_widget_shows_its_explainer(self, *_scans):
        window = self._window()
        button = window.ui.scan_local_btn
        event = QHelpEvent(QEvent.Type.WhatsThis, QPoint(2, 2), button.mapToGlobal(QPoint(2, 2)))

        QApplication.sendEvent(button, event)

        self.assertIsNotNone(_popup_text())

    def test_help_request_on_a_register_row_shows_its_explainer(self, *_scans):
        from PySide6.QtWidgets import QTableView

        view = QTableView()
        self.addCleanup(view.deleteLater)
        view.setModel(HoldingRegisterTableModel([RegisterRow.from_spec("vout_set", SIPM_REGISTER_MAP["vout_set"], 4567)]))
        view.show()
        position = view.visualRect(view.model().index(0, 2)).center()
        event = QHelpEvent(QEvent.Type.WhatsThis, position, view.viewport().mapToGlobal(position))

        QApplication.sendEvent(view.viewport(), event)

        self.assertIsNotNone(_popup_text())


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QFile, QIODevice
from PySide6.QtGui import QAction, QIcon
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QWidget,
)
from serial.tools import list_ports

from nlab_modbus.core.enums import DeviceType
from nlab_modbus.discovery.scan import scan_local_modbus_devices, scan_remote_boards, scan_remote_modbus_devices

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_WINDOW_UI = PROJECT_ROOT / "view" / "main_window.ui"
APP_ICON = PROJECT_ROOT / "resources" / "ewt.ico"


class ModbusMainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.ui = self._load_ui(MAIN_WINDOW_UI)
        self.available_devices = {
            "local": {},
            "remote": {},
        }

        self._setup_window()
        self._setup_menu_bar()
        self._setup_status_bar()
        self._connect_signals()

    def _load_ui(self, ui_path: Path) -> Any:
        if not ui_path.exists():
            raise FileNotFoundError(f"UI file not found: {ui_path}")

        ui_file = QFile(str(ui_path))

        if not ui_file.open(QIODevice.OpenModeFlag.ReadOnly):
            raise RuntimeError(f"Could not open UI file: {ui_path}")

        try:
            loader = QUiLoader()
            ui = loader.load(ui_file, self)

            if ui is None:
                raise RuntimeError(f"Could not load UI file: {ui_path}")

            return ui

        finally:
            ui_file.close()

    def _setup_window(self) -> None:
        """
        Configure main window after loading the .ui file.
        """

        self.setWindowTitle("Modbus Monitor")
        # self.resize(1100, 750)
        self.setCentralWidget(self.ui)
        self.ui.devices_group.hide()

        if APP_ICON.exists():
            self.setWindowIcon(QIcon(str(APP_ICON)))
        else:
            raise FileNotFoundError(f"Application icon not found: {APP_ICON}")
        self.scan_local_ports()

    def _connect_signals(self) -> None:
        """
        Connect main window buttons, menu actions, etc.
        """
        self.action_about.triggered.connect(self.on_about_clicked)
        self.action_licenses.triggered.connect(self.on_licenses_clicked)
        self.action_scan_local_ports.triggered.connect(self.scan_local_ports)
        self.ui.port_select.currentIndexChanged.connect(self._update_comboboxes)
        self.ui.host_select.currentIndexChanged.connect(self._update_comboboxes)
        self.ui.remote_port_select.currentIndexChanged.connect(self._update_comboboxes)

    def on_connect_clicked(self) -> None:
        """
        Placeholder for local/remote Modbus connection logic.
        """
        pass

    def on_scan_clicked(self) -> None:
        """
        Placeholder for device discovery logic.
        """
        pass

    def add_device_tab(self, device: object) -> None:
        """
        Later this will:
        - load device_tab.ui
        - create a DeviceTabController
        - insert the tab into self.ui.tabs_widget
        """
        pass

    def _setup_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        connection_menu = menu_bar.addMenu("&Connection")
        view_menu = menu_bar.addMenu("&View")
        help_menu = menu_bar.addMenu("&Help")

        self.action_exit = QAction("E&xit", self)
        self.action_exit.setShortcut("Ctrl+Q")
        file_menu.addAction(self.action_exit)

        self.action_scan_local_ports = QAction("Scan for local ports")
        connection_menu.addAction(self.action_scan_local_ports)

        self.action_clear_plot = QAction("&Clear Plot", self)
        view_menu.addAction(self.action_clear_plot)

        self.action_about = QAction("&About", self)
        self.action_licenses = QAction("&Licenses", self)
        help_menu.addAction(self.action_about)
        help_menu.addAction(self.action_licenses)

    def _setup_status_bar(self) -> None:
        status_bar = QStatusBar(self)
        self.setStatusBar(status_bar)

        self.statusBar().showMessage("Ready")

    def scan_local_ports(self) -> None:
        """Scan for available local COM ports"""
        local_devices = scan_local_modbus_devices()
        self.ui.port_select.clear()

        for item in local_devices:
            port = item["port"]
            dev_id = item["device_id"]
            dev_name = item["type"].name
            if port not in self.available_devices["local"]:
                self.available_devices["local"][port] = []

            self.available_devices["local"][port].append(f"{dev_id} {dev_name}")

        local_ports = list(self.available_devices["local"].keys())
        self.ui.port_select.clear()
        self.ui.port_select.addItems(local_ports)

        self.ui.local_select.addItems(self.available_devices["local"][port])
        found_devices = {}
        ips = scan_remote_boards()
        for ip in ips:
            found_devices[ip] = {}
            for port in ["5001", "5002"]:
                found_devices[ip][port] = []
                remotes = scan_remote_modbus_devices(ip, int(port))
                for item in remotes:
                    dev_id = item["device_id"]
                    dev_name = item["type"].name
                    if remotes:
                        found_devices[ip][port].append(f"{dev_id} {dev_name}")
        self.ui.host_select.clear()
        self.ui.host_select.addItems(ips)

        self.available_devices["remote"] = found_devices
        self._update_comboboxes()

    def _update_comboboxes(self):
        local_port = self.ui.port_select.currentText()
        local_ids = self.available_devices["local"][local_port]
        self.ui.local_select.clear()
        self.ui.local_select.addItems(local_ids)

        remote_host = self.ui.host_select.currentText()
        remote_port = self.ui.remote_port_select.currentText()
        remote_ids = self.available_devices["remote"][remote_host][remote_port]
        self.ui.remote_select.clear()
        self.ui.remote_select.addItems(remote_ids)

    def on_about_clicked(self) -> None:
        QMessageBox.about(
            self,
            "About Modbus Monitor",
            ("<b>Modbus Monitor</b><br>Version 0.1.0<br><br>Eastern Wall Technologies<br><br>Hardware monitoring and Modbus control application."),
        )

    def on_licenses_clicked(self) -> None:
        QMessageBox.information(
            self,
            "Licenses",
            (
                "This application uses third-party open-source components, "
                "including PySide6 / Qt for Python, Qt, pyqtgraph, and pymodbus."
                "<br><br>"
                "See the bundled THIRD_PARTY_NOTICES or LICENSES file for details."
            ),
        )

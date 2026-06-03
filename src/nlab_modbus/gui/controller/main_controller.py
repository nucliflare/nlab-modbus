from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QWidget,
)

from nlab_modbus.core.base_modbus_device import BaseModbusDevice
from nlab_modbus.core.enums import DeviceType
from nlab_modbus.discovery.scan import scan_local_modbus_devices, scan_remote_boards, scan_remote_modbus_devices
from nlab_modbus.gui.controller.tab_controller import DeviceTab
from nlab_modbus.gui.generated.ui_main_window import Ui_MainWindow
from nlab_modbus.services.manager import DeviceManager

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ModbusMainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.central = QWidget(self)

        self.ui = Ui_MainWindow()

        self.ui.setupUi(self.central)
        self.setCentralWidget(self.central)

        self.available_devices = {
            "local": {},
            "remote": {},
        }
        self.manager = DeviceManager()
        self._open_devices: dict[BaseModbusDevice, DeviceTab] = {}
        self._setup_window()
        self._setup_menu_bar()
        self._setup_status_bar()
        self._connect_signals()

    def _setup_window(self) -> None:
        """
        Configure main window after loading the .ui file.
        """

        self.setWindowTitle("Modbus Monitor")
        # self.resize(1100, 750)
        # self.setCentralWidget(self.ui)
        self.ui.devices_group.hide()
        self.scan_for_available_devices()

    def _connect_signals(self) -> None:
        """
        Connect main window buttons, menu actions, etc.
        """
        self.action_about.triggered.connect(self.on_about_clicked)
        self.action_licenses.triggered.connect(self.on_licenses_clicked)
        self.action_scan_for_available_devices.triggered.connect(self.scan_for_available_devices)
        self.ui.port_select.currentIndexChanged.connect(self._update_comboboxes)
        self.ui.host_select.currentIndexChanged.connect(self._update_comboboxes)
        self.ui.remote_port_select.currentIndexChanged.connect(self._update_comboboxes)
        self.ui.local_btn.clicked.connect(self.on_connect_local_clicked)
        self.ui.remote_btn.clicked.connect(self.on_connect_remote_clicked)

    def on_connect_remote_clicked(self) -> None:
        host = self.ui.host_select.currentText()
        port = self.ui.remote_port_select.currentText()
        device_id, device_type = self.ui.remote_select.currentText().split()
        device = self.manager.connect_remote(host, int(port), int(device_id), DeviceType[device_type])
        self.add_device_tab(device)

    def on_connect_local_clicked(self) -> None:
        """
        Local Modbus connection handler.
        """
        port = self.ui.port_select.currentText()
        baudrate = int(self.ui.baudrate_select.currentText())
        stopbit = int(self.ui.stopbit_select.currentText())
        parity = self.ui.parity_select.currentText()[0]
        device_id, device_type = self.ui.local_select.currentText().split()
        device = self.manager.connect_local(port, int(device_id), DeviceType[device_type], baudrate, parity, stopbit)
        self.add_device_tab(device)

    def add_device_tab(self, device):
        if self.ui.devices_group.isHidden():
            self.ui.devices_group.show()

        if device not in self._open_devices:
            tab = DeviceTab(device, self)
            self.ui.devices_tab.addTab(tab, device.connection_info())
            self._open_devices[device] = tab
        else:
            self.ui.devices_tab.setCurrentWidget(self._open_devices[device])
            QMessageBox.information(self, "Device Already Connected", f"The device '{device.connection_info()}' is already connected.")

    def on_scan_clicked(self) -> None:
        """
        Placeholder for device discovery logic.
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

        self.action_scan_for_available_devices = QAction("Scan for available devices")
        connection_menu.addAction(self.action_scan_for_available_devices)

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

    def scan_for_available_devices(self) -> None:
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

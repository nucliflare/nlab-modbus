from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QWidget,
)

from nlab_modbus import __version__
from nlab_modbus.core.base_modbus_device import BaseModbusDevice
from nlab_modbus.core.enums import DeviceType
from nlab_modbus.discovery.scan import scan_local_modbus_devices, scan_remote_boards, scan_remote_modbus_devices
from nlab_modbus.gui.controller.tab_controller import DeviceTab
from nlab_modbus.gui.generated.ui_main_window import Ui_MainWindow
from nlab_modbus.services.manager import DeviceManager

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ModbusMainWindow(QMainWindow):
    """Main application window for the Modbus Monitor GUI.

    Hosts the connection panel (serial port / TCP dropdowns, connect buttons)
    and a QTabWidget where each connected device gets its own DeviceTab.
    Owns the DeviceManager so it can close all transports cleanly on exit.

    Device tabs are tracked in _open_devices so the same device cannot be
    opened twice; connecting an already-open device raises an info dialog and
    switches focus to the existing tab instead.
    """

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
        self.action_exit.triggered.connect(self.close)
        self.action_disconnect_tab.triggered.connect(self.on_disconnect_tab_clicked)
        self.action_disconnect_all.triggered.connect(self.on_disconnect_all_clicked)
        self.action_clear_plot.triggered.connect(self.on_clear_plot_clicked)
        self.ui.port_select.currentIndexChanged.connect(self._update_comboboxes)
        self.ui.host_select.currentIndexChanged.connect(self._update_comboboxes)
        self.ui.remote_port_select.currentIndexChanged.connect(self._update_comboboxes)
        self.ui.local_btn.clicked.connect(self.on_connect_local_clicked)
        self.ui.remote_btn.clicked.connect(self.on_connect_remote_clicked)

    def on_connect_remote_clicked(self) -> None:
        """Connect to the device selected in the remote (TCP) dropdowns."""
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
        """Open a DeviceTab for device, or bring the existing tab to front."""
        if self.ui.devices_group.isHidden():
            self.ui.devices_group.show()

        if device not in self._open_devices:
            tab = DeviceTab(device, self)
            self.ui.device_tabs.addTab(tab, device.connection_info())
            self._open_devices[device] = tab
        else:
            self.ui.device_tabs.setCurrentWidget(self._open_devices[device])
            QMessageBox.information(self, "Device Already Connected", f"The device '{device.connection_info()}' is already connected.")

    def _setup_menu_bar(self) -> None:
        """Build the File / Connection / View / Help menus and wire their actions."""
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        connection_menu = menu_bar.addMenu("&Connection")
        view_menu = menu_bar.addMenu("&View")
        help_menu = menu_bar.addMenu("&Help")

        self.action_exit = QAction("E&xit", self)
        self.action_exit.setShortcut("Ctrl+Q")
        file_menu.addAction(self.action_exit)

        self.action_scan_for_available_devices = QAction("&Scan for available devices", self)
        self.action_scan_for_available_devices.setShortcut("F5")
        self.action_disconnect_tab = QAction("&Disconnect current tab", self)
        self.action_disconnect_all = QAction("Disconnect &all", self)
        connection_menu.addAction(self.action_scan_for_available_devices)
        connection_menu.addSeparator()
        connection_menu.addAction(self.action_disconnect_tab)
        connection_menu.addAction(self.action_disconnect_all)

        self.action_clear_plot = QAction("&Clear Plot", self)
        view_menu.addAction(self.action_clear_plot)

        self.action_about = QAction("&About", self)
        self.action_licenses = QAction("&Licenses", self)
        help_menu.addAction(self.action_about)
        help_menu.addAction(self.action_licenses)

    def _setup_status_bar(self) -> None:
        """Create and attach the status bar, initially showing 'Ready'."""
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

        if local_ports:
            self.ui.local_select.addItems(self.available_devices["local"][local_ports[0]])
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
        """Refresh device-ID dropdowns to match the currently selected port / host."""
        local_port = self.ui.port_select.currentText()
        local_ids = self.available_devices["local"].get(local_port, [])
        self.ui.local_select.clear()
        self.ui.local_select.addItems(local_ids)

        remote_host = self.ui.host_select.currentText()
        remote_port = self.ui.remote_port_select.currentText()
        remote_ids = self.available_devices["remote"].get(remote_host, {}).get(remote_port, [])
        self.ui.remote_select.clear()
        self.ui.remote_select.addItems(remote_ids)

    def on_about_clicked(self) -> None:
        """Show the About dialog."""
        QMessageBox.about(
            self,
            "About Modbus Monitor",
            f"<b>Modbus Monitor</b><br>Version {__version__}<br><br>Eastern Wall Technologies<br><br>Hardware monitoring and Modbus control application.",
        )

    def on_licenses_clicked(self) -> None:
        """Show third-party licence information."""
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

    def _shutdown(self) -> None:
        """Stop all polling threads and close all Modbus clients."""
        for device_tab in self._open_devices.values():
            device_tab.close()
        self.manager.close_all()

    def closeEvent(self, event):
        self._shutdown()
        super().closeEvent(event)

    def on_disconnect_tab_clicked(self) -> None:
        """Close the currently visible device tab."""
        tab = self.ui.device_tabs.currentWidget()
        if isinstance(tab, DeviceTab):
            tab.close_tab()

    def on_disconnect_all_clicked(self) -> None:
        """Close every open device tab."""
        while self.ui.device_tabs.count():
            tab = self.ui.device_tabs.widget(0)
            if isinstance(tab, DeviceTab):
                tab.close_tab()

    def on_clear_plot_clicked(self) -> None:
        """Clear the plot buffers of the currently visible device tab."""
        tab = self.ui.device_tabs.currentWidget()
        if isinstance(tab, DeviceTab):
            tab.clear_buffers()

    def hide_tabs(self):
        """Collapse the devices group box and resize the window when all tabs are closed."""
        if self.ui.device_tabs.count() == 0:
            self.ui.devices_group.hide()
            QTimer.singleShot(0, self.adjustSize)

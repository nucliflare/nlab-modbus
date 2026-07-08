from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QWidget,
)

from nlab_modbus import __version__
from nlab_modbus.core.base_modbus_device import BaseModbusDevice
from nlab_modbus.core.enums import DeviceType
from nlab_modbus.discovery.scan import scan_local_modbus_devices, scan_remote_boards, scan_remote_modbus_devices
from nlab_modbus.gui.controller.tab_controller import DeviceTab
from nlab_modbus.gui.generated.ui_main_window import Ui_MainWindow
from nlab_modbus.gui.model.log_handler import LogStatusBar, QtLogHandler
from nlab_modbus.services.manager import DeviceManager

logger = logging.getLogger(__name__)

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

    def __init__(
        self,
        log_handler: QtLogHandler | None = None,
        initial_baudrate: int = 115200,
        scan_id_range: range = range(1, 17),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._log_handler = log_handler

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
        self._scan_id_range = scan_id_range
        self._apply_initial_baudrate(initial_baudrate)
        self._setup_window()
        self._setup_menu_bar()
        self._setup_status_bar()
        self._connect_signals()

    def _apply_initial_baudrate(self, baudrate: int) -> None:
        """Pre-select a baud rate in the combo before the first scan runs."""
        combo = self.ui.baudrate_select
        index = combo.findText(str(baudrate))
        if index >= 0:
            combo.setCurrentIndex(index)
        else:
            combo.insertItem(0, str(baudrate))
            combo.setCurrentIndex(0)
            logger.warning("Baud rate %d not in combo list — added dynamically", baudrate)

    def _setup_window(self) -> None:
        """
        Configure main window after loading the .ui file.
        """

        self.setWindowTitle("Nuclearlab - Modbus")
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
        self.action_debug_mode.triggered.connect(self._on_debug_mode_toggled)
        self.action_service_mode.triggered.connect(self.on_service_mode_toggled)
        self.ui.device_tabs.currentChanged.connect(self._on_tab_changed)
        self.ui.port_select.currentIndexChanged.connect(self._update_comboboxes)
        self.ui.host_select.currentIndexChanged.connect(self._update_comboboxes)
        self.ui.remote_port_select.currentIndexChanged.connect(self._update_comboboxes)
        self.ui.local_btn.clicked.connect(self.on_connect_local_clicked)
        self.ui.remote_btn.clicked.connect(self.on_connect_remote_clicked)
        self.ui.scan_local_btn.clicked.connect(self._scan_local_devices)
        self.ui.scan_remote_btn.clicked.connect(self._scan_remote_devices)
        self.ui.local_id_select.currentTextChanged.connect(self._auto_select_local_type)
        self.ui.remote_id_select.currentTextChanged.connect(self._auto_select_remote_type)
        self.ui.remote_port_select.currentTextChanged.connect(self._auto_select_remote_type)

    def on_connect_remote_clicked(self) -> None:
        """Connect to the device selected in the remote (TCP) dropdowns."""
        host = self.ui.host_select.currentText()
        port = self.ui.remote_port_select.currentText()
        device_id = int(self.ui.remote_id_select.currentText())
        device_type = self.ui.remote_type_select.currentText()
        try:
            device = self.manager.connect_remote(host, int(port), device_id, DeviceType[device_type])
        except Exception as exc:
            QMessageBox.critical(self, "Connection Failed", f"Could not connect to {host}:{port} id={device_id}:\n{exc}")
            return
        if not self._check_hardware_version(device, device_type):
            return
        self.add_device_tab(device)

    def on_connect_local_clicked(self) -> None:
        """Local Modbus connection handler."""
        port = self.ui.port_select.currentText()
        baudrate = int(self.ui.baudrate_select.currentText())
        device_id = int(self.ui.local_id_select.currentText())
        device_type = self.ui.local_type_select.currentText()
        try:
            device = self.manager.connect_local(port, device_id, DeviceType[device_type], baudrate, parity="N", stopbits=1)
        except Exception as exc:
            QMessageBox.critical(self, "Connection Failed", f"Could not connect to {port} id={device_id}:\n{exc}")
            return
        if not self._check_hardware_version(device, device_type):
            return
        self.add_device_tab(device)

    def _check_hardware_version(self, device, selected_type: str) -> bool:
        """Read hardware_version and confirm with the user on mismatch.

        Returns True if the tab should be opened, False if the user cancelled.
        """
        try:
            hw_version = device.read("hardware_version")
            expected = DeviceType[selected_type]
            if hw_version != expected.value:
                actual_name = next((t.name for t in DeviceType if t.value == hw_version), f"unknown (0x{hw_version:04X})")
                answer = QMessageBox.question(
                    self,
                    "Device Type Mismatch",
                    f"Selected type: {selected_type}\n"
                    f"Hardware reports: {actual_name} (version={hw_version})\n\n"
                    "The register map may not match the device.\n"
                    "Open tab anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                return answer == QMessageBox.StandardButton.Yes
        except Exception as exc:
            logger.warning("Could not verify hardware version: %s", exc)
        return True

    def add_device_tab(self, device):
        """Open a DeviceTab for device, or bring the existing tab to front."""
        if device in self._open_devices:
            self.ui.device_tabs.setCurrentWidget(self._open_devices[device])
            QMessageBox.information(self, "Device Already Connected", f"The device '{device.connection_info()}' is already connected.")
            return

        try:
            tab = DeviceTab(device, self)
        except Exception as exc:
            self.manager.disconnect(device)
            QMessageBox.critical(self, "Device Error", f"Failed to open device '{device.connection_info()}':\n{exc}")
            return

        self.ui.device_tabs.addTab(tab, device.connection_info())
        self._open_devices[device] = tab
        if self.ui.devices_group.isHidden():
            self.ui.devices_group.show()

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
        self.action_debug_mode = QAction("&Debug Mode", self)
        self.action_debug_mode.setCheckable(True)
        view_menu.addAction(self.action_clear_plot)
        view_menu.addAction(self.action_debug_mode)

        self.action_service_mode = QAction("&Service Mode", self)
        self.action_service_mode.setCheckable(True)
        connection_menu.addSeparator()
        connection_menu.addAction(self.action_service_mode)

        self.action_about = QAction("&About", self)
        self.action_licenses = QAction("&Licenses", self)
        help_menu.addAction(self.action_about)
        help_menu.addAction(self.action_licenses)

    def _setup_status_bar(self) -> None:
        """Replace the default status bar with a log-aware one.

        Double-click the status bar to open the full application log.
        """
        if self._log_handler is not None:
            self._log_status_bar = LogStatusBar(self._log_handler, self)
            self.setStatusBar(self._log_status_bar)
        self.statusBar().showMessage("Ready")

    def scan_for_available_devices(self) -> None:
        """Scan for both local and remote devices."""
        self._scan_local_devices()
        self._scan_remote_devices()

    def _scan_local_devices(self) -> None:
        """Scan local COM ports for Modbus devices at the selected baud rate."""
        baudrate = int(self.ui.baudrate_select.currentText())
        logger.info("=== Local scan started (baudrate=%d, id range=%d–%d) ===", baudrate, self._scan_id_range.start, self._scan_id_range.stop - 1)
        local_devices = scan_local_modbus_devices(device_ids=self._scan_id_range, baudrate=baudrate)
        self.available_devices["local"] = {}
        for item in local_devices:
            port = item["port"]
            dev_id = str(item["device_id"])
            if port not in self.available_devices["local"]:
                self.available_devices["local"][port] = {}
            self.available_devices["local"][port][dev_id] = item["type"].name

        local_ports = list(self.available_devices["local"].keys())
        self.ui.port_select.clear()
        self.ui.port_select.addItems(local_ports)
        self._update_comboboxes()
        logger.info("=== Local scan complete — ports: %s ===", local_ports)

    def _scan_remote_devices(self) -> None:
        """Scan for remote boards via mDNS and probe discovered IPs."""
        logger.info("=== Remote scan started (id range=%d–%d) ===", self._scan_id_range.start, self._scan_id_range.stop - 1)
        found_devices = {}
        ips = scan_remote_boards()
        for ip in ips:
            found_devices[ip] = {}
            for port in ["5001", "5002"]:
                found_devices[ip][port] = {}
                remotes = scan_remote_modbus_devices(ip, int(port))
                for item in remotes:
                    dev_id = str(item["device_id"])
                    found_devices[ip][port][dev_id] = item["type"].name
        self.ui.host_select.clear()
        self.ui.host_select.addItems(ips)
        self.available_devices["remote"] = found_devices
        self._update_comboboxes()
        logger.info("=== Remote scan complete — hosts: %s ===", list(found_devices.keys()))

    def _update_comboboxes(self):
        """Refresh device-ID dropdowns to match the currently selected port / host."""
        local_port = self.ui.port_select.currentText()
        local_ids = list(self.available_devices["local"].get(local_port, {}).keys())
        self.ui.local_id_select.clear()
        self.ui.local_id_select.addItems(local_ids)

        remote_host = self.ui.host_select.currentText()
        remote_port = self.ui.remote_port_select.currentText()
        remote_ids = list(self.available_devices["remote"].get(remote_host, {}).get(remote_port, {}).keys())
        self.ui.remote_id_select.clear()
        self.ui.remote_id_select.addItems(remote_ids)

        self._auto_select_local_type()
        self._auto_select_remote_type()

    def _auto_select_local_type(self) -> None:
        port = self.ui.port_select.currentText()
        dev_id = self.ui.local_id_select.currentText()
        device_type = self.available_devices["local"].get(port, {}).get(dev_id)
        if device_type:
            idx = self.ui.local_type_select.findText(device_type)
            if idx >= 0:
                self.ui.local_type_select.setCurrentIndex(idx)

    def _auto_select_remote_type(self) -> None:
        host = self.ui.host_select.currentText()
        port = self.ui.remote_port_select.currentText()
        dev_id = self.ui.remote_id_select.currentText()
        device_type = self.available_devices["remote"].get(host, {}).get(port, {}).get(dev_id)
        if device_type:
            idx = self.ui.remote_type_select.findText(device_type)
            if idx >= 0:
                self.ui.remote_type_select.setCurrentIndex(idx)

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

    def _on_debug_mode_toggled(self, checked: bool) -> None:
        if hasattr(self, "_log_status_bar"):
            self._log_status_bar.set_debug_mode(checked)

    def on_service_mode_toggled(self, checked: bool) -> None:
        tab = self.ui.device_tabs.currentWidget()
        if not isinstance(tab, DeviceTab):
            self.action_service_mode.setChecked(False)
            return
        if checked:
            password, ok = QInputDialog.getInt(
                self,
                "Service Password",
                "Enter the service password:",
                0,
                -32767,
                32767,
            )
            if ok:
                try:
                    tab.device.write("pass_static", password)
                    tab.holding_model.update_value(tab.device.get_register_address("pass_static"), password)
                    tab.set_service_mode(True)
                except Exception as exc:
                    logger.error("Password write failed: %s", exc)
                    self.action_service_mode.setChecked(False)
            else:
                self.action_service_mode.setChecked(False)
        else:
            tab.set_service_mode(False)

    def _on_tab_changed(self, index: int) -> None:
        tab = self.ui.device_tabs.widget(index)
        if isinstance(tab, DeviceTab):
            self.action_service_mode.setChecked(tab.service_mode)
        else:
            self.action_service_mode.setChecked(False)

    def update_service_mode_action(self) -> None:
        tab = self.ui.device_tabs.currentWidget()
        if isinstance(tab, DeviceTab):
            self.action_service_mode.setChecked(tab.service_mode)

    def hide_tabs(self):
        """Collapse the devices group box and resize the window when all tabs are closed."""
        if self.ui.device_tabs.count() == 0:
            self.ui.devices_group.hide()
            QTimer.singleShot(0, self.adjustSize)

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QSettings, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QWidget,
)
from pymodbus.client import ModbusSerialClient, ModbusTcpClient

from nlab_modbus import __version__
from nlab_modbus.core.base_modbus_device import BaseModbusDevice
from nlab_modbus.core.enums import DeviceType
from nlab_modbus.discovery.scan import scan_local_modbus_devices, scan_remote_boards, scan_remote_modbus_devices
from nlab_modbus.gui.controller.io_worker import DeviceIoThread
from nlab_modbus.gui.controller.scan_worker import DeviceScanThread
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

    initial_scan_finished = Signal()

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

        self.available_devices: dict[str, dict] = {
            "local": {},
            "remote": {},
        }
        self.manager = DeviceManager()
        self._open_devices: dict[BaseModbusDevice, DeviceTab] = {}
        self._scan_threads: dict[str, DeviceScanThread] = {}
        self._io_threads: set[DeviceIoThread] = set()
        self._connections_in_progress: set[str] = set()
        self._initial_scan_pending = True
        self._closing = False
        self._scan_id_range = scan_id_range
        self._apply_initial_baudrate(initial_baudrate)
        self._setup_window()
        self._setup_menu_bar()
        self._setup_status_bar()
        self._connect_signals()
        self._restore_settings()
        QTimer.singleShot(0, self.scan_for_available_devices)

    def _apply_initial_baudrate(self, baudrate: int) -> None:
        """Set the initial baud rate on the spinbox before the first scan runs."""
        self.ui.baudrate_select.setValue(baudrate)

    def _setup_window(self) -> None:
        """
        Configure main window after loading the .ui file.
        """

        self.setWindowTitle("Nuclearlab - Modbus")
        # self.resize(1100, 750)
        # self.setCentralWidget(self.ui)
        self.ui.devices_group.hide()

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
        host = self.ui.host_select.currentText().strip()
        if not host:
            QMessageBox.warning(self, "Invalid Connection", "Enter a remote host name or IP address.")
            return
        port = self._validated_integer(self.ui.remote_port_select.currentText(), "TCP port", 1, 65535)
        device_id = self._validated_integer(self.ui.remote_id_select.currentText(), "Modbus address", 1, 254)
        if port is None or device_id is None:
            return
        existing = self.manager.find_device(("tcp", host, port), device_id)
        if existing in self._open_devices:
            self.add_device_tab(existing)
            return
        selected_type = self.ui.remote_type_select.currentText()
        self._begin_connection(
            "remote",
            selected_type,
            lambda: self.manager.connect_remote(
                host,
                port,
                device_id,
                DeviceType[selected_type],
            ),
        )

    def on_connect_local_clicked(self) -> None:
        """Local Modbus connection handler."""
        port = self.ui.port_select.currentText().strip()
        if not port:
            QMessageBox.warning(self, "Invalid Connection", "Select or enter a serial port.")
            return
        baudrate = self.ui.baudrate_select.value()
        device_id = self._validated_integer(self.ui.local_id_select.currentText(), "Modbus address", 1, 254)
        if device_id is None:
            return
        existing = self.manager.find_device(("serial", port), device_id)
        if existing in self._open_devices:
            self.add_device_tab(existing)
            return
        selected_type = self.ui.local_type_select.currentText()
        self._begin_connection(
            "local",
            selected_type,
            lambda: self.manager.connect_local(
                port,
                device_id,
                DeviceType[selected_type],
                baudrate,
                parity="N",
                stopbits=1,
            ),
        )

    def _begin_connection(self, kind: str, selected_type: str, connect) -> None:
        """Connect and probe identity without performing I/O on the GUI thread."""
        if kind in self._scan_threads:
            logger.info("Cannot connect a %s device while its scan is running", kind)
            return
        if kind in self._connections_in_progress:
            logger.info("A %s connection is already in progress", kind)
            return

        self._connections_in_progress.add(kind)
        self._refresh_connection_controls()
        self.statusBar().showMessage(f"Connecting to {kind} device…")

        def probe(stop_requested):
            device = None
            try:
                device = connect()
                if stop_requested():
                    self.manager.disconnect(device)
                    return None
                hardware_version = device.read("hardware_version")
                firmware_version = device.read("firmware_version")
                if stop_requested():
                    self.manager.disconnect(device)
                    return None
                return {
                    "device": device,
                    "selected_type": selected_type,
                    "hardware_version": hardware_version,
                    "firmware_version": firmware_version,
                }
            except Exception:
                if device is not None:
                    self.manager.disconnect(device)
                raise

        self._start_io_operation(kind, "probe", probe)

    def _validated_integer(
        self,
        text: str,
        label: str,
        minimum: int,
        maximum: int,
    ) -> int | None:
        """Parse a user-entered numeric connection field with a clear error."""
        try:
            value = int(text.strip())
        except (AttributeError, ValueError):
            QMessageBox.warning(self, "Invalid Connection", f"{label} must be an integer.")
            return None
        if not minimum <= value <= maximum:
            QMessageBox.warning(
                self,
                "Invalid Connection",
                f"{label} must be between {minimum} and {maximum}.",
            )
            return None
        return value

    def _confirm_hardware_version(self, result: dict) -> bool:
        """Confirm a worker-probed device identity without touching the wire."""
        device = result["device"]
        selected_type = result["selected_type"]
        hw_raw = result["hardware_version"]
        fw_raw = result["firmware_version"]
        hw_type = (hw_raw >> 8) & 0xFF
        hw_rev = hw_raw & 0xFF
        fw_major = (fw_raw >> 8) & 0xFF
        fw_minor = fw_raw & 0xFF

        logger.info(
            "%s hardware rev=%d  firmware=%d.%d",
            device.connection_info(),
            hw_rev,
            fw_major,
            fw_minor,
        )
        expected = DeviceType[selected_type]
        if hw_type == expected.value:
            return True

        actual_name = next(
            (item.name for item in DeviceType if item.value == hw_type),
            f"unknown (type=0x{hw_type:02X})",
        )
        answer = QMessageBox.question(
            self,
            "Device Type Mismatch",
            f"Selected type: {selected_type}\n"
            f"Hardware reports: {actual_name} (rev={hw_rev}, fw={fw_major}.{fw_minor})\n\n"
            "The register map may not match the device.\n"
            "Open tab anyway?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _start_io_operation(self, kind: str, stage: str, operation) -> None:
        worker = DeviceIoThread(kind, stage, operation, self)
        worker.result_ready.connect(self._on_io_result)
        worker.operation_failed.connect(self._on_io_failed)
        worker.finished.connect(lambda: self._on_io_finished(worker))
        self._io_threads.add(worker)
        worker.start()

    def _on_io_result(self, kind: str, stage: str, result: object) -> None:
        if self._closing:
            return
        io_result = cast(dict[str, Any], result)
        device = io_result["device"]

        if stage == "probe":
            if not self._confirm_hardware_version(io_result):
                self.manager.disconnect(device)
                self._finish_connection(kind)
                return

            self.statusBar().showMessage(f"Loading {kind} device registers…")

            def initialise(stop_requested):
                try:
                    input_values = device.get_all_input_registers(raw=True)
                    if stop_requested():
                        self.manager.disconnect(device)
                        return None
                    holding_values = device.get_all_holding_registers(raw=True)
                    if stop_requested():
                        self.manager.disconnect(device)
                        return None
                    return {
                        "device": device,
                        "input_values": input_values,
                        "holding_values": holding_values,
                    }
                except Exception:
                    self.manager.disconnect(device)
                    raise

            self._start_io_operation(kind, "initialization", initialise)
            return

        self.add_device_tab(
            device,
            input_values=cast(dict[str, int], io_result["input_values"]),
            holding_values=cast(dict[str, int], io_result["holding_values"]),
        )
        self._finish_connection(kind)

    def _on_io_failed(self, kind: str, stage: str, error: str) -> None:
        if self._closing:
            return
        QMessageBox.critical(
            self,
            "Connection Failed",
            f"The {kind} device {stage} failed:\n{error}",
        )
        self._finish_connection(kind)

    def _on_io_finished(self, worker: DeviceIoThread) -> None:
        self._io_threads.discard(worker)
        worker.deleteLater()
        if not self._scan_threads and not self._io_threads and not self._connections_in_progress and not self._closing:
            self.statusBar().showMessage("Ready")

    def _finish_connection(self, kind: str) -> None:
        self._connections_in_progress.discard(kind)
        self._refresh_connection_controls()

    def add_device_tab(
        self,
        device,
        *,
        input_values: dict | None = None,
        holding_values: dict | None = None,
    ):
        """Open a DeviceTab for device, or bring the existing tab to front."""
        if device in self._open_devices:
            self.ui.device_tabs.setCurrentWidget(self._open_devices[device])
            QMessageBox.information(self, "Device Already Connected", f"The device '{device.connection_info()}' is already connected.")
            return

        if input_values is None or holding_values is None:
            raise ValueError("Initial register snapshots are required for a new device tab")

        try:
            tab = DeviceTab(
                device,
                self,
                input_values=input_values,
                holding_values=holding_values,
            )
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
        """Start independent local and remote scans in background threads."""
        if self._closing:
            return
        self._scan_local_devices()
        self._scan_remote_devices()

    def _scan_local_devices(self) -> None:
        """Scan unused local COM ports without blocking the GUI."""
        if self._closing:
            return
        if "local" in self._connections_in_progress:
            logger.info("Cannot scan local devices while a connection is in progress")
            return
        if "local" in self._scan_threads:
            logger.info("Local scan is already running")
            return

        baudrate = self.ui.baudrate_select.value()
        logger.info("=== Local scan started (baudrate=%d, id range=%d–%d) ===", baudrate, self._scan_id_range.start, self._scan_id_range.stop - 1)
        active = self.manager.discovery_snapshot()["local"]
        in_use_ports = {item["port"] for item in active}
        preserved = list(active)
        for port in in_use_ports:
            for device_id, type_name in self.available_devices["local"].get(port, {}).items():
                preserved.append(
                    {
                        "type": DeviceType[type_name],
                        "device_id": int(device_id),
                        "host": None,
                        "port": port,
                    }
                )

        def scan(stop_requested):
            discovered = scan_local_modbus_devices(
                device_ids=self._scan_id_range,
                baudrate=baudrate,
                exclude_ports=in_use_ports,
                should_stop=stop_requested,
            )
            return {
                "devices": [*preserved, *discovered],
                "skipped_ports": in_use_ports,
            }

        self._start_scan("local", scan)

    def _scan_remote_devices(self) -> None:
        """Discover remote boards and probe their RTU-over-TCP endpoints."""
        if self._closing:
            return
        if "remote" in self._connections_in_progress:
            logger.info("Cannot scan remote devices while a connection is in progress")
            return
        if "remote" in self._scan_threads:
            logger.info("Remote scan is already running")
            return

        logger.info("=== Remote scan started (id range=%d–%d) ===", self._scan_id_range.start, self._scan_id_range.stop - 1)
        active = self.manager.discovery_snapshot()["remote"]
        in_use_endpoints = {(item["host"], int(item["port"])) for item in active}
        preserved = list(active)
        for host, port in in_use_endpoints:
            known_ids = self.available_devices["remote"].get(host, {}).get(str(port), {})
            for device_id, type_name in known_ids.items():
                preserved.append(
                    {
                        "type": DeviceType[type_name],
                        "device_id": int(device_id),
                        "host": host,
                        "port": port,
                    }
                )

        def scan(stop_requested):
            hosts = scan_remote_boards(should_stop=stop_requested)
            devices = list(preserved)
            for host in hosts:
                for port in (5001, 5002):
                    if stop_requested():
                        return {
                            "hosts": hosts,
                            "devices": devices,
                            "skipped_endpoints": in_use_endpoints,
                        }
                    if (host, port) in in_use_endpoints:
                        continue
                    devices.extend(
                        scan_remote_modbus_devices(
                            host,
                            port,
                            candidate_ids=self._scan_id_range,
                            should_stop=stop_requested,
                        )
                    )
            return {
                "hosts": hosts,
                "devices": devices,
                "skipped_endpoints": in_use_endpoints,
            }

        self._start_scan("remote", scan)

    def _start_scan(self, kind: str, scan) -> None:
        worker = DeviceScanThread(kind, scan, self)
        worker.result_ready.connect(self._on_scan_result)
        worker.scan_failed.connect(self._on_scan_failed)
        worker.finished.connect(lambda: self._on_scan_finished(kind, worker))
        self._scan_threads[kind] = worker
        self._set_scan_running(kind, True)
        worker.start()

    def _set_scan_running(self, kind: str, running: bool) -> None:
        self._refresh_connection_controls()
        if running:
            self.statusBar().showMessage(f"Scanning {kind} devices…")

    def _refresh_connection_controls(self) -> None:
        local_busy = (
            "local" in self._scan_threads
            or "local" in self._connections_in_progress
        )
        remote_busy = (
            "remote" in self._scan_threads
            or "remote" in self._connections_in_progress
        )
        self.ui.scan_local_btn.setEnabled(not local_busy)
        self.ui.local_btn.setEnabled(not local_busy)
        self.ui.scan_remote_btn.setEnabled(not remote_busy)
        self.ui.remote_btn.setEnabled(not remote_busy)
        self.action_scan_for_available_devices.setEnabled(
            not self._scan_threads and not self._connections_in_progress
        )

    def _on_scan_result(self, kind: str, result: object) -> None:
        if self._closing:
            return
        if kind == "local":
            scan_result = cast(dict[str, Any], result)
            current_active_ports = {
                item["port"] for item in self.manager.discovery_snapshot()["local"]
            }
            local_devices: dict[str, dict[str, str]] = {}
            for item in scan_result["devices"]:
                port = item["port"]
                if port in scan_result["skipped_ports"] and port not in current_active_ports:
                    continue
                local_devices.setdefault(port, {})[str(item["device_id"])] = item["type"].name
            self.available_devices["local"] = local_devices
            ports = sorted(local_devices)
            self._replace_combo_items(self.ui.port_select, ports)
            logger.info("=== Local scan complete — ports: %s ===", ports)
        else:
            scan_result = cast(dict[str, Any], result)
            current_active_endpoints = {
                (item["host"], int(item["port"]))
                for item in self.manager.discovery_snapshot()["remote"]
            }
            current_active_hosts = {host for host, _port in current_active_endpoints}
            remote_devices: dict[str, dict[str, dict[str, str]]] = {
                host: {} for host in set(scan_result["hosts"]) | current_active_hosts
            }
            for item in scan_result["devices"]:
                host = item["host"]
                port = str(item["port"])
                endpoint = (host, int(item["port"]))
                if (
                    endpoint in scan_result["skipped_endpoints"]
                    and endpoint not in current_active_endpoints
                ):
                    continue
                remote_devices.setdefault(host, {}).setdefault(port, {})[
                    str(item["device_id"])
                ] = item["type"].name
            self.available_devices["remote"] = remote_devices
            hosts = sorted(remote_devices)
            self._replace_combo_items(self.ui.host_select, hosts)
            logger.info("=== Remote scan complete — hosts: %s ===", hosts)
        self._update_comboboxes()

    def _on_scan_failed(self, kind: str, error: str) -> None:
        if self._closing:
            return
        if self._initial_scan_pending:
            logger.error("Initial %s device scan failed: %s", kind, error)
            return
        QMessageBox.warning(self, "Scan Failed", f"The {kind} device scan failed:\n{error}")

    def _on_scan_finished(self, kind: str, worker: DeviceScanThread) -> None:
        if self._scan_threads.get(kind) is worker:
            self._scan_threads.pop(kind, None)
        self._set_scan_running(kind, False)
        worker.deleteLater()
        if not self._scan_threads and not self._closing:
            if self._initial_scan_pending:
                self._initial_scan_pending = False
                self.initial_scan_finished.emit()
            if not self._io_threads and not self._connections_in_progress:
                self.statusBar().showMessage("Ready")

    @staticmethod
    def _replace_combo_items(combo, items: list[str]) -> None:
        """Replace discovered choices while retaining editable manual input."""
        current_text = combo.currentText()
        previous_block_state = combo.blockSignals(True)
        combo.clear()
        combo.addItems(items)
        match = combo.findText(current_text)
        if match >= 0:
            combo.setCurrentIndex(match)
        elif combo.isEditable() and current_text:
            combo.setEditText(current_text)
        combo.blockSignals(previous_block_state)

    def _update_comboboxes(self):
        """Refresh device-ID dropdowns to match the currently selected port / host."""
        local_port = self.ui.port_select.currentText()
        local_ids = sorted(
            self.available_devices["local"].get(local_port, {}).keys(),
            key=int,
        )
        self._replace_combo_items(self.ui.local_id_select, local_ids)

        remote_host = self.ui.host_select.currentText()
        remote_port = self.ui.remote_port_select.currentText()
        remote_ids = sorted(
            self.available_devices["remote"].get(remote_host, {}).get(remote_port, {}).keys(),
            key=int,
        )
        self._replace_combo_items(self.ui.remote_id_select, remote_ids)

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

    def forget_available_device(self, device: BaseModbusDevice) -> None:
        """Remove a non-responsive device from the discovery choices."""
        device_id = str(device.device_id)
        if isinstance(device.client, ModbusSerialClient):
            port = str(device.client.comm_params.host)
            devices = self.available_devices["local"].get(port)
            if devices is not None:
                devices.pop(device_id, None)
                if not devices:
                    self.available_devices["local"].pop(port, None)
                    if self.ui.port_select.currentText() == port:
                        self.ui.port_select.setEditText("")
            self._replace_combo_items(
                self.ui.port_select,
                sorted(self.available_devices["local"]),
            )
        elif isinstance(device.client, ModbusTcpClient):
            host = str(device.client.comm_params.host)
            port = str(device.client.comm_params.port)
            endpoints = self.available_devices["remote"].get(host)
            if endpoints is not None:
                devices = endpoints.get(port)
                if devices is not None:
                    devices.pop(device_id, None)
                    if not devices:
                        endpoints.pop(port, None)
                if not endpoints:
                    self.available_devices["remote"].pop(host, None)
                    if self.ui.host_select.currentText() == host:
                        self.ui.host_select.setEditText("")
            self._replace_combo_items(
                self.ui.host_select,
                sorted(self.available_devices["remote"]),
            )
        self._update_comboboxes()

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
        """Cancel discovery, stop polling, and then close all transports."""
        if self._closing:
            return
        self._closing = True
        background_threads = [*self._scan_threads.values(), *self._io_threads]
        for worker in background_threads:
            worker.requestInterruption()
        for worker in background_threads:
            worker.wait()

        for device_tab in list(self._open_devices.values()):
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

    def _restore_settings(self) -> None:
        settings = QSettings("EWT", "nlab-modbus-gui")
        debug = settings.value("view/debug_mode", False, type=bool)
        self.action_debug_mode.setChecked(debug)
        if hasattr(self, "_log_status_bar"):
            self._log_status_bar.set_debug_mode(debug)

    def _on_debug_mode_toggled(self, checked: bool) -> None:
        if hasattr(self, "_log_status_bar"):
            self._log_status_bar.set_debug_mode(checked)
        QSettings("EWT", "nlab-modbus-gui").setValue("view/debug_mode", checked)

    def on_service_mode_toggled(self, checked: bool) -> None:
        tab = self.ui.device_tabs.currentWidget()
        if not isinstance(tab, DeviceTab):
            self.action_service_mode.setChecked(False)
            return
        if checked:
            tab.request_service_mode()
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

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QTimer, Slot
from PySide6.QtWidgets import QHeaderView, QInputDialog, QMessageBox, QWidget

from nlab_modbus.core.base_modbus_device import BaseModbusDevice
from nlab_modbus.core.transport import GATEWAY_BAUDRATE
from nlab_modbus.gui.generated.ui_device_tab import Ui_DeviceTab
from nlab_modbus.gui.help import DEVICE_TAB_HELP, apply_help
from nlab_modbus.gui.model.register_tables import (
    HoldingRegisterTableModel,
    InputRegisterTableModel,
    ProtectedRowDelegate,
    RegisterRow,
)
from nlab_modbus.gui.model.ring_buffer import NumpyRingBuffer
from nlab_modbus.services.polling_worker import TRANSPORT_REGISTERS, DevicePollingThread

if TYPE_CHECKING:
    from nlab_modbus.gui.controller.main_controller import ModbusMainWindow

logger = logging.getLogger(__name__)

HISTORY = 1000  # samples kept per plotted register
PLOT_REFRESH_MS = 100  # redraw at most 10x per second, and only while visible
# Colour-blind safe palette (Okabe-Ito), cycled for plotted registers.
PALETTE = ("#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#000000", "#F0E442")


class DeviceTab(QWidget):
    """One connected device: holding/input tables, live plot and its polling thread.

    All bus I/O runs on the DevicePollingThread; this widget only renders
    snapshots and queues writes.
    """

    def __init__(
        self,
        device: BaseModbusDevice,
        parent: ModbusMainWindow,
        *,
        input_values: dict[str, int],
        holding_values: dict[str, int],
    ) -> None:
        super().__init__(parent)
        if device.device_type is None:
            raise ValueError("Cannot open a tab for a device without a device type")
        self.device = device
        self.main_widget = parent
        self._closing = False
        self._plot_dirty = False
        self.ui = Ui_DeviceTab()
        self.ui.setupUi(self)
        apply_help(self.ui, DEVICE_TAB_HELP)
        self.ui.type_edit.setText(device.device_type.name)

        self.time_buffer = NumpyRingBuffer(HISTORY)
        self.input_register_buffer = {name: NumpyRingBuffer(HISTORY) for name in input_values}
        self.plot_items: dict[str, pg.PlotDataItem] = {}

        specs = device.REGISTER_MAP
        self.input_model = InputRegisterTableModel(
            [RegisterRow.from_spec(name, specs[name], value) for name, value in input_values.items()]
        )
        self.holding_model = HoldingRegisterTableModel(
            [RegisterRow.from_spec(name, specs[name], value) for name, value in holding_values.items()]
        )
        for model in (self.input_model, self.holding_model):
            model.set_display_raw(parent.show_raw_values)

        self._setup_register_tables()
        self._setup_plot()
        self._connect_signals()
        self._plot_timer = QTimer(self)
        self._plot_timer.timeout.connect(self._refresh_plot)
        self._plot_timer.start(PLOT_REFRESH_MS)
        self._run_worker()

    # ---- setup -------------------------------------------------------------

    def _setup_register_tables(self) -> None:
        self.ui.holding_table_view.setModel(self.holding_model)
        self.ui.holding_table_view.setItemDelegate(ProtectedRowDelegate(self.ui.holding_table_view))
        self.ui.input_table_view.setModel(self.input_model)
        for table in (self.ui.holding_table_view, self.ui.input_table_view):
            table.setAlternatingRowColors(True)
            table.verticalHeader().setVisible(False)

        fit, drag = QHeaderView.ResizeMode.ResizeToContents, QHeaderView.ResizeMode.Interactive
        for table, modes in (
            (self.ui.holding_table_view, (fit, drag, drag, fit)),
            (self.ui.input_table_view, (fit, drag, drag, fit, fit)),
        ):
            header = table.horizontalHeader()
            for column, mode in enumerate(modes):
                header.setSectionResizeMode(column, mode)
            header.resizeSection(1, 180)
            header.resizeSection(2, 80)
            header.setStretchLastSection(table is self.ui.holding_table_view)

    def _setup_plot(self) -> None:
        """Plot tuned for redraw cost: clipped, peak-downsampled curves and plain axes."""
        layout = pg.GraphicsLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        self.ui.input_plot.setCentralItem(layout)
        self.ui.input_plot.setBackground("#ffffff")
        layout.addLabel("Input registers", angle=-90)
        self.main_plot = layout.addPlot()
        self.main_plot.showGrid(x=True, y=True, alpha=0.2)
        self.main_plot.setClipToView(True)
        self.main_plot.setDownsampling(auto=True, mode="peak")
        self.main_plot.addLegend(offset=(10, 10))
        self.main_plot.getViewBox().setBorder(pg.mkPen("#808080"))
        layout.nextRow()
        layout.addLabel("Time [s]", col=1)

    def _connect_signals(self) -> None:
        self.holding_model.write_requested.connect(self.holding_write_requested)
        self.holding_model.edit_rejected.connect(
            lambda name, reason: logger.warning("%s: %s not written: %s", self.label, name, reason)
        )
        self.input_model.plot_enabled_changed.connect(self.plot_enabled_changed)
        self.ui.tab_disconnect_btn.clicked.connect(self.close_tab)
        self.ui.clear_plot_btn.clicked.connect(self.clear_buffers)

    def _run_worker(self) -> None:
        self.polling_thread = DevicePollingThread(
            device=self.device,
            refresh_rate_ms=self.ui.refresh_spinner.value(),
            holding_refresh_rate_ms=self.ui.holding_refresh_spinner.value(),
        )
        worker = self.polling_thread
        worker.input_registers_updated.connect(self.update_input_registers)
        worker.holding_registers_updated.connect(self.update_holding_registers)
        worker.polling_failed.connect(self.on_device_polling_failed)
        worker.connection_lost.connect(self.on_device_connection_lost)
        worker.transport_changed.connect(self.on_transport_configuration_changed)
        worker.write_succeeded.connect(self.on_device_write_succeeded)
        worker.write_failed.connect(self.on_device_write_failed)
        worker.service_unlock_finished.connect(self.on_service_unlock_finished)
        self.ui.refresh_spinner.valueChanged.connect(worker.update_refresh_rate)
        self.ui.holding_refresh_spinner.valueChanged.connect(worker.update_holding_refresh_rate)
        worker.start()

    # ---- data ----------------------------------------------------------------

    def update_input_registers(self, elapsed_s: float, data: dict[str, int]) -> None:
        """Store a polled snapshot; the table updates now, the plot on the next timer tick."""
        if self._closing:
            return
        self.time_buffer.append(elapsed_s)
        for name, buffer in self.input_register_buffer.items():
            buffer.append(data.get(name, float("nan")))
        self.input_model.update_values(data)
        self._plot_dirty = True

    def update_holding_registers(self, data: dict[str, int]) -> None:
        if not self._closing:
            self.holding_model.update_values(data)

    def _refresh_plot(self) -> None:
        if not self._plot_dirty or not self.plot_items or not self.isVisible():
            return
        self._plot_dirty = False
        times = self.time_buffer.array()
        for name, item in self.plot_items.items():
            if item.isVisible():
                item.setData(times, self._plot_values(name))

    def _plot_values(self, name: str) -> np.ndarray:
        """History of one register as displayed: raw counts or physical values."""
        raw = self.input_register_buffer[name].array()
        if self.input_model.display_raw:
            return raw
        spec = self.device.REGISTER_MAP[name]
        values = raw * spec.scale
        if spec.unavailable is not None:
            values[raw == spec.unavailable] = np.nan
        return values

    def set_display_raw(self, raw: bool) -> None:
        """Show raw register counts instead of physical values (tables and plot)."""
        for model in (self.input_model, self.holding_model):
            model.set_display_raw(raw)
        self._plot_dirty = True

    @Slot(str, bool)
    def plot_enabled_changed(self, register_name: str, enabled: bool) -> None:
        item = self.plot_items.get(register_name)
        if item is None and enabled:
            color = PALETTE[len(self.plot_items) % len(PALETTE)]
            unit = self.device.REGISTER_MAP[register_name].unit
            label = f"{register_name} [{unit}]" if unit else register_name
            item = self.main_plot.plot([], [], pen=pg.mkPen(color, width=1), name=label)
            self.plot_items[register_name] = item
        if item is not None:
            item.setVisible(enabled)
            self._plot_dirty = True

    def clear_buffers(self) -> None:
        """Reset the plot history."""
        for buffer in self.input_register_buffer.values():
            buffer.clear()
        self.time_buffer.clear()
        self._plot_dirty = True

    # ---- worker events ---------------------------------------------------------

    @property
    def label(self) -> str:
        return self.main_widget.device_label(self.device)

    def on_device_polling_failed(self, error: str) -> None:
        logger.warning("%s poll failed: %s", self.label, error)

    def on_device_connection_lost(self, error: str) -> None:
        """Detach a device after repeated failures, such as a USB unplug."""
        if self._closing:
            return
        label, main_widget, device = self.label, self.main_widget, self.device
        logger.error("Connection lost for %s: %s", label, error)
        self.close_tab()
        main_widget.forget_available_device(device)
        QMessageBox.warning(
            main_widget,
            "Device Disconnected",
            f"{label} stopped responding and was disconnected.\n\nReconnect the hardware, then scan again.",
        )

    def on_device_write_failed(self, register_name: str, error: str, password_required: bool) -> None:
        logger.error("%s: writing %s failed: %s", self.label, register_name, error)
        if password_required and register_name != "pass_static":
            self._prompt_service_password()

    def on_device_write_succeeded(self, register_name: str) -> None:
        logger.info("%s: %s written", self.label, register_name)

    def on_service_unlock_finished(self, accepted: bool) -> None:
        self.set_service_mode(accepted)
        self.main_widget.update_service_mode_action()
        if not accepted:
            QMessageBox.warning(self, "Service Password Rejected", "The device rejected the service password and stays locked.")

    def on_transport_configuration_changed(self, register_name: str, raw_value: int) -> None:
        """The board no longer answers on this link after an rs485_* change: close and rescan."""
        if self._closing:
            return
        main_widget, device, label = self.main_widget, self.device, self.label
        remote = device.link is not None and device.link.kind == "tcp"
        if register_name == "rs485_mb_addr":
            detail = f"The board now answers at Modbus address {raw_value}."
        else:
            detail = f"The board's RS-485 port now runs at {raw_value * 100} baud."
            if remote:
                detail += (
                    "\nThe gateway stays at its ser2net baud rate (9600), so the board is "
                    "unreachable through it until ser2net.yaml is changed."
                )
        self.close_tab()
        main_widget.forget_available_device(device)
        main_widget.rescan("remote" if remote else "local")
        QMessageBox.information(
            main_widget,
            "Connection Settings Changed",
            f"{register_name} was changed on {label}.\n{detail}\n\nThe connection was closed and a new scan started.",
        )

    # ---- writes and service mode -----------------------------------------------

    @property
    def service_mode(self) -> bool:
        return self.holding_model._service_mode

    def set_service_mode(self, enabled: bool) -> None:
        self.holding_model.set_service_mode(enabled)

    def request_service_mode(self, prompt: str = "Enter the service password:") -> None:
        """Ask for the password and let the polling worker verify it on the device."""
        self.main_widget.action_service_mode.setChecked(False)
        password, ok = QInputDialog.getInt(self, "Service Password", prompt, 0, -32767, 32767)
        if ok:
            self.polling_thread.enqueue_service_unlock(password)

    def _prompt_service_password(self) -> None:
        self.request_service_mode("Write rejected — enter the service password:")

    @Slot(int, str, int)
    def holding_write_requested(self, register_id: int, register_name: str, new_value: int) -> None:
        """Queue a table edit on the polling worker; rs485_* changes need confirmation."""
        if register_name in TRANSPORT_REGISTERS and not self._confirm_transport_change(register_name, new_value):
            return  # the next holding poll restores the displayed value
        self.polling_thread.enqueue_write_command(register_id, register_name, new_value)

    def _confirm_transport_change(self, register_name: str, raw_value: int) -> bool:
        remote = self.device.link is not None and self.device.link.kind == "tcp"
        setting = f"address {raw_value}" if register_name == "rs485_mb_addr" else f"{raw_value * 100} baud"
        if remote and register_name == "rs485_baud" and raw_value * 100 == GATEWAY_BAUDRATE:
            text = f"{setting} matches the gateway's ser2net setting."
        elif remote and register_name == "rs485_baud":
            text = (
                "The digitizer gateway talks to this RS-485 bus at a fixed 9600 baud (ser2net.yaml). "
                f"After switching the board to {setting} it will not answer through the gateway "
                "until ser2net is reconfigured."
            )
        elif remote:
            text = f"The board will answer at {setting}. This tab closes and the gateway is rescanned."
        else:
            text = (
                f"Over RS-485 the board switches to {setting} and stops answering at the old setting; "
                "this tab then closes and the ports are rescanned.\n"
                "Over MicroUSB the connection is not affected."
            )
        answer = QMessageBox.question(
            self,
            "Change RS-485 Settings",
            f"{text}\n\nWrite {register_name} = {raw_value}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    # ---- teardown ------------------------------------------------------------

    def stop_polling(self) -> None:
        """Ask the polling thread to stop (non-blocking)."""
        self._closing = True
        self._plot_timer.stop()
        self.polling_thread.stop()

    def close_tab(self) -> None:
        """Remove the tab now; the transport is released once the polling thread exits."""
        index = self.main_widget.ui.device_tabs.indexOf(self)
        if index == -1:
            return
        self.stop_polling()
        self.main_widget.release_device(self.device, self.polling_thread)
        self.main_widget.ui.device_tabs.removeTab(index)
        self.main_widget._open_devices.pop(self.device, None)
        self.main_widget._identities.pop(self.device, None)
        self.main_widget.hide_tabs()
        self.deleteLater()

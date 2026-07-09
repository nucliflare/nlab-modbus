from __future__ import annotations

import logging
import random

import pyqtgraph as pg
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QHeaderView, QInputDialog, QWidget

from nlab_modbus.core.base_modbus_device import BaseModbusDevice
from nlab_modbus.gui.generated.ui_device_tab import Ui_DeviceTab
from nlab_modbus.gui.model.register_tables import HoldingRegisterTableModel, InputRegisterTableModel, ProtectedRowDelegate, RegisterRow
from nlab_modbus.gui.model.ring_buffer import NumpyRingBuffer
from nlab_modbus.services.polling_worker import DevicePollingThread


logger = logging.getLogger(__name__)


class DeviceTab(QWidget):
    """
    Generic GUI tab for displaying and controlling one Modbus device.

    Responsibilities:
    - Owns one concrete BaseModbusDevice-derived instance.
    - Loads the matching .ui file.
    - Displays holding/input register tables.
    - Emits/handles GUI-level register write requests.
    - Manages pyqtgraph plots for selected live values.

    This class should not directly own polling logic if you can avoid it.
    Prefer feeding it snapshots from a worker/service layer.
    """

    def __init__(
        self,
        device: BaseModbusDevice,
        parent: ModbusMainWindow,
    ) -> None:
        super().__init__(parent)

        self.device = device
        self.main_widget = parent
        # self.ui = self._load_ui(self.TAB_UI)
        self.ui = Ui_DeviceTab()
        self.ui.setupUi(self)
        self.ui.type_edit.setText(device.device_type.name)
        self.input_register_buffer = {}
        self.time_buffer = NumpyRingBuffer(1000)
        self.plot_items = {}
        # self.main_plot = None

        input_registers = []
        for i, (register, value) in enumerate(self.device.get_all_input_registers(raw=True).items()):
            self.input_register_buffer[register] = NumpyRingBuffer(1000)
            spec = self.device.REGISTER_MAP[register]
            input_registers.append(RegisterRow(i, register, value, description=spec.description))
        holding_registers = []
        for i, (name, value) in enumerate(self.device.get_all_holding_registers(raw=True).items()):
            spec = self.device.REGISTER_MAP[name]
            holding_registers.append(
                RegisterRow(
                    i, name, value,
                    password_protected=spec.password_protected,
                    min_val=spec.min,
                    max_val=spec.max,
                    description=spec.description,
                )
            )
        self.holding_model = HoldingRegisterTableModel(holding_registers)
        self.input_model = InputRegisterTableModel(input_registers)

        self.lines_dict: dict[str, list[pg.PlotDataItem]] = {}

        self._setup_register_tables()
        self._connect_signals()
        self._setup_plots()
        self._run_worker()

    def _setup_register_tables(self) -> None:
        """Attach models to the two table views and apply column sizing."""
        self.ui.holding_table_view.setModel(self.holding_model)
        self.ui.holding_table_view.setItemDelegate(ProtectedRowDelegate(self.ui.holding_table_view))
        self.ui.input_table_view.setModel(self.input_model)

        for table in (
            self.ui.holding_table_view,
            self.ui.input_table_view,
        ):
            table.setAlternatingRowColors(True)
            table.verticalHeader().setVisible(False)

        self._configure_input_table()
        self._configure_holding_table()

    def _configure_holding_table(self) -> None:
        """ID fixed to content; Register and Value user-resizable; Value stretches to fill."""
        table = self.ui.holding_table_view
        header = table.horizontalHeader()

        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)       # Register
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)       # Value
        header.setStretchLastSection(True)

    def _configure_input_table(self) -> None:
        """ID and Plot fixed; Register and Value user-resizable; Register stretches to fill."""
        table = self.ui.input_table_view
        header = table.horizontalHeader()

        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)       # Register
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)       # Value
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Plot
        header.setStretchLastSection(False)
        header.resizeSection(1, 180)  # Register initial width
        header.resizeSection(2, 80)   # Value initial width

    def _connect_signals(self) -> None:
        """Wire model signals, button clicks, and plot toggle to their slots."""
        self.holding_model.write_requested.connect(self.holding_write_requested)
        self.input_model.plot_enabled_changed.connect(self.plot_enabled_changed)
        self.ui.tab_disconnect_btn.clicked.connect(self.close_tab)
        self.ui.clear_plot_btn.clicked.connect(self.clear_buffers)

    def _setup_plots(self) -> None:
        """
        Main plot setup entry point.

        Assumes the .ui file contains a pyqtgraph GraphicsView or PlotWidget
        named something like:

            self.ui.plot_graphics_view

        Adjust the widget name to match your .ui file, because Qt Designer
        will not read your mind. Tragically.
        """
        labels = {
            "input": "Input registers",
        }

        self._setup_single_plot(
            plot=self.ui.input_plot,
            key="input",
            label=labels["input"],
        )

    def _setup_single_plot(
        self,
        plot: pg.GraphicsView,
        key: str,
        label: str,
    ) -> None:
        """Configure one pyqtgraph GraphicsView: layout, axes, grid, and Y label."""
        layout = pg.GraphicsLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        plot.setCentralItem(layout)
        plot.setBackground("#ffffff")

        layout.addLabel(label, angle=-90)

        self.main_plot = layout.addPlot()

        self.main_plot.showAxis("right")
        self.main_plot.showAxis("top")
        self.main_plot.showGrid(x=True, y=True, alpha=0.2)

        dashed_grey_pen = pg.mkPen(
            "grey",
            width=2,
            style=Qt.PenStyle.DashLine,
        )

        self.main_plot.getAxis("bottom").setTickPen(dashed_grey_pen)
        self.main_plot.getAxis("left").setTickPen(dashed_grey_pen)

        layout.nextRow()
        layout.addLabel("Time [s]", col=1)

        viewbox = self.main_plot.getViewBox()
        viewbox.setBorder(pg.mkPen({"color": "black", "width": 2}))
        viewbox.setBackgroundColor((255, 255, 255))

    def _run_worker(self):
        """Create and start the DevicePollingThread, wiring its signals to this tab's slots."""
        self.polling_thread = DevicePollingThread(
            device=self.device,
            refresh_rate_ms=self.ui.refresh_spinner.value(),
            holding_refresh_rate_ms=self.ui.holding_refresh_spinner.value(),
        )
        self.polling_thread.input_registers_updated.connect(self.update_input_registers)
        self.polling_thread.holding_registers_updated.connect(self.update_holding_registers)
        self.polling_thread.polling_failed.connect(self.on_device_polling_failed)
        self.polling_thread.write_failed.connect(self.on_device_write_failed)
        self.ui.refresh_spinner.valueChanged.connect(self.polling_thread.update_refresh_rate)
        self.ui.holding_refresh_spinner.valueChanged.connect(self.polling_thread.update_holding_refresh_rate)
        self.polling_thread.start()

    def update_input_registers(
        self,
        elapsed_s: float,
        data: dict[str, int],
    ) -> None:
        """Slot: receive a polled snapshot, push values into buffers and the table model."""
        self.time_buffer.append(elapsed_s)
        for register_name, value in data.items():
            row_index = self.device.get_register_address(register_name)
            self.input_model.update_value(row_index, value)
            self.input_register_buffer[register_name].append(value)

        self.update_plots()

    def update_holding_registers(self, data: dict[str, int]):
        """Slot: refresh the holding register table after a successful write-readback."""
        for register_name, value in data.items():
            row_index = self.device.get_register_address(register_name)
            self.holding_model.update_value(row_index, value)

    def on_device_polling_failed(self, error: str):
        logger.warning("%s poll failed: %s", self.device.connection_info(), error)

    def on_device_write_failed(self, error: str):
        logger.error("%s write failed: %s", self.device.connection_info(), error)
        if "exception_code=4" in error:
            self._prompt_service_password()

    @property
    def service_mode(self) -> bool:
        return self.holding_model._service_mode

    def set_service_mode(self, enabled: bool) -> None:
        self.holding_model.set_service_mode(enabled)

    def _prompt_service_password(self) -> None:
        password, ok = QInputDialog.getInt(
            self, "Service Password",
            "Write rejected — enter the service password:",
            0, -32767, 32767,
        )
        if ok:
            try:
                self.device.write("pass_static", password)
                self.holding_model.update_value(
                    self.device.get_register_address("pass_static"), password
                )
                self.set_service_mode(True)
                self.main_widget.update_service_mode_action()
            except Exception as exc:
                logger.error("Password write failed: %s", exc)

    @Slot(int, str, int)
    def holding_write_requested(self, register_id: int, register_name: str, new_value: int) -> None:
        """
        Called when the holding register table model requests a write.

        Keep this thin. Ideally forward the request to a worker/service layer,
        because direct Modbus I/O in the GUI thread is where apps go to die.
        """

        self.polling_thread.enqueue_write_command(register_id, register_name, new_value)

    @Slot(str, bool)
    def plot_enabled_changed(self, register_name: str, enabled: bool) -> None:
        """
        Called when a model row toggles plotting on/off.
        """
        if enabled:
            if register_name not in self.plot_items:
                color = (
                    random.randint(128, 255),
                    random.randint(128, 255),
                    random.randint(128, 255),
                )

                plot = self.main_plot.plot(
                    [],
                    [],
                    pen=pg.mkPen({"color": color, "width": 3.0}),
                    name=register_name,
                )

                self.plot_items[register_name] = plot
            self.plot_items[register_name].show()
        else:
            self.plot_items[register_name].hide()

    def update_plots(self) -> None:
        """
        Update one plotted line.

        Parameters
        ----------
        key:
            Plot group key, for example "input" or "holding".
        x:
            Time axis.
        y:
            Register values.
        channel:
            Line index inside self.lines_dict[key].
        """

        registers_to_plot = self.input_model.plot_enabled_dict()
        for register, enabled in registers_to_plot.items():
            if enabled:
                self.plot_items[register].setData(self.time_buffer.array(), self.input_register_buffer[register].array())

    def close(self):
        """Stop the polling thread gracefully (waits up to 2 s for it to exit)."""
        if self.polling_thread:
            self.polling_thread.stop()
            self.polling_thread.wait(500)

    def close_tab(self):
        """Remove this tab from the QTabWidget and schedule the widget for deletion."""
        index = self.main_widget.ui.device_tabs.indexOf(self)
        if index == -1:
            return
        self.close()
        self.main_widget.manager.disconnect(self.device)
        self.main_widget.ui.device_tabs.removeTab(index)
        self.main_widget._open_devices.pop(self.device, None)
        self.main_widget.hide_tabs()
        self.deleteLater()

    def clear_buffers(self):
        """Reset all ring buffers and the time axis (clears the plot history)."""
        for buffer in self.input_register_buffer.values():
            buffer.clear()
        self.time_buffer.clear()

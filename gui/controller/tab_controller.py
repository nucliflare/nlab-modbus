from __future__ import annotations

from pathlib import Path
from typing import Any

import pyqtgraph as pg
from model.register_tables import HoldingRegisterTableModel, InputRegisterTableModel, RegisterRow
from PySide6.QtCore import Qt, Slot
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QVBoxLayout, QWidget

from nlab_modbus.core.base_modbus_device import BaseModbusDevice


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

    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    TAB_UI = PROJECT_ROOT / "view" / "device_tab.ui"

    def __init__(
        self,
        device: BaseModbusDevice,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.device = device

        self.ui = self._load_ui(self.TAB_UI)

        input_registers = [RegisterRow(i, *pair) for i, pair in enumerate(self.device.get_all_input_registers().items())]
        holding_registers = [RegisterRow(i, *pair) for i, pair in enumerate(self.device.get_all_holding_registers().items())]
        self.holding_model = HoldingRegisterTableModel(holding_registers)
        self.input_model = InputRegisterTableModel(input_registers)

        self.lines_dict: dict[str, list[pg.PlotDataItem]] = {}

        self._setup_layout()
        self._setup_register_tables()
        self._connect_signals()
        self._setup_plots()

    def _load_ui(self, ui_file: Path) -> QWidget:
        loader = QUiLoader()

        loader.registerCustomWidget(pg.PlotWidget)
        loader.registerCustomWidget(pg.GraphicsView)
        ui_file = ui_file.resolve()
        if not ui_file.exists():
            raise FileNotFoundError(f"UI file not found: {ui_file}")

        widget = loader.load(str(ui_file), self)
        if widget is None:
            raise RuntimeError(f"Failed to load UI file: {ui_file}")

        return widget

    def _setup_layout(self) -> None:
        """
        Put loaded .ui widget inside this QWidget.

        If your .ui file's top-level widget is already intended to be this
        widget, you can also use loadUi-style approaches instead. With
        QUiLoader, wrapping it into this widget is usually cleaner.
        """

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.ui)

        self.ui.type_edit.setText(self.device.device_type.name)

    def _setup_register_tables(self) -> None:
        self.ui.holding_table_view.setModel(self.holding_model)
        self.ui.input_table_view.setModel(self.input_model)

        self.ui.holding_table_view.resizeColumnsToContents()
        self.ui.input_table_view.resizeColumnsToContents()

        self.ui.holding_table_view.setAlternatingRowColors(True)
        self.ui.input_table_view.setAlternatingRowColors(True)

    def _connect_signals(self) -> None:
        self.holding_model.write_requested.connect(self.on_holding_write_requested)

        self.input_model.plot_enabled_changed.connect(self.on_plot_enabled_changed)

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
            # "holding": "Holding registers",
        }

        self._setup_single_plot(
            plot=self.ui.input_plot,
            key="input",
            label=labels["input"],
        )

        # self._setup_single_plot(
        #     plot=self.ui.holding_plot_widget,
        #     key="holding",
        #     label=labels["holding"],
        # )

    def _setup_single_plot(
        self,
        plot: pg.GraphicsView,
        key: str,
        label: str,
    ) -> None:
        layout = pg.GraphicsLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        plot.setCentralItem(layout)
        plot.setBackground("#f8f9fa")

        layout.addLabel(label, angle=-90)

        plot_item = layout.addPlot()

        plot_0 = plot_item.plot(
            [],
            [],
            pen=pg.mkPen({"color": "red", "width": 0.5}),
            name="Channel 0",
        )

        self.lines_dict[key] = [plot_0]

        plot_item.showAxis("right")
        plot_item.showAxis("top")
        plot_item.showGrid(x=True, y=True, alpha=0.2)

        dashed_grey_pen = pg.mkPen(
            "grey",
            width=2,
            style=Qt.PenStyle.DashLine,
        )

        plot_item.getAxis("bottom").setTickPen(dashed_grey_pen)
        plot_item.getAxis("left").setTickPen(dashed_grey_pen)

        layout.nextRow()
        layout.addLabel("Time [s]", col=1)

        viewbox = plot_item.getViewBox()
        viewbox.setBorder(pg.mkPen({"color": "black", "width": 2}))
        viewbox.setBackgroundColor((255, 255, 255))

    @Slot(object, object)
    def on_holding_write_requested(self, register: object, value: object) -> None:
        """
        Called when the holding register table model requests a write.

        Keep this thin. Ideally forward the request to a worker/service layer,
        because direct Modbus I/O in the GUI thread is where apps go to die.
        """
        # Example only:
        # self.write_requested.emit(self.device, register, value)
        #
        # Or, if you really want to do it directly:
        # self.device.write_register(register.name, value)

        raise NotImplementedError

    @Slot(object, bool)
    def on_plot_enabled_changed(self, register: object, enabled: bool) -> None:
        """
        Called when a model row toggles plotting on/off.
        """
        # Example:
        # if enabled:
        #     self._add_register_plot(register)
        # else:
        #     self._remove_register_plot(register)

        raise NotImplementedError

    def update_register_tables(
        self,
        holding_rows: list[Any] | None = None,
        input_rows: list[Any] | None = None,
    ) -> None:
        """
        Update table model data from a fresh device snapshot.

        Exact method names depend on your table model implementation.
        """
        if holding_rows is not None:
            self.holding_model.set_rows(holding_rows)

        if input_rows is not None:
            self.input_model.set_rows(input_rows)

    def update_plot_data(
        self,
        key: str,
        x: list[float],
        y: list[float],
        channel: int = 0,
    ) -> None:
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
        if key not in self.lines_dict:
            return

        lines = self.lines_dict[key]

        if channel >= len(lines):
            return

        lines[channel].setData(x, y)

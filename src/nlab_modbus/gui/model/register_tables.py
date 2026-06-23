from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    Qt,
    Signal,
)


@dataclass
class RegisterRow:
    """One row of data shared by both table models.

    register_id maps to the Modbus address so updates from the polling thread
    can locate the correct row without a full linear scan on every poll cycle.
    plot_enabled is only meaningful for input registers.
    """

    register_id: int
    name: str
    value: int = 0
    plot_enabled: bool = False
    password_protected: bool = False


class HoldingRegisterTableModel(QAbstractTableModel):
    """Qt table model for holding (read/write) registers.

    Displays three columns: ID, Register name, Value.  The Value column is
    editable; committing a new integer emits write_requested so the tab
    controller can forward it to the polling thread's write queue without the
    model touching Modbus directly.
    """

    write_requested = Signal(int, str, int)

    COL_ID = 0
    COL_REGISTER = 1
    COL_VALUE = 2

    HEADERS = ["ID", "Register", "Value"]

    def __init__(
        self,
        rows: list[RegisterRow] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._rows = rows or []
        self._service_mode = False

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.HEADERS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]

        return str(section + 1)

    def data(
        self,
        index: QModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid():
            return None

        row = self._rows[index.row()]
        col = index.column()

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if col == self.COL_ID:
                return row.register_id
            if col == self.COL_REGISTER:
                return row.name
            if col == self.COL_VALUE:
                return row.value

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (self.COL_ID, self.COL_VALUE):
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        return None

    def set_service_mode(self, enabled: bool) -> None:
        self._service_mode = enabled
        self.layoutChanged.emit()

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

        if index.column() == self.COL_VALUE:
            row = self._rows[index.row()]
            if not row.password_protected or self._service_mode:
                flags |= Qt.ItemFlag.ItemIsEditable

        return flags

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        """Accept a user edit on the Value column and emit write_requested.

        Rejects the edit silently if the value can't be parsed as an integer or
        falls outside the int16 range.  No-ops if the value is unchanged to
        avoid spurious writes to the device.
        """
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False
        if index.column() != self.COL_VALUE:
            return False
        row = self._rows[index.row()]
        try:
            new_value = int(float(str(value).strip()))
        except (ValueError, TypeError):
            return False
        if not -0x8000 <= new_value <= 0x7FFF:
            return False
        if new_value == row.value:
            return True
        row.value = new_value
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
        self.write_requested.emit(row.register_id, row.name, new_value)
        return True

    def update_value(self, register_id: int, value: int) -> None:
        for row_idx, row in enumerate(self._rows):
            if row.register_id != register_id:
                continue

            row.value = value
            index = self.index(row_idx, self.COL_VALUE)

            self.dataChanged.emit(
                index,
                index,
                [Qt.ItemDataRole.DisplayRole],
            )
            return


class InputRegisterTableModel(QAbstractTableModel):
    """Qt table model for input (read-only) registers.

    Displays four columns: ID, Register name, Value, Plot checkbox.  Values are
    updated by the polling thread via update_value(); the Plot column lets users
    toggle a live pyqtgraph trace for any register.  Toggling emits
    plot_enabled_changed so the tab controller can add/hide plot curves.
    """

    plot_enabled_changed = Signal(str, bool)

    COL_ID = 0
    COL_REGISTER = 1
    COL_VALUE = 2
    COL_PLOT = 3

    HEADERS = ["ID", "Register", "Value", "Plot"]

    def __init__(
        self,
        rows: list[RegisterRow] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._rows: list[RegisterRow] = rows if rows is not None else []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0

        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0

        return len(self.HEADERS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self.HEADERS):
                return self.HEADERS[section]
            return None

        return str(section + 1)

    def data(
        self,
        index: QModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid():
            return None

        row_index = index.row()
        col = index.column()

        if row_index < 0 or row_index >= len(self._rows):
            return None

        row = self._rows[row_index]

        if role == Qt.ItemDataRole.CheckStateRole:
            if col == self.COL_PLOT:
                return Qt.CheckState.Checked if row.plot_enabled else Qt.CheckState.Unchecked

            return None

        if role in (
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.EditRole,
        ):
            if col == self.COL_ID:
                return row.register_id

            if col == self.COL_REGISTER:
                return row.name

            if col == self.COL_VALUE:
                return row.value

            if col == self.COL_PLOT:
                return ""

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (self.COL_ID, self.COL_VALUE):
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

            if col == self.COL_PLOT:
                return Qt.AlignmentFlag.AlignCenter

            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

        if index.column() == self.COL_PLOT:
            flags |= Qt.ItemFlag.ItemIsUserCheckable

        return flags

    def setData(
        self,
        index: QModelIndex,
        value: Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if not index.isValid():
            return False

        row_index = index.row()
        col = index.column()

        if row_index < 0 or row_index >= len(self._rows):
            return False

        if col != self.COL_PLOT:
            return False

        if role != Qt.ItemDataRole.CheckStateRole:
            return False

        row = self._rows[row_index]

        enabled = value in (
            Qt.CheckState.Checked,
            Qt.CheckState.Checked.value,
            int(Qt.CheckState.Checked.value),
        )

        if row.plot_enabled == enabled:
            return False

        row.plot_enabled = enabled

        self.dataChanged.emit(
            index,
            index,
            [Qt.ItemDataRole.CheckStateRole],
        )

        self.plot_enabled_changed.emit(
            row.name,
            enabled,
        )

        return True

    def update_value(
        self,
        row_index: int,
        value: int,
    ) -> None:
        """
        Update only the value cell in the i-th table row.

        This does not insert rows, remove rows, reset the model,
        or modify any other cells.
        """

        if row_index < 0 or row_index >= len(self._rows):
            return

        row = self._rows[row_index]

        if row.value == value:
            return

        row.value = value

        value_index = self.index(row_index, self.COL_VALUE)

        self.dataChanged.emit(
            value_index,
            value_index,
            [
                Qt.ItemDataRole.DisplayRole,
                Qt.ItemDataRole.EditRole,
            ],
        )

    def update_value_by_register_id(
        self,
        register_id: int,
        value: int,
    ) -> None:
        """
        Optional helper if you want to update by register_id instead of row index.
        """

        for row_index, row in enumerate(self._rows):
            if row.register_id == register_id:
                self.update_value(row_index, value)
                return

    def plot_enabled_dict(self) -> dict[str, bool]:
        return {row.name: row.plot_enabled for row in self._rows}

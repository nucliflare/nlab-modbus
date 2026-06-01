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
    register_id: int
    name: str
    value: int = 0
    plot_enabled: bool = False


class HoldingRegisterTableModel(QAbstractTableModel):
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

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

        if index.column() == self.COL_VALUE:
            flags |= Qt.ItemFlag.ItemIsEditable

        return flags

    def setData(
        self,
        index: QModelIndex,
        value: Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if not index.isValid():
            return False

        if role != Qt.ItemDataRole.EditRole:
            return False

        if index.column() != self.COL_VALUE:
            return False

        row = self._rows[index.row()]

        try:
            new_value = int(str(value).strip())
        except ValueError:
            return False

        if not 0 <= new_value <= 65535:
            return False

        row.value = new_value

        self.dataChanged.emit(
            index,
            index,
            [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole],
        )

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
    plot_enabled_changed = Signal(int, str, bool)

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
        self._rows = rows or []

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

        if role == Qt.ItemDataRole.CheckStateRole:
            if col == self.COL_PLOT:
                return Qt.CheckState.Checked if row.plot_enabled else Qt.CheckState.Unchecked
            return None

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
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

        if index.column() != self.COL_PLOT:
            return False

        if role != Qt.ItemDataRole.CheckStateRole:
            return False

        row = self._rows[index.row()]
        enabled = value == Qt.CheckState.Checked.value

        row.plot_enabled = enabled

        self.dataChanged.emit(
            index,
            index,
            [Qt.ItemDataRole.CheckStateRole],
        )

        self.plot_enabled_changed.emit(row.register_id, row.name, enabled)
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

    def plotted_registers(self) -> list[RegisterRow]:
        return [row for row in self._rows if row.plot_enabled]

"""Qt table models for holding and input registers.

Rows keep the raw register count; the view shows either the raw count or
the physical value (``raw * scale`` with its unit), toggled by
``set_display_raw``. Edits are accepted in the displayed form and converted
to a validated raw count before a write is requested.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from nlab_modbus.core.register_specs import RegisterSpec, RegisterType, decode_register_value, to_raw

_DISPLAY = Qt.ItemDataRole.DisplayRole
_EDIT = Qt.ItemDataRole.EditRole
_RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
_LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter


@dataclass
class RegisterRow:
    """One table row: the register's raw value plus how to display and validate it."""

    register_id: int
    name: str
    value: int = 0
    plot_enabled: bool = False
    password_protected: bool = False
    min_val: int = -0x8000
    max_val: int = 0x7FFF
    description: str = ""
    spec: RegisterSpec | None = None

    @classmethod
    def from_spec(cls, name: str, spec: RegisterSpec, value: int) -> RegisterRow:
        return cls(
            spec.address, name, value,
            password_protected=spec.password_protected,
            min_val=spec.min, max_val=spec.max,
            description=spec.description, spec=spec,
        )

    @property
    def effective_spec(self) -> RegisterSpec:
        if self.spec is not None:
            return self.spec
        return RegisterSpec(RegisterType.HOLDING, self.register_id, "int16", self.min_val, self.max_val)

    @property
    def decimals(self) -> int:
        """Digits needed to show one raw count: 0.01 → 2, 0.1 → 1, ≥ 1 → 0."""
        scale = self.effective_spec.scale
        return 0 if scale >= 1 else max(0, -math.floor(math.log10(scale) + 1e-9))

    def text(self, raw: bool) -> str:
        if raw:
            return str(self.value)
        value = decode_register_value(self.value, self.effective_spec)
        if isinstance(value, float):
            return "n/a" if math.isnan(value) else f"{value:.{self.decimals}f}"
        return str(int(value))

    def unit_text(self, raw: bool) -> str:
        spec = self.effective_spec
        if raw and spec.scale != 1:
            return f"×{spec.scale:g} {spec.unit or ''}".rstrip()
        return spec.unit or ""

    def tooltip(self, raw: bool) -> str:
        spec = self.effective_spec
        unit = f" {spec.unit}" if spec.unit else ""
        lines = [self.description] if self.description else []
        if spec.scale != 1:
            lines.append(f"= {self.text(raw=False)}{unit}" if raw else f"Raw count: {self.value}")
        if spec.reg_type is RegisterType.HOLDING:
            limits = f"Limits: {spec.min * spec.scale:g} … {spec.max * spec.scale:g}{unit}"
            if spec.default is not None:
                limits += f", default {spec.default * spec.scale:g}"
            lines.append(limits)
            flags = [text for flag, text in ((spec.persistent, "saved to EEPROM"), (spec.password_protected, "needs service password")) if flag]
            if flags:
                lines.append("; ".join(flags).capitalize())
        return "\n".join(lines)

    def parse(self, text: Any, raw: bool) -> int:
        """Convert edited text (raw count or physical value) to a validated raw count."""
        number = float(str(text).strip().replace(",", "."))
        if raw and not number.is_integer():
            raise ValueError("Raw counts must be whole numbers")
        return to_raw(int(number) if raw else number, self.effective_spec, raw=raw)


class _RegisterTableModel(QAbstractTableModel):
    """Shared behaviour: raw/physical display, batched updates, tooltips."""

    HEADERS: list[str] = []
    COL_ID = 0
    COL_REGISTER = 1
    COL_VALUE = 2
    COL_UNIT = 3

    def __init__(self, rows: list[RegisterRow] | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[RegisterRow] = rows or []
        self._row_by_name = {row.name: index for index, row in enumerate(self._rows)}
        self._display_raw = False

    @property
    def display_raw(self) -> bool:
        return self._display_raw

    def set_display_raw(self, raw: bool) -> None:
        if raw != self._display_raw:
            self._display_raw = raw
            self._emit_rows(0, len(self._rows) - 1, self.COL_VALUE, self.COL_UNIT)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = _DISPLAY) -> Any:
        if role != _DISPLAY:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section] if 0 <= section < len(self.HEADERS) else None
        return str(section + 1)

    def data(self, index: QModelIndex, role: int = _DISPLAY) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row, col = self._rows[index.row()], index.column()
        if role == Qt.ItemDataRole.ToolTipRole:
            return row.tooltip(self._display_raw) or None
        if role in (_DISPLAY, _EDIT):
            if col == self.COL_ID:
                return row.register_id
            if col == self.COL_REGISTER:
                return row.name
            if col == self.COL_VALUE:
                return row.text(self._display_raw)
            if col == self.COL_UNIT:
                return row.unit_text(self._display_raw)
            return None
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return _RIGHT if col in (self.COL_ID, self.COL_VALUE) else _LEFT
        return None

    def update_values(self, values: dict[str, int]) -> None:
        """Apply a snapshot ``{name: raw}``; emits one dataChanged for the changed span."""
        changed = []
        for name, value in values.items():
            index = self._row_by_name.get(name)
            if index is not None and self._rows[index].value != value:
                self._rows[index].value = value
                changed.append(index)
        if changed:
            self._emit_rows(min(changed), max(changed), self.COL_VALUE, self.COL_VALUE)

    def update_value(self, register_id: int, value: int) -> None:
        for row in self._rows:
            if row.register_id == register_id:
                self.update_values({row.name: value})
                return

    update_value_by_register_id = update_value

    def row(self, name: str) -> RegisterRow | None:
        index = self._row_by_name.get(name)
        return None if index is None else self._rows[index]

    def _emit_rows(self, first: int, last: int, first_col: int, last_col: int) -> None:
        if last >= first >= 0:
            self.dataChanged.emit(self.index(first, first_col), self.index(last, last_col), [_DISPLAY, _EDIT])


class ProtectedRowDelegate(QStyledItemDelegate):
    """Mutes the selection highlight of password-protected rows outside service mode."""

    def initStyleOption(self, option, index) -> None:
        super().initStyleOption(option, index)
        model = index.model()
        if not isinstance(model, HoldingRegisterTableModel):
            return
        row = model._rows[index.row()]
        if row.password_protected and not model._service_mode and option.state & QStyle.StateFlag.State_Selected:
            option.palette.setColor(QPalette.ColorGroup.Active, QPalette.ColorRole.Highlight, QColor(200, 215, 230))
            option.palette.setColor(QPalette.ColorGroup.Active, QPalette.ColorRole.HighlightedText, QColor(120, 120, 120))


class HoldingRegisterTableModel(_RegisterTableModel):
    """Holding registers: editable Value column; edits emit ``write_requested`` with a raw count."""

    write_requested = Signal(int, str, int)
    edit_rejected = Signal(str, str)  # register name, reason

    HEADERS = ["ID", "Register", "Value", "Unit"]

    def __init__(self, rows: list[RegisterRow] | None = None, parent: QObject | None = None) -> None:
        super().__init__(rows, parent)
        self._service_mode = False

    def data(self, index: QModelIndex, role: int = _DISPLAY) -> Any:
        if role == Qt.ItemDataRole.ForegroundRole and index.isValid():
            row = self._rows[index.row()]
            if row.password_protected and not self._service_mode:
                return QColor(160, 160, 160)
        return super().data(index, role)

    def set_service_mode(self, enabled: bool) -> None:
        self._service_mode = enabled
        self.layoutChanged.emit()

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        row = self._rows[index.row()]
        if index.column() == self.COL_VALUE and (not row.password_protected or self._service_mode):
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def setData(self, index: QModelIndex, value: Any, role: int = _EDIT) -> bool:
        """Validate an edit against the firmware limits and request a raw write."""
        if not index.isValid() or role != _EDIT or index.column() != self.COL_VALUE:
            return False
        row = self._rows[index.row()]
        try:
            new_raw = row.parse(value, self._display_raw)
        except (TypeError, ValueError) as exc:
            self.edit_rejected.emit(row.name, str(exc))
            return False
        if new_raw == row.value:
            return True
        row.value = new_raw
        self._emit_rows(index.row(), index.row(), self.COL_VALUE, self.COL_VALUE)
        self.write_requested.emit(row.register_id, row.name, new_raw)
        return True


class InputRegisterTableModel(_RegisterTableModel):
    """Input registers: read-only values plus a Plot checkbox column."""

    plot_enabled_changed = Signal(str, bool)

    HEADERS = ["ID", "Register", "Value", "Unit", "Plot"]
    COL_PLOT = 4

    def data(self, index: QModelIndex, role: int = _DISPLAY) -> Any:
        if index.isValid() and index.column() == self.COL_PLOT:
            if role == Qt.ItemDataRole.CheckStateRole:
                row = self._rows[index.row()]
                return Qt.CheckState.Checked if row.plot_enabled else Qt.CheckState.Unchecked
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return Qt.AlignmentFlag.AlignCenter
            if role in (_DISPLAY, _EDIT):
                return ""
        return super().data(index, role)

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == self.COL_PLOT:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        return flags

    def setData(self, index: QModelIndex, value: Any, role: int = _EDIT) -> bool:
        if not index.isValid() or index.column() != self.COL_PLOT or role != Qt.ItemDataRole.CheckStateRole:
            return False
        row = self._rows[index.row()]
        enabled = value in (Qt.CheckState.Checked, Qt.CheckState.Checked.value)
        if row.plot_enabled == enabled:
            return False
        row.plot_enabled = enabled
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
        self.plot_enabled_changed.emit(row.name, enabled)
        return True

    def plot_enabled_dict(self) -> dict[str, bool]:
        return {row.name: row.plot_enabled for row in self._rows}

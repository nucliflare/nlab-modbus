from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from nlab_modbus.gui.model.register_tables import (  # noqa: E402
    HoldingRegisterTableModel,
    InputRegisterTableModel,
    RegisterRow,
)
from nlab_modbus.maps.psu_map import PSU_REGISTER_MAP  # noqa: E402
from nlab_modbus.maps.sipm_map import SIPM_REGISTER_MAP  # noqa: E402


class TableModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_snapshot_updates_emit_one_notification_for_changed_rows(self):
        model = InputRegisterTableModel([RegisterRow(i, f"r{i}", 0) for i in range(20)])
        spans = []
        model.dataChanged.connect(lambda first, last, _roles: spans.append((first.row(), last.row())))

        model.update_values({"r3": 5, "r7": 9, "r12": 0, "unknown": 1})
        model.update_values({"r3": 5})  # unchanged: no repaint

        self.assertEqual(spans, [(3, 7)])
        self.assertEqual(model.data(model.index(7, model.COL_VALUE)), "9")

    def test_values_show_physical_units_or_raw_counts(self):
        model = HoldingRegisterTableModel([RegisterRow.from_spec("vout_set", SIPM_REGISTER_MAP["vout_set"], 4567)])
        value, unit = model.index(0, model.COL_VALUE), model.index(0, model.COL_UNIT)

        self.assertEqual((model.data(value), model.data(unit)), ("45.67", "V"))
        model.set_display_raw(True)
        self.assertEqual((model.data(value), model.data(unit)), ("4567", "×0.01 V"))

    def test_missing_sensor_shows_not_available(self):
        model = InputRegisterTableModel([RegisterRow.from_spec("pmt_temp", PSU_REGISTER_MAP["pmt_temp"], -30000)])
        self.assertEqual(model.data(model.index(0, model.COL_VALUE)), "n/a")

    def test_edits_are_converted_and_checked_against_firmware_limits(self):
        model = HoldingRegisterTableModel([RegisterRow.from_spec("vout_set", SIPM_REGISTER_MAP["vout_set"], 4567)])
        writes, rejected = [], []
        model.write_requested.connect(lambda _id, name, raw: writes.append((name, raw)))
        model.edit_rejected.connect(lambda name, _reason: rejected.append(name))
        value = model.index(0, model.COL_VALUE)

        model.setData(value, "45.5")
        model.setData(value, "100")  # above the 78 V limit
        model.set_display_raw(True)
        model.setData(value, "4600")

        self.assertEqual(writes, [("vout_set", 4550), ("vout_set", 4600)])
        self.assertEqual(rejected, ["vout_set"])


if __name__ == "__main__":
    unittest.main()

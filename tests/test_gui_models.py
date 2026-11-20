from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from nlab_modbus.gui.model.register_tables import InputRegisterTableModel, RegisterRow  # noqa: E402


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
        self.assertEqual(model.data(model.index(7, model.COL_VALUE)), 9)


if __name__ == "__main__":
    unittest.main()

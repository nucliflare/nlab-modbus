from __future__ import annotations

import sys
from pathlib import Path

from controller.main_controller import ModbusMainWindow
from PySide6.QtCore import QFile, QIODevice
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QApplication, QMainWindow

BASE_DIR = Path(__file__).resolve().parent
UI_PATH = BASE_DIR / "view" / "main_window.ui"


def load_ui(ui_path: Path):
    if not ui_path.exists():
        raise FileNotFoundError(f"UI file not found: {ui_path}")

    ui_file = QFile(str(ui_path))

    if not ui_file.open(QIODevice.OpenModeFlag.ReadOnly):
        raise RuntimeError(f"Could not open UI file: {ui_path}")

    try:
        loader = QUiLoader()
        widget = loader.load(ui_file)

        if widget is None:
            raise RuntimeError(f"Could not load UI file: {ui_path}")

        return widget

    finally:
        ui_file.close()


def main() -> int:
    app = QApplication(sys.argv)

    window = ModbusMainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

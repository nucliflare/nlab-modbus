from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from nlab_modbus.gui.controller.main_controller import ModbusMainWindow

PROJECT_ROOT = Path(__file__).resolve().parent
APP_ICON = PROJECT_ROOT / "resources" / "ewt.ico"


def main() -> int:

    if sys.platform == "win32":
        myappid = "EWT.Modbus.Monitor.0.3.0"  # arbitrary but unique
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    app = QApplication(sys.argv)

    window = ModbusMainWindow()
    window.show()

    if APP_ICON.exists():
        app.setWindowIcon(QIcon(str(APP_ICON)))
    else:
        raise FileNotFoundError(f"Application icon not found: {APP_ICON}")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

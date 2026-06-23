from __future__ import annotations

import ctypes
import logging
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from nlab_modbus import __version__
from nlab_modbus.gui.controller.main_controller import ModbusMainWindow
from nlab_modbus.gui.model.log_handler import QtLogHandler

_SCRIPT_DIR = Path(__file__).resolve().parent


def _find_icon() -> Path:
    candidates = [
        _SCRIPT_DIR / "resources" / "ewt.ico",
        _SCRIPT_DIR / "nlab_modbus" / "gui" / "resources" / "ewt.ico",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(f"Application icon not found in: {candidates}")


def main() -> int:
    """Create the QApplication, open the main window, and run the event loop.

    Sets a Windows AppUserModelID so the taskbar icon matches the window icon
    rather than the generic Python launcher icon.
    """
    if sys.platform == "win32":
        myappid = f"EWT.Modbus.Monitor.{__version__}"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    app = QApplication(sys.argv)

    log_handler = QtLogHandler()
    root_logger = logging.getLogger("nlab_modbus")
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(log_handler)

    window = ModbusMainWindow(log_handler=log_handler)
    window.show()

    app.setWindowIcon(QIcon(str(_find_icon())))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

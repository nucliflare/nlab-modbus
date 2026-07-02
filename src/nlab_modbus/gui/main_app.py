from __future__ import annotations

import argparse
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
    parser = argparse.ArgumentParser(description="nlab Modbus Monitor GUI")
    parser.add_argument(
        "--baudrate", type=int, default=115200,
        metavar="BAUD",
        help="Serial baud rate used for the initial device scan (default: 115200)",
    )
    parser.add_argument(
        "--start-id", type=int, default=1,
        metavar="ID",
        help="First Modbus device ID to probe during scan (default: 1)",
    )
    parser.add_argument(
        "--end-id", type=int, default=16,
        metavar="ID",
        help="Last Modbus device ID to probe during scan (default: 253)",
    )
    args, _ = parser.parse_known_args()

    if sys.platform == "win32":
        myappid = f"EWT.Modbus.Monitor.{__version__}"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    app = QApplication(sys.argv)

    log_handler = QtLogHandler()
    root_logger = logging.getLogger("nlab_modbus")
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(log_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s", datefmt="%H:%M:%S"))
    root_logger.addHandler(console_handler)

    logging.getLogger("nlab_modbus").info("Starting nlab-modbus-gui v%s", __version__)

    window = ModbusMainWindow(log_handler=log_handler, initial_baudrate=args.baudrate, scan_id_range=range(args.start_id, args.end_id + 1))
    window.show()

    app.setWindowIcon(QIcon(str(_find_icon())))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

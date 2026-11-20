from __future__ import annotations

import argparse
import ctypes
import logging
import sys
from pathlib import Path

from PySide6.QtCore import QEventLoop, Qt
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox, QSplashScreen

from nlab_modbus import __version__
from nlab_modbus.gui import theme
from nlab_modbus.gui.controller.main_controller import PRODUCT_NAME, ModbusMainWindow
from nlab_modbus.gui.model.log_handler import QtLogHandler

_SCRIPT_DIR = Path(__file__).resolve().parent


def _find_resource(filename: str) -> Path | None:
    candidates = [
        _SCRIPT_DIR / "resources" / filename,
        _SCRIPT_DIR / "nlab_modbus" / "gui" / "resources" / filename,
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _find_icon() -> Path:
    p = _find_resource("ewt.ico")
    if p is None:
        raise FileNotFoundError("Application icon ewt.ico not found")
    return p


def _parse_arguments(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description=f"{PRODUCT_NAME} GUI")
    parser.add_argument(
        "--baudrate", type=int, default=None,
        metavar="BAUD",
        help="Fixed serial baud rate for scans and connections (default: auto, tries 9600 then 115200)",
    )
    parser.add_argument(
        "--start-id", type=int, default=1,
        metavar="ID",
        help="First Modbus device ID to probe during scan (default: 1)",
    )
    parser.add_argument(
        "--end-id", type=int, default=16,
        metavar="ID",
        help="Last Modbus device ID to probe during scan (default: 16)",
    )
    args, qt_args = parser.parse_known_args(argv)
    if not 1 <= args.start_id <= args.end_id <= 254:
        parser.error("scan IDs must satisfy 1 <= --start-id <= --end-id <= 254")
    return args, qt_args


def main() -> int:
    """Create the QApplication, open the main window, and run the event loop.

    Sets a Windows AppUserModelID so the taskbar icon matches the window icon
    rather than the generic Python launcher icon.
    """
    args, qt_args = _parse_arguments(sys.argv[1:])

    if sys.platform == "win32":
        myappid = f"EWT.Modbus.Monitor.{__version__}"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    app = QApplication([sys.argv[0], *qt_args])
    app.setApplicationName(PRODUCT_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("EWT")
    app.setOrganizationDomain("ewt.local")
    app.setWindowIcon(QIcon(str(_find_icon())))
    applied = theme.apply_application_theme(app)

    log_handler = QtLogHandler()
    root_logger = logging.getLogger("nlab_modbus")
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(log_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    # Keep detailed discovery diagnostics in the in-app log without flooding
    # the launch terminal with expected per-address scan misses.
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s", datefmt="%H:%M:%S"))
    root_logger.addHandler(console_handler)

    logging.getLogger("nlab_modbus").info("Starting nlab-modbus-gui v%s (%s theme)", __version__, applied.mode.value)

    splash = _show_splash()
    _update_splash(splash, "Preparing the main window…")
    try:
        window = ModbusMainWindow(
            log_handler=log_handler,
            initial_baudrate=args.baudrate,
            scan_id_range=range(args.start_id, args.end_id + 1),
        )
        _finish_startup(splash, window)
    except Exception as exc:
        splash.close()
        logging.getLogger("nlab_modbus").exception("Application startup failed")
        QMessageBox.critical(None, "Startup failed", str(exc))
        return 1

    return app.exec()


def _finish_startup(splash: QSplashScreen, window: ModbusMainWindow) -> None:
    """Reveal the connection window before dismissing its startup splash."""
    window.show()
    QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
    splash.finish(window)


def _show_splash() -> QSplashScreen:
    return _create_splash(PRODUCT_NAME, "Launching application")


def _create_splash(title: str, message: str) -> QSplashScreen:
    """EWT lockup splash in the active theme (same design as nlab-community)."""
    splash = QSplashScreen(theme.splash_pixmap(title), Qt.WindowType.WindowStaysOnTopHint)
    splash.setWindowTitle(title)
    splash.show()
    _update_splash(splash, message)
    return splash


def _update_splash(splash: QSplashScreen, message: str) -> None:
    splash.showMessage(
        message,
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
        QColor(theme.colors().text_muted),
    )
    QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)


if __name__ == "__main__":
    raise SystemExit(main())

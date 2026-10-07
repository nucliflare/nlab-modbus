from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from nlab_modbus.gui import main_app  # noqa: E402


class SplashTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_splash_matches_nlab_community_dimensions_and_progress_style(self) -> None:
        splash = main_app._show_splash()
        self.addCleanup(splash.close)

        self.assertTrue(splash.isVisible())
        self.assertEqual(splash.message(), "Launching application")
        self.assertEqual(splash.pixmap().size().width(), 520)
        self.assertEqual(splash.pixmap().size().height(), 320)

        main_app._update_splash(splash, "Scanning for devices…")
        self.assertEqual(splash.message(), "Scanning for devices…")

    def test_startup_reveals_window_before_closing_splash(self) -> None:
        splash = main_app._show_splash()
        window = QWidget()
        self.addCleanup(splash.close)
        self.addCleanup(window.close)

        self.assertFalse(window.isVisible())
        main_app._finish_startup(splash, window)

        self.assertTrue(window.isVisible())
        self.assertFalse(splash.isVisible())


if __name__ == "__main__":
    unittest.main()

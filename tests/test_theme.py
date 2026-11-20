"""EWT design-system themes: brand values, contrast, stylesheet, selection, assets."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, QtMsgType, qInstallMessageHandler  # noqa: E402
from PySide6.QtGui import QColor, QFontInfo  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from nlab_modbus.gui import theme  # noqa: E402
from nlab_modbus.gui.theme import ThemeColors, ThemeMode, contrast_ratio  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EWT_THEMES = (theme.LIGHT, theme.DARK)


def text_pairs(c: ThemeColors) -> list[tuple[str, str, str]]:
    """Text that must stay readable: WCAG AA 4.5:1."""
    return [
        ("text/bg", c.text, c.bg), ("text/raised", c.text, c.bg_raised), ("text/tint", c.text, c.bg_tint),
        ("muted/bg", c.text_muted, c.bg), ("muted/raised", c.text_muted, c.bg_raised),
        ("accent/bg", c.text_accent, c.bg),
        ("connect", c.on_action, c.action), ("connect hover", c.on_action, c.action_hover),
        ("connect pressed", c.on_action, c.action_pressed),
        ("disconnect", c.on_stop, c.stop_bg), ("disconnect pressed", c.on_stop, c.stop_pressed),
        ("tooltip", c.tooltip_text, c.tooltip_bg), ("log", c.console_text, c.console_bg),
        ("plot axis", c.plot_foreground, c.plot_background),
        ("warning", c.status_warning, c.bg), ("error", c.status_error, c.bg),
    ]


def reduced_pairs(c: ThemeColors) -> list[tuple[str, str, str]]:
    """Disabled text, control borders and plot lines: 3:1."""
    pairs = [
        ("disabled/bg", c.text_disabled, c.bg), ("disabled/raised", c.text_disabled, c.bg_raised),
        ("control border", c.line_strong, c.bg), ("focus", c.focus, c.bg),
        ("connect disabled", c.action_disabled_text, c.action_disabled_bg),
        ("disconnect disabled", c.stop_disabled_text, c.stop_disabled_bg),
    ]
    return pairs + [(f"series {i}", color, c.plot_background) for i, color in enumerate(c.series)]


class TokenTests(unittest.TestCase):
    def test_brand_values_match_the_design_system(self):
        # Owner-set screen values of the CMYK masters; never adjust them here.
        self.assertEqual(
            (theme.BRAND_INK, theme.BRAND_BLUE, theme.BRAND_CYAN, theme.BRAND_WHITE),
            ("#00000C", "#0472B9", "#00B9D4", "#FFFFFF"),
        )
        # Blue is the action colour; cyan is never text on white, blue too dark as text on ink.
        self.assertEqual((theme.LIGHT.action, theme.DARK.action), (theme.BRAND_BLUE, theme.BRAND_BLUE))
        self.assertEqual((theme.LIGHT.text_accent, theme.DARK.text_accent), (theme.BRAND_BLUE, theme.BRAND_CYAN))
        self.assertEqual((theme.LIGHT.bg, theme.DARK.bg), (theme.BRAND_WHITE, theme.BRAND_INK))

    def test_text_meets_wcag_aa(self):
        for c in EWT_THEMES:
            for label, foreground, background in text_pairs(c):
                with self.subTest(theme=c.mode.value, pair=label):
                    self.assertGreaterEqual(contrast_ratio(foreground, background), 4.5)

    def test_disabled_text_controls_and_plot_lines_keep_three_to_one(self):
        for c in EWT_THEMES:
            for label, foreground, background in reduced_pairs(c):
                with self.subTest(theme=c.mode.value, pair=label):
                    self.assertGreaterEqual(contrast_ratio(foreground, background), 3.0)

    def test_series_never_rely_on_cyan_and_blue_together(self):
        for c in EWT_THEMES:
            with self.subTest(theme=c.mode.value):
                self.assertFalse({theme.BRAND_BLUE, theme.BRAND_CYAN} <= set(c.series))
                self.assertEqual(len(set(c.series)), len(c.series))

    def test_classic_keeps_the_original_colours(self):
        c = theme.CLASSIC
        self.assertEqual((c.action, c.on_action, c.stop_bg, c.on_stop), ("#D4EDDA", "#155724", "#F8D7DA", "#721C24"))
        self.assertEqual(c.plot_border, "#808080")

    def test_ui_files_carry_no_inline_colours(self):
        for ui_file in (ROOT / "src/nlab_modbus/gui/view").glob("*.ui"):
            with self.subTest(file=ui_file.name):
                self.assertNotIn("styleSheet", ui_file.read_text(encoding="utf-8"))


class ApplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        theme.apply_application_theme(self.app, ThemeMode.LIGHT)

    def test_stylesheets_parse_without_qt_warnings(self):
        warnings: list[str] = []

        def handler(kind, _context, message):
            if kind != QtMsgType.QtDebugMsg:
                warnings.append(message)

        previous = qInstallMessageHandler(handler)
        try:
            for mode in ThemeMode:
                theme.apply_application_theme(self.app, mode)
                from PySide6.QtWidgets import QComboBox, QPushButton, QTableView

                for widget in (QPushButton("x"), QComboBox(), QTableView()):
                    widget.show()
                    self.app.processEvents()
                    widget.close()
        finally:
            qInstallMessageHandler(previous)
        self.assertEqual([w for w in warnings if "style" in w.lower()], [])

    def test_ewt_theme_uses_roboto_and_the_brand_palette(self):
        applied = theme.apply_application_theme(self.app, ThemeMode.DARK)

        self.assertIs(theme.colors(), applied)
        self.assertEqual(QFontInfo(self.app.font()).family(), "Roboto")
        self.assertEqual(self.app.palette().window().color(), QColor(theme.BRAND_INK))

    def test_theme_choice_persists_and_environment_overrides_it(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = QSettings(str(Path(folder) / "settings.ini"), QSettings.Format.IniFormat)
            with patch.object(theme, "_settings", return_value=settings):
                self.assertEqual(theme.startup_theme_mode(), ThemeMode.LIGHT)
                theme.save_theme_mode(ThemeMode.DARK)
                self.assertEqual(theme.startup_theme_mode(), ThemeMode.DARK)
                with patch.dict(os.environ, {theme.THEME_ENVIRONMENT_VARIABLE: "classic"}):
                    self.assertEqual(theme.startup_theme_mode(), ThemeMode.CLASSIC)

    def test_splash_draws_the_lockup_on_the_theme_ground(self):
        for c, ground in ((theme.LIGHT, theme.BRAND_WHITE), (theme.DARK, theme.BRAND_INK)):
            with self.subTest(theme=c.mode.value):
                image = theme.splash_pixmap("nuclearLab Modbus Monitor", theme=c).toImage()
                self.assertEqual(image.pixelColor(5, 300), QColor(ground))
                self.assertEqual(image.pixelColor(5, 1), QColor(theme.BRAND_CYAN))  # top rule
                lockup = {image.pixelColor(x, y).name() for x in range(200, 320, 4) for y in range(40, 200, 4)}
                self.assertGreater(len(lockup), 3, "lockup not drawn")

    def test_dark_lockup_only_recolours_the_wordmark(self):
        brand = ROOT / "src/nlab_modbus/gui/resources/brand"
        light = (brand / "ewt-vertical-color-on-light.svg").read_text(encoding="utf-8")
        dark = (brand / "ewt-vertical-color-on-dark.svg").read_text(encoding="utf-8")
        self.assertEqual(dark, light.replace('fill="#00000C"', 'fill="#FFFFFF"'))


if __name__ == "__main__":
    unittest.main()

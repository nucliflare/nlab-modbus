"""Application appearance: EWT light (default), EWT dark and Classic themes.

All interface colours, the typeface and the stylesheet live here, so widgets
ask for roles (``connect``/``disconnect`` buttons, protected rows, plot
canvas) instead of literal colours. The theme is chosen at start-up
(View > Theme, applied at the next launch; ``NLAB_THEME`` overrides it once).

Token values follow the Eastern Wall Technologies design system (Claude
design-system artifact, tokens.json v1, 2026-11-14) and match nlab-community's
theme so both EWT desktop apps look alike:

* Brand colours are the owner-set screen values of the CMYK masters.
* Light/dark neutrals are the design system's (marked "derived" there).
* Hover/pressed/disabled shades, the Disconnect red, status colours and the
  plot series palettes are not defined by the design system; they are derived
  here and checked for WCAG contrast in ``tests/test_theme.py``.
* The design system's typeface (HK Grotesk) is for documents; the GUI uses
  Roboto, like nlab-community, because its shorter ascenders suit dense tables.

Classic reproduces the pre-redesign interface (platform style and font, the
original pastel Connect/Disconnect buttons and plot colours).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from PySide6.QtCore import QRectF, QSettings, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImageReader, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

log = logging.getLogger(__name__)

RESOURCES = Path(__file__).resolve().parent / "resources"
SETTINGS_KEY = "appearance/theme"
THEME_ENVIRONMENT_VARIABLE = "NLAB_THEME"
ROLE_PROPERTY = "nlabRole"  # dynamic property read by the stylesheet


class ThemeMode(StrEnum):
    LIGHT = "light"
    DARK = "dark"
    CLASSIC = "classic"


THEME_LABELS = {
    ThemeMode.LIGHT: "EWT light",
    ThemeMode.DARK: "EWT dark",
    ThemeMode.CLASSIC: "Classic (system style)",
}
DEFAULT_THEME = ThemeMode.LIGHT

# --- Brand (design system: owner-set, never adjust) ---------------------------
BRAND_INK = "#00000C"
BRAND_BLUE = "#0472B9"
BRAND_CYAN = "#00B9D4"
BRAND_WHITE = "#FFFFFF"


@dataclass(frozen=True)
class ThemeColors:
    """Every colour role the interface uses, for one theme."""

    mode: ThemeMode
    dark: bool
    bg: str
    bg_raised: str
    bg_tint: str
    bg_pressed: str
    line: str
    line_strong: str
    text: str
    text_muted: str
    text_accent: str
    text_disabled: str
    focus: str
    action: str
    action_hover: str
    action_pressed: str
    action_disabled_bg: str
    action_disabled_text: str
    on_action: str
    stop_bg: str
    stop_pressed: str
    stop_disabled_bg: str
    stop_disabled_text: str
    on_stop: str
    status_warning: str
    status_error: str
    tooltip_bg: str
    tooltip_text: str
    console_bg: str
    console_text: str
    plot_background: str
    plot_foreground: str
    plot_border: str
    series: tuple[str, ...]  # plot line colours, in assignment order
    icon_suffix: str


LIGHT = ThemeColors(
    mode=ThemeMode.LIGHT,
    dark=False,
    bg=BRAND_WHITE,
    bg_raised="#F2F4F6",
    bg_tint="#E6F7FA",
    bg_pressed="#E4E8EC",
    line="#C9D0D6",
    line_strong="#77838F",
    text=BRAND_INK,
    text_muted="#4A5561",
    text_accent=BRAND_BLUE,
    text_disabled="#77838F",
    focus=BRAND_BLUE,
    action=BRAND_BLUE,
    action_hover="#03619D",
    action_pressed="#024F80",
    action_disabled_bg="#D7E6F2",
    action_disabled_text="#4F6F88",
    on_action=BRAND_WHITE,
    stop_bg="#C0262D",
    stop_pressed="#9A1C22",
    stop_disabled_bg="#F6DCDD",
    stop_disabled_text="#8E4A4D",
    on_stop=BRAND_WHITE,
    status_warning="#A14E00",
    status_error="#C0262D",
    tooltip_bg=BRAND_INK,
    tooltip_text="#EEF1F4",
    console_bg=BRAND_INK,
    console_text="#EEF1F4",
    plot_background=BRAND_WHITE,
    plot_foreground="#4A5561",
    plot_border="#C9D0D6",
    # Brand blue first; no cyan (too close to blue and below 3:1 on white).
    series=("#0472B9", "#C2410C", "#00795A", BRAND_INK, "#A3336D", "#6B4FBB", "#8A6100", "#0E7C86"),
    icon_suffix="",
)

DARK = ThemeColors(
    mode=ThemeMode.DARK,
    dark=True,
    bg=BRAND_INK,
    bg_raised="#0D1218",
    bg_tint="#062530",
    bg_pressed="#1A232C",
    line="#26313B",
    line_strong="#5C6875",
    text="#EEF1F4",
    text_muted="#9AA5B1",
    text_accent=BRAND_CYAN,  # blue is only 4.1:1 on ink
    text_disabled="#6B7784",
    focus=BRAND_CYAN,
    action=BRAND_BLUE,
    action_hover="#03619D",
    action_pressed="#024F80",
    action_disabled_bg="#0B2A40",
    action_disabled_text="#8FB3CF",
    on_action=BRAND_WHITE,
    stop_bg="#C0262D",
    stop_pressed="#9A1C22",
    stop_disabled_bg="#3A1416",
    stop_disabled_text="#D8999B",
    on_stop=BRAND_WHITE,
    status_warning="#F0A23B",
    status_error="#FF6B6E",
    tooltip_bg="#26313B",
    tooltip_text="#EEF1F4",
    console_bg=BRAND_INK,
    console_text="#EEF1F4",
    plot_background=BRAND_INK,
    plot_foreground="#9AA5B1",
    plot_border="#26313B",
    # Brand cyan first; no brand blue (too close to cyan).
    series=("#00B9D4", "#F0A23B", "#4CC38A", "#EEF1F4", "#F08AC6", "#B4A0FF", "#E8D44D", "#6FA8FF"),
    icon_suffix="-dark",
)

# Pre-redesign values: Classic installs no palette, only the role colours.
CLASSIC = ThemeColors(
    mode=ThemeMode.CLASSIC,
    dark=False,
    bg="#FFFFFF",
    bg_raised="#F0F0F0",
    bg_tint="#C8D7E6",
    bg_pressed="#E0E0E0",
    line="#C8C8C8",
    line_strong="#808080",
    text="#000000",
    text_muted="#505050",
    text_accent="#0066CC",
    text_disabled="#A0A0A0",
    focus="#0078D4",
    action="#D4EDDA",
    action_hover="#C3E6CB",
    action_pressed="#B1DFBB",
    action_disabled_bg="#E9F5EC",
    action_disabled_text="#7A9A80",
    on_action="#155724",
    stop_bg="#F8D7DA",
    stop_pressed="#F1B0B7",
    stop_disabled_bg="#FBEBEC",
    stop_disabled_text="#A0767A",
    on_stop="#721C24",
    status_warning="#B54708",
    status_error="#B00020",
    tooltip_bg="#FFFFDC",
    tooltip_text="#000000",
    console_bg="#FFFFFF",
    console_text="#000000",
    plot_background="#FFFFFF",
    plot_foreground="#969696",
    plot_border="#808080",
    series=("#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#000000", "#F0E442"),
    icon_suffix="",
)

THEMES = {theme.mode: theme for theme in (LIGHT, DARK, CLASSIC)}
_active: ThemeColors = LIGHT


def colors() -> ThemeColors:
    """The active theme's colours (light until a theme is applied)."""
    return _active


# --- Selection ------------------------------------------------------------------


def _settings() -> QSettings:
    return QSettings("EWT", "nlab-modbus-gui")


def saved_theme_mode() -> ThemeMode:
    try:
        return ThemeMode(str(_settings().value(SETTINGS_KEY, DEFAULT_THEME.value)))
    except ValueError:
        return DEFAULT_THEME


def save_theme_mode(mode: ThemeMode) -> None:
    _settings().setValue(SETTINGS_KEY, mode.value)


def startup_theme_mode() -> ThemeMode:
    """The theme for this launch: ``NLAB_THEME`` if set, else the saved choice."""
    override = os.environ.get(THEME_ENVIRONMENT_VARIABLE, "").strip().lower()
    if override:
        try:
            return ThemeMode(override)
        except ValueError:
            log.warning("Ignoring unknown %s=%s", THEME_ENVIRONMENT_VARIABLE, override)
    return saved_theme_mode()


# --- Typography -------------------------------------------------------------------

FONT_FAMILY = "Roboto"
FONT_FALLBACKS = ("Segoe UI", "Helvetica Neue", "Arial", "sans-serif")
APP_FONT_POINT_SIZE = 9.0
_FONT_FILES = ("Roboto-Regular.ttf", "Roboto-Medium.ttf", "Roboto-Bold.ttf")
_fonts_loaded: bool | None = None


def register_fonts() -> bool:
    """Register the bundled Roboto faces once; False when none could be loaded."""
    global _fonts_loaded
    if _fonts_loaded is None:
        loaded = False
        for name in _FONT_FILES:
            if QFontDatabase.addApplicationFont(str(RESOURCES / "fonts" / name)) >= 0:
                loaded = True
            else:
                log.warning("Could not load bundled font %s", name)
        _fonts_loaded = loaded
    return _fonts_loaded


def application_font() -> QFont:
    font = QFont()
    font.setFamilies([FONT_FAMILY, *FONT_FALLBACKS])
    font.setPointSizeF(APP_FONT_POINT_SIZE)
    return font


# --- Palette and stylesheet -------------------------------------------------------


def application_palette(theme: ThemeColors) -> QPalette:
    palette = QPalette()
    roles = QPalette.ColorRole
    if theme.dark:
        bevels = {roles.Light: "#2A3540", roles.Midlight: "#1A232C", roles.Mid: theme.line,
                  roles.Dark: "#05080C", roles.Shadow: "#000000"}
    else:
        bevels = {roles.Light: BRAND_WHITE, roles.Midlight: theme.bg_raised, roles.Mid: theme.line,
                  roles.Dark: theme.line_strong, roles.Shadow: theme.text_muted}
    values = {
        roles.Window: theme.bg, roles.WindowText: theme.text, roles.Base: theme.bg,
        roles.AlternateBase: theme.bg_raised, roles.Text: theme.text, roles.PlaceholderText: theme.text_muted,
        roles.Button: theme.bg, roles.ButtonText: theme.text, roles.BrightText: BRAND_WHITE,
        roles.Highlight: theme.action, roles.HighlightedText: theme.on_action,
        roles.Link: theme.text_accent, roles.LinkVisited: theme.text_accent,
        roles.ToolTipBase: theme.tooltip_bg, roles.ToolTipText: theme.tooltip_text, **bevels,
    }
    for role, value in values.items():
        palette.setColor(role, QColor(value))
    disabled = QPalette.ColorGroup.Disabled
    for role in (roles.WindowText, roles.Text, roles.ButtonText):
        palette.setColor(disabled, role, QColor(theme.text_disabled))
    palette.setColor(disabled, roles.Base, QColor(theme.bg_raised))
    palette.setColor(disabled, roles.Button, QColor(theme.bg_raised))
    return palette


def _role_button_rules(c: ThemeColors) -> str:
    bold = "font-weight: 700;" if c.mode is not ThemeMode.CLASSIC else ""
    return f"""
QPushButton[nlabRole="connect"] {{
    background: {c.action}; color: {c.on_action}; border: 1px solid {c.action}; {bold}
}}
QPushButton[nlabRole="connect"]:hover {{ background: {c.action_hover}; border-color: {c.action_hover}; }}
QPushButton[nlabRole="connect"]:pressed {{ background: {c.action_pressed}; border-color: {c.action_pressed}; }}
QPushButton[nlabRole="connect"]:disabled {{
    background: {c.action_disabled_bg}; color: {c.action_disabled_text}; border-color: {c.action_disabled_bg};
}}
QPushButton[nlabRole="disconnect"] {{
    background: {c.stop_bg}; color: {c.on_stop}; border: 1px solid {c.stop_bg}; {bold}
}}
QPushButton[nlabRole="disconnect"]:hover, QPushButton[nlabRole="disconnect"]:pressed {{
    background: {c.stop_pressed}; border-color: {c.stop_pressed};
}}
QPushButton[nlabRole="disconnect"]:disabled {{
    background: {c.stop_disabled_bg}; color: {c.stop_disabled_text}; border-color: {c.stop_disabled_bg};
}}
"""


def _icon_url(name: str) -> str:
    return (RESOURCES / "icons" / name).as_posix()


def _svg_images_supported() -> bool:
    return b"svg" in QImageReader.supportedImageFormats()


def application_stylesheet(theme: ThemeColors | None = None, *, svg_icons: bool = True) -> str:
    """Stylesheet for a theme; Classic only colours the Connect/Disconnect roles."""
    c = theme or LIGHT
    if c.mode is ThemeMode.CLASSIC:
        return _role_button_rules(c)
    icon = c.icon_suffix
    arrows = ""
    if svg_icons:
        arrows = f"""
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right; width: 20px; border: none; }}
QComboBox::down-arrow {{ image: url({_icon_url(f"chevron-down{icon}.svg")}); width: 12px; height: 12px; }}
QComboBox::down-arrow:disabled {{ image: url({_icon_url(f"chevron-down{icon}-disabled.svg")}); }}
QAbstractSpinBox {{ padding-right: 18px; }}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
    subcontrol-origin: border; width: 16px; border: none; border-left: 1px solid {c.line}; background: transparent;
}}
QAbstractSpinBox::up-button {{ subcontrol-position: top right; border-top-right-radius: 4px; }}
QAbstractSpinBox::down-button {{ subcontrol-position: bottom right; border-bottom-right-radius: 4px; }}
QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {{ background: {c.bg_raised}; }}
QAbstractSpinBox::up-arrow {{ image: url({_icon_url(f"chevron-up{icon}.svg")}); width: 10px; height: 10px; }}
QAbstractSpinBox::down-arrow {{ image: url({_icon_url(f"chevron-down{icon}.svg")}); width: 10px; height: 10px; }}
QAbstractSpinBox::up-arrow:disabled, QAbstractSpinBox::up-arrow:off {{
    image: url({_icon_url(f"chevron-up{icon}-disabled.svg")});
}}
QAbstractSpinBox::down-arrow:disabled, QAbstractSpinBox::down-arrow:off {{
    image: url({_icon_url(f"chevron-down{icon}-disabled.svg")});
}}
QCheckBox::indicator:checked, QTableView::indicator:checked {{ image: url({_icon_url("check.svg")}); }}
"""
    return f"""
/* Eastern Wall Technologies {c.mode.value} theme, generated by nlab_modbus.gui.theme */
QToolTip {{ background: {c.tooltip_bg}; color: {c.tooltip_text}; border: none; border-radius: 4px; padding: 6px 8px; }}

QMenuBar {{ background: {c.bg_raised}; border-bottom: 1px solid {c.line}; padding: 2px 4px; }}
QMenuBar::item {{ background: transparent; padding: 4px 10px; border-radius: 4px; }}
QMenuBar::item:selected {{ background: {c.bg_tint}; }}
QMenuBar::item:pressed {{ background: {c.bg_pressed}; }}
QMenu {{ background: {c.bg}; border: 1px solid {c.line}; padding: 4px; }}
QMenu::item {{ padding: 5px 24px 5px 26px; border-radius: 4px; }}
QMenu::item:selected {{ background: {c.bg_tint}; color: {c.text}; }}
QMenu::item:disabled {{ color: {c.text_disabled}; }}
QMenu::separator {{ height: 1px; background: {c.line}; margin: 4px 8px; }}
QMenu::indicator {{ width: 14px; height: 14px; left: 6px; }}

QStatusBar {{ background: {c.bg_raised}; border-top: 1px solid {c.line}; color: {c.text_muted}; }}
QStatusBar::item {{ border: none; }}
QMainWindow > QWidget#centralwidget {{ background: {c.bg_raised}; }}

QTabWidget::pane {{ border: 1px solid {c.line}; border-radius: 0; top: -1px; background: {c.bg}; }}
QTabBar::tab {{
    background: transparent; color: {c.text_muted}; font-weight: 500; border: none;
    border-bottom: 3px solid transparent; padding: 7px 14px 6px 14px; margin-right: 2px;
}}
QTabBar::tab:hover {{ color: {c.text}; background: {c.bg_pressed}; }}
QTabBar::tab:selected {{ color: {c.text}; background: {c.bg}; border-bottom-color: {c.action}; }}
QTabBar::tab:left {{ border-bottom: none; border-right: 3px solid transparent; padding: 14px 7px 14px 6px; margin: 0 0 2px 0; }}
QTabBar::tab:left:selected {{ border-right-color: {c.action}; }}

QGroupBox {{
    border: 1px solid {c.line}; border-radius: 8px; font-weight: 700;
    margin-top: 12px; padding: 10px 8px 8px 8px; background: {c.bg};
}}
QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; left: 10px; padding: 0 4px; color: {c.text}; }}
QGroupBox::title:disabled {{ color: {c.text_disabled}; }}

QPushButton {{
    background: {c.bg}; color: {c.text}; border: 1px solid {c.line_strong};
    border-radius: 8px; padding: 3px 12px; min-height: 18px;
}}
QPushButton:hover {{ background: {c.bg_raised}; }}
QPushButton:pressed {{ background: {c.bg_pressed}; }}
QPushButton:default {{ border: 2px solid {c.focus}; padding: 2px 11px; }}
QPushButton:disabled {{ background: {c.bg_raised}; color: {c.text_disabled}; border-color: {c.line}; }}
QPushButton:focus {{ outline: none; }}
{_role_button_rules(c)}
QLineEdit, QAbstractSpinBox, QComboBox {{
    background: {c.bg}; color: {c.text}; border: 1px solid {c.line_strong};
    border-radius: 4px; padding: 2px 6px; min-height: 18px;
    selection-background-color: {c.action}; selection-color: {c.on_action};
}}
QLineEdit:hover, QAbstractSpinBox:hover, QComboBox:hover {{ border-color: {c.text_muted}; }}
QLineEdit:focus, QAbstractSpinBox:focus, QComboBox:focus {{ border: 2px solid {c.focus}; padding: 1px 5px; }}
QLineEdit:disabled, QAbstractSpinBox:disabled, QComboBox:disabled {{
    background: {c.bg_raised}; color: {c.text_disabled}; border-color: {c.line};
}}
QLineEdit[readOnly="true"] {{ background: {c.bg_raised}; }}
QComboBox {{ padding-right: 20px; combobox-popup: 0; }}
QComboBox:focus {{ padding-right: 19px; }}
QComboBox QAbstractItemView {{
    background: {c.bg}; color: {c.text}; border: 1px solid {c.line}; outline: 0;
    selection-background-color: {c.bg_tint}; selection-color: {c.text};
}}
QComboBox QAbstractItemView::item {{ padding: 3px 6px; }}
QComboBox QAbstractItemView::item:selected {{ background: {c.bg_tint}; color: {c.text}; }}
{arrows}
QPlainTextEdit {{
    background: {c.console_bg}; color: {c.console_text}; border: 1px solid {c.line}; border-radius: 4px;
    selection-background-color: {c.action}; selection-color: {c.on_action};
}}

QCheckBox, QTableView::indicator {{ spacing: 6px; }}
QCheckBox::indicator, QTableView::indicator {{
    width: 12px; height: 12px; background: {c.bg}; border: 1px solid {c.line_strong}; border-radius: 3px;
}}
QCheckBox::indicator:hover, QTableView::indicator:hover {{ border-color: {c.focus}; }}
QCheckBox::indicator:checked, QTableView::indicator:checked {{ background: {c.action}; border-color: {c.action}; }}

QTableView {{
    background: {c.bg}; color: {c.text}; alternate-background-color: {c.bg_raised};
    border: 1px solid {c.line}; border-radius: 4px; gridline-color: {c.line};
    selection-background-color: {c.bg_tint}; selection-color: {c.text};
}}
QHeaderView::section {{
    background: {c.bg_raised}; color: {c.text_muted}; font-weight: 500;
    border: none; border-right: 1px solid {c.line}; border-bottom: 1px solid {c.line}; padding: 3px 4px;
}}
QTableCornerButton::section {{ background: {c.bg_raised}; border: none; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {c.line}; border-radius: 3px; min-height: 24px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {c.line}; border-radius: 3px; min-width: 24px; margin: 2px; }}
QScrollBar::handle:hover {{ background: {c.line_strong}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
QSplitter::handle {{ background: {c.bg_raised}; }}
"""


def set_role(widget: QWidget, role: str) -> None:
    """Tag a button ``connect`` or ``disconnect`` for the stylesheet."""
    widget.setProperty(ROLE_PROPERTY, role)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


def configure_plots(theme: ThemeColors) -> None:
    """Default pyqtgraph canvas and axis colours; call before creating plots."""
    import pyqtgraph as pg

    pg.setConfigOptions(background=theme.plot_background, foreground=theme.plot_foreground)


def apply_application_theme(app: QApplication, mode: ThemeMode | None = None) -> ThemeColors:
    """Activate a theme for this process; call once before building windows."""
    global _active
    theme = THEMES[mode or startup_theme_mode()]
    _active = theme
    configure_plots(theme)
    if theme.mode is ThemeMode.CLASSIC:
        app.setStyleSheet(application_stylesheet(theme))
        return theme
    app.setStyle("Fusion")
    app.setPalette(application_palette(theme))
    if register_fonts():
        app.setFont(application_font())
    app.setStyleSheet(application_stylesheet(theme, svg_icons=_svg_images_supported()))
    return theme


# --- Splash -----------------------------------------------------------------------


def splash_pixmap(title: str, width: int = 520, height: int = 320, theme: ThemeColors | None = None) -> QPixmap:
    """EWT colour lockup and product name on the theme's ground (white, or ink in dark)."""
    c = theme or colors()
    background, title_color = (BRAND_INK, DARK.text) if c.dark else (BRAND_WHITE, BRAND_INK)
    lockup = RESOURCES / "brand" / f"ewt-vertical-color-on-{'dark' if c.dark else 'light'}.svg"
    register_fonts()
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(background))
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        lockup_height = 170.0
        from PySide6.QtSvg import QSvgRenderer

        renderer = QSvgRenderer(str(lockup))
        if renderer.isValid():
            size = renderer.defaultSize()
            lockup_width = lockup_height * (size.width() / size.height() if size.height() else 1.0)
            renderer.render(painter, QRectF((width - lockup_width) / 2, 36, lockup_width, lockup_height))
        font = application_font()
        font.setPointSizeF(14)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor(title_color))
        painter.drawText(QRectF(0, 36 + lockup_height + 14, width, 28), Qt.AlignmentFlag.AlignCenter, title)
        painter.fillRect(0, 0, width, 4, QColor(BRAND_CYAN))
    finally:
        painter.end()
    return pixmap


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG 2 contrast ratio between two colours."""

    def luminance(value: str) -> float:
        color = QColor(value)
        channels = [
            part / 12.92 if part <= 0.04045 else ((part + 0.055) / 1.055) ** 2.4
            for part in (color.redF(), color.greenF(), color.blueF())
        ]
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    lighter, darker = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)

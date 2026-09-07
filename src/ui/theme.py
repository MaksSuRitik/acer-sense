"""Acer Sense Theme Management and Stylesheet Generator.

Supports Light, Dark, and System (auto-detecting) modes.
Provides color constants and global QSS for PyQt6.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication

from core.config import load_config, save_config


@dataclass(frozen=True)
class ThemePalette:
    name: str
    is_dark: bool
    bg_main: str
    bg_card: str
    bg_card_sub: str
    border: str
    border_sub: str
    text_primary: str
    text_secondary: str
    text_muted: str
    accent: str
    accent_dark: str
    accent_subtle: str
    tab_bg: str
    tab_hover: str
    tab_selected: str
    progress_track: str
    badge_bg: str
    badge_border: str


PALETTE_LIGHT = ThemePalette(
    name="light",
    is_dark=False,
    bg_main="#f2f5f3",
    bg_card="#ffffff",
    bg_card_sub="#f8faf9",
    border="#dde7e2",
    border_sub="#e5ede9",
    text_primary="#2c3833",
    text_secondary="#55665f",
    text_muted="#73857e",
    accent="#388e6a",
    accent_dark="#27684d",
    accent_subtle="#eef6f2",
    tab_bg="#f8faf8",
    tab_hover="#edf5f0",
    tab_selected="#f2f7f4",
    progress_track="#e4eee8",
    badge_bg="#eaf3ef",
    badge_border="#c8ddd6",
)

PALETTE_DARK = ThemePalette(
    name="dark",
    is_dark=True,
    bg_main="#151917",
    bg_card="#1e2421",
    bg_card_sub="#191f1c",
    border="#2b3630",
    border_sub="#232d27",
    text_primary="#e1ebe5",
    text_secondary="#9cb0a6",
    text_muted="#71857b",
    accent="#42b582",
    accent_dark="#2e875f",
    accent_subtle="#1f3329",
    tab_bg="#191f1c",
    tab_hover="#232c28",
    tab_selected="#202a24",
    progress_track="#27332c",
    badge_bg="#1d2e25",
    badge_border="#2f4d3e",
)


def detect_system_dark() -> bool:
    """Check if the desktop environment prefers dark theme."""
    # 1. Check Qt application styleHints (reliable on Qt 6.5+)
    app = QApplication.instance()
    if app:
        try:
            scheme = app.styleHints().colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                return True
            if scheme == Qt.ColorScheme.Light:
                return False
        except Exception:
            pass

    # 2. Check gsettings (GNOME / Cinnamon / Hyprland portal)
    if shutil.which("gsettings"):
        try:
            out = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                capture_output=True, text=True, timeout=1, check=False,
            ).stdout.strip().lower()
            if "dark" in out:
                return True
            if "light" in out or "default" in out:
                return False
        except Exception:
            pass

    # 3. Check GTK_THEME environment variable
    gtk_theme = os.environ.get("GTK_THEME", "").lower()
    if "dark" in gtk_theme:
        return True

    return False


def get_current_palette(mode: Optional[str] = None) -> ThemePalette:
    if not mode:
        config = load_config()
        mode = config.get("theme", "system")

    if mode == "dark":
        return PALETTE_DARK
    elif mode == "light":
        return PALETTE_LIGHT
    else:  # "system"
        return PALETTE_DARK if detect_system_dark() else PALETTE_LIGHT


def generate_qss(p: ThemePalette) -> str:
    return f"""
        QMainWindow, QWidget {{
            background: {p.bg_main};
            color: {p.text_primary};
            font-family: 'Inter', 'Noto Sans', 'Segoe UI', sans-serif;
        }}

        /* Tabs */
        QTabWidget::pane {{
            border: 0;
            border-top: 1px solid {p.border};
            background: {p.bg_main};
        }}
        QTabBar {{
            background: {p.tab_bg};
        }}
        QTabBar::tab {{
            background: {p.tab_bg};
            color: {p.text_secondary};
            min-width: 0;
            padding: 14px 22px 13px;
            margin: 0;
            font-size: 13px;
            font-weight: 600;
            border-bottom: 2.5px solid transparent;
        }}
        QTabBar::tab:selected {{
            color: {p.accent};
            border-bottom-color: {p.accent};
            font-weight: 700;
            background: {p.tab_selected};
        }}
        QTabBar::tab:hover:!selected {{
            color: {p.text_primary};
            background: {p.tab_hover};
        }}

        /* Scrollbars */
        QScrollArea {{
            border: 0;
            background: transparent;
        }}
        QScrollBar:vertical {{
            width: 7px;
            background: transparent;
            margin: 8px 2px;
        }}
        QScrollBar::handle:vertical {{
            min-height: 40px;
            background: {p.border};
            border-radius: 3px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {p.accent};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}

        /* Standard Buttons */
        QPushButton {{
            font-family: 'Inter', 'Noto Sans', 'Segoe UI', sans-serif;
        }}

        /* Labels */
        QLabel {{
            background: transparent;
        }}

        /* Dialogs */
        QDialog {{
            background: {p.bg_main};
            color: {p.text_primary};
        }}
        QTextEdit {{
            background: {p.bg_card};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 8px;
        }}
    """


class _ThemeManager(QObject):
    theme_changed = pyqtSignal(object)  # ThemePalette

    def __init__(self):
        super().__init__()
        self._palette = get_current_palette()

    @property
    def palette(self) -> ThemePalette:
        return self._palette

    def set_theme_mode(self, mode: str):
        save_config({"theme": mode})
        self._palette = get_current_palette(mode)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(generate_qss(self._palette))
        self.theme_changed.emit(self._palette)

    def apply_current(self):
        self._palette = get_current_palette()
        app = QApplication.instance()
        if app:
            app.setStyleSheet(generate_qss(self._palette))
        self.theme_changed.emit(self._palette)


theme_manager = _ThemeManager()

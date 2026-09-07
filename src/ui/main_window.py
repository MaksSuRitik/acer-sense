"""Acer Sense Main Window — native vector icons, theme awareness, matching official AcerSense."""
from __future__ import annotations

from pathlib import Path
import subprocess

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QMainWindow, QPushButton,
                              QTabWidget, QWidget)

from .icons import render_svg_pixmap
from .tab_checkup import CheckupTab
from .tab_home import HomeTab
from .tab_settings import SettingsTab
from .theme import ThemePalette, theme_manager


# ──────────────────────────────────────────────────────────────────────────────
# Круглая кнопка гарнитуры/микрофона (векторная иконка)
# ──────────────────────────────────────────────────────────────────────────────

class MicButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Микрофон: переключить звук (XF86Launch6)")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = theme_manager.palette
        hover = self.underMouse()
        pressed = self.isDown()

        # Background circle on hover
        if pressed:
            p.setBrush(QBrush(QColor(pal.accent_subtle)))
            p.setPen(QPen(QColor(pal.accent), 1.2))
            p.drawEllipse(QRectF(2, 2, 32, 32))
        elif hover:
            p.setBrush(QBrush(QColor(pal.tab_hover)))
            p.setPen(QPen(QColor(pal.border), 1.2))
            p.drawEllipse(QRectF(2, 2, 32, 32))
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(pal.border), 1.0))
            p.drawEllipse(QRectF(2, 2, 32, 32))

        # Render vector headset icon
        color = pal.accent if (hover or pressed) else pal.text_secondary
        pix = render_svg_pixmap("headset", color, 20)
        p.drawPixmap(8, 8, pix)


# ──────────────────────────────────────────────────────────────────────────────
# Круглая кнопка настроек (векторная шестерёнка из официального AcerSense)
# ──────────────────────────────────────────────────────────────────────────────

class SettingsButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Персональные настройки")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = theme_manager.palette
        hover = self.underMouse()
        pressed = self.isDown()

        # Background circle on hover
        if pressed:
            p.setBrush(QBrush(QColor(pal.accent_subtle)))
            p.setPen(QPen(QColor(pal.accent), 1.2))
            p.drawEllipse(QRectF(2, 2, 32, 32))
        elif hover:
            p.setBrush(QBrush(QColor(pal.tab_hover)))
            p.setPen(QPen(QColor(pal.border), 1.2))
            p.drawEllipse(QRectF(2, 2, 32, 32))
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(pal.border), 1.0))
            p.drawEllipse(QRectF(2, 2, 32, 32))

        # Render vector gear icon
        color = pal.accent if (hover or pressed) else pal.text_secondary
        pix = render_svg_pixmap("gear", color, 20)
        p.drawPixmap(8, 8, pix)


# ──────────────────────────────────────────────────────────────────────────────
# Главное окно MainWindow
# ──────────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Acer Sense")
        self.resize(1180, 720)
        self.setMinimumSize(820, 520)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(False)

        # ── Логотип Acer слева ──────────────────────────────────────────────
        logo_widget = QWidget()
        logo_layout = QHBoxLayout(logo_widget)
        logo_layout.setContentsMargins(18, 0, 16, 0)
        logo_layout.setSpacing(6)

        self.logo_brand = QLabel("acer")
        self.logo_brand.setStyleSheet(f"""
            color: {theme_manager.palette.accent};
            font-family: 'Inter', 'Arial', sans-serif;
            font-size: 20px;
            font-weight: 900;
            letter-spacing: -0.5px;
            background: transparent;
        """)

        self.logo_app = QLabel("SENSE")
        self.logo_app.setStyleSheet(f"""
            color: {theme_manager.palette.text_muted};
            font-family: 'Inter', 'Segoe UI', sans-serif;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 2.5px;
            padding-top: 5px;
            background: transparent;
        """)

        logo_layout.addWidget(self.logo_brand)
        logo_layout.addWidget(self.logo_app)

        # ── Кнопки действий справа (круглые векторные) ────────────────────────
        self.btn_mic = MicButton()
        self.btn_mic.clicked.connect(self._toggle_mic)

        self.btn_settings = SettingsButton()
        self.btn_settings.clicked.connect(self._open_quick_settings)

        right_widget = QWidget()
        right_layout = QHBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 16, 0)
        right_layout.setSpacing(8)
        right_layout.addWidget(self.btn_mic)
        right_layout.addWidget(self.btn_settings)

        self.tabs.setCornerWidget(logo_widget, Qt.Corner.TopLeftCorner)
        self.tabs.setCornerWidget(right_widget, Qt.Corner.TopRightCorner)

        # ── Вкладки без текстовых эмодзи (чистая типографика AcerSense) ───────
        self.home_tab = HomeTab()
        self.checkup_tab = CheckupTab()
        self.settings_tab = SettingsTab()

        self.tabs.addTab(self.home_tab, "Дом")
        self.tabs.addTab(self.checkup_tab, "Проверить")
        self.tabs.addTab(self.settings_tab, "Персональные настройки")
        self.setCentralWidget(self.tabs)

        theme_manager.theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self, pal: ThemePalette):
        self.logo_brand.setStyleSheet(f"""
            color: {pal.accent};
            font-family: 'Inter', 'Arial', sans-serif;
            font-size: 20px;
            font-weight: 900;
            letter-spacing: -0.5px;
            background: transparent;
        """)
        self.logo_app.setStyleSheet(f"""
            color: {pal.text_muted};
            font-family: 'Inter', 'Segoe UI', sans-serif;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 2.5px;
            padding-top: 5px;
            background: transparent;
        """)
        self.btn_mic.update()
        self.btn_settings.update()

    def _toggle_mic(self):
        dev_script = Path(__file__).resolve().parents[2] / "scripts" / "mic-sync.sh"
        user_script = Path.home() / ".config" / "hypr" / "mic-sync.sh"
        installed_script = Path("/usr/lib/acer-sense/scripts/mic-sync.sh")

        for s in (dev_script, user_script, installed_script):
            if s.exists():
                try:
                    txt = s.read_text(encoding="utf-8", errors="ignore")[:300]
                    if "cite:" in txt:
                        continue
                except OSError:
                    pass
                subprocess.Popen(["bash", str(s), "toggle"])
                break

    def _open_quick_settings(self):
        self.tabs.setCurrentWidget(self.settings_tab)

    def go_to_tab(self, name: str):
        mapping = {"home": self.home_tab, "checkup": self.checkup_tab,
                   "settings": self.settings_tab}
        widget = mapping.get(name)
        if widget:
            self.tabs.setCurrentWidget(widget)

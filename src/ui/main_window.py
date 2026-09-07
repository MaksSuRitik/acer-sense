"""Acer Sense Main Application Window with Dark/Light Theme Support and Minimal Icons."""
from __future__ import annotations

from pathlib import Path
import subprocess

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QMainWindow, QPushButton,
                              QTabWidget, QWidget)

from .tab_checkup import CheckupTab
from .tab_home import HomeTab
from .tab_settings import SettingsTab
from .theme import ThemePalette, theme_manager


# ──────────────────────────────────────────────────────────────────────────────
# Векторная кнопка микрофона с поддержкой тем
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

        if pressed:
            p.setBrush(QBrush(QColor(pal.accent_subtle)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(2, 2, 32, 32), 16, 16)
        elif hover:
            p.setBrush(QBrush(QColor(pal.tab_hover)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(2, 2, 32, 32), 16, 16)

        color = QColor(pal.accent if hover else pal.text_secondary)
        pen = QPen(color, 2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        # Капсюль микрофона
        p.drawRoundedRect(QRectF(14, 8, 8, 13), 4, 4)

        # Дуга вокруг микрофона
        arc_path = QPainterPath()
        arc_path.arcMoveTo(QRectF(10.5, 12, 15, 12), 0)
        arc_path.arcTo(QRectF(10.5, 12, 15, 12), 0, -180)
        p.drawPath(arc_path)

        # Ножка и основание
        p.drawLine(QPointF(18, 24), QPointF(18, 28))
        p.drawLine(QPointF(13, 28), QPointF(23, 28))


# ──────────────────────────────────────────────────────────────────────────────
# Векторная кнопка шестерёнки настроек (чёткая, адаптивная к темам)
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

        if pressed:
            p.setBrush(QBrush(QColor(pal.accent_subtle)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(2, 2, 32, 32), 16, 16)
        elif hover:
            p.setBrush(QBrush(QColor(pal.tab_hover)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(2, 2, 32, 32), 16, 16)

        cx, cy = 18.0, 18.0
        color = QColor(pal.accent if hover else pal.text_secondary)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(color))

        # 8 зубцов шестерёнки
        for i in range(8):
            p.save()
            p.translate(cx, cy)
            p.rotate(i * 45)
            p.drawRoundedRect(QRectF(-2.2, -9.5, 4.4, 4.0), 1.2, 1.2)
            p.restore()

        # Обод шестерёнки
        p.drawEllipse(QPointF(cx, cy), 7.2, 7.2)

        # Центральное отверстие
        hole_color = QColor(pal.accent_subtle if pressed else (pal.tab_hover if hover else pal.bg_main))
        p.setBrush(QBrush(hole_color))
        p.drawEllipse(QPointF(cx, cy), 3.2, 3.2)


# ──────────────────────────────────────────────────────────────────────────────
# MainWindow
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
            font-size: 19px;
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
            padding-top: 4px;
            background: transparent;
        """)

        logo_layout.addWidget(self.logo_brand)
        logo_layout.addWidget(self.logo_app)

        # ── Кнопки действий справа ───────────────────────────────────────────
        self.btn_mic = MicButton()
        self.btn_mic.clicked.connect(self._toggle_mic)

        self.btn_settings = SettingsButton()
        self.btn_settings.clicked.connect(self._open_quick_settings)

        right_widget = QWidget()
        right_layout = QHBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 16, 0)
        right_layout.setSpacing(6)
        right_layout.addWidget(self.btn_mic)
        right_layout.addWidget(self.btn_settings)

        self.tabs.setCornerWidget(logo_widget, Qt.Corner.TopLeftCorner)
        self.tabs.setCornerWidget(right_widget, Qt.Corner.TopRightCorner)

        # ── Вкладки с минималистичными иконками ──────────────────────────────
        self.home_tab = HomeTab()
        self.checkup_tab = CheckupTab()
        self.settings_tab = SettingsTab()

        self.tabs.addTab(self.home_tab, "⚡  Дом")
        self.tabs.addTab(self.checkup_tab, "🩺  Проверить")
        self.tabs.addTab(self.settings_tab, "⚙️  Персональные настройки")
        self.setCentralWidget(self.tabs)

        theme_manager.theme_changed.connect(self._on_theme_changed)

    def _on_theme_changed(self, pal: ThemePalette):
        self.logo_brand.setStyleSheet(f"""
            color: {pal.accent};
            font-family: 'Inter', 'Arial', sans-serif;
            font-size: 19px;
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
            padding-top: 4px;
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

from pathlib import Path
import subprocess

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QMainWindow, QPushButton,
                              QTabWidget, QWidget)

from .tab_checkup import CheckupTab
from .tab_home import HomeTab
from .tab_settings import SettingsTab

ACCENT      = "#388e6a"
ACCENT_DARK = "#256349"
BG_MAIN     = "#f2f5f3"
BORDER_COL  = "#dbe5e0"


# ──────────────────────────────────────────────────────────────────────────────
# Векторная кнопка микрофона (чистая геометрия без эмодзи)
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

        hover = self.underMouse()
        pressed = self.isDown()

        # Фоновый круг
        bg_col = QColor("#d6eae0" if pressed else ("#e5f1ea" if hover else "transparent"))
        p.setBrush(QBrush(bg_col))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(2, 2, 32, 32), 16, 16)

        # Капсюль микрофона
        p.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(QColor("#3d4b45" if not hover else ACCENT_DARK), 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)

        # Капсюль (скруглённый прямоугольник по центру)
        p.drawRoundedRect(QRectF(14, 9, 8, 12), 4, 4)

        # Дуга вокруг микрофона
        arc_path = QPainterPath()
        arc_path.arcMoveTo(QRectF(11, 13, 14, 12), 0)
        arc_path.arcTo(QRectF(11, 13, 14, 12), 0, -180)
        p.drawPath(arc_path)

        # Ножка и основание
        p.drawLine(QPointF(18, 25), QPointF(18, 28))
        p.drawLine(QPointF(14, 28), QPointF(22, 28))


# ──────────────────────────────────────────────────────────────────────────────
# Векторная кнопка шестерёнки настроек (без эмодзи)
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

        hover = self.underMouse()
        pressed = self.isDown()

        bg_col = QColor("#d6eae0" if pressed else ("#e5f1ea" if hover else "transparent"))
        p.setBrush(QBrush(bg_col))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(2, 2, 32, 32), 16, 16)

        # Шестерёнка
        p.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(QColor("#3d4b45" if not hover else ACCENT_DARK), 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)

        cx, cy = 18.0, 18.0
        r_inner = 3.5
        r_outer = 7.5

        # Центральный круг
        p.drawEllipse(QPointF(cx, cy), r_inner, r_inner)

        # 6 зубцов шестерёнки
        for i in range(6):
            p.save()
            p.translate(cx, cy)
            p.rotate(i * 60)
            p.drawLine(QPointF(0, -r_inner - 1), QPointF(0, -r_outer - 1))
            p.restore()


# ──────────────────────────────────────────────────────────────────────────────
# MainWindow
# ──────────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Acer Sense")
        self.resize(1280, 760)
        self.setMinimumSize(960, 620)
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background: {BG_MAIN};
                color: #38423d;
                font-family: 'Inter', 'Noto Sans', 'Segoe UI', sans-serif;
            }}
            QTabWidget::pane {{
                border: 0;
                border-top: 1px solid {BORDER_COL};
                background: {BG_MAIN};
            }}
            QTabBar {{
                background: #f8faf8;
            }}
            QTabBar::tab {{
                background: #f8faf8;
                color: #63736c;
                min-width: 0;
                padding: 14px 20px 13px;
                margin: 0;
                font-size: 13px;
                font-weight: 500;
                border-bottom: 2.5px solid transparent;
            }}
            QTabBar::tab:selected {{
                color: {ACCENT_DARK};
                border-bottom-color: {ACCENT};
                font-weight: 700;
                background: #f2f7f4;
            }}
            QTabBar::tab:hover:!selected {{
                color: #242e29;
                background: #edf5f0;
            }}
            QScrollBar:vertical {{
                width: 7px;
                background: transparent;
                margin: 8px 2px;
            }}
            QScrollBar::handle:vertical {{
                min-height: 40px;
                background: #b5d9c7;
                border-radius: 3px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(False)

        # ── Логотип Acer слева ──────────────────────────────────────────────
        logo_widget = QWidget()
        logo_layout = QHBoxLayout(logo_widget)
        logo_layout.setContentsMargins(18, 0, 16, 0)
        logo_layout.setSpacing(6)

        logo_brand = QLabel("acer")
        logo_brand.setStyleSheet(f"""
            color: {ACCENT};
            font-family: 'Inter', 'Arial', sans-serif;
            font-size: 19px;
            font-weight: 900;
            letter-spacing: -0.5px;
            background: transparent;
        """)

        logo_app = QLabel("SENSE")
        logo_app.setStyleSheet("""
            color: #798c84;
            font-family: 'Inter', 'Segoe UI', sans-serif;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 2.5px;
            padding-top: 4px;
            background: transparent;
        """)

        logo_layout.addWidget(logo_brand)
        logo_layout.addWidget(logo_app)

        # ── Кнопки действий справа (строгие векторные) ───────────────────────
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

        # ── Вкладки ────────────────────────────────────────────────────────
        self.home_tab = HomeTab()
        self.checkup_tab = CheckupTab()
        self.settings_tab = SettingsTab()

        self.tabs.addTab(self.home_tab, "Дом")
        self.tabs.addTab(self.checkup_tab, "Проверить")
        self.tabs.addTab(self.settings_tab, "Персональные настройки")
        self.setCentralWidget(self.tabs)

    # ── Хэндлеры ───────────────────────────────────────────────────────────

    def _toggle_mic(self):
        """Вызвать mic-sync.sh toggle с автоматическим выбором рабочего пути."""
        dev_script = Path(__file__).resolve().parents[2] / "scripts" / "mic-sync.sh"
        user_script = Path.home() / ".config" / "hypr" / "mic-sync.sh"
        installed_script = Path("/usr/lib/acer-sense/scripts/mic-sync.sh")

        for s in (dev_script, user_script, installed_script):
            if s.exists():
                try:
                    # Проверяем, нет ли в скрипте артефактов [cite:]
                    txt = s.read_text(encoding="utf-8", errors="ignore")[:300]
                    if "cite:" in txt:
                        continue
                except OSError:
                    pass
                subprocess.Popen(["bash", str(s), "toggle"])
                break

    def _open_quick_settings(self):
        """Переключить на вкладку Персональные настройки."""
        self.tabs.setCurrentWidget(self.settings_tab)

    def go_to_tab(self, name: str):
        mapping = {"home": self.home_tab, "checkup": self.checkup_tab,
                   "settings": self.settings_tab}
        widget = mapping.get(name)
        if widget:
            self.tabs.setCurrentWidget(widget)

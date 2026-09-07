from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (QButtonGroup, QFrame, QGridLayout, QHBoxLayout,
                             QLabel, QPushButton, QVBoxLayout, QWidget)

from core.power import get_power_profile, set_power_profile
from core.sensors import get_battery_info, get_cpu_temp, get_cpu_usage, get_ram_info


ACCENT = "#4ba781"


class RingProgress(QWidget):
    def __init__(self, size: int = 74, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.value = 0

    def set_value(self, value: float):
        self.value = max(0, min(100, value))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(8, 8, self.width() - 16, self.height() - 16)
        pen = QPen(QColor("#dcebe4"), 6)
        painter.setPen(pen)
        painter.drawArc(rect, 0, 360 * 16)
        pen.setColor(QColor(ACCENT))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, 90 * 16, int(-self.value * 3.6 * 16))
        painter.setPen(QColor("#535b57"))
        painter.setFont(QFont("Inter", 10, QFont.Weight.DemiBold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{int(self.value)}%")


class WelcomeIllustration(QFrame):
    """CSS-only illustration so the package stays self-contained and lightweight."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(205)
        self.setMaximumHeight(240)
        self.setStyleSheet("""
            QFrame { border: 0; border-radius: 22px;
              background: qradialgradient(cx:0.5, cy:0.3, radius:0.85, stop:0 #fbfffc, stop:1 #eaf8f1); }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 15, 28, 15)
        layout.addStretch(1)
        scene = QLabel("◜     ◯     ♫\n\n          ▱\n      ━━━━━━━━━")
        scene.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scene.setStyleSheet("background: transparent; color: #61b894; font-size: 25px; font-weight: 300; line-height: 1.2;")
        layout.addWidget(scene)
        layout.addStretch(1)


class ProfileButton(QPushButton):
    def __init__(self, icon: str, label: str, parent=None):
        super().__init__(f"{icon}\n{label}", parent)
        self.setCheckable(True)
        self.setMinimumSize(118, 76)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QPushButton {{ border: 0; border-radius: 13px; color: #5f6863; background: transparent;
                            font-size: 12px; font-weight: 600; padding: 6px 5px; }}
            QPushButton:checked {{ color: white; background: {ACCENT}; }}
            QPushButton:hover:!checked {{ background: #f0f7f3; color: #357d61; }}
        """)


class HomeTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(104, 28, 104, 44)
        layout.setSpacing(52)

        left = QVBoxLayout()
        left.setSpacing(12)
        left.setAlignment(Qt.AlignmentFlag.AlignTop)
        welcome = QLabel("Вас приветствует AcerSense")
        welcome.setStyleSheet("font-size: 21px; font-weight: 700; color: #343b37;")
        left.addWidget(welcome)
        registration = QLabel("Зарегистрировать устройство.                                      ›")
        registration.setFixedHeight(30)
        registration.setStyleSheet("background: #ffffff; border-radius: 5px; color: #6f7873; font-size: 12px; padding: 0 9px;")
        left.addWidget(registration)
        left.addWidget(WelcomeIllustration())
        modes_title = QLabel("Режим использования системы                                  ⓘ")
        modes_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        modes_title.setStyleSheet("font-size: 12px; color: #79837e; margin-top: 8px;")
        left.addWidget(modes_title)
        mode_panel = QFrame()
        mode_panel.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #e5ebe7; border-radius: 15px; }")
        mode_layout = QHBoxLayout(mode_panel)
        mode_layout.setContentsMargins(6, 5, 6, 5)
        mode_layout.setSpacing(1)
        self.profile_group = QButtonGroup(self)
        profile = get_power_profile()
        for icon, label, mode in (("◴", "Бесшумно", "power-saver"),
                                  ("◔", "Обычный", "balanced"),
                                  ("◕", "Производительность", "performance")):
            button = ProfileButton(icon, label)
            button.setChecked(profile == mode)
            button.clicked.connect(lambda checked, value=mode: set_power_profile(value))
            self.profile_group.addButton(button)
            mode_layout.addWidget(button)
        left.addWidget(mode_panel)
        mode_hint = QLabel("Для работы, например, с Microsoft Office.")
        mode_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mode_hint.setStyleSheet("font-size: 11px; color: #919a95;")
        left.addWidget(mode_hint)
        left.addStretch(1)

        right = QVBoxLayout()
        right.setSpacing(14)
        right.setAlignment(Qt.AlignmentFlag.AlignTop)
        right.addWidget(self._make_insight_card())
        right.addWidget(self._make_stats_card())
        right.addWidget(self._make_battery_card())
        right.addStretch(1)

        left_holder = QWidget()
        left_holder.setLayout(left)
        left_holder.setMinimumWidth(510)
        left_holder.setMaximumWidth(610)
        right_holder = QWidget()
        right_holder.setLayout(right)
        right_holder.setFixedWidth(300)
        layout.addWidget(left_holder, 1)
        layout.addWidget(right_holder)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(2000)
        self.update_stats()

    def _card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #e4e9e6; border-radius: 16px; }")
        return card

    def _make_insight_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        banner = QFrame()
        banner.setFixedHeight(75)
        banner.setStyleSheet("QFrame { border: 0; border-radius: 10px; background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #77ceb0, stop:1 #bcebd9); }")
        banner_layout = QVBoxLayout(banner)
        banner_title = QLabel("Acer Sense для Linux")
        banner_title.setStyleSheet("color: #ffffff; background: transparent; border: 0; font-size: 16px; font-weight: 700;")
        banner_note = QLabel("Настройте ноутбук под свой ритм работы")
        banner_note.setStyleSheet("color: #effff7; background: transparent; border: 0; font-size: 11px;")
        banner_layout.addWidget(banner_title)
        banner_layout.addWidget(banner_note)
        layout.addWidget(banner)
        caption = QLabel("Мониторинг, режимы питания и защита аккумулятора — в одном месте.")
        caption.setWordWrap(True)
        caption.setStyleSheet("font-size: 11px; color: #67716c; border: 0; padding: 1px 2px 0;")
        layout.addWidget(caption)
        return card

    def _make_stats_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 12)
        title = QLabel("Обзор рабочих параметров")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #646b67; border: 0;")
        layout.addWidget(title)
        grid = QGridLayout()
        grid.setHorizontalSpacing(5)
        for column, name in enumerate(("ОЗУ", "ЦП", "Система")):
            label = QLabel(name)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("font-size: 10px; color: #78827d; border: 0;")
            grid.addWidget(label, 0, column)
        self.ram_ring = RingProgress(66)
        self.cpu_ring = RingProgress(66)
        grid.addWidget(self.ram_ring, 1, 0, Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(self.cpu_ring, 1, 1, Qt.AlignmentFlag.AlignCenter)
        self.temp_value = QLabel("—°C")
        self.temp_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.temp_value.setStyleSheet("font-size: 19px; font-weight: 700; color: #575f5a; border: 0;")
        grid.addWidget(self.temp_value, 1, 2)
        layout.addLayout(grid)
        return card

    def _make_battery_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 11, 12, 12)
        title = QLabel("Состояние аккумулятора")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #646b67; border: 0;")
        self.battery_value = QLabel("▰  —")
        self.battery_value.setStyleSheet(f"font-size: 27px; font-weight: 700; color: {ACCENT}; border: 0; margin-top: 8px;")
        self.battery_note = QLabel("Информация обновляется автоматически")
        self.battery_note.setStyleSheet("font-size: 10px; color: #7f8984; border: 0;")
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background: #dcebe4; border: 0; margin: 8px 0 5px;")
        more = QLabel("Информация о состоянии аккумулятора  ›")
        more.setStyleSheet(f"font-size: 11px; color: {ACCENT}; font-weight: 600; border: 0;")
        layout.addWidget(title)
        layout.addWidget(self.battery_value)
        layout.addWidget(self.battery_note)
        layout.addWidget(line)
        layout.addWidget(more)
        return card

    def update_stats(self):
        self.cpu_ring.set_value(get_cpu_usage())
        self.ram_ring.set_value(get_ram_info()["percent"])
        temperature = get_cpu_temp()
        self.temp_value.setText(f"{temperature}°C" if temperature else "—°C")
        battery = get_battery_info()
        if battery["percent"] is None:
            self.battery_value.setText("▱  Недоступен")
            self.battery_note.setText("Аккумулятор не обнаружен")
        else:
            icon = "▰" if battery["plugged"] else "▱"
            self.battery_value.setText(f"{icon}  {battery['percent']}%")
            self.battery_note.setText("Питание подключено" if battery["plugged"] else "Питание от аккумулятора")

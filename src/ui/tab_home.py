from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPainterPath, QBrush
from PyQt6.QtWidgets import (QButtonGroup, QFrame, QGridLayout, QHBoxLayout,
                              QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from core.power import get_power_profile, set_power_profile
from core.sensors import (get_battery_info, get_cpu_temp, get_cpu_usage,
                           get_gpu_temp, get_ram_info)
from ui.details_dialogs import BatteryInfoDialog

ACCENT      = "#388e6a"
ACCENT_DARK = "#27684d"
TEXT_DARK   = "#2c3833"
TEXT_MUTED  = "#73857e"
BG_CARD     = "#ffffff"

_PROFILE_MODES = [
    ("power-saver",  "Бесшумно",         "Энергосбережение"),
    ("balanced",     "Обычный",           "Оптимальный баланс"),
    ("performance",  "Производительность","Максимум мощности"),
]

_PROFILE_HINTS = {
    "power-saver": "Ограничивает частоты ЦП и снижает шум вентиляторов. Идеально для работы от батареи, чтения и звонков.",
    "balanced":    "Автоматически регулирует производительность под текущие задачи: работа с документами, браузинг, видео.",
    "performance": "Максимальная вычислительная мощность и активное охлаждение. Рекомендуется для игр, компиляции и рендеринга.",
}


class RingProgress(QWidget):
    def __init__(self, size: int = 64, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.value = 0.0
        self.label = ""

    def set_value(self, value: float, label: str = ""):
        self.value = max(0.0, min(100.0, value))
        self.label = label
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(6, 6, self.width() - 12, self.height() - 12)

        # Фоновый трек
        p.setPen(QPen(QColor("#e4eee8"), 5))
        p.drawArc(r, 0, 360 * 16)

        # Активная дуга
        if self.value > 0:
            fill_pen = QPen(QColor(ACCENT), 5)
            fill_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(fill_pen)
            p.drawArc(r, 90 * 16, int(-self.value * 3.6 * 16))

        # Значение в центре
        p.setPen(QColor(TEXT_DARK))
        p.setFont(QFont("Inter", 9, QFont.Weight.DemiBold))
        text = self.label if self.label else f"{int(self.value)}%"
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, text)


class ProfileButton(QPushButton):
    def __init__(self, mode: str, label: str, subtitle: str, parent=None):
        super().__init__(parent)
        self._mode = mode
        self._label = label
        self._subtitle = subtitle
        self.setCheckable(True)
        self.setMinimumSize(90, 72)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        active = self.isChecked()
        hover = self.underMouse()

        bg_rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
        if active:
            bg_color = QColor(ACCENT)
            border_color = QColor(ACCENT_DARK)
        elif hover:
            bg_color = QColor("#f2f8f5")
            border_color = QColor("#b9decb")
        else:
            bg_color = QColor("#ffffff")
            border_color = QColor("#dbe5e0")

        p.setBrush(QBrush(bg_color))
        p.setPen(QPen(border_color, 1.5))
        p.drawRoundedRect(bg_rect, 12, 12)

        icon_pen = QPen(QColor("#ffffff") if active else QColor(ACCENT), 2)
        icon_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        icon_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(icon_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        cx = w / 2.0
        cy = 22.0

        if self._mode == "power-saver":
            path = QPainterPath()
            path.moveTo(cx - 7, cy + 5)
            path.quadTo(cx - 7, cy - 7, cx + 5, cy - 7)
            path.quadTo(cx + 5, cy + 5, cx - 7, cy + 5)
            path.moveTo(cx - 5, cy + 3)
            path.lineTo(cx + 1, cy - 3)
            p.drawPath(path)
        elif self._mode == "balanced":
            p.drawLine(QPointF(cx - 8, cy - 4), QPointF(cx + 8, cy - 4))
            p.drawLine(QPointF(cx - 8, cy + 4), QPointF(cx + 8, cy + 4))
            p.setBrush(QBrush(QColor("#ffffff") if active else QColor(ACCENT)))
            p.drawEllipse(QPointF(cx - 2, cy - 4), 2.5, 2.5)
            p.drawEllipse(QPointF(cx + 3, cy + 4), 2.5, 2.5)
        elif self._mode == "performance":
            path = QPainterPath()
            path.moveTo(cx - 7, cy + 4)
            path.arcTo(QRectF(cx - 8, cy - 8, 16, 16), 210, -240)
            p.drawPath(path)
            p.drawLine(QPointF(cx, cy), QPointF(cx + 4, cy - 4))

        p.setFont(QFont("Inter", 11, QFont.Weight.Bold if active else QFont.Weight.DemiBold))
        p.setPen(QColor("#ffffff") if active else QColor(TEXT_DARK))
        label_rect = QRectF(4, cy + 12, w - 8, 18)
        p.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, self._label)

        p.setFont(QFont("Inter", 8, QFont.Weight.Normal))
        p.setPen(QColor("#e4f7ee") if active else QColor(TEXT_MUTED))
        sub_rect = QRectF(4, cy + 30, w - 8, 14)
        p.drawText(sub_rect, Qt.AlignmentFlag.AlignCenter, self._subtitle)


class HomeTab(QWidget):
    def __init__(self):
        super().__init__()
        self._gpu_available: bool | None = None

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # Скролл-контейнер для адаптации под любые разрешения и тайлинг
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: 0; background: transparent; }")

        content = QWidget()
        root = QHBoxLayout(content)
        root.setContentsMargins(20, 16, 20, 20)
        root.setSpacing(16)

        # ── Левая колонка ──────────────────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(14)
        left.setAlignment(Qt.AlignmentFlag.AlignTop)

        welcome_box = QVBoxLayout()
        welcome_box.setSpacing(2)
        welcome_title = QLabel("Управление системой")
        welcome_title.setStyleSheet("font-size: 20px; font-weight: 700; color: #222d28;")
        welcome_sub = QLabel("Режимы энергопотребления и аппаратный контроль Acer")
        welcome_sub.setStyleSheet("font-size: 11px; color: #73857e;")
        welcome_box.addWidget(welcome_title)
        welcome_box.addWidget(welcome_sub)
        left.addLayout(welcome_box)

        # Карточка режимов питания
        profiles_card = QFrame()
        profiles_card.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1px solid #dde7e2;
                border-radius: 16px;
            }
        """)
        pc_layout = QVBoxLayout(profiles_card)
        pc_layout.setContentsMargins(18, 16, 18, 16)
        pc_layout.setSpacing(12)

        sec_header = QHBoxLayout()
        sec_title = QLabel("Режим использования системы")
        sec_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #323d38; border: 0;")
        sec_shortcut = QLabel("Fn + F")
        sec_shortcut.setStyleSheet("font-size: 11px; font-weight: 700; color: #388e6a; background: #eef6f2; padding: 3px 8px; border-radius: 6px; border: 1px solid #c8e0d4;")
        sec_header.addWidget(sec_title)
        sec_header.addStretch()
        sec_header.addWidget(sec_shortcut)
        pc_layout.addLayout(sec_header)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.profile_group = QButtonGroup(self)
        self._profile_buttons: dict[str, ProfileButton] = {}
        curr_profile = get_power_profile()

        for mode, label, sub in _PROFILE_MODES:
            btn = ProfileButton(mode, label, sub)
            btn.setChecked(mode == curr_profile)
            btn.clicked.connect(lambda _, m=mode: self._on_profile_clicked(m))
            self.profile_group.addButton(btn)
            self._profile_buttons[mode] = btn
            btn_row.addWidget(btn)

        pc_layout.addLayout(btn_row)

        self.mode_hint_box = QFrame()
        self.mode_hint_box.setStyleSheet("background: #f7faf8; border: 1px solid #e1ebe6; border-radius: 10px;")
        hint_lo = QVBoxLayout(self.mode_hint_box)
        hint_lo.setContentsMargins(12, 10, 12, 10)
        self.mode_hint = QLabel(_PROFILE_HINTS.get(curr_profile, ""))
        self.mode_hint.setWordWrap(True)
        self.mode_hint.setStyleSheet("font-size: 11px; color: #586962; line-height: 1.4; border: 0; background: transparent;")
        hint_lo.addWidget(self.mode_hint)
        pc_layout.addWidget(self.mode_hint_box)

        left.addWidget(profiles_card)
        left.addStretch(1)

        # ── Правая колонка ─────────────────────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(14)
        right.setAlignment(Qt.AlignmentFlag.AlignTop)
        right.addWidget(self._make_stats_card())
        right.addWidget(self._make_battery_card())
        right.addStretch(1)

        left_w = QWidget()
        left_w.setLayout(left)
        left_w.setMinimumWidth(260)

        right_w = QWidget()
        right_w.setLayout(right)
        right_w.setFixedWidth(290)

        root.addWidget(left_w, 1)
        root.addWidget(right_w)

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(2000)
        self.update_stats()

    def _make_stats_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"background: {BG_CARD}; border: 1px solid #dde7e2; border-radius: 16px;")
        lo = QVBoxLayout(card)
        lo.setContentsMargins(16, 14, 16, 14)
        lo.setSpacing(10)

        title = QLabel("Обзор рабочих параметров")
        title.setStyleSheet("font-size: 13px; font-weight: 700; color: #323d38; border: 0;")
        lo.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)

        for col, name in enumerate(("ОЗУ", "ЦП", "Система")):
            lbl = QLabel(name)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #73857e; border: 0;")
            grid.addWidget(lbl, 0, col)

        self.ram_ring = RingProgress(60)
        self.cpu_ring = RingProgress(60)
        grid.addWidget(self.ram_ring, 1, 0, Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(self.cpu_ring, 1, 1, Qt.AlignmentFlag.AlignCenter)

        self.cpu_col_label = grid.itemAtPosition(0, 1).widget()

        self.temp_value = QLabel("—°C")
        self.temp_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.temp_value.setStyleSheet("font-size: 17px; font-weight: 700; color: #2e3b35; border: 0;")
        grid.addWidget(self.temp_value, 1, 2, Qt.AlignmentFlag.AlignCenter)

        lo.addLayout(grid)
        return card

    def _make_battery_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"background: {BG_CARD}; border: 1px solid #dde7e2; border-radius: 16px;")
        lo = QVBoxLayout(card)
        lo.setContentsMargins(16, 14, 16, 14)
        lo.setSpacing(8)

        title = QLabel("Состояние аккумулятора")
        title.setStyleSheet("font-size: 13px; font-weight: 700; color: #323d38; border: 0;")
        lo.addWidget(title)

        bat_row = QHBoxLayout()
        self.battery_pct = QLabel("—%")
        self.battery_pct.setStyleSheet(f"font-size: 26px; font-weight: 700; color: {ACCENT}; border: 0;")
        
        self.battery_status_lbl = QLabel("Питание от батареи")
        self.battery_status_lbl.setStyleSheet("font-size: 11px; color: #71827b; border: 0; padding-top: 6px;")
        
        bat_row.addWidget(self.battery_pct)
        bat_row.addSpacing(6)
        bat_row.addWidget(self.battery_status_lbl)
        bat_row.addStretch()
        lo.addLayout(bat_row)

        self.opt_badge = QFrame()
        self.opt_badge.setStyleSheet("background: #f0f7f4; border: 1px solid #c2e2d2; border-radius: 8px;")
        bl = QHBoxLayout(self.opt_badge)
        bl.setContentsMargins(8, 4, 8, 4)
        badge_text = QLabel("Оптимизированная зарядка (лимит 80%)")
        badge_text.setStyleSheet("font-size: 10px; color: #2e6d52; font-weight: 600; border: 0; background: transparent;")
        bl.addWidget(badge_text)
        lo.addWidget(self.opt_badge)

        self.btn_battery_details = QPushButton("Детальные сведения об аккумуляторе ›")
        self.btn_battery_details.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_battery_details.setStyleSheet(f"""
            QPushButton {{
                text-align: left; background: transparent; border: 0;
                color: {ACCENT}; font-size: 11px; font-weight: 600; padding: 4px 0;
            }}
            QPushButton:hover {{ color: {ACCENT_DARK}; text-decoration: underline; }}
        """)
        self.btn_battery_details.clicked.connect(self._open_battery_info)
        lo.addWidget(self.btn_battery_details)

        return card

    def _open_battery_info(self):
        dlg = BatteryInfoDialog(self)
        dlg.exec()

    def _on_profile_clicked(self, mode: str):
        set_power_profile(mode)
        self.mode_hint.setText(_PROFILE_HINTS.get(mode, ""))

    def update_stats(self):
        cpu = get_cpu_usage()
        self.cpu_ring.set_value(cpu)
        self.ram_ring.set_value(get_ram_info()["percent"])

        if self._gpu_available is None:
            self._gpu_available = get_gpu_temp() is not None

        temp = get_cpu_temp()
        if self._gpu_available:
            gpu_t = get_gpu_temp()
            self.cpu_col_label.setText("ЦП | GPU")
            if gpu_t is not None:
                self.temp_value.setText(f"{gpu_t}°C")
            else:
                self.temp_value.setText(f"{temp}°C" if temp else "—°C")
        else:
            self.cpu_col_label.setText("ЦП")
            self.temp_value.setText(f"{temp}°C" if temp else "—°C")

        bat = get_battery_info()
        if bat["percent"] is None:
            self.battery_pct.setText("—")
            self.battery_status_lbl.setText("Батарея не обнаружена")
            self.opt_badge.hide()
        else:
            self.battery_pct.setText(f"{bat['percent']}%")
            if bat["plugged"]:
                self.battery_status_lbl.setText("Подключено к сети")
            else:
                self.battery_status_lbl.setText("Работа от батареи")
            
            from core.config import load_config
            cfg = load_config()
            if cfg.get("charge_limit") == 80:
                self.opt_badge.show()
            else:
                self.opt_badge.hide()

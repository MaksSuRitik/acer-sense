"""Home tab — system profiles, live parameters (CPU/GPU separate temps), and battery status."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPainterPath, QBrush
from PyQt6.QtWidgets import (QButtonGroup, QFrame, QGridLayout, QHBoxLayout,
                              QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from core.power import get_power_profile, set_power_profile
from core.sensors import (get_battery_info, get_cpu_temp, get_cpu_usage,
                           get_gpu_temp, get_ram_info)
from ui.details_dialogs import BatteryInfoDialog
from ui.theme import ThemePalette, theme_manager

_PROFILE_MODES = [
    ("power-saver",  "🍃 Бесшумно",          "Энергосбережение"),
    ("balanced",     "⚖️ Обычный",            "Оптимальный баланс"),
    ("performance",  "🚀 Производительность", "Максимум мощности"),
]

_PROFILE_HINTS = {
    "power-saver": "Ограничивает частоты ЦП и снижает шум вентиляторов. Идеально для работы от батареи, чтения и звонков.",
    "balanced":    "Автоматически регулирует производительность под текущие задачи: работа с документами, браузинг, видео.",
    "performance": "Максимальная вычислительная мощность и активное охлаждение. Рекомендуется для игр, компиляции и рендеринга.",
}


# ─────────────────────────────────────────────────────────────────────────────
# Ring progress widget
# ─────────────────────────────────────────────────────────────────────────────

class RingProgress(QWidget):
    def __init__(self, size: int = 60, parent=None):
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
        pal = theme_manager.palette
        r = QRectF(5, 5, self.width() - 10, self.height() - 10)

        p.setPen(QPen(QColor(pal.progress_track), 4))
        p.drawArc(r, 0, 360 * 16)

        if self.value > 0:
            fill_pen = QPen(QColor(pal.accent), 4)
            fill_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(fill_pen)
            p.drawArc(r, 90 * 16, int(-self.value * 3.6 * 16))

        p.setPen(QColor(pal.text_primary))
        p.setFont(QFont("Inter", 8, QFont.Weight.DemiBold))
        text = self.label if self.label else f"{int(self.value)}%"
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, text)


# ─────────────────────────────────────────────────────────────────────────────
# Profile button
# ─────────────────────────────────────────────────────────────────────────────

class ProfileButton(QPushButton):
    def __init__(self, mode: str, label: str, subtitle: str, parent=None):
        super().__init__(parent)
        self._mode = mode
        self._label = label
        self._subtitle = subtitle
        self.setCheckable(True)
        self.setMinimumSize(92, 72)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = theme_manager.palette

        w = self.width()
        h = self.height()
        active = self.isChecked()
        hover  = self.underMouse()

        bg_rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
        if active:
            bg_color     = QColor(pal.accent)
            border_color = QColor(pal.accent_dark)
        elif hover:
            bg_color     = QColor(pal.tab_hover)
            border_color = QColor(pal.accent)
        else:
            bg_color     = QColor(pal.bg_card)
            border_color = QColor(pal.border)

        p.setBrush(QBrush(bg_color))
        p.setPen(QPen(border_color, 1.5))
        p.drawRoundedRect(bg_rect, 12, 12)

        # Draw label
        p.setFont(QFont("Inter", 9, QFont.Weight.Bold if active else QFont.Weight.DemiBold))
        p.setPen(QColor("#ffffff") if active else QColor(pal.text_primary))
        label_rect = QRectF(4, 18, w - 8, 20)
        p.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, self._label)

        # Draw subtitle
        p.setFont(QFont("Inter", 7, QFont.Weight.Normal))
        p.setPen(QColor("#d8f3e5") if active else QColor(pal.text_muted))
        sub_rect = QRectF(4, 40, w - 8, 16)
        p.drawText(sub_rect, Qt.AlignmentFlag.AlignCenter, self._subtitle)


# ─────────────────────────────────────────────────────────────────────────────
# Temp indicator widget
# ─────────────────────────────────────────────────────────────────────────────

class TempCell(QWidget):
    def __init__(self, heading: str, parent=None):
        super().__init__(parent)
        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(2)
        lo.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._head = QLabel(heading)
        self._head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._val = QLabel("—")
        self._val.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lo.addWidget(self._head)
        lo.addWidget(self._val)
        self.apply_theme(theme_manager.palette)

    def apply_theme(self, pal: ThemePalette):
        self._head.setStyleSheet(
            f"font-size: 10px; font-weight: 600; color: {pal.text_muted}; background: transparent; border: 0;"
        )
        self._val.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {pal.text_primary}; background: transparent; border: 0;"
        )

    def set_value(self, celsius: int | None):
        if celsius is None or celsius == 0:
            self._val.setText("—")
        else:
            self._val.setText(f"{celsius}°")


# ─────────────────────────────────────────────────────────────────────────────
# Main tab
# ─────────────────────────────────────────────────────────────────────────────

class HomeTab(QWidget):
    def __init__(self):
        super().__init__()
        self._gpu_available: bool | None = None

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: 0; background: transparent; }")

        content = QWidget()
        root = QHBoxLayout(content)
        root.setContentsMargins(24, 18, 24, 22)
        root.setSpacing(20)

        # ── Левая колонка ──────────────────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(14)
        left.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Page heading
        heading_box = QVBoxLayout()
        heading_box.setSpacing(3)
        self.h_title = QLabel("Управление системой")
        self.h_sub = QLabel("Режимы энергопотребления и аппаратный контроль Acer")
        heading_box.addWidget(self.h_title)
        heading_box.addWidget(self.h_sub)
        left.addLayout(heading_box)

        # Power profiles card
        self.profiles_card = QFrame()
        pc_layout = QVBoxLayout(self.profiles_card)
        pc_layout.setContentsMargins(18, 16, 18, 16)
        pc_layout.setSpacing(12)

        sec_header = QHBoxLayout()
        self.sec_title = QLabel("⚡  Режим использования системы")
        self.fn_badge = QLabel("Fn + F")
        sec_header.addWidget(self.sec_title)
        sec_header.addStretch()
        sec_header.addWidget(self.fn_badge)
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

        self.hint_frame = QFrame()
        hint_lo = QVBoxLayout(self.hint_frame)
        hint_lo.setContentsMargins(12, 9, 12, 9)
        self.mode_hint = QLabel(_PROFILE_HINTS.get(curr_profile, ""))
        self.mode_hint.setWordWrap(True)
        hint_lo.addWidget(self.mode_hint)
        pc_layout.addWidget(self.hint_frame)

        left.addWidget(self.profiles_card)
        left.addStretch(1)

        # ── Правая колонка ─────────────────────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(14)
        right.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.stats_card = self._make_stats_card()
        self.battery_card = self._make_battery_card()
        right.addWidget(self.stats_card)
        right.addWidget(self.battery_card)
        right.addStretch(1)

        left_w = QWidget()
        left_w.setLayout(left)
        left_w.setMinimumWidth(340)

        right_w = QWidget()
        right_w.setLayout(right)
        right_w.setFixedWidth(300)

        root.addWidget(left_w, 1)
        root.addWidget(right_w)

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

        self.apply_theme(theme_manager.palette)
        theme_manager.theme_changed.connect(self.apply_theme)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(2000)
        self.update_stats()

    # ── Stats card ─────────────────────────────────────────────────────────

    def _make_stats_card(self) -> QFrame:
        card = QFrame()
        lo = QVBoxLayout(card)
        lo.setContentsMargins(16, 14, 16, 16)
        lo.setSpacing(12)

        self.stats_title = QLabel("📊  Рабочие параметры")
        lo.addWidget(self.stats_title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)

        self.ram_ring = RingProgress(54)
        self.cpu_ring = RingProgress(54)
        grid.addWidget(self.ram_ring, 1, 0, Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(self.cpu_ring, 1, 1, Qt.AlignmentFlag.AlignCenter)

        self.cpu_temp_cell = TempCell("ЦП °C")
        self.gpu_temp_cell = TempCell("GPU °C")
        grid.addWidget(self.cpu_temp_cell, 1, 2, Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(self.gpu_temp_cell, 1, 3, Qt.AlignmentFlag.AlignCenter)

        self.ram_label = QLabel("ОЗУ")
        self.cpu_label = QLabel("ЦП")
        self.ram_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cpu_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(self.ram_label, 0, 0)
        grid.addWidget(self.cpu_label, 0, 1)

        lo.addLayout(grid)
        return card

    # ── Battery card ───────────────────────────────────────────────────────

    def _make_battery_card(self) -> QFrame:
        card = QFrame()
        lo = QVBoxLayout(card)
        lo.setContentsMargins(16, 14, 16, 14)
        lo.setSpacing(8)

        self.bat_title = QLabel("🔋  Состояние аккумулятора")
        lo.addWidget(self.bat_title)

        bat_row = QHBoxLayout()
        self.battery_pct = QLabel("—%")
        self.battery_status_lbl = QLabel("")
        bat_row.addWidget(self.battery_pct)
        bat_row.addSpacing(8)
        bat_row.addWidget(self.battery_status_lbl)
        bat_row.addStretch()
        lo.addLayout(bat_row)

        self.opt_badge = QFrame()
        bl = QHBoxLayout(self.opt_badge)
        bl.setContentsMargins(8, 4, 8, 4)
        self.badge_text = QLabel("🛡️  Оптимизированная зарядка (80%)")
        bl.addWidget(self.badge_text)
        self.opt_badge.hide()
        lo.addWidget(self.opt_badge)

        self.btn_battery_details = QPushButton("Детальные сведения об аккумуляторе →")
        self.btn_battery_details.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_battery_details.clicked.connect(self._open_battery_info)
        lo.addWidget(self.btn_battery_details)

        return card

    # ── Theme Application ──────────────────────────────────────────────────

    def apply_theme(self, pal: ThemePalette):
        card_style = f"background: {pal.bg_card}; border: 1px solid {pal.border}; border-radius: 16px;"
        self.profiles_card.setStyleSheet(card_style)
        self.stats_card.setStyleSheet(card_style)
        self.battery_card.setStyleSheet(card_style)

        self.h_title.setStyleSheet(f"font-size: 19px; font-weight: 700; color: {pal.text_primary}; background: transparent;")
        self.h_sub.setStyleSheet(f"font-size: 11px; color: {pal.text_muted}; background: transparent;")
        self.sec_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {pal.text_primary}; border: 0; background: transparent;")
        self.stats_title.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {pal.text_primary}; border: 0; background: transparent;")
        self.bat_title.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {pal.text_primary}; border: 0; background: transparent;")

        self.fn_badge.setStyleSheet(
            f"font-size: 10px; font-weight: 700; color: {pal.accent}; background: {pal.accent_subtle};"
            f" padding: 2px 8px; border-radius: 5px; border: 1px solid {pal.badge_border};"
        )
        self.hint_frame.setStyleSheet(
            f"background: {pal.bg_card_sub}; border: 1px solid {pal.border_sub}; border-radius: 10px;"
        )
        self.mode_hint.setStyleSheet(f"font-size: 11px; color: {pal.text_secondary}; line-height: 1.4; border: 0; background: transparent;")

        self.battery_pct.setStyleSheet(f"font-size: 28px; font-weight: 700; color: {pal.accent}; border: 0; background: transparent;")
        self.battery_status_lbl.setStyleSheet(f"font-size: 10px; color: {pal.text_muted}; border: 0; background: transparent; padding-top: 8px;")

        self.opt_badge.setStyleSheet(
            f"background: {pal.accent_subtle}; border: 1px solid {pal.badge_border}; border-radius: 8px;"
        )
        self.badge_text.setStyleSheet(f"font-size: 10px; color: {pal.accent}; font-weight: 700; border: 0; background: transparent;")

        self.btn_battery_details.setStyleSheet(f"""
            QPushButton {{
                text-align: left; background: transparent; border: 0;
                color: {pal.accent}; font-size: 11px; font-weight: 600; padding: 4px 0;
            }}
            QPushButton:hover {{ color: {pal.accent_dark}; text-decoration: underline; }}
        """)

        lbl_style = f"font-size: 10px; font-weight: 600; color: {pal.text_muted}; border: 0; background: transparent;"
        self.ram_label.setStyleSheet(lbl_style)
        self.cpu_label.setStyleSheet(lbl_style)

        self.cpu_temp_cell.apply_theme(pal)
        self.gpu_temp_cell.apply_theme(pal)
        self.ram_ring.update()
        self.cpu_ring.update()
        for btn in self._profile_buttons.values():
            btn.update()

    # ── Event handlers ─────────────────────────────────────────────────────

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

        # CPU temperature
        cpu_t = get_cpu_temp()
        self.cpu_temp_cell.set_value(cpu_t if cpu_t else None)

        # GPU temperature
        if self._gpu_available is None:
            self._gpu_available = get_gpu_temp() is not None
        if self._gpu_available:
            gpu_t = get_gpu_temp()
            self.gpu_temp_cell.set_value(gpu_t)
        else:
            self.gpu_temp_cell.set_value(None)

        # Battery card
        bat = get_battery_info()
        if bat["percent"] is None:
            self.battery_pct.setText("—")
            self.battery_status_lbl.setText("Батарея не обнаружена")
            self.opt_badge.hide()
        else:
            self.battery_pct.setText(f"{bat['percent']}%")
            self.battery_status_lbl.setText(
                "Подключено к сети" if bat["plugged"] else "Работа от батареи"
            )
            from core.config import load_config
            cfg = load_config()
            if cfg.get("charge_limit") == 80:
                self.opt_badge.show()
            else:
                self.opt_badge.hide()

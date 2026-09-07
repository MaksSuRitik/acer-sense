"""Settings tab — professional redesign.

All radio options are wrapped in transparent card rows. No dark background strip.
No emoji anywhere. Clean typography and consistent spacing.
"""
from __future__ import annotations

import shutil
import subprocess

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QButtonGroup, QComboBox, QFrame, QHBoxLayout, QLabel,
                              QPushButton, QRadioButton, QScrollArea, QSlider,
                              QVBoxLayout, QWidget)

from core.config import load_config, save_config
from core.ec_control import set_charge_limit
from core.power import get_power_profile, set_power_profile
from ui.toggle import ToggleSwitch

ACCENT      = "#388e6a"
ACCENT_DARK = "#27684d"
_RADIO_SS = f"""
    QRadioButton {{
        color: #2e3b35;
        font-size: 12px;
        font-weight: 600;
        spacing: 8px;
        background: transparent;
    }}
    QRadioButton:focus {{
        outline: none;
        background: transparent;
    }}
    QRadioButton::indicator {{
        width: 16px;
        height: 16px;
        border: 1.5px solid #a8c8ba;
        border-radius: 8px;
        background: #ffffff;
    }}
    QRadioButton::indicator:checked {{
        border: 4px solid {ACCENT};
        background: #ffffff;
    }}
    QRadioButton::indicator:hover {{
        border-color: {ACCENT};
    }}
"""


class SettingsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.night_proc = None
        self._hyprland_available: bool | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(16)

        sidebar = self._build_sidebar()
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { border: 0; background: transparent; }")

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 8, 0)
        content_layout.setSpacing(14)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.power_card   = self._build_power_card()
        self.battery_card = self._build_battery_card()
        self.screen_card  = self._build_screen_card()
        self.hypr_card    = self._build_hyprland_card()

        content_layout.addWidget(self.power_card)
        content_layout.addWidget(self.battery_card)
        content_layout.addWidget(self.screen_card)
        content_layout.addWidget(self.hypr_card)
        content_layout.addStretch(1)

        self.scroll.setWidget(content)
        layout.addWidget(sidebar)
        layout.addWidget(self.scroll, 1)

    # ── Sidebar navigation ─────────────────────────────────────────────────

    def _build_sidebar(self) -> QFrame:
        panel = QFrame()
        panel.setFixedWidth(198)
        panel.setObjectName("navPanel")
        panel.setStyleSheet("""
            QFrame#navPanel {
                background: #ffffff;
                border: 1px solid #dde7e2;
                border-radius: 16px;
            }
        """)
        lo = QVBoxLayout(panel)
        lo.setContentsMargins(12, 14, 12, 14)
        lo.setSpacing(4)
        lo.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("Персональные настройки")
        title.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: #2e3b35; margin-bottom: 6px; background: transparent;"
        )
        lo.addWidget(title)

        self.nav_group = QButtonGroup(panel)
        self.btn_nav_power   = self._nav_button("Режим использования")
        self.btn_nav_battery = self._nav_button("Аккумулятор")
        self.btn_nav_screen  = self._nav_button("Экран и защита зрения")
        self.btn_nav_hypr    = self._nav_button("Горячие клавиши")

        self.btn_nav_power.clicked.connect(
            lambda: self._show_section(self.power_card, self.btn_nav_power))
        self.btn_nav_battery.clicked.connect(
            lambda: self._show_section(self.battery_card, self.btn_nav_battery))
        self.btn_nav_screen.clicked.connect(
            lambda: self._show_section(self.screen_card, self.btn_nav_screen))
        self.btn_nav_hypr.clicked.connect(
            lambda: self._show_section(self.hypr_card, self.btn_nav_hypr))

        self.btn_nav_power.setChecked(True)
        for btn in (self.btn_nav_power, self.btn_nav_battery,
                    self.btn_nav_screen, self.btn_nav_hypr):
            lo.addWidget(btn)
        lo.addStretch(1)
        return panel

    def _nav_button(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                border: 0; border-radius: 8px; padding: 9px 10px;
                text-align: left; font-size: 11px; font-weight: 500;
                color: #55665f; background: transparent;
            }}
            QPushButton:checked {{
                color: {ACCENT_DARK}; font-weight: 700; background: #eef6f2;
                border-left: 3px solid {ACCENT};
            }}
            QPushButton:hover:!checked {{ background: #f4f8f6; }}
        """)
        self.nav_group.addButton(btn)
        return btn

    # ── Card template ──────────────────────────────────────────────────────

    def _section_card(self, title: str, subtitle: str = "") -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame { background: #ffffff; border: 1px solid #dde7e2; border-radius: 16px; }
            QLabel { border: 0; background: transparent; }
        """)
        section = QVBoxLayout(card)
        section.setContentsMargins(20, 16, 20, 16)
        section.setSpacing(10)

        heading = QLabel(title)
        heading.setStyleSheet("font-size: 14px; color: #2e3b35; font-weight: 700;")
        rule = QFrame()
        rule.setFixedHeight(1)
        rule.setStyleSheet("background: #d8e5df; border: 0; margin: 0;")
        section.addWidget(heading)
        section.addWidget(rule)
        if subtitle:
            intro = QLabel(subtitle)
            intro.setWordWrap(True)
            intro.setStyleSheet("font-size: 11px; color: #6f7f78;")
            section.addWidget(intro)
        return card

    # ── Radio option — no dark strip ───────────────────────────────────────

    def _radio_option(self, parent: QFrame, title: str, description: str,
                      selected: bool, callback) -> QRadioButton:
        """Each option is an isolated card row with transparent radio button."""
        row_frame = QFrame()
        row_frame.setStyleSheet(
            "QFrame { background: #f8faf9; border: 1px solid #e5ede9;"
            " border-radius: 10px; margin: 1px 0; } "
            "QLabel { background: transparent; border: 0; }"
        )
        row_lo = QVBoxLayout(row_frame)
        row_lo.setContentsMargins(12, 10, 12, 10)
        row_lo.setSpacing(3)

        radio = QRadioButton(title)
        radio.setChecked(selected)
        radio.setCursor(Qt.CursorShape.PointingHandCursor)
        radio.setStyleSheet(_RADIO_SS)
        radio.clicked.connect(callback)

        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("font-size: 10px; color: #72827c; margin-left: 24px;")

        row_lo.addWidget(radio)
        row_lo.addWidget(desc_lbl)
        parent.layout().addWidget(row_frame)
        return radio

    # ── Section: power profiles ────────────────────────────────────────────

    def _build_power_card(self) -> QFrame:
        card = self._section_card(
            "Режим использования системы",
            "Режимы производительности и охлаждения. Переключение: Fn + F."
        )
        group = QButtonGroup(card)
        current = get_power_profile()
        for title, description, profile in (
            ("Бесшумно",
             "Ограничение частот и низкий уровень шума для работы от батареи.",
             "power-saver"),
            ("Обычный",
             "Сбалансированная работа для повседневных офисных задач.",
             "balanced"),
            ("Производительность",
             "Максимальная вычислительная мощность для игр и рендера.",
             "performance"),
        ):
            radio = self._radio_option(
                card, title, description,
                current == profile,
                lambda _, v=profile: set_power_profile(v),
            )
            group.addButton(radio)
        return card

    # ── Section: battery ───────────────────────────────────────────────────

    def _build_battery_card(self) -> QFrame:
        card = self._section_card(
            "Аккумулятор и зарядка",
            "Управление режимом зарядки для продления ресурса аккумулятора."
        )
        group = QButtonGroup(card)
        limit = self.config.get("charge_limit", 100)

        radio_80 = self._radio_option(
            card,
            "Оптимизированная зарядка",
            "(Рекомендуется) Аккумулятор заряжается до 80% для продления срока службы.",
            limit == 80,
            lambda: self._set_charge_limit(80),
        )
        radio_100 = self._radio_option(
            card,
            "Зарядка до полной ёмкости",
            "Зарядка до 100% для максимального времени автономной работы.",
            limit != 80,
            lambda: self._set_charge_limit(100),
        )
        group.addButton(radio_80)
        group.addButton(radio_100)

        btn_details = QPushButton("Детальные сведения об аккумуляторе →")
        btn_details.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_details.setStyleSheet(f"""
            QPushButton {{
                text-align: left; background: transparent; border: 0;
                color: {ACCENT}; font-size: 11px; font-weight: 600; padding: 4px 0;
            }}
            QPushButton:hover {{ color: {ACCENT_DARK}; text-decoration: underline; }}
        """)
        btn_details.clicked.connect(self._open_battery_info)
        card.layout().addWidget(btn_details)

        # Divider
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #dde7e2; border: 0; margin: 4px 0;")
        card.layout().addWidget(sep)

        # USB charging toggle
        usb_row = QHBoxLayout()
        usb_info = QVBoxLayout()
        usb_title = QLabel("Зарядка через USB при выключенном питании")
        usb_title.setStyleSheet("font-size: 12px; color: #2e3b35; font-weight: 600;")
        usb_text = QLabel(
            "Позволяет заряжать устройства от USB-порта даже при выключенном ноутбуке."
        )
        usb_text.setWordWrap(True)
        usb_text.setStyleSheet("font-size: 10px; color: #72827c;")
        usb_info.addWidget(usb_title)
        usb_info.addWidget(usb_text)
        usb_row.addLayout(usb_info, 1)

        usb_enabled = self.config.get("usb_charging", False)
        self.toggle_usb = ToggleSwitch()
        self.toggle_usb.setChecked(usb_enabled)
        self.toggle_usb.toggled.connect(self._toggle_usb_charging)
        usb_row.addWidget(self.toggle_usb)
        card.layout().addLayout(usb_row)

        return card

    # ── Section: screen ────────────────────────────────────────────────────

    def _build_screen_card(self) -> QFrame:
        card = self._section_card("Экран и защита зрения")

        top_row = QHBoxLayout()
        info_col = QVBoxLayout()
        bl_title = QLabel("Acer BluelightShield")
        bl_title.setStyleSheet("font-size: 13px; color: #2e3b35; font-weight: 700;")
        bl_desc = QLabel(
            "Снижает уровень синего излучения дисплея, снижая усталость глаз.\n"
            "Использует hyprsunset или wlsunset при наличии в Wayland-сессии."
        )
        bl_desc.setWordWrap(True)
        bl_desc.setStyleSheet("font-size: 10px; color: #72827c;")
        info_col.addWidget(bl_title)
        info_col.addWidget(bl_desc)
        top_row.addLayout(info_col, 1)

        self.toggle_bluelight = ToggleSwitch()
        self.toggle_bluelight.setChecked(self.config.get("bluelight_enabled", False))
        self.toggle_bluelight.toggled.connect(self.toggle_night_light)
        top_row.addWidget(self.toggle_bluelight)
        card.layout().addLayout(top_row)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #dde7e2; border: 0; margin: 4px 0;")
        card.layout().addWidget(sep)

        preset_title = QLabel("Пресеты фильтрации:")
        preset_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #44544d;")
        card.layout().addWidget(preset_title)

        presets_row = QHBoxLayout()
        presets_row.setSpacing(8)
        self.preset_group = QButtonGroup(card)

        presets_data = [
            ("Мягкий",    5500, "Легкая коррекция для дневной работы"),
            ("Баланс",    4500, "Оптимальный стандарт для вечера"),
            ("Усиленный", 3800, "Теплый оттенок при слабом освещении"),
            ("Ночной",    3000, "Глубокий янтарный для темноты"),
        ]

        current_temp = self.config.get("bluelight_temp", 4500)
        self._preset_buttons: dict[int, QPushButton] = {}

        for name, kelvin, desc in presets_data:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(f"{desc} ({kelvin} K)")
            btn.setFixedHeight(28)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: #f4f8f6; border: 1px solid #cce0d6;
                    border-radius: 14px; color: #4a5953;
                    font-size: 11px; font-weight: 600; padding: 0 12px;
                }}
                QPushButton:hover {{ background: #e8f3ee; border-color: #a8d5c0; }}
                QPushButton:checked {{
                    background: {ACCENT}; border-color: {ACCENT_DARK}; color: #ffffff;
                }}
            """)
            if abs(current_temp - kelvin) < 250:
                btn.setChecked(True)
            btn.clicked.connect(lambda _, k=kelvin: self._apply_preset(k))
            self.preset_group.addButton(btn)
            self._preset_buttons[kelvin] = btn
            presets_row.addWidget(btn)

        card.layout().addLayout(presets_row)

        slider_row = QHBoxLayout()
        slider_row.setSpacing(12)

        self.temp_slider = QSlider(Qt.Orientation.Horizontal)
        self.temp_slider.setRange(2500, 6500)
        self.temp_slider.setValue(current_temp)
        self.temp_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 6px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #f5a623, stop:0.5 #ffd599, stop:1 #d6e8fa);
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: #ffffff; border: 2px solid {ACCENT};
                width: 16px; margin: -5px 0; border-radius: 8px;
            }}
        """)
        self.temp_slider.valueChanged.connect(self._on_slider_changed)
        self.temp_slider.sliderReleased.connect(self._on_slider_released)

        self.temp_lbl = QLabel(f"{current_temp} K")
        self.temp_lbl.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: #2e3b35; min-width: 55px;"
        )

        slider_row.addWidget(self.temp_slider, 1)
        slider_row.addWidget(self.temp_lbl)
        card.layout().addLayout(slider_row)

        return card

    # ── Section: Hyprland keybinds ─────────────────────────────────────────

    def _build_hyprland_card(self) -> QFrame:
        from core.hyprland import detect_hyprland, has_keybinds

        card = self._section_card(
            "Горячие клавиши (Hyprland)",
            "Интеграция с Hyprland: автоматическая настройка клавиш микрофона "
            "и смены профилей питания.",
        )

        self._hyprland_available = detect_hyprland()
        status_text  = "Hyprland обнаружен" if self._hyprland_available else "Hyprland не обнаружен"
        status_color = ACCENT if self._hyprland_available else "#9a9e9c"
        status_lbl = QLabel(f"Статус: {status_text}")
        status_lbl.setStyleSheet(
            f"font-size: 11px; color: {status_color}; font-weight: 600;"
        )
        card.layout().addWidget(status_lbl)

        binds_info = QLabel(
            "XF86Reload   →  power-cycle.sh        (Fn+F: смена профиля питания)\n"
            "XF86Launch6  →  mic-sync.sh toggle    (микрофон + LED индикатор)"
        )
        binds_info.setStyleSheet(
            "font-size: 10px; color: #586962; font-family: 'JetBrains Mono', monospace; "
            "background: #f4f8f6; border: 1px solid #dde7e2; border-radius: 6px; "
            "padding: 8px 12px; margin: 4px 0;"
        )
        card.layout().addWidget(binds_info)

        row = QHBoxLayout()
        bind_col = QVBoxLayout()
        bind_title = QLabel("Активировать биндинги Acer Sense")
        bind_title.setStyleSheet("font-size: 12px; color: #2e3b35; font-weight: 700;")
        bind_sub = QLabel("Автоматически обновляет конфиг Hyprland")
        bind_sub.setStyleSheet("font-size: 10px; color: #72827c;")
        bind_col.addWidget(bind_title)
        bind_col.addWidget(bind_sub)
        row.addLayout(bind_col, 1)

        self.toggle_mic_bind = ToggleSwitch()
        bound = has_keybinds() if self._hyprland_available else False
        self.toggle_mic_bind.setChecked(bound)
        self.toggle_mic_bind.setEnabled(bool(self._hyprland_available))
        self.toggle_mic_bind.toggled.connect(self._toggle_mic_keybind)
        row.addWidget(self.toggle_mic_bind)
        card.layout().addLayout(row)

        self.mic_bind_status = QLabel("Биндинги активны" if bound else "Биндинги не установлены")
        self.mic_bind_status.setStyleSheet(
            f"font-size: 10px; color: {ACCENT if bound else '#9a9e9c'}; font-weight: 600;"
        )
        card.layout().addWidget(self.mic_bind_status)

        btn_reload = QPushButton("Применить конфигурацию Hyprland")
        btn_reload.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reload.setEnabled(bool(self._hyprland_available))
        btn_reload.setStyleSheet(f"""
            QPushButton {{
                border: 1px solid #88c2a8; border-radius: 12px; color: {ACCENT_DARK};
                padding: 7px 16px; font-size: 11px; font-weight: 600; background: #fff;
            }}
            QPushButton:hover {{ background: #edf8f2; }}
            QPushButton:disabled {{ color: #9ab0a8; border-color: #c8ddd2; }}
        """)
        btn_reload.clicked.connect(self._hyprctl_reload)
        card.layout().addWidget(btn_reload)
        return card

    # ── Helpers ────────────────────────────────────────────────────────────

    def _show_section(self, section: QFrame, button: QPushButton):
        button.setChecked(True)
        self.scroll.ensureWidgetVisible(section, 0, 20)

    def _set_charge_limit(self, limit: int):
        set_charge_limit(limit, persist=True)
        self.config["charge_limit"] = limit

    def _toggle_usb_charging(self, enabled: bool):
        from core.ec_control import set_usb_charging
        set_usb_charging(enabled, persist=True)

    def _open_battery_info(self, *_):
        from ui.details_dialogs import BatteryInfoDialog
        BatteryInfoDialog(self).exec()

    def _apply_preset(self, kelvin: int):
        self.temp_slider.setValue(kelvin)
        self.temp_lbl.setText(f"{kelvin} K")
        self.config["bluelight_temp"] = kelvin
        save_config({"bluelight_temp": kelvin})
        if self.toggle_bluelight.isChecked():
            self._apply_night_light(True)

    def _on_slider_changed(self, val: int):
        self.temp_lbl.setText(f"{val} K")

    def _on_slider_released(self):
        val = self.temp_slider.value()
        self.config["bluelight_temp"] = val
        save_config({"bluelight_temp": val})
        self.preset_group.setExclusive(False)
        for k, btn in self._preset_buttons.items():
            btn.setChecked(abs(val - k) < 150)
        self.preset_group.setExclusive(True)
        if self.toggle_bluelight.isChecked():
            self._apply_night_light(True)

    def toggle_night_light(self, enabled: bool):
        save_config({"bluelight_enabled": enabled})
        self._apply_night_light(enabled)

    def _apply_night_light(self, enabled: bool):
        temp = self.config.get("bluelight_temp", 4500)
        tool = (
            "hyprsunset" if shutil.which("hyprsunset")
            else "wlsunset" if shutil.which("wlsunset") else None
        )
        if self.night_proc:
            try:
                self.night_proc.terminate()
                self.night_proc.wait(timeout=1)
            except (OSError, subprocess.SubprocessError):
                pass
            self.night_proc = None
        if enabled and tool:
            self.night_proc = subprocess.Popen([tool, "-t", str(temp)])

    def _toggle_mic_keybind(self, enabled: bool):
        from core.hyprland import install_keybinds, remove_keybinds
        if enabled:
            ok = install_keybinds()
            self.mic_bind_status.setText(
                "Биндинги установлены" if ok else "Ошибка установки"
            )
            self.mic_bind_status.setStyleSheet(
                f"font-size: 10px; color: {ACCENT if ok else '#c44040'}; font-weight: 600;"
            )
        else:
            ok = remove_keybinds()
            self.mic_bind_status.setText("Биндинги удалены" if ok else "Ошибка удаления")
            self.mic_bind_status.setStyleSheet(
                "font-size: 10px; color: #9a9e9c; font-weight: 600;"
            )

    def _hyprctl_reload(self):
        from core.hyprland import reload_hyprland
        from PyQt6.QtWidgets import QMessageBox
        ok = reload_hyprland()
        if ok:
            QMessageBox.information(self, "Hyprland", "Конфигурация перезагружена.")
        else:
            QMessageBox.warning(self, "Hyprland", "Не удалось выполнить hyprctl reload.")

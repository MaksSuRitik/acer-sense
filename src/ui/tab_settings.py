"""Settings tab — matching official AcerSense layout with vector category icons and no text emojis."""
from __future__ import annotations

import shutil
import subprocess

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel,
                              QPushButton, QRadioButton, QScrollArea, QSlider,
                              QVBoxLayout, QWidget)

from core.battery_daemon import trigger_battery_monitor
from core.config import load_config, save_config
from core.ec_control import set_charge_limit
from core.power import get_power_profile, set_power_profile
from ui.icons import render_svg_pixmap
from ui.theme import ThemePalette, theme_manager
from ui.toggle import ToggleSwitch


class SettingsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.night_proc = None
        self._hyprland_available: bool | None = None
        self._cards: list[QFrame] = []
        self._radio_frames: list[tuple[QFrame, QRadioButton, QLabel]] = []
        self._section_icons: list[tuple[QLabel, str]] = []
        self._power_radios: dict[str, QRadioButton] = {}

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
        self.theme_card   = self._build_theme_card()

        content_layout.addWidget(self.power_card)
        content_layout.addWidget(self.battery_card)
        content_layout.addWidget(self.screen_card)
        content_layout.addWidget(self.hypr_card)
        content_layout.addWidget(self.theme_card)
        content_layout.addStretch(1)

        self.scroll.setWidget(content)
        layout.addWidget(sidebar)
        layout.addWidget(self.scroll, 1)

        self.apply_theme(theme_manager.palette)
        theme_manager.theme_changed.connect(self.apply_theme)

        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self._sync_realtime_settings)
        self.sync_timer.start(2000)

    # ── Sidebar navigation ─────────────────────────────────────────────────

    def _build_sidebar(self) -> QFrame:
        self.nav_panel = QFrame()
        self.nav_panel.setFixedWidth(216)
        self.nav_panel.setObjectName("navPanel")

        lo = QVBoxLayout(self.nav_panel)
        lo.setContentsMargins(12, 14, 12, 14)
        lo.setSpacing(4)
        lo.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.sidebar_title = QLabel("Персональные настройки")
        lo.addWidget(self.sidebar_title)

        self.nav_group = QButtonGroup(self.nav_panel)
        self.btn_nav_power   = self._nav_button("Режим использования системы")
        self.btn_nav_battery = self._nav_button("Аккумулятор и зарядка через USB")
        self.btn_nav_screen  = self._nav_button("Экран")
        self.btn_nav_hypr    = self._nav_button("Горячие клавиши (Hyprland)")
        self.btn_nav_theme   = self._nav_button("Внешний вид и тема")

        self.btn_nav_power.clicked.connect(
            lambda: self._show_section(self.power_card, self.btn_nav_power))
        self.btn_nav_battery.clicked.connect(
            lambda: self._show_section(self.battery_card, self.btn_nav_battery))
        self.btn_nav_screen.clicked.connect(
            lambda: self._show_section(self.screen_card, self.btn_nav_screen))
        self.btn_nav_hypr.clicked.connect(
            lambda: self._show_section(self.hypr_card, self.btn_nav_hypr))
        self.btn_nav_theme.clicked.connect(
            lambda: self._show_section(self.theme_card, self.btn_nav_theme))

        self.btn_nav_power.setChecked(True)
        for btn in (self.btn_nav_power, self.btn_nav_battery,
                    self.btn_nav_screen, self.btn_nav_hypr, self.btn_nav_theme):
            lo.addWidget(btn)
        lo.addStretch(1)
        return self.nav_panel

    def _nav_button(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.nav_group.addButton(btn)
        return btn

    # ── Card template ──────────────────────────────────────────────────────

    def _section_card(self, icon_name: str, title: str, subtitle: str = "") -> QFrame:
        card = QFrame()
        self._cards.append(card)
        section = QVBoxLayout(card)
        section.setContentsMargins(20, 16, 20, 16)
        section.setSpacing(10)

        # Header row: circular vector icon + title
        h_row = QHBoxLayout()
        h_row.setSpacing(8)

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(28, 28)
        self._section_icons.append((icon_lbl, icon_name))
        h_row.addWidget(icon_lbl)

        heading = QLabel(title)
        heading.setObjectName("sectionHeading")
        h_row.addWidget(heading)
        h_row.addStretch()
        section.addLayout(h_row)

        rule = QFrame()
        rule.setFixedHeight(1)
        rule.setObjectName("sectionRule")
        section.addWidget(rule)

        if subtitle:
            intro = QLabel(subtitle)
            intro.setWordWrap(True)
            intro.setObjectName("sectionIntro")
            section.addWidget(intro)
        return card

    # ── Radio option ───────────────────────────────────────────────────────

    def _radio_option(self, parent: QFrame, title: str, description: str,
                      selected: bool, callback) -> QRadioButton:
        row_frame = QFrame()
        row_frame.setObjectName("radioRow")
        row_lo = QVBoxLayout(row_frame)
        row_lo.setContentsMargins(14, 10, 14, 10)
        row_lo.setSpacing(3)

        radio = QRadioButton(title)
        radio.setChecked(selected)
        radio.setCursor(Qt.CursorShape.PointingHandCursor)
        radio.clicked.connect(callback)

        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setObjectName("radioDesc")

        row_lo.addWidget(radio)
        row_lo.addWidget(desc_lbl)
        parent.layout().addWidget(row_frame)

        self._radio_frames.append((row_frame, radio, desc_lbl))
        return radio

    # ── Section: Power Profiles ────────────────────────────────────────────

    def _build_power_card(self) -> QFrame:
        card = self._section_card(
            "speedo_circle",
            "Режим использования системы",
            "Эта настройка предлагает разные режимы использования для следующих сценариев. Вы можете изменить режимы в любое время, нажав клавиши Fn+F."
        )
        group = QButtonGroup(card)
        current = get_power_profile()
        for title, description, profile in (
            ("Бесшумно",
             "Для веб-сайтов или онлайн-бесед.",
             "power-saver"),
            ("Обычный",
             "Для работы, например, с Microsoft Office.",
             "balanced"),
            ("Производительность",
             "Для ресурсоемких игр, рендеринга, потоковой передачи или работы с видео.",
             "performance"),
        ):
            radio = self._radio_option(
                card, title, description,
                current == profile,
                lambda _, v=profile: set_power_profile(v),
            )
            self._power_radios[profile] = radio
            group.addButton(radio)
        return card

    # ── Section: Battery ───────────────────────────────────────────────────

    def _build_battery_card(self) -> QFrame:
        card = self._section_card(
            "battery_circle",
            "Аккумулятор и зарядка через USB",
            "Режим заряда аккумулятора"
        )
        group = QButtonGroup(card)
        limit = self.config.get("charge_limit", 100)

        self._radio_80 = self._radio_option(
            card,
            "Оптимизированная зарядка аккум.",
            "(Рекомендуется) Для продления срока службы аккумулятора он будет заряжен только до 80% емкости.",
            limit == 80,
            lambda: self._set_charge_limit(80),
        )
        self._radio_100 = self._radio_option(
            card,
            "Зарядка аккум. до полной емкости",
            "Зарядка до максимальной емкости для более долгого использования в мобильном режиме.",
            limit != 80,
            lambda: self._set_charge_limit(100),
        )
        group.addButton(self._radio_80)
        group.addButton(self._radio_100)

        self.btn_details = QPushButton("См. дополнительную информацию о состоянии аккумулятора >")
        self.btn_details.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_details.clicked.connect(self._open_battery_info)
        card.layout().addWidget(self.btn_details)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setObjectName("sectionRule")
        card.layout().addWidget(sep)

        # USB charging toggle
        usb_row = QHBoxLayout()
        usb_info = QVBoxLayout()
        self.usb_title = QLabel("Зарядка через USB при выключенном питании")
        self.usb_text = QLabel(
            "Заряжайте мобильные устройства через выделенный разъем USB, даже когда ноутбук выключен."
        )
        self.usb_text.setWordWrap(True)
        usb_info.addWidget(self.usb_title)
        usb_info.addWidget(self.usb_text)
        usb_row.addLayout(usb_info, 1)

        usb_enabled = self.config.get("usb_charging", False)
        self.toggle_usb = ToggleSwitch()
        self.toggle_usb.setChecked(usb_enabled)
        self.toggle_usb.toggled.connect(self._toggle_usb_charging)
        usb_row.addWidget(self.toggle_usb)
        card.layout().addLayout(usb_row)

        return card

    # ── Section: Screen (BluelightShield) ───────────────────────────────────

    def _build_screen_card(self) -> QFrame:
        card = self._section_card("display", "Экран")

        top_row = QHBoxLayout()
        info_col = QVBoxLayout()
        self.bl_title = QLabel("BluelightShield")
        self.bl_desc = QLabel(
            "Примените настройки Acer BluelightShield, чтобы защитить глаза от синего спектра света."
        )
        self.bl_desc.setWordWrap(True)
        info_col.addWidget(self.bl_title)
        info_col.addWidget(self.bl_desc)
        top_row.addLayout(info_col, 1)

        self.toggle_bluelight = ToggleSwitch()
        self.toggle_bluelight.setChecked(self.config.get("bluelight_enabled", False))
        self.toggle_bluelight.toggled.connect(self.toggle_night_light)
        top_row.addWidget(self.toggle_bluelight)
        card.layout().addLayout(top_row)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setObjectName("sectionRule")
        card.layout().addWidget(sep)

        self.preset_title = QLabel("Пресеты фильтрации:")
        card.layout().addWidget(self.preset_title)

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
        self.temp_slider.valueChanged.connect(self._on_slider_changed)
        self.temp_slider.sliderReleased.connect(self._on_slider_released)

        self.temp_lbl = QLabel(f"{current_temp} K")
        slider_row.addWidget(self.temp_slider, 1)
        slider_row.addWidget(self.temp_lbl)
        card.layout().addLayout(slider_row)

        return card

    # ── Section: Hyprland Keybinds ─────────────────────────────────────────

    def _build_hyprland_card(self) -> QFrame:
        from core.hyprland import detect_hyprland, has_keybinds

        card = self._section_card(
            "keyboard",
            "Горячие клавиши (Hyprland)",
            "Автоматическая привязка клавиши переключения микрофона и смены профилей питания."
        )

        self._hyprland_available = detect_hyprland()
        status_text  = "Hyprland обнаружен" if self._hyprland_available else "Hyprland не обнаружен"
        self.status_lbl = QLabel(f"Статус системы: {status_text}")
        card.layout().addWidget(self.status_lbl)

        self.binds_info = QLabel(
            "XF86Reload   →  power-cycle.sh        (Fn+F: смена профиля питания)\n"
            "XF86Launch6  →  mic-sync.sh toggle    (микрофон + LED индикатор)"
        )
        card.layout().addWidget(self.binds_info)

        row = QHBoxLayout()
        bind_col = QVBoxLayout()
        self.bind_title = QLabel("Активировать биндинги Acer Sense")
        self.bind_sub = QLabel("Автоматически обновляет конфиг Hyprland при переключении")
        bind_col.addWidget(self.bind_title)
        bind_col.addWidget(self.bind_sub)
        row.addLayout(bind_col, 1)

        self.toggle_mic_bind = ToggleSwitch()
        bound = has_keybinds() if self._hyprland_available else False
        self.toggle_mic_bind.setChecked(bound)
        self.toggle_mic_bind.setEnabled(bool(self._hyprland_available))
        self.toggle_mic_bind.toggled.connect(self._toggle_mic_keybind)
        row.addWidget(self.toggle_mic_bind)
        card.layout().addLayout(row)

        self.mic_bind_status = QLabel("Биндинги активны" if bound else "Биндинги не установлены")
        card.layout().addWidget(self.mic_bind_status)

        self.btn_reload = QPushButton("Применить конфигурацию Hyprland (hyprctl reload)")
        self.btn_reload.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reload.setEnabled(bool(self._hyprland_available))
        self.btn_reload.clicked.connect(self._hyprctl_reload)
        card.layout().addWidget(self.btn_reload)
        return card

    # ── Section: Theme / Appearance ────────────────────────────────────────

    def _build_theme_card(self) -> QFrame:
        card = self._section_card(
            "theme_palette",
            "Внешний вид и тема оформления",
            "Выберите тему интерфейса. Режим 'Системная' автоматически подстраивается под настройки окружения."
        )
        group = QButtonGroup(card)
        current_theme = self.config.get("theme", "system")

        radio_light = self._radio_option(
            card,
            "Светлая тема",
            "Классический светлый интерфейс с высокой контрастностью.",
            current_theme == "light",
            lambda: self._set_theme("light"),
        )
        radio_dark = self._radio_option(
            card,
            "Тёмная тема",
            "Глубокая тёмно-изумрудная тема, снижающая нагрузку на глаза ночью.",
            current_theme == "dark",
            lambda: self._set_theme("dark"),
        )
        radio_system = self._radio_option(
            card,
            "Системная тема",
            "Автоматический подхват тёмной или светлой темы из настроек рабочего стола.",
            current_theme == "system",
            lambda: self._set_theme("system"),
        )

        group.addButton(radio_light)
        group.addButton(radio_dark)
        group.addButton(radio_system)
        return card

    # ── Theme Application ──────────────────────────────────────────────────

    def apply_theme(self, pal: ThemePalette):
        self.nav_panel.setStyleSheet(f"""
            QFrame#navPanel {{
                background: {pal.bg_card};
                border: 1px solid {pal.border};
                border-radius: 16px;
            }}
        """)
        self.sidebar_title.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {pal.text_primary}; margin-bottom: 6px; background: transparent;"
        )

        nav_ss = f"""
            QPushButton {{
                border: 0; border-radius: 8px; padding: 9px 10px;
                text-align: left; font-size: 11px; font-weight: 500;
                color: {pal.text_secondary}; background: transparent;
            }}
            QPushButton:checked {{
                color: {pal.accent}; font-weight: 700; background: {pal.accent_subtle};
                border-left: 3px solid {pal.accent};
            }}
            QPushButton:hover:!checked {{ background: {pal.tab_hover}; }}
        """
        for btn in (self.btn_nav_power, self.btn_nav_battery, self.btn_nav_screen,
                    self.btn_nav_hypr, self.btn_nav_theme):
            btn.setStyleSheet(nav_ss)

        for icon_lbl, icon_name in self._section_icons:
            pix = render_svg_pixmap(icon_name, pal.accent, 26)
            icon_lbl.setPixmap(pix)

        for card in self._cards:
            card.setStyleSheet(f"background: {pal.bg_card}; border: 1px solid {pal.border}; border-radius: 16px;")
            for head in card.findChildren(QLabel, "sectionHeading"):
                head.setStyleSheet(f"font-size: 14px; color: {pal.text_primary}; font-weight: 700; background: transparent; border: 0;")
            for intro in card.findChildren(QLabel, "sectionIntro"):
                intro.setStyleSheet(f"font-size: 11px; color: {pal.text_muted}; background: transparent; border: 0;")
            for rule in card.findChildren(QFrame, "sectionRule"):
                rule.setStyleSheet(f"background: {pal.border}; border: 0; margin: 0;")

        # Radio options styling
        for r_frame, radio, desc in self._radio_frames:
            r_frame.setStyleSheet(f"""
                QFrame#radioRow {{
                    background: {pal.bg_card_sub};
                    border: 1px solid {pal.border_sub};
                    border-radius: 10px;
                    margin: 1px 0;
                }}
            """)
            radio.setStyleSheet(f"""
                QRadioButton {{
                    color: {pal.text_primary};
                    font-size: 12px;
                    font-weight: 600;
                    spacing: 8px;
                    background: transparent;
                }}
                QRadioButton:focus {{ outline: none; background: transparent; }}
                QRadioButton::indicator {{
                    width: 16px; height: 16px;
                    border: 1.5px solid {pal.border};
                    border-radius: 8px;
                    background: {pal.bg_card};
                }}
                QRadioButton::indicator:checked {{
                    border: 4.5px solid {pal.accent};
                    background: {pal.bg_card};
                }}
                QRadioButton::indicator:hover {{ border-color: {pal.accent}; }}
            """)
            desc.setStyleSheet(f"font-size: 11px; color: {pal.text_muted}; margin-left: 24px; background: transparent; border: 0;")

        self.btn_details.setStyleSheet(f"""
            QPushButton {{
                text-align: left; background: transparent; border: 0;
                color: {pal.accent}; font-size: 11px; font-weight: 600; padding: 4px 0;
            }}
            QPushButton:hover {{ color: {pal.accent_dark}; text-decoration: underline; }}
        """)

        self.usb_title.setStyleSheet(f"font-size: 12px; color: {pal.text_primary}; font-weight: 600; background: transparent; border: 0;")
        self.usb_text.setStyleSheet(f"font-size: 11px; color: {pal.text_muted}; background: transparent; border: 0;")

        self.bl_title.setStyleSheet(f"font-size: 13px; color: {pal.text_primary}; font-weight: 700; background: transparent; border: 0;")
        self.bl_desc.setStyleSheet(f"font-size: 11px; color: {pal.text_muted}; background: transparent; border: 0;")
        self.preset_title.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {pal.text_secondary}; background: transparent; border: 0;")

        for btn in self._preset_buttons.values():
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {pal.bg_card_sub}; border: 1px solid {pal.border};
                    border-radius: 14px; color: {pal.text_secondary};
                    font-size: 11px; font-weight: 600; padding: 0 12px;
                }}
                QPushButton:hover {{ background: {pal.tab_hover}; border-color: {pal.accent}; }}
                QPushButton:checked {{
                    background: {pal.accent}; border-color: {pal.accent_dark}; color: #ffffff;
                }}
            """)

        self.temp_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 6px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #f5a623, stop:0.5 #ffd599, stop:1 #d6e8fa);
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: #ffffff; border: 2px solid {pal.accent};
                width: 16px; margin: -5px 0; border-radius: 8px;
            }}
        """)
        self.temp_lbl.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {pal.text_primary}; min-width: 55px; background: transparent; border: 0;")

        status_color = pal.accent if self._hyprland_available else pal.text_muted
        self.status_lbl.setStyleSheet(f"font-size: 11px; color: {status_color}; font-weight: 600; background: transparent; border: 0;")
        self.binds_info.setStyleSheet(
            f"font-size: 10px; color: {pal.text_secondary}; font-family: 'JetBrains Mono', monospace; "
            f"background: {pal.bg_card_sub}; border: 1px solid {pal.border_sub}; border-radius: 6px; "
            f"padding: 8px 12px; margin: 4px 0;"
        )
        self.bind_title.setStyleSheet(f"font-size: 12px; color: {pal.text_primary}; font-weight: 700; background: transparent; border: 0;")
        self.bind_sub.setStyleSheet(f"font-size: 10px; color: {pal.text_muted}; background: transparent; border: 0;")
        self.mic_bind_status.setStyleSheet(f"font-size: 10px; color: {pal.accent if self.toggle_mic_bind.isChecked() else pal.text_muted}; font-weight: 600; background: transparent; border: 0;")

        self.btn_reload.setStyleSheet(f"""
            QPushButton {{
                border: 1px solid {pal.border}; border-radius: 12px; color: {pal.accent};
                padding: 7px 16px; font-size: 11px; font-weight: 600; background: {pal.bg_card};
            }}
            QPushButton:hover {{ background: {pal.tab_hover}; border-color: {pal.accent}; }}
            QPushButton:disabled {{ color: {pal.text_muted}; border-color: {pal.border_sub}; }}
        """)

    # ── Helpers ────────────────────────────────────────────────────────────

    def _show_section(self, section: QFrame, button: QPushButton):
        button.setChecked(True)
        self.scroll.ensureWidgetVisible(section, 0, 20)

    def _set_theme(self, mode: str):
        self.config["theme"] = mode
        theme_manager.set_theme_mode(mode)

    def _set_charge_limit(self, limit: int):
        set_charge_limit(limit, persist=True)
        self.config["charge_limit"] = limit
        trigger_battery_monitor()

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
                f"font-size: 10px; color: {theme_manager.palette.accent if ok else '#c44040'}; font-weight: 600;"
            )
        else:
            ok = remove_keybinds()
            self.mic_bind_status.setText("Биндинги удалены" if ok else "Ошибка удаления")
            self.mic_bind_status.setStyleSheet(
                f"font-size: 10px; color: {theme_manager.palette.text_muted}; font-weight: 600;"
            )

    def _hyprctl_reload(self):
        from core.hyprland import reload_hyprland
        from PyQt6.QtWidgets import QMessageBox
        ok = reload_hyprland()
        if ok:
            QMessageBox.information(self, "Hyprland", "Конфигурация перезагружена.")
        else:
            QMessageBox.warning(self, "Hyprland", "Не удалось выполнить hyprctl reload.")

    def _sync_realtime_settings(self):
        # 1. Real-time Power Profile radio synchronization
        current = get_power_profile()
        if current in self._power_radios:
            radio = self._power_radios[current]
            if not radio.isChecked():
                radio.blockSignals(True)
                radio.setChecked(True)
                radio.blockSignals(False)

        # 2. Real-time Battery Limit radio synchronization
        try:
            from core.config import load_config
            cfg = load_config()
            limit = cfg.get("charge_limit", 100)
            if hasattr(self, "_radio_80") and hasattr(self, "_radio_100"):
                if limit == 80 and not self._radio_80.isChecked():
                    self._radio_80.blockSignals(True)
                    self._radio_80.setChecked(True)
                    self._radio_80.blockSignals(False)
                elif limit != 80 and not self._radio_100.isChecked():
                    self._radio_100.blockSignals(True)
                    self._radio_100.setChecked(True)
                    self._radio_100.blockSignals(False)
        except Exception:
            pass


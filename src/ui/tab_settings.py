from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QButtonGroup, QComboBox, QFrame, QHBoxLayout, QLabel,
                              QPushButton, QRadioButton, QScrollArea, QVBoxLayout,
                              QWidget)
import shutil
import subprocess

from core.config import load_config, save_config
from core.ec_control import set_charge_limit
from core.power import get_power_profile, set_power_profile
from ui.toggle import ToggleSwitch


ACCENT = "#4ba781"
ACCENT_DARK = "#357a5e"


class SettingsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.night_proc = None
        self._hyprland_available: bool | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(90, 22, 90, 32)
        layout.setSpacing(14)

        sidebar = self._build_sidebar()
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { border: 0; background: transparent; }")

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 4, 0)
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

        content_holder = QWidget()
        content_holder.setMaximumWidth(640)
        holder_layout = QHBoxLayout(content_holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        holder_layout.addWidget(self.scroll)

        layout.addWidget(sidebar)
        layout.addWidget(content_holder, 1)

        self.btn_nav_power.clicked.connect(
            lambda: self._show_section(self.power_card, self.btn_nav_power))
        self.btn_nav_battery.clicked.connect(
            lambda: self._show_section(self.battery_card, self.btn_nav_battery))
        self.btn_nav_screen.clicked.connect(
            lambda: self._show_section(self.screen_card, self.btn_nav_screen))
        self.btn_nav_hypr.clicked.connect(
            lambda: self._show_section(self.hypr_card, self.btn_nav_hypr))

    # ── Боковая навигация ───────────────────────────────────────────────────

    def _build_sidebar(self) -> QWidget:
        outer = QVBoxLayout()
        heading = QLabel("Персональные настройки")
        heading.setStyleSheet("font-size: 13px; font-weight: 700; color: #49514d;"
                              "padding-left: 9px;")

        frame = QFrame()
        frame.setFixedWidth(270)
        frame.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #dde7e2;"
                            "border-radius: 14px; }")
        nav = QVBoxLayout(frame)
        nav.setContentsMargins(0, 8, 0, 8)
        nav.setSpacing(0)

        self.nav_group = QButtonGroup(self)
        self.btn_nav_power   = self._nav_button("Режим использования системы", True)
        self.btn_nav_battery = self._nav_button("Аккумулятор и зарядка через USB", False)
        self.btn_nav_screen  = self._nav_button("Экран", False)
        self.btn_nav_hypr    = self._nav_button("Клавиатура (Hyprland)", False)

        for btn in (self.btn_nav_power, self.btn_nav_battery,
                    self.btn_nav_screen, self.btn_nav_hypr):
            nav.addWidget(btn)
        nav.addStretch(1)

        outer.addWidget(heading)
        outer.addSpacing(3)
        outer.addWidget(frame)
        outer.addStretch(1)

        holder = QWidget()
        holder.setFixedWidth(270)
        holder.setLayout(outer)
        return holder

    def _nav_button(self, text: str, selected: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(selected)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(44)
        btn.setStyleSheet(f"""
            QPushButton {{ text-align: left; padding: 0 14px; border: 0;
                           border-left: 3px solid transparent;
                           background: transparent; color: #66706b; font-size: 12px; }}
            QPushButton:checked {{ border-left-color: {ACCENT};
                                   color: {ACCENT_DARK}; font-weight: 700; background: #f4faf7; }}
            QPushButton:hover:!checked {{ background: #f6f9f7; }}
        """)
        self.nav_group.addButton(btn)
        return btn

    # ── Шаблон карточки ─────────────────────────────────────────────────────

    def _section_card(self, icon: str, title: str, subtitle: str = "") -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame { background: #ffffff; border: 1px solid #dde8e3; border-radius: 16px; }
            QLabel { border: 0; background: transparent; }
        """)
        section = QVBoxLayout(card)
        section.setContentsMargins(16, 14, 16, 16)
        section.setSpacing(7)

        heading = QLabel(f"{icon}  {title}" if icon else title)
        heading.setStyleSheet("font-size: 15px; color: #555e59; font-weight: 700;")
        rule = QFrame()
        rule.setFixedHeight(1)
        rule.setStyleSheet("background: #cfe6da; border: 0; margin: 0 0 3px;")
        section.addWidget(heading)
        section.addWidget(rule)
        if subtitle:
            intro = QLabel(subtitle)
            intro.setWordWrap(True)
            intro.setStyleSheet("font-size: 11px; color: #747d78; margin-bottom: 3px;")
            section.addWidget(intro)
        return card

    def _radio_option(self, parent: QFrame, title: str, description: str,
                      selected: bool, callback) -> QRadioButton:
        radio = QRadioButton(title)
        radio.setChecked(selected)
        radio.setCursor(Qt.CursorShape.PointingHandCursor)
        radio.setStyleSheet(f"""
            QRadioButton {{ color: #545e59; font-size: 13px; font-weight: 700; padding-top: 4px; }}
            QRadioButton::indicator {{ width: 15px; height: 15px;
                border: 1px solid #b0ccbc; border-radius: 7px; }}
            QRadioButton::indicator:checked {{ border: 4px solid {ACCENT}; background: #fff; }}
        """)
        radio.clicked.connect(callback)
        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("font-size: 10px; color: #7a8480; margin-left: 26px; margin-bottom: 2px;")
        parent.layout().addWidget(radio)
        parent.layout().addWidget(desc_lbl)
        return radio

    # ── Карточки настроек ───────────────────────────────────────────────────

    def _build_power_card(self) -> QFrame:
        card = self._section_card(
            "", "Режим использования системы",
            "Эта настройка предлагает разные режимы использования для следующих сценариев. "
            "Вы можете изменить режимы в любое время, нажав клавиши Fn+F."
        )
        group = QButtonGroup(card)
        current = get_power_profile()
        for title, description, profile in (
            ("Бесшумно",       "Для веб-сайтов или онлайн-бесед.",                   "power-saver"),
            ("Обычный",        "Для работы, например, с Microsoft Office.",           "balanced"),
            ("Производительность",
             "Для ресурсоёмких игр, рендеринга, потоковой передачи или работы с видео.",
             "performance"),
        ):
            radio = self._radio_option(
                card, title, description,
                current == profile,
                lambda _, v=profile: set_power_profile(v),
            )
            group.addButton(radio)
        return card

    def _build_battery_card(self) -> QFrame:
        card = self._section_card("", "Аккумулятор и зарядка через USB",
                                  "Режим заряда аккумулятора")
        group = QButtonGroup(card)
        limit = self.config.get("charge_limit", 100)

        radio_80 = self._radio_option(
            card,
            "Оптимизированная зарядка аккум.",
            "(Рекомендуется)\nДля продления срока службы аккумулятора он будет заряжен только до 80% ёмкости.",
            limit == 80,
            lambda: self._set_charge_limit(80),
        )
        radio_100 = self._radio_option(
            card,
            "Зарядка аккум. до полной ёмкости",
            "Зарядка до максимальной ёмкости для более долгого использования в мобильном режиме.",
            limit != 80,
            lambda: self._set_charge_limit(100),
        )
        group.addButton(radio_80)
        group.addButton(radio_100)

        btn_details = QPushButton("Детальные сведения об аккумуляторе ›")
        btn_details.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_details.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                background: transparent;
                border: 0;
                color: {ACCENT};
                font-size: 11px;
                font-weight: 600;
                padding: 4px 0;
            }}
            QPushButton:hover {{
                color: {ACCENT_DARK};
                text-decoration: underline;
            }}
        """)
        btn_details.clicked.connect(self._open_battery_info)
        card.layout().addWidget(btn_details)

        # ── Разделитель ──────────────────────────────────────────────────
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #dde9e3; border: 0;")
        card.layout().addWidget(sep)

        # ── USB зарядка при выключении ───────────────────────────────────
        usb_title = QLabel("Зарядка через USB при выключенном питании")
        usb_title.setStyleSheet("font-size: 13px; color: #545e59; font-weight: 700; margin-top: 4px;")
        usb_text = QLabel(
            "Заряжайте мобильные устройства через выделенный разъём USB, даже\n"
            "когда ноутбук выключен, находится в режиме гибернации или питается от аккумулятора."
        )
        usb_text.setWordWrap(True)
        usb_text.setStyleSheet("font-size: 10px; color: #7a8480;")
        usb_enabled = self.config.get("usb_charging", False)
        self.toggle_usb = ToggleSwitch()
        self.toggle_usb.setChecked(usb_enabled)
        self.toggle_usb.toggled.connect(self._toggle_usb_charging)

        card.layout().addWidget(usb_title)
        card.layout().addWidget(usb_text)
        card.layout().addWidget(self.toggle_usb)

        # ── Ограничение заряда при питании от аккумулятора ──────────────
        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet("background: #dde9e3; border: 0;")
        card.layout().addWidget(sep2)

        limit_title = QLabel("Ограничение заряда при питании от аккумулятора")
        limit_title.setStyleSheet("font-size: 13px; color: #545e59; font-weight: 700; margin-top: 4px;")
        limit_desc = QLabel(
            "При питании от аккумулятора прекратите зарядку, когда уровень заряда\n"
            "аккумулятора достигает:"
        )
        limit_desc.setWordWrap(True)
        limit_desc.setStyleSheet("font-size: 10px; color: #7a8480;")

        self.charge_combo = QComboBox()
        self.charge_combo.setFixedWidth(120)
        self.charge_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.charge_combo.setStyleSheet(f"""
            QComboBox {{ background: #ffffff; border: 1px solid #b8d5c5;
                         border-radius: 8px; padding: 4px 10px; font-size: 12px; color: #545e59; }}
            QComboBox::drop-down {{ border: 0; }}
            QComboBox QAbstractItemView {{ background: #fff; border: 1px solid #c8ddd2;
                                           selection-background-color: #d7f0e5; color: #3d4f47; }}
        """)
        for pct in ("30%", "50%", "80%", "100%"):
            self.charge_combo.addItem(pct)
        saved_limit = self.config.get("charge_limit", 100)
        limit_map = {80: "80%", 100: "100%"}
        self.charge_combo.setCurrentText(limit_map.get(saved_limit, "100%"))
        self.charge_combo.currentTextChanged.connect(self._on_limit_combo_changed)

        card.layout().addWidget(limit_title)
        card.layout().addWidget(limit_desc)
        card.layout().addWidget(self.charge_combo)
        return card

    def _build_screen_card(self) -> QFrame:
        card = self._section_card("", "Экран")

        # BluelightShield
        bl_title = QLabel("BluelightShield")
        bl_title.setStyleSheet("font-size: 13px; color: #545e59; font-weight: 700;")
        bl_desc = QLabel(
            "Применяет настройки Acer BluelightShield, чтобы защитить глаза.\n"
            "Использует hyprsunset или wlsunset при наличии в системе."
        )
        bl_desc.setWordWrap(True)
        bl_desc.setStyleSheet("font-size: 10px; color: #7a8480;")

        self.toggle_bluelight = ToggleSwitch()
        self.toggle_bluelight.setChecked(self.config.get("bluelight_enabled", False))
        self.toggle_bluelight.toggled.connect(self.toggle_night_light)

        card.layout().addWidget(bl_title)
        card.layout().addWidget(bl_desc)
        card.layout().addWidget(self.toggle_bluelight)
        return card

    def _build_hyprland_card(self) -> QFrame:
        from core.hyprland import detect_hyprland, has_keybinds

        card = self._section_card(
            "", "Горячие клавиши (Hyprland)",
            "Интеграция с Hyprland: автоматическая настройка клавиш микрофона и смены профилей питания."
        )

        self._hyprland_available = detect_hyprland()
        status_text  = "Hyprland обнаружен" if self._hyprland_available else "Hyprland не обнаружен"
        status_color = "#4d8a73" if self._hyprland_available else "#9a9e9c"
        status_lbl = QLabel(f"Статус: {status_text}")
        status_lbl.setStyleSheet(f"font-size: 11px; color: {status_color}; font-weight: 600;")
        card.layout().addWidget(status_lbl)

        # Строка с описанием биндов
        binds_info = QLabel(
            "XF86Launch6  →  mic-sync.sh toggle   (микрофон + LED)\n"
            "XF86Reload   →  power-cycle.sh        (Fn+F, смена профиля)"
        )
        binds_info.setStyleSheet(
            "font-size: 10px; color: #6a7570; font-family: monospace; "
            "background: #f4f7f5; border: 1px solid #dde9e3; border-radius: 6px; "
            "padding: 7px 10px; margin: 4px 0;"
        )
        card.layout().addWidget(binds_info)

        # Toggle — устанавливает/удаляет обе привязки сразу
        row = QHBoxLayout()
        row.setSpacing(10)
        bind_lbl = QVBoxLayout()
        bind_title = QLabel("Установить все биндинги Acer Sense")
        bind_title.setStyleSheet("font-size: 13px; color: #545e59; font-weight: 700;")
        bind_sub = QLabel("Добавляет секцию «Acer Sense keybinds» в конфиг Hyprland")
        bind_sub.setStyleSheet("font-size: 10px; color: #7a8480;")
        bind_lbl.addWidget(bind_title)
        bind_lbl.addWidget(bind_sub)
        row.addLayout(bind_lbl, 1)

        self.toggle_mic_bind = ToggleSwitch()
        bound = has_keybinds() if self._hyprland_available else False
        self.toggle_mic_bind.setChecked(bound)
        self.toggle_mic_bind.setEnabled(bool(self._hyprland_available))
        self.toggle_mic_bind.toggled.connect(self._toggle_mic_keybind)
        row.addWidget(self.toggle_mic_bind)
        card.layout().addLayout(row)

        self.mic_bind_status = QLabel("Биндинги установлены" if bound else "Биндинги не установлены")
        self.mic_bind_status.setStyleSheet(
            f"font-size: 10px; color: {'#4d8a73' if bound else '#9a9e9c'};"
        )
        card.layout().addWidget(self.mic_bind_status)

        # Кнопка перезагрузки конфига
        btn_reload = QPushButton("Применить (hyprctl reload)")
        btn_reload.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reload.setEnabled(bool(self._hyprland_available))
        btn_reload.setStyleSheet(f"""
            QPushButton {{ border: 1px solid #88c2a8; border-radius: 14px; color: #4d8a73;
                           padding: 6px 12px; font-size: 11px; font-weight: 600; background: #fff; }}
            QPushButton:hover {{ background: #edf8f2; }}
            QPushButton:disabled {{ color: #9ab0a8; border-color: #c8ddd2; }}
        """)
        btn_reload.clicked.connect(self._hyprctl_reload)
        card.layout().addWidget(btn_reload)
        return card

    # ── Вспомогательные методы ───────────────────────────────────────────────

    def _show_section(self, section: QFrame, button: QPushButton):
        button.setChecked(True)
        self.scroll.ensureWidgetVisible(section, 0, 20)

    def _set_charge_limit(self, limit: int):
        if set_charge_limit(limit):
            self.config["charge_limit"] = limit
            save_config({"charge_limit": limit})

    def _on_limit_combo_changed(self, text: str):
        try:
            pct = int(text.replace("%", ""))
        except ValueError:
            return
        # ec-helper поддерживает только 80 и 100; остальные — только сохраняем
        if pct in (80, 100):
            self._set_charge_limit(pct)
        else:
            self.config["charge_limit"] = pct
            save_config({"charge_limit": pct})

    def _toggle_usb_charging(self, enabled: bool):
        from core.ec_control import set_usb_charging
        set_usb_charging(enabled, persist=True)

    def _open_battery_info(self, *_):
        from ui.details_dialogs import BatteryInfoDialog
        BatteryInfoDialog(self).exec()

    def toggle_night_light(self, enabled: bool):
        save_config({"bluelight_enabled": enabled})
        self._apply_night_light(enabled)

    def _apply_night_light(self, enabled: bool):
        temp = self.config.get("bluelight_temp", 4500)
        tool = ("hyprsunset" if shutil.which("hyprsunset")
                else "wlsunset" if shutil.which("wlsunset") else None)
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
        from core.hyprland import install_mic_keybind, remove_mic_keybind
        if enabled:
            ok = install_mic_keybind()
            self.mic_bind_status.setText("Биндинг установлен" if ok else "Ошибка установки")
            self.mic_bind_status.setStyleSheet(
                f"font-size: 10px; color: {'#4d8a73' if ok else '#c44040'};"
            )
        else:
            ok = remove_mic_keybind()
            self.mic_bind_status.setText("Биндинг удалён" if ok else "Ошибка удаления")
            self.mic_bind_status.setStyleSheet("font-size: 10px; color: #9a9e9c;")

    def _hyprctl_reload(self):
        from core.hyprland import reload_hyprland
        ok = reload_hyprland()
        from PyQt6.QtWidgets import QMessageBox
        if ok:
            QMessageBox.information(self, "Hyprland", "Конфигурация перезагружена успешно.")
        else:
            QMessageBox.warning(self, "Hyprland", "Не удалось выполнить hyprctl reload.")

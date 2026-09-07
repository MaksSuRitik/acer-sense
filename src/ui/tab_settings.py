from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel,
                             QPushButton, QRadioButton, QScrollArea, QSlider,
                             QVBoxLayout, QWidget)
import shutil
import subprocess

from core.config import load_config, save_config
from core.ec_control import set_charge_limit
from core.power import get_power_profile, set_power_profile
from ui.toggle import ToggleSwitch


ACCENT = "#4ba781"


class SettingsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.night_proc = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(100, 24, 100, 34)
        layout.setSpacing(12)

        sidebar = self._build_sidebar()
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { border: 0; background: transparent; }")
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 4, 0)
        content_layout.setSpacing(12)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.power_card = self._build_power_card()
        self.battery_card = self._build_battery_card()
        self.screen_card = self._build_screen_card()
        content_layout.addWidget(self.power_card)
        content_layout.addWidget(self.battery_card)
        content_layout.addWidget(self.screen_card)
        content_layout.addStretch(1)
        self.scroll.setWidget(content)

        content_holder = QWidget()
        content_holder.setMaximumWidth(620)
        holder_layout = QHBoxLayout(content_holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        holder_layout.addWidget(self.scroll)
        layout.addWidget(sidebar)
        layout.addWidget(content_holder, 1)

        self.btn_nav_power.clicked.connect(lambda: self._show_section(self.power_card, self.btn_nav_power))
        self.btn_nav_battery.clicked.connect(lambda: self._show_section(self.battery_card, self.btn_nav_battery))
        self.btn_nav_screen.clicked.connect(lambda: self._show_section(self.screen_card, self.btn_nav_screen))

    def _build_sidebar(self) -> QFrame:
        outer = QVBoxLayout()
        heading = QLabel("Персональные настройки")
        heading.setStyleSheet("font-size: 13px; font-weight: 700; color: #49514d; padding-left: 9px;")
        frame = QFrame()
        frame.setFixedWidth(270)
        frame.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #e5eae7; border-radius: 15px; }")
        nav = QVBoxLayout(frame)
        nav.setContentsMargins(0, 8, 0, 8)
        nav.setSpacing(0)
        self.nav_group = QButtonGroup(self)
        self.btn_nav_power = self._nav_button("Режим использования системы", True)
        self.btn_nav_battery = self._nav_button("Аккумулятор и зарядка через USB", False)
        self.btn_nav_screen = self._nav_button("Экран", False)
        nav.addWidget(self.btn_nav_power)
        nav.addWidget(self.btn_nav_battery)
        nav.addWidget(self.btn_nav_screen)
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
        button = QPushButton(text)
        button.setCheckable(True)
        button.setChecked(selected)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedHeight(42)
        button.setStyleSheet(f"""
            QPushButton {{ text-align: left; padding: 0 12px; border: 0; border-left: 3px solid transparent;
                            background: transparent; color: #66706b; font-size: 12px; }}
            QPushButton:checked {{ border-left-color: {ACCENT}; color: #438b6d; font-weight: 700; background: #f5faf7; }}
            QPushButton:hover:!checked {{ background: #f8faf8; }}
        """)
        self.nav_group.addButton(button)
        return button

    def _section_card(self, icon: str, title: str, subtitle: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame { background: #ffffff; border: 1px solid #e1e8e4; border-radius: 16px; }
            QLabel { border: 0; background: transparent; }
        """)
        section = QVBoxLayout(card)
        section.setContentsMargins(14, 13, 14, 14)
        section.setSpacing(7)
        heading = QLabel(f"{icon}  {title}")
        heading.setStyleSheet("font-size: 16px; color: #5d6661; font-weight: 700;")
        rule = QFrame()
        rule.setFixedHeight(1)
        rule.setStyleSheet("background: #cfe6da; border: 0; margin: 0 0 4px;")
        intro = QLabel(subtitle)
        intro.setWordWrap(True)
        intro.setStyleSheet("font-size: 11px; color: #737c77; margin-bottom: 4px;")
        section.addWidget(heading)
        section.addWidget(rule)
        section.addWidget(intro)
        return card

    def _radio_option(self, parent: QFrame, title: str, description: str, selected: bool, callback) -> QRadioButton:
        radio = QRadioButton(title)
        radio.setChecked(selected)
        radio.setCursor(Qt.CursorShape.PointingHandCursor)
        radio.setStyleSheet(f"""
            QRadioButton {{ color: #59635e; font-size: 13px; font-weight: 700; padding-top: 5px; }}
            QRadioButton::indicator {{ width: 14px; height: 14px; border: 1px solid #aacdbd; border-radius: 7px; }}
            QRadioButton::indicator:checked {{ border: 4px solid {ACCENT}; background: #ffffff; }}
        """)
        radio.clicked.connect(callback)
        description_label = QLabel(description)
        description_label.setWordWrap(True)
        description_label.setStyleSheet("font-size: 10px; color: #7c8580; margin-left: 26px; margin-bottom: 3px;")
        parent.layout().addWidget(radio)
        parent.layout().addWidget(description_label)
        return radio

    def _build_power_card(self) -> QFrame:
        card = self._section_card("◴", "Режим использования системы", "Выберите баланс автономности, шума и производительности. Сочетание Fn+F меняет профиль, если это поддерживает устройство.")
        group = QButtonGroup(card)
        current = get_power_profile()
        for title, description, profile in (
            ("Бесшумно", "Для веб-сайтов, чтения и онлайн-встреч.", "power-saver"),
            ("Обычный", "Для повседневной работы и офисных задач.", "balanced"),
            ("Производительность", "Для ресурсоёмких приложений, игр и рендеринга.", "performance"),
        ):
            radio = self._radio_option(card, title, description, current == profile, lambda checked=False, value=profile: set_power_profile(value))
            group.addButton(radio)
        return card

    def _build_battery_card(self) -> QFrame:
        card = self._section_card("◉", "Аккумулятор и зарядка через USB", "Режим заряда аккумулятора")
        group = QButtonGroup(card)
        limit = self.config.get("charge_limit", 100)
        radio_80 = self._radio_option(card, "Оптимизированная зарядка аккум.", "Рекомендуется. Заряд останавливается на 80%, чтобы снизить износ аккумулятора.", limit == 80, lambda: self._set_charge_limit(80))
        radio_100 = self._radio_option(card, "Зарядка аккум. до полной ёмкости", "Используйте, когда нужна максимальная автономность.", limit != 80, lambda: self._set_charge_limit(100))
        group.addButton(radio_80)
        group.addButton(radio_100)
        more = QLabel("См. дополнительную информацию о состоянии аккумулятора  ›")
        more.setStyleSheet(f"font-size: 10px; color: {ACCENT}; font-weight: 700; margin: 4px 0 8px;")
        card.layout().addWidget(more)
        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background: #e3eae6; border: 0;")
        card.layout().addWidget(separator)
        usb_title = QLabel("Зарядка через USB при выключенном питании")
        usb_title.setStyleSheet("font-size: 13px; color: #59635e; font-weight: 700; margin-top: 5px;")
        usb_text = QLabel("Управление этой функцией зависит от EC конкретной модели Acer и будет активно только на поддерживаемом устройстве.")
        usb_text.setWordWrap(True)
        usb_text.setStyleSheet("font-size: 10px; color: #7c8580;")
        card.layout().addWidget(usb_title)
        card.layout().addWidget(usb_text)
        return card

    def _build_screen_card(self) -> QFrame:
        card = self._section_card("◒", "Экран", "BluelightShield")
        description = QLabel("Применяет тёплый цветовой фильтр через hyprsunset или wlsunset, когда одна из утилит доступна в системе.")
        description.setWordWrap(True)
        description.setStyleSheet("font-size: 11px; color: #737c77;")
        controls = QHBoxLayout()
        controls.setContentsMargins(0, 4, 0, 0)
        self.toggle_bluelight = ToggleSwitch()
        self.toggle_bluelight.setChecked(self.config.get("bluelight_enabled", False))
        self.toggle_bluelight.toggled.connect(self.toggle_night_light)
        self.temp_slider = QSlider(Qt.Orientation.Horizontal)
        self.temp_slider.setRange(2500, 6500)
        self.temp_slider.setValue(self.config.get("bluelight_temp", 4500))
        self.temp_slider.setFixedWidth(170)
        self.temp_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{ border-radius: 3px; height: 6px; background: #dcebe4; }}
            QSlider::handle:horizontal {{ background: {ACCENT}; width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; }}
            QSlider::sub-page:horizontal {{ background: #9cd6bb; border-radius: 3px; }}
        """)
        self.temp_slider.valueChanged.connect(self._update_temp_label)
        self.temp_slider.sliderReleased.connect(self.apply_night_light)
        self.temp_label = QLabel(f"{self.temp_slider.value()} K")
        self.temp_label.setStyleSheet("font-size: 12px; color: #59635e; font-weight: 700;")
        controls.addWidget(QLabel("Фильтр синего:"))
        controls.addWidget(self.toggle_bluelight)
        controls.addSpacing(12)
        controls.addWidget(self.temp_slider)
        controls.addWidget(self.temp_label)
        controls.addStretch(1)
        card.layout().addWidget(description)
        card.layout().addLayout(controls)
        return card

    def _show_section(self, section: QFrame, button: QPushButton):
        button.setChecked(True)
        self.scroll.ensureWidgetVisible(section, 0, 20)

    def _set_charge_limit(self, limit: int):
        if set_charge_limit(limit):
            self.config["charge_limit"] = limit

    def _update_temp_label(self, value: int):
        self.temp_label.setText(f"{value} K")

    def toggle_night_light(self, enabled: bool):
        save_config({"bluelight_enabled": enabled})
        self.apply_night_light()

    def apply_night_light(self):
        temperature = self.temp_slider.value()
        save_config({"bluelight_temp": temperature})
        tool = "hyprsunset" if shutil.which("hyprsunset") else "wlsunset" if shutil.which("wlsunset") else None
        if self.night_proc:
            try:
                self.night_proc.terminate()
                self.night_proc.wait(timeout=1)
            except (OSError, subprocess.SubprocessError):
                pass
            self.night_proc = None
        if self.toggle_bluelight.isChecked() and tool:
            self.night_proc = subprocess.Popen([tool, "-t", str(temperature)])

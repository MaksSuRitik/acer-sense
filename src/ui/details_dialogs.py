from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QFrame,
                              QLabel, QScrollArea, QVBoxLayout, QWidget)

from core.sensors import get_battery_info
from core.system_info import get_system_info
from ui.theme import theme_manager


class DetailsDialog(QDialog):
    def __init__(self, title: str, rows: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(640, 500)
        self.setMinimumSize(480, 340)

        pal = theme_manager.palette
        self.setStyleSheet(f"""
            QDialog {{
                background: {pal.bg_main};
                color: {pal.text_primary};
                font-family: 'Inter', 'Noto Sans', sans-serif;
            }}
            QLabel#dlg-title {{
                font-size: 18px; font-weight: 700; color: {pal.text_primary};
                padding-bottom: 4px;
            }}
            QLabel#key {{
                color: {pal.text_muted}; font-size: 12px;
                min-width: 160px; padding-top: 1px;
            }}
            QLabel#value {{
                color: {pal.text_primary}; font-size: 12px; font-weight: 600;
            }}
            QFrame#row {{
                background: {pal.bg_card};
                border: 1px solid {pal.border};
                border-radius: 10px;
            }}
            QPushButton {{
                min-width: 88px; padding: 7px 16px;
                border: 1px solid {pal.border}; border-radius: 14px;
                color: {pal.accent}; background: {pal.bg_card};
                font-size: 12px; font-weight: 600;
            }}
            QPushButton:hover {{ background: {pal.tab_hover}; border-color: {pal.accent}; }}
            QScrollBar:vertical {{ width: 7px; background: transparent; }}
            QScrollBar::handle:vertical {{
                background: {pal.border}; border-radius: 3px; min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(14)

        heading = QLabel(title)
        heading.setObjectName("dlg-title")
        layout.addWidget(heading)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: 0; background: transparent; }")

        content = QWidget()
        rows_layout = QVBoxLayout(content)
        rows_layout.setContentsMargins(0, 4, 4, 8)
        rows_layout.setSpacing(6)

        for key, value in rows:
            frame = QFrame()
            frame.setObjectName("row")
            form = QFormLayout(frame)
            form.setContentsMargins(14, 10, 14, 10)
            form.setHorizontalSpacing(20)
            form.setVerticalSpacing(4)
            form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

            key_label = QLabel(key)
            key_label.setObjectName("key")

            value_label = QLabel(value or "Недоступно")
            value_label.setObjectName("value")
            value_label.setWordWrap(True)
            if "\n" in (value or ""):
                key_label.setAlignment(Qt.AlignmentFlag.AlignTop)

            form.addRow(key_label, value_label)
            rows_layout.addWidget(frame)

        rows_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class SystemInfoDialog(DetailsDialog):
    def __init__(self, parent=None):
        info = get_system_info()
        rows = [
            ("Модель ноутбука",   info.get("product_name", "Acer")),
            ("Серийный номер",    info.get("serial_number", "—")),
            ("Версия BIOS",       info.get("bios_version", "—")),
            ("Процессор",         info.get("cpu_model", "—")),
            ("Оперативная память",info.get("ram_total", "—")),
            ("Графика",           info.get("gpu", "—")),
            ("Операционная система", info.get("os_pretty", "Linux")),
            ("Версия ядра",       info.get("kernel", "—")),
        ]
        super().__init__("Сведения о системе", rows, parent)


class BatteryInfoDialog(DetailsDialog):
    def __init__(self, parent=None):
        info = get_battery_info()
        health = f"{info['health_percent']}%" if info.get("health_percent") else "Недоступно"
        cycles = str(info["cycles"]) if info.get("cycles") is not None else "Недоступно"
        temp = f"{info['temperature']}°C" if info.get("temperature") is not None else "Недоступно"
        status = "Подключено к сети (AC)" if info.get("plugged") else "Работа от аккумулятора"

        rows = [
            ("Текущий уровень заряда", f"{info.get('percent', '—')}%"),
            ("Статус питания",        status),
            ("Остаточная ёмкость (Health)", health),
            ("Количество циклов заряда", cycles),
            ("Температура аккумулятора", temp),
            ("Статус контроллера",    info.get("status", "—")),
        ]
        super().__init__("Сведения об аккумуляторе", rows, parent)

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QFrame,
                              QLabel, QScrollArea, QVBoxLayout, QWidget)

from core.sensors import get_battery_info
from core.system_info import get_system_info


class DetailsDialog(QDialog):
    def __init__(self, title: str, rows: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(640, 500)
        self.setMinimumSize(480, 340)
        self.setStyleSheet("""
            QDialog {
                background: #f4f6f5;
                color: #505954;
                font-family: 'Inter', 'Noto Sans', sans-serif;
            }
            QLabel#dlg-title {
                font-size: 18px; font-weight: 700; color: #2e3934;
                padding-bottom: 4px;
            }
            QLabel#key {
                color: #6b7872; font-size: 12px;
                min-width: 160px; padding-top: 1px;
            }
            QLabel#value {
                color: #313935; font-size: 12px; font-weight: 600;
            }
            QFrame#row {
                background: #ffffff;
                border: 1px solid #dde9e4;
                border-radius: 10px;
            }
            QPushButton {
                min-width: 88px; padding: 7px 16px;
                border: 1px solid #82c4a6; border-radius: 14px;
                color: #3a8264; background: #ffffff;
                font-size: 12px;
            }
            QPushButton:hover { background: #edf8f2; }
            QScrollBar:vertical { width: 7px; background: transparent; }
            QScrollBar::handle:vertical {
                background: #b8d9c9; border-radius: 3px; min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
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
            # Для multiline-значений (графика, температуры) использовать
            # выравнивание по верху ключа
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


class BatteryInfoDialog(DetailsDialog):
    def __init__(self, parent=None):
        battery = get_battery_info()

        status_map = {
            "Charging":    "Заряжается",
            "Discharging": "Разряжается",
            "Full":        "Полный заряд",
            "Not charging":"Не заряжается",
            "Unknown":     "Неизвестно",
        }
        status = status_map.get(battery["status"], battery["status"])

        rows = [
            ("Состояние",          status),
            ("Текущий заряд",
             f"{battery['percent']}%" if battery["percent"] is not None else "Недоступно"),
            ("Питание",
             "Зарядное устройство подключено" if battery["plugged"] else "Питание от аккумулятора"),
            ("Остаточная ёмкость",
             f"{battery['health_percent']}% от заводской"
             if battery["health_percent"] is not None else "Недоступно"),
            ("Температура",
             f"{battery['temperature']}°C"
             if battery.get("temperature") is not None else "Недоступно"),
            ("Циклы перезарядки",
             str(battery["cycles"]) if battery["cycles"] is not None else "Недоступно"),
        ]
        super().__init__("Состояние аккумулятора", rows, parent)


class SystemInfoDialog(DetailsDialog):
    def __init__(self, parent=None):
        super().__init__("Сведения о системе", get_system_info(), parent)

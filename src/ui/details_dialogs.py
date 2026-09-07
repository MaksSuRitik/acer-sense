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
        self.resize(610, 470)
        self.setMinimumSize(460, 330)
        self.setStyleSheet("""
            QDialog { background: #f7f8f6; color: #505954; font-family: 'Inter', 'Noto Sans', sans-serif; }
            QLabel#title { font-size: 19px; font-weight: 700; color: #404944; }
            QLabel#key { color: #718079; font-size: 12px; }
            QLabel#value { color: #48534d; font-size: 12px; font-weight: 600; }
            QFrame#row { background: #ffffff; border: 1px solid #e2e9e5; border-radius: 9px; }
            QPushButton { min-width: 88px; padding: 7px 14px; border: 1px solid #71b899; border-radius: 14px; color: #438b6d; background: #ffffff; }
            QPushButton:hover { background: #edf8f2; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        heading = QLabel(title)
        heading.setObjectName("title")
        layout.addWidget(heading)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        rows_layout = QVBoxLayout(content)
        rows_layout.setContentsMargins(0, 8, 4, 8)
        rows_layout.setSpacing(7)
        for key, value in rows:
            frame = QFrame()
            frame.setObjectName("row")
            form = QFormLayout(frame)
            form.setContentsMargins(12, 9, 12, 9)
            form.setHorizontalSpacing(24)
            form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            key_label = QLabel(key)
            key_label.setObjectName("key")
            value_label = QLabel(value or "Недоступно")
            value_label.setObjectName("value")
            value_label.setWordWrap(True)
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
        rows = [
            ("Состояние", battery["status"]),
            ("Текущий заряд", f"{battery['percent']}%" if battery["percent"] is not None else "Недоступно"),
            ("Питание", "Подключено" if battery["plugged"] else "От аккумулятора"),
            ("Остаточная ёмкость", f"{battery['health_percent']}% от заводской" if battery["health_percent"] is not None else "Недоступно"),
            ("Циклы перезарядки", str(battery["cycles"]) if battery["cycles"] is not None else "Недоступно"),
        ]
        super().__init__("Состояние аккумулятора", rows, parent)


class SystemInfoDialog(DetailsDialog):
    def __init__(self, parent=None):
        super().__init__("Сведения о системе", get_system_info(), parent)

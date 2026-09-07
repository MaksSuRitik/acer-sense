from __future__ import annotations

from datetime import datetime
import threading

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QMessageBox,
                             QProgressBar, QPushButton, QScrollArea,
                             QVBoxLayout, QWidget)

from core.diagnostics import CRITICAL, GOOD, UNKNOWN, WARNING, run_deep_check
from core.sensors import get_battery_info, get_ram_info
from core.storage import get_physical_drives
from core.trash import empty_trash, format_size, get_trash_stats
from ui.details_dialogs import SystemInfoDialog


ACCENT = "#4ba781"
STATUS_STYLE = {
    GOOD: ("Хорошее", "#469d79"),
    WARNING: ("Требует внимания", "#b77b27"),
    CRITICAL: ("Обнаружена проблема", "#c45151"),
    UNKNOWN: ("Недоступно", "#7d8581"),
}


class DeepCheckWorker(QThread):
    progress_changed = pyqtSignal(str, int, str)
    result_ready = pyqtSignal(str, object)
    complete = pyqtSignal()

    def __init__(self, tasks: list[tuple[str, dict | None]], memory_duration_seconds: int = 150, parent=None):
        super().__init__(parent)
        self.tasks = tasks
        self.memory_duration_seconds = memory_duration_seconds
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        for card_id, payload in self.tasks:
            if self.cancel_event.is_set():
                break
            result = run_deep_check(
                card_id,
                payload,
                lambda value, text, current=card_id: self.progress_changed.emit(current, value, text),
                self.cancel_event,
                self.memory_duration_seconds,
            )
            self.result_ready.emit(card_id, result)
        self.complete.emit()


class CheckupTab(QWidget):
    """Acer Sense-like detailed diagnostics; the memory workload is safely bounded."""

    def __init__(self):
        super().__init__()
        self.cards: dict[str, dict] = {}
        self.worker: DeepCheckWorker | None = None
        self.active_card_ids: list[str] = []
        self.drives = get_physical_drives()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: 0; background: transparent; }")
        content = QWidget()
        outer = QHBoxLayout(content)
        outer.setContentsMargins(100, 24, 100, 36)
        outer.setSpacing(16)

        main_column = QVBoxLayout()
        main_column.setSpacing(12)
        main_column.setAlignment(Qt.AlignmentFlag.AlignTop)
        main_column.addLayout(self._build_header())
        self._add_battery_card(main_column)
        for index, drive in enumerate(self.drives):
            self._add_drive_card(main_column, f"drive_{index}", drive)
        self._add_memory_card(main_column)
        self._add_system_card(main_column)
        main_column.addStretch(1)

        side_column = QVBoxLayout()
        side_column.setSpacing(14)
        side_column.setAlignment(Qt.AlignmentFlag.AlignTop)
        side_column.addWidget(self._build_system_info_card())
        side_column.addWidget(self._build_cleanup_card())
        side_column.addWidget(self._build_scope_card())
        side_column.addStretch(1)

        main_holder = QWidget()
        main_holder.setLayout(main_column)
        main_holder.setMinimumWidth(570)
        side_holder = QWidget()
        side_holder.setLayout(side_column)
        side_holder.setFixedWidth(270)
        outer.addWidget(main_holder, 1)
        outer.addWidget(side_holder)
        scroll.setWidget(content)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(16)
        left = QVBoxLayout()
        title = QLabel("Проверить")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #3f4743;")
        self.btn_check_all = QPushButton("⌕\nПроверить всё")
        self.btn_check_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_check_all.setFixedSize(142, 76)
        self.btn_check_all.setStyleSheet(f"""
            QPushButton {{ background: #bcebd9; color: #34795f; border: 1px solid #83c9aa; border-radius: 14px;
                            font-size: 13px; font-weight: 700; }}
            QPushButton:hover {{ background: #a9e2ca; }}
            QPushButton:disabled {{ color: #799a8d; background: #d8eee4; }}
        """)
        self.btn_check_all.clicked.connect(self.check_all)
        left.addWidget(title)
        left.addSpacing(3)
        left.addWidget(self.btn_check_all)
        header.addLayout(left)
        description = QLabel("Полная диагностика аккумулятора, накопителей, ОЗУ и датчиков. Проверка ОЗУ постепенно занимает безопасную часть свободной памяти и длится около 3 минут.")
        description.setWordWrap(True)
        description.setStyleSheet("font-size: 11px; line-height: 1.35; color: #77817c; padding-top: 23px;")
        header.addWidget(description, 1)
        return header

    def _card_frame(self) -> QFrame:
        card = QFrame()
        card.setObjectName("diagnosticCard")
        card.setStyleSheet("""
            QFrame#diagnosticCard { background: #ffffff; border: 1px solid #e1e8e4; border-radius: 16px; }
            QLabel { border: 0; background: transparent; }
        """)
        return card

    def _add_card(self, target: QVBoxLayout, card_id: str, icon: str, title: str,
                  overview: list[str], meter: int | None, payload: dict | None = None):
        card = self._card_frame()
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(6)
        heading = QLabel(f"{icon}  {title}")
        heading.setStyleSheet("font-size: 16px; color: #5c6560; font-weight: 700;")
        rule = QFrame()
        rule.setFixedHeight(1)
        rule.setStyleSheet("background: #cee5da; border: 0;")
        status = QLabel("Не проверено")
        status.setStyleSheet("font-size: 14px; color: #7c8580; font-weight: 700; margin-top: 3px;")
        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setTextVisible(False)
        progress.setFixedHeight(5)
        progress.setStyleSheet(f"QProgressBar {{ border: 0; background: #dcebe4; border-radius: 2px; }} QProgressBar::chunk {{ background: {ACCENT}; border-radius: 2px; }}")
        progress.hide()
        btn = QPushButton("Проверить")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(120, 28)
        btn.setStyleSheet(f"""
            QPushButton {{ background: #ffffff; color: #548a74; border: 1px solid #80bda4; border-radius: 14px;
                            font-size: 12px; font-weight: 600; }}
            QPushButton:hover {{ background: #edf8f2; }}
            QPushButton:disabled {{ color: #9bb6aa; border-color: #c8dbd1; }}
        """)
        checked_at = QLabel("Последняя проверка: —")
        checked_at.setStyleSheet("font-size: 10px; color: #98a19c;")
        left.addWidget(heading)
        left.addWidget(rule)
        left.addWidget(status)
        left.addWidget(progress)
        left.addWidget(btn)
        left.addWidget(checked_at)
        left.addStretch(1)

        detail_box = QFrame()
        detail_box.setObjectName("detailBox")
        detail_box.setStyleSheet("QFrame#detailBox { background: #fbfcfb; border: 0; border-radius: 8px; }")
        details = QVBoxLayout(detail_box)
        details.setContentsMargins(14, 10, 14, 10)
        details.setSpacing(5)
        overview_label = QLabel("\n".join(overview))
        overview_label.setWordWrap(True)
        overview_label.setStyleSheet("font-size: 11px; color: #6d7671;")
        details.addWidget(overview_label)
        if meter is not None:
            meter_line = QFrame()
            meter_line.setFixedHeight(7)
            meter_line.setObjectName("meter")
            meter_line.setStyleSheet(f"""
                QFrame#meter {{ border: 0; border-radius: 3px;
                  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {ACCENT}, stop:{max(0.01, min(1, meter / 100)):.2f} {ACCENT},
                    stop:{max(0.01, min(1, meter / 100)):.2f} #dcebe4, stop:1 #dcebe4); }}
            """)
            details.addWidget(meter_line)
        result_label = QLabel("")
        result_label.setWordWrap(True)
        result_label.setStyleSheet("font-size: 10px; color: #82908a; margin-top: 3px;")
        details.addWidget(result_label)
        details.addStretch(1)

        card_layout.addLayout(left, 1)
        card_layout.addWidget(detail_box, 1)
        target.addWidget(card)
        self.cards[card_id] = {
            "payload": payload, "button": btn, "status": status, "progress": progress,
            "date": checked_at, "result": result_label,
        }
        btn.clicked.connect(lambda checked=False, key=card_id: self.start_cards([key]))

    def _add_battery_card(self, target: QVBoxLayout):
        battery = get_battery_info()
        charge = battery["percent"]
        overview = [f"Заряд аккумулятора: {charge}%" if charge is not None else "Заряд аккумулятора: недоступен"]
        if battery["cycles"] is not None:
            overview.append(f"Количество циклов: {battery['cycles']}")
        self._add_card(target, "battery", "◉", "Аккумулятор", overview, charge)

    def _add_drive_card(self, target: QVBoxLayout, card_id: str, drive: dict):
        partitions = drive.get("partitions", [])
        overview = [f"{item['mount']}: свободно {item['free_gb']} ГБ, всего {item['total_gb']} ГБ" for item in partitions]
        used = max((item["percent"] for item in partitions), default=0)
        self._add_card(target, card_id, "▣", drive["model"], overview or ["Нет подключённых разделов"], used, drive)

    def _add_memory_card(self, target: QVBoxLayout):
        memory = get_ram_info()
        overview = [f"Использование RAM: {memory['percent']}%", f"Всего: {memory['total_gb']} ГБ", "Стресс-тест: до 8% свободной памяти, максимум 512 МБ"]
        self._add_card(target, "memory", "◌", "ОЗУ", overview, int(memory["percent"]))

    def _add_system_card(self, target: QVBoxLayout):
        self._add_card(target, "system", "◒", "Система и охлаждение", ["Пять замеров температурных датчиков за 10 секунд"], None)

    def _build_system_info_card(self) -> QFrame:
        card = self._card_frame()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        title = QLabel("Сведения о системе")
        title.setStyleSheet("font-size: 13px; font-weight: 700; color: #626b66;")
        text = QLabel("Версия ОС и ядра, модель устройства, BIOS, железо, аккумулятор и температуры.")
        text.setWordWrap(True)
        text.setStyleSheet("font-size: 11px; line-height: 1.45; color: #77817c;")
        button = QPushButton("Открыть сведения")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(f"QPushButton {{ border: 1px solid #80bda4; border-radius: 14px; color: #548a74; padding: 6px; font-size: 11px; font-weight: 600; background: #fff; }} QPushButton:hover {{ background: #edf8f2; }}")
        button.clicked.connect(self.open_system_info)
        layout.addWidget(title)
        layout.addWidget(text)
        layout.addWidget(button)
        return card

    def _build_cleanup_card(self) -> QFrame:
        card = self._card_frame()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        title = QLabel("Оптимизировать хранилище")
        title.setStyleSheet("font-size: 13px; font-weight: 700; color: #626b66;")
        self.trash_summary = QLabel("")
        self.trash_summary.setWordWrap(True)
        self.trash_summary.setStyleSheet("font-size: 10px; color: #7d8782;")
        button = QPushButton("Быстрая очистка")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(f"QPushButton {{ border: 1px solid #80bda4; border-radius: 14px; color: #548a74; padding: 6px; font-size: 11px; font-weight: 600; background: #fff; }} QPushButton:hover {{ background: #edf8f2; }}")
        button.clicked.connect(self.cleanup_trash)
        layout.addWidget(title)
        layout.addWidget(button)
        layout.addWidget(self.trash_summary)
        self._refresh_trash_summary()
        return card

    def _build_scope_card(self) -> QFrame:
        card = self._card_frame()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        title = QLabel("Что проверяется")
        title.setStyleSheet("font-size: 13px; font-weight: 700; color: #626b66;")
        text = QLabel("• статус и ёмкость аккумулятора\n• SMART и свободное место\n• стресс-тест ОЗУ с шаблонами\n• стабильность датчиков температуры")
        text.setStyleSheet("font-size: 11px; line-height: 1.5; color: #77817c;")
        text.setWordWrap(True)
        note = QLabel("SMART работает только на активных дисках и не запускает запись или самотест накопителя.")
        note.setWordWrap(True)
        note.setStyleSheet("font-size: 10px; color: #99a29e; margin-top: 6px;")
        layout.addWidget(title)
        layout.addWidget(text)
        layout.addWidget(note)
        return card

    def _refresh_trash_summary(self):
        stats = get_trash_stats()
        if stats["count"]:
            self.trash_summary.setText(f"В корзине: {stats['count']} файлов, {format_size(stats['size'])}")
        else:
            self.trash_summary.setText("Системная корзина текущего пользователя пуста")

    def open_system_info(self):
        SystemInfoDialog(self).exec()

    def cleanup_trash(self):
        stats = get_trash_stats()
        if not stats["count"]:
            QMessageBox.information(self, "Быстрая очистка", "Системная корзина текущего пользователя уже пуста.")
            return
        message = f"Удалить {stats['count']} файлов ({format_size(stats['size'])}) из ~/.local/share/Trash?\nВосстановить их после очистки нельзя."
        answer = QMessageBox.question(self, "Быстрая очистка", message, QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.Cancel)
        if answer != QMessageBox.StandardButton.Yes:
            return
        removed = empty_trash()
        self._refresh_trash_summary()
        QMessageBox.information(self, "Быстрая очистка", f"Удалено: {removed['count']} файлов, {format_size(removed['size'])}.")

    def check_all(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.btn_check_all.setEnabled(False)
            return
        self.start_cards(list(self.cards))

    def start_cards(self, card_ids: list[str]):
        if self.worker and self.worker.isRunning():
            return
        if "memory" in card_ids:
            answer = QMessageBox.question(
                self,
                "Стресс-проверка ОЗУ",
                "Проверка длится около 3 минут и временно использует до 8% свободной памяти (максимум 512 МБ). Продолжить?",
                QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.active_card_ids = card_ids
        tasks = [(card_id, self.cards[card_id]["payload"]) for card_id in card_ids]
        for card_id in card_ids:
            card = self.cards[card_id]
            card["button"].setEnabled(False)
            card["progress"].setValue(0)
            card["progress"].show()
            card["status"].setText("Подготовка…")
            card["status"].setStyleSheet("font-size: 14px; color: #548a74; font-weight: 700; margin-top: 3px;")
        self.btn_check_all.setText("Отменить")
        self.worker = DeepCheckWorker(tasks, parent=self)
        self.worker.progress_changed.connect(self.update_progress)
        self.worker.result_ready.connect(self.apply_result)
        self.worker.complete.connect(self.finish_scan)
        self.worker.start()

    def update_progress(self, card_id: str, value: int, text: str):
        card = self.cards[card_id]
        card["progress"].setValue(value)
        card["status"].setText(text)

    def apply_result(self, card_id: str, result: dict):
        card = self.cards[card_id]
        status_name, color = STATUS_STYLE[result["status"]]
        card["status"].setText(status_name)
        card["status"].setStyleSheet(f"font-size: 14px; color: {color}; font-weight: 700; margin-top: 3px;")
        details = result["details"]
        if card_id == "battery":
            details = [line for line in details if not line.startswith("Заряд:")]
        elif card_id.startswith("drive_"):
            details = [line for line in details if not line.startswith("/")]
        elif card_id == "memory":
            details = [line for line in details if not line.startswith("Используется:")]
        card["result"].setText("\n".join([result["headline"], *details]))
        card["date"].setText(f"Последняя проверка: {datetime.now().strftime('%d.%m.%Y %H:%M')}")

    def finish_scan(self):
        for card_id in self.active_card_ids:
            card = self.cards[card_id]
            card["button"].setEnabled(True)
            card["progress"].hide()
        self.active_card_ids = []
        self.btn_check_all.setEnabled(True)
        self.btn_check_all.setText("⌕\nПроверить всё")

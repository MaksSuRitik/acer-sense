from __future__ import annotations

from datetime import datetime
import subprocess
import threading
import webbrowser

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QFrame, QHBoxLayout,
                              QLabel, QMessageBox, QProgressBar, QPushButton,
                              QScrollArea, QTextEdit, QVBoxLayout, QWidget)

from core.diagnostics import CRITICAL, GOOD, UNKNOWN, WARNING, run_deep_check
from core.sensors import get_battery_info, get_ram_info
from core.storage import get_physical_drives
from core.trash import empty_trash, format_size, get_trash_stats
from ui.details_dialogs import SystemInfoDialog


ACCENT = "#4ba781"
STATUS_STYLE = {
    GOOD:     ("Хорошее",           "#469d79"),
    WARNING:  ("Требует внимания",   "#b77b27"),
    CRITICAL: ("Обнаружена проблема","#c45151"),
    UNKNOWN:  ("Недоступно",         "#7d8581"),
}
ACER_SUPPORT_URL = "https://www.acer.com/ru-ru/support"


# ──────────────────────────────────────────────────────────────────────────────
# Worker thread
# ──────────────────────────────────────────────────────────────────────────────

class DeepCheckWorker(QThread):
    progress_changed = pyqtSignal(str, int, str)
    result_ready     = pyqtSignal(str, object)
    complete         = pyqtSignal()

    def __init__(self, tasks: list[tuple[str, dict | None]],
                 memory_duration_seconds: int = 150, parent=None):
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
                card_id, payload,
                lambda value, text, cid=card_id: self.progress_changed.emit(cid, value, text),
                self.cancel_event,
                self.memory_duration_seconds,
            )
            self.result_ready.emit(card_id, result)
        self.complete.emit()


# ──────────────────────────────────────────────────────────────────────────────
# Диалог «Калибровка аккумулятора»
# ──────────────────────────────────────────────────────────────────────────────

class BatteryCalibrationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Калибровка аккумулятора")
        self.setModal(True)
        self.resize(520, 380)
        self.setStyleSheet("""
            QDialog { background: #f5f8f6; font-family: 'Inter','Noto Sans',sans-serif; }
            QLabel { color: #484f4b; }
            QTextEdit { background: #ffffff; border: 1px solid #d8e6de; border-radius: 8px;
                        color: #525b57; font-size: 11px; }
            QPushButton { min-width: 88px; padding: 7px 14px;
                          border: 1px solid #71b899; border-radius: 14px;
                          color: #438b6d; background: #fff; }
            QPushButton:hover { background: #edf8f2; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(12)

        title = QLabel("Калибровка аккумулятора")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #3a4440;")
        layout.addWidget(title)

        instructions = QTextEdit()
        instructions.setReadOnly(True)
        instructions.setFixedHeight(240)
        instructions.setMarkdown("""
**Зачем нужна калибровка?**

Со временем показания уровня заряда могут расходиться с реальной ёмкостью.
Калибровка позволяет точнее измерять оставшийся заряд.

**Шаги калибровки:**

1. Зарядите аккумулятор до **100%** при подключённом зарядном устройстве.
2. Оставьте ноутбук подключённым ещё **2 часа** после достижения 100%.
3. Отключите зарядное устройство.
4. Используйте ноутбук, пока не появится предупреждение о низком заряде (примерно 5%).
5. Подключите зарядное устройство и зарядите до **100%** не прерываясь.

**Рекомендуемая частота:** раз в 3–6 месяцев.

> ⚠ Не разряжайте аккумулятор до нуля — это может его повредить.
        """)
        layout.addWidget(instructions)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


# ──────────────────────────────────────────────────────────────────────────────
# Главный виджет вкладки
# ──────────────────────────────────────────────────────────────────────────────

class CheckupTab(QWidget):
    """Acer Sense-like detailed diagnostics; memory workload is safely bounded."""

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
        outer.setContentsMargins(20, 16, 20, 24)
        outer.setSpacing(18)

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
        side_column.setSpacing(12)
        side_column.setAlignment(Qt.AlignmentFlag.AlignTop)
        side_column.addWidget(self._build_battery_optimize_card())
        side_column.addWidget(self._build_cleanup_card())
        side_column.addWidget(self._build_system_info_card())
        side_column.addStretch(1)

        main_holder = QWidget()
        main_holder.setLayout(main_column)
        main_holder.setMinimumWidth(560)

        side_holder = QWidget()
        side_holder.setLayout(side_column)
        side_holder.setFixedWidth(280)

        outer.addWidget(main_holder, 1)
        outer.addWidget(side_holder)

        scroll.setWidget(content)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

    # ── Шапка ───────────────────────────────────────────────────────────────

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(16)

        left = QVBoxLayout()
        title = QLabel("Проверить")
        title.setStyleSheet("font-size: 14px; font-weight: 700; color: #3f4743;")

        self.btn_check_all = QPushButton("🔍  Проверить всё")
        self.btn_check_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_check_all.setFixedSize(156, 80)
        self.btn_check_all.setStyleSheet(f"""
            QPushButton {{
                background: #bcebd9; color: #2d7357;
                border: 1px solid #8dcfb2; border-radius: 16px;
                font-size: 13px; font-weight: 700;
            }}
            QPushButton:hover {{ background: #a9e2ca; }}
            QPushButton:disabled {{ color: #799a8d; background: #d8eee4; }}
        """)
        self.btn_check_all.clicked.connect(self.check_all)
        left.addWidget(title)
        left.addSpacing(3)
        left.addWidget(self.btn_check_all)
        header.addLayout(left)

        desc = QLabel(
            "Проверка работоспособности компонентов,\n"
            "включая аккумулятор, накопители и RAM."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 11px; line-height: 1.4; color: #7a847f; padding-top: 26px;")
        header.addWidget(desc, 1)

        # Ссылки справа
        links_layout = QVBoxLayout()
        links_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        links_layout.setSpacing(6)
        sys_info_link = QLabel(
            f"<a href='sysinfo' style='color:{ACCENT};text-decoration:none;"
            "font-size:11px;font-weight:600;'>Сведения о системе ⓘ</a>"
        )
        sys_info_link.setOpenExternalLinks(False)
        sys_info_link.linkActivated.connect(self.open_system_info)
        support_link = QLabel(
            f"<a href='support' style='color:{ACCENT};text-decoration:none;"
            "font-size:11px;font-weight:600;'>Техническая поддержка ⓘ</a>"
        )
        support_link.setOpenExternalLinks(False)
        support_link.linkActivated.connect(lambda: webbrowser.open(ACER_SUPPORT_URL))
        links_layout.addWidget(sys_info_link)
        links_layout.addWidget(support_link)
        header.addLayout(links_layout)
        return header

    # ── Фабрика карточек ─────────────────────────────────────────────────────

    def _card_frame(self) -> QFrame:
        card = QFrame()
        card.setObjectName("diagnosticCard")
        card.setStyleSheet("""
            QFrame#diagnosticCard { background: #ffffff; border: 1px solid #dde8e3; border-radius: 16px; }
            QLabel { border: 0; background: transparent; }
        """)
        return card

    def _colored_bar(self, percent: int) -> QFrame:
        """Горизонтальная полоска прогресса (как на скриншотах)."""
        bar = QFrame()
        bar.setFixedHeight(7)
        bar.setObjectName("driveBar")
        filled = max(0.01, min(1.0, percent / 100))
        color = ACCENT if percent < 85 else ("#e6a020" if percent < 95 else "#c44040")
        bar.setStyleSheet(f"""
            QFrame#driveBar {{
                border: 0; border-radius: 3px;
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {color}, stop:{filled:.3f} {color},
                    stop:{min(filled + 0.001, 1.0):.3f} #ddeae2, stop:1 #ddeae2);
            }}
        """)
        return bar

    def _add_card(self, target: QVBoxLayout, card_id: str, icon: str, title: str,
                  overview_widget: QWidget | None, payload: dict | None = None):
        card = self._card_frame()
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(18)

        # Левая панель: статус + кнопка
        left = QVBoxLayout()
        left.setSpacing(6)
        left.setAlignment(Qt.AlignmentFlag.AlignTop)

        heading = QLabel(f"{icon}  {title}")
        heading.setStyleSheet("font-size: 15px; color: #515a56; font-weight: 700;")

        rule = QFrame()
        rule.setFixedHeight(1)
        rule.setStyleSheet("background: #cbe5d9; border: 0;")

        status = QLabel("Не проверено")
        status.setStyleSheet("font-size: 13px; color: #7c8580; font-weight: 700; margin-top: 2px;")

        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setTextVisible(False)
        progress.setFixedHeight(5)
        progress.setStyleSheet(f"""
            QProgressBar {{ border: 0; background: #dceae3; border-radius: 2px; }}
            QProgressBar::chunk {{ background: {ACCENT}; border-radius: 2px; }}
        """)
        progress.hide()

        btn = QPushButton("Проверить")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(128, 30)
        btn.setStyleSheet(f"""
            QPushButton {{ background: #fff; color: #4d8a73; border: 1px solid #88c2a8;
                           border-radius: 15px; font-size: 12px; font-weight: 600; }}
            QPushButton:hover {{ background: #edf8f2; }}
            QPushButton:disabled {{ color: #a0b8ae; border-color: #c5dbd2; }}
        """)

        checked_at = QLabel("Последняя проверка: —")
        checked_at.setStyleSheet("font-size: 10px; color: #9ea8a2;")

        left.addWidget(heading)
        left.addWidget(rule)
        left.addWidget(status)
        left.addWidget(progress)
        left.addWidget(btn)
        left.addWidget(checked_at)
        left.addStretch(1)

        card_layout.addLayout(left, 1)
        if overview_widget:
            card_layout.addWidget(overview_widget, 2)

        target.addWidget(card)
        self.cards[card_id] = {
            "payload": payload, "button": btn, "status": status,
            "progress": progress, "date": checked_at, "result": QLabel(),
        }
        btn.clicked.connect(lambda _, key=card_id: self.start_cards([key]))

    # ── Конкретные карточки ───────────────────────────────────────────────────

    def _add_battery_card(self, target: QVBoxLayout):
        battery = get_battery_info()
        charge = battery["percent"]
        temp = battery.get("temperature")
        cycles = battery.get("cycles")

        detail = QFrame()
        detail.setObjectName("detailBox")
        detail.setStyleSheet("QFrame#detailBox { background: #f9fafa; border: 0; border-radius: 8px; }")
        dv = QVBoxLayout(detail)
        dv.setContentsMargins(12, 10, 12, 10)
        dv.setSpacing(6)

        def _row(label: str, value: str):
            lbl = QLabel(f"<b style='color:#5a6560;font-size:11px;'>{label}</b>")
            lbl.setTextFormat(Qt.TextFormat.RichText)
            dv.addWidget(lbl)
            if charge is not None and label == "Заряд аккумулятора":
                bar = self._colored_bar(charge)
                dv.addWidget(bar)
            val_lbl = QLabel(value)
            val_lbl.setStyleSheet("font-size: 11px; color: #6b7470;")
            dv.addWidget(val_lbl)

        charge_str = f"{charge}%" if charge is not None else "Недоступен"
        _row("Заряд аккумулятора", charge_str)
        if temp is not None:
            _row("Температура", f"{temp}°C")
        if cycles is not None:
            _row("Количество циклов", str(cycles))

        # Кнопка детальных сведений
        btn_card_details = QPushButton("Детальные сведения об аккумуляторе ›")
        btn_card_details.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_card_details.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                background: transparent;
                border: 0;
                color: {ACCENT};
                font-size: 11px;
                font-weight: 600;
                padding: 6px 0 2px 0;
            }}
            QPushButton:hover {{
                color: #27684d;
                text-decoration: underline;
            }}
        """)
        btn_card_details.clicked.connect(self._open_battery_info)
        dv.addWidget(btn_card_details)

        dv.addStretch(1)

        self._add_card(target, "battery", "■", "Аккумулятор", detail)

    def _add_drive_card(self, target: QVBoxLayout, card_id: str, drive: dict):
        detail = QFrame()
        detail.setObjectName("detailBox")
        detail.setStyleSheet("QFrame#detailBox { background: #f9fafa; border: 0; border-radius: 8px; }")
        dv = QVBoxLayout(detail)
        dv.setContentsMargins(12, 10, 12, 10)
        dv.setSpacing(5)

        for part in drive.get("partitions", []):
            mount_lbl = QLabel(part["mount"])
            mount_lbl.setStyleSheet("font-size: 11px; color: #585f5c; font-weight: 600;")
            dv.addWidget(mount_lbl)
            dv.addWidget(self._colored_bar(int(part["percent"])))
            info = QLabel(f"осталось {part['free_gb']} ГБ, всего {part['total_gb']} ГБ")
            info.setStyleSheet("font-size: 10px; color: #7a8480;")
            dv.addWidget(info)
        dv.addStretch(1)

        self._add_card(target, card_id, "◉", drive["model"], detail, drive)

    def _add_memory_card(self, target: QVBoxLayout):
        memory = get_ram_info()
        detail = QFrame()
        detail.setObjectName("detailBox")
        detail.setStyleSheet("QFrame#detailBox { background: #f9fafa; border: 0; border-radius: 8px; }")
        dv = QVBoxLayout(detail)
        dv.setContentsMargins(12, 10, 12, 10)
        dv.setSpacing(5)

        ram_lbl = QLabel("Использование RAM")
        ram_lbl.setStyleSheet("font-size: 11px; color: #585f5c; font-weight: 600;")
        dv.addWidget(ram_lbl)
        dv.addWidget(self._colored_bar(int(memory["percent"])))
        dv.addWidget(QLabel(f"{memory['percent']}%  ({memory['used_gb']} / {memory['total_gb']} ГБ)"))
        note = QLabel("Стресс-тест ОЗУ: до 8% свободной памяти, не более 512 МБ")
        note.setWordWrap(True)
        note.setStyleSheet("font-size: 10px; color: #95a09a; margin-top: 6px;")
        dv.addWidget(note)
        dv.addStretch(1)

        self._add_card(target, "memory", "◈", "ОЗУ", detail)

    def _add_system_card(self, target: QVBoxLayout):
        detail = QFrame()
        detail.setObjectName("detailBox")
        detail.setStyleSheet("QFrame#detailBox { background: #f9fafa; border: 0; border-radius: 8px; }")
        dv = QVBoxLayout(detail)
        dv.setContentsMargins(12, 10, 12, 10)
        dv.setSpacing(4)
        note = QLabel("Пять замеров температурных датчиков за 10 секунд.\n"
                      "Результат включает все доступные тепловые зоны.")
        note.setWordWrap(True)
        note.setStyleSheet("font-size: 11px; color: #7a8480;")
        dv.addWidget(note)
        dv.addStretch(1)
        self._add_card(target, "system", "◌", "Система и охлаждение", detail)

    # ── Боковые карточки ──────────────────────────────────────────────────────

    def _side_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #dde8e3;"
                           "border-radius: 14px; } QLabel { border: 0; background: transparent; }")
        return card

    def _build_battery_optimize_card(self) -> QFrame:
        card = self._side_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        title = QLabel("Оптимизировать аккумулятор")
        title.setStyleSheet("font-size: 12px; font-weight: 700; color: #576059;")
        layout.addWidget(title)

        btn_calib = QPushButton("Калибровка аккумулятора")
        btn_calib.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_calib.setStyleSheet(f"""
            QPushButton {{ border: 1px solid #88c2a8; border-radius: 14px; color: #4d8a73;
                           padding: 7px; font-size: 11px; font-weight: 600; background: #fff; }}
            QPushButton:hover {{ background: #edf8f2; }}
        """)
        btn_calib.clicked.connect(self.open_calibration)
        layout.addWidget(btn_calib)

        last = QLabel("Последняя проверка: —")
        last.setStyleSheet("font-size: 10px; color: #9aa3a0;")
        layout.addWidget(last)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #dde9e3; border: 0;")
        layout.addWidget(sep)

        # Кнопка детальных сведений об аккумуляторе
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
                color: #27684d;
                text-decoration: underline;
            }}
        """)
        btn_details.clicked.connect(self._open_battery_info)
        layout.addWidget(btn_details)
        return card

    def _build_cleanup_card(self) -> QFrame:
        card = self._side_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        title = QLabel("Оптимизировать хранилище")
        title.setStyleSheet("font-size: 12px; font-weight: 700; color: #576059;")
        layout.addWidget(title)

        btn = QPushButton("Быстрая очистка")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{ border: 1px solid #88c2a8; border-radius: 14px; color: #4d8a73;
                           padding: 7px; font-size: 11px; font-weight: 600; background: #fff; }}
            QPushButton:hover {{ background: #edf8f2; }}
        """)
        btn.clicked.connect(self.cleanup_trash)
        layout.addWidget(btn)

        self.trash_summary = QLabel("")
        self.trash_summary.setWordWrap(True)
        self.trash_summary.setStyleSheet("font-size: 10px; color: #828c88;")
        layout.addWidget(self.trash_summary)

        self._refresh_trash_summary()
        return card

    def _build_system_info_card(self) -> QFrame:
        card = self._side_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        title = QLabel("Сведения о системе")
        title.setStyleSheet("font-size: 12px; font-weight: 700; color: #576059;")
        layout.addWidget(title)

        text = QLabel("Версия ОС, ядра, железо, аккумулятор, температуры.")
        text.setWordWrap(True)
        text.setStyleSheet("font-size: 10px; color: #7d8782;")
        layout.addWidget(text)

        btn = QPushButton("Открыть сведения")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{ border: 1px solid #88c2a8; border-radius: 14px; color: #4d8a73;
                           padding: 7px; font-size: 11px; font-weight: 600; background: #fff; }}
            QPushButton:hover {{ background: #edf8f2; }}
        """)
        btn.clicked.connect(self.open_system_info)
        layout.addWidget(btn)
        return card

    # ── Действия ──────────────────────────────────────────────────────────────

    def _refresh_trash_summary(self):
        stats = get_trash_stats()
        if stats["count"]:
            self.trash_summary.setText(
                f"Освободится {format_size(stats['size'])} дискового пространства"
            )
        else:
            self.trash_summary.setText("Корзина текущего пользователя пуста")

    def open_system_info(self, *_):
        SystemInfoDialog(self).exec()

    def open_calibration(self):
        BatteryCalibrationDialog(self).exec()

    def _open_battery_info(self, *_):
        from ui.details_dialogs import BatteryInfoDialog
        BatteryInfoDialog(self).exec()

    def cleanup_trash(self):
        stats = get_trash_stats()
        if not stats["count"]:
            QMessageBox.information(self, "Быстрая очистка",
                                    "Корзина текущего пользователя уже пуста.")
            return
        msg = (f"Удалить {stats['count']} файлов ({format_size(stats['size'])}) "
               f"из ~/.local/share/Trash?\nВосстановить их после очистки нельзя.")
        ans = QMessageBox.question(
            self, "Быстрая очистка", msg,
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        removed = empty_trash()
        self._refresh_trash_summary()
        QMessageBox.information(self, "Быстрая очистка",
                                f"Удалено: {removed['count']} файлов, {format_size(removed['size'])}.")

    # ── Управление диагностикой ───────────────────────────────────────────────

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
            ans = QMessageBox.question(
                self, "Стресс-проверка ОЗУ",
                "Проверка длится около 3 минут и временно использует до 8% свободной памяти "
                "(максимум 512 МБ). Продолжить?",
                QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.Cancel,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return

        self.active_card_ids = card_ids
        tasks = [(cid, self.cards[cid]["payload"]) for cid in card_ids]
        for cid in card_ids:
            c = self.cards[cid]
            c["button"].setEnabled(False)
            c["progress"].setValue(0)
            c["progress"].show()
            c["status"].setText("Подготовка…")
            c["status"].setStyleSheet("font-size: 13px; color: #4d8a73; font-weight: 700; margin-top: 2px;")

        self.btn_check_all.setText("✕  Отменить")
        self.worker = DeepCheckWorker(tasks, parent=self)
        self.worker.progress_changed.connect(self.update_progress)
        self.worker.result_ready.connect(self.apply_result)
        self.worker.complete.connect(self.finish_scan)
        self.worker.start()

    def update_progress(self, card_id: str, value: int, text: str):
        c = self.cards[card_id]
        c["progress"].setValue(value)
        c["status"].setText(text)

    def apply_result(self, card_id: str, result: dict):
        c = self.cards[card_id]
        status_name, color = STATUS_STYLE[result["status"]]
        c["status"].setText(status_name)
        c["status"].setStyleSheet(f"font-size: 13px; color: {color}; font-weight: 700; margin-top: 2px;")
        details = result["details"]
        if card_id == "battery":
            details = [ln for ln in details if not ln.startswith("Заряд:")]
        elif card_id.startswith("drive_"):
            details = [ln for ln in details if not ln.startswith("/")]
        elif card_id == "memory":
            details = [ln for ln in details if not ln.startswith("Используется:")]
        if c["result"].parent():
            c["result"].setText("\n".join([result["headline"], *details]))
        c["date"].setText(f"Последняя проверка: {datetime.now().strftime('%d.%m.%Y %H:%M')}")

    def finish_scan(self):
        for cid in self.active_card_ids:
            c = self.cards[cid]
            c["button"].setEnabled(True)
            c["progress"].hide()
        self.active_card_ids = []
        self.btn_check_all.setEnabled(True)
        self.btn_check_all.setText("🔍  Проверить всё")

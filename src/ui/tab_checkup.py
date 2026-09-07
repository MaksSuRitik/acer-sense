"""Diagnostics tab — matching official AcerSense layout with vector icons and deep tests."""
from __future__ import annotations

from datetime import datetime
import subprocess
import threading
import webbrowser

from PyQt6.QtCore import QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QFrame, QHBoxLayout,
                              QLabel, QMessageBox, QProgressBar, QPushButton,
                              QScrollArea, QTextEdit, QVBoxLayout, QWidget)

from core.diagnostics import CRITICAL, GOOD, UNKNOWN, WARNING, run_deep_check
from core.sensors import (get_battery_info, get_cpu_temp, get_gpu_temp,
                           get_ram_info)
from core.storage import get_physical_drives
from core.trash import empty_trash, format_size, get_trash_stats
from ui.details_dialogs import SystemInfoDialog
from ui.icons import render_svg_pixmap
from ui.theme import ThemePalette, theme_manager

STATUS_STYLE = {
    GOOD:     ("Хорошее",            "#42b582"),
    WARNING:  ("Требует внимания",    "#e6a020"),
    CRITICAL: ("Обнаружена проблема", "#e05252"),
    UNKNOWN:  ("Недоступно",          "#82918a"),
}
ACER_SUPPORT_URL = "https://www.acer.com/ru-ru/support"


# ─────────────────────────────────────────────────────────────────────────────
# Worker thread
# ─────────────────────────────────────────────────────────────────────────────

class DeepCheckWorker(QThread):
    progress_changed = pyqtSignal(str, int, str)
    result_ready     = pyqtSignal(str, object)
    complete         = pyqtSignal()

    def __init__(self, tasks: list[tuple[str, dict | None]],
                 memory_duration_seconds: int = 120, parent=None):
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


# ─────────────────────────────────────────────────────────────────────────────
# Battery calibration dialog
# ─────────────────────────────────────────────────────────────────────────────

class BatteryCalibrationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Калибровка аккумулятора")
        self.setModal(True)
        self.resize(520, 380)

        pal = theme_manager.palette
        self.setStyleSheet(f"""
            QDialog {{ background: {pal.bg_main}; font-family: 'Inter','Noto Sans',sans-serif; }}
            QLabel {{ color: {pal.text_primary}; }}
            QTextEdit {{ background: {pal.bg_card}; border: 1px solid {pal.border}; border-radius: 8px;
                        color: {pal.text_secondary}; font-size: 11px; }}
            QPushButton {{ min-width: 88px; padding: 7px 16px;
                          border: 1px solid {pal.border}; border-radius: 12px;
                          color: {pal.accent}; background: {pal.bg_card}; font-weight: 600; }}
            QPushButton:hover {{ background: {pal.tab_hover}; border-color: {pal.accent}; }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(12)

        title = QLabel("Калибровка аккумулятора")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {pal.text_primary};")
        layout.addWidget(title)

        instructions = QTextEdit()
        instructions.setReadOnly(True)
        instructions.setFixedHeight(240)
        instructions.setMarkdown("""
**Зачем нужна калибровка?**

Со временем из-за циклов заряд-разряд датчик уровня заряда может расходиться с реальной ёмкостью.
Калибровка позволяет контроллеру точно пересчитать полную ёмкость.

**Шаги калибровки:**

1. Зарядите аккумулятор до **100%** при подключённом блоке питания.
2. Оставьте ноутбук подключённым к сети ещё на **1.5–2 часа** после достижения 100%.
3. Отключите зарядное устройство и работайте от батареи до предупреждения о низком заряде (~5%).
4. Подключите зарядное устройство и зарядите до **100%** без перерыва.

**Рекомендуемая периодичность:** 1 раз в 3 месяца.
        """)
        layout.addWidget(instructions)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


# ─────────────────────────────────────────────────────────────────────────────
# Main tab widget
# ─────────────────────────────────────────────────────────────────────────────

class CheckupTab(QWidget):
    def __init__(self):
        super().__init__()
        self.cards: dict[str, dict] = {}
        self.worker: DeepCheckWorker | None = None
        self.active_card_ids: list[str] = []
        self.drives = get_physical_drives()
        self._all_card_frames: list[QFrame] = []
        self._icon_labels: list[tuple[QLabel, str]] = []
        self._all_progress_bars: list[QProgressBar] = []

        # Real-time widget tracking
        self._bat_bar: QFrame | None = None
        self._bat_charge_val: QLabel | None = None
        self._bat_temp_val: QLabel | None = None
        self._drive_part_widgets: dict[str, dict[str, tuple[QFrame, QLabel]]] = {}
        self._ram_bar: QFrame | None = None
        self._ram_val_lbl: QLabel | None = None
        self._sys_temp_lbl: QLabel | None = None

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
        self.opt_card = self._build_battery_optimize_card()
        self.clean_card = self._build_cleanup_card()
        self.info_card = self._build_system_info_card()
        side_column.addWidget(self.opt_card)
        side_column.addWidget(self.clean_card)
        side_column.addWidget(self.info_card)
        side_column.addStretch(1)

        main_holder = QWidget()
        main_holder.setLayout(main_column)
        main_holder.setMinimumWidth(540)

        side_holder = QWidget()
        side_holder.setLayout(side_column)
        side_holder.setFixedWidth(272)

        outer.addWidget(main_holder, 1)
        outer.addWidget(side_holder)

        scroll.setWidget(content)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        self.apply_theme(theme_manager.palette)
        theme_manager.theme_changed.connect(self.apply_theme)

        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self.update_realtime_metrics)
        self.monitor_timer.start(2000)
        self.update_realtime_metrics()

    # ── Header ──────────────────────────────────────────────────────────────

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(8)

        self.header_title = QLabel("Проверить")
        left.addWidget(self.header_title)

        self.btn_check_all = QPushButton("Проверить все")
        self.btn_check_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_check_all.setFixedHeight(38)
        self.btn_check_all.clicked.connect(self.check_all)
        left.addWidget(self.btn_check_all)
        header.addLayout(left)

        self.header_desc = QLabel(
            "Проверка работоспособности компонентов, включая аккумулятор, накопители и RAM."
        )
        self.header_desc.setWordWrap(True)
        header.addWidget(self.header_desc, 1)

        links_layout = QVBoxLayout()
        links_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        links_layout.setSpacing(6)

        self.sys_info_link = QLabel(
            f"<a href='sysinfo' style='text-decoration:none;font-size:11px;font-weight:600;'>"
            "Сведения о системе ></a>"
        )
        self.sys_info_link.setOpenExternalLinks(False)
        self.sys_info_link.linkActivated.connect(self.open_system_info)

        self.support_link = QLabel(
            f"<a href='support' style='text-decoration:none;font-size:11px;font-weight:600;'>"
            "Техническая поддержка ></a>"
        )
        self.support_link.setOpenExternalLinks(False)
        self.support_link.linkActivated.connect(lambda: webbrowser.open(ACER_SUPPORT_URL))

        links_layout.addWidget(self.sys_info_link)
        links_layout.addWidget(self.support_link)
        header.addLayout(links_layout)
        return header

    # ── Card factory ─────────────────────────────────────────────────────────

    def _card_frame(self) -> QFrame:
        card = QFrame()
        card.setObjectName("diagnosticCard")
        self._all_card_frames.append(card)
        return card

    def _update_bar(self, bar: QFrame, percent: int):
        pal = theme_manager.palette
        filled = max(0.01, min(1.0, percent / 100))
        color = pal.accent if percent < 85 else ("#e6a020" if percent < 95 else "#e05252")
        bar.setStyleSheet(f"""
            QFrame#driveBar {{
                border: 0; border-radius: 3px;
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {color}, stop:{filled:.3f} {color},
                    stop:{min(filled + 0.001, 1.0):.3f} {pal.progress_track}, stop:1 {pal.progress_track});
            }}
        """)

    def _colored_bar(self, percent: int) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(6)
        bar.setObjectName("driveBar")
        self._update_bar(bar, percent)
        return bar

    def _add_card(self, target: QVBoxLayout, card_id: str, icon_name: str, title: str,
                  overview_widget: QWidget | None, payload: dict | None = None):
        card = self._card_frame()
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(18)

        left = QVBoxLayout()
        left.setSpacing(6)
        left.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Header row: circular vector icon + title
        h_row = QHBoxLayout()
        h_row.setSpacing(8)

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(28, 28)
        self._icon_labels.append((icon_lbl, icon_name))
        h_row.addWidget(icon_lbl)

        heading = QLabel(title)
        heading.setObjectName("cardHeading")
        h_row.addWidget(heading)
        h_row.addStretch()
        left.addLayout(h_row)

        rule = QFrame()
        rule.setFixedHeight(1)
        rule.setObjectName("cardRule")
        left.addWidget(rule)

        status = QLabel("Не проверено")
        status.setObjectName("cardStatus")
        left.addWidget(status)

        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setTextVisible(False)
        progress.setFixedHeight(4)
        progress.hide()
        self._all_progress_bars.append(progress)
        left.addWidget(progress)

        btn = QPushButton("Проверить")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(110, 28)
        btn.setObjectName("cardButton")
        left.addWidget(btn)

        checked_at = QLabel("Последняя проверка: —")
        checked_at.setObjectName("cardDate")
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

    # ── Specific cards ───────────────────────────────────────────────────────

    def _add_battery_card(self, target: QVBoxLayout):
        battery = get_battery_info()
        charge  = battery["percent"]
        temp    = battery.get("temperature")
        cycles  = battery.get("cycles")

        detail = QFrame()
        detail.setObjectName("detailBox")
        dv = QVBoxLayout(detail)
        dv.setContentsMargins(12, 10, 12, 10)
        dv.setSpacing(6)

        lbl = QLabel("Заряд аккумулятора")
        lbl.setObjectName("detailLabel")
        dv.addWidget(lbl)
        self._bat_bar = self._colored_bar(charge if charge is not None else 0)
        dv.addWidget(self._bat_bar)

        self._bat_charge_val = QLabel(f"{charge}%" if charge is not None else "Недоступен")
        self._bat_charge_val.setObjectName("detailValue")
        dv.addWidget(self._bat_charge_val)

        t_lbl = QLabel("Температура аккумулятора")
        t_lbl.setObjectName("detailLabel")
        dv.addWidget(t_lbl)
        self._bat_temp_val = QLabel(f"{temp}°C" if temp is not None else "—")
        self._bat_temp_val.setObjectName("detailValue")
        dv.addWidget(self._bat_temp_val)

        if cycles is not None:
            c_lbl = QLabel("Количество циклов")
            c_lbl.setObjectName("detailLabel")
            dv.addWidget(c_lbl)
            c_val = QLabel(str(cycles))
            c_val.setObjectName("detailValue")
            dv.addWidget(c_val)

        btn_card_details = QPushButton("Информация о состоянии аккумулятора >")
        btn_card_details.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_card_details.setObjectName("textActionBtn")
        btn_card_details.clicked.connect(self._open_battery_info)
        dv.addWidget(btn_card_details)
        dv.addStretch(1)

        self._add_card(target, "battery", "battery_circle", "Аккумулятор", detail)

    def _add_drive_card(self, target: QVBoxLayout, card_id: str, drive: dict):
        detail = QFrame()
        detail.setObjectName("detailBox")
        dv = QVBoxLayout(detail)
        dv.setContentsMargins(12, 10, 12, 10)
        dv.setSpacing(5)

        self._drive_part_widgets[card_id] = {}
        for part in drive.get("partitions", []):
            mount = part["mount"]
            mount_lbl = QLabel(mount)
            mount_lbl.setObjectName("detailLabel")
            dv.addWidget(mount_lbl)
            bar = self._colored_bar(int(part["percent"]))
            dv.addWidget(bar)
            info = QLabel(f"осталось {part['free_gb']} GB, всего {part['total_gb']} GB ({part['percent']}%)")
            info.setObjectName("detailValue")
            dv.addWidget(info)
            self._drive_part_widgets[card_id][mount] = (bar, info)
        dv.addStretch(1)

        self._add_card(target, card_id, "ssd", drive["model"], detail, drive)

    def _add_memory_card(self, target: QVBoxLayout):
        memory = get_ram_info()
        detail = QFrame()
        detail.setObjectName("detailBox")
        dv = QVBoxLayout(detail)
        dv.setContentsMargins(12, 10, 12, 10)
        dv.setSpacing(5)

        ram_lbl = QLabel("Использование RAM (реальное время)")
        ram_lbl.setObjectName("detailLabel")
        dv.addWidget(ram_lbl)
        self._ram_bar = self._colored_bar(int(memory["percent"]))
        dv.addWidget(self._ram_bar)
        self._ram_val_lbl = QLabel(f"{memory['percent']}%  ({memory['used_gb']} / {memory['total_gb']} ГБ)")
        self._ram_val_lbl.setObjectName("detailValue")
        dv.addWidget(self._ram_val_lbl)

        note = QLabel("Глубокий 5-проходный стресс-тест ОЗУ (шаблоны битов, хеш-структуры, удержание ячеек, ECC).")
        note.setWordWrap(True)
        note.setObjectName("detailValue")
        dv.addWidget(note)
        dv.addStretch(1)

        self._add_card(target, "memory", "ram", "ОЗУ", detail)

    def _add_system_card(self, target: QVBoxLayout):
        detail = QFrame()
        detail.setObjectName("detailBox")
        dv = QVBoxLayout(detail)
        dv.setContentsMargins(12, 10, 12, 10)
        dv.setSpacing(4)

        self._sys_temp_lbl = QLabel("Мониторинг сенсоров: ЦП ...°C | GPU ...°C")
        self._sys_temp_lbl.setObjectName("detailLabel")
        dv.addWidget(self._sys_temp_lbl)

        note = QLabel(
            "Комплексный 45-секундный термотест под математической нагрузкой:\n"
            "• Замер начальной и пиковой температуры CPU и GPU (NVIDIA RTX 2050)\n"
            "• Оценка скорости отвода тепла и эффективности кулеров\n"
            "• Проверка аппаратного термотроттлинга"
        )
        note.setWordWrap(True)
        note.setObjectName("detailValue")
        dv.addWidget(note)
        dv.addStretch(1)
        self._add_card(target, "system", "cooling", "Охлаждение и система", detail)

    # ── Side cards ───────────────────────────────────────────────────────────

    def _side_card(self) -> QFrame:
        card = QFrame()
        self._all_card_frames.append(card)
        return card

    def _build_battery_optimize_card(self) -> QFrame:
        card = self._side_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        title = QLabel("Оптимизировать аккумулятор")
        title.setObjectName("sideCardTitle")
        layout.addWidget(title)

        btn_calib = QPushButton("Калибровка аккумулятора")
        btn_calib.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_calib.setObjectName("sideCardBtn")
        btn_calib.clicked.connect(self.open_calibration)
        layout.addWidget(btn_calib)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setObjectName("cardRule")
        layout.addWidget(sep)

        btn_details = QPushButton("Режим заряда аккумулятора >")
        btn_details.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_details.setObjectName("textActionBtn")
        btn_details.clicked.connect(self._open_battery_info)
        layout.addWidget(btn_details)
        return card

    def _build_cleanup_card(self) -> QFrame:
        card = self._side_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        title = QLabel("Оптимизировать хранилище")
        title.setObjectName("sideCardTitle")
        layout.addWidget(title)

        btn = QPushButton("Быстрая очистка")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setObjectName("sideCardBtn")
        btn.clicked.connect(self.cleanup_trash)
        layout.addWidget(btn)

        self.trash_summary = QLabel("")
        self.trash_summary.setWordWrap(True)
        self.trash_summary.setObjectName("detailValue")
        layout.addWidget(self.trash_summary)

        self._refresh_trash_summary()
        return card

    def _build_system_info_card(self) -> QFrame:
        card = self._side_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        title = QLabel("Сведения о системе")
        title.setObjectName("sideCardTitle")
        layout.addWidget(title)

        text = QLabel("Версия ОС, ядра, комплектующие ноутбука, драйверы.")
        text.setWordWrap(True)
        text.setObjectName("detailValue")
        layout.addWidget(text)

        btn = QPushButton("Открыть сведения")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setObjectName("sideCardBtn")
        btn.clicked.connect(self.open_system_info)
        layout.addWidget(btn)
        return card

    # ── Theme Application ──────────────────────────────────────────────────

    def apply_theme(self, pal: ThemePalette):
        self.header_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {pal.text_primary};")
        self.header_desc.setStyleSheet(f"font-size: 11px; line-height: 1.4; color: {pal.text_muted}; padding-top: 4px;")

        # "Проверить все" button with vector icon
        icon_pix = render_svg_pixmap("heart_check", "#ffffff", 20)
        self.btn_check_all.setIcon(QIcon(icon_pix))
        self.btn_check_all.setIconSize(icon_pix.size())
        self.btn_check_all.setStyleSheet(f"""
            QPushButton {{
                background: {pal.accent};
                color: #ffffff;
                border: none;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 700;
                padding: 0 20px;
            }}
            QPushButton:hover {{ background: {pal.accent_dark}; }}
            QPushButton:disabled {{ color: {pal.text_muted}; background: {pal.progress_track}; }}
        """)

        self.sys_info_link.setStyleSheet(f"color: {pal.accent}; font-size: 11px; font-weight: 600;")
        self.support_link.setStyleSheet(f"color: {pal.accent}; font-size: 11px; font-weight: 600;")

        # Render all circular card vector icons
        for icon_lbl, icon_name in self._icon_labels:
            pix = render_svg_pixmap(icon_name, pal.accent, 26)
            icon_lbl.setPixmap(pix)

        for card in self._all_card_frames:
            card.setStyleSheet(f"""
                QFrame {{
                    background: {pal.bg_card};
                    border: 1px solid {pal.border};
                    border-radius: 16px;
                }}
            """)
            for box in card.findChildren(QFrame, "detailBox"):
                box.setStyleSheet(f"QFrame#detailBox {{ background: {pal.bg_card_sub}; border: 1px solid {pal.border_sub}; border-radius: 10px; }}")
            for h in card.findChildren(QLabel, "cardHeading"):
                h.setStyleSheet(f"font-size: 14px; color: {pal.text_primary}; font-weight: 700; background: transparent; border: 0;")
            for r in card.findChildren(QFrame, "cardRule"):
                r.setStyleSheet(f"background: {pal.border}; border: 0;")
            for d in card.findChildren(QLabel, "cardDate"):
                d.setStyleSheet(f"font-size: 10px; color: {pal.text_muted}; background: transparent; border: 0;")
            for l in card.findChildren(QLabel, "detailLabel"):
                l.setStyleSheet(f"font-size: 11px; color: {pal.text_primary}; font-weight: 600; background: transparent; border: 0;")
            for v in card.findChildren(QLabel, "detailValue"):
                v.setStyleSheet(f"font-size: 10px; color: {pal.text_secondary}; line-height: 1.3; background: transparent; border: 0;")
            for t in card.findChildren(QLabel, "sideCardTitle"):
                t.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {pal.text_primary}; background: transparent; border: 0;")
            for b in card.findChildren(QPushButton, "sideCardBtn"):
                b.setStyleSheet(f"""
                    QPushButton {{ border: 1px solid {pal.border}; border-radius: 12px; color: {pal.accent};
                                   padding: 7px; font-size: 11px; font-weight: 600; background: {pal.bg_card}; }}
                    QPushButton:hover {{ background: {pal.tab_hover}; border-color: {pal.accent}; }}
                """)
            for tb in card.findChildren(QPushButton, "textActionBtn"):
                tb.setStyleSheet(f"""
                    QPushButton {{
                        text-align: left; background: transparent; border: 0;
                        color: {pal.accent}; font-size: 11px; font-weight: 600; padding: 4px 0;
                    }}
                    QPushButton:hover {{ color: {pal.accent_dark}; text-decoration: underline; }}
                """)
            for cb in card.findChildren(QPushButton, "cardButton"):
                cb.setStyleSheet(f"""
                    QPushButton {{
                        background: {pal.bg_card}; color: {pal.accent};
                        border: 1px solid {pal.border}; border-radius: 14px;
                        font-size: 11px; font-weight: 600;
                    }}
                    QPushButton:hover {{ background: {pal.tab_hover}; border-color: {pal.accent}; }}
                    QPushButton:disabled {{ color: {pal.text_muted}; border-color: {pal.border_sub}; }}
                """)

        for p_bar in self._all_progress_bars:
            p_bar.setStyleSheet(f"""
                QProgressBar {{ border: 0; background: {pal.progress_track}; border-radius: 2px; }}
                QProgressBar::chunk {{ background: {pal.accent}; border-radius: 2px; }}
            """)

    # ── Actions ──────────────────────────────────────────────────────────────

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
        msg = (
            f"Удалить {stats['count']} файлов ({format_size(stats['size'])}) "
            f"из ~/.local/share/Trash?\nВосстановить их после очистки нельзя."
        )
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

    # ── Diagnostics control ───────────────────────────────────────────────────

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
                self, "Глубокая диагностика ОЗУ",
                "Будет выполнен 4-проходный стресс-тест памяти (шаблоны битов, хеш-целостность, удержание ячеек).\n"
                "Тест безопасен и занимает ~1.5 минуты. Продолжить?",
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
            c["status"].setText("Подготовка...")
            c["status"].setStyleSheet(
                f"font-size: 12px; color: {theme_manager.palette.accent}; font-weight: 600; margin-top: 2px;"
            )

        self.btn_check_all.setText("Отменить")
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
        status_name, color = STATUS_STYLE.get(result["status"], ("Неизвестно", "#82918a"))
        c["status"].setText(status_name)
        c["status"].setStyleSheet(
            f"font-size: 12px; color: {color}; font-weight: 700; margin-top: 2px;"
        )
        details = result["details"]
        if card_id == "battery":
            details = [ln for ln in details if not ln.startswith("Уровень заряда:")]
        elif card_id.startswith("drive_"):
            details = [ln for ln in details if not ln.startswith("/")]
        elif card_id == "memory":
            details = [ln for ln in details if not ln.startswith("Общая память:")]
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
        self.btn_check_all.setText("Проверить все")

    def update_realtime_metrics(self):
        # Skip updating card overview gauges while deep check worker is running
        if self.worker is not None and self.worker.isRunning():
            return

        # 1. Real-time RAM consumption
        if self._ram_bar and self._ram_val_lbl:
            mem = get_ram_info()
            self._update_bar(self._ram_bar, int(mem["percent"]))
            self._ram_val_lbl.setText(
                f"{mem['percent']}%  ({mem['used_gb']} / {mem['total_gb']} ГБ • свободно {mem['available_gb']} ГБ)"
            )

        # 2. Real-time Drives partition usage
        fresh_drives = get_physical_drives()
        for d_idx, d_info in enumerate(fresh_drives):
            cid = f"drive_{d_idx}"
            if cid in self._drive_part_widgets:
                for part in d_info.get("partitions", []):
                    mount = part["mount"]
                    if mount in self._drive_part_widgets[cid]:
                        bar, lbl = self._drive_part_widgets[cid][mount]
                        self._update_bar(bar, int(part["percent"]))
                        lbl.setText(f"осталось {part['free_gb']} GB, всего {part['total_gb']} GB ({part['percent']}%)")

        # 3. Real-time Battery state
        bat = get_battery_info()
        charge = bat.get("percent")
        if charge is not None and self._bat_bar and self._bat_charge_val:
            self._update_bar(self._bat_bar, charge)
            v_str = f" • {bat['voltage_v']} В" if bat.get("voltage_v") else ""
            p_str = f" • {bat['power_w']} Вт" if bat.get("power_w") and bat['power_w'] > 0 else ""
            if bat.get("plugged"):
                st = "Полный заряд" if (bat.get("status") == "Full" or charge >= 99) else "Зарядка"
            else:
                st = "Разрядка"
            self._bat_charge_val.setText(f"{charge}% ({st}{v_str}{p_str})")

        if self._bat_temp_val:
            t = bat.get("temperature")
            self._bat_temp_val.setText(f"{t}°C" if t is not None else "Норма")

        # 4. Real-time System & Cooling sensors
        if self._sys_temp_lbl:
            c_temp = get_cpu_temp()
            g_temp = get_gpu_temp()
            g_str = f"{g_temp}°C" if g_temp is not None else "Сон"
            self._sys_temp_lbl.setText(f"Мониторинг сенсоров: ЦП {c_temp}°C | GPU {g_str}")


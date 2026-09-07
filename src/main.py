#!/usr/bin/env python3
import sys
import os
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from ui.main_window import MainWindow
from ui.theme import theme_manager
from core.config import load_config
from core.ec_control import apply_saved_charge_limit
from core.battery_daemon import start_battery_monitor, stop_battery_monitor
from core.hyprland import detect_hyprland, has_keybinds, install_keybinds


def main():
    app = QApplication(sys.argv)

    # Применение темы оформления (Светлая / Тёмная / Системная)
    theme_manager.apply_current()

    # Восстановление фильтра BluelightShield при запуске
    config = load_config()
    if config.get("bluelight_enabled", False):
        import subprocess, shutil
        temp = config.get("bluelight_temp", 4500)
        tool = "hyprsunset" if shutil.which("hyprsunset") else "wlsunset" if shutil.which("wlsunset") else None
        if tool:
            subprocess.Popen([tool, "-t", str(temp)])

    # Автономная интеграция с Hyprland: если бинды ещё не прописаны, добавляем их автоматически
    if detect_hyprland() and not has_keybinds():
        install_keybinds()

    icon_path = os.path.join(os.path.dirname(__file__), '../assets/icon.png')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Запуск фонового гистерезисного монитора батареи
    start_battery_monitor()
    app.aboutToQuit.connect(stop_battery_monitor)

    window = MainWindow()
    window.show()

    # The helper uses polkit and therefore runs after a visible application window exists.
    QTimer.singleShot(100, apply_saved_charge_limit)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

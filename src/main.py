#!/usr/bin/env python3
import sys
import os
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from ui.main_window import MainWindow
from core.config import load_config
from core.ec_control import apply_saved_charge_limit

def main():
    app = QApplication(sys.argv)

    # Відновлюємо BluelightShield при запуску, якщо він був увімкнений
    config = load_config()
    if config.get("bluelight_enabled", False):
        import subprocess, shutil
        temp = config.get("bluelight_temp", 4500)
        tool = "hyprsunset" if shutil.which("hyprsunset") else "wlsunset" if shutil.which("wlsunset") else None
        if tool:
            subprocess.Popen([tool, "-t", str(temp)])

    icon_path = os.path.join(os.path.dirname(__file__), '../assets/icon.png')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()
    # The helper uses polkit and therefore runs after a visible application window exists.
    QTimer.singleShot(0, apply_saved_charge_limit)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

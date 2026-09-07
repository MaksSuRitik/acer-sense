from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QMainWindow, QTabWidget

from .tab_checkup import CheckupTab
from .tab_home import HomeTab
from .tab_settings import SettingsTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Acer Sense")
        self.resize(1280, 760)
        self.setMinimumSize(960, 620)
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #f7f8f6; color: #4a4e4c; font-family: 'Inter', 'Noto Sans', 'Segoe UI', sans-serif; }
            QTabWidget::pane { border: 0; border-top: 1px solid #e5ebe7; }
            QTabBar { background: #fbfcfa; }
            QTabBar::tab {
                background: #fbfcfa; color: #626b67; min-width: 0;
                padding: 14px 13px 13px; margin: 0 3px;
                font-size: 13px; font-weight: 600;
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected { color: #3d9675; border-bottom-color: #4ba781; }
            QTabBar::tab:hover:!selected { color: #2e3934; }
            QLabel#logo { color: #4ba781; font-family: 'Arial'; font-size: 28px; font-style: italic; font-weight: 800; padding: 0 15px 2px 20px; }
            QLabel#topAction { color: #6e7773; font-size: 18px; padding: 0 18px; }
            QLabel#pageHeading { color: #353c38; font-size: 21px; font-weight: 700; }
            QLabel#emptyState { color: #737c77; font-size: 14px; }
            QScrollBar:vertical { width: 8px; background: transparent; margin: 10px 2px; }
            QScrollBar::handle:vertical { min-height: 42px; background: #a8d9c5; border-radius: 4px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(False)

        logo = QLabel("a")
        logo.setObjectName("logo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tabs.setCornerWidget(logo, Qt.Corner.TopLeftCorner)
        action = QLabel("◉   ⚙")
        action.setObjectName("topAction")
        self.tabs.setCornerWidget(action, Qt.Corner.TopRightCorner)

        self.tabs.addTab(HomeTab(), "Дом")
        self.tabs.addTab(CheckupTab(), "Проверить")
        self.tabs.addTab(SettingsTab(), "Персональные настройки")
        self.setCentralWidget(self.tabs)

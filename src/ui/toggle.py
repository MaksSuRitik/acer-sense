from PyQt6.QtWidgets import QCheckBox
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush
from PyQt6.QtCore import Qt, QPropertyAnimation, pyqtProperty
from ui.theme import theme_manager


class ToggleSwitch(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(50, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._position = 3
        self.animation = QPropertyAnimation(self, b"position")
        self.animation.setDuration(150)
        self.stateChanged.connect(self.start_animation)

    @pyqtProperty(float)
    def position(self):
        return self._position

    @position.setter
    def position(self, pos):
        self._position = pos
        self.update()

    def start_animation(self, state):
        self.animation.stop()
        if state:
            self.animation.setEndValue(23)
        else:
            self.animation.setEndValue(3)
        self.animation.start()

    def hitButton(self, position):
        return self.rect().contains(position)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = theme_manager.palette

        if self.isChecked():
            bg_color = QColor(pal.accent)
        else:
            bg_color = QColor(pal.progress_track if pal.is_dark else "#d6e0db")

        # Background capsule
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 13, 13)

        # White knob with subtle border
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawEllipse(int(self._position), 3, 20, 20)
        painter.end()

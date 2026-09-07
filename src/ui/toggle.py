from PyQt6.QtWidgets import QCheckBox
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush
from PyQt6.QtCore import Qt, QPropertyAnimation, pyqtProperty

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
        """QCheckBox normally accepts only its indicator; a switch is one control."""
        return self.rect().contains(position)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Колір фону
        if self.isChecked():
            bg_color = QColor("#4CAF50") # Зелений Acer
        else:
            bg_color = QColor("#e0e0e0") # Сірий

        # Малюємо фон (капсулу)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 13, 13)

        # Малюємо білий кружечок
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawEllipse(int(self._position), 3, 20, 20)
        painter.end()

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QPlainTextEdit, QLineEdit, QPushButton, QSizePolicy


class PromptEdit(QPlainTextEdit):
    prompt_nonempty = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QPlainTextEdit.Shape.NoFrame)
        self.setFont(QFont("Consolas", 10))
        self.textChanged.connect(self.check_prompt)

    def get_prompt(self):
        return self.toPlainText().strip()

    def check_prompt(self):
        self.prompt_nonempty.emit(bool(self.get_prompt()))


class FramelessLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrame(False)


class FixedSizeButton(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

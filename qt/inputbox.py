from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QLabel,
)


class InputBox(QFrame):
    prompt_sent = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        self.setLayout(layout)

        self._box = QPlainTextEdit(self)
        self._box.setFont(QFont("Consolas", 10))
        layout.addWidget(self._box)

        bottom_bar = QFrame(self)
        layout.addWidget(bottom_bar)

        bottom_bar_layout = QHBoxLayout()
        bottom_bar.setLayout(bottom_bar_layout)

        self._status_label = QLabel(self)
        bottom_bar_layout.addWidget(self._status_label)

        self._send_button = QPushButton(self)
        self._send_button.clicked.connect(self.send)
        self._send_button.setText("Send")
        self._send_button.setToolTip(
            "Press Ctrl+Return to send. Press Return to start a new line."
        )
        bottom_bar_layout.addWidget(self._send_button)

        self._send_action = QAction(self)
        self._send_action.triggered.connect(self.send)
        self._send_action.setShortcut("Ctrl+Return")
        self.addAction(self._send_action)

    def send(self):
        prompt = self._box.toPlainText().strip()
        if not prompt:
            # TODO display a warning over the send button
            return
        self.prompt_sent.emit(prompt)

    def enable(self):
        self._set_enabled(True)

    def disable(self):
        self._set_enabled(False)

    def clear(self):
        self._box.clear()

    def show_tokens_used(self, tokens_used: int, max_tokens: int):
        self._status_label.setText(f"Token usage: {tokens_used}/{max_tokens}")

    def _set_enabled(self, flag: bool):
        self._send_action.setEnabled(flag)
        self._send_button.setEnabled(flag)

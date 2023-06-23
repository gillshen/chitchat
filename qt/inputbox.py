from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QSizePolicy,
)

from .shared import PromptEdit


class InputBox(QFrame):
    prompt_sent = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_prompt = ""

        layout = QVBoxLayout()
        layout.setContentsMargins(8, 4, 8, 8)
        self.setLayout(layout)

        self._prompt_edit = PromptEdit(self)
        self._prompt_edit.prompt_nonempty.connect(self._set_enabled)
        layout.addWidget(self._prompt_edit)

        bottom_bar = QFrame(self)
        bottom_bar.setFrameShape(QFrame.Shape.NoFrame)
        bottom_bar.setFrameShadow(QFrame.Shadow.Plain)
        layout.addWidget(bottom_bar)

        bottom_bar_layout = QHBoxLayout()
        bottom_bar_layout.setContentsMargins(0, 0, 0, 0)
        bottom_bar.setLayout(bottom_bar_layout)

        self._status_label = QLabel(self)
        self._status_label.setText("0/0")
        self._status_label.setToolTip("Current context length / Maximum context length")
        self._status_label.setFixedWidth(120)
        self._status_label.setDisabled(True)
        bottom_bar_layout.addWidget(self._status_label)

        bottom_bar_layout.addStretch()

        self._restore_button = QPushButton(self)
        self._restore_button.clicked.connect(self.restore)
        self._restore_button.setText("Restore")
        self._restore_button.setToolTip("Restore the last prompt; Ctrl+R.")
        bottom_bar_layout.addWidget(self._restore_button)

        self._restore_action = QAction(self)
        self._restore_action.triggered.connect(self.restore)
        self._restore_action.setShortcut("Ctrl+R")
        self.addAction(self._restore_action)

        self._send_button = QPushButton(self)
        self._send_button.clicked.connect(self.send)
        self._send_button.setText("Send")
        self._send_button.setToolTip(
            "Press Ctrl+Return to send. Press Return to start a new line."
        )
        self._send_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        bottom_bar_layout.addWidget(self._send_button)

        self._send_action = QAction(self)
        self._send_action.triggered.connect(self.send)
        self._send_action.setShortcut("Ctrl+Return")
        self.addAction(self._send_action)

        # No prompt to send or restore upon init
        self._restore_button.setDisabled(True)
        self._restore_action.setDisabled(True)
        self._send_button.setDisabled(True)
        self._send_action.setDisabled(True)

    def get_prompt(self):
        return self._prompt_edit.get_prompt()

    def send(self):
        prompt = self.get_prompt()
        self.prompt_sent.emit(prompt)
        self._last_prompt = prompt
        self._restore_button.setEnabled(True)

    def restore(self):
        self._prompt_edit.setPlainText(self._last_prompt)

    def enable(self):
        self._set_enabled(True)
        self._prompt_edit.check_prompt()

    def disable(self):
        self._set_enabled(False)

    def clear(self):
        self._prompt_edit.clear()

    def show_tokens_used(self, tokens_used: int, max_tokens: int):
        self._status_label.setText(f"{tokens_used}/{max_tokens}")

    def _set_enabled(self, flag: bool):
        self._send_action.setEnabled(flag)
        self._send_button.setEnabled(flag)

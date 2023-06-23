from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QFrame,
    QPushButton,
)

from .shared import PromptEdit


class NewChatDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Chat")
        self.setMinimumWidth(400)

        layout = QVBoxLayout()
        self.setLayout(layout)

        layout.addWidget(QLabel("Title (optional)"))

        self._title_edit = QLineEdit(self)
        self._title_edit.setText("New Chat")
        layout.addWidget(self._title_edit)

        layout.addSpacing(10)

        sys_label = QLabel(self)
        sys_label.setText("System message (optional)")
        sys_label.setToolTip(
            'A standing instruction to ChatGPT, e.g. "Always reply in Spanish."\n'
            "No guarantee it will be followed. Counts toward the context length."
        )
        layout.addWidget(sys_label)

        self._sys_message_edit = PromptEdit(self)
        layout.addWidget(self._sys_message_edit)

        layout.addSpacing(10)

        layout.addWidget(QLabel("Prompt"))

        self._prompt_edit = PromptEdit(self)
        self._prompt_edit.prompt_nonempty.connect(self._set_enabled)
        layout.addWidget(self._prompt_edit)

        buttons_frame = QFrame(self)
        layout.addWidget(buttons_frame)
        buttons_frame_layout = QHBoxLayout()
        buttons_frame_layout.setContentsMargins(0, 0, 0, 0)
        buttons_frame.setLayout(buttons_frame_layout)

        self._cancel_button = QPushButton(self)
        self._cancel_button.setText("Cancel")
        self._cancel_button.clicked.connect(self.reject)
        buttons_frame_layout.addWidget(self._cancel_button)

        buttons_frame_layout.addStretch(1)

        self._send_button = QPushButton(self)
        self._send_button.setText("Send")
        self._send_button.setToolTip("Ctrl+Return to send.")
        self._send_button.clicked.connect(self.accept)
        self._send_button.setDisabled(True)
        buttons_frame_layout.addWidget(self._send_button)

        self._send_action = QAction(self)
        self._send_action.triggered.connect(self.accept)
        self._send_action.setShortcut("Ctrl+Return")
        self._send_action.setDisabled(True)
        self.addAction(self._send_action)

    def _set_enabled(self, flag: bool):
        self._send_button.setEnabled(flag)
        self._send_action.setEnabled(flag)

    def get_title(self):
        return self._title_edit.text().strip()

    def get_system_message(self) -> str:
        return self._sys_message_edit.get_prompt()

    def get_prompt(self) -> str:
        return self._prompt_edit.get_prompt()

    def clear(self):
        self._title_edit.setText("New Chat")
        self._sys_message_edit.clear()
        self._prompt_edit.clear()

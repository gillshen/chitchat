from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QMenu,
    QDialog,
    QHBoxLayout,
    QPushButton,
)

from .shared import FramelessLineEdit


class ChatNotFound(Exception):
    pass


class _ChatItem(QListWidgetItem):
    # add a __hash__ method so it can serve as dict keys

    def __hash__(self) -> int:
        return id(self)


class ChatsList(QListWidget):
    """A dynamic list chats, with newly added ones at the top"""

    chat_selected = pyqtSignal(int)  # chat_id
    rename_requested = pyqtSignal(tuple)  # (chat_id, new_name)
    delete_requested = pyqtSignal(int)  # chat_id
    error = pyqtSignal(Exception)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QListWidget.Shape.NoFrame)

        self._map = {}  # QListWidgetItem -> chat_id
        self._selected_chat_id = None
        self.itemClicked.connect(self._on_left_click)

        self._ask_rename_action = QAction("Rename", self)
        self._ask_rename_action.triggered.connect(self._request_rename)
        self._ask_delete_action = QAction("Delete", self)
        self._ask_delete_action.triggered.connect(self._request_delete)

        self._context_menu = QMenu(self)
        self._context_menu.addAction(self._ask_rename_action)
        self._context_menu.addAction(self._ask_delete_action)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _new_item(self, chat_id: int, chat_title: str):
        item = _ChatItem()
        item.setText(chat_title)
        self._map[item] = chat_id
        return item

    def _get_item(self, chat_id: int) -> _ChatItem:
        for item in self._map:
            if self._map[item] == chat_id:
                return item
        else:
            self.error.emit(ChatNotFound(f"{chat_id=}"))

    def populate(self, chats_map: dict):
        self._map.clear()
        for chat_id, chat_title in chats_map.items():
            self.addItem(self._new_item(chat_id, chat_title))

    def rename_chat(self, chat_id: int, new_name: str):
        self._get_item(chat_id).setText(new_name)

    def insert_at_top(self, chat_id: int, chat_title: str):
        self.insertItem(0, self._new_item(chat_id, chat_title))

    def select_chat(self, chat_id: int | None):
        if chat_id is None:
            self.setCurrentItem(None)
            self._selected_chat_id = None
        else:
            self.setCurrentItem(self._get_item(chat_id))
            self._selected_chat_id = chat_id

    def delete_chat(self, chat_id: int):
        for item in self._map:
            if self._map[item] == chat_id:
                self.takeItem(self.row(item))
                return
        else:
            self.error.emit(ChatNotFound(f"{chat_id=}"))

    @property
    def current_chat_id(self) -> int:
        return self._map[self.currentItem()]

    @property
    def selected_chat_id(self) -> int:
        """Return the id of the chat that has been selected (left-clicked)"""
        return self._selected_chat_id

    def _on_left_click(self):
        self._selected_chat_id = self.current_chat_id
        self.chat_selected.emit(self.current_chat_id)

    def _request_rename(self):
        current_name = self.currentItem().text()
        dialog = RenameDialog(self, current_name=current_name)

        def _emit_request():
            new_name = dialog.get_text()
            self.rename_requested.emit((self.current_chat_id, new_name))

        dialog.accepted.connect(_emit_request)
        dialog.exec()

    def _request_delete(self):
        self.delete_requested.emit(self.current_chat_id)

    def _show_context_menu(self, position):
        item = self.itemAt(position)
        if item is not None:
            self._context_menu.exec(self.mapToGlobal(position))


class RenameDialog(QDialog):
    def __init__(self, parent=None, current_name=""):
        super().__init__(parent)
        self.setWindowTitle("Rename Chat")

        layout = QHBoxLayout()
        self.setLayout(layout)

        self.edit = FramelessLineEdit(self)
        self.edit.setText(current_name)
        self.edit.setMinimumWidth(200)
        layout.addWidget(self.edit)

        self._okay_button = QPushButton(self)
        self._okay_button.setText("Okay")
        self._okay_button.clicked.connect(self.accept)
        layout.addWidget(self._okay_button)

        self._okay_action = QAction(self)
        self._okay_action.triggered.connect(self.accept)
        self._okay_action.setShortcut("Ctrl+Return")
        self.addAction(self._okay_action)

    def get_text(self):
        return self.edit.text().strip()

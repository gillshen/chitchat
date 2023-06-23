from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QMenu, QInputDialog, QLineEdit


class ChatNotFound(Exception):
    pass


class _ListItem(QListWidgetItem):
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

    def populate(self, chats_map: dict):
        self._map.clear()
        for chat_id, chat_title in chats_map.items():
            item = _ListItem(self)
            item.setText(chat_title)
            self._map[item] = chat_id
            self.addItem(item)

    def rename_chat(self, chat_id: int, new_name: str):
        for item in self._map:
            if self._map[item] == chat_id:
                item.setText(new_name)
                return
        else:
            self.error.emit(ChatNotFound(f"{chat_id=}"))

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
        current_item = self.currentItem()
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Chat",  # title
            "Enter a new name",  # label text
            QLineEdit.EchoMode.Normal,  # echo mode
            current_item.text(),  # current text
        )
        if ok:
            self.rename_requested.emit((self.current_chat_id, new_name))

    def _request_delete(self):
        self.delete_requested.emit(self.current_chat_id)

    def _show_context_menu(self, position):
        item = self.itemAt(position)
        if item is not None:
            self._context_menu.exec(self.mapToGlobal(position))

import sys
import time

from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QMainWindow, QSplitter

from core import DEFAULT_MODEL, MAX_TOKENS
from chat import Chat
from qt.chatroom import ChatRoom
from qt.inputbox import InputBox
import db


class ChatManager(QObject):
    """Make API requests and manage data storage"""

    # passing on signals from chat threads
    waiting = pyqtSignal()
    wait_finished = pyqtSignal()
    streaming = pyqtSignal(str)
    streaming_finished = pyqtSignal(str)
    error = pyqtSignal(Exception)

    # emit `Chat.tokens_used()`
    tokens_used = pyqtSignal(int)

    def __init__(self, model: str):
        super().__init__()
        self.model = model
        self._chats = {}  # id -> Chat
        self._active_chat: Chat = None
        self._unsaved_chat: Chat = None

        self._chat_thread: None | ChatThread = None

        self.temperature = None
        self.top_p = None
        self.presence_penalty = None
        self.frequency_penalty = None

        self.max_tokens = MAX_TOKENS
        self.reserve_tokens = MAX_TOKENS // 10

    @property
    def active_chat(self):
        if self._active_chat is None:
            self.new_chat()
        return self._active_chat

    def set_active_chat(self, chat_id: str):
        self._active_chat = self._chats[chat_id]

    def new_chat(self, system_message=""):
        self._active_chat = self._unsaved_chat = Chat(system_message=system_message)

    def rename_chat(self, chat_id: str, title: str):
        db.rename_chat(chat_id, title)

    def delete_chat(self, chat_id):
        chat = self._chats.pop(chat_id)
        if self.active_chat is chat:
            self.active_chat = None
        if self._unsaved_chat is chat:
            self._unsaved_chat = None
        else:
            # `chat` has been saved
            db.delete_chat(chat_id)

    def create_completion(self, prompt: str):
        self._chat_thread = ChatThread(chat_manager=self, prompt=prompt)
        self._chat_thread.waiting.connect(self.waiting.emit)
        self._chat_thread.wait_finished.connect(self.wait_finished.emit)
        self._chat_thread.streaming.connect(self.streaming)
        self._chat_thread.streaming_finished.connect(self._on_streaming_finish)
        self._chat_thread.error.connect(self.error.emit)
        self._chat_thread.start()

    def _on_streaming_finish(self, response: str):
        self.streaming_finished.emit(response)
        self.tokens_used.emit(self.active_chat.tokens_used(self.model))

        # if the current chat is unsaved, save it
        if self.active_chat is self._unsaved_chat:
            chat_id = db.save_chat(self.active_chat)
            self._chats[chat_id] = self.active_chat
            self._unsaved_chat = None
        else:
            chat_id = self._get_chat_id(self.active_chat)

        # save the request
        db.save_request(chat_id, self.active_chat.last_request)

    def _get_chat_id(self, chat: Chat):
        for key in self._chats:
            if self._chats[key] is chat:
                return key
        else:
            raise ValueError(f"Can't find {chat}")


class ChatThread(QThread):
    # passing on signals from wait threads
    waiting = pyqtSignal()

    # emitted when waiting ends for whatever reason
    wait_finished = pyqtSignal()
    # emit chunks yielded by `Chat.create_completion()`
    streaming = pyqtSignal(str)
    # emit `Chat.last_response`
    streaming_finished = pyqtSignal(str)

    error = pyqtSignal(Exception)

    def __init__(self, chat_manager: ChatManager, prompt: str, parent=None):
        super().__init__(parent)
        self._cm = chat_manager
        self._prompt = prompt
        self._is_waiting = True
        self._wait_thread = ChatWaitThread()
        self._wait_thread.waiting.connect(self.waiting.emit)

    def run(self):
        chat = self._cm.active_chat
        self._wait_thread.start()
        try:
            for chunk in chat.create_completion(
                prompt=self._prompt,
                model=self._cm.model,
                temperature=self._cm.temperature,
                top_p=self._cm.top_p,
                presence_penalty=self._cm.presence_penalty,
                frequency_penalty=self._cm.frequency_penalty,
                max_tokens=self._cm.max_tokens,
                reserve_tokens=self._cm.reserve_tokens,
            ):
                self._stop_waiting()
                self.streaming.emit(chunk)
        except Exception as e:
            self._stop_waiting()
            self.error.emit(e)
        else:
            self.streaming_finished.emit(chat.last_response)

    def _stop_waiting(self):
        if not self._is_waiting:
            return
        self._wait_thread.stop()
        self.wait_finished.emit()
        self._is_waiting = False


class ChatWaitThread(QThread):
    waiting = pyqtSignal()
    stopped = pyqtSignal()

    def __init__(self, parent=None, interval=0.5):
        super().__init__(parent)
        self._interval = interval
        self._stop = False

    def run(self):
        while True:
            if self._stop:
                self.stopped.emit()
                return
            self.waiting.emit()
            time.sleep(self._interval)

    def stop(self):
        self._stop = True
        self.quit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.chat_manager = ChatManager(model=DEFAULT_MODEL)

        central = QSplitter(Qt.Orientation.Vertical, self)
        self.setCentralWidget(central)

        self.chat_room = ChatRoom(self)
        self.chat_room.setReadOnly(True)
        central.addWidget(self.chat_room)

        self.input_box = InputBox(self)
        central.addWidget(self.input_box)

        self.input_box.prompt_sent.connect(self.input_box.disable)
        self.input_box.prompt_sent.connect(self.chat_room.show_prompt)
        self.input_box.prompt_sent.connect(self.chat_manager.create_completion)

        self.chat_manager.waiting.connect(self.chat_room.white_waiting)

        self.chat_manager.wait_finished.connect(self.input_box.clear)
        self.chat_manager.wait_finished.connect(self.chat_room.on_wait_finish)

        self.chat_manager.streaming.connect(self.chat_room.stream_completion)

        self.chat_manager.streaming_finished.connect(self.chat_room.on_streaming_finish)
        self.chat_manager.streaming_finished.connect(self.input_box.enable)
        self.chat_manager.tokens_used.connect(self._show_tokens_used)

        self.chat_manager.error.connect(self.chat_room.show_error)
        self.chat_manager.error.connect(self.input_box.enable)

        # Initialize appearance
        self._show_tokens_used(0)
        self.setWindowTitle("chitchat")
        self.setGeometry(400, 100, 480, 600)
        central.setSizes([350, 250])  # height ratio of the chat room to the input box

        # for debugging
        _show_html_action = QAction(self)
        _show_html_action.triggered.connect(lambda: print(self.chat_room.toHtml()))
        _show_html_action.setShortcut("Ctrl+u")
        self.addAction(_show_html_action)

    def _show_tokens_used(self, tokens_used: str):
        self.input_box.show_tokens_used(tokens_used, self.chat_manager.max_tokens)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

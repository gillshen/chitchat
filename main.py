import sys
import time

from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QMainWindow, QSplitter, QFrame, QVBoxLayout

from core import Request, DEFAULT_MODEL, MAX_TOKENS
from chat import Chat
from qt.chatslist import ChatsList
from qt.paramsctrl import ParamsControl
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

    def add_chat(self, chat_id: int, chat: Chat):
        self._chats[chat_id] = chat

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

        body = QSplitter(self)
        self.setCentralWidget(body)

        sidebar = QFrame(self)
        sidebar.setLayout(QVBoxLayout())
        body.addWidget(sidebar)

        self.chats_list = ChatsList(self)
        sidebar.layout().addWidget(self.chats_list)

        self.params_ctrl = ParamsControl(self)
        sidebar.layout().addWidget(self.params_ctrl)

        mainframe = QSplitter(Qt.Orientation.Vertical, self)
        body.addWidget(mainframe)

        self.chat_room = ChatRoom(self)
        self.chat_room.setReadOnly(True)
        mainframe.addWidget(self.chat_room)

        self.input_box = InputBox(self)
        mainframe.addWidget(self.input_box)

        # signals

        self.chats_list.chat_selected.connect(self._load_chat)
        self.chats_list.rename_requested.connect(self._rename_chat)
        self.chats_list.delete_requested.connect(self._delete_chat)

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

        # initialize

        self._show_tokens_used(0)
        self.setWindowTitle("chitchat")
        self.setGeometry(400, 100, 720, 660)

        # width ratio of `sidebar` to `mainframe`
        body.setSizes([220, 500])
        # height ratio of chat_room to input_box
        mainframe.setSizes([400, 260])

        chats_list = db.list_chat_titles()
        chats_list.reverse()  # in reverse chronological order
        self.chats_list.populate(dict(chats_list))

        self._rebuild_chats()

        # for debugging
        _show_html_action = QAction(self)
        _show_html_action.triggered.connect(lambda: print(self.chat_room.toHtml()))
        _show_html_action.setShortcut("Ctrl+u")
        self.addAction(_show_html_action)

    def _rebuild_chats(self):
        """Reconstruct Chat objects from database"""

        chats_map = {}  # id -> chat_data (params to Chat.from_data)

        # fetch all messages from the database, with chat id and info
        # no need for parameters such as temperature, so "simple" is enough
        for (
            chat_id,
            title,
            system_message,
            date_started,
            model,
            prompt,
            response,
        ) in db.list_messages_simple():
            chat_data = chats_map.setdefault(
                chat_id,
                dict(
                    title=title,
                    system_message=system_message,
                    date_started=date_started,
                    history=[],
                ),
            )
            request = Request(model=model, prompt=prompt, response=response)
            chat_data["history"].append(request)

        for chat_id, chat_data in chats_map.items():
            chat = Chat.from_data(**chat_data)
            self.chat_manager.add_chat(chat_id=chat_id, chat=chat)

    def _load_chat(self, chat_id: int):
        self.chat_manager.set_active_chat(chat_id)
        chat = self.chat_manager.active_chat
        self.chat_room.set_from_requests(chat.history)
        # update the token usage label
        tokens_used = chat.tokens_used(self.chat_manager.model)
        max_tokens = self.chat_manager.max_tokens
        self.input_box.show_tokens_used(tokens_used, max_tokens)

    def _rename_chat(self, id_name: tuple):
        db.rename_chat(*id_name)
        self.chats_list.rename_chat(*id_name)

    def _delete_chat(self, chat_id: int):
        db.delete_chat(chat_id)
        self.chats_list.delete_chat(chat_id)
        if self.chats_list.selected_chat_id == chat_id:
            self.chat_room.clear()

    def _show_tokens_used(self, tokens_used: str):
        self.input_box.show_tokens_used(tokens_used, self.chat_manager.max_tokens)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

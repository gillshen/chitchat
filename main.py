import sys
import time

from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QMainWindow, QSplitter, QFrame, QVBoxLayout

from core import Request, DEFAULT_MODEL, MAX_TOKENS, DEFAULT_TITLE
from chat import Chat
from qt.shared import FixedSizeButton
from qt.chatslist import ChatsList
from qt.paramsctrl import ParamsControl
from qt.chatroom import ChatRoom
from qt.inputbox import InputBox
from qt.newchat import NewChatDialog
import db


APP_NAME = "chitchat"


class ChatManager(QObject):
    """Make API requests and manage data storage"""

    # passing on signals from chat threads
    waiting = pyqtSignal()
    wait_finished = pyqtSignal()
    streaming = pyqtSignal(str)
    streaming_finished = pyqtSignal(str)
    new_chat_saved = pyqtSignal(tuple)  # (chat_id, chat_title)
    error = pyqtSignal(Exception)

    # emit `Chat.tokens_used()`
    tokens_used = pyqtSignal(int)

    def __init__(self, model: str):
        super().__init__()
        self.model = model
        self._chats: dict[int, Chat] = {}  # id -> Chat
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
            self.new_chat(title=DEFAULT_TITLE)
        return self._active_chat

    def set_active_chat(self, chat_id: str):
        self._active_chat = self._chats[chat_id]

    def add_chat(self, chat_id: int, chat: Chat):
        self._chats[chat_id] = chat

    def new_chat(self, system_message="", title=""):
        self._active_chat = Chat(system_message=system_message, title=title)
        self._unsaved_chat = self._active_chat

    def rename_chat(self, chat_id: str, title: str):
        self._chats[chat_id].title = title
        db.rename_chat(chat_id, title)

    def delete_chat(self, chat_id):
        deleted = self._chats.pop(chat_id)
        if self._active_chat is deleted:
            self._active_chat = None
        if self._unsaved_chat is deleted:
            self._unsaved_chat = None
        else:
            # the chat to be deleted has been saved
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
        # if the current chat is unsaved, save it
        if self.active_chat is self._unsaved_chat:
            chat_id = db.save_chat(self.active_chat)
            self._chats[chat_id] = self.active_chat
            self._unsaved_chat = None
            self.new_chat_saved.emit((chat_id, self.active_chat.title))
        else:
            chat_id = self._get_chat_id(self.active_chat)

        # save the request
        db.save_request(chat_id, self.active_chat.last_request)

        self.streaming_finished.emit(response)
        self.tokens_used.emit(self.active_chat.tokens_used(self.model))

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

    streaming = pyqtSignal(str)  # chunks generated by Chat.create_completion()
    streaming_finished = pyqtSignal(str)  # Chat.last_response

    error = pyqtSignal(Exception)

    def __init__(self, chat_manager: ChatManager, prompt: str, parent=None):
        super().__init__(parent)
        self._manager = chat_manager
        self._prompt = prompt
        self._is_waiting = True
        self._wait_thread = ChatWaitThread()
        self._wait_thread.waiting.connect(self.waiting.emit)

    def run(self):
        chat = self._manager.active_chat
        self._wait_thread.start()
        try:
            for chunk in chat.create_completion(
                prompt=self._prompt,
                model=self._manager.model,
                temperature=self._manager.temperature,
                top_p=self._manager.top_p,
                presence_penalty=self._manager.presence_penalty,
                frequency_penalty=self._manager.frequency_penalty,
                max_tokens=self._manager.max_tokens,
                reserve_tokens=self._manager.reserve_tokens,
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
        self.manager = ChatManager(model=DEFAULT_MODEL)

        body = QSplitter(self)
        self.setCentralWidget(body)

        sidebar = QFrame(self)
        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(6, 6, 0, 2)
        sidebar.setLayout(sidebar_layout)
        body.addWidget(sidebar)

        self.new_chat_dialog = NewChatDialog(self)

        self.new_chat_button = FixedSizeButton(self)
        self.new_chat_button.setText("+ New Chat")
        self.new_chat_button.setStyleSheet("padding: 6 20 6 12")
        sidebar_layout.addWidget(self.new_chat_button)

        self.chats_list = ChatsList(self)
        sidebar_layout.addWidget(self.chats_list)

        self.params_ctrl = ParamsControl(self)
        sidebar_layout.addWidget(self.params_ctrl)

        mainframe = QSplitter(Qt.Orientation.Vertical, self)
        body.addWidget(mainframe)

        chat_room_frame = QFrame(self)
        mainframe.addWidget(chat_room_frame)

        chat_room_frame.setLayout(QVBoxLayout())
        chat_room_frame.layout().setContentsMargins(0, 6, 6, 0)
        self.chat_room = ChatRoom(self)
        self.chat_room.setReadOnly(True)
        chat_room_frame.layout().addWidget(self.chat_room)

        self.input_box = InputBox(self)
        mainframe.addWidget(self.input_box)

        # signals

        self.new_chat_button.clicked.connect(self.new_chat_dialog.exec)
        self.new_chat_dialog.accepted.connect(self._new_chat)

        self.chats_list.chat_selected.connect(self._load_chat)
        self.chats_list.rename_requested.connect(self._rename_chat)
        self.chats_list.delete_requested.connect(self._delete_chat)

        self.params_ctrl.temperature_set_default.connect(self._set_temperature)
        self.params_ctrl.temperature_set.connect(self._set_temperature)
        self.params_ctrl.top_p_set_default.connect(self._set_top_p)
        self.params_ctrl.top_p_set.connect(self._set_top_p)
        self.params_ctrl.pres_penalty_set_default.connect(self._set_presence_penalty)
        self.params_ctrl.pres_penalty_set.connect(self._set_presence_penalty)
        self.params_ctrl.freq_penalty_set_default.connect(self._set_frequency_penalty)
        self.params_ctrl.freq_penalty_set.connect(self._set_frequency_penalty)

        self.input_box.prompt_sent.connect(self.input_box.clear)
        self.input_box.prompt_sent.connect(self._lock_ui)
        self.input_box.prompt_sent.connect(self.chat_room.show_prompt)
        self.input_box.prompt_sent.connect(self.manager.create_completion)

        self.manager.waiting.connect(self.chat_room.white_waiting)
        self.manager.wait_finished.connect(self.chat_room.on_wait_finish)

        self.manager.streaming.connect(self.chat_room.stream_completion)

        self.manager.new_chat_saved.connect(self._list_new_chat)
        self.manager.streaming_finished.connect(self.chat_room.on_streaming_finish)
        self.manager.streaming_finished.connect(self._unlock_ui)
        self.manager.tokens_used.connect(self._show_tokens_used)

        self.manager.error.connect(self.chat_room.show_error)
        self.manager.error.connect(self._unlock_ui)

        # initialize

        self._set_window_title()
        self._show_tokens_used(0)
        self.setGeometry(400, 100, 800, 660)
        sidebar.setFixedWidth(300)

        # width ratio of `sidebar` to `mainframe`
        body.setSizes([300, 500])
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

    def _set_window_title(self, chat_title: str = None):
        if not chat_title:
            self.setWindowTitle(APP_NAME)
        else:
            self.setWindowTitle(f"{chat_title} - {APP_NAME}")

    def _new_chat(self):
        title = self.new_chat_dialog.get_title()
        system_message = self.new_chat_dialog.get_system_message()
        prompt = self.new_chat_dialog.get_prompt()
        self.manager.new_chat(system_message=system_message, title=title)
        self.chat_room.clear()
        self.chat_room.show_prompt(prompt)
        self.manager.create_completion(prompt)
        self.new_chat_dialog.clear()

    def _list_new_chat(self, id_title):
        chat_id, chat_title = id_title
        self.chats_list.insert_at_top(chat_id, chat_title)
        self.chats_list.select_chat(chat_id)
        self._set_window_title(chat_title)

    def _rebuild_chats(self):
        """Reconstruct Chat objects from database"""

        chats_map = {}  # id -> chat_data (params to Chat.from_data)

        # fetch all messages from the database, with chat id and info
        # no need for parameters such as temperature, so "simple" is enough
        for row in db.fetch_full_history():
            chat_data = chats_map.setdefault(
                row["chat_id"],
                dict(
                    title=row["title"],
                    system_message=row["system_message"],
                    date_started=row["date_started"],
                    history=[],
                ),
            )
            # a chat may have an empty history - if the first prompt failed
            # and the user closed the program without retrying
            if row["model"] is not None:
                request = Request(
                    model=row["model"],
                    prompt=row["prompt"],
                    response=row["response"],
                    timestamp=row["timestamp"],
                    temperature=row["temperature"],
                    top_p=row["top_p"],
                    presence_penalty=row["presence_penalty"],
                    frequency_penalty=row["frequency_penalty"],
                )
                chat_data["history"].append(request)

        for chat_id, chat_data in chats_map.items():
            chat = Chat.from_data(**chat_data)
            self.manager.add_chat(chat_id=chat_id, chat=chat)

    def _load_chat(self, chat_id: int):
        self.manager.set_active_chat(chat_id)
        chat = self.manager.active_chat
        # reconstruct chat history and shows it in chatroom
        self.chat_room.set_from_requests(chat.history)
        # update the token usage label
        tokens_used = chat.tokens_used(self.manager.model)
        max_tokens = self.manager.max_tokens
        self.input_box.show_tokens_used(tokens_used, max_tokens)
        # update window title
        self._set_window_title(chat.title)

    def _rename_chat(self, id_name: tuple):
        chat_id, chat_title = id_name
        self.manager.rename_chat(chat_id, chat_title)
        self.chats_list.rename_chat(chat_id, chat_title)

        # if the renamed chat happens to be the one being displayed:
        if self.chats_list.selected_chat_id == chat_id:
            self._set_window_title(chat_title)

    def _delete_chat(self, chat_id: int):
        db.delete_chat(chat_id)
        self.manager.delete_chat(chat_id)
        self.chats_list.delete_chat(chat_id)

        # if the deleted chat happens to be the one being displayed:
        if self.chats_list.selected_chat_id == chat_id:
            self.chat_room.clear()
            self.chats_list.select_chat(None)
            self._set_window_title()

    def _lock_ui(self):
        self.input_box.disable()
        self.chats_list.setDisabled(True)
        self.new_chat_button.setDisabled(True)

    def _unlock_ui(self):
        self.input_box.enable()
        self.chats_list.setEnabled(True)
        self.new_chat_button.setEnabled(True)

    def _show_tokens_used(self, tokens_used: int):
        self.input_box.show_tokens_used(tokens_used, self.manager.max_tokens)

    def _set_temperature(self, value=None):
        self.manager.temperature = value

    def _set_top_p(self, value=None):
        self.manager.top_p = value

    def _set_presence_penalty(self, value=None):
        self.manager.presence_penalty = value

    def _set_frequency_penalty(self, value=None):
        self.manager.frequency_penalty = value


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

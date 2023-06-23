import sqlite3

from core import Request, BaseChat

_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS Chat (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    system_message TEXT NOT NULL,
    date_started TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Request (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    model TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    temperature REAL DEFAULT NULL,
    top_p REAL DEFAULT NULL,
    presence_penalty REAL DEFAULT NULL,
    frequency_penalty REAL DEFAULT NULL,
    FOREIGN KEY (chat_id) REFERENCES Chat(id) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Message (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    FOREIGN KEY (request_id) REFERENCES Request(id) ON UPDATE CASCADE ON DELETE CASCADE
);
"""


def connect() -> sqlite3.Connection:
    con = sqlite3.connect("chat_history.sqlite")
    return con


class Manager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            con = connect()
            with con:
                con.executescript(_CREATE_TABLES)
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.con = connect()
        self.con.execute("PRAGMA foreign_keys = ON")

    def save_chat(self, chat: BaseChat) -> int:
        sql = "INSERT INTO Chat (title, system_message, date_started) VALUES (?, ?, ?);"
        with self.con:
            cur = self.con.execute(
                sql, (chat.title, chat.system_message, chat.date_started)
            )
            return cur.lastrowid

    def save_request(self, chat_id: int, req: Request):
        sql = """
            INSERT INTO Request (
                chat_id,
                model,
                timestamp,
                temperature,
                top_p,
                presence_penalty,
                frequency_penalty
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?
            );
            """
        with self.con:
            cur = self.con.execute(
                sql,
                (
                    chat_id,
                    req.model,
                    req.timestamp,
                    req.temperature,
                    req.top_p,
                    req.presence_penalty,
                    req.frequency_penalty,
                ),
            )
            req_id = cur.lastrowid
            self._insert_message(
                cursor=cur,
                request_id=req_id,
                role="user",
                content=req.prompt,
            )
            self._insert_message(
                cursor=cur,
                request_id=req_id,
                role="assistant",
                content=req.response,
            )

    @staticmethod
    def _insert_message(
        cursor: sqlite3.Cursor,
        request_id: int,
        role: str,
        content: str,
    ):
        sql = "INSERT INTO Message (request_id, role, content) VALUES (?, ?, ?);"
        cursor.execute(sql, (request_id, role, content))

    def rename_chat(self, chat_id: int, title: str):
        with self.con:
            self.con.execute("UPDATE Chat SET title=? WHERE id=?", (title, chat_id))

    def delete_chat(self, chat_id: int):
        with self.con:
            self.con.execute("DELETE FROM Chat WHERE id=?", (chat_id,))

    def list_chat_titles(self) -> list:
        """Return a list of (id, title) tuples"""
        return self.con.execute("SELECT id, title FROM Chat").fetchall()

    def list_messages_simple(self) -> list:
        """Return a list of tuples:
        (chat_id, title, system_message, date_started, model, prompt, response)
        """
        sql = """
            SELECT 
                Chat.id, 
                Chat.title, 
                Chat.system_message, 
                Chat.date_started, 
                Request.model, 
                Prompt.content,
                Response.content
            FROM Chat
                LEFT JOIN Request ON Chat.id = Request.chat_id
                LEFT JOIN (SELECT request_id, content FROM Message WHERE role == 'user') AS Prompt
                    ON Request.id = Prompt.request_id
                LEFT JOIN (SELECT request_id, content FROM Message WHERE role == 'assistant') AS Response
                    ON Request.id = Response.request_id;
            """
        return self.con.execute(sql).fetchall()


# Convenience functions
def save_chat(chat: BaseChat) -> int:
    return Manager().save_chat(chat)


def save_request(chat_id: int, req: Request):
    Manager().save_request(chat_id, req)


def rename_chat(chat_id: int, title: str):
    Manager().rename_chat(chat_id, title)


def delete_chat(chat_id: int):
    Manager().delete_chat(chat_id)


def list_chat_titles():
    return Manager().list_chat_titles()


def list_messages_simple():
    return Manager().list_messages_simple()

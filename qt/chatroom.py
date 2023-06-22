import re
import html

from PyQt6.QtGui import QTextCursor, QTextBlockFormat, QTextCharFormat
from PyQt6.QtWidgets import QTextBrowser
import markdown


class ChatRoom(QTextBrowser):
    _block_format = QTextBlockFormat()
    _block_format.setNonBreakableLines(False)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc = self.document()
        self._doc.setDocumentMargin(6)
        self._wait_signal_count = 0
        self._response_start = None

    def show_prompt(self, prompt: str):
        escaped = html.escape(prompt)
        self.append(
            f'<div style="color: #205E80; white-space: pre-wrap">{escaped}</div>'
        )
        self.append("")
        self.append("")
        self.ensureCursorVisible()

    def white_waiting(self):
        self._append(". ")
        self._wait_signal_count += 1
        if self._wait_signal_count > 5:
            self._remove_last_line()
            self._wait_signal_count = 0
        self.ensureCursorVisible()

    def on_wait_finish(self):
        self._remove_last_line()
        cur = self.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        self._response_start = cur.position()

    def stream_completion(self, chunk: str):
        self._append(chunk)
        self.ensureCursorVisible()

    def on_streaming_finish(self, response: str):
        cur = self.textCursor()
        cur.setPosition(self._response_start)
        cur.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        cur.removeSelectedText()

        # extra two spaces to make `markdown` put <br /> between lone newlines
        md = re.sub(r"(?<=\S)\n(?=\S)", "  \n", response)

        html = markdown.markdown(md, extensions=["fenced_code"])
        cur.insertHtml(f'<div style="color: #222222;">{html}</div>')

        # start a new block as a style firewall
        char_format = QTextCharFormat()
        cur.setCharFormat(char_format)
        cur.insertBlock(self._block_format)

        # scroll to the bottom
        vbar = self.verticalScrollBar()
        vbar.setValue(vbar.maximum())

    def _append(self, text: str):
        cur = self.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cur)
        self.insertPlainText(text)

    def _remove_last_line(self):
        cur = self.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        cur.movePosition(
            QTextCursor.MoveOperation.StartOfLine,
            QTextCursor.MoveMode.KeepAnchor,
        )
        cur.removeSelectedText()

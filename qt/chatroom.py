import re
import html
import traceback

from PyQt6.QtGui import QTextCursor, QTextBlockFormat, QTextCharFormat
from PyQt6.QtWidgets import QTextBrowser, QFrame
import markdown

# from ..core import Request


PROMPT_STYLE = "color: #205E80; white-space: pre-wrap;"
COMPLETION_STYLE = "color: #222222;"
ERROR_STYLE = "color: #8B0000; white-space: pre-wrap;"


class ChatRoom(QTextBrowser):
    _block_format = QTextBlockFormat()
    _block_format.setNonBreakableLines(False)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self._doc = self.document()
        self._doc.setDocumentMargin(6)
        self._wait_signal_count = 0
        self._response_start = None

    def show_prompt(self, prompt: str):
        self._append_prompt(prompt)
        self.ensureCursorVisible()

    def _append_prompt(self, prompt: str):
        escaped = html.escape(prompt)
        self.append(f'<span style="{PROMPT_STYLE}">{escaped}</span>')
        self.append("")
        self.append("")

    def white_waiting(self):
        self._append_plaintext(". ")
        self._wait_signal_count += 1
        if self._wait_signal_count > 5:
            self._remove_last_line()
            self._wait_signal_count = 0
        self.ensureCursorVisible()

    def on_wait_finish(self):
        self._wait_signal_count = 0
        self._remove_last_line()
        cur = self.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        self._response_start = cur.position()

    def stream_completion(self, chunk: str):
        self._append_plaintext(chunk)
        self.ensureCursorVisible()

    def _append_plaintext(self, text: str):
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

    def on_streaming_finish(self, response: str):
        cur = self.textCursor()
        cur.setPosition(self._response_start)
        cur.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        cur.removeSelectedText()
        self._append_response(response, cur=cur)
        self._scroll_to_bottom()

    def _append_response(self, response: str, cur: QTextCursor = None):
        if not cur:
            cur = self.textCursor()
            cur.movePosition(QTextCursor.MoveOperation.End)
            self.setTextCursor(cur)

        # two spaces needed for `markdown` to treat lone newlines as <br />
        md = re.sub(r"(?<=\S)\n(?=\S)", "  \n", response)

        html = markdown.markdown(md, extensions=["fenced_code"])
        cur.insertHtml(f'<span style="{COMPLETION_STYLE}">{html}</span>')

        # start a new block as a style firewall
        char_format = QTextCharFormat()
        cur.setCharFormat(char_format)
        cur.insertBlock(self._block_format)

    def _scroll_to_bottom(self):
        vbar = self.verticalScrollBar()
        vbar.setValue(vbar.maximum())

    def show_error(self, e: Exception):
        tb = "\n".join(traceback.format_exception(e))
        self.append(f'<span style="{ERROR_STYLE}">{tb}</span>')
        self.append("")
        self.append("")

    def set_from_requests(self, requests: list):
        """Clear self and show messages from the list of Request objects"""
        self.clear()
        for req in requests:
            self._append_prompt(prompt=req.prompt)
            self._append_response(response=req.response)
        self._scroll_to_bottom()

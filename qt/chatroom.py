from PyQt6.QtGui import QTextCursor, QTextBlockFormat
from PyQt6.QtWidgets import QTextEdit


class ChatRoom(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc = self.document()
        self._doc.setDocumentMargin(6)
        self._wait_signal_count = 0
        self._response_start = None

    def show_prompt(self, prompt: str):
        self.append(f'<div style="color: #205E80">{prompt}</div>')
        self.append("")
        self.append("")
        self.ensureCursorVisible()

    def white_waiting(self):
        self._append(". ")
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
        # TODO remove
        print(response, "-" * 40, sep="\n")

        cur = self.textCursor()
        cur.setPosition(self._response_start)
        cur.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        cur.removeSelectedText()
        cur.insertMarkdown(response)

        # start a new block to prevent markdown format spilling over
        new_block_format = QTextBlockFormat()
        new_block_format.setNonBreakableLines(False)
        cur.insertBlock(new_block_format)

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

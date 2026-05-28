"""Editor widget – Markdown only, có line numbers, autocomplete, auto-pair, smart indent."""
import mimetypes
import re

from PyQt6.QtCore import Qt, QRect, QSize, QStringListModel
from PyQt6.QtGui import (QColor, QFont, QPainter, QTextCursor, QTextFormat)
from PyQt6.QtWidgets import QCompleter, QPlainTextEdit, QTextEdit, QWidget

from .config import MARKDOWN_TEMPLATES
from .highlighter import MarkdownHighlighter
from .text_normalizer import normalize_external_paste_text


PAIR_MAP = {
    "{": "}",
    "[": "]",
    "(": ")",
    "\"": "\"",
    "'": "'",
    "$": "$",
    "`": "`",
}

IMAGE_FILE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_line_numbers(event)


class CodeEditor(QPlainTextEdit):
    """Markdown editor với line numbers, autocomplete, auto-pair, smart indent.

    Phát tín hiệu request_ai khi người dùng bấm Ctrl+G.
    """

    def __init__(self, file_path="", main_window=None):
        super().__init__()
        self.mode = "markdown"
        self.file_path = file_path
        self.main_window = main_window

        cfg = main_window.editor_config if main_window else {}
        self.editor_config = cfg
        font_family = cfg.get("font_family", "Consolas")
        font_size = cfg.get("font_size", 13)
        self.tab_spaces = cfg.get("tab_spaces", 2)
        self.auto_pair = cfg.get("auto_pair", True)

        font = QFont(font_family, font_size)
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setFixedPitch(True)
        self.setFont(font)

        wrap = QPlainTextEdit.LineWrapMode.WidgetWidth if cfg.get("wrap_lines", True) \
            else QPlainTextEdit.LineWrapMode.NoWrap
        self.setLineWrapMode(wrap)

        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * self.tab_spaces)
        self.setStyleSheet(
            "QPlainTextEdit{"
            "background:#ffffff;"
            "color:#0f172a;"
            "selection-background-color:#bfdbfe;"
            "selection-color:#0f172a;"
            "border:0;"
            "}")

        self.line_area = LineNumberArea(self)
        self.blockCountChanged.connect(self._update_lna_width)
        self.updateRequest.connect(self._update_lna)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self._update_lna_width(0)

        # Highlighter
        self.highlighter = MarkdownHighlighter(self.document())

        # Autocomplete
        self._templates = MARKDOWN_TEMPLATES
        self._completer_model = QStringListModel(list(self._templates.keys()), self)
        self.completer = QCompleter(self._completer_model, self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.activated[str].connect(self.insert_completion)

        # Popup style: viền sáng + nền trắng để khỏi dính dark mode
        self.completer.popup().setStyleSheet(
            "QListView{background:#ffffff;color:#0f172a;border:1px solid #cbd5e1;"
            "selection-background-color:#2563eb;selection-color:#ffffff;}")

        self.highlight_current_line()

    # --------- Line numbers ---------
    def line_number_width(self):
        digits = 1
        m = max(1, self.blockCount())
        while m >= 10:
            m //= 10
            digits += 1
        return 14 + self.fontMetrics().horizontalAdvance('9') * digits

    def _update_lna_width(self, _):
        self.setViewportMargins(self.line_number_width(), 0, 0, 0)

    def _update_lna(self, rect, dy):
        if dy:
            self.line_area.scroll(0, dy)
        else:
            self.line_area.update(0, rect.y(), self.line_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_lna_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_width(), cr.height()))

    def paint_line_numbers(self, event):
        painter = QPainter(self.line_area)
        painter.fillRect(event.rect(), QColor("#f5f7fa"))
        block = self.firstVisibleBlock()
        block_num = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        cur_block_num = self.textCursor().blockNumber()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QColor("#0f172a") if block_num == cur_block_num else QColor("#94a3b8"))
                rect = QRect(0, int(top), self.line_area.width() - 6, self.fontMetrics().height())
                painter.drawText(rect, Qt.AlignmentFlag.AlignRight, str(block_num + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_num += 1

    def highlight_current_line(self):
        extras = []
        if not self.isReadOnly():
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(QColor("#eef4ff"))
            sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            sel.cursor = self.textCursor()
            sel.cursor.clearSelection()
            extras.append(sel)
        self.setExtraSelections(extras)
        self.line_area.update()

    def update_font(self, font):
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setFixedPitch(True)
        self.setFont(font)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * self.tab_spaces)
        self._update_lna_width(0)

    # --------- Autocomplete ---------
    def insert_completion(self, key):
        content = self._templates.get(key, key)
        tc = self.textCursor()
        prefix = self.completer.completionPrefix()
        if prefix:
            tc.movePosition(QTextCursor.MoveOperation.Left,
                            QTextCursor.MoveMode.KeepAnchor, len(prefix))
            tc.removeSelectedText()
        self._insert_with_placeholder(content, tc)

    def _insert_with_placeholder(self, content, cursor=None):
        if cursor is None:
            cursor = self.textCursor()
        selected = cursor.selectedText().replace(' ', '\n')
        if "%|" in content:
            if selected:
                cursor.insertText(content.replace("%|", selected))
            else:
                before, after = content.split("%|", 1)
                cursor.insertText(before)
                pos = cursor.position()
                cursor.insertText(after)
                cursor.setPosition(pos)
                self.setTextCursor(cursor)
        else:
            cursor.insertText(content)

    def apply_snippet(self, snippet):
        """Public API: chèn 1 đoạn snippet vào vị trí con trỏ."""
        self._insert_with_placeholder(snippet)
        self.setFocus()

    def insert_inline_math(self):
        cursor = self.textCursor()
        sel = cursor.selectedText()
        cursor.insertText(f"${sel}$" if sel else "$$")
        if not sel:
            cursor.movePosition(QTextCursor.MoveOperation.Left)
            self.setTextCursor(cursor)

    def insert_display_math(self):
        cursor = self.textCursor()
        sel = cursor.selectedText().replace(' ', '\n')
        cursor.insertText(f"\n$$\n{sel}\n$$\n")

    def toggle_comment(self):
        """Bọc/bỏ HTML comment <!-- ... --> theo dòng."""
        cursor = self.textCursor()
        start, end = cursor.selectionStart(), cursor.selectionEnd()
        cursor.setPosition(start)
        start_block = cursor.blockNumber()
        cursor.setPosition(end)
        end_block = cursor.blockNumber()

        cursor.beginEditBlock()
        for ln in range(start_block, end_block + 1):
            block = self.document().findBlockByNumber(ln)
            text = block.text()
            stripped = text.strip()
            c = QTextCursor(block)
            if stripped.startswith("<!--") and stripped.endswith("-->"):
                new_text = re.sub(r"^(\s*)<!--\s?", r"\1", text)
                new_text = re.sub(r"\s?-->\s*$", "", new_text)
                c.select(QTextCursor.SelectionType.LineUnderCursor)
                c.insertText(new_text)
            else:
                if stripped:
                    c.select(QTextCursor.SelectionType.LineUnderCursor)
                    c.insertText(f"<!-- {text} -->")
        cursor.endEditBlock()

    def goto_line(self, line):
        line = max(1, min(line, self.blockCount()))
        block = self.document().findBlockByLineNumber(line - 1)
        cursor = self.textCursor()
        cursor.setPosition(block.position())
        self.setTextCursor(cursor)
        self.centerCursor()
        self.setFocus()

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        if (event.button() == Qt.MouseButton.LeftButton and self.main_window
                and hasattr(self.main_window, "_sync_preview_to_editor_line")):
            line = self.textCursor().blockNumber() + 1
            self.main_window._sync_preview_to_editor_line(line)

    # --------- Drag-drop: bỏ qua file URL để main window mở thành tab ---------
    @staticmethod
    def _mime_has_image_urls(source):
        if not source.hasUrls():
            return False
        for url in source.urls():
            path = url.toLocalFile()
            mime = mimetypes.guess_type(path)[0] if path else ""
            ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
            if path and ((mime and mime.startswith("image/")) or f".{ext}" in IMAGE_FILE_EXTENSIONS):
                return True
        return False

    def canInsertFromMimeData(self, source):
        if source.hasImage() or self._mime_has_image_urls(source):
            return True
        if source.hasUrls():
            for url in source.urls():
                if url.toLocalFile():
                    return False
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        if (source.hasImage() or self._mime_has_image_urls(source)) and self.main_window:
            handler = getattr(self.main_window, "_insert_pasted_image_from_mime", None)
            if handler and handler(self, source):
                return
        if source.hasText():
            text = normalize_external_paste_text(source.text())
            cursor = self.textCursor()
            cursor.beginEditBlock()
            cursor.insertText(text)
            cursor.endEditBlock()
            self.setTextCursor(cursor)
            return
        super().insertFromMimeData(source)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(
                u.toLocalFile() for u in event.mimeData().urls()):
            event.ignore()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls() and any(
                u.toLocalFile() for u in event.mimeData().urls()):
            event.ignore()
            return
        super().dropEvent(event)

    # --------- Key handling ---------
    def _handle_app_shortcut(self, event):
        mw = self.main_window
        if not mw:
            return False

        key = event.key()
        mods = event.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        alt = bool(mods & Qt.KeyboardModifier.AltModifier)

        def run(handler):
            handler()
            event.accept()
            return True

        if alt and key == Qt.Key.Key_F4:
            return run(mw.close)

        if not ctrl and not alt and key == Qt.Key.Key_F11:
            return run(mw.act_zen.trigger)

        if not ctrl or alt:
            return False

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            return run(mw._compile_preview)
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            return run(mw._prev_tab if shift or key == Qt.Key.Key_Backtab else mw._next_tab)
        if shift and key == Qt.Key.Key_W:
            return run(mw.close)
        if key in (Qt.Key.Key_W, Qt.Key.Key_F4):
            return run(mw._close_current_tab)
        if key == Qt.Key.Key_N and not shift:
            return run(mw._new_file)
        if key == Qt.Key.Key_O and not shift:
            return run(mw._open_file)
        if key == Qt.Key.Key_S:
            return run(mw._save_as_current if shift else mw._save_current)
        if key == Qt.Key.Key_F and not shift:
            return run(mw._show_find)
        if key == Qt.Key.Key_H and not shift:
            return run(mw._show_find)
        if key == Qt.Key.Key_B and not shift:
            return run(lambda: mw._wrap_selection("bold"))
        if key == Qt.Key.Key_I and not shift:
            return run(lambda: mw._wrap_selection("italic"))
        if key == Qt.Key.Key_M:
            return run(mw._block_math if shift else mw._inline_math)
        if key == Qt.Key.Key_T and not shift:
            return run(mw._insert_table)
        if key == Qt.Key.Key_Slash and not shift:
            return run(mw._toggle_comment_current)
        if key == Qt.Key.Key_P and not shift:
            return run(mw.act_toggle_preview.trigger)
        if key == Qt.Key.Key_G and not shift:
            return run(mw.trigger_ai_assistant)
        if key == Qt.Key.Key_L and not shift:
            return run(lambda: mw._line_prefix("- "))

        return False

    def keyPressEvent(self, event):
        if self._handle_app_shortcut(event):
            return

        # Tab -> indent / completer
        if event.key() == Qt.Key.Key_Tab and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            if self.completer.popup() and self.completer.popup().isVisible():
                event.ignore()
                return
            cursor = self.textCursor()
            if cursor.hasSelection():
                self._indent_selection(True)
            else:
                cursor.insertText(" " * self.tab_spaces)
            return

        if event.key() == Qt.Key.Key_Backtab:
            self._indent_selection(False)
            return

        # Auto-pair brackets / quotes
        if self.auto_pair and event.text() and event.text() in PAIR_MAP:
            opening = event.text()
            closing = PAIR_MAP[opening]
            cursor = self.textCursor()
            if cursor.hasSelection():
                sel = cursor.selectedText()
                cursor.insertText(f"{opening}{sel}{closing}")
                return
            # Đặc biệt: ' và " không auto-pair khi đứng sau ký tự chữ
            if opening in ("'", "\"") and cursor.position() > 0:
                prev = self.document().characterAt(cursor.position() - 1)
                if prev.isalnum():
                    super().keyPressEvent(event)
                    return
            cursor.insertText(opening + closing)
            cursor.movePosition(QTextCursor.MoveOperation.Left)
            self.setTextCursor(cursor)
            return

        # Skip over closing bracket nếu đã có
        if self.auto_pair and event.text() in ("}", "]", ")", "$"):
            cursor = self.textCursor()
            if not cursor.hasSelection():
                pos = cursor.position()
                if pos < self.document().characterCount() - 1:
                    nxt = self.document().characterAt(pos)
                    if nxt == event.text():
                        cursor.movePosition(QTextCursor.MoveOperation.Right)
                        self.setTextCursor(cursor)
                        return

        # Smart indent khi Enter
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.completer.popup() and self.completer.popup().isVisible():
                event.ignore()
                return
            self._smart_newline()
            return

        # Backspace xóa cả cặp ngoặc
        if event.key() == Qt.Key.Key_Backspace and self.auto_pair:
            cursor = self.textCursor()
            if not cursor.hasSelection() and cursor.position() > 0:
                pos = cursor.position()
                prev_char = self.document().characterAt(pos - 1)
                next_char = self.document().characterAt(pos)
                if prev_char in PAIR_MAP and PAIR_MAP[prev_char] == next_char:
                    cursor.beginEditBlock()
                    cursor.deletePreviousChar()
                    cursor.deleteChar()
                    cursor.endEditBlock()
                    return

        super().keyPressEvent(event)

        # Cập nhật completer (gợi ý sau khi gõ >= 2 ký tự alpha)
        tc = self.textCursor()
        block_text = tc.block().text()
        text_before = block_text[:tc.positionInBlock()]
        match = re.search(r'(\\[a-zA-Z]+|[a-zA-Z]+)$', text_before)
        completion_prefix = match.group(1) if match else ""

        ctrl_space = ((event.modifiers() & Qt.KeyboardModifier.ControlModifier)
                      and event.key() == Qt.Key.Key_Space)
        trigger = (len(completion_prefix) >= 2) or ctrl_space

        if trigger and completion_prefix:
            self.completer.setCompletionPrefix(completion_prefix)
            popup = self.completer.popup()
            if self.completer.completionCount() > 0:
                popup.setCurrentIndex(self.completer.completionModel().index(0, 0))
                cr = self.cursorRect()
                cr.setWidth(popup.sizeHintForColumn(0) + popup.verticalScrollBar().sizeHint().width())
                self.completer.complete(cr)
            else:
                popup.hide()
        elif self.completer.popup().isVisible():
            self.completer.popup().hide()

    def _smart_newline(self):
        cursor = self.textCursor()
        line = cursor.block().text()
        indent_match = re.match(r"[\t ]*", line)
        indent = indent_match.group(0) if indent_match else ""

        # Tiếp tục list / ordered list / task list
        m = re.match(r"^(\s*)([-*+]\s+\[[ xX]\]\s|\d+\.\s+|[-*+]\s+)", line)
        if m:
            content = line[m.end():].strip()
            if not content:
                # Dòng list rỗng -> bỏ marker
                cursor.beginEditBlock()
                cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock,
                                    QTextCursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
                cursor.endEditBlock()
                cursor.insertText("\n" + indent)
                return
            marker = m.group(2)
            num_match = re.match(r"(\d+)\.\s+", marker)
            if num_match:
                n = int(num_match.group(1)) + 1
                marker = f"{n}. "
            elif "[" in marker:
                marker = re.sub(r"\[[ xX]\]", "[ ]", marker)
            cursor.insertText("\n" + m.group(1) + marker)
            return

        cursor.insertText("\n" + indent)

    def _indent_selection(self, indent_in):
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        cursor.setPosition(start)
        start_block = cursor.blockNumber()
        cursor.setPosition(end)
        end_block = cursor.blockNumber()
        if not cursor.hasSelection():
            cursor.insertText(" " * self.tab_spaces if indent_in else "")
            return
        cursor.beginEditBlock()
        spaces = " " * self.tab_spaces
        for ln in range(start_block, end_block + 1):
            block = self.document().findBlockByNumber(ln)
            c = QTextCursor(block)
            if indent_in:
                c.insertText(spaces)
            else:
                line_text = block.text()
                if line_text.startswith(spaces):
                    c.setPosition(block.position())
                    for _ in range(self.tab_spaces):
                        c.deleteChar()
                elif line_text.startswith("\t"):
                    c.setPosition(block.position())
                    c.deleteChar()
        cursor.endEditBlock()

"""Gemini AI assistant – chatbox hỗ trợ soạn thảo Markdown."""
import base64
import html
import mimetypes
import os
import re
import uuid

import requests

from PyQt6.QtCore import Qt, QObject, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QKeySequence, QPixmap, QShortcut, QTextCursor
from PyQt6.QtWidgets import (QApplication, QComboBox, QDialog, QFileDialog,
                              QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                              QPushButton, QTextBrowser, QTextEdit,
                              QVBoxLayout, QWidget)

from .config import (CONFIG_DIR, DEFAULT_GEMINI_MODELS, gemini_model_sort_key,
                     load_api_key, load_editor_config, save_api_key,
                     save_editor_config)

try:
    import markdown as md_lib
except ImportError:
    md_lib = None


def fetch_gemini_models(api_key, timeout=15):
    """Gọi Gemini Models API của Google và sort model mới trước."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    names = []
    for model in resp.json().get("models", []):
        name = model.get("name", "")
        methods = model.get("supportedGenerationMethods", []) or []
        if "generateContent" not in methods:
            continue
        if name.startswith("models/"):
            name = name[len("models/"):]
        if "gemini" in name.lower():
            names.append(name)
    names = list(dict.fromkeys(names))
    names.sort(key=gemini_model_sort_key)
    return names


def _clean_model_text(text):
    clean = re.sub(r"^```[a-zA-Z]*\n?", "", text.strip())
    clean = re.sub(r"\n?```$", "", clean)
    return clean


def _markdown_fragment_to_html(text):
    if md_lib is None:
        return html.escape(text).replace("\n", "<br>")
    return md_lib.markdown(
        text,
        extensions=["extra", "tables", "fenced_code", "sane_lists"],
        output_format="html5",
    )


class ModelFetchWorker(QObject):
    finished = pyqtSignal(list, str)  # (models, error)

    def __init__(self, api_key):
        super().__init__()
        self.api_key = api_key

    def run(self):
        try:
            self.finished.emit(fetch_gemini_models(self.api_key), "")
        except Exception as exc:
            self.finished.emit([], str(exc))


class GeminiWorker(QObject):
    finished = pyqtSignal(str, str)   # (text, error)

    SYSTEM_PROMPT = (
        "Bạn là agent hỗ trợ soạn thảo trong eMeX, một trình editor Markdown có MathJax và TikZ. "
        "Trả lời ngắn gọn, hữu ích. Khi người dùng muốn chèn hoặc sửa tài liệu, hãy trả về Markdown "
        "sẵn dùng, không bao toàn bộ câu trả lời trong code fence trừ khi chính nội dung cần là code fence. "
        "Giữ nguyên công thức $...$ / $$...$$ và block ```tikz khi chỉnh sửa."
    )

    def __init__(self, api_key, model, messages):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.messages = messages

    def _image_part(self, path):
        mime, _ = mimetypes.guess_type(path)
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        return {"inlineData": {"mimeType": mime or "image/png", "data": data}}

    def run(self):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
            contents = []
            for msg in self.messages:
                role = "model" if msg.get("role") == "assistant" else "user"
                parts = []
                text = (msg.get("text") or "").strip()
                if text:
                    parts.append({"text": text})
                for image_path in msg.get("images", []):
                    if os.path.exists(image_path):
                        parts.append(self._image_part(image_path))
                if parts:
                    contents.append({"role": role, "parts": parts})

            payload = {
                "systemInstruction": {"parts": [{"text": self.SYSTEM_PROMPT}]},
                "contents": contents,
            }
            resp = requests.post(url, json=payload, timeout=90)
            if resp.status_code != 200:
                self.finished.emit("", f"API {resp.status_code}: {resp.text[:500]}")
                return
            data = resp.json()
            try:
                text = data["candidates"][0]["content"]["parts"][0]["text"]
            except Exception:
                self.finished.emit("", f"Phản hồi không hợp lệ: {data}")
                return
            self.finished.emit(_clean_model_text(text), "")
        except Exception as exc:
            self.finished.emit("", f"Lỗi kết nối: {exc}")


class ChatInput(QTextEdit):
    """Ô chat nhận paste ảnh trực tiếp từ clipboard."""

    def __init__(self, chat_widget):
        super().__init__(chat_widget)
        self.chat_widget = chat_widget
        self.setAcceptDrops(True)

    def insertFromMimeData(self, source):
        if source.hasImage():
            image = source.imageData()
            if isinstance(image, QPixmap):
                image = image.toImage()
            if isinstance(image, QImage) and not image.isNull():
                self.chat_widget.add_pending_image(self.chat_widget.save_chat_image(image))
                return
        if source.hasUrls():
            paths = []
            for url in source.urls():
                path = url.toLocalFile()
                mime = mimetypes.guess_type(path)[0] if path else ""
                if path and mime and mime.startswith("image/"):
                    paths.append(path)
            if paths:
                self.chat_widget.add_pending_images(paths)
                return
        super().insertFromMimeData(source)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
                return
            self.chat_widget._send()
            event.accept()
            return
        super().keyPressEvent(event)


class AIChatWidget(QWidget):
    """Widget chat dùng được trong dialog nổi hoặc dock compact dưới editor."""

    apply_requested = pyqtSignal(str, str)  # (action, markdown)
    dock_requested = pyqtSignal()
    closed_requested = pyqtSignal()

    LIGHT_QSS = """
        QWidget{background:#f8fafc;color:#0f172a;}
        QLabel{color:#0f172a;}
        QTextBrowser{background:#ffffff;color:#0f172a;border:1px solid #dbe3ef;border-radius:8px;}
        QTextEdit{background:#ffffff;color:#0f172a;border:1px solid #cbd5e1;border-radius:8px;padding:8px;}
        QLineEdit{background:#ffffff;color:#0f172a;border:1px solid #cbd5e1;border-radius:7px;padding:6px 8px;}
        QComboBox{background:#ffffff;color:#0f172a;border:1px solid #cbd5e1;border-radius:7px;padding:5px 8px;}
        QComboBox QAbstractItemView{background:#ffffff;color:#0f172a;
            selection-background-color:#2563eb;selection-color:#ffffff;}
        QPushButton{background:#ffffff;color:#0f172a;border:1px solid #cbd5e1;border-radius:7px;padding:7px 12px;}
        QPushButton:hover{background:#eff6ff;border-color:#2563eb;color:#1d4ed8;}
        QPushButton:disabled{color:#94a3b8;background:#f1f5f9;border-color:#e2e8f0;}
    """

    def __init__(self, parent=None, selected_text="", document_text="",
                 compact=False, context_provider=None):
        super().__init__(parent)
        self.setStyleSheet(self.LIGHT_QSS)
        self.selected_text = selected_text
        self.document_text = document_text
        self.context_provider = context_provider
        self.messages = []
        self.pending_images = []
        self.latest_response = ""
        self._thread = None
        self._worker = None
        self._model_thread = None
        self._model_worker = None

        cfg = load_editor_config()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self.full_header = QWidget()
        header = QHBoxLayout(self.full_header)
        header.setContentsMargins(0, 0, 0, 0)
        title = QLabel("✨ AI Chat")
        title.setStyleSheet("font-size:18px;font-weight:800;color:#111827;")
        header.addWidget(title)
        header.addStretch()

        header.addWidget(QLabel("API key:"))
        self.api_input = QLineEdit()
        self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_input.setPlaceholderText("Gemini API key")
        self.api_input.setText(load_api_key())
        self.api_input.setMinimumWidth(210)
        header.addWidget(self.api_input)

        self.btn_save_key = QPushButton("Lưu key")
        self.btn_save_key.clicked.connect(self._save_key_and_refresh)
        header.addWidget(self.btn_save_key)

        header.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(cfg.get("gemini_models_cache") or DEFAULT_GEMINI_MODELS)
        saved = cfg.get("gemini_model", "gemini-2.5-flash")
        idx = self.model_combo.findText(saved)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        self.model_combo.setMinimumWidth(190)
        header.addWidget(self.model_combo)

        self.btn_refresh_models = QPushButton("↻")
        self.btn_refresh_models.setToolTip("Cập nhật danh sách model từ Google")
        self.btn_refresh_models.clicked.connect(self._refresh_models)
        header.addWidget(self.btn_refresh_models)

        self.btn_dock = QPushButton("↧")
        self.btn_dock.setToolTip("Đưa AI xuống dưới cửa sổ soạn thảo")
        self.btn_dock.clicked.connect(self.dock_requested.emit)
        header.addWidget(self.btn_dock)
        root.addWidget(self.full_header)

        self.compact_header = QWidget()
        compact_row = QHBoxLayout(self.compact_header)
        compact_row.setContentsMargins(6, 4, 6, 0)
        compact_title = QLabel("✨ AI Chat")
        compact_title.setStyleSheet("font-weight:800;color:#111827;")
        compact_row.addWidget(compact_title)
        compact_row.addStretch()
        self.btn_undock_hint = QLabel("Compact")
        self.btn_undock_hint.setStyleSheet("color:#64748b;")
        compact_row.addWidget(self.btn_undock_hint)
        self.btn_close_compact = QPushButton("×")
        self.btn_close_compact.setFixedWidth(32)
        self.btn_close_compact.clicked.connect(self.closed_requested.emit)
        compact_row.addWidget(self.btn_close_compact)
        root.addWidget(self.compact_header)

        self.hint_label = QLabel("")
        self.hint_label.setStyleSheet("color:#475569;background:#e0f2fe;border:1px solid #bae6fd;"
                                      "padding:6px 9px;border-radius:8px;")
        root.addWidget(self.hint_label)

        self.chat_view = QTextBrowser()
        self.chat_view.setOpenExternalLinks(True)
        self.chat_view.document().setDefaultStyleSheet("""
            p{margin:0 0 6px 0;}
            ul,ol{margin-top:4px;margin-bottom:6px;}
            code{background:#f1f5f9;color:#0f172a;padding:1px 4px;border-radius:4px;}
            pre{background:#0f172a;color:#e2e8f0;padding:8px;border-radius:7px;}
            table{border-collapse:collapse;}
            th,td{border:1px solid #cbd5e1;padding:4px 7px;}
            blockquote{border-left:3px solid #93c5fd;margin:4px 0;padding-left:8px;color:#475569;}
        """)
        root.addWidget(self.chat_view, 1)
        self._append_chat_bubble(
            "assistant",
            "Mình sẵn sàng hỗ trợ soạn thảo, chỉnh sửa Markdown, công thức, TikZ hoặc phân tích ảnh. "
            "Bạn có thể dán ảnh trực tiếp vào ô chat."
        )

        input_bar = QHBoxLayout()
        self.input_edit = ChatInput(self)
        self.input_edit.setPlaceholderText("Nhập yêu cầu... Enter để gửi, Shift+Enter để xuống dòng, Ctrl+V để dán ảnh.")
        self.input_edit.setFixedHeight(84 if compact else 92)
        input_bar.addWidget(self.input_edit, 1)

        side = QVBoxLayout()
        self.btn_attach = QPushButton("📎 Ảnh")
        self.btn_attach.clicked.connect(self._attach_image)
        side.addWidget(self.btn_attach)
        self.btn_send = QPushButton("Gửi")
        self.btn_send.setStyleSheet("background:#2563eb;color:#ffffff;font-weight:700;border:0;"
                                    "padding:9px 18px;border-radius:8px;")
        self.btn_send.clicked.connect(self._send)
        side.addWidget(self.btn_send)
        side.addStretch()
        input_bar.addLayout(side)
        root.addLayout(input_bar)

        self.attach_label = QLabel("")
        self.attach_label.setStyleSheet("color:#475569;")
        root.addWidget(self.attach_label)

        self.action_row_widget = QWidget()
        action_row = QHBoxLayout(self.action_row_widget)
        action_row.setContentsMargins(0, 0, 0, 0)
        self.btn_insert = QPushButton("➕ Chèn phản hồi")
        self.btn_insert.clicked.connect(lambda: self._emit_apply("insert"))
        self.btn_replace = QPushButton("↔ Thay vùng chọn")
        self.btn_replace.clicked.connect(lambda: self._emit_apply("replace"))
        self.btn_copy = QPushButton("📋 Copy phản hồi")
        self.btn_copy.clicked.connect(self._copy_latest)
        for btn in (self.btn_insert, self.btn_replace, self.btn_copy):
            btn.setEnabled(False)
            action_row.addWidget(btn)
        action_row.addStretch()
        root.addWidget(self.action_row_widget)

        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self._send)
        QShortcut(QKeySequence("Ctrl+Enter"), self, activated=self._send)
        self.set_compact(compact)
        self._update_context_hint()
        if load_api_key():
            QTimer.singleShot(250, self._refresh_models)

    def set_compact(self, compact):
        self.full_header.setVisible(not compact)
        self.compact_header.setVisible(compact)
        self.hint_label.setVisible(not compact)
        self.action_row_widget.setVisible(not compact)
        self.input_edit.setFixedHeight(76 if compact else 92)

    def _current_context(self):
        if callable(self.context_provider):
            return self.context_provider()
        return self.selected_text, self.document_text

    def _update_context_hint(self):
        selected_text, document_text = self._current_context()
        if selected_text:
            text = f"Vùng chọn: {len(selected_text.split())} từ"
        elif document_text:
            text = f"Tài liệu hiện tại: {len(document_text.split())} từ"
        else:
            text = "Không có vùng chọn"
        self.hint_label.setText(text)

    def _set_status(self, text, error=False):
        color = "#b91c1c" if error else "#475569"
        bg = "#fef2f2" if error else "#e0f2fe"
        border = "#fecaca" if error else "#bae6fd"
        self.hint_label.setStyleSheet(
            f"color:{color};background:{bg};border:1px solid {border};"
            "padding:6px 9px;border-radius:8px;")
        self.hint_label.setText(text)

    def _save_key_and_refresh(self):
        key = self.api_input.text().strip()
        save_api_key(key)
        if key:
            self._refresh_models()
        else:
            self._set_status("Chưa có API key Gemini.", error=True)

    def _refresh_models(self):
        key = self.api_input.text().strip() or load_api_key()
        if not key:
            self._set_status("Nhập Gemini API key để cập nhật model từ Google.", error=True)
            return
        save_api_key(key)
        self.btn_refresh_models.setEnabled(False)
        self.btn_refresh_models.setText("...")
        self._set_status("Đang cập nhật model từ Google...")

        self._model_thread = QThread(self)
        self._model_worker = ModelFetchWorker(key)
        self._model_worker.moveToThread(self._model_thread)
        self._model_thread.started.connect(self._model_worker.run)
        self._model_worker.finished.connect(self._on_models_loaded)
        self._model_worker.finished.connect(self._model_thread.quit)
        self._model_worker.finished.connect(self._model_worker.deleteLater)
        self._model_thread.finished.connect(self._model_thread.deleteLater)
        self._model_thread.start()

    def _on_models_loaded(self, models, error):
        self.btn_refresh_models.setEnabled(True)
        self.btn_refresh_models.setText("↻")
        if error:
            self._set_status("Không cập nhật được model: " + error, error=True)
            return
        if not models:
            self._set_status("Google không trả về model Gemini khả dụng.", error=True)
            return
        current = self.model_combo.currentText()
        self.model_combo.clear()
        self.model_combo.addItems(models)
        idx = self.model_combo.findText(current)
        self.model_combo.setCurrentIndex(idx if idx >= 0 else 0)
        cfg = load_editor_config()
        cfg["gemini_models_cache"] = models
        cfg["gemini_model"] = self.model_combo.currentText()
        save_editor_config(cfg)
        self._set_status(f"Đã cập nhật {len(models)} model từ Google.")

    def save_chat_image(self, image):
        folder = os.path.join(CONFIG_DIR, "ai_images")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"paste_{uuid.uuid4().hex[:10]}.png")
        image.save(path)
        return path

    def add_pending_images(self, paths):
        for path in paths:
            if path and path not in self.pending_images:
                self.pending_images.append(path)
        self._refresh_attach_label()

    def add_pending_image(self, path):
        self.add_pending_images([path])

    def _refresh_attach_label(self):
        if not self.pending_images:
            self.attach_label.setText("")
            return
        names = ", ".join(os.path.basename(p) for p in self.pending_images[-3:])
        extra = "" if len(self.pending_images) <= 3 else f" +{len(self.pending_images) - 3}"
        self.attach_label.setText(f"Ảnh đính kèm: {names}{extra}")

    def _attach_image(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Đính kèm ảnh", "", "Hình ảnh (*.png *.jpg *.jpeg *.webp)")
        self.add_pending_images(paths)

    def _context_for_message(self):
        selected_text, document_text = self._current_context()
        chunks = []
        if selected_text:
            chunks.append("=== VÙNG CHỌN TRONG EDITOR ===\n" + selected_text)
        elif document_text:
            doc = document_text
            if len(doc) > 12000:
                doc = doc[:12000] + "\n\n...[đã rút gọn]..."
            chunks.append("=== TÀI LIỆU HIỆN TẠI ===\n" + doc)
        return "\n\n".join(chunks)

    def _send(self):
        key = self.api_input.text().strip() or load_api_key()
        if not key:
            self._set_status("Nhập Gemini API key trong cửa sổ AI trước khi gửi.", error=True)
            return
        save_api_key(key)
        text = self.input_edit.toPlainText().strip()
        if not text and not self.pending_images:
            QMessageBox.information(self, "Trống", "Hãy nhập yêu cầu hoặc dán ảnh trước.")
            return

        context = self._context_for_message()
        full_text = text if not context else text + "\n\n" + context
        images = list(self.pending_images)
        self.pending_images.clear()
        self._refresh_attach_label()
        self.input_edit.clear()

        user_msg = {"role": "user", "text": full_text, "images": images}
        self.messages.append(user_msg)
        self._append_chat_bubble("user", text or "(ảnh)", images)

        cfg = load_editor_config()
        cfg["gemini_model"] = self.model_combo.currentText()
        save_editor_config(cfg)

        self.btn_send.setEnabled(False)
        self.btn_send.setText("Đang gửi...")

        self._thread = QThread(self)
        self._worker = GeminiWorker(key, self.model_combo.currentText(), list(self.messages))
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_finished(self, text, error):
        self.btn_send.setEnabled(True)
        self.btn_send.setText("Gửi")
        if error:
            self._append_chat_bubble("assistant", "LỖI: " + error)
            return
        self.latest_response = text
        self.messages.append({"role": "assistant", "text": text, "images": []})
        self._append_chat_bubble("assistant", text)
        for btn in (self.btn_insert, self.btn_replace, self.btn_copy):
            btn.setEnabled(True)

    def _append_chat_bubble(self, role, text, images=None):
        align = "right" if role == "user" else "left"
        bg = "#dbeafe" if role == "user" else "#ffffff"
        border = "#bfdbfe" if role == "user" else "#e2e8f0"
        title = "Bạn" if role == "user" else "AI"
        content = _markdown_fragment_to_html(text)
        img_note = ""
        if images:
            names = ", ".join(html.escape(os.path.basename(p)) for p in images)
            img_note = f"<div style='margin-top:6px;color:#475569;font-size:12px'>📎 {names}</div>"
        self.chat_view.append(
            f"<div align='{align}' style='margin:8px 4px'>"
            f"<div style='display:inline-block;max-width:82%;background:{bg};border:1px solid {border};"
            f"border-radius:10px;padding:8px 10px;text-align:left'>"
            f"<div style='font-weight:700;color:#1e3a8a;margin-bottom:4px'>{title}</div>"
            f"<div>{content}</div>{img_note}</div></div>"
        )
        self.chat_view.moveCursor(QTextCursor.MoveOperation.End)

    def _copy_latest(self):
        if self.latest_response:
            QApplication.clipboard().setText(self.latest_response)
            self.btn_copy.setText("Đã copy")

    def _emit_apply(self, action):
        if not self.latest_response.strip():
            QMessageBox.information(self, "Trống", "Chưa có phản hồi AI để chèn.")
            return
        self.apply_requested.emit(action, self.latest_response)


class AIQuickDialog(QDialog):
    """Dialog nổi chứa AIChatWidget đầy đủ."""

    def __init__(self, parent, selected_text="", document_text=""):
        super().__init__(parent)
        self.result_text = ""
        self.action_taken = None
        self._chat_taken = False

        self.setWindowTitle("AI Chat – eMeX")
        self.setMinimumSize(840, 680)
        self.setStyleSheet(AIChatWidget.LIGHT_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        self.chat_widget = AIChatWidget(
            self, selected_text=selected_text, document_text=document_text, compact=False)
        self.chat_widget.apply_requested.connect(self._finish)
        self.chat_widget.dock_requested.connect(self._dock)
        layout.addWidget(self.chat_widget)

        bottom = QHBoxLayout()
        bottom.addStretch()
        self.btn_close = QPushButton("Đóng")
        self.btn_close.clicked.connect(self.reject)
        bottom.addWidget(self.btn_close)
        layout.addLayout(bottom)

    def _finish(self, action, text):
        self.action_taken = action
        self.result_text = text
        self.accept()

    def _dock(self):
        self.action_taken = "dock"
        self.accept()

    def take_chat_widget(self):
        self._chat_taken = True
        try:
            self.chat_widget.apply_requested.disconnect(self._finish)
        except Exception:
            pass
        try:
            self.chat_widget.dock_requested.disconnect(self._dock)
        except Exception:
            pass
        self.layout().removeWidget(self.chat_widget)
        self.chat_widget.setParent(None)
        return self.chat_widget

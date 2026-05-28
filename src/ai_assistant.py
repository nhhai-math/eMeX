"""Gemini AI assistant – chatbox hỗ trợ soạn thảo Markdown."""
import base64
import html
import mimetypes
import os
import re
import uuid

import requests

from PyQt6.QtCore import Qt, QObject, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import (QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel,
                              QMessageBox, QPushButton, QScrollArea,
                              QSizePolicy, QTextEdit, QVBoxLayout, QWidget)

from .config import (CONFIG_DIR, ROOT_DIR, gemini_model_sort_key,
                     load_api_key, load_editor_config)
from .i18n import current_language, t

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


def _load_readme_context():
    """Read README.md so Gemini has app-specific support context."""
    path = os.path.join(ROOT_DIR, "README.md")
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read().strip()
    except Exception:
        return "Không đọc được README.md của ứng dụng."
    if len(text) > 24000:
        return text[:24000] + "\n\n...[README.md đã được rút gọn]..."
    return text


def _read_text_file(path, limit=60000):
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read(limit + 1)
    except Exception:
        return ""
    if len(text) > limit:
        return text[:limit] + "\n\n...[tệp đã được rút gọn]..."
    return text


class GeminiWorker(QObject):
    finished = pyqtSignal(str, str)   # (text, error)

    SYSTEM_PROMPT = (
        "You are an assistant that helps users use the eMeX application. "
        "Your only task is answering questions about eMeX usage, commands, menus, "
        "shortcuts, workflows, app configuration, and helping draft or edit Markdown, MathJax, "
        "and TikZ when it serves the document being edited in eMeX. "
        "Do not support topics outside the application; if the user asks about unrelated content, "
        "briefly decline and say you only support eMeX usage. "
        "Use the README.md below as the preferred context. If README.md does not contain the information, "
        "say that the app documentation does not include it instead of guessing. "
        "Language policy: detect the language of the latest user request and reply in that same language, "
        "including languages other than Vietnamese or English. If the request mixes languages, use the "
        "dominant language or the language the user explicitly asks for. If the latest request has no "
        "detectable language, use the current eMeX interface language. "
        "Answer concisely and directly. When the user asks how to write Markdown, formulas, "
        "or TikZ in eMeX, explain the steps and include a short Markdown example if needed; do not wrap "
        "the whole answer in a code fence unless the requested content is itself a code fence."
    )

    def __init__(self, api_key, model, messages):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.messages = messages

    def _system_prompt(self):
        ui_language = "English" if current_language() == "en" else "Vietnamese"
        return (
            self.SYSTEM_PROMPT
            + f"\n\nCurrent eMeX interface language: {ui_language}."
            + "\n\n=== eMeX README.md ===\n"
            + _load_readme_context()
        )

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
                "systemInstruction": {"parts": [{"text": self._system_prompt()}]},
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
                self.finished.emit("", t("Phản hồi không hợp lệ: {data}", data=data))
                return
            self.finished.emit(_clean_model_text(text), "")
        except Exception as exc:
            self.finished.emit("", t("Lỗi kết nối: {error}", error=exc))


# =============================================================================
# Chat bubble widgets – phong cách ChatBox: user phải, AI trái, có avatar
# =============================================================================
def _bubble_styled_html(markdown_text: str, color="#0f172a") -> str:
    """Render markdown đoạn ngắn + bọc style inline cho QLabel rich-text."""
    body = _markdown_fragment_to_html(markdown_text)
    return (
        f"<div style=\"font-size:13px;color:{color};line-height:1.55;\">"
        + body + "</div>"
    )


class ChatBubble(QFrame):
    """Một message – avatar tròn + bubble bo, căn lề theo role."""

    MAX_BUBBLE_WIDTH = 540

    def __init__(self, role, markdown_text, images=None, files=None, parent=None):
        super().__init__(parent)
        self.role = role
        self.setObjectName(f"chatRow_{role}")
        self.setStyleSheet(f"QFrame#chatRow_{role}{{background:transparent;}}")

        is_user = role == "user"
        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 4, 8, 4)
        outer.setSpacing(10)

        avatar = QLabel("🧑" if is_user else "🤖")
        avatar.setFixedSize(34, 34)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if is_user:
            avatar.setStyleSheet(
                "background:#2563eb;color:#ffffff;border-radius:17px;"
                "font-size:16px;font-weight:700;")
        else:
            avatar.setStyleSheet(
                "background:#ede9fe;color:#6d28d9;border-radius:17px;"
                "font-size:16px;font-weight:700;border:1px solid #ddd6fe;")

        bubble = QFrame()
        bubble.setObjectName("chatBubble")
        if is_user:
            bubble.setStyleSheet(
                "QFrame#chatBubble{background:#2563eb;border:1px solid #1d4ed8;"
                "border-radius:14px;border-bottom-right-radius:4px;}"
                "QLabel{background:transparent;color:#ffffff;}")
        else:
            bubble.setStyleSheet(
                "QFrame#chatBubble{background:#ffffff;border:1px solid #e2e8f0;"
                "border-radius:14px;border-bottom-left-radius:4px;}"
                "QLabel{background:transparent;color:#0f172a;}")
        bubble.setSizePolicy(QSizePolicy.Policy.Preferred,
                              QSizePolicy.Policy.Preferred)
        self._bubble_frame = bubble

        bubble_lay = QVBoxLayout(bubble)
        bubble_lay.setContentsMargins(13, 9, 13, 10)
        bubble_lay.setSpacing(4)

        self._content_color = "#ffffff" if is_user else "#0f172a"
        content = QLabel(_bubble_styled_html(markdown_text, color=self._content_color))
        content.setTextFormat(Qt.TextFormat.RichText)
        content.setWordWrap(True)
        content.setOpenExternalLinks(True)
        content.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse |
            Qt.TextInteractionFlag.LinksAccessibleByMouse)
        content.setMaximumWidth(self.MAX_BUBBLE_WIDTH - 32)
        if is_user:
            content.setStyleSheet("color:#ffffff;")
        self._content_label = content
        bubble_lay.addWidget(content)

        if images:
            names = ", ".join(html.escape(os.path.basename(p)) for p in images)
            img_lbl = QLabel(f"📎 {names}")
            img_lbl.setWordWrap(True)
            tint = "rgba(255,255,255,0.85)" if is_user else "#475569"
            img_lbl.setStyleSheet(f"color:{tint};font-size:11px;")
            bubble_lay.addWidget(img_lbl)

        if files:
            names = ", ".join(html.escape(os.path.basename(p)) for p in files)
            file_lbl = QLabel(f"📄 {names}")
            file_lbl.setWordWrap(True)
            tint = "rgba(255,255,255,0.85)" if is_user else "#475569"
            file_lbl.setStyleSheet(f"color:{tint};font-size:11px;")
            bubble_lay.addWidget(file_lbl)

        if is_user:
            outer.addStretch(1)
            outer.addWidget(bubble, 0)
            outer.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)
        else:
            outer.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)
            outer.addWidget(bubble, 0)
            outer.addStretch(1)
        self.set_available_width(self.MAX_BUBBLE_WIDTH)

    def set_markdown_text(self, markdown_text):
        self._content_label.setText(_bubble_styled_html(markdown_text, color=self._content_color))

    def set_available_width(self, width):
        width = max(160, min(self.MAX_BUBBLE_WIDTH, int(width)))
        self._bubble_frame.setMaximumWidth(width)
        self._content_label.setMaximumWidth(max(120, width - 32))
        self.updateGeometry()


class TypingBubble(QFrame):
    """Indicator '● ● ●' chạy nhịp khi đang đợi AI trả lời."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("typingRow")
        self.setStyleSheet("QFrame#typingRow{background:transparent;}")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 2, 8, 2)
        outer.setSpacing(10)

        avatar = QLabel("🤖")
        avatar.setFixedSize(34, 34)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(
            "background:#ede9fe;color:#6d28d9;border-radius:17px;"
            "font-size:16px;font-weight:700;border:1px solid #ddd6fe;")
        outer.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)

        dots = QLabel("○ ○ ○")
        dots.setStyleSheet(
            "background:#ffffff;border:1px solid #e2e8f0;color:#94a3b8;"
            "border-radius:14px;border-bottom-left-radius:4px;"
            "padding:9px 18px;font-size:16px;letter-spacing:3px;")
        outer.addWidget(dots, 0)
        outer.addStretch(1)

        self._dots_label = dots
        self._frames = ["○ ○ ○", "● ○ ○", "● ● ○", "● ● ●", "○ ● ●", "○ ○ ●"]
        self._tick = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.start(280)

    def _step(self):
        self._dots_label.setText(self._frames[self._tick % len(self._frames)])
        self._tick += 1

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)


class AttachmentCard(QFrame):
    """Preview một ảnh hoặc tệp văn bản đã dán vào chat."""

    def __init__(self, kind, path, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.path = path
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(136, 104)
        self.setStyleSheet(
            "QFrame{background:#ffffff;border:1px solid #cbd5e1;border-radius:8px;}"
            "QFrame:hover{border-color:#2563eb;background:#eff6ff;}"
            "QLabel{background:transparent;color:#0f172a;}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(7, 7, 7, 7)
        layout.setSpacing(4)

        if kind == "image":
            preview = QLabel()
            preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pix = QPixmap(path)
            if not pix.isNull():
                preview.setPixmap(pix.scaled(
                    118, 62,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
            else:
                preview.setText(t("Ảnh"))
            layout.addWidget(preview, 1)
            caption = os.path.basename(path)
        else:
            text = _read_text_file(path, limit=220).strip()
            text = re.sub(r"\s+", " ", text)
            preview = QLabel(text[:100] + ("..." if len(text) > 100 else ""))
            preview.setWordWrap(True)
            preview.setStyleSheet("font-size:10px;color:#475569;")
            layout.addWidget(preview, 1)
            caption = t("Văn bản đã dán")

        name = QLabel(caption)
        name.setStyleSheet("font-size:10px;font-weight:700;color:#334155;")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setToolTip(path)
        layout.addWidget(name)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.kind == "image":
                ImagePreviewDialog(self.path, self).exec()
            else:
                TextPreviewDialog(self.path, self).exec()
            event.accept()
            return
        super().mousePressEvent(event)


class ImagePreviewDialog(QDialog):
    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(os.path.basename(path))
        self.resize(900, 700)
        self.setStyleSheet(AIChatWidget.LIGHT_QSS)

        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pix = QPixmap(path)
        if not pix.isNull():
            label.setPixmap(pix)
        else:
            label.setText(t("Không mở được ảnh."))
        scroll.setWidget(label)
        layout.addWidget(scroll, 1)

        btn = QPushButton(t("Đóng"))
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignRight)


class TextPreviewDialog(QDialog):
    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(os.path.basename(path))
        self.resize(760, 560)
        self.setStyleSheet(AIChatWidget.LIGHT_QSS)

        layout = QVBoxLayout(self)
        viewer = QTextEdit()
        viewer.setReadOnly(True)
        viewer.setPlainText(_read_text_file(path, limit=200000))
        layout.addWidget(viewer, 1)

        btn = QPushButton(t("Đóng"))
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignRight)


class AssistantTitleBar(QFrame):
    dock_requested = pyqtSignal()
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos = None
        self.setFixedHeight(38)
        self.setStyleSheet(
            "QFrame{background:#f8fafc;border-bottom:1px solid #e2e8f0;}"
            "QLabel{background:transparent;color:#0f172a;}"
            "QPushButton{background:#ffffff;color:#0f172a;border:1px solid #cbd5e1;"
            "border-radius:6px;padding:4px 8px;}"
            "QPushButton:hover{background:#eff6ff;border-color:#2563eb;color:#1d4ed8;}"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 4, 8, 4)
        row.setSpacing(6)
        self.title_label = QLabel("✨ " + t("Trợ lý eMeX"))
        self.title_label.setStyleSheet("font-weight:700;")
        row.addWidget(self.title_label)
        row.addStretch()

        self.btn_dock = QPushButton("↧")
        self.btn_dock.setFixedSize(32, 28)
        self.btn_dock.setToolTip(t("Thu gọn Trợ lý eMeX sang cột trái"))
        self.btn_dock.clicked.connect(self.dock_requested.emit)
        row.addWidget(self.btn_dock)

        self.btn_close = QPushButton("×")
        self.btn_close.setFixedSize(32, 28)
        self.btn_close.setToolTip(t("Đóng"))
        self.btn_close.clicked.connect(self.close_requested.emit)
        row.addWidget(self.btn_close)

    def retranslate_ui(self):
        self.title_label.setText("✨ " + t("Trợ lý eMeX"))
        self.btn_dock.setToolTip(t("Thu gọn Trợ lý eMeX sang cột trái"))
        self.btn_close.setToolTip(t("Đóng"))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            window = self.window()
            current = event.globalPosition().toPoint()
            window.move(window.pos() + current - self._drag_pos)
            self._drag_pos = current
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)


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
        if source.hasText():
            text = source.text()
            if self.chat_widget.should_attach_text(text):
                self.chat_widget.add_pending_text(text)
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

    dock_requested = pyqtSignal()
    undock_requested = pyqtSignal()
    closed_requested = pyqtSignal()

    WELCOME_TEXT = (
        "Mình hỗ trợ cách dùng eMeX, các lệnh trong ứng dụng, và soạn/chỉnh Markdown, "
        "công thức, TikZ cho tài liệu trong eMeX. Khóa API và mô hình được cấu hình "
        "trong bảng Cài đặt."
    )

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

    def __init__(self, parent=None, compact=False):
        super().__init__(parent)
        self.setStyleSheet(self.LIGHT_QSS)
        self.messages = []
        self.pending_images = []
        self.pending_text_files = []
        self._thread = None
        self._worker = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        self.full_header = QWidget()
        header = QHBoxLayout(self.full_header)
        header.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.full_header)

        self.compact_header = QWidget()
        compact_row = QHBoxLayout(self.compact_header)
        compact_row.setContentsMargins(6, 4, 6, 4)
        self.compact_title = QLabel("✨ " + t("Trợ lý eMeX"))
        self.compact_title.setStyleSheet("font-weight:800;color:#111827;")
        compact_row.addWidget(self.compact_title)
        compact_row.addStretch()
        self.btn_undock = QPushButton("↟")
        self.btn_undock.setToolTip(t("Đưa Trợ lý eMeX trở lại cửa sổ nổi"))
        self.btn_undock.setFixedWidth(32)
        self.btn_undock.clicked.connect(self.undock_requested.emit)
        compact_row.addWidget(self.btn_undock)
        self.btn_close_compact = QPushButton("×")
        self.btn_close_compact.setToolTip(t("Đóng"))
        self.btn_close_compact.setFixedWidth(32)
        self.btn_close_compact.clicked.connect(self.closed_requested.emit)
        compact_row.addWidget(self.btn_close_compact)
        root.addWidget(self.compact_header)

        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.chat_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat_scroll.setStyleSheet(
            "QScrollArea{background:#f8fafc;border:1px solid #e2e8f0;"
            "border-radius:10px;}"
            "QScrollBar:vertical{background:transparent;width:10px;margin:2px;}"
            "QScrollBar::handle:vertical{background:#cbd5e1;border-radius:5px;"
            "min-height:32px;}"
            "QScrollBar::handle:vertical:hover{background:#94a3b8;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical"
            "{height:0;background:transparent;}"
            "QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical"
            "{background:transparent;}")
        self.chat_container = QWidget()
        self.chat_container.setStyleSheet("QWidget{background:#f8fafc;}")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(4, 8, 4, 8)
        self.chat_layout.setSpacing(2)
        self.chat_layout.addStretch(1)
        self.chat_scroll.setWidget(self.chat_container)
        root.addWidget(self.chat_scroll, 1)

        self._typing_bubble = None  # ref đến TypingBubble đang hiển thị

        self._welcome_bubble = self._append_chat_bubble("assistant", t(self.WELCOME_TEXT))

        self.attachment_strip = QWidget()
        self.attachment_strip.setVisible(False)
        self.attachment_layout = QHBoxLayout(self.attachment_strip)
        self.attachment_layout.setContentsMargins(0, 0, 0, 0)
        self.attachment_layout.setSpacing(8)
        self.attachment_layout.addStretch(1)
        root.addWidget(self.attachment_strip)

        input_bar = QHBoxLayout()
        self.input_edit = ChatInput(self)
        self.input_edit.setPlaceholderText(t("Nhập yêu cầu... Enter để gửi, Shift+Enter để xuống dòng, Ctrl+V để dán ảnh."))
        self.input_edit.setFixedHeight(84 if compact else 92)
        input_bar.addWidget(self.input_edit, 1)

        side = QVBoxLayout()
        self.btn_attach = QPushButton("📎 " + t("Ảnh"))
        self.btn_attach.clicked.connect(self._attach_image)
        side.addWidget(self.btn_attach)
        self.btn_send = QPushButton(t("Gửi"))
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

        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self._send)
        QShortcut(QKeySequence("Ctrl+Enter"), self, activated=self._send)
        self.set_compact(compact)

    def set_compact(self, compact):
        self.full_header.setVisible(False)
        self.compact_header.setVisible(compact)
        self.input_edit.setFixedHeight(76 if compact else 92)

    def retranslate_ui(self):
        """Cập nhật lại toàn bộ text cố định trong khung Trợ lý eMeX."""
        self.compact_title.setText("✨ " + t("Trợ lý eMeX"))
        self.btn_undock.setToolTip(t("Đưa Trợ lý eMeX trở lại cửa sổ nổi"))
        self.btn_close_compact.setToolTip(t("Đóng"))
        self.input_edit.setPlaceholderText(
            t("Nhập yêu cầu... Enter để gửi, Shift+Enter để xuống dòng, Ctrl+V để dán ảnh."))
        self.btn_attach.setText("📎 " + t("Ảnh"))
        self.btn_send.setText(t("Đang gửi...") if not self.btn_send.isEnabled() else t("Gửi"))
        if self._welcome_bubble is not None:
            self._welcome_bubble.set_markdown_text(t(self.WELCOME_TEXT))
        self._refresh_attachments()

    def _set_status(self, text, error=False):
        color = "#b91c1c" if error else "#475569"
        self.attach_label.setStyleSheet(f"color:{color};")
        self.attach_label.setText(text)

    def save_chat_image(self, image):
        folder = os.path.join(CONFIG_DIR, "ai_images")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"paste_{uuid.uuid4().hex[:10]}.png")
        image.save(path)
        return path

    def save_pasted_text(self, text):
        folder = os.path.join(CONFIG_DIR, "ai_files")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"paste_{uuid.uuid4().hex[:10]}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def should_attach_text(self, text):
        if not text:
            return False
        return len(text) >= 1200 or text.count("\n") >= 18

    def add_pending_images(self, paths):
        for path in paths:
            if path and path not in self.pending_images:
                self.pending_images.append(path)
        self._refresh_attachments()

    def add_pending_image(self, path):
        self.add_pending_images([path])

    def add_pending_text(self, text):
        path = self.save_pasted_text(text)
        self.pending_text_files.append(path)
        self._refresh_attachments()

    def _refresh_attachments(self):
        self.attach_label.setStyleSheet("color:#475569;")
        while self.attachment_layout.count() > 1:
            item = self.attachment_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for path in self.pending_text_files:
            self.attachment_layout.insertWidget(
                self.attachment_layout.count() - 1,
                AttachmentCard("text", path, self.attachment_strip))
        for path in self.pending_images:
            self.attachment_layout.insertWidget(
                self.attachment_layout.count() - 1,
                AttachmentCard("image", path, self.attachment_strip))
        has_attachments = bool(self.pending_images or self.pending_text_files)
        self.attachment_strip.setVisible(has_attachments)
        if not has_attachments:
            self.attach_label.setText("")
            return
        total = len(self.pending_images) + len(self.pending_text_files)
        self.attach_label.setText(t("Đính kèm: {count} mục", count=total))

    def _refresh_attach_label(self):
        self._refresh_attachments()

    def _attach_image(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, t("Đính kèm ảnh"), "", t("Hình ảnh (*.png *.jpg *.jpeg *.webp)"))
        self.add_pending_images(paths)

    def _send(self):
        key = load_api_key()
        if not key:
            self._set_status(t("Nhập khóa API Gemini trong Cài đặt > Gemini AI trước khi gửi."), error=True)
            return
        text = self.input_edit.toPlainText().strip()
        if not text and not self.pending_images and not self.pending_text_files:
            QMessageBox.information(self, t("Trống"), t("Hãy nhập yêu cầu hoặc dán nội dung trước."))
            return

        images = list(self.pending_images)
        text_files = list(self.pending_text_files)
        file_chunks = []
        for path in text_files:
            content = _read_text_file(path)
            if content:
                file_chunks.append(
                    f"=== TỆP VĂN BẢN ĐÃ DÁN: {os.path.basename(path)} ===\n{content}")
        full_text = text
        if file_chunks:
            full_text = "\n\n".join([part for part in [text, *file_chunks] if part])
        self.pending_images.clear()
        self.pending_text_files.clear()
        self._refresh_attachments()
        self.input_edit.clear()

        user_msg = {"role": "user", "text": full_text, "images": images}
        self.messages.append(user_msg)
        self._append_chat_bubble(
            "user",
            text or (t("(tệp văn bản)") if text_files else t("(ảnh)")),
            images,
            text_files)

        cfg = load_editor_config()
        model = cfg.get("gemini_model", "gemini-2.5-flash")

        self.btn_send.setEnabled(False)
        self.btn_send.setText(t("Đang gửi..."))
        self._show_typing()

        self._thread = QThread(self)
        self._worker = GeminiWorker(key, model, list(self.messages))
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_finished(self, text, error):
        self._hide_typing()
        self.btn_send.setEnabled(True)
        self.btn_send.setText(t("Gửi"))
        if error:
            self._append_chat_bubble("assistant", t("Lỗi: ") + error)
            return
        self.messages.append({"role": "assistant", "text": text, "images": []})
        self._append_chat_bubble("assistant", text)

    def _append_chat_bubble(self, role, text, images=None, files=None):
        bubble = ChatBubble(
            role, text, images=images, files=files, parent=self.chat_container)
        self._fit_chat_bubble(bubble)
        insert_idx = max(0, self.chat_layout.count() - 1)  # trước stretch
        # Nếu đang có typing indicator, đặt message trước nó để giữ thứ tự.
        if self._typing_bubble is not None:
            typing_pos = self.chat_layout.indexOf(self._typing_bubble)
            if typing_pos >= 0:
                insert_idx = typing_pos
        self.chat_layout.insertWidget(insert_idx, bubble)
        QTimer.singleShot(10, self._scroll_to_bottom)
        return bubble

    def _available_bubble_width(self):
        widths = [
            value for value in (self.width(), self.chat_scroll.viewport().width())
            if value and value > 0
        ]
        viewport_width = min(widths) if widths else self.MAX_BUBBLE_WIDTH
        # Trừ avatar, spacing, margins và scrollbar để bubble không bị cắt ở panel hẹp.
        return max(160, viewport_width - 74)

    def _fit_chat_bubble(self, bubble):
        if isinstance(bubble, ChatBubble):
            bubble.set_available_width(self._available_bubble_width())

    def _fit_all_chat_bubbles(self):
        for i in range(self.chat_layout.count()):
            widget = self.chat_layout.itemAt(i).widget()
            self._fit_chat_bubble(widget)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._fit_all_chat_bubbles)

    def _scroll_to_bottom(self):
        sb = self.chat_scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _show_typing(self):
        if self._typing_bubble is not None:
            return
        self._typing_bubble = TypingBubble(parent=self.chat_container)
        insert_idx = max(0, self.chat_layout.count() - 1)
        self.chat_layout.insertWidget(insert_idx, self._typing_bubble)
        QTimer.singleShot(10, self._scroll_to_bottom)

    def _hide_typing(self):
        if self._typing_bubble is None:
            return
        self.chat_layout.removeWidget(self._typing_bubble)
        self._typing_bubble.setParent(None)
        self._typing_bubble.deleteLater()
        self._typing_bubble = None


class AIQuickDialog(QDialog):
    """Dialog nổi chứa AIChatWidget đầy đủ."""

    def __init__(self, parent, chat_widget=None):
        super().__init__(parent)
        self.setObjectName("assistantDialog")
        self.action_taken = None
        self._chat_taken = False

        self.setWindowTitle(t("Trợ lý eMeX"))
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setMinimumSize(840, 680)
        self.setStyleSheet(
            AIChatWidget.LIGHT_QSS
            + """
            QDialog#assistantDialog{
                background:#f8fafc;
                border:2px solid #06b6d4;
            }
            """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        self.title_bar = AssistantTitleBar(self)
        self.title_bar.dock_requested.connect(self._dock)
        self.title_bar.close_requested.connect(self.reject)
        layout.addWidget(self.title_bar)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(14, 14, 14, 14)
        body_layout.setSpacing(8)
        self.chat_widget = chat_widget or AIChatWidget(self, compact=False)
        self.chat_widget.setParent(body)
        self.chat_widget.set_compact(False)
        body_layout.addWidget(self.chat_widget)
        layout.addWidget(body, 1)

    def retranslate_ui(self):
        self.setWindowTitle(t("Trợ lý eMeX"))
        self.title_bar.retranslate_ui()
        self.chat_widget.retranslate_ui()

    def _dock(self):
        self.action_taken = "dock"
        self.accept()

    def take_chat_widget(self):
        self._chat_taken = True
        try:
            self.title_bar.dock_requested.disconnect(self._dock)
        except Exception:
            pass
        self.chat_widget.parentWidget().layout().removeWidget(self.chat_widget)
        self.chat_widget.setParent(None)
        return self.chat_widget

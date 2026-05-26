"""Dialogs phụ trợ: Settings, About. Đều ép light theme."""
from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                              QFontComboBox, QFormLayout, QFrame, QHBoxLayout,
                              QLabel, QListWidget, QListWidgetItem,
                              QMessageBox, QPushButton, QSpinBox, QTabWidget,
                              QTextEdit, QVBoxLayout, QWidget)

from .ai_assistant import fetch_gemini_models
from .config import (APP_NAME, APP_VERSION, DEFAULT_EDITOR_CONFIG,
                     DEFAULT_GEMINI_MODELS, load_api_key, load_editor_config,
                     save_editor_config)


LIGHT_QSS = """
QDialog{background:#ffffff;color:#0f172a;}
QWidget{background:#ffffff;color:#0f172a;}
QLabel{color:#0f172a;background:transparent;}
QLineEdit, QTextEdit, QSpinBox, QComboBox, QFontComboBox{
    background:#ffffff;color:#0f172a;
    border:1px solid #cbd5e1;border-radius:6px;padding:4px 6px;
    selection-background-color:#2563eb;selection-color:#ffffff;
}
QComboBox QAbstractItemView{background:#ffffff;color:#0f172a;
    selection-background-color:#2563eb;selection-color:#ffffff;}
QPushButton{background:#ffffff;color:#0f172a;border:1px solid #cbd5e1;border-radius:6px;
    padding:6px 12px;}
QPushButton:hover{background:#eff6ff;border-color:#2563eb;color:#1d4ed8;}
QPushButton:default{background:#2563eb;color:#ffffff;border:0;}
QPushButton:default:hover{background:#1d4ed8;}
QTabWidget::pane{border:1px solid #e5e7eb;border-radius:8px;background:#ffffff;top:-1px;}
QTabBar::tab{background:#f8fafc;border:1px solid #e5e7eb;color:#475569;
    padding:6px 14px;margin-right:2px;border-top-left-radius:6px;border-top-right-radius:6px;}
QTabBar::tab:selected{background:#ffffff;color:#0f172a;font-weight:600;border-bottom-color:#ffffff;}
QListWidget{background:#ffffff;color:#0f172a;border:1px solid #cbd5e1;border-radius:6px;}
QCheckBox{color:#0f172a;background:transparent;}
QCheckBox::indicator{width:16px;height:16px;}
QCheckBox::indicator:unchecked{border:1px solid #94a3b8;background:#ffffff;border-radius:3px;}
QCheckBox::indicator:checked{border:1px solid #2563eb;background:#2563eb;border-radius:3px;}
"""


class _ModelFetcher(QObject):
    """Worker chạy fetch_gemini_models trong thread riêng."""
    finished = pyqtSignal(list, str)   # (models, error)

    def __init__(self, api_key):
        super().__init__()
        self.api_key = api_key

    def run(self):
        try:
            models = fetch_gemini_models(self.api_key)
            self.finished.emit(models, "")
        except Exception as exc:
            self.finished.emit([], str(exc))


class SettingsDialog(QDialog):
    """Cài đặt editor và model mặc định; API key nằm trong AI Chat."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cài đặt eMeX")
        self.setMinimumSize(620, 560)
        self.setStyleSheet(LIGHT_QSS)

        self.cfg = load_editor_config()

        outer = QVBoxLayout(self)
        tabs = QTabWidget()
        outer.addWidget(tabs)

        tabs.addTab(self._build_editor_tab(), "Editor")
        tabs.addTab(self._build_ai_tab(), "Gemini AI")

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.RestoreDefaults)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self._restore)
        outer.addWidget(btns)

        self._fetch_thread = None
        self._fetcher = None

    # ----- Editor tab -----
    def _build_editor_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)

        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont(self.cfg.get("font_family", "Consolas")))
        form.addRow("Font soạn thảo:", self.font_combo)

        self.font_size = QSpinBox()
        self.font_size.setRange(8, 32)
        self.font_size.setValue(self.cfg.get("font_size", 13))
        form.addRow("Cỡ chữ:", self.font_size)

        self.tab_size = QSpinBox()
        self.tab_size.setRange(1, 8)
        self.tab_size.setValue(self.cfg.get("tab_spaces", 2))
        form.addRow("Số khoảng trắng / Tab:", self.tab_size)

        self.cb_wrap = QCheckBox("Bật wrap line")
        self.cb_wrap.setChecked(self.cfg.get("wrap_lines", True))
        form.addRow("", self.cb_wrap)

        self.cb_auto_pair = QCheckBox("Tự đóng cặp { } [ ] ( ) \" \" $ $ ` `")
        self.cb_auto_pair.setChecked(self.cfg.get("auto_pair", True))
        form.addRow("", self.cb_auto_pair)

        self.cb_auto_save = QCheckBox("Tự động lưu sau 60s (chỉ file đã đặt tên)")
        self.cb_auto_save.setChecked(self.cfg.get("auto_save", False))
        form.addRow("", self.cb_auto_save)

        info = QLabel(
            "Mẹo: Ctrl+G mở Gemini AI · Ctrl+P bật/tắt preview · Ctrl+/ comment · Ctrl+Enter compile preview.")
        info.setStyleSheet("color:#6b7280;font-style:italic;padding-top:14px;")
        info.setWordWrap(True)
        form.addRow("", info)
        return w

    # ----- AI tab -----
    def _build_ai_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)

        help_link = QLabel(
            "API key được nhập trực tiếp trong cửa sổ <b>AI Chat</b>. "
            "Lấy key tại <a href='https://aistudio.google.com/app/apikey'>aistudio.google.com/app/apikey</a>.")
        help_link.setOpenExternalLinks(True)
        help_link.setTextFormat(Qt.TextFormat.RichText)
        help_link.setWordWrap(True)
        help_link.setStyleSheet("color:#475569;background:#f8fafc;border:1px solid #e2e8f0;"
                                "border-radius:8px;padding:8px 10px;")
        v.addWidget(help_link)

        v.addSpacing(8)

        # Models section
        model_header = QHBoxLayout()
        mh_label = QLabel("Model Gemini")
        mh_label.setStyleSheet("font-weight:600;")
        model_header.addWidget(mh_label)
        model_header.addStretch()
        self.btn_fetch = QPushButton("⟳ Tải danh sách model")
        self.btn_fetch.clicked.connect(self._fetch_models)
        model_header.addWidget(self.btn_fetch)
        v.addLayout(model_header)

        # Default model combo
        row_default = QHBoxLayout()
        row_default.addWidget(QLabel("Model mặc định:"))
        self.model_combo = QComboBox()
        models = self.cfg.get("gemini_models_cache") or DEFAULT_GEMINI_MODELS
        self.model_combo.addItems(models)
        cur = self.cfg.get("gemini_model", "gemini-2.5-flash")
        idx = self.model_combo.findText(cur)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        row_default.addWidget(self.model_combo, 1)
        v.addLayout(row_default)

        # Model list view
        self.model_list = QListWidget()
        self.model_list.setMinimumHeight(180)
        self._populate_model_list(models)
        v.addWidget(self.model_list, 1)

        self.fetch_status = QLabel("")
        self.fetch_status.setStyleSheet("color:#475569;font-style:italic;")
        v.addWidget(self.fetch_status)

        return w

    def _populate_model_list(self, models):
        self.model_list.clear()
        for name in models:
            item = QListWidgetItem(f"• {name}")
            self.model_list.addItem(item)

    def _fetch_models(self):
        key = load_api_key()
        if not key:
            QMessageBox.warning(self, "Thiếu API key",
                                "Hãy nhập API key trong cửa sổ AI Chat trước khi tải danh sách model.")
            return

        self.btn_fetch.setEnabled(False)
        self.btn_fetch.setText("⌛ Đang tải...")
        self.fetch_status.setText("Đang gọi Gemini API...")

        self._fetch_thread = QThread(self)
        self._fetcher = _ModelFetcher(key)
        self._fetcher.moveToThread(self._fetch_thread)
        self._fetch_thread.started.connect(self._fetcher.run)
        self._fetcher.finished.connect(self._on_fetch_done)
        self._fetcher.finished.connect(self._fetch_thread.quit)
        self._fetcher.finished.connect(self._fetcher.deleteLater)
        self._fetch_thread.finished.connect(self._fetch_thread.deleteLater)
        self._fetch_thread.start()

    def _on_fetch_done(self, models, error):
        self.btn_fetch.setEnabled(True)
        self.btn_fetch.setText("⟳ Tải danh sách model")
        if error:
            self.fetch_status.setText(f"❌ {error[:200]}")
            QMessageBox.critical(self, "Không tải được model",
                                 f"Chi tiết:\n{error[:600]}")
            return

        if not models:
            self.fetch_status.setText("⚠ Không có model nào hỗ trợ generateContent.")
            return

        # Cập nhật cache
        self.cfg["gemini_models_cache"] = models
        save_editor_config(self.cfg)

        cur = self.model_combo.currentText()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(models)
        if cur in models:
            self.model_combo.setCurrentText(cur)
        self.model_combo.blockSignals(False)

        self._populate_model_list(models)
        self.fetch_status.setText(
            f"✅ Đã tải {len(models)} model (sắp xếp mới → cũ).")

    def _restore(self):
        self.cfg = DEFAULT_EDITOR_CONFIG.copy()
        self.font_combo.setCurrentFont(QFont(self.cfg["font_family"]))
        self.font_size.setValue(self.cfg["font_size"])
        self.tab_size.setValue(self.cfg["tab_spaces"])
        self.cb_wrap.setChecked(self.cfg["wrap_lines"])
        self.cb_auto_pair.setChecked(self.cfg["auto_pair"])
        self.cb_auto_save.setChecked(self.cfg["auto_save"])
        self.model_combo.setCurrentText(self.cfg["gemini_model"])

    def _save(self):
        self.cfg["font_family"] = self.font_combo.currentFont().family()
        self.cfg["font_size"] = self.font_size.value()
        self.cfg["tab_spaces"] = self.tab_size.value()
        self.cfg["wrap_lines"] = self.cb_wrap.isChecked()
        self.cfg["auto_pair"] = self.cb_auto_pair.isChecked()
        self.cfg["auto_save"] = self.cb_auto_save.isChecked()
        self.cfg["gemini_model"] = self.model_combo.currentText()
        save_editor_config(self.cfg)
        self.accept()


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Giới thiệu {APP_NAME}")
        self.setFixedSize(520, 480)
        self.setStyleSheet(LIGHT_QSS)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)

        title = QLabel(APP_NAME)
        title.setStyleSheet("font-size:32px;font-weight:800;color:#1f2937;background:transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        ver = QLabel(f"Phiên bản {APP_VERSION}  ·  Markdown Editor")
        ver.setStyleSheet("color:#6b7280;background:transparent;")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(ver)

        lay.addSpacing(10)

        info = QTextEdit()
        info.setReadOnly(True)
        info.setStyleSheet(
            "QTextEdit{background:#f8fafc;color:#0f172a;border:1px solid #e5e7eb;"
            "border-radius:8px;padding:8px;}")
        info.setHtml(f"""
        <p><b>eMeX</b> là trình soạn thảo Markdown gọn nhẹ, tích hợp:</p>
        <ul>
          <li>Preview thời gian thực với <b>MathJax</b> + <b>TikZJax</b> cho công thức và hình vẽ.</li>
          <li>Trợ lý <b>Gemini AI</b> – bấm <b>Ctrl + G</b> để gọi.</li>
          <li>Bảng ký hiệu toán nhanh, autocomplete <code>h1, code, math, tikz…</code></li>
          <li>Multi-tab, find/replace, auto-pair, smart indent.</li>
        </ul>
        <p><b>Phím tắt chính:</b></p>
        <ul>
          <li><b>Ctrl+N / Ctrl+O / Ctrl+S</b> – Tạo / mở / lưu</li>
          <li><b>Ctrl+F / Ctrl+H</b> – Tìm / Thay thế</li>
          <li><b>Ctrl+G</b> – Gemini AI</li>
          <li><b>Ctrl+/ </b>– Toggle comment HTML</li>
          <li><b>Ctrl+Enter</b> – Compile preview</li>
          <li><b>Ctrl+P</b> – Bật/Tắt preview · <b>F11</b> – Zen mode</li>
          <li><b>Ctrl+B / Ctrl+I</b> – Bold / Italic</li>
          <li><b>Ctrl+M</b> – Math inline · <b>Ctrl+Shift+M</b> – Math block</li>
        </ul>
        """)
        lay.addWidget(info, 1)

        btn = QPushButton("Đóng")
        btn.setDefault(True)
        btn.clicked.connect(self.accept)
        lay.addWidget(btn)

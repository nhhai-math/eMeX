"""Dialogs phụ trợ: Settings, About. Đều ép light theme."""
from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                              QFontComboBox, QFormLayout, QFrame, QHBoxLayout,
                              QLabel, QLineEdit, QListWidget, QListWidgetItem,
                              QMessageBox, QPushButton, QSpinBox, QTabWidget,
                              QTextEdit, QVBoxLayout, QWidget, QGroupBox)

from .ai_assistant import fetch_gemini_models
from .config import (APP_NAME, APP_VERSION, DEFAULT_EDITOR_CONFIG,
                     DEFAULT_GEMINI_MODELS, load_api_key, load_editor_config,
                     save_api_key, save_editor_config)
from .i18n import current_language, language_name, set_language, supported_languages, t


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
    """Cài đặt editor và Gemini AI."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("Cài đặt eMeX"))
        self.setMinimumSize(620, 560)
        self.setStyleSheet(LIGHT_QSS)

        self.cfg = load_editor_config()
        self._initial_language = current_language()

        outer = QVBoxLayout(self)
        tabs = QTabWidget()
        outer.addWidget(tabs)

        tabs.addTab(self._build_editor_tab(), t("Trình soạn thảo"))
        tabs.addTab(self._build_ai_tab(), "Gemini AI")

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.RestoreDefaults)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self._restore)
        btns.button(QDialogButtonBox.StandardButton.Save).setText(t("Lưu"))
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText(t("Hủy"))
        btns.button(QDialogButtonBox.StandardButton.RestoreDefaults).setText(t("Mặc định"))
        outer.addWidget(btns)

        self._fetch_thread = None
        self._fetcher = None

    # ----- Editor tab -----
    def _build_editor_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)

        self.language_combo = QComboBox()
        for code in supported_languages():
            self.language_combo.addItem(language_name(code), code)
        lang_idx = self.language_combo.findData(current_language())
        if lang_idx >= 0:
            self.language_combo.setCurrentIndex(lang_idx)
        form.addRow(t("Ngôn ngữ:"), self.language_combo)

        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont(self.cfg.get("font_family", "Consolas")))
        form.addRow(t("Phông chữ soạn thảo:"), self.font_combo)

        self.font_size = QSpinBox()
        self.font_size.setRange(8, 32)
        self.font_size.setValue(self.cfg.get("font_size", 13))
        form.addRow(t("Cỡ chữ:"), self.font_size)

        self.tab_size = QSpinBox()
        self.tab_size.setRange(1, 8)
        self.tab_size.setValue(self.cfg.get("tab_spaces", 2))
        form.addRow(t("Số khoảng trắng / Tab:"), self.tab_size)

        self.cb_wrap = QCheckBox(t("Tự xuống dòng"))
        self.cb_wrap.setChecked(self.cfg.get("wrap_lines", True))
        form.addRow("", self.cb_wrap)

        self.cb_auto_pair = QCheckBox(t("Tự đóng cặp { } [ ] ( ) \" \" $ $ ` `"))
        self.cb_auto_pair.setChecked(self.cfg.get("auto_pair", True))
        form.addRow("", self.cb_auto_pair)

        self.cb_auto_save = QCheckBox(t("Tự động lưu sau 60 giây (chỉ tệp đã đặt tên)"))
        self.cb_auto_save.setChecked(self.cfg.get("auto_save", False))
        form.addRow("", self.cb_auto_save)

        # --- Nhóm kích thước giao diện ---
        size_group = QGroupBox(t("Kích thước thanh công cụ && biểu tượng"))
        size_group.setStyleSheet("""
            QGroupBox {
                font-weight:600; color:#1d4ed8;
                border:1px solid #e5e7eb; border-radius:8px;
                margin-top:14px; padding:14px 10px 10px 10px;
            }
            QGroupBox::title {
                subcontrol-origin:margin; left:12px;
                padding:0 6px; background:#ffffff;
            }
        """)
        size_form = QFormLayout(size_group)
        size_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        size_form.setSpacing(8)

        self.spin_toolbar_icon = QSpinBox()
        self.spin_toolbar_icon.setRange(16, 48)
        self.spin_toolbar_icon.setSuffix(" px")
        self.spin_toolbar_icon.setValue(self.cfg.get("toolbar_icon_size", 22))
        self.spin_toolbar_icon.setToolTip(t("Kích thước biểu tượng emoji trên thanh công cụ chính"))
        size_form.addRow(t("Cỡ biểu tượng thanh công cụ:"), self.spin_toolbar_icon)

        self.spin_toolbar_padding = QSpinBox()
        self.spin_toolbar_padding.setRange(2, 16)
        self.spin_toolbar_padding.setSuffix(" px")
        self.spin_toolbar_padding.setValue(self.cfg.get("toolbar_btn_padding", 6))
        self.spin_toolbar_padding.setToolTip(t("Đệm bên trong mỗi nút trên thanh công cụ"))
        size_form.addRow(t("Đệm nút thanh công cụ:"), self.spin_toolbar_padding)

        self.spin_symbol_size = QSpinBox()
        self.spin_symbol_size.setRange(24, 64)
        self.spin_symbol_size.setSuffix(" px")
        self.spin_symbol_size.setValue(self.cfg.get("symbol_btn_size", 38))
        self.spin_symbol_size.setToolTip(t("Kích thước mỗi nút ký hiệu ở bảng bên trái"))
        size_form.addRow(t("Nút bảng ký hiệu:"), self.spin_symbol_size)

        self.spin_symbol_font = QSpinBox()
        self.spin_symbol_font.setRange(9, 28)
        self.spin_symbol_font.setSuffix(" pt")
        self.spin_symbol_font.setValue(self.cfg.get("symbol_btn_font_size", 13))
        self.spin_symbol_font.setToolTip(t("Cỡ chữ trên các nút ký hiệu"))
        size_form.addRow(t("Cỡ chữ ký hiệu:"), self.spin_symbol_font)

        form.addRow(size_group)

        info = QLabel(
            t("Mẹo: Ctrl+G mở Trợ lý eMeX · Ctrl+P bật/tắt xem trước · Ctrl+/ bình luận · Ctrl+Enter biên dịch xem trước."))
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
            t("Cấu hình Gemini dùng cho Trợ lý eMeX. Lấy khóa API tại <a href='https://aistudio.google.com/app/apikey'>aistudio.google.com/app/apikey</a>."))
        help_link.setOpenExternalLinks(True)
        help_link.setTextFormat(Qt.TextFormat.RichText)
        help_link.setWordWrap(True)
        help_link.setStyleSheet("color:#475569;background:#f8fafc;border:1px solid #e2e8f0;"
                                "border-radius:8px;padding:8px 10px;")
        v.addWidget(help_link)

        v.addSpacing(8)

        api_row = QHBoxLayout()
        api_row.addWidget(QLabel(t("Khóa API Gemini:")))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText(t("Dán khóa API Gemini"))
        self.api_key_input.setText(load_api_key())
        api_row.addWidget(self.api_key_input, 1)
        v.addLayout(api_row)

        # Models section
        model_header = QHBoxLayout()
        mh_label = QLabel(t("Mô hình Gemini"))
        mh_label.setStyleSheet("font-weight:600;")
        model_header.addWidget(mh_label)
        model_header.addStretch()
        self.btn_fetch = QPushButton("⟳ " + t("Tải danh sách mô hình"))
        self.btn_fetch.clicked.connect(self._fetch_models)
        model_header.addWidget(self.btn_fetch)
        v.addLayout(model_header)

        # Default model combo
        row_default = QHBoxLayout()
        row_default.addWidget(QLabel(t("Mô hình mặc định:")))
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
        key = self.api_key_input.text().strip()
        if not key:
            QMessageBox.warning(self, t("Thiếu khóa API"),
                                t("Hãy nhập khóa API trong tab Gemini AI trước khi tải danh sách mô hình."))
            return
        save_api_key(key)

        self.btn_fetch.setEnabled(False)
        self.btn_fetch.setText("⌛ " + t("Đang tải..."))
        self.fetch_status.setText(t("Đang gọi Gemini API..."))

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
        self.btn_fetch.setText("⟳ " + t("Tải danh sách mô hình"))
        if error:
            self.fetch_status.setText(f"❌ {error[:200]}")
            QMessageBox.critical(self, t("Không tải được mô hình"),
                                 t("Chi tiết:\n{error}", error=error[:600]))
            return

        if not models:
            self.fetch_status.setText("⚠ " + t("Không có mô hình nào hỗ trợ generateContent."))
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
            "✅ " + t("Đã tải {count} mô hình (sắp xếp mới → cũ).", count=len(models)))

    def _restore(self):
        self.cfg = DEFAULT_EDITOR_CONFIG.copy()
        self.font_combo.setCurrentFont(QFont(self.cfg["font_family"]))
        self.font_size.setValue(self.cfg["font_size"])
        self.tab_size.setValue(self.cfg["tab_spaces"])
        self.cb_wrap.setChecked(self.cfg["wrap_lines"])
        self.cb_auto_pair.setChecked(self.cfg["auto_pair"])
        self.cb_auto_save.setChecked(self.cfg["auto_save"])
        self.spin_toolbar_icon.setValue(self.cfg["toolbar_icon_size"])
        self.spin_toolbar_padding.setValue(self.cfg["toolbar_btn_padding"])
        self.spin_symbol_size.setValue(self.cfg["symbol_btn_size"])
        self.spin_symbol_font.setValue(self.cfg["symbol_btn_font_size"])
        self.model_combo.setCurrentText(self.cfg["gemini_model"])
        lang_idx = self.language_combo.findData(self.cfg.get("language", "vi"))
        if lang_idx >= 0:
            self.language_combo.setCurrentIndex(lang_idx)

    def _save(self):
        language = self.language_combo.currentData() or "vi"
        set_language(str(language))
        self.cfg = load_editor_config()
        self.cfg["font_family"] = self.font_combo.currentFont().family()
        self.cfg["font_size"] = self.font_size.value()
        self.cfg["tab_spaces"] = self.tab_size.value()
        self.cfg["wrap_lines"] = self.cb_wrap.isChecked()
        self.cfg["auto_pair"] = self.cb_auto_pair.isChecked()
        self.cfg["auto_save"] = self.cb_auto_save.isChecked()
        self.cfg["toolbar_icon_size"] = self.spin_toolbar_icon.value()
        self.cfg["toolbar_btn_padding"] = self.spin_toolbar_padding.value()
        self.cfg["symbol_btn_size"] = self.spin_symbol_size.value()
        self.cfg["symbol_btn_font_size"] = self.spin_symbol_font.value()
        self.cfg["gemini_model"] = self.model_combo.currentText()
        self.cfg["language"] = str(language)
        save_editor_config(self.cfg)
        save_api_key(self.api_key_input.text().strip())
        self.accept()


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("Giới thiệu {app}", app=APP_NAME))
        self.setFixedSize(520, 480)
        self.setStyleSheet(LIGHT_QSS)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)

        title = QLabel(APP_NAME)
        title.setStyleSheet("font-size:32px;font-weight:800;color:#1f2937;background:transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        ver = QLabel(t("Phiên bản {version} · Trình soạn thảo Markdown", version=APP_VERSION))
        ver.setStyleSheet("color:#6b7280;background:transparent;")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(ver)

        lay.addSpacing(10)

        info = QTextEdit()
        info.setReadOnly(True)
        info.setStyleSheet(
            "QTextEdit{background:#f8fafc;color:#0f172a;border:1px solid #e5e7eb;"
            "border-radius:8px;padding:8px;}")
        info.setHtml(_about_html())
        lay.addWidget(info, 1)

        btn = QPushButton(t("Đóng"))
        btn.setDefault(True)
        btn.clicked.connect(self.accept)
        lay.addWidget(btn)


def _about_html() -> str:
    if current_language() == "en":
        return """
        <p><b>eMeX</b> is a lightweight Markdown editor with:</p>
        <ul>
          <li>Live preview with <b>MathJax</b> + <b>TikZJax</b> for formulas and drawings.</li>
          <li><b>eMeX Assistant</b> powered by Gemini, opened with <b>Ctrl + G</b>.</li>
          <li>A quick math symbol palette and snippet completion such as <code>h1, code, math, tikz...</code></li>
          <li>Tabs, find/replace, auto-pairing, and smart indentation.</li>
        </ul>
        <p><b>Main shortcuts:</b></p>
        <ul>
          <li><b>Ctrl+N / Ctrl+O / Ctrl+S</b> - New / open / save</li>
          <li><b>Ctrl+F / Ctrl+H</b> - Find / replace</li>
          <li><b>Ctrl+G</b> - eMeX Assistant</li>
          <li><b>Ctrl+/ </b>- Toggle HTML comment</li>
          <li><b>Ctrl+Enter</b> - Compile preview</li>
          <li><b>Ctrl+P</b> - Toggle preview · <b>F11</b> - Focus mode</li>
          <li><b>Ctrl+B / Ctrl+I</b> - Bold / italic</li>
          <li><b>Ctrl+M</b> - Inline math · <b>Ctrl+Shift+M</b> - Block math</li>
        </ul>
        """
    return """
    <p><b>eMeX</b> là trình soạn thảo Markdown gọn nhẹ, tích hợp:</p>
    <ul>
      <li>Xem trước thời gian thực với <b>MathJax</b> + <b>TikZJax</b> cho công thức và hình vẽ.</li>
      <li><b>Trợ lý eMeX</b> dùng Gemini, bấm <b>Ctrl + G</b> để gọi.</li>
      <li>Bảng ký hiệu toán nhanh và tự hoàn thành đoạn mẫu như <code>h1, code, math, tikz...</code></li>
      <li>Nhiều thẻ, tìm/thay thế, tự đóng cặp và tự thụt dòng thông minh.</li>
    </ul>
    <p><b>Phím tắt chính:</b></p>
    <ul>
      <li><b>Ctrl+N / Ctrl+O / Ctrl+S</b> - Tạo / mở / lưu</li>
      <li><b>Ctrl+F / Ctrl+H</b> - Tìm / thay thế</li>
      <li><b>Ctrl+G</b> - Trợ lý eMeX</li>
      <li><b>Ctrl+/ </b>- Bật/tắt bình luận HTML</li>
      <li><b>Ctrl+Enter</b> - Biên dịch xem trước</li>
      <li><b>Ctrl+P</b> - Bật/tắt xem trước · <b>F11</b> - Chế độ tập trung</li>
      <li><b>Ctrl+B / Ctrl+I</b> - In đậm / in nghiêng</li>
      <li><b>Ctrl+M</b> - Toán trong dòng · <b>Ctrl+Shift+M</b> - Toán khối</li>
    </ul>
    """

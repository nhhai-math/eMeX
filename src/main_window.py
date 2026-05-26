"""Cửa sổ chính eMeX – Markdown only, một toolbar gọn gàng."""
import os
import sys

from PyQt6.QtCore import Qt, QSize, QTimer, QUrl
from PyQt6.QtGui import (QAction, QActionGroup, QColor, QDesktopServices,
                          QFont, QIcon, QKeySequence, QPainter, QPixmap,
                          QShortcut, QTextCursor, QTextDocument)
from PyQt6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout,
                              QInputDialog, QLabel, QLineEdit, QMainWindow,
                              QMenu, QMessageBox, QPlainTextEdit, QPushButton,
                              QSizePolicy, QSplitter, QStatusBar, QTabWidget,
                              QToolBar, QToolButton, QVBoxLayout, QWidget,
                              QFrame)

from .ai_assistant import AIChatWidget, AIQuickDialog
from .config import (APP_ICON_FILE, APP_NAME, APP_VERSION, MARKDOWN_DEFAULT_DOC, SESSION_FILE,
                     load_editor_config, load_recent, push_recent,
                     save_editor_config, save_json)
from .dialogs import AboutDialog, SettingsDialog
from .editor import CodeEditor
from .exporters import markdown_to_docx, markdown_to_html, markdown_to_latex
from .preview import PreviewPane
from .symbol_palette import SymbolPalette


def emoji_icon(emoji, size=36):
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
    if sys.platform == "darwin":
        font = QFont("Apple Color Emoji", int(size * 0.65))
    else:
        font = QFont("Segoe UI Emoji", int(size * 0.6))
    p.setFont(font)
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, emoji)
    p.end()
    return QIcon(pm)


def _vline():
    """Một đường phân cách dọc mảnh, hiện đại hơn QToolBar separator mặc định."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.VLine)
    line.setStyleSheet("color:#e2e8f0;background:#e2e8f0;max-width:1px;margin:6px 6px;")
    line.setFixedWidth(1)
    return line


class EmexWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.editor_config = load_editor_config()

        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        if os.path.exists(APP_ICON_FILE):
            self.setWindowIcon(QIcon(APP_ICON_FILE))
        self.resize(1400, 880)
        self.last_export_path = ""

        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self._do_render_current_block)

        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.setInterval(60_000)
        self.auto_save_timer.timeout.connect(self._auto_save)
        if self.editor_config.get("auto_save", False):
            self.auto_save_timer.start()

        # Stylesheet tổng
        self.setStyleSheet("""
            QMainWindow{background:#f1f5f9;color:#0f172a;}
            QWidget{color:#0f172a;}
            QToolBar{background:#ffffff;border:0;border-bottom:1px solid #e5e7eb;
                spacing:1px;padding:6px 10px;}
            QToolBar QToolButton{background:transparent;color:#334155;
                padding:6px 9px;border-radius:8px;font-size:13px;margin:0 1px;}
            QToolBar QToolButton:hover{background:#eff6ff;color:#1d4ed8;}
            QToolBar QToolButton:checked{background:#dbeafe;color:#1d4ed8;}
            QToolBar QToolButton:pressed{background:#bfdbfe;}
            QToolBar QToolButton::menu-indicator{
                image:none;
                subcontrol-position: right center;
                subcontrol-origin: padding;
                width:10px;
            }
            QToolBar QLabel{color:#0f172a;background:transparent;padding:0 4px;}
            QToolBar::separator{background:#e2e8f0;width:1px;margin:6px 6px;}
            QStatusBar{background:#0f172a;color:#e2e8f0;}
            QStatusBar QLabel{color:#e2e8f0;background:transparent;padding:0 8px;}
            QTabWidget::pane{border:0;background:#ffffff;}
            QSplitter::handle{background:#e5e7eb;}
            QSplitter::handle:hover{background:#cbd5e1;}
            QMessageBox{background:#ffffff;color:#0f172a;}
            QMenu{background:#ffffff;color:#0f172a;border:1px solid #cbd5e1;padding:4px;}
            QMenu::item{padding:7px 16px;border-radius:5px;margin:1px 2px;}
            QMenu::item:selected{background:#2563eb;color:#ffffff;}
            QMenu::separator{height:1px;background:#e5e7eb;margin:4px 6px;}
            QInputDialog{background:#ffffff;color:#0f172a;}
        """)

        self._build_ui()
        self._build_actions()
        self._build_toolbar()
        self._install_shortcuts()

        self.recent_files = load_recent()
        self._load_session_or_default()

        # Không menu bar
        self.setMenuBar(None)

    # =====================================================================
    # UI scaffolding
    # =====================================================================
    def _build_ui(self):
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.tabs.setStyleSheet("""
            QTabBar{background:#ffffff;}
            QTabBar::tab {
                background:#f8fafc;
                border:1px solid #e5e7eb;
                border-bottom:0;
                padding:6px 14px;
                margin-right:2px;
                color:#475569;
            }
            QTabBar::tab:selected {background:#ffffff;color:#0f172a;font-weight:600;}
            QTabBar::tab:hover {background:#eff6ff;color:#1d4ed8;}
            QTabBar::close-button{
                image:none;
                subcontrol-position: right;
            }
        """)

        self.symbol_palette = SymbolPalette()
        self.symbol_palette.snippet_clicked.connect(self._insert_snippet_to_current)

        self.preview = PreviewPane(self)
        self.preview.btn_compile.clicked.connect(self._compile_preview)
        self.preview.web.loadFinished.connect(lambda _ok: self.preview.set_compiling(False))
        self.preview.web.source_line_requested.connect(self._sync_editor_to_preview_line)

        self.editor_splitter = QSplitter(Qt.Orientation.Vertical)
        self.editor_splitter.addWidget(self.tabs)
        self.ai_panel_host = QWidget()
        self.ai_panel_host.setVisible(False)
        self.ai_panel_layout = QVBoxLayout(self.ai_panel_host)
        self.ai_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.ai_panel_layout.setSpacing(0)
        self.ai_chat_widget = None
        self.editor_splitter.addWidget(self.ai_panel_host)
        self.editor_splitter.setSizes([720, 220])
        self.editor_splitter.setStretchFactor(0, 1)
        self.editor_splitter.setStretchFactor(1, 0)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.addWidget(self.symbol_palette)
        self.main_splitter.addWidget(self.editor_splitter)
        self.main_splitter.addWidget(self.preview)
        self.main_splitter.setSizes([260, 600, 540])
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStretchFactor(2, 1)
        self.main_splitter.setChildrenCollapsible(False)

        self.find_bar = self._build_find_bar()

        outer.addWidget(self.find_bar)
        outer.addWidget(self.main_splitter, 1)
        self.setCentralWidget(central)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status_msg = QLabel("Sẵn sàng")
        self.status_pos = QLabel("Dòng 1, Cột 1")
        self.status_words = QLabel("0 từ")
        self.status.addWidget(self.status_msg, 1)
        self.status.addPermanentWidget(self.status_words)
        self.status.addPermanentWidget(self.status_pos)

    def _build_find_bar(self):
        bar = QWidget()
        bar.setStyleSheet(
            "QWidget{background:#fef3c7;color:#0f172a;}"
            "QLabel{color:#0f172a;background:transparent;}"
            "QLineEdit{background:#ffffff;color:#0f172a;border:1px solid #cbd5e1;border-radius:4px;padding:3px 6px;}"
            "QPushButton{background:#ffffff;color:#0f172a;border:1px solid #cbd5e1;"
            "border-radius:4px;padding:4px 8px;}"
            "QPushButton:hover{background:#fde68a;}")
        bar.setVisible(False)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(6)

        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Tìm...")
        self.find_input.returnPressed.connect(self._find_next)

        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Thay bằng...")

        btn_prev = QPushButton("◀")
        btn_next = QPushButton("▶")
        btn_rep = QPushButton("Thay")
        btn_rep_all = QPushButton("Thay tất cả")
        btn_close = QPushButton("✕")
        for b in (btn_prev, btn_next, btn_close):
            b.setFixedWidth(34)
        btn_prev.clicked.connect(self._find_prev)
        btn_next.clicked.connect(self._find_next)
        btn_rep.clicked.connect(self._replace_one)
        btn_rep_all.clicked.connect(self._replace_all)
        btn_close.clicked.connect(lambda: bar.setVisible(False))

        lay.addWidget(QLabel("Tìm:"))
        lay.addWidget(self.find_input, 2)
        lay.addWidget(btn_prev)
        lay.addWidget(btn_next)
        lay.addWidget(QLabel("Thay:"))
        lay.addWidget(self.replace_input, 2)
        lay.addWidget(btn_rep)
        lay.addWidget(btn_rep_all)
        lay.addStretch()
        lay.addWidget(btn_close)
        return bar

    # =====================================================================
    # Actions
    # =====================================================================
    def _build_actions(self):
        # ---- File ----
        self.act_new = QAction(emoji_icon("📄"), "Mới (Ctrl+N)", self)
        self.act_new.setShortcut("Ctrl+N")
        self.act_new.triggered.connect(self._new_file)

        self.act_open = QAction(emoji_icon("📂"), "Mở (Ctrl+O)", self)
        self.act_open.setShortcut("Ctrl+O")
        self.act_open.triggered.connect(self._open_file)

        self.act_save = QAction(emoji_icon("💾"), "Lưu (Ctrl+S)", self)
        self.act_save.setShortcut("Ctrl+S")
        self.act_save.triggered.connect(self._save_current)

        # Save As – KHÔNG xuất hiện trên toolbar nữa, chỉ giữ shortcut
        self.act_save_as = QAction("Lưu thành... (Ctrl+Shift+S)", self)
        self.act_save_as.setShortcut("Ctrl+Shift+S")
        self.act_save_as.triggered.connect(self._save_as_current)
        self.addAction(self.act_save_as)

        # ---- Format ----
        self.act_bold = QAction(emoji_icon("𝐁"), "In đậm (Ctrl+B)", self)
        self.act_bold.setShortcut("Ctrl+B")
        self.act_bold.triggered.connect(lambda: self._wrap_selection("bold"))

        self.act_italic = QAction(emoji_icon("𝑰"), "In nghiêng (Ctrl+I)", self)
        self.act_italic.setShortcut("Ctrl+I")
        self.act_italic.triggered.connect(lambda: self._wrap_selection("italic"))

        self.act_strike = QAction(emoji_icon("S̶"), "Gạch ngang", self)
        self.act_strike.triggered.connect(lambda: self._wrap_selection("strike"))

        self.act_code = QAction(emoji_icon("⟨⟩"), "Inline code", self)
        self.act_code.triggered.connect(lambda: self._wrap_selection("code"))

        self.act_inline_math = QAction(emoji_icon("∑"), "Toán inline (Ctrl+M)", self)
        self.act_inline_math.setShortcut("Ctrl+M")
        self.act_inline_math.triggered.connect(self._inline_math)

        self.act_block_math = QAction(emoji_icon("∫"), "Toán block (Ctrl+Shift+M)", self)
        self.act_block_math.setShortcut("Ctrl+Shift+M")
        self.act_block_math.triggered.connect(self._block_math)

        # ---- Insert ----
        self.act_quote = QAction(emoji_icon("❝"), "Trích dẫn", self)
        self.act_quote.triggered.connect(lambda: self._line_prefix("> "))

        self.act_hr = QAction(emoji_icon("━"), "Đường ngang", self)
        self.act_hr.triggered.connect(
            lambda: self._cur_editor() and self._cur_editor().apply_snippet("\n---\n"))

        self.act_link = QAction(emoji_icon("🔗"), "Chèn link", self)
        self.act_link.triggered.connect(self._insert_link)

        self.act_image = QAction(emoji_icon("🖼"), "Chèn ảnh", self)
        self.act_image.triggered.connect(self._insert_image)

        self.act_table = QAction(emoji_icon("▦"), "Bảng (Ctrl+T)", self)
        self.act_table.setShortcut("Ctrl+T")
        self.act_table.triggered.connect(self._insert_table)

        self.act_codeblock = QAction(emoji_icon("⌨"), "Code block", self)
        self.act_codeblock.triggered.connect(self._insert_codeblock)

        self.act_comment = QAction(emoji_icon("💬"), "Comment HTML (Ctrl+/)", self)
        self.act_comment.setShortcut("Ctrl+/")
        self.act_comment.triggered.connect(self._toggle_comment_current)

        # ---- Tools ----
        self.act_find = QAction(emoji_icon("🔍"), "Tìm (Ctrl+F)", self)
        self.act_find.setShortcut("Ctrl+F")
        self.act_find.triggered.connect(self._show_find)

        self.act_replace = QAction("Thay (Ctrl+H)", self)
        self.act_replace.setShortcut("Ctrl+H")
        self.act_replace.triggered.connect(self._show_find)
        self.addAction(self.act_replace)

        self.act_render = QAction(emoji_icon("▶"), "Compile preview (Ctrl+Enter)", self)
        self.act_render.setShortcuts([QKeySequence("Ctrl+Return"), QKeySequence("Ctrl+Enter")])
        self.act_render.triggered.connect(self._compile_preview)

        self.act_ai = QAction(emoji_icon("🤖"), "AI Assistant (Ctrl+G)", self)
        self.act_ai.setShortcut("Ctrl+G")
        self.act_ai.triggered.connect(self.trigger_ai_assistant)

        # ---- View ----
        self.act_toggle_preview = QAction(emoji_icon("👁"), "Bật/Tắt preview (Ctrl+P)", self)
        self.act_toggle_preview.setShortcut("Ctrl+P")
        self.act_toggle_preview.setCheckable(True)
        self.act_toggle_preview.setChecked(True)
        self.act_toggle_preview.toggled.connect(self._toggle_preview)

        self.act_toggle_palette = QAction(emoji_icon("∑"), "Bật/Tắt bảng ký hiệu", self)
        self.act_toggle_palette.setCheckable(True)
        self.act_toggle_palette.setChecked(True)
        self.act_toggle_palette.toggled.connect(self._toggle_palette)

        self.act_zen = QAction(emoji_icon("🧘"), "Zen mode (F11)", self)
        self.act_zen.setShortcut("F11")
        self.act_zen.setCheckable(True)
        self.act_zen.toggled.connect(self._toggle_zen)

        # ---- Settings ----
        self.act_settings = QAction(emoji_icon("⚙"), "Cài đặt", self)
        self.act_settings.triggered.connect(self._open_settings)

        self.act_about = QAction(emoji_icon("ℹ"), "Giới thiệu", self)
        self.act_about.triggered.connect(self._open_about)

        # Các action nằm trong menu dropdown vẫn cần nhận shortcut khi menu đang đóng.
        for action in (self.act_open, self.act_save, self.act_bold, self.act_italic,
                       self.act_inline_math, self.act_block_math,
                       self.act_table, self.act_comment, self.act_find,
                       self.act_render, self.act_ai, self.act_toggle_preview,
                       self.act_zen):
            self.addAction(action)

    # =====================================================================
    # Toolbar layout
    # =====================================================================
    def _build_toolbar(self):
        self._configure_preview_export_menu()

        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setIconSize(QSize(22, 22))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

        # Group 1 – File
        for a in (self.act_new,):
            tb.addAction(a)
        self.btn_open = QToolButton()
        self.btn_open.setText("📂")
        self.btn_open.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.btn_open.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_open.setToolTip("Mở tệp Markdown / tệp gần đây")
        self.btn_open.setStyleSheet(
            "QToolButton{padding:6px 10px;border-radius:8px;color:#334155;font-size:13px;}"
            "QToolButton:hover{background:#eff6ff;color:#1d4ed8;}"
            "QToolButton::menu-indicator{image:none;}")
        self._refresh_recent_menu()
        tb.addWidget(self.btn_open)
        self.btn_save = self._make_command_button(
            "💾", "Lưu tệp Markdown hiện tại (Ctrl+S)", self.act_save)
        tb.addWidget(self.btn_save)

        tb.addWidget(_vline())

        # Group 2 – Insert
        self.btn_insert = self._make_action_menu_button("＋", "Chèn nội dung",
            [self.act_image, self.act_table, self.act_codeblock])
        tb.addWidget(self.btn_insert)
        tb.addWidget(_vline())

        # Group 4 – Tools
        self.btn_tools = self._make_action_menu_button("☰", "Công cụ soạn thảo",
            [self.act_comment, self.act_find])
        tb.addWidget(self.btn_tools)
        tb.addWidget(_vline())

        # Spacer đẩy view/settings sang phải
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        # Right side – View toggles
        self.btn_view = self._make_action_menu_button("☷", "Tùy chọn hiển thị",
            [self.act_toggle_palette, self.act_toggle_preview, self.act_zen])
        tb.addWidget(self.btn_view)
        tb.addWidget(_vline())

        # Far right – Settings/About
        tb.addAction(self.act_settings)
        tb.addAction(self.act_about)

        self.addToolBar(tb)
        self.toolbar = tb

    def _configure_preview_export_menu(self):
        self.btn_export = self.preview.btn_export
        export_menu = QMenu(self.btn_export)
        export_menu.setStyleSheet(
            "QMenu{background:#ffffff;color:#0f172a;border:1px solid #cbd5e1;padding:4px;}"
            "QMenu::item{padding:8px 18px;border-radius:5px;margin:1px;}"
            "QMenu::item:selected{background:#2563eb;color:#ffffff;}")
        act_pdf = QAction("📕   PDF (.pdf)", self)
        act_pdf.setShortcut("Ctrl+Shift+E")
        act_pdf.triggered.connect(self._export_pdf)
        act_html = QAction("🌐   HTML (.html)", self)
        act_html.triggered.connect(self._export_html)
        act_tex = QAction("📜   LaTeX (.tex)", self)
        act_tex.triggered.connect(self._export_latex)
        act_docx = QAction("📝   Word (.docx)", self)
        act_docx.triggered.connect(self._export_docx)
        act_open_last = QAction("📂   Mở tệp vừa xuất", self)
        act_open_last.triggered.connect(self._open_last_export)
        for action in (act_pdf, act_html, act_tex, act_docx):
            export_menu.addAction(action)
        export_menu.addSeparator()
        export_menu.addAction(act_open_last)
        self.btn_export.setMenu(export_menu)

    def _make_dropdown_button(self, text, tooltip, items):
        btn = QToolButton()
        btn.setText(text)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn.setToolTip(tooltip)
        btn.setStyleSheet(
            "QToolButton{padding:6px 10px;border-radius:8px;color:#334155;font-size:13px;font-weight:600;}"
            "QToolButton:hover{background:#eff6ff;color:#1d4ed8;}"
            "QToolButton::menu-indicator{image:none;}")
        menu = QMenu(btn)
        menu.setStyleSheet(
            "QMenu{background:#ffffff;color:#0f172a;border:1px solid #cbd5e1;padding:4px;}"
            "QMenu::item{padding:7px 16px;border-radius:5px;margin:1px;}"
            "QMenu::item:selected{background:#2563eb;color:#ffffff;}")
        for label, handler in items:
            act = QAction(label, self)
            act.triggered.connect(handler)
            menu.addAction(act)
        btn.setMenu(menu)
        return btn

    def _make_command_button(self, text, tooltip, action):
        btn = QToolButton()
        btn.setText(text)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        btn.setToolTip(tooltip)
        btn.clicked.connect(action.trigger)
        btn.setStyleSheet(
            "QToolButton{padding:6px 12px;border-radius:8px;color:#334155;"
            "font-weight:600;font-size:13px;}"
            "QToolButton:hover{background:#eff6ff;color:#1d4ed8;}"
            "QToolButton:pressed{background:#bfdbfe;}")
        return btn

    def _make_action_menu_button(self, text, tooltip, actions):
        btn = QToolButton()
        btn.setText(text)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn.setToolTip(tooltip)
        btn.setStyleSheet(
            "QToolButton{padding:6px 10px;border-radius:8px;color:#334155;font-size:13px;font-weight:600;}"
            "QToolButton:hover{background:#eff6ff;color:#1d4ed8;}"
            "QToolButton::menu-indicator{image:none;}")
        menu = QMenu(btn)
        menu.setStyleSheet(
            "QMenu{background:#ffffff;color:#0f172a;border:1px solid #cbd5e1;padding:4px;}"
            "QMenu::item{padding:7px 16px;border-radius:5px;margin:1px;}"
            "QMenu::item:selected{background:#2563eb;color:#ffffff;}"
            "QMenu::separator{height:1px;background:#e5e7eb;margin:4px 6px;}")
        for action in actions:
            if action is None:
                menu.addSeparator()
            else:
                menu.addAction(action)
        btn.setMenu(menu)
        return btn

    def _install_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+W"), self,
                  activated=lambda: self._close_tab(self.tabs.currentIndex()))
        QShortcut(QKeySequence("Escape"), self, activated=self._dismiss_find)
        QShortcut(QKeySequence("Ctrl+Tab"), self, activated=self._next_tab)
        QShortcut(QKeySequence("Ctrl+Shift+Tab"), self, activated=self._prev_tab)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=lambda: self._line_prefix("- "))

    def _refresh_recent_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu{background:#ffffff;color:#0f172a;border:1px solid #cbd5e1;padding:4px;}"
            "QMenu::item{padding:6px 14px;border-radius:5px;margin:1px;}"
            "QMenu::item:selected{background:#2563eb;color:#ffffff;}"
            "QMenu::separator{height:1px;background:#e5e7eb;margin:4px 6px;}")
        open_action = menu.addAction("📂   Mở...")
        open_action.triggered.connect(self._open_file)
        menu.addSeparator()
        self.recent_files = load_recent()
        if not self.recent_files:
            act = menu.addAction("(Chưa có tệp gần đây)")
            act.setEnabled(False)
        else:
            for p in self.recent_files[:15]:
                act = menu.addAction(os.path.basename(p))
                act.setToolTip(p)
                act.triggered.connect(lambda checked=False, pp=p: self._open_specific_file(pp))
            menu.addSeparator()
            clear = menu.addAction("Xoá danh sách")
            clear.triggered.connect(self._clear_recent)
        self.btn_open.setMenu(menu)

    def _clear_recent(self):
        from .config import RECENT_FILES_FILE
        save_json(RECENT_FILES_FILE, [])
        self._refresh_recent_menu()

    # =====================================================================
    # Tabs / files
    # =====================================================================
    def _new_file(self):
        self._add_tab("Untitled.md", MARKDOWN_DEFAULT_DOC, "")

    def _open_file(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Mở file Markdown", "",
            "Markdown (*.md *.markdown *.mdown *.txt);;Tất cả (*)")
        for p in paths:
            self._open_specific_file(p)

    def _open_specific_file(self, path):
        path = os.path.abspath(path)
        if not os.path.exists(path):
            QMessageBox.warning(self, "Không tìm thấy file", path)
            return
        for i in range(self.tabs.count()):
            ed = self.tabs.widget(i)
            if ed.file_path and os.path.normcase(ed.file_path) == os.path.normcase(path):
                self.tabs.setCurrentIndex(i)
                return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as exc:
            QMessageBox.critical(self, "Không đọc được file", str(exc))
            return

        self._add_tab(os.path.basename(path), content, path)
        push_recent(path)
        self._refresh_recent_menu()

    def _add_tab(self, title, content, path):
        editor = CodeEditor(file_path=path, main_window=self)
        editor.setPlainText(content)
        editor.textChanged.connect(self._on_editor_changed)
        editor.cursorPositionChanged.connect(self._update_status_pos)
        idx = self.tabs.addTab(editor, title)
        self.tabs.setCurrentIndex(idx)
        self._update_status_pos()
        self._do_render_preview()

    def _close_tab(self, index):
        if index < 0:
            return
        editor = self.tabs.widget(index)
        if editor and editor.document().isModified() and editor.toPlainText().strip():
            res = QMessageBox.question(
                self, "Chưa lưu",
                f"File '{self.tabs.tabText(index)}' chưa được lưu. Lưu trước khi đóng?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No |
                QMessageBox.StandardButton.Cancel)
            if res == QMessageBox.StandardButton.Cancel:
                return
            if res == QMessageBox.StandardButton.Yes:
                self.tabs.setCurrentIndex(index)
                if not self._save_current():
                    return
        self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self._new_file()

    def _on_tab_changed(self, index):
        if index < 0:
            return
        self._update_status_pos()
        self._do_render_preview()

    def _next_tab(self):
        if self.tabs.count():
            self.tabs.setCurrentIndex((self.tabs.currentIndex() + 1) % self.tabs.count())

    def _prev_tab(self):
        if self.tabs.count():
            self.tabs.setCurrentIndex((self.tabs.currentIndex() - 1) % self.tabs.count())

    def _update_status_pos(self):
        editor = self._cur_editor()
        if not editor:
            return
        cur = editor.textCursor()
        line = cur.blockNumber() + 1
        col = cur.positionInBlock() + 1
        self.status_pos.setText(f"Dòng {line}, Cột {col}")
        text = editor.toPlainText()
        words = len([w for w in text.split() if w])
        chars = len(text)
        self.status_words.setText(f"{words} từ · {chars} ký tự")

    def _cur_editor(self) -> CodeEditor:
        return self.tabs.currentWidget()

    def _save_current(self):
        editor = self._cur_editor()
        if not editor:
            return False
        if not editor.file_path:
            return self._save_as_current()
        try:
            with open(editor.file_path, "w", encoding="utf-8") as f:
                f.write(editor.toPlainText())
            editor.document().setModified(False)
            self._update_tab_title(self.tabs.currentIndex())
            self.status_msg.setText(f"Đã lưu: {editor.file_path}")
            push_recent(editor.file_path)
            self._refresh_recent_menu()
            return True
        except Exception as exc:
            QMessageBox.critical(self, "Lỗi lưu", str(exc))
            return False

    def _save_as_current(self):
        editor = self._cur_editor()
        if not editor:
            return False
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu thành .md", editor.file_path or "document.md",
            "Markdown (*.md);;Tất cả (*)")
        if not path:
            return False
        editor.file_path = path
        if not self._save_current():
            return False
        self._update_tab_title(self.tabs.currentIndex())
        return True

    def _update_tab_title(self, index):
        editor = self.tabs.widget(index)
        if not editor:
            return
        name = os.path.basename(editor.file_path) if editor.file_path else "Untitled.md"
        if editor.document().isModified():
            name = "● " + name
        self.tabs.setTabText(index, name)

    def _on_editor_changed(self):
        idx = self.tabs.currentIndex()
        if idx >= 0:
            self._update_tab_title(idx)
        self._update_status_pos()
        self.preview_timer.start(450)

    # =====================================================================
    # Export
    # =====================================================================
    def _export_html(self):
        editor = self._cur_editor()
        if not editor:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Xuất HTML",
            (editor.file_path or "document").rsplit(".", 1)[0] + ".html",
            "HTML (*.html)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(markdown_to_html(editor.toPlainText()))
            self._remember_export(path)
            self.status_msg.setText(f"✅ Đã xuất HTML: {path}")
            QMessageBox.information(self, "Đã xuất HTML", path)
        except Exception as exc:
            QMessageBox.critical(self, "Lỗi xuất HTML", str(exc))

    def _export_latex(self):
        editor = self._cur_editor()
        if not editor:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Xuất LaTeX",
            (editor.file_path or "document").rsplit(".", 1)[0] + ".tex",
            "LaTeX (*.tex)")
        if not path:
            return
        try:
            # Lấy tiêu đề từ # heading đầu tiên nếu có
            title = "Tài liệu Markdown"
            for line in editor.toPlainText().split("\n"):
                m = line.strip()
                if m.startswith("# "):
                    title = m[2:].strip()
                    break
            with open(path, "w", encoding="utf-8") as f:
                f.write(markdown_to_latex(editor.toPlainText(), title=title))
            self._remember_export(path)
            self.status_msg.setText(f"✅ Đã xuất LaTeX: {path}")
            QMessageBox.information(self, "Đã xuất LaTeX", path)
        except Exception as exc:
            QMessageBox.critical(self, "Lỗi xuất LaTeX", str(exc))

    def _export_docx(self):
        editor = self._cur_editor()
        if not editor:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Xuất Word",
            (editor.file_path or "document").rsplit(".", 1)[0] + ".docx",
            "Word (*.docx)")
        if not path:
            return
        try:
            markdown_to_docx(editor.toPlainText(), path)
            self._remember_export(path)
            self.status_msg.setText(f"✅ Đã xuất Word: {path}")
            QMessageBox.information(self, "Đã xuất Word", path)
        except RuntimeError as exc:
            QMessageBox.warning(self, "Thiếu thư viện", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Lỗi xuất Word", str(exc))

    def _export_pdf(self):
        """In bản preview hiện tại (đã render MathJax + TikZ) ra PDF."""
        editor = self._cur_editor()
        if not editor:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Xuất PDF",
            (editor.file_path or "document").rsplit(".", 1)[0] + ".pdf",
            "PDF (*.pdf)")
        if not path:
            return

        # Đảm bảo preview đang mở & vừa render
        if not self.preview.isVisible():
            self.act_toggle_preview.setChecked(True)
        self.preview.render(editor.toPlainText(),
                            base_url=os.path.dirname(editor.file_path) if editor.file_path else "")

        self.status_msg.setText("⌛ Đang chờ MathJax/TikZ render rồi in PDF...")

        # Đợi 1.6s cho MathJax + TikZJax xử lý xong
        QTimer.singleShot(1600, lambda: self._print_pdf_now(path))

    def _print_pdf_now(self, path):
        page = self.preview.web.page()
        # Đảm bảo chỉ kết nối một lần
        try:
            page.pdfPrintingFinished.disconnect(self._on_pdf_done)
        except Exception:
            pass
        page.pdfPrintingFinished.connect(self._on_pdf_done)
        page.printToPdf(path)

    def _on_pdf_done(self, file_path, success):
        try:
            self.preview.web.page().pdfPrintingFinished.disconnect(self._on_pdf_done)
        except Exception:
            pass
        if success:
            self._remember_export(file_path)
            self.status_msg.setText(f"✅ Đã xuất PDF: {file_path}")
            QMessageBox.information(self, "Đã xuất PDF", file_path)
        else:
            self.status_msg.setText("❌ Xuất PDF thất bại.")
            QMessageBox.critical(self, "Lỗi xuất PDF",
                                 "Không thể tạo PDF từ preview.\nKiểm tra rằng preview đang hiển thị đúng.")

    def _remember_export(self, path):
        self.last_export_path = os.path.abspath(path)

    def _open_last_export(self):
        if not self.last_export_path:
            QMessageBox.information(self, "Chưa có tệp xuất", "Chưa có tệp nào được xuất trong phiên này.")
            return
        if not os.path.exists(self.last_export_path):
            QMessageBox.warning(self, "Không tìm thấy tệp", self.last_export_path)
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.last_export_path))

    # =====================================================================
    # Editing helpers
    # =====================================================================
    def _wrap_selection(self, kind):
        editor = self._cur_editor()
        if not editor:
            return
        cursor = editor.textCursor()
        sel = cursor.selectedText() or "%|"
        wrap = {"bold": "**", "italic": "*", "strike": "~~", "code": "`"}[kind]
        snippet = f"{wrap}{sel}{wrap}"
        if "%|" in snippet:
            editor.apply_snippet(snippet)
        else:
            cursor.insertText(snippet)

    def _line_prefix(self, prefix):
        editor = self._cur_editor()
        if not editor:
            return
        cursor = editor.textCursor()
        if not cursor.hasSelection():
            block = cursor.block()
            txt = block.text()
            c = QTextCursor(block)
            c.setPosition(block.position())
            if not txt.startswith(prefix):
                c.insertText(prefix)
            return
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        cursor.setPosition(start)
        start_block = cursor.blockNumber()
        cursor.setPosition(end)
        end_block = cursor.blockNumber()
        cursor.beginEditBlock()
        for ln in range(start_block, end_block + 1):
            block = editor.document().findBlockByNumber(ln)
            c = QTextCursor(block)
            txt = block.text()
            if not txt.startswith(prefix):
                c.setPosition(block.position())
                c.insertText(prefix)
        cursor.endEditBlock()

    def _inline_math(self):
        editor = self._cur_editor()
        if editor:
            editor.insert_inline_math()

    def _block_math(self):
        editor = self._cur_editor()
        if editor:
            editor.insert_display_math()

    def _insert_table(self):
        editor = self._cur_editor()
        if not editor:
            return
        editor.apply_snippet(
            "| %| | Cột 2 | Cột 3 |\n|------|------|------|\n|      |      |      |\n")

    def _insert_image(self):
        editor = self._cur_editor()
        if not editor:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Chọn ảnh", "",
                                              "Hình ảnh (*.png *.jpg *.jpeg *.svg *.gif *.webp)")
        if not path:
            return
        if editor.file_path:
            try:
                path = os.path.relpath(path, os.path.dirname(editor.file_path))
            except ValueError:
                pass
        path = path.replace("\\", "/")
        editor.apply_snippet(f"![%|]({path})")

    def _insert_link(self):
        editor = self._cur_editor()
        if not editor:
            return
        url, ok = QInputDialog.getText(self, "Chèn link", "URL:")
        if not ok:
            return
        editor.apply_snippet(f"[%|]({url})")

    def _insert_codeblock(self):
        editor = self._cur_editor()
        if not editor:
            return
        lang, ok = QInputDialog.getText(self, "Code block",
                                         "Ngôn ngữ (vd python, javascript, tikz):")
        if not ok:
            return
        editor.apply_snippet(f"```{lang}\n%|\n```")

    def _toggle_comment_current(self):
        editor = self._cur_editor()
        if editor:
            editor.toggle_comment()

    def _insert_snippet_to_current(self, snippet):
        editor = self._cur_editor()
        if not editor:
            return
        cursor = editor.textCursor()
        sel = cursor.selectedText()
        if "%|" in snippet:
            if sel:
                cursor.insertText(snippet.replace("%|", sel))
            else:
                editor.apply_snippet(snippet)
        else:
            cursor.insertText(snippet)
        editor.setFocus()

    # =====================================================================
    # Preview render
    # =====================================================================
    def _do_render_preview(self):
        editor = self._cur_editor()
        if not editor:
            return
        base = os.path.dirname(editor.file_path) if editor.file_path else ""
        self.preview.render(editor.toPlainText(), base_url=base, mode="full")

    def _do_render_current_block(self):
        editor = self._cur_editor()
        if not editor:
            return
        block_text, start_line = self._current_markdown_block(editor)
        base = os.path.dirname(editor.file_path) if editor.file_path else ""
        self.preview.render(block_text, base_url=base, mode="fragment", start_line=start_line)

    def _compile_preview(self):
        self.preview.set_compiling(True)
        self.status_msg.setText("Đang compile preview...")
        self._do_render_preview()

        def finish():
            self.preview.set_compiling(False)
            self.status_msg.setText("Đã compile preview.")

        QTimer.singleShot(1400, finish)

    def _current_markdown_block(self, editor):
        lines = editor.toPlainText().split("\n")
        if not lines:
            return "", 1
        line = max(0, min(editor.textCursor().blockNumber(), len(lines) - 1))

        def stripped(idx):
            return lines[idx].strip()

        def is_list(text):
            import re
            return bool(re.match(r'^([-*+]\s+(\[[ xX]\]\s+)?|\d+\.\s+)', text))

        def is_hr(text):
            import re
            return bool(re.match(r'^(?:---+|\*\*\*+|___+)\s*$', text))

        def is_heading(text):
            import re
            return bool(re.match(r'^(#{1,6})\s+', text))

        def is_table_line(text):
            return text.startswith("|")

        def block_join(start, end):
            return "\n".join(lines[start:end + 1]), start + 1

        # Code/TikZ fence: nếu con trỏ nằm trong fence thì render cả block đó.
        fence_start = None
        for i in range(line, -1, -1):
            if stripped(i).startswith("```"):
                fence_start = i
                break
        if fence_start is not None:
            fence_count = sum(1 for i in range(0, fence_start + 1) if stripped(i).startswith("```"))
            if fence_count % 2 == 1:
                end = fence_start
                while end + 1 < len(lines) and not stripped(end + 1).startswith("```"):
                    end += 1
                if end + 1 < len(lines):
                    end += 1
                return block_join(fence_start, end)

        # Display math $$...$$.
        math_start = None
        for i in range(line, -1, -1):
            if stripped(i).startswith("$$"):
                math_start = i
                break
        if math_start is not None:
            math_count = sum(1 for i in range(0, math_start + 1) if stripped(i).startswith("$$"))
            if math_count % 2 == 1:
                end = math_start
                while end + 1 < len(lines) and not stripped(end + 1).endswith("$$"):
                    end += 1
                if end + 1 < len(lines):
                    end += 1
                return block_join(math_start, end)

        cur = stripped(line)
        if is_table_line(cur):
            start = line
            while start > 0 and is_table_line(stripped(start - 1)):
                start -= 1
            end = line
            while end + 1 < len(lines) and is_table_line(stripped(end + 1)):
                end += 1
            return block_join(start, end)

        if is_list(cur):
            start = line
            while start > 0 and is_list(stripped(start - 1)):
                start -= 1
            end = line
            while end + 1 < len(lines) and is_list(stripped(end + 1)):
                end += 1
            return block_join(start, end)

        if cur.startswith("> "):
            start = line
            while start > 0 and stripped(start - 1).startswith("> "):
                start -= 1
            end = line
            while end + 1 < len(lines) and stripped(end + 1).startswith("> "):
                end += 1
            return block_join(start, end)

        if is_heading(cur) or is_hr(cur) or not cur:
            return block_join(line, line)

        start = line
        while start > 0:
            prev = stripped(start - 1)
            if (not prev or prev.startswith("```") or prev.startswith("$$") or is_heading(prev)
                    or is_list(prev) or prev.startswith("> ") or is_table_line(prev) or is_hr(prev)):
                break
            start -= 1
        end = line
        while end + 1 < len(lines):
            nxt = stripped(end + 1)
            if (not nxt or nxt.startswith("```") or nxt.startswith("$$") or is_heading(nxt)
                    or is_list(nxt) or nxt.startswith("> ") or is_table_line(nxt) or is_hr(nxt)):
                break
            end += 1
        return block_join(start, end)

    def _sync_preview_to_editor_line(self, line):
        if not self.preview.isVisible():
            self.act_toggle_preview.setChecked(True)
        self.preview.scroll_to_source_line(line)

    def _sync_editor_to_preview_line(self, line):
        editor = self._cur_editor()
        if not editor:
            return
        editor.goto_line(line)
        self.status_msg.setText(f"Đã đồng bộ tới dòng {line}.")

    # =====================================================================
    # Find / Replace
    # =====================================================================
    def _show_find(self):
        self.find_bar.setVisible(True)
        editor = self._cur_editor()
        if editor:
            sel = editor.textCursor().selectedText()
            if sel:
                self.find_input.setText(sel)
        self.find_input.setFocus()
        self.find_input.selectAll()

    def _dismiss_find(self):
        self.find_bar.setVisible(False)
        editor = self._cur_editor()
        if editor:
            editor.setFocus()

    def _find_next(self):
        text = self.find_input.text()
        editor = self._cur_editor()
        if not editor or not text:
            return
        if not editor.find(text):
            cur = editor.textCursor()
            cur.movePosition(QTextCursor.MoveOperation.Start)
            editor.setTextCursor(cur)
            editor.find(text)

    def _find_prev(self):
        text = self.find_input.text()
        editor = self._cur_editor()
        if not editor or not text:
            return
        opt = QTextDocument.FindFlag.FindBackward
        if not editor.find(text, opt):
            cur = editor.textCursor()
            cur.movePosition(QTextCursor.MoveOperation.End)
            editor.setTextCursor(cur)
            editor.find(text, opt)

    def _replace_one(self):
        editor = self._cur_editor()
        if not editor:
            return
        cur = editor.textCursor()
        if cur.hasSelection() and cur.selectedText() == self.find_input.text():
            cur.insertText(self.replace_input.text())
        self._find_next()

    def _replace_all(self):
        editor = self._cur_editor()
        find = self.find_input.text()
        repl = self.replace_input.text()
        if not editor or not find:
            return
        cur = editor.textCursor()
        cur.beginEditBlock()
        cur.movePosition(QTextCursor.MoveOperation.Start)
        editor.setTextCursor(cur)
        cnt = 0
        while editor.find(find):
            editor.textCursor().insertText(repl)
            cnt += 1
        cur.endEditBlock()
        self.status_msg.setText(f"Đã thay {cnt} chỗ.")

    # =====================================================================
    # AI
    # =====================================================================
    def trigger_ai_assistant(self):
        editor = self._cur_editor()
        if not editor:
            return
        cursor = editor.textCursor()
        sel_text = cursor.selectedText().replace('\u2029', '\n')
        dlg = AIQuickDialog(self, selected_text=sel_text, document_text=editor.toPlainText())
        if dlg.exec() and dlg.action_taken == "dock":
            self._show_ai_panel(dlg.take_chat_widget())
            return
        if dlg.result_text:
            editor.setTextCursor(cursor)
            self._apply_ai_result(dlg.action_taken or "insert", dlg.result_text)

    def _ai_context(self):
        editor = self._cur_editor()
        if not editor:
            return "", ""
        cursor = editor.textCursor()
        return cursor.selectedText().replace('\u2029', '\n'), editor.toPlainText()

    def _show_ai_panel(self, widget=None):
        if self.ai_chat_widget is not None:
            self.ai_chat_widget.setParent(None)
            self.ai_chat_widget.deleteLater()
            self.ai_chat_widget = None
        if widget is None:
            selected_text, document_text = self._ai_context()
            widget = AIChatWidget(self, selected_text=selected_text,
                                  document_text=document_text, compact=True,
                                  context_provider=self._ai_context)
        widget.context_provider = self._ai_context
        widget.set_compact(True)
        widget.apply_requested.connect(self._apply_ai_result)
        widget.closed_requested.connect(self._hide_ai_panel)
        self.ai_chat_widget = widget
        self.ai_panel_layout.addWidget(widget)
        self.ai_panel_host.setVisible(True)
        self.editor_splitter.setSizes([620, 260])
        widget.input_edit.setFocus()

    def _hide_ai_panel(self):
        self.ai_panel_host.setVisible(False)

    def _apply_ai_result(self, action, text):
        editor = self._cur_editor()
        if not editor or not text:
            return
        cursor = editor.textCursor()
        if action == "replace" and cursor.hasSelection():
            cursor.insertText(text)
        else:
            cursor.insertText(text)
        editor.setFocus()

    # =====================================================================
    # Misc
    # =====================================================================
    def _toggle_preview(self, on):
        self.preview.setVisible(on)
        if on:
            sizes = self.main_splitter.sizes()
            if sizes[2] < 200:
                self.main_splitter.setSizes([sizes[0], sizes[1], 500])
            self._do_render_preview()

    def _toggle_palette(self, on):
        self.symbol_palette.setVisible(on)

    def _toggle_zen(self, on):
        if on:
            self.toolbar.setVisible(False)
            self.symbol_palette.setVisible(False)
            self.preview.setVisible(False)
            self.statusBar().setVisible(False)
            self.act_toggle_palette.setChecked(False)
            self.act_toggle_preview.setChecked(False)
        else:
            self.toolbar.setVisible(True)
            self.symbol_palette.setVisible(True)
            self.preview.setVisible(True)
            self.statusBar().setVisible(True)
            self.act_toggle_palette.setChecked(True)
            self.act_toggle_preview.setChecked(True)

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self.editor_config = load_editor_config()
            font = QFont(self.editor_config.get("font_family", "Consolas"),
                         self.editor_config.get("font_size", 13))
            wrap_mode = (QPlainTextEdit.LineWrapMode.WidgetWidth
                         if self.editor_config.get("wrap_lines", True)
                         else QPlainTextEdit.LineWrapMode.NoWrap)
            for i in range(self.tabs.count()):
                ed = self.tabs.widget(i)
                ed.editor_config = self.editor_config
                ed.tab_spaces = self.editor_config.get("tab_spaces", 2)
                ed.auto_pair = self.editor_config.get("auto_pair", True)
                ed.update_font(font)
                ed.setLineWrapMode(wrap_mode)
            if self.editor_config.get("auto_save", False):
                self.auto_save_timer.start()
            else:
                self.auto_save_timer.stop()
            self.status_msg.setText("Đã cập nhật cấu hình.")

    def _open_about(self):
        AboutDialog(self).exec()

    def _auto_save(self):
        for i in range(self.tabs.count()):
            ed = self.tabs.widget(i)
            if ed.file_path and ed.document().isModified():
                try:
                    with open(ed.file_path, "w", encoding="utf-8") as f:
                        f.write(ed.toPlainText())
                    ed.document().setModified(False)
                    self._update_tab_title(i)
                except Exception:
                    pass

    # =====================================================================
    # Session
    # =====================================================================
    def _load_session_or_default(self):
        try:
            if os.path.exists(SESSION_FILE):
                with open(SESSION_FILE, "r", encoding="utf-8") as f:
                    import json
                    data = json.load(f)
                opened = 0
                for p in data.get("files", []):
                    if os.path.exists(p):
                        self._open_specific_file(p)
                        opened += 1
                if opened:
                    return
        except Exception:
            pass
        self._new_file()

    def _save_session(self):
        files = []
        for i in range(self.tabs.count()):
            ed = self.tabs.widget(i)
            if ed.file_path:
                files.append(ed.file_path)
        save_json(SESSION_FILE, {"files": files})

    def closeEvent(self, event):
        for i in range(self.tabs.count()):
            ed = self.tabs.widget(i)
            if ed.document().isModified() and ed.toPlainText().strip():
                self.tabs.setCurrentIndex(i)
                res = QMessageBox.question(
                    self, "Chưa lưu",
                    f"File '{self.tabs.tabText(i)}' có thay đổi. Lưu trước khi thoát?",
                    QMessageBox.StandardButton.Yes |
                    QMessageBox.StandardButton.No |
                    QMessageBox.StandardButton.Cancel)
                if res == QMessageBox.StandardButton.Cancel:
                    event.ignore()
                    return
                if res == QMessageBox.StandardButton.Yes:
                    if not self._save_current():
                        event.ignore()
                        return
        self._save_session()
        event.accept()

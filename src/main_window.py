"""Cửa sổ chính eMeX – Markdown only, một toolbar gọn gàng."""
from datetime import datetime
import mimetypes
import os
import shutil
import sys

from PyQt6.QtCore import QEvent, Qt, QRectF, QSize, QThread, QTimer, QUrl
from PyQt6.QtGui import (QAction, QActionGroup, QColor, QDesktopServices,
                          QFont, QIcon, QKeySequence, QLinearGradient, QPainter,
                          QPen, QImage, QPixmap, QShortcut, QTextCursor,
                          QTextDocument)
from PyQt6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout,
                              QInputDialog, QLabel, QLineEdit, QMainWindow,
                              QMenu, QMessageBox, QPlainTextEdit, QPushButton,
                              QSizePolicy, QSplitter, QStatusBar, QTabWidget,
                              QTabBar, QToolBar, QToolButton, QVBoxLayout, QWidget,
                              QFrame)

from .ai_assistant import AIChatWidget, AIQuickDialog
from .config import (APP_ICON_FILE, APP_NAME, APP_VERSION, CONFIG_DIR,
                     MARKDOWN_PAGE_TEMPLATES, SESSION_FILE, load_editor_config, load_recent,
                     load_user_page_templates, push_recent, save_editor_config,
                     save_json, save_user_page_templates)
from .dialogs import AboutDialog, SettingsDialog
from .editor import CodeEditor
from .exporters import markdown_to_docx, markdown_to_html, markdown_to_latex
from .i18n import t
from .preview import PreviewPane
from .symbol_palette import SymbolPalette
from .workers import Toast, run_async


IMAGE_FILE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}


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
        self.user_page_templates = load_user_page_templates()

        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        if os.path.exists(APP_ICON_FILE):
            self.setWindowIcon(QIcon(APP_ICON_FILE))
        self.resize(1400, 880)
        self.last_export_path = ""

        # Cho phép kéo-thả tệp .md trực tiếp vào cửa sổ.
        self.setAcceptDrops(True)

        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        # Auto vá block đang gõ và chỉ typeset MathJax cho block đó.
        # TikZJax chỉ chạy khi Ctrl+Enter compile lại toàn bộ preview.
        self.preview_timer.timeout.connect(self._do_auto_preview_update)

        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.setInterval(60_000)
        self.auto_save_timer.timeout.connect(self._auto_save)
        if self.editor_config.get("auto_save", False):
            self.auto_save_timer.start()

        # Stylesheet tổng
        _tb_pad = self.editor_config.get("toolbar_btn_padding", 6)
        self.setStyleSheet(f"""
            QMainWindow{{background:#f1f5f9;color:#0f172a;}}
            QWidget{{color:#0f172a;}}
            QToolBar{{background:#ffffff;border:0;border-bottom:1px solid #e5e7eb;
                spacing:1px;padding:{_tb_pad}px 10px;}}
            QToolBar QToolButton{{background:transparent;color:#334155;
                padding:{_tb_pad}px 9px;border-radius:8px;font-size:13px;margin:0 1px;}}
            QToolBar QToolButton:hover{{background:#eff6ff;color:#1d4ed8;}}
            QToolBar QToolButton:checked{{background:#dbeafe;color:#1d4ed8;}}
            QToolBar QToolButton:pressed{{background:#bfdbfe;}}
            QToolBar QToolButton::menu-indicator{{
                image:none;
                subcontrol-position: right center;
                subcontrol-origin: padding;
                width:10px;
            }}
            QToolBar QLabel{{color:#0f172a;background:transparent;padding:0 4px;}}
            QToolBar::separator{{background:#e2e8f0;width:1px;margin:6px 6px;}}
            QStatusBar{{background:#0f172a;color:#e2e8f0;}}
            QStatusBar QLabel{{color:#e2e8f0;background:transparent;padding:0 8px;}}
            QTabWidget::pane{{border:0;background:#ffffff;}}
            QSplitter::handle{{background:#e5e7eb;}}
            QSplitter::handle:hover{{background:#cbd5e1;}}
            QMessageBox{{background:#ffffff;color:#0f172a;}}
            QMenu{{background:#ffffff;color:#0f172a;border:1px solid #cbd5e1;padding:4px;}}
            QMenu::item{{padding:7px 16px;border-radius:5px;margin:1px 2px;}}
            QMenu::item:selected{{background:#2563eb;color:#ffffff;}}
            QMenu::separator{{height:1px;background:#e5e7eb;margin:4px 6px;}}
            QInputDialog{{background:#ffffff;color:#0f172a;}}
        """)

        self._build_ui()
        self._build_actions()
        self._build_toolbar()
        self._install_shortcuts()
        self._restore_ui_state()

        self.recent_files = load_recent()
        self._load_session_or_default()
        self._init_update_notification()
        QTimer.singleShot(1500, self._start_update_check)

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
        # Middle-click đóng tab + right-click hiện context menu (open folder…).
        self.tabs.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self._show_tab_context_menu)
        self.tabs.tabBar().installEventFilter(self)
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
                subcontrol-position: right;
                border-radius: 8px;
                margin: 4px 4px 4px 6px;
                padding: 2px;
            }
            QTabBar::close-button:hover{
                background:#fee2e2;
            }
            QTabBar::close-button:pressed{
                background:#fecaca;
            }
        """)

        self.symbol_palette = SymbolPalette(editor_config=self.editor_config)
        self.symbol_palette.snippet_clicked.connect(self._insert_snippet_to_current)

        self.preview = PreviewPane(self)
        self.preview.btn_compile.clicked.connect(self._compile_preview)
        self.preview.web.loadFinished.connect(lambda _ok: self.preview.set_compiling(False))
        self.preview.web.source_line_requested.connect(self._sync_editor_to_preview_line)

        self.ai_panel_host = QWidget()
        self.ai_panel_host.setVisible(False)
        self.ai_panel_layout = QVBoxLayout(self.ai_panel_host)
        self.ai_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.ai_panel_layout.setSpacing(0)
        self.ai_chat_widget = None

        self.left_splitter = QSplitter(Qt.Orientation.Vertical)
        self.left_splitter.addWidget(self.symbol_palette)
        self.left_splitter.addWidget(self.ai_panel_host)
        self.left_splitter.setSizes([720, 260])
        self.left_splitter.setStretchFactor(0, 1)
        self.left_splitter.setStretchFactor(1, 0)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.addWidget(self.left_splitter)
        self.main_splitter.addWidget(self.tabs)
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
        self.status_msg = QLabel(t("Sẵn sàng"))
        self.status_pos = QLabel(t("Dòng {line}, Cột {col}", line=1, col=1))
        self.status_words = QLabel(t("{words} từ · {chars} ký tự", words=0, chars=0))
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
        self.find_input.setPlaceholderText(t("Tìm..."))
        self.find_input.returnPressed.connect(self._find_next)

        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText(t("Thay bằng..."))

        btn_prev = QPushButton("◀")
        btn_next = QPushButton("▶")
        self.btn_find_replace = QPushButton(t("Thay"))
        self.btn_find_replace_all = QPushButton(t("Thay tất cả"))
        btn_close = QPushButton("✕")
        for b in (btn_prev, btn_next, btn_close):
            b.setFixedWidth(34)
        btn_prev.clicked.connect(self._find_prev)
        btn_next.clicked.connect(self._find_next)
        self.btn_find_replace.clicked.connect(self._replace_one)
        self.btn_find_replace_all.clicked.connect(self._replace_all)
        btn_close.clicked.connect(lambda: bar.setVisible(False))

        self.lbl_find = QLabel(t("Tìm:"))
        self.lbl_replace = QLabel(t("Thay:"))
        lay.addWidget(self.lbl_find)
        lay.addWidget(self.find_input, 2)
        lay.addWidget(btn_prev)
        lay.addWidget(btn_next)
        lay.addWidget(self.lbl_replace)
        lay.addWidget(self.replace_input, 2)
        lay.addWidget(self.btn_find_replace)
        lay.addWidget(self.btn_find_replace_all)
        lay.addStretch()
        lay.addWidget(btn_close)
        return bar

    # =====================================================================
    # Actions
    # =====================================================================
    def _build_actions(self):
        # ---- File ----
        self.act_new = QAction(emoji_icon("📄"), t("Trang trống (Ctrl+N)"), self)
        self.act_new.triggered.connect(self._new_file)

        self.act_open = QAction(emoji_icon("📂"), t("Mở (Ctrl+O)"), self)
        self.act_open.setShortcut("Ctrl+O")
        self.act_open.triggered.connect(self._open_file)

        self.act_save = QAction(emoji_icon("💾"), t("Lưu (Ctrl+S)"), self)
        self.act_save.setShortcut("Ctrl+S")
        self.act_save.triggered.connect(self._save_current)

        # Save As – KHÔNG xuất hiện trên toolbar nữa, chỉ giữ shortcut
        self.act_save_as = QAction(t("Lưu thành... (Ctrl+Shift+S)"), self)
        self.act_save_as.setShortcut("Ctrl+Shift+S")
        self.act_save_as.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.act_save_as.triggered.connect(self._save_as_current)
        self.addAction(self.act_save_as)

        # ---- Format ----
        self.act_bold = QAction(emoji_icon("𝐁"), t("In đậm (Ctrl+B)"), self)
        self.act_bold.setShortcut("Ctrl+B")
        self.act_bold.triggered.connect(lambda: self._wrap_selection("bold"))

        self.act_italic = QAction(emoji_icon("𝑰"), t("In nghiêng (Ctrl+I)"), self)
        self.act_italic.setShortcut("Ctrl+I")
        self.act_italic.triggered.connect(lambda: self._wrap_selection("italic"))

        self.act_strike = QAction(emoji_icon("S̶"), t("Gạch ngang"), self)
        self.act_strike.triggered.connect(lambda: self._wrap_selection("strike"))

        self.act_code = QAction(emoji_icon("⟨⟩"), t("Mã trong dòng"), self)
        self.act_code.triggered.connect(lambda: self._wrap_selection("code"))

        self.act_inline_math = QAction(emoji_icon("∑"), t("Toán trong dòng (Ctrl+M)"), self)
        self.act_inline_math.setShortcut("Ctrl+M")
        self.act_inline_math.triggered.connect(self._inline_math)

        self.act_block_math = QAction(emoji_icon("∫"), t("Toán khối (Ctrl+Shift+M)"), self)
        self.act_block_math.setShortcut("Ctrl+Shift+M")
        self.act_block_math.triggered.connect(self._block_math)

        # ---- Insert ----
        self.act_quote = QAction(emoji_icon("❝"), t("Trích dẫn"), self)
        self.act_quote.triggered.connect(lambda: self._line_prefix("> "))

        self.act_hr = QAction(emoji_icon("━"), t("Đường ngang"), self)
        self.act_hr.triggered.connect(
            lambda: self._cur_editor() and self._cur_editor().apply_snippet("\n---\n"))

        self.act_link = QAction(emoji_icon("🔗"), t("Chèn liên kết"), self)
        self.act_link.triggered.connect(self._insert_link)

        self.act_image = QAction(emoji_icon("🖼"), t("Chèn ảnh"), self)
        self.act_image.triggered.connect(self._insert_image)

        self.act_table = QAction(emoji_icon("▦"), t("Bảng (Ctrl+T)"), self)
        self.act_table.setShortcut("Ctrl+T")
        self.act_table.triggered.connect(self._insert_table)

        self.act_codeblock = QAction(emoji_icon("⌨"), t("Khối mã"), self)
        self.act_codeblock.triggered.connect(self._insert_codeblock)

        self.act_comment = QAction(emoji_icon("💬"), t("Bình luận HTML (Ctrl+/)"), self)
        self.act_comment.setShortcut("Ctrl+/")
        self.act_comment.triggered.connect(self._toggle_comment_current)

        # ---- Tools ----
        self.act_find = QAction(emoji_icon("🔍"), t("Tìm (Ctrl+F)"), self)
        self.act_find.setShortcut("Ctrl+F")
        self.act_find.triggered.connect(self._show_find)

        self.act_replace = QAction(t("Thay (Ctrl+H)"), self)
        self.act_replace.setShortcut("Ctrl+H")
        self.act_replace.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.act_replace.triggered.connect(self._show_find)
        self.addAction(self.act_replace)

        self.act_render = QAction(emoji_icon("▶"), t("Biên dịch xem trước (Ctrl+Enter)"), self)
        self.act_render.setShortcuts([QKeySequence("Ctrl+Return"), QKeySequence("Ctrl+Enter")])
        self.act_render.triggered.connect(self._compile_preview)

        self.act_ai = QAction(emoji_icon("🤖"), t("Trợ lý eMeX (Ctrl+G)"), self)
        self.act_ai.setShortcut("Ctrl+G")
        self.act_ai.triggered.connect(self.trigger_ai_assistant)

        # ---- View ----
        self.act_toggle_preview = QAction(emoji_icon("👁"), t("Bật/Tắt xem trước (Ctrl+P)"), self)
        self.act_toggle_preview.setShortcut("Ctrl+P")
        self.act_toggle_preview.setCheckable(True)
        self.act_toggle_preview.setChecked(True)
        self.act_toggle_preview.toggled.connect(self._toggle_preview)

        self.act_toggle_palette = QAction(emoji_icon("∑"), t("Bật/Tắt bảng ký hiệu"), self)
        self.act_toggle_palette.setCheckable(True)
        self.act_toggle_palette.setChecked(True)
        self.act_toggle_palette.toggled.connect(self._toggle_palette)

        self.act_zen = QAction(emoji_icon("🧘"), t("Chế độ tập trung (F11)"), self)
        self.act_zen.setShortcut("F11")
        self.act_zen.setCheckable(True)
        self.act_zen.toggled.connect(self._toggle_zen)

        # ---- Settings ----
        self.act_settings = QAction(emoji_icon("⚙"), t("Cài đặt"), self)
        self.act_settings.triggered.connect(self._open_settings)

        self.act_about = QAction(emoji_icon("ℹ"), t("Giới thiệu"), self)
        self.act_about.triggered.connect(self._open_about)

        # Các action nằm trong menu dropdown vẫn cần nhận shortcut khi menu đang đóng.
        for action in (self.act_new, self.act_open, self.act_save, self.act_bold, self.act_italic,
                       self.act_inline_math, self.act_block_math,
                       self.act_table, self.act_comment, self.act_find,
                       self.act_render, self.act_ai, self.act_toggle_preview,
                       self.act_zen):
            action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
            self.addAction(action)

    # =====================================================================
    # Toolbar layout
    # =====================================================================
    def _build_toolbar(self):
        self._configure_preview_export_menu()

        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setFloatable(False)
        icon_sz = self.editor_config.get("toolbar_icon_size", 22)
        tb.setIconSize(QSize(icon_sz, icon_sz))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

        pad = self.editor_config.get("toolbar_btn_padding", 6)
        self._toolbar_pad = pad

        # Group 1 – File
        self.btn_new = QToolButton()
        self.btn_new.setText("📄")
        self.btn_new.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.btn_new.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_new.setToolTip(t("Tạo trang Markdown mới từ trang trống hoặc mẫu"))
        self.btn_new.setStyleSheet(
            f"QToolButton{{padding:{pad}px 10px;border-radius:8px;color:#334155;font-size:13px;}}"
            "QToolButton:hover{background:#eff6ff;color:#1d4ed8;}"
            "QToolButton::menu-indicator{image:none;}")
        self._refresh_new_page_menu()
        tb.addWidget(self.btn_new)
        self.btn_open = QToolButton()
        self.btn_open.setText("📂")
        self.btn_open.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.btn_open.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_open.setToolTip(t("Mở tệp Markdown / tệp gần đây"))
        self.btn_open.setStyleSheet(
            f"QToolButton{{padding:{pad}px 10px;border-radius:8px;color:#334155;font-size:13px;}}"
            "QToolButton:hover{background:#eff6ff;color:#1d4ed8;}"
            "QToolButton::menu-indicator{image:none;}")
        self._refresh_recent_menu()
        tb.addWidget(self.btn_open)
        self.btn_save = self._make_command_button(
            "💾", t("Lưu tệp Markdown hiện tại (Ctrl+S)"), self.act_save)
        tb.addWidget(self.btn_save)

        tb.addWidget(_vline())

        # Group 2 – Insert
        self.btn_insert = self._make_action_menu_button("＋", t("Chèn nội dung"),
            [self.act_image, self.act_table, self.act_codeblock])
        tb.addWidget(self.btn_insert)
        tb.addWidget(_vline())

        # Group 4 – Tools
        self.btn_tools = self._make_action_menu_button("☰", t("Công cụ soạn thảo"),
            [self.act_comment, self.act_find])
        tb.addWidget(self.btn_tools)
        tb.addWidget(_vline())

        # Spacer đẩy view/settings sang phải
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        # Right side – View toggles
        self.btn_view = self._make_action_menu_button("☷", t("Tùy chọn hiển thị"),
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
        act_open_last = QAction("📂   " + t("Mở tệp vừa xuất"), self)
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
            f"QToolButton{{padding:{self._toolbar_pad}px 10px;border-radius:8px;color:#334155;font-size:13px;font-weight:600;}}"
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
            f"QToolButton{{padding:{self._toolbar_pad}px 12px;border-radius:8px;color:#334155;"
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
            f"QToolButton{{padding:{self._toolbar_pad}px 10px;border-radius:8px;color:#334155;font-size:13px;font-weight:600;}}"
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

    def _refresh_new_page_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu{background:#ffffff;color:#0f172a;border:1px solid #cbd5e1;padding:4px;}"
            "QMenu::item{padding:6px 14px;border-radius:5px;margin:1px;}"
            "QMenu::item:selected{background:#2563eb;color:#ffffff;}"
            "QMenu::separator{height:1px;background:#e5e7eb;margin:4px 6px;}")

        blank_action = menu.addAction("📄   " + t("Trang trống"))
        blank_action.triggered.connect(self._new_file)
        menu.addSeparator()

        for template in MARKDOWN_PAGE_TEMPLATES:
            template_name = t(template["name"])
            act = menu.addAction(f"🧩   {template_name}")
            act.setToolTip(t("Tạo trang mới từ mẫu {name}", name=template_name))
            act.triggered.connect(
                lambda checked=False, tpl=template: self._new_file_from_template(tpl))

        self.user_page_templates = load_user_page_templates()
        if self.user_page_templates:
            menu.addSeparator()
            heading = menu.addAction(t("Mẫu của bạn"))
            heading.setEnabled(False)
            for template in self.user_page_templates:
                act = menu.addAction(f"⭐   {template['name']}")
                act.setToolTip(t("Tạo trang mới từ mẫu của bạn: {name}", name=template["name"]))
                act.triggered.connect(
                    lambda checked=False, tpl=template: self._new_file_from_template(tpl))

        menu.addSeparator()
        add_template = menu.addAction("＋   " + t("Thêm mẫu từ trang hiện tại"))
        add_template.triggered.connect(self._add_user_page_template)
        self.btn_new.setMenu(menu)

    def _install_shortcuts(self):
        self._shortcuts = []

        def add_shortcut(sequence, handler):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(handler)
            shortcut.activatedAmbiguously.connect(handler)
            self._shortcuts.append(shortcut)

        add_shortcut("Ctrl+W", self._close_current_tab)
        add_shortcut("Ctrl+F4", self._close_current_tab)
        add_shortcut("Ctrl+N", self._new_file)
        add_shortcut("Ctrl+Return", self._compile_preview)
        add_shortcut("Ctrl+Enter", self._compile_preview)
        add_shortcut("Alt+F4", self.close)
        add_shortcut("Ctrl+Shift+W", self.close)
        add_shortcut("Escape", self._dismiss_find)
        add_shortcut("Ctrl+Tab", self._next_tab)
        add_shortcut("Ctrl+Shift+Tab", self._prev_tab)
        add_shortcut("Ctrl+L", lambda: self._line_prefix("- "))

    def _close_current_tab(self):
        self._close_tab(self.tabs.currentIndex())

    def _refresh_recent_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu{background:#ffffff;color:#0f172a;border:1px solid #cbd5e1;padding:4px;}"
            "QMenu::item{padding:6px 14px;border-radius:5px;margin:1px;}"
            "QMenu::item:selected{background:#2563eb;color:#ffffff;}"
            "QMenu::separator{height:1px;background:#e5e7eb;margin:4px 6px;}")
        open_action = menu.addAction("📂   " + t("Mở..."))
        open_action.triggered.connect(self._open_file)
        menu.addSeparator()
        self.recent_files = load_recent()
        if not self.recent_files:
            act = menu.addAction(t("(Chưa có tệp gần đây)"))
            act.setEnabled(False)
        else:
            for p in self.recent_files[:15]:
                act = menu.addAction(os.path.basename(p))
                act.setToolTip(p)
                act.triggered.connect(lambda checked=False, pp=p: self._open_specific_file(pp))
            menu.addSeparator()
            clear = menu.addAction(t("Xoá danh sách"))
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
        self._add_tab(t("Chưa đặt tên.md"), "", "")

    def _new_file_from_template(self, template):
        title = template.get("filename") or self._template_tab_title(template.get("name", t("Chưa đặt tên")))
        content = template.get("content", "")
        self._add_tab(title, content, "")
        editor = self._cur_editor()
        if editor and content.strip():
            editor.document().setModified(True)
            self._update_tab_title(self.tabs.currentIndex())
        self.status_msg.setText(t("Đã tạo trang mới từ mẫu: {name}", name=t(template.get("name", title))))

    def _add_user_page_template(self):
        editor = self._cur_editor()
        if not editor:
            return
        content = editor.toPlainText()
        if not content.strip():
            QMessageBox.information(
                self, t("Trang trống"), t("Trang hiện tại đang trống, chưa có nội dung để lưu thành mẫu."))
            return

        default_name = self._suggest_template_name(content, editor)
        name, ok = QInputDialog.getText(
            self, t("Thêm mẫu"), t("Tên mẫu:"), QLineEdit.EchoMode.Normal, default_name)
        if not ok:
            return
        name = name.strip()
        if not name:
            QMessageBox.warning(self, t("Thiếu tên mẫu"), t("Vui lòng nhập tên mẫu."))
            return

        templates = load_user_page_templates()
        new_template = {
            "name": name,
            "filename": self._template_tab_title(name),
            "content": content,
        }
        replaced = False
        for idx, template in enumerate(templates):
            if template["name"].casefold() == name.casefold():
                res = QMessageBox.question(
                    self, t("Mẫu đã tồn tại"),
                    t("Mẫu '{name}' đã tồn tại. Ghi đè bằng trang hiện tại?", name=name),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if res != QMessageBox.StandardButton.Yes:
                    return
                templates[idx] = new_template
                replaced = True
                break
        if not replaced:
            templates.append(new_template)

        if not save_user_page_templates(templates):
            QMessageBox.critical(self, t("Lỗi lưu mẫu"), t("Không thể lưu mẫu mới vào cấu hình."))
            return

        self.user_page_templates = templates
        self._refresh_new_page_menu()
        action_text = t("cập nhật") if replaced else t("thêm")
        self.status_msg.setText(t("Đã {action} mẫu: {name}", action=action_text, name=name))

    @staticmethod
    def _template_tab_title(name):
        cleaned = "".join("-" if ch in '<>:"/\\|?*' else ch for ch in name).strip(" .")
        return f"{cleaned or t('Chưa đặt tên')}.md"

    @staticmethod
    def _suggest_template_name(content, editor):
        for line in content.splitlines():
            title = line.strip()
            if title.startswith("# "):
                return title[2:].strip() or t("Mẫu mới")
        if editor.file_path:
            return os.path.splitext(os.path.basename(editor.file_path))[0]
        return t("Mẫu mới")

    def _open_file(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, t("Mở tệp Markdown"), "",
            t("Markdown (*.md *.markdown *.mdown *.txt);;Tất cả (*)"))
        for p in paths:
            self._open_specific_file(p)

    def _open_specific_file(self, path):
        path = os.path.abspath(path)
        if not os.path.exists(path):
            QMessageBox.warning(self, t("Không tìm thấy tệp"), path)
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
            QMessageBox.critical(self, t("Không đọc được tệp"), str(exc))
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
                self, t("Chưa lưu"),
                t("Tệp '{name}' chưa được lưu. Lưu trước khi đóng?", name=self.tabs.tabText(index)),
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
        self.status_pos.setText(t("Dòng {line}, Cột {col}", line=line, col=col))
        text = editor.toPlainText()
        words = len([w for w in text.split() if w])
        chars = len(text)
        self.status_words.setText(t("{words} từ · {chars} ký tự", words=words, chars=chars))

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
            self.status_msg.setText(t("Đã lưu: {path}", path=editor.file_path))
            push_recent(editor.file_path)
            self._refresh_recent_menu()
            return True
        except Exception as exc:
            QMessageBox.critical(self, t("Lỗi lưu"), str(exc))
            return False

    def _save_as_current(self):
        editor = self._cur_editor()
        if not editor:
            return False
        path, _ = QFileDialog.getSaveFileName(
            self, t("Lưu thành .md"), editor.file_path or "tai-lieu.md",
            t("Markdown (*.md);;Tất cả (*)"))
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
        name = os.path.basename(editor.file_path) if editor.file_path else t("Chưa đặt tên.md")
        if editor.document().isModified():
            name = "● " + name
        self.tabs.setTabText(index, name)

    def _on_editor_changed(self):
        idx = self.tabs.currentIndex()
        if idx >= 0:
            self._update_tab_title(idx)
        self._update_status_pos()
        # Debounce 700ms: auto update nhẹ cho block hiện tại, không chạy lại TikZJax.
        self.preview_timer.start(700)

    # =====================================================================
    # Toast helper
    # =====================================================================
    def _toast(self, message, kind="info", duration_ms=3500,
               action_label="", on_action=None):
        """Hiện toast không-modal ở góc dưới-phải; fallback statusbar."""
        try:
            return Toast.show_toast(self, message, kind=kind,
                                     duration_ms=duration_ms,
                                     action_label=action_label,
                                     on_action=on_action)
        except Exception:
            self.status_msg.setText(message)
            return None

    # =====================================================================
    # Export
    # =====================================================================
    def _export_via_worker(self, kind, path, work_fn, success_message,
                            *, open_label=None):
        """Chạy 1 tác vụ export trên worker thread, hiện toast khi xong.

        ``work_fn`` là callable không tham số, thực hiện việc ghi ra ``path``.
        """
        open_label = open_label or t("Mở tệp")
        self.status_msg.setText("⌛ " + t("Đang xuất {kind}...", kind=kind))
        toast_busy = self._toast(t("Đang xuất {kind}…", kind=kind), kind="info",
                                  duration_ms=0)

        def _on_done(_result):
            self._remember_export(path)
            self.status_msg.setText(success_message)
            self._toast(
                success_message,
                kind="success",
                duration_ms=5000,
                action_label=open_label,
                on_action=lambda p=path: QDesktopServices.openUrl(QUrl.fromLocalFile(p)),
            )

        def _on_error(message):
            self.status_msg.setText("❌ " + t("Lỗi xuất {kind}: {message}", kind=kind, message=message))
            self._toast(t("Lỗi xuất {kind}: {message}", kind=kind, message=message), kind="error",
                         duration_ms=6000)

        def _on_finished():
            if toast_busy is not None:
                toast_busy.dismiss()

        run_async(self, work_fn,
                   on_done=_on_done, on_error=_on_error,
                   on_finished=_on_finished)

    def _export_html(self):
        editor = self._cur_editor()
        if not editor:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, t("Xuất HTML"),
            (editor.file_path or "tai-lieu").rsplit(".", 1)[0] + ".html",
            "HTML (*.html)")
        if not path:
            return
        source = editor.toPlainText()

        def work():
            with open(path, "w", encoding="utf-8") as f:
                f.write(markdown_to_html(source))
            return path

        self._export_via_worker("HTML", path, work, f"✅ {t('Đã xuất HTML: {path}', path=path)}")

    def _export_latex(self):
        editor = self._cur_editor()
        if not editor:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, t("Xuất LaTeX"),
            (editor.file_path or "tai-lieu").rsplit(".", 1)[0] + ".tex",
            "LaTeX (*.tex)")
        if not path:
            return
        source = editor.toPlainText()
        # Lấy tiêu đề từ # heading đầu tiên nếu có (trên main thread, rẻ).
        title = t("Tài liệu Markdown")
        for line in source.split("\n"):
            m = line.strip()
            if m.startswith("# "):
                title = m[2:].strip()
                break

        def work():
            with open(path, "w", encoding="utf-8") as f:
                f.write(markdown_to_latex(source, title=title))
            return path

        self._export_via_worker("LaTeX", path, work, f"✅ {t('Đã xuất LaTeX: {path}', path=path)}")

    def _export_docx(self):
        editor = self._cur_editor()
        if not editor:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, t("Xuất Word"),
            (editor.file_path or "tai-lieu").rsplit(".", 1)[0] + ".docx",
            "Word (*.docx)")
        if not path:
            return
        source = editor.toPlainText()

        def work():
            markdown_to_docx(source, path)
            return path

        self._export_via_worker("Word", path, work, f"✅ {t('Đã xuất Word: {path}', path=path)}")

    def _export_pdf(self):
        """In bản preview hiện tại (đã render MathJax + TikZ) ra PDF.

        Thay vì fix 1.6s đoán mò, polling cờ ``__emexRenderState`` mà
        ``preview.py`` set sau khi MathJax + TikZ xong.
        """
        editor = self._cur_editor()
        if not editor:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, t("Xuất PDF"),
            (editor.file_path or "tai-lieu").rsplit(".", 1)[0] + ".pdf",
            "PDF (*.pdf)")
        if not path:
            return

        if not self.preview.isVisible():
            self.act_toggle_preview.setChecked(True)
        self.preview.render(editor.toPlainText(),
                            base_url=os.path.dirname(editor.file_path) if editor.file_path else "")

        self.status_msg.setText("⌛ " + t("Đang chờ MathJax/TikZ kết xuất rồi in PDF..."))
        toast = self._toast(t("Đang chuẩn bị PDF…"), kind="info", duration_ms=0)

        deadline_ms = 12000
        poll_ms = 120
        elapsed = {"t": 0}

        def poll():
            elapsed["t"] += poll_ms

            def _on_state(state):
                if state == "error":
                    if toast is not None:
                        toast.dismiss()
                    self.status_msg.setText("❌ " + t("Lỗi kết xuất xem trước, không xuất được PDF."))
                    self._toast(t("Lỗi kết xuất xem trước, không xuất được PDF."),
                                 kind="error", duration_ms=6000)
                elif state == "done":
                    if toast is not None:
                        toast.dismiss()
                    self._print_pdf_now(path)
                elif elapsed["t"] >= deadline_ms:
                    if toast is not None:
                        toast.dismiss()
                    self.status_msg.setText("❌ " + t("Xem trước kết xuất quá lâu, không xuất được PDF."))
                    self._toast(t("Xem trước kết xuất quá lâu, không xuất được PDF."),
                                 kind="error", duration_ms=6000)
                else:
                    QTimer.singleShot(poll_ms, poll)

            try:
                self.preview.web.page().runJavaScript(
                    "window.__emexRenderState || 'pending'", _on_state)
            except Exception:
                # Nếu Qt không cho callback (rất hiếm), fallback fixed delay
                QTimer.singleShot(max(0, 1600 - elapsed["t"]),
                                   lambda: self._print_pdf_now(path))

        QTimer.singleShot(poll_ms, poll)

    def _print_pdf_now(self, path):
        page = self.preview.web.page()
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
            self.status_msg.setText(f"✅ {t('Đã xuất PDF: {path}', path=file_path)}")
            self._toast(
                f"✅ {t('Đã xuất PDF: {name}', name=os.path.basename(file_path))}",
                kind="success",
                duration_ms=5000,
                action_label=t("Mở tệp"),
                on_action=lambda p=file_path: QDesktopServices.openUrl(QUrl.fromLocalFile(p)),
            )
        else:
            self.status_msg.setText("❌ " + t("Xuất PDF thất bại."))
            self._toast(t("Không thể tạo PDF từ khung xem trước. Kiểm tra khung xem trước đang hiển thị đúng."),
                         kind="error", duration_ms=6000)

    def _remember_export(self, path):
        self.last_export_path = os.path.abspath(path)

    def _open_last_export(self):
        if not self.last_export_path:
            self._toast(t("Chưa có tệp nào được xuất trong phiên này."),
                         kind="info", duration_ms=3000)
            return
        if not os.path.exists(self.last_export_path):
            self._toast(t("Không tìm thấy: {path}", path=self.last_export_path),
                         kind="warning", duration_ms=4000)
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
        path, _ = QFileDialog.getOpenFileName(self, t("Chọn ảnh"), "",
                                              t("Hình ảnh (*.png *.jpg *.jpeg *.svg *.gif *.webp)"))
        if not path:
            return
        if editor.file_path:
            try:
                path = os.path.relpath(path, os.path.dirname(editor.file_path))
            except ValueError:
                pass
        path = path.replace("\\", "/")
        editor.apply_snippet(f"![%|]({self._markdown_link_target(path)})")

    def _insert_pasted_image_from_mime(self, editor, source):
        """Save clipboard images and insert Markdown image links."""
        try:
            inserted_paths = []
            saved_clipboard_image = False
            if source.hasImage():
                image = source.imageData()
                if isinstance(image, QPixmap):
                    image = image.toImage()
                if isinstance(image, QImage) and not image.isNull():
                    inserted_paths.append(self._save_pasted_image(editor, image))
                    saved_clipboard_image = True

            if not saved_clipboard_image and source.hasUrls():
                for url in source.urls():
                    path = url.toLocalFile()
                    if path and self._is_image_file_path(path):
                        inserted_paths.append(self._copy_pasted_image_file(editor, path))

            if not inserted_paths:
                return False

            self._insert_image_markdown(editor, inserted_paths)
            self.status_msg.setText(t(
                "Đã chèn ảnh từ clipboard: {name}",
                name=os.path.basename(inserted_paths[-1]),
            ))
            return True
        except Exception as exc:
            self.status_msg.setText(t("Không dán được ảnh: {message}", message=str(exc)))
            return False

    @staticmethod
    def _is_image_file_path(path):
        mime = mimetypes.guess_type(path)[0] or ""
        ext = os.path.splitext(path)[1].lower()
        return mime.startswith("image/") or ext in IMAGE_FILE_EXTENSIONS

    def _image_asset_dir(self, editor):
        if getattr(editor, "file_path", ""):
            return os.path.join(os.path.dirname(os.path.abspath(editor.file_path)), "images")
        return os.path.join(CONFIG_DIR, "pasted_images")

    @staticmethod
    def _unique_pasted_image_path(folder, ext=".png"):
        os.makedirs(folder, exist_ok=True)
        ext = ext.lower() if ext else ".png"
        if ext not in IMAGE_FILE_EXTENSIONS:
            ext = ".png"
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        path = os.path.join(folder, f"pasted-{stamp}{ext}")
        counter = 2
        while os.path.exists(path):
            path = os.path.join(folder, f"pasted-{stamp}-{counter}{ext}")
            counter += 1
        return path

    def _save_pasted_image(self, editor, image):
        path = self._unique_pasted_image_path(self._image_asset_dir(editor), ".png")
        if not image.save(path, "PNG"):
            raise OSError(t("Không lưu được ảnh clipboard."))
        return path

    def _copy_pasted_image_file(self, editor, source_path):
        ext = os.path.splitext(source_path)[1].lower() or ".png"
        target = self._unique_pasted_image_path(self._image_asset_dir(editor), ext)
        shutil.copy2(source_path, target)
        return target

    def _image_markdown_path(self, editor, path):
        if getattr(editor, "file_path", ""):
            try:
                path = os.path.relpath(path, os.path.dirname(os.path.abspath(editor.file_path)))
            except ValueError:
                pass
        return path.replace("\\", "/")

    def _insert_image_markdown(self, editor, paths):
        cursor = editor.textCursor()
        selected = cursor.selectedText().replace(" ", " ").strip()
        if len(paths) == 1:
            alt = selected or t("ảnh")
            target = self._markdown_link_target(self._image_markdown_path(editor, paths[0]))
            cursor.insertText(f"![{alt}]({target})")
        else:
            lines = []
            for index, path in enumerate(paths, start=1):
                alt = f"{t('ảnh')} {index}"
                target = self._markdown_link_target(self._image_markdown_path(editor, path))
                lines.append(f"![{alt}]({target})")
            cursor.insertText("\n".join(lines))
        editor.setTextCursor(cursor)
        editor.setFocus()

    @staticmethod
    def _markdown_link_target(path):
        if any(ch.isspace() for ch in path) or any(ch in path for ch in "()"):
            return f"<{path.replace('>', '%3E')}>"
        return path

    def _insert_link(self):
        editor = self._cur_editor()
        if not editor:
            return
        url, ok = QInputDialog.getText(self, t("Chèn liên kết"), t("URL:"))
        if not ok:
            return
        editor.apply_snippet(f"[%|]({url})")

    def _insert_codeblock(self):
        editor = self._cur_editor()
        if not editor:
            return
        lang, ok = QInputDialog.getText(self, t("Khối mã"),
                                         t("Ngôn ngữ (ví dụ: python, javascript, tikz):"))
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

    def _do_auto_preview_update(self):
        editor = self._cur_editor()
        if not editor or not self.preview.isVisible():
            return
        block_text, start_line = self._current_markdown_block(editor)
        if not self._can_auto_update_preview_block(block_text):
            return
        self.preview.update_fragment(block_text, start_line)

    @staticmethod
    def _can_auto_update_preview_block(block_text):
        text = block_text or ""
        stripped = text.strip()
        if not stripped:
            return False
        low = stripped.lower()
        if low.startswith("```tikz") or "\\begin{tikzpicture}" in low:
            return False
        return True

    def _compile_preview(self):
        self.preview.set_compiling(True)
        self.status_msg.setText(t("Đang biên dịch xem trước..."))
        self._do_render_preview()

        def finish():
            self.preview.set_compiling(False)
            self.status_msg.setText(t("Đã biên dịch xem trước."))

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

        # Display math $$...$$, \[...\], plus legacy pasted [...] blocks.
        math_delimiters = (("$$", "$$", "startswith"), (r"\[", r"\]", "exact"), ("[", "]", "exact"))
        for opener, closer, mode in math_delimiters:
            math_start = None
            for i in range(line, -1, -1):
                token = stripped(i)
                if (mode == "startswith" and token.startswith(opener)) or token == opener:
                    math_start = i
                    break
            if math_start is None:
                continue
            if mode == "startswith":
                math_count = sum(1 for i in range(0, math_start + 1)
                                 if stripped(i).startswith(opener))
                if math_count % 2 != 1:
                    continue
                end = math_start
                while end + 1 < len(lines) and not stripped(end + 1).endswith(closer):
                    end += 1
                if end + 1 < len(lines):
                    return block_join(math_start, end + 1)
            else:
                end = math_start
                while end + 1 < len(lines) and stripped(end + 1) != closer:
                    end += 1
                if end + 1 < len(lines):
                    return block_join(math_start, end + 1)

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
        self.status_msg.setText(t("Đã đồng bộ tới dòng {line}.", line=line))

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
        self.status_msg.setText(t("Đã thay {count} chỗ.", count=cnt))

    # =====================================================================
    # AI
    # =====================================================================
    def trigger_ai_assistant(self):
        dlg = AIQuickDialog(self)
        if dlg.exec() and dlg.action_taken == "dock":
            self._show_ai_panel(dlg.take_chat_widget())

    def _show_ai_panel(self, widget=None):
        if self.ai_chat_widget is not None and self.ai_chat_widget is not widget:
            self.ai_chat_widget.setParent(None)
            self.ai_chat_widget.deleteLater()
            self.ai_chat_widget = None
        if widget is None:
            widget = AIChatWidget(self, compact=True)
        widget.set_compact(True)
        try:
            widget.undock_requested.disconnect(self._undock_ai_panel)
        except Exception:
            pass
        try:
            widget.closed_requested.disconnect(self._hide_ai_panel)
        except Exception:
            pass
        widget.undock_requested.connect(self._undock_ai_panel)
        widget.closed_requested.connect(self._hide_ai_panel)
        self.ai_chat_widget = widget
        self.ai_panel_layout.addWidget(widget)
        self.ai_panel_host.setVisible(True)
        self.editor_config["ui_ai_state"] = "compact"
        self.left_splitter.setSizes([620, 300])
        sizes = self.main_splitter.sizes()
        if sizes and sizes[0] < 320:
            self.main_splitter.setSizes([340, max(520, sizes[1]), sizes[2] if len(sizes) > 2 else 520])
        widget.input_edit.setFocus()

    def _hide_ai_panel(self):
        self.ai_panel_host.setVisible(False)
        self.editor_config["ui_ai_state"] = "closed"
        if self.ai_chat_widget is not None:
            widget = self.ai_chat_widget
            self.ai_chat_widget = None
            self.ai_panel_layout.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()

    def _undock_ai_panel(self):
        if self.ai_chat_widget is None:
            return
        widget = self.ai_chat_widget
        self.ai_chat_widget = None
        self.ai_panel_layout.removeWidget(widget)
        self.ai_panel_host.setVisible(False)
        self.editor_config["ui_ai_state"] = "closed"
        widget.setParent(None)
        try:
            widget.undock_requested.disconnect(self._undock_ai_panel)
        except Exception:
            pass
        try:
            widget.closed_requested.disconnect(self._hide_ai_panel)
        except Exception:
            pass
        dlg = AIQuickDialog(self, chat_widget=widget)
        if dlg.exec() and dlg.action_taken == "dock":
            self._show_ai_panel(dlg.take_chat_widget())

    # =====================================================================
    # Misc
    # =====================================================================
    def _valid_splitter_sizes(self, sizes, expected):
        return (isinstance(sizes, list)
                and len(sizes) == expected
                and all(isinstance(v, int) and v >= 0 for v in sizes)
                and sum(sizes) > 0)

    def _valid_window_geometry(self, geometry):
        return (isinstance(geometry, list)
                and len(geometry) == 4
                and all(isinstance(v, int) for v in geometry)
                and geometry[2] >= 640
                and geometry[3] >= 480)

    def _restore_ui_state(self):
        geometry = self.editor_config.get("ui_window_geometry", [])
        if self._valid_window_geometry(geometry):
            self.setGeometry(*geometry)
        if self.editor_config.get("ui_window_maximized", False):
            QTimer.singleShot(0, self.showMaximized)

        palette_visible = self.editor_config.get("ui_palette_visible", True)
        preview_visible = self.editor_config.get("ui_preview_visible", True)
        self.symbol_palette.setVisible(palette_visible)
        self.preview.setVisible(preview_visible)
        self.act_toggle_palette.blockSignals(True)
        self.act_toggle_palette.setChecked(palette_visible)
        self.act_toggle_palette.blockSignals(False)
        self.act_toggle_preview.blockSignals(True)
        self.act_toggle_preview.setChecked(preview_visible)
        self.act_toggle_preview.blockSignals(False)

        if self.editor_config.get("ui_ai_state") == "compact" and self.ai_chat_widget is None:
            self._show_ai_panel()

        main_sizes = self.editor_config.get("ui_main_splitter_sizes", [])
        if self._valid_splitter_sizes(main_sizes, 3):
            self.main_splitter.setSizes(main_sizes)
        left_sizes = self.editor_config.get("ui_left_splitter_sizes", [])
        if self._valid_splitter_sizes(left_sizes, 2):
            self.left_splitter.setSizes(left_sizes)

        if self.editor_config.get("ui_zen_enabled", False):
            self.act_zen.setChecked(True)

    def _save_ui_state(self):
        self.editor_config["ui_preview_visible"] = self.preview.isVisible()
        self.editor_config["ui_palette_visible"] = self.symbol_palette.isVisible()
        self.editor_config["ui_ai_state"] = (
            "compact" if self.ai_chat_widget is not None and self.ai_panel_host.isVisible()
            else "closed"
        )
        self.editor_config["ui_main_splitter_sizes"] = self.main_splitter.sizes()
        self.editor_config["ui_left_splitter_sizes"] = self.left_splitter.sizes()
        normal = self.normalGeometry()
        self.editor_config["ui_window_geometry"] = [
            normal.x(), normal.y(), normal.width(), normal.height()
        ]
        self.editor_config["ui_window_maximized"] = self.isMaximized()
        self.editor_config["ui_zen_enabled"] = self.act_zen.isChecked()
        save_editor_config(self.editor_config)

    def _toggle_preview(self, on):
        self.preview.setVisible(on)
        self.editor_config["ui_preview_visible"] = on
        if on:
            sizes = self.main_splitter.sizes()
            if sizes[2] < 200:
                self.main_splitter.setSizes([sizes[0], sizes[1], 500])
            self._do_render_preview()

    def _toggle_palette(self, on):
        self.symbol_palette.setVisible(on)
        self.editor_config["ui_palette_visible"] = on

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
            # Cập nhật kích thước toolbar & bảng ký hiệu
            self._apply_toolbar_sizes()
            self.symbol_palette.apply_config(self.editor_config)
            self._retranslate_ui()
            self.status_msg.setText(t("Đã cập nhật cấu hình."))

    def _retranslate_ui(self):
        """Cập nhật các nhãn chính sau khi đổi ngôn ngữ."""
        self.find_input.setPlaceholderText(t("Tìm..."))
        self.replace_input.setPlaceholderText(t("Thay bằng..."))
        self.lbl_find.setText(t("Tìm:"))
        self.lbl_replace.setText(t("Thay:"))
        self.btn_find_replace.setText(t("Thay"))
        self.btn_find_replace_all.setText(t("Thay tất cả"))

        self.act_new.setText(t("Trang trống (Ctrl+N)"))
        self.act_open.setText(t("Mở (Ctrl+O)"))
        self.act_save.setText(t("Lưu (Ctrl+S)"))
        self.act_save_as.setText(t("Lưu thành... (Ctrl+Shift+S)"))
        self.act_bold.setText(t("In đậm (Ctrl+B)"))
        self.act_italic.setText(t("In nghiêng (Ctrl+I)"))
        self.act_strike.setText(t("Gạch ngang"))
        self.act_code.setText(t("Mã trong dòng"))
        self.act_inline_math.setText(t("Toán trong dòng (Ctrl+M)"))
        self.act_block_math.setText(t("Toán khối (Ctrl+Shift+M)"))
        self.act_quote.setText(t("Trích dẫn"))
        self.act_hr.setText(t("Đường ngang"))
        self.act_link.setText(t("Chèn liên kết"))
        self.act_image.setText(t("Chèn ảnh"))
        self.act_table.setText(t("Bảng (Ctrl+T)"))
        self.act_codeblock.setText(t("Khối mã"))
        self.act_comment.setText(t("Bình luận HTML (Ctrl+/)"))
        self.act_find.setText(t("Tìm (Ctrl+F)"))
        self.act_replace.setText(t("Thay (Ctrl+H)"))
        self.act_render.setText(t("Biên dịch xem trước (Ctrl+Enter)"))
        self.act_ai.setText(t("Trợ lý eMeX (Ctrl+G)"))
        self.act_toggle_preview.setText(t("Bật/Tắt xem trước (Ctrl+P)"))
        self.act_toggle_palette.setText(t("Bật/Tắt bảng ký hiệu"))
        self.act_zen.setText(t("Chế độ tập trung (F11)"))
        self.act_settings.setText(t("Cài đặt"))
        self.act_about.setText(t("Giới thiệu"))
        self.act_about.setToolTip(t("Giới thiệu"))

        self.btn_new.setToolTip(t("Tạo trang Markdown mới từ trang trống hoặc mẫu"))
        self.btn_open.setToolTip(t("Mở tệp Markdown / tệp gần đây"))
        self.btn_save.setToolTip(t("Lưu tệp Markdown hiện tại (Ctrl+S)"))
        self.btn_insert.setToolTip(t("Chèn nội dung"))
        self.btn_tools.setToolTip(t("Công cụ soạn thảo"))
        self.btn_view.setToolTip(t("Tùy chọn hiển thị"))
        self.preview.retranslate_ui()
        self.symbol_palette.retranslate_ui()
        if self.ai_chat_widget is not None:
            self.ai_chat_widget.retranslate_ui()
        self._refresh_new_page_menu()
        self._refresh_recent_menu()
        self._configure_preview_export_menu()
        self._retranslate_untitled_tabs()
        self._update_status_pos()

    def _retranslate_untitled_tabs(self):
        untitled_names = {"Chưa đặt tên.md", "Untitled.md"}
        for i in range(self.tabs.count()):
            editor = self.tabs.widget(i)
            if getattr(editor, "file_path", ""):
                continue
            if self.tabs.tabText(i) in untitled_names:
                self.tabs.setTabText(i, t("Chưa đặt tên.md"))

    def _apply_toolbar_sizes(self):
        """Áp dụng kích thước toolbar từ cấu hình hiện tại."""
        icon_sz = self.editor_config.get("toolbar_icon_size", 22)
        pad = self.editor_config.get("toolbar_btn_padding", 6)
        self._toolbar_pad = pad
        self.toolbar.setIconSize(QSize(icon_sz, icon_sz))
        # Cập nhật padding cho tất cả QToolButton trên toolbar
        for child in self.toolbar.findChildren(QToolButton):
            old_ss = child.styleSheet()
            if old_ss:
                # Thay padding:Npx thành giá trị mới
                import re
                new_ss = re.sub(
                    r'padding:\s*\d+px',
                    f'padding:{pad}px',
                    old_ss
                )
                child.setStyleSheet(new_ss)

    def _open_about(self):
        if getattr(self, "_update_available", False) and self._pending_release is not None:
            self._open_update_dialog()
            return
        AboutDialog(self).exec()

    # =====================================================================
    # Auto-update
    # =====================================================================
    def _init_update_notification(self):
        self._update_available = False
        self._pending_release = None
        self._about_blink_on = True
        self._about_blink_timer = QTimer(self)
        self._about_blink_timer.setInterval(620)
        self._about_blink_timer.timeout.connect(self._blink_about_update_icon)
        self._update_check_thread = None
        self._update_checker = None

    def _start_update_check(self):
        if self._update_check_thread is not None:
            return
        try:
            from .updater import UpdateChecker
        except Exception:
            return

        thread = QThread(self)
        checker = UpdateChecker()
        checker.moveToThread(thread)
        thread.started.connect(checker.run)
        checker.update_available.connect(self._set_update_available)
        checker.check_done.connect(thread.quit)
        checker.check_done.connect(checker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: setattr(self, "_update_check_thread", None))
        thread.finished.connect(lambda: setattr(self, "_update_checker", None))
        self._update_check_thread = thread
        self._update_checker = checker
        thread.start()

    def _set_update_available(self, release):
        self._update_available = True
        self._pending_release = release
        self._about_blink_on = True
        self.act_about.setText(t("Giới thiệu"))
        self.act_about.setToolTip(
            t("Có bản cập nhật mới: eMeX v{version}\nNhấp để cập nhật.", version=release.version)
        )
        self.act_about.setIcon(self._make_update_about_icon(True))
        if not self._about_blink_timer.isActive():
            self._about_blink_timer.start()
        self.status_msg.setText(t("Có bản cập nhật mới: eMeX v{version}", version=release.version))

    def _clear_update_notification(self):
        self._update_available = False
        self._pending_release = None
        self._about_blink_on = True
        self._about_blink_timer.stop()
        self.act_about.setText(t("Giới thiệu"))
        self.act_about.setToolTip(t("Giới thiệu"))
        self.act_about.setIcon(emoji_icon("ℹ"))

    def _blink_about_update_icon(self):
        if not self._update_available:
            self._about_blink_timer.stop()
            return
        self._about_blink_on = not self._about_blink_on
        self.act_about.setIcon(self._make_update_about_icon(self._about_blink_on))

    def _make_update_about_icon(self, on: bool, size=36):
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        margin = 3
        rect = QRectF(pm.rect()).adjusted(margin, margin, -margin, -margin)
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        if on:
            grad.setColorAt(0.0, QColor("#ef4444"))
            grad.setColorAt(1.0, QColor("#f97316"))
            text_color = QColor("#ffffff")
            ring_color = QColor("#fee2e2")
        else:
            grad.setColorAt(0.0, QColor("#fef3c7"))
            grad.setColorAt(1.0, QColor("#fde68a"))
            text_color = QColor("#92400e")
            ring_color = QColor("#f59e0b")

        p.setPen(QPen(ring_color, 2))
        p.setBrush(grad)
        p.drawEllipse(rect)
        p.setFont(QFont("Segoe UI", int(size * 0.62), QFont.Weight.Black))
        p.setPen(text_color)
        p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "!")
        p.end()
        return QIcon(pm)

    def _open_update_dialog(self):
        from .update_dialog import RESULT_SKIP, UpdateDialog
        dlg = UpdateDialog(self._pending_release, parent=self)
        result = dlg.exec()
        if result == RESULT_SKIP:
            self._clear_update_notification()

    def _auto_save(self):
        """Auto-save không-blocking: snapshot nội dung trên main thread rồi
        ghi nền. Đánh dấu modified=False ngay lập tức để user không thấy nháy.
        """
        pending = []
        for i in range(self.tabs.count()):
            ed = self.tabs.widget(i)
            if ed.file_path and ed.document().isModified():
                pending.append((i, ed, ed.file_path, ed.toPlainText()))
        if not pending:
            return

        def write_all():
            errors = []
            for _idx, _ed, path, text in pending:
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(text)
                except Exception as exc:  # noqa: BLE001
                    errors.append((path, str(exc)))
            return errors

        def on_done(errors):
            if errors:
                # Không spam toast cho auto-save; chỉ ghi status bar.
                names = ", ".join(os.path.basename(p) for p, _ in errors[:3])
                self.status_msg.setText(t("Tự động lưu lỗi: {names}", names=names))
                return
            for idx, ed, _path, _text in pending:
                # Có thể tab đã đóng trong lúc đang lưu, skip an toàn.
                try:
                    if ed.document().isModified() and ed.toPlainText() == _text:
                        ed.document().setModified(False)
                        self._update_tab_title(idx)
                except RuntimeError:
                    pass

        run_async(self, write_all, on_done=on_done)

    # =====================================================================
    # Session
    # =====================================================================
    def _load_session_or_default(self):
        """Khôi phục phiên bằng cách đọc file song song trên thread riêng,
        sau đó dồn về main thread để tạo tab. Splash dismiss được sớm hơn
        vì window đã sẵn sàng trước khi file đọc xong.
        """
        paths = self._session_paths()
        if not paths:
            self._new_file()
            return

        # Tạo 1 tab placeholder ngay để window không trống. Khi reader xong,
        # nội dung sẽ được nạp vào tabs thực sự.
        self._new_file()
        placeholder_idx = self.tabs.count() - 1

        def read_all():
            results = []
            for p in paths:
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        results.append((p, f.read(), None))
                except Exception as exc:  # noqa: BLE001
                    results.append((p, None, str(exc)))
            return results

        def on_done(results):
            # Xoá placeholder nếu trống và còn nhiều hơn 1 tab sẽ hiển thị.
            successful = [r for r in results if r[1] is not None]
            if successful:
                placeholder = self.tabs.widget(placeholder_idx)
                if (placeholder is not None
                        and not placeholder.toPlainText().strip()
                        and not placeholder.file_path):
                    self.tabs.removeTab(placeholder_idx)
            for path, content, _err in successful:
                self._add_tab(os.path.basename(path), content, path)
                push_recent(path)
            self._refresh_recent_menu()
            failures = [(p, e) for p, c, e in results if c is None]
            if failures:
                names = ", ".join(os.path.basename(p) for p, _ in failures[:3])
                self._toast(t("Không mở được {count} tệp: {names}", count=len(failures), names=names),
                             kind="warning", duration_ms=5000)

        run_async(self, read_all, on_done=on_done,
                   on_error=lambda msg: self._toast(
                       t("Lỗi khôi phục phiên: {message}", message=msg), kind="error"))

    def _session_paths(self):
        if not os.path.exists(SESSION_FILE):
            return []
        try:
            import json
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return []
        return [p for p in data.get("files", []) if isinstance(p, str) and os.path.exists(p)]

    def _save_session(self):
        files = []
        for i in range(self.tabs.count()):
            ed = self.tabs.widget(i)
            if ed.file_path:
                files.append(ed.file_path)
        save_json(SESSION_FILE, {"files": files})

    # =====================================================================
    # Tab UX: middle-click close, context menu, file actions
    # =====================================================================
    def eventFilter(self, obj, event):  # noqa: N802 (Qt API)
        if hasattr(self, "tabs") and obj is self.tabs.tabBar():
            if event.type() == QEvent.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.MiddleButton:
                    idx = self.tabs.tabBar().tabAt(event.pos())
                    if idx >= 0:
                        self._close_tab(idx)
                        return True
        return super().eventFilter(obj, event)

    def _show_tab_context_menu(self, pos):
        bar = self.tabs.tabBar()
        idx = bar.tabAt(pos)
        if idx < 0:
            return
        editor = self.tabs.widget(idx)
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu{background:#ffffff;color:#0f172a;border:1px solid #cbd5e1;padding:4px;}"
            "QMenu::item{padding:6px 14px;border-radius:5px;margin:1px;}"
            "QMenu::item:selected{background:#2563eb;color:#ffffff;}"
            "QMenu::separator{height:1px;background:#e5e7eb;margin:4px 6px;}")

        act_close = menu.addAction(t("Đóng tab"))
        act_close.triggered.connect(lambda: self._close_tab(idx))
        act_close_others = menu.addAction(t("Đóng các tab khác"))
        act_close_others.setEnabled(self.tabs.count() > 1)
        act_close_others.triggered.connect(lambda: self._close_other_tabs(idx))
        act_close_right = menu.addAction(t("Đóng các tab bên phải"))
        act_close_right.setEnabled(idx < self.tabs.count() - 1)
        act_close_right.triggered.connect(lambda: self._close_tabs_to_right(idx))

        if editor and editor.file_path and os.path.exists(editor.file_path):
            menu.addSeparator()
            act_open_folder = menu.addAction(t("Mở thư mục chứa"))
            act_open_folder.triggered.connect(
                lambda p=editor.file_path: self._reveal_in_explorer(p))
            act_copy_path = menu.addAction(t("Sao chép đường dẫn"))
            act_copy_path.triggered.connect(
                lambda p=editor.file_path: QApplication.clipboard().setText(p))

        menu.exec(bar.mapToGlobal(pos))

    def _close_other_tabs(self, keep_idx):
        # Đóng từ phải sang trái để index không lệch.
        for i in range(self.tabs.count() - 1, -1, -1):
            if i != keep_idx:
                self._close_tab(i)

    def _close_tabs_to_right(self, idx):
        for i in range(self.tabs.count() - 1, idx, -1):
            self._close_tab(i)

    def _reveal_in_explorer(self, path):
        path = os.path.abspath(path)
        folder = os.path.dirname(path) or path
        if sys.platform == "win32" and os.path.exists(path):
            try:
                import subprocess
                subprocess.Popen(["explorer", "/select,", path])
                return
            except Exception:
                pass
        if sys.platform == "darwin" and os.path.exists(path):
            try:
                import subprocess
                subprocess.Popen(["open", "-R", path])
                return
            except Exception:
                pass
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    # =====================================================================
    # Drag & drop
    # =====================================================================
    _DROP_EXTENSIONS = (".md", ".markdown", ".mdown", ".txt")

    def _drop_paths(self, event):
        if not event.mimeData().hasUrls():
            return []
        paths = []
        for url in event.mimeData().urls():
            local = url.toLocalFile()
            if not local:
                continue
            if local.lower().endswith(self._DROP_EXTENSIONS) and os.path.isfile(local):
                paths.append(local)
        return paths

    def dragEnterEvent(self, event):  # noqa: N802 (Qt API)
        if self._drop_paths(event):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):  # noqa: N802 (Qt API)
        if self._drop_paths(event):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):  # noqa: N802 (Qt API)
        paths = self._drop_paths(event)
        if not paths:
            super().dropEvent(event)
            return
        event.acceptProposedAction()
        for p in paths:
            self._open_specific_file(p)
        if paths:
            self._toast(t("Đã mở {count} tệp", count=len(paths)), kind="success", duration_ms=2500)

    def closeEvent(self, event):
        for i in range(self.tabs.count()):
            ed = self.tabs.widget(i)
            if ed.document().isModified() and ed.toPlainText().strip():
                self.tabs.setCurrentIndex(i)
                res = QMessageBox.question(
                    self, t("Chưa lưu"),
                    t("Tệp '{name}' có thay đổi. Lưu trước khi thoát?", name=self.tabs.tabText(i)),
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
        thread = getattr(self, "_update_check_thread", None)
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait(2000)
        timer = getattr(self, "_about_blink_timer", None)
        if timer is not None:
            timer.stop()
        self._save_ui_state()
        self._save_session()
        event.accept()

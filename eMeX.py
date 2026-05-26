#!/usr/bin/env python3
"""eMeX – trình soạn thảo Markdown gọn nhẹ, tích hợp Gemini AI.

Chạy:
    python eMeX.py [file.md]
"""
import os
import sys

# Thêm src vào path
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# QtWebEngineWidgets phải được import TRƯỚC khi QApplication được tạo
from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPalette
from PyQt6.QtWidgets import QApplication

from src.config import APP_ICON_FILE
from src.main_window import EmexWindow


def _force_light_theme(app: QApplication):
    """Ép Fusion style + palette sáng để không bị Windows dark mode chi phối."""
    app.setStyle("Fusion")

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor("#f1f5f9"))
    pal.setColor(QPalette.ColorRole.WindowText, QColor("#0f172a"))
    pal.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#f1f5f9"))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor("#0f172a"))
    pal.setColor(QPalette.ColorRole.Text, QColor("#0f172a"))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor("#94a3b8"))
    pal.setColor(QPalette.ColorRole.Button, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor("#0f172a"))
    pal.setColor(QPalette.ColorRole.BrightText, QColor("#0f172a"))
    pal.setColor(QPalette.ColorRole.Link, QColor("#2563eb"))
    pal.setColor(QPalette.ColorRole.Highlight, QColor("#2563eb"))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.Mid, QColor("#cbd5e1"))
    pal.setColor(QPalette.ColorRole.Light, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.Midlight, QColor("#e2e8f0"))
    pal.setColor(QPalette.ColorRole.Dark, QColor("#64748b"))
    pal.setColor(QPalette.ColorRole.Shadow, QColor("#0f172a"))

    # Disabled state
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#94a3b8"))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#94a3b8"))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor("#94a3b8"))

    app.setPalette(pal)

    # Stylesheet fallback cho widgets thường bị Windows hệ thống ép tối
    app.setStyleSheet("""
        QToolTip{background:#ffffff;color:#0f172a;border:1px solid #cbd5e1;padding:4px;}
        QMessageBox{background:#ffffff;color:#0f172a;}
        QMessageBox QLabel{color:#0f172a;}
        QInputDialog{background:#ffffff;color:#0f172a;}
        QInputDialog QLabel{color:#0f172a;}
        QFileDialog{background:#ffffff;color:#0f172a;}
    """)


def _first_file_arg():
    for arg in sys.argv[1:]:
        if os.path.exists(arg):
            return arg
    return None


def main():
    os.environ.setdefault("QT_MAC_WANTS_LAYER", "1")
    app = QApplication(sys.argv)
    app.setApplicationName("eMeX")
    app.setOrganizationName("eMeX")
    if os.path.exists(APP_ICON_FILE):
        app.setWindowIcon(QIcon(APP_ICON_FILE))
    app.setFont(QFont("Segoe UI" if sys.platform == "win32" else "Inter", 10))

    _force_light_theme(app)

    win = EmexWindow()
    win.show()

    file_arg = _first_file_arg()
    if file_arg:
        win._open_specific_file(file_arg)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

"""Symbol palette – sidebar có thể thu gọn, chứa ký hiệu toán & snippet thường dùng."""
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QGridLayout, QGroupBox, QPushButton,
                              QScrollArea, QVBoxLayout, QWidget)

from .config import SYMBOL_PALETTE


class SymbolButton(QPushButton):
    def __init__(self, label, snippet):
        super().__init__(label)
        self.snippet = snippet
        self.setFixedSize(38, 32)
        font = QFont()
        font.setPointSize(13)
        self.setFont(font)
        self.setToolTip(snippet.replace("%|", "▮"))
        self.setStyleSheet("""
            QPushButton {
                background:#ffffff;
                border:1px solid #d1d5db;
                border-radius:5px;
                color:#0f172a;
            }
            QPushButton:hover {
                background:#eff6ff;
                border-color:#2563eb;
                color:#1d4ed8;
            }
            QPushButton:pressed {
                background:#dbeafe;
            }
        """)


class SymbolPalette(QWidget):
    snippet_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(280)
        self.setMaximumWidth(360)
        self.setStyleSheet("QWidget{background:#f8fafc;color:#0f172a;}")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea{background:#f8fafc;border:0;}"
            "QScrollBar:vertical{background:#f1f5f9;width:10px;}"
            "QScrollBar::handle:vertical{background:#cbd5e1;border-radius:5px;min-height:24px;}"
            "QScrollBar::handle:vertical:hover{background:#94a3b8;}")
        outer.addWidget(scroll, 1)

        container = QWidget()
        container.setStyleSheet("background:#f8fafc;color:#0f172a;")
        v = QVBoxLayout(container)
        v.setContentsMargins(10, 8, 10, 10)
        v.setSpacing(10)
        scroll.setWidget(container)

        for group_name, items in SYMBOL_PALETTE.items():
            group = QGroupBox(group_name)
            group.setStyleSheet("""
                QGroupBox {
                    font-weight:700;
                    color:#0f172a;
                    border:1px solid #e5e7eb;
                    border-radius:8px;
                    margin-top: 14px;
                    padding-top: 10px;
                    background:#ffffff;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 4px;
                    color:#1d4ed8;
                    background:#ffffff;
                }
            """)
            grid = QGridLayout(group)
            grid.setSpacing(4)
            grid.setContentsMargins(8, 6, 8, 6)
            for idx, (label, snippet) in enumerate(items):
                btn = SymbolButton(label, snippet)
                btn.clicked.connect(lambda checked=False, s=snippet: self.snippet_clicked.emit(s))
                grid.addWidget(btn, idx // 6, idx % 6)
            v.addWidget(group)

        v.addStretch()

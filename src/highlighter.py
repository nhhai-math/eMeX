"""Markdown syntax highlighter."""
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QFont, QColor
from PyQt6.QtCore import QRegularExpression


def _fmt(color, bold=False, italic=False, bg=None):
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color))
    if bg:
        fmt.setBackground(QColor(bg))
    if bold:
        fmt.setFontWeight(QFont.Weight.Bold)
    if italic:
        fmt.setFontItalic(True)
    return fmt


class MarkdownHighlighter(QSyntaxHighlighter):
    """Highlighter Markdown + công thức $...$ + code fence."""

    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        # Headings (# ...)
        heading_colors = ["#0b3d91", "#1d4ed8", "#2563eb", "#3b82f6", "#60a5fa", "#93c5fd"]
        for level, color in enumerate(heading_colors):
            pattern = QRegularExpression(r"^" + "#" * (level + 1) + r"\s.*")
            self.rules.append((pattern, _fmt(color, bold=True)))

        # **bold** / __bold__
        self.rules.append((QRegularExpression(r"\*\*[^\*\n]+\*\*"),
                           _fmt("#0f172a", bold=True)))
        self.rules.append((QRegularExpression(r"__[^_\n]+__"),
                           _fmt("#0f172a", bold=True)))

        # *italic* / _italic_
        self.rules.append((QRegularExpression(r"(?<!\*)\*[^\*\n]+\*(?!\*)"),
                           _fmt("#334155", italic=True)))
        self.rules.append((QRegularExpression(r"(?<!_)_[^_\n]+_(?!_)"),
                           _fmt("#334155", italic=True)))

        # ~~strike~~
        self.rules.append((QRegularExpression(r"~~[^~\n]+~~"),
                           _fmt("#64748b", italic=True)))

        # `inline code`
        self.rules.append((QRegularExpression(r"`[^`\n]+`"),
                           _fmt("#9c2bb4", bg="#f5e8fb")))

        # Math inline $...$
        self.rules.append((QRegularExpression(r"\$[^$\n]+\$"),
                           _fmt("#6b21a8", bg="#faf5ff")))

        # Links / images
        self.rules.append((QRegularExpression(r"!?\[[^\]\n]*\]\([^)\n]*\)"),
                           _fmt("#0e7c7b", bold=False)))

        # Block quote > ...
        self.rules.append((QRegularExpression(r"^>\s.*"),
                           _fmt("#475569", italic=True)))

        # List markers
        self.rules.append((QRegularExpression(r"^\s*([-*+]|\d+\.)\s"),
                           _fmt("#b91c1c", bold=True)))

        # Task list checkboxes
        self.rules.append((QRegularExpression(r"^\s*[-*+]\s\[[ xX]\]"),
                           _fmt("#16a34a", bold=True)))

        # Horizontal rule
        self.rules.append((QRegularExpression(r"^(?:---+|\*\*\*+|___+)\s*$"),
                           _fmt("#94a3b8")))

        # LaTeX command (chỉ nổi bật khi có dạng \word, hữu ích khi viết math)
        self.rules.append((QRegularExpression(r"\\[a-zA-Z]+"),
                           _fmt("#0b3d91", bold=False)))

    def highlightBlock(self, text):
        # Code fence ```lang ... ``` -> đánh dấu khối
        block_state = self.previousBlockState()
        in_code = block_state >= 1
        stripped = text.strip()
        if stripped.startswith("```"):
            self.setFormat(0, len(text), _fmt("#9c2bb4", bold=True))
            # toggle state
            self.setCurrentBlockState(0 if in_code else 1)
            return
        if in_code:
            self.setFormat(0, len(text), _fmt("#475569", bg="#f8fafc"))
            self.setCurrentBlockState(1)
            return

        self.setCurrentBlockState(0)
        for pattern, fmt in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)

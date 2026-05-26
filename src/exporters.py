"""Bộ chuyển đổi Markdown → HTML / LaTeX / DOCX / PDF."""
import os
import re
import html


# ============================================================
# HTML  (re-export từ preview để main_window dùng một import duy nhất)
# ============================================================
from .preview import markdown_to_html  # noqa: F401  (re-export)


# ============================================================
# LaTeX
# ============================================================
LATEX_TEMPLATE = r"""\documentclass[12pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[english,vietnamese]{babel}
\usepackage{amsmath,amssymb,amsthm}
\usepackage{graphicx}
\usepackage{hyperref}
\usepackage{tikz}
\usepackage{xcolor}
\usepackage{listings}
\usepackage[normalem]{ulem}

\lstset{
    basicstyle=\ttfamily\small,
    backgroundcolor=\color{gray!10},
    breaklines=true,
    frame=single,
    rulecolor=\color{gray!40}
}

\title{@@TITLE@@}
\author{eMeX}
\date{\today}

\begin{document}
\maketitle

@@BODY@@

\end{document}
"""


def _latex_escape(text):
    """Escape ký tự đặc biệt LaTeX trong văn bản thường."""
    if not text:
        return text
    # backslash phải xử lý trước
    text = text.replace('\\', '\x00BS\x00')
    pairs = [
        ('&', r'\&'),
        ('%', r'\%'),
        ('$', r'\$'),
        ('#', r'\#'),
        ('_', r'\_'),
        ('{', r'\{'),
        ('}', r'\}'),
        ('~', r'\textasciitilde{}'),
        ('^', r'\textasciicircum{}'),
    ]
    for o, n in pairs:
        text = text.replace(o, n)
    text = text.replace('\x00BS\x00', r'\textbackslash{}')
    return text


def _latex_inline(text):
    """Convert markdown inline (sau khi đã escape) thành LaTeX."""
    # **bold** / __bold__
    text = re.sub(r'\*\*([^\*\n]+?)\*\*', r'\\textbf{\1}', text)
    text = re.sub(r'__([^_\n]+?)__', r'\\textbf{\1}', text)
    # *italic* / _italic_ (không khớp ** vì đã xử lý ở trên)
    text = re.sub(r'(?<![\*\\])\*([^\*\n]+?)\*(?!\*)', r'\\textit{\1}', text)
    text = re.sub(r'(?<![_a-zA-Z\\])_([^_\n]+?)_(?![_a-zA-Z])', r'\\textit{\1}', text)
    # ~~strike~~
    text = re.sub(r'~~([^~\n]+?)~~', r'\\sout{\1}', text)
    # [text](url) – chú ý đã escape '_' trong url, cần unescape một số
    def link_repl(m):
        label = m.group(1)
        url = m.group(2).replace(r'\_', '_').replace(r'\#', '#').replace(r'\%', '%')
        return f"\\href{{{url}}}{{{label}}}"
    text = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', link_repl, text)
    return text


def _markdown_to_latex_body(source):
    """Convert raw markdown body (chưa wrap document) → LaTeX body."""
    placeholders = []

    def stash(kind, content):
        placeholders.append((kind, content))
        return f"@@PH{len(placeholders) - 1}@@"

    # 1. TikZ block (ưu tiên trước code thường)
    def tikz_repl(m):
        return "\n" + stash('tikz', m.group(1).strip()) + "\n"
    source = re.sub(r'```tikz\s*([\s\S]*?)```', tikz_repl, source, flags=re.IGNORECASE)

    # 2. Code fences
    def code_repl(m):
        return "\n" + stash('code', (m.group(1) or '', m.group(2))) + "\n"
    source = re.sub(r'```(\w*)\s*\n([\s\S]*?)```', code_repl, source)

    # 3. Display math $$...$$
    def dmath_repl(m):
        return "\n" + stash('dmath', m.group(1).strip()) + "\n"
    source = re.sub(r'\$\$([\s\S]+?)\$\$', dmath_repl, source)

    # 4. Inline math $...$
    def imath_repl(m):
        return stash('imath', m.group(1))
    source = re.sub(r'(?<!\$)\$([^\n$]+?)\$(?!\$)', imath_repl, source)

    # 5. Inline code
    def icode_repl(m):
        return stash('icode', m.group(1))
    source = re.sub(r'`([^`\n]+)`', icode_repl, source)

    # ----- Tokenize line-by-line -----
    lines = source.split('\n')
    out = []
    i = 0
    in_list = None  # 'itemize' | 'enumerate' | None
    in_quote = False

    def close_blocks():
        nonlocal in_list, in_quote
        if in_list:
            out.append(f"\\end{{{in_list}}}")
            in_list = None
        if in_quote:
            out.append(r"\end{quote}")
            in_quote = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Dòng có chứa duy nhất placeholder dạng @@PHn@@ → in raw
        if re.fullmatch(r'@@PH\d+@@', stripped):
            close_blocks()
            out.append(stripped)
            i += 1
            continue

        # Heading
        h = re.match(r'^(#{1,6})\s+(.*)$', stripped)
        if h:
            close_blocks()
            level = len(h.group(1))
            content = _latex_inline(_latex_escape(h.group(2)))
            cmd = ['section', 'subsection', 'subsubsection',
                   'paragraph', 'subparagraph', 'subparagraph'][min(level - 1, 5)]
            out.append(f"\\{cmd}{{{content}}}")
            i += 1
            continue

        # Horizontal rule
        if re.match(r'^(?:---+|\*\*\*+|___+)\s*$', stripped):
            close_blocks()
            out.append(r"\noindent\rule{\linewidth}{0.4pt}")
            i += 1
            continue

        # Task list: - [ ] / - [x]
        task = re.match(r'^[-*+]\s+\[([ xX])\]\s+(.*)$', stripped)
        if task:
            if in_list != 'itemize':
                close_blocks()
                out.append(r"\begin{itemize}")
                in_list = 'itemize'
            mark = r"$\boxtimes$" if task.group(1).lower() == 'x' else r"$\square$"
            content = _latex_inline(_latex_escape(task.group(2)))
            out.append(f"  \\item[{mark}] {content}")
            i += 1
            continue

        # Bullet list
        bullet = re.match(r'^[-*+]\s+(.*)$', stripped)
        if bullet:
            if in_list != 'itemize':
                close_blocks()
                out.append(r"\begin{itemize}")
                in_list = 'itemize'
            content = _latex_inline(_latex_escape(bullet.group(1)))
            out.append(f"  \\item {content}")
            i += 1
            continue

        # Ordered list
        om = re.match(r'^\d+\.\s+(.*)$', stripped)
        if om:
            if in_list != 'enumerate':
                close_blocks()
                out.append(r"\begin{enumerate}")
                in_list = 'enumerate'
            content = _latex_inline(_latex_escape(om.group(1)))
            out.append(f"  \\item {content}")
            i += 1
            continue

        # Block quote
        if stripped.startswith('> '):
            if not in_quote:
                if in_list:
                    out.append(f"\\end{{{in_list}}}")
                    in_list = None
                out.append(r"\begin{quote}")
                in_quote = True
            out.append(_latex_inline(_latex_escape(stripped[2:])))
            i += 1
            continue

        # GFM Table: | a | b | + separator |---|---|
        if (stripped.startswith('|') and i + 1 < len(lines)
                and re.match(r'^\|[\s\-:|]+\|\s*$', lines[i + 1].strip())):
            close_blocks()
            header = [c.strip() for c in stripped.strip().strip('|').split('|')]
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                rows.append(cells)
                i += 1
            n = len(header)
            spec = '|' + 'l|' * n
            out.append(r"\begin{center}")
            out.append(f"\\begin{{tabular}}{{{spec}}}")
            out.append(r"\hline")
            out.append(' & '.join(_latex_inline(_latex_escape(c)) for c in header) + r' \\')
            out.append(r'\hline')
            for row in rows:
                row = (row + [''] * n)[:n]
                out.append(' & '.join(_latex_inline(_latex_escape(c)) for c in row) + r' \\')
                out.append(r'\hline')
            out.append(r"\end{tabular}")
            out.append(r"\end{center}")
            out.append("")
            continue

        # Image standalone: ![alt](url)
        img_only = re.match(r'^!\[([^\]]*)\]\(([^)\s]+)\)\s*$', stripped)
        if img_only:
            close_blocks()
            alt = _latex_escape(img_only.group(1))
            url = img_only.group(2)
            out.append(r"\begin{figure}[ht]")
            out.append(r"  \centering")
            out.append(f"  \\includegraphics[width=0.7\\linewidth]{{{url}}}")
            if alt:
                out.append(f"  \\caption{{{alt}}}")
            out.append(r"\end{figure}")
            i += 1
            continue

        # Dòng trống → đóng list/quote
        if not stripped:
            close_blocks()
            out.append("")
            i += 1
            continue

        # Đoạn văn thường: gom các dòng liên tiếp không phải block đặc biệt
        para = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if not nxt:
                break
            # Nếu dòng kế là heading / list / quote / table thì dừng
            if (re.match(r'^(#{1,6})\s', nxt) or re.match(r'^[-*+]\s', nxt)
                    or re.match(r'^\d+\.\s', nxt) or nxt.startswith('> ')
                    or nxt.startswith('|') or nxt.startswith('```')
                    or re.fullmatch(r'@@PH\d+@@', nxt)):
                break
            para.append(nxt)
            i += 1
        close_blocks()
        joined = ' '.join(para)
        out.append(_latex_inline(_latex_escape(joined)))
        out.append("")

    close_blocks()
    body = '\n'.join(out)

    # ----- Restore placeholders -----
    def restore(m):
        idx = int(m.group(1))
        kind, content = placeholders[idx]
        if kind == 'tikz':
            return f"\n\\begin{{tikzpicture}}\n{content}\n\\end{{tikzpicture}}\n"
        if kind == 'code':
            _lang, code = content
            return f"\n\\begin{{lstlisting}}\n{code.rstrip()}\n\\end{{lstlisting}}\n"
        if kind == 'dmath':
            return f"\n\\[\n{content}\n\\]\n"
        if kind == 'imath':
            return f"${content}$"
        if kind == 'icode':
            return f"\\texttt{{{_latex_escape(content)}}}"
        return ''
    body = re.sub(r'@@PH(\d+)@@', restore, body)
    return body


def markdown_to_latex(source, title="Tài liệu Markdown"):
    """Convert markdown source → standalone LaTeX document."""
    body = _markdown_to_latex_body(source)
    return (LATEX_TEMPLATE
            .replace('@@TITLE@@', _latex_escape(title))
            .replace('@@BODY@@', body))


# ============================================================
# DOCX
# ============================================================
def markdown_to_docx(source, path):
    """Convert markdown → .docx (cần python-docx)."""
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor, Inches
        from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
    except ImportError as exc:
        raise RuntimeError(
            "Chưa có thư viện python-docx. Cài bằng:\n  pip install python-docx") from exc

    doc = Document()

    # Default font
    normal = doc.styles['Normal']
    normal.font.name = 'Calibri'
    normal.font.size = Pt(11)

    lines = source.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Heading
        h = re.match(r'^(#{1,6})\s+(.*)$', stripped)
        if h:
            level = len(h.group(1))
            text = _docx_strip_inline(h.group(2))
            doc.add_heading(text, level=min(level, 9))
            i += 1
            continue

        # Code block
        if stripped.startswith('```'):
            lang = stripped[3:].strip()
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith('```'):
                buf.append(lines[i])
                i += 1
            i += 1  # skip closing
            p = doc.add_paragraph()
            run = p.add_run('\n'.join(buf))
            run.font.name = 'Consolas'
            run.font.size = Pt(10)
            if lang:
                p.paragraph_format.left_indent = Inches(0.2)
            continue

        # GFM Table
        if (stripped.startswith('|') and i + 1 < len(lines)
                and re.match(r'^\|[\s\-:|]+\|\s*$', lines[i + 1].strip())):
            header = [c.strip() for c in stripped.strip().strip('|').split('|')]
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                rows.append(cells)
                i += 1
            n = len(header)
            table = doc.add_table(rows=1 + len(rows), cols=n)
            table.style = 'Light Grid Accent 1'
            for j, h_text in enumerate(header):
                cell = table.cell(0, j)
                cell.text = ""
                _docx_fill_runs(cell.paragraphs[0], h_text, bold=True)
            for r_idx, row in enumerate(rows):
                row = (row + [''] * n)[:n]
                for j, cell_text in enumerate(row):
                    cell = table.cell(r_idx + 1, j)
                    cell.text = ""
                    _docx_fill_runs(cell.paragraphs[0], cell_text)
            continue

        # Horizontal rule
        if re.match(r'^(?:---+|\*\*\*+|___+)\s*$', stripped):
            p = doc.add_paragraph('_' * 60)
            p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
            i += 1
            continue

        # Bullet list
        bullet = re.match(r'^[-*+]\s+\[([ xX])\]\s+(.*)$', stripped)
        if bullet:
            mark = "☒" if bullet.group(1).lower() == 'x' else "☐"
            text = _docx_strip_inline(bullet.group(2))
            p = doc.add_paragraph(f"{mark} {text}")
            i += 1
            continue

        b = re.match(r'^[-*+]\s+(.*)$', stripped)
        if b:
            p = doc.add_paragraph(style='List Bullet')
            _docx_fill_runs(p, b.group(1))
            i += 1
            continue

        # Ordered list
        o = re.match(r'^\d+\.\s+(.*)$', stripped)
        if o:
            p = doc.add_paragraph(style='List Number')
            _docx_fill_runs(p, o.group(1))
            i += 1
            continue

        # Block quote
        if stripped.startswith('> '):
            buf = []
            while i < len(lines) and lines[i].strip().startswith('> '):
                buf.append(lines[i].strip()[2:])
                i += 1
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.4)
            _docx_fill_runs(p, ' '.join(buf))
            run = p.runs[0] if p.runs else p.add_run('')
            run.italic = True
            continue

        # Image
        img = re.match(r'^!\[([^\]]*)\]\(([^)\s]+)\)\s*$', stripped)
        if img:
            url = img.group(2)
            try:
                if os.path.exists(url):
                    doc.add_picture(url, width=Inches(5))
                else:
                    doc.add_paragraph(f"[Image: {url}]")
            except Exception:
                doc.add_paragraph(f"[Image: {url}]")
            if img.group(1):
                cap = doc.add_paragraph(img.group(1))
                cap.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                if cap.runs:
                    cap.runs[0].italic = True
            i += 1
            continue

        # Dòng trống
        if not stripped:
            i += 1
            continue

        # Paragraph thường
        buf = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if not nxt:
                break
            if (re.match(r'^(#{1,6})\s', nxt) or re.match(r'^[-*+]\s', nxt)
                    or re.match(r'^\d+\.\s', nxt) or nxt.startswith('> ')
                    or nxt.startswith('|') or nxt.startswith('```')):
                break
            buf.append(nxt)
            i += 1
        p = doc.add_paragraph()
        _docx_fill_runs(p, ' '.join(buf))

    doc.save(path)
    return path


def _docx_strip_inline(text):
    """Bỏ ký hiệu markdown đơn giản trong heading/list text (giữ tiếng)."""
    text = re.sub(r'\*\*([^\*]+)\*\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    text = re.sub(r'\*([^\*]+)\*', r'\1', text)
    text = re.sub(r'(?<!_)_([^_]+)_(?!_)', r'\1', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    return text


def _docx_fill_runs(paragraph, text, bold=False):
    """Thêm text vào paragraph, hỗ trợ **bold**, *italic*, `code`, [link](url)."""
    if not text:
        return

    def apply_base(run):
        if bold:
            run.bold = True
        return run

    # Tokenize theo các marker phổ biến
    pattern = re.compile(
        r"(\*\*[^\*\n]+?\*\*|__[^_\n]+?__|"
        r"(?<![\*])\*[^\*\n]+?\*(?!\*)|(?<![_a-zA-Z])_[^_\n]+?_(?![_a-zA-Z])|"
        r"`[^`\n]+?`|\[[^\]]+?\]\([^)\s]+?\))"
    )
    parts = pattern.split(text)
    for part in parts:
        if not part:
            continue
        if part.startswith('**') and part.endswith('**'):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
            apply_base(run)
        elif part.startswith('__') and part.endswith('__'):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
            apply_base(run)
        elif part.startswith('*') and part.endswith('*') and len(part) > 2:
            run = paragraph.add_run(part[1:-1])
            run.italic = True
            apply_base(run)
        elif part.startswith('_') and part.endswith('_') and len(part) > 2:
            run = paragraph.add_run(part[1:-1])
            run.italic = True
            apply_base(run)
        elif part.startswith('`') and part.endswith('`'):
            from docx.shared import Pt
            run = paragraph.add_run(part[1:-1])
            run.font.name = 'Consolas'
            run.font.size = Pt(10)
            apply_base(run)
        elif part.startswith('[') and ']' in part and part.endswith(')'):
            m = re.match(r'\[([^\]]+)\]\(([^)\s]+)\)', part)
            if m:
                run = paragraph.add_run(m.group(1))
                run.font.color.rgb = _docx_link_color()
                run.underline = True
                apply_base(run)
            else:
                apply_base(paragraph.add_run(part))
        else:
            apply_base(paragraph.add_run(part))


def _docx_link_color():
    from docx.shared import RGBColor
    return RGBColor(0x25, 0x63, 0xEB)

"""Preview Markdown realtime: MathJax + TikZJax."""
import re
import html
import json

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QToolBar,
                              QToolButton, QVBoxLayout, QWidget)
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView


try:
    import markdown as md_lib
except ImportError:
    md_lib = None


HTML_BASE_CSS = """
body {
  font-family: 'Segoe UI', Arial, sans-serif;
  font-size: 16px;
  line-height: 1.65;
  color: #1f2937;
  padding: 24px 32px;
  background: #ffffff;
  margin: 0;
}
h1, h2, h3, h4 {
  color: #111;
  border-bottom: 1px solid #e5e7eb;
  padding-bottom: .25em;
  margin-top: 1.2em;
}
h1:first-child, h2:first-child { margin-top: 0; }
code {
  font-family: Consolas, 'Courier New', monospace;
  background: #f3f4f6;
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 0.95em;
}
pre {
  background: #f3f4f6;
  padding: 12px 14px;
  border-radius: 8px;
  overflow-x: auto;
}
pre code { background: transparent; padding: 0; }
blockquote {
  border-left: 4px solid #cbd5e1;
  color: #475569;
  margin: 12px 0;
  padding: 4px 14px;
  background: #f8fafc;
}
table {
  border-collapse: collapse;
  width: auto;
  margin: 14px 0;
}
th, td {
  border: 1px solid #d1d5db;
  padding: 8px 12px;
}
th { background: #f3f4f6; }
ul li input[type="checkbox"] { margin-right: 6px; }
.edraw-tikz-block {
  margin: 16px 0;
  padding: 10px;
  border: 1px dashed #d1d5db;
  border-radius: 10px;
  background: #fffefb;
  text-align: center;
  overflow-x: auto;
}
.edraw-tikz-block svg { max-width: 100%; height: auto; }
mjx-container[jax="CHTML"][display="true"],
mjx-container[jax="SVG"][display="true"] {
  margin: 1em 0;
  overflow-x: auto;
  overflow-y: hidden;
}
.error-box {
  background:#fef2f2; color:#991b1b;
  border:1px solid #fecaca; border-radius:10px;
  padding:12px; margin:12px 0; white-space:pre-wrap;
  font-family: Consolas, monospace; font-size:13px;
}
.emex-sync-highlight {
  outline: 2px solid #2563eb;
  outline-offset: 6px;
  border-radius: 6px;
  transition: outline-color .25s ease;
}
"""


def _mathjax_head(title="Preview"):
    return f"""<!doctype html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<script>
window.MathJax = {{
  tex: {{
    inlineMath: [['$','$'], ['\\\\(','\\\\)']],
    displayMath: [['$$','$$'], ['\\\\[','\\\\]']],
    processEscapes: true,
    processEnvironments: true,
    packages: {{'[+]': ['ams','color','cancel','mhchem','noerrors','noundefined','boldsymbol']}}
  }},
  options: {{
    skipHtmlTags: ['script','noscript','style','textarea','pre','code']
  }},
  startup: {{ typeset: false }}
}};
</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"></script>
<link rel="stylesheet" href="https://tikzjax.com/v1/fonts.css">
<script src="https://tikzjax.com/v1/tikzjax.js"></script>
<style>{HTML_BASE_CSS}</style>
</head><body>
"""


def _mathjax_tail(sync_script=""):
    return "\n" + sync_script + """
<script>
async function renderAll(){
  if (window.MathJax && MathJax.typesetPromise) {
    MathJax.typesetClear();
    await MathJax.typesetPromise();
  }
  if (window.tikzjax && typeof window.tikzjax.process === 'function') window.tikzjax.process();
  else if (typeof window.process_tikz === 'function') window.process_tikz();
  else window.dispatchEvent(new Event('load'));
}
renderAll();
</script>
</body></html>
"""


def _extract_tikz_blocks(source):
    blocks = []
    token = "%%EMEX_TIKZ_BLOCK_{idx}%%"

    def _replace(m):
        idx = len(blocks)
        blocks.append(m.group(1).strip())
        return f"\n\n{token.format(idx=idx)}\n\n"

    new_src = re.sub(r"```tikz\s*([\s\S]*?)```", _replace, source, flags=re.IGNORECASE)
    return new_src, blocks


def _tikz_to_html(code):
    safe = code.replace("</script", r"<\/script")
    return f"""<div class="edraw-tikz-block"><script type="text/tikz">
{safe}
</script></div>"""


def _source_block_lines(source, first_line=1):
    """Ước lượng dòng nguồn bắt đầu của từng block HTML chính."""
    lines = source.split('\n')
    starts = []
    i = 0

    def is_list(text):
        return bool(re.match(r'^([-*+]\s+(\[[ xX]\]\s+)?|\d+\.\s+)', text))

    def is_hr(text):
        return bool(re.match(r'^(?:---+|\*\*\*+|___+)\s*$', text))

    def is_table_start(index):
        return (lines[index].strip().startswith('|') and index + 1 < len(lines)
                and re.match(r'^\|[\s\-:|]+\|\s*$', lines[index + 1].strip()))

    def is_block_start(text, index):
        return (text.startswith('```') or re.match(r'^(#{1,6})\s+', text)
                or is_list(text) or text.startswith('> ') or is_hr(text)
                or text.startswith('$$') or text.startswith('|') or is_table_start(index))

    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue

        starts.append(first_line + i)

        if stripped.startswith('```'):
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                i += 1
            i += 1
            continue

        if is_table_start(i):
            i += 2
            while i < len(lines) and lines[i].strip().startswith('|'):
                i += 1
            continue

        if is_list(stripped):
            i += 1
            while i < len(lines) and (is_list(lines[i].strip()) or not lines[i].strip()):
                i += 1
            continue

        if stripped.startswith('> '):
            i += 1
            while i < len(lines) and lines[i].strip().startswith('> '):
                i += 1
            continue

        if stripped.startswith('$$'):
            i += 1
            while i < len(lines) and not lines[i].strip().endswith('$$'):
                i += 1
            i += 1
            continue

        if re.match(r'^(#{1,6})\s+', stripped) or is_hr(stripped):
            i += 1
            continue

        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if not nxt or is_block_start(nxt, i):
                break
            i += 1

    return starts


def _preview_sync_script(source, first_line=1):
    line_starts = json.dumps(_source_block_lines(source, first_line=first_line))
    return f"""
<script>
window.__emexSourceLines = {line_starts};
(function installEmexSync(){{
  const selector = 'h1,h2,h3,h4,h5,h6,p,pre,blockquote,table,ul,ol,hr,.edraw-tikz-block';
  const blocks = Array.from(document.body.children).filter(el => el.matches(selector));
  blocks.forEach((el, index) => {{
    const line = window.__emexSourceLines[index];
    if (line) el.dataset.sourceLine = String(line);
  }});
  document.addEventListener('dblclick', event => {{
    const target = event.target.closest('[data-source-line]');
    if (!target) return;
    event.preventDefault();
    window.location.href = 'emex-sync://line/' + target.dataset.sourceLine;
  }}, true);
}})();
</script>
"""


def markdown_to_html(source, enable_sync=False, first_line=1, title="Markdown Preview"):
    """Convert markdown source -> standalone HTML."""
    src_no_tikz, tikz_blocks = _extract_tikz_blocks(source)

    if md_lib is not None:
        body = md_lib.markdown(
            src_no_tikz,
            extensions=["extra", "tables", "fenced_code", "toc", "sane_lists"],
            output_format="html5",
        )
    else:
        body = "<pre>" + html.escape(src_no_tikz) + "</pre>"

    for i, code in enumerate(tikz_blocks):
        body = body.replace(f"%%EMEX_TIKZ_BLOCK_{i}%%", _tikz_to_html(code))

    sync_script = _preview_sync_script(source, first_line=first_line) if enable_sync else ""
    return _mathjax_head(title) + body + _mathjax_tail(sync_script)


class SyncPreviewPage(QWebEnginePage):
    source_line_requested = pyqtSignal(int)

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if url.scheme() == "emex-sync" and url.host() == "line":
            try:
                line = int(url.path().lstrip("/"))
            except ValueError:
                return False
            self.source_line_requested.emit(line)
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


class WebPreview(QWebEngineView):
    source_line_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        page = SyncPreviewPage(self)
        page.source_line_requested.connect(self.source_line_requested.emit)
        self.setPage(page)
        self.setHtml("<body style='font-family:sans-serif;color:#94a3b8;text-align:center;margin-top:80px'>"
                     "<p>Đang chuẩn bị preview...</p></body>")

    def render_markdown(self, source, base_url="", first_line=1, title="Markdown Preview"):
        text = markdown_to_html(source, enable_sync=True, first_line=first_line, title=title)
        if base_url:
            self.setHtml(text, QUrl.fromLocalFile(base_url + "/"))
        else:
            self.setHtml(text)

    def render_fragment(self, source, start_line, base_url=""):
        self.render_markdown(source, base_url=base_url, first_line=start_line,
                             title="Auto Preview")

    def scroll_to_source_line(self, line):
        line = max(1, int(line))
        script = f"""
(function(line) {{
  const blocks = Array.from(document.querySelectorAll('[data-source-line]'))
    .sort((a, b) => Number(a.dataset.sourceLine) - Number(b.dataset.sourceLine));
  let target = null;
  for (const block of blocks) {{
    const blockLine = Number(block.dataset.sourceLine);
    if (blockLine <= line) target = block;
    else break;
  }}
  if (!target && blocks.length) target = blocks[0];
  if (!target) return false;
  target.scrollIntoView({{behavior: 'smooth', block: 'center'}});
  document.querySelectorAll('.emex-sync-highlight')
    .forEach(el => el.classList.remove('emex-sync-highlight'));
  target.classList.add('emex-sync-highlight');
  setTimeout(() => target.classList.remove('emex-sync-highlight'), 1200);
  return true;
}})({line});
"""
        self.page().runJavaScript(script)


class PreviewPane(QWidget):
    """Toolbar nhỏ + WebPreview."""

    def __init__(self, main_window=None):
        super().__init__()
        self.setStyleSheet("QWidget{background:#ffffff;}")
        self.main_window = main_window

        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.toolbar.setStyleSheet(
            "QToolBar{background:#f8fafc;border-bottom:1px solid #e5e7eb;color:#111;}"
            "QToolBar QPushButton{background:#ffffff;color:#0f172a;border:1px solid #d1d5db;"
            "padding:4px 8px;border-radius:6px;margin:0 2px;min-width:28px;}"
            "QToolBar QPushButton:hover{background:#eff6ff;border-color:#2563eb;color:#1d4ed8;}"
            "QToolBar QToolButton{background:#ffffff;color:#0f172a;border:1px solid #d1d5db;"
            "padding:4px 8px;border-radius:6px;margin:0 2px;min-width:28px;}"
            "QToolBar QToolButton:hover{background:#eff6ff;border-color:#2563eb;color:#1d4ed8;}"
            "QToolBar QPushButton#compileButton{background:#2563eb;color:#ffffff;"
            "border:1px solid #2563eb;font-weight:700;padding:5px 10px;}"
            "QToolBar QPushButton#compileButton:hover{background:#1d4ed8;border-color:#1d4ed8;color:#ffffff;}"
            "QToolBar QPushButton#compileButton:disabled{background:#93c5fd;border-color:#93c5fd;color:#ffffff;}"
            "QLabel{color:#111;}")

        self.btn_compile = QPushButton("▶ Compile")
        self.btn_compile.setObjectName("compileButton")
        self.btn_compile.setToolTip("Compile preview (Ctrl+Enter)")
        self.btn_export = QToolButton()
        self.btn_export.setText("📤")
        self.btn_export.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.btn_export.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_export.setToolTip("Xuất tài liệu")
        self.mode_label = QLabel("Auto: đoạn hiện tại")
        self.mode_label.setVisible(False)
        self.mode_label.setStyleSheet("color:#475569;background:transparent;padding:0 8px;")
        self.btn_zoom_in = QPushButton("➕")
        self.btn_zoom_out = QPushButton("➖")
        self.btn_zoom_in.setFixedWidth(36)
        self.btn_zoom_out.setFixedWidth(36)

        self._spinner_index = 0
        self._spinner_frames = ["⟳", "↻", "⟳", "↺"]
        self._spinner_timer = QTimer(self)
        self._spinner_timer.setInterval(120)
        self._spinner_timer.timeout.connect(self._advance_compile_spinner)

        self.toolbar.addWidget(self.btn_compile)
        self.toolbar.addWidget(self.btn_export)
        self.toolbar.addSeparator()
        self.toolbar.addWidget(self.btn_zoom_out)
        self.toolbar.addWidget(self.btn_zoom_in)

        self.web = WebPreview(self)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.toolbar)
        lay.addWidget(self.web)

        self.btn_zoom_in.clicked.connect(self._zoom_in)
        self.btn_zoom_out.clicked.connect(self._zoom_out)

    def render(self, source, base_url="", mode="full", start_line=1):
        if mode == "fragment":
            self.mode_label.setText(f"Auto: dòng {start_line}")
            self.web.render_fragment(source, start_line, base_url=base_url)
        else:
            self.mode_label.setText("Compile: toàn tài liệu")
            self.web.render_markdown(source, base_url=base_url)

    def scroll_to_source_line(self, line):
        self.web.scroll_to_source_line(line)

    def set_compiling(self, active):
        if active:
            self._spinner_index = 0
            self.btn_compile.setEnabled(False)
            self._advance_compile_spinner()
            self._spinner_timer.start()
            return
        self._spinner_timer.stop()
        self.btn_compile.setEnabled(True)
        self.btn_compile.setText("▶ Compile")

    def _advance_compile_spinner(self):
        frame = self._spinner_frames[self._spinner_index % len(self._spinner_frames)]
        self.btn_compile.setText(f"{frame} Compile")
        self._spinner_index += 1

    def _zoom_in(self):
        self.web.setZoomFactor(min(3.0, self.web.zoomFactor() * 1.1))

    def _zoom_out(self):
        self.web.setZoomFactor(max(0.4, self.web.zoomFactor() * 0.9))

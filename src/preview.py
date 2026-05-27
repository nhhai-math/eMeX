"""Preview Markdown realtime: MathJax + TikZJax."""
import re
import html
import json
import os

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QToolBar,
                              QToolButton, QVBoxLayout, QWidget)
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView

from .i18n import t


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
img {
  max-width: 100%;
  height: auto;
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
.edraw-tikz-block:has(svg) .edraw-tikz-status {
  display: none;
}
.edraw-tikz-status {
  color: #64748b;
  font-size: 13px;
  font-family: 'Segoe UI', Arial, sans-serif;
}
.edraw-tikz-block.is-error {
  background:#fef2f2;
  border-color:#fecaca;
}
.edraw-tikz-block.is-error .edraw-tikz-status {
  color:#991b1b;
  white-space:pre-wrap;
}
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


def _mathjax_head(title=None):
    title = title or t("Xem trước")
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
    tail = """
<script>
window.__emexRenderState = 'pending';
function sleep(ms){ return new Promise(resolve => setTimeout(resolve, ms)); }
function tikzBlocks(){
  return Array.from(document.querySelectorAll('.edraw-tikz-block'));
}
function tikzEngineReady(){
  return !!((window.tikzjax && typeof window.tikzjax.process === 'function') ||
            typeof window.process_tikz === 'function');
}
function runTikzProcessor(){
  if (window.tikzjax && typeof window.tikzjax.process === 'function') {
    window.tikzjax.process();
    return true;
  }
  if (typeof window.process_tikz === 'function') {
    window.process_tikz();
    return true;
  }
  window.dispatchEvent(new Event('load'));
  return false;
}
function refreshTikzStatus(){
  tikzBlocks().forEach(block => {
    if (block.querySelector('svg')) {
      block.querySelectorAll('.edraw-tikz-status').forEach(status => status.remove());
      block.classList.remove('is-error');
    }
  });
}
function installTikzStatusObserver(){
  if (window.__emexTikzStatusObserver) return;
  window.__emexTikzStatusObserver = new MutationObserver(() => refreshTikzStatus());
  window.__emexTikzStatusObserver.observe(document.body, {
    childList: true,
    subtree: true
  });
}
function setTikzError(message){
  tikzBlocks().forEach(block => {
    if (block.querySelector('svg')) return;
    block.classList.add('is-error');
    let status = block.querySelector('.edraw-tikz-status');
    if (!status) {
      status = document.createElement('div');
      status.className = 'edraw-tikz-status';
      block.prepend(status);
    }
    status.textContent = message;
  });
}
async function waitForTikz(timeoutMs){
  const blocks = tikzBlocks();
  if (!blocks.length) return;
  runTikzProcessor();
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    refreshTikzStatus();
    const rendered = blocks.every(block => block.querySelector('svg'));
    if (rendered) return;
    await sleep(150);
  }
  refreshTikzStatus();
  if (blocks.every(block => block.querySelector('svg'))) return;
  const message = tikzEngineReady()
    ? '__TIKZ_TIMEOUT__'
    : '__TIKZ_LOAD_ERROR__';
  setTikzError(message);
  throw new Error(message);
}
async function renderAll(){
  try {
    installTikzStatusObserver();
    if (window.MathJax && MathJax.typesetPromise) {
      MathJax.typesetClear();
      await MathJax.typesetPromise();
    }
    await waitForTikz(10000);
    refreshTikzStatus();
    window.__emexRenderState = 'done';
  } catch (err) {
    refreshTikzStatus();
    window.__emexRenderState = 'error';
    window.__emexRenderError = String(err);
  }
}
renderAll();
</script>
</body></html>
"""
    tail = tail.replace("__TIKZ_TIMEOUT__", t("TikZ kết xuất quá lâu hoặc mã TikZ có lỗi."))
    tail = tail.replace("__TIKZ_LOAD_ERROR__", t("Không tải được TikZJax. Kiểm tra kết nối mạng hoặc quyền tải CDN."))
    return "\n" + sync_script + tail


def _extract_tikz_blocks(source):
    blocks = []
    token = "<!--EMEX_TIKZ_BLOCK_{idx}-->"

    def _replace(m):
        idx = len(blocks)
        blocks.append(m.group(1).strip())
        return f"\n\n{token.format(idx=idx)}\n\n"

    new_src = re.sub(r"```tikz\s*([\s\S]*?)```", _replace, source, flags=re.IGNORECASE)
    return new_src, blocks


def _tikz_to_html(code):
    safe = code.replace("</script", r"<\/script")
    return f"""<div class="edraw-tikz-block"><div class="edraw-tikz-status">{html.escape(t("Đang kết xuất TikZ..."))}</div><script type="text/tikz">
{safe}
</script></div>"""


def _local_image_src_to_file_url(src):
    """Convert Windows local image paths from Markdown into browser-safe file URLs."""
    src = html.unescape(src or "").strip()
    if not src:
        return src
    if re.match(r"^[a-zA-Z]:[\\/]", src) or src.startswith("\\\\"):
        return bytes(QUrl.fromLocalFile(src).toEncoded()).decode("ascii")
    return src


def _normalize_local_image_sources(body):
    def replace_src(match):
        prefix, quote, src = match.group(1), match.group(2), match.group(3)
        normalized = _local_image_src_to_file_url(src)
        return f"{prefix}{quote}{html.escape(normalized, quote=True)}{quote}"

    return re.sub(r"(<img\b[^>]*\bsrc=)(['\"])(.*?)(?:\2)",
                  replace_src, body, flags=re.IGNORECASE)


def _apply_strikethrough_markup(source):
    """Support GitHub-style ~~text~~ without touching code spans/fences."""
    protected = []

    def stash(match):
        token = f"\x00EMEX_CODE_{len(protected)}\x00"
        protected.append(match.group(0))
        return token

    text = re.sub(r"(?ms)^([`~]{3,})[^\n]*\n.*?^\1[ \t]*$", stash, source)
    text = re.sub(r"(`+)([^\n]*?)(?<!`)\1(?!`)", stash, text)

    def replace_strike(match):
        return "<s>" + html.escape(match.group(1), quote=False) + "</s>"

    text = re.sub(r"(?<!~)~~(?=\S)(.+?)(?<=\S)~~(?!~)", replace_strike, text)
    for index, original in enumerate(protected):
        text = text.replace(f"\x00EMEX_CODE_{index}\x00", original)
    return text


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


def markdown_to_html(source, enable_sync=False, first_line=1, title=None):
    """Convert markdown source -> standalone HTML."""
    title = title or t("Xem trước")
    src_no_tikz, tikz_blocks = _extract_tikz_blocks(source)
    src_no_tikz = _apply_strikethrough_markup(src_no_tikz)

    if md_lib is not None:
        body = md_lib.markdown(
            src_no_tikz,
            extensions=["extra", "tables", "fenced_code", "toc", "sane_lists"],
            output_format="html5",
        )
    else:
        body = "<pre>" + html.escape(src_no_tikz) + "</pre>"

    for i, code in enumerate(tikz_blocks):
        body = body.replace(f"<!--EMEX_TIKZ_BLOCK_{i}-->", _tikz_to_html(code))

    body = _normalize_local_image_sources(body)
    sync_script = _preview_sync_script(source, first_line=first_line) if enable_sync else ""
    return _mathjax_head(title) + body + _mathjax_tail(sync_script)


def markdown_fragment_to_html(source):
    """Convert one markdown block to HTML. MathJax is applied in-place later."""
    source = _apply_strikethrough_markup(source)
    if md_lib is not None:
        body = md_lib.markdown(
            source,
            extensions=["extra", "tables", "fenced_code", "toc", "sane_lists"],
            output_format="html5",
        )
    else:
        body = "<pre>" + html.escape(source) + "</pre>"
    return _normalize_local_image_sources(body)


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
        self._configure_web_settings()
        self.setHtml("<body style='font-family:sans-serif;color:#94a3b8;text-align:center;margin-top:80px'>"
                     f"<p>{html.escape(t('Đang chuẩn bị xem trước...'))}</p></body>")

    def _configure_web_settings(self):
        settings = self.settings()
        for attribute_name in (
            "JavascriptEnabled",
            "LocalContentCanAccessRemoteUrls",
            "LocalContentCanAccessFileUrls",
        ):
            try:
                attribute = getattr(QWebEngineSettings.WebAttribute, attribute_name)
            except AttributeError:
                continue
            settings.setAttribute(attribute, True)

    def render_markdown(self, source, base_url="", first_line=1, title=None):
        text = markdown_to_html(source, enable_sync=True, first_line=first_line, title=title)
        base_path = base_url or os.getcwd()
        self.setHtml(text, QUrl.fromLocalFile(base_path + "/"))

    def render_fragment(self, source, start_line, base_url=""):
        self.render_markdown(source, base_url=base_url, first_line=start_line,
                             title=t("Xem trước"))

    def update_fragment(self, source, start_line):
        fragment = markdown_fragment_to_html(source)
        script = f"""
(async function(line, fragmentHtml) {{
  try {{
    window.__emexRenderState = 'pending';
    const blocks = Array.from(document.querySelectorAll('[data-source-line]'))
      .sort((a, b) => Number(a.dataset.sourceLine) - Number(b.dataset.sourceLine));
    const target = blocks.find(el => Number(el.dataset.sourceLine) === line);
    if (target && target.classList.contains('edraw-tikz-block')) {{
      window.__emexRenderState = 'done';
      return false;
    }}
    const template = document.createElement('template');
    template.innerHTML = fragmentHtml.trim();
    const nodes = Array.from(template.content.children);
    if (!nodes.length) {{
      window.__emexRenderState = 'done';
      return false;
    }}
    const replacement = nodes.length === 1 ? nodes[0] : document.createElement('div');
    if (nodes.length > 1) nodes.forEach(node => replacement.appendChild(node));
    replacement.dataset.sourceLine = String(line);
    if (target) {{
      if (window.MathJax && MathJax.typesetClear) MathJax.typesetClear([target]);
      target.replaceWith(replacement);
    }} else {{
      let previous = null;
      for (const block of blocks) {{
        if (Number(block.dataset.sourceLine) < line) previous = block;
        else break;
      }}
      if (previous) previous.insertAdjacentElement('afterend', replacement);
      else document.body.prepend(replacement);
    }}
    if (window.MathJax && MathJax.typesetPromise) {{
      await MathJax.typesetPromise([replacement]);
    }}
    window.__emexRenderState = 'done';
    return true;
  }} catch (err) {{
    window.__emexRenderState = 'error';
    window.__emexRenderError = String(err);
    return false;
  }}
}})({int(start_line)}, {json.dumps(fragment)});
"""
        self.page().runJavaScript(script)

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

        self.btn_compile = QPushButton("▶ " + t("Biên dịch"))
        self.btn_compile.setObjectName("compileButton")
        self.btn_compile.setToolTip(t("Biên dịch xem trước (Ctrl+Enter)"))
        self.btn_export = QToolButton()
        self.btn_export.setText("📤")
        self.btn_export.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.btn_export.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_export.setToolTip(t("Xuất tài liệu"))
        self._mode_label_key = "Tự động: đoạn hiện tại"
        self._mode_label_kwargs = {}
        self.mode_label = QLabel(t(self._mode_label_key))
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
            self._set_mode_label("Tự động: dòng {line}", line=start_line)
            self.web.render_fragment(source, start_line, base_url=base_url)
        else:
            self._set_mode_label("Biên dịch: toàn tài liệu")
            self.web.render_markdown(source, base_url=base_url)

    def update_fragment(self, source, start_line):
        self._set_mode_label("Tự động: dòng {line}", line=start_line)
        self.web.update_fragment(source, start_line)

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
        self.btn_compile.setText("▶ " + t("Biên dịch"))

    def retranslate_ui(self):
        """Cập nhật lại các nhãn trong khung xem trước."""
        if not self._spinner_timer.isActive():
            self.btn_compile.setText("▶ " + t("Biên dịch"))
        self.btn_compile.setToolTip(t("Biên dịch xem trước (Ctrl+Enter)"))
        self.btn_export.setToolTip(t("Xuất tài liệu"))
        self._refresh_mode_label()

    def _set_mode_label(self, key, **kwargs):
        self._mode_label_key = key
        self._mode_label_kwargs = kwargs
        self._refresh_mode_label()

    def _refresh_mode_label(self):
        self.mode_label.setText(t(self._mode_label_key, **self._mode_label_kwargs))

    def _advance_compile_spinner(self):
        frame = self._spinner_frames[self._spinner_index % len(self._spinner_frames)]
        self.btn_compile.setText(f"{frame} {t('Biên dịch')}")
        self._spinner_index += 1

    def _zoom_in(self):
        self.web.setZoomFactor(min(3.0, self.web.zoomFactor() * 1.1))

    def _zoom_out(self):
        self.web.setZoomFactor(max(0.4, self.web.zoomFactor() * 0.9))

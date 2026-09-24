"""Preview Markdown realtime: MathJax + TikZJax."""
import hashlib
import re
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from PyQt6.QtCore import Qt, QTimer, QUrl, QSize, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QMenu, QPushButton, QSizePolicy,
                              QToolBar, QToolButton, QVBoxLayout, QWidget)
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView

from .config import CONFIG_DIR, ROOT_DIR
from .i18n import t
from .text_normalizer import normalize_markdown_for_compile
from .toolbar_icons import toolbar_icon
from .translation import (COMPILE_TRANSLATION_LANGUAGES, COMPILE_TRANSLATION_TOOLS,
                          compile_language_label, normalize_compile_language,
                          normalize_translation_tool, translation_tool_label)


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
.edraw-tikz-image {
  display: block;
  max-width: 100%;
  height: auto;
  margin: 0 auto;
}
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
.emex-math-block {
  margin: 1em 0;
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
body.emex-justify-text p,
body.emex-justify-text li {
  text-align: justify;
  text-justify: inter-word;
}
"""



_TIKZJAX_HTTPD = None
_TIKZJAX_BASE_URL = ""
_TIKZJAX_LOCK = threading.Lock()
_DEFAULT_TIKZ_LIBRARIES = "positioning,arrows.meta,calc,fit,backgrounds,shapes.geometric"
_TIKZ_RENDER_CACHE = os.path.join(CONFIG_DIR, "tikz_image_cache")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_LIST_ITEM_RE = re.compile(r"^([ \t]*)([-*+]\s+)(.*)$")
_SCHEDULE_TIME_RE = re.compile(
    r"(?:\*\*)?\d{1,2}:\d{2}\s*[-–—]\s*\d{1,2}:\d{2}(?:\*\*)?"
)
_ITALIC_LIST_NOTE_RE = re.compile(r"^(?:\*[^*\s](?:.*\S)?\*|_[^_\s](?:.*\S)?_)$")
_INLINE_MATH_TOKEN = "@@EMEX_INLINE_MATH_{idx}@@"


class _TikzJaxAssetHandler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".gz": "application/gzip",
        ".ttf": "font/ttf",
        ".wasm": "application/wasm",
    }

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, _format, *args):
        return

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return


def _tikzjax_asset_root():
    candidates = [os.path.join(ROOT_DIR, "vendor", "tikzjax")]
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        candidates.append(os.path.join(meipass, "vendor", "tikzjax"))
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        candidates.extend([
            os.path.join(exe_dir, "vendor", "tikzjax"),
            os.path.join(exe_dir, "_internal", "vendor", "tikzjax"),
        ])

    for path in candidates:
        js_path = os.path.join(path, "v1", "tikzjax.js")
        if os.path.exists(js_path):
            return path
    return ""


def _ensure_tikzjax_server():
    global _TIKZJAX_HTTPD, _TIKZJAX_BASE_URL
    if _TIKZJAX_BASE_URL:
        return _TIKZJAX_BASE_URL

    with _TIKZJAX_LOCK:
        if _TIKZJAX_BASE_URL:
            return _TIKZJAX_BASE_URL
        root = _tikzjax_asset_root()
        if not root:
            return ""
        handler = partial(_TikzJaxAssetHandler, directory=root)
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        except OSError:
            return ""
        thread = threading.Thread(
            target=httpd.serve_forever,
            name="eMeX TikZJax assets",
            daemon=True,
        )
        thread.start()
        _TIKZJAX_HTTPD = httpd
        _TIKZJAX_BASE_URL = f"http://127.0.0.1:{httpd.server_port}"
        return _TIKZJAX_BASE_URL


def _mathjax_head(title=None, justify_text=False):
    title = title or t("Xem trước")
    tikz_base = _ensure_tikzjax_server()
    if tikz_base:
        tikz_assets = (
            "<script>"
            "window.__emexTikzScriptLoaded=false;"
            "window.__emexTikzScriptError=false;"
            "</script>\n"
            f'<link rel="stylesheet" href="{html.escape(tikz_base, quote=True)}/v1/fonts.css">\n'
            f'<script src="{html.escape(tikz_base, quote=True)}/v1/tikzjax.js" '
            'onload="window.__emexTikzScriptLoaded=true" '
            'onerror="window.__emexTikzScriptError=true"></script>'
        )
    else:
        tikz_assets = "<script>window.__emexTikzLocalMissing = true;</script>"
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
{tikz_assets}
<style>{HTML_BASE_CSS}</style>
</head><body class="{'emex-justify-text' if justify_text else ''}">
"""


def _mathjax_tail(sync_script=""):
    tail = """
<script>
window.__emexRenderState = 'pending';
function sleep(ms){ return new Promise(resolve => setTimeout(resolve, ms)); }
function tikzBlocks(){
  return Array.from(document.querySelectorAll('.edraw-tikz-block'));
}
function tikzBlockRendered(block){
  return !!(block.querySelector('svg') || block.querySelector('img.edraw-tikz-image'));
}
function tikzEngineReady(){
  return !!((window.tikzjax && typeof window.tikzjax.process === 'function') ||
            typeof window.process_tikz === 'function');
}
function runTikzProcessor(){
  if (window.__emexTikzScriptError) return false;
  window.__emexTikzProcessingRequested = true;
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
    if (tikzBlockRendered(block)) {
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
    if (tikzBlockRendered(block)) return;
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
  refreshTikzStatus();
  if (blocks.every(tikzBlockRendered)) return;
  runTikzProcessor();
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    refreshTikzStatus();
    const rendered = blocks.every(tikzBlockRendered);
    if (rendered) return;
    await sleep(150);
  }
  refreshTikzStatus();
  if (blocks.every(tikzBlockRendered)) return;
  const message = window.__emexTikzLocalMissing
    ? '__TIKZ_LOCAL_MISSING__'
    : (window.__emexTikzScriptError || window.__emexTikzScriptLoaded === false
      ? '__TIKZ_LOAD_ERROR__'
      : '__TIKZ_TIMEOUT__');
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
    await waitForTikz(45000);
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
    tail = tail.replace("__TIKZ_LOCAL_MISSING__", t("Thiếu TikZJax local. Kiểm tra thư mục vendor/tikzjax."))
    tail = tail.replace("__TIKZ_LOAD_ERROR__", t("Không tải được TikZJax local. Kiểm tra dịch vụ nội bộ hoặc thư mục vendor/tikzjax."))
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
    image_path = _render_tikz_with_pdflatex_image(code)
    if image_path:
        image_src = bytes(QUrl.fromLocalFile(image_path).toEncoded()).decode("ascii")
        return f"""<div class="edraw-tikz-block edraw-tikz-pdflatex-image">
<img class="edraw-tikz-image" src="{html.escape(image_src, quote=True)}" alt="TikZ">
</div>"""

    if "\\usetikzlibrary" not in code and "\\begin{document}" not in code:
        code = f"\\usetikzlibrary{{{_DEFAULT_TIKZ_LIBRARIES}}}\n{code}"
    safe = code.replace("</script", r"<\/script")
    return f"""<div class="edraw-tikz-block"><div class="edraw-tikz-status">{html.escape(t("Đang kết xuất TikZ..."))}</div><script type="text/tikz">
{safe}
</script></div>"""


def _render_tikz_with_pdflatex_image(code):
    pdflatex = shutil.which("pdflatex")
    converter = shutil.which("pdftocairo") or shutil.which("magick")
    if not pdflatex or not converter:
        return None

    tex_source = _wrap_tikz_for_pdflatex(code)
    cache_key = hashlib.sha256(("pdflatex-png-v2\n" + tex_source).encode("utf-8")).hexdigest()
    try:
        os.makedirs(_TIKZ_RENDER_CACHE, exist_ok=True)
    except OSError:
        return None
    cached_png = os.path.join(_TIKZ_RENDER_CACHE, cache_key + ".png")
    if os.path.exists(cached_png):
        return cached_png

    try:
        with tempfile.TemporaryDirectory(prefix="emex-tikz-", dir=CONFIG_DIR) as tmp:
            tex_path = os.path.join(tmp, "tikz.tex")
            pdf_path = os.path.join(tmp, "tikz.pdf")
            png_path = os.path.join(tmp, "tikz.png")
            with open(tex_path, "w", encoding="utf-8") as f:
                f.write(tex_source)

            tex_cmd = [
                pdflatex,
                "-interaction=nonstopmode",
                "-halt-on-error",
                "tikz.tex",
            ]
            subprocess.run(
                tex_cmd,
                cwd=tmp,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=45,
                check=True,
                **_subprocess_hidden_kwargs(),
            )
            if not os.path.exists(pdf_path):
                return None

            if os.path.basename(converter).lower().startswith("pdftocairo"):
                convert_cmd = [
                    converter,
                    "-png",
                    "-singlefile",
                    "-r",
                    "220",
                    "tikz.pdf",
                    "tikz",
                ]
            else:
                convert_cmd = [
                    converter,
                    "-density",
                    "220",
                    "tikz.pdf",
                    "-quality",
                    "95",
                    "tikz.png",
                ]
            subprocess.run(
                convert_cmd,
                cwd=tmp,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=45,
                check=True,
                **_subprocess_hidden_kwargs(),
            )
            if not os.path.exists(png_path):
                return None
            shutil.copy2(png_path, cached_png)
            return cached_png
    except Exception:
        return None


def _wrap_tikz_for_pdflatex(code):
    if "\\begin{document}" in code:
        return code

    library_lines = re.findall(
        r"^\s*\\usetikzlibrary\s*\{[^}]*\}\s*$",
        code,
        flags=re.MULTILINE,
    )
    body = re.sub(
        r"^\s*\\usetikzlibrary\s*\{[^}]*\}\s*$",
        "",
        code,
        flags=re.MULTILINE,
    ).strip()
    libraries = "\n".join(library_lines)
    if not libraries:
        libraries = f"\\usetikzlibrary{{{_DEFAULT_TIKZ_LIBRARIES}}}"

    return f"""\\documentclass[tikz,border=2pt]{{standalone}}
\\usepackage[utf8]{{inputenc}}
\\usepackage[T5]{{fontenc}}
\\usepackage[vietnamese]{{babel}}
\\usepackage{{amsmath,amssymb}}
{libraries}
\\begin{{document}}
{body}
\\end{{document}}
"""


def _subprocess_hidden_kwargs():
    if sys.platform != "win32":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {
        "startupinfo": startupinfo,
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
    }


def _extract_display_math_blocks(source):
    blocks = []
    lines = source.split("\n")
    out = []
    i = 0
    in_fence = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if re.match(r"^\s*(```|~~~)", stripped):
            in_fence = not in_fence
            out.append(line)
            i += 1
            continue

        if in_fence or not stripped.startswith("$$"):
            out.append(line)
            i += 1
            continue

        block_lines = []
        first = line[line.find("$$") + 2:]
        if first.strip().endswith("$$") and first.strip() != "$$":
            block_lines.append(first[:first.rfind("$$")])
            i += 1
        else:
            if first.strip():
                block_lines.append(first)
            i += 1
            while i < len(lines):
                candidate = lines[i]
                candidate_stripped = candidate.strip()
                if candidate_stripped.endswith("$$"):
                    end_index = candidate.rfind("$$")
                    if candidate[:end_index].strip():
                        block_lines.append(candidate[:end_index])
                    i += 1
                    break
                block_lines.append(candidate)
                i += 1

        idx = len(blocks)
        blocks.append("\n".join(block_lines).strip())
        out.append(f"@@EMEX_MATH_BLOCK_{idx}@@")

    return "\n".join(out), blocks


def _math_to_html(code):
    safe = html.escape(code, quote=False)
    return f"""<div class="emex-math-block">$$
{safe}
$$</div>"""


def _restore_html_block(body, token, replacement):
    pattern = rf"<p>\s*{re.escape(token)}\s*</p>"
    body = re.sub(pattern, lambda _match: replacement, body)
    return body.replace(token, replacement)


def _extract_inline_math_spans(source):
    spans = []
    out_lines = []
    in_fence = False

    for line in source.split("\n"):
        stripped = line.strip()
        if _FENCE_RE.match(stripped):
            in_fence = not in_fence
            out_lines.append(line)
            continue

        if in_fence:
            out_lines.append(line)
            continue

        out = []
        i = 0
        code_ticks = 0
        while i < len(line):
            if line[i] == "`":
                j = i
                while j < len(line) and line[j] == "`":
                    j += 1
                ticks = j - i
                if code_ticks == 0:
                    code_ticks = ticks
                elif ticks == code_ticks:
                    code_ticks = 0
                out.append(line[i:j])
                i = j
                continue

            if code_ticks:
                out.append(line[i])
                i += 1
                continue

            if line.startswith(r"\(", i):
                end = line.find(r"\)", i + 2)
                if end != -1:
                    token = _INLINE_MATH_TOKEN.format(idx=len(spans))
                    spans.append(line[i:end + 2])
                    out.append(token)
                    i = end + 2
                    continue

            if line[i] == "$" and not _is_escaped(line, i):
                if i + 1 < len(line) and line[i + 1] == "$":
                    out.append(line[i])
                    i += 1
                    continue
                end = _find_inline_dollar_end(line, i + 1)
                if end is not None:
                    token = _INLINE_MATH_TOKEN.format(idx=len(spans))
                    spans.append(line[i:end + 1])
                    out.append(token)
                    i = end + 1
                    continue

            out.append(line[i])
            i += 1

        out_lines.append("".join(out))

    return "\n".join(out_lines), spans


def _restore_inline_math_spans(body, spans):
    for index, span in enumerate(spans):
        body = body.replace(_INLINE_MATH_TOKEN.format(idx=index),
                            html.escape(span, quote=False))
    return body


def _find_inline_dollar_end(line, start):
    i = start
    while i < len(line):
        if line[i] == "$" and not _is_escaped(line, i):
            if i + 1 < len(line) and line[i + 1] == "$":
                return None
            if i == start:
                return None
            return i
        i += 1
    return None


def _is_escaped(text, index):
    slash_count = 0
    i = index - 1
    while i >= 0 and text[i] == "\\":
        slash_count += 1
        i -= 1
    return slash_count % 2 == 1


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


def _normalize_schedule_note_indents(source):
    """Treat italic note bullets after timed agenda items as nested notes.

    Users often type agenda notes as ``* *MC giới thiệu...*`` directly after a
    timed bullet. Python-Markdown sees that as a sibling item, so we add the
    four-space Markdown child indent before rendering. This keeps line numbers
    intact and only targets a narrow agenda pattern.
    """
    lines = source.split("\n")
    out = []
    in_fence = False
    active_schedule_indent = None

    for line in lines:
        stripped = line.strip()
        if _FENCE_RE.match(stripped):
            in_fence = not in_fence
            out.append(line)
            active_schedule_indent = None
            continue

        if in_fence:
            out.append(line)
            continue

        match = _LIST_ITEM_RE.match(line)
        if not match:
            out.append(line)
            if stripped:
                active_schedule_indent = None
            continue

        indent, marker, body = match.groups()
        body_stripped = body.strip()
        if active_schedule_indent == indent and _ITALIC_LIST_NOTE_RE.match(body_stripped):
            out.append(f"{indent}    {marker}{body_stripped}")
            continue

        out.append(line)
        active_schedule_indent = indent if _SCHEDULE_TIME_RE.search(body_stripped) else None

    return "\n".join(out)


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
  const selector = 'h1,h2,h3,h4,h5,h6,p,pre,blockquote,table,ul,ol,hr,.edraw-tikz-block,.emex-math-block';
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


def markdown_to_html(source, enable_sync=False, first_line=1, title=None,
                     justify_text=False):
    """Convert markdown source -> standalone HTML."""
    title = title or t("Xem trước")
    source = normalize_markdown_for_compile(source)
    src_no_tikz, tikz_blocks = _extract_tikz_blocks(source)
    src_no_tikz, math_blocks = _extract_display_math_blocks(src_no_tikz)
    src_no_tikz = _normalize_schedule_note_indents(src_no_tikz)
    src_no_tikz = _apply_strikethrough_markup(src_no_tikz)
    src_no_tikz, inline_math_spans = _extract_inline_math_spans(src_no_tikz)

    if md_lib is not None:
        body = md_lib.markdown(
            src_no_tikz,
            extensions=["extra", "tables", "fenced_code", "toc", "sane_lists"],
            output_format="html5",
        )
    else:
        body = "<pre>" + html.escape(src_no_tikz) + "</pre>"

    for i, code in enumerate(tikz_blocks):
        body = _restore_html_block(body, f"<!--EMEX_TIKZ_BLOCK_{i}-->", _tikz_to_html(code))
    for i, code in enumerate(math_blocks):
        body = _restore_html_block(body, f"@@EMEX_MATH_BLOCK_{i}@@", _math_to_html(code))

    body = _restore_inline_math_spans(body, inline_math_spans)
    body = _normalize_local_image_sources(body)
    sync_script = _preview_sync_script(source, first_line=first_line) if enable_sync else ""
    return _mathjax_head(title, justify_text=justify_text) + body + _mathjax_tail(sync_script)


def markdown_fragment_to_html(source):
    """Convert one markdown block to HTML. MathJax is applied in-place later."""
    source = normalize_markdown_for_compile(source)
    source, math_blocks = _extract_display_math_blocks(source)
    source = _normalize_schedule_note_indents(source)
    source = _apply_strikethrough_markup(source)
    source, inline_math_spans = _extract_inline_math_spans(source)
    if md_lib is not None:
        body = md_lib.markdown(
            source,
            extensions=["extra", "tables", "fenced_code", "toc", "sane_lists"],
            output_format="html5",
        )
    else:
        body = "<pre>" + html.escape(source) + "</pre>"
    for i, code in enumerate(math_blocks):
        body = _restore_html_block(body, f"@@EMEX_MATH_BLOCK_{i}@@", _math_to_html(code))
    body = _restore_inline_math_spans(body, inline_math_spans)
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
        self._justify_text = False
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
        text = markdown_to_html(
            source,
            enable_sync=True,
            first_line=first_line,
            title=title,
            justify_text=self._justify_text,
        )
        base_path = base_url or os.getcwd()
        self.setHtml(text, QUrl.fromLocalFile(base_path + "/"))

    def set_justify_text(self, enabled):
        self._justify_text = bool(enabled)
        class_name = "emex-justify-text"
        enabled_js = "true" if self._justify_text else "false"
        self.page().runJavaScript(
            f"document.body && document.body.classList.toggle('{class_name}', {enabled_js});"
        )

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

    translation_changed = pyqtSignal()
    copy_png_requested = pyqtSignal()
    copy_pdf_requested = pyqtSignal()
    quick_open_pdf_requested = pyqtSignal()

    def __init__(self, main_window=None):
        super().__init__()
        self.setStyleSheet("QWidget{background:#ffffff;}")
        self.main_window = main_window

        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.toolbar.setObjectName("previewToolBar")
        self.toolbar.setStyleSheet(
            "QToolBar#previewToolBar{background:#ffffff;border:0;"
            "border-bottom:1px solid #e5e7eb;spacing:2px;padding:5px 8px;}"
            "QToolBar#previewToolBar QPushButton, QToolBar#previewToolBar QToolButton{"
            "background:transparent;color:#475569;border:1px solid transparent;"
            "border-radius:8px;padding:0;margin:0;}"
            "QToolBar#previewToolBar QPushButton:hover,"
            "QToolBar#previewToolBar QToolButton:hover{background:#f1f5f9;color:#0f172a;}"
            "QToolBar#previewToolBar QPushButton:pressed,"
            "QToolBar#previewToolBar QToolButton:pressed{background:#dbeafe;"
            "border-color:#bfdbfe;}"
            "QToolBar#previewToolBar QToolButton::menu-indicator{image:none;width:0;}"
            "QToolBar#previewToolBar::separator{background:#e2e8f0;"
            "width:1px;margin:6px 7px;}")
        self.btn_compile = QPushButton()
        self.btn_compile.setObjectName("compileButton")
        self.btn_compile.setIcon(toolbar_icon("play"))
        self.btn_compile.setIconSize(QSize(20, 20))
        self.btn_compile.setToolTip(t("Biên dịch xem trước (Ctrl+Enter)"))
        self._translation_tool = "google"
        self._translation_language = "none"
        self._translation_actions = {}
        self.btn_translate = QToolButton()
        self.btn_translate.setObjectName("translateButton")
        self.btn_translate.setIcon(toolbar_icon("globe"))
        self.btn_translate.setIconSize(QSize(20, 20))
        self.btn_translate.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.btn_translate.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_translate.setMenu(self._build_translation_menu())
        self._refresh_translation_button()
        self.btn_export = QToolButton()
        self.btn_export.setIcon(toolbar_icon("upload"))
        self.btn_export.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.btn_export.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_export.setToolTip(t("Xuất tài liệu"))
        self.btn_copy_png = QToolButton()
        self.btn_copy_png.setObjectName("copyPngButton")
        self.btn_copy_png.setIcon(toolbar_icon("clipboard-image"))
        self.btn_copy_png.setIconSize(QSize(20, 20))
        self.btn_copy_png.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.btn_copy_png.setToolTip(t("Sao chép PNG để gửi nhanh"))
        self.btn_copy_png.clicked.connect(self.copy_png_requested.emit)
        self.btn_copy_pdf = QToolButton()
        self.btn_copy_pdf.setObjectName("copyPdfButton")
        self.btn_copy_pdf.setIcon(toolbar_icon("clipboard-file"))
        self.btn_copy_pdf.setIconSize(QSize(20, 20))
        self.btn_copy_pdf.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.btn_copy_pdf.setToolTip(t("Sao chép PDF để gửi nhanh"))
        self.btn_copy_pdf.clicked.connect(self.copy_pdf_requested.emit)
        self.btn_quick_open_pdf = QToolButton()
        self.btn_quick_open_pdf.setObjectName("quickOpenPdfButton")
        self.btn_quick_open_pdf.setIcon(toolbar_icon("file-output"))
        self.btn_quick_open_pdf.setIconSize(QSize(20, 20))
        self.btn_quick_open_pdf.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.btn_quick_open_pdf.setToolTip(t("Mở PDF bằng trình đọc mặc định"))
        self.btn_quick_open_pdf.clicked.connect(self.quick_open_pdf_requested.emit)
        self._mode_label_key = "Tự động: đoạn hiện tại"
        self._mode_label_kwargs = {}
        self.mode_label = QLabel(t(self._mode_label_key))
        self.mode_label.setVisible(False)
        self.mode_label.setStyleSheet("color:#475569;background:transparent;padding:0 8px;")
        self.btn_zoom_in = QPushButton()
        self.btn_zoom_in.setIcon(toolbar_icon("zoom-in"))
        self.btn_zoom_in.setToolTip(t("Phóng to xem trước"))
        self.btn_zoom_out = QPushButton()
        self.btn_zoom_out.setIcon(toolbar_icon("zoom-out"))
        self.btn_zoom_out.setToolTip(t("Thu nhỏ xem trước"))

        self._spinner_index = 0
        self._spinner_frames = ["⟳", "↻", "⟳", "↺"]
        self._spinner_timer = QTimer(self)
        self._spinner_timer.setInterval(120)
        self._spinner_timer.timeout.connect(self._advance_compile_spinner)

        self.toolbar.addWidget(self.btn_compile)
        self.toolbar.addWidget(self.btn_translate)
        self.toolbar.addWidget(self.btn_export)
        self.toolbar.addSeparator()
        self.toolbar.addWidget(self.btn_zoom_out)
        self.toolbar.addWidget(self.btn_zoom_in)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(spacer)
        self.toolbar.addWidget(self.btn_copy_png)
        self.toolbar.addWidget(self.btn_copy_pdf)
        self.toolbar.addWidget(self.btn_quick_open_pdf)

        self.web = WebPreview(self)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.toolbar)
        lay.addWidget(self.web)

        self.btn_zoom_in.clicked.connect(self._zoom_in)
        self.btn_zoom_out.clicked.connect(self._zoom_out)
        config = getattr(main_window, "editor_config", {})
        self.apply_toolbar_sizes(config.get("toolbar_icon_size", 22),
                                 config.get("toolbar_btn_padding", 6))

    def apply_toolbar_sizes(self, icon_size, padding):
        """Keep the preview controls the same size as the main toolbar."""
        icon_size = int(icon_size)
        button_size = max(28, icon_size + int(padding) * 2)
        self.toolbar.setIconSize(QSize(icon_size, icon_size))
        for button in (self.btn_compile, self.btn_translate, self.btn_export,
                       self.btn_zoom_out, self.btn_zoom_in, self.btn_copy_png,
                       self.btn_copy_pdf, self.btn_quick_open_pdf):
            button.setIconSize(QSize(icon_size, icon_size))
            button.setFixedSize(button_size, button_size)

    def set_justify_text(self, enabled):
        self.web.set_justify_text(enabled)

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

    def translation_tool(self):
        return normalize_translation_tool(self._translation_tool)

    def translation_tool_label(self):
        return translation_tool_label(self.translation_tool())

    def set_translation_tool(self, tool):
        self._translation_tool = normalize_translation_tool(tool)
        self._refresh_translation_button()

    def translation_language(self):
        return normalize_compile_language(self._translation_language)

    def translation_language_label(self):
        return compile_language_label(self.translation_language())

    def set_translation_language(self, language):
        self._translation_language = normalize_compile_language(language)
        self._refresh_translation_button()

    def set_compiling(self, active):
        self.btn_translate.setEnabled(not active)
        if active:
            self._spinner_index = 0
            self.btn_compile.setEnabled(False)
            self._advance_compile_spinner()
            self._spinner_timer.start()
            return
        self._spinner_timer.stop()
        self.btn_compile.setEnabled(True)
        self.btn_compile.setIcon(toolbar_icon("play"))

    def retranslate_ui(self):
        """Cập nhật lại các nhãn trong khung xem trước."""
        if not self._spinner_timer.isActive():
            self.btn_compile.setIcon(toolbar_icon("play"))
        self.btn_compile.setToolTip(t("Biên dịch xem trước (Ctrl+Enter)"))
        self._refresh_translation_button()

        self.btn_export.setToolTip(t("Xuất tài liệu"))
        self.btn_zoom_in.setToolTip(t("Phóng to xem trước"))
        self.btn_zoom_out.setToolTip(t("Thu nhỏ xem trước"))
        self.btn_copy_png.setToolTip(t("Sao chép PNG để gửi nhanh"))
        self.btn_copy_pdf.setToolTip(t("Sao chép PDF để gửi nhanh"))

        self.btn_quick_open_pdf.setToolTip(t("Mở PDF bằng trình đọc mặc định"))
        self._refresh_mode_label()

    def _build_translation_menu(self):
        menu = QMenu(self)
        none_action = QAction("None", self)
        none_action.setCheckable(True)
        none_action.triggered.connect(
            lambda _checked=False: self._set_translation_choice(self._translation_tool, "none"))
        menu.addAction(none_action)
        self._translation_actions[("none", "none")] = none_action
        menu.addSeparator()

        for tool_code, tool_label in COMPILE_TRANSLATION_TOOLS:
            submenu = menu.addMenu(tool_label)
            for language_code, language_label in COMPILE_TRANSLATION_LANGUAGES:
                if language_code == "none":
                    continue
                action = QAction(language_label, self)
                action.setCheckable(True)
                action.triggered.connect(
                    lambda _checked=False, tc=tool_code, lc=language_code:
                    self._set_translation_choice(tc, lc))
                submenu.addAction(action)
                self._translation_actions[(tool_code, language_code)] = action
        return menu

    def _set_translation_choice(self, tool, language):
        self._translation_tool = normalize_translation_tool(tool)
        self._translation_language = normalize_compile_language(language)
        self._refresh_translation_button()
        self.translation_changed.emit()

    def _refresh_translation_button(self):
        language = self.translation_language()
        tool = self.translation_tool()
        tool_text = "Google" if tool == "google" else translation_tool_label(tool)
        self.btn_translate.setToolTip(
            f"{t('Công cụ dịch khi biên dịch')}: {tool_text} / "
            f"{compile_language_label(language)}")
        for (action_tool, action_language), action in self._translation_actions.items():
            action.setChecked(
                (language == "none" and action_language == "none")
                or (tool == action_tool and language == action_language)
            )

    def _set_mode_label(self, key, **kwargs):
        self._mode_label_key = key
        self._mode_label_kwargs = kwargs
        self._refresh_mode_label()

    def _refresh_mode_label(self):
        self.mode_label.setText(t(self._mode_label_key, **self._mode_label_kwargs))

    def _advance_compile_spinner(self):
        frame_index = self._spinner_index % len(self._spinner_frames)
        self.btn_compile.setIcon(toolbar_icon("spinner", rotation=frame_index * 90))
        self._spinner_index += 1

    def _zoom_in(self):
        self.web.setZoomFactor(min(3.0, self.web.zoomFactor() * 1.1))

    def _zoom_out(self):
        self.web.setZoomFactor(max(0.4, self.web.zoomFactor() * 0.9))

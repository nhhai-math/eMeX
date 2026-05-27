"""Cấu hình, đường dẫn, defaults – eMeX (Markdown only)."""
import os
import json
import sys

APP_NAME = "eMeX"
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP_ICON_FILE = os.path.join(ROOT_DIR, "docs", "assets", "icon_eMeX.png")
APP_VERSION_FALLBACK = "2026.05.27.04"


def _read_app_version():
    """Read app version from bundled/source VERSION file.

    Release builds write this file from the Git tag, e.g. vYYYY.MM.DD.xx
    becomes YYYY.MM.DD.xx. Keeping runtime version data in a file prevents
    the updater from comparing a packaged release against a stale hard-coded
    value.
    """
    exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else ""
    candidates = [
        os.path.join(ROOT_DIR, "VERSION"),
        os.path.join(getattr(sys, "_MEIPASS", ""), "VERSION"),
        os.path.join(exe_dir, "VERSION") if exe_dir else "",
        os.path.join(exe_dir, "_internal", "VERSION") if exe_dir else "",
    ]
    for path in candidates:
        if not path:
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                version = f.read().strip()
        except OSError:
            continue
        if version.lower().startswith("v"):
            version = version[1:]
        if version:
            return version
    return APP_VERSION_FALLBACK


APP_VERSION = _read_app_version()

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".emex_editor")
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)

SESSION_FILE = os.path.join(CONFIG_DIR, "session.json")
AI_CONFIG_FILE = os.path.join(CONFIG_DIR, "ai_config.json")
EDITOR_CONFIG_FILE = os.path.join(CONFIG_DIR, "editor_config.json")
RECENT_FILES_FILE = os.path.join(CONFIG_DIR, "recent_files.json")
SNIPPETS_FILE = os.path.join(CONFIG_DIR, "user_snippets.json")
PAGE_TEMPLATES_FILE = os.path.join(CONFIG_DIR, "page_templates.json")

DEFAULT_EDITOR_CONFIG = {
    "language": "vi",
    "font_family": "Consolas" if sys.platform == "win32" else "Menlo",
    "font_size": 13,
    "tab_spaces": 2,
    "auto_pair": True,
    "wrap_lines": True,
    "show_line_numbers": True,
    "gemini_model": "gemini-2.5-flash",
    "gemini_models_cache": [],  # danh sách model đã tải về
    "auto_save": False,
    # UI size settings
    "toolbar_icon_size": 22,        # kích thước icon trên toolbar (px)
    "toolbar_btn_padding": 6,       # padding nút toolbar (px)
    "symbol_btn_size": 38,          # kích thước nút bảng ký hiệu (px)
    "symbol_btn_font_size": 13,     # cỡ chữ nút bảng ký hiệu (pt)
    "ui_preview_visible": True,
    "ui_palette_visible": True,
    "ui_ai_state": "closed",        # closed | compact
    "ui_main_splitter_sizes": [],
    "ui_left_splitter_sizes": [],
    "ui_window_geometry": [],
    "ui_window_maximized": False,
    "ui_zen_enabled": False,
}

# --------- Markdown snippets ---------
# Sau khi gõ 2 ký tự khoá (vd "h1", "code", "math") sẽ gợi ý expand.
MARKDOWN_TEMPLATES = {
    "h1": "# %|",
    "h2": "## %|",
    "h3": "### %|",
    "h4": "#### %|",
    "bold": "**%|**",
    "italic": "*%|*",
    "strike": "~~%|~~",
    "code": "`%|`",
    "codeblock": "```%|\n\n```",
    "py": "```python\n%|\n```",
    "js": "```javascript\n%|\n```",
    "bash": "```bash\n%|\n```",
    "link": "[%|]()",
    "image": "![%|]()",
    "ul": "- %|",
    "ol": "1. %|",
    "task": "- [ ] %|",
    "quote": "> %|",
    "hr": "\n---\n",
    "table": "| %| | Cột 2 |\n|------|------|\n|      |      |",
    "math": "$%|$",
    "mathblock": "$$\n%|\n$$",
    "tikz": "```tikz\n\\begin{tikzpicture}\n%|\n\\end{tikzpicture}\n```",
    # Một vài lệnh toán hay dùng bên trong $...$
    "frac": "\\dfrac{%|}{}",
    "sqrt": "\\sqrt{%|}",
    "sum": "\\sum_{%|}^{}",
    "int": "\\int_{%|}^{}",
    "lim": "\\lim_{%| \\to }",
    "vec": "\\vec{%|}",
    "overline": "\\overline{%|}",
    "begin": "\\begin{%|}\n\n\\end{}",
}

MARKDOWN_DEFAULT_DOC = r"""# Tài liệu Markdown mới

Đây là tài liệu Markdown được tạo bởi **eMeX**. Bạn có thể chỉnh sửa nội dung này.

## Công thức toán

Inline: $E = mc^2$.

Block:

$$
\int_a^b f(x)\,dx = F(b) - F(a)
$$

## TikZ

```tikz
\begin{tikzpicture}
  \draw[->] (-1,0) -- (4,0) node[right] {$x$};
  \draw[->] (0,-1) -- (0,4) node[above] {$y$};
  \draw[domain=-1:3, smooth, variable=\x] plot ({\x},{(\x-1)^2});
\end{tikzpicture}
```

## Bảng

| Cột 1 | Cột 2 |
|-------|-------|
| A     | 1     |
| B     | 2     |

## Mã nguồn

```python
def hello():
    print("Xin chào từ eMeX")
```

## Danh sách

- Mục một
- Mục hai
- [ ] Việc chưa xong
- [x] Việc đã xong
"""

MARKDOWN_PAGE_TEMPLATES = [
    {
        "name": "Tài liệu cơ bản",
        "filename": "Tai-lieu-co-ban.md",
        "content": MARKDOWN_DEFAULT_DOC,
    },
    {
        "name": "Ghi chú nhanh",
        "filename": "Ghi-chu-nhanh.md",
        "content": """# Ghi chú nhanh

## Ý chính

-

## Việc cần làm

- [ ]

## Ghi thêm

""",
    },
    {
        "name": "Bài học",
        "filename": "Bai-hoc.md",
        "content": """# Tên bài học

## Mục tiêu

-

## Nội dung

### 1. Khởi động

### 2. Kiến thức chính

### 3. Luyện tập

## Ghi chú giáo viên

""",
    },
    {
        "name": "Bài tập toán",
        "filename": "Bai-tap-toan.md",
        "content": """# Bài tập toán

## Đề bài


## Lời giải

$$

$$

## Kết luận

""",
    },
    {
        "name": "Báo cáo ngắn",
        "filename": "Bao-cao-ngan.md",
        "content": """# Báo cáo ngắn

## Tóm tắt


## Nội dung chính


## Kết quả


## Việc tiếp theo

- [ ]
""",
    },
]

# --------- Bảng ký hiệu nhanh cho Symbol Palette ---------
# Khi chèn vào Markdown, các ký hiệu \alpha, \frac... chỉ có nghĩa khi nằm trong $...$.
SYMBOL_PALETTE = {
    "Markdown nhanh": [
        ("𝐁", "**%|**"), ("𝑰", "*%|*"), ("S̶", "~~%|~~"), ("`x`", "`%|`"),
        ("∑", "$%|$"), ("∫", "$$\n%|\n$$"),
        ("H1", "# %|"), ("H2", "## %|"), ("H3", "### %|"), ("H4", "#### %|"),
        ("• ", "- %|"), ("1.", "1. %|"), ("[ ]", "- [ ] %|"),
        ("> ", "> %|"), ("---", "\n---\n"), ("⛓", "[%|]()"),
    ],
    "Hy Lạp thường": [
        ("α", "\\alpha"), ("β", "\\beta"), ("γ", "\\gamma"), ("δ", "\\delta"),
        ("ε", "\\varepsilon"), ("ζ", "\\zeta"), ("η", "\\eta"), ("θ", "\\theta"),
        ("ι", "\\iota"), ("κ", "\\kappa"), ("λ", "\\lambda"), ("μ", "\\mu"),
        ("ν", "\\nu"), ("ξ", "\\xi"), ("π", "\\pi"), ("ρ", "\\rho"),
        ("σ", "\\sigma"), ("τ", "\\tau"), ("φ", "\\varphi"), ("χ", "\\chi"),
        ("ψ", "\\psi"), ("ω", "\\omega"),
    ],
    "Hy Lạp hoa": [
        ("Γ", "\\Gamma"), ("Δ", "\\Delta"), ("Θ", "\\Theta"), ("Λ", "\\Lambda"),
        ("Ξ", "\\Xi"), ("Π", "\\Pi"), ("Σ", "\\Sigma"), ("Φ", "\\Phi"),
        ("Ψ", "\\Psi"), ("Ω", "\\Omega"),
    ],
    "Quan hệ": [
        ("≤", "\\leq"), ("≥", "\\geq"), ("≠", "\\neq"), ("≈", "\\approx"),
        ("≡", "\\equiv"), ("∼", "\\sim"), ("≅", "\\cong"), ("∝", "\\propto"),
        ("⊂", "\\subset"), ("⊆", "\\subseteq"), ("⊃", "\\supset"), ("⊇", "\\supseteq"),
        ("∈", "\\in"), ("∉", "\\notin"), ("∪", "\\cup"), ("∩", "\\cap"),
    ],
    "Phép toán": [
        ("·", "\\cdot"), ("×", "\\times"), ("÷", "\\div"), ("±", "\\pm"),
        ("∓", "\\mp"), ("∘", "\\circ"), ("⊕", "\\oplus"), ("⊗", "\\otimes"),
        ("√", "\\sqrt{%|}"), ("∑", "\\sum_{%|}^{}"), ("∏", "\\prod_{%|}^{}"),
        ("∫", "\\int_{%|}^{}"), ("∮", "\\oint"), ("∂", "\\partial"),
        ("∇", "\\nabla"), ("∞", "\\infty"),
    ],
    "Mũi tên": [
        ("→", "\\to"), ("←", "\\leftarrow"), ("↔", "\\leftrightarrow"),
        ("⇒", "\\Rightarrow"), ("⇐", "\\Leftarrow"), ("⇔", "\\Leftrightarrow"),
        ("↦", "\\mapsto"), ("↑", "\\uparrow"), ("↓", "\\downarrow"),
    ],
    "Logic & Tập hợp": [
        ("∀", "\\forall"), ("∃", "\\exists"), ("¬", "\\neg"),
        ("∧", "\\land"), ("∨", "\\lor"), ("∅", "\\emptyset"),
        ("ℝ", "\\mathbb{R}"), ("ℕ", "\\mathbb{N}"), ("ℤ", "\\mathbb{Z}"),
        ("ℚ", "\\mathbb{Q}"), ("ℂ", "\\mathbb{C}"),
    ],
}

# --------- Default Gemini model list (dùng khi chưa fetch được) ---------
DEFAULT_GEMINI_MODELS = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
]

# --------- helpers load / save JSON ---------
def load_json(path, default):
    if not os.path.exists(path):
        return default.copy() if isinstance(default, (dict, list)) else default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default.copy() if isinstance(default, (dict, list)) else default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def load_editor_config():
    cfg = DEFAULT_EDITOR_CONFIG.copy()
    if os.path.exists(EDITOR_CONFIG_FILE):
        try:
            with open(EDITOR_CONFIG_FILE, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
            for k, v in user_cfg.items():
                if k in cfg:
                    cfg[k] = v
        except Exception:
            pass
    return cfg

def save_editor_config(cfg):
    save_json(EDITOR_CONFIG_FILE, cfg)

def load_api_key():
    if not os.path.exists(AI_CONFIG_FILE):
        return ""
    try:
        with open(AI_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("api_key", "")
    except Exception:
        return ""

def save_api_key(key):
    save_json(AI_CONFIG_FILE, {"api_key": key})

def load_recent():
    return load_json(RECENT_FILES_FILE, [])

def push_recent(path):
    recent = load_recent()
    path = os.path.abspath(path)
    if path in recent:
        recent.remove(path)
    recent.insert(0, path)
    recent = recent[:15]
    save_json(RECENT_FILES_FILE, recent)
    return recent


def load_user_page_templates():
    data = load_json(PAGE_TEMPLATES_FILE, [])
    if not isinstance(data, list):
        return []
    templates = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        content = item.get("content", "")
        if not name or not isinstance(content, str):
            continue
        filename = str(item.get("filename", "")).strip() or f"{name}.md"
        templates.append({"name": name, "filename": filename, "content": content})
    return templates


def save_user_page_templates(templates):
    return save_json(PAGE_TEMPLATES_FILE, templates)


def gemini_model_sort_key(name):
    """Trả về key sort sao cho model mới hơn xếp trước.

    Quy ước: ưu tiên version (2.5 > 2.0 > 1.5), rồi 'pro' > 'flash' > 'flash-lite'.
    """
    import re
    m = re.search(r"gemini[-_]?(\d+(?:\.\d+)?)", name.lower())
    ver = float(m.group(1)) if m else 0.0
    tier_score = 0
    low = name.lower()
    if "pro" in low:
        tier_score = 3
    elif "flash-lite" in low or "flash_lite" in low:
        tier_score = 1
    elif "flash" in low:
        tier_score = 2
    # preview / experimental đứng dưới latest cùng version
    extra = 0
    if "preview" in low or "exp" in low:
        extra = -0.1
    if "latest" in low:
        extra = 0.05
    return (-ver, -tier_score, -extra, name)

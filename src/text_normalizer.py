"""Normalize pasted/legacy Markdown so math renders reliably."""
from __future__ import annotations

import re
import unicodedata


_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_MATH_BLOCK_OPENERS = {"[": "]", r"\[": r"\]", "$$": "$$"}
_INLINE_PROTECTED_RE = re.compile(
    r"(!?\[[^\]\n]*\]\((?:<[^>\n]*>|[^)\n]*)\)"
    r"|`+[^`\n]*`+"
    r"|\$\$[^\n]+?\$\$"
    r"|(?<!\$)\$[^\n$]+?\$(?!\$)"
    r"|\\\([^\n]*?\\\))"
)
_OPERATOR_GROUP_RE = re.compile(r"\\(min|max)\s*\{")
_FRAC_SHORTHAND_RE = re.compile(r"\\frac\s*([A-Za-z0-9])\s*([A-Za-z0-9])")
_SQRT_SHORTHAND_RE = re.compile(r"\\sqrt\s*([A-Za-z0-9])")
_SQRT_COMMA_SPACE_RE = re.compile(r"(\\sqrt\{[^{}]+\}),\s*([A-Za-z])")
_ROW_SPACING_RE = re.compile(r",\s*(\[\d+(?:\.\d+)?(?:pt|em|ex|mm|cm|in|px)\])\s*$")
_BROKEN_SIZED_PARENS_RE = re.compile(
    r"(\\(?P<size>bigg?|Bigg?)l?[ \t]*)\$(?!\$)"
    r"([^$\n]*?)(\\(?P=size)r?[ \t]*)\$(?!\$)"
)


def normalize_external_paste_text(text: str) -> str:
    """Preserve clipboard source; only adapt its line endings for the editor.

    Paste also receives partial formulas, code, and ordinary parentheses. The
    compile-time math heuristics cannot infer their context and must not rewrite
    the user's document. Preview/export normalization runs on a separate copy.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


def normalize_markdown_for_compile(source: str) -> str:
    """Return Markdown that is friendlier to MathJax/export compilation.

    The function is intentionally line-count preserving. Preview sync relies on
    source line numbers, so transformations replace text in-place instead of
    deleting or inserting lines.
    """
    if not source:
        return source

    source = _normalize_unicode_text(source)
    lines = source.split("\n")
    out: list[str] = []
    i = 0
    in_fence = False
    display_close: str | None = None

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if _FENCE_RE.match(stripped):
            in_fence = not in_fence
            display_close = None
            out.append(line)
            i += 1
            continue

        if in_fence:
            out.append(line)
            i += 1
            continue

        # Display delimiters may share a line with the formula. Keep every
        # line in that block out of the prose/parenthesized-math heuristic.
        if display_close is not None:
            normalized, display_close = _normalize_display_math_line(line, display_close)
            out.append(normalized)
            i += 1
            continue

        opener = next((token for token in ("$$", r"\[") if stripped.startswith(token)), None)
        if opener is not None:
            start = line.index(opener)
            close = "$$" if opener == "$$" else r"\]"
            normalized, display_close = _normalize_display_math_line(
                line[start + len(opener):], close)
            out.append(line[:start] + "$$" + normalized)
            i += 1
            continue

        if stripped in _MATH_BLOCK_OPENERS:
            close = _MATH_BLOCK_OPENERS[stripped]
            end = _find_math_block_end(lines, i + 1, close)
            if end is not None and (stripped != "[" or _has_nonempty_lines(lines[i + 1:end])):
                out.append(_replace_stripped_token(line, "$$"))
                out.extend(_normalize_math_line(math_line) for math_line in lines[i + 1:end])
                out.append(_replace_stripped_token(lines[end], "$$"))
                i = end + 1
                continue

        out.append(_normalize_text_line(line))
        i += 1

    return "\n".join(out)


def _normalize_display_math_line(line: str, close: str) -> tuple[str, str | None]:
    # A damaged closing parenthesis can sit directly before the closing $$,
    # producing $$$. Keep the first dollar in the math so it can be repaired.
    pattern = re.escape(close) + (r"(?!\$)" if close == "$$" else "")
    for match in re.finditer(pattern, line):
        # A delimiter escaped with an odd number of backslashes is literal.
        prefix = line[:match.start()]
        slash_count = len(prefix) - len(prefix.rstrip("\\"))
        if slash_count % 2:
            continue
        math = _normalize_math_line(prefix)
        suffix = _normalize_text_line(line[match.end():])
        return math + "$$" + suffix, None
    return _normalize_math_line(line), close


def _normalize_unicode_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    replacements = {
        "\ufeff": "",
        "\u200b": "",
        "\u200c": "",
        "\u200d": "",
        "\u00a0": " ",
        "\u202f": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _find_math_block_end(lines: list[str], start: int, close: str) -> int | None:
    for index in range(start, len(lines)):
        stripped = lines[index].strip()
        if _FENCE_RE.match(stripped):
            return None
        if stripped == close:
            return index
    return None


def _replace_stripped_token(line: str, replacement: str) -> str:
    indent = re.match(r"\s*", line).group(0)
    return indent + replacement


def _has_nonempty_lines(lines: list[str]) -> bool:
    return any(line.strip() for line in lines)


def _normalize_math_line(line: str) -> str:
    if not line.strip():
        return line

    indent_match = re.match(r"\s*", line)
    indent = indent_match.group(0) if indent_match else ""
    stripped = line.strip()

    if re.fullmatch(r"={2,}", stripped):
        return indent + "="

    if stripped.startswith("# "):
        candidate = stripped[2:].strip()
        if _looks_like_inline_math(candidate):
            stripped = candidate

    stripped = _ROW_SPACING_RE.sub(r"\\\\\1", stripped)
    return indent + _normalize_latex_math(stripped)


def _normalize_text_line(line: str) -> str:
    parts = _INLINE_PROTECTED_RE.split(line)
    for index in range(0, len(parts), 2):
        parts[index] = _normalize_parenthesized_math(parts[index])
    return "".join(parts)


def _normalize_parenthesized_math(text: str) -> str:
    out: list[str] = []
    i = 0

    while i < len(text):
        if text[i] != "(":
            out.append(text[i])
            i += 1
            continue

        end = _find_matching_paren(text, i)
        if end is None:
            out.append(text[i])
            i += 1
            continue

        content = text[i + 1:end]
        if _looks_like_inline_math(content):
            out.append("$" + _normalize_latex_math(content.strip()) + "$")
        else:
            out.append("(" + _normalize_parenthesized_math(content) + ")")
        i = end + 1

    return "".join(out)


def _find_matching_paren(text: str, open_index: int) -> int | None:
    depth = 0
    for index in range(open_index, len(text)):
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _looks_like_inline_math(content: str) -> bool:
    content = content.strip()
    if not content or "\n" in content or len(content) > 160:
        return False
    if re.search(r"https?://|[a-zA-Z]:[\\/]", content):
        return False

    if re.search(r"\\[a-zA-Z]+", content):
        return True
    if re.search(r"[:<>]?=|\\leq?|\\geq?|\\neq|\\in\b", content):
        return True
    if re.search(r"(?<![./])\b[A-Za-z0-9\]}]+_\{?[A-Za-z0-9\\]+", content):
        return True
    if "^" in content:
        return True
    if re.fullmatch(r"[A-Za-z](?:_\{?[A-Za-z0-9\\]+\}?)?", content):
        return True
    if re.fullmatch(r"[A-Za-z]_[A-Za-z0-9]+\([A-Za-z0-9_,{}\\\s+-]+\)", content):
        return True
    return False


def _normalize_latex_math(text: str) -> str:
    # Earlier paste normalization replaced sized parentheses with dollars in
    # multiline display math. Recover only the matching pair it produced.
    text = _BROKEN_SIZED_PARENS_RE.sub(r"\1(\3\4)", text)
    text = _FRAC_SHORTHAND_RE.sub(r"\\frac{\1}{\2}", text)
    text = _SQRT_SHORTHAND_RE.sub(r"\\sqrt{\1}", text)
    text = _SQRT_COMMA_SPACE_RE.sub(r"\1\\,\2", text)
    text = re.sub(r"\\left\s*(?:\\\{|\{)", r"\\left\\lbrace ", text)
    text = re.sub(r"\\right\s*(?:\\\}|\})", r"\\right\\rbrace", text)
    return _normalize_operator_set_braces(text)


def _normalize_operator_set_braces(text: str) -> str:
    out: list[str] = []
    i = 0

    while True:
        match = _OPERATOR_GROUP_RE.search(text, i)
        if not match:
            out.append(text[i:])
            break

        open_index = match.end() - 1
        close_index = _find_matching_brace(text, open_index)
        if close_index is None:
            out.append(text[i:])
            break

        inner = text[open_index + 1:close_index]
        out.append(text[i:match.start()])
        if _should_show_operator_braces(inner):
            out.append(text[match.start():open_index] + r"\{" + inner + r"\}")
        else:
            out.append(text[match.start():close_index + 1])
        i = close_index + 1

    return "".join(out)


def _find_matching_brace(text: str, open_index: int) -> int | None:
    depth = 0
    index = open_index
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _should_show_operator_braces(inner: str) -> bool:
    return "," in inner or "\n" in inner or r"\left" in inner or r"\right" in inner

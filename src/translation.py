"""Translation support for compile-time preview rendering."""
from __future__ import annotations

import re
from typing import Iterable


COMPILE_TRANSLATION_LANGUAGES = (
    ("none", "None"),
    ("en", "EN"),
    ("vi", "VN"),
    ("zh-CN", "CHI"),
    ("ja", "JA"),
    ("ko", "KO"),
    ("fr", "FR"),
    ("de", "DE"),
    ("es", "ES"),
    ("ru", "RU"),
)

COMPILE_TRANSLATION_TOOLS = (
    ("google", "Google Translate"),
    ("gemini", "Gemini"),
)

_LANGUAGE_CODES = {code for code, _label in COMPILE_TRANSLATION_LANGUAGES}
_TOOL_CODES = {code for code, _label in COMPILE_TRANSLATION_TOOLS}
_GOOGLE_TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
_MAX_CHUNK_SIZE = 3500
_GEMINI_TRANSLATE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

_PROTECTED_BLOCK_RE = re.compile(
    r"(^[ \t]*(```|~~~)[^\n]*\n.*?^[ \t]*\2[ \t]*$)"
    r"|(\$\$.*?\$\$)"
    r"|(\\\[.*?\\\])"
    r"|(\\begin\{tikzpicture\}.*?\\end\{tikzpicture\})",
    re.MULTILINE | re.DOTALL,
)
_INLINE_PROTECTED_RE = re.compile(
    r"(`[^`\n]+`)"
    r"|(?<!\$)(\$[^\n$]+\$)(?!\$)"
    r"|(\\\([^\n]+?\\\))"
)


def normalize_compile_language(language: str | None) -> str:
    value = (language or "none").strip()
    return value if value in _LANGUAGE_CODES else "none"


def compile_language_label(language: str | None) -> str:
    normalized = normalize_compile_language(language)
    for code, label in COMPILE_TRANSLATION_LANGUAGES:
        if code == normalized:
            return label
    return "None"


def normalize_translation_tool(tool: str | None) -> str:
    value = (tool or "google").strip()
    return value if value in _TOOL_CODES else "google"


def translation_tool_label(tool: str | None) -> str:
    normalized = normalize_translation_tool(tool)
    for code, label in COMPILE_TRANSLATION_TOOLS:
        if code == normalized:
            return label
    return "Google Translate"


def translate_markdown(
    source: str,
    target_language: str,
    tool: str,
    *,
    gemini_api_key: str = "",
    gemini_model: str = "gemini-2.5-flash",
) -> str:
    tool = normalize_translation_tool(tool)
    if tool == "gemini":
        return translate_markdown_with_gemini(
            source, target_language, gemini_api_key, gemini_model)
    return translate_markdown_with_google(source, target_language)


def translate_markdown_with_google(source: str, target_language: str) -> str:
    """Translate markdown prose while preserving code, TikZ, and math blocks."""
    target_language = normalize_compile_language(target_language)
    if target_language == "none" or not source:
        return source

    translated_parts: list[str] = []
    for text, protected in _split_protected(source, _PROTECTED_BLOCK_RE):
        if protected or not text.strip():
            translated_parts.append(text)
            continue
        translated_parts.append(_translate_inline_safe(text, target_language))
    return "".join(translated_parts)


def translate_markdown_with_gemini(
    source: str,
    target_language: str,
    api_key: str,
    model: str,
) -> str:
    """Translate markdown with Gemini while preserving document structure."""
    target_language = normalize_compile_language(target_language)
    if target_language == "none" or not source:
        return source
    if not api_key:
        raise RuntimeError("Thiếu khóa API Gemini. Vào Cài đặt > Gemini AI để nhập khóa API.")

    translated_parts: list[str] = []
    for text, protected in _split_protected(source, _PROTECTED_BLOCK_RE):
        if protected or not text.strip():
            translated_parts.append(text)
            continue
        translated_parts.append(_translate_inline_safe_with_gemini(
            text, target_language, api_key, model))
    return "".join(translated_parts)


def _translate_inline_safe(text: str, target_language: str) -> str:
    translated_parts: list[str] = []
    for part, protected in _split_protected(text, _INLINE_PROTECTED_RE):
        if protected or not part.strip():
            translated_parts.append(part)
            continue
        translated_parts.append(_translate_text(part, target_language))
    return "".join(translated_parts)


def _translate_inline_safe_with_gemini(
    text: str,
    target_language: str,
    api_key: str,
    model: str,
) -> str:
    translated_parts: list[str] = []
    for part, protected in _split_protected(text, _INLINE_PROTECTED_RE):
        if protected or not part.strip():
            translated_parts.append(part)
            continue
        translated_parts.append(_translate_text_with_gemini(
            part, target_language, api_key, model))
    return "".join(translated_parts)


def _split_protected(text: str, pattern: re.Pattern[str]) -> Iterable[tuple[str, bool]]:
    pos = 0
    for match in pattern.finditer(text):
        start, end = match.span()
        if start > pos:
            yield text[pos:start], False
        yield text[start:end], True
        pos = end
    if pos < len(text):
        yield text[pos:], False


def _translate_text(text: str, target_language: str) -> str:
    chunks = _chunk_text(text)
    return "".join(_request_google_translate(chunk, target_language) for chunk in chunks)


def _chunk_text(text: str) -> list[str]:
    if len(text) <= _MAX_CHUNK_SIZE:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for piece in re.split(r"(\n{2,})", text):
        if current_len + len(piece) > _MAX_CHUNK_SIZE and current:
            chunks.append("".join(current))
            current = []
            current_len = 0
        if len(piece) > _MAX_CHUNK_SIZE:
            chunks.extend(piece[i:i + _MAX_CHUNK_SIZE]
                          for i in range(0, len(piece), _MAX_CHUNK_SIZE))
            continue
        current.append(piece)
        current_len += len(piece)
    if current:
        chunks.append("".join(current))
    return chunks


def _request_google_translate(text: str, target_language: str) -> str:
    import requests

    params = {
        "client": "gtx",
        "sl": "auto",
        "tl": target_language,
        "dt": "t",
    }
    response = requests.post(
        _GOOGLE_TRANSLATE_URL,
        params=params,
        data={"q": text},
        timeout=20,
        headers={"User-Agent": "eMeX/1.0"},
    )
    response.raise_for_status()
    payload = response.json()
    sentences = payload[0] if isinstance(payload, list) and payload else []
    return "".join(
        sentence[0]
        for sentence in sentences
        if isinstance(sentence, list) and sentence and sentence[0] is not None
    )


def _translate_text_with_gemini(
    text: str,
    target_language: str,
    api_key: str,
    model: str,
) -> str:
    chunks = _chunk_text(text)
    return "".join(
        _request_gemini_translate(chunk, target_language, api_key, model)
        for chunk in chunks
    )


def _request_gemini_translate(
    text: str,
    target_language: str,
    api_key: str,
    model: str,
) -> str:
    import requests

    language_name = compile_language_label(target_language)
    prompt = (
        f"Translate the following Markdown text to {language_name}.\n"
        "Requirements:\n"
        "- Return only the translated Markdown text. Do not add explanations, notes, or code fences.\n"
        "- Preserve the original layout exactly: paragraph breaks, blank lines, headings, lists, tables, "
        "block quotes, indentation, punctuation placement where possible, and the order of all content.\n"
        "- Keep the sentence structure as close to the source as the target language naturally allows.\n"
        "- Translate by the original context so the result is clear and natural, but do not rewrite, "
        "summarize, expand, reorder, or change the meaning.\n"
        "- Preserve Markdown markers and any remaining technical tokens exactly when they should not be translated.\n\n"
        "SOURCE MARKDOWN:\n"
        "<<<EMEX_TRANSLATE_SOURCE>>>\n"
        f"{text}\n"
        "<<<END_EMEX_TRANSLATE_SOURCE>>>"
    )
    url = _GEMINI_TRANSLATE_URL.format(model=model)
    response = requests.post(
        url,
        params={"key": api_key},
        json={
            "contents": [{
                "role": "user",
                "parts": [{"text": prompt}],
            }],
            "generationConfig": {
                "temperature": 0.1,
                "topP": 0.8,
            },
        },
        timeout=90,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Gemini API {response.status_code}: {response.text[:500]}")
    data = response.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as exc:
        raise RuntimeError(f"Phản hồi Gemini không hợp lệ: {data}") from exc

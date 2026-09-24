"""One scalable, consistent SVG icon set for both editor toolbars."""
from functools import lru_cache

from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer


# All glyphs use the same 24-unit grid, rounded caps, and 1.8-unit stroke.
_PATHS = {
    "file-plus": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M12 12v6m-3-3h6"/>',
    "folder-open": '<path d="M3 8V6a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v2"/><path d="M3 10h18l-2 10H5z"/>',
    "save": '<path d="M5 3h13l3 3v14a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M7 3v6h10V3M7 21v-8h10v8M14 3v4"/>',
    "bold": '<path d="M7 4h6a4 4 0 0 1 0 8H7zM7 12h7a4 4 0 0 1 0 8H7z"/>',
    "italic": '<path d="M13 4h7M4 20h7M15 4 9 20"/>',
    "strike": '<path d="M17 6c-1-2-3-3-5-3-3 0-5 2-5 4 0 3 3 4 6 5M7 18c1 2 3 3 5 3 3 0 5-2 5-4M3 12h18"/>',
    "code": '<path d="m8 8-4 4 4 4m8-8 4 4-4 4"/>',
    "sigma": '<path d="M18 4H6l6 8-6 8h12"/>',
    "integral": '<path d="M16 3c-4-1-5 2-6 7l-1 6c-1 5-2 6-5 5M6 11h9"/>',
    "quote": '<path d="M10 11H5V6h6v5c0 4-2 6-5 7m13-7h-5V6h6v5c0 4-2 6-5 7"/>',
    "minus": '<path d="M5 12h14"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7 .2l2-2a5 5 0 0 0-7-7l-1.2 1.2M14 11a5 5 0 0 0-7-.2l-2 2a5 5 0 0 0 7 7l1.2-1.2"/>',
    "image": '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 16-5-5L5 21"/>',
    "table": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M3 15h18M9 4v16m6-16v16"/>',
    "code-square": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="m10 8-4 4 4 4m4-8 4 4-4 4"/>',
    "comment": '<path d="M20 11.5a8.5 8.5 0 0 1-8.5 8.5H4l2-4a8.5 8.5 0 1 1 14-4.5z"/><path d="m10 9-2 2 2 2m4-4 2 2-2 2"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m16 16 5 5"/>',
    "play": '<path d="m8 5 11 7-11 7z"/>',
    "git-branch": '<circle cx="6" cy="4" r="2"/><circle cx="6" cy="20" r="2"/><circle cx="18" cy="7" r="2"/><path d="M6 6v12m12-9v3a6 6 0 0 1-6 6H6"/>',
    "panel-left": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/>',
    "eye": '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>',
    "sparkles": '<path d="m12 3 1.6 5.4L19 10l-5.4 1.6L12 17l-1.6-5.4L5 10l5.4-1.6zM19 17l.6 1.4L21 19l-1.4.6L19 21l-.6-1.4L17 19l1.4-.6z"/>',
    "maximize": '<path d="M8 3H4a1 1 0 0 0-1 1v4m13-5h4a1 1 0 0 1 1 1v4M3 16v4a1 1 0 0 0 1 1h4m13-5v4a1 1 0 0 1-1 1h-4"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3M4.9 4.9 7 7m10 10 2.1 2.1M19.1 4.9 17 7M7 17l-2.1 2.1"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 11v6m0-10h.01"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c-3 3-3 15 0 18m0-18c3 3 3 15 0 18"/>',
    "upload": '<path d="M12 16V3m-4 4 4-4 4 4M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>',
    "zoom-in": '<circle cx="10.5" cy="10.5" r="7"/><path d="M10.5 7v7m-3.5-3.5h7M16 16l5 5"/>',
    "zoom-out": '<circle cx="10.5" cy="10.5" r="7"/><path d="M7 10.5h7M16 16l5 5"/>',
    "clipboard-image": '<rect x="4" y="5" width="16" height="17" rx="2"/><path d="M9 5V3h6v2"/><circle cx="9" cy="11" r="1"/><path d="m6 19 5-5 3 3 2-2 2 2"/>',
    "clipboard-file": '<rect x="4" y="5" width="16" height="17" rx="2"/><path d="M9 5V3h6v2M8 11h8m-8 4h8m-8 4h5"/>',
    "file-output": '<path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8M13 2v6h7m-9 9h10m-4-4 4 4-4 4"/>',
    "spinner": '<path d="M20 12a8 8 0 1 1-8-8"/>',
}


@lru_cache(maxsize=128)
def toolbar_icon(name: str, color: str = "#475569", rotation: int = 0) -> QIcon:
    """Return a crisp SVG icon using the same drawing grid at every toolbar size."""
    path = _PATHS[name]
    if rotation:
        path = f'<g transform="rotate({rotation} 12 12)">{path}</g>'
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
           f'fill="none" stroke="{color}" stroke-width="1.8" '
           f'stroke-linecap="round" stroke-linejoin="round">{path}</svg>')
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    icon = QIcon()
    for size in (16, 20, 22, 24, 32, 36, 48, 64):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter)
        painter.end()
        icon.addPixmap(pixmap)
    return icon
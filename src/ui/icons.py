"""Vector icon library for Acer Sense.

Renders native SVG vectors into QIcon / QPixmap with dynamic theme color adaptation.
No emoji characters or textual pseudo-icons.
"""
from __future__ import annotations

from PyQt6.QtCore import QByteArray, QSize, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

# ─────────────────────────────────────────────────────────────────────────────
# SVG Vector Templates
# ─────────────────────────────────────────────────────────────────────────────

SVG_TEMPLATES: dict[str, str] = {
    # ── Header & Common ──────────────────────────────────────────────────────
    "gear": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="{size}" height="{size}">
<path fill="{color}" d="M12 15.5A3.5 3.5 0 0 1 8.5 12 3.5 3.5 0 0 1 12 8.5a3.5 3.5 0 0 1 3.5 3.5 3.5 3.5 0 0 1-3.5 3.5m7.43-2.53c.04-.32.07-.64.07-.97 0-.33-.03-.66-.07-1l2.11-1.63c.19-.15.24-.42.12-.64l-2-3.46c-.12-.22-.39-.31-.61-.22l-2.49 1c-.52-.39-1.06-.73-1.69-.98l-.37-2.65A.506.506 0 0 0 13.5 2h-4c-.25 0-.46.18-.5.42l-.37 2.65c-.63.25-1.17.59-1.69.98l-2.49-1c-.22-.09-.49 0-.61.22l-2 3.46c-.13.22-.07.49.12.64l2.11 1.63c-.04.34-.07.67-.07 1 0 .33.03.65.07.97l-2.11 1.66c-.19.15-.25.42-.12.64l2 3.46c.12.22.39.3.61.22l2.49-1.01c.52.4 1.06.74 1.69.99l.37 2.65c.04.24.25.42.5.42h4c.25 0 .46-.18.5-.42l.37-2.65c.63-.26 1.17-.59 1.69-.99l2.49 1.01c.22.08.49 0 .61-.22l2-3.46c.12-.22.07-.49-.12-.64l-2.11-1.66z"/>
</svg>""",

    "headset": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="{size}" height="{size}">
<path fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" d="M3 14h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a9 9 0 0 1 18 0v7a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3"/>
<path fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" d="M19 19a3 3 0 0 1-3 3h-2"/>
</svg>""",

    # ── Power Profiles Speedometers (matching official AcerSense app) ─────────
    "speedo_quiet": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 36" width="{size}" height="{size}">
<path d="M 7 24 A 12 12 0 1 1 29 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round"/>
<circle cx="18" cy="22" r="2.2" fill="{color}"/>
<line x1="18" y1="22" x2="11" y2="18" stroke="{color}" stroke-width="2.4" stroke-linecap="round"/>
<path d="M 11 13 A 3.2 3.2 0 0 0 13 16.2 A 2.4 2.4 0 0 1 11 13" fill="{color}" stroke="{color}" stroke-width="0.8"/>
</svg>""",

    "speedo_balanced": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 36" width="{size}" height="{size}">
<path d="M 7 24 A 12 12 0 1 1 29 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round"/>
<line x1="10.5" y1="14" x2="12.5" y2="15.5" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
<line x1="25.5" y1="14" x2="23.5" y2="15.5" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
<circle cx="18" cy="22" r="2.2" fill="{color}"/>
<line x1="18" y1="22" x2="18" y2="12" stroke="{color}" stroke-width="2.4" stroke-linecap="round"/>
</svg>""",

    "speedo_performance": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 36" width="{size}" height="{size}">
<path d="M 7 24 A 12 12 0 1 1 29 24" fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round"/>
<line x1="10.5" y1="14" x2="12.5" y2="15.5" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
<line x1="18" y1="10" x2="18" y2="12.5" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
<circle cx="18" cy="22" r="2.2" fill="{color}"/>
<line x1="18" y1="22" x2="25" y2="17" stroke="{color}" stroke-width="2.4" stroke-linecap="round"/>
</svg>""",

    # ── Hardware Diagnostic Badges ───────────────────────────────────────────
    "battery": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="{size}" height="{size}">
<rect x="2" y="6" width="17" height="12" rx="2.5" fill="none" stroke="{color}" stroke-width="1.8"/>
<line x1="21.5" y1="10" x2="21.5" y2="14" stroke="{color}" stroke-width="2" stroke-linecap="round"/>
<rect x="4.5" y="8.5" width="9" height="7" rx="1" fill="{color}"/>
</svg>""",

    "battery_circle": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 28" width="{size}" height="{size}">
<circle cx="14" cy="14" r="12.5" fill="none" stroke="{color}" stroke-width="1.5"/>
<rect x="9.5" y="8" width="9" height="13" rx="2" fill="none" stroke="{color}" stroke-width="1.5"/>
<line x1="12" y1="6" x2="16" y2="6" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
<rect x="11.5" y="11" width="5" height="7" rx="0.8" fill="{color}"/>
</svg>""",

    "ssd": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 28" width="{size}" height="{size}">
<circle cx="14" cy="14" r="12.5" fill="none" stroke="{color}" stroke-width="1.5"/>
<rect x="7" y="8.5" width="14" height="11" rx="1.5" fill="none" stroke="{color}" stroke-width="1.5"/>
<circle cx="9.5" cy="11" r="0.9" fill="{color}"/>
<line x1="10" y1="19.5" x2="10" y2="21.5" stroke="{color}" stroke-width="1.3" stroke-linecap="round"/>
<line x1="13" y1="19.5" x2="13" y2="21.5" stroke="{color}" stroke-width="1.3" stroke-linecap="round"/>
<line x1="16" y1="19.5" x2="16" y2="21.5" stroke="{color}" stroke-width="1.3" stroke-linecap="round"/>
<rect x="10.5" y="12.5" width="7" height="4" rx="0.5" fill="{color}"/>
</svg>""",

    "ram": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 28" width="{size}" height="{size}">
<circle cx="14" cy="14" r="12.5" fill="none" stroke="{color}" stroke-width="1.5"/>
<rect x="6.5" y="10" width="15" height="8" rx="1" fill="none" stroke="{color}" stroke-width="1.5"/>
<rect x="8.5" y="11.5" width="3" height="3" fill="{color}"/>
<rect x="12.5" y="11.5" width="3" height="3" fill="{color}"/>
<rect x="16.5" y="11.5" width="3" height="3" fill="{color}"/>
<line x1="8.5" y1="18" x2="8.5" y2="19.5" stroke="{color}" stroke-width="1.2"/>
<line x1="11.5" y1="18" x2="11.5" y2="19.5" stroke="{color}" stroke-width="1.2"/>
<line x1="16.5" y1="18" x2="16.5" y2="19.5" stroke="{color}" stroke-width="1.2"/>
<line x1="19.5" y1="18" x2="19.5" y2="19.5" stroke="{color}" stroke-width="1.2"/>
</svg>""",

    "cooling": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 28" width="{size}" height="{size}">
<circle cx="14" cy="14" r="12.5" fill="none" stroke="{color}" stroke-width="1.5"/>
<circle cx="14" cy="14" r="2" fill="{color}"/>
<path d="M14 12C14 8 16.5 7 16.5 7C16.5 7 16 9.5 14 12Z" fill="{color}"/>
<path d="M16 14C20 14 21 16.5 21 16.5C21 16.5 18.5 16 16 14Z" fill="{color}"/>
<path d="M14 16C14 20 11.5 21 11.5 21C11.5 21 12 18.5 14 16Z" fill="{color}"/>
<path d="M12 14C8 14 7 11.5 7 11.5C7 11.5 9.5 12 12 14Z" fill="{color}"/>
</svg>""",

    "heart_check": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="{size}" height="{size}">
<path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" fill="none" stroke="{color}" stroke-width="1.8"/>
<polyline points="7 9 10 12 17 6" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",

    "speedo_circle": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 28" width="{size}" height="{size}">
<circle cx="14" cy="14" r="12.5" fill="none" stroke="{color}" stroke-width="1.5"/>
<path d="M 8.5 18.5 A 7.5 7.5 0 1 1 19.5 18.5" fill="none" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
<circle cx="14" cy="17.5" r="1.5" fill="{color}"/>
<line x1="14" y1="17.5" x2="17.5" y2="12.5" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
</svg>""",

    # ── Settings Categories ──────────────────────────────────────────────────
    "display": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 28" width="{size}" height="{size}">
<circle cx="14" cy="14" r="12.5" fill="none" stroke="{color}" stroke-width="1.5"/>
<rect x="7" y="8" width="14" height="9.5" rx="1.5" fill="none" stroke="{color}" stroke-width="1.4"/>
<line x1="14" y1="17.5" x2="14" y2="20.5" stroke="{color}" stroke-width="1.4"/>
<line x1="11" y1="20.5" x2="17" y2="20.5" stroke="{color}" stroke-width="1.4" stroke-linecap="round"/>
</svg>""",

    "keyboard": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 28" width="{size}" height="{size}">
<circle cx="14" cy="14" r="12.5" fill="none" stroke="{color}" stroke-width="1.5"/>
<rect x="6.5" y="9.5" width="15" height="9" rx="1.5" fill="none" stroke="{color}" stroke-width="1.4"/>
<line x1="9" y1="12" x2="10.5" y2="12" stroke="{color}" stroke-width="1.3" stroke-linecap="round"/>
<line x1="13.2" y1="12" x2="14.7" y2="12" stroke="{color}" stroke-width="1.3" stroke-linecap="round"/>
<line x1="17.5" y1="12" x2="19" y2="12" stroke="{color}" stroke-width="1.3" stroke-linecap="round"/>
<line x1="10.5" y1="15" x2="17.5" y2="15" stroke="{color}" stroke-width="1.3" stroke-linecap="round"/>
</svg>""",

    "theme_palette": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 28" width="{size}" height="{size}">
<circle cx="14" cy="14" r="12.5" fill="none" stroke="{color}" stroke-width="1.5"/>
<path d="M14 6.5A7.5 7.5 0 0 0 6.5 14c0 4.14 3.36 7.5 7.5 7.5 1.04 0 1.88-.84 1.88-1.88 0-.48-.19-.92-.5-1.25-.3-.32-.5-.76-.5-1.25 0-1.04.84-1.87 1.87-1.87H18c2.48 0 4.5-2.02 4.5-4.5 0-4.55-3.81-8.25-8.5-8.25z" fill="none" stroke="{color}" stroke-width="1.4"/>
<circle cx="10" cy="11.5" r="1" fill="{color}"/>
<circle cx="14" cy="9.5" r="1" fill="{color}"/>
<circle cx="18" cy="11.5" r="1" fill="{color}"/>
</svg>""",

    "clean": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="{size}" height="{size}">
<path d="M19.36 10.04l-4.4-4.4 1.4-1.4a1 1 0 0 1 1.42 0l3 3a1 1 0 0 1 0 1.4l-1.42 1.4zM5.93 17.57l7.07-7.07 4.24 4.24-7.07 7.07a2 2 0 0 1-1.41.59H4v-4.83c0-.53.21-1.04.59-1.41z" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
</svg>""",

    "info": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="{size}" height="{size}">
<circle cx="12" cy="12" r="9" fill="none" stroke="{color}" stroke-width="1.8"/>
<line x1="12" y1="11" x2="12" y2="16" stroke="{color}" stroke-width="2" stroke-linecap="round"/>
<circle cx="12" cy="7.8" r="1" fill="{color}"/>
</svg>""",
}


def render_svg_pixmap(icon_name: str, color: str, size: int = 24) -> QPixmap:
    """Render an inline SVG string into a crisp QPixmap of given size and color."""
    template = SVG_TEMPLATES.get(icon_name)
    if not template:
        pix = QPixmap(size, size)
        pix.fill()
        return pix

    svg_code = template.format(color=color, size=size)
    renderer = QSvgRenderer(QByteArray(svg_code.encode("utf-8")))

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()

    return pixmap


def create_svg_icon(icon_name: str, color: str, size: int = 24) -> QIcon:
    """Return a QIcon created from an inline SVG."""
    return QIcon(render_svg_pixmap(icon_name, color, size))

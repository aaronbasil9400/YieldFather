"""Light/dark theming helpers for the SPC desktop app.

Central palettes plus Qt plumbing so every surface (app palette, KPI cards,
warning banner, pyqtgraph charts) switches together. The manual override is
persisted by the session-settings mechanism in spc_app.main; "System"
resolves through the OS personalization preference (Windows registry).
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette

THEME_MODES = ("System", "Light", "Dark")

LIGHT = {
    "window": "#F1F3F5",
    "base": "#FFFFFF",
    "alt_base": "#F7F9FA",
    "button": "#FAFBFC",
    "tooltip_base": "#FFFBEA",
    "highlight": "#3B82F6",
    "text": "#31333F",
    "muted": "#64748B",
    "card_bg": "rgba(128, 128, 128, 0.08)",
    "card_border": "rgba(128, 128, 128, 0.3)",
    "banner_bg": "rgba(245, 158, 11, 0.15)",
    "banner_border": "rgba(245, 158, 11, 0.5)",
    "banner_text": "#7C4A03",
    "plot_bg": "#FFFFFF",
    "plot_fg": "#31333F",
    "plot_axis": "#94A3B8",
}

DARK = {
    "window": "#0F172A",
    "base": "#1E293B",
    "alt_base": "#243244",
    "button": "#1E293B",
    "tooltip_base": "#1E293B",
    "highlight": "#60A5FA",
    "text": "#E2E8F0",
    "muted": "#94A3B8",
    "card_bg": "rgba(148, 163, 184, 0.10)",
    "card_border": "rgba(148, 163, 184, 0.28)",
    "banner_bg": "rgba(245, 158, 11, 0.16)",
    "banner_border": "rgba(245, 158, 11, 0.45)",
    "banner_text": "#FCD34D",
    "plot_bg": "#111827",
    "plot_fg": "#E5E7EB",
    "plot_axis": "#64748B",
}


def system_prefers_dark() -> bool:
    """Resolve the OS app-theme preference; falls back to light."""
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        try:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return int(value) == 0
        finally:
            key.Close()
    except OSError:
        return False


def resolve_palette(mode: str) -> dict:
    if mode == "Light":
        return LIGHT
    if mode == "Dark":
        return DARK
    return DARK if system_prefers_dark() else LIGHT


def build_app_palette(p: dict) -> QPalette:
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(p["window"]))
    pal.setColor(QPalette.WindowText, QColor(p["text"]))
    pal.setColor(QPalette.Base, QColor(p["base"]))
    pal.setColor(QPalette.AlternateBase, QColor(p["alt_base"]))
    pal.setColor(QPalette.Text, QColor(p["text"]))
    pal.setColor(QPalette.Button, QColor(p["button"]))
    pal.setColor(QPalette.ButtonText, QColor(p["text"]))
    pal.setColor(QPalette.ToolTipBase, QColor(p["tooltip_base"]))
    pal.setColor(QPalette.ToolTipText, QColor(p["text"]))
    pal.setColor(QPalette.Highlight, QColor(p["highlight"]))
    pal.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    pal.setColor(QPalette.PlaceholderText, QColor(p["muted"]))
    return pal


def card_qss(p: dict) -> str:
    return f"""
QFrame#kpiCard {{
    background: {p['card_bg']};
    border: 1px solid {p['card_border']};
    border-radius: 10px;
}}
QFrame#kpiCard QLabel {{ background: transparent; border: none; }}
QLabel#kpiLabel {{
    font-size: 11px; font-weight: 600; letter-spacing: 0.5px;
    color: {p['muted']};
}}
QLabel#kpiValue {{ font-size: 19px; font-weight: 800; color: {p['text']}; }}
"""


def banner_qss(p: dict) -> str:
    return (
        "QFrame { background: " + p["banner_bg"] + ";"
        " border: 1px solid " + p["banner_border"] + "; border-radius: 8px; }"
        "QLabel { color: " + p["banner_text"] + "; font-weight: 600; border: none; }"
    )

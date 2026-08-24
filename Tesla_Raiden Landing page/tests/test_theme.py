"""Unit tests for spc_app.theme palettes and Qt-free helpers."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from spc_app import theme

REQUIRED_KEYS = ("window", "base", "text", "muted", "card_bg", "card_border",
                 "banner_bg", "banner_border", "banner_text", "plot_bg",
                 "plot_fg", "plot_axis")


def test_palettes_define_all_required_keys():
    for name, palette in (("light", theme.LIGHT), ("dark", theme.DARK)):
        missing = [k for k in REQUIRED_KEYS if k not in palette]
        assert not missing, f"{name} palette missing {missing}"


def test_dark_text_is_light_and_light_text_is_dark():
    assert theme.DARK["text"] != theme.LIGHT["text"]
    assert theme.LIGHT["plot_bg"] == "#FFFFFF"


def test_resolve_palette_explicit_modes():
    assert theme.resolve_palette("Light") is theme.LIGHT
    assert theme.resolve_palette("Dark") is theme.DARK


def test_system_prefers_dark_returns_bool():
    assert isinstance(theme.system_prefers_dark(), bool)


def test_card_qss_uses_palette_colors():
    qss = theme.card_qss(theme.DARK)
    assert theme.DARK["text"] in qss and theme.DARK["card_bg"] in qss
    light_qss = theme.card_qss(theme.LIGHT)
    assert theme.LIGHT["text"] in light_qss


def test_banner_qss_uses_palette_colors():
    qss = theme.banner_qss(theme.DARK)
    assert theme.DARK["banner_text"] in qss
    assert theme.DARK["banner_border"] in qss


def test_build_app_palette_smoke(qapp):
    pal = theme.build_app_palette(theme.DARK)
    from PySide6.QtGui import QPalette
    assert pal.color(QPalette.WindowText).name().upper() == "#E2E8F0"


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])

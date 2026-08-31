"""تست‌های مربوط به تم، پالت و QSS مرکزی برنامه."""

from __future__ import annotations

import pytest

pytest.importorskip(
    "PySide6.QtWidgets",
    exc_type=ImportError,
    reason="PySide6 not available in test environment",
)
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from app.ui import theme


def _contrast_ratio(foreground: QColor, background: QColor) -> float:
    foreground_luminance = theme.relative_luminance(foreground)
    background_luminance = theme.relative_luminance(background)
    lighter = max(foreground_luminance, background_luminance)
    darker = min(foreground_luminance, background_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def test_apply_theme_switches_between_light_and_dark_palettes() -> None:
    app = QApplication.instance() or QApplication([])

    light_theme = theme.apply_theme(app, "light")
    light_window = app.palette().color(QPalette.ColorRole.Window)
    light_base = app.palette().color(QPalette.ColorRole.Base)
    light_highlight = app.palette().color(QPalette.ColorRole.Highlight)
    light_stylesheet = app.styleSheet()

    dark_theme = theme.apply_theme(app, "dark")
    dark_window = app.palette().color(QPalette.ColorRole.Window)
    dark_base = app.palette().color(QPalette.ColorRole.Base)
    dark_highlight = app.palette().color(QPalette.ColorRole.Highlight)
    dark_stylesheet = app.styleSheet()

    assert light_theme.mode == "light"
    assert dark_theme.mode == "dark"
    assert dark_window != light_window
    assert dark_window.value() < light_window.value()
    assert light_stylesheet
    assert dark_stylesheet
    assert dark_stylesheet != light_stylesheet

    assert dark_window == dark_theme.window
    assert dark_base == dark_theme.card
    assert dark_highlight == dark_theme.accent

    assert light_window == light_theme.window
    assert light_base == light_theme.card
    assert light_highlight == light_theme.accent


def test_apply_theme_is_idempotent_and_replaces_ad_hoc_stylesheet() -> None:
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet("QWidget { background: red; }")

    first_palette_theme = theme.apply_theme(app, "dark")
    first_window_color = app.palette().color(QPalette.ColorRole.Window)
    first_stylesheet = app.styleSheet()

    second_palette_theme = theme.apply_theme(app, "dark")
    second_window_color = app.palette().color(QPalette.ColorRole.Window)
    second_stylesheet = app.styleSheet()

    assert first_palette_theme.mode == "dark"
    assert second_palette_theme.mode == "dark"
    assert first_window_color == second_window_color
    assert first_stylesheet
    assert second_stylesheet == first_stylesheet
    assert "background: red" not in second_stylesheet


def test_build_stylesheet_resolves_theme_tokens() -> None:
    dark_theme = theme.build_dark_theme()

    stylesheet = theme.build_stylesheet(dark_theme)

    assert stylesheet
    assert dark_theme.colors.background in stylesheet
    assert dark_theme.colors.card in stylesheet
    assert dark_theme.colors.primary in stylesheet
    assert "{background}" not in stylesheet
    assert "{card}" not in stylesheet
    assert "{primary}" not in stylesheet


def test_primary_button_white_text_has_accessible_contrast_in_both_modes() -> None:
    white = QColor("#ffffff")

    for mode in ("light", "dark"):
        accent = theme.build_theme(mode).accent
        assert _contrast_ratio(white, accent) >= 4.5

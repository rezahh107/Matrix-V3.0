"""تست‌های مربوط به تم، پالت و QSS مرکزی برنامه."""

from __future__ import annotations

import pytest

try:
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QApplication, QHBoxLayout, QPushButton
except ImportError as exc:
    pytest.skip(f"PySide6 unavailable: {exc}", allow_module_level=True)

from app.ui import theme
from app.ui.widgets import FilePicker


_CANONICAL_STYLESHEET_TOKENS = (
    "background",
    "surface_primary",
    "surface_secondary",
    "control_surface",
    "control_hover",
    "boundary_subtle",
    "boundary_control",
    "text_primary",
    "text_secondary",
    "accent",
    "accent_hover",
    "accent_pressed",
    "focus",
    "selection",
    "success",
    "warning",
    "error",
    "disabled_text",
    "disabled_surface",
    "diagnostic_background",
    "diagnostic_text",
    "caption_size",
    "body_size",
    "body_strong_size",
    "subtitle_size",
    "title_size",
    "micro",
    "icon_to_text",
    "label_to_control",
    "within_group",
    "between_groups",
    "section_spacing",
    "panel_padding",
    "cta_separation",
    "control_radius",
    "container_radius",
)


def _contrast_ratio(foreground: QColor, background: QColor) -> float:
    foreground_luminance = theme.relative_luminance(foreground)
    background_luminance = theme.relative_luminance(background)
    lighter = max(foreground_luminance, background_luminance)
    darker = min(foreground_luminance, background_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def _palette_snapshot(app: QApplication) -> dict[QPalette.ColorRole, QColor]:
    palette = app.palette()
    return {
        role: palette.color(role)
        for role in (
            QPalette.ColorRole.Window,
            QPalette.ColorRole.Base,
            QPalette.ColorRole.AlternateBase,
            QPalette.ColorRole.Highlight,
            QPalette.ColorRole.HighlightedText,
            QPalette.ColorRole.Link,
        )
    }


def _assert_palette_matches_theme(
    palette: dict[QPalette.ColorRole, QColor], resolved_theme: theme.Theme
) -> None:
    colors = resolved_theme.colors
    assert palette[QPalette.ColorRole.Window] == QColor(colors.background)
    assert palette[QPalette.ColorRole.Base] == QColor(colors.control_surface)
    assert palette[QPalette.ColorRole.AlternateBase] == QColor(colors.surface_secondary)
    assert palette[QPalette.ColorRole.Highlight] == QColor(colors.selection)
    assert palette[QPalette.ColorRole.HighlightedText] == QColor(colors.text_primary)
    assert palette[QPalette.ColorRole.Link] == QColor(colors.accent)


def test_apply_theme_switches_between_light_and_dark_palettes() -> None:
    app = QApplication.instance() or QApplication([])

    light_theme = theme.apply_theme(app, "light")
    light_palette = _palette_snapshot(app)
    light_stylesheet = app.styleSheet()

    dark_theme = theme.apply_theme(app, "dark")
    dark_palette = _palette_snapshot(app)
    dark_stylesheet = app.styleSheet()

    assert light_theme.mode == "light"
    assert dark_theme.mode == "dark"
    assert dark_palette[QPalette.ColorRole.Window] != light_palette[QPalette.ColorRole.Window]
    assert (
        dark_palette[QPalette.ColorRole.Window].value()
        < light_palette[QPalette.ColorRole.Window].value()
    )
    assert light_stylesheet
    assert dark_stylesheet
    assert dark_stylesheet != light_stylesheet

    _assert_palette_matches_theme(light_palette, light_theme)
    _assert_palette_matches_theme(dark_palette, dark_theme)


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
    assert dark_theme.colors.control_surface in stylesheet
    assert dark_theme.colors.surface_secondary in stylesheet
    assert dark_theme.colors.selection in stylesheet
    assert dark_theme.colors.text_primary in stylesheet
    assert dark_theme.colors.accent in stylesheet

    assert "QComboBox#themeSelector" in stylesheet
    assert "QComboBox::drop-down" in stylesheet
    assert "QComboBox::down-arrow" in stylesheet
    assert 'QPushButton[variant="primary"]' in stylesheet
    assert 'QPushButton[variant="secondary"]' in stylesheet
    assert "QPushButton:disabled" in stylesheet

    for token in _CANONICAL_STYLESHEET_TOKENS:
        assert "{" + token + "}" not in stylesheet


def test_file_picker_preserves_path_space_and_browse_button_proportion() -> None:
    app = QApplication.instance() or QApplication([])
    picker = FilePicker()
    layout = picker.layout()
    browse_button = picker.findChild(QPushButton, "secondaryButton")

    assert app is not None
    assert isinstance(layout, QHBoxLayout)
    assert layout.spacing() == 10
    assert layout.stretch(1) == 1
    assert browse_button is not None
    assert browse_button.minimumWidth() == 92


def test_primary_button_white_text_has_accessible_contrast_in_both_modes() -> None:
    white = QColor("#ffffff")

    for mode in ("light", "dark"):
        accent = theme.build_theme(mode).accent
        assert _contrast_ratio(white, accent) >= 4.5

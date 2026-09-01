"""Central Matrix Qt presentation tokens and application-level theme authority."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from app.ui.fonts import create_app_font
from app.ui.i18n import Language

__all__ = [
    "BASE_FONT_PT",
    "ThemeColors",
    "ThemeTypography",
    "Theme",
    "apply_layout_direction",
    "apply_global_font",
    "apply_palette",
    "apply_theme",
    "build_dark_theme",
    "build_light_theme",
    "relative_luminance",
    "contrast_ratio",
    "apply_card_shadow",
    "setup_button_hover_animation",
    "build_theme",
    "build_stylesheet",
    "apply_theme_mode",
]

BASE_FONT_PT = 10
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ThemeColors:
    """Canonical V2 semantic color roles. Compatibility aliases are properties only."""

    background: str = "#F4F6F8"
    surface_primary: str = "#FFFFFF"
    surface_secondary: str = "#E6EBF1"
    control_surface: str = "#FFFFFF"
    control_hover: str = "#F2F5F9"
    boundary_subtle: str = "#D5DCE5"
    boundary_control: str = "#7A8798"
    text_primary: str = "#182230"
    text_secondary: str = "#526174"
    accent: str = "#1F5FBF"
    accent_hover: str = "#184F9F"
    accent_pressed: str = "#123D7D"
    focus: str = "#0B57D0"
    selection: str = "#D9E8FF"
    success: str = "#146C43"
    warning: str = "#8A4B08"
    error: str = "#B42318"
    disabled_text: str = "#7A8796"
    disabled_surface: str = "#E9EDF2"
    diagnostic_background: str = "#EEF2F6"
    diagnostic_text: str = "#253347"

    @property
    def card(self) -> str:
        return self.surface_primary

    @property
    def surface_alt(self) -> str:
        return self.surface_secondary

    @property
    def subtle_boundary(self) -> str:
        return self.boundary_subtle

    @property
    def control_boundary(self) -> str:
        return self.boundary_control

    @property
    def focus_indicator(self) -> str:
        return self.focus

    @property
    def text(self) -> str:
        return self.text_primary

    @property
    def text_muted(self) -> str:
        return self.text_secondary

    @property
    def primary(self) -> str:
        return self.accent

    @property
    def primary_hover(self) -> str:
        return self.accent_hover

    @property
    def primary_pressed(self) -> str:
        return self.accent_pressed

    @property
    def primary_soft(self) -> str:
        return self.selection

    @property
    def warning_surface(self) -> str:
        return self.surface_secondary

    @property
    def log_background(self) -> str:
        return self.diagnostic_background

    @property
    def log_foreground(self) -> str:
        return self.diagnostic_text

    @property
    def log_border(self) -> str:
        return self.boundary_subtle

    @property
    def log_success(self) -> str:
        return self.success

    @property
    def log_warning(self) -> str:
        return self.warning

    @property
    def log_error(self) -> str:
        return self.error

    @property
    def border(self) -> str:
        return self.boundary_control


@dataclass(frozen=True)
class ThemeTypography:
    """V2 semantic typography roles, in points."""

    font_fa_stack: str = "Vazirmatn, Vazir, Tahoma, sans-serif"
    font_en_stack: str = "Segoe UI, Arial, sans-serif"
    caption_size: int = 9
    body_size: int = 10
    body_strong_size: int = 10
    subtitle_size: int = 11
    title_size: int = 13
    regular_weight: int = 400
    strong_weight: int = 600

    @property
    def card_title_size(self) -> int:
        return self.subtitle_size


@dataclass(frozen=True)
class Theme:
    """Complete Matrix V2 presentation token bundle."""

    colors: ThemeColors = ThemeColors()
    typography: ThemeTypography = ThemeTypography()
    mode: str = "light"

    micro: int = 4
    icon_to_text: int = 6
    label_to_control: int = 8
    control_to_control: int = 8
    field_to_field: int = 8
    within_group: int = 12
    between_groups: int = 16
    section_spacing: int = 20
    page_margin_normal: int = 20
    page_margin_compact: int = 16
    panel_padding: int = 12
    cta_separation: int = 16
    control_radius: int = 6
    container_radius: int = 8

    @property
    def spacing_base(self) -> int:
        return self.label_to_control

    @property
    def spacing_xs(self) -> int:
        return self.micro

    @property
    def spacing_sm(self) -> int:
        return self.label_to_control

    @property
    def spacing_md(self) -> int:
        return self.within_group

    @property
    def spacing_lg(self) -> int:
        return self.between_groups

    @property
    def spacing_xl(self) -> int:
        return self.section_spacing

    @property
    def radius_sm(self) -> int:
        return self.control_radius

    @property
    def radius_md(self) -> int:
        return self.container_radius

    @property
    def radius_lg(self) -> int:
        # Compatibility alias only. V2 intentionally has no routine third radius tier.
        return self.container_radius

    @property
    def accent_soft(self) -> QColor:
        return QColor(self.colors.selection)

    @property
    def window(self) -> QColor:
        return QColor(self.colors.background)

    @property
    def surface(self) -> QColor:
        return QColor(self.colors.surface_primary)

    @property
    def surface_alt(self) -> QColor:
        return QColor(self.colors.surface_secondary)

    @property
    def card(self) -> QColor:
        return QColor(self.colors.surface_primary)

    @property
    def accent(self) -> QColor:
        return QColor(self.colors.accent)

    @property
    def border(self) -> QColor:
        return QColor(self.colors.boundary_control)

    @property
    def subtle_boundary(self) -> QColor:
        return QColor(self.colors.boundary_subtle)

    @property
    def focus_indicator(self) -> QColor:
        return QColor(self.colors.focus)

    @property
    def text_primary(self) -> QColor:
        return QColor(self.colors.text_primary)

    @property
    def text_muted(self) -> QColor:
        return QColor(self.colors.text_secondary)

    @property
    def success(self) -> QColor:
        return QColor(self.colors.success)

    @property
    def success_soft(self) -> QColor:
        return QColor(self.colors.surface_secondary)

    @property
    def warning(self) -> QColor:
        return QColor(self.colors.warning)

    @property
    def error(self) -> QColor:
        return QColor(self.colors.error)

    @property
    def log_bg(self) -> QColor:
        return QColor(self.colors.diagnostic_background)

    @property
    def log_border(self) -> QColor:
        return QColor(self.colors.boundary_subtle)

    @property
    def log_text(self) -> QColor:
        return QColor(self.colors.diagnostic_text)


def apply_global_font(app: QApplication) -> None:
    """Apply the one application base-font authority for the current UI direction."""

    is_rtl = app.layoutDirection() == Qt.LayoutDirection.RightToLeft
    font = create_app_font(
        point_size=BASE_FONT_PT,
        fallback_family="Tahoma" if is_rtl else "Segoe UI",
        prefer_vazir=is_rtl,
    )
    app.setFont(font)


def apply_palette(app: QApplication, theme: Theme) -> None:
    app.setPalette(_create_palette_from_theme(theme))


def _create_palette_from_theme(theme: Theme) -> QPalette:
    colors = theme.colors
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(colors.background))
    palette.setColor(QPalette.ColorRole.Base, QColor(colors.control_surface))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors.surface_secondary))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(colors.surface_primary))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(colors.text_primary))
    palette.setColor(QPalette.ColorRole.Text, QColor(colors.text_primary))
    palette.setColor(QPalette.ColorRole.Button, QColor(colors.control_surface))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors.text_primary))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(colors.text_primary))
    palette.setColor(QPalette.ColorRole.Mid, QColor(colors.boundary_control))
    palette.setColor(QPalette.ColorRole.Dark, QColor(colors.boundary_subtle))
    palette.setColor(QPalette.ColorRole.Midlight, QColor(colors.surface_secondary))
    palette.setColor(QPalette.ColorRole.Light, QColor(colors.surface_primary))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(colors.selection))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(colors.text_primary))
    palette.setColor(QPalette.ColorRole.Link, QColor(colors.accent))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(colors.error))

    disabled = QPalette.ColorGroup.Disabled
    palette.setColor(disabled, QPalette.ColorRole.Text, QColor(colors.disabled_text))
    palette.setColor(disabled, QPalette.ColorRole.ButtonText, QColor(colors.disabled_text))
    palette.setColor(disabled, QPalette.ColorRole.WindowText, QColor(colors.disabled_text))
    palette.setColor(disabled, QPalette.ColorRole.Button, QColor(colors.disabled_surface))
    palette.setColor(disabled, QPalette.ColorRole.Base, QColor(colors.disabled_surface))
    return palette


def _stylesheet_token_mapping(theme: Theme) -> dict[str, str]:
    colors = theme.colors
    typography = theme.typography
    return {
        "background": colors.background,
        "surface_primary": colors.surface_primary,
        "surface_secondary": colors.surface_secondary,
        "control_surface": colors.control_surface,
        "control_hover": colors.control_hover,
        "boundary_subtle": colors.boundary_subtle,
        "boundary_control": colors.boundary_control,
        "text_primary": colors.text_primary,
        "text_secondary": colors.text_secondary,
        "accent": colors.accent,
        "accent_hover": colors.accent_hover,
        "accent_pressed": colors.accent_pressed,
        "focus": colors.focus,
        "selection": colors.selection,
        "success": colors.success,
        "warning": colors.warning,
        "error": colors.error,
        "disabled_text": colors.disabled_text,
        "disabled_surface": colors.disabled_surface,
        "diagnostic_background": colors.diagnostic_background,
        "diagnostic_text": colors.diagnostic_text,
        "caption_size": str(typography.caption_size),
        "body_size": str(typography.body_size),
        "body_strong_size": str(typography.body_strong_size),
        "subtitle_size": str(typography.subtitle_size),
        "title_size": str(typography.title_size),
        "micro": str(theme.micro),
        "icon_to_text": str(theme.icon_to_text),
        "label_to_control": str(theme.label_to_control),
        "within_group": str(theme.within_group),
        "between_groups": str(theme.between_groups),
        "section_spacing": str(theme.section_spacing),
        "panel_padding": str(theme.panel_padding),
        "cta_separation": str(theme.cta_separation),
        "control_radius": str(theme.control_radius),
        "container_radius": str(theme.container_radius),
        # Legacy token names map to the canonical roles; they are not independent sources.
        "card": colors.surface_primary,
        "surface_alt": colors.surface_secondary,
        "subtle_boundary": colors.boundary_subtle,
        "control_boundary": colors.boundary_control,
        "focus_indicator": colors.focus,
        "text": colors.text_primary,
        "text_muted": colors.text_secondary,
        "primary": colors.accent,
        "primary_hover": colors.accent_hover,
        "primary_pressed": colors.accent_pressed,
        "primary_soft": colors.selection,
        "warning_surface": colors.surface_secondary,
        "log_background": colors.diagnostic_background,
        "log_foreground": colors.diagnostic_text,
        "log_border": colors.boundary_subtle,
        "border": colors.boundary_control,
        "card_title_size": str(typography.subtitle_size),
        "spacing_xs": str(theme.micro),
        "spacing_sm": str(theme.label_to_control),
        "spacing_md": str(theme.within_group),
        "spacing_lg": str(theme.between_groups),
        "radius_sm": str(theme.control_radius),
        "radius_md": str(theme.container_radius),
        "radius_lg": str(theme.container_radius),
    }


def build_stylesheet(theme: Theme) -> str:
    qss_path = Path(__file__).with_name("styles.qss")
    try:
        rendered = qss_path.read_text(encoding="utf-8")
    except OSError:
        LOGGER.exception("Unable to load UI stylesheet: %s", qss_path)
        return ""
    for token, value in _stylesheet_token_mapping(theme).items():
        rendered = rendered.replace("{" + token + "}", value)
    return rendered


def apply_theme(app: QApplication, theme: Theme | str | None = None) -> Theme:
    """Apply Fusion behavior plus the Matrix-owned palette/QSS presentation."""

    app.setStyle("Fusion")
    resolved = theme if isinstance(theme, Theme) else build_theme(theme or "light")
    apply_global_font(app)
    app.setPalette(_create_palette_from_theme(resolved))
    app.setStyleSheet(build_stylesheet(resolved))
    return resolved


def apply_layout_direction(app: QApplication, language: Language | str) -> None:
    lang_enum = language if isinstance(language, Language) else Language.from_code(language)
    app.setLayoutDirection(
        Qt.LayoutDirection.RightToLeft if lang_enum is Language.FA else Qt.LayoutDirection.LeftToRight
    )
    apply_global_font(app)


def apply_card_shadow(widget: QWidget) -> None:
    """Compatibility seam: V2 deliberately removes routine same-plane shadows."""

    widget.setGraphicsEffect(None)


def setup_button_hover_animation(button: QPushButton) -> None:
    """Compatibility seam: V2 hover is state color only; no opacity animation."""

    button.setProperty("matrixDecorativeHoverAnimation", False)


def build_theme(mode: str | None = None) -> Theme:
    normalized = "dark" if (mode or "").lower() == "dark" else "light"
    if normalized == "dark":
        colors = ThemeColors(
            background="#0F141A",
            surface_primary="#171E26",
            surface_secondary="#202A35",
            control_surface="#1B2632",
            control_hover="#243342",
            boundary_subtle="#33404D",
            boundary_control="#7A8A9D",
            text_primary="#E7EDF4",
            text_secondary="#A9B6C4",
            accent="#2F67CA",
            accent_hover="#356FD3",
            accent_pressed="#2E65C7",
            focus="#73A9FF",
            selection="#233B5B",
            success="#4FC38A",
            warning="#F0C04A",
            error="#FF7A73",
            disabled_text="#7E8B99",
            disabled_surface="#202832",
            diagnostic_background="#111820",
            diagnostic_text="#D7E0EA",
        )
    else:
        colors = ThemeColors()
    return Theme(colors=colors, mode=normalized)


def build_light_theme() -> Theme:
    return build_theme("light")


def build_dark_theme() -> Theme:
    return build_theme("dark")


def relative_luminance(color: QColor | str) -> float:
    """WCAG relative luminance using the sRGB 0.04045 breakpoint."""

    resolved = QColor(color) if isinstance(color, str) else color

    def _channel(value: int) -> float:
        srgb = value / 255.0
        return srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4

    return (
        0.2126 * _channel(resolved.red())
        + 0.7152 * _channel(resolved.green())
        + 0.0722 * _channel(resolved.blue())
    )


def contrast_ratio(foreground: QColor | str, background: QColor | str) -> float:
    fg = relative_luminance(foreground)
    bg = relative_luminance(background)
    lighter, darker = max(fg, bg), min(fg, bg)
    return (lighter + 0.05) / (darker + 0.05)


def apply_theme_mode(app: QApplication, mode: str | None = None) -> Theme:
    return apply_theme(app, build_theme(mode or "light"))

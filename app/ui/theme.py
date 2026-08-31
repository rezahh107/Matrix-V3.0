"""مدیریت تم سبک با توکن‌های مرکزی برای UI PySide6.

این ماژول تم روشن/تیره، پالت Qt و QSS مرکزی را از یک مجموعه توکن واحد
تولید می‌کند. هدف، یکپارچگی بصری بدون تغییر رفتار ویجت‌ها یا جریان برنامه است.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from app.ui.effects import SafeDropShadowEffect
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
    "apply_card_shadow",
    "setup_button_hover_animation",
    "build_theme",
    "build_stylesheet",
    "apply_theme_mode",
]

BASE_FONT_PT = 9
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ThemeColors:
    """توکن‌های رنگی بر اساس نقش بصری، نه نوع ویجت."""

    background: str = "#f3f5f7"
    card: str = "#ffffff"
    surface_alt: str = "#edf1f5"
    subtle_boundary: str = "#dfe5ec"
    control_boundary: str = "#aeb8c5"
    focus_indicator: str = "#1d4ed8"
    control_hover: str = "#f7f9fc"
    text: str = "#172033"
    text_muted: str = "#667085"
    primary: str = "#2563eb"
    primary_hover: str = "#1d4ed8"
    primary_pressed: str = "#1e40af"
    success: str = "#15803d"
    warning: str = "#8a4b08"
    warning_surface: str = "#fff7ed"
    error: str = "#c2413a"
    log_background: str = "#f7f9fc"
    log_foreground: str = "#253047"
    log_border: str = "#d7dde6"
    log_success: str = "#15803d"
    log_warning: str = "#a15c07"
    log_error: str = "#b42318"
    # Backward-compatible token retained for callers/tests; interactive controls
    # should use control_boundary and decorative surfaces subtle_boundary.
    border: str = "#aeb8c5"


@dataclass(frozen=True)
class ThemeTypography:
    """مقیاس تایپوگرافی واحد برای فارسی و انگلیسی."""

    font_fa_stack: str = "Vazirmatn, Vazir, IRANSansX, Tahoma, sans-serif"
    font_en_stack: str = "Segoe UI, system-ui, sans-serif"
    title_size: int = 13
    card_title_size: int = 11
    body_size: int = BASE_FONT_PT


@dataclass(frozen=True)
class Theme:
    """بستهٔ توکن‌های تم شامل رنگ، تایپوگرافی و فاصله."""

    colors: ThemeColors = ThemeColors()
    typography: ThemeTypography = ThemeTypography()
    spacing_base: int = 8
    radius_sm: int = 6
    radius_md: int = 10
    radius_lg: int = 14
    mode: str = "light"

    @property
    def spacing_xs(self) -> int:
        return max(2, self.spacing_base // 2)

    @property
    def spacing_sm(self) -> int:
        return self.spacing_base

    @property
    def spacing_md(self) -> int:
        return int(self.spacing_base * 1.5)

    @property
    def spacing_lg(self) -> int:
        return self.spacing_base * 2

    @property
    def spacing_xl(self) -> int:
        return int(self.spacing_base * 3)

    @property
    def accent_soft(self) -> QColor:
        base = QColor(self.colors.primary)
        soft = QColor(base)
        soft.setAlphaF(0.12)
        return soft

    @property
    def window(self) -> QColor:
        return QColor(self.colors.background)

    @property
    def surface(self) -> QColor:
        return QColor(self.colors.card)

    @property
    def surface_alt(self) -> QColor:
        return QColor(self.colors.surface_alt)

    @property
    def card(self) -> QColor:
        return QColor(self.colors.card)

    @property
    def accent(self) -> QColor:
        return QColor(self.colors.primary)

    @property
    def border(self) -> QColor:
        return QColor(self.colors.control_boundary)

    @property
    def subtle_boundary(self) -> QColor:
        return QColor(self.colors.subtle_boundary)

    @property
    def focus_indicator(self) -> QColor:
        return QColor(self.colors.focus_indicator)

    @property
    def text_primary(self) -> QColor:
        return QColor(self.colors.text)

    @property
    def text_muted(self) -> QColor:
        return QColor(self.colors.text_muted)

    @property
    def success(self) -> QColor:
        return QColor(self.colors.success)

    @property
    def success_soft(self) -> QColor:
        base = QColor(self.colors.success).darker(110)
        base.setAlpha(90)
        return base

    @property
    def warning(self) -> QColor:
        return QColor(self.colors.warning)

    @property
    def error(self) -> QColor:
        return QColor(self.colors.error)

    @property
    def log_bg(self) -> QColor:
        return QColor(self.colors.log_background)

    @property
    def log_border(self) -> QColor:
        return QColor(self.colors.log_border)

    @property
    def log_text(self) -> QColor:
        return QColor(self.colors.log_foreground)


def apply_global_font(app: QApplication) -> None:
    """اعمال فونت پایهٔ Regular برنامه بر اساس وزیر یا تاهوما."""

    app.setFont(create_app_font(point_size=BASE_FONT_PT))


def apply_palette(app: QApplication, theme: Theme) -> None:
    """تنظیم پالت هماهنگ با توکن‌های تم."""

    app.setPalette(_create_palette_from_theme(theme))


def _create_palette_from_theme(theme: Theme) -> QPalette:
    """ساخت پالت Fusion برای سطوح و complex controlهای native."""

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, theme.window)
    palette.setColor(QPalette.ColorRole.Base, theme.card)
    palette.setColor(QPalette.ColorRole.AlternateBase, theme.surface_alt)
    palette.setColor(QPalette.ColorRole.ToolTipBase, theme.card)
    palette.setColor(QPalette.ColorRole.ToolTipText, theme.text_primary)
    palette.setColor(QPalette.ColorRole.Text, theme.text_primary)
    palette.setColor(QPalette.ColorRole.Button, theme.card)
    palette.setColor(QPalette.ColorRole.ButtonText, theme.text_primary)
    palette.setColor(QPalette.ColorRole.WindowText, theme.text_primary)
    palette.setColor(QPalette.ColorRole.Mid, theme.border)
    palette.setColor(QPalette.ColorRole.Dark, theme.subtle_boundary)
    palette.setColor(QPalette.ColorRole.Midlight, theme.surface_alt)
    palette.setColor(QPalette.ColorRole.Light, theme.card)
    palette.setColor(QPalette.ColorRole.Highlight, theme.accent)
    highlighted_text = QColor("#ffffff")
    if relative_luminance(theme.accent) > 0.55:
        highlighted_text = QColor("#111827")
    palette.setColor(QPalette.ColorRole.HighlightedText, highlighted_text)
    palette.setColor(QPalette.ColorRole.Link, theme.accent)
    palette.setColor(QPalette.ColorRole.BrightText, theme.error)

    disabled = QPalette.ColorGroup.Disabled
    palette.setColor(disabled, QPalette.ColorRole.Text, theme.text_muted)
    palette.setColor(disabled, QPalette.ColorRole.ButtonText, theme.text_muted)
    palette.setColor(disabled, QPalette.ColorRole.WindowText, theme.text_muted)
    palette.setColor(disabled, QPalette.ColorRole.Button, theme.surface_alt)
    palette.setColor(disabled, QPalette.ColorRole.Base, theme.surface_alt)
    return palette


def _qss_rgba(color: QColor) -> str:
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"


def _stylesheet_token_mapping(theme: Theme) -> dict[str, str]:
    """تبدیل توکن‌های Theme به مقادیر قابل‌استفاده در QSS."""

    return {
        "background": theme.colors.background,
        "card": theme.colors.card,
        "surface_alt": theme.colors.surface_alt,
        "subtle_boundary": theme.colors.subtle_boundary,
        "control_boundary": theme.colors.control_boundary,
        "focus_indicator": theme.colors.focus_indicator,
        "control_hover": theme.colors.control_hover,
        "text": theme.colors.text,
        "text_muted": theme.colors.text_muted,
        "primary": theme.colors.primary,
        "primary_hover": theme.colors.primary_hover,
        "primary_pressed": theme.colors.primary_pressed,
        "primary_soft": _qss_rgba(theme.accent_soft),
        "success": theme.colors.success,
        "warning": theme.colors.warning,
        "warning_surface": theme.colors.warning_surface,
        "error": theme.colors.error,
        "log_background": theme.colors.log_background,
        "log_foreground": theme.colors.log_foreground,
        "log_border": theme.colors.log_border,
        "border": theme.colors.border,
        "title_size": str(theme.typography.title_size),
        "card_title_size": str(theme.typography.card_title_size),
        "body_size": str(theme.typography.body_size),
        "spacing_xs": str(theme.spacing_xs),
        "spacing_sm": str(theme.spacing_sm),
        "spacing_md": str(theme.spacing_md),
        "spacing_lg": str(theme.spacing_lg),
        "radius_sm": str(theme.radius_sm),
        "radius_md": str(theme.radius_md),
        "radius_lg": str(theme.radius_lg),
    }


def build_stylesheet(theme: Theme) -> str:
    """رندر امن QSS مرکزی بدون تداخل braceهای CSS با قالب‌بندی پایتون."""

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
    """اعمال تم روشن/تیره با Fusion، QPalette و QSS مرکزی."""

    app.setStyle("Fusion")
    apply_global_font(app)

    if isinstance(theme, Theme):
        resolved_theme = theme
    elif isinstance(theme, str):
        resolved_theme = build_theme(theme)
    else:
        resolved_theme = build_theme("light")

    app.setPalette(_create_palette_from_theme(resolved_theme))
    app.setStyleSheet(build_stylesheet(resolved_theme))
    return resolved_theme


def apply_layout_direction(app: QApplication, language: Language | str) -> None:
    """تنظیم جهت چیدمان اپلیکیشن بر اساس زبان."""

    lang_enum = language if isinstance(language, Language) else Language.from_code(language)
    if lang_enum is Language.FA:
        app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    else:
        app.setLayoutDirection(Qt.LayoutDirection.LeftToRight)


def apply_card_shadow(widget: QWidget) -> None:
    """افزودن سایهٔ نرم به کارت‌ها با Qt."""

    shadow = SafeDropShadowEffect(
        f"card_shadow[{widget.objectName() or widget.__class__.__name__}]",
        widget,
    )
    shadow.setBlurRadius(20)
    shadow.setOffset(0, 6)
    shadow.setColor(QColor(0, 0, 0, 28))
    widget.setGraphicsEffect(shadow)
    LOGGER.debug(
        "card_shadow installed | widget=%s effect=%s blur=%s offset=%s",
        widget,
        hex(id(shadow)),
        shadow.blurRadius(),
        shadow.offset(),
    )


class _HoverAnimationFilter(QObject):
    """فیلتر ساده برای انیمیشن Hover دکمه."""

    def __init__(self, button: QPushButton, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._button = button
        self._animation = QPropertyAnimation(button, b"windowOpacity", self)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._animation.setDuration(120)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 - امضای Qt
        if obj is self._button:
            if event.type() == QEvent.Type.Enter:
                self._fade_to(0.94)
            elif event.type() == QEvent.Type.Leave:
                self._fade_to(1.0)
        return super().eventFilter(obj, event)

    def _fade_to(self, value: float) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._button.windowOpacity())
        self._animation.setEndValue(value)
        self._animation.start()


def setup_button_hover_animation(button: QPushButton) -> None:
    """نصب انیمیشن Hover سبک برای دکمه‌ها."""

    filter_ = _HoverAnimationFilter(button, button)
    button.installEventFilter(filter_)
    button.setProperty("_hover_filter", filter_)


def build_theme(mode: str | None = None) -> Theme:
    """ساخت تم بر پایهٔ حالت روشن یا تیره با توکن‌های نقش‌محور."""

    normalized = "dark" if (mode or "").lower() == "dark" else "light"
    if normalized == "dark":
        colors = ThemeColors(
            background="#101419",
            card="#1c2530",
            surface_alt="#242e3a",
            subtle_boundary="#34404d",
            control_boundary="#64748b",
            focus_indicator="#60a5fa",
            control_hover="#273341",
            text="#e6edf3",
            text_muted="#aeb8c5",
            primary="#2563eb",
            primary_hover="#1d4ed8",
            primary_pressed="#1e40af",
            success="#3fb950",
            warning="#facc15",
            warning_surface="#2b2515",
            error="#f47067",
            log_background="#0d1117",
            log_foreground="#d8dee9",
            log_border="#34404d",
            log_success="#3fb950",
            log_warning="#facc15",
            log_error="#f47067",
            border="#64748b",
        )
    else:
        colors = ThemeColors()

    return Theme(colors=colors, typography=ThemeTypography(), mode=normalized)


def build_light_theme() -> Theme:
    """ساخت تم روشن با توکن‌های پیش‌فرض."""

    return build_theme("light")


def build_dark_theme() -> Theme:
    """ساخت تم تیره."""

    return build_theme("dark")


def relative_luminance(color: QColor) -> float:
    """محاسبهٔ روشنایی نسبی رنگ بر اساس استاندارد WCAG."""

    def _channel(value: int) -> float:
        srgb = value / 255
        return srgb / 12.92 if srgb <= 0.03928 else ((srgb + 0.055) / 1.055) ** 2.4

    r = _channel(color.red())
    g = _channel(color.green())
    b = _channel(color.blue())
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def apply_theme_mode(app: QApplication, mode: str | None = None) -> Theme:
    """اعمال تم بر اساس حالت درخواستی."""

    return apply_theme(app, build_theme(mode or "light"))

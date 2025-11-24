"""پنل لاگ با ظاهر هماهنگ و ترجمه‌پذیر."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedLayout,
    QTextEdit,
    QVBoxLayout,
)

from app.ui.fonts import get_app_font
from app.ui.texts import UiTranslator
from app.ui.theme import Theme

__all__ = ["LogPanel"]


class LogPanel(QFrame):
    """ویجت ترکیبی برای نمایش و مدیریت لاگ."""

    def __init__(self, translator: UiTranslator, theme: Theme, parent: QFrame | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("logPanel")
        self._translator = translator
        self._theme = theme

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(theme.spacing_md)

        stack_host = QFrame(self)
        stack_host.setObjectName("logStackHost")
        stack_layout = QStackedLayout(stack_host)
        stack_layout.setContentsMargins(0, 0, 0, 0)
        stack_layout.setStackingMode(QStackedLayout.StackingMode.StackAll)

        self._placeholder = QLabel(
            self._t("log.placeholder", "🗒️ هنوز گزارشی ثبت نشده است."),
            stack_host,
        )
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setObjectName("logPlaceholder")
        self._placeholder.setWordWrap(True)
        self._placeholder.setFont(get_app_font())

        self._text = QTextEdit(self)
        self._text.setReadOnly(True)
        self._text.setObjectName("textLog")
        self._text.setFont(get_app_font())

        stack_layout.addWidget(self._placeholder)
        stack_layout.addWidget(self._text)
        self._stack = stack_layout
        self._text.textChanged.connect(self._sync_placeholder)
        self._sync_placeholder()

        root.addWidget(stack_host, 1)

        buttons_col = QVBoxLayout()
        buttons_col.setSpacing(theme.spacing_md)
        self._btn_clear = QPushButton(self._t("log.clear", "پاک کردن گزارش"), self)
        self._btn_clear.setObjectName("btnClearLog")
        self._btn_clear.setProperty("variant", "secondary")
        self._btn_save = QPushButton(self._t("log.save", "ذخیره گزارش…"), self)
        self._btn_save.setObjectName("btnSaveLog")
        self._btn_save.setProperty("variant", "secondary")
        buttons_col.addWidget(self._btn_clear)
        buttons_col.addWidget(self._btn_save)
        buttons_col.addStretch(1)
        root.addLayout(buttons_col, 0)

        self.apply_theme(theme)

    # ------------------------------------------------------------------ رابط دسترسی
    @property
    def text_edit(self) -> QTextEdit:
        """دسترسی مستقیم به QTextEdit داخلی."""

        return self._text

    @property
    def clear_button(self) -> QPushButton:
        """دریافت دکمه پاک‌سازی."""

        return self._btn_clear

    @property
    def save_button(self) -> QPushButton:
        """دریافت دکمه ذخیره."""

        return self._btn_save

    # ------------------------------------------------------------------ ترجمه و تم
    def update_translator(self, translator: UiTranslator) -> None:
        """به‌روزرسانی متن‌های نمایش داده شده بر اساس مترجم جدید."""

        self._translator = translator
        self._btn_clear.setText(self._t("log.clear", "پاک کردن گزارش"))
        self._btn_save.setText(self._t("log.save", "ذخیره گزارش…"))
        self._placeholder.setText(
            self._t("log.placeholder", "🗒️ هنوز گزارشی ثبت نشده است."),
        )
        self._sync_placeholder()

    def apply_theme(self, theme: Theme) -> None:
        """اعمال تم روی پس‌زمینه و دکمه‌ها."""

        self._theme = theme
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, theme.log_bg)
        palette.setColor(QPalette.ColorRole.Base, theme.log_bg)
        palette.setColor(QPalette.ColorRole.Text, theme.log_text)
        palette.setColor(QPalette.ColorRole.WindowText, theme.log_text)
        self.setPalette(palette)
        self.setAutoFillBackground(True)

        self.setStyleSheet(
            f"#logPanel{{background:{theme.colors.log_background};"
            f"border:1px solid {theme.colors.log_border};border-radius:{theme.radius_md}px;}}"
            f"#logPlaceholder{{color:{theme.colors.text_muted};}}"
            f"QTextEdit#textLog{{border:none;background:transparent;"
            f"color:{theme.colors.log_foreground};line-height:1.35; padding:{theme.spacing_sm}px;}}"
            f"QPushButton#btnClearLog, QPushButton#btnSaveLog{{"
            f"background:{theme.colors.card};border:1px solid {theme.colors.border};"
            f"border-radius:{theme.radius_sm}px;padding:{theme.spacing_xs}px {theme.spacing_md}px;}}"
            f"QPushButton#btnClearLog:hover, QPushButton#btnSaveLog:hover{{"
            f"background:{theme.colors.surface_alt};}}"
            f"QPushButton#btnClearLog:disabled, QPushButton#btnSaveLog:disabled{{"
            f"opacity:0.65;}}"
        )

    # ------------------------------------------------------------------ داخلی
    def sync_placeholder(self) -> None:
        """همگام‌سازی وضعیت نمایش Placeholder."""

        self._sync_placeholder()

    def _sync_placeholder(self) -> None:
        target = self._text if self._text.toPlainText().strip() else self._placeholder
        self._stack.setCurrentWidget(target)

    def _t(self, key: str, fallback: str) -> str:
        return self._translator.text(key, fallback)

    def connect_clear(self, slot: Callable[[], None]) -> None:
        """اتصال سیگنال پاک کردن به تابع مورد نظر."""

        self._btn_clear.clicked.connect(slot)

    def connect_save(self, slot: Callable[[], None]) -> None:
        """اتصال سیگنال ذخیره به تابع مورد نظر."""

        self._btn_save.clicked.connect(slot)

"""ویجت انتخاب فایل عمومی برای UI."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QFileInfo, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFileDialog,
    QFileIconProvider,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from app.ui.texts import UiTranslator

__all__ = ["FilePicker"]


class FilePicker(QWidget):
    """ویجت ساده برای انتخاب مسیر فایل ورودی یا خروجی."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        save: bool = False,
        placeholder: str = "",
        dialog_filter: str = "Excel/CSV (*.xlsx *.xls *.xlsm *.csv);;All Files (*.*)",
        translator: UiTranslator | None = None,
    ) -> None:
        super().__init__(parent)
        self._save = save
        self._dialog_filter = dialog_filter
        self._translator = translator
        self._icon_provider = QFileIconProvider()

        self._edit = QLineEdit(self)
        self._edit.setPlaceholderText(placeholder)
        self._edit.setAlignment(Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignVCenter)
        self._edit.textChanged.connect(self._sync_icon)

        self._button = QPushButton(self._t("action.browse", "انتخاب…"), self)
        self._button.setObjectName("secondaryButton")
        self._button.setMinimumWidth(92)
        self._button.clicked.connect(self._pick)

        self._icon_label = QLabel(self)
        self._icon_label.setObjectName("fileIconLabel")
        self._icon_label.setFixedWidth(20)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self._icon_label)
        layout.addWidget(self._edit, 1)
        layout.addWidget(self._button)

        self._sync_icon("")

    def update_translator(self, translator: UiTranslator) -> None:
        """به‌روزرسانی متن‌های خود FilePicker بدون تغییر دادهٔ انتخاب‌شده."""

        self._translator = translator
        self._button.setText(self._t("action.browse", "انتخاب…"))

    def set_placeholder_text(self, text: str) -> None:
        self._edit.setPlaceholderText(text)

    def set_button_text(self, text: str) -> None:
        self._button.setText(text)

    def text(self) -> str:
        return self._edit.text().strip()

    def path(self) -> Path:
        return Path(self.text()) if self.text() else Path()

    def setText(self, value: str) -> None:  # noqa: N802 - امضای Qt
        self._edit.setText(value)

    def blockSignals(self, block: bool) -> bool:  # noqa: N802 - امضای Qt
        blocked = super().blockSignals(block)
        self._edit.blockSignals(block)
        return blocked

    def line_edit(self) -> QLineEdit:
        return self._edit

    def _pick(self) -> None:
        """باز کردن دیالوگ انتخاب فایل و مقداردهی فیلد."""

        if self._save:
            path, _ = QFileDialog.getSaveFileName(
                self,
                self._t("file_picker.save_title", "ذخیره خروجی"),
                "",
                self._dialog_filter,
            )
        else:
            path, _ = QFileDialog.getOpenFileName(
                self,
                self._t("file_picker.open_title", "انتخاب فایل"),
                "",
                self._dialog_filter,
            )

        if path:
            self._edit.setText(path)

    def _sync_icon(self, text: str) -> None:
        """همگام‌سازی آیکون native فایل/پوشه بر اساس مسیر فعلی."""

        self._icon_label.clear()
        if not text:
            icon = self._icon_provider.icon(QFileIconProvider.IconType.Folder)
            self._icon_label.setPixmap(icon.pixmap(16, 16))
            return
        info = QFileInfo(text)
        icon: QIcon = self._icon_provider.icon(info)
        self._icon_label.setPixmap(icon.pixmap(16, 16))

    def _t(self, key: str, fallback: str) -> str:
        if self._translator is None:
            return fallback
        return self._translator.text(key, fallback)

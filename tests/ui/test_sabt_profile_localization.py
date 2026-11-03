from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from app.ui.i18n import Language
from app.ui.main_window import MainWindow


def test_sabt_profile_picker_localizes_without_changing_selected_path(qapp) -> None:
    window = MainWindow()
    original_direction = qapp.layoutDirection()
    selected = "C:/synthetic/sabt-profile.xlsx"
    try:
        picker = window._picker_sabt_profile_alloc
        picker.setText(selected)
        hint = window.findChild(QLabel, "sabtAutoTemplateHint")
        assert hint is not None
        for language, direction, snippet in (
            (Language.FA, Qt.LayoutDirection.RightToLeft, "پروفایل"),
            (Language.EN, Qt.LayoutDirection.LeftToRight, "profile"),
            (Language.FA, Qt.LayoutDirection.RightToLeft, "پروفایل"),
        ):
            window._apply_language(language)
            assert qapp.layoutDirection() == direction
            assert snippet.lower() in picker.line_edit().placeholderText().lower()
            assert "نگاشت" in picker.toolTip() if language == Language.FA else (
                "authorized" in picker.toolTip().lower()
            )
            assert picker.line_edit().toolTip() == picker.toolTip()
            labels = [label.text() for label in window.findChildren(QLabel)]
            assert ("فایل پروفایل Sabt" if language == Language.FA else "Sabt export profile") in labels
            assert hint.text()
            assert ("پیش‌بررسی" in hint.text()) if language == Language.FA else (
                "preflight" in hint.text().lower()
            )
            assert picker.text() == selected
            assert picker._button.isEnabled()
    finally:
        qapp.setLayoutDirection(original_direction)
        window.close()
        qapp.processEvents()

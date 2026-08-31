"""Focused falsification tests for MATRIX-UIUX-ROOT-COMPLETE-01."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QPushButton,
    QStyle,
    QStyleOptionComboBox,
    QWidget,
)

from app.ui.i18n import Language
from app.ui.log_panel import LogPanel
from app.ui.main_window import MainWindow
from app.ui.texts import UiTranslator
from app.ui.theme import apply_theme, build_stylesheet, build_theme
from app.ui.widgets.dashboard_card import DashboardCard
from app.ui.widgets.file_picker import FilePicker
from app.ui.widgets.status_bar import ThemedStatusBar

ROOT = Path(__file__).resolve().parents[2]
ACTIVE_TRANSLATION_MODULES = (
    ROOT / "app/ui/main_window.py",
    ROOT / "app/ui/log_panel.py",
    ROOT / "app/ui/database_tab.py",
    ROOT / "app/ui/widgets/file_picker.py",
    ROOT / "app/ui/widgets/health_indicator.py",
)


def _ratio(fg: str, bg: str) -> float:
    def luminance(value: str) -> float:
        c = QColor(value)
        channels = []
        for raw in (c.red(), c.green(), c.blue()):
            x = raw / 255.0
            channels.append(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4)
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    l1, l2 = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def _fresh_settings() -> None:
    settings = QSettings()
    settings.clear()
    settings.sync()


def test_ui_typography_hierarchy(qapp: QApplication) -> None:
    current = build_theme("light")
    apply_theme(qapp, current)
    assert qapp.font().weight() == QFont.Weight.Normal
    qss = build_stylesheet(current)
    assert "font-weight: 600" in qss
    assert "font-weight: 700" in qss
    assert qss.index("font-weight: 400") < qss.index("font-weight: 700")


def test_ui_style_authority_has_no_competing_local_stylesheets(qapp: QApplication) -> None:
    light = build_theme("light")
    dark = build_theme("dark")
    log = LogPanel(UiTranslator("en"), light)
    status = ThemedStatusBar(light)
    card = DashboardCard("Title", "Description", theme=light)
    assert log.styleSheet() == ""
    assert status.styleSheet() == ""
    assert card.styleSheet() == ""
    for widget in (log, status, card):
        widget.apply_theme(dark)
        widget.apply_theme(light)
        assert widget.styleSheet() == ""


def test_ui_contrast_tokens_meet_selected_thresholds() -> None:
    for mode in ("light", "dark"):
        colors = build_theme(mode).colors
        assert _ratio(colors.text, colors.card) >= 4.5
        assert _ratio(colors.warning, colors.warning_surface) >= 4.5
        for background in (colors.primary, colors.primary_hover, colors.primary_pressed):
            assert _ratio("#ffffff", background) >= 4.5
        assert _ratio(colors.focus_indicator, colors.card) >= 3.0
    light = build_theme("light").colors
    dark = build_theme("dark").colors
    assert light.subtle_boundary != light.control_boundary
    assert dark.subtle_boundary != dark.control_boundary
    assert _ratio(dark.card, dark.background) > 1.15


def test_ui_control_states_keep_combo_native_and_states_distinct(qapp: QApplication) -> None:
    current = build_theme("dark")
    qss = build_stylesheet(current)
    assert "QComboBox::drop-down" not in qss
    assert current.colors.primary != current.colors.primary_hover != current.colors.primary_pressed
    assert current.colors.control_hover != current.colors.focus_indicator
    assert current.radius_sm <= 7
    apply_theme(qapp, current)
    combo = QComboBox()
    combo.addItems(["A", "B"])
    combo.resize(180, 32)
    option = QStyleOptionComboBox()
    combo.initStyleOption(option)
    rect = combo.style().subControlRect(
        QStyle.ComplexControl.CC_ComboBox,
        option,
        QStyle.SubControl.SC_ComboBoxArrow,
        combo,
    )
    assert not rect.isEmpty()
    assert rect.width() > 0 and rect.height() > 0


def test_ui_translation_inventory_is_complete_and_reference_keys_are_split() -> None:
    payload = json.loads((ROOT / "resources/translations/ui_texts.json").read_text(encoding="utf-8"))
    assert set(payload["fa"]) == set(payload["en"])
    keys = set(payload["en"])
    referenced: set[str] = set()
    pattern = re.compile(r'(?:_t|\.text)\(\s*["\']([^"\']+)["\']')
    for path in ACTIVE_TRANSLATION_MODULES:
        source = path.read_text(encoding="utf-8")
        referenced.update(pattern.findall(source))
    assert referenced <= keys
    assert "reference.schools.placeholder" in keys
    assert "reference.groupcodes.placeholder" in keys
    assert "reference.allocate.hint" in keys
    assert "reference.hint" not in (ROOT / "app/ui/main_window.py").read_text(encoding="utf-8")


def test_ui_bidi_and_stable_database_identity(qapp: QApplication) -> None:
    _fresh_settings()
    window = MainWindow()
    window._apply_language(Language.FA)
    assert qapp.layoutDirection() == Qt.LayoutDirection.RightToLeft
    forms = window.findChildren(QFormLayout)
    assert forms
    assert all(form.labelAlignment() & Qt.AlignmentFlag.AlignTrailing for form in forms)
    pickers = window.findChildren(FilePicker)
    assert pickers
    assert all(p.line_edit().alignment() & Qt.AlignmentFlag.AlignLeading for p in pickers)
    database = window._database_tab
    ids_fa = [
        section.property("sectionId")
        for section in database.findChildren(type(database._schools_section), "databaseSection")
    ]
    database.update_translator(UiTranslator("en"))
    window._apply_language(Language.EN)
    assert qapp.layoutDirection() == Qt.LayoutDirection.LeftToRight
    ids_en = [
        section.property("sectionId")
        for section in database.findChildren(type(database._schools_section), "databaseSection")
    ]
    assert ids_fa == ids_en == ["schools", "groupcodes"]
    window.close()


@pytest.mark.parametrize("size", [(1200, 800), (960, 640)])
@pytest.mark.parametrize("language", [Language.FA, Language.EN])
def test_ui_primary_actions_are_fixed_and_visible(
    qapp: QApplication, size: tuple[int, int], language: Language
) -> None:
    _fresh_settings()
    window = MainWindow()
    window._apply_language(language)
    window.resize(*size)
    window.show()
    qapp.processEvents()
    for page_name, button in (
        ("pageBuild", window._btn_build),
        ("pageAllocate", window._btn_allocate),
        ("pageRuleEngine", window._btn_rule_engine),
    ):
        page = window.findChild(QWidget, page_name)
        assert page is not None
        assert bool(page.property("fixedActionPage"))
        assert button.isVisibleTo(page)
        assert button.geometry().height() > 0
        matches = [candidate for candidate in page.findChildren(QPushButton) if candidate is button]
        assert len(matches) == 1
    normalized_rows = [
        widget for widget in window.findChildren(QWidget) if bool(widget.property("normalizedFileRow"))
    ]
    assert normalized_rows
    window.close()


def test_ui_shell_geometry_and_log_stack(qapp: QApplication) -> None:
    _fresh_settings()
    window = MainWindow()
    window.resize(960, 640)
    window.show()
    qapp.processEvents()
    sizes = window._splitter.sizes()
    assert len(sizes) == 2 and all(value > 0 for value in sizes)
    ratio = sizes[0] / sizes[1]
    assert 2.2 <= ratio <= 4.2
    assert not window._status.isVisible()
    assert window._log_panel.isVisibleTo(window)
    assert window._log_panel._stack.stackingMode().name == "StackOne"
    window._log_panel.text_edit.clear()
    window._log_panel.sync_placeholder()
    assert window._log_panel._stack.currentWidget() is window._log_panel._placeholder
    window._log_panel.text_edit.setPlainText("line")
    qapp.processEvents()
    assert window._log_panel._stack.currentWidget() is window._log_panel.text_edit
    window.close()


def test_ui_busy_overlay_is_not_splitter_pane(qapp: QApplication) -> None:
    _fresh_settings()
    window = MainWindow()
    assert window._splitter.count() == 2
    assert window._busy_overlay is not None
    assert window._busy_overlay.parentWidget() is window
    assert all(
        window._splitter.widget(index) is not window._busy_overlay
        for index in range(window._splitter.count())
    )
    window.close()


def test_ui_busy_overlay_tracks_splitter_geometry(qapp: QApplication) -> None:
    _fresh_settings()
    window = MainWindow()
    window.resize(960, 640)
    window.show()
    qapp.processEvents()

    overlay = window._busy_overlay
    splitter = window._splitter
    assert overlay is not None and splitter is not None

    window._disable_controls(True)
    qapp.processEvents()
    expected_top_left = splitter.mapTo(window, splitter.rect().topLeft())
    assert overlay.isVisibleTo(window)
    assert overlay.geometry().topLeft() == expected_top_left
    assert overlay.size() == splitter.size()

    window.resize(1100, 720)
    qapp.processEvents()
    expected_top_left = splitter.mapTo(window, splitter.rect().topLeft())
    assert overlay.geometry().topLeft() == expected_top_left
    assert overlay.size() == splitter.size()

    window._disable_controls(False)
    qapp.processEvents()
    assert not overlay.isVisible()
    window.close()


def test_ui_splitter_state_roundtrip_preserves_two_panes(qapp: QApplication) -> None:
    _fresh_settings()
    first = MainWindow()
    first.resize(960, 640)
    first.show()
    qapp.processEvents()
    first._splitter.setSizes([1, 1])
    qapp.processEvents()
    saved_sizes = first._splitter.sizes()
    assert len(saved_sizes) == 2 and all(value > 0 for value in saved_sizes)
    saved_ratio = saved_sizes[0] / saved_sizes[1]
    first.close()
    qapp.processEvents()
    QSettings().sync()

    second = MainWindow()
    second.resize(960, 640)
    second.show()
    qapp.processEvents()
    restored_sizes = second._splitter.sizes()
    assert len(restored_sizes) == 2 and all(value > 0 for value in restored_sizes)
    restored_ratio = restored_sizes[0] / restored_sizes[1]
    assert abs(restored_ratio - saved_ratio) <= 0.35
    second.close()
    qapp.processEvents()
    _fresh_settings()


def test_ui_busy_overlay_source_preserves_base_method() -> None:
    base_source = (ROOT / "app/ui/main_window_base.py").read_text(encoding="utf-8")
    wrapper_source = (ROOT / "app/ui/main_window.py").read_text(encoding="utf-8")
    assert "_busy_overlay: QFrame | None = QFrame(self._splitter)" not in base_source
    assert "_busy_overlay: QFrame | None = QFrame(self)" in base_source
    assert "self._splitter.mapTo(" in base_source
    assert "_busy_overlay.setParent" not in wrapper_source
    assert "_splitter.restoreState(" not in wrapper_source
    assert 'setValue("ui/main_splitter"' not in wrapper_source


def test_ui_native_icon_source_has_no_emoji(qapp: QApplication) -> None:
    picker = FilePicker(translator=UiTranslator("en"))
    label = picker._icon_label
    assert label.text() == ""
    pixmap = label.pixmap()
    assert pixmap is not None and not pixmap.isNull()
    assert "📁" not in (ROOT / "app/ui/widgets/file_picker.py").read_text(encoding="utf-8")
    assert "🗒" not in (ROOT / "app/ui/log_panel.py").read_text(encoding="utf-8")

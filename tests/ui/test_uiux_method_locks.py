"""Focused falsification tests for the active Matrix C2/V2 UI contracts."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
from PySide6.QtCore import QByteArray, QRect, QSettings, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QScrollArea,
    QStyle,
    QStyleOptionComboBox,
    QVBoxLayout,
    QWidget,
)

from app.ui import main_window as main_window_module
from app.ui.i18n import Language
from app.ui.log_panel import LogPanel
from app.ui.main_window import MainWindow
from app.ui.texts import UiTranslator
from app.ui.theme import apply_theme, build_stylesheet, build_theme, contrast_ratio
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
_EXPECTED_SURFACES = ("build", "allocate", "rule-engine", "explain", "database")


def _fresh_settings() -> None:
    settings = QSettings()
    settings.clear()
    settings.sync()


def _mapped_rect(widget: QWidget, ancestor: QWidget) -> QRect:
    return QRect(widget.mapTo(ancestor, widget.rect().topLeft()), widget.size())


def _assert_contained(widget: QWidget, ancestor: QWidget) -> None:
    rect = _mapped_rect(widget, ancestor)
    assert rect.width() > 0 and rect.height() > 0
    assert ancestor.rect().contains(rect)


def _governing_scroll_area(widget: QWidget, surface: QWidget) -> QScrollArea | None:
    current: QWidget | None = widget.parentWidget()
    while current is not None:
        if isinstance(current, QScrollArea):
            if current is surface or surface.isAncestorOf(current):
                return current
            return None
        if current is surface:
            return None
        current = current.parentWidget()
    return None


def _assert_scroll_reachable(
    widget: QWidget, surface: QWidget, qapp: QApplication
) -> None:
    scroll = _governing_scroll_area(widget, surface)
    assert scroll is not None, "critical control has no governing QScrollArea"
    horizontal = scroll.horizontalScrollBar()
    vertical = scroll.verticalScrollBar()
    previous = (horizontal.value(), vertical.value())
    try:
        scroll.ensureWidgetVisible(widget, 0, 0)
        qapp.processEvents()
        viewport = scroll.viewport()
        rect = _mapped_rect(widget, viewport)
        assert rect.width() > 0 and rect.height() > 0
        assert viewport.rect().contains(rect)
    finally:
        horizontal.setValue(previous[0])
        vertical.setValue(previous[1])
        qapp.processEvents()


def _combo_arrow_rect(combo: QComboBox) -> QRect:
    option = QStyleOptionComboBox()
    combo.initStyleOption(option)
    return combo.style().subControlRect(
        QStyle.ComplexControl.CC_ComboBox,
        option,
        QStyle.SubControl.SC_ComboBoxArrow,
        combo,
    )


def test_ui_qsettings_harness_uses_isolated_test_identity(qapp: QApplication) -> None:
    assert (qapp.organizationName(), qapp.applicationName()) == (
        "MatrixV3Tests",
        "MatrixV3UI",
    )
    assert (qapp.organizationName(), qapp.applicationName()) != (
        "YourOrg",
        "AllocationApp",
    )

    settings = QSettings()
    assert settings.status() == QSettings.Status.NoError
    sentinel = "tests/qsettings_harness_sentinel"
    settings.setValue(sentinel, "ok")
    settings.sync()
    assert settings.value(sentinel) == "ok"
    settings.remove(sentinel)
    settings.sync()
    assert settings.value(sentinel) is None


def test_ui_typography_hierarchy_matches_v2(qapp: QApplication) -> None:
    current = build_theme("light")
    apply_theme(qapp, current)
    assert qapp.font().weight() == QFont.Weight.Normal
    assert current.typography.regular_weight == 400
    assert current.typography.strong_weight == 600
    qss = build_stylesheet(current)
    assert "font-weight: 400" in qss
    assert "font-weight: 600" in qss
    assert "font-weight: 700" not in qss


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


def test_ui_contrast_tokens_meet_v2_semantic_thresholds() -> None:
    for mode in ("light", "dark"):
        colors = build_theme(mode).colors
        active_text_pairs = (
            (colors.text_primary, colors.surface_primary),
            (colors.text_primary, colors.control_surface),
            (colors.text_secondary, colors.surface_primary),
            (colors.success, colors.surface_primary),
            (colors.warning, colors.surface_primary),
            (colors.error, colors.surface_primary),
            ("#FFFFFF", colors.accent),
            ("#FFFFFF", colors.accent_hover),
            ("#FFFFFF", colors.accent_pressed),
        )
        assert all(contrast_ratio(fg, bg) >= 4.5 for fg, bg in active_text_pairs)
        essential_boundaries = (
            (colors.focus, colors.surface_primary),
            (colors.boundary_control, colors.surface_primary),
        )
        assert all(contrast_ratio(fg, bg) >= 3.0 for fg, bg in essential_boundaries)

        # Disabled/inactive presentation is tracked separately and is not promoted
        # to the active-text threshold contract.
        disabled_ratio = contrast_ratio(colors.disabled_text, colors.disabled_surface)
        assert disabled_ratio > 1.0


def test_ui_combo_is_matrix_styled_while_qt_keeps_behavior(qapp: QApplication) -> None:
    current = build_theme("dark")
    qss = build_stylesheet(current)
    assert "QComboBox::drop-down" in qss
    assert "QComboBox::down-arrow" in qss
    assert "QComboBox QAbstractItemView" in qss
    assert "QComboBox:hover" in qss
    assert "QComboBox:focus" in qss
    assert "QComboBox:disabled" in qss
    assert re.search(r"QScrollBar::[A-Za-z-]+\s*\{", qss) is None
    assert re.search(r"QCheckBox::indicator\s*\{", qss) is None

    apply_theme(qapp, current)
    combo = QComboBox()
    combo.addItems(["A", "B", "C"])
    combo.resize(180, 32)
    combo.setCurrentIndex(2)
    assert combo.count() == 3
    assert combo.currentText() == "C"

    for direction in (Qt.LayoutDirection.RightToLeft, Qt.LayoutDirection.LeftToRight):
        combo.setLayoutDirection(direction)
        option = QStyleOptionComboBox()
        combo.initStyleOption(option)
        arrow = _combo_arrow_rect(combo)
        assert arrow.width() > 0 and arrow.height() > 0
        assert combo.rect().contains(arrow)


def test_ui_translation_inventory_is_complete_and_reference_keys_are_split() -> None:
    payload = json.loads(
        (ROOT / "resources/translations/ui_texts.json").read_text(encoding="utf-8")
    )
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
    presentation_source = (ROOT / "app/ui/main_window_presentation_base.py").read_text(
        encoding="utf-8"
    )
    assert "reference.hint" not in presentation_source


def test_ui_c2_surface_registry_is_id_based(qapp: QApplication) -> None:
    _fresh_settings()
    window = MainWindow()
    window.show()
    qapp.processEvents()

    assert window.workspace_surface_ids() == _EXPECTED_SURFACES
    assert window.primary_surface_ids() == ("build", "allocate", "rule-engine")
    assert window.secondary_surface_ids() == ("explain", "database")
    assert window._tabs.tabBar().isHidden()

    for surface_id in reversed(_EXPECTED_SURFACES):
        assert window.activate_surface(surface_id)
        qapp.processEvents()
        assert window.current_surface_id() == surface_id
        assert window._workspace_nav_buttons[surface_id].isChecked()

    render_source = (ROOT / "tools/render_ui_matrix.py").read_text(encoding="utf-8")
    assert "activate_surface(" in render_source
    assert "current_surface_id(" in render_source
    assert "_tabs.setCurrentIndex(" not in render_source
    window.close()


def test_scroll_aware_oracle_reaches_target_outside_initial_viewport(
    qapp: QApplication,
) -> None:
    surface = QWidget()
    surface.resize(240, 140)
    surface_layout = QVBoxLayout(surface)
    scroll = QScrollArea(surface)
    scroll.setWidgetResizable(True)
    surface_layout.addWidget(scroll)

    content = QWidget()
    content_layout = QVBoxLayout(content)
    spacer = QWidget(content)
    spacer.setFixedHeight(320)
    target = QWidget(content)
    target.setFixedSize(120, 32)
    content_layout.addWidget(spacer)
    content_layout.addWidget(target)
    scroll.setWidget(content)

    surface.show()
    qapp.processEvents()
    initial_rect = _mapped_rect(target, scroll.viewport())
    assert not scroll.viewport().rect().contains(initial_rect)
    initial_scroll = scroll.verticalScrollBar().value()

    _assert_scroll_reachable(target, surface, qapp)

    assert scroll.verticalScrollBar().value() == initial_scroll
    surface.close()


def test_scroll_aware_oracle_rejects_target_that_cannot_fit_viewport(
    qapp: QApplication,
) -> None:
    surface = QWidget()
    surface.resize(240, 140)
    surface_layout = QVBoxLayout(surface)
    scroll = QScrollArea(surface)
    scroll.setWidgetResizable(True)
    surface_layout.addWidget(scroll)

    content = QWidget()
    content_layout = QVBoxLayout(content)
    target = QWidget(content)
    target.setFixedSize(120, 240)
    content_layout.addWidget(target)
    scroll.setWidget(content)

    surface.show()
    qapp.processEvents()
    with pytest.raises(AssertionError):
        _assert_scroll_reachable(target, surface, qapp)
    surface.close()


@pytest.mark.parametrize("size", [(1200, 800), (960, 640)])
@pytest.mark.parametrize("language", [Language.FA, Language.EN])
def test_ui_bidi_and_primary_actions_are_contained(
    qapp: QApplication, size: tuple[int, int], language: Language
) -> None:
    _fresh_settings()
    window = MainWindow()
    window._apply_language(language)
    window.resize(*size)
    window.show()
    qapp.processEvents()

    expected_direction = (
        Qt.LayoutDirection.RightToLeft
        if language is Language.FA
        else Qt.LayoutDirection.LeftToRight
    )
    assert qapp.layoutDirection() == expected_direction

    forms = window.findChildren(QFormLayout)
    assert forms
    assert all(form.labelAlignment() & Qt.AlignmentFlag.AlignTrailing for form in forms)
    pickers = window.findChildren(FilePicker)
    assert pickers
    assert all(p.line_edit().alignment() & Qt.AlignmentFlag.AlignLeading for p in pickers)

    for surface_id, button in (
        ("build", window._btn_build),
        ("allocate", window._btn_allocate),
        ("rule-engine", window._btn_rule_engine),
    ):
        assert window.activate_surface(surface_id)
        qapp.processEvents()
        surface = window._workspace_surfaces[surface_id]
        assert button.isVisibleTo(surface)
        _assert_contained(button, surface)

    assert window.activate_surface("allocate")
    qapp.processEvents()
    allocate = window._workspace_surfaces["allocate"]
    combo = window.findChild(QComboBox, "academicYearInput")
    assert combo is not None and combo.isVisibleTo(allocate)
    _assert_scroll_reachable(combo, allocate, qapp)
    arrow = _combo_arrow_rect(combo)
    assert arrow.width() > 0 and arrow.height() > 0
    assert combo.rect().contains(arrow)
    assert window._picker_students.isVisibleTo(allocate)
    _assert_scroll_reachable(window._picker_students, allocate, qapp)

    navigation = window._workspace_navigation
    toggle = window._diagnostics_toggle
    assert navigation is not None and navigation.isVisibleTo(window)
    assert toggle is not None and toggle.isVisibleTo(window)
    _assert_contained(navigation, window)
    _assert_contained(toggle, window)
    window.close()


def test_ui_diagnostics_startup_is_explicitly_collapsed(qapp: QApplication) -> None:
    _fresh_settings()
    settings = QSettings()
    settings.setValue("ui/main_splitter", QByteArray(b"legacy-state-must-not-open-c2"))
    settings.sync()

    window = MainWindow()
    window.resize(960, 640)
    window.show()
    qapp.processEvents()

    pane = window._diagnostics_pane
    toggle = window._diagnostics_toggle
    assert pane is not None and toggle is not None
    assert pane.isHidden()
    assert not pane.isVisibleTo(window)
    assert not toggle.isChecked()
    assert not window.diagnostics_expanded()
    assert window._status_bar is not None and window._status_bar.isVisibleTo(window)
    assert window._stage_badge.isVisibleTo(window)
    window.close()
    _fresh_settings()


def test_ui_diagnostics_roundtrip_uses_only_v2_persistence(qapp: QApplication) -> None:
    _fresh_settings()
    first = MainWindow()
    first.resize(1000, 700)
    first.show()
    qapp.processEvents()

    first.set_diagnostics_expanded(True)
    qapp.processEvents()
    assert first.diagnostics_expanded()
    assert first._diagnostics_pane is not None
    assert first._diagnostics_pane.isVisibleTo(first)
    first._splitter.setSizes([650, 250])
    qapp.processEvents()
    expanded_sizes = first._splitter.sizes()

    first.set_diagnostics_expanded(False)
    qapp.processEvents()
    assert first._diagnostics_pane.isHidden()
    assert not first._diagnostics_toggle.isChecked()
    saved_v2 = QSettings().value("ui/main_splitter_v2")
    assert isinstance(saved_v2, QByteArray) and not saved_v2.isEmpty()
    first.close()
    qapp.processEvents()

    second = MainWindow()
    second.resize(1000, 700)
    second.show()
    qapp.processEvents()
    assert not second.diagnostics_expanded()
    assert second._diagnostics_pane is not None and second._diagnostics_pane.isHidden()
    second.set_diagnostics_expanded(True)
    qapp.processEvents()
    restored_sizes = second._splitter.sizes()
    assert second._diagnostics_pane.isVisibleTo(second)
    assert second._diagnostics_toggle.isChecked()
    assert len(restored_sizes) == len(expanded_sizes) == 2
    assert restored_sizes[1] > 0
    second.set_diagnostics_expanded(False)
    assert second._diagnostics_pane.isHidden()
    second.close()
    _fresh_settings()


def test_ui_diagnostics_error_path_auto_reveals(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fresh_settings()
    window = MainWindow()
    window.show()
    qapp.processEvents()
    assert not window.diagnostics_expanded()

    monkeypatch.setattr(window, "_show_async_message", lambda *_args, **_kwargs: None)
    window._on_finished(False, RuntimeError("diagnostic evidence"))
    qapp.processEvents()

    assert window.diagnostics_expanded()
    assert window._diagnostics_pane is not None
    assert window._diagnostics_pane.isVisibleTo(window)
    assert window._diagnostics_toggle is not None and window._diagnostics_toggle.isChecked()
    window.close()
    _fresh_settings()


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


def test_ui_authority_documents_are_synchronized() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    authority = (ROOT / "docs/UI_PRESENTATION_AUTHORITY.md").read_text(encoding="utf-8")
    design = (ROOT / "docs/UI_DESIGN_CONTRACT.md").read_text(encoding="utf-8")
    assert "docs/UI_PRESENTATION_AUTHORITY.md" in agents
    assert "docs/UI_DESIGN_CONTRACT.md" in agents
    assert "| `QComboBox` | STYLED |" in authority
    assert "current bytes are split-owner" not in authority
    assert "drop-down/arrow stays Fusion-native" not in authority
    assert "QScrollBar" in authority and "NATIVE" in authority
    assert "QCheckBox" in authority and "HYBRID" in authority
    assert "PRIMARY_WORKSPACE_WITH_UTILITY_SEPARATION" in design
    assert "SOLID_LAYERED_PRODUCTIVITY" in design


def test_public_demo_instantiates_current_public_main_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class FakeWindow:
        def __init__(self) -> None:
            events.append("created")

        def show(self) -> None:
            events.append("shown")

    class FakeApp:
        def exec(self) -> int:
            events.append("exec")
            return 0

    fake_app = FakeApp()

    class FakeApplication:
        @staticmethod
        def instance() -> FakeApp:
            return fake_app

    monkeypatch.setattr(main_window_module, "MainWindow", FakeWindow)
    monkeypatch.setattr(main_window_module, "QApplication", FakeApplication)
    main_window_module.run_demo()

    assert events == ["created", "shown", "exec"]
    source = (ROOT / "app/ui/main_window.py").read_text(encoding="utf-8")
    assert "_v1.run_demo()" not in source


def test_ui_native_icon_source_has_no_emoji(qapp: QApplication) -> None:
    picker = FilePicker(translator=UiTranslator("en"))
    label = picker._icon_label
    assert label.text() == ""
    pixmap = label.pixmap()
    assert pixmap is not None and not pixmap.isNull()
    assert "📁" not in (ROOT / "app/ui/widgets/file_picker.py").read_text(encoding="utf-8")
    assert "🗒" not in (ROOT / "app/ui/log_panel.py").read_text(encoding="utf-8")

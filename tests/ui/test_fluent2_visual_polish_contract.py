"""Focused falsification tests for the Fluent-2 neutral visual-polish locks.

Each test maps to one conformance lock of WU-UI-FLUENT2-POLISH-01:

* ``CL-UI-TONAL-01``      -> semantic neutral palette / material invariants
* ``CL-UI-TYPOGRAPHY-01`` -> font rendering strategy
* ``CL-UI-LAYOUT-01``     -> shared working column and CTA alignment
* ``CL-UI-COMBO-01``      -> Matrix-owned combo drop-down geometry
* ``CL-UI-SCROLLBAR-01``  -> complete styled scrollbar ownership
* ``CL-UI-I18N-01``       -> stable localization bindings and capacity guidance
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
from PySide6.QtCore import QRect, QSettings, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLabel,
    QLineEdit,
    QScrollArea,
    QWidget,
)

from app.ui import fonts
from app.ui.i18n import Language
from app.ui.main_window import MainWindow
from app.ui.theme import Theme, build_stylesheet, build_theme, contrast_ratio

ROOT = Path(__file__).resolve().parents[2]
QSS_SOURCE = (ROOT / "app/ui/styles.qss").read_text(encoding="utf-8")
CHEVRON_SOURCE = (ROOT / "app/ui/widgets/combo_chevron.py").read_text(encoding="utf-8")

# Surface roles that must read as neutral charcoal/gray rather than navy.
_SURFACE_ROLES = (
    "background",
    "surface_primary",
    "surface_secondary",
    "control_surface",
    "control_hover",
    "disabled_surface",
    "diagnostic_background",
)


def _fresh_settings() -> None:
    settings = QSettings()
    settings.clear()
    settings.sync()


def _destroy(window: MainWindow, qapp: QApplication) -> None:
    """Tear a workspace window down completely.

    The application font authority walks ``QApplication.allWidgets()`` on every
    language switch, so windows left alive by ``close()`` alone make each later
    case in the session quadratically slower.
    """

    window.close()
    window.deleteLater()
    qapp.processEvents()
    _fresh_settings()


def _channels(value: str) -> tuple[int, int, int]:
    color = QColor(value)
    return color.red(), color.green(), color.blue()


def _mapped_rect(widget: QWidget, ancestor: QWidget) -> QRect:
    return QRect(widget.mapTo(ancestor, widget.rect().topLeft()), widget.size())


def _qss_rule_body(selector: str) -> str:
    """Return the declaration body of one central QSS rule.

    Rules are authored one per line, and token placeholders such as
    ``{control_surface}`` contain braces, so the body is taken from the line
    itself rather than by scanning to the first closing brace.
    """

    for line in QSS_SOURCE.splitlines():
        stripped = line.strip()
        if not stripped.endswith("}"):
            continue
        head, _, body = stripped.partition("{")
        if head.strip() == selector:
            return body.rsplit("}", 1)[0]
    raise AssertionError(f"missing QSS rule: {selector}")


# --------------------------------------------------------------- CL-UI-TONAL-01
def test_dark_workflow_surfaces_are_neutral_not_navy() -> None:
    colors = build_theme("dark").colors
    for role in _SURFACE_ROLES:
        red, green, blue = _channels(getattr(colors, role))
        spread = max(red, green, blue) - min(red, green, blue)
        assert spread <= 8, f"dark {role} is not a neutral surface: spread={spread}"
        assert blue - red <= 8, f"dark {role} is blue/navy biased: blue-red={blue - red}"
        assert blue >= red, f"dark {role} must stay in the cool-neutral family"


def test_light_theme_keeps_distinct_page_surface_and_control_roles() -> None:
    colors = build_theme("light").colors
    page = QColor(colors.background).lightness()
    surface = QColor(colors.surface_primary).lightness()
    secondary = QColor(colors.surface_secondary).lightness()

    assert surface > page > secondary, "light page/surface/control depth is flat"
    assert contrast_ratio(colors.background, colors.surface_primary) >= 1.08
    assert contrast_ratio(colors.background, colors.surface_secondary) >= 1.05
    for role in _SURFACE_ROLES:
        red, green, blue = _channels(getattr(colors, role))
        assert max(red, green, blue) - min(red, green, blue) <= 8


def test_accent_family_is_one_controlled_cool_family() -> None:
    for mode in ("light", "dark"):
        colors = build_theme(mode).colors
        for role in ("accent", "accent_hover", "accent_pressed"):
            red, green, blue = _channels(getattr(colors, role))
            assert blue > red and green > red, f"{mode} {role} is not a cool accent"
            assert contrast_ratio("#FFFFFF", getattr(colors, role)) >= 4.5


def test_theme_colors_remains_the_single_semantic_authority() -> None:
    theme_source = (ROOT / "app/ui/theme.py").read_text(encoding="utf-8")
    # Hex literals may only appear in ThemeColors defaults, the dark override and
    # the primary-CTA foreground. No parallel palette map may be introduced.
    hex_literals = re.findall(r'"#[0-9A-Fa-f]{6}"', theme_source)
    assert len(hex_literals) == 42, f"unexpected palette literal count: {len(hex_literals)}"
    assert theme_source.count("class ThemeColors") == 1
    for mode in ("light", "dark"):
        stylesheet = build_stylesheet(build_theme(mode))
        assert stylesheet
        unresolved = re.findall(r"\{[a-z_]+\}", stylesheet)
        assert unresolved == [], f"unresolved QSS tokens: {sorted(set(unresolved))}"


# ------------------------------------------------------------ CL-UI-TONAL-01 (material)
def test_governed_qss_has_no_glass_like_material() -> None:
    lowered = QSS_SOURCE.lower()
    for forbidden in (
        "rgba(",
        "hsla(",
        "acrylic",
        "mica",
        "backdrop",
        "blur",
        "glow",
        "box-shadow",
        "drop-shadow",
        "qlineargradient",
        "qradialgradient",
        "qconicalgradient",
        "opacity",
    ):
        assert forbidden not in lowered, f"glass-like mechanism in QSS: {forbidden}"

    theme_source = (ROOT / "app/ui/theme.py").read_text(encoding="utf-8").lower()
    for forbidden in ("qgraphicsblureffect", "qgraphicsdropshadoweffect", "setwindowopacity"):
        assert forbidden not in theme_source


def test_routine_controls_do_not_use_a_bright_boundary() -> None:
    button_rule = _qss_rule_body("QPushButton, QToolButton")
    assert "border: 1px solid {boundary_subtle}" in button_rule

    # Essential authored affordances keep the stronger boundary role.
    input_rule = _qss_rule_body("QLineEdit, QTextEdit, QPlainTextEdit, QComboBox")
    assert "border: 1px solid {boundary_control}" in input_rule

    for mode in ("light", "dark"):
        colors = build_theme(mode).colors
        # A routine outline must stay quiet against its own surface.
        assert contrast_ratio(colors.boundary_subtle, colors.surface_primary) < 2.0
        # Essential boundaries and focus must remain perceivable.
        assert contrast_ratio(colors.boundary_control, colors.surface_primary) >= 3.0
        assert contrast_ratio(colors.focus, colors.surface_primary) >= 3.0


def test_accent_is_not_spread_across_ordinary_controls() -> None:
    accent_rules = [
        line
        for line in QSS_SOURCE.splitlines()
        if "background-color: {accent}" in line or "background-color: {accent_" in line
    ]
    for line in accent_rules:
        selector = line.split("{", 1)[0].strip()
        assert any(
            marker in selector
            for marker in ('QPushButton[variant="primary"]', "QProgressBar::chunk")
        ), f"accent fill leaked onto an ordinary control: {selector}"


# ---------------------------------------------------------- CL-UI-TYPOGRAPHY-01
def test_font_strategy_prefers_vertical_hinting_over_forced_full_hinting() -> None:
    font = fonts.create_app_font(point_size=10)
    strategy = font.styleStrategy()
    assert strategy & QFont.StyleStrategy.PreferAntialias
    assert strategy & QFont.StyleStrategy.PreferQuality
    assert font.kerning()

    vertical = getattr(QFont.HintingPreference, "PreferVerticalHinting", None)
    full = getattr(QFont.HintingPreference, "PreferFullHinting", None)
    if vertical is not None:
        assert font.hintingPreference() == vertical
    if full is not None:
        assert font.hintingPreference() != full


def test_font_authority_has_no_new_asset_source() -> None:
    source = (ROOT / "app/ui/fonts.py").read_text(encoding="utf-8")
    assert "VAZIRMATN_VARIABLE_TTF_BASE64" in source
    assert source.count("addApplicationFontFromData") == 1
    assert "Segoe UI" in source
    assets = sorted(path.name for path in (ROOT / "app/ui/assets").glob("font_data_*.py"))
    assert assets == ["font_data_vazirmatn.py"]


def test_semantic_typography_sizes_are_preserved() -> None:
    typography = Theme().typography
    assert (typography.caption_size, typography.body_size) == (9, 10)
    assert (typography.subtitle_size, typography.title_size) == (11, 13)
    assert (typography.regular_weight, typography.strong_weight) == (400, 600)


# --------------------------------------------------------------- CL-UI-COMBO-01
def test_combo_overlay_geometry_is_matrix_token_owned() -> None:
    assert "SC_ComboBoxArrow" not in CHEVRON_SOURCE
    assert "subControlRect" not in CHEVRON_SOURCE
    assert "combo_dropdown_width" in CHEVRON_SOURCE
    assert "{combo_dropdown_width}px" in QSS_SOURCE
    assert "{combo_content_inset}px" in QSS_SOURCE


@pytest.mark.parametrize(
    "direction", [Qt.LayoutDirection.RightToLeft, Qt.LayoutDirection.LeftToRight]
)
def test_combo_chevron_stays_inside_the_matrix_drop_down_region(
    qapp: QApplication, direction: Qt.LayoutDirection
) -> None:
    from app.ui.widgets.combo_chevron import install_combo_chevrons

    combo = QComboBox()
    combo.addItems(["A", "B"])
    combo.setLayoutDirection(direction)
    combo.resize(200, 32)
    install_combo_chevrons(combo)
    install_combo_chevrons(combo)
    qapp.processEvents()

    overlays = [
        child
        for child in combo.children()
        if isinstance(child, QWidget) and child.objectName() == "comboChevronOverlay"
    ]
    assert len(overlays) == 1, "exactly one Matrix chevron overlay per combo"
    overlay = overlays[0]
    width = Theme().combo_dropdown_width

    assert combo.rect().contains(overlay.geometry())
    assert overlay.width() == width
    if direction == Qt.LayoutDirection.RightToLeft:
        assert overlay.geometry().left() == 0
    else:
        assert overlay.geometry().right() == combo.width() - 1
    combo.close()


# ----------------------------------------------------------- CL-UI-SCROLLBAR-01
def test_styled_scrollbar_owns_the_complete_visible_family() -> None:
    required = (
        "QScrollBar:vertical",
        "QScrollBar:horizontal",
        "QScrollBar::handle:vertical",
        "QScrollBar::handle:horizontal",
        "QScrollBar::add-line:vertical",
        "QScrollBar::sub-line:vertical",
        "QScrollBar::add-line:horizontal",
        "QScrollBar::sub-line:horizontal",
        "QScrollBar::add-page:vertical",
        "QScrollBar::sub-page:vertical",
        "QScrollBar::add-page:horizontal",
        "QScrollBar::sub-page:horizontal",
        "QScrollBar::up-arrow:vertical",
        "QScrollBar::down-arrow:vertical",
        "QScrollBar::left-arrow:horizontal",
        "QScrollBar::right-arrow:horizontal",
        "QScrollBar::handle:vertical:hover",
        "QScrollBar::handle:vertical:pressed",
        "QScrollBar::handle:vertical:disabled",
        # Qt hosts the corner between two scrollbars on QAbstractScrollArea.
        "QAbstractScrollArea::corner",
    )
    for selector in required:
        assert selector in QSS_SOURCE, f"scrollbar subcontrol not owned: {selector}"
    # `QScrollBar::corner` names no real Qt subcontrol, so a rule written against
    # it silently owns nothing while the documentation claims the corner.
    assert "QScrollBar::corner" not in QSS_SOURCE

    theme = Theme()
    stylesheet = build_stylesheet(build_theme("dark"))
    assert f"width: {theme.scrollbar_thickness}px" in stylesheet
    assert f"height: {theme.scrollbar_thickness}px" in stylesheet
    assert f"min-height: {theme.scrollbar_handle_min}px" in stylesheet
    assert f"min-width: {theme.scrollbar_handle_min}px" in stylesheet

    # Legacy Fusion arrow buttons must be removed, not merely recolored.
    line_rule = _qss_rule_body(
        "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical, "
        "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal"
    )
    assert "width: 0px" in line_rule and "height: 0px" in line_rule

    # No hover rule may change the reserved extent (that would reflow content).
    for line in QSS_SOURCE.splitlines():
        if line.startswith("QScrollBar") and ":hover" in line.split("{", 1)[0]:
            body = line.split("{", 1)[1]
            assert "width:" not in body and "height:" not in body


def test_scrollbar_reclassification_added_no_behavior_owner() -> None:
    for path in sorted((ROOT / "app/ui").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert "QProxyStyle" not in source, f"custom style owner introduced in {path}"
        assert "setStyle(" not in source or path.name == "theme.py"

    theme_source = (ROOT / "app/ui/theme.py").read_text(encoding="utf-8")
    assert 'app.setStyle("Fusion")' in theme_source


def test_scrollbar_handle_stays_usable_in_both_themes() -> None:
    for mode in ("light", "dark"):
        colors = build_theme(mode).colors
        assert contrast_ratio(colors.boundary_control, colors.background) >= 3.0
        assert contrast_ratio(colors.boundary_control, colors.surface_primary) >= 3.0


# --------------------------------------------------------------- CL-UI-LAYOUT-01
def test_shared_working_column_tokens_are_semantic() -> None:
    theme = Theme()
    assert theme.working_measure >= 960
    assert theme.field_measure < theme.working_measure
    main_source = (ROOT / "app/ui/main_window.py").read_text(encoding="utf-8")
    assert "_MAX_WORKING_MEASURE" not in main_source
    assert "self._theme.working_measure" in main_source
    assert "self._theme.field_measure" in main_source


@pytest.mark.parametrize("language", [Language.FA, Language.EN])
def test_footer_cta_shares_the_content_working_column(
    qapp: QApplication, language: Language
) -> None:
    _fresh_settings()
    window = MainWindow()
    window._apply_language(language)
    window.show()

    try:
        # A scroll area reserves its scrollbar extent outside the viewport, so the
        # work column and the footer column may differ by at most that reservation.
        tolerance = window._theme.scrollbar_thickness + window._theme.micro
        for size in ((960, 640), (1200, 800), (1680, 900)):
            window.resize(*size)
            qapp.processEvents()
            for surface_id, button in (
                ("build", window._btn_build),
                ("allocate", window._btn_allocate),
            ):
                assert window.activate_surface(surface_id)
                qapp.processEvents()
                surface = window._workspace_surfaces[surface_id]
                content = window.findChild(
                    QWidget, f"page{surface_id.capitalize()}Content"
                )
                column = button.parentWidget()
                assert content is not None and column is not None
                assert column.objectName() == "pageActionFooterColumn"

                content_rect = _mapped_rect(content, window)
                column_rect = _mapped_rect(column, window)
                assert content.width() <= window._theme.working_measure
                assert column.width() <= window._theme.working_measure
                # The CTA column and the work content share one logical column.
                assert (
                    abs(content_rect.center().x() - column_rect.center().x())
                    <= tolerance
                ), f"{size} {surface_id}: CTA column is not centred on the content"
                assert abs(content_rect.width() - column_rect.width()) <= tolerance

                # The CTA sits on the trailing edge of the form's own column,
                # never on a distant window edge.
                margins = content.layout().contentsMargins()
                inner = content_rect.adjusted(margins.left(), 0, -margins.right(), 0)
                button_rect = _mapped_rect(button, window)
                drift = (
                    abs(button_rect.left() - inner.left())
                    if language is Language.FA
                    else abs(button_rect.right() - inner.right())
                )
                assert drift <= tolerance, f"{size} {surface_id}: CTA drift={drift}px"
                assert button.isVisibleTo(surface)
                assert surface.rect().contains(_mapped_rect(button, surface))

                # Bounding the working column must not add a horizontal page scroll.
                scroll = surface.findChild(QScrollArea)
                assert scroll is not None
                assert (
                    scroll.horizontalScrollBarPolicy()
                    == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
                )
                assert not scroll.horizontalScrollBar().isVisibleTo(surface)
    finally:
        _destroy(window, qapp)


def test_form_fields_stay_within_the_bounded_field_measure(qapp: QApplication) -> None:
    _fresh_settings()
    window = MainWindow()
    window.show()

    try:
        measure = window._theme.field_measure
        for size in ((960, 640), (1680, 900)):
            window.resize(*size)
            qapp.processEvents()
            assert window.activate_surface("allocate")
            qapp.processEvents()

            assert window._picker_students.width() <= measure + 1
            combo = window.findChild(QComboBox, "academicYearInput")
            assert combo is not None and combo.width() <= measure + 1
            capacity = window.findChild(QLineEdit, "editCapacityCol")
            assert capacity is not None and capacity.width() <= measure + 1
    finally:
        _destroy(window, qapp)


@pytest.mark.parametrize("language", [Language.FA, Language.EN])
def test_working_column_evidence_names_the_edge_it_measures(
    qapp: QApplication, language: Language
) -> None:
    """The render manifest must describe the metric it actually computes.

    The CTA sits on the working column's logical *trailing* edge in both
    directions - the right edge in LTR, the left edge in RTL - and the harness
    measures drift from exactly that edge. Reporting RTL as ``leading`` made the
    evidence contradict both the geometry and the design contract.
    """

    from tools.render_ui_matrix import _working_column_record

    _fresh_settings()
    window = MainWindow()
    window._apply_language(language)
    window.resize(1680, 900)
    window.show()

    try:
        tolerance = window._theme.scrollbar_thickness + window._theme.micro
        for surface_id, button in (
            ("build", window._btn_build),
            ("allocate", window._btn_allocate),
        ):
            assert window.activate_surface(surface_id)
            qapp.processEvents()

            record = _working_column_record(window, surface_id, button)
            assert record is not None

            # The manifest shape is part of the contract: no key renames.
            assert set(record) == {
                "working_measure",
                "content_column_geometry",
                "footer_column_geometry",
                "cta_geometry",
                "cta_edge_drift_px",
                "cta_edge_tolerance_px",
                "logical_edge",
            }
            assert record["logical_edge"] == "trailing"
            assert record["cta_edge_drift_px"] <= record["cta_edge_tolerance_px"]

            # ...and the CTA really is on that edge, so the label was corrected
            # rather than the geometry bent to fit the old label.
            content = window.findChild(QWidget, f"page{surface_id.capitalize()}Content")
            assert content is not None
            margins = content.layout().contentsMargins()
            content_rect = _mapped_rect(content, window)
            cta_rect = _mapped_rect(button, window)
            if language is Language.FA:
                assert qapp.layoutDirection() == Qt.LayoutDirection.RightToLeft
                trailing_edge = content_rect.left() + margins.left()
                assert abs(cta_rect.left() - trailing_edge) <= tolerance
                assert cta_rect.center().x() < content_rect.center().x()
            else:
                assert qapp.layoutDirection() == Qt.LayoutDirection.LeftToRight
                trailing_edge = content_rect.right() - margins.right()
                assert abs(cta_rect.right() - trailing_edge) <= tolerance
                assert cta_rect.center().x() > content_rect.center().x()
    finally:
        _destroy(window, qapp)


# ----------------------------------------------------------------- CL-UI-I18N-01
def test_reference_hint_and_capacity_keys_exist_in_both_catalogues() -> None:
    payload = json.loads(
        (ROOT / "resources/translations/ui_texts.json").read_text(encoding="utf-8")
    )
    assert set(payload["fa"]) == set(payload["en"])
    for key in (
        "reference.hint",
        "reference.allocate.hint",
        "files.capacity_column",
        "files.capacity_column.help",
        "files.capacity_column.tooltip",
    ):
        assert key in payload["fa"] and key in payload["en"]
        assert payload["fa"][key].strip() and payload["en"][key].strip()

    persian = re.compile(r"[؀-ۿ]")
    assert persian.search(payload["fa"]["reference.hint"])
    assert persian.search(payload["fa"]["files.capacity_column.help"])
    assert not persian.search(payload["en"]["reference.hint"])
    # The runtime column identifier is a value, never a translated string.
    assert payload["fa"]["placeholder.capacity"] == "remaining_capacity"
    assert payload["en"]["placeholder.capacity"] == "remaining_capacity"
    assert "remaining_capacity" in payload["fa"]["files.capacity_column.help"]
    assert "remaining_capacity" in payload["en"]["files.capacity_column.help"]


def test_localization_binding_uses_a_stable_semantic_target() -> None:
    presentation = (ROOT / "app/ui/main_window_presentation_base.py").read_text(
        encoding="utf-8"
    )
    assert "_bind_first_spanning_label" not in presentation
    assert "allocateReferenceHint" in presentation
    base = (ROOT / "app/ui/main_window_base.py").read_text(encoding="utf-8")
    assert 'setObjectName("allocateReferenceHint")' in base


@pytest.mark.parametrize("language", [Language.FA, Language.EN])
def test_reviewed_allocate_surface_does_not_leak_the_other_language(
    qapp: QApplication, language: Language
) -> None:
    _fresh_settings()
    window = MainWindow()
    window._apply_language(language)
    window.resize(1200, 800)
    window.show()
    qapp.processEvents()
    assert window.activate_surface("allocate")
    qapp.processEvents()

    persian = re.compile(r"[؀-ۿ]")
    hint = window.findChild(QLabel, "allocateReferenceHint")
    assert hint is not None and hint.text().strip()
    capacity = window.findChild(QLineEdit, "editCapacityCol")
    assert capacity is not None
    capacity_help = window.findChild(QLabel, "fieldHelp_allocate_capacity")
    assert capacity_help is not None and capacity_help.text().strip()

    if language is Language.FA:
        assert persian.search(hint.text())
        assert "database-backed" not in hint.text()
        assert persian.search(capacity_help.text())
    else:
        assert not persian.search(hint.text())
        assert not persian.search(capacity_help.text())

    # Capacity semantics never change: the value stays the runtime column id.
    assert capacity.text() == "remaining_capacity"
    assert capacity.placeholderText() == "remaining_capacity"
    assert "remaining_capacity" in capacity_help.text()
    assert "remaining_capacity" in capacity.toolTip()

    _destroy(window, qapp)

"""Focused falsification tests for the spatial-hierarchy locks.

Each test maps to one conformance lock of
WU-SPATIAL-HIERARCHY-SECTION-REGIONS-01:

* ``CL-UI-SECTION-01`` -> Major Section Region grammar and semantic identity
* ``CL-UI-SECTION-02`` -> Common Region material drawn from existing theme roles
* ``CL-UI-SPACING-01`` -> macro section gap above the intra-section row rhythm
* ``CL-UI-ACTION-01``  -> content-contained Action Region and retired footer
* ``CL-UI-LARGE-01``   -> large-desktop composition balance
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
from PySide6.QtCore import QRect, QSettings, Qt
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QComboBox,
    QFrame,
    QGroupBox,
    QLabel,
    QLineEdit,
    QScrollArea,
    QStyle,
    QStyleOptionGroupBox,
    QWidget,
)

from app.ui.i18n import Language
from app.ui.main_window import MainWindow
from app.ui.theme import Theme, build_stylesheet, build_theme

ROOT = Path(__file__).resolve().parents[2]
QSS_SOURCE = (ROOT / "app/ui/styles.qss").read_text(encoding="utf-8")

# The Major Sections each primary workflow page is expected to compose, in order.
# Stable object names, never title text: the pages are bilingual.
BUILD_SECTIONS = ("buildInputsSection", "buildPolicySection", "buildOutputSection")
ALLOCATE_SECTIONS = (
    "allocateInputsSection",
    "allocateAdvancedSection",
    "centerManagerGroup",
    "registrationGroupBox",
    "allocateOutputSection",
    "allocateSabtSection",
)
LARGE_DESKTOP = (1600, 900)


def _fresh_settings() -> None:
    settings = QSettings()
    settings.clear()
    settings.sync()


def _destroy(window: MainWindow, qapp: QApplication) -> None:
    window.close()
    window.deleteLater()
    qapp.processEvents()
    _fresh_settings()


def _mapped_rect(widget: QWidget, ancestor: QWidget) -> QRect:
    return QRect(widget.mapTo(ancestor, widget.rect().topLeft()), widget.size())


def _qss_rule_body(selector: str) -> str:
    for line in QSS_SOURCE.splitlines():
        stripped = line.strip()
        if not stripped.endswith("}"):
            continue
        head, _, body = stripped.partition("{")
        if head.strip() == selector:
            return body.rsplit("}", 1)[0]
    raise AssertionError(f"missing QSS rule: {selector}")


def _page_content(window: MainWindow, surface_id: str) -> QWidget:
    content = window.findChild(QWidget, f"page{surface_id.capitalize()}Content")
    assert content is not None, f"no page content for {surface_id}"
    return content


def _top_level_sections(content: QWidget) -> list[QGroupBox]:
    outer = content.layout()
    assert isinstance(outer, QBoxLayout)
    return [
        item
        for item in (outer.itemAt(index).widget() for index in range(outer.count()))
        if isinstance(item, QGroupBox)
    ]


def _section_boundary(group: QGroupBox, ancestor: QWidget) -> QRect:
    """Return the visible region boundary, not the widget rect.

    The macro gap is carried by the region's own QSS margin, so the widget rect
    is larger than the boundary a reader sees between two regions.
    """

    option = QStyleOptionGroupBox()
    group.initStyleOption(option)
    frame = group.style().subControlRect(
        QStyle.ComplexControl.CC_GroupBox,
        option,
        QStyle.SubControl.SC_GroupBoxFrame,
        group,
    )
    origin = _mapped_rect(group, ancestor)
    return QRect(
        origin.left() + frame.left(), origin.top() + frame.top(), frame.width(), frame.height()
    )


def _action_region(content: QWidget) -> QFrame:
    region = content.findChild(QFrame, "pageActionRegion")
    assert region is not None, "no content-contained Action Region"
    return region


# ------------------------------------------------------------- CL-UI-SECTION-01
@pytest.mark.parametrize(
    ("surface_id", "expected"),
    [("build", BUILD_SECTIONS), ("allocate", ALLOCATE_SECTIONS)],
)
def test_primary_pages_compose_explicit_major_section_regions(
    qapp: QApplication, surface_id: str, expected: tuple[str, ...]
) -> None:
    _fresh_settings()
    window = MainWindow()
    window.resize(1200, 800)
    window.show()
    try:
        assert window.activate_surface(surface_id)
        qapp.processEvents()
        sections = _top_level_sections(_page_content(window, surface_id))

        assert tuple(group.objectName() for group in sections) == expected
        for group in sections:
            assert group.property("sectionRole") == "major"
            # A section without a visible title is not a section.
            assert group.title().strip()
    finally:
        _destroy(window, qapp)


def test_major_section_role_does_not_leak_to_unrelated_group_boxes(
    qapp: QApplication,
) -> None:
    """Only the semantic workflow sections may carry the region role.

    The role is what turns a group into a card, so a leak is exactly the "card
    soup" failure. Every other ``QGroupBox`` reachable from the running window -
    including the ones the unified Settings surface composes - must stay flat.
    """

    from app.ui.preferences.settings_dialog import UnifiedSettingsDialog

    _fresh_settings()
    window = MainWindow()
    window.resize(1200, 800)
    window.show()
    try:
        # Every group a workflow page's own top-level layout owns is a Major
        # Section by construction. Anything else - a nested group, a dialog
        # group, a group on a support surface - must stay flat.
        promoted: set[int] = set()
        workflow_pages = [
            shell
            for shell in window.findChildren(QWidget)
            if bool(shell.property("workflowPage"))
        ]
        assert workflow_pages, "no workflow page shells found"
        for shell in workflow_pages:
            scroll = shell.findChild(QScrollArea)
            assert scroll is not None and scroll.widget() is not None
            promoted.update(id(group) for group in _top_level_sections(scroll.widget()))

        leaked = [
            group.objectName() or group.title()
            for group in window.findChildren(QGroupBox)
            if id(group) not in promoted and group.property("sectionRole") == "major"
        ]
        assert leaked == [], f"section role leaked onto non-section groups: {leaked}"

        # In particular, the region treatment never nests: a group inside a
        # Major Section would be exactly the card-soup failure.
        for surface_id in ("build", "allocate"):
            for section in _top_level_sections(_page_content(window, surface_id)):
                nested = section.findChildren(QGroupBox)
                assert nested == [], f"{section.objectName()} nests groups: {nested}"

        dialog = UnifiedSettingsDialog(
            window._prefs, window._user_settings, window._translator, window
        )
        try:
            groups = dialog.findChildren(QGroupBox)
            assert groups, "settings surface is expected to compose groups"
            assert all(group.property("sectionRole") != "major" for group in groups)
        finally:
            dialog.deleteLater()
    finally:
        _destroy(window, qapp)


def test_default_group_box_presentation_stays_flat() -> None:
    """The global group rule must remain the flat non-card default."""

    default_rule = _qss_rule_body("QGroupBox")
    assert "background-color: transparent" in default_rule
    assert "border: none" in default_rule

    # The card treatment must be reachable only through the semantic role.
    assert 'QGroupBox[sectionRole="major"]' in QSS_SOURCE
    card_rule = _qss_rule_body('QGroupBox[sectionRole="major"]')
    assert "background-color: {surface_primary}" in card_rule
    assert "border: 1px solid {boundary_subtle}" in card_rule
    assert "border-radius: {container_radius}px" in card_rule


def test_section_identity_is_not_derived_from_title_text() -> None:
    """Section promotion must not match Persian/English copy or child indexes."""

    source = (ROOT / "app/ui/main_window_presentation_base.py").read_text(encoding="utf-8")
    promotion = source.split("def _promote_major_sections", 1)[1].split("\n    def ", 1)[0]
    assert "title()" not in promotion
    assert "text()" not in promotion
    # Structural identity: a Major Section is a group the page layout owns.
    assert "isinstance(group, QGroupBox)" in promotion


# ------------------------------------------------------------- CL-UI-SECTION-02
def test_section_region_material_uses_existing_semantic_roles() -> None:
    """No section may introduce an independent colour authority."""

    card_rule = _qss_rule_body('QGroupBox[sectionRole="major"]')
    title_rule = _qss_rule_body('QGroupBox[sectionRole="major"]::title')
    for rule in (card_rule, title_rule):
        assert not re.search(r"#[0-9A-Fa-f]{3,8}", rule), f"hard-coded colour: {rule}"
        assert "rgb" not in rule

    # The title paints the region's own surface, never a page-coloured rectangle
    # cutting through it.
    assert "background-color: transparent" in title_rule
    assert "{background}" not in title_rule

    for mode in ("light", "dark"):
        stylesheet = build_stylesheet(build_theme(mode))
        assert re.search(r"\{[a-z_]+\}", stylesheet) is None


def test_section_titles_keep_the_strong_semantic_title_role(qapp: QApplication) -> None:
    """A section title must outrank an ordinary field label by role, not size alone."""

    typography = Theme().typography
    card_rule = _qss_rule_body('QGroupBox[sectionRole="major"]')
    assert "font-size: {subtitle_size}pt" in card_rule
    assert "font-weight: 600" in card_rule
    assert typography.subtitle_size > typography.body_size

    _fresh_settings()
    window = MainWindow()
    window.resize(1200, 800)
    window.show()
    try:
        assert window.activate_surface("build")
        qapp.processEvents()
        content = _page_content(window, "build")
        section = _top_level_sections(content)[0]
        label = window.findChild(QLabel, "fieldHelp_build_inspactor")
        assert label is not None

        section_font = section.font()
        assert section_font.bold() or section_font.weight() >= 600
        assert section_font.pointSize() > label.font().pointSize()
    finally:
        _destroy(window, qapp)


@pytest.mark.parametrize("language", [Language.FA, Language.EN])
def test_section_titles_use_logical_leading_alignment(
    qapp: QApplication, language: Language
) -> None:
    """The title sits on the region's leading edge in both directions.

    The same inset in RTL and LTR proves the rule is direction-safe rather than
    carrying a physical left/right assumption.
    """

    _fresh_settings()
    window = MainWindow()
    window._apply_language(language)
    window.resize(1200, 800)
    window.show()
    try:
        rtl = qapp.layoutDirection() == Qt.LayoutDirection.RightToLeft
        assert rtl is (language is Language.FA)
        for surface_id in ("build", "allocate"):
            assert window.activate_surface(surface_id)
            qapp.processEvents()
            for group in _top_level_sections(_page_content(window, surface_id)):
                option = QStyleOptionGroupBox()
                group.initStyleOption(option)
                style = group.style()
                title = style.subControlRect(
                    QStyle.ComplexControl.CC_GroupBox,
                    option,
                    QStyle.SubControl.SC_GroupBoxLabel,
                    group,
                )
                body = style.subControlRect(
                    QStyle.ComplexControl.CC_GroupBox,
                    option,
                    QStyle.SubControl.SC_GroupBoxContents,
                    group,
                )
                leading = group.width() - title.right() - 1 if rtl else title.left()
                assert 0 < leading <= Theme().major_section_padding + 4, (
                    f"{surface_id}/{group.objectName()}: title inset={leading}"
                )
                # The title is inside the region and never collides with row one.
                assert group.rect().contains(title)
                assert title.bottom() < body.top()
    finally:
        _destroy(window, qapp)


# ------------------------------------------------------------- CL-UI-SPACING-01
def test_macro_section_gap_is_one_named_token() -> None:
    theme = Theme()
    assert theme.major_section_gap > theme.within_group
    assert theme.major_section_extra_gap == theme.major_section_gap - theme.within_group
    assert theme.major_section_title_band == (
        theme.major_section_padding + theme.major_section_title_line + theme.within_group
    )
    # The gap reaches the QSS through the token, never as a repeated literal.
    card_rule = _qss_rule_body('QGroupBox[sectionRole="major"]')
    assert "margin-top: {major_section_extra_gap}px" in card_rule
    assert "{major_section_title_band}px" in card_rule
    assert "{major_section_padding}px" in card_rule
    assert not re.search(r"margin-top: \d+px", card_rule)


@pytest.mark.parametrize("surface_id", ["build", "allocate"])
def test_inter_section_gap_exceeds_the_intra_section_row_gap(
    qapp: QApplication, surface_id: str
) -> None:
    _fresh_settings()
    window = MainWindow()
    window.resize(1200, 800)
    window.show()
    try:
        assert window.activate_surface(surface_id)
        qapp.processEvents()
        theme = window._theme
        content = _page_content(window, surface_id)
        sections = _top_level_sections(content)
        assert len(sections) >= 2

        boundaries = [_section_boundary(group, content) for group in sections]
        gaps = [
            later.top() - earlier.bottom() - 1
            for earlier, later in zip(boundaries, boundaries[1:])
        ]
        assert gaps, "expected at least one inter-section gap"
        for gap in gaps:
            assert gap == theme.major_section_gap
            assert gap > theme.within_group
    finally:
        _destroy(window, qapp)


# -------------------------------------------------------------- CL-UI-ACTION-01
def test_fixed_action_footer_architecture_is_retired() -> None:
    """No dead fixed-footer path may remain behind the new contract."""

    for name in ("main_window.py", "main_window_presentation_base.py"):
        source = (ROOT / "app/ui" / name).read_text(encoding="utf-8")
        assert "pageActionFooter" not in source
        assert "_fixed_action_page" not in source
        assert "_sync_footer_working_column" not in source
    assert "pageActionFooter" not in QSS_SOURCE
    assert "QFrame#pageActionRegion" in QSS_SOURCE


@pytest.mark.parametrize(
    ("surface_id", "button_attribute"),
    [("build", "_btn_build"), ("allocate", "_btn_allocate")],
)
def test_primary_action_is_contained_in_the_page_content(
    qapp: QApplication, surface_id: str, button_attribute: str
) -> None:
    _fresh_settings()
    window = MainWindow()
    window.resize(1200, 800)
    window.show()
    try:
        assert window.activate_surface(surface_id)
        qapp.processEvents()
        content = _page_content(window, surface_id)
        surface = window._workspace_surfaces[surface_id]
        button = getattr(window, button_attribute)
        region = _action_region(content)

        # The action belongs to the region, and the region to the scrolled content.
        assert button.parentWidget() is region
        assert content.isAncestorOf(region)
        scroll = surface.findChild(QScrollArea)
        assert scroll is not None and scroll.widget() is content
        assert scroll.widget().isAncestorOf(button)

        # ...and it is not a fixed sibling pinned beneath the ScrollArea.
        shell_layout = surface.layout()
        assert shell_layout is not None
        assert shell_layout.count() == 1
        assert shell_layout.itemAt(0).widget() is scroll
        assert surface.findChild(QFrame, "pageActionFooter") is None

        # The action follows the final Major Section with no expanding spacer.
        outer = content.layout()
        indexes = {
            "sections": [
                index
                for index in range(outer.count())
                if isinstance(outer.itemAt(index).widget(), QGroupBox)
            ],
            "action": next(
                index
                for index in range(outer.count())
                if outer.itemAt(index).widget() is region
            ),
        }
        assert indexes["action"] > max(indexes["sections"])
        assert not [
            index
            for index in range(max(indexes["sections"]) + 1, indexes["action"])
            if outer.itemAt(index).spacerItem() is not None
        ]

        # The visible separation stays inside the macro rhythm, so the action
        # never floats away from the form it submits.
        last = _section_boundary(
            outer.itemAt(max(indexes["sections"])).widget(), content
        )
        gap = _mapped_rect(button, content).top() - last.bottom() - 1
        assert 0 < gap <= window._theme.major_section_gap
    finally:
        _destroy(window, qapp)


@pytest.mark.parametrize("language", [Language.FA, Language.EN])
def test_action_region_shares_the_working_column(
    qapp: QApplication, language: Language
) -> None:
    _fresh_settings()
    window = MainWindow()
    window._apply_language(language)
    window.show()
    try:
        tolerance = window._theme.scrollbar_thickness + window._theme.micro
        for size in ((960, 640), (1200, 800), LARGE_DESKTOP):
            window.resize(*size)
            qapp.processEvents()
            for surface_id, button in (
                ("build", window._btn_build),
                ("allocate", window._btn_allocate),
            ):
                assert window.activate_surface(surface_id)
                qapp.processEvents()
                content = _page_content(window, surface_id)
                region = _action_region(content)

                assert content.width() <= window._theme.working_measure
                assert region.width() <= window._theme.working_measure

                margins = content.layout().contentsMargins()
                content_rect = _mapped_rect(content, window)
                inner = content_rect.adjusted(margins.left(), 0, -margins.right(), 0)
                button_rect = _mapped_rect(button, window)
                drift = (
                    abs(button_rect.left() - inner.left())
                    if language is Language.FA
                    else abs(button_rect.right() - inner.right())
                )
                assert drift <= tolerance, f"{size} {surface_id}: action drift={drift}px"
    finally:
        _destroy(window, qapp)


@pytest.mark.parametrize(
    ("surface_id", "slot", "button_attribute"),
    [
        ("build", "_start_build", "_btn_build"),
        ("allocate", "_start_allocate", "_btn_allocate"),
    ],
)
def test_primary_action_stays_wired_to_its_workflow_slot(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, surface_id: str, slot: str, button_attribute: str
) -> None:
    """Recomposing the action must not re-route or drop its execution wiring."""

    calls: list[str] = []
    monkeypatch.setattr(
        MainWindow, slot, lambda self, *args, **kwargs: calls.append(slot), raising=True
    )
    _fresh_settings()
    window = MainWindow()
    window.resize(1200, 800)
    window.show()
    try:
        assert window.activate_surface(surface_id)
        qapp.processEvents()
        button = getattr(window, button_attribute)
        assert button.isEnabled()
        assert button.property("variant") == "primary"
        # Keyboard accessibility survives the reparent into the region.
        assert button.focusPolicy() != Qt.FocusPolicy.NoFocus
        button.click()
        qapp.processEvents()
        assert calls == [slot]
    finally:
        _destroy(window, qapp)


# --------------------------------------------------------------- CL-UI-LARGE-01
@pytest.mark.parametrize("language", [Language.FA, Language.EN])
def test_large_desktop_keeps_content_top_aligned_and_action_attached(
    qapp: QApplication, language: Language
) -> None:
    """The defect this work unit retires is geometric, so it is measured.

    On a large desktop window the page must not stretch its sections to fill the
    monitor, and the primary action must stay attached to the final section
    instead of being pushed to the window edge by unused vertical space.
    """

    _fresh_settings()
    window = MainWindow()
    window._apply_language(language)
    window.resize(*LARGE_DESKTOP)
    window.show()
    try:
        for surface_id, button in (
            ("build", window._btn_build),
            ("allocate", window._btn_allocate),
        ):
            assert window.activate_surface(surface_id)
            qapp.processEvents()
            content = _page_content(window, surface_id)
            surface = window._workspace_surfaces[surface_id]
            scroll = surface.findChild(QScrollArea)
            assert scroll is not None
            viewport = scroll.viewport()

            sections = _top_level_sections(content)
            boundaries = [_section_boundary(group, content) for group in sections]

            # Content is top-aligned: the first section starts near the top of the
            # page rather than being centred in the available height.
            assert boundaries[0].top() < viewport.height() // 2

            # Sections keep their natural height; none is stretched to fill.
            for group, boundary in zip(sections, boundaries):
                assert boundary.height() <= group.sizeHint().height() + 4

            # The action still follows the final section by the macro rhythm, and
            # is reachable by ordinary page scrolling.
            gap = _mapped_rect(button, content).top() - boundaries[-1].bottom() - 1
            assert 0 < gap <= window._theme.major_section_gap
            scroll.ensureWidgetVisible(button, 0, 0)
            qapp.processEvents()
            assert viewport.rect().contains(_mapped_rect(button, viewport))

            # No horizontal overflow and no clipped section at this size.
            assert (
                scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            assert not scroll.horizontalScrollBar().isVisibleTo(surface)
            for boundary in boundaries:
                assert boundary.left() >= 0
                assert boundary.right() <= content.width()
    finally:
        _destroy(window, qapp)


def test_bounded_field_measure_survives_the_section_pass(qapp: QApplication) -> None:
    _fresh_settings()
    window = MainWindow()
    window.show()
    try:
        measure = window._theme.field_measure
        for size in ((960, 640), LARGE_DESKTOP):
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


def test_layout_hosts_do_not_repaint_the_page_over_a_section(
    qapp: QApplication,
) -> None:
    """A bare row wrapper owns no surface and must not punch through a region.

    Before the region treatment this was invisible, because every group was
    transparent and the page background matched underneath.
    """

    assert 'QWidget[sectionRowHost="true"]' in QSS_SOURCE
    host_rule = _qss_rule_body(
        'QWidget[sectionRowHost="true"], QWidget[normalizedFileRow="true"], FilePicker'
    )
    assert "background-color: transparent" in host_rule

    _fresh_settings()
    window = MainWindow()
    window.resize(1200, 800)
    window.show()
    try:
        for surface_id in ("build", "allocate"):
            assert window.activate_surface(surface_id)
            qapp.processEvents()
            for group in _top_level_sections(_page_content(window, surface_id)):
                unmarked = [
                    child
                    for child in group.findChildren(QWidget)
                    if type(child) is QWidget
                    and child.layout() is not None
                    and not bool(child.property("sectionRowHost"))
                ]
                assert unmarked == [], (
                    f"{group.objectName()} hosts unmarked layout wrappers: "
                    f"{[child.objectName() for child in unmarked]}"
                )
    finally:
        _destroy(window, qapp)

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from PySide6.QtCore import QCalendar, QDate, QSignalBlocker, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QScrollArea

import app.ui.main_window_base as base
from app.infra.cli_legacy import _read_optional_first_sheet
from app.ui.helpers.academic_year import suggest_academic_year
from app.ui.i18n import Language
from app.ui.main_window import MainWindow


@pytest.mark.parametrize(
    ("gregorian", "jalali", "expected"),
    [
        ((2026, 6, 21), (1405, 3, 31), 1404),
        ((2026, 6, 22), (1405, 4, 1), 1405),
        ((2026, 11, 1), (1405, 8, 10), 1405),
        ((2027, 4, 4), (1406, 1, 15), 1405),
        ((2027, 6, 21), (1406, 3, 31), 1405),
        ((2027, 6, 22), (1406, 4, 1), 1406),
        ((2027, 3, 20), (1405, 12, 29), 1405),
        ((2027, 3, 21), (1406, 1, 1), 1405),
        ((2025, 3, 20), (1403, 12, 30), 1403),
        ((2025, 3, 21), (1404, 1, 1), 1403),
    ],
    ids=[
        "1405-last-khordad",
        "1405-first-tir",
        "1405-aban",
        "1406-farvardin",
        "1406-last-khordad",
        "1406-first-tir",
        "1405-year-end",
        "1406-nowruz",
        "1403-leap-day",
        "1404-nowruz",
    ],
)
def test_calendar_boundaries(
    gregorian: tuple[int, int, int], jalali: tuple[int, int, int], expected: int
) -> None:
    date = QDate(*gregorian)
    parts = QCalendar(QCalendar.System.Jalali).partsFromDate(date)
    assert (parts.year, parts.month, parts.day) == jalali
    assert suggest_academic_year(date) == expected


@pytest.mark.parametrize("local_date", [QDate(), QDate(1900, 1, 1)])
def test_invalid_or_unsupported_clock_date_has_no_suggestion(local_date: QDate) -> None:
    assert suggest_academic_year(local_date) is None


@dataclass
class _AllocateHarness:
    window: MainWindow
    local_date: list[QDate]
    warnings: list[str] = field(default_factory=list)
    preflights: list[Callable[[], None]] = field(default_factory=list)
    launches: list[tuple[list[str], dict[str, object]]] = field(default_factory=list)


@pytest.fixture
def allocate_harness(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> _AllocateHarness:
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))
    local_date = [QDate(2026, 6, 22)]
    monkeypatch.setattr(base, "suggest_academic_year", lambda: suggest_academic_year(local_date[0]))
    window = MainWindow()
    harness = _AllocateHarness(window, local_date)
    monkeypatch.setattr(
        base, "compute_reference_readiness", lambda **_: SimpleNamespace(is_ready_for_run=True)
    )
    monkeypatch.setattr(
        QMessageBox, "warning", lambda _parent, _title, text: harness.warnings.append(text)
    )
    monkeypatch.setattr(
        window,
        "_run_unknowns_preflight",
        lambda _argv, *, on_proceed, **_: harness.preflights.append(on_proceed),
    )
    monkeypatch.setattr(
        window,
        "_launch_cli",
        lambda argv, _action, *, overrides, **_: harness.launches.append((list(argv), overrides)),
    )
    window.show()
    window.activateWindow()
    qapp.processEvents()  # Complete the startup refresh before setting the synthetic pool path.
    for picker, name in (
        (window._picker_students, "synthetic-students.xlsx"),
        (window._picker_pool, "synthetic-pool.xlsx"),
        (window._picker_sabt_profile_alloc, "synthetic-profile.xlsx"),
        (window._picker_prior_roster, "synthetic-prior.csv"),
        (window._picker_current_roster, "synthetic-current.csv"),
    ):
        path = tmp_path / name
        # These files are never opened by the dispatch spy or preflight stub.
        picker.setText(str(path))
        path.touch()
    window._picker_alloc_out.setText(str(tmp_path / "allocation.xlsx"))
    return harness


@pytest.mark.parametrize("entry", ["button", "shortcut"])
@pytest.mark.parametrize(
    ("optional", "has_prior", "has_current", "allowed"),
    [
        (False, False, False, False),
        (False, True, False, False),
        (False, False, True, False),
        (False, True, True, True),
        (True, False, False, True),
        (True, True, False, True),
        (True, False, True, True),
        (True, True, True, True),
    ],
)
def test_allocate_roster_presence_gate(
    allocate_harness: _AllocateHarness,
    qapp: QApplication,
    entry: str,
    optional: bool,
    has_prior: bool,
    has_current: bool,
    allowed: bool,
) -> None:
    harness = allocate_harness
    window = harness.window
    assert window.activate_surface("allocate")
    assert not window._optional_roster.isChecked()
    inputs = (
        ("prior_roster", window._picker_prior_roster, has_prior, "Prior roster"),
        ("current_roster", window._picker_current_roster, has_current, "Current roster"),
    )
    for _key, picker, present, _label in inputs:
        if not present:
            picker.setText("  ")
    paths = {key: picker.text() for key, picker, _present, _label in inputs if picker.text()}
    window._academic_year_confirm.click()
    window._optional_roster.setChecked(optional)
    assert window._academic_year_confirm.isChecked()
    assert all(picker.text() == paths.get(key, "") for key, picker, _, _ in inputs)
    assert not harness.preflights

    if entry == "shortcut":
        QTest.keyClick(window, Qt.Key.Key_L, Qt.KeyboardModifier.ControlModifier)
    else:
        scroll = window._allocate_tab.findChild(QScrollArea)
        assert scroll is not None
        scroll.ensureWidgetVisible(window._btn_allocate)
        qapp.processEvents()
        QTest.mouseClick(window._btn_allocate, Qt.MouseButton.LeftButton)
    qapp.processEvents()

    if not allowed:
        assert not harness.preflights and not harness.launches
        missing = [f"• {label}" for _key, _picker, present, label in inputs if not present]
        assert harness.warnings == ["\n".join(["Select the required roster files.", *missing])]
        assert window._academic_year_confirm.isChecked()
        return

    assert len(harness.preflights) == 1 and not harness.launches and not harness.warnings
    harness.preflights[0]()
    [(argv, overrides)] = harness.launches
    for key, _picker, present, _label in inputs:
        flag = "--" + key.replace("_", "-")
        if present:
            assert argv[argv.index(flag) + 1] == overrides[key] == paths[key]
        else:
            assert flag not in argv and key not in overrides


def test_standard_mode_rechecks_paths_captured_before_preflight(
    allocate_harness: _AllocateHarness,
) -> None:
    harness = allocate_harness
    window = harness.window
    prior = window._picker_prior_roster.text()
    window._picker_prior_roster.setText("")
    window._optional_roster.setChecked(True)
    window._academic_year_confirm.click()
    window._start_allocate()
    assert len(harness.preflights) == 1

    window._optional_roster.setChecked(False)
    window._picker_prior_roster.setText(prior)
    harness.preflights[0]()
    assert not harness.launches
    assert harness.warnings == ["Select the required roster files.\n• Prior roster"]
    assert window._operation_state == "cancelled"
    assert window._academic_year_confirm.isChecked()

    # Retry with the now-complete inputs, then reuse the exact same files.
    for attempt in (1, 2):
        if not window._academic_year_confirm.isChecked():
            window._academic_year_confirm.click()
        window._start_allocate()
        harness.preflights[attempt]()
    assert len(harness.launches) == 2
    assert harness.launches[0][0] == harness.launches[1][0]
    assert harness.launches[0][1]["current_roster"] == harness.launches[1][1]["current_roster"]


def test_optional_roster_mode_keeps_other_allocate_guards(
    allocate_harness: _AllocateHarness, tmp_path: Path
) -> None:
    harness = allocate_harness
    window = harness.window
    window._optional_roster.setChecked(True)
    assert not window._academic_year_confirm.isChecked()
    window._start_allocate()
    assert "Confirm the displayed academic year" in harness.warnings[-1]
    window._academic_year_confirm.click()

    worker = base.Worker(lambda **_: None)
    window._worker = worker
    try:
        window._start_allocate()
        assert "عملیات جاری" in harness.warnings[-1]
    finally:
        window._worker = None
    missing = tmp_path / "unavailable-roster.csv"
    window._picker_current_roster.setText(str(missing))
    window._start_allocate()
    assert str(missing) in harness.warnings[-1]
    assert not harness.preflights and not harness.launches


def test_optional_mode_forwards_malformed_roster_to_existing_reader(
    allocate_harness: _AllocateHarness, tmp_path: Path
) -> None:
    harness = allocate_harness
    window = harness.window
    malformed = tmp_path / "not-a-workbook.xlsx"
    malformed.write_bytes(b"synthetic invalid workbook")
    window._picker_prior_roster.setText("")
    window._picker_current_roster.setText(str(malformed))
    window._optional_roster.setChecked(True)
    window._academic_year_confirm.click()
    window._start_allocate()
    assert len(harness.preflights) == 1
    harness.preflights[0]()
    [(_argv, overrides)] = harness.launches
    assert overrides["current_roster"] == str(malformed)
    with pytest.raises(ValueError):
        _read_optional_first_sheet(str(overrides["current_roster"]))


def test_optional_roster_mode_is_not_restored_in_new_workspace(
    allocate_harness: _AllocateHarness,
) -> None:
    window = allocate_harness.window
    window._optional_roster.setChecked(True)
    window.close()
    reopened = MainWindow()
    try:
        assert not reopened._optional_roster.isChecked()
    finally:
        reopened.close()


@pytest.mark.parametrize("entry", ["button", "shortcut", "direct"])
def test_allocate_entry_requires_conscious_confirmation_for_each_dispatch(
    allocate_harness: _AllocateHarness, qapp: QApplication, entry: str
) -> None:
    harness = allocate_harness
    window = harness.window
    confirm = window._academic_year_confirm
    assert window._combo_academic_year.currentText() == "1405"
    assert window._combo_academic_year.currentIndex() == window._combo_academic_year.findText(
        "1405"
    )
    assert not confirm.isChecked()

    def _request_allocate() -> None:
        if entry == "shortcut":
            QTest.keyClick(window, Qt.Key.Key_L, Qt.KeyboardModifier.ControlModifier)
        elif entry == "button":
            assert window.activate_surface("allocate")
            scroll = window._allocate_tab.findChild(QScrollArea)
            assert scroll is not None
            scroll.ensureWidgetVisible(window._btn_allocate)
            qapp.processEvents()
            QTest.mouseClick(window._btn_allocate, Qt.MouseButton.LeftButton)
        else:
            window._start_allocate()
        qapp.processEvents()

    _request_allocate()
    assert not harness.preflights and not harness.launches
    assert harness.warnings == ["Confirm the displayed academic year, then run Allocate again."]
    assert window.current_surface_id() == "allocate"
    assert confirm.hasFocus()
    assert not confirm.isChecked()

    confirm.setChecked(True)  # A programmatic check is not an operator click.
    _request_allocate()
    assert not harness.preflights and not harness.launches and not confirm.isChecked()

    QTest.keyClick(confirm, Qt.Key.Key_Space)
    assert confirm.isChecked()
    _request_allocate()
    assert len(harness.preflights) == 1 and not harness.launches
    harness.preflights[0]()
    [(argv, overrides)] = harness.launches
    assert argv[0] == "allocate"
    assert argv[argv.index("--academic-year") + 1] == "1405"
    assert overrides["academic_year"] == 1405
    assert not confirm.isChecked()

    _request_allocate()
    assert len(harness.preflights) == len(harness.launches) == 1
    assert len(harness.warnings) == 3


def test_reentering_allocate_refreshes_untouched_suggestion_and_keeps_manual_choice(
    allocate_harness: _AllocateHarness,
) -> None:
    harness = allocate_harness
    window = harness.window
    harness.local_date[0] = QDate(2027, 6, 22)
    assert window.activate_surface("allocate")
    assert window._combo_academic_year.currentText() == "1406"
    window._combo_academic_year.setEditText("1404")
    window._academic_year_confirm.click()

    harness.local_date[0] = QDate(2028, 11, 1)
    assert window.activate_surface("build")
    assert window.activate_surface("allocate")
    assert "1407" in window._academic_year_hint.text()
    assert window._combo_academic_year.currentText() == "1404"
    assert window._academic_year_confirm.isChecked()


def test_manual_edit_and_late_programmatic_change_cannot_reuse_a_confirmation(
    allocate_harness: _AllocateHarness, qapp: QApplication
) -> None:
    harness = allocate_harness
    window = harness.window
    assert window.activate_surface("allocate")
    confirm = window._academic_year_confirm
    confirm.click()
    window._start_allocate()
    assert len(harness.preflights) == 1

    edit = window._combo_academic_year.lineEdit()
    assert edit is not None
    edit.selectAll()
    QTest.keyClicks(edit, "1404")
    assert not confirm.isChecked()
    window._set_academic_year(1405)
    confirm.click()
    harness.preflights[0]()
    assert not harness.launches
    assert window._operation_state == "cancelled"
    assert confirm.isChecked()  # This confirmation is available to a new attempt.

    with QSignalBlocker(window._combo_academic_year):
        window._set_academic_year(1406)
    qapp.processEvents()
    window._start_allocate()
    assert len(harness.preflights) == 1 and not harness.launches
    assert not confirm.isChecked()


def test_preflight_corrections_keep_confirmation_until_allocation_dispatches(
    allocate_harness: _AllocateHarness,
) -> None:
    harness = allocate_harness
    window = harness.window
    confirm = window._academic_year_confirm
    profile = window._picker_sabt_profile_alloc.text()
    confirm.click()
    window._picker_sabt_profile_alloc.setText("")
    window._start_allocate()
    assert confirm.isChecked() and not harness.preflights
    window._picker_sabt_profile_alloc.setText(profile)
    window._start_allocate()
    assert len(harness.preflights) == 1 and confirm.isChecked()

    # The first preflight did not proceed. Retry with the same confirmed year.
    window._start_allocate()
    assert len(harness.preflights) == 2 and confirm.isChecked()
    harness.preflights[1]()
    assert len(harness.launches) == 1 and not confirm.isChecked()


def test_roster_offer_preserves_manual_choice_and_explicit_use_requires_reconfirmation(
    allocate_harness: _AllocateHarness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = allocate_harness
    window = harness.window
    picker = window._picker_current_roster
    confirm = window._academic_year_confirm
    callbacks: list[Callable[[pd.DataFrame], None]] = []
    monkeypatch.setattr(
        window, "_run_excel_loader", lambda _path, *, on_loaded, **_: callbacks.append(on_loaded)
    )
    roster = pd.DataFrame({"student_id": ["543570007", "543730009"]})
    assert window.activate_surface("allocate")
    picker.setText(str(tmp_path / "first.csv"))
    window._autodetect_counters()
    picker.setText(str(tmp_path / "second.csv"))
    window._autodetect_counters()
    window._set_academic_year(1403)
    confirm.click()

    callbacks[0](roster)
    assert window._btn_use_roster_year.isHidden()
    assert window._allocate_counter_preview_label.isHidden()
    callbacks[1](roster)
    assert window._combo_academic_year.currentText() == "1403"
    assert confirm.isChecked()
    assert window._btn_use_roster_year.isVisible()
    assert window._btn_use_roster_year.text() == "Use roster year 1404"
    assert "The system date suggests 1405" in window._academic_year_hint.text()
    assert "543570007" in window._allocate_counter_preview_label.text()
    assert "543730009" in window._allocate_counter_preview_label.text()

    window._btn_use_roster_year.click()
    assert window._combo_academic_year.currentText() == "1404"
    assert not confirm.isChecked()
    assert window._btn_use_roster_year.isHidden()
    assert window._allocate_counter_preview_label.isHidden()


@pytest.mark.parametrize(
    ("selected", "ids", "basis", "latest"),
    [
        (1404, ["543570007", "543730009"], 1404, "543570007"),
        (1403, ["543570007", "543730009"], 1404, "543570007"),
        (1403, ["543570007", "533570005"], 1403, "533570005"),
        (1403, [], 1403, None),
        (None, [], None, None),
    ],
    ids=["same-year", "different-year", "fallback", "unknown-roster", "no-basis"],
)
def test_counter_preview_identifies_basis_and_tracks_selection(
    allocate_harness: _AllocateHarness,
    selected: int | None,
    ids: list[str],
    basis: int | None,
    latest: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = allocate_harness.window
    monkeypatch.setattr(window._prefs, "set_language", lambda _language: None)
    window._apply_language(Language.EN)
    assert window.activate_surface("allocate")
    window._combo_academic_year.setEditText(str(selected) if selected is not None else "")
    confirm = window._academic_year_confirm
    if selected is not None:
        confirm.click()
    window._process_counter_dataframe(
        pd.DataFrame({"student_id": ids}), window._combo_academic_year
    )
    preview = window.findChild(QLabel, "allocateCounterPreview")
    assert preview is not None and preview.isVisible(), "Counter values need a scoped preview"
    assert preview.wordWrap()
    assert preview.layoutDirection() == Qt.LayoutDirection.LeftToRight
    english = preview.text()
    expected_selection = (
        "Selected Allocate year is unset."
        if selected is None
        else f"Selected Allocate year is {selected}."
    )
    expected_basis = (
        "Counter basis year is unavailable." if basis is None else f"Counter basis year is {basis}."
    )
    assert expected_selection in english
    assert expected_basis in english
    if ids and basis == 1403:
        assert "Possible roster year is 1404." in english
        assert "Next boys’ sequence 0006" in english
    if not ids:
        assert "Roster year could not be detected." in english
    if latest is not None:
        assert f"Latest boys’ ID {latest}" in english
    if basis == 1404:
        assert "Next boys’ sequence 0008" in english
        assert "Next girls’ sequence 0010" in english
    assert window._get_academic_year() == selected
    assert confirm.isChecked() == (selected is not None)

    window._apply_language(Language.FA)
    assert preview.layoutDirection() == Qt.LayoutDirection.RightToLeft
    persian = preview.text()
    assert "سال انتخاب‌شده برای تخصیص" in persian
    assert "سال مبنای شمارنده" in persian
    if latest is not None:
        assert latest in persian and "آخرین شناسهٔ پسران" in persian
    assert confirm.isChecked() == (selected is not None)

    window._set_academic_year(1405)
    assert preview.isHidden() and not preview.text()
    assert not confirm.isChecked()


@pytest.mark.parametrize("value", ["", "abc", "1349", "1450"])
def test_unsupported_year_is_rejected_before_preflight(
    allocate_harness: _AllocateHarness, value: str
) -> None:
    harness = allocate_harness
    window = harness.window
    window._combo_academic_year.setEditText(value)
    window._start_allocate()
    assert not harness.preflights and not harness.launches
    assert harness.warnings == ["Enter a valid academic year from 1350 to 1449."]
    assert "academic_year" not in window._build_allocate_overrides()


@pytest.mark.parametrize(("text", "year"), [("۱۳۵۰", 1350), ("1449", 1449)])
def test_unavailable_date_allows_manual_entry_at_core_limits(
    allocate_harness: _AllocateHarness, tmp_path: Path, text: str, year: int
) -> None:
    harness = allocate_harness
    window = harness.window
    harness.local_date[0] = QDate()
    assert window.activate_surface("allocate")
    assert window._combo_academic_year.currentText() == ""
    assert not window._academic_year_confirm.isChecked()
    assert "System-date suggestion unavailable" in window._academic_year_hint.text()
    window._combo_academic_year.setEditText(text)
    # Switching academic-year context clears any manually set prior-year path.
    assert window._picker_prior_roster.text() == ""
    prior = tmp_path / "synthetic-prior.csv"
    window._picker_prior_roster.setText(str(prior))
    window._academic_year_confirm.click()
    window._start_allocate()
    assert len(harness.preflights) == 1
    harness.preflights[0]()
    assert harness.launches[0][1]["academic_year"] == year


def test_language_switch_preserves_value_and_confirmation_and_localizes_controls(
    allocate_harness: _AllocateHarness, qapp: QApplication
) -> None:
    window = allocate_harness.window
    assert window.activate_surface("allocate")
    assert qapp.layoutDirection() == Qt.LayoutDirection.LeftToRight
    assert window._combo_academic_year.accessibleName() == "Academic year"
    assert (
        window._academic_year_confirm.text() == "Confirm this academic year for the next allocation"
    )
    window._apply_language(Language.FA)
    assert qapp.layoutDirection() == Qt.LayoutDirection.RightToLeft
    assert window._combo_academic_year.currentText() == "1405"
    assert not window._academic_year_confirm.isChecked()
    assert window._combo_academic_year.accessibleName() == "سال تحصیلی"
    assert "۱ تیر" in window._academic_year_hint.text()
    assert window._academic_year_confirm.text() == "سال تحصیلی را برای تخصیص بعدی تأیید می‌کنم"
    window._start_allocate()
    assert "تأیید کنید" in allocate_harness.warnings[-1]

    window._set_academic_year(1404)
    window._academic_year_confirm.click()
    window._apply_language(Language.EN)
    assert qapp.layoutDirection() == Qt.LayoutDirection.LeftToRight
    assert window._combo_academic_year.currentText() == "1404"
    assert window._academic_year_confirm.isChecked()


@pytest.mark.parametrize("language", [Language.FA, Language.EN])
def test_academic_year_controls_fit_and_render_at_compact_width(
    allocate_harness: _AllocateHarness, qapp: QApplication, language: Language
) -> None:
    window = allocate_harness.window
    window.resize(960, 640)
    window._apply_language(language)
    assert window.activate_surface("allocate")
    if expected_qpa := os.environ.get("MATRIX_ROSTER_EXPECTED_QPA"):
        assert qapp.platformName() == expected_qpa
        assert window.windowHandle() is not None
        assert QTest.qWaitForWindowExposed(window, 5000)
    if expected_dpr := os.environ.get("MATRIX_ROSTER_EXPECTED_DPR"):
        assert window.devicePixelRatioF() == pytest.approx(float(expected_dpr))
    confirm = window._academic_year_confirm
    scroll = window._allocate_tab.findChild(QScrollArea)
    assert scroll is not None
    scroll.ensureWidgetVisible(confirm)
    qapp.processEvents()

    viewport = scroll.viewport()
    for control in (window._combo_academic_year, window._academic_year_hint, confirm):
        assert control.isVisible()
        assert viewport.rect().contains(control.mapTo(viewport, control.rect().topLeft()))
        assert viewport.rect().contains(control.mapTo(viewport, control.rect().bottomRight()))
    assert confirm.width() >= confirm.sizeHint().width()
    assert not confirm.isChecked()

    optional = window._optional_roster
    expected_text = "حالت اختیاری Roster" if language is Language.FA else "Optional roster mode"
    assert optional.objectName() == "optionalRosterMode" and optional.text() == expected_text
    direction = (
        Qt.LayoutDirection.RightToLeft
        if language is Language.FA
        else Qt.LayoutDirection.LeftToRight
    )
    assert optional.layoutDirection() == confirm.layoutDirection() == direction
    assert not optional.isChecked()
    scroll.ensureWidgetVisible(optional)
    optional.setFocus()
    qapp.processEvents()
    assert optional.isVisible()
    assert viewport.rect().contains(optional.mapTo(viewport, optional.rect().topLeft()))
    assert viewport.rect().contains(optional.mapTo(viewport, optional.rect().bottomRight()))
    assert optional.hasFocus() and optional.width() >= optional.sizeHint().width()
    QTest.keyClick(optional, Qt.Key.Key_Space)
    assert optional.isChecked() and not confirm.isChecked()
    QTest.keyClick(optional, Qt.Key.Key_Space)
    assert not optional.isChecked()
    QTest.keyClick(optional, Qt.Key.Key_Tab)
    next_control = qapp.focusWidget()
    assert next_control is not None and next_control is not optional
    QTest.keyClick(next_control, Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
    assert optional.hasFocus()
    if language is Language.FA:
        window._picker_current_roster.setText("")
        confirm.click()
        window._start_allocate()
        assert allocate_harness.warnings == [
            "فایل‌های روستر الزامی را انتخاب کنید.\n• روستر سال جاری"
        ]
        assert not allocate_harness.preflights and confirm.isChecked()
        confirm.click()

    window._process_counter_dataframe(
        pd.DataFrame({"student_id": ["543570007", "543730009"]}), window._combo_academic_year
    )
    preview = window._allocate_counter_preview_label
    qapp.processEvents()  # Give the form layout a chance to size the newly visible preview.
    scroll.ensureWidgetVisible(preview)
    qapp.processEvents()
    assert preview.isVisible()
    assert viewport.rect().contains(preview.mapTo(viewport, preview.rect().topLeft()))
    assert viewport.rect().contains(preview.mapTo(viewport, preview.rect().bottomRight()))

    if evidence_dir := os.environ.get("MATRIX_ACADEMIC_YEAR_EVIDENCE"):
        output_dir = Path(evidence_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        registration = confirm.parentWidget()
        assert registration is not None and registration.objectName() == "registrationGroupBox"
        assert registration.grab().save(str(output_dir / f"academic-year-{language.code}.png"))


def test_deferred_allocate_rejects_changed_explicit_prior_selection(
    allocate_harness: _AllocateHarness, tmp_path: Path
) -> None:
    harness = allocate_harness
    window = harness.window
    window._academic_year_confirm.click()
    window._start_allocate()
    assert len(harness.preflights) == 1
    other = tmp_path / "replacement.csv"
    other.write_bytes(b"replacement")
    window._picker_prior_roster.setText(str(other))
    harness.preflights[0]()
    assert not harness.launches
    assert harness.warnings and "changed during preflight" in harness.warnings[-1]
    assert window._operation_state == "cancelled"


def test_deferred_allocate_rejects_modified_prior_file(
    allocate_harness: _AllocateHarness
) -> None:
    harness = allocate_harness
    window = harness.window
    window._academic_year_confirm.click()
    window._start_allocate()
    assert len(harness.preflights) == 1
    prior = Path(window._picker_prior_roster.text())
    prior.write_bytes(b"synthetic changed after preflight")
    harness.preflights[0]()
    assert not harness.launches
    assert "changed during preflight" in harness.warnings[-1]


def test_deferred_allocate_rejects_optional_switch_with_full_paths(
    allocate_harness: _AllocateHarness
) -> None:
    harness = allocate_harness
    window = harness.window
    window._academic_year_confirm.click()
    window._start_allocate()
    assert len(harness.preflights) == 1
    window._optional_roster.setChecked(True)
    harness.preflights[0]()
    assert not harness.launches
    assert "changed during preflight" in harness.warnings[-1]

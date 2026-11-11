"""Year-scoped prior Roster persistence through actual Qt/QSettings boundaries."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

import app.ui.main_window_base as base
from app.infra.cli_legacy import _read_optional_first_sheet
from app.ui.app_preferences import AppPreferences
from app.ui.i18n import Language
from app.ui.main_window import MainWindow
from app.ui.prior_roster_reference import (
    PriorRosterReference,
    capture_prior_roster,
    probe_prior_roster,
    reference_key,
)


@pytest.fixture
def isolated_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication
) -> tuple[Path, Path]:
    settings_file = tmp_path / "isolated-matrix-roster.ini"

    class IsolatedPreferences(AppPreferences):
        def __init__(self) -> None:
            super().__init__()
            self._settings = QSettings(str(settings_file), QSettings.Format.IniFormat)

    monkeypatch.setattr(base, "AppPreferences", IsolatedPreferences)
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))
    monkeypatch.setattr(base, "suggest_academic_year", lambda: 1405)
    return settings_file, tmp_path


def _operator_select(window: MainWindow, path: Path) -> None:
    """Exercise the editable FilePicker's actual commit signal, not only setText."""
    edit = window._picker_prior_roster.line_edit()
    edit.setText(str(path))
    edit.setModified(True)
    edit.editingFinished.emit()


def _new_window(qapp: QApplication) -> MainWindow:
    window = MainWindow()
    window.show()
    qapp.processEvents()
    assert window._get_academic_year() == 1405
    return window


def test_real_qsettings_store_and_new_window_restore(
    isolated_settings: tuple[Path, Path], qapp: QApplication
) -> None:
    settings_path, root = isolated_settings
    roster = root / "prior-roster.csv"
    roster.write_text("synthetic\n", encoding="utf-8")
    window = _new_window(qapp)
    _operator_select(window, roster)
    assert window._prior_reference_state == "stored"
    reference, state = window._prefs.read_prior_roster_reference(1405)
    assert state == "stored" and reference is not None
    assert reference.path == str(roster.resolve())
    assert reference.academic_year == 1405
    assert reference.sha256 and len(reference.sha256) == 64
    assert not any(key in reference.to_json().lower() for key in ("national_id", "student_id"))
    assert settings_path.is_file()
    window._prefs._settings.sync()
    window.close()
    restored = _new_window(qapp)
    assert restored._picker_prior_roster.text() == reference.path
    assert restored._prior_reference_state == "restored"
    assert "not yet validated" in restored._prior_reference_status.text()
    assert not restored._optional_roster.isChecked()
    assert not restored._academic_year_confirm.isChecked()


def test_year_switch_never_carries_reference_into_other_year(
    isolated_settings: tuple[Path, Path], qapp: QApplication
) -> None:
    _settings, root = isolated_settings
    prior = root / "prior.csv"
    prior.write_bytes(b"synthetic-first\n")
    window = _new_window(qapp)
    _operator_select(window, prior)
    window._set_academic_year(1406)
    assert window._picker_prior_roster.text() == ""
    assert window._prior_reference_state == "absent"
    window._set_academic_year(1405)
    assert window._picker_prior_roster.text() == str(prior)
    assert window._prior_reference_state == "restored"


def test_explicit_omission_stays_blank_through_refresh_and_toggle(
    isolated_settings: tuple[Path, Path], qapp: QApplication
) -> None:
    _settings, root = isolated_settings
    prior = root / "prior.csv"
    prior.write_bytes(b"synthetic\n")
    window = _new_window(qapp)
    _operator_select(window, prior)
    window._btn_omit_prior_reference.click()
    assert window._picker_prior_roster.text() == ""
    assert window._prior_reference_state == "omitted"
    window._optional_roster.setChecked(True)
    window._optional_roster.setChecked(False)
    window._apply_language(Language.FA)
    assert "حذف شد" in window._prior_reference_status.text()
    window._apply_language(Language.EN)
    window._refresh_academic_year_texts()
    window._sync_prior_roster_for_year()
    assert window._picker_prior_roster.text() == ""
    assert window._prefs.read_prior_roster_reference(1405)[1] == "stored"
    window.close()
    restored = _new_window(qapp)
    assert restored._picker_prior_roster.text() == str(prior)


def test_forget_is_year_scoped_and_does_not_resurrect(
    isolated_settings: tuple[Path, Path], qapp: QApplication
) -> None:
    _settings, root = isolated_settings
    prior = root / "prior.csv"
    next_prior = root / "next.csv"
    prior.write_bytes(b"first")
    next_prior.write_bytes(b"second")
    window = _new_window(qapp)
    _operator_select(window, prior)
    window._set_academic_year(1406)
    _operator_select(window, next_prior)
    assert window._prefs.read_prior_roster_reference(1406)[1] == "stored"
    window._set_academic_year(1405)
    window._btn_forget_prior_reference.click()
    assert window._picker_prior_roster.text() == ""
    assert window._prefs.read_prior_roster_reference(1405)[1] == "absent"
    assert window._prefs.read_prior_roster_reference(1406)[1] == "stored"
    window._refresh_academic_year_texts()
    assert window._picker_prior_roster.text() == ""


@pytest.mark.parametrize("change", ["rewrite", "move"])
def test_changed_or_missing_saved_path_is_not_silently_restored(
    isolated_settings: tuple[Path, Path], qapp: QApplication, change: str
) -> None:
    _settings, root = isolated_settings
    prior = root / "prior.csv"
    prior.write_bytes(b"first")
    first = _new_window(qapp)
    _operator_select(first, prior)
    first.close()
    if change == "rewrite":
        prior.write_bytes(b"second-version-with-different-length")
    else:
        prior.rename(root / "moved.csv")
    restored = _new_window(qapp)
    assert restored._picker_prior_roster.text() == ""
    assert restored._prior_reference_state == ("changed" if change == "rewrite" else "missing")
    assert restored._prefs.read_prior_roster_reference(1405)[1] == "stored"
    assert restored._btn_omit_prior_reference.isEnabled()


def test_replacement_recovers_from_changed_saved_file(
    isolated_settings: tuple[Path, Path], qapp: QApplication
) -> None:
    _settings, root = isolated_settings
    prior = root / "prior.csv"
    prior.write_bytes(b"first")
    window = _new_window(qapp)
    _operator_select(window, prior)
    window.close()
    prior.write_bytes(b"changed")
    restored = _new_window(qapp)
    assert restored._prior_reference_state == "changed"
    _operator_select(restored, prior)
    assert restored._prior_reference_state == "stored"
    ref, state = restored._prefs.read_prior_roster_reference(1405)
    assert state == "stored" and ref is not None and probe_prior_roster(ref) == "unchanged"


def test_invalid_descriptor_is_not_treated_as_valid_reference(
    isolated_settings: tuple[Path, Path], qapp: QApplication
) -> None:
    _settings, root = isolated_settings
    prior = root / "prior.csv"
    prior.write_bytes(b"synthetic")
    window = _new_window(qapp)
    _operator_select(window, prior)
    ref, _state = window._prefs.read_prior_roster_reference(1405)
    assert ref is not None
    key = reference_key(1405)
    for value in (
        "not JSON",
        json.dumps({**json.loads(ref.to_json()), "academic_year": 1406}),
        json.dumps({**json.loads(ref.to_json()), "version": 999}),
        json.dumps({**json.loads(ref.to_json()), "size": -1}),
        json.dumps({**json.loads(ref.to_json()), "sha256": "missing"}),
    ):
        window._prefs._settings.setValue(key, value)
        window._prefs._settings.sync()
        assert window._prefs.read_prior_roster_reference(1405) == (None, "malformed")
    window.close()
    broken = _new_window(qapp)
    assert broken._prior_reference_state == "malformed"
    assert broken._picker_prior_roster.text() == ""


def test_descriptor_probe_distinguishes_local_identity_from_reader_validity(
    isolated_settings: tuple[Path, Path]
) -> None:
    _settings, root = isolated_settings
    corrupt_excel = root / "synthetic-invalid.xlsx"
    corrupt_excel.write_bytes(b"not an Excel workbook")
    preferences = AppPreferences()
    preferences._settings = QSettings(str(root / "unit.ini"), QSettings.Format.IniFormat)
    reference = preferences.store_prior_roster_reference(1405, str(corrupt_excel))
    assert probe_prior_roster(reference) == "unchanged"
    with pytest.raises(ValueError):
        _read_optional_first_sheet(str(corrupt_excel))


def test_unavailable_or_bad_settings_cannot_claim_success(
    isolated_settings: tuple[Path, Path]
) -> None:
    _settings, root = isolated_settings
    prior = root / "prior.csv"
    prior.write_bytes(b"synthetic")
    preferences = AppPreferences()

    class FailedSettings:
        def sync(self) -> None:
            pass

        def status(self) -> QSettings.Status:
            return QSettings.Status.AccessError

        def setValue(self, key: str, value: str) -> None:  # noqa: N802 - Qt API
            pass

        def remove(self, key: str) -> None:
            pass

    preferences._settings = FailedSettings()  # type: ignore[assignment]
    with pytest.raises(OSError, match="settings write failed"):
        preferences.store_prior_roster_reference(1405, str(prior))
    with pytest.raises(OSError, match="settings clear failed"):
        preferences.forget_prior_roster_reference(1405)
    assert preferences.read_prior_roster_reference(1405) == (None, "settings_error")


def test_descriptor_local_file_evidence_catches_same_size_mutation(
    isolated_settings: tuple[Path, Path]
) -> None:
    _settings, root = isolated_settings
    prior = root / "prior.csv"
    prior.write_bytes(b"abc")
    before: PriorRosterReference = capture_prior_roster(1405, str(prior))
    saved_mtime = prior.stat().st_mtime_ns
    prior.write_bytes(b"xyz")
    import os
    os.utime(prior, ns=(saved_mtime, saved_mtime))
    assert prior.stat().st_size == before.size
    assert prior.stat().st_mtime_ns == before.mtime_ns
    assert probe_prior_roster(before) == "changed"


def test_restored_reference_reaches_allocate_and_success_callback(
    isolated_settings: tuple[Path, Path], qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reconstruction -> restored input -> CLI arguments and success callback state.

    The real reader acceptance is separately asserted in the integration suite.
    """
    from types import SimpleNamespace

    import pandas as pd
    from PySide6.QtWidgets import QMessageBox

    _settings, root = isolated_settings
    prior = root / "prior.xlsx"
    pd.DataFrame(
        {"کد ملی": ["0000000001"], "student_id": ["533570123"]}
    ).to_excel(prior, index=False)
    first = _new_window(qapp)
    _operator_select(first, prior)
    first.close()
    restored = _new_window(qapp)
    assert restored._prior_reference_state == "restored"
    assert restored._picker_prior_roster.text() == str(prior)
    for picker, name in (
        (restored._picker_students, "students.xlsx"),
        (restored._picker_pool, "pool.xlsx"),
        (restored._picker_sabt_profile_alloc, "profile.xlsx"),
        (restored._picker_current_roster, "current.xlsx"),
    ):
        path = root / name
        path.touch()
        picker.setText(str(path))
    restored._picker_alloc_out.setText(str(root / "result.xlsx"))
    monkeypatch.setattr(
        base, "compute_reference_readiness",
        lambda **_: SimpleNamespace(is_ready_for_run=True),
    )

    def unexpected_warning(_parent: object, _title: str, detail: str) -> None:
        pytest.fail(f"Unexpected Allocate warning: {detail}")

    monkeypatch.setattr(QMessageBox, "warning", unexpected_warning)
    monkeypatch.setattr(
        restored, "_run_unknowns_preflight",
        lambda _args, *, on_proceed, **_: on_proceed(),
    )
    captured: list[tuple[list[str], dict[str, object]]] = []

    def launch(argv: list[str], _action: str, *, overrides: dict[str, object], on_success, **_) -> None:
        captured.append((list(argv), dict(overrides)))
        on_success()

    monkeypatch.setattr(restored, "_launch_cli", launch)
    for _attempt in range(2):
        if not restored._academic_year_confirm.isChecked():
            restored._academic_year_confirm.click()
        restored._start_allocate()
    assert len(captured) == 2
    for argv, overrides in captured:
        assert argv[argv.index("--prior-roster") + 1] == str(prior)
        assert overrides["prior_roster"] == str(prior)
        assert overrides["academic_year"] == 1405
        assert overrides["current_roster"] == str(root / "current.xlsx")
    assert restored._prior_reference_state == "reader_accepted"
    assert "does not prove official identity" in restored._prior_reference_status.text()
    assert _read_optional_first_sheet(str(prior)) is not None
    assert restored._prefs.read_prior_roster_reference(1405)[1] == "stored"


def test_reference_controls_keyboard_and_language(
    isolated_settings: tuple[Path, Path], qapp: QApplication
) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QScrollArea

    _settings, root = isolated_settings
    prior = root / "prior.csv"
    prior.write_bytes(b"synthetic")
    window = _new_window(qapp)
    _operator_select(window, prior)
    window.resize(960, 640)
    window._apply_language(Language.FA)
    assert window.activate_surface("allocate")
    assert "حذف موقت" in window._btn_omit_prior_reference.text()
    assert "فراموش" in window._btn_forget_prior_reference.text()
    assert window._prior_reference_status.layoutDirection() == Qt.LayoutDirection.RightToLeft
    scroll = window._allocate_tab.findChild(QScrollArea)
    assert scroll is not None
    scroll.ensureWidgetVisible(window._btn_omit_prior_reference)
    qapp.processEvents()
    window._btn_omit_prior_reference.setFocus()
    QTest.keyClick(window._btn_omit_prior_reference, Qt.Key.Key_Space)
    assert window._prior_reference_state == "omitted"
    assert window._picker_prior_roster.text() == ""
    window._apply_language(Language.EN)
    assert window._btn_forget_prior_reference.isEnabled()
    window._btn_forget_prior_reference.setFocus()
    QTest.keyClick(window._btn_forget_prior_reference, Qt.Key.Key_Space)
    assert window._prior_reference_state == "forgotten"
    assert window._prefs.read_prior_roster_reference(1405)[1] == "absent"
    assert window._btn_forget_prior_reference.layoutDirection() == Qt.LayoutDirection.LeftToRight


def test_inaccessible_file_is_reported_without_using_it(
    isolated_settings: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.ui.prior_roster_reference as reference_module

    _settings, root = isolated_settings
    path = root / "roster.csv"
    path.write_bytes(b"synthetic")
    ref = capture_prior_roster(1405, str(path))

    def blocked(_year: int, _path: str) -> PriorRosterReference:
        raise PermissionError("synthetic denied access")

    monkeypatch.setattr(reference_module, "capture_prior_roster", blocked)
    assert probe_prior_roster(ref) == "inaccessible"

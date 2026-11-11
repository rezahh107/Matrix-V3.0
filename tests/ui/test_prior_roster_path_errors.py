"""Regression for Python 3.11 pathlib symlink-loop errors in prior Roster UI."""

from __future__ import annotations

import errno
import hashlib
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox

import app.ui.main_window_base as base
from app.ui.app_preferences import AppPreferences
from app.ui.i18n import Language
from app.ui.main_window import MainWindow
from app.ui.prior_roster_reference import capture_prior_roster, probe_prior_roster


def _raise_from_resolve(
    monkeypatch: pytest.MonkeyPatch, affected: Path, message: str
) -> None:
    """Reproduce Python 3.11's exception without changing the host interpreter."""
    original = Path.resolve

    def resolve(self: Path, *args: object, **kwargs: object) -> Path:
        if self == affected:
            raise RuntimeError(message)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)


def _create_symlink(link: Path, target: str) -> None:
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Symlink creation unavailable on this host: {exc}")


@pytest.fixture
def new_roster_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qapp: QApplication
) -> Callable[[], MainWindow]:
    settings_path = tmp_path / "prior-roster-loop.ini"

    class IsolatedPreferences(AppPreferences):
        def __init__(self) -> None:
            super().__init__()
            self._settings = QSettings(str(settings_path), QSettings.Format.IniFormat)

    monkeypatch.setattr(base, "AppPreferences", IsolatedPreferences)
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))
    monkeypatch.setattr(base, "suggest_academic_year", lambda: 1405)

    def make_window() -> MainWindow:
        window = MainWindow()
        window.show()
        qapp.processEvents()
        assert window._get_academic_year() == 1405
        window._apply_language(Language.EN)
        return window

    return make_window


def _commit_prior_path(window: MainWindow, path: Path) -> None:
    edit = window._picker_prior_roster.line_edit()
    edit.setText(str(path))
    edit.setModified(True)
    edit.editingFinished.emit()


def test_python311_loop_runtimeerror_is_only_normalized_at_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "reference.csv"
    path.write_bytes(b"synthetic-data")
    reference = capture_prior_roster(1405, str(path))
    _raise_from_resolve(monkeypatch, path, f"Symlink loop from {str(path)!r}")
    with pytest.raises(OSError) as error:
        capture_prior_roster(1405, str(path))
    assert error.value.errno == errno.ELOOP
    assert isinstance(error.value.__cause__, RuntimeError)
    assert probe_prior_roster(reference) == "inaccessible"


def test_unrelated_resolve_runtimeerror_is_not_masked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "reference.csv"
    path.write_bytes(b"synthetic-data")
    _raise_from_resolve(monkeypatch, path, "unexpected runtime defect")
    with pytest.raises(RuntimeError, match="unexpected runtime defect"):
        capture_prior_roster(1405, str(path))


def test_real_symlink_loop_is_inaccessible_not_uncaught(tmp_path: Path) -> None:
    path = tmp_path / "cycle.csv"
    path.write_bytes(b"synthetic-data")
    reference = capture_prior_roster(1405, str(path))
    path.unlink()
    _create_symlink(path, path.name)
    with pytest.raises(OSError) as error:
        capture_prior_roster(1405, str(path))
    assert error.value.errno == errno.ELOOP
    assert probe_prior_roster(reference) == "inaccessible"


def test_valid_symlink_preserves_identity_and_hash(tmp_path: Path) -> None:
    path = tmp_path / "real.csv"
    payload = b"synthetic-content-only"
    path.write_bytes(payload)
    alias = tmp_path / "alias.csv"
    _create_symlink(alias, path.name)
    direct = capture_prior_roster(1405, str(path))
    linked = capture_prior_roster(1405, str(alias))
    assert linked == direct
    assert linked.sha256 == hashlib.sha256(payload).hexdigest()
    assert probe_prior_roster(linked) == "unchanged"
    assert linked.path == str(path.resolve())


def test_python311_loop_on_qsettings_restore_is_actionable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    new_roster_window: Callable[[], MainWindow],
) -> None:
    path = tmp_path / "prior.csv"
    path.write_bytes(b"synthetic-data")
    first = new_roster_window()
    _commit_prior_path(first, path)
    assert first._prior_reference_state == "stored"
    saved, state = first._prefs.read_prior_roster_reference(1405)
    assert state == "stored" and saved is not None
    first.close()

    _raise_from_resolve(monkeypatch, path, f"Symlink loop from {str(path)!r}")
    restored = new_roster_window()
    assert restored._prior_reference_state == "inaccessible"
    assert restored._picker_prior_roster.text() == ""
    assert "inaccessible" in restored._prior_reference_status.text().lower()
    assert restored._prefs.read_prior_roster_reference(1405) == (saved, "stored")
    assert restored._prefs.read_prior_roster_reference(1406)[1] == "absent"
    restored._btn_omit_prior_reference.click()
    assert restored._picker_prior_roster.text() == ""
    assert restored._prior_reference_state == "omitted"
    assert restored._prefs.read_prior_roster_reference(1405)[1] == "stored"
    restored._btn_forget_prior_reference.click()
    assert restored._prior_reference_state == "forgotten"
    assert restored._prefs.read_prior_roster_reference(1405)[1] == "absent"


def test_operator_selection_and_allocate_fail_before_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    new_roster_window: Callable[[], MainWindow],
) -> None:
    path = tmp_path / "prior.csv"
    path.write_bytes(b"synthetic-data")
    window = new_roster_window()
    _raise_from_resolve(monkeypatch, path, f"Symlink loop from {str(path)!r}")
    _commit_prior_path(window, path)
    assert window._prior_reference_state == "unsaved"
    assert window._prefs.read_prior_roster_reference(1405)[1] == "absent"

    for picker, filename in (
        (window._picker_students, "synthetic-students.xlsx"),
        (window._picker_pool, "synthetic-pool.xlsx"),
        (window._picker_sabt_profile_alloc, "synthetic-profile.xlsx"),
    ):
        file = tmp_path / filename
        file.touch()
        picker.setText(str(file))
    window._optional_roster.setChecked(True)
    window._academic_year_confirm.click()
    monkeypatch.setattr(
        base, "compute_reference_readiness", lambda **_: SimpleNamespace(is_ready_for_run=True)
    )
    warnings: list[str] = []
    preflights: list[object] = []
    launches: list[object] = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda _parent, _title, detail: warnings.append(detail)
    )
    monkeypatch.setattr(
        window,
        "_run_unknowns_preflight",
        lambda *_args, **_kwargs: preflights.append(True),
    )
    monkeypatch.setattr(
        window, "_launch_cli", lambda *_args, **_kwargs: launches.append(True)
    )

    window._start_allocate()
    assert warnings and "cannot be read" in warnings[-1]
    assert not preflights and not launches
    assert window._worker is None
    assert window._prefs.read_prior_roster_reference(1405)[1] == "absent"

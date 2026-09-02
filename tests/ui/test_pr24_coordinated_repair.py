from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from PySide6.QtWidgets import QMessageBox

import app.ui.main_window_base as base_module
from app.infra.groupcode.groupcode_repository import GroupCodeRepository
from app.infra.local_database import LocalDatabase
from app.infra.schools.school_repository import SchoolRepository
from app.ui.main_window import MainWindow


def _set_output_state(window: MainWindow, tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "automatic-output"
    sentinel = tmp_path / "prior-successful-run"
    window._prefs.output_root_dir = str(root)
    window._prefs.last_output_dir = str(sentinel)
    return root, sentinel


def _install_repositories(window: MainWindow, tmp_path: Path, *, ready: bool) -> None:
    db = LocalDatabase(tmp_path / ("ready.sqlite" if ready else "not-ready.sqlite"))
    window._local_db = db
    window._school_repository = SchoolRepository(db)
    window._groupcode_repository = GroupCodeRepository(db)
    if not ready:
        return

    schools = pd.DataFrame(
        {
            "کد مدرسه": [1],
            "نام مدرسه": ["A"],
            "مرکز گلستان صدرا": [10],
            "جنسیت": [1],
            "فعال": [1],
        }
    )
    schools_path = tmp_path / "schools.xlsx"
    schools.to_excel(schools_path, index=False)
    window._school_repository.import_from_excel(schools_path)


def _mute_warnings(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda _parent, title, text: warnings.append((title, text))),
    )
    return warnings


def _output_arg(argv: list[str]) -> str:
    return argv[argv.index("--output") + 1]


def _run_dirs(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.iterdir() if path.is_dir())


def test_build_rejection_does_not_commit_automatic_workspace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, qapp
) -> None:
    window = MainWindow()
    root, sentinel = _set_output_state(window, tmp_path)
    warnings = _mute_warnings(monkeypatch)
    launches: list[object] = []
    monkeypatch.setattr(window, "_launch_cli", lambda *args, **kwargs: launches.append(args))

    window._picker_inspactor.setText("")
    window._start_build()

    assert warnings
    assert _run_dirs(root) == []
    assert window._prefs.last_output_dir == str(sentinel)
    assert not launches
    window.close()
    qapp.processEvents()


@pytest.mark.parametrize(
    "reject_kind",
    ["reference_not_ready", "missing_required", "missing_year", "invalid_roster"],
)
def test_allocate_rejections_do_not_commit_automatic_workspace(
    reject_kind: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    qapp,
) -> None:
    window = MainWindow()
    root, sentinel = _set_output_state(window, tmp_path)
    _install_repositories(window, tmp_path, ready=reject_kind != "reference_not_ready")
    _mute_warnings(monkeypatch)

    preflights: list[object] = []
    launches: list[object] = []
    monkeypatch.setattr(
        window,
        "_run_unknowns_preflight",
        lambda *args, **kwargs: preflights.append((args, kwargs)),
    )
    monkeypatch.setattr(window, "_launch_cli", lambda *args, **kwargs: launches.append(args))

    window._picker_students.setText(str(tmp_path / "students.xlsx"))
    window._picker_pool.setText(str(tmp_path / "pool.xlsx"))
    window._combo_academic_year.setEditText("1404")
    if reject_kind == "missing_required":
        window._picker_students.setText("")
    elif reject_kind == "missing_year":
        window._combo_academic_year.setEditText("")
    elif reject_kind == "invalid_roster":
        window._picker_prior_roster.setText(str(tmp_path / "missing-prior.xlsx"))

    window._start_allocate()

    assert _run_dirs(root) == []
    assert window._prefs.last_output_dir == str(sentinel)
    assert not preflights
    assert not launches
    window.close()
    qapp.processEvents()


@pytest.mark.parametrize("reject_kind", ["missing_required", "missing_year", "invalid_roster"])
def test_rule_engine_rejections_do_not_commit_automatic_workspace(
    reject_kind: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    qapp,
) -> None:
    window = MainWindow()
    root, sentinel = _set_output_state(window, tmp_path)
    _mute_warnings(monkeypatch)
    launches: list[object] = []
    monkeypatch.setattr(window, "_launch_cli", lambda *args, **kwargs: launches.append(args))

    window._picker_rule_matrix.setText(str(tmp_path / "matrix.xlsx"))
    window._picker_rule_students.setText(str(tmp_path / "students.xlsx"))
    window._combo_rule_academic_year.setEditText("1404")
    if reject_kind == "missing_required":
        window._picker_rule_matrix.setText("")
    elif reject_kind == "missing_year":
        window._combo_rule_academic_year.setEditText("")
    elif reject_kind == "invalid_roster":
        window._picker_rule_current_roster.setText(str(tmp_path / "missing-current.xlsx"))

    window._start_rule_engine()

    assert _run_dirs(root) == []
    assert window._prefs.last_output_dir == str(sentinel)
    assert not launches
    window.close()
    qapp.processEvents()


def test_valid_automatic_build_commits_once_at_launch_boundary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, qapp
) -> None:
    window = MainWindow()
    root, _sentinel = _set_output_state(window, tmp_path)
    window._picker_inspactor.setText(str(tmp_path / "inspactor.xlsx"))
    launches: list[tuple[list[str], dict[str, Any]]] = []

    def _capture_launch(argv: list[str], _action: str, **kwargs: Any) -> None:
        launches.append((list(argv), kwargs))

    monkeypatch.setattr(window, "_launch_cli", _capture_launch)
    window._start_build()

    run_dirs = _run_dirs(root)
    assert len(run_dirs) == 1
    assert len(launches) == 1
    output = Path(_output_arg(launches[0][0]))
    assert output.parent == run_dirs[0]
    assert output.name.startswith("matrix_")
    assert output.suffix == ".xlsx"
    assert window._prefs.last_output_dir == str(run_dirs[0])
    window.close()
    qapp.processEvents()


def test_valid_allocate_commits_before_preflight_and_reuses_same_workspace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, qapp
) -> None:
    window = MainWindow()
    root, _sentinel = _set_output_state(window, tmp_path)
    _install_repositories(window, tmp_path, ready=True)
    window._picker_students.setText(str(tmp_path / "students.xlsx"))
    window._picker_pool.setText(str(tmp_path / "pool.xlsx"))
    window._combo_academic_year.setEditText("1404")
    window._picker_sabt_output_alloc.setText(str(tmp_path / "requested-sabt.xlsx"))

    preflight: dict[str, Any] = {}
    launches: list[tuple[list[str], dict[str, Any]]] = []

    def _capture_preflight(
        argv: list[str],
        *,
        overrides: dict[str, object],
        report_path: Path,
        on_proceed,
    ) -> None:
        preflight["argv"] = list(argv)
        preflight["overrides"] = dict(overrides)
        preflight["report_path"] = report_path
        on_proceed()

    def _capture_launch(argv: list[str], _action: str, **kwargs: Any) -> None:
        launches.append((list(argv), kwargs))

    monkeypatch.setattr(window, "_run_unknowns_preflight", _capture_preflight)
    monkeypatch.setattr(window, "_launch_cli", _capture_launch)
    window._start_allocate()

    run_dirs = _run_dirs(root)
    assert len(run_dirs) == 1
    assert len(launches) == 1
    preflight_output = Path(_output_arg(preflight["argv"]))
    launch_output = Path(_output_arg(launches[0][0]))
    assert preflight_output == launch_output
    assert launch_output.parent == run_dirs[0]
    assert launch_output.name.startswith("allocation_")
    report_path = Path(preflight["report_path"])
    assert report_path == run_dirs[0] / "reports" / "unknown_data_report.json"
    sabt_output = Path(str(preflight["overrides"]["sabt_output"]))
    assert sabt_output.parent == run_dirs[0]
    assert sabt_output.name.startswith("sabt_")
    assert window._prefs.last_output_dir == str(run_dirs[0])
    window.close()
    qapp.processEvents()


def test_valid_rule_engine_commits_one_workspace_and_run_local_sabt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, qapp
) -> None:
    window = MainWindow()
    root, _sentinel = _set_output_state(window, tmp_path)
    window._picker_rule_matrix.setText(str(tmp_path / "matrix.xlsx"))
    window._picker_rule_students.setText(str(tmp_path / "students.xlsx"))
    window._combo_rule_academic_year.setEditText("1404")
    window._picker_sabt_output_rule.setText(str(tmp_path / "requested-rule-sabt.xlsx"))
    launches: list[tuple[list[str], dict[str, Any]]] = []

    def _capture_launch(argv: list[str], _action: str, **kwargs: Any) -> None:
        launches.append((list(argv), kwargs))

    monkeypatch.setattr(window, "_launch_cli", _capture_launch)
    window._start_rule_engine()

    run_dirs = _run_dirs(root)
    assert len(run_dirs) == 1
    assert len(launches) == 1
    output = Path(_output_arg(launches[0][0]))
    assert output.parent == run_dirs[0]
    assert output.name.startswith("rule_engine_")
    overrides = launches[0][1]["overrides"]
    sabt_output = Path(str(overrides["sabt_output"]))
    assert sabt_output.parent == run_dirs[0]
    assert sabt_output.name.startswith("sabt_")
    assert window._prefs.last_output_dir == str(run_dirs[0])
    window.close()
    qapp.processEvents()


def test_explicit_build_path_bypasses_automatic_workspace_without_pointer_mutation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, qapp
) -> None:
    window = MainWindow()
    root, sentinel = _set_output_state(window, tmp_path)
    explicit = tmp_path / "explicit-matrix.xlsx"
    window._picker_inspactor.setText(str(tmp_path / "inspactor.xlsx"))
    window._picker_output_matrix.setText(str(explicit))
    launches: list[list[str]] = []

    monkeypatch.setattr(
        window,
        "_launch_cli",
        lambda argv, _action, **_kwargs: launches.append(list(argv)),
    )
    window._start_build()

    assert len(launches) == 1
    assert _output_arg(launches[0]) == str(explicit)
    assert window._picker_output_matrix.text() == str(explicit)
    assert window._picker_output_matrix.isHidden()
    assert _run_dirs(root) == []
    assert window._prefs.last_output_dir == str(sentinel)
    window.close()
    qapp.processEvents()


def test_polished_layer_uses_base_validation_hook_instead_of_start_flow_copies() -> None:
    polished_source = Path("app/ui/main_window.py").read_text(encoding="utf-8")
    base_source = Path("app/ui/main_window_base.py").read_text(encoding="utf-8")

    assert "def _prepare_validated_output(" in polished_source
    assert "def _prepare_validated_output(" in base_source
    assert "def _start_build(" not in polished_source
    assert "def _start_allocate(" not in polished_source
    assert "def _start_rule_engine(" not in polished_source
    assert base_module.MainWindow._start_build is not None

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QDate, QDateTime, QSettings, QTime

from app.ui.app_preferences import AppPreferences
from app.ui.run_output import (
    create_run_workspace,
    default_output_root,
    jalali_date_string,
    run_stamp,
)


def _isolated_preferences(path: Path) -> AppPreferences:
    prefs = object.__new__(AppPreferences)
    prefs._settings = QSettings(str(path), QSettings.Format.IniFormat)
    prefs._valid_centers = {0, 1, 2}
    return prefs


def test_default_output_root_is_user_documents_workspace(qapp) -> None:
    root = default_output_root()
    assert root.name == "Output"
    assert root.parent.name == "MentorAllocation"
    assert root != Path.cwd()


def test_custom_output_root_persists_without_overloading_last_output(tmp_path: Path) -> None:
    settings_file = tmp_path / "prefs.ini"
    prefs = _isolated_preferences(settings_file)
    custom_root = tmp_path / "custom-output"
    run_folder = tmp_path / "custom-output" / "existing-run"

    prefs.output_root_dir = str(custom_root)
    prefs.last_output_dir = str(run_folder)

    reloaded = _isolated_preferences(settings_file)
    assert reloaded.output_root_dir == str(custom_root)
    assert reloaded.last_output_dir == str(run_folder)


def test_jalali_date_and_stamp_use_ascii_windows_safe_format(qapp) -> None:
    moment = QDateTime(QDate(2026, 9, 2), QTime(14, 53, 27))
    assert jalali_date_string(moment) == "1405-06-11"
    assert run_stamp(moment) == "1405-06-11_145327"
    assert all(char not in run_stamp(moment) for char in ":/\\")


def test_build_and_allocate_primary_names(tmp_path: Path, qapp) -> None:
    moment = QDateTime(QDate(2026, 9, 2), QTime(14, 53, 27))
    build = create_run_workspace(tmp_path, "build", moment=moment)
    allocate = create_run_workspace(tmp_path, "allocate", moment=moment)

    assert build.run_dir.name == "1405-06-11_145327_build"
    assert allocate.run_dir.name == "1405-06-11_145327_allocate"
    assert build.primary_output_path.name == "matrix_1405-06-11_145327.xlsx"
    assert allocate.primary_output_path.name == "allocation_1405-06-11_145327.xlsx"


def test_rule_engine_gui_workspace_is_retired(tmp_path: Path, qapp) -> None:
    moment = QDateTime(QDate(2026, 9, 2), QTime(14, 53, 27))
    with pytest.raises(ValueError, match="unsupported run type: rule-engine"):
        create_run_workspace(tmp_path, "rule-engine", moment=moment)


def test_same_second_collision_never_overwrites_existing_run(tmp_path: Path, qapp) -> None:
    moment = QDateTime(QDate(2026, 9, 2), QTime(14, 53, 27))
    first = create_run_workspace(tmp_path, "build", moment=moment)
    second = create_run_workspace(tmp_path, "build", moment=moment)
    third = create_run_workspace(tmp_path, "build", moment=moment)

    assert first.run_dir.name == "1405-06-11_145327_build"
    assert second.run_dir.name == "1405-06-11_145327_build_02"
    assert third.run_dir.name == "1405-06-11_145327_build_03"
    assert len({first.run_dir, second.run_dir, third.run_dir}) == 3
    assert all(workspace.run_dir.is_dir() for workspace in (first, second, third))


def test_optional_artifact_is_kept_inside_same_run_workspace(tmp_path: Path, qapp) -> None:
    moment = QDateTime(QDate(2026, 9, 2), QTime(14, 53, 27))
    workspace = create_run_workspace(tmp_path, "allocate", moment=moment)
    sabt = workspace.artifact_path("sabt")

    assert sabt.parent == workspace.run_dir
    assert sabt.name == "sabt_1405-06-11_145327.xlsx"
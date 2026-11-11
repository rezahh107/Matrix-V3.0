"""SQLite reference-status regression: real files, rows, provenance and year reopening."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd
import pytest

from app.core.common.domain import EDUCATIONAL_STRUCTURE
from app.infra.db.reference_readiness import compute_reference_readiness
from app.infra.errors import DatabaseCorruptError, DatabasePreparationError
from app.infra.groupcode.groupcode_repository import GroupCodeRepository
from app.infra.local_database import LocalDatabase
from app.infra.schools.school_repository import SchoolRepository
from app.infra.year_database_manager import YearDatabaseManager


def _logical_snapshot(path: Path) -> tuple[object, ...]:
    """Compare SQLite logical schema and all rows; ignore WAL/file-byte churn."""
    uri = path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        schema = tuple(
            conn.execute(
                "SELECT name, sql FROM sqlite_master "
                "WHERE type IN ('table', 'view', 'index', 'trigger') "
                "ORDER BY name, type"
            ).fetchall()
        )
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        rows = tuple(
            (
                name,
                tuple(sorted(repr(row) for row in conn.execute(
                    'SELECT * FROM "' + name.replace('"', '""') + '"'
                ).fetchall())),
            )
            for (name,) in tables
        )
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    return (schema, rows, version)


def _reference_snapshot(path: Path) -> tuple[object, ...]:
    """Compare authoritative reference rows and metadata across ordinary reopen.

    Reopen may legitimately restore a schema index after an import-table swap;
    the reference data and provenance must still remain unchanged.
    """
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        return tuple(
            (
                name,
                tuple(sorted(repr(row) for row in conn.execute(
                    'SELECT * FROM "' + name + '"'
                ).fetchall())),
            )
            for name in ("schools", "groupcodes", "reference_meta")
        )


def _import_schools(repo: SchoolRepository, path: Path) -> None:
    pd.DataFrame(
        {
            "کد مدرسه": [1],
            "نام مدرسه": ["Synthetic School"],
            "مرکز گلستان صدرا": [0],
            "جنسیت": [1],
        }
    ).to_excel(path, index=False)
    repo.import_from_excel(path)


def _import_groupcodes(repo: GroupCodeRepository, path: Path) -> None:
    pd.DataFrame(
        {
            "group_code": [24],
            "level": ["متوسطه دوم"],
            "grade": [10],
            "track": ["ریاضی"],
            "is_active": [1],
        }
    ).to_excel(path, index=False)
    repo.import_from_excel(path)


def test_c1_missing_path_is_observed_without_creating_database(tmp_path: Path) -> None:
    path = tmp_path / "never-created.sqlite"
    db = LocalDatabase(path)
    schools = SchoolRepository(db)
    groups = GroupCodeRepository(db)

    for _ in range(2):
        ready = compute_reference_readiness(school_repo=schools, groupcode_repo=groups)
        assert ready.schools.row_count == 0
        assert ready.groupcodes.row_count == 0
        assert not ready.is_ready_for_run
        assert groups.status().version_tag is None
        assert not path.exists()
        assert not Path(str(path) + "-wal").exists()


def test_existing_blank_sqlite_file_is_not_mistaken_for_new_bootstrap(
    tmp_path: Path,
) -> None:
    path = tmp_path / "preexisting-blank.sqlite"
    with closing(sqlite3.connect(path)):
        pass
    assert path.exists()

    with LocalDatabase(path) as db:
        db.initialize()
        status = GroupCodeRepository(db).status()
        assert status.row_count == 0
        assert status.version_tag is None
        with closing(db.connect_readonly()) as conn:
            assert conn.execute(
                "SELECT COUNT(*) FROM reference_meta WHERE table_name='groupcodes'"
            ).fetchone()[0] == 0


def test_c2_repeated_readiness_has_no_logical_mutation(tmp_path: Path) -> None:
    path = tmp_path / "healthy.sqlite"
    with LocalDatabase(path) as db:
        db.initialize()
        schools = SchoolRepository(db)
        groups = GroupCodeRepository(db)
        _import_schools(schools, tmp_path / "schools.xlsx")
        original = _logical_snapshot(path)

        for _ in range(3):
            ready = compute_reference_readiness(school_repo=schools, groupcode_repo=groups)
            assert ready.is_ready_for_run
            assert ready.schools.row_count == 1
            assert ready.groupcodes.row_count == len(EDUCATIONAL_STRUCTURE)
            assert ready.schools.source_filename == "schools.xlsx"
            assert ready.groupcodes.version_tag == "builtin:ssot"
        assert _logical_snapshot(path) == original


def test_c3_deleted_imported_groupcodes_remain_missing_after_status_and_reopen(
    tmp_path: Path,
) -> None:
    manager = YearDatabaseManager(tmp_path / "years")
    db = manager.open_year("1404")
    schools = SchoolRepository(db)
    groups = GroupCodeRepository(db)
    _import_schools(schools, tmp_path / "schools.xlsx")
    _import_groupcodes(groups, tmp_path / "groups.xlsx")
    assert groups.status().source_filename == "groups.xlsx"

    with db.connect() as conn:
        conn.execute("DELETE FROM groupcodes")
        conn.commit()
    before = _logical_snapshot(db.path)
    reference_before = _reference_snapshot(db.path)
    ready = compute_reference_readiness(school_repo=schools, groupcode_repo=groups)
    assert not ready.is_ready_for_run
    assert ready.groupcodes.row_count == 0
    assert ready.groupcodes.version_tag is None
    assert _logical_snapshot(db.path) == before

    db.close_all_connections()
    reopened = manager.open_year("1404")
    assert GroupCodeRepository(reopened).status().row_count == 0
    with pytest.raises(DatabasePreparationError, match="خالی"):
        GroupCodeRepository(reopened).load_crosswalk_groups_frame()
    assert _reference_snapshot(db.path) == reference_before
    reopened.close_all_connections()


def test_missing_metadata_does_not_gain_fabricated_provenance(tmp_path: Path) -> None:
    manager = YearDatabaseManager(tmp_path / "years")
    db = manager.open_year("1404")
    with db.connect() as conn:
        conn.execute("DELETE FROM reference_meta WHERE table_name = 'groupcodes'")
        conn.commit()
    before = _logical_snapshot(db.path)

    status = GroupCodeRepository(db).status()
    assert status.row_count == len(EDUCATIONAL_STRUCTURE)
    assert status.version_tag is None
    assert status.source_filename is None
    assert status.imported_at is None
    db.close_all_connections()

    reopened = manager.open_year("1404")
    assert GroupCodeRepository(reopened).status().version_tag is None
    assert _logical_snapshot(reopened.path) == before
    reopened.close_all_connections()


def test_stale_schools_metadata_cannot_make_readiness_ready(tmp_path: Path) -> None:
    with LocalDatabase(tmp_path / "stale.sqlite") as db:
        db.initialize()
        db.record_reference_meta(
            table_name="schools",
            source="synthetic",
            row_count=200,
            version_tag="stale-version",
        )
        before = _logical_snapshot(db.path)
        ready = compute_reference_readiness(
            school_repo=SchoolRepository(db),
            groupcode_repo=GroupCodeRepository(db),
        )
        assert ready.schools.row_count == 0
        assert ready.schools.version_tag is None
        assert ready.groupcodes_ready
        assert not ready.is_ready_for_run
        assert _logical_snapshot(db.path) == before


def test_partial_groupcodes_are_not_replaced_or_mislabelled(tmp_path: Path) -> None:
    manager = YearDatabaseManager(tmp_path / "years")
    db = manager.open_year("1403")
    with db.connect() as conn:
        conn.execute(
            "DELETE FROM groupcodes WHERE group_code <> "
            "(SELECT group_code FROM groupcodes ORDER BY group_code LIMIT 1)"
        )
        conn.commit()
    before = _logical_snapshot(db.path)
    status = GroupCodeRepository(db).status()
    assert status.row_count == 1
    assert status.version_tag is None  # stale 33-row seed metadata
    db.close_all_connections()

    reopened = manager.open_year("1403")
    assert GroupCodeRepository(reopened).status().row_count == 1
    assert _logical_snapshot(reopened.path) == before
    reopened.close_all_connections()


def test_missing_reference_table_is_not_recreated_by_status(tmp_path: Path) -> None:
    with LocalDatabase(tmp_path / "missing-table.sqlite") as db:
        db.initialize()
        with db.connect() as conn:
            conn.execute("DROP TABLE groupcodes")
            conn.commit()
        before = _logical_snapshot(db.path)
        status = GroupCodeRepository(db).status()
        assert status.row_count == 0
        assert _logical_snapshot(db.path) == before


def test_separate_years_and_first_bootstrap_remain_correct(tmp_path: Path) -> None:
    manager = YearDatabaseManager(tmp_path / "years")
    first = manager.create_year("1404")
    second = manager.create_year("1405")
    assert first.path != second.path
    expected = len(EDUCATIONAL_STRUCTURE)
    assert GroupCodeRepository(first).status().row_count == expected
    assert GroupCodeRepository(second).status().row_count == expected
    with first.connect() as conn:
        conn.execute("DELETE FROM groupcodes")
        conn.commit()
    first_before = _logical_snapshot(first.path)
    second_before = _logical_snapshot(second.path)
    first.close_all_connections()
    second.close_all_connections()

    reopened_first = manager.open_year("1404")
    reopened_second = manager.open_year("1405")
    assert GroupCodeRepository(reopened_first).status().row_count == 0
    assert GroupCodeRepository(reopened_second).status().row_count == expected
    assert _logical_snapshot(reopened_first.path) == first_before
    assert _logical_snapshot(reopened_second.path) == second_before
    reopened_first.close_all_connections()
    reopened_second.close_all_connections()


def test_valid_and_invalid_groupcode_import_preserve_authority(tmp_path: Path) -> None:
    with LocalDatabase(tmp_path / "imports.sqlite") as db:
        db.initialize()
        repo = GroupCodeRepository(db)
        _import_groupcodes(repo, tmp_path / "valid.xlsx")
        status = repo.status()
        assert status.row_count == 1
        assert status.source_filename == "valid.xlsx"
        before = _logical_snapshot(db.path)
        pd.DataFrame(
            {"group_code": [], "level": [], "grade": [], "track": []}
        ).to_excel(tmp_path / "invalid.xlsx", index=False)
        with pytest.raises(DatabasePreparationError):
            repo.import_from_excel(tmp_path / "invalid.xlsx")
        assert _logical_snapshot(db.path) == before


def test_corruption_recovery_still_preserves_backup_and_error(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.sqlite"
    db = LocalDatabase(path)
    db.initialize()
    db.close_all_connections()
    damaged_bytes = b"definitely not a SQLite database"
    path.write_bytes(damaged_bytes)

    restored = LocalDatabase(path)
    with pytest.raises(DatabaseCorruptError):
        restored.initialize()
    backup = path.with_suffix(path.suffix + ".corrupt")
    assert backup.exists()
    assert backup.read_bytes() == damaged_bytes
    assert GroupCodeRepository(restored).status().row_count == len(EDUCATIONAL_STRUCTURE)
    restored.close_all_connections()


def test_snapshot_negative_control_detects_real_sqlite_content_change(tmp_path: Path) -> None:
    with LocalDatabase(tmp_path / "control.sqlite") as db:
        db.initialize()
        before = _logical_snapshot(db.path)
        with db.connect() as conn:
            conn.execute("DELETE FROM groupcodes WHERE group_code = (SELECT MIN(group_code) FROM groupcodes)")
            conn.commit()
        assert _logical_snapshot(db.path) != before

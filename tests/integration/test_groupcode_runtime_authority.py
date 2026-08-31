from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pandas as pd
import pytest

from app.core.policy_loader import load_policy
from app.infra import cli, cli_legacy
from app.infra.groupcode.groupcode_repository import GroupCodeRepository
from app.infra.local_database import LocalDatabase
from app.infra.schools.school_repository import SchoolRepository
from app.infra.year_database_manager import YearDatabaseManager

POLICY_PATH = Path("config/policy.json")


def _write_excel(frame: pd.DataFrame, path: Path) -> Path:
    frame.to_excel(path, index=False)
    return path


def _groupcodes(code: int) -> pd.DataFrame:
    rows = {
        24: ("متوسطه دوم", 10, "ریاضی"),
        25: ("متوسطه دوم", 10, "تجربی"),
    }
    level, grade, track = rows[code]
    return pd.DataFrame(
        {
            "group_code": [code],
            "level": [level],
            "grade": [grade],
            "track": [track],
            "is_active": [1],
        }
    )


def _invalid_groupcodes() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "group_code": [999],
            "level": ["متوسطه دوم"],
            "grade": [10],
            "track": ["ریاضی"],
            "is_active": [1],
        }
    )


def _schools() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "کد مدرسه": [101],
            "نام مدرسه": ["Synthetic School"],
            "مرکز گلستان صدرا": [0],
            "جنسیت": [1],
            "فعال": [1],
        }
    )


def _student(group_code: int = 24) -> pd.DataFrame:
    group_name = "دهم ریاضی" if group_code == 24 else "دهم تجربی"
    return pd.DataFrame(
        {
            "student_id": ["synthetic-student-1"],
            "کد ملی": ["0000000001"],
            "کدرشته": [group_code],
            "گروه آزمایشی": [group_name],
            "جنسیت": [1],
            "دانش آموز فارغ": [1],
            "مرکز گلستان صدرا": [0],
            "مالی حکمت بنیاد": [0],
            "کد مدرسه": [0],
        }
    )


def _inspactor(group_code: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "نام پشتیبان": ["Synthetic Mentor"],
            "نام مدیر": ["Synthetic Manager"],
            "کد کارمندی پشتیبان": ["9001"],
            "کدپستی": ["5000"],
            "تعداد مدارس تحت پوشش": [0],
            "تعداد داوطلبان تحت پوشش": [0],
            "تعداد تحت پوشش خاص": [5],
            "شامل گروه های آزمایشی": [str(group_code)],
            "گروه آزمایشی": [group_code],
            "کدرشته": [group_code],
            "جنسیت": [1],
            "دانش آموز فارغ": [1],
            "مرکز گلستان صدرا": [0],
            "مالی حکمت بنیاد": [0],
            "کد مدرسه": [0],
            "نام مدرسه 1": [0],
            "نام مدرسه 2": [0],
            "نام مدرسه 3": [0],
            "نام مدرسه 4": [0],
        }
    )


def _prepare_reference_db(tmp_path: Path, group_code: int = 24) -> tuple[Path, Path, Path]:
    db_path = tmp_path / "annual.sqlite"
    school_path = _write_excel(_schools(), tmp_path / "schools.xlsx")
    group_path = _write_excel(
        _groupcodes(group_code), tmp_path / f"groupcodes-{group_code}.xlsx"
    )
    db = LocalDatabase(db_path)
    SchoolRepository(db).import_from_excel(school_path)
    GroupCodeRepository(db).import_from_excel(group_path)
    return db_path, school_path, group_path


def _matrix_group_values(matrix_path: Path) -> set[int]:
    matrix = pd.read_excel(matrix_path, sheet_name="matrix")
    group_column = next(
        column for column in matrix.columns if str(column).split("|", 1)[0].strip() == "کدرشته"
    )
    return set(pd.to_numeric(matrix[group_column], errors="coerce").dropna().astype(int))


def _build_matrix(
    *, tmp_path: Path, db_path: Path, school_path: Path, group_code: int
) -> Path:
    inspactor_path = _write_excel(
        _inspactor(group_code), tmp_path / f"inspactor-{group_code}.xlsx"
    )
    matrix_path = tmp_path / f"matrix-{group_code}.xlsx"
    rc = cli_legacy.main(
        [
            "build-matrix",
            "--inspactor",
            str(inspactor_path),
            "--schools",
            str(school_path),
            "--output",
            str(matrix_path),
            "--policy",
            str(POLICY_PATH),
            "--local-db",
            str(db_path),
            "--min-coverage",
            "0",
            "--use-v3-mentor-pipeline",
        ]
    )
    assert rc == 0
    assert matrix_path.exists()
    return matrix_path


def test_p0_01_explicit_groupcode_import_reaches_real_build(tmp_path: Path) -> None:
    db_path, school_path, _ = _prepare_reference_db(tmp_path, group_code=24)
    group_b = _write_excel(_groupcodes(25), tmp_path / "groupcodes-B.xlsx")

    rc = cli_legacy.main(
        [
            "import-groupcodes",
            "--crosswalk",
            str(group_b),
            "--local-db",
            str(db_path),
        ]
    )
    assert rc == 0

    repo = GroupCodeRepository(LocalDatabase(db_path))
    stored = repo.load_canonical_frame()
    assert set(stored["group_code"].astype(int)) == {25}
    status = repo.status()
    assert status.row_count == 1
    assert status.source_filename == group_b.name
    assert status.version_tag == group_b.stem
    assert status.imported_at is not None

    matrix_path = _build_matrix(
        tmp_path=tmp_path,
        db_path=db_path,
        school_path=school_path,
        group_code=25,
    )
    values = _matrix_group_values(matrix_path)
    assert 25 in values
    assert 24 not in values


def test_p0_02_real_student_ingress_tracks_current_db_groupcodes(tmp_path: Path) -> None:
    db_path, _, _ = _prepare_reference_db(tmp_path, group_code=24)
    students_path = _write_excel(_student(24), tmp_path / "students.xlsx")
    policy = load_policy(POLICY_PATH)
    db = LocalDatabase(db_path)

    current, _, _ = cli_legacy._resolve_students_frame(
        Namespace(students=str(students_path)), policy, db=db
    )
    assert int(current.loc[0, "کدرشته"]) == 24

    GroupCodeRepository(db).import_from_excel(
        _write_excel(_groupcodes(25), tmp_path / "groupcodes-B.xlsx")
    )
    with pytest.raises(ValueError, match="Unknown group code"):
        cli_legacy._resolve_students_frame(
            Namespace(students=str(students_path)), policy, db=db
        )


def test_p0_03_groupcode_change_blocks_now_ineligible_real_allocation(tmp_path: Path) -> None:
    db_path, school_path, _ = _prepare_reference_db(tmp_path, group_code=24)
    matrix_path = _build_matrix(
        tmp_path=tmp_path,
        db_path=db_path,
        school_path=school_path,
        group_code=24,
    )
    students_path = _write_excel(_student(24), tmp_path / "students.xlsx")
    output_a = tmp_path / "allocation-A.xlsx"

    rc = cli_legacy.main(
        [
            "allocate",
            "--students",
            str(students_path),
            "--pool",
            str(matrix_path),
            "--pool-type",
            "matrix",
            "--pool-sheet",
            "matrix",
            "--policy",
            str(POLICY_PATH),
            "--academic-year",
            "1404",
            "--counter-duplicate-strategy",
            "assign-new",
            "--output",
            str(output_a),
            "--local-db",
            str(db_path),
        ]
    )
    assert rc == 0
    assert output_a.exists()

    GroupCodeRepository(LocalDatabase(db_path)).import_from_excel(
        _write_excel(_groupcodes(25), tmp_path / "groupcodes-B.xlsx")
    )
    with pytest.raises(ValueError, match="Unknown group code"):
        cli_legacy.main(
            [
                "allocate",
                "--students",
                str(students_path),
                "--pool",
                str(matrix_path),
                "--pool-type",
                "matrix",
                "--pool-sheet",
                "matrix",
                "--policy",
                str(POLICY_PATH),
                "--academic-year",
                "1404",
                "--counter-duplicate-strategy",
                "assign-new",
                "--output",
                str(tmp_path / "allocation-B.xlsx"),
                "--local-db",
                str(db_path),
            ]
        )


def test_p0_04_deprecated_build_crosswalk_fails_without_mutating_db(tmp_path: Path) -> None:
    db_path, _, group_a = _prepare_reference_db(tmp_path, group_code=24)
    group_b = _write_excel(_groupcodes(25), tmp_path / "groupcodes-B.xlsx")
    output = tmp_path / "must-not-build.xlsx"

    rc = cli_legacy.main(
        [
            "build-matrix",
            "--crosswalk",
            str(group_b),
            "--output",
            str(output),
            "--local-db",
            str(db_path),
        ]
    )
    assert rc == 2
    assert not output.exists()

    repo = GroupCodeRepository(LocalDatabase(db_path))
    stored = repo.load_canonical_frame()
    assert set(stored["group_code"].astype(int)) == {24}
    meta = repo.status()
    assert meta.source_filename == group_a.name


def test_p0_05_stale_student_cache_is_revalidated_against_current_db(tmp_path: Path) -> None:
    db_path, _, _ = _prepare_reference_db(tmp_path, group_code=24)
    students_path = _write_excel(_student(24), tmp_path / "students.xlsx")
    policy = load_policy(POLICY_PATH)
    db = LocalDatabase(db_path)

    cached, _, _ = cli_legacy._resolve_students_frame(
        Namespace(students=str(students_path)), policy, db=db
    )
    assert int(cached.loc[0, "کدرشته"]) == 24

    GroupCodeRepository(db).import_from_excel(
        _write_excel(_groupcodes(25), tmp_path / "groupcodes-B.xlsx")
    )
    with pytest.raises(ValueError, match="Unknown group code"):
        cli_legacy._resolve_students_frame(Namespace(students=None), policy, db=db)


def test_p0_06_gui_backend_and_direct_cli_share_groupcode_db(tmp_path: Path) -> None:
    db_path, school_path, _ = _prepare_reference_db(tmp_path, group_code=25)
    inspactor_path = _write_excel(_inspactor(25), tmp_path / "inspactor-parity.xlsx")
    gui_output = tmp_path / "matrix-gui-backend.xlsx"
    cli_output = tmp_path / "matrix-direct-cli.xlsx"

    common_args = [
        "build-matrix",
        "--inspactor",
        str(inspactor_path),
        "--schools",
        str(school_path),
        "--policy",
        str(POLICY_PATH),
        "--min-coverage",
        "0",
        "--use-v3-mentor-pipeline",
    ]
    gui_rc = cli.main(
        [*common_args, "--output", str(gui_output)],
        ui_overrides={"local_db_path": str(db_path)},
    )
    direct_rc = cli_legacy.main(
        [
            *common_args,
            "--output",
            str(cli_output),
            "--local-db",
            str(db_path),
        ]
    )

    assert gui_rc == 0
    assert direct_rc == 0
    assert _matrix_group_values(gui_output) == {25}
    assert _matrix_group_values(cli_output) == {25}


def test_allocate_cannot_disable_authoritative_reference_db(tmp_path: Path) -> None:
    students_path = _write_excel(_student(24), tmp_path / "students.xlsx")
    rc = cli_legacy.main(
        [
            "allocate",
            "--students",
            str(students_path),
            "--pool",
            str(tmp_path / "unused-matrix.xlsx"),
            "--output",
            str(tmp_path / "unused-output.xlsx"),
            "--disable-local-db",
        ]
    )
    assert rc == 2


def test_failed_empty_groupcode_import_preserves_previous_reference(tmp_path: Path) -> None:
    db_path, _, group_a = _prepare_reference_db(tmp_path, group_code=24)
    empty = _write_excel(
        pd.DataFrame(columns=["group_code", "level", "grade", "track"]),
        tmp_path / "empty-groupcodes.xlsx",
    )

    rc = cli_legacy.main(
        [
            "import-groupcodes",
            "--crosswalk",
            str(empty),
            "--local-db",
            str(db_path),
        ]
    )
    assert rc == 2

    repo = GroupCodeRepository(LocalDatabase(db_path))
    stored = repo.load_canonical_frame()
    assert set(stored["group_code"].astype(int)) == {24}
    assert repo.status().source_filename == group_a.name


def test_failed_invalid_groupcode_import_preserves_previous_reference(tmp_path: Path) -> None:
    db_path, _, group_a = _prepare_reference_db(tmp_path, group_code=24)
    invalid = _write_excel(_invalid_groupcodes(), tmp_path / "invalid-groupcodes.xlsx")

    rc = cli_legacy.main(
        [
            "import-groupcodes",
            "--crosswalk",
            str(invalid),
            "--local-db",
            str(db_path),
        ]
    )
    assert rc == 2

    repo = GroupCodeRepository(LocalDatabase(db_path))
    stored = repo.load_canonical_frame()
    assert set(stored["group_code"].astype(int)) == {24}
    assert repo.status().source_filename == group_a.name


def test_groupcode_authority_persists_across_annual_db_reopen(tmp_path: Path) -> None:
    manager = YearDatabaseManager(tmp_path / "annual-dbs")
    db = manager.open_year("1404")
    group_path = _write_excel(_groupcodes(24), tmp_path / "year-groupcodes.xlsx")
    GroupCodeRepository(db).import_from_excel(group_path)
    db.close_all_connections()

    reopened = manager.open_year("1404")
    repo = GroupCodeRepository(reopened)
    stored = repo.load_canonical_frame()
    status = repo.status()

    assert set(stored["group_code"].astype(int)) == {24}
    assert status.source_filename == group_path.name
    assert status.imported_at is not None

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pandas as pd

from app.core.policy_loader import load_policy
from app.infra import cli
from app.infra.groupcode.groupcode_repository import GroupCodeRepository
from app.infra.local_database import LocalDatabase
from app.infra.reference_mentors_repository import (
    import_mentor_pool_from_excel,
    load_mentor_pool_from_cache,
)
from app.infra.reference_schools_repository import (
    import_school_crosswalk_from_excel,
    import_school_report_from_excel,
)
from app.infra.reference_students_repository import import_student_report_from_excel
from app.infra.schools.school_repository import SchoolRepository


def _write_excel(df: pd.DataFrame, path: Path) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)


def _seed_student_references(db: LocalDatabase, tmp_path: Path) -> None:
    schools_path = tmp_path / "student-schools.xlsx"
    _write_excel(
        pd.DataFrame(
            {
                "کد مدرسه": [3581],
                "نام مدرسه": ["Synthetic School"],
                "مرکز گلستان صدرا": [1],
                "جنسیت": [1],
            }
        ),
        schools_path,
    )
    SchoolRepository(db).import_from_excel(schools_path)

    groups_path = tmp_path / "student-groupcodes.xlsx"
    _write_excel(
        pd.DataFrame(
            {
                "group_code": [1],
                "level": ["کنکوری"],
                "grade": [12],
                "track": ["ریاضی"],
            }
        ),
        groups_path,
    )
    GroupCodeRepository(db).import_from_excel(groups_path)


def _sample_students() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "student_id": ["S1"],
            "کدرشته": [1],
            "گروه آزمایشی": ["تجربی"],
            "جنسیت": [1],
            "دانش آموز فارغ": [0],
            "مرکز گلستان صدرا": [1],
            "مالی حکمت بنیاد": [0],
            "کد مدرسه": [3581],
            "کد ملی": ["001"],
        }
    )


def _sample_pool() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "پشتیبان": ["الف", "الف"],
            "کد کارمندی پشتیبان": ["M1", "M1"],
            "کدرشته": [1, 3],
            "گروه آزمایشی": ["تجربی", "ریاضی"],
            "جنسیت": [1, 1],
            "دانش آموز فارغ": [0, 0],
            "مرکز گلستان صدرا": [1, 2],
            "مالی حکمت بنیاد": [0, 0],
            "کد مدرسه": [3581, 3582],
            "remaining_capacity": [2, 1],
            "نام پشتیبان": ["الف", "الف"],
            "نام مدیر": ["مدیر", "مدیر"],
            "تعداد داوطلبان تحت پوشش": [1, 1],
            "تعداد مدارس تحت پوشش": [1, 1],
            "کدپستی": ["1", "1"],
            "تعداد تحت پوشش خاص": [0, 0],
        }
    )


def test_allocate_uses_cached_students_and_pool(tmp_path: Path, monkeypatch) -> None:
    policy = load_policy()
    db = LocalDatabase(tmp_path / "cache.sqlite")
    _seed_student_references(db, tmp_path)

    students_path = tmp_path / "students.xlsx"
    pool_path = tmp_path / "pool.xlsx"
    _write_excel(_sample_students(), students_path)
    _write_excel(_sample_pool(), pool_path)

    import_student_report_from_excel(students_path, db=db, policy=policy)
    import_mentor_pool_from_excel(pool_path, db=db, policy=policy)

    captured: dict[str, pd.DataFrame] = {}

    def fake_prepare(students_df, pool_df, **_kwargs):  # type: ignore[no-untyped-def]
        captured["students"] = students_df.copy()
        captured["pool"] = pool_df.copy()
        return students_df, pool_df

    monkeypatch.setattr(cli, "_prepare_allocation_frames", fake_prepare)
    monkeypatch.setattr(cli.cli_legacy, "_prepare_allocation_frames", fake_prepare)
    monkeypatch.setattr(cli, "_allocate_and_write", lambda *_, **__: 0)
    monkeypatch.setattr(cli.cli_legacy, "_allocate_and_write", lambda *_, **__: 0)
    monkeypatch.setattr(cli, "_apply_mentor_pool_overrides", lambda pool, *_: pool)
    monkeypatch.setattr(cli.cli_legacy, "_apply_mentor_pool_overrides", lambda pool, *_: pool)

    args = Namespace(
        students=None,
        pool=None,
        output=str(tmp_path / "alloc.xlsx"),
        policy=str(tmp_path / "policy.json"),
        capacity_column=None,
        mentor_overrides=None,
        manager_overrides=None,
        _ui_overrides={},
        local_db_path=str(db.path),
        disable_local_db=False,
        academic_year=1402,
        prior_roster=None,
        current_roster=None,
        export_profile="sabt",
        export_profile_path=None,
        sabt_output=None,
        sabt_config=None,
        sabt_template=None,
        audit=False,
        metrics=False,
        determinism_check=False,
        counter_duplicate_strategy="prompt",
    )

    result = cli._run_allocate(args, policy, lambda *_: None)

    assert result == 0
    assert "students" in captured and not captured["students"].empty
    assert "pool" in captured and not captured["pool"].empty


def test_build_matrix_errors_when_cache_missing(tmp_path: Path) -> None:
    policy = load_policy()
    db = LocalDatabase(tmp_path / "cache.sqlite")
    args = Namespace(
        inspactor=None,
        output=str(tmp_path / "out.xlsx"),
        schools=None,
        crosswalk=None,
        min_coverage=None,
        policy_version=None,
        manager_overrides=None,
        mentor_overrides=None,
        _ui_overrides={},
        local_db_path=str(db.path),
        disable_local_db=False,
        policy=str(tmp_path / "policy.json"),
    )

    try:
        cli._run_build_matrix(args, policy, lambda *_: None)
    except Exception as exc:  # noqa: BLE001
        assert "import-mentors" in str(exc)
    else:  # pragma: no cover
        assert False, "expected failure due to missing cache"


def _write_pool_workbook(path: Path, primary: pd.DataFrame, alternate: pd.DataFrame) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        primary.to_excel(writer, sheet_name="primary", index=False)
        alternate.to_excel(writer, sheet_name="alt", index=False)


def test_pool_sheet_selection_matches_cli_and_cache(tmp_path: Path) -> None:
    policy = load_policy()
    db = LocalDatabase(tmp_path / "cache.sqlite")

    schools_df = pd.DataFrame(
        {
            "کد مدرسه": [3581],
            "نام مدرسه": ["نمونه"],
            "مرکز گلستان صدرا": [1],
            "جنسیت": [1],
        }
    )
    schools_path = tmp_path / "schools.xlsx"
    _write_excel(schools_df, schools_path)
    import_school_report_from_excel(schools_path, db=db)

    crosswalk_path = tmp_path / "crosswalk.xlsx"
    with pd.ExcelWriter(crosswalk_path, engine="openpyxl") as writer:
        pd.DataFrame(
            {"گروه آزمایشی": ["27"], "کد گروه": [27], "مقطع تحصیلی": ["دوازدهم"]}
        ).to_excel(writer, sheet_name="پایه تحصیلی (گروه آزمایشی)", index=False)
    import_school_crosswalk_from_excel(crosswalk_path, db=db)

    primary_pool = pd.DataFrame(
        {
            "نام پشتیبان": ["پشتیبان A"],
            "نام مدیر": ["مرکز"],
            "کد کارمندی پشتیبان": ["M-1"],
            "گروه آزمایشی": ["27"],
            "شامل گروه های آزمایشی": ["27"],
            "جنسیت": [1],
            "دانش آموز فارغ": [0],
            "مرکز گلستان صدرا": [1],
            "مالی حکمت بنیاد": [0],
            "کد مدرسه": [3581],
            "کدرشته": [27],
            "remaining_capacity": [1],
        }
    )
    alternate_pool = primary_pool.copy()
    alternate_pool["remaining_capacity"] = [9]
    pool_path = tmp_path / "pool.xlsx"
    _write_pool_workbook(pool_path, primary_pool, alternate_pool)

    args = Namespace(pool=str(pool_path), pool_type="inspactor", pool_sheet="alt")

    pool_df, _, _ = cli._resolve_mentor_pool_frame(
        args, policy, db=None, pool_arg="pool", pool_source="inspactor"
    )
    assert int(pool_df["remaining_capacity"].iloc[0]) == 9

    import_mentor_pool_from_excel(
        pool_path,
        db=db,
        policy=policy,
        pool_source="inspactor",
        pool_type="inspactor",
        pool_sheet="alt",
    )
    cached_pool = load_mentor_pool_from_cache(db=db, policy=policy)

    assert int(cached_pool["remaining_capacity"].iloc[0]) == 9

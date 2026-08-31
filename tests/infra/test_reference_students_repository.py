from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal

from app.core.policy_loader import load_policy
from app.infra.groupcode.groupcode_repository import GroupCodeRepository
from app.infra.local_database import LocalDatabase
from app.infra.reference_students_repository import (
    import_student_report_from_excel,
    load_students_from_cache,
)
from app.infra.schools.school_repository import SchoolRepository


def _write_student_excel(df: pd.DataFrame, path: Path) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)


def _seed_references(db: LocalDatabase, tmp_path: Path) -> None:
    schools_path = tmp_path / "schools.xlsx"
    _write_student_excel(
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

    groups_path = tmp_path / "groupcodes.xlsx"
    _write_student_excel(
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


def test_students_cache_roundtrip(tmp_path: Path) -> None:
    policy = load_policy()
    db = LocalDatabase(tmp_path / "cache.sqlite")
    _seed_references(db, tmp_path)

    raw = pd.DataFrame(
        {
            "student_id": ["S1", "S2"],
            "کدرشته": [1, 1],
            "گروه آزمایشی": ["تجربی", "تجربی"],
            "جنسیت": [1, 0],
            "دانش آموز فارغ": [0, 0],
            "مرکز گلستان صدرا": [1, 1],
            "مالی حکمت بنیاد": [0, 0],
            "کد مدرسه": [3581, 3581],
            "کد ملی": ["001", "002"],
        }
    )
    excel_path = tmp_path / "students.xlsx"
    _write_student_excel(raw, excel_path)

    normalized = import_student_report_from_excel(excel_path, db=db, policy=policy)
    loaded = load_students_from_cache(db=db, policy=policy)

    assert list(loaded.dtypes[policy.join_keys]) == ["Int64"] * len(policy.join_keys)
    assert_frame_equal(
        loaded.sort_values(by="student_id").reset_index(drop=True),
        normalized.sort_values(by="student_id").reset_index(drop=True),
        check_dtype=False,
    )

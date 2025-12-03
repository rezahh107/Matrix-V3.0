from pathlib import Path

import pandas as pd

from app.core.policy_loader import load_policy
from app.infra.local_database import LocalDatabase
from app.infra.reference_schools_repository import import_school_report_with_validation


def test_school_import_with_join_key_validation(tmp_path: Path) -> None:
    policy = load_policy()
    df = pd.DataFrame(
        [
            {
                "کدرشته": 1,
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 1,
                "مالی حکمت بنیاد": 0,
                "کد مدرسه": 100,
            },
            {
                "کدرشته": "bad",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 1,
                "مالی حکمت بنیاد": 0,
                "کد مدرسه": 101,
            },
        ]
    )
    path = tmp_path / "schools.xlsx"
    df.to_excel(path, index=False)
    db = LocalDatabase(tmp_path / "db.sqlite")
    result = import_school_report_with_validation(path, db=db, policy=policy)
    assert len(result.canonical_df) == 1
    assert len(result.issues) >= 1

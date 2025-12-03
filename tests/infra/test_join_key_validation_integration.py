from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.policy_loader import load_policy
from app.infra.excel.import_students import import_students_with_validation
from app.infra.local_database import LocalDatabase


def test_student_import_validation(tmp_path: Path) -> None:
    policy = load_policy()
    df = pd.DataFrame(
        [
            {
                "کدرشته": "1",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 2,
                "مالی حکمت بنیاد": 1,
                "کد مدرسه": 10,
            },
            {
                "کدرشته": "",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 2,
                "مالی حکمت بنیاد": 1,
                "کد مدرسه": 10,
            },
        ]
    )
    csv_path = tmp_path / "students.csv"
    df.to_csv(csv_path, index=False)
    db = LocalDatabase(tmp_path / "db.sqlite")
    result = import_students_with_validation(csv_path, db=db, policy=policy)
    assert len(result.canonical_df) == 1
    assert result.issues

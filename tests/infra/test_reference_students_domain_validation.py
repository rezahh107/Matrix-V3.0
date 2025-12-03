from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.policy_loader import load_policy
from app.infra.excel.import_students import import_students_with_validation
from app.infra.local_database import LocalDatabase


def test_reference_students_repo_applies_domain_validation(tmp_path: Path) -> None:
    policy = load_policy()
    df = pd.DataFrame(
        [
            {
                "کدرشته": 1,
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 2,
                "مالی حکمت بنیاد": 1,
                "کد مدرسه": 10,
            },
            {
                "کدرشته": 33,
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
    assert result.domain.issues


def test_domain_issues_persisted_to_cache(tmp_path: Path) -> None:
    policy = load_policy()
    df = pd.DataFrame(
        {
            "کدرشته": [33],
            "جنسیت": [1],
            "دانش آموز فارغ": [0],
            "مرکز گلستان صدرا": [2],
            "مالی حکمت بنیاد": [1],
            "کد مدرسه": [10],
        }
    )
    csv_path = tmp_path / "students.csv"
    df.to_csv(csv_path, index=False)
    db = LocalDatabase(tmp_path / "db.sqlite")
    result = import_students_with_validation(csv_path, db=db, policy=policy)
    cached = result.canonical_df
    assert cached.empty
    # join-key issues are independent from domain issues
    assert not result.join_keys.issues

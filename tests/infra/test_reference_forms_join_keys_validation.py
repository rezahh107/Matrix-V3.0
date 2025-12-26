from pathlib import Path

import pandas as pd

from app.core.policy_loader import load_policy
from app.infra.local_database import LocalDatabase
from app.infra.reference_forms_repository import (
    import_forms_with_validation,
    load_forms_with_validation,
)


def test_forms_import_with_join_key_validation(tmp_path: Path) -> None:
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
                "کدرشته": None,
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 1,
                "مالی حکمت بنیاد": 0,
                "کد مدرسه": 101,
            },
        ]
    )
    path = tmp_path / "forms.xlsx"
    df.to_excel(path, index=False)
    db = LocalDatabase(tmp_path / "db.sqlite")
    result = import_forms_with_validation(path, db=db, policy=policy)
    assert len(result.canonical_df) == 1
    assert len(result.issues) >= 1


def test_forms_import_accepts_alias_headers(tmp_path: Path) -> None:
    policy = load_policy()
    df = pd.DataFrame(
        [
            {
                "گروه آزمایشی نهایی": 1,
                "gender": 1,
                "وضعیت تحصیلی": 0,
                "مرکز ثبت نام": 3,
                "وضعیت ثبت نام": 0,
                "مدرسه نهایی": 200,
            }
        ]
    )
    path = tmp_path / "forms_alias.xlsx"
    df.to_excel(path, index=False)
    db = LocalDatabase(tmp_path / "db.sqlite")

    result = import_forms_with_validation(path, db=db, policy=policy)

    assert not result.issues
    assert set(policy.join_keys).issubset(result.canonical_df.columns)


def test_forms_cached_load_uses_header_pipeline_aliases(tmp_path: Path) -> None:
    policy = load_policy()
    db = LocalDatabase(tmp_path / "db.sqlite")
    cached = pd.DataFrame(
        [
            {
                "entry_id": "1",
                "received_at": pd.Timestamp("2024-01-01"),
                "گروه آزمایشی نهایی": 1,
                "gender": 1,
                "وضعیت تحصیلی": 0,
                "مرکز ثبت نام": 5,
                "وضعیت ثبت نام": 1,
                "مدرسه نهایی": 300,
            }
        ]
    )
    db.upsert_forms_entries(cached, source="test")

    result = load_forms_with_validation(db=db, policy=policy)

    assert not result.issues
    assert set(policy.join_keys).issubset(result.canonical_df.columns)

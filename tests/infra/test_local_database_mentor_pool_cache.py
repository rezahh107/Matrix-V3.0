from pathlib import Path

import pandas as pd
import pytest

from app.infra.errors import DatabaseSchemaMismatchError
from app.infra.local_database import LocalDatabase

JOIN_KEYS = [
    "کدرشته",
    "جنسیت",
    "دانش آموز فارغ",
    "مرکز گلستان صدرا",
    "مالی حکمت بنیاد",
    "کد مدرسه",
]


def _mentor_pool_row() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "mentor_id": ["m1"],
            "کد کارمندی پشتیبان": ["m1"],
            "کدرشته": [101],
            "گروه آزمایشی": ["رشته"],
            "جنسیت": [1],
            "دانش آموز فارغ": [0],
            "مرکز گلستان صدرا": [1],
            "مالی حکمت بنیاد": [0],
            "کد مدرسه": [0],
            "remaining_capacity": [2.0],
            "allocations_new": [0],
            "occupancy_ratio": [0.0],
        }
    )


def test_load_mentor_pool_cache_enforces_versions(tmp_path: Path) -> None:
    db = LocalDatabase(tmp_path / "pool.sqlite")
    df = _mentor_pool_row()
    db.upsert_mentor_pool_cache(
        df, join_keys=JOIN_KEYS, policy_version="0.9.0", ssot_version="0.9.0"
    )

    with pytest.raises(DatabaseSchemaMismatchError):
        db.load_mentor_pool_cache(join_keys=JOIN_KEYS)


def test_load_mentor_pool_cache_preserves_metadata(tmp_path: Path) -> None:
    db = LocalDatabase(tmp_path / "pool.sqlite")
    df = _mentor_pool_row()
    pool_hash = "hash-abc"

    db.upsert_mentor_pool_cache(df, join_keys=JOIN_KEYS, pool_hash=pool_hash)
    loaded = db.load_mentor_pool_cache(join_keys=JOIN_KEYS)

    assert loaded["policy_version"].iat[0] == "1.0.3"
    assert loaded["ssot_version"].iat[0] == "1.0.2"
    assert loaded["pool_hash"].iat[0] == pool_hash

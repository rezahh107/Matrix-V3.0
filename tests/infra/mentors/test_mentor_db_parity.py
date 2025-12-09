from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.core.policy_adapter import policy
from app.infra.errors import DatabasePreparationError
from app.infra.groupcode.groupcode_repository import GroupCodeRepository
from app.infra.local_database import LocalDatabase
from app.infra.mentors.pipeline_v3 import MentorPipelineV3
from app.infra.schools.school_repository import SchoolRepository


def _write_excel(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)


def _seed_reference_data(
    tmp_path: Path,
) -> tuple[LocalDatabase, SchoolRepository, GroupCodeRepository]:
    db = LocalDatabase(tmp_path / "local.sqlite")
    school_repo = SchoolRepository(db)
    groupcode_repo = GroupCodeRepository(db)

    schools_df = pd.DataFrame(
        {
            "کد مدرسه": [101, 102],
            "نام مدرسه": ["A", "B"],
            "مرکز گلستان صدرا": [10, 11],
            "جنسیت": [1, 1],
            "فعال": [1, 1],
        }
    )
    groupcodes_df = pd.DataFrame(
        {
            "group_code": [1, 2],
            "level": ["L1", "L2"],
            "grade": [1, 2],
            "track": ["T1", "T2"],
            "is_active": [1, 1],
        }
    )

    school_path = tmp_path / "schools.xlsx"
    groupcode_path = tmp_path / "groupcodes.xlsx"
    _write_excel(schools_df, school_path)
    _write_excel(groupcodes_df, groupcode_path)

    school_repo.import_from_excel(school_path)
    groupcode_repo.import_from_excel(groupcode_path)
    return db, school_repo, groupcode_repo


def _mentor_payload() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "mentor_id": ["m1", "m2"],
            "ظرفیت": [2, 1],
            "کدرشته": [1, 1],
            "جنسیت": [1, 1],
            "دانش آموز فارغ": [0, 0],
            "مرکز گلستان صدرا": [10, 11],
            "مالی حکمت بنیاد": [0, 0],
            "کد مدرسه": [101, 102],
        }
    )


def test_db_mode_matches_excel_mode(tmp_path: Path) -> None:
    db, school_repo, groupcode_repo = _seed_reference_data(tmp_path)
    payload = _mentor_payload()

    excel_pipeline = MentorPipelineV3(policy=policy.config, reference_mode="excel")
    excel_result = excel_pipeline.run(payload)

    db_pipeline = MentorPipelineV3(
        policy=policy.config,
        db=db,
        school_repo=school_repo,
        groupcode_repo=groupcode_repo,
    )
    db_result = db_pipeline.run(payload)

    join_cols = ["mentor_id", *policy.config.join_keys, "remaining_capacity", "ظرفیت"]
    pd.testing.assert_frame_equal(
        db_result.build_result.pool.loc[:, join_cols].reset_index(drop=True),
        excel_result.build_result.pool.loc[:, join_cols].reset_index(drop=True),
        check_dtype=False,
    )


def test_db_mode_requires_reference_data(tmp_path: Path) -> None:
    db = LocalDatabase(tmp_path / "local.sqlite")
    school_repo = SchoolRepository(db)
    groupcode_repo = GroupCodeRepository(db)
    payload = _mentor_payload()

    pipeline = MentorPipelineV3(
        policy=policy.config,
        db=db,
        reference_mode="db",
        school_repo=school_repo,
        groupcode_repo=groupcode_repo,
    )

    with pytest.raises(DatabasePreparationError):
        pipeline.run(payload)

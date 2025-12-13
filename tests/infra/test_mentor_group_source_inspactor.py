from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.core.build_matrix import (
    COL_GENDER,
    COL_GROUP,
    COL_GROUP_INCLUDED,
    COL_MANAGER_NAME,
    COL_MENTOR_ID,
    COL_STATUS_B,
)
from app.core.policy_loader import load_policy
from app.infra.local_database import LocalDatabase
from app.infra.reference_mentors_repository import _derive_pool_join_keys


@pytest.fixture()
def _fake_school_frames(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_frames(_db: LocalDatabase):
        schools_df = pd.DataFrame({"کد مدرسه": [0], "نام مدرسه": ["مدرسه تست"]})
        crosswalk_df = pd.DataFrame(
            {"گروه آزمایشی": ["ریاضی"], "کد گروه": [27], "مقطع تحصیلی": [""]}
        )
        return schools_df, crosswalk_df, None

    monkeypatch.setattr(
        "app.infra.reference_mentors_repository.get_school_reference_frames",
        _fake_frames,
    )


def _derive(pool_df: pd.DataFrame, tmp_path: Path) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    policy = load_policy()
    db = LocalDatabase(tmp_path / "mentor_pool_group_source.sqlite")
    db.initialize()
    return _derive_pool_join_keys(pool_df, db=db, policy=policy)


def test_group_source_uses_included_column_only(tmp_path: Path, _fake_school_frames: None) -> None:
    pool_df = pd.DataFrame(
        {
            COL_MENTOR_ID: ["EMP-1"],
            COL_MANAGER_NAME: ["مدیر الف"],
            COL_GROUP_INCLUDED: ["27"],
            COL_GROUP: [""],
            COL_GENDER: [1],
            COL_STATUS_B: [1],
        }
    )

    derived, issues = _derive(pool_df, tmp_path)
    group_key = load_policy().stage_column("group")
    reasons = {issue.get("reason") for issue in issues}

    assert int(derived[group_key].iloc[0]) == 27
    assert "LEGACY_GROUP_CONFLICT" not in reasons
    assert "MISSING_INCLUDED_GROUP_COLUMN" not in reasons


def test_group_source_reports_legacy_conflict(tmp_path: Path, _fake_school_frames: None) -> None:
    pool_df = pd.DataFrame(
        {
            COL_MENTOR_ID: ["EMP-2"],
            COL_MANAGER_NAME: ["مدیر ب"],
            COL_GROUP_INCLUDED: ["27"],
            COL_GROUP: ["28"],
            COL_GENDER: [1],
            COL_STATUS_B: [1],
        }
    )

    derived, issues = _derive(pool_df, tmp_path)
    legacy_conflicts = [issue for issue in issues if issue.get("reason") == "LEGACY_GROUP_CONFLICT"]

    assert int(derived[load_policy().stage_column("group")].iloc[0]) == 27
    assert legacy_conflicts
    assert legacy_conflicts[0]["column"] == COL_GROUP


def test_group_source_missing_included_column_is_blocking(tmp_path: Path, _fake_school_frames: None) -> None:
    pool_df = pd.DataFrame(
        {
            COL_MENTOR_ID: ["EMP-3"],
            COL_MANAGER_NAME: ["مدیر ج"],
            COL_GROUP: ["27"],
            COL_GENDER: [1],
            COL_STATUS_B: [1],
        }
    )

    derived, issues = _derive(pool_df, tmp_path)
    reasons = {issue.get("reason") for issue in issues}

    assert COL_GROUP_INCLUDED not in derived.columns
    assert "MISSING_INCLUDED_GROUP_COLUMN" in reasons

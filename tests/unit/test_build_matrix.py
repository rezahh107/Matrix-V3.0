import pandas as pd

from app.core.build_matrix import (
    CAPACITY_CURRENT_COL,
    CAPACITY_SPECIAL_COL,
    COL_GROUP,
    COL_MANAGER_NAME,
    COL_MENTOR_ID,
    COL_MENTOR_NAME,
    COL_POSTAL,
    COL_SCHOOL_COUNT,
    BuildConfig,
    build_matrix,
)
from app.core.canonical_frames import POOL_DUPLICATE_SUMMARY_ATTR, canonicalize_pool_frame
from app.core.policy_loader import load_policy


def test_build_matrix_reports_key_level_join_key_duplicates() -> None:
    policy = load_policy()
    insp_df = pd.DataFrame(
        {
            COL_MENTOR_NAME: ["الف", "الف"],
            COL_MANAGER_NAME: ["مدیر", "مدیر"],
            COL_MENTOR_ID: ["EMP-1", "EMP-1"],
            COL_GROUP: ["تجربی", "تجربی"],
            COL_POSTAL: ["1234", "2345"],
            COL_SCHOOL_COUNT: [0, 0],
            CAPACITY_CURRENT_COL: [0, 0],
            CAPACITY_SPECIAL_COL: [1, 1],
            "کدرشته": [1201, 1201],
            "جنسیت": [1, 1],
            "دانش آموز فارغ": [0, 0],
            "مرکز گلستان صدرا": [1, 1],
            "مالی حکمت بنیاد": [0, 0],
            "کد مدرسه": [3581, 3581],
        }
    )
    schools_df = pd.DataFrame({"کد مدرسه": [3581], "نام مدرسه 1": ["مدرسه"]})
    crosswalk_df = pd.DataFrame(
        {"گروه آزمایشی": ["تجربی"], "کد گروه": [1201], "مقطع تحصیلی": ["دهم"]}
    )

    cfg = BuildConfig(policy=policy)
    (
        matrix,
        validation,
        removed_df,
        unmatched_schools_df,
        unseen_groups_df,
        invalid_df,
        duplicate_join_keys_df,
        progress_log,
    ) = build_matrix(
        insp_df,
        schools_df,
        crosswalk_df,
        cfg=cfg,
    )

    assert not invalid_df.empty
    assert removed_df.empty
    assert unmatched_schools_df.empty
    assert unseen_groups_df.empty
    assert any("duplicate" in str(reason) for reason in invalid_df["reason"])

    assert not duplicate_join_keys_df.empty
    assert duplicate_join_keys_df[COL_MENTOR_ID].tolist() == ["EMP-1", "EMP-1"]
    assert duplicate_join_keys_df.attrs.get("duplicate_scope") == "per_mentor"
    assert duplicate_join_keys_df["duplicate_group_size"].dropna().unique().tolist() == [2]

    canonicalized = canonicalize_pool_frame(
        insp_df,
        policy=policy,
        sanitize_pool=False,
        pool_source="inspactor",
        require_join_keys=False,
        preserve_columns=["نام مدرسه 1"],
        include_distinct_mentor_duplicates=True,
    )
    summary = canonicalized.attrs[POOL_DUPLICATE_SUMMARY_ATTR]
    assert summary["duplicate_scope"] == "per_key"
    assert summary["total"] == len(duplicate_join_keys_df)
    assert canonicalized.attrs.get("pool_duplicate_scope") == "per_key"


def test_build_matrix_allows_distinct_mentors_on_same_join_key() -> None:
    policy = load_policy()
    insp_df = pd.DataFrame(
        {
            COL_MENTOR_NAME: ["الف", "ب"],
            COL_MANAGER_NAME: ["مدیر", "مدیر"],
            COL_MENTOR_ID: ["EMP-1", "EMP-2"],
            COL_GROUP: ["تجربی", "تجربی"],
            COL_POSTAL: ["1234", "2345"],
            COL_SCHOOL_COUNT: [0, 0],
            CAPACITY_CURRENT_COL: [0, 0],
            CAPACITY_SPECIAL_COL: [1, 1],
            "کدرشته": [1201, 1201],
            "جنسیت": [1, 1],
            "دانش آموز فارغ": [0, 0],
            "مرکز گلستان صدرا": [1, 1],
            "مالی حکمت بنیاد": [0, 0],
            "کد مدرسه": [3581, 3581],
        }
    )
    schools_df = pd.DataFrame({"کد مدرسه": [3581], "نام مدرسه 1": ["مدرسه"]})
    crosswalk_df = pd.DataFrame(
        {"گروه آزمایشی": ["تجربی"], "کد گروه": [1201], "مقطع تحصیلی": ["دهم"]}
    )

    cfg = BuildConfig(policy=policy)
    _, validation, *_rest, duplicate_join_keys_df, _ = build_matrix(
        insp_df,
        schools_df,
        crosswalk_df,
        cfg=cfg,
    )

    assert duplicate_join_keys_df.empty
    assert validation["join_key_duplicate_rows"].iat[0] == 0

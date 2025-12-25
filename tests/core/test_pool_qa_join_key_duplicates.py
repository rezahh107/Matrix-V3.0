import pandas as pd

from app.core.canonical_frames import build_join_key_duplicate_report, canonicalize_pool_frame
from app.core.policy_loader import load_policy


def test_pool_join_key_duplicates_frame_contains_all_columns() -> None:
    policy = load_policy()
    pool = pd.DataFrame(
        {
            "نام پشتیبان": ["الف", "ب", "الف"],
            "کد کارمندی پشتیبان": ["EMP-1", "EMP-2", "EMP-1"],
            "کدرشته": [1, 1, 1],
            "جنسیت": [0, 0, 0],
            "دانش آموز فارغ": [1, 1, 1],
            "مرکز گلستان صدرا": [0, 0, 0],
            "مالی حکمت بنیاد": [0, 0, 0],
            "کد مدرسه": [10, 10, 10],
        }
    )

    canonical = canonicalize_pool_frame(
        pool,
        policy=policy,
        sanitize_pool=False,
        pool_source="inspactor",
    )

    duplicate_report = build_join_key_duplicate_report(
        canonical,
        policy.join_keys,
        "کد کارمندی پشتیبان",
        include_distinct_mentors=False,
        pool_source="inspactor",
    )
    prefix = list(duplicate_report.columns)[: len(policy.join_keys) + 1]
    assert prefix[: len(policy.join_keys)] == list(policy.join_keys)
    assert prefix[-1] in {"mentor_id", "کد کارمندی پشتیبان"}
    assert "duplicate_group_size" in duplicate_report.columns
    assert "pool_row_index" in duplicate_report.columns
    assert "pool_source" in duplicate_report.columns
    mentor_col = "mentor_id" if "mentor_id" in duplicate_report.columns else "کد کارمندی پشتیبان"
    assert duplicate_report["duplicate_group_size"].max() == 2
    assert set(duplicate_report[mentor_col]) == {"EMP-1"}
    assert duplicate_report["pool_source"].iat[0] == "inspactor"

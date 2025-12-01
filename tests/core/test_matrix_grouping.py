import pandas as pd

from app.core.common.domain import BuildConfig
from app.core.matrix.grouping import build_candidate_group_keys


def test_normal_candidate_keeps_small_postal_alias_with_policy_range_override() -> None:
    cfg = BuildConfig(postal_valid_range=(1, 9999))
    base_df = pd.DataFrame(
        {
            "mentor_id": ["m1"],
            "group_pairs": [[("گروه", 101)]],
            "genders": [[1]],
            "statuses_normal": [[1]],
            "statuses_school": [[]],
            "finance": [[0]],
            "schools_normal": [[0]],
            "school_codes": [[]],
            "center_code": [1],
            "alias_normal": ["999"],
            "alias_school": [""],
            "can_normal": [True],
            "can_school": [False],
        }
    )

    candidates = build_candidate_group_keys(
        base_df,
        join_keys=cfg.policy.join_keys,
        center_column="مرکز گلستان صدرا",
        finance_column="مالی حکمت بنیاد",
        school_code_column=cfg.policy.columns.school_code,
        cfg=cfg,
    )

    normal_rows = candidates.loc[candidates["variant"] == "normal"]
    assert not normal_rows.empty
    assert normal_rows["has_alias"].all()
    assert normal_rows["can_generate"].all()


def test_school_candidate_uses_mentor_id_alias_without_numeric_threshold() -> None:
    cfg = BuildConfig()
    base_df = pd.DataFrame(
        {
            "mentor_id": ["s1"],
            "group_pairs": [[("گروه", 101)]],
            "genders": [[1]],
            "statuses_normal": [[]],
            "statuses_school": [[1]],
            "finance": [[0]],
            "schools_normal": [[]],
            "school_codes": [[5001]],
            "center_code": [1],
            "alias_normal": [""],
            "alias_school": ["SCHOOL-ID"],
            "can_normal": [False],
            "can_school": [True],
        }
    )

    candidates = build_candidate_group_keys(
        base_df,
        join_keys=cfg.policy.join_keys,
        center_column="مرکز گلستان صدرا",
        finance_column="مالی حکمت بنیاد",
        school_code_column=cfg.policy.columns.school_code,
        cfg=cfg,
    )

    school_rows = candidates.loc[candidates["variant"] == "school"]
    assert not school_rows.empty
    assert school_rows["has_alias"].all()
    assert school_rows["can_generate"].all()

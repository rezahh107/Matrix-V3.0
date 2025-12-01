from dataclasses import replace

import pandas as pd
import pytest

from app.core.canonical_frames import canonicalize_pool_frame, canonicalize_students_frame
from app.core.common.join_keys import JoinKeyCanonicalizationError
from app.core.policy_loader import load_policy


def test_canonicalize_students_frame_normalizes_localized_join_keys() -> None:
    policy = load_policy()
    students = pd.DataFrame(
        {
            "student_id": ["s1"],
            policy.stage_column("group"): ["۹۱۰۰"],
            policy.stage_column("gender"): ["پسر"],
            policy.stage_column("graduation_status"): ["۰"],
            policy.stage_column("center"): ["۰۳"],
            policy.stage_column("finance"): ["۳"],
            policy.columns.school_code: [""],
        }
    )

    canonical = canonicalize_students_frame(students, policy=policy)

    for column in policy.join_keys:
        assert pd.api.types.is_integer_dtype(canonical[column])
        assert canonical[column].isna().sum() == 0
    assert canonical[policy.stage_column("gender")].iloc[0] == int(policy.gender_codes.male.value)
    assert canonical[policy.stage_column("center")].iloc[0] == 3
    assert canonical[policy.stage_column("finance")].iloc[0] == 3


def test_canonicalize_pool_frame_rejects_invalid_school_code() -> None:
    policy = replace(load_policy(), school_code_empty_as_zero=False)
    pool = pd.DataFrame(
        {
            policy.stage_column("group"): [1201],
            policy.stage_column("gender"): [1],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [1],
            policy.stage_column("finance"): [1],
            policy.columns.school_code: ["نامعتبر"],
            "کد کارمندی پشتیبان": ["m1"],
            "remaining_capacity": [1],
        }
    )

    with pytest.raises(JoinKeyCanonicalizationError):
        canonicalize_pool_frame(pool, policy=policy)


def test_sanitize_pool_does_not_drop_alias_by_virtual_range() -> None:
    policy = replace(
        load_policy(),
        virtual_alias_ranges=((7000, 8000),),
    )
    pool = pd.DataFrame(
        {
            "mentor_name": ["مجازی"],
            "alias": [7501],
            "remaining_capacity": [1],
            "کدرشته": [101],
            "جنسیت": [1],
            "دانش آموز فارغ": [1],
            "مرکز گلستان صدرا": [1],
            "مالی حکمت بنیاد": [0],
            "کد مدرسه": [0],
        }
    )

    sanitized = canonicalize_pool_frame(
        pool, policy=policy, sanitize_pool=True, pool_source="inspactor"
    )

    assert len(sanitized) == 1

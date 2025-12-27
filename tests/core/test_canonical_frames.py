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
            policy.stage_column("group"): ["۲۱"],
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



def test_canonicalize_students_frame_infers_center_from_manager_when_zero() -> None:
    policy = replace(load_policy(), center_map={"مدیر الف": 5, "*": 0})
    students = pd.DataFrame(
        {
            "student_id": ["s1"],
            "مدیر": ["مدیر الف"],
            policy.stage_column("group"): [21],
            policy.stage_column("gender"): ["پسر"],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [0],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [0],
        }
    )

    canonical = canonicalize_students_frame(students, policy=policy)

    assert canonical[policy.stage_column("center")].iloc[0] == 5


def test_canonicalize_students_frame_infers_center_from_manager_substring() -> None:
    policy = replace(load_policy(), center_map={"مدیر": 4})
    students = pd.DataFrame(
        {
            "student_id": ["s1"],
            "مدیر": ["مدیر ارشد"],
            policy.stage_column("group"): [21],
            policy.stage_column("gender"): ["پسر"],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [0],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [0],
        }
    )

    canonical = canonicalize_students_frame(students, policy=policy)

    assert canonical[policy.stage_column("center")].iloc[0] == 4


def test_canonicalize_students_frame_infers_center_from_wildcard() -> None:
    policy = replace(load_policy(), center_map={"*": 9})
    students = pd.DataFrame(
        {
            "student_id": ["s1"],
            "مدیر": ["نامشخص"],
            policy.stage_column("group"): [21],
            policy.stage_column("gender"): ["پسر"],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [0],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [0],
        }
    )

    canonical = canonicalize_students_frame(students, policy=policy)

    assert canonical[policy.stage_column("center")].iloc[0] == 9


def test_canonicalize_students_frame_no_center_match_keeps_zero() -> None:
    policy = replace(load_policy(), center_map={"مدیر الف": 3})
    students = pd.DataFrame(
        {
            "student_id": ["s1"],
            "مدیر": ["نامشخص"],
            policy.stage_column("group"): [21],
            policy.stage_column("gender"): ["پسر"],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [0],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [0],
        }
    )

    canonical = canonicalize_students_frame(students, policy=policy)

    assert canonical[policy.stage_column("center")].iloc[0] == 0


def test_canonicalize_students_frame_prefers_longest_substring_match() -> None:
    policy = replace(load_policy(), center_map={"مدیر": 2, "مدیر ارشد": 6})
    students = pd.DataFrame(
        {
            "student_id": ["s1"],
            "مدیر": ["مدیر ارشد اول"],
            policy.stage_column("group"): [21],
            policy.stage_column("gender"): ["پسر"],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [0],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [0],
        }
    )

    canonical = canonicalize_students_frame(students, policy=policy)

    assert canonical[policy.stage_column("center")].iloc[0] == 6


def test_canonicalize_students_frame_breaks_ties_lexicographically() -> None:
    policy = replace(load_policy(), center_map={"الف": 7, "بتا": 8})
    students = pd.DataFrame(
        {
            "student_id": ["s1"],
            "مدیر": ["مدیر الف بتا"],
            policy.stage_column("group"): [21],
            policy.stage_column("gender"): ["پسر"],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [0],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [0],
        }
    )

    canonical = canonicalize_students_frame(students, policy=policy)

    assert canonical[policy.stage_column("center")].iloc[0] == 7

def test_canonicalize_pool_frame_rejects_invalid_school_code() -> None:
    policy = replace(load_policy(), school_code_empty_as_zero=False)
    pool = pd.DataFrame(
        {
            policy.stage_column("group"): [1],
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


def test_canonicalize_pool_frame_reports_index_on_missing_join_key() -> None:
    policy = load_policy()
    pool = pd.DataFrame(
        {
            policy.stage_column("group"): [pd.NA],
            policy.stage_column("gender"): [1],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [1],
            policy.stage_column("finance"): [1],
            policy.columns.school_code: [0],
            "کد کارمندی پشتیبان": ["m1"],
            "remaining_capacity": [1],
        }
    )

    with pytest.raises(JoinKeyCanonicalizationError) as excinfo:
        canonicalize_pool_frame(pool, policy=policy)

    message = str(excinfo.value)
    assert "index 0" in message
    assert policy.stage_column("group") in message


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
            "کدرشته": [21],
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


def test_canonicalize_pool_frame_derives_remaining_capacity_with_baseline() -> None:
    policy = load_policy()
    pool = pd.DataFrame(
        {
            policy.stage_column("group"): [21],
            policy.stage_column("gender"): [1],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [1],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [0],
            "mentor_id": ["m1"],
            "capacity_limit": [10],
            "assigned_baseline": [2],
            "allocations_new": [3],
            "remaining_capacity": [99],
        }
    )

    canonical = canonicalize_pool_frame(pool, policy=policy)

    assert canonical["remaining_capacity"].iloc[0] == 5
    assert pd.api.types.is_integer_dtype(canonical["remaining_capacity"])


def test_canonicalize_pool_frame_reconstructs_capacity_limit_legacy_inputs() -> None:
    policy = load_policy()
    pool = pd.DataFrame(
        {
            policy.stage_column("group"): [21],
            policy.stage_column("gender"): [1],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [1],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [0],
            "mentor_id": ["m1"],
            "remaining_capacity": [4],
            "allocations_new": [1],
        }
    )

    canonical = canonicalize_pool_frame(pool, policy=policy)

    assert canonical["capacity_limit"].iloc[0] == 5
    assert canonical["assigned_baseline"].iloc[0] == 0
    assert canonical["remaining_capacity"].iloc[0] == 4

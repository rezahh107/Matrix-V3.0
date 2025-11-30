from __future__ import annotations

from dataclasses import replace

import pandas as pd

from app.core.policy_loader import load_policy
from app.infra.qa.alloc_join_validation import validate_allocation_join_keys_with_wildcard
from app.infra.validators.join_keys import validate_allocation_join_keys


def test_validate_allocation_join_keys_with_school_wildcard() -> None:
    policy = load_policy()
    school_col = policy.columns.school_code
    allocations = pd.DataFrame({"student_id": ["s1"], "mentor_id": ["m1"]})
    students = pd.DataFrame(
        {
            "student_id": ["s1"],
            policy.stage_column("group"): [1],
            policy.stage_column("gender"): [1],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [1],
            policy.stage_column("finance"): [0],
            school_col: [123],
        }
    )
    mentors = pd.DataFrame(
        {
            "mentor_id": ["m1"],
            policy.stage_column("group"): [1],
            policy.stage_column("gender"): [1],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [1],
            policy.stage_column("finance"): [0],
            school_col: [0],
        }
    )

    base = validate_allocation_join_keys(allocations, students, mentors, policy=policy)
    wildcard = validate_allocation_join_keys_with_wildcard(
        allocations, students, mentors, policy=policy
    )

    assert base.invalid_count == 1
    assert wildcard.invalid_count == 0


def test_validate_allocation_join_keys_with_school_wildcard_disabled() -> None:
    policy = replace(load_policy(), school_code_empty_as_zero=False)
    school_col = policy.columns.school_code
    allocations = pd.DataFrame({"student_id": ["s1"], "mentor_id": ["m1"]})
    students = pd.DataFrame(
        {
            "student_id": ["s1"],
            policy.stage_column("group"): [1],
            policy.stage_column("gender"): [1],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [1],
            policy.stage_column("finance"): [0],
            school_col: [0],
        }
    )
    mentors = pd.DataFrame(
        {
            "mentor_id": ["m1"],
            policy.stage_column("group"): [1],
            policy.stage_column("gender"): [1],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [1],
            policy.stage_column("finance"): [0],
            school_col: [123],
        }
    )

    base = validate_allocation_join_keys(allocations, students, mentors, policy=policy)
    wildcard = validate_allocation_join_keys_with_wildcard(
        allocations, students, mentors, policy=policy
    )

    assert base.invalid_count == 1
    assert wildcard.invalid_count == 0


def test_validate_allocation_join_keys_with_center_wildcard() -> None:
    policy = load_policy()
    center_col = policy.stage_column("center")
    allocations = pd.DataFrame({"student_id": ["s1"], "mentor_id": ["m1"]})
    students = pd.DataFrame(
        {
            "student_id": ["s1"],
            policy.stage_column("group"): [1],
            policy.stage_column("gender"): [1],
            policy.stage_column("graduation_status"): [0],
            center_col: [5],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [0],
        }
    )
    mentors = pd.DataFrame(
        {
            "mentor_id": ["m1"],
            policy.stage_column("group"): [1],
            policy.stage_column("gender"): [1],
            policy.stage_column("graduation_status"): [0],
            center_col: [0],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [0],
        }
    )

    wildcard = validate_allocation_join_keys_with_wildcard(
        allocations, students, mentors, policy=policy
    )

    assert wildcard.invalid_count == 0


def test_validate_allocation_join_keys_flags_student_center_zero_without_policy_wildcard() -> None:
    policy = replace(load_policy(), center_map={})
    center_col = policy.stage_column("center")
    allocations = pd.DataFrame({"student_id": ["s1"], "mentor_id": ["m1"]})
    students = pd.DataFrame(
        {
            "student_id": ["s1"],
            policy.stage_column("group"): [1],
            policy.stage_column("gender"): [1],
            policy.stage_column("graduation_status"): [0],
            center_col: [0],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [0],
        }
    )
    mentors = pd.DataFrame(
        {
            "mentor_id": ["m1"],
            policy.stage_column("group"): [1],
            policy.stage_column("gender"): [1],
            policy.stage_column("graduation_status"): [0],
            center_col: [2],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [0],
        }
    )

    wildcard = validate_allocation_join_keys_with_wildcard(
        allocations, students, mentors, policy=policy
    )

    assert wildcard.invalid_count == 1


def test_validate_allocation_join_keys_flags_missing_student_center() -> None:
    policy = load_policy()
    center_col = policy.stage_column("center")
    allocations = pd.DataFrame({"student_id": ["s1"], "mentor_id": ["m1"]})
    students = pd.DataFrame(
        {
            "student_id": ["s1"],
            policy.stage_column("group"): [1],
            policy.stage_column("gender"): [1],
            policy.stage_column("graduation_status"): [0],
            center_col: [pd.NA],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [0],
        }
    )
    mentors = pd.DataFrame(
        {
            "mentor_id": ["m1"],
            policy.stage_column("group"): [1],
            policy.stage_column("gender"): [1],
            policy.stage_column("graduation_status"): [0],
            center_col: [2],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [0],
        }
    )

    wildcard = validate_allocation_join_keys_with_wildcard(
        allocations, students, mentors, policy=policy
    )

    assert wildcard.invalid_count == 1


def test_validate_allocation_join_keys_accepts_mentor_global_center() -> None:
    policy = replace(load_policy(), center_map={"*": 0})
    center_col = policy.stage_column("center")
    allocations = pd.DataFrame({"student_id": ["s1"], "mentor_id": ["m1"]})
    students = pd.DataFrame(
        {
            "student_id": ["s1"],
            policy.stage_column("group"): [1],
            policy.stage_column("gender"): [1],
            policy.stage_column("graduation_status"): [0],
            center_col: [5],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [0],
        }
    )
    mentors = pd.DataFrame(
        {
            "mentor_id": ["m1"],
            policy.stage_column("group"): [1],
            policy.stage_column("gender"): [1],
            policy.stage_column("graduation_status"): [0],
            center_col: [0],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [0],
        }
    )

    wildcard = validate_allocation_join_keys_with_wildcard(
        allocations, students, mentors, policy=policy
    )

    assert wildcard.invalid_count == 0


def test_validate_allocation_join_keys_rejects_student_center_zero_with_policy_wildcard() -> None:
    policy = replace(load_policy(), center_map={"*": 0})
    center_col = policy.stage_column("center")
    allocations = pd.DataFrame({"student_id": ["s1"], "mentor_id": ["m1"]})
    students = pd.DataFrame(
        {
            "student_id": ["s1"],
            policy.stage_column("group"): [1],
            policy.stage_column("gender"): [1],
            policy.stage_column("graduation_status"): [0],
            center_col: [0],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [0],
        }
    )
    mentors = pd.DataFrame(
        {
            "mentor_id": ["m1"],
            policy.stage_column("group"): [1],
            policy.stage_column("gender"): [1],
            policy.stage_column("graduation_status"): [0],
            center_col: [5],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [0],
        }
    )

    wildcard = validate_allocation_join_keys_with_wildcard(
        allocations, students, mentors, policy=policy
    )

    assert wildcard.invalid_count == 1


def test_validate_allocation_join_keys_with_center_and_school_mismatch() -> None:
    policy = replace(load_policy(), school_code_empty_as_zero=False)
    allocations = pd.DataFrame({"student_id": ["s1"], "mentor_id": ["m1"]})
    students = pd.DataFrame(
        {
            "student_id": ["s1"],
            policy.stage_column("group"): [1],
            policy.stage_column("gender"): [1],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [1],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [10],
        }
    )
    mentors = pd.DataFrame(
        {
            "mentor_id": ["m1"],
            policy.stage_column("group"): [1],
            policy.stage_column("gender"): [1],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [2],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [11],
        }
    )

    wildcard = validate_allocation_join_keys_with_wildcard(
        allocations, students, mentors, policy=policy
    )

    assert wildcard.invalid_count == 1


def test_validate_allocation_join_keys_handles_farsi_tokens_and_localized_digits() -> None:
    policy = load_policy()
    allocations = pd.DataFrame({"student_id": ["s1"], "mentor_id": ["m1"]})
    students = pd.DataFrame(
        {
            "student_id": ["s1"],
            policy.stage_column("group"): ["۹۱۰۰"],
            policy.stage_column("gender"): ["پسر"],
            policy.stage_column("graduation_status"): ["۰"],
            policy.stage_column("center"): ["۰۳"],
            policy.stage_column("finance"): ["۳"],
            policy.columns.school_code: ["۰"],
        }
    )
    mentors = pd.DataFrame(
        {
            "mentor_id": ["m1"],
            policy.stage_column("group"): [9100],
            policy.stage_column("gender"): [1],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [3],
            policy.stage_column("finance"): [3],
            policy.columns.school_code: [0],
        }
    )

    audit = validate_allocation_join_keys_with_wildcard(
        allocations, students, mentors, policy=policy
    )

    assert audit.invalid_count == 0


def test_validate_allocation_join_keys_flags_mismatch_after_canonicalization() -> None:
    policy = load_policy()
    allocations = pd.DataFrame({"student_id": ["s1"], "mentor_id": ["m1"]})
    students = pd.DataFrame(
        {
            "student_id": ["s1"],
            policy.stage_column("group"): ["۹۱۰۰"],
            policy.stage_column("gender"): ["پسر"],
            policy.stage_column("graduation_status"): ["۰"],
            policy.stage_column("center"): ["۰۳"],
            policy.stage_column("finance"): ["۳"],
            policy.columns.school_code: ["۰"],
        }
    )
    mentors = pd.DataFrame(
        {
            "mentor_id": ["m1"],
            policy.stage_column("group"): [9100],
            policy.stage_column("gender"): [1],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [4],
            policy.stage_column("finance"): [3],
            policy.columns.school_code: [0],
        }
    )

    audit = validate_allocation_join_keys_with_wildcard(
        allocations, students, mentors, policy=policy
    )

    assert audit.invalid_count == 1
    assert "مرکز گلستان صدرا" in audit.audit_frame.loc[0, "mismatch_summary"]

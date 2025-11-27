from __future__ import annotations

from dataclasses import replace

import pandas as pd

from app.core.allocate_students import (
    _detect_pool_mismatch,
    _filter_candidates_by_join_map,
    _merge_join_mismatches,
    allocate_student,
)
from app.core.common.filters import apply_join_filters
from app.core.common.join_keys import normalize_join_key_name
from app.core.policy_loader import load_policy


def test_filter_candidates_respects_finance_variants() -> None:
    policy = load_policy()
    join_map = {
        normalize_join_key_name(policy.stage_column("group")): 1,
        normalize_join_key_name(policy.stage_column("gender")): 1,
        normalize_join_key_name(policy.stage_column("graduation_status")): 0,
        normalize_join_key_name(policy.stage_column("center")): 1,
        normalize_join_key_name(policy.stage_column("finance")): 0,
        normalize_join_key_name(policy.columns.school_code): 0,
    }
    pool = pd.DataFrame(
        {
            "mentor_id": ["m1", "m2"],
            policy.stage_column("finance"): [1, 3],
            policy.columns.school_code: [0, 0],
            policy.stage_column("center"): [1, 1],
            policy.stage_column("gender"): [1, 1],
            policy.stage_column("graduation_status"): [0, 0],
            policy.stage_column("group"): [1, 1],
        }
    )

    filtered, mismatches = _filter_candidates_by_join_map(pool, join_map=join_map, policy=policy)

    assert len(filtered) == 2
    assert not mismatches or all(
        match.get("column") != policy.stage_column("finance") for match in mismatches
    )


def test_filter_candidates_handles_finance_iterables() -> None:
    policy = load_policy()
    join_map = {
        normalize_join_key_name(policy.stage_column("group")): 1,
        normalize_join_key_name(policy.stage_column("gender")): 1,
        normalize_join_key_name(policy.stage_column("graduation_status")): 0,
        normalize_join_key_name(policy.stage_column("center")): 1,
        normalize_join_key_name(policy.stage_column("finance")): 0,
        normalize_join_key_name(policy.columns.school_code): 0,
    }
    pool = pd.DataFrame(
        {
            "mentor_id": ["m1", "m2"],
            policy.stage_column("finance"): [(0, 1, 3), [0, 2]],
            policy.columns.school_code: [0, 0],
            policy.stage_column("center"): [1, 1],
            policy.stage_column("gender"): [1, 1],
            policy.stage_column("graduation_status"): [0, 0],
            policy.stage_column("group"): [1, 1],
        }
    )

    filtered, mismatches = _filter_candidates_by_join_map(pool, join_map=join_map, policy=policy)

    assert len(filtered) == 2
    assert not mismatches


def test_filter_candidates_allows_global_school_without_wildcard() -> None:
    policy = replace(load_policy(), school_code_empty_as_zero=False)
    join_map = {
        normalize_join_key_name(policy.stage_column("group")): 1,
        normalize_join_key_name(policy.stage_column("gender")): int(policy.gender_codes.male.value),
        normalize_join_key_name(policy.stage_column("graduation_status")): 0,
        normalize_join_key_name(policy.stage_column("center")): 1,
        normalize_join_key_name(policy.stage_column("finance")): 0,
        normalize_join_key_name(policy.columns.school_code): 555,
    }
    pool = pd.DataFrame(
        {
            "mentor_id": ["g1", "r1"],
            policy.stage_column("finance"): [0, 0],
            policy.columns.school_code: [0, 999],
            "has_school_constraint": [False, True],
            policy.stage_column("center"): [1, 1],
            policy.stage_column("gender"): [
                int(policy.gender_codes.male.value),
                int(policy.gender_codes.male.value),
            ],
            policy.stage_column("graduation_status"): [0, 0],
            policy.stage_column("group"): [1, 1],
        }
    )

    filtered, _ = _filter_candidates_by_join_map(pool, join_map=join_map, policy=policy)

    assert filtered["mentor_id"].tolist() == ["g1"]


def test_filter_candidates_respects_center_wildcard_zero_and_rejects_missing() -> None:
    policy = load_policy()
    join_map = {
        normalize_join_key_name(policy.stage_column("group")): 1,
        normalize_join_key_name(policy.stage_column("gender")): 1,
        normalize_join_key_name(policy.stage_column("graduation_status")): 0,
        normalize_join_key_name(policy.stage_column("center")): 5,
        normalize_join_key_name(policy.stage_column("finance")): 0,
        normalize_join_key_name(policy.columns.school_code): 0,
    }
    pool = pd.DataFrame(
        {
            "mentor_id": ["m1", "m2", "m3", "m4"],
            policy.stage_column("finance"): [0, 0, 0, 0],
            policy.columns.school_code: [0, 0, 0, 0],
            policy.stage_column("center"): [0, 5, pd.NA, 7],
            policy.stage_column("gender"): [1, 1, 1, 1],
            policy.stage_column("graduation_status"): [0, 0, 0, 0],
            policy.stage_column("group"): [1, 1, 1, 1],
        }
    )

    filtered, mismatches = _filter_candidates_by_join_map(pool, join_map=join_map, policy=policy)

    assert filtered[policy.stage_column("center")].tolist() == [0, 5]
    assert any(match.get("column") == policy.stage_column("center") for match in mismatches)


def test_filter_candidates_accepts_farsi_gender_tokens() -> None:
    policy = load_policy()
    join_map = {
        normalize_join_key_name(policy.stage_column("group")): 1,
        normalize_join_key_name(policy.stage_column("gender")): int(
            policy.gender_codes.female.value
        ),
        normalize_join_key_name(policy.stage_column("graduation_status")): 0,
        normalize_join_key_name(policy.stage_column("center")): 1,
        normalize_join_key_name(policy.stage_column("finance")): 0,
        normalize_join_key_name(policy.columns.school_code): 0,
    }
    pool = pd.DataFrame(
        {
            "mentor_id": ["m1", "m2"],
            policy.stage_column("finance"): [0, 0],
            policy.columns.school_code: [0, 0],
            policy.stage_column("center"): [1, 1],
            policy.stage_column("gender"): ["دختر", "پسر"],
            policy.stage_column("graduation_status"): [0, 0],
            policy.stage_column("group"): [1, 1],
        }
    )

    filtered, _ = _filter_candidates_by_join_map(pool, join_map=join_map, policy=policy)

    assert filtered["mentor_id"].tolist() == ["m1"]


def test_join_key_mismatches_preserved_on_success_allocation() -> None:
    policy = load_policy()
    student = {
        "student_id": "s1",
        policy.stage_column("group"): 1,
        policy.stage_column("gender"): 1,
        policy.stage_column("graduation_status"): 0,
        policy.stage_column("center"): 1,
        policy.stage_column("finance"): 0,
        policy.columns.school_code: 0,
    }
    pool = pd.DataFrame(
        {
            "mentor_id": ["m1", "m2"],
            policy.stage_column("group"): [1, 1],
            policy.stage_column("gender"): [1, 1],
            policy.stage_column("graduation_status"): [0, 0],
            policy.stage_column("center"): [1, 1],
            policy.stage_column("finance"): [1, 2],
            policy.columns.school_code: [0, 0],
            "remaining_capacity": [1, 1],
            "allocations_new": [0, 0],
            "occupancy_ratio": [0.0, 0.5],
        }
    )

    result = allocate_student(student, pool, policy=policy)

    assert result.log.get("allocation_status") == "success"
    assert result.log.get("join_key_mismatches")


def test_join_key_mismatches_include_prefilter_details() -> None:
    policy = load_policy()

    primary = [
        {
            "column": policy.stage_column("finance"),
            "student_value": 0,
            "mentor_values": [2],
            "reason": "mentor_value_mismatch",
        }
    ]
    secondary = [
        {
            "column": policy.stage_column("group"),
            "student_value": 1,
            "mentor_values": [0],
            "reason": "mentor_value_mismatch",
        }
    ]

    merged = _merge_join_mismatches(primary, secondary)

    assert len(merged) == 2
    assert {entry["column"] for entry in merged} == {
        policy.stage_column("finance"),
        policy.stage_column("group"),
    }


def test_apply_join_filters_finance_variants_with_join_map() -> None:
    policy = load_policy()
    student = {
        policy.stage_column("group"): 1,
        policy.stage_column("gender"): 1,
        policy.stage_column("graduation_status"): 0,
        policy.stage_column("center"): 1,
        policy.stage_column("finance"): 0,
        policy.columns.school_code: 0,
    }
    join_map = {
        normalize_join_key_name(column): int(student[column]) for column in policy.join_keys
    }
    pool = pd.DataFrame(
        {
            policy.stage_column("group"): [1, 1],
            policy.stage_column("gender"): [1, 1],
            policy.stage_column("graduation_status"): [0, 0],
            policy.stage_column("center"): [1, 1],
            policy.stage_column("finance"): [
                policy.finance_variants[1],
                policy.finance_variants[2],
            ],
            policy.columns.school_code: [0, 0],
        }
    )

    filtered = apply_join_filters(pool, student, policy=policy, student_join_map=join_map)

    assert filtered.shape[0] == 2


def test_apply_join_filters_finance_accepts_string_variants() -> None:
    policy = load_policy()
    student = {
        policy.stage_column("group"): 1,
        policy.stage_column("gender"): 1,
        policy.stage_column("graduation_status"): 0,
        policy.stage_column("center"): 1,
        policy.stage_column("finance"): "۰",
        policy.columns.school_code: 0,
    }
    join_map = {
        normalize_join_key_name(policy.stage_column("group")): 1,
        normalize_join_key_name(policy.stage_column("gender")): int(policy.gender_codes.male.value),
        normalize_join_key_name(policy.stage_column("graduation_status")): 0,
        normalize_join_key_name(policy.stage_column("center")): 1,
        normalize_join_key_name(policy.stage_column("finance")): 0,
        normalize_join_key_name(policy.columns.school_code): 0,
    }
    pool = pd.DataFrame(
        {
            policy.stage_column("group"): [1, 1],
            policy.stage_column("gender"): [1, 1],
            policy.stage_column("graduation_status"): [0, 0],
            policy.stage_column("center"): [1, 1],
            policy.stage_column("finance"): [
                policy.finance_variants[0],
                policy.finance_variants[2],
            ],
            policy.columns.school_code: [0, 0],
        }
    )

    filtered = apply_join_filters(pool, student, policy=policy, student_join_map=join_map)

    assert filtered.shape[0] == 2


def test_apply_join_filters_accepts_farsi_gender_tokens() -> None:
    policy = load_policy()
    student = {
        policy.stage_column("group"): 1,
        policy.stage_column("gender"): "پسر",
        policy.stage_column("graduation_status"): 0,
        policy.stage_column("center"): 1,
        policy.stage_column("finance"): 0,
        policy.columns.school_code: 0,
    }
    join_map = {
        normalize_join_key_name(policy.stage_column("group")): 1,
        normalize_join_key_name(policy.stage_column("gender")): int(policy.gender_codes.male.value),
        normalize_join_key_name(policy.stage_column("graduation_status")): 0,
        normalize_join_key_name(policy.stage_column("center")): 1,
        normalize_join_key_name(policy.stage_column("finance")): 0,
        normalize_join_key_name(policy.columns.school_code): 0,
    }
    pool = pd.DataFrame(
        {
            policy.stage_column("group"): [1],
            policy.stage_column("gender"): [int(policy.gender_codes.male.value)],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [1],
            policy.stage_column("finance"): [policy.finance_variants[0]],
            policy.columns.school_code: [0],
        }
    )

    filtered = apply_join_filters(pool, student, policy=policy, student_join_map=join_map)

    assert filtered.shape[0] == 1


def test_detect_pool_mismatch_center_subset_alignment() -> None:
    candidate_pool = pd.DataFrame({"mentor_id": ["m1", "m2"]}).set_index(pd.Index([5, 7]))
    pool_state_view = pd.DataFrame({"mentor_id": ["m1", "m2"]}).set_index(pd.Index([5, 7]))

    mismatch = _detect_pool_mismatch(
        candidate_pool=candidate_pool,
        pool_view=candidate_pool,
        pool_state_view=pool_state_view,
    )

    assert not mismatch


def test_allocate_student_finance_variants_success() -> None:
    policy = load_policy()
    student = {
        "student_id": "s2",
        policy.stage_column("group"): 1,
        policy.stage_column("gender"): 0,
        policy.stage_column("graduation_status"): 0,
        policy.stage_column("center"): 1,
        policy.stage_column("finance"): 0,
        policy.columns.school_code: 123,
    }
    pool = pd.DataFrame(
        {
            "mentor_id": ["m1", "m2"],
            policy.stage_column("group"): [1, 1],
            policy.stage_column("gender"): [0, 0],
            policy.stage_column("graduation_status"): [0, 0],
            policy.stage_column("center"): [1, 1],
            policy.stage_column("finance"): [
                policy.finance_variants[0],
                policy.finance_variants[1],
            ],
            policy.columns.school_code: [123, 123],
            "remaining_capacity": [1, 1],
            "allocations_new": [0, 0],
            "occupancy_ratio": [0.1, 0.2],
        }
    )

    result = allocate_student(student, pool, policy=policy)

    assert result.log.get("allocation_status") == "success"
    assert result.log.get("mentor_id") == "m1"

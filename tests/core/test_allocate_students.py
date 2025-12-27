from __future__ import annotations

from dataclasses import replace

import pandas as pd

from app.core.allocate_students import (
    _collect_join_key_map,
    _detect_pool_mismatch,
    _filter_candidates_by_join_map,
    _merge_join_mismatches,
    allocate_batch,
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


def test_collect_join_key_map_marks_missing_none_values() -> None:
    policy = load_policy()
    student = {
        policy.stage_column("group"): 1,
        policy.stage_column("gender"): None,
        policy.stage_column("graduation_status"): 0,
        policy.stage_column("center"): 1,
        policy.stage_column("finance"): 0,
        policy.columns.school_code: 10,
    }

    join_map, missing = _collect_join_key_map(student, policy)

    assert policy.stage_column("gender") in missing
    assert join_map[normalize_join_key_name(policy.stage_column("gender"))] == -1


def test_allocate_student_returns_data_missing_for_blank_join_key() -> None:
    policy = load_policy()
    student = {
        "student_id": "s-1",
        policy.stage_column("group"): " ",
        policy.stage_column("gender"): 1,
        policy.stage_column("graduation_status"): 0,
        policy.stage_column("center"): 1,
        policy.stage_column("finance"): 0,
        policy.columns.school_code: 10,
    }
    candidate_pool = pd.DataFrame(
        {
            "mentor_id": ["m1"],
            policy.stage_column("group"): [1],
            policy.stage_column("gender"): [1],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [1],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [10],
            policy.columns.remaining_capacity: [1],
        }
    )

    result = allocate_student(student, candidate_pool, policy=policy)

    assert result.mentor_row is None
    assert result.log.get("error_type") == "DATA_MISSING"
    assert "Missing student join key data" in str(result.log.get("detailed_reason"))


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


def test_filter_candidates_respects_school_constraints_without_excluding_matches() -> None:
    policy = load_policy()
    join_map = {
        normalize_join_key_name(policy.stage_column("group")): 1,
        normalize_join_key_name(policy.stage_column("gender")): int(policy.gender_codes.male.value),
        normalize_join_key_name(policy.stage_column("graduation_status")): 0,
        normalize_join_key_name(policy.stage_column("center")): 1,
        normalize_join_key_name(policy.stage_column("finance")): 0,
        normalize_join_key_name(policy.columns.school_code): 777,
    }
    pool = pd.DataFrame(
        {
            "mentor_id": ["global", "restricted"],
            policy.stage_column("finance"): [0, 0],
            policy.columns.school_code: [0, 777],
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

    assert filtered["mentor_id"].tolist() == ["global", "restricted"]


def test_allocate_batch_outputs_match_counters() -> None:
    policy = load_policy()
    students = pd.DataFrame(
        {
            policy.stage_column("group"): [1],
            policy.stage_column("gender"): [int(policy.gender_codes.male.value)],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [1],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [0],
            "student_id": ["1"],
        }
    )

    pool = pd.DataFrame(
        {
            "mentor_id": ["m1"],
            "mentor_alias_code": [111],
            "mentor_name": ["mentor m1"],
            policy.stage_column("group"): [1],
            policy.stage_column("gender"): [int(policy.gender_codes.male.value)],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [1],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [0],
            policy.columns.remaining_capacity: [1],
            "کد کارمندی پشتیبان": ["m1"],
            "allocations_new": [0],
            "occupancy_ratio": [0.0],
        }
    )

    result = allocate_batch(students, pool, policy=policy, frames_already_canonical=True)
    allocations_df, updated_pool_df, logs_df, trace_df = result

    assert len(allocations_df) == 1
    assert not updated_pool_df.empty
    assert not logs_df.empty
    assert not trace_df.empty


def test_allocate_batch_zero_capacity_produces_no_allocations() -> None:
    policy = load_policy()
    students = pd.DataFrame(
        {
            policy.stage_column("group"): [1],
            policy.stage_column("gender"): [int(policy.gender_codes.male.value)],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [1],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [0],
            "student_id": ["1"],
        }
    )

    pool = pd.DataFrame(
        {
            "mentor_id": ["m1"],
            "mentor_alias_code": [111],
            "mentor_name": ["mentor m1"],
            policy.stage_column("group"): [1],
            policy.stage_column("gender"): [int(policy.gender_codes.male.value)],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [1],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [0],
            policy.columns.remaining_capacity: [0],
            "کد کارمندی پشتیبان": ["m1"],
            "allocations_new": [0],
            "occupancy_ratio": [0.0],
        }
    )

    result = allocate_batch(students, pool, policy=policy, frames_already_canonical=True)
    allocations_df, updated_pool_df, logs_df, trace_df = result

    assert allocations_df.empty
    assert logs_df.empty or len(logs_df) == 1

    summary_df = result.trace_extras.summary_df
    assert summary_df is not None
    assert len(summary_df) == 1
    assert summary_df.iloc[0]["final_status"] == "NO_CAPACITY"


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


def test_filter_candidates_respects_policy_wildcard_value_for_mentor_centers() -> None:
    policy = load_policy()
    policy.center_map["*"] = 99
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
            "mentor_id": ["wildcard", "exact", "global"],
            policy.stage_column("finance"): [0, 0, 0],
            policy.columns.school_code: [0, 0, 0],
            policy.stage_column("center"): [99, 5, 0],
            policy.stage_column("gender"): [1, 1, 1],
            policy.stage_column("graduation_status"): [0, 0, 0],
            policy.stage_column("group"): [1, 1, 1],
        }
    )

    filtered, _ = _filter_candidates_by_join_map(pool, join_map=join_map, policy=policy)

    assert filtered["mentor_id"].tolist() == ["wildcard", "exact", "global"]


def test_filter_candidates_accepts_student_center_wildcard_value() -> None:
    policy = load_policy()
    policy.center_map["*"] = 42
    join_map = {
        normalize_join_key_name(policy.stage_column("group")): 1,
        normalize_join_key_name(policy.stage_column("gender")): 1,
        normalize_join_key_name(policy.stage_column("graduation_status")): 0,
        normalize_join_key_name(policy.stage_column("center")): 42,
        normalize_join_key_name(policy.stage_column("finance")): 0,
        normalize_join_key_name(policy.columns.school_code): 0,
    }
    pool = pd.DataFrame(
        {
            "mentor_id": ["c1", "c2", "wildcard"],
            policy.stage_column("finance"): [0, 0, 0],
            policy.columns.school_code: [0, 0, 0],
            policy.stage_column("center"): [1, 2, 42],
            policy.stage_column("gender"): [1, 1, 1],
            policy.stage_column("graduation_status"): [0, 0, 0],
            policy.stage_column("group"): [1, 1, 1],
        }
    )

    filtered, _ = _filter_candidates_by_join_map(pool, join_map=join_map, policy=policy)

    assert filtered["mentor_id"].tolist() == ["wildcard"]


def test_filter_candidates_treats_student_center_zero_as_wildcard_without_policy_code() -> None:
    policy = replace(load_policy(), center_map={})
    join_map = {
        normalize_join_key_name(policy.stage_column("group")): 1,
        normalize_join_key_name(policy.stage_column("gender")): 1,
        normalize_join_key_name(policy.stage_column("graduation_status")): 0,
        normalize_join_key_name(policy.stage_column("center")): 0,
        normalize_join_key_name(policy.stage_column("finance")): 0,
        normalize_join_key_name(policy.columns.school_code): 0,
    }
    pool = pd.DataFrame(
        {
            "mentor_id": ["c1", "c2", "c3"],
            policy.stage_column("finance"): [0, 0, 0],
            policy.columns.school_code: [0, 0, 0],
            policy.stage_column("center"): [1, 2, 0],
            policy.stage_column("gender"): [1, 1, 1],
            policy.stage_column("graduation_status"): [0, 0, 0],
            policy.stage_column("group"): [1, 1, 1],
        }
    )

    filtered, mismatches = _filter_candidates_by_join_map(pool, join_map=join_map, policy=policy)

    assert filtered["mentor_id"].tolist() == ["c3"]
    assert {
        "column": policy.stage_column("center"),
        "reason": "mentor_value_mismatch",
        "student_value": 0,
        "mentor_values": [1, 2],
    } in mismatches


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
            "mentor_id": ["m_match", "m_other"],
            policy.stage_column("group"): [1, 1],
            policy.stage_column("gender"): [1, 1],
            policy.stage_column("graduation_status"): [0, 0],
            policy.stage_column("center"): [1, 2],
            policy.stage_column("finance"): [0, 0],
            policy.columns.school_code: [0, 0],
            "remaining_capacity": [1, 1],
            "allocations_new": [0, 0],
            "occupancy_ratio": [0.0, 0.0],
        }
    )

    result = allocate_student(student, pool, policy=policy, debug_trace=True)

    assert result.log.get("allocation_status") == "success"
    assert result.log.get("mentor_id") == "m_match"
    assert result.log.get("join_key_mismatches") == [
        {
            "column": policy.stage_column("center"),
            "student_value": 1,
            "mentor_values": [2],
            "reason": "mentor_value_mismatch",
        }
    ]


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
    assert merged == [
        {
            "column": policy.stage_column("finance"),
            "mentor_values": [2],
            "reason": "mentor_value_mismatch",
            "student_value": 0,
        },
        {
            "column": policy.stage_column("group"),
            "mentor_values": [0],
            "reason": "mentor_value_mismatch",
            "student_value": 1,
        },
    ]


def test_merge_join_mismatches_deduplicates_and_sorts() -> None:
    policy = load_policy()
    primary = [
        {
            "column": policy.stage_column("center"),
            "student_value": 1,
            "mentor_values": [2, 2],
            "reason": "mentor_value_mismatch",
        }
    ]
    secondary = [
        {
            "column": policy.stage_column("center"),
            "student_value": 1,
            "mentor_values": [2],
            "reason": "mentor_value_mismatch",
        },
        {
            "column": policy.stage_column("finance"),
            "student_value": 0,
            "mentor_values": [3, 2],
            "reason": "mentor_value_mismatch",
        },
    ]

    merged = _merge_join_mismatches(primary, secondary)

    assert merged == [
        {
            "column": policy.stage_column("finance"),
            "mentor_values": [2, 3],
            "reason": "mentor_value_mismatch",
            "student_value": 0,
        },
        {
            "column": policy.stage_column("center"),
            "mentor_values": [2],
            "reason": "mentor_value_mismatch",
            "student_value": 1,
        },
    ]


def test_join_key_mismatches_merge_combines_prefilter_and_eligibility_details() -> None:
    policy = load_policy()
    student = {
        "student_id": "s-merge",
        policy.stage_column("group"): 1,
        policy.stage_column("gender"): 1,
        policy.stage_column("graduation_status"): 0,
        policy.stage_column("center"): 1,
        policy.stage_column("finance"): 0,
        policy.columns.school_code: 0,
    }
    candidate_pool = pd.DataFrame(
        {
            "mentor_id": ["m_center_mismatch", "m_finance_mismatch", "m_match"],
            policy.stage_column("group"): [1, 1, 1],
            policy.stage_column("gender"): [1, 1, 1],
            policy.stage_column("graduation_status"): [0, 0, 0],
            policy.stage_column("center"): [2, 1, 1],
            policy.stage_column("finance"): [0, 2, 0],
            policy.columns.school_code: [0, 0, 0],
            "remaining_capacity": [1, 1, 1],
            "allocations_new": [0, 0, 0],
            "occupancy_ratio": [0.0, 0.0, 0.0],
        }
    )

    result = allocate_student(student, candidate_pool, policy=policy, debug_trace=True)

    assert result.log.get("allocation_status") == "success"
    assert result.log.get("mentor_id") == "m_match"
    assert result.log.get("join_key_mismatches") == [
        {
            "column": policy.stage_column("finance"),
            "student_value": 0,
            "mentor_values": [1],
            "reason": "mentor_value_mismatch",
        },
        {
            "column": policy.stage_column("center"),
            "student_value": 1,
            "mentor_values": [2],
            "reason": "mentor_value_mismatch",
        },
    ]


def test_join_key_mismatches_recorded_when_unallocated() -> None:
    policy = load_policy()
    student = {
        "student_id": "s-unalloc",
        policy.stage_column("group"): 1,
        policy.stage_column("gender"): 1,
        policy.stage_column("graduation_status"): 0,
        policy.stage_column("center"): 1,
        policy.stage_column("finance"): 0,
        policy.columns.school_code: 0,
    }
    candidate_pool = pd.DataFrame(
        {
            "mentor_id": ["m_finance", "m_center"],
            policy.stage_column("group"): [1, 1],
            policy.stage_column("gender"): [1, 1],
            policy.stage_column("graduation_status"): [0, 0],
            policy.stage_column("center"): [2, 3],
            policy.stage_column("finance"): [3, 4],
            policy.columns.school_code: [0, 0],
            "remaining_capacity": [1, 1],
            "allocations_new": [0, 0],
            "occupancy_ratio": [0.0, 0.0],
        }
    )

    result = allocate_student(student, candidate_pool, policy=policy)

    assert result.log.get("allocation_status") == "failed"
    assert result.log.get("join_key_mismatches") == [
        {
            "column": policy.stage_column("finance"),
            "student_value": 0,
            "mentor_values": [3],
            "reason": "mentor_value_mismatch",
        },
        {
            "column": policy.stage_column("center"),
            "student_value": 1,
            "mentor_values": [2, 3],
            "reason": "mentor_value_mismatch",
        },
    ]


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

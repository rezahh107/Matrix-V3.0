from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

import pandas as pd
import pytest

from app.core.canonical_frames import canonicalize_pool_frame, canonicalize_students_frame
from app.core.common.join_keys import (
    JoinKeyCanonicalizationError,
    canonicalize_join_key_value,
    coerce_join_int,
    matches_center_with_wildcard,
    normalize_join_key_name,
    resolve_finance_variants,
    validate_policy_join_keys,
)
from app.core.policy_loader import PolicyConfig, load_policy


def test_validate_policy_join_keys_handles_farsi_gender_string() -> None:
    policy = load_policy()
    join_map = {normalize_join_key_name(column): 1 for column in policy.join_keys}
    join_map[normalize_join_key_name(policy.stage_column("gender"))] = int(
        policy.gender_codes.male.value
    )
    mentor_row: dict[str, object] = {column: 1 for column in policy.join_keys}
    mentor_row[policy.stage_column("gender")] = "پسر"

    valid, mismatches = validate_policy_join_keys(mentor_row, join_map, policy)

    assert valid
    assert mismatches == []


def test_canonicalize_join_key_value_accepts_gender_tokens() -> None:
    policy = load_policy()

    female_value = canonicalize_join_key_value(policy.stage_column("gender"), "دختر", policy=policy)
    numeric_value = canonicalize_join_key_value(policy.stage_column("gender"), 1, policy=policy)

    assert female_value == int(policy.gender_codes.female.value)
    assert numeric_value == int(policy.gender_codes.male.value)


def test_canonicalize_join_key_value_rejects_unknown_gender_tokens() -> None:
    policy = load_policy()

    with pytest.raises(JoinKeyCanonicalizationError):
        canonicalize_join_key_value(policy.stage_column("gender"), "نامعتبر", policy=policy)


def test_validate_policy_join_keys_finance_variants() -> None:
    policy = load_policy()
    finance_column = policy.stage_column("finance")
    join_map = {normalize_join_key_name(column): 1 for column in policy.join_keys}
    join_map[normalize_join_key_name(finance_column)] = 0

    mentor_row_variant = {
        column: join_map.get(normalize_join_key_name(column), 0) for column in policy.join_keys
    }
    mentor_row_variant[finance_column] = policy.finance_variants[1]

    valid_variant, mismatches_variant = validate_policy_join_keys(
        mentor_row_variant, join_map, policy
    )

    mentor_row_outside = mentor_row_variant.copy()
    mentor_row_outside[finance_column] = 9

    valid_outside, mismatches_outside = validate_policy_join_keys(
        mentor_row_outside, join_map, policy
    )

    assert valid_variant
    assert mismatches_variant == []
    assert not valid_outside
    assert any(item.get("column") == finance_column for item in mismatches_outside)


def test_validate_policy_join_keys_finance_iterable_cells() -> None:
    policy = load_policy()
    finance_column = policy.stage_column("finance")
    join_map = {normalize_join_key_name(column): 1 for column in policy.join_keys}
    join_map[normalize_join_key_name(finance_column)] = 0

    mentor_row: dict[str, object] = {
        column: join_map.get(normalize_join_key_name(column), 0) for column in policy.join_keys
    }
    mentor_row[finance_column] = (0, 1, 3)

    valid, mismatches = validate_policy_join_keys(mentor_row, join_map, policy)

    assert valid
    assert mismatches == []


def test_validate_policy_join_keys_finance_list_clusters() -> None:
    base_policy = load_policy()
    policy: PolicyConfig = replace(
        base_policy,
        finance_variants=cast(Any, [[0, 1, 3], [4, 5]]),
    )
    finance_column = policy.stage_column("finance")
    join_map = {normalize_join_key_name(column): 1 for column in policy.join_keys}
    join_map[normalize_join_key_name(finance_column)] = 0

    mentor_row: dict[str, object] = {
        column: join_map.get(normalize_join_key_name(column), 0) for column in policy.join_keys
    }
    mentor_row[finance_column] = 3

    valid, mismatches = validate_policy_join_keys(mentor_row, join_map, policy)

    assert valid
    assert mismatches == []


def test_validate_policy_join_keys_allows_global_center() -> None:
    policy = load_policy()
    join_map = {normalize_join_key_name(column): 1 for column in policy.join_keys}
    join_map[normalize_join_key_name(policy.stage_column("center"))] = 5
    mentor_row = {column: join_map[normalize_join_key_name(column)] for column in policy.join_keys}
    mentor_row[policy.stage_column("center")] = 0

    valid, mismatches = validate_policy_join_keys(mentor_row, join_map, policy)

    assert valid
    assert mismatches == []


def test_canonicalize_center_missing_rejected() -> None:
    policy = load_policy()

    with pytest.raises(JoinKeyCanonicalizationError):
        canonicalize_join_key_value(policy.stage_column("center"), "", policy=policy)


def test_canonicalize_center_na_rejected() -> None:
    policy = load_policy()

    with pytest.raises(JoinKeyCanonicalizationError):
        canonicalize_join_key_value(policy.stage_column("center"), pd.NA, policy=policy)


def test_matches_center_with_wildcard_requires_mentor_side_global_or_match() -> None:
    policy = load_policy()
    wildcard = policy.center_map.get("*")

    assert matches_center_with_wildcard(5, 0, wildcard)
    assert not matches_center_with_wildcard(0, 2, None)
    assert not matches_center_with_wildcard(3, 4, wildcard)


def test_validate_policy_join_keys_flags_missing_center() -> None:
    policy = load_policy()
    join_map = {normalize_join_key_name(column): 1 for column in policy.join_keys}
    join_map[normalize_join_key_name(policy.stage_column("center"))] = 2
    mentor_row = {column: join_map[normalize_join_key_name(column)] for column in policy.join_keys}
    mentor_row[policy.stage_column("center")] = pd.NA

    valid, mismatches = validate_policy_join_keys(mentor_row, join_map, policy)

    assert not valid
    assert any(match["column"] == policy.stage_column("center") for match in mismatches)


def test_validate_policy_join_keys_detects_mismatching_center() -> None:
    policy = load_policy()
    join_map = {normalize_join_key_name(column): 1 for column in policy.join_keys}
    join_map[normalize_join_key_name(policy.stage_column("center"))] = 3
    mentor_row = {column: join_map[normalize_join_key_name(column)] for column in policy.join_keys}
    mentor_row[policy.stage_column("center")] = 7

    valid, mismatches = validate_policy_join_keys(mentor_row, join_map, policy)

    assert not valid
    assert any(match["column"] == policy.stage_column("center") for match in mismatches)


def test_resolve_finance_variants_expands_policy_values() -> None:
    policy = load_policy()
    variants = resolve_finance_variants(policy.finance_variants[0], policy)

    assert variants.issuperset(set(policy.finance_variants))


def test_matches_center_with_wildcard_rejects_student_side_global_with_policy_wildcard() -> None:
    policy = load_policy()
    wildcard = policy.center_map.get("*")

    assert wildcard is not None
    assert matches_center_with_wildcard(5, 0, wildcard)
    assert not matches_center_with_wildcard(0, 5, wildcard)


def test_resolve_finance_variants_unknown_falls_back() -> None:
    policy = load_policy()
    variants = resolve_finance_variants(999, policy)

    assert variants == frozenset({999})


def test_resolve_finance_variants_supports_mapping_policy_definition() -> None:
    policy = load_policy()
    mapping_policy: PolicyConfig = replace(
        policy,
        finance_variants=cast(
            Any,
            {
                "0": ["0", "1", "۳"],
                2: (2,),
            },
        ),
    )

    expanded_zero = resolve_finance_variants(0, mapping_policy)
    expanded_three = resolve_finance_variants(3, mapping_policy)
    unrelated = resolve_finance_variants(7, mapping_policy)

    assert expanded_zero == frozenset({0, 1, 3})
    assert expanded_three == frozenset({0, 1, 3})
    assert unrelated == frozenset({7})


def test_resolve_finance_variants_supports_sequence_clusters() -> None:
    policy = load_policy()
    cluster_policy: PolicyConfig = replace(
        policy,
        finance_variants=cast(Any, (("۰", "1", 3), ("۴", 5))),
    )

    expanded_one = resolve_finance_variants(1, cluster_policy)
    expanded_three = resolve_finance_variants(coerce_join_int("۳"), cluster_policy)
    expanded_four = resolve_finance_variants(4, cluster_policy)
    unknown = resolve_finance_variants(9, cluster_policy)

    assert expanded_one == frozenset({0, 1, 3})
    assert expanded_three == frozenset({0, 1, 3})
    assert expanded_four == frozenset({4, 5})
    assert unknown == frozenset({9})


def test_canonicalize_gender_farsi_tokens() -> None:
    policy = load_policy()
    male = canonicalize_join_key_value(policy.stage_column("gender"), "پسر", policy=policy)
    female = canonicalize_join_key_value(policy.stage_column("gender"), "دختر", policy=policy)

    assert male == int(policy.gender_codes.male.value)
    assert female == int(policy.gender_codes.female.value)


def test_canonicalize_join_key_value_localized_digits_and_iterables() -> None:
    policy = load_policy()
    finance_column = policy.stage_column("finance")

    localized = canonicalize_join_key_value(finance_column, "۱۲۳", policy=policy)
    iterable_first = canonicalize_join_key_value(finance_column, ["۲", "3"], policy=policy)

    assert localized == 123
    assert iterable_first == 2


def test_canonicalize_join_key_value_school_wildcard_policy_driven() -> None:
    base_policy = load_policy()
    school_column = base_policy.columns.school_code

    wildcard_value = canonicalize_join_key_value(school_column, "", policy=base_policy)

    strict_policy: PolicyConfig = replace(base_policy, school_code_empty_as_zero=False)
    with pytest.raises(JoinKeyCanonicalizationError):
        canonicalize_join_key_value(school_column, "", policy=strict_policy)

    assert wildcard_value == 0


def test_canonical_frames_enforce_canon01_join_key_ints() -> None:
    policy = load_policy()
    students = pd.DataFrame(
        {
            "student_id": ["s1"],
            policy.stage_column("group"): ["۹۱۰۰"],
            policy.stage_column("gender"): ["پسر"],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): ["۰"],
            policy.stage_column("finance"): [["۱", "0"]],
            policy.columns.school_code: [""],
        }
    )
    pool = pd.DataFrame(
        {
            policy.stage_column("group"): ["۹۱۰۰"],
            policy.stage_column("gender"): ["دختر"],
            policy.stage_column("graduation_status"): ["0"],
            policy.stage_column("center"): [0],
            policy.stage_column("finance"): ["۱"],
            policy.columns.school_code: [0],
            "کد کارمندی پشتیبان": ["m1"],
            "remaining_capacity": [1],
        }
    )

    canonical_students = canonicalize_students_frame(students, policy=policy)
    canonical_pool = canonicalize_pool_frame(pool, policy=policy)

    for column in policy.join_keys:
        assert pd.api.types.is_integer_dtype(canonical_students[column])
        assert pd.api.types.is_integer_dtype(canonical_pool[column])
        assert canonical_students[column].isna().sum() == 0
        assert canonical_pool[column].isna().sum() == 0

from __future__ import annotations

import pytest

from app.core.common.join_keys import (
    JoinKeyCanonicalizationError,
    canonicalize_join_key_value,
    normalize_join_key_name,
    validate_policy_join_keys,
)
from app.core.policy_loader import load_policy


def test_validate_policy_join_keys_handles_farsi_gender_string() -> None:
    policy = load_policy()
    join_map = {normalize_join_key_name(column): 1 for column in policy.join_keys}
    join_map[normalize_join_key_name(policy.stage_column("gender"))] = int(
        policy.gender_codes.male.value
    )
    mentor_row = {column: 1 for column in policy.join_keys}
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

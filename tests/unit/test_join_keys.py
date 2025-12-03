import pytest

from app.core.common.join_keys import (
    JoinKeyCanonicalizationError,
    canonicalize_join_key_value,
    coerce_join_int,
)
from app.core.policy_loader import load_policy


def test_canonicalize_join_key_value_maps_farsi_gender_tokens() -> None:
    policy = load_policy()
    gender_column = policy.stage_column("gender")

    male_code = canonicalize_join_key_value(gender_column, "پسر", policy=policy)
    female_code = canonicalize_join_key_value(gender_column, "دختر", policy=policy)

    assert male_code == policy.gender_codes.male.value
    assert female_code == policy.gender_codes.female.value


@pytest.mark.parametrize("value", [1, "1"])
def test_canonicalize_join_key_value_accepts_numeric_gender(value: object) -> None:
    policy = load_policy()
    gender_column = policy.stage_column("gender")

    assert (
        canonicalize_join_key_value(gender_column, value, policy=policy)
        == policy.gender_codes.male.value
    )


def test_canonicalize_join_key_value_rejects_unknown_gender_token() -> None:
    policy = load_policy()
    gender_column = policy.stage_column("gender")

    with pytest.raises(JoinKeyCanonicalizationError):
        canonicalize_join_key_value(gender_column, "نامعتبر", policy=policy)


def test_canonicalize_join_key_value_accepts_localized_digits_for_numeric_keys() -> None:
    policy = load_policy()
    center_column = policy.stage_column("center")

    assert canonicalize_join_key_value(center_column, "۱۲۳۴", policy=policy) == 1234


def test_canonicalize_join_key_value_rejects_non_numeric_for_numeric_keys() -> None:
    policy = load_policy()
    center_column = policy.stage_column("center")

    with pytest.raises(JoinKeyCanonicalizationError):
        canonicalize_join_key_value(center_column, "گروه", policy=policy)


@pytest.mark.parametrize("text, expected", [("۱۲۳", 123), ("7", 7)])
def test_coerce_join_int_accepts_digit_strings(text: str, expected: int) -> None:
    assert coerce_join_int(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("1\u200c2\u200d3", 123),
        ("1 2 3", 123),
    ],
)
def test_coerce_join_int_strips_hidden_and_whitespace(text: str, expected: int) -> None:
    assert coerce_join_int(text) == expected


def test_coerce_join_int_rejects_non_numeric_strings() -> None:
    with pytest.raises(ValueError):
        coerce_join_int("پسر")


def test_coerce_join_int_rejects_empty_after_cleaning() -> None:
    with pytest.raises(ValueError):
        coerce_join_int(" \u200c ")

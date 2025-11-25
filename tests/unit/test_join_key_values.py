import pytest

from app.core.common.types import JoinKeyValues


def test_from_policy_accepts_string_numbers() -> None:
    join_keys = ("a", "b", "c", "d", "e", "f")
    payload = {key: str(index) for index, key in enumerate(join_keys)}

    result = JoinKeyValues.from_policy(payload, join_keys)

    assert list(result.items()) == [(key, int(value)) for key, value in payload.items()]


def test_from_policy_accepts_int_zero_values() -> None:
    join_keys = ("a", "b", "c", "d", "e", "f")
    payload = {key: index for index, key in enumerate(join_keys)}

    result = JoinKeyValues.from_policy(payload, join_keys)

    assert list(result.items()) == [(key, value) for key, value in payload.items()]


def test_from_policy_missing_key_raises_value_error() -> None:
    join_keys = ("a", "b", "c", "d", "e", "f")
    payload = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}

    with pytest.raises(ValueError):
        JoinKeyValues.from_policy(payload, join_keys)


def test_from_policy_invalid_value_raises_type_error() -> None:
    join_keys = ("a", "b", "c", "d", "e", "f")
    payload = {key: str(index) for index, key in enumerate(join_keys)}
    payload["c"] = "invalid"

    with pytest.raises(TypeError) as excinfo:
        JoinKeyValues.from_policy(payload, join_keys)

    assert "Join key 'c' must be int-convertible" in str(excinfo.value)

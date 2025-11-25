import pytest

from app.core.common.types import JoinKeyValues, natural_key


@pytest.fixture
def sample_keys_data() -> dict[str, int]:
    return {
        "کدرشته": 1,
        "جنسیت": 1,
        "دانش_آموز_فارغ": 0,
        "مرکز_گلستان_صدرا": 1,
        "مالی_حکمت_بنیاد": 0,
        "کد_مدرسه": 10,
    }


def test_natural_key_orders_numbers_before_text():
    assert natural_key("EMP-2") < natural_key("EMP-10")


def test_natural_key_handles_mixed_tokens_stably():
    ids = ["M-10", "M-02", "M-1"]
    assert sorted(ids, key=natural_key) == ["M-1", "M-02", "M-10"]
    assert natural_key("08") < natural_key("9A")
    assert natural_key(" ") == ("",)


def test_join_key_values_requires_six_entries(sample_keys_data: dict[str, int]):
    keys = JoinKeyValues(sample_keys_data)
    assert keys["کد_مدرسه"] == 10
    assert tuple(keys.keys()) == tuple(sample_keys_data.keys())
    assert tuple(keys.items()) == tuple(sample_keys_data.items())


def test_join_key_values_int_enforcement(sample_keys_data: dict[str, int]):
    bad_data = {**sample_keys_data, "کد_مدرسه": "10"}
    with pytest.raises(TypeError):
        JoinKeyValues(bad_data)

    bad_data_float = {**sample_keys_data, "کد_مدرسه": 10.0}
    with pytest.raises(TypeError):
        JoinKeyValues(bad_data_float)


def test_join_key_values_expected_keys_validation(sample_keys_data: dict[str, int]):
    expected = tuple(sample_keys_data.keys())
    keys = JoinKeyValues(sample_keys_data, expected_keys=expected)
    assert tuple(keys) == expected

    missing_expected = expected[:-1] + ("گروه_آزمایشی",)
    with pytest.raises(ValueError):
        JoinKeyValues(sample_keys_data, expected_keys=missing_expected)

    extra_expected = expected + ("اضافی",)
    with pytest.raises(ValueError):
        JoinKeyValues(sample_keys_data, expected_keys=extra_expected)

    reordered_expected = (expected[-1],) + expected[:-1]
    with pytest.raises(ValueError):
        JoinKeyValues(sample_keys_data, expected_keys=reordered_expected)


def test_join_key_values_iteration_and_views(sample_keys_data: dict[str, int]):
    keys = JoinKeyValues(sample_keys_data)
    assert list(iter(keys)) == list(sample_keys_data.keys())
    assert list(keys.keys()) == list(sample_keys_data.keys())
    assert list(keys.values()) == list(sample_keys_data.values())
    assert ("کدرشته" in keys) is True
    assert (123 in keys) is False


def test_join_key_values_immutability_guards(sample_keys_data: dict[str, int]):
    keys = JoinKeyValues(sample_keys_data)
    with pytest.raises(AttributeError):
        keys._items = tuple()  # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        keys._mapping = {}  # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        keys.new_attr = 1  # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        keys._mapping["کدرشته"] = 2  # type: ignore[index]
    with pytest.raises(TypeError):
        keys._items[0] = ("کدرشته", 2)  # type: ignore[index]

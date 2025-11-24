from collections.abc import ItemsView, ValuesView

import pytest

from app.core.common.types import JoinKeyValues


JOIN_KEYS = (
    "کدرشته",
    "جنسیت",
    "دانش_آموز_فارغ",
    "مرکز_گلستان_صدرا",
    "مالی_حکمت_بنیاد",
    "کد_مدرسه",
)


def _sample_payload() -> dict[str, int]:
    return {
        "کدرشته": 11,
        "جنسیت": 1,
        "دانش_آموز_فارغ": 0,
        "مرکز_گلستان_صدرا": 2,
        "مالی_حکمت_بنیاد": 0,
        "کد_مدرسه": 401,
    }


def test_join_key_values_items_and_values_views_preserve_order() -> None:
    payload = _sample_payload()

    values = JoinKeyValues(payload, expected_keys=JOIN_KEYS)

    items_view = values.items()
    values_view = values.values()

    assert isinstance(items_view, ItemsView)
    assert isinstance(values_view, ValuesView)
    assert list(items_view) == list(payload.items())
    assert list(values_view) == [payload[key] for key in JOIN_KEYS]


def test_join_key_values_enforces_six_numeric_entries() -> None:
    with pytest.raises(ValueError):
        JoinKeyValues({"کدرشته": 1}, expected_keys=("کدرشته",))

    with pytest.raises(TypeError):
        JoinKeyValues({
            "کدرشته": "not-int",
            "جنسیت": 1,
            "دانش_آموز_فارغ": 0,
            "مرکز_گلستان_صدرا": 2,
            "مالی_حکمت_بنیاد": 0,
            "کد_مدرسه": 401,
        })

    with pytest.raises(ValueError):
        JoinKeyValues({**_sample_payload(), "اضافی": 7})


def test_join_key_values_behaves_like_mapping() -> None:
    payload = _sample_payload()
    values = JoinKeyValues(payload, expected_keys=JOIN_KEYS)

    assert len(values) == len(JOIN_KEYS) == 6
    assert list(iter(values)) == list(JOIN_KEYS)
    assert "کدرشته" in values
    assert "ناموجود" not in values
    assert values["کد_مدرسه"] == payload["کد_مدرسه"]
    assert list(values.keys()) == list(JOIN_KEYS)

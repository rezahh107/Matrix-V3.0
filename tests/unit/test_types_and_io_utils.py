import warnings

import pandas as pd
import pytest

from app.core.common.types import JoinKeyValues, natural_key
from app.infra.io_utils import _coalesce_duplicate_columns

CANONICAL_JOIN_KEYS = [
    "کدرشته",
    "جنسیت",
    "دانش_آموز_فارغ",
    "مرکز_گلستان_صدرا",
    "مالی_حکمت_بنیاد",
    "کد_مدرسه",
]


def test_join_key_values_from_policy_enforces_order_and_int_cast():
    payload = {key: str(index) for index, key in enumerate(CANONICAL_JOIN_KEYS, start=1)}
    join_keys = JoinKeyValues.from_policy(payload, CANONICAL_JOIN_KEYS)
    assert list(join_keys.keys()) == CANONICAL_JOIN_KEYS
    assert list(join_keys.values()) == [1, 2, 3, 4, 5, 6]


def test_join_key_values_from_policy_missing_key_raises():
    payload = {"کدرشته": 1}
    with pytest.raises(ValueError):
        JoinKeyValues.from_policy(payload, CANONICAL_JOIN_KEYS)


def test_join_key_values_normalizes_aliases_and_preserves_order() -> None:
    alias_payload = {
        "group_code": 11,
        "gender": 22,
        "graduation_status": 33,
        "center": 44,
        "finance": 55,
        "school_code": 66,
    }

    expected_order = list(CANONICAL_JOIN_KEYS)
    join_keys = JoinKeyValues(alias_payload, expected_keys=alias_payload.keys())

    assert list(join_keys.keys()) == expected_order
    assert tuple(join_keys.items()) == tuple(zip(expected_order, [11, 22, 33, 44, 55, 66]))
    assert join_keys["کدرشته"] == 11
    assert join_keys["gender"] == 22
    assert all(isinstance(value, int) for value in join_keys.values())


def test_natural_key_orders_strings_naturally():
    assert natural_key("EMP-2") < natural_key("EMP-10")
    assert natural_key(" ") == ("",)


def test_coalesce_duplicate_columns_avoids_downcast_warning_and_preserves_values():
    df = pd.DataFrame(
        [
            [None, "الف", 2, None],
            [1, None, None, "ب"],
        ],
        columns=["code", "name", "code", "name"],
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("error", FutureWarning)
        result = _coalesce_duplicate_columns(df)

    assert not caught
    assert result.shape == (2, 2)
    assert list(result.columns) == ["code", "name"]
    assert result.loc[0, "code"] == 2
    assert result.loc[1, "name"] == "ب"

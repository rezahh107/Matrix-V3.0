from collections.abc import ItemsView, ValuesView

import pytest

from app.core.common.types import (
    CANONICAL_JOIN_KEYS,
    CANONICAL_TRACE_ORDER,
    JoinKeyValues,
    TraceStageFlags,
    TraceStageName,
    parse_header_mode,
)


def _sample_payload() -> dict[str, int]:
    return {
        "کدرشته": 11,
        "جنسیت": 1,
        "دانش آموز فارغ": 0,
        "مرکز گلستان صدرا": 2,
        "مالی حکمت بنیاد": 0,
        "کد مدرسه": 401,
    }


def test_join_key_values_items_and_values_views_preserve_order() -> None:
    payload = _sample_payload()

    values = JoinKeyValues(payload)

    items_view = values.items()
    values_view = values.values()

    assert isinstance(items_view, ItemsView)
    assert isinstance(values_view, ValuesView)
    assert list(items_view) == list(payload.items())
    assert list(values_view) == [payload[key] for key in CANONICAL_JOIN_KEYS]


def test_join_key_values_enforces_six_numeric_entries() -> None:
    with pytest.raises(ValueError):
        JoinKeyValues({"کدرشته": 1}, expected_keys=("کدرشته",))

    with pytest.raises(TypeError):
        JoinKeyValues(
            {
                "کدرشته": "not-int",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 2,
                "مالی حکمت بنیاد": 0,
                "کد مدرسه": 401,
            }
        )

    with pytest.raises(ValueError):
        JoinKeyValues({**_sample_payload(), "اضافی": 7})


def test_join_key_values_behaves_like_mapping() -> None:
    payload = _sample_payload()
    values = JoinKeyValues(payload)

    assert len(values) == len(CANONICAL_JOIN_KEYS) == 6
    assert list(iter(values)) == list(CANONICAL_JOIN_KEYS)
    assert "کدرشته" in values
    assert "ناموجود" not in values
    assert values["کد مدرسه"] == payload["کد مدرسه"]
    assert list(values.keys()) == list(CANONICAL_JOIN_KEYS)


def test_join_key_values_normalizes_legacy_keys() -> None:
    legacy_payload = {
        "دانش_آموز_فارغ": 0,
        "کد_مدرسه": 100,
        "کدرشته": 1,
        "جنسیت": 1,
        "مرکز_گلستان_صدرا": 2,
        "مالی_حکمت_بنیاد": 3,
    }

    values = JoinKeyValues(legacy_payload)

    assert set(values.keys()) == set(CANONICAL_JOIN_KEYS)
    assert values["دانش آموز فارغ"] == 0
    assert values["کد مدرسه"] == 100


@pytest.mark.parametrize("header_mode", ["fa", "en", "fa_en"])
def test_parse_header_mode_accepts_expected_literals(header_mode: str) -> None:
    parsed = parse_header_mode(header_mode)

    assert parsed == header_mode


@pytest.mark.parametrize("invalid_mode", ["", "fa-en", None, 123])
def test_parse_header_mode_rejects_invalid_values(invalid_mode: object) -> None:
    with pytest.raises(ValueError):
        parse_header_mode(invalid_mode)


def test_trace_stage_aliases_match_canonical_order() -> None:
    stages: list[TraceStageName] = list(CANONICAL_TRACE_ORDER)
    flags: TraceStageFlags = {stage: False for stage in stages}

    assert stages == list(CANONICAL_TRACE_ORDER)
    assert set(flags.keys()) == set(CANONICAL_TRACE_ORDER)

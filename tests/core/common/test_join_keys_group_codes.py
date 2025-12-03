from __future__ import annotations

from app.core.common.join_keys import VALID_GROUP_CODES, parse_group_codes


def test_parse_group_codes_deduplicates_and_sorts() -> None:
    assert parse_group_codes("1,3,1,5") == [1, 3, 5]


def test_parse_group_codes_handles_ranges_and_persian_digits() -> None:
    spec = "۱ ، ۳ ، ۵، 7:9 ,21:23, 30"
    assert parse_group_codes(spec) == [1, 3, 5, 7, 8, 9, 21, 22, 23, 30]


def test_parse_group_codes_collects_invalid_codes() -> None:
    invalid: list[int] = []
    result = parse_group_codes("1,2,abc,4-6", valid_codes=(1, 5, 7), invalid_collector=invalid)

    assert result == [1, 5]
    assert sorted(invalid) == [2, 4, 6]


def test_parse_group_codes_respects_valid_group_catalog() -> None:
    # Ensures only LAW-valid codes survive the parser when no custom filter is provided.
    assert parse_group_codes("1,2,3,4,5,6") == [1, 3, 5]
    assert 2 not in VALID_GROUP_CODES
    assert 4 not in VALID_GROUP_CODES
    assert 6 not in VALID_GROUP_CODES

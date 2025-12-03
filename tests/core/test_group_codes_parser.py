from __future__ import annotations

from app.core.common.group_codes import (
    VALID_GROUP_CODES,
    GroupCodesParseResult,
    parse_group_codes,
)


def test_valid_group_codes_set_exact_values() -> None:
    expected = {
        1,
        3,
        5,
        7,
        8,
        9,
        11,
        12,
        14,
        17,
        18,
        21,
        22,
        23,
        24,
        25,
        26,
        27,
        29,
        30,
        31,
        33,
        35,
        41,
        43,
        45,
        46,
        53,
        55,
        66,
        69,
        83,
        89,
    }
    assert frozenset(expected) == VALID_GROUP_CODES


def test_parse_simple_list() -> None:
    result = parse_group_codes("1,3,5")
    assert isinstance(result, GroupCodesParseResult)
    assert result.codes == [1, 3, 5]
    assert result.invalid_tokens == []


def test_parse_persian_digits_and_commas() -> None:
    text = "۱ ، ۳ ، ۵، ۷:۹"
    result = parse_group_codes(text)
    assert result.codes == [1, 3, 5, 7, 8, 9]
    assert result.invalid_tokens == []


def test_parse_mixed_ranges_and_values() -> None:
    text = "1,5,7:9,21:23,30"
    result = parse_group_codes(text)
    assert result.codes == [1, 5, 7, 8, 9, 21, 22, 23, 30]
    assert result.invalid_tokens == []


def test_parse_drops_invalid_codes_not_in_valid_set() -> None:
    text = "1,2,3,4,5"
    result = parse_group_codes(text)
    assert result.codes == [1, 3, 5]
    assert 2 in result.raw_codes
    assert 4 in result.raw_codes
    assert result.invalid_tokens == []


def test_parse_reversed_range_normalized() -> None:
    result = parse_group_codes("9:7")
    assert result.codes == [7, 8, 9]
    assert result.invalid_tokens == []


def test_parse_invalid_token_recorded() -> None:
    result = parse_group_codes("1,abc,5")
    assert result.codes == [1, 5]
    assert "abc" in result.invalid_tokens


def test_parse_empty_and_none() -> None:
    assert parse_group_codes(None).codes == []
    assert parse_group_codes("").codes == []
    assert parse_group_codes("   ").codes == []


def test_parse_handles_non_string_input() -> None:
    result = parse_group_codes(123)
    assert result.codes == []
    assert result.raw_codes == [123]
    assert result.invalid_tokens == []


def test_idempotency_on_codes_roundtrip() -> None:
    for codes in ([1, 3, 5], [1, 5, 7, 8, 9], [21, 22, 23, 30]):
        text = ",".join(str(code) for code in codes)
        result = parse_group_codes(text)
        assert result.codes == sorted(codes)


def test_parse_collapse_repeated_separators_and_spaces() -> None:
    text = "1,,, 3   5"
    result = parse_group_codes(text)
    assert result.codes == [1, 3, 5]
    assert result.invalid_tokens == []

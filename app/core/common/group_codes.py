"""Utilities for parsing experimental group code strings.

The parser is deterministic and pure: it expands user-entered numbers and ranges (with
Persian/English digits and separators) and applies the Golden Rule by keeping only codes
defined in VALID_GROUP_CODES.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from app.core.common.domain import VALID_GROUP_CODES

VALID_GROUP_CODES_SET: frozenset[int] = frozenset(VALID_GROUP_CODES)


@dataclass(frozen=True)
class GroupCodesParseResult:
    """Result of parsing a group-code string."""

    codes: list[int]
    raw_codes: list[int]
    invalid_tokens: list[str]


_PERSIAN_DIGITS = {
    "۰": "0",
    "۱": "1",
    "۲": "2",
    "۳": "3",
    "۴": "4",
    "۵": "5",
    "۶": "6",
    "۷": "7",
    "۸": "8",
    "۹": "9",
}


def _normalize_digits(value: str) -> str:
    """Convert Persian digits to ASCII digits."""

    if not value:
        return value
    return "".join(_PERSIAN_DIGITS.get(ch, ch) for ch in value)


def _normalize_separators(value: str) -> str:
    """Normalize separators to a comma-based convention.

    Persian comma is mapped to ",". Whitespace becomes commas to act as separators. Hyphens are
    normalized to colons for range parsing. Repeated commas are collapsed, and leading/trailing
    commas are stripped to avoid empty tokens.
    """

    if not value:
        return value

    result_chars: list[str] = []
    prev_comma = False
    for ch in value:
        if ch == "،":
            ch = ","
        if ch.isspace():
            ch = ","
        if ch == "-":
            ch = ":"

        if ch == ",":
            if prev_comma:
                continue
            prev_comma = True
            result_chars.append(",")
        else:
            prev_comma = False
            result_chars.append(ch)

    normalized = "".join(result_chars).strip(",")
    return normalized


def _split_into_tokens(value: str) -> list[str]:
    """Split a normalized string into non-empty tokens."""

    if not value:
        return []
    return [token.strip() for token in value.split(",") if token.strip()]


def _parse_int_token(token: str) -> int | None:
    """Parse a token as a positive integer."""

    if not token:
        return None
    try:
        number = int(token)
    except ValueError:
        return None
    if number <= 0:
        return None
    return number


def _parse_range_token(token: str) -> list[int]:
    """Parse a token of the form 'a:b' into a list of integers inclusive."""

    parts = token.split(":")
    if len(parts) != 2:
        return []

    start = _parse_int_token(parts[0].strip())
    end = _parse_int_token(parts[1].strip())
    if start is None or end is None:
        return []

    if start > end:
        start, end = end, start

    return list(range(start, end + 1))


def _deduplicate_preserve_order(values: Iterable[int]) -> list[int]:
    """Deduplicate integers while preserving first-seen order."""

    seen: set[int] = set()
    result: list[int] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def parse_group_codes(value: Any) -> GroupCodesParseResult:
    """Parse a group-code string into validated group codes.

    The parser accepts arbitrary input, normalizes digits and separators, supports single numbers
    and ranges (a:b or a-b), records invalid tokens, and applies the Golden Rule by keeping only
    codes contained in VALID_GROUP_CODES. The output is deterministic for the same input.
    """

    if value is None:
        return GroupCodesParseResult(codes=[], raw_codes=[], invalid_tokens=[])

    text = str(value).strip()
    if not text:
        return GroupCodesParseResult(codes=[], raw_codes=[], invalid_tokens=[])

    normalized = _normalize_digits(text)
    normalized = _normalize_separators(normalized)

    if not normalized:
        return GroupCodesParseResult(codes=[], raw_codes=[], invalid_tokens=[])

    tokens = _split_into_tokens(normalized)
    raw_codes: list[int] = []
    invalid_tokens: list[str] = []

    for token in tokens:
        if ":" in token:
            numbers = _parse_range_token(token)
            if numbers:
                raw_codes.extend(numbers)
            else:
                invalid_tokens.append(token)
            continue

        number = _parse_int_token(token)
        if number is None:
            invalid_tokens.append(token)
        else:
            raw_codes.append(number)

    valid_raw_codes = [number for number in raw_codes if number in VALID_GROUP_CODES_SET]
    unique_valid_codes = _deduplicate_preserve_order(valid_raw_codes)
    sorted_codes = sorted(unique_valid_codes)

    return GroupCodesParseResult(
        codes=sorted_codes,
        raw_codes=list(raw_codes),
        invalid_tokens=invalid_tokens,
    )

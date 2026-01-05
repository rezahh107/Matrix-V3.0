from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

_REQUIRED_PAIR_COLUMNS: tuple[str, str] = ("student_id", "mentor_id")


def _stringify_value(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value)


def allocation_pairs_fingerprint(df: pd.DataFrame) -> list[tuple[str, str]]:
    """Return ordered list of (student_id, mentor_id) pairs as strings.

    Raises:
        AssertionError: If required columns are missing.
    """

    missing = [column for column in _REQUIRED_PAIR_COLUMNS if column not in df.columns]
    if missing:
        raise AssertionError(f"Missing required columns: {missing}")

    student_series = df[_REQUIRED_PAIR_COLUMNS[0]].map(_stringify_value)
    mentor_series = df[_REQUIRED_PAIR_COLUMNS[1]].map(_stringify_value)
    return list(zip(student_series.tolist(), mentor_series.tolist()))


def assert_pairs_equal(before: pd.DataFrame, after: pd.DataFrame) -> None:
    """Assert student_id -> mentor_id alignment is unchanged."""

    assert allocation_pairs_fingerprint(before) == allocation_pairs_fingerprint(after)


def _collect_header_map(columns: Iterable[object]) -> dict[str, int]:
    return {str(column): index for index, column in enumerate(columns)}

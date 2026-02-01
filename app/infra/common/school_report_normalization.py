from __future__ import annotations

import pandas as pd

from app.infra.sqlite_types import coerce_int_columns

_GENDER_TOKEN_MAP: dict[str, int] = {
    "دخترانه": 0,
    "پسرانه": 1,
}

_INT_COLUMNS: tuple[str, ...] = ("کد مدرسه", "مرکز گلستان صدرا", "جنسیت")


def _normalize_gender_tokens(series: pd.Series) -> pd.Series:
    text = series.astype("string").str.strip().str.lower()
    mapped = text.map(_GENDER_TOKEN_MAP)
    if mapped.notna().any():
        return series.mask(mapped.notna(), mapped)
    return series


def normalize_school_report_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize SchoolReport DataFrame (optional gender tokens, Int64 coercion)."""

    normalized = df
    if "جنسیت" in normalized.columns:
        mapped_gender = _normalize_gender_tokens(normalized["جنسیت"])
        if not mapped_gender.equals(normalized["جنسیت"]):
            normalized = normalized.copy()
            normalized["جنسیت"] = mapped_gender
    return coerce_int_columns(normalized, _INT_COLUMNS)


__all__ = ["normalize_school_report_frame"]

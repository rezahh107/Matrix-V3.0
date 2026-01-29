from __future__ import annotations

import pandas as pd

_GENDER_TOKEN_MAP: dict[str, int] = {
    "دخترانه": 0,
    "پسرانه": 1,
}


def normalize_gender_tokens(series: pd.Series) -> pd.Series:
    """Normalize Persian gender tokens to numeric codes (0/1) without breaking numeric inputs."""

    text = series.astype("string").str.strip().str.lower()
    mapped = text.map(_GENDER_TOKEN_MAP)
    if mapped.notna().any():
        return series.mask(mapped.notna(), mapped)
    return series


__all__ = ["normalize_gender_tokens"]

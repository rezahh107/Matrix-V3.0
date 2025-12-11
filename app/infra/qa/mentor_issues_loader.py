"""Helpers for loading and normalizing mentor issues QA artifacts."""

from __future__ import annotations

import pandas as pd


def normalize_missing_raw_values(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with missing-like raw values normalized to ``pd.NA``.

    Some inputs encode missing values as empty strings or literal ``"nan"``
    strings. Downstream comparisons expect consistent NA semantics, so we map
    these representations (including ``None``) to ``pd.NA`` before type
    conversion.
    """

    normalized = frame.copy()
    normalized["raw_value"] = normalized["raw_value"].replace(
        ["", "nan", "NaN", None], pd.NA
    )
    normalized["raw_value"] = normalized["raw_value"].astype("string")
    return normalized

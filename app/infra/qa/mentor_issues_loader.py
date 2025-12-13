"""Helpers for normalizing mentor join-key issue payloads."""

from __future__ import annotations

import pandas as pd


def normalize_missing_raw_values(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with empty-like raw_value entries normalized to <NA>.

    The function is intentionally defensive:
    - If the expected "raw_value" column is absent, the frame is returned
      unchanged.
    - Values that look empty after trimming ("", "nan", "NaN", "na", "none")
      are coerced to ``pd.NA`` regardless of original dtype, while existing
      missing values remain missing.
    - The column is coerced to pandas ``string`` dtype to keep NA round-trippable
      through downstream QA conversions.
    """

    normalized = frame.copy()
    if "raw_value" not in normalized.columns:
        return normalized

    normalized["raw_value"] = normalized["raw_value"].astype("string")
    lowered = normalized["raw_value"].str.strip().str.lower()
    missing_tokens = {"", "nan", "na", "none"}
    mask = lowered.isin(missing_tokens)
    normalized.loc[mask, "raw_value"] = pd.NA
    return normalized


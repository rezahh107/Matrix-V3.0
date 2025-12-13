"""Helpers for loading and normalizing mentor issues QA artifacts."""

from __future__ import annotations

import pandas as pd


def normalize_missing_raw_values(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with missing-like raw values normalized to ``pd.NA``.

    This helper is used by golden regression tests to keep raw_value semantics
    stable. Any "empty" textual representation (empty string, "nan", "NaN",
    "na", "none" with arbitrary spacing/case) and Python-level None must be
    treated as missing.

    Contract (enforced by tests):
    - Input rows with raw_value in: "", "nan", "NaN", None
      MUST become NA after normalization.
    - If the ``raw_value`` column is absent, the frame must be returned
      unchanged.
    """

    normalized = frame.copy()

    # If there is no raw_value column (e.g., in older or partial fixtures),
    # don't touch the frame; callers can rely on this being a no-op.
    if "raw_value" not in normalized.columns:
        return normalized

    # Work in pandas "string" dtype so .str accessors behave consistently.
    raw = normalized["raw_value"].astype("string")

    # Normalize textual variants to a canonical lower-cased form.
    lowered = raw.str.strip().str.lower()

    # Anything that "looks empty" should be treated as missing.
    missing_like = lowered.isin({"", "nan", "na", "none"})

    # Replace missing-like entries with proper NA; preserve already-null values.
    raw = raw.mask(missing_like, pd.NA)

    normalized["raw_value"] = raw
    return normalized

"""Helpers for loading and normalizing mentor issues QA artifacts."""

from __future__ import annotations

import pandas as pd


def normalize_missing_raw_values(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy where missing-like raw values are normalized to ``pd.NA``.

    This is used for mentor issues QA artifacts so that golden regression
    can compare NA masks reliably. Typical “missing” encodings we handle:

    - empty string: ""
    - whitespace-only strings: "   "
    - literal "nan" / "NaN" (case-insensitive)
    - explicit None

    Everything else (هر مقدار واقعی) دست‌نخورده می‌ماند.
    """

    # Work on a shallow copy so callers' frames نمی‌شکنند.
    normalized = frame.copy()

    # اگر به هر دلیل ستون raw_value وجود نداشت، بی‌سروصدا همون فریم رو برگردون.
    if "raw_value" not in normalized.columns:
        return normalized

    # به nullable string تبدیل می‌کنیم تا NAها درست مدیریت شوند.
    raw = normalized["raw_value"].astype("string")

    # تشخیص مقدارهای شبه-خالی (NA-like) به‌صورت case-insensitive و با trim.
    lowered = raw.str.strip().str.lower()
    missing_like = lowered.isin({"", "nan", "na", "none"})

    # این مقدارها را به pd.NA تبدیل می‌کنیم؛ بقیه دست‌نخورده می‌مانند.
    raw = raw.mask(missing_like, pd.NA)

    normalized["raw_value"] = raw
    return normalized

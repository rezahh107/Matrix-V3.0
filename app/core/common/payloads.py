"""Helper utilities for lightweight JSON-safe payloads."""

from __future__ import annotations

import hashlib
from typing import Any

import pandas as pd

__all__ = ["build_frame_payload", "json_safe_value"]


def json_safe_value(value: object) -> object:
    """Convert pandas/numpy scalars to JSON-safe primitives."""

    if value is None or value is pd.NA:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    if isinstance(value, (bool, int, float, str)):
        return value
    item_getter = getattr(value, "item", None)
    if callable(item_getter):  # pragma: no branch - numpy scalar behavior
        try:
            return item_getter()
        except Exception:  # pragma: no cover - defensive fallback
            return str(value)
    iso_getter = getattr(value, "isoformat", None)
    if callable(iso_getter):
        try:
            return iso_getter()
        except Exception:  # pragma: no cover - defensive fallback
            return str(value)
    return str(value)


def build_frame_payload(
    frame: pd.DataFrame,
    *,
    sample_size: int = 50,
    hash_rows: int = 1000,
) -> dict[str, Any]:
    """Build a lightweight payload for DataFrame attrs without storing the full frame."""

    sample_rows = frame.head(sample_size).to_dict(orient="records")
    safe_sample = [
        {key: json_safe_value(value) for key, value in row.items()} for row in sample_rows
    ]
    csv_head = frame.head(hash_rows).to_csv(index=False)
    sha256 = hashlib.sha256(csv_head.encode("utf-8")).hexdigest()
    return {
        "count": int(len(frame)),
        "sample": safe_sample,
        "shape": [int(frame.shape[0]), int(frame.shape[1])],
        "sha256_head": sha256,
    }

"""Regression tests for attribute preservation during CLI dataframe sanitation."""

from __future__ import annotations

import pandas as pd

from app.infra.cli import _coalesce_duplicate_columns, _ensure_valid_dataframe


def test_coalesce_duplicate_columns_preserves_attrs() -> None:
    df = pd.DataFrame([[1, 2]], columns=["a", "a"])
    df.attrs["history_info_df"] = pd.DataFrame({"student_id": [1]})

    sanitized = _coalesce_duplicate_columns(df)

    assert sanitized.attrs.get("history_info_df") is df.attrs["history_info_df"]


def test_ensure_valid_dataframe_preserves_attrs_after_duplicate_merge() -> None:
    df = pd.DataFrame([[1, 2]], columns=["a", "a"])
    df.attrs["meta"] = {"key": "value"}

    validated = _ensure_valid_dataframe(df, name="trace")

    assert validated.attrs.get("meta") == {"key": "value"}

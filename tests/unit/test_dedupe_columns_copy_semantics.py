from __future__ import annotations

import pandas as pd

from app.core.common.columns import dedupe_columns


def test_dedupe_columns_copy_true_matches_previous_behavior() -> None:
    df = pd.DataFrame([[1, 2]], columns=["x", "x"])

    result = dedupe_columns(df)

    assert result.columns.tolist() == ["x"]
    result.iloc[0, 0] = 10
    assert df.iloc[0, 0] == 1


def test_dedupe_columns_copy_false_returns_original_when_unique() -> None:
    df = pd.DataFrame([[1, 2]], columns=["x", "y"])

    result = dedupe_columns(df, copy=False)

    assert result is df


def test_dedupe_columns_copy_false_shares_data_after_deduplication() -> None:
    df = pd.DataFrame([[1, 2]], columns=["x", "x"])

    result = dedupe_columns(df, copy=False)

    assert result is not df
    pd.testing.assert_frame_equal(result, pd.DataFrame([[1]], columns=["x"]))

    # Mutating the result should not affect the original frame because pandas
    # will materialize a copy when slicing to resolve duplicate columns.
    result.iloc[0, 0] = 99
    assert df.iloc[0, 0] == 1

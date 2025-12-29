"""Index contracts for canonical pandas pipelines."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

__all__ = [
    "assert_index_preserved",
    "assert_no_new_labels",
    "enforce_rangeindex_with_lineage",
]


def _is_strict_range_index(index: pd.Index) -> bool:
    if not isinstance(index, pd.RangeIndex):
        return False
    return bool(index.equals(pd.RangeIndex(len(index))))


def assert_index_preserved(
    inp_index: pd.Index,
    out_index: pd.Index,
    *,
    require_unique: bool,
    require_same_order: bool,
    context: str,
) -> None:
    """Assert that output index preserves the input index contract."""

    if require_unique:
        if not inp_index.is_unique:
            raise ValueError(f"{context}: input index must be unique.")
        if not out_index.is_unique:
            raise ValueError(f"{context}: output index must be unique.")
    if len(inp_index) != len(out_index):
        raise ValueError(
            f"{context}: output index length ({len(out_index)}) does not match input ({len(inp_index)})."
        )
    if require_same_order:
        if not inp_index.equals(out_index):
            raise ValueError(f"{context}: output index does not match input index order.")
        return
    if set(inp_index.tolist()) != set(out_index.tolist()):
        raise ValueError(f"{context}: output index labels do not match input labels.")


def assert_no_new_labels(
    inp_index: pd.Index,
    out_index: pd.Index,
    *,
    context: str,
) -> None:
    """Fail fast when assignment introduced unexpected index labels."""

    new_labels = out_index.difference(inp_index)
    if not new_labels.empty:
        sample = new_labels[:5].tolist()
        raise ValueError(f"{context}: unexpected index labels detected: {sample}")


def enforce_rangeindex_with_lineage(
    df: pd.DataFrame,
    *,
    lineage_cols: Sequence[str],
    context: str,
) -> pd.DataFrame:
    """Ensure RangeIndex and capture original index values in lineage columns."""

    needs_range = not _is_strict_range_index(df.index)
    needs_lineage = any(col not in df.columns for col in lineage_cols)
    if not needs_range and not needs_lineage:
        return df

    result = df.copy()
    if needs_lineage:
        for column in lineage_cols:
            if column in result.columns:
                continue
            result[column] = pd.Series(result.index.tolist(), index=result.index, dtype="object")
    if needs_range:
        result = result.reset_index(drop=True)
    return result

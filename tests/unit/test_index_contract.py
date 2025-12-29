from __future__ import annotations

import pandas as pd
import pytest

from app.core.common.index_contract import assert_no_new_labels, enforce_rangeindex_with_lineage


def test_enforce_rangeindex_with_lineage_resets_index_and_preserves_lineage() -> None:
    df = pd.DataFrame({"value": [1, 2, 3]}, index=pd.Index([10, 20, 30], name="row_id"))

    result = enforce_rangeindex_with_lineage(
        df,
        lineage_cols=["__source_index__"],
        context="unit-test",
    )

    assert isinstance(result.index, pd.RangeIndex)
    assert result["__source_index__"].tolist() == [10, 20, 30]


def test_assert_no_new_labels_raises_on_index_drift() -> None:
    inp = pd.Index([10, 20, 30])
    out = pd.Index([10, 20, 30, 40])

    with pytest.raises(ValueError, match="unexpected index labels"):
        assert_no_new_labels(inp, out, context="unit-test")

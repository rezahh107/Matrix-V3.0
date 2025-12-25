from __future__ import annotations

import pandas as pd
import pandera as pa
import pytest

from app.core.contracts import InputContractError, InputContractSpec


class _MixedFailureSpec(InputContractSpec):
    def __init__(self) -> None:
        super().__init__(
            name="mixed",
            required_columns=("value",),
            schema=pa.DataFrameSchema(
                {"value": pa.Column(int, nullable=False)}, coerce=False, strict=False
            ),
        )


def test_schema_errors_include_null_and_invalid_for_same_column() -> None:
    df = pd.DataFrame({"value": [None, "oops"]})

    with pytest.raises(InputContractError) as excinfo:
        _MixedFailureSpec().validate(df)

    codes = [issue.code for issue in excinfo.value.issues]

    assert "null_value" in codes
    assert "invalid_value" in codes
    assert len(excinfo.value.issues) == 2

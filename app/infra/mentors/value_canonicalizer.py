from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from app.infra.sqlite_types import coerce_int_columns

from .field_registry import FieldRegistry


@dataclass(frozen=True)
class ValueCanonicalizationResult:
    canonical_df: pd.DataFrame
    issues: list[dict[str, Any]]

    @property
    def can_continue(self) -> bool:
        return not self.issues


class ValueCanonicalizer:
    """Canonicalize mentor join-key values to integers while surfacing issues."""

    def __init__(self, registry: FieldRegistry) -> None:
        self._registry = registry

    def canonicalize(self, df: pd.DataFrame) -> ValueCanonicalizationResult:
        join_fields = self._registry.join_fields
        school_binding_fields = self._registry.school_binding_fields
        fill_values = {field: 0 for field in school_binding_fields}
        canonical = coerce_int_columns(
            df, [*join_fields, *school_binding_fields], fill_values=fill_values
        )
        issues: list[dict[str, Any]] = []
        for column in join_fields:
            if column not in canonical.columns:
                issues.append({"reason": "MISSING_JOIN_KEY", "column": column, "row_index": None})
                continue
            raw_series = df[column] if column in df.columns else pd.Series(dtype="object")
            coerced = canonical[column]
            invalid_mask = coerced.isna() & raw_series.notna()
            for idx in coerced.index[invalid_mask]:
                issues.append(
                    {
                        "reason": "INVALID_JOIN_VALUE",
                        "column": column,
                        "row_index": int(idx),
                        "raw_value": raw_series.loc[idx],
                    }
                )
        return ValueCanonicalizationResult(canonical_df=canonical, issues=issues)

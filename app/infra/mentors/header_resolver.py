from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.core.common.columns import HEADER_ALIASES_V3
from app.core.common.types import HeaderMode
from app.infra.common.header_pipeline_v3 import HeaderPipelineV3

from .field_registry import FieldRegistry


@dataclass(frozen=True)
class HeaderResolutionResult:
    resolved_df: pd.DataFrame
    missing_fields: list[str]
    issues: list

    @property
    def can_continue(self) -> bool:
        return not self.missing_fields


class HeaderResolver:
    """Resolve mentor headers to canonical form and detect missing join fields."""

    def __init__(self, registry: FieldRegistry, *, header_mode: HeaderMode = "fa") -> None:
        self._registry = registry
        self._header_mode = header_mode
        self._pipeline = HeaderPipelineV3(
            alias_registry=HEADER_ALIASES_V3,
            required={"mentor": self._registry.required_fields},
            critical_required={"mentor": self._registry.required_fields},
        )

    def resolve(self, df: pd.DataFrame) -> HeaderResolutionResult:
        resolution = self._pipeline.resolve(df, source="mentor")
        resolved = resolution.resolved_df
        missing = self._missing_fields(resolved.columns)
        return HeaderResolutionResult(
            resolved_df=resolved, missing_fields=missing, issues=resolution.issues
        )

    def _missing_fields(self, columns: list[str] | pd.Index) -> list[str]:
        column_set = {col for col in columns}
        return [field for field in self._registry.required_fields if field not in column_set]

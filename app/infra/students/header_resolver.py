from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.core.common.columns import HEADER_ALIASES_V3
from app.core.common.types import HeaderMode
from app.infra.common.header_pipeline_v3 import HeaderPipelineV3


@dataclass(frozen=True)
class HeaderResolutionResult:
    resolved_df: pd.DataFrame
    issues: list
    missing_fields: list[str]

    @property
    def can_continue(self) -> bool:
        return not self.missing_fields


class StudentHeaderResolver:
    def __init__(self, *, required_fields: list[str], header_mode: HeaderMode = "fa") -> None:
        self._required_fields = required_fields
        self._header_mode = header_mode
        self._pipeline = HeaderPipelineV3(
            alias_registry=HEADER_ALIASES_V3,
            required={"student": required_fields},
            critical_required={"student": required_fields},
        )

    def resolve(self, df: pd.DataFrame) -> HeaderResolutionResult:
        resolution = self._pipeline.resolve(df, source="student")
        missing = [
            field for field in self._required_fields if field not in resolution.resolved_df.columns
        ]
        return HeaderResolutionResult(
            resolved_df=resolution.resolved_df, issues=resolution.issues, missing_fields=missing
        )

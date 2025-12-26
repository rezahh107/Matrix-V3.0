from __future__ import annotations

import pandas as pd

from app.core.common.columns import HEADER_ALIASES_V3
from app.core.common.types import HeaderMode
from app.infra.common.header_pipeline_v3 import HeaderPipelineV3, HeaderResolution


class SchoolHeaderResolver:
    def __init__(self, *, required_fields: list[str], header_mode: HeaderMode = "fa") -> None:
        self._required_fields = required_fields
        self._header_mode = header_mode
        self._pipeline = HeaderPipelineV3(
            alias_registry=HEADER_ALIASES_V3,
            required={"school": required_fields},
            critical_required={"school": required_fields},
        )

    def resolve(self, df: pd.DataFrame) -> HeaderResolution:
        return self._pipeline.resolve(df, source="school")

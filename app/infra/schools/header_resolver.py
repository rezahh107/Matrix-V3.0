from __future__ import annotations

import pandas as pd

from app.core.common.columns import HEADER_ALIASES_V3
from app.infra.common.header_pipeline_v3 import HeaderPipelineV3, HeaderResolution


class SchoolHeaderResolver:
    def __init__(self, *, required_fields: list[str]) -> None:
        self._pipeline = HeaderPipelineV3(
            alias_registry=HEADER_ALIASES_V3,
            required={"school": required_fields},
            critical_required={"school": required_fields},
            critical_fields={"school": set(required_fields)},
        )

    def resolve(self, df: pd.DataFrame) -> HeaderResolution:
        return self._pipeline.resolve(df, source="school")

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import pandas as pd

from app.core.common.columns import canonicalize_headers
from app.core.common.types import HeaderMode

from .field_registry import FieldRegistry


@dataclass(frozen=True)
class HeaderResolutionResult:
    resolved_df: pd.DataFrame
    missing_fields: list[str]

    @property
    def can_continue(self) -> bool:
        return not self.missing_fields


class HeaderResolver:
    """Resolve mentor headers to canonical form and detect missing join fields."""

    def __init__(self, registry: FieldRegistry, *, header_mode: HeaderMode = "fa") -> None:
        self._registry = registry
        self._header_mode = header_mode

    def resolve(self, df: pd.DataFrame) -> HeaderResolutionResult:
        resolved = canonicalize_headers(df, header_mode=self._header_mode)
        resolved = self._ensure_mentor_id(resolved)
        missing = self._missing_fields(resolved.columns)
        return HeaderResolutionResult(resolved_df=resolved, missing_fields=missing)

    def _missing_fields(self, columns: Iterable[str]) -> list[str]:
        column_set = {col for col in columns}
        return [field for field in self._registry.required_fields if field not in column_set]

    def _ensure_mentor_id(self, df: pd.DataFrame) -> pd.DataFrame:
        alias_map = {
            "mentor_id": "mentor_id",
            "کد کارمندی پشتیبان": "mentor_id",
            "mentorcode": "mentor_id",
            "mentor_code": "mentor_id",
            "mentorid": "mentor_id",
            "employee_id": "mentor_id",
            "employeeid": "mentor_id",
        }

        candidate_columns = [
            column for column in df.columns if str(column).strip().lower() in alias_map
        ]
        if not candidate_columns:
            return df

        series_list: list[pd.Series] = []
        for column in candidate_columns:
            candidate = df.loc[:, column]
            if isinstance(candidate, pd.DataFrame):
                candidate = candidate.iloc[:, 0]
            series_list.append(candidate.astype("string").str.strip())

        mentor_series = series_list[0].reindex(df.index)
        for extra in series_list[1:]:
            extra_aligned = extra.reindex(df.index)
            mentor_series = mentor_series.fillna(extra_aligned)
            mentor_series = mentor_series.mask(mentor_series.eq(""), extra_aligned)

        remaining = df.drop(columns=candidate_columns, errors="ignore")
        remaining["mentor_id"] = mentor_series
        return remaining

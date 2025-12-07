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
        if "mentor_id" in df.columns:
            return df
        alias_map = {
            "کد کارمندی پشتیبان": "mentor_id",
            "mentorcode": "mentor_id",
            "mentor_code": "mentor_id",
            "mentorid": "mentor_id",
            "employee_id": "mentor_id",
            "employeeid": "mentor_id",
        }
        renamed = df
        for column in df.columns:
            normalized = str(column).strip().lower()
            if normalized in alias_map:
                renamed = df.rename(columns={column: alias_map[normalized]})
                break
        return renamed

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import pandas as pd

from app.core.canonical_frames import canonicalize_headers

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

    def __init__(self, registry: FieldRegistry, *, header_mode: str = "fa") -> None:
        self._registry = registry
        self._header_mode = header_mode

    def resolve(self, df: pd.DataFrame) -> HeaderResolutionResult:
        resolved = canonicalize_headers(df, header_mode=self._header_mode)
        if "mentor_id" not in resolved.columns and "کد کارمندی پشتیبان" in resolved.columns:
            resolved = resolved.rename(columns={"کد کارمندی پشتیبان": "mentor_id"})
        missing = self._missing_fields(resolved.columns)
        return HeaderResolutionResult(resolved_df=resolved, missing_fields=missing)

    def _missing_fields(self, columns: Iterable[str]) -> list[str]:
        column_set = {col for col in columns}
        return [field for field in self._registry.required_fields if field not in column_set]

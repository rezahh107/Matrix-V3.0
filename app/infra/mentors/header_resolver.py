from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.core.common.types import HeaderMode
from app.infra.common.header_pipeline_v3 import HeaderIssue, HeaderPipelineV3, _normalize_header
from app.infra.sqlite_types import coerce_int_series

from .field_registry import FieldRegistry


@dataclass(frozen=True)
class HeaderResolutionResult:
    resolved_df: pd.DataFrame
    missing_fields: list[str]
    issues: list[HeaderIssue]

    @property
    def can_continue(self) -> bool:
        return not self.missing_fields and not any(issue.severity == "P0" for issue in self.issues)


class HeaderResolver:
    """Resolve mentor headers to canonical form and detect missing join fields."""

    def __init__(self, registry: FieldRegistry, *, header_mode: HeaderMode = "fa") -> None:
        self._registry = registry
        self._header_mode = header_mode
        critical_fields = self._critical_fields()
        self._pipeline = HeaderPipelineV3(
            alias_registry={"mentor": self._registry.header_aliases},
            required={"mentor": self._registry.required_fields},
            critical_required={"mentor": self._registry.required_fields},
            critical_fields={"mentor": critical_fields},
            conflict_tolerant_aliases={"mentor": {"mentor_id": {"mentor_code"}}},
            coerce_int_conflict_fields={"mentor": self._registry.join_fields},
        )

    def resolve(self, df: pd.DataFrame) -> HeaderResolutionResult:
        resolution = self._pipeline.resolve(df, source="mentor")
        resolved = self._resolve_school_binding_columns(
            df, resolution.resolved_df, resolution.issues
        )
        missing = self._missing_fields(resolved.columns)
        return HeaderResolutionResult(
            resolved_df=resolved, missing_fields=missing, issues=resolution.issues
        )

    def _ensure_mentor_id(self, df: pd.DataFrame) -> pd.DataFrame:
        """Coalesce mentor_id aliases into one canonical mentor_id column.

        Uses the shared header alias SSoT to avoid maintaining any ad-hoc lists.
        """
        alias_map = self._registry.header_aliases

        mentor_aliases = [
            alias for alias, canonical in alias_map.items() if canonical == "mentor_id"
        ]
        unique_aliases = list(dict.fromkeys(mentor_aliases))
        ordered_aliases = [
            "mentor_id",
            *[alias for alias in unique_aliases if alias != "mentor_id"],
        ]

        return self._pipeline._merge_mentor_id_aliases(df, ordered_aliases)

    def _missing_fields(self, columns: list[str] | pd.Index) -> list[str]:
        column_set = {col for col in columns}
        return [field for field in self._registry.required_fields if field not in column_set]

    def _critical_fields(self) -> set[str]:
        return {
            *self._registry.required_fields,
            "capacity_limit",
            "capacity_current",
            "capacity_special",
            "assigned_baseline",
            "allocations_new",
            "remaining_capacity",
        }

    def _resolve_school_binding_columns(
        self,
        raw_df: pd.DataFrame,
        resolved_df: pd.DataFrame,
        issues: list[HeaderIssue],
    ) -> pd.DataFrame:
        normalized_columns = self._normalized_column_map(raw_df)
        resolved = resolved_df.copy()

        for code_header, name_header in self._registry.school_binding_headers:
            code_series = self._select_raw_series(raw_df, normalized_columns, code_header)
            name_series = self._select_raw_series(raw_df, normalized_columns, name_header)
            if code_series is None and name_series is None:
                continue

            if code_series is not None and name_series is not None:
                code_norm = coerce_int_series(code_series)
                name_norm = coerce_int_series(name_series)
                conflict_mask = (
                    code_norm.notna()
                    & name_norm.notna()
                    & (code_norm.astype("Int64") != name_norm.astype("Int64"))
                )
                if bool(conflict_mask.any()):
                    issues.append(
                        HeaderIssue(
                            severity="P0",
                            header=f"{code_header},{name_header}",
                            canonical_field=code_header,
                            message="SCHOOL_BINDING_CONFLICT",
                        )
                    )
                combined = code_series.mask(code_norm.isna(), name_series)
            elif code_series is not None:
                combined = code_series
            else:
                combined = name_series

            if code_header in resolved.columns:
                resolved = resolved.drop(columns=[code_header])
            resolved[code_header] = combined.reindex(resolved.index)
            if name_series is not None and name_header not in resolved.columns:
                resolved[name_header] = name_series.reindex(resolved.index)

        return resolved

    @staticmethod
    def _normalized_column_map(df: pd.DataFrame) -> dict[str, list[str]]:
        normalized: dict[str, list[str]] = {}
        for column in df.columns:
            key = _normalize_header(str(column))
            normalized.setdefault(key, []).append(str(column))
        return normalized

    @staticmethod
    def _select_raw_series(
        df: pd.DataFrame, normalized_map: dict[str, list[str]], header: str
    ) -> pd.Series | None:
        key = _normalize_header(header)
        candidates = normalized_map.get(key, [])
        if not candidates:
            return None
        return df[candidates[0]]

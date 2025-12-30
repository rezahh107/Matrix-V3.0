from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

import pandas as pd

from app.core.common.columns import HEADER_ALIASES_V3, normalize_fa
from app.infra.errors import DatabasePreparationError


def _normalize_header(text: str) -> str:
    normalized = normalize_fa(text) or str(text)
    normalized = normalized.strip().lower()
    normalized = normalized.replace("_", " ")
    return normalized.replace(" ", "")


@dataclass(frozen=True)
class HeaderIssue:
    severity: str
    header: str
    message: str
    canonical_field: str | None = None
    extras: Mapping[str, object] | None = None


@dataclass
class HeaderResolution:
    resolved_df: pd.DataFrame
    issues: list[HeaderIssue] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)

    @property
    def can_continue(self) -> bool:
        return not self.missing_required and not any(
            issue.severity == "P0" for issue in self.issues
        )

    def require_can_continue(self, *, path: str, reason_fa: str) -> pd.DataFrame:
        if self.can_continue:
            return self.resolved_df

        hint = ", ".join(self.missing_required) if self.missing_required else None
        raise DatabasePreparationError(path=path, reason=reason_fa, hint=hint)

    def add_issues(self, new_issues: Iterable[HeaderIssue]) -> None:
        self.issues.extend(list(new_issues))


class HeaderPipelineV3:
    """Unified header/alias normalization across mentor/student/school payloads."""

    def __init__(
        self,
        *,
        alias_registry: Mapping[str, Mapping[str, str]] | None = None,
        required: Mapping[str, Iterable[str]] | None = None,
        critical_required: Mapping[str, Iterable[str]] | None = None,
    ) -> None:
        self._alias_registry = self._normalize_registry(
            alias_registry or self._default_alias_registry()
        )
        self._required = {key: list(value) for key, value in (required or {}).items()}
        self._critical_required = {
            key: {value for value in values} for key, values in (critical_required or {}).items()
        }

    def resolve(self, df: pd.DataFrame, source: str) -> HeaderResolution:
        normalized_aliases = self._alias_registry.get(source, {})
        issues: list[HeaderIssue] = []
        collisions: dict[str, list[str]] = defaultdict(list)

        for column in df.columns:
            normalized = _normalize_header(str(column))
            canonical = normalized_aliases.get(normalized)
            if canonical is None:
                issues.append(
                    HeaderIssue(
                        severity="P2",
                        header=str(column),
                        message="UNKNOWN_HEADER",
                    )
                )
                continue
            collisions[canonical].append(str(column))

        mentor_aliases = self._ordered_mentor_alias_columns(df, source)
        merged = self._merge_mentor_id_aliases(df, mentor_aliases)
        mapped_columns: dict[str, list[str]] = defaultdict(list)
        for column in merged.columns:
            normalized = _normalize_header(str(column))
            canonical = normalized_aliases.get(normalized)
            if canonical is None:
                continue
            mapped_columns[canonical].append(str(column))

        coalesced: dict[str, pd.Series] = {}
        conflict_counts: dict[str, int] = {}
        for canonical, headers in mapped_columns.items():
            if len(headers) > 1:
                merged_series, conflict_count = self._coalesce_columns(merged, headers)
                coalesced[canonical] = merged_series
                conflict_counts[canonical] = conflict_count

        resolved_columns: list[str] = []
        resolved_data: dict[str, pd.Series] = {}
        for column in merged.columns:
            normalized = _normalize_header(str(column))
            canonical = normalized_aliases.get(normalized)
            if canonical is None:
                if column not in resolved_data:
                    candidate = merged.loc[:, column]
                    if isinstance(candidate, pd.DataFrame):
                        candidate = candidate.iloc[:, 0]
                    resolved_data[column] = candidate.reindex(merged.index)
                    resolved_columns.append(str(column))
                continue
            if canonical in coalesced:
                if canonical not in resolved_data:
                    resolved_data[canonical] = coalesced[canonical].reindex(merged.index)
                    resolved_columns.append(canonical)
                continue
            if canonical not in resolved_data:
                resolved_data[canonical] = merged.loc[:, column].reindex(merged.index)
                resolved_columns.append(canonical)

        renamed = pd.DataFrame(resolved_data, index=merged.index).loc[:, resolved_columns].copy()
        if df.attrs:
            renamed.attrs.update(dict(df.attrs))

        for canonical, headers in collisions.items():
            if len(headers) > 1:
                conflict_count = conflict_counts.get(canonical, 0)
                resolution = "coalesce left-to-right (first non-null wins)"
                if canonical == "mentor_id":
                    resolution = "mentor_id alias merge (canonical preferred)"
                    if canonical not in conflict_counts and mentor_aliases:
                        _, conflict_count = self._coalesce_columns(df, mentor_aliases)
                issues.append(
                    HeaderIssue(
                        severity="P1",
                        header=",".join(headers),
                        canonical_field=canonical,
                        message="AMBIGUOUS_HEADER",
                        extras={
                            "original_columns": headers,
                            "resolution": resolution,
                            "conflict_count": conflict_count,
                        },
                    )
                )

        required = self._required.get(source, [])
        missing = [column for column in required if column not in renamed.columns]
        if missing:
            critical = self._critical_required.get(source, set())
            severity = "P0" if any(field in critical for field in missing) else "P1"
            issues.append(
                HeaderIssue(
                    severity=severity,
                    header=",".join(missing),
                    message="MISSING_REQUIRED",
                )
            )

        return HeaderResolution(resolved_df=renamed, issues=issues, missing_required=missing)

    @staticmethod
    def _coalesce_columns(
        df: pd.DataFrame, columns: Sequence[str]
    ) -> tuple[pd.Series, int]:
        candidates: list[pd.Series] = []
        for column in columns:
            if column not in df.columns:
                continue
            candidate = df.loc[:, column]
            if isinstance(candidate, pd.DataFrame):
                for idx in range(candidate.shape[1]):
                    candidates.append(candidate.iloc[:, idx])
            else:
                candidates.append(candidate)

        if not candidates:
            return pd.Series(index=df.index, dtype="object"), 0

        merged = candidates[0].reindex(df.index)
        conflict_count = 0
        for extra in candidates[1:]:
            extra_aligned = extra.reindex(df.index)
            both_non_null = merged.notna() & extra_aligned.notna()
            conflicts = both_non_null & merged.ne(extra_aligned)
            conflict_count += int(conflicts.sum())
            merged = merged.where(merged.notna(), extra_aligned)
        return merged, conflict_count

    @staticmethod
    def _merge_mentor_id_aliases(df: pd.DataFrame, aliases: list[str]) -> pd.DataFrame:
        candidates: list[pd.Series] = []

        for column in dict.fromkeys(aliases):
            if column not in df.columns:
                continue
            candidate = df.loc[:, column]
            if isinstance(candidate, pd.DataFrame):
                for idx in range(candidate.shape[1]):
                    candidates.append(candidate.iloc[:, idx])
            else:
                candidates.append(candidate)

        if not candidates:
            return df

        series_list = [candidate.astype("string").str.strip() for candidate in candidates]
        merged = series_list[0].reindex(df.index)
        for extra in series_list[1:]:
            extra_aligned = extra.reindex(df.index)
            merged = merged.fillna(extra_aligned)
            merged = merged.mask(merged.eq(""), extra_aligned)

        remaining = df.drop(columns=[col for col in aliases if col in df.columns], errors="ignore")
        remaining = remaining.loc[:, ~remaining.columns.duplicated(keep="first")]
        remaining["mentor_id"] = merged
        return remaining

    def _ordered_mentor_alias_columns(
        self, df: pd.DataFrame, source: str
    ) -> list[str]:
        alias_priority = self._mentor_alias_priority(source)
        normalized_columns: dict[str, list[str]] = defaultdict(list)

        for column in df.columns:
            normalized_columns[_normalize_header(str(column))].append(str(column))

        return [
            column
            for normalized in alias_priority
            for column in normalized_columns.get(normalized, [])
        ]

    def _mentor_alias_priority(self, source: str) -> list[str]:
        alias_map = self._alias_registry.get(source, {})
        canonical_normalized = _normalize_header("mentor_id")
        raw_aliases = [
            alias for alias, canonical in alias_map.items() if canonical == "mentor_id"
        ]
        unique_aliases = list(dict.fromkeys(raw_aliases))
        return [
            canonical_normalized,
            *[alias for alias in unique_aliases if alias != canonical_normalized],
        ]

    @staticmethod
    def _normalize_registry(registry: Mapping[str, Mapping[str, str]]) -> dict[str, dict[str, str]]:
        normalized: dict[str, dict[str, str]] = {}
        for source, mapping in registry.items():
            normalized[source] = {_normalize_header(key): value for key, value in mapping.items()}
        return normalized

    @staticmethod
    def _default_alias_registry() -> dict[str, dict[str, str]]:
        return {
            source: {_normalize_header(k): v for k, v in mapping.items()}
            for source, mapping in HEADER_ALIASES_V3.items()
        }

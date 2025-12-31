from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from app.core.common.types import HeaderMode
from app.core.policy_loader import PolicyConfig
from app.infra import pool_loader
from app.infra.errors import DatabasePreparationError
from app.infra.groupcode.groupcode_repository import GroupCodeRepository
from app.infra.local_database import LocalDatabase, _coerce_int_columns
from app.infra.reference_mentors_repository import _POOL_JOIN_KEY_QA_ATTR, _derive_pool_join_keys
from app.infra.schools.school_repository import SchoolRepository

from .field_registry import FieldRegistry
from .header_resolver import HeaderResolver
from .join_key_resolver import JoinKeyResolutionResult, JoinKeyResolver
from .mentor_pool_builder import MentorPoolBuilder, MentorPoolBuildResult
from .value_canonicalizer import ValueCanonicalizationResult, ValueCanonicalizer


@dataclass(frozen=True)
class MentorPipelineTraceEntry:
    stage: str
    rows: int
    columns: int
    fingerprint: str


@dataclass(frozen=True)
class MentorPipelineTrace:
    entries: list[MentorPipelineTraceEntry]

    def to_records(self) -> list[dict[str, object]]:
        return [
            {
                "stage": entry.stage,
                "rows": entry.rows,
                "columns": entry.columns,
                "fingerprint": entry.fingerprint,
            }
            for entry in self.entries
        ]


@dataclass(frozen=True)
class MentorPipelineResult:
    build_result: MentorPoolBuildResult
    header_result: Any
    value_result: ValueCanonicalizationResult
    join_key_result: JoinKeyResolutionResult
    trace: MentorPipelineTrace | None = None

    @property
    def can_continue(self) -> bool:
        return (
            self.header_result.can_continue
            and self.value_result.can_continue
            and self.join_key_result.can_continue
            and self.build_result.can_continue
        )


class MentorPipelineV3:
    """Unified mentor import pipeline (FieldRegistry → Header → Values → JoinKey → Pool)."""

    def __init__(
        self,
        *,
        policy: PolicyConfig,
        pool_source: str = "inspactor",
        header_mode: HeaderMode = "fa",
        db: LocalDatabase | None = None,
        reference_mode: Literal["excel", "db"] = "db",
        school_repo: SchoolRepository | None = None,
        groupcode_repo: GroupCodeRepository | None = None,
        enable_trace: bool = False,
        trace_max_rows: int = 1000,
    ) -> None:
        self._policy = policy
        self._pool_source = pool_source
        self._registry = FieldRegistry(policy)
        self._header_resolver = HeaderResolver(self._registry, header_mode=header_mode)
        self._canonicalizer = ValueCanonicalizer(self._registry)
        self._join_key_resolver = JoinKeyResolver(policy)
        self._builder = MentorPoolBuilder(policy, pool_source=pool_source)
        self._reference_mode = reference_mode
        self._school_repo = school_repo
        self._groupcode_repo = groupcode_repo
        self._db = db or (school_repo.database if school_repo is not None else None)
        self._trace_enabled = enable_trace
        self._trace_max_rows = trace_max_rows

    def run_from_excel(
        self,
        path: Path,
        *,
        pool_type: pool_loader.PoolType = "inspactor",
        pool_sheet: str | None = None,
    ) -> MentorPipelineResult:
        raw_df, _ = pool_loader.load_pool_with_detection(
            path, pool_type=pool_type, pool_sheet=pool_sheet
        )
        return self.run(raw_df)

    def run(self, df: pd.DataFrame) -> MentorPipelineResult:
        self._enforce_db_reference_mode()
        trace_entries: list[MentorPipelineTraceEntry] = []
        if self._trace_enabled:
            trace_entries.append(self._trace_entry("raw", df))
        header_result = self._header_resolver.resolve(df)
        working = header_result.resolved_df
        if self._trace_enabled:
            trace_entries.append(self._trace_entry("header_resolved", working))
        value_result = self._canonicalizer.canonicalize(working)
        canonical_df = value_result.canonical_df
        if self._trace_enabled:
            trace_entries.append(self._trace_entry("canonicalized", canonical_df))
        has_required_fields = self._registry.has_required_fields(canonical_df.columns)
        if self._trace_enabled and has_required_fields:
            trace_entries.append(self._trace_entry("join_keys_present", canonical_df))
        if not has_required_fields and self._db is not None:
            derived_df, derive_issues = _derive_pool_join_keys(
                working, db=self._db, policy=self._policy
            )
            derived_df = self._header_resolver._ensure_mentor_id(derived_df)
            derived_df.attrs[_POOL_JOIN_KEY_QA_ATTR] = derive_issues
            value_result = ValueCanonicalizationResult(
                canonical_df=derived_df, issues=derive_issues
            )
            canonical_df = derived_df
            if self._trace_enabled:
                trace_entries.append(self._trace_entry("canonicalized_db", canonical_df))
        attr_issues = canonical_df.attrs.get(_POOL_JOIN_KEY_QA_ATTR, [])
        if attr_issues and not value_result.issues:
            value_result = ValueCanonicalizationResult(
                canonical_df=canonical_df, issues=attr_issues
            )
        join_key_result = self._join_key_resolver.resolve(value_result)
        if self._trace_enabled:
            trace_entries.append(self._trace_entry("join_keys", join_key_result.canonical_df))
            trace_entries.append(
                self._trace_entry("usable_profiles", join_key_result.usable_profiles)
            )
        build_result = self._builder.build(join_key_result)
        if self._trace_enabled:
            trace_entries.append(self._trace_entry("pool_built", build_result.pool))
        trace = MentorPipelineTrace(entries=trace_entries) if trace_entries else None
        return MentorPipelineResult(
            build_result=build_result,
            header_result=header_result,
            value_result=value_result,
            join_key_result=join_key_result,
            trace=trace,
        )

    def _trace_entry(self, stage: str, frame: pd.DataFrame) -> MentorPipelineTraceEntry:
        columns = self._trace_columns(frame.columns)
        return MentorPipelineTraceEntry(
            stage=stage,
            rows=int(frame.shape[0]),
            columns=int(frame.shape[1]),
            fingerprint=_frame_fingerprint(
                frame,
                columns,
                max_rows=self._trace_max_rows,
            ),
        )

    def _trace_columns(self, columns: Iterable[str]) -> Sequence[str]:
        preferred = ["mentor_id", *self._registry.join_fields]
        column_set = set(columns)
        existing = [col for col in preferred if col in column_set]
        if not existing:
            return tuple(sorted(column_set))
        return tuple(existing)

    def _enforce_db_reference_mode(self) -> None:
        if self._reference_mode != "db":
            return
        if self._school_repo is None or self._groupcode_repo is None:
            raise DatabasePreparationError(
                path="local_db",
                reason="مرجع مدارس/کدگروه برای حالت DB تنظیم نشده است.",
                hint="ابتدا داده‌های مدارس و کدگروه را بارگذاری کنید.",
            )
        if self._school_repo.database is not self._groupcode_repo.database:
            raise DatabasePreparationError(
                path="local_db",
                reason="مراجع مدارس و کدگروه از پایگاه‌های متفاوت هستند.",
                hint="هر دو مخزن باید به یک پایگاه داده متصل باشند.",
            )
        try:
            school_status = self._school_repo.status()
            groupcode_status = self._groupcode_repo.status()
        except Exception as exc:  # pragma: no cover - defensive conversion
            raise DatabasePreparationError(
                path="local_db",
                reason="خواندن وضعیت داده مرجع ممکن نیست.",
                hint=str(exc),
            ) from exc
        if school_status.row_count <= 0 or groupcode_status.row_count <= 0:
            raise DatabasePreparationError(
                path="local_db",
                reason="جدول مدارس یا کدگروه خالی است.",
                hint="داده‌های مرجع را از فایل‌های Excel وارد کنید.",
            )


def canonicalize_join_keys_for_cache(payload: pd.DataFrame, policy: PolicyConfig) -> pd.DataFrame:
    registry = FieldRegistry(policy)
    canonicalizer = ValueCanonicalizer(registry)
    value_result = canonicalizer.canonicalize(payload)
    if not value_result.can_continue:
        return payload
    return _coerce_int_columns(value_result.canonical_df, registry.join_fields)


def _frame_fingerprint(
    frame: pd.DataFrame,
    columns: Sequence[str],
    *,
    max_rows: int,
) -> str:
    if frame.empty:
        return "empty"
    subset_columns = [column for column in columns if column in frame.columns]
    subset = frame.loc[:, subset_columns] if subset_columns else frame.iloc[:, 0:0]
    sample = subset.head(max_rows)
    payload = sample.to_csv(index=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

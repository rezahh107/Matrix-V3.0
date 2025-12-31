"""Eligibility channel for deterministic candidate pool filtering (Core-only)."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

import pandas as pd

from app.core.common.columns import ensure_series
from app.core.common.filters import apply_join_filters
from app.core.common.join_keys import (
    JoinKeyCanonicalizationError,
    StudentSchoolCode,
    canonicalize_join_key_value,
    center_wildcard_value,
    normalize_join_key_name,
    resolve_finance_variants,
)
from app.core.policy_loader import PolicyConfig

if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from app.core.common.join_resolver import EffectiveFinanceKeys, EffectiveJoinKeys

JoinBucketIndex = Mapping[tuple[int, ...], pd.Index]


@dataclass(frozen=True, slots=True)
class EligibilitySpec:
    effective_join_keys: EffectiveJoinKeys
    finance_keys: EffectiveFinanceKeys
    school_code: StudentSchoolCode
    student: Mapping[str, object]
    policy: PolicyConfig
    student_join_map: Mapping[str, int] | None = None
    join_bucket_index: JoinBucketIndex | None = None
    join_bucket_enabled: bool = False
    manager_preference_index: pd.Index | None = None
    manager_priority_enabled: bool = False

    def with_join_bucket(self, join_bucket_index: JoinBucketIndex | None) -> EligibilitySpec:
        return replace(self, join_bucket_index=join_bucket_index)

    def with_manager_preference(
        self,
        manager_preference_index: pd.Index | None,
        *,
        enabled: bool,
    ) -> EligibilitySpec:
        return replace(
            self,
            manager_preference_index=manager_preference_index,
            manager_priority_enabled=enabled,
        )

    def hard_mask(self, pool_df: pd.DataFrame) -> pd.Series:
        _, eligible, _ = _apply_join_filters(pool_df, self, tracker=None)
        return pd.Series(pool_df.index.isin(eligible.index), index=pool_df.index, dtype=bool)

    def priority_score(self, pool_df: pd.DataFrame) -> pd.Series:
        if not self.manager_priority_enabled or self.manager_preference_index is None:
            return pd.Series(0, index=pool_df.index, dtype=int)
        mask = pool_df.index.isin(self.manager_preference_index)
        return pd.Series(mask.astype(int), index=pool_df.index, dtype=int)

    def explain(self) -> dict[str, object]:
        return {
            "center_code": self.effective_join_keys.center_code,
            "center_source": self.effective_join_keys.center_source,
            "finance_code": self.finance_keys.finance_code,
            "finance_source": self.finance_keys.finance_source,
            "school_code": self.school_code.value,
            "school_wildcard": self.school_code.wildcard,
            "manager_priority_enabled": self.manager_priority_enabled,
            "join_bucket_enabled": self.join_bucket_enabled,
        }


def apply_eligibility(
    pool_df: pd.DataFrame,
    spec: EligibilitySpec,
) -> tuple[pd.DataFrame, pd.Series, dict[str, object]]:
    stage_counts: dict[str, int] = {}

    def _tracker(stage: str, count: int) -> None:
        stage_counts[stage] = int(count)

    bucketed, _, bucket_trace = _apply_join_filters(pool_df, spec, tracker=_tracker)
    mask = spec.hard_mask(pool_df)
    eligible = pool_df.loc[mask]
    priority = spec.priority_score(eligible)
    if not eligible.index.equals(priority.index):
        raise AssertionError("Eligibility priority index must align with eligible candidates")
    preferred_count = int((priority > 0).sum())

    fingerprint_columns = _fingerprint_columns(spec.policy, pool_df)
    trace = {
        "initial": _trace_entry(pool_df, fingerprint_columns),
        "bucketed": _trace_entry(bucketed, fingerprint_columns),
        "eligible": _trace_entry(eligible, fingerprint_columns),
        "stage_counts": dict(stage_counts),
        "preferred_count": preferred_count,
        "bucket_trace": bucket_trace,
        "explain": spec.explain(),
    }
    return eligible, priority, trace


def build_join_bucket_index(pool: pd.DataFrame, policy: PolicyConfig) -> JoinBucketIndex:
    normalized = _normalize_join_keys_for_bucketing(pool, policy)
    grouped = normalized.groupby(list(policy.join_keys), sort=False).indices
    buckets: dict[tuple[int, ...], pd.Index] = {}
    index = pool.index
    for key, positions in grouped.items():
        key_tuple = key if isinstance(key, tuple) else (key,)
        buckets[tuple(int(value) for value in key_tuple)] = index.take(positions)
    return buckets


def _apply_join_filters(
    pool_df: pd.DataFrame,
    spec: EligibilitySpec,
    *,
    tracker: Any,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    candidate_pool, bucket_trace = _bucket_candidate_pool_with_trace(pool_df, spec)
    eligible = apply_join_filters(
        candidate_pool,
        spec.student,
        policy=spec.policy,
        student_join_map=spec.student_join_map,
        tracker=tracker,
    )
    return candidate_pool, eligible, bucket_trace


def _bucket_candidate_pool_with_trace(
    candidate_pool: pd.DataFrame,
    spec: EligibilitySpec,
) -> tuple[pd.DataFrame, dict[str, object]]:
    trace: dict[str, object] = {
        "pool_built_size": int(candidate_pool.shape[0]),
        "pool_size_before_bucket": int(candidate_pool.shape[0]),
        "bucket_key": None,
        "bucket_size": None,
        "bucket_skip_reason": None,
        "bucket_key_variants": [],
        "bucket_sizes": [],
    }
    join_bucket_index = spec.join_bucket_index
    if not spec.join_bucket_enabled:
        trace["bucket_skip_reason"] = "disabled_by_setting"
        return candidate_pool, trace
    if join_bucket_index is None:
        trace["bucket_skip_reason"] = "no_join_bucket_index"
        return candidate_pool, trace
    if not join_bucket_index:
        trace["bucket_skip_reason"] = "empty_bucket_index"
        return candidate_pool, trace
    join_map = spec.student_join_map
    if join_map is None:
        trace["bucket_skip_reason"] = "missing_student_join_map"
        return candidate_pool, trace
    if any(column not in candidate_pool.columns for column in spec.policy.join_keys):
        trace["bucket_skip_reason"] = "missing_pool_join_columns"
        return candidate_pool, trace
    should_bucket, reason = _should_use_join_bucket(spec, candidate_pool)
    if not should_bucket:
        trace["bucket_skip_reason"] = reason or "not_eligible_for_bucket"
        return candidate_pool, trace

    key_variants = _join_bucket_key_variants(join_map, spec.policy)
    if not key_variants:
        trace["bucket_skip_reason"] = "no_bucket_variants"
        return candidate_pool, trace
    trace["bucket_key_variants"] = list(key_variants)

    bucket_entries: list[tuple[tuple[int, ...], int]] = []
    combined_values: list[object] = []
    for key in key_variants:
        bucket = join_bucket_index.get(key)
        if bucket is None or bucket.empty:
            continue
        bucket_entries.append((key, int(bucket.size)))
        combined_values.extend(bucket.to_list())

    if not combined_values:
        trace["bucket_skip_reason"] = "no_bucket_matches"
        return candidate_pool, trace

    bucket_entries = sorted(bucket_entries, key=lambda item: item[0])
    trace["bucket_sizes"] = [size for _, size in bucket_entries]
    trace["bucket_key"] = _format_bucket_keys([key for key, _ in bucket_entries])

    combined_index = pd.Index(pd.unique(pd.Index(combined_values)))
    trace["bucket_size"] = int(len(combined_index))
    selected_index = candidate_pool.index.intersection(combined_index, sort=False)
    if selected_index.empty:
        trace["bucket_skip_reason"] = "bucket_intersection_empty"
        return candidate_pool, trace
    return candidate_pool.loc[selected_index], trace


def _format_bucket_keys(keys: Sequence[tuple[int, ...]]) -> str | None:
    if not keys:
        return None
    rendered = ["(" + ",".join(str(value) for value in key) + ")" for key in keys]
    return ";".join(rendered)


def _should_use_join_bucket(
    spec: EligibilitySpec,
    candidate_pool: pd.DataFrame,
) -> tuple[bool, str | None]:
    join_map = spec.student_join_map
    if join_map is None:
        return False, "missing_student_join_map"
    for column in spec.policy.join_keys:
        normalized = normalize_join_key_name(column)
        value = join_map.get(normalized)
        if value is None or int(value) < 0:
            return False, "invalid_join_keys"
    school_code = spec.school_code
    if school_code.wildcard or school_code.missing or school_code.value is None:
        return False, "school_wildcard_or_missing"
    center_info = spec.effective_join_keys
    if center_info.center_code is None:
        return False, "missing_center_code"
    wildcard_center = center_wildcard_value(spec.policy)
    if wildcard_center is not None and int(center_info.center_code) == wildcard_center:
        return False, "center_wildcard"

    if "has_school_constraint" in candidate_pool.columns:
        constraint = ensure_series(candidate_pool["has_school_constraint"]).fillna(False).astype(bool)
        if (~constraint).any():
            return False, "invalid_pool_bucket_values"
    if "mentor_school_binding_mode" in candidate_pool.columns:
        return False, "invalid_pool_bucket_values"
    return True, None


def _join_bucket_key_variants(
    join_map: Mapping[str, int],
    policy: PolicyConfig,
) -> list[tuple[int, ...]]:
    normalized_keys = [normalize_join_key_name(column) for column in policy.join_keys]
    values: list[int] = []
    for normalized in normalized_keys:
        value = join_map.get(normalized)
        if value is None:
            return []
        values.append(int(value))

    base_variants: list[list[int]] = [values]

    finance_normalized = normalize_join_key_name(policy.stage_column("finance"))
    if finance_normalized in normalized_keys:
        finance_index = normalized_keys.index(finance_normalized)
        finance_value = values[finance_index]
        variants = resolve_finance_variants(finance_value, policy)
        if variants:
            base_variants = []
            for variant in sorted(variants):
                updated = list(values)
                updated[finance_index] = int(variant)
                base_variants.append(updated)

    expanded: set[tuple[int, ...]] = set()
    center_normalized = normalize_join_key_name(policy.stage_column("center"))
    school_normalized = normalize_join_key_name(policy.stage_column("school"))
    center_index = (
        normalized_keys.index(center_normalized) if center_normalized in normalized_keys else None
    )
    school_index = (
        normalized_keys.index(school_normalized) if school_normalized in normalized_keys else None
    )
    wildcard_center = center_wildcard_value(policy)
    school_wildcard = 0 if policy.school_code_empty_as_zero else None

    for base in base_variants:
        expanded.add(tuple(base))
        if center_index is not None:
            center_value = base[center_index]
            if center_value != 0:
                updated = list(base)
                updated[center_index] = 0
                expanded.add(tuple(updated))
            if wildcard_center is not None and wildcard_center != center_value:
                updated = list(base)
                updated[center_index] = int(wildcard_center)
                expanded.add(tuple(updated))
        if school_index is not None and school_wildcard is not None:
            school_value = base[school_index]
            if school_value != school_wildcard:
                updated = list(base)
                updated[school_index] = int(school_wildcard)
                expanded.add(tuple(updated))

    return sorted(expanded)


def _normalize_join_keys_for_bucketing(
    pool: pd.DataFrame,
    policy: PolicyConfig,
) -> pd.DataFrame:
    normalized: dict[str, pd.Series] = {}
    for column in policy.join_keys:
        if column not in pool.columns:
            raise KeyError(f"Join key '{column}' missing from candidate pool")
        series = ensure_series(pool[column])
        normalized[column] = series.map(
            lambda cell: _normalize_join_key_value_for_bucket(column, cell, policy)
        ).astype("int64")
    return pd.DataFrame(normalized, index=pool.index)


def _normalize_join_key_value_for_bucket(
    column: str, value: object, policy: PolicyConfig
) -> int:
    try:
        return canonicalize_join_key_value(column, value, policy=policy)
    except JoinKeyCanonicalizationError:
        if _is_missing_join_value(value):
            return -1
        return -2


def _is_missing_join_value(value: object) -> bool:
    if value is None:
        return True
    try:
        missing = pd.isna(value)
    except TypeError:
        missing = False
    if isinstance(missing, bool) and missing:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _fingerprint_columns(policy: PolicyConfig, pool_df: pd.DataFrame) -> Sequence[str]:
    base = [column for column in policy.join_keys if column in pool_df.columns]
    if "mentor_id" in pool_df.columns:
        base.append("mentor_id")
    return tuple(base)


def _trace_entry(frame: pd.DataFrame, columns: Sequence[str]) -> dict[str, object]:
    return {
        "rows": int(frame.shape[0]),
        "fingerprint": _frame_fingerprint(frame, columns),
    }


def _frame_fingerprint(
    frame: pd.DataFrame,
    columns: Sequence[str],
    *,
    max_rows: int = 20,
) -> str:
    if frame.empty:
        return "empty"
    subset_columns = [column for column in columns if column in frame.columns]
    subset = frame.loc[:, subset_columns] if subset_columns else frame.iloc[:, 0:0]
    sample = subset.head(max_rows)
    payload = sample.to_csv(index=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def eligibility_trace_rows(trace: Mapping[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for stage in ("initial", "bucketed", "eligible"):
        entry = trace.get(stage)
        if isinstance(entry, Mapping):
            rows.append(
                {
                    "stage": stage,
                    "rows": entry.get("rows"),
                    "fingerprint": entry.get("fingerprint"),
                }
            )
    return rows


__all__ = [
    "EligibilitySpec",
    "JoinBucketIndex",
    "apply_eligibility",
    "build_join_bucket_index",
    "eligibility_trace_rows",
]

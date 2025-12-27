"""منطق رتبه‌بندی پشتیبان‌ها طبق Policy (RANK-CORE)."""

from __future__ import annotations

import heapq
import re
from collections import defaultdict
from collections.abc import Hashable, Mapping, Sequence
from hashlib import blake2b
from numbers import Number
from pathlib import Path
from typing import TypedDict, cast

import pandas as pd

from app.core.common.columns import canonicalize_headers, dedupe_columns
from app.core.policy_loader import PolicyConfig, load_policy

from .ids import ensure_ranking_columns
from .reasons import ReasonCode, build_reason
from .types import natural_key

__all__ = [
    "natural_key",
    "build_mentor_state",
    "compute_remaining_capacity",
    "apply_ranking_policy",
    "consume_capacity",
    "HeapRankingManager",
    "ensure_ranking_columns",
]

_DEFAULT_POLICY_PATH = Path("config/policy.json")


class MentorCapacityState(TypedDict):
    """Normalized capacity state for a mentor.

    initial:
        ظرفیت اولیه در شروع run.
    remaining:
        ظرفیت باقی‌مانده در هر لحظه.
    alloc_new:
        تعداد تخصیص‌های جدید در این run.
    occupancy_ratio:
        Legacy diagnostic field; kept for compatibility but not recomputed.
    total_capacity:
        ظرفیت کل (برای گزارش).
    current_allocations:
        تعداد تخصیص‌های فعلی (برای گزارش).
    remaining_capacity:
        همان remaining، برای سازگاری با خروجی‌ها.
    """

    initial: int
    remaining: int
    alloc_new: int
    occupancy_ratio: float
    total_capacity: int
    current_allocations: int
    remaining_capacity: int


class HeapRankingManager:
    """Deterministic per-bucket priority queues for mentor ranking."""

    def __init__(
        self,
        *,
        index: pd.Index,
        join_bucket_index: Mapping[tuple[int, ...], pd.Index] | None = None,
    ) -> None:
        self._default_bucket: tuple[str, ...] = ("__all__",)
        self._index_to_bucket: dict[Hashable, tuple[int, ...] | tuple[str, ...]] = {}
        if join_bucket_index:
            for bucket_key, bucket_index in join_bucket_index.items():
                normalized_key = tuple(int(value) for value in bucket_key)
                for idx in bucket_index:
                    self._index_to_bucket[idx] = normalized_key
        else:
            for idx in index:
                self._index_to_bucket[idx] = self._default_bucket

        self._buckets: dict[
            tuple[int, ...] | tuple[str, ...],
            list[tuple[tuple[object, ...], int, Hashable]],
        ] = defaultdict(list)
        self._versions: dict[Hashable, int] = {}

    def _priority_from_row(self, row: pd.Series) -> tuple[object, ...]:
        remaining = _coerce_capacity_value(row.get("remaining_capacity", 0))
        allocations_new = _coerce_capacity_value(row.get("allocations_new", 0))
        mentor_token = row.get("mentor_sort_key")
        if mentor_token is None:
            mentor_token = natural_key(row.get("mentor_id_en", row.get("mentor_id")))
        return (-remaining, allocations_new, mentor_token)

    def refresh_candidates(self, ranked: pd.DataFrame) -> None:
        """Insert or update heap entries for the provided ranked frame."""

        for idx, row in ranked.iterrows():
            bucket_key = self._index_to_bucket.get(idx, self._default_bucket)
            version = self._versions.get(idx, 0) + 1
            self._versions[idx] = version
            priority = self._priority_from_row(row)
            heapq.heappush(self._buckets[bucket_key], (priority, version, idx))

    def _pop_bucket_order(
        self,
        bucket_key: tuple[int, ...] | tuple[str, ...],
        candidate_set: set[Hashable],
    ) -> list[Hashable]:
        ordered: list[Hashable] = []
        heap = self._buckets[bucket_key]
        temp: list[tuple[tuple[object, ...], int, Hashable]] = []
        target = len(candidate_set)
        while heap and len(ordered) < target:
            priority, version, idx = heapq.heappop(heap)
            if version != self._versions.get(idx):
                continue
            temp.append((priority, version, idx))
            if idx not in candidate_set:
                continue
            ordered.append(idx)
        for entry in temp:
            heapq.heappush(heap, entry)
        return ordered

    def order_indices(self, ranked: pd.DataFrame) -> list[Hashable]:
        """Return deterministic ordering for the provided ranked frame."""

        if ranked.empty:
            return []

        self.refresh_candidates(ranked)
        candidate_set = set(ranked.index)
        bucket_keys = {
            self._index_to_bucket.get(idx, self._default_bucket) for idx in candidate_set
        }
        ordered: list[Hashable] = []
        for bucket_key in sorted(bucket_keys):
            ordered.extend(self._pop_bucket_order(bucket_key, candidate_set))

        if len(ordered) < len(candidate_set):
            missing = [idx for idx in ranked.index if idx not in ordered]
            ordered.extend(missing)

        return ordered


CapacityScalar = int | float | str | None


def _safe_capacity(value: CapacityScalar) -> int:
    """Normalize capacity values to non-negative integers.

    Non-numeric inputs raise ``TypeError``; NaN values are treated as zero.
    """

    if value is None:
        return 0
    if isinstance(value, bool):
        numeric = int(value)
    elif isinstance(value, Number):
        if pd.isna(value):
            return 0
        numeric = int(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return 0
        try:
            numeric = int(float(text))
        except ValueError as exc:
            raise TypeError(f"Unsupported string value for capacity: {value!r}") from exc
    else:
        raise TypeError(f"Unsupported capacity value: {value!r}")
    return max(numeric, 0)


def compute_remaining_capacity(
    row: pd.Series, *, capacity_column: str = "remaining_capacity"
) -> int:
    """محاسبهٔ ظرفیت باقی‌ماندهٔ امن برای یک ردیف استخر."""

    if capacity_column not in row:
        return 0
    return _safe_capacity(row.get(capacity_column))


def build_mentor_state(
    pool_df: pd.DataFrame,
    *,
    capacity_column: str = "remaining_capacity",
    policy: PolicyConfig | None = None,
) -> dict[Hashable, MentorCapacityState]:
    """ساخت وضعیت ظرفیت اولیهٔ پشتیبان‌ها برای تخصیص و Rule Engine."""

    if policy is None:
        policy = load_policy()

    canonical = dedupe_columns(canonicalize_headers(pool_df, header_mode="en"))
    if "mentor_sort_key" not in canonical.columns and "mentor_id" in canonical.columns:
        canonical = canonical.copy()
        canonical["mentor_sort_key"] = canonical["mentor_id"].map(natural_key)
    sort_candidates = [
        column
        for column in ("occupancy_ratio", "allocations_new", "mentor_sort_key")
        if column in canonical.columns
    ]
    if sort_candidates:
        canonical = canonical.sort_values(
            by=sort_candidates,
            ascending=[True] * len(sort_candidates),
            kind="stable",
        ).reset_index(drop=True)
    if "mentor_id" not in canonical.columns:
        return {}

    candidates = [capacity_column]
    policy_defined = policy.columns.remaining_capacity
    if policy_defined not in candidates:
        candidates.append(policy_defined)
    canonical_candidate = canonicalize_headers(
        pd.DataFrame(columns=[capacity_column]), header_mode="en"
    ).columns[0]
    if canonical_candidate not in candidates:
        candidates.append(canonical_candidate)
    if "remaining_capacity" not in candidates:
        candidates.append("remaining_capacity")

    resolved_capacity: str | None = None
    for candidate in candidates:
        if candidate in canonical.columns:
            resolved_capacity = candidate
            break

    if resolved_capacity is None:
        return {}

    grouped = canonical.groupby("mentor_id", dropna=True)[resolved_capacity]
    initial = pd.to_numeric(grouped.max(), errors="coerce").fillna(0).astype(int)
    state: dict[Hashable, MentorCapacityState] = {}
    for mentor_id, capacity in initial.items():
        try:
            value = _safe_capacity(capacity)
        except TypeError:  # pragma: no cover - نگهبان ورودی غیرمنتظره
            value = 0
        state[mentor_id] = {
            "initial": value,
            "remaining": value,
            "alloc_new": 0,
            "occupancy_ratio": 0.0,
            "total_capacity": value,
            "current_allocations": 0,
            "remaining_capacity": value,
        }
    return state


def apply_ranking_policy(
    candidate_pool: pd.DataFrame,
    *,
    state: Mapping[Hashable, Mapping[str, CapacityScalar]] | None = None,
    policy: PolicyConfig | None = None,
    policy_path: str | Path = _DEFAULT_POLICY_PATH,
    heap_manager: HeapRankingManager | None = None,
) -> pd.DataFrame:
    """مرتب‌سازی استخر کاندید طبق RANK-CORE (ظرفیت‌محور)."""

    if candidate_pool.empty:
        ranked = candidate_pool.copy()
        ranked.attrs["fairness_strategy"] = "none"
        ranked.attrs["fairness_reason"] = None
        return ranked

    if policy is None:
        policy = load_policy(policy_path)

    ranked = ensure_ranking_columns(candidate_pool)
    en_view = dedupe_columns(canonicalize_headers(ranked, header_mode="en"))

    mentor_ids = en_view.get("mentor_id")
    if isinstance(mentor_ids, pd.DataFrame):
        mentor_ids = mentor_ids.iloc[:, 0]
    if mentor_ids is None:
        raise KeyError("candidate pool must include 'mentor_id' column after canonicalization")

    state_view: Mapping[Hashable, Mapping[str, CapacityScalar]]
    if state is not None:
        state_view = state
    else:
        state_source = en_view.copy()
        state_view = cast(
            Mapping[Hashable, Mapping[str, CapacityScalar]],
            build_mentor_state(state_source, policy=policy),
        )

    def _state_metric(mentor: Hashable, key: str, *, default: int = 0) -> int:
        entry = state_view.get(mentor)
        if entry is None:
            return default
        raw_value = entry.get(key)
        if raw_value is None:
            return default
        if isinstance(raw_value, (int, float, str, type(None))):
            try:
                return _safe_capacity(raw_value)
            except TypeError:  # pragma: no cover - نگهبان ورودی پیش‌بینی‌نشده
                return default
        return default

    def _series_as_int(series: pd.Series) -> pd.Series:
        numeric = pd.to_numeric(series, errors="coerce").fillna(0)
        clipped = numeric.clip(lower=0)
        return clipped.astype(int)

    remaining = mentor_ids.map(lambda mentor: _state_metric(mentor, "remaining"))
    allocations = mentor_ids.map(lambda mentor: _state_metric(mentor, "alloc_new"))

    remaining_int = _series_as_int(remaining)
    allocations_int = _series_as_int(allocations)

    ranked["occupancy_ratio"] = 0.0
    ranked["allocations_new"] = allocations_int
    ranked["remaining_capacity"] = remaining_int
    ranked["mentor_sort_key"] = mentor_ids.map(natural_key)
    ranked["mentor_id_en"] = mentor_ids

    if len(policy.ranking_rules) != 3:
        raise ValueError("policy.ranking_rules must define exactly three ranking rules")

    sort_columns = [rule.column for rule in policy.ranking_rules]
    ascending_flags = [rule.ascending for rule in policy.ranking_rules]
    if any("ratio" in column or "occupancy" in column for column in sort_columns):
        raise ValueError("Ranking columns must not include ratio-based metrics")

    ranking_mode = getattr(policy, "ranking_mode", "legacy_sort")
    if ranking_mode == "heap_queue" and heap_manager is not None:
        order = heap_manager.order_indices(ranked)
        ranked = ranked.loc[order]
    else:
        ranked = ranked.sort_values(
            by=sort_columns,
            ascending=ascending_flags,
            kind="mergesort",
        )

    strategy = getattr(policy, "fairness_strategy", "none")
    fairness_reason_obj: object | None = None

    if strategy != "none":
        tie_columns: tuple[str, ...] = ("remaining_capacity", "allocations_new")
        has_ties = ranked.duplicated(subset=list(tie_columns), keep=False).any()
        if has_ties:
            fair_ranked, applied = _apply_fairness_strategy(
                ranked,
                strategy=strategy,
                tie_columns=tie_columns,
            )
            if applied:
                ranked = fair_ranked
                fairness_reason_obj = ranked.attrs.get("fairness_reason") or build_reason(
                    ReasonCode.FAIRNESS_ORDER
                )

    ranked.attrs["fairness_strategy"] = strategy
    ranked.attrs["fairness_reason"] = fairness_reason_obj
    return ranked


def _coerce_capacity_value(value: CapacityScalar) -> int:
    """تبدیل امن مقادیر ظرفیت به عدد صحیح غیرمنفی."""

    try:
        return _safe_capacity(value)
    except TypeError:  # pragma: no cover - نگهبان ورودی غیرمنتظره
        return 0


def consume_capacity(
    state: dict[Hashable, MentorCapacityState], mentor_id: Hashable
) -> tuple[int, int, float]:
    """به‌روزرسانی ظرفیت پشتیبان پس از تخصیص و بازگشت ظرفیت قبل/بعد."""

    if mentor_id not in state:
        raise KeyError(f"Mentor '{mentor_id}' missing from state")
    entry = state[mentor_id]
    before = _coerce_capacity_value(entry.get("remaining", 0))
    if before <= 0:
        raise ValueError("CAPACITY_UNDERFLOW")
    after = before - 1
    if after < 0:
        raise ValueError("CAPACITY_UNDERFLOW")
    entry["remaining"] = after
    entry["alloc_new"] = _coerce_capacity_value(entry.get("alloc_new", 0)) + 1
    entry["remaining_capacity"] = after
    entry["current_allocations"] = _coerce_capacity_value(entry.get("current_allocations", 0)) + 1
    initial = _coerce_capacity_value(entry.get("initial", before))
    if initial <= 0:
        initial = max(before, 1)
    entry["total_capacity"] = max(
        initial, _coerce_capacity_value(entry.get("total_capacity", initial))
    )
    entry["occupancy_ratio"] = 0.0
    return before, after, entry["occupancy_ratio"]


_FAIRNESS_COUNTER_CANDIDATES: tuple[str, ...] = (
    "counter",
    "allocation_counter",
    "student_id",
    "row_number",
    "شمارنده",
)


def _hash_counter_series(series: pd.Series) -> pd.Series:
    from app.core.counter import stable_counter_hash, validate_counter

    def _hash(value: object) -> int:
        text = str(value or "").strip()
        if not text:
            text = "0"
        try:
            normalized = validate_counter(text)
        except ValueError:
            fallback = re.sub(r"\D", "", text) or text or "0"
            digest = blake2b(fallback.encode("utf-8"), digest_size=8)
            return int.from_bytes(digest.digest(), "big")
        return stable_counter_hash(normalized)

    return series.map(_hash)


def _apply_deterministic_jitter(df: pd.DataFrame) -> pd.DataFrame:
    source: pd.Series | None = None
    for column in _FAIRNESS_COUNTER_CANDIDATES:
        if column in df.columns:
            source = df[column].astype("string")
            break
    if source is None:
        source = df.index.astype("string")
    jitter = _hash_counter_series(source)
    df = df.assign(__fairness_key__=jitter)
    df = df.sort_values("__fairness_key__", kind="stable")
    return df.drop(columns=["__fairness_key__"])


def _hash_text(value: object) -> int:
    text = str(value or "").strip() or "0"
    digest = blake2b(text.encode("utf-8"), digest_size=8)
    return int.from_bytes(digest.digest(), "big")


def _apply_round_robin(df: pd.DataFrame) -> pd.DataFrame:
    if "mentor_id_en" not in df.columns:
        return df
    working = df.copy()
    working["__fairness_key__"] = working["mentor_id_en"].astype("string").map(_hash_text)
    working = working.sort_values("__fairness_key__", kind="stable")
    return working.drop(columns=["__fairness_key__"])


def _apply_fairness_strategy(
    ranked: pd.DataFrame,
    *,
    strategy: str,
    tie_columns: Sequence[str],
) -> tuple[pd.DataFrame, bool]:
    """اعمال استراتژی عدالت فقط درون گره‌های تساوی ظرفیت."""

    if strategy == "none" or ranked.empty or not tie_columns:
        return ranked, False

    groups = ranked.groupby(list(tie_columns), sort=False, group_keys=False)
    frames: list[pd.DataFrame] = []
    applied = False

    for _, block in groups:
        if len(block) <= 1:
            frames.append(block)
            continue
        original_index = tuple(block.index)
        if strategy == "deterministic_jitter":
            reordered = _apply_deterministic_jitter(block)
        elif strategy == "round_robin":
            reordered = _apply_round_robin(block)
        else:
            return ranked, False
        if tuple(reordered.index) != original_index:
            applied = True
        frames.append(reordered)

    if not frames:
        return ranked, False

    merged = pd.concat(frames, axis=0)
    if applied:
        merged.attrs["fairness_reason"] = build_reason(ReasonCode.FAIRNESS_ORDER)
    return merged, applied

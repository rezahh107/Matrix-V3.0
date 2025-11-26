from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, TypedDict, cast

import pandas as pd

from app.core.allocate_students import (
    _canonical_stage_counts,
    _collect_join_key_map,
    _filter_candidates_by_join_map,
)
from app.core.common.filters import apply_join_filters
from app.core.common.types import CANONICAL_TRACE_ORDER, TraceStageName
from app.core.policy_loader import PolicyConfig, load_policy

JoinKeyName = str


class JoinKeyMismatchDetail(TypedDict):
    """Details of a join-key mismatch between student and mentor pool."""

    column: JoinKeyName
    student_value: int | None
    mentor_value: int | None
    mismatch_type: Literal["student_missing", "mentor_missing", "value_mismatch"]


class StageCounts(TypedDict):
    """Candidate counts after each logical stage."""

    type: int
    group: int
    gender: int
    graduation_status: int
    center: int
    finance: int
    school: int
    capacity_gate: int


class PoolAlignmentReport(TypedDict):
    """Main per-student alignment report."""

    student_id: str
    join_key_values: dict[JoinKeyName, int | None]
    stage_counts: StageCounts
    candidate_count_initial: int
    candidate_count_final: int
    join_key_mismatches: list[JoinKeyMismatchDetail]
    missing_pool_indexes: list[int]
    error: str | None


def _empty_stage_counts() -> StageCounts:
    return cast(
        StageCounts,
        {stage: 0 for stage in CANONICAL_TRACE_ORDER},
    )


def _build_join_key_values(
    join_map: Mapping[str, int], policy: PolicyConfig
) -> dict[JoinKeyName, int | None]:
    values: dict[JoinKeyName, int | None] = {}
    for column in policy.join_keys:
        normalized = column.replace(" ", "_")
        raw_value = join_map.get(normalized)
        if raw_value is None or raw_value < 0:
            values[column] = None
        else:
            values[column] = int(raw_value)
    return values


def _capacity_filter(candidates: pd.DataFrame, *, policy: PolicyConfig) -> tuple[pd.DataFrame, int]:
    capacity_column = policy.capacity_column
    if capacity_column not in candidates.columns:
        return candidates.iloc[0:0], 0
    filtered = candidates.loc[candidates[capacity_column] > 0]
    return filtered, int(filtered.shape[0])


def _unique_missing_indexes(frame: pd.DataFrame, columns: list[str]) -> list[int]:
    indexes: list[int] = []
    for column in columns:
        if column not in frame.columns:
            continue
        missing_mask = frame[column].isna()
        if missing_mask.any():
            indexes.extend(frame.index[missing_mask].tolist())
    unique_indexes: list[int] = []
    for value in sorted(dict.fromkeys(indexes)):
        try:
            unique_indexes.append(int(value))
        except (TypeError, ValueError):
            continue
    return unique_indexes


def _convert_mismatches(
    mismatches: list[dict[str, object]],
    *,
    policy: PolicyConfig,
    join_map: Mapping[str, int],
    pool: pd.DataFrame,
) -> list[JoinKeyMismatchDetail]:
    results: list[JoinKeyMismatchDetail] = []
    normalized_to_original = {column.replace(" ", "_"): column for column in policy.join_keys}
    for item in mismatches:
        column_raw = str(item.get("column", ""))
        column = normalized_to_original.get(column_raw, column_raw)
        student_value_raw = join_map.get(column_raw)
        mentor_values = item.get("mentor_values")
        mentor_value = None
        if isinstance(mentor_values, list) and mentor_values:
            try:
                mentor_value = int(mentor_values[0])
            except (TypeError, ValueError):
                mentor_value = None
        if item.get("reason") == "student_join_key_missing":
            mismatch_type: Literal["student_missing", "mentor_missing", "value_mismatch"] = (
                "student_missing"
            )
            student_value = None
        elif item.get("reason") == "mentor_column_missing":
            mismatch_type = "mentor_missing"
            student_value = int(student_value_raw) if student_value_raw is not None else None
        else:
            mismatch_type = "value_mismatch"
            student_value = int(student_value_raw) if student_value_raw is not None else None
        results.append(
            {
                "column": column,
                "student_value": student_value,
                "mentor_value": mentor_value,
                "mismatch_type": mismatch_type,
            }
        )
    missing_columns = [
        column
        for column in policy.join_keys
        if column not in pool.columns and column not in {detail["column"] for detail in results}
    ]
    for column in missing_columns:
        normalized = column.replace(" ", "_")
        student_value_raw = join_map.get(normalized)
        results.append(
            {
                "column": column,
                "student_value": (
                    int(student_value_raw)
                    if student_value_raw is not None and student_value_raw >= 0
                    else None
                ),
                "mentor_value": None,
                "mismatch_type": "mentor_missing",
            }
        )
    return results


def _mentors_match_value(
    pool: pd.DataFrame,
    column: str,
    student_value: int,
    *,
    policy: PolicyConfig,
) -> bool:
    if column not in pool.columns:
        return False
    series = pd.to_numeric(pool[column], errors="coerce").astype("Int64")
    if column == policy.stage_column("center"):
        wildcard = _coerce_optional_int(policy.center_map.get("*"))
        mentor_centers = series.dropna().astype(int)
        if wildcard is not None and student_value == wildcard:
            return True
        if (mentor_centers == student_value).any():
            return True
        return bool(wildcard is not None and (mentor_centers == wildcard).any())
    if column == policy.columns.school_code:
        mentor_schools = series.dropna().astype(int)
        if policy.school_code_empty_as_zero and student_value == 0:
            return True
        if policy.school_code_empty_as_zero and (mentor_schools == 0).any():
            return True
        return bool((mentor_schools == student_value).any())
    return bool((series == student_value).any())


def _coerce_optional_int(value: object | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return int(float(text))
        except ValueError:
            return None
    return None


def analyze_pool_alignment_for_student(
    student: Mapping[str, object],
    candidate_pool: pd.DataFrame,
    *,
    policy: PolicyConfig | None = None,
    pool_state_view: pd.DataFrame | None = None,
) -> PoolAlignmentReport:
    """Analyze join-key alignment and stage counts for a single student."""

    resolved_policy = policy or load_policy()
    stage_counts: StageCounts = _empty_stage_counts()
    join_map, missing_columns = _collect_join_key_map(student, resolved_policy)
    join_key_values = _build_join_key_values(join_map, resolved_policy)

    candidate_count_initial = int(candidate_pool.shape[0])
    tracker_counts: dict[TraceStageName, int] = {stage: 0 for stage in CANONICAL_TRACE_ORDER}

    def _record(stage: str, count: int) -> None:
        stage_name = cast(TraceStageName, stage)
        tracker_counts[stage_name] = int(count)

    try:
        eligible_after_join = apply_join_filters(
            candidate_pool,
            student,
            policy=resolved_policy,
            student_join_map=join_map,
            tracker=_record,
        )
    except Exception as exc:  # pragma: no cover - guarded by batch wrapper
        return {
            "student_id": str(student.get("student_id", "")),
            "join_key_values": join_key_values,
            "stage_counts": stage_counts,
            "candidate_count_initial": candidate_count_initial,
            "candidate_count_final": 0,
            "join_key_mismatches": [],
            "missing_pool_indexes": [],
            "error": str(exc),
        }

    matched_candidates, mismatch_details = _filter_candidates_by_join_map(
        eligible_after_join, join_map=join_map, policy=resolved_policy
    )

    _, capacity_count = _capacity_filter(matched_candidates, policy=resolved_policy)

    stage_counts = cast(
        StageCounts,
        {
            **_canonical_stage_counts(tracker_counts),
            "capacity_gate": capacity_count,
        },
    )

    join_key_mismatches = _convert_mismatches(
        mismatch_details,
        policy=resolved_policy,
        join_map=join_map,
        pool=candidate_pool,
    )

    for column in missing_columns:
        join_key_mismatches.append(
            {
                "column": column,
                "student_value": None,
                "mentor_value": None,
                "mismatch_type": "student_missing",
            }
        )

    for column, value in join_key_values.items():
        if value is None:
            continue
        if not _mentors_match_value(candidate_pool, column, value, policy=resolved_policy):
            join_key_mismatches.append(
                {
                    "column": column,
                    "student_value": value,
                    "mentor_value": None,
                    "mismatch_type": "value_mismatch",
                }
            )

    missing_pool_indexes = _unique_missing_indexes(candidate_pool, resolved_policy.join_keys)

    return {
        "student_id": str(student.get("student_id", "")),
        "join_key_values": join_key_values,
        "stage_counts": stage_counts,
        "candidate_count_initial": candidate_count_initial,
        "candidate_count_final": capacity_count,
        "join_key_mismatches": join_key_mismatches,
        "missing_pool_indexes": missing_pool_indexes,
        "error": None,
    }


def analyze_pool_alignment_batch(
    students: pd.DataFrame,
    candidate_pool: pd.DataFrame,
    *,
    policy: PolicyConfig | None = None,
    pool_state_view: pd.DataFrame | None = None,
    limit: int | None = None,
) -> list[PoolAlignmentReport]:
    """Run alignment analysis for a deterministic subset of students."""

    resolved_policy = policy or load_policy()
    if "student_id" in students.columns:
        ordered_students = students.sort_values("student_id", kind="stable")
    else:
        ordered_students = students.copy()
    if limit is not None and limit > 0:
        ordered_students = ordered_students.head(limit)

    reports: list[PoolAlignmentReport] = []
    for _, row in ordered_students.iterrows():
        student_mapping = row.to_dict()
        try:
            report = analyze_pool_alignment_for_student(
                student_mapping,
                candidate_pool,
                policy=resolved_policy,
                pool_state_view=pool_state_view,
            )
        except Exception as exc:  # pragma: no cover - defensive per specs
            reports.append(
                {
                    "student_id": str(student_mapping.get("student_id", "")),
                    "join_key_values": {},
                    "stage_counts": _empty_stage_counts(),
                    "candidate_count_initial": int(candidate_pool.shape[0]),
                    "candidate_count_final": 0,
                    "join_key_mismatches": [],
                    "missing_pool_indexes": [],
                    "error": str(exc),
                }
            )
            continue
        reports.append(report)
    return reports

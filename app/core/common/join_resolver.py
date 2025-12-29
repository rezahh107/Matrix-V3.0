"""Resolve effective join keys for student matching (Core-only)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

import pandas as pd

from app.core.common.columns import CANON_EN_TO_FA
from app.core.common.join_keys import (
    JoinKeyCanonicalizationError,
    StudentSchoolCode,
    canonicalize_join_key_value,
    coerce_school_candidate,
    normalize_join_key_name,
    resolve_finance_variants,
)
from app.core.common.normalization import normalize_fa
from app.core.common.types import JoinKeySource, JoinKeySourceMap
from app.core.policy_loader import PolicyConfig

CenterSource = Literal[
    "raw",
    "manager_exact",
    "manager_substring",
    "manager_wildcard",
    "missing",
]

FinanceSource = Literal[
    "raw",
    "join_map",
    "missing",
    "invalid",
]

@dataclass(frozen=True, slots=True)
class EffectiveJoinKeys:
    center_code: int | None
    center_source: CenterSource


@dataclass(frozen=True, slots=True)
class EffectiveFinanceKeys:
    finance_code: int | None
    finance_variants: frozenset[int]
    finance_source: FinanceSource


class JoinKeyResolver:
    """Resolve student join keys with deterministic inference for center."""

    def __init__(self, policy: PolicyConfig) -> None:
        self._policy = policy
        self._center_map = _normalize_center_map(policy.center_map)

    def resolve_center(
        self,
        student: Mapping[str, object],
        *,
        student_join_map: Mapping[str, int] | None = None,
    ) -> EffectiveJoinKeys:
        center_column = self._policy.stage_column("center")
        normalized = normalize_join_key_name(center_column)
        center_value = _center_from_join_map(student_join_map, normalized)
        if center_value is None:
            center_value = _center_from_student(student, center_column, policy=self._policy)
        if center_value is None:
            return EffectiveJoinKeys(center_code=None, center_source="missing")
        if center_value != 0:
            return EffectiveJoinKeys(center_code=center_value, center_source="raw")
        inferred = self._infer_center_from_manager(student)
        if inferred is not None:
            return inferred
        return EffectiveJoinKeys(center_code=center_value, center_source="raw")

    def resolve_finance(
        self,
        student: Mapping[str, object],
        *,
        student_join_map: Mapping[str, int] | None = None,
    ) -> EffectiveFinanceKeys:
        column = self._policy.stage_column("finance")
        normalized = normalize_join_key_name(column)
        join_value = _value_from_join_map(student_join_map, normalized)
        if join_value is not None:
            variants = resolve_finance_variants(join_value, self._policy)
            return EffectiveFinanceKeys(
                finance_code=join_value,
                finance_variants=variants,
                finance_source="join_map",
            )
        raw = _student_value_optional(student, column)
        if raw is None:
            return EffectiveFinanceKeys(
                finance_code=None,
                finance_variants=frozenset(),
                finance_source="missing",
            )
        try:
            finance_value = canonicalize_join_key_value(column, raw, policy=self._policy)
        except JoinKeyCanonicalizationError:
            return EffectiveFinanceKeys(
                finance_code=None,
                finance_variants=frozenset(),
                finance_source="invalid",
            )
        return EffectiveFinanceKeys(
            finance_code=finance_value,
            finance_variants=resolve_finance_variants(finance_value, self._policy),
            finance_source="raw",
        )

    def resolve_school(
        self,
        student: Mapping[str, object],
        *,
        student_join_map: Mapping[str, int] | None = None,
    ) -> StudentSchoolCode:
        column = self._policy.stage_column("school")
        normalized = normalize_join_key_name(column)
        allow_zero = (
            self._policy.school_code_empty_as_zero and column == self._policy.columns.school_code
        )
        join_value = _value_from_join_map(student_join_map, normalized)
        if join_value is not None:
            wildcard = bool(allow_zero and join_value == 0)
            return StudentSchoolCode(value=join_value, missing=False, wildcard=wildcard)

        normalized_column = column.replace(" ", "_")
        candidate_keys = (
            column,
            normalized_column,
            "school_code_norm",
            "school_code",
            "school_code_raw",
        )
        candidates: list[object] = []
        for key in candidate_keys:
            if key in student:
                candidates.append(student[key])

        for candidate in candidates:
            value, missing = coerce_school_candidate(candidate)
            if not missing:
                wildcard = bool(allow_zero and value == 0)
                return StudentSchoolCode(value=value, missing=False, wildcard=wildcard)

        if allow_zero:
            return StudentSchoolCode(value=0, missing=False, wildcard=True)
        return StudentSchoolCode(value=None, missing=True, wildcard=False)

    def _infer_center_from_manager(
        self, student: Mapping[str, object]
    ) -> EffectiveJoinKeys | None:
        if not self._center_map:
            return None
        manager_name = _extract_manager_name(student)
        normalized_manager = normalize_fa(manager_name)
        if not normalized_manager:
            return None
        if normalized_manager in self._center_map and normalized_manager != "*":
            return EffectiveJoinKeys(
                center_code=self._center_map[normalized_manager],
                center_source="manager_exact",
            )
        matches = [
            key
            for key in self._center_map
            if key not in ("*", "") and key in normalized_manager
        ]
        if matches:
            best_key = min(matches, key=lambda key: (-len(key), key))
            return EffectiveJoinKeys(
                center_code=self._center_map[best_key],
                center_source="manager_substring",
            )
        wildcard = self._center_map.get("*")
        if wildcard is not None:
            return EffectiveJoinKeys(
                center_code=wildcard,
                center_source="manager_wildcard",
            )
        return None


def resolve_join_key_sources(
    student: Mapping[str, object],
    *,
    policy: PolicyConfig,
    student_join_map: Mapping[str, int] | None = None,
) -> JoinKeySourceMap:
    def _resolve_basic(column: str) -> JoinKeySource:
        return _resolve_basic_source(
            column,
            student,
            policy,
            student_join_map,
        )

    resolver = JoinKeyResolver(policy)
    center = resolver.resolve_center(student, student_join_map=student_join_map)
    finance = resolver.resolve_finance(student, student_join_map=student_join_map)
    school_source = _resolve_school_source(student, policy, student_join_map)
    return {
        "group_source": _resolve_basic(policy.stage_column("group")),
        "gender_source": _resolve_basic(policy.stage_column("gender")),
        "graduation_status_source": _resolve_basic(policy.stage_column("graduation_status")),
        "center_source": center.center_source,
        "finance_source": finance.finance_source,
        "school_source": school_source,
    }


def _center_from_join_map(
    join_map: Mapping[str, int] | None, normalized_column: str
) -> int | None:
    if join_map is None:
        return None
    value = join_map.get(normalized_column)
    if value is None or value < 0:
        return None
    return int(value)


def _source_from_join_map(
    join_map: Mapping[str, int] | None, normalized_column: str
) -> JoinKeySource | None:
    if join_map is None:
        return None
    value = join_map.get(normalized_column)
    if value is None:
        return None
    if value == -1:
        return "missing"
    if value == -2:
        return "invalid"
    return "raw"


def _value_from_join_map(
    join_map: Mapping[str, int] | None, normalized_column: str
) -> int | None:
    if join_map is None:
        return None
    value = join_map.get(normalized_column)
    if value is None or value < 0:
        return None
    return int(value)


def _center_from_student(
    student: Mapping[str, object], column: str, *, policy: PolicyConfig
) -> int | None:
    raw = _student_value_optional(student, column)
    if raw is None:
        return None
    try:
        return canonicalize_join_key_value(column, raw, policy=policy)
    except JoinKeyCanonicalizationError:
        return None


def _student_value_optional(student: Mapping[str, object], column: str) -> object | None:
    for key in (column, column.replace(" ", "_")):
        if key in student:
            return student[key]
    return None


def _is_missing_value(value: object) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        return not value.strip()
    return False


def _resolve_basic_source(
    column: str,
    student: Mapping[str, object],
    policy: PolicyConfig,
    student_join_map: Mapping[str, int] | None,
) -> JoinKeySource:
    normalized = normalize_join_key_name(column)
    source = _source_from_join_map(student_join_map, normalized)
    if source in {"missing", "invalid"}:
        return source
    value = _student_value_optional(student, column)
    if _is_missing_value(value):
        return "missing"
    try:
        canonicalize_join_key_value(column, value, policy=policy)
    except JoinKeyCanonicalizationError:
        return "invalid"
    return "raw"


def _resolve_school_source(
    student: Mapping[str, object],
    policy: PolicyConfig,
    student_join_map: Mapping[str, int] | None,
) -> JoinKeySource:
    column = policy.columns.school_code
    normalized = normalize_join_key_name(column)
    source = _source_from_join_map(student_join_map, normalized)
    if source in {"missing", "invalid"}:
        return source
    raw_value = _student_value_optional(student, column)
    if _is_missing_value(raw_value):
        return "defaulted_zero" if policy.school_code_empty_as_zero else "missing"
    return "raw"


def _extract_manager_name(student: Mapping[str, object]) -> str:
    manager_candidates = (
        "مدیر",
        CANON_EN_TO_FA.get("manager_name", "نام مدیر"),
        "manager",
        "manager_name",
    )
    for key in manager_candidates:
        if key in student:
            raw = student.get(key)
            if raw is None or raw is pd.NA:
                return ""
            return str(raw).strip()
    return ""


def _normalize_center_map(center_map: Mapping[str, int]) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for raw_key, raw_val in center_map.items():
        key = str(raw_key).strip()
        norm_key = "*" if key == "*" else normalize_fa(key)
        if not norm_key:
            continue
        try:
            normalized[norm_key] = int(raw_val)
        except (TypeError, ValueError):
            continue
    return normalized


__all__ = [
    "CenterSource",
    "EffectiveFinanceKeys",
    "EffectiveJoinKeys",
    "FinanceSource",
    "JoinKeyResolver",
    "JoinKeySource",
    "JoinKeySourceMap",
    "StudentSchoolCode",
    "resolve_join_key_sources",
]

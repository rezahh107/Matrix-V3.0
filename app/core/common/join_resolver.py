"""Resolve effective join keys for student matching (Core-only)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

import pandas as pd

from app.core.common.columns import CANON_EN_TO_FA
from app.core.common.join_keys import (
    JoinKeyCanonicalizationError,
    canonicalize_join_key_value,
    normalize_join_key_name,
)
from app.core.common.normalization import normalize_fa
from app.core.policy_loader import PolicyConfig

CenterSource = Literal[
    "raw",
    "manager_exact",
    "manager_substring",
    "manager_wildcard",
    "missing",
]


@dataclass(frozen=True, slots=True)
class EffectiveJoinKeys:
    center_code: int | None
    center_source: CenterSource


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
            if key not in ("*", "") and normalized_manager and key in normalized_manager
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


def _center_from_join_map(
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


__all__ = ["CenterSource", "EffectiveJoinKeys", "JoinKeyResolver"]

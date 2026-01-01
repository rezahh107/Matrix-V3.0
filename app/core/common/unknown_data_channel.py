"""Central channel for handling unknown data decisions (Core-only)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

from app.core.common.columns import ensure_series
from app.core.common.join_keys import JoinKeyCanonicalizationError, canonicalize_join_key_value
from app.core.policy_loader import PolicyConfig

UnknownEntityType = Literal["pool", "student", "mentor"]


@dataclass(frozen=True, slots=True)
class UnknownIssue:
    """Serializable record for unknown/unsupported data observations."""

    code: str
    entity_type: UnknownEntityType
    column: str | None
    row_index: int | None
    raw_value: object | None
    error_code: str | None = None
    details: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "code": self.code,
            "entity_type": self.entity_type,
            "column": self.column,
            "row_index": self.row_index,
            "raw_value": self.raw_value,
            "error_code": self.error_code,
        }
        if self.details:
            payload["details"] = dict(self.details)
        return payload


class UnknownDataError(ValueError):
    """Raised when unknown data is encountered in strict mode."""

    def __init__(self, issues: Sequence[UnknownIssue]) -> None:
        self.issues = list(issues)
        super().__init__(f"Unknown data encountered: {len(self.issues)} issue(s)")


@dataclass(slots=True)
class UnknownDataChannel:
    """Aggregate unknown data issues and optionally fail fast."""

    strict: bool
    _issues: list[UnknownIssue] = field(default_factory=list, init=False, repr=False)

    def report(self, issues: Sequence[UnknownIssue]) -> None:
        if not issues:
            return
        ordered = sorted(issues, key=_issue_sort_key)
        if self.strict:
            raise UnknownDataError(ordered)
        self._issues.extend(ordered)

    @property
    def issues(self) -> tuple[UnknownIssue, ...]:
        return tuple(self._issues)

    def to_payload(self) -> list[dict[str, object]]:
        return [issue.to_dict() for issue in self._issues]

    @classmethod
    def from_policy(cls, policy: PolicyConfig) -> UnknownDataChannel:
        strict = str(getattr(policy, "unknown_data_mode", "issue")).lower() == "strict"
        return cls(strict=strict)


def validate_pool_join_keys(
    pool: pd.DataFrame,
    *,
    policy: PolicyConfig,
    channel: UnknownDataChannel,
) -> None:
    issues: list[UnknownIssue] = []
    join_key_columns = list(policy.join_keys)
    row_positions = pd.Series(range(len(pool)), index=pool.index)

    for column in join_key_columns:
        if column not in pool.columns:
            issues.append(
                UnknownIssue(
                    code="MISSING_JOIN_KEY_COLUMN",
                    entity_type="pool",
                    column=column,
                    row_index=None,
                    raw_value=None,
                )
            )
            continue
        series = ensure_series(pool[column])
        for index, raw_value in series.items():
            try:
                canonicalize_join_key_value(column, raw_value, policy=policy)
            except JoinKeyCanonicalizationError as exc:
                error_code = "DATA_INVALID"
                inner = exc.__cause__
                if isinstance(inner, ValueError):
                    error_code = inner.args[0] if inner.args else "DATA_INVALID"
                issues.append(
                    UnknownIssue(
                        code="UNKNOWN_JOIN_KEY_VALUE",
                        entity_type="pool",
                        column=column,
                        row_index=int(row_positions[index]),
                        raw_value=raw_value,
                        error_code=str(error_code),
                    )
                )

    channel.report(issues)


def validate_join_key_columns_numeric(
    frame: pd.DataFrame,
    *,
    join_keys: Sequence[str],
    entity_type: UnknownEntityType,
    channel: UnknownDataChannel,
) -> None:
    issues: list[UnknownIssue] = []
    row_positions = pd.Series(range(len(frame)), index=frame.index)
    for column in join_keys:
        if column not in frame.columns:
            issues.append(
                UnknownIssue(
                    code="MISSING_JOIN_KEY_COLUMN",
                    entity_type=entity_type,
                    column=column,
                    row_index=None,
                    raw_value=None,
                )
            )
            continue
        series = ensure_series(frame[column])
        numeric = pd.to_numeric(series, errors="coerce")
        for index, raw_value in series.items():
            if _is_missing_value(raw_value):
                issues.append(
                    UnknownIssue(
                        code="MISSING_JOIN_KEY_VALUE",
                        entity_type=entity_type,
                        column=column,
                        row_index=int(row_positions[index]),
                        raw_value=raw_value,
                        error_code="DATA_MISSING",
                    )
                )
                continue
            if pd.isna(numeric.loc[index]):
                issues.append(
                    UnknownIssue(
                        code="UNKNOWN_JOIN_KEY_VALUE",
                        entity_type=entity_type,
                        column=column,
                        row_index=int(row_positions[index]),
                        raw_value=raw_value,
                        error_code="DATA_INVALID",
                    )
                )
    channel.report(issues)


def _is_missing_value(value: object) -> bool:
    if value is None:
        return True
    try:
        if bool(pd.isna(value)):
            return True
    except TypeError:
        pass
    if isinstance(value, str):
        return not value.strip()
    return False


def _issue_sort_key(issue: UnknownIssue) -> tuple[int, int, str, str, str]:
    column = issue.column or ""
    row_index = -1 if issue.row_index is None else int(issue.row_index)
    raw_value = repr(issue.raw_value)
    return (
        _entity_priority(issue.entity_type),
        row_index,
        column,
        issue.code,
        raw_value,
    )


def _entity_priority(entity: UnknownEntityType) -> int:
    order = {"student": 0, "pool": 1, "mentor": 2}
    return order.get(entity, 99)

"""Runtime health indicator derived from QA results.

This module lives in Infra to keep observability separate from domain rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from app.core.qa.invariants import QaReport


class RuntimeHealthState(str, Enum):
    """Finite health states for a QA run."""

    OK = "OK"
    WARN = "WARN"
    ERROR = "ERROR"


@dataclass(frozen=True)
class RuntimeHealthIndicator:
    """Derived health summary based on QA severity counts."""

    status: RuntimeHealthState
    severity_counts: Mapping[str, int]


def _normalize_severity(level: str) -> str:
    """Map arbitrary QA levels to canonical P0/P1/P2 buckets."""

    normalized = level.strip().lower()
    if normalized in {"p0", "error", "critical"}:
        return "P0"
    if normalized in {"p1", "warn", "warning"}:
        return "P1"
    return "P2"


def derive_runtime_health(report: QaReport) -> RuntimeHealthIndicator:
    """Compute runtime health indicator from QA report severities.

    Mapping rules (deterministic):
    - P0 > 0 → ERROR
    - P0 == 0 and P1 > 0 → WARN
    - otherwise → OK
    """

    counts: dict[str, int] = {"P0": 0, "P1": 0, "P2": 0}
    for violation in report.violations:
        severity = _normalize_severity(violation.level)
        counts[severity] = counts.get(severity, 0) + 1

    if counts["P0"] > 0:
        status = RuntimeHealthState.ERROR
    elif counts["P1"] > 0:
        status = RuntimeHealthState.WARN
    else:
        status = RuntimeHealthState.OK

    return RuntimeHealthIndicator(status=status, severity_counts=counts)


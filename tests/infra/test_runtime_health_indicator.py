from __future__ import annotations

from app.core.qa.invariants import QaReport, QaRuleResult, QaViolation
from app.infra.qa.health_status import (
    RuntimeHealthState,
    derive_runtime_health,
)


def _report_with_levels(levels: list[str]) -> QaReport:
    violations = [
        QaViolation(rule_id="QA_TEST", level=level, message="msg", details=None)
        for level in levels
    ]
    result = QaRuleResult(rule_id="QA_TEST", passed=not bool(levels), violations=violations)
    return QaReport(results=[result])


def test_health_ok_with_no_violations() -> None:
    report = _report_with_levels([])

    indicator = derive_runtime_health(report)

    assert indicator.status is RuntimeHealthState.OK
    assert indicator.severity_counts == {"P0": 0, "P1": 0, "P2": 0}


def test_health_warn_when_only_p1() -> None:
    report = _report_with_levels(["P1"])

    indicator = derive_runtime_health(report)

    assert indicator.status is RuntimeHealthState.WARN
    assert indicator.severity_counts["P1"] == 1


def test_health_error_when_any_p0() -> None:
    report = _report_with_levels(["error", "P1"])

    indicator = derive_runtime_health(report)

    assert indicator.status is RuntimeHealthState.ERROR
    assert indicator.severity_counts["P0"] == 1
    assert indicator.severity_counts["P1"] == 1


def test_unknown_levels_fall_back_to_p2() -> None:
    report = _report_with_levels(["note"])

    indicator = derive_runtime_health(report)

    assert indicator.status is RuntimeHealthState.OK
    assert indicator.severity_counts == {"P0": 0, "P1": 0, "P2": 1}


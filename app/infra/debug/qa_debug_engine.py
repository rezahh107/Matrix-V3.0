"""Observe-only QA debug helpers scoped to QA_RULE_MENTOR_TYPE_01."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import pandas as pd

from app.core.policy_loader import PolicyConfig
from app.core.qa.invariants import QaReport, QaRuleResult
from app.core.qa.rules import QA_RULE_MENTOR_TYPE_01, RuleId, get_rule_definitions

__all__ = ["QADebugStory", "explain_rule", "explain_report"]


@dataclass(frozen=True)
class QADebugStory:
    """Structured debug output for a single QA rule."""

    rule_id: RuleId
    law_refs: tuple[str, ...]
    severity: str
    evidence: str
    context: Mapping[str, object]
    story: tuple[str, ...]


def explain_rule(
    rule_result: QaRuleResult,
    *,
    matrix: pd.DataFrame | None,
    policy: PolicyConfig,
) -> QADebugStory | None:
    """Return a minimal debug story for QA_RULE_MENTOR_TYPE_01.

    The engine is intentionally narrow for v0: only mentor-type violations are
    explained. The provided ``matrix`` is consumed directly without any reload or
    recomputation so that the QA runner and debug view share identical objects.
    """

    if rule_result.rule_id != QA_RULE_MENTOR_TYPE_01:
        return None
    if rule_result.passed:
        return None
    return _explain_mentor_type(rule_result=rule_result, matrix=matrix, _policy=policy)


def explain_report(
    report: QaReport,
    *,
    matrix: pd.DataFrame | None,
    policy: PolicyConfig,
) -> list[QADebugStory]:
    """Build debug stories for all supported rules in the QA report."""

    stories: list[QADebugStory] = []
    for result in report.results:
        story = explain_rule(rule_result=result, matrix=matrix, policy=policy)
        if story is not None:
            stories.append(story)
    return stories


def _explain_mentor_type(
    *,
    rule_result: QaRuleResult,
    matrix: pd.DataFrame | None,
    _policy: PolicyConfig,
) -> QADebugStory | None:
    if matrix is None:
        return None

    law_refs = get_rule_definitions()[QA_RULE_MENTOR_TYPE_01].law_mapping.law_refs
    violations = tuple(rule_result.violations)

    combined_details_list: dict[str, list] = {}
    for violation in violations:
        if violation.details:
            for key, value in violation.details.items():
                if key not in combined_details_list:
                    combined_details_list[key] = []
                if isinstance(value, (list, tuple)):
                    combined_details_list[key].extend(value)
                else:
                    combined_details_list[key].append(value)

    combined_details: dict[str, object] = {
        key: tuple(dict.fromkeys(values)) for key, values in combined_details_list.items()
    }
    combined_details["matrix_rows"] = int(len(matrix))
    marker = matrix.attrs.get("qa_debug_marker")
    if marker is not None:
        combined_details["matrix_marker"] = marker

    evidence_parts = tuple(violation.message for violation in violations)
    evidence = "; ".join(dict.fromkeys(evidence_parts)) if evidence_parts else ""
    story_lines = (
        f"🔴 {QA_RULE_MENTOR_TYPE_01} / {', '.join(law_refs) if law_refs else 'LAW-MENTOR-TYPE-01'}",
        f"Evidence: {evidence}",
        "Why: منتور باید دقیقا یکی از انواع عادی/مدرسه‌ای با alias هم‌راستا با school_code داشته باشد.",
        "Next: سطرهای گزارش‌شده را در ماتریس اصلاح و دوباره QA را اجرا کنید.",
    )

    return QADebugStory(
        rule_id=QA_RULE_MENTOR_TYPE_01,
        law_refs=law_refs,
        severity="error",
        evidence=evidence,
        context=MappingProxyType(combined_details),
        story=story_lines,
    )

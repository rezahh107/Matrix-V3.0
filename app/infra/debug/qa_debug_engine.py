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
    if not violations:
        return None

    combined_details: dict[str, object] = {}
    for violation in violations:
        if violation.details:
            combined_details.update(violation.details)
    combined_details["matrix_rows"] = int(len(matrix))
    marker = matrix.attrs.get("qa_debug_marker")
    if marker is not None:
        combined_details["matrix_marker"] = marker
    breadcrumbs = tuple(matrix.attrs.get("qa_debug_breadcrumbs", ()))
    if breadcrumbs:
        combined_details["breadcrumbs"] = breadcrumbs

    evidence_parts = tuple(violation.message for violation in violations)
    evidence = "; ".join(dict.fromkeys(evidence_parts)) if evidence_parts else ""
    law_ref_display = ", ".join(law_refs) if law_refs else "LAW-MENTOR-TYPE-01"
    breadcrumb_count = len(breadcrumbs)
    story_lines = (
        f"🔴 {QA_RULE_MENTOR_TYPE_01} / {law_ref_display}",
        f"چه شد: {evidence}",
        f"از کجا/مسیر: ماتریس منتورها (Inspactor → مدرسه)؛ {breadcrumb_count} گام در breadcrumbs.",
        "چرا: منتور باید فقط یکی از انواع عادی یا مدرسه‌ای باشد و alias با school_code هم‌راستا بماند.",
        "گام بعدی: سطرهای تخطی را در ماتریس اصلاح کنید و دوباره QA_RULE_MENTOR_TYPE_01 را اجرا کنید.",
    )

    return QADebugStory(
        rule_id=QA_RULE_MENTOR_TYPE_01,
        law_refs=law_refs,
        severity="error",
        evidence=evidence,
        context=MappingProxyType(combined_details),
        story=story_lines,
    )

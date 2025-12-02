from __future__ import annotations

import pandas as pd

from app.core.policy_loader import load_policy
from app.core.qa.invariants import QaReport, QaRuleResult, QaViolation, check_MENTOR_TYPE_01
from app.core.qa.rules import QA_RULE_MENTOR_TYPE_01, QA_RULE_STU_01
from app.infra.debug.qa_debug_engine import QADebugStory, explain_report, explain_rule


def test_only_mentor_rule_has_explainer() -> None:
    policy = load_policy()
    other_rule = QaRuleResult(
        rule_id=QA_RULE_STU_01,
        passed=False,
        violations=[
            QaViolation(
                rule_id=QA_RULE_STU_01,
                level="error",
                message="dummy",
                details=None,
            )
        ],
    )

    story = explain_rule(rule_result=other_rule, matrix=pd.DataFrame(), policy=policy)

    assert story is None


def test_mentor_rule_explainer_uses_runner_matrix() -> None:
    policy = load_policy()
    school_col = policy.columns.school_code
    matrix = pd.DataFrame(
        {
            "mentor_id": [1],
            "عادی مدرسه": ["عادی"],
            "جایگزین": [""],
            school_col: [101],
        }
    )
    matrix.attrs["qa_debug_marker"] = "runner-matrix"

    result = check_MENTOR_TYPE_01(matrix=matrix, policy=policy)
    story = explain_rule(rule_result=result, matrix=matrix, policy=policy)

    assert isinstance(story, QADebugStory)
    assert story.rule_id == QA_RULE_MENTOR_TYPE_01
    assert story.severity == "error"
    assert story.context["matrix_rows"] == len(matrix)
    assert story.context["matrix_marker"] == "runner-matrix"
    assert "alias" in story.evidence

    report_story = explain_report(QaReport(results=[result]), matrix=matrix, policy=policy)
    assert [item.rule_id for item in report_story] == [QA_RULE_MENTOR_TYPE_01]

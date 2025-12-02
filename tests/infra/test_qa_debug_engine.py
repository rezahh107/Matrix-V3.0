from __future__ import annotations

import pandas as pd
import pytest

import app.infra.debug.qa_debug_engine as qa_debug_engine
from app.core.policy_loader import load_policy
from app.core.qa.invariants import QaReport, QaRuleResult, QaViolation, check_MENTOR_TYPE_01
from app.core.qa.rules import QA_RULE_MENTOR_TYPE_01, QA_RULE_STU_01
from app.infra.debug.qa_debug_engine import (
    QADebugStory,
    build_debug_stories,
    explain_report,
    explain_rule,
)
from app.infra.debug.qa_debug_presenter import format_story_for_text


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
    matrix.attrs["qa_debug_breadcrumbs"] = [
        {
            "step_id": "BUILD_BASE",
            "label": "base rows",
            "row_count": 1,
            "key_stats": {"invalid_mentors": 0},
        },
        {
            "step_id": "EXPLODE_SCHOOLS",
            "label": "explode",
            "row_count": 1,
            "key_stats": {"normal_rows": 1, "school_rows": 0, "null_school_codes": 0},
        },
    ]

    result = check_MENTOR_TYPE_01(matrix=matrix, policy=policy)
    story = explain_rule(rule_result=result, matrix=matrix, policy=policy)

    assert isinstance(story, QADebugStory)
    assert story.rule_id == QA_RULE_MENTOR_TYPE_01
    assert story.severity == "error"
    assert story.context["matrix_rows"] == len(matrix)
    assert story.context["matrix_marker"] == "runner-matrix"
    assert "breadcrumbs" in story.context
    breadcrumbs = story.context["breadcrumbs"]
    assert isinstance(breadcrumbs, tuple)
    assert any(crumb["step_id"] == "QA_RULE_MENTOR_TYPE_01" for crumb in breadcrumbs)
    assert "alias" in story.evidence

    report_story = explain_report(QaReport(results=[result]), matrix=matrix, policy=policy)
    assert [item.rule_id for item in report_story] == [QA_RULE_MENTOR_TYPE_01]


def test_mentor_story_includes_path_and_next_steps() -> None:
    policy = load_policy()
    school_col = policy.columns.school_code
    matrix = pd.DataFrame(
        {
            "mentor_id": [1, 2],
            "عادی مدرسه": ["عادی", "مدرسه‌ای"],
            "جایگزین": ["", "1000"],
            school_col: [101, 0],
        }
    )
    matrix.attrs["qa_debug_breadcrumbs"] = [
        {
            "step_id": "BUILD_BASE",
            "label": "base rows",
            "row_count": 2,
            "key_stats": {"invalid_mentors": 0},
        },
        {
            "step_id": "EXPLODE_SCHOOLS",
            "label": "explode",
            "row_count": 2,
            "key_stats": {"normal_rows": 1, "school_rows": 1, "null_school_codes": 1},
        },
    ]

    result = check_MENTOR_TYPE_01(matrix=matrix, policy=policy)
    story = explain_rule(rule_result=result, matrix=matrix, policy=policy)

    assert story is not None
    assert len(story.story) >= 4
    assert any("چه شد" in line for line in story.story)
    assert any("مسیر" in line for line in story.story)
    assert any("گام بعدی" in line for line in story.story)
    breadcrumbs = story.context.get("breadcrumbs")
    assert breadcrumbs is not None
    assert len(breadcrumbs) >= 3


def test_build_debug_stories_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = load_policy()
    report = QaReport(results=[])
    captured: dict[str, object] = {}

    def _fake_explain_report(*, report: QaReport, matrix: object, policy: object) -> list[str]:
        captured["report"] = report
        captured["matrix"] = matrix
        captured["policy"] = policy
        return ["story"]

    monkeypatch.setattr(qa_debug_engine, "explain_report", _fake_explain_report)

    stories = build_debug_stories(report=report, matrix=None, policy=policy)

    assert stories == ["story"]
    assert captured["report"] is report
    assert captured["matrix"] is None
    assert captured["policy"] is policy


def test_format_story_for_text_includes_context() -> None:
    story = QADebugStory(
        rule_id=QA_RULE_MENTOR_TYPE_01,
        law_refs=("LAW-01",),
        severity="error",
        evidence="alias mismatch",
        context={"matrix_rows": 2, "breadcrumbs": ("A", "B")},
        story=(
            "🔴 QA_RULE_MENTOR_TYPE_01 / LAW-01",
            "چه شد: two rows invalid",
            "از کجا/مسیر: debug",
            "چرا: mismatch",
            "گام بعدی: fix",
        ),
    )

    rendered = format_story_for_text(story)

    assert "LAW-01" in rendered
    assert "matrix_rows" in rendered
    assert "گام بعدی" in rendered

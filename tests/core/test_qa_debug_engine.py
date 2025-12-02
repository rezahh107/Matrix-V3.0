import pandas as pd

from app.core.debug.models import QABreadcrumb
from app.core.policy_loader import load_policy
from app.core.qa.invariants import QaRuleResult, check_MENTOR_TYPE_01


def test_qabreadcrumb_payload_is_serializable() -> None:
    crumb = QABreadcrumb(
        step_id="STEP1",
        label="base",
        row_count=5,
        key_stats={"foo": 1, "bar": "x"},
    )

    payload = crumb.to_payload()

    assert payload["step_id"] == "STEP1"
    assert payload["label"] == "base"
    assert payload["row_count"] == 5
    assert payload["key_stats"] == {"foo": 1, "bar": "x"}


def test_matrix_attrs_receive_breadcrumbs_from_mentor_rule() -> None:
    policy = load_policy()
    school_col = policy.columns.school_code
    matrix = pd.DataFrame(
        {
            "mentor_id": [1],
            "عادی مدرسه": ["عادی"],
            "جایگزین": [""],
            school_col: [0],
        }
    )
    matrix.attrs["qa_debug_breadcrumbs"] = [
        QABreadcrumb(
            step_id="BUILD_BASE",
            label="base rows",
            row_count=1,
            key_stats={"invalid_mentors": 0},
        ).to_payload(),
        QABreadcrumb(
            step_id="EXPLODE_SCHOOLS",
            label="explode",
            row_count=1,
            key_stats={"normal_rows": 1, "school_rows": 0},
        ).to_payload(),
    ]

    result: QaRuleResult = check_MENTOR_TYPE_01(matrix=matrix, policy=policy)

    breadcrumbs = matrix.attrs.get("qa_debug_breadcrumbs")
    assert isinstance(breadcrumbs, list)
    assert any(crumb["step_id"] == "QA_RULE_MENTOR_TYPE_01" for crumb in breadcrumbs)
    qa_step = breadcrumbs[-1]
    assert qa_step["row_count"] == len(matrix)
    assert qa_step["key_stats"]["violation_count"] == len(result.violations)

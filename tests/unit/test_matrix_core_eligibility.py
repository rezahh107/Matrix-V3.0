from __future__ import annotations

from app.core.matrix.eligibility_rules import evaluate_eligibility
from app.core.matrix.matrix_schema import JOIN_KEY_COLUMNS


def test_happy_path_basic_match() -> None:
    mentor = {key: 1 for key in JOIN_KEY_COLUMNS}
    mentor["mentor_id"] = 101
    student = {key: 1 for key in JOIN_KEY_COLUMNS}
    student["student_id"] = 501

    outcome = evaluate_eligibility(mentor, student)

    assert outcome.eligible
    assert outcome.blocking_codes == ()
    assert outcome.trace[-1] == ("capacity_gate", "pending")


def test_gender_mismatch_blocking() -> None:
    mentor = {
        "group_code": 11,
        "gender_code": 1,
        "grad_status_code": 1,
        "center_code": 2,
        "finance_code": 3,
        "school_code": 4,
    }
    student = {
        "group_code": 11,
        "gender_code": 2,
        "grad_status_code": 1,
        "center_code": 2,
        "finance_code": 3,
        "school_code": 4,
    }

    outcome = evaluate_eligibility(mentor, student)

    assert not outcome.eligible
    assert "gender_code_mismatch" in outcome.blocking_codes
    assert outcome.trace[-1] == ("gender", "blocked")


def test_center_wildcard_allows_match() -> None:
    mentor = {
        "group_code": 1,
        "gender_code": 1,
        "grad_status_code": 1,
        "center_code": 0,
        "finance_code": 1,
        "school_code": 0,
    }
    student = {
        "group_code": 1,
        "gender_code": 1,
        "grad_status_code": 1,
        "center_code": 22,
        "finance_code": 1,
        "school_code": 33,
    }

    outcome = evaluate_eligibility(mentor, student)

    assert outcome.eligible
    assert outcome.trace[-2] == ("school", "ok")

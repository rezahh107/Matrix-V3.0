from dataclasses import replace

import pandas as pd

from app.core.allocation.engine import annotate_students_with_channel
from app.core.policy_loader import PolicyConfig, load_policy


def _policy_with_school_codes() -> PolicyConfig:
    policy = load_policy()
    return replace(
        policy, allocation_channels=replace(policy.allocation_channels, school_codes=(101, 202))
    )


def test_school_channel_requires_student_status() -> None:
    policy = _policy_with_school_codes()
    status_col = policy.stage_column("graduation_status")
    school_col = policy.columns.school_code
    students = pd.DataFrame(
        [
            {"student_id": 1, school_col: 101, status_col: 1},
            {"student_id": 2, school_col: 101, status_col: 0},
        ]
    )

    result = annotate_students_with_channel(students, policy)

    assert result.loc[result["student_id"].eq(1), "allocation_channel"].iat[0] == "SCHOOL"
    assert result.loc[result["student_id"].eq(2), "allocation_channel"].iat[0] == "GENERIC"


def test_school_channel_respects_school_code_membership() -> None:
    policy = _policy_with_school_codes()
    status_col = policy.stage_column("graduation_status")
    school_col = policy.columns.school_code
    students = pd.DataFrame(
        [
            {"student_id": 3, school_col: 999, status_col: 1},
            {"student_id": 4, school_col: 0, status_col: 1},
        ]
    )

    result = annotate_students_with_channel(students, policy)

    assert (result.loc[result["student_id"].eq(3), "allocation_channel"] == "GENERIC").all()
    assert (result.loc[result["student_id"].eq(4), "allocation_channel"] == "GENERIC").all()


def test_school_channel_defaults_to_student_when_status_missing() -> None:
    policy = _policy_with_school_codes()
    school_col = policy.columns.school_code
    students = pd.DataFrame(
        [
            {"student_id": 5, school_col: 101},
            {"student_id": 6, school_col: 202},
        ]
    )

    result = annotate_students_with_channel(students, policy)

    assert (result.loc[result["student_id"].eq(5), "allocation_channel"] == "SCHOOL").all()
    assert (result.loc[result["student_id"].eq(6), "allocation_channel"] == "SCHOOL").all()

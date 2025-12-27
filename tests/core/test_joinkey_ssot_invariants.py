from __future__ import annotations

import pandas as pd

from app.core.common.filters import filter_by_center
from app.core.policy_loader import load_policy


def _expected_center_matches(
    mentor_centers: list[int],
    student_center: int,
) -> list[int]:
    return [
        center
        for center in mentor_centers
        if center == 0 or center == student_center
    ]


def test_joinkey_ssot_center_semantics_parity_default_policy() -> None:
    """JOINKEY-SSOT-02: student center must not disable filtering; mentor wildcard only."""

    policy = load_policy()
    center_column = policy.stage_column("center")
    mentor_centers = [0, 1, 2]
    pool = pd.DataFrame(
        {
            "mentor_id": [f"m{center}" for center in mentor_centers],
            center_column: mentor_centers,
        }
    )
    for student_center in mentor_centers:
        student = {center_column: student_center}
        filtered = filter_by_center(pool, student, policy=policy)
        expected_centers = _expected_center_matches(mentor_centers, student_center)
        assert filtered[center_column].tolist() == expected_centers


def test_joinkey_ssot_center_semantics_parity_with_policy_wildcard() -> None:
    """JOINKEY-SSOT-04: parity guard between filter and wildcard match semantics."""

    policy = load_policy()
    policy.center_map["*"] = 42
    center_column = policy.stage_column("center")
    mentor_centers = [0, 1, 2, 42]
    pool = pd.DataFrame(
        {
            "mentor_id": [f"m{center}" for center in mentor_centers],
            center_column: mentor_centers,
        }
    )
    for student_center in [0, 1, 2, 42]:
        student = {center_column: student_center}
        filtered = filter_by_center(pool, student, policy=policy)
        expected_centers = _expected_center_matches(mentor_centers, student_center)
        assert filtered[center_column].tolist() == expected_centers


def test_filter_by_center_student_zero_does_not_match_nonzero() -> None:
    policy = load_policy()
    center_column = policy.stage_column("center")
    pool = pd.DataFrame(
        {
            "mentor_id": ["m0", "m1", "m2"],
            center_column: [0, 1, 2],
        }
    )
    student = {center_column: 0}

    filtered = filter_by_center(pool, student, policy=policy)

    assert filtered[center_column].tolist() == [0]

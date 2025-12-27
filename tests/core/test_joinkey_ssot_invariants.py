from __future__ import annotations

import pandas as pd

from app.core.common.filters import filter_by_center
from app.core.common.join_keys import center_wildcard_value, matches_center_with_wildcard
from app.core.policy_loader import load_policy


def _expected_center_matches(
    mentor_centers: list[int],
    student_center: int,
    wildcard_center: int | None,
) -> list[int]:
    return [
        center
        for center in mentor_centers
        if matches_center_with_wildcard(student_center, center, wildcard_center)
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
    wildcard_center = center_wildcard_value(policy)

    for student_center in mentor_centers:
        student = {center_column: student_center}
        filtered = filter_by_center(pool, student, policy=policy)
        expected_centers = _expected_center_matches(
            mentor_centers, student_center, wildcard_center
        )
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
    wildcard_center = center_wildcard_value(policy)

    for student_center in [0, 1, 2, 42]:
        student = {center_column: student_center}
        filtered = filter_by_center(pool, student, policy=policy)
        expected_centers = _expected_center_matches(
            mentor_centers, student_center, wildcard_center
        )
        assert filtered[center_column].tolist() == expected_centers

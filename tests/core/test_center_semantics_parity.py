from __future__ import annotations

import pandas as pd

from app.core.common.filters import filter_by_center
from app.core.common.join_keys import matches_center_with_wildcard
from app.core.policy_loader import load_policy


def _expected_center_match(student_center: int, mentor_center: int) -> bool:
    if student_center == 0:
        return mentor_center == 0
    return mentor_center == 0 or mentor_center == student_center


def test_center_semantics_parity_filter_and_matcher() -> None:
    policy = load_policy()
    center_column = policy.stage_column("center")
    pool = pd.DataFrame({center_column: [0, 1, 2]})

    for student_center in (0, 1, 2):
        student = {center_column: student_center}
        filtered = filter_by_center(pool, student, policy)
        expected_centers = [
            value
            for value in pool[center_column].tolist()
            if _expected_center_match(student_center, int(value))
        ]
        assert filtered[center_column].tolist() == expected_centers

        for mentor_center in (0, 1, 2):
            assert (
                matches_center_with_wildcard(student_center, mentor_center, None)
                == _expected_center_match(student_center, mentor_center)
            )

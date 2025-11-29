from __future__ import annotations

import pandas as pd

from app.core.allocate_students import _center_mask_series


def test_center_mask_treats_missing_as_global_wildcard() -> None:
    mentor_centers = pd.Series([pd.NA, 0, 2, 3], dtype="Int64")

    mask = _center_mask_series(mentor_centers, student_center=3, wildcard_center=None)

    assert mask.tolist() == [True, True, False, True]


def test_center_mask_respects_policy_wildcard_passthrough() -> None:
    mentor_centers = pd.Series([pd.NA, 7, 12], dtype="Int64")

    mask = _center_mask_series(mentor_centers, student_center=99, wildcard_center=99)

    assert mask.tolist() == [True, True, True]

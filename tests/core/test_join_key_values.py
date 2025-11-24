import pandas as pd

from app.core.allocate_students import (
    _center_mask_series,
    _derive_error_type_from_stage_counts,
    _matches_center_with_wildcard,
    _matches_school_with_wildcard,
    _school_mask_series,
)
from app.core.common.types import CANONICAL_TRACE_ORDER


def test_center_and_school_wildcards_behave_consistently() -> None:
    assert _matches_center_with_wildcard(0, 2, 0) is True
    assert _matches_center_with_wildcard(1, 2, 0) is False

    assert _matches_school_with_wildcard(0, 303, True) is True
    assert _matches_school_with_wildcard(501, 0, True) is True
    assert _matches_school_with_wildcard(501, 501, True) is True
    assert _matches_school_with_wildcard(501, 999, True) is False


def test_mask_helpers_cover_wildcards_vectorized() -> None:
    mentor_centers = pd.Series([1, 2, 3])
    mentor_schools = pd.Series([0, 501, 502])

    center_mask = _center_mask_series(mentor_centers, 0, 0)
    school_mask = _school_mask_series(mentor_schools, 0, True)

    assert center_mask.tolist() == [True, True, True]
    assert school_mask.tolist() == [True, True, True]


def test_error_type_derivation_respects_canonical_stages() -> None:
    eligibility_counts = {stage: 1 for stage in CANONICAL_TRACE_ORDER}
    eligibility_counts["center"] = 0
    capacity_counts = {stage: 1 for stage in CANONICAL_TRACE_ORDER}
    capacity_counts["capacity_gate"] = 0

    assert _derive_error_type_from_stage_counts(eligibility_counts) == "ELIGIBILITY_NO_MATCH"
    assert _derive_error_type_from_stage_counts(capacity_counts) == "CAPACITY_FULL"

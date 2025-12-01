from __future__ import annotations

import pandas as pd
import pytest

from app.core.policy_loader import load_policy
from app.infra.cli import (
    AllocationConsistencyError,
    _sync_counter_summary_with_allocations,
    _validate_allocation_consistency,
)


def test_validate_allocation_consistency_raises_on_empty_allocations() -> None:
    counter_summary = {"new_male_count": 1, "new_female_count": 0}
    updated_pool = pd.DataFrame({"mentor_id": ["m1"]})
    selection_reasons = pd.DataFrame({"student_id": ["1"]})

    with pytest.raises(AllocationConsistencyError):
        _validate_allocation_consistency(
            counter_summary=counter_summary,
            allocations_df=pd.DataFrame(),
            updated_pool_df=updated_pool,
            selection_reasons_df=selection_reasons,
            sabt_allocations_df=None,
        )


def test_validate_allocation_consistency_passes_when_aligned() -> None:
    counter_summary = {"new_male_count": 1, "new_female_count": 0}
    allocations = pd.DataFrame({"student_id": ["1"], "mentor_id": ["m1"]})
    updated_pool = pd.DataFrame({"mentor_id": ["m1"], "remaining_capacity": [0]})
    selection_reasons = pd.DataFrame({"student_id": ["1"], "reason": ["matched"]})

    _validate_allocation_consistency(
        counter_summary=counter_summary,
        allocations_df=allocations,
        updated_pool_df=updated_pool,
        selection_reasons_df=selection_reasons,
        sabt_allocations_df=None,
    )


def test_sync_counter_summary_with_allocations_updates_gender_counts() -> None:
    policy = load_policy()
    students = pd.DataFrame(
        {
            "student_id": ["1", "2"],
            "gender": [int(policy.gender_codes.male.value), int(policy.gender_codes.female.value)],
        }
    )
    allocations = pd.DataFrame({"student_id": ["1", "2"], "mentor_id": ["m1", "m2"]})
    summary = _sync_counter_summary_with_allocations(
        counter_summary={"new_male_count": 0, "new_female_count": 0},
        allocations_df=allocations,
        students_df=students,
        policy=policy,
    )

    assert summary["new_male_count"] == 1
    assert summary["new_female_count"] == 1
    assert summary["next_male_start"] >= 2
    assert summary["next_female_start"] >= 2


def test_sync_counter_summary_with_allocations_resets_when_empty() -> None:
    policy = load_policy()
    summary = _sync_counter_summary_with_allocations(
        counter_summary={"new_male_count": 5, "new_female_count": 3},
        allocations_df=pd.DataFrame(),
        students_df=pd.DataFrame(),
        policy=policy,
    )

    assert summary["new_male_count"] == 0
    assert summary["new_female_count"] == 0

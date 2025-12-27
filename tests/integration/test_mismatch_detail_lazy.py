from __future__ import annotations

import pandas as pd
from pytest import MonkeyPatch

from app.core import allocate_students as alloc_mod
from app.core.allocate_students import JoinMismatch, allocate_student
from app.core.policy_loader import load_policy


def _student_row(policy) -> dict[str, int | str]:
    return {
        "student_id": "S-LAZY",
        policy.stage_column("group"): 1,
        policy.stage_column("gender"): 1,
        policy.stage_column("graduation_status"): 0,
        policy.stage_column("center"): 1,
        policy.stage_column("finance"): 0,
        policy.columns.school_code: 0,
    }


def _pool_row(policy, *, mentor_id: str, center: int, capacity: int = 1) -> dict[str, int | str]:
    return {
        "mentor_id": mentor_id,
        policy.stage_column("group"): 1,
        policy.stage_column("gender"): 1,
        policy.stage_column("graduation_status"): 0,
        policy.stage_column("center"): center,
        policy.stage_column("finance"): 0,
        policy.columns.school_code: 0,
        "remaining_capacity": capacity,
        "allocations_new": 0,
        "occupancy_ratio": 0.0,
    }


def test_success_path_skips_mismatch_detail_when_not_debug(
    monkeypatch: MonkeyPatch,
) -> None:
    policy = load_policy()
    student = _student_row(policy)
    pool = pd.DataFrame([_pool_row(policy, mentor_id="m-match", center=1)])

    def _raise_on_mismatch(*_args, **_kwargs):
        raise AssertionError("mismatch detail should be lazy on success")

    monkeypatch.setattr(alloc_mod, "_filter_candidates_by_join_map", _raise_on_mismatch)

    result = allocate_student(student, pool, policy=policy, debug_trace=False)

    assert result.log.get("allocation_status") == "success"
    assert "join_key_mismatches" not in result.log


def test_debug_trace_computes_mismatch_detail_on_success(
    monkeypatch: MonkeyPatch,
) -> None:
    policy = load_policy()
    student = _student_row(policy)
    pool = pd.DataFrame(
        [
            _pool_row(policy, mentor_id="m-match", center=1),
            _pool_row(policy, mentor_id="m-miss", center=2),
        ]
    )
    calls: list[str] = []
    original = alloc_mod._filter_candidates_by_join_map

    def _tracked_filter(*args, **kwargs) -> tuple[pd.DataFrame, list[JoinMismatch]]:
        calls.append("called")
        return original(*args, **kwargs)

    monkeypatch.setattr(alloc_mod, "_filter_candidates_by_join_map", _tracked_filter)

    result = allocate_student(student, pool, policy=policy, debug_trace=True)

    assert result.log.get("allocation_status") == "success"
    assert calls
    mismatches = result.log.get("join_key_mismatches")
    assert isinstance(mismatches, list) and mismatches


def test_failure_path_computes_mismatch_detail(
    monkeypatch: MonkeyPatch,
) -> None:
    policy = load_policy()
    student = _student_row(policy)
    pool = pd.DataFrame([_pool_row(policy, mentor_id="m-miss", center=2)])
    calls: list[str] = []
    original = alloc_mod._filter_candidates_by_join_map

    def _tracked_filter(*args, **kwargs) -> tuple[pd.DataFrame, list[JoinMismatch]]:
        calls.append("called")
        return original(*args, **kwargs)

    monkeypatch.setattr(alloc_mod, "_filter_candidates_by_join_map", _tracked_filter)

    result = allocate_student(student, pool, policy=policy, debug_trace=False)

    assert result.log.get("allocation_status") == "failed"
    assert result.log.get("error_type") == "ELIGIBILITY_NO_MATCH"
    assert calls
    mismatches = result.log.get("join_key_mismatches")
    assert isinstance(mismatches, list) and mismatches

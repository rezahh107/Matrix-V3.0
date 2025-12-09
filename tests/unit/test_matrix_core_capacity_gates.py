from __future__ import annotations

from app.core.matrix.capacity_gates import evaluate_capacity


def test_capacity_positive_passes() -> None:
    mentor = {"capacity_limit": 5, "assigned_baseline": 1, "allocations_new": 1}
    outcome = evaluate_capacity(mentor)

    assert outcome.capacity_ok
    assert outcome.remaining_capacity == 3


def test_capacity_zero_blocks() -> None:
    mentor = {"capacity_limit": 2, "assigned_baseline": 1, "allocations_new": 1}
    outcome = evaluate_capacity(mentor)

    assert not outcome.capacity_ok
    assert "capacity_exhausted" in outcome.blocking_codes


def test_capacity_frozen_blocks_even_with_space() -> None:
    mentor = {
        "capacity_limit": 10,
        "assigned_baseline": 1,
        "allocations_new": 1,
        "capacity_frozen": True,
    }
    outcome = evaluate_capacity(mentor)

    assert not outcome.capacity_ok
    assert "capacity_frozen" in outcome.blocking_codes


def test_capacity_special_extends_limit() -> None:
    mentor = {
        "capacity_limit": 3,
        "assigned_baseline": 1,
        "allocations_new": 1,
        "capacity_special": 2,
    }
    outcome = evaluate_capacity(mentor)

    assert outcome.capacity_ok
    assert outcome.remaining_capacity == 3

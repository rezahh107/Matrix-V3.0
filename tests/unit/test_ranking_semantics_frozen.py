from dataclasses import replace

import pandas as pd

from app.core.common.ranking import HeapRankingManager, apply_ranking_policy
from app.core.policy_loader import load_policy


def _candidate_pool() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "mentor_id": ["MENTOR-2", "MENTOR-10", "MENTOR-1"],
            "remaining_capacity": [2, 2, 2],
            "allocations_new": [0, 1, 0],
        }
    )


def test_heap_queue_matches_legacy_ordering() -> None:
    pool = _candidate_pool()
    state = {
        "MENTOR-1": {"remaining": 2, "alloc_new": 0},
        "MENTOR-2": {"remaining": 2, "alloc_new": 0},
        "MENTOR-10": {"remaining": 2, "alloc_new": 1},
    }

    legacy_policy = load_policy()
    legacy_ranked = apply_ranking_policy(pool, state=state, policy=legacy_policy)

    heap_policy = replace(legacy_policy, ranking_mode="heap_queue")
    heap_manager = HeapRankingManager(index=pool.index)
    heap_ranked = apply_ranking_policy(
        pool, state=state, policy=heap_policy, heap_manager=heap_manager
    )

    pd.testing.assert_frame_equal(
        legacy_ranked.reset_index(drop=True),
        heap_ranked.reset_index(drop=True),
        check_dtype=False,
    )


def test_heap_queue_updates_after_state_changes() -> None:
    pool = _candidate_pool()
    policy = replace(load_policy(), ranking_mode="heap_queue")
    state = {
        "MENTOR-1": {"remaining": 1, "alloc_new": 0},
        "MENTOR-2": {"remaining": 1, "alloc_new": 0},
        "MENTOR-10": {"remaining": 1, "alloc_new": 0},
    }

    heap_manager = HeapRankingManager(index=pool.index)
    first = apply_ranking_policy(pool, state=state, policy=policy, heap_manager=heap_manager)

    state["MENTOR-1"]["alloc_new"] = 2
    state["MENTOR-1"]["remaining"] = 0

    second = apply_ranking_policy(
        pool, state=state, policy=policy, heap_manager=heap_manager
    )
    legacy_after = apply_ranking_policy(pool, state=state, policy=load_policy())

    assert list(first["mentor_id"])[:2] == ["MENTOR-1", "MENTOR-2"]
    pd.testing.assert_frame_equal(
        second.reset_index(drop=True),
        legacy_after.reset_index(drop=True),
        check_dtype=False,
    )

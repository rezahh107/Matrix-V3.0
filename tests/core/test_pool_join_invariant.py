from __future__ import annotations

import pandas as pd

from app.core.policy_loader import load_policy
from app.core.qa.invariants import check_POOL_JOIN_01


def _base_row(mentor: str, policy_join_keys: list[str], seed: int = 1) -> dict[str, int | str]:
    base: dict[str, int | str] = {"mentor_id": mentor}
    for index, column in enumerate(policy_join_keys):
        base[column] = seed + index
    return base


def test_pool_join_invariant_allows_multi_profile_mentor() -> None:
    policy = load_policy()
    join_keys = policy.join_keys
    pool = pd.DataFrame(
        [
            _base_row("m1", join_keys, seed=10),
            _base_row("m1", join_keys, seed=20),
        ]
    )

    result, conflicts = check_POOL_JOIN_01(pool=pool, policy=policy)

    assert result.passed
    assert conflicts.empty


def test_pool_join_invariant_rejects_exact_duplicate_rows() -> None:
    policy = load_policy()
    join_keys = policy.join_keys
    duplicate_row = _base_row("m2", join_keys, seed=30)
    pool = pd.DataFrame([duplicate_row, duplicate_row])

    result, conflicts = check_POOL_JOIN_01(pool=pool, policy=policy)

    assert not result.passed
    assert not conflicts.empty
    assert conflicts[["mentor_id", *join_keys]].drop_duplicates().shape[0] == 1
    assert int(conflicts["duplicate_group_size"].iloc[0]) == 2
    assert conflicts["duplicate_group_size"].dtype == pd.Int64Dtype()

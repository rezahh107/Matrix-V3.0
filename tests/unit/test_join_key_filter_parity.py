from __future__ import annotations

from dataclasses import replace

import pandas as pd

from app.core.allocate_students import _filter_candidates_by_join_map
from app.core.common.filters import filter_by_finance, filter_by_school
from app.core.common.join_keys import normalize_join_key_name
from app.core.policy_loader import PolicyConfig, load_policy


def _build_join_map(policy: PolicyConfig, values: dict[str, int]) -> dict[str, int]:
    join_map: dict[str, int] = {}
    join_keys = getattr(policy, "join_keys")
    for column in join_keys:
        normalized = normalize_join_key_name(column)
        join_map[normalized] = int(values.get(column, 1))
    return join_map


def test_finance_filter_matches_join_map_matcher() -> None:
    policy = replace(load_policy(), finance_variants=(1, 2))
    finance_column = policy.stage_column("finance")
    school_column = policy.stage_column("school")

    data: dict[str, list[int]] = {}
    for column in policy.join_keys:
        if column == finance_column:
            data[column] = [1, 2, 3]
        elif column == school_column:
            data[column] = [5001, 5001, 5001]
        else:
            data[column] = [1, 1, 1]
    pool = pd.DataFrame(data)

    join_map = _build_join_map(
        policy,
        {
            finance_column: 1,
            school_column: 5001,
        },
    )

    filtered = filter_by_finance(pool, {}, policy, student_join_map=join_map)
    matched, _ = _filter_candidates_by_join_map(pool, join_map=join_map, policy=policy)

    assert filtered.index.tolist() == matched.index.tolist()


def test_school_filter_matches_join_map_matcher_with_constraints() -> None:
    policy = replace(load_policy(), school_code_empty_as_zero=True)
    school_column = policy.stage_column("school")
    finance_column = policy.stage_column("finance")

    data: dict[str, list[int]] = {}
    for column in policy.join_keys:
        if column == school_column:
            data[column] = [0, 5001, 7000]
        elif column == finance_column:
            data[column] = [1, 1, 1]
        else:
            data[column] = [1, 1, 1]
    pool = pd.DataFrame(data)
    pool["has_school_constraint"] = [False, True, True]

    join_map = _build_join_map(policy, {school_column: 0})

    filtered = filter_by_school(pool, {}, policy, student_join_map=join_map)
    matched, _ = _filter_candidates_by_join_map(pool, join_map=join_map, policy=policy)

    assert filtered.index.tolist() == matched.index.tolist()

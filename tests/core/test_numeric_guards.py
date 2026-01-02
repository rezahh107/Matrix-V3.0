from __future__ import annotations

import pandas as pd

from app.core.allocation.mentor_pool import _distribution_counts, _unique_mentor_ids
from app.core.build_matrix import _count_null_school_codes
from app.core.common.contracts import _validate_capacity_contract
from app.core.common.errors import ContractIssue


def test_count_null_school_codes_uses_first_duplicate_column() -> None:
    matrix = pd.DataFrame({"کد مدرسه": [0, 0, 1]})
    matrix.insert(1, "کد مدرسه", [1, 1, 1], allow_duplicates=True)

    nulls = _count_null_school_codes(matrix, "کد مدرسه")

    assert nulls == 2


def test_capacity_contract_ignores_duplicate_numeric_columns() -> None:
    pool = pd.DataFrame(
        {
            "allocations_new": [1, 2],
            "remaining_capacity": [3, 4],
            "assigned_baseline": [0, 0],
            "capacity_limit": [4, 6],
        }
    )
    pool.insert(1, "allocations_new", ["bad", "bad"], allow_duplicates=True)
    pool.insert(3, "remaining_capacity", ["bad", "bad"], allow_duplicates=True)
    pool.insert(5, "assigned_baseline", ["bad", "bad"], allow_duplicates=True)
    pool.insert(7, "capacity_limit", ["bad", "bad"], allow_duplicates=True)

    issues: list[ContractIssue] = []
    _validate_capacity_contract(pool, context="pool", issues=issues)

    assert issues == []


def test_mentor_pool_distribution_and_unique_ids_use_first_duplicate_column() -> None:
    frame = pd.DataFrame(
        {
            "group_code": [1, 1, 2],
            "gender": [1, 1, 1],
            "graduation_status": [1, 1, 1],
            "mentor_id": [10, 20, 30],
        }
    )
    frame.insert(1, "group_code", [9, 9, 9], allow_duplicates=True)
    frame.insert(len(frame.columns), "mentor_id", [999, 999, 999], allow_duplicates=True)

    distributions = _distribution_counts(frame)
    unique_ids = _unique_mentor_ids(frame)

    assert distributions["group_code"] == {1: 2, 2: 1}
    assert unique_ids == 3

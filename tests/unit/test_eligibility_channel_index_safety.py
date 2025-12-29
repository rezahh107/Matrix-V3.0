from __future__ import annotations

import pandas as pd

from app.core.common.eligibility_channel import apply_eligibility
from app.core.common.join_resolver import JoinKeyResolver
from app.core.policy_loader import load_policy


def test_eligibility_priority_alignment_with_shuffled_index() -> None:
    policy = load_policy()
    pool = pd.DataFrame(
        {
            "کدرشته": [1, 1, 1],
            "گروه آزمایشی": ["تجربی", "تجربی", "تجربی"],
            "جنسیت": [1, 1, 1],
            "دانش آموز فارغ": [0, 0, 0],
            "مرکز گلستان صدرا": [1, 1, 1],
            "مالی حکمت بنیاد": [0, 0, 0],
            "کد مدرسه": [1010, 1010, 1010],
            "mentor_id": [101, 102, 103],
        },
        index=pd.Index([30, 10, 20]),
    )
    student = {
        "student_id": "S-1",
        "کدرشته": 1,
        "گروه آزمایشی": "تجربی",
        "جنسیت": 1,
        "دانش آموز فارغ": 0,
        "مرکز گلستان صدرا": 1,
        "مالی حکمت بنیاد": 0,
        "کد مدرسه": 1010,
    }

    resolver = JoinKeyResolver(policy)
    spec = resolver.resolve_candidate_scope(
        student,
        manager_preference_index=pd.Index([20, 30]),
        manager_priority_enabled=True,
    )

    eligible, priority, _ = apply_eligibility(pool, spec)

    assert eligible.index.equals(priority.index)
    assert int(priority.loc[30]) == 1
    assert int(priority.loc[20]) == 1
    assert int(priority.loc[10]) == 0

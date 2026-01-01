from __future__ import annotations

import pandas as pd

from app.core.common.trace import build_allocation_trace
from app.core.policy_loader import load_policy


def test_trace_stage_aliasing_marks_type_group_overlap() -> None:
    policy = load_policy()
    pool = pd.DataFrame(
        {
            "کدرشته": [1],
            "جنسیت": [1],
            "دانش آموز فارغ": [1],
            "مرکز گلستان صدرا": [0],
            "مالی حکمت بنیاد": [0],
            "کد مدرسه": [0],
            "remaining_capacity": [1],
        }
    )
    student = {
        "کدرشته": 1,
        "جنسیت": 1,
        "دانش آموز فارغ": 1,
        "مرکز گلستان صدرا": 0,
        "مالی حکمت بنیاد": 0,
        "کد مدرسه": 0,
    }

    trace = build_allocation_trace(student, pool, policy=policy)
    type_stage = next(record for record in trace if record["stage"] == "type")
    extras = type_stage.get("extras") or {}

    assert "stage_type_alias_of" not in extras
    assert "stage_type_source_col" not in extras
    assert "stage_group_source_col" not in extras

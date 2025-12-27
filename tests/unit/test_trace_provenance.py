from __future__ import annotations

from dataclasses import replace

import pandas as pd

from app.core.allocate_students import _build_log_from_join_map, allocate_student
from app.core.common.trace import (
    JOIN_STAGE_SOURCE_KEYS,
    attach_join_source_extras,
    summarize_trace_outcome,
)
from app.core.policy_loader import load_policy


def test_trace_provenance_included_in_summary_and_trace() -> None:
    policy = replace(load_policy(), center_map={"مدیر الف": 1, "*": 0})
    pool = pd.DataFrame(
        {
            "پشتیبان": ["مینا"],
            "کد کارمندی پشتیبان": ["EMP-01"],
            "کدرشته": [27],
            "گروه آزمایشی": [27],
            "جنسیت": [1],
            "دانش آموز فارغ": [0],
            "مرکز گلستان صدرا": [1],
            "مالی حکمت بنیاد": [0],
            "کد مدرسه": [3581],
            "remaining_capacity": [1],
            "occupancy_ratio": [0.0],
            "allocations_new": [0],
        }
    )
    students = pd.DataFrame(
        {
            "student_id": ["STD-001"],
            "کدرشته": [27],
            "گروه آزمایشی": [27],
            "جنسیت": [1],
            "دانش آموز فارغ": [0],
            "مرکز گلستان صدرا": [0],
            "مالی حکمت بنیاد": [0],
            "کد مدرسه": [3581],
            "مدیر": ["مدیر الف"],
        }
    )

    student = students.iloc[0].to_dict()
    result = allocate_student(student, pool, policy=policy, debug_trace=True)
    outcome = summarize_trace_outcome(student, result.trace, result.log, policy=policy)
    assert outcome.metadata["center_source"] == "manager_exact"

    center_stage = next(stage for stage in result.trace if stage["stage"] == "center")
    extras = center_stage["extras"]
    assert isinstance(extras, dict)
    assert extras["center_source"] == "manager_exact"


def test_build_log_from_join_map_resolves_sources_when_missing() -> None:
    policy = load_policy()
    student = {
        "student_id": "STD-LOG",
        "کدرشته": 27,
        "گروه آزمایشی": 27,
        "جنسیت": 1,
        "دانش آموز فارغ": 0,
        "مرکز گلستان صدرا": 1,
        "مالی حکمت بنیاد": 0,
        "کد مدرسه": 3581,
    }
    join_map = {
        "کدرشته": 27,
        "جنسیت": 1,
        "دانش آموز فارغ": 0,
        "مرکز گلستان صدرا": 1,
        "مالی حکمت بنیاد": 0,
        "کد مدرسه": 3581,
    }

    log = _build_log_from_join_map(student, join_map, policy)

    join_sources = log.get("join_key_sources")
    assert isinstance(join_sources, dict)
    assert join_sources["gender_source"] == "raw"


def test_join_source_helpers_match_export_columns() -> None:
    extras: dict[str, object] = {}
    join_key_sources = {"center_source": "manager_exact"}

    attach_join_source_extras(
        extras,
        stage="center",
        join_key_sources=join_key_sources,
    )

    expected_columns = {
        "group": "group_source",
        "gender": "gender_source",
        "graduation_status": "graduation_status_source",
        "center": "center_source",
        "finance": "finance_source",
        "school": "school_source",
    }
    assert dict(JOIN_STAGE_SOURCE_KEYS) == expected_columns
    assert extras["center_source"] == "manager_exact"

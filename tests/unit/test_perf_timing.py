from __future__ import annotations

import pandas as pd

from app.core import allocate_students as allocator
from app.core.perf import measure_time
from app.core.policy_loader import load_policy


def _sample_students() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "student_id": "STD-1",
                "کدرشته": 1,
                "گروه آزمایشی": "تجربی",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 0,
                "مالی حکمت بنیاد": 0,
                "کد مدرسه": 1010,
            }
        ]
    )


def _sample_pool() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "پشتیبان": "منتور الف",
                "mentor_name": "منتور الف",
                "alias": 101,
                "remaining_capacity": 2,
                "allocations_new": 0,
                "کدرشته": 1,
                "گروه آزمایشی": "تجربی",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 0,
                "مالی حکمت بنیاد": 0,
                "کد مدرسه": 1010,
                "کد کارمندی پشتیبان": "EMP-101",
            }
        ]
    )


def test_measure_time_no_tracker_is_noop() -> None:
    calls: list[str] = []

    with measure_time("noop", None):
        calls.append("executed")

    assert calls == ["executed"]


def test_measure_time_records_elapsed() -> None:
    events: list[tuple[str, float]] = []

    times = iter([0.0, 0.25])

    def _clock() -> float:
        return next(times)

    def _tracker(stage: str, duration: float) -> None:
        events.append((stage, duration))

    with measure_time("sample", _tracker, clock=_clock):
        pass

    assert events == [("sample", 0.25)]


def test_allocate_batch_records_perf_stages() -> None:
    policy = load_policy()
    tracker_stages: list[str] = []

    def _tracker(stage: str, duration: float) -> None:
        tracker_stages.append(stage)
        assert duration >= 0

    students = _sample_students()
    pool = _sample_pool()

    result = allocator.allocate_batch(students, pool, policy=policy, perf_tracker=_tracker)

    assert result.allocations_df.shape[0] == 1
    for expected_stage in (
        "join_filters",
        "mismatch_detail",
        "capacity_gate",
        "ranking",
        "trace_detail",
        "trace_summary",
    ):
        assert expected_stage in tracker_stages

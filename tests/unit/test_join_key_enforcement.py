import pandas as pd

from app.core.allocate_students import allocate_batch
from app.core.policy_loader import load_policy


def _student_row(student_id: str, *, group_code: int, gender: int) -> dict[str, object]:
    return {
        "student_id": student_id,
        "کدرشته": group_code,
        "گروه آزمایشی": group_code,
        "جنسیت": gender,
        "دانش آموز فارغ": 0,
        "مرکز گلستان صدرا": 1,
        "مالی حکمت بنیاد": 0,
        "کد مدرسه": 111,
    }


def _pool_row(alias: int, *, group_code: int, gender: int, capacity: int = 1) -> dict[str, object]:
    return {
        "پشتیبان": f"M-{alias}",
        "کد کارمندی پشتیبان": alias,
        "جایگزین | alias": alias,
        "کدرشته": group_code,
        "کدرشته | group_code": group_code,
        "گروه آزمایشی": group_code,
        "جنسیت": gender,
        "جنسیت | gender": gender,
        "دانش آموز فارغ": 0,
        "دانش آموز فارغ | graduation_status": 0,
        "مرکز گلستان صدرا": 1,
        "مرکز گلستان صدرا | center": 1,
        "مالی حکمت بنیاد": 0,
        "مالی حکمت بنیاد | finance": 0,
        "کد مدرسه": 111,
        "کد مدرسه | school_code": 111,
        "remaining_capacity": capacity,
        "allocations_new": 0,
        "occupancy_ratio": 0.0,
    }


def test_join_key_mismatch_rejected_and_logged() -> None:
    policy = load_policy()
    students = pd.DataFrame([_student_row("STD-BOY", group_code=3, gender=1)])
    pool = pd.DataFrame([_pool_row(2504, group_code=21, gender=0)])

    allocations, _, logs, trace = allocate_batch(students, pool, policy=policy)

    assert allocations.empty
    assert logs.loc[0, "error_type"] == "ELIGIBILITY_NO_MATCH"
    assert logs.loc[0, "student_id"] == "STD-BOY"
    assert logs.loc[0, "candidate_count"] == 0
    mismatches = logs.loc[0, "join_key_mismatches"]
    assert isinstance(mismatches, list) and mismatches
    assert trace["student_id"].astype(str).str.strip().iloc[0] == "STD-BOY"


def test_join_key_match_succeeds_with_valid_pool_row() -> None:
    policy = load_policy()
    students = pd.DataFrame([_student_row("STD-GIRL", group_code=3, gender=0)])
    pool = pd.DataFrame(
        [
            _pool_row(2504, group_code=21, gender=0, capacity=0),
            _pool_row(9503, group_code=3, gender=0, capacity=2),
        ]
    )

    allocations, _, logs, trace = allocate_batch(students, pool, policy=policy)

    assert len(allocations) == 1
    assert allocations.loc[0, "student_id"] == "STD-GIRL"
    assert logs.loc[0, "allocation_status"] == "success"
    assert logs.loc[0, "error_type"] in (None, "", pd.NA)
    assert trace["student_id"].astype(str).str.strip().iloc[0] == "STD-GIRL"

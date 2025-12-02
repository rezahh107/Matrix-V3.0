import pandas as pd
import pytest

from app.core.canonical_frames import canonicalize_students_frame
from app.core.policy_loader import load_policy
from app.infra.canonical_frames import build_student_group_crosswalk


def test_student_crosswalk_merges_raw_group_codes() -> None:
    policy = load_policy()
    crosswalk = pd.DataFrame(
        {
            "گروه آزمایشی": ["علوم پایه", "علوم پایه"],
            "کد گروه": [5, 5],
            "کدرشته خام": [9110, 9120],
            "مقطع تحصیلی": ["دهم", "یازدهم"],
        }
    )
    mapping = build_student_group_crosswalk(crosswalk)

    students = pd.DataFrame(
        {
            "student_id": ["STD-1", "STD-2"],
            "کدرشته": [9110, 9120],
            "گروه آزمایشی": ["علوم پایه", "علوم پایه"],
            "جنسیت": [1, 1],
            "دانش آموز فارغ": [0, 0],
            "مرکز گلستان صدرا": [0, 0],
            "مالی حکمت بنیاد": [0, 0],
            "کد مدرسه": [0, 0],
        }
    )

    normalized = canonicalize_students_frame(students, policy=policy, group_code_crosswalk=mapping)

    assert normalized["کدرشته"].tolist() == [5, 5]
    assert normalized["group_code_raw"].tolist() == ["9110", "9120"]


def test_student_crosswalk_supports_group_names() -> None:
    policy = load_policy()
    crosswalk = pd.DataFrame(
        {
            "گروه آزمایشی": ["علوم پایه"],
            "کد گروه": [5],
            "کدرشته خام": [pd.NA],
            "مقطع تحصیلی": ["دهم"],
        }
    )
    mapping = build_student_group_crosswalk(crosswalk)

    students = pd.DataFrame(
        {
            "student_id": ["STD-3"],
            "کدرشته": ["علوم پایه"],
            "گروه آزمایشی": ["علوم پایه"],
            "جنسیت": [1],
            "دانش آموز فارغ": [0],
            "مرکز گلستان صدرا": [0],
            "مالی حکمت بنیاد": [0],
            "کد مدرسه": [0],
        }
    )

    normalized = canonicalize_students_frame(students, policy=policy, group_code_crosswalk=mapping)

    assert normalized["کدرشته"].tolist() == [5]


def test_student_crosswalk_unknown_group_fails_loudly() -> None:
    policy = load_policy()
    crosswalk = pd.DataFrame(
        {
            "گروه آزمایشی": ["ریاضی"],
            "کد گروه": [1200],
            "کدرشته خام": [1200],
            "مقطع تحصیلی": ["دهم"],
        }
    )
    mapping = build_student_group_crosswalk(crosswalk)

    students = pd.DataFrame(
        {
            "student_id": ["STD-404"],
            "کدرشته": [9999],
            "گروه آزمایشی": ["نامعلوم"],
            "جنسیت": [1],
            "دانش آموز فارغ": [0],
            "مرکز گلستان صدرا": [0],
            "مالی حکمت بنیاد": [0],
            "کد مدرسه": [0],
        }
    )

    with pytest.raises(ValueError, match="Unknown group code.*کدرشته"):
        canonicalize_students_frame(students, policy=policy, group_code_crosswalk=mapping)


def test_canonicalize_students_frame_handles_localized_join_keys() -> None:
    policy = load_policy()
    students = pd.DataFrame(
        {
            "student_id": ["s1"],
            "کدرشته": ["۲۱"],
            "جنسیت": ["پسر"],
            "دانش آموز فارغ": ["۰"],
            "مرکز گلستان صدرا": ["۰"],
            "مالی حکمت بنیاد": [["۱", "0"]],
            "کد مدرسه": ["۰"],
        }
    )

    canonical = canonicalize_students_frame(students, policy=policy)

    assert canonical["جنسیت"].iloc[0] == policy.gender_codes.male.value
    assert all(canonical[column].dtype == "int64" for column in policy.join_keys)


def test_canonicalize_students_frame_aligns_with_core_canonicalization() -> None:
    policy = load_policy()
    students = pd.DataFrame(
        {
            "student_id": ["s1", "s2"],
            policy.stage_column("group"): ["۲۱", "۲۱"],
            policy.stage_column("gender"): ["پسر", "دختر"],
            policy.stage_column("graduation_status"): [0, 1],
            policy.stage_column("center"): ["۰", "1"],
            policy.stage_column("finance"): [["۱", "0"], "۳"],
            policy.columns.school_code: [0, "۰"],
        }
    )

    canonical = canonicalize_students_frame(students, policy=policy)
    direct_gender = canonical[policy.stage_column("gender")].tolist()

    assert direct_gender == [policy.gender_codes.male.value, policy.gender_codes.female.value]
    assert canonical[policy.stage_column("finance")].tolist()[0] == 1

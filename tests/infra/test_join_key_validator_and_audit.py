import pandas as pd
import pytest

from app.core.policy_loader import load_policy
from app.infra.cli import assert_student_id_integrity, normalize_national_id
from app.infra.cli_legacy import AllocationConsistencyError, _validate_allocated_student_ids
from app.infra.excel.qa_export import (
    build_join_key_audit_sheet,
    build_join_key_summary_sheet,
)
from app.infra.validators.join_keys import validate_allocation_join_keys


def _sample_frames():
    policy = load_policy()
    students = pd.DataFrame(
        [
            {
                "student_id": "S-1",
                "کدرشته": 3,
                "گروه آزمایشی": 3,
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 1,
                "مالی حکمت بنیاد": 1,
                "کد مدرسه": 10,
            },
            {
                "student_id": "S-2",
                "کدرشته": 21,
                "گروه آزمایشی": 21,
                "جنسیت": 0,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 1,
                "مالی حکمت بنیاد": 1,
                "کد مدرسه": 10,
            },
        ]
    )
    pool = pd.DataFrame(
        [
            {
                "mentor_id": "M-1",
                "mentor_alias_code": "2504",
                "کدرشته": 3,
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 1,
                "مالی حکمت بنیاد": 1,
                "کد مدرسه": 10,
                "remaining_capacity": 2,
            },
            {
                "mentor_id": "M-2",
                "mentor_alias_code": "1111",
                "کدرشته": 21,
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 1,
                "مالی حکمت بنیاد": 1,
                "کد مدرسه": 10,
                "remaining_capacity": 1,
            },
        ]
    )
    allocations = pd.DataFrame(
        [
            {"student_id": "S-1", "mentor_id": "M-1", "mentor_alias_code": "2504"},
            {"student_id": "S-2", "mentor_id": "M-2", "mentor_alias_code": "1111"},
        ]
    )
    return policy, students, pool, allocations


def test_validate_allocation_join_keys_flags_mismatch():
    policy, students, pool, allocations = _sample_frames()
    # introduce mismatch: wrong gender for second mentor
    pool.loc[1, "جنسیت"] = 1  # student gender=0 → mismatch

    result = validate_allocation_join_keys(allocations, students, pool, policy=policy)

    assert result.total == 2
    assert result.invalid_count == 1
    audit = result.audit_frame
    mismatch_row = audit.loc[audit["student_id"] == "S-2"].iloc[0]
    assert bool(mismatch_row["any_mismatch"]) is True
    assert bool(mismatch_row["match_جنسیت"]) is False
    assert "جنسیت" in str(mismatch_row["mismatch_summary"])
    assert result.duplicate_columns == {key: 0 for key in policy.join_keys}


def test_validate_allocation_join_keys_counts_per_allocation_not_profiles() -> None:
    policy = load_policy()
    students = pd.DataFrame(
        [
            {
                "student_id": "S-1",
                "کدرشته": 2,
                "گروه آزمایشی": 2,
                "جنسیت": 0,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 10,
                "مالی حکمت بنیاد": 1,
                "کد مدرسه": 101,
            }
        ]
    )
    pool = pd.DataFrame(
        [
            {
                "mentor_id": "M-1",
                "remaining_capacity": 1,
                "کدرشته": 2,
                "جنسیت": 1,
                "دانش آموز فارغ": 1,
                "مرکز گلستان صدرا": 11,
                "مالی حکمت بنیاد": 0,
                "کد مدرسه": 999,
            },
            {
                "mentor_id": "M-1",
                "remaining_capacity": 1,
                "کدرشته": 3,
                "جنسیت": 1,
                "دانش آموز فارغ": 1,
                "مرکز گلستان صدرا": 12,
                "مالی حکمت بنیاد": 0,
                "کد مدرسه": 998,
            },
        ]
    )
    allocations = pd.DataFrame([{"student_id": "S-1", "mentor_id": "M-1"}])

    result = validate_allocation_join_keys(allocations, students, pool, policy=policy)

    assert result.total == 2
    assert result.invalid_count == 1
    audit = result.audit_frame
    assert audit["student_id"].nunique() == 1
    assert audit["any_mismatch"].all()


def test_validate_allocation_join_keys_does_not_require_alias_when_mentor_id_present() -> None:
    policy, students, pool, allocations = _sample_frames()
    # Ensure no real join-key mismatch exists.
    pool.loc[1, "جنسیت"] = 0

    # Alias code might be blank/missing in allocations even when mentor_id is present.
    allocations.loc[0, "mentor_alias_code"] = pd.NA

    result = validate_allocation_join_keys(allocations, students, pool, policy=policy)

    assert result.invalid_count == 0
    row = result.audit_frame.loc[result.audit_frame["student_id"] == "S-1"].iloc[0]
    assert str(row.get("mentor_lookup_mode", "")) in {"mentor_id", "mentor_alias", "missing"}


def test_validate_allocation_join_keys_handles_duplicate_join_columns_gender():
    policy, students, pool, allocations = _sample_frames()

    pool.loc[1, "جنسیت"] = 0
    gender_pos = students.columns.get_loc("جنسیت") + 1
    students.insert(gender_pos, "gender", students["جنسیت"] * 0)
    pool.insert(pool.columns.get_loc("جنسیت") + 1, "gender", pool["جنسیت"] * 0)

    result = validate_allocation_join_keys(allocations, students, pool, policy=policy)

    assert result.invalid_count == 0
    assert result.total == allocations.shape[0]
    assert result.audit_frame["جنسیت"].dtype == "Int64"
    assert result.audit_frame["جنسیت_mentor"].dtype == "Int64"
    assert result.duplicate_columns["جنسیت"] == 2  # one per dataframe copy
    assert "جنسیت" in result.audit_frame.loc[0, "duplicate_join_key_keys"]
    assert int(result.audit_frame.loc[0, "duplicate_join_key_columns"]) > 0


def test_validate_allocation_join_keys_handles_duplicate_finance_columns():
    policy, students, pool, allocations = _sample_frames()

    finance_pos_students = students.columns.get_loc("مالی حکمت بنیاد") + 1
    finance_pos_pool = pool.columns.get_loc("مالی حکمت بنیاد") + 1
    pool.loc[1, "جنسیت"] = 0
    students.insert(finance_pos_students, "finance", students["مالی حکمت بنیاد"])
    pool.insert(finance_pos_pool, "finance", pool["مالی حکمت بنیاد"] * 0)

    result = validate_allocation_join_keys(allocations, students, pool, policy=policy)

    assert result.invalid_count == 0
    assert result.audit_frame["مالی حکمت بنیاد"].dtype == "Int64"
    assert result.audit_frame["مالی حکمت بنیاد_mentor"].dtype == "Int64"
    assert result.duplicate_columns["مالی حکمت بنیاد"] == 2
    assert "مالی حکمت بنیاد" in result.audit_frame.loc[0, "duplicate_join_key_keys"]


def test_validate_allocation_join_keys_handles_mixed_duplicate_columns():
    policy, students, pool, allocations = _sample_frames()

    gender_pos = students.columns.get_loc("جنسیت") + 1
    school_pos = students.columns.get_loc("کد مدرسه") + 1
    pool.loc[1, "جنسیت"] = 0
    students.insert(gender_pos, "gender", students["جنسیت"])
    students.insert(school_pos + 1, "school_code", students["کد مدرسه"])

    pool.insert(pool.columns.get_loc("جنسیت") + 1, "gender", pool["جنسیت"])
    pool.insert(pool.columns.get_loc("کد مدرسه") + 1, "school_code", pool["کد مدرسه"])

    result = validate_allocation_join_keys(allocations, students, pool, policy=policy)

    assert result.invalid_count == 0
    assert result.total == allocations.shape[0]
    assert result.duplicate_columns["جنسیت"] >= 2
    assert result.duplicate_columns["کد مدرسه"] >= 2
    assert "جنسیت" in result.audit_frame.loc[0, "duplicate_join_key_keys"]
    assert "کد مدرسه" in result.audit_frame.loc[0, "duplicate_join_key_keys"]
    assert pd.api.types.is_integer_dtype(result.audit_frame["کد مدرسه"])
    assert pd.api.types.is_integer_dtype(result.audit_frame["کد مدرسه_mentor"])


def test_join_key_audit_and_summary_builders():
    policy, students, pool, allocations = _sample_frames()
    pool.loc[1, "جنسیت"] = 0
    result = validate_allocation_join_keys(allocations, students, pool, policy=policy)

    audit_sheet = build_join_key_audit_sheet(result.audit_frame, policy=policy)
    summary_sheet = build_join_key_summary_sheet(result.audit_frame)

    assert not audit_sheet.empty
    assert "any_mismatch" in audit_sheet.columns
    assert summary_sheet.loc[0, "total"] == 2
    assert summary_sheet.loc[0, "invalid_count"] == 0


def test_assert_student_id_integrity_rejects_missing_column() -> None:
    frame = pd.DataFrame({"value": [1, 2]})

    with pytest.raises(AllocationConsistencyError):
        assert_student_id_integrity(frame, header_mode="en")


def test_assert_student_id_integrity_rejects_null_and_duplicate_ids() -> None:
    frame = pd.DataFrame({"student_id": ["S-1", pd.NA, "S-1"]})

    with pytest.raises(AllocationConsistencyError):
        assert_student_id_integrity(frame, header_mode="en")


def test_assert_student_id_integrity_allows_duplicates_when_opted_out() -> None:
    frame = pd.DataFrame({"student_id": ["S-1", "S-1"]})

    out = assert_student_id_integrity(frame, header_mode="en", expect_unique=False)

    assert out["student_id"].tolist() == ["S-1", "S-1"]


def test_assert_student_id_integrity_checks_against_spine() -> None:
    frame = pd.DataFrame({"student_id": ["S-1", "S-2"]})
    spine = pd.DataFrame({"student_id": ["S-1"]})

    with pytest.raises(AllocationConsistencyError):
        assert_student_id_integrity(frame, header_mode="en", students_df=spine)


@pytest.mark.parametrize(
    "raw, expected",
    [
        (" ۱۲۳۴۵۶۷۸۹ ", "0123456789"),
        ("۱۲۳-۴۵۶-۷۸۹۰", "1234567890"),
        ("۰۰۱", "0000000001"),
        ("abc", None),
        (None, None),
    ],
)
def test_normalize_national_id_variants(raw, expected):
    assert normalize_national_id(raw) == expected


def test_validate_allocated_student_ids_raises_on_mismatch():
    allocations = pd.DataFrame({"student_id": ["S-1"]})
    logs = pd.DataFrame(
        {
            "student_id": ["S-2"],
            "allocation_status": ["success"],
        }
    )

    with pytest.raises(AllocationConsistencyError):
        _validate_allocated_student_ids(allocations_df=allocations, logs_df=logs)


def test_validate_allocated_student_ids_filters_success_status():
    allocations = pd.DataFrame({"student_id": ["S-1", "S-2"]})
    logs = pd.DataFrame(
        {
            "student_id": ["S-1", "S-3"],
            "allocation_status": ["failed", "success"],
        }
    )

    with pytest.raises(AllocationConsistencyError):
        _validate_allocated_student_ids(allocations_df=allocations, logs_df=logs)

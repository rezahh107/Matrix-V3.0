import pandas as pd
import pytest

from app.core.policy_loader import load_policy
from app.infra.cli import attach_student_id_column, normalize_national_id
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


def test_attach_student_id_column_fills_missing_and_nan():
    frame = pd.DataFrame(
        {
            "student_id": [" ", " nan ", pd.NA],
            "national_id": ["N1", "N2", "N3"],
            "value": [1, 2, 3],
        }
    )
    ids = pd.Series(["S-1", "S-2", "S-3"], index=[10, 11, 12])
    students = pd.DataFrame(
        {"student_id": ["S-1", "S-2", "S-3"], "national_id": ["N1", "N2", "N3"]},
        index=[10, 11, 12],
    )

    result = attach_student_id_column(
        frame, ids, header_mode="en", ensure_existing=True, students_df=students
    )

    assert result["student_id"].tolist() == ["S-1", "S-2", "S-3"]
    assert "value" in result.columns


def test_attach_student_id_column_preserves_existing_values():
    frame = pd.DataFrame(
        {
            "student_id": ["S-1", "S-2"],
            "mentor_id": ["M-1", "M-2"],
        },
        index=[10, 11],
    )
    ids = pd.Series(["S-10", "S-11"], index=[11, 10])

    result = attach_student_id_column(frame, ids, header_mode="en", ensure_existing=True)

    assert result["student_id"].tolist() == ["S-1", "S-2"]
    assert result["mentor_id"].tolist() == ["M-1", "M-2"]


def test_attach_student_id_column_respects_completed_ids():
    frame = pd.DataFrame(
        {
            "student_id": ["S-1", "S-2"],
            "national_id": ["N-1", "N-2"],
        }
    )
    ids = pd.Series(["S-10", "S-20"])

    result = attach_student_id_column(frame, ids, header_mode="en", ensure_existing=False)

    assert result["student_id"].tolist() == ["S-1", "S-2"]


def test_attach_student_id_column_preserves_existing_with_ensure_flag():
    frame = pd.DataFrame({"student_id": ["S-1", "S-2"], "extra": [1, 2]})
    ids = pd.Series(["A", "B"], index=[1, 0])

    result = attach_student_id_column(frame, ids, header_mode="en", ensure_existing=True)

    assert result["student_id"].tolist() == ["S-1", "S-2"]
    assert result["extra"].tolist() == [1, 2]


def test_attach_student_id_column_uses_national_id_join():
    students = pd.DataFrame(
        {"student_id": ["S-1", "S-2"], "national_id": ["N-1", "N-2"]},
        index=[2, 1],
    )
    frame = pd.DataFrame(
        {
            "national_id": ["N-2", "N-1"],
            "student_id": [pd.NA, ""],
        },
        index=[100, 200],
    )
    ids = students["student_id"]

    result = attach_student_id_column(
        frame, ids, header_mode="en", ensure_existing=True, students_df=students
    )

    assert result["student_id"].tolist() == ["S-2", "S-1"]


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


def test_attach_student_id_column_fills_via_national_id_with_normalization():
    students = pd.DataFrame(
        {"student_id": ["S-1", "S-2"], "national_id": ["۱۲۳۴۵۶۷۸۹", "0000000002"]}
    )
    frame = pd.DataFrame(
        {"student_id": [pd.NA, ""], "national_id": ["۰۱۲۳۴۵۶۷۸۹", "۲"]}
    )

    result = attach_student_id_column(
        frame,
        students["student_id"],
        header_mode="en",
        ensure_existing=True,
        students_df=students,
    )

    assert result["student_id"].tolist() == ["S-1", "S-2"]


def test_attach_student_id_column_raises_on_duplicate_national_id():
    students = pd.DataFrame(
        {
            "student_id": ["S-1", "S-2"],
            "national_id": ["123", "123"],
        }
    )
    frame = pd.DataFrame({"national_id": ["123", "123"], "student_id": [pd.NA, pd.NA]})

    with pytest.raises(AllocationConsistencyError):
        attach_student_id_column(
            frame,
            students["student_id"],
            header_mode="en",
            ensure_existing=True,
            students_df=students,
        )


def test_attach_student_id_column_raises_on_missing_national_id_for_needed_rows():
    students = pd.DataFrame(
        {"student_id": ["S-1"], "national_id": ["1234567890"]}
    )
    frame = pd.DataFrame({"student_id": [pd.NA], "national_id": [" "]})

    with pytest.raises(AllocationConsistencyError):
        attach_student_id_column(
            frame,
            students["student_id"],
            header_mode="en",
            ensure_existing=True,
            students_df=students,
        )


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

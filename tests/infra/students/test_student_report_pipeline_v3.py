from pathlib import Path

import pandas as pd

from app.core.policy_loader import load_policy
from app.infra.local_database import LocalDatabase
from app.infra.reference_students_repository import import_student_report_with_validation


def _write_excel(df: pd.DataFrame, path: Path):
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)


def test_student_report_aliases_produce_join_keys(tmp_path):
    policy = load_policy()
    db = LocalDatabase(tmp_path / "cache.sqlite")
    raw = pd.DataFrame(
        {
            "student_id": ["s1"],
            "گروه آزمایشی نهایی": ["27"],
            "وضعیت تحصیلی": [1],
            "مرکز ثبت نام": [1],
            "مدرسه نهایی": [1001],
            "جنسیت": [1],
            "مالی حکمت بنیاد": [0],
        }
    )
    excel_path = tmp_path / "students.xlsx"
    _write_excel(raw, excel_path)

    bundle = import_student_report_with_validation(excel_path, db=db, policy=policy)

    assert not bundle.join_keys.issues
    assert set(policy.join_keys).issubset(bundle.canonical_df.columns)


def test_student_report_header_normalization_handles_variants(tmp_path):
    policy = load_policy()
    db = LocalDatabase(tmp_path / "cache.sqlite")
    raw = pd.DataFrame(
        {
            "student_id": ["s1"],
            " گروه‌آزمایشی نهایی ": [27],
            "  وضعیت‌تحصیلی": [1],
            "مرکز  ثبت‌نام": [1],
            "مدرسه‌ نهايی": [1001],
            "جنسيت": [0],
            "مالی حکمت بنیاد": [0],
        }
    )
    excel_path = tmp_path / "students.xlsx"
    _write_excel(raw, excel_path)

    bundle = import_student_report_with_validation(excel_path, db=db, policy=policy)

    assert not bundle.join_keys.issues
    assert set(policy.join_keys).issubset(bundle.canonical_df.columns)


def test_student_report_missing_alias_surfaces_missing_column(tmp_path):
    policy = load_policy()
    db = LocalDatabase(tmp_path / "cache.sqlite")
    raw = pd.DataFrame(
        {
            "student_id": ["s1"],
            "نام درس": ["x"],
            "جنسیت": [1],
            "مالی حکمت بنیاد": [0],
            "مدرسه نهایی": [1001],
        }
    )
    excel_path = tmp_path / "students.xlsx"
    _write_excel(raw, excel_path)

    bundle = import_student_report_with_validation(excel_path, db=db, policy=policy)

    missing_columns = {issue.column for issue in bundle.join_keys.issues if issue.error_code == "MISSING_COLUMN"}
    assert "کدرشته" in missing_columns
    hint_issue = next(
        issue for issue in bundle.join_keys.issues if issue.column == "کدرشته" and issue.row_index == -1
    )
    assert "accepted_aliases" in str(hint_issue.raw_value)
    assert bundle.join_keys.canonical_df.empty


def test_student_report_registration_status_alias_used_for_finance(tmp_path):
    policy = load_policy()
    db = LocalDatabase(tmp_path / "cache.sqlite")
    raw = pd.DataFrame(
        {
            "student_id": ["s1"],
            "جنسیت": [1],
            "کدرشته": [101],
            "دانش آموز فارغ": [0],
            "مرکز گلستان صدرا": [12],
            "کد مدرسه": [2001],
            "وضعیت ثبت نام": [3],
        }
    )
    excel_path = tmp_path / "students.xlsx"
    _write_excel(raw, excel_path)

    bundle = import_student_report_with_validation(excel_path, db=db, policy=policy)

    finance_missing = [
        issue
        for issue in bundle.join_keys.issues
        if issue.error_code == "MISSING_COLUMN" and issue.column == "مالی حکمت بنیاد"
    ]
    assert not finance_missing
    assert "مالی حکمت بنیاد" in bundle.canonical_df.columns
    assert bundle.canonical_df.loc[:, "مالی حکمت بنیاد"].tolist() == [3]


def test_student_report_registration_status_conflict_is_deterministic(tmp_path):
    policy = load_policy()
    db = LocalDatabase(tmp_path / "cache.sqlite")
    raw = pd.DataFrame(
        {
            "student_id": ["s1"],
            "جنسیت": [0],
            "کدرشته": [202],
            "دانش آموز فارغ": [1],
            "مرکز گلستان صدرا": [7],
            "کد مدرسه": [3001],
            "مالی حکمت بنیاد": [0],
            "وضعیت ثبت نام": [5],
        }
    )
    excel_path = tmp_path / "students.xlsx"
    _write_excel(raw, excel_path)

    bundle = import_student_report_with_validation(excel_path, db=db, policy=policy)

    assert not bundle.join_keys.issues
    assert bundle.canonical_df.loc[:, "مالی حکمت بنیاد"].tolist() == [0]

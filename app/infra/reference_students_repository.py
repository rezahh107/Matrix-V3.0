"""مخزن مرجع برای کش StudentReport در SQLite.

این لایه مسئول خواندن StudentReport از Excel/CSV، نرمال‌سازی بر اساس Policy و
ذخیرهٔ نسخهٔ تمیز در جدول ``students_cache`` است. Core از تغییرات ذخیره‌سازی
بی‌خبر می‌ماند و همچنان DataFrame دریافت می‌کند.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.common.types import StudentValidationBundle
from app.core.policy_loader import PolicyConfig
from app.infra.errors import JoinKeyValidationError
from app.infra.groupcode.groupcode_repository import GroupCodeRepository
from app.infra.io_utils import read_excel_first_sheet
from app.infra.local_database import LocalDatabase, _coerce_int_columns
from app.infra.schools.school_repository import SchoolRepository
from app.infra.students.pipeline_v3 import StudentPipelineV3


def _read_student_source(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls", ".xlsm"}:
        return read_excel_first_sheet(path)
    return pd.read_csv(path)


def _db_backed_pipeline(*, db: LocalDatabase, policy: PolicyConfig) -> StudentPipelineV3:
    """Build the existing DB-mode pipeline against one authoritative LocalDatabase."""

    school_repo = SchoolRepository(db)
    groupcode_repo = GroupCodeRepository(db)
    return StudentPipelineV3(
        policy=policy,
        header_mode="fa",
        reference_mode="db",
        db=db,
        school_repo=school_repo,
        groupcode_repo=groupcode_repo,
    )


def _run_student_import(path: Path, *, db: LocalDatabase, policy: PolicyConfig):
    """Run the authoritative DB-backed pipeline once and persist its canonical frame."""

    raw_df = _read_student_source(path)
    pipeline = _db_backed_pipeline(db=db, policy=policy)
    result = pipeline.run(raw_df)
    db.upsert_students_cache(result.canonical_df, join_keys=policy.join_keys)
    return result


def import_student_report_with_validation(
    path: Path, *, db: LocalDatabase, policy: PolicyConfig
) -> StudentValidationBundle:
    """وارد کردن StudentReport با مراجع عملیاتی DB و ذخیره در کش SQLite.

    ``schools`` و ``groupcodes`` از همان ``LocalDatabase`` فعال خوانده می‌شوند؛
    فایل StudentReport هرگز GroupCode authority موازی ایجاد نمی‌کند.
    """

    return _run_student_import(path, db=db, policy=policy).validation


def import_student_report_from_excel(
    path: Path, *, db: LocalDatabase, policy: PolicyConfig
) -> pd.DataFrame:
    """Compatibility wrapper returning only canonical student data."""

    result = _run_student_import(path, db=db, policy=policy)
    if result.validation.join_keys.issues:
        raise JoinKeyValidationError(result.validation.join_keys)
    return result.canonical_df


def load_students_from_cache(*, db: LocalDatabase, policy: PolicyConfig) -> pd.DataFrame:
    """Load cached students and revalidate them against current DB references.

    The cache is storage, not a reference authority. Re-running the existing DB-mode
    student pipeline ensures a cache produced under GroupCode state A cannot silently
    bypass the currently active GroupCode state B.
    """

    cached = db.load_students_cache(join_keys=policy.join_keys)
    cached = _coerce_int_columns(cached, policy.join_keys)
    pipeline = _db_backed_pipeline(db=db, policy=policy)
    result = pipeline.run(cached)
    if result.validation.join_keys.issues:
        raise JoinKeyValidationError(result.validation.join_keys)
    return _coerce_int_columns(result.canonical_df, policy.join_keys)


__all__ = [
    "import_student_report_from_excel",
    "load_students_from_cache",
]

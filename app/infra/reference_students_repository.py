"""مخزن مرجع برای کش StudentReport در SQLite.

این لایه مسئول خواندن StudentReport از Excel/CSV، نرمال‌سازی بر اساس Policy و
ذخیرهٔ نسخهٔ تمیز در جدول ``students_cache`` است. Core از تغییرات ذخیره‌سازی
بی‌خبر می‌ماند و همچنان DataFrame دریافت می‌کند.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.canonical_frames import canonicalize_students_frame
from app.core.common.columns import canonicalize_headers
from app.core.common.join_keys import validate_and_canonicalize_join_keys
from app.core.common.types import (
    StudentDomainValidationResult,
    StudentValidationBundle,
)
from app.core.policy_loader import PolicyConfig
from app.core.students.domain_validation import validate_student_domain
from app.infra.errors import JoinKeyValidationError
from app.infra.io_utils import read_excel_first_sheet
from app.infra.local_database import LocalDatabase, _coerce_int_columns


def _read_student_source(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls", ".xlsm"}:
        return read_excel_first_sheet(path)
    return pd.read_csv(path)


def import_student_report_with_validation(
    path: Path, *, db: LocalDatabase, policy: PolicyConfig
) -> StudentValidationBundle:
    """وارد کردن StudentReport از دیسک و ذخیره در کش SQLite.

    دیتافریم خروجی بر اساس Policy نرمال شده و سپس در ``students_cache``
    ذخیره می‌شود تا اجرای بعدی بدون خواندن مجدد Excel انجام شود.
    """

    raw_df = _read_student_source(path)
    raw_df = canonicalize_headers(raw_df, header_mode="fa")
    validation = validate_and_canonicalize_join_keys(raw_df, policy=policy, entity_type="student")
    if validation.issues:
        return StudentValidationBundle(
            join_keys=validation,
            domain=StudentDomainValidationResult(canonical_df=validation.canonical_df, issues=[]),
        )
    normalized = canonicalize_students_frame(validation.canonical_df, policy=policy)
    domain_result = validate_student_domain(normalized, policy=policy)
    db.upsert_students_cache(domain_result.canonical_df, join_keys=policy.join_keys)
    return StudentValidationBundle(join_keys=validation, domain=domain_result)


def import_student_report_from_excel(
    path: Path, *, db: LocalDatabase, policy: PolicyConfig
) -> pd.DataFrame:
    """Compatibility wrapper returning only canonical student data."""

    result = import_student_report_with_validation(path, db=db, policy=policy)
    if result.join_keys.issues:
        raise JoinKeyValidationError(result.join_keys)
    return result.canonical_df


def load_students_from_cache(*, db: LocalDatabase, policy: PolicyConfig) -> pd.DataFrame:
    """بازیابی دیتافریم نرمال‌شدهٔ دانش‌آموزان از SQLite."""

    cached = db.load_students_cache(join_keys=policy.join_keys)
    return _coerce_int_columns(cached, policy.join_keys)


__all__ = [
    "import_student_report_from_excel",
    "load_students_from_cache",
]

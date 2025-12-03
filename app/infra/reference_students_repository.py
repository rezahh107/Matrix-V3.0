"""مخزن مرجع برای کش StudentReport در SQLite.

این لایه مسئول خواندن StudentReport از Excel/CSV، نرمال‌سازی بر اساس Policy و
ذخیرهٔ نسخهٔ تمیز در جدول ``students_cache`` است. Core از تغییرات ذخیره‌سازی
بی‌خبر می‌ماند و همچنان DataFrame دریافت می‌کند.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.canonical_frames import canonicalize_students_frame
from app.core.common.join_keys import validate_and_canonicalize_join_keys
from app.core.common.types import JoinKeyValidationResult
from app.core.policy_loader import PolicyConfig
from app.infra.io_utils import read_excel_first_sheet
from app.infra.local_database import LocalDatabase, _coerce_int_columns


def _read_student_source(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls", ".xlsm"}:
        return read_excel_first_sheet(path)
    return pd.read_csv(path)


def import_student_report_with_validation(
    path: Path, *, db: LocalDatabase, policy: PolicyConfig
) -> JoinKeyValidationResult:
    """وارد کردن StudentReport از دیسک و ذخیره در کش SQLite.

    دیتافریم خروجی بر اساس Policy نرمال شده و سپس در ``students_cache``
    ذخیره می‌شود تا اجرای بعدی بدون خواندن مجدد Excel انجام شود.
    """

    raw_df = _read_student_source(path)
    validation = validate_and_canonicalize_join_keys(raw_df, policy=policy, entity_type="student")
    normalized = canonicalize_students_frame(validation.canonical_df, policy=policy)
    db.upsert_students_cache(normalized, join_keys=policy.join_keys)
    return JoinKeyValidationResult(canonical_df=normalized, issues=validation.issues)


def import_student_report_from_excel(
    path: Path, *, db: LocalDatabase, policy: PolicyConfig
) -> pd.DataFrame:
    """Compatibility wrapper returning only canonical student data."""

    result = import_student_report_with_validation(path, db=db, policy=policy)
    return result.canonical_df


def load_students_from_cache(*, db: LocalDatabase, policy: PolicyConfig) -> pd.DataFrame:
    """بازیابی دیتافریم نرمال‌شدهٔ دانش‌آموزان از SQLite."""

    cached = db.load_students_cache(join_keys=policy.join_keys)
    return _coerce_int_columns(cached, policy.join_keys)


__all__ = [
    "import_student_report_from_excel",
    "load_students_from_cache",
]

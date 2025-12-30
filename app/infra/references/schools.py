"""مخزن مرجع مدارس و Crosswalk با تکیه بر SQLite."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.infra.common.header_pipeline_v3 import HeaderIssue
from app.infra.io_utils import ALT_CODE_COLUMN, read_crosswalk_workbook, read_excel_first_sheet
from app.infra.local_database import LocalDatabase
from app.infra.reference_repository import SQLiteReferenceRepository
from app.infra.schools.header_resolver import SchoolHeaderResolver
from app.infra.schools.school_repository import SchoolRepository
from app.infra.sqlite_types import coerce_int_columns, coerce_int_series


def _coerce_school_code(series: pd.Series, *, fill_value: int | None = None) -> pd.Series:
    """تبدیل ستون کد مدرسه به نوع Int64 با مقدار پیش‌فرض مشخص."""

    return coerce_int_series(series, fill_value=fill_value)


_SCHOOL_COMPAT_DEFAULTS: dict[str, object] = {
    "مرکز گلستان صدرا": 0,
    "جنسیت": 0,
    "نام مدرسه": "",
}


def _normalize_schools_frame(
    df: pd.DataFrame,
    *,
    path: Path | str | None = None,
    compat_mode: bool = False,
) -> pd.DataFrame:
    """نرمال‌سازی دیتافریم مدارس برای ذخیره‌سازی قابل‌اتکا در SQLite."""

    resolver = SchoolHeaderResolver(
        required_fields=list(SchoolRepository.REQUIRED_COLUMNS)
    )
    resolution = resolver.resolve(df)
    missing_required = list(resolution.missing_required)
    if missing_required and compat_mode:
        allowed_missing = sorted(
            [col for col in missing_required if col in _SCHOOL_COMPAT_DEFAULTS]
        )
        blocking_missing = sorted(
            [col for col in missing_required if col not in _SCHOOL_COMPAT_DEFAULTS]
        )
        if blocking_missing:
            resolution.require_can_continue(
                path=str(path) if path is not None else "SchoolReport",
                reason_fa="ستون‌های الزامی مدارس در فایل موجود نیست.",
            )
        canonical = resolution.resolved_df.copy()
        compat_notes: list[dict[str, object]] = []
        issues: list[HeaderIssue] = []
        for column in allowed_missing:
            default_value = _SCHOOL_COMPAT_DEFAULTS[column]
            canonical[column] = default_value
            compat_notes.append(
                {
                    "column": column,
                    "default": default_value,
                    "issue": "COMPAT_DEFAULT_APPLIED",
                }
            )
            issues.append(
                HeaderIssue(
                    severity="P1",
                    header=str(column),
                    message="COMPAT_DEFAULT_APPLIED",
                    canonical_field=str(column),
                    extras={"default": default_value},
                )
            )
        if compat_notes:
            canonical.attrs = dict(canonical.attrs or {})
            canonical.attrs["compat_notes"] = compat_notes
            resolution.add_issues(issues)
    else:
        canonical = resolution.require_can_continue(
            path=str(path) if path is not None else "SchoolReport",
            reason_fa="ستون‌های الزامی مدارس در فایل موجود نیست.",
        )
    code_col = "کد مدرسه"
    if code_col in canonical.columns:
        canonical = canonical.copy()
        canonical[code_col] = _coerce_school_code(canonical[code_col])
    return canonical


def _schools_repository(db: LocalDatabase) -> SQLiteReferenceRepository:
    return SQLiteReferenceRepository(
        db=db,
        table_name="schools",
        int_columns=("کد مدرسه",),
        unique_columns=("کد مدرسه",),
    )


def import_school_report_from_excel(
    path: Path,
    db: LocalDatabase,
    *,
    compat_mode: bool = False,
) -> pd.DataFrame:
    """ورود SchoolReport از Excel و ذخیره در SQLite.

    این تابع فایل گزارش مدارس را یک‌بار می‌خواند، سرستون‌ها را به حالت
    استاندارد تبدیل می‌کند، ستون «کد مدرسه» را به نوع عددی Int64
    درمی‌آورد و سپس در جدول مرجع ``schools`` ذخیره می‌کند.
    """

    raw_df = read_excel_first_sheet(path)
    normalized = _normalize_schools_frame(raw_df, path=path, compat_mode=compat_mode)
    _schools_repository(db).upsert_frame(normalized, source=str(path))
    return normalized


def import_school_crosswalk_from_excel(
    path: Path, db: LocalDatabase
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """ورود Crosswalk مدارس (گروه‌ها و Synonyms) و ذخیره در SQLite."""

    groups_df, synonyms_df = read_crosswalk_workbook(path)
    groups_df = coerce_int_columns(groups_df, ["کد مدرسه", ALT_CODE_COLUMN])
    if synonyms_df is not None:
        synonyms_df = coerce_int_columns(synonyms_df, ["کد مدرسه", ALT_CODE_COLUMN])
    db.upsert_school_crosswalk(groups_df, synonyms_df=synonyms_df)
    return groups_df, synonyms_df


def get_school_reference_frames(
    db: LocalDatabase,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None]:
    """بازیابی دیتافریم‌های مرجع مدارس و Crosswalk از SQLite."""

    schools_df = _schools_repository(db).load_frame()
    crosswalk_groups_df, crosswalk_synonyms_df = db.load_school_crosswalk()
    return schools_df, crosswalk_groups_df, crosswalk_synonyms_df


__all__ = [
    "import_school_report_from_excel",
    "import_school_crosswalk_from_excel",
    "get_school_reference_frames",
]

"""مخزن کش استخر منتورها با پشتیبانی SQLite.

Excel Inspactor تنها یک‌بار خوانده و با قواعد Policy نرمال می‌شود؛ نسخهٔ تمیز
در جدول ``mentor_pool_cache`` نگه‌داری می‌شود تا اجرای بعدی از SQLite خوانده شود.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any, Final

import pandas as pd

from app.core.build_matrix import (
    COL_GENDER,
    COL_GROUP,
    COL_MANAGER_NAME,
    COL_MENTOR_ID,
    COL_SCHOOL1,
    COL_SCHOOL2,
    COL_SCHOOL3,
    COL_SCHOOL4,
    COL_STATUS_A,
    COL_STATUS_B,
    BuildConfig,
    _as_domain_config,
    build_school_maps,
    collect_school_codes_from_row,
    domain_center_from_manager,
    expand_group_token,
    norm_gender,
    norm_status,
    prepare_crosswalk_mappings,
)
from app.core.canonical_frames import canonicalize_headers, canonicalize_pool_frame
from app.core.common.domain import _coerce_finance, _num_to_int_safe
from app.core.common.errors import InvalidCenterMappingError
from app.core.common.normalization import normalize_fa
from app.core.policy_loader import PolicyConfig
from app.infra.errors import DatabaseOperationError
from app.infra.io_utils import read_inspactor_workbook
from app.infra.local_database import LocalDatabase, _coerce_int_columns
from app.infra.references.schools import get_school_reference_frames


def import_mentor_pool_from_excel(
    path: Path,
    *,
    db: LocalDatabase,
    policy: PolicyConfig,
    pool_source: str = "inspactor",
) -> pd.DataFrame:
    """وارد کردن استخر منتورها از Inspactor و ذخیره در کش.

    این ورودی خام تنها شامل ستون‌های Inspactor/School است. این تابع ابتدا
    کلیدهای الحاقی شش‌تایی سیاست را مشتق کرده و QA ناشی از مپینگ‌های نامعتبر
    (گروه/مرکز/مالی/مدرسه) را روی خروجی نرمال‌شده نگه می‌دارد تا اپراتور
    بتواند هشدارها را در کش یا لاگ مشاهده کند.
    """

    raw_df = read_inspactor_workbook(path)
    raw_employee = None
    if "کد کارمندی پشتیبان" in raw_df.columns:
        candidate = raw_df.loc[:, "کد کارمندی پشتیبان"]
        if isinstance(candidate, pd.DataFrame):
            raw_employee = candidate.iloc[:, -1].copy()
        else:
            raw_employee = candidate.copy()
    else:
        raw_headers = canonicalize_headers(raw_df, header_mode="fa")
        if "کد کارمندی پشتیبان" in raw_headers.columns:
            candidate = raw_headers.loc[:, "کد کارمندی پشتیبان"]
            if isinstance(candidate, pd.DataFrame):
                candidate = candidate.iloc[:, 0]
            raw_employee = candidate.copy()

    derived, qa_issues = _derive_pool_join_keys(raw_df, db=db, policy=policy)
    if isinstance(raw_employee, pd.DataFrame):
        raw_employee = raw_employee.iloc[:, 0]
    if raw_employee is not None:
        derived["کد کارمندی پشتیبان (خام)"] = raw_employee.reindex(derived.index)
    normalized = canonicalize_pool_frame(
        derived,
        policy=policy,
        sanitize_pool=False,
        pool_source=pool_source,
    )
    normalized.attrs[_POOL_JOIN_KEY_QA_ATTR] = qa_issues
    _raise_on_duplicate_mentor_ids(
        normalized,
        policy=policy,
        pool_source=pool_source,
    )
    db.upsert_mentor_pool_cache(normalized, join_keys=policy.join_keys)
    return normalized


def load_mentor_pool_from_cache(*, db: LocalDatabase, policy: PolicyConfig) -> pd.DataFrame:
    """بازیابی استخر منتورها از کش SQLite."""

    cached = db.load_mentor_pool_cache(join_keys=policy.join_keys)
    _raise_on_duplicate_mentor_ids(cached, policy=policy, pool_source="cache")
    return _coerce_int_columns(cached, policy.join_keys)


__all__ = [
    "import_mentor_pool_from_excel",
    "load_mentor_pool_from_cache",
    "_POOL_JOIN_KEY_QA_ATTR",
    "_raise_on_duplicate_mentor_ids",
]


def _derive_pool_join_keys(
    pool_df: pd.DataFrame,
    *,
    db: LocalDatabase,
    policy: PolicyConfig,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """استخراج کلیدهای join شش‌تایی از ورودی Inspactor بر اساس مرجع مدرسه و Crosswalk.

    ورودی خام ستون‌های الهام‌گرفته از Inspactor/School دارد (مثل «گروه آزمایشی»،
    نام/کد مرکز، کد یا نام مدرسه). این تابع:
    - هر شش کلید الحاقی سیاست (`کدرشته`، `جنسیت`، `دانش آموز فارغ`،
      `مرکز گلستان صدرا`، `مالی حکمت بنیاد`، `کد مدرسه`) را مشتق و به نوع int
      تبدیل می‌کند.
    - برای مپینگ‌های ناموفق یا مبهم QA issue می‌سازد؛ reason code های فعلی شامل
      UNKNOWN_CENTER، CENTER_FALLBACK_WILDCARD، FINANCE_UNKNOWN، MISSING_GROUP_CODE،
      INVALID_GENDER، DEFAULT_GRADUATION_STATUS، SCHOOL_NOT_FOUND هستند.
    - نتیجه را به‌صورت (DataFrame نرمال‌شده، لیست QA) بازمی‌گرداند تا Infra بتواند
      هشدارها را در کش/لاگ نگه دارد بدون تغییر منطق Core.
    """

    if pool_df is None:
        return pool_df, []

    cfg = BuildConfig(policy=policy)
    domain_cfg = _as_domain_config(cfg)

    pool = canonicalize_headers(pool_df, header_mode="fa").copy()
    if all(join_key in pool.columns for join_key in policy.join_keys):
        coerced = _coerce_int_columns(pool, policy.join_keys)
        coerced.attrs[_POOL_JOIN_KEY_QA_ATTR] = []
        return coerced, []

    schools_df, crosswalk_groups_df, crosswalk_synonyms_df = get_school_reference_frames(db)
    if crosswalk_groups_df is None:
        raise ValueError("Crosswalk schools/groups data is required for mentor pool normalization")
    if schools_df is None:
        raise ValueError("School reference data is required for mentor pool normalization")

    name_to_code, code_to_name, buckets, synonyms = prepare_crosswalk_mappings(
        canonicalize_headers(crosswalk_groups_df, header_mode="fa"),
        crosswalk_synonyms_df,
    )
    code_to_name_school, school_name_to_code = build_school_maps(
        canonicalize_headers(schools_df, header_mode="fa"), cfg=cfg
    )

    group_key = policy.stage_column("group")
    gender_key = policy.stage_column("gender")
    grad_key = policy.stage_column("graduation_status")
    center_key = policy.stage_column("center")
    finance_key = policy.stage_column("finance")
    school_key = policy.stage_column("school")

    school_cols = [
        col for col in (COL_SCHOOL1, COL_SCHOOL2, COL_SCHOOL3, COL_SCHOOL4) if col in pool.columns
    ]
    derived: dict[str, list[int]] = {
        group_key: [],
        gender_key: [],
        grad_key: [],
        center_key: [],
        finance_key: [],
        school_key: [],
    }
    qa_issues: list[dict[str, Any]] = []

    center_map_norm = domain_cfg.center_map_norm()
    wildcard_center = center_map_norm.get("*")

    for idx, row in pool.iterrows():
        manager_name = str(row.get(COL_MANAGER_NAME, ""))
        group_tokens = expand_group_token(
            str(row.get(COL_GROUP, "")),
            name_to_code,
            code_to_name,
            buckets,
            synonyms,
        )
        group_code = int(group_tokens[0][1]) if group_tokens else 0
        if group_code == 0:
            _append_issue(
                qa_issues,
                reason="MISSING_GROUP_CODE",
                column=COL_GROUP,
                raw_value=row.get(COL_GROUP, ""),
                row_index=idx,
                mentor_id=row.get(COL_MENTOR_ID, ""),
            )

        gender_code = norm_gender(row.get(COL_GENDER))
        if gender_code is None:
            _append_issue(
                qa_issues,
                reason="INVALID_GENDER",
                column=COL_GENDER,
                raw_value=row.get(COL_GENDER),
                row_index=idx,
                mentor_id=row.get(COL_MENTOR_ID, ""),
            )

        status_code = norm_status(row.get(COL_STATUS_B) or row.get(COL_STATUS_A))
        if status_code is None:
            _append_issue(
                qa_issues,
                reason="DEFAULT_GRADUATION_STATUS",
                column=COL_STATUS_B,
                raw_value=row.get(COL_STATUS_B) or row.get(COL_STATUS_A),
                row_index=idx,
                mentor_id=row.get(COL_MENTOR_ID, ""),
            )

        school_binding = collect_school_codes_from_row(
            row,
            school_name_to_code,
            school_cols,
            domain_cfg=domain_cfg,
            binding_policy=policy.mentor_school_binding,
        )
        school_code = int(school_binding.codes[0]) if school_binding.codes else 0
        if school_binding.has_school_constraint and not school_binding.codes:
            _append_issue(
                qa_issues,
                reason="SCHOOL_NOT_FOUND",
                column=school_cols[0] if school_cols else COL_SCHOOL1,
                raw_value=_first_non_empty(row, school_cols),
                row_index=idx,
                mentor_id=row.get(COL_MENTOR_ID, ""),
            )

        try:
            center_value = domain_center_from_manager(manager_name, cfg=domain_cfg)
        except InvalidCenterMappingError:
            center_value = 0
            _append_issue(
                qa_issues,
                reason="UNKNOWN_CENTER",
                column=COL_MANAGER_NAME,
                raw_value=manager_name,
                row_index=idx,
                mentor_id=row.get(COL_MENTOR_ID, ""),
            )
        else:
            normalized_manager = normalize_fa(manager_name)
            center_known = False
            if normalized_manager and normalized_manager in center_map_norm:
                center_known = True
            else:
                for key, val in center_map_norm.items():
                    if key not in ("*",) and key and key in normalized_manager:
                        center_known = True
                        break
            if not center_known and wildcard_center is not None and center_value == wildcard_center:
                _append_issue(
                    qa_issues,
                    reason="CENTER_FALLBACK_WILDCARD",
                    column=COL_MANAGER_NAME,
                    raw_value=manager_name,
                    row_index=idx,
                    mentor_id=row.get(COL_MENTOR_ID, ""),
                )

        finance_value = row.get(finance_key, row.get("مالی حکمت بنیاد", 0))
        try:
            finance_normalized = int(_coerce_finance(finance_value, cfg=cfg))
        except Exception:
            finance_normalized = 0
            _append_issue(
                qa_issues,
                reason="FINANCE_UNKNOWN",
                column=finance_key,
                raw_value=finance_value,
                row_index=idx,
                mentor_id=row.get(COL_MENTOR_ID, ""),
            )
        else:
            finance_raw_int = _num_to_int_safe(finance_value)
            if (
                finance_value not in (None, "", 0, "0")
                and finance_raw_int not in cfg.finance_variants
            ):
                _append_issue(
                    qa_issues,
                    reason="FINANCE_UNKNOWN",
                    column=finance_key,
                    raw_value=finance_value,
                    row_index=idx,
                    mentor_id=row.get(COL_MENTOR_ID, ""),
                )

        derived[group_key].append(group_code)
        derived[gender_key].append(int(gender_code) if gender_code is not None else 0)
        derived[grad_key].append(
            int(status_code) if status_code is not None else int(cfg.default_status)
        )
        derived[center_key].append(center_value)
        derived[finance_key].append(finance_normalized)
        derived[school_key].append(int(school_code))

    enriched = pool.assign(**derived)
    enriched = _coerce_int_columns(enriched, policy.join_keys)
    enriched.attrs[_POOL_JOIN_KEY_QA_ATTR] = qa_issues
    return enriched, qa_issues


_POOL_JOIN_KEY_QA_ATTR: Final[str] = "pool_join_key_derivation_issues"


def _raise_on_duplicate_mentor_ids(
    pool: pd.DataFrame, *, policy: PolicyConfig, pool_source: str
) -> None:
    """ولیدیت یکتایی کلید ترکیبی «mentor_id + ۶ کلید اتصال» با پیام خوانا.

    این بررسی اجازه می‌دهد یک mentor_id در چند ترکیب کلید شش‌تایی تکرار شود،
    اما در صورت وجود دو ردیف یکسان روی کلید ترکیبی، خطای دترمینیستیک
    ``DatabaseOperationError`` با نمونهٔ ردیف‌های متضاد تولید می‌کند تا اپراتور
    بتواند ورودی Inspactor یا کش را اصلاح کند.

    Args:
        pool: دیتافریم کاننیکال استخر منتورها.
        policy: پیکربندی سیاست برای دسترسی به کلیدهای الحاقی (شش‌تایی).
        pool_source: منبع داده (inspactor/matrix/cache) جهت درج در پیام خطا.

    Raises:
        DatabaseOperationError: در صورت وجود ردیف تکراری روی کلید ترکیبی
            ``mentor_id`` به‌همراه ۶ کلید اتصال.

    مثال::

        >>> from app.core.policy_loader import load_policy
        >>> policy = load_policy()  # doctest: +SKIP
        >>> df = pd.DataFrame({
        ...     "mentor_id": ["m1", "m1"],
        ...     "کد کارمندی پشتیبان": ["E1", "E1"],
        ...     "کدرشته": [1201, 1201],
        ...     "جنسیت": [1, 1],
        ...     "دانش آموز فارغ": [0, 0],
        ...     "مرکز گلستان صدرا": [1, 1],
        ...     "مالی حکمت بنیاد": [0, 0],
        ...     "کد مدرسه": [3581, 3581],
        ... })
        >>> _raise_on_duplicate_mentor_ids(df, policy=policy, pool_source="inspactor")
        Traceback (most recent call last):
            ...
        DatabaseOperationError: استخر «inspactor» دارای ردیف تکراری بر اساس کلید ترکیبی mentor_id و کلیدهای اتصال است؛ نمونه‌ها: [{'mentor_id': 'm1', 'کدرشته': 1201, 'جنسیت': 1, 'دانش آموز فارغ': 0, 'مرکز گلستان صدرا': 1, 'مالی حکمت بنیاد': 0, 'کد مدرسه': 3581}]; نمونهٔ ردیف‌ها: [{'mentor_id': 'm1', 'کد کارمندی پشتیبان': 'E1', 'کدرشته': 1201, 'جنسیت': 1, 'دانش آموز فارغ': 0, 'مرکز گلستان صدرا': 1, 'مالی حکمت بنیاد': 0, 'کد مدرسه': 3581}]
    """

    if pool is None or "mentor_id" not in pool.columns:
        return
    key_columns = ["mentor_id", *policy.join_keys]
    if not all(col in pool.columns for col in key_columns):
        return

    trimmed = pool.copy()
    trimmed["mentor_id"] = trimmed["mentor_id"].astype("string").str.strip()
    non_null_mask = ~trimmed[key_columns].isna().any(axis=1)
    if not bool(non_null_mask.any()):
        return

    duplicate_mask = trimmed.loc[non_null_mask].duplicated(subset=key_columns, keep=False)
    if not bool(duplicate_mask.any()):
        return

    duplicate_rows = (
        trimmed.loc[non_null_mask & duplicate_mask, key_columns]
        .drop_duplicates()
        .head(5)
        .fillna("")
        .to_dict(orient="records")
    )
    raw_employee_col = (
        "کد کارمندی پشتیبان (خام)" if "کد کارمندی پشتیبان (خام)" in trimmed.columns else None
    )
    employee_col = raw_employee_col or "کد کارمندی پشتیبان"
    sample_columns = ["mentor_id", employee_col, *policy.join_keys]
    sample_rows = (
        trimmed.loc[non_null_mask & duplicate_mask, sample_columns]
        .head(5)
        .fillna("")
        .to_dict(orient="records")
    )

    message = (
        f"استخر «{pool_source}» دارای ردیف تکراری بر اساس کلید ترکیبی mentor_id و "
        f"کلیدهای اتصال است؛ نمونه‌ها: {duplicate_rows}; نمونهٔ ردیف‌ها: {sample_rows}"
    )
    raise DatabaseOperationError(message)


def _append_issue(
    collector: list[dict[str, Any]],
    *,
    reason: str,
    column: str,
    raw_value: Any,
    row_index: int,
    mentor_id: Any,
) -> None:
    """افزودن رکورد QA برای سطرهای دارای مپینگ نامعتبر یا ناکامل."""

    collector.append(
        {
            "row_index": int(row_index),
            "mentor_id": str(mentor_id) if mentor_id is not None else "",
            "reason": reason,
            "column": column,
            "raw_value": raw_value,
        }
    )


def _first_non_empty(row: pd.Series, cols: Iterable[str]) -> Any:
    """یافتن نخستین مقدار غیرتهی در ستون‌های مدرسه برای گزارش QA."""

    for col in cols:
        val = row.get(col)
        if val not in (None, "", 0, "0"):
            return val
    return None

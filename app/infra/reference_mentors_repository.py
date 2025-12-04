"""مخزن کش استخر منتورها با پشتیبانی SQLite.

Excel Inspactor تنها یک‌بار خوانده و با قواعد Policy نرمال می‌شود؛ نسخهٔ تمیز
در جدول ``mentor_pool_cache`` نگه‌داری می‌شود تا اجرای بعدی از SQLite خوانده شود.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any, Final

import pandas as pd
from pandas._libs.missing import NAType

from app.core.build_matrix import (  # type: ignore[attr-defined]
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
    build_school_maps,
    collect_school_codes_from_row,
    domain_center_from_manager,
    norm_gender,
    norm_status,
)
from app.core.canonical_frames import (  # type: ignore[attr-defined]
    POOL_JOIN_KEY_DUPLICATES_ATTR,
    canonicalize_headers,
    canonicalize_pool_frame,
)
from app.core.common.domain import _coerce_finance, _num_to_int_safe
from app.core.common.errors import InvalidCenterMappingError
from app.core.common.join_keys import (
    VALID_GROUP_CODES,
    parse_group_codes,
    validate_and_canonicalize_join_keys,
)
from app.core.common.normalization import normalize_fa
from app.core.common.types import JoinKeyValidationResult
from app.core.policy_loader import PolicyConfig
from app.infra.errors import JoinKeyValidationError
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
    # حذف ردیف‌های کاملاً تکراری تنها زمانی که ستون mentor_id در ورودی
    # موجود نیست (فرمت خام Inspactor). برای ورودی‌های دارای mentor_id،
    # تکرار روی کلیدهای ترکیبی باید منجر به خطای QA شود و نباید با
    # dedupe پنهان گردد.
    mentor_columns = [
        col
        for col in raw_df.columns
        if col.strip().lower() == "mentor_id" or str(col).strip() == COL_MENTOR_ID
    ]
    mentor_id_present = False
    for col in mentor_columns:
        candidate = raw_df[col]
        series = candidate.iloc[:, -1] if isinstance(candidate, pd.DataFrame) else candidate
        series = series.astype("string").str.strip()
        if not series.eq("").all():
            mentor_id_present = True
            break
    if not mentor_id_present:
        raw_df = raw_df.drop_duplicates(keep="first")
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
    validation = validate_and_canonicalize_join_keys(derived, policy=policy, entity_type="mentor")
    if validation.issues:
        raise JoinKeyValidationError(validation)
    derived = validation.canonical_df
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
    existing_duplicates = normalized.attrs.get(POOL_JOIN_KEY_DUPLICATES_ATTR)
    if not isinstance(existing_duplicates, pd.DataFrame) or existing_duplicates.empty:
        normalized.attrs[POOL_JOIN_KEY_DUPLICATES_ATTR] = _detect_duplicate_mentor_join_profiles(
            normalized, policy=policy, pool_source=pool_source
        )
    cache_payload = normalized
    if isinstance(existing_duplicates, pd.DataFrame) and not existing_duplicates.empty:
        cache_payload = normalized.drop_duplicates(
            subset=["mentor_id", *policy.join_keys], keep="first"
        ).copy()
        cache_payload.attrs.update(normalized.attrs)
    db.upsert_mentor_pool_cache(cache_payload, join_keys=policy.join_keys)
    return cache_payload


def import_mentor_pool_with_validation(
    path: Path,
    *,
    db: LocalDatabase,
    policy: PolicyConfig,
    pool_source: str = "inspactor",
) -> JoinKeyValidationResult:
    """Wrapper exposing join-key validation result for mentor pool import."""

    try:
        normalized = import_mentor_pool_from_excel(
            path, db=db, policy=policy, pool_source=pool_source
        )
    except JoinKeyValidationError as exc:
        return exc.result
    return JoinKeyValidationResult(canonical_df=normalized, issues=[])


def load_mentor_pool_from_cache(*, db: LocalDatabase, policy: PolicyConfig) -> pd.DataFrame:
    """بازیابی استخر منتورها از کش SQLite."""

    cached = db.load_mentor_pool_cache(join_keys=policy.join_keys)
    duplicates = _detect_duplicate_mentor_join_profiles(cached, policy=policy, pool_source="cache")
    cached.attrs[POOL_JOIN_KEY_DUPLICATES_ATTR] = duplicates
    return _coerce_int_columns(cached, policy.join_keys)


__all__ = [
    "import_mentor_pool_from_excel",
    "load_mentor_pool_from_cache",
    "_POOL_JOIN_KEY_QA_ATTR",
    "_detect_duplicate_mentor_join_profiles",
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
      UNKNOWN_CENTER، CENTER_FALLBACK_WILDCARD، FINANCE_UNKNOWN، INVALID_GROUP_CODE،
      INVALID_GENDER، DEFAULT_GRADUATION_STATUS، SCHOOL_NOT_FOUND هستند.
    - نتیجه را به‌صورت (DataFrame نرمال‌شده، لیست QA) بازمی‌گرداند تا Infra بتواند
      هشدارها را در کش/لاگ نگه دارد بدون تغییر منطق Core.
    """

    if pool_df is None:
        return pool_df, []

    cfg = BuildConfig(policy=policy)

    pool = canonicalize_headers(pool_df, header_mode="fa").copy()
    if all(join_key in pool.columns for join_key in policy.join_keys):
        coerced = _coerce_int_columns(pool, policy.join_keys)
        coerced.attrs[_POOL_JOIN_KEY_QA_ATTR] = []
        return coerced, []

    schools_df, crosswalk_groups_df, _ = get_school_reference_frames(db)
    if crosswalk_groups_df is None:
        raise ValueError("Crosswalk schools/groups data is required for mentor pool normalization")
    if schools_df is None:
        raise ValueError("School reference data is required for mentor pool normalization")
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
    derived: dict[str, list[int | NAType]] = {
        group_key: [],
        gender_key: [],
        grad_key: [],
        center_key: [],
        finance_key: [],
        school_key: [],
    }
    qa_issues: list[dict[str, Any]] = []

    center_map_norm = cfg.center_map_norm()
    wildcard_center = center_map_norm.get("*")

    for idx, row in pool.iterrows():
        manager_name = str(row.get(COL_MANAGER_NAME, ""))
        invalid_group_tokens: list[int] = []
        group_codes = parse_group_codes(
            row.get(COL_GROUP, ""),
            valid_codes=VALID_GROUP_CODES,
            invalid_collector=invalid_group_tokens,
        )
        group_code: int | NAType = pd.NA if not group_codes else int(group_codes[0])
        if not group_codes:
            _append_issue(
                qa_issues,
                reason="INVALID_GROUP_CODE",
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
            cfg=cfg,
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
            center_value = domain_center_from_manager(manager_name, cfg=cfg)
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
            finance_variants = cfg.finance_variants or ()
            if finance_value not in (None, "", 0, "0") and finance_raw_int not in finance_variants:
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


def _detect_duplicate_mentor_join_profiles(
    pool: pd.DataFrame, *, policy: PolicyConfig, pool_source: str
) -> pd.DataFrame:
    """گزارش تکرار کامل «mentor_id + ۶ کلید اتصال» بدون توقف اجرا.

    این تابع تنها ردیف‌های کاملاً یکسان (کلید هفت‌تایی) را برمی‌گرداند تا در QA
    نمایش داده شوند. ساختار join-key (حضور ستون‌ها و نوع int) باید پیش‌تر در
    Core تضمین شده باشد؛ در غیر این صورت دیتافریم تهی برمی‌گردد.
    """

    if pool is None or "mentor_id" not in pool.columns:
        return pd.DataFrame(columns=[*policy.join_keys, "mentor_id", "duplicate_group_size"])
    key_columns = ["mentor_id", *policy.join_keys]
    if not all(col in pool.columns for col in key_columns):
        return pd.DataFrame(columns=[*policy.join_keys, "mentor_id", "duplicate_group_size"])

    trimmed = pool.loc[:, key_columns].copy()
    trimmed["mentor_id"] = trimmed["mentor_id"].astype("string").str.strip()
    numeric_cols = [col for col in policy.join_keys if col in trimmed.columns]
    for column in numeric_cols:
        trimmed[column] = pd.to_numeric(trimmed[column], errors="coerce").astype("Int64")

    non_null_mask = ~trimmed[key_columns].isna().any(axis=1)
    if not bool(non_null_mask.any()):
        return pd.DataFrame(columns=[*policy.join_keys, "mentor_id", "duplicate_group_size"])

    duplicate_mask = trimmed.loc[non_null_mask].duplicated(subset=key_columns, keep=False)
    if not bool(duplicate_mask.any()):
        return pd.DataFrame(columns=[*policy.join_keys, "mentor_id", "duplicate_group_size"])

    duplicate_rows = trimmed.loc[non_null_mask & duplicate_mask, key_columns].copy()
    duplicate_rows["duplicate_group_size"] = (
        duplicate_rows.groupby(key_columns, sort=False)["mentor_id"]
        .transform("size")
        .astype("Int64")
    )
    numeric_index = pd.to_numeric(duplicate_rows.index, errors="coerce")
    duplicate_rows["pool_row_index"] = numeric_index.astype("Int64")
    duplicate_rows["pool_source"] = pool_source
    sort_columns = key_columns + ["pool_row_index"]
    return duplicate_rows.sort_values(sort_columns, kind="stable").reset_index(drop=True)


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

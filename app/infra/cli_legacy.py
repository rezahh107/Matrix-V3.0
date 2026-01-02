"""رابط خط فرمان headless برای ماتریس و تخصیص مطابق Policy.

این ماژول کلیهٔ مسئولیت‌های I/O را بر عهده دارد و با تزریق progress به
توابع Core، اصل Policy-First و جداسازی لایه‌ها را حفظ می‌کند.

مثال::

    >>> from app.infra import cli
    >>> cli.main(["build-matrix", "--inspactor", "insp.xlsx", "--schools", "sch.xlsx",
    ...           "--crosswalk", "cross.xlsx", "--output", "out.xlsx", "--policy",
    ...           "config/policy.json"])  # doctest: +SKIP
"""

# Program boundaries:
# - Pool Builder commands (build-matrix, import-mentors) may consume Inspactor workbooks
#   to construct mentor pools.
# - Allocation/QA commands (allocate, preflight-unknowns, rule-engine) are matrix-only
#   and must never fall back to Inspactor sheets.

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import platform
import sys
from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, NoReturn, cast
from uuid import uuid4

import pandas as pd
from pandas import testing as pd_testing
from pandas.api import types as pd_types

import app.core.allocation.mentor_pool as mentor_pool
import app.core.build_matrix as build_matrix_module
import app.core.common.columns as columns_module
from app.core.allocate_students import (
    TraceDebugFrames,
    allocate_batch,
    build_selection_reason_rows,
)
from app.core.allocation.engine import enrich_summary_with_history
from app.core.allocation.history_metrics import METRIC_COLUMNS, compute_history_metrics
from app.core.canonical_frames import canonicalize_allocation_frames, canonicalize_pool_frame
from app.core.common.isin_guard import isin_mask
from app.core.common.join_keys import JoinKeyCanonicalizationError
from app.core.common.join_resolver import JoinKeyResolver
from app.core.common.payloads import json_safe_value
from app.core.common.types import JoinKeyValidationIssue, JoinKeyValidationResult
from app.core.common.unknown_data_channel import (
    UnknownDataChannel,
    UnknownIssue,
    validate_join_key_columns_numeric,
    validate_pool_join_keys,
)
from app.core.counter import (
    assert_unique_student_ids,
    assign_counters,
    build_registration_id,
    find_duplicate_student_id_groups,
    infer_year_strict,
    pick_counter_sheet_name,
    year_to_yy,
)
from app.core.debug_pool_alignment import analyze_pool_alignment_batch
from app.core.inspactor_schema_helper import (
    InspactorDefaultConfig,
    with_default_inspactor_columns,
)
from app.core.policy_loader import MentorStatus, PolicyConfig, load_policy
from app.core.qa.invariants import QaReport, run_all_invariants
from app.infra import history_store, pool_loader
from app.infra.audit_allocations import audit_allocations, summarize_report
from app.infra.config_flags import (
    UserSettings,
    coerce_user_settings,
    load_user_settings,
)
from app.infra.console import safe_print
from app.infra.errors import (
    DatabaseCorruptError,
    DatabasePreparationError,
    DatabaseSchemaMismatchError,
    JoinKeyValidationError,
    ReferenceDataMissingError,
    SchemaVersionMismatchError,
)
from app.infra.excel.export_allocations import (
    DEFAULT_SABT_PROFILE_PATH,
    build_sabt_export_frame,
    collect_trace_debug_sheets,
    load_sabt_export_profile,
)
from app.infra.excel.export_qa_validation import (
    QaValidationContext,
    export_qa_validation,
)
from app.infra.excel.import_to_sabt import (
    apply_alias_rule,
    build_errors_frame,
    build_optional_sheet_frame,
    build_sheet2_frame,
    build_summary_frame,
    load_exporter_config,
    prepare_allocation_export_frame,
    write_import_to_sabt_excel,
)
from app.infra.excel.qa_export import (
    build_join_key_audit_sheet,
    build_join_key_summary_sheet,
)
from app.infra.excel_writer import write_selection_reasons_sheet
from app.infra.exporter_archive_repository import (
    ExporterArchiveConfig,
    ExporterArchiveRepository,
)
from app.infra.forms_repository import FormsRepository, WordPressFormsClient
from app.infra.groupcode.groupcode_repository import GroupCodeRepository
from app.infra.io_utils import (
    ALT_CODE_COLUMN,
    read_excel_first_sheet,
    write_json_report,
    write_xlsx_atomic,
)
from app.infra.local_database import LocalDatabase
from app.infra.logging import structured_event
from app.infra.mentors.field_registry import FieldRegistry
from app.infra.mentors.header_resolver import HeaderResolver
from app.infra.mentors.value_canonicalizer import ValueCanonicalizer
from app.infra.qa.alloc_join_validation import validate_allocation_join_keys_with_wildcard
from app.infra.reference_managers_repository import import_managers_from_excel
from app.infra.reference_mentors_repository import (
    _POOL_PIPELINE_TRACE_ATTR,
    import_mentor_pool_from_dataframe,
    import_mentor_pool_from_excel,
    load_mentor_pool_from_cache,
)
from app.infra.reference_schools_repository import (
    get_school_reference_frames,
    import_school_crosswalk_from_excel,
    import_school_report_from_excel,
)
from app.infra.reference_students_repository import (
    import_student_report_from_excel,
    load_students_from_cache,
)
from app.infra.students.pipeline_v3 import StudentPipelineV3
from app.infra.validators.join_keys import (
    JoinKeyAuditResult,
    validate_allocation_join_keys,  # noqa: F401
)

if TYPE_CHECKING:
    from app.core.common.domain import BuildConfig
    from app.core.common.types import HeaderMode
    from app.core.policy_loader import MentorPoolGovernanceConfig
else:
    MentorPoolGovernanceConfig = mentor_pool.MentorPoolGovernanceConfig
    BuildConfig = build_matrix_module.BuildConfig
    HeaderMode = columns_module.HeaderMode

apply_manager_mentor_governance = mentor_pool.apply_manager_mentor_governance
apply_mentor_pool_governance = mentor_pool.apply_mentor_pool_governance
build_matrix = build_matrix_module.build_matrix
CANON_EN_TO_FA = columns_module.CANON_EN_TO_FA
canonicalize_headers = columns_module.canonicalize_headers
enrich_school_columns_en = columns_module.enrich_school_columns_en

ProgressFn = Callable[[int, str], None]

_DEFAULT_POLICY_PATH = Path("config/policy.json")
_DEFAULT_EXPORTER_CONFIG_PATH = Path("config/SmartAlloc_Exporter_Config_v1.json")
_DEFAULT_SABT_TEMPLATE_PATH = Path("templates/ImportToSabt (1404) - Copy.xlsx")
_DEFAULT_ALLOC_PROFILE_PATH = DEFAULT_SABT_PROFILE_PATH
_DEFAULT_LOCAL_DB_PATH = Path("smart_alloc.db")

logger = logging.getLogger(__name__)


def build_matrix_v3(
    insp_df: pd.DataFrame,
    schools_df: pd.DataFrame,
    crosswalk_groups_df: pd.DataFrame,
    *,
    crosswalk_synonyms_df: pd.DataFrame | None = None,
    cfg: BuildConfig,
    progress: ProgressFn,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    """Build matrix using HeaderPipelineV3 for mentor header/value canonicalization."""

    registry = FieldRegistry(cfg.policy)
    resolver = HeaderResolver(registry, header_mode=cfg.policy.excel.header_mode_internal)
    header_result = resolver.resolve(insp_df)
    if not header_result.can_continue:
        error = ValueError("mentor header resolution failed")
        setattr(error, "header_issues", header_result.issues)
        raise error

    canonicalizer = ValueCanonicalizer(registry)
    value_result = canonicalizer.canonicalize(header_result.resolved_df)
    if not value_result.can_continue:
        error = ValueError("mentor value canonicalization failed")
        setattr(error, "value_issues", value_result.issues)
        raise error

    canonical_insp = value_result.canonical_df.rename(
        columns={
            "mentor_id": build_matrix_module.COL_MENTOR_ID,
            "capacity_current": build_matrix_module.CAPACITY_CURRENT_COL,
            "capacity_special": build_matrix_module.CAPACITY_SPECIAL_COL,
            "schools_covered_count": build_matrix_module.COL_SCHOOL_COUNT,
        },
        errors="ignore",
    )
    default_cfg = InspactorDefaultConfig(
        school_code_columns=(
            build_matrix_module.COL_SCHOOL_CODE,
            *registry.school_binding_fields,
        ),
        school_count_column=build_matrix_module.COL_SCHOOL_COUNT,
        derived_factories={
            build_matrix_module.COL_POSTAL: lambda frame: pd.Series(
                [pd.NA] * len(frame), index=frame.index, dtype="string"
            ),
            build_matrix_module.CAPACITY_CURRENT_COL: lambda frame: pd.Series(
                [0] * len(frame), index=frame.index, dtype="Int64"
            ),
            build_matrix_module.CAPACITY_SPECIAL_COL: lambda frame: pd.Series(
                [0] * len(frame), index=frame.index, dtype="Int64"
            ),
        },
    )
    canonical_insp = with_default_inspactor_columns(canonical_insp, default_cfg)

    return build_matrix_module.build_matrix(
        canonical_insp,
        schools_df,
        crosswalk_groups_df,
        crosswalk_synonyms_df=crosswalk_synonyms_df,
        cfg=cfg,
        progress=progress,
        precanonicalized_inspactor=True,
    )


def _safe_row_index(raw: Hashable | None) -> int:
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        try:
            return int(raw)
        except ValueError:
            return 0
    return 0


class AllocationConsistencyError(ValueError):
    """Raised when allocation counters and produced outputs diverge."""


def _sync_counter_summary_with_allocations(
    *,
    counter_summary: Mapping[str, int],
    allocations_df: pd.DataFrame,
    students_df: pd.DataFrame,
    policy: PolicyConfig,
) -> dict[str, int]:
    """Align counter summary with actual allocations and genders.

    ``_inject_student_ids`` می‌تواند شمارنده‌ها را بر اساس ورودی روستر محاسبه
    کند، اما این تابع بعد از تخصیص فراخوانی می‌شود تا تعداد واقعی دانش‌آموزان
    تخصیص‌گرفته (به تفکیک جنسیت) در summary ثبت شود و از بروز ناسازگاری بین
    شمارنده‌ها و دیتافریم خروجی جلوگیری کند.
    """

    synced = dict(counter_summary)
    if allocations_df.empty:
        synced["new_male_count"] = 0
        synced["new_female_count"] = 0
        return synced

    alloc_en = canonicalize_headers(allocations_df, header_mode="en")
    students_en = canonicalize_headers(students_df, header_mode="en")
    gender_col = "gender"
    merged = alloc_en
    if "student_id" in alloc_en.columns and "student_id" in students_en.columns:
        student_gender = students_en.loc[:, ["student_id"]].copy()
        if gender_col in students_en.columns:
            student_gender[gender_col] = columns_module.ensure_series(students_en[gender_col])
        merged = alloc_en.merge(
            student_gender,
            on="student_id",
            how="left",
            validate="many_to_one",
        )

    male_value = int(policy.gender_codes.male.value)
    female_value = int(policy.gender_codes.female.value)
    genders = pd.to_numeric(merged.get(gender_col), errors="coerce")
    male_count = int((genders == male_value).sum())
    female_count = int((genders == female_value).sum())

    synced["new_male_count"] = male_count
    synced["new_female_count"] = female_count

    next_male_start = int(counter_summary.get("next_male_start", 1))
    next_female_start = int(counter_summary.get("next_female_start", 1))
    synced["next_male_start"] = max(next_male_start, male_count + 1)
    synced["next_female_start"] = max(next_female_start, female_count + 1)

    return synced


def _build_qa_meta(
    *,
    run_uuid: str,
    command_name: str,
    policy: PolicyConfig,
    capacity_column: str,
    output: Path,
    input_students_path: Path | None,
    input_pool_path: Path | None,
    started_at: datetime,
    completed_at: datetime | None,
    qa_report: QaReport | None,
    join_key_audit: pd.DataFrame | None,
    trace_df: pd.DataFrame | None,
    trace_summary_df: pd.DataFrame | None,
    history_info_df: pd.DataFrame | None,
    pool_detection: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Summarize QA and trace observability for logging and exports."""

    meta: dict[str, object] = {
        "run_uuid": run_uuid,
        "command": command_name,
        "policy_version": policy.version,
        "ssot_version": "1.0.2",
        "capacity_column": capacity_column,
        "output_path": str(output),
        "source_output": str(output),
    }
    if input_students_path:
        meta["input_students"] = str(input_students_path)
    if input_pool_path:
        meta["input_pool"] = str(input_pool_path)
    if pool_detection:
        meta["pool_detection"] = pool_detection

    meta["started_at"] = started_at.isoformat().replace("+00:00", "Z")
    if completed_at is not None:
        meta["completed_at"] = completed_at.isoformat().replace("+00:00", "Z")
        meta["duration_seconds"] = max(0.0, (completed_at - started_at).total_seconds())

    if qa_report is not None:
        total_rules = len(qa_report.results)
        failed_rules = sum(not result.passed for result in qa_report.results)
        meta["qa_rules_total"] = total_rules
        meta["qa_rules_failed"] = failed_rules
        meta["qa_passed"] = failed_rules == 0

    join_mismatches = 0
    if join_key_audit is not None and "any_mismatch" in join_key_audit.columns:
        join_mismatches = int(join_key_audit["any_mismatch"].fillna(False).sum())
    meta["join_mismatches"] = join_mismatches

    if trace_df is not None:
        meta["trace_rows"] = int(trace_df.shape[0])
    if isinstance(trace_summary_df, pd.DataFrame):
        meta["trace_summary_rows"] = int(trace_summary_df.shape[0])
    if history_info_df is not None:
        meta["history_info_rows"] = int(history_info_df.shape[0])

    return meta


def _coerce_header_mode(value: str | None) -> HeaderMode:
    """Validate and narrow header mode strings to the HeaderMode literal type.

    ``None`` یا رشتهٔ تهی به حالت پیش‌فرض «fa» نگاشت می‌شود تا سناریوهای
    Policy جعلی در تست‌ها بدون خطا عبور کنند.
    """

    if value is None:
        return "fa"
    normalized = str(value).strip()
    if not normalized:
        return "fa"
    if normalized not in {"fa", "en", "fa_en"}:
        raise ValueError(f"Invalid header_mode: {value}")
    return cast(HeaderMode, normalized)


def _normalize_student_id(series: pd.Series) -> pd.Series:
    """Return a trimmed string Series for student IDs."""

    return series.astype("string").str.strip()


def _student_id_missing_mask(series: pd.Series) -> pd.Series:
    """Identify empty, NA, or 'nan' student_id values in a normalized Series."""

    return series.eq("") | series.str.lower().eq("nan") | series.isna()


def _get_student_id_set_from_series(series: pd.Series) -> set[str]:
    ids = _normalize_student_id(series)
    ids = ids[~_student_id_missing_mask(ids)]
    return set(ids.tolist())


def _ensure_student_id_column_for_empty(frame: pd.DataFrame | None) -> pd.DataFrame:
    """Provide an empty ``student_id`` column when frame is empty or ``None``.

    This helper avoids positional attachment by only materializing a zero-length
    column for guard checks, keeping LAW/EXPORT-SSOT-ID-01 intact.
    """

    if frame is None:
        return pd.DataFrame(columns=["student_id"])
    if frame.empty and "student_id" not in frame.columns:
        return pd.DataFrame(columns=["student_id"], index=frame.index)
    return frame


def _build_students_spine(
    students_df: pd.DataFrame, *, header_mode: HeaderMode
) -> pd.DataFrame:
    """Create a canonical, validated student spine with stable ``student_id`` values."""

    students_en = canonicalize_headers(students_df, header_mode="en").copy()
    if "student_id" not in students_en.columns:
        raise AllocationConsistencyError(
            "ستون student_id در داده‌های دانش‌آموز یافت نشد؛ پیش از خروجی‌گیری باید شناسه تزریق شود."
        )

    students_en["student_id"] = _normalize_student_id(students_en["student_id"])
    missing_mask = _student_id_missing_mask(students_en["student_id"])
    if missing_mask.any():
        missing_rows = students_en.index[missing_mask].tolist()[:5]
        raise AllocationConsistencyError(
            "شناسهٔ دانش‌آموز (student_id) نباید خالی باشد؛ نمونه ردیف‌های ناقص: "
            f"{missing_rows}."
        )

    duplicates = students_en["student_id"].duplicated(keep=False)
    if duplicates.any():
        sample = students_en.loc[duplicates, "student_id"].unique().tolist()[:5]
        raise AllocationConsistencyError(
            "student_id باید یکتا باشد؛ نمونهٔ تکراری: " f"{sample}."
        )

    return canonicalize_headers(students_en, header_mode=header_mode)


def _get_success_log_rows(
    logs_df: pd.DataFrame, *, header_mode: HeaderMode = "en"
) -> pd.DataFrame:
    """Return successful log rows; if allocation_status is missing, return all rows."""

    logs_en = canonicalize_headers(logs_df, header_mode="en")
    status_series = logs_en.get("allocation_status")
    if status_series is None:
        success_rows = logs_en
    else:
        success_rows = logs_en.loc[status_series.astype("string").str.lower() == "success"]
    if header_mode == "en":
        return success_rows
    return canonicalize_headers(success_rows, header_mode=header_mode)


def _build_success_spine(
    logs_df: pd.DataFrame, *, students_spine: pd.DataFrame, header_mode: HeaderMode
) -> pd.DataFrame:
    """Filter ``students_spine`` down to successful students and validate size integrity."""

    success_rows = _get_success_log_rows(logs_df)

    if "student_id" not in success_rows.columns:
        raise AllocationConsistencyError("logs_df must include student_id for success spine.")

    success_set = _get_student_id_set_from_series(success_rows["student_id"])

    students_en = canonicalize_headers(students_spine, header_mode="en").copy()
    students_en["student_id"] = _normalize_student_id(students_en["student_id"])
    success_spine = students_en.loc[
        isin_mask(students_en["student_id"], success_set, name="success_set")
    ].copy()

    if len(success_spine) != len(success_set):
        missing = sorted(success_set - set(success_spine["student_id"].tolist()))[:5]
        raise AllocationConsistencyError(
            "ناسازگاری بین لاگ موفق و دادهٔ دانش‌آموز: student_idهایی در لاگ یافت شد که در دادهٔ اصلی نیستند; "
            f"نمونه={missing}."
        )

    sort_candidates = ["کد ثبت نام0", "student_id"]
    sort_column = next((col for col in sort_candidates if col in success_spine.columns), None)
    if sort_column is not None:
        success_spine = success_spine.sort_values(sort_column, kind="mergesort")

    return canonicalize_headers(success_spine, header_mode=header_mode)


def _build_allocations_view(
    allocations_df: pd.DataFrame,
    *,
    success_spine: pd.DataFrame,
    header_mode: HeaderMode,
) -> pd.DataFrame:
    """Align allocations to the success spine using key-based joins (student_id-only)."""

    alloc_en = canonicalize_headers(allocations_df, header_mode="en").copy()
    if "student_id" not in alloc_en.columns:
        raise AllocationConsistencyError(
            "LAW/EXPORT-SSOT-ID-01: allocations_df فاقد ستون student_id است و "
            "امکان هم‌ترازسازی وجود ندارد."
        )
    alloc_en["student_id"] = _normalize_student_id(alloc_en["student_id"])
    missing_mask = _student_id_missing_mask(alloc_en["student_id"])
    if missing_mask.any():
        sample_rows = alloc_en.index[missing_mask].tolist()[:5]
        raise AllocationConsistencyError(
            "LAW/EXPORT-SSOT-ID-01: allocations_df شامل student_id خالی/نامعتبر است؛ "
            f"نمونه ردیف‌ها={sample_rows}."
        )

    spine_en = canonicalize_headers(success_spine, header_mode="en").copy()
    spine_en["student_id"] = _normalize_student_id(spine_en["student_id"])

    merged = spine_en[["student_id"]].merge(
        alloc_en,
        on="student_id",
        how="left",
        validate="one_to_one",
    )

    if merged["student_id"].isna().any():
        raise AllocationConsistencyError("allocations_df missing student_id values after alignment.")

    return canonicalize_headers(merged, header_mode=header_mode)


def normalize_national_id(value: Any) -> str | None:
    """Normalize national_id for stable joins.

    - Coerce to string, strip whitespace.
    - Convert Persian/Arabic digits to English digits.
    - Remove non-digit characters.
    - Zero-pad to length 10 when possible; otherwise return ``None``.
    """

    if value is None:
        return None

    digit_map = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    normalized = str(value).strip().translate(digit_map)
    digits_only = "".join(ch for ch in normalized if ch.isdigit())
    if not digits_only:
        return None
    if len(digits_only) < 10:
        digits_only = digits_only.zfill(10)
    if len(digits_only) != 10:
        return None
    return digits_only


def assert_student_id_integrity(
    frame: pd.DataFrame,
    *,
    header_mode: HeaderMode,
    expect_unique: bool = True,
    students_df: pd.DataFrame | None = None,
    context: str | None = None,
) -> pd.DataFrame:
    """Validate that ``student_id`` is already present and canonical.

    This guard is intentionally **non-mutating** to enforce LAW/EXPORT-SSOT-ID-01
    and prevent any positional or repair-style attachment. It only validates:

    - presence of ``student_id`` (SSoT),
    - non-null / non-empty values after trimming,
    - optional uniqueness (default),
    - consistency with ``students_df`` when provided.
    """

    en_frame = canonicalize_headers(frame, header_mode="en").copy()
    rule_hint = "LAW/EXPORT-SSOT-ID-01"
    location = f" ({context})" if context else ""

    if "student_id" not in en_frame.columns:
        raise AllocationConsistencyError(
            f"{rule_hint}: ستون student_id در داده موجود نیست{location}."
        )

    normalized = _normalize_student_id(en_frame["student_id"])
    missing_mask = _student_id_missing_mask(normalized)
    if missing_mask.any():
        missing_rows = en_frame.index[missing_mask].tolist()[:5]
        sample_ids = normalized.loc[missing_mask].tolist()[:5]
        raise AllocationConsistencyError(
            f"{rule_hint}: student_id تهی/نامعتبر شناسایی شد{location}; "
            f"نمونه ردیف/مقدار = {list(zip(missing_rows, sample_ids))}."
        )

    if expect_unique:
        duplicates = normalized.duplicated(keep=False)
        if duplicates.any():
            sample = normalized.loc[duplicates].unique().tolist()[:5]
            raise AllocationConsistencyError(
                f"{rule_hint}: student_id باید یکتا باشد{location}; نمونه={sample}."
            )

    if students_df is not None:
        students_en = canonicalize_headers(students_df, header_mode="en").copy()
        if "student_id" not in students_en.columns:
            raise AllocationConsistencyError(
                f"{rule_hint}: students_df فاقد student_id است و نمی‌تواند SSoT باشد{location}."
            )
        reference = _normalize_student_id(students_en["student_id"])
        reference_set = _get_student_id_set_from_series(reference)
        frame_set = _get_student_id_set_from_series(normalized)
        if frame_set - reference_set:
            sample = sorted(frame_set - reference_set)[:5]
            raise AllocationConsistencyError(
                f"{rule_hint}: student_id خارج از محدودهٔ students_spine یافت شد{location}; نمونه={sample}."
            )

    return canonicalize_headers(en_frame, header_mode=header_mode)


def attach_student_id_column(
    frame: pd.DataFrame,
    student_ids: pd.Series | None = None,
    *,
    header_mode: HeaderMode,
    ensure_existing: bool = False,
    students_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Deprecated compatibility wrapper for legacy callers.

    The function now delegates to :func:`assert_student_id_integrity` and performs
    **no mutation**. Parameters are kept for backward compatibility only.
    """

    _ = student_ids, ensure_existing  # maintained for signature stability
    return assert_student_id_integrity(
        frame,
        header_mode=header_mode,
        expect_unique=True,
        students_df=students_df,
    )


_LAST_PROGRESS_PCT: int | None = None


def _default_progress(pct: int, message: str) -> None:
    """چاپ سادهٔ وضعیت پیشرفت در حالت headless."""
    global _LAST_PROGRESS_PCT
    pct_value = max(0, min(100, int(pct)))
    if _LAST_PROGRESS_PCT is not None and pct_value == _LAST_PROGRESS_PCT:
        return
    _LAST_PROGRESS_PCT = pct_value
    print(f"{pct_value:3d}% | {message}")


def _add_local_db_args(parser: argparse.ArgumentParser) -> None:
    """افزودن آرگومان‌های پایگاه دادهٔ محلی برای لاگ اجرا."""

    parser.add_argument(
        "--local-db",
        dest="local_db_path",
        default=str(_DEFAULT_LOCAL_DB_PATH),
        help="مسیر فایل SQLite جهت ثبت تاریخچهٔ اجرا",
    )
    parser.add_argument(
        "--disable-local-db",
        action="store_true",
        help="غیرفعال‌سازی ثبت تاریخچه در SQLite",
    )


def _add_exporter_archive_args(parser: argparse.ArgumentParser) -> None:
    """آرگومان‌های اختیاری بایگانی خروجی ImportToSabt."""

    parser.add_argument(
        "--archive-exporter",
        action="store_true",
        help="در صورت تولید فایل Sabt خروجی را در SQLite بایگانی کن",
    )
    parser.add_argument(
        "--archive-row-limit",
        type=int,
        default=500,
        help="حداکثر تعداد ردیفی که به‌صورت کامل در Snapshot ذخیره می‌شود",
    )


def _resolve_local_db(args: argparse.Namespace) -> LocalDatabase | None:
    """تولید LocalDatabase از آرگومان‌ها یا بازگشت None در صورت غیرفعال بودن."""

    overrides = getattr(args, "_ui_overrides", {}) or {}
    if bool(overrides.get("disable_local_db")) or getattr(args, "disable_local_db", False):
        return None
    path_text = (
        overrides.get("local_db_path")
        or getattr(args, "local_db_path", None)
        or str(_DEFAULT_LOCAL_DB_PATH)
    )
    try:
        return LocalDatabase(Path(path_text))
    except Exception:  # pragma: no cover - خطاهای غیرمنتظرهٔ مسیر
        logger.exception("Failed to prepare local DB at %s", path_text)
        return None


def reset_local_database(db: LocalDatabase) -> Path | None:
    """بازنشانی کامل پایگاه‌داده محلی با بکاپ‌گیری ایمن.

    این کمک‌تابع برای استفادهٔ CLI/UI تعبیه شده تا از منطق یکنواخت
    :class:`LocalDatabase` بهره ببرد و فایل فعلی را با پسوند زمان‌دار
    بکاپ بگیرد، سپس Schema جدید را مقداردهی کند.
    """

    result = db.reset_full_database()
    if result is None or isinstance(result, Path):
        return result
    raise TypeError("reset_full_database must return a Path or None")


def _format_db_prepare_error(exc: BaseException, *, db_path: Path) -> str:
    """تبدیل خطاهای آماده‌سازی پایگاه داده به پیام کاربرپسند."""

    prefix = "خطا در آماده‌سازی پایگاه داده."
    base_hint = f"مسیر: {db_path}"
    if isinstance(exc, DatabasePreparationError):
        message = str(exc)
        if getattr(exc, "diagnostics", None):
            details = []
            diagnostics = getattr(exc, "diagnostics", {}) or {}
            for table, missing in diagnostics.items():
                details.append(f"{table}: {', '.join(missing)}")
            if details:
                message = f"{message} | ستون‌های مفقود → {'؛ '.join(details)}"
        return message
    if isinstance(exc, SchemaVersionMismatchError):
        rebuild_hint = (
            f"نسخهٔ Schema پشتیبانی نمی‌شود؛ فایل {db_path} را حذف کنید تا دوباره ساخته شود."
            if exc.actual_version < 2
            else f"برای ادامه، فایل {db_path} را بازسازی یا از نسخهٔ سازگار استفاده کنید."
        )
        return f"{prefix} {exc.message}; {rebuild_hint}"
    return f"{prefix} {exc} ({base_hint})"


def _prepare_local_db(db: LocalDatabase, progress: ProgressFn) -> None:
    """اجرای initialize با گزارش خطای دقیق روی progress."""

    try:
        db.initialize()
    except DatabaseSchemaMismatchError as exc:
        diagnostics = db.get_schema_diagnostics()
        logger.error(
            "Database schema mismatch at %s (module=%s)",
            db.path,
            diagnostics.module_path,
        )
        progress(0, _format_db_prepare_error(exc, db_path=db.path))
        raise
    except (DatabaseCorruptError, DatabasePreparationError, SchemaVersionMismatchError) as exc:
        progress(0, _format_db_prepare_error(exc, db_path=db.path))
        raise


def _resolve_forms_client(args: argparse.Namespace) -> WordPressFormsClient:
    """برگشت کلاینت WordPress تزریق‌شده یا خطای خوانا در صورت نبود."""

    overrides: dict[str, Any] = getattr(args, "_ui_overrides", {}) or {}
    client = overrides.get("forms_client")
    if isinstance(client, WordPressFormsClient):
        return client
    if client is not None:
        raise TypeError("forms_client override must be a WordPressFormsClient instance")
    raise ReferenceDataMissingError(
        table="forms_entries",
        message=(
            "کلاینت WordPress تعریف نشده است؛ در محیط عملیاتی یک پیاده‌سازی "
            "WordPressFormsClient تزریق کنید یا cache-only را برای استفادهٔ آفلاین فعال کنید."
        ),
    )


def _print_audit_summary(report: dict[str, dict[str, Any]]) -> None:
    """چاپ خلاصهٔ گزارش ممیزی تخصیص."""

    print("=== Allocation Audit ===")
    for key, payload in report.items():
        count = int(payload.get("count", 0))
        print(f"{key}: {count}")
        samples = payload.get("samples") or []
        if samples:
            preview = json.dumps(samples[:3], ensure_ascii=False)
            print(f"  samples: {preview}")


def _print_metrics(report: dict[str, dict[str, Any]]) -> None:
    """چاپ JSON ساخت‌یافته برای سامانه‌های Observability."""

    summary = summarize_report(report)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _parse_since(value: str | None) -> datetime | None:
    """تبدیل ورودی متنی به datetime آگاه از timezone."""

    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _empty_history_metrics_df() -> pd.DataFrame:
    """دیتافریم خالی با ستون‌های KPI تاریخچه."""

    return pd.DataFrame(columns=METRIC_COLUMNS)


def _resolve_user_settings(ui_overrides: Mapping[str, object] | None) -> UserSettings:
    if ui_overrides:
        override_val = ui_overrides.get("user_settings")
        if override_val is not None:
            return coerce_user_settings(override_val)
    return load_user_settings()


def _log_history_metrics(
    summary_df: pd.DataFrame | None,
    *,
    students_df: pd.DataFrame,
    history_info_df: pd.DataFrame | None,
    policy: PolicyConfig,
    history_metrics_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """ثبت خلاصهٔ KPI تاریخچه به‌صورت لاگ برای هر کانال تخصیص."""

    if history_metrics_df is None:
        if summary_df is None or summary_df.empty:
            logger.info("History metrics unavailable (no summary rows).")
            return _empty_history_metrics_df()

        if history_info_df is None:
            logger.info("History metrics unavailable (no history info).")
            return _empty_history_metrics_df()

        try:
            enriched_summary = enrich_summary_with_history(
                summary_df,
                students_df=students_df,
                history_info_df=history_info_df,
                policy=policy,
            )
            history_metrics_df = compute_history_metrics(enriched_summary)
        except KeyError:
            logger.info("History metrics unavailable (missing columns).")
            return _empty_history_metrics_df()

    if history_metrics_df.empty:
        logger.info("History metrics unavailable (empty metrics).")
        return _empty_history_metrics_df()

    for _, row in history_metrics_df.iterrows():
        logger.info(
            "HistoryMetrics[channel=%s] total=%d already=%d no_match=%d missing=%d same_mentor=%d ratio=%.3f",
            row["allocation_channel"],
            int(row["students_total"]),
            int(row["history_already_allocated"]),
            int(row["history_no_history_match"]),
            int(row["history_missing_or_invalid"]),
            int(row["same_history_mentor_true"]),
            float(row["same_history_mentor_ratio"] or 0.0),
        )
    return history_metrics_df


def _validate_allocation_consistency(
    *,
    counter_summary: Mapping[str, int],
    allocations_df: pd.DataFrame,
    updated_pool_df: pd.DataFrame,
    selection_reasons_df: pd.DataFrame,
    sabt_allocations_df: pd.DataFrame | None,
) -> None:
    """Ensure counters and allocation outputs remain aligned."""

    new_male = int(counter_summary.get("new_male_count", 0))
    new_female = int(counter_summary.get("new_female_count", 0))
    expected_allocations = new_male + new_female
    if expected_allocations <= 0:
        return

    actual_allocations = len(allocations_df)
    if actual_allocations != expected_allocations:
        raise AllocationConsistencyError(
            "Allocation count mismatch: counters report "
            f"{expected_allocations} new allocations but allocations_df has "
            f"{actual_allocations} rows."
        )

    def _assert_non_empty(df: pd.DataFrame, name: str) -> None:
        if df.empty:
            raise AllocationConsistencyError(
                f"Expected non-empty DataFrame for {name} when allocations exist."
            )

    _assert_non_empty(allocations_df, "allocations")
    _assert_non_empty(updated_pool_df, "updated_pool")
    _assert_non_empty(selection_reasons_df, "selection_reasons")
    if sabt_allocations_df is not None:
        _assert_non_empty(sabt_allocations_df, "allocations_sabt")


def _validate_allocated_student_ids(
    *, allocations_df: pd.DataFrame, logs_df: pd.DataFrame
) -> None:
    """Ensure allocation and logs student_ids stay consistent before export."""

    alloc_en = canonicalize_headers(allocations_df, header_mode="en")
    success_logs = _get_success_log_rows(logs_df)

    if "student_id" not in alloc_en.columns:
        raise AllocationConsistencyError("allocations_df is missing student_id column.")
    student_ids = _normalize_student_id(alloc_en["student_id"])
    missing_mask = _student_id_missing_mask(student_ids)
    if bool(missing_mask.any()):
        missing_count = int(missing_mask.sum())
        sample = student_ids[missing_mask].head(5).tolist()
        raise AllocationConsistencyError(
            "allocations_df contains missing student_id values after attachment: "
            f"{missing_count} missing (sample={sample})."
        )

    duplicates = student_ids[student_ids.duplicated()].unique().tolist()
    if duplicates:
        raise AllocationConsistencyError(
            "allocations_df contains duplicate student_id values: "
            f"sample={duplicates[:5]}."
        )

    success_series = success_logs.get("student_id", pd.Series(dtype="string"))
    allocated_set = _get_student_id_set_from_series(student_ids)
    success_set = _get_student_id_set_from_series(success_series)

    if allocated_set != success_set:
        only_in_alloc = sorted(allocated_set - success_set)[:5]
        only_in_logs = sorted(success_set - allocated_set)[:5]
        raise AllocationConsistencyError(
            "Mismatch between allocated student_ids and successful log entries: "
            f"allocations={len(allocated_set)} success_logs={len(success_set)}; "
            f"only_in_allocations={only_in_alloc} only_in_success_logs={only_in_logs}."
        )


def _validate_and_write_allocation_workbook(
    *,
    sheets: dict[str, pd.DataFrame],
    header_overrides: dict[str, HeaderMode | None],
    prepare_overrides: dict[str, Literal["default", "raw"]],
    output: Path,
    policy: PolicyConfig,
    allocations_df: pd.DataFrame,
    logs_df: pd.DataFrame,
    join_key_audit: JoinKeyAuditResult | None,
    unallocated_summary: pd.DataFrame | None,
    sabt_allocations_df: pd.DataFrame | None,
) -> None:
    """Run export invariants (LAW/EXPORT-SSOT-ID-01) and write only after they pass."""

    _enforce_allocation_export_invariants(
        allocations_df=allocations_df,
        logs_df=logs_df,
        join_key_audit=join_key_audit,
        unallocated_summary=unallocated_summary,
        sabt_allocations_df=sabt_allocations_df,
    )

    header_internal = _coerce_header_mode(policy.excel.header_mode_internal)
    prepared_sheets: dict[str, pd.DataFrame] = {}
    for name, df in sheets.items():
        if header_overrides.get(name) is None:
            prepared_sheets[name] = df
        else:
            prepared_sheets[name] = canonicalize_headers(df, header_mode=header_internal)

    write_xlsx_atomic(
        prepared_sheets,
        output,
        rtl=policy.excel.rtl,
        font_name=policy.excel.font_name,
        font_size=policy.excel.font_size,
        header_mode=_coerce_header_mode(policy.excel.header_mode_write),
        sheet_header_modes=header_overrides,
        sheet_prepare_modes=prepare_overrides,
    )


def _enforce_allocation_export_invariants(
    *,
    allocations_df: pd.DataFrame,
    logs_df: pd.DataFrame,
    join_key_audit: JoinKeyAuditResult | None,
    unallocated_summary: pd.DataFrame | None,
    sabt_allocations_df: pd.DataFrame | None = None,
) -> None:
    """Hard guardrails for export integrity (P0, fail-fast).

    LAW/EXPORT-SSOT-ID-01 mandates:
    - AC-01: set(allocations.student_id) == set(logs.success.student_id)
    - AC-02: allocations and unallocated are disjoint by student_id.
    - AC-03: allocations_sabt (when present) matches success set.
    - INV-QA-ALLOC-JOIN-02: join-key audit invalid_count == 0.
    """

    # Re-check right before writing any output files.
    _validate_allocated_student_ids(allocations_df=allocations_df, logs_df=logs_df)

    success_rows = _get_success_log_rows(logs_df)

    if "student_id" not in success_rows.columns:
        raise AllocationConsistencyError("logs_df must contain student_id for export invariants.")

    success_set = _get_student_id_set_from_series(success_rows["student_id"])

    if join_key_audit is not None and int(join_key_audit.invalid_count) > 0:
        audit = join_key_audit.audit_frame
        audit_en = (
            canonicalize_headers(audit, header_mode="en")
            if isinstance(audit, pd.DataFrame)
            else None
        )
        sample: list[str] = []
        if isinstance(audit_en, pd.DataFrame) and "student_id" in audit_en.columns:
            any_mismatch = audit_en.get("any_mismatch")
            if any_mismatch is not None:
                bad_rows = audit_en.loc[any_mismatch == True].copy()  # noqa: E712
                bad_rows["student_id"] = _normalize_student_id(bad_rows["student_id"])
                for _, row in bad_rows.head(5).iterrows():
                    parts: list[str] = []
                    sid = row.get("student_id")
                    if pd.notna(sid):
                        parts.append(str(sid))
                    mismatch = row.get("mismatch_summary")
                    if isinstance(mismatch, str) and mismatch:
                        parts.append(mismatch)
                    mode = row.get("mentor_lookup_mode")
                    if isinstance(mode, str) and mode:
                        parts.append(f"mentor={mode}")
                    sample.append(" | ".join(parts))
        raise AllocationConsistencyError(
            "LAW/EXPORT-SSOT-ID-01 | INV-QA-ALLOC-JOIN-02: "
            "خطای ممیزی کلیدهای الحاق؛ خروجی متوقف شد. "
            f"invalid_count={int(join_key_audit.invalid_count)} total={int(join_key_audit.total)} "
            f"نمونه={sample or 'N/A'}."
        )

    alloc_en = canonicalize_headers(allocations_df, header_mode="en")
    allocated_set = _get_student_id_set_from_series(
        alloc_en.get("student_id", pd.Series(dtype="string"))
    )

    # Prefer unallocated_summary if present, otherwise fall back to logs where status != success.
    unallocated_set: set[str] = set()
    summary_was_used = False
    if isinstance(unallocated_summary, pd.DataFrame) and not unallocated_summary.empty:
        unalloc_en = canonicalize_headers(unallocated_summary, header_mode="en")
        if "student_id" in unalloc_en.columns:
            unallocated_set = _get_student_id_set_from_series(unalloc_en["student_id"])
            summary_was_used = True
    if not summary_was_used:
        logs_en = canonicalize_headers(logs_df, header_mode="en")
        if "student_id" in logs_en.columns and "allocation_status" in logs_en.columns:
            status = logs_en["allocation_status"].astype("string").str.lower()
            unalloc_rows = logs_en.loc[status != "success", "student_id"]
            unallocated_set = _get_student_id_set_from_series(unalloc_rows)

    if unallocated_set:
        overlap = allocated_set.intersection(unallocated_set)
        if overlap:
            overlap_sample = sorted(overlap)[:5]
            raise AllocationConsistencyError(
                "LAW/EXPORT-SSOT-ID-01 / AC-02: همپوشانی دانش‌آموز بین allocations و unallocated ممنوع است؛ "
                f"overlap_count={len(overlap)} sample={overlap_sample}."
            )

    if sabt_allocations_df is not None:
        sabt_en = canonicalize_headers(sabt_allocations_df, header_mode="en")
        if "student_id" not in sabt_en.columns:
            raise AllocationConsistencyError(
                "LAW/EXPORT-SSOT-ID-01 / AC-03: allocations_sabt فاقد ستون student_id است."
            )
        sabt_set = _get_student_id_set_from_series(sabt_en["student_id"])
        if sabt_set != success_set:
            only_in_sabt = sorted(sabt_set - success_set)[:5]
            only_in_success = sorted(success_set - sabt_set)[:5]
            raise AllocationConsistencyError(
                "LAW/EXPORT-SSOT-ID-01 / AC-03: عدم انطباق student_id بین allocations_sabt و لاگ موفق؛ "
                f"sabt_count={len(sabt_set)} success_count={len(success_set)}; "
                f"only_in_sabt={only_in_sabt} only_in_success={only_in_success}."
            )
        overlap_sabt_unalloc = sabt_set.intersection(unallocated_set)
        if overlap_sabt_unalloc:
            sample = sorted(overlap_sabt_unalloc)[:5]
            raise AllocationConsistencyError(
                "LAW/EXPORT-SSOT-ID-01 / AC-03: allocations_sabt نباید با دانش‌آموزان تخصیص‌نیافته همپوشان شود؛ "
                f"overlap_count={len(overlap_sabt_unalloc)} sample={sample}."
            )



def _load_forms_repository(args: argparse.Namespace, db: LocalDatabase) -> FormsRepository:
    """ساخت FormsRepository با توجه به حالت online/offline."""

    cache_only = bool(getattr(args, "cache_only", False))
    client = None if cache_only else _resolve_forms_client(args)
    return FormsRepository(client=client, db=db)


def _resolve_reference_frames(
    *, args: argparse.Namespace, db: LocalDatabase, progress: ProgressFn = _default_progress
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame | None,
    dict[str, str],
    dict[str, float],
]:
    """بارگذاری دیتافریم مدارس و Crosswalk از SQLite یا Excel."""

    _prepare_local_db(db, progress)
    schools_df: pd.DataFrame | None = None
    crosswalk_groups_df: pd.DataFrame | None = None
    crosswalk_synonyms_df: pd.DataFrame | None = None
    inputs: dict[str, str] = {}
    inputs_mtime: dict[str, float] = {}

    if getattr(args, "schools", None):
        schools_path = Path(args.schools)
        schools_df = import_school_report_from_excel(schools_path, db)
        inputs["schools"] = str(schools_path)
        inputs_mtime["schools"] = schools_path.stat().st_mtime

    groupcode_repo = GroupCodeRepository(db)
    try:
        crosswalk_groups_df = groupcode_repo.load_crosswalk_groups_frame()
        inputs.setdefault("groupcodes", f"sqlite://{db.path}")
        inputs_mtime.setdefault("groupcodes", db.path.stat().st_mtime if db.path.exists() else 0.0)
    except DatabasePreparationError:
        crosswalk_groups_df = None

    if schools_df is None:
        try:
            schools_db, _, _ = get_school_reference_frames(db)
        except ReferenceDataMissingError as exc:
            raise ReferenceDataMissingError(
                table=exc.table,
                message=(
                    f"جدول {exc.table} در پایگاه داده یافت نشد؛ «build-matrix» را با "
                    "گزینه‌های --schools اجرا کنید یا ابتدا «import-schools» را برای پر کردن کش SQLite اجرا نمایید."
                ),
            ) from exc
        schools_df = schools_db
        inputs.setdefault("schools", f"sqlite://{db.path}")
        inputs_mtime.setdefault("schools", db.path.stat().st_mtime if db.path.exists() else 0.0)

    if crosswalk_groups_df is None:
        raise ReferenceDataMissingError(
            table="groupcodes",
            message=(
                "جدول groupcodes خالی است؛ فایل کدگروه را از تب Database وارد کنید یا دستور import-groupcodes را اجرا نمایید."
            ),
        )

    return schools_df, crosswalk_groups_df, crosswalk_synonyms_df, inputs, inputs_mtime


def _resolve_students_frame(
    args: argparse.Namespace, policy: PolicyConfig, *, db: LocalDatabase | None
) -> tuple[pd.DataFrame, dict[str, str], dict[str, float]]:
    """بارگذاری دیتافریم دانش‌آموزان از مسیر فایل یا کش SQLite."""

    if getattr(args, "students", None):
        students_path = Path(args.students)
        if db:
            df = import_student_report_from_excel(students_path, db=db, policy=policy)
        else:
            raw_df = read_excel_first_sheet(students_path)
            pipeline = StudentPipelineV3(
                policy=policy, header_mode="fa", reference_mode="excel"
            )
            result = pipeline.run(raw_df)
            if result.validation.join_keys.issues:
                raise JoinKeyValidationError(result.validation.join_keys)
            df = result.canonical_df
        inputs = {"students": str(students_path)}
        inputs_mtime = {"students": students_path.stat().st_mtime}
        return df, inputs, inputs_mtime

    if db is None:
        raise ValueError(
            "برای استفاده از کش دانش‌آموز باید --local-db فعال باشد یا مسیر فایل را مشخص کنید."
        )
    df = load_students_from_cache(db=db, policy=policy)
    inputs = {"students": f"sqlite://{db.path}"}
    inputs_mtime = {"students": db.path.stat().st_mtime if db.path.exists() else 0.0}
    return df, inputs, inputs_mtime


def _resolve_mentor_pool_frame(
    args: argparse.Namespace,
    policy: PolicyConfig,
    *,
    db: LocalDatabase | None,
    pool_arg: str = "inspactor",
    pool_source: str = "inspactor",
    matrix_only: bool = False,
) -> tuple[pd.DataFrame, dict[str, str], dict[str, float]]:
    """Load mentor pool from file or SQLite cache.

    Allocation/QA paths MUST pass ``matrix_only=True`` to enforce the matrix-only
    contract. Pool-builder paths may keep ``matrix_only=False`` to allow
    Inspactor inputs via the mentor pipeline.
    """

    pool_type_arg = getattr(args, "pool_type", "matrix" if matrix_only else "inspactor")
    pool_sheet = getattr(args, "pool_sheet", None)
    path_text = getattr(args, pool_arg, None)

    if path_text:
        pool_path = Path(path_text)
        detection: pool_loader.PoolDetectionResult | None = None
        ui_overrides: dict[str, object] = getattr(args, "_ui_overrides", {}) or {}
        user_settings_payload = getattr(args, "_user_settings", None)
        if user_settings_payload is not None:
            resolved_settings = coerce_user_settings(user_settings_payload)
        else:
            resolved_settings = _resolve_user_settings(ui_overrides)
        trace_enabled = resolved_settings.enable_mentor_trace_debug

        def _load_matrix_raw() -> pd.DataFrame:
            nonlocal detection
            try:
                raw_df, detection = pool_loader.load_pool_with_detection(
                    pool_path, pool_type="matrix", pool_sheet=pool_sheet
                )
            except pool_loader.MatrixPoolRequiredError as exc:
                sheets = exc.sheets
                hint = ""
                if any("inspactor" in str(name).lower() for name in sheets):
                    hint = (
                        " This file looks like an inspactor workbook; allocation requires the matrix pool output file."
                    )
                message = (
                    f"This Allocation program requires a mentor pool workbook containing a sheet named 'matrix'. "
                    f"Please provide the matrix pool file. File: {pool_path} | Sheets: {sheets}.{hint}"
                )
                raise SystemExit(message)
            return raw_df

        def _load_inspactor_raw() -> pd.DataFrame:
            with pd.ExcelFile(pool_path) as excel:
                sheet_to_parse = pool_sheet or excel.sheet_names[0]
                return excel.parse(sheet_to_parse)

        if matrix_only:
            if pool_type_arg and pool_type_arg != "matrix":
                raise SystemExit("pool-type باید فقط 'matrix' باشد.")
            if pool_sheet and str(pool_sheet).lower() != "matrix":
                raise SystemExit("pool-sheet باید 'matrix' باشد.")
            raw_df = _load_matrix_raw()
            pool_type = "matrix"
        else:
            if pool_type_arg == "matrix":
                raw_df = _load_matrix_raw()
                pool_type = "matrix"
            else:
                pool_type = pool_type_arg or "inspactor"
                raw_df = _load_inspactor_raw()

        pool_source_value = pool_source if pool_source != "auto" else pool_type
        if db:
            df = import_mentor_pool_from_dataframe(
                raw_df,
                db=db,
                policy=policy,
                pool_source=pool_source_value,
                trace_enabled=trace_enabled,
            )
            detection = detection or df.attrs.get("pool_detection")
        else:
            try:
                df = canonicalize_pool_frame(
                    raw_df,
                    policy=policy,
                    sanitize_pool=False,
                    pool_source=pool_source_value,
                )
            except JoinKeyCanonicalizationError as exc:
                issue = JoinKeyValidationIssue(
                    entity_type="mentor",
                    row_index=_safe_row_index(exc.index),
                    column=exc.column,
                    raw_value=exc.value,
                    error_code="DATA_INVALID",
                )
                raise JoinKeyValidationError(
                    JoinKeyValidationResult(canonical_df=pd.DataFrame(), issues=[issue])
                ) from exc
        detection = detection or df.attrs.get("pool_detection")
        pool_source_value = (
            pool_source
            if pool_source != "auto"
            else getattr(detection, "pool_type", pool_type)
        )
        if detection is not None:
            df.attrs["pool_detection"] = detection
        df.attrs["pool_source"] = pool_source_value
        if os.environ.get("ALLOC_DEBUG") and matrix_only:
            raw_rows = getattr(detection, "evidence", {}).get("raw_row_count") if detection else raw_df.shape[0]
            selected_sheet = getattr(detection, "selected_sheet", "?")
            print(
                f"[ALLOC_DEBUG] mentor_pool path={pool_path} sheet={selected_sheet} "
                f"raw_rows={raw_rows} canonical_rows={df.shape[0]}"
            )
        inputs = {pool_arg: str(pool_path)}
        inputs_mtime = {pool_arg: pool_path.stat().st_mtime}
        return df, inputs, inputs_mtime

    if db is None:
        raise ValueError(
            "برای استفاده از کش استخر منتورها باید --local-db فعال باشد یا مسیر فایل را مشخص کنید."
        )
    df = load_mentor_pool_from_cache(db=db, policy=policy)
    inputs = {pool_arg: f"sqlite://{db.path}"}
    inputs_mtime = {pool_arg: db.path.stat().st_mtime if db.path.exists() else 0.0}
    return df, inputs, inputs_mtime


def _qa_validation_output_path(base: Path, *, stem_override: str | None = None) -> Path:
    suffix = stem_override or f"{base.stem}_validation.xlsx"
    return base.with_name(suffix)


def _export_qa_validation_workbook(
    *,
    report: QaReport,
    base_output: Path,
    context: QaValidationContext,
    stem_override: str | None = None,
) -> Path:
    from app.core.qa.invariants import QaReport as _QaReport  # محفاظت از چرخهٔ import

    if not isinstance(report, _QaReport):
        raise TypeError("report must be QaReport")
    output_path = _qa_validation_output_path(base_output, stem_override=stem_override)
    export_qa_validation(report, output=output_path, context=context)
    return output_path


def _normalize_override_mapping(data: Mapping[object, object] | None) -> dict[str, bool]:
    if not data:
        return {}
    normalized: dict[str, bool] = {}
    for key, value in data.items():
        try:
            enabled = bool(value)
        except Exception:
            continue
        text_key = str(key).strip()
        if text_key:
            normalized[text_key] = enabled
    return normalized


def _resolve_mentor_pool_overrides(args: argparse.Namespace) -> dict[str | int | float, bool]:
    overrides: dict[str | int | float, bool] = {}
    ui_overrides: dict[str, Any] = getattr(args, "_ui_overrides", {}) or {}
    ui_mapping = ui_overrides.get("mentor_pool_overrides")
    overrides.update(
        _normalize_override_mapping(ui_mapping if isinstance(ui_mapping, Mapping) else {})
    )

    raw = getattr(args, "mentor_overrides", None)
    if raw:
        payload = json.loads(raw)
        if not isinstance(payload, Mapping):
            raise ValueError("mentor-overrides must be a JSON object")
        overrides.update(_normalize_override_mapping(payload))
    return overrides


def _resolve_manager_overrides(args: argparse.Namespace) -> dict[str | int | float, bool]:
    overrides: dict[str | int | float, bool] = {}
    ui_overrides: dict[str, Any] = getattr(args, "_ui_overrides", {}) or {}
    ui_mapping = ui_overrides.get("mentor_pool_manager_overrides")
    overrides.update(
        _normalize_override_mapping(ui_mapping if isinstance(ui_mapping, Mapping) else {})
    )

    raw = getattr(args, "manager_overrides", None)
    if raw:
        payload = json.loads(raw)
        if not isinstance(payload, Mapping):
            raise ValueError("manager-overrides must be a JSON object")
        overrides.update(_normalize_override_mapping(payload))
    return overrides


def _default_governance_config() -> MentorPoolGovernanceConfig:
    return MentorPoolGovernanceConfig(
        default_status=MentorStatus.ACTIVE,
        mentor_status_map={},
        allowed_statuses=(MentorStatus.ACTIVE, MentorStatus.INACTIVE),
    )


def _apply_mentor_pool_overrides(
    pool: pd.DataFrame, policy: PolicyConfig, args: argparse.Namespace
) -> pd.DataFrame:
    overrides = _resolve_mentor_pool_overrides(args)
    config: MentorPoolGovernanceConfig = getattr(
        policy, "mentor_pool_governance", _default_governance_config()
    )
    ui_overrides: dict[str, object] = getattr(args, "_ui_overrides", {}) or {}
    user_settings_payload = getattr(args, "_user_settings", None)
    if user_settings_payload is not None:
        resolved_settings = coerce_user_settings(user_settings_payload)
    else:
        resolved_settings = _resolve_user_settings(ui_overrides)
    return apply_mentor_pool_governance(
        pool,
        config,
        overrides=cast(Mapping[int | str | float, bool], overrides),
        enable_trace=resolved_settings.enable_pool_governance_trace,
    )


def _detect_reader(path: Path) -> Callable[[Path], pd.DataFrame]:
    """انتخاب تابع خواندن مناسب؛ برای Excel شیت 'matrix' را ترجیح بده."""
    suffix = path.suffix.lower()
    dtype_map = {ALT_CODE_COLUMN: str}
    if suffix in {".xlsx", ".xls", ".xlsm"}:

        def _read_xlsx(p: Path) -> pd.DataFrame:
            with pd.ExcelFile(p) as xls:
                sheet = "matrix" if "matrix" in xls.sheet_names else xls.sheet_names[0]
                return xls.parse(sheet, dtype=dtype_map)

        return _read_xlsx
    return lambda p: pd.read_csv(p, dtype=dtype_map)


# --- توابع کمکی برای پارامترهای خط فرمان ---
def _normalize_min_coverage_arg(value: float | None) -> float | None:
    if value is None:
        return None
    ratio = float(value)
    if ratio > 1:
        ratio /= 100.0
    if ratio < 0 or ratio > 1:
        raise ValueError("حداقل نسبت پوشش باید عددی بین 0 و 1 باشد یا به‌صورت درصد معتبر وارد شود.")
    return ratio


# --- توابع کمکی برای پاک‌سازی خروجی (کاملاً ایمن و جامع) ---
def _is_empty_arraylike(x: object) -> bool:
    """بررسی می‌کند که آیا x یک آرایه خالی است یا خیر"""
    if isinstance(x, (pd.Series, pd.DataFrame, list, tuple)):
        return len(x) == 0
    size = getattr(x, "size", None)
    if size is not None and hasattr(x, "__len__"):
        return bool(size == 0)
    return False


def _safe_isna(x: object) -> bool:
    """نسخه ایمن از pd.isna که با آرایه‌های خالی کار می‌کند"""
    try:
        if _is_empty_arraylike(x):
            return True
        result = pd.isna(x)
        if hasattr(result, "all"):
            return bool(result.all())
        if isinstance(result, (list, tuple)):
            return all(bool(item) for item in result)
        return bool(result)
    except ValueError:
        return True
    except Exception:
        return True


def _safe_json_dumps(x: object) -> str:
    """نسخه ایمن از json.dumps"""
    try:
        return json.dumps(x, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(x)


_QA_OFFENDER_SCHEMA_VERSION = "1.0"


def _mentor_type_offenders_frame(report: QaReport) -> pd.DataFrame:
    details = report.to_details_frame("QA_RULE_MENTOR_TYPE_01")
    columns = [
        "source_sheet",
        "source_row_index",
        "mentor_id",
        "mentor_type",
        "raw_school_token",
        "resolved_school_code",
        "reason",
    ]
    if details.empty or "offenders" not in details.columns:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, object]] = []
    for offenders in details["offenders"]:
        if isinstance(offenders, list):
            for offender in offenders:
                if isinstance(offender, Mapping):
                    rows.append(dict(offender))
    if not rows:
        return pd.DataFrame(columns=columns)
    frame = pd.DataFrame(rows)
    for column in columns:
        if column not in frame.columns:
            frame[column] = pd.NA
    frame = frame.loc[:, columns]
    frame["mentor_id"] = frame["mentor_id"].astype("string").str.strip()
    frame["source_sheet"] = frame["source_sheet"].astype("string").fillna("").str.strip()
    if "source_row_index" in frame.columns:
        frame["source_row_index"] = pd.to_numeric(frame["source_row_index"], errors="coerce")
    frame = frame.sort_values(
        by=["source_sheet", "source_row_index", "mentor_id"], kind="stable"
    ).reset_index(drop=True)
    return frame


def _json_safe_value(value: object) -> object:
    if value is None or value is pd.NA:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    if isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _canonicalize_offender_records(offenders: pd.DataFrame) -> list[dict[str, object]]:
    columns = [
        "source_sheet",
        "source_row_index",
        "mentor_id",
        "mentor_type",
        "raw_school_token",
        "resolved_school_code",
        "reason",
    ]
    normalized = offenders.copy()
    for column in columns:
        if column not in normalized.columns:
            normalized[column] = pd.NA
    normalized = normalized.loc[:, columns]
    normalized["source_sheet"] = normalized["source_sheet"].astype("string").str.strip()
    normalized["mentor_id"] = normalized["mentor_id"].astype("string").str.strip()
    normalized["source_row_index"] = pd.to_numeric(
        normalized["source_row_index"], errors="coerce"
    )

    records: list[dict[str, object]] = []
    for _, row in normalized.iterrows():
        record: dict[str, object] = {}
        for column in columns:
            value = _json_safe_value(row[column])
            if column == "source_sheet" and value == "":
                value = None
            record[column] = value
        records.append(record)
    return records


def _fingerprint_offenders(offenders: list[dict[str, object]]) -> str:
    canonical = json.dumps(
        offenders, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _write_mentor_type_offenders_artifact(
    report: QaReport, *, output: Path
) -> tuple[Path, int] | None:
    offenders = _mentor_type_offenders_frame(report)
    if offenders.empty:
        return None
    offender_records = _canonicalize_offender_records(offenders)
    fingerprint = _fingerprint_offenders(offender_records)
    payload = {
        "schema_version": _QA_OFFENDER_SCHEMA_VERSION,
        "rule_id": "QA_RULE_MENTOR_TYPE_01",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "offenders": offender_records,
        "offender_count": len(offender_records),
        "data_fingerprint": fingerprint,
    }
    artifact_path = output.parent / "artifacts" / "qa_offenders.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return artifact_path, len(offender_records)


def _raise_qa_invariant_failure(report: QaReport, *, output: Path) -> NoReturn:
    sorted_failed_rules = sorted(violation.rule_id for violation in report.violations)
    artifact = _write_mentor_type_offenders_artifact(report, output=output)
    artifact_path, offender_count = artifact if artifact is not None else (None, 0)
    logger.warning(
        "QA invariants failed: rule_ids=%s offender_count=%s artifact=%s",
        sorted_failed_rules,
        offender_count,
        artifact_path,
    )
    detail = "; ".join(f"{v.rule_id}: {v.message}" for v in report.violations)
    raise ValueError(
        "QA invariants failed: " f"rules={sorted_failed_rules} details={detail or 'n/a'}"
    )


def _copy_with_attrs(df: pd.DataFrame, template: pd.DataFrame) -> pd.DataFrame:
    """کپی دیتافریم با حفظ attrs دترمینیستیک.

    pandas ``copy`` به‌صورت پیش‌فرض ``attrs`` را منتقل نمی‌کند؛ این تابع
    اطمینان می‌دهد متادیتای تزریق‌شده (مانند ``history_info_df`` روی trace)
    پس از عملیات پاک‌سازی از بین نرود.
    """

    copied = df.copy()
    if template.attrs:
        copied.attrs = template.attrs.copy()
    return copied


def _coalesce_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """ادغام امن ستون‌های تکراری حتی با نام‌های تهی/NaN."""

    if df.empty or not any(df.columns.duplicated()):
        return _copy_with_attrs(df, df)

    result_df = pd.DataFrame(index=df.index)

    def _label_key(label: object) -> tuple[str, object | None]:
        try:
            if pd.isna(label):
                return ("__nan__", None)
        except TypeError:
            # برچسب‌های ناسازگار (مثل لیست) برابر None فرض می‌شوند
            return ("__nan__", None)
        return ("value", label)

    groups: dict[tuple[str, object | None], list[int]] = {}
    representatives: dict[tuple[str, object | None], object] = {}
    for idx, column in enumerate(df.columns):
        key = _label_key(column)
        if key not in groups:
            groups[key] = []
            representatives[key] = column
        groups[key].append(idx)

    for key, positions in groups.items():
        subset = df.iloc[:, positions]
        if subset.shape[1] == 1:
            result_df[representatives[key]] = subset.iloc[:, 0]
            continue
        filled = subset.bfill(axis=1)
        result_df[representatives[key]] = filled.iloc[:, 0]

    return _copy_with_attrs(result_df, df)


def _is_complex_safe(x: object) -> bool:
    """چک می‌کند آیا یک مقدار، یک شیء پیچیده است یا نه (ایمن در برابر ndarray خالی)."""
    if isinstance(x, (dict, list, tuple, set)):
        return True

    if isinstance(x, (pd.Series, pd.DataFrame)):
        return bool(x.size > 0)

    return False


def _make_excel_safe(df: pd.DataFrame) -> pd.DataFrame:
    """
    تبدیل ایمن ستون‌های object در دیتافریم برای نوشتن در Excel
    با روش‌هایی که کاملاً در برابر ستون‌های تکراری و آرایه‌های خالی مقاوم هستند.
    """
    if df.empty:
        return _copy_with_attrs(df, df)

    # ابتدا ستون‌های تکراری را ادغام می‌کنیم
    df = _coalesce_duplicate_columns(df)

    out = df.copy()

    # پردازش هر ستون
    for col in out.columns:
        s = out[col]

        # اطمینان از اینکه s یک Series است (نه DataFrame)
        if isinstance(s, pd.DataFrame):
            if s.shape[1] > 0:
                # استفاده از اولین ستون
                s = s.iloc[:, 0]
            else:
                # اگر DataFrame خالی بود
                out[col] = pd.Series([""] * len(out), index=out.index)
                continue

        # برای ستون‌های از نوع object
        if pd_types.is_object_dtype(s.dtype):
            # تابع تبدیل ایمن برای هر مقدار
            def _safe_convert(v: object) -> str:
                if _safe_isna(v):
                    return ""
                if isinstance(v, (dict, list, tuple, set)):
                    return _safe_json_dumps(v)
                if isinstance(v, (pd.Series, pd.DataFrame)) and v.size == 0:
                    return ""
                return str(v)

            # استفاده از apply به جای map برای حساسیت کمتر به انواع داده
            out[col] = s.apply(_safe_convert)

        # برای ستون‌های عددی که ممکن است شامل NaN باشند
        elif pd_types.is_numeric_dtype(s.dtype):
            out[col] = s.fillna(0)

        # برای سایر انواع
        else:
            out[col] = s.fillna("")

    return out


def _ensure_valid_dataframe(df: pd.DataFrame, name: str = "") -> pd.DataFrame:
    """
    اطمینان از معتبر بودن یک دیتافریم برای نوشتن در Excel

    این تابع چک می‌کند که:
    1. ستون‌های تکراری وجود نداشته باشند
    2. هیچ سلولی حاوی شیء پیچیده نباشد
    3. هیچ سلولی NaN نباشد

    و در صورت لزوم، تبدیلات لازم را انجام می‌دهد.
    """
    if df.empty:
        safe_print(f"⚠️  هشدار: دیتافریم {name} خالی است!")
        return df

    # 1. بررسی و ادغام ستون‌های تکراری
    duplicate_cols = df.columns[df.columns.duplicated()]
    if len(duplicate_cols) > 0:
        safe_print(
            f"⚠️  هشدار: دیتافریم {name} دارای {len(duplicate_cols)} ستون تکراری است: {list(duplicate_cols.unique())}"
        )
        df = _coalesce_duplicate_columns(df)

    # 2. اطمینان از اینکه هیچ ستونی DataFrame نیست
    complex_cols = []
    for col in df.columns:
        if isinstance(df[col], pd.DataFrame):
            complex_cols.append(col)

    if len(complex_cols) > 0:
        safe_print(f"⚠️  هشدار: دیتافریم {name} دارای ستون‌های پیچیده است: {complex_cols}")
        df = _make_excel_safe(df)

    return df


# --- پایان توابع کمکی ---


def _read_optional_first_sheet(path: str | None) -> pd.DataFrame | None:
    """خواندن روستر شمارنده با تشخیص شیت مناسب و هدر EN."""

    if not path:
        return None

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Roster file not found: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix in {".xlsx", ".xls", ".xlsm"}:
        with pd.ExcelFile(file_path) as workbook:
            sheet_name = pick_counter_sheet_name(workbook.sheet_names)
            if sheet_name is None:
                raise ValueError(
                    "هیچ شیت سازگار با شمارنده در فایل یافت نشد؛ نام‌های قابل قبول شامل 'شمارنده' و 'Counters' است."
                )
            frame = workbook.parse(sheet_name)
    else:
        frame = pd.read_csv(file_path)

    return canonicalize_headers(frame, header_mode="en")


def _resolve_optional_override(
    args: argparse.Namespace, name: str, default: str | None = None
) -> str | None:
    """اولویت‌دهی overrideهای UI نسبت به آرگومان‌های CLI."""

    overrides = getattr(args, "_ui_overrides", {}) or {}
    value = overrides.get(name)
    candidates = [value, getattr(args, name, None), default]
    for candidate in candidates:
        if isinstance(candidate, str):
            text = candidate.strip()
            if text:
                return text
    return None


def _add_center_management_args(parser: argparse.ArgumentParser) -> None:
    """افزودن گروه آرگومان‌های مرتبط با مدیریت مراکز."""

    center_group = parser.add_argument_group("مدیریت مراکز")
    center_group.add_argument(
        "--center-manager",
        action="append",
        dest="center_manager",
        metavar="CENTER_ID=MANAGER_NAME",
        help="Override مدیر یک مرکز (قابل تکرار)",
    )
    center_group.add_argument(
        "--center-priority",
        type=str,
        help="ترتیب دلخواه مراکز (لیست جداشده با ویرگول)",
    )
    center_group.add_argument(
        "--strict-manager-validation",
        action="store_true",
        help="در صورت نبود مدیر برای مراکز خطا بده",
    )


def _parse_center_managers(cli_managers: list[str] | None) -> dict[int, list[str]]:
    """تجزیهٔ آرگومان‌های --center-manager به نگاشت پایدار."""

    mapping: dict[int, list[str]] = {}
    if not cli_managers:
        return mapping
    for item in cli_managers:
        if "=" not in item:
            raise ValueError(
                f"center-manager value '{item}' must use format CENTER_ID=MANAGER_NAME"
            )
        center_text, manager_text = item.split("=", 1)
        try:
            center_id = int(center_text.strip())
        except ValueError as exc:
            raise ValueError("center id must be an integer") from exc
        manager = manager_text.strip().strip("\"'")
        if not manager:
            raise ValueError("manager name cannot be empty")
        mapping.setdefault(center_id, []).append(manager)
    return mapping


def _parse_center_priority(priority_str: str | None) -> list[int] | None:
    """تبدیل رشتهٔ اولویت مراکز به لیست اعداد."""

    if not priority_str:
        return None
    tokens = priority_str.replace("،", ",").split(",")
    result: list[int] = []
    for token in tokens:
        text = token.strip()
        if not text:
            continue
        try:
            result.append(int(text))
        except ValueError as exc:
            raise ValueError(f"فرمت نامعتبر برای اولویت مراکز: {priority_str}") from exc
    return result or None


def _normalize_center_override_map(source: object) -> dict[int, list[str]]:
    """تبدیل ورودی دلخواه (Mapping یا JSON) به ساختار استاندارد."""

    if not isinstance(source, Mapping):
        return {}
    normalized: dict[int, list[str]] = {}
    for key, value in source.items():
        try:
            center_id = int(key)
        except (TypeError, ValueError):
            continue
        names = value if isinstance(value, (list, tuple)) else [value]
        cleaned = [str(name).strip() for name in names if str(name).strip()]
        if cleaned:
            normalized[center_id] = cleaned
    return normalized


def _merge_center_manager_maps(
    target: dict[int, list[str]], source: Mapping[int, list[str]] | None
) -> dict[int, list[str]]:
    """ادغام نگاشت ثانویه در نگاشت اصلی با حفظ ترتیب."""

    if not source:
        return target
    for center_id, names in source.items():
        existing = target.setdefault(center_id, [])
        for name in names:
            if name not in existing:
                existing.append(name)
    return target


def _resolve_center_preferences(args: argparse.Namespace, policy: PolicyConfig) -> tuple[
    Mapping[int, Sequence[str]] | None,
    Mapping[int, Sequence[str]] | None,
    list[int] | None,
    bool,
]:
    """گردآوری ورودی‌های UI و CLI برای مدیریت مراکز."""

    overrides = getattr(args, "_ui_overrides", {}) or {}
    ui_mapping = _normalize_center_override_map(overrides.get("center_managers"))

    cli_mapping = _parse_center_managers(getattr(args, "center_manager", None) or [])
    json_payload = getattr(args, "center_managers", None)
    if json_payload:
        data = json.loads(json_payload)
        if not isinstance(data, Mapping):
            raise ValueError("center-managers must be a JSON object")
        cli_mapping = _merge_center_manager_maps(cli_mapping, _normalize_center_override_map(data))
    legacy = {"golestan_manager": 1, "sadra_manager": 2}
    for attr, center_id in legacy.items():
        text = getattr(args, attr, None)
        if isinstance(text, str) and text.strip():
            cli_mapping.setdefault(center_id, []).append(text.strip())

    priority_override = overrides.get("center_priority")
    priority_text: str | None
    if isinstance(priority_override, (list, tuple)):
        priority_text = ",".join(str(item) for item in priority_override)
    elif priority_override is not None:
        priority_text = str(priority_override)
    else:
        priority_text = getattr(args, "center_priority", None)
    try:
        center_priority = _parse_center_priority(priority_text)
    except ValueError as exc:
        raise ValueError(f"center priority override is invalid: {exc}") from exc

    strict_flag = bool(getattr(args, "strict_manager_validation", False))

    return (
        ui_mapping or None,
        cli_mapping or None,
        center_priority,
        strict_flag,
    )


def _collect_cli_center_manager_overrides(
    args: argparse.Namespace,
) -> dict[int, tuple[str, ...]]:
    """تابع سازگار با تست‌های قدیمی برای جمع‌آوری override های CLI."""

    cli_mapping = _parse_center_managers(getattr(args, "center_manager", None) or [])
    json_payload = getattr(args, "center_managers", None)
    if json_payload:
        data = json.loads(json_payload)
        if not isinstance(data, Mapping):
            raise ValueError("center-managers must be a JSON object")
        cli_mapping = _merge_center_manager_maps(cli_mapping, _normalize_center_override_map(data))
    legacy = {"golestan_manager": 1, "sadra_manager": 2}
    for attr, center_id in legacy.items():
        text = getattr(args, attr, None)
        if isinstance(text, str) and text.strip():
            cli_mapping.setdefault(center_id, []).append(text.strip())
    return {center_id: tuple(names) for center_id, names in cli_mapping.items() if names}


def _maybe_export_import_to_sabt(
    *,
    args: argparse.Namespace,
    allocations_df: pd.DataFrame,
    students_df: pd.DataFrame,
    mentors_df: pd.DataFrame,
    logs_df: pd.DataFrame,
    student_ids: pd.Series,
    db: LocalDatabase | None,
    run_uuid: str | None,
) -> None:
    """تولید فایل ImportToSabt در صورت مشخص شدن مسیر خروجی."""

    sabt_output = _resolve_optional_override(args, "sabt_output")
    if not sabt_output:
        return
    cfg_path = _resolve_optional_override(
        args, "sabt_config", str(_DEFAULT_EXPORTER_CONFIG_PATH)
    ) or str(_DEFAULT_EXPORTER_CONFIG_PATH)
    template_path = _resolve_optional_override(
        args, "sabt_template", str(_DEFAULT_SABT_TEMPLATE_PATH)
    ) or str(_DEFAULT_SABT_TEMPLATE_PATH)
    exporter_cfg = load_exporter_config(cfg_path)
    export_df = prepare_allocation_export_frame(
        allocations_df,
        students_df,
        mentors_df,
        student_ids=student_ids,
    )
    df_sheet2 = build_sheet2_frame(export_df, exporter_cfg)
    df_sheet2 = apply_alias_rule(df_sheet2, export_df)
    status_series = logs_df.get("allocation_status")
    error_count = 0
    if isinstance(status_series, pd.Series):
        error_count = int((status_series.astype("string") != "success").sum())
    dedupe_logs = export_df.attrs.get("dedupe_logs")
    df_summary = build_summary_frame(
        exporter_cfg,
        total_students=len(students_df),
        allocated_count=len(df_sheet2),
        error_count=error_count,
        dedupe_logs=dedupe_logs,
    )
    df_errors = build_errors_frame(logs_df, exporter_cfg)
    df_sheet5 = build_optional_sheet_frame(exporter_cfg, "Sheet5")
    df_9394 = build_optional_sheet_frame(exporter_cfg, "9394")
    write_import_to_sabt_excel(
        df_sheet2,
        df_summary,
        df_errors,
        df_sheet5,
        df_9394,
        template_path,
        sabt_output,
    )
    if db is not None and getattr(args, "archive_exporter", False):
        archive_cfg = ExporterArchiveConfig(
            enabled=True, row_limit=int(getattr(args, "archive_row_limit", 500))
        )
        repo = ExporterArchiveRepository(db=db)
        metadata = {
            "export_path": sabt_output,
            "config_path": cfg_path,
            "template_path": template_path,
        }
        repo.archive_snapshot(
            rows_df=df_sheet2,
            exporter_version=str(exporter_cfg.get("version") or ""),
            run_uuid=run_uuid,
            run_id=None,
            metadata=metadata,
            config=archive_cfg,
        )


def _compose_duplicate_display_name(row: pd.Series) -> str:
    """تولید نام قابل‌خواندن برای گزارش ردیف تکراری."""

    if row is None:
        return ""
    candidates = [
        row.get("full_name"),
        row.get("student_name"),
        row.get("name"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    first = str(row.get("first_name", "")).strip()
    last = str(row.get("last_name", "")).strip()
    return " ".join(part for part in (first, last) if part).strip()


def _build_duplicate_row_report(
    students_df: pd.DataFrame,
    students_en: pd.DataFrame,
    duplicate_groups: dict[str, list[object]],
) -> list[dict[str, object]]:
    """ساخت ساختار قابل‌نمایش برای شناسه‌های تکراری."""

    position_map = {index: pos for pos, index in enumerate(students_df.index)}
    report: list[dict[str, object]] = []
    for student_id, index_list in duplicate_groups.items():
        rows: list[dict[str, object]] = []
        ordered = sorted(index_list, key=lambda idx: position_map.get(idx, 10**9))
        for index_label in ordered:
            position = position_map.get(index_label)
            row = students_en.loc[index_label] if index_label in students_en.index else None
            if row is None:
                national_id = ""
            else:
                raw_national_id = row.get("national_id", "")
                national_id = "" if pd.isna(raw_national_id) else str(raw_national_id).strip()
            rows.append(
                {
                    "index": index_label,
                    "position": None if position is None else position + 1,
                    "national_id": national_id,
                    "name": _compose_duplicate_display_name(row),
                }
            )
        report.append({"student_id": student_id, "rows": rows})
    return report


def _format_duplicate_report(report: list[dict[str, object]]) -> str:
    """تبدیل ساختار تکراری‌ها به متن فشرده برای چاپ."""

    lines: list[str] = []
    for payload in report:
        student_id = payload.get("student_id")
        row_items: list[str] = []
        rows_obj = payload.get("rows")
        rows = rows_obj if isinstance(rows_obj, list) else []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            name = row.get("name") or "-"
            national_id = row.get("national_id") or "-"
            position = row.get("position")
            index_label = row.get("index")
            label_parts = []
            if position is not None:
                label_parts.append(f"ردیف داده {position}")
            label_parts.append(f"index={index_label}")
            label_parts.append(f"کدملی={national_id}")
            if name and name != "-":
                label_parts.append(f"نام={name}")
            row_items.append("، ".join(label_parts))
        joined = " | ".join(row_items)
        lines.append(f"student_id {student_id} در ردیف‌های زیر تکراری است → {joined}")
    return "\n".join(lines)


def _prompt_duplicate_resolution(report_text: str) -> str:
    """نمایش گزارش و دریافت تصمیم کاربر برای رفع تکرار."""

    safe_print("❌ student_id تکراری در خروجی شمارنده یافت شد:")
    safe_print(report_text)
    safe_print("گزینه‌ها:")
    safe_print("  [R] تخصیص شمارندهٔ جدید به ردیف‌های تکراری")
    safe_print("  [D] حذف ردیف‌های تکراری و نگهداشت اولین رخداد")
    safe_print("  [A] انصراف و اصلاح دستی (خروج با خطا)")
    while True:
        choice = input("گزینهٔ موردنظر (R/D/A): ").strip().lower()
        mapping = {"r": "assign-new", "d": "drop", "a": "abort"}
        if choice in mapping:
            return mapping[choice]
        safe_print("گزینهٔ نامعتبر است؛ یکی از R/D/A را انتخاب کنید.")


def _assign_new_counters_for_duplicates(
    counters: pd.Series,
    duplicate_groups: dict[str, list[object]],
    students_en: pd.DataFrame,
    policy: PolicyConfig,
    academic_year: int,
) -> tuple[pd.Series, int]:
    """تخصیص شمارندهٔ جدید برای ردیف‌های تکراری بدون حذف داده."""

    gender_codes = policy.gender_codes
    male_value = int(gender_codes.male.value)
    female_value = int(gender_codes.female.value)
    male_mid3 = str(gender_codes.male.counter_code).zfill(3)
    female_mid3 = str(gender_codes.female.counter_code).zfill(3)
    summary: dict[str, int | str] = {
        "reused_count": 0,
        "new_male_count": 0,
        "new_female_count": 0,
        "next_male_start": 1,
        "next_female_start": 1,
    }
    summary.update(counters.attrs.get("counter_summary", {}))
    next_male = int(summary.get("next_male_start", 1))
    next_female = int(summary.get("next_female_start", 1))
    yy = year_to_yy(academic_year)
    resolved_rows = 0

    position_map = {index: pos for pos, index in enumerate(students_en.index)}

    for index_list in duplicate_groups.values():
        ordered = sorted(index_list, key=lambda idx: position_map.get(idx, 10**9))
        for index_label in ordered[1:]:
            if index_label not in students_en.index:
                continue
            row = students_en.loc[index_label]
            gender_value = pd.to_numeric(row.get("gender"), errors="coerce")
            if pd.isna(gender_value):
                raise ValueError(
                    "gender نامعتبر برای ردیف تکراری یافت شد؛ امکان تخصیص شمارندهٔ جدید نیست."
                )
            gender_value = int(gender_value)
            if gender_value == male_value:
                sequence = next_male
                next_male += 1
                summary["new_male_count"] = int(summary.get("new_male_count", 0)) + 1
                mid3 = male_mid3
            elif gender_value == female_value:
                sequence = next_female
                next_female += 1
                summary["new_female_count"] = int(summary.get("new_female_count", 0)) + 1
                mid3 = female_mid3
            else:
                raise ValueError(
                    "مقدار gender برای ردیف تکراری با policy هم‌خوانی ندارد؛ شمارندهٔ جدید قابل تولید نیست."
                )
            counters.at[index_label] = build_registration_id(yy, mid3, sequence)
            resolved_rows += 1

    if resolved_rows:
        summary["next_male_start"] = next_male
        summary["next_female_start"] = next_female
        summary["duplicate_resolution_mode"] = "assign-new"
        summary["duplicate_resolution_count"] = (
            int(summary.get("duplicate_resolution_count", 0)) + resolved_rows
        )
        counters.attrs["counter_summary"] = summary
    return counters, resolved_rows


def _apply_counter_duplicate_strategy(
    *,
    counters: pd.Series,
    duplicate_groups: dict[str, list[object]],
    students_df: pd.DataFrame,
    students_en: pd.DataFrame,
    policy: PolicyConfig,
    academic_year: int,
    strategy: str,
    interactive: bool,
) -> tuple[pd.Series, bool, tuple[object, ...]]:
    """اجرای استراتژی انتخاب‌شده برای رفع تکرار شناسه‌ها."""

    report = _build_duplicate_row_report(students_df, students_en, duplicate_groups)
    report_text = _format_duplicate_report(report)

    normalized_strategy = (strategy or "prompt").strip().lower()
    valid_strategies = {"prompt", "abort", "drop", "assign-new"}
    if normalized_strategy not in valid_strategies:
        normalized_strategy = "prompt"

    if normalized_strategy == "prompt":
        if not interactive:
            raise ValueError(
                "student_id تکراری یافت شد و ورودی تعاملی در دسترس نیست؛ "
                "یکی از گزینه‌های --counter-duplicate-strategy={drop|assign-new|abort} را مشخص کنید."
            )
        normalized_strategy = _prompt_duplicate_resolution(report_text)
    elif normalized_strategy == "abort":
        safe_print("❌ student_id تکراری در خروجی شمارنده یافت شد:")
        safe_print(report_text)

    if normalized_strategy == "abort":
        raise ValueError("student_id تکراری یافت شد؛ اجرای شمارنده متوقف شد تا ورودی اصلاح شود.")

    if normalized_strategy == "drop":
        drop_indexes: list[object] = []
        for payload in report:
            rows_obj = payload.get("rows")
            rows = rows_obj if isinstance(rows_obj, list) else []
            drop_indexes.extend(row.get("index") for row in rows[1:] if isinstance(row, Mapping))
        drop_indexes = [idx for idx in drop_indexes if idx in students_df.index]
        if not drop_indexes:
            return counters, False, tuple()
        safe_print(
            f"ℹ️  {len(drop_indexes)} ردیف تکراری حذف می‌شود؛ شمارنده برای ردیف‌های باقی‌مانده بازتولید خواهد شد."
        )
        return counters, True, tuple(drop_indexes)

    updated, resolved_rows = _assign_new_counters_for_duplicates(
        counters,
        duplicate_groups,
        students_en,
        policy,
        academic_year,
    )
    safe_print(f"ℹ️  شمارندهٔ جدید برای {resolved_rows} ردیف تکراری ساخته شد.")
    return updated, False, tuple()


def _inject_student_ids(
    students_df: pd.DataFrame,
    args: argparse.Namespace,
    policy: PolicyConfig,
) -> tuple[pd.Series, dict[str, int], pd.DataFrame]:
    """ساخت ستون student_id با رعایت Policy و ورودی‌های UI/CLI."""

    overrides = getattr(args, "_ui_overrides", {}) or {}
    is_ui_mode = bool(getattr(args, "_ui_mode", False))

    def _resolve_path(name: str) -> str | None:
        value = overrides.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
        cli_value = getattr(args, name, None)
        if isinstance(cli_value, str) and cli_value.strip():
            return cli_value.strip()
        return None

    prior_path = _resolve_path("prior_roster")
    current_path = _resolve_path("current_roster")

    prior_df = _read_optional_first_sheet(prior_path)
    current_df = _read_optional_first_sheet(current_path)

    strategy_override = overrides.get("counter_duplicate_strategy")
    if strategy_override in (None, "") and is_ui_mode:
        strategy_override = "assign-new"
    strategy_value = None
    if isinstance(strategy_override, str) and strategy_override.strip():
        strategy_value = strategy_override.strip()
    elif isinstance(getattr(args, "counter_duplicate_strategy", None), str):
        strategy_value = getattr(args, "counter_duplicate_strategy").strip()
    strategy_value = (strategy_value or "prompt").strip().lower()

    academic_year_raw = overrides.get("academic_year") or getattr(args, "academic_year", None)
    if academic_year_raw in ("", None):
        academic_year_raw = infer_year_strict(current_df)
    if academic_year_raw in ("", None):
        raise ValueError(
            "سال تحصیلی مشخص نشده یا در روستر جاری یکتا نیست؛ مقدار --academic-year الزامی است."
        )

    if isinstance(academic_year_raw, str):
        academic_year_value: int | str = academic_year_raw.strip() or academic_year_raw
    elif isinstance(academic_year_raw, int):
        academic_year_value = academic_year_raw
    else:
        raise ValueError(f"سال تحصیلی نامعتبر است: {academic_year_raw}")

    try:
        year_value = int(academic_year_value)
    except (TypeError, ValueError) as exc:  # pragma: no cover - نگهبان مهاجرت
        raise ValueError(f"سال تحصیلی نامعتبر است: {academic_year_raw}") from exc

    final_students_en: pd.DataFrame | None = None

    while True:
        students_en = canonicalize_headers(students_df, header_mode="en")
        students_en = enrich_school_columns_en(
            students_en, empty_as_zero=policy.school_code_empty_as_zero
        )
        final_students_en = students_en

        required = {"national_id", "gender"}
        missing = sorted(required - set(students_en.columns))
        if missing:
            raise ValueError(
                "ستون‌های لازم برای شمارنده یافت نشدند؛ ستون‌های مورد انتظار: 'national_id' و 'gender'."
            )

        counters = assign_counters(
            students_en,
            prior_roster_df=prior_df,
            current_roster_df=current_df,
            academic_year=year_value,
        )

        duplicate_groups = find_duplicate_student_id_groups(counters)
        if duplicate_groups:
            counters, retry_required, drop_indexes = _apply_counter_duplicate_strategy(
                counters=counters,
                duplicate_groups=duplicate_groups,
                students_df=students_df,
                students_en=students_en,
                policy=policy,
                academic_year=year_value,
                strategy=strategy_value,
                interactive=(sys.stdin.isatty() and not is_ui_mode),
            )
            if retry_required:
                if drop_indexes:
                    students_df = students_df.drop(index=list(drop_indexes))
                continue
        break

    students_en = (
        final_students_en
        if final_students_en is not None
        else canonicalize_headers(students_df, header_mode="en")
    )
    students_fa = canonicalize_headers(students_en, header_mode="fa")
    school_fa = CANON_EN_TO_FA.get("school_code", "کد مدرسه")
    if school_fa in students_fa.columns:
        school_series = students_fa[school_fa]
        if isinstance(school_series, pd.DataFrame):
            school_series = school_series.iloc[:, 0]
        students_df[school_fa] = school_series
    for column_name in ("school_code_raw", "school_code_norm", "school_status_resolved"):
        if column_name in students_en.columns:
            students_df[column_name] = students_en[column_name]

    assert_unique_student_ids(counters)

    summary = {
        "reused_count": 0,
        "new_male_count": 0,
        "new_female_count": 0,
        "next_male_start": 1,
        "next_female_start": 1,
    }
    summary.update(counters.attrs.get("counter_summary", {}))

    student_ids = counters.reindex(students_df.index).astype("string")
    students_df = students_df.copy()
    students_df["student_id"] = student_ids

    print(
        "[Counter] reused={reused_count} new_male={new_male_count} "
        "new_female={new_female_count} next_male_start={next_male_start} "
        "next_female_start={next_female_start}".format(**summary)
    )

    return student_ids, summary, students_df


def _run_build_matrix(args: argparse.Namespace, policy: PolicyConfig, progress: ProgressFn) -> int:
    """اجرای فرمان ساخت ماتریس با چاپ پیشرفت و خروجی Excel."""

    output = Path(args.output)
    db = _resolve_local_db(args)
    if db is None:
        raise ValueError(
            "پایگاه دادهٔ محلی غیرفعال است؛ برای استفاده از جداول مرجع مدارس باید فعال باشد."
        )

    progress(0, f"policy {policy.version} loaded")
    try:
        (
            schools_df,
            crosswalk_groups_df,
            crosswalk_synonyms_df,
            ref_inputs,
            ref_inputs_mtime,
        ) = _resolve_reference_frames(args=args, db=db, progress=progress)
    except TypeError as exc:
        if "progress" not in str(exc):
            raise
        (
            schools_df,
            crosswalk_groups_df,
            crosswalk_synonyms_df,
            ref_inputs,
            ref_inputs_mtime,
        ) = _resolve_reference_frames(args=args, db=db)
    pool_source_arg = getattr(args, "pool_type", "inspactor")
    insp_df, pool_inputs, pool_inputs_mtime = _resolve_mentor_pool_frame(
        args, policy, db=db, pool_arg="inspactor", pool_source=pool_source_arg
    )

    governance_cfg: MentorPoolGovernanceConfig = getattr(
        policy, "mentor_pool_governance", _default_governance_config()
    )
    mentor_overrides = _resolve_mentor_pool_overrides(args)
    manager_overrides = _resolve_manager_overrides(args)
    if mentor_overrides or manager_overrides:
        insp_df = apply_manager_mentor_governance(
            insp_df,
            governance_cfg,
            mentor_overrides=cast(Mapping[int | str | float, bool], mentor_overrides),
            manager_overrides=cast(Mapping[int | str | float, bool], manager_overrides),
        )

    inputs = {**pool_inputs, **ref_inputs}
    inputs_mtime = {**pool_inputs_mtime, **ref_inputs_mtime}

    min_coverage = _normalize_min_coverage_arg(getattr(args, "min_coverage", None))
    expected_policy_version = getattr(args, "policy_version", None)
    if isinstance(expected_policy_version, str):
        expected_policy_version = expected_policy_version.strip() or None
    cfg = BuildConfig(
        policy=policy,
        min_coverage_ratio=min_coverage,
        expected_policy_version=expected_policy_version,
    )

    if cfg.expected_policy_version and cfg.policy_version != cfg.expected_policy_version:
        raise ValueError(
            "policy version mismatch: "
            f"loaded='{cfg.policy_version}' expected='{cfg.expected_policy_version}'"
        )

    use_v3_pipeline = bool(getattr(args, "use_v3_mentor_pipeline", False))
    build_fn = build_matrix_v3 if use_v3_pipeline else build_matrix
    (
        matrix,
        validation,
        removed,
        unmatched_schools,
        unseen_groups,
        invalid_mentors,
        join_key_duplicates,
        progress_log,
    ) = build_fn(
        insp_df,
        schools_df,
        crosswalk_groups_df,
        crosswalk_synonyms_df=crosswalk_synonyms_df,
        cfg=cfg,
        progress=progress,
    )

    duplicate_threshold = int(getattr(cfg, "join_key_duplicate_threshold", 0) or 0)
    duplicate_rows = int(len(join_key_duplicates))
    if duplicate_rows > duplicate_threshold >= 0:
        preview = ""
        if "warning_type" in validation.columns and "warning_message" in validation.columns:
            warning_mask = validation["warning_type"].notna()
            if bool(warning_mask.any()):
                preview = str(validation.loc[warning_mask, "warning_message"].iloc[0])
        progress(
            65,
            (
                "❌ join-key duplicates (same mentor per 6-key) exceed threshold: "
                f"rows={duplicate_rows} threshold={duplicate_threshold}"
            ),
        )
        message = (
            f"تعداد ردیف‌های دارای کلید تکراری برای همان پشتیبان ({duplicate_rows}) از "
            f"آستانهٔ مجاز ({duplicate_threshold}) بیشتر است. هر پشتیبان باید حداکثر یک"
            " بار روی هر ترکیب ۶ کلید ظاهر شود؛ وجود پشتیبان‌های متفاوت روی"
            " یک کلید مجاز است."
        )
        if preview:
            message += f" نمونه: {preview}"
        error = ValueError(message)
        setattr(error, "is_join_key_duplicate_threshold_error", True)
        raise error

    progress(70, "building sheets")
    meta = {
        "policy_version": policy.version,
        "ssot_version": "1.0.2",
        "build_time": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "build_host": platform.node(),
        "inputs": inputs,
        "inputs_mtime": inputs_mtime,
        "rowcounts": {
            "inspactor": int(len(insp_df)),
            "schools": int(len(schools_df)),
        },
    }
    group_coverage_summary = progress_log.attrs.get("group_coverage_summary")
    if group_coverage_summary:
        meta["group_coverage_summary"] = group_coverage_summary
    coverage_metrics = progress_log.attrs.get("coverage_metrics")
    if coverage_metrics:
        meta["coverage_metrics"] = asdict(coverage_metrics)
    normalization_reports = progress_log.attrs.get("column_normalization_reports")
    if normalization_reports:
        meta["column_normalization_reports"] = normalization_reports

    progress(72, "qa invariants")
    qa_report = run_all_invariants(
        policy=policy,
        matrix=matrix,
        inspactor=insp_df,
        invalid_mentors=invalid_mentors,
        extras={"pool_join_conflicts": pd.DataFrame()},
    )
    pool_join_key_duplicates = join_key_duplicates.copy()
    merged_extras = dict(getattr(qa_report, "extras", None) or {})
    merged_extras["pool_join_key_duplicates"] = pool_join_key_duplicates
    qa_report.extras = merged_extras
    qa_context = QaValidationContext(
        matrix=matrix,
        inspactor=insp_df,
        invalid_mentors=invalid_mentors,
        meta=meta,
        pool_join_key_duplicates=pool_join_key_duplicates,
    )
    _export_qa_validation_workbook(
        report=qa_report,
        base_output=output,
        context=qa_context,
        stem_override="matrix_vs_students_validation.xlsx",
    )
    if not qa_report.passed:
        _raise_qa_invariant_failure(qa_report, output=output)
    sheets = {
        "matrix": matrix,
        "validation": validation,
        "removed": removed,
        "unmatched_schools": unmatched_schools,
        "unseen_groups": unseen_groups,
        "invalid_mentors": invalid_mentors,
        "join_key_duplicates": join_key_duplicates,
        "progress_log": progress_log,
        "meta": pd.json_normalize([meta]),
    }
    if isinstance(unseen_groups, pd.DataFrame) and not unseen_groups.empty:
        sheets["invalid_group_tokens"] = unseen_groups
    group_coverage_df = progress_log.attrs.get("group_coverage")
    if isinstance(group_coverage_df, pd.DataFrame):
        sheets["group_coverage_debug"] = group_coverage_df
        if "is_unseen_viable" in group_coverage_df.columns:
            unseen_slice = group_coverage_df[group_coverage_df["is_unseen_viable"]]
        else:
            unseen_slice = group_coverage_df[
                isin_mask(
                    group_coverage_df["status"],
                    ["candidate_only", "blocked_candidate"],
                    name="group_coverage_statuses",
                )
            ]
        sheets["group_coverage_unseen"] = unseen_slice
    header_internal = _coerce_header_mode(policy.excel.header_mode_internal)
    prepared_sheets = {
        name: canonicalize_headers(df, header_mode=header_internal) for name, df in sheets.items()
    }
    write_xlsx_atomic(
        prepared_sheets,
        output,
        rtl=policy.excel.rtl,
        font_name=policy.excel.font_name,
        font_size=policy.excel.font_size,
        header_mode=_coerce_header_mode(policy.excel.header_mode_write),
    )
    progress(100, "done")
    return 0


def _run_import_schools(
    args: argparse.Namespace, policy: PolicyConfig, progress: ProgressFn
) -> int:
    """ورود مرجع مدارس و Crosswalk به SQLite بدون اجرای ماتریس."""

    db = _resolve_local_db(args)
    if db is None:
        raise ValueError(
            "پایگاه دادهٔ محلی غیرفعال است؛ برای وارد کردن دادهٔ مرجع، گزینهٔ disable را حذف کنید."
        )

    schools_path = Path(args.school_report)
    crosswalk_path = Path(args.crosswalk)

    progress(5, "reading SchoolReport")
    schools_df = import_school_report_from_excel(schools_path, db)
    progress(40, "reading crosswalk")
    crosswalk_groups_df, crosswalk_synonyms_df = import_school_crosswalk_from_excel(
        crosswalk_path, db
    )
    progress(100, "schools and crosswalk imported")
    logger.info(
        "Imported %d schools and %d crosswalk rows into SQLite",
        len(schools_df),
        len(crosswalk_groups_df),
    )
    if crosswalk_synonyms_df is not None:
        logger.info("Synonyms rows imported: %d", len(crosswalk_synonyms_df))
    return 0


def _load_matrix_candidate_pool(matrix_path: Path, policy: PolicyConfig) -> pd.DataFrame:
    """خواندن شیت ماتریس و آماده‌سازی آن به‌عنوان استخر منتورها.

    مثال::

        >>> from pathlib import Path
        >>> import pandas as pd
        >>> sample = Path("matrix.xlsx")
        >>> _ = pd.DataFrame({
        ...     "mentor_name": ["مجازی", "علی"],
        ...     "alias": [7501, 102],
        ...     "remaining_capacity": [0, 3],
        ... }).to_excel(sample, sheet_name="matrix", index=False)  # doctest: +SKIP
        >>> policy = load_policy()  # doctest: +SKIP
        >>> sanitized = _load_matrix_candidate_pool(sample, policy)  # doctest: +SKIP
        >>> int(sanitized.loc[0, "remaining_capacity"])  # doctest: +SKIP
        3

    Args:
        matrix_path: مسیر فایل ماتریس ساخته‌شده توسط build-matrix.
        policy: سیاست فعال برای نرمال‌سازی و اعمال فیلترهای مجازی.

    Returns:
        DataFrame سازگار با allocate_batch که منتورهای مجازی را حذف کرده است.
    """

    if not matrix_path.exists():
        raise FileNotFoundError(f"Matrix file not found: {matrix_path}")

    try:
        with pd.ExcelFile(matrix_path) as workbook:
            if "matrix" not in workbook.sheet_names:
                raise ValueError(
                    "شیت 'matrix' در فایل ماتریس یافت نشد؛ build-matrix باید اجرا شده باشد."
                )
            frame = workbook.parse("matrix")
    except FileNotFoundError:
        raise
    except Exception as exc:  # pragma: no cover - خطای خواندن پیش‌بینی‌نشده
        raise ValueError(f"خطا در خواندن ماتریس {matrix_path}: {exc}") from exc

    return canonicalize_headers(
        frame, header_mode=_coerce_header_mode(policy.excel.header_mode_internal)
    )


def _prepare_allocation_frames(
    students_df: pd.DataFrame,
    pool_df: pd.DataFrame,
    *,
    policy: PolicyConfig,
    sanitize_pool: bool = True,
    pool_source: str = "inspactor",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """نرمال‌سازی ستون‌های ورودی برای اجرای تخصیص."""

    students_clean, pool_clean = canonicalize_allocation_frames(
        students_df,
        pool_df,
        policy=policy,
        sanitize_pool=sanitize_pool,
        pool_source=pool_source,
    )
    pool_clean.attrs.update(pool_df.attrs)
    return students_clean, pool_clean


def _run_pool_alignment_preflight(
    students_df: pd.DataFrame, pool_df: pd.DataFrame, *, policy: PolicyConfig
) -> pd.DataFrame:
    sample_limit = None if len(students_df) <= 500 else 100
    reports = analyze_pool_alignment_batch(
        students_df, pool_df, policy=policy, limit=sample_limit
    )
    preflight_df = pd.DataFrame(reports)
    if preflight_df.empty:
        return preflight_df
    if "student_id" in preflight_df.columns:
        normalized_ids = _normalize_student_id(preflight_df["student_id"])
        missing_mask = _student_id_missing_mask(normalized_ids)
        if missing_mask.any():
            normalized_ids = normalized_ids.mask(missing_mask, other="<missing>")
        preflight_df["student_id"] = normalized_ids

    def _stage_type_zero(counts: object) -> bool:
        if not isinstance(counts, dict):
            return False
        value = counts.get("type")
        try:
            return int(value) == 0
        except (TypeError, ValueError):
            return False

    zero_mask = preflight_df["candidate_count_final"].fillna(0) == 0
    zero_rate = float(zero_mask.mean()) if len(preflight_df) else 0.0
    stage_type_zero_rate = 0.0
    if bool(zero_mask.any()):
        stage_type_zero_rate = float(
            preflight_df.loc[zero_mask, "stage_counts"].apply(_stage_type_zero).mean()
        )

    log_fn = logger.warning if zero_rate >= 0.2 else logger.info
    log_fn(
        "Pool alignment preflight: zero_candidates=%.3f stage0=%.3f sample=%d",
        zero_rate,
        stage_type_zero_rate,
        len(preflight_df),
    )
    if zero_rate >= 0.7 and stage_type_zero_rate >= 0.7:
        raise ValueError(
            "پیش‌وارسی استخر منتورها نشان می‌دهد بیش از ۷۰٪ نمونه هیچ کاندیدایی ندارند (مرحله type=0). "
            "احتمالاً شیت اشتباه انتخاب شده است؛ گزینه‌های --pool-sheet و --pool-type را بررسی کنید."
        )
    return preflight_df


_UNKNOWN_REPORT_VERSION = "1.0"
_UNKNOWN_REPORT_NAME = "unknown_data_report.json"


def _unknown_issue_sort_key(issue: UnknownIssue) -> tuple[int, int, str, str, str]:
    column = issue.column or ""
    row_index = -1 if issue.row_index is None else int(issue.row_index)
    raw_value = repr(issue.raw_value)
    return (
        _unknown_entity_priority(issue.entity_type),
        row_index,
        column,
        issue.code,
        raw_value,
    )


def _unknown_entity_priority(entity_type: str) -> int:
    order = {"student": 0, "pool": 1, "mentor": 2}
    return order.get(entity_type, 99)


def _summarize_unknown_issues(issues: Sequence[UnknownIssue]) -> dict[str, object]:
    by_entity: dict[str, int] = {}
    by_code: dict[str, int] = {}
    for issue in issues:
        by_entity[issue.entity_type] = by_entity.get(issue.entity_type, 0) + 1
        by_code[issue.code] = by_code.get(issue.code, 0) + 1
    return {
        "total": int(len(issues)),
        "by_entity_type": dict(sorted(by_entity.items())),
        "by_code": dict(sorted(by_code.items())),
    }


def _unknown_issue_payload(issue: UnknownIssue) -> dict[str, object]:
    payload = issue.to_dict()
    payload["raw_value"] = json_safe_value(issue.raw_value)
    details = payload.get("details")
    if isinstance(details, dict):
        payload["details"] = {key: json_safe_value(val) for key, val in details.items()}
    return payload


def _build_unknowns_report(
    issues: Sequence[UnknownIssue],
    *,
    policy: PolicyConfig,
    sample_limit: int = 20,
) -> dict[str, object]:
    ordered = sorted(issues, key=_unknown_issue_sort_key)
    payloads = [_unknown_issue_payload(issue) for issue in ordered]
    return {
        "version": _UNKNOWN_REPORT_VERSION,
        "policy": {
            "unknown_data_mode": policy.unknown_data_mode,
            "unknown_manager_mode": policy.center_management.unknown_manager_mode,
        },
        "summary": _summarize_unknown_issues(ordered),
        "issues": payloads,
        "sample": payloads[: max(0, sample_limit)],
    }


def _unknown_report_path(output: Path) -> Path:
    output_path = output.expanduser()
    output_dir = output_path if output_path.is_dir() else output_path.parent
    return (output_dir / "reports" / _UNKNOWN_REPORT_NAME).resolve()


def _issues_from_join_validation(
    result: JoinKeyValidationResult,
) -> list[UnknownIssue]:
    issues: list[UnknownIssue] = []
    for issue in result.issues:
        issues.append(
            UnknownIssue(
                code="INVALID_JOIN_KEY",
                entity_type=issue.entity_type,
                column=issue.column,
                row_index=issue.row_index,
                raw_value=issue.raw_value,
                error_code=issue.error_code,
            )
        )
    return issues


def collect_unknown_issues(
    *,
    students_df: pd.DataFrame,
    pool_df: pd.DataFrame,
    policy: PolicyConfig,
) -> tuple[tuple[UnknownIssue, ...], bool]:
    channel = UnknownDataChannel(strict=False)
    validate_join_key_columns_numeric(
        students_df,
        join_keys=policy.join_keys,
        entity_type="student",
        channel=channel,
    )
    validate_join_key_columns_numeric(
        pool_df,
        join_keys=policy.join_keys,
        entity_type="pool",
        channel=channel,
    )
    validate_pool_join_keys(pool_df, policy=policy, channel=channel)
    resolver = JoinKeyResolver(policy, unknown_channel=channel)
    for _, row in students_df.iterrows():
        resolver.resolve_center(row.to_dict())
    ordered = tuple(sorted(channel.issues, key=_unknown_issue_sort_key))
    blocking = any(issue.code == "MISSING_JOIN_KEY_COLUMN" for issue in ordered)
    return ordered, blocking


def compute_preflight_exit_code(
    issues: Sequence[UnknownIssue],
    *,
    policy: PolicyConfig,
    blocking: bool,
) -> int:
    if not issues:
        return 0
    if blocking or policy.unknown_data_mode == "strict":
        return 3
    return 2


def _run_preflight_unknowns(
    args: argparse.Namespace, policy: PolicyConfig, progress: ProgressFn
) -> int:
    """Run UNKNOWN-ASK-01 preflight and write a deterministic JSON report."""

    output = Path(args.output)
    report_path = _unknown_report_path(output)

    progress(0, "loading inputs for unknowns preflight")
    db = _resolve_local_db(args)
    try:
        students_df, _, _ = _resolve_students_frame(args, policy, db=db)
        pool_df, _, _ = _resolve_mentor_pool_frame(
            args,
            policy,
            db=db,
            pool_arg="pool",
            pool_source="matrix",
            matrix_only=True,
        )
    except JoinKeyValidationError as exc:
        issues = _issues_from_join_validation(exc.result)
        report = _build_unknowns_report(issues, policy=policy)
        write_json_report(report_path, report)
        progress(
            100,
            f"unknowns report: {report_path} (issues={len(issues)})",
        )
        return 3

    pool_source_arg = "matrix"
    detection = pool_df.attrs.get("pool_detection")
    pool_source = getattr(detection, "pool_type", None) or pool_df.attrs.get(
        "pool_source", pool_source_arg
    )
    students_base, pool_base = _prepare_allocation_frames(
        students_df,
        pool_df,
        policy=policy,
        sanitize_pool=True,
        pool_source=pool_source,
    )
    pool_base = _apply_mentor_pool_overrides(pool_base, policy, args)

    issues, blocking = collect_unknown_issues(
        students_df=students_base,
        pool_df=pool_base,
        policy=policy,
    )
    report = _build_unknowns_report(issues, policy=policy)
    write_json_report(report_path, report)
    exit_code = compute_preflight_exit_code(
        issues, policy=policy, blocking=blocking
    )
    progress(
        100,
        f"unknowns report: {report_path} (issues={len(issues)})",
    )
    return exit_code


def _sanitize_pool_for_allocation(
    pool_df: pd.DataFrame, *, policy: PolicyConfig, pool_source: str = "inspactor"
) -> pd.DataFrame:
    """پاک‌سازی استخر منتورها برای تخصیص بر اساس Policy.

    این تابع لایهٔ Infra تنها وظیفهٔ فوروارد کردن استخر خام به منطق خالص
    :func:`app.core.canonical_frames.canonicalize_pool_frame` را دارد تا
    منتورهای مجازی حذف شوند، کلیدهای join به نوع صحیح `Int64` تبدیل شوند و
    آمار اصلاحات در ``df.attrs["pool_canonicalization_stats"]`` ثبت شود.

    مثال::

        >>> import pandas as pd
        >>> from app.core.policy_loader import load_policy
        >>> policy = load_policy()  # doctest: +SKIP
        >>> raw = pd.DataFrame({
        ...     "mentor_name": ["مجازی", "علی"],
        ...     "alias": [7501, 102],
        ...     "remaining_capacity": [0, 3],
        ... })
        >>> clean = _sanitize_pool_for_allocation(raw, policy=policy)  # doctest: +SKIP
        >>> int(clean["remaining_capacity"].sum())  # doctest: +SKIP
        3

    Args:
        pool_df: دیتافریم خام استخر منتورها (inspactor یا matrix).
        policy: سیاست فعال برای تشخیص منتور مجازی و اعمال قواعد ستون‌ها.

    Returns:
        دیتافریم استاندارد و فاقد منتور مجازی برای ورودی ``allocate_batch``.
    """

    sanitized = canonicalize_pool_frame(
        pool_df,
        policy=policy,
        sanitize_pool=True,
        pool_source=pool_source,
        require_join_keys=True,
    )

    sanitized_en = canonicalize_headers(sanitized, header_mode="en")
    sanitized_en = sanitized_en.loc[:, ~sanitized_en.columns.duplicated()]
    sanitized_en.attrs.update(sanitized.attrs)

    return sanitized_en


def _allocate_and_write(
    students_base: pd.DataFrame,
    pool_base: pd.DataFrame,
    *,
    args: argparse.Namespace,
    policy: PolicyConfig,
    progress: ProgressFn,
    output: Path,
    capacity_column: str,
    db: LocalDatabase | None,
    command_name: str,
    input_students_path: Path | None,
    input_pool_path: Path | None,
    policy_path: Path,
    user_settings: UserSettings | None = None,
    pool_alignment_preflight: pd.DataFrame | None = None,
    pool_detection: Mapping[str, object] | None = None,
) -> int:
    """اجرای تخصیص، الصاق شناسه‌ها و نوشتن خروجی‌های Excel."""
    run_uuid = uuid4().hex
    started_at = datetime.now(UTC)
    cli_args_text = " ".join(getattr(args, "_raw_argv", [])).strip() or None
    ui_overrides: dict[str, object] = getattr(args, "_ui_overrides", {}) or {}
    resolved_settings = coerce_user_settings(user_settings) if user_settings else _resolve_user_settings(ui_overrides)
    qa_report: QaReport | None = None
    join_key_audit: JoinKeyAuditResult | None = None
    history_metrics_df: pd.DataFrame | None = None
    history_info_df: pd.DataFrame | None = None
    qa_meta: dict[str, object] | None = None
    success = False
    status_message = "success"

    student_ids, counter_summary, students_base = _inject_student_ids(students_base, args, policy)
    setattr(args, "_counter_summary", counter_summary)

    ui_center_map, cli_center_map, center_priority, strict_validation = _resolve_center_preferences(
        args, policy
    )

    allocations_df: pd.DataFrame | None = None
    updated_pool_df: pd.DataFrame | None = None
    logs_df: pd.DataFrame | None = None
    trace_df: pd.DataFrame | None = None
    trace_extras: TraceDebugFrames | None = None
    sabt_allocations_df: pd.DataFrame | None = None

    try:
        batch_result = allocate_batch(
            students_base.copy(deep=True),
            pool_base.copy(deep=True),
            policy=policy,
            progress=progress,
            capacity_column=capacity_column,
            frames_already_canonical=True,
            center_manager_map=cli_center_map,
            ui_center_manager_map=ui_center_map,
            center_priority=center_priority,
            strict_center_validation=strict_validation,
            use_join_buckets=resolved_settings.use_join_buckets,
        )
        allocations_df = batch_result.allocations_df
        updated_pool_df = batch_result.pool_output
        logs_df = batch_result.logs_df
        trace_df = batch_result.trace_df
        trace_extras = batch_result.trace_extras

        header_internal: HeaderMode = _coerce_header_mode(policy.excel.header_mode_internal)
        students_spine = _build_students_spine(students_base, header_mode=header_internal)

        allocations_df = assert_student_id_integrity(
            _ensure_student_id_column_for_empty(allocations_df),
            header_mode=header_internal,
            expect_unique=True,
            students_df=students_spine,
            context="allocations",
        )
        logs_df = assert_student_id_integrity(
            _ensure_student_id_column_for_empty(logs_df),
            header_mode=header_internal,
            expect_unique=False,
            students_df=students_spine,
            context="logs",
        )
        trace_df = assert_student_id_integrity(
            _ensure_student_id_column_for_empty(trace_df),
            header_mode=header_internal,
            expect_unique=False,
            students_df=students_spine,
            context="trace",
        )

        _validate_allocated_student_ids(
            allocations_df=allocations_df,
            logs_df=logs_df,
        )

        success_spine = _build_success_spine(
            logs_df,
            students_spine=students_spine,
            header_mode=header_internal,
        )
        allocations_df = _build_allocations_view(
            allocations_df,
            success_spine=success_spine,
            header_mode=header_internal,
        )

        export_profile_choice = _resolve_optional_override(args, "export_profile", "sabt") or "sabt"
        export_profile_path = _resolve_optional_override(
            args, "export_profile_path", str(_DEFAULT_ALLOC_PROFILE_PATH)
        ) or str(_DEFAULT_ALLOC_PROFILE_PATH)
        students_for_export = students_spine.copy()
        if export_profile_choice == "sabt":
            sabt_profile = load_sabt_export_profile(Path(export_profile_path))
            sabt_allocations_df = build_sabt_export_frame(
                allocations_df,
                students_for_export,
                profile=sabt_profile,
                summary_df=trace_extras.summary_df if trace_extras else None,
            )

        # --- پاک‌سازی جامع خروجی قبل از نوشتن ---
        # اطمینان از معتبر بودن همه دیتافریم‌ها
        allocations_df = _ensure_valid_dataframe(allocations_df, "allocations")
        updated_pool_df = _ensure_valid_dataframe(updated_pool_df, "updated_pool")
        logs_df = _ensure_valid_dataframe(logs_df, "logs")
        trace_df = _ensure_valid_dataframe(trace_df, "trace")
        history_info_df = trace_df.attrs.get("history_info_df")
        selection_reasons_df = build_selection_reason_rows(
            allocations_df,
            students_base,
            pool_base,
            policy=policy,
            logs=logs_df,
            trace=trace_df,
            summary_df=trace_extras.summary_df if trace_extras else None,
        )
        selection_reasons_df = _ensure_valid_dataframe(selection_reasons_df, "selection_reasons")
        counter_summary = _sync_counter_summary_with_allocations(
            counter_summary=counter_summary,
            allocations_df=allocations_df,
            students_df=students_base,
            policy=policy,
        )
        _validate_allocation_consistency(
            counter_summary=counter_summary,
            allocations_df=allocations_df,
            updated_pool_df=updated_pool_df,
            selection_reasons_df=selection_reasons_df,
            sabt_allocations_df=sabt_allocations_df,
        )
        setattr(args, "_counter_summary", counter_summary)
        sheet_name, selection_reasons_df = write_selection_reasons_sheet(
            selection_reasons_df,
            writer=None,
            policy=policy,
        )

        students_for_audit = assert_student_id_integrity(
            students_base.copy(),
            header_mode=header_internal,
            expect_unique=True,
            students_df=students_spine,
            context="students_for_audit",
        )

        join_key_audit = validate_allocation_join_keys_with_wildcard(
            allocations_df,
            students_for_audit,
            pool_base,
            policy=policy,
        )
        join_key_audit_sheet = build_join_key_audit_sheet(join_key_audit.audit_frame, policy=policy)
        join_key_summary_sheet = build_join_key_summary_sheet(join_key_audit.audit_frame)

        if sabt_allocations_df is not None:
            sabt_allocations_df = _ensure_valid_dataframe(sabt_allocations_df, "allocations_sabt")

        qa_report = run_all_invariants(
            policy=policy,
            allocation=allocations_df,
            allocation_summary=updated_pool_df,
            student_report=None,
            pool=pool_base,
            history_info=history_info_df,
            pool_alignment_preflight=pool_alignment_preflight
            if resolved_settings.enable_qa_pool_coverage_rules
            else None,
            enable_pool_coverage_rules=resolved_settings.enable_qa_pool_coverage_rules,
        )
        qa_meta = _build_qa_meta(
            run_uuid=run_uuid,
            command_name=command_name,
            policy=policy,
            capacity_column=capacity_column,
            output=output,
            input_students_path=input_students_path,
            input_pool_path=input_pool_path,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            qa_report=qa_report,
            join_key_audit=join_key_audit.audit_frame,
            trace_df=trace_df,
            trace_summary_df=trace_extras.summary_df if trace_extras else None,
            history_info_df=history_info_df,
            pool_detection=pool_detection,
        )
        merged_extras = dict(qa_report.extras or {})
        preflight_sheet = (
            _make_excel_safe(pool_alignment_preflight)
            if isinstance(pool_alignment_preflight, pd.DataFrame)
            else None
        )
        trace_debug_sheets: dict[str, pd.DataFrame] = {}
        if resolved_settings.enable_mentor_trace_debug:
            trace_debug_sheets = collect_trace_debug_sheets(
                trace_df,
                logs_df=logs_df,
                students_df=students_base,
                policy=policy,
                pool_trace=pool_base.attrs.get(_POOL_PIPELINE_TRACE_ATTR),
                pool_df=pool_base,
                enable_standard_debug_sheets=False,
                enable_mentor_trace_debug=True,
                enable_history_metrics=False,
                enable_pool_governance_trace=resolved_settings.enable_pool_governance_trace,
                enable_bucket_trace=resolved_settings.enable_bucket_trace,
            )
        qa_context = QaValidationContext(
            allocation=allocations_df,
            allocation_summary=updated_pool_df,
            meta=qa_meta,
            alloc_join_audit=join_key_audit_sheet,
            alloc_join_summary=join_key_summary_sheet,
            pool_join_conflicts=merged_extras.get("pool_join_conflicts"),
            pool_alignment_preflight=preflight_sheet,
            eligibility_trace=trace_debug_sheets.get("EligibilityTrace"),
            mentor_pipeline_trace=trace_debug_sheets.get("MentorPipelineTrace"),
        )
        merged_extras["pool_join_conflicts"] = qa_context.pool_join_conflicts
        qa_report.extras = merged_extras
        _export_qa_validation_workbook(
            report=qa_report,
            base_output=output,
            context=qa_context,
        )
        if qa_meta is not None:
            logger.info(
                "QA and trace summary",
                extra={"structured": structured_event("qa.trace", **qa_meta)},
            )
        if not qa_report.passed:
            _raise_qa_invariant_failure(qa_report, output=output)

        summary_df_attr = trace_extras.summary_df if trace_extras else None
        ui_overrides = getattr(args, "_ui_overrides", {}) or {}
        history_metrics_df = _empty_history_metrics_df()
        if resolved_settings.enable_history_metrics and (
            isinstance(summary_df_attr, pd.DataFrame)
            and not summary_df_attr.empty
            and history_info_df is not None
        ):
            try:
                enriched_summary = enrich_summary_with_history(
                    summary_df_attr,
                    students_df=students_base,
                    history_info_df=history_info_df,
                    policy=policy,
                )
                history_metrics_df = compute_history_metrics(enriched_summary)
            except KeyError:
                history_metrics_df = _empty_history_metrics_df()

        if resolved_settings.enable_history_metrics:
            history_metrics_df = _log_history_metrics(
                summary_df_attr,
                students_df=students_base,
                history_info_df=history_info_df,
                policy=policy,
                history_metrics_df=history_metrics_df,
            )

        metrics_callback = ui_overrides.get("history_metrics_callback")
        if callable(metrics_callback):
            try:
                metrics_callback(history_metrics_df.copy())
            except Exception:  # pragma: no cover - UI callback safety
                logger.exception("Failed to deliver history metrics to UI")

        sheets: dict[str, pd.DataFrame] = {}
        header_overrides: dict[str, HeaderMode | None] = {}
        prepare_overrides: dict[str, Literal["default", "raw"]] = {}

        debug_sheets: dict[str, pd.DataFrame] = {}
        if (
            resolved_settings.enable_trace_debug_sheets
            or resolved_settings.enable_mentor_trace_debug
            or resolved_settings.enable_pool_governance_trace
            or resolved_settings.enable_bucket_trace
        ):
            debug_sheets = collect_trace_debug_sheets(
                trace_df,
                logs_df=logs_df,
                students_df=students_base,
                history_info_df=history_info_df,
                policy=policy,
                summary_df=summary_df_attr,
                unallocated_summary=trace_extras.unallocated_summary if trace_extras else None,
                policy_violations=trace_extras.policy_violations if trace_extras else None,
                final_status_counts=trace_extras.final_status_counts if trace_extras else None,
                pool_trace=pool_base.attrs.get(_POOL_PIPELINE_TRACE_ATTR),
                pool_df=pool_base,
                enable_standard_debug_sheets=resolved_settings.enable_trace_debug_sheets,
                enable_mentor_trace_debug=resolved_settings.enable_mentor_trace_debug,
                enable_history_metrics=resolved_settings.enable_history_metrics,
                enable_pool_governance_trace=resolved_settings.enable_pool_governance_trace,
                enable_bucket_trace=resolved_settings.enable_bucket_trace,
            )
        for name, df in debug_sheets.items():
            sheets[name] = _make_excel_safe(df)
            header_overrides[name] = None

        _enforce_allocation_export_invariants(
            allocations_df=allocations_df,
            logs_df=logs_df,
            join_key_audit=join_key_audit,
            unallocated_summary=trace_extras.unallocated_summary if trace_extras else None,
            sabt_allocations_df=sabt_allocations_df,
        )

        if _resolve_optional_override(args, "sabt_output"):
            _maybe_export_import_to_sabt(
                args=args,
                allocations_df=allocations_df,
                students_df=students_base,
                mentors_df=pool_base,
                logs_df=logs_df,
                student_ids=student_ids,
                db=db,
                run_uuid=run_uuid,
            )

        # تبدیل نهایی به فرمت‌های قابل نوشتن در Excel
        allocations_df = _make_excel_safe(allocations_df)
        updated_pool_df = _make_excel_safe(updated_pool_df)
        logs_df = _make_excel_safe(logs_df)
        if resolved_settings.enable_trace_export:
            trace_df = _make_excel_safe(trace_df)
        selection_reasons_df = _make_excel_safe(selection_reasons_df)
        # sabt_allocations_df با هدر اصلی حفظ می‌شود اما از مسیر آماده‌سازی پیش‌فرض
        # عبور می‌کند تا ستون‌های موبایل/رهگیری به‌صورت متن و با صفر پیشتاز ذخیره شوند.
        # --- پایان پاک‌سازی ---

        progress(90, "writing outputs")
        if sabt_allocations_df is not None:
            sheets["allocations"] = allocations_df
            sheets["allocations_sabt"] = sabt_allocations_df
            header_overrides["allocations_sabt"] = None
        else:
            sheets["allocations"] = allocations_df
        sheets["updated_pool"] = updated_pool_df
        sheets["logs"] = logs_df
        if resolved_settings.enable_trace_export:
            sheets["trace"] = trace_df
        sheets[sheet_name] = selection_reasons_df
        sheets["allocation_vs_pool_audit"] = join_key_audit_sheet

        _validate_and_write_allocation_workbook(
            sheets=sheets,
            header_overrides=header_overrides,
            prepare_overrides=prepare_overrides,
            output=output,
            policy=policy,
            allocations_df=allocations_df,
            logs_df=logs_df,
            join_key_audit=join_key_audit,
            unallocated_summary=trace_extras.unallocated_summary if trace_extras else None,
            sabt_allocations_df=sabt_allocations_df,
        )

        if getattr(args, "determinism_check", False):
            progress(92, "determinism check")
            allocations_check, pool_check, logs_check, trace_check = allocate_batch(
                students_base.copy(deep=True),
                pool_base.copy(deep=True),
                policy=policy,
                progress=lambda *_: None,
                capacity_column=capacity_column,
                frames_already_canonical=True,
                center_manager_map=cli_center_map,
                ui_center_manager_map=ui_center_map,
                center_priority=center_priority,
                strict_center_validation=strict_validation,
                use_join_buckets=resolved_settings.use_join_buckets,
            )

            header_internal = _coerce_header_mode(policy.excel.header_mode_internal)

            def _canon(df: pd.DataFrame) -> pd.DataFrame:
                return canonicalize_headers(df, header_mode=header_internal).reset_index(drop=True)

            try:
                pd_testing.assert_frame_equal(_canon(allocations_df), _canon(allocations_check))
                pd_testing.assert_frame_equal(_canon(updated_pool_df), _canon(pool_check))
                pd_testing.assert_frame_equal(_canon(logs_df), _canon(logs_check))
                pd_testing.assert_frame_equal(_canon(trace_df), _canon(trace_check))
            except AssertionError as exc:  # pragma: no cover - determinism failure path
                raise RuntimeError("Determinism check failed: outputs differ between runs") from exc

        if getattr(args, "audit", False) or getattr(args, "metrics", False):
            progress(95, "auditing allocations")
            report = audit_allocations(output)
            if getattr(args, "audit", False):
                _print_audit_summary(report)
            if getattr(args, "metrics", False):
                _print_metrics(report)

        progress(100, "done")
        success = True
        return 0
    except Exception as exc:
        status_message = str(exc)
        raise
    finally:
        completed_at = datetime.now(UTC)
        total_students = len(students_base)
        allocated_students = (
            allocations_df.shape[0] if isinstance(allocations_df, pd.DataFrame) else None
        )
        unallocated_students = (
            total_students - allocated_students if allocated_students is not None else None
        )
        if qa_meta is None:
            join_key_audit_frame = join_key_audit.audit_frame if join_key_audit else None
            qa_meta = _build_qa_meta(
                run_uuid=run_uuid,
                command_name=command_name,
                policy=policy,
                capacity_column=capacity_column,
                output=output,
                input_students_path=input_students_path,
                input_pool_path=input_pool_path,
                started_at=started_at,
                completed_at=completed_at,
                qa_report=qa_report,
                join_key_audit=join_key_audit_frame,
                trace_df=trace_df,
                trace_summary_df=trace_extras.summary_df if trace_extras else None,
                history_info_df=history_info_df,
                pool_detection=pool_detection,
            )
        final_meta = dict(qa_meta or {})
        final_meta.setdefault("completed_at", completed_at.isoformat().replace("+00:00", "Z"))
        final_meta["success"] = success
        final_meta["status"] = status_message
        logger.info(
            "Allocation run completed",
            extra={"structured": structured_event("qa.trace.completed", **final_meta)},
        )
        qa_outcome = history_store.summarize_qa(qa_report)
        run_ctx = history_store.build_run_context(
            command=command_name,
            cli_args=cli_args_text,
            policy_version=policy.version,
            ssot_version="1.0.2",
            started_at=started_at,
            completed_at=completed_at,
            success=success,
            message=status_message,
            input_students=input_students_path,
            input_pool=input_pool_path,
            output=output,
            policy_path=policy_path,
            total_students=total_students,
            allocated_students=allocated_students,
            unallocated_students=unallocated_students,
        )
        history_store.log_allocation_run(
            run_uuid=run_uuid,
            ctx=run_ctx,
            history_metrics=history_metrics_df if success and resolved_settings.enable_history_metrics else None,
            qa_outcome=qa_outcome,
            qa_report=qa_report,
            trace_snapshot=trace_df if success and resolved_settings.enable_trace_export else None,
            trace_summary_df=(
                trace_extras.summary_df
                if trace_extras and resolved_settings.enable_trace_debug_sheets
                else None
            ),
            qa_extras=getattr(qa_report, "extras", None),
            db=db,
        )


def _run_allocate(args: argparse.Namespace, policy: PolicyConfig, progress: ProgressFn) -> int:
    """اجرای فرمان تخصیص دانش‌آموزان با خروجی Excel."""

    output = Path(args.output)
    policy_path = Path(args.policy)
    capacity_column = args.capacity_column or policy.columns.remaining_capacity

    db = _resolve_local_db(args)
    user_settings: UserSettings | None = getattr(args, "_user_settings", None)

    progress(0, "loading inputs")
    students_df, student_inputs, _ = _resolve_students_frame(args, policy, db=db)
    pool_df, pool_inputs, _ = _resolve_mentor_pool_frame(
        args,
        policy,
        db=db,
        pool_arg="pool",
        pool_source="matrix",
        matrix_only=True,
    )
    detection = pool_df.attrs.get("pool_detection")
    detection_payload = asdict(detection) if detection is not None else None
    pool_source = getattr(detection, "pool_type", None) or pool_df.attrs.get(
        "pool_source", "matrix"
    )
    if pool_df.attrs:
        pool_df = pool_df.copy(deep=False)
        pool_df.attrs.clear()
        pool_df.attrs["pool_source"] = pool_source

    students_base, pool_base = _prepare_allocation_frames(
        students_df,
        pool_df,
        policy=policy,
        sanitize_pool=True,
        pool_source=pool_source,
    )

    pool_base = _apply_mentor_pool_overrides(pool_base, policy, args)

    preflight_df = _run_pool_alignment_preflight(
        students_base, pool_base, policy=policy
    )

    return _allocate_and_write(
        students_base,
        pool_base,
        args=args,
        policy=policy,
        progress=progress,
        output=output,
        capacity_column=capacity_column,
        db=db,
        command_name="allocate",
        input_students_path=(
            Path(args.students) if getattr(args, "students", None) else (db.path if db else None)
        ),
        input_pool_path=(
            Path(args.pool) if getattr(args, "pool", None) else (db.path if db else None)
        ),
        policy_path=policy_path,
        user_settings=user_settings,
        pool_alignment_preflight=preflight_df,
        pool_detection=detection_payload,
    )


def _run_rule_engine(args: argparse.Namespace, policy: PolicyConfig, progress: ProgressFn) -> int:
    """اجرای موتور قواعد روی ماتریس ساخته‌شده بدون نیاز به استخر جداگانه."""

    students_path = Path(args.students)
    matrix_path = Path(args.matrix)
    output = Path(args.output)
    policy_path = Path(args.policy)
    capacity_column = args.capacity_column or policy.columns.remaining_capacity

    reader_students = _detect_reader(students_path)

    progress(0, "loading inputs")
    students_df = reader_students(students_path)
    pool_df = _load_matrix_candidate_pool(matrix_path, policy)
    detection = pool_df.attrs.get("pool_detection")
    detection_payload = asdict(detection) if detection is not None else None
    if pool_df.attrs:
        pool_df = pool_df.copy(deep=False)
        pool_df.attrs.clear()

    students_base, pool_base = _prepare_allocation_frames(
        students_df,
        pool_df,
        policy=policy,
        sanitize_pool=True,
        pool_source="matrix",
    )

    pool_base = _apply_mentor_pool_overrides(pool_base, policy, args)

    db = _resolve_local_db(args)
    user_settings: UserSettings | None = getattr(args, "_user_settings", None)
    return _allocate_and_write(
        students_base,
        pool_base,
        args=args,
        policy=policy,
        progress=progress,
        output=output,
        capacity_column=capacity_column,
        db=db,
        command_name="rule-engine",
        input_students_path=students_path,
        input_pool_path=matrix_path,
        policy_path=policy_path,
        user_settings=user_settings,
        pool_alignment_preflight=None,
        pool_detection=detection_payload,
    )


def _import_students_from_forms_cache(*, db: LocalDatabase, policy: PolicyConfig) -> pd.DataFrame:
    """بارگذاری forms_entries و ذخیره در کش دانش‌آموزان برای Core."""

    repo = FormsRepository(client=None, db=db)
    entries = repo.load_entries()
    if entries.empty:
        raise ReferenceDataMissingError(
            table="forms_entries",
            message="کش forms_entries خالی است؛ ابتدا sync-forms را اجرا کنید.",
        )
    normalized = entries.copy()
    for key in policy.join_keys:
        if key not in normalized.columns:
            raise ReferenceDataMissingError(
                table="forms_entries",
                message=f"ستون مورد انتظار {key!r} در forms_entries یافت نشد.",
            )
        normalized[key] = pd.to_numeric(normalized[key], errors="coerce").astype("Int64")
    db.upsert_students_cache(normalized, join_keys=policy.join_keys)
    return normalized


def _run_sync_forms(args: argparse.Namespace, policy: PolicyConfig, progress: ProgressFn) -> int:
    """همگام‌سازی ورودی‌های فرم WordPress با کش SQLite."""

    db = _resolve_local_db(args)
    if db is None:
        raise ValueError("برای sync-forms باید --local-db مشخص شود.")

    _prepare_local_db(db, progress)
    cache_only = bool(getattr(args, "cache_only", False))
    repo = _load_forms_repository(args, db)
    if cache_only:
        try:
            cached = repo.load_entries()
        except ReferenceDataMissingError:
            print("no cached forms entries found")
            return 0
        if cached.empty:
            print("no cached forms entries found")
            return 0
        print(f"cached forms entries: {len(cached)} rows")
        return 0

    since_dt = _parse_since(getattr(args, "since", None))
    result = repo.sync_from_wordpress(since=since_dt)
    print(f"forms synced: fetched={result.fetched_count}, persisted={result.persisted_count}")
    return 0


def _run_exporter_archive(
    args: argparse.Namespace, *, db: LocalDatabase, progress: ProgressFn = _default_progress
) -> int:
    """اجرای فرمان‌های لیست/مقایسه Snapshot های ImportToSabt."""

    _prepare_local_db(db, progress)
    repo = ExporterArchiveRepository(db=db)
    if args.action == "list":
        rows = repo.list_snapshots()
        for row in rows:
            print(
                f"id={row.get('id')} name={row.get('exporter_name')} created_at={row.get('created_at')} "
                f"rows={row.get('row_count')} limit={row.get('row_limit')} truncated={bool(row.get('is_truncated'))} "
                f"hash={str(row.get('row_hash', ''))[:12]}"
            )
        if not rows:
            print("no exporter snapshots found")
        return 0

    if args.action == "compare":
        if args.snapshot_a is None or args.snapshot_b is None:
            raise ValueError("برای compare باید --a و --b مشخص شود.")
        try:
            result = repo.compare_snapshots(args.snapshot_a, args.snapshot_b)
        except ValueError as exc:
            print(str(exc))
            return 1
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        return 0

    raise RuntimeError(f"Unsupported exporter-archive action: {args.action}")


def _build_parser() -> argparse.ArgumentParser:
    """ایجاد پارسر دستورات با زیرفرمان‌های build، allocate و rule-engine."""
    parser = argparse.ArgumentParser(description="Eligibility Matrix CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    build_cmd = sub.add_parser(
        "build-matrix",
        help="ساخت ماتریس اهلیت",
        description=(
            "ساخت ماتریس مطابق policy؛ شامل گیت صحت کد/نام مدرسه که "
            "در صورت عبور از آستانهٔ policy اجرا را متوقف می‌کند و ردیف‌های خطا را "
            "در شیت invalid_mentors ثبت می‌کند."
        ),
    )
    build_cmd.add_argument(
        "--inspactor", required=False, help="(اختیاری) مسیر فایل inspactor برای بروزرسانی کش"
    )
    build_cmd.add_argument(
        "--pool-type",
        choices=("inspactor", "matrix"),
        default="inspactor",
        help="نوع استخر منتورها برای ساخت ماتریس (پیش‌فرض inspactor)",
    )
    build_cmd.add_argument(
        "--pool-sheet",
        required=False,
        help="نام شیت ورودی استخر (برای matrix باید 'matrix' باشد)",
    )
    build_cmd.add_argument(
        "--schools",
        required=False,
        help="(اختیاری) مسیر SchoolReport برای بروزرسانی مرجع مدارس در SQLite",
    )
    build_cmd.add_argument(
        "--crosswalk",
        required=False,
        help="(اختیاری) مسیر Crosswalk برای بروزرسانی مرجع در SQLite",
    )
    build_cmd.add_argument("--output", required=True, help="مسیر Excel خروجی")
    build_cmd.add_argument(
        "--policy",
        default=str(_DEFAULT_POLICY_PATH),
        help="مسیر فایل policy.json",
    )
    build_cmd.add_argument(
        "--min-coverage",
        type=float,
        default=None,
        help="حداقل نسبت پوشش (0-1 یا درصد؛ پیش‌فرض از policy)",
    )
    build_cmd.add_argument(
        "--policy-version",
        default=None,
        help="نسخه یا هش policy مورد انتظار برای تطبیق قبل از ساخت",
    )
    build_cmd.add_argument(
        "--manager-overrides",
        default=None,
        help="JSON object نگاشت manager→enabled برای اجرای جاری ماتریس",
    )
    build_cmd.add_argument(
        "--mentor-overrides",
        default=None,
        help="JSON object نگاشت mentor_id→enabled برای اجرای جاری ماتریس",
    )
    build_cmd.add_argument(
        "--use-v3-mentor-pipeline",
        action="store_true",
        help="استفاده از HeaderPipelineV3 برای کاننیکال‌سازی هدرهای پشتیبان",
    )

    refresh_cmd = sub.add_parser(
        "import-schools",
        help="ورود SchoolReport و Crosswalk به دیتابیس محلی به‌صورت مرجع",
    )
    refresh_cmd.add_argument("--school-report", required=True, help="مسیر فایل SchoolReport")
    refresh_cmd.add_argument("--crosswalk", required=True, help="مسیر فایل Crosswalk")
    _add_local_db_args(refresh_cmd)

    import_students_cmd = sub.add_parser(
        "import-students",
        help="ورود StudentReport و ذخیرهٔ کش دانش‌آموزان در SQLite",
    )
    import_students_cmd.add_argument(
        "--students",
        required=False,
        help="مسیر فایل StudentReport (Excel/CSV) یا استفاده از کش forms_entries",
    )
    import_students_cmd.add_argument(
        "--from-forms-cache",
        action="store_true",
        help="نصب کش دانش‌آموزان از جدول forms_entries بدون نیاز به فایل ورودی",
    )
    _add_local_db_args(import_students_cmd)

    import_mentors_cmd = sub.add_parser(
        "import-mentors",
        help="ورود Inspactor/MentorPool و ذخیرهٔ کش منتورها در SQLite",
    )
    import_mentors_cmd.add_argument(
        "--inspactor", required=True, help="مسیر فایل Inspactor"
    )
    import_mentors_cmd.add_argument(
        "--pool-type",
        choices=("inspactor", "matrix"),
        default="inspactor",
        help="نوع استخر منتورها برای ورود به کش (پیش‌فرض inspactor)",
    )
    import_mentors_cmd.add_argument(
        "--pool-sheet",
        required=False,
        help="نام شیت ورودی استخر (برای matrix باید 'matrix' باشد)",
    )
    _add_local_db_args(import_mentors_cmd)

    import_managers_cmd = sub.add_parser(
        "import-managers",
        help="ورود ManagerReport و ذخیرهٔ کش مدیران مراکز در SQLite (idempotent)",
    )
    import_managers_cmd.add_argument(
        "--manager-report",
        required=True,
        help="مسیر فایل ManagerReport (Excel) برای ثبت کش مراکز",
    )
    _add_local_db_args(import_managers_cmd)

    forms_cmd = sub.add_parser(
        "sync-forms",
        help="دریافت ورودی‌های فرم WordPress و ذخیره در کش forms_entries",
        description="همگام‌سازی فرم‌ها با امکان استفادهٔ offline از کش SQLite.",
    )
    forms_cmd.add_argument(
        "--since",
        required=False,
        help="(اختیاری) زمان شروع به‌صورت ISO8601 برای دریافت افزایشی",
    )
    forms_cmd.add_argument(
        "--cache-only",
        action="store_true",
        help="بدون دانلود؛ فقط محتویات کش forms_entries را بارگذاری و گزارش می‌کند",
    )
    forms_cmd.add_argument(
        "--policy",
        default=str(_DEFAULT_POLICY_PATH),
        help="مسیر فایل policy.json جهت تطبیق نسخهٔ Policy/SSoT",
    )
    _add_local_db_args(forms_cmd)

    alloc_cmd = sub.add_parser("allocate", help="تخصیص دانش‌آموزان به منتورها")
    alloc_cmd.add_argument(
        "--students",
        required=False,
        help="مسیر فایل دانش‌آموزان؛ در صورت عدم ارائه از کش SQLite خوانده می‌شود",
    )
    alloc_cmd.add_argument(
        "--pool",
        required=False,
        help="مسیر استخر منتورها؛ در صورت عدم ارائه از کش SQLite خوانده می‌شود",
    )
    alloc_cmd.add_argument(
        "--pool-type",
        choices=("matrix",),
        default="matrix",
        help="نوع استخر منتورها (تنها شیت 'matrix' مجاز است)",
    )
    alloc_cmd.add_argument(
        "--pool-sheet",
        required=False,
        help="نام شیت ورودی استخر (فقط 'matrix' مجاز است)",
    )
    alloc_cmd.add_argument("--output", required=True, help="مسیر Excel خروجی تخصیص")
    alloc_cmd.add_argument(
        "--capacity-column",
        default=None,
        help="نام ستون ظرفیت باقی‌مانده در استخر (پیش‌فرض از policy)",
    )
    alloc_cmd.add_argument(
        "--academic-year",
        type=int,
        required=False,
        help="سال تحصیلی شروع (مثلاً 1404)",
    )
    alloc_cmd.add_argument(
        "--prior-roster",
        default=None,
        help="مسیر روستر سال قبل برای بازیابی شمارنده",
    )
    alloc_cmd.add_argument(
        "--current-roster",
        default=None,
        help="مسیر روستر سال جاری برای ادامه شمارنده",
    )
    alloc_cmd.add_argument(
        "--policy",
        default=str(_DEFAULT_POLICY_PATH),
        help="مسیر فایل policy.json",
    )
    _add_center_management_args(alloc_cmd)
    alloc_cmd.add_argument(
        "--golestan-manager",
        default=None,
        help="(Legacy) نام مدیر مرکز گلستان (شناسه مرکز ۱)",
    )
    alloc_cmd.add_argument(
        "--sadra-manager",
        default=None,
        help="(Legacy) نام مدیر مرکز صدرا (شناسه مرکز ۲)",
    )
    alloc_cmd.add_argument(
        "--center-managers",
        default=None,
        help="نگاشت JSON مرکز→لیست مدیران برای override گروهی",
    )
    alloc_cmd.add_argument(
        "--mentor-overrides",
        default=None,
        help="JSON object نگاشت mentor_id→enabled برای اجرای جاری",
    )
    alloc_cmd.add_argument(
        "--audit",
        action="store_true",
        help="پس از تولید خروجی، ممیزی خودکار را اجرا کن",
    )
    alloc_cmd.add_argument(
        "--metrics",
        action="store_true",
        help="پس از اجرا، خلاصهٔ JSON ممیزی را چاپ کن",
    )
    alloc_cmd.add_argument(
        "--sabt-output",
        default=None,
        help="در صورت تعیین، خروجی ImportToSabt را در این مسیر بنویس",
    )
    alloc_cmd.add_argument(
        "--sabt-config",
        default=str(_DEFAULT_EXPORTER_CONFIG_PATH),
        help="مسیر فایل SmartAlloc Exporter Config",
    )
    alloc_cmd.add_argument(
        "--sabt-template",
        default=str(_DEFAULT_SABT_TEMPLATE_PATH),
        help="مسیر فایل قالب ImportToSabt",
    )
    alloc_cmd.add_argument(
        "--export-profile",
        choices=("basic", "sabt"),
        default="sabt",
        help="نوع خروجی شیت allocations (basic=ساختار قبلی، sabt=پروفایل 45 ستونی)",
    )
    alloc_cmd.add_argument(
        "--export-profile-path",
        default=str(_DEFAULT_ALLOC_PROFILE_PATH),
        help="مسیر فایل پروفایل Sabt (Sheet1) برای خروجی تخصیص",
    )
    _add_exporter_archive_args(alloc_cmd)
    alloc_cmd.add_argument(
        "--determinism-check",
        action="store_true",
        help="اجرای دوباره تخصیص برای تضمین دترمینیسم",
    )
    alloc_cmd.add_argument(
        "--counter-duplicate-strategy",
        choices=("prompt", "abort", "drop", "assign-new"),
        default="prompt",
        help="نحوهٔ مدیریت student_id تکراری: prompt=سوال تعاملی، drop=حذف، assign-new=شمارندهٔ جدید",
    )
    _add_local_db_args(alloc_cmd)

    preflight_cmd = sub.add_parser(
        "preflight-unknowns",
        aliases=["preflight_unknowns"],
        help="پیش‌بررسی داده‌های ناشناخته قبل از تخصیص",
    )
    preflight_cmd.add_argument(
        "--students",
        required=False,
        help="مسیر فایل دانش‌آموزان؛ در صورت عدم ارائه از کش SQLite خوانده می‌شود",
    )
    preflight_cmd.add_argument(
        "--pool",
        required=False,
        help="مسیر استخر منتورها؛ در صورت عدم ارائه از کش SQLite خوانده می‌شود",
    )
    preflight_cmd.add_argument(
        "--pool-type",
        choices=("matrix",),
        default="matrix",
        help="نوع استخر منتورها (تنها شیت 'matrix' مجاز است)",
    )
    preflight_cmd.add_argument(
        "--pool-sheet",
        required=False,
        help="نام شیت ورودی استخر (فقط 'matrix' مجاز است)",
    )
    preflight_cmd.add_argument(
        "--output",
        required=True,
        help="مسیر خروجی تخصیص یا پوشه خروجی برای ذخیرهٔ گزارش ناشناخته‌ها",
    )
    preflight_cmd.add_argument(
        "--policy",
        default=str(_DEFAULT_POLICY_PATH),
        help="مسیر فایل policy.json",
    )
    _add_center_management_args(preflight_cmd)
    _add_local_db_args(preflight_cmd)

    rule_cmd = sub.add_parser(
        "rule-engine",
        help="اجرای موتور قواعد روی ماتریس ساخته‌شده بدون استخر مجزا",
    )
    rule_cmd.add_argument("--matrix", required=True, help="مسیر فایل ماتریس")
    rule_cmd.add_argument("--students", required=True, help="مسیر فایل دانش‌آموزان")
    rule_cmd.add_argument("--output", required=True, help="مسیر خروجی تخصیص")
    rule_cmd.add_argument(
        "--capacity-column",
        default=None,
        help="نام ستون ظرفیت باقی‌مانده (پیش‌فرض policy)",
    )
    rule_cmd.add_argument(
        "--golestan-manager",
        default="شهدخت کشاورز",
        help="نام مدیر مرکز گلستان (شناسه مرکز ۱)",
    )
    rule_cmd.add_argument(
        "--sadra-manager",
        default="آیناز هوشمند",
        help="نام مدیر مرکز صدرا (شناسه مرکز ۲)",
    )
    rule_cmd.add_argument(
        "--center-priority",
        default="1,2,0",
        help="ترتیب پردازش مراکز هنگام اجرای موتور قواعد",
    )
    rule_cmd.add_argument(
        "--academic-year",
        type=int,
        required=False,
        help="سال تحصیلی شروع (مثلاً 1404)",
    )
    rule_cmd.add_argument(
        "--prior-roster",
        default=None,
        help="مسیر روستر سال قبل برای بازیابی شمارنده",
    )
    rule_cmd.add_argument(
        "--current-roster",
        default=None,
        help="مسیر روستر سال جاری برای ادامه شمارنده",
    )
    rule_cmd.add_argument(
        "--policy",
        default=str(_DEFAULT_POLICY_PATH),
        help="مسیر فایل policy.json",
    )
    rule_cmd.add_argument(
        "--mentor-overrides",
        default=None,
        help="JSON object نگاشت mentor_id→enabled برای اجرای جاری",
    )
    rule_cmd.add_argument(
        "--audit",
        action="store_true",
        help="پس از تولید خروجی، ممیزی خودکار را اجرا کن",
    )
    rule_cmd.add_argument(
        "--metrics",
        action="store_true",
        help="پس از اجرا، خلاصهٔ JSON ممیزی را چاپ کن",
    )
    rule_cmd.add_argument(
        "--determinism-check",
        action="store_true",
        help="اجرای دوباره تخصیص برای تضمین دترمینیسم",
    )
    rule_cmd.add_argument(
        "--sabt-output",
        default=None,
        help="در صورت تعیین، خروجی ImportToSabt را در این مسیر بنویس",
    )
    rule_cmd.add_argument(
        "--sabt-config",
        default=str(_DEFAULT_EXPORTER_CONFIG_PATH),
        help="مسیر فایل SmartAlloc Exporter Config",
    )
    rule_cmd.add_argument(
        "--sabt-template",
        default=str(_DEFAULT_SABT_TEMPLATE_PATH),
        help="مسیر فایل قالب ImportToSabt",
    )
    rule_cmd.add_argument(
        "--export-profile",
        choices=("basic", "sabt"),
        default="sabt",
        help="نوع خروجی شیت allocations هنگام اجرای rule-engine",
    )
    rule_cmd.add_argument(
        "--export-profile-path",
        default=str(_DEFAULT_ALLOC_PROFILE_PATH),
        help="مسیر فایل پروفایل Sabt برای خروجی rule-engine",
    )
    rule_cmd.add_argument(
        "--counter-duplicate-strategy",
        choices=("prompt", "abort", "drop", "assign-new"),
        default="prompt",
        help="نحوهٔ مدیریت student_id تکراری هنگام تولید شمارنده",
    )
    _add_local_db_args(rule_cmd)
    _add_exporter_archive_args(rule_cmd)

    archive_cmd = sub.add_parser(
        "exporter-archive",
        help="مدیریت Snapshot های خروجی ImportToSabt در SQLite",
    )
    archive_cmd.add_argument(
        "action",
        choices=("list", "compare"),
        help="عملیات روی بایگانی (لیست یا مقایسه)",
    )
    archive_cmd.add_argument(
        "--a",
        type=int,
        dest="snapshot_a",
        help="شناسه Snapshot مبدا برای مقایسه",
    )
    archive_cmd.add_argument(
        "--b",
        type=int,
        dest="snapshot_b",
        help="شناسه Snapshot مقصد برای مقایسه",
    )
    _add_local_db_args(archive_cmd)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    progress_factory: Callable[[], ProgressFn] | None = None,
    build_runner: Callable[[argparse.Namespace, PolicyConfig, ProgressFn], int] | None = None,
    allocate_runner: Callable[[argparse.Namespace, PolicyConfig, ProgressFn], int] | None = None,
    rule_engine_runner: Callable[[argparse.Namespace, PolicyConfig, ProgressFn], int] | None = None,
    ui_overrides: dict[str, Any] | None = None,
) -> int:
    """نقطهٔ ورود CLI؛ خروجی ۰ به معنای موفقیت است."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    args._raw_argv = list(argv) if argv is not None else sys.argv[1:]

    args._ui_overrides = ui_overrides or {}
    args._ui_mode = ui_overrides is not None
    args._user_settings = _resolve_user_settings(args._ui_overrides)

    if not hasattr(args, "policy"):
        args.policy = str(_DEFAULT_POLICY_PATH)

    policy_path = Path(args.policy)
    policy = load_policy(policy_path)

    progress = progress_factory() if progress_factory is not None else _default_progress

    try:
        if args.command == "build-matrix":
            runner = build_runner or _run_build_matrix
            return runner(args, policy, progress)

        if args.command == "import-schools":
            return _run_import_schools(args, policy, progress)

        if args.command == "import-students":
            db = _resolve_local_db(args)
            if db is None:
                raise ValueError("برای import-students باید --local-db مشخص شود.")
            if getattr(args, "from_forms_cache", False):
                _import_students_from_forms_cache(db=db, policy=policy)
                print("students cache imported from forms_entries")
            elif args.students:
                import_student_report_from_excel(Path(args.students), db=db, policy=policy)
                print("students cache imported")
            else:
                raise ValueError("یا --students بدهید یا --from-forms-cache را فعال کنید.")
            return 0

        if args.command == "import-mentors":
            db = _resolve_local_db(args)
            if db is None:
                raise ValueError("برای import-mentors باید --local-db مشخص شود.")
            pool_type_val = getattr(args, "pool_type", "inspactor") or "inspactor"
            pool_sheet = getattr(args, "pool_sheet", None)
            pool_path = Path(args.inspactor)
            if pool_type_val == "matrix":
                if pool_sheet and pool_sheet.lower() != "matrix":
                    raise SystemExit("pool-sheet باید 'matrix' باشد.")
                pool_sheet = pool_sheet or "matrix"
                resolved_pool_type = "matrix"
            elif pool_type_val == "inspactor":
                resolved_pool_type = "inspactor"
            else:
                raise SystemExit("pool-type باید 'inspactor' یا 'matrix' باشد.")
            resolved_pool_source = resolved_pool_type
            import_mentor_pool_from_excel(
                pool_path,
                db=db,
                policy=policy,
                pool_source=resolved_pool_source,
                pool_type=resolved_pool_type,
                pool_sheet=pool_sheet,
            )
            print("mentor pool cache imported")
            return 0

        if args.command == "import-managers":
            db = _resolve_local_db(args)
            if db is None:
                raise ValueError("برای import-managers باید --local-db مشخص شود.")
            report_path = Path(args.manager_report)
            if not report_path.exists():
                raise ValueError("فایل ManagerReport یافت نشد؛ مسیر ورودی را بررسی کنید.")
            import_managers_from_excel(report_path, db=db)
            print("managers cache imported")
            return 0

        if args.command == "exporter-archive":
            db = _resolve_local_db(args)
            if db is None:
                raise ValueError("برای exporter-archive باید --local-db مشخص شود.")
            return _run_exporter_archive(args, db=db, progress=progress)

        if args.command == "sync-forms":
            return _run_sync_forms(args, policy, progress)

        if args.command == "preflight-unknowns":
            return _run_preflight_unknowns(args, policy, progress)

        if args.command == "allocate":
            runner = allocate_runner or _run_allocate
            return runner(args, policy, progress)

        if args.command == "rule-engine":
            runner = rule_engine_runner or _run_rule_engine
            return runner(args, policy, progress)

        raise RuntimeError(f"Unsupported command: {args.command}")
    except JoinKeyValidationError as exc:
        if ui_overrides is not None:
            raise
        issues = exc.result.invalid_rows
        safe_print(f"❌ {exc}", file=sys.stderr)
        if not issues.empty:
            safe_print(issues.to_string(index=False), file=sys.stderr)
        return 2
    except ReferenceDataMissingError as exc:
        if ui_overrides is not None:
            raise
        safe_print(f"❌ {exc}", file=sys.stderr)
        return 2
    except (DatabasePreparationError, DatabaseCorruptError) as exc:
        if ui_overrides is not None:
            raise
        safe_print(f"❌ {exc}", file=sys.stderr)
        return 2
    except SchemaVersionMismatchError as exc:
        if ui_overrides is not None:
            raise
        safe_print(f"❌ نسخهٔ پایگاه داده ناسازگار است: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        if ui_overrides is not None:
            raise
        is_coverage_error = getattr(exc, "is_coverage_threshold_error", False)
        is_dedup_error = getattr(exc, "is_dedup_removed_threshold_error", False)
        is_duplicate_error = getattr(exc, "is_join_key_duplicate_threshold_error", False)
        is_school_lookup_error = getattr(exc, "is_school_lookup_threshold_error", False)
        if not (
            is_coverage_error or is_dedup_error or is_duplicate_error or is_school_lookup_error
        ):
            raise
        safe_print(f"❌ {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""خروجی تخصیص Sabt بر اساس پروفایل Policy-First."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

from app.core.allocation.engine import enrich_summary_with_history
from app.core.allocation.history_metrics import METRIC_COLUMNS, compute_history_metrics
from app.core.common.columns import CANON_EN_TO_FA, canonicalize_headers, ensure_series
from app.core.common.normalization import normalize_fa
from app.core.common.trace import JOIN_STAGE_SOURCE_KEYS
from app.core.common.types import CANONICAL_TRACE_ORDER
from app.core.pipeline import enrich_student_contacts
from app.core.policy_loader import PolicyConfig
from app.infra.excel.common import (
    attach_contact_columns,
    enforce_text_columns,
    identify_code_headers,
)
from app.infra.io_utils import write_xlsx_atomic

__all__ = [
    "AllocationExportColumn",
    "load_sabt_export_profile",
    "build_sabt_export_frame",
    "collect_trace_debug_sheets",
    "export_sabt_excel",
    "DEFAULT_SABT_PROFILE_PATH",
]


DEFAULT_SABT_PROFILE_PATH = Path("docs/Report (4).xlsx")
_PROFILE_SHEET_NAME = "Sheet1"
_HEADER_COLUMN = "عنوان ستون ها ورودی"
_VALUE_COLUMN = "مقدار برای مپ کردن از اکسل ورودی"
_ORDER_COLUMN = "اولویت و ترتیب در اکسل خروجی"
_SOURCE_COLUMN = "مقدار از کجا آورده شود"
_SOURCE_ALLOCATION = "خروجی برنامه بعد از تخصیص"
_SOURCE_STUDENT = "کپی کردن از اکسل ورودی"
_SOURCE_REMOVE = "حذف از اکسل خروجی"
_ALLOCATION_HEADER_MAP = {
    normalize_fa("پیدا کردن ردیف پشتیبان از فیلد 141"): "mentor_id",
    normalize_fa("کد ثبت نام0"): "student_id",
    normalize_fa("کپی کد جایگزین 39"): "mentor_alias_code",
}
_SPLIT_PATTERN = re.compile(r"[|،,/]+")
_ASCII_KEY_PATTERN = re.compile(r"[^0-9a-z]+")


def _clean_text(value: object) -> str:
    text = str(value).strip() if value is not None else ""
    if text.lower() == "nan":
        return ""
    return text


def _slugify(value: str) -> str:
    normalized = normalize_fa(value)
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", normalized).strip("_")
    return slug or "column"


def _normalize_lookup_key(value: str) -> str:
    normalized = normalize_fa(value)
    normalized = "".join(ch for ch in normalized.lower() if not ch.isspace())
    if normalized:
        return normalized
    ascii_fallback = _ASCII_KEY_PATTERN.sub("", str(value).strip().lower())
    return ascii_fallback


def _iter_mapping_candidates(value: str) -> Iterable[str]:
    if not value:
        return []
    parts = [_clean_text(value)]
    parts.extend(token.strip() for token in _SPLIT_PATTERN.split(value) if token.strip())
    return parts


@dataclass(frozen=True)
class AllocationExportColumn:
    """مدل ستونی خروجی Sabt با متادیتای Policy-First.

    مثال::

        >>> AllocationExportColumn(
        ...     key="mentor_id",
        ...     header="پیدا کردن ردیف پشتیبان از فیلد 141",
        ...     source_kind="allocation",
        ...     source_field="mentor_id",
        ...     literal_value=None,
        ...     order=1,
        ... )
    """

    key: str
    header: str
    source_kind: Literal["allocation", "student", "literal"]
    source_field: str | None
    literal_value: str | int | float | None
    order: int
    mapping_hint: str | None = None


def load_sabt_export_profile(
    path: Path = DEFAULT_SABT_PROFILE_PATH,
) -> list[AllocationExportColumn]:
    """خواندن Sheet1 و تبدیل به لیست ستون‌های موردنیاز Sabt."""

    profile_path = Path(path)
    if not profile_path.exists():
        raise FileNotFoundError(f"Sabt profile not found: {profile_path}")

    df = pd.read_excel(profile_path, sheet_name=_PROFILE_SHEET_NAME)
    try:
        idx_header = df.columns.get_loc(_HEADER_COLUMN)
        idx_value = df.columns.get_loc(_VALUE_COLUMN)
        idx_order = df.columns.get_loc(_ORDER_COLUMN)
        idx_source = df.columns.get_loc(_SOURCE_COLUMN)
    except KeyError as exc:  # pragma: no cover - محافظ در برابر تغییر پروفایل
        raise ValueError(f"Sabt profile missing expected column: {exc}") from exc
    numeric_orders = pd.to_numeric(df[_ORDER_COLUMN], errors="coerce")
    numeric_count = int(numeric_orders.notna().sum())
    records: list[AllocationExportColumn] = []

    for row in df.itertuples(index=False, name=None):
        header = _clean_text(row[idx_header])
        value_map = _clean_text(row[idx_value])
        source = _clean_text(row[idx_source])
        order_raw = row[idx_order]

        if not header:
            continue
        if source == _SOURCE_REMOVE:
            continue
        try:
            order_value = float(order_raw)
        except (TypeError, ValueError):
            continue
        if math.isnan(order_value):
            continue
        order = int(order_value)

        normalized_header = normalize_fa(header)
        key = _slugify(header)
        source_field: str | None = None
        literal_value: str | int | float | None = None
        resolved_source: Literal["allocation", "student", "literal"] = "student"

        if source == _SOURCE_ALLOCATION:
            resolved_source = "allocation"
            source_field = _ALLOCATION_HEADER_MAP.get(normalized_header)
            if source_field is None:
                raise ValueError(f"Allocation source field missing for header '{header}'")
        elif source == _SOURCE_STUDENT:
            resolved_source = "student"
            source_field = value_map or header
        else:
            resolved_source = "literal"
            literal_value = value_map or header

        records.append(
            AllocationExportColumn(
                key=source_field or key,
                header=header,
                source_kind=resolved_source,
                source_field=source_field,
                literal_value=literal_value,
                order=order,
                mapping_hint=value_map or header,
            )
        )

    records.sort(key=lambda col: col.order)

    if len(records) != numeric_count:
        raise ValueError("Sabt profile mismatch: numeric order rows do not equal exported columns")

    order_values = [column.order for column in records]
    if len(order_values) != len(set(order_values)):
        raise ValueError("Sabt profile contains duplicate order values")

    return records


def _resolve_student_column(
    column: AllocationExportColumn,
    lookup: dict[str, str],
) -> str | None:
    candidates = list(_iter_mapping_candidates(column.source_field or ""))
    if column.header not in candidates:
        candidates.append(column.header)
    for candidate in candidates:
        key = _normalize_lookup_key(candidate)
        if key in lookup:
            return lookup[key]
    return None


def _register_lookup_key(lookup: dict[str, str], label: str, column: str) -> None:
    key = _normalize_lookup_key(label)
    if key:
        lookup.setdefault(key, column)


def _build_students_lookup(df: pd.DataFrame) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for column in df.columns:
        label = str(column).strip()
        if not label:
            continue
        _register_lookup_key(lookup, label, column)
        persian_label = CANON_EN_TO_FA.get(label)
        if persian_label:
            _register_lookup_key(lookup, persian_label, column)
    return lookup


def _resolve_fallback_student_column(
    column: AllocationExportColumn, students: pd.DataFrame
) -> str | None:
    """یافتن ستون جایگزین برای مواردی مانند «وضعیت تحصیلی» زمانی که مپ اولیه پیدا نشد."""

    normalized_candidates = {
        _normalize_lookup_key(token) for token in _iter_mapping_candidates(column.header)
    }
    normalized_candidates.add(_normalize_lookup_key(column.source_field or column.header))
    for candidate in normalized_candidates:
        for col in students.columns:
            label = str(col)
            if _normalize_lookup_key(label) == candidate:
                return label
    if "student_educational_status" in students.columns:
        return "student_educational_status"
    return None


def _enrich_students_with_summary(
    students_en: pd.DataFrame, summary_df: pd.DataFrame | None
) -> pd.DataFrame:
    """ادغام فیلدهای هویتی از ``summary_df`` روی دیتافریم دانش‌آموزان."""

    if summary_df is None or summary_df.empty or "student_id" not in summary_df.columns:
        return students_en
    summary_en = canonicalize_headers(summary_df, header_mode="en")
    if "student_id" not in summary_en.columns:
        return students_en
    summary_en = summary_en.drop_duplicates("student_id", keep="first").copy()
    summary_indexed = summary_en.set_index("student_id", drop=False)
    students_indexed = students_en.set_index("student_id", drop=False)

    for column in (
        "student_educational_status",
        "student_registration_status",
        "student_national_code",
        "student_first_name",
        "student_last_name",
    ):
        if column in summary_indexed.columns:
            aligned = summary_indexed[column].reindex(students_indexed.index)
            base = (
                students_indexed[column]
                if column in students_indexed.columns
                else pd.Series(pd.NA, index=students_indexed.index)
            )
            students_indexed[column] = base.where(base.notna(), aligned)
    return students_indexed.reset_index(drop=True)


def build_sabt_export_frame(
    allocation_df: pd.DataFrame,
    students_df: pd.DataFrame,
    profile: Sequence[AllocationExportColumn],
    *,
    summary_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """ساخت دیتافریم Sabt با join روی student_id و مرتب‌سازی پایدار.

    ستون‌های تماس (شامل «وضعیت ثبت نام») از خروجی :func:`enrich_student_contacts`
    به دانش‌آموزان ضمیمه می‌شود تا وضعیت ثبت‌نام مستقیماً از SSOT خوانده شود.
    """

    if not profile:
        raise ValueError("Sabt export profile is empty")

    alloc_en = canonicalize_headers(allocation_df, header_mode="en").copy()
    students_contacts = enrich_student_contacts(students_df)
    students_en = canonicalize_headers(students_df, header_mode="en").copy()
    students_en = attach_contact_columns(students_en, students_contacts)
    if "student_id" in students_en.columns:
        students_en = _enrich_students_with_summary(students_en, summary_df)

    if "student_id" not in alloc_en.columns:
        raise KeyError("allocation_df must include 'student_id' column")
    if "student_id" not in students_en.columns:
        raise KeyError("students_df must include 'student_id' column")

    sort_columns = [column for column in ("student_id", "mentor_id") if column in alloc_en.columns]
    if sort_columns:
        alloc_en = alloc_en.sort_values(sort_columns, kind="mergesort")
    alloc_en = alloc_en.reset_index(drop=True)

    alloc_en["student_id"] = ensure_series(alloc_en["student_id"]).astype("string")
    students_en["student_id"] = ensure_series(students_en["student_id"]).astype("string")
    student_ids = ensure_series(alloc_en["student_id"]).copy()
    students_unique = students_en.drop_duplicates("student_id", keep="first")
    students_indexed = students_unique.set_index("student_id", drop=False)
    student_details = alloc_en[["student_id"]].merge(
        students_unique,
        on="student_id",
        how="left",
        validate="many_to_one",
    )
    lookup = _build_students_lookup(students_indexed)

    export_data: dict[str, pd.Series] = {}
    missing_columns: set[str] = set()

    for column in profile:
        if column.source_kind == "allocation":
            if not column.source_field or column.source_field not in alloc_en.columns:
                missing_columns.add(column.source_field or column.header)
                series = pd.Series(pd.NA, index=alloc_en.index, dtype="object")
            else:
                series = ensure_series(alloc_en[column.source_field]).reindex(alloc_en.index)
        elif column.source_kind == "student":
            resolved = _resolve_student_column(column, lookup)
            if resolved is None or resolved not in students_indexed.columns:
                fallback_column = _resolve_fallback_student_column(column, students_en)
                if fallback_column and fallback_column in students_indexed.columns:
                    resolved = fallback_column
            if resolved is None or resolved not in students_indexed.columns:
                missing_columns.add(column.source_field or column.header)
                series = pd.Series(pd.NA, index=alloc_en.index, dtype="object")
            else:
                series = ensure_series(student_details[resolved]).copy()
                series.index = alloc_en.index
        else:
            literal = column.literal_value
            series = pd.Series([literal] * len(alloc_en), index=alloc_en.index)
        export_data[column.header] = series

    student_id_series = ensure_series(student_ids).astype("string").reset_index(drop=True)
    export_df = pd.DataFrame(export_data)
    if "student_id" in export_df.columns:
        export_df["student_id"] = student_id_series
    else:
        export_df.insert(0, "student_id", student_id_series)
    code_headers = identify_code_headers(profile)
    export_df = enforce_text_columns(export_df, headers=code_headers)
    export_df.attrs["missing_student_columns"] = sorted(missing_columns)
    return export_df


def _empty_history_metrics_df() -> pd.DataFrame:
    return pd.DataFrame(columns=METRIC_COLUMNS)


def _build_history_metrics_sheet(
    summary_df: pd.DataFrame | None,
    *,
    students_df: pd.DataFrame | None,
    history_info_df: pd.DataFrame | None,
    policy: PolicyConfig | None,
) -> pd.DataFrame:
    if summary_df is None or summary_df.empty:
        return _empty_history_metrics_df()

    enriched_summary = summary_df
    if students_df is not None and policy is not None:
        enriched_summary = enrich_summary_with_history(
            summary_df,
            students_df=students_df,
            history_info_df=history_info_df,
            policy=policy,
        )
    try:
        return compute_history_metrics(enriched_summary)
    except KeyError:
        return _empty_history_metrics_df()


_JOIN_KEY_SOURCE_COLUMNS: dict[str, str] = dict(JOIN_STAGE_SOURCE_KEYS)

_DEFAULTED_SOURCES: set[str] = {"missing", "invalid", "defaulted_zero"}

_INFERRED_SOURCES: dict[str, set[str]] = {
    "center": {"manager_exact", "manager_substring", "manager_wildcard"},
}


def _join_key_stage_label(stage: str, policy: PolicyConfig | None) -> str:
    if policy is None:
        return stage
    if stage == "school":
        try:
            return policy.columns.school_code
        except AttributeError:
            return stage
    try:
        return policy.stage_column(stage)
    except KeyError:
        return stage


def _build_join_key_provenance_summary(
    summary_df: pd.DataFrame,
    *,
    policy: PolicyConfig | None,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    total_count = int(summary_df.shape[0])
    for stage, source_column in _JOIN_KEY_SOURCE_COLUMNS.items():
        inferred = 0
        defaulted = 0
        if source_column in summary_df.columns:
            series = summary_df[source_column].astype("string").fillna("")
            inferred = int(series.isin(_INFERRED_SOURCES.get(stage, set())).sum())
            defaulted = int(series.isin(_DEFAULTED_SOURCES).sum())
        rows.append(
            {
                "join_key_stage": stage,
                "join_key_column": _join_key_stage_label(stage, policy),
                "inferred_count": inferred,
                "defaulted_count": defaulted,
                "total_count": total_count,
            }
        )
    return pd.DataFrame(rows)


def _trace_count(entry: object) -> int | None:
    if not isinstance(entry, Mapping):
        return None
    value = entry.get("rows")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_eligibility_trace_sheet(
    logs_df: pd.DataFrame | None,
    *,
    policy: PolicyConfig | None,
) -> pd.DataFrame:
    stage_order = tuple(policy.trace_stage_names) if policy is not None else CANONICAL_TRACE_ORDER
    columns = [
        "student_id",
        "pool_built_size",
        "pool_size_before_bucket",
        "bucket_key",
        "bucket_size",
        "bucket_skip_reason",
        "bucket_key_variants",
        "bucket_sizes",
        "initial_candidates",
        "bucketed_candidates",
        "eligible_candidates",
        "preferred_count",
        *[f"stage_{stage}_count" for stage in stage_order],
    ]
    if logs_df is None or logs_df.empty:
        return pd.DataFrame(columns=columns)

    logs_en = canonicalize_headers(logs_df, header_mode="en").copy()
    if "student_id" not in logs_en.columns or "eligibility_trace" not in logs_en.columns:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, object]] = []
    for _, row in logs_en.iterrows():
        trace = row.get("eligibility_trace")
        stage_counts: Mapping[str, object] = {}
        bucket_trace: Mapping[str, object] = {}
        if isinstance(trace, Mapping):
            stage_counts_raw = trace.get("stage_counts", {})
            if isinstance(stage_counts_raw, Mapping):
                stage_counts = stage_counts_raw
            initial = _trace_count(trace.get("initial"))
            bucketed = _trace_count(trace.get("bucketed"))
            eligible = _trace_count(trace.get("eligible"))
            preferred = trace.get("preferred_count")
            bucket_trace_raw = trace.get("bucket_trace", {})
            if isinstance(bucket_trace_raw, Mapping):
                bucket_trace = bucket_trace_raw
        else:
            initial = None
            bucketed = None
            eligible = None
            preferred = None

        record: dict[str, object] = {
            "student_id": row.get("student_id"),
            "pool_built_size": bucket_trace.get("pool_built_size"),
            "pool_size_before_bucket": bucket_trace.get("pool_size_before_bucket"),
            "bucket_key": bucket_trace.get("bucket_key"),
            "bucket_size": bucket_trace.get("bucket_size"),
            "bucket_skip_reason": bucket_trace.get("bucket_skip_reason"),
            "bucket_key_variants": bucket_trace.get("bucket_key_variants"),
            "bucket_sizes": bucket_trace.get("bucket_sizes"),
            "initial_candidates": initial,
            "bucketed_candidates": bucketed,
            "eligible_candidates": eligible,
            "preferred_count": preferred,
        }
        for stage in stage_order:
            value = stage_counts.get(stage)
            try:
                record[f"stage_{stage}_count"] = int(value) if value is not None else None
            except (TypeError, ValueError):
                record[f"stage_{stage}_count"] = None
        rows.append(record)

    return pd.DataFrame(rows, columns=columns)


def _build_pipeline_trace_sheet(trace_payload: object) -> pd.DataFrame:
    if not isinstance(trace_payload, Sequence):
        return pd.DataFrame(columns=["stage", "rows", "columns", "fingerprint"])

    rows: list[dict[str, object]] = []
    for entry in trace_payload:
        if not isinstance(entry, Mapping):
            continue
        rows.append(
            {
                "stage": entry.get("stage"),
                "rows": entry.get("rows"),
                "columns": entry.get("columns"),
                "fingerprint": entry.get("fingerprint"),
            }
        )
    if not rows:
        return pd.DataFrame(columns=["stage", "rows", "columns", "fingerprint"])
    return pd.DataFrame(rows)


def _build_trace_ladder_sheet(
    trace_df: pd.DataFrame,
    *,
    logs_df: pd.DataFrame | None,
) -> pd.DataFrame:
    bucket_columns = [
        "pool_built_size",
        "pool_size_before_bucket",
        "bucket_key",
        "bucket_size",
        "bucket_skip_reason",
        "bucket_key_variants",
        "bucket_sizes",
    ]
    trace_ladder = trace_df.copy()
    if trace_ladder.empty:
        return trace_ladder
    if "student_id" not in trace_ladder.columns:
        for column in bucket_columns:
            if column not in trace_ladder.columns:
                trace_ladder[column] = None
        return trace_ladder
    if logs_df is None or logs_df.empty:
        for column in bucket_columns:
            if column not in trace_ladder.columns:
                trace_ladder[column] = None
        return trace_ladder

    logs_en = canonicalize_headers(logs_df, header_mode="en").copy()
    if "student_id" not in logs_en.columns or "eligibility_trace" not in logs_en.columns:
        for column in bucket_columns:
            if column not in trace_ladder.columns:
                trace_ladder[column] = None
        return trace_ladder

    bucket_records: list[dict[str, object]] = []
    for _, row in logs_en.iterrows():
        trace = row.get("eligibility_trace")
        if not isinstance(trace, Mapping):
            continue
        bucket_trace_raw = trace.get("bucket_trace", {})
        if not isinstance(bucket_trace_raw, Mapping):
            continue
        bucket_records.append(
            {
                "student_id": row.get("student_id"),
                "pool_built_size": bucket_trace_raw.get("pool_built_size"),
                "pool_size_before_bucket": bucket_trace_raw.get("pool_size_before_bucket"),
                "bucket_key": bucket_trace_raw.get("bucket_key"),
                "bucket_size": bucket_trace_raw.get("bucket_size"),
                "bucket_skip_reason": bucket_trace_raw.get("bucket_skip_reason"),
                "bucket_key_variants": bucket_trace_raw.get("bucket_key_variants"),
                "bucket_sizes": bucket_trace_raw.get("bucket_sizes"),
            }
        )

    if not bucket_records:
        for column in bucket_columns:
            if column not in trace_ladder.columns:
                trace_ladder[column] = None
        return trace_ladder

    bucket_df = pd.DataFrame(bucket_records)
    if "student_id" in bucket_df.columns:
        bucket_df = bucket_df.drop_duplicates(subset=["student_id"], keep="last")
    trace_ladder = trace_ladder.merge(bucket_df, on="student_id", how="left")
    return trace_ladder


def collect_trace_debug_sheets(
    trace_df: pd.DataFrame | None,
    *,
    logs_df: pd.DataFrame | None = None,
    students_df: pd.DataFrame | None = None,
    history_info_df: pd.DataFrame | None = None,
    policy: PolicyConfig | None = None,
    summary_df: pd.DataFrame | None = None,
    unallocated_summary: pd.DataFrame | None = None,
    policy_violations: pd.DataFrame | None = None,
    final_status_counts: pd.Series | None = None,
    pool_trace: object | None = None,
    enable_standard_debug_sheets: bool = True,
    enable_mentor_trace_debug: bool = False,
    enable_history_metrics: bool = True,
) -> dict[str, pd.DataFrame]:
    """ساخت شیت‌های تشخیصی از تریس برای خروجی Excel بدون تغییر رفتار اصلی.

    اگر ``summary_df``، ``unallocated_summary`` یا ``policy_violations`` داده شوند،
    آن‌ها را در یک دیکشنری با کلیدهای ایمن برمی‌گرداند تا توسط
    :func:`write_xlsx_atomic` روی شیت‌های مجزا (summary_df، unallocated_summary،
    policy_violations، FinalStatus_counts) نوشته شوند.
    زمانی که ``students_df``، ``history_info_df`` و ``policy`` مهیا باشند، این تابع
    خلاصهٔ تاریخچه را با :func:`enrich_summary_with_history` تکمیل کرده و شیت
    «HistoryMetrics» را با استفاده از :func:`compute_history_metrics` تولید می‌کند.
    در صورت فقدان دادهٔ تاریخچه، یک شیت خالی با سربرگ‌های استاندارد بازگردانده
    می‌شود تا مسیر تشخیصی پایدار بماند.
    """

    if trace_df is None:
        return {}
    if not enable_standard_debug_sheets and not enable_mentor_trace_debug:
        return {}

    sheets: dict[str, pd.DataFrame] = {}
    history_metrics_df = _empty_history_metrics_df()
    if enable_standard_debug_sheets:
        if isinstance(summary_df, pd.DataFrame) and not summary_df.empty:
            sheets["summary_df"] = summary_df.copy()
            value_counts = final_status_counts
            if isinstance(value_counts, pd.Series):
                counts_df = value_counts.reset_index()
                counts_df.columns = ["final_status", "count"]
                sheets["FinalStatus_counts"] = counts_df
            if enable_history_metrics:
                history_metrics_df = _build_history_metrics_sheet(
                    summary_df,
                    students_df=students_df,
                    history_info_df=history_info_df,
                    policy=policy,
                )
            sheets["JoinKeyProvenance_counts"] = _build_join_key_provenance_summary(
                summary_df,
                policy=policy,
            )

        if isinstance(unallocated_summary, pd.DataFrame) and not unallocated_summary.empty:
            sheets["unallocated_summary"] = unallocated_summary.copy()

        if isinstance(policy_violations, pd.DataFrame) and not policy_violations.empty:
            sheets["policy_violations"] = policy_violations.copy()

        sheets["HistoryMetrics"] = history_metrics_df

    if enable_mentor_trace_debug:
        sheets["EligibilityTrace"] = _build_eligibility_trace_sheet(logs_df, policy=policy)
        sheets["TraceLadder"] = _build_trace_ladder_sheet(trace_df, logs_df=logs_df)
        if pool_trace is not None:
            sheets["MentorPipelineTrace"] = _build_pipeline_trace_sheet(pool_trace)

    return sheets


def export_sabt_excel(
    allocation_df: pd.DataFrame,
    students_df: pd.DataFrame,
    output_path: Path,
    profile_path: Path | None = None,
    *,
    sheet_name: str = "Sabt",
    extra_sheets: Mapping[str, pd.DataFrame] | None = None,
    summary_df: pd.DataFrame | None = None,
) -> Path:
    """نوشتن خروجی Sabt در فایل Excel مستقل با ساختار پایدار."""

    profile = load_sabt_export_profile(profile_path or DEFAULT_SABT_PROFILE_PATH)
    export_df = build_sabt_export_frame(allocation_df, students_df, profile, summary_df=summary_df)
    sheets: dict[str, pd.DataFrame] = {sheet_name: export_df}
    if extra_sheets:
        sheets.update(extra_sheets)
    write_xlsx_atomic(
        sheets,
        output_path,
        header_mode=None,
        sheet_header_modes={sheet_name: None},
        sheet_prepare_modes={sheet_name: "raw"},
    )
    return output_path

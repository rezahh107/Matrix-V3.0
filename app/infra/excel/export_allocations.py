"""خروجی تخصیص Sabt بر اساس پروفایل Policy-First."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

from app.core.allocation.engine import enrich_summary_with_history
from app.core.allocation.history_metrics import METRIC_COLUMNS, compute_history_metrics
from app.core.common.columns import ensure_series
from app.core.common.isin_guard import isin_mask
from app.core.common.normalization import normalize_fa
from app.core.common.trace import JOIN_STAGE_SOURCE_KEYS
from app.core.common.types import CANONICAL_TRACE_ORDER
from app.core.pipeline import enrich_student_contacts
from app.core.policy_loader import PolicyConfig
from app.core.qa.invariants import QaRuleResult, QaViolation
from app.infra.common.header_pipeline_v3 import HeaderPipelineV3
from app.infra.excel.common import (
    attach_contact_columns,
    enforce_text_columns,
    identify_code_headers,
)
from app.infra.io_utils import write_xlsx_atomic
from app.infra.mentors.pipeline_v3 import build_global_prefilter_trace_entry
from app.infra.reference_mentors_repository import _POOL_QA_PAYLOAD_ATTR

__all__ = [
    "AllocationExportColumn",
    "load_sabt_export_profile",
    "build_sabt_export_frame",
    "collect_trace_debug_sheets",
    "export_sabt_excel",
    "DEFAULT_SABT_PROFILE_PATH",
    "ProfileMappingIssue",
    "build_profile_mapping_rule_result",
]


SABT_PROFILE_RULE_ID = "QA_RULE_SABT_PROFILE_01"


DEFAULT_SABT_PROFILE_PATH = Path("docs/Report (4).xlsx")
_HEKMAT_REGISTRATION_STATUS = 3
_EMPTY_LANDLINE_PLACEHOLDER = "00000000000"
_POLICY_EMPTY_SENTINEL_FA = "خالی"
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
_ASCII_KEY_PATTERN = re.compile(r"[^0-9a-z]+")


@dataclass(frozen=True)
class ProfileMappingIssue:
    """Structured issue for unresolved SABT export profile mappings."""

    output_column_name: str
    referenced_source_field: str
    dataset_frame_expected: Literal["students", "allocations"]
    profile_path: str | Path | None = None
    mapping_hint: str | None = None


def _resolve_headers(df: pd.DataFrame, source: str) -> pd.DataFrame:
    pipeline = HeaderPipelineV3()
    return pipeline.resolve(df, source=source).resolved_df


def _clean_text(value: object) -> str:
    text = str(value).strip() if value is not None else ""
    if text.lower() == "nan":
        return ""
    return text


def _slugify(value: str) -> str:
    normalized = normalize_fa(value)
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", normalized).strip("_")
    return slug or "column"


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
    profile_path: Path | None = None
    profile_row: int | None = None


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

    for row_number, row in enumerate(df.itertuples(index=False, name=None), start=2):
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
                profile_path=str(profile_path),
                profile_row=row_number,
            )
        )

    records.sort(key=lambda col: col.order)

    if len(records) != numeric_count:
        raise ValueError("Sabt profile mismatch: numeric order rows do not equal exported columns")

    order_values = [column.order for column in records]
    if len(order_values) != len(set(order_values)):
        raise ValueError("Sabt profile contains duplicate order values")

    return records


def _enrich_students_with_summary(
    students: pd.DataFrame,
    summary_df: pd.DataFrame | None,
    *,
    pipeline: HeaderPipelineV3,
) -> pd.DataFrame:
    """ادغام فیلدهای هویتی از ``summary_df`` روی دیتافریم دانش‌آموزان."""

    if summary_df is None or summary_df.empty:
        return students
    summary_resolved = pipeline.resolve(summary_df, source="student").resolved_df
    if "student_id" not in summary_resolved.columns:
        return students
    summary_resolved = summary_resolved.drop_duplicates("student_id", keep="first").copy()
    summary_indexed = summary_resolved.set_index("student_id", drop=False)
    students_indexed = students.set_index("student_id", drop=False)

    for column in (
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
    profile_path: Path | None = None,
) -> pd.DataFrame:
    """ساخت دیتافریم Sabt با join روی student_id و مرتب‌سازی پایدار.

    ستون‌های تماس (شامل «وضعیت ثبت نام») از خروجی :func:`enrich_student_contacts`
    به دانش‌آموزان ضمیمه می‌شود تا وضعیت ثبت‌نام مستقیماً از SSOT خوانده شود.
    """

    if not profile:
        raise ValueError("Sabt export profile is empty")

    pipeline = HeaderPipelineV3()

    profile_issues: list[ProfileMappingIssue] = []
    profile_path_str = str(profile_path) if profile_path else None

    def _record_issue(
        *,
        column: AllocationExportColumn,
        requested_field: str,
        dataset: Literal["students", "allocations"],
    ) -> None:
        profile_issues.append(
            ProfileMappingIssue(
                output_column_name=column.header,
                referenced_source_field=requested_field,
                dataset_frame_expected=dataset,
                profile_path=profile_path_str,
                mapping_hint=column.mapping_hint,
            )
        )

    alloc_resolved = pipeline.resolve(allocation_df, source="allocation").require_can_continue(
        path="allocation_df", reason_fa="هدرهای تخصیص برای Sabt نامعتبر است"
    )
    students_contacts = enrich_student_contacts(students_df)
    students_with_contacts = attach_contact_columns(students_df.copy(), students_contacts)
    students_resolved = pipeline.resolve(
        students_with_contacts, source="student"
    ).require_can_continue(path="students_df", reason_fa="هدرهای دانش‌آموز برای Sabt نامعتبر است")
    if "student_id" in students_resolved.columns:
        students_resolved = _enrich_students_with_summary(
            students_resolved, summary_df, pipeline=pipeline
        )

    if alloc_resolved.empty:
        index = alloc_resolved.index
        export_data: dict[str, pd.Series] = {}
        missing_columns: set[str] = set()

        for column in profile:
            if column.source_kind == "allocation":
                requested_field = column.source_field or column.header
                if isinstance(requested_field, str) and requested_field.strip() == _POLICY_EMPTY_SENTINEL_FA:
                    series = pd.Series(pd.NA, index=index, dtype="object")
                    export_data[column.header] = series
                    continue
                canonical = pipeline.resolve_field(requested_field, "allocation")
                if canonical is None:
                    missing_columns.add(requested_field)
                    _record_issue(
                        column=column,
                        requested_field=requested_field,
                        dataset="allocations",
                    )
                elif canonical not in alloc_resolved.columns:
                    missing_columns.add(requested_field)
                series = pd.Series(pd.NA, index=index, dtype="object")
            elif column.source_kind == "student":
                requested_field = column.source_field or column.header
                if isinstance(requested_field, str) and requested_field.strip() == _POLICY_EMPTY_SENTINEL_FA:
                    series = pd.Series(pd.NA, index=index, dtype="object")
                    export_data[column.header] = series
                    continue
                canonical = pipeline.resolve_field(requested_field, "student")
                if canonical is None:
                    missing_columns.add(requested_field)
                    _record_issue(
                        column=column,
                        requested_field=requested_field,
                        dataset="students",
                    )
                elif canonical not in students_resolved.columns:
                    missing_columns.add(requested_field)
                series = pd.Series(pd.NA, index=index, dtype="object")
            else:
                literal = column.literal_value
                series = pd.Series([literal] * len(index), index=index)
            export_data[column.header] = series

        export_df = pd.DataFrame(export_data, index=index)
        if "student_id" in export_df.columns:
            export_df["student_id"] = pd.Series(dtype="string", index=index)
        else:
            export_df.insert(0, "student_id", pd.Series(dtype="string", index=index))
        code_headers = identify_code_headers(profile)
        export_df = enforce_text_columns(export_df, headers=code_headers)
        export_df.attrs["missing_student_columns"] = sorted(missing_columns)
        export_df.attrs["profile_mapping_issues"] = profile_issues
        return export_df

    if "student_id" not in alloc_resolved.columns:
        raise KeyError("allocation_df must include 'student_id' column")
    if "student_id" not in students_resolved.columns:
        raise KeyError("students_df must include 'student_id' column")
    if "__source_index__" not in alloc_resolved.columns:
        raise KeyError("allocation_df must include '__source_index__' column")
    if "__source_index__" not in students_resolved.columns:
        raise KeyError("students_df must include '__source_index__' column")

    alloc_source_index = ensure_series(alloc_resolved["__source_index__"])
    students_source_index = ensure_series(students_resolved["__source_index__"])
    if alloc_source_index.isna().any():
        raise ValueError("allocation_df has null __source_index__ values")
    if students_source_index.isna().any():
        raise ValueError("students_df has null __source_index__ values")
    if alloc_source_index.duplicated().any():
        raise ValueError("allocation_df __source_index__ values must be unique")
    if students_source_index.duplicated().any():
        raise ValueError("students_df __source_index__ values must be unique")

    sort_columns = [column for column in ("student_id", "mentor_id") if column in alloc_resolved.columns]
    if sort_columns:
        alloc_resolved = alloc_resolved.sort_values(sort_columns, kind="mergesort")
    alloc_resolved = alloc_resolved.reset_index(drop=True)

    overlapping_columns = [
        col
        for col in students_resolved.columns
        if col in alloc_resolved.columns and col != "__source_index__"
    ]
    students_for_merge = students_resolved.drop(columns=overlapping_columns)

    merged = pd.merge(
        alloc_resolved,
        students_for_merge,
        on="__source_index__",
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    unmatched = merged.loc[merged["_merge"] != "both", ["student_id", "__source_index__"]]
    if not unmatched.empty:
        sample = unmatched.head(5).to_dict("records")
        raise ValueError(
            "Unmatched student rows after lineage join on __source_index__; sample="
            f"{sample}"
        )
    merged = merged.drop(columns=["_merge"])

    merged = merged.reset_index(drop=True)
    alloc_resolved = merged
    students_resolved = merged
    student_ids = ensure_series(alloc_resolved["student_id"]).copy()

    export_data: dict[str, pd.Series] = {}
    missing_columns: set[str] = set()

    landline_headers: list[str] = []

    for column in profile:
        if column.source_kind == "allocation":
            requested_field = column.source_field or column.header
            if isinstance(requested_field, str) and requested_field.strip() == _POLICY_EMPTY_SENTINEL_FA:
                series = pd.Series(pd.NA, index=alloc_resolved.index, dtype="object")
                export_data[column.header] = series
                continue
            canonical = pipeline.resolve_field(requested_field, "allocation")
            if canonical is None:
                missing_columns.add(requested_field)
                _record_issue(
                    column=column,
                    requested_field=requested_field,
                    dataset="allocations",
                )
                series = pd.Series(pd.NA, index=alloc_resolved.index, dtype="object")
            elif canonical not in alloc_resolved.columns:
                missing_columns.add(requested_field)
                series = pd.Series(pd.NA, index=alloc_resolved.index, dtype="object")
            else:
                series = ensure_series(alloc_resolved[canonical]).reindex(alloc_resolved.index)
        elif column.source_kind == "student":
            requested_field = column.source_field or column.header
            if isinstance(requested_field, str) and requested_field.strip() == _POLICY_EMPTY_SENTINEL_FA:
                series = pd.Series(pd.NA, index=alloc_resolved.index, dtype="object")
                export_data[column.header] = series
                continue
            canonical = pipeline.resolve_field(requested_field, "student")
            if canonical is None:
                missing_columns.add(requested_field)
                _record_issue(
                    column=column,
                    requested_field=requested_field,
                    dataset="students",
                )
                series = pd.Series(pd.NA, index=alloc_resolved.index, dtype="object")
            elif canonical not in students_resolved.columns:
                missing_columns.add(requested_field)
                series = pd.Series(pd.NA, index=alloc_resolved.index, dtype="object")
            else:
                series = ensure_series(students_resolved[canonical]).copy()
                series.index = alloc_resolved.index
                if canonical == "student_landline":
                    landline_headers.append(column.header)
        else:
            literal = column.literal_value
            series = pd.Series([literal] * len(alloc_resolved), index=alloc_resolved.index)
        export_data[column.header] = series

    if landline_headers:
        if "student_registration_status" not in students_resolved.columns:
            raise KeyError(
                "student_registration_status is required when exporting student_landline"
            )
        registration_status = ensure_series(
            students_resolved["student_registration_status"]
        ).astype("Int64")
        registration_status.index = alloc_resolved.index
        for header in landline_headers:
            landline_series = ensure_series(export_data[header]).astype("string")
            empty_mask = landline_series.astype("string").str.strip().eq("") | landline_series.isna()
            needs_fill = (registration_status == _HEKMAT_REGISTRATION_STATUS) & empty_mask
            if needs_fill.any():
                landline_series = landline_series.mask(
                    needs_fill, _EMPTY_LANDLINE_PLACEHOLDER
                )
            export_data[header] = landline_series

    student_id_series = ensure_series(student_ids).astype("string").reset_index(drop=True)
    export_df = pd.DataFrame(export_data)
    if "student_id" in export_df.columns:
        export_df["student_id"] = student_id_series
    else:
        export_df.insert(0, "student_id", student_id_series)
    code_headers = identify_code_headers(profile)
    export_df = enforce_text_columns(export_df, headers=code_headers)
    export_df.attrs["missing_student_columns"] = sorted(missing_columns)
    export_df.attrs["profile_mapping_issues"] = profile_issues
    return export_df


def build_profile_mapping_rule_result(
    issues: Sequence[ProfileMappingIssue],
) -> QaRuleResult | None:
    """Convert SABT profile mapping issues into a QA rule result."""

    if not issues:
        return None

    violations = []
    for issue in issues:
        message = (
            "SABT export profile references an unknown source field: "
            f"output={issue.output_column_name!r} source={issue.referenced_source_field!r}"
        )
        details: dict[str, object] = {
            "output_column_name": issue.output_column_name,
            "referenced_source_field": issue.referenced_source_field,
            "dataset_frame_expected": issue.dataset_frame_expected,
            "suggested_next_action": "fix profile mapping to exact canonical field name",
        }
        if issue.profile_path:
            details["profile_path"] = issue.profile_path
        if issue.mapping_hint:
            details["mapping_hint"] = issue.mapping_hint
        violations.append(
            QaViolation(
                rule_id=SABT_PROFILE_RULE_ID,
                level="error",
                message=message,
                details=details,
            )
        )

    return QaRuleResult(rule_id=SABT_PROFILE_RULE_ID, passed=True, violations=violations)


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
            inferred = int(
                isin_mask(
                    series,
                    _INFERRED_SOURCES.get(stage, set()),
                    name="inferred_sources",
                ).sum()
            )
            defaulted = int(
                isin_mask(series, _DEFAULTED_SOURCES, name="defaulted_sources").sum()
            )
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
    alias_metadata = _trace_alias_metadata(policy)
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
        *alias_metadata.keys(),
        *[f"stage_{stage}_count" for stage in stage_order],
    ]
    if logs_df is None or logs_df.empty:
        return pd.DataFrame(columns=columns)

    logs_en = _resolve_headers(logs_df, source="report")
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
            **alias_metadata,
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
        return pd.DataFrame(
            columns=[
                "stage",
                "rows",
                "columns",
                "fingerprint",
                "raw_count",
                "predicate_summary",
                "after_count",
                "profile_rows",
                "unique_mentor_ids",
                "multi_profile_mentor_count",
                "multi_profile_ratio",
                "predicate_expr",
                "predicate_source",
                "prefilter_removed",
            ]
        )

    columns = [
        "stage",
        "rows",
        "columns",
        "fingerprint",
        "raw_count",
        "predicate_summary",
        "after_count",
        "profile_rows",
        "unique_mentor_ids",
        "multi_profile_mentor_count",
        "multi_profile_ratio",
        "predicate_expr",
        "predicate_source",
        "prefilter_removed",
    ]
    rows: list[dict[str, object]] = []
    for entry in trace_payload:
        if not isinstance(entry, Mapping):
            continue
        rows.append({column: entry.get(column) for column in columns})
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns)


def _build_trace_ladder_sheet(
    trace_df: pd.DataFrame,
    *,
    logs_df: pd.DataFrame | None,
    policy: PolicyConfig | None,
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
    alias_metadata = _trace_alias_metadata(policy)
    if trace_ladder.empty:
        return trace_ladder
    if "student_id" not in trace_ladder.columns:
        for column in bucket_columns:
            if column not in trace_ladder.columns:
                trace_ladder[column] = None
        for key, value in alias_metadata.items():
            trace_ladder[key] = value
        return trace_ladder
    if logs_df is None or logs_df.empty:
        for column in bucket_columns:
            if column not in trace_ladder.columns:
                trace_ladder[column] = None
        for key, value in alias_metadata.items():
            trace_ladder[key] = value
        return trace_ladder

    logs_en = _resolve_headers(logs_df, source="report")
    if "student_id" not in logs_en.columns or "eligibility_trace" not in logs_en.columns:
        for column in bucket_columns:
            if column not in trace_ladder.columns:
                trace_ladder[column] = None
        for key, value in alias_metadata.items():
            trace_ladder[key] = value
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
        for key, value in alias_metadata.items():
            trace_ladder[key] = value
        return trace_ladder

    bucket_df = pd.DataFrame(bucket_records)
    if "student_id" in bucket_df.columns:
        bucket_df = bucket_df.drop_duplicates(subset=["student_id"], keep="last")
    trace_ladder = trace_ladder.merge(bucket_df, on="student_id", how="left")
    for key, value in alias_metadata.items():
        trace_ladder[key] = value
    return trace_ladder


def _trace_alias_metadata(policy: PolicyConfig | None) -> dict[str, object]:
    if policy is None:
        return {
            "stage_type_alias_of": None,
            "stage_type_source_col": None,
            "stage_group_source_col": None,
        }
    type_column = policy.stage_column("type")
    group_column = policy.stage_column("group")
    if type_column != group_column:
        return {
            "stage_type_alias_of": None,
            "stage_type_source_col": type_column,
            "stage_group_source_col": group_column,
        }
    return {
        "stage_type_alias_of": "group",
        "stage_type_source_col": type_column,
        "stage_group_source_col": group_column,
    }


def _build_bucket_trace_sheet(logs_df: pd.DataFrame | None) -> pd.DataFrame:
    columns = [
        "student_id",
        "pool_built_size",
        "pool_size_before_bucket",
        "bucket_key",
        "bucket_size",
        "bucket_skip_reason",
        "bucket_key_variants",
        "bucket_sizes",
    ]
    if logs_df is None or logs_df.empty:
        return pd.DataFrame(columns=columns)
    logs_en = _resolve_headers(logs_df, source="report")
    if "student_id" not in logs_en.columns or "eligibility_trace" not in logs_en.columns:
        return pd.DataFrame(columns=columns)
    records: list[dict[str, object]] = []
    for _, row in logs_en.iterrows():
        trace = row.get("eligibility_trace")
        if not isinstance(trace, Mapping):
            continue
        bucket_trace = trace.get("bucket_trace")
        if not isinstance(bucket_trace, Mapping):
            continue
        records.append(
            {
                "student_id": row.get("student_id"),
                "pool_built_size": bucket_trace.get("pool_built_size"),
                "pool_size_before_bucket": bucket_trace.get("pool_size_before_bucket"),
                "bucket_key": bucket_trace.get("bucket_key"),
                "bucket_size": bucket_trace.get("bucket_size"),
                "bucket_skip_reason": bucket_trace.get("bucket_skip_reason"),
                "bucket_key_variants": bucket_trace.get("bucket_key_variants"),
                "bucket_sizes": bucket_trace.get("bucket_sizes"),
            }
        )
    if not records:
        return pd.DataFrame(columns=columns)
    bucket_df = pd.DataFrame(records)
    if "student_id" in bucket_df.columns:
        bucket_df = bucket_df.drop_duplicates(subset=["student_id"], keep="last")
    return bucket_df


def _build_pool_governance_trace_sheet(pool_df: pd.DataFrame | None) -> pd.DataFrame:
    columns = [
        "stage_name",
        "raw_rows",
        "after_rows",
        "removed_rows",
        "removed_breakdown",
        "distribution_before",
        "distribution_after",
        "profile_rows_before",
        "profile_rows_after",
        "unique_mentor_ids_before",
        "unique_mentor_ids_after",
    ]
    if pool_df is None:
        return pd.DataFrame(columns=columns)
    trace_payload = pool_df.attrs.get("mentor_pool_governance_trace")
    if not isinstance(trace_payload, Sequence):
        return pd.DataFrame(columns=columns)
    rows: list[dict[str, object]] = []
    for entry in trace_payload:
        if isinstance(entry, Mapping):
            rows.append({column: entry.get(column) for column in columns})
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows, columns=columns)


def _build_pool_condense_trace_sheet(pool_df: pd.DataFrame | None) -> pd.DataFrame:
    columns = [
        "profile_rows_before",
        "unique_mentor_ids_before",
        "profile_rows_after",
        "unique_mentor_ids_after",
        "profiles_per_mentor_min",
        "profiles_per_mentor_p50",
        "profiles_per_mentor_p90",
        "profiles_per_mentor_max",
    ]
    if pool_df is None:
        return pd.DataFrame(columns=columns)
    payload = pool_df.attrs.get(_POOL_QA_PAYLOAD_ATTR)
    if not isinstance(payload, Mapping):
        return pd.DataFrame(columns=columns)
    all_profiles = payload.get("all_profiles")
    all_df = pd.DataFrame(all_profiles) if isinstance(all_profiles, list) else pd.DataFrame()
    profile_rows_before = int(all_df.shape[0])
    unique_before = (
        int(all_df["mentor_id"].nunique()) if "mentor_id" in all_df.columns else 0
    )
    profile_rows_after = int(pool_df.shape[0])
    unique_after = int(pool_df["mentor_id"].nunique()) if "mentor_id" in pool_df.columns else 0
    stats = {
        "profiles_per_mentor_min": None,
        "profiles_per_mentor_p50": None,
        "profiles_per_mentor_p90": None,
        "profiles_per_mentor_max": None,
    }
    if "mentor_id" in all_df.columns and not all_df.empty:
        counts = all_df["mentor_id"].astype("string").value_counts()
        stats = {
            "profiles_per_mentor_min": int(counts.min()),
            "profiles_per_mentor_p50": float(counts.quantile(0.5, interpolation="lower")),
            "profiles_per_mentor_p90": float(counts.quantile(0.9, interpolation="lower")),
            "profiles_per_mentor_max": int(counts.max()),
        }
    row = {
        "profile_rows_before": profile_rows_before,
        "unique_mentor_ids_before": unique_before,
        "profile_rows_after": profile_rows_after,
        "unique_mentor_ids_after": unique_after,
        **stats,
    }
    return pd.DataFrame([row], columns=columns)


def _build_multi_profile_summary_sheet(pool_df: pd.DataFrame | None) -> pd.DataFrame:
    columns = [
        "profile_rows",
        "unique_mentor_ids",
        "multi_profile_mentor_count",
        "multi_profile_ratio",
    ]
    if pool_df is None:
        return pd.DataFrame(columns=columns)
    payload = pool_df.attrs.get(_POOL_QA_PAYLOAD_ATTR)
    if not isinstance(payload, Mapping):
        return pd.DataFrame(columns=columns)
    all_profiles = payload.get("all_profiles")
    all_df = pd.DataFrame(all_profiles) if isinstance(all_profiles, list) else pd.DataFrame()
    if "mentor_id" not in all_df.columns or all_df.empty:
        return pd.DataFrame(
            [
                {
                    "profile_rows": int(all_df.shape[0]),
                    "unique_mentor_ids": 0,
                    "multi_profile_mentor_count": 0,
                    "multi_profile_ratio": 0.0,
                }
            ],
            columns=columns,
        )
    counts = all_df["mentor_id"].astype("string").value_counts()
    unique_mentors = int(counts.shape[0])
    multi_profile = int((counts > 1).sum())
    ratio = float(multi_profile / unique_mentors) if unique_mentors else 0.0
    return pd.DataFrame(
        [
            {
                "profile_rows": int(all_df.shape[0]),
                "unique_mentor_ids": unique_mentors,
                "multi_profile_mentor_count": multi_profile,
                "multi_profile_ratio": ratio,
            }
        ],
        columns=columns,
    )


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
    pool_df: pd.DataFrame | None = None,
    enable_standard_debug_sheets: bool = True,
    enable_mentor_trace_debug: bool = False,
    enable_history_metrics: bool = True,
    enable_pool_governance_trace: bool = False,
    enable_bucket_trace: bool = False,
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
    if (
        not enable_standard_debug_sheets
        and not enable_mentor_trace_debug
        and not enable_pool_governance_trace
        and not enable_bucket_trace
    ):
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
        sheets["TraceLadder"] = _build_trace_ladder_sheet(
            trace_df,
            logs_df=logs_df,
            policy=policy,
        )
        pipeline_trace_payload: object | None = pool_trace
        if policy is not None and pool_df is not None and students_df is not None:
            prefilter_entry = build_global_prefilter_trace_entry(
                pool_df,
                students_df,
                policy=policy,
            )
            merged_trace: list[dict[str, object]] = []
            if isinstance(pool_trace, Sequence) and not isinstance(pool_trace, (str, bytes)):
                for entry in pool_trace:
                    if isinstance(entry, Mapping):
                        merged_trace.append(dict(entry))
            merged_trace.append(prefilter_entry.to_record())
            pipeline_trace_payload = merged_trace
        if pipeline_trace_payload is not None:
            sheets["MentorPipelineTrace"] = _build_pipeline_trace_sheet(pipeline_trace_payload)

    if enable_bucket_trace:
        sheets["BucketTrace"] = _build_bucket_trace_sheet(logs_df)

    if enable_pool_governance_trace:
        sheets["PoolGovernanceTrace"] = _build_pool_governance_trace_sheet(pool_df)
        sheets["PoolCondenseTrace"] = _build_pool_condense_trace_sheet(pool_df)
        sheets["MultiProfileSummary"] = _build_multi_profile_summary_sheet(pool_df)

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

    resolved_profile_path = profile_path or DEFAULT_SABT_PROFILE_PATH
    profile = load_sabt_export_profile(resolved_profile_path)
    export_df = build_sabt_export_frame(
        allocation_df,
        students_df,
        profile,
        summary_df=summary_df,
        profile_path=resolved_profile_path,
    )
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


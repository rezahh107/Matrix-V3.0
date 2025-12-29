"""خروجی Excel برای گزارش اعتبارسنجی QA (Policy-First)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from app.core.qa.invariants import QaReport
from app.infra.io_utils import write_xlsx_atomic

__all__ = ["QaValidationContext", "export_qa_validation"]

_RULE_DESCRIPTIONS: dict[str, str] = {
    "QA_RULE_STU_01": "تطابق شمار دانش‌آموز در ورودی/خروجی‌ها",
    "QA_RULE_STU_02": "شمار دانش‌آموز به ازای هر منتور مطابق Inspactor/Allocation",
    "QA_RULE_JOIN_01": "سلامت ستون‌های join ماتریس",
    "QA_RULE_SCHOOL_01": "تفکیک منتورهای آزاد و مقید به مدرسه",
    "QA_RULE_ALLOC_01": "کنترل ظرفیت و نسبت اشغال منتورها",
    "QA_RULE_POOL_JOIN_01": "ردیف تکراری روی کلید ترکیبی mentor_id و کلیدهای اتصال",
}


@dataclass(frozen=True)
class QaValidationContext:
    """ورودی‌های تکمیلی برای ساخت ورک‌بوک اعتبارسنجی QA."""

    matrix: pd.DataFrame | None = None
    allocation: pd.DataFrame | None = None
    allocation_summary: pd.DataFrame | None = None
    inspactor: pd.DataFrame | None = None
    invalid_mentors: pd.DataFrame | None = None
    meta: Mapping[str, object] | None = None
    pool_join_key_duplicates: pd.DataFrame | None = None
    alloc_join_audit: pd.DataFrame | None = None
    alloc_join_summary: pd.DataFrame | None = None
    pool_join_conflicts: pd.DataFrame | None = None
    pool_alignment_preflight: pd.DataFrame | None = None


def _summary_sheet(report: QaReport) -> pd.DataFrame:
    summary = report.to_summary_frame(descriptions=_RULE_DESCRIPTIONS)
    if summary.empty:
        return summary
    summary = summary.sort_values(by=["rule_id"], kind="stable").reset_index(drop=True)
    return summary


def _students_per_mentor_sheet(report: QaReport) -> pd.DataFrame:
    details = report.to_details_frame("QA_RULE_STU_02")
    if details.empty:
        return pd.DataFrame(columns=["mentor_id", "expected", "assigned", "message", "level"])
    preferred_order = ["mentor_id", "expected", "assigned", "message", "level"]
    cols = [col for col in preferred_order if col in details.columns]
    remaining = [col for col in details.columns if col not in cols]
    ordered = details.loc[:, cols + remaining]
    return ordered


def _school_binding_sheet(report: QaReport) -> pd.DataFrame:
    details = report.to_details_frame("QA_RULE_SCHOOL_01")
    rows: list[dict[str, object]] = []
    for _, row in details.iterrows():
        mentor_ids = row.get("mentor_ids")
        if isinstance(mentor_ids, (list, tuple)) and mentor_ids:
            for mentor_id in mentor_ids:
                rows.append(
                    {
                        "mentor_id": mentor_id,
                        "issue": row.get("message"),
                        "level": row.get("level"),
                    }
                )
        else:
            rows.append(
                {
                    "mentor_id": row.get("mentor_id"),
                    "issue": row.get("message"),
                    "level": row.get("level"),
                }
            )
    if not rows:
        return pd.DataFrame(columns=["mentor_id", "issue", "level"])
    frame = pd.DataFrame(rows)
    return frame.sort_values(by=["mentor_id", "issue"], kind="stable").reset_index(drop=True)


def _allocation_capacity_sheet(report: QaReport) -> pd.DataFrame:
    details = report.to_details_frame("QA_RULE_ALLOC_01")
    if details.empty:
        return pd.DataFrame(
            columns=[
                "mentor_id",
                "assigned",
                "remaining",
                "allocations_new",
                "expected_ratio",
                "actual_ratio",
                "level",
            ]
        )
    preferred = [
        "mentor_id",
        "assigned",
        "remaining",
        "allocations_new",
        "expected_ratio",
        "actual_ratio",
        "message",
        "level",
    ]
    cols = [col for col in preferred if col in details.columns]
    remaining = [col for col in details.columns if col not in cols]
    ordered = details.loc[:, cols + remaining]
    return ordered


def _join_key_sheet(report: QaReport) -> pd.DataFrame:
    details = report.to_details_frame("QA_RULE_JOIN_01")
    if details.empty:
        return pd.DataFrame(columns=["message", "level"])
    return details


def _join_key_duplicates_sheet(context: QaValidationContext) -> pd.DataFrame:
    df = context.pool_join_key_duplicates
    if df is None:
        return pd.DataFrame(
            columns=[
                "کدرشته",
                "جنسیت",
                "دانش آموز فارغ",
                "مرکز گلستان صدرا",
                "مالی حکمت بنیاد",
                "کد مدرسه",
                "mentor_id",
                "duplicate_group_size",
                "pool_row_index",
                "pool_source",
            ]
        )
    ordered = [
        "کدرشته",
        "جنسیت",
        "دانش آموز فارغ",
        "مرکز گلستان صدرا",
        "مالی حکمت بنیاد",
        "کد مدرسه",
        "mentor_id",
        "duplicate_group_size",
        "pool_row_index",
        "pool_source",
    ]
    base_cols = [col for col in ordered if col in df.columns]
    remaining = [col for col in df.columns if col not in base_cols]
    if not base_cols and not remaining:
        return pd.DataFrame(columns=ordered)
    result = df.loc[:, base_cols + remaining].copy()
    if base_cols:
        result = result.sort_values(by=base_cols, kind="stable").reset_index(drop=True)
    return result


def _pool_join_conflicts_sheet(context: QaValidationContext, report: QaReport) -> pd.DataFrame:
    conflict_frame = context.pool_join_conflicts
    if conflict_frame is None and report.extras is not None:
        conflict_frame = report.extras.get("pool_join_conflicts")
    if conflict_frame is None:
        return pd.DataFrame(
            columns=[
                "mentor_id",
                "duplicate_group_size",
            ]
        )
    mentor_columns = ["mentor_id", "کد کارمندی پشتیبان"]
    join_key_columns = [
        col
        for col in conflict_frame.columns
        if col
        not in {
            "duplicate_group_size",
            "pool_row_index",
            "pool_source",
            "mentor_id",
            "کد کارمندی پشتیبان",
        }
    ]
    ordered: list[str] = [col for col in join_key_columns if col in conflict_frame.columns]
    ordered += [col for col in mentor_columns if col in conflict_frame.columns]
    ordered += [
        col
        for col in ("duplicate_group_size", "pool_row_index", "pool_source")
        if col in conflict_frame.columns
    ]
    remaining = [col for col in conflict_frame.columns if col not in ordered]
    frame = conflict_frame.loc[:, ordered + remaining]
    if not frame.empty and ordered:
        frame = frame.sort_values(by=ordered, kind="stable")
    return frame.reset_index(drop=True)


def _stu_count_sheet(report: QaReport) -> pd.DataFrame:
    details = report.to_details_frame("QA_RULE_STU_01")
    if details.empty:
        return pd.DataFrame(columns=["student_report", "matrix", "allocation", "message", "level"])
    preferred = ["student_report", "matrix", "allocation", "message", "level"]
    cols = [col for col in preferred if col in details.columns]
    remaining = [col for col in details.columns if col not in cols]
    return details.loc[:, cols + remaining]


def _meta_sheet(context: QaValidationContext, report: QaReport) -> pd.DataFrame:
    meta: dict[str, object] = {}
    if context.meta:
        meta.update(context.meta)
    meta.setdefault("generated_at", datetime.now(UTC).isoformat().replace("+00:00", "Z"))
    meta.setdefault("rules_total", len(report.results))
    meta.setdefault("rules_failed", sum(not r.passed for r in report.results))
    meta.setdefault("policy_version", meta.get("policy_version"))
    meta.setdefault("ssot_version", meta.get("ssot_version"))
    return pd.json_normalize([meta])


def _pool_detection_sheet(context: QaValidationContext) -> pd.DataFrame:
    detection: object | None = None
    if context.meta:
        detection = context.meta.get("pool_detection")
    if not detection or not isinstance(detection, Mapping):
        return pd.DataFrame(
            columns=[
                "sheet",
                "missing_required_count",
                "missing_required_list",
                "row_count",
                "col_count",
                "excluded_reason",
                "has_mentor_id",
                "selected_sheet",
                "pool_type",
                "detection_method",
                "confidence",
            ]
        )
    sheets = detection.get("sheets") if isinstance(detection, Mapping) else None
    if not isinstance(sheets, list):
        sheets = []
    detection_map = detection
    frame = pd.DataFrame(sheets)
    frame["selected_sheet"] = detection_map.get("selected_sheet")
    frame["pool_type"] = detection_map.get("pool_type")
    frame["detection_method"] = detection_map.get("detection_method")
    frame["confidence"] = detection_map.get("confidence")
    return frame


def export_qa_validation(
    report: QaReport,
    *,
    output: Path,
    context: QaValidationContext | None = None,
) -> None:
    """نوشتن ورک‌بوک اعتبارسنجی QA به‌صورت اتمیک و قابل تکرار."""

    ctx = context or QaValidationContext()
    sheets: dict[str, pd.DataFrame] = {
        "summary": _summary_sheet(report),
        "students_per_mentor": _students_per_mentor_sheet(report),
        "school_binding_issues": _school_binding_sheet(report),
        "allocation_capacity": _allocation_capacity_sheet(report),
        "join_keys": _join_key_sheet(report),
        "student_counts": _stu_count_sheet(report),
        "meta": _meta_sheet(ctx, report),
        "pool_join_key_duplicates": _join_key_duplicates_sheet(ctx),
        "pool_join_conflicts": _pool_join_conflicts_sheet(ctx, report),
        "pool_detection": _pool_detection_sheet(ctx),
    }
    if ctx.alloc_join_summary is not None:
        sheets["alloc_join_summary"] = ctx.alloc_join_summary
    if ctx.alloc_join_audit is not None:
        audit = ctx.alloc_join_audit
        if "any_mismatch" in audit.columns:
            audit = audit.loc[audit["any_mismatch"].fillna(False)].copy()
        sheets["alloc_join_mismatches"] = audit
    if ctx.pool_alignment_preflight is not None:
        sheets["pool_alignment_preflight"] = ctx.pool_alignment_preflight
    sheet_modes = {name: None for name in sheets}
    write_xlsx_atomic(sheets, output, header_mode=None, sheet_header_modes=sheet_modes)

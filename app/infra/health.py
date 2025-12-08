"""Health and debug report helpers built on top of QA snapshots.

این ماژول بدون تغییر در منطق Core، وضعیت سلامت خروجی هر اجرا را با استفاده از
داده‌های QA ذخیره‌شده در پایگاه داده محلی محاسبه می‌کند و یک گزارش فشرده برای
مصرف مدل زبانی یا پشتیبانی فنی تولید می‌نماید.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

import pandas as pd

from app.core.qa.law_mapping import all_law_mappings
from app.infra.local_database import LocalDatabase

HealthStatus = Literal["OK", "WARN", "ERROR"]


@dataclass(frozen=True)
class IssueSummary:
    """خلاصهٔ یک کد تخطی همراه با شدت و تعداد وقوع."""

    issue_code: str
    severity: str
    count: int
    description: str | None = None


@dataclass(frozen=True)
class HealthSummary:
    """وضعیت کلی سلامت یک اجرا."""

    status: HealthStatus
    summary_text: str
    counts: dict[str, int]
    issues_summary: list[IssueSummary]


def _deduce_severity(raw_level: object) -> str:
    text = str(raw_level).lower().strip()
    if text == "error":
        return "P0"
    if text == "warning":
        return "P1"
    return "P2"


def _describe_rule(rule_id: str) -> str | None:
    mapping = all_law_mappings().get(rule_id)
    if mapping is None:
        return None
    return mapping.description


def _resolve_run_row(db: LocalDatabase, run_id: str) -> dict[str, object] | None:
    try:
        run_key = int(run_id)
        by_id = db.fetch_run_by_id(run_key)
        if by_id is not None:
            return dict(by_id)
    except ValueError:
        pass
    by_uuid = db.fetch_run_by_uuid(run_id)
    return dict(by_uuid) if by_uuid is not None else None


def _summarize_issues(
    qa_details_df: pd.DataFrame | None, qa_summary_df: pd.DataFrame | None
) -> tuple[dict[str, int], list[IssueSummary]]:
    counts = {"P0": 0, "P1": 0, "P2": 0}
    issues: list[IssueSummary] = []
    if qa_details_df is not None and not qa_details_df.empty:
        grouped = qa_details_df.groupby("rule_id", dropna=False)
        for rule_id, frame in grouped:
            severity_levels = [_deduce_severity(value) for value in frame.get("level", [])]
            severity = (
                min(severity_levels, key=lambda lvl: ["P0", "P1", "P2"].index(lvl))
                if severity_levels
                else "P2"
            )
            count = int(len(frame.index))
            counts[severity] += count
            issues.append(
                IssueSummary(
                    issue_code=str(rule_id),
                    severity=severity,
                    count=count,
                    description=_describe_rule(str(rule_id)),
                )
            )
        return counts, issues

    if qa_summary_df is not None and not qa_summary_df.empty:
        for _, row in qa_summary_df.iterrows():
            rule_id = str(row.get("rule_id", ""))
            violations = int(row.get("violations_count", 0) or 0)
            status = str(row.get("status", "")).upper()
            severity = "P1" if status == "FAIL" and violations > 0 else "P2"
            counts[severity] += violations
            issues.append(
                IssueSummary(
                    issue_code=rule_id,
                    severity=severity,
                    count=violations,
                    description=_describe_rule(rule_id),
                )
            )
    return counts, issues


def compute_run_health(run_id: str, *, db: LocalDatabase) -> HealthSummary:
    """محاسبهٔ وضعیت سلامت یک اجرا بر اساس Snapshot های QA ذخیره‌شده."""

    run_row = _resolve_run_row(db, run_id)
    qa_summary_df: pd.DataFrame | None = None
    qa_details_df: pd.DataFrame | None = None
    if run_row is not None:
        summary_df, details_df, _ = db.fetch_qa_snapshot(int(run_row.get("id")))
        qa_summary_df = summary_df
        qa_details_df = details_df

    counts, issues = _summarize_issues(qa_details_df, qa_summary_df)
    status: HealthStatus = "OK"
    if counts["P0"] > 0:
        status = "ERROR"
    elif counts["P1"] > 0:
        status = "WARN"

    summary_text = {
        "ERROR": "System health: ERROR 🔴 (do NOT use this output)",
        "WARN": "System health: WARNING 🟡 (review warnings before using output)",
        "OK": "System health: OK ✅ (output is safe to use)",
    }[status]
    return HealthSummary(
        status=status, summary_text=summary_text, counts=counts, issues_summary=issues
    )


def _coerce_timestamp() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _allocation_snapshot(
    run_row: dict[str, object] | None, qa_details_df: pd.DataFrame | None
) -> dict[str, int | None]:
    total_students = (
        int(run_row.get("total_students"))
        if run_row and run_row.get("total_students") is not None
        else None
    )
    students_without_mentor = (
        int(run_row.get("total_unallocated"))
        if run_row and run_row.get("total_unallocated") is not None
        else None
    )
    negative_capacity = 0
    if qa_details_df is not None and not qa_details_df.empty:
        for column in qa_details_df.columns:
            if "capacity" in str(column).lower():
                with pd.option_context("mode.use_inf_as_na", True):
                    try:
                        negative_capacity += int((qa_details_df[column] < 0).sum())
                    except Exception:
                        continue
    return {
        "total_students": total_students,
        "students_without_mentor": students_without_mentor,
        "mentors_with_negative_capacity": negative_capacity or None,
    }


def _build_samples(
    qa_details_df: pd.DataFrame | None, issues: list[IssueSummary], *, sample_limit: int
) -> list[dict[str, object]]:
    if qa_details_df is None or qa_details_df.empty:
        return []
    candidate_fields = [
        "mentor_id",
        "student_id",
        "school_code",
        "center_code",
        "capacity",
        "remaining_capacity",
        "group_code",
    ]
    samples: list[dict[str, object]] = []
    for issue in sorted(issues, key=lambda item: item.issue_code):
        frame = qa_details_df[qa_details_df["rule_id"] == issue.issue_code]
        if frame.empty:
            continue
        limited = frame.head(sample_limit)
        rows: list[dict[str, object]] = []
        for _, row in limited.iterrows():
            payload = {
                field: row[field]
                for field in candidate_fields
                if field in row and pd.notna(row[field])
            }
            if payload:
                rows.append(payload)
        samples.append({"issue_code": issue.issue_code, "rows": rows})
    return samples


def build_llm_debug_report(
    run_id: str, *, db: LocalDatabase, sample_limit: int = 3
) -> dict[str, object]:
    """تولید گزارش فشرده برای دیباگ توسط پشتیبانی یا مدل زبانی."""

    run_row = _resolve_run_row(db, run_id)
    summary_df, details_df, extras = (None, None, {})
    if run_row is not None:
        summary_df, details_df, extras = db.fetch_qa_snapshot(int(run_row.get("id")))
    health = compute_run_health(run_id, db=db)
    samples = _build_samples(details_df, health.issues_summary, sample_limit=sample_limit)
    return {
        "meta": {
            "run_id": run_id,
            "timestamp": _coerce_timestamp(),
            "environment": None,
            "policy_version": run_row.get("policy_version") if run_row else None,
            "code_version": None,
        },
        "health": {
            "status": health.status,
            "summary_text": health.summary_text,
            "counts": health.counts,
        },
        "issues_summary": [issue.__dict__ for issue in health.issues_summary],
        "samples": samples,
        "allocation_snapshot": _allocation_snapshot(run_row, details_df),
        "extras": list(extras.keys()) if extras else [],
    }


def export_llm_debug_report_to_file(
    run_id: str, *, db: LocalDatabase, output_dir: Path | None = None, sample_limit: int = 3
) -> Path:
    """ساخت و ذخیرهٔ گزارش دیباگ در مسیر دترمینیستیک."""

    report = build_llm_debug_report(run_id, db=db, sample_limit=sample_limit)
    target_dir = output_dir or Path.cwd() / "debug_reports"
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = report["meta"]["timestamp"].replace(":", "-")
    filename = f"run_{run_id}_{timestamp}.json"
    path = target_dir / filename
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return path

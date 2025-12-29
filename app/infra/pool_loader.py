from __future__ import annotations

from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Literal

import pandas as pd

from app.core.build_matrix import COL_MENTOR_ID, REQUIRED_INSPACTOR_COLUMNS
from app.core.common.columns import canonicalize_headers
from app.core.inspactor_schema_helper import missing_inspactor_columns
from app.infra.io_utils import ALT_CODE_COLUMN

PoolType = Literal["inspactor", "matrix"]


@dataclass(frozen=True)
class PoolDetectionResult:
    pool_type: PoolType
    selected_sheet: str
    detection_method: Literal["explicit", "auto"]
    confidence: float
    evidence: dict[str, object]


def _worksheet_shape(
    excel: pd.ExcelFile, sheet_name: str, header_columns: list[str] | None
) -> tuple[int | None, int | None]:
    row_count: int | None = None
    col_count: int | None = None
    try:
        worksheet = excel.book[sheet_name]
        row_count = (
            worksheet.max_row - 1 if worksheet.max_row is not None and worksheet.max_row > 0 else 0
        )
        col_count = worksheet.max_column if worksheet.max_column is not None else None
    except Exception:  # pragma: no cover - defensive fallback
        row_count, col_count = None, None

    if (row_count is None or row_count <= 0) or col_count is None:
        try:
            sample = excel.parse(sheet_name, usecols=[0])
            row_count = sample.shape[0] if row_count is None or row_count <= 0 else row_count
            col_count = col_count or len(header_columns or [])
        except Exception:  # pragma: no cover - defensive fallback
            row_count = row_count if row_count is not None else 0
            col_count = col_count
    if col_count is None and header_columns is not None:
        col_count = len(header_columns)
    return row_count, col_count


def _sheet_evidence(
    *,
    sheet: str,
    missing: list[str] | None,
    row_count: int | None,
    col_count: int | None,
    excluded_reason: str | None,
    has_mentor_id: bool | None,
) -> dict[str, object]:
    return {
        "sheet": sheet,
        "missing_required_count": len(missing or []),
        "missing_required_list": list(missing[:8]) if missing else [],
        "row_count": row_count,
        "col_count": col_count,
        "excluded_reason": excluded_reason,
        "has_mentor_id": has_mentor_id,
    }


def _candidate_threshold() -> int:
    return max(2, int(0.3 * len(REQUIRED_INSPACTOR_COLUMNS)))


def _inspect_sheet(
    excel: pd.ExcelFile, sheet_name: str, *, explicit_sheet: str | None
) -> tuple[dict[str, object], tuple[str, int, int | None, bool] | None]:
    excluded_reason: str | None = None
    if sheet_name == "matrix" and explicit_sheet != "matrix":
        excluded_reason = "reserved_sheet_matrix"
    try:
        header_frame = excel.parse(sheet_name, nrows=0)
    except Exception as exc:  # pragma: no cover - defensive path
        evidence = _sheet_evidence(
            sheet=sheet_name,
            missing=None,
            row_count=None,
            col_count=None,
            excluded_reason=str(exc),
            has_mentor_id=None,
        )
        return evidence, None
    canonical_headers = canonicalize_headers(header_frame, header_mode="fa")
    missing = missing_inspactor_columns(canonical_headers, REQUIRED_INSPACTOR_COLUMNS)
    row_count, col_count = _worksheet_shape(
        excel, sheet_name, list(header_frame.columns)
    )
    has_mentor_id = "mentor_id" in canonical_headers.columns or COL_MENTOR_ID in canonical_headers.columns
    evidence = _sheet_evidence(
        sheet=sheet_name,
        missing=missing,
        row_count=row_count,
        col_count=col_count,
        excluded_reason=excluded_reason,
        has_mentor_id=has_mentor_id,
    )
    if excluded_reason is not None:
        return evidence, None
    if row_count is not None and row_count <= 0:
        return evidence, None
    return evidence, (sheet_name, len(missing), row_count, has_mentor_id)


def _detect_explicit_sheet(
    excel: pd.ExcelFile,
    *,
    source: Path,
    explicit_sheet: str,
    pool_type: PoolType,
) -> PoolDetectionResult:
    if explicit_sheet not in excel.sheet_names:
        raise ValueError(
            f"شیت «{explicit_sheet}» در فایل {source} یافت نشد؛ شیت‌های موجود: {excel.sheet_names}"
        )
    evidence, _ = _collect_inspactor_evidence(
        excel, explicit_sheet=explicit_sheet
    )
    return PoolDetectionResult(
        pool_type=pool_type,
        selected_sheet=explicit_sheet,
        detection_method="explicit",
        confidence=1.0,
        evidence={"path": str(source), "sheets": evidence},
    )


def _detect_matrix_sheet(excel: pd.ExcelFile, source: Path) -> PoolDetectionResult:
    if "matrix" not in excel.sheet_names:
        raise ValueError(
            "شیت 'matrix' برای pool_type='matrix' یافت نشد؛ شیت‌های موجود: "
            f"{excel.sheet_names}"
        )
    evidence, _ = _collect_inspactor_evidence(excel, explicit_sheet="matrix")
    return PoolDetectionResult(
        pool_type="matrix",
        selected_sheet="matrix",
        detection_method="auto",
        confidence=0.9,
        evidence={"path": str(source), "sheets": evidence},
    )


def _detect_inspactor_sheet(excel: pd.ExcelFile, source: Path) -> PoolDetectionResult:
    evidence, candidates = _collect_inspactor_evidence(excel, explicit_sheet=None)
    usable_candidates = [item for item in candidates if item[2] not in {None, 0}]
    if not usable_candidates:
        raise ValueError(
            "هیچ شیت معتبری برای استخر Inspactor یافت نشد؛ شیت 'matrix' کنار گذاشته شد."
            " برای استفاده از خروجی rule-engine از --pool-type matrix یا --pool-sheet استفاده کنید."
        )

    def _row_priority(row_count: int | None) -> float:
        return -float(row_count) if row_count is not None else float("inf")

    usable_candidates.sort(
        key=lambda item: (item[1], _row_priority(item[2]), item[0])
    )
    selected_sheet, missing_count, _, has_mentor_id = usable_candidates[0]
    threshold = _candidate_threshold()
    if not has_mentor_id or missing_count > threshold:
        raise ValueError(
            "هیچ شیت Inspactor با ستون‌های کافی یافت نشد؛ لطفاً از --pool-type matrix یا --pool-sheet برای انتخاب شیت درست استفاده کنید."
        )
    confidence = 0.9 if missing_count == 0 else 0.6
    return PoolDetectionResult(
        pool_type="inspactor",
        selected_sheet=selected_sheet,
        detection_method="auto",
        confidence=confidence,
        evidence={"path": str(source), "sheets": evidence},
    )


def _collect_inspactor_evidence(
    excel: pd.ExcelFile, *, explicit_sheet: str | None
) -> tuple[list[dict[str, object]], list[tuple[str, int, int | None, bool]]]:
    evidence: list[dict[str, object]] = []
    candidates: list[tuple[str, int, int | None, bool]] = []
    for sheet_name in excel.sheet_names:
        sheet_evidence, candidate = _inspect_sheet(
            excel, sheet_name, explicit_sheet=explicit_sheet
        )
        evidence.append(sheet_evidence)
        if candidate is not None:
            candidates.append(candidate)
    return evidence, candidates


def detect_pool_sheet(
    path: Path | str | PathLike[str],
    pool_type: PoolType,
    explicit_sheet: str | None = None,
) -> PoolDetectionResult:
    source = Path(path)
    try:
        with pd.ExcelFile(source) as excel:
            if not excel.sheet_names:
                raise ValueError(f"هیچ شیتی در فایل {source} یافت نشد.")

            if explicit_sheet is not None:
                return _detect_explicit_sheet(
                    excel, source=source, explicit_sheet=explicit_sheet, pool_type=pool_type
                )

            if pool_type == "matrix":
                return _detect_matrix_sheet(excel, source)

            return _detect_inspactor_sheet(excel, source)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"فایل یافت نشد: {source}") from exc


def load_pool_with_detection(
    path: Path | str | PathLike[str],
    *,
    pool_type: PoolType = "inspactor",
    pool_sheet: str | None = None,
) -> tuple[pd.DataFrame, PoolDetectionResult]:
    detection = detect_pool_sheet(path, pool_type=pool_type, explicit_sheet=pool_sheet)
    with pd.ExcelFile(path) as excel:
        df = excel.parse(detection.selected_sheet)
    canonical = canonicalize_headers(df, header_mode="fa")
    if ALT_CODE_COLUMN in canonical.columns:
        canonical = canonical.copy()
        canonical[ALT_CODE_COLUMN] = canonical[ALT_CODE_COLUMN].astype(str)
    canonical.attrs["pool_detection"] = detection
    canonical.attrs.setdefault("pool_source", pool_type)
    return canonical, detection


def load_pool(
    path: Path | str | PathLike[str],
    *,
    pool_type: PoolType = "inspactor",
    pool_sheet: str | None = None,
) -> pd.DataFrame:
    canonical, _ = load_pool_with_detection(
        path, pool_type=pool_type, pool_sheet=pool_sheet
    )
    return canonical


__all__ = [
    "PoolType",
    "PoolDetectionResult",
    "detect_pool_sheet",
    "load_pool",
    "load_pool_with_detection",
]

from __future__ import annotations

from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Literal

import pandas as pd

from app.core.build_matrix import COL_MENTOR_ID
from app.core.common.columns import canonicalize_headers
from app.infra.io_utils import ALT_CODE_COLUMN

# Matrix-only pool loader for allocation and diagnostics. Inspactor ingestion for the
# pool builder lives in reference_mentors_repository and MUST NOT be wired into
# allocation paths.

PoolType = Literal["matrix"]


@dataclass(frozen=True)
class PoolDetectionResult:
    pool_type: PoolType
    selected_sheet: str
    detection_method: Literal["explicit", "auto"]
    confidence: float
    evidence: dict[str, object]


class MatrixPoolRequiredError(Exception):
    """Raised when a mentor pool workbook does not contain a matrix sheet."""

    def __init__(self, source: Path, *, sheets: list[str]) -> None:
        self.source = source
        self.sheets = sheets
        super().__init__(str(self))

    def __str__(self) -> str:  # pragma: no cover - delegated to callers
        return (
            "فایل استخر منتورها باید شیت 'matrix' داشته باشد. "
            f"شیت‌های موجود: {self.sheets}"
        )


def _select_matrix_sheet(
    excel: pd.ExcelFile, *, explicit_sheet: str | None, source: Path
) -> tuple[str, Literal["explicit", "auto"]]:
    if not excel.sheet_names:
        raise MatrixPoolRequiredError(source, sheets=[])

    sheet_map = {name.lower(): name for name in excel.sheet_names}
    has_matrix = "matrix" in sheet_map

    if explicit_sheet is not None:
        if explicit_sheet.lower() != "matrix":
            raise MatrixPoolRequiredError(source, sheets=excel.sheet_names)
        if not has_matrix:
            raise MatrixPoolRequiredError(source, sheets=excel.sheet_names)
        return sheet_map["matrix"], "explicit"

    if not has_matrix:
        raise MatrixPoolRequiredError(source, sheets=excel.sheet_names)
    return sheet_map["matrix"], "auto"


def detect_pool_sheet(
    path: Path | str | PathLike[str],
    pool_type: PoolType = "matrix",
    explicit_sheet: str | None = None,
) -> PoolDetectionResult:
    if pool_type != "matrix":
        raise ValueError("pool-type باید 'matrix' باشد (بدون fallback).")

    source = Path(path)
    try:
        with pd.ExcelFile(source) as excel:
            selected_sheet, method = _select_matrix_sheet(
                excel, explicit_sheet=explicit_sheet, source=source
            )
            return PoolDetectionResult(
                pool_type="matrix",
                selected_sheet=selected_sheet,
                detection_method=method,
                confidence=1.0,
                evidence={"path": str(source), "sheets": list(excel.sheet_names)},
            )
    except FileNotFoundError as exc:  # pragma: no cover - passthrough
        raise FileNotFoundError(f"فایل یافت نشد: {source}") from exc


def load_pool_with_detection(
    path: Path | str | PathLike[str],
    *,
    pool_type: PoolType = "matrix",
    pool_sheet: str | None = None,
) -> tuple[pd.DataFrame, PoolDetectionResult]:
    detection = detect_pool_sheet(
        path, pool_type=pool_type, explicit_sheet=pool_sheet
    )
    with pd.ExcelFile(path) as excel:
        df = excel.parse(detection.selected_sheet)
    detection.evidence.setdefault("raw_row_count", int(df.shape[0]))
    canonical = canonicalize_headers(df, header_mode="fa")
    if ALT_CODE_COLUMN in canonical.columns:
        canonical = canonical.copy()
        canonical[ALT_CODE_COLUMN] = canonical[ALT_CODE_COLUMN].astype(str)
    canonical.attrs["pool_detection"] = detection
    canonical.attrs.setdefault("pool_source", detection.pool_type)
    canonical.attrs.setdefault("raw_row_count", int(df.shape[0]))
    canonical.attrs.setdefault("raw_sheet_name", detection.selected_sheet)
    if COL_MENTOR_ID in canonical.columns:
        mentor_col = canonical[COL_MENTOR_ID]
        if isinstance(mentor_col, pd.DataFrame):
            mentor_col = mentor_col.iloc[:, 0]
        if mentor_col.dtype == object:
            canonical = canonical.copy()
            canonical[COL_MENTOR_ID] = mentor_col.astype(str)
    return canonical, detection


def load_pool(
    path: Path | str | PathLike[str],
    *,
    pool_type: PoolType = "matrix",
    pool_sheet: str | None = None,
) -> pd.DataFrame:
    canonical, _ = load_pool_with_detection(
        path, pool_type=pool_type, pool_sheet=pool_sheet
    )
    return canonical


__all__ = [
    "PoolType",
    "PoolDetectionResult",
    "MatrixPoolRequiredError",
    "detect_pool_sheet",
    "load_pool",
    "load_pool_with_detection",
]

from __future__ import annotations

from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Literal, TypedDict, cast

import pandas as pd

PoolType = Literal["inspactor", "matrix"]


class SheetEvidence(TypedDict):
    sheet: str
    missing_columns: list[str]
    missing_count: int
    row_count: int | None
    excluded: bool
    exclusion_reason: str | None


@dataclass(frozen=True)
class PoolDetectionResult:
    pool_type: PoolType
    selected_sheet: str
    detection_method: str
    confidence: float
    evidence: dict[str, object]


_EXPECTED_COLUMNS: dict[PoolType, set[str]] = {
    "inspactor": {
        "نام معلم",
        "نام مدیر",
        "کد معلم",
        "کدپستی",
        "تعداد مدارس تحت پوشش",
        "کد ملی معلم جایگزین",
        "ظرفیت ویژه",
    },
    "matrix": set(),
}


def detect_pool_sheet(
    path: Path | str | PathLike[str],
    pool_type: PoolType,
    explicit_sheet: str | None = None,
) -> PoolDetectionResult:
    path = Path(path)
    excel = pd.ExcelFile(path)
    sheet_names = list(excel.sheet_names)

    if not sheet_names:
        raise ValueError(f"Workbook {path} has no sheets")

    if explicit_sheet and explicit_sheet not in sheet_names:
        raise ValueError(
            f"Requested sheet '{explicit_sheet}' not found in workbook; available: {sheet_names}"
        )

    evidence: list[SheetEvidence] = []
    expected = _EXPECTED_COLUMNS[pool_type]

    for sheet in sheet_names:
        header_frame = excel.parse(sheet, nrows=0)
        columns = {str(column).strip() for column in header_frame.columns}
        missing_columns = sorted(col for col in expected if col not in columns)
        missing_columns_lite = missing_columns[:5]
        missing_count = len(missing_columns)
        is_reserved_matrix = pool_type == "inspactor" and sheet == "matrix"
        exclusion_reason = (
            "not_explicit_sheet" if explicit_sheet is not None and sheet != explicit_sheet else None
        )
        exclusion_reason = (
            "reserved_sheet_matrix"
            if exclusion_reason is None and is_reserved_matrix and explicit_sheet != "matrix"
            else exclusion_reason
        )
        row_count: int | None = None
        if hasattr(excel, "book") and sheet in getattr(excel.book, "sheetnames", []):
            max_row = getattr(excel.book[sheet], "max_row", None)
            row_count = max(max_row - 1, 0) if max_row is not None else None

        evidence.append(
            {
                "sheet": sheet,
                "missing_columns": missing_columns_lite,
                "missing_count": missing_count,
                "row_count": row_count,
                "excluded": exclusion_reason is not None,
                "exclusion_reason": exclusion_reason,
            }
        )

    if explicit_sheet is not None:
        selected_sheet = explicit_sheet
        detection_method = "explicit_sheet"
        confidence = 1.0
    else:
        candidates = [info for info in evidence if not info["excluded"]]
        if not candidates:
            raise ValueError(
                "No usable sheets found after exclusions; 'matrix' is reserved for pool_type='matrix'. "
                "Pass explicit_sheet='matrix' or use pool_type='matrix'.",
            )

        best_missing_count = min(info["missing_count"] for info in candidates)
        best_candidates = [
            info for info in candidates if info["missing_count"] == best_missing_count
        ]
        all_have_row_counts = all(info["row_count"] is not None for info in best_candidates)
        if all_have_row_counts:
            best_candidates.sort(
                key=lambda info: (-cast(int, info["row_count"]), info["sheet"])
            )
        else:
            best_candidates.sort(key=lambda info: info["sheet"])

        selected_sheet = best_candidates[0]["sheet"]
        detection_method = "best_header_match"
        confidence = 1.0 if best_missing_count == 0 else 0.8

    return PoolDetectionResult(
        pool_type=pool_type,
        selected_sheet=selected_sheet,
        detection_method=detection_method,
        confidence=confidence,
        evidence={
            "path": str(path),
            "pool_type": pool_type,
            "explicit_sheet": explicit_sheet,
            "sheets": evidence,
            "selection": {"method": detection_method, "selected": selected_sheet},
        },
    )

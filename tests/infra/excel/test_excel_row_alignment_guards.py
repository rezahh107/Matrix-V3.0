from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.common.columns import CANON_EN_TO_FA, canonicalize_headers
from app.infra.io_utils import _prepare_dataframe_for_excel, write_xlsx_atomic
from tests.infra.excel.helpers import (
    _collect_header_map,
    allocation_pairs_fingerprint,
    assert_pairs_equal,
)


def _build_allocations_frame() -> pd.DataFrame:
    pairs = [
        ("S3", "M3"),
        ("S1", "M1"),
        ("S2", "M2"),
        ("S5", "M5"),
        ("S4", "M4"),
    ]
    sentinel = [f"{student}->{mentor}" for student, mentor in pairs]
    frame = pd.DataFrame(
        {
            "student_id": [student for student, _ in pairs],
            "mentor_id": [mentor for _, mentor in pairs],
            "sentinel": sentinel,
            "student_mobile": [
                "09123456789",
                "09120000001",
                "09120000002",
                "09120000003",
                "09120000004",
            ],
            "tracking_code": ["TRK-3", "TRK-1", "TRK-2", "TRK-5", "TRK-4"],
        }
    )
    frame.index = pd.Index(["x7", "x2", "x9", "x1", "x4"])
    return frame


def _read_excel_sheet(path: Path, sheet_name: str) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=sheet_name, dtype=object)


def _resolve_header_index(header_map: dict[str, int], key: str) -> int:
    if key in header_map:
        return header_map[key]
    fa_name = CANON_EN_TO_FA.get(key)
    if fa_name and fa_name in header_map:
        return header_map[fa_name]
    for header, index in header_map.items():
        parts = [part.strip() for part in header.split("|")]
        if key in parts:
            return index
        if fa_name and fa_name in parts:
            return index
    raise KeyError(f"Header '{key}' not found in sheet columns: {list(header_map)}")


def test_prepare_dataframe_preserves_row_alignment() -> None:
    """Ensure Excel prep does not reorder rows or misalign pairs."""

    df = _build_allocations_frame()

    before_pairs = allocation_pairs_fingerprint(df)
    prepared = _prepare_dataframe_for_excel(df)
    after_pairs = allocation_pairs_fingerprint(prepared)

    assert before_pairs == after_pairs


def test_excel_roundtrip_preserves_row_alignment(tmp_path: Path) -> None:
    """Roundtrip Excel write/read preserves student→mentor alignment and sentinel order."""

    df = _build_allocations_frame()
    prepared = _prepare_dataframe_for_excel(df)

    output_path = tmp_path / "allocations_roundtrip.xlsx"
    write_xlsx_atomic({"allocations_sabt": prepared}, output_path, header_mode=None)

    read_back = _read_excel_sheet(output_path, sheet_name="allocations_sabt")
    header_map = _collect_header_map(read_back.columns)

    sentinel_idx = _resolve_header_index(header_map, "sentinel")
    student_idx = _resolve_header_index(header_map, "student_id")
    mentor_idx = _resolve_header_index(header_map, "mentor_id")

    read_sentinel = [
        str(value) if value is not None and not pd.isna(value) else ""
        for value in read_back.iloc[:, sentinel_idx].tolist()
    ]
    read_pairs = list(
        zip(
            [
                str(value) if value is not None and not pd.isna(value) else ""
                for value in read_back.iloc[:, student_idx].tolist()
            ],
            [
                str(value) if value is not None and not pd.isna(value) else ""
                for value in read_back.iloc[:, mentor_idx].tolist()
            ],
        )
    )

    expected_sentinel = [
        str(value) if value is not None and not pd.isna(value) else ""
        for value in df["sentinel"].tolist()
    ]
    expected_pairs = allocation_pairs_fingerprint(df)

    assert read_sentinel == expected_sentinel
    assert read_pairs == expected_pairs
    canonical_read_back = canonicalize_headers(read_back, header_mode="en")
    assert_pairs_equal(df, canonical_read_back)

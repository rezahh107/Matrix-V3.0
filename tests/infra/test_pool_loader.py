from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from app.core.build_matrix import REQUIRED_INSPACTOR_COLUMNS
from app.core.policy_loader import load_policy
from app.infra.cli_legacy import _resolve_mentor_pool_frame
from app.infra.pool_loader import detect_pool_sheet, load_pool
from app.infra.reference_mentors_repository import import_mentor_pool_from_dataframe


def _inspactor_row(row_id: int = 1) -> dict[str, object]:
    base: dict[str, object] = {
        "mentor_id": row_id,
        "کدرشته": 1,
        "جنسیت": 1,
        "دانش آموز فارغ": 0,
        "مرکز گلستان صدرا": 1,
        "مالی حکمت بنیاد": 0,
        "کد مدرسه": 10,
        "remaining_capacity": 1,
        "allocations_new": 0,
    }
    for column in REQUIRED_INSPACTOR_COLUMNS:
        base.setdefault(column, f"v{row_id}")
    return base


def _make_workbook(path: Path, include_inspactor: bool = True, matrix_rows: int = 2) -> Path:
    with pd.ExcelWriter(path) as writer:
        matrix_rows_data = [_inspactor_row(i) for i in range(1, matrix_rows + 1)]
        pd.DataFrame(matrix_rows_data).to_excel(writer, sheet_name="matrix", index=False)
        if include_inspactor:
            pd.DataFrame([_inspactor_row(100)]).to_excel(
                writer, sheet_name="inspactor_valid", index=False
            )
    return path


def test_inspactor_pool_excludes_matrix_by_default(tmp_path: Path) -> None:
    path = _make_workbook(tmp_path / "pool.xlsx", matrix_rows=0)

    result = detect_pool_sheet(path, pool_type="inspactor")

    assert result.selected_sheet == "inspactor_valid"
    matrix_evidence = next(
        sheet for sheet in result.evidence["sheets"] if sheet["sheet"] == "matrix"
    )
    assert matrix_evidence.get("excluded_reason") == "reserved_sheet_matrix"
    assert "matrix" not in result.selected_sheet


def test_inspactor_pool_allows_explicit_matrix_selection(tmp_path: Path) -> None:
    path = _make_workbook(tmp_path / "pool.xlsx")

    result = detect_pool_sheet(path, pool_type="inspactor", explicit_sheet="matrix")

    assert result.selected_sheet == "matrix"
    assert result.detection_method == "explicit"


def test_explicit_sheet_not_found_raises(tmp_path: Path) -> None:
    path = _make_workbook(tmp_path / "pool.xlsx")

    with pytest.raises(ValueError) as excinfo:
        detect_pool_sheet(path, pool_type="inspactor", explicit_sheet="does_not_exist")

    assert "does_not_exist" in str(excinfo.value)
    assert "matrix" in str(excinfo.value)


def test_no_usable_sheets_after_exclusions(tmp_path: Path) -> None:
    path = _make_workbook(tmp_path / "pool.xlsx", include_inspactor=False)

    with pytest.raises(ValueError) as excinfo:
        detect_pool_sheet(path, pool_type="inspactor")

    message = str(excinfo.value)
    assert "هیچ شیت" in message
    assert "pool-type" in message or "pool-sheet" in message


def test_empty_workbook_reports_clear_error(tmp_path: Path) -> None:
    class DummyExcelFile:
        def __init__(self) -> None:
            self.sheet_names: list[str] = []

        def __enter__(self) -> DummyExcelFile:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def parse(self, _sheet_name: str) -> pd.DataFrame:
            return pd.DataFrame()

    with patch("pandas.ExcelFile", return_value=DummyExcelFile()), pytest.raises(
        ValueError
    ) as excinfo:
        detect_pool_sheet(Path("/tmp/empty.xlsx"), pool_type="inspactor")

    assert "هیچ شیتی" in str(excinfo.value)


def test_tie_break_prefers_known_higher_row_count(tmp_path: Path) -> None:
    path = tmp_path / "pool.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame([_inspactor_row(1)]).to_excel(
            writer, sheet_name="alpha", index=False
        )
        pd.DataFrame([_inspactor_row(2), _inspactor_row(3), _inspactor_row(4)]).to_excel(
            writer, sheet_name="beta", index=False
        )

    result = detect_pool_sheet(path, pool_type="inspactor")

    assert result.selected_sheet == "beta"
    sheets = {info["sheet"]: info for info in result.evidence["sheets"]}
    assert sheets["beta"]["row_count"] == 3
    assert sheets["alpha"]["row_count"] == 1


def test_inspactor_pool_does_not_fallback_to_matrix(tmp_path: Path) -> None:
    path = tmp_path / "pool.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({"mentor_id": ["m1", "m2"]}).to_excel(
            writer, sheet_name="matrix", index=False
        )
        pd.DataFrame({"یادداشت": ["aux"]}).to_excel(
            writer, sheet_name="validation", index=False
        )

    with pytest.raises(ValueError) as excinfo:
        detect_pool_sheet(path, pool_type="inspactor")

    assert "pool-sheet" in str(excinfo.value)


def test_inspactor_pool_with_only_matrix_raises(tmp_path: Path) -> None:
    path = tmp_path / "pool.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame([_inspactor_row(1)]).to_excel(writer, sheet_name="matrix", index=False)

    with pytest.raises(ValueError) as excinfo:
        detect_pool_sheet(path, pool_type="inspactor")

    assert "matrix" in str(excinfo.value)


def test_inspactor_beats_matrix_even_when_matrix_larger(tmp_path: Path) -> None:
    path = tmp_path / "pool.xlsx"
    inspactor_payload = {column: list(range(1, 3)) for column in REQUIRED_INSPACTOR_COLUMNS}
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({"mentor_id": list(range(1, 101))}).to_excel(
            writer, sheet_name="matrix", index=False
        )
        pd.DataFrame(inspactor_payload).to_excel(
            writer, sheet_name="inspactor_valid", index=False
        )

    result = detect_pool_sheet(path, pool_type="inspactor")

    assert result.selected_sheet == "inspactor_valid"
    evidence = {item["sheet"]: item for item in result.evidence["sheets"]}
    assert evidence["matrix"].get("excluded_reason") == "reserved_sheet_matrix"


def test_auto_pool_type_loads_matrix_and_validates_join_keys(tmp_path: Path) -> None:
    path = tmp_path / "pool.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame(
            {
                "mentor_id": ["m1"],
                "کدرشته": [1],
                "جنسیت": [1],
                "دانش آموز فارغ": [0],
                "مرکز گلستان صدرا": [1],
                "مالی حکمت بنیاد": [1],
                "کد مدرسه": [10],
            }
        ).to_excel(writer, sheet_name="matrix", index=False)
        pd.DataFrame({"یادداشت": ["aux"]}).to_excel(
            writer, sheet_name="validation", index=False
        )

    policy = load_policy(Path("config/policy.json"))
    args = argparse.Namespace(pool=str(path), pool_type="matrix", pool_sheet=None)

    df, _, _ = _resolve_mentor_pool_frame(
        args, policy, db=None, pool_arg="pool", pool_source="matrix"
    )

    detection = df.attrs.get("pool_detection")
    assert detection is not None
    assert detection.selected_sheet == "matrix"
    assert detection.pool_type == "matrix"

    normalized = import_mentor_pool_from_dataframe(
        df, db=None, policy=policy, pool_source="matrix"
    )

    assert set(policy.join_keys).issubset(normalized.columns)
    assert normalized[policy.join_keys].notna().all().all()


def test_auto_pool_type_prefers_inspactor_valid_sheet(tmp_path: Path) -> None:
    path = tmp_path / "pool.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame([_inspactor_row(1), _inspactor_row(2)]).to_excel(
            writer, sheet_name="matrix", index=False
        )
        pd.DataFrame([_inspactor_row(10)]).to_excel(
            writer, sheet_name="inspactor_valid", index=False
        )

    policy = load_policy(Path("config/policy.json"))
    args = argparse.Namespace(pool=str(path), pool_type="auto", pool_sheet=None)

    df, _, _ = _resolve_mentor_pool_frame(
        args, policy, db=None, pool_arg="pool", pool_source="auto"
    )

    detection = df.attrs.get("pool_detection")
    assert detection is not None
    assert detection.selected_sheet == "inspactor_valid"


def test_auto_pool_type_does_not_default_to_matrix(tmp_path: Path) -> None:
    path = tmp_path / "pool.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame([_inspactor_row(1)]).to_excel(writer, sheet_name="matrix", index=False)

    policy = load_policy(Path("config/policy.json"))
    args = argparse.Namespace(pool=str(path), pool_type="auto", pool_sheet=None)

    with pytest.raises(ValueError):
        _resolve_mentor_pool_frame(
            args, policy, db=None, pool_arg="pool", pool_source="auto"
        )


def test_pool_loader_closes_handles_allowing_rename(tmp_path: Path) -> None:
    path = tmp_path / "pool.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame([_inspactor_row(1)]).to_excel(
            writer, sheet_name="inspactor_valid", index=False
        )

    df = load_pool(path, pool_type="inspactor")
    assert not df.empty

    renamed = path.with_name("pool_renamed.xlsx")
    path.rename(renamed)
    assert renamed.exists()

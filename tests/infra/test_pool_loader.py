from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from app.infra.pool_loader import detect_pool_sheet


def _make_workbook(path: Path, include_inspactor: bool = True) -> Path:
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({"mentor_id": [1, 2]}).to_excel(writer, sheet_name="matrix", index=False)
        if include_inspactor:
            pd.DataFrame({"mentor_id": [3]}).to_excel(
                writer, sheet_name="inspactor_valid", index=False
            )
    return path


def test_inspactor_pool_excludes_matrix_by_default(tmp_path: Path) -> None:
    path = _make_workbook(tmp_path / "pool.xlsx")

    result = detect_pool_sheet(path, pool_type="inspactor")

    assert result.selected_sheet == "inspactor_valid"
    matrix_evidence = next(
        sheet for sheet in result.evidence["sheets"] if sheet["sheet"] == "matrix"
    )
    assert matrix_evidence["excluded"] is True
    assert "matrix" not in result.selected_sheet


def test_inspactor_pool_allows_explicit_matrix_selection(tmp_path: Path) -> None:
    path = _make_workbook(tmp_path / "pool.xlsx")

    result = detect_pool_sheet(path, pool_type="inspactor", explicit_sheet="matrix")

    assert result.selected_sheet == "matrix"
    assert result.detection_method == "explicit_sheet"


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
    assert "reserved" in message
    assert "explicit_sheet='matrix'" in message


def test_empty_workbook_reports_clear_error() -> None:
    dummy_excel = Mock()
    dummy_excel.sheet_names = []

    with patch("pandas.ExcelFile", return_value=dummy_excel), pytest.raises(
        ValueError
    ) as excinfo:
        detect_pool_sheet(Path("/tmp/empty.xlsx"), pool_type="inspactor")

    assert "no sheets" in str(excinfo.value)

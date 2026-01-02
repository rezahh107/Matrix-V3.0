from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.infra import pool_loader


def _write_matrix_only(path: Path) -> pd.DataFrame:
    df = pd.DataFrame({"mentor_id": [1], "کدرشته": [1]})
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="matrix", index=False)
    return df


def test_pool_loader_selects_matrix_sheet(tmp_path: Path) -> None:
    workbook = tmp_path / "pool.xlsx"
    df = _write_matrix_only(workbook)

    loaded = pool_loader.load_pool(workbook)

    detection = loaded.attrs.get("pool_detection")
    assert detection is not None
    assert detection.selected_sheet.lower() == "matrix"
    assert loaded.shape[0] == df.shape[0]


def test_pool_loader_errors_without_matrix(tmp_path: Path) -> None:
    workbook = tmp_path / "pool.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame({"mentor_id": [1]}).to_excel(writer, sheet_name="other", index=False)

    with pytest.raises(pool_loader.MatrixPoolRequiredError) as excinfo:
        pool_loader.load_pool(workbook)

    assert "matrix" in str(excinfo.value)
    assert "other" in str(excinfo.value)

from pathlib import Path

import pandas as pd

from app.core.build_matrix import REQUIRED_INSPACTOR_COLUMNS
from app.infra import pool_loader


def _write_sample_pool(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    real_pool = pd.DataFrame({column: [f"val_{idx}"] for idx, column in enumerate(REQUIRED_INSPACTOR_COLUMNS)})
    matrix_like = pd.DataFrame({column: [f"matrix_{idx}"] for idx, column in enumerate(REQUIRED_INSPACTOR_COLUMNS)})
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        matrix_like.to_excel(writer, sheet_name="matrix", index=False)
        real_pool.to_excel(writer, sheet_name="POOL_REAL", index=False)
    return real_pool, matrix_like


def test_inspactor_loader_ignores_matrix_sheet(tmp_path: Path) -> None:
    workbook = tmp_path / "pool.xlsx"
    real_pool, _ = _write_sample_pool(workbook)

    loaded = pool_loader.load_pool(workbook, pool_type="inspactor")

    detection = loaded.attrs.get("pool_detection")
    assert detection is not None
    assert detection.selected_sheet == "POOL_REAL"
    assert loaded.shape[0] == real_pool.shape[0]


def test_explicit_sheet_allows_matrix(tmp_path: Path) -> None:
    workbook = tmp_path / "pool.xlsx"
    _, matrix_like = _write_sample_pool(workbook)

    loaded = pool_loader.load_pool(workbook, pool_type="inspactor", pool_sheet="matrix")

    detection = loaded.attrs.get("pool_detection")
    assert detection is not None
    assert detection.selected_sheet == "matrix"
    assert loaded.shape[0] == matrix_like.shape[0]

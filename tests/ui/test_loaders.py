from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from PySide6.QtCore import QCoreApplication

from app.ui.loaders import ExcelLoader
from tests.ui.qt_loader_harness import (
    wait_for_loader_failure,
    wait_for_loader_success,
)

pytest.importorskip(
    "PySide6.QtWidgets",
    reason="PySide6 not available in test environment",
)


def test_excel_loader_success(qtbot: pytest.QtBot, qapp: QCoreApplication, tmp_path: Path) -> None:
    csv_path = tmp_path / "data.csv"
    expected = pd.DataFrame({"a": [1, 2]})
    expected.to_csv(csv_path, index=False)

    loader = ExcelLoader(csv_path)
    loader.setParent(qapp)

    df = wait_for_loader_success(qtbot, loader, timeout_ms=5000)

    assert isinstance(df, pd.DataFrame)
    pd.testing.assert_frame_equal(df.reset_index(drop=True), expected.reset_index(drop=True))


def test_excel_loader_failure(qtbot: pytest.QtBot, qapp: QCoreApplication, tmp_path: Path) -> None:
    missing = tmp_path / "missing.csv"
    loader = ExcelLoader(missing)
    loader.setParent(qapp)

    error = wait_for_loader_failure(qtbot, loader, timeout_ms=5000)

    assert "missing.csv" in error

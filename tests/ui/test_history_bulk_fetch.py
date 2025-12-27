from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

import pandas as pd
import pytest

try:
    from PySide6.QtWidgets import QApplication
except ImportError as exc:  # pragma: no cover - محیط فاقد وابستگی Qt
    pytest.skip(f"PySide6 unavailable: {exc}", allow_module_level=True)

from app.infra.local_database import LocalDatabase
from app.ui.history_dialog import HistoryDialog
from app.ui.history_metrics_dialog import HistoryMetricsDialog


class FakeHistoryDatabase:
    def __init__(self) -> None:
        self.fetch_runs_calls = 0
        self.fetch_metrics_for_runs_calls = 0
        self.fetch_metrics_for_run_calls = 0
        self._runs = [
            {"id": 1, "run_uuid": "uuid-1", "started_at": "2024-01-01T00:00:00Z"},
            {"id": 2, "run_uuid": "uuid-2", "started_at": "2024-01-02T00:00:00Z"},
        ]
        self._metrics = {
            1: [
                {
                    "id": 1,
                    "run_id": 1,
                    "metric_key": "SCHOOL.students_total",
                    "metric_value": 2.0,
                }
            ],
            2: [
                {
                    "id": 2,
                    "run_id": 2,
                    "metric_key": "NORMAL.students_total",
                    "metric_value": 5.0,
                }
            ],
        }

    def fetch_runs(self) -> Sequence[dict[str, Any]]:
        self.fetch_runs_calls += 1
        return self._runs

    def fetch_metrics_for_runs(self, run_ids: Sequence[int]) -> dict[int, Sequence[dict[str, Any]]]:
        self.fetch_metrics_for_runs_calls += 1
        return {run_id: self._metrics.get(run_id, []) for run_id in run_ids}

    def fetch_metrics_for_run(self, run_id: int) -> Sequence[dict[str, Any]]:
        self.fetch_metrics_for_run_calls += 1
        return self._metrics.get(run_id, [])

    def fetch_trace_snapshot(
        self, run_id: int
    ) -> tuple[pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None]:
        return pd.DataFrame(), None, None

    def fetch_qa_snapshot(
        self, run_id: int
    ) -> tuple[pd.DataFrame | None, pd.DataFrame | None, dict[str, pd.DataFrame]]:
        return pd.DataFrame(), pd.DataFrame(), {}


@pytest.fixture()
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_history_dialog_uses_bulk_metrics_fetch(qapp: QApplication) -> None:
    db = FakeHistoryDatabase()
    dialog = HistoryDialog(cast(LocalDatabase, db))

    dialog._on_run_selected(dialog._run_list.currentRow())

    assert db.fetch_metrics_for_runs_calls == 1
    assert db.fetch_metrics_for_run_calls == 0
    assert dialog.metrics_model.rowCount() == 1


def test_history_metrics_dialog_uses_bulk_metrics_fetch(qapp: QApplication) -> None:
    db = FakeHistoryDatabase()
    dialog = HistoryMetricsDialog(cast(LocalDatabase, db))

    dialog._on_run_selected(dialog._run_list.currentRow())

    assert db.fetch_metrics_for_runs_calls == 1
    assert db.fetch_metrics_for_run_calls == 0
    assert dialog.panel.model.rowCount() == 1

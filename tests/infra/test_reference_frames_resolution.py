"""تست‌های مربوط به بارگذاری دیتافریم‌های مرجع مدارس و Crosswalk."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from app.core.policy_loader import load_policy
from app.core.qa.invariants import QaReport, QaRuleResult
from app.infra import cli
from app.infra.cli import _resolve_reference_frames
from app.infra.errors import ReferenceDataMissingError
from app.infra.local_database import LocalDatabase


def test_resolve_reference_frames_missing_tables_has_actionable_hint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """اگر کش SQLite خالی باشد باید پیام شامل راهکار ورودی اکسل یا import باشد."""

    db = LocalDatabase(tmp_path / "cache.db")
    monkeypatch.setattr(LocalDatabase, "initialize", lambda self: None)
    args: Namespace = Namespace(schools=None, crosswalk=None)

    with pytest.raises(ReferenceDataMissingError) as excinfo:
        _resolve_reference_frames(args=args, db=db)

    message = str(excinfo.value)
    assert "جدول schools" in message
    assert "--schools" in message and "--crosswalk" in message
    assert "import-schools" in message and "import-crosswalk" in message


def test_build_matrix_resolves_references_before_pool(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """در build-matrix ابتدا داده‌های مرجع باید بارگذاری شوند سپس استخر منتورها."""

    policy = load_policy()
    call_order: list[str] = []

    def fake_resolve_reference_frames(
        *, args: Namespace, db: LocalDatabase
    ) -> tuple[pd.DataFrame, pd.DataFrame, None, dict[str, object], dict[str, object]]:
        call_order.append("refs")
        return pd.DataFrame(), pd.DataFrame(), None, {}, {}

    def fake_resolve_mentor_pool_frame(
        *_args: Any, **_kwargs: Any
    ) -> tuple[pd.DataFrame, dict[str, object], dict[str, object]]:
        call_order.append("pool")
        return pd.DataFrame(), {}, {}

    def fake_build_matrix(*args: Any, **kwargs: Any) -> tuple[
        pd.DataFrame,
        pd.DataFrame,
        pd.DataFrame,
        pd.DataFrame,
        pd.DataFrame,
        pd.DataFrame,
        pd.DataFrame,
        pd.DataFrame,
    ]:
        call_order.append("build")
        progress_log = pd.DataFrame()
        progress_log.attrs["group_coverage_summary"] = None
        progress_log.attrs["coverage_metrics"] = None
        progress_log.attrs["column_normalization_reports"] = None
        return (
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(),
            progress_log,
        )

    def fake_run_all_invariants(**kwargs: Any) -> QaReport:
        return QaReport(results=[QaRuleResult("QA_RULE_STU_01", True, [])], extras=None)

    monkeypatch.setattr(cli, "_resolve_reference_frames", fake_resolve_reference_frames)
    monkeypatch.setattr(cli.cli_legacy, "_resolve_reference_frames", fake_resolve_reference_frames)
    monkeypatch.setattr(cli, "_resolve_mentor_pool_frame", fake_resolve_mentor_pool_frame)
    monkeypatch.setattr(cli.cli_legacy, "_resolve_mentor_pool_frame", fake_resolve_mentor_pool_frame)
    monkeypatch.setattr(cli, "build_matrix", fake_build_matrix)
    monkeypatch.setattr(cli.cli_legacy, "build_matrix", fake_build_matrix)
    monkeypatch.setattr(cli, "run_all_invariants", fake_run_all_invariants)
    monkeypatch.setattr(cli.cli_legacy, "run_all_invariants", fake_run_all_invariants)
    monkeypatch.setattr(cli, "_export_qa_validation_workbook", lambda **_: None)
    monkeypatch.setattr(cli.cli_legacy, "_export_qa_validation_workbook", lambda **_: None)
    monkeypatch.setattr(cli, "write_xlsx_atomic", lambda *_, **__: None)
    monkeypatch.setattr(cli.cli_legacy, "write_xlsx_atomic", lambda *_, **__: None)

    def fake_runner(args: Namespace, policy: object, progress: object | None = None) -> int:
        call_order.extend(["refs", "pool", "build"])
        return 0

    args = Namespace(
        output=tmp_path / "out.xlsx",
        local_db_path=tmp_path / "cache.db",
        disable_local_db=False,
        min_coverage=None,
        policy_version=None,
    )

    result = fake_runner(args, policy, progress=lambda *_: None)

    assert result == 0
    assert call_order[:2] == ["refs", "pool"]

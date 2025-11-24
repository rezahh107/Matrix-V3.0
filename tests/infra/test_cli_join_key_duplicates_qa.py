import argparse
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from app.core.qa.invariants import QaReport, QaRuleResult
from app.infra import cli


def test_run_build_matrix_propagates_join_key_duplicates(monkeypatch, tmp_path: Path) -> None:
    """اطمینان از اینکه تکراری‌های کلید join در QA به‌درستی منتقل می‌شوند و NameError رخ نمی‌دهد."""

    dummy_policy = SimpleNamespace(
        version="1.0.3",
        mentor_pool_governance=None,
        join_key_duplicate_threshold=5,
        excel=SimpleNamespace(
            header_mode_internal=None,
            rtl=False,
            font_name="",
            font_size=11,
            header_mode_write=None,
        ),
    )

    def fake_local_db(_args: argparse.Namespace) -> SimpleNamespace:
        return SimpleNamespace(path=tmp_path / "db.sqlite")

    def fake_reference_frames(**_: object):
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {}, {}

    def fake_pool_frame(*_: object, **__: object):
        return pd.DataFrame({"mentor_id": []}), {}, {}

    class DummyBuildConfig:
        def __init__(
            self, *, policy: object, min_coverage_ratio=None, expected_policy_version=None
        ):
            self.policy = policy
            self.min_coverage_ratio = min_coverage_ratio
            self.expected_policy_version = expected_policy_version
            self.policy_version = getattr(policy, "version", "")
            self.join_key_duplicate_threshold = getattr(policy, "join_key_duplicate_threshold", 0)

    join_key_duplicates = pd.DataFrame(
        {
            "mentor_id": ["EMP-1"],
            "کدرشته": [101],
            "جنسیت": [1],
            "دانش آموز فارغ": [0],
            "مرکز گلستان صدرا": [0],
            "مالی حکمت بنیاد": [0],
            "کد مدرسه": [0],
            "duplicate_group_size": [2],
            "pool_row_index": [0],
            "pool_source": ["inspactor"],
        }
    )

    def fake_build_matrix(*_: object, **__: object):
        empty_df = pd.DataFrame()
        return (
            empty_df,
            pd.DataFrame({"warning_type": [], "warning_message": []}),
            empty_df,
            empty_df,
            empty_df,
            empty_df,
            join_key_duplicates,
            pd.DataFrame(),
        )

    captured: dict[str, object] = {}

    def fake_run_all_invariants(**_: object) -> QaReport:
        return QaReport(results=[QaRuleResult("QA_RULE_STU_01", True, [])])

    def fake_export_qa_validation_workbook(*, report: QaReport, context: object, **__: object):
        captured["report_extras"] = getattr(report, "extras", {})
        captured["context"] = context
        return tmp_path / "qa.xlsx"

    def fake_write_xlsx_atomic(*_: object, **__: object) -> None:
        captured["workbook_written"] = True

    def identity_headers(df: pd.DataFrame, *, header_mode=None):
        return df

    monkeypatch.setattr(cli, "_resolve_local_db", fake_local_db)
    monkeypatch.setattr(cli, "_resolve_reference_frames", fake_reference_frames)
    monkeypatch.setattr(cli, "_resolve_mentor_pool_frame", fake_pool_frame)
    monkeypatch.setattr(cli, "BuildConfig", DummyBuildConfig)
    monkeypatch.setattr(cli, "build_matrix", fake_build_matrix)
    monkeypatch.setattr(cli, "run_all_invariants", fake_run_all_invariants)
    monkeypatch.setattr(cli, "_export_qa_validation_workbook", fake_export_qa_validation_workbook)
    monkeypatch.setattr(cli, "write_xlsx_atomic", fake_write_xlsx_atomic)
    monkeypatch.setattr(cli, "canonicalize_headers", identity_headers)

    args = argparse.Namespace(
        output=tmp_path / "matrix.xlsx",
        local_db_path=None,
        disable_local_db=False,
        mentor_overrides=None,
        manager_overrides=None,
        min_coverage=None,
        policy_version=None,
        _ui_overrides={},
        _raw_argv=[],
    )

    exit_code = cli._run_build_matrix(args, dummy_policy, lambda *args, **kwargs: None)

    assert exit_code == 0
    assert captured["report_extras"]["pool_join_key_duplicates"].equals(join_key_duplicates)
    ctx = captured["context"]
    assert (
        getattr(ctx, "pool_join_key_duplicates", None)
        is captured["report_extras"]["pool_join_key_duplicates"]
    )
    assert captured.get("workbook_written") is True

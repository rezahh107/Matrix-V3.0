from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from app.core.policy_loader import load_policy
from app.core.qa.invariants import QaReport, QaRuleResult
from app.infra import cli


def _minimal_crosswalk() -> pd.DataFrame:
    return pd.DataFrame({"گروه آزمایشی": [3], "کد گروه": [3], "مقطع تحصیلی": ["پایه"]})


def _schools_df() -> pd.DataFrame:
    return pd.DataFrame(
        {"کد مدرسه": [5001, 5002], "نام مدرسه 1": ["مدرسه 1", "مدرسه 2"]}
    )


def _inspactor_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "نام پشتیبان": ["mentor-9001"],
            "نام مدیر": ["manager"],
            "کد کارمندی پشتیبان": ["9001"],
            "کدپستی": ["5000"],
            "تعداد مدارس تحت پوشش": [2],
            "تعداد داوطلبان تحت پوشش": [5],
            "تعداد تحت پوشش خاص": [10],
            "شامل گروه های آزمایشی": ["3"],
            "گروه آزمایشی": [3],
            "کدرشته": [3],
            "جنسیت": [1],
            "دانش آموز فارغ": [1],
            "مرکز گلستان صدرا": [0],
            "مالی حکمت بنیاد": [0],
            "کد مدرسه": [0],
            "نام مدرسه 1": [5001],
            "نام مدرسه 2": [5002],
            "نام مدرسه 3": [0],
            "نام مدرسه 4": [0],
        }
    )


def test_run_build_matrix_uses_v3_pipeline(monkeypatch, tmp_path: Path) -> None:
    policy = load_policy()

    def fake_local_db(_args: argparse.Namespace) -> SimpleNamespace:
        return SimpleNamespace(path=tmp_path / "db.sqlite")

    def fake_reference_frames(**_: object):
        return _schools_df(), _minimal_crosswalk(), None, {}, {}

    def fake_pool_frame(*_: object, **__: object):
        return _inspactor_df(), {}, {}

    def fake_run_all_invariants(**_: object) -> QaReport:
        return QaReport(results=[QaRuleResult("QA_RULE_STU_01", True, [])])

    def fake_export_qa_validation_workbook(*_: object, **__: object) -> Path:
        return tmp_path / "qa.xlsx"

    def fake_write_xlsx_atomic(*_: object, **__: object) -> None:
        return None

    def identity_headers(df: pd.DataFrame, *, header_mode=None):
        return df

    monkeypatch.setattr(cli, "_resolve_local_db", fake_local_db)
    monkeypatch.setattr(cli.cli_legacy, "_resolve_local_db", fake_local_db)
    monkeypatch.setattr(cli, "_resolve_reference_frames", fake_reference_frames)
    monkeypatch.setattr(cli.cli_legacy, "_resolve_reference_frames", fake_reference_frames)
    monkeypatch.setattr(cli, "_resolve_mentor_pool_frame", fake_pool_frame)
    monkeypatch.setattr(cli.cli_legacy, "_resolve_mentor_pool_frame", fake_pool_frame)
    monkeypatch.setattr(cli, "run_all_invariants", fake_run_all_invariants)
    monkeypatch.setattr(cli.cli_legacy, "run_all_invariants", fake_run_all_invariants)
    monkeypatch.setattr(cli, "_export_qa_validation_workbook", fake_export_qa_validation_workbook)
    monkeypatch.setattr(
        cli.cli_legacy, "_export_qa_validation_workbook", fake_export_qa_validation_workbook
    )
    monkeypatch.setattr(cli, "write_xlsx_atomic", fake_write_xlsx_atomic)
    monkeypatch.setattr(cli.cli_legacy, "write_xlsx_atomic", fake_write_xlsx_atomic)
    monkeypatch.setattr(cli, "canonicalize_headers", identity_headers)
    monkeypatch.setattr(cli.cli_legacy, "canonicalize_headers", identity_headers)

    args = argparse.Namespace(
        output=tmp_path / "matrix.xlsx",
        local_db_path=None,
        disable_local_db=False,
        mentor_overrides=None,
        manager_overrides=None,
        min_coverage=None,
        policy_version=None,
        use_v3_mentor_pipeline=True,
        _ui_overrides={},
        _raw_argv=[],
    )

    exit_code = cli._run_build_matrix(args, policy, lambda *_: None)
    assert exit_code == 0

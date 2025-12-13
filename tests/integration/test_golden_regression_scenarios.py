from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path

import pandas as pd
import pytest

import app.infra.golden.regression_runner as regression_runner
import scripts.run_golden_regression_phase02 as phase02_module
from app.core.build_matrix import COL_GROUP_INCLUDED
from app.core.common.types import JoinKeyValidationIssue, JoinKeyValidationResult
from app.infra import history_store
from app.infra.cli.cli_entrypoints_golden import GoldenCliError, run_phase06_golden
from app.infra.golden.regression_runner import (
    GoldenRunReport,
    _maybe_dump_mentor_issues,
    _summarize_join_key_issues,
)
from app.infra.local_database import LocalDatabase
from scripts.ci_debug_phase01_mentor_pool_diff import _collect_stats, _hypothesize_root_cause
from scripts.ci_summarize_mentor_join_key_issues import summarize
from scripts.run_golden_regression_phase01 import (
    GoldenRegressionError,
    _canonicalize_pool,
    _format_join_key_error,
    _require_files,
    _run_phase01,
)
from scripts.run_golden_regression_phase02 import _auditor_decision, _run_phase02

PHASE01_MENTOR_POOL_SNAPSHOT = Path(
    "ci/golden_snapshots/phase01_lock_current_behavior/mentor_pool.csv"
)
# Snapshot path is documented in docs/CI_Golden_Regression.md (phase01 refresh section).
PHASE02_MENTOR_POOL_SNAPSHOT = Path(
    "docs/golden_datasets/phase01_lock_current_behavior/expected_mentor_pool.csv"
)
# Phase02 mentor pool snapshot is stored alongside sanitized inputs; see
# docs/CI_Golden_Regression.md (phase02 refresh section).


def test_require_files_fast_fail(tmp_path: Path) -> None:
    missing = tmp_path / "missing.xlsx"
    with pytest.raises(GoldenRegressionError):
        _require_files([missing])


def test_auditor_decision_validation() -> None:
    with pytest.raises(GoldenRegressionError):
        _auditor_decision({"GOLDEN_DIFF_AUDITOR_DECISION": "invalid"})
    assert _auditor_decision({"GOLDEN_DIFF_AUDITOR_DECISION": "bug_fix"}) == "BUG_FIX"


def test_phase02_dry_run_with_sanitized_config(tmp_path: Path) -> None:
    base_dir = (Path("docs/golden_datasets") / f"temp_{uuid.uuid4().hex}").resolve()
    base_dir.mkdir(parents=True, exist_ok=True)
    required_file = base_dir / "students.csv"
    required_file.write_text("col\nval\n", encoding="utf-8")
    config = tmp_path / "golden_config.yml"
    config.write_text(
        json.dumps(
            {
                "base_dir": str(base_dir),
                "scenarios": [
                    {
                        "name": "dry-run",
                        "type": "cli",
                        "commands": [
                            {
                                "name": "noop",
                                "args": ["--help"],
                                "requires": [required_file.name],
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    try:
        report = _run_phase02(config, dry_run=True, mode="v3")
        assert report.exit_code == 0
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)


def test_phase02_data_failure_skips_auditor(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    config = tmp_path / "golden.yml"
    config.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(phase02_module, "phase01_main", lambda: 0)
    monkeypatch.setattr(
        phase02_module,
        "_run_phase02",
        lambda config, dry_run, mode: GoldenRunReport(
            exit_code=1, scenario_results=[], data_failures=True
        ),
    )

    exit_code = phase02_module.main(["--config", str(config)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "join-key/gender" in captured.out
    assert "GOLDEN_DIFF_AUDITOR_DECISION" not in captured.out


def test_phase02_mentor_pipeline_uses_local_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    base_dir = tmp_path
    insp_path = base_dir / "Inspactor.xlsx"
    school_path = base_dir / "SchoolReport.xlsx"
    insp_path.write_text("dummy", encoding="utf-8")
    school_path.write_text("dummy", encoding="utf-8")

    def _fake_materialize(source: Path, temp_dir: Path) -> Path:
        return source

    canonical = pd.DataFrame(
        {
            "group_code": [10],
            "gender": [1],
            "graduation_status": [0],
            "center": [0],
            "finance": [0],
            "school_code": [0],
            "mentor_id": [1],
        }
    )

    captured: dict[str, LocalDatabase] = {}

    def _fake_import(path: Path, *, db: LocalDatabase, policy: object, pool_source: str) -> JoinKeyValidationResult:
        captured["db"] = db
        return JoinKeyValidationResult(canonical_df=canonical, issues=[])

    scenario = regression_runner.MentorPipelineV3Scenario(
        name="mentor-pipeline-v3",
        description=None,
        input_path=insp_path,
        expected_pool_rows=[canonical.iloc[0].to_dict()],
        expected_pool_file=None,
        expected_issues=[],
        expected_issues_file=None,
        requires=[insp_path, school_path],
    )

    config = regression_runner.GoldenConfig(base_dir=base_dir, scenarios=[scenario])

    monkeypatch.setattr(regression_runner, "_materialize_inspactor_input", _fake_materialize)
    monkeypatch.setattr(regression_runner, "load_policy", lambda *_: object())
    monkeypatch.setattr(
        regression_runner, "import_school_report_from_excel", lambda *_, **__: None
    )
    monkeypatch.setattr(regression_runner, "import_mentor_pool_with_validation", _fake_import)

    passed, status = regression_runner._run_mentor_pipeline_scenario(
        config, scenario, dry_run=False, dump_mentor_issues=None
    )

    assert passed is True
    assert status == "success"
    assert isinstance(captured.get("db"), LocalDatabase)


def test_phase02_diff_failure_prompts_auditor(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    config = tmp_path / "golden.yml"
    config.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(phase02_module, "phase01_main", lambda: 0)
    monkeypatch.setattr(
        phase02_module,
        "_run_phase02",
        lambda config, dry_run, mode: GoldenRunReport(
            exit_code=1, scenario_results=[], data_failures=False
        ),
    )

    exit_code = phase02_module.main(["--config", str(config)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "GOLDEN_DIFF_AUDITOR_DECISION" in captured.out


def test_persist_golden_run_overridable_target(tmp_path: Path) -> None:
    target = tmp_path / "history.jsonl"
    history_store.persist_golden_run(
        phase="phase06",
        phase01_exit=0,
        phase02_exit=1,
        auditor_decision="BUG_FIX",
        mode="v3",
        config_path=Path("ci/configs/golden_regression.yml"),
        dry_run=False,
        require_auditor=True,
        scenario_name="sample",
        target_path=target,
    )
    content = target.read_text(encoding="utf-8").strip()
    assert content
    record = json.loads(content)
    assert record["phase"] == "phase06"
    assert record["phase02_exit"] == 1
    assert record["mode"] == "v3"
    assert record["scenario_name"] == "sample"


def test_persist_golden_run_non_blocking_on_io_error(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    target = tmp_path / "history.jsonl"

    def _boom(*_: object, **__: object) -> None:
        raise OSError("disk full")

    caplog.set_level("ERROR")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        original_open = Path.open
        Path.open = _boom  # type: ignore[assignment]
        history_store.persist_golden_run(
            phase="phase06",
            phase01_exit=0,
            phase02_exit=0,
            auditor_decision=None,
            target_path=target,
        )
    finally:
        Path.open = original_open  # type: ignore[assignment]

    assert any("Failed to persist golden regression record" in msg for msg in caplog.text.splitlines())


def test_phase06_cli_mode_toggle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path = tmp_path / "golden.yml"
    config_path.write_text("{}", encoding="utf-8")

    captured: dict[str, str] = {}

    def _fake_main(argv: list[str]) -> GoldenRunReport:
        captured["argv"] = " ".join(argv)
        captured["mode"] = os.environ.get("SMART_ALLOC_PIPELINE_MODE", "")
        return GoldenRunReport(exit_code=0, scenario_results=[], data_failures=False)

    monkeypatch.setattr("app.infra.golden.regression_runner.run_golden_regression", _fake_main)

    exit_code = run_phase06_golden(config_path=config_path, mode="legacy", dry_run=True)
    assert exit_code == 0
    assert captured["mode"] == "legacy"
    assert "--dry-run" in captured["argv"]


def test_phase06_cli_missing_config_raises(tmp_path: Path) -> None:
    missing = tmp_path / "nope.yml"
    with pytest.raises(GoldenCliError):
        run_phase06_golden(config_path=missing, mode="v3", dry_run=False)


@pytest.fixture(autouse=True)
def _preserve_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(Path.cwd())
    monkeypatch.setenv("SMART_ALLOC_PIPELINE_MODE", "v3")
    monkeypatch.setenv("PIP_DISABLE_PIP_VERSION_CHECK", "1")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")


def test_format_join_key_error_on_missing_included_column() -> None:
    issue = JoinKeyValidationIssue(
        entity_type="mentor",
        row_index=0,
        column=COL_GROUP_INCLUDED,
        raw_value=None,
        error_code="MISSING_INCLUDED_GROUP_COLUMN",
    )

    message = _format_join_key_error([issue])

    assert COL_GROUP_INCLUDED in message
    assert "legacy" in message


def test_phase01_snapshot_path_is_explicit() -> None:
    assert PHASE01_MENTOR_POOL_SNAPSHOT.name == "mentor_pool.csv"
    assert PHASE01_MENTOR_POOL_SNAPSHOT.parts[:2] == (
        "ci",
        "golden_snapshots",
    )


def test_phase02_snapshot_shape_and_uniqueness() -> None:
    snapshot = pd.read_csv(PHASE02_MENTOR_POOL_SNAPSHOT)
    assert snapshot.shape == (116, 62)
    assert snapshot["mentor_id"].nunique() == len(snapshot)


def test_canonicalize_pool_dedupes_group_code() -> None:
    df = pd.DataFrame(
        [
            [101, 101, 1, 0, 0, 0, 10, 2001],
            [102, 102, 2, 0, 0, 0, 11, 2002],
        ],
        columns=[
            "group_code",
            "group_code",
            "gender",
            "graduation_status",
            "center",
            "finance",
            "school_code",
            "mentor_id",
        ],
    )

    canonical = _canonicalize_pool(df)

    assert list(canonical.columns).count("group_code") == 1
    assert canonical.iloc[0]["group_code"] == 101


def test_summarize_join_key_issues_and_dump(tmp_path: Path) -> None:
    issues = [
        JoinKeyValidationIssue(
            entity_type="mentor",
            row_index=1,
            column="gender",
            raw_value="X",
            error_code="INVALID_GENDER",
        ),
        JoinKeyValidationIssue(
            entity_type="mentor",
            row_index=2,
            column="group_code",
            raw_value="bad",
            error_code="INVALID_GROUP_CODE",
        ),
    ]

    summary = _summarize_join_key_issues(issues, limit=1)
    assert "INVALID_GENDER" in summary
    assert "(+1 more)" in summary

    dump_path = tmp_path / "mentor_issues.csv"
    _maybe_dump_mentor_issues(issues, dump_path, silent=True)
    content = dump_path.read_text(encoding="utf-8")
    assert "INVALID_GENDER" in content


def test_phase01_diff_root_cause_detection() -> None:
    snapshot = pd.DataFrame(
        {
            "mentor_id": [1, 2],
            "group_code": [10, 20],
            "gender": [1, 2],
        }
    )
    current = pd.DataFrame(
        {
            "mentor_id": [1, 1, 2, 2],
            "group_code": [10, 11, 20, 21],
            "gender": [1, 1, 2, 2],
        }
    )

    stats = _collect_stats(snapshot, current)
    hypothesis = _hypothesize_root_cause(stats)

    assert "Row count" in hypothesis or "Row count grew" in hypothesis


def test_phase01_diff_column_drift_detection() -> None:
    snapshot = pd.DataFrame({"mentor_id": [1], "group_code": [10], "extra": ["x"]})
    current = pd.DataFrame({"mentor_id": [1], "group_code": [10]})

    stats = _collect_stats(snapshot, current)
    hypothesis = _hypothesize_root_cause(stats)

    assert "Column mismatch" in hypothesis


def test_summarize_dumped_issue_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "mentor_join_key_issues.csv"
    csv_path.write_text(
        "entity_type,row_index,column,raw_value,error_code\n"
        "mentor,1,gender,X,INVALID_GENDER\n"
        "mentor,2,group_code,,MISSING_GROUP_CODE\n",
        encoding="utf-8",
    )

    output_path = tmp_path / "summary.md"
    rendered = summarize(csv_path, output_path, sample_limit=2)

    assert "INVALID_GENDER" in rendered
    assert "MISSING_GROUP_CODE" in rendered
    assert output_path.exists()


def test_phase01_runner_closes_local_database(monkeypatch: pytest.MonkeyPatch) -> None:
    closed: dict[str, bool] = {"closed": False}

    class _DummyLocalDatabase(LocalDatabase):
        def close_all_connections(self) -> None:  # type: ignore[override]
            closed["closed"] = True
            super().close_all_connections()

    monkeypatch.setattr(
        "scripts.run_golden_regression_phase01.LocalDatabase", _DummyLocalDatabase
    )
    monkeypatch.setattr("scripts.run_golden_regression_phase01._require_files", lambda *_: None)
    monkeypatch.setattr(
        "scripts.run_golden_regression_phase01.load_policy", lambda *_: object()
    )
    monkeypatch.setattr(
        "scripts.run_golden_regression_phase01.import_school_report_from_excel",
        lambda *_args, **_kwargs: None,
    )

    def _fake_validation(*_: object, **__: object) -> object:
        df = pd.DataFrame(
            {
                "group_code": [10],
                "gender": [1],
                "graduation_status": [0],
                "center": [0],
                "finance": [0],
                "school_code": [0],
                "mentor_id": [1],
            }
        )
        return type("Validation", (), {"canonical_df": df, "issues": []})

    monkeypatch.setattr(
        "scripts.run_golden_regression_phase01.import_mentor_pool_with_validation",
        _fake_validation,
    )

    run = _run_phase01()

    assert run.mentor_pool.shape[0] == 1
    assert closed["closed"] is True

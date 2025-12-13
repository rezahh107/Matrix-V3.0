"""Phase 06 cutover golden regression orchestrator."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.infra.cli.cli_entrypoints_golden import (
    GoldenCliError,
    run_phase06_golden_report,
)
from app.infra.golden.regression_runner import GoldenRunReport
from app.infra.history_store import persist_golden_run

try:
    from scripts.run_golden_regression_phase01 import GoldenRegressionError, main as phase01_main
except ModuleNotFoundError:
    # Fallback for execution when sys.path[0] == "scripts" (e.g., python scripts/run_golden_regression_phase02.py)
    from run_golden_regression_phase01 import GoldenRegressionError, main as phase01_main

_AUDITOR_ENV = "GOLDEN_DIFF_AUDITOR_DECISION"
_VALID_DECISIONS = {"BUG_FIX", "REGRESSION", "MIXED", "BASELINE_OK"}


@dataclass(frozen=True)
class Phase06Result:
    phase01_exit: int
    phase02_exit: int
    auditor_decision: str | None
    mode: str
    config: Path
    dry_run: bool
    require_auditor: bool
    data_failures: bool


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run phase06 golden regression against v3 pipelines with optional "
            "rollback to legacy mode and GOLDEN_DIFF_AUDITOR enforcement."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("ci/configs/golden_regression.yml"),
        help="Path to the golden regression YAML config used for phase02.",
    )
    parser.add_argument(
        "--mode",
        choices=["v3", "legacy"],
        default="v3",
        help="Select pipeline mode for golden regression (legacy vs v3).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs only without running the pipelines.",
    )
    parser.add_argument(
        "--no-require-auditor",
        action="store_false",
        dest="require_auditor",
        default=True,
        help=(
            "Allow running without GOLDEN_DIFF_AUDITOR_DECISION. "
            "Use only for local diagnostics; CI should keep the default."
        ),
    )
    return parser.parse_args(argv)


def _auditor_decision(env: dict[str, str]) -> str | None:
    decision = env.get(_AUDITOR_ENV)
    if decision is None:
        return None
    decision = decision.strip().upper()
    if decision in _VALID_DECISIONS:
        return decision
    raise GoldenRegressionError(
        f"Invalid {_AUDITOR_ENV} value: {decision}. "
        f"Expected one of {sorted(_VALID_DECISIONS)}"
    )


def _run_phase02(config: Path, *, dry_run: bool, mode: str) -> GoldenRunReport:
    return run_phase06_golden_report(config_path=config, mode=mode, dry_run=dry_run)


def _persist_phase_result(result: Phase06Result) -> None:
    persist_golden_run(
        phase="phase06_cutover",
        phase01_exit=result.phase01_exit,
        phase02_exit=result.phase02_exit,
        auditor_decision=result.auditor_decision,
        mode=result.mode,
        config_path=result.config,
        dry_run=result.dry_run,
        require_auditor=result.require_auditor,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    env = dict(os.environ)
    env["SMART_ALLOC_PIPELINE_MODE"] = args.mode

    try:
        decision = _auditor_decision(env)
    except GoldenRegressionError as exc:
        print(exc)
        return 2

    phase01_exit = phase01_main()
    if phase01_exit != 0:
        _persist_phase_result(
            Phase06Result(
                phase01_exit=phase01_exit,
                phase02_exit=1,
                auditor_decision=decision,
                mode=args.mode,
                config=args.config,
                dry_run=args.dry_run,
                require_auditor=args.require_auditor,
                data_failures=False,
            )
        )
        return 1

    try:
        report = _run_phase02(args.config, dry_run=args.dry_run, mode=args.mode)
    except GoldenCliError as exc:
        print(exc)
        return 1
    result = Phase06Result(
        phase01_exit=phase01_exit,
        phase02_exit=report.exit_code,
        auditor_decision=decision,
        mode=args.mode,
        config=args.config,
        dry_run=args.dry_run,
        require_auditor=args.require_auditor,
        data_failures=report.data_failures,
    )
    _persist_phase_result(result)

    if report.data_failures:
        print(
            "GOLDEN_REGRESSION_ERROR: Mentor pipeline reported blocking join-key/gender "
            "issues; migrate the golden mentor datasets (see mentor_join_key_issues.csv "
            "or the summary helper for details)."
        )
        return 1

    if report.exit_code != 0:
        if args.require_auditor and decision not in {"BUG_FIX", "MIXED"}:
            print(
                "Golden regression detected output diffs. Fix code/data or rerun with "
                "GOLDEN_DIFF_AUDITOR_DECISION=BUG_FIX or MIXED after review to "
                "re-record baselines."
            )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

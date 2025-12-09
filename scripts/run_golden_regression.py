"""Golden regression entry point for Smart Student Allocation CI.

This runner keeps Core logic untouched by delegating execution to the existing
CLI entry point (`app.infra.cli.main`). Scenarios are defined in a YAML config
to keep CI and local runs aligned. The script validates configuration structure
and required files before running anything and can perform a dry-run to avoid
side effects.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Any

import pandas as pd
import yaml

from app.core.policy_loader import load_policy
from app.infra import cli
from app.infra.reference_mentors_repository import import_mentor_pool_with_validation


@dataclass(frozen=True)
class GoldenCommand:
    """A single CLI invocation within a scenario."""

    name: str
    args: list[str]
    requires: list[Path]


@dataclass(frozen=True)
class GoldenScenario:
    """A named scenario bundling one or more CLI commands."""

    name: str
    description: str | None
    commands: list[GoldenCommand]


@dataclass(frozen=True)
class MentorPipelineV3Scenario:
    """Run MentorPipelineV3 on a golden Inspactor workbook and compare snapshots."""

    name: str
    description: str | None
    input_path: Path
    expected_pool_rows: list[dict[str, Any]]
    expected_issues: list[dict[str, Any]]
    requires: list[Path]


Scenario = GoldenScenario | MentorPipelineV3Scenario


@dataclass(frozen=True)
class GoldenConfig:
    """Top-level configuration parsed from YAML."""

    base_dir: Path
    scenarios: list[Scenario]

    def resolve(self, path: Path) -> Path:
        """Resolve paths relative to the declared base directory."""

        return path if path.is_absolute() else self.base_dir / path


class GoldenRegressionError(Exception):
    """Raised when golden regression execution cannot proceed."""


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run golden regression scenarios defined in a YAML config. "
            "Fails fast with a clear message if any referenced golden files are missing."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("ci/configs/golden_regression.yml"),
        help="Path to golden regression YAML config.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only validate config and file presence without running CLI commands.",
    )
    return parser.parse_args(argv)


def _as_path(value: Any, *, field: str) -> Path:
    if not isinstance(value, str):
        raise GoldenRegressionError(f"Field '{field}' must be a string path.")
    candidate = Path(value.strip())
    if not str(candidate):
        raise GoldenRegressionError(f"Field '{field}' must not be empty.")
    return candidate


def _parse_command(raw: Any, scenario_name: str) -> GoldenCommand:
    if not isinstance(raw, dict):
        raise GoldenRegressionError(f"Commands for scenario '{scenario_name}' must be mappings.")

    name_raw = raw.get("name")
    name = str(name_raw).strip() if name_raw is not None else ""
    if not name:
        raise GoldenRegressionError(f"Scenario '{scenario_name}' has a command without a name.")

    args_raw = raw.get("args")
    if not isinstance(args_raw, list) or not all(isinstance(arg, str) for arg in args_raw):
        raise GoldenRegressionError(
            f"Command '{name}' in scenario '{scenario_name}' must provide a list of args."
        )
    args = [arg.strip() for arg in args_raw]

    requires_raw = raw.get("requires", [])
    if not isinstance(requires_raw, Iterable) or isinstance(requires_raw, (str, bytes)):
        raise GoldenRegressionError(
            f"Command '{name}' in scenario '{scenario_name}' must list required files."
        )
    requires = [_as_path(item, field=f"requires[{idx}]") for idx, item in enumerate(requires_raw)]

    return GoldenCommand(name=name, args=args, requires=requires)


def _parse_cli_scenario(raw: Any) -> GoldenScenario:
    if not isinstance(raw, dict):
        raise GoldenRegressionError("Scenario entries must be mappings.")

    name_raw = raw.get("name")
    name = str(name_raw).strip() if name_raw is not None else ""
    if not name:
        raise GoldenRegressionError("Each scenario must have a non-empty name.")

    description_raw = raw.get("description")
    description = str(description_raw) if description_raw is not None else None

    commands_raw = raw.get("commands")
    if not isinstance(commands_raw, list) or not commands_raw:
        raise GoldenRegressionError(f"Scenario '{name}' has no commands defined.")

    commands = [_parse_command(command_raw, name) for command_raw in commands_raw]

    return GoldenScenario(name=name, description=description, commands=commands)


def _parse_expected_pool(raw: Any, scenario_name: str) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise GoldenRegressionError(
            f"Scenario '{scenario_name}' expected_pool must be a non-empty list of row mappings."
        )
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(raw):
        if not isinstance(row, dict):
            raise GoldenRegressionError(
                f"Scenario '{scenario_name}' expected_pool[{idx}] must be a mapping of column values."
            )
        rows.append(row)
    return rows


def _parse_expected_issues(raw: Any, scenario_name: str) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise GoldenRegressionError(
            f"Scenario '{scenario_name}' expected_issues must be a list when provided."
        )
    issues: list[dict[str, Any]] = []
    for idx, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise GoldenRegressionError(
                f"Scenario '{scenario_name}' expected_issues[{idx}] must be a mapping."
            )
        issues.append(entry)
    return issues


def _parse_mentor_pipeline_scenario(raw: Any) -> MentorPipelineV3Scenario:
    if not isinstance(raw, dict):
        raise GoldenRegressionError("Scenario entries must be mappings.")

    name_raw = raw.get("name")
    name = str(name_raw).strip() if name_raw is not None else ""
    if not name:
        raise GoldenRegressionError("Each scenario must have a non-empty name.")

    description_raw = raw.get("description")
    description = str(description_raw) if description_raw is not None else None

    input_raw = raw.get("input")
    input_path = _as_path(input_raw, field="input")

    requires_raw = raw.get("requires", [input_path.as_posix()])
    if not isinstance(requires_raw, Iterable) or isinstance(requires_raw, (str, bytes)):
        raise GoldenRegressionError(
            f"Scenario '{name}' requires must be a list of file paths."
        )
    requires = [_as_path(item, field=f"requires[{idx}]") for idx, item in enumerate(requires_raw)]

    expected_pool_raw = raw.get("expected_pool")
    expected_pool_rows = _parse_expected_pool(expected_pool_raw, name)
    expected_issues_raw = raw.get("expected_issues")
    expected_issues = _parse_expected_issues(expected_issues_raw, name)

    return MentorPipelineV3Scenario(
        name=name,
        description=description,
        input_path=input_path,
        expected_pool_rows=expected_pool_rows,
        expected_issues=expected_issues,
        requires=requires,
    )


def _parse_scenario(raw: Any) -> Scenario:
    scenario_type = raw.get("type", "cli") if isinstance(raw, dict) else "cli"
    if scenario_type == "mentor-pipeline-v3":
        return _parse_mentor_pipeline_scenario(raw)
    return _parse_cli_scenario(raw)


def _load_config(config_path: Path) -> GoldenConfig:
    if not config_path.exists():
        raise GoldenRegressionError(
            f"Golden regression config not found: {config_path}. "
            "Add a config under ci/configs/ before running."
        )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise GoldenRegressionError("Golden regression config must be a mapping.")

    base_dir_raw = raw.get("base_dir")
    base_dir = _as_path(base_dir_raw, field="base_dir")
    if not base_dir.is_absolute():
        base_dir = (config_path.parent / base_dir).resolve()
    if not base_dir.exists():
        raise GoldenRegressionError(
            f"Golden regression base_dir does not exist: {base_dir}. "
            "Add sanitized golden datasets under ci/golden_datasets/ and update the config."
        )

    ci_golden_root = (config_path.parent.parent / "golden_datasets").resolve()
    if ci_golden_root.exists() and not base_dir.is_relative_to(ci_golden_root):
        raise GoldenRegressionError(
            f"base_dir must stay under the sanitized CI tree ({ci_golden_root}). "
            f"Got: {base_dir}"
        )

    scenarios_raw = raw.get("scenarios")
    if not isinstance(scenarios_raw, list) or not scenarios_raw:
        raise GoldenRegressionError("No scenarios defined in golden regression config.")

    scenarios = [_parse_scenario(item) for item in scenarios_raw]

    return GoldenConfig(base_dir=base_dir, scenarios=scenarios)


def _missing_files(paths: list[Path]) -> list[Path]:
    return [path for path in paths if not path.exists()]


def _run_command(command: GoldenCommand) -> int:
    return cli.main(command.args)


def _materialize_inspactor_input(source: Path, temp_dir: Path) -> Path:
    """Create an Excel workbook if the input is provided as CSV."""

    if source.suffix.lower() in {".xlsx", ".xls"}:
        return source
    if source.suffix.lower() == ".csv":
        temp_dir.mkdir(parents=True, exist_ok=True)
        frame = pd.read_csv(source)
        target = temp_dir / f"{source.stem}.xlsx"
        with pd.ExcelWriter(target, engine="openpyxl") as writer:
            frame.to_excel(writer, index=False, sheet_name="Sheet1")
        return target
    raise GoldenRegressionError(
        "MentorPipelineV3 input must be a CSV or Excel file: " f"{source.suffix}"
    )


def _normalize_frame(df: pd.DataFrame, *, sort_columns: Sequence[str] | None = None) -> pd.DataFrame:
    normalized = df.convert_dtypes()
    if sort_columns:
        existing = [col for col in sort_columns if col in normalized.columns]
    else:
        existing = sorted(normalized.columns)
    if existing:
        normalized = normalized.sort_values(by=existing, kind="mergesort")
    normalized = normalized.sort_index(axis=1)
    normalized = normalized.reset_index(drop=True)
    return normalized.where(lambda frame: ~frame.isna(), pd.NA)


def _compare_frames(label: str, expected: pd.DataFrame, current: pd.DataFrame) -> bool:
    expected_norm = _normalize_frame(expected)
    current_norm = _normalize_frame(current)
    try:
        pd.testing.assert_frame_equal(expected_norm, current_norm, check_dtype=False)
    except AssertionError as exc:
        print(f"  status: {label}-mismatch")
        print(f"  details: {exc}")
        return False
    return True


def _issues_to_frame(issues: Sequence[object]) -> pd.DataFrame:
    payload: list[dict[str, object]] = []
    for issue in issues:
        payload.append(
            {
                "entity_type": getattr(issue, "entity_type", None),
                "row_index": getattr(issue, "row_index", None),
                "column": getattr(issue, "column", None),
                "raw_value": getattr(issue, "raw_value", None),
                "error_code": getattr(issue, "error_code", None),
            }
        )
    frame = pd.DataFrame(payload).convert_dtypes()
    if frame.empty:
        return frame
    return _normalize_frame(frame, sort_columns=["row_index", "column", "error_code"])


def _run_cli_scenario(config: GoldenConfig, scenario: GoldenScenario, *, dry_run: bool) -> bool:
    print(f"[SCENARIO] {scenario.name} (cli)")
    if scenario.description:
        print(f"  description: {scenario.description}")

    resolved_requires = [
        config.resolve(path) for command in scenario.commands for path in command.requires
    ]
    missing = _missing_files(resolved_requires)

    if missing:
        missing_unique = sorted({path.as_posix() for path in missing})
        missing_list = "\n".join(f"  - {path}" for path in missing_unique)
        print("  status: missing-files")
        print("  details: The following required golden files are absent:")
        print(missing_list)
        return False

    if dry_run:
        print("  status: dry-run-success (all referenced files are present)")
        return True

    for command in scenario.commands:
        print(f"  running: {command.name} -> cli.main({command.args})")
        exit_code = _run_command(command)
        if exit_code != 0:
            print(f"  status: failed-command ({command.name})")
            print(f"  exit-code: {exit_code}")
            return False

    print("  status: success")
    return True


def _mentor_expected_pool(rows: list[dict[str, Any]], *, columns: Sequence[str]) -> pd.DataFrame:
    expected = pd.DataFrame(rows).convert_dtypes()
    missing_columns = [col for col in columns if col not in expected.columns]
    if missing_columns:
        raise GoldenRegressionError(
            "expected_pool is missing columns: " + ", ".join(sorted(missing_columns))
        )
    return _normalize_frame(expected, sort_columns=columns)


def _run_mentor_pipeline_scenario(
    config: GoldenConfig, scenario: MentorPipelineV3Scenario, *, dry_run: bool
) -> bool:
    print(f"[SCENARIO] {scenario.name} (mentor-pipeline-v3)")
    if scenario.description:
        print(f"  description: {scenario.description}")

    resolved_requires = [config.resolve(path) for path in scenario.requires]
    missing = _missing_files(resolved_requires)
    if missing:
        missing_unique = sorted({path.as_posix() for path in missing})
        missing_list = "\n".join(f"  - {path}" for path in missing_unique)
        print("  status: missing-files")
        print("  details: The following required golden files are absent:")
        print(missing_list)
        return False

    if dry_run:
        print("  status: dry-run-success (all referenced files are present)")
        return True

    policy_path = Path("config/policy.json")
    if not policy_path.exists():
        print("  status: missing-policy")
        print(f"  details: policy file not found at {policy_path}")
        return False

    inspactor_path = config.resolve(scenario.input_path)
    try:
        with tempfile.TemporaryDirectory(prefix="golden_inspactor_") as temp_dir:
            materialized_input = _materialize_inspactor_input(
                inspactor_path, Path(temp_dir)
            )
            policy = load_policy(policy_path)
            result = import_mentor_pool_with_validation(
                materialized_input, db=None, policy=policy, pool_source="inspactor"
            )
    except Exception as exc:  # pragma: no cover - runtime safety path
        print("  status: mentor-pipeline-error")
        print(f"  details: {exc}")
        return False

    pool_columns = list(result.canonical_df.columns)
    expected_pool = _mentor_expected_pool(scenario.expected_pool_rows, columns=pool_columns)
    current_pool = _normalize_frame(result.canonical_df, sort_columns=pool_columns)
    if not _compare_frames("mentor-pool", expected_pool, current_pool):
        return False

    current_issues = _issues_to_frame(result.issues)
    expected_issues_frame = pd.DataFrame(scenario.expected_issues).convert_dtypes()
    issue_columns = list(current_issues.columns) or list(expected_issues_frame.columns)
    missing_issue_columns = [col for col in issue_columns if col not in expected_issues_frame.columns]
    if missing_issue_columns:
        print("  status: mentor-issues-mismatch")
        print(
            "  details: expected_issues is missing columns: "
            + ", ".join(sorted(missing_issue_columns))
        )
        return False
    expected_issues = _normalize_frame(expected_issues_frame, sort_columns=issue_columns)
    if not _compare_frames("mentor-issues", expected_issues, current_issues):
        return False

    print("  status: success")
    return True


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        config = _load_config(args.config)
    except GoldenRegressionError as exc:
        print(f"golden regression: {exc}")
        return 1

    all_passed = True
    for scenario in config.scenarios:
        if isinstance(scenario, MentorPipelineV3Scenario):
            scenario_passed = _run_mentor_pipeline_scenario(
                config, scenario, dry_run=args.dry_run
            )
        else:
            scenario_passed = _run_cli_scenario(config, scenario, dry_run=args.dry_run)
        all_passed = all_passed and scenario_passed

    if not all_passed:
        print("golden regression completed with failures")
        return 1

    print("golden regression completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Golden regression entry point for Smart Student Allocation CI.

This runner keeps Core logic untouched by delegating execution to the existing
CLI entry point (`app.infra.cli.main`). Scenarios are defined in a YAML config
to keep CI and local runs aligned. The script validates configuration structure
and required files before running anything and can perform a dry-run to avoid
side effects.
"""

from __future__ import annotations

import argparse
import csv
import sys
import tempfile
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from app.core.build_matrix import COL_GROUP_INCLUDED
from app.core.policy_loader import load_policy
from app.infra.local_database import LocalDatabase
from app.infra.qa.mentor_issues_loader import normalize_missing_raw_values
from app.infra.reference_mentors_repository import import_mentor_pool_with_validation
from app.infra.references.schools import import_school_report_from_excel


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
    expected_pool_rows: list[dict[str, Any]] | None
    expected_pool_file: Path | None
    expected_issues: list[dict[str, Any]] | None
    expected_issues_file: Path | None
    requires: list[Path]


Scenario = GoldenScenario | MentorPipelineV3Scenario


MENTOR_ISSUE_COLUMNS: list[str] = [
    "entity_type",
    "row_index",
    "column",
    "raw_value",
    "error_code",
]


@dataclass(frozen=True)
class GoldenConfig:
    """Top-level configuration parsed from YAML."""

    base_dir: Path
    scenarios: list[Scenario]

    def resolve(self, path: Path) -> Path:
        """Resolve paths relative to the declared base directory."""

        return path if path.is_absolute() else self.base_dir / path


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    kind: str
    status: str
    passed: bool


@dataclass(frozen=True)
class GoldenRunReport:
    exit_code: int
    scenario_results: list[ScenarioResult]
    data_failures: bool


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
    parser.add_argument(
        "--dump-mentor-issues",
        type=Path,
        default=None,
        help=(
            "Optional path to write a compact CSV of mentor join-key/gender issues when "
            "they block a scenario."
        ),
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
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise GoldenRegressionError(
            f"Scenario '{scenario_name}' expected_pool must be a list of row mappings."
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
    expected_pool_file_raw = raw.get("expected_pool_file")
    expected_pool_file = _as_path(expected_pool_file_raw, field="expected_pool_file") if expected_pool_file_raw else None

    expected_issues_raw = raw.get("expected_issues")
    expected_issues = _parse_expected_issues(expected_issues_raw, name)
    expected_issues_file_raw = raw.get("expected_issues_file")
    expected_issues_file = _as_path(expected_issues_file_raw, field="expected_issues_file") if expected_issues_file_raw else None

    if not expected_pool_rows and expected_pool_file is None:
        raise GoldenRegressionError(
            f"Scenario '{name}' must provide expected_pool or expected_pool_file."
        )

    return MentorPipelineV3Scenario(
        name=name,
        description=description,
        input_path=input_path,
        expected_pool_rows=expected_pool_rows,
        expected_pool_file=expected_pool_file,
        expected_issues=expected_issues,
        expected_issues_file=expected_issues_file,
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

    project_root = config_path.parent.parent
    allowed_roots = [
        (project_root / "ci" / "golden_datasets").resolve(),
        (project_root / "docs" / "golden_datasets").resolve(),
    ]
    allowed_existing = [root for root in allowed_roots if root.exists()]
    if allowed_existing and not any(base_dir.is_relative_to(root) for root in allowed_existing):
        raise GoldenRegressionError(
            "base_dir must stay under a sanitized golden tree (allowed roots: "
            + ", ".join(str(root) for root in allowed_existing)
            + f"). Got: {base_dir}"
        )

    scenarios_raw = raw.get("scenarios")
    if not isinstance(scenarios_raw, list) or not scenarios_raw:
        raise GoldenRegressionError("No scenarios defined in golden regression config.")

    scenarios = [_parse_scenario(item) for item in scenarios_raw]

    return GoldenConfig(base_dir=base_dir, scenarios=scenarios)


def _missing_files(paths: list[Path]) -> list[Path]:
    return [path for path in paths if not path.exists()]


def _run_command(command: GoldenCommand) -> int:
    from app.infra import cli

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
    return normalized


def _normalize_numeric_pool(df: pd.DataFrame, *, keys: Sequence[str]) -> pd.DataFrame:
    normalized = df.copy()
    for column in normalized.columns:
        try:
            numeric = pd.to_numeric(normalized[column], errors="raise")
        except Exception:
            continue
        if pd.api.types.is_integer_dtype(numeric):
            normalized[column] = numeric.astype("Int64")
        elif pd.api.types.is_float_dtype(numeric):
            normalized[column] = numeric
    for key in keys:
        if key not in normalized.columns:
            continue
        try:
            normalized[key] = pd.to_numeric(normalized[key], errors="raise").astype("Int64")
        except Exception as exc:  # pragma: no cover - defensive numeric normalization
            raise GoldenRegressionError(
                f"GOLDEN_REGRESSION_ERROR: canonical pool contains non-numeric values for {key}"
            ) from exc
    return normalized


def _mentor_issues_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = normalize_missing_raw_values(frame).convert_dtypes()
    normalized["row_index"] = pd.to_numeric(
        normalized["row_index"], errors="raise"
    ).astype("Int64")
    return normalized


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
    frame = _mentor_issues_frame(pd.DataFrame(payload, columns=MENTOR_ISSUE_COLUMNS))
    if frame.empty:
        return frame
    return _normalize_frame(frame, sort_columns=["row_index", "column", "error_code"])


def _maybe_dump_mentor_issues(
    issues: Sequence[object], dump_path: Path | None, *, silent: bool = False
) -> None:
    if dump_path is None or not issues:
        return
    frame = _issues_to_frame(issues)
    dump_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(dump_path, index=False)
    if not silent:
        print(
            f"  details: wrote mentor join-key/gender issues to {dump_path.as_posix()} "
            f"({len(frame)} rows)"
        )


def _summarize_join_key_issues(issues: Sequence[object], *, limit: int = 10) -> str:
    if not issues:
        return ""
    counter = Counter(str(getattr(issue, "error_code", "UNKNOWN")).upper() for issue in issues)
    summary_parts = [f"{code} x{count}" for code, count in sorted(counter.items())]
    head: list[str] = []
    for issue in list(issues)[:limit]:
        column = getattr(issue, "column", None)
        code = getattr(issue, "error_code", None)
        row_index = getattr(issue, "row_index", None)
        head.append(f"[row={row_index}, column={column}, code={code}]")
    suffix = "" if len(issues) <= limit else f" (+{len(issues) - limit} more)"
    head_str = "; ".join(head)
    return f"{', '.join(summary_parts)} | examples: {head_str}{suffix}"


def _format_join_key_error(issues: Sequence[object]) -> str | None:
    for issue in issues:
        column = getattr(issue, "column", None)
        reason = str(getattr(issue, "error_code", "")).upper()
        if column == COL_GROUP_INCLUDED and reason in {
            "MISSING_COLUMN",
            "MISSING_INCLUDED_GROUP_COLUMN",
        }:
            return (
                f"Inspactor mentor input is missing the required '{COL_GROUP_INCLUDED}' column. "
                "Populate this column; legacy 'گروه آزمایشی' values are QA-only and cannot "
                "drive group_code."
            )
    if issues:
        return (
            "Mentor pipeline reported blocking join-key/gender issues (golden data needs "
            f"migration): {_summarize_join_key_issues(issues)}"
        )
    return None


def _run_cli_scenario(
    config: GoldenConfig, scenario: GoldenScenario, *, dry_run: bool
) -> tuple[bool, str]:
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
        return False, "missing-files"

    if dry_run:
        print("  status: dry-run-success (all referenced files are present)")
        return True, "dry-run-success"

    for command in scenario.commands:
        print(f"  running: {command.name} -> cli.main({command.args})")
        exit_code = _run_command(command)
        if exit_code != 0:
            print(f"  status: failed-command ({command.name})")
            print(f"  exit-code: {exit_code}")
            return False, "failed-command"

    print("  status: success")
    return True, "success"


def _mentor_expected_pool(rows: list[dict[str, Any]], *, columns: Sequence[str]) -> pd.DataFrame:
    expected = pd.DataFrame(rows, columns=columns).convert_dtypes()
    return _normalize_frame(expected, sort_columns=columns)


def _load_expected_frame(path: Path, *, kind: str) -> pd.DataFrame:
    if not path.exists():
        raise GoldenRegressionError(f"Expected {kind} file not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(path)
    elif suffix in {".xlsx", ".xls"}:
        frame = pd.read_excel(path)
    else:
        raise GoldenRegressionError(
            f"Expected {kind} file must be CSV or Excel. Got extension: {suffix}"
        )
    return frame.convert_dtypes()


def _load_expected_mentor_issues_frame(path: Path) -> pd.DataFrame:
    """Load mentor issues golden file enforcing the canonical 5-column schema."""

    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            try:
                header = next(reader)
            except StopIteration:
                raise GoldenRegressionError(
                    f"Mentor issues golden file is empty: {path}"
                ) from None
            if header != MENTOR_ISSUE_COLUMNS:
                raise GoldenRegressionError(
                    "Mentor issues golden file must have header "
                    f"{','.join(MENTOR_ISSUE_COLUMNS)}. Got: {header} at {path}"
                )

            rows: list[list[str]] = []
            for line_number, row in enumerate(reader, start=2):
                if len(row) != len(MENTOR_ISSUE_COLUMNS):
                    raise GoldenRegressionError(
                        "Mentor issues golden file has malformed row: "
                        f"{path} line {line_number} expected {len(MENTOR_ISSUE_COLUMNS)} "
                        f"columns, found {len(row)}"
                    )
                rows.append(row)
        frame = pd.DataFrame(rows, columns=MENTOR_ISSUE_COLUMNS)
        return _mentor_issues_frame(frame)

    frame = _load_expected_frame(path, kind="expected_issues")
    if list(frame.columns) != MENTOR_ISSUE_COLUMNS:
        raise GoldenRegressionError(
            "Mentor issues golden file must have columns "
            f"{','.join(MENTOR_ISSUE_COLUMNS)} in order. Got: {list(frame.columns)} "
            f"at {path}"
        )
    return _mentor_issues_frame(frame)


def _run_mentor_pipeline_scenario(
    config: GoldenConfig,
    scenario: MentorPipelineV3Scenario,
    *,
    dry_run: bool,
    dump_mentor_issues: Path | None,
) -> tuple[bool, str]:
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
        return False, "missing-files"

    if dry_run:
        print("  status: dry-run-success (all referenced files are present)")
        return True, "dry-run-success"

    policy_path = Path("config/policy.json")
    if not policy_path.exists():
        print("  status: missing-policy")
        print(f"  details: policy file not found at {policy_path}")
        return False

    inspactor_path = config.resolve(scenario.input_path)
    try:
        with tempfile.TemporaryDirectory(prefix="golden_inspactor_") as temp_dir:
            temp_path = Path(temp_dir)
            materialized_input = _materialize_inspactor_input(
                inspactor_path, temp_path
            )
            policy = load_policy(policy_path)
            db_path = temp_path / "golden_phase02.db"
            db = LocalDatabase(db_path)
            db.initialize()
            try:
                school_report = next(
                    (
                        path
                        for path in resolved_requires
                        if "schoolreport" in path.name.lower()
                    ),
                    None,
                )
                if school_report is None:
                    print("  status: missing-school-report")
                    print(
                        "  details: School report required to derive canonical mentor join keys "
                        "is missing from scenario requires."
                    )
                    return False, "missing-school-report"
                import_school_report_from_excel(school_report, db=db)
                result = import_mentor_pool_with_validation(
                    materialized_input, db=db, policy=policy, pool_source="inspactor"
                )
            finally:
                db.close_all_connections()
    except Exception as exc:  # pragma: no cover - runtime safety path
        print("  status: mentor-pipeline-error")
        print(f"  details: {exc}")
        return False, "mentor-pipeline-error"

    formatted_error = _format_join_key_error(result.issues)
    _maybe_dump_mentor_issues(result.issues, dump_mentor_issues)
    if formatted_error:
        print("  status: mentor-join-key-error")
        print(f"  details: {formatted_error}")
        return False, "mentor-join-key-error"

    sort_keys = [
        "group_code",
        "gender",
        "graduation_status",
        "center",
        "finance",
        "school_code",
        "mentor_id",
    ]
    canonical_pool = _normalize_numeric_pool(result.canonical_df, keys=sort_keys)
    pool_columns = list(canonical_pool.columns)
    if scenario.expected_pool_file is not None:
        expected_pool_frame = _load_expected_frame(
            config.resolve(scenario.expected_pool_file), kind="expected_pool"
        )
        expected_pool = _normalize_numeric_pool(
            expected_pool_frame, keys=sort_keys
        )
        expected_pool = _normalize_frame(expected_pool, sort_columns=pool_columns)
    else:
        expected_pool = _mentor_expected_pool(
            scenario.expected_pool_rows or [], columns=pool_columns
        )
    current_pool = _normalize_frame(canonical_pool, sort_columns=pool_columns)
    if not _compare_frames("mentor-pool", expected_pool, current_pool):
        return False, "mentor-pool-diff"

    current_issues = _issues_to_frame(result.issues)
    if scenario.expected_issues_file is not None:
        expected_issues_frame = _load_expected_mentor_issues_frame(
            config.resolve(scenario.expected_issues_file)
        )
    else:
        expected_issues_frame = _mentor_issues_frame(
            pd.DataFrame(scenario.expected_issues or [], columns=MENTOR_ISSUE_COLUMNS)
        )
    expected_cols = set(expected_issues_frame.columns)
    current_cols = set(current_issues.columns)
    if expected_cols != current_cols:
        print("  status: mentor-issues-mismatch")
        details = []
        if missing_cols := sorted(expected_cols - current_cols):
            details.append(f"Current issues are missing columns: {', '.join(missing_cols)}")
        if extra_cols := sorted(current_cols - expected_cols):
            details.append(f"Current issues have extra columns: {', '.join(extra_cols)}")
        print(f"  details: {' | '.join(details)}")
        return False, "mentor-issues-mismatch"
    issue_columns = sorted(list(expected_cols))
    expected_issues = _normalize_frame(expected_issues_frame, sort_columns=issue_columns)
    if not _compare_frames("mentor-issues", expected_issues, current_issues):
        return False, "mentor-issues-diff"

    print("  status: success")
    return True, "success"


def run_golden_regression(
    argv: Sequence[str] | None = None,
) -> GoldenRunReport:
    args = _parse_args(argv)
    try:
        config = _load_config(args.config)
    except GoldenRegressionError as exc:
        print(f"golden regression: {exc}")
        return GoldenRunReport(exit_code=1, scenario_results=[], data_failures=False)

    results: list[ScenarioResult] = []
    data_failures = False
    all_passed = True

    for scenario in config.scenarios:
        if isinstance(scenario, MentorPipelineV3Scenario):
            scenario_passed, status = _run_mentor_pipeline_scenario(
                config,
                scenario,
                dry_run=args.dry_run,
                dump_mentor_issues=args.dump_mentor_issues,
            )
            data_failures = data_failures or status == "mentor-join-key-error"
            results.append(
                ScenarioResult(
                    name=scenario.name,
                    kind="mentor-pipeline-v3",
                    status=status,
                    passed=scenario_passed,
                )
            )
        else:
            scenario_passed, status = _run_cli_scenario(
                config, scenario, dry_run=args.dry_run
            )
            results.append(
                ScenarioResult(
                    name=scenario.name,
                    kind="cli",
                    status=status,
                    passed=scenario_passed,
                )
            )
        all_passed = all_passed and scenario_passed

    if not all_passed:
        print("golden regression completed with failures")
        return GoldenRunReport(exit_code=1, scenario_results=results, data_failures=data_failures)

    print("golden regression completed successfully")
    return GoldenRunReport(exit_code=0, scenario_results=results, data_failures=data_failures)


def main(argv: Sequence[str] | None = None) -> int:
    report = run_golden_regression(argv)
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())

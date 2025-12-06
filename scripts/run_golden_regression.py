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
from typing import Any

import yaml

from app.infra import cli


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
class GoldenConfig:
    """Top-level configuration parsed from YAML."""

    base_dir: Path
    scenarios: list[GoldenScenario]

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


def _parse_scenario(raw: Any) -> GoldenScenario:
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

    scenarios_raw = raw.get("scenarios")
    if not isinstance(scenarios_raw, list) or not scenarios_raw:
        raise GoldenRegressionError("No scenarios defined in golden regression config.")

    scenarios = [_parse_scenario(item) for item in scenarios_raw]

    return GoldenConfig(base_dir=base_dir, scenarios=scenarios)


def _missing_files(paths: list[Path]) -> list[Path]:
    return [path for path in paths if not path.exists()]


def _run_command(command: GoldenCommand) -> int:
    return cli.main(command.args)


def _run_scenario(config: GoldenConfig, scenario: GoldenScenario, *, dry_run: bool) -> bool:
    print(f"[SCENARIO] {scenario.name}")
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


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        config = _load_config(args.config)
    except GoldenRegressionError as exc:
        print(f"golden regression: {exc}")
        return 1

    all_passed = True
    for scenario in config.scenarios:
        scenario_passed = _run_scenario(config, scenario, dry_run=args.dry_run)
        all_passed = all_passed and scenario_passed

    if not all_passed:
        print("golden regression completed with failures")
        return 1

    print("golden regression completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())

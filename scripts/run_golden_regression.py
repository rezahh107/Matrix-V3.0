"""Golden regression entry point for Smart Student Allocation CI."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.infra import cli


@dataclass
class GoldenCommand:
    name: str
    args: list[str]
    requires: list[Path]


@dataclass
class GoldenScenario:
    name: str
    description: str | None
    commands: list[GoldenCommand]


@dataclass
class GoldenConfig:
    scenarios: list[GoldenScenario]


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


def _load_config(config_path: Path) -> GoldenConfig:
    if not config_path.exists():
        raise GoldenRegressionError(
            f"Golden regression config not found: {config_path}. "
            "Add a config under ci/configs/ before running."
        )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise GoldenRegressionError("Golden regression config must be a mapping.")

    scenarios_raw = raw.get("scenarios")
    if not scenarios_raw:
        raise GoldenRegressionError("No scenarios defined in golden regression config.")

    scenarios: list[GoldenScenario] = []
    for item in scenarios_raw:
        if not isinstance(item, dict):
            raise GoldenRegressionError("Scenario entries must be mappings.")
        name = str(item.get("name") or "").strip()
        if not name:
            raise GoldenRegressionError("Each scenario must have a non-empty name.")

        description_raw = item.get("description")
        description = str(description_raw) if description_raw is not None else None

        commands_raw = item.get("commands")
        if not commands_raw:
            raise GoldenRegressionError(f"Scenario '{name}' has no commands defined.")

        commands: list[GoldenCommand] = []
        for command_raw in commands_raw:
            if not isinstance(command_raw, dict):
                raise GoldenRegressionError(f"Commands for scenario '{name}' must be mappings.")
            command_name = str(command_raw.get("name", "")).strip() or "unnamed-command"
            args = command_raw.get("args")
            if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
                raise GoldenRegressionError(
                    f"Command '{command_name}' in scenario '{name}' must provide a list of args."
                )

            requires_raw = command_raw.get("requires", [])
            requires: list[Path] = []
            if not isinstance(requires_raw, list):
                raise GoldenRegressionError(
                    f"Command '{command_name}' in scenario '{name}' must list required files."
                )
            for raw_path in requires_raw:
                requires.append(Path(str(raw_path)))

            commands.append(GoldenCommand(name=command_name, args=args, requires=requires))

        scenarios.append(GoldenScenario(name=name, description=description, commands=commands))

    return GoldenConfig(scenarios=scenarios)


def _missing_files(paths: list[Path]) -> list[Path]:
    return [path for path in paths if not path.exists()]


def _run_command(command: GoldenCommand) -> int:
    return cli.main(command.args)


def _run_scenario(scenario: GoldenScenario, *, dry_run: bool) -> bool:
    print(f"[SCENARIO] {scenario.name}")
    if scenario.description:
        print(f"  description: {scenario.description}")

    missing: list[Path] = []
    for command in scenario.commands:
        missing.extend(_missing_files(command.requires))

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
        result = _run_command(command)
        if result != 0:
            print(f"  status: failed-command ({command.name})")
            print(f"  exit-code: {result}")
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

    any_failures = False
    for scenario in config.scenarios:
        succeeded = _run_scenario(scenario, dry_run=args.dry_run)
        any_failures = any_failures or not succeeded

    if any_failures:
        print("golden regression completed with failures")
        return 1

    print("golden regression completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())

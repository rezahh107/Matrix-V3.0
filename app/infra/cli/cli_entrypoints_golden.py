from __future__ import annotations

import os
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from app.infra.golden import regression_runner
from app.infra.golden.regression_runner import GoldenRunReport

_VALID_MODES = {"v3", "legacy"}


@dataclass(frozen=True)
class GoldenCliError(RuntimeError):
    message: str

    def __str__(self) -> str:  # pragma: no cover - dataclass convenience
        return self.message


@contextmanager
def _temporary_env(var: str, value: str) -> Generator[None, None, None]:
    previous = os.environ.get(var)
    os.environ[var] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = previous


def run_phase06_golden(
    *, config_path: Path, mode: str = "v3", dry_run: bool = False
) -> int:
    if mode not in _VALID_MODES:
        raise GoldenCliError(
            message=(
                f"Unsupported SMART_ALLOC_PIPELINE_MODE='{mode}'. "
                f"Expected one of {sorted(_VALID_MODES)}."
            )
        )
    if not config_path.exists():
        raise GoldenCliError(
            message=(
                "Golden regression config not found. "
                f"Expected at: {config_path}"  # pragma: no cover - straight failure path
            )
        )

    argv: list[str] = ["--config", str(config_path)]
    if dry_run:
        argv.append("--dry-run")

    with _temporary_env("SMART_ALLOC_PIPELINE_MODE", mode):
        report = regression_runner.run_golden_regression(argv)
    return report.exit_code


def run_phase06_golden_report(
    *, config_path: Path, mode: str = "v3", dry_run: bool = False
) -> GoldenRunReport:
    if mode not in _VALID_MODES:
        raise GoldenCliError(
            message=(
                f"Unsupported SMART_ALLOC_PIPELINE_MODE='{mode}'. "
                f"Expected one of {sorted(_VALID_MODES)}."
            )
        )
    if not config_path.exists():
        raise GoldenCliError(
            message=(
                "Golden regression config not found. "
                f"Expected at: {config_path}"  # pragma: no cover - straight failure path
            )
        )

    argv: list[str] = ["--config", str(config_path)]
    if dry_run:
        argv.append("--dry-run")

    with _temporary_env("SMART_ALLOC_PIPELINE_MODE", mode):
        return regression_runner.run_golden_regression(argv)


def run_phase06_cli(argv: Sequence[str] | None = None) -> int:
    """Thin wrapper to expose the golden driver through app.infra.cli."""

    return regression_runner.main(argv)

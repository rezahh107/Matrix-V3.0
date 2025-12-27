from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _print_header(title: str) -> None:
    print(f"\n=== {title} ===")


def _run_command(command: list[str]) -> int:
    print(f"$ {' '.join(command)}")
    result = subprocess.run(command, check=False)
    return result.returncode


def _git_ref_exists(ref: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", ref],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _is_pull_request_context() -> bool:
    return os.environ.get("GITHUB_EVENT_NAME") == "pull_request" or bool(
        os.environ.get("GITHUB_BASE_REF")
    )


def _run_law_ssot_guard() -> int:
    base_ref = "HEAD"
    if _is_pull_request_context() and _git_ref_exists("origin/main"):
        base_ref = "origin/main"
    _print_header("LAW/SSoT Drift Guard")
    return _run_command(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "ci" / "law_ssot_drift_guard.py"),
            base_ref,
            "HEAD",
        ]
    )


def main() -> int:
    step = _run_law_ssot_guard()
    if step != 0:
        return step

    _print_header("Ruff")
    step = _run_command(["ruff", "check", "."])
    if step != 0:
        return step

    _print_header("Pytest (CI guards + core)")
    step = _run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/infra/ci",
            "tests/core",
        ]
    )
    if step != 0:
        return step

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

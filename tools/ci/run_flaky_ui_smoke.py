from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def run_pytest_with_retries(args: list[str], retries: int = 2) -> int:
    """Run pytest with limited retries to smooth over flaky UI smoke tests."""

    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    command = [sys.executable, "-m", "pytest", *args]

    for attempt in range(1, retries + 2):
        result = subprocess.run(command, cwd=repo_root, env=env, check=False)
        if result.returncode == 0:
            return 0

        if attempt > retries:
            return result.returncode

    return 1


def main() -> int:
    default_args = ["tests/ui", "--maxfail=1", "-q"]
    retries = int(os.environ.get("UI_SMOKE_RETRIES", "1"))
    return run_pytest_with_retries(default_args, retries=retries)


if __name__ == "__main__":
    raise SystemExit(main())

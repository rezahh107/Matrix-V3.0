from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    command = [sys.executable, "-m", "pytest", "tests/perf", "-q"]
    result = subprocess.run(command, cwd=repo_root, env=env, check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import subprocess
import sys
from typing import Sequence

CRITICAL_TESTS: Sequence[str] = [
    "tests/ui/test_join_key_validation_flow.py::test_join_key_validation_error_opens_dialog",
    "tests/ui/test_main_window_mentor_pool_integration.py::test_matrix_governance_button_and_overrides",
]
RUNS_PER_TEST = 3


def main() -> int:
    for test_path in CRITICAL_TESTS:
        for iteration in range(1, RUNS_PER_TEST + 1):
            result = subprocess.run([
                "pytest",
                test_path,
                "--maxfail=1",
                "-q",
            ])
            if result.returncode != 0:
                print(
                    f"Flaky UI smoke failed: {test_path} (iteration {iteration})",
                    file=sys.stderr,
                )
                return 1
    print(
        "Flaky UI smoke passed: "
        f"{len(CRITICAL_TESTS)} tests x {RUNS_PER_TEST} runs each.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import subprocess
import time
from collections.abc import Sequence

PERF_TESTS: Sequence[str] = [
    "tests/integration/test_allocator_end_to_end.py::test_allocator_end_to_end",
    "tests/integration/test_allocator_golden.py::test_bilingual_headers_reduce_false_no_match",
]
LIMIT_SECONDS: dict[str, float] = {
    "tests/integration/test_allocator_end_to_end.py::test_allocator_end_to_end": 20.0,
    "tests/integration/test_allocator_golden.py::test_bilingual_headers_reduce_false_no_match": 20.0,
}


def run_test(test_path: str) -> tuple[float, bool]:
    start = time.perf_counter()
    result = subprocess.run(
        [
            "pytest",
            test_path,
            "-q",
            "--maxfail=1",
        ]
    )
    elapsed = time.perf_counter() - start
    success = result.returncode == 0 and elapsed <= LIMIT_SECONDS[test_path]
    return elapsed, success


def main() -> int:
    failures = []
    print("Performance smoke results:")
    for test_path in PERF_TESTS:
        elapsed, success = run_test(test_path)
        limit = LIMIT_SECONDS[test_path]
        status = "PASS" if success else "FAIL"
        print(f"{status}: {test_path} — {elapsed:.2f}s (limit {limit:.2f}s)")
        if not success:
            failures.append(test_path)
    if failures:
        print("Performance smoke failed for:")
        for path in failures:
            print(f" - {path}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

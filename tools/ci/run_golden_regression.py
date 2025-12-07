from __future__ import annotations

import sys
from collections.abc import Sequence

import pytest

TEST_TARGETS: Sequence[str] = (
    "tests/integration/test_allocator_golden.py::test_bilingual_headers_reduce_false_no_match",
    "tests/integration/test_rule_engine_golden_realistic.py::test_realistic_high_no_match_scenario_golden",
    "tests/integration/test_excel_reason_sheet.py::test_reason_sheet_schema_and_snapshot",
)


def run_pytest(targets: Sequence[str]) -> int:
    """Execute pytest for the provided targets with fail-fast settings."""

    return pytest.main([*targets, "--maxfail=1", "-q"])


def main() -> int:
    """Run the curated golden regression suite."""

    return run_pytest(TEST_TARGETS)


if __name__ == "__main__":
    sys.exit(main())

from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.performance.run_perf_suite import run_perf_suite

DATASET_DIR = Path("tests/data/golden_perf/v1")


def test_allocation_determinism(tmp_path: Path) -> None:
    first = run_perf_suite(DATASET_DIR, output_dir=tmp_path / "run1")
    second = run_perf_suite(DATASET_DIR, output_dir=tmp_path / "run2")

    pd.testing.assert_frame_equal(first.allocations, second.allocations, check_like=True)

from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.performance.run_perf_suite import run_perf_suite

DATASET_DIR = Path("tests/data/golden_perf/v1")
BASELINE_DECISIONS = DATASET_DIR / "decisions_baseline.csv"


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.fillna("").copy()
    for column in normalized.columns:
        normalized[column] = normalized[column].astype(str)
    return normalized.reset_index(drop=True)


def test_golden_parity_matches_baseline(tmp_path: Path) -> None:
    result = run_perf_suite(DATASET_DIR, output_dir=tmp_path)
    expected = pd.read_csv(BASELINE_DECISIONS)

    aligned_expected = _normalize(expected)
    aligned_actual = _normalize(result.allocations)
    pd.testing.assert_frame_equal(aligned_expected, aligned_actual, check_dtype=False)

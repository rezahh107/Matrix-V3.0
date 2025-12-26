"""Performance suite runner for golden dataset parity and determinism."""

from __future__ import annotations

import argparse
import json
import sys
import tracemalloc
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd

from app.core.allocate_students import allocate_batch
from app.core.policy_loader import load_policy


@dataclass(frozen=True)
class PerfRunResult:
    allocations: pd.DataFrame
    metrics_path: Path
    decisions_path: Path
    total_runtime_seconds: float
    peak_memory_bytes: int
    stage_timings: dict[str, float]


def _load_dataset(base_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    meta_path = base_dir / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Missing meta.json at {meta_path}")

    with meta_path.open("r", encoding="utf-8") as handle:
        meta = json.load(handle)

    students_path = base_dir / (meta.get("students") or "students.csv")
    mentors_path = base_dir / (meta.get("mentors") or "mentors.csv")
    if not students_path.exists():
        raise FileNotFoundError(f"Missing students dataset at {students_path}")
    if not mentors_path.exists():
        raise FileNotFoundError(f"Missing mentors dataset at {mentors_path}")

    students_df = pd.read_csv(students_path)
    mentors_df = pd.read_csv(mentors_path)
    return students_df, mentors_df, meta


def run_perf_suite(dataset_dir: Path, output_dir: Path | None = None) -> PerfRunResult:
    dataset_dir = dataset_dir.resolve()
    output_dir = (output_dir or dataset_dir).resolve()

    policy = load_policy()

    stage_timings: dict[str, float] = {}
    overall_start = perf_counter()
    tracemalloc.start()

    load_start = perf_counter()
    students_df, mentors_df, meta = _load_dataset(dataset_dir)
    stage_timings["load_seconds"] = perf_counter() - load_start

    allocation_start = perf_counter()
    result = allocate_batch(
        students_df,
        mentors_df,
        policy=policy,
        frames_already_canonical=True,
    )
    stage_timings["allocation_seconds"] = perf_counter() - allocation_start

    allocations = result.allocations_df.sort_values(["student_id", "mentor_id"]).reset_index(drop=True)

    output_dir.mkdir(parents=True, exist_ok=True)

    write_start = perf_counter()
    decisions_path = output_dir / "decisions.csv"
    allocations.to_csv(decisions_path, index=False)
    stage_timings["write_seconds"] = perf_counter() - write_start

    total_runtime_seconds = perf_counter() - overall_start
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    metrics_path = output_dir / "metrics.json"
    metrics = {
        "dataset": meta.get("dataset", "unknown"),
        "total_runtime_seconds": total_runtime_seconds,
        "stage_timings": stage_timings,
        "peak_memory_bytes": peak,
        "decisions_path": str(decisions_path),
    }
    with metrics_path.open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2)

    return PerfRunResult(
        allocations=allocations,
        metrics_path=metrics_path,
        decisions_path=decisions_path,
        total_runtime_seconds=total_runtime_seconds,
        peak_memory_bytes=peak,
        stage_timings=stage_timings,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run performance suite.")
    parser.add_argument(
        "dataset_dir",
        type=Path,
        help="Path to the dataset directory containing meta.json and CSV inputs.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional output directory for decisions and metrics (defaults to dataset dir).",
    )

    args = parser.parse_args()

    try:
        run_perf_suite(args.dataset_dir, output_dir=args.output_dir)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Diagnostic tool for phase01 mentor pool snapshot drift."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.policy_loader import load_policy
from app.infra.local_database import LocalDatabase
from app.infra.reference_mentors_repository import import_mentor_pool_with_validation
from app.infra.references.schools import import_school_report_from_excel
from scripts.run_golden_regression_phase01 import (
    GOLDEN_INSPACTOR,
    GOLDEN_SCHOOL,
    SNAPSHOT_POOL,
    GoldenRegressionError,
    _canonicalize_pool,
    _require_files,
)

ARTIFACTS_DIR = Path("ci/artifacts")


@dataclass(frozen=True)
class Phase01PoolArtifacts:
    """Paths for diff artifacts produced by this diagnostic."""

    current_path: Path
    snapshot_copy_path: Path
    summary_path: Path


@dataclass(frozen=True)
class PoolStats:
    snapshot_shape: tuple[int, int]
    current_shape: tuple[int, int]
    columns_only_snapshot: list[str]
    columns_only_current: list[str]
    columns_common: list[str]
    mentor_counts_snapshot: Counter[str]
    mentor_counts_current: Counter[str]
    group_counts_snapshot: Counter[int]
    group_counts_current: Counter[int]
    rows_per_mentor_snapshot: float
    rows_per_mentor_current: float


ROOT_CAUSE_TEMPLATES = {
    "group_token_explosion": "Row count grew faster than mentor count; likely more profiles per mentor (group token expansion).",
    "new_mentors": "Row and mentor counts increased together; likely new mentors present in current pool.",
    "column_drift": "Column mismatch detected; schema changes or header normalization may differ.",
    "similar": "Shapes are similar; investigate minor content differences or QA filtering.",
}


def _ensure_artifacts_dir() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def _build_current_pool() -> pd.DataFrame:
    """Run the same path as the phase01 runner to materialize the current pool."""

    _require_files([GOLDEN_INSPACTOR, GOLDEN_SCHOOL])
    policy_path = Path("config/policy.json")
    if not policy_path.exists():
        raise GoldenRegressionError(
            f"GOLDEN_REGRESSION_ERROR: Missing policy file: {policy_path}. "
            "Ensure the policy SSoT is available."
        )

    policy = load_policy(policy_path)
    db = LocalDatabase(Path(ARTIFACTS_DIR) / "phase01_debug.db")
    db.initialize()
    import_school_report_from_excel(GOLDEN_SCHOOL, db=db)
    validation = import_mentor_pool_with_validation(
        GOLDEN_INSPACTOR, db=db, policy=policy, pool_source="inspactor"
    )
    if validation.issues:
        raise GoldenRegressionError(
            "GOLDEN_REGRESSION_ERROR: Mentor pipeline reported issues during debug run: "
            f"{validation.issues}"
        )
    return _canonicalize_pool(validation.canonical_df)


def _load_snapshot() -> pd.DataFrame:
    _require_files([SNAPSHOT_POOL])
    return pd.read_csv(SNAPSHOT_POOL)


def _collect_stats(snapshot: pd.DataFrame, current: pd.DataFrame) -> PoolStats:
    snapshot_shape = snapshot.shape
    current_shape = current.shape
    columns_only_snapshot = sorted(set(snapshot.columns) - set(current.columns))
    columns_only_current = sorted(set(current.columns) - set(snapshot.columns))
    columns_common = sorted(set(snapshot.columns).intersection(set(current.columns)))

    mentor_counts_snapshot = Counter(snapshot.get("mentor_id", pd.Series(dtype="Int64")))
    mentor_counts_current = Counter(current.get("mentor_id", pd.Series(dtype="Int64")))

    group_counts_snapshot = Counter(snapshot.get("group_code", pd.Series(dtype="Int64")))
    group_counts_current = Counter(current.get("group_code", pd.Series(dtype="Int64")))

    unique_snapshot = max(len(mentor_counts_snapshot), 1)
    unique_current = max(len(mentor_counts_current), 1)
    rows_per_mentor_snapshot = snapshot_shape[0] / unique_snapshot
    rows_per_mentor_current = current_shape[0] / unique_current

    return PoolStats(
        snapshot_shape=snapshot_shape,
        current_shape=current_shape,
        columns_only_snapshot=columns_only_snapshot,
        columns_only_current=columns_only_current,
        columns_common=columns_common,
        mentor_counts_snapshot=mentor_counts_snapshot,
        mentor_counts_current=mentor_counts_current,
        group_counts_snapshot=group_counts_snapshot,
        group_counts_current=group_counts_current,
        rows_per_mentor_snapshot=rows_per_mentor_snapshot,
        rows_per_mentor_current=rows_per_mentor_current,
    )


def _hypothesize_root_cause(stats: PoolStats) -> str:
    if stats.columns_only_snapshot or stats.columns_only_current:
        return ROOT_CAUSE_TEMPLATES["column_drift"]

    if stats.rows_per_mentor_current > stats.rows_per_mentor_snapshot * 1.25:
        return ROOT_CAUSE_TEMPLATES["group_token_explosion"]

    if stats.current_shape[0] > stats.snapshot_shape[0] and len(stats.mentor_counts_current) > len(
        stats.mentor_counts_snapshot
    ):
        return ROOT_CAUSE_TEMPLATES["new_mentors"]

    return ROOT_CAUSE_TEMPLATES["similar"]


def _write_frame(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _render_counter(counter: Counter[Any], limit: int = 5) -> str:
    if not counter:
        return "(empty)"
    most_common = counter.most_common(limit)
    lines = [f"- {key}: {count}" for key, count in most_common]
    remainder = sum(counter.values()) - sum(count for _, count in most_common)
    if remainder > 0:
        lines.append(f"- other: {remainder}")
    return "\n".join(lines)


def _write_summary(stats: PoolStats, output_path: Path) -> None:
    hypothesis = _hypothesize_root_cause(stats)
    summary_lines = [
        "# Phase01 Mentor Pool Diff Summary",
        "",
        "## Shapes",
        f"- snapshot: {stats.snapshot_shape}",
        f"- current: {stats.current_shape}",
        "",
        "## Columns",
        f"- only in snapshot ({len(stats.columns_only_snapshot)}): {stats.columns_only_snapshot}",
        f"- only in current ({len(stats.columns_only_current)}): {stats.columns_only_current}",
        f"- common ({len(stats.columns_common)}): {stats.columns_common}",
        "",
        "## Mentor counts",
        f"- unique mentors snapshot: {len(stats.mentor_counts_snapshot)}",
        f"- unique mentors current: {len(stats.mentor_counts_current)}",
        f"- rows per mentor snapshot: {stats.rows_per_mentor_snapshot:.2f}",
        f"- rows per mentor current: {stats.rows_per_mentor_current:.2f}",
        "",
        "Top mentor_id frequencies (snapshot):",
        _render_counter(stats.mentor_counts_snapshot),
        "",
        "Top mentor_id frequencies (current):",
        _render_counter(stats.mentor_counts_current),
        "",
        "Top group_code frequencies (snapshot):",
        _render_counter(stats.group_counts_snapshot),
        "",
        "Top group_code frequencies (current):",
        _render_counter(stats.group_counts_current),
        "",
        "## Root cause hypothesis",
        f"- {hypothesis}",
    ]
    output_path.write_text("\n".join(summary_lines), encoding="utf-8")


def run_diff() -> Phase01PoolArtifacts:
    _ensure_artifacts_dir()
    current = _build_current_pool()
    snapshot = _load_snapshot()
    stats = _collect_stats(snapshot, current)

    current_path = ARTIFACTS_DIR / "phase01_mentor_pool_current.csv"
    snapshot_copy_path = ARTIFACTS_DIR / "phase01_mentor_pool_snapshot.csv"
    summary_path = ARTIFACTS_DIR / "phase01_mentor_pool_diff_summary.md"

    _write_frame(current_path, current)
    _write_frame(snapshot_copy_path, snapshot)
    _write_summary(stats, summary_path)

    return Phase01PoolArtifacts(
        current_path=current_path,
        snapshot_copy_path=snapshot_copy_path,
        summary_path=summary_path,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate diagnostic artifacts comparing the current phase01 mentor pool "
            "against the locked snapshot without mutating any baselines."
        )
    )
    parser.parse_args()
    try:
        artifacts = run_diff()
    except GoldenRegressionError as exc:
        print(exc)
        return 1

    print("Phase01 mentor pool diagnostic artifacts written:")
    print(f"- current: {artifacts.current_path}")
    print(f"- snapshot copy: {artifacts.snapshot_copy_path}")
    print(f"- summary: {artifacts.summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

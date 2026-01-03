from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from app.core.allocate_students import allocate_batch
from app.core.canonical_frames import canonicalize_pool_frame, canonicalize_students_frame
from app.core.debug_pool_alignment import analyze_pool_alignment_batch
from app.core.policy_loader import load_policy
from app.core.qa.invariants import check_POOL_COVERAGE_01
from app.infra import cli_legacy as cli
from app.infra.io_utils import read_excel_first_sheet
from app.infra.pool_loader import load_pool

ROOT = Path(__file__).resolve().parents[2]


def _load_canonical_frames():
    policy = load_policy()
    students_raw = read_excel_first_sheet(ROOT / "students.xlsx")
    students = canonicalize_students_frame(students_raw, policy=policy)

    pool_raw = load_pool(
        ROOT / "0918.xlsx", pool_type="matrix", pool_sheet="matrix"
    )
    pool = canonicalize_pool_frame(pool_raw, policy=policy, pool_source="matrix")
    return policy, students, pool


def _assert_matrix_pool_metadata(pool: pd.DataFrame) -> None:
    detection = pool.attrs.get("pool_detection")
    assert detection is not None, "pool detection metadata missing"
    assert getattr(detection, "pool_type", None) == "matrix"
    assert pool.attrs.get("pool_source") == "matrix"


def test_canonical_alignment_parity() -> None:
    policy, students, pool = _load_canonical_frames()
    _assert_matrix_pool_metadata(pool)

    reports = analyze_pool_alignment_batch(
        students, pool, policy=policy, limit=None
    )
    summary_df = pd.DataFrame(reports)

    assert int(summary_df.shape[0]) == 12
    assert int(summary_df["candidate_count_initial"].eq(0).sum()) == 0
    assert int(summary_df["candidate_count_final"].eq(0).sum()) == 0
    assert int(summary_df["join_key_mismatches"].apply(bool).sum()) == 0


def test_matrix_allocation_parity(tmp_path: Path) -> None:
    policy, students, pool = _load_canonical_frames()
    _assert_matrix_pool_metadata(pool)

    args = argparse.Namespace(
        prior_roster=None,
        current_roster=None,
        counter_duplicate_strategy="assign-new",
        academic_year=1403,
        _ui_overrides={},
        _ui_mode=False,
    )
    _, _, students_with_ids = cli._inject_student_ids(
        students.copy(), args, policy
    )

    allocation_result = allocate_batch(
        students_with_ids,
        pool,
        policy=policy,
        frames_already_canonical=True,
    )

    output_path = tmp_path / "allocation_output.xlsx"
    with pd.ExcelWriter(output_path) as writer:
        allocation_result.allocations_df.to_excel(
            writer, sheet_name="allocations", index=False
        )
        allocation_result.pool_output.to_excel(
            writer, sheet_name="updated_pool", index=False
        )
        allocation_result.logs_df.to_excel(
            writer, sheet_name="logs", index=False
        )
        allocation_result.trace_df.to_excel(
            writer, sheet_name="trace", index=False
        )

    assert output_path.exists()
    assert output_path.stat().st_size > 0

    preflight_df = pd.DataFrame(
        analyze_pool_alignment_batch(
            students_with_ids, pool, policy=policy, limit=None
        )
    )
    qa_result = check_POOL_COVERAGE_01(
        pool_alignment_preflight=preflight_df, policy=policy
    )

    assert qa_result.passed
    assert not qa_result.violations

    policy_violations = allocation_result.trace_extras.policy_violations
    assert policy_violations is None or policy_violations.empty

    unallocated = allocation_result.trace_extras.unallocated_summary
    assert unallocated is None or unallocated.empty


def test_allocation_preflight_matrix_pool_source() -> None:
    policy = load_policy()
    args = argparse.Namespace(
        students=str(ROOT / "students.xlsx"),
        pool=str(ROOT / "0918.xlsx"),
        pool_type="matrix",
        pool_sheet="matrix",
        _ui_overrides={},
        _ui_mode=False,
        _user_settings=None,
    )

    students_df, _, _ = cli._resolve_students_frame(args, policy, db=None)
    pool_df, _, _ = cli._resolve_mentor_pool_frame(
        args,
        policy,
        db=None,
        pool_arg="pool",
        pool_source="matrix",
        matrix_only=True,
    )

    detection = pool_df.attrs.get("pool_detection")
    assert detection is not None
    assert getattr(detection, "pool_type", None) == "matrix"

    pool_df = cli._normalize_pool_attrs(
        pool_df, pool_source="matrix", detection=detection
    )

    students_base, pool_base = cli._prepare_allocation_frames(
        students_df,
        pool_df,
        policy=policy,
        sanitize_pool=True,
        pool_source="matrix",
    )
    pool_base = cli._apply_mentor_pool_overrides(pool_base, policy, args)

    preflight_df = cli._run_pool_alignment_preflight(
        students_base, pool_base, policy=policy
    )

    assert int(preflight_df["candidate_count_initial"].eq(0).sum()) == 0
    assert int(preflight_df["candidate_count_final"].eq(0).sum()) == 0
    assert int(preflight_df["join_key_mismatches"].apply(bool).sum()) == 0

    assert pool_base.attrs.get("pool_source") == "matrix"
    detection_after = pool_base.attrs.get("pool_detection")
    assert detection_after is None or getattr(detection_after, "pool_type", None) == "matrix"

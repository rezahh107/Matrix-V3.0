from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.canonical_frames import canonicalize_pool_frame, canonicalize_students_frame
from app.core.debug_pool_alignment import analyze_pool_alignment_batch
from app.core.policy_loader import load_policy
from app.infra.io_utils import read_excel_first_sheet, read_inspactor_workbook


def _write_output(path: Path, payload: dict[str, Any]) -> None:
    if path.suffix.lower() == ".csv":
        reports = payload.get("reports", [])
        df = pd.DataFrame(reports)
        df.to_csv(path, index=False)
        return
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Debug student vs mentor pool alignment",
    )
    parser.add_argument("--students", type=Path, required=True, help="Path to students Excel file.")
    parser.add_argument("--pool", type=Path, required=True, help="Path to mentor pool Excel file.")
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Max number of students to analyze (0 = all).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("debug_alignment_report.json"),
        help="Output JSON/CSV file.",
    )
    args = parser.parse_args()

    policy = load_policy()
    students_df = canonicalize_students_frame(read_excel_first_sheet(args.students), policy=policy)
    pool_df = canonicalize_pool_frame(read_inspactor_workbook(args.pool), policy=policy)

    limit = args.limit if args.limit > 0 else None
    reports = analyze_pool_alignment_batch(
        students_df,
        pool_df,
        policy=policy,
        limit=limit,
    )

    summary = {
        "total_students_analyzed": len(reports),
        "errors": sum(1 for r in reports if r["error"] is not None),
        "students_with_no_final_candidates": sum(
            1 for r in reports if r["candidate_count_final"] == 0 and r["error"] is None
        ),
        "students_with_join_key_mismatches": sum(1 for r in reports if r["join_key_mismatches"]),
    }

    payload = {
        "summary": summary,
        "reports": [dict(report) for report in reports],
    }

    _write_output(args.output, payload)

    print("Students analyzed:", summary["total_students_analyzed"])
    print("Errors:", summary["errors"])
    print("Zero final candidates:", summary["students_with_no_final_candidates"])
    print("Join-key mismatches:", summary["students_with_join_key_mismatches"])


if __name__ == "__main__":
    main()

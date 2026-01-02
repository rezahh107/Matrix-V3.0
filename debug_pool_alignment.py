from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.canonical_frames import canonicalize_pool_frame, canonicalize_students_frame
from app.core.common.filters import (
    filter_by_center,
    filter_by_finance,
    filter_by_gender,
    filter_by_graduation_status,
    filter_by_group,
    filter_by_school,
    filter_by_type,
)
from app.core.common.join_resolver import JoinKeyResolver
from app.core.debug_pool_alignment import analyze_pool_alignment_batch
from app.core.allocate_students import (
    _collect_join_key_map,
    _filter_candidates_by_join_map,
    _materialize_effective_center_in_join_map,
)
from app.core.policy_loader import load_policy
from app.infra.io_utils import read_excel_first_sheet
from app.infra.pool_loader import PoolType, load_pool_with_detection


def _die(msg: str, code: int = 2) -> None:
    print(f"❌ {msg}", file=sys.stderr)
    raise SystemExit(code)


def _safe_name(text: str, max_len: int = 80) -> str:
    text = str(text or "").strip()
    if not text:
        return "unknown"
    text = re.sub(r"[<>:\"/\\|?*\n\r\t]", "_", text)
    text = re.sub(r"\s+", "_", text)
    return text[:max_len]


def _inspect_workbook(path: Path) -> dict[str, Any]:
    if not path.exists():
        _die(f"فایل یافت نشد: {path}")
    info: dict[str, Any] = {"path": str(path), "sheets": []}
    with pd.ExcelFile(path) as wb:
        for sheet in wb.sheet_names:
            try:
                header = wb.parse(sheet, nrows=0)
                row_count = None
                try:
                    ws = wb.book[sheet]
                    if ws.max_row is not None:
                        row_count = max(0, int(ws.max_row) - 1)
                except Exception:
                    row_count = None
                info["sheets"].append(
                    {
                        "sheet": sheet,
                        "row_count_estimate": row_count,
                        "column_count": int(header.shape[1]),
                        "columns_preview": list(map(str, header.columns[:30])),
                    }
                )
            except Exception as exc:
                info["sheets"].append({"sheet": sheet, "error": str(exc)})
    return info


def _auto_pool_type(path: Path) -> PoolType:
    with pd.ExcelFile(path) as wb:
        return "matrix" if "matrix" in wb.sheet_names else "inspactor"


def _write_output(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".csv":
        rows: list[dict[str, Any]] = []
        for r in payload.get("reports", []):
            row = dict(r)
            for k in ["join_key_values", "stage_counts", "join_key_mismatches", "available_values"]:
                if k in row:
                    row[k] = json.dumps(row[k], ensure_ascii=False)
            rows.append(row)
        pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
        return
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _summarize(reports: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(reports)
    errors = sum(1 for r in reports if r.get("error") is not None)
    zero_initial = sum(1 for r in reports if r.get("candidate_count_initial") == 0 and r.get("error") is None)
    zero_final = sum(1 for r in reports if r.get("candidate_count_final") == 0 and r.get("error") is None)
    mismatches = sum(1 for r in reports if r.get("join_key_mismatches"))

    failing_stage = Counter()
    for r in reports:
        if r.get("error") is None and r.get("candidate_count_final") == 0:
            failing_stage[str(r.get("first_failing_stage") or "unknown")] += 1

    mismatch_cols = Counter()
    mismatch_types = Counter()
    for r in reports:
        for mm in r.get("join_key_mismatches", []) or []:
            mismatch_cols[str(mm.get("column", "unknown"))] += 1
            mismatch_types[str(mm.get("mismatch_type", "unknown"))] += 1

    return {
        "total_students_analyzed": total,
        "errors": errors,
        "students_with_zero_initial_candidates": zero_initial,
        "students_with_no_final_candidates": zero_final,
        "students_with_join_key_mismatches": mismatches,
        "top_failing_stages": dict(failing_stage.most_common(10)),
        "top_mismatch_columns": dict(mismatch_cols.most_common(10)),
        "mismatch_types": dict(mismatch_types.most_common()),
    }


_STAGE_FUNCS: list[tuple[str, Any]] = [
    ("type", filter_by_type),
    ("group", filter_by_group),
    ("gender", filter_by_gender),
    ("graduation_status", filter_by_graduation_status),
    ("center", filter_by_center),
    ("finance", filter_by_finance),
    ("school", filter_by_school),
]


def _capacity_filter(df: pd.DataFrame, capacity_column: str) -> pd.DataFrame:
    if capacity_column not in df.columns:
        return df.iloc[0:0]
    try:
        return df.loc[df[capacity_column] > 0]
    except Exception:
        return df.iloc[0:0]


def trace_student_pools(*, student: dict[str, Any], pool: pd.DataFrame, policy) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    join_map, missing_cols = _collect_join_key_map(student, policy)
    resolver = JoinKeyResolver(policy)
    effective_center = resolver.resolve_center(student, student_join_map=join_map)
    _materialize_effective_center_in_join_map(join_map, policy=policy, effective_center=effective_center)

    frames: dict[str, pd.DataFrame] = {"initial": pool}
    current = pool

    for stage, fn in _STAGE_FUNCS:
        current = fn(current, student, policy, student_join_map=join_map)
        frames[stage] = current

    strict_df, mismatch_details = _filter_candidates_by_join_map(current, join_map=join_map, policy=policy)
    frames["strict_join"] = strict_df

    cap_df = _capacity_filter(strict_df, policy.capacity_column)
    frames["capacity_gate"] = cap_df

    meta = {
        "missing_student_join_columns": list(missing_cols),
        "join_map": join_map,
        "mismatch_details_count": int(len(mismatch_details)),
        "capacity_column": policy.capacity_column,
        "counts": {k: int(v.shape[0]) for k, v in frames.items()},
    }
    return frames, meta


def _default_dump_columns(policy) -> list[str]:
    cols: list[str] = []
    for c in ["mentor_id", "کد کارمندی پشتیبان", "__source_index__", policy.capacity_column, "remaining_capacity"]:
        if c and c not in cols:
            cols.append(c)
    for c in policy.join_keys:
        if c not in cols:
            cols.append(c)
    for c in ["has_school_constraint", "mentor_school_binding_mode"]:
        if c not in cols:
            cols.append(c)
    return cols


def _select_columns(df: pd.DataFrame, desired: list[str]) -> pd.DataFrame:
    desired = [c for c in desired if c in df.columns]
    return df if not desired else df.loc[:, desired]


def _sort_df(df: pd.DataFrame) -> pd.DataFrame:
    sort_cols = [c for c in ["mentor_id", "__source_index__", "کد کارمندی پشتیبان"] if c in df.columns]
    if sort_cols:
        try:
            return df.sort_values(sort_cols, kind="stable")
        except Exception:
            return df
    return df


def dump_student_trace(
    *,
    dump_root: Path,
    student_key: str,
    frames: dict[str, pd.DataFrame],
    meta: dict[str, Any],
    stages: set[str],
    n: int,
    columns: list[str],
    dump_all_columns: bool,
) -> dict[str, Any]:
    student_folder = dump_root / f"student_{_safe_name(student_key)}"
    student_folder.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {"student_key": student_key, "meta": meta, "files": []}

    for stage_name, df in frames.items():
        if stages and stage_name not in stages:
            continue

        df2 = _sort_df(df)
        total_rows = int(df2.shape[0])

        if n > 0:
            df2 = df2.head(n)

        if not dump_all_columns:
            df2 = _select_columns(df2, columns)

        out_path = student_folder / f"{stage_name}.csv"
        df2.to_csv(out_path, index=False, encoding="utf-8-sig")

        manifest["files"].append(
            {
                "stage": stage_name,
                "path": str(out_path),
                "rows_total": total_rows,
                "rows_dumped": int(df2.shape[0]),
                "cols_dumped": int(df2.shape[1]),
            }
        )

    (student_folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def zip_dir(source_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in source_dir.rglob("*"):
            if p.is_file():
                zf.write(p, arcname=str(p.relative_to(source_dir)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug student vs mentor pool alignment (+ trace dumps)")

    parser.add_argument("--students", type=Path, required=True, help="Path to students Excel file.")
    parser.add_argument("--students-sheet", type=str, default=None, help="Optional: students sheet name.")
    parser.add_argument(
        "--id-column",
        type=str,
        default="student_id",
        help="Column name used as student identifier for --student-id selection (default: student_id).",
    )
    parser.add_argument(
        "--list-student-columns",
        action="store_true",
        help="Print canonicalized students columns and exit.",
    )

    parser.add_argument("--pool", type=Path, required=True, help="Path to mentor pool Excel file.")
    parser.add_argument(
        "--pool-type",
        type=str,
        default="auto",
        choices=["auto", "matrix", "inspactor"],
        help="Pool type: auto/matrix/inspactor. auto => uses 'matrix' if that sheet exists.",
    )
    parser.add_argument("--pool-sheet", type=str, default=None, help="Optional: explicit pool sheet name.")

    parser.add_argument("--limit", type=int, default=100, help="Max number of students to analyze (0 = all).")
    parser.add_argument("--output", type=Path, default=Path("debug_alignment_report.json"), help="Output JSON/CSV file.")
    parser.add_argument("--inspect", action="store_true", help="Print workbook sheet info (students & pool) then exit.")

    # Dump controls
    parser.add_argument("--dump-dir", type=Path, default=None, help="If set, dumps per-stage CSVs into this folder.")
    parser.add_argument("--student-id", action="append", default=[], help="Student identifier value (matches --id-column).")
    parser.add_argument("--student-index", action="append", default=[], help="Student index in sorted list (0-based).")
    parser.add_argument(
        "--dump-only-problems",
        action="store_true",
        help="Dumps traces only for students with zero_final or join mismatches (if no explicit selection).",
    )
    parser.add_argument(
        "--dump-stages",
        type=str,
        default="",
        help="Comma-separated stages to dump. Default = all. "
             "Valid: initial,type,group,gender,graduation_status,center,finance,school,strict_join,capacity_gate",
    )
    parser.add_argument("--dump-n", type=int, default=50, help="Rows per stage to dump (0 = all rows).")
    parser.add_argument("--dump-all-columns", action="store_true", help="Dump all columns instead of a curated set.")
    parser.add_argument("--dump-columns", type=str, default="", help="Comma-separated extra columns to include in dumps.")
    parser.add_argument("--zip-dumps", action="store_true", help="Create a zip archive next to dump-dir.")

    args = parser.parse_args()

    if args.inspect:
        print("== Students workbook ==")
        print(json.dumps(_inspect_workbook(args.students), ensure_ascii=False, indent=2))
        print("\n== Pool workbook ==")
        print(json.dumps(_inspect_workbook(args.pool), ensure_ascii=False, indent=2))
        return

    if not args.students.exists():
        _die(f"فایل دانش‌آموزها یافت نشد: {args.students}")
    if not args.pool.exists():
        _die(f"فایل استخر منتورها یافت نشد: {args.pool}")

    policy = load_policy()

    # Students load
    if args.students_sheet:
        with pd.ExcelFile(args.students) as wb:
            if args.students_sheet not in wb.sheet_names:
                _die(f"شیت «{args.students_sheet}» در فایل دانش‌آموزها نیست. شیت‌های موجود: {wb.sheet_names}")
            students_raw = wb.parse(args.students_sheet)
    else:
        students_raw = read_excel_first_sheet(args.students)

    students_df = canonicalize_students_frame(students_raw, policy=policy)

    if args.list_student_columns:
        print("✅ Canonicalized student columns:")
        for c in students_df.columns:
            print(" -", c)
        return

    # Pool load
    if args.pool_type == "auto":
        pool_type: PoolType = _auto_pool_type(args.pool)
    else:
        pool_type = args.pool_type  # type: ignore[assignment]

    pool_raw, detection = load_pool_with_detection(args.pool, pool_type=pool_type, pool_sheet=args.pool_sheet)
    pool_df = canonicalize_pool_frame(pool_raw, policy=policy, pool_source=pool_type)

    if pool_df.empty:
        _die(
            "استخر منتورها بعد از بارگذاری/کاننیکال‌سازی خالی است. "
            f"(pool_type={pool_type}, sheet={detection.selected_sheet})"
        )

    # Deterministic ordering
    # اگر id-column وجود داشت، با آن مرتب کن (برای repeatable indexes)
    if args.id_column in students_df.columns:
        ordered_students = students_df.sort_values(args.id_column, kind="stable")
    else:
        ordered_students = students_df.copy()

    limit = args.limit if args.limit > 0 else None
    if limit is not None:
        ordered_students = ordered_students.head(limit)

    # Reports
    reports = analyze_pool_alignment_batch(ordered_students, pool_df, policy=policy, limit=None)
    reports_list = [dict(r) for r in reports]
    summary = _summarize(reports_list)

    payload: dict[str, Any] = {
        "summary": summary,
        "meta": {
            "students_path": str(args.students),
            "students_sheet": args.students_sheet,
            "id_column": args.id_column,
            "pool_path": str(args.pool),
            "pool_type": pool_type,
            "pool_sheet": detection.selected_sheet,
            "pool_detection": detection.evidence,
            "pool_rows": int(pool_df.shape[0]),
            "pool_cols": int(pool_df.shape[1]),
        },
        "reports": reports_list,
    }
    _write_output(args.output, payload)

    print("Students analyzed:", summary["total_students_analyzed"])
    print("Errors:", summary["errors"])
    print("Zero initial candidates:", summary["students_with_zero_initial_candidates"])
    print("Zero final candidates:", summary["students_with_no_final_candidates"])
    print("Join-key mismatches:", summary["students_with_join_key_mismatches"])

    # Dumps
    if args.dump_dir is None:
        return

    dump_root = args.dump_dir
    dump_root.mkdir(parents=True, exist_ok=True)

    valid_stages = {
        "initial",
        "type",
        "group",
        "gender",
        "graduation_status",
        "center",
        "finance",
        "school",
        "strict_join",
        "capacity_gate",
    }
    stages: set[str] = set()
    if args.dump_stages.strip():
        parts = [p.strip() for p in args.dump_stages.split(",") if p.strip()]
        unknown = [p for p in parts if p not in valid_stages]
        if unknown:
            _die(f"مرحله‌های نامعتبر در --dump-stages: {unknown}. مجاز: {sorted(valid_stages)}")
        stages = set(parts)

    columns = _default_dump_columns(policy)
    if args.dump_columns.strip():
        extra = [c.strip() for c in args.dump_columns.split(",") if c.strip()]
        for c in extra:
            if c not in columns:
                columns.append(c)

    # Selection
    selected_rows: list[dict[str, Any]] = []
    by_id_values = [str(x).strip() for x in args.student_id if str(x).strip()]
    by_index: list[int] = []
    for raw in args.student_index:
        try:
            by_index.append(int(raw))
        except Exception:
            _die(f"--student-index باید عدد صحیح باشد (0-based). مقدار نامعتبر: {raw}")

    if by_id_values:
        if args.id_column not in ordered_students.columns:
            _die(
                f"ستون شناسه «{args.id_column}» در students وجود ندارد.\n"
                "برای دیدن ستون‌ها این را بزن:\n"
                "  python debug_pool_alignment.py --students <...> --pool <...> --list-student-columns\n"
                "یا به‌جای --student-id از --student-index استفاده کن."
            )
        id_set = set(by_id_values)
        for _, row in ordered_students.iterrows():
            if str(row.get(args.id_column, "")).strip() in id_set:
                selected_rows.append(row.to_dict())

    for idx in sorted(set(by_index)):
        if idx < 0 or idx >= len(ordered_students):
            _die(f"--student-index خارج از محدوده است: {idx} (max={len(ordered_students)-1})")
        selected_rows.append(ordered_students.iloc[idx].to_dict())

    if args.dump_only_problems and not (by_id_values or by_index):
        # derive from reports
        problem_keys: set[str] = set()
        key_col = args.id_column if args.id_column in ordered_students.columns else None
        for r in reports_list:
            if r.get("error") is None and (r.get("candidate_count_final") == 0 or r.get("join_key_mismatches")):
                if key_col and key_col in r:
                    problem_keys.add(str(r.get(key_col, "")).strip())
                elif "student_id" in r:
                    problem_keys.add(str(r.get("student_id", "")).strip())

        if problem_keys and key_col:
            for _, row in ordered_students.iterrows():
                if str(row.get(key_col, "")).strip() in problem_keys:
                    selected_rows.append(row.to_dict())

    if not selected_rows:
        print(
            "ℹ️ dump-dir فعال است اما هیچ دانش‌آموزی برای dump انتخاب نشده.\n"
            "از یکی از این‌ها استفاده کن:\n"
            "  --student-index 0\n"
            "  --student-id <value> --id-column <column_name>\n"
            "  --dump-only-problems"
        )
        return

    # Deduplicate
    seen = set()
    unique_selected: list[dict[str, Any]] = []
    for s in selected_rows:
        key = str(s.get(args.id_column, "")).strip() if args.id_column in s else json.dumps(s, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        unique_selected.append(s)

    dump_manifests: list[dict[str, Any]] = []
    for student in unique_selected:
        student_key = str(student.get(args.id_column, "")).strip() if args.id_column in student else "unknown"
        frames, meta = trace_student_pools(student=student, pool=pool_df, policy=policy)
        meta["student_key"] = student_key
        meta["id_column"] = args.id_column

        manifest = dump_student_trace(
            dump_root=dump_root,
            student_key=student_key or "unknown",
            frames=frames,
            meta=meta,
            stages=stages,
            n=int(args.dump_n),
            columns=columns,
            dump_all_columns=bool(args.dump_all_columns),
        )
        dump_manifests.append(manifest)

    (dump_root / "dump_manifest.json").write_text(
        json.dumps(
            {
                "dump_root": str(dump_root),
                "students_dumped": len(dump_manifests),
                "id_column": args.id_column,
                "pool_type": pool_type,
                "pool_sheet": detection.selected_sheet,
                "stages": sorted(stages) if stages else "ALL",
                "dump_n": int(args.dump_n),
                "dump_all_columns": bool(args.dump_all_columns),
                "default_columns": columns,
                "manifests": [m["student_key"] for m in dump_manifests],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"✅ Dumps written to: {dump_root}")

    if args.zip_dumps:
        zip_path = dump_root.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in dump_root.rglob("*"):
                if p.is_file():
                    zf.write(p, arcname=str(p.relative_to(dump_root)))
        print(f"✅ Dump zip created: {zip_path}")


if __name__ == "__main__":
    main()

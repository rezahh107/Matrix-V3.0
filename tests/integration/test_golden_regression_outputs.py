from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = ROOT / "tests" / "golden" / "outputs"
GOLDEN_OUTPUT_DIR = GOLDEN_DIR / "output"
GOLDEN_VALIDATION_DIR = GOLDEN_DIR / "output_validation"

OUTPUT_SHEETS: Mapping[str, list[str]] = {
    "allocations": ["student_id"],
    "updated_pool": ["کد کارمندی پشتیبان | mentor_id"],
    "logs": ["row_index"],
    "دلایل انتخاب پشتیبان": ["student_id"],
    "allocation_vs_pool_audit": ["student_id"],
}

VALIDATION_SHEETS: Mapping[str, list[str]] = {
    "summary": ["rule_id"],
    "students_per_mentor": ["mentor_id"],
    "school_binding_issues": ["mentor_id"],
    "allocation_capacity": ["mentor_id"],
    "join_keys": ["rule_id"],
    "student_counts": ["metric"],
    "pool_join_key_duplicates": ["کد کارمندی پشتیبان"],
    "pool_join_conflicts": ["mentor_id"],
    "pool_detection": ["pool_type"],
    "alloc_join_summary": ["rule_id"],
    "alloc_join_mismatches": ["student_id"],
    "pool_alignment_preflight": ["student_id", "join_key_values"],
}


def load_xlsx_sheet_as_df(path: Path, sheet_name: str) -> pd.DataFrame:
    try:
        return pd.read_excel(path, sheet_name=sheet_name, dtype=object)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise AssertionError(f"Sheet '{sheet_name}' missing in {path}") from exc


def _normalize_value(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value)
    if text.lower() == "nan":
        return ""
    if text.endswith(".0") and text.replace(".0", "").isdigit():
        return text[:-2]
    return text.strip()


def normalize_df(df: pd.DataFrame, key_columns: Iterable[str]) -> pd.DataFrame:
    normalized = df.copy()
    normalized.columns = [str(col).strip() for col in normalized.columns]
    for column in normalized.columns:
        normalized[column] = normalized[column].map(_normalize_value)
    normalized = normalized.reindex(sorted(normalized.columns), axis=1)
    keys = [col for col in key_columns if col in normalized.columns]
    if keys:
        normalized = normalized.sort_values(keys, kind="mergesort")
    else:
        normalized = normalized.sort_values(list(normalized.columns), kind="mergesort")
    normalized = normalized.reset_index(drop=True)
    return normalized


def compare_dfs(
    df_new: pd.DataFrame,
    df_golden: pd.DataFrame,
    *,
    key_columns: Iterable[str],
) -> list[dict[str, object]]:
    keys = [col for col in key_columns if col in df_new.columns]
    if keys:
        new_indexed = df_new.set_index(keys)
        golden_indexed = df_golden.set_index(keys)
    else:
        new_indexed = df_new.set_index(df_new.index)
        golden_indexed = df_golden.set_index(df_golden.index)

    combined_index = new_indexed.index.union(golden_indexed.index)
    new_aligned = new_indexed.reindex(combined_index).fillna("")
    golden_aligned = golden_indexed.reindex(combined_index).fillna("")

    differences: list[dict[str, object]] = []
    for idx in combined_index:
        new_row = new_aligned.loc[idx]
        golden_row = golden_aligned.loc[idx]
        if new_row.equals(golden_row):
            continue
        diff_columns = [col for col in new_aligned.columns if new_row[col] != golden_row[col]]
        key_payload: dict[str, object]
        if isinstance(idx, tuple):
            key_payload = {f"key_{i}": value for i, value in enumerate(idx)}
        else:
            key_payload = {"key": idx}
        differences.append(
            {
                **key_payload,
                "columns": diff_columns,
                "golden": golden_row[diff_columns].to_dict(),
                "new": new_row[diff_columns].to_dict(),
            }
        )
    return differences


def _write_diff(artifact_dir: Path, sheet: str, diffs: list[dict[str, object]]) -> Path:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for diff in diffs:
        columns = diff.pop("columns", [])
        for column in columns:
            record = {**diff}
            record["column"] = column
            record["golden"] = diff.get("golden", {}).get(column, "")
            record["new"] = diff.get("new", {}).get(column, "")
            records.append(record)
    artifact_path = artifact_dir / f"{sheet}_diff.csv"
    pd.DataFrame(records).to_csv(artifact_path, index=False)
    return artifact_path


def _sheet_csv_path(sheet: str, base_dir: Path) -> Path:
    safe_name = sheet.replace("/", "_")
    return base_dir / f"{safe_name}.csv"


def _load_golden_sheet(sheet: str, base_dir: Path) -> pd.DataFrame:
    csv_path = _sheet_csv_path(sheet, base_dir)
    if not csv_path.exists():
        raise AssertionError(f"Golden sheet missing: {csv_path}")
    return pd.read_csv(csv_path, dtype=object).fillna("")


def _assert_workbook_matches(
    generated: Path,
    golden_base: Path,
    *,
    sheets: Mapping[str, list[str]],
    artifact_dir: Path,
) -> None:
    failures: list[str] = []
    for sheet, keys in sheets.items():
        new_df = normalize_df(load_xlsx_sheet_as_df(generated, sheet), keys)
        golden_df = normalize_df(_load_golden_sheet(sheet, golden_base), keys)
        diffs = compare_dfs(new_df, golden_df, key_columns=keys)
        if diffs:
            diff_path = _write_diff(artifact_dir, sheet, diffs)
            failures.append(f"Sheet '{sheet}' differs; see {diff_path}")
    if failures:
        pytest.fail("; ".join(failures))


def _write_golden_snapshot(output: Path, validation: Path) -> None:
    GOLDEN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    GOLDEN_VALIDATION_DIR.mkdir(parents=True, exist_ok=True)

    for sheet, keys in OUTPUT_SHEETS.items():
        df = normalize_df(load_xlsx_sheet_as_df(output, sheet), keys)
        df.to_csv(_sheet_csv_path(sheet, GOLDEN_OUTPUT_DIR), index=False)

    for sheet, keys in VALIDATION_SHEETS.items():
        df = normalize_df(load_xlsx_sheet_as_df(validation, sheet), keys)
        df.to_csv(_sheet_csv_path(sheet, GOLDEN_VALIDATION_DIR), index=False)


def test_golden_regression_outputs(
    canonical_allocation_outputs: tuple[Path, Path], tmp_path: Path
) -> None:
    output_path, validation_path = canonical_allocation_outputs

    if os.environ.get("UPDATE_GOLDEN") == "1":
        _write_golden_snapshot(output_path, validation_path)
        return

    missing = []
    for sheet in OUTPUT_SHEETS:
        if not _sheet_csv_path(sheet, GOLDEN_OUTPUT_DIR).exists():
            missing.append(_sheet_csv_path(sheet, GOLDEN_OUTPUT_DIR))
    for sheet in VALIDATION_SHEETS:
        if not _sheet_csv_path(sheet, GOLDEN_VALIDATION_DIR).exists():
            missing.append(_sheet_csv_path(sheet, GOLDEN_VALIDATION_DIR))
    if missing:
        pytest.fail(
            "Golden outputs are missing. Run with UPDATE_GOLDEN=1 to create them: "
            + ", ".join(str(path) for path in missing)
        )

    artifact_dir = tmp_path / "diffs"
    _assert_workbook_matches(
        output_path,
        GOLDEN_OUTPUT_DIR,
        sheets=OUTPUT_SHEETS,
        artifact_dir=artifact_dir,
    )
    _assert_workbook_matches(
        validation_path,
        GOLDEN_VALIDATION_DIR,
        sheets=VALIDATION_SHEETS,
        artifact_dir=artifact_dir,
    )

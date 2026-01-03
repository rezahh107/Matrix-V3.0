from __future__ import annotations

import json
import os
import re
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

VOLATILE_COLUMN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"timestamp", re.IGNORECASE),
    re.compile(r"time$", re.IGNORECASE),
    re.compile(r"created_at", re.IGNORECASE),
    re.compile(r"updated_at", re.IGNORECASE),
    re.compile(r"run_id", re.IGNORECASE),
)

IGNORED_COLUMNS_BY_SHEET: Mapping[str, set[str]] = {
    # Logs can contain derived traces that embed timestamps; normalize by dropping volatile fields.
    "logs": {"phase_rule_trace"},
}


def load_xlsx_sheet_as_df(path: Path, sheet_name: str) -> pd.DataFrame:
    try:
        return pd.read_excel(path, sheet_name=sheet_name, dtype=object)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise AssertionError(f"Sheet '{sheet_name}' missing in {path}") from exc


def _normalize_string(text: str) -> str:
    replacements = {"ي": "ی", "ك": "ک"}
    for src, tgt in replacements.items():
        text = text.replace(src, tgt)
    text = re.sub(r"\s+", " ", text.strip())
    return text


def _normalize_value(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    text = _normalize_string(str(value))
    if text.lower() == "nan":
        return ""
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def _drop_ignored_columns(sheet: str, df: pd.DataFrame) -> pd.DataFrame:
    ignored = set(IGNORED_COLUMNS_BY_SHEET.get(sheet, set()))
    cols_to_drop = set()
    for column in df.columns:
        if column in ignored:
            cols_to_drop.add(column)
            continue
        for pattern in VOLATILE_COLUMN_PATTERNS:
            if pattern.search(str(column)):
                cols_to_drop.add(column)
                break
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop, errors="ignore")
    return df


def normalize_df(df: pd.DataFrame, key_columns: Iterable[str], *, sheet: str) -> pd.DataFrame:
    normalized = df.copy()
    normalized.columns = [_normalize_string(str(col)) for col in normalized.columns]
    normalized = _drop_ignored_columns(sheet, normalized)
    for column in normalized.columns:
        normalized[column] = normalized[column].map(_normalize_value)

    normalized = normalized.reindex(sorted(normalized.columns), axis=1)

    keys = [col for col in key_columns if col in normalized.columns]
    sort_by = keys + [col for col in normalized.columns if col not in keys]
    normalized = normalized.sort_values(sort_by, kind="mergesort")
    normalized = normalized.reset_index(drop=True)
    return normalized


def compare_dfs(
    df_new: pd.DataFrame,
    df_golden: pd.DataFrame,
    *,
    key_columns: Iterable[str],
) -> list[dict[str, object]]:
    combined_columns = sorted(set(df_new.columns) | set(df_golden.columns))
    df_new = df_new.reindex(columns=combined_columns, fill_value="")
    df_golden = df_golden.reindex(columns=combined_columns, fill_value="")

    keys = [col for col in key_columns if col in combined_columns]
    sort_by = keys + [col for col in combined_columns if col not in keys]

    df_new = df_new.sort_values(sort_by, kind="mergesort")
    df_golden = df_golden.sort_values(sort_by, kind="mergesort")

    group_keys = keys if keys else sort_by
    df_new["__dup_rank"] = df_new.groupby(group_keys, dropna=False).cumcount()
    df_golden["__dup_rank"] = df_golden.groupby(group_keys, dropna=False).cumcount()

    composite_keys = group_keys + ["__dup_rank"]

    new_indexed = df_new.set_index(composite_keys)
    golden_indexed = df_golden.set_index(composite_keys)

    combined_index = new_indexed.index.union(golden_indexed.index)
    new_aligned = new_indexed.reindex(combined_index).fillna("")
    golden_aligned = golden_indexed.reindex(combined_index).fillna("")

    differences: list[dict[str, object]] = []
    diff_mask = new_aligned.ne(golden_aligned)
    for idx in combined_index:
        row_mask = diff_mask.loc[idx]
        if not row_mask.any():
            continue
        diff_columns = list(row_mask[row_mask].index)
        key_payload = {
            key: value
            for key, value in zip(composite_keys, idx if isinstance(idx, tuple) else (idx,))
            if key != "__dup_rank"
        }
        for column in diff_columns:
            differences.append(
                {
                    **key_payload,
                    "column": column,
                    "golden": golden_aligned.at[idx, column],
                    "new": new_aligned.at[idx, column],
                }
            )
    return differences


def _write_diff(artifact_dir: Path, sheet: str, diffs: list[dict[str, object]]) -> Path:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    for diff in diffs:
        diff.setdefault("sheet", sheet)
    artifact_path = artifact_dir / f"{sheet}_diff.csv"
    pd.DataFrame(diffs).to_csv(artifact_path, index=False)
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
        new_df = normalize_df(load_xlsx_sheet_as_df(generated, sheet), keys, sheet=sheet)
        golden_df = normalize_df(_load_golden_sheet(sheet, golden_base), keys, sheet=sheet)
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
        df = normalize_df(load_xlsx_sheet_as_df(output, sheet), keys, sheet=sheet)
        df.to_csv(_sheet_csv_path(sheet, GOLDEN_OUTPUT_DIR), index=False)

    for sheet, keys in VALIDATION_SHEETS.items():
        df = normalize_df(load_xlsx_sheet_as_df(validation, sheet), keys, sheet=sheet)
        df.to_csv(_sheet_csv_path(sheet, GOLDEN_VALIDATION_DIR), index=False)


def test_golden_regression_outputs(
    canonical_allocation_outputs: tuple[Path, Path], tmp_path: Path
) -> None:
    output_path, validation_path = canonical_allocation_outputs

    if os.environ.get("UPDATE_GOLDEN") == "1":
        _write_golden_snapshot(output_path, validation_path)
        return

    missing = []
    for sheets, base_dir in [
        (OUTPUT_SHEETS, GOLDEN_OUTPUT_DIR),
        (VALIDATION_SHEETS, GOLDEN_VALIDATION_DIR),
    ]:
        for sheet in sheets:
            if not _sheet_csv_path(sheet, base_dir).exists():
                missing.append(_sheet_csv_path(sheet, base_dir))
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

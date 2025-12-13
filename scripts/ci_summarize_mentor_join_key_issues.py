"""Summarize mentor join-key/gender issues dumped from golden regression.

Typical usage (CSV produced by `--dump-mentor-issues`):

```
PYTHONPATH=. python scripts/ci_summarize_mentor_join_key_issues.py \
  --issues-csv ci/artifacts/mentor_join_key_issues.csv \
  --output ci/artifacts/mentor_join_key_issues_summary.md
```

The script is read-only: it only reads the issues CSV and writes a markdown
summary; it never modifies golden inputs.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_COLUMNS = [
    "entity_type",
    "row_index",
    "column",
    "raw_value",
    "error_code",
]


def _load_issues(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"Issue CSV not found: {csv_path}")
    frame = pd.read_csv(csv_path)
    expected = [col for col in DEFAULT_COLUMNS if col in frame.columns]
    frame = frame[expected].copy()
    return frame.convert_dtypes()


def _counter_summary(counter: Counter[Any], *, label: str, limit: int = 5) -> str:
    if not counter:
        return f"- {label}: none"
    lines = [f"- {label} (top {limit}):"]
    for value, count in counter.most_common(limit):
        lines.append(f"  - {value}: {count}")
    remainder = sum(counter.values()) - sum(count for _, count in counter.most_common(limit))
    if remainder > 0:
        lines.append(f"  - other: {remainder}")
    return "\n".join(lines)


def _sample_raw_values(frame: pd.DataFrame, column: str, error_code: str, limit: int = 5) -> list[str]:
    subset = frame[(frame["column"] == column) & (frame["error_code"] == error_code)]
    samples = subset["raw_value"].dropna().astype("string").unique().tolist()
    return samples[:limit]


def summarize(csv_path: Path, output_path: Path, *, sample_limit: int = 5) -> str:
    frame = _load_issues(csv_path)
    total_rows = len(frame)
    error_counts = Counter(frame.get("error_code", []))
    column_counts = Counter(frame.get("column", []))
    combo_counts = Counter(zip(frame.get("column", []), frame.get("error_code", [])))

    lines = [
        "# Mentor join-key/gender issues summary",
        f"- source: {csv_path}",
        f"- total rows: {total_rows}",
        "",
        _counter_summary(error_counts, label="issues by error_code"),
        "",
        _counter_summary(column_counts, label="issues by column"),
        "",
        "## Top (column, error_code) combinations",
    ]

    for (column, error_code), count in combo_counts.most_common(5):
        samples = _sample_raw_values(frame, column, error_code, limit=sample_limit)
        hint = "populate missing values" if "MISSING" in str(error_code).upper() else "normalize invalid values"
        lines.append(f"- {column} / {error_code}: {count} rows; sample raw values: {samples} (hint: {hint})")

    rendered = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize mentor join-key/gender issues dumped by golden regression "
            "(usually produced via --dump-mentor-issues). Writes a markdown "
            "summary to help humans fix golden Excel inputs; does not mutate "
            "any data."
        )
    )
    parser.add_argument(
        "--issues-csv",
        type=Path,
        default=Path("ci/artifacts/mentor_join_key_issues.csv"),
        help=(
            "Path to the mentor issues CSV produced by golden regression "
            "(--dump-mentor-issues)."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("ci/artifacts/mentor_join_key_issues_summary.md"),
        help=(
            "Where to write the markdown summary; parent directories are created "
            "as needed."
        ),
    )
    args = parser.parse_args()
    try:
        rendered = summarize(args.issues_csv, args.output)
    except Exception as exc:  # pragma: no cover - CLI safety
        print(f"Failed to summarize mentor issues: {exc}")
        return 1

    print(rendered)
    print(f"Summary written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

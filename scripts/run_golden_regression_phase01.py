"""Golden regression phase01 runner with UTF-8-safe stdout/stderr."""

from __future__ import annotations

import io
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from app.core.build_matrix import COL_GROUP_INCLUDED
from app.core.canonical_frames import canonicalize_headers
from app.core.common.columns import dedupe_columns
from app.core.policy_loader import load_policy
from app.infra.local_database import LocalDatabase
from app.infra.reference_mentors_repository import import_mentor_pool_with_validation
from app.infra.references.schools import import_school_report_from_excel

GOLDEN_DIR = Path("docs/golden_datasets/phase01_lock_current_behavior")
GOLDEN_INSPACTOR = GOLDEN_DIR / "InspactorReport-1404_09_15-3570.xlsx"
GOLDEN_SCHOOL = GOLDEN_DIR / "SchoolReport-1404_09_15-3570.xlsx"
SNAPSHOT_DIR = Path("ci/golden_snapshots/phase01_lock_current_behavior")
SNAPSHOT_POOL = SNAPSHOT_DIR / "mentor_pool.csv"
SNAPSHOT_ISSUES = SNAPSHOT_DIR / "mentor_join_key_issues.csv"

_LOG_PREFIX = "[GOLDEN]"


class GoldenRegressionError(RuntimeError):
    """Raised when golden regression cannot proceed or drifts are detected."""


@dataclass(frozen=True)
class Phase01Run:
    """Container for outputs produced during the phase01 golden run."""

    mentor_pool: pd.DataFrame
    join_key_issues: pd.DataFrame


def _log(message: str) -> None:
    print(f"{_LOG_PREFIX} {message}")


def _configure_stdio() -> None:
    """Ensure stdout/stderr can emit Unicode messages on Windows runners."""

    def _rewrap(stream_name: str) -> None:
        stream = getattr(sys, stream_name)
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
            return
        except (AttributeError, ValueError):
            pass

        try:
            wrapped = io.TextIOWrapper(
                stream.detach(), encoding="utf-8", errors="backslashreplace"
            )
        except Exception:
            return
        setattr(sys, stream_name, wrapped)

    _rewrap("stdout")
    _rewrap("stderr")


def _require_files(paths: Sequence[Path]) -> None:
    for path in paths:
        if not path.exists():
            raise GoldenRegressionError(
                f"GOLDEN_REGRESSION_ERROR: Missing golden input file: {path}"
            )


def _load_expected_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise GoldenRegressionError(
            f"GOLDEN_REGRESSION_ERROR: Missing golden snapshot file: {path}"
        )
    return pd.read_csv(path)


def _format_join_key_error(issues: Sequence[object]) -> str:
    for issue in issues:
        column = getattr(issue, "column", None)
        reason = str(getattr(issue, "error_code", ""))
        if column == COL_GROUP_INCLUDED and reason.upper() in {
            "MISSING_COLUMN",
            "MISSING_INCLUDED_GROUP_COLUMN",
        }:
            return (
                "GOLDEN_REGRESSION_ERROR: Inspactor mentor input is missing the required "
                f"'{COL_GROUP_INCLUDED}' column. This column is the only authorized "
                "source for group_code; the legacy 'گروه آزمایشی' column is QA-only."
            )
    return (
        "GOLDEN_REGRESSION_ERROR: Mentor pipeline reported P0 issues: "
        f"{list(issues)}"
    )


def _canonicalize_pool(df: pd.DataFrame) -> pd.DataFrame:
    canonical = dedupe_columns(canonicalize_headers(df, header_mode="en"))

    def _maybe_numeric(series: pd.Series) -> pd.Series:
        try:
            return pd.to_numeric(series, errors="raise")
        except Exception:
            return series

    canonical = canonical.apply(_maybe_numeric)
    if canonical.columns.duplicated().any():
        duplicated = sorted({col for col, is_dup in zip(canonical.columns, canonical.columns.duplicated()) if is_dup})
        joined = ", ".join(duplicated)
        raise GoldenRegressionError(
            "GOLDEN_REGRESSION_ERROR: canonical pool still has duplicate columns after "
            f"header normalization: {joined}"
        )
    sort_keys = [
        "group_code",
        "gender",
        "graduation_status",
        "center",
        "finance",
        "school_code",
        "mentor_id",
    ]
    missing = [key for key in sort_keys if key not in canonical.columns]
    if missing:
        joined = ", ".join(missing)
        raise GoldenRegressionError(
            f"GOLDEN_REGRESSION_ERROR: canonical pool is missing expected columns: {joined}"
        )
    try:
        canonical = canonical.assign(
            **{
                key: pd.to_numeric(canonical[key], errors="raise").astype("Int64")
                for key in sort_keys
            }
        )
    except Exception as exc:  # pragma: no cover - defensive numeric normalization
        raise GoldenRegressionError(
            "GOLDEN_REGRESSION_ERROR: canonical pool contains non-numeric join-key or mentor_id values"
        ) from exc
    return canonical.sort_values(by=sort_keys, kind="mergesort").reset_index(drop=True)


def _issues_to_frame(issues: Sequence[object]) -> pd.DataFrame:
    payload: list[dict[str, object]] = []
    for issue in issues:
        entity_type = getattr(issue, "entity_type", None)
        row_index = getattr(issue, "row_index", None)
        column = getattr(issue, "column", None)
        raw_value = getattr(issue, "raw_value", None)
        error_code = getattr(issue, "error_code", None)
        payload.append(
            {
                "entity_type": entity_type,
                "row_index": row_index,
                "column": column,
                "raw_value": raw_value,
                "error_code": error_code,
            }
        )
    frame = pd.DataFrame(payload).convert_dtypes()
    if frame.empty:
        return pd.DataFrame(
            columns=["entity_type", "row_index", "column", "raw_value", "error_code"]
        )
    return frame.sort_values(by=["row_index", "column"]).reset_index(drop=True)


def _compare_frames(label: str, expected: pd.DataFrame, current: pd.DataFrame) -> None:
    expected_sorted = (
        expected.sort_index(axis=1)
        .reset_index(drop=True)
        .convert_dtypes()
        .where(lambda df: ~df.isna(), pd.NA)
    )
    current_sorted = (
        current.sort_index(axis=1)
        .reset_index(drop=True)
        .convert_dtypes()
        .where(lambda df: ~df.isna(), pd.NA)
    )
    if "raw_value" in expected_sorted.columns and "raw_value" in current_sorted.columns:
        expected_sorted["raw_value"] = expected_sorted["raw_value"].astype("string")
        current_sorted["raw_value"] = current_sorted["raw_value"].astype("string")
    if expected_sorted.shape != current_sorted.shape:
        raise GoldenRegressionError(
            f"GOLDEN_REGRESSION_ERROR: {label} shape drift: "
            f"expected={expected_sorted.shape} got={current_sorted.shape}"
        )
    try:
        pd.testing.assert_frame_equal(expected_sorted, current_sorted, check_dtype=False)
    except AssertionError as exc:  # pragma: no cover - diff summary handled below
        raise GoldenRegressionError(
            f"GOLDEN_REGRESSION_ERROR: {label} content drift detected: {exc}"
        ) from exc


def _run_phase01() -> Phase01Run:
    _require_files([GOLDEN_INSPACTOR, GOLDEN_SCHOOL])
    policy_path = Path("config/policy.json")
    if not policy_path.exists():
        raise GoldenRegressionError(
            f"GOLDEN_REGRESSION_ERROR: Missing policy file: {policy_path}. "
            "Ensure the policy SSoT is available."
        )
    _log("Starting phase01 lock_current_behavior run...")
    policy = load_policy(policy_path)
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "golden_phase01.db"
        db = LocalDatabase(db_path)
        try:
            db.initialize()
            _log("Importing school report into temporary cache...")
            import_school_report_from_excel(GOLDEN_SCHOOL, db=db)
            _log("Importing mentor pool with join-key validation...")
            validation = import_mentor_pool_with_validation(
                GOLDEN_INSPACTOR, db=db, policy=policy, pool_source="inspactor"
            )
            if validation.issues:
                raise GoldenRegressionError(_format_join_key_error(validation.issues))
            pool = _canonicalize_pool(validation.canonical_df)
            issues = _issues_to_frame(validation.issues)
        finally:
            try:
                db.close_all_connections()
            except Exception as exc:  # pragma: no cover - defensive close
                raise GoldenRegressionError(
                    "GOLDEN_REGRESSION_ERROR: Failed to close golden_phase01.db before "
                    f"cleanup: {exc}"
                ) from exc
    return Phase01Run(mentor_pool=pool, join_key_issues=issues)


def main() -> int:
    _configure_stdio()
    try:
        run = _run_phase01()
        _log("Comparing mentor pool snapshot...")
        expected_pool = _load_expected_frame(SNAPSHOT_POOL)
        _compare_frames("mentor_pool", expected_pool, run.mentor_pool)
        _log("Comparing join-key validation issues snapshot...")
        expected_issues = _load_expected_frame(SNAPSHOT_ISSUES)
        _compare_frames("join_key_issues", expected_issues, run.join_key_issues)
    except GoldenRegressionError as exc:
        print(exc)
        return 1

    _log("Golden regression phase01_lock_current_behavior: PASSED (no drift detected)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

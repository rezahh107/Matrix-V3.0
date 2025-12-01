from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import pandas as pd

JOIN_KEYS: Final[list[str]] = [
    "کدرشته",
    "جنسیت",
    "دانش آموز فارغ",
    "مرکز گلستان صدرا",
    "مالی حکمت بنیاد",
    "کد مدرسه",
]

# Policy v1.0.3: only these 11 groups support both student (1) and graduate (0).
DUAL_STATUS_GROUPS: Final[frozenset[int]] = frozenset({1, 3, 5, 7, 8, 9, 11, 12, 14, 17, 18})


def allowed_statuses_for_group(group_code: int, *, is_school_branch: bool) -> Sequence[int]:
    """Return graduation_status domain for the given group and mentor branch.

    Policy v1.0.3 states that only the dual-status groups can appear with
    graduation_status == 0 (graduate). All other groups are student-only (1).
    School-branch mentors are also student-only unless Policy changes.
    """

    if is_school_branch:
        return (1,)
    if group_code in DUAL_STATUS_GROUPS:
        return (1, 0)
    return (1,)


def _require_columns(frame: pd.DataFrame, required: Sequence[str]) -> None:
    missing = [col for col in required if col not in frame.columns]
    if missing:
        joined = ", ".join(missing)
        raise KeyError(f"Missing required columns for matrix build: {joined}")


def build_matrix_v1_0_2(base_rows: pd.DataFrame) -> pd.DataFrame:
    """Explode mentor rows into eligibility matrix rows (Infra helper).

    This builder respects the 6 join keys defined in the LAW/Technical SSoT and
    enforces the group-specific graduation_status domain from Policy v1.0.3.
    Normal mentors use the per-group allowed statuses; school mentors remain
    student-only.
    """

    required_cols: tuple[str, ...] = (
        "کدرشته",
        "جنسیت",
        "مرکز گلستان صدرا",
        "مالی حکمت بنیاد",
        "کد مدرسه",
        "عادی مدرسه",
    )
    _require_columns(base_rows, required_cols)

    if base_rows.empty:
        return pd.DataFrame(columns=[*required_cols, "دانش آموز فارغ"])

    records: list[dict[str, int | str]] = []
    for record in base_rows.to_dict(orient="records"):
        group_code = int(record["کدرشته"])
        gender = int(record["جنسیت"])
        center = int(record["مرکز گلستان صدرا"])
        finance = int(record["مالی حکمت بنیاد"])
        school_code = int(record["کد مدرسه"])
        branch_label = str(record.get("عادی مدرسه", "")).strip() or "عادی"
        is_school_branch = branch_label == "مدرسه‌ای"

        statuses = allowed_statuses_for_group(group_code, is_school_branch=is_school_branch)
        for status in statuses:
            records.append(
                {
                    "کدرشته": group_code,
                    "جنسیت": gender,
                    "دانش آموز فارغ": int(status),
                    "مرکز گلستان صدرا": center,
                    "مالی حکمت بنیاد": finance,
                    "کد مدرسه": school_code,
                    "عادی مدرسه": branch_label,
                }
            )

    matrix = pd.DataFrame.from_records(records, columns=[*required_cols, "دانش آموز فارغ"])
    for key in JOIN_KEYS:
        matrix[key] = matrix[key].astype("Int64")
    return matrix

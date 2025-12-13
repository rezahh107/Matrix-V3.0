"""LEGACY MATRIX BUILDER (Policy v1.x / SSoT v1.x)

This Infra helper is retained for historical comparison and migrations.
The canonical Smart Student Allocation engine is Matrix v3
(MentorPipelineV3, StudentPipelineV3, MatrixCore v3) as defined in:

- docs/📚 Refactor Narrative v3.0 — روایت کامل و ماشین‌فهم از مسأله تا راه‌حل.md
- LAW_Smart_Student_Allocation_v3.0.md
- Technical_SSoT_Smart_Student_Allocation_v3.0-TECH.md
"""

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
# دقت شود کدرشتهٔ 7 (هنر کنکوری) با کدرشتهٔ 33 (پایه هفتم) متفاوت است.
DUAL_STATUS_GROUPS: Final[frozenset[int]] = frozenset({1, 3, 5, 7, 8, 9, 11, 12, 14, 17, 18})
STUDENT_ONLY_GROUPS: Final[frozenset[int]] = frozenset({33, 31, 27})


def allowed_statuses_for_group(group_code: int, *, is_school_branch: bool) -> Sequence[int]:
    """Return graduation_status domain for the given group and mentor branch.

    Policy v1.0.3 states that only the dual-status groups can appear with
    graduation_status == 0 (graduate). All other groups are student-only (1).
    School-branch mentors are also student-only unless Policy changes.
    """

    if is_school_branch:
        return (1,)
    if group_code in STUDENT_ONLY_GROUPS:
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

    matrix = base_rows.copy()

    matrix["عادی مدرسه"] = matrix["عادی مدرسه"].fillna("").astype(str).str.strip()
    matrix.loc[matrix["عادی مدرسه"] == "", "عادی مدرسه"] = "عادی"

    matrix["statuses"] = matrix.apply(
        lambda row: allowed_statuses_for_group(
            row["کدرشته"], is_school_branch=(row["عادی مدرسه"] == "مدرسه‌ای")
        ),
        axis=1,
    )

    matrix = matrix.explode("statuses").rename(columns={"statuses": "دانش آموز فارغ"})

    final_cols = [*required_cols, "دانش آموز فارغ"]
    matrix = matrix[final_cols]
    for key in JOIN_KEYS:
        if key in matrix.columns:
            matrix[key] = matrix[key].astype("Int64")

    return matrix

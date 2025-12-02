from __future__ import annotations

import pandas as pd

from app.core.build_matrix import _explode_rows
from app.core.common.domain import BuildConfig


def _dual_base_frame(alias_normal: str | None) -> pd.DataFrame:
    cfg = BuildConfig()
    return pd.DataFrame(
        {
            "supporter": ["A"],
            "manager": ["B"],
            "mentor_id": ["EMP-1"],
            "mentor_row_id": [1],
            "center_code": [1],
            "center_text": ["مرکز"],
            "group_pairs": [[("ریاضی", 1)]],
            "genders": [[1]],
            "school_codes": [[0]],
            "schools_normal": [[""]],
            "finance": [[0]],
            "statuses_normal": [[1]],
            "statuses_school": [[1]],
            "alias_normal": [alias_normal],
            "alias_school": ["EMP-1"],
            "mentor_school_binding_mode": [cfg.policy.mentor_school_binding.global_mode],
            "has_school_constraint": [True],
            "can_normal": [True],
            "can_school": [True],
            "capacity_current": [0],
            "capacity_special": [0],
            "capacity_remaining": [0],
            "school_count": [1],
        }
    )


def test_dual_mentor_produces_normal_and_school_rows() -> None:
    cfg = BuildConfig()
    base = _dual_base_frame(alias_normal="1200")
    cap_current_col = cfg.capacity_current_column or "تعداد داوطلبان تحت پوشش"
    cap_special_col = cfg.capacity_special_column or "تعداد تحت پوشش خاص"
    remaining_col = cfg.remaining_capacity_column or "remaining_capacity"
    school_code_col = cfg.school_code_column or "کد مدرسه"

    normal = _explode_rows(
        base,
        alias_col="alias_normal",
        status_col="statuses_normal",
        school_col="schools_normal",
        type_label="عادی",
        code_to_name_school={},
        cfg=cfg,
        cap_current_col=cap_current_col,
        cap_special_col=cap_special_col,
        remaining_col=remaining_col,
        school_code_col=school_code_col,
    )
    school = _explode_rows(
        base,
        alias_col="alias_school",
        status_col="statuses_school",
        school_col="school_codes",
        type_label="مدرسه‌ای",
        code_to_name_school={},
        cfg=cfg,
        cap_current_col=cap_current_col,
        cap_special_col=cap_special_col,
        remaining_col=remaining_col,
        school_code_col=school_code_col,
    )

    assert not normal.empty
    assert not school.empty
    assert set(normal["عادی مدرسه"].unique()) == {"عادی"}
    assert set(school["عادی مدرسه"].unique()) == {"مدرسه‌ای"}
    assert int(school.iloc[0][school_code_col]) == 0


def test_alias_below_threshold_blocks_normal_rows() -> None:
    cfg = BuildConfig()
    base = _dual_base_frame(alias_normal=None)
    cap_current_col = cfg.capacity_current_column or "تعداد داوطلبان تحت پوشش"
    cap_special_col = cfg.capacity_special_column or "تعداد تحت پوشش خاص"
    remaining_col = cfg.remaining_capacity_column or "remaining_capacity"
    school_code_col = cfg.school_code_column or "کد مدرسه"

    normal = _explode_rows(
        base,
        alias_col="alias_normal",
        status_col="statuses_normal",
        school_col="schools_normal",
        type_label="عادی",
        code_to_name_school={},
        cfg=cfg,
        cap_current_col=cap_current_col,
        cap_special_col=cap_special_col,
        remaining_col=remaining_col,
        school_code_col=school_code_col,
    )

    assert normal.empty

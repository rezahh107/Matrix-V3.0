from __future__ import annotations

import pandas as pd
import pytest

from app.core.allocate_students import _phase_stage_extras


def test_phase_stage_extras_duplicate_capacity_column_uses_first_column() -> None:
    pool = pd.DataFrame(
        [[1, 10], [2, 20]],
        columns=["remaining_capacity", "remaining_capacity"],
    )

    selection = pool["remaining_capacity"]
    assert isinstance(selection, pd.DataFrame)

    with pytest.raises(TypeError):
        pd.to_numeric(selection, errors="coerce")

    extras = _phase_stage_extras("center_phase_start", pool, "remaining_capacity")

    assert extras["message"] == "شروع فاز مرکزی پس از اتمام مدرسه‌ای"
    assert extras["remaining_capacity"] == 3

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.core.allocation.channels import AllocationChannel, derive_channels_for_students
from app.core.policy.config import AllocationChannelConfig


@dataclass(frozen=True)
class _Columns:
    school_code: str


class _FakePolicy:
    def __init__(self) -> None:
        self.columns = _Columns(school_code="کد مدرسه")
        self._stage_columns = {"center": "مرکز گلستان صدرا"}
        self.allocation_channels = AllocationChannelConfig(
            school_codes=(10,),
            center_channels={"GOLESTAN": (1,), "SADRA": (2,)},
            registration_center_column="registration_center",
            educational_status_column="student_educational_status",
            active_status_values=(0,),
        )

    def stage_column(self, stage: str) -> str:
        return self._stage_columns[stage]


def test_duplicate_center_columns_use_first_value() -> None:
    policy = _FakePolicy()
    center_column = policy.stage_column("center")

    students = pd.DataFrame(
        [[1, 2], [2, 1]],
        columns=[center_column, center_column],
    )

    result = derive_channels_for_students(students, policy)

    assert result.tolist() == [
        AllocationChannel.GOLESTAN,
        AllocationChannel.SADRA,
    ]

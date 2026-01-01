from __future__ import annotations

from dataclasses import replace
from typing import cast

import pandas as pd
import pytest

from app.core.allocation.channels import _active_student_mask
from app.core.common.eligibility_channel import EligibilitySpec
from app.core.common.isin_guard import require_isin_values
from app.core.common.join_resolver import JoinKeyResolver
from app.core.policy.config import AllocationChannelConfig
from app.core.policy_loader import load_policy


def test_isin_guard_rejects_scalar_int() -> None:
    with pytest.raises(TypeError) as excinfo:
        require_isin_values("sample_field", 123)

    message = str(excinfo.value)
    assert "sample_field" in message
    assert "123" in message
    assert "wrap single value" in message


def test_isin_guard_rejects_scalar_str() -> None:
    with pytest.raises(TypeError) as excinfo:
        require_isin_values("sample_field", "abc")

    message = str(excinfo.value)
    assert "sample_field" in message
    assert "'abc'" in message
    assert "wrap single value" in message


def test_eligibility_priority_score_rejects_scalar_manager_preference_index() -> None:
    policy = load_policy()
    pool = pd.DataFrame(index=pd.Index([1, 2, 3]))
    student = {
        "student_id": "S-1",
        "کدرشته": 1,
        "گروه آزمایشی": "تجربی",
        "جنسیت": 1,
        "دانش آموز فارغ": 0,
        "مرکز گلستان صدرا": 1,
        "مالی حکمت بنیاد": 0,
        "کد مدرسه": 1010,
    }
    resolver = JoinKeyResolver(policy)
    spec = EligibilitySpec(
        effective_join_keys=resolver.resolve_center(student),
        finance_keys=resolver.resolve_finance(student),
        school_code=resolver.resolve_school(student),
        student=student,
        policy=policy,
        manager_preference_index=cast(pd.Index, 123),
        manager_priority_enabled=True,
    )

    with pytest.raises(TypeError) as excinfo:
        spec.priority_score(pool)

    assert "manager_preference_index" in str(excinfo.value)


def test_channels_active_status_values_error_is_actionable() -> None:
    policy = load_policy()
    config = AllocationChannelConfig(
        school_codes=(1010,),
        center_channels={},
        registration_center_column=None,
        educational_status_column="student_educational_status",
        active_status_values=cast(tuple[int, ...], 123),
    )
    policy = replace(policy, allocation_channels=config)
    students_df = pd.DataFrame({"student_educational_status": [0, 1]})

    with pytest.raises(TypeError) as excinfo:
        _active_student_mask(students_df, policy)

    message = str(excinfo.value)
    assert "allocation_channels.active_status_values" in message
    assert "wrap single value" in message

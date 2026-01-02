from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest

from app.core.allocate_students import allocate_student
from app.core.common.join_resolver import JoinKeyResolver
from app.core.common.unknown_data_channel import (
    UnknownDataChannel,
    UnknownDataError,
    validate_join_key_columns_numeric,
    validate_pool_join_keys,
)
from app.core.policy_loader import load_policy


def test_unknown_manager_does_not_use_wildcard_by_default() -> None:
    policy = load_policy()
    center_management = replace(policy.center_management, unknown_manager_mode="issue")
    policy = replace(
        policy,
        center_map={"مدیر الف": 1, "*": 0},
        center_management=center_management,
    )
    channel = UnknownDataChannel(strict=False)
    resolver = JoinKeyResolver(policy, unknown_channel=channel)
    student = {
        policy.stage_column("center"): 0,
        "manager_name": "ناشناخته",
    }

    result = resolver.resolve_center(student)

    assert result.center_source == "raw"
    assert channel.issues
    assert channel.issues[0].code == "UNKNOWN_MANAGER_NAME"


def test_unknown_manager_wildcard_policy_records_issue() -> None:
    policy = load_policy()
    center_management = replace(policy.center_management, unknown_manager_mode="wildcard")
    policy = replace(
        policy,
        center_map={"مدیر الف": 1, "*": 0},
        center_management=center_management,
    )
    channel = UnknownDataChannel(strict=False)
    resolver = JoinKeyResolver(policy, unknown_channel=channel)
    student = {
        policy.stage_column("center"): 0,
        "manager_name": "ناشناخته",
    }

    result = resolver.resolve_center(student)

    assert result.center_source == "manager_wildcard"
    assert channel.issues
    assert channel.issues[0].code == "UNKNOWN_MANAGER_WILDCARD"


def test_allocate_student_reports_unknown_manager_once() -> None:
    policy = load_policy()
    center_management = replace(policy.center_management, unknown_manager_mode="issue")
    policy = replace(
        policy,
        center_map={"مدیر الف": 1, "*": 0},
        center_management=center_management,
    )
    pool = pd.DataFrame(
        {
            "پشتیبان": ["mentor"],
            "کد کارمندی پشتیبان": ["EMP-01"],
            "کدرشته": [27],
            "گروه آزمایشی": [27],
            "جنسیت": [1],
            "دانش آموز فارغ": [0],
            "مرکز گلستان صدرا": [0],
            "مالی حکمت بنیاد": [0],
            "کد مدرسه": [3581],
            "remaining_capacity": [1],
            "occupancy_ratio": [0.0],
            "allocations_new": [0],
        }
    )
    student = {
        "student_id": "STD-UNKNOWN",
        "کدرشته": 27,
        "گروه آزمایشی": 27,
        "جنسیت": 1,
        "دانش آموز فارغ": 0,
        "مرکز گلستان صدرا": 0,
        "مالی حکمت بنیاد": 0,
        "کد مدرسه": 3581,
        "manager_name": "ناشناخته",
    }
    channel = UnknownDataChannel(strict=False)

    allocate_student(student, pool, policy=policy, unknown_channel=channel)

    unknown_issues = [issue for issue in channel.issues if issue.code == "UNKNOWN_MANAGER_NAME"]
    assert unknown_issues
    assert len(unknown_issues) == 1


@pytest.mark.parametrize("strict", [True, False])
def test_pool_join_key_unknown_handling(strict: bool) -> None:
    policy = load_policy()
    channel = UnknownDataChannel(strict=strict)
    pool = pd.DataFrame({key: [1] for key in policy.join_keys})
    pool[policy.join_keys[0]] = ["نامعتبر"]

    if strict:
        with pytest.raises(UnknownDataError):
            validate_pool_join_keys(pool, policy=policy, channel=channel)
    else:
        validate_pool_join_keys(pool, policy=policy, channel=channel)
        assert channel.issues
        assert channel.issues[0].code == "UNKNOWN_JOIN_KEY_VALUE"


def test_pool_join_key_duplicate_columns_are_handled() -> None:
    policy = load_policy()
    channel = UnknownDataChannel(strict=False)
    key = policy.join_keys[0]
    pool = pd.DataFrame([[1, "نامعتبر"]], columns=[key, key])

    validate_pool_join_keys(pool, policy=policy, channel=channel)

    assert channel.issues
    assert any(issue.code == "MISSING_JOIN_KEY_COLUMN" for issue in channel.issues)


def test_join_key_columns_numeric_duplicate_columns_are_handled() -> None:
    policy = load_policy()
    channel = UnknownDataChannel(strict=False)
    key = policy.join_keys[0]
    frame = pd.DataFrame([[1, 2]], columns=[key, key])

    validate_join_key_columns_numeric(
        frame,
        join_keys=[key],
        entity_type="student",
        channel=channel,
    )

    assert not channel.issues

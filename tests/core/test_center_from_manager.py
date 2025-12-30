from __future__ import annotations

from dataclasses import replace

import pytest

from app.core.common.domain import BuildConfig, center_from_manager
from app.core.common.errors import InvalidCenterMappingError
from app.core.policy_loader import load_policy


def test_center_from_manager_exact_match() -> None:
    cfg = BuildConfig(center_map={"مدیر الف": 1, "*": 0})

    assert center_from_manager("مدیر الف", cfg=cfg) == 1


def test_center_from_manager_longest_match_wins() -> None:
    cfg = BuildConfig(
        center_map={
            "مدیر الف": 1,
            "مدیر الف ب": 2,
            "مدیر ب": 3,
            "*": 0,
        }
    )

    assert center_from_manager("مدیر الف ب - ناحیه", cfg=cfg) == 2


def test_center_from_manager_tie_breaks_lexicographically() -> None:
    cfg = BuildConfig(center_map={"مدیر آ": 10, "مدیر ب": 20, "*": 0})

    assert center_from_manager("سلام مدیر آ و مدیر ب", cfg=cfg) == 10


def test_center_from_manager_falls_back_to_wildcard() -> None:
    policy = load_policy()
    center_management = replace(policy.center_management, unknown_manager_mode="wildcard")
    cfg = BuildConfig(
        center_map={"*": 99},
        policy=replace(policy, center_management=center_management),
    )

    assert center_from_manager("نام ناشناخته", cfg=cfg) == 99


def test_center_from_manager_unknown_requires_policy() -> None:
    policy = load_policy()
    center_management = replace(policy.center_management, unknown_manager_mode="issue")
    cfg = BuildConfig(
        center_map={"*": 99},
        policy=replace(policy, center_management=center_management),
    )

    with pytest.raises(InvalidCenterMappingError):
        center_from_manager("نام ناشناخته", cfg=cfg)

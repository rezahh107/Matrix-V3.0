from __future__ import annotations

from dataclasses import replace

from app.core.common.join_resolver import JoinKeyResolver
from app.core.policy_loader import load_policy


def test_join_key_resolver_center_exact_match() -> None:
    policy = replace(load_policy(), center_map={"مدیر الف": 5, "*": 0})
    resolver = JoinKeyResolver(policy)

    effective = resolver.resolve_center(
        {policy.stage_column("center"): 0, "مدیر": "مدیر الف"}
    )

    assert effective.center_code == 5
    assert effective.center_source == "manager_exact"


def test_join_key_resolver_center_substring_match() -> None:
    policy = replace(load_policy(), center_map={"مدیر": 4, "*": 0})
    resolver = JoinKeyResolver(policy)

    effective = resolver.resolve_center(
        {policy.stage_column("center"): 0, "مدیر": "مدیر ارشد"}
    )

    assert effective.center_code == 4
    assert effective.center_source == "manager_substring"


def test_join_key_resolver_center_wildcard_match() -> None:
    base_policy = load_policy()
    center_management = replace(base_policy.center_management, unknown_manager_mode="wildcard")
    policy = replace(base_policy, center_map={"*": 9}, center_management=center_management)
    resolver = JoinKeyResolver(policy)

    effective = resolver.resolve_center(
        {policy.stage_column("center"): 0, "مدیر": "نامشخص"}
    )

    assert effective.center_code == 9
    assert effective.center_source == "manager_wildcard"


def test_join_key_resolver_center_no_match_returns_raw_zero() -> None:
    policy = replace(load_policy(), center_map={"مدیر الف": 3})
    resolver = JoinKeyResolver(policy)

    effective = resolver.resolve_center(
        {policy.stage_column("center"): 0, "مدیر": "نامشخص"}
    )

    assert effective.center_code == 0
    assert effective.center_source == "raw"


def test_join_key_resolver_center_ambiguous_longest_match_deterministic() -> None:
    policy = replace(load_policy(), center_map={"مدیر آ": 10, "مدیر ب": 11, "*": 0})
    resolver = JoinKeyResolver(policy)

    effective = resolver.resolve_center(
        {policy.stage_column("center"): 0, "مدیر": "سلام مدیر آ و مدیر ب"}
    )

    assert effective.center_code == 10
    assert effective.center_source == "manager_substring"


def test_join_key_resolver_finance_variants_from_join_map() -> None:
    policy = replace(load_policy(), finance_variants=(1, 2))
    resolver = JoinKeyResolver(policy)
    column = policy.stage_column("finance")
    join_map = {column.replace(" ", "_"): 1}

    effective = resolver.resolve_finance({}, student_join_map=join_map)

    assert effective.finance_code == 1
    assert effective.finance_variants == frozenset({1, 2})
    assert effective.finance_source == "join_map"


def test_join_key_resolver_school_normalizes_candidate() -> None:
    policy = replace(load_policy(), school_code_empty_as_zero=True)
    resolver = JoinKeyResolver(policy)
    column = policy.stage_column("school")
    student = {column: "35-81"}

    effective = resolver.resolve_school(student)

    assert effective.value == 3581
    assert effective.missing is False
    assert effective.wildcard is False

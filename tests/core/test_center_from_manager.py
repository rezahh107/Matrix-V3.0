from __future__ import annotations

from app.core.common.domain import BuildConfig, center_from_manager


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
    cfg = BuildConfig(center_map={"*": 99})

    assert center_from_manager("نام ناشناخته", cfg=cfg) == 99

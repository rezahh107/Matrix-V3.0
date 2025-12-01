from __future__ import annotations

import pytest

from app.core.common.domain import (
    BuildConfig,
    MentorType,
    classify_mentor_type_from_school_count,
    mentor_alias_for_type,
)


@pytest.mark.parametrize(
    "school_count, expected",
    [
        (None, MentorType.NORMAL),
        (0, MentorType.NORMAL),
        (1, MentorType.SCHOOL),
        (5, MentorType.SCHOOL),
    ],
)
def test_classify_mentor_type_from_school_count(
    school_count: int | None, expected: MentorType
) -> None:
    assert classify_mentor_type_from_school_count(school_count) is expected


def test_compute_alias_normal_with_valid_postal() -> None:
    cfg = BuildConfig()
    alias = mentor_alias_for_type(MentorType.NORMAL, "5000", "EMP-1", cfg=cfg)
    assert alias == "5000"


def test_compute_alias_normal_with_invalid_postal_returns_empty() -> None:
    cfg = BuildConfig()
    alias = mentor_alias_for_type(MentorType.NORMAL, "invalid", "EMP-2", cfg=cfg)
    assert alias == ""


def test_compute_alias_school_ignores_postal() -> None:
    cfg = BuildConfig()
    alias = mentor_alias_for_type(MentorType.SCHOOL, "12345", "EMP-42", cfg=cfg)
    assert alias == "EMP-42"

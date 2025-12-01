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
        (0, MentorType.NORMAL),
        (None, MentorType.NORMAL),
        (2, MentorType.SCHOOL),
    ],
)
def test_classify_mentor_type_from_school_count(
    school_count: int | None, expected: MentorType
) -> None:
    assert classify_mentor_type_from_school_count(school_count) is expected


def test_compute_alias_normal_requires_postal() -> None:
    cfg = BuildConfig()
    alias = mentor_alias_for_type(MentorType.NORMAL, "1234", "EMP-1", cfg=cfg)
    assert alias == "1234"


def test_compute_alias_school_uses_mentor_id() -> None:
    cfg = BuildConfig()
    alias = mentor_alias_for_type(MentorType.SCHOOL, "", "EMP-42", cfg=cfg)
    assert alias == "EMP-42"


def test_alias_value_does_not_change_mentor_type() -> None:
    cfg = BuildConfig()
    alias = mentor_alias_for_type(MentorType.NORMAL, "999", "EMP-1", cfg=cfg)
    # Even if alias is unusable, type detection is independent
    assert alias == ""
    assert classify_mentor_type_from_school_count(0) is MentorType.NORMAL

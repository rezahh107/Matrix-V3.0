from app.core.common.domain import (
    BuildConfig,
    MentorType,
    classify_mentor_mode,
)


def test_classify_mentor_normal_with_only_postal() -> None:
    cfg = BuildConfig()
    result = classify_mentor_mode(
        postal_code="1234",
        school_codes=[],
        cfg=cfg,
        has_school_constraint=False,
        school_count=0,
    )
    assert result is MentorType.NORMAL


def test_classify_mentor_school_when_restricted_and_no_postal() -> None:
    cfg = BuildConfig()
    result = classify_mentor_mode(
        postal_code="",
        school_codes=["3001"],
        cfg=cfg,
        has_school_constraint=True,
        school_count=1,
    )
    assert result is MentorType.SCHOOL


def test_classify_mentor_dual_with_postal_and_school_reference() -> None:
    cfg = BuildConfig()
    result = classify_mentor_mode(
        postal_code="1234",
        school_codes=["3001"],
        cfg=cfg,
        has_school_constraint=True,
        school_count=1,
    )
    assert result is MentorType.DUAL


def test_alias_below_threshold_forces_school_type() -> None:
    cfg = BuildConfig()
    result = classify_mentor_mode(
        postal_code="1234",
        school_codes=[],
        cfg=cfg,
        has_school_constraint=False,
        school_count=0,
        aliases=("999",),
    )
    assert result is MentorType.SCHOOL

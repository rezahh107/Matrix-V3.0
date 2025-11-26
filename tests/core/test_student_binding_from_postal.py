from app.core.common.domain import (
    BuildConfig,
    StudentBindingKind,
    classify_student_binding_from_postal,
)


def test_student_binding_normal_for_valid_postal() -> None:
    cfg = BuildConfig()
    assert classify_student_binding_from_postal("1234", cfg=cfg) is StudentBindingKind.NORMAL


def test_student_binding_school_for_small_postal() -> None:
    cfg = BuildConfig()
    assert classify_student_binding_from_postal("550", cfg=cfg) is StudentBindingKind.SCHOOL


def test_student_binding_mentor_based_when_missing() -> None:
    cfg = BuildConfig()
    assert classify_student_binding_from_postal("", cfg=cfg) is StudentBindingKind.MENTOR_BASED


def test_student_binding_invalid_range_defaults_to_mentor_based() -> None:
    cfg = BuildConfig()
    assert classify_student_binding_from_postal("12000", cfg=cfg) is StudentBindingKind.MENTOR_BASED

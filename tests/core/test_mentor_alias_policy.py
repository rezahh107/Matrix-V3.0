from app.core.common.domain import (
    BuildConfig,
    MentorType,
    classify_mentor_type_from_school_count,
    mentor_alias_for_type,
)


def test_classify_mentor_type_relies_on_school_count_only() -> None:
    assert classify_mentor_type_from_school_count(0) is MentorType.NORMAL
    assert classify_mentor_type_from_school_count(None) is MentorType.NORMAL
    assert classify_mentor_type_from_school_count(2) is MentorType.SCHOOL


def test_mentor_alias_for_type_is_pure_function_of_type() -> None:
    cfg = BuildConfig(postal_valid_range=(1, 9999))

    normal_alias = mentor_alias_for_type(MentorType.NORMAL, "050", "mentor-1", cfg=cfg)
    school_alias = mentor_alias_for_type(MentorType.SCHOOL, "9999", "mentor-1", cfg=cfg)

    assert normal_alias == "50"
    assert school_alias == "mentor-1"

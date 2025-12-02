import pytest

from app.core.common.domain import (
    DUAL_STATUS_GROUPS,
    EDUCATIONAL_STRUCTURE,
    Status,
    get_academic_info,
    get_eligible_codes_for_status,
    validate_student_allocation,
)


def test_get_academic_info_dual_status():
    info = get_academic_info(1)
    assert info["level"] == "کنکوری"
    assert info["group"] == "دوازدهم ریاضی"
    assert info["allowed_status"] == {Status.STUDENT, Status.GRADUATE}
    assert info["is_dual_status"] is True


def test_get_academic_info_student_only():
    info = get_academic_info(24)
    assert info["level"] == "متوسطه دوم"
    assert info["group"] == "دهم ریاضی"
    assert info["allowed_status"] == {Status.STUDENT}
    assert info["is_dual_status"] is False


def test_validate_student_allocation_respects_status():
    assert validate_student_allocation(1, Status.GRADUATE) is True
    assert validate_student_allocation(1, Status.STUDENT) is True
    assert validate_student_allocation(24, Status.STUDENT) is True
    assert validate_student_allocation(24, Status.GRADUATE) is False


def test_get_eligible_codes_for_status():
    graduate_codes = get_eligible_codes_for_status(Status.GRADUATE)
    assert graduate_codes == sorted(DUAL_STATUS_GROUPS)

    student_codes = get_eligible_codes_for_status(Status.STUDENT)
    assert len(student_codes) == len(EDUCATIONAL_STRUCTURE)
    assert set(student_codes).issuperset(graduate_codes)


def test_invalid_student_status_rejected():
    with pytest.raises(ValueError):
        get_eligible_codes_for_status(2)
    with pytest.raises(ValueError):
        validate_student_allocation(1, -1)

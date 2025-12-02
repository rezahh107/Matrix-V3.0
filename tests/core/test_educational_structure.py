import pytest

from app.core.common.domain import (
    DUAL_STATUS_GROUPS,
    EDUCATIONAL_STRUCTURE,
    get_code_from_group,
    get_info_from_code,
    is_dual_status_code,
)
from app.core.common.errors import DataMissingError


def test_get_info_from_code_distinguishes_art_and_grade_seven() -> None:
    art_level, art_group, art_code = get_info_from_code(7)
    grade_level, grade_group, grade_code = get_info_from_code(33)

    assert art_code == 7
    assert grade_code == 33
    assert art_group == "هنر"
    assert grade_group == "هفتم"
    assert art_level != grade_level


def test_get_code_from_group_resolves_with_and_without_level() -> None:
    assert get_code_from_group("هفتم", educational_level="متوسطه اول") == 33
    assert get_code_from_group("هنر", educational_level="کنکوری") == 7
    assert get_code_from_group("هفتم") == 33


@pytest.mark.parametrize("invalid_group", ["نامعتبر", "grade-seven"])
def test_get_code_from_group_invalid_raises(invalid_group: str) -> None:
    with pytest.raises(DataMissingError):
        get_code_from_group(invalid_group)


def test_is_dual_status_code_only_for_policy_set() -> None:
    assert is_dual_status_code(7)
    assert not is_dual_status_code(33)
    assert DUAL_STATUS_GROUPS.issuperset({1, 3, 5, 7, 8, 9, 11, 12, 14, 17, 18})


def test_educational_structure_complete_mapping() -> None:
    codes = {record.field_code for record in EDUCATIONAL_STRUCTURE}
    assert len(EDUCATIONAL_STRUCTURE) == len(codes)
    assert 41 in codes
    assert 5 in codes

import pytest

from app.core.common.domain import Gender, norm_gender
from app.core.common.errors import InvalidGenderValueError
from app.core.policy_loader import load_policy


def test_gender_contract_matches_loaded_policy() -> None:
    policy = load_policy()

    assert Gender.MALE.value == policy.gender_codes.male.value == 1
    assert Gender.FEMALE.value == policy.gender_codes.female.value == 0


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("male", Gender.MALE),
        ("female", Gender.FEMALE),
        ("پسر", Gender.MALE),
        ("دختر", Gender.FEMALE),
        ("1", Gender.MALE),
        ("0", Gender.FEMALE),
        (1, Gender.MALE),
        (0, Gender.FEMALE),
        (1.0, Gender.MALE),
        (0.0, Gender.FEMALE),
        ("۱", Gender.MALE),
        ("۰", Gender.FEMALE),
    ],
)
def test_norm_gender_accepts_canonical_representations(value: object, expected: Gender) -> None:
    assert norm_gender(value, strict=True) == expected


@pytest.mark.parametrize("value", [None, "", "??", False, 2, "2", 2.0])
def test_norm_gender_non_strict_invalid_values_default_to_male(value: object) -> None:
    assert norm_gender(value, strict=False) == Gender.MALE


@pytest.mark.parametrize("value", [None, "", "??", False, 2, "2", 2.0])
def test_norm_gender_strict_rejects_invalid_values(value: object) -> None:
    with pytest.raises(InvalidGenderValueError) as exc:
        norm_gender(value, strict=True)

    assert exc.value.column == "جنسیت"

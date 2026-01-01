from app.core.common.domain import get_code_from_group


def test_get_code_from_group_normalizes_inputs() -> None:
    assert get_code_from_group("هفتم ", educational_level="متوسطه‌اول") == 33
    assert get_code_from_group("دوازدهم  ریاضی") == 1

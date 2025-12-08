from app.core.build_matrix import normalize_capacity_values


def test_normalize_capacity_values_uses_capacity_special_as_ceiling() -> None:
    covered, special_limit, remaining = normalize_capacity_values(5, 12)

    assert covered == 5
    assert special_limit == 12
    assert remaining == 7


def test_normalize_capacity_values_does_not_promote_current_to_ceiling() -> None:
    covered, special_limit, remaining = normalize_capacity_values(15, 10)

    assert covered == 15
    assert special_limit == 10
    assert remaining == 0

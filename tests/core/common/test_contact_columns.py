from __future__ import annotations

from app.core.common.contact_columns import LANDLINE_COLUMN_NAMES, MOBILE_COLUMN_NAMES


def test_mobile_and_landline_registries_are_disjoint() -> None:
    assert MOBILE_COLUMN_NAMES.isdisjoint(LANDLINE_COLUMN_NAMES)


def test_landline_headers_not_misclassified_as_mobile() -> None:
    assert "تلفن منزل" not in MOBILE_COLUMN_NAMES
    assert "student_landline" not in MOBILE_COLUMN_NAMES

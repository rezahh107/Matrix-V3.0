from __future__ import annotations

from app.core.common.domain import StudentBindingKind
from app.core.matrix.validation import student_binding_for_row


def test_student_binding_delegates_to_core_helper() -> None:
    binding = student_binding_for_row({"کدپستی": "0099"})
    assert binding is StudentBindingKind.SCHOOL


def test_student_binding_default_to_normal_postal() -> None:
    binding = student_binding_for_row({"کدپستی": "1234567890"})
    assert binding is StudentBindingKind.MENTOR_BASED

from __future__ import annotations

from collections.abc import Mapping

from app.core.common.domain import (
    BuildConfig,
    StudentBindingKind,
    classify_student_binding_from_postal,
)
from app.core.qa.coverage_validation import build_coverage_validation_fields

__all__ = ["build_coverage_validation_fields", "student_binding_for_row"]


def student_binding_for_row(
    row: Mapping[str, object], *, cfg: BuildConfig = BuildConfig()
) -> StudentBindingKind:
    """Determine student binding mode using Core helper.

    The binding is derived solely from Core's postal-code classification so Infra
    avoids re-implementing SSoT rules.
    """

    postal = row.get("کدپستی", "")
    return classify_student_binding_from_postal(postal, cfg=cfg)

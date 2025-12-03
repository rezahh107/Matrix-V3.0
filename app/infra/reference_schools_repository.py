"""سازگاری عقب‌رو برای ماژول مرجع مدارس با اعتبارسنجی کلید join."""

from __future__ import annotations

from pathlib import Path

from app.core.common.join_keys import validate_and_canonicalize_join_keys
from app.core.common.types import JoinKeyValidationResult
from app.core.policy_loader import PolicyConfig
from app.infra.local_database import LocalDatabase
from app.infra.references.schools import (
    get_school_reference_frames,
    import_school_crosswalk_from_excel,
    import_school_report_from_excel,
)

__all__ = [
    "import_school_report_from_excel",
    "import_school_report_with_validation",
    "import_school_crosswalk_from_excel",
    "get_school_reference_frames",
]


def import_school_report_with_validation(
    path: Path, *, db: LocalDatabase, policy: PolicyConfig
) -> JoinKeyValidationResult:
    """Import school report with join-key validation and persistence."""

    raw_df = import_school_report_from_excel(path, db=db)
    validation = validate_and_canonicalize_join_keys(raw_df, policy=policy, entity_type="school")
    return validation

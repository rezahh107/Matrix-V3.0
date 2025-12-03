from __future__ import annotations

from pathlib import Path

from app.core.common.types import JoinKeyValidationResult
from app.core.policy_loader import PolicyConfig
from app.infra.local_database import LocalDatabase
from app.infra.reference_students_repository import import_student_report_with_validation

__all__ = ["import_students_with_validation"]


def import_students_with_validation(
    path: Path, *, db: LocalDatabase, policy: PolicyConfig
) -> JoinKeyValidationResult:
    """Excel import entry point exposing join-key validation results."""

    return import_student_report_with_validation(path, db=db, policy=policy)

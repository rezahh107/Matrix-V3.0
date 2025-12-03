from __future__ import annotations

from pathlib import Path

from app.core.common.types import JoinKeyValidationResult
from app.core.policy_loader import PolicyConfig
from app.infra.local_database import LocalDatabase
from app.infra.reference_schools_repository import import_school_report_with_validation

__all__ = ["import_schools_with_validation"]


def import_schools_with_validation(
    path: Path, *, db: LocalDatabase, policy: PolicyConfig
) -> JoinKeyValidationResult:
    """Excel import entry point for school references with validation."""

    return import_school_report_with_validation(path, db=db, policy=policy)

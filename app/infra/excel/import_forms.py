from __future__ import annotations

from pathlib import Path

from app.core.common.types import JoinKeyValidationResult
from app.core.policy_loader import PolicyConfig
from app.infra.local_database import LocalDatabase
from app.infra.reference_forms_repository import (
    import_forms_with_validation as _import_forms_with_validation,
)

__all__ = ["import_forms_with_validation"]


def import_forms_with_validation(
    path: Path, *, db: LocalDatabase, policy: PolicyConfig
) -> JoinKeyValidationResult:
    """Excel import entry point for forms with join-key validation."""

    return _import_forms_with_validation(path, db=db, policy=policy)

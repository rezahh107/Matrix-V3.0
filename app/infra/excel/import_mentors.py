from __future__ import annotations

from pathlib import Path

from app.core.common.types import JoinKeyValidationResult
from app.core.policy_loader import PolicyConfig
from app.infra.local_database import LocalDatabase
from app.infra.reference_mentors_repository import import_mentor_pool_with_validation

__all__ = ["import_mentors_with_validation"]


def import_mentors_with_validation(
    path: Path,
    *,
    db: LocalDatabase,
    policy: PolicyConfig,
    pool_source: str = "inspactor",
) -> JoinKeyValidationResult:
    """Excel import entry point exposing join-key validation results for mentors."""

    return import_mentor_pool_with_validation(path, db=db, policy=policy, pool_source=pool_source)

"""Compatibility wrapper to expose join-key validation for forms entries."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.common.join_keys import validate_and_canonicalize_join_keys
from app.core.common.types import JoinKeyValidationResult
from app.core.policy_loader import PolicyConfig
from app.infra.forms_repository import FormsRepository
from app.infra.io_utils import read_excel_first_sheet
from app.infra.local_database import LocalDatabase

__all__ = ["import_forms_with_validation", "load_forms_with_validation"]


def import_forms_with_validation(
    path: Path, *, db: LocalDatabase, policy: PolicyConfig
) -> JoinKeyValidationResult:
    """Import form entries from Excel/CSV and validate join keys."""

    df = read_excel_first_sheet(path)
    validation = validate_and_canonicalize_join_keys(df, policy=policy, entity_type="form")
    db.upsert_forms_entries(validation.canonical_df, source=str(path))
    return validation


def load_forms_with_validation(
    *, db: LocalDatabase, policy: PolicyConfig
) -> JoinKeyValidationResult:
    """Load cached forms entries and re-validate join keys."""

    repo = FormsRepository(client=None, db=db)
    cached: pd.DataFrame = repo.load_entries()
    validation = validate_and_canonicalize_join_keys(
        cached, policy=policy, entity_type="form"
    )
    return validation

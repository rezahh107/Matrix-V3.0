"""Compatibility wrapper to expose join-key validation for forms entries."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.common.columns import HEADER_ALIASES_V3
from app.core.common.join_keys import validate_and_canonicalize_join_keys
from app.core.common.types import JoinKeyValidationResult
from app.core.policy_loader import PolicyConfig
from app.infra.common.header_pipeline_v3 import HeaderPipelineV3
from app.infra.forms_repository import FormsRepository
from app.infra.io_utils import read_excel_first_sheet
from app.infra.local_database import LocalDatabase

__all__ = ["import_forms_with_validation", "load_forms_with_validation"]


def _build_forms_header_pipeline(policy: PolicyConfig) -> HeaderPipelineV3:
    return HeaderPipelineV3(
        alias_registry=HEADER_ALIASES_V3,
        required={"report": list(policy.join_keys)},
        critical_required={"report": set(policy.join_keys)},
    )


def import_forms_with_validation(
    path: Path, *, db: LocalDatabase, policy: PolicyConfig
) -> JoinKeyValidationResult:
    """Import form entries from Excel/CSV and validate join keys."""

    df = read_excel_first_sheet(path)
    resolution = _build_forms_header_pipeline(policy).resolve(df, source="report")
    normalized = resolution.resolved_df
    if "entry_id" not in normalized.columns or "received_at" not in normalized.columns:
        normalized = normalized.copy()
        if "entry_id" not in normalized.columns:
            normalized["entry_id"] = (normalized.index + 1).map(str)
        if "received_at" not in normalized.columns:
            normalized["received_at"] = pd.NaT
    validation = validate_and_canonicalize_join_keys(
        normalized, policy=policy, entity_type="form"
    )
    db.upsert_forms_entries(validation.canonical_df, source=str(path))
    return validation


def load_forms_with_validation(
    *, db: LocalDatabase, policy: PolicyConfig
) -> JoinKeyValidationResult:
    """Load cached forms entries and re-validate join keys."""

    repo = FormsRepository(client=None, db=db)
    cached: pd.DataFrame = repo.load_entries()
    normalized = _build_forms_header_pipeline(policy).resolve(cached, source="report").resolved_df
    validation = validate_and_canonicalize_join_keys(
        normalized, policy=policy, entity_type="form"
    )
    return validation

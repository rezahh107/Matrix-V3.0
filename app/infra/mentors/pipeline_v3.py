from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.common.types import HeaderMode
from app.core.policy_loader import PolicyConfig
from app.infra.io_utils import read_inspactor_workbook
from app.infra.local_database import LocalDatabase, _coerce_int_columns
from app.infra.reference_mentors_repository import _POOL_JOIN_KEY_QA_ATTR, _derive_pool_join_keys

from .field_registry import FieldRegistry
from .header_resolver import HeaderResolver
from .join_key_resolver import JoinKeyResolutionResult, JoinKeyResolver
from .mentor_pool_builder import MentorPoolBuilder, MentorPoolBuildResult
from .value_canonicalizer import ValueCanonicalizationResult, ValueCanonicalizer


@dataclass(frozen=True)
class MentorPipelineResult:
    build_result: MentorPoolBuildResult
    header_result: Any
    value_result: ValueCanonicalizationResult
    join_key_result: JoinKeyResolutionResult

    @property
    def can_continue(self) -> bool:
        return (
            self.header_result.can_continue
            and self.value_result.can_continue
            and self.join_key_result.can_continue
            and self.build_result.can_continue
        )


class MentorPipelineV3:
    """Unified mentor import pipeline (FieldRegistry → Header → Values → JoinKey → Pool)."""

    def __init__(
        self,
        *,
        policy: PolicyConfig,
        pool_source: str = "inspactor",
        header_mode: HeaderMode = "fa",
        db: LocalDatabase | None = None,
    ) -> None:
        self._policy = policy
        self._pool_source = pool_source
        self._registry = FieldRegistry(policy)
        self._header_resolver = HeaderResolver(self._registry, header_mode=header_mode)
        self._canonicalizer = ValueCanonicalizer(self._registry)
        self._join_key_resolver = JoinKeyResolver(policy)
        self._builder = MentorPoolBuilder(policy, pool_source=pool_source)
        self._db = db

    def run_from_excel(self, path: Path) -> MentorPipelineResult:
        raw_df = read_inspactor_workbook(path)
        return self.run(raw_df)

    def run(self, df: pd.DataFrame) -> MentorPipelineResult:
        header_result = self._header_resolver.resolve(df)
        working = header_result.resolved_df
        value_result = self._canonicalizer.canonicalize(working)
        canonical_df = value_result.canonical_df
        if not self._registry.has_required_fields(canonical_df.columns) and self._db is not None:
            derived_df, derive_issues = _derive_pool_join_keys(
                working, db=self._db, policy=self._policy
            )
            derived_df.attrs[_POOL_JOIN_KEY_QA_ATTR] = derive_issues
            value_result = ValueCanonicalizationResult(
                canonical_df=derived_df, issues=derive_issues
            )
            canonical_df = derived_df
        attr_issues = canonical_df.attrs.get(_POOL_JOIN_KEY_QA_ATTR, [])
        if attr_issues and not value_result.issues:
            value_result = ValueCanonicalizationResult(
                canonical_df=canonical_df, issues=attr_issues
            )
        join_key_result = self._join_key_resolver.resolve(value_result)
        build_result = self._builder.build(join_key_result)
        return MentorPipelineResult(
            build_result=build_result,
            header_result=header_result,
            value_result=value_result,
            join_key_result=join_key_result,
        )


def canonicalize_join_keys_for_cache(payload: pd.DataFrame, policy: PolicyConfig) -> pd.DataFrame:
    registry = FieldRegistry(policy)
    canonicalizer = ValueCanonicalizer(registry)
    value_result = canonicalizer.canonicalize(payload)
    if not value_result.can_continue:
        return payload
    return _coerce_int_columns(value_result.canonical_df, registry.join_fields)

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from app.core.canonical_frames import POOL_JOIN_KEY_DUPLICATES_ATTR, canonicalize_pool_frame
from app.core.policy_loader import PolicyConfig
from app.infra.reference_mentors_repository import _POOL_JOIN_KEY_QA_ATTR, _POOL_QA_PAYLOAD_ATTR

from .join_key_resolver import JoinKeyResolutionResult


@dataclass(frozen=True)
class MentorPoolBuildResult:
    pool: pd.DataFrame
    qa_issues: list[dict[str, Any]]
    join_key_duplicates: pd.DataFrame
    usable_profiles: pd.DataFrame
    all_profiles: pd.DataFrame
    qa_payload: dict[str, Any]

    @property
    def can_continue(self) -> bool:
        return not self.qa_issues


class MentorPoolBuilder:
    """Build canonical mentor pool dataframes from resolved join profiles."""

    def __init__(self, policy: PolicyConfig, *, pool_source: str = "inspactor") -> None:
        self._policy = policy
        self._pool_source = pool_source

    def build(self, resolved: JoinKeyResolutionResult) -> MentorPoolBuildResult:
        canonical = canonicalize_pool_frame(
            resolved.canonical_df,
            policy=self._policy,
            sanitize_pool=False,
            pool_source=self._pool_source,
        )
        canonical.attrs[POOL_JOIN_KEY_DUPLICATES_ATTR] = resolved.duplicates
        qa_attr = resolved.canonical_df.attrs.get(_POOL_JOIN_KEY_QA_ATTR, [])
        qa_issues = [*qa_attr, *resolved.issues]
        canonical.attrs[_POOL_JOIN_KEY_QA_ATTR] = qa_attr
        qa_payload = {
            "issues": qa_issues,
            "duplicates": resolved.duplicates.to_dict("records"),
            "multi_profile_mentors": sorted(
                set(resolved.all_profiles.get("mentor_id", []))
                - set(resolved.usable_profiles.get("mentor_id", []))
            ),
            "usable_profiles": resolved.usable_profiles.to_dict("records"),
            "all_profiles": resolved.all_profiles.to_dict("records"),
        }
        canonical.attrs[_POOL_QA_PAYLOAD_ATTR] = qa_payload
        return MentorPoolBuildResult(
            pool=canonical,
            qa_issues=qa_issues,
            join_key_duplicates=resolved.duplicates,
            usable_profiles=resolved.usable_profiles,
            all_profiles=resolved.all_profiles,
            qa_payload=qa_payload,
        )

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from app.core.common.join_keys import validate_and_canonicalize_join_keys
from app.core.policy_loader import PolicyConfig
from app.infra.reference_mentors_repository import _POOL_JOIN_KEY_QA_ATTR

from .value_canonicalizer import ValueCanonicalizationResult


@dataclass(frozen=True)
class JoinKeyResolutionResult:
    canonical_df: pd.DataFrame
    issues: list[dict[str, Any]]
    duplicates: pd.DataFrame
    usable_profiles: pd.DataFrame
    all_profiles: pd.DataFrame

    @property
    def can_continue(self) -> bool:
        return not self.issues


class JoinKeyResolver:
    """Validate mentor join profiles and flag multi-profile mentors."""

    def __init__(self, policy: PolicyConfig) -> None:
        self._policy = policy

    def resolve(self, values: ValueCanonicalizationResult) -> JoinKeyResolutionResult:
        validation = validate_and_canonicalize_join_keys(
            values.canonical_df, policy=self._policy, entity_type="mentor"
        )
        issues = list(values.issues)
        attr_issues = values.canonical_df.attrs.get(_POOL_JOIN_KEY_QA_ATTR, [])
        issues.extend(attr_issues)
        issues.extend(validation.issues)
        canonical = validation.canonical_df
        if attr_issues:
            canonical.attrs[_POOL_JOIN_KEY_QA_ATTR] = attr_issues
        all_profiles = canonical.copy()
        duplicates = self._detect_duplicate_profiles(all_profiles)
        multi_profile = self._find_multi_profile_mentors(all_profiles)
        if not duplicates.empty:
            issues.append({"reason": "DUPLICATE_JOIN_PROFILE", "rows": len(duplicates)})
        if multi_profile:
            issues.append(
                {
                    "reason": "MULTIPLE_JOIN_PROFILES_PER_MENTOR",
                    "mentors": sorted(multi_profile),
                }
            )
        usable_profiles = all_profiles.loc[~all_profiles["mentor_id"].isin(multi_profile)].copy()
        return JoinKeyResolutionResult(
            canonical_df=canonical,
            issues=issues,
            duplicates=duplicates,
            usable_profiles=usable_profiles,
            all_profiles=all_profiles,
        )

    def _find_multi_profile_mentors(self, canonical: pd.DataFrame) -> set[str]:
        if "mentor_id" not in canonical.columns:
            return set()
        deduped = canonical.drop_duplicates(subset=["mentor_id", *self._policy.join_keys])
        profile_counts = deduped.groupby("mentor_id", sort=False)[self._policy.join_keys].size()
        return {str(mentor) for mentor, count in profile_counts.items() if count > 1}

    def _detect_duplicate_profiles(self, canonical: pd.DataFrame) -> pd.DataFrame:
        key_columns = ["mentor_id", *self._policy.join_keys]
        if not all(col in canonical.columns for col in key_columns):
            return pd.DataFrame(columns=[*self._policy.join_keys, "mentor_id", "duplicate_group_size"])
        trimmed = canonical.loc[:, key_columns].copy()
        trimmed["mentor_id"] = trimmed["mentor_id"].astype("string").str.strip()
        numeric_cols = [col for col in self._policy.join_keys if col in trimmed.columns]
        for column in numeric_cols:
            trimmed[column] = pd.to_numeric(trimmed[column], errors="coerce").astype("Int64")
        non_null = ~trimmed[key_columns].isna().any(axis=1)
        duplicated_mask = trimmed.loc[non_null].duplicated(subset=key_columns, keep=False)
        if not bool(duplicated_mask.any()):
            return pd.DataFrame(columns=[*self._policy.join_keys, "mentor_id", "duplicate_group_size"])
        duplicate_rows = trimmed.loc[non_null & duplicated_mask, key_columns].copy()
        duplicate_rows["duplicate_group_size"] = (
            duplicate_rows.groupby(key_columns, sort=False)["mentor_id"].transform("size").astype("Int64")
        )
        duplicate_rows["pool_row_index"] = pd.to_numeric(duplicate_rows.index, errors="coerce").astype("Int64")
        return duplicate_rows.sort_values(key_columns + ["pool_row_index"], kind="stable").reset_index(drop=True)

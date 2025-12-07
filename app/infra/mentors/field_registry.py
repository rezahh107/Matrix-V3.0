from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.core.policy_loader import PolicyConfig


@dataclass(frozen=True)
class FieldRegistry:
    """Registry for mentor join and metadata fields used by the v3 pipeline."""

    policy: PolicyConfig

    @property
    def join_fields(self) -> list[str]:
        return list(self.policy.join_keys)

    @property
    def required_fields(self) -> list[str]:
        return ["mentor_id", *self.policy.join_keys]

    def has_required_fields(self, columns: Iterable[str]) -> bool:
        column_set = {col for col in columns}
        return all(field in column_set for field in self.required_fields)

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.core.common.types import JoinKeyEntityType, JoinKeyValidationResult


@dataclass(frozen=True)
class RunJoinKeySummary:
    run_label: str
    entity_counts: dict[JoinKeyEntityType, int]

    @property
    def total_issues(self) -> int:
        return sum(self.entity_counts.values())


class QADashboardVM:
    """View-model aggregating join-key validation issues per run."""

    def __init__(self, summaries: Iterable[RunJoinKeySummary] | None = None) -> None:
        self._summaries: list[RunJoinKeySummary] = list(summaries or [])

    @property
    def summaries(self) -> list[RunJoinKeySummary]:
        return list(self._summaries)

    def register_run(
        self, run_label: str, results: dict[JoinKeyEntityType, JoinKeyValidationResult]
    ) -> None:
        counts: dict[JoinKeyEntityType, int] = {}
        for entity_type, result in results.items():
            counts[entity_type] = len(result.issues)
        self._summaries.append(RunJoinKeySummary(run_label=run_label, entity_counts=counts))

    def issue_count(self, run_index: int, entity: JoinKeyEntityType) -> int:
        summary = self._summaries[run_index]
        return summary.entity_counts.get(entity, 0)

    def has_issues(self, run_index: int) -> bool:
        summary = self._summaries[run_index]
        return summary.total_issues > 0

    def fix_target(self, run_index: int, entity: JoinKeyEntityType) -> tuple[str, JoinKeyEntityType]:
        summary = self._summaries[run_index]
        return summary.run_label, entity

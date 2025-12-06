from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.core.common.types import (
    JoinKeyEntityType,
    JoinKeyValidationResult,
    StudentDomainValidationResult,
)


@dataclass(frozen=True)
class RunJoinKeySummary:
    run_label: str
    entity_counts: dict[JoinKeyEntityType, int]
    qa_failed_rules: int = 0
    trace_rows: int | None = None

    @property
    def total_issues(self) -> int:
        return sum(self.entity_counts.values())


class QADashboardVM:
    """View-model aggregating join-key validation issues per run."""

    def __init__(self, summaries: Iterable[RunJoinKeySummary] | None = None) -> None:
        self._summaries: list[RunJoinKeySummary] = list(summaries or [])
        self._student_domain_counts: list[int] = [0 for _ in self._summaries]

    @property
    def summaries(self) -> list[RunJoinKeySummary]:
        return list(self._summaries)

    @property
    def student_domain_counts(self) -> list[int]:
        return list(self._student_domain_counts)

    def register_run(
        self,
        run_label: str,
        results: dict[JoinKeyEntityType, JoinKeyValidationResult],
        student_domain: StudentDomainValidationResult | None = None,
        qa_failed_rules: int | None = None,
        trace_rows: int | None = None,
    ) -> None:
        counts: dict[JoinKeyEntityType, int] = {}
        for entity_type, result in results.items():
            counts[entity_type] = len(result.issues)
        self._summaries.append(
            RunJoinKeySummary(
                run_label=run_label,
                entity_counts=counts,
                qa_failed_rules=qa_failed_rules or 0,
                trace_rows=trace_rows,
            )
        )
        if student_domain is not None:
            self._student_domain_counts.append(len(student_domain.issues))
        else:
            self._student_domain_counts.append(0)

    def issue_count(self, run_index: int, entity: JoinKeyEntityType) -> int:
        summary = self._summaries[run_index]
        return summary.entity_counts.get(entity, 0)

    def has_issues(self, run_index: int) -> bool:
        summary = self._summaries[run_index]
        return summary.total_issues > 0 or self._student_domain_counts[run_index] > 0

    def fix_target(
        self, run_index: int, entity: JoinKeyEntityType
    ) -> tuple[str, JoinKeyEntityType]:
        summary = self._summaries[run_index]
        return summary.run_label, entity

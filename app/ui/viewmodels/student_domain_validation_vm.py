from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.core.common.types import StudentDomainValidationResult


@dataclass(frozen=True)
class StudentDomainIssueVM:
    row_index: int
    group_code: int | None
    graduation_status: int | None
    allowed_statuses: tuple[int, ...]
    error_code: str


class StudentDomainValidationVM:
    """View-model for presenting student domain validation issues."""

    def __init__(self, issues: Iterable[StudentDomainIssueVM] | None = None) -> None:
        self._issues = list(issues or [])

    @property
    def issues(self) -> list[StudentDomainIssueVM]:
        return list(self._issues)

    @property
    def total_issues(self) -> int:
        return len(self._issues)

    @classmethod
    def from_result(cls, result: StudentDomainValidationResult) -> StudentDomainValidationVM:
        items = [
            StudentDomainIssueVM(
                row_index=issue.row_index,
                group_code=issue.group_code,
                graduation_status=issue.graduation_status,
                allowed_statuses=issue.allowed_statuses,
                error_code=issue.error_code,
            )
            for issue in result.issues
        ]
        return cls(items)

    def issue_counts_by_error(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for issue in self._issues:
            counts[issue.error_code] = counts.get(issue.error_code, 0) + 1
        return counts

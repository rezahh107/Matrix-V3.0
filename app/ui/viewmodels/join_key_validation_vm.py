from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.core.common.types import JoinKeyValidationIssue, JoinKeyValidationResult


@dataclass
class JoinKeyIssueVM:
    entity_type: Literal["student", "mentor"]
    row_index: int
    column: str
    raw_value: object
    error_code: str


@dataclass
class JoinKeyValidationVM:
    issues: list[JoinKeyIssueVM]

    @classmethod
    def from_core_result(cls, result: JoinKeyValidationResult) -> JoinKeyValidationVM:
        return cls(
            issues=[
                JoinKeyIssueVM(
                    entity_type=issue.entity_type,
                    row_index=issue.row_index,
                    column=issue.column,
                    raw_value=issue.raw_value,
                    error_code=issue.error_code,
                )
                for issue in result.issues
            ]
        )

    def to_core_issues(self) -> list[JoinKeyValidationIssue]:
        return [
            JoinKeyValidationIssue(
                entity_type=issue.entity_type,
                row_index=issue.row_index,
                column=issue.column,
                raw_value=issue.raw_value,
                error_code=issue.error_code,
            )
            for issue in self.issues
        ]

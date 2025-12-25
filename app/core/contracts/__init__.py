"""قراردادهای ورودی و خطاهای مرتبط."""

from __future__ import annotations

from app.core.contracts.contract_errors import InputContractError, InputContractIssue
from app.core.contracts.specs import (
    CrosswalkGroupsSpec,
    CrosswalkSynonymsSpec,
    InputContractSpec,
    InspactorSpec,
    PoolSpec,
    SchoolsSpec,
    StudentReportSpec,
)

__all__ = [
    "InputContractError",
    "InputContractIssue",
    "InputContractSpec",
    "StudentReportSpec",
    "PoolSpec",
    "InspactorSpec",
    "SchoolsSpec",
    "CrosswalkGroupsSpec",
    "CrosswalkSynonymsSpec",
]


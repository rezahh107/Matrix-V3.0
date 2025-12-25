"""خطاها و اشیای بیانگر مشکلات قرارداد ورودی."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

__all__ = ["InputContractIssue", "InputContractError"]


@dataclass(frozen=True)
class InputContractIssue:
    """یک مورد مشخص از نقض قرارداد ورودی."""

    code: str
    message: str
    column: str | None = None
    count: int | None = None

    def __str__(self) -> str:  # pragma: no cover - ساده و قطعی
        return self.message


class InputContractError(ValueError):
    """خطای سطح بالا برای شکست قرارداد ورودی."""

    issues: Sequence[InputContractIssue]

    def __init__(self, issues: Iterable[InputContractIssue]):
        self.issues = list(issues)
        super().__init__("\n".join(str(issue) for issue in self.issues))


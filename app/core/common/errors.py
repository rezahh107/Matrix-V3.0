"""تعریف خطاهای دامنه برای هستهٔ ماتریس احراز صلاحیت."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any


class DomainError(Exception):
    """پایهٔ تمام خطاهای دامنه‌ای."""


@dataclass(frozen=True, slots=True)
class BaseDomainError(DomainError):
    """خطای غنی‌شده با زمینه برای دیباگ و گزارش‌گیری.

    Attributes:
        func: نام تابعی که خطا در آن رخ داده است.
        column: نام ستون در صورت ارتباط.
        value: مقدار خامی که باعث خطا شده است.
        row_index: شمارهٔ سطر ورودی (۱-پایه) در صورت موجود بودن.
    """

    func: str
    column: str | None = None
    value: Any | None = None
    row_index: int | None = None

    def __str__(self) -> str:  # pragma: no cover - نمایش ساده
        parts: list[str] = [self.__class__.__name__, f"func={self.func}"]
        if self.column is not None:
            parts.append(f"column={self.column}")
        if self.value is not None:
            parts.append(f"value={self.value!r}")
        if self.row_index is not None:
            parts.append(f"row_index={self.row_index}")
        return " ".join(parts)


class InvalidGenderValueError(BaseDomainError):
    """زمانی که مقدار جنسیت قابل نرمال‌سازی نیست."""


class InvalidCenterMappingError(BaseDomainError):
    """وقوع خطا در تطبیق مدیر به مرکز."""


class DataMissingError(BaseDomainError):
    """برای مقادیر ضروری که وجود ندارند یا تهی هستند."""


class PolicyVersionMismatchError(BaseDomainError):
    """در صورت ناهماهنگی نسخهٔ policy بارگذاری‌شده."""


@dataclass(frozen=True, slots=True)
class ContractIssue:
    """جزئیات نقض قراردادهای خروجی/مرزی برای گزارش‌گیری."""

    code: str
    message: str
    context: str | None = None


class ContractViolationError(DomainError):
    """خطای سطح بالا برای نقض قراردادهای خروجی."""

    issues: Sequence[ContractIssue]

    def __init__(self, issues: Iterable[ContractIssue]) -> None:
        self.issues = list(issues)
        super().__init__("\n".join(issue.message for issue in self.issues))


__all__ = [
    "DomainError",
    "BaseDomainError",
    "InvalidGenderValueError",
    "InvalidCenterMappingError",
    "DataMissingError",
    "PolicyVersionMismatchError",
    "ContractIssue",
    "ContractViolationError",
]

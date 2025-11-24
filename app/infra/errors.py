"""مدل خطای لایهٔ Infra برای عملیات پایگاه داده."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


class InfraError(RuntimeError):
    """پایهٔ همهٔ خطاهای لایهٔ زیرساخت."""

    def __str__(self) -> str:  # pragma: no cover - ساده
        return super().__str__()


@dataclass(eq=True)
class DatabaseDisabledError(InfraError):
    """وقتی دیتابیس محلی بنا به تنظیمات غیرفعال شده باشد."""

    reason: str = "پایگاه دادهٔ محلی غیرفعال است."

    def __str__(self) -> str:
        return self.reason


@dataclass(eq=True)
class ReferenceDataMissingError(InfraError):
    """نبود جداول مرجع ضروری مانند مدارس یا Crosswalk."""

    table: str
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(eq=True)
class SchemaVersionMismatchError(InfraError):
    """عدم تطابق نسخهٔ Schema پایگاه داده با نسخهٔ مورد انتظار."""

    expected_version: int
    actual_version: int
    message: str

    def __str__(self) -> str:
        return f"{self.message} (expected={self.expected_version}, actual={self.actual_version})"


@dataclass(eq=True)
class DatabaseOperationError(InfraError):
    """خطای کلی عملیات SQLite با پیام خوانا."""

    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(eq=True)
class DatabasePreparationError(DatabaseOperationError):
    """خطای آماده‌سازی پایگاه‌داده با پیام و راهکار عملیاتی."""

    path: str
    reason: str
    hint: str | None = None
    message: str = field(init=False)

    def __post_init__(self) -> None:
        path_text = str(self.path)
        details = self.reason.strip()
        if self.hint:
            details = f"{details}؛ {self.hint.strip()}"
        self.message = f"خطا در آماده‌سازی پایگاه داده: {details} (مسیر: {path_text})"


@dataclass(eq=True)
class DatabaseCorruptError(DatabasePreparationError):
    """پایگاه داده خراب است و بکاپ گرفته شده است."""

    backup_path: Path | None = None

    def __post_init__(self) -> None:  # pragma: no cover - delegated to base
        hint_parts: list[str] = []
        if self.hint:
            hint_parts.append(self.hint.strip())
        if self.backup_path:
            hint_parts.append(f"بکاپ در {self.backup_path} ذخیره شد")
        combined_hint = "؛ ".join(part for part in hint_parts if part)
        self.hint = combined_hint or None
        super().__post_init__()


@dataclass(eq=True)
class DatabaseSchemaMismatchError(DatabasePreparationError):
    """عدم سازگاری ساختار پایگاه‌داده با نسخهٔ فعلی برنامه."""

    diagnostics: dict[str, list[str]] | None = None

    def __post_init__(self) -> None:  # pragma: no cover - پیام توسط والد مدیریت می‌شود
        super().__post_init__()


__all__ = [
    "InfraError",
    "DatabaseDisabledError",
    "ReferenceDataMissingError",
    "SchemaVersionMismatchError",
    "DatabaseOperationError",
    "DatabasePreparationError",
    "DatabaseCorruptError",
    "DatabaseSchemaMismatchError",
]

"""قراردادهای ورودی مبتنی بر Pandera با پیام‌های فارسی."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import pandas as pd
import pandera as pa

from app.core.contracts.contract_errors import InputContractError, InputContractIssue

__all__ = [
    "InputContractSpec",
    "StudentReportSpec",
    "PoolSpec",
    "InspactorSpec",
    "SchoolsSpec",
    "CrosswalkGroupsSpec",
    "CrosswalkSynonymsSpec",
]

JOIN_KEY_COLUMNS: tuple[str, ...] = (
    "کدرشته",
    "جنسیت",
    "دانش آموز فارغ",
    "مرکز گلستان صدرا",
    "مالی حکمت بنیاد",
    "کد مدرسه",
)


def _non_nullable_columns(columns: Sequence[str]) -> dict[str, pa.Column]:
    return {column: pa.Column(None, required=True, nullable=False) for column in columns}


@dataclass(frozen=True)
class InputContractSpec:
    """قرارداد ورودی با اسکیما و پیام‌های فارسی."""

    name: str
    required_columns: tuple[str, ...]
    schema: pa.DataFrameSchema

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        missing_columns = [col for col in self.required_columns if col not in df.columns]
        if missing_columns:
            raise InputContractError(
                InputContractIssue(
                    code="missing_column",
                    column=col,
                    message=f"ستون «{col}» الزامی است و در ورودی وجود ندارد.",
                )
                for col in missing_columns
            )

        try:
            return self.schema.validate(df, lazy=True)
        except pa.errors.SchemaErrors as exc:
            raise InputContractError(_map_schema_errors(exc)) from None


def _map_schema_errors(exc: pa.errors.SchemaErrors) -> Sequence[InputContractIssue]:
    failures = exc.failure_cases
    if failures is None or failures.empty:
        return (
            InputContractIssue(
                code="schema_error",
                message="اعتبارسنجی ورودی ناموفق بود (جزئیات در دسترس نیست).",
            ),
        )

    issues: list[InputContractIssue] = []
    for column, group in failures.groupby("column", dropna=False):
        column_name = column if isinstance(column, str) else None
        null_mask = group["failure_case"].isna() | (group["failure_case"] == "null values not allowed")
        null_count = int(null_mask.sum())
        if null_count > 0:
            issues.append(
                InputContractIssue(
                    code="null_value",
                    column=column_name,
                    count=null_count,
                    message=(
                        f"ستون الزامی «{column_name}» دارای {null_count} مقدار خالی است؛ "
                        "لطفاً مقادیر تهی را اصلاح کنید."
                    ),
                )
            )
            continue

        failures_text = "، ".join(sorted({str(value) for value in group["failure_case"]}))
        issues.append(
            InputContractIssue(
                code="invalid_value",
                column=column_name,
                message=(
                    f"اعتبارسنجی ستون «{column_name or 'نامشخص'}» ناموفق بود: "
                    f"{failures_text or 'مقدار نامعتبر'}"
                ),
            )
        )

    return issues


class StudentReportSpec(InputContractSpec):
    def __init__(self) -> None:
        super().__init__(
            name="student_report",
            required_columns=JOIN_KEY_COLUMNS,
            schema=pa.DataFrameSchema(_non_nullable_columns(JOIN_KEY_COLUMNS), coerce=False, strict=False),
        )


class PoolSpec(InputContractSpec):
    def __init__(self) -> None:
        super().__init__(
            name="pool",
            required_columns=JOIN_KEY_COLUMNS,
            schema=pa.DataFrameSchema(_non_nullable_columns(JOIN_KEY_COLUMNS), coerce=False, strict=False),
        )


class InspactorSpec(InputContractSpec):
    def __init__(self) -> None:
        required_columns: tuple[str, ...] = ()
        super().__init__(
            name="inspactor",
            required_columns=required_columns,
            schema=pa.DataFrameSchema({}, coerce=False, strict=False),
        )


class SchoolsSpec(InputContractSpec):
    def __init__(self) -> None:
        required_columns = ("کد مدرسه",)
        super().__init__(
            name="schools",
            required_columns=required_columns,
            schema=pa.DataFrameSchema(_non_nullable_columns(required_columns), coerce=False, strict=False),
        )


class CrosswalkGroupsSpec(InputContractSpec):
    def __init__(self) -> None:
        required_columns = ("کد گروه",)
        super().__init__(
            name="crosswalk_groups",
            required_columns=required_columns,
            schema=pa.DataFrameSchema(_non_nullable_columns(required_columns), coerce=False, strict=False),
        )


class CrosswalkSynonymsSpec(InputContractSpec):
    def __init__(self) -> None:
        required_columns = ("کد گروه", "جایگزین")
        super().__init__(
            name="crosswalk_synonyms",
            required_columns=required_columns,
            schema=pa.DataFrameSchema(_non_nullable_columns(required_columns), coerce=False, strict=False),
        )


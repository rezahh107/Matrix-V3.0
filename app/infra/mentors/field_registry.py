from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.core.policy_loader import PolicyConfig

_SCHOOL_BINDING_FIELDS: tuple[str, ...] = (
    "کد مدرسه 1",
    "کد مدرسه 2",
    "کد مدرسه 3",
    "کد مدرسه 4",
)

_MENTOR_HEADER_ALIASES: dict[str, str] = {
    # join keys
    "کدرشته": "کدرشته",
    "کد رشته": "کدرشته",
    "کد گروه": "کدرشته",
    "کد گروه آزمایشی": "کدرشته",
    "گروه آزمایشی": "گروه آزمایشی",
    "جنسیت": "جنسیت",
    "gender": "جنسیت",
    "دانش آموز فارغ": "دانش آموز فارغ",
    "مرکز گلستان صدرا": "مرکز گلستان صدرا",
    "مالی حکمت بنیاد": "مالی حکمت بنیاد",
    "کد مدرسه": "کد مدرسه",
    "school code": "کد مدرسه",
    # identifiers and metadata
    "mentor_id": "mentor_id",
    "mentorid": "mentor_id",
    "mentor code": "mentor_id",
    "mentor_code": "mentor_id",
    "mentorcode": "mentor_id",
    "employee_id": "mentor_id",
    "employeeid": "mentor_id",
    "کد کارمندی پشتیبان": "mentor_id",
    "نام پشتیبان": "نام پشتیبان",
    "mentor name": "نام پشتیبان",
    "mentor": "نام پشتیبان",
    "manager": "نام مدیر",
    "manager name": "نام مدیر",
    "manager_name": "نام مدیر",
    "نام مدیر": "نام مدیر",
    # capacity and coverage
    "remaining_capacity": "remaining_capacity",
    "capacity_limit": "capacity_limit",
    "assigned_baseline": "assigned_baseline",
    "تعداد داوطلبان تحت پوشش": "capacity_current",
    "capacity_current": "capacity_current",
    "تعداد تحت پوشش خاص": "capacity_special",
    "capacity_special": "capacity_special",
    "تعداد مدارس تحت پوشش": "schools_covered_count",
    "schools_covered_count": "schools_covered_count",
    "covered_students_count": "covered_students_count",
    # school references (canonicalized to school_code_1..4)
    "نام مدرسه": "نام مدرسه",
    "نام مدرسه 1": "کد مدرسه 1",
    "نام مدرسه 2": "کد مدرسه 2",
    "نام مدرسه 3": "کد مدرسه 3",
    "نام مدرسه 4": "کد مدرسه 4",
    "کد مدرسه 1": "کد مدرسه 1",
    "کد مدرسه 2": "کد مدرسه 2",
    "کد مدرسه 3": "کد مدرسه 3",
    "کد مدرسه 4": "کد مدرسه 4",
}

_SCHOOL_BINDING_HEADERS: tuple[tuple[str, str], ...] = (
    ("کد مدرسه 1", "نام مدرسه 1"),
    ("کد مدرسه 2", "نام مدرسه 2"),
    ("کد مدرسه 3", "نام مدرسه 3"),
    ("کد مدرسه 4", "نام مدرسه 4"),
)


@dataclass(frozen=True)
class FieldRegistry:
    """Registry for mentor join and metadata fields used by the v3 pipeline."""

    policy: PolicyConfig

    @property
    def join_fields(self) -> list[str]:
        return list(self.policy.join_keys)

    @property
    def school_binding_fields(self) -> list[str]:
        return list(_SCHOOL_BINDING_FIELDS)

    @property
    def school_binding_headers(self) -> tuple[tuple[str, str], ...]:
        return _SCHOOL_BINDING_HEADERS

    @property
    def required_fields(self) -> list[str]:
        return ["mentor_id", *self.policy.join_keys]

    def has_required_fields(self, columns: Iterable[str]) -> bool:
        column_set = {col for col in columns}
        return all(field in column_set for field in self.required_fields)

    @property
    def header_aliases(self) -> dict[str, str]:
        return dict(_MENTOR_HEADER_ALIASES)

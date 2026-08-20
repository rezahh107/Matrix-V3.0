"""
Domain models and logic for Eligibility Matrix → Allocation system.
Python 3.10+, stdlib only, no I/O, no side-effects on import.
Deterministic and fail-safe, adhering to Policy v1.0.3.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Literal, TypedDict, TypeGuard, final

from app.core.policy_loader import PolicyConfig, load_policy

from .errors import DataMissingError, InvalidCenterMappingError, InvalidGenderValueError
from .normalization import normalize_fa, to_numlike_str

# ---------------------------------------------------------------------------
# Type Aliases
# ---------------------------------------------------------------------------
# StudentRow: TypeAlias = Mapping[str, Any]  # Not using TypeAlias for stdlib compatibility
StudentRow = Mapping[str, Any]
JoinKeyDict = dict[str, int]
MentorDict = dict[str, Any]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


@final
class MentorType(Enum):
    """Type of mentor based on school coverage in Inspactor."""

    NORMAL = "normal"
    SCHOOL = "school"


@final
class StudentBindingKind(Enum):
    """Binding classification for students based on school membership."""

    NORMAL = "normal"
    SCHOOL = "school"
    MENTOR_BASED = "mentor_based"


@final
class Status(IntEnum):
    """Student graduation status."""

    STUDENT = 1
    GRADUATE = 0


# Policy v1.0.3: only these کدرشته‌ها support both student and graduate statuses.
# توجه: «گروه آزمایشی هفتم/پایه هفتم» با کد 33 است و نباید با کدرشتهٔ 7
# (هنر کنکوری) اشتباه گرفته شود؛ منطق دامنه بر اساس کدرشته اعمال می‌شود.
DUAL_STATUS_GROUPS: frozenset[int] = frozenset(
    {
        1,
        3,
        5,
        7,
        8,
        9,
        11,
        12,
        14,
        17,
        18,
    }
)

# Student-only overrides for groups که حتی در صورت سابقهٔ دوحالته بودن، وضعیت
# فارغ‌التحصیل نباید داشته باشند (پایه‌های هفتم، هشتم و نهم با کدرشته‌های 33، 31،
# 27). سایر کدرشته‌ها به صورت پیش‌فرض دانش‌آموزی هستند مگر این‌که در دامنهٔ بالا
# باشند.
STUDENT_ONLY_GROUPS: frozenset[int] = frozenset({33, 31, 27})


@dataclass(frozen=True, slots=True)
class EducationalRecord:
    """Canonical triple for educational level, experimental group/grade, and code."""

    educational_level: str
    experimental_group: str
    field_code: int


EDUCATIONAL_STRUCTURE: tuple[EducationalRecord, ...] = (
    # کنکوری (University Entrance)
    EducationalRecord("کنکوری", "دوازدهم ریاضی", 1),
    EducationalRecord("کنکوری", "دوازدهم تجربی", 3),
    EducationalRecord("کنکوری", "دوازدهم انسانی", 5),
    EducationalRecord("کنکوری", "هنر", 7),
    EducationalRecord("کنکوری", "دوازدهم علوم و معارف اسلامی", 8),
    EducationalRecord("کنکوری", "منحصرا زبان", 9),
    # متوسطه دوم (High School)
    EducationalRecord("متوسطه دوم", "دهم ریاضی", 24),
    EducationalRecord("متوسطه دوم", "دهم تجربی", 25),
    EducationalRecord("متوسطه دوم", "دهم انسانی", 26),
    EducationalRecord("متوسطه دوم", "دهم علوم و معارف اسلامی", 30),
    EducationalRecord("متوسطه دوم", "یازدهم ریاضی", 21),
    EducationalRecord("متوسطه دوم", "یازدهم تجربی", 22),
    EducationalRecord("متوسطه دوم", "یازدهم علوم انسانی", 23),
    EducationalRecord("متوسطه دوم", "یازدهم علوم و معارف اسلامی", 29),
    # متوسطه اول (Middle School)
    EducationalRecord("متوسطه اول", "نهم", 27),
    EducationalRecord("متوسطه اول", "هشتم", 31),
    EducationalRecord("متوسطه اول", "هفتم", 33),
    # دبستان (Elementary)
    EducationalRecord("دبستان", "دوم دبستان", 46),
    EducationalRecord("دبستان", "سوم دبستان", 45),
    EducationalRecord("دبستان", "چهارم دبستان", 43),
    EducationalRecord("دبستان", "پنجم دبستان", 41),
    EducationalRecord("دبستان", "ششم دبستان", 35),
    # هنرستان (Technical School)
    EducationalRecord("هنرستان", "دوازدهم الکتروتکنیک", 11),
    EducationalRecord("هنرستان", "دوازدهم شبکه و نرم‌افزار رایانه", 12),
    EducationalRecord("هنرستان", "دوازدهم تربیت بدنی", 14),
    EducationalRecord("هنرستان", "دوازدهم حسابداری", 17),
    EducationalRecord("هنرستان", "دوازدهم مکانیک خودرو", 18),
    EducationalRecord("هنرستان", "یازدهم الکتروتکنیک", 53),
    EducationalRecord("هنرستان", "یازدهم شبکه و نرم افزار", 55),
    EducationalRecord("هنرستان", "یازدهم تربیت بدنی", 66),
    EducationalRecord("هنرستان", "یازدهم حسابداری", 69),
    EducationalRecord("هنرستان", "دهم شبکه و نرم‌افزار رایانه", 83),
    EducationalRecord("هنرستان", "دهم حسابداری", 89),
)

# Canonical, single-source list of valid experimental group codes derived from the
# educational structure. Keep sorted for deterministic consumers.
VALID_GROUP_CODES: frozenset[int] = frozenset(
    record.field_code for record in EDUCATIONAL_STRUCTURE
)


class AcademicInfo(TypedDict):
    level: str
    group: str
    code: int
    allowed_status: set[int]
    is_dual_status: bool


_CODE_TO_RECORD: dict[int, EducationalRecord] = {
    record.field_code: record for record in EDUCATIONAL_STRUCTURE
}


def _normalize_edu_text(value: str) -> str:
    return " ".join(normalize_fa(value).split())


_GROUP_TO_CODES: dict[tuple[str, str], int] = {
    (record.educational_level, record.experimental_group): record.field_code
    for record in EDUCATIONAL_STRUCTURE
}
_GROUP_TO_CODES_NORMALIZED: dict[tuple[str, str], int] = {
    (_normalize_edu_text(record.educational_level), _normalize_edu_text(record.experimental_group)): record.field_code
    for record in EDUCATIONAL_STRUCTURE
}

if len(_CODE_TO_RECORD) != len(EDUCATIONAL_STRUCTURE):
    raise ValueError("Duplicate field_code detected in EDUCATIONAL_STRUCTURE")

if len(_GROUP_TO_CODES) != len(EDUCATIONAL_STRUCTURE):
    raise ValueError(
        "Duplicate (educational_level, experimental_group) detected in EDUCATIONAL_STRUCTURE"
    )
if len(_GROUP_TO_CODES_NORMALIZED) != len(EDUCATIONAL_STRUCTURE):
    raise ValueError(
        "Duplicate normalized (educational_level, experimental_group) detected in EDUCATIONAL_STRUCTURE"
    )


def get_info_from_code(field_code: int) -> tuple[str, str, int]:
    """Return (educational_level, experimental_group, field_code) for the code."""

    record = _CODE_TO_RECORD.get(field_code)
    if record is None:
        raise DataMissingError(func="get_info_from_code", column="کدرشته", value=field_code)
    return (record.educational_level, record.experimental_group, record.field_code)


def get_code_from_group(experimental_group_name: str, educational_level: str | None = None) -> int:
    """Return the unique code for the given group name, optionally narrowed by level."""

    matches: list[int] = []
    if educational_level is not None:
        code = _GROUP_TO_CODES.get((educational_level, experimental_group_name))
        if code is not None:
            return code
        normalized_level = _normalize_edu_text(educational_level)
        normalized_group = _normalize_edu_text(experimental_group_name)
        code = _GROUP_TO_CODES_NORMALIZED.get((normalized_level, normalized_group))
        if code is not None:
            return code
    else:
        matches = [
            code
            for (level, group), code in _GROUP_TO_CODES.items()
            if group == experimental_group_name
        ]
        normalized_group = _normalize_edu_text(experimental_group_name)
        for (level, group), code in _GROUP_TO_CODES_NORMALIZED.items():
            if group == normalized_group and code not in matches:
                matches.append(code)
        if len(matches) == 1:
            return matches[0]
    raise DataMissingError(
        func="get_code_from_group",
        column="گروه آزمایشی",
        value={
            "experimental_group": experimental_group_name,
            "educational_level": educational_level,
            "candidates": matches,
        },
    )


def is_dual_status_code(field_code: int) -> bool:
    """Return True if the code supports dual graduation statuses."""

    return field_code in DUAL_STATUS_GROUPS


def allowed_statuses_for_group(group_code: int, *, is_school_branch: bool) -> tuple[int, ...]:
    """Return graduation_status domain for the given group and mentor branch.

    School-branch mentors are student-only. Normal mentors may expose both
    statuses only for the Policy-approved dual-status groups; all other groups
    are constrained to the student status (1).
    """

    if is_school_branch:
        return (Status.STUDENT,)
    if group_code in STUDENT_ONLY_GROUPS:
        return (Status.STUDENT,)
    if group_code in DUAL_STATUS_GROUPS:
        return (Status.STUDENT, Status.GRADUATE)
    return (Status.STUDENT,)


def get_academic_info(field_code: int) -> AcademicInfo:
    """Return complete educational info for the given code, including status.

    Raises:
        DataMissingError: اگر کد رشته در ساختار آموزشی تعریف نشده باشد.
    """

    record = _CODE_TO_RECORD.get(field_code)
    if record is None:
        raise DataMissingError(func="get_academic_info", column="کدرشته", value=field_code)

    is_dual_status = field_code in DUAL_STATUS_GROUPS
    allowed_status: set[int] = {Status.STUDENT}
    if is_dual_status:
        allowed_status.add(Status.GRADUATE)

    return AcademicInfo(
        level=record.educational_level,
        group=record.experimental_group,
        code=record.field_code,
        allowed_status=allowed_status,
        is_dual_status=is_dual_status,
    )


def validate_student_allocation(field_code: int, student_status: int) -> bool:
    """Check if the student status is allowed for the field code."""

    if student_status not in (Status.STUDENT, Status.GRADUATE):
        raise ValueError("student_status must be 0 (graduate) or 1 (student)")

    academic_info = get_academic_info(field_code)
    return student_status in academic_info["allowed_status"]


def get_eligible_codes_for_status(student_status: int) -> list[int]:
    """Return all field codes eligible for the given student status."""

    if student_status == Status.GRADUATE:
        return sorted(DUAL_STATUS_GROUPS)
    if student_status == Status.STUDENT:
        return sorted(_CODE_TO_RECORD.keys())
    raise ValueError("student_status must be 0 (graduate) or 1 (student)")


@final
class Gender(IntEnum):
    """Gender codes."""

    MALE = 1
    FEMALE = 0


@final
class FinanceCode(IntEnum):
    """Valid finance codes."""

    NORMAL = 0
    FOUNDATION = 1
    HEKMAT = 3


# ---------------------------------------------------------------------------
# Column name constants
# ---------------------------------------------------------------------------

COL_GROUP = "کدرشته"
COL_GENDER = "جنسیت"
COL_STATUS = "دانش آموز فارغ"
COL_CENTER = "مرکز گلستان صدرا"
COL_FINANCE = "مالی حکمت بنیاد"
COL_SCHOOL = "کد مدرسه"
COL_SCHOOL_NAME = "نام مدرسه"
COL_SCHOOL_CODE_1 = "کد مدرسه 1"
COL_SCHOOL_CODE_2 = "کد مدرسه 2"
COL_SCHOOL_CODE_3 = "کد مدرسه 3"
COL_SCHOOL_CODE_4 = "کد مدرسه 4"
COL_SCHOOL_NAME_1 = "نام مدرسه 1"
COL_SCHOOL_NAME_2 = "نام مدرسه 2"
COL_SCHOOL_NAME_3 = "نام مدرسه 3"
COL_SCHOOL_NAME_4 = "نام مدرسه 4"
COL_FULL_SCHOOL_CODE = "کد کامل مدرسه"
COL_EDU_CODE = "کد آموزش و پرورش"
COL_ALIAS = "جایگزین"
COL_MENTOR = "پشتیبان"
COL_MANAGER = "مدیر"
COL_MENTOR_ID = "کد کارمندی پشتیبان"
COL_MENTOR_ROWID = "ردیف پشتیبان"
# New column for output schema
COL_MENTOR_TYPE = "عادی مدرسه"


# ---------------------------------------------------------------------------
# Internal helpers (fail-safe)
# ---------------------------------------------------------------------------

# Status normalization constants
_STATUS_GRADUATE_EN = frozenset({"0", "graduate", "grad"})
_STATUS_STUDENT_EN = frozenset({"1", "student", "pupil"})
_STATUS_GRADUATE_FA = frozenset({"فارغ", "فارغ التحصیل"})
_STATUS_STUDENT_FA = frozenset({"دانش آموز", "دانشجو", "دانش اموز"})

# Gender normalization constants
_GENDER_MALE_EN = frozenset({"1", "male", "m", "boy", "♂"})
_GENDER_FEMALE_EN = frozenset({"0", "female", "f", "girl", "♀"})
_GENDER_MALE_FA = frozenset({"پسر", "مذکر"})
_GENDER_FEMALE_FA = frozenset({"دختر", "مونث"})
_GENDER_MALE_FA_NORMALIZED = frozenset(normalize_fa(tok) for tok in _GENDER_MALE_FA)
_GENDER_FEMALE_FA_NORMALIZED = frozenset(normalize_fa(tok) for tok in _GENDER_FEMALE_FA)
_GENDER_NUMERIC_TRANSLATION = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫",
    "01234567890123456789.",
)


def _num_to_int_safe(x: Any) -> int:
    """تبدیل امن مقدار به int بدون ایجاد استثناء غیرمنتظره.

    مثال::

        >>> _num_to_int_safe("12.7")
        12

    """

    s = to_numlike_str(x)
    if not s or s == "-":
        return 0
    sign = -1 if s.startswith("-") else 1
    digits = s[1:] if sign == -1 else s
    int_part = digits.split(".")[0]
    if not int_part:
        return 0
    if int_part.isdigit():
        return sign * int(int_part)
    return 0


def _coerce_center_id(val: Any, default_zero: int = 0) -> int:
    """تبدیل مقدار ورودی به شناسهٔ مرکز غیرمنفی."""

    n = _num_to_int_safe(val)
    return n if n >= 0 else default_zero


def _coerce_finance(val: Any, *, cfg: BuildConfig) -> int:
    """بازگرداندن کد مالی معتبر مطابق تنظیمات."""

    v = _num_to_int_safe(val)
    variants = cfg.finance_variants or ()
    if v in variants:
        return v
    return variants[0] if variants else 0


def _normalize_map_keys(m: Mapping[str, int]) -> dict[str, int]:
    """نرمال‌سازی کلیدهای نگاشت مراکز با رعایت wildcard."""

    out: dict[str, int] = {}
    for k, v in m.items():
        normalized_key = "*" if k == "*" else normalize_fa(k)
        if normalized_key:
            out[normalized_key] = _num_to_int_safe(v)
    return out


def _postal_valid(num_str: str, *, cfg: BuildConfig) -> bool:
    """اعتبارسنجی بازهٔ کدپستی مطابق پیکربندی."""

    n = _num_to_int_safe(num_str)
    postal_range = cfg.postal_valid_range
    if postal_range is None:
        raise ValueError("postal_valid_range is not configured")
    min_val, max_val = postal_range
    return min_val <= n <= max_val


def is_valid_postal_code(postal_code: Any) -> TypeGuard[str]:
    """
    TypeGuard to check if a value is a string of digits (potential postal code).
    This is a basic check before further validation.
    """
    return isinstance(postal_code, str) and postal_code.isdigit()


def _compute_school_alias(mentor_id: Any) -> str:
    """تولید alias شاخهٔ مدرسه‌ای؛ متن خام بدون اعشار ساختگی."""

    if mentor_id is None:
        return ""
    if isinstance(mentor_id, (int,)):
        return str(int(mentor_id))
    if isinstance(mentor_id, float):
        if math.isnan(mentor_id):
            return ""
        if mentor_id.is_integer():
            return str(int(mentor_id))
        return str(mentor_id)
    text = str(mentor_id).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def _normalize_normal_alias(postal_code: Any, cfg: BuildConfig) -> str:
    """Normalize postal code for NORMAL mentors using configured range."""

    postal_str = to_numlike_str(postal_code).strip()
    if not postal_str:
        return ""
    if not any(ch.isdigit() for ch in postal_str):
        return ""
    numeric_value = _num_to_int_safe(postal_str)
    alias = str(numeric_value)
    if not alias.isdigit():
        return ""
    if not _postal_valid(alias, cfg=cfg):
        return ""
    return alias


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@final
@dataclass(slots=True)
class BuildConfig:
    """
    Build-time configuration for the allocation system.

    Attributes:
        policy: Active policy reference for defaults and validation
        expected_policy_version: Optional policy version guard
        postal_valid_range: Min/max for valid postal codes
        finance_variants: Valid finance codes
        center_map: Manager name → center ID mapping
        school_code_empty_as_zero: Treat empty school codes as 0
        alias_rule_normal: Alias rule for NORMAL mentors
        alias_rule_school: Alias rule for SCHOOL mentors
        prefer_major_code: Whether StudentReport «کد رشته» overrides group name mapping
        min_coverage_ratio: Coverage threshold for validation sheets
        dedup_removed_ratio_threshold: Allowed duplicate-removal ratio
        join_key_duplicate_threshold: Maximum tolerated join-key collisions
        school_lookup_mismatch_threshold: Allowed ratio of unmatched school lookups
    """

    version: str = "1.0.4"
    policy: PolicyConfig = field(default_factory=load_policy)
    expected_policy_version: str | None = None
    finance_variants: tuple[int, ...] | None = None
    default_status: int = Status.STUDENT
    enable_capacity_gate: bool = True
    center_map: dict[str, int] | None = None
    can_allocate_truthy: tuple[str, ...] = ("بلی", "بله", "Yes", "yes", "1", "true", "True")
    postal_valid_range: tuple[int, int] | None = None
    school_code_empty_as_zero: bool | None = None
    alias_rule_normal: str | None = None
    alias_rule_school: str | None = None
    postal_code_column: str | None = None
    school_count_column: str | None = None
    school_code_column: str | None = None
    capacity_current_column: str | None = None
    capacity_special_column: str | None = None
    remaining_capacity_column: str | None = None
    prefer_major_code: bool | None = None
    min_coverage_ratio: float | None = None
    dedup_removed_ratio_threshold: float | None = None
    join_key_duplicate_threshold: int | None = None
    school_lookup_mismatch_threshold: float | None = None
    fail_on_school_lookup_threshold: bool = False
    policy_version: str = field(init=False)
    _center_map_norm: dict[str, int] = field(init=False, repr=False, default_factory=dict)

    def __post_init__(self) -> None:
        """Validate and hydrate configuration after initialization."""

        policy_version = str(getattr(self.policy, "version", "")).strip()
        if not policy_version:
            raise ValueError("policy configuration missing version identifier")
        object.__setattr__(self, "policy_version", policy_version)

        if self.expected_policy_version is not None:
            cleaned = str(self.expected_policy_version).strip()
            object.__setattr__(self, "expected_policy_version", cleaned or None)

        if self.finance_variants is None:
            object.__setattr__(self, "finance_variants", tuple(self.policy.finance_variants))
        else:
            unique: list[int] = []
            seen: set[int] = set()
            for item in self.finance_variants:
                iv = int(item)
                if iv not in seen:
                    unique.append(iv)
                    seen.add(iv)
            object.__setattr__(self, "finance_variants", tuple(unique))

        if self.center_map is None:
            object.__setattr__(self, "center_map", dict(self.policy.center_map))
        else:
            normalized_center_map = {str(k): int(v) for k, v in self.center_map.items()}
            object.__setattr__(self, "center_map", normalized_center_map)
        object.__setattr__(self, "_center_map_norm", {})

        if self.postal_valid_range is None:
            policy_range = self.policy.postal_valid_range
            if policy_range is None:
                raise ValueError("policy configuration missing postal_valid_range")
            postal_range = (int(policy_range[0]), int(policy_range[1]))
        else:
            postal_range = (
                int(self.postal_valid_range[0]),
                int(self.postal_valid_range[1]),
            )
        if len(postal_range) != 2 or postal_range[0] > postal_range[1]:
            raise ValueError(f"Invalid postal range: {postal_range}")
        object.__setattr__(self, "postal_valid_range", postal_range)

        school_code_empty_as_zero = (
            bool(self.policy.school_code_empty_as_zero)
            if self.school_code_empty_as_zero is None
            else bool(self.school_code_empty_as_zero)
        )
        object.__setattr__(self, "school_code_empty_as_zero", school_code_empty_as_zero)

        if self.alias_rule_normal is None:
            object.__setattr__(self, "alias_rule_normal", self.policy.alias_rule.normal)
        if self.alias_rule_school is None:
            object.__setattr__(self, "alias_rule_school", self.policy.alias_rule.school)

        columns = self.policy.columns
        if self.postal_code_column is None:
            object.__setattr__(self, "postal_code_column", columns.postal_code)
        if self.school_count_column is None:
            object.__setattr__(self, "school_count_column", columns.school_count)
        if self.school_code_column is None:
            object.__setattr__(self, "school_code_column", columns.school_code)
        if self.capacity_current_column is None:
            object.__setattr__(self, "capacity_current_column", columns.capacity_current)
        if self.capacity_special_column is None:
            object.__setattr__(self, "capacity_special_column", columns.capacity_special)
        if self.remaining_capacity_column is None:
            object.__setattr__(self, "remaining_capacity_column", columns.remaining_capacity)

        prefer_major_code = (
            bool(getattr(self.policy, "prefer_major_code", True))
            if self.prefer_major_code is None
            else bool(self.prefer_major_code)
        )
        object.__setattr__(self, "prefer_major_code", prefer_major_code)

        coverage_ratio_raw = (
            0.0 if self.min_coverage_ratio is None else float(self.min_coverage_ratio)
        )
        min_coverage_ratio = (
            coverage_ratio_raw / 100.0 if coverage_ratio_raw > 1 else coverage_ratio_raw
        )
        if min_coverage_ratio < 0 or min_coverage_ratio > 1:
            raise ValueError("min_coverage_ratio must be between 0 and 1 (inclusive)")
        object.__setattr__(self, "min_coverage_ratio", min_coverage_ratio)

        dedup_ratio_raw = (
            float(getattr(self.policy, "dedup_removed_ratio_threshold", 0.0))
            if self.dedup_removed_ratio_threshold is None
            else float(self.dedup_removed_ratio_threshold)
        )
        dedup_ratio = dedup_ratio_raw / 100.0 if dedup_ratio_raw > 1 else dedup_ratio_raw
        if dedup_ratio < 0 or dedup_ratio > 1:
            raise ValueError("dedup_removed_ratio_threshold must be between 0 and 1 (inclusive)")
        object.__setattr__(self, "dedup_removed_ratio_threshold", dedup_ratio)

        join_key_threshold = (
            int(getattr(self.policy, "join_key_duplicate_threshold", 0))
            if self.join_key_duplicate_threshold is None
            else int(self.join_key_duplicate_threshold)
        )
        if join_key_threshold < 0:
            raise ValueError("join_key_duplicate_threshold must be >= 0")
        object.__setattr__(self, "join_key_duplicate_threshold", join_key_threshold)

        school_lookup_raw = (
            float(getattr(self.policy, "school_lookup_mismatch_threshold", 0.0))
            if self.school_lookup_mismatch_threshold is None
            else float(self.school_lookup_mismatch_threshold)
        )
        school_lookup_ratio = (
            school_lookup_raw / 100.0 if school_lookup_raw > 1 else school_lookup_raw
        )
        if school_lookup_ratio < 0 or school_lookup_ratio > 1:
            raise ValueError("school_lookup_mismatch_threshold must be between 0 and 1 (inclusive)")
        object.__setattr__(self, "school_lookup_mismatch_threshold", school_lookup_ratio)

        object.__setattr__(
            self,
            "fail_on_school_lookup_threshold",
            bool(self.fail_on_school_lookup_threshold),
        )

    def center_map_norm(self) -> dict[str, int]:
        """
        Get normalized center_map with keys normalized using normalize_fa.
        Cached after first call.
        """
        if not self._center_map_norm:
            center_map: Mapping[str, int] = self.center_map or {}
            object.__setattr__(self, "_center_map_norm", _normalize_map_keys(center_map))
        return self._center_map_norm


# ---------------------------------------------------------------------------
# Domain functions
# ---------------------------------------------------------------------------


def norm_status(x: Any) -> int:
    """نرمال‌سازی وضعیت تحصیلی به کد ۰/۱.

    مثال::

        >>> norm_status("فارغ")
        0

    """

    raw = str(x or "").strip().lower()
    if raw in _STATUS_GRADUATE_EN:
        return 0
    if raw in _STATUS_STUDENT_EN:
        return 1

    normalized = normalize_fa(x)
    if any(token in normalized for token in _STATUS_GRADUATE_FA):
        return 0
    if any(token in normalized for token in _STATUS_STUDENT_FA):
        return 1
    return 1


def norm_gender(x: Any, strict: bool = False) -> Gender:
    """نرمال‌سازی جنسیت به مقادیر دامنه‌ای.

    Args:
        x: مقدار خام ورودی.
        strict: در صورت `True` برای مقادیر ناشناخته استثناء می‌اندازد.

    Returns:
        عضو :class:`Gender` متناظر. در حالت غیرسخت‌گیر مقدار پیش‌فرض
        :data:`Gender.MALE` برگردانده می‌شود.

    Raises:
        InvalidGenderValueError: اگر `strict=True` و مقدار ورودی قابل نگاشت
            نباشد.
    """

    raw = "" if x is None else str(x).strip().lower()
    if raw in _GENDER_MALE_EN:
        return Gender.MALE
    if raw in _GENDER_FEMALE_EN:
        return Gender.FEMALE

    normalized = normalize_fa(x)
    normalized_padded = f" {normalized} " if normalized else ""
    if normalized_padded:
        if any(f" {token} " in normalized_padded for token in _GENDER_MALE_FA_NORMALIZED):
            return Gender.MALE
        if any(f" {token} " in normalized_padded for token in _GENDER_FEMALE_FA_NORMALIZED):
            return Gender.FEMALE

    numeric_text = raw.translate(_GENDER_NUMERIC_TRANSLATION)
    integer_text, separator, fraction_text = numeric_text.partition(".")
    is_integer_literal = bool(integer_text) and integer_text.isdigit() and not separator
    is_zero_fraction_literal = (
        bool(integer_text)
        and integer_text.isdigit()
        and separator == "."
        and bool(fraction_text)
        and fraction_text.isdigit()
        and not fraction_text.strip("0")
    )
    if is_integer_literal or is_zero_fraction_literal:
        numeric = int(integer_text)
        if numeric == int(Gender.MALE):
            return Gender.MALE
        if numeric == int(Gender.FEMALE):
            return Gender.FEMALE

    if strict:
        raise InvalidGenderValueError(
            func="norm_gender",
            column=COL_GENDER,
            value=x,
        )

    return Gender.MALE


def center_from_manager(name: Any, *, cfg: BuildConfig) -> int:
    """استخراج شناسهٔ مرکز از نام مدیر با استفاده از نگاشت پیکربندی.

    مثال::

        >>> cfg = BuildConfig(center_map={"مدیر الف": 2, "*": 0})
        >>> center_from_manager("مدیر الف", cfg=cfg)
        2

    """

    s = normalize_fa(name)
    cmap = cfg.center_map_norm()
    wildcard = cmap.get("*")

    if s:
        if s in cmap:
            return cmap[s]

        matches: list[tuple[str, int]] = []
        for key, val in cmap.items():
            if key == "*" or not key:
                continue
            if key in s:
                matches.append((key, val))

        if matches:
            matches.sort(key=lambda item: (-len(item[0]), item[0]))
            return matches[0][1]

    if wildcard is not None and cfg.policy.center_management.unknown_manager_mode == "wildcard":
        return wildcard

    raise InvalidCenterMappingError(func="center_from_manager", value=name)


def classify_mentor_type_from_school_count(school_count: int | None) -> MentorType:
    """Derive mentor type solely from Inspactor school coverage count."""

    count = 0 if school_count is None else int(school_count)
    return MentorType.SCHOOL if count > 0 else MentorType.NORMAL


def mentor_alias_for_type(
    mentor_type: MentorType, postal_code: Any, mentor_id: Any, *, cfg: BuildConfig
) -> str:
    """Return alias value based on mentor type without changing semantics.

    - ``MentorType.NORMAL`` → normalized postal code (empty string if unusable).
    - ``MentorType.SCHOOL`` → normalized mentor_id.

    This helper never mutates mentor_type or infers type from alias values.
    """

    if mentor_type is MentorType.SCHOOL:
        return _compute_school_alias(mentor_id)
    return _normalize_normal_alias(postal_code, cfg)


def compute_alias(
    row_type: MentorType, postal_code: Any, mentor_id: Any, *, cfg: BuildConfig
) -> str:
    """Backward-compatible wrapper delegating to :func:`mentor_alias_for_type`."""

    return mentor_alias_for_type(row_type, postal_code, mentor_id, cfg=cfg)


def school_code_norm(value: Any, *, cfg: BuildConfig) -> int:
    """نرمال‌سازی کد مدرسه به عدد صحیح غیرمنفی."""

    text = to_numlike_str(value)
    if not text:
        return 0 if cfg.school_code_empty_as_zero else 0
    code = _num_to_int_safe(text)
    return max(code, 0)


def classify_student_binding(student: Mapping[str, Any], *, cfg: BuildConfig) -> StudentBindingKind:
    """Classify student binding based on school code and graduation status.

    The rule is deterministic and policy-driven:

    - If the student's school code belongs to ``policy.allocation_channels.school_codes``
      **and** graduation status equals ``Status.STUDENT`` → ``SCHOOL``.
    - Otherwise → ``NORMAL``.

    Postal code is intentionally ignored; school membership is defined solely by
    configured school codes plus graduation status.
    """

    policy = cfg.policy
    school_codes = policy.allocation_channels.school_codes
    school_column = policy.columns.school_code

    try:
        status_column = policy.stage_column("graduation_status")
    except KeyError:
        status_column = COL_STATUS

    school_value = student.get(school_column, 0)
    school_code = _num_to_int_safe(school_value)
    status_value = student.get(status_column, cfg.default_status)
    if status_value is None or (isinstance(status_value, float) and math.isnan(status_value)):
        status_value = cfg.default_status
    graduation_status = _num_to_int_safe(status_value)

    if graduation_status == Status.STUDENT and school_code > 0 and school_code in school_codes:
        return StudentBindingKind.SCHOOL
    return StudentBindingKind.NORMAL


def finance_cross(values: Iterable[int] | None, *, cfg: BuildConfig) -> tuple[int, ...]:
    """تضمین می‌کند که تمامی مقادیر مالی سیاست در لیست ورودی حضور داشته باشند."""

    base: tuple[int, ...] = tuple(cfg.finance_variants or ())
    if values is None:
        return base
    seen: set[int] = set()
    ordered: list[int] = []
    for item in values:
        iv = int(item)
        if iv not in seen:
            ordered.append(iv)
            seen.add(iv)
    missing = [code for code in base if code not in seen]
    if missing:
        raise AssertionError(f"finance codes missing from variants: {missing}")
    return tuple(ordered)


def compute_mentor_type_str(row_type: MentorType) -> str:
    """تبدیل نوع پشتیبان به متن فارسی استاندارد.

    مثال::

        >>> compute_mentor_type_str(MentorType.SCHOOL)
        'مدرسه‌ای'

    """

    mapping = {
        MentorType.NORMAL: "عادی",
        MentorType.SCHOOL: "مدرسه‌ای",
    }
    return mapping.get(row_type, "عادی")


# ---------------------------------------------------------------------------
# Join Key
# ---------------------------------------------------------------------------


@final
@dataclass(frozen=True, slots=True)
class JoinKey:
    """
    Six-field join key for matching students to mentor matrix rows.

    Fields: major, gender, status, center, finance, school_code
    """

    major: int
    gender: int
    status: int
    center: int
    finance: int
    school_code: int

    def __repr__(self) -> str:
        """Provide a clear string representation for debugging."""
        return (
            f"JoinKey(major={self.major}, gender={self.gender}, status={self.status}, "
            f"center={self.center}, finance={self.finance}, school_code={self.school_code})"
        )

    @staticmethod
    def from_student_row(row: StudentRow, *, cfg: BuildConfig) -> JoinKey:
        """ساخت کلید الحاق از سطر دانش‌آموز.

        مثال::

            >>> row = {
            ...     "کدرشته": 1,
            ...     "جنسیت": 1,
            ...     "دانش آموز فارغ": 0,
            ...     "مرکز گلستان صدرا": 1,
            ...     "مالی حکمت بنیاد": 0,
            ...     "کد مدرسه": 3581,
            ... }
            >>> JoinKey.from_student_row(row, cfg=BuildConfig())
            JoinKey(major=1, gender=1, status=1, center=1, finance=0, school_code=3581)

        """

        required = {COL_GROUP, COL_GENDER, COL_STATUS, COL_FINANCE}
        missing = [col for col in required if col not in row]
        if missing:
            raise DataMissingError(
                func="JoinKey.from_student_row", column=",".join(missing), value=None
            )

        major = _num_to_int_safe(row.get(COL_GROUP, 0))
        gender = norm_gender(row.get(COL_GENDER, 1))
        status = norm_status(row.get(COL_STATUS, 1))

        center_val = row.get(COL_CENTER, "")
        center = _coerce_center_id(center_val, default_zero=0)
        if center == 0:
            manager_name = row.get(COL_MANAGER, "")
            center = center_from_manager(manager_name, cfg=cfg)

        finance = _coerce_finance(row.get(COL_FINANCE, 0), cfg=cfg)

        school_val = row.get(COL_SCHOOL, "")
        school_str = to_numlike_str(school_val)
        school_code = _num_to_int_safe(school_str) if school_str and school_str != "0" else 0

        return JoinKey(
            major=major,
            gender=gender,
            status=status,
            center=center,
            finance=finance,
            school_code=school_code,
        )

    def as_dict(self) -> JoinKeyDict:
        """
        Convert to dict with Persian column names.

        Returns:
            A mapping: {COL_GROUP: major, COL_GENDER: gender, ...}
        """
        return {
            COL_GROUP: self.major,
            COL_GENDER: self.gender,
            COL_STATUS: self.status,
            COL_CENTER: self.center,
            COL_FINANCE: self.finance,
            COL_SCHOOL: self.school_code,
        }


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


@final
@dataclass(frozen=True, slots=True)
class MentorIdentity:
    """Mentor identity: ID, name, and manager name."""

    mentor_id: str
    mentor_name: str
    manager_name: str

    def __repr__(self) -> str:
        """Provide a clear string representation for debugging."""
        return f"MentorIdentity(mentor_id='{self.mentor_id}', mentor_name='{self.mentor_name}', manager_name='{self.manager_name}')"


@final
@dataclass(frozen=True, slots=True)
class Capacity:
    """
    Mentor capacity tracking.

    Attributes:
        covered_now: Current coverage count
        special_limit: Capacity limit for this mentor
        allocations_new: Number of new allocations made (default 0)
    """

    covered_now: int
    special_limit: int
    allocations_new: int = 0

    def __post_init__(self) -> None:
        """Validate capacity values after initialization."""
        if self.special_limit < 0:
            raise ValueError(f"special_limit must be non-negative, got {self.special_limit}")
        if self.covered_now < 0:
            raise ValueError(f"covered_now must be non-negative, got {self.covered_now}")
        if self.allocations_new < 0:
            raise ValueError(f"allocations_new must be non-negative, got {self.allocations_new}")

    def __repr__(self) -> str:
        """Provide a clear string representation for debugging."""
        return f"Capacity(covered_now={self.covered_now}, special_limit={self.special_limit}, allocations_new={self.allocations_new})"

    def occupancy_ratio(self) -> float:
        """نسبت اشغال فعلی را محاسبه می‌کند."""

        denominator = max(1, int(self.special_limit))
        numerator = max(int(self.covered_now) + int(self.allocations_new), 0)
        return float(numerator) / float(denominator)


@final
@dataclass(frozen=True, slots=True)
class MatrixRow:
    """
    A single row from the eligibility matrix.

    Represents one mentor with their eligibility criteria and metadata.
    """

    alias: str
    mentor: MentorIdentity
    major: int
    gender: int
    status: int
    center: int
    finance: int
    school_code: int
    row_type: MentorType
    mentor_row_id: int | str
    # New field for output schema
    mentor_type_str: str = field(init=False)

    def __post_init__(self) -> None:
        """Calculate mentor_type_str after initialization."""
        object.__setattr__(self, "mentor_type_str", compute_mentor_type_str(self.row_type))

    def __repr__(self) -> str:
        """Provide a clear string representation for debugging."""
        return (
            f"MatrixRow(alias='{self.alias}', mentor={self.mentor}, row_type={self.row_type.value})"
        )


@final
@dataclass(frozen=True, slots=True)
class ImportToSabtRow:
    """
    Output row for import to Sabt system.

    Contains postal code and mentor name for assignment.
    """

    postal_code: str
    mentor_name: str

    def __repr__(self) -> str:
        """Provide a clear string representation for debugging."""
        return (
            f"ImportToSabtRow(postal_code='{self.postal_code}', mentor_name='{self.mentor_name}')"
        )


# ---------------------------------------------------------------------------
# Trace types
# ---------------------------------------------------------------------------

DecisionReason = Literal[
    "no_candidate",
    "capacity_full",
    "gender_mismatch",
    "center_mismatch",
    "school_mismatch",
    "finance_mismatch",
    "status_policy",
]


class TraceDict(TypedDict, total=False):
    """
    Trace dictionary for allocation decisions.

    Required key: 'key' (dict with join keys)
    Optional keys: 'candidates' (int), 'reason' (str), 'top5' (list of mentor dicts)
    """

    key: JoinKeyDict  # Six join keys
    candidates: int
    reason: DecisionReason
    top5: list[MentorDict]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "COL_GROUP",
    "COL_GENDER",
    "COL_STATUS",
    "COL_CENTER",
    "COL_FINANCE",
    "COL_SCHOOL",
    "COL_SCHOOL_NAME",
    "COL_SCHOOL_CODE_1",
    "COL_SCHOOL_CODE_2",
    "COL_SCHOOL_CODE_3",
    "COL_SCHOOL_CODE_4",
    "COL_SCHOOL_NAME_1",
    "COL_SCHOOL_NAME_2",
    "COL_SCHOOL_NAME_3",
    "COL_SCHOOL_NAME_4",
    "COL_FULL_SCHOOL_CODE",
    "COL_EDU_CODE",
    "COL_ALIAS",
    "COL_MENTOR",
    "COL_MANAGER",
    "COL_MENTOR_ID",
    "COL_MENTOR_ROWID",
    "COL_MENTOR_TYPE",
    "MentorType",
    "StudentBindingKind",
    "Status",
    "Gender",
    "FinanceCode",
    "BuildConfig",
    "JoinKey",
    "MentorIdentity",
    "Capacity",
    "MatrixRow",
    "ImportToSabtRow",
    "norm_status",
    "norm_gender",
    "center_from_manager",
    "compute_alias",
    "compute_mentor_type_str",
    "classify_mentor_type_from_school_count",
    "classify_student_binding",
    "school_code_norm",
    "finance_cross",
    "DecisionReason",
    "TraceDict",
    "StudentRow",
    "JoinKeyDict",
    "MentorDict",
]

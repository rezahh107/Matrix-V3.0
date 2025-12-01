"""لایهٔ مرکزی QA برای اینورینت‌های ماتریس و تخصیص."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

import pandas as pd
from pandas.api import types as ptypes

from app.core.allocation.mentor_pool import compute_effective_status
from app.core.canonical_frames import POOL_JOIN_KEY_DUPLICATES_ATTR
from app.core.common.domain import BuildConfig, StudentBindingKind, classify_student_binding
from app.core.common.national_id import canonical_national_code
from app.core.policy_loader import MentorStatus, PolicyConfig

RuleId = str

__all__ = [
    "QaViolation",
    "QaRuleResult",
    "QaReport",
    "run_all_invariants",
    "check_STU_01",
    "check_STU_02",
    "check_STU_BINDING_01",
    "check_JOIN_01",
    "check_POOL_JOIN_01",
    "check_SCHOOL_01",
    "check_MENTOR_TYPE_01",
    "check_GOV_01",
    "check_ALLOC_01",
    "check_HISTORY_CHANNEL_01",
]


def _canonicalize_national_code(value: object) -> str | None:
    return canonical_national_code(value)


@dataclass(frozen=True)
class QaViolation:
    """نمایش یک تخطی از قانون QA.

    Attributes
    ----------
    rule_id:
        شناسهٔ پایدار قانون (مثلاً ``"QA_RULE_STU_01"``).
    level:
        سطح تخطی؛ در این نسخه فقط ``"error"`` پشتیبانی می‌شود.
    message:
        توضیح خوانا از علت تخطی.
    details:
        دادهٔ ساخت‌یافتهٔ اختیاری برای گزارش‌های اکسل/لاگ.
    """

    rule_id: RuleId
    level: str
    message: str
    details: Mapping[str, object] | None = None


@dataclass(frozen=True)
class QaRuleResult:
    """نتیجهٔ اجرای یک قانون واحد QA."""

    rule_id: RuleId
    passed: bool
    violations: list[QaViolation]


@dataclass
class QaReport:
    """گزارش نهایی QA برای یک نوبت ساخت/تخصیص."""

    results: list[QaRuleResult]
    extras: Mapping[str, pd.DataFrame] | None = None

    @property
    def violations(self) -> list[QaViolation]:
        """تمام تخطی‌ها را در یک لیست مسطح برمی‌گرداند."""

        merged: list[QaViolation] = []
        for result in self.results:
            merged.extend(result.violations)
        return merged

    @property
    def passed(self) -> bool:
        """آیا تمام قوانین بدون تخطی عبور کرده‌اند؟"""

        return all(result.passed for result in self.results)

    def violations_by_rule(self, rule_id: RuleId) -> list[QaViolation]:
        """لیست تخطی‌های مربوط به یک قانون مشخص را برمی‌گرداند."""

        return [
            violation
            for result in self.results
            if result.rule_id == rule_id
            for violation in result.violations
        ]

    def to_summary_frame(self, *, descriptions: Mapping[str, str] | None = None) -> pd.DataFrame:
        """خلاصهٔ قوانین را به‌صورت DataFrame برمی‌گرداند.

        Parameters
        ----------
        descriptions:
            نقشهٔ اختیاری ``rule_id`` به توضیح خوانا برای نمایش در گزارش.
        """

        descriptions = descriptions or {}
        rows = []
        for result in sorted(self.results, key=lambda item: item.rule_id):
            rows.append(
                {
                    "rule_id": result.rule_id,
                    "description": descriptions.get(result.rule_id, ""),
                    "status": "PASS" if result.passed else "FAIL",
                    "violations_count": len(result.violations),
                }
            )
        return pd.DataFrame(rows)

    def to_details_frame(self, rule_id: RuleId) -> pd.DataFrame:
        """تبدیل تخطی‌های یک قانون به DataFrame ساخت‌یافته."""

        violations = self.violations_by_rule(rule_id)
        base_columns = ["rule_id", "level", "message"]
        rows: list[dict[str, object]] = []
        detail_keys: set[str] = set()
        for violation in violations:
            detail_map = violation.details or {}
            detail_keys.update(detail_map.keys())
            row: dict[str, object] = {
                "rule_id": violation.rule_id,
                "level": violation.level,
                "message": violation.message,
            }
            row.update(detail_map)
            rows.append(row)

        ordered_columns = base_columns + sorted(detail_keys)
        frame = pd.DataFrame(rows, columns=ordered_columns)
        if not frame.empty:
            sort_keys = [
                col for col in ordered_columns if col in frame.columns and col not in {"message"}
            ]
            if sort_keys:
                frame = frame.sort_values(by=sort_keys, kind="stable").reset_index(drop=True)
        return frame


def run_all_invariants(
    *,
    policy: PolicyConfig,
    matrix: pd.DataFrame | None = None,
    allocation: pd.DataFrame | None = None,
    student_report: pd.DataFrame | None = None,
    inspactor: pd.DataFrame | None = None,
    invalid_mentors: pd.DataFrame | None = None,
    allocation_summary: pd.DataFrame | None = None,
    governance_overrides: Mapping[int | str | float, bool] | None = None,
    pool: pd.DataFrame | None = None,
    extras: Mapping[str, pd.DataFrame] | None = None,
    history_info: pd.DataFrame | None = None,
) -> QaReport:
    """اجرای همهٔ قوانین QA و تولید گزارش تجمیعی.

    مثال ساده
    ---------
    >>> import pandas as pd
    >>> from app.core.policy_loader import load_policy
    >>> policy = load_policy()
    >>> matrix = pd.DataFrame({"کدرشته": [1201], "جنسیت": [1], "دانش آموز فارغ": [0],
    ... "مرکز گلستان صدرا": [0], "مالی حکمت بنیاد": [0], "کد مدرسه": [1010],
    ... "has_school_constraint": [False]})
    >>> report = run_all_invariants(policy=policy, matrix=matrix)
    >>> report.passed
    True
    """

    checks = [
        check_STU_01(
            matrix=matrix,
            allocation=allocation,
            student_report=student_report,
        ),
        check_STU_02(allocation=allocation, inspactor=inspactor),
        check_STU_BINDING_01(student_report=student_report, policy=policy),
        check_JOIN_01(matrix=matrix, policy=policy),
        check_MENTOR_TYPE_01(matrix=matrix, policy=policy),
        check_SCHOOL_01(matrix=matrix, invalid_mentors=invalid_mentors, policy=policy),
        check_GOV_01(
            allocation=allocation,
            allocation_summary=allocation_summary,
            policy=policy,
            overrides=governance_overrides,
        ),
        check_ALLOC_01(
            allocation=allocation,
            allocation_summary=allocation_summary,
            policy=policy,
        ),
        check_HISTORY_CHANNEL_01(history_info=history_info),
    ]
    pool_result, pool_conflicts = check_POOL_JOIN_01(pool=pool, policy=policy)
    checks.append(pool_result)

    extra_frames: dict[str, pd.DataFrame] = dict(extras or {})
    extra_frames.setdefault("pool_join_conflicts", pool_conflicts)
    return QaReport(results=checks, extras=extra_frames if extra_frames else None)


def _resolve_student_count(frame: pd.DataFrame | None) -> int | None:
    if frame is None:
        return None
    if "student_id" in frame.columns:
        return int(frame["student_id"].notna().sum())
    return int(len(frame))


def _resolve_mentor_column(frame: pd.DataFrame | None) -> str | None:
    if frame is None:
        return None
    candidates = (
        "mentor_id",
        "کد کارمندی پشتیبان",
        "mentor_code",
    )
    for name in candidates:
        if name in frame.columns:
            return name
    return None


def check_STU_01(  # noqa: N802
    *,
    matrix: pd.DataFrame | None,
    allocation: pd.DataFrame | None,
    student_report: pd.DataFrame | None,
) -> QaRuleResult:
    """QA_RULE_STU_01 — هم‌خوانی تعداد دانش‌آموز در همهٔ خروجی‌ها."""

    counts = {
        "student_report": _resolve_student_count(student_report),
        "matrix": _resolve_student_count(matrix),
        "allocation": _resolve_student_count(allocation),
    }
    known_counts = {k: v for k, v in counts.items() if v is not None}

    violations: list[QaViolation] = []
    if len(set(known_counts.values())) > 1:
        violations.append(
            QaViolation(
                rule_id="QA_RULE_STU_01",
                level="error",
                message="عدم تطابق تعداد دانش‌آموز بین خروجی‌ها",
                details=known_counts,
            )
        )

    return QaRuleResult(
        rule_id="QA_RULE_STU_01",
        passed=not violations,
        violations=violations,
    )


def check_STU_02(  # noqa: N802
    *,
    allocation: pd.DataFrame | None,
    inspactor: pd.DataFrame | None,
) -> QaRuleResult:
    """QA_RULE_STU_02 — شمار دانش‌آموز به ازای هر منتور مطابق Inspactor/Allocation."""

    mentor_col = _resolve_mentor_column(inspactor) or _resolve_mentor_column(allocation)
    if mentor_col is None or allocation is None or inspactor is None:
        return QaRuleResult("QA_RULE_STU_02", True, [])

    expected_col_candidates: Sequence[str] = (
        "expected_student_count",
        "student_count",
        "students_count",
    )
    expected_col = next((c for c in expected_col_candidates if c in inspactor.columns), None)
    if expected_col is None:
        return QaRuleResult("QA_RULE_STU_02", True, [])

    expected_counts = (
        pd.to_numeric(inspactor[mentor_col], errors="coerce")
        .to_frame("mentor_id")
        .assign(expected=inspactor[expected_col])
        .dropna()
    )
    expected_counts["expected"] = pd.to_numeric(expected_counts["expected"], errors="coerce")
    expected_counts = expected_counts.groupby("mentor_id", as_index=False)["expected"].sum()

    alloc_counts = (
        pd.to_numeric(allocation[mentor_col], errors="coerce")
        .to_frame("mentor_id")
        .dropna()
        .groupby("mentor_id", as_index=False)
        .size()
        .rename(columns={"size": "assigned"})
    )

    merged = expected_counts.merge(alloc_counts, on="mentor_id", how="left").fillna({"assigned": 0})
    mismatches = merged[merged["expected"] != merged["assigned"]]

    violations: list[QaViolation] = []
    for _, row in mismatches.iterrows():
        violations.append(
            QaViolation(
                rule_id="QA_RULE_STU_02",
                level="error",
                message="اختلاف شمارش دانش‌آموز برای منتور",
                details={
                    "mentor_id": int(row["mentor_id"]),
                    "expected": int(row["expected"]),
                    "assigned": int(row["assigned"]),
                },
            )
        )

    return QaRuleResult(
        rule_id="QA_RULE_STU_02",
        passed=not violations,
        violations=violations,
    )


def check_STU_BINDING_01(  # noqa: N802
    *, student_report: pd.DataFrame | None, policy: PolicyConfig
) -> QaRuleResult:
    """QA_RULE_STU_BINDING_01 — هم‌خوانی Rule STUDENT-TYPE-01 با دادهٔ دانش‌آموز."""

    violations: list[QaViolation] = []
    if student_report is None:
        return QaRuleResult("QA_RULE_STU_BINDING_01", True, violations)

    try:
        status_column = policy.stage_column("graduation_status")
    except KeyError:
        return QaRuleResult("QA_RULE_STU_BINDING_01", True, violations)

    school_column = policy.columns.school_code
    missing_columns = [
        column for column in (status_column, school_column) if column not in student_report.columns
    ]
    if missing_columns:
        violations.append(
            QaViolation(
                rule_id="QA_RULE_STU_BINDING_01",
                level="error",
                message="ستون‌های لازم برای قانون STUDENT-TYPE-01 موجود نیست",
                details={"missing_columns": tuple(sorted(missing_columns))},
            )
        )
        return QaRuleResult("QA_RULE_STU_BINDING_01", False, violations)

    cfg = BuildConfig(policy=policy)
    bindings = student_report.apply(
        lambda row: classify_student_binding(row, cfg=cfg), axis=1
    ).reset_index(drop=True)

    allowed_bindings = {StudentBindingKind.NORMAL, StudentBindingKind.SCHOOL}
    legacy_mask = bindings == StudentBindingKind.MENTOR_BASED
    unexpected_mask = ~bindings.isin(allowed_bindings | {StudentBindingKind.MENTOR_BASED})
    if bool(legacy_mask.any()):
        violations.append(
            QaViolation(
                rule_id="QA_RULE_STU_BINDING_01",
                level="error",
                message="وضعیت legacy برای student binding مشاهده شد",
                details={"legacy_rows": tuple(student_report.index[legacy_mask].tolist())},
            )
        )

    if bool(unexpected_mask.any()):
        violations.append(
            QaViolation(
                rule_id="QA_RULE_STU_BINDING_01",
                level="error",
                message="مقدار نامعتبر برای student binding مشاهده شد",
                details={"invalid_rows": tuple(student_report.index[unexpected_mask].tolist())},
            )
        )

    return QaRuleResult(
        rule_id="QA_RULE_STU_BINDING_01",
        passed=not violations,
        violations=violations,
    )


def check_JOIN_01(  # noqa: N802
    *, matrix: pd.DataFrame | None, policy: PolicyConfig
) -> QaRuleResult:
    """QA_RULE_JOIN_01 — سلامت ۶ کلید join در ماتریس."""

    violations: list[QaViolation] = []
    if matrix is None:
        return QaRuleResult("QA_RULE_JOIN_01", True, violations)

    missing = [key for key in policy.join_keys if key not in matrix.columns]
    if missing:
        violations.append(
            QaViolation(
                rule_id="QA_RULE_JOIN_01",
                level="error",
                message="ستون‌های join در ماتریس ناقص است",
                details={"missing_columns": tuple(missing)},
            )
        )
        return QaRuleResult("QA_RULE_JOIN_01", False, violations)

    for key in policy.join_keys:
        series = matrix[key]
        if series.isna().any():
            violations.append(
                QaViolation(
                    rule_id="QA_RULE_JOIN_01",
                    level="error",
                    message=f"مقدار خالی در ستون join '{key}'",
                    details={"null_rows": int(series.isna().sum())},
                )
            )
        if not ptypes.is_integer_dtype(series):
            violations.append(
                QaViolation(
                    rule_id="QA_RULE_JOIN_01",
                    level="error",
                    message=f"ستون join '{key}' باید نوع عددی صحیح داشته باشد",
                    details={"dtype": str(series.dtype)},
                )
            )

    return QaRuleResult(
        rule_id="QA_RULE_JOIN_01",
        passed=not violations,
        violations=violations,
    )


def _normalize_str(value: object) -> str:
    if value is None or value is pd.NA:
        return ""
    text = str(value).strip()
    return text


def check_MENTOR_TYPE_01(  # noqa: N802
    *, matrix: pd.DataFrame | None, policy: PolicyConfig
) -> QaRuleResult:
    """QA_RULE_MENTOR_TYPE_01 — اعتبارسنجی نوع منتور و alias."""

    violations: list[QaViolation] = []
    if matrix is None:
        return QaRuleResult("QA_RULE_MENTOR_TYPE_01", True, violations)

    mentor_col = _resolve_mentor_column(matrix)
    required_columns = {
        "جایگزین",
        policy.columns.school_code,
        "عادی مدرسه",
    }
    missing_columns = [col for col in required_columns if col not in matrix.columns]
    if mentor_col is None:
        missing_columns.append("mentor_id")
    if missing_columns:
        violations.append(
            QaViolation(
                rule_id="QA_RULE_MENTOR_TYPE_01",
                level="error",
                message="ستون‌های لازم برای قانون منتور نوع موجود نیست",
                details={"missing_columns": tuple(sorted(missing_columns))},
            )
        )
        return QaRuleResult("QA_RULE_MENTOR_TYPE_01", False, violations)

    type_col = "عادی مدرسه"
    allowed_types = {"عادی", "مدرسه‌ای"}
    invalid_types = matrix.loc[~matrix[type_col].isin(allowed_types)]
    if not invalid_types.empty:
        violations.append(
            QaViolation(
                rule_id="QA_RULE_MENTOR_TYPE_01",
                level="error",
                message="مقدار نامعتبر در ستون نوع منتور",
                details={"rows": tuple(invalid_types.index.tolist())},
            )
        )

    mentor_values = matrix[mentor_col].astype("string").str.strip()
    type_counts = (
        matrix.assign(_mentor=mentor_values)
        .groupby("_mentor", dropna=True)[type_col]
        .nunique(dropna=True)
    )
    dual_ids = [mentor for mentor, count in type_counts.items() if mentor and count > 1]
    if dual_ids:
        violations.append(
            QaViolation(
                rule_id="QA_RULE_MENTOR_TYPE_01",
                level="error",
                message="منتور نباید همزمان عادی و مدرسه‌ای باشد",
                details={"mentor_ids": tuple(dual_ids)},
            )
        )

    school_col = policy.columns.school_code
    normal_rows = matrix[type_col] == "عادی"
    normal_with_school = matrix.loc[normal_rows, school_col].fillna(0).astype(int) != 0
    if bool(normal_with_school.any()):
        offenders = matrix.loc[normal_rows & normal_with_school, mentor_col].tolist()
        violations.append(
            QaViolation(
                rule_id="QA_RULE_MENTOR_TYPE_01",
                level="error",
                message="سطر عادی نباید کد مدرسه غیرصفر داشته باشد",
                details={"mentor_ids": tuple(_normalize_str(v) for v in offenders)},
            )
        )

    school_rows = matrix[type_col] == "مدرسه‌ای"
    school_with_zero = matrix.loc[school_rows, school_col].fillna(0).astype(int) == 0
    if bool(school_with_zero.any()):
        offenders = matrix.loc[school_rows & school_with_zero, mentor_col].tolist()
        violations.append(
            QaViolation(
                rule_id="QA_RULE_MENTOR_TYPE_01",
                level="error",
                message="سطر مدرسه‌ای بدون کد مدرسه معتبر",
                details={"mentor_ids": tuple(_normalize_str(v) for v in offenders)},
            )
        )

    alias_series = matrix.loc[school_rows, "جایگزین"].astype("string").str.strip()
    mentor_series = matrix.loc[school_rows, mentor_col].astype("string").str.strip()
    alias_mismatch_mask = alias_series.ne(mentor_series)
    if bool(alias_mismatch_mask.any()):
        offenders = matrix.loc[school_rows, :].loc[alias_mismatch_mask, mentor_col].tolist()
        violations.append(
            QaViolation(
                rule_id="QA_RULE_MENTOR_TYPE_01",
                level="error",
                message="alias مدرسه‌ای باید برابر mentor_id باشد",
                details={"mentor_ids": tuple(_normalize_str(v) for v in offenders)},
            )
        )

    normal_alias_missing = matrix.loc[normal_rows, "جایگزین"].astype("string").str.strip() == ""
    if bool(normal_alias_missing.any()):
        offenders = matrix.loc[normal_rows & normal_alias_missing, mentor_col].tolist()
        violations.append(
            QaViolation(
                rule_id="QA_RULE_MENTOR_TYPE_01",
                level="error",
                message="سطر عادی بدون alias معتبر",
                details={"mentor_ids": tuple(_normalize_str(v) for v in offenders)},
            )
        )

    return QaRuleResult(
        rule_id="QA_RULE_MENTOR_TYPE_01",
        passed=not violations,
        violations=violations,
    )


def _sorted_int_values(series: pd.Series) -> tuple[int, ...]:
    numeric = pd.to_numeric(series, errors="coerce").dropna().astype(int)
    return tuple(sorted(numeric.unique().tolist()))


def _build_pool_join_duplicates(pool: pd.DataFrame, policy: PolicyConfig) -> pd.DataFrame:
    mentor_col = _resolve_mentor_column(pool)
    if mentor_col is None:
        return pd.DataFrame(columns=[*policy.join_keys, "duplicate_group_size", "mentor_id"])

    existing_report = pool.attrs.get(POOL_JOIN_KEY_DUPLICATES_ATTR)
    if isinstance(existing_report, pd.DataFrame):
        expected_columns = set(policy.join_keys) | {mentor_col, "duplicate_group_size"}
        if expected_columns.issubset(set(existing_report.columns)):
            return existing_report.copy()

    required_columns = [mentor_col] + [col for col in policy.join_keys if col in pool.columns]
    normalized = pool.loc[:, required_columns].copy()
    normalized[mentor_col] = normalized[mentor_col].astype("string").str.strip()
    normalized = normalized[normalized[mentor_col].ne("")]
    for column in policy.join_keys:
        if column in normalized.columns:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce").astype("Int64")

    duplicate_mask = normalized.duplicated(subset=[mentor_col, *policy.join_keys], keep=False)
    if not bool(duplicate_mask.any()):
        return pd.DataFrame(columns=[*policy.join_keys, "duplicate_group_size", mentor_col])

    duplicate_rows = normalized.loc[duplicate_mask, [*policy.join_keys, mentor_col]].copy()
    duplicate_rows["duplicate_group_size"] = (
        duplicate_rows.groupby([mentor_col, *policy.join_keys], sort=False)[mentor_col]
        .transform("size")
        .astype("Int64")
    )
    return duplicate_rows.sort_values([mentor_col, *policy.join_keys], kind="stable").reset_index(
        drop=True
    )


def check_POOL_JOIN_01(  # noqa: N802
    *, pool: pd.DataFrame | None, policy: PolicyConfig
) -> tuple[QaRuleResult, pd.DataFrame]:
    """QA_RULE_POOL_JOIN_01 — ردیف تکراری روی کلید ترکیبی mentor_id و کلیدهای اتصال."""

    if pool is None:
        empty = pd.DataFrame(columns=[*policy.join_keys, "duplicate_group_size", "mentor_id"])
        return QaRuleResult("QA_RULE_POOL_JOIN_01", True, []), empty

    conflicts = _build_pool_join_duplicates(pool, policy)
    violations: list[QaViolation] = []
    if not conflicts.empty:
        mentor_col = _resolve_mentor_column(conflicts) or "mentor_id"
        join_key_columns = [col for col in policy.join_keys if col in conflicts.columns]
        grouping_columns = [mentor_col, *join_key_columns]
        violations.append(
            QaViolation(
                rule_id="QA_RULE_POOL_JOIN_01",
                level="error",
                message="ردیف تکراری روی کلید ترکیبی mentor_id و کلیدهای اتصال در استخر",
                details={
                    "duplicate_groups": int(conflicts[grouping_columns].drop_duplicates().shape[0]),
                    "duplicate_rows": int(len(conflicts)),
                },
            )
        )

    result = QaRuleResult(
        rule_id="QA_RULE_POOL_JOIN_01", passed=not violations, violations=violations
    )
    return result, conflicts


def check_SCHOOL_01(  # noqa: N802
    *,
    matrix: pd.DataFrame | None,
    invalid_mentors: pd.DataFrame | None,
    policy: PolicyConfig,
) -> QaRuleResult:
    """QA_RULE_SCHOOL_01 — تمایز منتورهای آزاد و مقید به مدرسه."""

    violations: list[QaViolation] = []
    if matrix is None:
        return QaRuleResult("QA_RULE_SCHOOL_01", True, violations)

    if "has_school_constraint" not in matrix.columns:
        violations.append(
            QaViolation(
                rule_id="QA_RULE_SCHOOL_01",
                level="error",
                message="ستون has_school_constraint در ماتریس موجود نیست",
            )
        )
        return QaRuleResult("QA_RULE_SCHOOL_01", False, violations)

    mentor_col = _resolve_mentor_column(matrix)
    invalid_ids: set[int] = set()
    if invalid_mentors is not None:
        invalid_col = _resolve_mentor_column(invalid_mentors)
        if invalid_col and invalid_col in invalid_mentors.columns:
            invalid_ids = set(
                pd.to_numeric(invalid_mentors[invalid_col], errors="coerce")
                .dropna()
                .astype(int)
                .tolist()
            )

    unrestricted_mask = matrix["has_school_constraint"] == False  # noqa: E712
    if mentor_col and invalid_ids:
        unrestricted_ids = set(
            pd.to_numeric(matrix.loc[unrestricted_mask, mentor_col], errors="coerce")
            .dropna()
            .astype(int)
            .tolist()
        )
        leaked = sorted(unrestricted_ids.intersection(invalid_ids))
        if leaked:
            violations.append(
                QaViolation(
                    rule_id="QA_RULE_SCHOOL_01",
                    level="error",
                    message="منتور آزاد در لیست خطای مدرسه دیده شده است",
                    details={"mentor_ids": tuple(leaked)},
                )
            )

    restricted_mask = matrix["has_school_constraint"] == True  # noqa: E712
    school_col = policy.columns.school_code
    if restricted_mask.any():
        restricted_rows = matrix.loc[restricted_mask]
        missing_school = restricted_rows[school_col].isna() | (
            pd.to_numeric(restricted_rows[school_col], errors="coerce").fillna(0).eq(0)
        )
        if missing_school.any():
            offenders: Iterable[int] = ()
            if mentor_col:
                offenders = (
                    pd.to_numeric(restricted_rows.loc[missing_school, mentor_col], errors="coerce")
                    .dropna()
                    .astype(int)
                    .tolist()
                )
            violations.append(
                QaViolation(
                    rule_id="QA_RULE_SCHOOL_01",
                    level="error",
                    message="منتور مقید مدرسه بدون کد مدرسه معتبر",
                    details={"mentor_ids": tuple(offenders)},
                )
            )

    return QaRuleResult(
        rule_id="QA_RULE_SCHOOL_01",
        passed=not violations,
        violations=violations,
    )


def check_GOV_01(  # noqa: N802
    *,
    allocation: pd.DataFrame | None,
    allocation_summary: pd.DataFrame | None,
    policy: PolicyConfig,
    overrides: Mapping[int | str | float, bool] | None = None,
) -> QaRuleResult:
    """QA_RULE_GOV_01 — حذف منتورهای غیرفعال از تخصیص."""

    violations: list[QaViolation] = []
    if allocation is None:
        return QaRuleResult("QA_RULE_GOV_01", True, violations)

    mentor_col = _resolve_mentor_column(allocation) or _resolve_mentor_column(allocation_summary)
    if mentor_col is None:
        return QaRuleResult("QA_RULE_GOV_01", True, violations)

    governance = policy.mentor_pool_governance

    allocated_ids = (
        pd.to_numeric(allocation[mentor_col], errors="coerce").dropna().astype(int).unique()
    )
    if allocated_ids.size == 0:
        return QaRuleResult("QA_RULE_GOV_01", True, violations)

    mentors_df = pd.DataFrame({"mentor_id": allocated_ids})
    statuses = compute_effective_status(mentors_df, governance, overrides)

    for mentor_id, status in zip(allocated_ids, statuses):
        if status != MentorStatus.ACTIVE:
            violations.append(
                QaViolation(
                    rule_id="QA_RULE_GOV_01",
                    level="error",
                    message="منتور غیرفعال در تخصیص دیده شد",
                    details={"mentor_id": int(mentor_id), "status": status.value},
                )
            )

    return QaRuleResult(rule_id="QA_RULE_GOV_01", passed=not violations, violations=violations)


def check_ALLOC_01(  # noqa: N802
    *,
    allocation: pd.DataFrame | None,
    allocation_summary: pd.DataFrame | None,
    policy: PolicyConfig,
) -> QaRuleResult:
    """QA_RULE_ALLOC_01 — ظرفیت و نسبت اشغال منتورها در تخصیص."""

    violations: list[QaViolation] = []
    if allocation is None or allocation_summary is None:
        return QaRuleResult("QA_RULE_ALLOC_01", True, violations)

    mentor_col = _resolve_mentor_column(allocation_summary) or _resolve_mentor_column(allocation)
    if mentor_col is None:
        return QaRuleResult("QA_RULE_ALLOC_01", True, violations)

    assigned = (
        pd.to_numeric(allocation[mentor_col], errors="coerce").dropna().astype(int).value_counts()
    )

    summary = allocation_summary.copy()
    summary["__mentor"] = pd.to_numeric(summary[mentor_col], errors="coerce")
    summary = summary.dropna(subset=["__mentor"])
    summary["__mentor"] = summary["__mentor"].astype(int)

    remaining_col = policy.columns.remaining_capacity
    alloc_new_col = "allocations_new"

    for _, row in summary.iterrows():
        mentor_id = int(row["__mentor"])
        assigned_count = int(assigned.get(mentor_id, 0))
        remaining = float(pd.to_numeric(row.get(remaining_col, 0), errors="coerce"))
        alloc_new = float(pd.to_numeric(row.get(alloc_new_col, assigned_count), errors="coerce"))

        if assigned_count > remaining + alloc_new + 1e-9:
            violations.append(
                QaViolation(
                    rule_id="QA_RULE_ALLOC_01",
                    level="error",
                    message="تخصیص بیش از ظرفیت منتور",
                    details={
                        "mentor_id": mentor_id,
                        "assigned": assigned_count,
                        "remaining": remaining,
                        "allocations_new": alloc_new,
                    },
                )
            )

    return QaRuleResult(
        rule_id="QA_RULE_ALLOC_01",
        passed=not violations,
        violations=violations,
    )


def check_HISTORY_CHANNEL_01(*, history_info: pd.DataFrame | None) -> QaRuleResult:  # noqa: N802
    """QA_RULE_HISTORY_CHANNEL_01 — کلید تاریخچه باید کاننیکال و یکتا باشد."""

    if history_info is None or history_info.empty:
        return QaRuleResult("QA_RULE_HISTORY_CHANNEL_01", True, [])

    violations: list[QaViolation] = []
    frame = history_info.copy()
    if "allocation_channel" in frame.columns:
        frame["allocation_channel"] = (
            frame["allocation_channel"].astype("string").str.upper().str.strip()
        )

    national_col: str | None = None
    for candidate in ("national_code", "کد ملی"):
        if candidate in frame.columns:
            national_col = candidate
            frame[national_col] = frame[national_col].map(_canonicalize_national_code)
            break

    if national_col is None:
        return QaRuleResult("QA_RULE_HISTORY_CHANNEL_01", True, [])

    missing = frame[national_col].isna()
    if bool(missing.any()):
        violations.append(
            QaViolation(
                rule_id="QA_RULE_HISTORY_CHANNEL_01",
                level="error",
                message="کد ملی تاریخچه نامعتبر یا خالی است",
                details={"invalid_rows": int(missing.sum())},
            )
        )

    key_cols = [national_col]
    if "allocation_channel" in frame.columns:
        key_cols.append("allocation_channel")
    duplicates = frame.dropna(subset=key_cols).duplicated(subset=key_cols, keep=False)
    if bool(duplicates.any()):
        violations.append(
            QaViolation(
                rule_id="QA_RULE_HISTORY_CHANNEL_01",
                level="error",
                message="کلید تاریخچه (کد ملی/کانال) یکتا نیست",
                details={"duplicate_rows": int(duplicates.sum())},
            )
        )

    return QaRuleResult(
        rule_id="QA_RULE_HISTORY_CHANNEL_01",
        passed=not violations,
        violations=violations,
    )

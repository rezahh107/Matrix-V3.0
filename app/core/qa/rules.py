from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from app.core.common.columns import CANON_EN_TO_FA
from app.core.debug.models import QADebugContext
from app.core.qa.law_mapping import LawMapping, all_law_mappings

RuleId = str

QA_RULE_STU_01 = "QA_RULE_STU_01"
QA_RULE_STU_02 = "QA_RULE_STU_02"
QA_RULE_STU_BINDING_01 = "QA_RULE_STU_BINDING_01"
QA_RULE_JOIN_01 = "QA_RULE_JOIN_01"
QA_RULE_MENTOR_TYPE_01 = "QA_RULE_MENTOR_TYPE_01"
QA_RULE_POOL_JOIN_01 = "QA_RULE_POOL_JOIN_01"
QA_RULE_SCHOOL_01 = "QA_RULE_SCHOOL_01"
QA_RULE_GOV_01 = "QA_RULE_GOV_01"
QA_RULE_ALLOC_01 = "QA_RULE_ALLOC_01"
QA_RULE_HISTORY_CHANNEL_01 = "QA_RULE_HISTORY_CHANNEL_01"
QA_RULE_STATUS_DOMAIN_01 = "QA_RULE_STATUS_DOMAIN_01"

QA_RULE_IDS: tuple[RuleId, ...] = (
    QA_RULE_STU_01,
    QA_RULE_STU_02,
    QA_RULE_STU_BINDING_01,
    QA_RULE_JOIN_01,
    QA_RULE_MENTOR_TYPE_01,
    QA_RULE_POOL_JOIN_01,
    QA_RULE_SCHOOL_01,
    QA_RULE_GOV_01,
    QA_RULE_ALLOC_01,
    QA_RULE_HISTORY_CHANNEL_01,
    QA_RULE_STATUS_DOMAIN_01,
)

__all__ = [
    "RuleId",
    "QaRuleDefinition",
    "QA_RULE_IDS",
    "QA_RULE_STU_01",
    "QA_RULE_STU_02",
    "QA_RULE_STU_BINDING_01",
    "QA_RULE_JOIN_01",
    "QA_RULE_MENTOR_TYPE_01",
    "QA_RULE_POOL_JOIN_01",
    "QA_RULE_SCHOOL_01",
    "QA_RULE_GOV_01",
    "QA_RULE_ALLOC_01",
    "QA_RULE_HISTORY_CHANNEL_01",
    "QA_RULE_STATUS_DOMAIN_01",
    "get_rule_definitions",
]


_GROUP_CODE = CANON_EN_TO_FA["group_code"]
_GENDER = CANON_EN_TO_FA["gender"]
_GRADUATION_STATUS = CANON_EN_TO_FA["graduation_status"]
_CENTER = CANON_EN_TO_FA["center"]
_FINANCE = CANON_EN_TO_FA["finance"]
_SCHOOL_CODE = CANON_EN_TO_FA["school_code"]


@dataclass(frozen=True)
class QaRuleDefinition:
    """Metadata required for QA rule observability."""

    rule_id: RuleId
    title: str
    law_mapping: LawMapping
    debug_context: QADebugContext


def _frozen_thresholds(values: Mapping[str, float]) -> Mapping[str, float]:
    return MappingProxyType(dict(values))


def get_rule_definitions() -> dict[RuleId, QaRuleDefinition]:
    """Return immutable definitions for all QA rules."""

    mappings = all_law_mappings()
    return {
        QA_RULE_STU_01: QaRuleDefinition(
            rule_id=QA_RULE_STU_01,
            title="هم‌خوانی تعداد دانش‌آموز در خروجی‌ها",
            law_mapping=mappings[QA_RULE_STU_01],
            debug_context=QADebugContext.from_sequences(
                important_columns=("student_id",),
                source_tables=("matrix", "allocation", "student_report"),
                lineage_keys=("student_id",),
                diagnosis_hints=(
                    "مطابق‌شدن شمار دانش‌آموز در ماتریس، تخصیص و گزارش دانش‌آموز را بررسی کنید.",
                ),
                canary_thresholds=_frozen_thresholds({}),
            ),
        ),
        QA_RULE_STU_02: QaRuleDefinition(
            rule_id=QA_RULE_STU_02,
            title="شمار دانش‌آموز به ازای هر منتور",
            law_mapping=mappings[QA_RULE_STU_02],
            debug_context=QADebugContext.from_sequences(
                important_columns=("mentor_id", "expected_student_count"),
                source_tables=("allocation", "inspactor"),
                lineage_keys=("mentor_id",),
                diagnosis_hints=(
                    "مقادیر ستون expected_student_count یا student_count در Inspactor را با تخصیص مقایسه کنید.",
                ),
                canary_thresholds=_frozen_thresholds({}),
            ),
        ),
        QA_RULE_STU_BINDING_01: QaRuleDefinition(
            rule_id=QA_RULE_STU_BINDING_01,
            title="هم‌خوانی Rule STUDENT-TYPE-01 با دادهٔ دانش‌آموز",
            law_mapping=mappings[QA_RULE_STU_BINDING_01],
            debug_context=QADebugContext.from_sequences(
                important_columns=("student_binding", _CENTER, _FINANCE),
                source_tables=("student_report",),
                lineage_keys=("student_id",),
                diagnosis_hints=(
                    "ستون‌های مالی و مرکز گلستان صدرا را با سیاست نوع دانش‌آموز تطبیق دهید.",
                ),
                canary_thresholds=_frozen_thresholds({}),
            ),
        ),
        QA_RULE_JOIN_01: QaRuleDefinition(
            rule_id=QA_RULE_JOIN_01,
            title="سلامت ۶ کلید join در ماتریس",
            law_mapping=mappings[QA_RULE_JOIN_01],
            debug_context=QADebugContext.from_sequences(
                important_columns=(
                    _GROUP_CODE,
                    _GENDER,
                    _GRADUATION_STATUS,
                    _CENTER,
                    _FINANCE,
                    _SCHOOL_CODE,
                ),
                source_tables=("matrix",),
                lineage_keys=(
                    _GROUP_CODE,
                    _GENDER,
                    _GRADUATION_STATUS,
                    _CENTER,
                    _FINANCE,
                    _SCHOOL_CODE,
                ),
                diagnosis_hints=(
                    "ستون‌های join باید کامل، غیرخالی و از نوع int باشند؛ مقدار null یا dtype اشتباه را اصلاح کنید.",
                ),
                canary_thresholds=_frozen_thresholds({}),
            ),
        ),
        QA_RULE_MENTOR_TYPE_01: QaRuleDefinition(
            rule_id=QA_RULE_MENTOR_TYPE_01,
            title="اعتبارسنجی نوع منتور و alias",
            law_mapping=mappings[QA_RULE_MENTOR_TYPE_01],
            debug_context=QADebugContext.from_sequences(
                important_columns=("mentor_id", "جایگزین", "عادی مدرسه", _SCHOOL_CODE),
                source_tables=("matrix",),
                lineage_keys=("mentor_id", _SCHOOL_CODE),
                diagnosis_hints=(
                    "منتور نباید همزمان عادی و مدرسه‌ای باشد و alias باید با school_code هم‌راستا باشد.",
                ),
                canary_thresholds=_frozen_thresholds({}),
            ),
        ),
        QA_RULE_POOL_JOIN_01: QaRuleDefinition(
            rule_id=QA_RULE_POOL_JOIN_01,
            title="ردیف تکراری در استخر منتور",
            law_mapping=mappings[QA_RULE_POOL_JOIN_01],
            debug_context=QADebugContext.from_sequences(
                important_columns=("mentor_id", "POOL_JOIN_KEY"),
                source_tables=("pool",),
                lineage_keys=("mentor_id",),
                diagnosis_hints=(
                    "کلید ترکیبی mentor_id و ۶ کلید join باید یکتا باشد؛ ردیف‌های تکراری را حذف کنید.",
                ),
                canary_thresholds=_frozen_thresholds({}),
            ),
        ),
        QA_RULE_SCHOOL_01: QaRuleDefinition(
            rule_id=QA_RULE_SCHOOL_01,
            title="تمایز منتورهای آزاد و مقید به مدرسه",
            law_mapping=mappings[QA_RULE_SCHOOL_01],
            debug_context=QADebugContext.from_sequences(
                important_columns=("mentor_id", _SCHOOL_CODE, "has_school_constraint"),
                source_tables=("matrix", "invalid_mentors"),
                lineage_keys=("mentor_id", _SCHOOL_CODE),
                diagnosis_hints=(
                    "منتور مدرسه‌ای باید به همان مدرسه تخصیص یابد و منتور آزاد نباید constraint داشته باشد.",
                ),
                canary_thresholds=_frozen_thresholds({}),
            ),
        ),
        QA_RULE_GOV_01: QaRuleDefinition(
            rule_id=QA_RULE_GOV_01,
            title="حذف منتورهای غیرفعال از تخصیص",
            law_mapping=mappings[QA_RULE_GOV_01],
            debug_context=QADebugContext.from_sequences(
                important_columns=("mentor_id", "status", "effective_status"),
                source_tables=("allocation", "governance_overrides"),
                lineage_keys=("mentor_id",),
                diagnosis_hints=("منتور با وضعیت رد یا غیرفعال نباید در تخصیص نهایی باقی بماند.",),
                canary_thresholds=_frozen_thresholds({}),
            ),
        ),
        QA_RULE_ALLOC_01: QaRuleDefinition(
            rule_id=QA_RULE_ALLOC_01,
            title="ظرفیت منتورها در تخصیص",
            law_mapping=mappings[QA_RULE_ALLOC_01],
            debug_context=QADebugContext.from_sequences(
                important_columns=("mentor_id", "remaining_capacity", "allocations_new"),
                source_tables=("allocation_summary", "policy"),
                lineage_keys=("mentor_id",),
                diagnosis_hints=(
                    "remaining_capacity و allocations_new را نسبت به سقف policy بررسی کنید.",
                ),
                canary_thresholds=_frozen_thresholds({}),
            ),
        ),
        QA_RULE_HISTORY_CHANNEL_01: QaRuleDefinition(
            rule_id=QA_RULE_HISTORY_CHANNEL_01,
            title="کلید تاریخچه باید کاننیکال و یکتا باشد",
            law_mapping=mappings[QA_RULE_HISTORY_CHANNEL_01],
            debug_context=QADebugContext.from_sequences(
                important_columns=("history_key", "allocation_channel"),
                source_tables=("history_info",),
                lineage_keys=("history_key",),
                diagnosis_hints=(
                    "کلید تاریخچه باید بدون فضای خالی و یکتا باشد؛ تخصیص channel را بررسی کنید.",
                ),
                canary_thresholds=_frozen_thresholds({}),
            ),
        ),
        QA_RULE_STATUS_DOMAIN_01: QaRuleDefinition(
            rule_id=QA_RULE_STATUS_DOMAIN_01,
            title="دامنهٔ وضعیت فارغ‌التحصیلی مطابق Policy/SSoT",  # noqa: RUF001
            law_mapping=mappings[QA_RULE_STATUS_DOMAIN_01],
            debug_context=QADebugContext.from_sequences(
                important_columns=(_GRADUATION_STATUS, _GROUP_CODE),
                source_tables=("matrix",),
                lineage_keys=(_GRADUATION_STATUS, _GROUP_CODE),
                diagnosis_hints=(
                    "کدرشته‌های دوحالته باید در دامنهٔ مجاز فارغ/دانش‌آموز باشند.",
                ),
                canary_thresholds=_frozen_thresholds({}),
            ),
        ),
    }

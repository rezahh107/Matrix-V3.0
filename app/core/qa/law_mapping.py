from __future__ import annotations

from dataclasses import dataclass

RuleId = str

__all__ = ["LawMapping", "all_law_mappings"]


@dataclass(frozen=True)
class LawMapping:
    """Central LAW mapping for QA rules."""

    rule_id: RuleId
    law_refs: tuple[str, ...]
    description: str


def all_law_mappings() -> dict[RuleId, LawMapping]:
    """Return LAW mappings for every QA rule."""

    return {
        "QA_RULE_STU_01": LawMapping(
            rule_id="QA_RULE_STU_01",
            law_refs=("LAW-STU-COUNT-01",),
            description="تعداد دانش‌آموز باید در ماتریس، تخصیص و گزارش‌ها هماهنگ باشد.",
        ),
        "QA_RULE_STU_02": LawMapping(
            rule_id="QA_RULE_STU_02",
            law_refs=("LAW-STU-COUNT-02",),
            description="ظرفیت انتظاری منتور در Inspactor باید با شمار تخصیص برابر باشد.",
        ),
        "QA_RULE_STU_BINDING_01": LawMapping(
            rule_id="QA_RULE_STU_BINDING_01",
            law_refs=("LAW-STU-BINDING-01",),
            description="الزام اتصال نوع دانش‌آموز به نوع منتور طبق Policy/SSoT.",
        ),
        "QA_RULE_JOIN_01": LawMapping(
            rule_id="QA_RULE_JOIN_01",
            law_refs=("LAW-JOIN-KEYS-01",),
            description="۶ کلید join باید کامل، غیرتهی و از نوع عددی صحیح باشند.",
        ),
        "QA_RULE_MENTOR_TYPE_01": LawMapping(
            rule_id="QA_RULE_MENTOR_TYPE_01",
            law_refs=("LAW-MENTOR-TYPE-01",),
            description="تمایز منتور عادی/مدرسه‌ای و alias مطابق ستون‌های ماتریس.",
        ),
        "QA_RULE_POOL_JOIN_01": LawMapping(
            rule_id="QA_RULE_POOL_JOIN_01",
            law_refs=("LAW-POOL-UNIQUE-01",),
            description="ردیف منتور در استخر باید روی کلید ترکیبی یکتا باشد.",
        ),
        "QA_RULE_SCHOOL_01": LawMapping(
            rule_id="QA_RULE_SCHOOL_01",
            law_refs=("LAW-SCHOOL-ASSIGNMENT-01",),
            description="منتور مدرسه‌ای نباید به مدرسهٔ متفاوت یا دانش‌آموز آزاد تخصیص گیرد.",
        ),
        "QA_RULE_GOV_01": LawMapping(
            rule_id="QA_RULE_GOV_01",
            law_refs=("LAW-GOV-STATUS-01",),
            description="منتور غیرفعال یا ردشده از کانال حاکمیتی باید حذف شود.",
        ),
        "QA_RULE_ALLOC_01": LawMapping(
            rule_id="QA_RULE_ALLOC_01",
            law_refs=("LAW-ALLOC-CAPACITY-01",),
            description="ظرفیت منتور نباید از سقف مجاز Policy تجاوز کند.",
        ),
        "QA_RULE_HISTORY_CHANNEL_01": LawMapping(
            rule_id="QA_RULE_HISTORY_CHANNEL_01",
            law_refs=("LAW-HISTORY-CHANNEL-01",),
            description="کلید تاریخچه باید کاننیکال، یکتا و ردیابی‌پذیر باشد.",
        ),
        "QA_RULE_STATUS_DOMAIN_01": LawMapping(
            rule_id="QA_RULE_STATUS_DOMAIN_01",
            law_refs=("LAW-STU-GRAD-01",),
            description="دامنهٔ وضعیت فارغ‌التحصیلی باید با گروه/پایه سازگار باشد.",
        ),
    }

"""Presentation-only metadata for retained diagnostics and advanced controls.

Runtime configuration remains owned by :mod:`app.infra.config_flags`. This
catalog only explains existing settings in the Qt presentation layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from .diagnostics_guides import GUIDES

CategoryId = Literal["diagnostics", "analysis", "advanced"]
ImpactKind = Literal["diagnostic", "analysis", "validation", "algorithmic"]


@dataclass(frozen=True)
class LocalizedText:
    fa: str
    en: str

    def for_language(self, language: str) -> str:
        return self.fa if language == "fa" else self.en


@dataclass(frozen=True)
class CapabilityPresentation:
    setting_key: str
    category: CategoryId
    title: LocalizedText
    summary: LocalizedText
    impact: LocalizedText
    impact_kind: ImpactKind
    allocation_impact: str
    validation_impact: str
    algorithm_impact: str
    guide_intro: LocalizedText


def _guide(setting_key: str) -> LocalizedText:
    fa, en = GUIDES[setting_key]
    return LocalizedText(fa, en)


CATEGORY_TITLES: Final[dict[CategoryId, LocalizedText]] = {
    "diagnostics": LocalizedText("ابزارهای خطایابی و مشاهده", "Diagnostics / Observability"),
    "analysis": LocalizedText("تحلیل", "Analysis"),
    "advanced": LocalizedText(
        "اعتبارسنجی و رفتار پیشرفته", "Advanced Validation / Execution Behavior"
    ),
}


CAPABILITIES: Final[tuple[CapabilityPresentation, ...]] = (
    CapabilityPresentation(
        "enable_trace_debug_sheets",
        "diagnostics",
        LocalizedText("شیت‌های خطایابی Trace", "Trace Debug Sheets"),
        LocalizedText(
            "شیت‌های کمکی Excel برای دیدن داده‌های میانی و علت‌های قابل بررسی یک اجرا.",
            "Adds Excel debug sheets that expose intermediate, inspectable run data.",
        ),
        LocalizedText(
            "فقط خطایابی — نتیجه تخصیص را تغییر نمی‌دهد",
            "DIAGNOSTIC ONLY — does not change allocation results",
        ),
        "diagnostic",
        "NO",
        "NO",
        "NO",
        _guide("enable_trace_debug_sheets"),
    ),
    CapabilityPresentation(
        "enable_mentor_trace_debug",
        "diagnostics",
        LocalizedText("Trace پایپلاین منتور", "Mentor Pipeline Trace"),
        LocalizedText(
            "برای دنبال‌کردن اینکه ردیف‌های منتور در مراحل آماده‌سازی استخر چگونه عبور یا حذف شده‌اند.",
            "Shows how mentor rows move through the mentor-pool preparation pipeline.",
        ),
        LocalizedText("فقط خطایابی", "DIAGNOSTIC ONLY"),
        "diagnostic",
        "NO",
        "NO",
        "NO",
        _guide("enable_mentor_trace_debug"),
    ),
    CapabilityPresentation(
        "enable_pool_governance_trace",
        "diagnostics",
        LocalizedText("Trace حاکمیت استخر", "Pool Governance Trace"),
        LocalizedText(
            "تغییرات اندازه، پروفایل‌ها و فشرده‌سازی استخر منتورها را برای بررسی فنی ثبت می‌کند.",
            "Records mentor-pool size, profile, governance, and condense diagnostics.",
        ),
        LocalizedText("فقط خطایابی", "DIAGNOSTIC ONLY"),
        "diagnostic",
        "NO",
        "NO",
        "NO",
        _guide("enable_pool_governance_trace"),
    ),
    CapabilityPresentation(
        "enable_bucket_trace",
        "diagnostics",
        LocalizedText("Trace باکت", "Bucket Trace"),
        LocalizedText(
            "نشان می‌دهد مرحله bucketing چه کلید، اندازه یا دلیل skip داشته است؛ حتی خاموش‌بودن bucketing قابل مشاهده است.",
            "Shows bucket keys, sizes, and skip reasons for the bucketing stage, including when bucketing is disabled.",
        ),
        LocalizedText(
            "فقط خطایابی — با Use Join Buckets متفاوت است",
            "DIAGNOSTIC ONLY — distinct from Use Join Buckets",
        ),
        "diagnostic",
        "NO",
        "NO",
        "NO",
        _guide("enable_bucket_trace"),
    ),
    CapabilityPresentation(
        "enable_trace_export",
        "diagnostics",
        LocalizedText("خروجی شیت Trace", "Trace Sheet Export"),
        LocalizedText(
            "Trace خام و توسعه‌دهنده‌محور را به‌عنوان شیت اضافی برای بررسی عمیق صادر می‌کند.",
            "Exports the raw, developer-oriented trace as an additional forensic sheet.",
        ),
        LocalizedText("فقط خروجی تشخیصی", "DIAGNOSTIC OUTPUT ONLY"),
        "diagnostic",
        "NO",
        "NO",
        "NO",
        _guide("enable_trace_export"),
    ),
    CapabilityPresentation(
        "enable_history_metrics",
        "analysis",
        LocalizedText("متریک‌های تاریخچه", "History Metrics"),
        LocalizedText(
            "شاخص‌های تحلیلی درباره ارتباط تخصیص فعلی با داده‌های تاریخچه را محاسبه و نمایش می‌دهد.",
            "Computes and presents analytical metrics relating the current run to history data.",
        ),
        LocalizedText(
            "فقط تحلیل — خاموش‌کردن آن history-aware allocation را خاموش نمی‌کند",
            "ANALYSIS ONLY — disabling it does not disable history-aware allocation",
        ),
        "analysis",
        "NO",
        "NO",
        "NO",
        _guide("enable_history_metrics"),
    ),
    CapabilityPresentation(
        "enable_qa_pool_coverage_rules",
        "advanced",
        LocalizedText("قواعد QA پوشش استخر", "QA Pool Coverage Rules"),
        LocalizedText(
            "قواعد QA اضافی را برای بررسی وجود کاندید منتور مطابق کلیدهای join فعال می‌کند.",
            "Enables additional QA rules that check whether students have mentor candidates matching the join keys.",
        ),
        LocalizedText(
            "ممکن است اعتبارسنجی PASS/FAIL را تغییر دهد",
            "MAY AFFECT VALIDATION PASS/FAIL",
        ),
        "validation",
        "NO",
        "YES",
        "NO",
        _guide("enable_qa_pool_coverage_rules"),
    ),
    CapabilityPresentation(
        "use_join_buckets",
        "advanced",
        LocalizedText("استفاده از Join Buckets", "Use Join Buckets"),
        LocalizedText(
            "مسیر جست‌وجوی کاندیدها را با محدودکردن اولیه به bucketهای join تغییر می‌دهد؛ گزینه‌ای پیشرفته و عموماً خاموش است.",
            "Changes candidate search by first narrowing through join buckets; this is an advanced option that is normally left off.",
        ),
        LocalizedText(
            "گزینه پیشرفته الگوریتمی / کارایی — مسیر اجرا را تغییر می‌دهد",
            "ADVANCED ALGORITHMIC / PERFORMANCE OPTION — changes execution path",
        ),
        "algorithmic",
        "CONDITIONAL",
        "NO",
        "YES",
        _guide("use_join_buckets"),
    ),
)

CAPABILITY_BY_KEY: Final[dict[str, CapabilityPresentation]] = {
    item.setting_key: item for item in CAPABILITIES
}
CATEGORY_ORDER: Final[tuple[CategoryId, ...]] = ("diagnostics", "analysis", "advanced")

"""Presentation-only metadata for retained diagnostics and advanced controls.

Runtime configuration remains owned by :mod:`app.infra.config_flags`.  This
catalog only explains existing settings in the Qt presentation layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

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
        LocalizedText("فقط خطایابی — نتیجه تخصیص را تغییر نمی‌دهد", "DIAGNOSTIC ONLY — does not change allocation results"),
        "diagnostic",
        "NO",
        "NO",
        "NO",
        LocalizedText(
            "Trace یعنی ثبت مرحله‌به‌مرحله اطلاعاتی که Matrix هنگام پردازش تولید یا مصرف می‌کند. این گزینه نمایش تشخیصی بیشتری به خروجی اضافه می‌کند و قانون تخصیص جدیدی فعال نمی‌کند.",
            "A trace is a step-by-step record of information Matrix uses or produces while processing. This setting adds diagnostic visibility; it does not enable a new allocation rule.",
        ),
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
        LocalizedText(
            "پایپلاین منتور زنجیره آماده‌سازی داده‌های منتور قبل از مصرف توسط تخصیص است. این Trace برای پاسخ به سؤال «ردیف منتور من کجا رفت؟» طراحی شده است.",
            "The mentor pipeline is the preparation chain that turns mentor input into the pool consumed by allocation. This trace helps answer: “Where did my mentor row go?”",
        ),
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
        LocalizedText(
            "استخر منتور مجموعه منتورهای آماده برای تخصیص است. این گزینه شواهدی درباره تغییرات ساختاری استخر تولید می‌کند، نه اینکه قواعد حاکم بر آن را عوض کند.",
            "The mentor pool is the set of mentors prepared for allocation. This setting records evidence about structural pool changes; it does not redefine the governance rules.",
        ),
    ),
    CapabilityPresentation(
        "enable_bucket_trace",
        "diagnostics",
        LocalizedText("Trace باکت", "Bucket Trace"),
        LocalizedText(
            "نشان می‌دهد مرحله bucketing چه کلید، اندازه یا دلیل skip داشته است؛ حتی خاموش‌بودن bucketing قابل مشاهده است.",
            "Shows bucket keys, sizes, and skip reasons for the bucketing stage, including when bucketing is disabled.",
        ),
        LocalizedText("فقط خطایابی — با Use Join Buckets متفاوت است", "DIAGNOSTIC ONLY — distinct from Use Join Buckets"),
        "diagnostic",
        "NO",
        "NO",
        "NO",
        LocalizedText(
            "Bucket Trace ناظر رفتار bucketing است. روشن‌کردن این گزینه به‌تنهایی bucketing را فعال نمی‌کند؛ Use Join Buckets کنترل جداگانه مسیر الگوریتمی است.",
            "Bucket Trace observes bucketing behavior. Enabling this trace does not itself enable bucketing; Use Join Buckets is the separate algorithm-path control.",
        ),
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
        LocalizedText(
            "این گزینه نتیجه معمول کاربر را جایگزین نمی‌کند؛ فقط Trace خام را برای تحلیل فنی عمیق‌تر در خروجی نگه می‌دارد.",
            "This does not replace the normal user result. It retains raw trace data in the output for deeper technical inspection.",
        ),
    ),
    CapabilityPresentation(
        "enable_history_metrics",
        "analysis",
        LocalizedText("متریک‌های تاریخچه", "History Metrics"),
        LocalizedText(
            "شاخص‌های تحلیلی درباره ارتباط تخصیص فعلی با داده‌های تاریخچه را محاسبه و نمایش می‌دهد.",
            "Computes and presents analytical metrics relating the current run to history data.",
        ),
        LocalizedText("فقط تحلیل — خاموش‌کردن آن history-aware allocation را خاموش نمی‌کند", "ANALYSIS ONLY — disabling it does not disable history-aware allocation"),
        "analysis",
        "NO",
        "NO",
        "NO",
        LocalizedText(
            "History Metrics گزارش است، نه کل مکانیزم تاریخچه. این گزینه برای فهم الگوهای تاریخی خروجی است و خاموش‌کردنش به معنی حذف همه رفتارهای تخصیص آگاه از تاریخچه نیست.",
            "History Metrics is reporting, not the entire history mechanism. It helps interpret historical patterns in results; turning it off does not disable all history-aware allocation behavior.",
        ),
    ),
    CapabilityPresentation(
        "enable_qa_pool_coverage_rules",
        "advanced",
        LocalizedText("قواعد QA پوشش استخر", "QA Pool Coverage Rules"),
        LocalizedText(
            "قواعد QA اضافی را برای بررسی وجود کاندید منتور مطابق کلیدهای join فعال می‌کند.",
            "Enables additional QA rules that check whether students have mentor candidates matching the join keys.",
        ),
        LocalizedText("ممکن است اعتبارسنجی PASS/FAIL را تغییر دهد", "MAY AFFECT VALIDATION PASS/FAIL"),
        "validation",
        "NO",
        "YES",
        "NO",
        LocalizedText(
            "این گزینه صرفاً گزارش‌گیری نیست. اگر دانش‌آموزی در استخر نهایی کاندید مطابق نداشته باشد، قانون QA پوشش می‌تواند fail شود و در نتیجه QaReport.passed را تغییر دهد.",
            "This is not reporting-only. If a student has no matching candidate in the final pool, the coverage QA rule can fail and therefore change QaReport.passed.",
        ),
    ),
    CapabilityPresentation(
        "use_join_buckets",
        "advanced",
        LocalizedText("استفاده از Join Buckets", "Use Join Buckets"),
        LocalizedText(
            "مسیر جست‌وجوی کاندیدها را با محدودکردن اولیه به bucketهای join تغییر می‌دهد؛ گزینه‌ای پیشرفته و عموماً خاموش است.",
            "Changes candidate search by first narrowing through join buckets; this is an advanced option that is normally left off.",
        ),
        LocalizedText("گزینه پیشرفته الگوریتمی / کارایی — مسیر اجرا را تغییر می‌دهد", "ADVANCED ALGORITHMIC / PERFORMANCE OPTION — changes execution path"),
        "algorithmic",
        "CONDITIONAL",
        "NO",
        "YES",
        LocalizedText(
            "Bucketing یعنی تقسیم کاندیدها به گروه‌های قابل جست‌وجوی کوچک‌تر بر پایه کلیدهای join. تست‌های parity برای برابری خروجی در سناریوهای پوشش‌داده‌شده وجود دارند، اما این تست‌ها اثبات ریاضی برای همه ورودی‌های ممکن نیستند.",
            "Bucketing partitions candidates into smaller searchable groups based on join keys. Parity tests cover equivalence in tested scenarios, but those tests are not a mathematical proof for every possible input.",
        ),
    ),
)

CAPABILITY_BY_KEY: Final[dict[str, CapabilityPresentation]] = {
    item.setting_key: item for item in CAPABILITIES
}
CATEGORY_ORDER: Final[tuple[CategoryId, ...]] = ("diagnostics", "analysis", "advanced")

"""Complete bilingual help text for the eight retained advanced capabilities.

Claims in this module are presentation documentation derived from current code
and tests. It is not a runtime configuration or domain-policy authority.
"""

from __future__ import annotations

from typing import Final


def _fa(
    *,
    title: str,
    key: str,
    mental: str,
    purpose: str,
    subsystem: str,
    concept: str,
    enable_when: str,
    leave_off: str,
    allocation: str,
    validation: str,
    algorithm: str,
    diagnostic_only: str,
    internal: str,
    output: str,
    location: str,
    reading: str,
    example: str,
    not_prove: str,
    limitations: str,
    performance: str,
    related: str,
    implementation: str,
    tests: str,
    evidence: str,
) -> str:
    return f"""{title}

A. درک پایه
- این چیست؟ {purpose}
- مدل ذهنی یک‌جمله‌ای: {mental}
- چرا Matrix آن را دارد؟ برای اینکه رفتار یا داده‌های بخش «{subsystem}» بدون تغییر قانون اصلی قابل مشاهده، تحلیل یا کنترل باشد.
- زیرسیستم مرتبط: {subsystem}

B. توضیح مفهوم
{concept}

C. چه زمانی استفاده کنم؟
- روشن کنید وقتی: {enable_when}
- مثال از نشانه عملی: وقتی خروجی نهایی به‌تنهایی پاسخ نمی‌دهد که مشکل در کدام مرحله یا داده رخ داده است.
- خاموش بگذارید وقتی: {leave_off}

D. اثر رفتاری
- آیا نتیجه تخصیص را تغییر می‌دهد؟ {allocation}
- آیا می‌تواند PASS/FAIL اعتبارسنجی را تغییر دهد؟ {validation}
- آیا مسیر اجرای الگوریتم را تغییر می‌دهد؟ {algorithm}
- آیا فقط خروجی/مشاهده اضافی است؟ {diagnostic_only}

E. داخل برنامه چه اتفاقی می‌افتد؟
{internal}

F. خروجی و روش خواندن
- خروجی مورد انتظار: {output}
- کجا پیدا می‌شود؟ {location}
- چگونه بخوانم؟ {reading}
- نکته: نام فایل اصلی به مسیر خروجی همان run بستگی دارد؛ فقط نام sheet/fileهایی که کد صریحاً تولید می‌کند در این راهنما قطعی اعلام شده‌اند.

G. مثال عملی
{example}

H. محدودیت و چیزی که ثابت نمی‌کند
- این خروجی چه چیزی را ثابت نمی‌کند؟ {not_prove}
- محدودیت‌های شناخته‌شده: {limitations}

I. کارایی و فضای ذخیره‌سازی
{performance}
- هزینه دقیق CPU: NOT MEASURED
- هزینه دقیق Memory: NOT MEASURED
- افزایش دقیق اندازه workbook/log/storage: NOT MEASURED

J. پیکربندی
- setting key واقعی: {key}
- مقدار پیش‌فرض واقعی: OFF / False
- persistence واقعی: فیلد UserSettings در JSON کاربر؛ مسیر پیش‌فرض `~/.smart_alloc/user_settings.json`.
- پس از خاموش‌کردن: runهای بعدی این قابلیت اختیاری را فعال نمی‌کنند؛ رفتار دقیق طبق consumerهای فعلی همان setting است.
- artifactهای قدیمی: خاموش‌کردن setting فایل‌ها، sheetها یا logهای قبلاً ساخته‌شده را حذف نمی‌کند.

K. ابزارهای مرتبط
{related}

L. نقشه نگه‌دارنده
- implementation اصلی: {implementation}
- تست‌ها/guardهای مرتبط: {tests}

M. صداقت شواهد
{evidence}
DIRECTLY_CONFIRMED یعنی کد/تست فعلی صریحاً آن را نشان می‌دهد. INFERRED یعنی برداشت کاربردی از رفتار تأییدشده است. NOT_PROVEN یعنی شواهد فعلی برای ادعای قطعی کافی نیست.
"""


def _en(
    *,
    title: str,
    key: str,
    mental: str,
    purpose: str,
    subsystem: str,
    concept: str,
    enable_when: str,
    leave_off: str,
    allocation: str,
    validation: str,
    algorithm: str,
    diagnostic_only: str,
    internal: str,
    output: str,
    location: str,
    reading: str,
    example: str,
    not_prove: str,
    limitations: str,
    performance: str,
    related: str,
    implementation: str,
    tests: str,
    evidence: str,
) -> str:
    return f"""{title}

A. Basic understanding
- What is this? {purpose}
- One-sentence mental model: {mental}
- Why does Matrix have it? To make the behavior or data of “{subsystem}” observable, analyzable, or controllable without redefining the core rules.
- Related subsystem: {subsystem}

B. Concept explanation
{concept}

C. When should I use it?
- Enable it when: {enable_when}
- Concrete symptom: the final result alone cannot tell you which stage or data condition caused what you are investigating.
- Leave it OFF when: {leave_off}

D. Behavioral impact
- Does it change allocation results? {allocation}
- Can it change validation PASS/FAIL? {validation}
- Does it change the algorithmic execution path? {algorithm}
- Is it only additional diagnostic/reporting output? {diagnostic_only}

E. What actually happens internally?
{internal}

F. Output and interpretation
- Expected output: {output}
- Where do I find it? {location}
- How do I read it? {reading}
- Note: the primary workbook filename depends on that run's output path. This guide claims exact sheet/file names only where current code explicitly creates them.

G. Practical example
{example}

H. Limitations and what it does not prove
- What does this output NOT prove? {not_prove}
- Known limitations: {limitations}

I. Performance and storage
{performance}
- Exact CPU cost: NOT MEASURED
- Exact memory cost: NOT MEASURED
- Exact workbook/log/storage growth: NOT MEASURED

J. Configuration
- Actual setting key: {key}
- Actual default: OFF / False
- Actual persistence: UserSettings field in the user's JSON settings file; default path `~/.smart_alloc/user_settings.json`.
- After turning it OFF: later runs no longer enable this optional capability; exact behavior follows the current consumers of this setting.
- Existing artifacts: turning it off does not delete files, sheets, or logs already produced.

K. Related tools
{related}

L. Maintainer map
- Primary implementation: {implementation}
- Relevant tests/guards: {tests}

M. Evidence honesty
{evidence}
DIRECTLY_CONFIRMED means current code/tests state it directly. INFERRED means a practical interpretation of confirmed behavior. NOT_PROVEN means current evidence is insufficient for a universal claim.
"""


GUIDES: Final[dict[str, tuple[str, str]]] = {
    "enable_history_metrics": (
        _fa(
            title="History Metrics — متریک‌های تاریخچه",
            key="enable_history_metrics",
            mental="یک داشبورد آماری برای فهم رابطه تخصیص فعلی با سابقه؛ نه کل موتور تاریخچه.",
            purpose="محاسبه و ارائه شاخص‌های تحلیلی تاریخچه برای run جاری است.",
            subsystem="history metrics / history reporting",
            concept="«History Metrics» آمار خلاصه‌شده بر اساس allocation channel می‌سازد. ستون‌های تأییدشده شامل `allocation_channel`, `students_total`, `history_already_allocated`, `history_no_history_match`, `history_missing_or_invalid`, `same_history_mentor_true`, `same_history_mentor_ratio` هستند. `same_history_mentor_ratio` نسبت مواردی است که منتور انتخاب‌شده با منتور تاریخچه یکسان بوده به تعداد دانش‌آموزان آن کانال. مهم: این reporting با history-aware allocation behavior یکسان نیست.",
            enable_when="می‌خواهید بفهمید چند دانش‌آموز سابقه معتبر داشته‌اند، چند مورد match نشده و نسبت حفظ منتور قبلی چقدر بوده است.",
            leave_off="به این آمار نیاز ندارید و فقط خروجی عملیاتی عادی را می‌خواهید.",
            allocation="NO — این setting گزارش متریک را کنترل می‌کند؛ خاموش‌کردن آن به معنی خاموش‌کردن تمام رفتار history-aware allocation نیست.",
            validation="NO — از شواهد فعلی این setting به‌عنوان QA PASS/FAIL gate استفاده نمی‌شود.",
            algorithm="NO برای مسیر تخصیص؛ محاسبه گزارش اضافی انجام می‌شود.",
            diagnostic_only="ANALYSIS/REPORTING ONLY نسبت به تصمیم تخصیص.",
            internal="`cli_legacy.py` فقط هنگام روشن‌بودن setting، DataFrame متریک تاریخچه را می‌سازد/لاگ می‌کند. `compute_history_metrics` در `app/core/allocation/history_metrics.py` محاسبات ستون‌های متریک را انجام می‌دهد. در مسیر debug-sheet، exporter می‌تواند sheet `HistoryMetrics` را از همین داده بسازد.",
            output="لاگ‌های `HistoryMetrics[...]` و، وقتی مسیر standard debug sheets نیز در همان خروجی استفاده شود، sheet با نام دقیق `HistoryMetrics`.",
            location="در log همان run و در workbookی که debug sheets به آن اضافه شده‌اند. نمایش UI تاریخچه نیز توسط `app/ui/history_metrics.py` پشتیبانی می‌شود.",
            reading="هر ردیف را بر حسب `allocation_channel` بخوانید. `students_total` مخرج جمعیت است؛ سه ستون history وضعیت سابقه را دسته‌بندی می‌کنند؛ `same_history_mentor_true` شمارش و `same_history_mentor_ratio` نسبت همان منتور تاریخی است.",
            example="نشانه: مدیر می‌پرسد چرا به‌نظر می‌رسد منتورهای قبلی کمتر حفظ شده‌اند. → History Metrics را روشن کنید. → ratio هر channel را ببینید. → اگر `history_missing_or_invalid` بالا است، اول کیفیت داده تاریخچه را بررسی کنید؛ ratio پایین به‌تنهایی اثبات نمی‌کند ranking خراب است.",
            not_prove="ratio پایین به‌تنهایی اثبات نمی‌کند الگوریتم اشتباه کرده یا history-aware behavior اجرا نشده است؛ کیفیت/وجود تاریخچه و eligibility نیز مؤثرند.",
            limitations="متریک خلاصه است و علت دقیق تصمیم هر دانش‌آموز را نشان نمی‌دهد. برای علت ردیفی از traceهای مرتبط استفاده کنید.",
            performance="محاسبه DataFrame متریک و logging/output اضافی می‌تواند CPU، memory، log volume و در صورت export اندازه workbook را افزایش دهد. تغییر مستقل DB ناشی از خود این toggle از این راهنما اثبات نشده است.",
            related="برای علت یک تصمیم خاص Trace Debug Sheets/Trace Sheet Export مناسب‌تر است؛ برای سؤال «ردیف منتور کجا حذف شد؟» Mentor Pipeline Trace را انتخاب کنید.",
            implementation="`app/core/allocation/history_metrics.py::compute_history_metrics`; `app/infra/cli_legacy.py`; `app/infra/excel/export_allocations.py::_build_history_metrics_sheet`; `app/ui/history_metrics.py`.",
            tests="`tests/core/allocation/test_history_metrics.py`; `tests/infra/test_history_metrics_logging.py`; `tests/test_user_settings.py`.",
            evidence="DIRECTLY_CONFIRMED: setting/default/persistence، ستون‌های METRIC_COLUMNS، logging و sheet `HistoryMetrics`. INFERRED: سناریوی عیب‌یابی پیشنهادی. NOT_PROVEN: هزینه دقیق کارایی و اینکه یک ratio خاص به‌تنهایی علت دامنه‌ای مشخصی دارد.",
        ),
        _en(
            title="History Metrics",
            key="enable_history_metrics",
            mental="A statistical dashboard for understanding the current allocation against history, not the whole history engine.",
            purpose="Computes and presents history-analysis metrics for the current run.",
            subsystem="history metrics / history reporting",
            concept="History Metrics creates summaries by allocation channel. Confirmed columns include `allocation_channel`, `students_total`, `history_already_allocated`, `history_no_history_match`, `history_missing_or_invalid`, `same_history_mentor_true`, and `same_history_mentor_ratio`. `same_history_mentor_ratio` is the share of students in the channel whose selected mentor matches the history mentor. Reporting is distinct from history-aware allocation behavior.",
            enable_when="you need to quantify valid/missing history, unmatched history, or how often a prior mentor was retained.",
            leave_off="you do not need history reporting and only want routine operational output.",
            allocation="NO — this setting controls metric reporting; disabling it does not mean all history-aware allocation behavior is disabled.",
            validation="NO — current evidence does not wire this setting as a QA PASS/FAIL gate.",
            algorithm="NO for the allocation path; extra metric computation is performed.",
            diagnostic_only="ANALYSIS/REPORTING ONLY relative to the allocation decision.",
            internal="`cli_legacy.py` builds/logs the history-metrics DataFrame only when enabled. `compute_history_metrics` in `app/core/allocation/history_metrics.py` computes the metric columns. In the debug-sheet path, the exporter can create the `HistoryMetrics` sheet from this data.",
            output="`HistoryMetrics[...]` log records and, when standard debug sheets are included in the same output path, the exact sheet `HistoryMetrics`.",
            location="the current run log and the workbook receiving debug sheets. `app/ui/history_metrics.py` also supports the UI metrics presentation.",
            reading="read each row by `allocation_channel`. `students_total` is the population denominator; the history-status columns classify history state; `same_history_mentor_true` is the count and `same_history_mentor_ratio` the corresponding share.",
            example="Symptom: an operator thinks prior mentors are being retained less often. → Enable History Metrics. → Compare the ratio by channel. → If `history_missing_or_invalid` is high, investigate history-data quality first; a low ratio alone does not prove ranking is broken.",
            not_prove="a low ratio alone does not prove an algorithm defect or prove that history-aware behavior failed to execute; history availability and eligibility matter.",
            limitations="this is summary analysis, not a per-student causal explanation. Use trace tools for row-level investigation.",
            performance="extra DataFrame computation and logging/output can increase CPU, memory, log volume, and workbook size when exported. An independent database cost caused solely by this toggle is not proven here.",
            related="use Trace Debug Sheets/Trace Sheet Export for a specific decision; use Mentor Pipeline Trace for “where did the mentor row go?” questions.",
            implementation="`app/core/allocation/history_metrics.py::compute_history_metrics`; `app/infra/cli_legacy.py`; `app/infra/excel/export_allocations.py::_build_history_metrics_sheet`; `app/ui/history_metrics.py`.",
            tests="`tests/core/allocation/test_history_metrics.py`; `tests/infra/test_history_metrics_logging.py`; `tests/test_user_settings.py`.",
            evidence="DIRECTLY_CONFIRMED: setting/default/persistence, METRIC_COLUMNS, logging, and the `HistoryMetrics` sheet. INFERRED: the proposed troubleshooting sequence. NOT_PROVEN: exact performance cost or a universal causal meaning for any single ratio.",
        ),
    ),
    "enable_trace_debug_sheets": (
        _fa(
            title="Trace Debug Sheets — شیت‌های خطایابی Trace",
            key="enable_trace_debug_sheets",
            mental="مثل بازکردن چند پنجره بازرسی روی run، بدون عوض‌کردن تصمیم موتور.",
            purpose="مجموعه‌ای از sheetهای استاندارد debug را به خروجی اضافه می‌کند تا خلاصه‌ها، وضعیت‌ها و provenance قابل بررسی باشند.",
            subsystem="allocation trace/export observability",
            concept="Trace یعنی ثبت مرحله‌به‌مرحله اطلاعات استفاده‌شده یا تولیدشده هنگام پردازش. این setting خود trace کاننیکال دامنه را بازتعریف نمی‌کند؛ فقط نمایش‌های debug Excel را از داده‌های موجود می‌سازد.",
            enable_when="خروجی تخصیص غیرمنتظره است و به summary، وضعیت‌های نهایی، provenance کلیدهای join یا ردیف‌های unallocated/policy violations نیاز دارید.",
            leave_off="run عادی است و به workbook سبک‌تر و بدون sheetهای developer-oriented نیاز دارید.",
            allocation="NO — exporter شیت اضافه می‌کند و allocation result را بازنویسی نمی‌کند.",
            validation="NO — خود این toggle rule QA جدیدی فعال نمی‌کند.",
            algorithm="NO — مسیر تصمیم تخصیص را تغییر نمی‌دهد.",
            diagnostic_only="YES — خروجی تشخیصی اضافه است.",
            internal="`resolved_settings.enable_trace_debug_sheets` به `collect_trace_debug_sheets(... enable_standard_debug_sheets=...)` داده می‌شود. exporter از trace/summary موجود DataFrameهای تشخیصی می‌سازد؛ این کار پس از/کنار تولید داده تخصیص انجام می‌شود.",
            output="نام‌های تأییدشده بسته به داده موجود: `summary_df`, `FinalStatus_counts`, `JoinKeyProvenance_counts`, `HistoryMetrics`, `unallocated_summary`, `policy_violations`. وجود بعضی sheetها مشروط به وجود داده متناظر است.",
            location="در workbook خروجی‌ای که CLI/export path، debug_sheets را به آن اضافه می‌کند؛ نام فایل اصلی تابع مسیر خروجی run است.",
            reading="`summary_df` خلاصه ردیفی/اجرایی؛ `FinalStatus_counts` تعداد هر final_status؛ `JoinKeyProvenance_counts` تعداد inferred/defaulted برای stageهای join؛ `unallocated_summary` موارد تخصیص‌نیافته؛ `policy_violations` تخطی‌های policy. `HistoryMetrics` را با راهنمای History Metrics بخوانید.",
            example="نشانه: تعداد تخصیص‌نیافته‌ها غیرمنتظره زیاد است. → Trace Debug Sheets را روشن کنید. → `unallocated_summary` و `FinalStatus_counts` را بررسی کنید. → سپس اگر منشأ join مشکوک است `JoinKeyProvenance_counts` را بخوانید و برای جزئیات ردیفی سراغ trace تخصصی بروید.",
            not_prove="وجود یک مقدار در sheet debug به‌تنهایی اثبات علت ریشه‌ای نیست؛ این sheetها evidence برای تحقیق‌اند.",
            limitations="sheetهای conditional ممکن است وقتی DataFrame ورودی خالی/ناموجود است ساخته نشوند یا خالی باشند. این گزینه همه traceهای تخصصی را خودکار روشن نمی‌کند.",
            performance="ساخت/copy کردن DataFrameها و نوشتن sheetهای بیشتر می‌تواند CPU، memory و workbook size را افزایش دهد. logging مستقل اضافی برای همه sheetها اثبات نشده؛ DB را تغییر نمی‌دهد.",
            related="Mentor Pipeline Trace برای مسیر آماده‌سازی منتور؛ Pool Governance Trace برای ساختار استخر؛ Bucket Trace برای bucketing؛ Trace Sheet Export برای trace خام مناسب‌ترند.",
            implementation="`app/infra/cli_legacy.py`; `app/infra/excel/export_allocations.py::collect_trace_debug_sheets` و helperهای همان ماژول.",
            tests="`tests/test_excel_export_smoke.py`; `tests/test_allocation_invariance.py`; `tests/test_user_settings.py`.",
            evidence="DIRECTLY_CONFIRMED: wiring setting و sheet names. INFERRED: ترتیب پیشنهادی عیب‌یابی. NOT_PROVEN: هزینه دقیق و اینکه هر sheet همیشه برای هر run غیرخالی باشد.",
        ),
        _en(
            title="Trace Debug Sheets",
            key="enable_trace_debug_sheets",
            mental="Open several inspection windows onto a run without changing the engine's decision.",
            purpose="Adds standard debug sheets so summaries, final states, and provenance can be inspected.",
            subsystem="allocation trace/export observability",
            concept="A trace is a step-by-step record of information used or produced during processing. This setting does not redefine the canonical domain trace; it creates Excel debug views from data Matrix already has.",
            enable_when="an allocation output is unexpected and you need summaries, final-status counts, join-key provenance, unallocated rows, or policy-violation evidence.",
            leave_off="the run is routine and you prefer a smaller workbook without developer-oriented sheets.",
            allocation="NO — the exporter adds sheets; it does not rewrite allocation results.",
            validation="NO — this toggle does not enable new QA rules.",
            algorithm="NO — it does not change the allocation decision path.",
            diagnostic_only="YES — additional diagnostic output.",
            internal="`resolved_settings.enable_trace_debug_sheets` is passed to `collect_trace_debug_sheets(... enable_standard_debug_sheets=...)`. The exporter derives diagnostic DataFrames from existing trace/summary data alongside the normal export path.",
            output="confirmed names, conditional on available data: `summary_df`, `FinalStatus_counts`, `JoinKeyProvenance_counts`, `HistoryMetrics`, `unallocated_summary`, and `policy_violations`.",
            location="the output workbook to which the CLI/export path adds debug sheets; the primary filename is determined by that run's output path.",
            reading="`summary_df` is a run/row summary; `FinalStatus_counts` counts each final status; `JoinKeyProvenance_counts` counts inferred/defaulted join-stage provenance; `unallocated_summary` lists unallocated cases; `policy_violations` records policy issues. Read `HistoryMetrics` with the dedicated History Metrics guide.",
            example="Symptom: unexpectedly many students are unallocated. → Enable Trace Debug Sheets. → Inspect `unallocated_summary` and `FinalStatus_counts`. → If join provenance looks suspicious, inspect `JoinKeyProvenance_counts`, then use a specialized trace for row-level detail.",
            not_prove="a value in a debug sheet does not by itself prove root cause; these sheets are evidence for investigation.",
            limitations="conditional sheets may be absent or empty when their source data is absent/empty. This setting does not automatically enable every specialized trace.",
            performance="building/copying DataFrames and writing more sheets can increase CPU, memory, and workbook size. Extra independent logging for every sheet is not proven; this setting does not itself modify the database.",
            related="use Mentor Pipeline Trace for mentor preparation, Pool Governance Trace for pool structure, Bucket Trace for bucketing, and Trace Sheet Export for raw trace.",
            implementation="`app/infra/cli_legacy.py`; `app/infra/excel/export_allocations.py::collect_trace_debug_sheets` and helpers in that module.",
            tests="`tests/test_excel_export_smoke.py`; `tests/test_allocation_invariance.py`; `tests/test_user_settings.py`.",
            evidence="DIRECTLY_CONFIRMED: setting wiring and sheet names. INFERRED: suggested investigation order. NOT_PROVEN: exact cost or that every sheet is non-empty for every run.",
        ),
    ),
    "enable_mentor_trace_debug": (
        _fa(
            title="Mentor Pipeline Trace — Trace پایپلاین منتور",
            key="enable_mentor_trace_debug",
            mental="رسید مرحله‌به‌مرحله برای پاسخ به «ردیف‌های منتور من در کدام مرحله تغییر کردند؟».",
            purpose="مراحل آماده‌سازی mentor pool را ثبت و به sheetهای قابل خواندن تبدیل می‌کند.",
            subsystem="MentorPipelineV3 and allocation eligibility observability",
            concept="Mentor Pipeline زنجیره `FieldRegistry → HeaderResolver → ValueCanonicalizer → JoinKeyResolver → MentorPoolBuilder` است. stageهای مستقیم مشاهده‌شده در کد شامل `raw`, `header_resolved`, `canonicalized`, در شرایط مربوط `join_keys_present` یا `canonicalized_db`, سپس `join_keys`, `all_profiles`, `usable_profiles`, `condense_profiles_to_unique_mentors`, `pool_built` و در export ترکیبی `global_prefilter` هستند.",
            enable_when="ردیف منتور در pool نهایی دیده نمی‌شود، تعداد profileها تغییر کرده، یا می‌خواهید بفهمید کاهش row count در کدام stage رخ داده است.",
            leave_off="مسیر mentor input سالم و قابل انتظار است و به جزئیات stage-by-stage نیاز ندارید.",
            allocation="NO — trace ثبت می‌شود؛ قواعد pipeline/allocation تغییر نمی‌کنند.",
            validation="NO — این toggle به‌تنهایی QA rule جدید فعال نمی‌کند.",
            algorithm="NO برای semantics pipeline؛ instrumentation/trace اضافی اجرا می‌شود.",
            diagnostic_only="YES.",
            internal="`MentorPipelineV3(enable_trace=True)` entryهای stage را با rows/columns/fingerprint و metrics پروفایل ثبت می‌کند. exporter همچنین `EligibilityTrace`, `TraceLadder` و `MentorPipelineTrace` را در حالت mentor trace می‌سازد؛ `global_prefilter` نیز می‌تواند به trace pipeline افزوده شود.",
            output="sheetهای دقیق `EligibilityTrace`, `TraceLadder`, `MentorPipelineTrace`. ستون‌های `MentorPipelineTrace` شامل `stage`, `rows`, `columns`, `fingerprint`, `raw_count`, `predicate_summary`, `after_count`, `profile_rows`, `unique_mentor_ids`, `multi_profile_mentor_count`, `multi_profile_ratio`, `predicate_expr`, `predicate_source`, `prefilter_removed` هستند.",
            location="در workbook خروجی که debug sheets به آن افزوده شده‌اند.",
            reading="ردیف‌های `MentorPipelineTrace` را به ترتیب stage بخوانید و تغییر `rows`/`after_count` را دنبال کنید. `fingerprint` برای مقایسه snapshot داده است، نه توضیح معنایی. در `EligibilityTrace` شمارش کاندیدها و stageهای eligibility را برای student دنبال کنید؛ `TraceLadder` نمای ladder همان trace را غنی می‌کند.",
            example="نشانه: منتور EMP-123 در ورودی هست ولی در pool قابل تخصیص نیست. → Mentor Pipeline Trace را روشن کنید. → تعداد/اثر stageهای `all_profiles` و `usable_profiles` و سپس `pool_built` را مقایسه کنید. → اگر افت در usable profiles است، issues مربوط به join/profile را بررسی کنید.",
            not_prove="کم‌شدن row count به‌تنهایی اثبات bug نیست؛ ممکن است نتیجه canonicalization/governance معتبر باشد. fingerprint نیز علت تغییر را توضیح نمی‌دهد.",
            limitations="trace به داده‌ها و stageهای اجراشده وابسته است؛ بعضی stageهای شرطی ممکن است ظاهر نشوند. مقدار `trace_max_rows` روی fingerprint sampling اثر دارد.",
            performance="instrumentation، fingerprinting، DataFrame ساختن و sheet export می‌تواند CPU، memory و workbook size را افزایش دهد؛ DB semantics تغییر نمی‌کند.",
            related="Pool Governance Trace برای چرایی تغییرات governance/condense متمرکزتر است؛ Trace Debug Sheets برای خلاصه عمومی؛ Bucket Trace برای narrowing کاندیدها در allocation.",
            implementation="`app/infra/mentors/pipeline_v3.py::MentorPipelineV3` و `MentorPipelineTraceEntry`; `app/infra/excel/export_allocations.py::_build_pipeline_trace_sheet`, `_build_eligibility_trace_sheet`, `_build_trace_ladder_sheet`; `app/infra/cli_legacy.py`.",
            tests="`tests/test_user_settings.py` (MentorPipelineTrace export/global_prefilter); `tests/test_excel_export_smoke.py`; pipeline-specific tests under `tests/infra`.",
            evidence="DIRECTLY_CONFIRMED: stage names، fields و sheet names. INFERRED: workflow عیب‌یابی نمونه. NOT_PROVEN: اینکه هر کاهش rows نشان‌دهنده defect باشد یا هزینه دقیق instrumentation.",
        ),
        _en(
            title="Mentor Pipeline Trace",
            key="enable_mentor_trace_debug",
            mental="A stage-by-stage receipt for answering, “At which preparation stage did my mentor rows change?”",
            purpose="Records mentor-pool preparation stages and exports readable trace sheets.",
            subsystem="MentorPipelineV3 and allocation eligibility observability",
            concept="The Mentor Pipeline is `FieldRegistry → HeaderResolver → ValueCanonicalizer → JoinKeyResolver → MentorPoolBuilder`. Stage names directly present in current code include `raw`, `header_resolved`, `canonicalized`, conditionally `join_keys_present` or `canonicalized_db`, then `join_keys`, `all_profiles`, `usable_profiles`, `condense_profiles_to_unique_mentors`, `pool_built`, plus the export-composed `global_prefilter` stage.",
            enable_when="a mentor row is missing from the final pool, profile counts changed, or you need to locate the stage where row counts dropped.",
            leave_off="mentor input/pool preparation is behaving as expected and stage-level evidence is unnecessary.",
            allocation="NO — tracing is added; pipeline/allocation rules are unchanged.",
            validation="NO — this toggle alone does not enable an additional QA rule.",
            algorithm="NO for pipeline semantics; extra instrumentation/tracing executes.",
            diagnostic_only="YES.",
            internal="`MentorPipelineV3(enable_trace=True)` records stage entries with rows/columns/fingerprint and profile metrics. The exporter also builds `EligibilityTrace`, `TraceLadder`, and `MentorPipelineTrace`; `global_prefilter` may be appended to the pipeline trace.",
            output="exact sheets `EligibilityTrace`, `TraceLadder`, and `MentorPipelineTrace`. Confirmed pipeline columns include `stage`, `rows`, `columns`, `fingerprint`, `raw_count`, `predicate_summary`, `after_count`, `profile_rows`, `unique_mentor_ids`, `multi_profile_mentor_count`, `multi_profile_ratio`, `predicate_expr`, `predicate_source`, and `prefilter_removed`.",
            location="the output workbook receiving the debug sheets.",
            reading="follow `MentorPipelineTrace` in stage order and compare `rows`/`after_count`. `fingerprint` helps compare data snapshots; it is not a semantic explanation. In `EligibilityTrace`, follow candidate counts/stages for a student; `TraceLadder` is an enriched ladder view of trace information.",
            example="Symptom: mentor EMP-123 exists in input but is not usable in the final pool. → Enable Mentor Pipeline Trace. → Compare `all_profiles`, `usable_profiles`, then `pool_built`. → If the drop occurs at usable profiles, investigate join/profile issues.",
            not_prove="a lower row count is not automatically a bug; valid canonicalization/governance can remove or condense data. A fingerprint also does not explain why data changed.",
            limitations="trace content depends on executed stages; conditional stages may be absent. `trace_max_rows` affects fingerprint sampling.",
            performance="instrumentation, fingerprinting, DataFrame construction, and sheet export can increase CPU, memory, and workbook size; database semantics are unchanged.",
            related="use Pool Governance Trace for governance/condense details, Trace Debug Sheets for general summaries, and Bucket Trace for allocation candidate narrowing.",
            implementation="`app/infra/mentors/pipeline_v3.py::MentorPipelineV3` and `MentorPipelineTraceEntry`; `app/infra/excel/export_allocations.py::_build_pipeline_trace_sheet`, `_build_eligibility_trace_sheet`, `_build_trace_ladder_sheet`; `app/infra/cli_legacy.py`.",
            tests="`tests/test_user_settings.py` (MentorPipelineTrace export/global_prefilter); `tests/test_excel_export_smoke.py`; pipeline-focused tests under `tests/infra`.",
            evidence="DIRECTLY_CONFIRMED: stage names, fields, and sheet names. INFERRED: the example investigation workflow. NOT_PROVEN: that every row decrease is a defect or the exact instrumentation cost.",
        ),
    ),
    "enable_pool_governance_trace": (
        _fa(
            title="Pool Governance Trace — Trace حاکمیت استخر",
            key="enable_pool_governance_trace",
            mental="صورت‌جلسه‌ای از اینکه ساختار استخر منتورها قبل و بعد از governance/condense چگونه دیده می‌شود.",
            purpose="شواهد ساختاری درباره governance، condense و multi-profile mentorها صادر می‌کند.",
            subsystem="mentor pool governance / profile condensation observability",
            concept="mentor pool مجموعه منتورهای آماده مصرف allocation است. governance یعنی قواعد/مراحل کنترل ساختار و قابلیت استفاده pool؛ profile یک ترکیب مشخص از ویژگی‌های join برای mentor است؛ condense در این context خلاصه‌کردن نمای چند profile به وضعیت قابل بررسی در سطح mentor است. این trace فقط گزارش می‌کند و governance را بازتعریف نمی‌کند.",
            enable_when="تعداد mentor/profile قبل و بعد متفاوت است، multi-profileها مشکوک‌اند یا می‌خواهید breakdown حذف‌ها و توزیع‌ها را ببینید.",
            leave_off="ساختار pool مسئله تحقیق نیست و خروجی فنی اضافه لازم ندارید.",
            allocation="NO — trace گزارش وضعیت pool است.",
            validation="NO — این toggle به‌تنهایی QA gate جدید فعال نمی‌کند.",
            algorithm="NO — governance semantics تغییر نمی‌کند.",
            diagnostic_only="YES.",
            internal="exporter از attrs/payload موجود pool سه DataFrame تشخیصی می‌سازد: governance stage records، condense summary و multi-profile summary.",
            output="sheetهای دقیق `PoolGovernanceTrace`, `PoolCondenseTrace`, `MultiProfileSummary`. فیلدهای governance شامل `stage_name`, `raw_rows`, `after_rows`, `removed_rows`, `removed_breakdown`, `distribution_before`, `distribution_after`, `profile_rows_before/after`, `unique_mentor_ids_before/after` است. Condense شامل counts و quantileهای profiles-per-mentor است؛ MultiProfileSummary شامل `profile_rows`, `unique_mentor_ids`, `multi_profile_mentor_count`, `multi_profile_ratio` است.",
            location="در workbook خروجی‌ای که trace debug sheets به آن افزوده می‌شود.",
            reading="در `PoolGovernanceTrace` هر stage را before/after مقایسه کنید؛ `removed_breakdown` دلیل‌های دسته‌بندی‌شده حذف را نشان می‌دهد اگر payload آن را فراهم کرده باشد. `PoolCondenseTrace` تفاوت profile rows و unique mentors را نشان می‌دهد. `MultiProfileSummary` سهم mentorهای دارای بیش از یک profile را خلاصه می‌کند.",
            example="نشانه: ورودی ۳ profile برای ۲ mentor دارد ولی pool نهایی ۲ ردیف دارد. → trace را روشن کنید. → `PoolCondenseTrace` و `MultiProfileSummary` را بخوانید. → اگر یک mentor چند profile دارد، سپس issues JoinKeyResolver/governance را بررسی کنید؛ اختلاف count به‌تنهایی bug نیست.",
            not_prove="وجود multi-profile mentor به‌تنهایی خطای داده یا تخصیص نیست؛ domain می‌تواند multi-profile را بشناسد و resolver/governance رفتار مشخص خود را دارد.",
            limitations="کیفیت جزئیات به attrs/payload تولیدشده upstream وابسته است؛ نبود payload می‌تواند sheet خالی ایجاد کند.",
            performance="ساخت summaryهای governance و نوشتن سه sheet می‌تواند CPU، memory و workbook size را افزایش دهد؛ logging/DB اضافی مستقل از این toggle اثبات نشده است.",
            related="Mentor Pipeline Trace برای stage-by-stage ingestion؛ Trace Debug Sheets برای خلاصه عمومی؛ QA Pool Coverage برای سؤال «آیا student کاندید قابل استفاده دارد؟».",
            implementation="`app/infra/excel/export_allocations.py::_build_pool_governance_trace_sheet`, `_build_pool_condense_trace_sheet`, `_build_multi_profile_summary_sheet`; payloadهای mentor pool در Infra pipeline/builder.",
            tests="`tests/infra/test_pool_condense_trace.py`; `tests/test_user_settings.py` و تست‌های mentor-pool governance مرتبط.",
            evidence="DIRECTLY_CONFIRMED: سه sheet و ستون‌های builder. INFERRED: تفسیر عملی counts. NOT_PROVEN: اینکه هر condense یا multi-profile وضعیت نامعتبر باشد و هزینه دقیق.",
        ),
        _en(
            title="Pool Governance Trace",
            key="enable_pool_governance_trace",
            mental="A meeting record of how the mentor-pool structure looks before and after governance/condense handling.",
            purpose="Exports structural evidence about governance, condense behavior, and multi-profile mentors.",
            subsystem="mentor pool governance / profile condensation observability",
            concept="The mentor pool is the set of mentors prepared for allocation. Governance means the controls/stages applied to pool structure and usability; a profile is a particular join-attribute combination for a mentor; condense here summarizes profile-level structure toward mentor-level inspection. The trace reports this behavior; it does not redefine governance.",
            enable_when="mentor/profile counts differ, multi-profile behavior is under investigation, or you need removal/distribution evidence.",
            leave_off="pool structure is not the subject of investigation and you do not need extra technical output.",
            allocation="NO — it reports pool state.",
            validation="NO — this toggle alone does not enable a new QA gate.",
            algorithm="NO — governance semantics are unchanged.",
            diagnostic_only="YES.",
            internal="the exporter derives three diagnostic DataFrames from existing pool attrs/payload: governance-stage records, a condense summary, and a multi-profile summary.",
            output="exact sheets `PoolGovernanceTrace`, `PoolCondenseTrace`, and `MultiProfileSummary`. Governance fields include `stage_name`, `raw_rows`, `after_rows`, `removed_rows`, `removed_breakdown`, `distribution_before`, `distribution_after`, `profile_rows_before/after`, and `unique_mentor_ids_before/after`. Condense reports profile/mentor counts and profiles-per-mentor quantiles. MultiProfileSummary reports `profile_rows`, `unique_mentor_ids`, `multi_profile_mentor_count`, and `multi_profile_ratio`.",
            location="the output workbook receiving trace debug sheets.",
            reading="compare before/after per `PoolGovernanceTrace` stage; use `removed_breakdown` when upstream payload provides it. `PoolCondenseTrace` compares profile rows with unique mentors. `MultiProfileSummary` summarizes how many mentors have more than one profile.",
            example="Symptom: input has three profiles for two mentors but the final pool has two rows. → Enable the trace. → Read `PoolCondenseTrace` and `MultiProfileSummary`. → If one mentor has multiple profiles, investigate JoinKeyResolver/governance issues next; the count difference alone is not a bug.",
            not_prove="a multi-profile mentor alone does not prove bad data or incorrect allocation; the domain can represent multiple profiles and resolver/governance has defined handling.",
            limitations="detail quality depends on upstream attrs/payload; missing payload can produce empty diagnostic sheets.",
            performance="building governance summaries and writing three sheets can increase CPU, memory, and workbook size; separate logging/database growth caused solely by this toggle is not proven.",
            related="use Mentor Pipeline Trace for stage-by-stage ingestion, Trace Debug Sheets for broad summaries, and QA Pool Coverage for “does this student have a usable candidate?” questions.",
            implementation="`app/infra/excel/export_allocations.py::_build_pool_governance_trace_sheet`, `_build_pool_condense_trace_sheet`, `_build_multi_profile_summary_sheet`; mentor-pool payload producers in the Infra pipeline/builder.",
            tests="`tests/infra/test_pool_condense_trace.py`; `tests/test_user_settings.py` and related mentor-pool governance tests.",
            evidence="DIRECTLY_CONFIRMED: the three sheets and builder columns. INFERRED: practical interpretation of counts. NOT_PROVEN: that every condense/multi-profile state is invalid or the exact cost.",
        ),
    ),
    "enable_bucket_trace": (
        _fa(
            title="Bucket Trace — Trace باکت",
            key="enable_bucket_trace",
            mental="دوربین روی مرحله narrowing کاندیدها؛ نه کلید روشن‌کردن آن مرحله.",
            purpose="اطلاعات bucketing کاندیدها را برای هر student به sheet قابل بررسی تبدیل می‌کند.",
            subsystem="eligibility candidate bucketing observability",
            concept="Bucket گروهی از کاندیدهای mentor است که بر پایه کلیدهای join برای جست‌وجوی محدودتر ساخته/انتخاب می‌شود. Bucket Trace فقط وضعیت این مرحله را گزارش می‌کند. `Use Join Buckets` setting جداگانه‌ای است که فعال‌بودن مسیر bucketing را کنترل می‌کند.",
            enable_when="می‌خواهید بدانید candidate pool قبل از bucket چقدر بوده، چه bucket key/size استفاده شده یا چرا bucketing skip شده است.",
            leave_off="narrowing کاندیدها موضوع تحقیق نیست.",
            allocation="NO — trace کردن bucket نتیجه را تغییر نمی‌دهد.",
            validation="NO.",
            algorithm="NO — خود trace مسیر را تغییر نمی‌دهد.",
            diagnostic_only="YES.",
            internal="exporter `bucket_trace` موجود در eligibility trace/logs را به DataFrame تبدیل می‌کند. اگر Join Buckets خاموش باشد، core trace مقدار تأییدشده `bucket_skip_reason = disabled_by_setting` را ثبت می‌کند.",
            output="sheet دقیق `BucketTrace` با ستون‌های `student_id`, `pool_built_size`, `pool_size_before_bucket`, `bucket_key`, `bucket_size`, `bucket_skip_reason`, `bucket_key_variants`, `bucket_sizes`.",
            location="در workbook دارای debug trace sheets.",
            reading="برای هر student ابتدا `pool_size_before_bucket` را ببینید. اگر `bucket_skip_reason` مقدار دارد، narrowing انجام نشده یا قابل اجرا نبوده است. `disabled_by_setting` صریحاً یعنی Use Join Buckets خاموش بوده. اگر bucket استفاده شده، key و size نشان می‌دهند جست‌وجو به چه مجموعه‌ای محدود شده است.",
            example="نشانه: می‌خواهید مطمئن شوید optimization در یک run واقعاً استفاده شده. → Bucket Trace را روشن کنید. → اگر `disabled_by_setting` می‌بینید، trace سالم است ولی Use Join Buckets خاموش بوده؛ اگر key/size وجود دارد، narrowing فعال را بررسی کنید.",
            not_prove="کوچک‌شدن bucket به‌تنهایی اثبات نمی‌کند انتخاب mentor صحیح یا سریع‌تر بوده است.",
            limitations="بدون logs/eligibility_trace مناسب sheet می‌تواند خالی باشد. Trace به‌تنهایی Use Join Buckets را روشن نمی‌کند.",
            performance="ساخت یک sheet per-student diagnostic می‌تواند CPU، memory و workbook size را افزایش دهد؛ الگوریتم allocation را از طریق این toggle تغییر نمی‌دهد.",
            related="Use Join Buckets کنترل الگوریتم است؛ Bucket Trace ناظر آن است. برای stageهای eligibility گسترده‌تر Mentor Pipeline Trace/EligibilityTrace را ببینید.",
            implementation="`app/core/common/eligibility_channel.py` (bucket trace payload/skip reasons); `app/infra/excel/export_allocations.py::_build_bucket_trace_sheet`.",
            tests="`tests/infra/test_bucket_trace_flags.py`; `tests/integration/test_join_bucketing_edge_cases.py`.",
            evidence="DIRECTLY_CONFIRMED: `BucketTrace` columns و `disabled_by_setting`. INFERRED: workflow بررسی optimization. NOT_PROVEN: performance gain یا correctness صرفاً از روی bucket size.",
        ),
        _en(
            title="Bucket Trace",
            key="enable_bucket_trace",
            mental="A camera pointed at candidate narrowing, not the switch that enables narrowing.",
            purpose="Turns per-student bucketing information into an inspectable sheet.",
            subsystem="eligibility candidate bucketing observability",
            concept="A bucket is a group of mentor candidates formed/selected from join keys so search can be narrowed. Bucket Trace only reports this stage. `Use Join Buckets` is the separate setting that enables the bucketing execution path.",
            enable_when="you need to know the candidate-pool size before bucketing, the bucket key/size used, or why bucketing was skipped.",
            leave_off="candidate narrowing is not under investigation.",
            allocation="NO — tracing the bucket does not change the result.",
            validation="NO.",
            algorithm="NO — the trace itself does not change the path.",
            diagnostic_only="YES.",
            internal="the exporter converts the `bucket_trace` payload already present in eligibility trace/logs into a DataFrame. When Join Buckets is off, core trace records the confirmed value `bucket_skip_reason = disabled_by_setting`.",
            output="exact sheet `BucketTrace` with `student_id`, `pool_built_size`, `pool_size_before_bucket`, `bucket_key`, `bucket_size`, `bucket_skip_reason`, `bucket_key_variants`, and `bucket_sizes`.",
            location="the workbook containing debug trace sheets.",
            reading="for each student, start with `pool_size_before_bucket`. A non-empty `bucket_skip_reason` means narrowing was skipped/unavailable. `disabled_by_setting` explicitly means Use Join Buckets was off. When a bucket is used, key/size show which candidate set was searched.",
            example="Symptom: you want to verify whether the optimization was actually used in a run. → Enable Bucket Trace. → If you see `disabled_by_setting`, tracing is working but Use Join Buckets was off; if key/size are present, inspect the active narrowing.",
            not_prove="a smaller bucket alone does not prove the mentor choice was correct or faster.",
            limitations="without suitable logs/eligibility_trace the sheet can be empty. This trace never enables Use Join Buckets by itself.",
            performance="building a per-student diagnostic sheet can increase CPU, memory, and workbook size; this toggle does not change the allocation algorithm.",
            related="Use Join Buckets controls the algorithm; Bucket Trace observes it. Use Mentor Pipeline Trace/EligibilityTrace for broader eligibility-stage evidence.",
            implementation="`app/core/common/eligibility_channel.py` (bucket trace payload/skip reasons); `app/infra/excel/export_allocations.py::_build_bucket_trace_sheet`.",
            tests="`tests/infra/test_bucket_trace_flags.py`; `tests/integration/test_join_bucketing_edge_cases.py`.",
            evidence="DIRECTLY_CONFIRMED: `BucketTrace` columns and `disabled_by_setting`. INFERRED: optimization-inspection workflow. NOT_PROVEN: performance gain or correctness from bucket size alone.",
        ),
    ),
    "enable_trace_export": (
        _fa(
            title="Trace Sheet Export — خروجی شیت Trace",
            key="enable_trace_export",
            mental="ذخیره نسخه خام‌تر «جعبه سیاه پرواز» برای توسعه‌دهنده، کنار نتیجه معمول کاربر.",
            purpose="DataFrame خام trace را به‌عنوان sheet اضافی در workbook خروجی نگه می‌دارد.",
            subsystem="raw allocation trace export",
            concept="خروجی معمول کاربر برای مصرف عملیاتی طراحی شده است؛ raw trace برای forensic/debugging است و می‌تواند جزئیات داخلی بیشتری داشته باشد. این setting فقط export آن نمای خام را کنترل می‌کند.",
            enable_when="برای بازبینی فنی عمیق، reproduction یا مقایسه تصمیمات به trace خام نیاز دارید.",
            leave_off="کاربر عادی فقط نتیجه عملیاتی را لازم دارد و workbook developer-oriented اضافی نمی‌خواهد.",
            allocation="NO.",
            validation="NO.",
            algorithm="NO.",
            diagnostic_only="YES — export forensic اضافی.",
            internal="در `cli_legacy.py` وقتی `enable_trace_export` روشن است، `trace_df` Excel-safe می‌شود و با کلید sheet دقیق `trace` به مجموعه sheets اضافه می‌شود.",
            output="sheet دقیق `trace`. محتوای columns به trace DataFrame تولیدشده توسط run بستگی دارد و نباید به‌عنوان یک گزارش خلاصه کاربر تفسیر شود.",
            location="در workbook اصلی خروجی همان run که sheets در آن نوشته می‌شوند.",
            reading="از شناسه student/mentor و stage/reasonهای موجود برای دنبال‌کردن مسیر تصمیم استفاده کنید. ابتدا مشخص کنید کدام ستون canonical/trace field است؛ raw trace ممکن است برای خواننده غیرتوسعه‌دهنده متراکم باشد.",
            example="نشانه: دو run ظاهراً نتیجه متفاوت دارند و summary کافی نیست. → Trace Sheet Export را روشن کنید. → sheet `trace` دو run را با ورودی/Policy یکسان مقایسه کنید. → اختلاف stage/data را پیدا کنید؛ سپس علت را در source data یا ابزار تخصصی‌تر بررسی کنید.",
            not_prove="وجود trace خام اثبات نمی‌کند تصمیم domain صحیح است؛ فقط شواهدی از داده/مسیر ثبت‌شده فراهم می‌کند.",
            limitations="schema عملی trace می‌تواند با داده‌های موجود/نسخه implementation مرتبط باشد؛ برای مصرف external ثابت طراحی نشده مگر قرارداد جداگانه‌ای آن را تضمین کند.",
            performance="Excel-safe conversion و نوشتن trace می‌تواند CPU، memory و به‌خصوص workbook size را افزایش دهد. log/database اضافی مستقل از خود export اثبات نشده است.",
            related="Trace Debug Sheets برای نماهای خلاصه‌تر؛ Mentor Pipeline/Pool/Bucket Trace برای سؤال‌های تخصصی‌تر معمولاً خواناترند.",
            implementation="`app/infra/cli_legacy.py` branch مربوط به `enable_trace_export`; trace producerهای allocation در Core/Infra.",
            tests="`tests/test_excel_export_smoke.py`; `tests/test_user_settings.py`; trace provenance/invariance tests موجود.",
            evidence="DIRECTLY_CONFIRMED: setting wiring و sheet name `trace`. INFERRED: روش مقایسه runها. NOT_PROVEN: ثبات دائمی همه raw columns یا هزینه دقیق.",
        ),
        _en(
            title="Trace Sheet Export",
            key="enable_trace_export",
            mental="Save a rawer flight-recorder view for developers next to the normal user result.",
            purpose="Keeps the raw trace DataFrame as an additional output-workbook sheet.",
            subsystem="raw allocation trace export",
            concept="The normal user result is designed for operations; raw trace is developer/forensic material and can contain denser internal detail. This setting controls exporting that raw view only.",
            enable_when="you need deep technical review, reproduction evidence, or comparison of decision traces.",
            leave_off="a normal operator only needs operational output and does not need a developer-oriented trace sheet.",
            allocation="NO.",
            validation="NO.",
            algorithm="NO.",
            diagnostic_only="YES — additional forensic export.",
            internal="in `cli_legacy.py`, when `enable_trace_export` is on, `trace_df` is converted to an Excel-safe form and added to the sheet map under the exact key `trace`.",
            output="exact sheet `trace`. Its columns depend on the trace DataFrame produced by the run and should not be treated as a simplified user report.",
            location="the main output workbook for that run where sheets are written.",
            reading="use student/mentor identifiers and available stage/reason fields to follow the recorded decision path. Identify canonical/trace fields first; raw trace can be dense for non-developers.",
            example="Symptom: two runs appear to differ and summaries are insufficient. → Enable Trace Sheet Export. → Compare the `trace` sheets with equivalent inputs/Policy. → Locate the stage/data difference, then investigate source data or a specialized trace.",
            not_prove="a raw trace does not prove the domain decision is correct; it provides evidence of recorded data/path behavior.",
            limitations="the practical raw-trace schema can depend on available data/implementation version unless a separate contract freezes it for external consumers.",
            performance="Excel-safe conversion and trace writing can increase CPU, memory, and especially workbook size. Separate log/database growth caused solely by this export is not proven.",
            related="Trace Debug Sheets gives more summarized views; Mentor Pipeline/Pool/Bucket traces are usually easier for specialized questions.",
            implementation="the `enable_trace_export` branch in `app/infra/cli_legacy.py`; allocation trace producers in Core/Infra.",
            tests="`tests/test_excel_export_smoke.py`; `tests/test_user_settings.py`; existing trace provenance/invariance tests.",
            evidence="DIRECTLY_CONFIRMED: setting wiring and exact `trace` sheet name. INFERRED: run-comparison workflow. NOT_PROVEN: permanent stability of every raw column or exact cost.",
        ),
    ),
    "enable_qa_pool_coverage_rules": (
        _fa(
            title="QA Pool Coverage Rules — قواعد QA پوشش استخر",
            key="enable_qa_pool_coverage_rules",
            mental="بازرس اضافی که می‌پرسد «آیا برای هر دانش‌آموز حداقل یک کاندید مطابق join keys در pool نهایی وجود دارد؟».",
            purpose="دو بررسی QA اضافی pool coverage/diversity را به گزارش QA اضافه می‌کند؛ یکی از آن‌ها می‌تواند FAIL ایجاد کند.",
            subsystem="QA validation and mentor-pool alignment preflight",
            concept="Coverage یعنی امکان پوشش‌دادن student توسط حداقل یک candidate mentor مطابق کلیدهای join. وقتی `candidate_count_final == 0` باشد، `QA_RULE_POOL_COVERAGE_01` violation سطح error می‌سازد و `passed=False` می‌شود. `QA_RULE_POOL_DIVERSITY_01` نیز برای group/gender/graduation_status تنوع بسیار محدود را warning می‌کند اما خودش `passed=True` می‌ماند.",
            enable_when="می‌خواهید run به‌طور صریح نبود candidate مطابق را به‌عنوان failure QA بگیرد یا کیفیت پوشش pool را قبل/همراه خروجی بررسی کنید.",
            leave_off="نمی‌خواهید این دو rule اختیاری در تصمیم QA این run شرکت کنند. خاموش‌کردن به معنی حل‌شدن مشکل coverage نیست؛ فقط این gate اختیاری را اجرا نمی‌کند.",
            allocation="NO — allocation DataFrame را مستقیماً تغییر نمی‌دهد.",
            validation="YES — `QA_RULE_POOL_COVERAGE_01` می‌تواند `QaReport.passed` را از True به False ببرد.",
            algorithm="NO برای الگوریتم allocation؛ preflight/QA checks اضافی اجرا می‌شوند.",
            diagnostic_only="NO — MAY AFFECT VALIDATION.",
            internal="`cli_legacy.py` فقط هنگام روشن‌بودن setting، `pool_alignment_preflight` را به `run_all_invariants` می‌دهد و `enable_pool_coverage_rules=True` می‌کند. invariant runner `QA_RULE_POOL_COVERAGE_01` و `QA_RULE_POOL_DIVERSITY_01` را اضافه می‌کند. QaReport.passed برابر all(result.passed) است؛ بنابراین coverage failure روی PASS/FAIL کل اثر دارد.",
            output="در QA workbook، وقتی ruleها در report حضور دارند، sheetهای دقیق `PoolCoverageFailures` و `PoolDiversityReport` ساخته می‌شوند. Coverage details شامل `student_id`, `first_failing_stage`, `expected_value`, `available_values` و join-key values موجود است.",
            location="در QA validation workbook همان run و در status/details گزارش QA.",
            reading="ابتدا `PoolCoverageFailures` را بخوانید. `first_failing_stage` اولین stageای است که candidateها به صفر رسیده‌اند؛ `expected_value` مقدار مورد انتظار student و `available_values` نمونه مقادیر موجود pool است. `PoolDiversityReport` warning تحلیلی است و coverage failure نیست.",
            example="نشانه: student S-42 تخصیص نمی‌گیرد و می‌خواهید run این وضعیت را fail کند. → QA Pool Coverage را روشن کنید. → `PoolCoverageFailures` نشان می‌دهد اولین شکست مثلاً graduation_status بوده است. → expected/available را با داده pool و effective join keys بررسی کنید.",
            not_prove="coverage PASS اثبات نمی‌کند ranking/ظرفیت/انتخاب نهایی صحیح است؛ فقط وجود candidate مطابق طبق این preflight/rule را نشان می‌دهد.",
            limitations="اگر preflight None/empty باشد coverage rule pass خالی برمی‌گرداند. Diversity rule warning است و PASS/FAIL را تغییر نمی‌دهد.",
            performance="ساخت preflight و اجرای ruleهای اضافی می‌تواند CPU/memory و اندازه QA workbook را افزایش دهد؛ خروجی‌های QA بیشتری ذخیره می‌شوند. هزینه دقیق و اثر DB مستقل NOT MEASURED/NOT PROVEN است.",
            related="Mentor Pipeline/Pool Governance Trace برای فهم علت آماده‌سازی pool؛ Eligibility/Trace Debug برای مسیر candidate؛ این setting زمانی مناسب است که outcome باید validation consequence داشته باشد.",
            implementation="`app/core/qa/invariants.py::check_POOL_COVERAGE_01`, `check_POOL_DIVERSITY_01`, `run_all_invariants`, `QaReport.passed`; `app/infra/cli_legacy.py`; `app/infra/excel/export_qa_validation.py`.",
            tests="`tests/infra/test_qa_pool_coverage_rules.py`; `tests/core/test_pool_alignment_center_inference.py`; `tests/integration/test_alignment_allocation_parity.py`.",
            evidence="DIRECTLY_CONFIRMED: دو rule، failure semantics، QaReport aggregation و sheet names. INFERRED: troubleshooting sequence. NOT_PROVEN: اینکه coverage PASS correctness کامل allocation را تضمین کند یا هزینه دقیق.",
        ),
        _en(
            title="QA Pool Coverage Rules",
            key="enable_qa_pool_coverage_rules",
            mental="An extra inspector asking, “Does every student have at least one final-pool mentor candidate matching the join keys?”",
            purpose="Adds two optional pool coverage/diversity QA checks; one can create a validation failure.",
            subsystem="QA validation and mentor-pool alignment preflight",
            concept="Coverage means a student can be covered by at least one mentor candidate matching join keys. When `candidate_count_final == 0`, `QA_RULE_POOL_COVERAGE_01` emits an error violation and returns `passed=False`. `QA_RULE_POOL_DIVERSITY_01` also warns when group/gender/graduation_status diversity is unusually narrow, but that rule itself remains `passed=True`.",
            enable_when="you want missing matching candidates to participate explicitly in QA failure, or you need stronger pool-coverage validation for the run.",
            leave_off="you do not want these optional rules participating in this run's QA decision. Turning them off does not fix coverage; it only stops this optional gate from executing.",
            allocation="NO — it does not directly rewrite the allocation DataFrame.",
            validation="YES — `QA_RULE_POOL_COVERAGE_01` can change `QaReport.passed` from True to False.",
            algorithm="NO for allocation; additional preflight/QA checks execute.",
            diagnostic_only="NO — MAY AFFECT VALIDATION.",
            internal="`cli_legacy.py` supplies `pool_alignment_preflight` and sets `enable_pool_coverage_rules=True` only when enabled. The invariant runner adds `QA_RULE_POOL_COVERAGE_01` and `QA_RULE_POOL_DIVERSITY_01`. `QaReport.passed` is `all(result.passed)`, so a coverage failure affects overall PASS/FAIL.",
            output="when the rules are present in the report, the QA workbook adds exact sheets `PoolCoverageFailures` and `PoolDiversityReport`. Coverage details include `student_id`, `first_failing_stage`, `expected_value`, `available_values`, and available join-key values.",
            location="the run's QA validation workbook and QA status/details.",
            reading="start with `PoolCoverageFailures`. `first_failing_stage` identifies the first stage where candidates reached zero; `expected_value` is the student's required value and `available_values` samples pool values. `PoolDiversityReport` is an analytical warning, not the coverage failure itself.",
            example="Symptom: student S-42 remains unallocated and you want the run to fail validation for missing coverage. → Enable QA Pool Coverage. → `PoolCoverageFailures` may identify graduation_status as the first failure. → Compare expected/available values with pool data and effective join keys.",
            not_prove="a coverage PASS does not prove ranking, capacity, or final mentor selection is correct; it proves only the candidate-availability condition checked by this preflight/rule.",
            limitations="if preflight is None/empty, the coverage rule returns an empty pass. The diversity rule is warning-only and does not fail QA.",
            performance="building preflight and running extra rules can increase CPU/memory and QA-workbook size; more QA output may be stored. Exact cost and independent database impact are NOT MEASURED/NOT PROVEN.",
            related="use Mentor Pipeline/Pool Governance Trace to understand pool preparation and Eligibility/Trace Debug for candidate paths; use this setting when the finding must have a validation consequence.",
            implementation="`app/core/qa/invariants.py::check_POOL_COVERAGE_01`, `check_POOL_DIVERSITY_01`, `run_all_invariants`, `QaReport.passed`; `app/infra/cli_legacy.py`; `app/infra/excel/export_qa_validation.py`.",
            tests="`tests/infra/test_qa_pool_coverage_rules.py`; `tests/core/test_pool_alignment_center_inference.py`; `tests/integration/test_alignment_allocation_parity.py`.",
            evidence="DIRECTLY_CONFIRMED: both rules, failure semantics, QaReport aggregation, and sheet names. INFERRED: troubleshooting sequence. NOT_PROVEN: that coverage PASS proves complete allocation correctness or the exact cost.",
        ),
    ),
    "use_join_buckets": (
        _fa(
            title="Use Join Buckets — استفاده از Join Buckets",
            key="use_join_buckets",
            mental="قبل از جست‌وجوی کامل candidate pool، قفسه مناسب را با join keys انتخاب کن و داخل همان قفسه جست‌وجو کن.",
            purpose="یک مسیر الگوریتمی اختیاری برای narrowing کاندیدها با index/bucketهای join است.",
            subsystem="allocation eligibility candidate search",
            concept="Bucketing کاندیدها را بر پایه join-key index به گروه‌های کوچک‌تر تقسیم/بازیابی می‌کند تا به‌جای بررسی pool کامل، مجموعه محدودتری بررسی شود. این گزینه diagnostic نیست. default آن False است. وقتی خاموش است eligibility channel candidate_pool کامل را نگه می‌دارد و trace دلیل `disabled_by_setting` ثبت می‌کند.",
            enable_when="دلیل فنی مشخص برای ارزیابی مسیر optimization دارید و parity/determinism guardها را همراه run بررسی می‌کنید.",
            leave_off="کاربر عادی هستید یا نیاز عملکردی اثبات‌شده ندارید؛ default عمداً OFF است.",
            allocation="CONDITIONAL — طراحی و parity tests هدفشان برابری نتیجه است، اما مسیر candidate search متفاوت است و تست‌ها اثبات جهانی همه ورودی‌های ممکن نیستند.",
            validation="NO مستقیم — setting QA rule جدیدی فعال نمی‌کند؛ با این حال هر drift الگوریتمی بالقوه می‌تواند downstream evidence را تغییر دهد، که تست‌های parity برای جلوگیری از آن وجود دارند.",
            algorithm="YES — مسیر narrowing/search کاندیدها تغییر می‌کند.",
            diagnostic_only="NO — ADVANCED ALGORITHMIC / PERFORMANCE OPTION.",
            internal="`cli_legacy.py` مقدار setting را به `allocate_batch(... use_join_buckets=...)` می‌دهد. eligibility channel وقتی enabled باشد از `join_bucket_index` برای انتخاب candidate subset استفاده می‌کند؛ وقتی disabled باشد pool بدون narrowing bucket عبور می‌کند. Bucket trace metadata اندازه/key/skip reason را ثبت می‌کند.",
            output="خود setting artifact مستقل تضمین‌شده‌ای تولید نمی‌کند. برای مشاهده رفتار، Bucket Trace را جداگانه روشن کنید؛ آن‌وقت `BucketTrace` key/size/skip reason را نشان می‌دهد. risk register همچنین مقایسه runtime/memory از `metrics.json` را پیشنهاد می‌کند، اما وجود/معنای آن برای هر run در این راهنما تضمین نمی‌شود.",
            location="اثر اصلی در execution path است؛ evidence قابل مشاهده در trace/log/outputهای موجود و در صورت روشن‌بودن Bucket Trace در sheet `BucketTrace` دیده می‌شود.",
            reading="اگر Bucket Trace فعال است، `pool_size_before_bucket` را با `bucket_size` مقایسه کنید. `disabled_by_setting` یعنی این option خاموش بوده. سپس نتیجه allocation را با baseline OFF در همان fixture/input مقایسه کنید؛ فقط کوچک‌ترشدن candidate set معیار موفقیت نیست.",
            example="نیاز: pool بسیار بزرگ است و می‌خواهید optimization را ارزیابی کنید. → baseline با OFF را نگه دارید. → option را ON کنید و parity/determinism tests را اجرا کنید. → با Bucket Trace narrowing را تأیید کنید. → اگر allocation DataFrame یا ordering از baseline منحرف شد، option را برای آن بررسی/rollback کنید؛ این PR الگوریتم را تغییر نمی‌دهد.",
            not_prove="عبور parity tests موجود اثبات ریاضی برای تمام wildcard/school/center/inputهای ممکن نیست؛ فقط سناریوهای تحت پوشش را محافظت می‌کند. همچنین ON بودن به‌تنهایی performance gain تضمین نمی‌کند.",
            limitations="risk register صریحاً silent behavioral drift در wildcard paths را ریسک می‌داند و re-run determinism/golden parity را توصیه می‌کند. default OFF باقی می‌ماند.",
            performance="هدف optimization کارایی است، اما gain واقعی CPU/memory برای workload شما NOT MEASURED در این work unit است. ساخت index/bucket نیز هزینه دارد؛ نتیجه باید با measurement ارزیابی شود.",
            related="Bucket Trace ابزار مشاهده این مسیر است. تست‌های parity/determinism مهم‌تر از Trace Debug Sheets برای تصمیم فعال‌سازی هستند.",
            implementation="`app/core/allocate_students.py::allocate_batch`; `app/core/common/eligibility_channel.py`; wiring در `app/infra/cli_legacy.py`; risk documentation در `docs/performance/RISK_REGISTER_join_bucketing.md`.",
            tests="`tests/integration/test_join_bucketing_flag_parity.py`; `tests/integration/test_join_bucketing_edge_cases.py`; `tests/integration/test_ranking_heap_parity.py` و determinism/golden guards مرتبط.",
            evidence="DIRECTLY_CONFIRMED: default False، wiring به allocate_batch، `disabled_by_setting`، parity test coverage و risk register. INFERRED: توصیه عملی baseline comparison. NOT_PROVEN: performance gain روی workload خاص یا equivalence مطلق همه ورودی‌ها.",
        ),
        _en(
            title="Use Join Buckets",
            key="use_join_buckets",
            mental="Choose the join-key shelf first, then search that shelf instead of scanning the whole candidate pool.",
            purpose="An optional algorithmic path that narrows candidates using join indexes/buckets.",
            subsystem="allocation eligibility candidate search",
            concept="Bucketing partitions/retrieves candidates by a join-key index so a smaller set can be searched instead of the full pool. This is not a diagnostic setting. Its default is False. When off, eligibility keeps the full candidate pool and trace records `disabled_by_setting` as the skip reason.",
            enable_when="you have a specific technical reason to evaluate the optimization path and will run parity/determinism guards with it.",
            leave_off="you are a normal user or do not have a demonstrated performance need; the default is intentionally OFF.",
            allocation="CONDITIONAL — design and parity tests aim for equivalent results, but the candidate-search path is different and tests are not a universal proof for every possible input.",
            validation="NO direct QA-rule effect — this setting does not enable a QA rule; however any hypothetical algorithm drift could affect downstream evidence, which parity tests are intended to detect.",
            algorithm="YES — candidate narrowing/search execution changes.",
            diagnostic_only="NO — ADVANCED ALGORITHMIC / PERFORMANCE OPTION.",
            internal="`cli_legacy.py` passes the setting into `allocate_batch(... use_join_buckets=...)`. When enabled, eligibility uses `join_bucket_index` to select a candidate subset; when disabled, the full pool passes without bucket narrowing. Bucket trace metadata records sizes/keys/skip reasons.",
            output="the setting itself guarantees no standalone artifact. Enable Bucket Trace separately to observe `BucketTrace` key/size/skip reason. The risk register also recommends comparing runtime/memory via `metrics.json`, but this guide does not guarantee that artifact for every run.",
            location="the primary effect is the execution path; observable evidence appears in existing trace/log/output and, with Bucket Trace enabled, in the `BucketTrace` sheet.",
            reading="with Bucket Trace on, compare `pool_size_before_bucket` with `bucket_size`. `disabled_by_setting` means this option was off. Then compare allocation results against an OFF baseline on equivalent input; a smaller candidate set alone is not the success criterion.",
            example="Need: a very large pool motivates optimization evaluation. → Keep an OFF baseline. → Turn the option ON and run parity/determinism tests. → Use Bucket Trace to verify narrowing. → If allocation DataFrame/order diverges from baseline, investigate/roll back the option for that case; this PR does not change the algorithm itself.",
            not_prove="passing current parity tests is not a mathematical proof for every wildcard/school/center/input combination. Enabling the option also does not guarantee a performance gain.",
            limitations="the risk register explicitly calls out possible silent drift around wildcard paths and recommends determinism/golden parity reruns. Default remains OFF.",
            performance="performance is the optimization objective, but actual CPU/memory gain for your workload is NOT MEASURED in this work unit. Building/using indexes also has cost; evaluate with measurement.",
            related="Bucket Trace observes this path. Parity/determinism tests are more important than general debug sheets when deciding whether to enable it.",
            implementation="`app/core/allocate_students.py::allocate_batch`; `app/core/common/eligibility_channel.py`; wiring in `app/infra/cli_legacy.py`; `docs/performance/RISK_REGISTER_join_bucketing.md`.",
            tests="`tests/integration/test_join_bucketing_flag_parity.py`; `tests/integration/test_join_bucketing_edge_cases.py`; `tests/integration/test_ranking_heap_parity.py` and related determinism/golden guards.",
            evidence="DIRECTLY_CONFIRMED: default False, allocate_batch wiring, `disabled_by_setting`, parity-test coverage, and risk register. INFERRED: baseline-comparison recommendation. NOT_PROVEN: workload-specific performance gain or absolute equivalence for all possible inputs.",
        ),
    ),
}

# Add the remaining two diagnostics after the core dictionary so their content
# stays independently reviewable while keeping the same runtime lookup shape.
GUIDES["enable_pool_governance_trace"] = GUIDES["enable_pool_governance_trace"]

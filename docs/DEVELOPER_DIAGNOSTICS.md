# Matrix Developer Diagnostics

> Canonical technical inventory for the intentionally retained diagnostics, analysis, and advanced execution controls.
>
> این سند موجودی فنی کاننیکال ابزارهای خطایابی، تحلیل و گزینه‌های اجرای پیشرفته‌ای است که عمداً حفظ شده‌اند.

This document is subordinate to LAW / Technical SSoT for domain semantics. It documents current code-backed behavior; it does not create allocation, ranking, capacity, join, history, QA, or Rule Engine rules.

---

## 1. Retention and Rule Engine status

- **Rule Engine GUI:** **RETIRED** from the normal end-user workspace.
- **Rule Engine backend / CLI:** **INTENTIONALLY PRESERVED**.
- `app/core/rule_engine.py` and CLI `rule-engine` are not dead code merely because the GUI surface is absent.
- The eight capabilities below are intentionally retained. **Default OFF does not mean dead code.**

### وضعیت فارسی

- **GUI موتور قواعد:** از فضای عادی کاربر **بازنشسته** شده است.
- **Backend / CLI موتور قواعد:** **عمداً حفظ شده است**.
- نبودن Rule Engine در GUI مجوز حذف `app/core/rule_engine.py` یا CLI `rule-engine` نیست.
- هشت قابلیت زیر عمداً پشتیبانی می‌شوند؛ **OFF بودن پیش‌فرض به معنی dead code بودن نیست**.

---

## 2. Shared configuration contract / قرارداد مشترک تنظیمات

All eight controls are fields of `app.infra.config_flags.UserSettings`.

- Default for every capability: `False` / OFF.
- Default persistence path: `~/.smart_alloc/user_settings.json`.
- Persistence format: JSON via `save_user_settings`; reload via `load_user_settings`.
- Turning a capability OFF affects later runs; it does **not** delete workbooks, sheets, logs, or other artifacts produced previously.
- The UI catalog under `app/ui/preferences/` is presentation-only and is not a second configuration authority.

تمام هشت کنترل، فیلدهای `UserSettings` هستند. مقدار پیش‌فرض همه `False` است و در مسیر پیش‌فرض `~/.smart_alloc/user_settings.json` ذخیره می‌شوند. خاموش‌کردن یک گزینه artifactهای قبلی را پاک نمی‌کند. catalog رابط کاربری فقط presentation است و منبع تنظیمات جدیدی ایجاد نمی‌کند.

---

## 3. Inventory / موجودی

| Capability | Setting key | Category | Allocation impact | Validation impact | Algorithm path | Primary exact artifacts |
| --- | --- | --- | --- | --- | --- | --- |
| History Metrics | `enable_history_metrics` | Analysis | NO | NO | NO | `HistoryMetrics` when debug-sheet export path is active; `HistoryMetrics[...]` logging |
| Trace Debug Sheets | `enable_trace_debug_sheets` | Diagnostics / Observability | NO | NO | NO | `summary_df`, `FinalStatus_counts`, `JoinKeyProvenance_counts`, `HistoryMetrics`, conditional `unallocated_summary`, `policy_violations` |
| Mentor Pipeline Trace | `enable_mentor_trace_debug` | Diagnostics / Observability | NO | NO | NO | `EligibilityTrace`, `TraceLadder`, `MentorPipelineTrace` |
| Pool Governance Trace | `enable_pool_governance_trace` | Diagnostics / Observability | NO | NO | NO | `PoolGovernanceTrace`, `PoolCondenseTrace`, `MultiProfileSummary` |
| Bucket Trace | `enable_bucket_trace` | Diagnostics / Observability | NO | NO | NO | `BucketTrace` |
| QA Pool Coverage Rules | `enable_qa_pool_coverage_rules` | Advanced Validation | NO | **YES** | NO | QA rules plus `PoolCoverageFailures`, `PoolDiversityReport` |
| Trace Sheet Export | `enable_trace_export` | Diagnostics / Observability | NO | NO | NO | raw sheet `trace` |
| Use Join Buckets | `use_join_buckets` | Advanced Execution | **CONDITIONAL** | no direct QA rule | **YES** | no guaranteed standalone artifact; observe with `BucketTrace` |

`CONDITIONAL` for Join Buckets means: current parity tests protect equivalence in tested scenarios, but a different candidate-search execution path is used; tests are not a mathematical proof for every possible input.

---

# 4. History Metrics

## فارسی

**مدل ذهنی:** یک داشبورد آماری برای رابطه نتیجه جاری با سابقه، نه کل موتور تاریخچه.

**چه کاری می‌کند؟** وقتی `enable_history_metrics` روشن باشد، مسیر CLI متریک‌های تاریخچه را محاسبه/لاگ می‌کند. ستون‌های تأییدشده در `METRIC_COLUMNS` عبارت‌اند از `allocation_channel`, `students_total`, `history_already_allocated`, `history_no_history_match`, `history_missing_or_invalid`, `same_history_mentor_true`, `same_history_mentor_ratio`. نسبت `same_history_mentor_ratio` سهم دانش‌آموزانی است که mentor انتخاب‌شده با mentor تاریخچه یکسان بوده است.

**چه زمانی روشن شود؟** وقتی می‌خواهید بدانید سابقه چقدر موجود/معتبر بوده، چند مورد match نشده یا منتور تاریخی با چه نسبتی حفظ شده است. **چه زمانی خاموش بماند؟** وقتی فقط خروجی عملیاتی لازم است.

**اثر رفتاری:** تخصیص = **NO**؛ validation = **NO**؛ مسیر الگوریتم = **NO**. خاموش‌کردن History Metrics به معنی خاموش‌شدن همه history-aware allocation behavior نیست.

**خروجی:** logهای `HistoryMetrics[...]` و، وقتی standard debug-sheet path نیز فعال باشد، sheet دقیق `HistoryMetrics`. هر ردیف را بر اساس `allocation_channel` بخوانید و `students_total` را مخرج جمعیت در نظر بگیرید.

**مثال:** اگر نسبت حفظ منتور قبلی پایین به‌نظر می‌رسد، متریک‌ها را روشن کنید؛ اگر `history_missing_or_invalid` بالا است ابتدا داده تاریخچه را بررسی کنید. ratio پایین به‌تنهایی خرابی ranking را ثابت نمی‌کند.

**محدودیت:** summary است و علت تصمیم یک student را ثابت نمی‌کند. هزینه CPU/memory/log/workbook دقیق: **NOT MEASURED**.

**نقشه پیاده‌سازی:** `app/core/allocation/history_metrics.py::compute_history_metrics`, `app/infra/cli_legacy.py`, `app/infra/excel/export_allocations.py::_build_history_metrics_sheet`, `app/ui/history_metrics.py`.

**تست‌ها:** `tests/core/allocation/test_history_metrics.py`, `tests/infra/test_history_metrics_logging.py`, `tests/test_user_settings.py`.

**Evidence:** ستون‌ها، wiring و sheet/log = **DIRECTLY_CONFIRMED**؛ تفسیر troubleshooting = **INFERRED**؛ هزینه دقیق و علت جهان‌شمول یک ratio = **NOT_PROVEN**.

## English

**Mental model:** a statistical dashboard relating the current result to history, not the whole history engine.

**What it does:** with `enable_history_metrics` enabled, the CLI path computes/logs history metrics. Confirmed `METRIC_COLUMNS` are `allocation_channel`, `students_total`, `history_already_allocated`, `history_no_history_match`, `history_missing_or_invalid`, `same_history_mentor_true`, and `same_history_mentor_ratio`. The ratio is the share of students whose selected mentor matches the history mentor.

**When to enable:** when you need to quantify valid/missing history, unmatched history, or prior-mentor retention. **Leave OFF:** when routine operational output is sufficient.

**Behavior:** allocation = **NO**; validation = **NO**; algorithm path = **NO**. Disabling History Metrics does not disable all history-aware allocation behavior.

**Output:** `HistoryMetrics[...]` logs and, when standard debug sheets are also emitted, the exact `HistoryMetrics` sheet. Read rows by `allocation_channel`; `students_total` is the population denominator.

**Example:** if prior-mentor retention looks low, enable metrics. A high `history_missing_or_invalid` count points first to history-data quality; a low ratio does not by itself prove ranking is broken.

**Limitations:** summary reporting does not prove the cause of an individual decision. Exact CPU/memory/log/workbook cost: **NOT MEASURED**.

**Implementation:** `app/core/allocation/history_metrics.py::compute_history_metrics`, `app/infra/cli_legacy.py`, `app/infra/excel/export_allocations.py::_build_history_metrics_sheet`, `app/ui/history_metrics.py`.

**Tests:** `tests/core/allocation/test_history_metrics.py`, `tests/infra/test_history_metrics_logging.py`, `tests/test_user_settings.py`.

**Evidence:** columns/wiring/artifacts = **DIRECTLY_CONFIRMED**; troubleshooting interpretation = **INFERRED**; exact cost or universal causal meaning = **NOT_PROVEN**.

---

# 5. Trace Debug Sheets

## فارسی

**مدل ذهنی:** چند پنجره بازرسی Excel روی همان run، بدون عوض‌کردن تصمیم موتور.

`enable_trace_debug_sheets` به `collect_trace_debug_sheets(... enable_standard_debug_sheets=...)` وصل است. Trace یعنی ثبت مرحله‌به‌مرحله اطلاعاتی که Matrix هنگام پردازش مصرف یا تولید می‌کند. این setting trace کاننیکال را بازتعریف نمی‌کند؛ نماهای تشخیصی می‌سازد.

**زمان استفاده:** وقتی summary نهایی برای توضیح unallocated، final status یا provenance کلید join کافی نیست. **خاموش:** run عادی و workbook سبک‌تر.

**اثر:** allocation = **NO**؛ validation = **NO**؛ algorithm path = **NO**؛ diagnostic output = **YES**.

**نام sheetهای تأییدشده:** `summary_df`, `FinalStatus_counts`, `JoinKeyProvenance_counts`, `HistoryMetrics`, و در صورت وجود داده `unallocated_summary`, `policy_violations`. بعضی sheetها conditional هستند.

**خواندن:** `FinalStatus_counts` تعداد final statusها؛ `JoinKeyProvenance_counts` شمارش inferred/defaulted stageهای join؛ `unallocated_summary` موارد تخصیص‌نیافته؛ `policy_violations` تخطی‌های policy. این evidence علت ریشه‌ای را به‌تنهایی ثابت نمی‌کند.

**کارایی:** DataFrameهای اضافه و Excel sheets می‌توانند CPU/memory/workbook size را زیاد کنند؛ مقدار دقیق **NOT MEASURED**.

**Implementation:** `app/infra/cli_legacy.py`; `app/infra/excel/export_allocations.py::collect_trace_debug_sheets`.

**Tests:** `tests/test_excel_export_smoke.py`, `tests/test_allocation_invariance.py`, `tests/test_user_settings.py`.

**Evidence:** wiring و sheet names = **DIRECTLY_CONFIRMED**؛ ترتیب پیشنهادی بررسی = **INFERRED**؛ اندازه دقیق هزینه = **NOT_PROVEN**.

## English

**Mental model:** several Excel inspection windows onto the same run without changing the engine decision.

`enable_trace_debug_sheets` is wired to `collect_trace_debug_sheets(... enable_standard_debug_sheets=...)`. A trace is a step-by-step record of information used or produced by Matrix. This setting does not redefine canonical trace semantics; it creates diagnostic views.

**Use when:** final summaries are insufficient to explain unallocated cases, final states, or join-key provenance. **Leave OFF:** routine runs where a smaller workbook is preferred.

**Impact:** allocation = **NO**; validation = **NO**; algorithm path = **NO**; additional diagnostic output = **YES**.

**Confirmed sheet names:** `summary_df`, `FinalStatus_counts`, `JoinKeyProvenance_counts`, `HistoryMetrics`, and conditionally `unallocated_summary`, `policy_violations`. Some sheets depend on source data being present/non-empty.

**Reading:** `FinalStatus_counts` counts final statuses; `JoinKeyProvenance_counts` summarizes inferred/defaulted join stages; `unallocated_summary` lists unallocated cases; `policy_violations` shows policy issues. These sheets are evidence, not proof of root cause.

**Performance:** extra DataFrames and Excel sheets can increase CPU/memory/workbook size; exact cost is **NOT MEASURED**.

**Implementation:** `app/infra/cli_legacy.py`; `app/infra/excel/export_allocations.py::collect_trace_debug_sheets`.

**Tests:** `tests/test_excel_export_smoke.py`, `tests/test_allocation_invariance.py`, `tests/test_user_settings.py`.

**Evidence:** wiring/sheet names = **DIRECTLY_CONFIRMED**; suggested investigation order = **INFERRED**; exact cost = **NOT_PROVEN**.

---

# 6. Mentor Pipeline Trace

## فارسی

**مدل ذهنی:** رسید مرحله‌به‌مرحله برای سؤال «ردیف‌های منتور من کجا تغییر کردند؟».

Mentor Pipeline فعلی همان `FieldRegistry → HeaderResolver → ValueCanonicalizer → JoinKeyResolver → MentorPoolBuilder` است. stageهای مستقیماً موجود در کد: `raw`, `header_resolved`, `canonicalized`, در شرایط مربوط `join_keys_present` یا `canonicalized_db`, سپس `join_keys`, `all_profiles`, `usable_profiles`, `condense_profiles_to_unique_mentors`, `pool_built` و در trace export ترکیبی `global_prefilter`.

**اثر:** allocation = **NO**؛ validation = **NO**؛ semantics الگوریتم = **NO**؛ instrumentation اضافه = **YES**.

**خروجی دقیق:** `EligibilityTrace`, `TraceLadder`, `MentorPipelineTrace`. ستون‌های pipeline شامل `stage`, `rows`, `columns`, `fingerprint`, `raw_count`, `predicate_summary`, `after_count`, `profile_rows`, `unique_mentor_ids`, `multi_profile_mentor_count`, `multi_profile_ratio`, `predicate_expr`, `predicate_source`, `prefilter_removed` است.

**خواندن:** stageها را به ترتیب بخوانید و تغییر `rows`/`after_count` را دنبال کنید. fingerprint snapshot مقایسه‌ای است و علت معنایی را توضیح نمی‌دهد.

**مثال:** mentor در input هست ولی در pool usable نیست → `all_profiles`، `usable_profiles` و `pool_built` را مقایسه کنید → سپس issues join/profile را بررسی کنید.

**محدودیت:** stageهای شرطی ممکن است ظاهر نشوند؛ کاهش rows لزوماً bug نیست. هزینه دقیق tracing **NOT MEASURED**.

**Implementation:** `app/infra/mentors/pipeline_v3.py::MentorPipelineV3`, `MentorPipelineTraceEntry`; helperهای pipeline/eligibility/ladder در `app/infra/excel/export_allocations.py`.

**Tests:** `tests/test_user_settings.py`, `tests/test_excel_export_smoke.py`, pipeline tests under `tests/infra`.

**Evidence:** stage/fields/sheets = **DIRECTLY_CONFIRMED**؛ workflow عیب‌یابی = **INFERRED**؛ defect بودن هر کاهش rows = **NOT_PROVEN**.

## English

**Mental model:** a stage-by-stage receipt answering “where did my mentor rows change?”

The current Mentor Pipeline is `FieldRegistry → HeaderResolver → ValueCanonicalizer → JoinKeyResolver → MentorPoolBuilder`. Directly observed stages include `raw`, `header_resolved`, `canonicalized`, conditionally `join_keys_present` or `canonicalized_db`, then `join_keys`, `all_profiles`, `usable_profiles`, `condense_profiles_to_unique_mentors`, `pool_built`, plus export-composed `global_prefilter`.

**Impact:** allocation = **NO**; validation = **NO**; algorithm semantics = **NO**; extra instrumentation = **YES**.

**Exact outputs:** `EligibilityTrace`, `TraceLadder`, `MentorPipelineTrace`. Pipeline fields include `stage`, `rows`, `columns`, `fingerprint`, `raw_count`, `predicate_summary`, `after_count`, `profile_rows`, `unique_mentor_ids`, `multi_profile_mentor_count`, `multi_profile_ratio`, `predicate_expr`, `predicate_source`, `prefilter_removed`.

**Reading:** follow stages and compare `rows`/`after_count`. A fingerprint supports snapshot comparison; it does not explain semantic cause.

**Example:** a mentor exists in input but is not usable in the final pool → compare `all_profiles`, `usable_profiles`, then `pool_built` → investigate join/profile issues.

**Limitations:** conditional stages may be absent; a row-count decrease is not automatically a bug. Exact tracing cost is **NOT MEASURED**.

**Implementation:** `app/infra/mentors/pipeline_v3.py::MentorPipelineV3`, `MentorPipelineTraceEntry`; pipeline/eligibility/ladder helpers in `app/infra/excel/export_allocations.py`.

**Tests:** `tests/test_user_settings.py`, `tests/test_excel_export_smoke.py`, pipeline tests under `tests/infra`.

**Evidence:** stages/fields/sheets = **DIRECTLY_CONFIRMED**; troubleshooting workflow = **INFERRED**; every row decrease being a defect = **NOT_PROVEN**.

---

# 7. Pool Governance Trace

## فارسی

**تعریف مفاهیم:** mentor pool مجموعه منتورهای آماده تخصیص است. governance کنترل ساختار/قابلیت استفاده pool است. profile یک ترکیب join برای mentor است. condense نمای profileها را برای بررسی سطح mentor خلاصه می‌کند؛ trace این رفتار را گزارش می‌دهد و قانون governance جدیدی نمی‌سازد.

**اثر:** allocation = **NO**؛ validation = **NO**؛ algorithm path = **NO**؛ diagnostic = **YES**.

**خروجی دقیق:** `PoolGovernanceTrace`, `PoolCondenseTrace`, `MultiProfileSummary`.

`PoolGovernanceTrace`: `stage_name`, `raw_rows`, `after_rows`, `removed_rows`, `removed_breakdown`, `distribution_before`, `distribution_after`, `profile_rows_before/after`, `unique_mentor_ids_before/after`.

`PoolCondenseTrace`: profile/mentor counts و stats مربوط به profiles-per-mentor. `MultiProfileSummary`: `profile_rows`, `unique_mentor_ids`, `multi_profile_mentor_count`, `multi_profile_ratio`.

**مثال:** سه profile برای دو mentor وارد شده ولی دو row نهایی می‌بینید → condense/multi-profile sheets را بخوانید. اختلاف count به‌تنهایی bug یا data corruption را ثابت نمی‌کند.

**محدودیت:** خروجی به attrs/payload upstream وابسته است و در نبود آن می‌تواند خالی باشد. هزینه دقیق **NOT MEASURED**.

**Implementation:** builderهای pool trace در `app/infra/excel/export_allocations.py`; payload producers در mentor pipeline/builder.

**Tests:** `tests/infra/test_pool_condense_trace.py` و governance tests مرتبط.

**Evidence:** sheet/columns = **DIRECTLY_CONFIRMED**؛ تفسیر count = **INFERRED**؛ نامعتبر بودن هر multi-profile = **NOT_PROVEN**.

## English

**Concepts:** mentor pool = mentors prepared for allocation. Governance = controls around pool structure/usability. Profile = a mentor join combination. Condense summarizes profile-level structure toward mentor-level inspection. The trace reports behavior; it does not define new governance rules.

**Impact:** allocation = **NO**; validation = **NO**; algorithm path = **NO**; diagnostic = **YES**.

**Exact outputs:** `PoolGovernanceTrace`, `PoolCondenseTrace`, `MultiProfileSummary`.

`PoolGovernanceTrace` fields include `stage_name`, `raw_rows`, `after_rows`, `removed_rows`, `removed_breakdown`, `distribution_before`, `distribution_after`, `profile_rows_before/after`, `unique_mentor_ids_before/after`. `PoolCondenseTrace` summarizes profile/mentor counts and profiles-per-mentor stats. `MultiProfileSummary` contains `profile_rows`, `unique_mentor_ids`, `multi_profile_mentor_count`, `multi_profile_ratio`.

**Example:** three profiles for two mentors become two final rows → inspect condense/multi-profile sheets. The count difference alone does not prove a bug or corruption.

**Limitations:** output depends on upstream attrs/payload and can be empty if that payload is unavailable. Exact cost: **NOT MEASURED**.

**Implementation:** pool trace builders in `app/infra/excel/export_allocations.py`; payload producers in mentor pipeline/builder.

**Tests:** `tests/infra/test_pool_condense_trace.py` and related governance tests.

**Evidence:** sheets/columns = **DIRECTLY_CONFIRMED**; count interpretation = **INFERRED**; every multi-profile state being invalid = **NOT_PROVEN**.

---

# 8. Bucket Trace

## فارسی

**مدل ذهنی:** دوربین روی مرحله narrowing؛ نه کلید روشن‌کردن آن مرحله.

Bucket گروه candidateهای mentor بر اساس join keys است. `enable_bucket_trace` فقط observation است؛ `use_join_buckets` گزینه جداگانه الگوریتمی است.

**اثر:** allocation = **NO**؛ validation = **NO**؛ algorithm = **NO**؛ diagnostic = **YES**.

**خروجی دقیق:** `BucketTrace` با `student_id`, `pool_built_size`, `pool_size_before_bucket`, `bucket_key`, `bucket_size`, `bucket_skip_reason`, `bucket_key_variants`, `bucket_sizes`.

اگر Join Buckets خاموش باشد، کد مقدار دقیق `bucket_skip_reason = disabled_by_setting` را ثبت می‌کند. این وضعیت خطا نیست؛ یعنی narrowing عمداً خاموش بوده است.

**خواندن:** `pool_size_before_bucket` را با `bucket_size` مقایسه کنید. key/size وجود narrowing را نشان می‌دهد. کوچک‌شدن pool به‌تنهایی correctness یا performance gain را ثابت نمی‌کند.

**محدودیت:** بدون eligibility trace/log مناسب sheet می‌تواند خالی باشد. هزینه دقیق **NOT MEASURED**.

**Implementation:** `app/core/common/eligibility_channel.py`; `app/infra/excel/export_allocations.py::_build_bucket_trace_sheet`.

**Tests:** `tests/infra/test_bucket_trace_flags.py`, `tests/integration/test_join_bucketing_edge_cases.py`.

**Evidence:** columns و `disabled_by_setting` = **DIRECTLY_CONFIRMED**؛ performance interpretation = **INFERRED/NOT_PROVEN**.

## English

**Mental model:** a camera pointed at candidate narrowing, not the switch that enables narrowing.

A bucket is a mentor-candidate group based on join keys. `enable_bucket_trace` is observation only; `use_join_buckets` is the separate algorithmic option.

**Impact:** allocation = **NO**; validation = **NO**; algorithm = **NO**; diagnostic = **YES**.

**Exact output:** `BucketTrace` with `student_id`, `pool_built_size`, `pool_size_before_bucket`, `bucket_key`, `bucket_size`, `bucket_skip_reason`, `bucket_key_variants`, `bucket_sizes`.

When Join Buckets is disabled, current code records the exact reason `bucket_skip_reason = disabled_by_setting`. This is not itself an error; it means narrowing was intentionally disabled.

**Reading:** compare `pool_size_before_bucket` with `bucket_size`. Key/size indicate narrowing. A smaller pool alone does not prove correctness or a performance gain.

**Limitations:** without suitable eligibility trace/log data the sheet can be empty. Exact cost is **NOT MEASURED**.

**Implementation:** `app/core/common/eligibility_channel.py`; `app/infra/excel/export_allocations.py::_build_bucket_trace_sheet`.

**Tests:** `tests/infra/test_bucket_trace_flags.py`, `tests/integration/test_join_bucketing_edge_cases.py`.

**Evidence:** columns and `disabled_by_setting` = **DIRECTLY_CONFIRMED**; performance interpretation = **INFERRED/NOT_PROVEN**.

---

# 9. QA Pool Coverage Rules

## فارسی

> **هشدار:** این گزینه diagnostic-only نیست. **MAY AFFECT VALIDATION / ممکن است PASS/FAIL اعتبارسنجی را تغییر دهد.**

Coverage یعنی برای student حداقل یک candidate mentor مطابق join keys در final pool موجود باشد. هنگام فعال‌بودن setting، `run_all_invariants` دو rule اختیاری را اضافه می‌کند:

1. `QA_RULE_POOL_COVERAGE_01`: اگر `candidate_count_final == 0` باشد violation سطح error می‌سازد و `passed=False` برمی‌گرداند.
2. `QA_RULE_POOL_DIVERSITY_01`: محدودبودن diversity در group/gender/graduation_status را warning می‌کند ولی خودش `passed=True` باقی می‌ماند.

از آنجا که `QaReport.passed` برابر `all(result.passed)` است، coverage failure می‌تواند نتیجه کلی validation را FAIL کند.

**اثر:** allocation = **NO**؛ validation = **YES**؛ allocation algorithm path = **NO**؛ diagnostic-only = **NO**.

**خروجی دقیق QA:** `PoolCoverageFailures`, `PoolDiversityReport`. Coverage details شامل `student_id`, `first_failing_stage`, `expected_value`, `available_values` و join-key values است.

**خواندن:** `first_failing_stage` اولین stage صفرشدن candidateهاست. expected/available را برای یافتن mismatch بررسی کنید. Diversity warning را با coverage failure اشتباه نگیرید.

**مثال:** student تخصیص نمی‌گیرد → setting را روشن کنید → اگر `PoolCoverageFailures` مثلاً graduation_status را نشان داد، effective join keys و pool values همان stage را بررسی کنید.

**چه چیزی ثابت نمی‌کند؟** Coverage PASS صحت ranking، capacity یا انتخاب نهایی mentor را ثابت نمی‌کند.

**محدودیت:** اگر preflight خالی/None باشد coverage rule pass خالی می‌دهد. هزینه دقیق preflight/rules/workbook: **NOT MEASURED**.

**Implementation:** `app/core/qa/invariants.py::check_POOL_COVERAGE_01`, `check_POOL_DIVERSITY_01`, `run_all_invariants`, `QaReport.passed`; `app/infra/cli_legacy.py`; `app/infra/excel/export_qa_validation.py`.

**Tests:** `tests/infra/test_qa_pool_coverage_rules.py`, `tests/core/test_pool_alignment_center_inference.py`, `tests/integration/test_alignment_allocation_parity.py`.

**Evidence:** rule/failure/sheets = **DIRECTLY_CONFIRMED**؛ correctness کامل allocation از coverage PASS = **NOT_PROVEN**.

## English

> **Warning:** this is not diagnostic-only. **MAY AFFECT VALIDATION PASS/FAIL.**

Coverage means a student has at least one final-pool mentor candidate matching join keys. When enabled, `run_all_invariants` adds two optional rules:

1. `QA_RULE_POOL_COVERAGE_01`: when `candidate_count_final == 0`, it emits an error violation and returns `passed=False`.
2. `QA_RULE_POOL_DIVERSITY_01`: warns about narrow group/gender/graduation_status diversity but itself remains `passed=True`.

Because `QaReport.passed` is `all(result.passed)`, a coverage failure can fail overall validation.

**Impact:** allocation = **NO**; validation = **YES**; allocation algorithm path = **NO**; diagnostic-only = **NO**.

**Exact QA outputs:** `PoolCoverageFailures`, `PoolDiversityReport`. Coverage details include `student_id`, `first_failing_stage`, `expected_value`, `available_values`, and join-key values.

**Reading:** `first_failing_stage` is the first stage where candidates reached zero. Compare expected/available values. Do not confuse diversity warning with the coverage failure.

**Example:** a student remains unallocated → enable the rules → if `PoolCoverageFailures` identifies graduation_status, investigate effective join keys and pool values at that stage.

**What it does not prove:** a coverage PASS does not prove ranking, capacity, or final mentor selection is correct.

**Limitations:** if preflight is empty/None, the coverage rule returns an empty pass. Exact preflight/rule/workbook cost is **NOT MEASURED**.

**Implementation:** `app/core/qa/invariants.py::check_POOL_COVERAGE_01`, `check_POOL_DIVERSITY_01`, `run_all_invariants`, `QaReport.passed`; `app/infra/cli_legacy.py`; `app/infra/excel/export_qa_validation.py`.

**Tests:** `tests/infra/test_qa_pool_coverage_rules.py`, `tests/core/test_pool_alignment_center_inference.py`, `tests/integration/test_alignment_allocation_parity.py`.

**Evidence:** rules/failure/sheets = **DIRECTLY_CONFIRMED**; complete allocation correctness from a coverage PASS = **NOT_PROVEN**.

---

# 10. Trace Sheet Export

## فارسی

**مدل ذهنی:** نسخه خام‌تر «جعبه سیاه پرواز» برای developer، کنار نتیجه معمول کاربر.

وقتی `enable_trace_export` روشن است، `cli_legacy.py`، `trace_df` را Excel-safe می‌کند و با نام sheet دقیق `trace` در workbook می‌نویسد.

**اثر:** allocation = **NO**؛ validation = **NO**؛ algorithm path = **NO**؛ forensic output = **YES**.

این sheet raw/developer-oriented است و جایگزین نتیجه عادی کاربر نیست. از student/mentor IDs و stage/reasonهای موجود برای دنبال‌کردن evidence استفاده کنید. raw trace به‌تنهایی صحت domain decision را ثابت نمی‌کند و schema عملی آن بدون قرارداد جداگانه نباید external stable API فرض شود.

**کارایی:** Excel conversion و sheet بزرگ‌تر می‌تواند CPU/memory/workbook size را بالا ببرد؛ هزینه دقیق **NOT MEASURED**.

**Implementation:** branch مربوط به `enable_trace_export` در `app/infra/cli_legacy.py` و trace producers موجود.

**Tests:** `tests/test_excel_export_smoke.py`, `tests/test_user_settings.py`, trace provenance/invariance tests.

**Evidence:** sheet `trace` و wiring = **DIRECTLY_CONFIRMED**؛ ثبات ابدی همه raw columns = **NOT_PROVEN**.

## English

**Mental model:** a rawer flight-recorder view for developers next to the normal user result.

With `enable_trace_export` enabled, `cli_legacy.py` converts `trace_df` to an Excel-safe form and writes it under the exact sheet name `trace`.

**Impact:** allocation = **NO**; validation = **NO**; algorithm path = **NO**; forensic output = **YES**.

This is raw/developer-oriented material, not a replacement for normal operational output. Use available student/mentor IDs and stage/reason fields to follow evidence. Raw trace does not prove domain correctness and should not be assumed to be a permanently stable external API without a separate contract.

**Performance:** Excel conversion and a larger sheet can increase CPU/memory/workbook size; exact cost is **NOT MEASURED**.

**Implementation:** the `enable_trace_export` branch in `app/infra/cli_legacy.py` and existing trace producers.

**Tests:** `tests/test_excel_export_smoke.py`, `tests/test_user_settings.py`, trace provenance/invariance tests.

**Evidence:** `trace` sheet/wiring = **DIRECTLY_CONFIRMED**; permanent stability of every raw column = **NOT_PROVEN**.

---

# 11. Use Join Buckets

## فارسی

> **هشدار:** این گزینه diagnostic نیست. **ADVANCED ALGORITHMIC / PERFORMANCE OPTION — مسیر اجرا را تغییر می‌دهد.**

**مفهوم:** bucketing کاندیدهای mentor را بر اساس join-key index به مجموعه‌های کوچک‌تر تقسیم/بازیابی می‌کند تا candidate search ابتدا محدود شود. `cli_legacy.py` setting را به `allocate_batch(... use_join_buckets=...)` می‌دهد؛ در eligibility channel، enabled بودن سبب استفاده از `join_bucket_index` می‌شود. در حالت OFF، pool کامل بدون narrowing bucket عبور می‌کند و trace می‌تواند `disabled_by_setting` ثبت کند.

**پیش‌فرض:** OFF / False و تغییر داده نشده است.

**اثر:** allocation result = **CONDITIONAL**؛ validation = **NO مستقیم**؛ algorithm path = **YES**؛ diagnostic-only = **NO**.

`CONDITIONAL` به این معنی نیست که کد عمداً نتیجه را تغییر می‌دهد. تست‌های parity برای برابری خروجی در سناریوهای پوشش‌داده‌شده وجود دارند، اما test coverage اثبات ریاضی همه wildcard/school/center/inputهای ممکن نیست.

**زمان استفاده:** فقط وقتی دلیل فنی مشخص برای ارزیابی optimization دارید و baseline OFF و parity/determinism validation را حفظ می‌کنید. کاربر عادی باید معمولاً OFF بگذارد.

**خروجی:** artifact مستقل تضمین‌شده ندارد. برای مشاهده رفتار `Bucket Trace` را جداگانه فعال کنید و `pool_size_before_bucket`, `bucket_size`, key و skip reason را بخوانید.

**مثال:** pool بزرگ → baseline OFF را نگه دارید → ON را ارزیابی کنید → parity/determinism tests و Bucket Trace را بررسی کنید. ON بودن به‌تنهایی performance gain را ثابت نمی‌کند.

**Performance:** هدف option کارایی است، اما gain واقعی workload-specific در این work unit **NOT MEASURED** است. risk register نیز re-run determinism/golden parity را توصیه می‌کند.

**Implementation:** `app/core/allocate_students.py::allocate_batch`, `app/core/common/eligibility_channel.py`, wiring در `app/infra/cli_legacy.py`, `docs/performance/RISK_REGISTER_join_bucketing.md`.

**Tests:** `tests/integration/test_join_bucketing_flag_parity.py`, `tests/integration/test_join_bucketing_edge_cases.py`, `tests/integration/test_ranking_heap_parity.py` و guards determinism/golden مرتبط.

**Evidence:** default/wiring/parity/risk = **DIRECTLY_CONFIRMED**؛ performance gain و equivalence مطلق همه inputs = **NOT_PROVEN**.

## English

> **Warning:** this is not a diagnostic setting. **ADVANCED ALGORITHMIC / PERFORMANCE OPTION — it changes execution path.**

**Concept:** bucketing partitions/retrieves mentor candidates using a join-key index so candidate search can be narrowed first. `cli_legacy.py` passes the setting to `allocate_batch(... use_join_buckets=...)`; the eligibility channel uses `join_bucket_index` when enabled. With the setting OFF, the full pool passes without bucket narrowing and trace can record `disabled_by_setting`.

**Default:** OFF / False, unchanged.

**Impact:** allocation result = **CONDITIONAL**; validation = **NO direct rule effect**; algorithm path = **YES**; diagnostic-only = **NO**.

`CONDITIONAL` does not mean the implementation intentionally changes results. Parity tests protect equivalence in covered scenarios, but test coverage is not a mathematical proof for every wildcard/school/center/input combination.

**When to use:** only with a specific technical reason to evaluate optimization while retaining an OFF baseline and parity/determinism validation. Normal users should generally leave it OFF.

**Output:** no guaranteed standalone artifact. Enable Bucket Trace separately and inspect `pool_size_before_bucket`, `bucket_size`, key, and skip reason.

**Example:** large pool → preserve OFF baseline → evaluate ON → run parity/determinism tests and inspect Bucket Trace. ON alone does not prove a performance gain.

**Performance:** performance is the objective, but workload-specific gain in this work unit is **NOT MEASURED**. The risk register recommends rerunning determinism/golden parity.

**Implementation:** `app/core/allocate_students.py::allocate_batch`, `app/core/common/eligibility_channel.py`, wiring in `app/infra/cli_legacy.py`, `docs/performance/RISK_REGISTER_join_bucketing.md`.

**Tests:** `tests/integration/test_join_bucketing_flag_parity.py`, `tests/integration/test_join_bucketing_edge_cases.py`, `tests/integration/test_ranking_heap_parity.py`, and related determinism/golden guards.

**Evidence:** default/wiring/parity/risk = **DIRECTLY_CONFIRMED**; performance gain and absolute equivalence for all inputs = **NOT_PROVEN**.

---

## 12. GUI reader contract

`UnifiedSettingsDialog` presents the eight capabilities in three semantic groups:

1. **Diagnostics / Observability**: Trace Debug Sheets, Mentor Pipeline Trace, Pool Governance Trace, Bucket Trace, Trace Sheet Export.
2. **Analysis**: History Metrics.
3. **Advanced Validation / Execution Behavior**: QA Pool Coverage Rules, Use Join Buckets.

Every row has a checkbox, localized title, plain-language description, visible impact label, and `Full Guide / راهنمای کامل`. The guide opens a scrollable/selectable bilingual reader with Persian RTL and English LTR available at the same time regardless of application language. Critical behavior is visible in the dialog and guide, not hidden only in a tooltip.

Source of GUI guide prose: `app/ui/preferences/diagnostics_guides.py`. Presentation metadata: `app/ui/preferences/diagnostics_catalog.py`. Runtime setting authority remains `app/infra/config_flags.py`.

---

## 13. Evidence maintenance rule

When code changes any setting consumer, artifact name, QA behavior, pipeline stage, or Join Buckets parity contract:

1. update the implementation/tests first;
2. update this document;
3. update `app/ui/preferences/diagnostics_guides.py` so GUI and developer documentation remain semantically aligned;
4. do not promote an inferred claim to confirmed without code/test evidence.

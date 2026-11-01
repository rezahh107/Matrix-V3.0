# Smart Student Allocation System — Vision & Scope (v1.0)

> **منبع حقیقت قوانین تخصیص (LAW v3.0 / Technical SSoT v3.0):** این سند راهنما/تاریخچه است؛ تمام قواعد ثابت (کلیدهای join، رتبه‌بندی، انواع منتور/دانش‌آموز، گیت ظرفیت، trace و ...) فقط در `docs/LAW_Smart_Student_Allocation_v3.0.md` و `docs/Technical_SSoT_Smart_Student_Allocation_v3.0-TECH.md` معتبرند. در صورت هر تعارض، محتوای این دو فایل حاکم است و نکات قدیمی این سند به‌عنوان LEGACY خوانده شوند.
- **Status:** Draft
- **Related Documents:** SSoT v1.0.2; Policy v1.0.3; Eligibility Matrix AGENTS.md (v1.0.3); repository-level AGENTS.md (agentsmd.net-aligned); Phase 0 System Requirements
- **Audience:** Product owner, tech lead/architect, QA/release, desktop operator/mentor admin, WordPress/Gravity Forms maintainer, coding agents (Codex/LLM) following AGENTS.md

## Product Vision
- Provide a deterministic, auditable, Policy-First allocation system that assigns students to mentors fairly, reuses capacity efficiently, and produces explainable outputs.
- Replace fragile manual allocations with reproducible, traceable decisions while retaining strong Excel interoperability for local workflows.
- Serve administrators/operators (desktop UI), mentors/patrons, and downstream systems (e.g., Sabt/Hekmat) through consistent imports/exports and clear audit trails.
- Success means: same inputs → same outputs; every allocation has a reason trail; capacity usage and fairness follow Policy; humans and agents can navigate consistent specs (Policy/SSoT, Vision/Scope, AGENTS.md).

## System Context
Major components and flow:
- **WordPress + Gravity Forms intake:** collects student/mentor data in controlled schemas.
- **Eligibility Matrix builder:** normalizes inputs and builds the matrix per Policy.
- **Allocation engine:** ranks/assigns students to mentors deterministically.
- **Exporter:** emits ImportToSabt and other downstream-friendly formats.
- **PySide6 desktop app/UI shell:** orchestrates runs, surfaces status, and shows logs.
- **Logging & audit layer:** records trace (8-step) and allocation explanations.

Data flow (conceptual):
```
Intake (Gravity Forms) → Normalization/Matrix Builder → Allocation Engine → Trace/Audit → Exporter (ImportToSabt & others) → Downstream systems
                                     ↘ Desktop UI (PySide6) orchestration ↗
```

### حافظهٔ تخصیص و کانال‌های جریان دانش‌آموز
- **حافظهٔ تخصیص (HistoryStore):** زیرساخت، تاریخچهٔ تخصیص‌های موفق را با کلید طبیعی «کد ملی نرمال‌شده» نگه می‌دارد تا سیستم در هر اجرا بداند چه دانش‌آموزی قبلاً منتور گرفته است. این حافظه بخشی از تعهد شفافیت است و بدون تغییر در ۶ کلید Join یا سیاست رتبه‌بندی، ورودی‌های جدید را با گذشته می‌سنجد.
- **تشخیص تکرار با `dedupe_by_national_id`:** Core پیش از ورود به الگوریتم رتبه‌بندی، دانش‌آموزان را بر اساس کد ملی به دو دستهٔ «قبلاً تخصیص‌گرفته» و «کاندید جدید» تقسیم می‌کند؛ در نتیجه دانش‌آموزی که در تاریخچه وجود دارد دوباره وارد صف allocation نمی‌شود مگر اینکه سیاست اجازه دهد و علت در trace ثبت می‌شود.
- **کانال‌های تخصیص (AllocationChannel):** سیاست، هر دانش‌آموز را به یکی از چهار کانال SCHOOL / GOLESTAN / SADRA / GENERIC هدایت می‌کند تا جریان‌های مدرسه‌ای، مراکز گلستان/صدرا و مسیر عمومی متمایز و قابل توضیح باشند. کانال‌ها از PolicyConfig/AllocationChannelConfig خوانده می‌شوند و صرفاً مسیر اجرای همان رتبه‌بندی ثابت را مشخص می‌کنند.
- **Explainability:** گزارش‌های trace و خلاصهٔ مدیریتی باید نشان دهند دانش‌آموز در کدام کانال پردازش شده و آیا به دلیل تاریخچه از صف اصلی خارج شده است؛ این رفتار افزوده به شفافیت کمک می‌کند بدون اینکه اساس رتبه‌بندی یا ظرفیت را تغییر دهد.

### حاکمیت استخر پشتیبان‌ها (Mentor Pool Governance)
- **MentorProfile/mentor_status:** هر پشتیبان/مدیر یک پروفایل سیاستی دارد که در SSoT/Policy نگهداری می‌شود و حداقل شامل `mentor_id`, ظرفیت‌های اعلام‌شده و وضعیت `mentor_status` است. این وضعیت می‌تواند `ACTIVE` (در دسترس برای استخر عمومی)، `FROZEN` (خارج از استخر حتی اگر در InspactorReport دیده شود) یا در آینده حالت‌های محدود مانند `RESTRICTED_*` باشد.
- **Policy-First نه Excel-first:** حذف یا اضافه کردن افراد به استخر به‌صورت رسمی در Policy/SSoT ثبت می‌شود و Core فقط از روی همین داده‌ها تصمیم می‌گیرد؛ دستکاری دستی ردیف‌ها در InspactorReport فقط یک راهکار اضطراری است و مسیر اصلی محسوب نمی‌شود.
- **پوشش سناریوهای خاص:** اگر پشتیبانی فقط برای یک مدرسه/کانال خاص مجاز باشد، Policy می‌تواند پروفایل او را با الگوی `RESTRICTED_*` تعریف کند تا Core او را تنها در همان قیدها ببیند و از ورود او به استخر عمومی جلوگیری شود.
- **همگام با HistoryStore و AllocationChannel:** پیشنهادهای فریزشدن یا محدودسازی بر اساس الگوهای تاریخی در HistoryStore می‌تواند توسط انسان بررسی و سپس در MentorProfile ثبت شود؛ AllocationChannel صرفاً جریان دانش‌آموز را مشخص می‌کند و جایگزین mentor_status نیست. این فیلتر قبل از ساخت ماتریس و بدون دست‌کاری ۶ کلید Join یا سیاست رتبه‌بندی اعمال می‌شود تا دترمینیسم حفظ شود.
- **هدف تجاری:** این مکانیزم تضمین می‌کند پشتیبان‌هایی که دورهٔ مأموریت‌شان تمام شده یا فقط در شرایط خاص کمک می‌کنند، به شکل شفاف و قابل‌ردیابی از استخر عمومی کنار گذاشته شوند و اپراتورها مجبور نباشند قبل از هر اجرا فایل‌های Excel را ویرایش کنند.
- **UI/CLI رسمی برای مدیریت:** پنل «مدیریت استخر پشتیبان‌ها» در PySide6 و CLI باید همین MentorProfile/Policy را نمایش و ویرایش کند، یعنی هر تغییری که اپراتور اعمال می‌کند فوراً در SSoT ذخیره شود و اجرای بعدی Core دقیقاً همان وضعیت را مصرف کند. مسیر غیررسمی (Excel edit) فقط در صورت بروز بحران قابل استفاده است و باید در گزارش عملیات ثبت شود تا جلوی بازگشت ناخواستهٔ افراد فریز‌شده گرفته شود.
- **دترمینیسم و قابلیت ردیابی:** ورود یا حذف هر Mentor از استخر باید در trace/گزارش مدیریتی مشخص باشد (مثلاً ستون وضعیت یا پیغام «FROZEN by policy») تا در ممیزی بعدی بتوان نشان داد که تصمیم بر اساس Policy بوده است. این الزام مانع از بازگشت ناخواستهٔ افراد فریز شده در importهای بعدی می‌شود.

### دترمینیسم QA و اصل «عدم ابهام»
- پس از ساخت ماتریس و اجرای تخصیص، لایهٔ QA خالص Core (`app/core/qa/invariants.py`) با `run_all_invariants(...)` روی خروجی‌ها اجرا می‌شود تا نتیجهٔ هر اجرا به‌صورت قطعی یکی از سه حالت `FAILED_PRE_QA`، `FAILED_QA` یا `PASSED_QA` باشد.
- هر اختلاف یا ناسازگاری که توسط قوانین QA (QA_RULE_*) پرچم می‌شود «نویز قابل‌قبول» نیست و به‌عنوان باگ/خطای داده تلقی می‌شود تا دترمینیسم و شفافیت حفظ شود.

## Scope & Phases
### Overall Scope
Unified Smart Student Allocation ecosystem covering intake, matrix, allocation, audit, export, and operator UI, governed by Policy/SSoT and executed by agents following AGENTS.md.

### Phase 0 (foundation / existing)
- In-scope: Eligibility Matrix builder; initial allocation logic; basic Excel I/O; manual/WordPress intake alignment; core ranking policy; initial trace logging.
- Out-of-scope for Phase 0: advanced UI flows; automated Sabt integration; multi-center orchestration; web self-service.

### Phase 1 (MVP for unified system)
- In-scope: deterministic allocation with full 8-step trace; PySide6 desktop orchestration; Gravity Forms intake alignment; importer/exporter for Excel + ImportToSabt; clear AGENTS.md references; policy/SSoT version binding; QA checklists.
- Not in Phase 1: autoscaling multi-tenant deployments; complex analytics dashboards; fully automated WordPress-to-allocator pipelines without operator review.

### Phase 2+ (future, not required now)
- Candidate scope: richer dashboards/monitoring; automated policy change governance; high-scale web/CLI entrypoints; deeper downstream integrations (live APIs); advanced anomaly detection; multi-repo AGENTS.md federation.
- Explicitly out-of-scope until approved: changing ranking policy, changing 6 Join Keys, relaxing determinism or Core/Infra/UI separations.

## Invariants & Constraints
- **6 Join Keys (int, immutable):** `کدرشته`, `جنسیت`, `دانش آموز فارغ`, `مرکز گلستان صدرا`, `مالی حکمت بنیاد`, `کد مدرسه`; used consistently across intake, matrix, allocation, exporter.
- **Ranking policy (LAW v3.0 / Technical SSoT v3.0):** مرتب‌سازی صرفاً بر اساس `remaining_capacity` نزولی و سپس `mentor_id` صعودی (natural + stable). توضیحات قبلی بر پایهٔ `occupancy_ratio` LEGACY است و نباید برای اجرا استفاده شود.
- **حافظهٔ تخصیص:** تاریخچهٔ تخصیص‌ها با کلید ملی نگهداری می‌شود و قبل از ورود به رتبه‌بندی اعمال می‌شود؛ این مکانیسم صرفاً ورودی صف را مدیریت می‌کند و در هستهٔ سیاست رتبه‌بندی دخالتی ندارد.
- **کانال‌های تخصیص:** مقدار `allocation_channel` برای هر دانش‌آموز به‌صورت سیاست‌محور و بدون هاردکد مرکز/مدرسه تعیین می‌شود و به‌عنوان متادیتای trace/خلاصه نگه داشته می‌شود.
- **Determinism:** same inputs/policy versions yield the same outputs; stable sorts; explicit version tagging (policy_version, ssot_version, schema versions).
- **Policy-First boundaries:** Core has no I/O or Qt; Infra handles Excel/WordPress/filesystem; UI is PySide6-only for desktop, Gravity Forms-only for intake; CLI/web entrypoints wrap Infra/Core without redefining policy.
- **Explainability:** 8-step trace (`type`, `group`, `gender`, `graduation_status`, `center`, `finance`, `school`, `capacity_gate`) with candidate counts and allocation reasons per student; audit logs retained.
- **Data contracts:** Excel schemas and Gravity Forms fields must align with SSOT/Policy; Join Keys remain integer; crosswalks/premap and natural sort respected; no hardcoded dates/paths in Core.
- **Safe variability:** UI layout wording, minor Excel formatting, or operational scripts may evolve if they do not violate Policy/SSoT, join keys, ranking, determinism, or Core/Infra/UI separation.

## Quality Attributes
- **Determinism & reproducibility:** stable/natural sorts; seeded runs if needed; explicit policy_version/ssot_version in outputs.
- **Auditability & explainability:** per-student trace, status/reason codes, versioned logs; 8-step trace completeness.
- **تاریخچه و کانال‌محوری:** خروجی‌ها باید نشان دهند چه دانش‌آموزی از تاریخچه حذف شده یا در چه کانالی پردازش شده است؛ این اطلاعات برای یادگیری‌های بعدی و تحلیل انحراف‌ها ضروری است و در کنار trace اصلی ذخیره می‌شود.
- **Performance:** typical batches (10k students) under budget; avoid repeated merges; premap mentor code mapping; no pandas inplace.
- **Robustness to data issues:** Persian/number normalization, mobile/ID validation per policy, resilience to crosswalk drift with clear errors.
- **Maintainability:** clear separation of concerns; AGENTS.md for agent operations; SSoT/Policy for domain rules; this Vision/Scope for product boundaries; modular roles for agents.

## Relationship to SSoT, Policy, and AGENTS.md
- **LAW v3.0 + Technical SSoT v3.0:** تنها منبع حقیقت برای قواعد ثابت (join keys، RANK-CORE capacity-based، trace، انواع دانش‌آموز/منتور). این سند به آن‌ها ارجاع می‌دهد و در صورت تعارض تابع آن‌هاست.
- **SSoT v1.0.2 + Policy v1.0.3:** برای بقیهٔ حوزه‌های محصول (پیش از LAW/TECH v3.0) خواندنی هستند، اما هر قاعدهٔ تخصیص باید با LAW/TECH v3.0 سنجیده شود.
- **Vision & Scope (this document):** defines why and what the product delivers, phase boundaries, invariants, and quality expectations; it does not redefine rules.
- **AGENTS.md (agentsmd.net compliant):** defines how coding agents operate (repo navigation, coding conventions, test commands, Core vs Infra vs UI boundaries); Eligibility Matrix AGENTS.md adds component-specific guidance. AGENTS.md must stay consistent with this Vision/Scope and Policy; if conflicts arise, Policy/SSoT win, then Vision/Scope, then AGENTS.md.
- **Evolution:** Vision/Scope changes only with product direction shifts; AGENTS.md can evolve operationally but must never contradict Policy/SSoT/LAW/TECH; policy updates require re-alignment and version bumps in all artifacts.

## Risks, Assumptions, and Open Questions
- **Risks:** Excel template drift; Gravity Forms schema changes; crosswalk misalignment; policy/SSoT divergence; insufficient audit retention; deterministic sorting accidentally broken; performance regressions on large batches.
- **Assumptions:** Admins control form/schema changes; Join Keys remain integer and consistent; limited, known center list; desktop operators review pipelines; downstream ImportToSabt formats stay stable.
- **Open Questions:** Governance model for multiple AGENTS.md files (global vs component-specific); final ownership of policy updates and rollout cadence; exact boundary between desktop orchestration and WordPress automation in later phases; handling of future API-based downstream consumers.

## Glossary
- **Student:** person to be allocated; source from intake/Excel.
- **Mentor/پشتیبان:** capacity provider؛ ظرفیت و نوع منتور طبق LAW/TECH مشخص می‌شود؛ متریک‌های occupancy_ratio صرفاً تاریخی‌اند.
- **Eligibility Matrix:** matrix built from normalized inputs per Policy to gate eligibility.
- **Allocation:** assignment of a student to a mentor using ranking policy and constraints.
- **ImportToSabt:** exporter format for downstream systems (e.g., Sabt/Hekmat).
- **SSoT:** single source of truth document (v1.0.2) describing canonical data/policy.
- **Policy:** governing rules (v1.0.3) including join keys, ranking, trace steps.
- **AGENTS.md:** agent-facing operational guide aligned with agentsmd.net; includes Eligibility Matrix-specific and repo-level instructions.
- **Join Keys:** six integer keys linking data across sources: `کدرشته`, `جنسیت`, `دانش آموز فارغ`, `مرکز گلستان صدرا`, `مالی حکمت بنیاد`, `کد مدرسه`.
- **occupancy_ratio (LEGACY):** متریک تاریخی از نسخه‌های قبلی؛ از LAW/TECH v3.0 به بعد رتبه‌بندی بر اساس ظرفیت باقی‌مانده است.
- **allocations_new:** count of new allocations per mentor historically used; در LAW/TECH v3.0 فقط ظرفیت باقی‌مانده و mentor_id معیار رتبه‌بندی‌اند.


## Owner-approved Matrix delivery outcomes — 2026-11-01

**Decision status:** Owner-approved additions to the complete product destination for Matrix-V3.0. Implementation, verification, release and actual operator acceptance remain separate evidence claims. This addendum to the historical Draft Vision takes precedence over an older assumption that its newly approved delivery/qualification goals are optional, but does NOT replace any original product capability or redefine Policy/LAW/Technical SSoT, six integer join keys, remaining-capacity ranking, eight-stage Trace, deterministic allocation, import/export formats, or Core/Infra/UI isolation. The relevant domain and presentation authorities remain higher priority. No new architecture or application version has been selected by adopting these goals.

### D1 — End-to-end, self-guided desktop operator workflow

- The supported Windows application must let a qualified operator prepare/update the Database's reference data, Build Matrix, Allocate, review truthful QA/Trace/History when relevant, and produce, locate and review the required ImportToSabt and other approved outputs. Preserve existing data contracts, required capabilities, and supported paths; do not collapse the destination to the most recently modified screen.
- Maintain the already approved C2 primary Build/Allocate workspace, secondary Explain/Database destinations, V2 visual direction, existing diagnostics and intentionally retired Rule Engine GUI boundary (backend/CLI retained).
- For material actions, reveal purpose, prerequisites, consequence, running/result state and next valid step in straightforward UI language. Show a practical outcome before optional low-level logs. No invented progress percentages, ambiguous success, automatic retry claims or hidden external/data side effects.
- QA and Explain must distinguish observed evidence, bounded interpretation and suggested follow-up. Do not show sample values as real allocation evidence or duplicate domain decisions in the presentation layer. Inventory the existing real Trace data before the separate Owner decision on any NEW interactive Explain product capability.
- Prefer concise contextual guidance over tours, a separate Help Center or a forest of tooltips. User-facing statements about runtime behavior need appropriate runtime or contract evidence.

**Proof:** actual supported workflow state transitions, representative sanitized inputs, QA and export correctness, and an operator-comprehension check proportional to consequence. Existing CI alone does not prove the operator experience.

### D2 — Accessible, faithful bilingual UI and material usability repair

- Keep existing Qt STYLED/NATIVE/HYBRID ownership, C2/V2 tokens and native Qt behavior. Correct confirmed material visual/interaction defects such as History Metrics truncation, Explain sample presentation, misleading workflow badges, mixed-language strings, and meaningful overflow; do not reopen design locks for cosmetic novelty.
- Cover Persian RTL and English LTR, technical mixed-direction identifiers, Light/Dark themes, longer translations, Windows layout/resize/DPI, keyboard/focus and semantic status cues beyond color alone.
- Test changed UI behavior and renders with targeted regression/state checks and full-resolution comparisons. Use independent comprehension review for material guidance changes when feasible. Synthetic/offscreen screenshot success is not physical Windows user acceptance.

**Proof:** bounded Qt UI/RTL/resize/keyboard tests plus evidence appropriate to the actual user-facing claim; unsatisfied real-device/comprehension elements remain NOT_PROVEN.

### D3 — High-fidelity Windows runtime simulation/qualification in CI [HIGH PRIORITY]

- Build a reproducible, pinned, artifact-identifiable CI qualification path resembling the supported Windows runtime as closely as practical: Windows version/environment, Python and Qt/PySide6, actual startup, dependencies, embedded Persian fonts, local reference DB, user settings/QSettings, filesystem permissions and paths, source input files, Worker lifecycle, file dialogs, GUI behavior, output persistence and important FA/EN Light/Dark, High-DPI/focus cases.
- Include the supported operator path to its prerequisites where meaningful: reference import/preparation, Build, Allocate, QA/Trace, real exports. Tests which synthesize fixtures/preload hidden state are useful component evidence but not proof that actual users can reach that state.
- Address known intermittent native Qt access violation and recurring QSettings.AccessError through bounded root-cause investigation and true regression evidence. Retain existing Core/domain/golden/parity safety guards. Do not suppress, skip, weaken or reclassify failures merely to make CI green.
- Keep an explicit proof boundary between headless/offscreen rendering, virtualized Windows testing, actual built EXE behavior and physical/operator-desktop behavior. CI cannot be claimed equivalent to physical interactive Windows unless the relevant interactions are actually exercised. Mark gaps NOT_PROVEN.
- Reuse working GitHub Actions, uv and existing tests; add only the minimum effective coverage and environment machinery justified by a named mismatch, not a universal OS matrix or paid always-on runtime.

**Proof:** an executable repeatable Windows CI path covering the application and representative workflow, exact-source/artifact identity, retained crash artifacts, guarded negative cases and an explicit coverage/limitations statement. A successful single offscreen UI run does not close this outcome.

### D4 — Governed application versioning, packaging and release [HIGH PRIORITY]

- Establish exactly one authoritative application release version, consistently visible in package metadata, changelog, application/about or equivalent where supported, Windows EXE metadata/asset labeling and published releases. Keep application version separate from independently governed LAW/Policy/Technical SSoT/schema versions. Audit existing inconsistent historical indicators (currently pyproject.toml indicates 0.1.0, while CHANGELOG.md includes 1.0.0) before choosing a release baseline; do NOT invent an approved starting version.
- Establish one canonical Windows production build path using the real repository/PyInstaller environment, bundled Qt dependencies and runtime assets. Qualify the **produced Windows distributable itself**, rather than only the Python source: startup, embedded fonts, reference/data paths, QSettings, representative operations/exports, safe defaults and negative failure paths where practical. Tie a candidate, its checks and its published artifact to one reviewed source identity.
- Provide a low-friction Prepare → Qualify → Owner-controlled Publish → verify real downloadable asset and consumer installation/runtime → Recover lifecycle. Version tags and publication are not implicit in Merge or green CI. Only publish production versions with explicit Owner authorization or a separately approved publication contract. Preserve immutable published history and truthful partial-failure/recovery semantics.
- Choose SemVer or an appropriate alternative from actual product distribution constraints, not by copying a workflow from another product. Use reusable native CI/build primitives, minimal scopes, explicit hashes/identity and adequate documentation, with no redundant release governance stack.

**Proof:** one traceable candidate built/validated from exact code; version consistency; checked downloadable Windows artifact and explicit publication decision; real download/install/run evidence where tested. No release is claimed before verified publication.

### D5 — Honest progress, privacy, proportional engineering and full destination coverage

- Preserve the complete original destination, all immutable LAW/Technical SSoT and UI-owner decisions. Never mark the whole product Done because a PR merged, source CI passed, evidence images exist or a partial feature was implemented.
- Distinguish planned, implemented, CI-tested, merged, built, released, installed and used. A fixture-assisted test proves only its exercised path. The Owner currently cannot perform physical Windows testing; this is a temporary acceptance-evidence gap, not a reason to stop independent CI development.
- For new infrastructure and guards, use named failure → bounded diagnosis → smallest sufficient mechanism → actual verification → stop. Prefer supported Qt/platform capabilities inside locked visual ownership; preserve successful baselines and avoid unnecessary redesign, duplicate standards, extra control documents or unrelated refactors. Only reopen costly frozen architecture with substantive evidence and Owner authority.
- Keep public CI, support/LLM reports and release artifacts privacy-safe: do not leak real student/mentor identifiers or secrets; use representative non-sensitive fixtures while preserving realistic behavior.
- Prioritize the next safe observable user outcome, not PR/task counts; proactively surface drift and unmet parts before declaring completion.

**Execution orientation, not a fixed schedule:** first contain/root-cause the observed Windows UI CI access violation and recurring QSettings failure. Next qualify a coherent Windows CI simulation plus app versioning and release candidate path using current build/test infrastructure; progress on other independently safe UX/History/Explain display defects may proceed in parallel. Any product expansion of Explain requires a separate Owner decision grounded in existing Trace evidence.

**Current outcome coverage at adoption:** present and clear: locked domain LAW/Technical SSoT, C2/V2 UI/ownership, initial Windows CI and PyInstaller build instructions; present but incomplete/ambiguous: operator-flow experience, remaining UX and Explain behavior, reproducible simulation of actual supported runtime, canonical application release version and governed distributable lifecycle; missing or unproven: permanent resolution of Qt/QSettings instability, production-quality published Windows binary and real operator acceptance. Overall Matrix destination is INCOMPLETE until full supported outcomes are demonstrated. This new goal text is not evidence of implementation.

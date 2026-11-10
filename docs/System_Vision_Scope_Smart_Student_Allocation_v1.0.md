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
- **Ranking policy (LAW v3.0 / Technical SSoT v3.0; Owner GOAL_AUTHORITY §L, 2026-11-08):** مرتب‌سازی مصوب `remaining_capacity` نزولی، سپس `allocations_new` صعودی، سپس `mentor_sort_key = natural_key(mentor_id)` صعودی و پایدار است. رتبه‌بندی بر پایهٔ `occupancy_ratio` LEGACY است و نباید اجرا شود.
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
- **allocations_new:** شمار تخصیص‌های جدید منتور در اجرای جاری؛ معیار دومِ مصوب رتبه‌بندی پس از تساوی `remaining_capacity` است و پیش از tie-break نهایی `mentor_id` استفاده می‌شود (Owner GOAL_AUTHORITY §L).


## Owner-approved Matrix delivery outcomes — 2026-11-01

**Decision status:** Owner-approved additions to the complete product destination for Matrix-V3.0. Implementation, verification, release and actual operator acceptance remain separate evidence claims. This addendum to the historical Draft Vision takes precedence over an older assumption that its newly approved delivery/qualification goals are optional, but does NOT replace any original product capability or redefine Policy/LAW/Technical SSoT, six integer join keys, remaining-capacity ranking, eight-stage Trace, deterministic allocation, import/export formats, or Core/Infra/UI isolation. The relevant domain and presentation authorities remain higher priority. No new application version has been selected by adopting these goals. Owner decision (2026-11-01, superseding the earlier D3/D4 package wording): **uv is the supported routine execution/distribution direction; PyInstaller and standalone EXE packaging are explicitly NOT part of the Matrix project goals.** This choice does not waive trustworthy Windows CI, release/versioning or validated end-user execution.

### D1 — End-to-end, self-guided desktop operator workflow

- **Owner-confirmed Roster lifecycle (MATRIX-OPS-ROSTER-20261110-001):** Before **every Allocate**, the operator obtains a newly downloaded current-academic-year Roster from the official registration system and supplies it for that run. It is the basis for continuing the gender-specific numbering after registrations already completed externally. Do not silently reuse a previously selected Roster as if it were a new official snapshot; because Matrix has no independent official-system freshness check, operator-supplied evidence/attestation and actual verified freshness must remain distinct. No particular UI/CLI enforcement mechanism is approved by this goal statement.
- **Prior-year identity continuity:** A valid prior-academic-year Roster is normally selected once per academic-year context and safely reused in later Allocate attempts and after restarting Matrix while the official source and file remain valid. File relocation, deletion, corruption, official replacement or switching academic-year context requires revalidation or re-selection. Returning students retain their existing valid official registration ID by national-ID matching; genuinely new students receive a new sequence derived from the selected year and current Roster. The official normal business rule is one valid historical registration ID per student; ambiguous/corrupted imports remain exceptional technical-validation inputs.
- **Official-system cycle and concurrency:** The operational loop is fresh current Roster → usable prior-year reference → explicit year confirmation → Allocate → truthful QA/output inspection → official registration → fresh current Roster for the next run. Competing or overlapping allocations must not silently assume that one numbering snapshot remains current. Protect the external registration-ID integrity objective without silently changing Core counter/LAW/Technical SSoT rules.
- The supported Windows application must let a qualified operator prepare/update the Database's reference data, Build Matrix, Allocate, review truthful QA/Trace/History when relevant, and produce, locate and review the required ImportToSabt and other approved outputs. Preserve existing data contracts, required capabilities, and supported paths; do not collapse the destination to the most recently modified screen.
- Maintain the already approved C2 primary Build/Allocate workspace, secondary Explain/Database destinations, V2 visual direction, existing diagnostics and intentionally retired Rule Engine GUI boundary (backend/CLI retained).
- For material actions, reveal purpose, prerequisites, consequence, running/result state and next valid step in straightforward UI language. Show a practical outcome before optional low-level logs. No invented progress percentages, ambiguous success, automatic retry claims or hidden external/data side effects.
- QA and Explain must distinguish observed evidence, bounded interpretation and suggested follow-up. Do not show sample values as real allocation evidence or duplicate domain decisions in the presentation layer. Inventory the existing real Trace data before the separate Owner decision on any NEW interactive Explain product capability.
- Prefer concise contextual guidance over tours, a separate Help Center or a forest of tooltips. User-facing statements about runtime behavior need appropriate runtime or contract evidence.

**Proof:** actual supported workflow state transitions, representative sanitized inputs, QA and export correctness, and an operator-comprehension check proportional to consequence. Existing CI alone does not prove the operator experience.

### D2 — Accessible, faithful bilingual UI and material usability repair

- **Roster truthfulness in the selected Readiness Ledger (Concept A):** In Persian RTL and English LTR distinguish (i) path selected vs file presently available/validated, (ii) previously stored prior-year reference vs newly chosen replacement, (iii) operator-confirmed current-year download vs independently verified official freshness (not currently supported), and (iv) a genuinely ready Allocate versus missing/untrusted critical Roster input. Give concise actionable recovery, selected academic-year context and an intelligible next step, never unsupported “verified fresh” or automatic synchronization claims. Preserve C2/V2 and native Qt ownership; do not reopen the already selected Concept A direction.
- Keep existing Qt STYLED/NATIVE/HYBRID ownership, C2/V2 tokens and native Qt behavior. Correct confirmed material visual/interaction defects such as History Metrics truncation, Explain sample presentation, misleading workflow badges, mixed-language strings, and meaningful overflow; do not reopen design locks for cosmetic novelty.
- Cover Persian RTL and English LTR, technical mixed-direction identifiers, Light/Dark themes, longer translations, Windows layout/resize/DPI, keyboard/focus and semantic status cues beyond color alone.
- Test changed UI behavior and renders with targeted regression/state checks and full-resolution comparisons. Use independent comprehension review for material guidance changes when feasible. Synthetic/offscreen screenshot success is not physical Windows user acceptance.

**Proof:** bounded Qt UI/RTL/resize/keyboard tests plus evidence appropriate to the actual user-facing claim; unsatisfied real-device/comprehension elements remain NOT_PROVEN.

### D3 — High-fidelity Windows runtime simulation/qualification in CI [HIGH PRIORITY]

- Build a reproducible, pinned, artifact-identifiable CI qualification path resembling the supported Windows runtime as closely as practical: Windows version/environment, Python and Qt/PySide6, actual startup, dependencies, embedded Persian fonts, local reference DB, user settings/QSettings, filesystem permissions and paths, source input files, Worker lifecycle, file dialogs, GUI behavior, output persistence and important FA/EN Light/Dark, High-DPI/focus cases.
- Include the supported operator path to its prerequisites where meaningful: reference import/preparation, Build, Allocate, QA/Trace, real exports. Tests which synthesize fixtures/preload hidden state are useful component evidence but not proof that actual users can reach that state.
- Address known intermittent native Qt access violation and recurring QSettings.AccessError through bounded root-cause investigation and true regression evidence. Retain existing Core/domain/golden/parity safety guards. Do not suppress, skip, weaken or reclassify failures merely to make CI green.
- Keep an explicit proof boundary between headless/offscreen rendering, virtualized Windows testing, the actual released uv-runnable source/dependency distribution and physical/operator-desktop behavior. CI cannot be claimed equivalent to physical interactive Windows unless the relevant interactions are actually exercised. Mark gaps NOT_PROVEN.
- Reuse working GitHub Actions, the supported uv workflow (including the repository's pinned Python/dependency lock) and existing tests. Qualify a clean supported Windows setup and real UI startup/operations with the uv commands documented for operators. No PyInstaller/EXE build or EXE testing is required or authorized as a product destination. Add only minimum effective coverage for identified mismatches, not a universal OS matrix or paid always-on runtime.

**Proof:** an executable repeatable Windows CI path covering the application and representative workflow, exact-source/artifact identity, retained crash artifacts, guarded negative cases and an explicit coverage/limitations statement. A successful single offscreen UI run does not close this outcome.

### D4 — Governed application versioning and uv-based release [HIGH PRIORITY]

- Establish exactly one authoritative application release version, consistently visible in package metadata, changelog, application/about or equivalent where supported, versioned release identity and downloadable source/dependency artifacts when applicable. Keep the application release version separate from independently governed LAW/Policy/Technical SSoT/schema versions. Audit existing inconsistent historical indicators (currently pyproject.toml indicates 0.1.0, while CHANGELOG.md includes 1.0.0) before choosing a release baseline; do NOT invent an approved starting version.
- Establish one canonical, **uv-based Windows execution and delivery path**, grounded in the repository's verified entry point, pyproject.toml, uv.lock and required version-controlled runtime resources. The candidate Release should supply or point unambiguously to a reproducible versioned source snapshot (or appropriately constructed source archive) and exact setup/launch instructions; the user need not receive a frozen EXE. From a clean Windows environment, actually exercise **uv sync --locked** and the validated **uv run --locked** application command, startup, fonts/resources, reference/data paths, QSettings, representative Build/Allocate operations and outputs, safe defaults and meaningful failure cases where CI supports them. Verify that any published downloadable archive is complete and corresponds to the reviewed source and lockfile. Do **not** introduce or require PyInstaller, a standalone EXE, installer, or native binary bundling as a release goal.
- Provide a low-friction Prepare → Qualify → Owner-controlled Publish → verify the actual tagged/source release and a fresh uv setup/launch on supported Windows → Recover lifecycle. Version tags and publication are not implicit in Merge or green CI. Only publish production versions with explicit Owner authorization or a separately approved publication contract. Preserve immutable published history and truthful partial-failure/recovery semantics.
- Choose SemVer or an appropriate alternative from actual product distribution constraints, not by copying a workflow from another product. Prefer existing uv and GitHub Actions primitives; ensure clean-checkout reproducibility and release identity, with minimal controls and no redundant build or release governance stack.

**Proof:** one traceable, version-consistent candidate validated from exact source and uv.lock; a verified tagged/downloadable source release (when published) and successful clean supported Windows uv setup/launch plus representative workflow tests where exercised; an explicit publication decision and truthful handling of unavailable physical-user acceptance. No release is claimed before verified publication.

### D5 — Honest progress, privacy, proportional engineering and full destination coverage

- Preserve the complete original destination, all immutable LAW/Technical SSoT and UI-owner decisions. Never mark the whole product Done because a PR merged, source CI passed, evidence images exist or a partial feature was implemented.
- Distinguish planned, implemented, CI-tested, merged, built, released, installed and used. A fixture-assisted test proves only its exercised path. The Owner currently cannot perform physical Windows testing; this is a temporary acceptance-evidence gap, not a reason to stop independent CI development.
- For new infrastructure and guards, use named failure → bounded diagnosis → smallest sufficient mechanism → actual verification → stop. Prefer supported Qt/platform capabilities inside locked visual ownership; preserve successful baselines and avoid unnecessary redesign, duplicate standards, extra control documents or unrelated refactors. Only reopen costly frozen architecture with substantive evidence and Owner authority.
- Keep public CI, support/LLM reports and release artifacts privacy-safe: do not leak real student/mentor identifiers or secrets; use representative non-sensitive fixtures while preserving realistic behavior.
- Prioritize the next safe observable user outcome, not PR/task counts; proactively surface drift and unmet parts before declaring completion.

**Execution orientation, not a fixed schedule:** first contain/root-cause the observed Windows UI CI access violation and recurring QSettings failure. Next qualify a coherent Windows CI simulation plus application versioning and uv-source-release candidate path using current uv/test infrastructure (without an EXE/installer requirement); progress on other independently safe UX/History/Explain display defects may proceed in parallel. Any product expansion of Explain requires a separate Owner decision grounded in existing Trace evidence.

**Current outcome coverage at adoption:** present and clear: locked domain LAW/Technical SSoT, C2/V2 UI/ownership, initial Windows CI and working uv run instructions; present but incomplete/ambiguous: operator-flow experience, remaining UX and Explain behavior, reproducible simulation of actual supported runtime, canonical application release version and governed uv-based source-release lifecycle; missing or unproven: permanent resolution of Qt/QSettings instability, independently qualified uv-run release on a clean supported Windows environment and real operator acceptance. Any historical PyInstaller build instructions elsewhere in the repository are legacy/optional historical information, not an approved Matrix destination or prerequisite. Overall Matrix destination is INCOMPLETE until full supported outcomes are demonstrated. This new goal text is not evidence of implementation.


### D4 clarification — Owner-approved personal release and safe incremental update (2026-11-05)

Record MATRIX-D4-PERSONAL-RELEASE-001 is an Owner-approved partial supersession of D4 distribution assumptions, not a domain LAW change. Matrix is a personal Windows application for its Owner, while GitHub may remain PUBLIC temporarily for GitHub Actions. Governed, actual versions, concise per-version history, exact source+uv.lock identity, explicit approval before an official annotated Git Tag/GitHub Release, bounded release qualification and safe rollback remain required. The routine personal update path is an initial Git clone, explicit Owner-approved tag selection, incremental Git fetch and locked uv sync, without repeated full source-ZIP downloads; a source candidate remains valuable for QA/recovery. No EXE/installer/new public-customer distribution channel is authorized. Protect real SQLite databases, QSettings, organization Sabt Profiles, output files and working data by inspected path and non-destructive failure behavior. A passing PR/CI is never publication approval. First official version is NOT SELECTED (pyproject 0.1.0 is metadata; historical changelog 1.0.0 is not a release). The full D1/D2/D3/D5, LAW/SSoT and established UI destination remains unchanged. See docs/PERSONAL_RELEASE_GIT_UV.fa.md for operating and recovery limitations.


### D4 GitHub Release publication implementation direction — Owner decision 2026-11-07

Owner explicitly selected **GitHub Release** as the governed publication capability in addition to personal Git+uv updates. This replaces only the earlier tag-only alternative, not Matrix's personal-user audience or D1–D5/LAW/Technical SSoT/C2/V2 obligations. The reviewable implementation introduces an owner-only manual workflow, exact-current-main SHA pinning, rerun of Windows uv/Core/UI/Golden qualification, SemVer/lock/Python/changelog checks, immutable annotated tag, attached selective source and provenance assets, live Release/download/tag verification and bounded partial-state recovery. It is NOT authorization to run the workflow or publish v0.1.0; PR merge/CI alone cannot publish.

Because GitHub Releases expose **automatic full repository-source ZIP/TAR.GZ** in addition to explicitly uploaded limited assets, tracked Excel/CSV/Golden inputs and unverified redistribution/ownership rights are an explicit PUBLIC publication gate. Existing Owner approval for current center-manager names stands unchanged. As long as material full-archive privacy/rights clearance is unproven, the LIVE step fails closed. The workflow's environment gate can be separately protected in GitHub settings; referencing an environment does not establish that reviewers are configured. See `docs/PERSONAL_RELEASE_GIT_UV.fa.md` for controls, required Owner decisions and non-destructive failure handling. Implementation and CI-level proof are distinct from merged, officially released, end-user installed and accepted states.


### Matrix operational Roster decision — Owner approval 2026-11-10 (goal-level trace)

- **Decision/trace:** `MATRIX-OPS-ROSTER-20261110-001`; documentation PR [#56](https://github.com/rezahh107/Matrix-V3.0/pull/56), reviewed Head `5e8813e2702318b59486fba7a02366635a9b4f3f`, still unmerged at goal update. The approved D1/D2 outcome above is from direct Owner authority; the PR itself is documentation evidence, not an implementation or merge decision.
- **Observed implementation baseline:** `main@4a1a064d8ee9365a8bef8dc47c1649fc660275d3` on 2026-11-10. `app/ui/main_window_base.py::_build_allocate_overrides` forwards optional non-empty Roster paths, `app/infra/cli_legacy.py` loads both as optional; `AppPreferences` does not persist a year-scoped prior-Roster path. Core `app/core/counter.py` contains a national-ID prior-ID reuse path but cannot compensate for missing/invalid prior-year input. These source observations do not prove that every malformed/duplicate import is safely handled or that any real operator task succeeded.
- **Delivery state:** `APPROVED_REQUIREMENTS / NOT_IMPLEMENTED` for persistent prior-Roster reuse, per-run current-Roster enforcement, truthful freshness acknowledgement and competing-run safeguards. Correct UI copy, validation and physical operator acceptance remain `NOT_PROVEN` for the new requirements. No code, merge, release or changes to LAW/Technical SSoT are authorized by these statements.
- **Requirement/acceptance detail:** `docs/Phase_0_System_Requirements_v2.5_Final.md` addendum `MATRIX-OPS-ROSTER-20261110-001`. Prior-year file may be unchanged across runs; a newly downloaded current-year file may legitimately have identical bytes if the official registration set did not change. Repeated unchanged content alone cannot establish stale data. Do not claim remote freshness from timestamp/hash or operator confirmation alone.

# AGENTS — Smart Student Allocation Engine (v3.5)

**Scope:** Coding / refactor agents working on the student→mentor allocation system  
**Audience:** LLM-based coding agents (Codex, etc.) + human reviewers  

This file is a **contract**.  
Agents MUST follow this file and the upstream specs listed below.

---

## 1. Upstream specs (authoritative sources)

Always treat these as the **Single Source of Truth (SSoT)** for domain rules:

- `docs/LAW_Smart_Student_Allocation_v3.0.md`  
- `docs/Technical_SSoT_Smart_Student_Allocation_v3.0-TECH.md`  
- `docs/Repository Specification (SSoT).md`  
- `docs/📚 Refactor Narrative v3.0 — Import & Join Pipeline.md`  
- `docs/LAW v3.0 — Regulatory Coverage Map v1.0.md`

**AGENTS.md MUST NOT define new domain rules.**  
If anything here conflicts with these documents, **those documents win**.

Presentation-only authorities inside `app/ui/**`:

- `docs/UI_PRESENTATION_AUTHORITY.md` — defines **who owns** each visible Qt control/subcontrol surface (`STYLED`, `NATIVE`, `HYBRID`).
- `docs/UI_DESIGN_CONTRACT.md` — defines **how** the owned Matrix presentation is composed under the selected C2 workspace and V2 visual direction.
- `docs/DEVELOPER_DIAGNOSTICS.md` — canonical code-backed inventory for intentionally retained diagnostics/analysis/advanced controls and Rule Engine GUI/backend status.

These presentation/diagnostics documents are subordinate to LAW/Technical SSoT and domain authorities. They do not define or override domain behavior.

Machine hint:

- When you need exact semantics (wildcards, capacity formula details, special cases),
  **look up by rule ID** in the upstream docs (e.g. `JOIN-CORE-01`, `RANK-CORE-01`, `SCHOOL-01`).

---

## 2. Architecture boundaries (Core / Infra / UI)

### 2.1. Layers

- **Core** (`app/core/**`)
  - Pure domain + algorithms.
  - No I/O: no file, no network, no DB, no Qt, no CLI, no logging.
  - Deterministic: same inputs → same outputs (including ordering).
  - Pandas:
    - No `inplace=True`.
    - No merge-in-loops in hot paths.
    - Avoid chained assignment; use `.copy()` when needed.

- **Infra** (`app/infra/**`)
  - I/O (Excel, SQLite, WordPress), CLI, logging, QA exporters, history store.
  - May import Core; MUST NOT re-implement:
    - join semantics,
    - ranking semantics,
    - 8-step trace semantics.
  - Can add feature flags, error handling, and observability around Core.

- **UI** (`app/ui/**`)
  - PySide6 presentation layer (widgets, dialogs, view-models).
  - No business rules: no allocation/join/ranking/trace logic.
  - Talks to Infra/Core via public APIs.
  - Visual ownership changes MUST follow `docs/UI_PRESENTATION_AUTHORITY.md`; do not introduce a second incompatible visual owner for a geometry-sharing Qt control.
  - Workspace composition, presentation hierarchy, density, typography, diagnostics placement, bidi/resize/DPI presentation and V2 visual decisions MUST follow `docs/UI_DESIGN_CONTRACT.md`.

### 2.2. Dependency rule

Dependency direction:

- **Allowed:** `Core ← Infra ← UI`
- **Forbidden:**
  - Any import from `app.infra` or `app.ui` inside `app.core`
  - Circular imports between layers

If a requested change requires breaking this direction, agents MUST treat it as a red flag and use **RISK_REFUSAL**.

---

## 3. Non-negotiable domain invariants

These are hard constraints derived from LAW v3.0 + Technical SSoT + Coverage Map.

### 3.1. Join keys and profiles

**[INVARIANT-JOIN-01] Six join keys**

Exactly 6 join keys, all `int`, used end-to-end:

```text
["کدرشته", "جنسیت", "دانش آموز فارغ", "مرکز گلستان صدرا", "مالی حکمت بنیاد", "کد مدرسه"]
````

Canonical (snake_case) fields:

```text
group_code, gender_code, grad_status_code,
center_code, finance_code, school_code
```

Rules:

* DO NOT add/remove join keys.
* DO NOT change their type (must stay `int`).
* DO NOT change their semantics (including meaning of `0` as wildcard where defined in LAW/TECH).

**[INVARIANT-JOIN-02] JoinKeyProfile**

Domain object: `JoinKeyProfile`

* Immutable, hashable value object over the 6 join keys.
* Equality and `__hash__` MUST depend only on these 6 fields.

Domain:

* A Mentor MAY have multiple profiles (multi-profile mentor allowed at domain level).
* A Student has exactly one join profile (one row in canonical student frame).

Default v3 behavior (Refactor Narrative):

* `JoinKeyResolver` MAY be conservative:

  * a multi-profile mentor can be excluded from `usable_profiles`,
  * but MUST always be surfaced in QA outputs (`all_profiles` + issues).

Any change that:

* modifies the set of join keys, or
* redefines equality/hash for `JoinKeyProfile`

MUST be treated as a **policy-level change** → use **RISK_REFUSAL**.

**[INVARIANT-JOIN-03] Effective Join Keys / No Raw JoinKey Access**

* Allocation, QA, and export MUST consume **Effective Join Keys** only.
* Effective Join Keys come exclusively from `JoinKeyResolver` (canonicalize + infer + wildcard).
* Any direct use of raw join-key columns outside JoinKeyResolver is forbidden.
* Any change to join-key list or wildcard semantics requires **policy-level review** → use **RISK_REFUSAL**.

### 3.2. Mentor pipeline invariants

- **MENTOR_PIPELINE_V3_SSoT:** تمام ریفکتورهای ایمپورت پشتیبان باید MentorPipelineV3 را تنها SSoT برای استخر mentor نگه دارند؛ هیچ منطق join/الحاق جدیدی در Infra بیرون از این پایپلاین مجاز نیست.
- **MENTOR_QA_EXPORT_STABLE_SCHEMA:** اسکیمای خروجی QA برای مسائل الحاق پشتیبان باید پایدار بماند؛ هر تغییری باید با Technical SSoT و تست‌ها به‌روزرسانی شود و breaking change بدون هماهنگی ممنوع است.
- **NO_CORE_MENTOR_JOIN_LOGIC:** Core نباید منطق join پشتیبان را پیاده‌سازی کند؛ Core فقط استخر canonical خروجی MentorPipelineV3 را مصرف می‌کند.

---

### 3.2. Capacity and ranking

**[INVARIANT-CAP-01] remaining_capacity**

Formula (domain-level):

```text
remaining_capacity = capacity_limit - (assigned_baseline + allocations_new)
```

Invariants:

* `remaining_capacity` MUST NOT be negative in any canonical mentor pool.
* If a negative value would appear, it MUST be detected and turned into a QA issue or hard failure,
  according to LAW/TECH and QA rules.
* The canonical `remaining_capacity` column in mentor pools MUST always be derived from this formula;
  no alternative or independently maintained `remaining_capacity` source of truth is allowed.

**[INVARIANT-RANK-01] Ranking order (RANK-CORE)**

Ranking for student→mentor matching in Core:

1. `remaining_capacity` (descending)
2. `allocations_new` (ascending) — when present as explicit tie-breaker
3. `mentor_id` (ascending), stable sort

Rules:

* DO NOT change the ranking order.
* DO NOT introduce ratio-based ranking metrics (e.g. `occupancy_ratio`, composite scores) as domain concepts.
* Any optimization (pre-sorting, batching, etc.) MUST preserve this order.

---

### 3.3. Trace (8-stage)

**[INVARIANT-TRACE-01] Trace steps**

Per allocation, the trace has exactly 8 stages in this order:

```text
type, group, gender, graduation_status, center, finance, school, capacity_gate
```

Rules:

* You MAY add extra metadata around the trace (e.g. counts, debug info).
* You MUST NOT:

  * change names,
  * change order,
  * drop stages.

---

### 3.4. School / center wildcard, mentor type, matrix branch

High-level (exact semantics live in LAW/TECH + Coverage Map):

* **SCHOOL-01, CENTER-01, WILDCARD-COMBINE-01:**

  * `school_code = 0` and/or `center_code = 0` act as wildcards under specific rules.
  * Eligibility is defined as an AND of `school_match` and `center_match`.
* **MENTOR-TYPE-01:**

  * Mentor type derived from school-related fields (`NORMAL` vs `SCHOOL`).
  * Semantics defined in Technical SSoT.
* **MATRIX-BRANCH-01:**

  * Matrix rows belong either to a “normal” branch or a “school” branch.
  * No hybrid rows mixing branches.

Agents MUST NOT invent:

* new mentor types (e.g. “dual”, “mixed”) at domain level,
* or alternative wildcard semantics.

---

## 4. Refactor v3 — mentor import & join pipeline

All mentor import & join work in v3 MUST follow this unified pipeline:

```text
FieldRegistry → HeaderResolver → ValueCanonicalizer → JoinKeyResolver → MentorPoolBuilder
```

### 4.1. Stage responsibilities

**[PIPELINE-01] FieldRegistry (Infra)**

Single SSoT for mentor/join-related fields:

* canonical name,
* type,
* required/optional,
* `join_key_index` (1..6 or `None`),
* semantic version.

**[PIPELINE-02] HeaderResolver (Infra)**

Maps raw Excel headers → canonical field names using `FieldRegistry`.

Outputs:

* `mapping`,
* `issues` (missing, ambiguous, unknown),
* `can_continue` flag.

MUST fail-fast (`can_continue = False`) for:

* missing essential join headers,
* unresolvable ambiguity on join headers.

**[PIPELINE-03] ValueCanonicalizer (Infra)**

Converts raw cells → canonical domain values:

* group, gender, grad_status, finance, center, school, mentor_type, capacity, etc.

Outputs:

* canonical `DataFrame`,
* `issues` (invalid/unknown values),
* `failed_rows`,
* `can_continue` flag based on threshold (see Refactor Narrative v3.0 tunables).

**[PIPELINE-04] JoinKeyResolver (Infra, Core-facing)**

Constructs `JoinKeyProfile`(s) from canonical DF using `FieldRegistry`.

Builds:

* `all_profiles: dict[mentor_id, list[JoinKeyProfile]]`
* `usable_profiles: dict[mentor_id, JoinKeyProfile]`

Detects:

* missing join keys,
* invalid combinations,
* multiple profiles per mentor.

Emits:

* structured issues (`JoinKeyIssue`),
* `failed_rows`,
* `can_continue`.

**[PIPELINE-05] MentorPoolBuilder (Infra)**

Builds canonical mentor pool DF for Core:

* 6 join key columns (`int`),
* capacity columns (`capacity_limit`, `assigned_baseline`, `allocations_new`, `remaining_capacity`),
* mentor type/status,
* other domain fields.

Applies capacity gates from Policy/LAW/Technical SSoT.
Emits QA sheets and metrics.

### 4.2. Core consumption rule

Core (`build_matrix`, allocation) MUST only consume:

* canonical mentor DF from `MentorPoolBuilder`,
* canonical student DF from the existing pipeline,
* Policy/LAW-compatible config objects.

Core MUST NOT:

* reconstruct join keys from raw headers,
* re-implement join logic,
* re-implement capacity gates or wildcards.

Any new mentor import path MUST be wired through these 5 stages.

---

## 5. Coding style & quality (for all agents)

### 5.1. Typing and structure

All functions/methods:

* fully typed (parameters + return type),
* no bare `dict`/`list`/`set`/`tuple`; use typed generics.

`Any` and `# type: ignore`:

* only when strictly necessary,
* with smallest possible scope,
* MUST include a short comment (reason).

Functions:

* keep small and intention-revealing (~≤40 effective lines, ≤3 main branches),
* prefer composition (helpers, dataclasses) over inheritance.

### 5.2. Tools and commands

Every production change MUST be compatible with:

```bash
python -m pytest -q
mypy --strict app/core app/infra app/ui tests
ruff check .
black --check app/ infra/ ui/ tests/
```

Tests MUST:

* follow Arrange–Act–Assert pattern,
* be deterministic, with no hidden shared state,
* include regression tests for each bug fix,
* especially cover join, capacity, trace, and QA behaviors.

When changing join-key logic or QA joins, **required tests**:

* Parity unit tests (JoinKeyResolver vs legacy paths).
* Parity integration tests (allocation vs audit/export).

### 5.3. Mandatory pre-merge guards

The pre-merge guard suite (see `tools/ci/pre_merge_guards.py` and CI job
`pre-merge-guards`) is a required merge gate. Do NOT bypass or dilute these
guards by changing workflows or expanding allowlists without review.

---

## 6. Observability & QA

Keep `ExecutionTracer` and QA exporters working:

* 8-stage trace for allocations,
* QA workbooks for:

  * join-key issues,
  * invalid mentors,
  * capacity issues,
  * matrix vs students validation.

When behavior affecting QA changes:

* update / add QA tests and snapshots,
* do NOT weaken or remove QA checks to “make tests green”.

### 6.1. Retained diagnostics / advanced controls

The following eight capabilities are **intentionally retained and supported**. Their default `False` / OFF state does **not** mean dead code:

1. History Metrics — `enable_history_metrics`
2. Trace Debug Sheets — `enable_trace_debug_sheets`
3. Mentor Pipeline Trace — `enable_mentor_trace_debug`
4. Pool Governance Trace — `enable_pool_governance_trace`
5. Bucket Trace — `enable_bucket_trace`
6. QA Pool Coverage Rules — `enable_qa_pool_coverage_rules`
7. Trace Sheet Export — `enable_trace_export`
8. Use Join Buckets — `use_join_buckets`

Before deleting, consolidating, renaming, or refactoring any of these, agents **MUST** inspect `docs/DEVELOPER_DIAGNOSTICS.md` plus current consumers/tests.

Critical distinctions:

- **QA Pool Coverage Rules may affect validation PASS/FAIL**; do not classify them as diagnostic-only.
- **Use Join Buckets changes an algorithmic execution path**; do not classify it as diagnostic-only or change its default/algorithm without the appropriate domain/performance review.
- History Metrics reporting is not the same as history-aware allocation behavior.
- Bucket Trace observes bucketing; it does not enable Use Join Buckets.

Rule Engine status for future agents:

- **Rule Engine GUI: RETIRED** from the normal user workspace.
- **Rule Engine backend / CLI: INTENTIONALLY PRESERVED**.
- GUI absence is **not** evidence that `app/core/rule_engine.py`, CLI `rule-engine`, shared ranking/allocation/rules/loaders/QA/history infrastructure, or historical compatibility values are dead code.

---

## 7. Risk & refusal behaviour (RISK_REFUSAL)

Agents are expected to implement the **RISK_REFUSAL** protocol defined in their system-prompt.

Use **RISK_REFUSAL** (instead of guessing) when a requested change would:

* Modify any of these invariants:

  * 6 join keys (set, type, semantics),
  * ranking order,
  * 8-stage trace,
  * capacity rules,
  * wildcard school/center semantics,
  * mentor types or matrix branches.
* Break architecture boundaries:

  * Core ↔ Infra ↔ UI direction,
  * introduce I/O/logging/Qt into Core.
* Conflict with LAW / Technical SSoT / Repository Spec / Coverage Map.
* Require a broad refactor across many modules with unclear migration/rollback.

When in doubt → stop and emit **RISK_REFUSAL** with a short explanation and recommendation.

---

## 8. File-scoped guidance

When editing:

* `app/core/**`:

  * no I/O, no randomness, no time-based decisions;
  * keep join/rank/trace/capacity invariants intact.

* `app/infra/**`:

  * keep parsing, I/O, Excel/DB/CLI here;
  * do not redefine domain behavior; only adapt external formats to canonical forms.

* `app/ui/**`:

  * view-only orchestration and interaction;
  * do not add allocation/join/QA logic here;
  * for visual rendering or control/subcontrol styling, obey `docs/UI_PRESENTATION_AUTHORITY.md` before changing QSS, palette, fonts, or local stylesheets;
  * for C2/V2 workspace composition, hierarchy, density, diagnostics placement, bidi/resize/DPI presentation or visual-direction changes, obey `docs/UI_DESIGN_CONTRACT.md`;
  * for the eight retained diagnostics/analysis/advanced controls, keep GUI prose synchronized with `docs/DEVELOPER_DIAGNOSTICS.md` and do not turn presentation metadata into runtime authority.

If a change blurs these boundaries, treat it as a red flag and consider **RISK_REFUSAL**.

---

## 9. Versioning & maintenance

This AGENTS file targets:

* LAW v3.0
* Technical SSoT v3.0-TECH
* Repository Specification (SSoT)
* Refactor Narrative v3.0 — Import & Join Pipeline
* LAW v3.0 — Regulatory Coverage Map v1.0
* UI Presentation Authority (presentation-only; subordinate to LAW/TECH)
* UI Design Contract (C2/V2 composition-only; subordinate to LAW/TECH)
* Developer Diagnostics inventory (code-backed diagnostics/advanced presentation documentation; subordinate to LAW/TECH)

When any upstream doc changes in a way that affects code:

1. Update upstream doc first (LAW/TECH/Refactor/SSoT).
2. Adjust tests and implementation.
3. Update `AGENTS.md`:

   * bump version (e.g. v3.1 → v3.2),
   * add a short changelog entry.

Ensure changes are reviewed with **architectural focus**, not only line-by-line code review.

---

## 10. Mentor-focused PR checklist

For any PR touching mentors or mentor import:

- [ ] آیا ۶ کلید join همچنان `int` و بدون تغییر معنا هستند؟
- [ ] آیا ترتیب ranking (remaining_capacity ↓, allocations_new ↑, mentor_id ↑) و Trace ۸ مرحله‌ای حفظ شده است؟
- [ ] آیا مسیر ایمپورت از MentorPipelineV3 عبور می‌کند و اسکیمای QA exports حفظ شده است؟

## 11. HealthStatus و LLM Debug Report — قواعد Agentها

- **MUST:**
  - HealthStatus را فقط به‌عنوان Observability لایهٔ Infra/Shell ببینید؛ هیچ تغییر قانون دامنه از آن استخراج نکنید.
  - Health و `LLMDebugReport` صرفاً برای دیباگ، QA و insights CI استفاده شوند؛ خروجی آنها نباید رفتار Core را تغییر دهد.
- **MUST NOT:**
  - ۶ کلید join، ترتیب ranking یا Trace هشت‌مرحله‌ای را هنگام کار روی Health/LLM دستکاری کنید.
  - semantics جدید به لایهٔ Health یا گزارش LLM تزریق کنید یا آن را منبع قانون قرار دهید.
- **Guidance:**
  - کد Health در ماژول‌های Infra/Shell و UI integration قرار دارد؛ Core از Health بی‌اطلاع است.
  - Health check جدید فقط با خواندن سیگنال‌های QA/History موجود یا قوانین مستند LAW/Technical SSoT مجاز است؛ business rule تازه در Health ممنوع است.

## 12. Changelog

**v3.5**

* Added `docs/DEVELOPER_DIAGNOSTICS.md` discoverability and an explicit retention contract for the eight supported diagnostics/analysis/advanced capabilities.
* Recorded Rule Engine GUI as retired while preserving Rule Engine backend/CLI authority; no domain semantics changed.

**v3.4**

* Added `docs/UI_DESIGN_CONTRACT.md` discoverability beside `docs/UI_PRESENTATION_AUTHORITY.md`, clarifying ownership vs C2/V2 composition; no domain semantics changed.

**v3.3**

* Added the presentation-only `docs/UI_PRESENTATION_AUTHORITY.md` reference for `app/ui/**` visual ownership; no domain semantics changed.

**v3.2**

* Added Effective Join Keys / No Raw JoinKey Access constraint.
* Added mandatory parity unit + integration tests for join-key changes.

**v3.1**

* English, LLM-oriented version.
* Explicit rule IDs (`INVARIANT-*`, `PIPELINE-*`) for easier machine reference.
* Tight alignment with:

  * LAW v3.0,
  * Technical SSoT v3.0-TECH,
  * Refactor Narrative v3.0,
  * Regulatory Coverage Map v1.0.
* Stronger guidance for RISK_REFUSAL triggers and Core/Infra/UI boundaries.

## 13. SSoT و ظرفیت — قواعد تکمیلی Agentها

- **AGENT/SSOT-01 — تقدم LAW/Technical SSoT بر تست‌ها:**
  - Agentها باید LAW v3.0 و Technical SSoT را منبع حقیقت معنایی بدانند.
  - اگر انتظار تست با LAW/Technical تعارض داشت (مثلاً استفاده از `remaining_capacity` به‌عنوان ظرفیت اولیه یا تفسیر `capacity_current` به‌جای `capacity_limit`)، **تست باید اصلاح شود** و معنای دامنه نباید برای رضایت تست تغییر کند.
  - «تست‌ها SSoT نیستند»؛ آن‌ها قراردادهایی هستند که در صورت انحراف از LAW/Technical باید بازبینی شوند.

- **AGENT/CAPACITY-01 — ممنوعیت تغییر معنا برای فیلدهای ظرفیت:**
  - Agentها حق ندارند معناهای `capacity_current`, `capacity_limit`, `remaining_capacity` یا `allocations_new` را برای سبز شدن تست‌ها تغییر دهند.
  - به‌طور مشخص:
    - `capacity_current` باید همان «load جاری» بماند.
    - `capacity_limit` باید همان «ceiling ظرفیت» بماند.
    - `remaining_capacity` باید همان «متریک مشتق = capacity_limit − allocations_new» بماند.
  - اگر نیاز به مفهوم تازه‌ای (مثلاً ستون «ظرفیت» در ورودی/خروجی) باشد، باید به یک فیلد کاننیکال جدید مثل `capacity_limit` نگاشت شود و نه به سوءاستفاده از `capacity_current` یا `remaining_capacity`.
  - هر تغییر رفتاری که این معانی را دگرگون کند نیازمند آپدیت قبلی LAW/Technical است و صرفاً با تغییر کد مجاز نیست.

- **AGENT/HEADERS-01 — حفاظت از رجیستری هدرهای کاننیکال:**
  - در `app/core/common/columns.py` (یا رجیستری کاننیکال هدرها)، Agentها می‌توانند:
    - فیلد کاننیکال جدید و aliasهای آن را اضافه کنند.
    - aliasهای تازه برای فیلدهای موجود اضافه کنند.
  - Agentها نباید:
    - نام‌های فارسی/انگلیسی کاننیکال یا معنای سطح‌بالای فیلدهای موجود (مثل `capacity_current`, `remaining_capacity`, `mentor_id` یا ۶ کلید join) را تغییر دهند مگر با آپدیت صریح LAW/Technical SSoT.
  - اگر تست یا import به هدر تازه‌ای نیاز داشت (مثلاً «ظرفیت»)، این کار باید با:
    - افزودن فیلد کاننیکال جدید (مثلاً `capacity_limit`) و نگاشت هدر جدید به آن، یا
    - افزودن هدر جدید به‌عنوان alias فیلد موجود، در صورتی که با LAW/Technical SSoT تعارض نداشته باشد، انجام شود.

```
```

# AGENTS.md — Smart Student Allocation (Global)

**Spec Level:** agentsmd.net (HEADER → PURPOSE → SCOPE → ROLES → BOUNDARIES → TASK ROUTING → ALLOWED/PROHIBITED → QA → VERSIONING → EXAMPLES)  
**LAW / TECH Sources:** برای قواعد ثابت تخصیص، تنها `docs/LAW_Smart_Student_Allocation_v3.0.md` و `docs/Technical_SSoT_Smart_Student_Allocation_v3.0-TECH.md` مرجع هستند؛ سایر روایت‌ها (ازجمله اشاره به occupancy_ratio) LEGACY محسوب می‌شوند.
**Policy Ref:** Policy v1.0.3 (immutable, Policy-First)
**SSoT Ref:** SSoT v1.0.2 (immutable)
**Vision & Scope:** docs/System_Vision_Scope_Smart_Student_Allocation_v1.0.md (read-only)  
**Architecture Blueprint:** docs/System_Architecture_Blueprint_Smart_Student_Allocation_v1.0.md (read-only)  
**Supersedes:** any prior subsystem-only AGENTS (e.g., Eligibility Matrix-only rules)  
**Audience:** All agents (CoderAgent, InfraAgent, UIAgent, DocumentationAgent, QAAgent, ReviewerAgent, SupervisorAgent)

---

## PURPOSE

Single, authoritative contract for all LLM and human agents to operate the Smart Student Allocation
product with Policy-First, SSoT-First and Type-Safe discipline. Defines roles, boundaries,
determinism, routing, Python/static-analysis expectations, and QA across Core/Infra/UI + Agents
layer.

---

## SCOPE

Applies to the entire repository. Local AGENTS.md files do not exist; this document governs every
path. All agents must comply with Vision/Scope v1.0, Architecture Blueprint v1.0, Policy v1.0.3,
and SSoT v1.0.2. برای قواعد ثابت تخصیص، LAW v3.0 و Technical SSoT v3.0 بالادست همهٔ این اسناد هستند و هر تعارض یا اشاره به قواعد قدیمی (مثلاً رتبه‌بندی occupancy_ratio) LEGACY محسوب می‌شود.

---

## AGENT ROLES

- **PolicyAgent / SSoTOwner**  
  مالک روایت Policy و SSoT؛ معانی ستون‌ها، HistoryStore و AllocationChannelConfig را در
  `policy.json` تعریف می‌کند. هر تغییر در SCHOOL/GOLESTAN/SADRA/GENERIC یا قواعد dedupe باید ابتدا در
  Policy ثبت و با Coder/Infra/Docs/QA هماهنگ شود.

- **CoderAgent (Core)**  
  Implements deterministic, typed code within Core, honoring dependency rules and reproducibility.  
  مسئول پیاده‌سازی خالص توابعی مانند `dedupe_by_national_id`, `derive_allocation_channel`,
  منطق رتبه‌بندی، trace هشت‌مرحله‌ای و premap؛ هیچ I/O یا hardcode برای school/center ندارد و فقط به
  PolicyConfig تکیه می‌کند.  
  CoderAgent MUST:
  - Respect the global System Prompt:
    `SYSTEM — SENIOR PYTHON ARCHITECT & COACH (Policy-First, Type-Safe)`,
  - Follow the 6-section output protocol (DEBUG_REPORT + PLAN / CHANGES / PATCHES / TESTS / RUN & VERIFY / SELF-CHECK),
  - Produce code that is clean under `mypy --strict`, `ruff`, `black --check`.

- **InfraAgent**  
  Builds adapters, I/O, Excel pipelines, WordPress intake bridges within `app/infra`, `scripts`,
  `tools` respecting Core contracts. Chooses engines explicitly; handles atomic Excel writes per
  Infra specs. مسئول نگهداشت HistoryStore (ذخیره‌سازی، نرمال‌سازی کد ملی، تحویل DataFrame تمیز به
  Core) و خواندن/نوشتن `policy.json`.  
  InfraAgent MUST keep Infra code type-safe (mypy/ruff/black-clean) and aligned with Python Type
  System section.

- **UIAgent**  
  Works in PySide6 shell within `app/ui` and `run_gui.py`; no business logic; consumes Infra/Core
  services only. برچسب‌گذاری و نمایش `allocation_channel`, `dedupe_reason` و وضعیت‌های
  already_allocated/new_candidates را طبق Policy و Docs انجام می‌دهد و با Core/Docs برای اصطلاحات
  هماهنگ می‌ماند. Qt usage MUST follow Qt type-safety rules (enums, flags, no Qt in Core).

- **DocumentationAgent**  
  Updates docs in `docs/`, `README*`, guides. References Policy/SSoT without redefining. Maintains
  clarity for navigation and operations. مسئول همگام‌سازی روایت HistoryStore، dedupe، AllocationChannel
  و ستون `allocation_channel` در Vision/Scope، Architecture، Phase0 و این AGENTS است.

- **QAAgent / ReviewerAgent**  
  Enforces Policy/SSoT alignment, dependency boundaries, determinism, QA checklist and
  join/ranking invariants. Blocks drift. طراح تست برای `dedupe_by_national_id`, توابع کانال، پوشش
  ۶ کلید join، ranking ثابت و الزامات mypy/ruff/black است؛ هر تغییر history/channel بدون تست
  واحد/یکپارچه و بدون عبور از static analysis رد می‌شود.

- **SupervisorAgent**  
  Routes tasks to roles, checks version coherence (Policy 1.0.3, SSoT 1.0.2), ensures CI/test
  coverage and adherence to Architecture Blueprint و Python Type System. مالک جریان تغییرات
  history/channel (Policy → Core → Infra → Docs → UI → QA) و حل تعارضات بین لایه‌ها است.

---

## REPOSITORY STRUCTURE & NAVIGATION

- **Core (`app/core`)**  
  Deterministic, pure logic (pandas allowed). No I/O, no Qt, no network. Honors natural+stable
  sorting. Uses injectable `progress(pct: int, msg: str)` only. Uses injected `Clock/RandomProvider`
  for any time/random needs (هیچ `datetime.now()` یا `random.random()` مستقیم در Core مجاز نیست).

- **Infra (`app/infra`, `scripts`, `tools`)**  
  I/O, Excel pipelines, adapters, logging, WordPress intake, Excel fallback atomic writer. Calls
  Core; never the reverse. مسئول atomic writes، sanitizing sheet names و امنیت مسیرها/SQL است.

- **UI (`app/ui`, `run_gui.py`)**  
  PySide6 shell/view. Consumes Infra/Core APIs; forbids business logic and file/network I/O beyond
  UI needs. Qt usage fully typed (enums/flags)، no direct Policy/SSoT manipulation.

- **Agents Layer (`app/agents` if present)**  
  Orchestration only; must not break Core/Infra/UI boundaries.

- **Docs (`docs`, top-level READMEs, guides)**  
  Policy/SSoT references only. Do not embed business logic.

- **Config (`config/`)**  
  Policy JSON/YAML loaders; immutable schema from Policy v1.0.3 and SSoT v1.0.2. No hardcoded
  policy in code.

- **Tests (`tests/`)**  
  Layer-aligned; Core tests remain pure/deterministic; Infra/UI tests may use fixtures and golden
  outputs. CI must run `pytest`, `mypy --strict`, `ruff`, `black --check`.

- **Navigation**  
  Use `rg` برای جست‌وجو؛ از `ls -R`/`grep -R` بی‌هدف پرهیز کنید. Follow path by layer; do not
  cross-write.

---

## BINDING TO VISION/SCOPE v1.0 & ARCHITECTURE BLUEPRINT v1.0

- Always read **System_Vision_Scope_Smart_Student_Allocation_v1.0.md** for product goals, user
  journeys and non-functional constraints.
- Always read **System_Architecture_Blueprint_Smart_Student_Allocation_v1.0.md** for layered rules,
  module boundaries and dependency direction (UI → Infra → Core only).
- Any change conflicting with these documents is forbidden. If ambiguity arises, SupervisorAgent
  decides by referencing these documents and Policy/SSoT.

---

## POLICY & SSoT ENFORCEMENT

  - **Immutable invariants (do NOT alter):**
    - **Join Keys (6, int):** `"کدرشته"` (group_code), `"جنسیت"` (gender),
      `"دانش آموز فارغ"` (graduation_status), `"مرکز گلستان صدرا"` (center),
      `"مالی حکمت بنیاد"` (finance), `"کد مدرسه"` (school_code).
      - **Trace mapping note:** `"کدرشته"` feeds both the `type` and `group` trace steps
        (one-to-many mapping join key → trace steps).
    - **Ranking Policy (stable):** طبق LAW v3.0 / Technical SSoT v3.0 صرفاً بر اساس
      `remaining_capacity` نزولی و سپس `mentor_id` صعودی (natural + stable) است؛ هر روایت قبلی
      دربارهٔ `occupancy_ratio` LEGACY و صرفاً تاریخی است.
    - **Trace (8-step explainability):** `type, group, gender, graduation_status, center, finance,
      school, capacity_gate` with candidate counts after each filter.
  - **Determinism:** identical inputs yield identical outputs; stable sorts everywhere; no randomness/
    time-based logic in Core.
  - **Policy Version:** 1.0.3; **SSoT Version:** 1.0.2. Never downgrade/upgrade silently.

- **History-Aware invariants:**  
  `HistoryStore` باید تنها مرجع گذشتهٔ تخصیص باشد؛ نرمال‌سازی کد ملی و
  `dedupe_by_national_id` فقط در Core و بر اساس Policy تعریف می‌شود؛ هیچ عامل دیگری اجازهٔ
  تغییر semantics را ندارد. `AllocationChannel`, `AllocationChannelConfig` و ستون
  `allocation_channel` در summary/trace باید دقیقاً از Policy تبعیت کنند؛ کانال‌ها محدود به
  `SCHOOL`, `GOLESTAN`, `SADRA`, `GENERIC` هستند.

- **Policy-First:** Load policy from config/policy.json (or policy.yaml equivalent); never hardcode
  policy constants in Core.

- **SSoT-First:** Use SSoT datasets/schemas as canonical truth; avoid schema drift.

---

## HISTORY & ALLOCATION CHANNEL COORDINATION

هر ویژگی history-aware (HistoryStore، national_code normalization، dedupe) یا AllocationChannel
باید جریان زیر را طی کند:

1. **PolicyAgent / SSoTOwner** قواعد را در `policy.json` و مستندات Policy ثبت/به‌روزرسانی می‌کند.
2. **CoderAgent** منطق خالص (`dedupe_by_national_id`, `derive_allocation_channel`,
   `derive_channels_for_students`) را مطابق Policy پیاده‌سازی یا اصلاح می‌کند؛ ۶ کلید join و
   ranking دست‌نخورده می‌مانند.
3. **InfraAgent** HistoryStore و I/O (Excel/DB/WordPress) را با قواعد جدید همگام می‌کند و ورودی
   تمیز برای Core فراهم می‌سازد.
4. **DocumentationAgent** همهٔ اسناد (Vision/Scope، Architecture، Phase0، READMEها) را با روایت
   جدید history/channel هم‌راستا می‌کند و تغییرات را در changelogها ثبت می‌کند.
5. **UIAgent** نمایش و diagnostics (`allocation_channel`, `dedupe_reason`,
   `already_allocated/new_candidates`) را به‌روزرسانی می‌کند و از Policy/Docs برای copywriting کمک
   می‌گیرد.
6. **QAAgent / ReviewerAgent** تست‌های واحد/یکپارچه برای history/channel را اضافه یا
   به‌روزرسانی کرده و اجرای آن‌ها را قبل از merge الزامی می‌کند.

هیچ تغییر history/channel بدون عبور از این چرخه و تأیید SupervisorAgent و QAAgent اجازهٔ merge
ندارد؛ Trace و summary باید ستون `allocation_channel` و شمارش dedupe را منعکس کنند.

---

## MENTOR POOL GOVERNANCE (MentorProfile)

- **Policy-First:** هر تغییری در استخر پشتیبان‌ها باید از طریق MentorProfile/mentor_status در
  Policy/SSoT اعمال شود (`ACTIVE`, `FROZEN` و در صورت نیاز `RESTRICTED_*`). حذف ردیف از
  InspactorReport یا Excel تنها به‌عنوان workaround اضطراری مجاز است و باید در گزارش عملیات ثبت شود.
- **Infra Ownership:** InfraAgent مسئول خواندن/نوشتن MentorProfile (policy.json یا فایل پروفایل
  مجزا) و تحویل DataFrame تمیز به Core است. تغییراتی که از UI/CLI می‌آیند باید در همین منبع
  ذخیره شوند و audit log versioned داشته باشند.
- **Core Behavior:** CoderAgent باید مرحلهٔ BuildMentorPool را طوری نگه دارد که تنها پروفایل‌های
  `ACTIVE` وارد eligibility matrix شوند و وضعیت هر mentor در trace/summary ثبت شود. Core هرگز
  نام‌ها یا شناسه‌ها را هاردکد نمی‌کند و فقط روی mentor_status تصمیم می‌گیرد؛ Join Keys و
  ranking بدون تغییر باقی می‌مانند.
- **UI/CLI Responsibilities:** UIAgent باید پنل «مدیریت استخر پشتیبان‌ها» را به MentorProfile متصل
  کند تا اپراتور بتواند وضعیت را مشاهده/تغییر دهد و پیشنهادهای HistoryStore را صرفاً به‌عنوان
  توصیه ببیند. هیچ تغییری نباید local-only باشد؛ هر دکمهٔ toggle باید موفقیت persistence را
  اعلام کند.
- **QA Enforcement:** ReviewerAgent باید اطمینان دهد که تست‌های یکپارچه وجود دارد تا نشان دهند
  mentor_status=`FROZEN` حتی در صورت بازگشت در InspactorReport به استخر وارد نمی‌شود و trace
  دلیل سیاستی (مثلاً `FROZEN (Policy v1.0.3)`) را گزارش می‌کند.

---

## PYTHON TYPE SYSTEM & TOOLING (CoderAgent / InfraAgent)

این سکشن جزئیات Python-level را برای CoderAgent و InfraAgent مشخص می‌کند و مکمل System Prompt
Type-Safe است.

### 1) Static Analysis & Type Stubs

- Core و Infra باید تحت این ابزارها **بدون خطای جدید** باشند:
  - `pytest`,
  - `mypy --strict`,
  - `ruff`,
  - `black --check` (line-length=100).
- برای کتابخانه‌های شخص ثالث مهم، stubs در dev-deps نگه‌داری شوند، مثلاً:
  - `types-PySide6`, `types-PyYAML`, `types-requests` و مشابه‌ها.
- استفاده از `mypy --install-types` در CI یا dev برای به‌روز نگه‌داشتن stubs مجاز است.
- هر `# type: ignore[...]`:
  - باید error code داشته باشد (مثلاً `attr-defined`, `call-arg`, …)،
  - باید یک توضیح کوتاه در همان خط داشته باشد،
  - ترجیحاً در بازنگری بعدی حذف یا با refactor/`cast` جایگزین شود.

### 2) Advanced Type Hints

- از containers بدون نوع (`dict`, `list`, `set`, `tuple` بدون پارامتر) پرهیز شود؛ همیشه parametrized:
  - `dict[str, int]`, `list[StudentSchema]`, `set[int]`, …
- در صورت مفید بودن، از انواع دقیق‌تر استفاده شود:
  - `Literal["fa", "en", "fa_en"]` برای مودهای محدود، نه `str` ساده،
  - `Sequence[T]` / `Mapping[K, V]` به‌جای `list[T]` / `dict[K, V]` وقتی فقط read-only مد نظر است.
- برای رکوردهای ساخت‌یافته (دانش‌آموز، پشتیبان، pool rows و …) از:
  - `TypedDict`, `dataclasses` یا `NamedTuple` استفاده شود.
- در ماژول‌های جدید یا refactor شده، `from __future__ import annotations` ترجیح داده می‌شود.

### 3) Pandas & DataFrame Schemas

- DataFrameهای مهم (students, mentors, pools, crosswalk, history) باید schema مستند داشته باشند
  (مثلاً `StudentRow(TypedDict)` در `schemas.py`).
- Join keys:
  - باید به‌صورت ستون‌های integer-typed نگه‌داری شوند (ترجیحاً `pd.Int64Dtype()` برای nullable)،
  - قبل از `merge`/`join` باید نوع (dtype) دو طرف یکسان و validate شود.
- برای type coercion:
  - از `.astype(...)` صریح با dtype مشخص استفاده شود،
  - از تکیه بر inference شفاف‌نبودن پرهیز شود.
- برای performance:
  - از `.apply(lambda)` روی سطرها در hot pathها خودداری شود،
  - تا حد امکان vectorized ops و precomputed maps استفاده شود.

### 4) Qt / UI Types

- Qt/PySide6 هرگز در Core import نمی‌شود؛ هرگونه Qt usage به UI و adapterهای نازک Infra محدود است.
- در UI/Infra:
  - از enums و flags کامل (`Qt.AlignmentFlag`, `Qt.CursorShape`,
    `QDialogButtonBox.StandardButton`, `QColor.NameFormat`, …) استفاده شود،
  - از aliasهای قدیمی مانند `Qt.AlignCenter`, `QDialogButtonBox.Save` پرهیز شود.
- اگر API خاصی در stubs به‌خوبی تایپ نشده:
  - call مربوطه در یک helper کوچک ایزوله شود،
  - باقی ماژول fully-typed بماند.

### 5) Async / Concurrency

- Core کاملاً **synchronous** می‌ماند؛ وابستگی به `asyncio` و async I/O در Core ممنوع است.
- Infra می‌تواند async استفاده کند (مثلاً برای WordPress/HTTP) به شرطی که:
  - مرز async واضح باشد (مثلاً CLI از `asyncio.run(...)` استفاده کند)،
  - UI integration با patternهای صحیح Qt (threadpool/QThread) انجام شود و event loop block نشود.
- کارهای CPU-bound طولانی در Core پیاده‌سازی می‌شود ولی از Infra/UI از طریق threads یا workerها
  فراخوانی می‌گردد؛ busy-wait در UI thread ممنوع است.

### 6) Error Handling, Logging & Security (Python-level)

- Hierarchy استثناهای دامنه در `core.exceptions` نگه‌داری می‌شود:
  - `AllocationError` (base),
  - `EligibilityError`, `CapacityError`, `DataValidationError`, `InternalError`, …
- Core:
  - این استثناهای دامنه را raise می‌کند،
  - log نمی‌کند و استثناءها را بی‌صدا نمی‌بلعد.
- Infra/UI:
  - استثناها را با `logging.getLogger(__name__)` log می‌کند،
  - آن‌ها را به پیام کاربر یا exit code مناسب تبدیل می‌کند.
- ممنوع:
  - `except:` bare،
  - `except Exception:` بدون log و بدون re-raise/translation.
- Security در Infra/CLI:
  - همیشه queryهای SQL را با parameters بسازید؛ f-string SQL ممنوع است،
  - مسیر فایل‌ها و input کاربر را sanitize کنید (`..` و تغییر drive را reject کنید)،
  - secrets (passwords, API keys, tokens, PII حساس) هرگز log نشود.

### 7) Testing Strategy (Python-specific)

- Core:
  - باید پوشش تست بالای ۹۰٪ داشته باشد (unit-level deterministic tests),
  - هم “happy path” و هم failure modes (استثناهای دامنه) را پوشش دهد.
- Infra/UI:
  - هدف پوشش ~۷۰٪، با تمرکز بر مسیرهای اصلی I/O و error handling،
  - برای Excel/trace/QA outputs از snapshot/golden tests استفاده شود (schema + key columns + چند ردیف نمونه).
- Property-based tests (مثل `hypothesis`):
  - در صورت به‌کارگیری، invariants باید واضح باشند (مثلاً ظرفیت منفی نشود، join keys intact بمانند)،
  - از seeds مشخص برای دترمینیسم تست‌ها استفاده شود.

---

## ALLOWED ACTIONS

- Edit only files within assigned agent scope and layer boundaries.
- Use pandas in Core for tabular logic; avoid inplace mutations; copy before transforms when needed.
- Apply natural+stable sort for any identifier ordering (e.g., mentor_id) using shared helpers.
- Implement atomic Excel writes with sanitized sheet names in Infra.
- Reference Policy/SSoT/Vision/Architecture docs; cite versions in PRs/commits.
- Add tests (unit/snapshot) per layer؛ prefer deterministic fixtures and golden outputs.
- Use `pytest`, `mypy --strict`, `ruff`, `black --check` as standard quality gates.

---

## FORBIDDEN ACTIONS

- Breaking dependency direction (Core depending on Infra/UI/Agents).
- Introducing I/O, Qt signals or network calls in Core.
- Hardcoding policy/SSoT constants داخل Core logic؛ bypassing config loaders.
- Altering Join Keys, Ranking Policy, Trace stages, Policy/SSoT versions.
- Using non-deterministic operations (random, time-based ordering, unstable sorts) در Core.
- Merging data in loops (avoid repeated merges; use premap).
- Using `inplace=True` pandas mutations or lambda validators returning None.
- Hardcoding file paths/dates؛ embedding secrets؛ modifying policy documents directly.
- Logging secrets/PII؛ استفاده از f-string برای SQL.

---

## DEPENDENCY BOUNDARIES

- Allowed imports: UI → Infra → Core only. Agents/orchestration may call UI/Infra/Core but must not
  invert dependencies.
- Core exposes pure functions/classes; Infra wraps Core with I/O; UI consumes Infra/Core via
  adapters؛ Agents orchestrate بدون embed کردن business logic.
- Infra may depend on `config/` loaders; Core may depend on `config/` contracts but not on Infra/UI
  implementations.

---

## TASK ROUTING RULES

- SupervisorAgent assigns tasks per layer:
  - Core logic → CoderAgent،
  - I/O/Excel/WordPress adapters → InfraAgent،
  - PySide6 view/controller → UIAgent،
  - docs/guides → DocumentationAgent،
  - reviews/QC → QAAgent/ReviewerAgent.
- Cross-layer tasks must be decomposed into layer-scoped sub-tasks؛ no single agent edits multiple
  layers unless explicitly authorized by SupervisorAgent.
- Any policy/SSoT ambiguity → escalate to SupervisorAgent with references to Policy v1.0.3 &
  SSoT v1.0.2.

---

## BEST-OF-N DECISION RULES FOR AGENTS

- **When to use best-of-N:**
  - Routine, well-specified, low-risk edits (typos, single-column additions, doc paragraph updates)
    → default N = 1.
  - Non-trivial refactors within a single layer (**Core**, **Infra** یا **UI**) که چند طراحی ممکن دارد
    → best-of-2 یا best-of-3.
  - Ambiguous UX/copy یا تفاوت‌های ساختاری (layout, error-reporting style) → best-of-2/3.
  - Large یا cross-cutting changes در یک لایه فقط وقتی best-of-N مجاز است که QA checklist و tests
    واضح باشند؛ در غیر این صورت scope را کوچک کنید.

- **How to compare best-of-N candidates:**
  - هرگز انتخاب تصادفی؛ ارزیابی بر اساس Policy v1.0.3 و SSoT v1.0.2 (join keys، ranking،
    determinism، trace steps) و dependency boundaries.
  - ترجیح به تغییرات کوچک‌تر و localized که تسک را کامل انجام می‌دهند و deterministic هستند.
  - ترجیح به variantهایی که tests مرتبط اضافه/به‌روز می‌کنند و سبک پروژه را حفظ می‌کنند.
  - اگر variants معادل بودند، آنی را انتخاب کنید که فایل‌های کم‌تری را لمس کرده و abstraction
    اضافه تحمیل نکند.

- **Defaults and safeguards:**
  - Routine, well-specified tasks → N = 1.
  - Medium complexity → N = 2 (تا حداکثر N = 3).
  - High-risk refactors با guardrails تستی قوی → حداکثر N = 3.
  - از best-of-N برای brute-force کردن requirements مبهم استفاده نکنید.

- **Role-specific behavior:**
  - **CoderAgent / InfraAgent / UIAgent:** می‌توانند برای تولید داخلی best-of-N بخواهند؛ باید در
    PLAN/DEBUG_REPORT توضیح دهند چرا.
  - **QAAgent / ReviewerAgent:** variants را با Policy/SSoT invariants، QA checklist و scope می‌سنجد و توضیح
    می‌دهد چرا variant انتخاب‌شده بهتر است.
  - **SupervisorAgent:** حداکثر N (N ≤ 3) را enforce می‌کند و می‌تواند در نواحی حساس Core
    (join/ranking logic) best-of-N را ممنوع کند مگر با توجیه صریح.

- **Interaction with user-specified N:**
  - N اعلام‌شده‌ی کاربر را احترام بگذارید، ولی همان قواعد انتخاب را اعمال کنید.
  - اگر N خواسته‌شده بیش از حد است (مثلاً N = 10 برای تغییر کوچک)، در PLAN توضیح دهید که N
    مؤثر کوچک‌تر است، حتی اگر tooling candidates بیشتری بسازد.

---

## TESTING COMMANDS

- **Core:** `pytest tests/core -q`
- **Infra:** `pytest tests/infra -q`
- **UI (headless where possible):** `pytest tests/ui -q`
- **All layers:** `pytest -q`
- **Type checking:** `mypy --strict`
- **Lint:** `ruff check .`
- **Formatting:** `black --check .`

---

## QA CHECKLISTS FOR AGENTS

- **Policy/SSoT:**
  - Policy version == 1.0.3, SSoT version == 1.0.2،
  - Join Keys (6) و Ranking Policy و Trace 8-step بدون تغییر.

- **Determinism:**
  - Stable sorts، no randomness/time-based logic در Core،
  - Natural key برای identifiers (mentor_id, …)،
  - Fixtures و golden outputs reproducible.

- **Boundaries:**
  - UI → Infra → Core dependency flow،
  - no I/O/Qt در Core،
  - no policy constants hardcoded،
  - HistoryStore فقط توسط Infra نوشته و توسط Core به‌شکل خالص مصرف می‌شود،
  - AllocationChannel تنها از PolicyConfig خوانده می‌شود.

- **Data Contracts & Pandas:**
  - Join keys typed as int؛ schemas match SSoT،
  - premap استفاده شده؛ repeated merges در loops وجود ندارد،
  - no inplace pandas ops؛ no chained assignment بدون `.copy()`.

- **Excel/Adapters:**
  - Atomic Excel writer با sheet names sanitized،
  - engine selection explicit (openpyxl/xlsxwriter fallback)،
  - HistoryStore read/write سنجیده می‌شود (type-safety، نرمال‌سازی کد ملی، dedupe traceable).

- **Static Analysis & Coverage:**
  - `pytest` green،
  - `mypy --strict` بدون خطای جدید،
  - `ruff` و `black --check` بدون violation،
  - Core coverage ≳ 90٪؛ Infra/UI coverage ≳ 70٪،
  - هر bug fix همراه با regression test.

- **History/Channel & Docs:**
  - تست‌های ویژه برای `dedupe_by_national_id`, `derive_allocation_channel`, `allocation_channel` در
    summary/trace و سناریوهای already_allocated/new_candidates،
  - Docs تغییرات را در Vision/Scope، Architecture و این AGENTS منعکس می‌کند؛ هیچ redefinition در Policy
    وجود ندارد؛ navigation instructions intact.

---

## VERSIONING POLICY

- AGENTS.md version tracks Policy v1.0.3 & SSoT v1.0.2 alignment. Any Policy/SSoT change requires
  SupervisorAgent review and AGENTS.md update. Changelog must be appended؛ historical sections
  remain immutable.

---

## EXAMPLES

- **Valid:** CoderAgent updates a `app/core` function to apply stable natural sort for `mentor_id` using
  shared `natural_key`; adds unit test in `tests/core`; cites Policy v1.0.3 join/ranking invariants
  and passes `mypy --strict`, `ruff`, `black --check`.
- **Invalid:** InfraAgent edits Core to read Excel directly؛ UIAgent hardcodes ranking policy؛
  DocumentationAgent rewrites Join Keys؛ any agent introduces non-deterministic shuffle؛ هر تغییری
  که باعث خطای جدید در mypy/ruff/black شود بدون اصلاح رد می‌شود.

---

## CHANGELOG

- **v1.0 (Global):** Replaces Eligibility Matrix-only AGENTS with global, layered contract; embeds
  Policy 1.0.3 & SSoT 1.0.2 invariants, dependency boundaries, routing, testing and QA rules across
  Smart Student Allocation.
- **v1.1:** Added BEST-OF-N decision rules for agents (supervised variant selection).
- **v1.2:** تعریف صریح نقش‌ها و جریان هماهنگی برای HistoryStore، `dedupe_by_national_id` و
  `AllocationChannel` (SCHOOL / GOLESTAN / SADRA / GENERIC) بدون نقض Policy-First و ۶ کلید join.
- **v1.3:** Added Python Type System & Tooling section; aligned AGENTS with System Prompt
  Type-Safe rules (mypy --strict, ruff, black, Qt type-safety, coverage targets).

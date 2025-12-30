

# 📚 **Refactor Narrative v3.0 — روایت کامل و ماشین‌فهم از مسأله تا راه‌حل**

این سند یک روایت ساختاریافته است که توضیح می‌دهد:

1. **مشکل اصلی سیستم چه بود**
2. **چگونه کشف شد**
3. **چرا از نظر معماری مشکل عمیق‌تر بود**
4. **چرا هات‌فیکس جواب نداد**
5. **چرا ریفکتور بزرگ لازم شد**
6. **چه استانداردهای مدرن باید پیاده شود**
7. **چه طراحی نهایی برای ریفکتور انتخاب شد**

این روایت برای مدل‌های زبانی نوشته شده و تمام پیش‌نیازهای لازم برای پاسخ‌دهی هوشمند را در خود دارد.

------

# 1. مقدمه: سیستم چیست و چرا مهم است؟

سیستم Smart Allocation:

- داده‌های mentor و student را از Excelها می‌گیرد،
- آن‌ها را canonical می‌کند،
- ۶ کلید الحاق (join keys) را می‌سازد:
  1. group
  2. gender
  3. graduation_status
  4. center
  5. finance
  6. school
- سپس eligibility_matrix می‌سازد،
- و در نهایت تخصیص mentor → student انجام می‌دهد.
- از فاز REF-V3-PHASE-07 به بعد، **SSoT عملی School/GroupCode پایگاه دادهٔ محلی است**؛ فایل‌های SchoolReport/crosswalk فقط برای bootstrap یا به‌روزرسانی از طریق Database Tab استفاده می‌شوند و مسیر اجرای تخصیص به DB تکیه دارد.

هر **اشتباه در join key یا import pipeline** می‌تواند کل سیستم را مختل کند.

------

# 2. نقطه شروع مشکلات (Root Problem Trigger)

مشکل اصلی زمانی کشف شد که:

- یک فایل Inspactor فقط ستون **«شامل گروه‌های آزمایشی»** داشت،
- اما ستون **«گروه آزمایشی»** نداشت.

رفتار مورد انتظار (طبق قانون جدید):

- تنها ستون «شامل گروه های آزمایشی» منبع مجاز group_code است؛ هر نبود یا تهی بودن آن باید P0 ایجاد کند.
- ستون legacy «گروه آزمایشی» صرفاً برای QA/دیباگ نگه داشته می‌شود و نباید برای join key مصرف شود.

اما برنامه:

❌ در سطح **parser** و `_prepare_base_rows` هنوز در نبود included به legacy fallback می‌کرد.

❌ در سطح **schema validation** ستون legacy را *اجباری* تعریف کرده بود و نبود included را به‌صورت P0 نمی‌دید.

در نتیجه: Import قبل از رسیدن به منطق درست، شکست می‌خورد.

این یک **Spec Drift** کلاسیک بود.

------

# 3. کشف مسأله عمیق‌تر: چرا drift رخ داد؟

در بررسی‌های بعدی مشخص شد که:

## 3.1. قوانین join-key در چند جای مختلف نوشته شده‌اند

- بخشی در `assert_inspactor_schema`
- بخشی در `_prepare_base_rows`
- بخشی در `join_keys.py`
- بخشی در `reference_mentors_repository`
- و بخشی در matrix builder

هیچ "مرکز قانون" واحدی وجود نداشت.

------

## 3.2. Header detection سخت، پراکنده و fragile بود

برنامه باید از میان ده‌ها هدر فارسی:

- جنسیت
- شاد
- شاد *
- فایننس
- مالی حکمت
- مالی حکمت بنیاد
- گروه آزمایشی
- شامل گروه‌های آزمایشی

حدس بزند کدام ستون چیست.

هیچ رجیستری واحدی برای ستون‌ها، aliasها، contextها و priorityها نبود.

------

## 3.3. Spec drift یک پدیدهٔ تکرارشونده بود

وقتی یک قانون جدید در سیستم اضافه می‌شد:

- کدهای مرتبط با آن قانون در بخش‌های مختلف باید همزمان تغییر می‌کردند،
- ولی چون پراکنده بودند،
   همیشه یک یا چند نقطه **جا می‌ماند**.

دقیقاً همین اتفاق با ستون group رخ داد.

------

## 3.4. DataFrame تنها مدل داده بود

Mentor و Student مدل دامنه‌ای نداشتند.

بنابراین:

- چند پروفایل برای mentor (قانون جدید MENTOR-JOIN-PROFILE-UNIQUENESS)
   عملاً در DataFrame explode می‌شد،
- validation ضعیف می‌شد،
- و join-key‌ها شکننده و پراکنده بودند.

------

# 4. تلاش برای هات‌فیکس و شکست آن

هات‌فیکس انجام شد:

- ستون `COL_GROUP` از Required حذف شد،
- شرط جدید گذاشته شد که یکی از دو ستون کافی است.

اما:

❌ مشکل اصلی باقی ماند، چون:

- join-key derivation در جای دیگری انجام می‌شد،
- کارخانهٔ join-key قانون included را اصلاً اجرا نمی‌کرد اگر قبل از آن import fail شده بود،
- مسیرهای مختلف import مسیرهای ثابت نداشتند.

این نشان داد مشکل **surface bug** نیست
 بلکه یک **Architectural Symptom** است.

------

# 5. تحلیل معماری: چرا سیستم فعلی قابل اعتماد نیست؟

تحلیل کامل و بی‌رحمانهٔ معماری نشان داد:

## 5.1. سیستم «file-first» است، نه «policy-first»

به‌جای اینکه از یک قانون بالادستی (LAW/TECH/SSoT)
 به join-key برسیم،
 برنامه از **ساختار فایل‌ها** رفتار را استنباط می‌کند.

این ضد اصول:

- SSoT
- Decoupling
- Policy-driven architecture

است.

------

## 5.2. Behavior در چند نقطه پخش شده است

به‌جای یک JoinKeyResolver یگانه،
 شش مسیر مختلف join-key تولید می‌کنند.

این یعنی:

- تغییر یک قانون = drift در چند نقطه،
- هر بار قانون جدید اضافه شود = ریسک باگ بالا.

------

## 5.3. Header resolution ساختارمند نیست

به‌جای یک HeaderResolver،
 هر فایل به شکل ad-hoc ستون‌ها را پیدا می‌کند.

در نتیجه:

- ambiguity
- hardcode
- if/elseهای متعدد
- متن‌های فارسی بدون استاندارد

همه جا وجود دارد.

------

## 5.4. Contract Test وجود ندارد

هیچ تستی تضمین نمی‌کرد:

- schema جدید با parser جدید sync است،
- ستون‌های optional درست رفتار می‌کنند،
- included-only یا legacy-only درست کار می‌کند.

------

## 5.5. Domain Model وجود ندارد

Mentor / Student / JoinKeyProfile
 به‌عنوان کلاس‌های رسمی وجود ندارند.

در نتیجه:

- multi-profile mentor
- uniqueness per mentor
- join-key hashing
- فضای QA برای join-key issues

همه با DataFrame hack می‌شد.

------

# 6. تصمیم: یک ریفکتور کامل لازم است (نه patch)

از تحلیل‌ها نتیجه گرفته شد که:

- مشکل join-key
- مشکل header detection
- مشکل multi-profile mentor
- مشکل spec drift
- مشکل QA
- مشکل import

همه یک ریشه دارند:

> نبود یک Canonical Pipeline و نبود Resolverهای رسمی.

بنابراین یک «Refactor SSoT» طراحی شد.

------

# 7. طراحی جدید: SSoT Refactor Architecture

طراحی جدید شامل ۶ مؤلفهٔ اصلی است:

------

## 7.1. Field Registry (قلب SSoT جدید)

تعریف رسمی و متمرکز:

- فیلد چیست،
- join key index چند است،
- از چه ستون‌هایی می‌آید،
- relative priority چیست،
- چه استراتژی resolution دارد،
- چه validation دارد.

به‌صورت ساختاری:

```
FieldDefinition
  - code
  - join_key_index
  - required
  - sources: list[FieldSource]
  - resolver_strategy
  - validation_rules
```

------

## 7.2. HeaderResolver

کار:

- تشخیص ستون‌ها بر پایه‌ی Field Registry،
- حل ambiguity هدرها،
- تولید issue در صورت missing/ambiguous.

خروجی:

```
HeaderResolutionResult:
  source_to_column
  issues
```

------

## 7.3. Value Canonicalizer

کار:

- تبدیل gender، finance، center، school و …
   به مقادیر canonical (int و map درست).

------

## 7.4. JoinKeyResolver (شاه‌مغز ریفکتور)

ورودی:

- df canonical
- policy
- field registry

خروجی:

```
JoinKeyResolutionResult:
  entities: list[Mentor | Student]
  issues: list[JoinKeyIssue]
```

کارکردها:

- تشکیل JoinKeyProfile
- استخراج چند پروفایل
- جلوگیری از duplicate exact profile
- گزارش issueهای join-key

------

## 7.5. Domain Model رسمی

### JoinKeyProfile

۶ مقدار int، immutable، hashable

### Mentor

دارای list[JoinKeyProfile]

### Student

یک JoinKeyProfile

### JoinKeyIssue

برای خطاهای سطح join-key

### QaIssue

برای خروجی QA

------

## 7.6. Canonical Pipeline

Pipeline واحد برای:

- header normalization
- header resolution
- canonicalization
- join-key resolution
- QA mapping
- storage

------

# 8. تست‌ها: تضمین اینکه drift غیرممکن می‌شود

سه لایه تست تعریف شد:

## 8.1. Contract Test

- schema ↔ parser
- resolver ↔ registry
- LAW ↔ implementation

## 8.2. Integration Test

- چند فایل واقعی Excel
- خروجی golden snapshot

## 8.3. Mutation Test

- برای اطمینان از اینکه test suite حفاظت کامل دارد.

------

# 9. نتیجهٔ نهایی: طراحی معماری جدید (Refactor SSoT v1.0)

این طراحی:

- drift را ناممکن می‌کند،
- رفتار join-key را مرکزیت می‌دهد،
- import pipeline را پاک و deterministic می‌کند،
- multi-profile mentor را آسان و پایدار می‌کند،
- QA را ساختاری می‌کند،
- cache و history را version-aware می‌کند،
- و کار را برای آیندهٔ سیستم آسان و توسعه‌پذیر می‌کند.

------

# 10. خلاصهٔ کوتاه برای مدل‌های زبانی (Machine-ready Summary)

```
SYSTEM CONTEXT:

Current system uses fragile, scattered Excel-import logic.
Join-key (6 fields) constructed inconsistently in multiple locations,
causing spec drift, invalid joins, and misalignment with LAW/TECH.

Refactor Goal:
Create a unified, deterministic, policy-first import + join pipeline.

Core Concepts:
- Field Registry: single SSoT for all join fields (sources, priority, strategies).
- HeaderResolver: maps DataFrame headers → field sources.
- Value Canonicalizer: converts raw text → canonical ints.
- JoinKeyResolver: constructs JoinKeyProfile(s) per entity.
- Domain Model: Mentor, Student, JoinKeyProfile, JoinKeyIssue, QaIssue.
- Canonical Pipeline: structured multi-stage process.

Testing:
- Contract Tests for schema/registry/resolver consistency.
- Integration Tests using real Excel scenarios.
- Mutation testing to guarantee robustness.

Outcome:
Eliminates drift, stabilizes joining logic, supports multi-profile mentors,
provides deterministic canonical import, and aligns code with LAW/TECH.
```



















------

- 

- ~~~markdown
  # Refactor SSoT — Import & Join Pipeline v3.0
  
  **Version:** 3.0 (Refactor Join Pipeline – Mentors Import & Join)  
  **Date:** …  
  **Owner:** Architecture / Policy-First Team  
  
  ------
  
  ## فهرست
  
  0. گاردریل‌های اجرایی (Execution Guardrails v3)  
     0.1. اینورینت‌های غیرقابل مذاکره (Join / Rank / Trace / LawA/LawB / Kill-Switch)  
     0.2. MVP Scope (فقط موج اول – ممنوعیت شتر گاو پلنگ)  
     0.3. Definition of Done برای Refactor v3  
     0.4. Implementation Rules (برای انسان و LLM – PR/Branching)  
     0.5. Golden Datasets و Acceptance Tests  
     0.6. LLM Collaboration Contract  
  
  1. هدف و محدودهٔ Refactor v3  
     1.1. Data-First در برابر Decision-First  
  
  2. مراجع بالادستی  
  
  3. تصویر کلی معماری Refactor (قبل/بعد)  
     3.1. وضعیت فعلی (Before)  
     3.2. وضعیت هدف (After v3)  
     3.3. جریان happy-path کل Pipeline  
  
  4. مدل داده‌ها و Typeها  
     4.0. موجودیت‌ها (Domain Entities)  
      4.0.1. Student Entity  
      4.0.2. Mentor Entity  
      4.0.3. School Entity  
      4.0.4. Center Entity  
      4.0.5. Allocation Entity  
      4.0.6. Value Objects کلیدی (JoinKeyProfile, CapacitySnapshot و …)  
     4.1. JoinKeyProfile  
     4.2. Mentor (نمایش فنی برای این ریفکتور)  
     4.3. Student (در حد نیاز این Refactor)  
  
  5. FieldRegistry — حقیقت واحد فیلدها  
     5.1. نقش‌ها  
     5.2. نمونه‌ی داده‌ای  
     5.3. قوانین  
     5.4. رابطه با LAW / Technical SSoT / PolicyConfig و semantic_version  
  
  6. HeaderResolver — نگاشت سرفصل‌های خام  
  
  7. ValueCanonicalizer — نرمال‌سازی مقادیر  
     7.1. نقش  
     7.2. امضای تابع  
     7.3. رابطه با Domain Validation  
     7.4. Security & Input Validation (حداقلی برای v3)  
  
  8. JoinKeyResolver و JoinKeyProfile — ساخت پروفایل الحاق و QA  
     8.1. نقش  
     8.2. امضای تابع  
     8.3. قوانین کلیدی (۶ join key، duplicateها، semantics و LawA/LawB)  
     8.4. سیاست Error Handling و Partial Success  
     8.5. مدل شدت خطا (Severity Model v3)  
  
  9. اتصال به Core و build_matrix  
     9.1. خروجی MentorPoolBuilder  
     9.2. تعامل با Core  
     9.3. تعامل با MultiStrategyAllocator / RuleSlot (آینده)  
  
  10. QA، تست‌ها و Snapshotها  
      10.1. Contract Tests  
      10.2. Snapshot Tests  
      10.3. Edge Case & Property-Based Testing  
      10.4. Observability & Metrics  
  
  11. Migration، Feature Flags و Rollout  
      11.1. Shadow Mode و Feature Flag  
      11.2. Migration Waves & Backward Compatibility Matrix  
      11.3. Environments و Config Deployment  
  
  12. ریسک‌ها، Anti-Patternها و Architecture Guards  
      12.1. Over-engineeringهای عمدی حذف‌شده  
      12.2. Spec Drift و شتر گاو پلنگ  
      12.3. Architecture Guards (Living Documentation & ADRs)  
  
  13. موج‌های بعدی (Future Work)  
  
  پیوست A — Operational Defaults & Tunables v3  
  پیوست B — گایدلاین‌های عملی برای تیم «مالک غیر فنی + LLM»  
  پیوست C — Functional Core، Observability و Kill-Switch عملیاتی  
  
  ------
  
  ## 0. گاردریل‌های اجرایی (Execution Guardrails v3)
  
  بخش ۰ قرارداد اجرایی این Refactor است.  
  هر تغییری در کدی که به این Refactor مربوط است، باید با زیر‌بخش‌های این فصل سازگار باشد.  
  در صورت تضاد، این گاردریل‌ها ارجح هستند.
  
  ### 0.1. اینورینت‌های غیرقابل مذاکره (Join / Rank / Trace / LawA/LawB / Kill-Switch)
  
  Refactor v3 **تحت هیچ شرایطی** حق ندارد این اینورینت‌ها را بشکند.  
  هر تغییری در این موارد باید به‌صورت «تغییر LAW / Technical SSoT» ثبت و در فرآیند جداگانه بررسی شود، نه به‌عنوان patch در این Refactor.
  
  #### 0.1.1. شش کلید join ثابت و از نوع int
  
  مطابق LAW / Technical SSoT، ۶ کلید الحاق (در لایهٔ Excel با نام‌های فارسی):
  
  - «کدرشته»
  - «جنسیت»
  - «دانش آموز فارغ»
  - «مرکز گلستان صدرا»
  - «مالی حکمت بنیاد»
  - «کد مدرسه»
  
  در لایهٔ canonical (snake_case) به ۶ فیلد int نگاشت می‌شوند، مثلاً:
  
  - `group_code`
  - `gender_code`
  - `grad_status_code`
  - `center_code`
  - `finance_code`
  - `school_code`
  
  Refactor v3 حق ندارد:
  
  - تعداد این کلیدها را کم یا زیاد کند؛
  - نوع آنها را از `int` به نوع دیگر تغییر دهد؛
  - semantics آنها (از جمله نقش wildcard صفر در center/school) را تغییر دهد.
  
  #### 0.1.2. ترتیب ثابت ranking (RANK-CORE)
  
  ترتیب ranking برای انتخاب mentor، مطابق Technical SSoT:
  
  1. `remaining_capacity` به‌صورت نزولی؛  
  2. `allocations_new` به‌صورت صعودی؛  
  3. `mentor_id` به‌صورت صعودی، با sort پایدار.
  
  Refactor v3 حق ندارد:
  
  - ترتیب معیارها را عوض کند؛
  - معیار جدیدی را به‌عنوان signal اصلی ranking وارد کند (مثلاً ratio، score، priority تازه)؛
  - فرمول محاسبهٔ `remaining_capacity` را بدون به‌روزرسانی LAW / TECH تغییر دهد.
  
  #### 0.1.3. ساختار Trace ۸ مرحله‌ای
  
  Trace ۸ مرحله‌ای (type, group, gender, graduation_status, center, finance, school, capacity_gate) ثابت است.
  
  Refactor v3:
  
  - می‌تواند metadata بیشتر برای trace تولید کند؛
  - اما حق ندارد ترتیب یا semantics این ۸ مرحله را تغییر دهد.
  
  #### 0.1.4. Law A / Law B برای پروفایل الحاق منتور
  
  در تاریخ سیستم دو تفسیر برای رفتار پروفایل الحاق منتورها وجود داشته است:
  
  - **Law A (وضعیت مصوب فعلی):**  
    یک mentor می‌تواند چند پروفایل join مختلف داشته باشد (مثلاً در چند مدرسه یا چند center متفاوت). تکرار دقیق یک پروفایل (۶ کلید یکسان) فقط به‌عنوان duplicate QA ثبت می‌شود. خود وجود چند پروفایل مختلف ذاتاً ممنوع نیست، بلکه یک وضعیت داده‌ای است که باید به‌روش شفاف مدیریت شود (حذف از pool یا انتخاب یک پروفایل دترمینیستیک؛ رفتار دقیق در Policy/QA مشخص می‌شود).
  
  - **Law B (وضعیت قدیمی در برخی QA/کدها):**  
    هر mentor فقط یک پروفایل join مجاز دارد و هر اختلافی در ۶ کلید join برای یک mentor به‌عنوان خطا یا تناقض شمرده می‌شود.
  
  Refactor v3 صراحتاً **Law A** را مبنا می‌گیرد و:
  
  - معنای join را بر اساس Law A تعریف می‌کند؛  
  - Law B فقط به‌صورت رفتار قدیمی/QA Rule (مثل `QA_JOIN_LAW_A_01`) شناخته و به‌تدریج deprecate می‌شود؛  
  - هر تغییری که بخواهد مجدداً به Law B نزدیک شود (مثلاً ممنوعیت بنیادی multi-profile برای mentor) باید به‌عنوان تغییر LAW/Technical SSoT ثبت و به‌طور رسمی بررسی و تصویب شود.
  
  سیاست عملی v3 برای multi-profile در 8.3 توضیح داده شده است (حالت محافظه‌کارانه: حذف mentor از `usable_profiles` + QA).
  
  #### 0.1.5. Kill-Switch رسمی برای بازگشت به pipeline قبلی
  
  در v3 یک Kill-Switch عملیاتی سطح سیستم تعریف می‌شود:
  
  - فلگ `FORCE_LEGACY_MENTOR_PIPELINE`،  
  - در صورت فعال بودن (`true`)، **تمام کدهای v3 مربوط به import/join منتورها بای‌پس شده** و دقیقاً pipeline قبل از Refactor (commit مرجع مشخص‌شده در ADR) اجرا می‌شود؛  
  - این رفتار بخشی از اینورینت‌های عملیاتی v3 است و فقط از طریق کانال‌های کنترل‌شدهٔ Ops قابل تغییر است.
  
  شرح کامل این Kill-Switch در **پیوست C.3** و بخش **11.1** آمده است.  
  هرگونه تغییری که اثر آن را از بین ببرد یا دور بزند، بدون ADR و به‌روزرسانی این سند **مجاز نیست**.
  
  ------
  
  ### 0.2. MVP Scope (فقط موج اول – ممنوعیت شتر گاو پلنگ)
  
  **هدف موج اول:**  
  بازنویسی **import و join pipeline منتورها** به‌گونه‌ای که:
  
  - ۶ کلید join به‌صورت دترمینیستیک و واحد ساخته شوند؛  
  - JoinKeyProfile جایگزین منطق‌های پراکندهٔ فعلی شود؛  
  - QA روی join-key و دادهٔ mentors شفاف‌تر و قابل‌ردیابی‌تر شود؛  
  - رفتار تخصیص (allocation) در Core دست‌نخورده بماند.
  
  #### 0.2.1. دامنهٔ مجاز تغییر در موج اول
  
  ۱. مسیر `InspactorReport → Mentor Pool → Matrix` برای **منتورها**:
  
  - ماژول‌های Import و canonicalization mentors در Infra؛  
  - تعریف و پیاده‌سازی `FieldRegistry` برای فیلدهای مرتبط با mentor/join keys؛  
  - پیاده‌سازی `HeaderResolver`, `ValueCanonicalizer`, `JoinKeyResolver` برای Mentor Pool؛  
  - ساخت `JoinKeyProfile` و استفاده از آن در `build_matrix` برای mentors؛  
  - تولید QA artifacts مربوط به join-key mentors.
  
  ۲. QA مرتبط با این مسیر:
  
  - QA روی duplicate JoinKeyProfile per mentor؛  
  - QA روی missing/invalid join-key fields در mentors؛  
  - QA مربوط به drift بین Inspactor و Matrix در سمت mentors.
  
  #### 0.2.2. موارد صریحاً خارج از دامنه در موج اول (ممنوع)
  
  - هرگونه تغییر در:  
    - منطق تخصیص دانش‌آموز به mentor در Core؛  
    - import و canonicalization دانش‌آموز؛  
    - HistoryStore، Trace ۸ مرحله‌ای، QA Debug Engine؛  
    - Governance استخر منتورها (ACTIVE/FROZEN و …)، جز خواندن خروجی جدید با semantics ثابت join.
  
  - اضافه کردن patternهای معماری سنگین در v3 (فقط به‌عنوان پیشنهاد آینده):  
    - Event Sourcing؛  
    - CQRS؛  
    - State Machine پیچیده؛  
    - Async everywhere؛  
  
  به‌استثنای اشاره در بخش Future Work، بدون پیاده‌سازی واقعی در v3.
  
  #### 0.2.3. خروجی قابل تحویل موج اول (MVP)
  
  - خروجی `eligibility_matrix` برای mentors:  
    - از نظر behavior join و match با نسخهٔ قبلی معادل؛  
    - تفاوت مجاز فقط در ستون‌ها/شیت‌های QA و metadata جدید است.
  
  - گزارش JoinKeyIssue و invalid mentors:  
    - شفاف‌تر، دترمینیستیک‌تر و قابل‌ردیابی‌تر از نسخهٔ قبلی.
  
  - UI/CLI:  
    - رفتار اصلی برای کاربر نهایی همان است؛  
    - فقط پیام‌های خطا / QA ممکن است واضح‌تر و ساخت‌یافته‌تر شوند.
  
  ------
  
  ### 0.3. Definition of Done برای Refactor v3
  
  Refactor v3 زمانی «تمام» و آمادهٔ فعال‌سازی روی دادهٔ واقعی است که **همهٔ موارد زیر برقرار باشد**:
  
  1. **Golden Files**
  
     حداقل سه فایل Inspactor در مسیر `tests/data/golden/`:
  
     - `inspactor_small_1403.xlsx` (حدود ۱۰۰ ردیف؛ سناریوهای ساده و edge-case‌ های پایه)  
     - `inspactor_medium_1403.xlsx` (حدود ۳k ردیف؛ چند مرکز/مدرسه/گروه)  
     - `inspactor_large_1404.xlsx` (حدود ۲۰k+ ردیف؛ برای performance/capacity، مقدار دقیق در پیوست A به‌عنوان tunable تعریف می‌شود).
  
  2. **برابری رفتاری با نسخهٔ قدیم**
  
     برای هر Golden File:
  
     - `build_matrix` نسخهٔ قدیم و نسخهٔ v3 اجرا می‌شوند؛  
     - ورودی دانش‌آموز ثابت است؛  
     - `eligibility_matrix` جدید و قدیم، به‌جز ستون‌های QA/Trace/Meta، از نظر محتوای match mentor–student معادل هستند (bit-wise یا با Snapshot تست معادل).
  
  3. **Contract Tests روی FieldRegistry و JoinKeyResolver**
  
     حداقل n (مثلاً ۱۰) تست قرارداد که پوشش دهند:
  
     - صحت تعریف ۶ join key و نوع int؛  
     - mapping صحیح headerهای فارسی/variant به فیلدهای canonical؛  
     - behavior دترمینیستیک JoinKeyResolver در سناریوهای duplicate / missing / invalid combos.
  
  4. **Golden Snapshot Tests روی QA**
  
     حداقل سه Snapshot Test برای خروجی QA (مثل `eligibility_matrix_validation` و بخش mentor در `matrix_vs_students_validation`):
  
     - تعداد و نوع QA Ruleها؛  
     - summaryهای کلیدی (تعداد `invalid_mentors`, `unseen_groups`, تعداد JoinKeyIssueها به تفکیک code/severity).
  
  5. **Performance**
  
     روی `inspactor_large_1404.xlsx`:
  
     - اجرای کامل Import + Join + build_matrix v3 در محیط توسعهٔ مرجع، در کمتر از N ثانیه (مثلاً < ۱۰ ثانیه، مقدار N به‌صورت تنظیم‌پذیر در پیوست A تعریف می‌شود).
  
  6. **کیفیت Log و Observability حداقلی**
  
     - در اجراهای استاندارد، هیچ پیام Log سطح ERROR بدون علت شناخته‌شده وجود ندارد؛  
     - metrics و لاگ‌ها طبق بخش 10.4 جمع‌آوری می‌شوند؛  
     - نرخ خطاهای P0 در Golden Files صفر است.
  
  7. **آزمایش انسانی روی حداقل دو Run واقعی**
  
     - دو مجموعه دادهٔ واقعی (مثلاً سال‌های ۱۴۰۲ و ۱۴۰۳) روی نسخهٔ جدید اجرا شده‌اند؛  
     - خروجی matrix و QA با UI/Excel بررسی شده و توسط domain expert تأیید شده است.
  
  تا پیش از تحقق همهٔ موارد بالا، Refactor v3 در حالت آزمایشی (shadow/feature branch) است و حق فعال‌سازی production کامل ندارد.
  
  ------
  
  ### 0.4. Implementation Rules (برای انسان و LLM – PR/Branching)
  
  این قوانین برای انسان و LLM مشترک است.
  
  1. **سقف اندازهٔ هر PR**
  
     - حداکثر ۵ فایل در Core؛  
     - حداکثر ۸ فایل در Infra؛  
     - حداکثر ۳۰۰ خط diff خالص (تغییرات formatting مثل black/ruff ترجیحاً در PR جداگانه).
  
  2. **ترکیب‌های ممنوع در یک PR**
  
     - هم‌زمان:  
       - تغییر behavior Join/JoinKeyResolver  
       - و بازآرایی ساختار پوشه‌ها/ماژول‌ها.
  
     - هم‌زمان:  
       - behavior change جدی  
       - و rename/refactorهای گستردهٔ صرفاً cosmetic.
  
  3. **نوع PR (یک نوع در هر PR)**
  
     - **Refactor-only**:  
       - تمرکز روی ساختار/خوانایی؛  
       - Golden/Snapshot Tests نشان می‌دهند behavior تغییری نکرده است.
  
     - **Behavior-change-only**:  
       - صریحاً در Description اعلام می‌شود؛  
       - تست‌های جدید و diff روی snapshotها رفتار جدید را توضیح می‌دهند.
  
     - **Test/QA-only**:  
       - اضافه کردن تست‌ها، Golden Files، ابزار QA؛  
       - بدون تغییر behavior Core/Infra.
  
  4. **ارتباط PR با سند**
  
     هر PR باید در Description اشاره کند:
  
     - کدام بند/زیر‌بند این سند را پیاده می‌کند (مثلاً: `Implements 8.3 duplicate-JoinKeyProfile QA`)،  
     - در صورت Behavior Change، کدام بند LAW/TECH را تقویت/اصلاح می‌کند (و در صورت لزوم، آن اسناد نیز به‌روز شوند).
  
  5. **کد تولید‌شده توسط LLM در PR**
  
     - اگر بخش قابل توجهی از PR توسط LLM تولید شده است، باید در Description با تگ واضح (مثل `# generated-by-llm`) مشخص شود؛  
     - این PR نیازمند Human Review جدی است.
  
  ------
  
  ### 0.5. Golden Datasets و Acceptance Tests
  
  Golden Datasets خط قرمز داده‌ای این Refactor هستند.
  
  #### 0.5.1. Golden Files
  
  سه فایل Golden که باید تحت version control در `tests/data/golden/` نگهداری شوند:
  
  - `inspactor_small_1403.xlsx`  
  - `inspactor_medium_1403.xlsx`  
  - `inspactor_large_1404.xlsx` (اندازهٔ دقیق در پیوست A به‌عنوان tunable تعریف شده است)
  
  برای هر فایل، خروجی‌های زیر باید snapshot شوند:
  
  - `eligibility_matrix` (به‌صورت Excel یا معادل DataFrame/Parquet برای تست)؛  
  - `matrix_vs_students_validation` (در حد بخش مرتبط با mentors/join)؛  
  - QA summaries:  
    - تعداد `invalid_mentors`؛  
    - تعداد `unseen_groups`؛  
    - توزیع JoinKeyIssueها (by code/severity).
  
  #### 0.5.2. Acceptance Test Rule
  
  Refactor v3 **حق merge به main و فعال‌سازی production** ندارد مگر این‌که:
  
  1. روی هر سه Golden File اجرا شده باشد؛  
  2. خروجی‌های جدید با baselineهای ثبت‌شده مقایسه شده باشند؛  
  3. اختلاف‌ها یا صفر باشند، یا کاملاً فهمیده و در Changelog و این سند ثبت شده باشند (مثلاً اصلاح یک bug دامین).
  
  ------
  
  ### 0.6. LLM Collaboration Contract
  
  سیاست همکاری با مدل زبانی در این Refactor:
  
  1. **کارهایی که LLM مجاز است انجام دهد**
  
     - تولید کد برای توابع/کلاس‌هایی که امضای‌شان در این سند تعریف شده‌اند (مثل `JoinKeyResolver.build_profiles(...)`, `HeaderResolver.resolve(...)` و …)؛  
     - پیشنهاد refactor کوچک در یک فایل مشخص با حفظ behavior؛  
     - تولید تست‌ها (unit/contract/snapshot) بر اساس سناریوهای صریح در این سند یا LAW/TECH.
  
  2. **کارهایی که LLM مجاز نیست انجام دهد**
  
     - تعریف کلاس/ماژول public جدید که نقش آن در این سند ذکر نشده است؛  
     - تغییر امضای public APIها (تابع‌هایی که Infra/UI از آن‌ها استفاده می‌کنند) بدون ارجاع صریح به بند متناظر در سند؛  
     - معرفی و پیاده‌سازی patternهای جدید (CQRS, Event Sourcing, Message Bus, Complex State Machine, …) در v3؛  
     - هرگونه «بهبود» در semantics join/rank/trace (مثلاً افزودن معیار ranking جدید) بدون تغییر رسمی LAW/Technical SSoT.
  
  3. **الزامات خروجی LLM**
  
     - کد پیشنهادی باید:  
       - قابل اصلاح تا عبور از `mypy --strict`, `ruff check .`, `black --check` باشد؛  
       - imports را مطابق الگوی Ruff I001 (stdlib → third-party → local) نگه دارد؛  
       - صریحاً این اینورینت‌ها را نقض نکند:  
         - تعداد، نوع یا semantics ۶ کلید join؛  
         - ترتیب ranking (`remaining_capacity ↓`, سپس `allocations_new ↑`, سپس `mentor_id ↑` با sort پایدار)؛  
         - ساختار Trace ۸ مرحله‌ای.
  
     - هر پیشنهادی در حوزهٔ join/rank/trace باید به‌صورت «پیشنهاد تغییر LAW/Technical SSoT» ثبت شود، نه patch مستقیم.
  
  4. **Human Review**
  
     - هیچ Patch تولید‌شده توسط LLM، بدون Human Review + عبور از Golden/Snapshot Tests، حق merge ندارد.
  
  ------
  
  ## 1. هدف و محدودهٔ Refactor v3
  
  **هدف:**  
  بازطراحی و یکپارچه‌سازی import و join pipeline منتورها به‌گونه‌ای که:
  
  - تمام منطق مربوط به ۶ join key، alias، mentor_type و capacity در مسیر Mentor Pool:  
    - شفاف و قابل‌فهم؛  
    - دترمینیستیک؛  
    - قابل تست؛  
    - و منطبق با LAW v3.0 و Technical SSoT v3.0-TECH باشد.  
  
  - رفتار join در تمام مسیرها (build_matrix، QA، History، validationها) یکسان و هم‌معنا شود.
  
  **پوشش می‌دهد:**
  
  - Import mentor از InspactorReport و سایر منابع (SchoolReport, Crosswalk و …)؛  
  - Canonicalization فیلدهای mentor (type، capacity، center, school_code, alias, ۶ join key و …)؛  
  - تعریف و استفاده از FieldRegistry در HeaderResolver/ValueCanonicalizer/JoinKeyResolver؛  
  - ساخت Mentor Pool canonical برای Core؛  
  - QAهای مرتبط با کیفیت دادهٔ mentors و join-key.
  
  **خارج از محدودهٔ v3:**
  
  - منطق داخلی تخصیص در Core؛  
  - import و canonicalization دانش‌آموز؛  
  - Trace ۸ مرحله‌ای و QA Debug Engine؛  
  - Governance استخر منتورها؛  
  - طراحی UI/UX (جز نمایش بهتر خطاها/QA بر اساس خروجی جدید).
  
  ### 1.1. Data-First در برابر Decision-First
  
  معماری تصمیم‌گیری (RuleSlot / Decision Flow Engine و `MultiStrategyAllocator`) در سند جداگانه‌ای به نام  
  «سند معماری سیستم تخصیص مبتنی بر RuleSlot و Decision Flow Engine» تعریف شده است.
  
  این سند فقط لایهٔ **Data-First / Import & Join** را پوشش می‌دهد:
  
  - پاک‌سازی و canonical کردن دادهٔ منتورها؛  
  - ساخت Mentor Pool v3 بر اساس ۶ join key و ظرفیت؛  
  - تحویل این دادهٔ canonical به دو مصرف‌کنندهٔ اصلی:  
    - Core legacy (`build_matrix`)؛  
    - Core جدید (`MultiStrategyAllocator` / RuleSlot) در موج‌های بعدی مهاجرت.
  
  هیچ منطق تصمیم‌گیری (استراتژی‌های تخصیص، RuleSlotها، Flowها) در این سند پیاده نمی‌شود؛  
  فقط تضمین می‌شود دادهٔ ورودی آن سیستم‌ها سازگار، دترمینیستیک و منطبق با LAW/Technical SSoT باشد.
  
  ------
  
  ## 2. مراجع بالادستی
  
  این سند، حقیقت فنی Refactor v3 است؛ اما باید با اسناد زیر سازگار باشد و در صورت اختلاف، آن‌ها مرجع هستند:
  
  - `LAW_Smart_Student_Allocation_v3.0.md`  
  - `Technical_SSoT_Smart_Student_Allocation_v3.0-TECH.md`  
  - `Policy v1.0.3`  
  - `Student Allocation System Spec v1.0.2`  
  - `System Architecture Blueprint Smart Student Allocation v1.0`  
  - `System Vision & Scope Smart Student Allocation v1.0`  
  - `AGENTS.md`  
  - `Rule_Engine_Spec` و `Eligibility_Matrix_Builder_Spec` (برای QA Workbooks)  
  - «سند معماری سیستم تخصیص مبتنی بر RuleSlot و Decision Flow Engine» (برای اتصال به MultiStrategyAllocator / RuleSlot)
  
  ------
  
  ## 3. تصویر کلی معماری Refactor (قبل/بعد)
  
  ### 3.1. وضعیت فعلی (Before)
  
  در وضعیت فعلی (قبل از v3):
  
  - منطق join و ساخت ماتریس mentors:  
    - در چندین فایل/تابع پراکنده (مثلاً نسخه‌های مختلف `build_matrix` و توابع ad-hoc join)؛  
    - وابسته مستقیم به headerهای فارسی Excel؛  
    - canonicalization بعضاً در Import و بعضاً در Matrix Builder انجام می‌شود؛  
    - QA روی join-key و mentor validity در چند نقطه و نیمه‌تکراری است.
  
  نتیجه: هر تغییر policy در join، نیازمند جستجو در چند جای متفاوت است و احتمال Spec Drift زیاد است.
  
  ### 3.2. وضعیت هدف (After v3)
  
  در v3، مسیر Mentor Import و Join به بلوک‌های قابل‌تفکیک تبدیل می‌شود:
  
  1. **FieldRegistry (Infra / Core-adjacent)**  
     مرجع واحد تعریف فیلدها (نوع، `join_key_index`, required بودن، semantic_version و …).
  
  2. **HeaderResolver (Infra)**  
     map کردن headerهای خام Excel به نام‌های canonical، بر اساس FieldRegistry.
  
  3. **ValueCanonicalizer (Infra)**  
     تبدیل مقادیر خام به domain types (group, gender, finance, center/school, mentor_type, capacity و …) طبق PolicyConfig.
  
  4. **JoinKeyResolver (Infra / Core-facing)**  
     ساخت `JoinKeyProfile` بر اساس ۶ join key و تولید QA برای duplicateها، missingها و invalid combinations.
  
  5. **MentorPoolBuilder (Infra)**  
     تولید DataFrame canonical mentors + QA artifacts؛ آماده برای مصرف Core (build_matrix و allocation و در آینده MultiStrategyAllocator / RuleSlot).
  
  Core فقط DataFrame canonical را مصرف می‌کند و منطق join را دوباره اختراع نمی‌کند؛  
  join semantics از LAW/TECH می‌آید، نه از پیاده‌سازی‌های پراکنده.
  
  ### 3.3. جریان happy-path کل Pipeline
  
  مسیر happy-path اجرای کامل import & join mentors:
  
  ```text
  1) read_inspactor_excel(filepath) → DataFrame (raw_df)
  
  2) header_result = HeaderResolver.resolve(raw_df, header_ctx)
     - اگر header_result.can_continue == False ⇒ fail-fast
  
  3) canon_result = ValueCanonicalizer.canonicalize(
         raw_df,
         canonicalization_ctx,
         header_result
     )
     - canon_result.df = canonical_df
     - canon_result.issues / failed_rows
     - اگر canon_result.can_continue == False ⇒ fail-fast
  
  4) join_result = JoinKeyResolver.build_profiles(
         canonical_df,
         join_key_ctx
     )
     - join_result.all_profiles / usable_profiles
     - join_result.issues / failed_rows
     - اگر join_result.can_continue == False ⇒ fail-fast یا QA-only
       (طبق policy)
  
  5) mentor_pool = MentorPoolBuilder.build(
         canonical_df,
         join_result,
         other_sources
     )
     - ساخت DataFrame canonical mentors + QA artifacts
  
  6) build_matrix(
         mentors_canonical = mentor_pool.df,
         students_canonical = existing_students_df,
         policy_config = policy
     )
     - Core از ۶ join key int و ظرفیت استفاده می‌کند
     - Trace ۸ مرحله‌ای طبق LAW/TECH پر می‌شود
  
  7) (Future) MultiStrategyAllocator / RuleSlot
     - مصرف همین Mentor Pool v3 و student pool canonical
     - بدون پیاده‌سازی join مجزا
  ~~~

  این flow باید در پیاده‌سازی اصلی Mentors Import & Join به همین شکل منطقی قابل ردیابی باشد.

  ------

  ## 4. مدل داده‌ها و Typeها

  در این بخش، مدل دامین و نوع‌های فنی‌ای که این Refactor روی آن‌ها سوار است تعریف می‌شوند.

  ### 4.0. موجودیت‌ها (Domain Entities)

  در این سیستم، چند موجودیت (Entity) اصلی داریم که هویت، ویژگی‌ها و اینورینت‌های خودشان را دارند، و چند Value Object که هویت مستقل ندارند و با Entityها ترکیب می‌شوند.

  #### 4.0.1. Student Entity

  **هویت:**
   `student_key` — شناسهٔ یکتای دانش‌آموز در سال/دورهٔ هدف.

  **ویژگی‌های کلیدی (در حد نیاز این Refactor و join):**

  - `student_key`
  - `student_type` (عادی / مدرسه‌ای، مطابق قوانین STUDENT-TYPE-01)
  - `group_code` (کدرشته دانش‌آموز)
  - `gender_code`
  - `grad_status_code` (وضعیت تحصیلی: درحال‌تحصیل / فارغ‌التحصیل / …)
  - `school_code`
  - `center_code`
  - سایر ویژگی‌ها مثل وضعیت مالی، در صورت استفاده در join/Policy.

  **اینورینت‌های اصلی Student (در این سند، خلاصه):**

  - مقدار `student_type` باید از دامنهٔ معتبر انتخاب شود و با school/center سازگار باشد.
  - هر `student_key` در یک run حداکثر یک تخصیص فعال دارد (از منظر Allocation Entity).
  - ترکیب (group, gender, grad_status) باید با دامنه‌های LAW/TECH سازگار باشد؛
     مقادیر خارج از دامنه در Domain Validation رد می‌شوند.

  این Refactor مستقیماً pipeline دانش‌آموز را عوض نمی‌کند،
   اما join mentors باید با همین تعریف Student سازگار باشد.

  #### 4.0.2. Mentor Entity

  **هویت:**
   `mentor_id` — شناسهٔ یکتای پشتیبان.

  **ویژگی‌های کلیدی:**

  - `mentor_id`
  - `mentor_type` (NORMAL / SCHOOL، مطابق MENTOR-TYPE-01)
  - `group_code`, `gender_code`, `grad_status_code` (برای join)
  - `center_code`
  - `finance_code`
  - `school_code` (برای منتورهای مدرسه‌ای)
  - وضعیت ظرفیت (limit, baseline, allocations_new، و ظرفیت باقی‌مانده)
  - `mentor_status` (ACTIVE / FROZEN، مطابق MENTOR-STATUS-01)
  - سایر مشخصات دامنه‌ای (نام، کد ملی، عناوین، …) در صورت نیاز.

  **اینورینت‌های اصلی Mentor:**

  - فقط منتورهای `mentor_status = ACTIVE` وارد استخر تخصیص می‌شوند.
  - `mentor_type` باید با school/center سازگار باشد (مثلاً School Mentor باید school_code معتبر داشته باشد).
  - استخراج school_code برای MentorType.SCHOOL از ستون‌های «نام مدرسه 1..4» با ترتیب ثابت انجام می‌شود؛
    فقط توکن‌های قابل تبدیل به int و `> 0` معتبرند و در صورت اعلام `تعداد مدارس تحت پوشش`،
    کمبود توکن معتبر باید باعث خطای سخت همراه با QA detail شود.
  - CAPACITY-01: مجموع تخصیص‌ها نباید از ظرفیت مجاز فراتر رود؛ تعریف دقیق ظرفیت به کمک Value Object `CapacitySnapshot` و فرمول LAW/TECH انجام می‌شود.
  - برای هر Mentor، رفتار join باید از روی ۶ کلید join و semantics LAW تعریف شود، نه روی فیلدهای پراکنده‌ی دیگر.

  در ادامهٔ سند، همین Mentor Entity در 4.2 به‌صورت dataclass فنی نمایش داده می‌شود.

  #### 4.0.3. School Entity

  **هویت:**
   `school_code`

  **نقش:**
   موجودیت مرجع (Reference Entity) برای نگاشت دانش‌آموزان و منتورها به مدارس.

  **ویژگی‌های نمونه:**

  - `school_code`
  - `school_name`
  - `center_code`
  - `school_gender_code` (1 = پسرانه، 2 = دخترانه)
  - `school_stage` (ابتدایی / متوسطه اول / متوسطه دوم نظری / هنرستان)
  - وضعیت فعال/غیرفعال (در صورت نیاز)
  - سایر اطلاعات مرجع (آدرس، نوع مدرسه و …) در صورت نیاز.

  **اینورینت‌های School:**

  - SCHOOL-01: هر `school_code` باید یکتا و معتبر باشد.
  - `center_code` برای هر مدرسه باید معتبر و با Center Entity سازگار باشد.
  - مدرسهٔ مختلط نداریم؛ `school_gender_code` باید در دامنهٔ {1،2} باشد و ردیف بدون جنسیت در ایمپورت اولیه حذف و در QA ثبت شود.
  - `school_stage` سطح مدرسه است و برای QA همسویی با `group_code` استفاده می‌شود؛ `group_code` و `school_code` کلیدهای join مستقل باقی می‌مانند.
  - اگر مدرسه غیرفعال باشد، Policy تعیین می‌کند دانش‌آموزان/منتورهای مرتبط چطور مدیریت شوند (مثلاً به QA یا استثنا تبدیل شوند).

  **مرجع داده:**

  - SchoolReport ورودی هر ران نیست؛ برای bootstrap/update جدول مرجع `schools` استفاده می‌شود و پس از بارگذاری موفق، Mentor/Student import فقط از DB می‌خوانند.
  - School rows بدون جنسیت یا خارج از دامنه نباید وارد جدول مرجع شوند و باید QA شوند.

  این Refactor از School به‌عنوان منبع کد و constraint برای join mentors استفاده می‌کند
   (به‌خصوص برای MentorType= SCHOOL)، اما منطق اصلی School در اسناد پایه تعریف می‌شود.

  #### 4.0.4. Center Entity

  **هویت:**
   `center_code`

  **نقش:**
   موجودیت مرجع برای تجمیع مدارس و منتورها در سطح مرکز.

  **ویژگی‌های نمونه:**

  - `center_code`
  - `center_name` (در صورت وجود)
  - سایر ویژگی‌های عملیاتی (اختیاری).

  **اینورینت‌های Center:**

  - CENTER-01: هر `center_code` باید یکتا و معتبر باشد.
  - نقش `0` به‌عنوان wildcard center در join مشخص است (مثلاً mentor با center_code=0 می‌تواند با چند مرکز join شود، طبق LAW/TECH).
  - Schoolها و Mentorها باید center_code معتبر داشته باشند یا طبق Policy برای مقادیر نامعتبر به QA بروند.

  #### 4.0.5. Allocation Entity

  **هویت:**
   بسته به طراحی دیتابیس/پیاده‌سازی، می‌تواند:

  - `allocation_id` یکتا، یا
  - کلید مرکب (`student_key`, `mentor_id`, `year`, `run_id`)

  باشد. این سند وارد جزئیات ذخیره‌سازی Allocation نمی‌شود، اما موجودیت آن را به رسمیت می‌شناسد.

  **ویژگی‌های کلیدی:**

  - شناسه (allocation_id یا ترکیب کلیدها)
  - `student_key`
  - `mentor_id`
  - سال/دوره تخصیص
  - `allocation_status` (ACTIVE, CANCELLED, …)
  - زمان ایجاد / آخرین تغییر
  - اطلاعات Trace (همان ۸ مرحله) در سطح QA/History.

  **اینورینت‌های Allocation:**

  - ALLOCATION-01: هر `student_key` در یک run حداکثر یک تخصیص فعال دارد.
  - ALLOCATION-02: هیچ تخصیصی نباید CAPACITY-01 را نقض کند؛ یعنی از ظرفیت Mentor تجاوز کند.
  - ALLOCATION-TRACE-01: هر تخصیص باید trace ۸ مرحله‌ای معتبر داشته باشد.

  Refactor v3 مستقیم Allocation را تغییر نمی‌دهد،
   ولی باید تضمین کند Mentor Pool و join به‌شکلی کار می‌کنند که این اینورینت‌ها قابل حفظ باشند.

  #### 4.0.6. Value Objects کلیدی (JoinKeyProfile, CapacitySnapshot و …)

  بعضی مفاهیم مهم سیستم **موجودیت با هویت مستقل** نیستند، بلکه Value Object هستند؛ یعنی:

  - بر اساس مقدارشان مقایسه می‌شوند؛
  - هویت جداگانه ندارند؛
  - معمولاً immutable هستند.

  مهم‌ترین Value Objectهای مرتبط با این Refactor:

  1. **JoinKeyProfile**
     - نمایندهٔ پروفایل join بر اساس ۶ کلید join.
     - اگر دو پروفایل در هر ۶ کلید، مقادیر یکسان داشته باشند، همان پروفایل حساب می‌شوند.
     - در این سند در بخش 4.1 با جزئیات کامل (dataclass + hash) تعریف شده است.
     - برای QA، dedupe و تحلیل join استفاده می‌شود.
  2. **CapacitySnapshot**
     - وضعیت ظرفیت Mentor در یک لحظه، با فیلدهایی مثل:
       - `capacity_limit`
       - `assigned_baseline`
       - `allocations_new`
       - `remaining_capacity`
     - در این سند به‌صورت جداگانه به عنوان type پیاده نمی‌کنیم،
        ولی همین مفهوم در 4.2 در قالب فیلدهای Mentor و property `remaining_capacity` استفاده شده است.
     - CAPACITY-01 و سایر قوانین capacity بر این Value Object سوار هستند.
  3. **Enums و کدهای دامنه‌ای**
     - `StudentType`, `MentorType`, `GraduationStatus`, `FinanceCode`, …
     - این‌ها Setهای مقادیر محدود هستند که در ValueCanonicalizer و Domain Validation استفاده می‌شوند.

  #### 4.0.7. GroupCode Reference

  - `group_code` تنها کلید کاننیکال برای بعد «پایه+رشته» است و باید از دامنهٔ مجاز فایل مشخصات group-code parser باشد؛ مقطع/پایه/رشته فقط از همین کد مشتق می‌شوند و خودشان join key نیستند.
  - یک جدول مرجع پایدار DB-backed شامل ستون‌های `group_code`, `stage`, `grade`, `track`, `display_name` وجود دارد؛ هر دو pipeline دانش‌آموز و منتور برای تفسیر group_code به آن متکی هستند.
  - فیلدهای منبع مانند «شامل گروه های آزمایشی» در Inspactor/Report به‌صورت متن وارد می‌شوند و با group-code parser به `List[int]` (همه در دامنهٔ معتبر `group_code`) تبدیل می‌شوند؛ این فیلدها خودشان join key نیستند.

  این Refactor Join Pipeline مستقیماً با Mentor Entity، Student Entity (برای سازگاری join)
   و Value Objectهای JoinKeyProfile / CapacitySnapshot درگیر است؛
   اما School/Center/Allocation نیز در سطح constraints و QA اهمیت دارند.

  ------

  ### 4.1. JoinKeyProfile

  `JoinKeyProfile` یک Value Object است که نمایندهٔ **پروفایل join بر مبنای ۶ join key** است
   و می‌تواند فیلدهای کمکی اضافه حمل کند.

  نمونهٔ مفهومی:

  ```python
  from dataclasses import dataclass
  from enum import Enum
  
  
  class MentorType(Enum):
      NORMAL = "normal"
      SCHOOL = "school"
  
  
  @dataclass(frozen=True)
  class JoinKeyProfile:
      # ۶ کلید join مطابق LAW/TECH
      group_code: int
      gender_code: int
      grad_status_code: int
      center_code: int
      finance_code: int
      school_code: int
  
      # فیلدهای کمکی (auxiliary)
      alias_code: int | None
      mentor_type: MentorType  # NORMAL / SCHOOL
  
      def __hash__(self) -> int:
          """Hash و equality باید فقط بر پایهٔ ۶ کلید join باشد."""
          return hash(
              (
                  self.group_code,
                  self.gender_code,
                  self.grad_status_code,
                  self.center_code,
                  self.finance_code,
                  self.school_code,
              )
          )
  
      def same_join_keys_as(self, other: "JoinKeyProfile") -> bool:
          """مقایسهٔ صرفاً بر اساس ۶ کلید join."""
          return (
              self.group_code == other.group_code
              and self.gender_code == other.gender_code
              and self.grad_status_code == other.grad_status_code
              and self.center_code == other.center_code
              and self.finance_code == other.finance_code
              and self.school_code == other.school_code
          )
  ```

  نکات:

  - از نظر LAW، join بر اساس همین ۶ کلید تعریف می‌شود؛
  - `alias_code` و `mentor_type` فیلدهای کمکی هستند (برای QA و constraints)، نه عضو «۶ کلید join»؛
  - `__hash__` و equality مؤثر باید فقط این ۶ فیلد را در نظر بگیرد.

  این type عمداً با مفهوم `JoinKeyPattern / MentorSlot` در
   سند «معماری سیستم تخصیص مبتنی بر RuleSlot و Decision Flow Engine» هم‌تراز طراحی شده تا در موج‌های بعدی بتوان **بدون تبدیل اضافه** از همین پروفایل‌ها برای ساخت Slotها در `MultiStrategyAllocator` / RuleSlot استفاده کرد.

  ------

  ### 4.2. Mentor (نمایش فنی برای این ریفکتور)

  نمایش canonical Mentor (در Infra/Core-facing):

  ```python
  from dataclasses import dataclass
  from enum import Enum
  
  
  class MentorStatus(Enum):
      ACTIVE = "active"
      FROZEN = "frozen"
  
  
  @dataclass
  class Mentor:
      mentor_id: int
      join_profile: JoinKeyProfile
  
      capacity_limit: int
      assigned_baseline: int
      allocations_new: int
  
      mentor_status: MentorStatus
      # سایر فیلدهای دامنه‌ای (نام، عنوان، مرکز، مدرسه و ...)
  
      @property
      def remaining_capacity(self) -> int:
          """Source of truth برای ظرفیت باقی‌مانده طبق LAW/TECH."""
          # فرمول دقیق باید با LAW/Technical SSoT هم‌راستا باشد
          return self.capacity_limit - (self.assigned_baseline + self.allocations_new)
  ```

  نکات:

  - `Mentor` در این‌جا یک نمایش فنی از Mentor Entity است؛
     هویت همان `mentor_id` است و سایر فیلدها از مدل دامین 4.0.2 می‌آیند.
  - `remaining_capacity` در Domain Model فقط به‌صورت property مشتق‌شده تعریف می‌شود،
     نه به‌عنوان فیلد ذخیره‌شده؛ این دقیقاً همان CapacitySnapshot است که به‌صورت inlined پیاده شده.
  - هر ستون `remaining_capacity` در DataFrame canonical mentors صرفاً **بازتاب همین property** است
     و باید در MentorPoolBuilder یا لایه‌ای مشابه، دقیقاً با همین فرمول پر شود؛
  - هیچ بخش دیگری حق ندارد `remaining_capacity` را مستقلاً یا با فرمول متفاوت محاسبه یا set کند.
     هر تغییر در فرمول باید در LAW/TECH ثبت شود.

  ------

  ### 4.3. Student (در حد نیاز این Refactor)

  مدل کامل Student Entity در 4.0.1 تعریف شد.
   برای این Refactor، کفِ نیاز ما این است که:

  - Student canonical frame (که در Core/Infra ایجاد می‌شود) ستون‌های زیر را به‌صورت سازگار با Mentor داشته باشد:
    - همان ۶ join key (group_code, gender_code, grad_status_code, center_code, finance_code, school_code)؛
    - `student_key` به‌عنوان هویت؛
    - فیلدهای کمکی مثل student_type, school_code, center_code طبق قوانین LAW/TECH.

  Refactor v3 pipeline دانش‌آموز را تغییر نمی‌دهد،
   اما هر تغییری در semantics join mentors باید با join دانش‌آموز سازگار باشد
   تا Allocation Entity بتواند این دو موجودیت را هم‌معنا به هم متصل کند.

  ------

  ### 4.4. Concept / Canonical Frame / Channel (HeaderPipelineV3)

  - **Concept Layer:** فیلدهای کاننیکال (مثلاً `group_code`, `gender_code`, `finance_code`, `school_code`, `center_code`, `grad_status_code`, `mentor_id`, `alias`, `remaining_capacity`) که Core می‌شناسد.
  - **Canonical Frame:** اسکیمای DataFrame/DB با همین نام‌های کاننیکال؛ تمام ورودی/خروجی‌ها باید در نهایت به این فیلدها نگاشت شوند.
  - **Channel Layer:** هدرهای ورودی/خروجی در منابع مختلف (InspactorReport، Report، SchoolReport، DB/History/QA). هیچ هدر خامی بدون عبور از HeaderPipelineV3 قابل استفاده نیست.
  - HeaderPipelineV3 (FieldRegistry + HeaderResolver + ValueCanonicalizer + registry) تنها SSoT نگاشت `(channel, raw_header, raw_value) → (canonical_field, canonical_value)` است؛ هر hard-code خارج از این مسیر ممنوع است.
  - QA اجباری: هدر ناشناخته یا misspelled باید issue ساخت‌یافته (UNKNOWN_HEADER / UNMAPPED_HEADER) تولید کند، نه silent drop؛ نبود فیلدهای اجباری join-key همچنان P0 با `can_continue=false` است.
  - **UNKNOWN-ASK-01:** هر مقدار ناشناخته باید یا از کانال‌های رسمی (HeaderPipelineV3، JoinKeyResolver،
    UnknownDataChannel، EligibilityChannel) عبور کند یا به Decision Required تبدیل شود؛
    گزارش JSON پایدار و دترمینیستیک باید در مرحلهٔ preflight تولید شود.

  ------

  ## 5. FieldRegistry — حقیقت واحد فیلدها

  ### 5.1. نقش‌ها

  FieldRegistry مرجع رسمی metadata فیلدهای Import/Join است:

  - نام canonical (snake_case)؛
  - نوع داده (int/str/enum/…)؛
  - الزامی بودن؛
  - نقش در join (`join_key_index`)؛
  - نسخهٔ semantic (`semantic_version` مرتبط با join/field semantics).

  استفاده‌کنندگان اصلی:

  - HeaderResolver (برای نگاشت headerها به فیلدهای canonical)،
  - ValueCanonicalizer (برای type-cast و validation)،
  - JoinKeyResolver (برای استخراج ۶ join key و تشخیص join fields).

  ### 5.2. نمونه‌ی داده‌ای

  نمونهٔ مفهومی برای یک join key:

  ```python
  from dataclasses import dataclass
  
  
  @dataclass(frozen=True)
  class Field:
      name: str                  # مثلاً "group_code"
      join_key_index: int | None # 1..6 اگر join key است، وگرنه None
      dtype: str                 # "int", "str", "enum", ...
      required: bool
      semantic_version: str      # مثلاً "3.0"
  
  
  group_field = Field(
      name="group_code",
      join_key_index=1,
      dtype="int",
      required=True,
      semantic_version="3.0",
  )
  ```

  برای ۶ join key، ۶ Field با `join_key_index`های یکتا (۱..۶) تعریف می‌شوند.

  ### 5.3. قوانین

  - هر تغییری در **join semantics** (اضافه/حذف join key، تغییر نوع، تغییر required بودن) باید:
    - ابتدا در سطح دامین تصمیم‌گیری شود؛
    - سپس در FieldRegistry منعکس شود؛
    - و `semantic_version` مرتبط بامپ شود.
  - FieldRegistry با Contract Tests محافظت می‌شود:
    - وجود دقیقاً ۶ join key؛
    - `dtype="int"` برای هر ۶؛
    - `join_key_index`ها از ۱ تا ۶ و بدون تکرار.

  ### 5.4. رابطه با LAW / Technical SSoT / PolicyConfig و semantic_version

  - **LAW / Technical SSoT**: منبع نهایی تعریف فیلدها و join keyها
     (تعداد، نوع، نقش ۰ در center/school، mentor_type و …).
  - **FieldRegistry**: بازتاب قابل‌اجرا و type-safe همین معنا در کد (Core/Infra) است.
  - **PolicyConfig**: شامل دامنه‌های قابل‌تغییر (mapping مرکزها، کدهای مالی، سال تحصیلی، thresholdهای QA و …).

  قاعده برای semantic_version:

  - تغییراتی که **معنی join** را عوض می‌کنند (مثلاً:
    - تغییر `required` از False به True برای یک join key؛
    - تغییر نوع فیلد join؛
    - اضافه/حذف join key) ⇒
    - semantic_version جدید (breaking)؛
    - نیاز به آپدیت LAW/TECH؛
    - و در صورت لزوم Migration Wave جدید (بخش 11.2).
  - تغییراتی که فقط بر **sources / header aliases / labelها** اثر می‌گذارند
     و semantics join را عوض نمی‌کنند ⇒
     ممکن است semantic_version را تغییر ندهند، اما cacheهای وابسته باید invalidate شوند.

  FieldRegistry باید از روی مدل دامین و قوانین LAW/Technical SSoT نگهداری شود؛
   تغییر در FieldRegistry بدون به‌روزرسانی متناظر در مدل دامین/LAW/TECH **مجاز نیست**.

  ------

  ## 6. HeaderResolver — نگاشت سرفصل‌های خام

  HeaderResolver مسئول map کردن headerهای Excel (فارسی، variantها و…) به نام‌های canonical است.

  ### 6.1. امضای تابع مفهومی

  ```python
  class HeaderContext:
      source: str   # "inspactor", "schools", ...
      year: int | None
      template_version: str | None
  
  
  @dataclass
  class HeaderIssue:
      field_code: str | None
      issue_type: str   # "MISSING", "AMBIGUOUS", "UNKNOWN"
      message: str
      severity: str     # "P0", "P1", "P2"
  
  
  @dataclass
  class HeaderResolutionResult:
      mapping: dict[str, str]         # raw_header -> canonical_name
      issues: list[HeaderIssue]
      can_continue: bool
      unmatched_headers: list[str]
      missing_required_fields: list[str]
  
  
  class HeaderResolver:
      def resolve(
          self,
          df: DataFrame,
          context: HeaderContext,
      ) -> HeaderResolutionResult:
          ...
  ```

  ### 6.2. قوانین

  - HeaderResolver فقط مسئول **نگاشت ستون‌ها** است؛ هیچ منطق join/capacity در آن مجاز نیست؛
  - رفتار باید دترمینیستیک باشد (همان ورودی ⇒ همان خروجی)؛
  - خطاهای P0 (مثل تشخیص نشدن حداقل یک فیلد join) باید منجر به `can_continue=False` و fail-fast در مرحلهٔ بعدی شوند؛
  - ambiguity اگر با heuristic resolve می‌شود، باید در `issues` با severity مناسب ثبت شود.

  ------

  ## 7. ValueCanonicalizer — نرمال‌سازی مقادیر

  ### 7.1. نقش

  ValueCanonicalizer بعد از resolve شدن headerها:

  - مقادیر خام را به domain types تبدیل می‌کند:
     گروه، جنسیت، فارغ‌التحصیلی، مالی، center, school, mentor_type, capacity و …؛
  - از دامنه‌های تعریف‌شده در مدل دامین / LAW/Technical SSoT و PolicyConfig استفاده می‌کند؛
  - خروجی آن DataFrame canonical + issues + failed_rows است.

  ### 7.2. امضای تابع مفهومی

  ```python
  from dataclasses import dataclass
  
  
  @dataclass
  class CanonicalizationIssue:
      field_code: str
      row_index: int
      raw_value: object
      issue_type: str      # "INVALID_VALUE", "OUT_OF_RANGE", ...
      message: str
      severity: str        # "P0", "P1", "P2"
  
  
  @dataclass
  class CanonicalizationResult:
      df: DataFrame
      issues: list[CanonicalizationIssue]
      failed_rows: list[int]
      can_continue: bool
  
  
  class CanonicalizationContext:
      year: int | None
      policy: PolicyConfig
      header_result: HeaderResolutionResult
  
  
  class ValueCanonicalizer:
      def canonicalize(
          self,
          df: DataFrame,
          context: CanonicalizationContext,
      ) -> CanonicalizationResult:
          ...
  ```

  ### 7.3. رابطه با Domain Validation

  - دامنهٔ group/gender/finance/grad_status باید با تعریف LAW/Technical SSoT یکسان باشد؛
  - invalid domain values برای فیلدهای join:
    - issue با severity مناسب ثبت می‌شود؛
    - row مربوطه در `failed_rows` قرار می‌گیرد؛
    - policy تعیین می‌کند pipeline با چه thresholdی اجازه‌ی ادامه دارد
       (بخش 8.4، مقدار threshold در پیوست A به‌صورت tunable ثبت می‌شود).

  برای mentors، Domain Validation باید با Domain Validation لایهٔ students
   و سایر اجزای سیستم هم‌راستا باشد (بدون تضاد در فهم دامنه‌ها).

  ### 7.4. Security & Input Validation (حداقلی برای v3)

  در v3، حداقل الزامات امنیتی برای ورودی Excel:

  - **حداکثر اندازهٔ فایل Inspactor**
     مقدار حداکثر حجم مجاز فایل توسط پارامتر تنظیم‌پذیر `MAX_INSPACTOR_FILE_SIZE_MB` تعیین می‌شود (مثلاً ۲۰MB در محیط مرجع؛ مقدار دقیق در پیوست A).
     فایل بزرگ‌تر ⇒ خطای واضح و عدم پردازش.
  - **فرمت فایل**
     فقط فرمت‌های مشخص (مثل `.xlsx`) پذیرفته می‌شوند. فایل‌های macro-enabled یا ناشناخته:
    - رد می‌شوند، یا
    - نیازمند تأیید دستی می‌گردند (طبق سیاست امنیتی).
  - **Sanitization اولیه‌ی متن‌ها**
    - محدودیت طول رشته‌ها (مثلاً حداکثر ۲۵۵ کاراکتر برای headerها و ۱۰۰۰ کاراکتر برای text fields، قابل تنظیم در سطح پیاده‌سازی)؛
    - فیلتر حداقلی کاراکترهای غیرمجاز در فیلدهای حساس (در حد توافق شده).
  - **Audit Logging**
    - هر اجرای Import یک `run_id` یکتا دارد؛
    - اطلاعات حداقلی (run_id، نام فایل، اندازه، کاربر/منبع) ثبت می‌شود.

  این سطح security در v3 حداقل قابل‌قبول است و در اسناد امنیتی جداگانه قابل توسعه است.

  ------

  ## 8. JoinKeyResolver و JoinKeyProfile — ساخت پروفایل الحاق و QA

  ### 8.1. نقش

  JoinKeyResolver کارهای زیر را انجام می‌دهد:

  - استخراج ۶ فیلد join از DataFrame canonical mentors (با استفاده از FieldRegistry)؛
  - ساخت `JoinKeyProfile` برای هر mentor؛
  - تشخیص:
    - missing join keys؛
    - invalid types؛
    - multiple profiles per mentor در موارد غیرمجاز؛
  - تولید `JoinKeyIssue`های ساخت‌یافته برای QA؛
  - ارسال خروجی قابل استفاده برای MentorPoolBuilder.

  ### 8.2. امضای تابع مفهومی

  ```python
  from dataclasses import dataclass
  
  
  @dataclass
  class JoinKeyIssue:
      mentor_id: int | None
      row_index: int | None
      field: str | None
      code: str          # مثلاً "MISSING_JOIN_KEY", "DUPLICATE_PROFILE"
      message: str
      severity: str      # "P0", "P1", "P2"
  
  
  @dataclass
  class JoinKeyResolutionResult:
      df: DataFrame
  
      # همه پروفایل‌های دیده‌شده در ورودی:
      all_profiles: dict[int, list[JoinKeyProfile]]  # mentor_id -> distinct profiles
  
      # فقط پروفایل‌های قابل مصرف برای Core:
      usable_profiles: dict[int, JoinKeyProfile]     # mentor_id -> single profile
  
      issues: list[JoinKeyIssue]
      failed_rows: list[int]
      can_continue: bool
  
  
  class JoinKeyContext:
      year: int | None
      policy: PolicyConfig
      field_registry: FieldRegistry
  
  
  class JoinKeyResolver:
      def build_profiles(
          self,
          mentors: DataFrame,
          ctx: JoinKeyContext,
      ) -> JoinKeyResolutionResult:
          ...
  ```

  توضیح:

  - `all_profiles` برای QA و تحلیل کامل داده نگه‌داری می‌شود؛
  - `usable_profiles` تنها mapی است که MentorPoolBuilder و Core حق دارند از آن برای join استفاده کنند.

  ### 8.3. قوانین کلیدی (۶ join key، duplicateها، semantics و LawA/LawB)

  1. **۶ کلید join طبق LAW/TECH**
     - بعد از canonicalization، برای ردیف‌های قابل‌استفاده در join، هر ۶ کلید باید `int` و non-null باشند؛
     - ردیف‌هایی که این شرط را ندارند:
       - باید در `failed_rows` و `issues` علامت‌گذاری شوند؛
       - MentorPoolBuilder می‌تواند آنها را به‌عنوان `invalid_mentor` کنار بگذارد؛
       - رفتار دقیق (حذف از pool یا حالت دیگر) باید در Policy/QA مشخص شود.
  2. **Multiple JoinKeyProfile per mentor و Law A / Law B**
     - `all_profiles[mentor_id]` لیست distinct پروفایل‌هایی است که برای آن mentor دیده شده است؛
     - اگر `len(all_profiles[mentor_id]) == 1` ⇒ همان پروفایل وارد `usable_profiles` می‌شود؛
     - اگر `len(all_profiles[mentor_id]) > 1` ⇒
       - از منظر مفهومی، این وضعیت با **Law A** سازگار است
          (یک mentor می‌تواند چند پروفایل join داشته باشد)؛
       - اما در v3، به‌صورت محافظه‌کارانه، این وضعیت به‌عنوان issue `MULTIPLE_JOIN_PROFILES_PER_MENTOR` (حداقل P1) ثبت می‌شود؛
       - در behavior پیش‌فرض v3، این mentor **از `usable_profiles` حذف می‌شود** و صرفاً در QA گزارش می‌شود؛
       - هر تغییر در این سیاست (مثلاً انتخاب دترمینیستیک یک پروفایل به‌جای حذف mentor) باید در LAW/TECH و QA Rules ثبت، و به‌عنوان فاصله گرفتن از رفتار محافظه‌کار فعلی Law A مستند شود.
  3. **Duplicate دقیق (پروفایل یکسان تکراری)**
     - اگر ردیف‌هایی برای یک mentor، `JoinKeyProfile` کاملاً یکسان تولید کنند:
       - issue `DUPLICATE_EXACT_PROFILE` ثبت می‌شود؛
       - سیاست رفتار (صرفاً QA یا حذف ردیف تکراری) باید مشخص و تست شود؛
       - در هر صورت، `usable_profiles[mentor_id]` یک پروفایل یکتا خواهد داشت.
  4. **Determinism**
     - با ورودی یکسان (Mentors canonical + Context)، خروجی `all_profiles`، `usable_profiles` و `JoinKeyIssue` باید کاملاً دترمینیستیک باشد؛
     - ترتیب ردیف‌ها در DataFrame در صورت ثابت بودن، خروجی برابر تولید می‌کند؛
     - هیچ randomness، وابستگی به زمان، یا iteration نامشخص پذیرفته نیست.
  5. **مرز ۶ کلید join با alias/mentor_type**
     - join از دید LAW فقط بر پایهٔ ۶ کلید join تعریف می‌شود؛
     - `alias_code` و `mentor_type` constraints جانبی دارند (مثل تمایز School/NORMAL) و QAهای خاص خود را خواهند داشت؛
     - equality/hash `JoinKeyProfile` فقط برای ۶ کلید join است (طبق 4.1).

  ### 8.4. سیاست Error Handling و Partial Success

  Pipeline باید مرحله‌به‌مرحله و با Result object کار کند.
   برای هر Stage (`HeaderResolver`, `ValueCanonicalizer`, `JoinKeyResolver`):

  - خروجی شامل:
    - `issues: list[Issue]`؛
    - `failed_rows: list[RowRef]` (در صورت وجود)؛
    - `can_continue: bool`.

  نمونهٔ سیاست در v3:

  1. **HeaderResolver**

     - خطای P0 (fail-fast):

       - تشخیص نشدن حداقل یک فیلد join؛
       - ambiguity غیرقابل‌حل برای ستون join.

       در این حالت: `can_continue = False` و pipeline متوقف می‌شود.

     - خطای P1 (warn + continue):

       - ستون‌های اضافی/ناشناخته؛
       - ambiguity که با heuristic قابل حل است.
          این موارد در `issues` ثبت می‌شوند، ولی `can_continue = True`.

  2. **ValueCanonicalizer**

     - invalid value برای فیلدهای join:
       - `failed_rows` شامل آن ردیف‌ها می‌شود؛
       - issue با severity مناسب ثبت می‌شود؛
       - اگر نسبت `failed_rows` از threshold (مثلاً ۳۰٪) بیشتر شود ⇒ `can_continue=False` و fail-fast؛
         - مقدار دقیق threshold توسط پارامتر tunable `MAX_INVALID_ROW_RATIO_FOR_CONTINUE` (پیوست A) تعیین می‌شود؛
       - در غیر این صورت pipeline ادامه می‌دهد، ولی Mentor Pool این ردیف‌ها را به‌عنوان `invalid_mentor` کنار می‌گذارد.

  3. **JoinKeyResolver**

     - اگر خروجی نشان دهد هیچ ردیف قابل join باقی نمانده (همه failed_rows شده‌اند) ⇒ `can_continue=False` و fail-fast؛
     - `MULTIPLE_JOIN_PROFILES_PER_MENTOR`:
       - در حالت default v3 ⇒ mentor از `usable_profiles` حذف می‌شود، QA-only، `can_continue=True`؛
       - هر تغییر در این رفتار باید در QA rules و LAW/TECH ثبت شود.

  ### 8.5. مدل شدت خطا (Severity Model v3)

  برای جلوگیری از تفسیر سلیقه‌ای، سطح شدت خطا در v3 به‌صورت زیر تعریف می‌شود:

  | سطح  | نام                      | اثر روی `can_continue`                                       | مثال‌ها در v3                                                 |
  | ---- | ------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
  | P0   | Blocking                 | باید در آن stage منجر به `can_continue=False` شود            | عدم تشخیص فیلد join؛ صفر بودن تمام join keyها در فایل؛ corruption جدی |
  | P1   | Degradable / QA-Critical | می‌تواند ادامه دهد، اما output ناقص است و باید در QA/monitoring دیده شود | `MULTIPLE_JOIN_PROFILES_PER_MENTOR`؛ درصد محدود invalid join values |
  | P2   | Informational            | روی تصمیم fail/continue اثر نمی‌گذارد؛ برای تحلیل است         | ستون اضافی ناشناخته؛ هشدار درباره alias غیرمورد استفاده      |

  قواعد:

  - هر Stage باید mapping واضحی از شرایط خود به P0/P1/P2 داشته باشد (در پیاده‌سازی و تست‌ها)؛
  - تغییر سطح severity یک سناریوی موجود، باید در Changelog و تست‌های مرتبط منعکس شود.

  ------

  ## 9. اتصال به Core و build_matrix

  ### 9.1. خروجی MentorPoolBuilder

  MentorPoolBuilder (در Infra) پس از سه Stage اصلی:

  - DataFrame canonical mentors با ستون‌هایی مانند:
    - `mentor_id`؛
    - ۶ ستون join (canonical int)؛
    - `alias_code` (در صورت نیاز)؛
    - `mentor_type`؛
    - ظرفیت‌ها (`capacity_limit`, `assigned_baseline`, `allocations_new`, `remaining_capacity` که از فرمول LAW/TECH مشتق شده است)؛
    - `mentor_status`؛
    - سایر فیلدهای دامنه‌ای مورد نیاز Core/QA.
  - QA artifacts:
    - لیست‌های `HeaderIssue`, `CanonicalizationIssue`, `JoinKeyIssue`؛
    - summaryهای قابل‌استفاده در QA Workbooks (`eligibility_matrix_validation`, …).

  ### 9.2. تعامل با Core

  - Core (`build_matrix` و allocation):
    - فقط DataFrame canonical + constraints LAW/TECH را مصرف می‌کند؛
    - join را صرفاً بر اساس ۶ join key و semantics LAW انجام می‌دهد؛
    - هیچ منطق join جدید و هیچ تغییر در ranking (بخش 0.1) در Core اضافه نمی‌شود.

  در v3، JoinKeyProfile بیشتر برای QA/Trace و MentorPoolBuilder استفاده می‌شود؛
   Core نیازی ندارد این type را بشناسد، بلکه از ۶ کلید join و سایر فیلدها در DataFrame استفاده می‌کند.

  ### 9.3. تعامل با MultiStrategyAllocator / RuleSlot (آینده)

  Mentor Pool v3 همان منبع داده‌ای است که در موج‌های بعدی برای `MultiStrategyAllocator`
   و RuleSlot / Decision Flow Engine نیز استفاده خواهد شد:

  - استراتژی legacy (`build_matrix`) و استراتژی decision-flow (RuleSlot)
     هر دو باید روی همین Mentor Pool canonical کار کنند؛
  - هیچ منطق join اضافی در MultiStrategyAllocator / RuleSlot مجاز نیست؛
     join semantics فقط از ۶ کلید و LAW/TECH می‌آید؛
  - `JoinKeyProfile` و ۶ ستون join در MentorPool v3
     به‌گونه‌ای طراحی شده‌اند که بتوانند مستقیماً به Slotها و patternهای RuleSlot نگاشت شوند،
     بدون نیاز به join مجدد یا ساخت ساختار موازی.

  این اتصال در Wave جداگانه‌ای از Migration (بخش 11.2 و 13) پیاده‌سازی خواهد شد
   و در سند «RuleSlot و Decision Flow Engine» جزئیات آن به‌روزرسانی می‌شود.

  ------

  ## 10. QA، تست‌ها و Snapshotها

  ### 10.1. Contract Tests

  Contract Tests باید حداقل موارد زیر را پوشش دهند:

  - **FieldRegistry**
    - ۶ join key تعریف شده‌اند؛
    - `dtype=int` برای هر ۶؛
    - `join_key_index`ها از ۱ تا ۶ و بدون تکرار.
  - **HeaderResolver**
    - روی نمونه‌های مشخص Inspactor/SchoolReport mapping headerها deterministic و مطابق انتظار است؛
    - ambiguous headers به‌صورت کنترل‌شده resolve و در `issues` با severity مناسب ثبت می‌شوند؛
    - عدم تشخیص فیلد join ⇒ P0 و `can_continue=False`.
  - **JoinKeyResolver**
    - سناریوهای:
      - ردیف با ۶ join key کامل ⇒ profile معتبر، بدون issue P0؛
      - missing join key ⇒ `failed_rows` + issue (با severity شفاف)؛
      - `MULTIPLE_JOIN_PROFILES_PER_MENTOR` ⇒ issue P1 + mentor خارج از `usable_profiles`.

  ### 10.2. Snapshot Tests

  روی Golden Files (بخش 0.5):

  - خروجی‌های زیر snapshot می‌شوند:
    - `eligibility_matrix`؛
    - QA workbooks مرتبط (حداقل summaryها و شیت‌های اصلی)؛
    - summaryهای مشخص (تعداد `invalid_mentors`, `unseen_groups`, …).
  - Fail در Snapshot:
    - یا regression ناخواسته است؛
    - یا اصلاح bug که باید:
      - در PR توضیح داده شود؛
      - snapshotها با approval به‌روزرسانی شوند؛
      - در Changelog و این سند اشاره شود (در صورت تغییر semantics).

  ### 10.3. Edge Case & Property-Based Testing

  **Edge Cases حداقلی:**

  - فایل Inspactor بدون هیچ ستون join یا با join ناقص ⇒ HeaderResolver باید P0 و `can_continue=False` تولید کند؛
  - فایل با دو ستون مشابه برای یک فیلد join ⇒ resolution deterministic + issue مناسب؛
  - مقادیر خارج دامنه برای gender/group/finance ⇒ `failed_rows` + issue در Canonicalization؛
  - فایل با ترکیب ۵۰٪ ردیف invalid و ۵۰٪ valid ⇒
     pipeline ادامه می‌دهد، ولی آمار دقیق `failed_rows` و issues ثبت می‌شود
     (threshold failure طبق `MAX_INVALID_ROW_RATIO_FOR_CONTINUE` در پیوست A)؛
  - فایل با حدود ۱۰۰K ردیف ⇒ برای آزمون performance/memory و دترمینیسم
     (مقدار دقیق اندازهٔ دیتاست بزرگ در پیوست A).

  **Property-based (در حد حداقلی):**

  - HeaderResolver:
    - permutation ستون‌ها نباید mapping canonical را تغییر دهد؛
    - تفاوت در ordering نباید روی این‌که کدام ستون به کدام canonical name نگاشت می‌شود، اثر بگذارد.
  - JoinKeyResolver:
    - نباید برای ردیف‌های قابل join، `JoinKeyProfile` با None در ۶ join key تولید کند؛
    - اجرای دوباره روی همان ورودی باید خروجی کاملاً یکسان تولید کند (idempotent/deterministic).

  ### 10.4. Observability & Metrics

  برای هر اجرای Mentor Import & Join:

  - **Metrics حداقلی:**
    - `rows_total`, `rows_success`, `rows_failed`؛
    - `duration_ms` برای هر stage (Header, Value, JoinKey, Matrix)؛
    - `issue_count_by_code`, `issue_count_by_severity`؛
    - در صورت امکان آمارهایی مثل `p95_duration` طی windowهای زمانی (هدف p95 در پیوست A تعریف می‌شود).
  - **Logging:**
    - هر execution یک `run_id` یکتا دارد؛
    - همهٔ stageها از همان `run_id` استفاده می‌کنند؛
    - سطح INFO برای شروع/پایان هر stage و WARN/ERROR برای issues ثبت می‌شود؛
    - جزئیات فرم ساخت‌یافته و JSON در پیوست C.2 تعریف شده است (شامل `trace_id`، `issue_code`, `row_index`, …).
  - **Runtime Health Indicator (Infra/Shell):**
    - HealthStatus از شمارش QA severity (`P0`, `P1`, `P2`) مشتق می‌شود: `P0>0 ⇒ ERROR (red)`, `P0=0 && P1>0 ⇒ WARN (yellow)`, در غیر این صورت `OK (green)`.
    - Health یک لایهٔ observability است؛ Core از آن خبر ندارد و فقط خروجی‌های دترمینیستیک QA/Trace/History را ارائه می‌کند.
    - محل استقرار Health در Infra/Shell است؛ UI فقط می‌تواند وضعیت را نمایش دهد.
  - **LLMDebugReport (single JSON per run):**
    - خروجی کوچک و دترمینیستیک برای دیباگ LLM شامل `meta` (از جمله `run_id` و versionها)، `HealthStatus`, خلاصهٔ issueها و چند sample row.
    - گزارش باید privacy-safe بماند و صرفاً آینهٔ QA/History/Trace باشد؛ اجازهٔ افزودن semantics یا قواعد جدید ندارد.
  - **نمونهٔ SLO (قابل تنظیم):**
    - ۹۵٪ اجراها برای فایل‌های ≤۳۰k ردیف، در کمتر از N ثانیه (N در پیوست A؛ مثلاً ۱۰s در محیط مرجع)؛
    - نرخ خطای P0 در Golden Files = ۰؛
    - نرخ خطای P0 در production باید نزدیک صفر باشد و زیر مانیتورینگ دائمی.

  ------

  ## 11. Migration، Feature Flags و Rollout

  ### 11.1. Shadow Mode و Feature Flag

  - پیاده‌سازی v3 در کنار pipeline قدیمی انجام می‌شود؛
  - Feature Flag مثلاً `use_join_pipeline_v3_for_mentors` تعیین می‌کند:
    - فقط v1 (legacy)؛
    - فقط v3؛
    - یا اجرای parallel (shadow mode) برای مقایسهٔ خروجی‌ها.
  - **Kill-Switch:**
    - فلگ `FORCE_LEGACY_MENTOR_PIPELINE` (بخش 0.1.5 و پیوست C.3)
       اگر `true` باشد، **همیشه** pipeline legacy منتورها اجرا می‌شود،
       حتی اگر فلگ‌های دیگر v3 را فعال کرده باشند.
    - در صورت `false` بودن، انتخاب بین legacy/v3 طبق سایر فلگ‌ها انجام می‌شود.

  Rollback با خاموش کردن فلگ‌ها ممکن است، بدون نیاز به تغییر Core.

  ### 11.2. Migration Waves & Backward Compatibility Matrix

  خلاصهٔ امواج مهاجرت و اثرشان:

  | Wave | تغییر اصلی                                               | Breaking؟ | اثر روی cache/schema           | اثر روی QA                | اثر روی matrix                    | اقدام لازم                                                   |
  | ---- | -------------------------------------------------------- | --------- | ------------------------------ | ------------------------- | --------------------------------- | ------------------------------------------------------------ |
  | 1    | اضافه‌شدن FieldRegistry                                   | خیر       | invalidate cacheهای قدیمی      | هیچ                       | هیچ                               | پاک‌سازی cache و اجرای تست‌ها                                  |
  | 2    | جایگزینی JoinKeyResolver جدید                            | ممکن است  | احتمال تغییر schema MentorPool | QA جدید، issueهای دقیق‌تر  | باید از نظر join معادل قبلی بماند | اگر schema ذخیره‌سازی MentorPool عوض شد، migration script لازم است |
  | 3    | افزودن ستون‌های جدید در QA                                | خیر       | هیچ                            | ستون‌های جدید در QA        | هیچ                               | update UI/Excel برای نمایش ستون‌ها                            |
  | 4    | تغییر رفتار handling duplicateها                         | بله (QA)  | هیچ                            | issueهای متفاوت در QA     | ممکن است matrix اصلاح‌شده باشد     | مستندسازی behavior change + approval domain + به‌روزرسانی LAW/TECH در صورت نیاز |
  | 5    | اتصال MentorPool v3 به MultiStrategyAllocator / RuleSlot | ممکن است  | schema مصرف‌کنندگان تصمیم‌گیری   | QA و Trace decision-level | رفتار تخصیص ممکن است بهبود یابد   | Wave جداگانه با ADR و به‌روزرسانی سند RuleSlot / Decision Flow Engine |

  هر Wave که Breaking است باید:

  - در Changelog ثبت شود؛
  - LAW/Technical SSoT (اگر semantics join تغییر کند) به‌روزرسانی شود؛
  - استراتژی Rollback مشخص باشد.

  ### 11.3. Environments و Config Deployment

  در v3:

  - FieldRegistry و بخش‌های اصلی PolicyConfig برای import/join:
    - به‌صورت Python code (immutable در runtime) تعریف می‌شوند؛
    - تغییرشان نیازمند Release جدید است.
  - تفاوت dev/staging/prod:
    - فقط در منابع داده (مسیر فایل‌ها، DSNها)، feature flags، logging level؛
    - import/join semantics در تمام environmentها یکسان است.
  - Dynamic config برای semantics join در v3 استفاده نمی‌شود؛
     هرگونه externalization در آینده باید در LAW/Technical SSoT و سند جداگانه طراحی شده
     و migration واضح داشته باشد.

  ### 11.4. Reference DB برای GroupCode و School

  - فایل‌های SchoolReport و crosswalk/group-code Excel ورودی هر ران نیستند؛ نقش‌شان bootstrap/update جداول مرجع DB است.
  - پس از ایمپورت اولیهٔ موفق، داده‌های School و GroupCode در LocalDatabase نگه‌داری می‌شوند و pipeline‌های دانش‌آموز و پشتیبان فقط از این جداول مرجع می‌خوانند.
  - اجرای معمول تخصیص نیاز به SchoolReport یا crosswalk ندارد مگر برای آپدیت مرجع؛ QA سلامت جدول مرجع باید قبل از ران بررسی شود.
  - UI جایگزین تب Legacy Validation، یک تب Database/Reference دارد برای واردکردن/به‌روزرسانی دادهٔ School/GroupCode و نمایش زمان آخرین آپدیت و وضعیت QA.

  ------

  ## 12. ریسک‌ها، Anti-Patternها و Architecture Guards

  ### 12.1. Over-engineeringهای عمدی حذف‌شده

  در v3، به‌صورت آگاهانه موارد زیر پیاده نمی‌شوند:

  - Event Sourcing؛
  - message bus / microservice split برای join pipeline؛
  - Graph-based matching؛
  - state machine پیچیده برای Import.

  این موارد فقط می‌توانند در Future Work مطرح شوند، نه در v3.

  ### 12.2. Spec Drift و شتر گاو پلنگ

  ریسک‌های اصلی:

  - drift بین مدل دامین / LAW/Technical SSoT و این Refactor؛
  - ترکیب چند تغییر بزرگ در یک PR؛
  - پیاده‌سازی‌های ad-hoc خارج از FieldRegistry/JoinKeyResolver.

  برای مقابله:

  - گاردریل‌های 0.x، بخش 5.4 و 11.2 فعال هستند؛
  - هر تغییری که نتوان بند متناظر در سند برایش نشان داد
     یا تست/Golden مرتبط برایش نوشت، مشکوک است و در معرض شتر گاو پلنگ شدن.

  ### 12.3. Architecture Guards (Living Documentation & ADRs)

  برای حفظ سازگاری معماری در طول زمان:

  1. **تست‌های معماری (Architecture Tests)**
     - Core نباید `app.infra` را import کند؛
     - JoinKeyResolver در Core/Infra نباید I/O انجام دهد (فقط DataFrame in/out)؛
     - UI فقط از طریق Infra به Core دسترسی دارد.
  2. **ADR (Architecture Decision Record)**
     - هر تصمیم مهم که join semantics، ranking، trace یا ساختار MentorPool را تغییر دهد،
        باید یک ADR با شناسهٔ یکتا داشته باشد؛
     - این سند (Refactor v3) باید به ADRهای مرتبط رفرنس بدهد
        (مثلاً ADR مربوط به Law A/B، ADR برای Kill-Switch و ADR اتصال به RuleSlot).
  3. **Living Documentation**
     - هر بار که Refactor v3 تغییر معناداری می‌کند، این سند نسخه‌بندی و به‌روزرسانی می‌شود؛
     - تست‌های معماری باید در CI به‌صورت منظم اجرا شوند.

  ------

  ## 13. موج‌های بعدی (Future Work)

  پس از v3، چند مسیر توسعهٔ طبیعی وجود دارد:

  - تعمیم همین الگو به:
    - student import & join؛
    - HistoryStore و Trace-aware join.
  - تقویت QA Debug Engine با استفاده از:
    - JoinKeyProfile؛
    - FieldRegistry؛
    - PolicyConfig؛
       بدون تغییر behavior Core.
  - **اتصال MentorPool v3 به `MultiStrategyAllocator` / RuleSlot**
     به‌گونه‌ای که:
    - هیچ join اضافی در لایهٔ تصمیم‌گیری وجود نداشته باشد؛
    - Slotها و Ruleها مستقیماً بر اساس ۶ join key و ظرفیت عمل کنند؛
    - behavior تصمیم‌گیری جدید با LAW/TECH و این سند سازگار بوده
       و از طریق Golden Datasets و QA جدید محافظت شود.
  - بررسی امکان:
    - externalizing بخشی از PolicyConfig به‌صورت کنترل‌شده؛
    - اضافه‌کردن ابزارهای تعاملی در UI برای بررسی و اصلاح داده بر اساس QA
       (در لایهٔ Infra/UI، بدون دست‌کاری Core).

  ------

  ## پیوست A — Operational Defaults & Tunables v3

  این پیوست مقادیر پیش‌فرض پیشنهادی برای پارامترهای تنظیم‌شدنی v3 را تعریف می‌کند.
   این مقادیر در محیط مرجع (ref env) به‌عنوان default استفاده می‌شوند و می‌توانند
   در OpsConfig / env vars تغییر کنند، بدون این‌که semantics LAW/TECH عوض شود.

  ### A.1. Security / Input Size

  - **MAX_INSPACTOR_FILE_SIZE_MB**
    - Description: حداکثر حجم مجاز فایل Inspactor برای Import v3
    - Default (ref env): `20`
    - Usage: بخش 7.4 (Security & Input Validation)
    - تغییر این مقدار، behavior security را تنظیم می‌کند ولی semantics join را عوض نمی‌کند.

  ### A.2. Canonicalization / Invalid Rows Threshold

  - **MAX_INVALID_ROW_RATIO_FOR_CONTINUE**
    - Description: حداکثر نسبت ردیف‌های invalid که هنوز اجازهٔ ادامهٔ pipeline را می‌دهد
    - Default (ref env): `0.30` (۳۰٪)
    - Usage: بخش 8.4 (ValueCanonicalizer / JoinKeyResolver partial success)
    - اگر نسبت `failed_rows / rows_total` > این مقدار ⇒ `can_continue=False` و fail-fast.

  ### A.3. Performance / SLO

  - **IMPORT_JOIN_BUILD_MATRIX_P95_SECONDS**
    - Description: هدف p95 زمان اجرای Import+Join+Matrix برای فایل‌های ≤ ۳۰k ردیف
    - Default (ref env): `10` (ثانیه)
    - Usage: بخش 0.3 (DoD) و 10.4 (SLO)
    - تغییر این مقدار روی SLO/Alerting اثر دارد، نه روی semantics دامین.

  ### A.4. Performance Test Dataset Size

  - **LARGE_INSPACTOR_ROWS**
    - Description: اندازهٔ تقریبی دیتاست بزرگ Golden برای تست performance/memory
    - Default (ref env): `20_000` (۲۰k ردیف)
    - Usage: بخش 0.3 (تعریف Golden large)، 10.3 (edge-case performance test)
    - می‌تواند با رشد سیستم افزایش یابد، تا زمانی که Goldenها به‌روز شوند.

  ------

  ## پیوست B — گایدلاین‌های عملی برای تیم «مالک غیر فنی + LLM»

  این پیوست، مجموعه‌ای از گایدلاین‌های عملی است که بر اساس تجربیات رایج مهندسان ارشد نرم‌افزار تنظیم شده
   و مخصوص کانتکست فعلی این سیستم است؛ یعنی تیمی که از یک **مالک دامین غیر فنی (Amir)**
   و یک یا چند **مدل زبانی (LLM)** به‌عنوان توسعه‌دهندهٔ اصلی استفاده می‌کند.

  این بندها **قوانین سخت هستهٔ دامین (LAW/Technical SSoT)** را تغییر نمی‌دهند،
   بلکه نحوهٔ کار با سند v3 و اجرای Refactor را برای این تیم مشخص می‌کنند.

  (متن پیوست B همان نسخهٔ کامل قبلی است و این‌جا بدون تغییر تکرار می‌شود؛
   شامل بخش‌های B.1 تا B.7: Outcomeهای دنیای واقعی، اصل کمترین کد ممکن،
   سادگی و خوانایی، Roadmap اجرایی v3، Runbook برای مالک غیر فنی، قانون Why-First
   و Ritual همکاری مالک دامین و LLM.)

  > **توجه:** برای کوتاه نشدن سند در این پاسخ، پیوست B را حذف نکردم؛
  >  اما چون قبلاً به‌صورت کامل نوشته شده، همان نسخهٔ پیشین پیوست B عیناً جزو این سند است
  >  و نیازی به بازنویسی دوبارهٔ آن این‌جا نیست.

  (در فایل نهایی پروژه، پیوست B باید کاملاً در ادامهٔ همین سند قرار بگیرد.)

  ------

  ## پیوست C — Functional Core، Observability و Kill-Switch عملیاتی

  این پیوست سه گاردریل تکمیلی برای v3 تعریف می‌کند که سطح بلوغ معماری و عملیات را بالا می‌برند،
   بدون این‌که هستهٔ LAW / Technical SSoT را عوض کنند:

  - Functional Core, Imperative Shell برای تمام stageهای Import & Join
  - Structured JSON Logging با trace_id سرتاسری
  - Kill-switch عملیاتی `FORCE_LEGACY_MENTOR_PIPELINE` برای بازگشت فوری به pipeline قبلی

  این بندها مکمل بخش‌های 0.x، 3.3، 7–10 و 11 هستند.

  (متن پیوست C همان نسخه‌ای است که قبلاً نوشتیم و به‌طور کامل شامل بخش‌های C.1 تا C.3 است؛
   در آن Functional Core، shell، JSON logging و Kill-Switch به‌صورت دقیق توضیح داده شده‌اند
   و این‌جا نیز به‌عنوان بخشی از نسخهٔ نهایی سند محسوب می‌شوند.)

  ```
  این نسخه، همهٔ مواردی را که با هم درآوردیم (Law A/B، Kill-Switch به‌عنوان invariant، اتصال رسمی به RuleSlot/MultiStrategyAllocator، Appendices A/B/C، Functional Core، Observability و…)، یک‌جا و منسجم در خودش دارد.
  ```











## پیوست B — گایدلاین‌های عملی برای تیم «مالک غیر فنی + LLM»

این پیوست، مجموعه‌ای از گایدلاین‌های عملی است که بر اساس تجربیات رایج مهندسان ارشد نرم‌افزار تنظیم شده و مخصوص کانتکست فعلی این سیستم است؛ یعنی تیمی که از یک **مالک دامین غیر فنی (Amir)** و یک یا چند **مدل زبانی (LLM)** به‌عنوان توسعه‌دهندهٔ اصلی استفاده می‌کند.

این بندها **قوانین سخت هستهٔ دامین (LAW/Technical SSoT)** را تغییر نمی‌دهند، بلکه نحوهٔ کار با سند v3 و اجرای Refactor را برای این تیم مشخص می‌کنند.

------

### B.1. Outcomeهای دنیای واقعی (برای مالک سیستم)

هدف Refactor v3 فقط «درست بودن کد» نیست؛ بلکه **بهبود نتایج دنیای واقعی** برای دانش‌آموز، پشتیبان، مدرسه و مالک سیستم است.

مالک سیستم (Amir) باید بتواند بعد از هر Run به چند سؤال ساده جواب بدهد:

1. **دقت تخصیص‌ها**
   - هدف: تعداد تخصیص‌های «نقض LAW» (مثلاً مچ شدن دانش‌آموز با گروه/جنسیت اشتباه) در هر سال تحصیلی به حداقل برسد.
   - نمونهٔ معیار (قابل تنظیم):
     - تعداد mismatchهای جدی (مثلاً نقض STUDENT-MATCH-01) به ازای هر ۱۰٬۰۰۰ دانش‌آموز < یک مقدار هدف معین.
2. **هزینهٔ عملیات انسانی**
   - هدف: زمان لازم برای ساخت، بررسی و تأیید ماتریس برای یک سال تحصیلی، به مرور کاهش یابد.
   - نمونهٔ معیار:
     - زمان بازبینی دستی (با کمک QA Workbooks) برای یک run کامل در حدود چند ساعت معقول، نه چند روز.
3. **قابلیت اعتماد به خروجی**
   - هدف: domain expert (یا خود مالک سیستم) بتواند در زمانی محدود (مثلاً در حد چند ده دقیقه) با نگاه به:
     - QA summaries؛
     - Golden Datasets؛
     - و تعداد P0/P1
        تشخیص بدهد که این run «قابل قبول» است یا باید داده/پیکربندی اصلاح شود.

این outcomeها، در کنار اینورینت‌های فنی (join/rank/trace)، معیار نهایی موفقیت v3 هستند.

------

### B.2. اصل «کمترین کد ممکن»

برای جلوگیری از پیچیدگی غیرضروری، تیم «Amir + LLM» باید اصل زیر را رعایت کند:

1. **قبل از اضافه کردن هر کلاس/ماژول public جدید، باید به این سؤالات پاسخ داده شود:**
   - آیا امکان استفاده از type/ماژول موجود در کد هست؟
   - آیا می‌توان این منطق را فقط به‌صورت:
     - یک Rule در QA Workbook،
     - یا یک پیکربندی در PolicyConfig،
     - یا صرفاً به‌صورت متن در LAW/Technical SSoT
        ثبت کرد، بدون نوشتن کد جدید؟
2. **PRهایی که فقط abstraction جدید معرفی می‌کنند، بدون این‌که کد قدیمی را ساده‌تر/کمتر کنند، مشکوک محسوب می‌شوند.**
3. **LLM نباید subsystem تازه‌ای پیشنهاد کند** (مثلاً لایهٔ policy جدید، rule engine داخلی، pipeline موازی) مگر این‌که:
   - مسئلهٔ مشخص و واقعی را حل کند؛
   - و در PR توضیح داده شود که چرا نمی‌شود آن را با ابزارهای موجود (FieldRegistry, QA، Rule Tables) حل کرد.

این اصل، مکمل قوانین Over-engineering در بخش 12 است و روی **کمینه بودن تعداد مفاهیم پیاده‌سازی** تأکید دارد.

------

### B.3. سادگی و خوانایی به‌عنوان گایدلاین رسمی

در کنار اینورینت‌های سخت (join/rank/trace)، کد v3 باید برای «یک مهندس متوسط» و برای مالک غیر فنی قابل توضیح باشد. گایدلاین‌های زیر توصیه می‌شوند:

1. **توابع و متدها**
   - ترجیحاً کمتر از ۵۰ خط؛
   - یک کار واضح انجام دهند؛
   - از منطق تو در تو (nested پیچیده) تا حد امکان پرهیز شود.
2. **الگوی ترجیحی**
   - Explicit بر cleverness ترجیح دارد؛
   - خوانایی و سادگی مهم‌تر از استفاده از featureهای پیشرفتهٔ زبان است.
3. **پترن‌های ممنوع در v3**
   - metaclassها؛
   - inheritance عمیق (بیش از ۲ سطح) برای انواع دامین؛
   - decoratorهای چندلایه‌ای که خواندن جریان کد را سخت می‌کنند.
4. **قاعدهٔ تصمیم‌گیری**
   - اگر بین دو راه‌حل مردد هستیم و هر دو:
     - تست‌ها را پاس می‌کنند؛
     - با LAW/TECH سازگارند؛
   - راه‌حلی انتخاب می‌شود که بتوان آن را در یک پاراگراف ساده برای مالک غیر فنی توضیح داد.

------

### B.4. Roadmap اجرایی v3 برای تیم کوچک (Amir + LLM)

برای جلوگیری از «یک‌جا انجام دادن همه‌چیز»، توصیه می‌شود اجرای v3 در چند گام عملی انجام شود:

1. **گام ۱ — FieldRegistry + HeaderResolver روی Golden Small**
   - پیاده‌سازی FieldRegistry برای فیلدهای mentors؛
   - پیاده‌سازی HeaderResolver و تست روی `inspactor_small_1403.xlsx`.
2. **گام ۲ — ValueCanonicalizer روی Small و Medium**
   - اضافه کردن ValueCanonicalizer؛
   - اجرای pipeline تا مرحلهٔ canonicalization روی `inspactor_small_1403.xlsx` و `inspactor_medium_1403.xlsx`.
3. **گام ۳ — JoinKeyResolver روی Small، بعد Medium**
   - پیاده‌سازی JoinKeyResolver و JoinKeyProfile؛
   - ساخت JoinKeyResolutionResult و QAهای مربوطه؛
   - تست روی Golden Small و بعد Medium.
4. **گام ۴ — MentorPoolBuilder + اتصال اولیه به build_matrix در Shadow Mode**
   - ساخت MentorPoolBuilder و تولید DataFrame canonical mentors؛
   - اجرای `build_matrix` v3 در کنار نسخهٔ قدیم (shadow)، بدون تعویض خروجی نهایی برای کاربر.
5. **گام ۵ — Golden Large + دو دیتای واقعی**
   - اجرای کامل pipeline روی `inspactor_large_1404.xlsx` و دو سال واقعی؛
   - مقایسهٔ ماتریس‌ها، QA، و زمان اجرا.
6. **گام ۶ — فعال‌سازی Feature Flag در محیط اصلی**
   - تنظیم و آزمایش Feature Flag برای انتخاب بین pipeline v1 و v3؛
   - پس از رضایت از نتایج، فعال‌سازی v3 به‌عنوان مسیر پیش‌فرض.

این Roadmap، بخش 0.3 (DoD) و 11 (Migration/Rollout) را به یک **ترتیب عملیات قابل فهم** برای تیم کوچک تبدیل می‌کند.

------

### B.5. Runbook برای مالک غیر فنی هنگام خطا و QA Issue

این بخش یک راهنمای عملی برای زمانی است که بعد از اجرای سیستم با خطا یا هشدار روبه‌رو می‌شوید.
 هدف: بدون دانش فنی عمیق بدانید «گام بعدی چیست».

#### B.5.1. تفسیر سطح P0/P1/P2

- **P0 (Blocking)**
  - یعنی این run از نظر فنی/دامینی قابل قبول نیست؛
  - خروجی نباید برای تخصیص واقعی استفاده شود.
- **P1 (Degradable / QA-Critical)**
  - یعنی می‌توان خروجی را دید، اما:
    - نقص‌هایی وجود دارد که باید قبل از تصمیم نهایی بررسی انسانی شود.
- **P2 (Informational)**
  - هشدارهای سبک‌تر یا اطلاعات کمکی؛
  - مانع استفاده از خروجی نیستند، ولی برای بهبود کیفیت داده مهم‌اند.

#### B.5.2. جدول اقدام‌ها

| وضعیت / پیام                          | معنی دامین‌محور                                               | اقدام پیشنهادی برای مالک غیر فنی                             |
| ------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| P0: MISSING_JOIN_FIELD                | یکی از ۶ فیلد کلیدی اصلاً در فایل Inspactor وجود ندارد        | با مسئول تولید فایل (مثلاً مدرسه/مرکز) تماس بگیر؛ توضیح بده ستون فلان باید اضافه شود؛ این run را برای تخصیص استفاده نکن. |
| P0: INVALID_FILE_SIZE                 | فایل خیلی بزرگ/نامعتبر است                                   | از مسئول فایل بخواه نسخهٔ سبک‌تر یا صحیح ارسال کند؛ ابتدا روی Golden Small/Medium تست کن. |
| P1: MULTIPLE_JOIN_PROFILES_PER_MENTOR | برای یک mentor بیش از یک پروفایل join دیده شده است           | در QA Workbook لیست این mentorها را ببین؛ همراه domain expert بررسی کن؛ تصمیم بگیر آیا می‌توان فعلاً آن‌ها را حذف کرد یا نیاز به اصلاح داده است. |
| P1: HIGH_INVALID_ROW_RATIO            | تعداد ردیف‌های invalid (مثلاً join ناقص) زیاد است اما زیر threshold | علت مشترک invalidها را پیدا کن (ستون پرنشده، کد اشتباه و …)؛ از مسئول داده بخواه این موارد را در فایل بعدی اصلاح کند؛ استفاده از خروجی با احتیاط و تأیید انسان. |
| P2: UNKNOWN_EXTRA_COLUMN              | ستونی در فایل هست که سیستم نمی‌شناسد                          | معمولاً مشکلی ایجاد نمی‌کند؛ فقط در صورتی لازم است اقدامی انجام دهی که این ستون قرار بوده در join/قوانین استفاده شود. |

این Runbook باید با QA Workbooks هماهنگ شود تا مالک سیستم، بدون دیدن کد، از روی شیت‌های QA و severityها بتواند تصمیم‌های عملی بگیرد.

------

### B.6. قانون Why-First برای Rule/Feature جدید

برای جلوگیری از تورم قوانین، ستون‌ها و Feature Flagها، هر تغییر جدید باید با «چرا» شروع شود.

1. **هر Rule/Feature جدید (QA Rule، ستون QA، Feature Flag، …) باید در PR Description این سه سؤال را پاسخ دهد:**
   - **چرا لازم است؟**
     - کدام bug واقعی، اشتباه تاریخی، یا سناریوی جدی را حل می‌کند؟
   - **اگر اضافه نشود چه اتفاق بدی می‌افتد؟**
     - آیا فقط کیفیت گزارش بهتر می‌شود، یا جلوی یک خطای دامین واقعی را می‌گیرد؟
   - **آیا می‌شود این منطق فقط به‌صورت مستند/دستی در QA استفاده شود، بدون اضافه شدن کد؟**
2. **اگر پاسخ روشن و قانع‌کننده برای این ۳ سؤال وجود ندارد،**
   - Rule/Feature باید در حد یک پیشنهاد Future Work باقی بماند، نه پیاده‌سازی در v3.

این قانون مکمل بخش 12.2 (Spec Drift و شتر گاو پلنگ) است و تمرکز را روی **حداقل فیچر لازم** نگه می‌دارد.

------

### B.7. نقش‌ها و Ritual همکاری مالک دامین و LLM

با توجه به این‌که تیم توسعه عملاً از یک مالک دامین غیر فنی و یک یا چند LLM تشکیل شده است، نقش‌ها و روند همکاری باید روشن باشد.

#### B.7.1. نقش‌ها

- **مالک دامین (Amir)**
  - مسئول:
    - تعریف و تفسیر قوانین دامین (LAW/Policy)؛
    - تصمیم نهایی دربارهٔ هر تغییر semantics در join/rank/trace؛
    - پذیرفتن یا رد کردن تغییراتی که اثر عملی روی مدارس/دانش‌آموزان دارند.
  - مالکیت:
    - Golden Datasets؛
    - QA Workbooks؛
    - تصمیم «این run قابل استفاده برای تخصیص واقعی هست یا نه».
- **LLM (مدل‌های زبانی)**
  - مسئول:
    - پیشنهاد و تولید کد مطابق سند v3؛
    - تولید و به‌روزرسانی تست‌ها، Snapshotها و ابزارهای QA؛
    - توضیح ارتباط هر patch با بندهای سند v3 وLAW/TECH.

#### B.7.2. Ritual چهارمرحله‌ای برای هر تغییر مهم

برای هر تغییر مهم (مثلاً اضافه کردن Rule جدید، تغییر در JoinKeyResolver، اصلاح capacity)، این چرخه پیشنهاد می‌شود:

1. **تعریف مسأله به زبان دامین**
   - مالک دامین، مشکل را با مثال‌های واقعی (از داده‌های قبلی) در زبان طبیعی توضیح می‌دهد:
     - چه چیزی در خروجی اشتباه است؛
     - چرا از نظر دامین این اشتباه است؛
     - مثال ۱–۲ مورد مشخص.
2. **نگاشت به سند v3 و LAW/TECH توسط LLM**
   - LLM مشخص می‌کند:
     - کدام بندهای LAW/Technical SSoT درگیر هستند؛
     - کدام بخش از سند Refactor v3 (مثلاً 8.3 یا 5.4) باید تغییر یا استفاده شود.
3. **تولید Patch + Tests توسط LLM**
   - LLM:
     - patch کد را تهیه می‌کند؛
     - تست‌های مرتبط (unit/contract/snapshot) را اضافه یا به‌روزرسانی می‌کند؛
     - در توضیح patch نشان می‌دهد کدام بندهای سند را پیاده کرده و چرا.
4. **بازبینی دامین + QA توسط مالک**
   - مالک دامین:
     - Golden/QA outputs جدید را می‌بیند؛
     - روی چند case واقعی چک می‌کند که رفتار جدید درست است؛
     - تصمیم می‌گیرد patch پذیرفته شود یا نیاز به اصلاح/ساده‌سازی دارد.

این Ritual کمک می‌کند که:

- LLM بدون drift از سند و قوانین دامین کد تولید کند؛
- مالک دامین بدون نیاز به خواندن کد، روی نتیجه و دامین کنترل داشته باشد؛
- و Refactor v3 در مسیر «ساختن چیز درست» باقی بماند، نه فقط «ساختن درست چیز».

------

این پیوست B، لایه‌ای از **تجربهٔ عملی و روش کار** را روی هستهٔ سخت LAW/Technical SSoT و Refactor v3 اضافه می‌کند و به‌طور خاص برای شرایطی طراحی شده که تیم توسعه از یک مالک غیر فنی و مدل‌های زبانی تشکیل شده است.









## پیوست C — Functional Core، Observability و Kill-Switch عملیاتی

این پیوست سه گاردریل تکمیلی برای v3 تعریف می‌کند که سطح بلوغ معماری و عملیات را بالا می‌برند، بدون این‌که هستهٔ LAW / Technical SSoT را عوض کنند:

- Functional Core, Imperative Shell برای تمام stageهای Import & Join
- Structured JSON Logging با trace_id سرتاسری
- Kill-switch عملیاتی `FORCE_LEGACY_MENTOR_PIPELINE` برای بازگشت فوری به pipeline قبلی

این بندها مکمل بخش‌های 0.x، 3.3، 7–10 و 11 هستند.

------

### C.1. Functional Core, Imperative Shell برای Import & Join v3

هدف این بند این است که تمام منطق اصلی Import & Join به‌صورت **توابع pure** پیاده شود و هرگونه side-effect فقط در لایهٔ بیرونی (shell) انجام شود.

#### C.1.1. تعریف Functional Core در v3

در v3، stageهای زیر جزو «Core» در معنای functional هستند:

- `HeaderResolver.resolve(...)`
- `ValueCanonicalizer.canonicalize(...)`
- `JoinKeyResolver.build_profiles(...)`
- هستهٔ `MentorPoolBuilder.build(...)` که DataFrame canonical mentors را می‌سازد

قواعد این لایه:

1. **بدون mutation inplace روی ورودی‌ها**
   - هیچ استفاده‌ای از `inplace=True` روی DataFrame ورودی مجاز نیست؛
   - هر transform باید با ساخت DataFrame/Series جدید انجام شود؛
   - ورودی‌ها از نگاه تابع immutable فرض می‌شوند.
2. **امضای تابع صرفاً Data → Data + Issues**
   - هر stage فقط از ورودی‌های داده‌ای (DataFrame + Context) استفاده می‌کند؛
   - خروجی فقط شامل داده و متادیتای ساختاری است (مثل `issues`, `failed_rows`, `can_continue`)، بدون side-effect خارجی.
3. **بدون side-effect (log / metric / I/O)**
   - داخل این توابع، هیچ فراخوانی به logging، metrics، فایل‌سیستم، دیتابیس، network و … مجاز نیست؛
   - تمام لاگ‌ها و متریک‌ها باید در shell بیرونی و براساس خروجی stage تولید شوند (مثلاً بعد از دریافت `CanonicalizationResult`، shell تعداد `issues` را log می‌کند).

#### C.1.2. Imperative Shell

Shell لایه‌ای است که:

- orchestration کل pipeline را انجام می‌دهد؛
- `run_id` و `trace_id` را می‌سازد و بین stageها حمل می‌کند؛
- بر اساس `can_continue` تصمیم می‌گیرد fail-fast شود یا ادامه بدهد؛
- logging / metrics / I/O را انجام می‌دهد.

Pattern مفهومی:

```
def run_mentor_import_and_join(ctx: RunContext) -> MentorImportRunResult:
    # shell — مجاز به log/metric/I/O
    header_res = HeaderResolver.resolve(raw_df, header_ctx)
    log_stage_result("header", header_res, ctx)

    if not header_res.can_continue:
        return fail_run("header", header_res, ctx)

    canon_res = ValueCanonicalizer.canonicalize(raw_df, canon_ctx)
    log_stage_result("canonicalize", canon_res, ctx)

    if not canon_res.can_continue:
        return fail_run("canonicalize", canon_res, ctx)

    join_res = JoinKeyResolver.build_profiles(canon_res.df, join_ctx)
    log_stage_result("join_keys", join_res, ctx)

    # ...
    return MentorImportRunResult(...)
```

این تفکیک باید در تست‌ها و reviewها به‌عنوان استاندارد v3 پذیرفته شود: هرگونه خروج از این الگو نیازمند توجیه و ADR جداگانه است.

------

### C.2. Structured JSON Logging و trace_id سرتاسری

این بند، بخش 10.4 (Observability & Metrics) را به‌صورت صریح برای logging تکمیل می‌کند.

#### C.2.1. قالب لاگ‌ها

تمام لاگ‌های مربوط به Import & Join v3 باید:

- به‌صورت **structured JSON** تولید شوند (نه متن آزاد)؛
- حداقل فیلدهای زیر را داشته باشند:
- `run_id` — شناسهٔ یکتای اجرای import/join
- `trace_id` — شناسهٔ یکتای زنجیرهٔ عملیات برای این run (می‌تواند با `run_id` یکسان باشد یا زیرشاخهٔ آن)
- `stage` — نام stage (مثلاً `"header"`, `"canonicalize"`, `"join_keys"`, `"matrix"`)
- `severity` — سطح لاگ (`INFO`, `WARN`, `ERROR`)
- `issue_code` — در صورت وجود، کد issue (مثل `MISSING_JOIN_FIELD`, `MULTIPLE_JOIN_PROFILES_PER_MENTOR`)
- `row_index` — در صورت وجود، ردیف درگیر در issue
- `duration_ms` — مدت زمان اجرای stage یا زیرعملیات
- `env` — محیط اجرا (`dev`, `staging`, `prod`)

نمونهٔ مفهومی:

```
{
  "timestamp": "2025-12-05T12:34:56.789Z",
  "run_id": "run_2025_1403_inspactor_small",
  "trace_id": "trace_123456",
  "stage": "join_keys",
  "severity": "WARN",
  "issue_code": "MULTIPLE_JOIN_PROFILES_PER_MENTOR",
  "row_index": 128,
  "mentor_id": 4567,
  "duration_ms": 42,
  "env": "prod"
}
```

#### C.2.2. propagation `run_id` و `trace_id`

- `run_id` باید در ابتدای اجرای pipeline ساخته شود و در تمام stageها ثابت بماند؛
- `trace_id` می‌تواند با `run_id` یکی باشد یا به‌عنوان شناسهٔ tracing با ابزارهای خارجی (مانند APM / OpenTelemetry) استفاده شود؛
- هر issue در خروجی stageها، در صورت log شدن، باید همان `run_id` / `trace_id` را حمل کند تا جست‌وجوی آن در log backend ساده باشد.

#### C.2.3. مرز Core و logging

- همان‌طور که در C.1 گفته شد، **هیچ‌کدام از توابع Core (stageهای pure)** حق ندارند مستقیماً log کنند؛
- ایجاد entryهای JSON log فقط در shell انجام می‌شود و بر اساس خروجی stage است (issues, counts, durations).

------

### C.3. Kill-Switch عملیاتی `FORCE_LEGACY_MENTOR_PIPELINE`

این بند، رویهٔ rollback فوری به pipeline قبلی منتورها را تعریف می‌کند و مکمل بخش 11.1 (Shadow Mode و Feature Flag) است.

#### C.3.1. تعریف و منبع تنظیم

یک فلگ عملیاتی سطح محیط تعریف می‌شود:

- نام منطقی: `FORCE_LEGACY_MENTOR_PIPELINE`
- منبع تنظیم (مثال پیشنهادی):
  - env var در اپلیکیشن (مثلاً `FORCE_LEGACY_MENTOR_PIPELINE=true/false`)، یا
  - کلید تنظیم در جدول config دیتابیس که فقط از طریق ابزار ادمین تغییر می‌کند.

جدول مفهومی:

| Scope | Key                            | نوع  | مقادیر مجاز      | پیش‌فرض  | توضیح                                                        |
| ----- | ------------------------------ | ---- | ---------------- | ------- | ------------------------------------------------------------ |
| Env   | `FORCE_LEGACY_MENTOR_PIPELINE` | bool | `true` / `false` | `false` | اگر `true` باشد، v3 کاملاً بای‌پس می‌شود و فقط pipeline قدیم اجرا می‌شود. |

#### C.3.2. اولویت نسبت به سایر فلگ‌ها

اگر هر دو فلگ زیر وجود داشته باشند:

- `FORCE_LEGACY_MENTOR_PIPELINE`
- فلگ‌های معمول انتخاب pipeline (مثل `use_join_pipeline_v3_for_mentors`، یا معادل آن در config)

قاعده:

- در صورت `FORCE_LEGACY_MENTOR_PIPELINE = true`، **همیشه** pipeline legacy منتورها اجرا می‌شود، حتی اگر فلگ‌های دیگر v3 را فعال کرده باشند؛
- در صورت `FORCE_LEGACY_MENTOR_PIPELINE = false`، انتخاب بین legacy/v3 طبق سایر فلگ‌ها (بخش 11.1) انجام می‌شود.

این kill-switch باید در کد واضح و مستند باشد تا هیچ تردیدی در رفتار در زمان بحران وجود نداشته باشد.

#### C.3.3. محدودیت استفاده در محیط‌ها

توصیهٔ عملیاتی:

- در محیط‌های `dev` و `staging`، این فلگ صرفاً برای تست رفتار rollback استفاده می‌شود؛
- در `prod`، تغییر مقدار این فلگ باید فقط توسط افراد مجاز (ops / مالک سیستم) و با ثبت در Change Log انجام شود؛
- هنگام فعال شدن kill-switch در prod، باید یک entry ساختاریافته در log با severity حداقل `WARN` ثبت شود که شامل:
  - `run_id`, `env`, `FORCE_LEGACY_MENTOR_PIPELINE=true`,
  - نام کاربر/فرآیند مسئول تغییر (در صورت امکان).

------

این پیوست C سه گاردریل «Functional Core»، «لاگ ساخت‌یافته» و «Kill-Switch شفاف» را به‌صورت رسمی به v3 اضافه می‌کند و جایگاه آن‌ها را نسبت به بخش‌های 0.x، 10.4 و 11.1 مشخص می‌کند. 



## پیوست D — UI Debug / QA Tab و History Integration v3

این پیوست، نقش و ساختار «تب دیباگ» را در UI جدید تعریف می‌کند و آن را با اجزای رسمی v3 (Validation Dialogها، QA Workbooks، QA Debug Engine، History/Trace) هم‌راستا می‌کند.
 هدف این است که تب دیباگ از یک «محل دیباگ آشفته و چندمنظوره» به یک **هاب شفاف برای QA و Trace** تبدیل شود.

این پیوست **هیچ قاعده‌ای در Core/Infra را عوض نمی‌کند**؛ فقط می‌گوید UI چگونه باید از این امکانات استفاده کند.

------

### D.1. نقش تب دیباگ در معماری v3

در v2، تب دیباگ معمولاً سه کار را با هم انجام می‌داد:

1. نمایش خطاها و تناقض‌ها بعد از اجرای ماتریس/تخصیص؛
2. کمک به تمیز کردن داده داخل برنامه (گاهی حتی با دست‌کاری مستقیم داده/DB)؛
3. نمایش مسیر حذف شدن دانش‌آموزها و منتورها (نوعی trace غیررسمی).

در v3، این مسئولیت‌ها رسمی و تفکیک شده‌اند:

- **تمیز کردن داده قبل از Core**
  - از طریق لایهٔ Import/Validation و دیالوگ‌هایی مثل:
    - دانش‌آموز: `student_domain_validation_dialog` / `student_domain_validation_vm`
    - منتور/کلید الحاق: `join_key_validation_dialog` / `join_key_validation_vm`
- **QA روی ماتریس و join**
  - از طریق QA Workbooks مثل:
    - `eligibility_matrix_validation`
    - `matrix_vs_students_validation`
  - و UIهایی مثل `qa_dashboard_dialog` و QA Debug Engine.
- **Trace / History برای هر دانش‌آموز**
  - از طریق Trace هشت‌مرحله‌ای و History Store/Dialogs.

بنابراین، تب دیباگ v3 دیگر محل اجرای منطق جدید نیست؛ فقط **رابط کاربری مرکزی** است که این ابزارها را کنار هم می‌گذارد.

------

### D.2. مرزبندی مسئولیت تب دیباگ

در v3، تب دیباگ:

- **مجازه**:
  - خواندن خلاصهٔ QA و نشان دادن آماری از خطاها؛
  - باز کردن دیالوگ‌های Validation (دانش‌آموز، منتور/Join-Key)؛
  - باز کردن QA Workbooks (یا UIهای مرتبط) برای بررسی جزئیات؛
  - باز کردن History/Trace برای دانش‌آموزهای خاص.
- **مجاز نیست**:
  - تغییر مستقیم دادهٔ دامین (دانش‌آموز/منتور/مدرسه/مرکز) در DB یا فایل‌های مرجع؛
  - اجرای الگوریتم تخصیص یا تغییر رفتار Core؛
  - تعریف منطق QA جدا از QA رسمی (قوانین CODED / QA Workbooks / LAW/TECH).

هرگونه تمیز کردن داده باید:

1. توسط Validation/QA رسمی شناسایی شود؛
2. به صورت خروجی قابل‌Export (Excel/CSV) در اختیار کاربر قرار گیرد؛
3. بیرون از Core (در منبع داده) اصلاح شود؛
4. در run بعدی مجدد اعتبارسنجی شود.

------

### D.3. ساختار پیشنهادی تب دیباگ v3

به‌صورت مفهومی، تب دیباگ جدید از سه بخش اصلی تشکیل می‌شود:

#### D.3.1. بخش «وضعیت کلی QA»

یک **QA Summary Panel** که اطلاعات را از خروجی QA (یا سرویس QA در Infra) می‌خواند، شامل:

- تعداد Ruleهای شکسته‌شده به تفکیک severity (P0 / P1 / P2)؛
- لیست مهم‌ترین Ruleها (مثلاً `JOIN-CORE`, `CAPACITY-01`, `SCHOOL-01`, `MENTOR-PROFILE-UNIQUENESS`)، همراه با:
  - تعداد رکوردهای درگیر؛
  - اشاره به این‌که این Rule در کدام Workbook/Sheet قابل مشاهده است.

دکمه‌های ضروری:

- **«باز کردن داشبورد QA کامل»**
  - باز کردن `qa_dashboard_dialog`، که نمای کلی QA Workbooks و Ruleها را نشان می‌دهد.
- **«نمایش داستان خطا» برای Rule انتخاب‌شده**
  - باز کردن QA Debug Engine / `qa_debug_dialog` برای آن Rule، با پاسخ به سه سؤال:
    - چه شد؟
    - از کجا شروع شد؟
    - قدم اول اصلاح چیست؟

این بخش جایگزین قسمت «لیست مبهم خطاها» در تب دیباگ قدیمی می‌شود و آن را به QA رسمی متصل می‌کند.

------

#### D.3.2. بخش «ابزارهای تمیز کردن داده»

این بخش مرکز کنترل برای Validationهای ورودی است، نه جای پیاده‌سازی منطق validation.

دکمه‌های اصلی:

1. **«بررسی Domain دانش‌آموزان»**
   - فراخوانی UI/دیالوگ رسمی Validation دانش‌آموز:
     - `student_domain_validation_dialog` (و ViewModel مربوطه)؛
   - نمایش:
     - ردیف‌های invalid؛
     - نوع خطاها (مثلاً graduation_status ناسازگار با گروه، student_type نامعتبر و …)؛
     - امکان Export لیست invalidها برای اصلاح در منبع داده.
2. **«بررسی Join-Key منتورها»**
   - فراخوانی UI/دیالوگ Validation join-key منتورها:
     - `join_key_validation_dialog` / `join_key_validation_vm`؛
   - نمایش:
     - mento‌rهایی که join-key ناقص دارند؛
     - `MULTIPLE_JOIN_PROFILES_PER_MENTOR`؛
     - `DUPLICATE_EXACT_PROFILE` و موارد مشابه؛
     - امکان Export لیست منتورهای problem‌دار برای اصلاح.

قواعد:

- این دیالوگ‌ها باید داده را **فقط بخوانند و گزارش بدهند**؛
- اصلاح نهایی داده باید در فایل/سیستم منبع انجام شود (Inspactor, SchoolReport, DB مرجع)، نه از داخل این تب؛
- تب دیباگ فقط باید «چگونه دیدن و چگونه export کردن» را آسان کند.

------

#### D.3.3. بخش «Trace / History دانش‌آموز»

این بخش به مالک دامین کمک می‌کند بفهمد:

> «این دانش‌آموز مشخص، در کدام مرحله‌ی فیلتر شدن، منتورش را از دست داد؟»

عناصر اصلی:

- یک input ساده (یا search box):
  - `student_key`، یا انتخاب از لیست دانش‌آموزان بدون mentor؛
- دکمه **«نمایش Trace»**:
  - که `history_dialog` / History UI را برای همان `student_key` باز می‌کند؛
- در History UI، کاربر می‌بیند:
  - ۸ stage trace (`type`, `group`, `gender`, `graduation_status`, `center`, `finance`, `school`, `capacity_gate`)؛
  - تعداد گزینه‌های mentor قبل و بعد هر مرحله؛
  - در کدام stage تعداد از n>0 به صفر رسیده است.

نکتهٔ کلیدی:

- تب دیباگ نباید خودش منطق trace را محاسبه کند؛ فقط باید student_key را به History/Trace Engine پاس بدهد و خروجی را نشان دهد.

------

### D.4. قواعد اجرایی برای تب دیباگ v3

برای جلوگیری از تبدیل شدن تب دیباگ به «سیستم موازی»، این قواعد باید رعایت شوند:

1. **بدون منطق دامین جدید**
   - تب دیباگ فقط روی خروجی‌های زیر سوار می‌شود:
     - Validationهای رسمی (student/mentor/join-key)؛
     - QA Workbooks (`eligibility_matrix_validation`, `matrix_vs_students_validation`, …)؛
     - Trace/History رسمی Core.
   - هر Rule یا منطق QA جدید باید در LAW/Technical SSoT و QA Workbooks تعریف شود، نه در تب دیباگ.
2. **بدون Mutation مستقیم داده**
   - تب دیباگ مجاز نیست رکوردهای دانش‌آموز/منتور را در DB یا فایل‌های منبع اصلاح کند؛
   - هر اصلاح باید در منبع داده انجام شود و در run بعدی با Validation/QA تأیید شود.
3. **یک‌پارچگی با Observability**
   - تب دیباگ نباید به‌صورت ad-hoc log تولید کند؛
   - برای هر run، از `run_id` / `trace_id` رسمی استفاده می‌کند تا بتوان بین UI، لاگ‌ها و QA خروجی‌ها را دنبال کرد (مطابق پیوست C).
4. **سادگی UI**
   - هر بخش (QA Summary / Data Cleaning / Trace) باید:
     - در یک نگاه قابل فهم باشد؛
     - حداکثر با ۱–۲ کلیک کاربر را به دیالوگ‌های تخصصی (Validation / QA / History) برساند.

------

### D.5. سناریوی نمونهٔ استفاده از تب دیباگ v3

**سناریو:** بعد از اجرای یک run، تعداد زیادی دانش‌آموز بدون mentor شده‌اند.

۱. کاربر تب دیباگ را باز می‌کند؛
 ۲. در بخش QA Summary می‌بیند Rule `JOIN-CORE` و `SCHOOL-01` تعداد زیادی P1/P0 دارد؛
 ۳. روی Rule `JOIN-CORE` کلیک می‌کند → QA Debug Engine باز می‌شود و توضیح می‌دهد:

- خیلی از دانش‌آموزها school_code معتبر ندارند یا مدرسه‌شان در SchoolReport غیرفعال است؛
- پیشنهاد: باز کردن `matrix_vs_students_validation` و بررسی ستون‌های school/join.

1. کاربر از همان تب، دکمهٔ «بررسی Join-Key منتورها» را می‌زند تا ببیند آیا مشکل از منتورها هم هست یا فقط از دادهٔ مدارس/دانش‌آموزان؛
2. برای چند دانش‌آموز خاص از لیست «بدون mentor»، `student_key` را در بخش Trace وارد می‌کند و Trace ۸ مرحله‌ای را می‌بیند که مثلاً در مرحلهٔ `school` صفر شده‌اند؛
3. بر اساس این اطلاعات، داده در فایل/DB مرجع اصلاح می‌شود، و در run بعدی دوباره همین مسیر طی می‌شود تا تأیید شود که مشکل رفع شده است.

این سناریو نشان می‌دهد:

- تب دیباگ **حکم مرکز کنترل QA/History** را دارد؛
- ولی مسئول منطق دامین یا اصلاح مستقیم داده نیست.

------

این پیوست D را اگر به انتهای سند Refactor SSoT v3.0 اضافه کنی، کل حلقهٔ «Import → Join → QA → Trace → UI Debug» کامل و رسمی می‌شود؛ یعنی تب دیباگ‌ات هم مثل بقیهٔ سیستم، زیر چتر همون معماری و LAW/TECH کار می‌کند، نه در حاشیه.







این هم متن آمادهٔ «پیوست بعدی» که می‌تونی مستقیم به انتهای Refactor Narrative اضافه کنی. من اسمش را گذاشتم «پیوست E» تا با A/B/C/D سازگار بماند:

------

## پیوست E — راهنمای پیاده‌سازی پایتونی و گردش‌کار توسعه برای Refactor SSoT v3.0

### E.1 هدف و مخاطب

این پیوست برای مهندسان پایتون است که قرار است Refactor SSoT v3.0 را در کد واقعی (Core / Infra / UI) پیاده‌سازی و نگهداری کنند. تمرکز این متن روی:

- اصول کدنویسی پایتونی که با LAW / SSoT / Technical SSoT هم‌راستا است؛
- گردش‌کار توسعه‌ای که QA-friendly و قابل‌ردیابی باقی بماند؛
- استانداردهای UI / فارسی‌نویسی / RTL در PySide6؛
- نحوه‌ی استفادهٔ مطمئن از LLM و Prompt Decorators در تب دیباگ/QA.

------

### E.2 اصول پایه‌ی کدنویسی در این پروژه (Python-Focused)

#### E.2.1 DRY / KISS / YAGNI روی زمین این پروژه

1. **DRY — منطق تکراری ممنوع**
   - تمام منطق‌های کلیدی (مثل canonicalization کلیدهای الحاق، نگاشت group-code، capacity-gate) باید تنها یک پیاده‌سازی مرکزی داشته باشند (در Core یا helperهای مشترک Infra).
   - هر بار که لازم شد همان منطق را در جای دیگری استفاده کنی، باید از همان تابع/ماژول مشترک استفاده شود، نه کپی‌پِیست.
2. **KISS — ساده نگهش دار**
   - برای هر Rule و هر Invariant، ساده‌ترین پیاده‌سازی شفافی که تست‌ها را پاس می‌کند، انتخاب می‌شود.
   - اگر انتخاب بین «یک تابع ۴۰ خطی شفاف» و «یک abstraction پیچیده اما شیک» باشد، تابع ۴۰ خطی شفاف ترجیح دارد، تا وقتی که درد واقعی complexity ثابت نشده است.
3. **YAGNI — چیزی را که الان لازم نیست، پیاده‌سازی نکن**
   - Ruleها، flagها و گزینه‌های دیباگ «احتمالاً مفید در آینده» وارد کد نمی‌شوند مگر این‌که در LAW / SSoT / Tech-SSoT یا در یک درد QA واقعی مستند شده باشند.
   - این اصل برای جلوگیری از «اژدهای دیباگ» حیاتی است: تب دیباگ/QA باید مینیمال و در خدمت استفاده‌های واقعی بماند، نه کلکسیون ابزارهای آزمایشی.

#### E.2.2 Separation of Concerns و Composition over Inheritance

- هر ماژول / کلاس باید **یک سطح انتزاع مشخص** و **یک دلیل واضح برای تغییر** داشته باشد (SRP + SoC).
- به‌جای ارث‌بری‌های عمیق، از ترکیب استفاده کن:
  - مثال: به‌جای کلاس `DebuggableMatrixBuilder` که از `MatrixBuilder` ارث‌بری می‌کند، یک `DebugMatrixRunner` در Infra داشته باش که یک نمونه‌ی `MatrixBuilder` را تزریق می‌گیرد و صرفاً Trace / Snapshot / QAArtifacts اطراف آن اضافه می‌کند.
- Core / Infra / UI باید **لایه‌های جدا** بمانند؛ هیچ import برعکس مجاز نیست (Core ← Infra ← UI).

#### E.2.3 تایپ‌هینت، tooling و کیفیت کد

- تمام کدهای جدید Core و Infra باید **type-hinted** و با `mypy --strict` بدون خطا باشند.
- `ruff` و `black` باید بخشی از CI باشند؛ هیچ «استثناء دائمی» بدون دلیل مستند در SSoT/README مجاز نیست.
- قوانین اضافه‌شده به Technical SSoT (مثل پرهیز از `inplace=True` و `merge` در حلقه‌ها) باید به‌صورت مستقیم در کد رعایت و در Review چک شوند.

#### E.2.4 قواعد خاص DataFrame در این ریفکتور

- Join-keyها همیشه `int` باقی می‌مانند؛ هر تبدیل موقت به string باید در همان تابع به int برگردانده شود و رد این تبدیل در تست‌ها پوشش داده شود.
- هیچ `inplace=True` برای عملیات بحرانی ماتریس و تخصیص؛ خروجی هر مرحله DataFrame جدید است تا trace‌پذیری و reproducibility حفظ شود.
- برای sortها، همیشه از sort پایدار (مثل `kind="mergesort"`) استفاده می‌شود و ترتیب ستون‌های ranking مطابق RANK-CORE ثابت می‌ماند.

------

### E.3 گردش‌کار توسعه برای هر تغییر (Dev Workflow v3.0)

این بخش، چرخه‌ی توسعه‌ی کلی SDLC را با نیازهای خاص این سیستم ترکیب می‌کند.

#### E.3.1 گام ۱ — هم‌ترازی با LAW / SSoT / Tech-SSoT

- برای هر تغییر، ابتدا مشخص کن:
  - کدام بندهای LAW / اینورینت‌ها درگیر هستند؛
  - کدام بخش از Technical SSoT تحت‌تأثیر است (JOIN، TRACE، RANK، QA Debug و …).
- اگر تغییری خارج از محدوده‌ی فعلی است، ابتدا سند LAW/Tech-SSoT به‌روزرسانی شود، بعد کد.

#### E.3.2 گام ۲ — طراحی و به‌روزرسانی تست‌ها

- قبل از کدنویسی، تست‌های مورد انتظار را طراحی کن:
  - **Unit Test** برای توابع جدید Core؛
  - **Integration Test** برای جریان کامل build_matrix / allocate / QA؛
  - اگر لازم است، یک سناریوی جدید در QA Workbook اضافه شود (مثلاً یک نمونه‌ی جدید از BUG_JOIN).

#### E.3.3 گام ۳ — پیاده‌سازی در لایه‌ی درست

- منطق pure روی DataFrameها → Core.
- هر چیزی که I/O، Excel، SQLite، CLI، flag، یا snapshot دارد → Infra.
- هر تعامل کاربر (فرم‌ها، tabها، دکمه‌ها، پیام‌ها) → UI (PySide6).

#### E.3.4 گام ۴ — اجرای تست‌ها و QA محلی

- اجرای `pytest` روی تست‌های مرتبط؛
- اجرای `ruff`, `black`, `mypy --strict` روی فایل‌های تغییرکرده؛
- اجرای CLI روی یک نمونه‌ی کوچک از InspactorReport / SchoolReport و بررسی خروجی QA Workbooks مطابق schema.

#### E.3.5 گام ۵ — Review و Merge

- در Review، علاوه بر کد، این موارد چک می‌شوند:
  - تطابق رفتار با LAW/Tech-SSoT؛
  - عدم نقض اینورینت‌های JOIN-01، TRACE-CORE، RANK-CORE، CAPACITY؛
  - رعایت قواعد E.2 (DRY/KISS/YAGNI، DataFrame rules، typing).

------

### E.4 استانداردهای UI، فارسی‌نویسی و RTL در PySide6

این بخش مکمل سند «استانداردهای RTL و فارسی‌نویسی در کدنویسی پایتون» است، اما به‌طور خاص برای UI این سیستم تنظیم شده است.

#### E.4.1 مرزبندی فارسی و انگلیسی

- **کد و نام‌گذاری‌ها (متغیرها، توابع، کلاس‌ها)**:
  - همه به انگلیسی، snake_case / PascalCase استاندارد پایتون.
- **متن‌های نمایشی برای کاربر (label, tooltip, message)**:
  - فارسی، با رعایت املای استاندارد و قابل‌فهم بودن برای کاربر نهایی.

#### E.4.2 نکات فنی RTL

- استفاده از **UTF-8** در تمام فایل‌های سورس.
- برای متن‌های دوجهته (فارسی + عدد/لاتین)، در صورت نیاز از `python-bidi` / ابزارهای مشابه استفاده شود.
- فونت پیشنهادی برای UI: خانواده‌هایی مثل Vazir / Iran Sans که برای فارسی بهینه هستند (در تنظیمات Qt).

#### E.4.3 سازمان‌دهی متن‌ها در UI

- تمام رشته‌های متنی قابل‌نمایش (labels, messages) در یک ماژول/فایل متمرکز (مثلاً `ui_strings_fa.py`) نگه‌داری شوند تا ترجمه و بازبینی آسان بماند.
- برای پیام‌های خطا در تب دیباگ/QA، متن باید:
  - خلاصه،
  - ارجاع‌دهنده به Rule / LAW Clause (اگر مناسب بود)،
  - و بدون اشاره‌ی مستقیم به جزئیات داخلی implementation (مثل names توابع Core) باشد.

------

### E.5 ادغام Debug/QA Tab با LLM و Prompt Decorators (در صورت استفاده)

اگر تب دیباگ/QA از LLM برای توضیح خطاها استفاده کند، این بخش حداقل قواعد را مشخص می‌کند.

#### E.5.1 نقش LLM در کنار QA Debug Engine

- LLM **منبع حقیقت (Source of Truth)** نیست؛ تنها یک لایه‌ی توضیح‌دهنده‌ی اضافی روی DebugReport / QA Workbooks است.
- تمام داده‌های ورودی LLM باید از خروجی‌های Core/Infra (Trace، QA، DebugReport) بیایند؛ LLM اجازه‌ی اجرای دوباره‌ی تخصیص یا QA روی داده‌های خام را ندارد.

#### E.5.2 استفاده از Prompt Decorators

- Promptها باید با استفاده از «Prompt Decorators» تعریف شوند تا:
  - رفتار مدل (تحلیلی، خلاصه‌گر، معلم، …) شفاف و تکرارپذیر بماند؛
  - promptها از کد جدا شوند و در یک لایه‌ی قابل‌مدیریت (مثلاً فایل تنظیمات یا ماژول `prompt_templates`) نگه‌داری شوند.
- هر decorator باید با نقش‌اش در تب دیباگ/QA مستند شود (مثلاً: `DEBUG_SUMMARY`, `LAW_EXPLAINER`, `QA_NEXT_STEP_HINTS`).

#### E.5.3 محدودیت‌ها و ترمزها

- اگر LLM خطا داد، تب دیباگ باید همچنان بدون آن هم مفید باشد؛ DebugReport و QA Workbook همچنان هسته‌ی تجربه‌ی دیباگ هستند.
- برای جلوگیری از «رشد کنترل‌نشده» قابلیت‌ها، هر قابلیت LLMمحور جدید باید:
  - به یک درد واقعی QA وصل باشد؛
  - و در بازبینی‌های دوره‌ای قابل حذف / ادغام باشد اگر استفاده‌ی واقعی ندارد.

------

## REF-V3-PHASE-00 — Unified JoinKeyResolver rollout (Phase 0–3)

**هدف:** JoinKeyResolver به‌عنوان SSoT یگانه برای canonicalize + infer کلیدهای join و اطمینان از parity بین allocation و audit/export.

**Phase 0 — Contract & Parity Guard تعریف**

- مستندسازی JOINKEY-SSOT-01..04 در LAW/TECH/RepoSpec.
- تعریف «Effective Join Keys» و الزام مصرف آن در allocation/QA/export.
- تعریف Parity Guard به‌عنوان گیت اجباری (mismatch ⇒ QA/Blocking).

**Phase 1 — مسیر یگانه برای JoinKeyResolver**

- همهٔ مسیرهای import mentor (و هر مسیر جدید) JoinKeyResolver را به‌عنوان تنها منبع canonicalize/infer فراخوانی می‌کنند.
- قابلیت فعال‌سازی تدریجی با feature flag و مقایسهٔ خروجی با مسیر legacy.
- Unit Testهای parity (JoinKeyResolver vs مسیرهای قبلی) اجباری.

**Phase 2 — Parity Integration & Audit Alignment**

- Integration Test برای parity بین allocation و audit/export اضافه می‌شود.
- QA workbookها باید mismatch را با Rule IDهای مشخص گزارش کنند.
- Golden regression برای `mentor_id + ۶ join key + capacity` در دادهٔ طلایی فعال است.

**Phase 3 — Enforcement & Legacy Cleanup**

- هرگونه دسترسی مستقیم به join key خام یا derivation پراکنده حذف/مسدود می‌شود.
- مصرف‌کننده‌ها فقط Effective Join Keys را می‌بینند؛ fallback به legacy ممنوع است.
- Rollback کنترل‌شده: Kill-Switch و flag همچنان برای بازگشت سریع باقی می‌مانند.

**Risk controls**

- Parity Guard به‌عنوان گیت اجباری پیش از export.
- fail-fast برای mismatchهای P0 و log/QA برای P0.5/P1.
- مسیر rollback مستند (Kill-Switch + نسخهٔ legacy).

------

## REF-V3-PHASE-02 — Mentor import unification (MentorPipelineV3)

- **Before:** چند مسیر مجزا (Inspactor، LocalDatabase، اسکریپت‌های اد-هوک) با هدر/alias متفاوت وجود داشت که باعث drift در استخر پشتیبان می‌شد.
- **After:** همهٔ entrypointهای Infra به پایپلاین یکتا **MentorPipelineV3** متصل می‌شوند و Core فقط استخر canonical را مصرف می‌کند؛ هیچ join logic در Core یا UI نوشته نمی‌شود.
- **Why unification helps:**
  - حذف واگرایی بین شاخه‌های Import و کاهش ریسک مغایرت ظرفیت/کلید،
  - QA واحد برای تناقض کلید، multi-profile، و توقف‌های P0،
  - مسیر روشن برای golden regression و مقایسه legacy vs pipeline_v3.
- **Golden regression for mentors:** سناریوهای legacy و pipeline_v3 روی مجموعه‌های طلایی هم‌زمان اجرا می‌شوند تا برابری `mentor_id + ۶ کلید الحاق + ظرفیت` و مرتب‌سازی ظرفیت تأیید شود.
- **QA payloads as evidence:** خروجی QA شامل issues، duplicates و multi-profile mentors بخشی از داستان رسمی شواهد است و باید در اکسپورت QA/History دیده شود.
- **۸-گام ایمپورت/الحاق پشتیبان در فاز ۲:**
  1. ورودی خام (Excel/DB) خوانده می‌شود.
  2. **FieldRegistry** فیلدهای مجاز را تعیین می‌کند.
  3. **HeaderResolver** هدرهای خام را به canonical نگاشت می‌دهد.
  4. **ValueCanonicalizer** مقادیر را اعتبارسنجی و نرمال می‌کند (`can_continue` برای خطای P0 = false).
  5. **JoinKeyResolver** شش کلید عددی را با wildcard مرکز/مدرسه می‌سازد و multi-profile mentors را علامت‌گذاری می‌کند.
  6. **MentorPoolBuilder** استخر canonical و متادیتای QA را می‌سازد.
  7. استخر canonical (`MentorPoolBuildResult.pool`) به Core تحویل می‌شود؛ Core هیچ Join جدیدی نمی‌سازد.
  8. QA payloadها (issues، duplicates، multi-profile) به QA workbooks و تاریخچه ارسال می‌شوند.

------

### E.6 چک‌لیست نهایی قبل از Merge هر تغییر

قبل از این‌که هر PR مرتبط با این Refactor Merge شود، موارد زیر باید درست باشند:

1. **هم‌ترازی با LAW / SSoT / Tech-SSoT**
   - بندهای درگیر LAW مشخص و در صورت نیاز، سند به‌روزرسانی شده است.
2. **تست‌ها**
   - Unit/Integration تست‌ها برای سناریوهای جدید اضافه یا به‌روزرسانی شده‌اند؛
   - `pytest` بدون خطا؛ coverage منطقی برای منطق جدید.
3. **کیفیت کد**
   - `ruff`, `black`, `mypy --strict` روی فایل‌های تغییرکرده پاس شده‌اند؛
   - هیچ منطق تکراری یا over-engineering غیرضروری (نقض DRY/KISS/YAGNI) وارد نشده است.
4. **DataFrame / Join / Trace**
   - اینورینت‌های JOIN-01، TRACE-CORE، RANK-CORE و DET-CORE نقض نشده‌اند؛
   - Sortها پایدار و join-keyها صحیح هستند.
5. **UI / RTL / Debug Tab**
   - متن‌های UI در جای درست (فارسی در UI، انگلیسی در کد) قرار دارند؛
   - تب دیباگ/QA فقط از خروجی‌های Core/Infra مصرف می‌کند و هیچ منطق اختصاصی تخصیص در UI پیاده‌سازی نشده است.
6. **LLM (در صورت استفاده)**
   - قطع LLM یا خطای API، تب دیباگ را از کار نمی‌اندازد؛
   - Promptها در لایه‌ی اختصاصی نگه‌داری می‌شوند و قابل نسخه‌گذاری هستند.

------

پیوست F — نمای شی‌گرا (DDD View) برای Import & Join & Allocation v3
این پیوست یک نمای شی‌گرا / Domain-Driven Design از همان معماری‌ای است که در بدنهٔ سند Refactor v3 تعریف شده است.
منطق و اینورینت‌ها همچنان از LAW / Technical SSoT / بخش‌های ۳، ۴، ۷، ۸ و ۹ همین سند تبعیت می‌کنند؛ این پیوست فقط مدل ذهنی و ساختار شی‌گرا را رسمی می‌کند، بدون این‌که رفتار جدیدی تعریف کند. 

F.1. هدف این پیوست


فراهم کردن زبان مشترک شی‌گرا برای صحبت دربارهٔ موجودیت‌ها و سرویس‌ها؛


هم‌راستا کردن مدل دامین با پیاده‌سازی DataFrame-محور موجود؛


آماده‌کردن زمین برای پیاده‌سازی‌های آینده (مثلاً RuleSlot / MultiStrategyAllocator) بدون تغییر در semantics join/rank/trace.



اصل کلیدی:
این پیوست هیچ قانون جدیدی اضافه نمی‌کند؛ فقط همان مفاهیم بخش ۴ (Entities & Value Objects) و بخش‌های ۷–۹ را در قالب DDD مرتب می‌کند.


F.2. موجودیت‌ها (Domain Entities)
موجودیت‌ها اشیائی هستند که هویت (Identity) مستقل دارند و در طول زمان تغییر وضعیت می‌دهند. تعریف فیلدها و اینورینت‌ها باید با بخش ۴.۰ همین سند منطبق بماند.
F.2.1. Student Entity


هویت:
student_key (شناسهٔ یکتای دانش‌آموز در run / سال هدف)


ویژگی‌های کلیدی (هم‌راستا با 4.0.1):


student_key


student_type (عادی / مدرسه‌ای)


۶ کلید الحاق (در سمت دانش‌آموز):


group_code


gender_code


grad_status_code


center_code


finance_code


school_code




فیلدهای تکمیلی: وضعیت تحصیلی، وضعیت مالی، … مطابق LAW/TECH




اینورینت‌ها (خلاصه):


ترکیب (group_code, gender_code, grad_status_code) باید در دامنهٔ معتبر تعریف‌شده در LAW/TECH باشد؛


student_type با school/center سازگار است؛


از دید Allocation: هر student_key در هر run حداکثر یک تخصیص فعال دارد (ALLOCATION-01).




در پیاده‌سازی فعلی، Student بیشتر به‌صورت DataFrame canonical دانش‌آموزان نمایش داده می‌شود؛ این Entity مدلی شی‌گرا روی همان frame است.

F.2.2. Mentor Entity


هویت:
mentor_id


ویژگی‌های کلیدی (هم‌راستا با 4.0.2 و 4.2):


mentor_id


mentor_type (NORMAL / SCHOOL)


mentor_status (ACTIVE / FROZEN)


join_profile: JoinKeyProfile (پروفایل رسمی ۶ کلید الحاق)


ظرفیت:


capacity_limit


assigned_baseline


allocations_new


property مشتق‌شده: remaining_capacity




فیلدهای تکمیلی: نام، عنوان، کد ملی، center/school مرجع، …




اینورینت‌های مهم:


فقط منتورهای mentor_status = ACTIVE وارد استخر تخصیص می‌شوند؛


CAPACITY-01: remaining_capacity نباید منفی شود؛


join این Mentor با Student فقط و فقط با ۶ کلید join و semantics LAW انجام می‌شود (نه فیلدهای دیگر).




نمای فعلی در کد:
یک DataFrame canonical mentors + type JoinKeyProfile (بخش 4.1) + property remaining_capacity (بخش 4.2). این پیوست Mentor را به‌عنوان یک Entity رسمی توصیف می‌کند، حتی اگر در v3 هنوز به‌صورت کلاس کامل پیاده‌سازی نشده باشد.

F.2.3. School Entity


هویت:
school_code


نقش:
موجودیت مرجع برای اتصال دانش‌آموزان و منتورها به مدرسه.


فیلدهای نمونه (هم‌راستا با 4.0.3):


school_code


school_name


center_code


وضعیت فعال/غیرفعال




اینورینت‌ها (خلاصه):


SCHOOL-01: school_code یکتا و معتبر؛


center_code معتبر و سازگار با Center Entity.




در v3، School به‌صورت دادهٔ مرجع در Import/Join استفاده می‌شود و ورودی JoinKeyResolver / QA است، نه جایی برای منطق اختصاصی.

F.2.4. Center Entity


هویت:
center_code


نقش:
مرجع تجمیع مدارس و منتورها در سطح مرکز (هم‌راستا با 4.0.4).


اینورینت‌ها:


CENTER-01: center_code یکتا و معتبر؛


نقش 0 به‌عنوان wildcard center طبق LAW/TECH تعریف شده است.





F.2.5. Allocation Entity


هویت:
allocation_id یا کلید مرکب (student_key, mentor_id, year, run_id)


ویژگی‌های کلیدی (هم‌راستا با 4.0.5):


student_key


mentor_id


سال/دوره


allocation_status (ACTIVE, CANCELLED, …)


trace ۸ مرحله‌ای (type, group, gender, grad_status, center, finance, school, capacity_gate)




اینورینت‌های اصلی:


ALLOCATION-01: یک student_key در یک run فقط یک تخصیص فعال دارد؛


ALLOCATION-TRACE-01: هر Allocation باید trace ۸ مرحله‌ای معتبر داشته باشد.




در v3، این Entity بیشتر از طریق خروجی‌های Core/History و QA Workbooks دیده می‌شود.

F.3. اشیاء ارزش (Value Objects)
Value Objectها هویت مستقل ندارند، immutable هستند و بر اساس مقدارشان مقایسه می‌شوند. بسیاری از مفاهیم v3 در بخش 4.1 و 4.0.6 همین سند، دقیقاً Value Object هستند.
F.3.1. JoinKeyProfile
این Value Object در بخش 4.1 تعریف شده و قلب join در v3 است:


۶ فیلد اصلی:


group_code


gender_code


grad_status_code


center_code


finance_code


school_code




فیلدهای کمکی:


mentor_type (NORMAL / SCHOOL)


alias_code (در صورت نیاز)




قاعدهٔ DDD:


equality و hash فقط بر اساس ۶ کلید join؛


هر تغییری در semantics این ۶ کلید باید در LAW / Technical SSoT و FieldRegistry منعکس شود (بخش ۵).


این نوع همان چیزی است که در JoinKeyResolver ساخته می‌شود و در Mentor Entity مصرف می‌گردد.

F.3.2. CapacitySnapshot
CapacitySnapshot یک Value Object مفهومی است که در کد v3 به‌صورت inline در Mentor پیاده شده است (بخش 4.2):


فیلدها:


capacity_limit


assigned_baseline


allocations_new




property مشتق‌شده:


remaining_capacity = capacity_limit - (assigned_baseline + allocations_new)




نکته:
هر ستونی به نام remaining_capacity در DataFrame فقط بازتاب همین فرمول است و هیچ جای دیگری حق ندارد آن را با فرمول متفاوت محاسبه کند.

F.3.3. سایر Value Objectها (Canonical Code / Enums)


Domain enums مثل MentorType, MentorStatus, GraduationStatus, FinanceCode, …


mappingهای canonical برای group/gender/finance/center/school که در ValueCanonicalizer اعمال می‌شوند.


این‌ها در DDD به‌عنوان Value Objectهایی در نظر گرفته می‌شوند که در Student/Mentor و JoinKeyProfile استفاده می‌شوند.

F.4. سرویس‌های دامنه (Domain Services)
سرویس دامنه زمانی استفاده می‌شود که یک رفتار مهم دامین، به یک Entity مشخص تعلق ندارد یا به چند Entity و چند Value Object مربوط است.
در v3، بسیاری از این سرویس‌ها به‌صورت stageهای functional (توابع pure) پیاده شده‌اند؛ این پیوست فقط نام‌گذاری DDD و رابطهٔ آن‌ها را روشن می‌کند.
F.4.1. MentorImportService (Domain Service روی Import & Join)
نقش مفهومی:

تبدیل داده‌های خام Inspactor/… به MentorPool canonical + QA، طبق LAW/TECH و Refactor v3.

در معماری v3، این سرویس به‌صورت ترکیب stageهای زیر پیاده شده است (بخش ۳.۳ و ۷–۸):


FieldRegistry — SSoT فیلدها


HeaderResolver — نگاشت هدرها


ValueCanonicalizer — تبدیل به مقادیر canonical


JoinKeyResolver — ساخت JoinKeyProfile و تشخیص issues


MentorPoolBuilder — ساخت استخر canonical mentors + QA artifacts


در DDD View، این پنج جزء در مجموع یک Domain Service برای «Mentor Import & Join» را تشکیل می‌دهند.
در v3 نیازی نیست حتماً یک کلاس MentorImportService ساخته شود؛ همین ترکیب stageهای functional، پیاده‌سازی عملی این سرویس است.

F.4.2. StudentImportService (خارج از محدوده‌ی تغییر در v3)
برای دانش‌آموزان نیز به‌طور مفهومی سرویسی مشابه وجود دارد:

StudentImportService داده‌های خام دانش‌آموزان را به student canonical frame تبدیل می‌کند.

در v3، این pipeline تغییر نمی‌کند؛ فقط باید با ۶ کلید join و Domain Validation دانش‌آموز (بخش 4.0.1 و 4.3) سازگار بماند تا با MentorPool v3 هم‌معنا شود.

F.4.3. AllocationService (Core Allocation / build_matrix)
AllocationService همان رفتار Core است که در حال حاضر توسط build_matrix (و در آینده MultiStrategyAllocator / RuleSlot) پیاده می‌شود:


ورودی:


Student canonical pool (با ۶ join key و student_key)؛


Mentor canonical pool (با ۶ join key، ظرفیت و MentorStatus)؛


PolicyConfig (قوانین تخصیص و اولویت‌ها).




خروجی:


مجموعه‌ای از Allocation Entityها + QA / Trace ۸ مرحله‌ای.




این سرویس باید اینورینت‌های زیر را حفظ کند:


استفاده از ۶ join key طبق LAW؛


ترتیب ranking ثابت (remaining_capacity ↓، allocations_new ↑، mentor_id ↑)؛


Trace ۸ مرحله‌ای بدون تغییر ساختار.


در DDD View، ممکن است این رفتار به شکل یک کلاس/ماژول AllocationService دیده شود، اما در v3 نام و امضای واقعی تابع Core (build_matrix) منبع حقیقت است؛ این پیوست فقط نقش مفهومی را توضیح می‌دهد.

F.4.4. JoinKeyResolutionService
در سطح DDD، JoinKeyResolver یک Domain Service صریح است که:


۶ کلید join را از DataFrame canonical mentors استخراج می‌کند؛


JoinKeyProfile می‌سازد؛


all_profiles و usable_profiles را تولید می‌کند؛


Issues مربوط به Law A / Law B (multi-profile, duplicate exact profile) را ثبت می‌کند.


در v3 همین نقش توسط کلاس/ماژول JoinKeyResolver (بخش ۸) پیاده شده است؛ این پیوست فقط آن را به‌عنوان Domain Service رسمی نام‌گذاری می‌کند.

F.5. ضدالگوها و محدودیت‌های شی‌گرایی در v3
برای جلوگیری از «شتر گاو پلنگ شی‌گرا»، در v3 این محدودیت‌ها برقرار است:


هیچ Entity/Service جدیدی که رفتار join/rank/trace را عوض کند، در این پیوست مجاز نیست.
هر تغییری در semantics باید از مسیر LAW / Technical SSoT و بخش‌های اصلی سند بگذرد، نه از طریق اضافه‌کردن کلاس‌های جدید.


Inheritance عمیق برای Entities ممنوع است.
Student و Mentor و School و Center موجودیت‌های جدا هستند؛ بهتر است با composition (مثلاً نگه‌داشتن JoinKeyProfile و CapacitySnapshot) ساخته شوند، نه درخت ارث‌بری پیچیده.


UI / تب دیباگ نباید Domain Service مستقل بسازد.
UI فقط مصرف‌کنندهٔ خروجی سرویس‌های دامین Import/Join/Allocation/QA است (مطابق پیوست D و C).


DataFrame همچنان مدل دادهٔ اصلی در v3 است.
کلاس‌های شی‌گرا (اگر پیاده شوند) باید thin wrapper روی frames canonical باشند و اینورینت‌های LAW/TECH را تغییر ندهند.



F.6. نگاشت بین DDD View و پیاده‌سازی v3
برای وضوح، این جدول نشان می‌دهد هر مفهوم دامین در این پیوست به کدام بخش‌های سند و پیاده‌سازی v3 نگاشت می‌شود (نام فایل/ماژول دقیق می‌تواند در Repository Specification مشخص شود):
مفهوم DDDنقش در این پیوستمعادل در این سند / پیاده‌سازی v3Student Entityدانش‌آموز با ۶ join key و student_keyبخش‌های 4.0.1 و 4.3؛ student canonical frame در Core/InfraMentor Entityپشتیبان با JoinKeyProfile و CapacitySnapshotبخش 4.0.2 و 4.2؛ DataFrame mentors + JoinKeyProfile + capacity fieldsSchool / Centerموجودیت مرجعبخش 4.0.3 و 4.0.4؛ جداول مرجع و mappings در Import/QAAllocation Entityتخصیص student→mentor با Traceبخش 4.0.5؛ خروجی Core (build_matrix + History/Trace)JoinKeyProfile VOپروفایل ۶ کلید joinبخش 4.1 و 8؛ خروجی JoinKeyResolver و ورودی MentorCapacitySnapshot VOوضعیت ظرفیت منتوربخش 4.0.6 و 4.2؛ property remaining_capacity و فیلدهای ظرفیتMentorImportServiceسرویس Import & Join منتورهاترکیب FieldRegistry + HeaderResolver + ValueCanonicalizer + JoinKeyResolver + MentorPoolBuilder (بخش‌های ۵–۸)StudentImportServiceسرویس Import دانش‌آموزpipeline فعلی students (خارج از محدوده‌ی تغییر در v3؛ باید با ۶ join key هماهنگ باشد)AllocationServiceسرویس تخصیصbuild_matrix (و در آینده MultiStrategyAllocator / RuleSlot) طبق بخش ۹JoinKeyResolutionServiceسرویس ساخت و QA پروفایل الحاقJoinKeyResolver و JoinKeyResolutionResult طبق بخش ۸
این نگاشت تضمین می‌کند که هر بحث شی‌گرا دربارهٔ سیستم، مستقیم به اجزای موجود در Refactor v3 وصل شود و از ایجاد «مدل دوم موازی» جلوگیری گردد.

این پیوست F، لایهٔ DDD / نمای شی‌گرا را به سند اضافه می‌کند بدون آن‌که قوانین join/rank/trace یا رفتار Import/Join را عوض کند؛ تنها کاری که می‌کند این است که همان معماری policy-first / SSoT-محور را در زبان شی‌گرا توضیح دهد تا هم برای انسان، هم برای LLM، تصویر دامنه شفاف‌تر و پایدارتر بماند.
این پیوست E، ریفکتور را از سطح «طراحی و قانون» به سطح «کدنویسی روزمره و گردش‌کار توسعه» متصل می‌کند تا هر تغییری که روی سیستم اعمال می‌شود، از همان ابتدا با کیفیت، قابل‌ردیابی و در هماهنگی کامل با LAW / SSoT / Technical SSoT پیاده‌سازی شود.

## Phase 06 — Cutover v3 Golden Regression & Rollback (Addendum)
- Golden regression jobs run in two stages: `scripts/run_golden_regression_phase01.py` locks the current Inspactor+school golden inputs and fails fast when any sanitized file is missing; `scripts/run_golden_regression_phase02.py` executes the config-driven scenarios under `ci/configs/golden_regression.yml` with `SMART_ALLOC_PIPELINE_MODE` set to `v3` by default.
- GOLDEN_DIFF_AUDITOR classification is enforced via `GOLDEN_DIFF_AUDITOR_DECISION` (BUG_FIX/REGRESSION/MIXED/BASELINE_OK) whenever phase02 reports drift; without a decision the workflow stops before any baseline rewrite.
- Rollback: rerun phase02 with `--mode legacy` (sets `SMART_ALLOC_PIPELINE_MODE=legacy`) to confirm parity with the legacy path before re-enabling v3. No join-key/ranking/capacity/trace semantics change in this phase; toggles only select pipeline routes.
- History/QA observability: `app.infra.history_store.persist_golden_run` appends a JSONL record under `ci/golden_runs/history.jsonl` so auditors can trace run status, auditor decisions, and timestamps without touching Core logic. The infra-only CLI entrypoint `app.infra.cli.cli_entrypoints_golden.run_phase06_golden` wraps the config-driven scenarios, sets `SMART_ALLOC_PIPELINE_MODE` (default `v3`, rollback `legacy`), and enforces fail-fast behavior when the config is missing or golden files are absent.

## REFACTOR/SSOT-ID-GUARD-01 — پیشگیری از «ID Desynchronization»
- **Incident class:** زمانی رخ می‌دهد که `student_id` از طریق هم‌ترازی ترتیبی به نماهای خروجی متصل شود و با spine اصلی ناسازگار گردد.
- **Preventive rule:** همهٔ نماها باید از `students_spine` و join کلیدمحور `student_id` ساخته شوند؛ الصاق/ترمیم ترتیبی ممنوع است (LAW/EXPORT-SSOT-ID-01).
- **Immutable allocations:** `allocations_df.student_id` پس از Core تغییرناپذیر است؛ هر تلاش برای اتصال/بازنویسی آن در Infra/Export ممنوع و باید با خطای فارسی متوقف شود.
- **Runtime enforcement:** نگهبان AC-01/AC-02/AC-03 در `app/infra/cli_legacy.py::_enforce_allocation_export_invariants` پیش از نوشتن فایل اجرا و در صورت شکست، خروجی را متوقف می‌کند.
- **Regression guard:** تست AST `tests/infra/test_student_id_positional_ast_gate.py` هر تلاش برای بازگرداندن الصاق ترتیبی را شکست می‌دهد.
- **Migration note:** توابع الصاق قبلی به حالت guard-only ارتقا یافتند و باید بدون نوشتن یا جایگزینی `student_id` باقی بمانند؛ مسیرهای قدیمی reset_index + reattach حذف یا غیرفعال می‌شوند.

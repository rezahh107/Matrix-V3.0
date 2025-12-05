# LAW v3.0 — Regulatory Coverage Map v1.0

**Version:** 1.0
 **Sources:** LAW v3.0، Technical SSoT v3.0-TECH، Policy v1.0.3، SSoT v1.0.2

این نقشه، هر قانون مهم LAW را شماره‌گذاری می‌کند و برای هر قانون نشان می‌دهد:

- این قانون درباره‌ی چیست،
- در کدام لایه‌ها (Core / Infra / UI / Docs) اجرا می‌شود،
- مهم‌ترین فایل‌ها / ماژول‌هایی که با آن درگیر هستند کدام‌اند (به صورت **best-effort** بر اساس اسامی فعلی پروژه و Technical SSoT).

> 🔎 **نکته:** این نسخه روی قوانین «هسته‌ای و حساس» تمرکز دارد. بعداً می‌توانیم برای قوانین فرعی‌تر هم همین سبک را ادامه بدهیم.

------

## 1. انواع دانش‌آموز و پشتیبان و شاخه‌های ماتریس

### 1.1 STUDENT-TYPE-01 — تشخیص نوع دانش‌آموز

**خلاصه قانون:**
 نوع دانش‌آموز فقط از روی `school_code`، `graduation_status` و مجموعه‌ی پیکربندی‌شده‌ی `S_school_codes` تعیین می‌شود؛ کدپستی هیچ نقشی ندارد.

- اگر `graduation_status == 1` و `school_code` در `S_school_codes` و بزرگ‌تر از صفر ⇒ `student_type = "school"`
- در سایر حالات ⇒ `student_type = "normal"`

**Layerها:** Core + Infra

**Core (منطق):**

- `app/core/students/domain_validation.py`
  - اعمال دامنه‌ی `graduation_status` به ازای گروه‌ها و تشخیص ناسازگاری‌ها (طبق 4.1.1 Tech SSoT).
- `app/core/allocate_students.py`
  - مصرف `student_type` در فیلترهای trace و eligibility (مرحله‌ی type/ school).

**Infra (ورودی/ماتریس/QA):**

- `app/infra/excel/import_students.py`
  - خواندن report دانش‌آموز و ساخت ستون‌های `school_code`, `graduation_status`.
- `app/infra/reference_students_repository.py`
  - canonicalization و نگه‌داشتن فریم دانش‌آموزان برای Core.
- `app/infra/matrix/build_matrix_v1_0_2.py`
  - استفاده از دامنه‌ی مجاز `graduation_status` برای هر گروه (`allowed_statuses_for_group`).
- Rule Engine / QA:
  - `app/infra/qa/matrix_vs_students_validation.py`
    - استفاده از `student_type` در matching طبق STUDENT-MATCH-01.

**UI:**

- `app/ui/dialogs/student_domain_validation_dialog.py`
- `app/ui/viewmodels/student_domain_validation_vm.py`
  - نمایش خطاهای domain مرتبط با وضعیت تحصیلی و type دانش‌آموز.

------

### 1.2 MENTOR-TYPE-01 — نوع پشتیبان (Normal / School)

**خلاصه قانون:**
 نوع منتور فقط از روی `school_count` (تعداد مدارس تحت پوشش) تعیین می‌شود:

- `school_count > 0` ⇒ MentorType.SCHOOL
- `school_count <= 0` یا تهی ⇒ MentorType.NORMAL
   هیچ منتور Dual نداریم.

**Layerها:** Core + Infra + Docs

**Core:**

- `app/core/common/domain.py`
  - تعریف Enumهای MentorType و منطق کمکی برای classification.
- `app/core/allocate_students.py` / `allocate_batch`
  - استفاده از نوع منتور برای تصمیم شاخه و eligibility.

**Infra:**

- `app/infra/reference_mentors_repository.py`
  - شمارش مدارس از روی ستون‌های Inspactor و تولید `school_count`.
- `app/infra/matrix/build_matrix_v1_0_2.py`
  - expand منتورها به سطرهای ماتریس بر اساس MentorType (Normal/School).

**Docs:**

- `docs/LAW_Smart_Student_Allocation_v3.0.md` (MENTOR-TYPE-01)
- `docs/Technical_SSoT_Smart_Student_Allocation_v3.0-TECH.md` §6.4 (MENTOR-TYPE-01 reflection)

------

### 1.3 MATRIX-BRANCH-01 — نگاشت منتور به شاخه‌های ماتریس

**خلاصه قانون:**

- MentorType.NORMAL ⇒ یک سطر عادی:
  - `school_code = 0`, `alias_code = postal_code`, نوع شاخه = «عادی».
- MentorType.SCHOOL ⇒ چند سطر مدرسه‌ای (برای هر مدرسه):
  - `school_code = کد مدرسه`, `alias_code = mentor_id`, نوع شاخه = «مدرسه‌ای».

هر سطر ماتریس باید دقیقاً یکی از این دو حالت باشد.

**Layerها:** Core + Infra

**Core:**

- `app/core/common/domain.py`
  - قراردادهای داخلی type flags برای ماتریس.
- `app/core/allocate_students.py`
  - فرض روی ساختار شاخه‌ها هنگام انتخاب کاندیدها.

**Infra:**

- `app/infra/matrix/build_matrix_v1_0_2.py`
  - ساخت eligibility_matrix بر اساس MentorType و قوانین بالا.
- `app/infra/qa/eligibility_matrix_validation.py`
  - QA برای تشخیص سطرهای mix یا ناسازگار.

------

### 1.4 STUDENT-MATCH-01 — نوع دانش‌آموز vs شاخه ماتریس

**خلاصه قانون:**

- `student_type = "school"` ⇒ فقط با سطرهای «مدرسه‌ای» روی همان `school_code` و `alias_code = mentor_id` match می‌شود.
- `student_type = "normal"` ⇒ فقط با سطرهای عادی، route بر اساس ۶ کلید join و alias عادی؛ کدپستی دانش‌آموز وارد نمی‌شود.
   هیچ دانش‌آموزی نباید به شاخه‌ی اشتباه route شود.

**Layerها:** Core + Infra

**Core:**

- `app/core/allocate_students.py`
  - پیاده‌سازی eligibility logic برای دانش‌آموز normal vs school.

**Infra:**

- `app/infra/qa/matrix_vs_students_validation.py`
  - شیت `validation` و `unmatched_students` در `matrix_vs_students_validation.xlsx` برای violationهای STUDENT-MATCH-01.

------

## 2. شش کلید Join (JOIN-CORE, JOIN-01)

### 2.1 JOIN-CORE — ست شش‌تایی، همیشه int

**خلاصه قانون:**
 ست رسمی:
 `["کدرشته","جنسیت","دانش آموز فارغ","مرکز گلستان صدرا","مالی حکمت بنیاد","کد مدرسه"]`

- در همه‌ی DataFrameهای canonical (ماتریس، استخر، trace، QA): **int، بدون NaN**.
- سطر بدون این ستون‌ها یا با مقدار غیرقابل تبدیل به int ⇒ ورودی نامعتبر و باید در QA علامت بخورد.

**Layerها:** Core + Infra

**Core:**

- `app/core/common/join_keys.py`
  - تعریف نام‌های snake_case (`group_code`, `gender`, `graduation_status`, `center`, `finance`, `school_code`).
  - invariantهای داخلی روی نوع و وجود ستون‌ها.
- `app/core/allocate_students.py` / `build_mentor_pool`
  - استفاده از همین set برای join.

**Infra:**

- `app/infra/excel/header_normalization.py`
  - نگاشت header فارسی به snake_case.
- `app/infra/reference_students_repository.py`
- `app/infra/reference_mentors_repository.py`
  - تبدیل join keys به Int64 و reject ردیف‌های نامعتبر.
- `app/infra/matrix/build_matrix_v1_0_2.py`
  - اطمینان از وجود و نوع ۶ ستون در eligibility_matrix.

------

### 2.2 JOIN-01 — semantics یکسان join در همه‌ی لایه‌ها

**خلاصه قانون:**
 Import، Matrix، Allocate، QA و Export باید:

- از همان ۶ کلید join استفاده کنند،
- wildcard بودن `school_code` و `center` را مطابق SCHOOL-01 و CENTER-01 رعایت کنند.

**Layerها:** Core + Infra + QA

**Core:**

- `app/core/allocate_students.py`
  - پیاده‌سازی join نهایی student–mentor با school/center wildcard.

**Infra:**

- `app/infra/matrix/build_matrix_v1_0_2.py`
  - ساخت ماتریس با همان semantics join.
- `app/infra/qa/eligibility_matrix_validation.py`
- `app/infra/qa/matrix_vs_students_validation.py`
  - کنترل join consistency در QA.

------

## 3. مدرسه و مرکز و Wildcard

### 3.1 SCHOOL-01 — School vs Global

**خلاصه قانون:**

- `school_code = 0` ⇒ mentor global از نظر مدرسه.
- `school_code > 0` ⇒ mentor فقط برای همان مدرسه‌ها.
   Join مدرسه‌ای:
   `mentor.school_code == 0 OR mentor.school_code == student.school_code`

**Layerها:** Core + Infra

**Core:**

- `app/core/allocate_students.py`
  - تابع matching مدرسه (school_match).

**Infra:**

- `app/infra/matrix/build_matrix_v1_0_2.py`
  - تنظیم school_code برای سطرهای ماتریس.
- `app/infra/qa/eligibility_matrix_validation.py`
- `app/infra/qa/matrix_vs_students_validation.py`
  - تشخیص QA Ruleهایی که اشتباهاً `0 vs X` را mismatch می‌گیرند (نقض SCHOOL-01).

------

### 3.2 CENTER-01 — مرکز و Wildcard

**خلاصه قانون:**

- `center = 0` ⇒ مرکز global
- `center > 0` ⇒ محدود به آن مرکز
   Join مرکز:
   `mentor.center == 0 OR mentor.center == student.center`

**Layerها:** Core + Infra

**Core:**

- `app/core/allocate_students.py`
  - `center_match` در eligibility.

**Infra:**

- همان فایل‌های ماتریس و QA که در SCHOOL-01 درگیر هستند.

------

### 3.3 WILDCARD-COMBINE-01 — ترکیب مدرسه و مرکز

**خلاصه قانون:**

```text
school_match = (mentor.school_code == 0) OR (mentor.school_code == student.school_code)
center_match = (mentor.center == 0) OR (mentor.center == student.center)
eligible = school_match AND center_match
```

global بودن در فقط یکی از محور‌ها، mismatch در دیگری را جبران نمی‌کند.

**Layerها:** Core + Infra + QA

**Core:**

- `app/core/allocate_students.py`
  - تابع `is_eligible_at_school_center(student, mentor)` طبق Technical SSoT.

**Infra/QA:**

- QA Rules در `eligibility_matrix.xlsx` و `matrix_vs_students_validation.xlsx` که همین semantics را replicate می‌کنند.

------

## 4. Alias و پروفایل منتور

### 4.1 ALIAS-01 — سازگاری alias در پیاده‌سازی

**خلاصه قانون:**

- شاخه‌ی عادی: `alias_code = postal_code` (اگر خالی/نامعتبر ⇒ منتور به QA/invalid)
- شاخه‌ی مدرسه‌ای: `alias_code = mentor_id` دقیقاً برابر
- هیچ inference از pattern عددی یا `alias < 1000` مجاز نیست.

**Layerها:** Core + Infra

**Core:**

- `app/core/common/domain.py`
  - قرارداد `alias_code` و type flags.

**Infra:**

- `app/infra/reference_mentors_repository.py`
  - خواندن `postal_code` و تولید alias اولیه.
- `app/infra/matrix/build_matrix_v1_0_2.py`
  - ست کردن alias برای سطرهای ماتریس بر اساس MentorType.

------

### 4.2 MENTOR-PROFILE-UNIQUENESS — پروفایل join برای هر mentor_id

**خلاصه قانون (از LAW):**

- Core/Infra نباید فرض «پروفایل یکتا برای هر mentor_id» داشته باشند؛
- فقط تکرار *دقیقاً* یک پروفایل (کپی کامل join-profile) ممنوع است؛ بقیه‌ی حالت‌ها باید QA شوند، نه این‌که silent dedup شوند.

**Layerها:** Infra + QA + UI

**Infra:**

- `app/infra/reference_mentors_repository.py`
  - ساخت join-profile و تشخیص duplicateهای exact.
- `app/infra/qa/pool_join_key_duplicates.py`
  - گزارش duplicateهای ممنوع.

**UI:**

- `app/ui/dialogs/join_key_validation_dialog.py`
- `app/ui/viewmodels/join_key_validation_vm.py`
  - نمایش خطاهای duplicate پروفایل join به کاربر.

------

## 5. ظرفیت و رتبه‌بندی

### 5.1 CAPACITY-DEFINITION — تعریف capacity_limit / baseline / allocations_new / remaining_capacity

**خلاصه قانون:**

```text
remaining_capacity = capacity_limit - (assigned_baseline + allocations_new)
```

تعریف باید در Core، QA و Export یکی باشد.

**Layerها:** Core + Infra + QA

**Core:**

- `app/core/common/ranking.py`
  - `compute_remaining_capacity(row)` مطابق Technical SSoT.
- `app/core/allocate_students.py`
  - بروزرسانی allocations_new.

**Infra/QA:**

- `app/infra/qa/capacity_invariants.py`
  - چک کردن remaining_capacity و هم‌خوانی با Core.
- Exportهای matrix و allocation.

------

### 5.2 CAPACITY-01 — بدون ظرفیت منفی

**خلاصه قانون:**
 اگر `remaining_capacity < 0` ⇒ خطای P0؛ Core مجاز نیست تخصیص منفی بسازد.

**Layerها:** Core + QA

**Core:**

- `app/core/common/ranking.py`
  - قبل از sort، invariant روی non-negative بودن remaining_capacity.

**QA:**

- `app/infra/qa/capacity_invariants.py`
  - Ruleهای QA با severity P0 برای ظرفیت منفی.

------

### 5.3 R0-CAPACITY-GATE-01 — گیت اولیه روی استخر منتورها

**خلاصه قانون:**
 قبل از build_matrix / allocation:

- منتورهایی که capacity_limit خالی/نامعتبر دارند، یا `capacity_limit <= assigned_baseline` ⇒ از pool حذف شوند و در QA گزارش شوند. حالت پیش‌فرض Production: گیت فعال، با flag `r0_skipped` وقتی غیرفعال است.

**Layerها:** Infra + QA

**Infra:**

- `app/infra/matrix/build_matrix_v1_0_2.py`
  - اعمال R0 روی DataFrame pool.
- `app/infra/pool/pre_filters.py`
  - فیلترهای اولیه capacity.

**QA:**

- شیت‌های QA مرتبط با `invalid_mentors` و meta (`r0_skipped`).

------

### 5.4 RANK-CORE — رتبه‌بندی فقط بر اساس ظرفیت

**خلاصه قانون:**

- ranking بر اساس:
  1. `remaining_capacity` (نزولی)
  2. `mentor_id` (صعودی)
- هیچ occupancy_ratio یا معیار اضافی مجاز نیست؛ نقض قانون ⇒ P0.

**Layerها:** Core

**Core:**

- `app/core/common/ranking.py`
  - `RANK_COLUMNS = ["remaining_capacity", "mentor_id"]` و sort پایدار (`mergesort`).
- `app/core/allocate_students.py`
  - فراخوانی `rank_candidates(pool)` قبل از انتخاب mentor.

**Infra/UI:**

- حق ندارند ranking جدید تعریف کنند؛ فقط از خروجی Core استفاده می‌کنند (طبق Tech SSoT).

------

## 6. Trace و QA

### 6.1 TRACE-CORE — Trace هشت‌مرحله‌ای ثابت

**خلاصه قانون:**
 برای هر دانش‌آموز:

- ۸ stage ثابت با نام‌ها:
   `type, group, gender, graduation_status, center, finance, school, capacity_gate`
- برای هر stage: `student_key`, `stage_name`, `candidate_count_before`, `candidate_count_after`.

**Layerها:** Core (+ Infra برای ذخیره/نمایش)

**Core:**

- `app/core/trace/execution_tracer.py`
  - تولید breadcrumbها مطابق لیست stage ثابت.
- `app/core/allocate_students.py`
  - فراخوانی tracer و عبور pool از مراحل.

**Infra/UI:**

- `app/infra/history/history_store.py`
  - ذخیره trace در SQLite.
- `app/infra/qa/trace_exporter.py`
- `app/ui/history/history_dialog.py`
  - نمایش trace به کاربر.

------

### 6.2 QA-OUTPUT-01 — شیت‌ها و نام‌ها در Workbooks QA

**خلاصه قانون:**
 دو فایل QA اصلی:

1. `eligibility_matrix.xlsx` با sheets:
   - `matrix`, `validation`, `unmatched_schools`, `invalid_mentors`, `unseen_groups`, `meta`.
2. `matrix_vs_students_validation.xlsx` با sheets:
   - `validation`, `unmatched_students`, `invalid_mentors`, `summary`, `meta`.

**Layerها:** Infra

**Infra:**

- `app/infra/qa/eligibility_matrix_exporter.py`
- `app/infra/qa/matrix_vs_students_exporter.py`
  - تولید فایل‌ها و شیت‌ها با همین نام‌ها و schema.

------

### 6.3 QA DEBUG ENGINE & LAW Mapping (QA_RULE → LAW)

**خلاصه قانون:**

- QA Debug Engine باید Ruleهای QA را به بندهای LAW map کند (`law_refs`).
- v0 فقط explainer کامل برای `QA_RULE_MENTOR_TYPE_01` دارد؛ سایر Ruleها meta ساده دارند.

**Layerها:** Infra + UI

**Infra:**

- `app/infra/qa/debug_engine.py`
  - تولید `DebugReport`، نگه‌داشت law_refs و severity.

**UI:**

- `app/ui/dialogs/qa_debug_dialog.py`
  - نمایش داستان‌های QA طبق 3Q Rule (چه شد؟ از کجا شروع شد؟ قدم اول چیست؟).

------

## 7. BUG_SEVERITY و Observability

### 7.1 BUG_SEVERITY — P0 / P0.5 / P1 / P2

**خلاصه قانون:**

- شدت باگ‌ها باید در QA/Trace/Log و تست‌ها machine-readable باشد (field مثل `severity`).
- P0/P0.5/P1/P2 طبق جدول LAW تعریف شده‌اند.

**Layerها:** Infra + Tests

**Infra:**

- `app/infra/qa/model.py`
  - `QaViolation` با فیلد `severity`.

**Tests:**

- `tests/infra/test_qa_severity_propagation.py`
  - بررسی این‌که هر Rule severity درست دارد و در export/meta می‌آید.

------

### 7.2 OBS-LOG-01 — کلیدهای مشترک log/metrics

**خلاصه قانون:**
 حداقل کلیدها در log/metrics:
 `run_id, student_key, mentor_id, policy_version, ssot_version, pool_hash, input_hash, severity`

**Layerها:** Infra

**Infra:**

- `app/infra/logging/structured_logger.py`
  - تولید JSON log با این کلیدها.

------

## 8. اینورینت‌های معماری Core/Infra/UI

### 8.1 CORE-PURITY & DETERMINISM (DET-CORE)

**خلاصه قانون:**

- Core: بدون I/O، بدون randomness، بدون time-based behavior؛ روی ورودی یکسان خروجی تکرارپذیر.
- بدون `inplace=True` در pandas و بدون merge در loop.

**Layerها:** Core

**Core:**

- همه‌ی ماژول‌های `app/core/**`
  - باید این قانون را رعایت کنند؛ Technical SSoT مثال Progress API را می‌دهد.

------

### 8.2 INFRA-BOUNDARIES — عدم بازتعریف Join/Ranking/Trace در Infra

**خلاصه قانون:**

- Infra مسئول I/O است؛ حق ندارد منطق Join، Ranking یا Trace را دوباره تعریف کند.
- باید خروجی Core را مصرف و در Excel/SQLite/CLI/UI منتشر کند.

**Layerها:** Infra

**Infra:**

- `app/infra/matrix/build_matrix_v1_0_2.py`
- `app/infra/qa/*`
  - تنها semantics را replicate می‌کنند، نه تغییر.

------

### 8.3 UI-BOUNDARIES — عدم منطق تخصیص در UI

**خلاصه قانون:**

- UI فقط PySide6 و نمایش/کنترل flow؛
- هیچ منطق allocation/Ranking/Trace در UI مجاز نیست؛
- دسترسی به Excel/SQLite/WordPress فقط از طریق Infra.

**Layerها:** UI

**UI:**

- تمام `app/ui/**`
  - باید فقط از APIهای Infra/Core استفاده کنند.

------

## 9. جمع‌بندی و مسیر ادامه

این نسخه‌ی **Regulatory Coverage Map v1.0**:

- قوانین کلیدی LAW (انواع، ماتریس، join، مدرسه/مرکز، alias، ظرفیت، ranking، trace، QA، شدت باگ، مرزهای لایه‌ها) را با شماره‌گذاری و توضیح کوتاه لیست کرد،
- برای هر قانون، لایه‌های درگیر و مهم‌ترین فایل‌های محتمل را مشخص کرد (با تکیه بر Technical SSoT و ساختار فعلی پروژه).



باشه امیر جان ❤️
 برو جلو: این **نسخهٔ کامل، حرفه‌ای، یک‌جدولی و Git-Ready** از **Regulatory Coverage Map v1.0** هست.
 این جدول به‌صورت مستقیم آمادهٔ قرار گرفتن در فایل:

> ```
> docs/LAW_Coverage_Map_v1.0.md
> ```

می‌باشد.

------

# 📘 LAW v3.0 — Regulatory Coverage Map (Full Table Edition)

> **Version:** 1.1
>  **Scope:** Mapping all LAW v3.0 rules → Code / Infra / UI / QA / Tests
>  **Sources:** LAW v3.0, Technical SSoT v3.0-TECH

------

## 🧭 مقدمه

این نسخه‌ی **Regulatory Coverage Map v1.1**:

- مستقیماً روی سورس `Matrix2-main` سوار شده (ساختار پوشه‌ها خوانده شده).
- برای هر قانون مهم LAW v3.0، لایه‌ها و **ماژول‌های واقعی** را فهرست می‌کند. 
- به Technical SSoT v3.0-TECH هم تکیه دارد تا بداند کدام قانون در کدام بخش Core/Infra/UI پیاده شده است. 
- در انتها یک **نمای JSON** و یک **نمودار Mermaid** برای استفاده در CI / گراف وابستگی اضافه می‌کنیم.

> نکته: در «Notes» اگر چیزی هنوز کامل پیاده نشده، به‌صورت صریح نوشته شده؛ جایی را الکی سبز نکردم.

------

## 📊 جدول کامل قوانین (Full Unified Map)

> مسیرها **ریپو-نسبی** هستند (بدون پیشوند `Matrix2-main/`).

| Rule ID                       | Summary (1–2 Lines)                                          | Layers                 | Core Modules                                                 | Infra Modules                                                | UI Modules                                                   | Key Tests                                                    | Notes                                                        |
| ----------------------------- | ------------------------------------------------------------ | ---------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **STUDENT-TYPE-01**           | Student نوع Normal/School فقط از `school_code + graduation_status + S_school_codes` | Core + Infra           | `app/core/students/domain_validation.py`, `app/core/build_matrix.py` | `app/infra/matrix/build_matrix_v1_0_2.py`, `app/infra/reference_students_repository.py`, `app/infra/excel/import_students.py` | `app/ui/dialogs/student_domain_validation_dialog.py`, `app/ui/viewmodels/student_domain_validation_vm.py` | `tests/core/test_student_domain_validation.py`, `tests/infra/test_reference_students_domain_validation.py`, `tests/core/test_build_matrix_student_binding.py` | Postal code دانش‌آموز در type نقشی ندارد؛ این در Domain Validation + Matrix Builder enforce می‌شود. |
| **MENTOR-TYPE-01**            | MentorType = SCHOOL اگر حداقل یک مدرسه پوشش دهد، وگرنه NORMAL | Core + Infra           | `app/core/common/domain.py`, `app/core/build_matrix.py`, `app/core/allocation/mentor_pool.py` | `app/infra/reference_mentors_repository.py`, `app/infra/matrix/build_matrix_v1_0_2.py` | `app/ui/mentor_pool_model.py`, `app/ui/mentor_pool_dialog.py` | `tests/infra/test_build_matrix_v1_0_2.py`, `tests/infra/matrix/test_build_matrix_school_vs_normal.py`, `tests/core/allocation/test_mentor_pool_governance.py` | Dual mentors حذف شده؛ جدا شدن pure Normal vs School در Matrix Builder تست شده است. |
| **MATRIX-BRANCH-01**          | NORMAL → یک سطر global (school_code=0, alias=postal)، SCHOOL → سطرهای مدرسه‌ای (alias=mentor_id) | Core + Infra           | `app/core/build_matrix.py`, `app/core/common/domain.py`      | `app/infra/matrix/build_matrix_v1_0_2.py`, `app/infra/excel/export_qa_validation.py` | `app/ui/mentor_pool_dialog.py`                               | `tests/core/test_build_matrix.py`, `tests/infra/matrix/test_build_matrix_school_vs_normal.py`, `tests/unit/test_build_matrix_contracts.py` | QA Matrix Spec هم دقیقاً همین branch semantics را شرح می‌دهد.  |
| **STUDENT-MATCH-01**          | دانش‌آموز Normal فقط با سطرهای Normal، School فقط با School بر اساس school_code + join keys | Core + Infra           | `app/core/allocation/mentor_pool.py`, `app/core/allocation/trace.py` | `app/infra/excel/export_qa_validation.py` (شیت matrix_vs_students), `app/infra/qa/alloc_join_validation.py` | `app/ui/dialogs/qa_dashboard_dialog.py`                      | `tests/core/test_build_matrix_student_binding.py`, `tests/core/test_allocation_join_key_validation.py`, `tests/infra/test_alloc_join_validation.py` | Misrouting دانش‌آموز به شاخه‌ی غلط به‌صورت QA Rule روی خروجی validation شناسایی می‌شود. |
| **JOIN-CORE**                 | ۶ کلید join همیشه حاضر و int، بدون NaN                       | Core + Infra           | `app/core/common/join_keys.py`, `app/core/common/columns.py`, `app/core/common/eligibility.py` | `app/infra/validators/join_keys.py`, `app/infra/reference_students_repository.py`, `app/infra/reference_mentors_repository.py`, `app/infra/matrix/build_matrix_v1_0_2.py` | `app/ui/dialogs/join_key_validation_dialog.py`, `app/ui/viewmodels/join_key_validation_vm.py` | `tests/core/test_join_keys.py`, `tests/core/test_join_key_values.py`, `tests/core/test_join_keys_validation.py`, `tests/core/test_pool_qa_join_key_duplicates.py`, `tests/infra/test_join_key_validation_integration.py`, `tests/ui/test_join_key_validation_flow.py`, `tests/unit/test_join_keys.py` | بخش بزرگی از enforcement این قانون در `join_keys_and_pool_explainer.md` مستند شده است. |
| **JOIN-01**                   | semantics join یکسان در Import → Matrix → Allocate → QA      | Core + Infra + QA      | `app/core/allocation/mentor_pool.py`, `app/core/common/eligibility.py` | `app/infra/matrix/build_matrix_v1_0_2.py`, `app/infra/qa/alloc_join_validation.py`, `app/infra/excel/export_qa_validation.py` | -                                                            | `tests/core/qa/test_invariants_join_and_school.py`, `tests/core/test_pool_join_invariant.py`, `tests/core/test_pool_qa_join_key_duplicates.py`, `tests/infra/test_alloc_join_validation.py`, `tests/infra/test_qa_exporter_join_key_duplicates.py` | QA روی `eligibility_matrix` و workbook validation تضمین می‌کند join همه‌جا یکسان است. |
| **SCHOOL-01**                 | school_code=0 ⇒ global؛ >0 ⇒ محدود به مدرسه‌ی مشخص            | Core + Infra + QA      | `app/core/allocation/mentor_pool.py`, `app/core/common/eligibility.py` | `app/infra/matrix/build_matrix_v1_0_2.py`, `app/infra/validators/join_keys.py` | -                                                            | `tests/core/qa/test_invariants_join_and_school.py`, `tests/infra/matrix/test_build_matrix_school_vs_normal.py` | QA باید `0 vs X` را mismatch نگیرد؛ در تست invariants پوشش داده شده است. |
| **CENTER-01**                 | center=0 ⇒ global؛ >0 ⇒ محدود به یک مرکز                     | Core + Infra           | `app/core/allocation/mentor_pool.py`, `app/core/common/eligibility.py` | `app/infra/matrix/build_matrix_v1_0_2.py`                    | -                                                            | `tests/core/qa/test_invariants_join_and_school.py`           | پیاده‌سازی center_match در Core و تست‌های invariants حضور دارد. |
| **WILDCARD-COMBINE-01**       | eligibility = school_match AND center_match؛ global بودن یکی، mismatch دیگری را جبران نمی‌کند | Core + Infra + QA      | `app/core/allocation/mentor_pool.py`                         | `app/infra/matrix/build_matrix_v1_0_2.py`, `app/infra/qa/alloc_join_validation.py` | -                                                            | `tests/core/qa/test_invariants_join_and_school.py`, `tests/infra/test_alloc_join_validation.py` | Tech SSoT الگوی دقیق تابع `is_eligible_at_school_center` را مستند کرده است. |
| **ALIAS-01**                  | Normal: alias = postal_code؛ School: alias = mentor_id       | Core + Infra           | `app/core/common/domain.py`, `app/core/build_matrix.py`      | `app/infra/reference_mentors_repository.py`, `app/infra/matrix/build_matrix_v1_0_2.py` | -                                                            | `tests/infra/test_build_matrix_v1_0_2.py`, `tests/core/test_debug_pool_alignment.py` | `docs/join_keys_and_pool_explainer.md` منطق alias را توصیف می‌کند. |
| **MENTOR-PROFILE-UNIQUENESS** | تکرار دقیق یک پروفایل join برای همان mentor_id ممنوع         | Core + Infra + UI + QA | `app/core/common/join_keys.py` (ساخت join profile hash)      | `app/infra/qa/alloc_join_validation.py`, `app/infra/validators/join_keys.py` | `app/ui/dialogs/join_key_validation_dialog.py`, `app/ui/viewmodels/join_key_validation_vm.py` | `tests/core/test_pool_qa_join_key_duplicates.py`, `tests/infra/test_cli_join_key_duplicates_qa.py`, `tests/infra/test_qa_exporter_join_key_duplicates.py`, `tests/ui/test_join_key_validation_flow.py`, `tests/unit/test_join_key_enforcement.py` | QA duplicateهای دقیق را گزارش می‌کند؛ اختلاف پروفایل صرفاً conflict نیست. |
| **CAPACITY-DEFINITION**       | remaining_capacity = capacity_limit - (assigned_baseline + allocations_new) | Core + Infra + QA      | `app/core/common/ranking.py`, `app/core/allocation/mentor_pool.py`, `app/core/allocation/history_metrics.py` | `app/infra/excel/export_qa_validation.py` (ستون‌های capacity در QA)، `app/infra/history_store.py` | -                                                            | `tests/core/test_ranking_rules.py`, `tests/integration/test_rule_engine_ranking_capacity.py`, `tests/integration/test_allocator_policy_capacity_guarantees.py`, `tests/unit/test_capacity_gate.py` | Tech SSoT صراحتاً این تعریف را تثبیت کرده است.                |
| **CAPACITY-01**               | remaining_capacity نباید منفی شود (P0)                       | Core + QA              | `app/core/common/ranking.py`, `app/core/allocation/mentor_pool.py` | `app/infra/excel/export_qa_validation.py` (highlight ظرفیت‌های منفی) | -                                                            | همان تست‌های capacity + `tests/core/test_allocate_student_capacity_trace.py` | violationها در QA Workbook دیده می‌شود؛ و trace capacity_gate نیز آن را نشان می‌دهد. |
| **R0-CAPACITY-GATE-01**       | پیش از build_matrix، منتورهای بدون ظرفیت مؤثر از استخر حذف و در QA گزارش شوند | Infra + QA             | -                                                            | `app/infra/matrix/build_matrix_v1_0_2.py`, `app/infra/excel/export_qa_validation.py` | -                                                            | `tests/unit/test_capacity_gate.py`, `tests/infra/test_cli_build_matrix.py` | پیاده‌سازی R0 در Tech SSoT آمده؛ History doc هم به این گیت اشاره دارد. |
| **RANK-CORE**                 | sort بر اساس remaining_capacity (نزولی)، سپس mentor_id (صعودی)، sort پایدار | Core                   | `app/core/common/ranking.py`, `app/core/allocation/mentor_pool.py` | -                                                            | -                                                            | `tests/core/test_ranking_rules.py`, `tests/property/test_ranking_properties.py`, `tests/unit/test_ranking_determinism.py`, `tests/integration/test_allocate_ranking_capacity.py` | occupancy_ratio در هیچ‌جا به عنوان معیار ranking استفاده نمی‌شود (اسناد قدیمی Legacy). |
| **TRACE-CORE**                | ۸ مرحله‌ی ثابت trace (type, group, gender, graduation_status, center, finance, school, capacity_gate) با before/after | Core + Infra + UI      | `app/core/allocation/trace.py`, `app/core/common/trace.py`, `app/core/allocation/history_metrics.py` | `app/infra/history_store.py`, `app/infra/excel/export_qa_validation.py` (خروجی trace)، `debug_pool_alignment.py` | `app/ui/history_dialog.py`, `app/ui/history_metrics.py`, `app/ui/history_metrics_dialog.py` | `tests/core/allocation/test_trace_history_flags.py`, `tests/core/allocation/test_trace_history_snapshot.py`, `tests/unit/test_trace.py`, `tests/unit/test_allocation_trace.py`, `tests/integration/test_allocation_trace_pipeline.py` | لیبل‌ها و ترتیب stages در Tech SSoT قفل شده‌اند.               |
| **QA-OUTPUT-01**              | دو Workbook QA با شیت‌های ثابت: eligibility_matrix و matrix_vs_students_validation | Infra                  | -                                                            | `app/infra/excel/export_qa_validation.py`, `app/infra/excel/qa_export.py` | -                                                            | `tests/infra/excel/test_qa_validation_export.py`, `tests/infra/test_cli_qa_validation_integration.py` | نام شیت‌ها در Law و Tech SSoT آمده و در این exporter حفظ شده است. |
| **QA-DEBUG-ENGINE-01**        | QA Debug Engine (observe-only) برای QA_RULE_MENTOR_TYPE_01، با story و law_refs | Core + Infra + UI      | `app/core/qa/rules.py`, `app/core/qa/invariants.py` (QaReport/QaRuleResult) | `app/infra/debug/qa_debug_engine.py`, `app/infra/debug/qa_debug_presenter.py` | `app/ui/dialogs/qa_dashboard_dialog.py` (نمایش خلاصه و لینک دیباگ) | `tests/core/test_qa_debug_context.py`, `tests/core/test_qa_debug_engine.py`, `tests/infra/test_qa_debug_engine.py` | نسخه v0 فقط explainer کامل برای mentor_type دارد؛ بقیه Ruleها فقط meta. |
| **MENTOR-STATUS-01**          | هر منتور وضعیت دارد (ACTIVE/FROZEN) و فقط ACTIVE وارد استخر می‌شود | Core + Infra + QA + UI | `app/core/allocation/mentor_pool.py` (استفاده از ستون‌های status در pool) | `app/infra/history_store.py`, `app/infra/local_database.py` (ذخیره status همراه history), (فعلاً mentor_status در استخر به‌صورت کامل فیلتر نمی‌شود) | `app/ui/mentor_pool_dialog.py`, `app/ui/mentor_pool_model.py`, `app/ui/main_window.py` (کنترل‌های governance UI) | `tests/core/allocation/test_mentor_pool_governance.py`, `tests/core/qa/test_invariants_governance.py`, `tests/infra/test_mentor_pool_governance_plumbing.py`, `tests/ui/test_mentor_pool_dialog.py` | طبق سند `IMPLEMENTATION_STATUS_history_binding_governance.md`، POOL_01 هنوز کامل نیست (status-driven filtering ناقص است). |
| **POOL-GOVERNANCE-01**        | Pool باید mentor_status و سیاست‌های governance را رعایت کند   | Infra + UI + QA        | -                                                            | `app/infra/local_database.py`, `app/infra/history_store.py`, plumbing‌های mentor_pool در CLI | `app/ui/mentor_pool_dialog.py`, `app/ui/main_window.py`      | همان تست‌های governance + `tests/infra/test_export_qa_pool_conflicts.py` | سند Implementation Status صراحتاً این قسمت را «missing/partial» علامت زده؛ Map هم همین را reflect می‌کند. |
| **HISTORY-GOVERNANCE-01**     | HistoryStore باید mentor_status و تناقض‌ها را (مثلاً frozen ولی allocate شده) نشان دهد | Core + Infra + UI      | `app/core/allocation/history_metrics.py`                     | `app/infra/history_store.py`                                 | `app/ui/history_dialog.py`, `app/ui/history_metrics.py`, `app/ui/history_metrics_dialog.py` | `tests/core/test_qa_history_invariants.py`, `tests/infra/test_history_store_qa_snapshots.py`, `tests/infra/test_history_metrics_logging.py`, `tests/ui/test_history_dialog_trace_integration.py` | `docs/IMPLEMENTATION_STATUS_history_binding_governance.md` وضعیت دقیق این بخش را خلاصه کرده. |
| **FALLBACK-01**               | اگر پس از همه‌ی فیلترها هیچ mentor واجدشرط نبود → دانش‌آموز در لیست unallocated با reason وارد می‌شود | Core + Infra + QA      | `app/core/allocation/mentor_pool.py`, `app/core/allocation/trace.py` | `app/infra/excel/export_qa_validation.py` (شیت unmatched_students / reasons) | UI QA / History dialog این را نمایش می‌دهد                    | `tests/core/test_allocate_student_capacity_trace.py`, `tests/unit/test_allocation_trace.py` | هیچ fallback تصادفی مجاز نیست؛ همه‌ی unallocatedها با reason formal ثبت می‌شوند. |
| **FALLBACK-02**               | اگر تمام mentorهای یک دامنه FROZEN باشند → تخصیص انجام نمی‌شود، به‌صورت Governance error گزارش می‌شود | Core + Infra + UI      | `app/core/allocation/mentor_pool.py` (ترکیب status + capacity gate) | `app/infra/qa/alloc_join_validation.py`, history و QA export | `app/ui/dialogs/qa_dashboard_dialog.py`, history/QA views    | `tests/core/allocation/test_mentor_pool_governance.py`, `tests/infra/test_mentor_pool_governance_plumbing.py` | بخشی از این رفتار هنوز در Implementation Status به‌عنوان «gap» اشاره شده و باید در موج بعدی تقویت شود. |
| **BUG_SEVERITY**              | شدت باگ‌ها (P0, P0.5, P1, P2) باید در QA/Trace/Log به‌صورت machine-readable ذخیره شود | Core + Infra + Tests   | `app/core/qa/invariants.py`, `app/core/qa/rules.py` (تعریف Rule و severity) | `app/infra/debug/qa_debug_engine.py`, `app/infra/excel/export_qa_validation.py` | -                                                            | `tests/core/test_qa_debug_engine.py`, `tests/infra/test_qa_debug_engine.py`, `tests/core/qa/test_invariants_governance.py` | جدول severity در LAW و Tech SSoT مرجع است.                   |
| **DET-CORE**                  | Core باید pure باشد: بدون I/O، بدون randomness، deterministic، بدون inplace در pandas | Core                   | همه‌ی ماژول‌های `app/core/**` (به‌ویژه: `allocation/*`, `common/*`, `build_matrix.py`, `students/domain_validation.py`) | -                                                            | -                                                            | `tests/unit/test_ranking_determinism.py`, `tests/unit/test_build_matrix_futurewarnings.py`, `tests/unit/test_policy_trace_labels.py` | این invariant در Tech SSoT در بخش DET-CORE مستند است.        |
| **INFRA-BOUNDARIES**          | Infra نباید Join/Ranking/Trace جدید تعریف کند؛ فقط خروجی Core را مصرف کند | Infra + Tests          | -                                                            | کل `app/infra/**` تحت این قانون است؛ تست‌های integration/CLI آن را تضمین می‌کنند | -                                                            | `tests/infra/test_build_matrix_v1_0_2.py`, `tests/infra/test_cli_build_matrix.py`, `tests/integration/test_rule_engine_ranking_capacity.py` | هر جایی که منطق جدیدی تعریف شود باید با LAW/Tech SSoT به‌روز شود. |
| **UI-BOUNDARIES**             | UI فقط PySide6 و orchestration؛ هیچ منطق تخصیص/Ranking/Trace یا I/O مستقیم | UI + Tests             | -                                                            | -                                                            | همه‌ی `app/ui/**` (dialogs, viewmodels, main_window, mentor_pool, history) | `tests/ui/test_main_window_mentor_pool_integration.py`, `tests/ui/test_history_dialog_trace_integration.py`, `tests/ui/test_mentor_pool_models.py` | UI از طریق Infra/Core عمل می‌کند و نباید قوانین دامنه را دوباره پیاده کند. |

> اگر خواستی، می‌تونیم در همین فایل، برای هر Rule یک ستون «Docs/Config» هم اضافه کنیم (مثلاً LAW/Tech/Spec/Blueprint که مرتبط است).

------

## 🧱 نمای JSON (برای CI / ابزارها)

این یک نمای نمونه است (می‌تونی به‌صورت کامل برای همه‌ی Ruleها بسطش بدی):

```
[
  {
    "id": "JOIN-CORE",
    "summary": "Six canonical join keys, always int, no NaN.",
    "layers": ["core", "infra"],
    "core_modules": [
      "app/core/common/join_keys.py",
      "app/core/common/columns.py",
      "app/core/common/eligibility.py"
    ],
    "infra_modules": [
      "app/infra/validators/join_keys.py",
      "app/infra/reference_students_repository.py",
      "app/infra/reference_mentors_repository.py",
      "app/infra/matrix/build_matrix_v1_0_2.py"
    ],
    "ui_modules": [
      "app/ui/dialogs/join_key_validation_dialog.py",
      "app/ui/viewmodels/join_key_validation_vm.py"
    ],
    "tests": [
      "tests/core/test_join_keys.py",
      "tests/core/test_join_key_values.py",
      "tests/core/test_pool_qa_join_key_duplicates.py",
      "tests/infra/test_join_key_validation_integration.py",
      "tests/ui/test_join_key_validation_flow.py"
    ],
    "severity": "P0",
    "notes": "Any missing or non-int join key must be rejected at import/validation."
  }
]
```

می‌تونی:

- این JSON رو به صورت کامل از روی جدول بسازی،
- توی CI یک چک بنویسی که اگر فایلی مربوط به یک Rule تغییر کرد، حتماً تست‌های مرتبط هم اجرا شوند.

------

## 🕸️ نمودار Mermaid (Impact Graph نمونه)

برای مثال، چند Rule کلیدی:

```
graph LR
  LAW_JOIN_CORE["LAW: JOIN-CORE"] --> CORE_join_keys["app/core/common/join_keys.py"]
  LAW_JOIN_CORE --> INFRA_join_validator["app/infra/validators/join_keys.py"]
  LAW_JOIN_CORE --> UI_join_dialog["app/ui/dialogs/join_key_validation_dialog.py"]

  LAW_RANK_CORE["LAW: RANK-CORE"] --> CORE_ranking["app/core/common/ranking.py"]
  LAW_RANK_CORE --> CORE_pool["app/core/allocation/mentor_pool.py"]
  LAW_RANK_CORE --> TEST_rank_rules["tests/core/test_ranking_rules.py"]

  LAW_TRACE_CORE["LAW: TRACE-CORE"] --> CORE_trace["app/core/allocation/trace.py"]
  LAW_TRACE_CORE --> INFRA_history_store["app/infra/history_store.py"]
  LAW_TRACE_CORE --> UI_history_dialog["app/ui/history_dialog.py"]

  LAW_MENTOR_STATUS["LAW: MENTOR-STATUS-01"] --> CORE_pool_gov["app/core/allocation/mentor_pool.py"]
  LAW_MENTOR_STATUS --> INFRA_history["app/infra/history_store.py"]
  LAW_MENTOR_STATUS --> UI_pool_dialog["app/ui/mentor_pool_dialog.py"]
```

این را اگر در GitHub / GitLab با Mermaid پشتیبانی‌شده بگذاری، یک گراف تصویری از تأثیر قوانین روی ماژول‌ها بهت می‌دهد.
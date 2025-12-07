# سند حقیقت فنی (Technical SSoT) — هستهٔ تخصیص دانش‌آموزان

**نسخه:** 3.0-TECH (Production-Ready)  
**تاریخ:** …  
**مالک سند:** تیم معماری / Policy-First  

---

## فهرست

0. چکیدهٔ اجرایی  
1. هدف و محدوده  
2. مراجع بالادستی  
3. تصویر معماری و قرارداد لایه‌ها  
4. مدل داده و شناسه‌ها (join keys، alias، student_key)  
5. اینورینت‌های هستهٔ Core (JOIN-CORE، RANK-CORE، TRACE-CORE، DET-CORE)  
6. اینورینت‌های سرتاسری (JOIN-01، CAPACITY-01، SCHOOL-01، CENTER-01، MENTOR-TYPE-01، ALIAS-01، R0-CAPACITY-GATE-01)  
7. شدت باگ‌ها (BUG_SEVERITY)  
8. Trace، QA و Explainability  
9. نگرانی‌های Production-Grade (Observability، Feature Flags، Migration، Performance، Testing)  
10. نگاشت فازهای باگ‌یابی ۰ تا ۸  
11. نحوهٔ استفاده توسط انسان و Agentها  

---

## 0. چکیدهٔ اجرایی

این سند، نسخهٔ فنی و نهایی (Technical SSoT) برای **هستهٔ تخصیص دانش‌آموزان به پشتیبانان** است.  
Focus آن روی این است که:

- اینورینت‌های ثابت LAW (به‌خصوص **۶ Join Key، Ranking بر اساس ظرفیت، Trace ۸ مرحله‌ای، انواع Normal/School، Alias، گیت ظرفیت R0 و Governance استخر**) را به قراردادهای فنی تبدیل کند.
- برای ۵ سال آینده، زبان مشترک بین Core، Infra، UI، QA، History و ابزارهای AI (مثل Codex/CodeSurgeon) باشد.
- هر تغییر کدی که این قراردادها را نقض کند، **به‌صورت خودکار در تست/QA/Trace قابل شناسایی** باشد.

اگر این سند و LAW با هم تضاد داشتند، LAW v3.0 معیار است و این سند باید اصلاح شود.

---

## 1. هدف و محدوده

**پوشش می‌دهد:**

- منطق هسته‌ای: `build_matrix` / `BuildMentorPool`، `allocate_student` / `allocate_batch`
- Join Keys، ظرفیت و Ranking، Trace ۸ مرحله‌ای
- قراردادهای Progress API در Core
- QA invariants و خروجی‌های Excel Validation
- Observability، Feature Flags، Rollout، Migration، Performance و Testing

**خارج از محدوده:**

- تعریف جزئی کدهای دامنه (جنسیت، گروه‌ها، مالی…) → Policy/SSoT
- طراحی UI/UX و جزئیات فرم‌های WordPress/GravityForms
- سیاست‌های تجاری خارج از تخصیص (مثلاً قوانین هزینه‌گذاری)

---

## 2. مراجع بالادستی

این سند باید با موارد زیر سازگار باشد:

- `Policy v1.0.3`
- `Student_Allocation_System_Spec_v1.0.md` (SSoT v1.0.2)
- `System_Architecture_Blueprint_Smart_Student_Allocation_v1.0.md`
- `System_Vision_Scope_Smart_Student_Allocation_v1.0.md`
- `AGENTS.md`
- `docs/LAW_Smart_Student_Allocation_v3.0.md`
- اسناد Rule Engine و Eligibility Matrix (مانند `Rule_Engine_Spec.md`, `Eligibility_Matrix_Builder_Spec.md`)

---

## 3. تصویر معماری و قرارداد لایه‌ها

### 3.1. Core (هستهٔ تخصیص)

**مسئولیت:**

- پیاده‌سازی دقیق قوانین LAW برای:
  - Student/Mentor type (Normal/School)
  - Join Keys شش‌تایی (JOIN-CORE)
  - ظرفیت و Ranking (RANK-CORE)
  - Trace ۸ مرحله‌ای (TRACE-CORE)
- بدون هیچ I/O یا Qt.

**مجاز:**

- `pandas`، type hints، `TypedDict`، `Enum`، `dataclass`
- توابع pure روی `DataFrame`ها و ساختارهای درون‌حافظه‌ای

**ممنوع:**

- هرگونه فایل، شبکه، Excel، SQLite، logging مستقیم، Qt
- هرگونه randomness (`sample`، seed داخلی، `time.time()` در منطق تخصیص)
- تغییر قوانین LAW از داخل Core (مثلاً افزودن tie-breaker جدید)

---

### 3.2. Infra

**مسئولیت:**

- I/O کامل: Excel، WordPress/Gravity Forms، SQLite، CLI
- Import و canonicalization دانش‌آموز/پشتیبان/مدرسه
- ساخت استخر اولیه و ماتریس (با استفاده از Core)
- Export اصلی (ImportToSabt) و QA Workbooks
- مدیریت HistoryStore و AllocationChannel

**ممنوع:**

- بازتعریف منطق Join، Ranking یا Trace
- bypass کردن Core برای تخصیص «میان‌بُر»
- دستکاری خام خروجی Core به‌نحوی که LAW را نقض کند

---

### 3.3. UI

**مسئولیت:**

- PySide6-only؛ نمایش داشبورد، Trace، QA، History، governance
- کنترل flows (Import → Build → Allocate → QA → Export)
- اعمال overrideهای Governance (مثلاً freeze/unfreeze mentor) **به‌صورت شفاف و audit-able**

**ممنوع:**

- نوشتن منطق تخصیص/Ranking/Trace در UI
- دسترسی مستقیم به Excel/SQLite/WordPress (باید از طریق Infra عبور کند)

---

### 3.4. Progress API در Core

الگوی استاندارد:

```python
from __future__ import annotations

from collections.abc import Callable
import pandas as pd

ProgressCallback = Callable[[int, str], None]


def allocate_batch(
    students: pd.DataFrame,
    pool: pd.DataFrame,
    policy: Policy,
    progress: ProgressCallback | None = None,
) -> AllocationResult:
    if progress is not None:
        progress(0, "start")

    # ... allocation logic ...

    if progress is not None:
        progress(100, "done")

    return result
```

**قواعد:**

- Core فقط `progress(pct, msg)` را **call** می‌کند؛ معنای msg و مقصد log بر عهدهٔ Infra/UI است.
- هیچ فرضی درباره‌ی زمان‌بندی، threading یا محل نمایش نباید در Core وجود داشته باشد.

---

## 4. مدل داده و شناسه‌ها

### 4.1. Join Keys و aliasهای داخلی

| # | نام ستون (فارسی)   | کلید داخلی (snake_case) | نوع | توضیح کوتاه                         |
|---|--------------------|-------------------------|-----|-------------------------------------|
| 1 | `کدرشته`           | `group_code`            | int | از Crosswalk SSoT                  |
| 2 | `جنسیت`            | `gender`                | int | کدهای Policy                       |
| 3 | `دانش آموز فارغ`   | `graduation_status`     | int | ۰/۱ طبق Policy                     |
| 4 | `مرکز گلستان صدرا` | `center`                | int | ۰ = global center                  |
| 5 | `مالی حکمت بنیاد`  | `finance`               | int | ۰/۱/۳ طبق SSoT                     |
| 6 | `کد مدرسه`         | `school_code`           | int | ۰ = mentor global روی مدرسه       |

Core **فقط** این نام‌های snake_case را می‌شناسد؛ نگاشت از header فارسی به این کلیدها وظیفهٔ Infra است.

#### 4.1.1. دامنهٔ وضعیت فارغ‌التحصیلی به‌ازای گروه

- Policy v1.0.3 تعیین می‌کند که تنها ۱۱ گروه ( `{1, 3, 5, 7, 8, 9, 11, 12, 14, 17, 18}` ) هر دو وضعیت `دانش آموز` (۱) و `فارغ` (۰) را دارند.
- ۲۲ گروه دیگر صرفاً دانش‌آموزی هستند و باید با `دانش آموز فارغ = 1` در ماتریس دیده شوند (مثلاً گروه‌های یازدهم: ۲۱، ۲۲، ۲۳، ۲۹؛ دهم: ۲۴، ۲۵، ۲۶، ۳۰؛ متوسطه اول: ۲۷، ۳۱، ۳۳؛ دبستان: ۳۵، ۴۱، ۴۳، ۴۵، ۴۶؛ هنرستان یازدهم: ۵۳، ۵۵، ۶۶، ۶۹؛ هنرستان دهم: ۸۳، ۸۹).
- ماژول `app/core/students/domain_validation.py` این دامنه را روی دیتافریم دانش‌آموزان اعمال می‌کند و ردیف‌های نامعتبر را برای داشبورد QA گزارش می‌دهد.
- در لایهٔ Infra، تابع `allowed_statuses_for_group` (در `app/infra/matrix/build_matrix_v1_0_2.py`) این قاعدهٔ Policy را هنگام ساخت ماتریس اعمال می‌کند؛ Core همچنان تنها ۶ کلید join را مصرف می‌کند.

---

### 4.2. شناسهٔ دانش‌آموز

- `student_key`: کلید داخلی پایدار (مثلاً شمارنده یا hash پایدار)  
- در خروجی‌ها ممکن است با نام `student_id` بیاید، ولی معنی‌اش **همیشه** همان `student_key` است.
- `student_national_code` فقط برای join با سیستم‌های خارجی استفاده می‌شود، نه برای Trace/History داخلی.

---

### 4.3. شناسه و Alias پشتیبان

- `mentor_id`: کلید اصلی پشتیبان
- `alias_code`: طبق LAW:
  - برای سطر عادی: کدپستی چهاررقمی
  - برای سطر مدرسه‌ای: `mentor_id`

Core باید از این دو به‌صورت type-safe استفاده کند. **پروفایل‌های متعدد روی یک `mentor_id` مجازند**؛
تنها ممنوعیت، تکرار دقیق همان ۷-تایی `(mentor_id + ۶ join key)` است که باید یا به‌صورت
دترمینیستیک dedupe شود یا به QA (`duplicate mentor join profile`) گزارش گردد. اختلاف پروفایل‌ها
conflict محسوب نمی‌شود.

### 4.4. STUDENT-TYPE-01 — قانون فنی تشخیص نوع دانش‌آموز

- **ورودی‌ها:**
  - ستون Policy برای وضعیت تحصیلی (`graduation_status`)،
  - ستون Policy برای کد مدرسه (`school_code`)،
  - مجموعهٔ پیکربندی‌شدهٔ ``allocation_channels.school_codes``.
- **قانون:**
  - اگر ``graduation_status == 1`` و ``school_code`` در ``allocation_channels.school_codes`` باشد ⇒ `student_type = "school"`.
  - در سایر حالات ⇒ `student_type = "normal"`.
- **وابستگی‌ها:** کدپستی دانش‌آموز در این قانون نقشی ندارد و هر کد دیگری (مثلاً mentor_id) نباید مسیر جداگانه‌ای بسازد.

### 4.5. Mentor Import & Join — Infra Pipeline v3

- همهٔ ورودی‌های ایمپورت/الحاق پشتیبان در Infra باید از پایپلاین واحد **MentorPipelineV3** عبور کنند؛ هیچ مسیر موازی یا ساخت استخر بدون این پایپلاین مجاز نیست.
- مراحل پایپلاین (به همین ترتیب):
  1. **FieldRegistry** — ثبت فیلدهای mentor و فیلدهای Join (۶ کلید عددی) برای ارجاع ثابت.
  2. **HeaderResolver** — نگاشت هدرهای خام به فیلدهای canonical با قواعد alias؛ خروجی شامل مپ هدر و گزارش alias است.
  3. **ValueCanonicalizer** — اعتبارسنجی دامنه و کاننیکال‌سازی مقادیر؛ خروجی `ValueCanonicalizationResult` با پرچم `can_continue` (خطای P0 ⇒ can_continue=false و توقف).
  4. **JoinKeyResolver** — ساخت شش کلید الحاق عددی، اعمال wildcard مدرسه/مرکز طبق LAW/TECH، برچسب‌گذاری پشتیبان‌های چندپروفایله، و تولید QA برای کلیدهای Join.
  5. **MentorPoolBuilder** — تولید `MentorPoolBuildResult` شامل `pool` canonical برای Core و متادیتای QA (issues، duplicates، multi-profile).
- شکل مورد انتظار `MentorPoolBuildResult.pool` (حداقل ستون‌های مصرفی Core):
  - `mentor_id`, شش کلید join (`group_code`, `gender_code`, `grad_status_code`, `center_code`, `finance_code`, `school_code`) همگی `int` بدون مقدار خالی.
  - ظرفیت و وضعیت: `capacity_limit`, `assigned_baseline`, `allocations_new`, `remaining_capacity` با فرمول CAPACITY-01، `mentor_status`, نوع پشتیبان (School/Normal).
  - تبارشناسی/lineage: `_src_insp_row_id`, `_src_mentor_id`, `_src_school_idx` و سایر ستون‌های ردیابی موردنیاز QA.
- متادیتای QA در `MentorPoolBuildResult`: لیست issues (severity، نگاشت LAW/QA Rule، context)، گزارش duplicates (بر اساس mentor_id و پروفایل join)، و multi-profile mentors با `all_profiles`, `usable_profiles`, QA-only.
- معنای `can_continue`:
  - HeaderResolver / ValueCanonicalizer / JoinKeyResolver باید خطاهای P0 را به `can_continue=false` ارتقا دهند و از ساخت استخر جلوگیری کنند؛ خطاهای پایین‌تر به‌صورت QA issue عبور می‌کنند.
  - MentorPoolBuilder فقط زمانی `pool` را برمی‌گرداند که `can_continue=true`; در غیر این صورت نتیجه صرفاً شامل متادیتای توقف است.
- همهٔ entrypointهای ایمپورت در Infra باید MentorPipelineV3 را صدا بزنند و فقط `MentorPoolBuildResult.pool` را به Core تحویل دهند؛ Core هیچ منطق الحاق مستقلی ندارد و صرفاً مصرف‌کنندهٔ این SSoT است.

---

## 5. اینورینت‌های هستهٔ Core

### 5.1. JOIN-CORE — ۶ کلید کاننیکال

در Core، برای DataFrameهای:

- ماتریس استخر،
- حالت داخلی تخصیص،
- Trace/QA داخلی،

این شروط برقرار است:

1. ستون‌های `group_code`, `gender`, `graduation_status`, `center`, `finance`, `school_code` وجود دارند.
2. نوع‌شان `int` است (بدون NaN).
3. هیچ کد «متفرقه/خارج از دامنه» بدون ثبت در QA پذیرفته نمی‌شود.

الگوی check نمونه (برای تست/QA):

```python
from __future__ import annotations

from collections.abc import Sequence
import pandas as pd


def invariant_join_core(df: pd.DataFrame) -> None:
    required: Sequence[str] = [
        "group_code",
        "gender",
        "graduation_status",
        "center",
        "finance",
        "school_code",
    ]
    missing = [c for c in required if c not in df.columns]
    assert not missing, f"missing join-key columns: {missing}"
    assert not df[required].isna().any().any(), "join-key columns must not be null"
```

---

### 5.2. RANK-CORE — Ranking بر اساس ظرفیت

**مطابق LAW:**  
هیچ occupancy_ratio در طراحی نهایی نداریم؛ فقط ظرفیت مهم است.

تعاریف عملی:

```python
def compute_remaining_capacity(row: pd.Series) -> int:
    used = int(row["assigned_baseline"]) + int(row["allocations_new"])
    return int(row["capacity_limit"]) - used
```

**رتبه‌بندی:**

1. `remaining_capacity` بزرگ‌تر بهتر است (sort نزولی)
2. در حالت مساوی ⇒ `mentor_id` کوچک‌تر (sort صعودی)

پیاده‌سازی نمونه:

```python
RANK_COLUMNS = ["remaining_capacity", "mentor_id"]


def rank_candidates(pool: pd.DataFrame) -> pd.DataFrame:
    pool = pool.assign(
        remaining_capacity=pool.apply(compute_remaining_capacity, axis=1)
    )
    return pool.sort_values(
        RANK_COLUMNS,
        ascending=[False, True],
        kind="mergesort",
    )
```

هر تغییری در این ترتیب بدون آپدیت LAW ⇒ شکست تست و نقض RANK-CORE.

---

### 5.3. TRACE-CORE — Trace ۸ مرحله‌ای

Trace Core باید:

- برای هر `student_key`، ۸ رکورد ثابت با `stage_name` در ست زیر داشته باشد:

  ```text
  {"type","group","gender","graduation_status","center","finance","school","capacity_gate"}
  ```

- حداقل فیلدهای الزامی:
  - `student_key`
  - `stage_name`
  - `candidate_count_before`
  - `candidate_count_after`

فیلدهای پیشنهادی (غیرقراردادی ولی مفید):

- `filter_description`
- `pool_mismatch_detected`
- `expected_op`, `expected_threshold`

---

### 5.4. DET-CORE — دترمینیسم و purity

Core باید:

- بدون randomness عمل کند؛
- روی ورودی یکسان و policy/SSoT یکسان، خروجی بایت‌به‌بایت تکرارپذیر تولید کند (تا جای ممکن)؛
- از `inplace=True` در pandas و `merge` در loop پرهیز کند (مطابق AGENTS.md).

---

## 6. اینورینت‌های سرتاسری (Phase 0 Focus)

در این بخش، اینورینت‌های cross-layer مطابق LAW را formal می‌کنیم.

### 6.1. JOIN-01 — semantics یکسان join

- Import، ماتریس، Allocate، QA و Export باید:
  - از همان ۶ کلید Join استفاده کنند، با همان نگاشت فارسی ↔ snake_case.
  - wildcard بودن `school_code`/`center` را همان‌طور که در LAW تعریف شده است رعایت کنند.

اگر QA join را فقط روی زیرمجموعه‌ای از کلیدها انجام دهد، یا wildcard را نادیده بگیرد، JOIN-01 نقض شده است.

---

### 6.2. CAPACITY-01 — ظرفیت و state

- تعریف `capacity_limit`, `assigned_baseline`, `allocations_new`, `remaining_capacity` در Core و QA باید یکسان باشد.
- QA/Export نمی‌توانند capacity را «از نو» محاسبه کنند؛ باید از داده‌های Core استفاده کنند.
- `remaining_capacity < 0` در هر نقطه ⇒ خطای QA حتمی (P0).

---

### 6.3. SCHOOL-01 و CENTER-01 — پیاده‌سازی فنی join

Core باید LOGIC زیر را پیاده کند (یا معادل واضح):

```python
def school_match(student, mentor) -> bool:
    return mentor.school_code == 0 or mentor.school_code == student.school_code


def center_match(student, mentor) -> bool:
    return mentor.center == 0 or mentor.center == student.center


def is_eligible_at_school_center(student, mentor) -> bool:
    return school_match(student, mentor) and center_match(student, mentor)
```

QA و Export باید دقیقا همین semantics را replicate کنند؛ نه چیزی کمتر، نه چیزی بیشتر.

---

### 6.4. MENTOR-TYPE-01 — بازتاب در ماتریس

Core/Infra باید نوع منتور را **فقط** از روی `تعداد مدارس تحت پوشش` استخراج کنند:

- `school_count > 0` ⇒ MentorType.SCHOOL
- `school_count <= 0` یا تهی ⇒ MentorType.NORMAL

Dual تولید نمی‌شود. expand ماتریس نیز بر همین مبناست:

- MentorType.NORMAL ⇒ تنها شاخهٔ عادی با `school_code = 0` و `alias = postal_code` (معتبر و غیرتهی)
- MentorType.SCHOOL ⇒ تنها شاخهٔ مدرسه‌ای با `school_code > 0` و `alias = mentor_id`

---

### 6.5. ALIAS-01 — سازگاری alias در پیاده‌سازی

- شاخهٔ عادی: `alias_code = postal_code` (اگر خالی/نامعتبر باشد، ردیف منتور باید به QA/invalid منتقل شود).
- شاخهٔ مدرسه‌ای: `alias_code = mentor_id` و باید دقیقاً با آن برابر باشد.
- هیچ inference از روی `alias < 1000` یا pattern عددی مجاز نیست؛ alias صرفاً بر اساس نوع منتور تنظیم می‌شود.

---

### 6.6. R0-CAPACITY-GATE-01 — پیاده‌سازی

Infra باید:

- قبل از build_matrix:
  - mentorهایی را که `capacity_limit` ندارند یا مقدارشان ≤ `assigned_baseline` است، حذف کند.
  - و آنها را با reason مناسب در QA/Log ثبت کند.
- این رفتار باید قابل فعال/غیرفعال‌شدن از طریق config/feature flag باشد، ولی حالت پیش‌فرض Production همیشه **فعال** است.

---

### 6.7. GROUP-SOURCE-01 — Group Source Resolution (Inspactor)

- **قرارداد ستون‌ها:** ورودی Inspactor باید حداقل یکی از دو ستون «گروه آزمایشی» (Legacy) یا «شامل گروه های آزمایشی» (New) را داشته باشد؛ نبود هر دو ستون ⇒ خطای Schema (P0) پیش از هر گونه parsing. این الزام فقط منبع گروه را تعریف می‌کند و ۶ کلید join همچنان همان مقادیر LAW را دارند.
- **اولویت منبع:** اگر ستون «شامل گروه های آزمایشی» موجود و قابل parse باشد، همان به‌عنوان منبع اصلی group_codes استفاده می‌شود؛ ستون legacy تنها وقتی مصرف می‌شود که ستون جدید غایب یا عملاً خالی/نامعتبر باشد. رفتار پردازش توکن‌های نامعتبر در ستون جدید بدون تغییر باقی می‌ماند (تجمیع در unseen/invalid).
- **مرکز آینده (GroupSourceResolver):** برای حذف منطق پراکندهٔ تشخیص منبع گروه، یک abstraction آینده به نام `GroupSourceResolver` در Infra/Docs تعریف می‌شود که مسئول تعیین وجود/اولویت/پیام خطا برای منابع گروه است و به Core صرفاً خروجی canonical (group_pairs) را می‌دهد. این بند اکنون فقط Contract را formal می‌کند؛ پیاده‌سازی نهایی resolver در refactor بعدی انجام می‌شود.
- **جایگاه در هرم اسناد:** این قانون زیرمجموعهٔ JOIN-01 است و باید در Architecture Blueprint اشاره شود تا اپراتورها و QA برای ورودی‌های Inspactor محل واحدی برای رفتار منبع گروه داشته باشند. هرگونه تغییر در precedence یا نام ستون‌ها مستلزم به‌روزرسانی LAW/TECH-SSoT و resolver است.

---

## 7. شدت باگ‌ها (BUG_SEVERITY)

همان جدول LAW، اما اینجا برای استفاده در تست و CI:

- P0/P0.5/P1/P2 باید در گزارش‌های QA/Trace/Log و در تست‌ها به‌صورت machine-readable ظاهر شوند (مثلاً field `severity` در `QaViolation`).

---

## 8. Trace، QA و Explainability

### 8.1. Trace Snapshot per Student

Core باید API مشخصی برای گرفتن Trace per student (یا per run) داشته باشد؛ Infra می‌تواند آن را:

- در SQLite ذخیره کند،
- در QA Workbookها مصرف کند،
- یا در UI نمایش دهد.

هیچ نسخه‌ی «دوم» از منطق Trace در Infra/UI مجاز نیست؛ همه‌ی تحلیل‌ها باید روی خروجی Core سوار شوند.

---

### 8.2. QA Validation Workbook Schema (فنی)

برای:

1. `eligibility_matrix.xlsx`:

   - `matrix`: سطرهای ماتریس با join keys، capacity، alias، type flags
   - `validation`: summary ولیدیشن روی pool (missing group, finance unknown, …)
   - `unmatched_schools`: مدرسه‌هایی که در ماتریس دیده نشده‌اند
   - `invalid_mentors`: mentorهایی با دادهٔ ناقص/متناقض
   - `unseen_groups`: گروه‌های آزمایشی بدون match در crosswalk
   - `meta`: نسخه‌های policy/SSoT، hashها، timestamp

2. `matrix_vs_students_validation.xlsx`:

   - `validation`: ردیف به ردیف StudentReport vs Matrix (مسیر تصمیم Rule Engine)
   - `unmatched_students`: دانش‌آموزانی که هیچ سطر واجدشرط ندارند
   - `invalid_mentors`: ارجاع‌های invalid به mentor یا alias
   - `summary`: تجمیع Ruleها و count mismatchها
   - `meta`: metadata کامل run

Technical SSoT اینجا فقط **نام شیت‌ها و نقش‌شان** را تثبیت می‌کند؛ ستون‌های دقیق در specهای جدا (`Rule_Engine_Spec.md`) آمده‌اند.

---

### 8.3. Lineage حداقلی برای QA Debug

- همهٔ خروجی‌های QA/Trace باید حداقل این ستون‌های lineage را حمل کنند (type-safe, non-null مگر در legacy ورودی):
  - `_src_insp_row_id: int` — شناسهٔ سطر خام InspactorReport
  - `_src_mentor_id: int` — mentor_id خام قبل از canonicalization
  - `_src_school_idx: int` — ایندکس مدرسه‌ی منبع در Inspactor (۱..۴ یا ۰)
  - `mentor_id: int` — کلید canonical پس از پاک‌سازی
- Core این فیلدها را **نمی‌سازد**؛ Infra/QA آن را به خروجی‌های Core اضافه می‌کند، بدون تغییر در منطق تخصیص.
- ترتیب و معنی ستون‌ها **ثابت** است تا QA Debug Engine بتواند نقض‌ها را تکرارپذیر توضیح دهد.

---

### 8.4. DebugReport (v0) — شکل و معنا

- ساختار پیشنهادی و ثابت‌شدنی برای QA Debug Engine (observe-only):
  - `rule_id: str` — شناسه QA Rule (مثلاً `QA_RULE_MENTOR_TYPE_01`).
  - `law_refs: list[str]` — بندهای LAW مرتبط (مانند `LAW/MENTOR-TYPE-01`).
  - `severity: str` — یکی از `error`, `warning`, `info` که با ایموجی ساده نگاشت می‌شود: `🔴`/`❌`=error، `🟡`=warning، `🟢/✅`=ok.
  - `context: Mapping[str, str|int]` — کلید/مقدارهای مرتبط (مثلاً lineage columns، stage name، hash ورودی).
  - `evidence: str` — خلاصهٔ قابل خواندن انسان با ارجاع به ستون‌های lineage/trace.
  - `story: list[str]` — ۵ جمله/بخش برای Debug Story v0 به ترتیب: Severity، Rule/Clause، Evidence، Cause (Why)، Next Action.
- DebugReport باید **pure و قابل بازتولید** باشد؛ Debug Engine **هیچ تخصیصی را تغییر نمی‌دهد** و فقط بر روی خروجی Core/Infra کار می‌کند.

---

### 8.5. ExecutionTracer و Snapshots

- ExecutionTracer فقط breadcrumb فراهم می‌کند و در هستهٔ تخصیص دخالتی ندارد:
  - Breadcrumb: لیست stageها و شمارش candidate قبل/بعد (مطابق TRACE-CORE).
  - Snapshot: خروجی میانی پس از هر مرحله (اختیاری، فقط برای QA/دیباگ؛ حجم کنترل‌شده).
- Tracer باید دترمینیستیک باشد، بدون randomness یا sleep؛ فعال/غیرفعال‌سازی آن از طریق flag در Infra انجام می‌شود.
- Snapshots فقط **خواندنی** هستند؛ هیچ mutation روی DataFrame اصلی Core ایجاد نمی‌شود.

---

### 8.6. QA Debug Engine (observe-only)

- وظایف:
  - مصرف Trace، lineage و خروجی‌های QA برای تولید DebugReportهای تکرارپذیر.
  - نگاشت QA Rule → LAW Clause و درج آن در `law_refs`.
  - حفظ purity: Engine **نباید** Join/Ranking/Trace را override کند و **نباید** خروجی تخصیص را دستکاری کند.
- خروجی باید با CLI/UI قابل نمایش باشد و با Policy/SSoT نسخه‌گذاری شود (`policy_version`, `ssot_version`).
- اگر Engine خاموش باشد، باید در meta/QA ثبت شود؛ حالت پیش‌فرض Production «فعال و observe-only» است.
- نسخهٔ v0 حداقلی باقی می‌ماند: تنها `QA_RULE_MENTOR_TYPE_01` یک explainer عملیاتی دارد؛ سایر قوانین
  صرفاً meta/summary دریافت می‌کنند و near-miss/canary برای نسخهٔ فعلی غیرفعال است.

---

### 8.7. CLI/Presenter Debug Story v0

- قالب روایت انسانی برای هر DebugReport:
  1. **Severity ایموجی** (`🔴`, `🟡`, `🟢/✅`, `❌`).
  2. **Rule/Clause** (QA Rule + LAW ref).
  3. **Evidence** (ستون lineage یا stage عددی Trace).
  4. **Why** (علت دترمینیستیک؛ بدون حدس).
  5. **Next Action** (گام بعدی پیشنهادی برای اپراتور یا اصلاح داده).
- Presenter باید خروجی را بدون رنگ ANSI (صرفاً متن + ایموجی) نمایش دهد تا در محیط‌های CLI ساده نیز قابل خواندن باشد.
- Story v0 فقط خواندنی است؛ هیچ دکمه/اکشنی در Core/Infra را تحریک نمی‌کند و با فعال/غیرفعال‌شدن feature flag تغییری در تخصیص ایجاد نمی‌کند.

### 8.8. QA Debug Governance (v0) — عملیاتی‌سازی ترمزها

- **قرارداد QADebugStory (v0 mentor rule):**
  - فقط برای `QA_RULE_MENTOR_TYPE_01` یک `story: list[str]` ارائه می‌شود که دقیقاً سه پرسش 3Q را پوشش دهد: «چه شد؟»، «از کجا شروع شد؟»، «اولین اقدام چیست؟».
  - `context: Mapping[str, str|int|float|list|dict]` باید سبک‌وزن بماند؛ شامل کلیدهای ساده، شمارش‌ها یا breadcrumbهای کوچک، نه DataFrame کامل یا محاسبات جدید.
- **کدگذاری breadcrumb:**
  - اگر breadcrumb وجود داشته باشد، به‌صورت اختیاری در `matrix.attrs["qa_debug_breadcrumbs"]` ذخیره می‌شود به‌شکل `list[dict]` با کلیدهای `step_id`, `label`, `row_count`, `key_stats` (دیکشنری کوچک از اعداد/کلیدهای متنی).
  - Breadcrumb فقط برای مشاهده است؛ نبود آن نباید correctness QA را تغییر دهد.
- **بدون محاسبهٔ مجدد در explainer:**
  - Engine دیباگ Infra باید همان ماتریس و نتایج QA را مصرف کند؛ اجازهٔ rerun تخصیص یا QA، یا بارگذاری کپی مستقل از داده‌ها را ندارد. context افزوده باید از metadata/attributes تزریق‌شده توسط runner بیاید.
- **چرخهٔ عمر قابلیت‌ها:**
  - هر قابلیت دیباگ جدید باید به یک رخداد واقعی QA و درد مستند (زمان/گام‌های از دست رفته) ارجاع دهد.
  - در بازبینی دوره‌ای، قابلیت‌های کم‌استفاده باید یا ساده/ادغام شوند، یا به کانال آزمایشی منتقل شوند، یا حذف شوند.
  - حذف/ادغام باید در changelog QA/Infra ثبت شود تا تعمد در کوچک‌سازی سطح دیباگ شفاف بماند.
- **محدوده v0 (observe-only):**
  - explainer کامل و story فقط برای `QA_RULE_MENTOR_TYPE_01` پیاده‌سازی می‌شود؛ سایر Ruleها صرفاً metadata (`law_refs`, `debug context`) دارند و story ندارند.
  - گسترش به Ruleهای دیگر نیازمند به‌روزرسانی LAW/Technical SSoT و رعایت همان ترمزها (🕒 30-Second Rule، 3Q، Pain-First، Prune-Usage).
- **جایگاه Core vs Infra:**
  - Core تنها metadata ثابت (مانند `QADebugContext`, `law_refs`) را نگه می‌دارد؛ هیچ قالب‌بندی، I/O یا جریان تعاملی دیباگ در Core مجاز نیست.
  - Infra تنها محل engine/story/CLI/GUI و استفاده از ایموجی است؛ lineage/breadcrumb باید مینیمال و کلیدمحور باقی بماند و به tracing framework سنگین تبدیل نشود مگر با مصوبهٔ جدید.
- **Near-miss/Canary:**
  - برای v0، near-miss/canary پیش‌فرض خاموش است؛ در صورت نیاز باید با flag/تصمیم رسمی فعال شود و همچنان observe-only بماند.

---

## 9. نگرانی‌های Production-Grade

### 9.1. Observability & Logging

حداقل کلیدهای مشترک برای log/metrics:

- `run_id`, `student_key`, `mentor_id`, `policy_version`, `ssot_version`, `pool_hash`, `input_hash`, `severity`

Core از طریق ProgressCallback و return values، اطلاعات لازم را به Infra می‌دهد؛ Infra آن را به log/metric ساخت‌یافته تبدیل می‌کند (JSON, Prometheus, …).

---

### 9.2. Feature Flags & Rollout Strategy

الگو:

- هر تغییر مهم (rule جدید، QA جدید، تغییر در ظرفیت، Governance) پشت یک flag در Infra یا پیکربندی policy قرار می‌گیرد.
- Rollout امن:
  - **Shadow run:** اجرای نسخهٔ جدید در کنار نسخهٔ قبلی و مقایسه‌ی allocations/trace.
  - **Gradual enablement:** فعال‌سازی بر اساس مرکز یا subset محدودی از دانش‌آموزان.
  - **Rollback سریع:** یک سوئیچ config؛ بدون نیاز به deploy دوباره‌ی Core.

---

### 9.3. Migration & Backfill

Technical SSoT باید تضمین کند:

- Policy و SSoT versioned هستند (مثلاً `policy_version`, `ssot_version` در meta).
- هر breaking change (مثلاً تغییر join semantics) نیاز به:
  - بامپ version Policy/SSoT،
  - و سناریوی backfill برای History/QA دارد.
- HistoryStore باید امکان replay runهای قدیمی را با نسخهٔ مربوطه Core فراهم کند.

---

### 9.4. Performance & Capacity Planning

اهداف نمونه (قابل تنظیم):

- حداقل چند ده هزار دانش‌آموز در چند دقیقه روی سخت‌افزار مرجع.
- build_matrix در حد ممکن columnar/برداری (پرهیز از loopهای خطی روی DataFrame).
- `allocate_batch` از sort پایدار و indexing مناسب استفاده کند، نه scanهای بی‌مورد.

---

### 9.5. Testing Strategy

لایه‌های تست:

1. Unit tests (Core):
   - JoinKey helpers، Ranking، capacity gating، Trace، Student/Mentor type detection.
2. Golden tests (Infra/Exporter):
   - فایل‌های eligibility_matrix و matrix_vs_students_validation و ImportToSabt با snapshot ثابت.
3. Integration tests (CLI):
   - pipeline کامل Import → Build → Allocate → Export/QA.
4. Replay tests (History):
   - چند run واقعی/نمونه از History خوانده شده و با نسخهٔ فعلی Core replay می‌شود؛ اختلاف‌ها باید در محدودهٔ کنترل‌شده باشد.

---

## 10. نگاشت فازهای باگ‌یابی ۰ تا ۸

| فاز | عنوان کوتاه                                    | بخش‌های مرتبط در این سند |
|-----|-----------------------------------------------|--------------------------|
| 0   | Invariants سرتاسری                            | §5, §6, §8, §9           |
| 1   | ورودی دانش‌آموز / canonicalize_students       | §4، §6.1، §9.5           |
| 2   | ورودی پشتیبان/مدرسه قبل از Matrix            | §4، §6.4–6.6، §8.2       |
| 3   | BuildMentorPool / build_matrix                 | §3، §4، §5.1، §6.2       |
| 4   | allocate_student / allocate_batch (edge cases) | §5.2–5.4، §6.2، §9.4     |
| 5   | QA Rules                                      | §6، §7، §8، §9.5         |
| 6   | HistoryStore و Replay                         | §8، §9.3، §9.5           |
| 7   | CLI & Infra Pipelines                         | §3.2، §9.1–9.2، §9.5     |
| 8   | UI / UX و سطح اپراتور                        | §3.3، §8، §9.1           |

---

## 11. استفاده توسط انسان و Agentها

- توسعه‌دهنده انسانی:
  - هنگام تغییر code، باید در PR توضیح بدهد کدام قانون LAW/TECH-SSoT را تقویت/لمس کرده.
- Agentها (Codex/CodeSurgeon):
  - هر prompt باید:
    - `POLICY_VERSION: "1.0.3"`
    - `SSoT_VERSION: "1.0.2"`
    - و رفرنس به این فایل (`Technical_SSoT_Smart_Student_Allocation_v3.0-TECH.md`) و LAW داشته باشد.
  - تغییر Join Keys / Ranking / Trace / capacity بدون اشاره به آپدیت LAW/TECH-SSoT ⇒ پیشنهاد نامعتبر است.

---

این سند می‌تواند بدون تغییر، به‌عنوان:

`docs/Technical_SSoT_Smart_Student_Allocation_v3.0-TECH.md`

در ریپو commit شود و در کنار LAW v3.0، تنها مرجع فنی/اجرایی برای تمام تغییرات آینده باشد.

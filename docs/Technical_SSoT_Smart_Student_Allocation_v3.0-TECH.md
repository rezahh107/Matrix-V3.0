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

- اینورینت‌های ثابت LAW (به‌خصوص **۶ Join Key، Ranking بر اساس ظرفیت، Trace ۸ مرحله‌ای، انواع Normal/School/Dual، Alias، گیت ظرفیت R0 و Governance استخر**) را به قراردادهای فنی تبدیل کند.
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
  - Student/Mentor type (Normal/School/Dual)
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

Core/Infra باید انواع Normal/School/Dual را که در LAW تعریف شده‌اند، به یک سری **tag** یا flag تبدیل کنند:

- `is_school_limited: bool`
- `has_school_branch: bool`
- `has_normal_branch: bool`

و بر این اساس، expand ماتریس را انجام دهند. هر سطر ماتریس باید قابل ردیابی به یکی از سه حالت LAW باشد.

---

### 6.5. ALIAS-01 — سازگاری alias در پیاده‌سازی

برای هر `mentor_id` که در ماتریس ظاهر می‌شود:

- تمام سطرهایش باید Join Profile یکسان داشته باشند (به‌جز school_code/alias_code).
- هر conflict باید در QA (مثلاً در sheet `invalid_mentors`) ظاهر شود.

---

### 6.6. R0-CAPACITY-GATE-01 — پیاده‌سازی

Infra باید:

- قبل از build_matrix:
  - mentorهایی را که `capacity_limit` ندارند یا مقدارشان ≤ `assigned_baseline` است، حذف کند.
  - و آنها را با reason مناسب در QA/Log ثبت کند.
- این رفتار باید قابل فعال/غیرفعال‌شدن از طریق config/feature flag باشد، ولی حالت پیش‌فرض Production همیشه **فعال** است.

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

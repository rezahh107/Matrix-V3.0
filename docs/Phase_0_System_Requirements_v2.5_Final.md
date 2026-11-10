# Phase 0 System Requirements — Smart Student Allocation (v2.5 Final)

> **منبع حقیقت قوانین تخصیص (LAW v3.0 / Technical SSoT v3.0):** این سند راهنما/تاریخچه است؛ تمام قواعد ثابت (کلیدهای join، رتبه‌بندی، انواع منتور/دانش‌آموز، گیت ظرفیت، trace و ...) فقط در `docs/LAW_Smart_Student_Allocation_v3.0.md` و `docs/Technical_SSoT_Smart_Student_Allocation_v3.0-TECH.md` معتبرند. در صورت هر تعارض، محتوای این دو فایل حاکم است و نکات قدیمی این سند به‌عنوان LEGACY خوانده شوند.
## 1. مقدمه و دامنه
- این سند الزامات فاز ۰ سیستم تخصیص دانش‌آموزان را با تکیه بر Policy v1.0.3، SSoT v1.0.2 و معماری Core/Infra/UI تعریف می‌کند.
- دامنه شامل منطق Policy-First، لایهٔ Infra برای I/O (WordPress، Excel، HistoryStore) و رابط PySide6/CLI است؛ تغییر سیاست رتبه‌بندی یا ۶ کلید Join در این نسخه مجاز نیست.
- هدف، افزودن رفتار تاریخچه‌محور (HistoryStore + `dedupe_by_national_id`) و کانال‌محور (AllocationChannel) بدون نقض تعیین‌گرایی و شفافیت است.

## 2. الزامات عملکردی (Functional Requirements)
### 2.1 مدیریت تاریخچه و جلوگیری از تخصیص تکراری
- **FR-HIST-01 — نگهداری HistoryStore:** Infra باید انباره‌ای پایدار از تخصیص‌های قطعی بسازد که با کلید `national_id_normalized` و ۶ کلید Join (همگی `int`) قابل جست‌وجو باشد. داده‌های حداقلی شامل `mentor_id`, `allocation_date`, `کد مدرسه`, `مرکز گلستان صدرا`, `gender`, `graduation_status`, `allocation_channel` و نشان نسخهٔ policy/ssot است. این مخزن در هر اجرا خوانده و پس از تخصیص‌های جدید به‌صورت افزایشی به‌روزرسانی می‌شود.
- **FR-HIST-02 — دِداپ مبتنی بر کد ملی:** Core باید قبل از هرگونه رتبه‌بندی، تابع خالص `dedupe_by_national_id` را اجرا کند تا ورودی‌ها به دو گروه «allocated_before» (دارای سابقه معتبر در HistoryStore) و «new_candidates» تفکیک شوند. نرمال‌سازی اعداد فارسی/لاتین، صفر پیشرو و حذف نویز در همین مرحله انجام می‌شود و نتیجهٔ آن باید در trace/خلاصه ثبت شود.
- **FR-HIST-03 — دلیل تصمیم:** برای هر دانش‌آموزی که از جریان تخصیص حذف می‌شود، باید مقدار `dedupe_reason` (مثلاً «کد ملی نامعتبر»، «تخصیص قبلی» یا «بدون سابقه») در trace و خروجی QA موجود باشد تا اپراتور بتواند تصمیم را توضیح دهد.

### 2.2 کانال‌های تخصیص سیاست‌محور
- **FR-CHAN-01 — پشتیبانی AllocationChannelConfig:** PolicyConfig باید شامل بخش AllocationChannelConfig باشد و Core موظف است بدون هاردکد شناسه، مقدار `allocation_channel` را از بین چهار مقدار SCHOOL / GOLESTAN / SADRA / GENERIC برای هر دانش‌آموز محاسبه کند. قواعد تصمیم‌گیری می‌تواند از ترکیب `کد مدرسه`, `مرکز گلستان صدرا`, `مرکز ثبت‌نام` و وضعیت تحصیلی استفاده کند ولی باید همگی از PolicyConfig خوانده شوند.
- **FR-CHAN-02 — کانال در trace/export:** مقدار `allocation_channel` برای تمام دانش‌آموزان (چه تخصیص‌یافته چه ردشده) باید در trace، خلاصهٔ مدیریتی و خروجی ImportToSabt/Excel قابل مشاهده باشد تا تحلیل جریان‌ها و مقایسهٔ کانال‌ها ممکن شود.
- **FR-CHAN-03 — همزیستی با سیاست رتبه‌بندی:** اجرای کانال‌ها نباید ترتیب رتبه‌بندی را تغییر دهد؛ پس از تعیین کانال، سیاست RANK-CORE مصوب مبتنی بر LAW/TECH (`remaining_capacity` نزولی، سپس `allocations_new` صعودی، سپس `mentor_sort_key = natural_key(mentor_id)` صعودی و پایدار) اجرا می‌شود. ذکر `occupancy_ratio` در نسخه‌های قبلی LEGACY است؛ هر استثناء باید در PolicyConfig تعریف شود، نه در Core.

### 2.3 گزارش‌پذیری و خروجی‌ها
- **FR-TRACE-01 — غنی‌سازی Trace:** trace هشت‌مرحله‌ای باید علاوه‌بر شمارش‌های استاندارد، ستون‌های `allocation_channel`, `dedupe_reason`, `allocated_before` را شامل شود تا اپراتور بتواند تصمیم تاریخچه/کانال را در کنار فیلترهای اصلی مشاهده کند.
- **FR-EXPORT-01 — همگام‌سازی با HistoryStore:** پس از ثبت تخصیص‌های موفق در خروجی ImportToSabt، همان رکوردها باید به HistoryStore اضافه شوند تا اجرای بعدی دقیقاً همان آگاهی تاریخچه‌ای را داشته باشد. این فرآیند باید اتمیک و مقاوم در برابر شکست نیمه‌راه باشد.
  - *رفتار در شکست جزئی:* اگر نوشتن ImportToSabt یا Excel موفق شود ولی درج در HistoryStore شکست بخورد، Infra باید کل اجرای تخصیص را «ناموفق» علامت‌گذاری کند، نتیجه را به Core/UI برنگرداند و حداقل سه تلاش مجدد با backoff انجام دهد.
  - *تضمین عدم دوگانگی:* در صورت تداوم خطا، سیستم باید رخداد را به‌عنوان خطای بحرانی ثبت کند، اپراتور را مطلع سازد و از تحویل خروجی به اپراتور جلوگیری کند تا عدم انطباق بین خروجی و HistoryStore ایجاد نشود.
  - *حفظ قابلیت بازیابی:* پس از رفع خطا، اجرای تکراری باید بتواند همان خروجی ImportToSabt را دوباره تولید و در HistoryStore ثبت کند تا انطباق کامل برقرار شود؛ این الزام بخشی از معیار «اتمیک و مقاوم» محسوب می‌شود.
- **FR-EXPORT-02 — پایگاه دادهٔ محلی:** برای سناریوهای کاملاً آفلاین، Infra باید یک ماژول SQLite (`app/infra/local_database.py`) با schema دترمینیستیک فراهم کند تا متادیتای اجرا (run_uuid، policy_version/ssot_version، مسیر و هش ورودی‌ها، خلاصهٔ QA و KPI تاریخچه) ذخیره شود. CLI/UI باید بتوانند مسیر فایل را با `--local-db` تنظیم یا با `--disable-local-db` غیرفعال کنند؛ Core از این لایه بی‌خبر می‌ماند.

### 2.4 جدول مرجع کانال‌ها (اطلاعات تجمیعی)
| کانال | توصیف سیاستی | ورودی‌های محتمل |
|-------|---------------|------------------|
| SCHOOL | دانش‌آموزانی که مطابق PolicyConfig به مدرسهٔ مشخص متصل‌اند و باید در همان جریان مدرسه‌ای توضیح داده شوند. | `کد مدرسه`, وضعیت مدرسه در PolicyConfig |
| GOLESTAN | جریان ثبت‌نام مراکز گلستان (WordPress/Gravity Forms) که مستقیم از مرکز گلستان به پشتیبان می‌رسند. | `مرکز گلستان صدرا`, فیلدهای ثبت‌نام گلستان |
| SADRA | درخواست‌های مرکز صدرا که از PolicyConfig کانال ویژه دریافت می‌کنند تا ظرفیت و گزارش مجزا داشته باشند. | `مرکز گلستان صدرا` با مقدارهای صدرا، فیلدهای مالی حکمت بنیاد |
| GENERIC | سایر دانش‌آموزان که در PolicyConfig به جریان عمومی هدایت می‌شوند؛ همان سیاست رتبه‌بندی مشترک را طی می‌کنند. | همهٔ مواردی که در سه کانال دیگر قرار نمی‌گیرند |

### 2.5 حاکمیت استخر پشتیبان‌ها
- **FR-MENT-01 — مشاهده پروفایل پشتیبان‌ها:** اپراتور باید بتواند از طریق UI/CLI فهرست MentorProfile را مشاهده کند؛ این فهرست از SSoT/Policy بارگذاری می‌شود و حداقل ستون‌های `mentor_id`, `mentor_status`, ظرفیت فعال و مدیر مربوطه را نشان می‌دهد.
  - *معیار پذیرش:* لیست مستقل از InspactorReport است و حتی اگر پشتیبانی در import جدید وجود نداشته باشد، وضعیت او از SSoT خوانده می‌شود.
- **یادداشت پیاده‌سازی Core:** بلوک `mentor_pool_governance` در policy.json فعال است و Core پیش از ساخت ماتریس فقط منتورهای `active` را نگه می‌دارد؛ override نوبتی mentor_id→enabled از UI/CLI قابل تزریق است و تأثیری بر ۶ کلید join یا رتبه‌بندی ندارد.
- **FR-MENT-02 — تغییر وضعیت mentor_status:** اپراتور باید بتواند وضعیت هر پشتیبان را بین `ACTIVE` و `FROZEN` (و در صورت تعریف الگوهای `RESTRICTED_*`) تغییر دهد؛ این تغییر به‌صورت نسخه‌دار در Policy/SSoT ذخیره می‌شود.
  - *معیار پذیرش:* اجرای بعدی pipeline تضمین می‌کند که پشتیبان‌های `FROZEN` در استخر فعال ظاهر نشوند حتی اگر در InspactorReport حضور داشته باشند؛ تاریخچهٔ تغییر در فایل log/trace ثبت می‌شود و UI/CLI به اپراتور تأیید می‌دهد که تغییر در SSoT persisted شده است.
- **FR-MENT-03 — محدودیت‌های RESTRICTED:** اگر Policy الگوهای `RESTRICTED_*` تعریف کند، UI باید امکان ثبت این قیود (مثلاً محدود به یک مدرسه یا کانال) را فراهم کند تا Core بتواند آن را به قید eligibility تبدیل کند.
  - *معیار پذیرش:* قید ثبت‌شده در خروجی QA/trace به‌عنوان دلیل محدودیت ذکر می‌شود و با ۶ کلید join در تضاد نیست.
- **FR-MENT-04 — پیشنهادهای HistoryStore:** سیستم باید با اتکا بر HistoryStore پیشنهاد کند کدام پروفایل‌ها کاندید فریز شدن هستند (مثلاً به سقف تخصیص نرم رسیده‌اند یا در یک مدرسهٔ خاص ثابت مانده‌اند)، ولی تصمیم نهایی بر عهدهٔ کاربر است و تا زمانی که mentor_status تغییر نکند، Core رفتاری تغییر نمی‌دهد.
  - *معیار پذیرش:* پیشنهادها صرفاً به‌صورت پیام/پرچم نمایش داده می‌شوند؛ هیچ فریز خودکاری بدون تغییر Policy رخ نمی‌دهد.
- **FR-MENT-05 — جلوگیری از بازگشت ناخواسته به استخر:** سامانه باید تضمین کند که حتی در صورت اضافه‌شدن مجدد یک پشتیبان در ورودی‌های خام، وضعیت `FROZEN` مانع از ورود او به استخر می‌شود؛ این الزام شامل مسیرهای CLI و UI است.
  - *معیار پذیرش:* تست یکپارچه‌ای وجود دارد که InspactorReport تازه‌ای را با همان `mentor_id` بارگذاری می‌کند و نشان می‌دهد خروجی BuildMentorPool خالی از آن پشتیبان است.
- **FR-MENT-06 — مسیر رسمی بدون ویرایش دستی Excel:** کنترل استخر باید از طریق MentorProfile/Policy و UI/CLI انجام شود؛ حذف ردیف‌ها از InspactorReport صرفاً یک راه‌حل اضطراری است و نباید مسیر پیش‌فرض اپراتور باشد.
  - *معیار پذیرش:* در مستندات عملیات و UI هشدار صریحی وجود دارد که تغییرات پایدار باید در MentorProfile ذخیره شود؛ اجراهای بعدی نیز نشان می‌دهند که بدون دست‌کاری Excel، وضعیت mentor_status همان‌طور که در Policy آمده مصرف می‌شود.
- **FR-MENT-07 — UI حاکمیت استخر:** UI باید یک دیالوگ حاکمیت استخر فراهم کند تا اپراتور بتواند منتورها/مدیران را برای اجرای جاری فعال یا غیرفعال کند و این overrideها را از مسیر UI→Infra→Core به موتور تخصیص برساند.
  - *معیار پذیرش:* تست UI و یکپارچه نشان می‌دهد که منتور غیرفعال از طریق دیالوگ در خروجی تخصیص دانش‌آموزی دریافت نمی‌کند.
- **FR-MENT-08 — ثبت دلایل سیاستی:** برای هر پشتیبانی که خارج از استخر نگه داشته می‌شود باید در خروجی trace/گزارش مدیریتی ستونی وجود داشته باشد که وضعیت و دلیل Policy (مثلاً `FROZEN (Policy v1.0.3)`) را نشان دهد تا ممیزی بدون مراجعه به Excel امکان‌پذیر باشد.
  - *معیار پذیرش:* اجرای QA، عدم وجود Mentor بدون reason را به‌عنوان خطا علامت می‌زند؛ UI نیز هنگام نمایش لیست، برچسب دلیل را از Policy/HistoryStore پیشنهاد شده نشان می‌دهد.

## 3. الزامات غیرعملکردی و کیفی (Non-Functional Requirements)
- **NFR-DET-01 — تعیین‌گرایی:** ورودی مساوی، خروجی مساوی؛ همهٔ sort ها (به‌ویژه رتبه‌بندی mentors) باید stable + natural باشند. تاریخچه و کانال نباید منجر به رفتار غیرقابل‌پیش‌بینی شوند.
- **NFR-JOIN-01 — کلیدهای ثابت:** شش کلید Join (`کدرشته`, `جنسیت`, `دانش آموز فارغ`, `مرکز گلستان صدرا`, `مالی حکمت بنیاد`, `کد مدرسه`) باید همیشه `int` باقی بمانند و در HistoryStore/trace/export بدون تغییر معنا ذخیره شوند.
- **NFR-POLICY-01 — Policy-First:** تمام قواعد تاریخچه و کانال باید از PolicyConfig/AllocationChannelConfig خوانده شوند؛ Core اجازهٔ هاردکد شناسه مدرسه/مرکز یا استثناء جدید ندارد.
- **NFR-TRACE-01 — قابلیت ردیابی:** برای هر دانش‌آموز باید امکان بازسازی مسیر تصمیم وجود داشته باشد (policy_version، ssot_version، allocation_channel، dedupe_reason، ظرفیت و Mentor انتخاب‌شده). خروجی QA باید امکان فیلتر روی هر کدام از این فیلدها را بدهد.
- **NFR-RESILIENCE-01 — خطایابی:** اگر HistoryStore در دسترس نباشد یا ناسازگار باشد، Infra باید خطای واضح تولید کند و تخصیص متوقف شود؛ استفاده از تاریخچه ناقص یا حدسی مجاز نیست.
- **NFR-RESILIENCE-02 — لاگ محلی:** ثبت تاریخچهٔ اجرا باید بتواند روی پایگاه دادهٔ SQLite محلی (`smart_alloc.db`) انجام شود و در صورت غیرفعال‌سازی (`--disable-local-db`) یا خطا، جریان تخصیص متوقف نشود.
- **NFR-UX-01 — هماهنگی UI/CLI:** UI/CLI باید پیام‌های مرتبط با تاریخچه/کانال را از Core دریافت و بدون تغییر معنی به کاربر نمایش دهند (مثلاً شمارش دانش‌آموزان خارج‌شده به‌دلیل تاریخچه یا کانال خاص).


### QA Validation Workbook
- **FR-QA-02 — ورک‌بوک اعتبارسنجی QA:** پس از اجرای `run_all_invariants`، Infra باید فایل Excel تکرارپذیری بسازد (مثلاً `matrix_validation.xlsx` یا `allocations_validation.xlsx`) که شامل شیت خلاصهٔ قوانین و شیت‌های تفکیکی `students_per_mentor`, `school_binding_issues`, `allocation_capacity`, `student_counts`, `join_keys`, `meta` باشد تا اپراتور بتواند بدون تغییر منطق Core، وضعیت QA را بررسی کند.
## 4. ردیابی الزامات به معماری و Vision
- FR-HIST-01/02/03 توسط زیربخش «HistoryStore و `dedupe_by_national_id`» در Architecture Blueprint و بخش «حافظهٔ تخصیص» در Vision پشتیبانی می‌شوند.
- FR-CHAN-01/02/03 و جدول کانال‌ها با زیربخش AllocationChannel در Architecture و بخش «کانال‌های جریان دانش‌آموز» در Vision هم‌راستا هستند.
- NFR-DET-01, NFR-JOIN-01, NFR-POLICY-01 با Invariants Vision و بخش Determinism معماری همخوان است؛ Trace و Explainability نیز در هر سه سند تکرار شده‌اند تا سازگاری تضمین شود.


---

## Addendum — Approved operational Roster lifecycle requirements (2026-11-10)

**Decision reference:** `MATRIX-OPS-ROSTER-20261110-001` — direct Owner confirmation; documentation PR [#56](https://github.com/rezahh107/Matrix-V3.0/pull/56), reviewed Head `5e8813e2702318b59486fba7a02366635a9b4f3f` (OPEN and unmerged when documented). **Verified production baseline:** `main@4a1a064d8ee9365a8bef8dc47c1649fc660275d3` (includes PR #55). **Authority:** approved product operation and D1/D2 user outcomes; subordinate to LAW v3.0, Technical SSoT v3.0 and existing counter/QA/Sabt contracts. This addendum preserves historical Phase 0 material and does not change domain rules or approve any implementation mechanism.

### Owner-confirmed requirements — delivery status is separate

| ID | Requirement / user outcome | Source-grounded state on the inspected baseline |
| --- | --- | --- |
| **FR-ROSTER-CUR-01** | Operator must acquire and supply a **fresh official current-year Roster for every Allocate**, including repeated runs in one session, to avoid reissuing registration numbers already used in the official system. The prior selected path or old snapshot is not automatically accepted as freshly acquired. | **NOT_IMPLEMENTED:** GUI/CLI Roster paths are optional; no enforceable per-run freshness lifecycle. |
| **FR-ROSTER-PRIOR-01** | Operator selects one valid prior-year Roster per academic-year context; subsequent Allocate runs and application restarts may safely reuse it while valid and unchanged at the official source. Re-select only if year context/source/file validity changes. | **NOT_IMPLEMENTED:** prior-year Roster path is not persisted/recovered across restart. |
| **FR-ROSTER-VALID-01** | Restored prior-year path must be checked for availability, readability, appropriate year/context and integrity sufficient to preserve returning-student IDs; moved/deleted/invalid files must produce a truthful blocking/recovery state where such a reference is needed. | **NOT_PROVEN/UNIMPLEMENTED AS AN END-TO-END LIFECYCLE:** no restored reference exists today; partial file validation is not proof of operational safety. |
| **FR-ROSTER-ID-01** | Returning students retain their one valid prior official registration ID by normalized national-ID matching; genuinely new students get new gender-specific numbering after the current Roster's already-used sequence, using the confirmed academic year. Never make “two valid historic IDs per student” an ordinary business rule. | **SOURCE_INSPECTED PARTIAL:** `counter.py` has prior-ID matching and current-Roster sequence logic; does not itself guarantee complete inputs or safe malformed-import handling. |
| **FR-ROSTER-FRESH-01** | UI must clearly distinguish “selected”, “exists/readable”, “operator confirms freshly downloaded for this run” and “independently verified fresh in official system” (the last capability is **not available**). Do not certify freshness from filename, timestamp, identical/different bytes, or an operator declaration. | **NOT_IMPLEMENTED:** no evidenced truthful per-run freshness interaction/enforcement. |
| **FR-ROSTER-RACE-01** | Concurrent, retried and overlapping Allocate attempts cannot silently rely on the same current-Roster snapshot as proof that official numbering remained unchanged. Detect risk, prevent unsupported assurance and require a safe operator response; do not invent a remote lock or transactional registration API. | **NOT_IMPLEMENTED/NEEDS FEASIBILITY:** concurrency coordination and official updates are outside current verified contract. |
| **UX-ROSTER-01** | Concept A Readiness Ledger must present both Roster roles separately: persisted/reused prior-year reference versus newly acquired current-year reference, and identify missing/stale/unchecked critical prerequisites, recovery action and confirmed Allocate year in FA/RTL and EN/LTR. | **CONDITIONAL_CONCEPT_WINNER, NOT IMPLEMENTED** for this lifecycle; Qt C2/V2 presentation locks retained. |

**Operational cycle:** Obtain newly downloaded current-year Roster → resolve a valid prior-year Roster (reuse safely where appropriate) → confirm academic-year start year (1 Tir boundary) → Allocate and inspect QA/output → register approved outputs in the official system → obtain a new current Roster for the next Allocate. Distinguish operator declaration from independent official-state verification; in particular, two valid downloads can have identical contents if no registration has been added.

### Bounded acceptance scenarios (synthetic/nonprivate fixtures first)

| ID | Scenario | Required evidence/result (not an implementation mechanism) |
| --- | --- | --- |
| **AC-RSTR-01** | First Allocate after 1 Tir, fresh academic-year context | Valid prior-year reference is provided, current-year Roster is freshly supplied, year is explicitly confirmed, returning IDs are preserved and new sequence follows current official snapshot. |
| **AC-RSTR-02** | Second Allocate in same open session | Previously selected current file alone is not silently treated as fresh; the operator must provide/attest the new download for this run. Prior-year reference may remain reused if valid. |
| **AC-RSTR-03** | Close and restart Matrix | Correct prior-year reference is restored with its year context and validated before reuse; absence/invalidity yields actionable correction instead of silent omission. |
| **AC-RSTR-04** | Switch to next academic year | Previously stored prior-year reference is not silently used in an incompatible context; appropriate new reference must be resolved and confirmed. |
| **AC-RSTR-05** | Previously valid prior-year Roster moved, deleted or corrupted | No fabricated successful identity continuity; explicit diagnosis, safe stop or correction and no silent “prior data optional” inference when returning students depend on it. |
| **AC-RSTR-06** | Current-year Roster omitted or old selected path retained | Allocate is blocked or otherwise fails closed under the approved per-run Roster requirement; the UI explains what to obtain from the official system. |
| **AC-RSTR-07** | Official registrations added between two runs | Second run requires a newly acquired snapshot; subsequent newly issued numbers must continue after IDs in that snapshot. |
| **AC-RSTR-08** | Newly downloaded snapshot has the same bytes as previous one | Do not claim it must be stale on hash/timestamp equality alone; distinguish operator acquisition claim from true official verification. |
| **AC-RSTR-09** | Two overlapping/competing runs share a numbered snapshot | No silent assertion that snapshot is still unique/current; a safe stop/coordination/reconciliation path is established without unauthorized changes to Core counting semantics. |
| **AC-RSTR-10** | Returning student vs genuinely new student | Same normalized national ID reuses the one valid historical registration ID; new student uses per-gender new sequence from confirmed year/current Roster; malformed, duplicate or corrupted input takes an explicit exceptional validation path. |
| **AC-RSTR-11** | FA/RTL and EN/LTR, keyboard, narrow/High-DPI | Operator can identify selected vs validated vs restored vs attested and can recover without hidden persistence or unsupported official-freshness claims. |
| **AC-RSTR-12** | Windows physical operator with representative synthetic data | Correct task comprehension/decision and expected file/QA outcomes are directly observed; Qt offscreen/CI pass alone is insufficient to close this acceptance. |

### Evidence, dependencies and priority (management, not LAW)

- **SOURCE_INSPECTED** on baseline: current GUI `_build_allocate_overrides` sends only nonempty optional Roster inputs; CLI `_read_optional_first_sheet` reads both optionally; prior path is not persisted via `AppPreferences`; Core has partial national-ID ID continuity and sequence behavior. No genuine official-system freshness verification exists; no physical Windows operator task observed for these new obligations.
- **P0 decision/feasibility for ID safety (D1/D2):** bounded read-only appraisal of Roster source of truth, persistence lifecycle, per-run refresh/attestation and overlapping-run risk as one coherent domain/UX contract **before** selecting a technical mechanism. Owner-approved requirement is not authorization to alter LAW, Core, CLI or policy. This is the next high-value backlog work package, subject to ongoing D3 native Windows crash investigation as a separate independent reliability blocker.
- **P1 implementation candidate:** after the bounded contract/feasibility return and separate Owner execution approval, implement the smallest cohesive year-scoped prior-Roster reuse + current-Roster per-run gate + truthful FA/EN feedback and focused regression suite. Evaluate race/overlap protection only after its authority and safe mechanism are resolved; do not promise complete prevention without official-system integration.
- **P2 validation:** physical Windows operator workflow, current/prior file states, positive/negative identity outcomes, access/keyboard/recovery and counter-result accuracy; source, Windows CI, Host render and owner acceptance are distinct evidence.
- **Standing issues:** Windows native Qt access violation in post-merge `main@4a1a064d...` CI run 42815198900 is **CI_OBSERVED FAILURE**, causal link to PR #55 not established; SQLite reference-readiness side effects remain under independent contract qualification; Concept A Readiness Ledger is a selected *conditional* UX direction, not an implemented product experience. Do not silently de-prioritize engineering safety or global D1–D5 objectives.
- **Pending Owner/LPM decisions, not guessed mechanisms:** how to treat overlap/locks between separate processes and external system writes; exact official-freshness evidence, if any integration can be authorized; scope of CLI enforcement vs GUI; acceptable handling of missing prior-year Roster when no returning student can be proven. No credentials, official connections, real student data or schema changes authorized here.

**Trace:** Owner direct decision `MATRIX-OPS-ROSTER-20261110-001`; docs PR #56 (unmerged) for the operational guide and owner decision record; the Vision D1/D2 Roster bullets are authorized outcomes, not evidence of deployment. This addendum does not modify PR #56, LAW v3.0, Technical SSoT v3.0, allocation/QA or release mechanics.

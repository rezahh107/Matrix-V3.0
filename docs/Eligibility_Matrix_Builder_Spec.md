# Eligibility Matrix Builder Spec (Policy v1.0.3, SSoT v1.0.2)

> **منبع حقیقت قوانین تخصیص (LAW v3.0 / Technical SSoT v3.0):** این سند راهنما/تاریخچه است؛ تمام قواعد ثابت (کلیدهای join، رتبه‌بندی، انواع منتور/دانش‌آموز، گیت ظرفیت، trace و ...) فقط در `docs/LAW_Smart_Student_Allocation_v3.0.md` و `docs/Technical_SSoT_Smart_Student_Allocation_v3.0-TECH.md` معتبرند. در صورت هر تعارض، محتوای این دو فایل حاکم است و نکات قدیمی این سند به‌عنوان LEGACY خوانده شوند.
## Scope
توصیف دقیق تولید ماتریس احراز صلاحیت 9354سطره با پوشش شاخهٔ عادی/مدرسه‌ای و ولیدیشن مبتنی بر کدپستی دانش‌آموز.

## ورودی‌ها
- **InspactorReport**: ستون‌های `کد کارمندی پشتیبان`, `کدپستی`, `تعداد مدارس تحت پوشش` و `کد مدرسه 1..4` برای تشخیص MentorType.
- **SchoolReport**: نگاشت «کد مدرسه» به نام مدرسه؛ کدهای نامعتبر به `unmatched_schools` می‌رود.
- **Crosswalk گروه آزمایشی**: name↔code + Synonyms/Buckets مطابق SSoT.
- **Policy**: `postal_valid_range`, `alias_rule.normal/school`, MentorSchoolBindingPolicy (school_constraint/global_mode).

## منطق تشخیص MentorType
- `classify_mentor_mode(postal_code, school_codes, has_school_constraint, cfg)`:
  - postal در بازهٔ policy ⇒ normal قابلیت عادی دارد.
  - school_code>0 یا school_constraint اجباری ⇒ قابلیت مدرسه‌ای دارد.
  - نتیجه: NORMAL / SCHOOL / DUAL (هر دو قابلیت).
- school_constraint در حالت compulsion اگر school_code معتبر یافت نشود، school_count=1 می‌شود تا SCHOOL/DUAL از دست نرود.

## تولید سطرهای ماتریس
- **Normal branch** (فقط وقتی alias_normal معتبر است):
  - `جایگزین = کدپستی 4رقمی` در بازه policy.
  - `عادی مدرسه=عادی`, `کد مدرسه=0`, `نام مدرسه=""`.
  - دو وضعیت ساخته می‌شود: `دانش آموز فارغ=1` و `دانش آموز فارغ=0`.
- **School branch** (فقط وقتی school_code>0 و has_school_constraint=True):
  - `جایگزین = کد کارمندی پشتیبان`، `عادی مدرسه=مدرسه‌ای`.
  - فقط وضعیت دانش‌آموز (`دانش آموز فارغ=1`) ساخته می‌شود؛ فارغ‌التحصیل حذف می‌شود.
- **Dual**: هر دو شاخه به‌صورت مستقل ساخته می‌شوند (۳ سطر برای هر گروه/مالی/جنسیت).
- ضرب‌کارتزین روی گروه‌های آزمایشی، مالی 0/1/3، جنسیت، مرکز و ۶ کلید join بدون تغییر باقی می‌ماند.

## Alias و بازهٔ کدپستی
- alias عادی خارج از بازه policy ⇒ شاخهٔ عادی ساخته نمی‌شود.
- alias مدرسه‌ای همیشه از mentor_id است؛ در خروجی عددی بدون `.0` می‌ماند.
- مقادیر alias<حداقل بازه (مثلاً <1000) در ولیدیشن دانش‌آموز به‌عنوان school-based تفسیر می‌شود و باید school_code معتبر داشته باشد.

## ولیدیشن با StudentReport
- مسیر انتخاب شاخه:
  - `<min(postal)>` ⇒ `school_by_schoolcode` (مطالبهٔ «کد مدرسه» روی سطرهای مدرسه‌ای).
  - `[min..max]` ⇒ `normal_by_alias` (جست‌وجوی سطر عادی با همان alias).
  - `>max` یا غیرعددی ⇒ `school_by_mentorid` (جست‌وجوی شاخهٔ مدرسه‌ای بر اساس mentor_id alias).
- پس از انتخاب شاخه، ترتیب چک‌ها: جنسیت → وضعیت → مرکز (از نام مدیر) → کدگروه (join_keys[0]). اولین خطا دلیل mismatch است.

## خروجی و شمارش
- سطر شمارندهٔ پایدار (`counter`) با sort پایدار center→کدرشته→کد مدرسه→alias.
- انتظار خروجی کامل: ~9354 سطر برای داده‌های فعلی (افزودن شاخهٔ مدرسه‌ای نسبت به روایت 0918).
- شیت‌های `validation`, `unmatched_schools`, `invalid_mentors`, `unseen_groups` بدون تغییر نام باقی می‌مانند.

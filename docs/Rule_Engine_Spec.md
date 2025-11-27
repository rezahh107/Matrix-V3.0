# Rule Engine Spec (Allocation Policy v1.0.3)

> **منبع حقیقت قوانین تخصیص (LAW v3.0 / Technical SSoT v3.0):** این سند راهنما/تاریخچه است؛ تمام قواعد ثابت (کلیدهای join، رتبه‌بندی، انواع منتور/دانش‌آموز، گیت ظرفیت، trace و ...) فقط در `docs/LAW_Smart_Student_Allocation_v3.0.md` و `docs/Technical_SSoT_Smart_Student_Allocation_v3.0-TECH.md` معتبرند. در صورت هر تعارض، محتوای این دو فایل حاکم است و نکات قدیمی این سند به‌عنوان LEGACY خوانده شوند.
## Purpose
همگام‌سازی Rule Engine با تعاریف جدید SCHOOL/NORMAL برای دانش‌آموز و پشتیبان تا مطابقت ولیدیشن و ماتریس حفظ شود.

## داده‌های ورودی Rule Engine
- `eligibility_matrix` خروجی Builder (شامل شاخهٔ عادی/مدرسه‌ای و alias مطابق policy).
- StudentReport نرمال‌شده (کد پستی/کد جایگزین، نام پشتیبان، مدیر، گروه آزمایشی، کد مدرسه).
- PolicyConfig شامل `postal_valid_range`, `alias_rule`, MentorSchoolBindingPolicy.

## قواعد دانش‌آموز
- **Routing by alias:**
  - `<min(postal_valid_range)>` ⇒ دانش‌آموز مدرسه‌ای (school_by_schoolcode) و Rule Engine باید فقط روی سطرهای `عادی مدرسه=مدرسه‌ای` جست‌وجو کند.
  - `[min..max]` ⇒ دانش‌آموز عادی (normal_by_alias) و جست‌وجوی دقیق alias روی شاخهٔ `عادی`.
  - `>max` یا غیرعددی ⇒ دانش‌آموز مدرسه‌ای (school_by_mentorid) با alias مبتنی بر mentor_id.
- **Status/Gender/Center/Group checks:** پس از انتخاب شاخه، Rule Engine باید همان ترتیب ولیدیشن را اجرا کند: جنسیت → وضعیت → مرکز از نام مدیر → کد گروه join_keys[0]. اولین mismatch دلیل شکست است.

## قواعد پشتیبان
- MentorType از Inspactor طبق SSoT v1.0.2:
  - postal معتبر ⇒ capability عادی.
  - school_code>0 یا school_constraint ⇒ capability مدرسه‌ای.
  - DUAL اگر هر دو فراهم باشد.
- شاخهٔ عادی فقط با alias چهارنمری در بازهٔ policy ساخته و مصرف می‌شود؛ شاخهٔ مدرسه‌ای همیشه با mentor_id و school_code>0 است.

## ماتریس و هم‌خطی
- Rule Engine باید فرض کند ماتریس دارای هر دو شاخه است (مجموعه کامل 9354سطره) و ۶ کلید join ثابت مانده‌اند.
- alias<حداقل بازه در ورودی دانش‌آموز هرگز نباید به شاخهٔ عادی مسیردهی شود؛ در غیر این صورت تطبیق false می‌شود.
- روایت 0918 (ماتریس 4212سطره بدون شاخهٔ مدرسه‌ای) دیگر معتبر نیست و نباید در قوانین استفاده شود.

## خروجی Rule Engine
- علت عدم تطبیق باید از بین دلایل استاندارد ولیدیشن (`no normal alias match`, `no mentor-id school match`, `no school-code match`, `gender mismatch`, `status mismatch`, `center mismatch`, `group_code mismatch`) انتخاب شود تا QA و ماتریس هماهنگ بمانند.

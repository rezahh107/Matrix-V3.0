# Managers Import Spec (ManagerReport)

> **منبع حقیقت قوانین تخصیص (LAW v3.0 / Technical SSoT v3.0):** این سند راهنما/تاریخچه است؛ تمام قواعد ثابت (کلیدهای join، رتبه‌بندی، انواع منتور/دانش‌آموز، گیت ظرفیت، trace و ...) فقط در `docs/LAW_Smart_Student_Allocation_v3.0.md` و `docs/Technical_SSoT_Smart_Student_Allocation_v3.0-TECH.md` معتبرند. در صورت هر تعارض، محتوای این دو فایل حاکم است و نکات قدیمی این سند به‌عنوان LEGACY خوانده شوند.
## Input File
- Expected source: ManagerReport-YYYY_MM_DD-XXXX.xlsx

## Field Mapping
- manager_id ← "کد مدیر" (اگر نبود، هش از نام+شماره)
- name ← "نام مدیر"
- relations:
  - mentors.manager_id باید به این جدول وصل شود.

## Source Columns (auto-detected snapshot)
{
  "path": "/mnt/data/ManagerReport-1404_05_19-3570.xlsx",
  "sheets": [
    "ManagerList3570"
  ],
  "columns": [
    "کد نمایندگی",
    "کد کارمندی مدیر",
    "کد مدیر",
    "نام مدیر",
    "جنسیت",
    "موبایل",
    "قبلا پشتیبان بود",
    "عادی",
    "اموزشگاه",
    "مدرسه",
    "شمارنده",
    "تعداد پشتیبان عادی",
    "تعداد پشتیبان آموزشگاه",
    "تعداد پشتیبان مدرسه"
  ]
}

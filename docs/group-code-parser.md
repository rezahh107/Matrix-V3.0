# Group Code Parser Spec

> **منبع حقیقت قوانین تخصیص (LAW v3.0 / Technical SSoT v3.0):** این سند راهنما/تاریخچه است؛ تمام قواعد ثابت (کلیدهای join، رتبه‌بندی، انواع منتور/دانش‌آموز، گیت ظرفیت، trace و ...) فقط در `docs/LAW_Smart_Student_Allocation_v3.0.md` و `docs/Technical_SSoT_Smart_Student_Allocation_v3.0-TECH.md` معتبرند. در صورت هر تعارض، محتوای این دو فایل حاکم است و نکات قدیمی این سند به‌عنوان LEGACY خوانده شوند.
Grammar:
- Accepts tokens separated by comma `,`, Persian comma `،`, or whitespace.
- A range token `a:b` expands to all integers from a to b inclusive.
- Single integers allowed. Persian/English digits allowed.
- **Source column:** Only the Inspactor column «شامل گروه های آزمایشی» is authoritative for mentor `group_code`. The legacy «گروه آزمایشی» column may be retained for QA/debug but MUST NOT drive join keys.

Examples:
- "1,3,5,7:9"  -> [1,3,5,7,8,9]
- "۲ ، ۴ ، ۶:۸" -> [2,4,6,7,8]
- "10 12 14:16" -> [10,12,14,15,16]

Validation:
- Non-integer tokens are ignored with a warning in logs.

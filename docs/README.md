# مستندات Core Policy Adapter

> **منبع حقیقت قوانین تخصیص (LAW v3.0 / Technical SSoT v3.0):** این سند راهنما/تاریخچه است؛ تمام قواعد ثابت (کلیدهای join، رتبه‌بندی، انواع منتور/دانش‌آموز، گیت ظرفیت، trace و ...) فقط در `docs/LAW_Smart_Student_Allocation_v3.0.md` و `docs/Technical_SSoT_Smart_Student_Allocation_v3.0-TECH.md` معتبرند. در صورت هر تعارض، محتوای این دو فایل حاکم است و نکات قدیمی این سند به‌عنوان LEGACY خوانده شوند.
- نسخه Policy: 1.0.3 — منبع واحد حقیقت برای نام ستون‌ها و مراحل Trace.
- آداپتور: `app/core/policy_adapter.py` خواندن JSON را متمرکز و کش می‌کند.
- فیلترها و Trace مستقیماً ستون را از Policy می‌گیرند؛ بدون هاردکد در Core.
- نرمال‌سازی ورودی در لایهٔ Reader ارقام فارسی/عربی و هدرها را یکسان می‌کند.
- تست پذیرش `tests/test_allocation_system.py` تضمین می‌کند تغییر JSON بدون تغییر کد رفتار را عوض می‌کند.

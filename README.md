# سامانه تخصیص دانشجو-منتور (نسخه معماری مدولار)

> **منبع حقیقت قوانین تخصیص (LAW v3.0 / Technical SSoT v3.0):** این مخزن باید قوانین ثابت (۶ کلید join، رتبه‌بندی RANK-CORE بر اساس ظرفیت باقی‌مانده، انواع منتور/دانش‌آموز، گیت ظرفیت، trace) را فقط از `docs/LAW_Smart_Student_Allocation_v3.0.md` و `docs/Technical_SSoT_Smart_Student_Allocation_v3.0-TECH.md` بگیرد. این README راهنمای اجراست؛ هر تعارض با LAW/TECH یا روایت‌های قدیمی (مانند occupancy_ratio) LEGACY محسوب می‌شود.

## اجرا
```bash
uv sync --locked
uv run --locked python -m app.main
```

## ساخت فایل اجرایی (PyInstaller)
```bash
uv sync --locked --group packaging
uv run --locked --group packaging pyinstaller --onefile --windowed --name تخصیص_دانشجو_منتور \
  --collect-all PySide6 --hidden-import openpyxl --hidden-import pandas.io.formats.excel \
  app/main.py
```

## Policy-First در Core

- تمامی نام ستون‌ها، مراحل Trace و فیلترها از فایل `config/policy.json` خوانده می‌شوند.
- کلاس `PolicyAdapter` در `app/core/policy_adapter.py` تنها نقطهٔ دسترسی به تنظیمات Policy است.
- برای تغییر رفتار فیلترها، تنها کافی است JSON را ویرایش کنید؛ نیازی به تغییر کد نیست.
- ستون ظرفیت از مرحلهٔ `capacity_gate` گرفته می‌شود و برای Override می‌توان پارامتر صریح به تابع تخصیص داد.

## نرمال‌سازی ورودی

- حروف عربی (ي/ك) و ارقام فارسی/عربی به معادل فارسی/لاتین تبدیل می‌شوند.
- فاصله‌ها، نیم‌فاصله و کاراکترهای ترکیبی حذف می‌شوند تا مقایسهٔ ستون‌ها پایدار بماند.
- آلیاس‌ها از Policy برای سازگاری با گزارش Inspactor و Crosswalk استفاده می‌شوند.

## تست‌های سیاست‌محور

- `uv run --locked pytest -q` سناریوهای ترجیح «کدرشته» بر نام گروه و مصرف ستون ظرفیت از Policy را پوشش می‌دهد.
- تغییر JSON (مثلاً تغییر نام ستون ظرفیت) باید بدون تغییر کد باعث تغییر رفتار تخصیص شود.

## 🏢 مدیریت مراکز

سیستم از مدیریت پیشرفته مراکز پشتیبانی می‌کند که به شما امکان می‌دهد مراکز مختلف را تعریف کرده و برای هر مرکز مدیران مشخصی تعیین کنید.

### پیکربندی مراکز

مراکز در فایل `policy.yaml` تعریف می‌شوند:

```yaml
center_management:
  enabled: true
  default_center_for_invalid: 0
  strict_manager_validation: false
  school_student_column: "is_school_student"
  
  centers:
    - id: 1
      name: "گلستان"
      default_manager: "شهدخت کشاورز"
      description: "مرکز گلستان"
      
    - id: 2  
      name: "صدرا"
      default_manager: "آیناز هوشمند" 
      description: "مرکز صدرا"
      
    - id: 0
      name: "مرکزی"
      default_manager: null
      description: "مرکز اصلی"
  
  priority_order: [1, 2, 0]
```

### استفاده از طریق UI

1. در تب "تخصیص"، بخش "مدیریت مراکز" را پیدا کنید
2. برای هر مرکز، مدیر مورد نظر را از dropdown انتخاب کنید
3. از دکمه‌های زیر استفاده کنید:
   - **بازنشانی به پیش‌فرض**: بازگشت به مقادیر Policy
   - **بارگذاری مجدد مدیران**: به‌روزرسانی لیست مدیران از فایل استخر

> **نکته درباره فناوری UI:** رابط کاربری روی **PySide6/Qt** پیاده‌سازی شده و در حال حاضر هیچ لایه‌ی سازگاری یا Bridge با Tkinter ندارد؛ برای استفاده از Tkinter باید یک Adapter جدید نوشته شود یا از CLI بهره بگیرید.

> **جایگزین‌های پیشنهادی برای UI:**
> - **CLI موجود**: برای خودکارسازی و اسکریپت‌نویسی بدون نیاز به GUI (مسیر کم‌ریسک برای نگهداشت Policy).
> - **Tkinter سبک**: یک entry point جدید بسازید که رویدادهای Tkinter را به همان دستورات CLI نگاشت کند تا از منطق هسته جدا بماند.
> - **TUI/متنی (مثلاً Textual/Rich)**: رابط ترمینالی با کنترل ورودی‌های Policy محور؛ وابستگی گرافیکی ندارد و برای استقرار روی سرور مناسب است.
> - **وب‌اپ کوچک (FastAPI/Flask + HTMX)**: اگر نیاز به چند کاربر یا اجرا در مرورگر دارید، می‌توان از API موجود بهره گرفت و لایه ارائه را وبی کرد.

### استفاده از طریق CLI

```bash
# تنظیم مدیران برای مراکز مختلف
uv run --locked python -m app.cli allocate \
  --center-manager 1="شهدخت کشاورز" \
  --center-manager 2="آیناز هوشمند" \
  --center-priority 1,2,0

# فعال‌سازی validation سخت‌گیرانه
uv run --locked python -m app.cli allocate \
  --center-manager 1="مدیر گلستان" \
  --strict-manager-validation
```

### الگوریتم تخصیص

1. **جداسازی دانش‌آموزان**: 
   - دانش‌آموزان مدرسه‌ای (بر اساس ستون مشخص شده)
   - دانش‌آموزان مرکزی

2. **ترتیب پردازش**:
   - ابتدا تمام دانش‌آموزان مدرسه‌ای
   - سپس دانش‌آموزان مرکزی به ترتیب اولویت مراکز

3. **فیلتر مدیر**:
   - هر دانش‌آموز فقط به مدیران مرکز خودش تخصیص می‌یابد
   - در صورت نبود مدیر، هشدار داده می‌شود

### عیب‌یابی

**مشکل: مدیران در dropdown نشان داده نمی‌شوند**
- مطمئن شوید فایل استخر انتخاب شده است
- بررسی کنید ستون `manager_name` در فایل استخر وجود دارد

**مشکل: دانش‌آموزان به مدیر اشتباه تخصیص می‌یابند**
- مقادیر مرکز دانش‌آموزان را بررسی کنید
- تنظیمات مدیران هر مرکز را بررسی کنید

**مشکل: خطای "مرکز نامعتبر"**
- مقادیر مرکز در دیتای دانش‌آموزان را بررسی کنید
- از `default_center_for_invalid` در Policy استفاده کنید

## هشدار خروجی Excel

- فایل‌های Excel تولیدشده فونت‌های Vazir/Vazirmatn را **جاسازی نمی‌کنند**؛ برای اشتراک‌گذاری با سیستم‌های فاقد فونت، خروجی را به PDF تبدیل کنید.

## مستندات تکمیلی

- راهنمای کامل اپراتور GUI: [docs/SmartAlloc_GUI_Operator_Guide.fa.md](docs/SmartAlloc_GUI_Operator_Guide.fa.md)
- چک‌لیست QA سرتاسری: [docs/SmartAlloc_E2E_QA_Checklist.fa.md](docs/SmartAlloc_E2E_QA_Checklist.fa.md)
- نکات QA برای تیم توسعه: [docs/SmartAlloc_Dev_QA_Notes.md](docs/SmartAlloc_Dev_QA_Notes.md)
- خروجی آرتیفکت QA برای خطای `QA_RULE_MENTOR_TYPE_01` در مسیر `artifacts/qa_offenders.json` کنار خروجی اجرا ذخیره می‌شود.

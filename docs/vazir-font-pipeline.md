# مسیر فونت C2/V2 در Matrix-V3.0

> **جایگاه این سند:** این فایل راهنمای عملیاتی/فنی فونت UI است. قواعد دامنه همچنان فقط از `docs/LAW_Smart_Student_Allocation_v3.0.md` و `docs/Technical_SSoT_Smart_Student_Allocation_v3.0-TECH.md` می‌آیند. برای composition و typography در presentation، `docs/UI_DESIGN_CONTRACT.md` مرجع C2/V2 است. این سند هیچ authority مستقل جدیدی ایجاد نمی‌کند.

## 1) authority فونت در سطح برنامه

authority جهت و خانوادهٔ فونت در سطح `QApplication` قرار دارد:

- `app/ui/theme.py::apply_layout_direction()` ابتدا جهت FA/RTL یا EN/LTR را اعمال می‌کند و سپس `apply_global_font()` را فراخوانی می‌کند.
- `app/ui/theme.py::apply_global_font()` تنها enforcement boundary خانوادهٔ پایه است: family هدف را با همان منطق جهت‌دار و `create_app_font()` resolve می‌کند، آن را روی `QApplication` می‌گذارد و widgetهای موجودِ واجد شرایط را به‌صورت مرکزی به family جدید rebind می‌کند.
- widgetهای ordinary/base-text خانوادهٔ FA/EN مستقلی انتخاب نمی‌کنند؛ widgetهای جدید از font پایهٔ فعال `QApplication` استفاده می‌کنند.
- اگر یک widget به نقش semantic متفاوتی مانند اندازه یا weight بزرگ‌تر نیاز داشته باشد، آن تغییر باید از font فعلی application/inherited مشتق شود و family فعال را حفظ کند.

رفتار جهت‌دار C2/V2:

- **FA / RTL:** ابتدا `Vazirmatn`/`Vazir` تعبیه‌شده؛ در صورت عدم دسترسی، fallback امن فارسی از زنجیرهٔ موجود استفاده می‌شود.
- **EN / LTR:** ابتدا `Segoe UI` و سپس fallbackهای امن موجود.
- اندازهٔ پایهٔ فعلی UI برابر `10pt` و weight پایه `Regular / 400` است.

`create_app_font()` یک factory سطح پایین/compatibility است؛ این helper به‌تنهایی language authority برنامه نیست. `get_app_font()` نیز برای compatibility/semantic sizing است و نباید توسط widgetهای ordinary به‌عنوان انتخاب‌کنندهٔ مستقل family استفاده شود.

## 2) ثبت Vazirmatn در حافظهٔ Qt

فونت اصلی به‌صورت base64 در `app/ui/assets/font_data_vazirmatn.py` نگه‌داری می‌شود. production startup مسیر زیر را استفاده می‌کند:

1. `_embedded_font_bytes()` payload تعبیه‌شده را decode می‌کند.
2. `_register_embedded_vazirmatn()` با `QFontDatabase.addApplicationFontFromData()` bytes را مستقیماً در حافظهٔ Qt ثبت می‌کند.
3. `resolve_vazir_family_name()` family ثبت‌شده را resolve می‌کند.
4. در مسیر FA/RTL، `apply_global_font()` همان family را در سطح `QApplication` فعال می‌کند.

production startup برای این کار **هیچ TTFای داخل source/install directory نمی‌نویسد**.

## 3) materialization و مسیرهای development

Disk materialization یک seam صریح development/test است، نه رفتار production:

- `ensure_vazir_local_fonts()` فقط directory صریح `FONTS_DIR` را ایجاد می‌کند و TTF تعبیه‌شده را خودکار materialize نمی‌کند.
- `_materialize_embedded_font(target_dir)` فقط وقتی caller صریحاً یک directory writable می‌دهد، `Vazirmatn-Regular.ttf` را برای development/test می‌سازد.
- `_windows_candidates()` فقط مسیرهایی را می‌خواند که صریحاً از طریق `VAZIR_FONT_PATHS` opt-in شده‌اند.
- production مسیرهای `Downloads` یا `LocalAppData` را به‌طور خودکار scan یا copy نمی‌کند.

وجود فایل قدیمی یا دستی در `app/ui/fonts/` authority production نیست. منبع اصلی production همان embedded bytes ثبت‌شده در حافظهٔ Qt است.

## 4) propagation در widgetهای موجود

قاعدهٔ C2/V2 این است که ordinary text controls خانوادهٔ فونت مستقل نگه ندارند و تغییر زبان بدون reconstruction انجام شود. با این حال، یک تغییر صرف در default font سطح `QApplication` یا یک `QFont()` بدون family override **به‌تنهایی تضمین نمی‌کند** که تمام widgetهای از قبل ساخته‌شده family resolve‌شدهٔ خود را در همهٔ مسیرهای Qt/QSS فوراً عوض کنند.

مدل runtime فعلی به‌صورت مرکزی داخل `apply_global_font()` این مسئله را می‌بندد:

1. قبل از تغییر font برنامه، family فعلی `QApplication` ثبت می‌شود.
2. population موجود widgetها از `QApplication.allWidgets()` snapshot می‌شود و برای هر widget یک `captured QFont` از وضعیت پیش از mutation نگه‌داری می‌شود.
3. family هدف با همان authority جهت‌دار موجود resolve می‌شود و `QApplication` به font جدید تغییر می‌کند.
4. فقط widgetهایی eligible هستند که family موجود در `captured QFont` آن‌ها با family قبلی application برابر بوده باشد.
5. برای هر widget واجد شرایط، از همان `captured QFont` یک copy ساخته می‌شود و فقط family آن با `setFamily()` به family هدف تغییر می‌کند.

این روش عمداً کل `QApplication.font()` را روی همهٔ widgetها overwrite نمی‌کند؛ بنابراین `pointSize`، `weight`، italic/style و سایر تفاوت‌های semantic موجود حفظ می‌شوند. widgetهایی که family متفاوت و مستقل داشته‌اند نیز با این predicate دست‌کاری نمی‌شوند.

برای compatibility با بخش‌های قدیمی، `get_app_font()` در فراخوانی بدون semantic size همچنان یک `QFont` بدون family override برمی‌گرداند و دو call قدیمی `setFont(get_app_font())` حفظ شده‌اند. صحت تغییر family این seam به inheritance پویا و تضمین‌نشدهٔ `QFont()` متکی نیست؛ همان central previous-family → target-family rebind آن را پوشش می‌دهد.

widgetهای جدیدی که پس از transition ساخته می‌شوند، font پایهٔ جاری `QApplication` را به‌طور عادی دریافت می‌کنند. هیچ widget به‌صورت مستقل تصمیم نمی‌گیرد که برای FA یا EN چه familyای انتخاب شود.

نقش‌های semantic مانند heading می‌توانند copy فونت فعال application را بگیرند و فقط `pointSize`، `weight` یا style لازم را تغییر دهند؛ family نباید دوباره در سطح widget انتخاب شود.

## 5) تست و evidence

پوشش فعال باید این موارد را اثبات کند:

- `tests/unit/test_ui_fonts.py`: factory/compatibility helperها دیگر EN authority را با legacy `Tahoma` یکی نمی‌گیرند.
- `tests/ui/test_theme_and_fonts.py`: رفتار FA/RTL و EN/LTR، transition واقعی FA → EN → FA روی widgetهای موجود، و حفظ semantic point-size/weight/style هنگام family rebinding.
- `tests/ui/test_font_materialization.py`: registration در حافظه بدون disk write، materialization صریح development/test و نبود scan خودکار Downloads/LocalAppData.
- `tools/render_ui_matrix.py`: evidence تصویری C2/V2 روی exact Head.
- `tools/validate_ui_dpi.py`: evidence High-DPI روی exact Head.

CI باید exact checkout را حفظ کند و Core/UI/render/DPI را از workflow موجود اجرا کند.

## 6) عیب‌یابی

برای بررسی font runtime:

1. `QApplication.font().family()` و `QApplication.layoutDirection()` را با زبان فعال مقایسه کنید.
2. در FA/RTL انتظار family از خانوادهٔ `Vazirmatn`/`Vazir` است؛ در EN/LTR روی Windows مسیر پشتیبانی‌شده انتظار `Segoe UI` است.
3. برای widget موجود، family قبل و بعد از transition را همراه با `pointSize` و `weight` بررسی کنید؛ widget واجد شرایط باید family جدید را بگیرد و semantic properties خود را حفظ کند.
4. `collect_font_diagnostics()` را برای `embedded_bytes`، `embedded_families` و `explicit_dev_paths` بررسی کنید.
5. نبود `Vazirmatn-Regular.ttf` در `app/ui/fonts/` به‌تنهایی خطا نیست؛ production برای بارگذاری font به materialization روی دیسک وابسته نیست.
6. اگر development به font file واقعی نیاز دارد، `_materialize_embedded_font()` را فقط با directory صریح test/dev استفاده کنید یا `VAZIR_FONT_PATHS` را صریحاً تنظیم کنید.

## 7) خروجی Excel

فونت Excel موضوع جداگانهٔ Infra است و این C2/V2 font-authority migration آن را تغییر نمی‌دهد. فایل Excel خود font را embed نمی‌کند؛ رفتار formatting/export باید با تست‌های Infra مربوط به خودش ارزیابی شود.

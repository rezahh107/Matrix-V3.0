# مسیر فونت C2/V2 در Matrix-V3.0

> **جایگاه این سند:** این فایل راهنمای عملیاتی/فنی فونت UI است. قواعد دامنه همچنان فقط از
> `docs/LAW_Smart_Student_Allocation_v3.0.md` و
> `docs/Technical_SSoT_Smart_Student_Allocation_v3.0-TECH.md` می‌آیند. برای composition و
> typography در presentation، `docs/UI_DESIGN_CONTRACT.md` مرجع C2/V2 است. این سند authority
> مستقل جدیدی ایجاد نمی‌کند.

## 1) authority فونت در سطح برنامه

authority جهت و خانوادهٔ فونت در سطح `QApplication` قرار دارد:

- `app/ui/theme.py::apply_layout_direction()` جهت FA/RTL یا EN/LTR را اعمال و سپس
  `apply_global_font()` را فراخوانی می‌کند.
- `app/ui/theme.py::apply_global_font()` enforcement boundary خانوادهٔ پایه است؛ family هدف را
  resolve می‌کند، روی `QApplication` می‌گذارد و widgetهای موجود واجد شرایط را centrally rebind
  می‌کند.
- widgetهای ordinary/base-text خانوادهٔ پایهٔ مستقلی انتخاب نمی‌کنند.
- semantic size/weight از font فعال application/inherited مشتق می‌شود و family فعال را حفظ می‌کند.

رفتار جهت‌دار C2/V2:

- **FA / RTL:** `Vazirmatn` embedded variable font؛ fallbackهای امن موجود فقط در صورت شکست
  registration به کار می‌روند.
- **EN / LTR:** ابتدا `Segoe UI` و سپس fallbackهای امن موجود.
- اندازهٔ پایهٔ UI `10pt` و weight پایه `Regular / 400` باقی می‌ماند.

نقش‌های semantic موجود نیز تغییر نکرده‌اند: `500` برای Medium، `600` برای
DemiBold/SemiBold و `700` برای Bold، هر جا که همان role قبلاً درخواست شده باشد. این repair
هیچ global-bold policy اضافه نمی‌کند.

## 2) artifact دقیق و ثبت در حافظهٔ Qt

production asset در `app/ui/assets/font_data_vazirmatn.py` یک payload واحد و pinned است:

- family: `Vazirmatn`
- full name: `Vazirmatn Regular`
- version: `Version 33.003`
- `OS/2 usWeightClass`: `400`
- variable axis: `wght` از `100` تا `900` با default `400`
- variable tables: `fvar`, `gvar`, `HVAR`
- decoded size: `241328`
- SHA-256: `696249a2c74b39ffdef55de4df2809c5b639d3ff80d618d8160a095d2fd49dca`

مسیر production:

1. `_embedded_font_bytes()` canonical variable payload را decode می‌کند.
2. `_register_embedded_vazirmatn()` با `QFontDatabase.addApplicationFontFromData()` bytes را
   مستقیماً در حافظهٔ Qt ثبت می‌کند.
3. `resolve_vazir_family_name()` family ثبت‌شده را resolve می‌کند.
4. در FA/RTL، `apply_global_font()` همان family را در سطح `QApplication` فعال می‌کند.

production startup برای این کار **هیچ TTFای داخل source/install directory نمی‌نویسد**.

وجود family صحیح به‌تنهایی provenance را ثابت نمی‌کند؛
`tests/ui/test_font_materialization.py` decoded size و SHA-256 دقیق را guard می‌کند.

## 3) materialization و مسیرهای development

Disk materialization یک seam صریح development/test است، نه رفتار production:

- `ensure_vazir_local_fonts()` فقط directory صریح `FONTS_DIR` را ایجاد می‌کند و TTF تعبیه‌شده را
  خودکار materialize نمی‌کند.
- `_materialize_embedded_font(target_dir)` فقط با directory writable صریح caller فایل
  `Vazirmatn-Variable.ttf` را برای development/test می‌سازد.
- `_windows_candidates()` فقط مسیرهایی را می‌خواند که صریحاً از طریق `VAZIR_FONT_PATHS`
  opt-in شده‌اند.
- production مسیرهای `Downloads` یا `LocalAppData` را به‌طور خودکار scan یا copy نمی‌کند.

وجود فایل قدیمی یا دستی در `app/ui/fonts/` authority production نیست. منبع اصلی production همان
embedded bytes ثبت‌شده در حافظهٔ Qt است.

## 4) propagation در widgetهای موجود

ordinary text controls خانوادهٔ فونت مستقل نگه نمی‌دارند و تغییر زبان بدون reconstruction انجام
می‌شود. یک تغییر صرف در default font سطح `QApplication` یا یک `QFont()` بدون family override
**به‌تنهایی تضمین نمی‌کند** که تمام widgetهای از قبل ساخته‌شده family resolve‌شدهٔ خود را فوراً
عوض کنند.

runtime فعلی داخل `apply_global_font()` این boundary را می‌بندد:

1. family فعلی `QApplication` پیش از تغییر ثبت می‌شود.
2. widgetها از `QApplication.allWidgets()` snapshot می‌شوند و برای هر کدام یک `captured QFont`
   نگه‌داری می‌شود.
3. family هدف resolve و application font تغییر می‌کند.
4. فقط widgetهایی eligible هستند که family موجود در `captured QFont` آن‌ها با family قبلی
   application برابر باشد.
5. از همان `captured QFont` copy ساخته می‌شود و فقط family با `setFamily()` تغییر می‌کند.

بنابراین `pointSize`، `weight` و سایر ویژگی‌های semantic حفظ می‌شوند و FA → EN → FA یا
EN → FA → EN نیازمند reconstruction widget نیست.

## 5) variable-weight regression

asset pinned باید realization وزن‌های semantic را ممکن کند:

```text
400 → 400
500 → 500
600 → 600
700 → 700
```

regression test از requested `QFont.weight()` به‌تنهایی استفاده نمی‌کند؛ `QFontInfo` و
`QRawFont` برای family/weight resolved بررسی می‌شوند. مرزهای اصلی این‌اند که `500` به `400`
collapse نشود و `600` به `700` resolve نشود. representative Persian glyph coverage نیز از
`QRawFont` بررسی می‌شود.

برای acceptance نهایی Windows، runtime oracle باید روی Windows native با
`QT_QPA_PLATFORM=windows` اجرا شود؛ رفتار `offscreen` به‌تنهایی جایگزین این oracle نیست.

## 6) تست و evidence

پوشش فعال:

- `tests/unit/test_ui_fonts.py`: factory/compatibility helperها.
- `tests/ui/test_theme_and_fonts.py`: FA/RTL و EN/LTR، transition روی widgetهای موجود، و حفظ
  semantic point-size/weight/style هنگام family rebinding.
- `tests/ui/test_font_materialization.py`: exact embedded-byte provenance، registration در حافظه
  بدون disk write، development materialization، variable-weight realization و Persian glyphs.
- `tools/render_ui_matrix.py`: evidence تصویری C2/V2.
- `tools/validate_ui_dpi.py`: evidence High-DPI.

CI باید exact PR Head را checkout و تست کند. PNG generation به‌تنهایی visual inspection محسوب
نمی‌شود.

## 7) provenance و license

artifact copyright metadata:

`Copyright 2015 The Vazirmatn Project Authors (https://github.com/rastikerdar/vazirmatn)`

license: `SIL Open Font License, Version 1.1`.

`app/ui/assets/fonts/LICENSE.md` متن `OFL.txt` رسمی upstream Vazirmatn را نگه می‌دارد. منبع
authoritative license text، upstream project و متن رسمی SIL OFL 1.1 است؛ license قدیمی
Bitstream/DejaVu برای bundled Vazirmatn authority نیست.

## 8) عیب‌یابی

1. `QApplication.font().family()` و `QApplication.layoutDirection()` را با زبان فعال مقایسه کنید.
2. در FA/RTL انتظار `Vazirmatn` است؛ در EN/LTR روی Windows انتظار `Segoe UI` است.
3. برای weight realization، requested weight را با `QFontInfo.weight()` و `QRawFont.weight()`
   مقایسه کنید.
4. برای widget موجود، family قبل و بعد transition را همراه `pointSize` و `weight` بررسی کنید.
5. `collect_font_diagnostics()` را برای `embedded_bytes`، `embedded_families` و
   `explicit_dev_paths` بررسی کنید.
6. نبود `Vazirmatn-Variable.ttf` روی دیسک خطا نیست؛ production به materialization وابسته نیست.

## 9) خروجی Excel

فونت Excel موضوع جداگانهٔ Infra است و این repair آن را تغییر نمی‌دهد.

# Bundled UI Font

فونت deterministic رابط فارسی Matrix3 همان artifact متغیر `Vazirmatn[wght].ttf` است که
به‌صورت Base64 در `app/ui/assets/font_data_vazirmatn.py` نگه‌داری می‌شود. production به فایل
TTF جداگانه یا نصب سراسری Vazirmatn وابسته نیست.

## Artifact authority

- family: `Vazirmatn`
- subfamily: `Regular`
- full name: `Vazirmatn Regular`
- PostScript name: `Vazirmatn-Regular`
- version: `Version 33.003`
- variable axis: `wght` (`100..900`, default `400`)
- required tables: `fvar`, `gvar`, `HVAR`
- byte length: `241328`
- SHA-256: `696249a2c74b39ffdef55de4df2809c5b639d3ff80d618d8160a095d2fd49dca`
- copyright: `Copyright 2015 The Vazirmatn Project Authors`
- upstream: `https://github.com/rastikerdar/vazirmatn`
- license: `SIL Open Font License, Version 1.1`

این fingerprint بخشی از contract است. فایل دیگری با همان filename، یک release جدیدتر، یا فونتی
که فقط family مشابه دارد جایگزین معتبر این artifact محسوب نمی‌شود.

## Runtime model

`app.ui.fonts` payload را decode می‌کند و با
`QFontDatabase.addApplicationFontFromData()` مستقیماً در حافظهٔ Qt ثبت می‌کند. مسیر production:

```text
embedded exact bytes
→ QFontDatabase.addApplicationFontFromData()
→ Vazirmatn
→ QApplication/theme authority
```

هیچ scan خودکار `Downloads` یا `LocalAppData` و هیچ نیاز production به globally-installed
Vazirmatn وجود ندارد. Materialization روی دیسک فقط seam صریح development/test است و فایل
توسعه‌ای آن `Vazirmatn-Variable.ttf` نام دارد.

## Semantic weights

base typography همچنان `10pt Regular / 400` است. variable asset برای این است که semantic
weightهای موجود بدون redesign مقیاس typography قابل realization باشند:

- Regular: `400`
- Medium: `500`
- DemiBold/SemiBold: `600`
- Bold: `700`

## Updating the pinned asset

این asset نباید خودکار با «latest Vazirmatn» جایگزین شود. هر تغییر آینده باید آگاهانه انجام شود و
هم‌زمان fingerprint، provenance/license documentation و regression guardهای
`tests/ui/test_font_materialization.py` را به artifact جدید pin کند. Base64 wrapping می‌تواند تغییر
کند، اما decoded bytes باید دقیقاً fingerprint ثبت‌شده را بازتولید کند.

متن مجوز bundled font در `app/ui/assets/fonts/LICENSE.md` از `OFL.txt` رسمی پروژهٔ Vazirmatn
گرفته شده است.

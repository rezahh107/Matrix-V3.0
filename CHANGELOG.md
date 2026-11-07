# Changelog

All notable changes to this project will be documented in this file.

Application package version is sourced from `pyproject.toml`. Historical entries below are not evidence of published GitHub Releases; the first official release version is not yet approved.

## [Unreleased]
- قابلیت زیرساختی انتشار دستی GitHub Release با تأیید Owner، کنترل SHA/نسخه و آرشیو کامل عمومی، CI دقیق Windows و بازیابی بدون تغییر تاریخچه؛ **پیاده‌سازی در PR، بدون انتخاب نسخهٔ نخست و بدون انتشار**.
- مسیر شخصی Git+uv برای انتخاب صریح تگ مصوب، نسخه‌های worktree مجزا، rollback بدون حذف داده و مستندسازی بکاپ/مرز انتشار؛ بدون انتخاب نخستین نسخهٔ رسمی.
### Added
- Governed uv source-candidate identity, version/lock checks and review-only privacy signaling; no official version or publication selected.
- **سیستم مدیریت مراکز پیشرفته**: پشتیبانی از مراکز پویا و مبتنی بر Policy
  - تعریف مراکز در فایل `policy.yaml` با قابلیت افزودن مراکز جدید بدون تغییر کد
  - UI پویا که به طور خودکار با مراکز تعریف شده در Policy به‌روز می‌شود
  - CLI آرگومان‌های پیشرفته برای مدیریت مراکز (`--center-manager`, `--center-priority`)
  - تابع `resolve_center_manager_config` برای ادغام تنظیمات از Policy، UI و CLI
  - validation کامل برای مدیران و مراکز

- **الگوریتم تخصیص پیشرفته**:
  - پردازش دانش‌آموزان مدرسه‌ای قبل از مرکزی
  - ترتیب اولویت مراکز (1 → 2 → 0)
  - handle کردن دانش‌آموزان با مرکز نامعتبر
  - هشدارهای جامع برای خطاهای مختلف

- **رابط کاربری بهبود یافته**:
  - بخش مدیریت مراکز با ComboBoxهای پویا
  - دکمه‌های "بازنشانی به پیش‌فرض" و "بارگذاری مجدد مدیران"
  - error handling پیشرفته با QMessageBox
  - مدیریت تنظیمات با اعتبارسنجی کامل

- **مستندات و تست‌ها**:
  - Docstrings فارسی کامل برای تمام توابع
  - Type hints دقیق
  - تست‌های واحد برای منطق مدیریت مراکز
  - تست‌های integration برای UI
  - تست‌های edge case برای سناریوهای مختلف

### Changed
- **تغییرات سازگار با گذشته**:
  - حفظ compatibility با آرگومان‌های CLI قدیمی
  - بهبود performance با حفظ مرتب‌سازی‌های پایدار
  - جداسازی منطق business از UI

### Fixed
- رفع مشکل validation نبود مدیر
- رفع مشکل handle کردن مقادیر center نامعتبر
- بهبود پیام‌های خطا و هشدار به کاربر

## [0.1.0] - 2026-11-07

> **Proposed first Owner-only personal-release candidate; NOT an approved or published release.** The date above is the candidate preparation date, not the official release date. This section describes the already implemented baseline, not features all introduced today.

- Windows PySide6 application with Policy/LAW-governed matrix building, allocation, QA/Trace/History and Excel/Sabt-oriented workflows; real organizational Sabt acceptance is not established.
- Existing version-selectable Git+uv personal installer/controller: exact annotated-tag/source/lock/Python checks, isolated worktrees, explicit activation, status, launch and bounded code rollback.
- Candidate qualification through locked Windows Core/UI and exact-source archive checks, with an additional real-Matrix, local-only annotated-tag Git+uv integration probe.
- On activation, back up known annual SQLite databases and the user JSON settings file; preserve prior worktrees and reject dirty or unqualified installations. Windows Registry/QSettings, external Sabt Profiles, user-chosen output paths and database-schema downgrades are **not** automatically backed up or reversed.
- No EXE/installer, public downloadable release, automatic update or official tag. Official version approval and any publication surface remain separate Owner decisions.

## Historical entry: 1.0.0 (2024-01-01; not an established GitHub Release)
### Added
- اولین نسخه پایه سیستم تخصیص پشتیبان

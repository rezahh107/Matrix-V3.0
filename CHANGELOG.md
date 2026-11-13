# Changelog

All notable changes to this project will be documented in this file.

Application package version is sourced from `pyproject.toml`. Historical entries alone do not establish that GitHub published any Release. The initial personal release v0.1.0 was published on GitHub on 2026-11-07; later versions remain candidates until separately approved and published.

## [Unreleased]
- قابلیت انتشار دستی GitHub Release با تأیید Owner، کنترل SHA/نسخه و آرشیو عمومی بررسی‌شده، CI Windows و بازیابی بدون بازنویسی تاریخچه؛ انتشار با Merge یا CI خودکار انجام نمی‌شود.
- مسیر شخصی Git+uv با تگ منتخب Owner، worktree نسخه‌های جدا، rollback کد و مستندسازی بکاپ؛ `v0.1.0` در تاریخ 2026-11-07 منتشر شده است.
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

## [0.2.0] - 2026-11-13

> Candidate for review and Windows two-version qualification. Release publication requires a separate Owner decision.

- Incorporates the merged optional-Roster presence control (PR #57) without adding freshness requirements or changing allocation semantics.
- Retains the year-scoped prior-year Roster file reference when its local identity is unchanged; changed, missing or inaccessible references require operator attention (PR #58).
- Incorporates SQLite reference-readiness and GroupCode observation fixes (PR #59), plus the connected native Windows operator journey test coverage (PR #60).
- Aligns the personal-release and GUI operator guidance with the published v0.1.0 baseline and implemented Roster restoration behavior.
- Adds candidate-specific, authentic published-v0.1.0 to candidate Git+uv upgrade, synthetic persistence and recovery qualification. Passing the new Windows checks is required evidence, not assumed by these notes.
- Keeps the existing Git+uv controller, separate worktrees, and bounded code rollback; Registry, external Profiles, and database-schema downgrades are not automatically restored.

## [0.1.0] - 2026-11-07

> **First Owner-controlled v0.1.0 GitHub Release, published 2026-11-07.** This section describes its baseline capabilities; it is not the changelog for the later v0.2.0 candidate.

- Windows PySide6 application with Policy/LAW-governed matrix building, allocation, QA/Trace/History and Excel/Sabt-oriented workflows; real organizational Sabt acceptance is not established.
- Existing version-selectable Git+uv personal installer/controller: exact annotated-tag/source/lock/Python checks, isolated worktrees, explicit activation, status, launch and bounded code rollback.
- Candidate qualification through locked Windows Core/UI and exact-source archive checks, with an additional real-Matrix, local-only annotated-tag Git+uv integration probe.
- On activation, back up known annual SQLite databases and the user JSON settings file; preserve prior worktrees and reject dirty or unqualified installations. Windows Registry/QSettings, external Sabt Profiles, user-chosen output paths and database-schema downgrades are **not** automatically backed up or reversed.
- Prepared exact-content admission for five inspected synthetic/header-only CSVs, exact Git-archive omissions for review-pending test data, and prepublication comparison of hosted GitHub ZIP/TAR with the reviewed commit.
- No EXE/installer or automatic update. The immutable official Tag/Release is created only by the explicit Owner-controlled manual GitHub workflow.

## Historical entry: 1.0.0 (2024-01-01; not an established GitHub Release)
### Added
- اولین نسخه پایه سیستم تخصیص پشتیبان

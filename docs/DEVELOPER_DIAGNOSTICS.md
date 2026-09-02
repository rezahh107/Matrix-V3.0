# Matrix Developer Diagnostics

## Retention and discoverability contract

This document is the canonical technical inventory for Matrix diagnostics, analysis, and advanced execution controls. It is intentionally presentation/documentation authority only; it does not define allocation, ranking, capacity, join, history, QA, or Rule Engine domain semantics.

### Rule Engine status

- **Rule Engine GUI:** RETIRED from the normal end-user workspace by this work unit.
- **Rule Engine backend / CLI:** INTENTIONALLY PRESERVED.
- Absence from the GUI is **not** evidence that Rule Engine backend code is dead or removable.

### Intentionally retained capabilities

The following eight capabilities are supported and must not be treated as dead code merely because their default is OFF:

1. History Metrics
2. Trace Debug Sheets
3. Mentor Pipeline Trace
4. Pool Governance Trace
5. Bucket Trace
6. QA Pool Coverage Rules
7. Trace Sheet Export
8. Use Join Buckets

Future maintainers and coding agents must inspect this document and current code/tests before deleting, consolidating, or refactoring any of these capabilities.

Critical behavioral distinctions that must remain visible in implementation and documentation:

- **QA Pool Coverage Rules** may affect QA validation PASS/FAIL and must not be described as diagnostic-only.
- **Use Join Buckets** changes an algorithmic execution path and must not be described as diagnostic-only.
- **History Metrics** reporting is distinct from history-aware allocation behavior.
- **Bucket Trace** observes bucketing behavior; it is distinct from enabling **Use Join Buckets**.

---

# قرارداد نگه‌داری و قابلیت کشف

این سند موجودی فنی کاننیکال برای ابزارهای خطایابی، تحلیل و گزینه‌های اجرای پیشرفته Matrix است. این سند فقط مرجع ارائه/مستندسازی است و قانون جدیدی برای تخصیص، رتبه‌بندی، ظرفیت، join، تاریخچه، QA یا Rule Engine تعریف نمی‌کند.

## وضعیت Rule Engine

- **رابط گرافیکی Rule Engine:** در این work unit از فضای عادی کاربر بازنشسته می‌شود.
- **Backend / CLI Rule Engine:** عمداً حفظ می‌شود.
- نبودن Rule Engine در GUI به معنی dead code بودن backend یا مجاز بودن حذف آن نیست.

## قابلیت‌های عمداً حفظ‌شده

هشت قابلیت زیر پشتیبانی‌شده هستند و صرفاً به دلیل اینکه مقدار پیش‌فرض آن‌ها OFF است نباید dead code تلقی شوند:

1. History Metrics
2. Trace Debug Sheets
3. Mentor Pipeline Trace
4. Pool Governance Trace
5. Bucket Trace
6. QA Pool Coverage Rules
7. Trace Sheet Export
8. Use Join Buckets

نگه‌دارندگان و agentهای آینده قبل از حذف، ادغام یا refactor هر یک از این قابلیت‌ها باید این سند و کد/تست‌های جاری را بررسی کنند.

تمایزهای رفتاری مهم که باید در پیاده‌سازی و مستندات آشکار باقی بمانند:

- **QA Pool Coverage Rules** ممکن است نتیجه PASS/FAIL اعتبارسنجی QA را تغییر دهد و diagnostic-only نیست.
- **Use Join Buckets** مسیر اجرای الگوریتمی را تغییر می‌دهد و diagnostic-only نیست.
- گزارش **History Metrics** با رفتار history-aware allocation یکسان نیست.
- **Bucket Trace** رفتار bucketing را مشاهده می‌کند و با فعال‌کردن **Use Join Buckets** تفاوت دارد.

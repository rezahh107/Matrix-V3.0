# راهنمای انتشار شخصی Matrix با Git و uv

این مسیر فقط برای استفادهٔ شخصی Owner روی Windows است. عمومی بودن مخزن به معنی انتشار نسخهٔ رسمی نیست. **در این PR هیچ شمارهٔ نسخه یا تگ رسمی اولیه‌ای انتخاب یا منتشر نشده است.**

## مدل عملیات

یک Git clone ثابت نقش کنترل‌کننده را دارد؛ هر تگ رسمی با Git worktree در پوشهٔ مجزای .matrix-personal/versions/ نصب می‌شود. Git فقط تغییرات/اشیای مورد نیاز را fetch می‌کند؛ بنابراین هر بار ZIP کامل سورس دانلود نمی‌شود، اما worktree یک نسخهٔ کامل محلی است. محیط .venv مستقل هر نسخه ممکن است برای وابستگی جدید دانلود داشته باشد. .matrix-personal/state.json فقط بعد از تأیید tag/pyproject/uv.lock/CHANGELOG، uv sync --locked و import probe به‌صورت اتمی تغییر می‌کند. نسخهٔ قبلی خودکار حذف نمی‌شود.

## آماده‌سازی یک نسخهٔ کاندیدا، بدون انتشار

1. در PR بررسی‌شدنی، نسخهٔ پیشنهادی را در pyproject.toml تعیین کنید؛ uv lock را به‌روز کنید؛ در CHANGELOG.md بخش ## [X.Y.Z] - YYYY-MM-DD و توضیح کوتاه تغییرات اضافه کنید. این اقدام پیشنهاد نسخه است و انتشار نیست.
2. CI برای همان SHA: Windows Core/UI، Windows uv source qualification، LAW/SSoT و Golden مرتبط. اجرای دستی اختیاری: python tools/ci/qualify_uv_source.py --require-release-version X.Y.Z --output-dir OUTPUT_FRESH. خروجی فقط candidate است، نه یک Release.
3. تعیین نخستین نسخهٔ رسمی و اجازهٔ ساخت تگ annotated غیرقابل‌بازنویسی vX.Y.Z و GitHub Release، به تصمیم جداگانهٔ صریح Owner وابسته است. CI/PR/Merge، انتشار خودکار ندارند. حقوق/حریم خصوصی هر سطح انتشار باید جداگانه بررسی شود.
4. در هنگام انتشارِ مجاز، tag/Source SHA، uv.lock، changelog، CI و آرتیفکت واقعی تطبیق داده شوند. تگ منتشرشده بازنویسی نشود؛ اصلاح با نسخهٔ جدید صورت گیرد.

## نصب، فعال‌سازی، اجرا و rollback روی Windows

پیش‌نیاز: Git for Windows، uv، اتصال به مخزن و مجوز دسترسی آن. فرمان‌ها در PowerShell یا CMD:

~~~powershell
git clone https://github.com/rezahh107/Matrix-V3.0.git
cd Matrix-V3.0
uv python install 3.11
.\Matrix-Personal.cmd activate vX.Y.Z
.\Matrix-Personal.cmd status
.\Matrix-Personal.cmd start
~~~

در ارتقای بعدی، فقط نسخهٔ رسمی و مصوبِ دقیق را مشخص کنید (هرگز latest به‌صورت خودکار انتخاب نمی‌شود):

~~~powershell
.\Matrix-Personal.cmd activate vA.B.C
.\Matrix-Personal.cmd status
.\Matrix-Personal.cmd start
~~~

اگر نسخهٔ جدید هنگام استفاده نامناسب بود، بعد از بستن Matrix:

~~~powershell
.\Matrix-Personal.cmd rollback
.\Matrix-Personal.cmd start
~~~

عبارت‌های vX.Y.Z و vA.B.C جای‌نگهدارند؛ فعلاً تگ رسمی تعریف نشده است. status نسخه و SHA کامل فعال و قبلی را نشان می‌دهد. activate/rollback برنامه را باز نمی‌کنند. start برنامه را از محیط قفل‌شده همان نسخه با python -m app.main اجرا می‌کند. Launch_Matrix3.cmd برای اجرای checkout اصلی است و معادل انتخاب نسخهٔ تأییدشده نیست.

## مرز داده و بازیابی

- هنگام ارتقا/rollback برنامه را ببندید. هر تغییر ردیابی‌شده یا فایل untracked در checkout پایه یا worktree فعال باعث توقف عملیات می‌شود. هیچ Git reset --hard، Git clean، حذف خودکار نسخهٔ قبلی یا بازنویسی اطلاعات شخصی انجام نمی‌شود.
- SQLiteهای سالانهٔ GUI در ~/.smart_alloc/years/ و تنظیمات JSON در ~/.smart_alloc/user_settings.json هستند. پیش از فعال‌سازی با SQLite online backup نسخهٔ جداگانهٔ فایل‌های .sqlite و .db آن پوشه برداشته می‌شود؛ شکست بکاپ مانع فعال‌سازی است. بکاپ‌ها داخل .matrix-personal/backups/ هستند و پیش از حذف clone باید به محل مستقل منتقل شوند.
- QSettings در Windows Registry نگهداری می‌شود؛ شناسه‌های Qt مورد استفاده عبارت‌اند از YourOrg/AllocationApp و YourOrganization/MentorAllocation. updater تنظیمات را دستکاری نمی‌کند، ولی بکاپ خودکار Registry انجام نمی‌دهد. پس از اجرای نسخهٔ جدید، اگر فرمت تنظیمات تغییر کند، rollback کد تضمین برگشت تنظیمات نیست.
- خروجی‌های خودکار GUI به‌طور پیش‌فرض در Documents/MentorAllocation/Output قرار می‌گیرند؛ QSettings می‌تواند این مسیر را تغییر دهد. فایل خصوصی Sabt Profile با انتخاب کاربر تعیین می‌شود و ممکن است در هر محلی باشد؛ فایل‌های خارج از مسیر دیتابیسِ شناخته‌شده در بکاپ خودکار پوشش ندارند. آن‌ها را خارج checkout/worktree نگه دارید و جداگانه بکاپ کنید.
- Policyهای پیش‌فرض ردیابی‌شده (config/policy.json، policy.yaml، policy_sample.yaml) به هر نسخه تعلق دارند. ویرایش محلی tracked مانع فعال‌سازی می‌شود؛ اصلاحات سفارشی به نسخهٔ جدید خودکار منتقل نمی‌شوند. از این موارد در یک محل مستقل نسخه بردارید و سازگاری آن‌ها را با LAW/SSoT بررسی کنید.
- کاربری که مسیر Profile/خروجی را به داخل worktree قبلی داده، باید پیش از هر حذف دستی worktree مسیر را بررسی و به محل پایدار منتقل کند. ابزار هیچ نسخهٔ قدیمی را پاک نمی‌کند.
- rollback فقط **کد، tag و uv environment** قبلی را دوباره فعال می‌کند؛ **دیتابیس و Registry را restore نمی‌کند**. پس از اجرای نسخهٔ جدید، سازگاری معکوس schema ممکن است برقرار نباشد؛ بازیابی دیتابیس واقعی نیازمند بررسی و توقف برنامه و تصمیم مستقل است.
- فقط یک عملیات activate، rollback یا start می‌تواند هم‌زمان اجرا شود. تا وقتی برنامه با start باز است، عملیات به‌روزرسانی/rollback دوم رد می‌شود. اگر فرآیند در میانهٔ کار غیرعادی متوقف شود، پوشهٔ `.matrix-personal/.operation-lock` ممکن است باقی بماند. در این حالت **ابتدا همهٔ پنجره‌های Matrix و فرمان‌های فعال Git/uv را بررسی و متوقف کنید**، سپس فقط همین پوشهٔ قفل را به‌شکل دستی حذف و دوباره status را اجرا کنید؛ ابزار عمداً قفل مشکوک را خودکار پاک نمی‌کند.
- شکست fetch، tag، تطبیق نسخه، Python، uv sync، import یا snapshot وضعیت فعال قبلی را حفظ می‌کند. ممکن است worktree نیمه‌آماده برای بررسی باقی بماند؛ هیچ پاکسازی مخربی انجام ندهید.
- فایل‌های داخل .venv، logs، artifacts و cacheها ممکن است توسط ابزارهای معمول بازتولید/پاک شوند؛ فایل خصوصی را به این مسیرها نسپارید. اعمال چند نسخهٔ هم‌زمان بدون هماهنگی مجاز نیست.

## مرز شواهد

تست مصنوعی Git+uv و Windows CI offscreen معادل پذیرش GUI واقعی و Profile سازمانی Sabt نیست. D1، D2، D3 و D5 همچنان اهداف مستقلی هستند.

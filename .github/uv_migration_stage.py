from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Dependency declaration SSoT: preserve all pre-existing direct constraints.
p = ROOT / "pyproject.toml"
s = p.read_text(encoding="utf-8")
s = s.replace(
    "dependencies = []",
    '''dependencies = [
    "PySide6>=6.5.0",
    "pandas>=2.0.0",
    "openpyxl>=3.1.0",
    "numpy>=1.24.0,<2.0.0",
    "PyYAML>=6.0",
    "pandera>=0.18.0,<0.19.0",
]

[dependency-groups]
dev = [
    "ruff>=0.6.9",
    "black>=24.10.0",
    "hypothesis>=6.75.3",
    "pytest>=8.3.0",
    "pytest-timeout>=2.3.1",
    "pytest-qt",
]
packaging = [
    "pyinstaller",
]''',
)
p.write_text(s, encoding="utf-8")
(ROOT / ".python-version").write_text("3.11\n", encoding="utf-8")
(ROOT / ".gitignore").write_text(".venv/\n", encoding="utf-8")

# Runtime dependency-error guidance only.
p = ROOT / "app/main.py"
s = p.read_text(encoding="utf-8").replace(
    "برای نصب وابستگی‌ها: pip install -r requirements.txt",
    "برای نصب وابستگی‌ها: uv sync --locked",
)
p.write_text(s, encoding="utf-8")

p = ROOT / "tests/ui/test_dependency_errors.py"
s = p.read_text(encoding="utf-8").replace(
    'assert "pip install -r requirements.txt" in message',
    'assert "uv sync --locked" in message',
)
p.write_text(s, encoding="utf-8")

# Primary README: setup, execution, test, CLI and packaging commands only.
p = ROOT / "README.md"
s = p.read_text(encoding="utf-8")
s = s.replace(
    "## اجرا\n```bash\npip install -r requirements.txt\npython -m app.main\n```",
    "## اجرا\n```bash\nuv sync --locked\nuv run --locked python -m app.main\n```",
)
s = s.replace(
    "```bash\npyinstaller --onefile --windowed --name تخصیص_دانشجو_منتور \\\n  --collect-all PySide6 --hidden-import openpyxl --hidden-import pandas.io.formats.excel \\\n  app/main.py\n```",
    "```bash\nuv sync --locked --group packaging\nuv run --locked --group packaging pyinstaller --onefile --windowed --name تخصیص_دانشجو_منتور \\\n  --collect-all PySide6 --hidden-import openpyxl --hidden-import pandas.io.formats.excel \\\n  app/main.py\n```",
)
s = s.replace("`pytest -q` سناریوهای", "`uv run --locked pytest -q` سناریوهای")
s = s.replace("python -m app.cli allocate \\\n", "uv run --locked python -m app.cli allocate \\\n")
p.write_text(s, encoding="utf-8")

# Active PyInstaller workflow.
p = ROOT / "tools/packaging/README_packaging.md"
s = p.read_text(encoding="utf-8")
s = s.replace(
    '''3. نصب وابستگی‌ها:
   ```powershell
   py -3.11 -m venv .venv
   .\\.venv\\Scripts\\Activate.ps1
   pip install -U pip
   pip install -r requirements.txt
   pip install pyinstaller
   ```''',
    '''3. نصب `uv` و همگام‌سازی محیط پروژه با گروه بسته‌بندی:
   ```powershell
   uv sync --locked --group packaging
   ```
   `uv` محیط `.venv` پروژه را مدیریت می‌کند و PyInstaller را از گروه `packaging` در `pyproject.toml` و نسخهٔ قفل‌شدهٔ `uv.lock` نصب می‌کند.''',
)
s = s.replace(
    "pyinstaller tools/packaging/matrix2_gui.spec",
    "uv run --locked --group packaging pyinstaller tools/packaging/matrix2_gui.spec",
)
s = s.replace("python run_gui.py", "uv run --locked python run_gui.py")
p.write_text(s, encoding="utf-8")

# Operator guide environment/run instructions only.
p = ROOT / "docs/SmartAlloc_GUI_Operator_Guide.fa.md"
s = p.read_text(encoding="utf-8")
s = s.replace(
    "**حالت توسعه (اختیاری):** نصب Python 3.10 به‌همراه `pip install -r requirements.txt` برای اجرا از سورس.",
    "**حالت توسعه (اختیاری):** نصب Python 3.11 و `uv`؛ سپس اجرای `uv sync --locked` برای آماده‌سازی محیط قفل‌شدهٔ پروژه.",
)
s = s.replace("  python run_gui.py", "  uv run --locked python run_gui.py")
p.write_text(s, encoding="utf-8")

# Golden developer instructions only.
p = ROOT / "docs/CI_Golden_Regression.md"
s = p.read_text(encoding="utf-8")
s = s.replace(
    "- Install dependencies (`pip install -r requirements.txt && pip install -e .`).",
    "- Synchronize the locked project environment (`uv sync --locked`).",
)
s = s.replace("PYTHONPATH=. python scripts/", "uv run --locked python scripts/")
s = s.replace(
    "python scripts/run_golden_regression.py",
    "uv run --locked python scripts/run_golden_regression.py",
)
s = s.replace("uv run --locked uv run --locked python", "uv run --locked python")
p.write_text(s, encoding="utf-8")

# Windows setup/run instructions.
p = ROOT / "docs/windows-ui-guide.md"
s = p.read_text(encoding="utf-8")
s = s.replace(
    "- فایل `requirements.txt`",
    "- فایل `pyproject.toml`\n     - فایل `uv.lock`\n     - فایل `.python-version`",
)
start = s.index("### نصب برنامه:\n")
end = s.index("\n---\n\n## مرحله 4:", start)
new_block = '''### نصب برنامه:

در پنجره PowerShell، ابتدا مطمئن شوید `uv` نصب است. اگر نصب نیست، از نصب‌کنندهٔ رسمی uv استفاده کنید:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/0.12.7/install.ps1 | iex"
```

سپس PowerShell را یک‌بار ببندید و دوباره در پوشهٔ پروژه باز کنید و اجرا کنید:

```powershell
uv --version
uv sync --locked
```

- `uv` نسخهٔ Python ترجیحی پروژه را از `.python-version` می‌خواند.
- محیط مجازی `.venv` به‌صورت خودکار توسط uv ساخته و مدیریت می‌شود؛ فعال‌سازی دستی لازم نیست.
- `uv sync --locked` فقط از `pyproject.toml` و `uv.lock` استفاده می‌کند و lockfile را بازنویسی نمی‌کند.
'''
s = s[:start] + new_block + s[end:]
s = s.replace(
    '''1. اگر پنجره PowerShell را بسته‌اید، دوباره آن را باز کنید (مطابق **مرحله 3**)

2. محیط مجازی را فعال کنید:
   ```powershell
   .\\.venv\\Scripts\\Activate.ps1
   ```
   - باید `(.venv)` در ابتدای خط ظاهر شود

3. **اجرای برنامه:**
   ```powershell
   python -m app.main
   ```

4. یک پنجره گرافیکی با عنوان "سامانه تخصیص دانشجو-منتور" باز می‌شود''',
    '''1. اگر پنجره PowerShell را بسته‌اید، دوباره آن را باز کنید (مطابق **مرحله 3**)

2. **اجرای برنامه:**
   ```powershell
   uv run --locked python -m app.main
   ```

3. یک پنجره گرافیکی با عنوان "سامانه تخصیص دانشجو-منتور" باز می‌شود''',
)
s = s.replace(
    "python -m app.infra.cli build-matrix",
    "uv run --locked python -m app.infra.cli build-matrix",
)
s = s.replace(
    "python -m app.infra.cli allocate",
    "uv run --locked python -m app.infra.cli allocate",
)
s = s.replace(
    '''### مشکل 2: خطا در فعال‌سازی محیط مجازی
**راه حل:**
- دستور زیر را اجرا کنید:
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```
- سپس `Y` را تایپ و Enter بزنید

### مشکل 3: "ModuleNotFoundError: PySide6"
**راه حل:**
- محیط مجازی را فعال کنید
- دستور نصب کتابخانه‌ها را دوباره اجرا کنید:
  ```powershell
  pip install -r requirements.txt
  ```''',
    '''### مشکل 2: خطا در آماده‌سازی محیط پروژه
**راه حل:**
- مطمئن شوید `uv --version` بدون خطا اجرا می‌شود.
- سپس همگام‌سازی قفل‌شده را دوباره اجرا کنید:
  ```powershell
  uv sync --locked
  ```

### مشکل 3: "ModuleNotFoundError: PySide6"
**راه حل:**
- از ریشهٔ مخزن همگام‌سازی قفل‌شده را دوباره اجرا کنید:
  ```powershell
  uv sync --locked
  ```''',
)
p.write_text(s, encoding="utf-8")

SETUP_UV = "astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9 # v9.0.0"

(ROOT / ".github/workflows/ci-main.yml").write_text(f'''name: CI — Core & UI

on:
  push:
    branches: ["main"]
  pull_request:
    branches: ["main"]

jobs:
  pre-merge-guards:
    name: Pre-merge guards
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Set up uv
        uses: {SETUP_UV}
        with:
          version: "0.12.7"
          enable-cache: true
          cache-dependency-glob: |
            pyproject.toml
            uv.lock
            .python-version
      - name: Set up Python
        run: uv python install
      - name: Sync locked environment
        run: uv sync --locked
      - name: Run pre-merge guards
        run: uv run --locked python tools/ci/pre_merge_guards.py

  core-windows:
    name: Core tests (Windows)
    runs-on: windows-latest
    timeout-minutes: 30
    env:
      QT_QPA_PLATFORM: offscreen
      MATRIX2_TEMP_SKIP_QT_UI: "1"
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
      - name: Set up uv
        uses: {SETUP_UV}
        with:
          version: "0.12.7"
          enable-cache: true
          cache-dependency-glob: |
            pyproject.toml
            uv.lock
            .python-version
      - name: Set up Python
        run: uv python install
      - name: Sync locked environment
        run: uv sync --locked
      - name: Lint with ruff
        run: uv run --locked ruff check .
      - name: Run core pytest suite (Windows, includes CI guard tests)
        run: uv run --locked pytest tests/unit tests/infra tests/integration --maxfail=1 -q

  ui-windows:
    name: UI tests (Windows, Qt/PySide6)
    runs-on: windows-latest
    timeout-minutes: 30
    needs: [core-windows]
    env:
      QT_QPA_PLATFORM: offscreen
      PYTEST_QT_API: pyside6
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
      - name: Set up uv
        uses: {SETUP_UV}
        with:
          version: "0.12.7"
          enable-cache: true
          cache-dependency-glob: |
            pyproject.toml
            uv.lock
            .python-version
      - name: Set up Python
        run: uv python install
      - name: Sync locked environment
        run: uv sync --locked
      - name: Run UI pytest suite
        run: uv run --locked pytest tests/ui --maxfail=1 -q
''', encoding="utf-8")

(ROOT / ".github/workflows/ci-advanced-guards.yml").write_text(f'''name: CI — Advanced Guards (Flaky/Perf/DB)

on:
  workflow_dispatch:
  schedule:
    - cron: "0 2 * * *"

jobs:
  flaky-ui-smoke:
    runs-on: windows-latest
    env:
      QT_QPA_PLATFORM: offscreen
    steps:
      - uses: actions/checkout@v4
      - name: Set up uv
        uses: {SETUP_UV}
        with:
          version: "0.12.7"
          enable-cache: true
          cache-dependency-glob: |
            pyproject.toml
            uv.lock
            .python-version
      - name: Set up Python
        run: uv python install
      - name: Sync locked environment
        run: uv sync --locked
      - name: Run flaky UI smoke
        run: uv run --locked python -m tools.ci.run_flaky_ui_smoke

  perf-smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up uv
        uses: {SETUP_UV}
        with:
          version: "0.12.7"
          enable-cache: true
          cache-dependency-glob: |
            pyproject.toml
            uv.lock
            .python-version
      - name: Set up Python
        run: uv python install
      - name: Sync locked environment
        run: uv sync --locked
      - name: Run performance smoke
        run: uv run --locked python -m tools.ci.run_perf_smoke

  db-snapshot-smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up uv
        uses: {SETUP_UV}
        with:
          version: "0.12.7"
          enable-cache: true
          cache-dependency-glob: |
            pyproject.toml
            uv.lock
            .python-version
      - name: Set up Python
        run: uv python install
      - name: Sync locked environment
        run: uv sync --locked
      - name: Run DB snapshot smoke
        run: uv run --locked pytest tests/infra/test_local_database_snapshots.py -q
''', encoding="utf-8")

(ROOT / ".github/workflows/golden-regression.yml").write_text(f'''name: Golden Regression (MentorPipelineV3)

on:
  workflow_dispatch:
  pull_request:
    branches: ["main"]
    paths:
      - .github/workflows/golden-regression.yml
      - scripts/run_golden_regression_phase01.py
      - scripts/run_golden_regression_phase02.py
      - ci/configs/golden_regression.yml
      - scripts/run_golden_regression.py
      - ci/golden_datasets/**
      - docs/golden_datasets/**
      - config/policy.json
      - pyproject.toml
      - uv.lock
      - .python-version

env:
  QT_QPA_PLATFORM: offscreen

jobs:
  mentor-pipeline-golden:
    runs-on: windows-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
      - name: Set up uv
        uses: {SETUP_UV}
        with:
          version: "0.12.7"
          enable-cache: true
          cache-dependency-glob: |
            pyproject.toml
            uv.lock
            .python-version
      - name: Set up Python
        run: uv python install
      - name: Sync locked environment
        run: uv sync --locked
      - name: Phase01 lock_current_behavior (fail-fast on missing inputs)
        run: uv run --locked python scripts/run_golden_regression_phase01.py
      - name: Phase06 golden regression (v3 cutover, GOLDEN_DIFF_AUDITOR enforced)
        env:
          GOLDEN_DIFF_AUDITOR_DECISION: BASELINE_OK
        run: uv run --locked python scripts/run_golden_regression_phase02.py --config ci/configs/golden_regression.yml
''', encoding="utf-8")

# The manually-maintained requirements file is no longer authoritative or needed.
(ROOT / "requirements.txt").unlink()

# Golden Regression CI

Golden regression is a thin, config-driven wrapper around the existing CLI
(`app.infra.cli.main`). It runs allocation/QA commands against committed golden
Excel inputs without touching Core behavior.

## Where to store golden files
- Place all committed golden Excel inputs/outputs under a committed docs
  folder, for example `docs/golden_datasets/phase01_lock_current_behavior/`.
  Keep the directory free of secrets; placeholder files are fine until real
  goldens are ready.

## Configure scenarios (YAML)
- Edit `ci/configs/golden_regression.yml`.
- Top-level keys:
  - `base_dir`: root directory that contains your golden Excel files (for
    example `docs/golden_datasets/phase01_lock_current_behavior`). Relative
    paths in `requires` are resolved against this directory.
  - `scenarios`: list of named scenarios. Each scenario includes:
    - `name` (required) and optional `description`.
    - `commands`: one or more CLI invocations. Each command defines:
      - `name`: label for logging.
      - `args`: list of arguments passed verbatim to `app.infra.cli.main`
        (e.g., `build-matrix --inspactor ...`). Paths can be absolute or
        relative; use `base_dir` to avoid repetition.
      - `requires`: list of Excel files that must exist before running. Relative
        entries are resolved under `base_dir` and are validated before any CLI
        command executes. Ensure `args` and `requires` reference the same
        filenames so the runner checks the files you actually use.

The scaffolded scenario points to the `phase01_lock_current_behavior` golden
set; adjust `base_dir` and filenames to match your committed goldens.

## MentorPipelineV3 parity (mentors)
- Golden regression باید سناریوهای parity بین مسیر legacy و **MentorPipelineV3** را شامل شود.
- مقایسه‌ها باید روی تپّل‌های شش‌گانهٔ join key (`group_code`, `gender_code`, `grad_status_code`, `center_code`, `finance_code`, `school_code`) و ستون‌های ظرفیت (`capacity_limit`, `assigned_baseline`, `allocations_new`, `remaining_capacity`) strict باشد.
- اگر `ci/golden_datasets/mentors/**` پیدا نشود یا فایل‌ها خراب باشند، runner باید fail-fast با پیام واضح برگرداند.
- فقط از داده‌های سانیت‌شدهٔ زیر `ci/golden_datasets/mentors/**` استفاده کنید؛ سناریوهای دیگر نباید به دادهٔ حساس تکیه کنند.

## Run locally
- Install dependencies (`pip install -r requirements.txt && pip install -e .`).
- Dry run (validate YAML + file presence only):
  ```bash
  python scripts/run_golden_regression.py --config ci/configs/golden_regression.yml --dry-run
  ```
- Full run (executes CLI commands):
  ```bash
  python scripts/run_golden_regression.py --config ci/configs/golden_regression.yml
  ```
- Exit codes: non-zero when the config is missing/malformed, when required files
  are absent, or when any CLI command fails.

## CI usage (GitHub Actions)
- The script is OS-agnostic (uses `pathlib.Path`) and can run on Windows or
  Linux runners.
- Example invocation from a workflow step:
  ```bash
  python scripts/run_golden_regression.py --config ci/configs/golden_regression.yml --dry-run
  ```
  - Add real golden Excel files under your chosen `base_dir` (for example,
    `docs/golden_datasets/phase01_lock_current_behavior/`) and update the YAML
    when scenarios are ready. The runner will fail fast in CI if required files
    are missing, providing a clear list of absent paths.

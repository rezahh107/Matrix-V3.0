# Golden Regression CI

Golden regression is a thin, config-driven wrapper around the existing CLI
(`app.infra.cli.main`) and MentorPipelineV3. It runs allocation/QA commands
against committed, sanitized golden inputs without touching Core behavior.

## Where to store golden files
- Place all committed golden mentor inputs/outputs under the sanitized
  `docs/golden_datasets/**` (or `ci/golden_datasets/**`) tree. Keep the
  directory free of secrets; placeholder files are fine until real goldens are
  ready. CSV inputs are supported, but phase01 locks use the provided Excel
  workbooks directly.

## Configure scenarios (YAML)
- Edit `ci/configs/golden_regression.yml`.
- Top-level keys:
  - `base_dir`: root directory that contains your golden Excel/CSV files (for
    example `docs/golden_datasets/phase01_lock_current_behavior`). Relative
    paths in `requires` are resolved against this directory. The runner fails
    fast if `base_dir` does not exist or falls outside the sanitized
    `docs/golden_datasets/**` or `ci/golden_datasets/**` trees.
  - `scenarios`: list of named scenarios. Each scenario includes:
    - `type`: either `cli` (default) or `mentor-pipeline-v3`.
    - `name` (required) and optional `description`.
    - For `cli` scenarios:
      - `commands`: one or more CLI invocations. Each command defines `name`,
        `args`, and `requires` (validated before running).
    - For `mentor-pipeline-v3` scenarios (MentorPipelineV3 parity checks):
      - `input`: Inspactor CSV or workbook under `base_dir` (required). CSV is
        preferred; the runner auto-converts it to a temporary Excel file for the
        MentorPipelineV3 loader.
      - `requires`: files that must exist (defaults to `[input]`).
      - `expected_pool`: inline rows describing the canonicalized mentor pool
        DataFrame expected from MentorPipelineV3 (use `expected_pool_file` to
        read expectations from CSV/Excel instead).
      - `expected_issues`: inline rows capturing expected join-key QA issues
        (`expected_issues_file` is available to load CSV/Excel expectations;
        empty list when no issues are expected).

The scaffolded scenario points to the locked `docs/golden_datasets/phase01_lock_current_behavior`
golden set; adjust `base_dir` and filenames to match your committed goldens.

## MentorPipelineV3 parity (mentors)
- Golden regression باید سناریوهای parity بین مسیر legacy و **MentorPipelineV3** را شامل شود.
- مقایسه‌ها باید روی تپّل‌های شش‌گانهٔ join key (`group_code`, `gender_code`, `grad_status_code`, `center_code`, `finance_code`, `school_code`) و ستون‌های ظرفیت (`capacity_limit`, `assigned_baseline`, `allocations_new`, `remaining_capacity`) strict باشد.
- اگر `docs/golden_datasets/phase01_lock_current_behavior/**` (یا سایر مسیرهای سانیت‌شده) پیدا نشود یا فایل‌ها خراب باشند، runner باید fail-fast با پیام واضح برگرداند.
- فقط از داده‌های سانیت‌شدهٔ زیر `docs/golden_datasets/**` (یا `ci/golden_datasets/**`) استفاده کنید؛ سناریوهای دیگر نباید به دادهٔ حساس تکیه کنند.

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
- The golden regression workflow is configured to run on the `windows-latest`
  GitHub Actions runner; the script itself remains OS-agnostic via
  `pathlib.Path`.
- Example invocation from a workflow step:
  ```bash
  python scripts/run_golden_regression.py --config ci/configs/golden_regression.yml --dry-run
  ```
  - Add real golden Excel files under your chosen `base_dir` (for example,
    `docs/golden_datasets/phase01_lock_current_behavior/`) and update the YAML
    when scenarios are ready. The runner will fail fast in CI if required files
    are missing, providing a clear list of absent paths.

## Health / issue stability checks
- Golden regression MAY assert that `health.status` برای دیتاست‌های طلایی `OK` بماند یا شمارش issue_codeهای کلیدی پایدار باشد.
- هر تغییر در رفتار Health باید با تغییر مستند در LAW/Technical SSoT توجیه شود، نه با تصمیمات موردی.

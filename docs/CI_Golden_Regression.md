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
        empty list when no issues are expected). Mentor issues goldens MUST follow
        the canonical 5-column schema `entity_type,row_index,column,raw_value,error_code`.
        The runner fails fast when headers differ or any row has the wrong column
        count, reporting the offending file and line number.

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

## Refreshing phase01 mentor pool snapshot (manual, gated)
The phase01 mentor pool snapshot is intentionally locked under
`ci/golden_snapshots/phase01_lock_current_behavior/mentor_pool.csv` to detect
unexpected drift. Only refresh it after confirming current behavior matches
LAW/Technical SSoT.

1) Generate diagnostics
   - Run:
     ```bash
     PYTHONPATH=. python scripts/ci_debug_phase01_mentor_pool_diff.py
     ```
   - This writes:
     - `ci/artifacts/phase01_mentor_pool_current.csv` (current canonical pool)
     - `ci/artifacts/phase01_mentor_pool_snapshot.csv` (copy of locked snapshot)
     - `ci/artifacts/phase01_mentor_pool_diff_summary.md` (shape/column stats and
       root-cause hypothesis)

2) Manual review (Architect approval required)
   - Compare the summary and both CSVs.
   - Confirm the current pool follows LAW/Technical SSoT (six join keys, ranking
     invariants) and that row/column differences are expected refactor behavior.

3) If approved, refresh snapshot in a dedicated PR
   - Replace the locked snapshot CSV with the current pool (for example, move
     `ci/artifacts/phase01_mentor_pool_current.csv` into
     `ci/golden_snapshots/phase01_lock_current_behavior/mentor_pool.csv`).
   - Update any tests that assert shapes/columns to match the refreshed snapshot.
   - Describe the PR as a "phase01 mentor pool snapshot refresh"; no domain rule
     changes are allowed.

4) Data fixes are separate
   - Do not change join-key semantics or ranking when refreshing the snapshot.
   - Use `scripts/ci_summarize_mentor_join_key_issues.py` to guide fixes to
     golden Excel inputs; refresh the snapshot only after data is corrected and
     validated.

## Refreshing phase02 mentor pool snapshot (manual, gated)
The phase02 mentor pool snapshot for the MentorPipelineV3 scenario is stored
alongside the sanitized golden inputs at
`docs/golden_datasets/phase01_lock_current_behavior/expected_mentor_pool.csv`
and `expected_mentor_issues.csv`. Refresh it only when the canonical mentor
pool produced by the v3 pipeline (Inspactor → LocalDatabase + school report →
MentorPipelineV3) is LAW/Technical SSoT–compliant and the change is
classified as **BUG_FIX** (or **MIXED** if explicitly justified).

1) Generate the current canonical pool
   - Run the phase02 mentor scenario to build the canonical pool via the v3
     pipeline:
     ```bash
     PYTHONPATH=. python scripts/run_golden_regression_phase02.py \
       --config ci/configs/golden_regression.yml --mode v3
     ```
     or run the mentor scenario directly via `app.infra.golden.regression_runner`
     to capture the canonical pool/issue CSVs.

2) Manual review (Architect approval required)
   - Confirm the canonical pool has 6 join keys (int), 1 row per mentor, and
     any issue CSV is empty or contains only LAW-justified rows.
   - Verify the shape matches the expected canonical schema (currently 116×62)
     and that group codes come only from «شامل گروه‌های آزمایشی».

3) If approved, refresh the snapshot in a dedicated PR
   - Replace `expected_mentor_pool.csv` (and the 5-column
     `expected_mentor_issues.csv` if present) with the canonical outputs.
   - Note in the PR description that this is a **phase02 mentor pool snapshot
     refresh** classified as **BUG_FIX**; no domain rule changes are allowed.

4) Auditor and baselines
   - Diff auditor gating (`GOLDEN_DIFF_AUDITOR_DECISION`) remains in place for
     baseline re-recording; set it to BUG_FIX or MIXED only after the refresh is
     approved. Golden regression CI still fails on canonical drift or
     join-key/gender blockers.

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

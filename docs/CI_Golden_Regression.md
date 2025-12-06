# Golden Regression CI (Scaffold)

## Purpose
- Run allocation/QA flows on committed golden Excel datasets without touching Core logic.
- Executes via `scripts/run_golden_regression.py` (used by `.github/workflows/golden_regression.yml`).

## Add golden datasets
- Place golden Excel inputs under `ci/golden/` (e.g., `ci/golden/sample_inspactor.xlsx`).
- Keep the directory committed and free of secrets; do **not** add real data until ready.

## Wire scenarios
- Edit `ci/configs/golden_regression.yml`:
  - Add a `name` and optional `description` for each scenario.
  - Provide one or more `commands` with CLI `args` matching `app.infra.cli.main` (e.g., `build-matrix ...`).
  - List `requires` paths for every golden Excel file needed by the command.
- The helper script fails fast with a clear message if any `requires` path is missing.

## Running locally
- Install dependencies (`pip install -r requirements.txt && pip install -e .`).
- Dry run (structure + file presence only): `python scripts/run_golden_regression.py --dry-run`.
- Full run (executes CLI commands): `python scripts/run_golden_regression.py`.

## CI workflow
- Trigger manually via `workflow_dispatch` in `.github/workflows/golden_regression.yml`.
- To run on PRs later, add `pull_request` (and optional `push`) triggers to the workflow when golden data are committed.

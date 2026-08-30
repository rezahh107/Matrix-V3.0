# Cleanup Adjudication Manifest — Matrix-V3.0

## Current cleanup state

**Prompt 4 status: `CLEANUP_PASS_COMPLETE`**

This manifest preserves the Prompt 2 adjudication lineage and records the executed Prompt 3 and Prompt 4 cleanup results.

- Repository: `rezahh107/Matrix-V3.0`
- Verified baseline commit: `24a13e928808715953b3c1260b6ac7271c7dfe31`
- Verified baseline tree: `03fb418444badc04412228596efc04c904ec8cfd`
- Baseline tag: `matrix3-baseline-from-matrix2`
- Prompt 2 commit: `7ef738b53174c9b04fed8b3890ebe7f623439939`
- Prompt 3 commit: `a26b33dd0887090c75e1e07ebcbb4a3e586cfc14`
- Prompt 4 branch: `cleanup/dead-superseded-pass`

## Prompt 2 historical adjudication

Prompt 2 adjudicated 21 material candidates:

- KEEP: 12
- CONFIRMED_DEAD: 6
- SUPERSEDED: 0
- OWNER_DECISION_REQUIRED: 2
- NEEDS_INVESTIGATION: 1

The six CONFIRMED_DEAD entries were historical `.patch` delivery artifacts. The two owner-decision candidates were the root diagnostic tools. The unresolved candidate was `app/infra/students/student_import_pipeline.py`.

## Prompt 3 execution closure

Prompt 3 removed exactly these six historical patch artifacts and no production code:

1. `CSAP_CENTER_ZERO_INFER_CANON_fix.patch`
2. `CSAP_STUDENT_ID_DESYNC_fix.patch`
3. `FIX-INV-QA-ALLOC-JOIN-02-mentor-merge-or-and-better-message.patch`
4. `FIX-INV-QA-ALLOC-JOIN-02-use-wildcard.patch`
5. `HARDEN-join-key-audit-normalize-student_id.patch`
6. `INC-EXPORT-ID-DESYNC-2025-12-26_REL.patch`

Prompt 3 verification closed with Ruff PASS, core/infra/integration baseline preserved, pre-merge guards PASS, and Golden Regression PASS/no drift.

## Closed Owner decisions

- `debug_array_error.py` → **KEEP**
- `debug_pool_alignment.py` → **KEEP**

These files remain present and unchanged in Prompt 4.

## Prompt 4 candidate investigation

### CAND-021 — `app/infra/students/student_import_pipeline.py`

- Previous classification: `NEEDS_INVESTIGATION`
- Prompt 4 classification: **`CONFIRMED_DEAD`**
- Confidence: **HIGH**
- Scope: `run_student_pipeline_from_excel()` and `run_student_pipeline_from_dataframe()` convenience wrappers.

### Confirmed reference/reachability evidence

1. Repository-wide exact-symbol searches found both wrapper functions only at their definitions; no runtime, CLI, GUI, test, script, or developer-tool caller was found.
2. Exact module-name search found only the module itself and its dedicated mypy override entry.
3. There is no package-level `__init__.py` re-export or documented public import path for this wrapper.
4. Current student import runtime directly instantiates `app.infra.students.pipeline_v3.StudentPipelineV3`.
5. `app/infra/cli_legacy.py`, reference-student import code, and current tests use the canonical `StudentPipelineV3` path directly.
6. `app/infra/students/pipeline_v3.py` provides the complete underlying behavior through `StudentPipelineV3.run_from_excel()` and `StudentPipelineV3.run()`.
7. Git path history shows the wrapper was added on 2025-12-09 and did not subsequently evolve; no migration, deprecation, or compatibility-maintenance history was found.
8. The repository separately contains `app/infra/students/student_pipeline_v3.py`, whose source explicitly calls itself a **Compatibility shim** and which is directly tested. That affirmative compatibility evidence is absent from `student_import_pipeline.py`.
9. Repository README documents application GUI/CLI usage rather than these wrapper functions.
10. GitHub reports no repository releases establishing this wrapper as a released public API contract.
11. No `importlib`, string/getattr dispatch, config selector, subprocess command, serialization name, persistence path, CI command, or documentation workflow targets the wrapper or either function.

### Evidence interpretation

- **Confirmed fact:** canonical StudentPipelineV3 behavior remains active and untouched.
- **Inference:** `student_import_pipeline.py` was an unused convenience surface introduced alongside the canonical V3 implementation, not a maintained compatibility contract.
- **Residual possibility:** an unknown external script could theoretically import any package path. No release, documentation, compatibility marker, history, or in-repository contract evidence supports treating this theoretical consumer as a maintained responsibility.

The evidence crossed the Prompt 4 practical safety threshold for `CONFIRMED_DEAD`.

## Prompt 4 cleanup performed

### Dead code removed

- `app/infra/students/student_import_pipeline.py`

### Bounded transitive cleanup

- Removed only `"app.infra.students.student_import_pipeline"` from the mypy ignore override in `pyproject.toml`.

That configuration entry existed solely for the deleted module and has no independent role.

### Superseded code removed

None.

### Tests removed

None.

## Protected KEEP findings

The following remained untouched:

- `debug_array_error.py`
- `debug_pool_alignment.py`
- `app/infra/students/pipeline_v3.py` — canonical active implementation
- `app/infra/students/student_pipeline_v3.py` — explicit compatibility shim
- `app/infra/cli_legacy.py` — live CLI implementation
- `app/infra/cli/__init__.py` — live compatibility facade
- `app/core/allocate.py` — active allocation contract gateway
- `app/main.py` and `run_gui.py` — GUI launch surfaces
- `app/infra/local_database.py` — persistence boundary
- golden regression runners/workflow and canonical workbooks

## Deferred unresolved findings

None after bounded Prompt 4 investigation.

## Owner decisions required

None. The two prior owner decisions are closed as KEEP.

## Deferred non-cleanup findings

Observed dependency/environment warnings remain outside Prompt 4, including Pandas deprecation warnings and GitHub Actions Node-runtime deprecation warnings. No bug fix, modernization, dependency migration, uv work, Qt modernization, pandas modernization, CI modernization, or architecture refactor was performed.

## Prompt 4 verification receipt

### Static verification

`ruff check .` → **PASS** (`All checks passed!`)

### Core / Infra / Integration

Command:

`pytest tests/unit tests/infra tests/integration --maxfail=1 -q`

Result:

- **1219 passed**
- **4 skipped**
- **0 failed**

Prompt 3 reference was 1220 passed / 4 skipped / 0 failed. The exact one-case reduction is expected and causally reconciled: `tests/unit/test_repo_hygiene.py` parametrizes one test case for every `app/**/*.py` file. Prompt 4 intentionally removed exactly one `app` Python module, therefore this retained hygiene test collects exactly one fewer parameter case. No test file or retained-behavior test was removed or weakened.

### Pre-merge guards

`python tools/ci/pre_merge_guards.py` → **PASS**

- **335 passed**
- **0 failed**

LAW/SSoT Drift Guard also completed successfully.

### Golden Regression

Executed using the existing workflow and existing commands:

- `python scripts/run_golden_regression_phase01.py` → **PASSED (no drift detected)**
- Phase02 with `GOLDEN_DIFF_AUDITOR_DECISION=BASELINE_OK` → **success**
- Final workflow message: `golden regression completed successfully`

Because the workflow is path-filtered and the connector exposes no workflow-dispatch action, Golden was triggered on a separate verification-only branch containing the exact Prompt 4 application/config code state plus one inert documentation trigger file under `docs/golden_datasets/`. The trigger was not a canonical input or golden baseline and is not part of the final Prompt 4 branch.

### UI verification

`pytest tests/ui --maxfail=1 -q` → **PASS**

- **77 passed**
- **3 skipped**
- **0 failed**

No cleanup-caused UI regression appeared. This matches the semantic Prompt 3 GitHub profile; the Prompt 1 local QSignalSpy failures remain environment-specific observations and were not modified.

### Runtime startup smoke

`NOT_RUN_ENVIRONMENT_LIMITATION` — no connector action exposes an interactive GUI startup command, and the local execution environment lacks the repository's PySide6 runtime. Automated core, UI, and golden gates passed; this optional limitation is not a blocker.

## Final Prompt 4 scope audit

Prompt 4 production/config scope is exactly:

1. delete `app/infra/students/student_import_pipeline.py`;
2. delete its one dedicated mypy override entry from `pyproject.toml`;
3. update the two existing cleanup manifests with adjudication and verification evidence.

No production behavior implementation, test, CI workflow, dependency declaration, golden baseline, golden dataset, database/schema file, debug tool, or unrelated documentation was changed.

Matrix2 remains untouched. `main` remains untouched. Prompt 5 work has not begun.

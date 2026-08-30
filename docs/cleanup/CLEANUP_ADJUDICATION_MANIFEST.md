# Cleanup Adjudication Manifest — Matrix-V3.0

## Current status

This file is the continuing cleanup record for `rezahh107/Matrix-V3.0`. It preserves the Prompt 2 adjudication history, Prompt 3 low-risk artifact cleanup, and Prompt 4 bounded dead/superseded-code investigation.

Baseline commit: `24a13e928808715953b3c1260b6ac7271c7dfe31`  
Baseline tree: `03fb418444badc04412228596efc04c904ec8cfd`  
Baseline tag: `matrix3-baseline-from-matrix2`

## Phase history

### Prompt 2 — adjudication

Branch: `cleanup/adjudication-manifest`  
Commit: `7ef738b53174c9b04fed8b3890ebe7f623439939`

Prompt 2 adjudicated 21 material candidates:

- KEEP: 12
- CONFIRMED_DEAD: 6
- SUPERSEDED: 0
- OWNER_DECISION_REQUIRED: 2
- NEEDS_INVESTIGATION: 1

The six CONFIRMED_DEAD items were historical root `.patch` artifacts. The two owner-decision items were `debug_array_error.py` and `debug_pool_alignment.py`. The unresolved item was `app/infra/students/student_import_pipeline.py`.

### Prompt 3 — low-risk artifacts

Branch: `cleanup/low-risk-artifacts`  
Commit: `a26b33dd0887090c75e1e07ebcbb4a3e586cfc14`

Removed exactly these six historical patch artifacts:

1. `CSAP_CENTER_ZERO_INFER_CANON_fix.patch`
2. `CSAP_STUDENT_ID_DESYNC_fix.patch`
3. `FIX-INV-QA-ALLOC-JOIN-02-mentor-merge-or-and-better-message.patch`
4. `FIX-INV-QA-ALLOC-JOIN-02-use-wildcard.patch`
5. `HARDEN-join-key-audit-normalize-student_id.patch`
6. `INC-EXPORT-ID-DESYNC-2025-12-26_REL.patch`

The represented production fixes remain in current source/history. Prompt 3 verification preserved the established core, pre-merge and golden behavior.

Owner decisions were subsequently closed:

- `debug_array_error.py` → KEEP
- `debug_pool_alignment.py` → KEEP

## Candidate register

| ID | Path / scope | Prompt 2 | Current classification | Resolution |
|---|---|---|---|---|
| CAND-001 | `app/main.py` | KEEP | KEEP | Protected GUI bootstrap |
| CAND-002 | `run_gui.py` | KEEP | KEEP | Protected root GUI entrypoint |
| CAND-003 | `app/infra/cli_legacy.py` | KEEP | KEEP | Live CLI implementation |
| CAND-004 | `app/infra/cli/__init__.py` | KEEP | KEEP | Explicit compatibility facade |
| CAND-005 | `app/core/allocate.py` | KEEP | KEEP | Active allocation contract gateway |
| CAND-006 | `app/infra/students/student_pipeline_v3.py` | KEEP | KEEP | Explicit compatibility shim; directly tested |
| CAND-007 | `scripts/run_golden_regression.py` | KEEP | KEEP | Verification entrypoint |
| CAND-008 | `.github/workflows/golden-regression.yml` | KEEP | KEEP | Golden CI surface |
| CAND-009 | `tools/ci/pre_merge_guards.py` | KEEP | KEEP | Active CI guard |
| CAND-010 | `0918.xlsx` | KEEP | KEEP | Canonical golden mentor-pool input |
| CAND-011 | `students.xlsx` | KEEP | KEEP | Canonical golden student input |
| CAND-012 | `app/infra/local_database.py` | KEEP | KEEP | Persistence boundary |
| CAND-013 | `CSAP_CENTER_ZERO_INFER_CANON_fix.patch` | CONFIRMED_DEAD | CLOSED_REMOVED | Removed Prompt 3 |
| CAND-014 | `CSAP_STUDENT_ID_DESYNC_fix.patch` | CONFIRMED_DEAD | CLOSED_REMOVED | Removed Prompt 3 |
| CAND-015 | `FIX-INV-QA-ALLOC-JOIN-02-mentor-merge-or-and-better-message.patch` | CONFIRMED_DEAD | CLOSED_REMOVED | Removed Prompt 3 |
| CAND-016 | `FIX-INV-QA-ALLOC-JOIN-02-use-wildcard.patch` | CONFIRMED_DEAD | CLOSED_REMOVED | Removed Prompt 3 |
| CAND-017 | `HARDEN-join-key-audit-normalize-student_id.patch` | CONFIRMED_DEAD | CLOSED_REMOVED | Removed Prompt 3 |
| CAND-018 | `INC-EXPORT-ID-DESYNC-2025-12-26_REL.patch` | CONFIRMED_DEAD | CLOSED_REMOVED | Removed Prompt 3 |
| CAND-019 | `debug_array_error.py` | OWNER_DECISION_REQUIRED | KEEP | Owner explicitly retained diagnostic workflow |
| CAND-020 | `debug_pool_alignment.py` | OWNER_DECISION_REQUIRED | KEEP | Owner explicitly retained diagnostic workflow |
| CAND-021 | `app/infra/students/student_import_pipeline.py` | NEEDS_INVESTIGATION | CONFIRMED_DEAD | Prompt 4 bounded investigation resolved; remove wrapper |

## Prompt 4 — bounded investigation

Branch: `cleanup/dead-superseded-pass`

### CAND-021 — `app/infra/students/student_import_pipeline.py`

Scope: `run_student_pipeline_from_excel()` and `run_student_pipeline_from_dataframe()` convenience wrappers around `StudentPipelineV3`.

**Prompt 4 classification: `CONFIRMED_DEAD` — HIGH confidence.**

Converging evidence:

1. Repository-wide exact-symbol searches find the two wrapper functions only at their definitions; no runtime, CLI, GUI, test, script or tooling caller was found.
2. Exact module-name search finds only the module itself and its dedicated mypy override entry; there is no package `__init__.py` re-export or documented public import path.
3. Current operational student import uses `app.infra.students.pipeline_v3.StudentPipelineV3` directly; for example `app/infra/reference_students_repository.py` instantiates the canonical class directly.
4. `app/infra/cli_legacy.py` and current student tests likewise use `StudentPipelineV3` directly rather than these wrapper functions.
5. `app/infra/students/pipeline_v3.py` provides the complete underlying responsibilities: `run_from_excel()` and `run()` plus reference-mode handling.
6. Git history shows `student_import_pipeline.py` was added once on 2025-12-09 and never subsequently evolved. No migration/deprecation/compatibility history was found for this path.
7. The repository has a separate compatibility shim, `app/infra/students/student_pipeline_v3.py`, whose docstring explicitly says `Compatibility shim` and which is directly tested. That explicit compatibility evidence is absent for `student_import_pipeline.py`.
8. Repository README documents the product as an application invoked through GUI/CLI (`python -m app.main` and CLI workflows), not through these wrapper functions.
9. GitHub reports no repository releases, providing no evidence of a formal released public API contract for this wrapper path.
10. No dynamic import, config-driven invocation, serialization name, persistence reference, CI command or documentation workflow targets the wrapper or its function names.

Confirmed fact: the canonical pipeline remains active and is not removed.  
Inference: the wrapper was an unused convenience surface introduced alongside V3 rather than a maintained compatibility contract.  
Residual external possibility: an unknown out-of-repository script could import any public Python path, but the repository provides no release, docs, compatibility marker or history supporting that as a maintained contract; this theoretical possibility does not outweigh the converging deadness evidence.

### Prompt 4 cleanup authorized

Remove:

- `app/infra/students/student_import_pipeline.py`

Bounded transitive cleanup:

- remove only `"app.infra.students.student_import_pipeline"` from the mypy ignore override in `pyproject.toml`, because that configuration entry has no independent role after the module is deleted.

Do not remove or modify:

- `app/infra/students/pipeline_v3.py`
- `app/infra/students/student_pipeline_v3.py`
- tests covering the canonical pipeline or compatibility shim
- `debug_array_error.py`
- `debug_pool_alignment.py`

## Prompt 4 verification receipt

Verification is recorded against the Prompt 4 cleanup tree. Required gates:

- Ruff: `PENDING`
- Core / Infra / Integration: `PENDING`
- Pre-merge guards: `PENDING`
- Golden Regression: `PENDING`
- UI: `PENDING`
- Runtime startup smoke: `PENDING`

No test is removed in Prompt 4, so the expected retained-behavior test counts remain unchanged unless the execution environment itself changes collection/skips.

## Deferred non-cleanup findings

None are authorized for fixing in Prompt 4. Dependency warnings, Qt behavior, pandas deprecations, architecture modernization and uv migration remain outside this cleanup pass.

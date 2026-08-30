# Cleanup Adjudication Manifest — Matrix-V3.0

## Current cleanup state

**Prompt 5 status: `FINAL_CLEANUP_PASS_COMPLETE_WITH_DEFERRED_ITEMS`**

Prompt 5 completed the last planned bounded dead-code discovery pass. No newly discovered element crossed the high-confidence removal threshold. Two standalone developer utilities remain preserved as `DEFERRED_UNRESOLVED`; this does not authorize another proactive dead-code census.

**Closure declaration: `FINAL_DEAD_CODE_DISCOVERY_CLOSED`**

## Verified lineage

- Repository: `rezahh107/Matrix-V3.0`
- Original baseline commit: `24a13e928808715953b3c1260b6ac7271c7dfe31`
- Original baseline tree: `03fb418444badc04412228596efc04c904ec8cfd`
- Baseline tag: `matrix3-baseline-from-matrix2`
- Prompt 2 adjudication commit: `7ef738b53174c9b04fed8b3890ebe7f623439939`
- Prompt 3 cleanup commit: `a26b33dd0887090c75e1e07ebcbb4a3e586cfc14`
- Prompt 4 cleanup commit: `8132f9dbde5cebc46a1b6a072ab69f275c23f609`
- Prompt 4 tree: `6551fa00f07cef5f4c4795f1736c8778e2624415`
- Prompt 5 branch: `cleanup/final-bounded-discovery`

## Closed Prompt 2–4 history

Prompt 2 adjudicated 21 material candidates: 12 KEEP, 6 CONFIRMED_DEAD historical `.patch` artifacts, 0 SUPERSEDED, 2 OWNER_DECISION_REQUIRED diagnostic tools, and 1 NEEDS_INVESTIGATION student-import wrapper.

Prompt 3 removed exactly the six historical `.patch` artifacts and no production code.

Prompt 4 resolved `CAND-021` (`app/infra/students/student_import_pipeline.py`) as `CONFIRMED_DEAD`, removed that wrapper, and removed only its dedicated mypy override entry. Prompt 4 closed with Ruff PASS, core/infra/integration 1219 passed / 4 skipped / 0 failed, pre-merge 335 passed / 0 failed, Golden Regression PASS/no drift, and UI 77 passed / 3 skipped / 0 failed.

The following prior decisions remained protected and were not reopened in Prompt 5:

- `debug_array_error.py` → KEEP
- `debug_pool_alignment.py` → KEEP
- `app/infra/students/pipeline_v3.py` → KEEP, canonical implementation
- `app/infra/students/student_pipeline_v3.py` → KEEP, explicit compatibility shim
- `app/infra/cli_legacy.py` → KEEP, live CLI implementation
- `app/infra/cli/__init__.py` → KEEP, live compatibility facade
- `app/core/allocate.py` → KEEP
- `app/main.py` and `run_gui.py` → KEEP
- `app/infra/local_database.py` and persistence surfaces → KEEP
- Golden regression runners/workflow and canonical workbooks → KEEP

No new material evidence contradicted any closed finding.

# Prompt 5 — Final Bounded Discovery

## Discovery boundary

Prompt 5 performed one bounded inspection of previously unadjudicated, high-value cleanup surfaces only. The scan covered:

- root-level and `scripts/` developer utilities;
- `tools/` packaging and CI tooling;
- version/legacy-named production modules surfaced by bounded repository search;
- Golden diagnostic helpers;
- performance tooling;
- package exposure and `pyproject.toml` package scope;
- documentation-defined operational commands;
- direct/string references, tests/CI evidence, and available Git path history for material leads.

Prompt 5 did not restart a full repository census and did not reopen the prior 21 candidates.

## New candidates

### CAND-022 — `tools/packaging/matrix2_gui.spec`

- Candidate type: historical-name packaging surface.
- Classification: **KEEP**.
- Why new: packaging tooling was not a material candidate in the previous manifest.
- Confirmed fact: `tools/packaging/README_packaging.md` explicitly instructs developers to run `pyinstaller tools/packaging/matrix2_gui.spec` and documents the produced `Matrix2-GUI.exe` distribution and runtime configuration layout.
- Runtime reachability: not normal application runtime; this is a documented human-invoked packaging workflow.
- Operational role: affirmative developer delivery capability.
- Inference: the `Matrix2` name is historical branding, not proof of deadness.
- Cleanup: none.

### CAND-023 — `scripts/compare_excel_structure.py`

- Candidate type: apparently orphaned standalone developer utility.
- Classification: **DEFERRED_UNRESOLVED**.
- Why new: not represented in the previous manifest.
- Confirmed fact: bounded repository search found no caller or documentation reference beyond the script itself.
- Confirmed fact: the file has an explicit `__main__` command interface, compares workbook sheet/header structures, and returns an operational exit status.
- Package exposure: setuptools packages only `app` and `app.*`; this script is not a package export.
- Runtime/dynamic/config reachability: no application, CLI, GUI, config, CI, or subprocess reference was found during the bounded scan.
- Git history: path history exists in November 2025, but does not establish retirement or current support.
- Residual uncertainty: repository evidence cannot distinguish a retired one-off helper from an intentionally retained ad-hoc developer command.
- Cleanup: none; ambiguous executable utility preserved.

### CAND-024 — `scripts/csap_evidence_pack.py`

- Candidate type: hard-coded evidence-generation utility.
- Classification: **DEFERRED_UNRESOLVED**.
- Why new: not represented in the previous manifest.
- Confirmed fact: the script prints Git provenance and SHA-256 hashes for a fixed CSAP-related file set; it is directly executable and invokes Git through subprocess.
- Confirmed fact: bounded exact-name/content search found no documentation, CI, application, config, or in-repository caller for the command.
- Package exposure: outside the packaged `app` namespace.
- Git history: changed during December 2025 hardening/evidence work, including join-bucketing/eligibility evidence and unknowns preflight/UI gating work.
- Residual uncertainty: it resembles phase-specific evidence tooling, but no explicit retirement record disproves continuing manual provenance/hash evidence use.
- Cleanup: none; preserved.

### CAND-025 — `app/infra/matrix/build_matrix_v1_0_2.py`

- Candidate type: version-named production module / possible old-new pair.
- Classification: **KEEP**.
- Why new: surfaced by final version-name scan.
- Confirmed fact: `tests/infra/test_build_matrix_v1_0_2.py` directly covers the module.
- Confirmed fact: current LAW/Technical SSoT documentation references the module.
- Contract role: directly tested and documented; versioned filename is not deadness evidence.
- Cleanup: none.

### CAND-026 — Golden diagnostic helpers

Paths:

- `scripts/ci_debug_phase01_mentor_pool_diff.py`
- `scripts/ci_summarize_mentor_join_key_issues.py`

Classification: **KEEP**.

- Why new: these standalone diagnostics were not separately adjudicated in the prior manifest.
- Confirmed fact: `docs/CI_Golden_Regression.md` explicitly instructs maintainers to run both commands during gated Golden snapshot diagnosis/refresh.
- Operational role: documented human-invoked Golden maintenance workflow.
- Cleanup: none.

### CAND-027 — `scripts/performance/run_perf_suite.py`

- Candidate type: standalone performance tooling.
- Classification: **KEEP**.
- Why new: performance tooling was not a prior material cleanup candidate.
- Confirmed fact: repository performance checklist/risk documentation references the command.
- Operational role: developer-facing performance verification workflow.
- Cleanup: none.

## Prompt 5 classification summary

- New candidates: **6**
- KEEP: **4**
- CONFIRMED_DEAD: **0**
- SUPERSEDED: **0**
- OWNER_DECISION_REQUIRED: **0**
- DEFERRED_UNRESOLVED: **2**

## Cleanup execution

### Dead code removed

None. No newly discovered candidate crossed the high-confidence deletion threshold.

### Superseded code removed

None.

### Transitive cleanup

None. There was no approved dead/superseded parent candidate.

### Owner decisions required

None. The two deferred utilities are unresolved reachability/retirement questions, not demonstrated product-capability decisions; ordinary technical uncertainty was not shifted to the Owner.

## Deferred non-cleanup findings

Existing Pandas deprecation warnings and GitHub Actions runtime deprecation warnings remain outside cleanup. No bug fix, refactor, dependency/uv migration, Qt/Pandas modernization, CI modernization, typing sweep, architecture redesign, or performance optimization was performed.

# Prompt 5 verification receipt

## Static verification

`ruff check .` → **PASS** (`All checks passed!`).

## Core / Infra / Integration

Command:

`pytest tests/unit tests/infra tests/integration --maxfail=1 -q`

Result:

- **1219 passed**
- **4 skipped**
- **0 failed**

This exactly matches the Prompt 4 profile; no count reconciliation is required.

## Pre-merge verification

`python tools/ci/pre_merge_guards.py` → **PASS**

- **335 passed**
- **0 failed**

LAW/SSoT Drift Guard → **PASS**.

## Golden Regression

Golden was executed using the existing path-filtered workflow on a verification-only branch derived from the exact Prompt 5 candidate state, plus one inert documentation trigger file under `docs/golden_datasets/`. The trigger was not runtime source, config, a golden dataset, a golden baseline, or a canonical operational input.

Results:

- Phase01 → **PASSED (no drift detected)**
- Phase02 with `GOLDEN_DIFF_AUDITOR_DECISION=BASELINE_OK` → **success**
- Scenario status → **success**
- Final message → `golden regression completed successfully`

The final Prompt 5 application source, config, golden datasets/baselines, and canonical inputs are byte-identical to the Golden-tested candidate state. The temporary trigger is not part of the final Prompt 5 branch.

## UI verification

`pytest tests/ui --maxfail=1 -q` → **PASS**

- **77 passed**
- **3 skipped**
- **0 failed**

This exactly matches the Prompt 4 GitHub profile; no cleanup-caused UI regression exists.

## Runtime startup smoke

`NOT_RUN_ENVIRONMENT_LIMITATION` — available connector actions do not expose an arbitrary interactive GUI startup command. Because Prompt 5 changes no executable/config/runtime material and all automated retained-behavior gates pass, this limitation is not a blocker.

# Final Prompt 5 scope audit

Prompt 5 changes only the existing cleanup governance artifacts:

1. `docs/cleanup/CLEANUP_ADJUDICATION_MANIFEST.md`
2. `docs/cleanup/cleanup_adjudication_manifest.json`

Prompt 5 modifies no production code, config, tests, CI workflow, dependencies, golden inputs/baselines, database/schema, runtime resources, or developer utilities. Matrix2 remains untouched and `main` remains untouched.

# Discovery closure

**`FINAL_DEAD_CODE_DISCOVERY_CLOSED`**

Consequences:

- no further proactive dead-code census is authorized before Prompt 6;
- `CAND-023` and `CAND-024` remain retained as `DEFERRED_UNRESOLVED`;
- future deletion of those or other surfaces requires genuinely new evidence arising from later development, not another speculative census;
- Prompt 6 is verification/freeze only, not another discovery pass.

Prompt 6 has not begun.

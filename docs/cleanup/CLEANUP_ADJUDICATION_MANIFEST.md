# Cleanup Adjudication Manifest — Matrix-V3.0

## Current cleanup state

**Prompt 5 status: `VERIFICATION_PENDING`**

This is the existing cleanup governance record extended for the final bounded discovery pass. Prompt 2–4 history remains authoritative and closed except where explicitly stated below.

### Verified lineage

- Repository: `rezahh107/Matrix-V3.0`
- Original baseline commit: `24a13e928808715953b3c1260b6ac7271c7dfe31`
- Original baseline tree: `03fb418444badc04412228596efc04c904ec8cfd`
- Baseline tag: `matrix3-baseline-from-matrix2`
- Prompt 2 adjudication: `7ef738b53174c9b04fed8b3890ebe7f623439939`
- Prompt 3 cleanup: `a26b33dd0887090c75e1e07ebcbb4a3e586cfc14`
- Prompt 4 cleanup: `8132f9dbde5cebc46a1b6a072ab69f275c23f609`
- Prompt 4 tree: `6551fa00f07cef5f4c4795f1736c8778e2624415`
- Prompt 5 branch: `cleanup/final-bounded-discovery`

## Closed Prompt 2–4 history

Prompt 2 adjudicated 21 material candidates: 12 KEEP, 6 CONFIRMED_DEAD historical `.patch` artifacts, 0 SUPERSEDED, 2 OWNER_DECISION_REQUIRED diagnostic tools, and 1 NEEDS_INVESTIGATION student-import wrapper.

Prompt 3 removed exactly the six historical `.patch` artifacts and no production code. Prompt 4 resolved `CAND-021` (`app/infra/students/student_import_pipeline.py`) as `CONFIRMED_DEAD`, removed that wrapper, and removed only its dedicated mypy override entry. Prompt 4 closed with Ruff PASS, core/infra/integration 1219 passed / 4 skipped / 0 failed, pre-merge 335 passed / 0 failed, Golden Regression PASS/no drift, and UI 77 passed / 3 skipped / 0 failed.

The following prior decisions remain protected and were not reopened in Prompt 5:

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
- version/legacy-named production modules surfaced by repository search;
- Golden diagnostic helpers;
- performance tooling;
- package exposure and `pyproject.toml` package scope;
- documentation-defined operational commands;
- direct/string references, tests/CI, and available Git path history for material leads.

Prompt 5 did **not** restart a full census and did **not** reopen the prior 21 candidates.

## New candidates

### CAND-022 — `tools/packaging/matrix2_gui.spec` and packaging guide

- Candidate type: old-name packaging surface.
- Prompt 5 classification: **KEEP**.
- Why new: packaging tooling was not a material candidate in the prior 21-candidate manifest.
- Confirmed fact: `tools/packaging/README_packaging.md` explicitly instructs developers to run `pyinstaller tools/packaging/matrix2_gui.spec` and documents the produced `Matrix2-GUI.exe` distribution and runtime config layout.
- Runtime reachability: not application runtime; this is a human-invoked packaging workflow.
- Compatibility/operational role: affirmative, documented developer delivery capability.
- Inference: the `Matrix2` name is historical branding, not proof of deadness.
- Cleanup performed: none.

### CAND-023 — `scripts/compare_excel_structure.py`

- Candidate type: apparently orphaned standalone developer utility.
- Prompt 5 classification: **DEFERRED_UNRESOLVED**.
- Why new: not represented in the prior manifest.
- Confirmed fact: repository search found no caller or documentation reference beyond the script itself; it is not part of the packaged `app` namespace because setuptools includes only `app` and `app.*`.
- Confirmed fact: the file has an explicit `__main__` command interface and compares workbook sheet/header structures, returning an operational exit status.
- Runtime/dynamic/config reachability: no application, CLI, GUI, config, CI, or subprocess reference was found by bounded search.
- Git history: path history exists in November 2025, but available history does not establish whether it was a one-off migration aid or an intentionally retained ad-hoc diagnostic.
- Residual uncertainty: a developer can intentionally invoke this command manually; repository evidence neither proves a currently supported workflow nor proves the command has no remaining operational use.
- Cleanup performed: none. Ambiguous executable utility preserved.

### CAND-024 — `scripts/csap_evidence_pack.py`

- Candidate type: hard-coded evidence-generation utility.
- Prompt 5 classification: **DEFERRED_UNRESOLVED**.
- Why new: not represented in the prior manifest.
- Confirmed fact: the script prints Git provenance and SHA-256 hashes for a fixed CSAP-related file set; it is a direct `__main__` command and uses `git` through subprocess.
- Confirmed fact: bounded exact-name/content search found no documentation, CI, application, config, or other in-repository caller for the command.
- Confirmed fact: it is outside the packaged `app` namespace.
- Git history: the path was changed during December 2025 hardening/evidence work, including commits associated with join-bucketing/eligibility evidence and unknowns preflight/UI gating.
- Residual uncertainty: this strongly resembles phase-specific evidence tooling, but the executable command itself can still produce a provenance/hash evidence pack and the repository contains no explicit retirement record. That remaining operational possibility is material enough to prevent deletion in the final bounded pass.
- Cleanup performed: none.

### CAND-025 — `app/infra/matrix/build_matrix_v1_0_2.py`

- Candidate type: version-named production module / possible old-new pair.
- Prompt 5 classification: **KEEP**.
- Why new: surfaced by final version-name search; not a prior material candidate.
- Confirmed fact: repository references include `tests/infra/test_build_matrix_v1_0_2.py` and current LAW/Technical SSoT documentation references the module.
- Runtime/contract role: retained implementation is directly covered by tests and documentation; filename versioning is not deadness evidence.
- Cleanup performed: none.

### CAND-026 — `scripts/ci_debug_phase01_mentor_pool_diff.py` and `scripts/ci_summarize_mentor_join_key_issues.py`

- Candidate type: diagnostic CI/Golden helper surface.
- Prompt 5 classification: **KEEP**.
- Why new: these standalone diagnostics were not separately adjudicated in the prior manifest.
- Confirmed fact: `docs/CI_Golden_Regression.md` explicitly instructs maintainers to run both commands during gated Golden snapshot diagnosis/refresh.
- Operational role: documented human-invoked Golden maintenance workflow.
- Cleanup performed: none.

### CAND-027 — `scripts/performance/run_perf_suite.py`

- Candidate type: standalone performance tooling.
- Prompt 5 classification: **KEEP**.
- Why new: performance tooling was not a prior material candidate.
- Confirmed fact: repository documentation references the command from performance PR/checklist/risk documentation.
- Operational role: developer-facing performance verification workflow; performance modernization is out of scope and no removal evidence exists.
- Cleanup performed: none.

## Prompt 5 classification summary

- New candidates: 6
- KEEP: 4
- CONFIRMED_DEAD: 0
- SUPERSEDED: 0
- OWNER_DECISION_REQUIRED: 0
- DEFERRED_UNRESOLVED: 2

## Dead code removed

None. No newly discovered candidate crossed the high-confidence production/developer-tool deletion threshold.

## Superseded code removed

None.

## Transitive cleanup

None, because Prompt 5 authorizes transitive cleanup only from an approved dead/superseded parent candidate.

## Owner decisions required

None. The two deferred utilities are reachability/retirement ambiguities, not demonstrated supported-capability decisions; they are therefore retained without shifting ordinary technical uncertainty to the Owner.

## Deferred non-cleanup findings

Existing Pandas and GitHub Actions runtime deprecation warnings remain outside cleanup. No bug fix, refactor, dependency/uv migration, Qt/Pandas modernization, CI modernization, typing sweep, architecture redesign, or performance optimization was performed.

## Prompt 5 verification receipt

Verification is pending on the exact Prompt 5 candidate state. This section will be finalized after Ruff, core/infra/integration, pre-merge, Golden Regression, and UI gates complete.

## Prompt 5 scope audit

Before verification, the proposed Prompt 5 repository change is documentation/governance only:

1. update `docs/cleanup/CLEANUP_ADJUDICATION_MANIFEST.md`;
2. update `docs/cleanup/cleanup_adjudication_manifest.json`.

No production code, config, test, CI, dependency, golden input/baseline, database, runtime resource, or developer utility is proposed for deletion or modification.

Prompt 6 has not begun.

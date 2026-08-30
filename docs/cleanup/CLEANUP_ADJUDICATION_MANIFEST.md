# Cleanup Adjudication Manifest — Matrix-V3.0

## 1. Executive Assessment

**Final status: `ADJUDICATION_COMPLETE_WITH_OPEN_ITEMS`**

This adjudication starts from the verified Matrix3 baseline commit `24a13e928808715953b3c1260b6ac7271c7dfe31` and tree `03fb418444badc04412228596efc04c904ec8cfd`. The central safety conclusion is that the repository contains several elements that *look* legacy, duplicated, or incidental but are demonstrably live. In particular, `app/infra/cli_legacy.py`, the `app/infra/cli/` facade, the StudentPipelineV3 compatibility shim, root golden-input workbooks, and thin verification wrappers must not be removed merely because a newer-looking path exists.

The current Prompt 3 deletion-safe scope is deliberately narrow: **six root-level `.patch` delivery artifacts are `CONFIRMED_DEAD`**. Their represented changes are already incorporated into current tracked source, covered by current tests/verification surfaces, and anchored in Git history. No active repository mechanism was found that applies those patch files.

Two standalone diagnostic commands are technically separable but represent developer/operator capabilities, so they are `OWNER_DECISION_REQUIRED`. One StudentPipeline convenience wrapper is `NEEDS_INVESTIGATION` because in-repository callers were not found but external import compatibility cannot be disproved.

Classification totals:

| Classification | Count |
|---|---:|
| `KEEP` | 12 |
| `CONFIRMED_DEAD` | 6 |
| `SUPERSEDED` | 0 |
| `OWNER_DECISION_REQUIRED` | 2 |
| `NEEDS_INVESTIGATION` | 1 |
| **Total candidates adjudicated** | **21** |

The conservative rule used throughout was: **absence of an import is not affirmative deadness**. Dynamic imports, `__main__` entrypoints, compatibility re-exports, CI subprocesses, filesystem inputs, golden datasets, database paths, and human-invoked tools were treated as reachability mechanisms.

## 2. Baseline Receipt

- Repository: `rezahh107/Matrix-V3.0`
- Verified baseline commit: `24a13e928808715953b3c1260b6ac7271c7dfe31`
- Verified baseline tree: `03fb418444badc04412228596efc04c904ec8cfd`
- Baseline tag: `matrix3-baseline-from-matrix2`
- Verified tracked-file count supplied by Prompt 1: `719`
- Analysis branch: `cleanup/adjudication-manifest`
- Branch creation: created directly from `24a13e928808715953b3c1260b6ac7271c7dfe31` because it did not previously exist.
- `main` at analysis start: `24a13e928808715953b3c1260b6ac7271c7dfe31`
- Baseline tag target at analysis start: `24a13e928808715953b3c1260b6ac7271c7dfe31`
- Adjudication branch immediately before artifact creation: `24a13e928808715953b3c1260b6ac7271c7dfe31`

### Cleanliness gate

The GitHub connector operates on remote refs and has no mutable local checkout worktree. The equivalent cleanliness check therefore used the remote branch delta: the adjudication branch did not exist, was created directly from the verified baseline commit, and still pointed to that exact commit before these documentation artifacts were written. Thus no pre-existing branch changes were carried into Prompt 2.

### Prompt 1 execution evidence accepted as the verified dynamic baseline

- Core / Infra / Integration: `1220 passed, 4 skipped, 0 failed` on Matrix2 and Matrix3.
- Pre-merge guards: `335 passed, 0 failed` on both.
- Golden regression: passed with no drift on both.
- GUI startup: both repositories launch, `MainWindow` loads, exit code `0`.
- UI suite: `77 passed, 1 skipped, 2 failed` on both; the same two failures are the known PySide6/QSignalSpy `len()` verification-environment observation.

Prompt 2 did not fix, normalize, or otherwise alter those known UI failures.

## 3. Repository Surface Summary

The following reachable/responsibility surfaces were explicitly considered before classifying candidates:

- **Application/GUI entry:** `run_gui.py` → `app/main.py` → PySide6 application/MainWindow startup.
- **Core runtime:** `app/core/`, including allocation, matrix construction, canonicalization, common contracts, QA and policy loading.
- **Infrastructure:** `app/infra/`, including CLI, Excel I/O/export, reference repositories, student/mentor pipelines, history and persistence.
- **CLI:** `app/infra/cli/__init__.py`, `app/infra/cli_legacy.py`, golden CLI entrypoints and standalone `__main__` commands.
- **Persistence/schema responsibilities:** `app/infra/local_database.py` and repositories/import/history/UI consumers of `LocalDatabase`.
- **CI:** `.github/workflows/ci-main.yml`, `.github/workflows/golden-regression.yml`, `tools/ci/*`, golden runners and guard subprocesses.
- **Tests/fixtures:** unit, infra, integration, UI, CI guard and golden regression surfaces.
- **Configuration:** `config/policy.json`, exporter/dashboard/logging config and other policy surfaces.
- **Resources/filesystem inputs:** `resources/translations/`, root canonical workbooks, golden datasets and config-selected file paths.
- **Dynamic mechanisms:** `importlib/import_module` in GUI startup, `__getattr__` delegation in CLI compatibility facade, `__main__` entrypoints, subprocess-driven CI tools, filesystem/config selection and Qt signal/slot/UI wiring.
- **Compatibility:** explicit re-export shims and historical module paths.
- **Git history:** targeted history checks for patch application and join/export hardening.

No candidate was declared dead solely from text-search absence.

## 4. Adjudication Summary by Classification

### `KEEP` — 12

Important retained surfaces include GUI entrypoints, the live legacy-named CLI implementation, explicit compatibility facades/shims, contract gateways, CI/golden runners, canonical golden workbooks and local persistence infrastructure.

### `CONFIRMED_DEAD` — 6

All six are root-level `.patch` delivery artifacts. They are inert unified diffs whose material changes are already represented in current tracked source and Git history.

### `SUPERSEDED` — 0

No candidate satisfied the full supersession bar. Several files have concrete newer/canonical implementations behind them, but their old import or invocation surfaces still carry compatibility responsibility or unresolved external-consumer risk. They were therefore retained or left for investigation.

### `OWNER_DECISION_REQUIRED` — 2

Two root standalone diagnostic commands are not runtime dependencies but provide manual developer/operator capabilities. Removing them is a support/capability decision, not dead-code cleanup.

### `NEEDS_INVESTIGATION` — 1

`app/infra/students/student_import_pipeline.py` has no demonstrated in-repository caller, but its external import/API compatibility is not provably unused.

## 5. CONFIRMED_DEAD Findings

### CAND-013 — `CSAP_CENTER_ZERO_INFER_CANON_fix.patch`

- **Classification:** `CONFIRMED_DEAD`
- **Confidence:** HIGH
- **Observed role:** historical unified diff adding manager-to-center inference to `app/core/canonical_frames.py` plus test coverage.
- **Evidence:** current `app/core/canonical_frames.py` contains `_infer_center_from_manager`; Git history contains merge commit `3acaa83210081c35c440a7cbe8f426386af8d2a8` explicitly applying the student-id/center-inference fixes.
- **Why it matters:** the *behavior* carried by the patch is live, but the `.patch` file itself is not.
- **Cleanup implication:** Prompt 3 may delete this patch artifact only.
- **Risk if wrong:** loss of an undocumented archival/distribution convenience; no in-repo execution, migration, compatibility or CI consumer was found.

### CAND-014 — `CSAP_STUDENT_ID_DESYNC_fix.patch`

- **Classification:** `CONFIRMED_DEAD`
- **Confidence:** HIGH
- **Evidence:** current `app/core/allocate_students.py` contains `_canonical_student_id`; merge commit `3acaa83210081c35c440a7cbe8f426386af8d2a8` records the applied desync fix.
- **Cleanup implication:** delete the patch artifact only; do not alter the current student-id safeguards.
- **Risk if wrong:** same archival-only risk as above.

### CAND-015 — `FIX-INV-QA-ALLOC-JOIN-02-mentor-merge-or-and-better-message.patch`

- **Classification:** `CONFIRMED_DEAD`
- **Confidence:** HIGH
- **Evidence:** current `app/infra/validators/join_keys.py` contains student merge indicators, mentor-id-first lookup, alias fallback and `mentor_lookup_mode`; current tests reference the behavior; merge commit `7186876c597a92e793b9810b5ca39532a2039f87` records the hardening.
- **Cleanup implication:** patch file removable; current validator/CLI behavior must remain unchanged.
- **Risk if wrong:** only an undocumented patch-distribution workflow was not observable.

### CAND-016 — `FIX-INV-QA-ALLOC-JOIN-02-use-wildcard.patch`

- **Classification:** `CONFIRMED_DEAD`
- **Confidence:** HIGH
- **Evidence:** current CLI uses `validate_allocation_join_keys_with_wildcard`; the implementation exists in `app/infra/qa/alloc_join_validation.py`; tests cover it; merge commit `8cac97e232f266bdd6cdb19ba29e2fd41cbefc24` records wildcard-aware audit integration.
- **Cleanup implication:** delete only the historical diff file.
- **Risk if wrong:** undocumented archival consumption only.

### CAND-017 — `HARDEN-join-key-audit-normalize-student_id.patch`

- **Classification:** `CONFIRMED_DEAD`
- **Confidence:** HIGH
- **Evidence:** current `app/infra/validators/join_keys.py` strips/normalizes `student_id` in the student subset and allocation base before the audit merge; merge commit `8cac97e232f266bdd6cdb19ba29e2fd41cbefc24` records the normalization hardening.
- **Cleanup implication:** patch artifact removable; validator logic remains.
- **Risk if wrong:** undocumented archival consumption only.

### CAND-018 — `INC-EXPORT-ID-DESYNC-2025-12-26_REL.patch`

- **Classification:** `CONFIRMED_DEAD`
- **Confidence:** HIGH
- **Evidence:** current `app/infra/cli_legacy.py` contains `_enforce_allocation_export_invariants`; current tests include export invariant and export spine checks; merge commit `9664cbddeb5116c4a906c0e44774f7a10875a6d5` records the applied export/student-id hardening.
- **Cleanup implication:** patch file removable; production invariant code and its tests are not cleanup candidates.
- **Risk if wrong:** undocumented external distribution use only.

### Common affirmative-deadness evidence for all six patch files

1. Each file is a unified textual diff, not an imported Python module, configuration input, resource asset or persisted schema.
2. `pyproject.toml` packages `app` / `app.*`; the root patch files are outside the packaged Python surface.
3. Active CI workflows execute Python guards/tests/runners and do not apply these patch files.
4. Their key represented changes are present in current tracked source.
5. Targeted Git history records the corresponding applied/merged fixes.
6. Prompt 1 regression evidence succeeds on the current source baseline without any patch-application step.
7. No independent compatibility, migration, persistence or operational role for the patch *files themselves* was identified.

## 6. SUPERSEDED Findings

**None.**

This is intentional. For example, `app/infra/students/student_pipeline_v3.py` has the concrete successor implementation `app/infra/students/pipeline_v3.py`, but the old path is an explicit compatibility shim and is directly imported by tests. Likewise, `app/infra/cli_legacy.py` is not superseded by the `app/infra/cli/` package; the package delegates to and re-exports the legacy-named module.

A newer path was not treated as evidence that the older path is removable.

## 7. OWNER_DECISION_REQUIRED Findings

### CAND-019 — `debug_array_error.py`

- **Classification:** `OWNER_DECISION_REQUIRED`
- **Confidence:** HIGH
- **Observed role:** standalone manual allocation troubleshooting command.
- **Reachability:** direct human invocation through `__main__`; no internal caller is required for such a tool.
- **Capabilities:** runs allocation; can request audit, metrics and determinism checking.
- **Why it matters:** removing it would intentionally remove a developer/operator troubleshooting workflow rather than merely delete unreachable implementation.
- **Cleanup implication:** keep out of Prompt 3 unless Owner explicitly chooses to retire the workflow.
- **Risk if classification is wrong:** treating it as dead would silently remove incident-response capability.

### CAND-020 — `debug_pool_alignment.py`

- **Classification:** `OWNER_DECISION_REQUIRED`
- **Confidence:** HIGH
- **Observed role:** advanced standalone student-vs-pool alignment diagnostic.
- **Capabilities:** workbook inspection, canonicalization, staged filtering trace, per-stage CSV dumps and optional ZIP evidence.
- **Why it matters:** it is a manual diagnostic surface; lack of a normal import does not make it dead.
- **Cleanup implication:** keep unless Owner chooses to retire this workflow.
- **Important distinction:** `app/core/debug_pool_alignment.py` is separately used by current runtime/CLI code and remains `KEEP` regardless of the decision on this root command.

## 8. NEEDS_INVESTIGATION Findings

### CAND-021 — `app/infra/students/student_import_pipeline.py`

- **Classification:** `NEEDS_INVESTIGATION`
- **Confidence:** MEDIUM
- **Observed role:** thin convenience wrapper exposing `run_student_pipeline_from_excel()` and `run_student_pipeline_from_dataframe()` around canonical `StudentPipelineV3`.
- **Evidence suggesting removability:** repository search found no in-repository call site for `run_student_pipeline_from_excel`; direct module-name search primarily reaches `pyproject.toml`.
- **Evidence against declaring dead/superseded:** it is intentionally type-checked in project configuration; it exposes a plausible package API; external scripts/consumers are outside the repository evidence boundary.
- **Successor:** `app/infra/students/pipeline_v3.py` covers the underlying implementation but does not by itself prove that the wrapper's API/import path is retired.
- **Required investigation:** check release/API compatibility policy, historical documentation and any known out-of-repo automation/import consumers.
- **Cleanup implication:** no Prompt 3 deletion until that evidence closes the compatibility question.

## 9. Important KEEP Findings

### Live legacy CLI — `app/infra/cli_legacy.py`

This is the strongest “legacy name != dead code” finding. `app/infra/cli/__init__.py` explicitly says it re-exports the legacy single-file implementation to preserve helper access, wildcard-imports it and delegates `__getattr__` to it. The module itself imports and orchestrates current allocation, matrix, canonicalization, QA, export, persistence and reference implementations, and many tests directly exercise it.

**Risk of wrong deletion:** broad CLI and export/QA breakage.

### CLI facade — `app/infra/cli/__init__.py`

The package is not a replacement that makes `cli_legacy.py` removable; it is a compatibility facade over it.

### StudentPipelineV3 shim — `app/infra/students/student_pipeline_v3.py`

The file explicitly identifies itself as a compatibility shim and is imported by `tests/infra/students/test_student_pipeline_v3.py`. The canonical implementation lives in `pipeline_v3.py`, but both paths currently have responsibilities.

### Contract gateway — `app/core/allocate.py`

`enforce_allocation_output_contracts()` is imported through `app.core`, called from `allocate_students.py`, and covered by the contract harness. Its small size is not evidence of dispensability.

### GUI launch surfaces — `run_gui.py`, `app/main.py`

`run_gui.py` is an explicit root-level double-click entrypoint that calls `app.main.run()`. `app/main.py` contains GUI bootstrap and dynamic import logic. Prompt 1 also verified actual MainWindow startup.

### Golden input workbooks — `students.xlsx`, `0918.xlsx`

These root binary files look like likely accidental artifacts, but `tests/golden/README.md` explicitly designates them as canonical golden inputs. Integration tests reference them. Both are `KEEP`.

### Golden wrapper/workflow — `scripts/run_golden_regression.py`, phase runners, workflow

The thin wrapper is a real executable proxy to the infra regression runner. The golden workflow directly executes phase01/phase02 and monitors the wrapper/config/dataset paths. Prompt 1's no-drift golden result reinforces their verification role.

### Pre-merge guards — `tools/ci/pre_merge_guards.py`

Actively invoked by `.github/workflows/ci-main.yml`; Prompt 1 reports 335 passing guards.

### Local persistence — `app/infra/local_database.py`

Repository-wide `LocalDatabase` references span repository/import/history/UI/student paths. Persistence/schema compatibility makes this a high-risk cleanup area and clearly `KEEP`.

## 10. Transitive Cleanup Map

For the six `CONFIRMED_DEAD` patch artifacts, **no production-code transitive deletion is authorized or expected**. The intended Prompt 3 chain is:

`root .patch artifact` → delete that patch file only → run existing guards/tests/golden verification → no source/test/golden changes unless an unexpected reference proves this adjudication wrong.

No import, config entry, fixture, CI command or documentation command has been identified that must be edited to compensate for deleting those six patch files.

If the Owner later retires either diagnostic command, Prompt 3 must separately re-check documentation, operator notes, packaging instructions and any external runbooks before deleting the script. That future chain is **not** pre-authorized here.

`app/infra/students/student_import_pipeline.py` has no authorized transitive cleanup chain because its status remains `NEEDS_INVESTIGATION`.

## 11. Deferred Non-Cleanup Findings

The following are explicitly outside Prompt 2 and remain deferred even where the repository contains relevant evidence:

- uv migration.
- requirements/`pyproject.toml` dependency restructuring.
- dependency or Python-version modernization.
- Qt/PySide6 modernization.
- the two known QSignalSpy UI verification-environment failures.
- pandas modernization/warning cleanup.
- performance optimization.
- circular-import redesign.
- architecture/API redesign.
- broad typing cleanup.
- CI modernization.
- refactoring `cli_legacy.py` because of size/name.
- changing database/schema behavior.
- changing golden baselines.
- bug fixes discovered incidentally.

No such change was made.

## 12. Recommended Scope for Prompt 3

Prompt 3 is safe to begin **only with a frozen removal scope consisting of these six files**:

1. `CSAP_CENTER_ZERO_INFER_CANON_fix.patch`
2. `CSAP_STUDENT_ID_DESYNC_fix.patch`
3. `FIX-INV-QA-ALLOC-JOIN-02-mentor-merge-or-and-better-message.patch`
4. `FIX-INV-QA-ALLOC-JOIN-02-use-wildcard.patch`
5. `HARDEN-join-key-audit-normalize-student_id.patch`
6. `INC-EXPORT-ID-DESYNC-2025-12-26_REL.patch`

Prompt 3 should not delete, refactor or “fold away” the production code represented by those patches. It should delete the artifacts only, then run the existing regression gates.

Exclude from Prompt 3 until resolved:

- `debug_array_error.py`
- `debug_pool_alignment.py`
- `app/infra/students/student_import_pipeline.py`

All `KEEP` findings are hard exclusions.

## 13. Owner Decisions Required

1. **`debug_array_error.py`:** If we remove this file, developers/operators lose the one-command allocation troubleshooting workflow with optional audit, metrics and determinism checks. **Is that manual troubleshooting capability still intended to be supported?**

2. **`debug_pool_alignment.py`:** If we remove this file, developers/operators lose the detailed student-versus-mentor-pool tracing command that shows where candidates disappear stage by stage and can emit trace dumps. **Is that diagnostic workflow still intended to be supported?**

No Owner decision is requested for the technical safety of individual Python symbols. `app/infra/students/student_import_pipeline.py` remains an evidence-gathering task, not an Owner question at this stage.

## 14. Final Status

**`ADJUDICATION_COMPLETE_WITH_OPEN_ITEMS`**

Self-check:

- Production code deleted or modified: **No**
- Runtime behavior intentionally changed: **No**
- Bug fix performed: **No**
- Dependency/uv modernization performed: **No**
- Matrix2 modified: **No**
- Every `CONFIRMED_DEAD` item has converging source/history/CI or verification evidence: **Yes**
- Every `SUPERSEDED` item names/proves successor: **N/A; count is zero**
- Capability-removal cases classified `OWNER_DECISION_REQUIRED`: **Yes**
- Ambiguous external/API case remains `NEEDS_INVESTIGATION`: **Yes**
- Dynamic/config/CLI/CI/test/persistence paths considered: **Yes**
- Markdown and JSON classifications/counts agree: **Yes**
- Prompt 3 execution started: **No**

**Prompt 3 readiness:** safe for the six-file `CONFIRMED_DEAD` patch-artifact scope only; not safe for unresolved owner/investigation items.

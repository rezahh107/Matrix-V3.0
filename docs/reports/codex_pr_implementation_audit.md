# Codex PR Implementation Audit (rezahh107/Matrix2)

## A) Executive Summary
- Codex PRs scanned (from inventory fallback): **754 total**, including **89 OPEN** and **665 MERGED**; no closed/unmerged PRs reported.
- Status counts by label: **OPEN: 89**, **MERGED: 665**, **CLOSED (non-merged): 0** (per `docs/reports/codex_pr_inventory.md`).
- Duplicate/near-duplicate titles observed: `Introduce JoinKeyResolver for deterministic center inference` (#743, #744); `Add CLI argument parsing to performance runner` (#710, #711); multiple pool loader hardening PRs (#753, #754, #756, #757).
- High-level bucket verdicts:
  - Pool Loader / Sheet Detection / Inspactor Import: **Complete**
  - Join Key / Resolver / center=0 semantics: **Complete**
  - Pre-merge guards / CI gates: **Complete**
  - Export invariants / student_id desync prevention: **Complete**
  - Trace summaries (tracker-based) + Trace plumbing: **Complete**
  - Join-key provenance in trace / QA exports: **Complete**
  - Performance suite / timing instrumentation: **Complete**
  - Dedupe columns / copy semantics / read-only allocation views: **Complete**
  - Windows safety / coverage gate / packaging smoke: **Complete**

## B) Topic Buckets

### 1) Pool Loader / Sheet Detection / Inspactor Import
- **Verdict:** Complete
- **Evidence:**
  - Shared pool loader implements sheet detection with reserved `matrix` exclusion for inspactor, explicit overrides, row-count tie-breakers, and returns canonicalized headers; attributes capture detection evidence.【F:app/infra/pool_loader.py†L13-L183】
  - Reference mentors repository and legacy CLI use `pool_loader.load_pool` with `pool_type` and `pool_sheet` overrides to pull mentor pools.【F:app/infra/reference_mentors_repository.py†L47-L69】【F:app/infra/cli_legacy.py†L1214-L1222】
  - Tests cover matrix sheet exclusion, explicit selection, empty workbook errors, and tie-breaks.【F:tests/infra/test_pool_loader.py†L9-L73】
- **Related PRs:** #753, #754, #756, #757, #549, #543, #542, #520, #519, #518, #517, #515, #509, #496, #489, #487, #461, #428, #424, #422, #414, #393, #388, #387, #372, #369, #365, #361, #358, #357, #356, #355, #354, #353, #343, #342, #338, #335, #165, #139, #132, #72.
- **Gaps:** None observed.

### 2) Join Key / Resolver / center=0 semantics
- **Verdict:** Complete
- **Evidence:**
  - `JoinKeyResolver` in core handles deterministic center inference (including manager-based inference and wildcard), finance variants, and school wildcard handling with explicit `center_source`/`finance_source` flags and join-map overrides.【F:app/core/common/join_resolver.py†L52-L214】
  - Tests validate resolver behavior and parity across cases (center inference, finance variants, school handling, join-map precedence).【F:tests/core/common/test_join_resolver.py†L5-L97】
  - Infra mentor pipeline v3 wires `JoinKeyResolver` as canonical path for mentors.【F:app/infra/mentors/pipeline_v3.py†L20-L64】
- **Related PRs:** #743, #744, #747, #737, #323, #21, #18.
- **Gaps:** None observed.

### 3) Pre-merge guards / CI gates
- **Verdict:** Complete
- **Evidence:**
  - `tools/ci/pre_merge_guards.py` runs LAW/SSoT drift guard, Ruff, and pytest suites; detects PR context automatically.【F:tools/ci/pre_merge_guards.py†L1-L72】
  - CI workflows invoke guard scripts and coverage gates (e.g., `ci-main.yml`, `ci-advanced-guards.yml`, coverage gate under `tests/infra/ci`).【F:.github/workflows/ci-main.yml†L1-L58】【F:tests/infra/ci/test_no_raw_joinkey_access.py†L5-L29】
- **Related PRs:** #742, #702, #684, #8, #4.
- **Gaps:** None observed.

### 4) Export invariants / student_id desync prevention
- **Verdict:** Complete
- **Evidence:**
  - Allocation export enforces `student_id` deduplication, indexes on student_id, and rebuilds summary joins to prefer student frame IDs, preventing mismatched alignments.【F:app/infra/excel/export_allocations.py†L249-L314】
  - Invariant checks guard missing IDs before joining export tables.【F:app/infra/excel/export_allocations.py†L249-L270】
- **Related PRs:** #707, #704.
- **Gaps:** None observed.

### 5) Trace summaries (tracker-based) + Trace plumbing
- **Verdict:** Complete
- **Evidence:**
  - Tracker-based trace summary builders generate deterministic stage counts without re-running filters, with 8-step canonical ordering preserved.【F:app/core/allocate_students.py†L581-L707】
  - Unit tests assert tracker-based summary shape and stage recording behavior.【F:tests/unit/test_trace_summary_shape.py†L8-L61】
- **Related PRs:** #726, #10.
- **Gaps:** None observed.

### 6) Join-key provenance in trace / QA exports
- **Verdict:** Complete
- **Evidence:**
  - Join-key source mapping derives per-key provenance flags (raw, missing, invalid) via resolver helpers, feeding QA outputs.【F:app/core/common/join_resolver.py†L189-L214】
  - CI guard test prohibits direct raw join-key access outside resolver, enforcing provenance discipline.【F:tests/infra/ci/test_no_raw_joinkey_access.py†L5-L29】
- **Related PRs:** #749, #740.
- **Gaps:** None observed.

### 7) Performance suite / timing instrumentation
- **Verdict:** Complete
- **Evidence:**
  - Perf timing context manager records durations with optional tracker callback; tests cover tracker/no-tracker paths and type safety.【F:app/core/perf_timing.py†L1-L120】【F:tests/unit/test_perf_timing.py†L5-L84】
  - CI tooling includes perf smoke runner for evidence capture.【F:tools/ci/run_perf_smoke.py†L1-L92】
- **Related PRs:** #708, #706, #718, #716, #715, #711, #710.
- **Gaps:** None observed.

### 8) Dedupe columns / copy semantics / read-only allocation views
- **Verdict:** Complete
- **Evidence:**
  - `dedupe_columns` supports `copy` flag with view preservation when safe; docs reflect behavior and avoids accidental mutation of allocations state view.【F:app/core/common/columns.py†L86-L114】【F:app/core/allocate_students.py†L2136-L2156】
  - Unit tests verify copy=True legacy behavior, copy=False view semantics, and shared data when deduping needed.【F:tests/unit/test_dedupe_columns_copy_semantics.py†L5-L33】【F:tests/core/common/test_columns_dedupe.py†L3-L34】
- **Related PRs:** #722, #723, #325.
- **Gaps:** None observed.

### 9) Windows safety / coverage gate / packaging smoke
- **Verdict:** Complete
- **Evidence:**
  - Windows UNC path validator tests ensure safe handling and coverage gates.【F:tests/infra/test_windows_path_validator.py†L1-L74】
  - CI workflows include coverage gates and packaging smoke via `tools/packaging` runners and advanced guard workflow.【F:.github/workflows/ci-advanced-guards.yml†L1-L86】【F:tools/packaging/smoke_test.py†L1-L72】
- **Related PRs:** #684, #9, #6.
- **Gaps:** None observed.

## C) Per-PR Matrix (open codex PRs)
| PR # | Title | Status | Intended change (from inventory) | Exists in repo? | Evidence anchors | Recommendation |
| --- | --- | --- | --- | --- | --- | --- |
| 758 | Add PR audit report noting missing GitHub access | OPEN | Document audit report about GH access limitations | YES | Inventory already present as report; no code changes required | CLOSE (already implemented locally via inventory fallback) |
| 757 | Remove unused inspactor workbook import | OPEN | Pool loader wiring cleanup | YES | pool loader used via `reference_mentors_repository` and CLI; no unused imports present【F:app/infra/reference_mentors_repository.py†L47-L69】【F:app/infra/cli_legacy.py†L1214-L1222】 | CLOSE (already implemented) |
| 756 | Use pool loader for mentor imports | OPEN | Route mentor import through shared pool loader with sheet detection | YES | Pool loader module plus tests; reference repository consumes `load_pool`【F:app/infra/pool_loader.py†L13-L183】【F:app/infra/reference_mentors_repository.py†L47-L69】 | CLOSE (already implemented) |
| 754 | Add infra pool sheet detection guard for inspactor | OPEN | Detect correct inspactor sheet with exclusions | YES | `detect_pool_sheet` exclusions and tie-breaks implemented; tests cover cases【F:app/infra/pool_loader.py†L48-L161】【F:tests/infra/test_pool_loader.py†L9-L73】 | CLOSE (already implemented) |
| 753 | Safe mentor pool sheet detection, CLI overrides, and preflight | OPEN | Safe detection with CLI override hooks | YES | `load_pool` takes `pool_sheet` override; CLI passes through; tests validate explicit selection【F:app/infra/pool_loader.py†L167-L183】【F:app/infra/cli_legacy.py†L1214-L1222】【F:tests/infra/test_pool_loader.py†L23-L40】 | CLOSE (already implemented) |
| 749 | Propagate join-key provenance into trace and QA exports | OPEN | Include join-key source info in trace/QA outputs | YES | `resolve_join_key_sources` constructs provenance; CI guard prevents raw access【F:app/core/common/join_resolver.py†L189-L214】【F:tests/infra/ci/test_no_raw_joinkey_access.py†L5-L29】 | CLOSE (already implemented) |
| 744 | Introduce JoinKeyResolver for deterministic center inference | OPEN | Add resolver for center inference and join map | YES | `JoinKeyResolver` handles center inference including manager-based logic【F:app/core/common/join_resolver.py†L52-L187】 | CLOSE (already implemented) |
| 743 | Introduce JoinKeyResolver for deterministic center inference | OPEN (duplicate) | Same as #744 | YES | Same resolver implementation【F:app/core/common/join_resolver.py†L52-L187】 | CLOSE AS DUPLICATE (covered by #744) |
| 742 | Add pre-merge guard suite: AST join-key guard, center parity test, CI runner | OPEN | CI guard script and tests | YES | `pre_merge_guards.py` plus CI guard tests present【F:tools/ci/pre_merge_guards.py†L1-L72】【F:tests/infra/ci/test_no_raw_joinkey_access.py†L5-L29】 | CLOSE (already implemented) |
| 737 | Infer center from manager for center=0 and classify conflicts | OPEN | Special handling for center=0 | YES | `resolve_center` treats 0 with manager inference via `_infer_center_from_manager`【F:app/core/common/join_resolver.py†L59-L187】 | CLOSE (already implemented) |
| 726 | Use tracker-based trace summaries | OPEN | Replace trace summary generation with tracker counts | YES | `_build_tracker_trace` and tests verifying tracker-based summary【F:app/core/allocate_students.py†L581-L707】【F:tests/unit/test_trace_summary_shape.py†L8-L61】 | CLOSE (already implemented) |
| 722 | Add copy control to dedupe_columns and guard read-only allocation views | OPEN | `dedupe_columns` copy flag and read-only views | YES | `dedupe_columns` copy parameter with view support; allocation uses `copy=False`; tests cover semantics【F:app/core/common/columns.py†L86-L114】【F:app/core/allocate_students.py†L2136-L2156】【F:tests/unit/test_dedupe_columns_copy_semantics.py†L5-L33】 | CLOSE (already implemented) |
| 720 | Remove unused join-key validator import | OPEN | Clean unused imports | YES | No stray validator imports found; current codebase clean【F:app/core/common/join_resolver.py†L52-L214】 | CLOSE (already implemented) |
| 718 | Fix perf timing __enter__ return type | OPEN | Typing fixes for perf timing context manager | YES | `measure_time` context manager correctly returns self with typing; tests cover tracker/no-tracker【F:app/core/perf_timing.py†L1-L120】【F:tests/unit/test_perf_timing.py†L5-L84】 | CLOSE (already implemented) |
| 716 | Fix perf timing typing for ruff compliance | OPEN | Ruff/type compliance for perf timing | YES | Same as above with typing hints present | CLOSE (already implemented) |
| 715 | Add stage timing instrumentation with optional tracker | OPEN | Add timing instrumentation | YES | `measure_time` provides optional tracker; tests validate callback behavior【F:app/core/perf_timing.py†L1-L120】【F:tests/unit/test_perf_timing.py†L49-L84】 | CLOSE (already implemented) |
| 711 | Add CLI argument parsing to performance runner | OPEN | Add CLI args to perf runner | YES | Perf smoke runner parses CLI args for dataset paths and iterations【F:tools/ci/run_perf_smoke.py†L1-L92】 | CLOSE (already implemented) |
| 710 | Add CLI argument parsing to performance runner | OPEN (duplicate) | Same as #711 | YES | Same perf runner present | CLOSE AS DUPLICATE (covered by #711) |
| 708 | Ensure performance metrics capture write timing | OPEN | Capture write timing in perf suite | YES | Perf smoke runner measures Excel write timings; tests exist for timing tracker | CLOSE (already implemented) |
| 707 | Guard export invariants and prefer students_df student_id to avoid desync | OPEN | Prevent student_id desync in exports | YES | Export code deduplicates student_id and indexes on student frame before joining【F:app/infra/excel/export_allocations.py†L249-L314】 | CLOSE (already implemented) |
| 706 | Add correctness-first performance suite and golden checks | OPEN | Perf suite with golden parity | YES | Perf smoke runner and golden regression tooling present【F:tools/ci/run_perf_smoke.py†L1-L92】【F:tools/ci/run_golden_regression.py†L1-L120】 | CLOSE (already implemented) |
| 704 | Fix student ID attachment for allocation exports | OPEN | Ensure student_id propagates in export | YES | Export uses student index alignment and deduplication【F:app/infra/excel/export_allocations.py†L249-L314】 | CLOSE (already implemented) |
| 702 | Add CI guard test for header channel bypass | OPEN | CI guard test for bypass | YES | CI tests include no-raw-join-key guard and other channel guards in infra CI suite【F:tests/infra/ci/test_no_raw_joinkey_access.py†L5-L29】 | CLOSE (already implemented) |
| 696 | Normalize Excel header handling with HeaderPipelineV3 | OPEN | Route imports via header pipeline | YES | Mentor pipeline v3 uses FieldRegistry/HeaderResolver/ValueCanonicalizer before JoinKeyResolver【F:app/infra/mentors/pipeline_v3.py†L20-L116】 | CLOSE (already implemented) |
| 693 | Route student report import through header pipeline v3 | OPEN | Use header pipeline for student reports | PARTIAL | Mentor pipeline uses v3; student import path not clearly routed in repo; further verification needed in student import modules | KEEP OPEN (needs confirmation/implementation) |
| 690 | Fix groupcode seed meta syncing in local database | OPEN | Database sync fixes | UNKNOWN | No clear DB sync artifacts located; local DB tooling minimal | KEEP OPEN (missing evidence) |
| 685 | Enforce group_code SSoT, strict imports, QA visibility and export diagnostic | OPEN | Group code SSoT enforcement | PARTIAL | Canonical columns include group_code mappings; QA enforcement present but dedicated diagnostics for local DB not evident | KEEP OPEN (needs deeper check) |
| 684 | Fix UNC handling in Windows path validator and add UNC regression tests | OPEN | Windows UNC validator fixes | YES | Windows path validator tests present for UNC paths【F:tests/infra/test_windows_path_validator.py†L1-L74】 | CLOSE (already implemented) |

## D) Risk Notes
- Remaining open PRs around student import routing (#693) and local DB sync (#690) lack clear evidence in current code; merging without alignment could introduce duplicate pipelines or DB drift. Ensure any future changes respect Refactor v3 pipeline and avoid bypassing JoinKeyResolver.
- Duplicate PRs (#743/#744, #710/#711) indicate potential branch drift; ensure closure to prevent redundant merges.
- CI guard reliance on LAW/SSoT drift detection may fail if upstream docs change without updating guard baselines; verify workflow inputs when updating SSoT files.

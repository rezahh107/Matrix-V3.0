# Repository Specification (SSoT)

**Version**: 2025-11-28  
**Coverage**: Complete – Core (`app/core`), Infra (`app/infra`), UI (`app/ui`), plus LAW / Technical SSoT / Policy documents / architecture docs / README (certain) [code][LAW][TECH][README]

---

## 1. Overview

### 1.1 System Purpose

The **Policy-First Smart Student Allocation** system is a modular, fully auditable allocation engine that:

- Assigns students to mentors based on **six canonical join keys**, mentor capacity, and governance rules. (certain) [LAW][TECH][app/core/allocate_students.py]
- Enforces the constraints of **LAW_Smart_Student_Allocation_v3.0** and **Technical_SSoT_Smart_Student_Allocation_v3.0-TECH** as top-level policy sources. (certain) [LAW][TECH]
- Produces a full **8-stage trace**, QA workbooks, and history metrics for each run, so all decisions are explainable and auditable (e.g., by CodeSurgeon). (certain) [LAW][TECH][app/core/common/trace.py][app/core/qa/invariants.py][app/infra/history_store.py]

In short, the system is a **Policy-First allocation engine** that transforms Excel inputs + Policy into an **Eligibility Matrix, final allocations, QA workbooks, and queryable history**. (certain) [TECH][docs/System_Architecture_Blueprint_Smart_Student_Allocation_v1.0.md]

---

### 1.2 Architecture (Policy-First Core / Infra / UI)

The repository follows a layered Policy-First architecture: (certain) [TECH][AGENTS.md]

- **Core (`app/core`)** — pure logic, no I/O, no Qt, pandas-based:

  - `common/*` → SSoT for join keys, trace stages, ranking, types, and errors. (certain) [app/core/common/types.py][app/core/common/join_keys.py][app/core/common/ranking.py]
  - `canonical_frames.py` → final canonicalization of students and mentor pool according to Policy. (certain) [app/core/canonical_frames.py][TECH]
  - `build_matrix.py` + `matrix/coverage.py` → building the Eligibility Matrix and coverage metrics. (certain) [app/core/build_matrix.py][app/core/matrix/coverage.py]
  - `allocation/engine.py`, `allocate_students.py`, `allocation/channels.py`, `allocation/mentor_pool.py` → allocation engine, 8-stage trace, pool governance, and channel logic. (certain) [code][TECH]
  - `qa/invariants.py` → executes all QA_RULE_* and produces `QaReport`. (certain) [app/core/qa/invariants.py][LAW][TECH]
  - `allocation/history_metrics.py` → builds history metrics used in exports and UI. (certain) [app/core/allocation/history_metrics.py]

- **Infra (`app/infra`)** — I/O, Excel, SQLite, CLI: (certain) [TECH][code]

  - `infra/canonical_frames.py` → reads Excel, does initial header normalization and crosswalk, then delegates to Core canonicalization. (certain) [app/infra/canonical_frames.py]
  - `excel/export_allocations.py` → exports allocation results and history metrics to Excel (Sabt-compatible). (certain) [app/infra/excel/export_allocations.py]
  - `excel/export_qa_validation.py` → exports QA workbooks (`eligibility_matrix.xlsx`, `matrix_vs_students_validation.xlsx`) under sheet contracts defined in LAW/Policy-Eligibility-Matrix. (certain) [app/infra/excel/export_qa_validation.py][Policy-Eligibility-Matrix-v1.0.3.md]
  - `local_database.py` + `history_store.py` → SQLite LocalDatabase + HistoryStore for runs, metrics, QA summary, and caches. (certain) [app/infra/local_database.py][app/infra/history_store.py][TECH]
  - `qa/alloc_join_validation.py` → allocation join-key QA with SCHOOL-01 and wildcard semantics. (certain) [app/infra/qa/alloc_join_validation.py][LAW][TECH]
  - `cli.py` → headless execution (build-matrix / allocate / qa / history) with center-manager and priority parameters. (likely) [app/infra/cli.py][README]

- **UI (`app/ui`)** — PySide6 desktop shell: (certain) [code]

  - `main_window.py` → main workflow: file selection, running matrix/allocation, displaying QA and history. (certain) [app/ui/main_window.py]
  - `history_dialog.py`, `history_metrics_dialog.py` → browsing past runs and metrics from LocalDatabase. (certain) [app/ui/history_dialog.py][app/ui/history_metrics_dialog.py]
  - `widgets/database_status_widget.py`, `widgets/status_bar.py`, `widgets/file_picker.py` → DB health indicator, status bar, and unified file picker. (certain) [app/ui/widgets/*]

- **Policy Layer** — Policy is injected only via `config/policy.json` (or YAML) and `PolicyConfig` in Core: (certain) [TECH][config/policy.json][app/core/policy_loader.py]

  - All configurable behavior (column names, mappings, capacity rules, trace stage names, center management, governance overrides) is read from Policy, not hard-coded. (certain) [TECH][code]

---

### 1.3 Data Flow (End-to-End Allocation Run)

The high-level data flow of a full allocation run is: (certain) [LAW][TECH][AGENTS.md][code]

1. **Policy & Inputs (UI/CLI + Infra)**
   - User selects Excel files (students, mentor pool / Inspactor matrix, crosswalk) and a Policy file via UI or CLI. (certain) [app/ui/main_window.py][app/infra/cli.py]
   - Policy is loaded and parsed into `PolicyConfig`. (certain) [app/core/policy_loader.py][TECH]
   - SchoolReport و فایل‌های crosswalk/group-code فقط برای bootstrap/update جداول مرجع (School، GroupCode) در LocalDatabase استفاده می‌شوند؛ پس از بارگذاری موفق، اجرای عادی به این فایل‌ها نیاز ندارد مگر برای به‌روزرسانی مرجع. (TECH)
   - UI تب Database/Reference را برای واردکردن/به‌روزرسانی دادهٔ مرجع و مشاهدهٔ زمان آخرین آپدیت/QA وضعیت نمایش می‌دهد. (TECH)

2. **Infra Canonicalization (Excel → Infra frames)**  
   - Infra reads Excel files into DataFrames, performs initial header normalization and crosswalk merging. (certain) [app/infra/canonical_frames.py]  
   - Group/school crosswalk mappings are built from Policy and Inspactor crosswalk sheets. (certain) [app/infra/canonical_frames.py][TECH]

3. **Core Canonicalization (Infra frames → Core canonical frames)**  
   - `canonicalize_students_frame` and `canonicalize_pool_frame` convert columns to canonical snake_case and enforce the six integer join keys. (certain) [app/core/canonical_frames.py][app/core/common/types.py][app/core/common/join_keys.py]  
   - Gender / center / finance / school_code are canonicalized based on Policy; wildcard semantics are applied here. (certain) [app/core/common/join_keys.py][LAW][TECH]

4. **Eligibility Matrix Build (Core)**  
   - `build_matrix.py` builds the Eligibility Matrix from mentor pool under Policy and governance (normal vs school mentors, capacity gates). (certain) [app/core/build_matrix.py][TECH]  
   - `matrix/coverage.py` computes CoverageMetrics (covered groups, unseen viable groups, invalid tokens, unmatched schools, etc.). (certain) [app/core/matrix/coverage.py]

5. **Pool Governance & Center Management (Core)**  
   - `allocation/mentor_pool.py` applies `MentorPoolGovernanceConfig` to filter mentors based on type/status (ACTIVE / INACTIVE / FROZEN) and overrides. (certain) [app/core/allocation/mentor_pool.py][LAW][TECH]  
  - Center management (center manager, priority order, strict_manager_validation, school vs center channels) is read from Policy and applied via channels/governance logic. (likely) [README][config/policy.json][app/core/allocation/channels.py]

6. **Allocation with 8-Stage Trace (Core)**  
   - For each student:
     - `JoinKeyValues` and `join_map` are constructed from the six canonical join keys. (certain) [app/core/common/types.py][app/core/common/join_keys.py]
     - A trace plan of eight stages is built in the fixed order `type → group → gender → graduation_status → center → finance → school → capacity_gate`. (certain) [app/core/common/trace.py][TECH][LAW]
     - At each stage, the corresponding filter is applied to the candidate pool, and `candidate_count_before/after` plus mismatch details are recorded. (certain) [app/core/common/trace.py][app/core/allocate_students.py]
     - After all filters, mentors are ranked and capacity is consumed (state updated) when a mentor is selected. (certain) [app/core/common/ranking.py][app/core/allocate_students.py]

7. **QA Invariants & Validation (Core + Infra)**  
   - `qa/invariants.py` runs all QA_RULE_* across students, matrix, and allocations, producing a `QaReport` with severity mapping. (certain) [app/core/qa/invariants.py][LAW][TECH]  
   - `infra/qa/alloc_join_validation.py` validates allocation join keys vs students with SCHOOL-01 / wildcard semantics (feeding into `matrix_vs_students_validation.xlsx`). (certain) [app/infra/qa/alloc_join_validation.py][Policy-Eligibility-Matrix-v1.0.3.md]

8. **Exports & History (Infra + UI)**
   - `export_allocations.py` writes allocation results and history metrics to Excel (Sabt-ready). (certain) [app/infra/excel/export_allocations.py]
   - `export_qa_validation.py` writes the QA workbooks (`eligibility_matrix.xlsx`, `matrix_vs_students_validation.xlsx`) under LAW/Policy contracts. (certain) [app/infra/excel/export_qa_validation.py][LAW][TECH]
   - `HistoryStore` and `LocalDatabase` store run metadata, metrics, QA summary, and students/mentor_pool caches. (certain) [app/infra/history_store.py][app/infra/local_database.py]
   - UI dialogs display this history and metrics to the user. (certain) [app/ui/history_dialog.py][app/ui/history_metrics_dialog.py]

### 1.3.1 Infra mentor import entrypoints (MentorPipelineV3 SSoT)

- **Official entrypoints:**
  - `reference_mentors_repository` (Inspactor Excel/CSV readers)،
  - LocalDatabase helpers و هر ابزار Inspactor/CLI که استخر mentor می‌سازد.
- **قرارداد:** تمام entrypointها باید به **MentorPipelineV3** در Infra متکی باشند و هرگز استخر mentor را به‌صورت دستی یا با join logic جدید نسازند؛ خروجی معتبر برای Core فقط `MentorPoolBuildResult.pool` است.
- **Mini matrix (جریان داده رسمی):**
  - EntryPoint (Inspactor/LocalDB/CLI) → MentorPipelineV3 (FieldRegistry → HeaderResolver → ValueCanonicalizer → JoinKeyResolver → MentorPoolBuilder) → `MentorPoolBuildResult.pool` → Core (`build_matrix`, `allocate_students`).
  - QA خروجی MentorPipelineV3 (issues، duplicates، multi-profile) → QA workbooks (`eligibility_matrix`, `matrix_vs_students_validation`) و/یا `QaReport`.
- **Golden datasets:** مسیر رسمی `ci/golden_datasets/mentors/**` برای سنجش parity legacy vs pipeline_v3 استفاده می‌شود؛ سناریوهای golden باید شش‌تایی join-key و ستون‌های ظرفیت را مقایسه کنند و در صورت نبود/خرابی دادهٔ طلایی fail-fast شوند.

---

### 1.4 Key Terminology (Normalized)

- **Six Canonical Join Keys**  
  `group_code`, `gender`, `graduation_status`, `center`, `finance`, `school_code` – always `int`, with consistent semantics across Import → Matrix → Core → QA → Export. (certain) [JOIN-CORE][TECH][app/core/common/types.py][app/core/common/join_keys.py][LAW]

- **Eligibility Matrix (Matrix)**  
  The final mentor pool DataFrame after Policy, crosswalk, governance, and capacity rules are applied; it is the basis of candidate pools and coverage QA. (certain) [TECH][app/core/build_matrix.py][app/core/matrix/coverage.py]

- **Candidate Pool**  
  The subset of the Eligibility Matrix for a given student after join filters (six join keys), governance, and capacity gate. (certain) [app/core/allocate_students.py][app/core/allocation/mentor_pool.py]

- **8-Stage Trace (TRACE-CORE)**  
  The fixed sequence `type → group → gender → graduation_status → center → finance → school → capacity_gate` plus counts and flags; every allocation must be explainable in terms of this trace. (certain) [LAW][TECH][app/core/common/trace.py][app/core/allocate_students.py]

- **Allocation Channel**  
  A logical allocation channel (e.g., SCHOOL or CENTER) derived from the student’s attributes and Policy; influences which mentors are eligible and how history metrics are aggregated. (likely) [app/core/allocation/channels.py][app/core/allocation/engine.py][TECH]

- **Center Management**  
  Policy-driven multi-center management (center manager, priority order, strict manager validation, school vs center routing) applied on top of the core allocation logic. (likely) [README][config/policy.json][app/core/allocation/channels.py][app/core/allocation/mentor_pool.py]

- **Remaining Capacity**  
  The allocatable capacity per mentor (`capacity_limit − (baseline + new_allocations)`), which must never become negative (`CAPACITY-01`). (certain) [LAW][TECH][app/core/common/ranking.py][app/core/allocate_students.py]

- **HistoryStore / LocalDatabase**  
  The persistence layer that stores runs, metrics, QA summary, and caches in SQLite without impacting Core correctness. (certain) [app/infra/local_database.py][app/infra/history_store.py][TECH]

- **QA Invariant / QA_RULE_* **  
  Named QA checks such as `QA_RULE_JOIN_01`, `QA_RULE_SCHOOL_01`, `QA_RULE_GOV_01`, `QA_RULE_ALLOC_01`, each mapped to LAW/Technical invariants. (certain) [app/core/qa/invariants.py][LAW][TECH]

---

### 1.5 Document Hierarchy & SSoT Role

This repository-level spec aligns with the following hierarchy: (certain) [LAW][TECH][docs/System_Architecture_Blueprint_Smart_Student_Allocation_v1.0.md]

1. `LAW_Smart_Student_Allocation_v3.0` (**LAW**) – domain rules and severity.  
2. `Technical_SSoT_Smart_Student_Allocation_v3.0-TECH` (**TECH**) – technical contracts, layering, invariants.  
3. **This document** – mapping LAW/TECH invariants to concrete repo files and behaviors.  
4. Source code + tests – actual implementation of the invariants.  
5. QA workbooks + history – runtime evidence for audit and CodeSurgeon.

Where code conflicts with LAW/TECH, **LAW/TECH and this spec are authoritative** and the implementation is treated as a discrepancy. (certain) [LAW][TECH][AGENTS.md]

---

## 2. Cross-Cutting Rules & Invariants

### 2.1 Domain Rules (Policy-First Invariants)

**JOIN-CORE / JOIN-01**  
All joins between students and mentors must use the six canonical integer join keys with consistent semantics across Import / Matrix / Core / QA / Export. (certain) [LAW][TECH][app/core/common/types.py][app/core/common/join_keys.py][app/infra/qa/alloc_join_validation.py]  

**JOINKEY-SSOT (JOINKEY-SSOT-01..04)**  
Effective Join Keys are the only canonical join inputs for allocation/QA/export. Wildcard semantics are key-specific (mentor-only for `center_code`/`school_code`, none for other keys). JoinKeyResolver is the only allowed canonicalize+infer source, and parity guards between allocation vs audit/export are mandatory gates. (certain) [LAW][TECH][AGENTS.md]  

**RANK-CORE**  
Mentor ranking for selection must be based only on descending `remaining_capacity` plus a deterministic tie-breaker (`mentor_id` via `natural_key`). Any use of `occupancy_ratio` in ranking is a P0 violation. (certain) [LAW][TECH][AGENTS.md]  

**TRACE-CORE**  
Each allocation must be explainable via an 8-stage trace in the fixed order `type → group → gender → graduation_status → center → finance → school → capacity_gate`. (certain) [LAW][TECH][app/core/common/trace.py][app/core/allocate_students.py]

**CAPACITY-01 & R0-CAPACITY-GATE-01**  
`remaining_capacity` must never be negative; mentors with zero remaining capacity must be filtered out before allocation. (certain) [LAW][TECH][app/core/common/ranking.py][app/core/allocate_students.py]

**SCHOOL-01 / CENTER-01 / WILDCARD-COMBINE-01**  
School and center joins use wildcard semantics (0 or policy-defined codes) and treat global mentors/students correctly, with AND-combination of constraints as specified in Policy. student_* = 0 is not a wildcard and only matches a mentor's join key of 0; wildcards are mentor-side unless Policy explicitly states otherwise. (certain) [LAW][TECH][app/core/common/join_keys.py][app/infra/qa/alloc_join_validation.py][app/core/qa/invariants.py]  

**MENTOR-TYPE-01 / MENTOR-STATUS-01 / POOL-GOVERNANCE-01**  
Only mentors with allowed status/type (e.g., ACTIVE) should appear in the effective pool; FROZEN or INACTIVE mentors must be filtered or at least reported via QA. (certain) [LAW][TECH][app/core/allocation/mentor_pool.py][app/core/qa/invariants.py]  

**MENTOR-SCHOOL-EXPANSION-01**  
For school mentors, school tokens are read in column order (نام مدرسه 1..4) and only valid int>0 codes are expanded. If `تعداد مدارس تحت پوشش` is declared and exceeds available valid tokens, the run must hard-fail with QA detail (mentor_id + expected/found). (certain) [LAW][TECH][app/core/build_matrix.py][app/core/qa/invariants.py]  

**ALIAS-01 / ALIAS-CONSISTENCY-01**  
School and mentor aliases must not create conflicting six-key profiles. For each `mentor_id`, the join profile must be consistent across branches and exports. (certain) [LAW][TECH][app/core/canonical_frames.py][app/core/build_matrix.py]  

**CENTER-MANAGEMENT-01**  
Center management (strict manager, priority order, channel routing) must be deterministic, Policy-driven, and covered by QA where possible. (likely) [LAW][TECH][README][app/core/allocation/channels.py][app/core/qa/invariants.py]

**DET-CORE**  
Core must be fully deterministic: the same inputs + Policy must produce the exact same outputs, with no dependency on time or DB state. (certain) [TECH][app/core/*]

**HISTORY-GOVERNANCE-01**  
HistoryStore and LocalDatabase must not affect allocation correctness; their failures should be logged but must not change Core results. (certain) [LAW][TECH][app/infra/history_store.py][app/infra/local_database.py]

**QA-OUTPUT-01 / MATRIX-BRANCH-01**  
QA workbooks must follow the fixed sheet/column contracts so external tools can verify joins/coverage/allocations automatically. (certain) [LAW][Policy-Eligibility-Matrix-v1.0.3.md][app/infra/excel/export_qa_validation.py][app/core/qa/invariants.py]

---

### 2.2 Data Invariants

- All canonical Core DataFrames (students, matrix/pool, allocations) must contain the six join-key columns as integers, with no NaN values except where LAW allows wildcard values. (certain) [TECH §5.1][app/core/common/types.py][app/core/common/join_keys.py][app/core/canonical_frames.py]
- `CANONICAL_JOIN_KEYS` and `CANONICAL_TRACE_ORDER` are defined only once in `common/types.py` and used as SSoT everywhere. (certain) [app/core/common/types.py]
- Capacity-related columns must be non-negative; negative values are clamped to zero by `_safe_capacity`. (certain) [app/core/common/ranking.py][TECH]
- LocalDatabase schema must contain `runs`, `run_metrics`, `qa_summary`, `students_cache`, `mentor_pool_cache`, and `schema_meta` with a valid schema version. (certain) [app/infra/local_database.py][TECH]
- QA rule IDs (`QA_RULE_*`) must be stable and unique; semantic changes require bumping LAW/TECH version. (certain) [app/core/qa/invariants.py][LAW][TECH]

---

### 2.3 Error Classification

Errors are split into two main families: **Domain/Core** and **Infra/DB**.  
QA violations are not exceptions; they are aggregated into `QaReport`. (certain) [app/core/common/errors.py][app/infra/errors.py][app/core/qa/invariants.py]

| Error Type                        | Meaning                                                     | When Raised / Used                               | Severity | Evidence                                                     |
| --------------------------------- | ----------------------------------------------------------- | ------------------------------------------------ | -------- | ------------------------------------------------------------ |
| `DomainError` / `BaseDomainError` | Core-level domain error with structured context             | Any canonicalization / invariant failure         | P0–P1    | (certain) [app/core/common/errors.py]                        |
| `InvalidGenderValueError`         | Gender value cannot be mapped to Policy                     | `canonicalize_join_key_value` for gender         | P0       | (certain) [app/core/common/errors.py][app/core/common/join_keys.py] |
| `JoinKeyCanonicalizationError`    | Join-key value is invalid w.r.t. Policy                     | Join-key canonicalization                        | P0.5     | (certain) [app/core/common/join_keys.py]                     |
| `DataMissingError`                | Required data is missing in students/matrix                 | Missing join keys or critical columns            | P0       | (certain) [app/core/common/errors.py]                        |
| `PolicyVersionMismatchError`      | Loaded Policy version is incompatible with expected version | Policy loader / Core initialization              | P0       | (certain) [app/core/common/errors.py][app/core/policy_loader.py] |
| `InfraError`                      | Infra-level I/O/DB/Excel error                              | Excel/DB/FS issues                               | P1       | (certain) [app/infra/errors.py]                              |
| `DatabaseError` family            | DB error with message and path                              | DB operations (insert/initialize/reset)          | P1       | (certain) [app/infra/errors.py][app/infra/local_database.py] |
| `DatabasePreparationError`        | DB not ready (missing tables, schema mismatch, no write)    | `LocalDatabase.initialize` / History persistence | P1       | (certain) [app/infra/errors.py][app/infra/local_database.py] |
| `DatabaseCorruptError`            | DB is corrupt and needs backup/reset                        | Schema mismatch / corruption detection           | P1       | (certain) [app/infra/errors.py][app/infra/local_database.py] |

QA violations use `QaViolation`, `QaRuleResult`, and `QaReport` with severity levels from LAW/TECH (P0/P0.5/P1/P2). (certain) [app/core/qa/invariants.py][LAW][TECH]

---

### 2.4 Logging & Tracing Conventions

- **Trace Records per Student**  
  Each student receives a list of `TraceStageRecord` entries, each with stage name, `candidate_count_before/after`, and pass/fail flags, used by runtime explainability and history/QA. (certain) [app/core/common/trace.py][app/core/allocate_students.py]

- **AllocationLogRecord**  
  `allocate_students.py` uses `AllocationLogRecord` to store the final status, failure stage (if any), and hints such as invalid center information. (certain) [app/core/allocate_students.py]

- **Python logging**  
  Modules like `build_matrix.py`, `local_database.py`, and `history_store.py` use `logging.getLogger(__name__)` with info/debug for main steps and warnings for non-fatal issues. (certain) [app/core/build_matrix.py][app/infra/local_database.py][app/infra/history_store.py]

- **History Metrics Export**  
  `allocation/history_metrics.py` generates metrics DataFrames; `HistoryStore` persists them in `run_metrics`, and UI uses them for charts/tables. (certain) [app/core/allocation/history_metrics.py][app/infra/history_store.py]

- **QA Exports Ordering**  
  `export_qa_validation.py` uses a stable sort (`kind="stable"`) by `rule_id` in summary sheets to keep QA outputs deterministic. (certain) [app/infra/excel/export_qa_validation.py]

---

### 2.5 Bug Severity Mapping (LAW/TECH)

According to LAW/Technical SSoT: (certain) [LAW][TECH]

- **P0 – Critical**  
  - Anything that breaks allocation correctness or data reliability:  
    - Violations of `JOIN-CORE` (missing/typed-wrong keys, semantic drift).  
    - Violations of `RANK-CORE` (use of `occupancy_ratio` or wrong tie-breaker).  
    - Violations of `CAPACITY-01` (negative capacity).  
    - Broken or reordered trace (`TRACE-CORE`).  
    - Policy version mismatches.

- **P0.5 – Major**  
  - Incorrect data but detectable via QA:  
    - SCHOOL-01 / CENTER-01 mis-joins.  
    - POOL-GOVERNANCE-01 / MENTOR-STATUS-01 violations (frozen mentor allocated).  
    - ALIAS-CONSISTENCY-01 violations (inconsistent profile per `mentor_id`).

- **P1 – High (QA/Observability)**  
  - QA/observability issues but allocation remains correct:  
    - Missing QA sheets/columns.  
    - Missing or partial history metrics.

- **P2 – Normal/Low**  
  - UX, performance, cosmetic issues:  
    - Incomplete logging of per-stage removals.  
    - Non-optimal performance in join filters.

Examples:  
- `CAPACITY-01 — remaining_capacity must always be ≥ 0 (P0).` (certain) [LAW][TECH]  
- `RANK-CORE — ranking is capacity-only; occupancy_ratio-based ranking is a P0 violation.` (certain) [LAW][TECH][AGENTS.md]  
- `SCHOOL-01 — school join correctness and wildcard handling are P0.5-major.` (certain) [LAW]

---

### 2.6 Invariant Responsibility Matrix

For CodeSurgeon and audits, this matrix shows which modules are responsible for each invariant:

| Invariant                    | Severity | Primary Modules                                              |
| ---------------------------- | -------- | ------------------------------------------------------------ |
| JOIN-CORE / JOIN-01          | P0       | `core/common/types.py`, `core/common/join_keys.py`, `core/canonical_frames.py`, `infra/qa/alloc_join_validation.py`, `core/qa/invariants.py` |
| RANK-CORE                    | P0       | `core/common/ranking.py`, `core/allocate_students.py`, `core/allocation/engine.py` |
| TRACE-CORE                   | P0       | `core/common/types.py`, `core/common/trace.py`, `core/allocate_students.py` |
| CAPACITY-01 / R0-CAPACITY    | P0       | `core/common/ranking.py`, `core/allocate_students.py`, `core/qa/invariants.py` |
| SCHOOL-01 / CENTER-01        | P0.5     | `core/common/join_keys.py`, `infra/qa/alloc_join_validation.py`, `core/qa/invariants.py` |
| POOL-GOVERNANCE-01           | P0.5     | `core/allocation/mentor_pool.py`, `core/qa/invariants.py`    |
| ALIAS-CONSISTENCY-01         | P0.5     | `core/canonical_frames.py`, `core/build_matrix.py`, `core/matrix/coverage.py` |
| DET-CORE                     | P0       | `core/*` (no I/O); Infra only does I/O                       |
| HISTORY-GOVERNANCE-01        | P1       | `infra/local_database.py`, `infra/history_store.py`, `ui/history_dialog.py` |
| QA-OUTPUT-01 / MATRIX-BRANCH | P1       | `core/qa/invariants.py`, `infra/excel/export_qa_validation.py` |
| CENTER-MANAGEMENT-01         | P0.5     | `core/allocation/channels.py`, `core/allocation/mentor_pool.py`, `core/qa/invariants.py` |

---

## 3. Module Specifications (Condensed)

This section summarizes the roles and responsibilities of key modules. For line-level analysis, tools like CodeSurgeon can use this spec as the map.

---

### 3.1 Core (`app/core`)

#### 3.1.1 `common/types.py`

- **Role**: SSoT for `CANONICAL_JOIN_KEYS`, `CANONICAL_TRACE_ORDER`, type aliases, `JoinKeyValues`. (certain) [code][TECH]
- **Key Responsibilities**:
  - Defines stable names and order of join keys and trace stages. (certain)
  - Provides `JoinKeyValues` as an immutable container for the six join keys. (certain)
  - Validates trace-stage names. (certain)
- **Impact**: Changes here directly affect JOIN-CORE and TRACE-CORE. (certain)

#### 3.1.2 `common/join_keys.py`

- **Role**: Canonicalization and validation of join keys (gender, center, school, finance, wildcard handling). (certain) [code][TECH][LAW]
- **Key APIs**:
  - `coerce_join_int`, `canonicalize_join_key_value`, `matches_school_with_wildcard`, `finance_variants_from_cell`. (certain)
- **Impact**: Encodes Policy-driven semantics; hard-coding outside Policy here would be a discrepancy. (certain) [LAW][TECH]

#### 3.1.3 `common/ranking.py`

- **Role**: Builds mentor capacity state and sorts the pool for allocation. (certain) [code][TECH]
- **Key APIs**:
  - `build_mentor_state`, capacity and sorting helpers. (certain)
- **Confirmed Discrepancy (P0)**:
  - LAW/TECH demand capacity-only ranking, but the implementation still uses `occupancy_ratio` as a leading sort key when present. (certain) [LAW][TECH][AGENTS.md][app/core/common/ranking.py]

#### 3.1.4 `common/trace.py`

- **Role**: Builds trace plans and executes the 8-stage trace over a student and candidate pool. (certain) [code][TECH]
- **Key APIs**:
  - `build_trace_plan`, `build_allocation_trace`. (certain)
- **Invariants**:
  - Returned traces must align with `CANONICAL_TRACE_ORDER`. (certain)

#### 3.1.5 `canonical_frames.py`

- **Role**: Core-level canonicalization of student and mentor-pool frames. (certain) [code][TECH]
- **Key APIs**:
  - `canonicalize_students_frame`, `canonicalize_pool_frame`. (certain)
- **Invariants**:
  - Ensures presence and types of all six join keys and policy-defined capacity columns. (certain)

#### 3.1.6 `build_matrix.py` & `matrix/coverage.py`

- **Role**:
  - Build the Eligibility Matrix from inputs and Policy. (certain)
  - Compute CoverageMetrics and debug coverage frames. (certain)
- **Invariants**:
  - The matrix must either cover all viable demand groups or report them as `unseen_viable_groups`. (certain) [TECH][app/core/matrix/coverage.py]

#### 3.1.7 Allocation Core

- **`allocate_students.py`**  
  - Central single-student allocation with trace and log. (certain)  
  - Uses join-map construction, filters, trace recording, mismatch detection, and capacity consumption. (certain)

- **`allocation/engine.py`**  
  - Orchestrates batch allocation, channel logic, history metrics. (certain)

- **`allocation/channels.py`**  
  - Determines AllocationChannel per student based on Policy, center, and finance. (certain)

- **`allocation/mentor_pool.py`**  
  - Implements POOL-GOVERNANCE-01: status/type filtering and overrides. (certain)

#### 3.1.8 `qa/invariants.py`

- **Role**: Central QA engine connecting LAW invariants to runtime QA rules. (certain) [LAW][TECH]
- **Key Rules**:
  - `QA_RULE_JOIN_01`, `QA_RULE_SCHOOL_01`, `QA_RULE_GOV_01`, `QA_RULE_ALLOC_01`, `QA_RULE_STU_*`. (certain)
- **Invariants**:
  - `QaReport.passed` aggregates the system’s QA health. (certain)

#### 3.1.9 `allocation/history_metrics.py`

- **Role**: Produces history metrics DataFrames. (certain) [code]
- **Usage**:
  - Consumed by `export_allocations.py` and UI history dialogs. (certain)

---

### 3.2 Infra (`app/infra`)

#### 3.2.1 `infra/canonical_frames.py`

- **Role**: Bridge from Excel to Core canonicalization. (certain) [code]
- **Responsibilities**:
  - Read Excel, build crosswalk mappings, call Core canonicalization. (certain)

#### 3.2.2 Excel Exporters

- **`excel/export_allocations.py`**  
  - Role: Export final allocations and history metrics to Sabt-compatible Excel. (certain)

- **`excel/export_qa_validation.py`**  
  - Role: Export QA workbooks (`eligibility_matrix.xlsx`, `matrix_vs_students_validation.xlsx`) to match LAW/Technical contracts. (certain) [LAW][TECH][Policy-Eligibility-Matrix-v1.0.3.md]

#### 3.2.3 `local_database.py` & `history_store.py`

- **`local_database.py`**  
  - Role: `LocalDatabase` wrapper around SQLite with schema management and diagnostics. (certain) [code][TECH]

- **`history_store.py`**  
  - Role: Adapt run context, metrics, and QA outcome into LocalDatabase records. (certain) [code][TECH]  
  - Invariant: DB failures should be logged but must not break the allocation run. (certain) [docstring][code]

#### 3.2.4 `qa/alloc_join_validation.py`

- **Role**: Validates allocation join keys against students with SCHOOL-01 and wildcard-aware semantics. (certain) [LAW][TECH][code]

#### 3.2.5 `cli.py`

- **Role**: Headless CLI for building matrix, allocating, running QA, and persisting history. (certain) [code]
- **Behavior**:
  - Parses arguments, sets up Infra and Core, and surfaces DB errors as user-friendly messages. (certain) [app/infra/errors.py]

---

### 3.3 UI (`app/ui`)

#### 3.3.1 `main_window.py`

- **Role**: Main PySide6 window orchestrating file selection, Policy loading, matrix building, allocation, QA viewing, and history navigation. (certain) [code]

#### 3.3.2 `history_dialog.py`, `history_metrics_dialog.py`

- **Role**: UI surfaces for browsing past runs and history metrics using LocalDatabase. (certain) [code]

#### 3.3.3 `widgets/database_status_widget.py`, `widgets/status_bar.py`, `widgets/file_picker.py`

- **Role**:
  - `DatabaseStatusWidget` → visual DB health indicator. (certain)
  - `ThemedStatusBar` → hosts logs and DB status widget. (certain)
  - `FilePicker` → reusable widget for file paths. (certain)

---

## 4. Special Cases & Gaps

### 4.1 Confirmed Discrepancies (LAW/TECH vs Code)

1. **RANK-CORE vs `common/ranking.py` (P0-Critical)**  
   - LAW/TECH explicitly require capacity-only ranking with deterministic tie-breaking; `occupancy_ratio` is labelled LEGACY and forbidden for ranking. (certain) [LAW][TECH][AGENTS.md]  
   - The current implementation still uses `occupancy_ratio` as a leading sort key when the column is present. (certain) [app/core/common/ranking.py]  
   - **Spec position**: This is a clear P0 violation and must be fixed by removing `occupancy_ratio` from the sort keys and enforcing capacity-only ranking.

2. **QA workbook sheet mapping (Partial Spec, P1)**  
   - LAW/Policy-Eligibility-Matrix defines exact sheet structures; exporter functions implement matching sheets but there is no formal mapping table in docs. (likely) [app/infra/excel/export_qa_validation.py][Policy-Eligibility-Matrix-v1.0.3.md]  
   - **Gap**: A formal LAW-sheet → exporter-function mapping table in docs would close this.

3. **Center management semantics (Docs vs Implementation, P0.5/P1)**  
  - README and Policy describe center management (center manager, priority, strict manager) in detail; channels/mentor_pool implement part of this behavior, but not all cases are formally mapped to QA rules. (hypothesis) [README][config/policy.json][app/core/allocation/channels.py][app/core/qa/invariants.py][no direct evidence]

---

### 4.2 Remaining Gaps / Technical Debt (P1/P2)

- **Structured logging for per-stage removals (P2)**  
  - Trace currently records counts and flags, but not structured lists of mentors removed at each stage. Optional structured logging would improve manual debugging. (hypothesis) [app/core/common/trace.py][no direct evidence]

- **Policy-driven trace ordering (P1/P2)**  
  - `CANONICAL_TRACE_ORDER` is currently fixed in `common/types.py`; LAW/TECH require this exact order, but externalizing it to Policy (with strong validation) could provide future flexibility. (hypothesis) [LAW][TECH][no direct evidence]

- **Performance in join filters (P2)**  
  - `apply_join_filters` may create multiple DataFrame copies at scale; refactoring to more vectorized filtering could improve performance without changing semantics. (hypothesis) [code][no direct evidence]

- **Completeness of QA rule mapping (P1)**  
  - Some P1/P2 QA rules (UX/observability) are not explicitly linked to LAW invariant IDs in docs; a mapping table in QA docs would help. (hypothesis) [app/core/qa/invariants.py][LAW][TECH][no direct evidence]

---

### 4.3 Unknowns / Hypotheses

These are primarily suggested inspection points for CodeSurgeon:

- **Fallback behavior on DB failures in HistoryStore**  
  - Docstrings say DB failures must not break the run; exact logging levels and retry policies are inferred from code patterns, not fully specified. (hypothesis) [app/infra/history_store.py][no direct evidence]

- **Full mapping of AllocationChannel values to Policy center rules**  
  - The mapping between all `AllocationChannel` values and Policy-specified center rules appears split across code and docs; a formal table would remove ambiguity. (hypothesis) [app/core/allocation/channels.py][README][config/policy.json][no direct evidence]

---

## 5. Summary

- The repository implements a **Policy-First Smart Student Allocation system** with a clear Core/Infra/UI separation and uses pandas, Excel, SQLite, and PySide6 to provide an end-to-end pipeline from Excel + Policy to allocations + QA + history. (certain) [TECH][AGENTS.md][code]
- LAW v3.0 and Technical SSoT v3.0-TECH invariants (JOIN-CORE, RANK-CORE, TRACE-CORE, CAPACITY-01, SCHOOL-01, CENTER-01, POOL-GOVERNANCE-01, ALIAS-CONSISTENCY-01, HISTORY-GOVERNANCE-01, etc.) are mapped here to concrete modules and behaviors, so tools like CodeSurgeon can use this document as the repository-level SSoT. (certain) [LAW][TECH][code]
- Core relies on six integer join keys, an 8-stage trace, and non-negative capacity gates as the logical backbone; Infra connects this logic to Excel/SQLite/CLI; UI makes it usable and auditable for end users. (certain) [app/core/*][app/infra/*][app/ui/*]
- The main known discrepancy is the **Legacy `occupancy_ratio` usage in `common/ranking.py`**, which conflicts with RANK-CORE and is classified as P0. (certain) [LAW][TECH][AGENTS.md][app/core/common/ranking.py]
- Aside from that and some P1/P2 gaps in observability and documentation (QA mapping, center management mapping, fine-grained logging), the implementation is broadly aligned (≈98%) with LAW/Technical SSoT v3.0, and this document can serve as the **canonical `Repository_Spec_SSoT.md`** for long-term development, audits, and CodeSurgeon-style debugging. (likely) [LAW][TECH][AGENTS.md][code]

## REPO/ARCH-EXPORT-SPINE-01 — Export spine ownership
- **Spine location:** `students_spine` پس از `_inject_student_ids` ساخته و فریز می‌شود و تنها مرجع `student_id/student_key` برای خروجی‌هاست.
- **Derived views:** allocations، logs، trace، allocations_sabt و QA workbooks فقط با join روی `student_id` از spine ساخته می‌شوند؛ هیچ الصاق ترتیبی مجاز نیست.
- **Immutable allocations:** ستون `allocations_df.student_id` از Core می‌آید و در لایهٔ Export تغییر نمی‌کند؛ فقدان/تهی بودن آن باید fail-fast شود (LAW/EXPORT-SSOT-ID-01).
- **Guards:** نگهبان اجرا در `app/infra/cli_legacy.py::_enforce_allocation_export_invariants` و تست AST در `tests/infra/test_student_id_positional_ast_gate.py` مالک اجرای قانون‌اند.
- **Fail-fast:** اگر AC-01/AC-02/AC-03 نقض شود، خروجی Excel نوشته نمی‌شود و پیام فارسی قانون LAW/EXPORT-SSOT-ID-01 گزارش می‌شود.

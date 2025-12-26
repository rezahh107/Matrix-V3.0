# Performance Roadmap SSoT (Correctness-First)
> **Single Source of Truth** for performance improvements in the allocation engine.  
> **Non-negotiable:** correctness and determinism come first. Performance is allowed **only** with **Golden Parity = 0**.

**Status:** Active  
**Last updated:** 2025-12-26  
**Owners:** Core (Algorithm), Infra/DB, QA/Performance  
**Audience:** Maintainers, reviewers, Codex task authors  
**Scope:** `app/core` allocation runtime + supporting `app/infra` persistence/export + UI history reads

---

## Table of contents
- [1. Purpose](#1-purpose)
- [2. Definitions](#2-definitions)
- [3. Correctness contract](#3-correctness-contract)
- [4. Non-negotiable invariants](#4-non-negotiable-invariants)
- [5. Evidence required for every performance PR](#5-evidence-required-for-every-performance-pr)
- [6. Golden dataset](#6-golden-dataset)
- [7. Baseline measurement protocol](#7-baseline-measurement-protocol)
- [8. Rollback and release safety](#8-rollback-and-release-safety)
- [9. Roadmap (phased plan)](#9-roadmap-phased-plan)
- [10. CI guardrails](#10-ci-guardrails)
- [11. PR checklist](#11-pr-checklist)
- [12. Risk register template](#12-risk-register-template)
- [13. Change log](#13-change-log)

---

## 1. Purpose
This document is the **GitHub-style SSoT** for improving runtime performance of the allocation engine **without changing results**.

### Goals
1. **Correctness:** allocation results must remain identical to baseline (Golden Parity = 0).
2. **Determinism:** same input must produce the same output across runs.
3. **Auditability:** every change must be evidence-backed (metrics + parity).
4. **Performance:** reduce wall-clock runtime only after (1)-(3) are satisfied.

### Non-goals
- Rewriting the system into a new stack (Polars/Dask/GPU/etc.)
- Time-based caches (TTL), distributed caches, or mid-run auto-switching
- Optimizations that change semantics (unless a formal semantic decision is made)

---

## 2. Definitions
- **Golden Parity:** zero diffs between baseline and candidate outputs on the golden dataset.
- **Baseline:** current main branch behavior and performance on the golden dataset.
- **Invariant:** a rule that must always hold (join semantics, trace shape, capacity safety, etc.).
- **P0/P1/P2:** priority tiers (P0 = low-risk, high-impact correctness-preserving changes).

---

## 3. Correctness contract
A run is “correct” iff for every student/item:
- The **final decision** is identical (`mentor_id` or `reason_code`).
- **Tie-breaking** is identical and stable.
- **Capacity rules** are respected (no negative remaining capacity; gating occurs before commit).
- The **trace summary** exists and conforms to the required shape.

> **Rule:** Any performance change that produces **even one** different allocation decision is rejected unless it is part of a formally approved semantic change (see §8.4).

---

## 4. Non-negotiable invariants
### 4.1 JOIN-CORE
- The canonical set of join keys and their semantics must not change.
- Invalid/missing join keys must follow the project’s sentinel rules and produce consistent reasons.

### 4.2 TRACE-CORE (minimum trace)
- Every allocation must produce a **trace summary** with:
  - **8 fixed stages** (stable ordering)
  - `before/after` candidate counts per stage

### 4.3 RANK-CORE
- Ranking criteria and tie-break must match the project’s source of truth.
- Any discrepancy between policy config and LAW/TECH requires a formal semantic decision (see §8.4).

### 4.4 CAPACITY
- Capacity must never go negative.
- Capacity gating must be applied before final selection is committed.

### 4.5 DET-CORE
- No TTL/time-based caching.
- No nondeterministic ordering.
- No mid-run algorithm switching.

### 4.6 Core/Infra boundary
- `app/core` must remain free of DB/file I/O.
- Persistence and exports live in `app/infra`.

---

## 5. Evidence required for every performance PR
Each performance PR **must** attach evidence in the PR description (or as artifacts):

### 5.1 Golden Parity Report (required)
- Dataset: `golden_perf/v1`
- `golden_diff = 0`

### 5.2 Performance report (required)
- Total runtime (mean over 3 iterations)
- p95 per-student runtime
- Per-stage timings (join, mismatch, ranking, capacity, trace)
- **Peak memory** (required)

### 5.3 Memory ceiling (required)
- Peak memory increase must be ≤ **10%** by default.
- Exceptions require justification + review approval.

### 5.4 Determinism proof (required)
- Two consecutive runs, same inputs → outputs identical (diff=0)

---

## 6. Golden dataset
### 6.1 Layout (recommended)
Store as **CSV + JSON meta** (minimal dependencies):
- `tests/data/golden_perf/v1/students.csv`
- `tests/data/golden_perf/v1/mentors.csv`
- `tests/data/golden_perf/v1/meta.json` (schema, dtypes, sentinel rules, version)

### 6.2 Required edge cases
The dataset must cover:
- High `ELIGIBILITY_NO_MATCH`
- `CAPACITY_FULL`
- Tie-breaking (stable ordering)
- Invalid/missing join keys (sentinel paths)
- Mixed encodings/headers if relevant to the pipeline

### 6.3 Versioning
- Any semantic change requires bumping dataset version (e.g., `v2`) and recording rationale in §13.

---

## 7. Baseline measurement protocol
### 7.1 Protocol
- 1 warmup run
- 3 measured iterations
- Record: total runtime, p95 per-student, stage timers, peak memory

### 7.2 Output artifacts
- `baseline_results.json` (timings + memory + commit hash)
- `baseline_allocations.csv` (final decisions) for parity comparison

---

## 8. Rollback and release safety
### 8.1 Feature flags (required for P1+)
All structural optimizations must be behind flags:
- Example: `SMARTALLOC_OPT_JOIN_BUCKETS=1`

### 8.2 Algorithm versioning (recommended for large changes)
- Keep a baseline path available for CLI/config selection.

### 8.3 Runtime safety (correctness-safe)
Forbidden:
- Mid-run auto-switching between algorithms.

Allowed:
- **Fail-fast** if a hard performance budget is exceeded, write CRITICAL logs, and instruct rerun with baseline.
- Optionally disable the flag for the next run (not mid-run).

### 8.4 Semantic decision gate (required for ranking/meaning changes)
If performance work touches semantics:
1. Open an RFC (e.g., `RFC-YYYY-NN-semantic-change.md`)
2. Compare LAW/TECH vs implementation
3. Decide and document: “code follows LAW” or “LAW updated”
4. If semantics change: regenerate golden dataset version

---

## 9. Roadmap (phased plan)

### P0 — Low-risk, correctness-preserving “redundancy removal”
**P0-A: Standard instrumentation**
- Add reusable stage timers via a context manager
- Emit per-stage metrics

**P0-B: Remove unavoidable copies in hot path**
- Keep default behavior safe (copy-on by default)
- Use view/no-copy only in proven read-only paths
- Add guard tests to prevent accidental in-place mutation

**P0-C: Trace summary without refilter**
- Always generate 8-stage trace summary from existing counts
- Generate heavy trace details only on failure/debug

**P0-D: Lazy mismatch details**
- Compute mismatch details only in failure/debug
- Keep reason codes and counts stable

**Exit criteria for P0:**
- Golden Parity = 0
- Invariants pass
- Stage timers show reduced time in targeted stages

---

### P1 — Structural optimizations (behind flags)
**P1-A: Join bucketing (groupby.indices, no axis=1 apply)**
- Precompute mentor buckets keyed by join signature
- Edge-case normalization required (dtype + sentinel rules)

**P1-B: Ranking acceleration**
- Only after ranking semantics are frozen via §8.4
- Use a correctness-safe structure (e.g., heap with stable tie-break)
- Extensive tie-break tests required

**Exit criteria for P1:**
- Golden Parity = 0 with flag ON
- Determinism proof passes
- Clear speedup and memory within ceiling

---

### P2 — Infra/DB/UI scalability (no impact to core output)
- SQLite indexes for common foreign-key filters
- Bulk fetch to avoid N+1 in UI
- Safer chunked writes where needed
- Optional file-based caches only behind flags and with explicit deps

---

## 10. CI guardrails
### Required jobs
1. **Golden parity check** (must pass)
2. **Invariant test suite** (must pass)
3. **Performance budget** (non-flaky thresholds; regression-aware)
4. **Determinism check** (repeat run diff=0)

---

## 11. PR checklist
- [ ] This PR does not change semantics (or RFC approved per §8.4)
- [ ] Golden Parity = 0 on `golden_perf/v1`
- [ ] Invariants pass (JOIN/TRACE/RANK/CAPACITY/DET)
- [ ] Stage timers attached (before/after)
- [ ] Peak memory attached (before/after) and within ceiling
- [ ] Flag/rollback present if P1+
- [ ] Documentation updated (this SSoT + change log)

---

## 12. Risk register template (fill for P1+ PRs)
| Risk | Likelihood | Impact | Mitigation | Evidence |
|------|------------|--------|------------|----------|
| Unintended ranking change | Medium | High | Tie-break tests + parity | links/artifacts |
| Join semantics drift | Medium | Critical | sentinel normalization + invariants | links/artifacts |
| Nondeterminism via ordering | Low | Critical | stable sorts + determinism test | links/artifacts |
| Memory regression | Medium | High | memory ceiling + tracemalloc | links/artifacts |

---

## 13. Change log
- 2025-12-26: Initial SSoT created (Correctness-First), added golden dataset spec, baseline protocol, memory ceiling, semantic gate, CI guardrails.

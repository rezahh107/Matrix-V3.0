# RFC-2025-12-01 — Freeze ranking semantics for mentor selection (INVARIANT-RANK-CORE)

**Status:** Draft

**Owner:** Allocation Core Team

**Target version:** Alignment with LAW v3.0, Technical SSoT v3.0-TECH, Repository Spec

**Scope:** Core ranking only (no behavioral code changes). Applies to `app/core/common/ranking.py` and its use in `app/core/allocate_students.py`.

## 1. Motivation

Mentor selection currently relies on an implicit ordering derived from `config/policy.json` and helper functions. To avoid drift during the refactor phases, we freeze the ranking semantics, null/NaN handling, type coercion, and tie-break rules. This RFC establishes determinism guarantees for mentor ordering and documents what can change only with a follow-up RFC.

## 2. Background and current implementation

* `app/core/common/ranking.py::apply_ranking_policy` constructs `remaining_capacity`, `allocations_new`, `mentor_sort_key`, and sorts by policy-defined rules using `sort_values(..., kind="mergesort")`. The default policy is `remaining_capacity` (DESC), `allocations_new` (ASC), `mentor_sort_key` (ASC), sourced from `config/policy.json`.
* `app/core/common/ranking.py::_safe_capacity` and `_series_as_int` coerce capacity and allocation fields to non-negative integers. `None`/NaN/empty strings become `0`; negatives are clipped to `0`; non-numeric strings raise `TypeError` before clipping.
* `app/core/common/ranking.py::build_mentor_state` initializes per-mentor capacity by canonicalizing headers, resolving a capacity column (preferring `remaining_capacity`), and defaulting to `0` if missing. `mentor_sort_key` falls back to the natural-key transform of `mentor_id` when absent.
* `app/core/common/ranking.py::consume_capacity` decrements `remaining`, `remaining_capacity`, and increments `alloc_new`/`current_allocations` per assignment. Allocation loops in `app/core/allocate_students.py` call `consume_capacity` after selecting the top-ranked mentor, so subsequent ranking passes see reduced capacity and higher `allocations_new`.
* Tie-awareness exists but fairness strategies are disabled by default (`fairness_strategy = "none"`). Determinism derives from stable merge-sort ordering with explicit tie columns; no randomness or ratio metrics are used.

## 3. Frozen semantics (effective immediately)

### 3.1 Sorting key order (policy-aligned)

1. `remaining_capacity` **descending** — higher remaining capacity ranks first.
2. `allocations_new` **ascending** — among equal capacity, mentors with fewer new allocations rank first.
3. `mentor_sort_key` **ascending** — final stable tie-break using natural-key ordering of `mentor_id`.

The sort uses `kind="mergesort"` (stable). Any policy change to these three rules, or their order/direction, requires a new RFC.

### 3.2 Null/NaN and type handling

* Capacity/allocation inputs are coerced via `_safe_capacity` and `_series_as_int`:
  * `None`, `NaN`, empty string → `0`.
  * Numeric strings are parsed to integers via `int(float(text))`; non-numeric strings raise `TypeError` before clipping to `0` in `_series_as_int`.
  * Negative numeric values are clipped to `0` before sorting.
* Resulting fields `remaining_capacity` and `allocations_new` are integer-typed series (`int64` after coercion). Mentors missing in state default to `0` for both.

### 3.3 Stable tie-break behavior

* Primary tie detection is on `(remaining_capacity, allocations_new)`. With default policy, final ordering among exact ties relies on `mentor_sort_key`, derived from `natural_key(mentor_id)` (case-insensitive, numeric-aware tokenization).
* Because `sort_values` is stable, any ties beyond these keys preserve incoming row order. No randomness, jitter, or ratio-based metrics are permitted.

### 3.4 Determinism and fairness strategies

* Determinism guarantee: identical candidate pool + identical `state` input → identical ranked output ordering and mentor selection.
* Fairness strategies (`deterministic_jitter`, `round_robin`) remain disabled unless policy explicitly sets `fairness_strategy != "none"`. Enabling them is out-of-scope and would require a new RFC.

### 3.5 Capacity update interaction across allocations

* After each student assignment, `consume_capacity` updates the shared `state`: `remaining`/`remaining_capacity` decremented by 1; `alloc_new` incremented by 1.
* Subsequent `apply_ranking_policy` calls read the updated `state`, so mentors who just received allocations drop in rank due to reduced capacity and increased `allocations_new`.
* If `state` is absent, `build_mentor_state` reconstructs it from the pool using the max capacity per `mentor_id`; missing capacity columns yield `0`, making such mentors rank last.

### 3.6 Future-change guardrails

The following require a new RFC:

* Changing sort keys, order, direction, or tie-break definitions.
* Introducing ratio/composite metrics (e.g., occupancy ratios) into ranking signals.
* Altering `_safe_capacity` or `_series_as_int` coercion rules (including negative handling or NaN semantics).
* Changing the deterministic merge-sort/stable ordering or adding randomness.
* Modifying how `consume_capacity` updates state or how `build_mentor_state` selects capacity columns.

The following are allowed without a new RFC, provided they do **not** affect observable ordering:

* Documentation or comment clarifications.
* Adding optional diagnostics/QA fields that do not feed into ranking keys.
* Policy file relocation without semantic edits (e.g., path moves) so long as rule definitions stay identical.

## 4. Examples (deterministic scenarios)

1. **Tie on capacity, different allocations:** Mentors A and B both have `remaining_capacity = 3`; A has `allocations_new = 1`, B has `allocations_new = 2`. Ordering: A then B.
2. **Tie on capacity and allocations, different IDs:** Mentors A and B both have `remaining_capacity = 2`, `allocations_new = 0`. With `mentor_id` values `M-01` and `M-02`, ordering follows `natural_key` → `M-01` before `M-02`.
3. **Exact tie, stable order preserved:** Mentors A and B with identical fields including `mentor_id` tokens appear in the same order as the incoming candidate pool when all sort keys are equal (merge-sort stability).
4. **Successive allocations update ranking:** Starting with `remaining_capacity = 1` for both mentors, first allocation selects mentor with lower `allocations_new` (both zero → tie broken by `mentor_sort_key`). After consuming capacity, that mentor’s `remaining_capacity` becomes `0` and `allocations_new` becomes `1`; on the next student, the other mentor (remaining `1`, allocations `0`) ranks first.

## 5. Risks and mitigations

* **Ambiguity risk:** Multiple capacity columns in input → `build_mentor_state` resolves using policy order and canonical headers; missing columns default to `0`, which is now explicitly documented.
* **Determinism risk:** Any introduction of non-stable sorting or randomness would break guarantees; merge-sort stability is now explicitly frozen.
* **Data-quality risk:** Negative or malformed capacity values are coerced to `0`; allocators must rely on QA layers to flag upstream data issues.

## 6. Decision record

* Ranking semantics are frozen as described in §3; deviations require a new RFC.
* This RFC is documentation-only; no code paths change. Downstream tests must continue to pass without alterations.

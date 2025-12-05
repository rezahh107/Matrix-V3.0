# AGENTS — Smart Student Allocation Engine

Version: 2.0  
Scope: Coding / refactor agents working on the student→mentor allocation system.

This file is the contract for how agents should read the repo, which rules are non-negotiable,
and how to implement changes safely.

---

## 1. Upstream specs (read these first)

Authoritative domain rules live in these documents:

- `docs/LAW_Smart_Student_Allocation_v3.0.md`  (LAW v3.0)
- `docs/Technical_SSoT_Smart_Student_Allocation_v3.0-TECH.md`
- `docs/Repository Specification (SSoT).md`
- `docs/📚 Refactor Narrative v3.0 — Import & Join Pipeline.md`
- `docs/LAW v3.0 — Regulatory Coverage Map v1.0.md`

**AGENTS.md must NOT redefine domain rules.**  
If anything here conflicts with LAW/Technical SSoT/Regulatory Coverage Map, those documents win.

---

## 2. Architecture boundaries (Core / Infra / UI)

Everything you do must respect this layering:

- **Core (`app/core/**`)**
  - Pure domain + algorithms.
  - No file/network/DB/Qt/logging/UI.
  - Deterministic: same inputs ⇒ same outputs (including ordering).
  - No `inplace=True` in pandas, no merge-in-loops.

- **Infra (`app/infra/**`)**
  - I/O, Excel/SQLite/WordPress, CLI, QA exports, history.
  - May call Core; MUST NOT re-implement join, ranking, or trace semantics.
  - Can add logging/metrics/feature flags around Core.

- **UI (`app/ui/**`)**
  - PySide6 presentation only.
  - No allocation/join/ranking/trace logic.
  - Talks to Infra/Core via public APIs.

Any change that breaks `Core ← Infra ← UI` is forbidden.

---

## 3. Non-negotiable domain invariants

These invariants are defined in LAW v3.0 and the Regulatory Coverage Map.
Agents must treat them as *hard constraints*, not suggestions.

### 3.1 Join keys & profiles

- Exactly **6 join keys**, all integers, used consistently end-to-end:
  `["کدرشته","جنسیت","دانش آموز فارغ","مرکز گلستان صدرا","مالی حکمت بنیاد","کد مدرسه"]`
- Domain model:
  - `JoinKeyProfile`: 6-int immutable, hashable value object.
  - `Mentor`: may hold `list[JoinKeyProfile]` (multi-profile mentor allowed at domain level).
  - `Student`: exactly one `JoinKeyProfile`.

Never:
- add/remove join keys,
- change their meaning or type,
- build ad-hoc join logic outside the unified pipeline (see §4).

### 3.2 Capacity & ranking

- `remaining_capacity = capacity_limit - (assigned_baseline + allocations_new)`
- Invariants:
  - `remaining_capacity` MUST NOT be negative.
  - Ranking in Core:
    1. `remaining_capacity` (descending)
    2. `allocations_new` (ascending) — when present as explicit tie-breaker
    3. `mentor_id` (ascending), stable sort.
- No ratio/score-based ranking (`occupancy_ratio`, custom scores, etc.) as domain concepts.

### 3.3 Trace (8-stage)

Per student, the trace has exactly 8 stages in this order:

`type, group, gender, graduation_status, center, finance, school, capacity_gate`

Core may add extra metadata but MUST NOT:
- change names,
- change order,
- drop stages.

### 3.4 School / center wildcard & mentor type

From LAW v3.0 / Coverage Map (names only, semantics live there):

- `SCHOOL-01`, `CENTER-01`, `WILDCARD-COMBINE-01`  
  - School and center each support `0` as a wildcard.
  - Eligibility is the AND of school_match and center_match.
- `MENTOR-TYPE-01`  
  - Mentor type derived from `school_count` (NORMAL vs SCHOOL).
- `MATRIX-BRANCH-01`  
  - Matrix rows must be either “normal” branch or “school” branch, never a hybrid.

Agents MUST NOT introduce new “dual” mentor types or alternative wildcard semantics.

---

## 4. Refactor v3 — import & join pipeline (mentors)

For mentor import & join, all new work MUST follow this pipeline:

`FieldRegistry → HeaderResolver → ValueCanonicalizer → JoinKeyResolver → MentorPoolBuilder`

High-level expectations:

- **FieldRegistry (Infra)**
  - Single SSoT for mentor/join related fields (sources, priorities, parsing rules).
- **HeaderResolver (Infra)**
  - Maps raw Excel headers → canonical field names.
  - Fail-fast when headers are missing/ambiguous.
- **ValueCanonicalizer (Infra)**
  - Converts raw text values → canonical domain types (group, gender, finance, center/school, capacity…).
- **JoinKeyResolver (Infra, Core-facing)**
  - Constructs `JoinKeyProfile`(s), detects duplicates/missing/invalid combos.
  - Produces QA artifacts and a clear `can_continue` decision.
- **MentorPoolBuilder (Infra)**
  - Builds canonical mentor DataFrame for Core (`build_matrix`, allocation).
  - Applies capacity gates and emits QA sheets.

Core must only consume the canonical DataFrame and MUST NOT reconstruct join keys by itself.

---

## 5. Agent expectations (how to write code)

### 5.1 General coding style

- Fully type-annotated functions and methods (params + return).
- No bare `dict/list/set/tuple` — use typed generics.
- Avoid `Any` and `# type: ignore` except in the smallest possible scope, with a reason.
- Keep functions small and intention-revealing (≈≤40 effective lines, ≤~3 branches).
- Prefer composition (helpers, dataclasses) over inheritance.

### 5.2 Tests & tooling (must pass)

Every change that touches production code should ship with tests and pass:

- `pytest -q`
- `mypy --strict app/core app/infra app/ui tests`
- `ruff check .`
- `black --check app/ infra/ ui/ tests/`

Tests should:

- Use clear Arrange–Act–Assert structure.
- Be deterministic, no hidden shared state.
- Add regression tests for every bug fix (especially around join, capacity, trace, QA).

### 5.3 Observability & QA

- Keep `ExecutionTracer` and QA exporters working:
  - Trace 8 stages.
  - QA sheets for join-key issues, capacity issues, invalid mentors, matrix vs students.
- When changing behavior that affects QA, update or add QA tests instead of weakening checks.

---

## 6. Risk & refusal behaviour (for LLM agents)

Agents are expected to follow their system-prompt **RISK_REFUSAL** protocol.

Use RISK_REFUSAL instead of guessing when:

- A change would modify join semantics, ranking order, trace stages, capacity rules, or wildcard rules.
- A change would alter Core/Infra/UI boundaries.
- A request conflicts with LAW/Technical SSoT/Regulatory Coverage Map.
- Scope is a broad refactor across many modules with unclear migration impact.

When in doubt: **stop and emit RISK_REFUSAL** instead of silently changing domain semantics.

---

## 7. File-scoped guidance

When editing:

- `app/core/**`
  - Never add I/O, randomness, or time-based decisions.
  - Respect capacity, ranking, and trace invariants.
- `app/infra/**`
  - Keep Excel/DB/CLI concerns here.
  - Do not redefine join/ranking/trace; only adapt to external formats and QA.
- `app/ui/**`
  - No business logic; only PySide6 widgets, view-models, and wiring to Infra.

If a change seems to blur these boundaries, treat it as a red flag and fall back to RISK_REFUSAL.

---

## 8. Versioning & maintenance

- **AGENTS.md v2.0** targets:
  - LAW v3.0
  - Technical SSoT v3.0-TECH
  - Refactor Narrative v3.0 (Import & Join Pipeline)
  - LAW v3.0 — Regulatory Coverage Map v1.0
  - Repository Specification (SSoT)

When any of these upstream documents change in a way that affects code:

1. Update the upstream doc first.
2. Reflect the change in tests and implementation.
3. Update AGENTS.md (version bump, short changelog entry).
4. Have the change reviewed with architectural eyes, not just code review.

---

## 9. Changelog

- **v2.0**
  - Shrunk AGENTS.md into a concise, GitHub-style guide for coding agents.
  - Delegated full rule text to LAW v3.0, Technical SSoT, Refactor Narrative v3.0, and
    Regulatory Coverage Map v1.0.
  - Emphasised the unified mentor import & join pipeline and architectural invariants.

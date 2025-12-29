# Pandas Index Contract Policy

This document defines the **Pandas Index Contract Policy** for canonical/core/allocation
pipelines. The goal is to prevent silent data corruption (index drift, label creation,
ambiguous assignment).

## Wall-worthy rules

1. **Never mutate with bracket assignment on Series/DataFrame.**
   - ❌ `s[idx] = value`
   - ❌ `df[col][idx] = value`
   - ❌ `df[col][mask] = value` (chained indexing)
   - ❌ `df[col].values[...] = value`
   - ✅ `s.at[label] = value` (after enforcing index contract)
   - ✅ `df.loc[row_mask, col] = value` (explicit, single-step)

2. **Every DF→DF function must declare an index contract.**
   - **Index is meaningless:** enforce `RangeIndex` and persist lineage in columns.
   - **Index is meaningful:** preserve labels, and assert index equality/uniqueness.

3. **“.loc alone is not enough.”**  
   You must enforce the index contract before assignment; otherwise `.loc` can
   create new labels silently.

4. **Merges must be validated.**
   - Use `validate="one_to_one"`, `"one_to_many"`, or `"many_to_one"` whenever possible.
   - Use `"many_to_many"` only with an explicit comment (and tests) explaining why it’s safe.

## Canonical contracts in this repo

### Index is meaningless (RangeIndex enforced)

These functions reset to `RangeIndex` and preserve lineage in a column:

- `app/core/canonical_frames.py::canonicalize_students_frame`
- `app/core/canonical_frames.py::canonicalize_pool_frame`
- `app/core/canonical_frames.py::sanitize_pool_for_allocation`

Lineage column used by default:

```
__source_index__
```

### Index is meaningful (preserved + asserted)

Example:

- `app/infra/canonical_frames.py::canonicalize_mentor_pool_frame`

Here the output index must exactly match the input index, and be unique.

## Recommended fixes

### Replace bracket assignment

```python
normalized = pd.Series(index=canonical.index, dtype=object)
assert_index_preserved(canonical.index, normalized.index, require_unique=True, require_same_order=True, context="...")
for idx, value in canonical["mentor_status"].items():
    normalized.at[idx] = normalize_status(value)
assert_no_new_labels(canonical.index, normalized.index, context="...")
```

### Enforce RangeIndex with lineage

```python
result = enforce_rangeindex_with_lineage(
    result,
    lineage_cols=["__source_index__"],
    context="canonicalize_students_frame",
)
```

## Allowed exceptions

1. **Non-unique index**  
   Only allowed with:
   - documented rationale (docstring + in-code comment),
   - explicit `.loc` assignment,
   - dedicated regression tests.

2. **many_to_many merges**  
   Must include:
   - in-line comment explaining why non-uniqueness is expected,
   - tests demonstrating correct behavior.

## Debug checklist

- Is the index unique? Do you *want* it to be?
- Does any assignment risk creating new labels?
- Are you merging without `validate=...`?
- Are you depending on `RangeIndex` semantics without resetting it?

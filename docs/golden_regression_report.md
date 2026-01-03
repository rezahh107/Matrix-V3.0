# Golden regression gate

## Files added/changed
- `tests/integration/conftest.py`: canonical CLI allocation fixture for reuse across integration tests.
- `tests/integration/test_golden_regression_outputs.py`: compares canonical outputs against committed golden snapshots with an `UPDATE_GOLDEN=1` refresh escape hatch.
- `tests/golden/README.md` and `tests/golden/outputs/**.csv`: stored normalized per-sheet baselines for the regression gate (no binary files).

## Golden comparison coverage
The regression gate normalizes, sorts, and compares these sheets:
- Main workbook: `allocations`, `updated_pool`, `logs`, `دلایل انتخاب پشتیبان`, `allocation_vs_pool_audit`.
- Validation workbook: `summary`, `students_per_mentor`, `school_binding_issues`, `allocation_capacity`, `join_keys`, `student_counts`, `pool_join_key_duplicates`, `pool_join_conflicts`, `pool_detection`, `alloc_join_summary`, `alloc_join_mismatches`, `pool_alignment_preflight`.

`allocations_sabt` comparison is temporarily disabled while Sabt export changes are paused.

## Updating goldens intentionally
Run the golden regression test with the environment flag to rewrite snapshots:

```bash
UPDATE_GOLDEN=1 pytest tests/integration/test_golden_regression_outputs.py -q
```

Only refresh goldens when the behavior change is intentional and reviewed.

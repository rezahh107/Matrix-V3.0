# Golden regression snapshots

This folder stores the deterministic baseline outputs for the canonical
allocation run:

- Students: `./students.xlsx`
- Pool: `./0918.xlsx` (sheet `matrix`)

## How to refresh goldens

Run the integration test with `UPDATE_GOLDEN=1` to rewrite the snapshots:

```bash
UPDATE_GOLDEN=1 pytest tests/integration/test_golden_regression_outputs.py -q
```

New files will be written to `tests/golden/outputs/` as per-sheet normalized
CSVs (no binaries):

- `output/<sheet>.csv`
- `output_validation/<sheet>.csv`

Only update these files when the intentional, reviewed behavior changes.

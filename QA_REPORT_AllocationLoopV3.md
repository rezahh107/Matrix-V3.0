# QA_REPORT — AllocationLoopV3

## 1) Pytest integration

- command: python -m pytest tests/integration/test_allocation_end_to_end.py -k allocation_loop_v3 --maxfail=1 -q
- result: FAIL (no tests collected with `-k allocation_loop_v3`; test name lacks the `_v3` substring)
- details (on FAIL): Command deselected the only test ("1 deselected"). Reran without `-k` filter: `python -m pytest tests/integration/test_allocation_end_to_end.py -q` -> PASS (1 test).

## 2) Golden regression

- config: ci/configs/golden_regression.yml
- suite_name_used: phase01_lock_current_behavior (only scenario defined; script does not support `--suite` or `--diff-output` arguments)
- command_1 (--fail-on-missing): N/A (argument unsupported by runner). Executed `PYTHONPATH=. python scripts/run_golden_regression.py --config ci/configs/golden_regression.yml` instead.
- command_2 (--diff-output): N/A (argument unsupported by runner).
- golden_diff_summary:
  - number_of_files_with_diffs: 0 (execution halted before running commands)
  - short_description_per_file: N/A (missing required golden inputs prevented execution)
  - classification_per_file: N/A
- golden run notes: Runner reported missing required files:
  - /workspace/Matrix2/ci/configs/docs/golden_datasets/phase01_lock_current_behavior/InspactorReport-1404_09_15-3570.xlsx
  - /workspace/Matrix2/ci/configs/docs/golden_datasets/phase01_lock_current_behavior/SchoolReport-1404_09_15-3570.xlsx

## 3) Trace schema

- trace_source (trace_df / HistoryStore table ...): trace DataFrame returned by app.core.allocation.allocation_loop_v3.run_allocation_loop_v3 using in-test fixture
- columns_observed: ["student_id", "mentor_id", "type", "group", "gender", "graduation_status", "center", "finance", "school", "capacity_gate"]
- comparison_with_SSoT_and_existing_QA: MATCH (8-step trace columns present in order; student/mentor IDs preserved as leading columns)
- notes_on_any_mismatch: None

## 4) HistoryStore / QA workbooks

- workbook_or_tool_checked: None available in repo for AllocationLoopV3 trace; golden workbook inputs missing
- status: ERROR (blocked by absent golden Excel inputs and no workbook artifacts to open)
- notes: Could not validate workbook formulas because required golden Excel files are missing under docs/golden_datasets/phase01_lock_current_behavior.

## 5) Overall risk & recommendation (your view)

- overall_risk: MEDIUM (golden inputs missing; QA workbook compatibility unverified)
- merge_ok_if_architect_confirms: NO (needs golden files restored and workbook check)
- extra_notes: Golden runner lacks `--suite` and `--diff-output` flags; only dry-run/missing-file validation executed. Restore sanitized golden Excel files under docs/golden_datasets/phase01_lock_current_behavior and rerun runner to capture actual golden diffs.

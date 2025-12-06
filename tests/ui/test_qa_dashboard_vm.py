import pandas as pd

from app.core.common.types import JoinKeyValidationIssue, JoinKeyValidationResult
from app.ui.viewmodels.qa_dashboard_vm import QADashboardVM


def test_qa_dashboard_vm_registers_runs() -> None:
    vm = QADashboardVM()
    vm.register_run(
        "run-1",
        {
            "student": JoinKeyValidationResult(canonical_df=pd.DataFrame(), issues=[]),
            "mentor": JoinKeyValidationResult(
                canonical_df=pd.DataFrame(),
                issues=[
                    JoinKeyValidationIssue(
                        entity_type="mentor",
                        row_index=0,
                        column="کدرشته",
                        raw_value="bad",
                        error_code="DATA_INVALID",
                    )
                ],
            ),
        },
        qa_failed_rules=2,
        trace_rows=5,
    )
    assert vm.issue_count(0, "mentor") == 1
    assert vm.has_issues(0)
    assert vm.fix_target(0, "mentor") == ("run-1", "mentor")
    assert vm.summaries[0].qa_failed_rules == 2
    assert vm.summaries[0].trace_rows == 5

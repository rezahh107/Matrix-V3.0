from __future__ import annotations

import pandas as pd
import pytest

from app.core.common.types import StudentDomainValidationIssue, StudentDomainValidationResult
from app.ui.viewmodels.student_domain_validation_vm import (
    StudentDomainIssueVM,
    StudentDomainValidationVM,
)


def test_student_domain_validation_vm_aggregates_issues() -> None:
    issue = StudentDomainValidationIssue(
        row_index=0,
        group_code=33,
        graduation_status=0,
        allowed_statuses=(1,),
        error_code="INVALID",
    )
    result = StudentDomainValidationResult(canonical_df=pd.DataFrame(), issues=[issue])
    vm = StudentDomainValidationVM.from_result(result)
    assert vm.total_issues == 1
    counts = vm.issue_counts_by_error()
    assert counts == {"INVALID": 1}


def test_student_domain_validation_dialog_constructs() -> None:
    pytest.importorskip("PySide6")
    pytest.importorskip("pytestqt")
    from pytestqt.qtbot import QtBot  # type: ignore

    qtbot_fixture = QtBot(None)
    vm = StudentDomainValidationVM(
        [StudentDomainIssueVM(0, 33, 0, (1,), "INVALID_GRADUATION_FOR_GROUP")]
    )
    from app.ui.dialogs.student_domain_validation_dialog import StudentDomainValidationDialog

    dialog = StudentDomainValidationDialog(vm)
    qtbot_fixture.addWidget(dialog)
    dialog.show()
    assert dialog.isVisible()

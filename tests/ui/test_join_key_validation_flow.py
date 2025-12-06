from __future__ import annotations

import time
from typing import cast

import pandas as pd
import pytest

try:  # pragma: no cover - import guard for headless CI
    from PySide6.QtWidgets import QApplication, QWidget
except ImportError as exc:  # pragma: no cover - skipped when Qt missing
    pytest.skip(f"PySide6 unavailable: {exc}", allow_module_level=True)

from app.core.common.types import JoinKeyValidationIssue, JoinKeyValidationResult
from app.infra.errors import JoinKeyValidationError
from app.ui.dialogs.join_key_validation_dialog import JoinKeyValidationDialog
from app.ui.main_window import MainWindow
from app.ui.viewmodels.join_key_validation_vm import JoinKeyValidationVM


@pytest.fixture()
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _drain_events(app: QApplication, timeout_ms: int = 500) -> None:
    """Process Qt events for a bounded duration."""

    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        app.processEvents()


class _StubJoinKeyDialog(JoinKeyValidationDialog):
    instances: list[_StubJoinKeyDialog] = []

    def __init__(self, vm: JoinKeyValidationVM, parent: QWidget | None = None):
        super().__init__(vm, parent)
        self.shown = False
        self.raised = False
        _StubJoinKeyDialog.instances.append(self)

    def show(self) -> None:  # pragma: no cover - trivial UI plumbing
        self.shown = True

    def raise_(self) -> None:  # noqa: D401 - Qt signature
        self.raised = True


def test_join_key_validation_error_opens_dialog(qapp: QApplication) -> None:
    window = MainWindow()
    window._join_key_validation_dialog_class = cast(
        type[JoinKeyValidationDialog], _StubJoinKeyDialog
    )

    issue = JoinKeyValidationIssue(
        entity_type="student",
        row_index=0,
        column="کدرشته",
        raw_value="",
        error_code="DATA_MISSING",
    )
    result = JoinKeyValidationResult(canonical_df=pd.DataFrame(), issues=[issue])
    error = JoinKeyValidationError(result)

    window._on_finished(False, error)

    assert _StubJoinKeyDialog.instances, "join-key validation dialog should be created"
    dialog = _StubJoinKeyDialog.instances[-1]
    assert dialog.view_model.issues[0].column == "کدرشته"
    window.close()
    _drain_events(qapp)


def test_non_join_key_error_does_not_create_dialog(qapp: QApplication) -> None:
    window = MainWindow()
    window._join_key_validation_dialog_class = cast(
        type[JoinKeyValidationDialog], _StubJoinKeyDialog
    )

    _StubJoinKeyDialog.instances.clear()
    window._splitter.deleteLater()
    _drain_events(qapp)

    window._on_finished(False, ValueError("other error"))

    _drain_events(qapp)
    assert not _StubJoinKeyDialog.instances
    assert window._join_key_validation_dialog is None
    window.close()
    _drain_events(qapp)

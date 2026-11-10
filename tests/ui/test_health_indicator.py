from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from app.infra.health import HealthStatus, HealthSummary, IssueSummary
from app.ui.texts import UiTranslator
from app.ui.widgets.health_indicator import HealthCallbacks, HealthIndicatorWidget

_SUMMARY_TEXT = {
    "OK": "Recorded QA passed; output file not independently verified.",
    "WARN": "System health: WARNING 🟡 (review warnings before using output)",
    "ERROR": "System health: ERROR 🔴 (do NOT use this output)",
}


def _summary(status: HealthStatus = "WARN") -> HealthSummary:
    counts = {"P0": 0, "P1": 0, "P2": 0}
    if status == "ERROR":
        counts["P0"] = 1
    elif status == "WARN":
        counts["P1"] = 1
    return HealthSummary(
        status=status,
        summary_text=_SUMMARY_TEXT[status],
        counts=counts,
        issues_summary=[IssueSummary(issue_code="QA_RULE_SAMPLE", severity="P1", count=1)],
    )


def test_health_indicator_preserves_summary_text_without_translator(qtbot) -> None:
    summary = _summary("WARN")
    widget = HealthIndicatorWidget(
        HealthCallbacks(fetch_summary=lambda: summary, export_report=lambda: None)
    )
    qtbot.addWidget(widget)

    assert widget._status_label.text() == summary.summary_text
    assert widget._status_label.text().count("System health:") == 1


@pytest.mark.parametrize(
    ("status", "expected_state"),
    [("OK", "ok"), ("WARN", "warning"), ("ERROR", "error")],
)
def test_health_indicator_maps_status_to_existing_qss_state(
    qtbot, status: HealthStatus, expected_state: str
) -> None:
    summary = _summary(status)
    widget = HealthIndicatorWidget(
        HealthCallbacks(fetch_summary=lambda: summary, export_report=lambda: None)
    )
    qtbot.addWidget(widget)

    assert widget._status_label.property("health") == expected_state


@pytest.mark.parametrize(
    ("language", "status", "expected"),
    [
        ("en", "OK", "Recorded QA passed; output file not independently verified."),
        ("en", "WARN", "QA warnings recorded; review before using the output."),
        ("en", "ERROR", "QA failed or material errors were recorded; do not use the output."),
        ("fa", "OK", "نتیجهٔ ثبت‌شدهٔ QA موفق است؛ اعتبار فایل خروجی مستقلاً بررسی نشده است."),
        (
            "fa",
            "WARN",
            "در QA هشدار ثبت شده است؛ پیش از استفاده از خروجی آن را بررسی کنید.",
        ),
        ("fa", "ERROR", "QA ناموفق است یا خطای مهم ثبت شده؛ از خروجی استفاده نکنید."),
    ],
)
def test_health_indicator_uses_complete_localized_sentence(
    qtbot, language: str, status: HealthStatus, expected: str
) -> None:
    summary = _summary(status)
    widget = HealthIndicatorWidget(
        HealthCallbacks(fetch_summary=lambda: summary, export_report=lambda: None),
        translator=UiTranslator(language),
    )
    qtbot.addWidget(widget)

    assert widget._status_label.text() == expected
    if language == "fa":
        assert summary.summary_text not in widget._status_label.text()
        assert "System health" not in widget._status_label.text()


def test_health_indicator_update_translator_changes_presentation_only(qtbot) -> None:
    summary = _summary("WARN")
    widget = HealthIndicatorWidget(
        HealthCallbacks(fetch_summary=lambda: summary, export_report=lambda: None),
        translator=UiTranslator("en"),
    )
    qtbot.addWidget(widget)
    english_text = widget._status_label.text()

    widget.update_translator(UiTranslator("fa"))

    assert english_text == "QA warnings recorded; review before using the output."
    assert (
        widget._status_label.text()
        == "در QA هشدار ثبت شده است؛ پیش از استفاده از خروجی آن را بررسی کنید."
    )
    assert widget._status_label.property("health") == "warning"
    assert widget._current_summary is summary


def test_health_indicator_details_and_export_regression(qtbot, monkeypatch) -> None:
    summary = _summary("WARN")
    exported: list[str] = []

    def _export() -> str:
        exported.append("ok")
        return "/tmp/report.json"

    widget = HealthIndicatorWidget(
        HealthCallbacks(fetch_summary=lambda: summary, export_report=_export),
        translator=UiTranslator("en"),
    )
    qtbot.addWidget(widget)
    captured: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, title, text: captured.append((title, text)),
    )

    qtbot.mouseClick(widget._btn_details, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(widget._btn_export, Qt.MouseButton.LeftButton)

    assert widget._btn_details.isEnabled()
    assert widget._btn_export.isEnabled()
    assert exported == ["ok"]
    assert captured[0][0] == "Health details"
    assert "P1: 1" in captured[0][1]
    assert captured[1] == ("Report exported", "Report saved to: /tmp/report.json")


def test_health_indicator_unavailable_state_disables_actions(qtbot) -> None:
    widget = HealthIndicatorWidget(
        HealthCallbacks(fetch_summary=lambda: None, export_report=lambda: "/tmp/report.json"),
        translator=UiTranslator("en"),
    )
    qtbot.addWidget(widget)

    assert widget._current_summary is None
    assert widget._status_label.text() == "No run recorded; no QA result is available."
    assert widget._status_label.property("health") == "none"
    assert not widget._btn_details.isEnabled()
    assert not widget._btn_export.isEnabled()


@pytest.mark.parametrize(
    ("language", "reason", "expected"),
    [
        ("en", "not_recorded", "No QA result recorded; output is not verified."),
        ("en", "invalid", "Stored QA evidence is unreadable or invalid; output is not verified."),
        ("en", "incomplete", "Stored QA evidence is incomplete; output is not verified."),
        ("en", "run_failed", "Run failed; no assurance about its output is available."),
        ("fa", "not_recorded", "نتیجهٔ QA ثبت نشده است؛ خروجی تأیید نشده است."),
        ("fa", "invalid", "شواهد QA ناخوانا یا نامعتبر است؛ خروجی تأیید نشده است."),
        ("fa", "incomplete", "شواهد QA ناقص است؛ خروجی تأیید نشده است."),
        ("fa", "run_failed", "اجرا ناموفق بوده است؛ ایمن‌بودن خروجی تأیید نشده است."),
    ],
)
def test_health_indicator_reason_specific_truthful_message(qtbot, language, reason, expected):
    status = "ERROR" if reason == "run_failed" else "UNVERIFIED"
    summary = HealthSummary(
        status=status, reason=reason, summary_text="raw evidence reason",
        counts={"P0": 0, "P1": 0, "P2": 0}, issues_summary=[],
    )
    widget = HealthIndicatorWidget(
        HealthCallbacks(fetch_summary=lambda: summary, export_report=lambda: None),
        translator=UiTranslator(language),
    )
    qtbot.addWidget(widget)
    assert widget._status_label.text() == expected
    assert widget._status_label.property("health") == (
        "error" if status == "ERROR" else "none"
    )


def test_health_indicator_refresh_does_not_retain_prior_pass(qtbot):
    active = [_summary("OK")]
    widget = HealthIndicatorWidget(
        HealthCallbacks(fetch_summary=lambda: active[0], export_report=lambda: None),
        translator=UiTranslator("en"),
    )
    qtbot.addWidget(widget)
    assert widget._status_label.property("health") == "ok"
    active[0] = HealthSummary(
        status="UNVERIFIED", reason="not_recorded", summary_text="unverified",
        counts={"P0": 0, "P1": 0, "P2": 0}, issues_summary=[],
    )
    widget.refresh()
    assert widget._status_label.property("health") == "none"
    assert widget._status_label.text() == "No QA result recorded; output is not verified."
    active[0] = None
    widget.refresh()
    assert widget._status_label.text() == "No run recorded; no QA result is available."
    assert not widget._btn_details.isEnabled()

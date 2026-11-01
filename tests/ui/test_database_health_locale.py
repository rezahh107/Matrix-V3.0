"""Live EN/FA database health translation at the real MainWindow boundary."""

from __future__ import annotations

import re
import sqlite3

import pytest

from app.infra.local_database import DatabaseHealthReason, DatabaseHealthStatus, LocalDatabase
from app.ui.i18n import Language
from app.ui.main_window import MainWindow
from app.ui.theme import apply_theme, build_theme

_PERSIAN = re.compile(r"[\u0600-\u06ff]")
_CASES = {
    "ok": (DatabaseHealthStatus.OK, DatabaseHealthReason.READY, "DB: Ready", "پایگاه‌داده: آماده", "ok"),
    "degraded": (DatabaseHealthStatus.DEGRADED, DatabaseHealthReason.NEEDS_REVIEW, "DB: Check", "پایگاه‌داده: نیاز به بررسی", "warning"),
    "missing": (DatabaseHealthStatus.UNAVAILABLE, DatabaseHealthReason.MISSING_FILE, "DB: No file", "پایگاه‌داده: فایل یافت نشد", "error"),
    "connection": (DatabaseHealthStatus.UNAVAILABLE, DatabaseHealthReason.CONNECTION_ERROR, "DB: SQL error", "پایگاه‌داده: خطای اتصال", "error"),
}

_FULL_EN = {
    "ok": "Database: Ready",
    "degraded": "Database: Needs attention",
    "missing": "Database: File not found",
    "connection": "Database: Connection error",
}


def _database_for_scenario(tmp_path, scenario: str) -> LocalDatabase:
    path = tmp_path / (scenario + ".sqlite")
    if scenario == "ok":
        LocalDatabase(path).initialize()
    elif scenario == "degraded":
        sqlite3.connect(path).close()
    elif scenario == "connection":
        path.write_bytes(b"invalid SQLite header")
    return LocalDatabase(path)


@pytest.mark.parametrize("scenario", tuple(_CASES))
@pytest.mark.parametrize("theme", ("light", "dark"))
def test_health_live_en_fa_en_main_window(qapp, tmp_path, scenario: str, theme: str) -> None:
    expected_status, expected_reason, en, fa, state = _CASES[scenario]
    window = MainWindow()
    try:
        window._theme = build_theme(theme)
        apply_theme(qapp, window._theme)
        window._apply_theme_styles()
        window.resize(960, 640)
        window.show()
        qapp.processEvents()
        database = _database_for_scenario(tmp_path, scenario)
        summary = database.get_database_health_summary()
        assert summary.status is expected_status
        assert summary.reason is expected_reason
        widget = window._database_status
        assert widget is not None
        widget.set_summary(summary)
        for language, expected in ((Language.EN, en), (Language.FA, fa), (Language.EN, en)):
            window._apply_language(language)
            qapp.processEvents()
            assert widget._text_label.text() == expected
            detailed = _FULL_EN[scenario] if language is Language.EN else fa
            assert widget.accessibleDescription() == detailed
            assert widget.accessibleName() == (
                "Database health" if language is Language.EN else "سلامت پایگاه‌داده"
            )
            assert widget.toolTip().startswith(detailed)
            assert widget._icon_label.property("databaseHealth") == state
            assert widget._text_label.property("databaseHealth") == state
            if language is Language.EN:
                # Negative regression control: Persian infra strings may not
                # reach any English UI-owned status/tooltip/accessibility copy.
                for ui_text in (
                    widget._text_label.text(), widget.toolTip(),
                    widget.accessibleDescription(), widget.accessibleName()
                ):
                    assert not _PERSIAN.search(ui_text), ui_text
                if scenario in ("ok", "degraded"):
                    assert "Students: 0" in widget.toolTip()
                    assert "Mentors: 0" in widget.toolTip()
                    assert "Runs: 0" in widget.toolTip()
                    assert "Last checked:" in widget.toolTip()
            elif scenario in ("ok", "degraded"):
                assert "آخرین بررسی:" in widget.toolTip()
                assert "دانش‌آموز: 0" in widget.toolTip()
    finally:
        window.close()


def test_unknown_unavailable_reason_does_not_fabricate_specific_cause(qapp) -> None:
    from app.infra.local_database import DatabaseHealthSummary

    window = MainWindow()
    try:
        window._apply_language(Language.EN)
        summary = DatabaseHealthSummary(
            status=DatabaseHealthStatus.UNAVAILABLE,
            message="متن تشخیصی نامشخص", counts={}, reason=None,
        )
        widget = window._database_status
        assert widget is not None
        widget.set_summary(summary)
        assert widget._text_label.text() == "DB: Unavailable"
        assert widget.accessibleDescription() == "Database: Unavailable"
        assert "File not found" not in widget.toolTip()
        assert "Connection error" not in widget.toolTip()
    finally:
        window.close()

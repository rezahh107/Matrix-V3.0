"""Real Windows Qt evidence for the P0 QA false-assurance repair.

Isolated MainWindow, synthetic SQLite, and actual localized HealthIndicator.
This proves Windows offscreen rendering, not physical-screen/operator acceptance.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sqlite3
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch


def _record(token: str, when: datetime, *, qa: dict | None = None, status: str = "success"):
    from app.infra.local_database import RunRecord

    return RunRecord(
        run_uuid=token,
        started_at=when,
        finished_at=when,
        policy_version="synthetic",
        ssot_version="synthetic",
        entrypoint="allocate",
        cli_args=None,
        db_path=None,
        input_files_json="{}",
        input_hashes_json="{}",
        total_students=0,
        total_allocated=0,
        total_unallocated=0,
        history_metrics_json=None,
        qa_summary_json=json.dumps(qa) if qa is not None else None,
        status=status,
        message=None,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    if platform.system() != "Windows":
        raise RuntimeError("This test must run on the real Windows runner")
    expected_sha = os.environ.get("MATRIX_EXPECTED_SOURCE_SHA")
    actual_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if not expected_sha or expected_sha != actual_sha:
        raise RuntimeError(f"Checkout identity mismatch: {actual_sha} != {expected_sha}")

    target = args.output_dir.resolve()
    target.mkdir(parents=True, exist_ok=True)
    observations: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="matrix-qa-health-") as directory:
        root = Path(directory)
        home = root / "home"
        config = root / "settings"
        output = root / "output"
        for item in (home, config, output, root / "appdata", root / "localappdata"):
            item.mkdir(parents=True, exist_ok=True)
        env = {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "APPDATA": str(root / "appdata"),
            "LOCALAPPDATA": str(root / "localappdata"),
            "XDG_CONFIG_HOME": str(config),
            "XDG_DATA_HOME": str(root / "localappdata"),
            "QT_QPA_PLATFORM": "offscreen",
            "MATRIX_OUTPUT_ROOT": str(output),
        }
        with patch.dict(os.environ, env), patch.object(Path, "home", return_value=home):
            import pandas as pd
            from PySide6 import __version__ as pyside_version
            from PySide6.QtCore import QCoreApplication, QSettings
            from PySide6.QtWidgets import QApplication

            from app.ui.i18n import Language
            from app.ui.main_window import MainWindow
            from app.ui.texts import UiTranslator
            from app.ui.widgets.health_indicator import HealthCallbacks, HealthIndicatorWidget

            QCoreApplication.setOrganizationName("MatrixSyntheticQAQualification")
            QCoreApplication.setApplicationName("MatrixSyntheticQAQualification")
            QSettings.setDefaultFormat(QSettings.Format.IniFormat)
            QSettings.setPath(
                QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(config)
            )
            QSettings.setPath(
                QSettings.Format.IniFormat, QSettings.Scope.SystemScope, str(config)
            )
            app = QApplication.instance() or QApplication([])
            assert app.platformName() == "offscreen"
            window = MainWindow()
            window.show()
            app.processEvents()
            db = window._local_db
            assert db is not None and db.path.is_relative_to(root), (
                "MainWindow SQLite is not in the disposable profile"
            )

            try:
                def check(label: str, *, status: str | None, reason: str | None,
                          language: str, expected_text: str, screenshot: str):
                    window._apply_language(Language.FA if language == "fa" else Language.EN)
                    window._refresh_health_widget()
                    app.processEvents()
                    summary = window._health_widget._current_summary
                    visible = window._health_widget._status_label.text()
                    assert (summary.status if summary is not None else None) == status
                    assert (summary.reason if summary is not None else None) == reason
                    assert visible == expected_text, (label, visible, expected_text)
                    assert "safe to use" not in visible.lower()
                    assert "استفاده از خروجی ایمن است" not in visible
                    if label.startswith("unavailable_run_history"):
                        assert window._health_widget._status_label.property("health") == "none"
                        assert not window._health_widget._btn_details.isEnabled()
                        assert not window._health_widget._btn_export.isEnabled()
                    # The compact MainWindow status row may have tiny geometry in
                    # Windows offscreen CI. Capture the same real Qt widget with
                    # the same real callback in a separately sized evidence surface.
                    visual = HealthIndicatorWidget(
                        HealthCallbacks(
                            fetch_summary=window._fetch_health_summary,
                            export_report=lambda: None,
                        ),
                        translator=UiTranslator(language),
                    )
                    try:
                        visual.resize(680, 64)
                        visual.show()
                        app.processEvents()
                        assert visual._status_label.text() == visible
                        pix = visual.grab()
                        assert not pix.isNull() and pix.width() >= 400 and pix.height() >= 35
                        assert pix.save(str(target / screenshot), "PNG")
                    finally:
                        visual.close()
                    observations.append({
                        "scenario": label, "status": status, "reason": reason,
                        "language": language, "visible_text": visible,
                        "qss_state": window._health_widget._status_label.property("health"),
                        "image": screenshot,
                    })
    
                t = datetime(2026, 11, 9, 12, tzinfo=UTC)
                check(
                    "no_run", status=None, reason=None, language="en",
                    expected_text=UiTranslator("en").text("health.no_run"),
                    screenshot="no-run-en.png",
                )
                positive_id = db.insert_run(_record(
                    "synthetic-positive", t, qa={"passed": True, "violation_count": 0}
                ))
                db.insert_qa_snapshot(
                    run_id=positive_id,
                    qa_summary_df=pd.DataFrame([{
                        "rule_id": "QA_RULE_SAMPLE",
                        "status": "PASS",
                        "violations_count": 0,
                    }]),
                    qa_details_df=pd.DataFrame(columns=["rule_id", "level", "message"]),
                )
                for lang in ("en", "fa"):
                    check(
                        "valid_qa_pass", status="OK", reason=None, language=lang,
                        expected_text=UiTranslator(lang).text("health.summary.ok"),
                        screenshot=f"qa-pass-{lang}.png",
                    )
    
                db.insert_run(_record("synthetic-qa-missing", t + timedelta(seconds=1)))
                for lang in ("en", "fa"):
                    check(
                        "run_transition_to_missing_qa",
                        status="UNVERIFIED", reason="not_recorded", language=lang,
                        expected_text=UiTranslator(lang).text("health.summary.not_recorded"),
                        screenshot=f"qa-missing-{lang}.png",
                    )
    
                broken_id = db.insert_run(_record(
                    "synthetic-invalid", t + timedelta(seconds=2),
                    qa={"passed": True, "violation_count": 0},
                ))
                with db.connect() as conn:
                    conn.execute(
                        "INSERT INTO qa_snapshots (run_id, qa_summary_json) VALUES (?, ?)",
                        (broken_id, "{malformed"),
                    )
                    conn.commit()
                check(
                    "unreadable_qa_snapshot", status="UNVERIFIED", reason="invalid",
                    language="fa", expected_text=UiTranslator("fa").text("health.summary.invalid"),
                    screenshot="qa-invalid-fa.png",
                )
    
                db.insert_run(_record(
                    "synthetic-failed-run", t + timedelta(seconds=3), status="failed",
                ))
                check(
                    "failed_run", status="ERROR", reason="run_failed",
                    language="fa", expected_text=UiTranslator("fa").text("health.summary.run_failed"),
                    screenshot="failed-run-fa.png",
                )
                # F1: one damaged QA sibling does not hide independently
                # readable negative rule details in the real SQLite + GUI path.
                p0_id = db.insert_run(_record(
                    "synthetic-p0-broken-extras", t + timedelta(seconds=4),
                    qa={"passed": True, "violation_count": 1},
                ))
                db.insert_qa_snapshot(
                    run_id=p0_id,
                    qa_summary_df=pd.DataFrame([{
                        "rule_id": "QA_RULE_SAMPLE", "status": "WARN", "violations_count": 1,
                    }]),
                    qa_details_df=pd.DataFrame([{
                        "rule_id": "QA_RULE_SAMPLE", "level": "critical",
                    }]),
                )
                with db.connect() as conn:
                    conn.execute(
                        "UPDATE qa_snapshots SET qa_extras_json = ? WHERE run_id = ?",
                        ("{malformed", p0_id),
                    )
                    conn.commit()
                check(
                    "damaged_extras_preserves_p0", status="ERROR", reason=None,
                    language="en", expected_text=UiTranslator("en").text("health.summary.error"),
                    screenshot="damaged-extras-p0-en.png",
                )
                p1_id = db.insert_run(_record(
                    "synthetic-p1-broken-summary", t + timedelta(seconds=5),
                    qa={"passed": True, "violation_count": 1},
                ))
                db.insert_qa_snapshot(
                    run_id=p1_id,
                    qa_summary_df=pd.DataFrame([{
                        "rule_id": "QA_RULE_SAMPLE", "status": "WARN", "violations_count": 1,
                    }]),
                    qa_details_df=pd.DataFrame([{
                        "rule_id": "QA_RULE_SAMPLE", "level": "warn",
                    }]),
                )
                with db.connect() as conn:
                    conn.execute(
                        "UPDATE qa_snapshots SET qa_summary_json = ? WHERE run_id = ?",
                        ("{malformed", p1_id),
                    )
                    conn.commit()
                check(
                    "damaged_summary_preserves_p1", status="WARN", reason=None,
                    language="fa", expected_text=UiTranslator("fa").text("health.summary.warn"),
                    screenshot="damaged-summary-p1-fa.png",
                )

                # F2: a genuine empty history was tested above. A real failed
                # query must use the existing localized unavailable presentation.
                db.insert_run(_record(
                    "synthetic-positive-transition", t + timedelta(seconds=6),
                    qa={"passed": True, "violation_count": 0},
                ))
                latest_id = db.fetch_runs()[-1]["id"]
                db.insert_qa_snapshot(
                    run_id=latest_id,
                    qa_summary_df=pd.DataFrame([{
                        "rule_id": "QA_RULE_SAMPLE", "status": "PASS", "violations_count": 0,
                    }]),
                    qa_details_df=pd.DataFrame(columns=["rule_id", "level"]),
                )
                check(
                    "pass_before_history_failure", status="OK", reason=None,
                    language="en", expected_text=UiTranslator("en").text("health.summary.ok"),
                    screenshot="pass-before-history-failure-en.png",
                )
                unavailable_db = type(db)(root / "uninitialized-history.db")
                try:
                    try:
                        unavailable_db.fetch_runs()
                    except sqlite3.OperationalError as exc:
                        assert "no such table" in str(exc)
                    else:
                        raise AssertionError("SQLite history query unexpectedly succeeded")
                    window._local_db = unavailable_db
                    for lang in ("en", "fa"):
                        check(
                            "unavailable_run_history", status=None, reason=None,
                            language=lang,
                            expected_text=UiTranslator(lang).text("health.unavailable"),
                            screenshot=f"history-unavailable-{lang}.png",
                        )
                finally:
                    window._local_db = db
                    unavailable_db.close_all_connections()
                check(
                    "health_recovers_after_history_restored", status="OK", reason=None,
                    language="fa", expected_text=UiTranslator("fa").text("health.summary.ok"),
                    screenshot="history-restored-fa.png",
                )
                # F1 grouping: malformed rule identity must not hide valid P0.
                mixed_id = db.insert_run(_record(
                    "synthetic-valid-p0-bad-rule-sibling", t + timedelta(seconds=7),
                    qa={"passed": True, "violation_count": 2},
                ))
                db.insert_qa_snapshot(
                    run_id=mixed_id,
                    qa_summary_df=pd.DataFrame([{
                        "rule_id": "R", "status": "WARN", "violations_count": 2,
                    }]),
                    qa_details_df=pd.DataFrame([
                        {"rule_id": "R", "level": "P0", "student_id": 11},
                        {"rule_id": ["BROKEN"], "level": "P2", "student_id": 12},
                    ]),
                )
                for lang in ("en", "fa"):
                    check(
                        "valid_p0_with_malformed_rule_sibling", status="ERROR", reason=None,
                        language=lang,
                        expected_text=UiTranslator(lang).text("health.summary.error"),
                        screenshot=f"valid-p0-malformed-rule-{lang}.png",
                    )
                    observed = window._fetch_health_summary()
                    assert observed is not None and observed.counts["P0"] == 1
                    assert [(i.issue_code, i.severity) for i in observed.issues_summary] == [
                        ("R", "P0")
                    ]

                malformed_only_id = db.insert_run(_record(
                    "synthetic-bad-rule-only", t + timedelta(seconds=8),
                    qa={"passed": True, "violation_count": 1},
                ))
                db.insert_qa_snapshot(
                    run_id=malformed_only_id,
                    qa_summary_df=pd.DataFrame([{
                        "rule_id": "R", "status": "PASS", "violations_count": 1,
                    }]),
                    qa_details_df=pd.DataFrame([{
                        "rule_id": ["BROKEN"], "level": "P2", "student_id": 12,
                    }]),
                )
                check(
                    "malformed_rule_alone_not_positive", status="UNVERIFIED", reason="invalid",
                    language="en", expected_text=UiTranslator("en").text("health.summary.invalid"),
                    screenshot="invalid-rule-no-positive-en.png",
                )
                assert len(observations) == 16
                environment = {
                    "source_sha": actual_sha,
                    "platform": platform.platform(),
                    "python": sys.version.split()[0],
                    "pyside6": pyside_version,
                    "qt_platform": app.platformName(),
                    "synthetic_data_only": True,
                    "isolated_home_qsettings_sqlite": True,
                    "allocation_executed": False,
                }
                (target / "environment.json").write_text(
                    json.dumps(environment, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                (target / "qa-health-results.json").write_text(
                    json.dumps({"environment": environment, "observations": observations},
                               ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            finally:
                window.close()
                db.close_all_connections()
                app.processEvents()
    print(json.dumps({
        "source_sha": actual_sha,
        "scenarios": len(observations),
        "verdict": "WINDOWS_QT_QA_TRUTHFULNESS_OBSERVED",
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())

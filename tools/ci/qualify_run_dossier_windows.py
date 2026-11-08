"""Windows-offscreen, Dossier-specific visual and interaction qualification.

Only synthetic SQLite data is used; screenshots are of the actual HistoryDialog.
This is not human operator acceptance or a native interactive desktop test.
"""

from __future__ import annotations

import argparse
import hashlib
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

import pandas as pd
from PySide6 import __version__ as pyside_version
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QScrollArea

from app.infra.local_database import LocalDatabase, RunMetricRow, RunRecord
from app.ui.history_dialog import HistoryDialog
from app.ui.texts import UiTranslator
from app.ui.theme import apply_layout_direction, apply_theme

PATHS = (r"C:\synthetic\dossier\run-A.xlsx", r"C:\synthetic\dossier\run-B.xlsx")


def _head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def _seed(db: LocalDatabase) -> tuple[int, int]:
    db.initialize()
    ids: list[int] = []
    started = datetime(2026, 11, 8, tzinfo=UTC)
    for index, tag in enumerate(("A", "B")):
        current = started + timedelta(seconds=index)
        run_id = db.insert_run(
            RunRecord(
                run_uuid=f"synthetic-dossier-{tag}",
                started_at=current,
                finished_at=current,
                policy_version="1.0.3",
                ssot_version="1.0.2",
                entrypoint="allocate",
                cli_args=None,
                db_path=None,
                input_files_json=json.dumps({"output": PATHS[index]}),
                input_hashes_json="{}",
                total_students=1,
                total_allocated=1 if index == 0 else 0,
                total_unallocated=index,
                history_metrics_json=None,
                qa_summary_json=json.dumps({"passed": index == 1, "violation_count": 2 - index}),
                status="success" if index == 0 else "failed",
                message=f"Synthetic {tag} run",
            )
        )
        db.insert_trace_snapshot(
            run_id=run_id,
            trace_df=pd.DataFrame({"student_id": [f"synthetic-{tag}"], "stage": ["type"]}),
        )
        db.insert_qa_snapshot(
            run_id=run_id,
            qa_summary_df=pd.DataFrame({"rule_id": [f"QA-{tag}"], "status": ["FAIL"]}),
            qa_details_df=pd.DataFrame({"student_id": [f"synthetic-{tag}"]}),
            qa_extras={"synthetic": pd.DataFrame({"item": [f"extra-{tag}"]})},
        )
        db.insert_run_metrics(
            [RunMetricRow(run_id=run_id, metric_key=f"{tag}.count", metric_value=1.0)]
        )
        ids.append(run_id)
    return ids[0], ids[1]


def _check(report: dict[str, object], name: str, condition: bool) -> None:
    checks = report["checks"]
    assert isinstance(checks, list)
    checks.append({"check": name, "result": "PASS" if condition else "FAIL"})
    if not condition:
        raise AssertionError(name)


def _capture(
    app: QApplication,
    dialog: HistoryDialog,
    output_dir: Path,
    name: str,
    report: dict[str, object],
) -> None:
    app.processEvents()
    pixmap = dialog.grab()
    image = pixmap.toImage()
    _check(report, f"{name}: non-null screenshot", not image.isNull())
    file = output_dir / f"{name}.png"
    _check(report, f"{name}: image saved", image.save(str(file), "PNG"))
    pixel_colors = {
        image.pixelColor(x, y).rgb()
        for x in range(0, image.width(), max(1, image.width() // 24))
        for y in range(0, image.height(), max(1, image.height() // 18))
    }
    _check(report, f"{name}: nonuniform actual pixels", len(pixel_colors) > 2)
    _check(report, f"{name}: nontrivial image", file.stat().st_size > 2000)
    images = report["images"]
    assert isinstance(images, list)
    images.append(
        {
            "scenario": name,
            "file": file.name,
            "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
            "width_px": image.width(),
            "height_px": image.height(),
            "device_pixel_ratio": pixmap.devicePixelRatio(),
        }
    )


def _select(app: QApplication, dialog: HistoryDialog, row: int) -> None:
    dialog._run_list.setCurrentRow(row)
    app.processEvents()


def _case(
    app: QApplication,
    root: Path,
    output_dir: Path,
    language: str,
    theme: str,
    dpi: str,
    report: dict[str, object],
) -> None:
    mode = f"{language}-{theme}-{dpi}"
    apply_theme(app, theme)
    apply_layout_direction(app, language)
    translator = UiTranslator(language)
    db = LocalDatabase(root / f"{mode}.sqlite")
    run_a, run_b = _seed(db)
    errors: list[Exception] = []
    dialog = HistoryDialog(db, translator=translator, on_selection_error=errors.append)
    try:
        dialog.resize(1024, 700)
        dialog.show()
        app.processEvents()
        expected_direction = (
            Qt.LayoutDirection.RightToLeft
            if language == "fa"
            else Qt.LayoutDirection.LeftToRight
        )
        _check(report, f"{mode}: direction", dialog.layoutDirection() == expected_direction)
        _check(report, f"{mode}: theme active", bool(app.styleSheet()))
        _check(report, f"{mode}: title localized", dialog.windowTitle() == translator.text(
            "history.dossier.title", "Run Review Dossier"
        ))
        scroll = dialog.findChild(QScrollArea)
        _check(report, f"{mode}: dossier scroll container", scroll is not None)
        assert scroll is not None
        _check(report, f"{mode}: scroll layout", scroll.widgetResizable())
        _check(report, f"{mode}: nonzero list and dossier width", (
            dialog._run_list.width() > 100 and scroll.viewport().width() > 100
        ))
        dpr = dialog.devicePixelRatioF()
        _check(report, f"{mode}: effective DPI scale", (
            dpr >= 1.5 if dpi == "high" else 0.9 <= dpr < 1.5
        ))
        note = dialog._path_note.text()
        _check(report, f"{mode}: path authenticity disclosure", (
            "اصالت" in note if language == "fa" else "not verification" in note
        ))
        _check(report, f"{mode}: warning visible", dialog._path_note.isVisible())
        _check(report, f"{mode}: run B selected", dialog._selected_run_id == run_b)
        _check(report, f"{mode}: B execution failed", (
            translator.text("history.dossier.execution_failure", "Recorded failure")
            in dialog._outcome_label.text()
        ))
        _check(report, f"{mode}: B QA independently passed", (
            translator.text("history.dossier.qa_pass", "Passed")
            in dialog._qa_outcome_label.text()
        ))
        _check(report, f"{mode}: B output path", dialog._output_path_edit.text() == PATHS[1])
        _capture(app, dialog, output_dir, f"{mode}-run-b-failed-qa-passed", report)

        dialog._run_list.setFocus()
        QTest.keyClick(dialog._run_list, Qt.Key.Key_Up)
        app.processEvents()
        _check(report, f"{mode}: keyboard selection A", dialog._selected_run_id == run_a)
        _check(report, f"{mode}: A execution succeeded", (
            translator.text("history.dossier.execution_success", "Recorded success")
            in dialog._outcome_label.text()
        ))
        _check(report, f"{mode}: A QA independently failed", (
            translator.text("history.dossier.qa_fail", "Failed")
            in dialog._qa_outcome_label.text()
        ))
        _check(report, f"{mode}: A trace isolation", (
            str(dialog.trace_model.data(dialog.trace_model.index(0, 0))) == "synthetic-A"
        ))
        _check(report, f"{mode}: A output path", dialog._output_path_edit.text() == PATHS[0])
        _check(report, f"{mode}: Copy available", dialog._copy_path_button.isEnabled())
        dialog._copy_path_button.click()
        _check(report, f"{mode}: Copy exact A path", app.clipboard().text() == PATHS[0])
        dialog._retry_button.setFocus()
        QTest.keyClick(dialog._retry_button, Qt.Key.Key_Space)
        app.processEvents()
        _check(report, f"{mode}: keyboard Retry retains A", dialog._selected_run_id == run_a)
        _check(report, f"{mode}: Retry does not mix B", dialog._output_path_edit.text() == PATHS[0])
        _capture(app, dialog, output_dir, f"{mode}-run-a-success-qa-failed", report)

        if language == "en" and theme == "light":
            _edge_cases(app, dialog, db, run_a, run_b, scroll, output_dir, mode, report)
        expected_errors = 2 if language == "en" and theme == "light" else 0
        _check(report, f"{mode}: expected error count", len(errors) == expected_errors)
    finally:
        dialog.close()
        app.processEvents()
        db.close_all_connections()


def _edge_cases(
    app: QApplication,
    dialog: HistoryDialog,
    db: LocalDatabase,
    run_a: int,
    run_b: int,
    scroll: QScrollArea,
    output_dir: Path,
    mode: str,
    report: dict[str, object],
) -> None:
    long_text = ("Synthetic history evidence: long Unicode text فارسی 123 ABC. " * 110)
    with sqlite3.connect(db.path) as conn:
        conn.execute("UPDATE runs SET message = ? WHERE id = ?", (long_text, run_a))
        conn.commit()
    dialog.resize(760, 460)
    dialog._retry_button.click()
    app.processEvents()
    bar = scroll.verticalScrollBar()
    _check(report, f"{mode}: long text rendered", len(dialog._outcome_label.text()) > 1000)
    _check(report, f"{mode}: scroll reachable", bar.maximum() > 0)
    bar.setValue(bar.maximum())
    app.processEvents()
    _check(report, f"{mode}: scroll to end", bar.value() == bar.maximum())
    _capture(app, dialog, output_dir, f"{mode}-long-text-scrolled", report)
    with sqlite3.connect(db.path) as conn:
        conn.execute("UPDATE runs SET message = NULL WHERE id = ?", (run_a,))
        conn.execute("DELETE FROM trace_snapshots WHERE run_id = ?", (run_b,))
        conn.execute("DELETE FROM qa_snapshots WHERE run_id = ?", (run_b,))
        conn.commit()
    dialog.resize(1024, 700)
    _select(app, dialog, 1)
    _check(report, f"{mode}: missing trace", dialog._trace_empty.text() == "Not recorded")
    _check(report, f"{mode}: missing QA", dialog._qa_summary_empty.text() == "Not recorded")
    _check(report, f"{mode}: no previous run trace", dialog.trace_model.rowCount() == 0)
    _capture(app, dialog, output_dir, f"{mode}-missing-snapshots", report)

    db.insert_trace_snapshot(run_id=run_b, trace_df=pd.DataFrame())
    db.insert_qa_snapshot(
        run_id=run_b, qa_summary_df=pd.DataFrame(), qa_details_df=pd.DataFrame()
    )
    dialog._retry_button.click()
    app.processEvents()
    _check(report, f"{mode}: recorded empty trace", (
        dialog._trace_empty.text() == "Recorded, but empty"
    ))
    _check(report, f"{mode}: recorded empty QA", (
        dialog._qa_summary_empty.text() == "Recorded, but empty"
    ))
    _capture(app, dialog, output_dir, f"{mode}-recorded-empty", report)

    with sqlite3.connect(db.path) as conn:
        conn.execute(
            "UPDATE runs SET input_files_json = ?, qa_summary_json = ? WHERE id = ?",
            ("{broken-reference", "{broken-qa", run_b),
        )
        conn.commit()
    dialog._retry_button.click()
    app.processEvents()
    _check(report, f"{mode}: unreadable copy disabled", (
        not dialog._copy_path_button.isEnabled() and not dialog._output_path_edit.text()
    ))
    _check(report, f"{mode}: invalid QA disclosed", (
        "Unreadable recorded data" in dialog._qa_outcome_label.text()
    ))
    _capture(app, dialog, output_dir, f"{mode}-unreadable-metadata", report)

    with sqlite3.connect(db.path) as conn:
        old_snapshot = conn.execute(
            "SELECT qa_summary_json FROM qa_snapshots WHERE run_id = ?", (run_b,)
        ).fetchone()[0]
        conn.execute(
            "UPDATE qa_snapshots SET qa_summary_json = ? WHERE run_id = ?",
            ("{corrupt-snapshot", run_b),
        )
        conn.commit()
    dialog._retry_button.click()
    app.processEvents()
    _check(report, f"{mode}: corrupt snapshot revokes selection", (
        dialog._selected_run_id is None
        and dialog.trace_model.rowCount() == 0
        and not dialog._copy_path_button.isEnabled()
    ))
    _check(report, f"{mode}: corrupt error disclosed", (
        "unreadable" in dialog._identity_label.text()
    ))
    _capture(app, dialog, output_dir, f"{mode}-corrupt-snapshot", report)
    with sqlite3.connect(db.path) as conn:
        conn.execute(
            "UPDATE qa_snapshots SET qa_summary_json = ? WHERE run_id = ?",
            (old_snapshot, run_b),
        )
        conn.execute(
            "UPDATE runs SET input_files_json = ?, qa_summary_json = ? WHERE id = ?",
            (json.dumps({"output": PATHS[1]}), json.dumps({"passed": True}), run_b),
        )
        conn.commit()
    dialog._retry_button.click()
    app.processEvents()
    _check(report, f"{mode}: recovery B", (
        dialog._selected_run_id == run_b and dialog._output_path_edit.text() == PATHS[1]
    ))
    _capture(app, dialog, output_dir, f"{mode}-recovered-after-corruption", report)

    _select(app, dialog, 0)
    _check(report, f"{mode}: pre-error A path", dialog._recorded_output_path == PATHS[0])
    with patch.object(
        db, "fetch_run_by_id", side_effect=sqlite3.OperationalError("synthetic transient error")
    ):
        _select(app, dialog, 1)
    _check(report, f"{mode}: transient read revokes A", (
        dialog._recorded_output_path is None
        and dialog._selected_run_id is None
        and not dialog._copy_path_button.isEnabled()
        and dialog.trace_model.rowCount() == 0
    ))
    _capture(app, dialog, output_dir, f"{mode}-transient-read-error", report)
    dialog._retry_button.click()
    app.processEvents()
    _check(report, f"{mode}: transient retry B path only", (
        dialog._selected_run_id == run_b
        and dialog._output_path_edit.text() == PATHS[1]
        and dialog._copy_path_button.isEnabled()
    ))
    dialog._copy_path_button.click()
    _check(report, f"{mode}: recovered clipboard B", app.clipboard().text() == PATHS[1])
    _capture(app, dialog, output_dir, f"{mode}-transient-retried", report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dpi", choices=("standard", "high"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("MatrixDossierCI")
    app.setOrganizationName("MatrixSyntheticEvidence")
    screen = app.primaryScreen()
    report: dict[str, object] = {
        "head": _head(),
        "environment": {
            "platform": platform.platform(),
            "python": sys.version,
            "pyside6": pyside_version,
            "qt_platform": app.platformName(),
            "qt_scale_factor_requested": os.environ.get("QT_SCALE_FACTOR"),
            "dpi_mode": args.dpi,
            "screen_dpr": screen.devicePixelRatio() if screen else None,
            "render_mode": "Windows Qt offscreen widget rendering; NOT interactive operator desktop",
            "data": "isolated synthetic SQLite only",
        },
        "checks": [],
        "images": [],
        "status": "NOT_RUN",
    }
    try:
        _check(report, "Windows runner", sys.platform == "win32")
        _check(report, "Qt offscreen", app.platformName() == "offscreen")
        with tempfile.TemporaryDirectory(prefix="matrix-dossier-synthetic-") as tmp:
            for theme in ("light", "dark"):
                for language in ("fa", "en"):
                    _case(app, Path(tmp), output_dir, language, theme, args.dpi, report)
        report["status"] = "PASS"
        return 0
    except Exception as exc:
        report["status"] = "FAIL"
        report["failure"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        (output_dir / "manifest.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps({
            "head": report["head"],
            "dpi": args.dpi,
            "result": report["status"],
            "checks": len(report["checks"]),
            "images": len(report["images"]),
        }, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())

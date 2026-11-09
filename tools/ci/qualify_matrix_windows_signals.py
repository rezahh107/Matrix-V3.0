"""Windows-only, test-only observation of Matrix operator signals (A/B/C).

No allocation, real profiles, or production code modifications. Diagnostic PASS
means the observation is attributable, NOT that the product is safe.
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
import traceback
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch


def _run_record(run_uuid: str, status: str = "success"):
    from app.infra.local_database import RunRecord

    now = datetime.now(UTC)
    return RunRecord(
        run_uuid=run_uuid,
        started_at=now,
        finished_at=now,
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
        qa_summary_json=None,
        status=status,
        message=None,
    )


def _sqlite_state(path: Path) -> dict:
    """Logical snapshot and auxiliary-file evidence; never create a missing DB."""
    files = {}
    for suffix in ("", "-wal", "-shm", "-journal"):
        item = Path(str(path) + suffix)
        files[suffix or "main"] = {
            "exists": item.is_file(),
            "bytes": item.stat().st_size if item.is_file() else None,
            "sha256": hashlib.sha256(item.read_bytes()).hexdigest() if item.is_file() else None,
        }
    result = {"files": files, "tables": {}, "schema": [], "user_version": None}
    if not path.is_file():
        return result
    conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        result["user_version"] = conn.execute("PRAGMA user_version").fetchone()[0]
        result["schema"] = sorted(
            (name, sql) for name, sql in conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type IN ('table', 'index', 'trigger', 'view')"
            ) if name is not None
        )
        for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ):
            safe_name = '"' + name.replace('"', '""') + '"'
            rows = conn.execute("SELECT * FROM " + safe_name).fetchall()
            result["tables"][name] = {
                "count": len(rows),
                "digest": hashlib.sha256(repr(rows).encode("utf-8")).hexdigest(),
            }
    finally:
        conn.close()
    return result


def _logical(state: dict) -> dict:
    return {key: state[key] for key in ("schema", "tables", "user_version")}


def _reference_case(path: Path, prepare: str) -> dict:
    from app.infra.db import compute_reference_readiness
    from app.infra.groupcode.groupcode_repository import GroupCodeRepository
    from app.infra.local_database import LocalDatabase
    from app.infra.schools.school_repository import SchoolRepository

    with LocalDatabase(path) as db:
        if prepare in {"initialized", "missing-groupcodes"}:
            db.initialize()
        if prepare == "missing-groupcodes":
            with db.connect() as conn:
                conn.execute("DELETE FROM groupcodes")
                conn.commit()
        db.close_all_connections()
        before = _sqlite_state(path)
        ready = None
        error = None
        try:
            ready = compute_reference_readiness(
                school_repo=SchoolRepository(db),
                groupcode_repo=GroupCodeRepository(db),
            )
        except sqlite3.Error as exc:
            # A fresh SQLite connection may create an empty file even when
            # the missing reference_meta table prevents readiness evaluation.
            error = {"type": type(exc).__name__, "message": str(exc)}
        finally:
            db.close_all_connections()
        after = _sqlite_state(path)
    changed = _logical(before) != _logical(after)
    created_file = not before["files"]["main"]["exists"] and after["files"]["main"]["exists"]
    verdict = (
        "PERSISTENT_MUTATION_OBSERVED" if changed or created_file
        else ("INCONCLUSIVE" if error else "NO_MUTATION_OBSERVED")
    )
    return {
        "setup": prepare,
        "readiness": None if ready is None else {
            "schools_count": ready.schools.row_count,
            "groupcodes_count": ready.groupcodes.row_count,
            "ready": ready.is_ready_for_run,
        },
        "error": error,
        "before": before,
        "after": after,
        "logical_change": changed,
        "created_persistent_database_file": created_file,
        "verdict": verdict,
        "safety_property": "Readiness inspection must not persistently alter references",
        "limit": "Synthetic isolated SQLite; auxiliary WAL/file-byte changes alone do not prove logical mutation",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    target = args.output_dir.resolve()
    target.mkdir(parents=True, exist_ok=True)

    # Setup MUST precede Qt application, preferences, and MainWindow creation.
    with tempfile.TemporaryDirectory(prefix="matrix-windows-signals-") as td:
        profile = Path(td)
        for sub in ("home", "appdata", "localappdata", "qt", "tmp", "output"):
            (profile / sub).mkdir()
        environment = {
            "HOME": str(profile / "home"),
            "USERPROFILE": str(profile / "home"),
            "APPDATA": str(profile / "appdata"),
            "LOCALAPPDATA": str(profile / "localappdata"),
            "XDG_CONFIG_HOME": str(profile / "qt"),
            "XDG_DATA_HOME": str(profile / "localappdata"),
            "TMP": str(profile / "tmp"),
            "TEMP": str(profile / "tmp"),
            "MATRIX_OUTPUT_ROOT": str(profile / "output"),
            "QT_QPA_PLATFORM": "offscreen",
        }
        with patch.dict(os.environ, environment), patch.object(
            Path, "home", return_value=profile / "home"
        ):
            from PySide6 import __version__ as pyside_version
            from PySide6.QtCore import QCoreApplication, QSettings
            from PySide6.QtWidgets import QApplication

            QCoreApplication.setOrganizationName("MatrixSyntheticQualification")
            QCoreApplication.setApplicationName("MatrixSyntheticQualification")
            QSettings.setDefaultFormat(QSettings.Format.IniFormat)
            QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(profile / "qt"))
            QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.SystemScope, str(profile / "qt"))
            app = QApplication.instance() or QApplication([])

            expected_sha = os.environ.get("MATRIX_EXPECTED_SOURCE_SHA", "")
            actual_sha = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip()
            assert expected_sha and actual_sha == expected_sha, (
                f"checkout mismatch: expected {expected_sha}, actual {actual_sha}"
            )
            results: dict[str, dict] = {}
            failures: list[str] = []
            context: dict = {}
            environment_evidence = {
                "platform": platform.platform(),
                "windows": platform.system() == "Windows",
                "python": sys.version.split()[0],
                "pyside6": pyside_version,
                "qt_platform": app.platformName(),
                "source_sha": actual_sha,
                "qsettings_format": "IniFormat",
                "profile_isolation": True,
                "synthetic_only": True,
            }

            def run(name: str, func):
                try:
                    observed = func()
                    assert isinstance(observed, dict) and "verdict" in observed
                    results[name] = observed
                except Exception as exc:
                    failures.append(name)
                    results[name] = {
                        "verdict": "INCONCLUSIVE",
                        "error_type": type(exc).__name__,
                        "error": str(exc)[:600],
                        "traceback": traceback.format_exc(limit=4)[-1600:],
                    }

            from app.core.counter import year_to_yy
            from app.infra.health import compute_run_health
            from app.infra.local_database import LocalDatabase, QaSummaryRow
            from app.ui.i18n import Language
            from app.ui.texts import UiTranslator
            from app.ui.widgets.health_indicator import HealthCallbacks, HealthIndicatorWidget

            # B1 before A3: establish untouched UI control before any programmatic selection.
            def b1():
                from app.ui.main_window import MainWindow

                window = MainWindow()
                window.show()
                app.processEvents()
                combo = window.findChild(__import__("PySide6.QtWidgets", fromlist=["QComboBox"]).QComboBox, "academicYearInput")
                assert combo is not None, "Real academicYearInput not found"
                context["window"] = window
                context["initial_year"] = combo.currentText()
                context["initial_index"] = combo.currentIndex()
                assert combo.count() > 0
                image_path = target / "academic-year-initial.png"
                assert window.grab().save(str(image_path)), "Qt screenshot save failed"
                return {
                    "verdict": "INITIAL_1395_OBSERVED" if combo.currentText() == "1395" else "INITIAL_1395_NOT_OBSERVED",
                    "current_index": combo.currentIndex(),
                    "current_text": combo.currentText(),
                    "items": [combo.itemText(i) for i in range(combo.count())],
                    "operator_selection": False,
                    "safety_property": "Consequential year must reflect deliberate choice",
                    "artifact": image_path.name,
                }
            run("B1", b1)

            def b2():
                window = context["window"]
                combo = window._combo_academic_year
                before = combo.currentText()
                window._apply_language(Language.FA)
                app.processEvents()
                fa = combo.currentText()
                window._apply_language(Language.EN)
                app.processEvents()
                en = combo.currentText()
                assert before == fa == en, "Locale changed an untouched academic-year value"
                return {
                    "verdict": "YEAR_STABLE_ACROSS_LOCALES",
                    "before": before, "fa": fa, "en": en,
                    "safety_property": "Locale switch must not rewrite year",
                }
            run("B2", b2)

            def b3():
                window = context["window"]
                year = window._get_academic_year()
                overrides = window._build_allocate_overrides()
                assert year == int(context["initial_year"])
                assert overrides.get("academic_year") == year
                return {
                    "verdict": "UNTOUCHED_YEAR_PROPAGATED",
                    "year": year,
                    "academic_year_override": overrides.get("academic_year"),
                    "method": "Real MainWindow override builder; allocation not executed",
                    "safety_property": "Year propagation must be deliberate and visible",
                }
            run("B3", b3)

            def b4():
                window = context["window"]
                combo = window._combo_academic_year
                items = []
                for text in ("1299", "1300", "1349", "1350", "1449", "1450", "1500", "1501", "garbage"):
                    combo.setEditText(text)
                    accepted = window._get_academic_year()
                    try:
                        counter = year_to_yy(int(text))
                        counter_valid = True
                    except (ValueError, TypeError):
                        counter_valid = False
                        counter = None
                    items.append({
                        "input": text, "ui_accepted": accepted is not None,
                        "counter_valid": counter_valid, "counter_yy": counter,
                    })
                combo.setEditText(context["initial_year"])
                app.processEvents()
                return {
                    "verdict": "BOUNDARY_MISMATCH_OBSERVED" if any(
                        i["ui_accepted"] and not i["counter_valid"] for i in items
                    ) else "NO_BOUNDARY_MISMATCH_OBSERVED",
                    "cases": items,
                    "safety_property": "Year UI validation must not admit a counter-invalid value",
                }
            run("B4", b4)

            def a1():
                with LocalDatabase(profile / "missing-run.db") as db:
                    db.initialize()
                    h = compute_run_health("synthetic-run-does-not-exist", db=db)
                window = context.get("window")
                empty = window._fetch_health_summary() if window else None
                text = window._health_widget._status_label.text() if window else None
                if window is not None:
                    assert empty is None and window._health_widget._current_summary is None
                return {
                    "verdict": "FALSE_ASSURANCE_REPRODUCED" if h.status == "OK" else "FALSE_ASSURANCE_NOT_REPRODUCED",
                    "missing_run_status": h.status, "missing_run_text": h.summary_text,
                    "missing_run_counts": h.counts, "no_stored_run_summary": repr(empty),
                    "no_stored_run_visible_text": text,
                    "safety_property": "Nonexistent run must not be certified safe",
                    "limit": "No-run MainWindow observation only if B1 succeeded",
                }
            run("A1", a1)

            def a2():
                db = LocalDatabase(profile / "qa-no-snapshot.db")
                db.initialize()
                ident = db.insert_run(_run_record("synthetic-without-qa"))
                summary = compute_run_health(str(ident), db=db)
                context["a2_db"] = db
                assert summary.counts == {"P0": 0, "P1": 0, "P2": 0}
                return {
                    "verdict": "FALSE_ASSURANCE_REPRODUCED" if summary.status == "OK" else "FALSE_ASSURANCE_NOT_REPRODUCED",
                    "run_id": ident, "status": summary.status, "counts": summary.counts,
                    "text": summary.summary_text,
                    "qa_snapshot": "absent", "safety_property": "Missing QA must not imply PASS",
                }
            run("A2", a2)

            def a3():
                db = context["a2_db"]
                ident = db.fetch_runs()[-1]["id"]
                h = compute_run_health(str(ident), db=db)
                component = {}
                for language in ("en", "fa"):
                    widget = HealthIndicatorWidget(
                        HealthCallbacks(
                            fetch_summary=lambda: compute_run_health(str(ident), db=db),
                            export_report=lambda: None,
                        ),
                        translator=UiTranslator(language),
                    )
                    widget.show()
                    app.processEvents()
                    label = widget._status_label.text()
                    screenshot = target / f"qa-health-{language}.png"
                    assert widget.grab().save(str(screenshot))
                    component[language] = {"visible_text": label, "health_qss": widget._status_label.property("health"), "artifact": screenshot.name}
                    widget.close()
                assert all(value["health_qss"] == "ok" for value in component.values()) == (h.status == "OK")
                full = {"status": "NOT_PROVEN", "reason": "B1 MainWindow construction unavailable"}
                if "window" in context:
                    window = context["window"]
                    own_db = window._local_db
                    assert own_db is not None, "MainWindow did not open isolated local DB"
                    own_db.insert_run(_run_record("synthetic-window-without-qa"))
                    window._refresh_health_widget()
                    app.processEvents()
                    full = {
                        "status": "OBSERVED",
                        "callback_status": window._fetch_health_summary().status,
                        "visible_text": window._health_widget._status_label.text(),
                        "health_qss": window._health_widget._status_label.property("health"),
                    }
                    assert full["callback_status"] == h.status
                return {
                    "verdict": "FALSE_ASSURANCE_REPRODUCED" if h.status == "OK" else "FALSE_ASSURANCE_NOT_REPRODUCED",
                    "component": component, "full_main_window": full,
                    "safety_property": "Actual Qt signal must be backed by authoritative QA",
                }
            run("A3", a3)

            def a4():
                import pandas as pd

                db = context["a2_db"]
                outcomes = {}
                for label, state in (
                    ("qa_pass", "pass"), ("qa_fail_details_p0", "p0"),
                    ("qa_fail_summary_p1", "p1"), ("unreadable_snapshot", "unreadable"),
                    ("failed_run_without_qa", "failed"), ("separate_qa_outcome", "separate"),
                ):
                    run_id = db.insert_run(_run_record("synthetic-" + label, status="failed" if state == "failed" else "success"))
                    if state == "pass":
                        db.insert_qa_snapshot(
                            run_id=run_id,
                            qa_summary_df=pd.DataFrame([{"rule_id": "QA_SAMPLE", "status": "PASS", "violations_count": 0}]),
                            qa_details_df=None,
                        )
                    elif state == "p0":
                        db.insert_qa_snapshot(
                            run_id=run_id, qa_summary_df=None,
                            qa_details_df=pd.DataFrame([{"rule_id": "QA_SAMPLE", "level": "error"}]),
                        )
                    elif state == "p1":
                        db.insert_qa_snapshot(
                            run_id=run_id, qa_summary_df=pd.DataFrame([{"rule_id": "QA_SAMPLE", "status": "FAIL", "violations_count": 2}]),
                            qa_details_df=None,
                        )
                    elif state == "unreadable":
                        with db.connect() as conn:
                            conn.execute(
                                "INSERT INTO qa_snapshots (run_id, qa_summary_json, qa_details_json, qa_extras_json) VALUES (?, ?, ?, ?)",
                                (run_id, "{invalid-json", None, None),
                            )
                            conn.commit()
                    elif state == "separate":
                        db.insert_qa_summary([QaSummaryRow(run_id=run_id, violation_code="QA_SAMPLE", severity="P0", count=1)])
                    health = compute_run_health(str(run_id), db=db)
                    outcomes[label] = {"status": health.status, "counts": health.counts, "text": health.summary_text}
                assert outcomes["qa_fail_details_p0"]["status"] == "ERROR"
                assert outcomes["qa_fail_summary_p1"]["status"] == "WARN"
                return {
                    "verdict": "CONTRASTS_OBSERVED",
                    "cases": outcomes,
                    "safety_property": "Positive QA evidence and failed/absent/corrupt QA must remain distinguishable",
                    "limit": "Unreadable snapshot tested through existing non-strict deserialization",
                }
            run("A4", a4)

            for name, state in (
                ("C1", "fresh"),
                ("C2", "initialized"),
                ("C3", "missing-groupcodes"),
            ):
                run(name, lambda state=state, name=name: _reference_case(profile / (name + ".db"), state))

            for db_name in ("a2_db",):
                if db_name in context:
                    context[db_name].close_all_connections()
            if "window" in context:
                window = context["window"]
                window.close()
                if window._local_db is not None:
                    window._local_db.close_all_connections()
                app.processEvents()

            # Keep only evidence, never fixture DBs, in the artifacts.
            verdicts = {k: v["verdict"] for k, v in results.items()}
            all_cases = [f"A{i}" for i in range(1, 5)] + [f"B{i}" for i in range(1, 5)] + [f"C{i}" for i in range(1, 4)]
            missing = [name for name in all_cases if name not in results]
            inconclusive = [name for name, v in results.items() if v["verdict"] == "INCONCLUSIVE"]
            failures.extend(missing)
            report = {
                "brief_reference": "SCE-MATRIX-WINDOWS-QUALIFICATION-001",
                "source_sha": actual_sha,
                "environment": environment_evidence,
                "scenarios": results,
                "verdicts": verdicts,
                "qualification_complete": not failures,
                "named_gaps": sorted(set(failures)),
                "notes": [
                    "A diagnostic test can succeed while exposing an unsafe product behavior.",
                    "Offscreen Windows Qt cannot prove physical monitor, accessibility, or operator acceptance.",
                    "Only synthetic local fixtures were used; no allocation was executed.",
                ],
            }
            (target / "qualification-results.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            (target / "environment.json").write_text(
                json.dumps(environment_evidence, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            (target / "sqlite-before-after.json").write_text(
                json.dumps({n: results.get(n) for n in ("C1", "C2", "C3")}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (target / "test-results.txt").write_text(
                "\n".join(f"{name}: {verdicts.get(name, 'NOT_EXECUTED')}" for name in all_cases)
                + "\n", encoding="utf-8"
            )
            print(json.dumps({"source_sha": actual_sha, "verdicts": verdicts, "gaps": report["named_gaps"]}, ensure_ascii=False))
            return 1 if failures or platform.system() != "Windows" else 0


if __name__ == "__main__":
    sys.exit(main())

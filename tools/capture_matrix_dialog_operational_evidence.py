"""Verification-only captures of Matrix live dialogs and operational UI states.

Run with QT_QPA_PLATFORM=offscreen using the locked project environment.
All data are synthetic; allocation/build CLI and persistence writes are not invoked.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import tempfile
import threading
import time
import traceback
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
from PySide6.QtCore import QPoint, QRect, QSettings, Qt, qVersion
from PySide6.QtGui import QFontMetrics, QImage, QPainter
from PySide6.QtWidgets import (
    QApplication, QDialog, QLabel, QMessageBox, QPushButton, QScrollArea,
    QTabWidget, QTableView, QTextBrowser, QWidget,
)

from app.core.allocation.history_metrics import METRIC_COLUMNS
from app.infra.config_flags import UserSettings
from app.ui.i18n import Language
from app.ui.main_window import MainWindow
from app.ui.preferences.diagnostics_catalog import CAPABILITIES, CATEGORY_ORDER, CAPABILITY_BY_KEY
from app.ui.preferences.settings_dialog import DiagnosticsGuideDialog, UnifiedSettingsDialog
from app.ui.theme import apply_theme, build_theme

BASE_SHA = "782d178f5dc539bc078e04a1e67a10ad6ea5baa4"
SIZES = ((720, 760), (620, 560))
LANGUAGES = (Language.FA, Language.EN)
THEMES = ("light", "dark")


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def configure_settings(folder: Path) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    for scope in (QSettings.Scope.UserScope, QSettings.Scope.SystemScope):
        QSettings.setPath(QSettings.Format.IniFormat, scope, str(folder))


def rect_record(widget: QWidget, parent: QWidget) -> dict[str, object]:
    origin = widget.mapTo(parent, QPoint(0, 0))
    rect = QRect(origin, widget.size())
    return {
        "x": rect.x(), "y": rect.y(), "width": rect.width(), "height": rect.height(),
        "contained": parent.rect().contains(rect),
        "visible": widget.isVisible(),
    }


class Collector:
    def __init__(self, output: Path, app: QApplication) -> None:
        self.output = output
        self.app = app
        self.cases: list[dict[str, object]] = []
        self.failures: list[dict[str, str]] = []
        self.head = git_head()
        self.output.mkdir(parents=True, exist_ok=True)

    def environment(self, widget: QWidget, theme: str, language: Language) -> dict[str, object]:
        screen = widget.screen() or self.app.primaryScreen()
        return {
            "source_base_sha": BASE_SHA,
            "captured_head_sha": self.head,
            "os": platform.platform(),
            "python": platform.python_version(),
            "pyside6": __import__("PySide6").__version__,
            "qt": qVersion(),
            "qpa_plugin": self.app.platformName(),
            "qstyle": self.app.style().objectName(),
            "font_family": widget.font().family(),
            "font_point_size": widget.font().pointSizeF(),
            "application_font": self.app.font().family(),
            "layout_direction": "rtl" if self.app.layoutDirection() == Qt.LayoutDirection.RightToLeft else "ltr",
            "widget_direction": "rtl" if widget.layoutDirection() == Qt.LayoutDirection.RightToLeft else "ltr",
            "theme": theme, "language": language.code,
            "window_size": [widget.width(), widget.height()],
            "dpr": widget.devicePixelRatioF(),
            "screen_dpr": screen.devicePixelRatio() if screen is not None else None,
            "screen_logical_dpi": screen.logicalDotsPerInch() if screen is not None else None,
            "qt_scale_factor": os.getenv("QT_SCALE_FACTOR"),
            "qt_auto_screen_scale_factor": os.getenv("QT_AUTO_SCREEN_SCALE_FACTOR"),
        }

    def capture(self, widget: QWidget, name: str, family: str, theme: str,
                language: Language, **details: object) -> None:
        self.app.processEvents()
        file = self.output / (name + ".png")
        pix = widget.grab()
        if pix.isNull() or not pix.save(str(file), "PNG") or file.stat().st_size == 0:
            raise RuntimeError("PNG capture failed: " + name)
        self.cases.append({
            "case": name, "family": family, "image": file.name,
            "image_pixels": [pix.width(), pix.height()],
            **self.environment(widget, theme, language), **details,
        })

    def try_case(self, name: str, callback: object) -> None:
        try:
            callback()
        except Exception as exc:
            self.failures.append({
                "case": name, "error_type": type(exc).__name__,
                "error": str(exc), "traceback": traceback.format_exc(),
            })

    def save(self) -> None:
        (self.output / "manifest.json").write_text(
            json.dumps({
                "status": "partial_or_failed" if self.failures else "captures_recorded_not_usability_approved",
                "source_base_sha": BASE_SHA, "captured_head_sha": self.head,
                "capture_count": len(self.cases), "failure_count": len(self.failures),
                "cases": self.cases, "failures": self.failures,
                "evidence_limits": [
                    "Offscreen QWidget.grab and programmatic focus are not real Windows desktop acceptance.",
                    "Synthetic Worker events prove UI lifecycle only; no allocation, persistence or CLI execution.",
                    "Visual usability and bilingual semantic quality require review of original PNGs.",
                    "Long-text controls are intentionally non-production mutations.",
                    "Stored-run HistoryMetricsDialog is not treated as reachable without a live entrypoint.",
                ],
            }, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        summaries = [
            "# Matrix dialogs and operational state evidence",
            "",
            "Base (production) commit: " + BASE_SHA,
            "Captured branch commit: " + self.head,
            "Captured PNGs: " + str(len(self.cases)),
            "Failed scenarios: " + str(len(self.failures)),
            "",
            "## Boundaries",
            "Verification-only; no production UI/Core/Infra/persistence changes. "
            "All running/failure/completion scenarios use a synthetic Worker.",
            "A captured PNG is evidence, not an automatic visual acceptance.",
            "",
            "## Runtime cases",
        ]
        for case in self.cases:
            summaries.append("- " + str(case["case"]) + ": " + str(case["image"]))
        summaries.extend(["", "## Failures (not PASS)"])
        if not self.failures:
            summaries.append("- No harness exceptions; visual/interaction acceptance remains manual.")
        for failure in self.failures:
            summaries.append("- " + failure["case"] + ": " + failure["error_type"] + " — " + failure["error"])
        summaries.extend([
            "", "## Static inspection hypotheses to verify in PNG",
            "- Main toolbar actionHistoryMetrics opens app.ui.history_metrics.HistoryMetricsDialog "
            "(current-run metrics), not app.ui.history_metrics_dialog.HistoryMetricsDialog (stored runs).",
            "- HistoryMetricsPanel empty copy and METRIC_COLUMNS headers appear hard-coded in English.",
            "- Settings has three nested diagnostic category groups; inspect visual density at 620x560.",
            "- Indeterminate progress initially has a 0% caption; inspect whether this communicates uncertainty.",
            "- Explain sample must be reviewed for clipped/ambiguous columns; no redesign authorized.",
            "",
            "## Remaining acceptance",
            "- Review full-resolution screenshots and negative-control crops; inspect keyboard navigation with real input.",
            "- Repeat core focus, scroll, window-manager chrome, Windows font fallback and DPR "
            "on real Windows 10/11, not solely offscreen CI.",
        ])
        (self.output / "SUMMARY.md").write_text("\n".join(summaries) + "\n", encoding="utf-8")
        self.contact_sheets()

    def contact_sheets(self) -> None:
        for family in ("settings", "guide", "history", "operation", "explain"):
            members = [c for c in self.cases if c["family"] == family]
            if not members:
                continue
            tile_w, tile_h, columns = 320, 240, 3
            rows = (len(members) + columns - 1) // columns
            sheet = QImage(columns * tile_w, rows * tile_h, QImage.Format.Format_RGB32)
            sheet.fill(Qt.GlobalColor.white)
            painter = QPainter(sheet)
            for index, case in enumerate(members):
                image = QImage(str(self.output / str(case["image"])))
                if image.isNull():
                    continue
                x, y = (index % columns) * tile_w, (index // columns) * tile_h
                scaled = image.scaled(tile_w - 12, tile_h - 42,
                                      Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
                painter.drawImage(x + 6, y + 6, scaled)
                painter.setPen(Qt.GlobalColor.black)
                painter.drawText(x + 6, y + tile_h - 9, str(case["case"])[:48])
            painter.end()
            if not sheet.save(str(self.output / ("contact-" + family + ".png")), "PNG"):
                raise RuntimeError("Cannot save contact sheet: " + family)


def new_window(app: QApplication, theme: str, language: Language) -> MainWindow:
    QSettings().clear()
    QSettings().sync()
    window = MainWindow()
    window._theme = build_theme(theme)
    apply_theme(app, window._theme)
    window._apply_theme_styles()
    window._apply_language(language)
    window._prefs.theme = theme
    window.resize(1200, 800)
    window.show()
    app.processEvents()
    if window.workspace_surface_ids() != ("build", "allocate", "explain", "database"):
        raise AssertionError("Registered C2 surfaces changed")
    return window


def close_window(window: MainWindow, app: QApplication) -> None:
    window.close()
    app.processEvents()


def scroll_details(scroll: QScrollArea, target: QWidget) -> dict[str, object]:
    bar = scroll.verticalScrollBar()
    scroll.ensureWidgetVisible(target, 0, 0)
    QApplication.processEvents()
    viewport = scroll.viewport()
    return {
        "bar_value": bar.value(), "bar_maximum": bar.maximum(),
        "target": rect_record(target, viewport),
    }


def capture_settings(collector: Collector, theme: str, language: Language, size: tuple[int, int]) -> None:
    app = collector.app
    window = new_window(app, theme, language)
    width, height = size
    prefix = f"settings-{theme}-{language.code}-{width}x{height}"
    try:
        action = window._support_toolbar_actions["settings"]
        assert action.objectName() == "actionPresentationSettings"
        opened: list[str] = []

        def fake_guide_exec(guide: DiagnosticsGuideDialog) -> int:
            guide.show()
            app.processEvents()
            tabs = guide.findChild(QTabWidget, "diagnosticsGuideLanguages")
            fa = guide.findChild(QTextBrowser, "diagnosticsGuideFa")
            en = guide.findChild(QTextBrowser, "diagnosticsGuideEn")
            assert tabs is not None and tabs.count() == 2 and fa is not None and en is not None
            assert fa.layoutDirection() == Qt.LayoutDirection.RightToLeft
            assert en.layoutDirection() == Qt.LayoutDirection.LeftToRight
            for tab_id, label in enumerate(("fa", "en")):
                tabs.setCurrentIndex(tab_id)
                app.processEvents()
                reader = fa if tab_id == 0 else en
                reader.verticalScrollBar().setValue(reader.verticalScrollBar().maximum())
                app.processEvents()
                collector.capture(guide, prefix + "-guide-" + label, "guide", theme, language,
                                  active_tab=label, guide_module=type(guide).__module__,
                                  reader_direction="rtl" if reader.layoutDirection() == Qt.LayoutDirection.RightToLeft else "ltr",
                                  reader_scroll_max=reader.verticalScrollBar().maximum(),
                                  reader_characters=len(reader.toPlainText()))
            guide.close()
            return 0

        def fake_settings_exec(dialog: UnifiedSettingsDialog) -> int:
            opened.append(type(dialog).__name__)
            dialog.resize(width, height)
            dialog.show()
            app.processEvents()
            scroll = dialog.findChild(QScrollArea, "settingsScrollArea")
            assert scroll is not None
            assert (dialog.width(), dialog.height()) == size
            assert len(dialog._checks) == 8
            category_names = [f"diagnosticsCategory_{item}" for item in CATEGORY_ORDER]
            assert all(dialog.findChild(QWidget, n) is not None for n in category_names)
            checks = {}
            for capability in CAPABILITIES:
                key = capability.setting_key
                check = dialog._checks[key]
                description = dialog.findChild(QLabel, f"diagnosticDescription_{key}")
                impact = dialog.findChild(QLabel, f"diagnosticImpact_{key}")
                button = dialog.findChild(QPushButton, f"diagnosticGuide_{key}")
                assert description is not None and description.text()
                assert impact is not None and impact.text()
                assert button is not None and button.isEnabled()
                checks[key] = {
                    "checked": check.isChecked(), "impact_text": impact.text(),
                    "impact_kind": impact.property("impactKind"),
                    "focus_policy": int(check.focusPolicy().value),
                    "scroll_reachability": scroll_details(scroll, impact),
                }
            scroll.verticalScrollBar().setValue(0)
            app.processEvents()
            collector.capture(dialog, prefix + "-top", "settings", theme, language,
                              entrypoint=action.objectName(),
                              category_names=category_names, checks=checks,
                              scroll_maximum=scroll.verticalScrollBar().maximum())
            scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
            app.processEvents()
            collector.capture(dialog, prefix + "-bottom", "settings", theme, language,
                              scroll_value=scroll.verticalScrollBar().value(),
                              last_impact=checks["use_join_buckets"]["impact_text"])
            if size == (620, 560):
                # Negative control: no production text or design is modified.
                label = dialog.findChild(QLabel, "diagnosticDescription_use_join_buckets")
                assert label is not None
                original = label.text()
                label.setText(original + " " + (" طولانی آزمایشی ABC-987654321/آزمون " * 22))
                scroll.ensureWidgetVisible(label)
                app.processEvents()
                collector.capture(dialog, prefix + "-synthetic-overflow", "settings",
                                  theme, language, overflow_control=True,
                                  overflow_text_length=len(label.text()),
                                  target=rect_record(label, scroll.viewport()))
                label.setText(original)
            guide = dialog.findChild(QPushButton, "diagnosticGuide_enable_qa_pool_coverage_rules")
            assert guide is not None
            with patch.object(DiagnosticsGuideDialog, "exec", fake_guide_exec):
                guide.click()
            dialog.close()
            return int(QDialog.DialogCode.Rejected)

        with patch.object(UnifiedSettingsDialog, "exec", fake_settings_exec):
            action.trigger()
        assert opened == ["UnifiedSettingsDialog"]
    finally:
        close_window(window, app)


def sample_metrics(long_text: bool) -> pd.DataFrame:
    name = "synthetic_channel"
    if long_text:
        name += "_EXTREMELY_LONG_CHANNEL_NAME_" * 8
    row: dict[str, object] = {key: 7 for key in METRIC_COLUMNS}
    row["allocation_channel"] = name
    if "same_history_mentor_ratio" in row:
        row["same_history_mentor_ratio"] = 0.375
    return pd.DataFrame([row], columns=METRIC_COLUMNS)


def table_metrics(table: QTableView) -> dict[str, object]:
    model = table.model()
    header = table.horizontalHeader()
    font_metrics = QFontMetrics(header.font())
    columns = []
    if model is not None:
        for i in range(model.columnCount()):
            label = str(model.headerData(i, Qt.Orientation.Horizontal) or "")
            columns.append({
                "column": i, "label": label,
                "header_width": header.sectionSize(i),
                "label_text_width": font_metrics.horizontalAdvance(label),
                "first_cell": str(model.data(model.index(0, i)) or "") if model.rowCount() else "",
            })
    bar = table.horizontalScrollBar()
    return {
        "rows": model.rowCount() if model is not None else None,
        "columns": columns, "horizontal_max": bar.maximum(),
        "horizontal_value": bar.value(),
        "scroll_policy": str(table.horizontalScrollBarPolicy()),
    }


def capture_history(collector: Collector, theme: str, language: Language) -> None:
    app = collector.app
    window = new_window(app, theme, language)
    prefix = f"history-{theme}-{language.code}"
    try:
        action = window._support_toolbar_actions["history"]
        assert action.objectName() == "actionHistoryMetrics"
        window._reset_history_metrics()
        action.trigger()
        app.processEvents()
        dialog = window._history_metrics_dialog
        assert dialog is not None and dialog.isVisible()
        assert type(dialog).__module__ == "app.ui.history_metrics", "wrong live History dialog"
        table = dialog.findChild(QTableView)
        assert table is not None
        collector.capture(dialog, prefix + "-empty", "history", theme, language,
                          entrypoint=action.objectName(), dialog_module=type(dialog).__module__,
                          table=table_metrics(table))
        # Supported current-run callback, no database write or allocation.
        window._user_settings = UserSettings(enable_history_metrics=True)
        window._capture_history_metrics(sample_metrics(False))
        app.processEvents()
        collector.capture(dialog, prefix + "-populated", "history", theme, language,
                          synthetic_metrics=True, table=table_metrics(table))
        table.horizontalScrollBar().setValue(table.horizontalScrollBar().maximum())
        app.processEvents()
        collector.capture(dialog, prefix + "-rightmost", "history", theme, language,
                          table=table_metrics(table))
        window._capture_history_metrics(sample_metrics(True))
        app.processEvents()
        table.horizontalScrollBar().setValue(table.horizontalScrollBar().maximum())
        collector.capture(dialog, prefix + "-long-value-control", "history", theme,
                          language, overflow_control=True, table=table_metrics(table))
        dialog.close()
    finally:
        close_window(window, app)


def wait_worker(window: MainWindow, app: QApplication) -> None:
    deadline = time.monotonic() + 10.0
    while window._worker is not None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)
    if window._worker is not None:
        raise TimeoutError("synthetic Worker did not complete and deliver UI signal")


def status_record(window: MainWindow) -> dict[str, object]:
    return {
        "progress_value": window._progress.value(),
        "progress_min": window._progress.minimum(),
        "progress_max": window._progress.maximum(),
        "progress_busy_property": window._progress.property("busy"),
        "progress_text": window._progress_caption.text(),
        "status_text": window._status.text(),
        "stage_badge": window._stage_badge.text(),
        "stage_detail": window._stage_detail.text(),
        "diagnostics_expanded": window.diagnostics_expanded(),
        "allocate_enabled": window._btn_allocate.isEnabled(),
        "build_enabled": window._btn_build.isEnabled(),
        "focus_widget": QApplication.focusWidget().objectName() if QApplication.focusWidget() else None,
    }


def capture_operational(collector: Collector, theme: str, language: Language) -> None:
    app = collector.app
    window = new_window(app, theme, language)
    prefix = f"operation-{theme}-{language.code}"
    try:
        assert window.activate_surface("allocate")
        app.processEvents()
        collector.capture(window, prefix + "-ready", "operation", theme, language,
                          operation_state="ready", **status_record(window))
        messages: list[QMessageBox] = []

        def warning(parent: QWidget, title: str, content: str, *args: object, **kwargs: object) -> QMessageBox.StandardButton:
            box = QMessageBox(QMessageBox.Icon.Warning, title, content, QMessageBox.StandardButton.Ok, parent)
            box.show()
            app.processEvents()
            messages.append(box)
            collector.capture(box, prefix + "-missing-school-warning", "operation",
                              theme, language, operation_state="missing_school_reference",
                              warning_title=title, warning_text=content)
            return QMessageBox.StandardButton.Ok

        # Stop before any CLI/output path; exercise the actual Allocate button.
        window._school_repository = None
        window._groupcode_repository = None
        window._ensure_year_loaded = lambda: None
        with patch.object(QMessageBox, "warning", side_effect=warning):
            window._btn_allocate.click()
        assert len(messages) == 1, "School-reference preflight did not show expected warning"
        for box in messages:
            box.close()
        collector.capture(window, prefix + "-after-missing-school", "operation",
                          theme, language, operation_state="after_missing_school",
                          **status_record(window))

        started = threading.Event()
        release = threading.Event()

        def held_task(*, progress: object) -> None:
            started.set()
            if not release.wait(6.0):
                raise TimeoutError("synthetic hold expired")

        worker = window._launch_worker(held_task, "Synthetic verification only")
        try:
            if not started.wait(3):
                raise TimeoutError("synthetic worker never started")
            app.processEvents()
            assert window._progress.minimum() == 0 and window._progress.maximum() == 0
            collector.capture(window, prefix + "-indeterminate", "operation", theme,
                              language, operation_state="indeterminate_running",
                              **status_record(window))
        finally:
            release.set()
            wait_worker(window, app)
        collector.capture(window, prefix + "-completed", "operation", theme, language,
                          operation_state="synthetic_worker_completed",
                          **status_record(window))

        def failed_task(*, progress: object) -> None:
            raise RuntimeError("Synthetic controlled failure — no allocation executed")

        window._launch_worker(failed_task, "Synthetic verification only")
        wait_worker(window, app)
        app.processEvents()
        collector.capture(window, prefix + "-controlled-failure", "operation",
                          theme, language, operation_state="synthetic_worker_failed",
                          **status_record(window))
        assert window.diagnostics_expanded(), "failure did not reveal diagnostics"
        for box in window.findChildren(QMessageBox):
            if box.isVisible():
                collector.capture(box, prefix + "-failure-modal", "operation", theme,
                                  language, operation_state="failure_message",
                                  message=box.text())
                box.close()
    finally:
        close_window(window, app)


def capture_explain(collector: Collector, theme: str, language: Language) -> None:
    app = collector.app
    window = new_window(app, theme, language)
    try:
        assert window.activate_surface("explain")
        app.processEvents()
        tables = [table_metrics(item) for item in window._workspace_surfaces["explain"].findChildren(QTableView)]
        collector.capture(window, f"explain-{theme}-{language.code}-sample", "explain",
                          theme, language, tables=tables,
                          note="Visual inspection of existing example only; no synthesized Explain semantics")
    finally:
        close_window(window, app)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/ui-dialog-operational"))
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("AllocationApp")
    app.setOrganizationName("MatrixEvidenceVerifier")
    collector = Collector(args.output_dir, app)
    with tempfile.TemporaryDirectory(prefix="matrix-evidence-settings-") as folder:
        configure_settings(Path(folder))
        for theme in THEMES:
            for language in LANGUAGES:
                for size in SIZES:
                    label = f"settings-{theme}-{language.code}-{size[0]}x{size[1]}"
                    collector.try_case(label, lambda t=theme, l=language, s=size:
                                       capture_settings(collector, t, l, s))
                collector.try_case(f"history-{theme}-{language.code}",
                                   lambda t=theme, l=language: capture_history(collector, t, l))
                collector.try_case(f"operation-{theme}-{language.code}",
                                   lambda t=theme, l=language: capture_operational(collector, t, l))
                collector.try_case(f"explain-{theme}-{language.code}",
                                   lambda t=theme, l=language: capture_explain(collector, t, l))
    collector.save()
    print(f"Recorded {len(collector.cases)} PNG cases; {len(collector.failures)} failures")
    for failure in collector.failures:
        print("FAIL", failure["case"], failure["error"])
    return 1 if collector.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

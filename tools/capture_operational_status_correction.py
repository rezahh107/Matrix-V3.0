"""Full-resolution synthetic operational screenshots; no allocation or persistence calls.

Reuses the PR #28 Windows offscreen scenario names for genuine before/after parity.
The original PNGs are copied unmodified by the dedicated CI workflow.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import tempfile
import threading
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QSettings
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from app.ui.i18n import Language
from app.ui.main_window import MainWindow
from app.ui.task_runner import WorkerCancelled
from app.ui.theme import apply_theme, build_theme

THEMES = ("light", "dark")
LANGUAGES = (Language.FA, Language.EN)
PAIRABLE = {"ready": "ready", "indeterminate": "indeterminate",
            "completed": "completed", "failed": "controlled-failure"}


def wait_finished(window: MainWindow, app: QApplication) -> None:
    # Retain the QThread beyond the UI completion signal, through native teardown.
    worker = window._worker
    if worker is None:
        raise AssertionError("no synthetic Worker to await")
    deadline = time.monotonic() + 8
    while window._worker is not None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)
    if window._worker is not None:
        raise TimeoutError("synthetic Worker did not deliver a finished signal")
    if not worker.wait(5000):
        raise TimeoutError("synthetic QThread did not fully stop")


def capture(window: MainWindow, app: QApplication, output: Path, stem: str,
            state: str, cases: list[dict[str, object]]) -> None:
    app.processEvents()
    caption = window._progress_caption.text()
    translated = {
        "ready": window._t("status.ready", "آماده"),
        "indeterminate": window._t("status.running", "در حال پردازش"),
        "determinate": window._t("status.running", "در حال پردازش") + " · 37%",
        "completed": window._t("status.complete", "کامل"),
        "failed": window._t("status.error", "خطا"),
        "cancelled": window._t("status.cancelled", "لغو شد"),
    }[state]
    if caption != translated or not window._progress_caption.isVisibleTo(window):
        raise AssertionError(f"{stem}: status caption mismatch: {caption!r} vs {translated!r}")
    if not window._progress.isTextVisible():
        pass
    else:
        raise AssertionError(f"{stem}: native progress bar text must be hidden")
    if state != "determinate" and "%" in caption:
        raise AssertionError(f"{stem}: invalid or invented percentage {caption}")
    if state == "indeterminate" and window._progress.maximum() != 0:
        raise AssertionError(f"{stem}: unknown progress must use busy range")
    if state == "determinate" and window._progress.value() != 37:
        raise AssertionError(f"{stem}: determinate value mismatch")
    if state == "failed" and not window.diagnostics_expanded():
        raise AssertionError(f"{stem}: failures must reveal diagnostics")
    if state in ("ready", "indeterminate", "determinate", "completed") and window.diagnostics_expanded():
        raise AssertionError(f"{stem}: routine diagnostics must be collapsed")

    after = output / "after" / (stem + ".png")
    after.parent.mkdir(parents=True, exist_ok=True)
    pix = window.grab()
    if pix.size().width() != 1200 or pix.size().height() != 800:
        raise AssertionError(f"{stem}: expected 1200x800 screenshot")
    if not pix.save(str(after), "PNG") or after.stat().st_size == 0:
        raise RuntimeError(f"{stem}: failed to save screenshot")
    before_name = PAIRABLE.get(state)
    if before_name is not None:
        baseline = output / "before" / (stem.replace("-" + state, "-" + before_name) + ".png")
        original = QImage(str(baseline))
        current = QImage(str(after))
        if original.isNull() or current.isNull() or original.size() != current.size():
            raise AssertionError(f"{stem}: full-resolution baseline missing or different size")
        pair = QImage(2400, 800, QImage.Format.Format_ARGB32)
        painter = QPainter(pair)
        painter.drawImage(0, 0, original)
        painter.drawImage(1200, 0, current)
        painter.end()
        compare = output / "compare" / (stem + ".png")
        compare.parent.mkdir(parents=True, exist_ok=True)
        if not pair.save(str(compare), "PNG"):
            raise RuntimeError(f"{stem}: comparison image save failed")

    cases.append({
        "name": stem, "state": state, "caption": caption,
        "status_pill": window._status_bar_state.text(),
        "progress_range": [window._progress.minimum(), window._progress.maximum()],
        "progress_value": window._progress.value(),
        "diagnostics_expanded": window.diagnostics_expanded(),
        "image": str(after.relative_to(output)),
        "baseline": str(baseline.relative_to(output)) if before_name else None,
        "size": [1200, 800],
    })


def run_matrix(output: Path) -> list[dict[str, object]]:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("MatrixStatusCapture")
    app.setOrganizationName("MatrixStatusCapture")
    cases: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory() as settings_dir:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        for scope in (QSettings.Scope.UserScope, QSettings.Scope.SystemScope):
            QSettings.setPath(QSettings.Format.IniFormat, scope, settings_dir)
        for theme in THEMES:
            for language in LANGUAGES:
                QSettings().clear()
                window = MainWindow()
                try:
                    window._theme = build_theme(theme)
                    apply_theme(app, window._theme)
                    window._apply_theme_styles()
                    window._apply_language(language)
                    window.resize(1200, 800)
                    window.show()
                    window.activate_surface("allocate")
                    app.processEvents()
                    stem = f"operation-{theme}-{language.code}"
                    capture(window, app, output, stem + "-ready", "ready", cases)

                    release = threading.Event()
                    started = threading.Event()

                    def held_task(*, progress: object) -> None:
                        started.set()
                        if not release.wait(6):
                            raise TimeoutError("synthetic hold expired")

                    window._launch_worker(held_task, "Synthetic verification only")
                    try:
                        if not started.wait(3):
                            raise TimeoutError("synthetic Worker not started")
                        capture(window, app, output, stem + "-indeterminate", "indeterminate", cases)
                        window._on_progress(37, "Synthetic reported progress")
                        capture(window, app, output, stem + "-determinate", "determinate", cases)
                    finally:
                        release.set()
                        wait_finished(window, app)
                    capture(window, app, output, stem + "-completed", "completed", cases)

                    def failed_task(*, progress: object) -> None:
                        raise RuntimeError("Synthetic controlled failure")

                    window._show_async_message = lambda *_a, **_kw: None
                    window._launch_worker(failed_task, "Synthetic verification only")
                    wait_finished(window, app)
                    capture(window, app, output, stem + "-failed", "failed", cases)

                    window.set_diagnostics_expanded(False)

                    def cancel_task(*, progress: object) -> None:
                        raise WorkerCancelled("Synthetic cancellation")

                    window._launch_worker(cancel_task, "Synthetic verification only")
                    wait_finished(window, app)
                    capture(window, app, output, stem + "-cancelled", "cancelled", cases)
                finally:
                    window.close()
                    window.deleteLater()
                    app.processEvents()
                    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                    app.processEvents()
    return cases


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output: Path = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    cases = run_matrix(output)
    assert len(cases) == 24, f"expected 24 operational screenshots, got {len(cases)}"
    manifest = {
        "head_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "baseline_pr": 28,
        "baseline_verified_commit": "782d178f5dc539bc078e04a1e67a10ad6ea5baa4",
        "platform": platform.platform(),
        "mode": "synthetic Windows offscreen; not real-device interaction",
        "capture_count": len(cases), "pair_count": 16, "cases": cases,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Captured {len(cases)} states and 16 full-resolution before/after pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

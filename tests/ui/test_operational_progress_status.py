"""Regression tests for the operational-status UI (not allocation behavior)."""

from __future__ import annotations

import threading
import time

import pytest

pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.ui.i18n import Language
from app.ui.main_window import MainWindow
from app.ui.theme import apply_theme, build_theme


def _wait_for_worker(window: MainWindow, app: QApplication) -> None:
    deadline = time.monotonic() + 8
    while window._worker is not None and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(10)
    assert window._worker is None, "synthetic Worker failed to deliver finished signal"


@pytest.mark.parametrize("language", (Language.FA, Language.EN))
@pytest.mark.parametrize("theme", ("light", "dark"))
def test_operational_state_labels_and_progress_are_truthful(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, language: Language, theme: str
) -> None:
    window = MainWindow()
    try:
        window._theme = build_theme(theme)
        apply_theme(qapp, window._theme)
        window._apply_theme_styles()
        window._apply_language(language)
        window.resize(1200, 800)
        window.show()
        qapp.processEvents()
        assert not window._progress.isTextVisible()
        assert window._progress_caption.text() == window._t("status.ready", "آماده")
        assert "%" not in window._progress_caption.text()
        assert window._operation_state == "ready"
        assert not window.diagnostics_expanded()

        release = threading.Event()
        started = threading.Event()

        def held_task(*, progress: object) -> None:
            started.set()
            if not release.wait(6):
                raise TimeoutError("synthetic Worker hold expired")

        window._launch_worker(held_task, "Synthetic status test")
        try:
            assert started.wait(3)
            qapp.processEvents()
            assert window._operation_state == "running"
            assert window._progress.maximum() == 0
            assert "%" not in window._progress_caption.text()
            assert window._t("status.running", "در حال پردازش") in window._progress_caption.text()
            assert window._t("statusbar.running", "وضعیت: در حال اجرا") in window._status_bar_state.text()
            assert not window._btn_build.isEnabled()
            assert not window._btn_allocate.isEnabled()
            assert not window.diagnostics_expanded()

            for pct in (0, 37, 100):
                window._on_progress(pct, f"Reported stage {pct}")
                assert window._progress.maximum() == 100
                assert window._progress_caption.text().endswith(f"{pct}%")
            for invalid in (-1, 101):
                window._on_progress(invalid, "Unknown completion")
                assert window._progress.maximum() == 0
                assert window._progress.property("busy") is True
                assert "%" not in window._progress_caption.text()
            window._on_progress(72, "Known progress again")
            assert window._progress_caption.text().endswith("72%")
        finally:
            release.set()
            _wait_for_worker(window, qapp)

        assert window._operation_state == "completed"
        assert window._progress_caption.text() == window._t("status.complete", "کامل")
        assert "%" not in window._progress_caption.text()
        assert window._t("statusbar.completed", "وضعیت: تکمیل‌شده") in window._status_bar_state.text()
        assert window._btn_build.isEnabled()
        assert window._btn_allocate.isEnabled()
        assert not window.diagnostics_expanded()

        monkeypatch.setattr(window, "_show_async_message", lambda *_args, **_kwargs: None)
        window._on_finished(False, RuntimeError("Synthetic failure"))
        qapp.processEvents()
        assert window._operation_state == "failed"
        assert window._progress_caption.text() == window._t("status.error", "خطا")
        assert "%" not in window._progress_caption.text()
        assert window._t("statusbar.error", "وضعیت: خطا") in window._status_bar_state.text()
        assert window.diagnostics_expanded()

        window._on_finished(False, None)
        qapp.processEvents()
        assert window._operation_state == "cancelled"
        assert window._progress_caption.text() == window._t("status.cancelled", "لغو شد")
        assert "%" not in window._progress_caption.text()
        assert window._t("statusbar.cancelled", "وضعیت: لغوشده") in window._status_bar_state.text()
        assert window._btn_allocate.isEnabled()

        # A language toggle after a terminal result may not restore a stale Ready.
        other = Language.EN if language == Language.FA else Language.FA
        window._apply_language(other)
        assert window._operation_state == "cancelled"
        assert window._progress_caption.text() == window._t("status.cancelled", "لغو شد")
        assert window._t("statusbar.cancelled", "وضعیت: لغوشده") in window._status_bar_state.text()
    finally:
        window.close()


def test_diagnostics_toggle_remains_keyboard_operable(qapp: QApplication) -> None:
    window = MainWindow()
    try:
        window.resize(1200, 800)
        window.show()
        qapp.processEvents()
        toggle = window._diagnostics_toggle
        assert toggle is not None and toggle.isEnabled()
        assert toggle.focusPolicy() != Qt.FocusPolicy.NoFocus
        toggle.setFocus()
        qapp.processEvents()
        assert toggle.hasFocus()
        QTest.keyClick(toggle, Qt.Key.Key_Space)
        qapp.processEvents()
        assert window.diagnostics_expanded()
        assert toggle.hasFocus()
        QTest.keyClick(toggle, Qt.Key.Key_Space)
        qapp.processEvents()
        assert not window.diagnostics_expanded()
    finally:
        window.close()

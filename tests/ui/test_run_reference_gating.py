from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

try:  # pragma: no cover - import guard for headless CI
    from PySide6.QtWidgets import QApplication, QMessageBox
except ImportError as exc:  # pragma: no cover - skipped when Qt missing
    pytest.skip(f"PySide6 unavailable: {exc}", allow_module_level=True)

from app.infra.groupcode.groupcode_repository import GroupCodeRepository
from app.infra.local_database import LocalDatabase
from app.infra.schools.school_repository import SchoolRepository
from app.ui.main_window import MainWindow, UnknownsPreflightResult


def _write_excel(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)


@pytest.fixture()
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _build_window(tmp_path: Path) -> MainWindow:
    window = MainWindow()
    db = LocalDatabase(tmp_path / "local.sqlite")
    window._local_db = db
    window._school_repository = SchoolRepository(db)
    window._groupcode_repository = GroupCodeRepository(db)

    students = tmp_path / "students.xlsx"
    pool = tmp_path / "pool.xlsx"
    alloc_out = tmp_path / "alloc.xlsx"
    for path in (students, pool, alloc_out):
        path.touch()

    window._picker_students.setText(str(students))
    window._picker_pool.setText(str(pool))
    window._picker_alloc_out.setText(str(alloc_out))
    window._combo_academic_year.setCurrentText("1402")
    return window


def test_run_blocked_when_references_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, qapp: QApplication
) -> None:
    window = _build_window(tmp_path)

    # حتی اگر کاربر فایل‌های لازم را انتخاب کند/یا مسیرهای ورودی را پر کند، نبود داده در DB باید اجرا را مسدود کند.
    schools_path = tmp_path / "schools.xlsx"
    schools_path.touch()
    if hasattr(window, "_picker_schools"):
        # Set only the schools picker, not the optional crosswalk picker.
        window._picker_schools.setText(str(schools_path))

    warnings: list[tuple[str, str]] = []

    def _capture_warning(parent: object, title: str, text: str) -> None:
        warnings.append((title, text))

    monkeypatch.setattr(QMessageBox, "warning", staticmethod(_capture_warning))

    launches: list[tuple[object, ...]] = []

    def _fake_launch(*args: object, **kwargs: object) -> None:
        launches.append(args)

    monkeypatch.setattr(window, "_launch_cli", _fake_launch)

    window._start_allocate()

    assert warnings, "expected readiness gating to warn when references are missing"
    assert "reference" in warnings[0][0].lower() or "داده" in warnings[0][0]
    assert not launches, "allocation should not start when references are missing"

    window.close()
    qapp.processEvents()


def test_run_allowed_when_references_ready(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, qapp: QApplication
) -> None:
    window = _build_window(tmp_path)

    schools_df = pd.DataFrame(
        {
            "کد مدرسه": [1, 2],
            "نام مدرسه": ["A", "B"],
            "مرکز گلستان صدرا": [10, 20],
            "جنسیت": [1, 2],
            "فعال": [1, 1],
        }
    )
    schools_path = tmp_path / "schools.xlsx"
    _write_excel(schools_df, schools_path)

    assert window._school_repository is not None
    window._school_repository.import_from_excel(schools_path)

    launches: list[tuple[object, ...]] = []

    def _capture_launch(*args: object, **kwargs: object) -> None:
        launches.append(args)

    monkeypatch.setattr(window, "_launch_cli", _capture_launch)

    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox, "warning", staticmethod(lambda *_: warnings.append(("warn", "warn")))
    )

    monkeypatch.setattr(
        window,
        "_preflight_result_override",
        lambda _: UnknownsPreflightResult(
            status="clean", report_path=tmp_path / "noop.json", exit_code=0, summary=None
        ),
    )

    window._start_allocate()

    assert not warnings, "no warnings expected when references are ready"
    assert launches, "allocation should start when references are ready"

    window.close()
    qapp.processEvents()

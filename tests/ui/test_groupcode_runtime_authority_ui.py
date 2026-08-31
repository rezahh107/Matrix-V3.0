from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

try:
    from PySide6.QtWidgets import QApplication, QMessageBox
except ImportError as exc:  # pragma: no cover
    pytest.skip(f"PySide6 unavailable: {exc}", allow_module_level=True)

from app.infra.groupcode.groupcode_repository import GroupCodeRepository
from app.infra.local_database import LocalDatabase
from app.infra.schools.school_repository import SchoolRepository
from app.ui.main_window import MainWindow


@pytest.fixture()
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _window(tmp_path: Path) -> MainWindow:
    window = MainWindow()
    db = LocalDatabase(tmp_path / "annual.sqlite")
    window._local_db = db
    window._school_repository = SchoolRepository(db)
    window._groupcode_repository = GroupCodeRepository(db)

    students = tmp_path / "students.xlsx"
    output = tmp_path / "allocation.xlsx"
    students.touch()
    window._picker_students.setText(str(students))
    window._picker_alloc_out.setText(str(output))
    window._combo_academic_year.setCurrentText("1404")
    return window


def test_build_reference_controls_are_not_selectable_runtime_inputs(
    tmp_path: Path, qapp: QApplication
) -> None:
    window = _window(tmp_path)
    assert not window._picker_schools.isEnabled()
    assert not window._picker_crosswalk.isEnabled()
    assert "database" in window._picker_schools.toolTip().lower() or "پایگاه" in window._picker_schools.toolTip()
    assert "database" in window._picker_crosswalk.toolTip().lower() or "پایگاه" in window._picker_crosswalk.toolTip()
    window.close()
    qapp.processEvents()


def test_build_argv_contains_no_runtime_reference_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, qapp: QApplication
) -> None:
    window = _window(tmp_path)
    assert window._picker_pool.text().strip() == ""
    inspactor = tmp_path / "inspactor.xlsx"
    inspactor.touch()
    window._picker_inspactor.setText(str(inspactor))
    window._picker_output_matrix.setText(str(tmp_path / "matrix.xlsx"))
    window._picker_schools.setText(str(tmp_path / "ignored-schools.xlsx"))
    window._picker_crosswalk.setText(str(tmp_path / "ignored-groupcodes.xlsx"))
    launches: list[list[str]] = []

    def _capture(argv: list[str], *_args: object, **_kwargs: object) -> None:
        launches.append(list(argv))

    monkeypatch.setattr(window, "_launch_cli", _capture)
    window._start_build()
    assert launches
    assert "--schools" not in launches[0]
    assert "--crosswalk" not in launches[0]
    window.close()
    qapp.processEvents()


def test_allocate_blocks_when_groupcodes_reference_is_not_ready(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, qapp: QApplication
) -> None:
    window = _window(tmp_path)
    monkeypatch.setattr(
        "app.ui.main_window.compute_reference_readiness",
        lambda **_: SimpleNamespace(
            is_ready_for_run=False,
            schools_ready=True,
            groupcodes_ready=False,
            schools=SimpleNamespace(row_count=1),
            groupcodes=SimpleNamespace(row_count=0),
        ),
    )

    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda _parent, title, text: warnings.append((title, text))),
    )
    launches: list[tuple[object, ...]] = []
    monkeypatch.setattr(window, "_launch_cli", lambda *args, **kwargs: launches.append(args))

    window._start_allocate()

    assert warnings
    assert not launches
    window.close()
    qapp.processEvents()

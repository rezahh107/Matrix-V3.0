from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pandas as pd
import pytest

from app.core.policy_loader import load_policy
from app.infra import cli, cli_legacy
from app.infra.groupcode.groupcode_repository import GroupCodeRepository
from app.infra.local_database import LocalDatabase
from app.infra.schools.school_repository import SchoolRepository
from app.infra.year_database_manager import YearDatabaseManager

POLICY_PATH = Path("config/policy.json")


def _write_excel(frame: pd.DataFrame, path: Path) -> Path:
    frame.to_excel(path, index=False)
    return path


def _groupcodes(code: int) -> pd.DataFrame:
    rows = {
        24: ("متوسطه دوم", 10, "ریاضی"),
        25: ("متوسطه دوم", 10, "تجربی"),
    }
    level, grade, track = rows[code]
    return pd.DataFrame(
        {
            "group_code": [code],
            "level": [level],
            "grade": [grade],
            "track": [track],
            "is_active": [1],
        }
    )


def _invalid_groupcodes() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "group_code": [999],
            "level": ["متوسطه دوم"],
            "grade": [10],
            "track": ["ریاضی"],
            "is_active": [1],
        }
    )


def _schools(name: str = "Synthetic School") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "کد مدرسه": [101],
            "نام مدرسه": [name],
            "مرکز گلستان صدرا": [0],
            "جنسیت": [1],
            "فعال": [1],
        }
    )


def _student(group_code: int = 24) -> pd.DataFrame:
    group_name = "دهم ریاضی" if group_code == 24 else "دهم تجربی"
    return pd.DataFrame(
        {
            "student_id": ["synthetic-student-1"],
            "کد ملی": ["0000000001"],
            "کدرشته": [group_code],
            "گروه آزمایشی": [group_name],
            "جنسیت": [1],
            "دانش آموز فارغ": [1],
            "مرکز گلستان صدرا": [0],
            "مالی حکمت بنیاد": [0],
            "کد مدرسه": [0],
        }
    )


def _inspactor(group_code: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "نام پشتیبان": ["Synthetic Mentor"],
            "نام مدیر": ["Synthetic Manager"],
            "کد کارمندی پشتیبان": ["9001"],
            "کدپستی": ["5000"],
            "تعداد مدارس تحت پوشش": [0],
            "تعداد داوطلبان تحت پوشش": [0],
            "تعداد تحت پوشش خاص": [5],
            "شامل گروه های آزمایشی": [str(group_code)],
            "گروه آزمایشی": [group_code],
            "کدرشته": [group_code],
            "جنسیت": [1],
            "دانش آموز فارغ": [1],
            "مرکز گلستان صدرا": [0],
            "مالی حکمت بنیاد": [0],
            "کد مدرسه": [0],
            "نام مدرسه 1": [0],
            "نام مدرسه 2": [0],
            "نام مدرسه 3": [0],
            "نام مدرسه 4": [0],
        }
    )


def _prepare_reference_db(tmp_path: Path, group_code: int = 24) -> tuple[Path, Path, Path]:
    db_path = tmp_path / "annual.sqlite"
    school_path = _write_excel(_schools(), tmp_path / "schools.xlsx")
    group_path = _write_excel(
        _groupcodes(group_code), tmp_path / f"groupcodes-{group_code}.xlsx"
    )
    db = LocalDatabase(db_path)
    SchoolRepository(db).import_from_excel(school_path)
    GroupCodeRepository(db).import_from_excel(group_path)
    return db_path, school_path, group_path


def _matrix_group_values(matrix_path: Path) -> set[int]:
    matrix = pd.read_excel(matrix_path, sheet_name="matrix")
    group_column = next(
        column for column in matrix.columns if str(column).split("|", 1)[0].strip() == "کدرشته"
    )
    return set(pd.to_numeric(matrix[group_column], errors="coerce").dropna().astype(int))


def _build_matrix(*, tmp_path: Path, db_path: Path, group_code: int) -> Path:
    inspactor_path = _write_excel(
        _inspactor(group_code), tmp_path / f"inspactor-{group_code}.xlsx"
    )
    matrix_path = tmp_path / f"matrix-{group_code}.xlsx"
    rc = cli_legacy.main(
        [
            "build-matrix",
            "--inspactor",
            str(inspactor_path),
            "--output",
            str(matrix_path),
            "--policy",
            str(POLICY_PATH),
            "--local-db",
            str(db_path),
            "--min-coverage",
            "0",
            "--use-v3-mentor-pipeline",
        ]
    )
    assert rc == 0
    assert matrix_path.exists()
    return matrix_path


def test_p0_01_explicit_groupcode_import_reaches_real_build(tmp_path: Path) -> None:
    db_path, _, _ = _prepare_reference_db(tmp_path, group_code=24)
    group_b = _write_excel(_groupcodes(25), tmp_path / "groupcodes-B.xlsx")

    rc = cli_legacy.main(
        [
            "import-groupcodes",
            "--crosswalk",
            str(group_b),
            "--local-db",
            str(db_path),
        ]
    )
    assert rc == 0

    repo = GroupCodeRepository(LocalDatabase(db_path))
    stored = repo.load_canonical_frame()
    assert set(stored["group_code"].astype(int)) == {25}
    status = repo.status()
    assert status.row_count == 1
    assert status.source_filename == group_b.name
    assert status.version_tag == group_b.stem
    assert status.imported_at is not None

    matrix_path = _build_matrix(
        tmp_path=tmp_path,
        db_path=db_path,
        group_code=25,
    )
    values = _matrix_group_values(matrix_path)
    assert 25 in values
    assert 24 not in values


def test_p0_02_real_student_ingress_tracks_current_db_groupcodes(tmp_path: Path) -> None:
    db_path, _, _ = _prepare_reference_db(tmp_path, group_code=24)
    students_path = _write_excel(_student(24), tmp_path / "students.xlsx")
    policy = load_policy(POLICY_PATH)
    db = LocalDatabase(db_path)

    current, _, _ = cli_legacy._resolve_students_frame(
        Namespace(students=str(students_path)), policy, db=db
    )
    assert int(current.loc[0, "کدرشته"]) == 24

    GroupCodeRepository(db).import_from_excel(
        _write_excel(_groupcodes(25), tmp_path / "groupcodes-B.xlsx")
    )
    with pytest.raises(ValueError, match="Unknown group code"):
        cli_legacy._resolve_students_frame(
            Namespace(students=str(students_path)), policy, db=db
        )


def test_p0_03_groupcode_change_blocks_now_ineligible_real_allocation(tmp_path: Path) -> None:
    db_path, _, _ = _prepare_reference_db(tmp_path, group_code=24)
    matrix_path = _build_matrix(
        tmp_path=tmp_path,
        db_path=db_path,
        group_code=24,
    )
    students_path = _write_excel(_student(24), tmp_path / "students.xlsx")
    output_a = tmp_path / "allocation-A.xlsx"

    rc = cli_legacy.main(
        [
            "allocate",
            "--students",
            str(students_path),
            "--pool",
            str(matrix_path),
            "--pool-type",
            "matrix",
            "--pool-sheet",
            "matrix",
            "--policy",
            str(POLICY_PATH),
            "--academic-year",
            "1404",
            "--counter-duplicate-strategy",
            "assign-new",
            "--output",
            str(output_a),
            "--local-db",
            str(db_path),
        ]
    )
    assert rc == 0
    assert output_a.exists()

    GroupCodeRepository(LocalDatabase(db_path)).import_from_excel(
        _write_excel(_groupcodes(25), tmp_path / "groupcodes-B.xlsx")
    )
    with pytest.raises(ValueError, match="Unknown group code"):
        cli_legacy.main(
            [
                "allocate",
                "--students",
                str(students_path),
                "--pool",
                str(matrix_path),
                "--pool-type",
                "matrix",
                "--pool-sheet",
                "matrix",
                "--policy",
                str(POLICY_PATH),
                "--academic-year",
                "1404",
                "--counter-duplicate-strategy",
                "assign-new",
                "--output",
                str(tmp_path / "allocation-B.xlsx"),
                "--local-db",
                str(db_path),
            ]
        )


def test_p0_04_deprecated_build_crosswalk_fails_without_mutating_db(tmp_path: Path) -> None:
    db_path, _, group_a = _prepare_reference_db(tmp_path, group_code=24)
    group_b = _write_excel(_groupcodes(25), tmp_path / "groupcodes-B.xlsx")
    output = tmp_path / "must-not-build.xlsx"

    rc = cli_legacy.main(
        [
            "build-matrix",
            "--crosswalk",
            str(group_b),
            "--output",
            str(output),
            "--local-db",
            str(db_path),
        ]
    )
    assert rc == 2
    assert not output.exists()

    repo = GroupCodeRepository(LocalDatabase(db_path))
    stored = repo.load_canonical_frame()
    assert set(stored["group_code"].astype(int)) == {24}
    meta = repo.status()
    assert meta.source_filename == group_a.name


def test_deprecated_build_schools_fails_without_mutating_db(tmp_path: Path) -> None:
    db_path, school_a, _ = _prepare_reference_db(tmp_path, group_code=24)
    school_b = _write_excel(_schools("Replacement School"), tmp_path / "schools-B.xlsx")
    output = tmp_path / "must-not-build-schools.xlsx"

    rc = cli_legacy.main(
        [
            "build-matrix",
            "--schools",
            str(school_b),
            "--output",
            str(output),
            "--local-db",
            str(db_path),
        ]
    )
    assert rc == 2
    assert not output.exists()

    repo = SchoolRepository(LocalDatabase(db_path))
    stored = repo.load_canonical_frame()
    assert stored["نام مدرسه"].tolist() == ["Synthetic School"]
    assert repo.status().source_filename == school_a.name


def test_p0_05_stale_student_cache_is_revalidated_against_current_db(tmp_path: Path) -> None:
    db_path, _, _ = _prepare_reference_db(tmp_path, group_code=24)
    students_path = _write_excel(_student(24), tmp_path / "students.xlsx")
    policy = load_policy(POLICY_PATH)
    db = LocalDatabase(db_path)

    cached, _, _ = cli_legacy._resolve_students_frame(
        Namespace(students=str(students_path)), policy, db=db
    )
    assert int(cached.loc[0, "کدرشته"]) == 24

    GroupCodeRepository(db).import_from_excel(
        _write_excel(_groupcodes(25), tmp_path / "groupcodes-B.xlsx")
    )
    with pytest.raises(ValueError, match="Unknown group code"):
        cli_legacy._resolve_students_frame(Namespace(students=None), policy, db=db)


def test_p0_06_gui_backend_and_direct_cli_share_groupcode_db(tmp_path: Path) -> None:
    db_path, _, _ = _prepare_reference_db(tmp_path, group_code=25)
    inspactor_path = _write_excel(_inspactor(25), tmp_path / "inspactor-parity.xlsx")
    gui_output = tmp_path / "matrix-gui-backend.xlsx"
    cli_output = tmp_path / "matrix-direct-cli.xlsx"

    common_args = [
        "build-matrix",
        "--inspactor",
        str(inspactor_path),
        "--policy",
        str(POLICY_PATH),
        "--min-coverage",
        "0",
        "--use-v3-mentor-pipeline",
    ]
    gui_rc = cli.main(
        [*common_args, "--output", str(gui_output)],
        ui_overrides={"local_db_path": str(db_path)},
    )
    direct_rc = cli_legacy.main(
        [
            *common_args,
            "--output",
            str(cli_output),
            "--local-db",
            str(db_path),
        ]
    )

    assert gui_rc == 0
    assert direct_rc == 0
    assert _matrix_group_values(gui_output) == {25}
    assert _matrix_group_values(cli_output) == {25}


def test_allocate_cannot_disable_authoritative_reference_db(tmp_path: Path) -> None:
    students_path = _write_excel(_student(24), tmp_path / "students.xlsx")
    rc = cli_legacy.main(
        [
            "allocate",
            "--students",
            str(students_path),
            "--pool",
            str(tmp_path / "unused-matrix.xlsx"),
            "--output",
            str(tmp_path / "unused-output.xlsx"),
            "--disable-local-db",
        ]
    )
    assert rc == 2


def test_failed_empty_groupcode_import_preserves_previous_reference(tmp_path: Path) -> None:
    db_path, _, group_a = _prepare_reference_db(tmp_path, group_code=24)
    empty = _write_excel(
        pd.DataFrame(columns=["group_code", "level", "grade", "track"]),
        tmp_path / "empty-groupcodes.xlsx",
    )

    rc = cli_legacy.main(
        [
            "import-groupcodes",
            "--crosswalk",
            str(empty),
            "--local-db",
            str(db_path),
        ]
    )
    assert rc == 2

    repo = GroupCodeRepository(LocalDatabase(db_path))
    stored = repo.load_canonical_frame()
    assert set(stored["group_code"].astype(int)) == {24}
    assert repo.status().source_filename == group_a.name


def test_failed_invalid_groupcode_import_preserves_previous_reference(tmp_path: Path) -> None:
    db_path, _, group_a = _prepare_reference_db(tmp_path, group_code=24)
    invalid = _write_excel(_invalid_groupcodes(), tmp_path / "invalid-groupcodes.xlsx")

    rc = cli_legacy.main(
        [
            "import-groupcodes",
            "--crosswalk",
            str(invalid),
            "--local-db",
            str(db_path),
        ]
    )
    assert rc == 2

    repo = GroupCodeRepository(LocalDatabase(db_path))
    stored = repo.load_canonical_frame()
    assert set(stored["group_code"].astype(int)) == {24}
    assert repo.status().source_filename == group_a.name


def test_groupcode_authority_persists_across_annual_db_reopen(tmp_path: Path) -> None:
    manager = YearDatabaseManager(tmp_path / "annual-dbs")
    db = manager.open_year("1404")
    group_path = _write_excel(_groupcodes(24), tmp_path / "year-groupcodes.xlsx")
    GroupCodeRepository(db).import_from_excel(group_path)
    db.close_all_connections()

    reopened = manager.open_year("1404")
    repo = GroupCodeRepository(reopened)
    stored = repo.load_canonical_frame()
    status = repo.status()

    assert set(stored["group_code"].astype(int)) == {24}
    assert status.source_filename == group_path.name
    assert status.imported_at is not None


def test_operator_workflow_db_build_allocate_qa_sabt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise one connected operator path; Qt dialogs are stubbed, execution is real."""
    from hashlib import sha256

    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

    from app.core.common.types import CANONICAL_TRACE_ORDER
    from app.infra.config_flags import UserSettings
    from app.infra.excel import export_allocations as sabt_exports
    from app.ui.database_tab import DatabaseTab

    app = QApplication.instance() or QApplication([])
    db_path = tmp_path / "operator.sqlite"
    db = LocalDatabase(db_path)
    # MainWindow prepares the annual DB schema before attaching DatabaseTab.
    db.initialize()
    school_repo = SchoolRepository(db)
    group_repo = GroupCodeRepository(db)
    school_file = _write_excel(_schools(), tmp_path / "schools.xlsx")
    group_file = _write_excel(_groupcodes(24), tmp_path / "groupcodes.xlsx")
    stale_group_file = _write_excel(_groupcodes(25), tmp_path / "updated-groupcodes.xlsx")

    choices = iter((school_file, group_file, stale_group_file))
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *_args: (str(next(choices)), "Excel Files (*.xlsx)")),
    )
    notices: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        staticmethod(lambda _parent, _title, message: notices.append(message)),
    )
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda _parent, _title, message: warnings.append(message)),
    )

    tab = DatabaseTab(school_repository=school_repo, groupcode_repository=group_repo)
    try:
        assert school_repo.status().row_count == 0
        # A fresh DB seeds 33 built-in SSoT groupcodes; explicit import replaces them.
        assert group_repo.status().version_tag == "builtin:ssot"
        assert group_repo.status().imported_at is None
        tab._schools_button.click()
        tab._groupcodes_button.click()
        app.processEvents()
        assert len(notices) == 2 and not warnings
        assert school_repo.status().row_count == 1
        assert group_repo.status().row_count == 1
        assert group_repo.status().imported_at is not None
        assert set(group_repo.load_canonical_frame()["group_code"].astype(int)) == {24}

        # Build uses precisely the references just persisted by the Qt Database action.
        matrix_path = _build_matrix(tmp_path=tmp_path, db_path=db_path, group_code=24)
        assert _matrix_group_values(matrix_path) == {24}
        build_qa = tmp_path / "matrix_vs_students_validation.xlsx"
        assert build_qa.exists()
        with pd.ExcelFile(build_qa) as qa_book:
            assert "summary" in qa_book.sheet_names
            assert not pd.read_excel(qa_book, "summary").empty

        # The public source archive deliberately excludes the legacy XLSX mapping.
        # Supply an explicitly synthetic profile rather than leaking a real workbook.
        profile_path = tmp_path / "synthetic-sabt-profile.xlsx"
        pd.DataFrame(
            {
                sabt_exports._HEADER_COLUMN: [
                    "کد ثبت نام0",
                    "پیدا کردن ردیف پشتیبان از فیلد 141",
                ],
                sabt_exports._VALUE_COLUMN: ["student_id", ""],
                sabt_exports._ORDER_COLUMN: [1, 2],
                sabt_exports._SOURCE_COLUMN: [
                    sabt_exports._SOURCE_STUDENT,
                    sabt_exports._SOURCE_ALLOCATION,
                ],
            }
        ).to_excel(
            profile_path, sheet_name=sabt_exports._PROFILE_SHEET_NAME, index=False
        )
        students_file = _write_excel(_student(24), tmp_path / "students.xlsx")
        allocation_path = tmp_path / "allocation.xlsx"
        sabt_path = tmp_path / "sabt.xlsx"
        common = [
            "allocate",
            "--students",
            str(students_file),
            "--pool",
            str(matrix_path),
            "--pool-type",
            "matrix",
            "--pool-sheet",
            "matrix",
            "--policy",
            str(POLICY_PATH),
            "--academic-year",
            "1404",
            "--counter-duplicate-strategy",
            "assign-new",
            "--export-profile-path",
            str(profile_path),
            "--output",
            str(allocation_path),
            "--sabt-output",
            str(sabt_path),
            "--sabt-template",
            str(tmp_path / "synthetic-template.xlsx"),
            "--local-db",
            str(db_path),
        ]
        settings = {"user_settings": UserSettings(enable_trace_export=True)}
        assert cli_legacy.main(common, ui_overrides=settings) == 0
        assert allocation_path.exists() and sabt_path.exists()

        with pd.ExcelFile(allocation_path) as alloc_book:
            assert {"allocations", "logs", "updated_pool", "trace"}.issubset(
                alloc_book.sheet_names
            )
            allocations = pd.read_excel(alloc_book, "allocations", dtype=str)
            logs = pd.read_excel(alloc_book, "logs", dtype=str)
            trace = pd.read_excel(alloc_book, "trace", dtype=str)
        assert len(allocations) == 1
        allocated_id = str(allocations.loc[0, "student_id"])
        assert allocated_id and allocated_id.lower() != "nan"
        assert "success" in set(logs["allocation_status"])
        assert trace.loc[trace["student_id"] == allocated_id, "stage"].tolist() == list(
            CANONICAL_TRACE_ORDER
        )

        allocation_qa = tmp_path / "allocation_validation.xlsx"
        with pd.ExcelFile(allocation_qa) as qa_book:
            assert "summary" in qa_book.sheet_names
            qa_summary = pd.read_excel(qa_book, "summary")
            assert not qa_summary.empty
            assert set(qa_summary["status"]) <= {"PASS", "WARN"}

        with pd.ExcelFile(sabt_path) as sabt_book:
            assert {"Sheet2", "Summary", "Errors"}.issubset(sabt_book.sheet_names)
            sheet2 = pd.read_excel(sabt_book, "Sheet2", dtype=str)
            assert len(sheet2) == 1
            assert str(sheet2.loc[0, "شناسه دانش آموز"]) == allocated_id
            assert str(sheet2.loc[0, "کد ملی"]) == "0000000001"

        # After a real reference update, stale student data must be blocked and
        # must not overwrite the prior verified outputs.
        original = {
            path: sha256(path.read_bytes()).hexdigest()
            for path in (allocation_path, sabt_path)
        }
        tab._groupcodes_button.click()
        app.processEvents()
        assert set(group_repo.load_canonical_frame()["group_code"].astype(int)) == {25}
        with pytest.raises(ValueError, match="Unknown group code"):
            cli_legacy.main(common, ui_overrides=settings)
        assert all(
            sha256(path.read_bytes()).hexdigest() == digest
            for path, digest in original.items()
        )
        assert not warnings
    finally:
        tab.close()
        app.processEvents()
        db.close_all_connections()


def test_excel_student_import_mixed_national_codes_to_sabt_readback(tmp_path: Path) -> None:
    """Real Excel reader + DB-backed student import + keyed Sabt export/readback."""
    from openpyxl import load_workbook

    from app.infra.excel.import_to_sabt import (
        ImportToSabtExportError,
        build_errors_frame,
        build_sheet2_frame,
        build_summary_frame,
        ensure_template_workbook,
        load_exporter_config,
        prepare_allocation_export_frame,
        write_import_to_sabt_excel,
    )
    from app.infra.reference_students_repository import import_student_report_from_excel

    db_path, _, _ = _prepare_reference_db(tmp_path, group_code=24)
    students_raw = pd.concat([_student(24)] * 3, ignore_index=True)
    students_raw["student_id"] = ["S-1", "S-2", "S-3"]
    students_raw["کد ملی"] = ["0000000001", "0000000002", "0000000003"]
    students_raw["GF_NationalCode"] = ["۰۰۱۲۳۴۵۶۷۸", "", None]
    excel_path = _write_excel(students_raw, tmp_path / "mixed-student-report.xlsx")

    db = LocalDatabase(db_path)
    policy = load_policy()
    students = import_student_report_from_excel(excel_path, db=db, policy=policy)
    assert len(students) == 3
    assert "student_id" in students.columns

    # Allocation order intentionally differs from Excel source order.
    allocations = pd.DataFrame(
        {"student_id": ["S-2", "S-1", "S-3"], "mentor_id": ["M-1"] * 3}
    )
    mentors = pd.DataFrame({"mentor_id": ["M-1"], "mentor_name": ["Synthetic"]})

    with pytest.raises(ImportToSabtExportError, match="LAW/EXPORT-SSOT-ID-01"):
        prepare_allocation_export_frame(
            allocations,
            students,
            mentors,
            student_ids=pd.Series(["S-1", "S-2", "S-3"], index=[10, 11, 12]),
        )

    merged = prepare_allocation_export_frame(allocations, students, mentors)
    assert merged["student_id"].tolist() == ["S-2", "S-1", "S-3"]
    cfg = load_exporter_config("config/SmartAlloc_Exporter_Config_v1.json")
    sheet = build_sheet2_frame(merged, cfg)
    assert sheet["شناسه دانش آموز"].tolist() == ["S-2", "S-1", "S-3"]
    assert sheet["کد ملی"].tolist() == [
        "0000000002",
        "0012345678",
        "0000000003",
    ]

    summary = build_summary_frame(
        cfg, total_students=3, allocated_count=3, error_count=0
    )
    errors = build_errors_frame(
        pd.DataFrame({"student_id": ["S-1"], "allocation_status": ["success"]}),
        cfg,
    )
    template = tmp_path / "mixed-sabt-template.xlsx"
    output = tmp_path / "mixed-sabt.xlsx"
    ensure_template_workbook(template, cfg)
    write_import_to_sabt_excel(sheet, summary, errors, None, None, template, output)
    workbook = load_workbook(output, read_only=True, data_only=True)
    try:
        actual_rows = list(workbook["Sheet2"].values)
    finally:
        workbook.close()
    columns = list(actual_rows[0])
    id_idx = columns.index("شناسه دانش آموز")
    national_idx = columns.index("کد ملی")
    assert [(row[id_idx], row[national_idx]) for row in actual_rows[1:]] == [
        ("S-2", "0000000002"),
        ("S-1", "0012345678"),
        ("S-3", "0000000003"),
    ]
    db.close_all_connections()


def test_mainwindow_real_gui_build_allocate_sabt_and_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Actual C2 GUI buttons -> Qt Workers -> CLI -> Excel; native dialogs stubbed.

    Private historical Sabt profiles are intentionally not part of the uv source
    archive. The only supplied profile here is created from synthetic columns.
    """
    import time
    from hashlib import sha256

    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

    from app.core.common.types import CANONICAL_TRACE_ORDER
    from app.infra.config_flags import UserSettings
    from app.infra.excel import export_allocations as sabt_exports
    from app.ui import main_window_base as window_base
    from app.ui.main_window import MainWindow

    monkeypatch.setattr(
        window_base,
        "YearDatabaseManager",
        lambda _root: YearDatabaseManager(tmp_path / "years"),
    )
    app = QApplication.instance() or QApplication([])
    school_file = _write_excel(_schools(), tmp_path / "gui-schools.xlsx")
    group_file = _write_excel(_groupcodes(24), tmp_path / "gui-groups.xlsx")
    changed_groups = _write_excel(_groupcodes(25), tmp_path / "gui-stale-groups.xlsx")
    inspactor_file = _write_excel(_inspactor(24), tmp_path / "gui-inspactor.xlsx")
    students_file = _write_excel(_student(24), tmp_path / "gui-students.xlsx")
    profile_file = tmp_path / "authorized-synthetic-profile.xlsx"
    pd.DataFrame(
        {
            sabt_exports._HEADER_COLUMN: [
                "کد ثبت نام0",
                "پیدا کردن ردیف پشتیبان از فیلد 141",
            ],
            sabt_exports._VALUE_COLUMN: ["student_id", ""],
            sabt_exports._ORDER_COLUMN: [1, 2],
            sabt_exports._SOURCE_COLUMN: [
                sabt_exports._SOURCE_STUDENT,
                sabt_exports._SOURCE_ALLOCATION,
            ],
        }
    ).to_excel(profile_file, sheet_name=sabt_exports._PROFILE_SHEET_NAME, index=False)

    matrix = tmp_path / "gui-matrix.xlsx"
    allocation = tmp_path / "gui-allocation.xlsx"
    sabt = tmp_path / "gui-sabt.xlsx"
    file_choices = iter([school_file, group_file, profile_file, changed_groups])
    chosen_files: list[str] = []

    def choose_file(*_args: object) -> tuple[str, str]:
        path = str(next(file_choices))
        chosen_files.append(path)
        return path, "Excel (*.xlsx)"

    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(choose_file)
    )
    notices: list[str] = []
    warnings: list[str] = []
    async_errors: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        staticmethod(lambda _parent, _title, detail: notices.append(str(detail))),
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda _parent, _title, detail: warnings.append(str(detail))),
    )
    window = MainWindow()
    window._show_async_message = lambda _icon, _title, detail: async_errors.append(
        str(detail)
    )
    window._user_settings = UserSettings(enable_trace_export=True)
    window._prefs.output_root_dir = str(tmp_path / "gui-outputs")
    window._prefs.last_output_dir = ""  # isolate persisted C2 run pointer

    def wait_for_terminal(expected: str) -> None:
        deadline = time.monotonic() + 90
        observed = []
        while time.monotonic() < deadline:
            running = window._worker
            if running is not None and running not in observed:
                observed.append(running)
            app.processEvents()
            if window._worker is None and window._operation_state == expected:
                break
            time.sleep(0.02)
        assert window._worker is None, "GUI Worker did not complete"
        assert window._operation_state == expected, (
            expected, window._operation_state, async_errors, warnings
        )
        for worker in observed:
            assert worker.wait(5000), "Qt worker did not terminate"

    try:
        window.show()
        app.processEvents()
        assert window.activate_surface("database")
        tab = window._database_tab
        assert tab is not None
        tab._schools_button.click()
        tab._groupcodes_button.click()
        assert len(notices) == 2 and not warnings
        assert window._school_repository.status().row_count == 1
        assert window._groupcode_repository.status().row_count == 1
        assert "24" in tab._groupcodes_status_label.text() or (
            set(window._groupcode_repository.load_canonical_frame()["group_code"].astype(int))
            == {24}
        )

        assert window.activate_surface("build")
        window._picker_inspactor.setText(str(inspactor_file))
        window._picker_output_matrix.setText(str(matrix))
        window._btn_build.click()
        wait_for_terminal("completed")
        assert matrix.is_file()
        assert _matrix_group_values(matrix) == {24}
        assert window._prefs.last_matrix_path == str(matrix)

        assert window.activate_surface("allocate")
        window._picker_students.setText(str(students_file))
        window._picker_pool.setText(str(matrix))
        # Selecting a real pool starts an asynchronous manager-name ExcelLoader.
        # GUI controls are intentionally disabled until this loader finishes.
        loaders = list(window._excel_loaders)
        deadline = time.monotonic() + 20
        while window._excel_loaders and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.02)
        assert not window._excel_loaders, "Manager-name loader did not finish"
        for loader in loaders:
            assert loader.wait(5000)
        app.processEvents()
        window._picker_alloc_out.setText(str(allocation))
        window._combo_academic_year.setCurrentText("1404")
        window._picker_sabt_output_alloc.setText(str(sabt))
        # Exercise the actual FilePicker click; only the native OS dialog is stubbed.
        assert window._picker_sabt_profile_alloc.isEnabled()
        assert window._picker_sabt_profile_alloc._button.isEnabled()
        window._picker_sabt_profile_alloc._button.click()
        assert window._picker_sabt_profile_alloc.text() == str(profile_file), (
            chosen_files, window._picker_sabt_profile_alloc.text()
        )
        window._picker_sabt_template_alloc.setText("")
        # An unrelated valid workbook in an explicit output directory is not
        # a generated-template target, even when its name matches the old default.
        from openpyxl import Workbook, load_workbook

        sentinel = tmp_path / "sabt-template.xlsx"
        sentinel_book = Workbook()
        sentinel_book.active["A1"] = "SYNTHETIC USER WORKBOOK - DO NOT MODIFY"
        sentinel_book.save(sentinel)
        sentinel_hash = sha256(sentinel.read_bytes()).hexdigest()
        window._optional_roster.setChecked(True)
        window._academic_year_confirm.click()
        window._btn_allocate.click()
        wait_for_terminal("completed")

        assert allocation.is_file() and sabt.is_file()
        generated = list(tmp_path.glob("sabt-template-*/sabt-template.xlsx"))
        assert len(generated) == 1 and generated[0].is_file()
        assert generated[0].resolve() != sabt.resolve()
        assert sha256(sentinel.read_bytes()).hexdigest() == sentinel_hash
        verified_sentinel = load_workbook(sentinel, read_only=True)
        try:
            assert verified_sentinel.active["A1"].value == "SYNTHETIC USER WORKBOOK - DO NOT MODIFY"
        finally:
            verified_sentinel.close()
        with pd.ExcelFile(allocation) as book:
            assert {"allocations", "logs", "updated_pool", "trace"}.issubset(
                book.sheet_names
            )
            allocations = pd.read_excel(book, "allocations", dtype=str)
            trace = pd.read_excel(book, "trace", dtype=str)
        student_id = str(allocations.loc[0, "student_id"])
        assert student_id and student_id.lower() != "nan"
        assert trace.loc[trace["student_id"] == student_id, "stage"].tolist() == list(
            CANONICAL_TRACE_ORDER
        )

        qa_file = tmp_path / "gui-allocation_validation.xlsx"
        assert qa_file.is_file()
        with pd.ExcelFile(qa_file) as book:
            qa = pd.read_excel(book, "summary")
        assert not qa.empty
        assert set(qa["status"]) <= {"PASS", "WARN"}
        with pd.ExcelFile(sabt) as book:
            assert {"Sheet2", "Summary", "Errors"}.issubset(book.sheet_names)
            sheet2 = pd.read_excel(book, "Sheet2", dtype=str)
        assert len(sheet2) == 1
        assert sheet2.loc[0, "شناسه دانش آموز"] == student_id
        assert sheet2.loc[0, "کد ملی"] == "0000000001"

        # Reuse this actual GUI -> Worker -> CLI allocation. Verify its audit
        # across an independently reopened SQLite connection and the operator
        # toolbar, rather than constructing a second E2E fixture.
        assert window._local_db is not None
        history_db_path = window._local_db.path
        window._local_db.close_all_connections()
        reopened_db = LocalDatabase(history_db_path)
        matching_runs = [
            row
            for row in reopened_db.fetch_runs()
            if row["entrypoint"] == "allocate"
            and row["status"] == "success"
            and json.loads(row["input_files_json"])["output"] == str(allocation)
        ]
        assert len(matching_runs) == 1
        saved_run = matching_runs[0]
        run_id = int(saved_run["id"])
        assert saved_run["run_uuid"]
        assert int(saved_run["total_allocated"]) == len(allocations)
        assert json.loads(saved_run["input_hashes_json"])["students"] == sha256(
            students_file.read_bytes()
        ).hexdigest()

        saved_trace, _saved_summary, _history_info = reopened_db.fetch_trace_snapshot(run_id)
        assert saved_trace is not None
        assert len(saved_trace) == len(trace)
        assert saved_trace["student_id"].astype(str).eq(student_id).all()
        assert saved_trace["stage"].tolist() == list(CANONICAL_TRACE_ORDER)
        saved_qa, _saved_details, _saved_extras = reopened_db.fetch_qa_snapshot(run_id)
        assert saved_qa is not None and not saved_qa.empty
        # Metrics are a separate opt-in feature, disabled for this run.
        assert reopened_db.fetch_metrics_for_run(run_id) == []

        window._local_db = reopened_db
        history_action = window._support_toolbar_actions["run_history"]
        assert history_action.objectName() == "actionRunHistory"
        assert history_action.isVisible()
        history_action.trigger()
        dialog = window._run_history_dialog
        assert dialog is not None and dialog.isVisible()
        index = next(i for i, row in enumerate(dialog._runs) if int(row["id"]) == run_id)
        dialog._run_list.setCurrentRow(index)
        assert dialog.trace_model.rowCount() == len(saved_trace)
        assert dialog.qa_summary_model.rowCount() == len(saved_qa)
        from PySide6.QtCore import Qt

        trace_headers = [
            dialog.trace_model.headerData(i, Qt.Orientation.Horizontal)
            for i in range(dialog.trace_model.columnCount())
        ]
        assert "student_id" in trace_headers
        student_column = trace_headers.index("student_id")
        assert student_id in {
            dialog.trace_model.data(dialog.trace_model.index(i, student_column))
            for i in range(dialog.trace_model.rowCount())
        }
        dialog.close()

        # Reenter through the same real action: no cached in-memory run list.
        history_action.trigger()
        second_dialog = window._run_history_dialog
        assert second_dialog is not None and second_dialog is not dialog
        index = next(i for i, row in enumerate(second_dialog._runs) if int(row["id"]) == run_id)
        second_dialog._run_list.setCurrentRow(index)
        assert second_dialog.trace_model.rowCount() == len(saved_trace)
        assert second_dialog.qa_summary_model.rowCount() == len(saved_qa)
        second_dialog.close()

        assert window._prefs.last_alloc_output == str(allocation)
        assert window._toolbar_actions["output"].isEnabled()
        from PySide6.QtGui import QDesktopServices

        opened_folders: list[str] = []
        monkeypatch.setattr(
            QDesktopServices,
            "openUrl",
            staticmethod(lambda url: opened_folders.append(url.toLocalFile())),
        )
        window._toolbar_actions["output"].trigger()
        assert [Path(folder) for folder in opened_folders] == [tmp_path]
        assert not warnings and not async_errors

        original_hashes = {
            path: sha256(path.read_bytes()).hexdigest() for path in (allocation, sabt)
        }
        # Each rejected role collision must stop *before preflight* and leave
        # previous outputs plus all synthetic input workbooks byte-identical.
        # Existing-output replacement is still permitted when roles differ.
        from shutil import copyfile

        qa_profile = tmp_path / "qa_guard_validation.xlsx"
        copyfile(profile_file, qa_profile)
        protected_policy = tmp_path / "reports" / "unknown_data_report.json"
        protected_policy.parent.mkdir(exist_ok=True)
        copyfile(POLICY_PATH, protected_policy)
        protected = {
            path: sha256(path.read_bytes()).hexdigest()
            for path in (
                allocation, sabt, profile_file, students_file, matrix,
                sentinel, qa_profile, protected_policy,
            )
        }
        inputs = [
            window._picker_students,
            window._picker_pool,
            window._picker_alloc_out,
            window._picker_sabt_output_alloc,
            window._picker_sabt_template_alloc,
            window._picker_sabt_profile_alloc,
            window._picker_policy_allocate,
            window._picker_sabt_config_alloc,
        ]
        baseline_paths = {picker: picker.text() for picker in inputs}
        cases = [
            ("sabt vs profile", window._picker_sabt_output_alloc, str(profile_file)),
            ("sabt vs allocation", window._picker_sabt_output_alloc, str(allocation)),
            ("template vs sabt", window._picker_sabt_template_alloc, str(sabt)),
            ("template vs profile", window._picker_sabt_template_alloc, str(profile_file)),
            ("template vs student", window._picker_sabt_template_alloc, str(students_file)),
            ("sabt vs student", window._picker_sabt_output_alloc, str(students_file)),
            ("allocation vs student", window._picker_alloc_out, str(students_file)),
            ("allocation vs profile", window._picker_alloc_out, str(profile_file)),
            ("sabt vs config", window._picker_sabt_output_alloc,
             window._picker_sabt_config_alloc.text()),
            ("QA vs profile", window._picker_alloc_out, str(tmp_path / "qa_guard.xlsx")),
            ("preflight vs policy", window._picker_policy_allocate, str(protected_policy)),
        ]
        original_cli = window_base.cli.main
        launched_cli: list[str] = []

        def deny_cli(_argv: object, **_kwargs: object) -> int:
            launched_cli.append(str(_argv))
            raise AssertionError("Unsafe path collision must not launch CLI")

        window._academic_year_confirm.click()
        try:
            window_base.cli.main = deny_cli
            for case_name, picker, path in cases:
                for control, original_path in baseline_paths.items():
                    control.setText(original_path)
                if case_name == "QA vs profile":
                    window._picker_sabt_profile_alloc.setText(str(qa_profile))
                if case_name == "preflight vs policy":
                    window._picker_alloc_out.setText(str(tmp_path / "guard.xlsx"))
                picker.setText(path)
                prior_warnings = len(warnings)
                window._btn_allocate.click()
                assert window._worker is None, case_name
                assert len(warnings) == prior_warnings + 1, case_name
                assert not launched_cli, case_name
                assert all(
                    sha256(file.read_bytes()).hexdigest() == digest
                    for file, digest in protected.items()
                ), case_name
        finally:
            window_base.cli.main = original_cli
            for control, original_path in baseline_paths.items():
                control.setText(original_path)
        assert all(
            sha256(file.read_bytes()).hexdigest() == digest
            for file, digest in protected.items()
        )

        # A clean uv archive has no historical profile; missing user input must
        # be stopped before starting another Worker or overwriting prior output.
        window._picker_sabt_profile_alloc.setText("")
        window._btn_allocate.click()
        assert window._worker is None
        assert warnings and "Sabt" in warnings[-1]
        assert all(sha256(path.read_bytes()).hexdigest() == digest
                   for path, digest in original_hashes.items())

        # Real Database action changes the authoritative references; the same
        # GUI Allocate input is stale and cannot replace successful output.
        window._picker_sabt_profile_alloc.setText(str(profile_file))
        assert window.activate_surface("database")
        tab._groupcodes_button.click()
        assert set(window._groupcode_repository.load_canonical_frame()["group_code"].astype(int)) == {25}
        assert window.activate_surface("allocate")
        assert window._academic_year_confirm.isChecked()
        window._btn_allocate.click()
        wait_for_terminal("failed")
        assert all(sha256(path.read_bytes()).hexdigest() == digest
                   for path, digest in original_hashes.items())
        assert warnings or async_errors
    finally:
        window.close()
        app.processEvents()
        if window._local_db is not None:
            window._local_db.close_all_connections()

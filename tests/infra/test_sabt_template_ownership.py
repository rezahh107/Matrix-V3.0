"""File ownership regressions for the real Sabt workbook preparer (synthetic only)."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from tempfile import mkdtemp

from openpyxl import Workbook, load_workbook

from app.infra.excel.import_to_sabt import ensure_template_workbook, load_exporter_config


def _synthetic_workbook(path: Path) -> None:
    workbook = Workbook()
    workbook.active.title = "Sheet2"
    workbook.active["A1"] = "UNRELATED SYNTHETIC WORKBOOK"
    workbook.save(path)
    workbook.close()


def test_auto_template_in_unique_directory_preserves_existing_workbook(tmp_path: Path) -> None:
    """Actual exporter must not touch the unrelated fixed-name sentinel."""
    cfg = load_exporter_config("config/SmartAlloc_Exporter_Config_v1.json")
    sentinel = tmp_path / "sabt-template.xlsx"
    _synthetic_workbook(sentinel)
    digest = sha256(sentinel.read_bytes()).hexdigest()

    generated = Path(mkdtemp(prefix="sabt-template-", dir=tmp_path)) / "sabt-template.xlsx"
    ensure_template_workbook(generated, cfg)

    assert generated.is_file() and generated != sentinel
    assert sha256(sentinel.read_bytes()).hexdigest() == digest
    workbook = load_workbook(sentinel, read_only=True)
    try:
        assert workbook["Sheet2"]["A1"].value == "UNRELATED SYNTHETIC WORKBOOK"
    finally:
        workbook.close()



def test_selected_template_still_has_existing_in_place_update_contract(tmp_path: Path) -> None:
    """An explicitly selected workbook remains an in-place template input."""
    cfg = load_exporter_config("config/SmartAlloc_Exporter_Config_v1.json")
    selected = tmp_path / "operator-selected-template.xlsx"
    _synthetic_workbook(selected)
    before = sha256(selected.read_bytes()).hexdigest()

    ensure_template_workbook(selected, cfg)

    assert sha256(selected.read_bytes()).hexdigest() != before
    workbook = load_workbook(selected, read_only=True)
    try:
        assert {"Sheet2", "Summary", "Errors"}.issubset(workbook.sheetnames)
        assert workbook["Sheet2"]["A1"].value != "UNRELATED SYNTHETIC WORKBOOK"
    finally:
        workbook.close()

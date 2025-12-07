from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "ci" / "law_ssot_drift_guard.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("law_ssot_drift_guard", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def test_doc_changes_without_code_are_blocked():
    module = _load_module()
    ok, doc_changes = module.check_doc_drift(["docs/LAW_Smart_Student_Allocation_v3.0.md"])
    assert not ok
    assert doc_changes == ["docs/LAW_Smart_Student_Allocation_v3.0.md"]


def test_doc_changes_with_code_changes_allowed():
    module = _load_module()
    ok, doc_changes = module.check_doc_drift(
        [
            "docs/Technical_SSoT_Smart_Student_Allocation_v3.0-TECH.md",
            "app/core/allocator.py",
        ]
    )
    assert ok
    assert doc_changes == ["docs/Technical_SSoT_Smart_Student_Allocation_v3.0-TECH.md"]


def test_non_doc_changes_are_allowed():
    module = _load_module()
    ok, doc_changes = module.check_doc_drift(["app/core/example.py"])
    assert ok
    assert doc_changes == []

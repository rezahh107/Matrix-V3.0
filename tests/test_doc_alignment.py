from __future__ import annotations

from pathlib import Path

import json

import pytest

DOC_EXPECTATIONS: dict[Path, list[str]] = {
    Path("docs/LAW_Smart_Student_Allocation_v3.0.md"): [
        "قانون GROUP-CODE-01",
        "group_code` تنها کلید کاننیکال",
        "قانون FINANCE-01",
        "ALIAS-01",
        "SCHOOL-REF-01",
    ],
    Path("docs/Technical_SSoT_Smart_Student_Allocation_v3.0-TECH.md"): [
        "DB-backed",
        "HeaderPipelineV3",
        "وضعیت ثبت نام",
        "alias = mentor_id",
        "group_code` تنها کلید کاننیکال",
    ],
    Path("docs/Repository Specification (SSoT).md"): [
        "SchoolReport",
        "crosswalk",
        "Database/Reference",
    ],
    Path("docs/📚 Refactor Narrative v3.0 — روایت کامل و ماشین‌فهم از مسأله تا راه‌حل.md"): [
        "Refactor Narrative v3.0",
        "Reference DB",
        "Concept / Canonical Frame / Channel",
        "group_code",
        "School",
    ],
}


@pytest.mark.parametrize("doc_path, keywords", DOC_EXPECTATIONS.items())
def test_updated_docs_present(doc_path: Path, keywords: list[str]) -> None:
    assert doc_path.exists(), f"missing expected doc: {doc_path}"
    content = doc_path.read_text(encoding="utf-8")
    for keyword in keywords:
        assert (
            keyword in content
        ), f"expected '{keyword}' to appear in {doc_path} after documentation update"


@pytest.mark.parametrize(
    ("doc_path", "start", "stop"),
    [
        (Path("docs/LAW_Smart_Student_Allocation_v3.0.md"), "**ترتیب قطعی انتخاب منتور:**", "\n---"),
        (Path("docs/Technical_SSoT_Smart_Student_Allocation_v3.0-TECH.md"), "**رتبه‌بندی:**", "\n---"),
        (Path("docs/LAW v3.0 — Regulatory Coverage Map v1.0.md"), "- ترتیب انتخاب منتور:", "\n------"),
        (Path("docs/Repository Specification (SSoT).md"), "Mentor ranking uses the Owner-approved order:", "\n\n**TRACE-CORE**"),
        (Path("docs/Phase_0_System_Requirements_v2.5_Final.md"), "**FR-CHAN-03", "\n"),
    ],
)
def test_rank_core_three_criterion_docs(doc_path: Path, start: str, stop: str) -> None:
    """Keep the Owner-approved ordering aligned across directly normative references."""
    text = doc_path.read_text(encoding="utf-8")
    assert start in text, doc_path
    snippet = text.split(start, 1)[1].split(stop, 1)[0]
    ordering = ("remaining_capacity", "allocations_new", "mentor_sort_key")
    indices = [snippet.find(key) for key in ordering]
    assert all(index >= 0 for index in indices), (doc_path, indices)
    assert indices == sorted(indices), (doc_path, indices)


def test_rank_core_machine_spec_preserves_historical_audit_as_superseded() -> None:
    spec = json.loads(Path("docs/Repository_Spec_SSoT.json").read_text(encoding="utf-8"))
    rule = next(item for item in spec["invariants"] if item["id"] == "RANK-CORE")
    keys = ("remaining_capacity", "allocations_new", "mentor_sort_key")
    indices = [rule["description"].find(key) for key in keys]
    assert all(index >= 0 for index in indices) and indices == sorted(indices)
    historical = next(
        item for item in spec["discrepancies"] if item["id"] == "DISC-RANK-CORE-OCCUPANCY"
    )
    assert historical["status"] == "historical_superseded"
    assert "not a current P0" in historical["description"]

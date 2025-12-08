from __future__ import annotations

from pathlib import Path

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

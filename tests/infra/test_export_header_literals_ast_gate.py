from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.core.common.columns import CANON_EN_TO_FA


def _docstring_positions(node: ast.AST) -> set[tuple[int, int]]:
    positions: set[tuple[int, int]] = set()

    def _collect(body_node: ast.AST) -> None:
        if isinstance(body_node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if (
                body_node.body
                and isinstance(body_node.body[0], ast.Expr)
                and isinstance(body_node.body[0].value, ast.Constant)
                and isinstance(body_node.body[0].value.value, str)
            ):
                positions.add((body_node.body[0].value.lineno, body_node.body[0].value.col_offset))
            for child in body_node.body:
                _collect(child)

    _collect(node)
    return positions


def test_export_allocations_has_no_canonical_header_literals() -> None:
    path = Path("app/infra/excel/export_allocations.py")
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    docstring_positions = _docstring_positions(tree)
    forbidden_literals = set(CANON_EN_TO_FA.values())

    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            position = (node.lineno, node.col_offset)
            if position in docstring_positions:
                continue
            if node.value in forbidden_literals:
                offenders.append(f"{path}:{node.lineno}")

    if offenders:
        pytest.fail(
            "export_allocations.py contains canonical Persian header literals: "
            + ", ".join(sorted(offenders))
        )


def test_export_allocations_header_pipeline_only() -> None:
    path = Path("app/infra/excel/export_allocations.py")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    imports: set[str] = set()
    names: set[str] = set()
    resolve_calls = 0

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute) and node.attr == "resolve":
            resolve_calls += 1

    assert "HeaderPipelineV3" in names, "HeaderPipelineV3 must be imported in export_allocations.py"
    assert any(
        module.endswith("header_pipeline_v3") for module in imports
    ), "export_allocations.py must import HeaderPipelineV3"
    assert resolve_calls > 0, "export_allocations.py must call .resolve at least once"

    forbidden_symbols = {"canonicalize_headers", "CANON_EN_TO_FA"}
    assert not forbidden_symbols.intersection(imports), "Forbidden header helpers imported"
    assert "CANON_EN_TO_FA" not in names, "Forbidden canonical header registry referenced"

"""AST gate to prevent positional attachment to allocations_df.student_id."""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

EXPORT_FILES = [
    Path("app/infra/cli_legacy.py"),
    Path("app/infra/excel/export_allocations.py"),
    Path("app/infra/excel/import_to_sabt.py"),
]
FORBIDDEN_ATTRS = {"reindex", "iloc", "iat", "values", "to_numpy", "reset_index"}
TARGET_BASE_NAMES = {"allocations_df", "allocation_df", "allocations"}


def _slice_has_student_id(slice_node: ast.AST) -> bool:
    if isinstance(slice_node, ast.Constant):
        return slice_node.value == "student_id"
    if isinstance(slice_node, ast.Index):  # pragma: no cover - Python <3.9 compatibility
        return isinstance(slice_node.value, ast.Constant) and slice_node.value.value == "student_id"
    if isinstance(slice_node, ast.Tuple):
        return any(_slice_has_student_id(elt) for elt in slice_node.elts)
    return False


def _extract_base_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _target_is_allocations_student_id(target: ast.AST) -> bool:
    if not isinstance(target, ast.Subscript):
        return False
    if not _slice_has_student_id(target.slice):
        return False
    base_node = target.value
    if isinstance(base_node, ast.Attribute) and base_node.attr in {"loc", "iloc", "iat"}:
        base_node = base_node.value
    base_name = _extract_base_name(base_node)
    return base_name in TARGET_BASE_NAMES


def _rhs_has_forbidden(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and child.attr in FORBIDDEN_ATTRS:
            return True
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Attribute) and func.attr in {"reindex", "reset_index", "to_numpy"}:
                return True
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "array"
                and isinstance(func.value, ast.Name)
                and func.value.id in {"np", "numpy"}
            ):
                return True
        if (
            isinstance(child, ast.Subscript)
            and isinstance(child.value, ast.Attribute)
            and child.value.attr in {"iloc", "iat"}
        ):
            return True
    return False


def _iter_assignments(tree: ast.AST) -> Iterable[tuple[list[ast.AST], ast.AST, int]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            yield list(node.targets), node.value, node.lineno
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            target = getattr(node, "target", None)
            value = getattr(node, "value", None)
            if target is not None and value is not None:
                yield [target], value, node.lineno


def test_no_positional_allocations_student_id_assignments() -> None:
    offenders: list[str] = []

    for path in EXPORT_FILES:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for targets, value, lineno in _iter_assignments(tree):
            if any(_target_is_allocations_student_id(target) for target in targets) and _rhs_has_forbidden(
                value
            ):
                offenders.append(f"{path}:{lineno}")

    assert not offenders, (
        "LAW/EXPORT-SSOT-ID-01 violation: allocations_df.student_id assignment uses positional alignment; "
        f"offenders={offenders}"
    )

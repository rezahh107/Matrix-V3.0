"""AST gate ensuring student_id is never attached via positional/index alignment.

RULE: ID-SSOT-NO-POSITIONAL-ATTACH (LAW/EXPORT-SSOT-ID-01)
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

FORBIDDEN_ATTRS = {"reindex", "iloc", "iat", "values", "to_numpy"}
TARGET_DIRS = [Path("app/infra"), Path("app/ui")]


def _is_student_id_target(target: ast.AST) -> bool:
    if not isinstance(target, ast.Subscript):
        return False
    slice_node = target.slice
    if isinstance(slice_node, ast.Constant):
        return slice_node.value == "student_id"
    if isinstance(slice_node, ast.Index):  # pragma: no cover - Python <3.9 compatibility
        return isinstance(slice_node.value, ast.Constant) and slice_node.value.value == "student_id"
    return False


def _rhs_has_forbidden(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and child.attr in FORBIDDEN_ATTRS:
            return True
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Attribute) and func.attr == "reindex":
                return True
        if isinstance(child, ast.Subscript) and isinstance(child.value, ast.Attribute) and (
            child.value.attr in {"iloc", "iat"}
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


def test_no_positional_student_id_attachment_patterns() -> None:
    offenders: list[str] = []

    for root in TARGET_DIRS:
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            for targets, value, lineno in _iter_assignments(tree):
                if any(_is_student_id_target(target) for target in targets) and _rhs_has_forbidden(value):
                    offenders.append(f"{path}:{lineno}")

    assert not offenders, (
        "ID-SSOT-NO-POSITIONAL-ATTACH violation: student_id assignment uses positional alignment; "
        f"offenders={offenders}"
    )

from __future__ import annotations

import ast
import tokenize
from pathlib import Path

from app.core.common.columns import CANON_EN_TO_FA
from app.core.common.types import CANONICAL_JOIN_KEYS

REPO_ROOT = Path(__file__).resolve().parents[3]
CORE_ROOT = REPO_ROOT / "app" / "core"

ALLOWLIST = {
    # JoinKeyResolver is the only Core surface permitted to inspect raw join-key columns
    # before they are resolved into effective join keys (INVARIANT-JOIN-03).
    (CORE_ROOT / "common" / "join_resolver.py").resolve(),
}

_EN_JOIN_KEYS = (
    "group_code",
    "group",
    "gender",
    "graduation_status",
    "grad_status",
    "grad_status_code",
    "center",
    "finance",
    "school",
    "school_code",
)
JOIN_KEY_EN_LITERALS = set(_EN_JOIN_KEYS)
JOIN_KEY_LITERALS = set(CANONICAL_JOIN_KEYS)
for key in _EN_JOIN_KEYS:
    fa_value = CANON_EN_TO_FA.get(key)
    if fa_value is None:
        continue
    JOIN_KEY_LITERALS.add(fa_value)
    JOIN_KEY_LITERALS.add(fa_value.replace(" ", "_"))


def _iter_core_python_files() -> list[Path]:
    return sorted(CORE_ROOT.rglob("*.py"))


def _load_ast(path: Path) -> tuple[ast.AST | None, str | None]:
    try:
        with tokenize.open(path) as handle:
            source = handle.read()
        method = "tokenize"
    except (UnicodeDecodeError, SyntaxError, LookupError):
        data = path.read_bytes()
        try:
            source = data.decode("utf-8-sig")
            method = "utf-8-sig"
        except UnicodeDecodeError:
            source = data.decode("utf-8", errors="replace")
            method = "utf-8-replace"

    try:
        return ast.parse(source, filename=str(path)), None
    except (UnicodeDecodeError, SyntaxError) as err:
        try:
            rel = path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            rel = str(path)
        return None, f"{rel} (unreadable via {method}: {err.__class__.__name__}: {err})"


def _extract_literal(value: ast.AST) -> str | None:
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    if hasattr(ast, "Index") and isinstance(value, ast.Index):
        index_value = value.value
        if isinstance(index_value, ast.Constant) and isinstance(index_value.value, str):
            return index_value.value
    return None


def _iter_slice_literals(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Tuple):
        return [literal for element in node.elts for literal in _iter_slice_literals(element)]
    if hasattr(ast, "Index") and isinstance(node, ast.Index):
        return _iter_slice_literals(node.value)
    literal = _extract_literal(node)
    if literal is not None:
        return [literal]
    if isinstance(node, ast.Slice):
        parts = [part for part in (node.lower, node.upper, node.step) if part is not None]
        return [literal for part in parts for literal in _iter_slice_literals(part)]
    if isinstance(node, ast.Call):
        literals: list[str] = []
        for arg in node.args:
            literals.extend(_iter_slice_literals(arg))
        for keyword in node.keywords:
            if keyword.value is not None:
                literals.extend(_iter_slice_literals(keyword.value))
        return literals
    if isinstance(node, ast.Subscript):
        return _iter_slice_literals(node.slice)
    return []


def _find_raw_join_key_literals(tree: ast.AST) -> set[str]:
    violations: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            slice_literals = _iter_slice_literals(node.slice)
            for literal in slice_literals:
                if literal in JOIN_KEY_LITERALS:
                    violations.add(literal)
                if (
                    literal in JOIN_KEY_EN_LITERALS
                    and isinstance(node.slice, ast.Tuple)
                    and _is_axis_selector(node.value)
                ):
                    violations.add(literal)
            continue
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr != "get" or not node.args:
                continue
            literal = _extract_literal(node.args[0])
            if literal in JOIN_KEY_LITERALS:
                violations.add(literal)
    return violations


def _is_axis_selector(node: ast.AST) -> bool:
    if isinstance(node, ast.Attribute):
        return node.attr in {"loc", "iloc", "at", "iat"}
    return False


def test_guard_detects_tuple_slice_literals() -> None:
    source = """
import pandas as pd

rows = [0]
key = "center"

pool = pd.DataFrame({"center": [1], "school_code": [2]})

center_only = pool.loc[rows, "center"]
school_only = pool.loc[:, "school_code"]

ok = pool.loc[rows, key]
"""
    tree = ast.parse(source)
    violations = _find_raw_join_key_literals(tree)
    assert "center" in violations
    assert "school_code" in violations


def test_no_raw_join_key_access_in_core_modules() -> None:
    """JOINKEY-SSOT-03: Core modules must not index join keys directly."""

    violations: list[str] = []
    unreadable: list[str] = []
    for path in _iter_core_python_files():
        resolved = path.resolve()
        if resolved in ALLOWLIST:
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        tree, err = _load_ast(path)
        if err:
            unreadable.append(err)
            continue
        hit_literals = _find_raw_join_key_literals(tree)
        if hit_literals:
            violations.append(f"{rel}: {sorted(hit_literals)}")

    assert not unreadable, (
        "Guard could not decode/parse core files deterministically; "
        "ensure they are valid UTF-8 or contain a correct encoding cookie: "
        f"{sorted(unreadable)}"
    )
    assert not violations, (
        "Raw join-key column indexing detected in core modules; "
        "use Effective Join Keys / resolver helpers instead. "
        f"Violations: {sorted(violations)}"
    )

"""SSOT lock: prevent duplicate alias keys in header registries."""

from __future__ import annotations

import ast
from pathlib import Path


def _find_header_aliases_node(module: ast.Module) -> ast.Dict:
    for node in module.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "HEADER_ALIASES_V3"
            and isinstance(node.value, ast.Dict)
        ):
            return node.value
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "HEADER_ALIASES_V3"
            and isinstance(node.value, ast.Dict)
        ):
            return node.value
    raise AssertionError("HEADER_ALIASES_V3 definition not found as a dict literal")


def _collect_duplicate_keys(dict_node: ast.Dict) -> list[str]:
    duplicates: list[str] = []
    for outer_key_node, inner_value_node in zip(dict_node.keys, dict_node.values):
        if not isinstance(outer_key_node, ast.Constant) or not isinstance(outer_key_node.value, str):
            continue
        if not isinstance(inner_value_node, ast.Dict):
            continue
        seen: set[str] = set()
        for key_node in inner_value_node.keys:
            if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
                continue
            alias_key = key_node.value
            if alias_key in seen:
                duplicates.append(
                    f"HEADER_ALIASES_V3[{outer_key_node.value!r}] duplicate key {alias_key!r} at line {key_node.lineno}"
                )
            else:
                seen.add(alias_key)
    return duplicates


def test_header_aliases_v3_has_no_duplicate_keys() -> None:
    columns_path = Path("app/core/common/columns.py")
    source = columns_path.read_text(encoding="utf-8")
    module = ast.parse(source, filename=str(columns_path))
    aliases_dict = _find_header_aliases_node(module)
    duplicates = _collect_duplicate_keys(aliases_dict)
    assert not duplicates, "\n".join(duplicates)

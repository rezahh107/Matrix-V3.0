from __future__ import annotations

import ast
import tokenize
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ALLOCATION_ROOT = REPO_ROOT / "app" / "core" / "allocation"

JOIN_KEY_LITERALS = {
    "کدرشته",
    "جنسیت",
    "دانش آموز فارغ",
    "مرکز گلستان صدرا",
    "مالی حکمت بنیاد",
    "کد مدرسه",
}


def _iter_allocation_python_files() -> list[Path]:
    return sorted(ALLOCATION_ROOT.rglob("*.py"))


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


def _has_raw_join_key_access(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            slice_node = node.slice
            if (
                isinstance(slice_node, ast.Constant)
                and isinstance(slice_node.value, str)
                and slice_node.value in JOIN_KEY_LITERALS
            ):
                return True
    return False


def test_no_raw_join_key_access_in_allocation_modules() -> None:
    """JOINKEY-SSOT-03: allocation must not index raw join-key columns directly."""

    violations: list[str] = []
    unreadable: list[str] = []
    for path in _iter_allocation_python_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        tree, err = _load_ast(path)
        if err:
            unreadable.append(err)
            continue
        if _has_raw_join_key_access(tree):
            violations.append(rel)

    assert not unreadable, (
        "Guard could not decode/parse allocation files deterministically; "
        "ensure they are valid UTF-8 or contain a correct encoding cookie: "
        f"{sorted(unreadable)}"
    )
    assert not violations, (
        "Raw join-key column indexing detected in allocation modules; "
        "use Effective Join Keys / join-map helpers instead."
        f" Violations: {sorted(violations)}"
    )

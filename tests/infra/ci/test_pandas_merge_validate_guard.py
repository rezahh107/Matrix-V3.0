from __future__ import annotations

import ast
import tokenize
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = REPO_ROOT / "app"


@dataclass(frozen=True)
class MergeAllowlistEntry:
    path: str
    line_start: int
    line_end: int
    reason: str


ALLOWED_MERGE_CALLS: tuple[MergeAllowlistEntry, ...] = ()


def _iter_python_files() -> list[Path]:
    return sorted(APP_ROOT.rglob("*.py"))


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


def _is_allowlisted(path: str, lineno: int) -> bool:
    for entry in ALLOWED_MERGE_CALLS:
        if entry.path == path and entry.line_start <= lineno <= entry.line_end:
            return True
    return False


def _has_validate_keyword(node: ast.Call) -> bool:
    return any(keyword.arg == "validate" for keyword in node.keywords)


def _find_merge_calls(tree: ast.AST) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr != "merge":
                continue
            if not _has_validate_keyword(node):
                lines.append(getattr(node, "lineno", 0))
    return lines


def test_merge_validate_guard() -> None:
    """Require validate=... on DataFrame.merge calls in app/."""

    violations: list[str] = []
    unreadable: list[str] = []
    for path in _iter_python_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        tree, err = _load_ast(path)
        if err:
            unreadable.append(err)
            continue
        missing_validate_lines = _find_merge_calls(tree)
        for lineno in missing_validate_lines:
            if _is_allowlisted(rel, lineno):
                continue
            violations.append(f"{rel}:{lineno}")

    assert not unreadable, (
        "Guard could not decode/parse files deterministically; "
        "ensure they are valid UTF-8 or contain a correct encoding cookie: "
        f"{sorted(unreadable)}"
    )
    assert not violations, (
        "DataFrame.merge calls without validate= detected. "
        "Add validate= or document allowlist exceptions. "
        f"Violations: {sorted(violations)}"
    )

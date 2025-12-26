from __future__ import annotations

import ast
import tokenize
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INFRA_ROOT = REPO_ROOT / "app" / "infra"

ALLOWED_CANONICALIZATION_IMPORTS = {
    "app/infra/audit_allocations.py",
    "app/infra/canonical_frames.py",
    "app/infra/cli_legacy.py",
    "app/infra/excel/export_allocations.py",
    "app/infra/excel/import_to_sabt.py",
    "app/infra/io_utils.py",
    "app/infra/students/pipeline_v3.py",
    "app/infra/validators/join_keys.py",
}

ALLOWED_DIRECT_PANDAS_READS = {
    "app/infra/excel/export_allocations.py",
    "app/infra/golden/regression_runner.py",
}


def _iter_infra_python_files() -> list[Path]:
    return sorted(INFRA_ROOT.rglob("*.py"))


def _load_ast(path: Path) -> tuple[ast.AST | None, str | None]:
    try:
        with tokenize.open(path) as handle:
            source = handle.read()
        method = "tokenize"
    except (UnicodeDecodeError, SyntaxError):
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


def _assert_parseable_or_report(path: Path) -> ast.AST:
    tree, err = _load_ast(path)
    if err:
        raise AssertionError(err)
    assert tree is not None  # for type checkers
    return tree


def _has_forbidden_pandas_read(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "pandas" and any(
            name.name in {"read_excel", "read_csv"} for name in node.names
        ):
            return True
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"read_excel", "read_csv"}
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in {"pd", "pandas"}
        ):
            return True
    return False


def _has_forbidden_canonicalization_import(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "app.core.common.columns"
            and any(
                name.name in {"canonicalize_headers", "coerce_semantics"}
                for name in node.names
            )
        ):
            return True
        if isinstance(node, ast.Import) and any(
            alias.name == "app.core.common.columns" for alias in node.names
        ):
            return True
    return False


def test_no_direct_pandas_excel_reads_in_infra() -> None:
    violations: list[str] = []
    unreadable: list[str] = []
    for path in _iter_infra_python_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        tree, err = _load_ast(path)
        if err:
            unreadable.append(err)
            continue
        if _has_forbidden_pandas_read(tree) and rel not in ALLOWED_DIRECT_PANDAS_READS:
            violations.append(rel)
    assert not unreadable, (
        "Guard could not decode/parse the following infra files deterministically; "
        "ensure they are valid UTF-8 or contain a correct encoding cookie: "
        f"{sorted(unreadable)}"
    )
    assert not violations, (
        "Direct pandas.read_excel/read_csv calls found outside io_utils; "
        "route Excel reads through io_utils.read_excel_first_sheet instead."
        f" Violations: {sorted(violations)}"
    )


def test_no_direct_header_canonicalization_imports_in_infra() -> None:
    violations: list[str] = []
    unreadable: list[str] = []
    for path in _iter_infra_python_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        tree, err = _load_ast(path)
        if err:
            unreadable.append(err)
            continue
        if _has_forbidden_canonicalization_import(tree) and rel not in ALLOWED_CANONICALIZATION_IMPORTS:
            violations.append(rel)
    assert not unreadable, (
        "Guard could not decode/parse the following infra files deterministically; "
        "ensure they are valid UTF-8 or contain a correct encoding cookie: "
        f"{sorted(unreadable)}"
    )
    assert not violations, (
        "Infra modules must route header work through HeaderPipelineV3 resolvers; "
        "do not import canonicalize_headers/coerce_semantics directly."
        f" Violations: {sorted(violations)}"
    )


def test_load_ast_handles_utf8_without_cookie(tmp_path: Path) -> None:
    target = tmp_path / "tmp_guard_utf8.py"
    content = '"""Persian docstring حروف فارسی"""\n\n' "def sample():\n    return 1\n"
    target.write_text(content, encoding="utf-8")

    tree = _assert_parseable_or_report(target)

    assert isinstance(tree, ast.AST)


def test_load_ast_reports_unreadable_file(tmp_path: Path) -> None:
    target = tmp_path / "tmp_guard_bad.py"
    target.write_bytes(b"\xff\xfe\xfa\xfb")

    tree, err = _load_ast(target)

    assert tree is None
    assert err is not None
    assert "unreadable" in err

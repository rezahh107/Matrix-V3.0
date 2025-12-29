from __future__ import annotations

import ast
import tokenize
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = REPO_ROOT / "app"

PANDAS_CONSTRUCTORS = {"Series", "DataFrame"}
PANDAS_TYPE_NAMES = {"Series", "DataFrame"}
SERIES_FACTORY_NAMES = {"ensure_series"}


def _iter_python_files() -> list[Path]:
    return sorted(APP_ROOT.rglob("*.py"))


def _load_ast(path: Path) -> tuple[ast.AST | None, str | None, str]:
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
        return ast.parse(source, filename=str(path)), None, source
    except (UnicodeDecodeError, SyntaxError) as err:
        try:
            rel = path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            rel = str(path)
        return None, f"{rel} (unreadable via {method}: {err.__class__.__name__}: {err})", source


def _collect_pandas_aliases(tree: ast.AST) -> tuple[set[str], set[str]]:
    pandas_aliases: set[str] = set()
    pandas_direct: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "pandas":
                    pandas_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "pandas":
            for alias in node.names:
                alias_name = alias.asname or alias.name
                if alias.name in PANDAS_CONSTRUCTORS:
                    pandas_direct.add(alias_name)
                if alias.name == "pandas":
                    pandas_aliases.add(alias_name)
    return pandas_aliases, pandas_direct


def _annotation_kind(
    annotation: ast.expr | None,
    *,
    pandas_aliases: set[str],
    pandas_direct: set[str],
) -> str | None:
    if annotation is None:
        return None
    if isinstance(annotation, ast.Attribute) and isinstance(annotation.value, ast.Name):
        if annotation.value.id in pandas_aliases and annotation.attr in PANDAS_TYPE_NAMES:
            return annotation.attr.lower()
        return None
    if isinstance(annotation, ast.Name) and (
        annotation.id in pandas_direct or annotation.id in PANDAS_TYPE_NAMES
    ):
        return annotation.id.lower()
    return None


def _iter_target_names(target: ast.expr) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        names: list[str] = []
        for elt in target.elts:
            names.extend(_iter_target_names(elt))
        return names
    return []


def _constructor_kind(
    value: ast.expr,
    *,
    pandas_aliases: set[str],
    pandas_direct: set[str],
) -> str | None:
    if isinstance(value, ast.Call):
        func = value.func
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id in pandas_aliases
            and func.attr in PANDAS_CONSTRUCTORS
        ):
            return func.attr.lower()
        if isinstance(func, ast.Name):
            if func.id in SERIES_FACTORY_NAMES:
                return "series"
            if func.id in pandas_direct or func.id in PANDAS_CONSTRUCTORS:
                return func.id.lower()
    return None


class PandasVarCollector(ast.NodeVisitor):
    def __init__(self, pandas_aliases: set[str], pandas_direct: set[str]) -> None:
        self._pandas_aliases = pandas_aliases
        self._pandas_direct = pandas_direct
        self.pandas_vars: set[str] = set()
        self.pandas_series_vars: set[str] = set()
        self.pandas_df_vars: set[str] = set()

    def _register(self, name: str, kind: str | None) -> None:
        self.pandas_vars.add(name)
        if kind == "series":
            self.pandas_series_vars.add(name)
        elif kind == "dataframe":
            self.pandas_df_vars.add(name)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        for arg in node.args.args + node.args.kwonlyargs:
            kind = _annotation_kind(
                arg.annotation,
                pandas_aliases=self._pandas_aliases,
                pandas_direct=self._pandas_direct,
            )
            if kind:
                self._register(arg.arg, kind)
        return_kind = _annotation_kind(
            node.returns,
            pandas_aliases=self._pandas_aliases,
            pandas_direct=self._pandas_direct,
        )
        if return_kind:
            self._register(node.name, return_kind)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        kind = _constructor_kind(
            node.value, pandas_aliases=self._pandas_aliases, pandas_direct=self._pandas_direct
        )
        if kind:
            for target in node.targets:
                for name in _iter_target_names(target):
                    self._register(name, kind)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        kind = _annotation_kind(
            node.annotation,
            pandas_aliases=self._pandas_aliases,
            pandas_direct=self._pandas_direct,
        )
        if kind:
            for name in _iter_target_names(node.target):
                self._register(name, kind)
        value_kind = None
        if node.value:
            value_kind = _constructor_kind(
                node.value,
                pandas_aliases=self._pandas_aliases,
                pandas_direct=self._pandas_direct,
            )
        if value_kind:
            for name in _iter_target_names(node.target):
                self._register(name, value_kind)
        self.generic_visit(node)


class PandasAssignmentGuard(ast.NodeVisitor):
    def __init__(self, pandas_vars: PandasVarCollector) -> None:
        self._pandas_vars = pandas_vars.pandas_vars
        self._pandas_series_vars = pandas_vars.pandas_series_vars
        self._pandas_df_vars = pandas_vars.pandas_df_vars
        self._loop_depth = 0
        self.violations: list[tuple[int, str]] = []

    def visit_For(self, node: ast.For) -> None:  # noqa: N802
        self._loop_depth += 1
        self.generic_visit(node)
        self._loop_depth -= 1

    def visit_While(self, node: ast.While) -> None:  # noqa: N802
        self._loop_depth += 1
        self.generic_visit(node)
        self._loop_depth -= 1

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            self._check_target(target)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._check_target(node.target)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._check_target(node.target)
        self.generic_visit(node)

    def _check_target(self, target: ast.expr) -> None:
        if not isinstance(target, ast.Subscript):
            return
        root_name = _root_name(target)
        if root_name is None:
            return
        if not _is_pandas_like_name(root_name, self._pandas_vars):
            return

        if isinstance(target.value, ast.Subscript):
            self._record(target, "chained_subscript_assignment")
            return
        if isinstance(target.value, ast.Attribute) and target.value.attr == "values":
            self._record(target, "values_assignment")
            return
        if isinstance(target.value, ast.Call):
            func = target.value.func
            if isinstance(func, ast.Attribute) and func.attr == "to_numpy":
                self._record(target, "to_numpy_assignment")
                return
        if root_name in self._pandas_series_vars and self._loop_depth > 0:
            self._record(target, "loop_subscript_assignment")
            return
        if root_name in self._pandas_series_vars:
            self._record(target, "bracket_assignment")

    def _record(self, node: ast.AST, reason: str) -> None:
        lineno = getattr(node, "lineno", 0)
        self.violations.append((lineno, reason))


def _root_name(node: ast.Subscript) -> str | None:
    current: ast.AST | None = node
    while isinstance(current, ast.Subscript):
        current = current.value
    if isinstance(current, ast.Attribute):
        current = current.value
    if isinstance(current, ast.Name):
        return current.id
    return None


def _is_pandas_like_name(name: str, pandas_vars: set[str]) -> bool:
    if name in pandas_vars:
        return True
    suffixes = ("_df", "_series", "_frame")
    return name.endswith(suffixes)


def test_no_forbidden_pandas_assignments() -> None:
    """Guard against chained assignment and label-creating bracket writes."""

    violations: list[str] = []
    unreadable: list[str] = []
    for path in _iter_python_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        tree, err, _source = _load_ast(path)
        if err:
            unreadable.append(err)
            continue
        pandas_aliases, pandas_direct = _collect_pandas_aliases(tree)
        if not pandas_aliases and not pandas_direct:
            continue
        collector = PandasVarCollector(pandas_aliases, pandas_direct)
        collector.visit(tree)
        guard = PandasAssignmentGuard(collector)
        guard.visit(tree)
        for lineno, reason in guard.violations:
            violations.append(f"{rel}:{lineno} [{reason}]")

    assert not unreadable, (
        "Guard could not decode/parse files deterministically; "
        "ensure they are valid UTF-8 or contain a correct encoding cookie: "
        f"{sorted(unreadable)}"
    )
    assert not violations, (
        "Forbidden pandas assignment patterns detected. "
        "Use .loc/.at with enforced index contracts instead. "
        f"Violations: {sorted(violations)}"
    )

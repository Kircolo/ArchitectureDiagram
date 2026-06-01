from __future__ import annotations

import ast
from pathlib import Path
from collections.abc import Iterable


def parse_python_file(path: Path) -> ast.AST | None:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    try:
        return ast.parse(content)
    except SyntaxError:
        return None


def imported_module_roots(tree: ast.AST) -> set[str]:
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", 1)[0])
    return imports


def iter_calls(tree: ast.AST) -> Iterable[ast.Call]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            yield node


def call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = call_name(node.value)
        if parent is None:
            return node.attr
        return f"{parent}.{node.attr}"
    return None


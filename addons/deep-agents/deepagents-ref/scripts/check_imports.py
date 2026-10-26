"""Check a Python file's deepagents usage against the vendored 0.7.29 source (no install needed).

    python deepagents-ref/scripts/check_imports.py path/to/agent.py [more.py ...]

Reports:
- MISSING   `from deepagents.x import Name` where module or Name doesn't exist in sources/package/
- BAD-KWARG a keyword argument that the called deepagents function/class doesn't accept
- ANTI      known 0.7 breakers: backend factories (`backend=lambda`), positional args to
            StateBackend/StoreBackend, and system prompts mentioning write_todos without TodoListMiddleware
- WARN      (doesn't fail) InMemorySaver/InMemoryStore (lost on restart; fine in tests),
            LocalShellBackend/FilesystemBackend (real disk/shell), model="..." without "provider:"
Exit 1 if anything except WARN is reported. Uses only the standard library.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "sources" / "package"


def module_file(mod: str) -> Path | None:
    base = PKG.joinpath(*mod.split("."))
    for cand in (base.with_suffix(".py"), base / "__init__.py"):
        if cand.is_file():
            return cand
    return None


def top_level(tree: ast.Module) -> dict[str, ast.AST]:
    out: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            out[node.name] = node
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    out[t.id] = node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out[node.target.id] = node
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                out[a.asname or a.name] = node
    return out


def resolve(mod: str, name: str, depth: int = 0) -> ast.AST | None:
    """Follow re-exports until the defining class/function (or None)."""
    f = module_file(mod)
    if not f or depth > 6:
        return None
    node = top_level(ast.parse(f.read_text(encoding="utf-8"))).get(name)
    if isinstance(node, ast.ImportFrom) and node.module:
        src = next(a.name for a in node.names if (a.asname or a.name) == name)
        target = node.module if node.level == 0 else ".".join(mod.split(".")[: -node.level + (1 if f.name == "__init__.py" else 0)] + [node.module])
        return resolve(target, src, depth + 1)
    return node


def accepted_kwargs(node: ast.AST) -> tuple[set[str], bool] | None:
    """(parameter names, accepts **kwargs) for a function, or a class's __init__ / dataclass fields."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        a = node.args
        return {x.arg for x in a.posonlyargs + a.args + a.kwonlyargs} - {"self"}, a.kwarg is not None
    if isinstance(node, ast.ClassDef):
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                return accepted_kwargs(item)
        fields = {i.target.id for i in node.body if isinstance(i, ast.AnnAssign) and isinstance(i.target, ast.Name)}
        return (fields, False) if fields else None  # dataclass / TypedDict-like
    return None


def check(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    problems: list[str] = []
    imported: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "deepagents":
            if not module_file(node.module):
                problems.append(f"{path}:{node.lineno} MISSING module {node.module}")
                continue
            for a in node.names:
                if resolve(node.module, a.name) is None:
                    problems.append(f"{path}:{node.lineno} MISSING {node.module}.{a.name}")
                else:
                    imported[a.asname or a.name] = (node.module, a.name)

    uses_todo_mw = any(isinstance(n, ast.Name) and n.id == "TodoListMiddleware" for n in ast.walk(tree))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and "write_todos" in node.value and not uses_todo_mw:
            problems.append(f"{path}:{node.lineno} ANTI mentions write_todos but TodoListMiddleware is never used (opt-in since 0.7.0)")
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in imported):
            continue
        name = node.func.id
        for kw in node.keywords:
            if kw.arg == "backend" and isinstance(kw.value, ast.Lambda):
                problems.append(f"{path}:{node.lineno} ANTI backend=lambda: backend factories raise TypeError in 0.7; pass an instance")
        if imported[name][1] in {"StateBackend", "StoreBackend"} and node.args:
            problems.append(f"{path}:{node.lineno} ANTI {imported[name][1]} takes no positional args in 0.7")
        sig = accepted_kwargs(resolve(*imported[name]))
        if sig:
            params, var_kw = sig
            for kw in node.keywords:
                if kw.arg and kw.arg not in params and not var_kw:
                    problems.append(f"{path}:{node.lineno} BAD-KWARG {name}({kw.arg}=...) not accepted in 0.7.29")
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in {"InMemorySaver", "InMemoryStore", "MemorySaver"}:
                problems.append(f"{path}:{node.lineno} WARN {node.func.id}() is lost on restart; use a durable saver/store outside tests")
            if node.func.id in {"LocalShellBackend", "FilesystemBackend"}:
                problems.append(f"{path}:{node.lineno} WARN {node.func.id} gives the model real disk{' and a shell' if node.func.id == 'LocalShellBackend' else ''}; never for deployed agents")
        if isinstance(node, ast.keyword) and node.arg == "model" and isinstance(node.value, ast.Constant)                 and isinstance(node.value.value, str) and ":" not in node.value.value:
            problems.append(f"{path}:{node.value.lineno} WARN model={node.value.value!r} has no provider prefix; no provider/harness profile applies (use 'provider:model')")
    return problems


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    problems = [p for f in argv for p in check(Path(f))]
    for p in problems:
        print(p)
    failing = [p for p in problems if " WARN " not in p]
    print(("FAIL" if failing else "PASS") + f" — {len(failing)} problem(s), {len(problems) - len(failing)} warning(s); checked against {PKG.as_posix()}")
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Base-vs-head run 1 for a Python repo: which test modules import a touched module?

Usage (from the worktree root):
    python import_scan.py [--root <scan root> ...] <touched module> [<touched module> ...]

A touched module is a dotted name, e.g. `app.billing.invoice`. Every `.py` file under the
given roots (default: the whole worktree, skipping virtualenvs, caches and node_modules) is
parsed with `ast`; `import X` and `from X import ...` are collected, with package-relative
forms (`from . import x`, `from ..pkg import y`) resolved against the file's own dotted name.
A file's dotted name is computed from the top of its package, not the worktree root: walk up
while the parent folder has an `__init__.py`; the first folder without one is the import root
(so `src/app/billing/invoice.py` is `app.billing.invoice` in a src layout).

A name matches a target when it is the target, a submodule/attribute of it, or ends with it
on a `.` boundary (so `src.app.billing.invoice` still matches `app.billing.invoice`).

Every parsed file is a possible intermediate: a file that imports a target (or imports a file
that does, transitively) is reached, and so are its importers — this covers a test that pulls
the target in through a non-test helper (`from helpers import *`) or a package `__init__`
that re-exports it, and a test that imports a sibling test module by bare name. A module with
no package (a bare `helpers.py` / `test_common.py`) only counts as imported by files in its own
folder, or anywhere when it sits at the worktree root, matching how pytest's rootdir insertion
puts a test file's own folder on sys.path. Only test files (`test_*.py`, `*_test.py`) are
printed; a test file that cannot be parsed is selected (it cannot be ruled out) and reported on
stderr.

Prints one relative path per line, sorted, then `COUNT <n>`. Limits: Python only; with
`--root` narrowed to the tests folder, intermediates outside it (package `__init__` re-exports,
helpers elsewhere) are not seen, so keep the default root unless the tree is too large; imports
the scan can't see (dynamic `importlib`/`__import__`, plugins, conftest fixtures, sys.path
hacks that import a bare module from another folder) are missed. For any other stack, or when
any of those apply, run the whole affected suite instead and say so in the report. An empty set
is never proof on its own.
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "venv", "env", "__pycache__", "node_modules", ".tox", ".mypy_cache", ".pytest_cache", "build", "dist"}


def is_test_file(path: Path) -> bool:
    return path.name.startswith("test_") or path.name.endswith("_test.py")


def module_name(path: Path, root: Path) -> str:
    """Dotted name from the top of the file's package (the first folder up without __init__.py)."""
    parts = [] if path.name == "__init__.py" else [path.stem]
    d = path.parent
    while (d == root or root in d.parents) and (d / "__init__.py").is_file():
        parts.insert(0, d.name)
        d = d.parent
    return ".".join(parts)


def resolve_relative(current: str, is_package: bool, level: int, module: str | None) -> str:
    base = current.split(".") if current else []
    # a module's package is its parent; a package's __init__ is its own package
    if not is_package:
        base = base[:-1]
    if level > 1:
        base = base[: len(base) - (level - 1)] if level - 1 <= len(base) else []
    return ".".join([*base, *(module.split(".") if module else [])])


def imports_of(path: Path, root: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    me = module_name(path, root)
    is_package = path.name == "__init__.py"
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = resolve_relative(me, is_package, node.level, node.module) if node.level else (node.module or "")
            if base:
                found.add(base)
            for alias in node.names:
                found.add(f"{base}.{alias.name}" if base else alias.name)
    return found


def under(name: str, target: str) -> bool:
    return name == target or name.startswith(target + ".")


def hits_target(names: set[str], targets: list[str]) -> bool:
    """A name matches if it, or any dotted suffix of it, is the target or under it."""
    for n in names:
        parts = n.split(".")
        for i in range(len(parts)):
            suffix = ".".join(parts[i:])
            if any(under(suffix, t) for t in targets):
                return True
    return False


def python_files(root: Path, roots: list[str]) -> list[Path]:
    bases = [root / r for r in roots] if roots else [root]
    out = set()
    for base in bases:
        if not base.is_dir():
            continue
        for p in base.rglob("*.py"):
            if any(part in SKIP_DIRS for part in p.relative_to(root).parts):
                continue
            if p.is_file():
                out.add(p)
    return sorted(out)


def imports_file(importer: Path, names: set[str], mod: str, mod_path: Path, root: Path) -> bool:
    """Does `importer` (with import names `names`) import the module `mod` at `mod_path`?"""
    if not mod or importer == mod_path:
        return False
    if "." not in mod and mod_path.name != "__init__.py" and mod_path.parent not in (importer.parent, root):
        # a bare top-level module is importable from its own folder (or the worktree root)
        return False
    return any(under(n, mod) for n in names)


def scan(root: Path, roots: list[str], targets: list[str]) -> list[Path]:
    files = python_files(root, roots)
    imports: dict[Path, set[str]] = {}
    unparsed: list[Path] = []
    for p in files:
        try:
            imports[p] = imports_of(p, root)
        except (SyntaxError, UnicodeDecodeError, ValueError) as exc:
            print(f"UNPARSED {p.relative_to(root).as_posix()}: {exc.__class__.__name__}", file=sys.stderr)
            imports[p] = set()
            unparsed.append(p)
    names = {p: module_name(p, root) for p in files}

    reached = {p for p, found in imports.items() if hits_target(found, targets)}
    frontier = list(reached)
    while frontier:
        q = frontier.pop()
        for p, found in imports.items():
            if p not in reached and imports_file(p, found, names[q], q, root):
                reached.add(p)
                frontier.append(p)
    selected = {p for p in reached if is_test_file(p)} | {p for p in unparsed if is_test_file(p)}
    return sorted(selected)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", action="append", default=[], help="a scan root, relative to the worktree (repeatable)")
    ap.add_argument("targets", nargs="+", help="touched modules, dotted")
    args = ap.parse_args()
    root = Path.cwd()
    selected = scan(root, args.root, args.targets)
    for p in selected:
        print(p.relative_to(root).as_posix())
    print(f"COUNT {len(selected)}")


if __name__ == "__main__":
    main()

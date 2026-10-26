"""Regenerate the symbol table in wiki/lookup.md from sources/package/.

Every public name exported by a deepagents `__init__.py` (`__all__`), plus every
`create_deep_agent` parameter, gets one row: import path, definition file:line,
and the wiki pages that explain it (ranked by mentions, keywords first).

Only the block between the GENERATED markers is rewritten; the hand-written
term table above it is kept.

    python scripts/build_lookup.py
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "sources" / "package" / "deepagents"
WIKI = ROOT / "wiki"
LOOKUP = WIKI / "lookup.md"
START = "<!-- GENERATED:symbols (scripts/build_lookup.py) -->"
END = "<!-- /GENERATED:symbols -->"
SKIP_PAGES = {"index", "lookup", "gaps", "constitution", "anti", "versions", "sources", "do-not", "decisions"}
FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.S)


def module_name(path: Path) -> str:
    rel = path.relative_to(PKG.parent).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def definitions() -> dict[str, tuple[str, int]]:
    """name -> (repo-relative file, line) for top-level classes/functions/assignments."""
    found: dict[str, tuple[str, int]] = {}
    for py in sorted(PKG.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in tree.body:
            names = []
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                names = [node.name]
            elif isinstance(node, ast.Assign):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names = [node.target.id]
            rel = py.relative_to(ROOT).as_posix()
            for n in names:
                # Prefer the defining module over re-export shims in __init__.
                if n not in found or found[n][0].endswith("__init__.py"):
                    found[n] = (rel, node.lineno)
    return found


def exports() -> list[tuple[str, str]]:
    """(public import module, name) from every __init__ __all__."""
    out: list[tuple[str, str]] = []
    for init in sorted(PKG.rglob("__init__.py")):
        tree = ast.parse(init.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
            ):
                for elt in getattr(node.value, "elts", []):
                    if isinstance(elt, ast.Constant) and not elt.value.startswith("__"):
                        out.append((module_name(init), elt.value))
    seen: set[str] = set()
    uniq = []
    for mod, name in out:  # keep the shortest import path per name
        if name not in seen:
            seen.add(name)
            uniq.append((mod, name))
    return uniq


def create_deep_agent_params() -> list[str]:
    tree = ast.parse((PKG / "graph.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "create_deep_agent":
            a = node.args
            return [x.arg for x in a.posonlyargs + a.args + a.kwonlyargs]
    return []


def load_pages() -> dict[str, tuple[str, str]]:
    pages = {}
    for p in WIKI.glob("*.md"):
        if p.stem in SKIP_PAGES:
            continue
        text = p.read_text(encoding="utf-8")
        m = FM_RE.match(text)
        kw = ""
        if m:
            km = re.search(r"^keywords:\s*(.*)$", m.group(1), re.M)
            kw = km.group(1) if km else ""
        pages[p.stem] = (kw, text)
    return pages


def rank(term: str, pages: dict[str, tuple[str, str]], k: int = 2) -> list[str]:
    pat = re.compile(rf"(?<![\w.]){re.escape(term)}(?![\w])")
    scored = []
    for stem, (kw, text) in pages.items():
        n = len(pat.findall(text))
        if n == 0:
            continue
        in_kw = bool(pat.search(kw))
        scored.append((in_kw, n, stem))
    scored.sort(reverse=True)
    return [s for _, _, s in scored[:k]]


def main() -> int:
    defs = definitions()
    pages = load_pages()
    rows = ["| Symbol | Import | Defined at | Read |", "|---|---|---|---|"]
    missing = []
    for mod, name in exports():
        loc = defs.get(name)
        where = f"`{loc[0].replace('sources/', '../sources/')}:{loc[1]}`" if loc else "not found"
        hits = rank(name, pages)
        if not hits:
            missing.append(name)
        read = ", ".join(f"[[{h}]]" for h in hits) or "no wiki page — read the definition"
        rows.append(f"| `{name}` | `from {mod} import {name}` | {where} | {read} |")
    rows += ["", "`create_deep_agent` parameters (signature: [[create-deep-agent]]):", "",
             "| Parameter | Read |", "|---|---|"]
    for param in create_deep_agent_params():
        hits = [h for h in rank(param, pages, 3) if h != "create-deep-agent"][:2]
        read = ", ".join(f"[[{h}]]" for h in ["create-deep-agent", *hits])
        rows.append(f"| `{param}=` | {read} |")
    block = "\n".join([START, "", *rows, "", END])

    text = LOOKUP.read_text(encoding="utf-8")
    if START in text and END in text:
        text = text[: text.index(START)] + block + text[text.index(END) + len(END):]
    else:
        text = text.rstrip() + "\n\n" + block + "\n"
    LOOKUP.write_text(text, encoding="utf-8", newline="\n")
    print(f"lookup.md: {len(exports())} symbols, {len(create_deep_agent_params())} params")
    if missing:
        print("no wiki page mentions:", ", ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())

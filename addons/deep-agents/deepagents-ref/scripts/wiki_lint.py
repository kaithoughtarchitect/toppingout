"""Lint wiki/ so a cold agent can always find what it needs.

    python scripts/wiki_lint.py          check everything
    python scripts/wiki_lint.py --stamp  after re-checking pages: record the hash of each
                                         page's cited sources (clears STALE)
    python scripts/wiki_lint.py --strict STALE pages fail too (the refresh routine, MAINTAINING.md);
                                         without it they are reported but don't fail, since freshly
                                         fetched docs (scripts/setup_sources.py) may differ from the stamp

Checks
- frontmatter: title, id (= filename), type, status, product, keywords, read_when, updated
- every [[link]] resolves
- every page is listed on index.md with a one-line summary
- STALE: a page's cited `../sources/...` files changed since it was stamped
- MISSING-SOURCE: a page cites a source path that no longer exists (drift, like STALE: fails only with --strict)
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIKI = ROOT / "wiki"
REQUIRED = ("title", "id", "type", "status", "product", "keywords", "read_when", "updated")
TYPES = {"map", "concept", "api", "how-to", "decision", "reference", "product", "rule"}
STATUSES = {"code", "sourced", "draft"}
PRODUCTS = {"sdk", "dcode", "managed", "all"}
FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)
LINK_RE = re.compile(r"\[\[([^\]|#\n]+?)(?:\|[^\]]+)?\]\]")
SRC_RE = re.compile(r"`(\.\./sources/[^`:\s]+?)(?::\d+)?`")
CATALOG_RE = re.compile(r"^- \[\[([^\]]+)\]\] — \S", re.M)


def frontmatter(text: str) -> dict[str, str]:
    m = FM_RE.match(text)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


def cited_sources(text: str) -> list[Path]:
    sec = re.search(r"^## Sources\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    if not sec:
        return []
    return sorted({(WIKI / p).resolve() for p in SRC_RE.findall(sec.group(1))})


def _content(f: Path) -> bytes:
    # Normalise line endings so a Windows checkout (CRLF) hashes the same as LF.
    return f.read_bytes().replace(b"\r\n", b"\n")


def sources_hash(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in paths:
        h.update(p.relative_to(ROOT).as_posix().encode())
        if p.is_file():
            h.update(_content(p))
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file():
                    h.update(_content(f))
    return h.hexdigest()[:12]


def stamp(page: Path, text: str) -> str:
    digest = sources_hash(cited_sources(text))
    fm = FM_RE.match(text)
    body = fm.group(1)
    if re.search(r"^sources_hash:", body, re.M):
        body = re.sub(r"^sources_hash:.*$", f"sources_hash: {digest}", body, flags=re.M)
    else:
        body = body.rstrip() + f"\nsources_hash: {digest}"
    return text.replace(fm.group(1), body, 1)


def main(argv: list[str]) -> int:
    pages = {p.stem: p for p in sorted(WIKI.glob("*.md"))}
    errors: list[str] = []
    stale: list[str] = []
    gone: list[str] = []  # a cited source the docs no longer have (or not fetched yet): drift, like STALE
    for stem, path in pages.items():
        text = path.read_text(encoding="utf-8")
        if "--stamp" in argv and cited_sources(text):
            text = stamp(path, text)
            path.write_text(text, encoding="utf-8", newline="\n")
        fm = frontmatter(text)
        if not fm:
            errors.append(f"{stem}: no frontmatter")
            continue
        missing = [k for k in REQUIRED if not fm.get(k)]
        if missing:
            errors.append(f"{stem}: missing {', '.join(missing)}")
        if fm.get("id") and fm["id"] != stem:
            errors.append(f"{stem}: id {fm['id']!r} != filename")
        for key, allowed in (("type", TYPES), ("status", STATUSES), ("product", PRODUCTS)):
            if fm.get(key) and fm[key] not in allowed:
                errors.append(f"{stem}: bad {key} {fm[key]!r}")
        for link in set(LINK_RE.findall(text)):
            if link.strip() not in pages:
                errors.append(f"{stem}: [[{link}]] has no page")
        srcs = cited_sources(text)
        for p in srcs:
            if not p.exists():
                gone.append(f"{stem}: MISSING-SOURCE {p.relative_to(ROOT).as_posix()}")
        if srcs and fm.get("sources_hash") and fm["sources_hash"] != sources_hash(srcs):
            stale.append(stem)

    index = pages.get("index")
    if index:
        listed = set(CATALOG_RE.findall(index.read_text(encoding="utf-8")))
        for stem in pages:
            if stem != "index" and stem not in listed:
                errors.append(f"index: {stem} not listed as '- [[{stem}]] — summary'")

    for e in errors:
        print("ERROR", e)
    for g in gone:
        print("ERROR" if "--strict" in argv else "DRIFT", g)
    for s in stale:
        print(f"STALE {s}: cited sources changed since last stamp; re-check the page, then --stamp")
    drift = len(stale) + len(gone)
    ok = not errors and (not drift or "--strict" not in argv)
    print(("PASS" if ok else "FAIL") + f" — {len(pages)} pages, {len(errors)} errors, {len(stale)} stale, {len(gone)} missing sources"
          + (" (drift from the docs the wiki was checked against: re-check with MAINTAINING.md, then --strict)" if drift and "--strict" not in argv else ""))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

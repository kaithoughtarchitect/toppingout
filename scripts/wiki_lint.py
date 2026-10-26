"""Lint the person wiki: YAML schema + body [[wikilinks]] as the graph."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REQUIRED_KEYS = ("title", "type", "status", "updated")
TYPES = {"map", "person-facet", "work", "method", "platform", "proof", "rule", "skill", "agent"}
STATUSES = {"draft", "sourced", "published", "confirmed"}
WIKILINK_RE = re.compile(r"\[\[([^\]|#\n]+?)(?:\|[^\]]+)?\]\]")
FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.S)
UPDATED_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EXCLUDE_NAMES = {"_template.md", "readme.md"}
CATALOG_RE = re.compile(
    r"^[-*]\s+\[\[([^\]|#]+?)(?:\|[^\]]+)?\]\](?::|\s+[—–-])\s+(\S.+)$",
    re.M,
)
EDGE_VERBS = {
    "uses",
    "used by",
    "used-by",
    "used after",
    "used-after",
    "do-not-with",
    "supersedes",
    "contradicts",
}
EDGE_LINE_RE = re.compile(
    r"^[ \t]*(?:[-*][ \t]+)?(?P<verb>used[ \t]+(?:by|after)|do-not-with|"
    r"supersedes|contradicts|uses|[a-z]+(?:-[a-z]+)+|"
    r"related|relates|depends|requires|invalidates)[ \t]+\[\[",
    re.I | re.M,
)


def wiki_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    if here.is_file():
        here = here.parent
    # Explicit graph root (person wiki/ or skills-wiki/): directory that already has index.md.
    if (here / "index.md").is_file():
        return here
    for p in [here, *here.parents]:
        cand = p / "wiki"
        if cand.is_dir():
            return cand
    raise FileNotFoundError("wiki/ not found")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = FM_RE.match(text)
    if not m:
        return {}, text
    raw = m.group(1)
    data: dict = {}
    i = 0
    lines = raw.splitlines()
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        if line.startswith("  - ") or line.startswith("\t- "):
            i += 1
            continue
        if ":" not in line:
            i += 1
            continue
        key, rest = line.split(":", 1)
        key = key.strip()
        rest = rest.strip()
        if rest == "" or rest == "|" or rest == ">":
            items: list[str] = []
            i += 1
            while i < len(lines) and (
                lines[i].startswith("  - ")
                or lines[i].startswith("\t- ")
                or lines[i].startswith("- ")
            ):
                item = lines[i].lstrip()
                if item.startswith("- "):
                    items.append(_unquote(item[2:].strip()))
                i += 1
            data[key] = items
            continue
        if rest.startswith("[") and rest.endswith("]"):
            inner = rest[1:-1].strip()
            data[key] = (
                [_unquote(x.strip()) for x in inner.split(",") if x.strip()]
                if inner
                else []
            )
        else:
            data[key] = _unquote(rest)
        i += 1
    return data, text[m.end() :]


def _unquote(s: str) -> str:
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


def extract_wikilinks(body: str) -> list[str]:
    return [m.group(1).strip() for m in WIKILINK_RE.finditer(body)]


def normalize_target(target: str) -> str:
    return target.strip().replace("\\", "/").rstrip("/")


def content_pages(root: Path) -> list[Path]:
    pages = []
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(root).as_posix()
        if p.name.lower() in EXCLUDE_NAMES:
            continue
        if rel.startswith("today/"):
            continue
        pages.append(p)
    return pages


def page_stem(root: Path, path: Path) -> str:
    return path.relative_to(root).with_suffix("").as_posix()


def load_pages(root: Path) -> list[dict]:
    rows = []
    for path in content_pages(root):
        text = path.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(text)
        stem = page_stem(root, path)
        node_id = normalize_target(str(fm.get("id") or stem))
        relates = fm.get("relates") or []
        if isinstance(relates, str):
            relates = [relates]
        rows.append(
            {
                "path": path,
                "stem": stem,
                "id": node_id,
                "fm": fm,
                "body": body,
                "text": text,
                "relates": [normalize_target(x) for x in relates],
                "links": [normalize_target(x) for x in extract_wikilinks(body)],
            }
        )
    return rows


def resolve_ok(target: str, stems: set[str], ids: set[str]) -> bool:
    t = normalize_target(target)
    return t in stems or t in ids


def catalog_entries(index_body: str) -> dict[str, str]:
    out = {}
    for m in CATALOG_RE.finditer(index_body):
        out[normalize_target(m.group(1))] = m.group(2).strip()
    return out


def lint(root: Path) -> list[str]:
    rows = load_pages(root)
    stems = {r["stem"] for r in rows}
    ids = {r["id"] for r in rows}
    errors: list[str] = []
    seen_ids: dict[str, str] = {}
    index = next((r for r in rows if r["stem"] == "index"), None)

    for r in rows:
        rel = r["path"].relative_to(root).as_posix()
        fm = r["fm"]
        if not fm:
            errors.append(f"{rel}: FRONTMATTER: missing YAML block")
            continue
        missing = [k for k in REQUIRED_KEYS if not str(fm.get(k) or "").strip()]
        if missing:
            errors.append(f"{rel}: KEYS: missing {', '.join(missing)}")
        typ = str(fm.get("type") or "")
        if typ and typ not in TYPES:
            errors.append(f"{rel}: ENUM: bad type {typ!r}")
        st = str(fm.get("status") or "")
        if st and st not in STATUSES:
            errors.append(f"{rel}: ENUM: bad status {st!r}")
        upd = str(fm.get("updated") or "")
        if upd and not UPDATED_RE.match(upd):
            errors.append(f"{rel}: KEYS: updated must be YYYY-MM-DD")
        if typ in ("skill", "agent") and not r["stem"].startswith("_") and "\n**On site:**" not in "\n" + r["body"]:
            errors.append(f"{rel}: ON SITE: no **On site:** line (the Atlas and the site read the role from it)")
        if "relates" in fm and not isinstance(fm.get("relates"), list):
            errors.append(f"{rel}: KEYS: relates must be a list")
        if r["id"] in seen_ids:
            errors.append(f"{rel}: ID: duplicate {r['id']} ({seen_ids[r['id']]})")
        seen_ids[r["id"]] = rel
        if "id" in fm and normalize_target(str(fm["id"])) != r["stem"]:
            errors.append(
                f"{rel}: ID: id {fm['id']!r} must equal path stem {r['stem']!r}"
            )
        body_set = set(r["links"])
        for nb in r["relates"]:
            if nb == r["stem"] or nb == r["id"]:
                continue
            if nb not in body_set:
                errors.append(f"{rel}: NEIGHBOR: [[{nb}]] missing from body")
        for link in r["links"]:
            if not resolve_ok(link, stems, ids):
                errors.append(f"{rel}: RESOLVE: [[{link}]] has no page")
        for m in EDGE_LINE_RE.finditer(r["body"]):
            verb = " ".join(m.group("verb").lower().split())
            if verb not in EDGE_VERBS:
                allowed = "uses, used by, used after, do-not-with, supersedes, contradicts"
                errors.append(f"{rel}: EDGE: unknown verb {verb!r} (allowed: {allowed})")

    if index is None:
        errors.append("index.md: CATALOG: missing index page")
    else:
        cat = catalog_entries(index["body"])
        for r in rows:
            if r["stem"] == "index":
                continue
            if r["stem"] not in cat and r["id"] not in cat:
                errors.append(
                    f"index.md: CATALOG: missing [[{r['stem']}]]: <one-liner>"
                )
            else:
                line = cat.get(r["stem"]) or cat.get(r["id"]) or ""
                if not line.strip():
                    errors.append(f"index.md: CATALOG: empty summary for {r['stem']}")
    return errors


def collect_edges(root: Path) -> tuple[list[dict], list[tuple[str, str]]]:
    rows = load_pages(root)
    nodes = [{"id": r["stem"], "label": str(r["fm"].get("title") or r["stem"])} for r in rows]
    seen = set()
    edges = []
    for r in rows:
        src = r["stem"]
        for dest in sorted(set(r["links"]) | set(r["relates"])):
            if dest == src:
                continue
            if dest not in {x["id"] for x in nodes}:
                continue
            a, b = (src, dest) if src < dest else (dest, src)
            if (a, b) in seen:
                continue
            seen.add((a, b))
            edges.append((a, b))
    return nodes, edges


def main(argv: list[str]) -> int:
    root = wiki_root(Path(argv[1]) if len(argv) > 1 else None)
    errors = lint(root)
    if errors:
        sys.stdout.write("FAIL\n" + "\n".join(errors) + "\n")
        return 1
    nodes, edges = collect_edges(root)
    sys.stdout.write(
        f"PASS\n{len(list(content_pages(root)))} pages · {len(edges)} undirected edges\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

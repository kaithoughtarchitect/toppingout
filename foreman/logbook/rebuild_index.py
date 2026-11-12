#!/usr/bin/env python3
"""Rebuild logbook_index.md and logbook_links.md from the Logbook's cards.

Python 3.9+ standard library only. Run from the records root (the repository
that holds foreman/logbook/):

    python foreman/logbook/rebuild_index.py [--root DIR] [--check]

Why: with two lanes, both lanes' records branches rewrite the index and links
files at every sign-off, so merging records gives text conflicts there. The
cards are separate files and never conflict. After merging main into the
records branch, run this script instead of resolving the two files by hand.

What it writes:

- the index's header lines (Last Updated, Total Cards with per-type counts,
  Total Links; Version is kept), the three card tables with their (n) counts,
  one row per live card under foreman/logbook/entries/ (templates excluded,
  archived/ never read as live), rows sorted by ID;
- the links table: every row already in logbook_links.md, plus each card's
  `related:` edges, sorted by (From, Type, To);
- the `## Clusters` table, rebuilt from the cards' `cluster:` values (a card
  with a list is listed under each slug); any extra column already in that
  table (a hand-written description, say) is kept by slug, and other text in
  the section is kept as written.

What it keeps, because the cards do not hold it: each row's Summary (a new
card's Summary is its `summary:` line, or else its `# ` title), an Impact or
Conf cell when the card has no such field, every existing link row, the title,
the purpose lines and any other section. Cells the card does hold (impact,
confidence or success_rate, job) come from the card.

What it refuses (exit 1, nothing written): a malformed card (named), two cards
with one ID, an index row for a card that is neither live nor archived, a line
in a generated table it cannot place, and, in a file still holding git
conflict markers, two sides that disagree on text it cannot derive (a Summary,
a cluster description, a purpose line). A file with conflict markers is read
as both sides: their rows are joined, so the result does not depend on which
lane merged first.

`related:` items are card IDs (type `relates`) or `<type>:<ID>`, for example
`related: [refines:INSIGHT_20261020_SOME_LESSON]`. An untyped edge already in
the links table with any type is not added again.

--check writes nothing; it exits 1 if either file differs from a rebuild
(the Last Updated date is ignored) and prints a short summary of the
difference. A rebuild that changes nothing but the date writes nothing.

Exit codes: 0 ok (or up to date), 1 differs or data problem, 2 usage.
"""

import argparse
import fnmatch
import os
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

LOGBOOK_REL = Path("foreman") / "logbook"
CARD_PATTERN = "[A-Z]*_20*.md"
INDEX_NAME = "logbook_index.md"
LINKS_NAME = "logbook_links.md"
TYPES = ("METHOD", "INSIGHT", "BUILD")
INDEX_HEADER = "| ID | Summary | Impact | Conf | Job |"
INDEX_SEP = "| --- | --- | --- | --- | --- |"
LINKS_HEADER = "| From | Type | To |"
LINKS_SEP = "| --- | --- | --- |"
CLUSTER_PLACEHOLDER = "_No clusters yet. They emerge as cards accumulate._"
ID_RE = re.compile(r"(METHOD|INSIGHT|BUILD)_\d{8}_[A-Z0-9_]+")
LINK_TYPE_RE = re.compile(r"[a-z][a-z-]*")
DATE_LINE = re.compile(r"\*\*Last Updated\*\*:")
EXIT_OK, EXIT_DATA, EXIT_USAGE = 0, 1, 2


class UsageError(Exception):
    pass


class DataError(Exception):
    pass


# --- cards -------------------------------------------------------------------

def is_card_name(name):
    # Templates are TYPE-TEMPLATE.md. A card's own name may contain TEMPLATE
    # (a BUILD card about a handoff template, say), so only the hyphened form is skipped.
    return fnmatch.fnmatchcase(name, CARD_PATTERN) and "-TEMPLATE" not in name


def strip_comment(value):
    """Drop a trailing ` # comment` that sits outside quotes."""
    quote = None
    for i, ch in enumerate(value):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or value[i - 1] in " \t"):
            return value[:i].rstrip()
    return value


def unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_value(raw, where):
    raw = strip_comment(raw.strip())
    if raw.startswith("["):
        if not raw.endswith("]"):
            raise DataError(f"{where}: unclosed list {raw!r}")
        inner = raw[1:-1].strip()
        return [unquote(v) for v in inner.split(",") if v.strip()] if inner else []
    if raw in ("", "null", "~"):
        return None
    return unquote(raw)


def parse_card(path, rel):
    """Return a dict of the card's frontmatter plus '_title'; raise DataError naming the file."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise DataError(f"malformed card {rel}: not UTF-8")
    lines = text.splitlines()
    for n, line in enumerate(lines, 1):
        if line.startswith(("<<<<<<< ", ">>>>>>> ")) or line in ("<<<<<<<", ">>>>>>>"):
            raise DataError(f"malformed card {rel}: git conflict marker at line {n}")
    if not lines or lines[0].strip() != "---":
        raise DataError(f"malformed card {rel}: no frontmatter (the first line must be ---)")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise DataError(f"malformed card {rel}: frontmatter never closed with ---")
    fm, key = {}, None
    for n in range(1, end):
        line = lines[n]
        where = f"malformed card {rel} line {n + 1}"
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = re.match(r"\s+-\s*(.*)$", line)
        if item and key is not None:
            if fm[key] is None:
                fm[key] = []
            if not isinstance(fm[key], list):
                raise DataError(f"{where}: list item under a key that already has a value")
            fm[key].append(unquote(strip_comment(item.group(1))))
            continue
        m = re.match(r"([A-Za-z_][A-Za-z0-9_-]*):(?:\s+(.*))?$", line)
        if not m:
            raise DataError(f"{where}: not a `key: value` line: {line!r}")
        key = m.group(1)
        if key in fm:
            raise DataError(f"{where}: `{key}` given twice")
        fm[key] = parse_value(m.group(2) or "", where)
    title = None
    for line in lines[end + 1:]:
        if line.startswith("# "):
            title = line[2:].strip()
            break
    fm["_title"] = title
    return fm


def scalar(fm, key, rel):
    value = fm.get(key)
    if isinstance(value, list):
        raise DataError(f"malformed card {rel}: `{key}` must be one value, not a list")
    return value


def load_cards(lb):
    """Return {id: card} for every live card; refuse anything malformed."""
    entries = lb / "entries"
    cards = {}
    if not entries.is_dir():
        return cards
    for path in sorted(entries.rglob("*.md")):
        if not path.is_file() or not is_card_name(path.name):
            continue
        rel = path.relative_to(lb).as_posix()
        fm = parse_card(path, rel)
        cid = scalar(fm, "id", rel)
        ctype = scalar(fm, "type", rel)
        if not cid:
            raise DataError(f"malformed card {rel}: no `id:`")
        if cid != path.stem:
            raise DataError(f"malformed card {rel}: `id: {cid}` does not match the file name")
        if not ID_RE.fullmatch(cid):
            raise DataError(f"malformed card {rel}: id {cid} is not TYPE_YYYYMMDD_NAME")
        ctype = (ctype or "").upper()
        if ctype not in TYPES:
            raise DataError(f"malformed card {rel}: `type:` must be METHOD, INSIGHT or BUILD")
        if not cid.startswith(ctype + "_"):
            raise DataError(f"malformed card {rel}: id {cid} does not start with its type {ctype}")
        if cid in cards:
            raise DataError(f"two cards with id {cid}: {cards[cid]['rel']} and {rel}")
        conf = scalar(fm, "confidence", rel)
        if conf is None:
            conf = scalar(fm, "success_rate", rel)
        clusters = fm.get("cluster")
        clusters = [] if clusters is None else (clusters if isinstance(clusters, list) else [clusters])
        related = fm.get("related")
        related = [] if related is None else (related if isinstance(related, list) else [related])
        edges = []
        for item in related:
            ltype, target = None, item.strip()
            if ":" in target:
                ltype, target = (s.strip() for s in target.split(":", 1))
                if not LINK_TYPE_RE.fullmatch(ltype):
                    raise DataError(f"malformed card {rel}: related item {item!r} has a bad type")
            if not ID_RE.fullmatch(target):
                raise DataError(f"malformed card {rel}: related item {item!r} is not a card id")
            edges.append((ltype, target))
        cards[cid] = {
            "rel": rel,
            "type": ctype,
            "impact": scalar(fm, "impact", rel),
            "conf": conf,
            "job": scalar(fm, "job", rel),
            "summary": scalar(fm, "summary", rel),
            "title": fm["_title"],
            "clusters": [c.strip() for c in clusters if c and c.strip()],
            "related": edges,
        }
    return cards


def archived_ids(lb):
    base = lb / "archived"
    if not base.is_dir():
        return set()
    return {p.stem for p in base.rglob("*.md") if is_card_name(p.name)}


# --- reading the existing files ---------------------------------------------

def conflict_sides(text, name):
    """Split text holding git conflict markers into (ours, theirs) line lists.

    Lines outside the markers go to both sides; a diff3 base section is dropped.
    Text without markers gives one side.
    """
    lines = text.splitlines()
    if not any(l.startswith("<<<<<<<") for l in lines):
        return [lines]
    ours, theirs, state = [], [], None
    for n, line in enumerate(lines, 1):
        if line.startswith("<<<<<<<"):
            if state is not None:
                raise DataError(f"{name}: nested conflict marker at line {n}")
            state = "ours"
        elif line.startswith("|||||||") and state == "ours":
            state = "base"
        elif line.startswith("=======") and state in ("ours", "base"):
            state = "theirs"
        elif line.startswith(">>>>>>>") and state == "theirs":
            state = None
        elif state is None:
            ours.append(line)
            theirs.append(line)
        elif state == "ours":
            ours.append(line)
        elif state == "theirs":
            theirs.append(line)
    if state is not None:
        raise DataError(f"{name}: a conflict block is never closed")
    return [ours, theirs]


def split_row(line):
    s = line.strip()
    if not (s.startswith("|") and s.endswith("|")) or len(s) < 2:
        return None
    return s[1:-1]


def parse_index_row(line):
    inner = split_row(line)
    if inner is None:
        return None
    cid, _, rest = inner.partition("|")
    cid = cid.strip()
    if not ID_RE.fullmatch(cid):
        return None
    parts = rest.rsplit("|", 3)
    if len(parts) != 4:
        return None
    summary, impact, conf, job = (p.strip() for p in parts)
    return cid, {"summary": summary, "impact": impact, "conf": conf, "job": job}


def sections(lines):
    """Split lines at `## ` headings: [(heading or None, [lines])]."""
    out = [(None, [])]
    for line in lines:
        if line.startswith("## "):
            out.append((line.strip(), []))
        else:
            out[-1][1].append(line)
    return out


def parse_index(lines, name):
    """Parse one side of the index into its parts."""
    secs = sections(lines)
    heads = [h for h, _ in secs]
    for need in ("## Index Cards", "## Clusters"):
        if need not in heads:
            raise DataError(f"{name}: no `{need}` section")
    head = list(secs[0][1])
    version = None
    for key in ("Last Updated", "Total Cards", "Total Links"):
        if not any(l.startswith(f"**{key}**:") for l in head):
            raise DataError(f"{name}: no **{key}** line")
    norm_head = []
    for l in head:
        m = re.match(r"\*\*(Last Updated|Total Cards|Total Links|Version)\*\*:\s*(.*)$", l)
        if m:
            if m.group(1) == "Version":
                version = m.group(2).strip()
            norm_head.append(f"@{m.group(1)}")
        else:
            norm_head.append(l)
    rows, others, cluster = {}, [], None
    for heading, body in secs[1:]:
        if heading == "## Index Cards":
            for n, l in enumerate(body):
                s = l.strip()
                if not s or s in (INDEX_HEADER, INDEX_SEP) or re.fullmatch(r"### (METHOD|INSIGHT|BUILD) Cards \(\d+\)", s):
                    continue
                parsed = parse_index_row(l)
                if not parsed:
                    raise DataError(f"{name}: would lose this line under ## Index Cards: {s!r}")
                cid, row = parsed
                if cid in rows and rows[cid] != row:
                    raise DataError(f"{name}: two different rows for {cid}")
                rows[cid] = row
        elif heading == "## Clusters":
            cluster = parse_clusters(body, name)
        else:
            others.append((heading, body))
    return {"head": norm_head, "version": version, "rows": rows, "clusters": cluster, "others": others,
            "order": [h for h, _ in secs[1:]]}


def parse_clusters(body, name):
    """Return {'columns', 'extra': {slug: [cells]}, 'before', 'after', 'loose'}."""
    columns, extra, before, after, loose = None, {}, [], [], []
    in_table = False
    for l in body:
        s = l.strip()
        if s == CLUSTER_PLACEHOLDER:
            continue
        cells = split_row(l)
        if cells is not None and columns is None and not in_table:
            columns = [c.strip() for c in cells.split("|")]
            if not columns or columns[0] != "Cluster" or "Cards" not in columns:
                raise DataError(f"{name}: the Clusters table needs `Cluster` first and a `Cards` column, got {s!r}")
            in_table = True
            continue
        if in_table and cells is not None:
            parts = [c.strip() for c in cells.split("|")]
            if all(re.fullmatch(r":?-+:?", p) for p in parts):
                continue
            if len(parts) != len(columns):
                raise DataError(f"{name}: cluster row has {len(parts)} cells, the table has {len(columns)}: {s!r}")
            slug = parts[0]
            kept = [p for c, p in zip(columns, parts) if c not in ("Cluster", "Cards")]
            if slug in extra and extra[slug] != kept:
                raise DataError(f"{name}: two different rows for cluster {slug}")
            extra[slug] = kept
            continue
        if in_table and s and re.fullmatch(r"[|,\sA-Z0-9_\x00-\x1f]+", s) and ID_RE.search(s):
            # A broken row of card ids (its cluster name lost, perhaps to a control
            # character): every id in it is listed again from the cards.
            loose.append(s)
            continue
        if in_table and s:
            in_table = False  # text after the table; a second table is kept as text too
        (after if columns is not None else before).append(l)
    return {"columns": columns, "extra": extra, "before": before, "after": after, "loose": loose}


def parse_links(lines, name):
    secs = sections(lines)
    if "## Index Card Links" not in [h for h, _ in secs]:
        raise DataError(f"{name}: no `## Index Card Links` section")
    head = []
    for l in secs[0][1]:
        m = re.match(r"\*\*(Last Updated|Total Links)\*\*:", l)
        head.append(f"@{m.group(1)}" if m else l)
    for key in ("Last Updated", "Total Links"):
        if f"@{key}" not in head:
            raise DataError(f"{name}: no **{key}** line")
    rows, others = set(), []
    for heading, body in secs[1:]:
        if heading != "## Index Card Links":
            others.append((heading, body))
            continue
        for l in body:
            s = l.strip()
            if not s or s in (LINKS_HEADER, LINKS_SEP):
                continue
            inner = split_row(l)
            parts = [p.strip() for p in inner.split("|")] if inner is not None else []
            if len(parts) != 3 or not all(parts):
                raise DataError(f"{name}: would lose this line under ## Index Card Links: {s!r}")
            rows.add(tuple(parts))
    return {"head": head, "rows": rows, "others": others, "order": [h for h, _ in secs[1:]]}


def same(values, what, name):
    first = values[0]
    for v in values[1:]:
        if v != first:
            raise DataError(f"{name}: the two sides of a git conflict disagree on {what}; resolve that by hand first")
    return first


def version_key(v):
    return [int(x) if x.isdigit() else x for x in re.split(r"[.\s]", v or "")]


def merge_index(sides, name):
    head = same([s["head"] for s in sides], "the header or purpose lines", name)
    order = same([s["order"] for s in sides], "the sections", name)
    others = same([s["others"] for s in sides], "a section the cards do not build", name)
    versions = [s["version"] for s in sides if s["version"]]
    version = max(versions, key=version_key) if versions else None
    rows = {}
    for s in sides:
        for cid, row in s["rows"].items():
            if cid in rows and rows[cid] != row:
                old = rows[cid]
                if old["summary"] != row["summary"]:
                    raise DataError(f"{name}: the two sides of a git conflict give {cid} different summaries; resolve that row by hand first")
                # Other cells come from the card; keep both values for the fallback check.
                merged = dict(old)
                for k in ("impact", "conf", "job"):
                    if old[k] != row[k]:
                        merged[k] = ("CONFLICT", old[k], row[k])
                rows[cid] = merged
            elif cid not in rows:
                rows[cid] = row
    cl = [s["clusters"] for s in sides]
    columns = same([c["columns"] for c in cl if c["columns"] is not None] or [None], "the Clusters table columns", name)
    extra = {}
    for c in cl:
        for slug, cells in c["extra"].items():
            if slug in extra and extra[slug] != cells:
                raise DataError(f"{name}: the two sides of a git conflict describe cluster {slug} differently; resolve that row by hand first")
            extra[slug] = cells
    clusters = {
        "columns": columns,
        "extra": extra,
        "before": same([c["before"] for c in cl], "the text above the Clusters table", name),
        "after": same([c["after"] for c in cl], "the text below the Clusters table", name),
        "loose": sorted({x for c in cl for x in c["loose"]}),
    }
    return {"head": head, "version": version, "rows": rows, "clusters": clusters, "others": others, "order": order}


def merge_links(sides, name):
    return {
        "head": same([s["head"] for s in sides], "the header or purpose lines", name),
        "order": same([s["order"] for s in sides], "the sections", name),
        "others": same([s["others"] for s in sides], "a section the cards do not build", name),
        "rows": set().union(*[s["rows"] for s in sides]),
    }


# --- building ---------------------------------------------------------------

def cell(text):
    return " ".join(str(text).split()).replace("|", "\\|")


def norm(value):
    return str(value).strip().strip("`").rstrip("%").strip()


def pick(card_value, existing, fmt, default, cid, column):
    """The card's value wins; an existing cell that says the same is kept as written.

    With no value on the card, the existing cell is kept (the cards cannot rebuild it).
    """
    olds = list(existing[1:]) if isinstance(existing, tuple) else ([] if existing is None else [existing])
    if card_value is not None and str(card_value).strip():
        for v in olds:
            if norm(v) == norm(card_value):
                return v
        return fmt(card_value)
    if isinstance(existing, tuple):
        raise DataError(f"{INDEX_NAME}: the two sides of a git conflict give {cid} different {column} cells and the card has none; resolve that row by hand first")
    return existing if existing is not None else default


def build(lb, today):
    index_path, links_path = lb / INDEX_NAME, lb / LINKS_NAME
    for p in (index_path, links_path):
        if not p.is_file():
            raise DataError(f"missing {p.name}: copy the package's empty one first")
    index_text = index_path.read_text(encoding="utf-8")
    links_text = links_path.read_text(encoding="utf-8")
    idx = merge_index([parse_index(s, INDEX_NAME) for s in conflict_sides(index_text, INDEX_NAME)], INDEX_NAME)
    lnk = merge_links([parse_links(s, LINKS_NAME) for s in conflict_sides(links_text, LINKS_NAME)], LINKS_NAME)
    cards = load_cards(lb)
    notes = []

    # Rows with no live card.
    gone = sorted(set(idx["rows"]) - set(cards))
    if gone:
        archived = archived_ids(lb)
        lost = [c for c in gone if c not in archived]
        if lost:
            raise DataError(f"{INDEX_NAME}: rows for cards that are not in entries/ or archived/ (a rebuild would lose them): " + ", ".join(lost))
        notes.append(f"left out {len(gone)} rows for archived cards")

    # Links: every existing row, plus card edges.
    links = set(lnk["rows"])
    pairs = {(f, t) for f, _, t in links}
    for cid in sorted(cards):
        for ltype, target in cards[cid]["related"]:
            if ltype is None:
                if (cid, target) in pairs:
                    continue
                ltype = "relates"
            if (cid, ltype, target) not in links:
                links.add((cid, ltype, target))
                pairs.add((cid, target))
    dangling = sorted({e for f, _, t in links for e in (f, t) if ID_RE.fullmatch(e) and e not in cards})
    if dangling:
        notes.append(f"kept {sum(1 for f, _, t in links if f in dangling or t in dangling)} links naming a card not in entries/ ({len(dangling)} ids)")

    # Index rows.
    tables = {t: [] for t in TYPES}
    for cid in sorted(cards):
        c, old = cards[cid], idx["rows"].get(cid)
        if old:
            summary = old["summary"]
        elif c["summary"]:
            summary = cell(c["summary"])
        elif c["title"]:
            summary = cell(c["title"])
        else:
            raise DataError(f"malformed card {c['rel']}: no row in the index, no `summary:` and no `# ` title to build one from")
        cells = [
            pick(c["impact"], old and old["impact"], cell, "n/a", cid, "Impact"),
            pick(c["conf"], old and old["conf"], lambda v: cell(norm(v)), "n/a", cid, "Conf"),
            pick(c["job"], old and old["job"], lambda v: f"`{cell(v)}`", "none", cid, "Job"),
        ]
        tables[c["type"]].append(f"| {cid} | {summary} | {' | '.join(cells)} |")

    counts = {t: len(tables[t]) for t in TYPES}
    total = sum(counts.values())
    head_out = []
    for l in idx["head"]:
        if l == "@Last Updated":
            head_out.append(f"**Last Updated**: {today}")
        elif l == "@Total Cards":
            head_out.append(f"**Total Cards**: {total} ({counts['METHOD']} METHOD, {counts['INSIGHT']} INSIGHT, {counts['BUILD']} BUILD)")
        elif l == "@Total Links":
            head_out.append(f"**Total Links**: {len(links)}")
        elif l == "@Version":
            head_out.append(f"**Version**: {idx['version']}")
        else:
            head_out.append(l)

    index_body = ["## Index Cards", ""]
    for t in TYPES:
        index_body += [f"### {t} Cards ({counts[t]})", "", INDEX_HEADER, INDEX_SEP] + tables[t] + [""]

    # Clusters.
    cl = idx["clusters"]
    members = {}
    for cid in sorted(cards):
        for slug in cards[cid]["clusters"]:
            members.setdefault(slug, []).append(cid)
    for line in cl["loose"]:
        for x in (m.group(0) for m in ID_RE.finditer(line)):
            if x not in cards:
                raise DataError(f"{INDEX_NAME}: a broken Clusters line names {x}, which is not a live card (a rebuild would lose it): {line!r}")
    if cl["loose"]:
        notes.append(f"replaced {len(cl['loose'])} broken Clusters lines (their card ids are listed again from the cards)")
    columns = cl["columns"] or ["Cluster", "Cards"]
    slugs = sorted(set(members) | {s for s, cells in cl["extra"].items() if any(cells)})
    cluster_body = ["## Clusters", ""] + _trim(cl["before"])
    if slugs:
        if cluster_body[-1] != "":
            cluster_body.append("")
        cluster_body += ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
        for slug in slugs:
            extra = iter(cl["extra"].get(slug, [""] * (len(columns) - 2)))
            out = []
            for col in columns:
                out.append(slug if col == "Cluster" else ", ".join(members.get(slug, [])) if col == "Cards" else next(extra))
            cluster_body.append("| " + " | ".join(out) + " |")
    else:
        if cluster_body[-1] != "":
            cluster_body.append("")
        cluster_body.append(CLUSTER_PLACEHOLDER)
    after = _trim(cl["after"])
    if after:
        cluster_body += [""] + after
    cluster_body.append("")

    out = list(head_out)
    for heading in idx["order"]:
        if heading == "## Index Cards":
            out += index_body
        elif heading == "## Clusters":
            out += cluster_body
        else:
            body = next(b for h, b in idx["others"] if h == heading)
            out += [heading] + body
    index_new = "\n".join(_strip_end(out)) + "\n"

    lhead = []
    for l in lnk["head"]:
        if l == "@Last Updated":
            lhead.append(f"**Last Updated**: {today}")
        elif l == "@Total Links":
            lhead.append(f"**Total Links**: {len(links)}")
        else:
            lhead.append(l)
    lout = list(lhead)
    for heading in lnk["order"]:
        if heading == "## Index Card Links":
            lout += [heading, "", LINKS_HEADER, LINKS_SEP] + [f"| {f} | {t} | {to} |" for f, t, to in sorted(links)] + [""]
        else:
            body = next(b for h, b in lnk["others"] if h == heading)
            lout += [heading] + body
    links_new = "\n".join(_strip_end(lout)) + "\n"
    return {INDEX_NAME: (index_text, index_new), LINKS_NAME: (links_text, links_new)}, notes


def _trim(lines):
    lines = list(lines)
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def _strip_end(lines):
    lines = list(lines)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def undated(text):
    return [l for l in text.splitlines() if not DATE_LINE.match(l)]


def atomic_write(path, text, newline):
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline=newline) as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Rebuild logbook_index.md and logbook_links.md from the cards.")
    parser.add_argument("--root", default=".", help="records root that holds foreman/logbook/ (default: current directory)")
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 if a rebuild would change either file")
    parser.add_argument("--date", help=argparse.SUPPRESS)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return EXIT_USAGE if exc.code else EXIT_OK
    try:
        lb = Path(args.root).resolve() / LOGBOOK_REL
        if not lb.is_dir():
            raise UsageError(f"no {LOGBOOK_REL.as_posix()}/ under {Path(args.root).resolve()}: run from the records root or pass --root")
        today = args.date or date.today().isoformat()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", today):
            raise UsageError(f"--date must be YYYY-MM-DD, got {today!r}")
        files, notes = build(lb, today)
        for note in notes:
            print(f"note: {note}")
        changed = [n for n, (old, new) in files.items() if undated(old) != undated(new)]
        if args.check:
            for n in changed:
                old, new = files[n]
                a, b = Counter(undated(old)), Counter(undated(new))
                gone, added = a - b, b - a
                diff = [f"-{l}" for l in undated(old) if gone[l] and not gone.subtract([l])] + \
                       [f"+{l}" for l in undated(new) if added[l] and not added.subtract([l])]
                moved = "" if diff else "; same lines, new order"
                print(f"differs: {n} ({len(diff) - sum(1 for d in diff if d[0] == '-')} lines added, "
                      f"{sum(1 for d in diff if d[0] == '-')} removed by a rebuild{moved})")
                for d in diff[:8]:
                    print(f"  {d[:150]}")
                if len(diff) > 8:
                    print(f"  ... {len(diff) - 8} more")
            if changed:
                print("check: out of date; run python foreman/logbook/rebuild_index.py")
                return EXIT_DATA
            print("check: logbook_index.md and logbook_links.md match the cards")
            return EXIT_OK
        for n in changed:
            old, new = files[n]
            newline = "\r\n" if b"\r\n" in (lb / n).read_bytes() else "\n"
            atomic_write(lb / n, new, newline)
            print(f"wrote {LOGBOOK_REL.as_posix()}/{n}")
        if not changed:
            print("rebuild: logbook_index.md and logbook_links.md already match the cards; nothing written")
        return EXIT_OK
    except UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except DataError as exc:
        print(f"error: {exc} (nothing written)", file=sys.stderr)
        return EXIT_DATA
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_DATA


if __name__ == "__main__":
    sys.exit(main())

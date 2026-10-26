"""Regenerate skills-wiki/graph.html, the Skill Atlas: every skill and agent page, grouped
by the index's sections, linked by the pages' [[wikilinks]] and `relates` (same parser as
wiki_lint). Links to the index itself are left out: the groups carry that structure.

Usage: python scripts/wiki_graph_html.py [<wiki dir>] [<page title>]
"""

from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path

from wiki_lint import collect_edges, parse_frontmatter, wiki_root

HUB = "index"
MARKERS = ("**On site:**", "**In Foreman:**")   # the wiki page's role line; the old spelling still read
LINK = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")

# which part of the route a group belongs to, by the words in its heading
FAMILIES = [
    ("plan", ("before a job", "settling", "fork", "blueprint", "plan →")),
    ("inspect", ("inspection", "end game", "review lens", "plancheck")),
    ("close", ("close", "logbook", "merge")),
    ("run", ("starting", "running", "start")),
]
FAMILY_LABEL = {"plan": "Plan", "run": "Run a job", "inspect": "Inspect", "close": "Merge, close and Logbook", "kit": "Kit"}


def family_of(heading: str) -> str:
    h = heading.lower()
    for fam, words in FAMILIES:
        if any(w in h for w in words):
            return fam
    return "kit"


def read_index(root: Path) -> tuple[list[dict], dict[str, dict]]:
    """Groups in index order, and for each page id: its group and the index's one-liner."""
    path = root / f"{HUB}.md"
    groups: list[dict] = []
    where: dict[str, dict] = {}
    if not path.exists():
        return groups, where
    _, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    current = None
    for line in body.splitlines():
        if line.startswith("## "):
            name = line[3:].strip()
            current = {"name": name, "family": family_of(name), "ids": []}
            groups.append(current)
            continue
        m = re.match(r"\s*[-*]\s+\[\[([^\]|#]+)[^\]]*\]\]\s*(?:(?:[—–-]+|:)\s*(.*))?$", line)
        if m and current is not None:
            pid = m.group(1).strip()
            if pid not in where:
                current["ids"].append(pid)
                where[pid] = {"group": current["name"], "family": current["family"], "blurb": (m.group(2) or "").strip()}
    groups = [g for g in groups if g["ids"]]
    return groups, where


def source_description(root: Path, pid: str) -> dict:
    """The skill's or agent's own frontmatter description, split into when to use it, what it isn't for,
    and its old name. Agents' descriptions run long: their first two sentences are kept."""
    src = root.parent / (f"{pid}.md" if pid.startswith("agents/") else f"skills/{pid}/SKILL.md")
    if not src.exists():
        return {}
    m = re.match(r"---\r?\n(.*?)\r?\n---", src.read_text(encoding="utf-8"), re.S)
    if not m:
        return {}
    lines, text, on = m.group(1).splitlines(), [], False
    for line in lines:
        if line.startswith("description:"):
            on = True
            rest = line[len("description:"):].strip().lstrip(">|").strip()
            if rest:
                text.append(rest)
            continue
        if on:
            if line and not line[0].isspace():
                break
            text.append(line.strip())
    text = " ".join(t for t in text if t)
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z\"(/])", text)
    use, nots, old = [], [], ""
    for s in sentences:
        if s.startswith("Also answers to its old name"):
            old = s.rstrip(".").split(",")[-1].strip()
        elif re.match(r"^Not (for|the|a)\b", s) or re.search(r"\bnot for\b", s):
            nots.append(s)
        else:
            use.append(s)
    if pid.startswith("agents/"):
        use = use[:2]
    return {"use": " ".join(use), "not": " ".join(nots), "old": old}


def page_facts(root: Path, pid: str) -> dict:
    path = root / f"{pid}.md"
    if not path.exists():
        return {}
    fm, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    role = ""
    blurb = ""
    for para in re.split(r"\n\s*\n", body):
        p = para.strip()
        if not p or p.startswith("#") or p.startswith("- "):
            continue
        if p.startswith(MARKERS):
            role = p.split(":**", 1)[1].strip()
            continue
        if re.match(r"^(Slash|Agent|Folder):", p):
            continue
        if not blurb:
            blurb = p
    path_hint = ""
    m = re.search(r"`((?:skills|agents)/[^`]+)`", body)
    if m:
        path_hint = m.group(1)
    clean = lambda s: LINK.sub(lambda mm: mm.group(1).split("/")[-1], s).replace("**", "").replace("`", "")
    slash = re.search(r"Slash:\s*`(/[^`]+)`", body)
    when = re.search(r"^\*\*When to use it:\*\*\s*(.+)$", body, re.M)
    # the extra paragraph after the "On site" line, when there is one: a limit or a pointer worth showing
    paras = [p.strip() for p in re.split(r"\n\s*\n", body.split("\n## ")[0]) if p.strip()]
    note = ""
    for i, p in enumerate(paras):
        if p.startswith(MARKERS) and i + 1 < len(paras) and not paras[i + 1].startswith(("#", "- ", "**When to use it:**")):
            note = clean(paras[i + 1])
    # the typed links from the page's "## Links" section: uses / used by / used after
    rels = []
    sec = re.search(r"^## Links\s*\n(.*?)(?=^## |\Z)", body, re.S | re.M)
    for line in (sec.group(1).splitlines() if sec else []):
        mm = re.match(r"\s*-\s+(uses|used by|used after)\s+\[\[([^\]|#]+)[^\]]*\]\]\s*(?:\((.*)\))?", line)
        if mm:
            rels.append((mm.group(1), mm.group(2).strip(), (mm.group(3) or "").strip()))
    return {"type": str(fm.get("type") or "page"), "role": clean(role), "blurb": clean(blurb), "path": path_hint,
            "slash": slash.group(1) if slash else "", "note": note, "rels": rels, "when": clean(when.group(1)) if when else ""}


def build_data(root: Path) -> dict:
    nodes, edges = collect_edges(root)
    groups, where = read_index(root)
    out_nodes = []
    facts_of = {}
    for n in nodes:
        if n["id"] == HUB:
            continue
        facts = facts_of[n["id"]] = page_facts(root, n["id"])
        w = where.get(n["id"], {"group": "Other pages", "family": "kit", "blurb": ""})
        out_nodes.append({
            "id": n["id"], "label": n["label"], "type": facts.get("type", "page"),
            "group": w["group"], "family": w["family"],
            "blurb": w["blurb"] or facts.get("blurb", ""), "role": facts.get("role", ""), "path": facts.get("path", ""),
            "slash": facts.get("slash", ""), "note": facts.get("note", ""), "when": facts.get("when", ""),
            "uses": [], "usedBy": [], "after": [], "before": [],
            **source_description(root, n["id"]),
        })
    ids = {n["id"] for n in out_nodes}
    # typed relations, both directions: A uses B  <=>  B used by A;  A used after B  <=>  B leads to A
    by = {n["id"]: n for n in out_nodes}
    def add(lst, a, b, note):
        if b in ids and b != a and all(x["id"] != b for x in by[a][lst]):
            by[a][lst].append({"id": b, "note": note})
    for a, f in facts_of.items():
        for verb, b, note in f.get("rels", []):
            if b not in ids:
                continue
            if verb == "uses":
                add("uses", a, b, note); add("usedBy", b, a, note)
            elif verb == "used by":
                add("usedBy", a, b, note); add("uses", b, a, note)
            else:
                add("after", a, b, note); add("before", b, a, note)
    groups = [dict(g, ids=[i for i in g["ids"] if i in ids]) for g in groups]
    groups = [g for g in groups if g["ids"]]
    if any(n["group"] == "Other pages" for n in out_nodes):
        groups.append({"name": "Other pages", "family": "kit", "ids": [n["id"] for n in out_nodes if n["group"] == "Other pages"]})
    out_edges = [[a, b] for a, b in edges if a in ids and b in ids]
    return {"nodes": out_nodes, "edges": out_edges, "groups": groups, "families": FAMILY_LABEL}


TEMPLATE = r"""<title>__TITLE__</title>__ICON__<script>try{var t=localStorage.getItem("foreman-theme");if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t);}catch(e){}</script>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@700;800&family=Big+Shoulders+Stencil+Display:wght@800&family=Martian+Mono:wght@400;500;600&family=Public+Sans:wght@400;500;600;700&display=swap">
<style>
:root{color-scheme:light;
 --ground:#ECEEEA;--panel:#F8F9F6;--panel-2:#E2E6E0;--line:#C9CFC7;--line-2:#DADFD8;
 --ink:#15181A;--ink-2:#454C50;--ink-3:#727A7E;--hivis:#FBB401;
 --plan:#1D4E89;--run:#3B6D2F;--inspect:#8A3B8F;--close:#A5650F;--kit:#6A7378;--edge:#AEB6AD;--focus:#1D4E89}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
 --ground:#101315;--panel:#171B1E;--panel-2:#1F2427;--line:#2C3337;--line-2:#23292C;
 --ink:#E7EAE5;--ink-2:#B4BBB6;--ink-3:#808983;
 --plan:#80AFE9;--run:#8FCB7C;--inspect:#D79DDB;--close:#F0B04A;--kit:#9AA4A8;--edge:#3A4247;--focus:#80AFE9}}
:root[data-theme="dark"]{color-scheme:dark;
 --ground:#101315;--panel:#171B1E;--panel-2:#1F2427;--line:#2C3337;--line-2:#23292C;
 --ink:#E7EAE5;--ink-2:#B4BBB6;--ink-3:#808983;
 --plan:#80AFE9;--run:#8FCB7C;--inspect:#D79DDB;--close:#F0B04A;--kit:#9AA4A8;--edge:#3A4247;--focus:#80AFE9}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--ground);color:var(--ink);font:400 14.5px/1.5 "Public Sans",system-ui,-apple-system,"Segoe UI",sans-serif;padding-inline:16px;display:flex;flex-direction:column}
:focus-visible{outline:2px solid var(--focus);outline-offset:2px}
.f-plan{--c:var(--plan)}.f-run{--c:var(--run)}.f-inspect{--c:var(--inspect)}.f-close{--c:var(--close)}.f-kit{--c:var(--kit)}
header{display:flex;flex-wrap:wrap;gap:10px 28px;align-items:flex-end;justify-content:space-between;padding-block:22px 14px;border-bottom:1px solid var(--line)}
.kick{font:500 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3);display:flex;align-items:center;gap:9px}
.mark{width:30px;height:30px;flex:none;display:inline-block;vertical-align:middle;filter:drop-shadow(1.5px 0 0 #ECEEEA) drop-shadow(-1.5px 0 0 #ECEEEA) drop-shadow(0 1.5px 0 #ECEEEA) drop-shadow(0 -1.5px 0 #ECEEEA)}
h1{margin:8px 0 0;font:800 clamp(34px,5vw,54px)/1 "Big Shoulders Display","Arial Narrow",Impact,sans-serif;text-transform:uppercase;letter-spacing:.01em}
.stats{display:flex;gap:18px;flex-wrap:wrap;font:500 12px/1.2 "Martian Mono",ui-monospace,monospace;color:var(--ink-2)}
.stats b{display:block;font:800 30px/1 "Big Shoulders Stencil Display","Big Shoulders Display","Arial Narrow",sans-serif;color:var(--ink);font-variant-numeric:tabular-nums}
.legend{display:flex;flex-wrap:wrap;gap:6px 14px;padding-block:10px;font:500 12px/1 "Public Sans",system-ui,sans-serif;color:var(--ink-2);align-items:center}
.lg{display:inline-flex;gap:6px;align-items:center}
.lg i{width:11px;height:11px;border-radius:50%;background:var(--c);display:inline-block}
.lg.sq i{border-radius:2px;background:transparent;border:2px solid var(--ink-2)}
.lg.ci i{background:transparent;border:2px solid var(--ink-2)}
.main{flex:1;min-height:0;display:grid;grid-template-columns:minmax(0,1fr) clamp(340px,28vw,480px);border-top:1px solid var(--line);margin-inline:-16px}
#stage{position:relative;min-width:0;min-height:0;overflow:auto}
svg{display:block}
.col-h{font:800 26px "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;letter-spacing:.02em;fill:var(--c)}
.col-rule{stroke:var(--c);stroke-width:3}
.grp-lbl{font:600 10px "Martian Mono",ui-monospace,monospace;text-transform:uppercase;letter-spacing:.1em;fill:var(--ink-3);pointer-events:none;paint-order:stroke;stroke:var(--ground);stroke-width:5px;stroke-linejoin:round}
.edge{fill:none;stroke:var(--edge);stroke-width:1.3;transition:stroke .15s,opacity .15s}
.node .shape{fill:var(--panel);stroke:var(--c);stroke-width:2.4;transition:fill .15s}
.node.fill .shape{fill:var(--c)}
.node text{font:500 11px "Martian Mono",ui-monospace,monospace;fill:var(--ink);paint-order:stroke;stroke:var(--ground);stroke-width:4px;stroke-linejoin:round;pointer-events:none}
.node{cursor:pointer}
.node:hover .shape{fill:var(--c)}
svg.has-sel .edge{opacity:.12}
svg.has-sel .edge.hot{opacity:1;stroke:var(--ink);stroke-width:2}
svg.has-sel .node{opacity:.25}
svg.has-sel .node.near,svg.has-sel .node.sel{opacity:1}
.node.sel .shape{fill:var(--c);stroke:var(--ink);stroke-width:3}
aside{border-left:1px solid var(--line);background:var(--panel);display:flex;flex-direction:column;min-height:0}
.detail{padding:18px 20px 20px;display:flex;flex-direction:column;gap:12px;border-top:4px solid var(--c);flex:1;min-height:0;overflow:auto}
.detail .dk{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font:600 10.5px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.detail .dk .ty{color:var(--ground);background:var(--c);padding:3px 6px}
.detail .ttl{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.detail h2{margin:0;font:800 34px/1 "Big Shoulders Display","Arial Narrow",sans-serif;letter-spacing:.01em;overflow-wrap:anywhere}
.detail .slash{font:600 12px "Martian Mono",ui-monospace,monospace;color:var(--c)}
.detail p{margin:0;color:var(--ink-2)}
.detail .what{color:var(--ink);font-size:15.5px;line-height:1.45}
.detail .role{color:var(--ink);font-size:13.5px;border-left:3px solid var(--c);padding:2px 0 2px 11px}
.detail .note{font-size:13px;color:var(--ink-3)}
.detail code{font:500 11.5px "Martian Mono",ui-monospace,monospace;color:var(--ink-2);background:var(--panel-2);padding:3px 6px;align-self:flex-start;overflow-wrap:anywhere}
.conn{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px 16px;padding-top:12px;border-top:1px solid var(--line-2)}
.conn h3{margin:0 0 6px;font:600 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.conn h3 b{color:var(--ink);font-weight:600}
.conn ul{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:4px}
.nb{display:flex;gap:7px;align-items:baseline;width:100%;text-align:left;font:500 12px/1.35 "Martian Mono",ui-monospace,monospace;border:1px solid var(--line);background:var(--ground);color:var(--ink);padding:5px 8px;cursor:pointer}
.nb i{flex:none;width:8px;height:8px;border-radius:50%;background:var(--c);transform:translateY(-1px)}
.nb.ag i{border-radius:1px}
.nb small{display:block;font:400 11.5px/1.35 "Public Sans",system-ui,sans-serif;color:var(--ink-3)}
.nb:hover{border-color:var(--c)}
.route{display:flex;flex-wrap:wrap;gap:6px}
.route span{font:600 11px/1 "Martian Mono",ui-monospace,monospace;padding:6px 8px;border:1px solid var(--line);color:var(--ink-2);display:inline-flex;gap:6px;align-items:center}
.route span i{width:8px;height:8px;border-radius:50%;background:var(--c)}
.sec h3{margin:0 0 6px;font:600 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.sec p{font-size:13.5px;line-height:1.5}
.sec .not{margin-top:6px;color:var(--ink-3)}
.sec .old{margin-top:6px;font:500 11.5px "Martian Mono",ui-monospace,monospace;color:var(--ink-3)}
.steps{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;counter-reset:s}
.steps li{display:grid;grid-template-columns:26px auto minmax(0,1fr);gap:10px;padding:6px 0;border-bottom:1px dashed var(--line-2);counter-increment:s;align-items:baseline}
.steps li::before{content:counter(s,decimal-leading-zero);font:800 17px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;color:var(--c,var(--ink-3))}
.steps .sb{background:none;border:0;padding:0;text-align:left;cursor:pointer;font:600 13px "Martian Mono",ui-monospace,monospace;color:var(--ink)}
.steps .sb:hover{color:var(--c)}
.steps .pl{font:600 13px "Martian Mono",ui-monospace,monospace;color:var(--ink-2)}
.steps small{color:var(--ink-3);font-size:12.5px;line-height:1.4;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.steps .ph{counter-increment:none;grid-column:1/-1;display:block;font:600 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);padding:10px 0 2px;border:0}
.steps .ph::before{content:none}
.where{display:flex;gap:8px;align-items:center;flex-wrap:wrap;font:500 12px "Martian Mono",ui-monospace,monospace;color:var(--ink-2)}
.where button{font:600 11.5px "Martian Mono",ui-monospace,monospace;border:1px solid var(--line);background:var(--ground);color:var(--ink);padding:4px 8px;cursor:pointer}
.where button:hover{border-color:var(--c)}
.detail.docket{padding:16px 16px 22px;background:var(--ground);border-top:0;gap:0}
aside:has(.docket){background:var(--ground)}
.dkt{position:relative;background:var(--panel);border:1px solid var(--line);border-top:0;display:flex;flex-direction:column}
.dkt .haz{height:9px;background:repeating-linear-gradient(-45deg,var(--hivis) 0 9px,#101316 9px 18px)}
.dkt .band{height:5px;background:var(--c)}
.dkt .punch{height:14px;background:radial-gradient(circle at 12px 7px,var(--ground) 0 3.5px,transparent 4px) 0 0/24px 14px repeat-x;border-bottom:1px dashed var(--line)}
.dkt-h{display:grid;grid-template-columns:auto minmax(0,1fr);gap:14px;padding:16px 18px 8px;align-items:start;position:relative}
.dkt .no{display:flex;flex-direction:column;align-items:center;justify-content:center;min-width:66px;padding:9px 6px 7px;background:var(--c);color:#101316}
.dkt .no b{font:800 42px/.9 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;font-variant-numeric:tabular-nums}
.dkt .no span{font:600 9.5px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;margin-top:3px}
.dkt .eyebrow{font:600 10px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--c);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dkt h2{white-space:nowrap;padding-right:88px;margin:5px 0 9px;font:800 46px/.92 "Big Shoulders Display","Arial Narrow",sans-serif;letter-spacing:.005em;overflow-wrap:anywhere}
.dkt .stamp{position:absolute;right:16px;top:40px;transform:rotate(4deg);border:4px double var(--c);color:var(--c);font:800 19px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;letter-spacing:.14em;text-transform:uppercase;padding:5px 9px 4px}
.dkt .lead{padding:6px 18px 16px;margin:0;font-size:16.5px;line-height:1.45;color:var(--ink)}
.dkt .bx{margin:6px 18px 14px;border:1px solid var(--line);padding:13px 13px 11px;position:relative}
.dkt .lbl{position:absolute;top:-8px;left:10px;background:var(--panel);padding:0 6px;font:600 10px/16px "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--c)}
.dkt .bx p{margin:0;font-size:13.5px;line-height:1.5;color:var(--ink)}
.dkt .bx p.sub{margin-top:7px;color:var(--ink-3);font-size:12.5px}
.dkt .says{display:flex;flex-wrap:wrap;gap:6px}
.dkt .says span{font:500 12.5px/1.2 "Public Sans",system-ui,sans-serif;color:var(--ink);background:var(--panel-2);border-left:3px solid var(--c);padding:5px 9px}
.dkt .says span::before{content:"\201C";color:var(--ink-3)}
.dkt .says span::after{content:"\201D";color:var(--ink-3)}
.dkt .notice{margin:2px 18px 16px;background:#FBB401;border:2px solid #101316;display:flex;color:#101316}
.dkt .notice b{flex:none;display:flex;align-items:center;background:#101316;color:#FBB401;font:600 10px/1.2 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;padding:8px 9px}
.dkt .notice p{margin:0;padding:8px 11px;font:600 13px/1.45 "Public Sans",system-ui,sans-serif;color:#101316}
.dkt .tape{margin:4px 18px 16px}
.dkt .tl{display:flex;justify-content:space-between;align-items:baseline;font:600 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);margin-bottom:7px}
.dkt .tl b{color:var(--ink)}
.dkt .ts{display:flex;gap:2px;border-left:2px solid var(--ink-3);border-right:2px solid var(--ink-3);padding:0 2px}
.dkt .ts button{flex:1;min-width:0;height:24px;border:0;background:var(--panel-2);color:var(--ink-3);font:700 10px "Martian Mono",ui-monospace,monospace;cursor:pointer;padding:0}
.dkt .ts button.past{background:var(--line)}
.dkt .ts button.here{background:#FBB401;color:#101316}
.dkt .ts button:hover{outline:2px solid var(--c);outline-offset:-2px}
.dkt .tn{display:flex;justify-content:space-between;gap:10px;margin-top:7px}
.dkt .tn button{font:600 11.5px "Martian Mono",ui-monospace,monospace;background:none;border:0;color:var(--ink-2);cursor:pointer;padding:0}
.dkt .tn button:hover{color:var(--c)}
.dkt .tear{border-top:2px dashed var(--line);position:relative;margin-top:2px}
.dkt .tear::before,.dkt .tear::after{content:"";position:absolute;top:-8px;width:14px;height:14px;border-radius:50%;background:var(--ground);border:1px solid var(--line)}
.dkt .tear::before{left:-8px}
.dkt .tear::after{right:-8px}
.dkt .stub{padding:16px 18px 6px;display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px 14px}
.dkt .stub h3{margin:0 0 6px;font:600 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.dkt .stub h3 b{color:var(--ink);font-weight:600}
.dkt .stub ul{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:4px}
.dkt .stub .none{color:var(--ink-3);font-size:13px;margin:0}
.dkt .foot{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;padding:10px 18px 14px;font:500 11px "Martian Mono",ui-monospace,monospace;color:var(--ink-3)}
@media (max-width:860px){
 .main{grid-template-columns:1fr}
 #stage{max-height:70vh}
 aside{border-left:0;border-top:1px solid var(--line)}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}

.theme-toggle{position:fixed;top:calc(env(safe-area-inset-top,0px) + 12px);right:16px;z-index:50;font:600 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;padding:7px 11px;border:1px solid var(--line);border-radius:0;background:var(--panel);color:var(--ink);cursor:pointer}
.theme-toggle:hover{border-color:var(--ink)}
.theme-toggle:focus-visible{outline:2px solid var(--hivis);outline-offset:2px}
</style>
<button type="button" class="theme-toggle" data-theme-toggle>Light</button>
<header>
 <div><div class="kick">__MARK__<span>Topping Out · skills-wiki</span></div><h1>__TITLE__</h1></div>
 <div class="stats"><div><b id="n-skill"></b>skills</div><div><b id="n-agent"></b>agents</div><div><b id="n-edge"></b>links</div></div>
</header>
<div class="legend" id="legend"></div>
<div class="main">
 <div id="stage"><svg id="g" role="img" aria-label="Map of skills and agents, grouped, with the links between them"></svg></div>
 <aside>
  <div class="detail" id="detail" aria-live="polite"></div>
 </aside>
</div>
<script>
(function(){
const DATA = __DATA__;
const NS="http://www.w3.org/2000/svg";
const nodes=DATA.nodes, edges=DATA.edges, groups=DATA.groups;
const byId=Object.fromEntries(nodes.map(n=>[n.id,n]));
const nbr=Object.fromEntries(nodes.map(n=>[n.id,[]]));
edges.forEach(([a,b])=>{nbr[a].push(b);nbr[b].push(a)});
const svg=document.getElementById("g"), stage=document.getElementById("stage");
document.getElementById("n-skill").textContent=nodes.filter(n=>n.type==="skill").length;
document.getElementById("n-agent").textContent=nodes.filter(n=>n.type==="agent").length;
document.getElementById("n-edge").textContent=edges.length;
const fams=[...new Set(groups.map(g=>g.family))];
document.getElementById("legend").innerHTML=fams.map(f=>'<span class="lg f-'+f+'"><i></i>'+(DATA.families[f]||f)+'</span>').join("")+
 '<span class="lg ci"><i></i>skill</span><span class="lg sq"><i></i>agent</span>';
let sel=null;
const ORDER=["plan","run","inspect","close","kit"];
const cols=ORDER.filter(f=>groups.some(g=>g.family===f));
const ROW=27, GAP=16, TOP=70, PADX=26, MINCOL=178;
let COLW=230;const pos={};let H=0;
// the columns share the stage's whole width (no dead band beside the panel); narrower than that, the stage scrolls
function layout(){COLW=Math.max(MINCOL,Math.floor((stage.clientWidth-PADX*2+40)/cols.length));H=0;
 cols.forEach((f,ci)=>{let y=TOP;const x=PADX+ci*COLW;
  groups.filter(g=>g.family===f).forEach(g=>{g.x=x;g.y=y+4;y+=18;g.ids.forEach(id=>{pos[id]={x:x+8,y:y+8};y+=ROW});y+=GAP});
  H=Math.max(H,y)});
 const W=PADX*2+cols.length*COLW-40;
 svg.setAttribute("width",W);svg.setAttribute("height",H+10);svg.setAttribute("viewBox","0 0 "+W+" "+(H+10))}
const edgeEls=[],nodeEls={};
function curve(a,b){const A=pos[a],B=pos[b];if(A.x===B.x){const bx=Math.max(6,A.x-38-Math.min(60,Math.abs(B.y-A.y)*.18)); /* a same-column link bends left, never past the drawing's edge */return "M"+A.x+","+A.y+" C"+bx+","+A.y+" "+bx+","+B.y+" "+B.x+","+B.y}
 const L=A.x<B.x?A:B,R=A.x<B.x?B:A,dx=(R.x-L.x)*.45;return "M"+L.x+","+L.y+" C"+(L.x+dx)+","+L.y+" "+(R.x-dx)+","+R.y+" "+R.x+","+R.y}
function build(){layout();svg.innerHTML="";edgeEls.length=0;
 const heads=[];
 cols.forEach((f,ci)=>{const x=PADX+ci*COLW;const h=document.createElementNS(NS,"text");h.setAttribute("class","col-h f-"+f);h.setAttribute("x",x);h.setAttribute("y",34);h.textContent=DATA.families[f]||f;svg.appendChild(h);heads.push(h);
  const r=document.createElementNS(NS,"line");r.setAttribute("class","col-rule f-"+f);r.setAttribute("x1",x);r.setAttribute("x2",x+COLW-40);r.setAttribute("y1",46);r.setAttribute("y2",46);svg.appendChild(r)});
 // a column title never runs into the next column: shrink it until it fits its rule (again once the web fonts land)
 const fitHeads=()=>heads.forEach(h=>{let fs=26;h.style.fontSize="";while(h.getComputedTextLength()>COLW-44&&fs>14){fs--;h.style.fontSize=fs+"px";}});
 fitHeads();if(document.fonts&&document.fonts.ready)document.fonts.ready.then(fitHeads);
 const lbls=[];
 groups.forEach(g=>{const t=document.createElementNS(NS,"text");t.setAttribute("class","grp-lbl");t.setAttribute("x",g.x);t.setAttribute("y",g.y+8);t.textContent=g.name.split(":")[0].replace(/\s*\(.*\)\s*$/,"").replace(/^The /,"");svg.appendChild(t);lbls.push(t)});
 // a group label never runs into the next column either: shrink it, then trim it with an ellipsis
 const fitLbls=()=>lbls.forEach(t=>{const full=t.dataset.full||(t.dataset.full=t.textContent);t.textContent=full;let fs=10;t.style.fontSize="";
  while(t.getComputedTextLength()>COLW-34&&fs>8.5){fs-=.5;t.style.fontSize=fs+"px";}
  let s=full;while(t.getComputedTextLength()>COLW-34&&s.length>4){s=s.slice(0,-1);t.textContent=s.trimEnd()+"…";}
  if(t.textContent!==full){const tip=document.createElementNS(NS,"title");tip.textContent=full;t.appendChild(tip)}});
 fitLbls();if(document.fonts&&document.fonts.ready)document.fonts.ready.then(fitLbls);
 edges.forEach(([a,b])=>{const l=document.createElementNS(NS,"path");l.setAttribute("class","edge");l.setAttribute("d",curve(a,b));l.dataset.a=a;l.dataset.b=b;svg.appendChild(l);edgeEls.push(l)});
 nodes.forEach(n=>{const P=pos[n.id];if(!P)return;const g=document.createElementNS(NS,"g");g.setAttribute("class","node f-"+n.family);g.setAttribute("tabindex","0");
  g.setAttribute("role","button");g.setAttribute("aria-label",n.label+", "+n.type);g.setAttribute("transform","translate("+P.x+","+P.y+")");
  const r=6; let s;
  if(n.type==="agent"){s=document.createElementNS(NS,"rect");s.setAttribute("x",-r);s.setAttribute("y",-r);s.setAttribute("width",2*r);s.setAttribute("height",2*r);s.setAttribute("rx",1.5)}
  else{s=document.createElementNS(NS,"circle");s.setAttribute("r",r)}
  s.setAttribute("class","shape");const t=document.createElementNS(NS,"text");t.setAttribute("x",r+8);t.setAttribute("dy","0.35em");t.textContent=n.label;
  const hit=document.createElementNS(NS,"rect");hit.setAttribute("x",-10);hit.setAttribute("y",-12);hit.setAttribute("width",COLW-50);hit.setAttribute("height",24);hit.setAttribute("fill","transparent");
  g.appendChild(hit);g.appendChild(s);g.appendChild(t);
  g.addEventListener("click",()=>choose(n.id));
  g.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();choose(n.id)}});
  svg.appendChild(g);nodeEls[n.id]=g})}
function paint(){
 edgeEls.forEach(l=>{const on=!!sel&&(l.dataset.a===sel||l.dataset.b===sel);l.classList.toggle("hot",on);if(on)svg.appendChild(l)});
 nodes.forEach(n=>{const g=nodeEls[n.id];if(!g)return;const near=!!sel&&nbr[sel].includes(n.id);g.classList.toggle("sel",n.id===sel);g.classList.toggle("near",near);g.classList.toggle("fill",near);if(near||n.id===sel)svg.appendChild(g)});
 svg.classList.toggle("has-sel",!!sel)}
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const ROUTE=[["ph","Before a job"],["f-sketch"],["f-survey"],["f-blueprint"],["f-plancheck"],["f-schedule"],
 ["ph","Each job"],["f-shift"],["pl","work orders","the builder builds one task at a time; the foreman reviews each"],["f-inspect"],["pack-review"],["xreview"],["adjudicate"],
 ["pl","PR","opened on your word"],["f-greploop"],["pl","merge","your word"],["ph","After the merge"],["f-signoff"],["f-board"]];
const STEPS=ROUTE.filter(r=>r[0]!=="ph"&&r[0]!=="pl"&&byId[r[0]]).map(r=>r[0]);
function chip(r,shared){const m=byId[r.id];return '<li><button type="button" class="nb f-'+m.family+(m.type==="agent"?" ag":"")+'" data-id="'+esc(r.id)+'"><i></i><span>'+esc(m.label)+(r.note&&!shared?'<small>'+esc(r.note)+'</small>':'')+'</span></button></li>'}
// a note every link in the block shares is said once, under the heading, not on each chip
function block(title,arrow,rs){if(!rs.length)return '';const shared=rs.length>1&&rs[0].note&&rs.every(r=>r.note===rs[0].note)?rs[0].note:"";
 return '<div><h3>'+arrow+' '+title+' <b>'+rs.length+'</b></h3>'+(shared?'<p class="note" style="margin:-2px 0 6px">'+esc(shared)+'</p>':'')+'<ul>'+rs.map(r=>chip(r,!!shared)).join("")+'</ul></div>'}
function routeHTML(){return '<ol class="steps">'+ROUTE.map(r=>{
  if(r[0]==="ph")return '<li class="ph">'+esc(r[1])+'</li>';
  if(r[0]==="pl")return '<li class="f-kit"><span class="pl">'+esc(r[1])+'</span><small title="'+esc(r[2])+'">'+esc(r[2])+'</small></li>';
  const n=byId[r[0]];if(!n)return '';return '<li class="f-'+n.family+'"><button type="button" class="sb" data-id="'+esc(n.id)+'">'+esc(n.label)+'</button><small title="'+esc(n.blurb)+'">'+esc(n.blurb)+'</small></li>'}).join("")+'</ol>'}
function detail(){const d=document.getElementById("detail");
 if(!sel){d.className="detail f-kit";
  d.innerHTML='<div class="dk">The route, in order</div><h2>From sketch to sign-off</h2><p class="what">The map groups every skill and agent by stage; this is the order a project runs them. Pick a step here or anything on the map.</p>'+routeHTML();
  d.querySelectorAll(".sb").forEach(b=>b.addEventListener("click",()=>choose(b.dataset.id)));return}
 const n=byId[sel];d.className="detail docket f-"+n.family;
 const typed=new Set([...n.uses,...n.usedBy,...n.after,...n.before].map(r=>r.id));
 const other=nbr[sel].filter(id=>!typed.has(id)).map(id=>({id,note:""}));
 const conn=block("Comes after","&larr;",n.after)+block("Leads to","&rarr;",n.before)+block("Uses","&rarr;",n.uses)+block("Used by","&larr;",n.usedBy)+block("Also linked","&middot;",other);
 const i=STEPS.indexOf(sel), onRoute=i>=0;
 const code={plan:"PL",run:"RN",inspect:"IN",close:"CL",kit:"KT"}[n.family]||"--";
 // the description's when-sentences, without its quoted trigger phrases
 const sents=(n.use||"").split(/(?<=[.!?])\s+/), when=sents.filter(s=>/\b(use (when|for|this|it)|when the|before|after|typical triggers)\b/i.test(s)).join(" ")||n.use||"";
 // the description's own trigger phrases become "say it" chips (and leave the when-sentence)
 const says=[...new Set([...(n.use||"").matchAll(/"([^"]{2,60})"/g)].map(m=>m[1]))].slice(0,6);
 const whenText=n.when||when.replace(/,?\s*(?:says\s+)?"[^"]*"(?:\s*\([^)]*\))?/g,"").replace(/\s*,\s*,/g,",").replace(/,\s*(?=[.;])/g,"").replace(/\s{2,}/g," ").replace(/,\s*or\s*,/g,", or").trim();
 const tape=onRoute?'<div class="tape"><div class="tl"><span>On the route</span><span><b>step '+(i+1)+'</b> of '+STEPS.length+'</span></div><div class="ts">'+
   STEPS.map((id,k)=>'<button type="button" class="'+(k<i?"past":k===i?"here":"")+'" data-id="'+esc(id)+'" title="'+esc(byId[id].label)+'">'+(k+1)+'</button>').join("")+'</div>'+
   '<div class="tn">'+(STEPS[i-1]?'<button type="button" data-id="'+esc(STEPS[i-1])+'">&larr; '+esc(byId[STEPS[i-1]].label)+'</button>':'<span></span>')+(STEPS[i+1]?'<button type="button" data-id="'+esc(STEPS[i+1])+'">'+esc(byId[STEPS[i+1]].label)+' &rarr;</button>':'')+'</div></div>':'';
 d.innerHTML='<div class="dkt"><div class="haz"></div><div class="band"></div><div class="punch"></div>'+
  '<div class="dkt-h"><div class="no">'+(onRoute?'<b>'+String(i+1).padStart(2,"0")+'</b><span>of '+STEPS.length+'</span>':'<b>'+code+'</b><span>'+esc(n.type)+'</span>')+'</div>'+
   '<div><div class="eyebrow" title="'+esc(DATA.families[n.family]||n.family)+'">'+esc(n.group.split(":")[0].replace(/\s*\(.*\)\s*$/,"").replace(/^The /,""))+'</div><h2><span>'+esc(n.label)+'</span></h2>'+
   '</div>'+
   '<div class="stamp">'+esc(n.type)+'</div></div>'+
  (n.blurb?'<p class="lead">'+esc(n.blurb)+'</p>':'')+
  (n.role?'<div class="bx"><span class="lbl">On site</span><p>'+esc(n.role)+'</p>'+(n.note?'<p class="sub">'+esc(n.note)+'</p>':'')+'</div>':'')+
  (says.length?'<div class="bx"><span class="lbl">Say it</span><div class="says">'+says.map(s=>'<span>'+esc(s)+'</span>').join("")+'</div></div>':'')+
  (whenText?'<div class="bx"><span class="lbl">When to use it</span><p>'+esc(whenText)+'</p></div>':'')+
  (n.not?'<div class="notice"><b>Not for</b><p>'+esc(n.not.replace(/^Not for\s*/i,"").replace(/^Not the\s*/i,"the "))+'</p></div>':'')+
  tape+'<div class="tear"></div>'+
  '<div class="stub">'+(conn||'<p class="none">No links to other skills or agents.</p>')+'</div>'+
  '<div class="foot"><span>'+esc(n.path||"")+'</span>'+(n.old?'<span>old name '+esc(n.old)+'</span>':'')+'</div></div>';
 d.querySelectorAll(".nb,.ts button,.tn button").forEach(b=>b.addEventListener("click",()=>choose(b.dataset.id)));
 // a long name shrinks to fit its line instead of breaking mid-word (again once the web fonts land)
 const h=d.querySelector(".dkt h2"),fit=()=>{if(!h)return;const s=h.firstChild,room=h.clientWidth-88;let fs=46;h.style.fontSize="";while(s.offsetWidth>room&&fs>22){fs-=2;h.style.fontSize=fs+"px"}};
 fit();if(document.fonts&&document.fonts.ready)document.fonts.ready.then(fit)}
function choose(id){sel=(sel===id)?null:id;paint();detail()}
svg.addEventListener("click",e=>{if(e.target===svg){sel=null;paint();detail()}});
build();paint();detail();
let rz;window.addEventListener("resize",()=>{clearTimeout(rz);rz=setTimeout(()=>{const was=COLW;layout();if(COLW!==was){build();paint()}},120)});
})();
</script>

<script>(function(){var r=document.documentElement;function cur(){var t=r.getAttribute("data-theme");if(t==="light"||t==="dark")return t;return window.matchMedia&&matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";}document.querySelectorAll("[data-theme-toggle]").forEach(function(b){function lab(){var to=cur()==="dark"?"light":"dark";b.textContent=to==="dark"?"Dark":"Light";b.setAttribute("aria-label","Switch to "+to+" mode");b.title="Switch to "+to+" mode";}lab();b.addEventListener("click",function(){var n=cur()==="dark"?"light":"dark";r.setAttribute("data-theme",n);try{localStorage.setItem("foreman-theme",n);}catch(e){}document.querySelectorAll("[data-theme-toggle]").forEach(function(x){x.dispatchEvent(new Event("relabel"));});});b.addEventListener("relabel",lab);});})();</script>"""


def logo_uri(path):
    """The hard hat as a data: URI (pages stay single-file); '' when the file is missing."""
    try:
        return "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode("ascii")
    except OSError:
        return ""


def render(root: Path, title: str) -> str:
    data = build_data(root)
    logo = logo_uri(Path(__file__).resolve().parent.parent / "assets" / "foreman-logo-128.png")
    icon = f'<link rel="icon" type="image/png" href="{logo}">' if logo else ""
    mark = f'<img class="mark" src="{logo}" alt="">' if logo else ""
    return TEMPLATE.replace("__TITLE__", title).replace("__ICON__", icon).replace("__MARK__", mark).replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    root = wiki_root(Path(argv[1]) if len(argv) > 1 else None)
    title = argv[2] if len(argv) > 2 else "Skill Atlas"
    out = root / "graph.html"
    out.write_text(render(root, title), encoding="utf-8", newline="\n")
    data = build_data(root)
    print(f"wrote {out} ({len(data['nodes'])} pages, {len(data['edges'])} links, {len(data['groups'])} groups)")
    return 0


if __name__ == "__main__":
    scripts = Path(__file__).resolve().parent
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    raise SystemExit(main())

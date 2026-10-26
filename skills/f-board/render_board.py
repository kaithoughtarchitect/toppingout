#!/usr/bin/env python3
"""Project Board tool: validate BOARD.json, apply one lifecycle event, render board.html.

Stdlib only. Every event validates the data, applies the change to a copy, validates
the result, renders the page IN MEMORY, then writes both files through temp files
and atomic replaces: a failed event leaves BOARD.json untouched. Every event bumps
`version` once. Never hand-edit board.html; hand-edit BOARD.json only for text (titles,
summaries), then run `render`.

  render_board.py BOARD.json init --title "..." --head "<outcome>" [--test "..."] --job <id> --job-title "..." [--iteration]
                                                        start a board for a project not cut by /f-schedule
                                                        (--iteration: a board of small jobs added as they are found)
  render_board.py BOARD.json [render] [--standalone]   validate + write board.html
  The board opens in the browser on its first page and at a topping out (FOREMAN_BOARD_NO_OPEN=1: never).
  render_board.py BOARD.json check                      validate only
  render_board.py BOARD.json next [--after-close <job>] eligible jobs (now, or after closing <job>)
  render_board.py BOARD.json start   <job> --run J7
  render_board.py BOARD.json close   <job> --pr "#22" --merge <sha> (--next <job> | --no-next --reason "...")
                                     [--run J7] [--note "..."] [--standfirst "..."]
  render_board.py BOARD.json halt    <job> --reason "..." --to open|decision [--decision "..."]
  render_board.py BOARD.json decided <job> --note "the owner's decision, quoted"
  render_board.py BOARD.json add     <job> --title "..." [--needs a,b] [--decision "..."] [--summary "..."]
                                     [--merged --pr "#5" --merge <sha> --run J5]   (backfill a job already merged)
  render_board.py BOARD.json split   <job> --into "a=Title A,b=Title B" [--chain] [--active a]   (a suffix or the full child id)
  render_board.py BOARD.json covered <job> --by <job> --quote "<the owner's words>"   (an open job made redundant: it leaves the board)
  render_board.py BOARD.json set-next <job>
  render_board.py BOARD.json topout --report <path to the topping out report> [--quote "<the owner's words>"] [--head yes|partly|no]
  render_board.py BOARD.json report                    a topped-out board: print the mechanical part of the topping out
                                                        report (jobs, PRs, merges, carried over, owed) as Markdown
                                     the board's head is reached: freeze the board (no event runs after it);
                                     jobs not merged or resolved are carried over to the next head. Without
                                     --quote only when every job is merged or resolved; with any job unfinished,
                                     the owner's own words (--quote), never a goal's. No eligible next job alone
                                     is not a topping out

Jobs have a `kind`: `build` (default: delivered by a run and a PR) or `decision`
(delivered by the owner's decision). Stored states:
  build:    open | in-progress | merged | decision (halted for an owner question)
  decision: decision | resolved
`open` jobs are shown as ready (every need satisfied) or blocked; a need is satisfied
when its job is `merged` or `resolved`. At most one job is in progress at a time.

Exit codes: 0 ok · 1 the data is invalid (BOARD ERROR) · 2 bad usage or an impossible
event (USAGE ERROR) · 3 crash · 4 the event was recorded but the page wasn't written.
Write order: BOARD.json is authoritative and is written first (atomic replace); board.html is
derived from it and written second. Exit 1-3: BOARD.json unchanged. Exit 4: BOARD.json holds
the new version, the page is stale; fix the cause and run `render` (never replay the event).
"""
import base64
import copy
import datetime
import html
import json
import os
import re
import sys
from pathlib import Path

KINDS = ("build", "decision")
STORED = {"build": ("open", "in-progress", "merged", "decision"), "decision": ("decision", "resolved")}
SHOWN = ("merged", "resolved", "in-progress", "ready", "blocked", "decision")
LABEL = {"merged": "merged", "resolved": "decided", "in-progress": "in progress", "ready": "ready to build",
         "blocked": "blocked", "decision": "needs a decision"}
DONE = ("merged", "resolved")
SHA = re.compile(r"^[0-9a-f]{7,40}$")
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,15}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WARNINGS = []


class SpineError(Exception):
    def __init__(self, errors):
        self.errors = errors


class Usage(Exception):
    pass


# ---------------------------------------------------------------- model

def kind(b):
    return b.get("kind", "build")


def stored(b):
    s = b.get("state")
    if s in ("ready", "blocked") and kind(b) == "build":
        WARNINGS.append(f"job {b.get('id')}: legacy stored state {s!r} read as 'open' (ready/blocked are derived)")
        return "open"
    return s


def shown_state(b, by_id):
    s = stored(b)
    if s != "open":
        return s
    return "ready" if all(stored(by_id[n]) in DONE for n in b.get("needs", [])) else "blocked"


def eligible(board):
    by_id = {b["id"]: b for b in board["jobs"]}
    return [b for b in board["jobs"] if shown_state(b, by_id) == "ready"]


def is_str(v):
    return isinstance(v, str) and v.strip() != ""


def validate(board):
    e = []
    if not isinstance(board, dict):
        raise SpineError(["BOARD.json is not an object"])
    if type(board.get("schema")) is not int or board.get("schema") != 1:
        e.append(f"schema must be 1, got {board.get('schema')!r}")
    project = board.get("project")
    if not isinstance(project, dict):
        e.append("project must be an object")
        project = {}
    if not is_str(project.get("title")):
        e.append("project.title is empty")
    head = project.get("head")
    if not isinstance(head, dict) or not is_str(head.get("outcome")):
        e.append("project.head.outcome is empty")
    if isinstance(head, dict) and head.get("test") is not None and not isinstance(head.get("test"), str):
        e.append("project.head.test must be a string when present")
    for f in ("owed", "alerts", "facts"):
        v = project.get(f, [])
        if not isinstance(v, list) or not all(isinstance(n, str) for n in v):
            e.append(f"project.{f} must be a list of strings")
    les = project.get("lesson")
    if les is not None and not (isinstance(les, dict) and is_str(les.get("title")) and isinstance(les.get("rule", ""), str)):
        e.append("project.lesson must be an object with a title (and an optional rule)")
    owed = project.get("owed", [])
    if not isinstance(owed, list) or not all(isinstance(n, str) for n in owed):
        e.append("project.owed must be a list of strings")
    for f in ("eyebrow", "standfirst", "project_file"):
        if f in project and project[f] is not None and not isinstance(project[f], str):
            e.append(f"project.{f} must be a string")
    if project.get("mode") not in (None, "iteration"):
        e.append(f"project.mode must be 'iteration' when present, got {project.get('mode')!r}")
    top = board.get("topped_out")
    if top is not None:
        if not (isinstance(top, dict) and isinstance(top.get("date"), str) and DATE.match(top["date"])
                and type(top.get("version")) is int and is_str(top.get("report"))
                and isinstance(top.get("carried", []), list) and all(isinstance(x, str) for x in top.get("carried", []))):
            e.append("topped_out must be {date: YYYY-MM-DD, version: int, report: path, carried: [job ids]}")
        else:
            ids_now = {b.get("id") for b in board.get("jobs", []) if isinstance(b, dict)}
            missing = [x for x in top.get("carried", []) if x not in ids_now]
            if missing:
                e.append(f"topped_out.carried names jobs that aren't on the board: {missing}")
            if top.get("head_reached") not in (None, "yes", "partly", "no"):
                e.append("topped_out.head_reached must be yes, partly or no")
            if any(isinstance(b, dict) and b.get("state") == "in-progress" for b in board.get("jobs", [])):
                e.append("a topped-out board can't have a job in progress")
    pub = board.get("publish", {})
    if not isinstance(pub, dict):
        e.append("publish must be an object (use {} if not yet published)")
        pub = {}
    lh = pub.get("local_html", "board.html")
    if not isinstance(lh, str) or Path(lh).name != lh or not lh.endswith(".html"):
        e.append(f"publish.local_html must be a bare file name ending .html, got {lh!r}")
    if pub.get("url") is not None and not isinstance(pub.get("url"), str):
        e.append("publish.url must be a string or null")
    v = board.get("version")
    if isinstance(v, bool) or not isinstance(v, int) or v < 1:
        e.append(f"version must be a positive integer, got {v!r}")
    up = board.get("updated")
    if not isinstance(up, str) or not DATE.match(up):
        e.append(f"updated must be a YYYY-MM-DD date, got {up!r}")
    else:
        try:
            datetime.date.fromisoformat(up)
        except ValueError:
            e.append(f"updated {up!r} is not a real date")
    nxt = board.get("next")
    if nxt is not None and not isinstance(nxt, str):
        e.append(f"next must be a job id or null, got {nxt!r}")
        nxt = None
    jobs = board.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        e.append("jobs must be a non-empty list")
        raise SpineError(e)
    ids = []
    for i, b in enumerate(jobs):
        if not isinstance(b, dict):
            e.append(f"job #{i} is not an object")
            continue
        bid = b.get("id")
        if not isinstance(bid, str) or not ID.match(bid):
            e.append(f"job #{i}: id {bid!r} must be 1-16 letters/digits/._-")
            continue
        ids.append(bid)
        k = kind(b)
        if k not in KINDS:
            e.append(f"job {bid}: kind {k!r} not one of {KINDS}")
            continue
        if not is_str(b.get("title")):
            e.append(f"job {bid}: title is empty")
        st = stored(b)
        if st not in STORED[k]:
            e.append(f"job {bid}: state {b.get('state')!r} not valid for kind {k} {STORED[k]}")
        needs = b.get("needs", [])
        if not isinstance(needs, list) or not all(isinstance(n, str) for n in needs):
            e.append(f"job {bid}: needs must be a list of job ids")
        notes = b.get("notes", [])
        if not isinstance(notes, list) or not all(isinstance(n, str) for n in notes):
            e.append(f"job {bid}: notes must be a list of strings")
        figs = b.get("figures", [])
        if not isinstance(figs, list) or len(figs) > 6 or not all(
                isinstance(x, dict) and is_str(x.get("n")) and is_str(x.get("label")) and x.get("tone", "") in ("", "good", "warn") for x in figs):
            e.append(f"job {bid}: figures must be a list of at most 6 {{n, label, tone: good|warn|''}}")
        if "lesson" in b and b["lesson"] is not None and not isinstance(b["lesson"], str):
            e.append(f"job {bid}: lesson must be a string")
        twigs = b.get("twigs", [])
        if not isinstance(twigs, list) or not all(isinstance(n, str) for n in twigs) or len(twigs) > 3:
            e.append(f"job {bid}: twigs must be a list of at most 3 strings")
        for f in ("summary", "ticket", "key", "run", "pr", "merge", "decision", "resolution"):
            if f in b and b[f] is not None and not isinstance(b[f], str):
                e.append(f"job {bid}: {f} must be a string")
        if st == "merged":
            if not is_str(b.get("pr")):
                e.append(f"job {bid}: merged but no pr recorded")
            if not isinstance(b.get("merge"), str) or not SHA.match(b["merge"]):
                e.append(f"job {bid}: merged but merge {b.get('merge')!r} is not a 7-40 char hex sha")
            if not is_str(b.get("run")):
                e.append(f"job {bid}: merged but no run recorded")
        if st == "decision" and not is_str(b.get("decision")):
            e.append(f"job {bid}: state 'decision' but no 'decision' text (what must be decided, by whom)")
        if st == "resolved" and not is_str(b.get("resolution")):
            e.append(f"job {bid}: resolved but no 'resolution' (the owner's decision, quoted)")
        if st == "in-progress" and not is_str(b.get("run")):
            e.append(f"job {bid}: in-progress but no run recorded")
    if len(ids) != len(set(ids)):
        e.append("duplicate job ids")
    if e:
        raise SpineError(e)
    known = set(ids)
    for b in jobs:
        for n in b.get("needs", []):
            if n not in known:
                e.append(f"job {b['id']}: needs unknown job {n!r}")
            if n == b["id"]:
                e.append(f"job {b['id']}: needs itself")
    sup = board.get("superseded", [])
    if not isinstance(sup, list):
        e.append("superseded must be a list")
    else:
        for k, x in enumerate(sup):
            if not (isinstance(x, dict) and isinstance(x.get("id"), str) and isinstance(x.get("by"), list)
                    and all(isinstance(y, str) for y in x["by"])):
                e.append(f"superseded[{k}] must be an object with an id and a list 'by' of job ids")
            else:
                gone = known | {y.get("id") for y in sup if isinstance(y, dict)}
                for y in x["by"]:
                    if y not in gone:
                        e.append(f"superseded[{k}] ({x['id']}): by names unknown job {y!r}")
    log = board.get("log", [])
    if not isinstance(log, list) or not all(isinstance(x, str) for x in log):
        e.append("log must be a list of strings")
    pub = board.get("publish", {})
    if isinstance(pub, dict) and "standalone" in pub and not isinstance(pub["standalone"], bool):
        e.append("publish.standalone must be true or false")
    if e:
        raise SpineError(e)
    graph = {b["id"]: b.get("needs", []) for b in jobs}
    mark = {}

    def visit(n, path):
        if mark.get(n) == 1:
            e.append("dependency cycle: " + " -> ".join(path + [n]))
            return
        if mark.get(n) == 2:
            return
        mark[n] = 1
        for m in graph[n]:
            visit(m, path + [n])
        mark[n] = 2

    for n in graph:
        visit(n, [])
    by_id = {b["id"]: b for b in jobs}
    for b in jobs:
        if stored(b) in ("in-progress", "merged", "resolved"):
            for n in b.get("needs", []):
                if stored(by_id[n]) not in DONE:
                    e.append(f"job {b['id']}: is {b['state']} but its need {n} is not merged/resolved")
    in_j = [b["id"] for b in jobs if stored(b) == "in-progress"]
    if len(in_j) > 1:
        e.append(f"more than one job in progress: {in_j} (one at a time)")
    if nxt is not None:
        if nxt not in known:
            e.append(f"next {nxt!r} is not a job")
        else:
            s = shown_state(by_id[nxt], by_id)
            if s not in ("ready", "in-progress"):
                cands = sorted(b["id"] for b in eligible(board))
                e.append(f"next {nxt!r} is {s}; it must be ready or in-progress. eligible: {cands or 'none'}")
    if in_j and nxt != in_j[0]:
        e.append(f"job {in_j[0]} is in progress but next is {nxt!r}; next must be the job being built")
    if e:
        raise SpineError(e)
    sf = (board.get("project") or {}).get("standfirst") or ""
    for m in re.finditer(r"next\W{0,12}job\s+([A-Za-z0-9._-]+)", sf, re.I):
        said = m.group(1).rstrip(".")
        if said in by_id and stored(by_id[said]) == "merged":
            WARNINGS.append(f"the standfirst still names job {said} as next, but it is merged; update it with --standfirst")


# ---------------------------------------------------------------- argument parsing

def parse(args, allowed_values, allowed_flags=()):
    """Return (positional, values, flags). Unknown options are usage errors."""
    pos, vals, flags = [], {}, set()
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("--"):
            if a in allowed_flags:
                flags.add(a)
                i += 1
                continue
            if a not in allowed_values:
                raise Usage(f"unknown option {a}")
            if i + 1 >= len(args) or args[i + 1].startswith("--"):
                raise Usage(f"{a} needs a value")
            vals[a] = args[i + 1]
            i += 2
        else:
            pos.append(a)
            i += 1
    return pos, vals, flags


def one_job(pos, cmd):
    if len(pos) != 1:
        raise Usage(f"{cmd} takes exactly one job id, got {pos}")
    return pos[0]


def need(vals, name):
    if name not in vals:
        raise Usage(f"{name} is required")
    return vals[name]


# ---------------------------------------------------------------- events

def job(board, bid):
    for b in board["jobs"]:
        if b["id"] == bid:
            return b
    raise Usage(f"no job {bid!r}")


def bump(board, standfirst=None):
    board["version"] += 1
    board["updated"] = datetime.date.today().isoformat()
    if standfirst:
        board["project"]["standfirst"] = standfirst


def after_close(board, bid):
    s = copy.deepcopy(board)
    b = job(s, bid)
    b["state"] = "merged"
    return [x["id"] for x in eligible(s)]


def ev_start(board, args):
    pos, vals, _ = parse(args, ("--run", "--standfirst"))
    bid = one_job(pos, "start")
    b = job(board, bid)
    by_id = {x["id"]: x for x in board["jobs"]}
    busy = [x["id"] for x in board["jobs"] if stored(x) == "in-progress"]
    if busy:
        raise Usage(f"job {busy[0]} is already in progress; close or halt it first (one at a time)")
    if kind(b) != "build":
        raise Usage(f"job {bid} is a decision job; it is resolved with 'decided', not built")
    if shown_state(b, by_id) != "ready":
        raise Usage(f"job {bid} is {shown_state(b, by_id)}; only a ready job can start")
    b["state"], b["run"] = "in-progress", need(vals, "--run")
    board["next"] = bid
    bump(board, vals.get("--standfirst"))


def ev_close(board, args):
    pos, vals, flags = parse(args, ("--pr", "--merge", "--run", "--next", "--reason", "--note", "--standfirst"), ("--no-next",))
    bid = one_job(pos, "close")
    b = job(board, bid)
    if stored(b) != "in-progress":
        raise Usage(f"job {bid} is {b['state']}; close expects the job in progress")
    j = vals.get("--run")
    if j is not None and j != b.get("run"):
        raise Usage(f"--run {j} does not match the recorded run {b.get('run')}")
    merge = need(vals, "--merge")
    if not SHA.match(merge):
        raise Usage(f"--merge {merge!r} is not a 7-40 char hex sha")
    cands = after_close(board, bid)
    nxt = vals.get("--next")
    if nxt and "--no-next" in flags:
        raise Usage("use --next or --no-next, not both")
    if nxt is None:
        if cands and "--no-next" not in flags:
            raise Usage(f"jobs {cands} become eligible; choose one with --next, or --no-next --reason \"...\"")
        if "--no-next" in flags and not vals.get("--reason"):
            raise Usage("--no-next needs --reason")
    elif nxt not in cands:
        raise Usage(f"--next {nxt} is not eligible after this close; eligible: {cands or 'none'}")
    b.update(state="merged", pr=need(vals, "--pr"), merge=merge)
    if vals.get("--note"):
        b.setdefault("notes", []).append(vals["--note"])
    board["next"] = nxt
    if nxt is None and vals.get("--reason"):
        board.setdefault("log", []).append(f"v{board['version'] + 1}: no next chosen: {vals['--reason']}")
    if not vals.get("--standfirst"):
        WARNINGS.append(f"standfirst unchanged: {board['project'].get('standfirst', '')!r}; pass --standfirst if it no longer says where the project stands")
    bump(board, vals.get("--standfirst"))


def ev_halt(board, args):
    pos, vals, _ = parse(args, ("--reason", "--to", "--decision", "--standfirst"))
    bid = one_job(pos, "halt")
    b = job(board, bid)
    if stored(b) != "in-progress":
        raise Usage(f"job {bid} is {b['state']}; halt expects the job in progress")
    to = need(vals, "--to")
    if to not in ("open", "decision"):
        raise Usage("--to must be open or decision")
    b.setdefault("notes", []).append(f"HALTED in {b.get('run')}: {need(vals, '--reason')}")
    b["state"] = to
    if to == "decision":
        b["decision"] = need(vals, "--decision")
    board["next"] = None
    bump(board, vals.get("--standfirst"))


def ev_decided(board, args):
    pos, vals, _ = parse(args, ("--note", "--standfirst"))
    bid = one_job(pos, "decided")
    b = job(board, bid)
    if stored(b) != "decision":
        raise Usage(f"job {bid} is {b['state']}, not waiting on a decision")
    note = need(vals, "--note")
    if kind(b) == "decision":
        by_id = {x["id"]: x for x in board["jobs"]}
        unmet = [n for n in b.get("needs", []) if stored(by_id[n]) not in DONE]
        if unmet:
            raise Usage(f"decision job {bid} needs {unmet} first (merged or resolved); deciding without them is a re-plan: change its needs and record why")
        b["state"], b["resolution"] = "resolved", note
    else:
        b["state"] = "open"
        b.setdefault("notes", []).append(f"Decided: {note}")
        b.pop("decision", None)
    bump(board, vals.get("--standfirst"))


def ev_add(board, args):
    pos, vals, flags = parse(args, ("--title", "--needs", "--decision", "--summary", "--standfirst", "--pr", "--merge", "--run"), ("--merged",))
    bid = one_job(pos, "add")
    if not ID.match(bid):
        raise Usage(f"job id {bid!r} must be 1-16 letters/digits/._-")
    if any(b["id"] == bid for b in board["jobs"]):
        raise Usage(f"job {bid} already exists")
    if any(x.get("id") == bid for x in board.get("superseded", [])):
        raise Usage(f"job id {bid} belonged to a split job; ids are never reused")
    needs = [n for n in vals.get("--needs", "").split(",") if n]
    dec = vals.get("--decision")
    nb = {"id": bid, "title": need(vals, "--title"), "kind": "decision" if dec else "build",
          "state": "decision" if dec else "open", "needs": needs, "notes": []}
    if dec:
        nb["decision"] = dec
    if vals.get("--summary"):
        nb["summary"] = vals["--summary"]
    backfill = [o for o in ("--pr", "--merge", "--run") if o in vals]
    if "--merged" in flags:
        # backfill: a job merged before the board existed (its PR, merge commit and run, from the records)
        if dec:
            raise Usage("--merged is for a build job; a decided job is added with --decision, then 'decided'")
        merge = need(vals, "--merge")
        if not SHA.match(merge):
            raise Usage(f"--merge {merge!r} is not a 7-40 char hex sha")
        nb.update(state="merged", pr=need(vals, "--pr"), merge=merge, run=need(vals, "--run"))
    elif backfill:
        raise Usage(f"{', '.join(backfill)} only with --merged (backfilling a merged job)")
    board["jobs"].append(nb)
    bump(board, vals.get("--standfirst"))


def child_id(bid, suf):
    """A child id from a bare suffix ("a") or the full id ("02a"); never the parent's id twice ("0202a")."""
    suf = suf.strip()
    cid = suf if suf.startswith(bid) and len(suf) > len(bid) else bid + suf
    if cid.startswith(bid + bid):
        raise Usage(f"child id {cid!r} repeats the parent id {bid!r}: give a bare suffix (a) or the full id ({bid}a)")
    return cid


def ev_split(board, args):
    pos, vals, flags = parse(args, ("--into", "--active", "--standfirst"), ("--chain",))
    bid = one_job(pos, "split")
    b = job(board, bid)
    st = stored(b)
    if kind(b) != "build" or st not in ("open", "in-progress"):
        raise Usage(f"only an open or in-progress build job can be split; {bid} is {kind(b)}/{st}")
    parts = []
    for item in need(vals, "--into").split(","):
        if "=" not in item:
            raise Usage(f"--into items are suffix=Title, got {item!r}")
        suf, title = item.split("=", 1)
        cid = child_id(bid, suf)
        if not ID.match(cid) or any(x["id"] == cid for x in board["jobs"]):
            raise Usage(f"child id {cid!r} is invalid or exists")
        parts.append((cid, title.strip()))
    if len(parts) < 2:
        raise Usage("--into needs at least two children")
    active = vals.get("--active")
    if active:
        active = child_id(bid, active)[len(bid):]
    if st == "in-progress":
        if not active or bid + active not in [p[0] for p in parts]:
            raise Usage("splitting the job in progress needs --active <suffix> naming the child the run continues on")
    elif active:
        raise Usage("--active only applies when splitting the job in progress")
    idx = board["jobs"].index(b)
    children = []
    for k, (cid, title) in enumerate(parts):
        needs = list(b.get("needs", []))
        if "--chain" in flags and k > 0:
            needs = [parts[k - 1][0]]
        c = {"id": cid, "title": title, "kind": "build", "state": "open", "needs": needs,
             "notes": [f"split from {bid}"]}
        if st == "in-progress" and cid == bid + active:
            c["state"], c["run"] = "in-progress", b["run"]
        children.append(c)
    tail = [children[-1]["id"]] if "--chain" in flags else [c["id"] for c in children]
    for x in board["jobs"]:
        if bid in x.get("needs", []):
            x["needs"] = [n for n in x["needs"] if n != bid] + [t for t in tail if t not in x["needs"]]
    board["jobs"][idx:idx + 1] = children
    board.setdefault("superseded", []).append({"id": bid, "title": b["title"], "by": [c["id"] for c in children],
                                               "at_version": board["version"] + 1})
    if board.get("next") == bid:
        board["next"] = bid + active if active else None
    bump(board, vals.get("--standfirst"))


def ev_covered(board, args):
    """An open build job made redundant by another job: it leaves the board, on the owner's quoted word."""
    pos, vals, _ = parse(args, ("--by", "--quote", "--standfirst"))
    bid = one_job(pos, "covered")
    b = job(board, bid)
    if kind(b) != "build" or stored(b) != "open":
        raise Usage(f"only an open build job can be marked covered; {bid} is {kind(b)}/{stored(b)}")
    by = need(vals, "--by")
    if by == bid:
        raise Usage("a job can't be covered by itself")
    job(board, by)
    quote = need(vals, "--quote")
    for x in board["jobs"]:
        if bid in x.get("needs", []):
            x["needs"] = [n for n in x["needs"] if n != bid] + ([by] if by not in x["needs"] and by != x["id"] else [])
    board["jobs"].remove(b)
    board.setdefault("superseded", []).append({"id": bid, "title": b["title"], "by": [by],
                                               "at_version": board["version"] + 1, "reason": f"covered by {by}: {quote}"})
    if board.get("next") == bid:
        board["next"] = None
    bump(board, vals.get("--standfirst"))


def ev_topout(board, args):
    """The board's head is reached: freeze it. Jobs not merged or resolved are carried over to the next head."""
    pos, vals, _ = parse(args, ("--report", "--quote", "--head", "--standfirst"))
    if pos:
        raise Usage(f"unexpected arguments {pos}")
    report = need(vals, "--report")
    by_id = {b["id"]: b for b in board["jobs"]}
    busy = [b["id"] for b in board["jobs"] if stored(b) == "in-progress"]
    if busy:
        raise Usage(f"job {busy[0]} is in progress; close it first if it merged (close {busy[0]} --pr ... --merge <sha>, with --no-next --reason \"topping out\" when jobs are still ready), or halt it if it did not")
    carried = [b["id"] for b in board["jobs"] if stored(b) not in DONE]
    if carried and not vals.get("--quote"):
        raise Usage(f"jobs {carried} are not merged or resolved (ready, blocked or waiting on a decision); topping out with them carried over is the owner's call: pass the owner's own words with --quote (never a goal's)")
    merged = sum(1 for b in board["jobs"] if stored(b) in DONE)
    today = datetime.date.today().isoformat()
    head = vals.get("--head", "yes" if not carried else None)
    if head not in ("yes", "partly", "no"):
        raise Usage("--head must be yes, partly or no (whether the head's test passes); it is required when jobs are carried over")
    board["topped_out"] = {"date": today, "version": board["version"] + 1, "report": report, "carried": carried, "head_reached": head}
    if vals.get("--quote"):
        board["topped_out"]["owner"] = vals["--quote"]
    board["next"] = None
    jobs_done = f"{merged} job{'' if merged == 1 else 's'} done"
    board.setdefault("log", []).append(f"v{board['version'] + 1}: topped out ({jobs_done}, {len(carried)} carried over: {', '.join(carried) or 'none'}); report {report}")
    bump(board, vals.get("--standfirst") or f"Topped out on {today}: {jobs_done}, {len(carried)} carried over to the next head.")


def ev_set_next(board, args):
    pos, vals, _ = parse(args, ("--standfirst",))
    board["next"] = one_job(pos, "set-next")
    bump(board, vals.get("--standfirst"))


EVENTS = {"start": ev_start, "close": ev_close, "halt": ev_halt, "decided": ev_decided,
          "add": ev_add, "split": ev_split, "covered": ev_covered, "set-next": ev_set_next, "topout": ev_topout}


# ---------------------------------------------------------------- render

def esc(s):
    return html.escape(str(s), quote=True)


def wrap(text, width=20, lines=2):
    out, cur = [], ""
    for w in str(text).split():
        while len(w) > width:
            if cur:
                out.append(cur)
                cur = ""
            out.append(w[:width - 1] + "-")
            w = w[width - 1:]
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= width:
            cur += " " + w
        else:
            out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    if len(out) > lines:
        out = out[:lines]
        out[-1] = out[-1][: width - 1].rstrip("-") + "…"
    return out or [""]


RANK = {"in-progress": 0, "ready": 1, "decision": 2, "blocked": 3, "merged": 4, "resolved": 4}


def one_line(text, width):
    t = " ".join(str(text).split())
    return t if len(t) <= width else t[: width - 1].rstrip() + "…"


def fishbone(board, by_id):
    """The spine runs left to right into the head; ribs alternate above and below."""
    jobs, nxt = board["jobs"], board.get("next")
    SPINE, GAP, X0, RISE, RUN = 380, 140, 150, 250, 130
    n = len(jobs)
    slot = 0 if (nxt or board.get("topped_out")) else 1   # a dashed "next: not chosen" slot when nothing is next (never on a topped-out board)
    last_x = X0 + (n - 1 + slot) * GAP + GAP / 2
    head_x = last_x + 230
    W, H = int(head_x + 430), 760
    p = [f'<svg class="fish" id="fish" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet" role="img" '
         f'aria-label="Fishbone: {n} jobs feeding {esc(board["project"]["head"]["outcome"])}">',
         f'<line class="spine" x1="40" y1="{SPINE}" x2="{head_x:.0f}" y2="{SPINE}"/>']
    for i, b in enumerate(jobs):
        up = i % 2 == 0
        d = -1 if up else 1
        bx = X0 + i * GAP + (0 if up else GAP / 2)
        tx, ty = bx - RUN, SPINE + d * RISE
        st = shown_state(b, by_id)
        cls = st + (" next" if b["id"] == nxt else "")
        p.append(f'<g class="rib {cls}" data-i="{i}" tabindex="0" role="button" aria-label="{esc(b["id"])} {esc(b["title"])}, {esc(LABEL[st])}">')
        p.append(f'<line class="tick" x1="{bx:.0f}" y1="{SPINE - 7}" x2="{bx:.0f}" y2="{SPINE + 7}"/>')
        p.append(f'<path class="ribl" d="M{bx:.0f},{SPINE} L{tx:.0f},{ty}"/>')
        for k, tw in enumerate(b.get("twigs", [])[:3]):
            f = (k + 1) / 4
            px, py = bx - RUN * f, SPINE + d * RISE * f
            p.append(f'<line class="twl" x1="{px:.0f}" y1="{py:.0f}" x2="{px + 16:.0f}" y2="{py:.0f}"/>')
            p.append(f'<text class="twt" x="{px + 20:.0f}" y="{py + 4:.0f}">{esc(one_line(tw, 44))}</text>')
        cy = ty - 40 if up else ty + 18
        cw = max(36, 9 * len(b["id"]) + 14)
        p.append(f'<rect class="chip" x="{tx - cw / 2:.0f}" y="{cy}" width="{cw}" height="18"/>')
        p.append(f'<text class="chipt" x="{tx:.0f}" y="{cy + 13}" text-anchor="middle">{esc(b["id"])}</text>')
        p.append(f'<text class="ribname" x="{tx + cw / 2 + 8:.0f}" y="{cy + 14}"><title>{esc(b["title"])}</title>{esc(one_line(b["title"], 30))}</text>')
        sub = " · ".join(x for x in (b.get("key"), b.get("pr") and f'PR {b["pr"]}', LABEL[st] if st not in DONE else None) if x)
        if sub:
            p.append(f'<text class="ribkey" x="{tx + cw / 2 + 8:.0f}" y="{cy + (-6 if up else 32)}">{esc(one_line(sub, 40))}</text>')
        p.append("</g>")
    if slot:
        i = n
        up = i % 2 == 0
        bx = X0 + i * GAP + (0 if up else GAP / 2)
        tx, ty = bx - RUN, SPINE + (-1 if up else 1) * RISE
        p.append(f'<path class="nextl" d="M{bx:.0f},{SPINE} L{tx:.0f},{ty}"/>')
        p.append(f'<text class="nextt" x="{tx - 30:.0f}" y="{ty - 26 if up else ty + 30}">next · not chosen</text>')
    hl = wrap(board["project"]["head"]["outcome"], width=22, lines=3)
    box_h = 70 + 30 * len(hl)
    top = SPINE - box_h / 2
    p.append(f'<rect class="headbox" x="{head_x + 14:.0f}" y="{top:.0f}" width="380" height="{box_h:.0f}"/>')
    p.append(f'<rect class="headstripe" x="{head_x + 14:.0f}" y="{top:.0f}" width="10" height="{box_h:.0f}"/>')
    p.append(f'<text class="heads" x="{head_x + 40:.0f}" y="{top + 30:.0f}">THE HEAD</text>')
    for k, ln in enumerate(hl):
        p.append(f'<text class="headt" x="{head_x + 40:.0f}" y="{top + 62 + 30 * k:.0f}">{esc(ln)}</text>')
    test = board["project"]["head"].get("test")
    if test:
        for k, ln in enumerate(wrap("Judged by: " + test, width=48, lines=3)):
            p.append(f'<text class="headn" x="{head_x + 14:.0f}" y="{top + box_h + 26 + 18 * k:.0f}">{esc(ln)}</text>')
    p.append("</svg>")
    return "\n".join(p)


def fig_html(x):
    return f'<div class="fig {esc(x.get("tone", ""))}"><b>{esc(x["n"])}</b><span>{esc(x["label"])}</span></div>'


def job_detail(b, by_id):
    """The Job pane for one job, complete without script (the script rebuilds it on selection)."""
    st = shown_state(b, by_id)
    needs = b.get("needs") or []
    need_html = " ".join(f'<span class="{"ok" if shown_state(by_id[n], by_id) in DONE else "no"}">{esc(n)} {"✓" if shown_state(by_id[n], by_id) in DONE else "✗"}</span>'
                         for n in needs if n in by_id)
    cells = [(k, esc(v)) for k, v in (("Key", b.get("key")), ("Ticket", b.get("ticket")), ("Run", b.get("run"))) if v]
    if need_html:
        cells.append(("Needs", need_html))
    cells += [(k, esc(v)) for k, v in (("PR", b.get("pr")), ("Merge", b.get("merge"))) if v]
    spec = "".join(f'<div><dt>{k}</dt><dd>{v}</dd></div>' for k, v in cells)
    notes = b.get("notes", [])
    extra = []
    if st == "decision" and b.get("decision"):
        extra.append(f'<p class="flag dec"><b>To decide:</b> {esc(b["decision"])}</p>')
    if st == "resolved" and b.get("resolution"):
        extra.append(f'<p class="flag ok"><b>Decided:</b> {esc(b["resolution"])}</p>')
    flags = extra + [f'<p class="flag">{esc(x)}</p>' for x in notes]
    return (f'<div class="jobp" id="jobp" data-state="{st}"><div class="jobmain">'
            f'<div class="jobhead"><span class="jn" id="jn">{esc(b["id"])}</span><h2 class="jt" id="jt">{esc(b["title"])}</h2>'
            f'<span class="pill {st}" id="jp">{esc(LABEL[st])}</span></div>'
            f'<dl class="spec" id="jspec">{spec}</dl>'
            f'<p class="jbody" id="jb">{esc(b.get("summary") or "")}</p>'
            f'<div class="figs" id="jfigs">{"".join(fig_html(x) for x in b.get("figures", []))}</div>'
            f'<p class="jlesson" id="jl"{"" if b.get("lesson") else " hidden"}><b>Lesson</b> {esc(b.get("lesson") or "")}</p></div>'
            f'<div class="jside"><div class="lbl">Notes and flags · <span id="jcount">{len(flags) or "none"}</span></div>'
            f'<div id="jf" class="flags">{"".join(flags) or "<p class=\"flag none\">Nothing recorded against this job.</p>"}</div>'
            f'</div></div>')


def open_rows(jobs, by_id, nxt):
    rows = [b for b in jobs if shown_state(b, by_id) not in DONE]
    rows.sort(key=lambda b: (0 if b["id"] == nxt else 1, RANK[shown_state(b, by_id)]))
    out = []
    for b in rows:
        st = shown_state(b, by_id)
        needs = b.get("needs") or []
        nd = " ".join(f'<span class="{"ok" if shown_state(by_id[n], by_id) in DONE else "no"}">{esc(n)} {"✓" if shown_state(by_id[n], by_id) in DONE else "✗"}</span>' for n in needs if n in by_id)
        body = esc(b.get("summary") or "")
        if st == "decision" and b.get("decision"):
            body += f' <b>To decide:</b> {esc(b["decision"])}'
        out.append(f'<div class="cr {st}{" isnext" if b["id"] == nxt else ""}" data-job="{esc(b["id"])}" role="button" tabindex="0" title="Open board {esc(b["id"])}{(" · " + esc(b["run"])) if b.get("run") else ""}"><div><span class="ck">{esc(b["id"])}</span>'
                   f'<span class="cn">{esc(b["title"])}</span></div><div class="cb">{nd or "-"}</div>'
                   f'<div class="cnote">{body}</div><span class="pill {st}">{"next · " if b["id"] == nxt else ""}{esc(LABEL[st])}</span></div>')
    return "".join(out) or '<p class="lead">Every job is merged or decided.</p>'


CSS = r"""
:root{color-scheme:light;
 --ground:#ECEEEA;--panel:#F8F9F6;--panel-2:#E2E6E0;--line:#C9CFC7;--line-2:#DADFD8;
 --ink:#15181A;--ink-2:#454C50;--ink-3:#727A7E;--hivis:#FBB401;--hivis-ink:#101316;
 --merged:#2F6B3A;--run:#1D4E89;--ready:#454C50;--blocked:#8A8F8C;--decision:#A5650F;--rib:#454C50;--focus:#1D4E89}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
 --ground:#101315;--panel:#171B1E;--panel-2:#1F2427;--line:#2C3337;--line-2:#23292C;
 --ink:#E7EAE5;--ink-2:#B4BBB6;--ink-3:#808983;
 --merged:#8FCB7C;--run:#80AFE9;--ready:#C9D0CB;--blocked:#7A837E;--decision:#F0B04A;--rib:#9AA29D;--focus:#80AFE9}}
:root[data-theme="dark"]{color-scheme:dark;
 --ground:#101315;--panel:#171B1E;--panel-2:#1F2427;--line:#2C3337;--line-2:#23292C;
 --ink:#E7EAE5;--ink-2:#B4BBB6;--ink-3:#808983;
 --merged:#8FCB7C;--run:#80AFE9;--ready:#C9D0CB;--blocked:#7A837E;--decision:#F0B04A;--rib:#9AA29D;--focus:#80AFE9}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--ground);color:var(--ink);font:400 15px/1.55 "Public Sans",system-ui,-apple-system,"Segoe UI",sans-serif;padding-inline:16px;overflow:hidden}
:focus-visible{outline:2px solid var(--focus);outline-offset:3px}
.wrap{max-width:1400px;height:100%;margin:0 auto;display:grid;grid-template-rows:auto minmax(210px,40%) minmax(0,1fr);gap:10px;padding-block:12px}
.lbl{font:600 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3)}
.bar{display:flex;flex-direction:column;gap:2px}
.kick{font:500 11px/1.5 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);display:flex;align-items:center;gap:9px}
.theme-toggle{margin-left:auto;font:600 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;padding:7px 11px;border:1px solid var(--line);border-radius:0;background:var(--panel);color:var(--ink);cursor:pointer}
.theme-toggle:hover{border-color:var(--ink)}
.theme-toggle:focus-visible{outline:2px solid var(--hivis);outline-offset:2px}
.mark{width:30px;height:30px;flex:none;display:inline-block;vertical-align:middle;filter:drop-shadow(1.5px 0 0 #ECEEEA) drop-shadow(-1.5px 0 0 #ECEEEA) drop-shadow(0 1.5px 0 #ECEEEA) drop-shadow(0 -1.5px 0 #ECEEEA)}
.barrow{display:flex;flex-wrap:wrap;gap:10px 28px;align-items:flex-end;justify-content:space-between}
h1{margin:0;font:800 clamp(30px,3.6vw,46px)/.95 "Big Shoulders Display","Arial Narrow",Impact,sans-serif;text-transform:uppercase;text-wrap:balance}
.hright{display:flex;align-items:flex-end;gap:18px;flex:0 0 auto}
.gauge{display:flex;flex-direction:column;gap:6px;width:260px;max-width:100%}
.gnum{display:flex;align-items:baseline;gap:6px}
.gnum b{font:800 44px/.8 "Big Shoulders Display","Arial Narrow",sans-serif;font-variant-numeric:tabular-nums}
.gnum span{font:600 11px "Martian Mono",ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3)}
.gbar{display:flex;gap:2px;height:9px}
.gbar i{flex:1;background:var(--c,var(--line))}
.gbar .merged,.gbar .resolved{--c:var(--merged)}.gbar .in-progress{--c:var(--run)}.gbar .decision{--c:var(--decision)}.gbar .blocked{background:repeating-linear-gradient(-45deg,var(--ink-3) 0 2px,transparent 2px 4px)}.gbar .isnext{--c:var(--hivis)}
.status{display:flex;align-items:center;gap:0;white-space:nowrap}
.status span{font:500 12.5px "Public Sans",system-ui,sans-serif;color:var(--ink-2);padding:3px 12px;border-left:1px solid var(--line)}
.status span:first-child{border-left:0;padding-left:0}
.status b{font:700 13px "Martian Mono",ui-monospace,monospace;color:var(--ink);font-variant-numeric:tabular-nums}
.status .nx{background:var(--hivis);border-left:0;margin-left:8px;padding:6px 11px;color:var(--hivis-ink)}.status .nx b{color:var(--hivis-ink)}
.fishwrap{background:var(--panel);border:1px solid var(--line);display:grid;grid-template-rows:auto minmax(0,1fr) auto;min-height:0}
.fishbar{display:flex;flex-wrap:wrap;gap:6px 18px;align-items:center;justify-content:space-between;padding:7px 14px;border-bottom:1px solid var(--line-2)}
.leg{display:flex;flex-wrap:wrap;gap:6px 16px;font:500 11.5px "Martian Mono",ui-monospace,monospace;color:var(--ink-2)}
.leg i{display:inline-block;width:22px;height:0;border-top:2.5px solid var(--c,var(--rib));vertical-align:middle;margin-right:6px}
.leg .l-run i{--c:var(--run)}.leg .l-ready i{border-top-style:dashed}.leg .l-blocked i{--c:var(--blocked);border-top-style:dotted}.leg .l-decision i{--c:var(--decision);border-top-style:dashed}.leg .l-next i{--c:var(--hivis);border-top-width:4px}
.scroll{min-height:0;overflow:hidden;position:relative;background-image:radial-gradient(var(--line) 1px,transparent 1.3px);background-size:22px 22px;background-position:11px 11px}
svg.fish{display:block;width:100%;height:100%}
.spine{stroke:var(--line);stroke-width:5;stroke-linecap:round}
.spine.built{stroke:var(--ink);stroke-width:6}
.builtdot{fill:var(--ground);stroke:var(--ink);stroke-width:3}
.tick{stroke:var(--ink);stroke-width:2}
.ribl{stroke:var(--rib);stroke-width:2.2;fill:none;transition:stroke .15s}
.rib.in-progress .ribl{stroke:var(--run);stroke-width:3.2}
.rib.ready .ribl{stroke-dasharray:7 5}
.rib.blocked .ribl{stroke:var(--blocked);stroke-dasharray:2 5}
.rib.decision .ribl{stroke:var(--decision);stroke-dasharray:9 5}
.rib.next .ribl{stroke:var(--hivis);stroke-width:4}
.twl{stroke:var(--line);stroke-width:1.4}
.twt{font:600 13px "Public Sans",system-ui,sans-serif;fill:var(--ink);opacity:0;paint-order:stroke;stroke:var(--panel);stroke-width:5px;stroke-linejoin:round;transition:opacity .15s;pointer-events:none}
.twbg{fill:var(--panel);opacity:0;transition:opacity .15s;pointer-events:none}
.rib.on .twt,.rib:hover .twt,.rib.on .twbg,.rib:hover .twbg{opacity:1}
.rib.on .twl,.rib:hover .twl{stroke:var(--ink-2)}
.fsel{font:600 12px "Martian Mono",ui-monospace,monospace;background:var(--ink);color:var(--ground);padding:4px 9px;max-width:60%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.chip{fill:var(--panel);stroke:var(--rib);stroke-width:1.2}.chipt{font:600 11px "Martian Mono",ui-monospace,monospace;fill:var(--ink-2);letter-spacing:.04em}
.rib.in-progress .chip{fill:var(--run);stroke:var(--run)}.rib.in-progress .chipt{fill:var(--ground)}
.rib.decision .chip{fill:var(--decision);stroke:var(--decision)}.rib.decision .chipt{fill:var(--ground)}
.rib.blocked .chip{stroke-dasharray:2 2}
.rib.next .chip{fill:var(--hivis);stroke:var(--hivis)}.rib.next .chipt{fill:var(--hivis-ink)}
.rib:hover .chip{stroke:var(--ink)}
.rib.on .chip{fill:var(--ink);stroke:var(--ink)}.rib.on .chipt{fill:var(--ground)}
.ribname{font:700 15px "Public Sans",system-ui,sans-serif;fill:var(--ink);paint-order:stroke;stroke:var(--panel);stroke-width:5px;stroke-linejoin:round;opacity:0;pointer-events:none}
.rib.on .ribname,.rib:hover .ribname{opacity:1}
.ribkey{font:500 10.5px "Martian Mono",ui-monospace,monospace;fill:var(--ink-3);opacity:0;paint-order:stroke;stroke:var(--panel);stroke-width:4px}
.rib.on .ribkey{opacity:1}
.rib{cursor:pointer}.rib:focus{outline:none}
.rib:hover .ribl,.rib.on .ribl{stroke-width:3.4}
.rib.on .ribl{stroke:var(--ink)}.rib.on.next .ribl{stroke:var(--hivis)}
.rib:focus-visible .chip{stroke:var(--focus);stroke-width:3}
.nextl{stroke:var(--hivis);stroke-width:2.6;stroke-dasharray:8 6;fill:none}
.nextt{font:700 13px "Public Sans",system-ui,sans-serif;fill:var(--ink);paint-order:stroke;stroke:var(--panel);stroke-width:6px;stroke-linejoin:round}
.headbox{fill:var(--hivis)}.headstripe{fill:url(#hz)}.hzA{fill:var(--hivis)}.hzB{fill:var(--hivis-ink)}
.heads{font:600 10.5px "Martian Mono",ui-monospace,monospace;fill:var(--hivis-ink);letter-spacing:.14em;opacity:.75}
.headt{font:800 21px "Big Shoulders Display","Arial Narrow",sans-serif;fill:var(--hivis-ink);text-transform:uppercase}
.spinehead{fill:var(--ink)}
.headn{font:500 11px "Martian Mono",ui-monospace,monospace;fill:var(--ink-3)}
.chips{display:grid;grid-template-columns:repeat(auto-fit,minmax(34px,1fr));max-width:calc(var(--n,24) * 72px + 28px);gap:2px;padding:8px 14px 10px;border-top:1px solid var(--line-2)}
.jc{font:600 11px/1 "Martian Mono",ui-monospace,monospace;padding:7px 0 6px;border:0;border-bottom:4px solid var(--c,var(--line));background:var(--panel-2);color:var(--ink-2);cursor:pointer;text-align:center}
.jc:hover{color:var(--ink);background:var(--line-2)}
.jc.in-progress{--c:var(--run)}.jc.decision{--c:var(--decision)}.jc.blocked{--c:var(--blocked)}.jc.merged,.jc.resolved{--c:var(--merged)}.jc.isnext{--c:var(--hivis)}
.jc[aria-pressed="true"]{background:var(--ink);color:var(--ground)}
.panel{background:var(--panel);border:1px solid var(--line);display:grid;grid-template-rows:auto minmax(0,1fr);min-height:0}
.tabs{display:flex;overflow-x:auto;border-bottom:1px solid var(--line);background:var(--panel)}
.tab{font:800 18px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;letter-spacing:.02em;background:none;border:0;border-bottom:4px solid transparent;color:var(--ink-3);padding:10px 16px 7px;cursor:pointer;white-space:nowrap;display:flex;gap:8px;align-items:baseline}
.tab b{font:600 11px "Martian Mono",ui-monospace,monospace;color:var(--ink-3)}
.tab:hover{color:var(--ink)}
.tab[aria-selected="true"]{color:var(--ink);border-bottom-color:var(--hivis)}
.pane{padding:16px 18px;overflow:auto;min-height:0}
.lead{margin:0 0 12px;color:var(--ink-2);font-size:14.5px}
.jobp{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(0,1fr)}
.jobmain{padding:4px 24px 4px 4px;display:flex;flex-direction:column;gap:10px;border-right:1px solid var(--line-2)}
.jobhead{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.jn{font:800 32px/1 "Big Shoulders Display","Arial Narrow",sans-serif;background:var(--ink);color:var(--ground);padding:4px 10px 1px}
.jt{margin:0;font:800 32px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;overflow-wrap:anywhere}
.jk{margin:0;font:500 12px "Martian Mono",ui-monospace,monospace;color:var(--ink-3);overflow-wrap:anywhere}
.spec{margin:0;display:flex;flex-wrap:wrap;border:1px solid var(--line-2);background:var(--line-2);gap:1px}
.spec:empty{display:none}
.spec>div{background:var(--panel);padding:6px 12px 7px;display:flex;flex-direction:column;gap:2px;flex:1 1 auto}
.spec dt{font:600 9.5px "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3)}
.spec dd{margin:0;font:600 13px "Martian Mono",ui-monospace,monospace;color:var(--ink);white-space:nowrap}
.spec .ok{color:var(--merged)}.spec .no{color:var(--decision)}
.jobp{--sc:var(--line);border-top:4px solid var(--sc);padding-top:14px}
.jobp[data-state="merged"],.jobp[data-state="resolved"]{--sc:var(--merged)}.jobp[data-state="in-progress"]{--sc:var(--run)}
.jobp[data-state="decision"]{--sc:var(--decision)}.jobp[data-state="blocked"]{--sc:var(--blocked)}.jobp[data-state="ready"]{--sc:var(--ink-3)}
.jobp.swap .jobmain,.jobp.swap .jside{animation:swap .22s ease-out}
@keyframes swap{from{opacity:.25;transform:translateY(4px)}to{opacity:1;transform:none}}
.jbody{margin:0;font-size:15.5px;color:var(--ink-2);max-width:72ch;overflow-wrap:anywhere}
.jneeds{margin:0;font:500 12px "Martian Mono",ui-monospace,monospace;color:var(--ink-2)}
.jsha{margin:0;font:500 12px/1.5 "Martian Mono",ui-monospace,monospace;color:var(--merged)}
.jside{padding:4px 4px 4px 22px;display:flex;flex-direction:column;gap:10px}
.flags{display:flex;flex-direction:column;gap:14px}
.flag{margin:0;font-size:13.5px;color:var(--ink-2);padding:2px 0 2px 14px;border-left:3px solid var(--line);overflow-wrap:anywhere}
.flag.dec{border-left-color:var(--decision)}.flag.ok{border-left-color:var(--merged)}.flag.none{color:var(--ink-3)}
#pane-job{padding:0;overflow:hidden;display:grid;grid-template-rows:auto minmax(0,1fr)}
#pane-job[hidden]{display:none}
.jnav{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:8px 18px;border-bottom:1px solid var(--line-2);background:var(--panel)}
.jpos{font:600 12px "Martian Mono",ui-monospace,monospace;color:var(--ink-3);font-variant-numeric:tabular-nums}
.jscroll{overflow:auto;min-height:0;padding:16px 18px}
.figs{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:1px;background:var(--line-2);border:1px solid var(--line-2)}
.figs:empty{display:none}
.fig{background:var(--ground);padding:10px 12px;display:flex;flex-direction:column;gap:4px}
.fig b{font:800 30px/1 "Big Shoulders Display","Arial Narrow",sans-serif;font-variant-numeric:tabular-nums}
.fig.good b{color:var(--merged)}.fig.warn b{color:var(--decision)}
.fig span{font-size:12.5px;color:var(--ink-2);line-height:1.35}
.jlesson{margin:0;padding:10px 12px;background:var(--ink);color:var(--ground);font-size:14px;border-left:4px solid var(--hivis)}
.jlesson b{font:600 10.5px "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--hivis);margin-right:6px}
.lesson{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.15fr);gap:20px 40px;align-items:start}
.lmain,.llist{display:flex;flex-direction:column;gap:12px;min-width:0}
.lesson h3{margin:0;font:800 clamp(28px,3.2vw,44px)/.95 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;text-wrap:balance}
.lesson .rule{margin:0;border-left:6px solid var(--hivis);padding:4px 0 4px 18px;font-size:16px;line-height:1.6;color:var(--ink)}
.lesson .jl{margin:0;font-size:14px;color:var(--ink-2);padding:0 0 14px;border-bottom:1px solid var(--line-2)}
.jlh{display:flex;align-items:baseline;gap:10px;margin-bottom:4px;font-weight:700;color:var(--ink)}
.jlh b{font:600 11px "Martian Mono",ui-monospace,monospace;background:var(--ink);color:var(--ground);padding:3px 6px}
.alert{margin-top:8px;font-size:12.5px;color:var(--ink-2);background:var(--panel);border:1px solid var(--line);border-left:0;padding:6px 10px 6px 24px;position:relative;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.alert{cursor:pointer}.alert::before{content:"";position:absolute;left:0;top:0;bottom:0;width:12px;background:repeating-linear-gradient(-45deg,var(--hivis) 0 5px,var(--hivis-ink) 5px 10px)}.alert:hover{border-color:var(--ink-3)}
.alert b{font:600 10.5px "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;margin-right:6px}
.alert .more{font:600 11px "Martian Mono",ui-monospace,monospace;background:none;border:0;color:var(--run);cursor:pointer;padding:0 0 0 6px}
.alerts-l li{border-left:4px solid var(--hivis)}
.jnav button{font:600 12px "Martian Mono",ui-monospace,monospace;padding:7px 10px;border:1px solid var(--line);background:var(--ground);color:var(--ink);cursor:pointer}
.jnav button:disabled{opacity:.35;cursor:default}
.pill{justify-self:end;align-self:center;font:600 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--c,var(--ink-2));border:1.5px solid var(--c,var(--ink-2));padding:5px 7px;white-space:nowrap}
.pill.merged,.pill.resolved{--c:var(--merged)}.pill.in-progress{--c:var(--run)}.pill.blocked{--c:var(--blocked)}.pill.decision{--c:var(--decision)}
.cl{display:flex;flex-direction:column;gap:1px;background:var(--line-2);border:1px solid var(--line-2)}
.cr{background:var(--panel);display:grid;grid-template-columns:200px 150px minmax(0,1fr) auto;gap:0 16px;padding:12px 16px;border-left:4px solid var(--c,var(--line))}
.cr{cursor:pointer}.cr:hover{background:var(--ground)}.cr:focus-visible{outline:2px solid var(--focus);outline-offset:-2px}
.cr.in-progress{--c:var(--run)}.cr.blocked{--c:var(--blocked)}.cr.decision{--c:var(--decision)}.cr.isnext{--c:var(--hivis);background:color-mix(in srgb,var(--hivis) 10%,var(--panel))}
.ck{font:600 13px "Martian Mono",ui-monospace,monospace}
.cn{display:block;font-size:13.5px;font-weight:600;margin-top:2px}
.cb{font:500 11.5px/1.7 "Martian Mono",ui-monospace,monospace;color:var(--ink-2)}
.cb .ok{color:var(--merged)}.cb .no{color:var(--decision);font-weight:600}
.cnote{font-size:13.5px;color:var(--ink-2);overflow-wrap:anywhere}
.owed{counter-reset:o;list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:1px;background:var(--line-2);border:1px solid var(--line-2)}
.owed li{counter-increment:o;background:var(--panel);padding:11px 14px 11px 48px;position:relative;font-size:14px;color:var(--ink-2)}
.owed li::before{content:counter(o,decimal-leading-zero);position:absolute;left:14px;top:13px;font:600 11px "Martian Mono",ui-monospace,monospace;color:var(--ink-3);font-variant-numeric:tabular-nums}
.about{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.15fr);gap:18px 40px;align-items:start}
.amain,.aside{display:flex;flex-direction:column;gap:12px;min-width:0}
.about .foot{grid-column:1 / -1}
.about p{margin:0;color:var(--ink-2)}
.about .h{font:800 clamp(30px,3.4vw,46px)/.95 "Big Shoulders Display","Arial Narrow",sans-serif;text-wrap:balance;text-transform:uppercase;color:var(--ink)}
.foot{margin-top:14px;font:500 11px/1.7 "Martian Mono",ui-monospace,monospace;color:var(--ink-3);border-top:1px solid var(--line);padding-top:12px;overflow-wrap:anywhere}
@media (max-width:900px),(max-height:560px){
 body{overflow:auto}
 .wrap{height:auto;display:flex;flex-direction:column;gap:14px;padding-block:14px 40px}
 .fishwrap .scroll{height:300px;overflow-x:auto;overflow-y:hidden}
 .pane{overflow:visible}
 #pane-job{overflow:visible}
 .jscroll{overflow:visible}
}
.wrap>*,.fishwrap,.panel,.fishbar,.chips,.scroll{min-width:0}
.fishwrap,.panel{grid-template-columns:minmax(0,1fr)}
@media (max-width:900px){
 .spec dd{white-space:normal;overflow-wrap:anywhere}.fsel{max-width:100%}
 .jobp{grid-template-columns:1fr}.jobmain{border-right:0;border-bottom:1px solid var(--line-2);padding:0 0 16px}.jside{padding:16px 0 0}
 .hright{flex-wrap:wrap;flex:1 1 auto}.lesson,.about{grid-template-columns:1fr}.status{flex-wrap:wrap;row-gap:6px}
 .cr{grid-template-columns:1fr auto;gap:6px 12px}.cr .cb,.cr .cnote{grid-column:1 / -1}.cr .pill{grid-row:1;grid-column:2}
}
/* ── Site details: stencil numbers, site notices, the stamp, the work docket, the dimension line ── */
.jn,.gnum b,.fig b{font-family:"Big Shoulders Stencil Display","Big Shoulders Display","Arial Narrow",sans-serif}
/* site notice: yellow sign, black border, the label as a black plate */
.alert{background:var(--hivis);color:var(--hivis-ink);border:2px solid var(--hivis-ink);padding:5px 10px}
.alert::before{display:none}
.alert:hover{border-color:var(--hivis-ink);box-shadow:inset 0 0 0 1px var(--hivis-ink)}
.alert b{background:var(--hivis-ink);color:var(--hivis);padding:3px 7px 2px;margin-right:10px}
.alert .more{color:var(--hivis-ink);text-decoration:underline;text-underline-offset:2px}
.flag.dec{background:var(--hivis);color:var(--hivis-ink);border:2px solid var(--hivis-ink);padding:10px 12px}
.flag.dec b{font:700 11px "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;margin-right:4px}
.cr .pill.decision{background:var(--hivis);color:var(--hivis-ink);border:2px solid var(--hivis-ink)}
/* the stamp: the job's status on its docket, inked and a little off square */
.jobhead .pill{font:800 15px/1 "Big Shoulders Stencil Display","Big Shoulders Display","Arial Narrow",sans-serif;letter-spacing:.14em;
  border:3px double var(--c,var(--ink-2));padding:5px 9px 3px;transform:rotate(-4deg);opacity:.92}
/* the work docket: a punched top edge, a dashed tear line to the notes stub */
.jobp{position:relative;border-top:0;padding-top:24px}
.jobp::before{content:"";position:absolute;left:0;right:0;top:0;height:4px;background:var(--sc)}
.jobp::after{content:"";position:absolute;left:0;right:0;top:9px;height:7px;background:radial-gradient(circle,var(--ground) 2.4px,var(--line) 2.9px,transparent 3.4px) 4px 0/18px 7px repeat-x}
.jobmain{border-right:2px dashed var(--line)}
.jobmain::before{content:"Work docket";font:600 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.18em;text-transform:uppercase;color:var(--ink-3)}
/* the dimension line: a surveyor's measure over the built part of the tape */
.dim{grid-row:1;position:relative;height:16px;margin-bottom:3px;border-inline:1.5px solid var(--ink-3);display:flex;align-items:center;justify-content:center}
.dim::before{content:"";position:absolute;left:0;right:0;top:50%;border-top:1px solid var(--ink-3)}
.dim span{position:relative;background:var(--panel);padding:0 8px;font:600 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-2);white-space:nowrap}
/* under 3 chips the measure is too short for its label: the label sits just past its right end */
.dim.short{justify-content:flex-start}
.dim.short span{position:absolute;left:100%;margin-left:6px;padding-left:0}
.chips.has-dim .jc{grid-row:2}
@media (max-width:900px){
 .jobmain{border-right:0;border-bottom:2px dashed var(--line)}
 .dim{display:none}.chips.has-dim .jc{grid-row:auto}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
"""

JS = r"""
(function(){
const D = JSON.parse(document.getElementById("board-data").textContent);
const jobs = D.jobs, n = jobs.length, LABEL = D.label;
const chips = [...document.querySelectorAll(".jc")];
const NS = "http://www.w3.org/2000/svg", box = document.querySelector(".fishwrap .scroll"), svg = document.getElementById("fish");
function el(t, a, x){ const e = document.createElementNS(NS, t); for (const k in a) e.setAttribute(k, a[k]); if (x != null) e.textContent = x; return e; }
function cut(t, w){ t = String(t || ""); return t.length <= w ? t : t.slice(0, w - 1).trimEnd() + "\u2026"; }
function wrapWords(t, w, max){ const out = []; let c = ""; String(t).split(/\s+/).forEach(x => { if (!c) c = x; else if ((c + " " + x).length <= w) c += " " + x; else { out.push(c); c = x; } }); if (c) out.push(c); if (out.length > max) { out.length = max; out[max - 1] = cut(out[max - 1], w); } return out; }
let ribs = [];
function draw(){
  // a narrow screen keeps a full-size drawing and scrolls it sideways inside its own box
  const narrow = box.clientWidth < 760, W = narrow ? 900 : box.clientWidth, H = Math.max(190, box.clientHeight);
  svg.setAttribute("viewBox", "0 0 " + W + " " + H); svg.removeAttribute("width"); svg.removeAttribute("height");
  svg.style.width = narrow ? W + "px" : "";
  svg.textContent = "";
  const headW = Math.min(250, W * 0.22), slot = (D.next || D.topped) ? 0 : 1, total = n + slot;
  const SP = H / 2, left = 36, right = W - headW - 30;
  const step = (right - left) / Math.max(1, Math.ceil(total / 2) + 0.5);
  const rise = SP - 30, run = Math.min(step * 0.9, rise * 0.55);
  const defs = el("defs", {}), pat = el("pattern", {id:"hz", width:12, height:12, patternUnits:"userSpaceOnUse", patternTransform:"rotate(45)"});
  pat.appendChild(el("rect", {class:"hzA", width:12, height:12})); pat.appendChild(el("rect", {class:"hzB", width:6, height:12}));
  defs.appendChild(pat); svg.appendChild(defs);
  svg.appendChild(el("line", {class:"spine", x1:left - 10, y1:SP, x2:right + 4, y2:SP}));
  let built = -1; jobs.forEach((j, i) => { if (j.state === "merged" || j.state === "resolved") built = i; });
  if (built >= 0) { const bxb = left + run + Math.floor(built / 2) * step + (built % 2 ? step / 2 : 0);
    svg.appendChild(el("line", {class:"spine built", x1:left - 10, y1:SP, x2:bxb, y2:SP}));
    svg.appendChild(el("circle", {class:"builtdot", cx:bxb, cy:SP, r:6})); }
  svg.appendChild(el("path", {class:"spinehead", d:"M" + (right + 2) + "," + (SP - 9) + " L" + (right + 15) + "," + SP + " L" + (right + 2) + "," + (SP + 9) + " Z"}));
  ribs = [];
  const pos = i => { const up = i % 2 === 0, bx = left + run + Math.floor(i / 2) * step + (up ? 0 : step / 2); return {up, bx, tx: bx - run, ty: SP + (up ? -1 : 1) * rise}; };
  jobs.forEach((j, i) => {
    const {up, bx, tx, ty} = pos(i), d = up ? -1 : 1;
    const g = el("g", {class:"rib " + j.state + (j.id === D.next ? " next" : ""), tabindex:"0", role:"button", "aria-label": j.id + " " + j.title + ", " + LABEL[j.state]});
    g.appendChild(el("line", {class:"tick", x1:bx, y1:SP - 6, x2:bx, y2:SP + 6}));
    g.appendChild(el("path", {class:"ribl", d:"M" + bx + "," + SP + " L" + tx + "," + ty}));
    const east = bx < W * 0.55;
    (j.twigs || []).forEach((t, k) => { const f = (k + 1) / 4, px = bx - run * f, py = SP + d * rise * f;
      g.appendChild(el("line", {class:"twl", x1:px, y1:py, x2:east ? px + 12 : px - 12, y2:py}));
      g.appendChild(el("text", {class:"twt", x:east ? px + 16 : px - 16, y:py + 4, "text-anchor": east ? "start" : "end"}, cut(t, 46))); });
    const cw = Math.max(26, 8 * j.id.length + 10), cy = up ? ty - 20 : ty + 2;
    g.appendChild(el("rect", {class:"chip", x:tx - cw / 2, y:cy, width:cw, height:18}));
    g.appendChild(el("text", {class:"chipt", x:tx, y:cy + 13, "text-anchor":"middle"}, j.id));
    const anchor = east ? "start" : "end", nx = east ? tx + cw / 2 + 7 : tx - cw / 2 - 7;
    // the selected job's name is shown in the bar above the drawing (never on the canvas, where it would collide)
    const sub = [j.key, j.pr && "PR " + j.pr].filter(Boolean).join(" \u00b7 ");

    const tt = el("title", {}, j.id + " \u00b7 " + j.title); g.insertBefore(tt, g.firstChild);
    g.addEventListener("click", () => { pick(i); show("job", true); });
    g.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(i); show("job", true); } });
    g.dataset.x = tx; svg.appendChild(g); ribs.push(g);
  });
  svg.querySelectorAll(".twt").forEach(t => { const bb = t.getBBox();
    t.parentNode.insertBefore(el("rect", {class:"twbg", x:bb.x - 4, y:bb.y - 2, width:bb.width + 8, height:bb.height + 4}), t); });
  if (slot) { const {up, bx, tx, ty} = pos(n);
    svg.appendChild(el("path", {class:"nextl", d:"M" + bx + "," + SP + " L" + tx + "," + ty}));
    // one short line level with the chips, centred on the slot's open end
    svg.appendChild(el("text", {class:"nextt", x:tx, y:up ? ty - 6 : ty + 16, "text-anchor":"middle"}, "next: not chosen")); }
  const hx = right + 20, lines = wrapWords(D.head.outcome, Math.max(12, Math.floor(headW / 11)), 4), bh = 50 + 24 * lines.length, top = SP - bh / 2;
  svg.appendChild(el("rect", {class:"headbox", x:hx, y:top, width:headW, height:bh}));
  svg.appendChild(el("rect", {class:"headstripe", x:hx, y:top, width:headW, height:10}));
  svg.appendChild(el("text", {class:"heads", x:hx + 16, y:top + 30}, "THE HEAD"));
  lines.forEach((ln, k) => svg.appendChild(el("text", {class:"headt", x:hx + 16, y:top + 56 + 24 * k}, ln)));
  if (ribs[cur]) { ribs[cur].classList.add("on"); svg.appendChild(ribs[cur]); }
}
const $ = id => document.getElementById(id);
function txt(id, v){ const e = $(id); if (e) e.textContent = v || ""; }
let cur = D.start;
function pick(i){
  cur = i; const j = jobs[i];
  ribs.forEach((g, k) => g.classList.toggle("on", k === i));
  if (ribs[i]) { svg.appendChild(ribs[i]); if (box.scrollWidth > box.clientWidth) box.scrollLeft = Math.max(0, +ribs[i].dataset.x - box.clientWidth / 2); }
  chips.forEach((b, k) => b.setAttribute("aria-pressed", String(k === i)));
  txt("jn", j.id); txt("jt", j.title);
  const sp = $("jspec"); sp.textContent = "";
  const cell = (k, fill) => { const d = document.createElement("div"), t = document.createElement("dt"), v = document.createElement("dd"); t.textContent = k; fill(v); d.appendChild(t); d.appendChild(v); sp.appendChild(d); };
  [["Key", j.key], ["Ticket", j.ticket], ["Run", j.run]].forEach(([k, v]) => v && cell(k, e => { e.textContent = v; }));
  if (j.needs.length) cell("Needs", e => j.needs.forEach((x, q) => { const s = document.createElement("span"); s.className = x.done ? "ok" : "no"; s.textContent = x.id + (x.done ? " \u2713" : " \u2717"); if (q) e.appendChild(document.createTextNode(" ")); e.appendChild(s); }));
  [["PR", j.pr], ["Merge", j.merge]].forEach(([k, v]) => v && cell(k, e => { e.textContent = v; }));
  const jp2 = $("jobp"); jp2.dataset.state = j.state; jp2.classList.remove("swap"); void jp2.offsetWidth; jp2.classList.add("swap");
  txt("fsel", [j.id, j.title, j.key, j.pr && "PR " + j.pr].filter(Boolean).join(" · "));
  const p = $("jp"); p.textContent = LABEL[j.state]; p.className = "pill " + j.state;
  txt("jb", j.summary);

  const fg = $("jfigs"); fg.textContent = "";
  (j.figures || []).forEach(x => { const d = document.createElement("div"); d.className = "fig " + (x.tone || "");
    const b = document.createElement("b"); b.textContent = x.n; const sp = document.createElement("span"); sp.textContent = x.label;
    d.appendChild(b); d.appendChild(sp); fg.appendChild(d); });
  const jl = $("jl"); jl.hidden = !j.lesson; jl.textContent = ""; if (j.lesson) { const b = document.createElement("b"); b.textContent = "Lesson"; jl.appendChild(b); jl.appendChild(document.createTextNode(" " + j.lesson)); }
  const f = $("jf"); f.textContent = "";
  const flags = [];
  if (j.state === "decision" && j.decision) flags.push(["dec", "To decide: ", j.decision]);
  if (j.state === "resolved" && j.resolution) flags.push(["ok", "Decided: ", j.resolution]);
  j.notes.forEach(x => flags.push(["", "", x]));
  if (!flags.length) flags.push(["none", "", "Nothing recorded against this job."]);
  flags.forEach(([c, b, t]) => { const e = document.createElement("p"); e.className = "flag " + c;
    if (b) { const s = document.createElement("b"); s.textContent = b; e.appendChild(s); } e.appendChild(document.createTextNode(t)); f.appendChild(e); });
  txt("jcount", flags[0][0] === "none" ? "none" : String(flags.length));
  $("prev").disabled = i === 0; $("nextb").disabled = i === n - 1;
  txt("jpos", (i + 1) + " of " + n); const sc2 = $("jscroll"); if (sc2) sc2.scrollTop = 0;
}
chips.forEach((b, i) => b.addEventListener("click", () => { pick(i); show("job", true); }));
$("prev").addEventListener("click", () => cur > 0 && pick(cur - 1));
$("nextb").addEventListener("click", () => cur < n - 1 && pick(cur + 1));
const tabs = [...document.querySelectorAll(".tab")], KEY = "foreman-board-tab-" + D.slug;
function show(t, push){
  tabs.forEach(b => b.setAttribute("aria-selected", String(b.dataset.tab === t)));
  document.querySelectorAll(".pane").forEach(p => { p.hidden = p.id !== "pane-" + t; });
  try { localStorage.setItem(KEY, t); } catch (e) {}
  if (push) { try { history.replaceState(null, "", "#" + t); } catch (e) {} }
  const pane = document.getElementById("pane-" + t); if (pane) pane.scrollTop = 0;
}
tabs.forEach(b => b.addEventListener("click", () => show(b.dataset.tab, true)));
document.querySelectorAll(".cr[data-job]").forEach(r => { const go = () => { const i = jobs.findIndex(j => j.id === r.dataset.job); if (i >= 0) { pick(i); show("job", true); } };
  r.addEventListener("click", go); r.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } }); });
document.querySelectorAll("[data-go]").forEach(b => { b.addEventListener("click", e => { e.stopPropagation(); show(b.dataset.go, true); });
  b.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); show(b.dataset.go, true); } }); });
tabs.forEach((b, k) => b.addEventListener("keydown", e => {
  if (e.key === "ArrowRight" || e.key === "ArrowLeft") { const nb = tabs[(k + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length]; nb.focus(); show(nb.dataset.tab, true); } }));
let start = (location.hash || "").slice(1);
if (!tabs.some(b => b.dataset.tab === start)) { try { start = localStorage.getItem(KEY) || "job"; } catch (e) { start = "job"; } }
show(tabs.some(b => b.dataset.tab === start) ? start : "job", false);
draw(); pick(cur);
let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { draw(); pick(cur); }, 120); });
})();
"""


def logo_uri(path):
    """The hard hat as a data: URI (pages stay single-file); '' when the file is missing."""
    try:
        return "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode("ascii")
    except OSError:
        return ""


def render(board, standalone=False):
    jobs, nxt = board["jobs"], board.get("next")
    by_id = {b["id"]: b for b in jobs}
    count = {s: 0 for s in SHOWN}
    for b in jobs:
        count[shown_state(b, by_id)] += 1
    project = board["project"]
    nb = by_id.get(nxt)
    done = count["merged"] + count["resolved"]
    # the job the page opens on: the one in progress, else the next one, else the latest done
    start = next((i for i, b in enumerate(jobs) if shown_state(b, by_id) == "in-progress"), None)
    if start is None and nxt in by_id:
        start = [b["id"] for b in jobs].index(nxt)
    if start is None:
        start = max((i for i, b in enumerate(jobs) if shown_state(b, by_id) in DONE), default=0)
    segs = "".join(f'<i class="{shown_state(b, by_id)}{" isnext" if b["id"] == nxt else ""}" title="{esc(b["id"])} · {esc(LABEL[shown_state(b, by_id)])}"></i>' for b in jobs)
    gauge = (f'<div class="gauge"><div class="gnum"><b>{done}</b><span>/ {len(jobs)} done</span></div>'
             f'<div class="gbar" aria-hidden="true">{segs}</div></div>')
    status = []
    for st, word in (("in-progress", "in progress"), ("ready", "ready"), ("blocked", "blocked"), ("decision", "to decide")):
        if count[st]:
            status.append(f'<span><b>{count[st]}</b> {word}</span>')
    if board.get("topped_out"):
        status.append(f'<span class="nx">topped out <b>{esc(board["topped_out"]["date"])} · {len(board["topped_out"].get("carried", []))} carried over</b></span>')
    else:
        status.append(f'<span class="nx">next: <b>{esc(nxt + " · " + one_line(nb["title"], 34)) if nb else "not chosen"}</b></span>')
    built_to = max((i for i, b in enumerate(jobs) if shown_state(b, by_id) in DONE), default=-1)
    dim = (f'<div class="dim{" short" if built_to + 1 < 3 else ""}" style="grid-column:1 / span {built_to + 1}" aria-hidden="true"><span>{done} of {len(jobs)} built</span></div>'
           if built_to >= 0 else "")
    chips = "".join(f'<button type="button" class="jc {shown_state(b, by_id)}{" isnext" if b["id"] == nxt else ""}" id="jc-{esc(b["id"])}" '
                    f'aria-pressed="{str(i == start).lower()}">{esc(b["id"])}</button>' for i, b in enumerate(jobs))
    open_n = len(jobs) - done
    owed = project.get("owed") or []
    sup = board.get("superseded", [])
    tabs = [("job", "Job", ""), ("open", "Open", f"{open_n}")]
    if owed:
        tabs.append(("owed", "Debts", str(len(owed))))
    if sup:
        tabs.append(("split", "Split", str(len(sup))))
    plesson = project.get("lesson")
    jlessons = [b for b in jobs if b.get("lesson")]
    if plesson or jlessons:
        tabs.append(("lessons", "Lessons", str(len(jlessons)) if jlessons else ""))
    tabs.append(("head", "The head", ""))
    tab_html = "".join(f'<button type="button" role="tab" class="tab" id="tab-{k}" data-tab="{k}" aria-selected="{str(k == "job").lower()}">{label}'
                       f'{f" <b>{c}</b>" if c else ""}</button>' for k, label, c in tabs)
    panes = [f'<div class="pane" id="pane-job" role="tabpanel">'
             f'<div class="jnav"><button type="button" id="prev">← earlier</button>'
             f'<span class="jpos" id="jpos">{start + 1} of {len(jobs)}</span>'
             f'<button type="button" id="nextb">later →</button></div>'
             f'<div class="jscroll" id="jscroll" aria-live="polite">{job_detail(jobs[start], by_id)}</div></div>',
             f'<div class="pane" id="pane-open" role="tabpanel" hidden><p class="lead">Everything not yet merged or decided. The next job first.</p><div class="cl">{open_rows(jobs, by_id, nxt)}</div></div>']
    if owed:
        panes.append(f'<div class="pane" id="pane-owed" role="tabpanel" hidden><ul class="owed">{"".join(f"<li>{esc(o)}</li>" for o in owed)}</ul></div>')
    if sup:
        items = "".join(f'<li>{esc(x.get("id"))} · {esc(x.get("title", ""))} → split into {esc(", ".join(x.get("by", [])))} (v{esc(x.get("at_version", "?"))})</li>' for x in sup)
        panes.append(f'<div class="pane" id="pane-split" role="tabpanel" hidden><ul class="owed">{items}</ul></div>')
    if plesson or jlessons:
        les = ['<div class="lesson"><div class="lmain">']
        if plesson:
            les.append(f'<div class="lbl">The project\'s rule</div><h3>{esc(plesson["title"])}</h3>')
            if plesson.get("rule"):
                les.append(f'<p class="rule">{esc(plesson["rule"])}</p>')
        les.append('</div><div class="llist">')
        if jlessons:
            les.append(f'<div class="lbl">From each job · newest first</div>')
        for b in reversed(jlessons):
            les.append(f'<p class="jl"><span class="jlh"><b>{esc(b["id"])}</b>{esc(b["title"])}</span>{esc(b["lesson"])}</p>')
        les.append("</div></div>")
        panes.append(f'<div class="pane" id="pane-lessons" role="tabpanel" hidden>{"".join(les)}</div>')
    test = project["head"].get("test")
    about = [f'<div class="amain"><div class="lbl">The head · what done means</div><p class="h">{esc(project["head"]["outcome"])}</p>']
    if test:
        about.append(f'<p><b>Judged by:</b> {esc(test)}</p>')
    if project.get("standfirst"):
        about.append(f'<p>{esc(project["standfirst"])}</p>')
    alerts = project.get("alerts") or []
    facts = project.get("facts") or []
    if project.get("project_file"):
        about.append(f'<p class="jk">{esc(project["project_file"])}</p>')
    about.append('</div><div class="aside">')
    if alerts:
        about.append('<div class="lbl">Alerts</div><ul class="owed alerts-l">' + "".join(f"<li>{esc(a)}</li>" for a in alerts) + "</ul>")
    if facts:
        about.append('<div class="lbl">Standing facts</div><ul class="owed facts-l">' + "".join(f"<li>{esc(a)}</li>" for a in facts) + "</ul>")
    about.append('</div>')
    about.append(f'<p class="foot">Generated from BOARD.json v{esc(board["version"])} by render_board.py. Edit the data, not this page.</p>')
    panes.append(f'<div class="pane" id="pane-head" role="tabpanel" hidden><div class="about">{"".join(about)}</div></div>')
    al = project.get("alerts") or []
    alert_strip = ""
    if al:
        more = f' <button type="button" class="more" data-go="head">+{len(al) - 1} more</button>' if len(al) > 1 else ""
        alert_strip = f'<div class="alert" data-go="head" role="button" tabindex="0" title="{esc(al[0])}"><b>Alert</b> {esc(one_line(al[0], 190))}{more}</div>'
    data = {"slug": project.get("slug") or "board", "start": start, "label": LABEL, "next": nxt, "topped": bool(board.get("topped_out")),
            "head": {"outcome": project["head"]["outcome"], "test": project["head"].get("test") or ""},
            "jobs": [{"id": b["id"], "title": b["title"], "state": shown_state(b, by_id), "key": b.get("key"), "ticket": b.get("ticket"),
                      "run": b.get("run"), "summary": b.get("summary"), "pr": b.get("pr"), "merge": b.get("merge"),
                      "decision": b.get("decision"), "resolution": b.get("resolution"), "notes": b.get("notes", []), "twigs": b.get("twigs", [])[:3],
                      "figures": b.get("figures", []), "lesson": b.get("lesson") or "",
                      "needs": [{"id": x, "done": x in by_id and shown_state(by_id[x], by_id) in DONE} for x in b.get("needs") or []]}
                     for b in jobs]}
    blob = json.dumps(data, ensure_ascii=False).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    logo = logo_uri(Path(__file__).with_name("foreman-logo.png"))
    icon = f'<link rel="icon" type="image/png" href="{logo}">' if logo else ""
    mark = f'<img class="mark" src="{logo}" alt="">' if logo else ""
    body = f"""<title>{esc(project["title"])}</title>{icon}<script>try{{var t=localStorage.getItem("foreman-theme");if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t);}}catch(e){{}}</script>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@700;800&family=Big+Shoulders+Stencil+Display:wght@800&family=Martian+Mono:wght@400;500;600&family=Public+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap">
<style>{CSS}</style>
<div class="wrap">
<header class="bar">
<div class="kick">{mark}<span>Topping Out · {"iteration board" if project.get("mode") == "iteration" else "project board"}{(" · " + esc(project["eyebrow"])) if project.get("eyebrow") else ""}{(" · topped out " + esc(board["topped_out"]["date"])) if board.get("topped_out") else ""} · v{esc(board["version"])} · {esc(board["updated"])}</span><button type="button" class="theme-toggle" data-theme-toggle>Light</button></div>
<div class="barrow"><h1>{esc(project["title"])}</h1><div class="hright">{gauge}<div class="status">{"".join(status)}</div></div></div>
{alert_strip}
</header>
<section class="fishwrap">
<div class="fishbar"><div class="leg"><span><i></i>merged / decided</span><span class="l-run"><i></i>in progress</span><span class="l-ready"><i></i>ready</span><span class="l-blocked"><i></i>blocked</span><span class="l-decision"><i></i>to decide</span><span class="l-next"><i></i>next</span></div><span class="fsel" id="fsel" aria-live="polite">pick a rib or a chip</span></div>
<div class="scroll">{fishbone(board, by_id)}</div>
<div class="chips{" has-dim" if dim else ""}" style="--n:{len(jobs)}">{dim}{chips}</div>
</section>
<section class="panel">
<div class="tabs" role="tablist" aria-label="Board panels">{tab_html}</div>
{"".join(panes)}
</section>
</div>
<script type="application/json" id="board-data">{blob}</script>
<script>{JS}</script>
<script>(function(){{var r=document.documentElement;function cur(){{var t=r.getAttribute("data-theme");if(t==="light"||t==="dark")return t;return window.matchMedia&&matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";}}document.querySelectorAll("[data-theme-toggle]").forEach(function(b){{function lab(){{var to=cur()==="dark"?"light":"dark";b.textContent=to==="dark"?"Dark":"Light";b.setAttribute("aria-label","Switch to "+to+" mode");b.title="Switch to "+to+" mode";}}lab();b.addEventListener("click",function(){{var n=cur()==="dark"?"light":"dark";r.setAttribute("data-theme",n);try{{localStorage.setItem("foreman-theme",n);}}catch(e){{}}document.querySelectorAll("[data-theme-toggle]").forEach(function(x){{x.dispatchEvent(new Event("relabel"));}});}});b.addEventListener("relabel",lab);}});}})();</script>
"""
    if standalone:
        return ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
                + body.replace("</style>", "</style>\n</head><body>", 1) + "</body></html>\n")
    return body


# ---------------------------------------------------------------- io

def show(out, board):
    """Open the board in the browser: on its first page and at a topping out, never on routine updates.
    A page that isn't standalone (the artifact fragment) is opened from a standalone copy in the temp folder.
    FOREMAN_BOARD_NO_OPEN=1 turns it off (headless machines); =dry prints what it would open (the tests).
    Never fails the command."""
    mode = os.environ.get("FOREMAN_BOARD_NO_OPEN")
    if mode == "dry":
        print(f"would open {out} in the browser")
        return
    if mode:
        return
    try:
        target = out
        if not board.get("publish", {}).get("standalone"):
            import tempfile
            slug = re.sub(r"[^A-Za-z0-9_-]", "-", out.parent.name) or "board"
            target = Path(tempfile.gettempdir()) / f"topping-out-board-{slug}.html"
            target.write_text(render(board, True), encoding="utf-8", newline="\n")
        if sys.platform.startswith("win"):
            os.startfile(str(target))
        else:
            import subprocess
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(target)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"opened {target} in the browser")
    except Exception as ex:
        print(f"(could not open the board in a browser: {type(ex).__name__}: {ex}; open {out} yourself)", file=sys.stderr)


def write_atomic(pairs):
    """pairs: [(path, text)]. Write all temps first, then replace in order."""
    temps = []
    try:
        for p, text in pairs:
            tmp = p.with_name(p.name + ".tmp")
            tmp.write_text(text, encoding="utf-8", newline="\n")
            temps.append((tmp, p))
        for tmp, p in temps:
            os.replace(tmp, p)
    finally:
        for tmp, _ in temps:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass


def init(path, args):
    """Start a board for a project that wasn't cut by /f-schedule: the head and the first job.
    Later jobs come by 'add' (merged ones by 'add --merged'). Refuses to overwrite a board."""
    pos, vals, flags = parse(args, ("--title", "--head", "--test", "--job", "--job-title"), ("--iteration",))
    if pos:
        raise Usage(f"unexpected arguments {pos}")
    if path.exists():
        raise Usage(f"{path} already exists; init only starts a new board")
    first = need(vals, "--job")
    if not ID.match(first):
        raise Usage(f"job id {first!r} must be 1-16 letters/digits/._-")
    head = {"outcome": need(vals, "--head")}
    if vals.get("--test"):
        head["test"] = vals["--test"]
    board = {"schema": 1,
             "project": dict({"title": need(vals, "--title"), "head": head, "owed": [], "alerts": [], "facts": []},
                             **({"mode": "iteration"} if "--iteration" in flags else {})),
             "publish": {"local_html": "board.html"}, "version": 1,
             "updated": datetime.date.today().isoformat(), "next": None,
             "jobs": [{"id": first, "title": need(vals, "--job-title"), "kind": "build", "state": "open", "needs": [], "notes": []}],
             "log": ["v1: board started with init"]}
    validate(board)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = path.with_name("board.html")
    write_atomic([(path, json.dumps(board, indent=2, ensure_ascii=False) + "\n")])
    write_atomic([(out, render(board, False))])
    print(f"init: BOARD.json version 1 with job {first}; wrote {out}")
    show(out, board)
    return 0


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    args = argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    path = Path(args.pop(0))
    cmd = args.pop(0) if args and not args[0].startswith("--") else "render"
    if cmd == "init":
        return init(path, args)
    if cmd not in ("render", "check", "next", "report") and cmd not in EVENTS:
        raise Usage(f"unknown command {cmd!r}; see --help")
    try:
        board = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as ex:
        raise SpineError([f"BOARD.json is not valid JSON: {ex}"])
    validate(board)
    out = path.with_name(board.get("publish", {}).get("local_html", "board.html"))
    if cmd == "check":
        parse(args, ())
        for w in WARNINGS:
            print("WARNING:", w, file=sys.stderr)
        top = board.get("topped_out")
        print("BOARD OK:", len(board["jobs"]), "jobs, version", board["version"],
              f"TOPPED OUT {top['date']}, carried over: {', '.join(top.get('carried', [])) or 'none'}" if top else f"next = {board.get('next') or 'not chosen'}")
        return 0
    if cmd == "report":
        parse(args, ())
        top = board.get("topped_out")
        if not top:
            raise Usage("report is for a topped-out board (render_board.py BOARD.json topout first)")
        by_id = {b["id"]: b for b in board["jobs"]}
        done = [b for b in board["jobs"] if stored(b) in DONE]
        out = [f"## What was built (from BOARD.json v{board['version']}, topped out {top['date']})", "",
               "| Job | Title | State | PR | Merge | Run |", "|---|---|---|---|---|---|"]
        for b in done:
            out.append(f"| {b['id']} | {b['title']} | {stored(b)} | {b.get('pr') or ''} | {b.get('merge') or ''} | {b.get('run') or ''} |")
        out += ["", f"{len(done)} job{'' if len(done) == 1 else 's'} done, {len(top.get('carried', []))} carried over. "
                f"Head reached: {top.get('head_reached') or 'not recorded'}.", "", "## Carried over: jobs not built", ""]
        out += [f"- **{c}** {by_id[c]['title']} ({stored(by_id[c])}){': ' + by_id[c]['decision'] if by_id[c].get('decision') else ''}"
                for c in top.get("carried", []) if c in by_id] or ["- none"]
        out += ["", "## Carried over: owed items (word for word from the board)", ""]
        out += [f"- {o}" for o in board["project"].get("owed", [])] or ["- none"]
        print("\n".join(out))
        return 0
    if cmd == "next":
        pos, vals, _ = parse(args, ("--after-close",))
        if pos:
            raise Usage(f"unexpected arguments {pos}")
        if board.get("topped_out"):
            print(f"topped out on {board['topped_out']['date']}: no next job on this board (the next head gets a new board)")
            return 0
        if "--after-close" in vals:
            ids = after_close(board, vals["--after-close"])
            by_id = {b["id"]: b for b in board["jobs"]}
            el = [by_id[i] for i in ids]
        else:
            el = eligible(board)
        if not el:
            print("no eligible job (nothing ready with all needs merged or decided)")
        for b in el:
            print(b["id"], "-", b["title"])
        return 0
    if cmd == "render":
        _, _, flags = parse(args, (), ("--standalone",))
        standalone = "--standalone" in flags or bool(board.get("publish", {}).get("standalone"))
        first = not out.exists()
        write_atomic([(out, render(board, standalone))])
        print("wrote", out)
        if first:
            show(out, board)  # a new board's first page (e.g. /f-schedule's first render)
        return 0
    if board.get("topped_out"):
        raise Usage(f"this board topped out on {board['topped_out']['date']} (version {board['topped_out']['version']}); it is the project's record now. The next head gets a new board in its own foreman/projects/<new slug>/ (/f-schedule, or init --iteration)")
    new = copy.deepcopy(board)
    EVENTS[cmd](new, args)
    validate(new)
    page = render(new, bool(new.get("publish", {}).get("standalone")))
    first = not out.exists()
    # BOARD.json is authoritative: commit it first. The page is derived: if writing it
    # fails, the event stands and `render` reconciles the page later (exit 4).
    write_atomic([(path, json.dumps(new, indent=2, ensure_ascii=False) + "\n")])
    try:
        write_atomic([(out, page)])
    except Exception as ex:
        print(f"RENDER PENDING: BOARD.json is at version {new['version']} but {out.name} was not written "
              f"({type(ex).__name__}: {ex}). Fix the cause, then run: render_board.py {path.name}", file=sys.stderr)
        return 4
    for w in WARNINGS:
        print("WARNING:", w, file=sys.stderr)
    print(f"{cmd}: BOARD.json now version {new['version']}; wrote {out}")
    if first or cmd == "topout":
        show(out, new)  # a first page, or a topping out: the frozen board is the project's record
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except SpineError as ex:
        for m in ex.errors:
            print("BOARD ERROR:", m, file=sys.stderr)
        sys.exit(1)
    except Usage as ex:
        print("USAGE ERROR:", ex, file=sys.stderr)
        sys.exit(2)
    except Exception as ex:
        print(f"CRASH: {type(ex).__name__}: {ex}", file=sys.stderr)
        sys.exit(3)

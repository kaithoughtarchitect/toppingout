"""Build flow.html (the package root): Topping Out's route, start to finish.

The steps live in PHASES below. Change a step here, then run:
    python scripts/build_flow.py
Never hand-edit flow.html; it is overwritten.
"""
import base64
import html
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "flow.html"
def logo_uri(path):
    """The hard hat as a data: URI (pages stay single-file); '' when the file is missing."""
    try:
        return "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode("ascii")
    except OSError:
        return ""


LOGO = logo_uri(Path(__file__).resolve().parent.parent / "assets" / "foreman-logo-128.png")
E = lambda s: html.escape(s, quote=True)

ACT = {"op": "Owner", "or": "Foreman", "bu": "Builder", "rv": "Inspector"}
ACT_LONG = {"op": "Owner (you)", "or": "Foreman", "bu": "Builder", "rv": "Independent inspector"}
# (id, sign title, short, note, steps[(actor, title, detail, tags[(kind,label)], word)])
PHASES = [
 ("0", "A plan becomes a project", "Plan", "Once per big piece of work.", [
   ("op", "Bring the idea", "What you want built, in your words. Not ready yet? Capture it with its open questions kept.", [("skill", "f-sketch"), ("opt", "optional")], None),
   ("or", "Survey it", "Settle every open question against the code, so nothing is left to guess. Aloud if you like; a council can settle a fork you hand it.", [("skill", "f-survey"), ("skill", "model-council"), ("skill", "speak"), ("opt", "councils, voice optional")], None),
   ("or", "Write the blueprint", "One decision-complete plan: locked decisions, acceptance (VPs), tasks.", [("skill", "f-blueprint"), ("file", "foreman/blueprints/ready/")], None),
   ("rv", "Cold read of the blueprint", "One to five seats from other model families read it cold, in parallel. Findings are merged, never voted. It writes the gate line.", [("skill", "f-plancheck")], None),
   ("or", "Settle every finding", "Each finding applied to the blueprint or answered in it, its fate in the findings table. No gate line, no cut.", [], None),
   ("or", "Cut it into jobs", "One ticket per job, one PR each. Owner decisions become their own jobs. Every VP carried. Shown to you first.", [("skill", "f-schedule"), ("agent", "simplicity-critic")], None),
   ("op", "Approve the cut", "Writing the project and publishing the board are separate words.", [], "go · publish"),
   ("or", "Board v1", "BOARD.json renders the fishbone page you follow. The first eligible job is marked next.", [("skill", "f-board"), ("file", "foreman/projects/<slug>/")], None),
 ]),
 ("1", "Start a job", "Start", "Every job, one ticket.", [
   ("op", "Open a fresh session", "Paste the opener the last job left beside its handover. The first job on a board has its own opener.", [("file", "foreman/handovers/OPENER-JOB-<N>.txt")], None),
   ("or", "Stand up as foreman", "Loads the role, the rules and the playbook in full, the lessons that apply to this job, and checks the project's board (none yet: start it with init).", [("skill", "f-shift"), ("skill", "f-search"), ("file", "REPO-PROFILE.md")], None),
   ("or", "Site walk", "Answer the questions cold, then check the key. Measure the machine. Read the live ticket. Report every owed decision. Stop.", [("file", "METHOD §2")], None),
   ("bu", "Pre-flight", "No product writes: proves Bash, git, writing outside its folder, the tools and its permissions. READY or BLOCKED.", [("file", "BUILDER-PREFLIGHT.txt"), ("skill", "f-comply"), ("opt", "f-comply optional")], None),
   ("op", "Say go", "Choosing the ticket is not authorising the build.", [], "go"),
   ("or", "Mark it started", "The job goes in progress on the board.", [("tool", "render_board.py start")], None),
 ]),
 ("2", "Setup and the plan", "Setup", "Before any product code.", [
   ("bu", "Work order 1: setup and t0", "Cut the worktree by name, write the job record, capture t0 on every gate. No code.", [("file", "WORK-ORDER-1-SETUP.txt")], None),
   ("or", "Scoping", "Settle every design fork with evidence, and record what was rejected.", [("file", "SCOPING.md")], None),
   ("or", "The plan and gate 1", "Requirements verbatim, tasks, VPs, the tests that must fail first. Then a cold read, the same way as the blueprint.", [("file", "PLAN.md"), ("skill", "f-plancheck")], None),
 ]),
 ("3", "The build loop", "Build", "One work order per task, until every task is built.", [
   ("or", "Write the work order", "One verifiable outcome. Decisions labelled D-, exact commands, a pinned HEAD. Tick the pre-send checklist.", [("file", "WORK-ORDER.txt")], None),
   ("op", "Pass the pointer", "One line: read file X, lines A to B. Or the foreman sends it over the pane link and a background watcher wakes it at the stop.", [("skill", "orca-pi-connect"), ("opt", "pane link optional, Orca")], None),
   ("bu", "Build it", "Tests fail first, then build. Hostile inputs, coverage, probes, G1 to G6, every touched module's tests. One commit, captures, a report, stop.", [], None),
   ("or", "Review it", "Disk before words. Run the new tests on the old code. Probe it yourself. Attribute every difference. Update the job record.", [("file", "WORK-ORDER-REVIEW.md")], None),
 ]),
 ("4", "Inspections", "Inspect", "After the last task. The owner stays out of it.", [
   ("bu", "Base versus head", "Every test that depends on a changed module, and the wider suites, at base and at head, through the repo's test adapter. Anything red only at head: stop.", [("file", "BASE-VS-HEAD.txt"), ("file", "TEST-ADAPTERS.md")], None),
   ("or", "Gate 2", "Every commit against its review, final captures against t0, the foreman's own base-vs-head, the one safety fact.", [("file", "GATE2-REVIEW.md")], None),
   ("or", "Lens inspection", "The foreman runs it in its own session over the job's range, lenses as fresh subagents, findings only. No PR exists yet. QUICK jobs skip it.", [("skill", "f-inspect"), ("agent", "review lenses"), ("file", "LENS-INSPECTION.md")], None),
   ("or", "Check every finding", "Reproduce each against the code; accept, reject or partly accept. Only what's accepted goes back.", [("file", "ADJUDICATION.md")], None),
   ("bu", "Fix what was accepted", "Test-first repair work orders, reviewed like any other.", [("file", "WORK-ORDER.txt")], None),
   ("or", "Pack the review", "One blind brief: goal, constraints verbatim, non-goals, the diff, absolute paths. Nothing names the builder.", [("skill", "pack-review"), ("file", "PACK-REVIEW.md")], None),
   ("rv", "Cross-model review", "A fresh session of the other model family reviews it cold. Carried by hand, or the bundled dispatcher runs it headless.", [("skill", "xreview"), ("tool", "cross-review-dispatch.mjs")], None),
   ("or", "Adjudicate", "Every claim reproduced first. Accepted fixes become work orders; security and concurrency fixes go back to the reviewer.", [("skill", "adjudicate")], None),
   ("or", "Final re-run and the ledger", "Captures, probes and base-vs-head again at the final head. Every requirement and VP passes, or there is no PR.", [("file", "ACCEPTANCE-LEDGER.md")], None),
 ]),
 ("5", "PR and merge", "Merge", "Outward acts: each one needs your word.", [
   ("or", "PR body", "What changed, acceptance, proof, limitations, rollback, the review record. Scanned for builder names.", [("file", "PR-BODY.md")], None),
   ("op", "Open the PR", "Pushed and opened; you watch it in the browser. Opening is not merging.", [], "open the PR"),
   ("or", "Greptile rounds", "Greptile scores the open PR out of 5. Its findings are checked like any inspection, the builder fixes what's accepted, the tests and sign-off re-run, then the push. Three rounds at most, then it stops for you.", [("skill", "f-greploop")], "greploop"),
   ("or", "PR description check", "Before you're asked to merge: the PR's description is re-read against the final code and results, and anything stale is rewritten.", [], None),
   ("op", "Merge", "Then the merge's tree is checked against the tree that was reviewed.", [], "merge"),
   ("or", "Clean up", "Once the tree check passes: delete the merged branch and remove the job's worktrees, unasked. Only the tracker transition waits for your word.", [], "tracker transition"),
 ]),
 ("6", "Close and the next job", "Close", "Then back to stage 1 while a next job is confirmed; at the head, top out and stop.", [
   ("or", "Close the job", "Only on a merge that's really on main, and only when every requirement passed. Then the record, Logbook cards, the archive, and the end-game lock opens: nothing new starts until the steps below are done.", [("skill", "f-signoff"), ("file", "foreman/completed-jobs/")], None),
   ("or", "Dev report", "The day's lesson, and the foreman's own scorecard.", [("file", "DEV-REPORT.md")], None),
   ("or", "Next-ticket decision", "The foreman reads the board and recommends the next ticket, naming the board version and what picked it.", [("file", "NEXT-TICKET-DECISION.md"), ("tool", "render_board.py next")], None),
   ("op", "Confirm the next job", "Say yes, or pick another. Under a standing goal the foreman decides and records it.", [], None),
   ("or", "Ground investigation", "Four research agents, one angle each, plus the repo's framework check: the next survey starts from what they found.", [("file", "GROUND-INVESTIGATION.md")], None),
   ("or", "Board close", "One close event: merged plus the confirmed next job, one version, republished to the same link.", [("skill", "f-board"), ("tool", "render_board.py close --next")], None),
   ("or", "Shift handover and opener", "A session brief becomes the shift handover and its answer key, plus the next session's opener as a file beside them, ready to paste.", [("agent", "handoff-builder"), ("file", "foreman/handovers/")], None),
   ("or", "Top out (when the head is reached)", "The other ending, when every job is done: close the last job, top the board out (frozen as the project's record), write the topping out report, then three to five candidate next heads instead of a handover and opener. You pick a head when you're ready and the cycle starts again.", [("file", "TOPPING-OUT-REPORT.md"), ("file", "NEXT-HEADS.md"), ("tool", "render_board.py topout")], None),
   ("or", "Push the records", "The end-game lock clears. Merge main into the records branch (never a rebase), check only records differ, push.", [], None),
 ]),
]

SHAPE = {
    "op": '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 1.5 18.5 10 10 18.5 1.5 10Z"/></svg>',
    "or": '<svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="8.2"/></svg>',
    "bu": '<svg viewBox="0 0 20 20" aria-hidden="true"><rect x="2.4" y="2.4" width="15.2" height="15.2" rx="1.5"/></svg>',
    "rv": '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 1.8 18.6 17.4H1.4Z"/></svg>',
}


def tag(kind, label):
    if kind == "skill":
        return f'<span class="tg tg-skill">/{E(label)}</span>'
    if kind == "agent":
        return f'<span class="tg tg-agent">{E(label)}</span>'
    if kind == "tool":
        return f'<span class="tg tg-tool">$ {E(label)}</span>'
    if kind == "opt":
        return f'<span class="tg tg-opt">{E(label)}</span>'
    return f'<span class="tg tg-file">{E(label)}</span>'


total = sum(len(p[4]) for p in PHASES)
counts = {a: sum(1 for p in PHASES for s in p[4] if s[0] == a) for a in ACT}
words = [s for p in PHASES for s in p[4] if s[4]]

n = 0
stages_html = []
track_html = []
for pid, name, short, note, steps in PHASES:
    rows = []
    for actor, title, detail, tags, word in steps:
        n += 1
        w = (f'<div class="word"><b>Your word</b><span>“{E(word)}”</span></div>'
             if word else "")
        t = "".join(tag(k, l) for k, l in tags)
        rows.append(
            f'<li class="st a-{actor}{" has-word" if word else ""}" data-actor="{actor}">'
            f'<span class="node" title="{E(ACT_LONG[actor])}">{SHAPE[actor]}</span>'
            f'<div class="st-body"><span class="st-n">{n:02d}</span>'
            f'<div class="st-main"><h3>{E(title)}</h3><p>{E(detail)}</p>'
            f'{"<div class=tgs>" + t + "</div>" if t else ""}</div>'
            f'<span class="who">{E(ACT[actor])}</span>{w}</div></li>')
    loop = ""
    if pid == "3":
        loop = ('<li class="ret"><span class="ret-mark" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M19 17V9a5 5 0 0 0-5-5H6M9 1 5.5 4 9 7"/></svg></span>'
                '<p><b>Repeat per task.</b> Repairs go test-first into the next work order. A GREEN probe means a missing test: stop. A HALT is recorded on the board.</p></li>')
    if pid == "6":
        loop = ('<li class="ret"><span class="ret-mark" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M19 17V9a5 5 0 0 0-5-5H6M9 1 5.5 4 9 7"/></svg></span>'
                '<p><b>Back to stage 1</b> with the next job, while one is confirmed. When every job is merged or resolved, the board tops out and the work stops: only you pick the next head.</p></li>')
    stages_html.append(
        f'<section class="stage" id="s{pid}" data-stage="{pid}">'
        f'<header class="sign"><span class="sign-n">{pid}</span><div><h2>{E(name)}</h2>'
        f'<p>{E(note)} <span class="sign-c">{len(steps)} steps</span></p></div></header>'
        f'<ol class="route">{"".join(rows)}{loop}</ol></section>')
    dots = "".join(f'<i class="d d-{s[0]}"></i>' for s in steps)
    track_html.append(
        f'<a class="tk" href="#s{pid}" style="flex-grow:{len(steps)}" data-stage="{pid}">'
        f'<span class="tk-top"><b>{pid}</b>{E(short)}</span><span class="tk-dots">{dots}</span></a>')

legend = "".join(
    f'<button type="button" class="flt a-{a}" id="flt-{a}" data-f="{a}" aria-pressed="false">'
    f'<span class="node">{SHAPE[a]}</span><span>{E(ACT_LONG[a])}</span><span class="flt-c">{counts[a]}</span></button>'
    for a in ACT)

CSS = r"""
:root{color-scheme:light;
 --ground:#ECEEEA;--panel:#F8F9F6;--panel-2:#E2E6E0;--line:#C9CFC7;--line-2:#DADFD8;
 --ink:#15181A;--ink-2:#454C50;--ink-3:#727A7E;
 --hivis:#FBB401;--hivis-ink:#101316;
 --op:#A5650F;--or:#1D4E89;--bu:#3B6D2F;--rv:#8A3B8F;
 --focus:#1D4E89}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
 --ground:#101315;--panel:#171B1E;--panel-2:#1F2427;--line:#2C3337;--line-2:#23292C;
 --ink:#E7EAE5;--ink-2:#B4BBB6;--ink-3:#808983;
 --op:#F0B04A;--or:#80AFE9;--bu:#8FCB7C;--rv:#D79DDB;--focus:#80AFE9}}
:root[data-theme="dark"]{color-scheme:dark;
 --ground:#101315;--panel:#171B1E;--panel-2:#1F2427;--line:#2C3337;--line-2:#23292C;
 --ink:#E7EAE5;--ink-2:#B4BBB6;--ink-3:#808983;
 --op:#F0B04A;--or:#80AFE9;--bu:#8FCB7C;--rv:#D79DDB;--focus:#80AFE9}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:calc(env(safe-area-inset-top,0px) + 88px)}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{transition:none!important;animation:none!important}}
body{margin:0;background:var(--ground);color:var(--ink);font:400 15px/1.55 "Public Sans",system-ui,-apple-system,"Segoe UI",sans-serif;padding-inline:16px;padding-block:0 80px}
.a-op{--c:var(--op)}.a-or{--c:var(--or)}.a-bu{--c:var(--bu)}.a-rv{--c:var(--rv)}
.wrap{max-width:1120px;margin:0 auto}
.mono{font-family:"Martian Mono",ui-monospace,"Cascadia Mono",Consolas,monospace}
:focus-visible{outline:2px solid var(--focus);outline-offset:3px}

/* hero */
.hero{padding-block:48px 28px;display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr);gap:28px 48px;align-items:end;border-bottom:1px solid var(--line)}
.kicker{font:500 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3);display:flex;gap:10px;align-items:center}
.kicker b{color:var(--ink);font-weight:500}
.theme-toggle{position:fixed;top:calc(env(safe-area-inset-top,0px) + 12px);right:16px;z-index:50;font:600 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;padding:7px 11px;border:1px solid var(--line);border-radius:0;background:var(--panel);color:var(--ink);cursor:pointer}
.theme-toggle:hover{border-color:var(--ink)}
.theme-toggle:focus-visible{outline:2px solid var(--hivis);outline-offset:2px}
.mark{width:30px;height:30px;flex:none;display:inline-block;vertical-align:middle;filter:drop-shadow(1.5px 0 0 #ECEEEA) drop-shadow(-1.5px 0 0 #ECEEEA) drop-shadow(0 1.5px 0 #ECEEEA) drop-shadow(0 -1.5px 0 #ECEEEA)}
h1{margin:18px 0 0;font:800 clamp(44px,7.4vw,92px)/1.02 "Big Shoulders Display","Arial Narrow",Impact,sans-serif;text-transform:uppercase;letter-spacing:.005em;text-wrap:balance}
h1 em{font-style:normal;color:var(--ground);background:var(--ink);padding:.02em .1em 0;line-height:1.08;box-decoration-break:clone;-webkit-box-decoration-break:clone}
.lede{margin:18px 0 0;max-width:58ch;color:var(--ink-2);font-size:16.5px}
.facts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;background:var(--line);border:1px solid var(--line)}
.fact{background:var(--panel);padding:14px 14px 12px;display:flex;flex-direction:column;gap:4px}
.fact b{font:800 40px/1 "Big Shoulders Stencil Display","Big Shoulders Display","Arial Narrow",sans-serif;font-variant-numeric:tabular-nums}
.fact span{font-size:12.5px;color:var(--ink-2);line-height:1.3}
.fact.hv b{color:var(--hivis-ink);background:var(--hivis);align-self:flex-start;padding:2px 6px 0}

/* sticky control bar */
.bar{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:color-mix(in srgb,var(--ground) 92%,transparent);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);border-bottom:1px solid var(--line);margin-inline:-16px;padding:10px 16px}
.bar-in{max-width:1120px;margin:0 auto;display:flex;flex-direction:column;gap:10px}
.track{display:flex;gap:4px;overflow-x:auto;scrollbar-width:thin}
.tk{min-width:74px;flex-basis:0;display:flex;flex-direction:column;gap:6px;text-decoration:none;color:var(--ink-2);padding:6px 8px 7px;border-top:3px solid var(--line);background:var(--panel);transition:border-color .2s,color .2s}
.tk:hover,.tk.on{border-top-color:var(--ink);color:var(--ink)}
.tk-top{font:600 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.06em;text-transform:uppercase;display:flex;gap:7px;white-space:nowrap}
.tk-top b{color:var(--ink)}
.tk-dots{display:flex;gap:3px;flex-wrap:wrap}
.d{width:7px;height:7px;background:var(--c);display:block}
.d-op{--c:var(--op);transform:rotate(45deg) scale(.85)}.d-or{--c:var(--or);border-radius:50%}.d-bu{--c:var(--bu)}
.d-rv{--c:var(--rv);clip-path:polygon(50% 0,100% 100%,0 100%)}
.filters{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.filters-l{font:500 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);margin-right:4px}
.flt{font:500 13px/1 "Public Sans",system-ui,sans-serif;color:var(--ink);background:var(--panel);border:1px solid var(--line);padding:6px 10px 6px 8px;display:inline-flex;gap:7px;align-items:center;cursor:pointer;border-radius:999px;transition:background .15s,border-color .15s}
.flt:hover{border-color:var(--c,var(--ink-3))}
.flt[aria-pressed="true"]{background:var(--ink);color:var(--ground);border-color:var(--ink)}
.flt .node{width:13px;height:13px}
.flt[aria-pressed="true"] .node svg{fill:var(--ground)}
.flt-c{font:600 11px/1 "Martian Mono",ui-monospace,monospace;color:var(--ink-3);font-variant-numeric:tabular-nums}
.flt[aria-pressed="true"] .flt-c{color:var(--ground)}
.flt-word{background:var(--hivis);color:var(--hivis-ink);border-color:var(--hivis);font-weight:600}
.flt-word .flt-c{color:var(--hivis-ink);opacity:.7}
.flt-word[aria-pressed="true"]{background:var(--ink);color:var(--hivis);border-color:var(--ink)}

/* stages */
.stage{padding-top:36px}
.sign{display:flex;gap:16px;align-items:stretch;margin-bottom:10px}
.sign-n{flex:none;display:grid;place-items:center;width:64px;min-height:64px;background:var(--ink);color:var(--ground);font:800 46px/1 "Big Shoulders Stencil Display","Big Shoulders Display","Arial Narrow",sans-serif}
.sign h2{margin:4px 0 0;font:800 clamp(28px,4vw,40px)/.95 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;letter-spacing:.01em;text-wrap:balance}
.sign p{margin:6px 0 0;color:var(--ink-2);font-size:14.5px}
.sign-c{font:500 11px/1 "Martian Mono",ui-monospace,monospace;color:var(--ink-3);letter-spacing:.06em;margin-left:6px;white-space:nowrap}

.route{list-style:none;margin:0;padding:0 0 0 0;position:relative}
.route::before{content:"";position:absolute;left:31px;top:0;bottom:0;width:2px;background:repeating-linear-gradient(var(--line) 0 6px,transparent 6px 10px)}
.st{position:relative;display:grid;grid-template-columns:64px minmax(0,1fr);gap:0 16px;padding-block:10px;transition:opacity .2s}
.node{width:22px;height:22px;display:block}
.node svg{width:100%;height:100%;fill:var(--c);display:block}
.st>.node{justify-self:center;margin-top:16px;position:relative;z-index:1;filter:drop-shadow(0 0 0 var(--ground)) drop-shadow(0 0 3px var(--ground))}
.st-body{position:relative;background:var(--panel);border:1px solid var(--line-2);border-left:5px solid var(--c);display:grid;grid-template-columns:62px minmax(0,1fr);align-items:stretch;overflow:hidden}
.st-body::before{content:"";position:absolute;left:62px;right:0;top:0;height:10px;background:radial-gradient(circle at 11px 5px,var(--ground) 0 2.5px,transparent 3px) 0 0/22px 10px repeat-x;opacity:.9}
.st:hover .st-body{border-color:var(--c)}
.st-n{display:flex;align-items:flex-start;justify-content:center;padding-top:14px;background:color-mix(in srgb,var(--c) 14%,var(--panel));border-right:1px dashed var(--line);font:800 34px/1 "Big Shoulders Stencil Display","Big Shoulders Display","Arial Narrow",sans-serif;color:var(--c);font-variant-numeric:tabular-nums}
.st-main{padding:18px 120px 15px 18px;display:flex;flex-direction:column;gap:7px;min-width:0}
.who{position:absolute;top:14px;right:14px;transform:rotate(4deg);border:3px double var(--c);color:var(--c);font:800 14px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;letter-spacing:.14em;text-transform:uppercase;padding:4px 7px 3px;background:var(--panel)}
.st h3{margin:0;font:800 22px/1.05 "Big Shoulders Display","Arial Narrow",sans-serif;letter-spacing:.01em;text-transform:uppercase;text-wrap:balance}
.st p{margin:0;color:var(--ink-2);font-size:14.5px;max-width:66ch}
.word{grid-column:1/-1;display:flex;align-items:stretch;background:var(--hivis);border-top:2px solid var(--hivis-ink);color:var(--hivis-ink)}
.word b{display:flex;align-items:center;background:var(--hivis-ink);color:var(--hivis);font:600 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;padding:8px 10px}
.word span{font:700 14px/1 "Martian Mono",ui-monospace,monospace;padding:8px 12px;display:flex;align-items:center}
.st.has-word .st-body{border-left-color:var(--hivis)}
.tgs{display:flex;flex-wrap:wrap;gap:5px;padding-top:2px}
.tg{font:500 11.5px/1.2 "Martian Mono",ui-monospace,monospace;padding:4px 8px;background:var(--panel-2);color:var(--ink-2);border:1px solid var(--line-2);overflow-wrap:anywhere}
.tg-skill{background:#101316;color:#FBB401;border-color:#101316;font-weight:600}
.tg-agent{color:var(--rv);border-color:var(--rv);background:transparent}
.tg-tool{color:var(--bu);border-color:var(--bu);background:transparent}
.tg-opt{background:transparent;border:1px dashed var(--line);color:var(--ink-3)}
.ret{display:grid;grid-template-columns:64px minmax(0,1fr);gap:16px;padding-block:6px 4px}
.ret-mark{justify-self:center;width:30px;height:30px;display:grid;place-items:center;background:var(--ground);position:relative;z-index:1}
.ret-mark svg{width:24px;height:24px;fill:none;stroke:var(--ink);stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.ret p{margin:0;padding:10px 14px;border-left:3px solid var(--ink);background:var(--panel-2);color:var(--ink-2);font-size:14px}
.ret b{color:var(--ink)}

/* focus mode */
body[data-f] .st{opacity:.22}
body[data-f="op"] .st.a-op,body[data-f="or"] .st.a-or,body[data-f="bu"] .st.a-bu,body[data-f="rv"] .st.a-rv,body[data-f="word"] .st.has-word{opacity:1}

/* the rest */
.aside{margin-top:44px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.card{border-top:3px solid var(--ink);background:var(--panel);padding:16px 18px 18px}
.card h2{margin:0 0 8px;font:800 24px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;letter-spacing:.01em}
.card p{margin:0;color:var(--ink-2);font-size:14.5px}
.card code{font:500 12.5px "Martian Mono",ui-monospace,monospace;color:var(--or)}
footer{margin-top:28px;padding-top:14px;border-top:1px solid var(--line);font:500 11px/1.6 "Martian Mono",ui-monospace,monospace;color:var(--ink-3);letter-spacing:.02em}

@media (max-width:820px){
 .hero{grid-template-columns:1fr;padding-top:32px}
 .route::before{left:19px}
 .st,.ret{grid-template-columns:40px minmax(0,1fr);gap:0 12px}
 .ret{gap:12px}
 .sign-n{width:52px;min-height:52px;font-size:38px}
 .aside{grid-template-columns:1fr}
 .st-body{grid-template-columns:minmax(0,1fr)}
 .st-body>.tgs{grid-column:1;grid-row:auto;justify-content:flex-start;max-width:none}
}
@media (max-width:460px){.fact b{font-size:32px}.tk{min-width:64px}}
"""

JS = r"""
(function(){
 var body=document.body, KEY='foreman-flow-focus';
 var btns=[].slice.call(document.querySelectorAll('[data-f]'));
 function set(f){
  if(f){body.setAttribute('data-f',f)}else{body.removeAttribute('data-f')}
  btns.forEach(function(b){b.setAttribute('aria-pressed',String(b.getAttribute('data-f')===f))});
  try{ if(f){localStorage.setItem(KEY,f)}else{localStorage.removeItem(KEY)} }catch(e){}
 }
 btns.forEach(function(b){b.addEventListener('click',function(){
  var f=b.getAttribute('data-f'); set(body.getAttribute('data-f')===f?null:f);
 })});
 try{ var saved=localStorage.getItem(KEY); if(saved && document.querySelector('[data-f="'+saved+'"]')) set(saved) }catch(e){}
 if('IntersectionObserver' in window){
  var tks={}; [].forEach.call(document.querySelectorAll('.tk'),function(t){tks[t.getAttribute('data-stage')]=t});
  var io=new IntersectionObserver(function(es){es.forEach(function(e){
   if(e.isIntersecting){Object.keys(tks).forEach(function(k){tks[k].classList.toggle('on',k===e.target.getAttribute('data-stage'))})}
  })},{rootMargin:'-35% 0px -60% 0px'});
  [].forEach.call(document.querySelectorAll('.stage'),function(s){io.observe(s)});
 }
})();
"""

page = f"""<title>Topping Out Flow</title><script>try{{var t=localStorage.getItem("foreman-theme");if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t);}}catch(e){{}}</script>{f'<link rel="icon" type="image/png" href="{LOGO}">' if LOGO else ""}
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@700;800&family=Big+Shoulders+Stencil+Display:wght@800&family=Martian+Mono:wght@400;500;600&family=Public+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap">
<style>{CSS}</style>
<div class="wrap">
<button type="button" class="theme-toggle" data-theme-toggle>Light</button>
<header class="hero">
 <div>
  <div class="kicker">{f'<img class="mark" src="{LOGO}" alt="">' if LOGO else ""}<b>Topping Out</b><span>·</span><span>the route, start to finish</span></div>
  <h1>From an idea <em>to the next job</em></h1>
  <p class="lede">A foreman plans and inspects, a builder builds from work orders, readers from another model family check cold, and you give the word for every act that needs it. Seven stages; the build loop repeats once per task, and the whole route once per job.</p>
 </div>
 <div class="facts">
  <div class="fact"><b>{total}</b><span>steps on the route</span></div>
  <div class="fact"><b>2</b><span>inspections before any PR</span></div>
  <div class="fact hv"><b>{len(words)}</b><span>steps wait for your word</span></div>
 </div>
</header>
<nav class="bar" aria-label="Stages and roles"><div class="bar-in">
 <div class="track">{''.join(track_html)}</div>
 <div class="filters"><span class="filters-l">Show</span>{legend}
  <button type="button" class="flt flt-word" id="flt-word" data-f="word" aria-pressed="false">Only my words<span class="flt-c">{len(words)}</span></button></div>
</div></nav>
<main>{''.join(stages_html)}</main>
<div class="aside">
 <section class="card"><h2>The Logbook, now and then</h2><p><code>/f-card</code> for a lesson mid-job. <code>/f-dream</code> to merge duplicates and find repeated mistakes. <code>/f-distill</code> to promote the best cards into rules, on your word. <code>/f-archive</code> past 250 cards; ruled-out options always stay in view.</p></section>
 <section class="card"><h2>Form B: an audition</h2><p>For a builder on trial, stage 2 changes: the builder writes the plan itself as plain steps (<code>WORK-ORDER-2-PLAN.txt</code>) and the foreman judges it at gate 1 (<code>GATE1-REVIEW.md</code>). Everything else on the route stays the same.</p></section>
</div>
<footer>Topping Out · METHOD.md §0–§14 · every skill and agent on this route is mapped in skills-wiki/index.md · roles: ◆ owner · ● foreman · ■ builder · ▲ independent inspector</footer>
</div>
<script>{JS}</script>
<script>(function(){{var r=document.documentElement;function cur(){{var t=r.getAttribute("data-theme");if(t==="light"||t==="dark")return t;return window.matchMedia&&matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";}}document.querySelectorAll("[data-theme-toggle]").forEach(function(b){{function lab(){{var to=cur()==="dark"?"light":"dark";b.textContent=to==="dark"?"Dark":"Light";b.setAttribute("aria-label","Switch to "+to+" mode");b.title="Switch to "+to+" mode";}}lab();b.addEventListener("click",function(){{var n=cur()==="dark"?"light":"dark";r.setAttribute("data-theme",n);try{{localStorage.setItem("foreman-theme",n);}}catch(e){{}}document.querySelectorAll("[data-theme-toggle]").forEach(function(x){{x.dispatchEvent(new Event("relabel"));}});}});b.addEventListener("relabel",lab);}});}})();</script>
"""
OUT.write_text(page, encoding="utf-8", newline="\n")
print("wrote", OUT, total, "steps,", len(words), "words")

#!/usr/bin/env python3
"""Draw the README's pictures (assets/readme/*-dark.webp and *-light.webp) in the site's look.

    python scripts/readme_images.py

Each picture is an HTML page rendered by headless Chrome, then trimmed and saved as WebP. The receipt's
figures are read from README "What a finished job looks like" (the same rows the site's receipt reads),
so a picture never shows a number the README doesn't. Needs Chrome (or Edge) and Pillow.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "readme"
sys.path.insert(0, str(ROOT / "scripts"))
from build_site import ROLE_ICONS  # noqa: E402  (the site's own role hats)

BROWSERS = [os.environ.get("CHROME", ""), r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", "google-chrome", "chromium", "chromium-browser"]

THEMES = {
    "dark": {"ground": "#101316", "panel": "#171B1E", "line": "#2C3337", "ink": "#E7EAE5", "ink2": "#B4BBB6", "ink3": "#808983",
             "ok": "#8FCB7C", "stamp": "#FF7A6E"},
    "light": {"ground": "#ECEEEA", "panel": "#F8F9F6", "line": "#C9CFC7", "ink": "#15181A", "ink2": "#454C50", "ink3": "#727A7E",
              "ok": "#2F6B3A", "stamp": "#C0392B"},
}

FONTS = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@700;800'
         '&family=Martian+Mono:wght@400;600;700&family=Public+Sans:wght@400;600;700&display=swap">')

BASE_CSS = """
*{box-sizing:border-box}html,body{margin:0}
body{background:var(--ground);color:var(--ink);font:400 17px/1.45 "Public Sans",system-ui,sans-serif;padding:28px;width:1260px}
.mono{font-family:"Martian Mono",ui-monospace,monospace}
.disp{font-family:"Big Shoulders Display","Arial Narrow",sans-serif;font-weight:800;text-transform:uppercase}
.stripe{height:10px;background:repeating-linear-gradient(-45deg,#101316 0 10px,#FBB401 10px 20px)}
.lbl{font:600 12px/1.3 "Martian Mono",monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--ink3)}
"""


def css_vars(t):
    return ":root{" + "".join(f"--{k}:{v};" for k, v in THEMES[t].items()) + "}"


def receipt_rows():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    m = re.search(r"^## What a finished job looks like\n\n(.+?)\n\n```text\n(.+?)\n```", text, re.S | re.M)
    if not m:
        raise SystemExit("readme_images: README has no 'What a finished job looks like' text block")
    return dict(re.match(r"(.+?)\s{2,}(.+)", ln).groups() for ln in m.group(2).splitlines() if ln.strip())


def fig(rows, row, pat):
    hit = re.search(pat, rows.get(row, ""))
    if not hit:
        raise SystemExit(f"readme_images: no figure for {row!r} in the README receipt")
    return hit.groups()


# ---------------------------------------------------------------- 1 · the receipt, as an inspection certificate
def receipt_page():
    r = receipt_rows()
    pc = fig(r, "plan check", r"^(\d+) findings.*?(\d+) applied")
    lens = fig(r, "inspect 1", r"(\d+) fixes")
    grep = fig(r, "review", r"Greptile (\d+/\d+)")
    tests = fig(r, "tests", r"(\d+) -> (\d+) passing")
    probes = fig(r, "probes", r"(\d+) of (\d+) mutation")
    spend = fig(r, "spend", r"([\d.]+) USD in paid calls, against a ([\d.]+) USD cap")
    tiles = [
        (f"{pc[0]}", f"plan-check findings from a rival model family, {pc[1]} applied before any code"),
        (f"{lens[0]}", "fixes found by the lens inspectors, all accepted"),
        (("0" if "no findings" in r.get("inspect 2", "") else fig(r, "inspect 2", r"(\d+) findings")[0]),
         "findings from the independent inspector (another family)"),
        (f"{tests[0]}&rarr;{tests[1]}", "tests passing; nothing green at base went red"),
        (f"{probes[0]}/{probes[1]}", "mutation probes caught: each removes a guard, the tests must fail"),
        (f"{grep[0]}", "Greptile review score on the PR"),
    ]
    t = "".join(f'<div class="t"><b class="disp">{a}</b><span>{b}</span></div>' for a, b in tiles)
    return f"""<style>
.card{{background:var(--panel);border:2px solid var(--ink);position:relative;overflow:hidden}}
.hd{{display:flex;justify-content:space-between;align-items:flex-end;padding:22px 28px 14px;border-bottom:2px solid var(--line)}}
.hd h1{{margin:6px 0 0;font-size:54px;line-height:.9}}
.tiles{{display:grid;grid-template-columns:repeat(3,1fr);gap:0}}
.t{{padding:20px 28px 22px;border-right:1px solid var(--line);border-bottom:1px solid var(--line);display:flex;flex-direction:column;gap:6px}}
.t:nth-child(3n){{border-right:0}}
.t b{{font-size:64px;line-height:.9;color:var(--ink)}}
.t span{{color:var(--ink2);font-size:16px;max-width:30ch}}
.ft{{display:flex;justify-content:space-between;gap:20px;padding:16px 28px 18px;font:600 13px/1.4 "Martian Mono",monospace;color:var(--ink2)}}
.ft b{{color:var(--ok)}}
.stamp{{position:absolute;right:34px;top:20px;transform:rotate(-9deg);border:4px solid var(--stamp);color:var(--stamp);padding:8px 16px 6px;
 text-align:center;font:800 34px/1 "Big Shoulders Display",sans-serif;text-transform:uppercase;letter-spacing:.04em;opacity:.92}}
.stamp small{{display:block;font:700 12px/1.4 "Martian Mono",monospace;letter-spacing:.12em}}
</style>
<div class="card"><div class="stripe"></div>
<div class="hd"><div><div class="lbl">Inspection certificate &middot; one real job, ticket to merge, run on its own</div>
<h1 class="disp">Every claim, proven</h1></div></div>
<div class="stamp">Merged<small>tree = reviewed tree</small></div>
<div class="tiles">{t}</div>
<div class="ft"><span>Acceptance ledger: <b>every row PASS</b></span><span>Paid calls: <b>${spend[0]}</b> of a ${spend[1]} cap</span><span>Lessons saved for the next job</span></div>
</div>"""


# ---------------------------------------------------------------- 2 · the crew
CREW = [
    ("you", "Owner: you", "Says <q>go</q> and <q>merge</q>. Or hands over a whole night."),
    ("master", "Master builder", "One strong model plans and builds the job. Every check stays with someone else."),
    ("foreman", "Foreman", "Or split it: the foreman plans, writes work orders and checks every step."),
    ("builder", "Builder", "Builds each work order test-first, on a fast or cheap model. Never makes design calls."),
    ("inspectors", "Inspectors", "Nine lens inspectors, then a rival model family. They find; they never fix."),
]


def crew_page():
    cards = "".join(f'<div class="c{" you" if k == "you" else ""}"><div class="ic">{ROLE_ICONS[k]}</div><b class="disp">{n}</b><span>{d}</span></div>'
                    for k, n, d in CREW)
    return f"""<style>
.row{{display:grid;grid-template-columns:repeat(5,1fr);gap:14px}}
.c{{background:var(--panel);border:2px solid var(--ink);box-shadow:4px 4px 0 var(--ink);padding:18px 18px 20px;display:flex;flex-direction:column;gap:8px}}
.c.you{{background:#FBB401;color:#101316;border-color:#101316;box-shadow:4px 4px 0 #101316}}
.c.you span{{color:#101316}}
.ic svg{{width:84px;height:84px;display:block}}
.c b{{font-size:30px;line-height:1}}
.c span{{color:var(--ink2);font-size:15.5px}}
.top{{display:flex;align-items:baseline;gap:14px;margin:0 0 14px}}
.top h1{{margin:0;font-size:44px;line-height:1}}
</style>
<div class="top"><h1 class="disp">The crew</h1><span class="lbl">Who does what on the site</span></div>
<div class="row">{cards}</div>"""


# ---------------------------------------------------------------- 3 · one job, going up floor by floor
FLOORS = [  # (floor label, what happens, the owner's word on this floor or "")
    ("Top", "<b>Topped out.</b> Lessons saved as cards, the board updated, the next job proposed in a fresh session.", ""),
    ("5", "<b>Pull request.</b> CI runs the whole suite; Greptile reviews up to three rounds, each finding fixed and re-checked.", "merge"),
    ("4", "<b>Proof.</b> Tests before and after, mutation probes, and the acceptance ledger: every requirement PASS.", ""),
    ("3", "<b>Inspection.</b> Nine lens inspectors, then an independent inspector from another model family.", ""),
    ("2", "<b>Frame.</b> Built test-first, one commit per task, each step checked on disk.", ""),
    ("1", "<b>Plan.</b> Written by the master builder (or the foreman), read cold by rival model families before any code.", ""),
    ("G", "<b>Site walk.</b> The ticket, the repo and the handover checked against each other.", "go"),
]


def floors_page():
    rows = "".join(
        f'<div class="fl{" top" if n == "Top" else ""}"><span class="n disp">{n}</span><p>{d}</p>'
        f'{f"<span class=q>&ldquo;{w}&rdquo;</span>" if w else ""}</div>' for n, d, w in FLOORS)
    return f"""<style>
.wrap{{display:grid;grid-template-columns:110px 1fr;gap:0;align-items:end}}
.crane{{height:100%;position:relative}}
.crane svg{{position:absolute;left:0;bottom:0;width:110px;height:100%}}
.bld{{border-left:8px solid var(--ink);border-right:8px solid var(--ink);position:relative}}
.flag{{position:absolute;right:24px;top:-64px}}
.fl{{display:grid;grid-template-columns:64px 1fr auto;align-items:center;gap:18px;padding:14px 20px;border-top:6px solid var(--ink);background:var(--panel)}}
.fl:nth-child(even){{background:var(--ground)}}
.fl .n{{font-size:40px;line-height:1;color:var(--ink3);text-align:center}}
.fl p{{margin:0;color:var(--ink2);font-size:17px}}
.fl p b{{color:var(--ink)}}
.fl.top{{background:#FBB401;border-top-color:#101316}}.fl.top p,.fl.top p b,.fl.top .n{{color:#101316}}
.q{{background:#FBB401;color:#101316;border:2px solid #101316;font:700 16px/1 "Martian Mono",monospace;padding:9px 12px;white-space:nowrap}}
.ground{{height:14px;background:repeating-linear-gradient(-45deg,#101316 0 10px,#FBB401 10px 20px);grid-column:1 / span 2}}
.head{{display:flex;align-items:baseline;gap:14px;margin:0 0 84px}}
.head h1{{margin:0;font-size:44px;line-height:1}}
</style>
<div class="head"><h1 class="disp">One job, floor by floor</h1><span class="lbl">Every job goes up the same way. You give two words.</span></div>
<div class="wrap"><div class="crane"><svg viewBox="0 0 110 600" preserveAspectRatio="none" aria-hidden="true">
<path d="M40 600V40M60 600V40" stroke="var(--ink3)" stroke-width="5"/>
<path d="M40 560L60 520M60 520L40 480M40 480L60 440M60 440L40 400M40 400L60 360M60 360L40 320M40 320L60 280M60 280L40 240M40 240L60 200M60 200L40 160M40 160L60 120M60 120L40 80" stroke="var(--ink3)" stroke-width="3"/>
<path d="M20 40H110" stroke="#FBB401" stroke-width="10"/></svg></div>
<div class="bld"><svg class="flag" width="70" height="64" viewBox="0 0 70 64" aria-hidden="true"><path d="M10 64V4" stroke="var(--ink)" stroke-width="5"/>
<path d="M12 6h50v28H12Z" fill="#FBB401" stroke="#101316" stroke-width="3"/><path d="M28 6L46 34M44 6l18 26" stroke="#101316" stroke-width="7"/></svg>{rows}</div>
<div class="ground"></div></div>"""


# ---------------------------------------------------------------- 4 · keep it current
def update_page():
    steps = [("1", "The end of every job tells you", "the next-job card's &#11014;&#65039; line, or the morning summary after a night shift"),
             ("2", "Between jobs, type <code>/f-setup</code>", "it pulls the newest Topping Out from <code>main</code>"),
             ("3", "It shows what's new", "the changelog entries your install hasn't seen yet"),
             ("4", "It applies them on your yes", "and keeps every file you've adapted")]
    s = "".join(f'<div class="s"><span class="n disp">{n}</span><div><b>{a}</b><span>{b}</span></div></div>' for n, a, b in steps)
    return f"""<style>
.sign{{background:#FBB401;color:#101316;border:3px solid #101316;box-shadow:6px 6px 0 var(--ink);position:relative}}
.sh{{display:flex;align-items:center;gap:22px;padding:22px 28px 18px}}
.sh h1{{margin:0;font-size:58px;line-height:.9}}
.sh p{{margin:6px 0 0;font:600 15px/1.4 "Martian Mono",monospace}}
.cmd{{margin-left:auto;background:#101316;color:#FBB401;font:700 30px/1 "Martian Mono",monospace;padding:16px 22px;white-space:nowrap}}
.steps{{display:grid;grid-template-columns:repeat(4,1fr);border-top:3px solid #101316;background:var(--panel);color:var(--ink)}}
.s{{display:flex;gap:14px;padding:18px 20px 20px;border-right:1px solid var(--line)}}.s:last-child{{border-right:0}}
.s .n{{font-size:44px;line-height:.9;color:#FBB401;-webkit-text-stroke:1.5px var(--ink)}}
.s b{{display:block;font-size:18px;line-height:1.25;margin-bottom:4px}}.s span{{color:var(--ink2);font-size:15px}}
.s code{{font:700 15px "Martian Mono",monospace;white-space:nowrap}}
.arrow{{width:74px;height:74px;flex:none}}
</style>
<div class="sign"><div class="stripe"></div><div class="sh">
<svg class="arrow" viewBox="0 0 74 74" aria-hidden="true"><circle cx="37" cy="37" r="33" fill="#101316"/><path d="M37 56V22M23 35l14-14 14 14" fill="none" stroke="#FBB401" stroke-width="8" stroke-linecap="square"/></svg>
<div><h1 class="disp">Keep it current</h1><p>Topping Out improves almost daily. Updating takes one command, between jobs.</p></div>
<span class="cmd">/f-setup</span></div>
<div class="steps">{s}</div></div>"""


# ---------------------------------------------------------------- 5 · the memory: what every fresh session reads
MEMORY = [
    ("Board", "foreman/projects/&lt;slug&gt;/BOARD.json", "Every job toward the head: done, running, next, and what each needs."),
    ("Handover", "foreman/handovers/", "Where the last job stopped, and the next job's opener, ready to paste."),
    ("Work-session folder", "work-sessions/&lt;month&gt;/Work-&lt;date&gt;/", "Each day's plans, work orders, reports, reviews and ledgers."),
    ("Logbook", "foreman/logbook/", "INSIGHT, METHOD and BUILD cards, searched at every job start. The best become rules."),
]


def memory_page():
    cards = "".join(f'<div class="m{" lb" if n == "Logbook" else ""}"><b class="disp">{n}</b><code>{p}</code><span>{d}</span></div>' for n, p, d in MEMORY)
    return f"""<style>
.top{{display:flex;align-items:baseline;gap:14px;margin:0 0 16px}}.top h1{{margin:0;font-size:44px;line-height:1}}
.g{{display:grid;grid-template-columns:1fr 64px 300px;align-items:stretch;gap:0}}
.files{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.m{{background:var(--panel);border:2px solid var(--ink);box-shadow:4px 4px 0 var(--ink);padding:16px 18px;display:flex;flex-direction:column;gap:6px}}
.m b{{font-size:30px;line-height:1}}.m code{{font:600 13px "Martian Mono",monospace;color:var(--ink3)}}.m span{{color:var(--ink2);font-size:16px}}
.m.lb{{border-color:#FBB401;box-shadow:4px 4px 0 #FBB401}}.m.lb b{{color:#FBB401}}
.ar{{display:flex;align-items:center;justify-content:center}}
.ses{{background:#FBB401;color:#101316;border:3px solid #101316;box-shadow:5px 5px 0 var(--ink);padding:20px 22px;display:flex;flex-direction:column;justify-content:center;gap:10px}}
.ses b{{font-size:40px;line-height:.95}}.ses span{{font-size:17px}}.ses strong{{font:700 14px/1.4 "Martian Mono",monospace;border-top:2px solid #101316;padding-top:10px}}
</style>
<div class="top"><h1 class="disp">Zero context to manage</h1><span class="lbl">Nothing lives in a chat</span></div>
<div class="g"><div class="files">{cards}</div>
<div class="ar"><svg width="56" height="60" viewBox="0 0 56 60" aria-hidden="true"><path d="M4 30h38M30 14l18 16-18 16" fill="none" stroke="var(--ink)" stroke-width="7"/></svg></div>
<div class="ses"><b class="disp">A fresh session, every job</b><span>It reads these files first, so it starts knowing what every job before it learned. Job 100 knows what job 1 learned.</span>
<strong>You manage none of it.</strong></div></div>"""


# ---------------------------------------------------------------- 6 · heads, boards and topping out
def bld(floors, flag, h=150, w=96):
    """A small building: `floors` of 6 drawn, scaffolded above; a flag when topped out."""
    p = [f'<svg width="{w + 20}" height="{h + 40}" viewBox="0 0 {w + 20} {h + 40}" aria-hidden="true">']
    fh = h / 6
    for k in range(6):
        y = 30 + h - (k + 1) * fh
        if k < floors:
            p.append(f'<rect x="10" y="{y:.0f}" width="{w}" height="{fh - 3:.0f}" fill="{"#FBB401" if flag and k == 5 else "var(--panel)"}" stroke="var(--ink)" stroke-width="3"/>')
        else:
            p.append(f'<rect x="10" y="{y:.0f}" width="{w}" height="{fh - 3:.0f}" fill="none" stroke="var(--ink3)" stroke-width="2" stroke-dasharray="5 4"/>')
    if flag:
        p.append(f'<path d="M{w - 4} 30V4" stroke="var(--ink)" stroke-width="3"/><path d="M{w - 3} 5h22v14h-22Z" fill="#FBB401" stroke="#101316" stroke-width="2"/>')
    p.append(f'<path d="M0 {h + 30}h{w + 20}" stroke="var(--ink)" stroke-width="4"/></svg>')
    return "".join(p)


def cycle_page():
    plots = "".join(f'<div class="plot{" pick" if k == 1 else ""}"><span class="mono">{"Head 3 &#10003;" if k == 1 else f"Head {k + 2}?"}</span></div>' for k in range(4))
    return f"""<style>
.top{{display:flex;align-items:baseline;gap:14px;margin:0 0 16px}}.top h1{{margin:0;font-size:44px;line-height:1}}
.row{{display:grid;grid-template-columns:1fr 40px 1fr 40px 1.25fr 40px 1fr;align-items:stretch}}
.st{{background:var(--panel);border:2px solid var(--ink);padding:16px 16px 18px;display:flex;flex-direction:column;gap:8px;align-items:flex-start}}
.st b{{font-size:28px;line-height:1}}.st span{{color:var(--ink2);font-size:15.5px}}
.st .k{{font:700 12px/1 "Martian Mono",monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink3)}}
.st.you{{background:#FBB401;color:#101316;border-color:#101316}}.st.you span,.st.you .k{{color:#101316}}
.ar{{display:flex;align-items:center;justify-content:center;font:800 30px "Martian Mono",monospace;color:var(--ink3)}}
.plots{{display:grid;grid-template-columns:1fr 1fr;gap:8px;width:100%}}
.plot{{border:2px dashed var(--ink3);padding:10px 8px;text-align:center;font-size:13px;color:var(--ink2)}}
.plot.pick{{border:3px solid #101316;background:#101316;font-weight:700}}
.st.you .plot.pick span{{color:#FBB401;font-weight:700}}
.loop{{margin-top:14px;border:2px dashed var(--ink3);border-top:0;height:26px;margin-left:12%;margin-right:12%;position:relative}}
.loop span{{position:absolute;left:50%;bottom:-11px;transform:translateX(-50%);background:var(--ground);padding:0 12px;font:700 13px "Martian Mono",monospace;color:var(--ink2)}}
</style>
<div class="top"><h1 class="disp">Heads, boards and topping out</h1><span class="lbl">How a product grows</span></div>
<div class="row">
<div class="st"><span class="k">1 &middot; The head</span><b class="disp">What it must do</b><span>One outcome you name: &ldquo;a customer can buy a book online.&rdquo;</span></div>
<div class="ar">&rarr;</div>
<div class="st"><span class="k">2 &middot; The board</span>{bld(4, False, 96, 80)}<span>Its jobs, built floor by floor, one PR each.</span></div>
<div class="ar">&rarr;</div>
<div class="st"><span class="k">3 &middot; Topped out</span>{bld(6, True, 96, 80)}<span>The board frozen as the record: what was built, what's carried over, three to five candidate next heads.</span></div>
<div class="ar">&rarr;</div>
<div class="st you"><span class="k">4 &middot; You pick</span><div class="plots">{plots}</div><span>Whenever you're ready. Never picked for you. A new board starts.</span></div>
</div>
<div class="loop"><span>the cycle starts again on a new board</span></div>"""


PAGES = {"receipt": receipt_page, "crew": crew_page, "floors": floors_page, "update": update_page,
         "memory": memory_page, "cycle": cycle_page}


def chrome():
    for b in BROWSERS:
        if b and (Path(b).exists() or shutil.which(b)):
            return b
    raise SystemExit("readme_images: no Chrome or Edge found (set CHROME=<path>)")


def trim(png, bg):
    im = Image.open(png).convert("RGB")
    diff = ImageChops.difference(im, Image.new("RGB", im.size, bg))
    box = diff.getbbox()
    pad = 40
    return im.crop((max(0, box[0] - pad), max(0, box[1] - pad), min(im.width, box[2] + pad), min(im.height, box[3] + pad)))


def main():
    exe, tmp = chrome(), Path(tempfile.mkdtemp())
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        for name, build in PAGES.items():
            body = build()
            for theme in THEMES:
                page = tmp / f"{name}-{theme}.html"
                page.write_text(f'<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>{css_vars(theme)}{BASE_CSS}</style></head>'
                                f'<body>{body}</body></html>', encoding="utf-8")
                png = tmp / f"{name}-{theme}.png"
                subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                                "--window-size=1316,1400", "--virtual-time-budget=6000", f"--screenshot={png}", page.as_uri()],
                               check=True, capture_output=True)
                bg = tuple(int(THEMES[theme]["ground"][i:i + 2], 16) for i in (1, 3, 5))
                trim(png, bg).save(OUT / f"{name}-{theme}.webp", "WEBP", quality=90, method=6)
                print("wrote", (OUT / f"{name}-{theme}.webp").relative_to(ROOT))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

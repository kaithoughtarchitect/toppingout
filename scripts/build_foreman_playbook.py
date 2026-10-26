"""Build the two playbook pages (the package root) from their Markdown: Foreman-Playbook.md and Builder-Playbook.md.

The Markdown is the source. Change it, then run:
    python scripts/build_foreman_playbook.py
Never hand-edit the .html pages; they are overwritten. The look follows DESIGN.md.
"""
import base64
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGO = ROOT / "assets" / "foreman-logo-128.png"

# Section headings in the Markdown -> (anchor, kicker shown above the title)
FOREMAN_KICKERS = {
    "The one idea": ("idea", ""),
    "Before you plan": ("before", "Every job, first"),
    "Planning (the scoping and the plan)": ("planning", "The scoping and the plan"),
    "Writing a work order": ("order", "Check before sending"),
    "Reviewing a work order": ("review", "Disk before words"),
    "When the builder stops": ("stops", "A stop is a gift"),
    "When you write code yourself (the converged case)": ("yourself", "Only when the owner says so"),
    "The end game": ("endgame", "Before the merge"),
    "Talking to the owner": ("owner", "Every reply"),
    "Tool hygiene (small things that cost time)": ("hygiene", "Small things that cost time"),
    "Your own scorecard": ("scorecard", "After each job"),
}
BUILDER_KICKERS = {
    "The one idea": ("idea", ""),
    "Before the job": ("before", "Before work order 1"),
    "Every work order": ("order", "What every work order carries"),
    "Handing work orders over": ("handover", "A pointer, never pasted text"),
    "After every work order": ("after", "Disk before words"),
    "When to switch builders": ("switch", "Only on these two signals"),
    "Where a light builder fits": ("fits", "Settled design, clear tests"),
}
BOOKS = [
    {"src": "Foreman-Playbook.md", "out": "Foreman-Playbook.html", "kickers": FOREMAN_KICKERS,
     "eyebrow": "Topping Out · the foreman's part · any project"},
    {"src": "Builder-Playbook.md", "out": "Builder-Playbook.html", "kickers": BUILDER_KICKERS,
     "eyebrow": "Topping Out · the builder's part · any builder, any project"},
]


def inline(t):
    """Markdown inline -> HTML. Code spans are set aside first (their contents stay literal), so bold and
    italics can run across them, then put back."""
    codes = []

    def keep(m):
        codes.append("<code>" + html.escape(m.group(1)) + "</code>")
        return "@@CODE" + str(len(codes) - 1) + "@@"

    t = re.sub(r"`([^`]+)`", keep, t)
    t = html.escape(t, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", t)
    return re.sub(r"@@CODE(\d+)@@", lambda m: codes[int(m.group(1))], t)


def kind(line):
    if line.startswith("### "):
        return "h3"
    if line.startswith("|"):
        return "table"
    if line.startswith("- [ ] "):
        return "check"
    if re.match(r"\d+\. ", line):
        return "steps"
    if line.startswith("- "):
        return "bullets"
    return "para"


def blocks(lines):
    """Group lines into blocks: a new block starts at a blank line or when the line kind changes."""
    out, cur, ck = [], [], None
    for ln in lines:
        if not ln.strip():
            if cur:
                out.append((ck, cur))
            cur, ck = [], None
            continue
        k = kind(ln)
        if cur and k != ck:
            out.append((ck, cur))
            cur = []
        cur.append(ln)
        ck = k
    if cur:
        out.append((ck, cur))
    return out


def render_block(k, lines):
    if k == "h3":
        return "".join(f'<h3 class="sub">{inline(ln[4:])}</h3>' for ln in lines)
    if k == "table":
        rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines if not re.match(r"^\|[\s|:-]+\|$", ln.strip())]
        head, body = rows[0], rows[1:]
        if len(head) == 2 and all(len(r) == 2 for r in body):
            return ('<ol class="rules">' + "".join(
                f'<li><span class="rn">{i:02d}</span><div class="rt"><div class="rr">{inline(r[0])}</div>'
                f'<div class="rw"><b>{inline(head[1]) or "Why"}</b><span>{inline(r[1])}</span></div></div></li>'
                for i, r in enumerate(body, 1)) + "</ol>")
        th = "".join(f"<th>{inline(c)}</th>" for c in head)
        tb = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body)
        return f'<div class="tw"><table><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table></div>'
    if k == "check":
        return '<ol class="check">' + "".join(f"<li><span>{inline(ln[6:])}</span></li>" for ln in lines) + "</ol>"
    if k == "steps":
        items = [re.sub(r"^\d+\. ", "", ln) for ln in lines]
        return '<ol class="steps">' + "".join(f"<li><span>{inline(t)}</span></li>" for t in items) + "</ol>"
    if k == "bullets":
        return '<ul class="plain">' + "".join(f"<li>{inline(ln[2:])}</li>" for ln in lines) + "</ul>"
    return "".join(f"<p>{inline(ln)}</p>" for ln in lines)


def build(book):
    src, out = ROOT / book["src"], ROOT / book["out"]
    md = src.read_text(encoding="utf-8")
    head, _, rest = md.partition("\n---\n")
    head_lines = [ln for ln in head.splitlines() if ln.strip()]
    title = head_lines[0].lstrip("# ").strip()
    lede, note = head_lines[1], " ".join(head_lines[2:])
    sections = re.split(r"^## ", rest, flags=re.M)[1:]

    nav, body = [], []
    num = 0
    for sec in sections:
        name, _, text = sec.partition("\n")
        name = name.strip()
        text = re.sub(r"\n---\s*$", "", text.strip())
        anchor, kicker = book["kickers"].get(name, (re.sub(r"[^a-z]+", "-", name.lower()).strip("-"), ""))
        short = re.sub(r"\s*\(.*\)$", "", name)
        nav.append(f'<a href="#{anchor}">{html.escape(short)}</a>')
        bl = blocks(text.splitlines())
        if anchor == "idea":
            big = re.sub(r"\*\*", "", bl[0][1][0])
            words = big.split()
            big_html = html.escape(" ".join(words[:3])) + "<br><em>" + html.escape(" ".join(words[3:])) + "</em>"
            inner = "".join(render_block(k, ls) for k, ls in bl[1:]).replace('<ul class="plain">', "<ul>")
            body.append(f'<section id="idea" class="thesis" aria-label="The one idea"><div class="big">{big_html}</div>{inner}</section>')
            continue
        num += 1
        kick = f'<div class="kicker">{html.escape(kicker)}</div>' if kicker else ""
        body.append(f'<section id="{anchor}"><div class="sign"><span class="sn">{num:02d}</span><div>{kick}<h2>{html.escape(short)}</h2></div></div>'
                    + "".join(render_block(k, ls) for k, ls in bl) + "</section>")

    logo = ""
    if LOGO.exists():
        logo = "data:image/png;base64," + base64.b64encode(LOGO.read_bytes()).decode("ascii")
    icon = f'<link rel="icon" type="image/png" href="{logo}">' if logo else ""
    mark = f'<img class="mark" src="{logo}" alt="Topping Out">' if logo else ""
    page = f"""<title>{html.escape(title)}</title>{icon}<script>try{{var t=localStorage.getItem("foreman-theme");if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t);}}catch(e){{}}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@700;800&family=Big+Shoulders+Stencil+Display:wght@800&family=Public+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&family=Martian+Mono:wght@400;500;600&display=swap">
<style>{CSS}</style>

<button type="button" class="theme-toggle" data-theme-toggle>Light</button>
<div class="page">
  <nav class="toc" aria-label="Sections">
    <span class="lab">Playbook</span>
    {"".join(nav)}
  </nav>
  <main>
    <header class="top">
      {mark}
      <span class="eyebrow">{html.escape(book["eyebrow"])}</span>
      <h1>{html.escape(title)}</h1>
      <p class="lede">{inline(lede)}</p>
      <p class="note">{inline(note)}</p>
    </header>
    {"".join(body)}
    <footer>Built from {book['src']} by scripts/build_foreman_playbook.py. Edit the Markdown, not this page.</footer>
  </main>
</div>
<script>(function(){{var r=document.documentElement;function cur(){{var t=r.getAttribute("data-theme");if(t==="light"||t==="dark")return t;return window.matchMedia&&matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";}}document.querySelectorAll("[data-theme-toggle]").forEach(function(b){{function lab(){{var to=cur()==="dark"?"light":"dark";b.textContent=to==="dark"?"Dark":"Light";b.setAttribute("aria-label","Switch to "+to+" mode");b.title="Switch to "+to+" mode";}}lab();b.addEventListener("click",function(){{var n=cur()==="dark"?"light":"dark";r.setAttribute("data-theme",n);try{{localStorage.setItem("foreman-theme",n);}}catch(e){{}}document.querySelectorAll("[data-theme-toggle]").forEach(function(x){{x.dispatchEvent(new Event("relabel"));}});}});b.addEventListener("relabel",lab);}});}})();</script>
"""
    out.write_text(page, encoding="utf-8", newline="\n")
    return out, len(sections)


CSS = r"""
  :root{
    color-scheme:light;
    --ground:#ECEEEA;
    --surface:#F8F9F6;
    --surface-2:#E2E6E0;
    --ink:#15181A;
    --ink-2:#454C50;
    --ink-3:#727A7E;
    --line:#C9CFC7;
    --line-soft:#DADFD8;
    --accent:#946400;
    --accent-soft:rgba(251,180,1,.22);
    --good:#2F6B3A;
    --hivis:#FBB401;
    --hivis-ink:#101316;
    --warn:#A5650F;
    --warn-soft:#F3E4CF;
    --bad:#B3261E;
    --bad-soft:#F4DCD8;
  }
  @media (prefers-color-scheme: dark){
    :root:not([data-theme="light"]){
      color-scheme:dark;
      --ground:#101316; --surface:#171B1E; --surface-2:#1F2427;
      --ink:#E7EAE5; --ink-2:#B4BBB6; --ink-3:#808983;
      --line:#2C3337; --line-soft:#23292C;
      --accent:#FBB401; --accent-soft:rgba(251,180,1,.14); --good:#8FCB7C;
      --warn:#F0B04A; --warn-soft:#2E2213;
      --bad:#F2847A; --bad-soft:#35191A;
    }
  }
  :root[data-theme="dark"]{
    color-scheme:dark;
    --ground:#101316; --surface:#171B1E; --surface-2:#1F2427;
      --ink:#E7EAE5; --ink-2:#B4BBB6; --ink-3:#808983;
      --line:#2C3337; --line-soft:#23292C;
      --accent:#FBB401; --accent-soft:rgba(251,180,1,.14); --good:#8FCB7C;
      --warn:#F0B04A; --warn-soft:#2E2213;
      --bad:#F2847A; --bad-soft:#35191A;
  }

  *{box-sizing:border-box}
  body{
    margin:0; background:var(--ground); color:var(--ink);
    font-family:"Public Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
    font-size:16px; line-height:1.6;
    padding-block:40px 80px; padding-left:16px; padding-right:16px;
    -webkit-font-smoothing:antialiased;
  }
  .page{max-width:1080px;margin:0 auto;display:grid;grid-template-columns:200px minmax(0,1fr);gap:48px}
  @media (max-width:860px){ .page{grid-template-columns:minmax(0,1fr);gap:24px} nav.toc{display:none} }

  nav.toc{position:sticky;top:calc(env(safe-area-inset-top,0px) + 24px);align-self:start;
    font-family:"Martian Mono",ui-monospace,monospace;font-size:12px;display:flex;flex-direction:column;gap:2px}
  nav.toc .lab{letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3);margin-bottom:8px;font-size:11px}
  nav.toc a{color:var(--ink-2);text-decoration:none;padding:5px 0 5px 10px;border-left:2px solid var(--line-soft)}
  nav.toc a:hover,nav.toc a:focus-visible{color:var(--accent);border-left-color:var(--accent);outline:none}

  main{display:flex;flex-direction:column;gap:56px;min-width:0}

  header.top .mark{width:48px;height:48px;filter:drop-shadow(1.5px 0 0 #ECEEEA) drop-shadow(-1.5px 0 0 #ECEEEA) drop-shadow(0 1.5px 0 #ECEEEA) drop-shadow(0 -1.5px 0 #ECEEEA)}
  header.top{display:flex;flex-direction:column;gap:14px;padding-bottom:26px;position:relative}
  header.top::after{content:"";position:absolute;left:0;right:0;bottom:0;height:6px;background:repeating-linear-gradient(-45deg,var(--hivis) 0 9px,var(--hivis-ink) 9px 18px)}
  .eyebrow{font-family:"Martian Mono",monospace;font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);font-weight:600}
  h1{font-family:"Big Shoulders Display","Arial Narrow",sans-serif;font-weight:800;font-size:clamp(40px,7vw,68px);
     line-height:.95;letter-spacing:-.005em;text-transform:uppercase;margin:0;text-wrap:balance}
  .lede{font-size:18.5px;color:var(--ink-2);max-width:62ch;margin:0}
  .note{font-family:"Martian Mono",monospace;font-size:12px;color:var(--ink-3);margin:0}

  h2{font-family:"Big Shoulders Display","Arial Narrow",sans-serif;font-weight:600;font-size:30px;line-height:1.05;
     text-transform:uppercase;letter-spacing:.01em;margin:0 0 6px;text-wrap:balance}
  h3{font-family:"Big Shoulders Display","Arial Narrow",sans-serif;font-weight:600;font-size:21px;text-transform:uppercase;
     letter-spacing:.02em;margin:28px 0 10px}
  section > p{max-width:66ch;margin:0 0 12px;color:var(--ink-2)}
  .kicker{font-family:"Martian Mono",monospace;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3);margin-bottom:4px}

  /* the one idea */
  .thesis{background:#15181A;color:#ECEEEA;border:1px solid var(--line);border-left:6px solid var(--hivis);padding:26px 28px;display:flex;flex-direction:column;gap:14px}
  .thesis .big{font-family:"Big Shoulders Display",sans-serif;font-weight:700;font-size:clamp(30px,5vw,44px);line-height:1;text-transform:uppercase}
  .thesis .big em{font-style:normal;color:var(--hivis)}
    .thesis ul{margin:0;padding-left:18px;display:flex;flex-direction:column;gap:6px;max-width:68ch}
  .thesis li{color:#ECEEEA;opacity:.9}

  /* scorecard */
  .score{background:var(--surface);border:1px solid var(--line);padding:20px 22px;display:flex;flex-direction:column;gap:12px}
  .srow{display:grid;grid-template-columns:minmax(120px,190px) minmax(0,1fr) 34px;gap:14px;align-items:center}
  .sname{font-weight:600;font-size:15px}
  .sname small{display:block;font-weight:400;color:var(--ink-3);font-size:12.5px;line-height:1.35}
  .track{height:10px;background:var(--surface-2);position:relative}
  .track::after{content:"";position:absolute;inset:0;background:
     repeating-linear-gradient(90deg,transparent 0 calc(10% - 1px),var(--line) calc(10% - 1px) 10%)}
  .fill{height:100%;background:var(--good);position:relative;z-index:1}
  .fill.mid{background:var(--warn)} .fill.low{background:var(--bad)}
  .sval{font-family:"Martian Mono",monospace;font-weight:600;text-align:right;font-variant-numeric:tabular-nums}
  .overall{display:flex;flex-wrap:wrap;gap:10px 28px;border-top:1px solid var(--line-soft);padding-top:12px;
     font-family:"Martian Mono",monospace;font-size:12.5px;color:var(--ink-2)}
  .overall b{color:var(--ink);font-weight:600}
  @media (max-width:520px){ .srow{grid-template-columns:minmax(0,1fr) 34px} .track{grid-column:1 / -1;order:3} }

  /* checklists */
  ol.check,ul.check{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:0;border-top:1px solid var(--line)}
  .check li{display:grid;grid-template-columns:28px minmax(0,1fr);gap:12px;padding:12px 0;border-bottom:1px solid var(--line-soft)}
  .check li::before{content:"";width:16px;height:16px;border:2px solid var(--accent);margin-top:4px}
  .check li b{font-weight:600}

  /* rule table */
  .tw{overflow-x:auto;border:1px solid var(--line)}
  table{border-collapse:collapse;width:100%;background:var(--surface);font-size:15px}
  th,td{text-align:left;vertical-align:top;padding:11px 14px;border-bottom:1px solid var(--line-soft)}
  th{font-family:"Martian Mono",monospace;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);font-weight:600;background:var(--surface-2)}
  tbody tr:last-child td{border-bottom:none}
  td:first-child{font-weight:600;min-width:220px}
  td:last-child{color:var(--ink-2)}
  code{font-family:"Martian Mono",monospace;font-size:.86em;background:var(--accent-soft);padding:1px 5px;color:var(--ink)}

  .hostile{background:var(--warn-soft);border-left:4px solid var(--warn);padding:16px 20px}
  .hostile ul{margin:0;padding-left:18px;display:flex;flex-direction:column;gap:7px}
  .target{font-family:"Martian Mono",monospace;font-size:13px;display:flex;flex-wrap:wrap;gap:8px 20px;align-items:baseline;margin-top:14px}
  .target .num{font-size:26px;font-weight:600;color:var(--good)}
  .target .was{font-size:26px;font-weight:600;color:var(--ink-3);text-decoration:line-through}

  /* pointer */
  .pointer{display:flex;gap:0;align-items:stretch;border:1px solid var(--line);background:var(--surface);flex-wrap:wrap}
  .pointer pre{margin:0;padding:14px 16px;font-family:"Martian Mono",monospace;font-size:13px;white-space:pre-wrap;word-break:break-word;flex:1 1 280px}
  .pointer button{font-family:"Martian Mono",monospace;font-size:12px;letter-spacing:.08em;text-transform:uppercase;
     border:0;border-left:1px solid var(--line);background:var(--hivis);color:var(--hivis-ink);font-weight:600;padding:0 18px;cursor:pointer;min-height:44px}
  .pointer button:focus-visible{outline:3px solid var(--warn);outline-offset:2px}

  .switch{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1px;background:var(--line);border:1px solid var(--line)}
  .switch div{background:var(--surface);padding:16px 18px}
  .switch .yes{background:var(--bad-soft)}
  .tag{font-family:"Martian Mono",monospace;font-size:11px;letter-spacing:.12em;text-transform:uppercase;font-weight:600}
  .yes .tag{color:var(--bad)} .no .tag{color:var(--good)}
  .callout{border:1px solid var(--warn);color:var(--ink-2);padding:12px 16px;margin-top:14px;font-size:15px}
  .callout b{color:var(--warn)}

  .fit{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}
  .fit div{border-top:4px solid var(--good);background:var(--surface);padding:14px 16px}
  .fit div.watch{border-top-color:var(--warn)} .fit div.not{border-top-color:var(--bad)}
  .fit p{margin:6px 0 0;color:var(--ink-2)}

  footer{font-family:"Martian Mono",monospace;font-size:12px;color:var(--ink-3);border-top:1px solid var(--line);padding-top:14px;line-height:1.7}
  @media (prefers-reduced-motion:no-preference){ .fill{transition:width .6s ease} }

  /* numbered steps: the order matters, so the number shows */
  ol.steps{list-style:none;margin:0;padding:0;counter-reset:st;border-top:1px solid var(--line)}
  ol.steps li{counter-increment:st;display:grid;grid-template-columns:40px minmax(0,1fr);gap:12px;padding:12px 0;border-bottom:1px solid var(--line-soft)}
  ol.steps li::before{content:counter(st,decimal-leading-zero);font-family:"Big Shoulders Stencil Display","Big Shoulders Display","Arial Narrow",sans-serif;font-size:17px;font-weight:800;line-height:1;color:var(--hivis-ink);background:var(--hivis);align-self:start;justify-self:start;padding:2px 6px;margin-top:3px}
  /* plain lists: a short hi-vis rule, not a checkbox */
  ul.plain{list-style:none;margin:0 0 12px;padding:0;display:flex;flex-direction:column;gap:8px;max-width:72ch}
  ul.plain li{position:relative;padding-left:22px;color:var(--ink-2)}
  ul.plain li::before{content:"";position:absolute;left:0;top:.8em;width:12px;height:3px;background:var(--hivis)}
  section > p + .tw, section > p + ol, section > p + ul{margin-top:4px}
  .thesis p{margin:0;max-width:68ch;color:#ECEEEA;opacity:.92}
  .thesis code{background:rgba(251,180,1,.2);color:#ECEEEA}
  td:first-child{min-width:260px}

.theme-toggle{position:fixed;top:calc(env(safe-area-inset-top,0px) + 12px);right:16px;z-index:50;font:600 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;padding:7px 11px;border:1px solid var(--line);border-radius:0;background:var(--surface);color:var(--ink);cursor:pointer}
.theme-toggle:hover{border-color:var(--ink)}
.theme-toggle:focus-visible{outline:2px solid var(--hivis);outline-offset:2px}

  .sign{display:flex;gap:14px;align-items:stretch;margin:0 0 14px}
  .sign .sn{flex:none;display:grid;place-items:center;width:58px;min-height:58px;background:var(--ink);color:var(--ground);font:800 36px/1 "Big Shoulders Stencil Display","Big Shoulders Display","Arial Narrow",sans-serif}
  .sign .kicker{margin:2px 0 4px}
  .sign h2{margin:0}
  .rules{list-style:none;margin:6px 0 18px;padding:0;display:flex;flex-direction:column;gap:8px}
  .rules li{position:relative;display:grid;grid-template-columns:52px minmax(0,1fr);background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--hivis)}
  .rules li::before{content:"";position:absolute;left:52px;right:0;top:0;height:9px;background:radial-gradient(circle at 10px 4.5px,var(--ground) 0 2.2px,transparent 2.7px) 0 0/20px 9px repeat-x}
  .rules .rn{display:flex;justify-content:center;padding-top:13px;border-right:1px dashed var(--line);font:800 26px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;color:var(--ink-3);font-variant-numeric:tabular-nums}
  .rules .rt{padding:14px 16px 12px;display:flex;flex-direction:column;gap:8px;min-width:0}
  .rules .rr{font-size:15.5px;line-height:1.45;color:var(--ink)}
  .rules .rw{display:flex;gap:10px;align-items:baseline;border-top:1px dashed var(--line);padding-top:8px}
  .rules .rw b{flex:none;font:600 10px/1.4 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
  .rules .rw span{font-size:13.5px;line-height:1.5;color:var(--ink-2)}
  h3.sub{margin:22px 0 8px;font:800 20px/1.1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;letter-spacing:.02em;border-left:4px solid var(--hivis);padding-left:10px}
"""

if __name__ == "__main__":
    for book in BOOKS:
        out, n = build(book)
        print(f"wrote {out} ({n} sections)")

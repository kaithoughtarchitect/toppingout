"""Apply the Topping Out design system to the three picker consoles (Model Council, Agent Council, Plan Check).

Writes one <style id="foreman-system"> block into each console: the Topping Out colour and font tokens under the
consoles' own token names, plus the picker kit (header tag, numbered steps, tiles, card frame, steady cards,
phone wrapping). Layout and behaviour are untouched. Re-running replaces the block, it never stacks.
See DESIGN.md. Run: python scripts/picker_style.py
"""
import re
from pathlib import Path

R = Path(__file__).resolve().parent.parent / "skills"
FILES = ["model-council/model-council-console.html", "agent-council/scripts/agent-council-console.html",
         "f-plancheck/plancheck-console.html"]

FONTS = ('<link href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@700;800'
         '&family=Big+Shoulders+Stencil+Display:wght@800&family=Martian+Mono:wght@400;500;600&family=Public+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">')

OVERRIDE = """<style id="foreman-system">
/* Topping Out design system: concrete and asphalt, hi-vis amber, square edges (matches board, flow, atlas) */
:root {
  --bg: #ECEEEA; --bg-canvas: #E2E6E0; --panel: #F8F9F6; --panel-soft: #F1F3EF;
  --line: #DADFD8; --line-strong: #C9CFC7; --line-solid: #C9CFC7;
  --text: #15181A; --copy: #2E3437; --muted: #6A7276; --muted-strong: #454C50;
  --brand: #946400; --brand-strong: #6E4A00; --brand-soft: rgba(251,180,1,.18); --brand-border: rgba(148,100,0,.55);
  --on-brand: #101316; --hivis: #FBB401; --hivis-ink: #101316;
  --secondary: #1D4E89; --secondary-strong: #163C6A; --secondary-soft: rgba(29,78,137,.10); --secondary-border: rgba(29,78,137,.35);
  --pass: #2F6B3A; --warn: #A5650F; --fail: #B3261E;
  --focus-ring: rgba(29,78,137,.6); --selection: rgba(251,180,1,.3);
  --card-shadow: none; --card-shadow-hover: 0 0 0 1px var(--text);
  --r-sm: 0; --r: 0; --r-lg: 0;
  --sans: "Public Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --body: "Public Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: "Martian Mono", ui-monospace, Consolas, monospace;
  --display: "Big Shoulders Display", "Arial Narrow", Impact, sans-serif;
}
:root[data-theme="dark"] {
  --bg: #101316; --bg-canvas: #0C0F11; --panel: #171B1E; --panel-soft: #1F2427;
  --line: #23292C; --line-strong: #2C3337; --line-solid: #2C3337;
  --text: #E7EAE5; --copy: #C9D0CB; --muted: #808983; --muted-strong: #B4BBB6;
  --brand: #FBB401; --brand-strong: #FFC93D; --brand-soft: rgba(251,180,1,.13); --brand-border: rgba(251,180,1,.55);
  --on-brand: #101316;
  --secondary: #80AFE9; --secondary-strong: #A6C7F0; --secondary-soft: rgba(128,175,233,.12); --secondary-border: rgba(128,175,233,.35);
  --pass: #8FCB7C; --warn: #F0B04A; --fail: #F2847A;
  --focus-ring: rgba(128,175,233,.6); --selection: rgba(251,180,1,.25);
  --card-shadow: none; --card-shadow-hover: 0 0 0 1px var(--brand);
}
body { background: var(--bg); }
.topbar { backdrop-filter: none; background: var(--bg); border-bottom: 1px solid var(--line-strong); }
.topbar::after { content: ""; position: absolute; left: 0; right: 0; bottom: -5px; height: 4px;
  background: repeating-linear-gradient(-45deg, var(--hivis) 0 8px, var(--hivis-ink) 8px 16px); pointer-events: none; }
.brand-title { font-family: var(--display); font-weight: 800; font-size: 1.35rem; letter-spacing: .02em; text-transform: uppercase; }
.page-kicker { letter-spacing: .14em; }
.page-title { font-family: var(--display); font-weight: 800; font-size: clamp(2.4rem, 4.4vw, 3.4rem);
  line-height: .95; letter-spacing: 0; text-transform: uppercase; text-wrap: balance; }
h2, h3, .section-title { letter-spacing: 0; }
/* ── Topping Out picker kit: one header, one section style, one tile, one card frame for all three pickers ── */
/* header: TOPPING OUT wordmark, then the picker's name as a square tag; chip values in caps */
.brand-title { display: flex; align-items: center; gap: 10px; }
.brand-kicker { font-family: var(--mono) !important; font-size: .66rem !important; font-weight: 600 !important; letter-spacing: .12em !important;
  text-transform: uppercase !important; color: var(--brand) !important; background: var(--brand-soft) !important;
  border: 1px solid var(--brand-border) !important; border-radius: 0 !important; padding: 3px 7px 2px !important; line-height: 1.2 !important; }
.meta-tag { border-radius: 0 !important; }
.meta-tag b { text-transform: uppercase; }
.btn-ghost, .btn-primary, .btn-inspect { border-radius: 0 !important; }
/* the main action is the hat: hi-vis fill, outline-dark text, in both themes */
.btn-primary { background: var(--hivis) !important; color: var(--hivis-ink) !important; border: 1px solid var(--hivis) !important; font-weight: 700 !important; }
.btn-primary:disabled { opacity: .45 !important; cursor: not-allowed; }
.brand-kicker { white-space: nowrap; }
/* a closed drawer casts no shadow onto the page edge */
.drawer:not(.open) { box-shadow: none !important; }
/* phone: the top bar and the dock wrap instead of running off the side */
@media (max-width: 720px) {
  .topbar { height: auto !important; flex-wrap: wrap; row-gap: 8px; padding: 10px 16px !important; }
  .top-meta-group { order: 3; width: 100%; flex-wrap: wrap; row-gap: 6px; }
  .topbar .spacer { display: none; }
  .top-actions { margin-left: auto; }
  .dock-content { flex-wrap: wrap; row-gap: 10px; }
  .dock-actions { width: 100%; justify-content: flex-end; }
  .section-head { flex-wrap: wrap; }
}

/* page: numbered work-order steps */
main.app-shell { counter-reset: step; padding-bottom: 120px; }
main.app-shell > section { counter-increment: step; margin-top: 34px; }
.page-lede { max-width: 72ch; }
.section-head { display: flex; align-items: baseline; gap: 14px; margin-bottom: 12px; border-bottom: 1px solid var(--line-strong); padding-bottom: 8px; }
.section-title-wrap { display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; }
.section-title { font-family: var(--display) !important; font-weight: 800 !important; font-size: 1.55rem !important; text-transform: uppercase;
  letter-spacing: .01em !important; color: var(--text); display: flex; align-items: baseline; gap: 10px; }
.section-title::before { content: counter(step, decimal-leading-zero); font-family: var(--mono); font-size: .72rem; font-weight: 600;
  color: var(--on-brand); background: var(--hivis); padding: 3px 6px 2px; position: relative; top: -3px; }
.section-desc { color: var(--muted) !important; font-size: .86rem !important; }
.section-count { margin-left: auto; display: flex; align-items: center; gap: 10px; border: 0 !important; background: none !important; padding: 0 !important; border-radius: 0 !important; }
.section-count b { font-family: var(--mono); font-size: .8rem; color: var(--text); font-weight: 600; }
.slots { display: flex; gap: 3px; }
.slots i { width: 22px; height: 10px; background: var(--line-strong); }
.slots i.on { background: var(--hivis); }
.note, .structural-note-box { border-radius: 0 !important; }

/* tiles: the number is the headline, the chosen one carries a hi-vis bar */
.tile-grid, .quorum-protagonist-grid { gap: 10px !important; margin: 0 !important; }
.tile, .quorum-tile { border-radius: 0 !important; border: 1px solid var(--line-strong) !important; background: var(--panel) !important; box-shadow: none !important; position: relative; }
.tile { padding: 16px 18px 15px !important; gap: 4px !important; }
.quorum-tile { padding: 16px 18px !important; min-height: 76px; align-items: center !important; }
.tile-count, .quorum-tile-number { font-family: var(--display) !important; font-weight: 800 !important; color: var(--text) !important; letter-spacing: 0 !important; text-transform: uppercase; }
.tile-count { font-size: 2.6rem !important; line-height: .9 !important; }
.quorum-tile-number { font-size: 1.9rem !important; line-height: 1 !important; }
.tile-name, .quorum-tile-tag { font-family: var(--mono) !important; letter-spacing: .14em !important; text-transform: uppercase; color: var(--muted) !important; font-size: .68rem !important; font-weight: 600 !important; }
.tile-name { color: var(--brand) !important; }
.tile:hover, .quorum-tile:hover { border-color: var(--text) !important; }
.tile[aria-pressed="true"], .quorum-tile.active { background: var(--brand-soft) !important; border-color: var(--hivis) !important; box-shadow: inset 0 4px 0 var(--hivis) !important; }
.quorum-tile.active .quorum-tile-tag { color: var(--brand) !important; }

/* the fixed roles (chair, host, player, auditor slot): one quiet bar with a blue edge */
.chair, .structural-card { border-radius: 0 !important; box-shadow: none !important; border: 1px solid var(--line-strong) !important; border-left: 4px solid var(--secondary) !important; background: var(--panel) !important; }
.structural-card.auditor-active { border-left-color: var(--secondary) !important; background: var(--secondary-soft) !important; }
.structural-badge-tag { border-radius: 0 !important; font-family: var(--mono) !important; letter-spacing: .1em !important; }
.structural-card .structural-note-box { background: none !important; border: 0 !important; padding: 0 !important; font-family: var(--body) !important;
  font-size: .86rem !important; color: var(--muted-strong) !important; }
section > .structural-note-box { background: var(--panel) !important; border: 1px solid var(--line) !important; border-left: 4px solid var(--hivis) !important;
  font-family: var(--body) !important; font-size: .84rem !important; color: var(--copy) !important; padding: 10px 14px !important; }

/* cards: one frame. Square, hairline, the state as a solid tag top-right, a footer strip on a hairline */
:where(button, a, [role="button"], .model-card, .tile, .quorum-tile, .card):is(:hover, :active, :focus, :focus-visible) { transform: none !important; }
.model-card, .card { transition: border-color .12s ease, background-color .12s ease !important; }
.matrix-grid, .card-grid { grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)) !important; gap: 10px !important; align-items: stretch; }
.matrix-grid { grid-auto-rows: 1fr; }
.model-card { border-radius: 0 !important; border: 1px solid var(--line-strong) !important; box-shadow: none !important; background: var(--panel) !important;
  padding: 14px 16px 0 !important; gap: 10px !important; opacity: 1 !important; filter: none !important; }
.model-card:hover { border-color: var(--text) !important; }
.card-logo { border-radius: 0 !important; }
.card-name { font-family: var(--sans) !important; font-weight: 700 !important; font-size: 1rem !important; letter-spacing: 0 !important; }
.card-role-state { font-family: var(--mono) !important; font-size: .66rem !important; font-weight: 600 !important; letter-spacing: .1em !important; padding: 3px 7px 2px; }
.selected-panel .card-role-state { background: var(--hivis); color: var(--on-brand) !important; }
.selected-auditor .card-role-state { background: var(--secondary); color: var(--bg) !important; }
.vendor-collision .card-role-state { color: var(--fail) !important; padding-right: 0; }
.model-card.selected-panel { background: var(--brand-soft) !important; border-color: var(--hivis) !important; box-shadow: inset 0 0 0 1px var(--hivis) !important; }
.model-card.selected-auditor { background: var(--secondary-soft) !important; border-color: var(--secondary) !important; box-shadow: inset 0 0 0 1px var(--secondary) !important; }
.model-card.vendor-collision, .model-card[aria-disabled="true"] { background: var(--panel-soft) !important; }
.model-card[aria-disabled="true"] { cursor: not-allowed; }
.model-card.vendor-collision > :not(.card-top), .model-card.vendor-collision .card-identity,
.model-card[aria-disabled="true"] > :not(.card-top), .model-card[aria-disabled="true"] .card-identity { opacity: .4; }
/* prices: a plain spec strip, no inner box */
.card-specs { border: 0 !important; background: none !important; border-radius: 0 !important; padding: 0 !important; gap: 14px !important; }
.spec-label { font-family: var(--mono) !important; font-size: .6rem !important; letter-spacing: .12em !important; text-transform: uppercase; color: var(--muted) !important; }
.spec-val { font-family: var(--mono) !important; font-size: .86rem !important; font-weight: 600 !important; color: var(--text) !important; }
.door-chip { border: 0 !important; background: none !important; padding: 0 !important; border-radius: 0 !important; font-family: var(--mono) !important;
  font-size: .72rem !important; color: var(--muted-strong) !important; letter-spacing: .06em !important; }
/* footer strip */
.card-bottom { margin: auto -16px 0 !important; padding: 0 16px !important; height: 40px; display: flex; align-items: center; justify-content: space-between;
  border-top: 1px solid var(--line); }
.selected-panel .card-bottom { border-top-color: var(--brand-border); }
.effort-control { border-radius: 0 !important; border: 1px solid var(--line-strong) !important; background: none !important; padding: 0 !important; gap: 0 !important; }
.effort-btn { border-radius: 0 !important; font-family: var(--mono) !important; font-size: .66rem !important; letter-spacing: .08em; text-transform: uppercase; padding: 4px 9px !important; }
.effort-btn.active { background: var(--hivis) !important; color: var(--on-brand) !important; box-shadow: none !important; }
.effort-chip-fixed { border-radius: 0 !important; font-family: var(--mono) !important; letter-spacing: .1em; }
.btn-inspect { font-family: var(--mono) !important; font-size: .66rem !important; letter-spacing: .12em !important; }

/* site details, as on the board: stencilled numbers, site notices */
.tile-count, .quorum-tile-number { font-family: "Big Shoulders Stencil Display", var(--display) !important; }
.section-title::before { font-family: "Big Shoulders Stencil Display", var(--display); font-size: 1rem; font-weight: 800; line-height: 1; padding: 4px 6px 2px; top: -4px; }
.note, section > .structural-note-box { background: var(--hivis) !important; color: var(--hivis-ink) !important; border: 2px solid var(--hivis-ink) !important;
  border-left-width: 2px !important; font-weight: 500; }
.note b, .note strong, section > .structural-note-box b { color: var(--hivis-ink) !important; }
</style>"""

# The same theme choice as every other Topping Out page: a saved `foreman-theme` wins, applied before paint;
# with none saved the system setting decides. The consoles' own Mode button keeps working; this only
# saves what it chose.
THEME = """<script id="foreman-theme">(function(){var r=document.documentElement,K="foreman-theme";
try{var t=localStorage.getItem(K);if(t==="light"||t==="dark")r.setAttribute("data-theme",t);
else if(window.matchMedia&&matchMedia("(prefers-color-scheme: light)").matches)r.setAttribute("data-theme","light");}catch(e){}
document.addEventListener("click",function(e){if(e.target&&e.target.closest&&e.target.closest("#themeBtn"))
setTimeout(function(){try{localStorage.setItem(K,r.getAttribute("data-theme"));}catch(x){}},0);},true);})();</script>"""

for rel in FILES:
    p = R / rel
    s = p.read_text(encoding="utf-8")
    s, n1 = re.subn(r'<link href="https://fonts\.googleapis\.com/css2\?family=Geist\+Mono[^"]*" rel="stylesheet">\s*'
                    r'<link href="https://api\.fontshare\.com/[^"]*" rel="stylesheet">', FONTS, s)
    # a console already on the Topping Out fonts gets the current link (it may predate the stencil cut)
    s = re.sub(r'<link href="https://fonts\.googleapis\.com/css2\?family=Big\+Shoulders\+Display[^"]*" rel="stylesheet">', FONTS, s)
    s = re.sub(r'\n?<style id="foreman-system">.*?</style>', "", s, flags=re.S)
    s = re.sub(r'\n?<script id="foreman-theme">.*?</script>', "", s, flags=re.S)
    i = s.index("</head>")
    s = s[:i] + OVERRIDE + "\n" + THEME + "\n" + s[i:]
    assert n1 == 1 or FONTS in s, (rel, n1)
    p.write_text(s, encoding="utf-8", newline="\n")
    print(rel, "fonts", n1)

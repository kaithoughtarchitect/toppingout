"""Build docs/, the Topping Out website (the method whose roles are the foreman, the builder and the inspectors). Every page sits in one shell: a site-plan sidebar (a drawing
index, one sheet per page) beside the page itself. The generated pages (the route, the Atlas, both
playbooks, the board) are copied unchanged into docs/raw/ and shown inside a sheet of their own, so
they get the site's navigation without being edited. Skill facts come from the Skill Atlas data
(skills-wiki + each SKILL.md); the extra sections on a skill or agent page come from
docs/content/<skills|agents>/<name>.md. The front page's copy lives here, in FRONT.
Edit the sources, never the pages this writes.

Usage: python scripts/build_site.py
"""

from __future__ import annotations

import html
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_foreman_playbook import inline  # noqa: E402
import build_foreman_playbook as PBK  # noqa: E402  (the playbooks' own Markdown reader, reused as is)
from wiki_graph_html import TEMPLATE as ATLAS_TEMPLATE, build_data, logo_uri  # noqa: E402

ROOT = SCRIPTS.parent
OUT = ROOT / "docs"
# the custom domain GitHub Pages serves docs/ at; written to docs/CNAME on every build, since the build clears docs/
DOMAIN = "toppingout.dev"
SITE_URL = "https://" + DOMAIN + "/"
# the link preview (1200x630, dark), drawn from the front page's own headline by foreman-site-tools/og-card.mjs
OG_CARD = "assets/brand/og-card.png"
CONTENT = OUT / "content"  # skills/<name>.md and agents/<name>.md

# the generated pages, copied unchanged into docs/raw/: (raw name, source)
RAW = {
    "route": ("raw/route.html", "flow.html"),
    "atlas": ("raw/atlas.html", "skills-wiki/graph.html"),
    "foreman": ("raw/foreman-playbook.html", "Foreman-Playbook.html"),
    "builder": ("raw/builder-playbook.html", "Builder-Playbook.html"),
    "board": ("raw/board.html", "examples/example-board/board.html"),
}
# the site plan: one sheet per page, in this order
SHEETS = [
    ("index.html", "Start"),
    ("route.html", "Order of works"),
    ("repo.html", "Your repo"),
    ("logbook.html", "Logbook"),
    ("skills.html", "Skills and agents"),
    ("atlas.html", "Skill Atlas"),
    ("playbooks.html", "Playbooks"),
    ("board.html", "Example board"),
    ("requirements.html", "Requirements"),
]
# Brand marks for the requirements sheet, from Simple Icons (CC0): one 24x24 path each.
BRAND_PI = ('M420 280H280V140H0V0H420V280Z', 'M560 560H420V280H560V560Z', 'M140 560H0V140H140V280H280V420H140V560Z')
BRAND_MARKS = {
    'windows': 'M0,0H11.377V11.372H0ZM12.623,0H24V11.372H12.623ZM0,12.623H11.377V24H0Zm12.623,0H24V24H12.623',
    'claude': 'm4.7144 15.9555 4.7174-2.6471.079-.2307-.079-.1275h-.2307l-.7893-.0486-2.6956-.0729-2.3375-.0971-2.2646-.1214-.5707-.1215-.5343-.7042.0546-.3522.4797-.3218.686.0608 1.5179.1032 2.2767.1578 1.6514.0972 2.4468.255h.3886l.0546-.1579-.1336-.0971-.1032-.0972L6.973 9.8356l-2.55-1.6879-1.3356-.9714-.7225-.4918-.3643-.4614-.1578-1.0078.6557-.7225.8803.0607.2246.0607.8925.686 1.9064 1.4754 2.4893 1.8336.3643.3035.1457-.1032.0182-.0728-.164-.2733-1.3539-2.4467-1.445-2.4893-.6435-1.032-.17-.6194c-.0607-.255-.1032-.4674-.1032-.7285L6.287.1335 6.6997 0l.9957.1336.419.3642.6192 1.4147 1.0018 2.2282 1.5543 3.0296.4553.8985.2429.8318.091.255h.1579v-.1457l.1275-1.706.2368-2.0947.2307-2.6957.0789-.7589.3764-.9107.7468-.4918.5828.2793.4797.686-.0668.4433-.2853 1.8517-.5586 2.9021-.3643 1.9429h.2125l.2429-.2429.9835-1.3053 1.6514-2.0643.7286-.8196.85-.9046.5464-.4311h1.0321l.759 1.1293-.34 1.1657-1.0625 1.3478-.8804 1.1414-1.2628 1.7-.7893 1.36.0729.1093.1882-.0183 2.8535-.607 1.5421-.2794 1.8396-.3157.8318.3886.091.3946-.3278.8075-1.967.4857-2.3072.4614-3.4364.8136-.0425.0304.0486.0607 1.5482.1457.6618.0364h1.621l3.0175.2247.7892.522.4736.6376-.079.4857-1.2142.6193-1.6393-.3886-3.825-.9107-1.3113-.3279h-.1822v.1093l1.0929 1.0686 2.0035 1.8092 2.5075 2.3314.1275.5768-.3218.4554-.34-.0486-2.2039-1.6575-.85-.7468-1.9246-1.621h-.1275v.17l.4432.6496 2.3436 3.5214.1214 1.0807-.17.3521-.6071.2125-.6679-.1214-1.3721-1.9246L14.38 17.959l-1.1414-1.9428-.1397.079-.674 7.2552-.3156.3703-.7286.2793-.6071-.4614-.3218-.7468.3218-1.4753.3886-1.9246.3157-1.53.2853-1.9004.17-.6314-.0121-.0425-.1397.0182-1.4328 1.9672-2.1796 2.9446-1.7243 1.8456-.4128.164-.7164-.3704.0667-.6618.4008-.5889 2.386-3.0357 1.4389-1.882.929-1.0868-.0062-.1579h-.0546l-6.3385 4.1164-1.1293.1457-.4857-.4554.0608-.7467.2307-.2429 1.9064-1.3114Z',
    'git': 'M13.09 23.549a1.54 1.54 0 0 1-2.18 0L.451 13.089a1.54 1.54 0 0 1 0-2.179l7.191-7.19 2.733 2.733a1.85 1.85 0 0 0 .964 2.326v6.66a1.849 1.849 0 1 0 1.54 0V8.957l2.508 2.508a1.85 1.85 0 1 0 1.09-1.09l-2.634-2.634a1.85 1.85 0 0 0-2.378-2.377L8.73 2.63 10.91.451a1.54 1.54 0 0 1 2.179 0l10.459 10.46a1.54 1.54 0 0 1 0 2.179z',
    'github': 'M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12',
    'nodedotjs': 'M11.998,24c-0.321,0-0.641-0.084-0.922-0.247l-2.936-1.737c-0.438-0.245-0.224-0.332-0.08-0.383 c0.585-0.203,0.703-0.25,1.328-0.604c0.065-0.037,0.151-0.023,0.218,0.017l2.256,1.339c0.082,0.045,0.197,0.045,0.272,0l8.795-5.076 c0.082-0.047,0.134-0.141,0.134-0.238V6.921c0-0.099-0.053-0.192-0.137-0.242l-8.791-5.072c-0.081-0.047-0.189-0.047-0.271,0 L3.075,6.68C2.99,6.729,2.936,6.825,2.936,6.921v10.15c0,0.097,0.054,0.189,0.139,0.235l2.409,1.392 c1.307,0.654,2.108-0.116,2.108-0.89V7.787c0-0.142,0.114-0.253,0.256-0.253h1.115c0.139,0,0.255,0.112,0.255,0.253v10.021 c0,1.745-0.95,2.745-2.604,2.745c-0.508,0-0.909,0-2.026-0.551L2.28,18.675c-0.57-0.329-0.922-0.945-0.922-1.604V6.921 c0-0.659,0.353-1.275,0.922-1.603l8.795-5.082c0.557-0.315,1.296-0.315,1.848,0l8.794,5.082c0.57,0.329,0.924,0.944,0.924,1.603 v10.15c0,0.659-0.354,1.273-0.924,1.604l-8.794,5.078C12.643,23.916,12.324,24,11.998,24z M19.099,13.993 c0-1.9-1.284-2.406-3.987-2.763c-2.731-0.361-3.009-0.548-3.009-1.187c0-0.528,0.235-1.233,2.258-1.233 c1.807,0,2.473,0.389,2.747,1.607c0.024,0.115,0.129,0.199,0.247,0.199h1.141c0.071,0,0.138-0.031,0.186-0.081 c0.048-0.054,0.074-0.123,0.067-0.196c-0.177-2.098-1.571-3.076-4.388-3.076c-2.508,0-4.004,1.058-4.004,2.833 c0,1.925,1.488,2.457,3.895,2.695c2.88,0.282,3.103,0.703,3.103,1.269c0,0.983-0.789,1.402-2.642,1.402 c-2.327,0-2.839-0.584-3.011-1.742c-0.02-0.124-0.126-0.215-0.253-0.215h-1.137c-0.141,0-0.254,0.112-0.254,0.253 c0,1.482,0.806,3.248,4.655,3.248C17.501,17.007,19.099,15.91,19.099,13.993z',
    'python': 'M14.25.18l.9.2.73.26.59.3.45.32.34.34.25.34.16.33.1.3.04.26.02.2-.01.13V8.5l-.05.63-.13.55-.21.46-.26.38-.3.31-.33.25-.35.19-.35.14-.33.1-.3.07-.26.04-.21.02H8.77l-.69.05-.59.14-.5.22-.41.27-.33.32-.27.35-.2.36-.15.37-.1.35-.07.32-.04.27-.02.21v3.06H3.17l-.21-.03-.28-.07-.32-.12-.35-.18-.36-.26-.36-.36-.35-.46-.32-.59-.28-.73-.21-.88-.14-1.05-.05-1.23.06-1.22.16-1.04.24-.87.32-.71.36-.57.4-.44.42-.33.42-.24.4-.16.36-.1.32-.05.24-.01h.16l.06.01h8.16v-.83H6.18l-.01-2.75-.02-.37.05-.34.11-.31.17-.28.25-.26.31-.23.38-.2.44-.18.51-.15.58-.12.64-.1.71-.06.77-.04.84-.02 1.27.05zm-6.3 1.98l-.23.33-.08.41.08.41.23.34.33.22.41.09.41-.09.33-.22.23-.34.08-.41-.08-.41-.23-.33-.33-.22-.41-.09-.41.09zm13.09 3.95l.28.06.32.12.35.18.36.27.36.35.35.47.32.59.28.73.21.88.14 1.04.05 1.23-.06 1.23-.16 1.04-.24.86-.32.71-.36.57-.4.45-.42.33-.42.24-.4.16-.36.09-.32.05-.24.02-.16-.01h-8.22v.82h5.84l.01 2.76.02.36-.05.34-.11.31-.17.29-.25.25-.31.24-.38.2-.44.17-.51.15-.58.13-.64.09-.71.07-.77.04-.84.01-1.27-.04-1.07-.14-.9-.2-.73-.25-.59-.3-.45-.33-.34-.34-.25-.34-.16-.33-.1-.3-.04-.25-.02-.2.01-.13v-5.34l.05-.64.13-.54.21-.46.26-.38.3-.32.33-.24.35-.2.35-.14.33-.1.3-.06.26-.04.21-.02.13-.01h5.84l.69-.05.59-.14.5-.21.41-.28.33-.32.27-.35.2-.36.15-.36.1-.35.07-.32.04-.28.02-.21V6.07h2.09l.14.01zm-6.47 14.25l-.23.33-.08.41.08.41.23.33.33.23.41.08.41-.08.33-.23.23-.33.08-.41-.08-.41-.23-.33-.33-.23-.41-.08-.41.08z',
    'openrouter': 'M16.778 1.844v1.919q-.569-.026-1.138-.032-.708-.008-1.415.037c-1.93.126-4.023.728-6.149 2.237-2.911 2.066-2.731 1.95-4.14 2.75-.396.223-1.342.574-2.185.798-.841.225-1.753.333-1.751.333v4.229s.768.108 1.61.333c.842.224 1.789.575 2.185.799 1.41.798 1.228.683 4.14 2.75 2.126 1.509 4.22 2.11 6.148 2.236.88.058 1.716.041 2.555.005v1.918l7.222-4.168-7.222-4.17v2.176c-.86.038-1.611.065-2.278.021-1.364-.09-2.417-.357-3.979-1.465-2.244-1.593-2.866-2.027-3.68-2.508.889-.518 1.449-.906 3.822-2.59 1.56-1.109 2.614-1.377 3.978-1.466.667-.044 1.418-.017 2.278.02v2.176L24 6.014Z',
    'gnubash': 'M21.038,4.9l-7.577-4.498C13.009,0.134,12.505,0,12,0c-0.505,0-1.009,0.134-1.462,0.403L2.961,4.9 C2.057,5.437,1.5,6.429,1.5,7.503v8.995c0,1.073,0.557,2.066,1.462,2.603l7.577,4.497C10.991,23.866,11.495,24,12,24 c0.505,0,1.009-0.134,1.461-0.402l7.577-4.497c0.904-0.537,1.462-1.529,1.462-2.603V7.503C22.5,6.429,21.943,5.437,21.038,4.9z M15.17,18.946l0.013,0.646c0.001,0.078-0.05,0.167-0.111,0.198l-0.383,0.22c-0.061,0.031-0.111-0.007-0.112-0.085L14.57,19.29 c-0.328,0.136-0.66,0.169-0.872,0.084c-0.04-0.016-0.057-0.075-0.041-0.142l0.139-0.584c0.011-0.046,0.036-0.092,0.069-0.121 c0.012-0.011,0.024-0.02,0.036-0.026c0.022-0.011,0.043-0.014,0.062-0.006c0.229,0.077,0.521,0.041,0.802-0.101 c0.357-0.181,0.596-0.545,0.592-0.907c-0.003-0.328-0.181-0.465-0.613-0.468c-0.55,0.001-1.064-0.107-1.072-0.917 c-0.007-0.667,0.34-1.361,0.889-1.8l-0.007-0.652c-0.001-0.08,0.048-0.168,0.111-0.2l0.37-0.236 c0.061-0.031,0.111,0.007,0.112,0.087l0.006,0.653c0.273-0.109,0.511-0.138,0.726-0.088c0.047,0.012,0.067,0.076,0.048,0.151 l-0.144,0.578c-0.011,0.044-0.036,0.088-0.065,0.116c-0.012,0.012-0.025,0.021-0.038,0.028c-0.019,0.01-0.038,0.013-0.057,0.009 c-0.098-0.022-0.332-0.073-0.699,0.113c-0.385,0.195-0.52,0.53-0.517,0.778c0.003,0.297,0.155,0.387,0.681,0.396 c0.7,0.012,1.003,0.318,1.01,1.023C16.105,17.747,15.736,18.491,15.17,18.946z M19.143,17.859c0,0.06-0.008,0.116-0.058,0.145 l-1.916,1.164c-0.05,0.029-0.09,0.004-0.09-0.056v-0.494c0-0.06,0.037-0.093,0.087-0.122l1.887-1.129 c0.05-0.029,0.09-0.004,0.09,0.056V17.859z M20.459,6.797l-7.168,4.427c-0.894,0.523-1.553,1.109-1.553,2.187v8.833 c0,0.645,0.26,1.063,0.66,1.184c-0.131,0.023-0.264,0.039-0.398,0.039c-0.42,0-0.833-0.114-1.197-0.33L3.226,18.64 c-0.741-0.44-1.201-1.261-1.201-2.142V7.503c0-0.881,0.46-1.702,1.201-2.142l7.577-4.498c0.363-0.216,0.777-0.33,1.197-0.33 c0.419,0,0.833,0.114,1.197,0.33l7.577,4.498c0.624,0.371,1.046,1.013,1.164,1.732C21.686,6.557,21.12,6.411,20.459,6.797z',
    'powershell': 'M23.181 2.974c.568 0 .923.463.792 1.035l-3.659 15.982c-.13.572-.697 1.035-1.265 1.035H.819c-.568 0-.923-.463-.792-1.035L3.686 4.009c.13-.572.697-1.035 1.265-1.035zm-8.375 9.346c.251-.394.227-.905-.09-1.243L9.122 5.125c-.38-.404-1.037-.407-1.466-.003-.429.402-.468 1.056-.088 1.46l4.662 4.96v.11l-7.42 5.374c-.45.327-.533.977-.187 1.453.346.476.991.597 1.44.27l8.229-5.91c.28-.196.438-.365.514-.52zm-2.796 4.399a.928.928 0 00-.934.923c0 .51.418.923.934.923h4.433a.928.928 0 00.934-.923.928.928 0 00-.934-.923z',
}


# The site's own copy of the Skill Atlas. skills-wiki/graph.html belongs to the development session and is never
# edited here: the build copies it into docs/raw/ and makes these changes to the copy only, so it fits beside the site
# plan (drawn a little smaller rather than cut off) and its group labels wrap instead of trailing off. Each change must
# find its text exactly once; if the Atlas changes at its source, the build stops and says which one to look at.
ATLAS_SITE_EDITS = [('<h2>From sketch to sign-off</h2>', '<h2>From sketch to sign&#8209;off</h2>'), ('COLW=Math.max(MINCOL,Math.floor((stage.clientWidth-PADX*2+40)/cols.length))', 'COLW=Math.max(MINCOL,Math.floor((stage.clientWidth-PADX*2)/cols.length))'), ('  groups.filter(g=>g.family===f).forEach(g=>{g.x=x;g.y=y+4;y+=18;g.ids.forEach(id=>{pos[id]={x:x+8,y:y+8};y+=ROW});y+=GAP});', '  groups.filter(g=>g.family===f).forEach(g=>{g.x=x;g.y=y+4;g.lines=lblLines(g);y+=18+12*(g.lines.length-1);g.ids.forEach(id=>{pos[id]={x:x+8,y:y+8};y+=ROW});y+=GAP});'), (' const W=PADX*2+cols.length*COLW-40;\n svg.setAttribute("width",W);svg.setAttribute("height",H+10);svg.setAttribute("viewBox","0 0 "+W+" "+(H+10))}', ' const W=PADX*2+cols.length*COLW;\n svg.setAttribute("viewBox","0 0 "+W+" "+(H+10));svg.dataset.w=W;svg.dataset.h=H+10;fit()}\nfunction fit(){const W=+svg.dataset.w,Hh=+svg.dataset.h,k=Math.min(1,stage.clientWidth/W),z=k>=.72?k:1;svg.setAttribute("width",Math.floor(W*z));svg.setAttribute("height",Math.ceil(Hh*z))}'), ('function layout(){', 'const lblText=g=>g.name.split(":")[0].replace(/\\s*\\(.*\\)\\s*$/,"").replace(/^The /,"");\nfunction lblLines(g){const m=document.createElementNS(NS,"text");m.setAttribute("class","grp-lbl");svg.appendChild(m);const room=COLW-34,fits=s=>{m.textContent=s;return m.getComputedTextLength()<=room};\n const full=lblText(g);let out=[full];if(!fits(full)){const w=full.split(" ");let a=w.slice();while(a.length>1&&!fits(a.join(" ")))a.pop();out=[a.join(" "),w.slice(a.length).join(" ")]}\n svg.removeChild(m);return out}\nfunction layout(){'), ('t.textContent=g.name.split(":")[0].replace(/\\s*\\(.*\\)\\s*$/,"").replace(/^The /,"");svg.appendChild(t);lbls.push(t)});', 'g.lines.forEach((ln,k)=>{const sp=document.createElementNS(NS,"tspan");sp.setAttribute("x",g.x);if(k)sp.setAttribute("dy",12);sp.textContent=ln;t.appendChild(sp)});svg.appendChild(t);lbls.push(t)});'), (' fitLbls();if(document.fonts&&document.fonts.ready)document.fonts.ready.then(fitLbls);\n', ''), ('let rz;window.addEventListener("resize",()=>{clearTimeout(rz);rz=setTimeout(()=>{const was=COLW;layout();if(COLW!==was){build();paint()}},120)});', 'if(document.fonts&&document.fonts.ready)document.fonts.ready.then(()=>{build();paint()});\nlet rz;window.addEventListener("resize",()=>{clearTimeout(rz);rz=setTimeout(()=>{build();paint()},120)});')]


ATLAS_SITE_EXTRA = r"""<style>
/* the site's scrollbars here too */
html{scrollbar-color:#646C70 transparent}*{scrollbar-width:thin}
/* the site copy: each link drawn in the colour of the stage it leaves; a picked link still turns ink */
.edge.c-plan{stroke:var(--plan)}.edge.c-run{stroke:var(--run)}.edge.c-inspect{stroke:var(--inspect)}.edge.c-close{stroke:var(--close)}.edge.c-kit{stroke:var(--kit)}
.edge[class*="c-"]{stroke-opacity:.55;stroke-width:1.5}
svg.has-sel .edge.hot{stroke-opacity:1}
/* the route player */
.legend .play{margin-left:auto;display:inline-flex;align-items:center;gap:8px;font:700 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;
 padding:8px 12px;border:2px solid #101316;background:#101316;color:#FBB401;cursor:pointer}
.legend .play:hover,.legend .play:focus-visible{background:#FBB401;color:#101316}
.legend .play[aria-pressed="true"]{background:#FBB401;color:#101316}
:root[data-theme="dark"] .legend .play{border-color:#FBB401}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .legend .play{border-color:#FBB401}}
.legend .pstep{font:600 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.08em;color:var(--ink-3);min-width:9ch}
.legend .pbar{width:120px;height:6px;background:var(--line);overflow:hidden}.legend .pbar i{display:block;height:100%;width:0;background:#FBB401;transition:width .4s}
.node.sel .shape{animation:route-pulse 1.1s ease-out 1}
@keyframes route-pulse{0%{stroke-width:9}100%{stroke-width:2.4}}
@media (prefers-reduced-motion:reduce){.node.sel .shape{animation:none}}
</style>
<script>(function(){var svg=document.getElementById("g"),leg=document.getElementById("legend"),det=document.getElementById("detail");if(!svg||!leg||!det)return;
/* colour every link by the stage of the skill it leaves, again whenever the map is redrawn */
function fam(id){id=id.split("/").pop();var g=[].filter.call(svg.querySelectorAll("g.node"),function(n){return (n.getAttribute("aria-label")||"").split(",")[0]===id})[0];
 var m=g&&/f-(\w+)/.exec(g.getAttribute("class")||"");return m?m[1]:""}
function tint(){var cache={};[].forEach.call(svg.querySelectorAll("path.edge"),function(e){var a=e.getAttribute("data-a")||(e.dataset&&e.dataset.a);if(!a)return;
 var f=cache[a]||(cache[a]=fam(a));if(f&&!e.classList.contains("c-"+f))e.classList.add("c-"+f)})}
/* the group labels are drawn before the links; lift them on top after every redraw so their halo hides the lines behind them */
function lift(){var l=svg.querySelectorAll("text.grp-lbl");if(!l.length||svg.lastElementChild.classList.contains("grp-lbl"))return;[].forEach.call(l,function(t){svg.appendChild(t)})}
tint();lift();new MutationObserver(function(){tint();lift()}).observe(svg,{childList:true});
/* play the route: step through the route's skills in order, each lit on the map with its docket open */
var order=[].map.call(det.querySelectorAll(".sb[data-id]"),function(b){return b.getAttribute("data-id")});if(!order.length)return;
var b=document.createElement("button"),st=document.createElement("span"),bar=document.createElement("span");b.type="button";b.className="play";b.setAttribute("aria-pressed","false");b.textContent="\u25B6 Play the route";
st.className="pstep";bar.className="pbar";bar.innerHTML="<i></i>";st.hidden=bar.hidden=true;leg.appendChild(b);leg.appendChild(st);leg.appendChild(bar);
var k=-1,t=0,auto=false,STEP=2000;
function node(id){return [].filter.call(svg.querySelectorAll("g.node"),function(n){return (n.getAttribute("aria-label")||"").split(",")[0]===id})[0]}
function sel(){var s=svg.querySelector("g.node.sel");return s?(s.getAttribute("aria-label")||"").split(",")[0]:null}
function go(id){if(sel()===id)return;var x=det.querySelector('[data-id="'+id+'"]');auto=true;if(x)x.click();else{var n=node(id);n&&n.dispatchEvent(new MouseEvent("click",{bubbles:true}))}auto=false}
function show(i){k=i;go(order[i]);st.textContent="Step "+(i+1)+" of "+order.length;bar.firstChild.style.width=(100*(i+1)/order.length)+"%";
 var n=node(order[i]),stage=document.getElementById("stage");if(n&&stage){var r=n.getBoundingClientRect(),s=stage.getBoundingClientRect();if(r.top<s.top||r.bottom>s.bottom)stage.scrollTop+=r.top-s.top-s.height/3}}
function stop(clear){clearTimeout(t);if(k<0)return;k=-1;b.textContent="\u25B6 Play the route";b.setAttribute("aria-pressed","false");st.hidden=bar.hidden=true;if(clear){var s=sel();if(s){auto=true;var n=node(s);n&&n.dispatchEvent(new MouseEvent("click",{bubbles:true}));auto=false}}}
function tick(){if(k<0)return;if(k+1<order.length){show(k+1);t=setTimeout(tick,STEP)}else t=setTimeout(function(){stop(true)},STEP)}
b.addEventListener("click",function(){if(k>=0){stop(false);return}b.textContent="\u25A0 Stop";b.setAttribute("aria-pressed","true");st.hidden=bar.hidden=false;show(0);t=setTimeout(tick,STEP)});
/* the reader takes over the moment they pick anything themselves */
document.addEventListener("click",function(e){if(k>=0&&!auto&&e.isTrusted&&!b.contains(e.target))stop(false)},true);
})()</script>"""


# The About page: who drew the plans. Draft text, for the owner to rework; floors marked "tbw" are placeholders.
ABOUT = {
    "name": "Kai Thought Architect",
    "line": "I build AI coding systems.",
    "intro": "I'm Kai, the thought architect. For nearly three years I've been building systems that let AI write code without me babysitting it. Every one of them was built on the lessons of the one before. This is how they stack up.",
    "links": [("GitHub", "https://github.com/kaithoughtarchitect"), ("Reddit", "https://www.reddit.com/user/Kai_ThoughtArchitect/")],
    # the systems, newest first: (name, when, what it taught, placeholder?)
    # (name, when, what it changed, why it was needed, placeholder?, link)
    "floors": [
        ("Topping Out", "now, first called Foreman", "Split the work by trust: a foreman decides, a cheap model builds, another model family checks.", "Specialist teams were costly, and still checked by one model family.", False, ""),
        ("Journeyman", "2026", "Turned one agent into a team of specialists, and had every plan read cold before building.", "A single agent was marking its own homework.", False, ""),
        ("Noderr", "summer 2025", "Handed the bookkeeping to the AI, and traced every change through everything it touched.", "Maps and trackers kept by hand drifted away from the code.", False, "https://github.com/kaithoughtarchitect/noderr"),
        ("Pathfinder", "spring 2025", "Drew the whole app as a map, gave each part a spec, and marked nothing done until verified.", "So the AI could build fast without the app losing its shape.", False, ""),
    ],
    "next": "Topping Out is the latest floor, not the last. Each system so far has been built on the one below it, and the next will be built on this one.",
}


def about_floors() -> str:
    out = []
    total = len(ABOUT["floors"])
    for k, (name, when, what, why, tbw, url) in enumerate(ABOUT["floors"]):
        no = total - k
        out.append(f'<li class="fl{" top" if k == 0 else ""}{" tbw" if tbw else ""}"><span class="flno">Floor {no:02d}</span>'
                   f'<div class="flb"><b>{esc(name)}</b>' + ("" if tbw else f'<span class="flw">{esc(when)}</span>') + f'<p>{esc(what)}</p><p class="flwhy"><b>Why</b>{esc(why)}' + (f' <a class="flurl" href="{esc(url)}" rel="noopener" target="_blank">On GitHub &#8599;</a>' if url else "") + '</p></div>'
                   + ('<em class="tbwtag">To be written</em>' if tbw else "") + "</li>")
    return "".join(out)


def atlas_site_copy(text: str) -> str:
    for i, (old, new) in enumerate(ATLAS_SITE_EDITS, 1):
        if text.count(old) != 1:
            raise SystemExit(f"build_site: the Skill Atlas changed at its source; site edit {i} of {len(ATLAS_SITE_EDITS)} no longer applies: {old[:60]!r}")
        text = text.replace(old, new)
    return text + ATLAS_SITE_EXTRA


def brand_mark(m: str, colour: str) -> str:
    """A tool's logo: a raster or SVG file in assets/brands/ ("img:name"), the Pi blocks, or a Simple Icons path."""
    if m and m.startswith("img:"):
        return f'<span class="lg img"><img src="assets/brands/{m[4:] if "." in m else m[4:] + ".png"}" alt="" width="52" height="52"></span>'
    if m == "pi":
        return '<span class="lg"><svg viewBox="0 0 560 560" aria-hidden="true">' + "".join(f'<path class="pi" d="{d}"/>' for d in BRAND_PI) + "</svg></span>"
    if m:
        fill = "" if not colour else ' fill="' + colour + '"'
        return f'<span class="lg{"" if colour else " mono"}"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="{BRAND_MARKS[m]}"{fill}/></svg></span>'
    return '<span class="lg ini" style="background:#5B6368" aria-hidden="true">+</span>'


def sheet_no(page: str) -> str:
    """A sheet's number on the site plan, two digits."""
    return f"{[h for h, _ in SHEETS].index(page) + 1:02d}"


def _hat(fill: str, prop: str) -> str:
    return ('<svg class="ri" viewBox="0 0 48 48" aria-hidden="true" focusable="false">'
            f'<path d="M9 30C9 18 16 11 24 11S39 18 39 30Z" fill="{fill}" stroke="#101316" stroke-width="2.4" stroke-linejoin="round"/>'
            f'<path d="M21 11.6V30M27 11.6V30" stroke="#101316" stroke-width="2" opacity=".35"/>'
            f'<rect x="5" y="29.5" width="38" height="5.5" fill="{fill}" stroke="#101316" stroke-width="2.4" stroke-linejoin="round"/>'
            f'{prop}</svg>')


ROLE_ICONS = {
    # the foreman: white hat, a pencil for the work orders
    "foreman": _hat("#F4F4EF", '<g transform="rotate(-40 37 39)"><rect x="28" y="36" width="16" height="6" fill="#FBB401" stroke="#101316" stroke-width="2"/>'
                    '<path d="M44 36l5 3-5 3Z" fill="#E9D7B0" stroke="#101316" stroke-width="2" stroke-linejoin="round"/></g>'),
    # the builder: hat yellow, a brick
    "builder": _hat("#FBB401", '<rect x="27" y="35" width="17" height="9" fill="#C8553D" stroke="#101316" stroke-width="2.2"/>'
                    '<path d="M27 39.5h17M35.5 35v4.5" stroke="#101316" stroke-width="1.6"/>'),
    # the inspectors: the inspection scan's green, a magnifier
    "inspectors": _hat("#3FAE6A", '<circle cx="35" cy="38" r="6" fill="#DDEFE3" stroke="#101316" stroke-width="2.4"/>'
                       '<path d="M39.5 42.5l5 5" stroke="#101316" stroke-width="3.2" stroke-linecap="round"/>'),
    # the owner: no hat, a rubber stamp; giving the word
    "you": ('<svg class="ri" viewBox="0 0 48 48" aria-hidden="true" focusable="false">'
            '<path d="M19 8h10v6c0 3 4 5 4 9H15c0-4 4-6 4-9Z" fill="#101316"/>'
            '<rect x="10" y="23" width="28" height="7" fill="#101316"/>'
            '<rect x="7" y="34" width="34" height="9" fill="none" stroke="#101316" stroke-width="2.4"/>'
            '<path d="M13 38.5l3 3 6-6" fill="none" stroke="#101316" stroke-width="2.6" stroke-linecap="square"/>'
            '<path d="M25 38.5h11" stroke="#101316" stroke-width="2.6"/></svg>'),
}

# GitHub's mark (Octicons mark-github), for the link to the repo
GH_MARK = ("M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94"
           "-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07"
           "-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27"
           " 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07"
           "-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z")

# Why Topping Out, as four safety signs bolted to the site hoarding. Each pictogram acts its pillar out
# on a loop: the builder fills in only what the foreman drew; a scan rejects a bad block; a tower tops
# out overnight; the site diary turns its pages. CSS keyframes only; the resting frame (what reduced
# motion shows) is always the finished picture.
SIGNS = [
    ("blue", "Build only what is drawn",
     '<circle cx="100" cy="66" r="60" fill="#1F5FA8"/>'
     '<path d="M86 34c0-9 6-14 14-14s14 5 14 14Z" fill="#fff"/><rect x="82" y="33" width="36" height="4.5" fill="#fff"/>'
     '<path d="M100 40v12" stroke="#fff" stroke-width="2.5" stroke-dasharray="3 3"/>'
     '<rect x="52" y="56" width="96" height="40" fill="none" stroke="#fff" stroke-width="2" stroke-dasharray="4 3" opacity=".75"/>'
     + "".join(f'<rect class="brk" style="animation-delay:{k * 0.32:.2f}s" x="{x}" y="{y}" width="22" height="11" fill="#fff"/>'
               for k, (x, y) in enumerate([(54, 83), (78, 83), (102, 83), (126, 83), (66, 70), (90, 70), (114, 70), (54, 58), (78, 58), (102, 58), (126, 58)]))
     + '<text x="100" y="114" text-anchor="middle" class="tag" fill="#fff">BUILDER</text>'),
    ("yellow", "Inspection zone",
     '<path d="M100 8L190 122H10Z" fill="#FBB401" stroke="#101316" stroke-width="7" stroke-linejoin="round"/>'
     '<path d="M46 106h108" stroke="#101316" stroke-width="3"/>'
     '<rect x="54" y="86" width="20" height="20" fill="#101316"/><rect x="78" y="86" width="20" height="20" fill="#101316"/>'
     '<rect class="bad" x="102" y="86" width="20" height="20" fill="#101316"/>'
     '<rect class="fresh" x="102" y="86" width="20" height="20" fill="#101316"/>'
     '<rect x="126" y="86" width="20" height="20" fill="#101316"/>'
     '<g class="beam"><rect x="46" y="58" width="5" height="52" fill="#1E9E57"/><path d="M48.5 54l-6-8h12Z" fill="#101316"/></g>'
     '<text x="100" y="78" text-anchor="middle" class="tag stamp" fill="#C42B1C">REJECTED</text>'),
    ("night", "Works continue overnight",
     '<rect width="200" height="130" fill="#14233B"/>'
     '<g class="sky"><circle cx="100" cy="30" r="10" fill="#F4E9C8"/><circle cx="104" cy="27" r="9" fill="#14233B"/></g>'
     + "".join(f'<circle class="star" style="animation-delay:{d}s" cx="{x}" cy="{y}" r="1.4" fill="#fff"/>'
               for x, y, d in [(22, 18, 0), (48, 40, 1.1), (160, 22, .5), (182, 48, 1.7), (140, 12, 2.3), (30, 60, .8)])
     + '<path d="M0 122h200" stroke="#2C3E5A" stroke-width="16"/>'
     '<rect x="72" y="70" width="56" height="44" fill="#2A3A52"/>'
     + "".join(f'<rect class="win w{n}" x="{x}" y="{y}" width="10" height="7" fill="#FBB401"/>'
               for n, y in ((1, 102), (2, 88), (3, 74)) for x in (78, 95, 112))
     + "".join(f'<text x="64" y="{y + 7}" text-anchor="end" class="tag job j{n}" fill="#FBB401">J{10 + n}</text>' for n, y in ((1, 102), (2, 88), (3, 74)))
     + '<g class="flag"><path d="M100 70V52" stroke="#E7EAE5" stroke-width="2"/><path d="M101 52h14l-4 4 4 4h-14Z" fill="#3FAE6A"/></g>'),
    ("green", "Site diary kept at all times",
     '<rect width="200" height="130" fill="#1E7B4A"/>'
     '<path d="M40 30h58v74H44c-2 0-4-2-4-4Z" fill="#fff"/><path d="M160 30h-58v74h54c2 0 4-2 4-4Z" fill="#fff"/>'
     '<path d="M100 28v78" stroke="#0F4D2C" stroke-width="3"/>'
     + "".join(f'<path d="M50 {y}h40M110 {y}h40" stroke="#1E7B4A" stroke-width="3" opacity=".55"/>' for y in (44, 54, 64, 74, 84))
     + '<path class="pg" d="M102 30h56v74h-56Z" fill="#E6F2EA" stroke="#0F4D2C" stroke-width="1.5"/>'
     '<g class="cd"><rect x="112" y="8" width="38" height="24" fill="#FBB401" stroke="#101316" stroke-width="2"/><path d="M118 16h26M118 23h18" stroke="#101316" stroke-width="2.5"/></g>'
     '<text x="100" y="122" text-anchor="middle" class="tag" fill="#fff">LOGBOOK · HANDOVER</text>'),
]

# The skeptic's queries as stickers on the site office door: (short sticker text, sticker style), in the
# order of FRONT["skeptic"]. The full question, the response and the evidence show on the notice beside it.
STICKERS = [
    ("One agent for the lot?", "st-yel"),
    ("Why not just better prompts?", "st-red"),
    ("Why does it need my OK?", "st-wht"),
    ("Isn't it slow and costly?", "st-haz"),
    ("Am I locked in?", "st-grn"),
    ("What if it breaks at night?", "st-oct"),
    ("What if the builder cuts corners?", "st-tape"),
    ("Will it fit my project?", "st-blu"),
    ("Mac or Linux?", "st-note"),
]

# The route's walker: one small worker who walks the per-ticket loop, stops at each step in the hat of
# whoever does it, says a word, and walks back round for the next job. A quip per loop step, same order
# as FRONT["route_loop"].
WALK_SAYS = ["Clocking on", "One work order", "Two inspections", "Your go, or /goal", "Fixing findings", "Merged!", "Topped out!"]

WALKER = r"""<div class="walker" aria-hidden="true"><span class="bub"></span><svg viewBox="0 0 28 40" class="wk">
<path class="hat" d="M7 10C7 5 10 2 14 2s7 3 7 8Z" stroke="#101316" stroke-width="1.6"/><rect class="hat" x="5" y="9" width="18" height="3" stroke="#101316" stroke-width="1.6"/>
<circle cx="14" cy="15.5" r="3.6" fill="#E8C4A0" stroke="#101316" stroke-width="1.4"/>
<path d="M8.5 20h11l1 10h-13Z" fill="#FBB401" stroke="#101316" stroke-width="1.5"/><path d="M8.2 25h11.6" stroke="#ECEEEA" stroke-width="1.6"/>
<path class="arm a1" d="M9 21l-3 7" stroke="#101316" stroke-width="2.2" stroke-linecap="round"/><path class="arm a2" d="M19 21l3 7" stroke="#101316" stroke-width="2.2" stroke-linecap="round"/>
<path class="leg l1" d="M11.5 30l-1 9" stroke="#2C3337" stroke-width="2.8" stroke-linecap="round"/><path class="leg l2" d="M16.5 30l1 9" stroke="#2C3337" stroke-width="2.8" stroke-linecap="round"/>
</svg></div><script>(function(){
var loop=document.currentScript.parentNode,w=loop.querySelector(".walker"),bub=w.querySelector(".bub"),fig=w.querySelector(".wk");
var WHO=__WHO__,SAYS=__SAYS__,HAT={foreman:"#F4F4EF",builder:"#FBB401",inspectors:"#3FAE6A",you:"#E0442F"};
var still=!!(window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches),on=true,pts=[],seg=0,u=0,last=0,wait=0,dir=1;
function hat(c){[].forEach.call(w.querySelectorAll(".hat"),function(h){h.setAttribute("fill",c)})}
function measure(){var lr=loop.getBoundingClientRect(),mk=loop.querySelectorAll(".loop .phs .mk");pts=[];
 [].forEach.call(mk,function(m){var r=m.getBoundingClientRect();pts.push({x:r.left+r.width/2-lr.left,y:r.top-lr.top,stop:pts.length})});
 if(!pts.length)return;var right=lr.width-2,bottom=lr.height-14;
 pts.push({x:right,y:pts[0].y},{x:right,y:bottom},{x:2,y:bottom},{x:2,y:pts[0].y})}
function place(x,y){w.style.transform="translate("+(x-18)+"px,"+(y-50)+"px)"}
function say(i){if(i==null){bub.textContent="";w.classList.remove("talk");return}bub.textContent=SAYS[i];w.classList.add("talk");hat(HAT[WHO[i]]||HAT.foreman)}
function frame(t){if(!on){last=0;return}if(window.walkPaused){last=t;w.classList.remove("walking");requestAnimationFrame(frame);return}var dt=last?Math.min(60,t-last):16;last=t;
 if(!pts.length){requestAnimationFrame(frame);return}
 if(wait>0){wait-=dt;w.classList.remove("walking");if(wait<=0)say(null);requestAnimationFrame(frame);return}
 var a=pts[seg],b=pts[(seg+1)%pts.length],dx=b.x-a.x,dy=b.y-a.y,len=Math.max(1,Math.hypot(dx,dy));
 u+=dt*0.075/len;w.classList.add("walking");if(Math.abs(dx)>1){dir=dx>0?1:-1;fig.style.transform="scaleX("+dir+")"}
 if(u>=1){u=0;seg=(seg+1)%pts.length;var p=pts[seg];place(p.x,p.y);if(p.stop!=null){say(p.stop);wait=1500;if(window.walkHook)window.walkHook(p.stop)}if(seg===0)hat(HAT.foreman)}
 else place(a.x+dx*u,a.y+dy*u);
 requestAnimationFrame(frame)}
function reset(){measure();if(pts.length){seg=0;u=0;place(pts[0].x,pts[0].y);say(0);wait=1500}}
var ro;if(window.ResizeObserver){ro=new ResizeObserver(function(){measure();if(pts.length){var p=pts[seg];place(p.x,p.y)}});ro.observe(loop)}
reset();if(still){w.classList.remove("walking");return}
if(window.IntersectionObserver)new IntersectionObserver(function(es){var v=es[0].isIntersecting;if(v&&!on){on=true;requestAnimationFrame(frame)}else if(!v)on=false}).observe(loop);
requestAnimationFrame(frame)})()</script>"""

RULE_ICONS = ['<svg viewBox="0 0 40 40" aria-hidden="true"><path d="M12 2h16l10 10v16L28 38H12L2 28V12Z" fill="#C42B1C" stroke="#101316" stroke-width="2"/><text x="20" y="24.5" text-anchor="middle" font-family="Big Shoulders Display,Arial Narrow,sans-serif" font-weight="800" font-size="13" fill="#fff">STOP</text></svg>', '<svg viewBox="0 0 40 40" aria-hidden="true"><rect x="2" y="2" width="36" height="36" fill="#1E7B4A" stroke="#101316" stroke-width="2"/><path d="M10 21l7 7 13-15" fill="none" stroke="#fff" stroke-width="4.5" stroke-linecap="square"/></svg>', '<svg viewBox="0 0 40 40" aria-hidden="true"><circle cx="20" cy="20" r="17" fill="#fff" stroke="#C42B1C" stroke-width="5"/><path d="M8 8l24 24" stroke="#C42B1C" stroke-width="5"/></svg>', '<svg viewBox="0 0 40 40" aria-hidden="true"><circle cx="20" cy="20" r="18" fill="#1F5FA8" stroke="#101316" stroke-width="2"/><text x="20" y="25.5" text-anchor="middle" font-family="Big Shoulders Display,Arial Narrow,sans-serif" font-weight="800" font-size="15" fill="#fff">2&#8211;3</text></svg>']

CUTAWAY = '<svg class="cut" viewBox="0 0 820 440" role="group" aria-label="Where the method keeps memory: a cutaway of the site. The higher up, the shorter it lasts"><defs><pattern id="soilp" width="14" height="14" patternUnits="userSpaceOnUse"><rect width="14" height="14" class="c-soil"/><circle cx="3" cy="4" r="1.2" class="c-grit"/><circle cx="10" cy="10" r="1" class="c-grit"/></pattern><pattern id="conp" width="10" height="10" patternUnits="userSpaceOnUse"><rect width="10" height="10" fill="#9AA29C"/><circle cx="2" cy="3" r=".9" fill="#7C847E"/><circle cx="7" cy="7" r=".8" fill="#B9C0BA"/></pattern><linearGradient id="deep" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".42"/></linearGradient><radialGradient id="glowg"><stop offset="0" stop-color="#FFD28A" stop-opacity=".38"/><stop offset="1" stop-color="#FFD28A" stop-opacity="0"/></radialGradient><radialGradient id="shad"><stop offset="0" stop-color="#000" stop-opacity=".35"/><stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient><marker id="mw" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M1 1L8 5L1 9" fill="none" stroke="#FBB401" stroke-width="2.4"/></marker><marker id="mr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M1 1L8 5L1 9" fill="none" stroke="#5AA0F0" stroke-width="2.4"/></marker><g id="tok"><rect x="-7" y="-5" width="14" height="10" fill="#FBB401" stroke="#101316" stroke-width="1.6"/><path d="M-4 -1.5h8M-4 1.5h5" stroke="#101316" stroke-width="1.2"/></g><g id="tokb"><rect x="-7" y="-5" width="14" height="10" fill="#5AA0F0" stroke="#101316" stroke-width="1.6"/><path d="M-4 -1.5h8M-4 1.5h5" stroke="#101316" stroke-width="1.2"/></g></defs><rect width="820" height="250" class="c-sky"/><rect y="258" width="820" height="182" fill="url(#soilp)"/><rect y="258" width="776" height="182" fill="url(#deep)"/><rect y="250" width="820" height="8" class="c-ground"/><ellipse cx="258" cy="252" rx="98" ry="7" fill="url(#shad)"/><ellipse cx="578" cy="252" rx="160" ry="7" fill="url(#shad)"/><ellipse cx="58" cy="252" rx="46" ry="5" fill="url(#shad)"/><ellipse class="c-glow" cx="572" cy="212" rx="230" ry="84" fill="url(#glowg)"/><path d="M0 180H770M0 258H770" class="c-band"/><rect x="776" y="0" width="44" height="180" class="b-ses"/><rect x="776" y="180" width="44" height="78" class="b-job"/><rect x="776" y="258" width="44" height="182" class="b-perm"/><text class="rt" transform="translate(802 90) rotate(-90)" text-anchor="middle">ONE SESSION</text><text class="rt" transform="translate(802 219) rotate(-90)" text-anchor="middle">EVERY JOB</text><text class="rt" transform="translate(802 349) rotate(-90)" text-anchor="middle">PERMANENT</text><path d="M16 20h30" class="lk w" marker-end="url(#mw)"/><text class="lt" x="54" y="24">writes</text><path d="M110 20h30" class="lk r" marker-end="url(#mr)"/><text class="lt" x="148" y="24">reads</text><g transform="translate(30 0)"><rect x="150" y="100" width="140" height="50" class="c-next"/><path d="M290 100l14-8v50l-14 8" class="c-next"/><text x="220" y="130" text-anchor="middle" class="tg tg-next">J13 · NEXT</text><g class="nd" data-n="job" tabindex="0" role="button" aria-label="1, J12, being built"><rect class="hit" x="146" y="146" width="164" height="108"/><path d="M290 150L304 142V242L290 250Z" class="c-side"/><rect x="150" y="200" width="140" height="50" class="c-done"/><text x="220" y="230" text-anchor="middle" class="tg">J11 · MERGED</text><rect x="150" y="150" width="140" height="50" class="c-now"/><rect x="186" y="163" width="18" height="14" class="c-win"/><rect x="212" y="163" width="18" height="14" class="c-win"/><rect x="238" y="163" width="18" height="14" class="c-win"/><rect x="264" y="163" width="18" height="14" class="c-win"/><text x="220" y="193" text-anchor="middle" class="tg tg-now">J12 · NOW</text><g class="pin"><circle cx="166" cy="170" r="10"/><text x="166" y="174" text-anchor="middle">1</text></g></g></g><g class="nd" data-n="opener" tabindex="0" role="button" aria-label="3, The next opener"><rect class="hit" x="90" y="84" width="50" height="37"/><g transform="rotate(-5 114 104)"><rect x="94" y="90" width="40" height="28" class="c-paper"/><path d="M100 99h26M100 105h20M100 111h24" class="c-lines"/></g><circle cx="114" cy="91" r="3" fill="#C42B1C"/><g class="pin"><circle cx="76" cy="100" r="10"/><text x="76" y="104" text-anchor="middle">3</text></g></g><g class="nd" data-n="handover" tabindex="0" role="button" aria-label="2, The handover"><rect class="hit" x="90" y="124" width="48" height="34"/><rect x="94" y="128" width="40" height="26" class="c-paper"/><path d="M94 128l20 14 20-14" class="c-lines"/><g class="pin"><circle cx="76" cy="136" r="10"/><text x="76" y="140" text-anchor="middle">2</text></g></g><g class="nd" data-n="board" tabindex="0" role="button" aria-label="4, The board"><rect class="hit" x="11" y="181" width="86" height="73"/><path d="M30 250v-30M78 250v-30" class="c-post"/><rect x="16" y="186" width="76" height="38" class="c-paper"/><rect x="22" y="192" width="64" height="6" fill="#3FAE6A"/><rect x="22" y="202" width="44" height="6" fill="#FBB401"/><rect x="22" y="212" width="28" height="6" class="c-dash"/><text x="28" y="172" class="tg">BOARD</text><g class="pin"><circle cx="14" cy="164" r="10"/><text x="14" y="168" text-anchor="middle">4</text></g></g><path d="M724 172L738 164V242L724 250Z" class="c-cabside"/><path d="M420 172L434 164H738L724 172Z" class="c-roof"/><rect x="420" y="172" width="304" height="78" class="c-cabin"/><rect x="420" y="170" width="304" height="6" fill="#101316"/><text x="630" y="160" text-anchor="middle" class="tg">SITE OFFICE</text><g class="nd" data-n="logbook" tabindex="0" role="button" aria-label="5, The Logbook"><rect class="hit" x="443" y="180" width="107" height="68"/><rect x="446" y="184" width="100" height="60" class="c-drawer"/><text x="496" y="196" text-anchor="middle" class="tg tg-plate">LOGBOOK</text><rect x="454" y="202" width="84" height="16" class="c-paper"/><rect x="454" y="222" width="84" height="16" class="c-paper"/><text x="496" y="213.5" text-anchor="middle" class="tg tg-slot">INDEX</text><text x="496" y="233.5" text-anchor="middle" class="tg tg-slot">LINKS</text><g class="pin"><circle cx="430" cy="192" r="10"/><text x="430" y="196" text-anchor="middle">5</text></g></g><text x="644" y="188" text-anchor="middle" class="tg tg-key">ITS TOOLS</text><g class="nd tool" data-n="search" tabindex="0" role="button" aria-label="/f-search"><rect class="hit" x="565" y="192" width="38" height="40"/><rect x="568" y="196" width="32" height="32" class="c-paper"/><g transform="translate(568 198)"><circle cx="15" cy="14" r="7" fill="none" stroke="#101316" stroke-width="2.6"/><path d="M20 19l6 6" stroke="#101316" stroke-width="3" stroke-linecap="round"/></g></g><g class="nd tool" data-n="context" tabindex="0" role="button" aria-label="/f-context"><rect class="hit" x="605" y="192" width="38" height="40"/><rect x="608" y="196" width="32" height="32" class="c-paper"/><g transform="translate(608 198)"><path d="M5 9l7-3 8 3 7-3v18l-7 3-8-3-7 3Z" fill="#DDEFE3" stroke="#101316" stroke-width="1.8"/><path d="M12 6v18M20 9v18" stroke="#101316" stroke-width="1.2"/><circle cx="16" cy="15" r="2.4" fill="#C42B1C"/></g></g><g class="nd tool" data-n="catchup" tabindex="0" role="button" aria-label="/f-catchup"><rect class="hit" x="645" y="192" width="38" height="40"/><rect x="648" y="196" width="32" height="32" class="c-paper"/><g transform="translate(648 198)"><rect x="5" y="14" width="14" height="11" fill="#C8A46A" stroke="#101316" stroke-width="1.6"/><rect x="8" y="10" width="14" height="11" fill="#D9B97E" stroke="#101316" stroke-width="1.6"/><path d="M21 8h7v6" fill="none" stroke="#101316" stroke-width="2"/><rect x="22" y="16" width="8" height="10" fill="#FBB401" stroke="#101316" stroke-width="1.4"/></g></g><g class="nd tool" data-n="dream" tabindex="0" role="button" aria-label="/f-dream"><rect class="hit" x="685" y="192" width="38" height="40"/><rect x="688" y="196" width="32" height="32" class="c-paper"/><g transform="translate(688 198)"><path d="M20 6a9 9 0 1 0 6 15a7 7 0 1 1-6-15Z" fill="#F4E9C8" stroke="#101316" stroke-width="1.8"/><path d="M22 9h4l-4 4h4" fill="none" stroke="#101316" stroke-width="1.4"/></g></g><path d="M195 258v38M250 258v38M305 258v38" stroke="#9AA29C" stroke-width="10"/><g class="nd" data-n="rules" tabindex="0" role="button" aria-label="6, The foundations"><rect class="hit" x="94" y="290" width="258" height="92"/><path d="M324 300L336 293V345L324 352Z" class="c-conside"/><path d="M120 300h204v52H120Z" fill="url(#conp)" stroke="#101316" stroke-width="2.5"/><path d="M130 312h184M130 340h184" stroke="#7A5434" stroke-width="2.4" stroke-dasharray="1 9" stroke-linecap="round"/><text x="222" y="330" text-anchor="middle" class="tg tg-dk">FIRM RULES</text><text x="222" y="372" text-anchor="middle" class="tg tg-files">AGENTS.md · CLAUDE.md · RULES.md</text><g class="pin"><circle cx="80" cy="304" r="10"/><text x="80" y="308" text-anchor="middle">6</text></g></g><g class="nd" data-n="archive" tabindex="0" role="button" aria-label="7, The archive"><rect class="hit" x="464" y="328" width="165" height="108"/><path d="M610 340L622 333V407L610 414Z" class="c-vside"/><rect x="470" y="340" width="140" height="74" class="c-vault"/><rect x="482" y="374" width="36" height="30" class="c-box"/><rect x="524" y="374" width="36" height="30" class="c-box"/><rect x="566" y="374" width="36" height="30" class="c-box"/><rect x="502" y="347" width="36" height="27" class="c-box"/><rect x="544" y="347" width="36" height="27" class="c-box"/><text x="540" y="430" text-anchor="middle" class="tg">ARCHIVE</text><g class="pin"><circle cx="452" cy="324" r="10"/><text x="452" y="328" text-anchor="middle">7</text></g></g><path id="p-card" class="lk w lk-logbook lk-job lk-card" marker-end="url(#mw)" d="M336 172 C 384 172 406 232 442 232"/><path id="p-load" class="lk r lk-logbook lk-search" marker-end="url(#mr)" d="M540 184 C 540 104 420 112 342 122"/><path id="p-open" class="lk w lk-opener lk-job" marker-end="url(#mw)" d="M178 158 C 166 128 154 110 138 108"/><path id="p-hand" class="lk w lk-handover lk-job" marker-end="url(#mw)" d="M178 166 C 164 154 152 144 140 142"/><path id="p-board" class="lk w lk-board lk-job" marker-end="url(#mw)" d="M178 192 C 140 194 116 200 98 204"/><path id="p-distill" class="lk w lk-rules lk-logbook" marker-end="url(#mw)" d="M470 248 C 470 304 420 326 342 326"/><path id="p-arch" class="lk w lk-archive lk-logbook" marker-end="url(#mw)" d="M520 248 L 520 330"/><path id="p-asearch" class="lk r lk-archive" marker-end="url(#mr)" d="M598 336 L 598 252"/><path id="p-rule0" class="lk r lk-rules" marker-end="url(#mr)" d="M195 296 L 195 256"/><path id="p-rule1" class="lk r lk-rules" marker-end="url(#mr)" d="M250 296 L 250 256"/><path id="p-rule2" class="lk r lk-rules" marker-end="url(#mr)" d="M305 296 L 305 256"/><text class="lt" x="14" y="66">end of job: /f-signoff</text><text class="lt lt-r" x="556" y="118">/f-shift loads</text><text class="lt lt-r" x="556" y="132">the cards in force</text><g class="nd" data-n="card" tabindex="0" role="button" aria-label="How a lesson becomes a card" transform="translate(16 0)"><rect class="hit" x="324" y="148" width="72" height="74"/><rect x="352" y="168" width="34" height="22" class="c-press"/><rect x="363" y="160" width="12" height="9" class="c-press"/><path d="M369 152v8" class="c-pressrod"/><rect x="356" y="190" width="26" height="4" fill="#FBB401" stroke="#101316" stroke-width="1"/><text class="lt lt-w" x="330" y="216">/f-card</text></g><text class="lt lt-w lt-s" x="78" y="172">/f-board</text><text class="lt lt-w" x="352" y="280">/f-distill</text><text class="lt lt-w" x="352" y="294">with your OK</text><text class="lt lt-w" x="528" y="290">/f-archive</text><text class="lt lt-w" x="528" y="304">past 250</text><text class="lt lt-r" x="606" y="304">/f-archive-search</text><text class="lt lt-r" x="14" y="272">every session</text><text class="lt lt-r" x="14" y="286">reads them</text><use class="amb" href="#tok"><animateMotion dur="3.6s" repeatCount="indefinite" begin="-0s"><mpath href="#p-card"/></animateMotion></use><use class="amb" href="#tokb"><animateMotion dur="4.4s" repeatCount="indefinite" begin="-1.6s"><mpath href="#p-load"/></animateMotion></use><use class="amb" href="#tok"><animateMotion dur="6.5s" repeatCount="indefinite" begin="-3s"><mpath href="#p-distill"/></animateMotion></use><g id="tt" class="tourtok" transform="translate(-40 -40)"><use href="#tok" transform="scale(1.7)"/></g></svg>'

CALLOUT_JS = '<script>(function(){var m=document.getElementById("memmap");if(!m)return;var box=m.querySelector(".mems"),sc=m.querySelector(".cutsc"),svg=sc.querySelector("svg"),\n ar=document.createElement("i"),nav=box.querySelector(".mems>.mnav"),sh=document.createElement("button"),wide=matchMedia("(min-width:1200px)");\nar.className="marrow";ar.setAttribute("aria-hidden","true");m.appendChild(ar);sh.type="button";sh.className="mshut";sh.textContent="Hide";nav.appendChild(sh);\nsh.addEventListener("click",function(){m.classList.add("shut")});\nfunction pin(){if(!wide.matches){box.style.cssText="";return}var n=svg.querySelector(".nd.on");if(!n)return;\n var M=m.getBoundingClientRect(),S=sc.getBoundingClientRect(),r=n.getBoundingClientRect(),G=14,A=11,W=box.offsetWidth;\n box.style.maxHeight=(S.height-16)+"px";var H=box.offsetHeight,x=r.right-M.left+G+A,side="r";\n if(x+W>S.right-M.left-8){x=r.left-M.left-G-A-W;side="l"}if(x<S.left-M.left+8){x=S.left-M.left+8;side=""}\n var cy=r.top+r.height/2-M.top,y=Math.max(S.top-M.top+8,Math.min(S.bottom-M.top-H-8,cy-H/2));\n box.style.left=x+"px";box.style.top=y+"px";ar.className="marrow "+side;ar.style.opacity=side?1:0;\n ar.style.top=Math.max(y+12,Math.min(y+H-34,cy-A))+"px";ar.style.left=(side==="r"?x-2*A:x+W)+"px"}\n/* the card follows whichever part is lit: a tap, Previous and Next, or the tour */\nnew MutationObserver(function(){m.classList.remove("shut");requestAnimationFrame(pin)}).observe(svg,{subtree:true,attributes:true,attributeFilter:["class"]});\naddEventListener("resize",pin);addEventListener("load",pin);if(document.fonts&&document.fonts.ready)document.fonts.ready.then(pin);pin()})()</script>'
MEMORY_JS = '<script>(function(){var m=document.getElementById("memmap");if(!m)return;m.classList.add("js");\nvar svg=m.querySelector("svg"),nodes=[].slice.call(m.querySelectorAll(".nd")),cards=[].slice.call(m.querySelectorAll(".mem:not(.tour)")),links=[].slice.call(m.querySelectorAll(".lk[id]")),\n order=cards.map(function(c){return c.dataset.m}),tour=m.querySelector(".tour"),tb=m.querySelector("[data-tour]"),tt=svg.getElementById("tt"),\n TOUR=__TOUR__,still=!!(window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches),cur="logbook",ts=-1,tt0=0,raf=0,seen=true;\nfunction light(k,path){nodes.forEach(function(n){var on=n.dataset.n===k;n.classList.toggle("on",on);n.setAttribute("aria-pressed",on?"true":"false")});\n links.forEach(function(l){l.classList.toggle("hot",path?l.id===path:l.classList.contains("lk-"+k))});svg.classList.add("picked")}\nfunction pick(k){stop();cur=k;light(k);cards.forEach(function(c){c.hidden=c.dataset.m!==k});tour.hidden=true}\nfunction go(d){var i=order.indexOf(cur);pick(order[(i+d+order.length)%order.length])}\nnodes.forEach(function(n){n.addEventListener("click",function(){pick(n.dataset.n)});n.addEventListener("keydown",function(e){if(e.key==="Enter"||e.key===" "){e.preventDefault();pick(n.dataset.n)}})});\n[].forEach.call(m.querySelectorAll("[data-go]"),function(b){b.addEventListener("click",function(){go(+b.dataset.go)})});\n/* the tour: one lesson, from the job that learned it to the foundations and the archive */\nvar STEP=4200;\nfunction show(i){ts=i;tt0=performance.now();var s=TOUR[i];light(s[0],s[1]);cards.forEach(function(c){c.hidden=true});tour.hidden=false;\n tour.querySelector(".tn").textContent="Step "+(i+1)+" of "+TOUR.length;tour.querySelector("h3").textContent=s[3];tour.querySelector("p").textContent=s[4];\n tour.querySelector("[data-next]").textContent=i===TOUR.length-1?"Done":"Next →";\n if(still||!s[1])place(s[1],1)}\nvar PARK={job:"220 172",logbook:"496 158"};function place(path,u){if(!path){tt.setAttribute("transform","translate("+(PARK[ts>=0?TOUR[ts][0]:"job"]||PARK.job)+")");return}var p=svg.getElementById(path),L=p.getTotalLength(),pt=p.getPointAtLength(L*u);tt.setAttribute("transform","translate("+pt.x+" "+pt.y+")")}\nfunction frame(now){if(ts<0)return;var s=TOUR[ts],e=now-tt0;\n if(s[1]&&seen){var reps=s[2],per=Math.min(1700,(STEP-400)/reps),k=Math.floor(e/per);place(s[1],k<reps?(e%per)/per:1)}\n if(!still&&seen&&e>STEP){if(ts<TOUR.length-1)show(ts+1);else{stop();pick("logbook");return}}\n raf=requestAnimationFrame(frame)}\nfunction start(){svg.classList.add("touring");tb.textContent="Stop";tb.setAttribute("aria-pressed","true");show(0);cancelAnimationFrame(raf);raf=requestAnimationFrame(frame)}\nfunction stop(){if(ts<0)return;ts=-1;cancelAnimationFrame(raf);svg.classList.remove("touring");tb.textContent="▶ Follow one lesson";tb.setAttribute("aria-pressed","false");tt.setAttribute("transform","translate(-40 -40)")}\ntb.addEventListener("click",function(){ts<0?start():(stop(),pick(cur))});\ntour.querySelector("[data-next]").addEventListener("click",function(){if(ts<TOUR.length-1)show(ts+1);else{stop();pick("logbook")}});\n[].forEach.call(m.querySelectorAll(".mx"),function(x){var d=document.createElement("dialog"),b=x.querySelector(".mxb");d.className="mdlg";d.setAttribute("aria-label",x.dataset.title);d.innerHTML=\'<div class="mdh"><span></span><button type="button">Close</button></div><div class="mdb"></div>\';d.querySelector(".mdh span").textContent=x.dataset.title;d.querySelector(".mdb").appendChild(b);b.classList.remove("mxb");document.body.appendChild(d);d.querySelector(".mdh button").addEventListener("click",function(){d.close()});d.addEventListener("click",function(e){if(e.target===d)d.close()});x.querySelector(".mdiag").addEventListener("click",function(){if(d.showModal)d.showModal();else d.setAttribute("open","")})});\npick("logbook");\nif(svg.pauseAnimations){if(still)svg.pauseAnimations();else if(window.IntersectionObserver)new IntersectionObserver(function(es){seen=es[0].isIntersecting;seen?svg.unpauseAnimations():svg.pauseAnimations();if(seen&&ts>=0)tt0=performance.now()}).observe(svg)}\n})()</script>'
MEMORY_TOUR = [('job', None, 1, 'J12 learns something', 'Mid-job, the foreman finds a lesson worth keeping: a trap in this repo, a method that worked, a decision and the reason for it.'), ('logbook', 'p-card', 1, '/f-card makes it a card', 'It picks a type, checks the Logbook for a twin, scores the card and shows it to you. With your yes it is filed: the card, its row in the index, its links.'), ('logbook', None, 1, 'It links to what it builds on', 'The index gets a row for the new card, and logbook_links.md records that it refines an older one. Well-linked cards are the ones that stay live when the Logbook is thinned.'), ('logbook', 'p-load', 1, 'J13 starts knowing it', "A fresh session remembers nothing. Before any work, /f-shift searches the Logbook for the job's area and lists the cards in force."), ('logbook', 'p-load', 3, 'It keeps coming back', 'J14 and J15 load the same card. A lesson that keeps coming back is a rule waiting to be written.'), ('rules', 'p-distill', 1, '/f-distill pours a rule', "It proposes a firm rule and shows it to you first. With your OK it goes into the repo's own instructions or RULES.md, for good."), ('archive', 'p-arch', 1, 'Old cards go down to the archive', 'Past 250 live cards, /f-shift has /f-archive move older ones to the archive and leave 50 index cards. /f-archive-search still finds them.')]

LOGBOOK_GRAPH = '<figure class="lgraph"><div class="lgh"><span><code>logbook_index.md</code> every live card: its type, summary, impact and cluster</span><span><code>logbook_links.md</code> the typed links between them</span></div><svg viewBox="0 0 960 252" role="img" aria-label="An example Logbook graph. Cluster billing: a new insight refines an older one and contradicts another; the older one was derived from a build record. Cluster test-runs: one method supersedes an older method. Each card shows its number of links; the cards with one link are archived first."><defs><marker id="gm-plain" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L8 5L1 9" fill="none" stroke="currentColor" stroke-width="2.2"/></marker><marker id="gm-new" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L8 5L1 9" fill="none" stroke="#B07A00" stroke-width="2.2"/></marker><marker id="gm-bad" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L8 5L1 9" fill="none" stroke="#C42B1C" stroke-width="2.2"/></marker><marker id="gm-dash" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L8 5L1 9" fill="none" stroke="currentColor" stroke-width="2.2"/></marker></defs><rect x="14" y="26" width="626" height="214" class="gcl"/><text x="22" y="19" class="gcn">cluster: billing</text><rect x="664" y="26" width="282" height="214" class="gcl"/><text x="672" y="19" class="gcn">cluster: test-runs</text><path class="ge g-plain" d="M400 79 L 466 79" marker-end="url(#gm-plain)"/><text x="433" y="48" text-anchor="middle" class="gl g-plain">derived-from</text><path class="ge g-new" d="M325 172 L 325 106" marker-end="url(#gm-new)"/><text x="362" y="146" text-anchor="middle" class="gl g-new">refines</text><path class="ge g-bad" d="M258 182 L 130 106" marker-end="url(#gm-bad)"/><text x="160" y="156" text-anchor="middle" class="gl g-bad">contradicts</text><path class="ge g-dash" d="M180 79 L 246 79" marker-end="url(#gm-dash)"/><text x="213" y="70" text-anchor="middle" class="gl g-dash">relates</text><path class="ge g-plain" d="M770 102 L 840 168" marker-end="url(#gm-plain)"/><text x="850" y="128" text-anchor="middle" class="gl g-plain">supersedes</text><path class="ge g-dash" d="M400 196 C 540 196 600 90 686 84" marker-end="url(#gm-dash)"/><text x="590" y="138" text-anchor="middle" class="gl g-dash">relates</text><g class="gc"><rect x="30" y="56" width="150" height="46"/><text x="40" y="75" class="gid">I-05</text><text x="40" y="92" class="gk">INSIGHT</text><text x="170" y="75" text-anchor="end" class="gn">2 links</text></g><g class="gc"><rect x="250" y="56" width="150" height="46"/><text x="260" y="75" class="gid">I-11</text><text x="260" y="92" class="gk">INSIGHT</text><text x="390" y="75" text-anchor="end" class="gn">3 links</text></g><g class="gc gweak"><rect x="470" y="56" width="150" height="46"/><text x="480" y="75" class="gid">B-06</text><text x="480" y="92" class="gk">BUILD</text><text x="610" y="75" text-anchor="end" class="gn">1 link</text><text x="470" y="118" class="gweakt">archived first</text></g><g class="gc gnew"><rect x="250" y="172" width="150" height="46"/><text x="260" y="191" class="gid">I-17</text><text x="260" y="208" class="gk">INSIGHT</text><text x="390" y="191" text-anchor="end" class="gn">3 links</text><rect x="356" y="160" width="44" height="14" class="gtag"/><text x="378" y="170" text-anchor="middle" class="gtagt">NEW</text></g><g class="gc"><rect x="690" y="56" width="150" height="46"/><text x="700" y="75" class="gid">M-09</text><text x="700" y="92" class="gk">METHOD</text><text x="830" y="75" text-anchor="end" class="gn">2 links</text></g><g class="gc gweak"><rect x="776" y="172" width="150" height="46"/><text x="786" y="191" class="gid">M-04</text><text x="786" y="208" class="gk">METHOD</text><text x="916" y="191" text-anchor="end" class="gn">1 link</text><text x="776" y="234" class="gweakt">archived first</text></g></svg><figcaption>Past 250 cards, <code>/f-archive</code> keeps the best-linked and most recent cards live, so the faded ones go first. An example, not a real Logbook.</figcaption></figure>'

CARD_PRESS = '<ol class="press"><li><span class="pn">1</span><b>Mine</b><span class="pt">The job\'s key discoveries, its work-order reviews, its inspections and the dev report\'s learnings. Or one lesson, mid-job.</span></li><li><span class="pn">2</span><b>Type it</b><span class="pt">INSIGHT for a gotcha or principle, METHOD for a repeatable procedure, BUILD for a record of what was built. Each has its template.</span></li><li><span class="pn">3</span><b>Check for a twin</b><span class="pt">Search the Logbook for the same lesson. Over 80% overlap: the evidence goes on the old card instead.</span></li><li><span class="pn">4</span><b>Score it</b><span class="pt">Every section filled, the evidence, a concrete example. Confidence from evidence: one instance 75%, two or more 85%, measured 95%. Under 75 of 100, it goes back.</span></li><li><span class="pn">5</span><b>Show you</b><span class="pt">The whole card as a preview. Nothing is written until you say yes.</span></li><li><span class="pn">6</span><b>File it</b><span class="pt">The card file, a row in the index, its links, and the counts recounted from the files.</span></li></ol>'

# The order of works, step by step: what happens, what it reads, what it writes, and the gate it must pass.
# Sources: METHOD.md §2-§10 and §13, and each skill's page in skills-wiki/. The memory parts link to the cutaway.
STEP_NOTES = {
    'Shape the idea': ('idea', 'Your rough idea becomes a list of clear decisions. The foreman asks you a few questions at a time and checks the code to settle each one.', 'Your request, and the code itself.', 'A notes file while it is rough, then a brief with every question answered.', 'No question is left open.', []),
    'Write the plan': ('plan', 'The foreman writes the whole plan: the goal, the decisions, what must be true at the end, and the tasks. No code yet.', 'The settled decisions.', 'The project plan.', 'Every decision is made before the plan is written.', []),
    'Check the plan': ('check', 'AI models from other companies read the plan with the same checklist and point out problems. Their findings are combined, not voted on.', 'The plan, cold.', 'One combined list of findings.', 'The plan must pass before it is split into jobs.', []),
    'Cut into tickets': ('cut', 'The plan is split into jobs, in order, one ticket each. Anything that needs research or your decision becomes a job of its own.', 'The checked plan.', "The project's folder and its board.", 'Nothing is written until you say go.', [('writes', 'board')]),
    'Start the shift': ('hat', 'A fresh foreman reads the rules, the notes the last job left, and the lessons that apply to this one. Then it checks the code for itself.', 'The opener, the handover, the Logbook and the firm rules.', 'The cards in force, listed in its first reply.', 'If the notes and the code disagree, it trusts the code.', [('reads', 'opener'), ('reads', 'handover'), ('reads', 'logbook'), ('reads', 'rules')]),
    'Build': ('brick', 'The builder does one small task at a time, writing the test first. The foreman reviews every change.', "The foreman's work orders.", 'Code and tests, one commit per task.', 'A test that fails only on the new code stops the work.', []),
    'Inspect': ('lens', 'Two separate checks of the finished work. Fresh reviewers look for problems, then a model from another company reads it cold. Reviewers report problems; they never fix them.', 'The changes, and a brief with every model name taken out.', 'Findings, never fixes. Accepted fixes go back to the builder as a work order.', 'Both checks run, even when the first finds nothing.', []),
    'Open the PR': ('pr', 'The work goes up for review as a pull request, with a description checked against what was actually built.', 'The final changes and test runs.', 'The pull request.', 'Only with your OK, or your /goal.', []),
    'Review the PR': ('review', 'Greptile reviews the pull request. Each finding is checked, the builder fixes it, and the tests run again.', "The review's findings.", 'Fix commits, pushed with your word or your /goal.', 'Three rounds at most.', []),
    'Merge': ('merge', 'The work is merged, and the result is checked against what was reviewed.', 'The reviewed branch.', 'The merge.', 'Only with your OK, or your /goal.', []),
    'Close': ('flag', 'The job is checked against every requirement, then wrapped up: a short report, the lessons saved, the board updated, and notes for the next job.', 'The acceptance ledger and the job file.', 'Logbook cards, the board close, the handover and the next opener.', 'Every requirement has passed, with nothing left for later.', [('writes', 'logbook'), ('writes', 'board'), ('writes', 'handover'), ('writes', 'opener')]),
}

# The front page's caption under the route: one short line and one short rule per step, for a reader who skims.
# The Order of works page keeps the full STEP_NOTES.
STEP_SHORT = {
    'Shape the idea': ('Your idea becomes clear decisions.', 'No question left open.'),
    'Write the plan': ('The whole plan, before any code.', 'Every decision made first.'),
    'Check the plan': ('Other AI models check the plan.', 'It passes before it is split.'),
    'Cut into tickets': ('The plan becomes jobs, in order.', 'Nothing written until you say go.'),
    'Start the shift': ('A fresh foreman reads the notes, then the code.', 'Where they disagree, the code wins.'),
    'Build': ('One small task at a time, test first.', 'A test that breaks stops the work.'),
    'Inspect': ('Two reviews: fresh eyes, then another AI.', 'Both run, always.'),
    'Open the PR': ('The work goes up as a pull request.', 'Only on your word, or your /goal.'),
    'Review the PR': ('Greptile reviews it; findings get fixed.', 'Three rounds at most.'),
    'Merge': ('Merged, then checked against what was reviewed.', 'Only on your word, or your /goal.'),
    'Close': ('Every requirement checked, notes left for the next job.', 'Nothing left for later.'),
}

STEP_ICONS = {
    "idea": '<circle cx="12" cy="10" r="6.5" fill="#FBB401" stroke="#101316" stroke-width="1.8"/><path d="M9 17h6M10 20.5h4" stroke="#101316" stroke-width="1.8"/>',
    "plan": '<rect x="3" y="5" width="18" height="14" fill="#5AA0F0" stroke="#101316" stroke-width="1.8"/><path d="M6 9h12M6 12h8M6 15h10" stroke="#fff" stroke-width="1.3"/>',
    "check": '<rect x="3" y="3" width="13" height="17" fill="#F4F4EF" stroke="#101316" stroke-width="1.8"/><circle cx="15" cy="14" r="4.5" fill="#DDEFE3" stroke="#101316" stroke-width="1.8"/><path d="M18.3 17.3l3.2 3.2" stroke="#101316" stroke-width="2.4" stroke-linecap="round"/>',
    "cut": '<rect x="2" y="6" width="9" height="12" fill="#F4F4EF" stroke="#101316" stroke-width="1.6"/><rect x="13" y="6" width="9" height="12" fill="#FBB401" stroke="#101316" stroke-width="1.6"/><path d="M12 3v18" stroke="#101316" stroke-width="1.4" stroke-dasharray="2 2"/>',
    "hat": '<path d="M4 16c0-6 4-10 8-10s8 4 8 10Z" fill="#F4F4EF" stroke="#101316" stroke-width="1.8"/><rect x="2" y="15.5" width="20" height="3.5" fill="#F4F4EF" stroke="#101316" stroke-width="1.8"/>',
    "brick": '<rect x="2" y="7" width="20" height="11" fill="#C8553D" stroke="#101316" stroke-width="1.8"/><path d="M2 12.5h20M12 7v5.5M7 12.5V18M17 12.5V18" stroke="#101316" stroke-width="1.4"/>',
    "lens": '<circle cx="10" cy="10" r="6" fill="#DDEFE3" stroke="#101316" stroke-width="2"/><path d="M14.5 14.5l6 6" stroke="#101316" stroke-width="2.8" stroke-linecap="round"/>',
    "pr": '<circle cx="6" cy="5" r="2.5" fill="#F4F4EF" stroke="#101316" stroke-width="1.6"/><circle cx="6" cy="19" r="2.5" fill="#F4F4EF" stroke="#101316" stroke-width="1.6"/><circle cx="18" cy="19" r="2.5" fill="#FBB401" stroke="#101316" stroke-width="1.6"/><path d="M6 7.5v9M18 16.5V10c0-2-1.5-3-3.5-3H10" fill="none" stroke="#101316" stroke-width="1.6"/>',
    "review": '<path d="M3 4h18v12H10l-5 4v-4H3Z" fill="#F4F4EF" stroke="#101316" stroke-width="1.8" stroke-linejoin="round"/><path d="M8 10l3 3 5-5" fill="none" stroke="#1E7B4A" stroke-width="2"/>',
    "merge": '<circle cx="6" cy="5" r="2.5" fill="#F4F4EF" stroke="#101316" stroke-width="1.6"/><circle cx="18" cy="5" r="2.5" fill="#F4F4EF" stroke="#101316" stroke-width="1.6"/><circle cx="12" cy="19" r="2.8" fill="#3FAE6A" stroke="#101316" stroke-width="1.6"/><path d="M6 7.5c0 5 6 5 6 9M18 7.5c0 5-6 5-6 9" fill="none" stroke="#101316" stroke-width="1.6"/>',
    "flag": '<path d="M6 21V3" stroke="#101316" stroke-width="2"/><path d="M7 4h12l-3 3.5 3 3.5H7Z" fill="#3FAE6A" stroke="#101316" stroke-width="1.6" stroke-linejoin="round"/>',
}

ORDER_JS = '<script>(function(){var sec=document.getElementById("route"),strip=document.getElementById("stepbox");if(!sec||!strip)return;sec.classList.add("js");\nvar steps=[].slice.call(sec.querySelectorAll(".phs[data-step]")),items=[].slice.call(strip.querySelectorAll(".sitem")),mode=strip.querySelector(".smode"),pb=strip.querySelector("[data-play]"),\n order=items.map(function(it){return it.dataset.step}),loop=[].slice.call(sec.querySelectorAll(".loop .phs[data-step]")).map(function(s){return s.dataset.step}),cur=loop[0],held=false;\nfunction show(k){cur=k;var al=strip.querySelector(".sall");if(al)al.setAttribute("href","route.html#"+k);items.forEach(function(it){var off=it.dataset.step!==k;it.classList.toggle("off",off);it.setAttribute("aria-hidden",off?"true":"false")});steps.forEach(function(s){var on=s.dataset.step===k;s.classList.toggle("on",on);s.setAttribute("aria-pressed",on?"true":"false")})}\n/* held: you are reading; the walker waits. Playing: the strip follows the walker again. */\nfunction hold(k){held=true;window.walkPaused=true;strip.classList.add("pinned");mode.textContent="Paused";pb.setAttribute("aria-label","Play");if(k)show(k)}\nfunction play(){held=false;window.walkPaused=false;strip.classList.remove("pinned");mode.textContent="Now";pb.setAttribute("aria-label","Pause")}\npb.addEventListener("click",function(){held?play():hold()});\n[].forEach.call(strip.querySelectorAll("[data-sgo]"),function(b){b.addEventListener("click",function(){var i=order.indexOf(cur);hold(order[(i+(+b.dataset.sgo)+order.length)%order.length])})});\nsteps.forEach(function(s){s.addEventListener("click",function(e){if(e.target.closest("a"))return;hold(s.dataset.step)});s.addEventListener("keydown",function(e){if(e.key==="Enter"||e.key===" "){e.preventDefault();hold(s.dataset.step)}})});\nwindow.walkHook=function(i){if(!held)show(loop[i])};\n[].forEach.call(strip.querySelectorAll("[data-mem]"),function(b){b.addEventListener("click",function(){var n=document.querySelector(\'#memmap .nd[data-n="\'+b.dataset.mem+\'"]\'),mm=document.getElementById("memmap");if(!n||!mm)return;n.dispatchEvent(new MouseEvent("click",{bubbles:true}));mm.scrollIntoView({behavior:"smooth",block:"start"})})});\nif(window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches)hold(loop[0]);else show(loop[0])})()</script>'

CONVEYOR = '<svg class="conv" aria-hidden="true" focusable="false"><path class="cvl"/><text class="cvt">the tickets, one at a time</text><g class="cvk"></g></svg>\n<script>(function(){var sec=document.getElementById("route");if(!sec)return;var svg=sec.querySelector("svg.conv"),path=svg.querySelector(".cvl"),txt=svg.querySelector(".cvt"),kg=svg.querySelector(".cvk"),\n track=sec.querySelector(".once .track"),loop=sec.querySelector(".shiftbox .loop"),box=sec.querySelector(".shiftbox");if(!track||!loop||!box)return;\nvar still=!!(window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches),on=true,L=0,toks=[];\nfor(var i=0;i<3;i++){var g=document.createElementNS("http://www.w3.org/2000/svg","g");g.innerHTML=\'<rect x="-9" y="-6" width="18" height="12" fill="#FBB401" stroke="#101316" stroke-width="1.6"/><path d="M-5 -1.5h10M-5 2h6" stroke="#101316" stroke-width="1.2"/>\';kg.appendChild(g);toks.push(g)}\nfunction draw(){var s=sec.getBoundingClientRect(),tr=track.getBoundingClientRect(),lp=loop.getBoundingClientRect(),bx=box.getBoundingClientRect();\n svg.setAttribute("width",s.width);svg.setAttribute("height",s.height);\n var vert=parseFloat(getComputedStyle(track).borderLeftWidth)>0,sx,sy;\n if(vert){sx=tr.left-s.left+1.5;sy=tr.bottom-s.top}else{sx=tr.right-s.left-1.5;sy=tr.top-s.top+1.5}\n var ex=lp.left-s.left+1.5,ey=lp.top-s.top+(vert?20:0),ob=sec.querySelector(".once").getBoundingClientRect().bottom-s.top,cy=(ob+bx.top-s.top)/2;\n path.setAttribute("d","M"+sx+" "+sy+"V"+cy+"H"+ex+"V"+ey);L=path.getTotalLength();\n txt.setAttribute("x",vert?ex+14:(sx+ex)/2);txt.setAttribute("y",cy-9);txt.setAttribute("text-anchor",vert?"start":"middle")}\nfunction frame(now){if(!on)return;toks.forEach(function(g,i){var u=((now/1000)/9+i/3)%1,pt=path.getPointAtLength(L*u);g.setAttribute("transform","translate("+pt.x+" "+pt.y+")")});requestAnimationFrame(frame)}\ndraw();if(window.ResizeObserver)new ResizeObserver(draw).observe(sec);\nif(still){toks.forEach(function(g){g.style.display="none"});return}\nif(window.IntersectionObserver)new IntersectionObserver(function(es){var v=es[0].isIntersecting;if(v&&!on){on=true;requestAnimationFrame(frame)}else if(!v)on=false}).observe(sec);\nrequestAnimationFrame(frame)})()</script>'

NIGHT_STRIP = '<div class="nstrip" id="nstrip" style="--t:1"><span class="nstars" aria-hidden="true"></span><span class="nmoon" aria-hidden="true"></span><span class="nsun" aria-hidden="true"></span>\n<div class="nrow">\n<div class="ntype"><span class="nt">22:30 &middot; Before bed</span><b>You type one line</b><code><span class="nty">/goal night shift: jobs 11, 12, 13</span><span class="ncar" aria-hidden="true"></span></code></div>\n<div class="nline" role="img" aria-label="An example night: boards 11, 12 and 13 each built, checked and merged, one after another, between 22:40 and 05:50">\n<div class="nclock" aria-hidden="true"><span>Night shift</span><b class="nck">06:30</b></div>\n<div class="ntrack" aria-hidden="true">\n<div class="njob" style="--a:.02;--b:.33"><i class="nfill"></i><b>Board 11</b><span>built, checked</span><em>Merged</em></div>\n<div class="njob" style="--a:.345;--b:.65"><i class="nfill"></i><b>Board 12</b><span>on top of 11</span><em>Merged</em></div>\n<div class="njob" style="--a:.665;--b:.92"><i class="nfill"></i><b>Board 13</b><span>last on the list</span><em>Merged</em></div>\n<span class="ncur"></span></div>\n<div class="nticks" aria-hidden="true"><span>23:00</span><span>01:00</span><span>03:00</span><span>05:00</span></div>\n</div>\n<div class="nmorn"><span class="nt">07:00 &middot; Morning</span><b>3 jobs merged</b><span>The links, and anything only you can decide.</span></div>\n</div><button type="button" class="nreplay" hidden>&#8635; Replay the night</button></div>\n<p class="nextra"><b>A failed check stops the shift,</b> so nothing broken merges. <code>3 jobs, auto-pick</code> lets it choose. <a href="skills/f-night-shift.html">How it works &rarr;</a></p>\n<script>(function(){var n=document.getElementById("nstrip");if(!n)return;\nvar jobs=[].slice.call(n.querySelectorAll(".njob")),ck=n.querySelector(".nck"),ty=n.querySelector(".nty"),rb=n.querySelector(".nreplay"),cmd=ty.textContent,raf=0;\nfunction set(t){n.style.setProperty("--t",t.toFixed(4));var h=22.5+8*t,hh=Math.floor(h)%24,mm=Math.floor((h%1)*60);ck.textContent=(hh<10?"0":"")+hh+":"+(mm<10?"0":"")+mm;\n jobs.forEach(function(j){var a=+j.style.getPropertyValue("--a"),b=+j.style.getPropertyValue("--b"),f=Math.max(0,Math.min(1,(t-a)/(b-a)));j.style.setProperty("--f",f.toFixed(3));j.classList.toggle("on",f>0&&f<1);j.classList.toggle("done",f>=1)});\n n.classList.toggle("dawn",t>=1)}\nfunction play(){cancelAnimationFrame(raf);n.classList.add("live");set(0);ty.textContent="";var i=0,t0=0;\n (function type(){ty.textContent=cmd.slice(0,++i);if(i<cmd.length)raf=setTimeout(type,38);else{n.classList.add("typed");raf=requestAnimationFrame(function go(now){if(!t0)t0=now;var t=Math.min(1,(now-t0)/7000);set(t);if(t<1)raf=requestAnimationFrame(go)})}})()}\nset(1);\nif(!window.IntersectionObserver||(window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches))return;\nrb.hidden=false;rb.addEventListener("click",function(){clearTimeout(raf);n.classList.remove("typed");play()});\nnew IntersectionObserver(function(es,o){if(!es[0].isIntersecting)return;o.disconnect();play()},{threshold:.4}).observe(n)})()</script>'


CLOSER = '<section class="closer" aria-labelledby="closer-h"><div class="haz" role="presentation"></div><div class="cl">__MARK__<div><h2 id="closer-h">Top out your first job.</h2>\n<p>Two lines: install, then set up.</p>__CMD__<a class="gh" href="https://github.com/__REPO__"><svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path fill="currentColor" d="__GH__"/></svg><span><b>__REPOB__</b><small>Open source on GitHub · MIT</small></span><i aria-hidden="true">&#8599;</i></a>\n<a class="clnext" href="#needs">What it runs on &uarr;</a></div></div></section>'

# The front page is a site where each section's heading is set out but not yet delivered. As it scrolls into
# view a crane lowers it into place on its slings, it lands with a puff of dust and the hook goes back up for the
# next one (BUILD_JS). The signs bolted to each heading carry the jokes, so the body text stays plain and is never
# covered. The closer is the topping out: one floor per section, and the last beam goes up with its tree. Without
# JavaScript, or with reduced motion, every heading is simply in place and the building stands finished.
HOARD_SIGNS = {
    "pillars": ("blue", "Site rule", "Do not distract the builder. It only builds what&rsquo;s drawn."),
    "route": ("yellow", "Caution", "Inspectors on site. Do not feed."),
    "shift": ("night", "Notice", "Sorry for the noise. We&rsquo;re building your app while you sleep."),
    "lost": ("green", "Site record", 'Lessons forgotten on this site<span class="dg" aria-label="zero"><i>0</i><i>0</i><i>0</i></span>'),
    "why": ("red", "Not accepted", "&ldquo;Trust me, it&rsquo;s done&rdquo; is not a test result."),
    "needs": ("blue", "Site access", "Authorised plant only. Bring your own, and you maintain it."),
    "see": ("yellow", "Caution", "Viewing platform. Mind your head."),
}
FRONT_FLOORS = [("pillars", "Why Topping Out"), ("route", "Order of works"), ("shift", "The night shift"), ("lost", "Nothing is lost"),
                ("why", "Why not just&hellip;?"), ("needs", "Requirements"), ("see", "See it")]
SIGN_TILT = {"pillars": -.9, "route": .8, "shift": -.7, "lost": 1, "why": -1, "needs": .75, "see": -.8}


def hoard_sign(sid: str) -> str:
    kind, band, text = HOARD_SIGNS[sid]
    return f'<p class="hsign s-{kind}" style="--r:{SIGN_TILT[sid]}deg"><b>{band}</b><span>{text}</span></p>'


BUILD_CSS = r"""
.sec{position:relative}
.sec-h{flex-wrap:wrap;row-gap:10px}
.hsign{margin:0 0 -2px auto;align-self:flex-end;position:relative;width:min(100%,262px);border:2px solid #101316;background:#FFFFFF;color:#101316;
 box-shadow:3px 3px 0 rgba(16,19,22,.18);transform:rotate(var(--r,0deg));transform-origin:13px 9px;font:600 13.5px/1.4 "Public Sans",system-ui,sans-serif}
.hsign>b{display:block;padding:5px 10px 4px 28px;font:800 13px/1 "Big Shoulders Display","Arial Narrow",sans-serif;letter-spacing:.1em;text-transform:uppercase;border-bottom:2px solid #101316}
.hsign>span{display:block;padding:7px 11px 9px}
.hsign::before,.hsign::after{content:"";position:absolute;top:5px;width:7px;height:7px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#fff 0 1px,#C9CFC7 1.5px);border:1.5px solid #101316}
.hsign::before{left:9px}.hsign::after{right:8px}
.hsign.s-blue>b{background:#1F5FA8;color:#fff}.hsign.s-yellow>b{background:#FBB401;color:#101316}.hsign.s-green>b{background:#1E7B4A;color:#fff}
.hsign.s-red>b{background:#C42B1C;color:#fff}.hsign.s-night>b{background:#14233B;color:#FBB401}
.hsign .dg{display:flex;gap:4px;margin-top:6px}
.hsign .dg i{font:700 20px/1 "Martian Mono",ui-monospace,monospace;font-style:normal;background:#101316;color:#3FAE6A;padding:5px 6px 4px;box-shadow:inset 0 -9px 0 rgba(255,255,255,.06)}
.hsign:hover{animation:sign-swing .95s linear}
@keyframes sign-swing{0%{transform:rotate(var(--r));animation-timing-function:ease-out}16%{transform:rotate(calc(var(--r) + 6deg));animation-timing-function:ease-in-out}38%{transform:rotate(calc(var(--r) - 3.4deg));animation-timing-function:ease-in-out}58%{transform:rotate(calc(var(--r) + 1.8deg));animation-timing-function:ease-in-out}78%{transform:rotate(calc(var(--r) - .8deg));animation-timing-function:ease-in-out}100%{transform:rotate(var(--r))}}
@media (max-width:720px){.hsign{margin-left:0;flex-basis:100%;width:auto;max-width:330px}}
@media (prefers-reduced-motion:reduce){.hsign:hover{animation:none}}
.sec-h{position:relative}
.cr-wait>*:not(.cr-mark){opacity:0}
.cr-wait{border-bottom-style:dashed;border-bottom-color:var(--brand)}
.cr-mark{position:absolute!important;inset:-6px -8px -1px;z-index:2!important;pointer-events:none;border:1.5px dashed var(--brand);border-bottom:0;
 background:repeating-linear-gradient(-45deg,transparent 0 9px,var(--line-2) 9px 10px)}
.cr-mark::before,.cr-mark::after{content:"";position:absolute;bottom:-7px;width:13px;height:13px;
 background:linear-gradient(var(--brand),var(--brand)) center/1.5px 100% no-repeat,linear-gradient(var(--brand),var(--brand)) center/100% 1.5px no-repeat}
.cr-mark::before{left:-7px}.cr-mark::after{right:-7px}
.cr-mark b{position:absolute;left:10px;top:50%;transform:translateY(-50%);font:700 10.5px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;
 text-transform:uppercase;color:var(--brand);background:var(--ground);padding:3px 6px;transition:opacity .25s}
.cr-due b{opacity:0}
.cr-fly{z-index:30!important;will-change:transform;background:var(--ground);box-shadow:0 14px 22px -12px rgba(0,0,0,.45)}
.cr-rig{position:absolute;left:0;top:0;width:1px;height:1px;overflow:visible;pointer-events:none;z-index:3}
.cr-rig svg{position:absolute;left:0;top:0;overflow:visible}
.cr-rig .cb{stroke:var(--ink);stroke-width:2}.cr-rig .sl{stroke:var(--ink);stroke-width:1.6;fill:none}
.cr-rig .blk{fill:#FBB401;stroke:#101316;stroke-width:2}.cr-rig .hk{fill:none;stroke:var(--ink);stroke-width:3.2;stroke-linecap:round}
.cr-rig .sh{fill:#101316}.cr-rig .sh2{fill:#FBB401}.cr-rig .hz{fill:#101316}
.cr-rig .tg{fill:#fff;stroke:#101316;stroke-width:1.5}.cr-rig .tgs{stroke:var(--ink);stroke-width:1}
.cr-rig text{font:700 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.06em;fill:#101316}
.cr-shd{position:absolute;left:6%;right:6%;bottom:-9px;height:18px;border-radius:50%;background:radial-gradient(closest-side,rgba(16,19,22,.38),rgba(16,19,22,0));opacity:0}
.cr-clear{border-color:transparent!important;background:none!important}.cr-clear::before,.cr-clear::after,.cr-clear b,.cr-clear .cr-shd{display:none}
.cr-man{position:absolute;left:-23px;bottom:-1px;width:24px;height:44px;transition:opacity .45s,transform .45s}
.cr-man svg{display:block;width:24px;height:44px;overflow:visible}
.cr-man .lm{stroke:var(--ink)}.cr-man .lg{fill:#2B3A55}
:root[data-theme="dark"] .cr-man .lg{fill:#8191AE}@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .cr-man .lg{fill:#8191AE}}
.cr-man .arm{transform-origin:17px 19px;transform:rotate(68deg);transition:transform .3s}
.cr-man .hd{transform-origin:12px 14px;transition:transform .4s}
.cr-mark:not(.cr-due) .cr-man .hd{transform:rotate(-8deg)}
.cr-man.sig .arm{animation:cr-pat .42s ease-in-out infinite alternate}
@keyframes cr-pat{from{transform:rotate(-4deg)}to{transform:rotate(22deg)}}
.cr-man.ok .arm{transform:rotate(-90deg)}
.cr-man.off{opacity:0;transform:translateX(-12px)}
.cr-man[hidden]{display:none}
.cr-dust{position:absolute;bottom:-4px;width:0;height:0;pointer-events:none;z-index:3}
.cr-dust i{position:absolute;left:-9px;top:-9px;width:18px;height:18px;border-radius:50%;background:var(--ink-3);opacity:0;animation:cr-puff .75s ease-out forwards}
.cr-dust i:nth-child(2){--dx:-34px;animation-delay:.03s}.cr-dust i:nth-child(3){--dx:30px;animation-delay:.06s}.cr-dust i:nth-child(1){--dx:-6px}
@keyframes cr-puff{0%{opacity:.4;transform:translate(0,0) scale(.4)}100%{opacity:0;transform:translate(var(--dx),-16px) scale(1.9)}}
@media print{.cr-mark,.cr-rig,.cr-dust{display:none}.cr-wait>*{opacity:1!important}}
.closer .cl{grid-template-columns:auto minmax(0,1fr) 300px}
.topout{margin:0;align-self:end}
.topout svg{display:block;width:100%;height:auto;overflow:visible}
.closer .cl>div{display:flex;flex-direction:column;align-self:stretch}
.closer .tonote{margin:auto 0 0;padding-top:26px;max-width:46ch;font-size:13px;line-height:1.5;color:var(--ink-3)}
.closer .rebuild{display:block;margin-top:8px;padding:0;border:0;background:none;color:var(--ink);font:600 11.5px/1.4 "Martian Mono",ui-monospace,monospace;text-decoration:underline;text-underline-offset:3px;cursor:pointer}
.closer .rebuild:hover,.closer .rebuild:focus-visible{color:var(--brand)}
.closer .rebuild[hidden]{display:none}
.topout{--glass:#BCCED6;--mul:rgba(16,19,22,.22);--plate:#F4F4EF;--tk:#101316;--tl:#101316;--tg:#5F6B4F}
:root[data-theme="dark"] .topout{--glass:#22333C;--mul:rgba(231,234,229,.16);--plate:#101316;--tk:#8A938D;--tl:#E7EAE5;--tg:#3D4A35}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .topout{--glass:#22333C;--mul:rgba(231,234,229,.16);--plate:#101316;--tk:#8A938D;--tl:#E7EAE5;--tg:#3D4A35}}
.topout .gnd{fill:var(--tg)}
.topout .crn{fill:#FBB401;stroke:#101316;stroke-width:2}.topout .lat{fill:none;stroke:#101316;stroke-width:1.2}
.topout .tie{stroke:var(--tk);stroke-width:1.5}.topout .cw{fill:#101316;stroke:var(--tk);stroke-width:1.5}
.topout .fl .gl{fill:var(--glass)}.topout .fl .ml{stroke:var(--mul);stroke-width:1.2}.topout .fl .sl,.topout .fl .col{fill:var(--tk)}
.topout .fl .pl{fill:var(--plate);transition:fill .2s}
.topout .fl text{font:700 9.6px/1 "Martian Mono",ui-monospace,monospace;fill:var(--tl);letter-spacing:.04em;text-transform:uppercase;transition:fill .2s}
.topout .fl:hover .pl,.topout .fl:focus-visible .pl{fill:#FBB401}.topout .fl:hover text,.topout .fl:focus-visible text{fill:#101316}
.topout .fl:focus{outline:none}.topout .fl:focus-visible .gl{stroke:#FBB401;stroke-width:3}
.topout .fl .gl,.topout .fl .ml,.topout .fl .sl,.topout .fl .col,.topout .fl .pl{transition:opacity .2s,fill .2s}
.topout.pre .fl:not(.on) .gl{fill:transparent;stroke:var(--ink-3);stroke-dasharray:5 4}
.topout.pre .fl:not(.on) .ml,.topout.pre .fl:not(.on) .sl,.topout.pre .fl:not(.on) .col,.topout.pre .fl:not(.on) .pl{opacity:0}.topout.pre .fl:not(.on) text{fill:var(--ink-3)}
.topout .hb{fill:#101316;stroke:var(--tl);stroke-width:1}
.topout .beam{fill:#F4F4EF;stroke:#101316;stroke-width:2}.topout .tree{fill:#1E7B4A;stroke:#101316;stroke-width:1.5;stroke-linejoin:round}
.topout .pole{stroke:var(--tl);stroke-width:2}.topout .flag{fill:#FBB401;stroke:#101316;stroke-width:1.2;transform-box:fill-box;transform-origin:left center;animation:to-flag 2.6s ease-in-out infinite}
@keyframes to-flag{0%,100%{transform:skewY(0)}50%{transform:skewY(-9deg) scaleX(.9)}}
.topout .cbl{fill:var(--tl)}.topout .sling{stroke:var(--tl);stroke-width:1.3;fill:none}.topout .hook{fill:none;stroke:var(--tl);stroke-width:2.2;stroke-linecap:round}
.topout .lift{transform:translateY(-22px)}.topout .sling{opacity:0}
.topout .stamp{transform:rotate(-5deg);transform-box:fill-box;transform-origin:center}.topout .stamp rect{fill:none;stroke:#C42B1C;stroke-width:3}.topout .stamp text{font:800 23px/1 "Big Shoulders Display","Arial Narrow",sans-serif;fill:#C42B1C;letter-spacing:.06em}
:root[data-theme="dark"] .topout .stamp rect{stroke:#FF7A6E}:root[data-theme="dark"] .topout .stamp text{fill:#FF7A6E}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .topout .stamp rect{stroke:#FF7A6E}:root:not([data-theme="light"]) .topout .stamp text{fill:#FF7A6E}}
.topout.pre:not(.go) .lw{transform:translateY(-26px)}
.topout.pre:not(.go) .lift{transform:none}.topout.pre:not(.go) .sling{opacity:1}
.topout.pre:not(.go) .stamp,.topout.pre:not(.go) .flagg{opacity:0}
.topout.go .lw{animation:to-lower 1.6s cubic-bezier(.3,.55,.35,1) both}
.topout.go .lift{animation:to-lift .9s ease-in 1.9s both}.topout.go .sling{animation:to-out .25s linear 1.8s both}
.topout.go .flagg{animation:to-in .3s ease-out 1.7s both}
.topout.go .stamp{animation:to-stamp .32s cubic-bezier(.3,1.4,.5,1) 2.5s both;transform-box:fill-box;transform-origin:center}
@keyframes to-lower{from{transform:translateY(-26px)}to{transform:none}}
@keyframes to-lift{from{transform:none}to{transform:translateY(-22px)}}
@keyframes to-in{from{opacity:0}to{opacity:1}}@keyframes to-out{from{opacity:1}to{opacity:0}}
@keyframes to-stamp{0%{opacity:0;transform:scale(1.35) rotate(-5deg)}60%{opacity:1;transform:scale(.98) rotate(-5deg)}100%{opacity:1;transform:scale(1) rotate(-5deg)}}
@media (prefers-reduced-motion:reduce){.topout .flag{animation:none}}
@media (max-width:1100px){.closer .cl{grid-template-columns:auto minmax(0,1fr)}.topout{grid-column:1/-1;justify-self:center;width:min(100%,320px)}}
@media (max-width:720px){.closer .cl{grid-template-columns:minmax(0,1fr)}}
"""

BUILD_JS = r'''<script>(function(){
var rm=window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches,secs=[].slice.call(document.querySelectorAll("main .sec"));
if(rm||!window.IntersectionObserver||!secs.length||!document.body.animate){if(secs.length)console.info("Topping Out: the crane is off (reduced motion).");return}
var rb=document.querySelector(".closer .rebuild");if(rb){rb.hidden=false;rb.addEventListener("click",function(){if("scrollRestoration" in history)history.scrollRestoration="manual";scrollTo(0,0);location.reload()})}
var NS="http://www.w3.org/2000/svg",heads=[],MAN='<svg viewBox="0 0 24 44"><rect class="lg" x="7" y="30" width="4" height="13"/><rect class="lg" x="13" y="30" width="4" height="13"/><path class="lm" d="M6 42h6M12 42h6" stroke-width="2.4"/><rect x="5.5" y="16.5" width="13" height="15" rx="2" fill="#FBB401" stroke="#101316" stroke-width="1.4"/><rect x="5.5" y="24" width="13" height="2.2" fill="#E8EDF0"/><path class="lm" d="M7 18L3.5 29" stroke-width="2.6" stroke-linecap="round"/><g class="arm"><path class="lm" d="M17 19h7" stroke-width="2.6" stroke-linecap="round"/><circle cx="24.6" cy="19" r="1.7" fill="#E7B48F" stroke="#101316" stroke-width=".8"/></g><g class="hd"><circle cx="12" cy="11" r="4.2" fill="#E7B48F" stroke="#101316" stroke-width="1"/><path d="M6.6 9.6a5.4 5.2 0 0 1 10.8 0h1.7v1.7H4.9V9.6z" fill="#F4F4EF" stroke="#101316" stroke-width="1"/></g></svg>';
function fire(i){document.dispatchEvent(new CustomEvent("sv:built",{detail:i}))}
function el(tag,cls,parent){var e=document.createElementNS(NS,tag);if(cls)e.setAttribute("class",cls);if(parent)parent.appendChild(e);return e}
function done(h){if(h._done)return;h._done=1;io.unobserve(h);h.classList.remove("cr-wait");var m=h._mark,man=h._man;m.classList.add("cr-clear");fire(h._i);
 /* the banksman gives the all clear and walks off */
 man.classList.remove("sig");man.classList.add("ok");setTimeout(function(){man.classList.add("off")},1100);setTimeout(function(){if(m.parentNode)m.parentNode.removeChild(m)},1600)}
function gutter(h,man){var mn=document.querySelector("main");man.hidden=!mn||h.getBoundingClientRect().left-mn.getBoundingClientRect().left<30}
/* the load: from the number plate to the sign (or the end of the title), slung from one hook */
function span(h){var b=h.getBoundingClientRect(),a=h.querySelector(".n"),z=h.querySelector(".hsign")||h.querySelector("h2"),x1=a?a.getBoundingClientRect().left-b.left:0,
 x2=z?z.getBoundingClientRect().right-b.left:b.width,y=z?Math.min(0,z.getBoundingClientRect().top-b.top):0;return [x1,x2,y]}
function lift(h){if(h._done||h._going)return;var b=h.getBoundingClientRect();if(b.bottom<0||b.top>innerHeight){done(h);return}
 h._going=1;var sp=span(h),x1=sp[0],x2=sp[1],y0=sp[2],w=x2-x1,xc=x1+w/2,rise=Math.max(56,Math.min(120,w*.16)),hy=y0-rise,D=b.top-hy+60,
 tilt=Math.max(.7,Math.min(4,170/w)),rig=document.createElement("div"),sv=el("svg");rig.className="cr-rig";rig.setAttribute("aria-hidden","true");
 sv.setAttribute("width","1");sv.setAttribute("height","1");
 var c=el("line","cb",sv);c.setAttribute("x1",xc);c.setAttribute("x2",xc);c.setAttribute("y1",hy-30-4000);c.setAttribute("y2",hy-30);
 var k=el("path","blk",sv);k.setAttribute("d","M"+(xc-14)+" "+(hy-40)+"h28l3 7v15l-5 4h-24l-5-4v-15z");
 var hz=el("path","hz",sv);hz.setAttribute("d","M"+(xc-15)+" "+(hy-22)+"h30v3h-30zM"+(xc-11)+" "+(hy-22)+"l3 3h-3zM"+(xc-3)+" "+(hy-22)+"l3 3h-6zM"+(xc+5)+" "+(hy-22)+"l3 3h-6z");
 var bs=el("circle","sh",sv);bs.setAttribute("cx",xc);bs.setAttribute("cy",hy-31);bs.setAttribute("r",5.5);
 var b2=el("circle","sh2",sv);b2.setAttribute("cx",xc);b2.setAttribute("cy",hy-31);b2.setAttribute("r",1.8);
 var hk=el("path","hk",sv);hk.setAttribute("d","M"+xc+" "+(hy-14)+"v9a6.5 6.5 0 1 1 -6.5 6.5");
 /* the load tag: what this lift weighs, in the page's own kilobytes */
 var kb=(h.parentNode.textContent.replace(/\s+/g," ").length/1024).toFixed(1),ts=el("path","tgs",sv);ts.setAttribute("d","M"+xc+" "+(hy+9)+"v11");
 var tw=104,tg=el("rect","tg",sv);tg.setAttribute("x",xc-tw/2);tg.setAttribute("y",hy+20);tg.setAttribute("width",tw);tg.setAttribute("height",17);tg.setAttribute("rx",2);
 var tx=el("text",null,sv);tx.setAttribute("x",xc);tx.setAttribute("y",hy+31.8);tx.setAttribute("text-anchor","middle");tx.textContent="LIFT 0"+(h._i+1)+" \u00b7 "+kb+" kB";
 [x1+6,x2-6].forEach(function(x){var l=el("path","sl",sv);l.setAttribute("d","M"+xc+" "+(hy+4)+"L"+x+" "+(y0+2))});
 rig.appendChild(sv);h.appendChild(rig);[ts,tg,tx].forEach(function(e){sv.appendChild(e)});
 try{tw=tx.getComputedTextLength()+16;tg.setAttribute("x",xc-tw/2);tg.setAttribute("width",tw)}catch(e){}
 /* the set-out marks stay where the load will land */
 var m=h._mark,sec=h.parentNode;m.style.cssText="inset:auto;top:"+(h.offsetTop-6)+"px;left:"+(h.offsetLeft-8)+"px;width:"+(h.offsetWidth+16)+"px;height:"+(h.offsetHeight+7)+"px";m.classList.add("cr-due");sec.appendChild(m);gutter(h,h._man);h._man.classList.add("sig");
 h._shd.animate([{opacity:0,transform:"scaleX(.45)"},{opacity:1,transform:"scaleX(1)"}],{duration:1050,easing:"ease-in",fill:"forwards"});
 h.classList.remove("cr-wait");h.classList.add("cr-fly");h.style.transformOrigin=xc+"px "+hy+"px";
 var T="translateY(",a=h.animate([{transform:T+(-D)+"px) rotate("+tilt+"deg)",easing:"cubic-bezier(.32,.18,.42,1)"},{transform:T+"5px) rotate("+(-tilt*.55)+"deg)",offset:.7,easing:"ease-in-out"},
  {transform:T+"-1px) rotate("+(tilt*.25)+"deg)",offset:.84,easing:"ease-in-out"},{transform:T+"0) rotate("+(-tilt*.08)+"deg)",offset:.94},{transform:"none"}],{duration:1500});
 a.onfinish=function(){h.classList.remove("cr-fly");h.style.transformOrigin="";
  [x1+6,x2-6].forEach(function(x){var d=document.createElement("span");d.className="cr-dust";d.style.left=x+"px";d.innerHTML="<i></i><i></i><i></i>";h.appendChild(d);
   setTimeout(function(){if(d.parentNode)d.parentNode.removeChild(d)},900)});
  done(h);
  /* the slings let go and the hook goes back up for the next load */
  setTimeout(function(){var up=rig.animate([{transform:"none",opacity:1},{transform:"translateY("+(-(h.getBoundingClientRect().top-hy+200))+"px)",opacity:1,offset:.85},{transform:"translateY("+(-(h.getBoundingClientRect().top-hy+260))+"px)",opacity:0}],
   {duration:900,easing:"cubic-bezier(.5,0,.75,.4)",fill:"forwards"});up.onfinish=function(){if(rig.parentNode)rig.parentNode.removeChild(rig)}},280)}}
var free=0,io=new IntersectionObserver(function(es){es.forEach(function(e){if(!e.isIntersecting)return;var h=e.target;io.unobserve(h);
 var now=Date.now(),at=Math.max(now,free);free=at+350;setTimeout(function(){lift(h)},at-now)})},{rootMargin:"0px 0px -28% 0px"});
secs.forEach(function(s,i){var h=s.querySelector(".sec-h");if(!h)return;h._i=i;var b=h.getBoundingClientRect();
 if(b.top<innerHeight*.9){fire(i);return}
 var m=document.createElement("div"),t=document.createElement("b");m.className="cr-mark";m.setAttribute("aria-hidden","true");
 t.textContent="Level 0"+(i+1)+" \u00b7 set out, awaiting the crane";m.appendChild(t);h.appendChild(m);h._mark=m;
 var sd=document.createElement("i"),man=document.createElement("span");sd.className="cr-shd";man.className="cr-man";man.innerHTML=MAN;m.appendChild(sd);m.appendChild(man);h._shd=sd;h._man=man;gutter(h,man);h.classList.add("cr-wait");heads.push(h);io.observe(h)});
/* arriving by a link or an address: that heading is simply in place */
function arrive(id){var t=id&&document.getElementById(id),s=t&&t.closest&&t.closest("main .sec"),h=s&&s.querySelector(".sec-h");if(h&&h._mark&&!h._going)done(h)}
document.addEventListener("click",function(e){var a=e.target.closest&&e.target.closest("a[href*='#']");if(!a)return;
 var u=new URL(a.getAttribute("href"),location.href);if(u.pathname===location.pathname&&u.hash)arrive(decodeURIComponent(u.hash.slice(1)))},true);
addEventListener("hashchange",function(){arrive(decodeURIComponent(location.hash.slice(1)))});
if(location.hash)arrive(decodeURIComponent(location.hash.slice(1)));
})();
(function(){var t=document.getElementById("topout");if(!t)return;
var rm=window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches,fl=[].slice.call(t.querySelectorAll(".fl"));
if(rm||!window.IntersectionObserver||!document.querySelector("main .sec")||document.documentElement.classList.contains("sv-done"))return;
t.classList.add("pre");
document.addEventListener("sv:built",function(e){if(fl[e.detail])fl[e.detail].classList.add("on")});
var io=new IntersectionObserver(function(es){if(!es[0].isIntersecting)return;io.disconnect();
 var left=fl.filter(function(f){return !f.classList.contains("on")});
 (function next(){var f=left.shift();if(f){f.classList.add("on");setTimeout(next,150)}else setTimeout(function(){t.classList.add("go")},250)})()},{threshold:.6});
io.observe(t)})();
</script>'''


TOPOUT_NOTE = ('<p class="tonote">Each floor is a section of this page. A project tops out when every job on its board is done.'
               '<button type="button" class="rebuild" hidden>Knock it down and build it again &#8635;</button></p>')


def topout_svg(floors) -> str:
    """The closer's building: one floor per front-page section, bottom up, each a link to its section; the crane
    lowers the last beam with its tree onto the roof."""
    out = ['<figure class="topout" id="topout"><svg viewBox="0 0 304 330" role="group" aria-label="The building this page put up: one floor per section, and the last beam with its tree on top">',
           '<defs><clipPath id="to-clip"><rect x="0" y="53" width="300" height="277"/></clipPath></defs>',
           '<rect class="gnd" x="0" y="312" width="300" height="18"/>']
    # crane: mast, jib, ties, counterweight, cab, trolley
    out.append('<path class="tie" d="M47 14L16 40M47 14L290 40"/>'
               '<rect class="crn" x="40" y="40" width="14" height="272"/>'
               '<path class="lat" d="' + "".join(f"M40 {y}L54 {y + 17}L40 {y + 34}" for y in range(40, 279, 34)) + '"/>'
               '<rect class="crn" x="14" y="40" width="276" height="9"/>'
               '<path class="lat" d="' + "".join(f"M{x} 40L{x + 9} 49L{x + 18} 40" for x in range(58, 282, 18)) + '"/>'
               '<path class="crn" d="M47 14L40 40H54Z"/>'
               '<rect class="cw" x="14" y="49" width="24" height="15"/><rect class="crn" x="54" y="49" width="15" height="13"/>'
               '<rect class="cw" x="195" y="49" width="16" height="5"/>')
    for k, (sid, title) in enumerate(floors, 1):
        y = 312 - k * 26
        label = f"{k:02d} {html.unescape(title)}"
        plate = max(len(f"00 {html.unescape(t)}") for _s, t in floors) * 8.3 + 10
        mull = "".join(f"M{x} {y + 3}v23" for x in range(128, 295, 18))
        out.append(f'<a class="fl" href="#{sid}" aria-label="Floor {k:02d}: {title}"><title>Floor {k:02d}: {title}</title>'
                   f'<rect class="gl" x="110" y="{y}" width="185" height="26"/><path class="ml" d="{mull}"/>'
                   f'<rect class="sl" x="105" y="{y}" width="195" height="3.5"/>'
                   f'<rect class="col" x="110" y="{y}" width="6" height="26"/><rect class="col" x="289" y="{y}" width="6" height="26"/>'
                   f'<rect class="pl" x="120" y="{y + 7.5}" width="{plate:.0f}" height="16"/>'
                   f'<text x="125" y="{y + 18.9}">{esc(label)}</text></a>')
    # the load: last beam, tree and flag; the cable, slings and hook lift away once it is set
    out.append('<g clip-path="url(#to-clip)"><g class="lw"><rect class="beam" x="133" y="124" width="140" height="6"/>'
               '<path class="tree" d="M203 96L194 110H198L190 124H216L208 110H212Z"/>'
               '<g class="flagg"><path class="pole" d="M258 124V99"/><path class="flag" d="M259 99H275L271 104L275 109H259Z"/></g>'
               '<g class="lift"><rect class="cbl" x="202.3" y="-200" width="1.6" height="282"/><rect class="hb" x="198" y="78" width="10" height="6"/>'
               '<path class="sling" d="M203 86L140 124M203 86L266 124"/><path class="hook" d="M203 84v3"/></g></g></g>')
    out.append('<g class="stamp"><rect x="66" y="70" width="112" height="36"/><text x="122" y="96" text-anchor="middle">TOPPED OUT</text></g>')
    out.append('</svg></figure>')
    return "".join(out)


# ---------- the Order of works sheet: the landing page's 11 steps, each opening into build_flow.py's detailed steps ----------
def flow_phases() -> list:
    """build_flow.py's PHASES, read from its source without running the page writer (the dev session owns the file)."""
    src = (SCRIPTS / "build_flow.py").read_text(encoding="utf-8")
    ns = {"__file__": str(SCRIPTS / "build_flow.py")}
    exec(src[:src.index('CSS = r"""')], ns)
    return ns["PHASES"]


# which detailed steps sit under which of the 11 (titles exactly as build_flow.py has them; the build checks every one is placed once)
ORDER_MAP = {
    "Shape the idea": ["Bring the idea", "Survey it"],
    "Write the plan": ["Write the blueprint"],
    "Check the plan": ["Cold read of the blueprint", "Settle every finding"],
    "Cut into tickets": ["Cut it into jobs", "Approve the cut", "Board v1"],
    "Start the shift": ["Open a fresh session", "Stand up as foreman", "Site walk", "Pre-flight", "Say go", "Mark it started"],
    "Build": ["Work order 1: setup and t0", "Scoping", "The plan and gate 1", "Write the work order", "Pass the pointer", "Build it", "Review it"],
    "Inspect": ["Base versus head", "Gate 2", "Lens inspection", "Check every finding", "Fix what was accepted", "Pack the review", "Cross-model review", "Adjudicate", "Final re-run and the ledger"],
    "Open the PR": ["PR body", "Open the PR"],
    "Review the PR": ["Greptile rounds", "PR description check"],
    "Merge": ["Merge", "Clean up"],
    "Close": ["Close the job", "Dev report", "Next-ticket decision", "Confirm the next job", "Ground investigation", "Board close", "Shift handover and opener", "Top out (when the head is reached)", "Push the records"],
}
# The Order of works page's own short line per smaller step. build_flow.py belongs to the development session and
# keeps the full text; the build checks every smaller step has one here.
ORDER_SHORT = {'Bring the idea': 'What you want built, in your words.',
    'Survey it': 'Every open question settled against the code.',
    'Write the blueprint': 'One plan: decisions, acceptance checks, tasks.',
    'Cold read of the blueprint': 'One to five other AI models read it cold.',
    'Settle every finding': 'Each finding applied or answered. None left open.',
    'Cut it into jobs': 'One ticket per job, one PR each. Shown to you first.',
    'Approve the cut': 'Two words: one to write it, one to publish the board.',
    'Board v1': 'The board page you follow. The first job is marked next.',
    'Open a fresh session': 'Paste the opener the last job left.',
    'Stand up as foreman': "Loads the rules, the playbook and this job's lessons.", 'Site walk': 'Quiz answered cold, machine and ticket checked. Then stop.',
    'Pre-flight': 'The builder proves its tools work: ready or blocked.',
    'Say go': 'Choosing the ticket is not saying go.',
    'Mark it started': 'In progress on the board.',
    'Work order 1: setup and t0': 'Worktree, job record, a baseline of every check. No code.',
    'Scoping': 'Every design fork settled, with what was rejected.',
    'The plan and gate 1': 'Tasks and tests that must fail first, then a cold read.',
    'Write the work order': 'One outcome, exact commands, a pinned commit.',
    'Pass the pointer': 'One line to the builder, by hand or over the pane link.',
    'Build it': 'Failing tests first, then code. One commit, a report, stop.',
    'Review it': 'Disk before words. The foreman probes it itself.',
    'Base versus head': 'Every affected test, before and after. Red only after: stop.',
    'Gate 2': 'Every commit against its review, and the safety fact.',
    'Lens inspection': 'Fresh reviewers, findings only. No PR yet.',
    'Check every finding': 'Each one reproduced. Only accepted ones go back.',
    'Fix what was accepted': 'Test-first repairs, reviewed like any other.',
    'Pack the review': 'One blind brief. Nothing names the builder.',
    'Cross-model review': "Another company's model reviews it cold.", 'Adjudicate': 'Every claim reproduced. Accepted fixes become work orders.',
    'Final re-run and the ledger': 'Everything again at the final commit. Every requirement passes, or no PR.',
    'PR body': 'What changed, the proof, the limits, the review record.',
    'Open the PR': 'Pushed and opened. Opening is not merging.',
    'Greptile rounds': 'Scored out of 5, findings fixed. Three rounds at most.',
    'PR description check': 'Re-read against the final code before you are asked to merge.',
    'Merge': 'Then checked: what landed is what was reviewed.',
    'Clean up': 'Branch and worktrees removed. The tracker waits for your word.',
    'Close the job': 'Only when merged and every requirement passed.',
    'Dev report': "The day's lesson and the foreman's scorecard.", 'Next-ticket decision': 'The foreman recommends the next job from the board.',
    'Confirm the next job': 'Say yes, or pick another. Under a /goal it decides.',
    'Ground investigation': 'Four research agents look into the next job.',
    'Board close': 'Merged, and the next job named. One new version.',
    'Shift handover and opener': 'Notes, a quiz and the next opener, ready to paste.',
    'Top out (when the head is reached)': 'Every job done: the board is frozen as the record, with a report and three to five next heads.',
    'Push the records': 'The records pushed. The job ends.'}
# words the flow does not mark but the method does: confirming the next job is the owner's (METHOD.md section 10, step 7a)
ORDER_WORDS = {"Confirm the next job": "yes"}

# Your repo's short names for SETUP.md's job moments; a moment not listed keeps SETUP.md's own words
REPO_MOMENTS = {'The board is checked and you say "go"': "You say go", "After the merge (`/f-signoff`)": "After the merge", "Then, in order": "The end game"}

# The Logbook page's example INSIGHT card, written from METHOD.md section 7 (mutation probes) and section 14's own example.
# Its headings must be the INSIGHT template's, in order; if the template changes, the build stops.
INSIGHT_EXAMPLE = [
    ("Overview", "A mutation probe that stays GREEN means no test covers that guard. Re-aiming the probe until it bites hides the gap instead of closing it."),
    ("Impact", "A guard ships with no test behind it, while the report says every probe bites."),
    ("Pattern Structure", "Signal: a probe stays GREEN. Cause: the builder moves the probe somewhere a test does catch. Result: the probe bites and the missing test stays missing."),
    ("Anti-Pattern", "Treating GREEN as a broken probe and fixing the probe. In one job, a well-shaped forged value was refused only by the guard, and no test covered it."),
    ("Evidence", "Two builders, in two jobs, re-aimed a GREEN probe; both times it hid a missing test (`METHOD.md` section 7)."),
    ("Applications", "On GREEN the builder reports and stops (work order rule 7). Before sending a work order, the foreman checks every probe anchor still matches once."),
]

ORDER_NOTES = {
    "Build": ("Repeat per task.", "Each task gets its own work order, build and review, until every task is built. Repairs go test-first into the next work order."),
    "Cut into tickets": ("Or skip the plan: an iteration board.", "For work found while testing a product: no blueprint, small jobs added as they turn up "
                         "(f-board, init --iteration). It tops out the same way."),
    "Close": ("Back to 05 with the next job.", "Until every job on the list is merged or decided. On a night shift, the next job starts by itself. "
              "When the last job closes, the board tops out instead: frozen as the record, a report, and three to five next heads for you to pick from."),
}
ACTOR_ROLE = {"op": "you", "or": "foreman", "bu": "builder", "rv": "inspectors"}
GLOSSARY = [
    ("Ticket", "One piece of work from the plan. One job builds one ticket."),
    ("Blueprint", "The full plan for a project, written before any code."),
    ("Work order", "A short, exact instruction the foreman writes for the builder: one task, the commands to run, the code it starts from."),
    ("Worktree", "A separate working copy of the repo, so a job's changes never touch your main copy until they are merged."),
    ("VP", "A verification point: something that must be true when the work is done, with the way to check it."),
    ("t0", "The test results captured before any change, so every later result can be compared with them."),
    ("Base versus head", "Running the tests on the code before the job (base) and after it (head), to see exactly what the job changed."),
    ("Gate 1, gate 2", "Check points the job must pass: gate 1 checks the job's plan, gate 2 the finished build."),
    ("Cold read", "A review by someone who did not see the work being made, so it shares none of its assumptions."),
    ("Model family", "AI models from one company. A reviewer from another family has different blind spots."),
    ("Pull request (PR)", "A request to merge the job's branch, where the change is reviewed before it lands."),
    ("Greptile", "An automated pull-request reviewer. It reviews each pull request, up to three rounds."),
    ("Acceptance ledger", "Every requirement with its check and its result. Every row must pass before the job closes."),
    ("Opener, handover", "What one session leaves the next: a short opener to paste, and the notes on where the job ended."),
    ("D- decisions", "Design decisions in the plan, labelled D- and a letter, each settled down to the exact detail before a work order uses it."),
    ("H1 to Hn", "The hostile inputs a work order lists for its task, such as missing keys or wrong types. Each one needs a test."),
    ("G1 to G6", "The standard gap checklist in every work order: cancellation, deadlines, fields reaching their destination, every error path tested, many-item cases, typed errors for bad input."),
    ("HEAD", "The latest commit on a branch. A work order names the exact one it starts from."),
]

ORDER_CSS = r"""
.wrap{max-width:1180px;margin:0 auto;padding:0 32px}
.ohead{padding:40px 0 18px}
.ohead .eyebrow{font:600 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--brand)}
.ohead h1{margin:12px 0 14px;font:800 clamp(44px,7vw,80px)/.9 "Big Shoulders Display","Arial Narrow",Impact,sans-serif;text-transform:uppercase}
.ohead .lede{max-width:66ch;color:var(--ink-2);margin:0;font-size:17px}
.ostats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border:2px solid var(--ink);margin:22px 0 0}
.ostats div{padding:12px 14px;border-left:1px solid var(--line)}.ostats div:first-child{border-left:0}
.ostats b{display:block;font:800 34px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;color:var(--brand)}
.ostats span{font-size:13px;color:var(--ink-2)}
.obar{position:sticky;top:0;z-index:5;display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:12px 0;margin:18px 0 6px;background:var(--ground);border-bottom:1px solid var(--line)}
.obar .lbl{font:600 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);margin-right:4px}
.obar button{display:inline-flex;align-items:center;gap:7px;font:600 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.04em;padding:8px 10px;border:2px solid var(--line);background:var(--panel);color:var(--ink);cursor:pointer}
.obar button[aria-pressed="true"]{border-color:var(--ink);background:var(--ink);color:var(--ground)}
.obar button.word[aria-pressed="true"]{background:var(--hivis);color:#101316;border-color:#101316}
.obar .sp{flex:1}
.obar .sh{width:11px;height:11px;display:inline-block}
.sh-you{background:#FBB401;transform:rotate(45deg);border:1.5px solid #101316}.sh-foreman{background:#5AA0F0;border-radius:50%}.sh-builder{background:#6FBF73}
.sh-inspectors{width:0!important;height:0!important;border-left:6px solid transparent;border-right:6px solid transparent;border-bottom:11px solid #C38BD9}
.opart{margin:30px 0 10px;display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
.opart h2{margin:0;font:800 28px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.opart span{color:var(--ink-3);font-size:14px}
.olist{list-style:none;margin:0;padding:0;border-top:3px solid var(--ink)}
.ostep{border-bottom:1px solid var(--line)}
.ostep>summary{list-style:none;display:grid;grid-template-columns:44px 40px minmax(0,1fr) auto;gap:14px;align-items:start;padding:16px 8px 16px 0;cursor:pointer}
.ostep>summary::-webkit-details-marker{display:none}
.ostep .on{font:800 26px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;color:var(--brand);padding-top:4px}
.ostep .oi{width:40px;height:40px;padding:4px;background:#F4F4EF;border:2px solid #101316}
.ostep h3{margin:2px 0 6px;font:800 24px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.ostep .ow{display:inline-flex;gap:6px;margin-left:10px;vertical-align:4px}
.ostep .ow b{font:600 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;padding:4px 6px 3px;border:1.5px solid currentColor}
.ostep .ow b.r-you{background:var(--hivis);color:#101316;border-color:#101316}
.ostep .op{margin:0;font-size:15px;color:var(--ink);max-width:76ch}
.ostep .orl{margin:6px 0 0;font-size:13.5px;color:var(--ink-2)}
.ostep .orl i{font:600 9.5px/1 "Martian Mono",ui-monospace,monospace;font-style:normal;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);margin-right:6px}
.ostep .oc{align-self:center;display:inline-flex;align-items:center;gap:8px;font:600 11px/1 "Martian Mono",ui-monospace,monospace;color:var(--ink-2);white-space:nowrap;padding:8px 10px;border:2px solid var(--line)}
.ostep .oc::after{content:"+";font:700 15px/1 "Public Sans",sans-serif}
.ostep[open] .oc{border-color:var(--ink);color:var(--ink)}.ostep[open] .oc::after{content:"\2212"}
.ostep>summary:hover .oc,.ostep>summary:focus-visible .oc{border-color:var(--hivis);color:var(--ink)}
.ostep>summary:focus-visible{outline:3px solid var(--focus);outline-offset:2px}
.osubs{list-style:none;margin:0 0 18px 98px;padding:0 0 0 20px;border-left:2px dashed var(--line)}
.osub{position:relative;display:grid;grid-template-columns:52px minmax(0,1fr);gap:12px;padding:12px 0;border-bottom:1px dashed var(--line)}
.osub:last-child{border-bottom:0}
.osub>.sh{position:absolute;left:-27px;top:17px;width:12px;height:12px}
.osub .sn{font:700 11px/1.6 "Martian Mono",ui-monospace,monospace;color:var(--ink-3)}
.osub h4{margin:0 0 4px;font:700 16px/1.25 "Public Sans",system-ui,sans-serif}
.osub h4 small{margin-left:8px;font:600 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);vertical-align:2px}
.osub p{margin:0;font-size:14px;line-height:1.5;color:var(--ink-2);max-width:78ch}
.otags{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.otags a,.otags code,.otags em{font:500 11.5px/1.4 "Martian Mono",ui-monospace,monospace;padding:2px 6px;font-style:normal}
.otags a{color:var(--ink);background:var(--panel-2);text-decoration:none;border-bottom:2px solid var(--brand)}
.otags a:hover{background:var(--hivis);color:#101316}
.otags em{color:var(--ink-3);border:1px dashed var(--line)}
.oword{display:inline-flex;align-items:center;gap:8px;margin-top:8px;background:var(--hivis);color:#101316;padding:4px 8px;font:700 11.5px/1.3 "Martian Mono",ui-monospace,monospace}
.oword i{font-style:normal;font-weight:600;letter-spacing:.1em;text-transform:uppercase;font-size:10px}
.onote{margin:0 0 18px 98px;display:flex;gap:10px;align-items:baseline;padding:10px 14px;border:2px solid var(--ink);background:var(--panel);font-size:14px}
.onote b{font:800 17px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;white-space:nowrap}
.oglos{margin:44px 0 30px;border:3px solid var(--ink);background:var(--panel)}
.oglos h2{margin:0;padding:12px 18px;border-bottom:2px solid var(--ink);font:800 26px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.oglos dl{margin:0;padding:8px 18px 16px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px 32px}
.oglos dl>div{padding:10px 0;border-bottom:1px dashed var(--line)}
.oglos dt{font:700 14px/1.3 "Public Sans",system-ui,sans-serif}
.oglos dd{margin:3px 0 0;font-size:13.5px;color:var(--ink-2)}
.ostep.dim,.osub.dim{display:none}
@media (max-width:860px){.obar{position:static}.wrap{padding:0 16px}.ostats{grid-template-columns:repeat(2,minmax(0,1fr))}.ostats div:nth-child(3){border-left:0}
 .ostep>summary{grid-template-columns:36px minmax(0,1fr);gap:10px}.ostep .oi{display:none}.ostep .oc{grid-column:2;justify-self:start}
 .ostep .ow{display:flex;margin:6px 0 0}.osubs{margin-left:12px}.onote{margin-left:12px;flex-direction:column}.oglos dl{grid-template-columns:minmax(0,1fr)}}
"""

ORDER_DESK_CSS = r"""
.pane.full{grid-template-columns:minmax(0,1fr)}
.srow .sno{flex:none;width:22px;font:800 15px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;color:var(--brand)}
.srow svg{flex:none;width:24px;height:24px;padding:2px;background:#F4F4EF;border:1.5px solid #101316}
.srow b{flex:1}
.srow .yw{flex:none;width:9px;height:9px;background:#FBB401;border:1.5px solid #101316;transform:rotate(45deg);margin-right:3px}
.side .key{display:flex;align-items:center;gap:8px;margin:14px 18px 0;font-size:12px;color:var(--ink-3)}
.side .key i{width:9px;height:9px;background:#FBB401;border:1.5px solid #101316;transform:rotate(45deg)}
.tab svg.si{width:34px;height:34px;padding:3px;background:#F4F4EF;border:2px solid #101316}
.shd{display:flex;align-items:center;gap:14px;margin:0 0 12px}
.shd svg{flex:none;width:52px;height:52px;padding:5px;background:#F4F4EF;border:2px solid #101316}
.shd h4{margin:0}
.who{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.who b{display:inline-flex;align-items:center;gap:6px;font:600 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;padding:4px 7px 3px;border:1.5px solid var(--ink)}
.who b.r-you{background:var(--hivis);color:#101316;border-color:#101316}
.rw2{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);border:2px solid var(--line);margin:4px 0 12px}
.rw2>div{padding:12px 14px}.rw2>div+div{border-left:2px solid var(--line)}
.rw2 h5{margin:0 0 6px;font:700 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3)}
.rw2 p{margin:0;font-size:14.5px;line-height:1.5;color:var(--ink)}
.orule{display:flex;gap:10px;align-items:baseline;margin:0 0 12px;padding:10px 14px;border-left:3px solid var(--ink);background:var(--panel-2);font-size:14.5px}
.orule b,.oyour>b{flex:none;font:700 9.5px/1.6 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.oyour{margin:0 0 12px;padding:10px 14px;border-left:3px solid var(--hivis);background:rgba(251,180,1,.12)}
.oyour ul{list-style:none;margin:6px 0 0;padding:0;display:flex;flex-direction:column;gap:6px}
.oyour li{display:flex;align-items:baseline;gap:10px;font-size:13.5px;color:var(--ink-2)}.oyour li q{font:700 12.5px/1.3 "Martian Mono",ui-monospace,monospace;quotes:none;background:var(--hivis);color:#101316;padding:2px 6px}
.oloop{display:flex;gap:10px;align-items:baseline;margin:0 0 12px;padding:10px 14px;border:2px solid var(--ink);font-size:14px}
.oloop b{flex:none;font:800 16px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.osh{margin:18px 0 0;font:700 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3)}
.omore{margin:4px 0 0;font-size:13.5px;color:var(--ink-3)}
.omore button{font:inherit;color:var(--ink);background:none;border:0;padding:0;text-decoration:underline;text-decoration-color:var(--brand);text-underline-offset:3px;cursor:pointer}
.osubs{list-style:none;margin:6px 0 12px;padding:0;border-top:1px solid var(--line)}
.osub{display:grid;grid-template-columns:52px minmax(0,1fr);gap:12px;padding:11px 0;border-bottom:1px solid var(--line)}
.osub .sn{align-self:start;padding-top:1px;display:flex;align-items:center;gap:7px;font:700 11px/1.6 "Martian Mono",ui-monospace,monospace;color:var(--ink-3)}
.osub h6{margin:0 0 4px;font:700 15px/1.3 "Public Sans",system-ui,sans-serif}
.osub h6 small{margin-left:8px;font:600 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);vertical-align:2px}
.osub p{margin:0;font-size:14px;line-height:1.5;color:var(--ink-2)}
.otags{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.otags a,.otags code,.otags em{font:500 11.5px/1.4 "Martian Mono",ui-monospace,monospace;padding:2px 6px;font-style:normal}
.otags a{color:var(--ink);background:var(--panel-2);text-decoration:none;border-bottom:2px solid var(--brand)}
.otags a:hover{background:var(--hivis);color:#101316}
.otags em{color:var(--ink-3);border:1px dashed var(--line)}
.oword{display:inline-flex;align-items:center;gap:8px;margin-top:8px;background:var(--hivis);color:#101316;padding:4px 8px;font:700 11.5px/1.3 "Martian Mono",ui-monospace,monospace}
.oword i{font-style:normal;font-weight:600;letter-spacing:.1em;text-transform:uppercase;font-size:10px}
.sh{width:10px;height:10px;display:inline-block;flex:none}
.sh-you{background:#FBB401;transform:rotate(45deg);border:1.5px solid #101316}.sh-foreman{background:#5AA0F0;border-radius:50%}.sh-builder{background:#6FBF73}
.sh-inspectors{width:0!important;height:0!important;border-left:6px solid transparent;border-right:6px solid transparent;border-bottom:10px solid #C38BD9}
.gl{margin:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 32px}
.gl>div{padding:11px 0;border-bottom:1px solid var(--line)}
.gl dt{font:700 14.5px/1.3 "Public Sans",system-ui,sans-serif}
.gl dd{margin:3px 0 0;font-size:14px;line-height:1.5;color:var(--ink-2)}
@media (max-width:640px){.oloop{flex-direction:column;gap:4px}.rw2{grid-template-columns:minmax(0,1fr)}.rw2>div+div{border-left:0;border-top:2px solid var(--line)}.gl{grid-template-columns:minmax(0,1fr)}.shd svg{width:40px;height:40px}}

/* the step page in the site's language: a label plate for what it reads and writes, the rule as a striped site sign,
   and the owner's words on a hi-vis tag */
.orw{display:grid;grid-template-columns:auto minmax(0,1fr);margin:6px 0 16px;border:2px solid var(--ink);box-shadow:3px 3px 0 var(--ink)}
.orw dt{display:flex;align-items:center;font:700 9.5px/1.2 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;background:#101316;color:#FBB401;padding:8px 10px}
.orw dd{margin:0;padding:8px 12px;font-size:14.5px;line-height:1.45;color:var(--ink);background:var(--panel)}
.orw dt:first-of-type{border-bottom:1px solid #3A4046}.orw dd:first-of-type{border-bottom:2px solid var(--ink)}
.orule{display:flex;align-items:stretch;gap:0;margin:0 0 16px;padding:0;border:2px solid #101316;background:#FBB401;color:#101316;box-shadow:3px 3px 0 #101316;max-width:560px}
.orule::before{content:"";flex:none;width:10px;background:repeating-linear-gradient(-45deg,#101316 0 5px,#FBB401 5px 10px);border-right:2px solid #101316}
.orule b{display:flex;align-items:center;flex:none;font:700 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;background:#101316;color:#FBB401;padding:0 9px}
.orule span{padding:9px 12px;font:800 17px/1.15 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.oyour{margin:0 0 16px;padding:10px 12px 12px;border:2px solid #101316;background:#FBB401;color:#101316;box-shadow:3px 3px 0 #101316;max-width:560px}
.oyour>b{display:block;font:700 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:#101316}
.oyour>b small{font:inherit;color:#6B4E00;margin-left:6px}
.oyour li{color:#30363B}.oyour li q{background:#101316;color:#FBB401}
.reader .orule span,.reader .oyour,.reader .oyour li{color:#101316}.reader .oyour li span{color:#30363B}.reader .oyour ul{margin:8px 0 0;padding:0}.reader .oyour li{margin:0}
"""

SKILLS_DESK_CSS = r"""
.rhead2 .find{grid-column:2;display:flex;align-items:center;gap:10px;margin-top:10px;padding:0 12px;border:2px solid var(--ink);background:var(--panel);max-width:520px}
.rhead2 .find span{font:700 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3)}
.rhead2 .find input{flex:1;min-width:0;border:0;background:none;padding:10px 0;font:500 15px/1.2 "Public Sans",system-ui,sans-serif;color:var(--ink)}
.rhead2 .find input:focus{outline:none}.rhead2 .find:focus-within{outline:3px solid var(--focus);outline-offset:2px}
.rhead2 .find output{font:600 11px/1 "Martian Mono",ui-monospace,monospace;color:var(--ink-3);white-space:nowrap}
.tab svg.si{width:34px;height:34px;padding:3px;background:#F4F4EF;border:2px solid #101316}
.tab .tn{display:inline-block;min-width:34px;padding:5px 4px 3px;text-align:center;font:800 18px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;background:#FBB401;color:#101316;border:2px solid #101316}
.sk .srow .sno{flex:none;width:22px;font:800 15px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;color:var(--brand)}
.sk .srow b{flex:1;font:600 13.5px/1.2 "Martian Mono",ui-monospace,monospace;text-transform:none}
.sk .srow small{display:block;margin-top:3px;font:500 11.5px/1.3 "Public Sans",system-ui,sans-serif;color:var(--ink-3)}
.sk .side h3{margin:14px 18px 4px}
.shd2{display:flex;align-items:center;gap:14px;margin:0 0 10px}
.shd2 .big{flex:none;width:58px;height:58px;display:flex;flex-direction:column;align-items:center;justify-content:center;background:#FBB401;color:#101316;border:2px solid #101316}
.shd2 .big b{font:800 28px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif}
.shd2 .big span{font:700 8.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase}
.shd2 svg.big{padding:8px;background:#F4F4EF}
.shd2 h4{margin:0;font:700 26px/1.1 "Martian Mono",ui-monospace,monospace;text-transform:none}
.shd2 .meta{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin-top:6px}
.reader .shd2 .meta code{display:inline-flex;align-items:center;padding:5px 8px!important;line-height:1}
.shd2 .meta code{font:600 12px/1 "Martian Mono",ui-monospace,monospace;background:var(--ink);color:var(--panel);padding:5px 7px}
.shd2 .meta a{font:600 11px/1 "Martian Mono",ui-monospace,monospace;color:var(--ink);padding:5px 2px;text-decoration:underline;text-decoration-color:var(--brand);text-underline-offset:3px}
.shd2 .meta em{font:600 9.5px/1 "Martian Mono",ui-monospace,monospace;font-style:normal;letter-spacing:.12em;text-transform:uppercase;padding:5px 7px 4px;border:1.5px solid var(--ink)}
.kb{margin:0 0 12px}
.kb h5{margin:0 0 6px;font:700 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3)}
.kb p{margin:0;font-size:15px;line-height:1.55;color:var(--ink)}
.says{display:flex;flex-wrap:wrap;gap:6px}
.says span{font:500 13px/1.3 "Public Sans",system-ui,sans-serif;padding:4px 9px;border:1.5px dashed var(--ink-3);color:var(--ink)}
.says span::before{content:"\201C"}.says span::after{content:"\201D"}
.knot{display:flex;gap:10px;align-items:baseline;margin:0 0 12px;padding:10px 14px;border-left:3px solid #C42B1C;background:rgba(196,43,28,.07);font-size:14.5px}
.knot b{flex:none;font:700 9.5px/1.6 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:#C42B1C}
:root[data-theme="dark"] .knot b{color:#FF7A6E}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .knot b{color:#FF7A6E}}
.reader .body ul.kchk{display:block}
.kchk{list-style:none;margin:0;padding:0!important;border-top:1px solid var(--line)}
.kchk li{display:grid;grid-template-columns:22px minmax(0,1fr);gap:8px;padding:8px 0;border-bottom:1px solid var(--line);font-size:14.5px;line-height:1.5}
.kchk li::before{content:"";width:12px;height:12px;margin-top:4px;border:2px solid var(--brand)}
.kfull{display:flex;flex-wrap:wrap;align-items:center;gap:14px;margin:16px 0 0}
.kfull a.go{font:700 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.06em;text-transform:uppercase;padding:10px 12px;border:2px solid #101316;background:var(--hivis);color:#101316;text-decoration:none}
.kfull a.go:hover{background:var(--ink);color:var(--panel);border-color:var(--ink)}
.kfull span{font-size:13px;color:var(--ink-3)}
.pane.fnd .side li[hidden]{display:none}
.fgl{margin:12px 18px 2px;font:700 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3)}
.fgl[hidden]{display:none}
.fhint{color:var(--ink-3);font-size:15px}
@media (max-width:1000px){.rhead2 .find{grid-column:1}}

/* the site's language here: a does / when plate, "not for" as a prohibition sign, and a checklist you tick that stamps itself passed */
.orw{display:grid;grid-template-columns:auto minmax(0,1fr);margin:10px 0 14px;border:2px solid var(--ink);box-shadow:3px 3px 0 var(--ink)}
.orw dt{display:flex;align-items:center;font:700 9.5px/1.2 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;background:#101316;color:#FBB401;padding:8px 10px;white-space:nowrap}
.orw dd{margin:0;padding:8px 12px;font-size:14.5px;line-height:1.45;color:var(--ink);background:var(--panel)}
.orw dt:not(:last-of-type){border-bottom:1px solid #3A4046}.orw dd:not(:last-of-type){border-bottom:2px solid var(--ink)}
.knot{align-items:stretch;gap:0;padding:0;border:2px solid #101316;border-left:2px solid #101316;background:#F4F4EF;color:#101316;box-shadow:3px 3px 0 #101316;margin:0 0 16px}
.knot i{flex:none;width:40px;display:grid;place-items:center;background:#C42B1C;border-right:2px solid #101316}
.knot i::before{content:"";width:18px;height:18px;border-radius:50%;border:3px solid #fff;background:linear-gradient(45deg,transparent 42%,#fff 42% 58%,transparent 58%)}
.knot b{display:flex;align-items:center;padding:0 10px;font:800 15px/1 "Big Shoulders Display","Arial Narrow",sans-serif;letter-spacing:.04em;color:#C42B1C!important;white-space:nowrap}
.knot span{padding:9px 12px 9px 0;font-size:14px;color:#101316}
.knot code{background:#FBB401;color:#101316}
.kins{position:relative}
.rhead2 .rmode{grid-column:2;margin:2px 0 0;font-size:13px;color:var(--ink-3)}
@media (max-width:1000px){.rhead2 .rmode{grid-column:1}}
@media (max-width:560px){.knot{flex-wrap:wrap}.knot i{width:40px;min-height:36px}.knot span{flex:1 1 100%;padding:9px 12px;border-top:2px solid #101316}}
/* the full page, offered at the top of every skill: no scrolling to find it */
.shd2 .fullbtn{margin-left:auto;align-self:flex-start;display:grid;grid-template-columns:auto auto;align-items:center;gap:0 10px;padding:8px 10px 8px 12px;background:#FBB401;color:#101316;border:2px solid #101316;box-shadow:3px 3px 0 #101316;text-decoration:none;transition:transform .12s,box-shadow .12s}
.shd2 .fullbtn span{font:800 17px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;letter-spacing:.02em}
.shd2 .fullbtn small{grid-column:1;font:600 9px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;color:#4A3A00}
.shd2 .fullbtn i{grid-column:2;grid-row:1/span 2;font:800 22px/1 "Public Sans",sans-serif;font-style:normal}
.shd2 .fullbtn:hover,.shd2 .fullbtn:focus-visible{transform:translate(-2px,-2px);box-shadow:5px 5px 0 #101316}
@media (max-width:640px){.shd2{flex-wrap:wrap}.shd2 .fullbtn{margin-left:0;width:100%;grid-template-columns:1fr auto}}
"""

COPY_JS = '<script>(function(){var tip;function say(t){if(!tip){tip=document.createElement("div");tip.className="cptip";tip.setAttribute("role","status");document.body.appendChild(tip)}tip.textContent="Copied: "+t;tip.classList.add("on");clearTimeout(say.t);say.t=setTimeout(function(){tip.classList.remove("on")},1400)}function copy(t){if(navigator.clipboard&&window.isSecureContext)return navigator.clipboard.writeText(t);var a=document.createElement("textarea");a.value=t;a.style.position="fixed";a.style.opacity="0";document.body.appendChild(a);a.select();try{document.execCommand("copy")}catch(e){}a.remove();return Promise.resolve()}function go(el){var t=el.getAttribute("data-copy");Promise.resolve(copy(t)).then(function(){say(t);el.classList.add("copied");setTimeout(function(){el.classList.remove("copied")},900)},function(){say(t)})}document.addEventListener("click",function(e){var el=e.target.closest("[data-copy]");if(el)go(el)});document.addEventListener("keydown",function(e){var el=e.target.closest&&e.target.closest("[data-copy]");if(el&&(e.key==="Enter"||e.key===" ")){e.preventDefault();go(el)}})})()</script>'

WELCOME_JS = '<script>(function(){var K="to-welcome";var force=/[?&]welcome(=|&|$)/.test(location.search);try{if(!force&&localStorage.getItem(K))return}catch(e){if(!force)return}if(!force&&/about\\.html$/.test(location.pathname))return;\nvar home=document.querySelector(".brand"),base=home?home.getAttribute("href").replace(/index\\.html$/,""):"";\nvar w=document.createElement("aside");w.className="welcome";w.setAttribute("role","dialog");w.setAttribute("aria-label","Welcome");\nw.innerHTML=\'<img class="wbadge" src="\'+base+\'assets/brand/kai-badge-160.png" alt="" width="96" height="96"><div class="wbub"><button type="button" class="wx" aria-label="Close">&times;</button>\'\n +\'<p><b>Yo, what\\u2019s up.</b> Glad something sparked your interest enough to pop in. I\\u2019m Kai: three years building AI coding systems, and Topping Out is the latest. Have a look around.</p>\'\n +\'<div class="wact"><button type="button" class="wgo">Show me around</button><a href="\'+base+\'about.html">Who\\u2019s Kai? &rarr;</a></div></div>\';\nfunction shut(){try{localStorage.setItem(K,"1")}catch(e){}w.classList.remove("on");setTimeout(function(){w.remove()},300)}\nw.querySelector(".wx").addEventListener("click",shut);w.querySelector(".wgo").addEventListener("click",shut);w.querySelector("a").addEventListener("click",function(){try{localStorage.setItem(K,"1")}catch(e){}});\ndocument.addEventListener("keydown",function(e){if(e.key==="Escape"&&document.body.contains(w))shut()});\nfunction show(){var bar=[].filter.call(document.querySelectorAll(".strip"),function(b){var r=b.getBoundingClientRect();return r.top<innerHeight&&r.bottom>innerHeight-4})[0];if(bar)w.style.bottom=(innerHeight-bar.getBoundingClientRect().top+14)+"px";document.body.appendChild(w);requestAnimationFrame(function(){requestAnimationFrame(function(){w.classList.add("on")})})}\nvar oj=document.getElementById("oj");if(!oj||force){setTimeout(show,1100)}else{var done=false,chk=function(){if(!done&&oj.getBoundingClientRect().bottom<0){done=true;removeEventListener("scroll",chk);setTimeout(show,500)}};addEventListener("scroll",chk,{passive:true})}})()</script>'

FLIP_JS = '<script>(function(){document.addEventListener("keydown",function(e){if(e.altKey||e.ctrlKey||e.metaKey||e.shiftKey)return;var t=e.target;if(t&&(t.isContentEditable||/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)))return;var a=document.querySelector(\'.flip a[data-key="\'+e.key+\'"]\');if(a){e.preventDefault();location.href=a.href}})})()</script>'

SK_FIND_JS = """<script>(function(){var box=document.getElementById("findbox"),out=document.getElementById("findn"),root=document.querySelector("main[data-desk]");if(!box||!root)return;
var fp=root.querySelector(".pane.fnd"),rows=[].slice.call(fp.querySelectorAll("li[data-find]")),labels=[].slice.call(fp.querySelectorAll(".fgl")),none=fp.querySelector(".fnone"),hint=fp.querySelector(".fhint:not(.fnone)"),last=null;
function panes(){return[].slice.call(root.querySelectorAll(".pane:not(.fnd)"))}
box.addEventListener("input",function(){var q=box.value.trim().toLowerCase().split(/\\s+/).filter(Boolean);
 var tabs=[].slice.call(root.querySelectorAll("[data-rtab]"));
 if(!q.length){fp.hidden=true;if(last){last.hidden=false;tabs.forEach(function(t){t.setAttribute("aria-selected",t.dataset.rtab===last.dataset.role?"true":"false")})}last=null;out.textContent="";return}
 if(!last){last=panes().filter(function(p){return!p.hidden})[0]||null;panes().forEach(function(p){p.hidden=true});fp.hidden=false;tabs.forEach(function(t){t.setAttribute("aria-selected","false")})}
 var shown=0;rows.forEach(function(r){var ok=q.every(function(w){return r.dataset.find.indexOf(w)>=0});r.hidden=!ok;if(ok)shown++});
 labels.forEach(function(l){var any=false,n=l.nextElementSibling;[].forEach.call(n.children,function(li){if(!li.hidden)any=true});l.hidden=!any;n.hidden=!any});
 none.hidden=shown>0;hint.hidden=!shown;hint.textContent=shown+(shown===1?" match":" matches")+" on the left. Pick one to read it.";out.textContent=shown+" of "+rows.length});
fp.addEventListener("click",function(e){var g=e.target.closest("[data-go]");if(!g)return;var b=root.querySelector('.pane:not(.fnd) [data-open="'+g.dataset.go+'"]');
 fp.hidden=true;last=null;box.value="";out.textContent="";if(b)b.click()})})()</script>"""

REPO_DESK_CSS = r"""
.rhead2 .never{grid-column:2;border-left:4px solid #FBB401;display:flex;gap:10px;align-items:baseline;margin-top:10px;padding:9px 12px;background:#101316;color:#F4F4EF;font-size:13.5px;line-height:1.45;max-width:640px}
.rhead2 .never b{flex:none;font:700 9.5px/1.6 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:#FBB401}
.rhead2 .never code{font:500 .9em "Martian Mono",ui-monospace,monospace;color:#FBB401}
.tab svg.si{width:34px;height:34px;padding:3px;background:#F4F4EF;border:2px solid #101316}
.rp .srow{padding-top:6px;padding-bottom:6px}
.rp .srow b{font:600 13px/1.25 "Martian Mono",ui-monospace,monospace;text-transform:none;flex:1}
.rp .srow svg{flex:none;width:16px;height:16px}
.rp .srow.d1 b{font-weight:700}
.rp .srow.d2{padding-left:34px}
.rp .srow i{flex:none;font:600 9.5px/1 "Martian Mono",ui-monospace,monospace;font-style:normal;color:var(--ink-3)}
.rp .srow .mno{flex:none;width:24px;font:800 16px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;color:var(--brand)}
.rp .srow.mo b{font:800 16px/1.15 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.crumb{font:600 11px/1.4 "Martian Mono",ui-monospace,monospace;color:var(--ink-3);text-transform:none;letter-spacing:0}
.rhd{display:flex;align-items:center;gap:14px;margin:0 0 12px}
.rhd .ico{flex:none;width:54px;height:54px;padding:8px;background:#F4F4EF;border:2px solid #101316}
.rhd .mbig{flex:none;width:54px;height:54px;display:flex;align-items:center;justify-content:center;background:#FBB401;color:#101316;border:2px solid #101316;font:800 30px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif}
.rhd h4{margin:0;font:700 24px/1.15 "Martian Mono",ui-monospace,monospace;text-transform:none;overflow-wrap:anywhere}
.rhd h4.mt{font:800 30px/1.05 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.chips span,.chips a{font:600 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;padding:5px 7px 4px;border:1.5px solid var(--ink);color:var(--ink);text-decoration:none}
.chips .you{background:var(--hivis);color:#101316;border-color:#101316}
.chips a{text-transform:none;letter-spacing:0;font-size:11.5px;border-bottom:2px solid var(--brand)}
.chips a:hover{background:var(--hivis);color:#101316}
.inside{list-style:none;margin:0 0 14px;padding:0;border-top:1px solid var(--line)}
.inside li{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.3fr);gap:4px 18px;padding:8px 0 8px calc(var(--d,0) * 18px);border-bottom:1px solid var(--line)}
.inside .nm{font:600 13px/1.4 "Martian Mono",ui-monospace,monospace;color:var(--ink);overflow-wrap:anywhere}
.inside .nm.dir{font-weight:700}
.inside .ds{font-size:14px;line-height:1.45;color:var(--ink-2)}
.inside .ds em{display:block;margin-top:3px;font-style:normal;font:600 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);margin-right:6px}
.kb2{margin:0 0 14px}
.kb2 h5{margin:0 0 8px;font:700 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3)}
.kb2 p{margin:0;font-size:15px;line-height:1.55;color:var(--ink)}
.kb2 code{font:500 .86em "Martian Mono",ui-monospace,monospace;background:rgba(251,180,1,.2);padding:0 3px;color:var(--ink)}
.jumps{display:flex;flex-wrap:wrap;gap:8px}
.jumps button{display:inline-flex;align-items:center;gap:8px;padding:7px 10px;border:2px solid var(--ink);background:var(--panel);color:var(--ink);cursor:pointer;font:600 12.5px/1.2 "Public Sans",system-ui,sans-serif;text-align:left}
.jumps button b{font:800 15px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;color:var(--brand)}
.jumps button svg{width:18px;height:18px;flex:none}
.rhd h4.mt code{text-transform:none;font-size:.62em;vertical-align:3px}
.jumps button code{font:600 12px/1 "Martian Mono",ui-monospace,monospace;background:none;padding:0}
.jumps button:hover{background:var(--hivis);color:#101316;border-color:#101316}.jumps button:hover b{color:#101316}
@media (max-width:1000px){.rhead2 .never{grid-column:1}}
@media (max-width:640px){.inside li{grid-template-columns:minmax(0,1fr)}}

/* the site's language here too: a label plate, the never-here box as a red prohibition sign, names that open their folder */
.orw{display:grid;grid-template-columns:auto minmax(0,1fr);margin:6px 0 16px;border:2px solid var(--ink);box-shadow:3px 3px 0 var(--ink)}
.orw dt{display:flex;align-items:center;font:700 9.5px/1.2 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;background:#101316;color:#FBB401;padding:8px 10px;white-space:nowrap}
.orw dd{margin:0;padding:8px 12px;font-size:14.5px;line-height:1.45;color:var(--ink);background:var(--panel)}
.orw dt:not(:last-of-type){border-bottom:1px solid #3A4046}.orw dd:not(:last-of-type){border-bottom:2px solid var(--ink)}
.orw dd.chips{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.rhead2 .never{display:flex;align-items:stretch;gap:0;padding:0;background:#F4F4EF;color:#101316;border:2px solid #101316;border-left:2px solid #101316;box-shadow:3px 3px 0 #101316}
.rhead2 .never i{flex:none;width:44px;display:grid;place-items:center;background:#C42B1C;border-right:2px solid #101316}
.rhead2 .never i::before{content:"";width:22px;height:22px;border-radius:50%;border:4px solid #fff;background:linear-gradient(45deg,transparent 43%,#fff 43% 57%,transparent 57%)}
.rhead2 .never b{display:flex;align-items:center;padding:0 10px;font:800 15px/1 "Big Shoulders Display","Arial Narrow",sans-serif;letter-spacing:.04em;color:#C42B1C;white-space:nowrap}
.rhead2 .never span{padding:9px 12px 9px 0;font-size:13.5px}
.rhead2 .never code{color:#101316;background:#FBB401;padding:0 4px}
.rhead2 .rmode{grid-column:2;margin:2px 0 0;font-size:13px;color:var(--ink-3)}
@media (max-width:1000px){.rhead2 .rmode{grid-column:1}}
.crumb button{font:inherit;color:inherit;background:none;border:0;padding:0;cursor:pointer;text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:3px}
.crumb button:hover{color:var(--ink);text-decoration-color:#FBB401}
.inside button.nm{font:inherit;background:none;border:0;padding:0;cursor:pointer;color:var(--ink);text-align:left;text-decoration:underline;text-decoration-color:#FBB401;text-decoration-thickness:2px;text-underline-offset:3px}
.inside button.nm:hover{background:#FBB401;color:#101316}
main.rp .snav button small.navname{display:block;margin-top:3px;max-width:38ch;text-transform:none;font:600 13px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
"""

LOGBOOK_DESK_CSS = r"""
.press{grid-column:1/-1;list-style:none;margin:16px 0 0;padding:16px 0 0;border-top:1px dashed var(--line);display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:14px;counter-reset:none}
.press li{position:relative;border:2px solid var(--ink);background:var(--panel);padding:12px 12px 14px;display:flex;flex-direction:column;gap:6px}
.press li+li::before{content:"";position:absolute;left:-14px;top:22px;width:14px;height:2px;background:var(--ink)}
.press .pn{align-self:flex-start;font:800 15px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;background:#FBB401;color:#101316;padding:3px 6px 2px}
.press li:last-child .pn{background:#3FAE6A}
.press b{font:800 18px/1.05 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.press .pt{font-size:12.5px;line-height:1.45;color:var(--ink-2)}
@media (max-width:1100px){.press{grid-template-columns:repeat(3,minmax(0,1fr))}.press li:nth-child(4)::before{display:none}}
@media (max-width:640px){.press{grid-template-columns:minmax(0,1fr)}.press li+li::before{left:22px;top:-14px;width:2px;height:14px}.press li:nth-child(4)::before{display:block}}
.lgraph{grid-column:1/-1;margin:16px 0 0;padding-top:14px;border-top:1px dashed var(--line);color:var(--ink-2)}
.lgraph .lgh{display:flex;flex-wrap:wrap;gap:6px 26px;margin-bottom:10px;font-size:13.5px}
.lgraph .lgh code,.lgraph figcaption code{font-size:12px}
.lgraph svg{display:block;width:100%;height:auto}
.lgraph .gcl{fill:none;stroke:var(--ink-3);stroke-width:1.4;stroke-dasharray:5 5}
.lgraph .gcn{font:600 11px/1 "Martian Mono",ui-monospace,monospace;fill:var(--ink-3);letter-spacing:.06em}
.lgraph .gc rect{fill:#F4F4EF;stroke:#101316;stroke-width:2}.lgraph .gnew>rect:first-child{fill:#FBB401}
.lgraph .gweak rect{fill:#DCDCD5;stroke:#7C8387;stroke-dasharray:5 4}.lgraph .gweak .gid,.lgraph .gweak .gk,.lgraph .gweak .gn{fill:#3A4044}
.lgraph .gid{font:700 15px/1 "Martian Mono",ui-monospace,monospace;fill:#101316}
.lgraph .gk,.lgraph .gn{font:600 10px/1 "Martian Mono",ui-monospace,monospace;fill:#454C50;letter-spacing:.08em}
.lgraph .gtag{fill:#101316}.lgraph .gtagt{font:700 9.5px/1 "Martian Mono",ui-monospace,monospace;fill:#FBB401;letter-spacing:.12em}
.lgraph .gweakt{font:700 10px/1 "Martian Mono",ui-monospace,monospace;fill:var(--ink-2);letter-spacing:.08em;text-transform:uppercase}
.lgraph .ge{fill:none;stroke:currentColor;stroke-width:2.2}.lgraph .ge.g-dash{stroke-dasharray:6 5}
.lgraph .ge.g-new{stroke:#B07A00}.lgraph .ge.g-bad{stroke:#C42B1C}
.lgraph .gl{font:700 11.5px/1 "Martian Mono",ui-monospace,monospace;fill:currentColor;letter-spacing:.03em;paint-order:stroke;stroke:var(--panel);stroke-width:5px;stroke-linejoin:round}
.lgraph .gl.g-new{fill:var(--brand)}.lgraph .gl.g-bad{fill:#C42B1C}
:root[data-theme="dark"] .lgraph .gl.g-bad{fill:#FF7A6E}:root[data-theme="dark"] .lgraph .ge.g-bad,:root[data-theme="dark"] .lgraph #gm-bad path{stroke:#FF7A6E}:root[data-theme="dark"] .lgraph .ge.g-new,:root[data-theme="dark"] .lgraph #gm-new path{stroke:#FBB401}:root[data-theme="dark"] .lgraph .gweak rect{fill:#3A4044;stroke:#8A938D}:root[data-theme="dark"] .lgraph .gweak .gid{fill:#E7EAE5}:root[data-theme="dark"] .lgraph .gweak .gk,:root[data-theme="dark"] .lgraph .gweak .gn{fill:#B4BBB6}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .lgraph .gl.g-bad{fill:#FF7A6E}:root:not([data-theme="light"]) .lgraph .ge.g-bad,:root:not([data-theme="light"]) .lgraph #gm-bad path{stroke:#FF7A6E}:root:not([data-theme="light"]) .lgraph .ge.g-new,:root:not([data-theme="light"]) .lgraph #gm-new path{stroke:#FBB401}:root:not([data-theme="light"]) .lgraph .gweak rect{fill:#3A4044;stroke:#8A938D}:root:not([data-theme="light"]) .lgraph .gweak .gid{fill:#E7EAE5}:root:not([data-theme="light"]) .lgraph .gweak .gk,:root:not([data-theme="light"]) .lgraph .gweak .gn{fill:#B4BBB6}}
.lgraph figcaption{margin-top:8px;font-size:13.5px;line-height:1.5}
.reader .body ol.press{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:6px 0 0;border-top:0;padding:0}
.lb .press li:nth-child(4)::before{display:none}
.lb .lgraph{margin-top:6px;border-top:0;padding-top:0}
.rhead2 .rules3{grid-column:2;list-style:none;margin:10px 0 0;padding:9px 12px 9px 14px;border-left:4px solid #FBB401;background:#101316;color:#F4F4EF;font-size:13.5px;line-height:1.45;max-width:640px;display:flex;flex-direction:column;gap:3px}
.rhead2 .rules3 b{font:700 9.5px/1.6 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:#FBB401;margin-right:8px}
.rhead2 .rules3 code{font:500 .9em "Martian Mono",ui-monospace,monospace;color:#FBB401}
.tab svg.si{width:34px;height:34px;padding:3px;background:#F4F4EF;border:2px solid #101316}
.lb .srow b{flex:1}
.lb .srow .mno{flex:none;width:24px;font:800 16px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;color:var(--brand)}
.lb .srow .ty{flex:none;width:12px;height:16px;border:1.5px solid #101316}
.lb .srow code{font:600 12.5px/1.2 "Martian Mono",ui-monospace,monospace;text-transform:none}
.lb .srow.fl b{font:600 13px/1.25 "Martian Mono",ui-monospace,monospace;text-transform:none}
.ty-insight{background:#FBB401}.ty-method{background:#5AA0F0}.ty-build{background:#3FAE6A}.ty-score{background:#F4F4EF}.ty-ruled{background:#C42B1C}
.lhd{display:flex;align-items:center;gap:14px;margin:0 0 12px}
.lhd .mbig{flex:none;width:54px;height:54px;display:flex;align-items:center;justify-content:center;background:#FBB401;color:#101316;border:2px solid #101316;font:800 30px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif}
.lhd h4{margin:0}
.lhd h4.mono{font:700 24px/1.15 "Martian Mono",ui-monospace,monospace;text-transform:none;overflow-wrap:anywhere}
.lchips{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.lchips span,.lchips a{max-width:100%;overflow-wrap:anywhere;font:600 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;padding:5px 7px 4px;border:1.5px solid var(--ink);color:var(--ink);text-decoration:none}
.lchips .path,.lchips .cmd{text-transform:none;letter-spacing:0;font-size:11.5px}
.lchips .you{background:var(--hivis);color:#101316;border-color:#101316}
.lchips a{text-transform:none;letter-spacing:0;font-size:11.5px;border-bottom:2px solid var(--brand)}
.lchips a:hover{background:var(--hivis);color:#101316}
.card{margin:4px 0 14px;border:2px solid #101316;background:#FFFDF6;color:#101316;box-shadow:6px 6px 0 rgba(16,19,22,.18)}
.card .ch{display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px;padding:10px 14px;border-bottom:2px solid #101316}
.card.ty-insight .ch{background:#FBB401}.card.ty-method .ch{background:#9CC6F5}.card.ty-build .ch{background:#9AD7AE}
.card .ch b{font:800 13px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.06em}
.card .ch code{font:600 12px/1.3 "Martian Mono",ui-monospace,monospace;overflow-wrap:anywhere;background:none!important;padding:0!important;color:#101316}
.card .fm{display:flex;flex-wrap:wrap;gap:6px 16px;padding:8px 14px;border-bottom:1px dashed #9AA29C;font:500 11.5px/1.4 "Martian Mono",ui-monospace,monospace;color:#454C50}
.card .fm span b{color:#101316;font-weight:700}
.card .ex{margin-left:auto;font:600 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:#454C50}
.card ol{list-style:none;margin:0;padding:6px 14px 10px}
.card li{display:grid;grid-template-columns:170px minmax(0,1fr);gap:4px 14px;padding:7px 0;border-bottom:1px solid #E2E0D6}
.card li:last-child{border-bottom:0}
.card li b{font:700 14px/1.35 "Public Sans",system-ui,sans-serif;color:#101316}
.card .ch b,.card .fm span b{color:#101316}
.card li span{font-size:13.5px;line-height:1.45;color:#454C50}
.kb3{margin:0 0 14px}
.kb3 h5{margin:0 0 8px;font:700 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3)}
.kb3 p{margin:0 0 6px;font-size:15px;line-height:1.55;color:var(--ink)}
.kb3 code{font:500 .86em "Martian Mono",ui-monospace,monospace;background:rgba(251,180,1,.2);padding:0 3px;color:var(--ink)}
.scale{list-style:none;margin:0;padding:0;border-top:1px solid var(--line)}
.scale li{display:grid;grid-template-columns:120px minmax(0,1fr);gap:12px;padding:8px 0;border-bottom:1px solid var(--line);font-size:14.5px}
.scale li b{font:700 13px/1.4 "Martian Mono",ui-monospace,monospace}
.scale li.tot{border-top:2px solid var(--ink);font-weight:700}
.lyour{display:flex;gap:10px;align-items:baseline;margin:0 0 14px;padding:10px 14px;border-left:3px solid var(--hivis);background:rgba(251,180,1,.12);font-size:14.5px}
.lyour b{flex:none;font:700 9.5px/1.6 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
@media (max-width:1000px){.rhead2 .rules3{grid-column:1}}
@media (max-width:640px){.card li{grid-template-columns:minmax(0,1fr)}.reader .body ol.press{grid-template-columns:minmax(0,1fr)}.scale li{grid-template-columns:minmax(0,1fr)}}

/* the site's language here too: plates, the three rules as yellow signs, a track for a card's life, your word on a hi-vis tag */
.orw{display:grid;grid-template-columns:auto minmax(0,1fr);margin:10px 0 16px;border:2px solid var(--ink);box-shadow:3px 3px 0 var(--ink)}
.orw dt{display:flex;align-items:center;font:700 9.5px/1.2 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;background:#101316;color:#FBB401;padding:8px 10px;white-space:nowrap}
.orw dd{margin:0;padding:8px 12px;font-size:14.5px;line-height:1.45;color:var(--ink);background:var(--panel)}
.orw dt:not(:last-of-type){border-bottom:1px solid #3A4046}.orw dd:not(:last-of-type){border-bottom:2px solid var(--ink)}
.orw dd.lchips{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:0}
.rhead2 .rules3{padding:0;background:none;border:0;gap:8px;color:#101316}
.rhead2 .rules3 li{display:flex;align-items:stretch;border:2px solid #101316;background:#FBB401;box-shadow:3px 3px 0 #101316}
.rhead2 .rules3 li::before{content:"";flex:none;width:10px;background:repeating-linear-gradient(-45deg,#101316 0 5px,#FBB401 5px 10px);border-right:2px solid #101316}
.rhead2 .rules3 li span{display:flex;align-items:center;gap:0;font:800 15px/1.15 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;letter-spacing:.01em;color:#101316}
.rhead2 .rules3 li b{align-self:stretch;display:flex;align-items:center;margin:0 10px 0 0;padding:0 8px;background:#101316;color:#FBB401}
.rhead2 .rules3 li span{padding-right:10px;min-height:32px}
.rhead2 .rules3 code{background:#101316;color:#FBB401;padding:1px 4px;text-transform:none;font-size:.8em}
.ltrack{list-style:none;display:flex;align-items:center;gap:0;margin:0 0 14px;padding:0}
.ltrack li{flex:1;display:flex;align-items:center}.ltrack li:last-child{flex:none}
.ltrack li:not(:last-child)::after{content:"";flex:1;height:3px;background:var(--line)}
.ltrack li.past::after{background:#FBB401}
.ltrack button{flex:none;width:30px;height:30px;display:grid;place-items:center;font:800 13px/1 "Big Shoulders Display",sans-serif;border:2px solid var(--ink);background:var(--panel);color:var(--ink-3);cursor:pointer;padding:0}
.ltrack .past button{background:#FBB401;color:#101316;border-color:#101316}
.ltrack .on button{background:#101316;color:#FBB401;border-color:#101316;transform:scale(1.18)}
.lyour{display:flex;align-items:stretch;margin:0 0 16px;border:2px solid #101316;background:#FBB401;color:#101316;box-shadow:3px 3px 0 #101316;max-width:560px;padding:0}
.lyour b{flex:none;display:flex;align-items:center;padding:0 9px;font:700 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;background:#101316;color:#FBB401}
.lyour span{padding:8px 12px;font-size:14px;color:#101316}
main.lb .snav button{min-width:0;max-width:100%}main.lb .snav button small.navname{text-transform:none;font:600 13px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:0;white-space:nowrap;max-width:min(38ch,100%);overflow:hidden;text-overflow:ellipsis;display:block}
.sbar .pth{text-transform:none;letter-spacing:0;font-weight:600}
"""

OW_JS = """<script>(function(){var root=document.getElementById("order");if(!root)return;
var bs=[].slice.call(root.querySelectorAll(".obar [data-f]")),steps=[].slice.call(root.querySelectorAll(".ostep")),subs=[].slice.call(root.querySelectorAll(".osub")),xa=root.querySelector("[data-all]");
function apply(f){bs.forEach(function(b){b.setAttribute("aria-pressed",b.dataset.f===f?"true":"false")});
 subs.forEach(function(s){var ok=f==="all"||(f==="word"?s.classList.contains("has-word"):s.dataset.role===f);s.classList.toggle("dim",!ok)});
 steps.forEach(function(st){var any=st.querySelector(".osub:not(.dim)");st.classList.toggle("dim",!any);if(f!=="all")st.open=!!any})}
bs.forEach(function(b){b.addEventListener("click",function(){apply(b.dataset.f)})});
xa.addEventListener("click",function(){var open=xa.getAttribute("aria-pressed")!=="true";steps.forEach(function(st){st.open=open});xa.setAttribute("aria-pressed",open?"true":"false");xa.textContent=open?"Close all":"Open all"});
var h=location.hash.slice(1),st=h&&document.getElementById(h);if(st&&st.tagName==="DETAILS")st.open=true;apply("all")})()</script>"""

# the Skills and agents sheet: the route's skills under the same 11 steps as the landing page and the Order of works,
# then the Logbook's skills, the toolkit, and the agents
MEMORY_SKILLS = ["f-card", "f-search", "f-archive", "f-archive-search", "f-catchup", "f-context", "f-distill", "f-dream"]
KIND_ICONS = {
    "memory": '<rect x="3" y="6" width="18" height="14" fill="#8C949A" stroke="#101316" stroke-width="1.8"/><rect x="6" y="9" width="12" height="4" fill="#F4F4EF" stroke="#101316" stroke-width="1.2"/><rect x="6" y="14.5" width="12" height="4" fill="#F4F4EF" stroke="#101316" stroke-width="1.2"/><rect x="5" y="3" width="10" height="4" fill="#FBB401" stroke="#101316" stroke-width="1.4"/>',
    "toolkit": '<path d="M14.5 3.5a5 5 0 0 0-5.6 6.7L3.5 15.6a2 2 0 0 0 2.9 2.9l5.4-5.4a5 5 0 0 0 6.7-5.6l-3 3-2.6-.6-.6-2.6Z" fill="#9AA4A8" stroke="#101316" stroke-width="1.6" stroke-linejoin="round"/>',
    "agents": '<circle cx="12" cy="8.5" r="4" fill="#E8C4A0" stroke="#101316" stroke-width="1.6"/><path d="M8 6.5c0-3 1.8-4.5 4-4.5s4 1.5 4 4.5Z" fill="#C38BD9" stroke="#101316" stroke-width="1.4"/><path d="M4 21c0-4.5 3.5-7.5 8-7.5s8 3 8 7.5Z" fill="#C38BD9" stroke="#101316" stroke-width="1.6"/>',
}


def step_of_skill() -> dict:
    """skill id -> (step number, step name, its anchor on the Order of works), from the landing page's step data."""
    out = {}
    for i, (step, _who, _w, ids) in enumerate(FRONT["route_once"] + FRONT["route_loop"], 1):
        for s in ids:
            out[s] = (i, step, re.sub(r"[^a-z]+", "-", step.lower()).strip("-"))
    return out


def kind_of(pid: str, n: dict, steps: dict) -> str:
    if pid in steps:
        return "route"
    if n["type"] == "agent":
        return "agents"
    return "memory" if pid in MEMORY_SKILLS else "toolkit"

FIND_JS = """<script>(function(){var box=document.getElementById("findbox"),out=document.getElementById("findn"),none=document.getElementById("findnone");if(!box)return;
var rows=[].slice.call(document.querySelectorAll("[data-find]")),grps=[].slice.call(document.querySelectorAll(".grp"));
box.addEventListener("input",function(){var q=box.value.trim().toLowerCase().split(/\\s+/).filter(Boolean),shown=0;
 rows.forEach(function(r){var ok=q.every(function(w){return r.dataset.find.indexOf(w)>=0});r.hidden=!ok;if(ok)shown++});
 grps.forEach(function(g){g.hidden=!g.querySelector("li:not([hidden])")});
 out.textContent=q.length?shown+" of "+rows.length:"";none.hidden=shown>0})})()</script>"""

PBK_JS = """<script>(function(){var tabs=[].slice.call(document.querySelectorAll("[data-book]"));if(!tabs.length)return;
function show(k,scroll){tabs.forEach(function(b){var on=b.dataset.book===k;b.setAttribute("aria-selected",on?"true":"false");document.getElementById("book-"+b.dataset.book).hidden=!on});}
tabs.forEach(function(b){b.addEventListener("click",function(){show(b.dataset.book);try{history.replaceState(null,"","#tab-"+b.dataset.book)}catch(e){}})});
function fromHash(){var h=location.hash.slice(1);if(!h)return;var k=h==="tab-b"||h.indexOf("b-")===0?"b":(h==="tab-f"||h.indexOf("f-")===0?"f":null);if(!k)return;show(k);
 var el=document.getElementById(h);if(el&&h.indexOf("tab-")!==0)setTimeout(function(){el.scrollIntoView()},60)}
window.addEventListener("hashchange",fromHash);fromHash()})()</script>"""

PBK_CSS = ORDER_CSS + r"""
.phead{padding:40px 0 10px}
.phead .eyebrow{font:600 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--brand)}
.phead h1{margin:12px 0 14px;font:800 clamp(44px,7vw,80px)/.9 "Big Shoulders Display","Arial Narrow",Impact,sans-serif;text-transform:uppercase}
.phead .lede{max-width:70ch;color:var(--ink-2);margin:0;font-size:17px}
.phead .lede a{color:var(--ink)}
.who{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:20px}
.who div{border:2px solid var(--line);padding:12px 14px;display:flex;flex-direction:column;gap:4px}
.who b{font:800 19px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.who span{font-size:14px;color:var(--ink-2)}
.pbk .tabs{display:flex;gap:0;margin:26px 0 0;border-bottom:3px solid var(--ink)}
.pbk .tabs button{font:800 20px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;letter-spacing:.02em;padding:12px 18px 10px;border:2px solid var(--line);border-bottom:0;background:var(--panel);color:var(--ink-2);cursor:pointer;margin-right:6px}
.pbk .tabs button[aria-selected="true"]{background:var(--hivis);color:#101316;border-color:#101316}
.book{display:grid;grid-template-columns:200px minmax(0,1fr);gap:40px;padding-top:28px}
.book[hidden]{display:none}
.toc{position:sticky;top:20px;align-self:start;display:flex;flex-direction:column;gap:2px;font:500 12px/1.4 "Martian Mono",ui-monospace,monospace}
.toc .lab{letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);margin-bottom:8px;font-size:10.5px}
.toc a{color:var(--ink-2);text-decoration:none;padding:5px 0 5px 10px;border-left:2px solid var(--line-2)}
.toc a:hover,.toc a:focus-visible{color:var(--ink);border-left-color:var(--hivis);outline:none}
.bk{display:flex;flex-direction:column;gap:48px;min-width:0}
.bk section{scroll-margin-top:20px}
.btop{display:flex;flex-direction:column;gap:10px;padding-bottom:20px;border-bottom:1px solid var(--line)}
.btop .bt{margin:0;font:800 34px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.btop .lede{margin:0;font-size:17px;color:var(--ink-2);max-width:66ch}
.btop .note{margin:0;font:500 12px/1.6 "Martian Mono",ui-monospace,monospace;color:var(--ink-3)}
.bk h2{font:800 30px/1.05 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;margin:0}
.bk section>p{max-width:68ch;margin:0 0 12px;color:var(--ink-2)}
.bk .kicker{font:600 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3);margin:2px 0 6px}
.bk code{font:500 .86em "Martian Mono",ui-monospace,monospace;background:rgba(251,180,1,.2);padding:1px 5px;color:var(--ink)}
.bk .sign{display:flex;gap:14px;align-items:stretch;margin:0 0 14px}
.bk .sign .sn{flex:none;display:grid;place-items:center;width:58px;min-height:58px;background:var(--ink);color:var(--ground);font:800 34px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif}
.thesis{background:#15181A;color:#ECEEEA;border:3px solid var(--ink);border-left:8px solid var(--hivis);padding:24px 26px;display:flex;flex-direction:column;gap:14px}
.thesis .big{font:800 clamp(30px,5vw,46px)/1 "Big Shoulders Display",sans-serif;text-transform:uppercase}
.thesis .big em{font-style:normal;color:#FBB401}
.thesis p{margin:0;max-width:68ch;color:#ECEEEA;opacity:.92}.thesis ul{margin:0;padding-left:18px;display:flex;flex-direction:column;gap:6px;max-width:68ch}
.thesis li{color:#ECEEEA;opacity:.9}.thesis code{background:rgba(251,180,1,.2);color:#ECEEEA}
.bk .rules{list-style:none;margin:6px 0 18px;padding:0;display:flex;flex-direction:column;gap:8px}
.bk .rules li{display:grid;grid-template-columns:52px minmax(0,1fr);background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--hivis)}
.bk .rules .rn{display:flex;justify-content:center;padding-top:13px;border-right:1px dashed var(--line);font:800 24px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;color:var(--ink-3)}
.bk .rules .rt{padding:13px 16px 11px;display:flex;flex-direction:column;gap:8px;min-width:0}
.bk .rules .rr{font-size:15.5px;line-height:1.45;color:var(--ink)}
.bk .rules .rw{display:flex;gap:10px;align-items:baseline;border-top:1px dashed var(--line);padding-top:8px}
.bk .rules .rw b{flex:none;font:600 10px/1.4 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.bk .rules .rw span{font-size:13.5px;line-height:1.5;color:var(--ink-2)}
.bk ol.check{list-style:none;margin:0;padding:0;border-top:1px solid var(--line)}
.bk .check li{display:grid;grid-template-columns:28px minmax(0,1fr);gap:12px;padding:11px 0;border-bottom:1px solid var(--line-2)}
.bk .check li::before{content:"";width:16px;height:16px;border:2px solid var(--brand);margin-top:4px}
.bk ol.steps{list-style:none;margin:0;padding:0;counter-reset:st;border-top:1px solid var(--line)}
.bk ol.steps li{counter-increment:st;display:grid;grid-template-columns:40px minmax(0,1fr);gap:12px;padding:11px 0;border-bottom:1px solid var(--line-2)}
.bk ol.steps li::before{content:counter(st,decimal-leading-zero);font:800 17px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;color:#101316;background:var(--hivis);align-self:start;justify-self:start;padding:2px 6px;margin-top:3px}
.bk ul.plain{list-style:none;margin:0 0 12px;padding:0;display:flex;flex-direction:column;gap:8px;max-width:72ch}
.bk ul.plain li{position:relative;padding-left:22px;color:var(--ink-2)}
.bk ul.plain li::before{content:"";position:absolute;left:0;top:.8em;width:12px;height:3px;background:var(--hivis)}
.bk .tw{overflow-x:auto;border:1px solid var(--line)}
.bk table{border-collapse:collapse;width:100%;background:var(--panel);font-size:15px}
.bk th,.bk td{text-align:left;vertical-align:top;padding:11px 14px;border-bottom:1px solid var(--line-2)}
.bk th{font:600 11px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);background:var(--panel-2)}
.bk td:first-child{font-weight:600;min-width:240px}.bk td:last-child{color:var(--ink-2)}
.bk h3.sub{margin:22px 0 8px;font:800 20px/1.1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;border-left:4px solid var(--hivis);padding-left:10px}
.bk .src{margin:0;font:500 12px/1.6 "Martian Mono",ui-monospace,monospace;color:var(--ink-3);border-top:1px solid var(--line);padding-top:12px}
@media (max-width:860px){.who{grid-template-columns:minmax(0,1fr)}.book{grid-template-columns:minmax(0,1fr);gap:20px}.toc{position:static;display:none}
 .pbk .tabs button{font-size:16px;padding:10px 12px 8px}.bk td:first-child{min-width:180px}}
"""

# ---------- the Playbooks sheet: the handover loop, each playbook section pinned where it bites ----------
# station: (key, label, where on the loop, x, y). Sections are matched by their heading in the Markdown; the build checks every
# section of both playbooks is placed once ("The one idea" of each opens the page instead).
PB_STATIONS = [
    ("before", "Before", "Before any plan or work order", 150, 236),
    ("plan", "Plan", "The foreman settles every decision", 250, 108),
    ("write", "Write", "The foreman writes the work order", 450, 70),
    ("hand", "Hand over", "A pointer to the file, never pasted text", 650, 108),
    ("build", "Build", "The builder builds, test-first", 750, 236),
    ("review", "Review", "Back to the foreman: disk before words", 450, 372),
]
PB_MAP = {
    ("F", "Before you plan"): "before", ("B", "Before the job"): "before",
    ("F", "Planning (the scoping and the plan)"): "plan",
    ("F", "Writing a work order"): "write", ("B", "Every work order"): "write",
    ("B", "Handing work orders over"): "hand",
    ("B", "Where a light builder fits"): "build", ("B", "When to switch builders"): "build",
    ("F", "Reviewing a work order"): "review", ("B", "After every work order"): "review", ("F", "When the builder stops"): "review",
    ("F", "The end game"): "always", ("F", "Talking to the owner"): "always", ("F", "Tool hygiene (small things that cost time)"): "always",
    ("F", "Your own scorecard"): "always", ("F", "When you write code yourself (the converged case)"): "always",
}
PB_ALWAYS = ("always", "Around the loop", "The end game, talking to you, tool hygiene, the foreman's scorecard, and the rare case it writes code itself")


def pb_sections():
    """Both playbooks' sections: (book, heading, kicker, blocks), plus each book's opening idea."""
    out, ideas = [], {}
    for key, book in (("F", PBK.BOOKS[0]), ("B", PBK.BOOKS[1])):
        md = (ROOT / book["src"]).read_text(encoding="utf-8")
        _head, _, rest = md.partition("\n---\n")
        for sec in re.split(r"^## ", rest, flags=re.M)[1:]:
            name, _, text = sec.partition("\n")
            name = name.strip()
            bl = PBK.blocks(re.sub(r"\n---\s*$", "", text.strip()).splitlines())
            if name == "The one idea":
                ideas[key] = bl
                continue
            out.append((key, name, book["kickers"].get(name, ("", ""))[1], bl))
    placed = [(k, n) for k, n, *_ in out]
    if sorted(placed) != sorted(PB_MAP):
        raise SystemExit(f"build_site: PB_MAP and the playbooks disagree: {sorted(set(placed) ^ set(PB_MAP))}")
    return out, ideas


PB_REAL = re.compile(r"\b(once|on one job|in one job|on one ticket|one real)\b", re.I)
PB_MISS = re.compile(r"\s*\((?:a )?real miss:\s*(.+?)\)", re.I)
PB_SHOW = 6


def pb_card(rule, because="", label="Because", num=""):
    """One rule as a card: the rule, an optional reason, and the playbook's own 'a real miss' lifted out of its bracket."""
    miss = PB_MISS.search(rule)
    if miss:
        rule = PB_MISS.sub("", rule)
    real = bool(PB_REAL.search(because)) or bool(miss)
    find = re.sub(r"[*`]", "", " ".join([rule, because, miss.group(1) if miss else ""])).lower()
    return (f'<article class="rc{" real" if real else ""}" data-find="{esc(find)}">'
            + (f'<span class="rtag">From a real job</span>' if real and not miss else "")
            + f'<div class="rcr">{f"<i class=rnum>{num}</i>" if num else ""}{PBK.inline(rule)}</div>'
            + (f'<div class="rcm"><b>Real miss</b><span>{PBK.inline(miss.group(1))}</span></div>' if miss else "")
            + (f'<div class="rcw"><b>{label}</b><span>{PBK.inline(because)}</span></div>' if because else "") + "</article>")


def pb_cards(blocks):
    """A section's blocks as cards: rule tables, checklists, numbered steps and lists all become cards; prose and wide tables stay as written."""
    items, n = [], 0
    for k, ls in blocks:
        if k == "table":
            rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in ls if not re.match(r"^\|[\s|:-]+\|$", ln.strip())]
            head, body = rows[0], rows[1:]
            if len(head) == 2 and all(len(r) == 2 for r in body):
                label = "Aim for" if head[1].lower().startswith("aim") else "Because"
                for r in body:
                    n += 1
                    items.append(pb_card(r[0], r[1], label))
                continue
        if k in ("check", "bullets"):
            for ln in ls:
                n += 1
                items.append(pb_card(ln[6:] if k == "check" else ln[2:]))
            continue
        if k == "steps":
            for i, ln in enumerate(ls, 1):
                n += 1
                items.append(pb_card(re.sub(r"^\d+\. ", "", ln), num=f"{i:02d}"))
            continue
        items.append(f'<div class="rx" data-find="{esc(re.sub(r"<[^>]+>|[*`]", "", " ".join(ls)).lower())}">{PBK.render_block(k, ls)}</div>')
    cards = [x for x in items if x.startswith("<article")]
    extra = len(cards) - PB_SHOW
    out, seen = [], 0
    for x in items:
        if x.startswith("<article"):
            seen += 1
        hide = seen > PB_SHOW and not (x.startswith('<div class="rx"') and seen == 0)
        out.append(x.replace(' class="', ' class="more ', 1) if hide else x)
    more = f'<button type="button" class="pmore">Show all {len(cards)} rules</button>' if extra > 0 else ""
    return "".join(out) + more, n

def old_books_html(self) -> str:
    """Both playbooks, rendered from their Markdown by the playbook script's own reader, in the site's layout."""
    books = []
    for key, book, label in (("f", PBK.BOOKS[0], "The foreman's rules"), ("b", PBK.BOOKS[1], "The builder's rules")):
        md = (ROOT / book["src"]).read_text(encoding="utf-8")
        head, _, rest = md.partition("\n---\n")
        hl = [ln for ln in head.splitlines() if ln.strip()]
        title, lede, note = hl[0].lstrip("# ").strip(), hl[1], " ".join(hl[2:])
        toc, body, num = [], [], 0
        for sec in re.split(r"^## ", rest, flags=re.M)[1:]:
            name, _, text = sec.partition("\n")
            name = name.strip()
            text = re.sub(r"\n---\s*$", "", text.strip())
            anchor, kicker = book["kickers"].get(name, (re.sub(r"[^a-z]+", "-", name.lower()).strip("-"), ""))
            anchor = f"{key}-{anchor}"
            short = re.sub(r"\s*\(.*\)$", "", name)
            toc.append(f'<a href="#{anchor}">{esc(short)}</a>')
            bl = PBK.blocks(text.splitlines())
            if anchor.endswith("-idea"):
                words = re.sub(r"\*\*", "", bl[0][1][0]).split()
                big = esc(" ".join(words[:3])) + "<br><em>" + esc(" ".join(words[3:])) + "</em>"
                inner = "".join(PBK.render_block(k, ls) for k, ls in bl[1:]).replace('<ul class="plain">', "<ul>")
                body.append(f'<section id="{anchor}" class="thesis" aria-label="The one idea"><div class="big">{big}</div>{inner}</section>')
                continue
            num += 1
            kick = f'<div class="kicker">{esc(kicker)}</div>' if kicker else ""
            body.append(f'<section id="{anchor}"><div class="sign"><span class="sn">{num:02d}</span><div>{kick}<h2>{esc(short)}</h2></div></div>'
                        + "".join(PBK.render_block(k, ls) for k, ls in bl) + "</section>")
        books.append((key, label, title, lede, note, toc, body, book["src"]))
    tabs = "".join(f'<button type="button" role="tab" id="tab-{k}" aria-controls="book-{k}" data-book="{k}" aria-selected="{"true" if k == "f" else "false"}">{esc(lbl)}</button>'
                   for k, lbl, *_ in books)
    panes = "".join(
        f'<div class="book" id="book-{k}" role="tabpanel" aria-labelledby="tab-{k}"{"" if k == "f" else " hidden"}>'
        f'<nav class="toc" aria-label="Sections"><span class="lab">{esc(title)}</span>{"".join(toc)}</nav>'
        f'<div class="bk"><header class="btop"><h2 class="bt">{esc(title)}</h2><p class="lede">{inline(lede)}</p><p class="note">{inline(note)}</p></header>'
        f'{"".join(body)}<p class="src">Shown exactly as written in <code>{esc(src)}</code>.</p></div></div>'
        for k, _lbl, title, lede, note, toc, body, src in books)
    gl = "".join(f"<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>" for k, v in GLOSSARY)
    gl = "".join(f"<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>" for k, v in GLOSSARY)
    return (f'<div class="tabs" role="tablist" aria-label="Playbooks">{tabs}</div>{panes}'
            f'<section class="oglos" id="words" aria-labelledby="words-h"><h2 id="words-h">Words used in the playbooks</h2><dl>{gl}</dl></section>')


PB_LOOP_JS = PBK_JS + """<script>(function(){var root=document.getElementById("pbk");if(!root)return;root.classList.add("js");
var stns=[].slice.call(root.querySelectorAll("[data-st]")).filter(function(e){return !e.classList.contains("pp")}),pans=[].slice.call(root.querySelectorAll(".pp")),
 box=document.getElementById("pfind"),out=document.getElementById("pfn"),none=document.getElementById("pnone"),cur="write";
function pick(k,scroll){cur=k;box.value="";out.textContent="";none.hidden=true;root.classList.remove("finding");
 stns.forEach(function(s){var on=s.dataset.st===k;s.classList.toggle("on",on);s.setAttribute("aria-pressed",on?"true":"false")});
 pans.forEach(function(p){p.hidden=p.dataset.st!==k});[].forEach.call(root.querySelectorAll(".panels [data-find]"),function(c){c.hidden=false});
 [].forEach.call(root.querySelectorAll(".ps"),function(s){s.hidden=false});
 if(scroll){var p=document.getElementById("pb-"+k);if(p)p.scrollIntoView({behavior:"smooth",block:"start"})}}
[].forEach.call(root.querySelectorAll(".pmore"),function(b){b.addEventListener("click",function(){var s=b.closest(".ps");s.classList.add("all");b.hidden=true})});
stns.forEach(function(s){s.addEventListener("click",function(){pick(s.dataset.st,true)});s.addEventListener("keydown",function(e){if(e.key==="Enter"||e.key===" "){e.preventDefault();pick(s.dataset.st,true)}})});
box.addEventListener("input",function(){var q=box.value.trim().toLowerCase().split(/\\s+/).filter(Boolean);if(!q.length){pick(cur);return}
 root.classList.add("finding");var n=0;stns.forEach(function(s){s.classList.remove("on")});
 [].forEach.call(root.querySelectorAll(".panels [data-find]"),function(c){var ok=q.every(function(w){return c.dataset.find.indexOf(w)>=0});c.hidden=!ok;if(ok)n++});
 [].forEach.call(root.querySelectorAll(".ps"),function(s){s.hidden=!s.querySelector("[data-find]:not([hidden])")});
 pans.forEach(function(p){p.hidden=!p.querySelector(".ps:not([hidden])")});out.textContent=n+" found";none.hidden=n>0});
var h=location.hash.slice(1),hit=h&&document.getElementById(h);
if(hit&&hit.classList.contains("ps")){var pp=hit.closest(".pp");pick(pp.dataset.st);setTimeout(function(){hit.scrollIntoView()},60)}
else if(h.indexOf("pb-")===0)pick(h.slice(3));else pick("write");
var still=window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches,svg=root.querySelector("svg.loop");
if(svg&&svg.pauseAnimations){if(still)svg.pauseAnimations();else if(window.IntersectionObserver)new IntersectionObserver(function(es){es[0].isIntersecting?svg.unpauseAnimations():svg.pauseAnimations()}).observe(svg)}})()</script>"""

PB_LOOP_CSS = r"""
.phead{padding-bottom:4px}
.ideas{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin:24px 0 0}
.idea{background:#15181A;color:#ECEEEA;border:3px solid var(--ink);border-top:8px solid var(--hivis);padding:18px 20px 20px;display:flex;flex-direction:column;gap:12px}
.idea.b-b{border-top-color:#6FBF73}
.idea .pb{align-self:flex-start;font:700 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;padding:5px 7px;background:#FBB401;color:#101316}
.idea.b-b .pb{background:#6FBF73}
.idea h2{margin:0;font:800 clamp(26px,3.2vw,38px)/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.idea h2 em{font-style:normal;color:#FBB401}.idea.b-b h2 em{color:#8FD694}
.idea .il{margin:0;font-size:14px;color:#C9D1D9}
.inc{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}
.inc li{display:grid;grid-template-columns:34px minmax(0,1fr);gap:10px;align-items:start;background:#F4F4EF;color:#101316;border:2px solid #101316;border-left:6px solid #C42B1C;padding:9px 12px;font-size:14px;line-height:1.45}
.inc .in{font:800 18px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;color:#C42B1C;padding-top:2px}
.inc code{background:rgba(16,19,22,.1);color:#101316}
.idea .ip{margin:auto 0 0;font-size:15px;color:#ECEEEA}.idea .ip b{color:#FBB401}.idea.b-b .ip b{color:#8FD694}
.ringbox{position:relative;margin:30px 0 0;border:3px solid var(--ink);background:var(--panel);padding:10px 10px 12px}
.loop{display:block;width:100%;height:auto;color:var(--ink)}
.loop .ring{fill:none;stroke:var(--ink);stroke-width:4}
.loop .ring-dash{fill:none;stroke:var(--hivis);stroke-width:2;stroke-dasharray:2 14;stroke-linecap:round}
.loop .o-cab{fill:#1F5FA8;stroke:#101316;stroke-width:2.5}
.loop .lt{font:700 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;fill:var(--ink)}
.loop .stn{cursor:pointer;outline:none}
.loop .sc{fill:var(--panel);stroke:var(--ink);stroke-width:3}
.loop .sn{font:800 22px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;fill:var(--ink)}
.loop .sl{font:800 17px/1 "Big Shoulders Display","Arial Narrow",sans-serif;letter-spacing:.04em;fill:var(--ink)}
.loop .stn:hover .sc,.loop .stn:focus-visible .sc{stroke:var(--brand)}
.loop .stn.on .sc{fill:var(--hivis);stroke:#101316}.loop .stn.on .sn{fill:#101316}
.loop .mid{font:800 26px/1 "Big Shoulders Display","Arial Narrow",sans-serif;letter-spacing:.06em;fill:var(--ink)}
.loop .mid2{font:500 13px/1 "Public Sans",system-ui,sans-serif;fill:var(--ink-3)}
.always{display:flex;flex-direction:column;align-items:flex-start;gap:4px;margin:8px auto 0;max-width:640px;width:100%;text-align:left;font:800 18px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;padding:12px 14px;border:2px dashed var(--ink-3);background:none;color:var(--ink);cursor:pointer}
.always small{font:500 12.5px/1.4 "Public Sans",system-ui,sans-serif;text-transform:none;color:var(--ink-2)}
.always.on{border-style:solid;border-color:#101316;background:var(--hivis);color:#101316}.always.on small{color:#101316}
.find{display:flex;align-items:center;gap:12px;margin-top:22px;max-width:640px;border:2px solid var(--ink);background:var(--panel);padding:0 0 0 14px}
.find span{font:700 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3)}
.find input{flex:1;min-width:0;border:0;background:none;color:var(--ink);font:500 15px/1 "Public Sans",system-ui,sans-serif;padding:13px 0;outline:none}
.find:focus-within{outline:3px solid var(--focus);outline-offset:2px}
.find output{font:600 11px/1 "Martian Mono",ui-monospace,monospace;color:var(--ink-3);padding-right:12px;white-space:nowrap}
.pfind{margin-top:22px}
.panels{margin-top:22px}
.pp{scroll-margin-top:72px}
.pp[hidden],.ps[hidden],.panels [data-find][hidden]{display:none}
.pph{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 16px;border-bottom:3px solid var(--ink);padding-bottom:8px;margin-bottom:6px}
.pph h2{margin:0;font:800 34px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.pph span{font-size:14px;color:var(--ink-3)}
#pbk.finding .pph{display:none}
.ps{margin:22px 0 0;scroll-margin-top:72px}
.ps header{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 12px;margin-bottom:12px}
.ps .pb{font:700 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;padding:5px 7px;background:#FBB401;color:#101316}
.ps.b-b .pb{background:#6FBF73}
.ps h3{margin:0;font:800 24px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.ps .pk{font:600 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.pcards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.pcards .rx{grid-column:1/-1}
#pbk:not(.finding) .ps:not(.all) .more{display:none}
#pbk.finding .pmore{display:none}
.pmore{grid-column:1/-1;justify-self:start;font:700 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;padding:10px 14px;border:2px solid var(--ink);background:var(--panel);color:var(--ink);cursor:pointer}
.pmore:hover,.pmore:focus-visible{background:var(--hivis);color:#101316;border-color:#101316}
.rc{position:relative}
.rc .rtag{position:absolute;top:-6px;right:10px;font:700 9px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;padding:4px 6px;background:#C42B1C;color:#fff}
.rc.real{border-top-color:#C42B1C!important}
.rc .rnum{font-style:normal;font:800 15px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;color:#101316;background:var(--hivis);padding:2px 6px;margin-right:8px;vertical-align:1px}
.rcm{display:flex;gap:10px;align-items:baseline;padding:10px 14px;border-top:2px solid #C42B1C;background:rgba(196,43,28,.1)}
.rcm b{flex:none;font:700 9.5px/1.5 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:#C42B1C}
:root[data-theme="dark"] .rcm b{color:#FF7A6E}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .rcm b{color:#FF7A6E}}
.rcm span{font-size:13.5px;line-height:1.5;color:var(--ink)}
.pbar{position:sticky;top:0;z-index:5;display:flex;flex-wrap:wrap;gap:6px;padding:10px 0;margin:16px 0 0;background:var(--ground);border-bottom:1px solid var(--line)}
.pbar button{display:inline-flex;align-items:center;gap:7px;font:800 15px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;letter-spacing:.03em;padding:8px 11px;border:2px solid var(--line);background:var(--panel);color:var(--ink);cursor:pointer}
.pbar button b{font:800 14px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;color:var(--ink-3)}
.pbar button.on{background:var(--hivis);color:#101316;border-color:#101316}.pbar button.on b{color:#101316}
#pbk.finding .pbar button{opacity:.6}
@media (max-width:860px){.pbar{position:static}}
.rc{display:flex;flex-direction:column;background:var(--panel);border:2px solid var(--ink);border-top:6px solid #FBB401}
.ps.b-b .rc{border-top-color:#6FBF73}
.rcr{padding:13px 14px 12px;font-size:15px;line-height:1.45;color:var(--ink)}
.rcw{margin-top:auto;display:flex;gap:10px;align-items:baseline;padding:10px 14px 12px;border-top:1px dashed var(--line);background:var(--panel-2)}
.rcw b{flex:none;font:700 9.5px/1.5 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.rcw span{font-size:13.5px;line-height:1.5;color:var(--ink-2)}
.rc code,.rx code{font:500 .86em "Martian Mono",ui-monospace,monospace;background:rgba(251,180,1,.2);padding:1px 5px;color:var(--ink)}
.rx p{margin:0 0 10px;max-width:72ch;color:var(--ink-2)}
.rx ol.check,.rx ol.steps{list-style:none;margin:0 0 12px;padding:0;border-top:1px solid var(--line)}
.rx .check li{display:grid;grid-template-columns:28px minmax(0,1fr);gap:12px;padding:10px 0;border-bottom:1px solid var(--line-2)}
.rx .check li::before{content:"";width:16px;height:16px;border:2px solid var(--brand);margin-top:4px}
.rx ol.steps{counter-reset:st}.rx ol.steps li{counter-increment:st;display:grid;grid-template-columns:40px minmax(0,1fr);gap:12px;padding:10px 0;border-bottom:1px solid var(--line-2)}
.rx ol.steps li::before{content:counter(st,decimal-leading-zero);font:800 17px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;color:#101316;background:var(--hivis);align-self:start;justify-self:start;padding:2px 6px;margin-top:3px}
.rx ul.plain{list-style:none;margin:0 0 12px;padding:0;display:flex;flex-direction:column;gap:8px;max-width:76ch}
.rx ul.plain li{position:relative;padding-left:22px;color:var(--ink-2)}.rx ul.plain li::before{content:"";position:absolute;left:0;top:.8em;width:12px;height:3px;background:var(--hivis)}
.rx .tw{overflow-x:auto;border:1px solid var(--line)}.rx table{border-collapse:collapse;width:100%;background:var(--panel);font-size:14.5px}
.rx th,.rx td{text-align:left;vertical-align:top;padding:10px 12px;border-bottom:1px solid var(--line-2)}.rx th{font:600 10.5px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);background:var(--panel-2)}
.rx h3.sub{margin:16px 0 8px;font:800 19px/1.1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;border-left:4px solid var(--hivis);padding-left:10px}
.full{margin:40px 0 20px;border:3px solid var(--ink)}
.full>summary{cursor:pointer;padding:14px 18px;font:800 20px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;list-style:none}
.full>summary::-webkit-details-marker{display:none}
.full>summary::after{content:" +";color:var(--brand)}.full[open]>summary::after{content:" \2212"}
.full[open]>summary{border-bottom:3px solid var(--ink)}
.full>.tabs,.full>.book,.full>.oglos{margin-left:18px;margin-right:18px}
#pbk:not(.js) .pp{display:block!important}
@media (max-width:860px){.ideas,.pcards{grid-template-columns:minmax(0,1fr)}.loop .sl{font-size:22px}.loop .sn{font-size:26px}}
@media (prefers-reduced-motion:reduce){.loop .wot{display:none}}
"""

# the Example board sheet: the real /f-board page, unchanged, with how to read it above
BOARD_KEYS = [
    ("The head", "The goal of the whole project, in one sentence. Every job is a bone leading to it.",
     '<rect x="24" y="10" width="46" height="34" fill="#FBB401" stroke="#101316" stroke-width="2"/><path d="M24 14h46" stroke="#101316" stroke-width="4" stroke-dasharray="4 4"/><path d="M2 27h18" stroke="currentColor" stroke-width="3"/><path d="M16 21l6 6-6 6" fill="none" stroke="currentColor" stroke-width="2.5"/>'),
    ("One bone, one job", "Numbered in the order they were planned, above and below the spine.",
     '<path d="M4 40h64" stroke="currentColor" stroke-width="3.5"/><path d="M22 40L12 18" stroke="currentColor" stroke-width="2.5"/><rect x="2" y="4" width="16" height="13" fill="none" stroke="currentColor" stroke-width="2"/><text x="10" y="14" text-anchor="middle" font-size="10" font-family="Martian Mono,monospace" fill="currentColor">3</text><path d="M48 40l12 0" stroke="currentColor" stroke-width="3.5"/>'),
    ("Its line says its state", "Solid: merged. Dotted: blocked. Dashed amber: waiting for your decision.",
     '<path d="M4 12h64" stroke="currentColor" stroke-width="3"/><path d="M4 27h64" stroke="currentColor" stroke-width="3" stroke-dasharray="1.5 5" stroke-linecap="round"/><path d="M4 42h64" stroke="#C98A00" stroke-width="3" stroke-dasharray="8 5"/>'),
    ("Yellow is next", "The job the last close picked to build next, also named at the top.",
     '<path d="M4 40h64" stroke="currentColor" stroke-width="3.5"/><path d="M36 40L22 12" stroke="#FBB401" stroke-width="4"/><rect x="12" y="2" width="20" height="13" fill="#FBB401" stroke="#101316" stroke-width="1.6"/>'),
    ("Each job's docket", "The tabs underneath: what the job is, what it needs, and what it left behind.",
     '<rect x="4" y="8" width="64" height="38" fill="none" stroke="currentColor" stroke-width="2.5"/><path d="M4 18h64" stroke="currentColor" stroke-width="2"/><rect x="4" y="8" width="16" height="10" fill="#FBB401" stroke="#101316" stroke-width="1.4"/><path d="M12 28h40M12 36h28" stroke="currentColor" stroke-width="2"/>'),
]


ABOUT_CSS = r"""
.ab .wrap{max-width:980px;margin:0 auto;padding:30px 32px 10px}
.abh{display:grid;grid-template-columns:auto minmax(0,1fr);gap:26px;align-items:center}
.abadge{width:160px;height:160px;filter:drop-shadow(5px 6px 0 rgba(0,0,0,.25))}
.abh .eyebrow{font:700 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--brand)}
.abh h1{margin:8px 0 6px;font:800 clamp(38px,6vw,64px)/.95 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.abline{margin:0;font-size:17px;color:var(--ink-2)}
.alinks{display:flex;flex-wrap:wrap;gap:10px;margin-top:14px}
.alink{font:700 12px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.06em;text-transform:uppercase;padding:9px 12px;border:2px solid var(--ink);background:var(--panel);color:var(--ink);text-decoration:none;box-shadow:3px 3px 0 var(--ink);transition:transform .12s,box-shadow .12s}
.alink:hover,.alink:focus-visible{transform:translate(-2px,-2px);box-shadow:5px 5px 0 var(--ink);background:#FBB401;color:#101316}
.ab .lede{margin:26px 0 0;max-width:62ch;font-size:17px;line-height:1.55}
.abfix{margin:-4px 0 14px;font-size:15px;color:var(--ink-2)}
.abst{margin:34px 0 12px;font:800 28px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
/* the systems as the floors of a building, oldest at the bottom; the newest carries the flag */
.tower{position:relative;max-width:720px;padding-top:44px}
.tflag{position:absolute;top:0;left:120px}.tflag .mark{height:46px;width:auto}
.floors{list-style:none;margin:0;padding:0;border-left:6px solid var(--ink);border-right:6px solid var(--ink)}
.fl{position:relative;display:grid;grid-template-columns:110px minmax(0,1fr);align-items:stretch;border-top:6px solid var(--ink);background:var(--panel)}
.fl .flno{display:flex;align-items:center;justify-content:center;font:700 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);border-right:2px dashed var(--line)}
.fl .flb{padding:14px 18px}
.fl b{font:800 24px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.fl .flw{margin-left:10px;font:600 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3)}
.fl p{margin:6px 0 0;font-size:14.5px;line-height:1.5;color:var(--ink-2);max-width:56ch}
.fl.top{background:#FBB401;color:#101316}.fl.top .flno{color:#101316;border-right-color:rgba(16,19,22,.35)}.fl.top p,.fl.top .flw{color:#30363B}
.fl.tbw .flb{opacity:.6}
.fl p.flwhy{margin-top:6px;font-size:13.5px}.fl p.flwhy b{margin-right:8px;font:700 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;padding:3px 6px;background:var(--ink);color:var(--ground);vertical-align:1px}
.fl.top p.flwhy b{background:#101316;color:#FBB401}
.fl .flurl{margin-left:4px;font:700 11px/1 "Martian Mono",ui-monospace,monospace;color:var(--ink);white-space:nowrap}
.fl .tbwtag{position:absolute;right:12px;top:12px;font:700 9px/1 "Martian Mono",ui-monospace,monospace;font-style:normal;letter-spacing:.1em;text-transform:uppercase;color:#C42B1C;border:1.5px dashed #C42B1C;padding:4px 6px;transform:rotate(3deg)}
.slab b{color:var(--ink);font-weight:800}
.slab{border:6px solid var(--ink);border-top-width:6px;background:repeating-linear-gradient(-45deg,var(--panel-2) 0 8px,var(--panel) 8px 16px);padding:12px 16px;font:700 10px/1.7 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.abnext{margin:26px 0 0;max-width:62ch;font-size:15px;color:var(--ink-2)}.abnext a{font-weight:700;color:var(--ink)}
@media (max-width:640px){.ab .wrap{padding:22px 16px 10px}.abh{grid-template-columns:minmax(0,1fr)}.abadge{width:120px;height:120px}.fl{grid-template-columns:72px minmax(0,1fr)}.fl b{font-size:20px}.tflag{left:60px}}
"""

BOARD_CSS = r"""
.wrap{max-width:1180px;margin:0 auto;padding:0 32px}
.bhead{padding:40px 0 10px}
.bhead .eyebrow{font:600 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--brand)}
.bhead h1{margin:12px 0 14px;font:800 clamp(44px,7vw,80px)/.9 "Big Shoulders Display","Arial Narrow",Impact,sans-serif;text-transform:uppercase}
.bhead .lede{max-width:70ch;color:var(--ink-2);margin:0;font-size:17px}
.bhead .lede code,.bkeep code{font:500 .86em "Martian Mono",ui-monospace,monospace;background:rgba(251,180,1,.2);padding:1px 5px;color:var(--ink)}
.bsyn{display:inline-block;margin-top:14px;font:700 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;padding:6px 8px;border:2px dashed var(--ink-3);color:var(--ink-2)}
.bkeys{list-style:none;margin:14px 0 0;padding:0;display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}
.bkeys li{border:2px solid var(--ink);background:var(--panel);padding:12px 12px 14px;display:flex;flex-direction:column;gap:8px}
.bkeys svg{width:72px;height:48px;color:var(--ink);flex:none}
.bkeys li>div{display:flex;flex-direction:column;gap:6px}
.bhow{margin:30px 0 0;font:800 28px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.bkeys b{font:800 18px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.bkeys .kn{font:800 14px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;color:var(--brand);margin-right:6px}
.bkeys span{font-size:13.5px;line-height:1.45;color:var(--ink-2)}
.bkeep{margin:16px 0 0;font-size:14.5px;color:var(--ink-2);max-width:90ch}
.bkeep a{color:var(--ink);font-weight:600}
.bframe{margin:22px 0 40px;border:3px solid var(--ink)}
.bframe .bfh{display:flex;justify-content:space-between;gap:10px;padding:8px 12px;border-bottom:2px solid var(--ink);background:var(--panel);font:600 10.5px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3)}
.bframe .bfh a{color:var(--ink)}
.bframe iframe{display:block;width:100%;height:1150px;border:0;background:var(--ground)}
@media (max-width:1100px){.bkeys{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media (max-width:720px){.wrap{padding:0 16px}.bkeys{grid-template-columns:minmax(0,1fr)}.bkeys li{flex-direction:row;align-items:flex-start;gap:12px}.bframe iframe{height:1400px}}

/* the key points at the board; the "nobody edits it by hand" line is a rule sign */
.bhow small{display:none;margin-left:10px;font:600 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.06em;text-transform:none;color:var(--ink-3);vertical-align:middle}
.bhow.live small{display:inline}
.bkeys.live li[data-hl]{cursor:pointer;transition:transform .12s,box-shadow .12s,background .15s}
.bkeys.live li[data-hl]:hover,.bkeys.live li[data-hl]:focus-visible{transform:translate(-2px,-2px);box-shadow:5px 5px 0 #FBB401;outline:none}
.bkeep{display:flex;flex-wrap:wrap;align-items:center;gap:10px 16px}
.bsign{display:inline-flex;align-items:stretch;border:2px solid #101316;background:#FBB401;color:#101316;box-shadow:3px 3px 0 #101316}
.bsign::before{content:"";flex:none;width:10px;background:repeating-linear-gradient(-45deg,#101316 0 5px,#FBB401 5px 10px);border-right:2px solid #101316}
.bsign b{display:flex;align-items:center;padding:0 9px;font:700 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;background:#101316;color:#FBB401}
.bsign span{padding:8px 12px;font:800 15px/1.15 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
@media (max-width:560px){.bhow.live small{display:block;margin:6px 0 0}}
.btop{margin:-4px 0 18px;font-size:14px;color:var(--ink-2)}.btop b{color:var(--ink)}
"""

BOARD_JS = '<script>(function(){var f=document.getElementById("boardframe");if(!f)return;\n/* the frame is sized to the board once it loads (hosted only). The board fills whatever height it is given, so it is not re-fitted after that */\nfunction fit(){try{var d=f.contentDocument;if(d&&d.documentElement){var h=d.documentElement.scrollHeight;if(h>200)f.style.height=(h+8)+"px"}}catch(e){}}\nvar ro=null;f.addEventListener("load",function(){fit();if(doc()&&doc().body){var hw=document.querySelector(".bhow");hw&&hw.classList.add("live");document.querySelector(".bkeys")&&document.querySelector(".bkeys").classList.add("live")}setTimeout(fit,400);});\nwindow.addEventListener("resize",function(){setTimeout(fit,200)});\n/* the key lights its part of the board: hover or focus to light, tap to light and bring it into view */\nvar parts={1:"rect.headbox, text.headt",2:"svg#fish g.rib",3:".fishbar .leg",4:"svg#fish g.rib.next, .status .nx, .jc.isnext",5:"section.panel"};\nfunction doc(){try{return f.contentDocument}catch(e){return null}}\nfunction ready(d){if(!d||d.getElementById("to-hl"))return;var st=d.createElement("style");st.id="to-hl";\n st.textContent=".to-hl{outline:3px solid #FBB401!important;outline-offset:4px;box-shadow:0 0 0 7px rgba(251,180,1,.25)!important}svg .to-hl{outline:none!important;filter:drop-shadow(0 0 3px #FBB401) drop-shadow(0 0 6px #FBB401)}";d.head.appendChild(st)}\nfunction light(k,show){var d=doc();if(!d||!d.body)return;ready(d);[].forEach.call(d.querySelectorAll(".to-hl"),function(e){e.classList.remove("to-hl")});if(!k)return;\n var els=d.querySelectorAll(parts[k]);[].forEach.call(els,function(e){e.classList.add("to-hl")});\n if(show&&els[0]){var r=els[0].getBoundingClientRect(),fr=f.getBoundingClientRect(),y=fr.top+r.top;if(y<60||y>innerHeight-80)scrollBy({top:y-innerHeight/3,behavior:"smooth"})}}\n[].forEach.call(document.querySelectorAll(".bkeys [data-hl]"),function(li){var k=li.getAttribute("data-hl");\n li.addEventListener("mouseenter",function(){light(k)});li.addEventListener("mouseleave",function(){light(0)});\n li.addEventListener("focus",function(){light(k)});li.addEventListener("blur",function(){light(0)});\n li.addEventListener("click",function(){light(k,true)})})})()</script>'

# the Playbooks sheet: who does what. The roles come from METHOD.md section 0's table, the rules from each role's playbook.
def method_roles() -> dict:
    """METHOD.md section 0: role -> (does, never), each split into items at top-level commas."""
    text = (ROOT / "METHOD.md").read_text(encoding="utf-8")
    sec = re.search(r"^## 0 · Roles\s*\n(.*?)(?=^## )", text, re.S | re.M)
    if not sec:
        raise SystemExit("build_site: METHOD.md needs '## 0 · Roles' with its role table")

    def items(cell):
        out, depth, cur = [], 0, ""
        for ch in cell:
            depth += ch == "("
            depth -= ch == ")"
            if ch == "," and depth == 0:
                out.append(cur.strip())
                cur = ""
            else:
                cur += ch
        return [x for x in [*out, cur.strip()] if x]

    roles = {}
    for ln in sec.group(1).splitlines():
        m = re.match(r"^\|\s*\*\*(\w+)\*\*\s*\|(.*)\|(.*)\|\s*$", ln)
        if m:
            roles[m.group(1).lower()] = (items(m.group(2).strip()), items(m.group(3).strip()))
    for r in ("foreman", "builder", "owner"):
        if r not in roles:
            raise SystemExit(f"build_site: METHOD.md section 0 has no row for {r}")
    return roles


# the Playbooks page in plain English: what each role does and each playbook section, short and without jargon.
# The playbooks' own text stays one click away ("Exact wording"). Each entry: ("p", intro) ("r", rule, why) ("a", question, aim)
# ("h", subheading) ("n", note) ("say", a line to send). PLAIN_HASH holds a hash of the source each entry was written from:
# when a playbook section changes, the build warns until the plain version is checked and its hash updated.
PLAIN_ROLES = {
    "foreman": (["Plans each job", "Settles every design question", "Writes every work order", "Reviews every change",
                 "Tests the code before and after each change", "Runs the inspection, in its own session", "Writes the repair work orders",
                 "Keeps the records"],
                ["Writes product code while the builder is building (unless you hand it over)"]),
    "builder": (["Sets up its own copy of the code", "Keeps the job file", "Runs the checks and saves their results", "Writes the code and its tests",
                 "Commits", "Fixes what the foreman accepts from each inspection", "Opens the PR when told"],
                ["Makes design decisions", "Explains away results it didn't expect", "Pushes or merges on its own"]),
    "owner": (['Say "go"', "Paste the builder's pointers, when there is no pane link", "Watch the PR",
               "Give your word for each act that needs it (the list is in `RULES.md`)"],
              ["Choose between technical options. The foreman decides on evidence and writes down what it turned down"]),
}

PLAIN = {
    "f-before-you-plan": [
        ("p", "Get the facts straight before planning."),
        ("r", "Test what it knows about the project, then check the answers", "shows where its picture is wrong before that becomes a wrong plan"),
        ("r", "Count things itself. Don't trust the last session's notes", "notes go stale within hours"),
        ("r", "Read the ticket, and the scope of every ticket linked to it", "on one job, the deciding fact was in another ticket"),
        ("r", "Check the code before trusting the board", "a ticket can look ready while the work it depends on isn't done"),
    ],
    "f-planning": [
        ("p", "Make every decision before the builder starts."),
        ("r", "Decide every open question, and write down the options turned down", "the builder gets answers, not questions, and turned-down ideas don't come back"),
        ("r", "Check that every new name isn't already used", "in one project, every name a ticket proposed was taken"),
        ("r", "Find the risky parts first, security above all", "these are the planning mistakes that matter most"),
        ("r", "Have the plan read once by a fresh reviewer (`/f-plancheck`) before work order 2", "nobody else checks the foreman's plan"),
        ("r", "Write down what must not change", "the builder can't guess what's off-limits"),
        ("r", "When testing a builder, hide the notes that give the answers away", "otherwise the test proves nothing"),
    ],
    "f-writing-a-work-order": [
        ("p", "Check every work order against this list before sending it."),
        ("r", 'Say what "done" means, right at the top', "the builder can check itself against it"),
        ("r", "One outcome per work order. Two outcomes: split it", ""),
        ("r", "Every decision labelled and final", ""),
        ("r", "Every command written out exactly", ""),
        ("r", "Pin the exact version of the code it starts from", ""),
        ("r", "Name the tests that must fail now and pass after", ""),
        ("r", "Include the list of bad inputs to test for", ""),
        ("r", "Run the existing tests before committing", ""),
        ("r", "Only ask for tests that can exist", "a real miss: a length test for a field with no length limit"),
        ("r", "List the only files the builder may read", ""),
        ("r", "Try any claim about logs or libraries before writing it in", "a real miss: a library logged an error the plan didn't expect"),
        ("r", "For page changes, click through it in a real browser", "a text test doesn't prove a page works"),
        ("r", "For character or prompt text, describe what the owner wants in words, not a list of banned words", ""),
        ("r", 'Ask for one report: "Needs from the foreman" first, and a "Not confirmed" section', ""),
        ("r", "Read it once for contradictions", ""),
        ("r", "Hand it over as a one-line pointer to the file, never pasted text", ""),
        ("r", "Never name the builder", ""),
        ("n", "Draft the next one or two while the current one runs. Each starts by checking the code is where it expects."),
    ],
    "f-reviewing-a-work-order": [
        ("p", "Check the work in this order, every time."),
        ("r", "Look at what changed on disk before reading the report", ""),
        ("r", "Prove the new tests fail on the old code and pass on the new", "a test that can't fail first is pinned by a mutation probe instead"),
        ("r", "Try to break the new code itself", ""),
        ("r", "Explain every change in the test results since last time", ""),
        ("r", "Write a separate note on any security code", ""),
        ("r", "Reproduce every problem before asking for a fix", ""),
        ("r", "Say whether the builder should be switched, and why", ""),
        ("r", "Update the job file", ""),
        ("n", "Run its own experiments outside the project folder."),
    ],
    "f-when-the-builder-stops": [
        ("p", "A stop is a gift, not a failure. Check first whether it was the foreman's mistake."),
        ("r", "Make sure it hears about the stop", "you tell it, or, when the sessions are linked, its watcher wakes it"),
        ("r", "Check the disk first, then read the report", ""),
        ("r", "A test that fails for no clear reason: find out why. Never rerun it until it passes", ""),
        ("r", "A test it asked for that can't exist: fix the work order, keep the builder's work, note the mistake", ""),
        ("r", "An attempt to break the code that should have failed but passed: that's a missing test. Add it", ""),
    ],
    "f-when-you-write-code-yourself": [
        ("p", "Only when you tell it to take over. The same rules apply."),
        ("r", "Run the existing tests before committing", "a foreman once committed first and broke four"),
        ("r", "Keep what other code relies on", "one fix dropped an error code other code needed"),
        ("r", "It can't approve its own fix. Security fixes always go back to the reviewer before the merge", ""),
        ("r", "Treat warnings as errors where they could leak input", ""),
    ],
    "f-the-end-game": [
        ("p", "Before the merge."),
        ("r", "Test before and after the change twice, once by each of them, and again at the very end", ""),
        ("r", 'Reproduce every review comment before acting on it. Fix it now or reject it with a reason. No "later"', ""),
        ("r", "Run the inspection itself, then send the work to a reviewer from a different model family", "the builder never reviews its own work"),
        ("r", "Check the PR for any builder name", ""),
        ("r", "If the repo uses automated review: at most three rounds, then stop for you", ""),
        ("r", "Re-read the PR description against the final result before asking you to merge", ""),
    ],
    "f-talking-to-the-owner": [
        ("p", "How the foreman deals with you."),
        ("r", "Decide on evidence. No menus of options", "you shouldn't have to judge technical choices"),
        ("r", "Ask you only for the acts listed in `RULES.md`", "everything else is its call"),
        ("r", "Report exactly what happened, mistakes included", 'a foreman once said "nothing was pushed" when it had been'),
        ("r", 'A general "yes" approves the goal, not each act', "it asks again for each act that needs your word"),
        ("r", "You confirm the next job before it starts", ""),
        ("r", "When every job is done, it tops the board out and stops. The next head is always yours to pick", "with jobs left, only your own words top it out"),
        ("r", "Every job starts with work order 1, research too", ""),
        ("r", "Every job gets merged, code or not", ""),
        ("r", "A standing goal isn't your word for each act", 'it stops at "ready for your word"'),
        ("r", "Except an autonomous run you started: that covers every step of that one job, and any failure stops it", ""),
        ("r", "Explain plainly before asking for your word", "twice in one job the owner had to ask why"),
        ("r", "Once something is decided, it stays decided unless new evidence appears", ""),
        ("r", "End every reply with a short status block", "so you, and it, always know where things stand"),
        ("r", "Say plainly when it is asking you to switch builders", ""),
    ],
    "f-tool-hygiene": [
        ("p", "Small things that cost time."),
        ("r", "Count Windows line endings with the command that counts them right", ""),
        ("r", "Write text full of quotes with a file tool, not the shell", ""),
        ("r", "Ask Git for one version at a time, so each value is clear", ""),
        ("r", "Edit a published page from a fresh copy of it", ""),
        ("r", "Remove paid keys before setting other variables, or the command won't run", ""),
        ("r", "Never write a home-made wait loop. Use the ones provided", "a home-made one once read 0 every time"),
        ("r", "On Windows, read the Windows notes in `SETUP.md` first", ""),
    ],
    "f-your-own-scorecard": [
        ("p", "After each job, it grades itself as hard as it grades the builder."),
        ("a", "Work orders it had to correct because of its own mistake", "0"),
        ("a", "Real bugs that got past its reviews", "0"),
        ("a", "Committed before running the existing tests", "never"),
        ("a", "Claimed something it hadn't checked", "never"),
        ("a", "Work orders used, against its estimate", "within the estimate"),
        ("n", "The trend matters more than the number."),
    ],
    "b-before-the-job": [
        ("p", "Before work order 1."),
        ("r", "Run a setup check. Nothing starts until it says READY", ""),
        ("r", "Tell the foreman which builder this is", "so it writes every work order to suit"),
        ("r", "When testing a builder, keep the answers out of its reach", ""),
    ],
    "b-every-work-order": [
        ("p", "What every work order gives the builder."),
        ("r", "Answers, never questions", "judgment is a light builder's weak spot"),
        ("r", "One step, one decision", "less to reason about"),
        ("r", "Exact commands and exact file paths", "nothing left to guess"),
        ("r", "Tests that fail now. The builder makes them pass", ""),
        ("r", "The list of bad inputs to test for", "on one job, every early bug came from this"),
        ("r", 'What "done" means, right at the top', ""),
        ("r", "One report at the end, then stop", "survives a session that stops halfway"),
        ("r", "The report opens with what it needs from the foreman", "so a blocker isn't buried"),
        ("r", "Report only what it saw. No excuses for surprises", ""),
        ("r", "Evidence for every claim. A claim without it counts as not done", "saying it's done when it isn't is the most common failure"),
        ("r", 'A "Not confirmed" section, with where it looked', ""),
        ("h", "Testing made thorough by rule"),
        ("r", "Every new line is tested, or has a reason not to be", ""),
        ("r", "Every safety check is tested by trying to break it, straight away", ""),
        ("r", "A standard list of six common gaps, checked every time", ""),
        ("r", "The report lists what wasn't tested", ""),
        ("n", "Aim for about 8 or 9 work orders for a mid-sized ticket. Don't ask a light builder to plan or review more: keep the thinking with the foreman."),
        ("h", "Bad inputs to test for"),
        ("r", "A missing field gives a clear error, never a default", ""),
        ("r", "A wrong type gives the same error", ""),
        ("r", "Hidden control characters in names are refused", ""),
        ("r", "Data that skipped the checks on the way in is checked again", ""),
        ("r", "An error never carries private data along with it", ""),
        ("r", "Only checked data is signed", ""),
    ],
    "b-handing-work-orders-over": [
        ("p", "A pointer, never pasted text."),
        ("r", "Never copy a work order out of the chat window", "it breaks long lines"),
        ("r", "Give the builder a one-line pointer instead", ""),
        ("say", "Read the file <path>, lines A to B only, and carry it out exactly as written."),
        ("r", "When the sessions are linked, the foreman sends the pointer itself", ""),
    ],
    "b-after-every-work-order": [
        ("p", "What happens after each one."),
        ("r", "Tell the foreman the work order is done", "linked sessions do this on their own"),
        ("r", "The foreman checks the disk first, then reads the report", ""),
        ("r", "It tries to break the new code and puts any problems in the next work order", ""),
    ],
    "b-when-to-switch-builders": [
        ("p", "Switch to a stronger builder only if a review finds:"),
        ("r", "A security problem", ""),
        ("r", "A repeat of something the work order warned about", ""),
        ("n", "Everyday test gaps are normal and get fixed in the next work order. Switching costs nothing, because each work order stands alone. When the foreman writes a new setup check, it is asking you to switch."),
    ],
    "b-where-a-light-builder-fits": [
        ("p", "What to give a light builder."),
        ("r", "Good at: settled designs, clear tests, small focused changes", ""),
        ("r", "Watch closely: anything touching logins, credentials or data leaving the service", ""),
        ("r", "Not its job: scoping, planning, choosing between designs", ""),
    ],
}

PLAIN_HASH = {
    "f-job": "09819ffef0",
    "f-before-you-plan": "30247e5f5b",
    "f-planning": "6e58c46fdf",
    "f-writing-a-work-order": "0df656a461",
    "f-reviewing-a-work-order": "2d933087ab",
    "f-when-the-builder-stops": "66ea3cb562",
    "f-when-you-write-code-yourself": "25d508d8f5",
    "f-the-end-game": "de867dde89",
    "f-talking-to-the-owner": "27e7a8073c",
    "f-tool-hygiene": "9f36e5fffc",
    "f-your-own-scorecard": "1aac6f628f",
    "b-job": "ffc33f1ee4",
    "b-before-the-job": "add6c507cc",
    "b-every-work-order": "2953598084",
    "b-handing-work-orders-over": "78a50f75cb",
    "b-after-every-work-order": "252dedbb5a",
    "b-when-to-switch-builders": "158e786ae1",
    "b-where-a-light-builder-fits": "e2b46bedc2",
    "y-job": "3ef2917545",
}


def plain_html(entries):
    """A plain section: an intro line, numbered rules (restarting under each subheading), notes and lines to send."""
    out, rules, n = [], [], 0

    def flush():
        if rules:
            out.append('<ol class="rl">' + "".join(rules) + "</ol>")
            rules.clear()

    for e in entries:
        k = e[0]
        if k in ("r", "a"):
            n += 1
            label = "Aim for" if k == "a" else ("Real miss" if e[2].startswith("a real miss: ") else "Why")
            why = e[2][len("a real miss: "):] if label == "Real miss" else e[2]
            cls = "rm" if label == "Real miss" else "rw"
            rules.append(f'<li><span class="rn">{n:02d}</span><div><div class="rr">{inline(e[1])}</div>'
                         + (f'<div class="{cls}"><b>{label}</b><span>{inline(why)}</span></div>' if why else "") + "</div></li>")
            continue
        flush()
        if k == "p":
            out.append(f'<p class="lead">{inline(e[1])}</p>')
        elif k == "h":
            out.append(f'<h3 class="sub">{esc(e[1])}</h3>')
            n = 0
        elif k == "n":
            out.append(f'<p class="nt">{inline(e[1])}</p>')
        elif k == "say":
            out.append(f'<div class="say"><b>Send exactly</b><code>{esc(e[1])}</code></div>')
    flush()
    return "".join(out)


def plain_check(sources):
    """sources: {page id: source text}. Every page needs a plain version; a changed source warns until re-checked."""
    import hashlib
    missing = [k for k in sources if k not in PLAIN and not k.endswith("-job")]
    if missing:
        raise SystemExit(f"build_site: no plain version for playbook section(s) {missing}: add them to PLAIN")
    if os.environ.get("PLAIN_REHASH"):  # PLAIN_REHASH=1 prints the current hashes, to paste into PLAIN_HASH after a re-check
        print("PLAIN_HASH = " + repr({k: hashlib.sha1(s.encode("utf-8")).hexdigest()[:10] for k, s in sources.items()}))
    stale = [k for k, s in sources.items() if PLAIN_HASH.get(k) != hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]]
    if stale:
        print(f"WARN plain wording may be stale for {stale}: re-read those playbook sections, update PLAIN, then the hashes in PLAIN_HASH")
    return {k: hashlib.sha1(s.encode("utf-8")).hexdigest()[:10] for k, s in sources.items()}


def reader_html(blocks):
    """A playbook section for the reader. Rule tables, checklists, steps and lists all become one numbered rule list;
    a bracketed 'a real miss' is lifted out under its rule; prose after the rules becomes a note; a line that is only
    code is shown as a line to copy. Returns (html, how many numbered rules)."""
    out, rules, n, total, seen_rule = [], [], 0, 0, False

    def rule(text, why="", label="Why"):
        nonlocal n, total
        n += 1
        total += 1
        miss = PB_MISS.search(text)
        if miss:
            text = PB_MISS.sub("", text)
        return (f'<li><span class="rn">{n:02d}</span><div><div class="rr">{inline(text)}</div>'
                + (f'<div class="rw"><b>{esc(label)}</b><span>{inline(why)}</span></div>' if why else "")
                + (f'<div class="rm"><b>Real miss</b><span>{inline(miss.group(1))}</span></div>' if miss else "") + "</div></li>")

    def flush():
        if rules:
            out.append('<ol class="rl">' + "".join(rules) + "</ol>")
            rules.clear()

    for k, ls in blocks:
        if k == "table":
            rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in ls if not re.match(r"^\|[\s|:-]+\|$", ln.strip())]
            head, body = rows[0], rows[1:]
            if len(head) == 2 and all(len(r) == 2 for r in body):
                label = "Aim for" if head[1].lower().startswith("aim") else "Why"
                rules.extend(rule(r[0], r[1], label) for r in body)
                seen_rule = True
                continue
            flush()
            out.append(PBK.render_block(k, ls))
            seen_rule = True
            continue
        if k in ("check", "steps", "bullets"):
            rules.extend(rule(ln[6:] if k == "check" else re.sub(r"^\d+\. ", "", ln) if k == "steps" else ln[2:]) for ln in ls)
            seen_rule = True
            continue
        flush()
        if k == "h3":
            out.append(PBK.render_block(k, ls))
            seen_rule, n = False, 0
            continue
        for ln in ls:
            if re.fullmatch(r"`[^`]+`", ln.strip()):
                out.append(f'<div class="say"><b>Send exactly</b><code>{esc(ln.strip()[1:-1])}</code></div>')
            elif seen_rule:
                out.append(f'<p class="nt">{inline(ln)}</p>')
            else:
                out.append(f"<p>{inline(ln)}</p>")
    flush()
    return "".join(out), total

REQ_JS = r"""<script>(function(){var r=document.getElementById("req"),pass=document.getElementById("pass");if(!r||!pass)return;r.classList.add("js");
var kits=[].slice.call(r.querySelectorAll(".kit")),keys=[],K="to-kit",have={};kits.forEach(function(k){if(keys.indexOf(k.dataset.k)<0)keys.push(k.dataset.k)});
try{have=JSON.parse(localStorage.getItem(K)||"{}")||{}}catch(e){have={}}
var n=pass.querySelector(".pn"),bar=pass.querySelector(".pbar i"),msg=pass.querySelector(".pmsg"),was=-1;
function save(){try{localStorage.setItem(K,JSON.stringify(have))}catch(e){}}
function paint(){var got=keys.filter(function(k){return have[k]}).length,all=got===keys.length;
 kits.forEach(function(k){var on=k.dataset.k==="builder"?have.builder===k.querySelector("b").textContent:!!have[k.dataset.k];k.classList.toggle("on",on);k.querySelector("button").setAttribute("aria-pressed",on?"true":"false")});
 n.textContent=got;bar.style.width=(100*got/keys.length)+"%";
 msg.textContent=all?"Every piece of kit is on site.":got?(keys.length-got)+" to go.":"Tap each piece of kit you already have.";
 pass.classList.toggle("done",all);if(all&&was>=0&&was<keys.length)pass.classList.add("fresh");was=got}
kits.forEach(function(k){k.querySelector("button").addEventListener("click",function(){var key=k.dataset.k,name=k.querySelector("b").textContent;
 if(key==="builder")have.builder=have.builder===name?"":name;else have[key]=!have[key];save();paint()})});
pass.querySelector(".preset").addEventListener("click",function(){have={};save();pass.classList.remove("fresh");paint()});
paint()})()</script>"""

REQ_CSS = r"""
.rq{padding-bottom:40px}
.rq .rhead2{padding-bottom:6px}
.rq h2{margin:34px 0 6px;font:800 30px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;display:flex;align-items:center;gap:12px}
.rq h2 small{font:700 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;padding:5px 7px;color:#101316}
.rq .k-core small{background:#3FAE6A}.rq .k-build small{background:#FBB401}.rq .k-opt small{background:var(--line);color:var(--ink)}
.rq .hint{margin:0 0 14px;max-width:70ch;color:var(--ink-2);font-size:15px}
.tiles{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}
.tile{display:grid;grid-template-columns:52px minmax(0,1fr);gap:4px 14px;align-items:start;padding:16px;border:2px solid var(--ink);background:var(--panel);box-shadow:4px 4px 0 rgba(0,0,0,.12)}
.tile .lg{grid-row:1/span 3;width:52px;height:52px;display:grid;place-items:center;border:2px solid var(--ink);background:#fff}
.tile .lg svg{width:30px;height:30px}
.tile .lg.mono{background:var(--ink)}.tile .lg.mono svg{fill:var(--ground)}
.tile .lg.img{padding:0;overflow:hidden}.tile .lg.img img{display:block;width:100%;height:100%}.tile .lg .pi{fill:#111}
.tile .lg.ini{font:800 21px/1 "Big Shoulders Display","Arial Narrow",sans-serif;color:#fff;letter-spacing:.02em}
.tile b{font:800 20px/1.05 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.tile .role{font:700 10px/1.2 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3)}
.tile p{margin:4px 0 0;font-size:14px;line-height:1.5;color:var(--ink-2)}
.k-build .tile{border-color:#FBB401;box-shadow:4px 4px 0 rgba(251,180,1,.35)}
.rq .anyb{margin-top:12px;padding:10px 14px;border-left:4px solid #FBB401;background:var(--panel);font-size:14.5px;max-width:80ch}
.rq .intro{margin:22px 0 0;max-width:72ch;font-size:15.5px;color:var(--ink-2)}.rq .intro b{color:var(--ink)}
.ind{display:grid;grid-template-columns:minmax(0,1fr) 290px;gap:28px;align-items:start;margin-top:14px}
.lvl{position:relative;margin-top:22px;padding:18px 18px 20px 22px;border:2px solid var(--ink);background:var(--panel)}
.lvl::before{content:"";position:absolute;left:-2px;top:-2px;bottom:-2px;width:8px;background:repeating-linear-gradient(-45deg,#FBB401 0 8px,#101316 8px 16px)}
.lvh{display:grid;grid-template-columns:auto minmax(0,1fr);gap:2px 14px;align-items:baseline;margin-bottom:14px}
.lvh .lvn{font:700 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;background:#101316;color:#FBB401;padding:6px 8px;grid-row:1/span 2;align-self:center}
.lvh h2{margin:0;font:800 28px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.lvh p{margin:0;color:var(--ink-3);font-size:14px}
.kits{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px 14px}
.kit{transform-origin:50% 0;transform:rotate(-.6deg)}.kit:nth-child(even){transform:rotate(.6deg)}
.kit button::before{content:"";position:absolute;left:50%;top:5px;width:8px;height:8px;margin-left:-4px;border-radius:50%;background:var(--panel);border:2px solid var(--ink)}
.kit button::after{content:"";position:absolute;right:0;top:0;bottom:0;width:7px;background:#B9C0BC;border-left:2px solid var(--ink);border-radius:0 7px 0 0;transition:background .25s}
.kit.on button::after{background:#3FAE6A}
@media (max-width:560px){.kits{grid-template-columns:minmax(0,1fr)}}
.kit button{position:relative;width:100%;height:100%;text-align:left;font:inherit;color:inherit;cursor:pointer;display:grid;grid-template-columns:44px minmax(0,1fr);gap:2px 12px;align-items:start;
 padding:18px 20px 14px 13px;border:2px solid var(--ink);border-radius:10px 10px 2px 2px;background:var(--ground);box-shadow:3px 3px 0 rgba(0,0,0,.14);transition:transform .15s,box-shadow .15s,background .2s,border-color .2s}
.kit button:hover{transform:translate(-1px,-2px);box-shadow:5px 6px 0 rgba(0,0,0,.16)}
.kit button:focus-visible{outline:3px solid var(--focus);outline-offset:2px}
.kit .lg{grid-row:1/span 3;width:44px;height:44px;display:grid;place-items:center;border:2px solid var(--ink);background:#fff}
.kit .lg svg{width:26px;height:26px}.kit .lg.mono{background:var(--ink)}.kit .lg.mono svg{fill:var(--ground)}
.kit .lg.img{overflow:hidden}.kit .lg.img img{display:block;width:100%;height:100%}.kit .lg .pi{fill:#111}
.kit .lg.ini{font:800 24px/1 "Big Shoulders Display",sans-serif;color:#fff}
.kit b{font:800 18px/1.05 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.kit button{padding-bottom:30px}
.kit .role{font:700 9.5px/1.2 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3)}
.kit p{margin:3px 0 0;font-size:13px;line-height:1.45;color:var(--ink-2)}
.kit .got{position:absolute;right:16px;bottom:8px;font:700 8.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;font-style:normal;
 padding:4px 5px;border:1.5px dashed var(--ink-3);color:var(--ink-3);transform:rotate(4deg)}
.rq:not(.js) .kit .got{display:none}.rq:not(.js) .kit button{cursor:default}.rq:not(.js) .pass{display:none}.rq:not(.js) .ind{grid-template-columns:minmax(0,1fr)}
.kit.on button{border-color:#1E7B4A;background:color-mix(in srgb,#3FAE6A 14%,var(--ground));box-shadow:3px 3px 0 #1E7B4A}
.kit.on .got{border:1.5px solid #101316;background:#3FAE6A;color:#101316;animation:got .28s cubic-bezier(.3,1.6,.5,1)}
@keyframes got{from{transform:rotate(4deg) scale(1.8);opacity:0}to{transform:rotate(4deg) scale(1);opacity:1}}
.bpick{margin-top:16px;padding-top:14px;border-top:1px dashed var(--line)}
.bpick h4{margin:0 0 4px;font:800 20px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.bpick h4 small{font:700 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;background:#FBB401;color:#101316;padding:4px 6px;margin-left:8px;vertical-align:middle}
.bpick>p{margin:0 0 10px;font-size:13.5px;color:var(--ink-2)}
/* the pass: a lanyard card that fills as you check your kit */
.pass{position:sticky;top:22px;margin-top:22px;background:#F4F4EF;color:#101316;border:3px solid #101316;box-shadow:6px 7px 0 rgba(0,0,0,.25);transform:rotate(1deg)}
.pass .clip{position:absolute;left:50%;top:-16px;width:44px;height:22px;margin-left:-22px;border:3px solid #101316;border-bottom:0;border-radius:12px 12px 0 0;background:#8A9096}
.pass .ph{display:flex;justify-content:space-between;align-items:center;background:#1E5BB0;color:#fff;padding:12px 14px;font:800 20px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.pass .ph span{font:700 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;color:#C9D8F0}
.pass .pb{position:relative;padding:14px 16px 16px;overflow:hidden}
.pass .pname{font:700 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:#5B6368}
.pass .pcount{margin:6px 0 10px;font:800 46px/1 "Big Shoulders Display",sans-serif}.pass .pcount b{font:inherit}
.pass .pbar{height:14px;border:2px solid #101316;background:#E2E4E1}
.pass .pbar i{display:block;height:100%;width:0;background:repeating-linear-gradient(-45deg,#FBB401 0 7px,#101316 7px 14px);transition:width .45s cubic-bezier(.3,.7,.3,1)}
.pass.done .pbar i{background:#3FAE6A}
.pass .pmsg{margin:10px 0 0;font-size:13.5px;color:#30363B}
.pass .pstamp{position:absolute;right:10px;top:10px;padding:6px 10px;border:3px solid #1E7B4A;color:#1E7B4A;font:800 18px/.95 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;text-transform:uppercase;text-align:center;transform:rotate(-12deg) scale(.6);opacity:0;transition:opacity .2s,transform .2s}
.pass.done .pstamp{opacity:1;transform:rotate(-12deg) scale(1)}
.pass.fresh .pstamp{animation:stamp .45s cubic-bezier(.3,1.5,.5,1)}
@keyframes stamp{0%{transform:rotate(-12deg) scale(2.4);opacity:0}100%{transform:rotate(-12deg) scale(1);opacity:1}}
.pass .pgo{display:none;margin-top:12px;padding-top:12px;border-top:1px dashed #9AA29C}.pass.done .pgo{display:block}
.pass .pgo p{margin:0 0 8px;font-size:13px;font-weight:600}.pass .pgo .pthen{margin:10px 0 6px;font-weight:500}
.pass .pgo .cmdline{display:block;max-width:100%}.pass .pgo .cmdline code{display:block;white-space:normal;overflow-wrap:anywhere;font-size:12px;line-height:1.45}
.pass .preset{margin-top:12px;background:none;border:0;padding:0;font:600 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;color:#5B6368;cursor:pointer;text-decoration:underline}
@media (prefers-reduced-motion:reduce){.kit.on .got,.pass.fresh .pstamp{animation:none}.kit button{transition:none}}
@media (max-width:980px){.ind{grid-template-columns:minmax(0,1fr)}.pass{order:-1;position:relative;top:auto;transform:none;margin-top:18px}
 .pass .clip{display:none}.pass .pcount{font-size:30px;margin:2px 0 6px}.pass .pb{padding:10px 14px 12px}.pass .ph{padding:8px 12px;font-size:16px}}
.rq .two{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:18px;margin-top:34px}
.rq .rno,.rq .ryours{border:3px solid var(--ink);padding:16px 18px 18px}
.rq .rno{background:repeating-linear-gradient(-45deg,rgba(224,68,47,.08) 0 10px,transparent 10px 20px),var(--panel)}
.rq .rno h3,.rq .ryours h3{margin:0 0 10px;font:800 24px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.rq .rno h3{color:#C42B1C}:root[data-theme="dark"] .rq .rno h3{color:#FF7A66}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .rq .rno h3{color:#FF7A66}}
.rq .ryours{background:#1E7B4A;color:#F4F4EF;border-color:#101316}
.rq .rno p,.rq .ryours p{margin:0;font-size:14.5px;line-height:1.55}
.rq .rfork{display:inline-block;margin-top:14px;padding:9px 13px;background:#FBB401;color:#101316;border:2px solid #101316;font:700 12px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.06em;text-transform:uppercase;text-decoration:none}
.rq .wn{margin-top:34px;border:2px solid var(--ink);background:var(--panel);padding:16px 20px}
.rq .wn h3{margin:0 0 8px;font:800 22px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.rq .wn ul{margin:0;padding-left:18px;font-size:14.5px;line-height:1.55;color:var(--ink-2)}.rq .wn li+li{margin-top:6px}
@media (max-width:760px){.rq .two{grid-template-columns:minmax(0,1fr)}}
"""

ROLES_CSS = r"""
.wrap{max-width:1240px;margin:0 auto;padding:0 32px}
.rhead2{padding:26px 0 0;display:grid;grid-template-columns:auto minmax(0,1fr);gap:10px 40px;align-items:end}
.rhead2 .eyebrow{grid-column:1/-1;font:600 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--brand)}
.rhead2 h1{margin:0;font:800 clamp(40px,5vw,64px)/.9 "Big Shoulders Display","Arial Narrow",Impact,sans-serif;text-transform:uppercase}
.rhead2 .lede{margin:0;max-width:64ch;color:var(--ink-2);font-size:15.5px;line-height:1.5}
.tabs{display:flex;align-items:stretch;gap:10px;margin-top:20px}
.tab{display:flex;align-items:center;gap:12px;padding:9px 16px 9px 12px;border:3px solid var(--ink);background:var(--panel);color:var(--ink);cursor:pointer;font:inherit;text-align:left;
 box-shadow:5px 5px 0 var(--ink);transition:transform .12s,box-shadow .12s,background .15s}
.tab:not([aria-selected="true"]):hover,.tab:not([aria-selected="true"]):focus-visible{transform:translate(-2px,-2px);box-shadow:7px 7px 0 var(--ink);background:var(--panel-2)}
.tab:not([aria-selected="true"]):active{transform:translate(3px,3px);box-shadow:2px 2px 0 var(--ink)}
.tab svg{width:38px;height:38px;flex:none}
.tab b{display:block;font:800 28px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.tab span span{display:block;margin-top:2px;font:600 9.5px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;opacity:.7}
.tab:hover{border-color:var(--hivis)}
.tab.f[aria-selected="true"]{background:#F4F4EF;color:#101316;border-color:#101316}
.tab.b[aria-selected="true"]{background:#FBB401;color:#101316;border-color:#101316}
.tab.y[aria-selected="true"]{background:#F4F4EF;color:#101316;border-color:#101316}
:root[data-theme="dark"] .tab.y:not([aria-selected="true"]) svg{filter:invert(.92)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .tab.y:not([aria-selected="true"]) svg{filter:invert(.92)}}
.tab[aria-selected="true"]{transform:translate(5px,5px);box-shadow:inset 0 -5px 0 #FBB401;cursor:default}
.tab.b[aria-selected="true"]{box-shadow:inset 0 -5px 0 #101316}
@media (prefers-reduced-motion:reduce){.tab{transition:none}}
.tab.y{margin-left:auto}
.flow{display:flex;flex-direction:column;justify-content:center;gap:6px;font:700 9px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-2)}
.flow div{white-space:nowrap;display:flex;align-items:center;gap:6px}.flow svg{width:44px;height:14px;color:var(--ink)}
.desk{margin:14px 0 28px;border:3px solid var(--ink);background:var(--panel)}
.pane{display:grid;grid-template-columns:290px minmax(0,1fr);min-height:0}
.pane[hidden]{display:none}
.side{border-right:2px solid var(--line);padding:12px 0 16px;overflow-y:auto}
.side h3{margin:16px 18px 2px;font:700 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3)}
.side p{margin:0 18px 8px;font-size:12.5px;line-height:1.4;color:var(--ink-3)}
.side code,.reader code{padding:0 3px!important;font:500 .86em "Martian Mono",ui-monospace,monospace;background:rgba(251,180,1,.2);padding:1px 4px;color:var(--ink)}
.side ul{list-style:none;margin:0;padding:0}
.srow{width:100%;display:flex;justify-content:space-between;align-items:center;gap:10px;padding:8px 14px;border:0;border-left:4px solid transparent;background:none;color:var(--ink);text-align:left;cursor:pointer;font:inherit}
.srow b{font:800 17px/1.05 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.srow i{flex:none;font:600 10px/1 "Martian Mono",ui-monospace,monospace;font-style:normal;color:var(--ink-3)}
.srow:hover b{color:var(--brand)}
.srow.on{background:rgba(251,180,1,.2);border-left-color:var(--hivis)}
.srow.on i{color:var(--ink)}
.srow.job b{font-size:19px}
.reader{overflow-x:hidden;scroll-margin-top:70px;padding:20px 28px 22px;overflow-y:auto;overscroll-behavior:contain;min-width:0}
.spage[hidden]{display:none}
.spage .sbar span+span{white-space:nowrap}
.spage .sbar{display:flex;justify-content:space-between;align-items:baseline;gap:10px;margin-bottom:6px;font:600 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.spage h4{margin:0 0 14px;font:800 32px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.spage .snav{display:flex;justify-content:space-between;gap:10px;margin-top:16px;padding-top:12px;border-top:1px solid var(--line)}
.spage .snav button{font:700 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.06em;text-transform:uppercase;padding:9px 11px;border:2px solid var(--ink);background:var(--panel);color:var(--ink);cursor:pointer}
.spage .snav button:hover,.spage .snav button:focus-visible{background:var(--hivis);color:#101316;border-color:#101316}
.spage h4.idea1{margin:0 0 18px;font:800 32px/1.05 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.idea1 em{font-style:normal;color:var(--brand)}
.dn{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);border:2px solid var(--line)}
.dn>div{padding:14px 18px}.dn>div+div{border-left:2px solid var(--line);background:rgba(196,43,28,.06)}
.dn h3{margin:0 0 10px;font:700 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase}
.dn .no h3{color:#C42B1C}
:root[data-theme="dark"] .dn .no h3{color:#FF7A6E}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .dn .no h3{color:#FF7A6E}}
.dn ul{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}
.dn li{position:relative;padding-left:20px;font-size:15px;line-height:1.4;color:var(--ink)}
.dn .do li::before{content:"";position:absolute;left:0;top:.45em;width:10px;height:10px;background:var(--hivis);border:1.5px solid #101316}
.dn .no li::before{content:"";position:absolute;left:1px;top:.65em;width:11px;height:3px;background:#C42B1C}
.jobnote{margin:14px 0 0;font-size:13.5px;color:var(--ink-3)}
.spage{max-width:860px}
[data-desk]:not(.exact) .ex,[data-desk].exact .pl{display:none}
.wsw{display:flex;margin:4px 18px 6px;border:2px solid var(--ink)}
.wsw button{flex:1;padding:7px 8px;border:0;background:var(--panel);color:var(--ink-2);cursor:pointer;font:700 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase}
.wsw button+button{border-left:2px solid var(--ink)}
.wsw button[aria-pressed="true"]{background:var(--ink);color:var(--panel)}
.wsw button:hover{color:var(--ink)}.wsw button[aria-pressed="true"]:hover{color:var(--panel)}
.side .wnote{margin:0 18px 10px;font-size:12px;line-height:1.4;color:var(--ink-3)}
.reader .body p.lead{margin:0 0 12px;font-size:16px;line-height:1.5;color:var(--ink)}
.reader .body>p{margin:0 0 12px;font-size:15px;line-height:1.55;color:var(--ink-2)}
.reader .body ol.rl{list-style:none;display:block;margin:0 0 14px;padding:0;border-top:1px solid var(--line)}
.rl li{display:grid;grid-template-columns:34px minmax(0,1fr);gap:10px;padding:11px 0;border-bottom:1px solid var(--line)}
.rl .rn{font:800 17px/1.25 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;color:var(--brand)}
.rl .rr{font-size:15px;line-height:1.5;color:var(--ink)}
.rl .rw,.rl .rm{display:flex;gap:10px;align-items:baseline;margin-top:5px;font-size:13.5px;line-height:1.5;color:var(--ink-2)}
.rl .rw b,.rl .rm b{flex:none;font:700 9.5px/1.6 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.rl .rm{padding:6px 10px;border-left:3px solid #C42B1C;background:rgba(196,43,28,.08);color:var(--ink)}
.rl .rm b{color:#C42B1C}
:root[data-theme="dark"] .rl .rm b{color:#FF7A6E}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .rl .rm b{color:#FF7A6E}}
.reader .body p.nt{margin:4px 0 12px;padding:10px 14px;border-left:3px solid var(--hivis);background:rgba(251,180,1,.1);font-size:14px;line-height:1.55;color:var(--ink)}
.say{display:flex;flex-direction:column;gap:6px;margin:4px 0 14px;padding:12px 14px;border:2px solid var(--ink);background:var(--panel-2)}
.say b{font:700 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.reader .say code{background:none;padding:0;font-size:13.5px;line-height:1.5;white-space:normal}
.spage .snav button{display:flex;flex-direction:column;gap:5px;max-width:48%;text-align:left}
.spage .snav button+button,.spage .snav span+button{text-align:right;align-items:flex-end}
.spage .snav button small{font:800 16px/1.05 "Big Shoulders Display","Arial Narrow",sans-serif;letter-spacing:0;text-transform:uppercase}
.reader .body ul,.reader .body ol{margin:0 0 10px;padding-left:20px;display:flex;flex-direction:column;gap:6px;font-size:14.5px;color:var(--ink)}
.reader .body ol.check,.reader .body ol.rules{list-style:none;padding:0}
.reader .body .check li{display:grid;grid-template-columns:22px minmax(0,1fr);gap:8px}.reader .body .check li::before{content:"";width:13px;height:13px;border:2px solid var(--brand);margin-top:3px}
.reader .body .rules li{display:grid;grid-template-columns:30px minmax(0,1fr);gap:8px;padding:9px 0;border-bottom:1px dashed var(--line)}
.reader .body .rules .rn{font:800 16px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;color:var(--ink-3)}
.reader .body .rules .rw{margin-top:4px;font-size:13.5px;color:var(--ink-2)}.reader .body .rules .rw b{font:700 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);margin-right:6px}
.reader .body .tw{overflow-x:auto}.reader .body table{border-collapse:collapse;width:100%;font-size:13.5px}.reader .body th,.reader .body td{text-align:left;vertical-align:top;padding:7px 8px;border-bottom:1px solid var(--line)}
.reader .body h3.sub{margin:12px 0 6px;font:800 16px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
@media (min-width:1001px) and (min-height:620px){
 [data-desk].js .wrap{height:100vh;display:flex;flex-direction:column}
 [data-desk].js .desk{flex:1;min-height:0;display:flex}
 [data-desk].js .pane{flex:1;min-height:0}
}
@media (max-width:1000px){.flow{display:none}.tabs{flex-wrap:wrap}.tab.y{margin-left:0}.pane{grid-template-columns:minmax(0,1fr)}.side{border-right:0;border-bottom:2px solid var(--line)}}
@media (max-width:640px){.wrap{padding:0 16px}.rhead2{grid-template-columns:minmax(0,1fr)}.tabs{gap:6px;flex-wrap:nowrap}.tab{flex:1 1 0;min-width:0;gap:6px;padding:7px 8px}.tab svg{width:26px;height:26px}.tab b{font-size:20px}.tab span span{display:none}
 .reader{padding:16px}.dn{grid-template-columns:minmax(0,1fr)}.dn>div+div{border-left:0;border-top:2px solid var(--line)}.spage h4.idea1{font-size:25px}}
@media (max-width:440px){.tab{justify-content:center}.tab svg{display:none}}
/* four tabs on a phone sit two by two, each with room for its name; the raised shadow is smaller */
@media (max-width:640px){.tabs:has(>.tab:nth-of-type(4)){display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 10px}
 .tab{box-shadow:3px 3px 0 var(--ink)}.tab[aria-selected="true"]{transform:translate(3px,3px)}.tabs .tab .tn{display:none}.tab b{font-size:19px;line-height:1.05}}

/* a role's limits as a red prohibition sign, its duties under a black tab; your words on hi-vis tags */
.dn .do h3,.dn .no h3{display:inline-flex;align-items:center;gap:8px;padding:6px 10px;border:2px solid #101316;box-shadow:2px 2px 0 #101316}
.dn .do h3{background:#101316;color:#FBB401}
.dn .no h3,:root[data-theme="dark"] .dn .no h3{background:#C42B1C;color:#fff}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .dn .no h3{color:#fff}}
.dn .no h3::before{content:"";flex:none;width:12px;height:12px;border-radius:50%;border:2.5px solid #fff;background:linear-gradient(45deg,transparent 40%,#fff 40% 60%,transparent 60%)}
.reader .body ul.ywords{list-style:none;margin:6px 0 0;padding:0;border-top:1px solid var(--line)}
.reader .body ul.ywords li{margin:0;display:grid;grid-template-columns:200px minmax(0,1fr);gap:14px;align-items:center;padding:9px 0;border-bottom:1px solid var(--line)}
.ywords .wq{display:flex;flex-wrap:wrap;gap:5px}
.ywords q{quotes:none;font:700 12.5px/1.2 "Martian Mono",ui-monospace,monospace;background:#FBB401;color:#101316;border:2px solid #101316;padding:4px 8px;box-shadow:2px 2px 0 #101316}
.ywords a{font-size:14px;color:var(--ink-2);text-decoration:none}.ywords a b{color:var(--ink)}
.ywords a:hover b{text-decoration:underline;text-decoration-color:#FBB401;text-decoration-thickness:2px}
@media (max-width:560px){.ywords li{grid-template-columns:minmax(0,1fr);gap:6px}}
"""

ROLES_JS = """<script>(function(){var root=document.querySelector("main[data-desk]");if(!root)return;root.classList.add("js");
var q=function(s,el){return[].slice.call((el||root).querySelectorAll(s))};
function tab(r){q(".tab").forEach(function(t){t.setAttribute("aria-selected",t.dataset.rtab===r?"true":"false")});q(".pane").forEach(function(p){p.hidden=p.dataset.role!==r})}
function show(id,scroll){var pg=document.getElementById(id);if(!pg||!pg.classList.contains("spage"))return;var pane=pg.closest(".pane");tab(pane.dataset.role);
 q(".spage",pane).forEach(function(s){s.hidden=s!==pg});q(".srow",pane).forEach(function(b){b.classList.toggle("on",b.dataset.open===id)});
 var rd=pane.querySelector(".reader");rd.scrollTop=0;
 if(scroll&&!matchMedia("(min-width:1001px) and (min-height:620px)").matches){var top=rd.getBoundingClientRect().top;if(top<0||top>innerHeight*.6)rd.scrollIntoView()}}
function wording(w){root.classList.toggle("exact",w==="ex");q("[data-w]").forEach(function(b){b.setAttribute("aria-pressed",b.dataset.w===w?"true":"false")});try{localStorage.setItem("to-wording",w)}catch(x){}}
try{if(localStorage.getItem("to-wording")==="ex")wording("ex")}catch(x){}
root.addEventListener("click",function(e){var w=e.target.closest("[data-w]");if(w){wording(w.dataset.w);return}var t=e.target.closest("[data-rtab]"),o=e.target.closest("[data-open]");
 if(t){tab(t.dataset.rtab);var cur=root.querySelector('.pane[data-role="'+t.dataset.rtab+'"] .spage:not([hidden])');if(cur)try{history.replaceState(null,"","#"+cur.id)}catch(x){}}
 else if(o){show(o.dataset.open,true);try{history.replaceState(null,"","#"+o.dataset.open)}catch(x){}}});
function go(){var h=decodeURIComponent(location.hash.slice(1));if(!h)return;var el=document.getElementById(h);if(!el)return;if(el.dataset.rtab)tab(el.dataset.rtab);else show(h,false)}
window.addEventListener("hashchange",go);go()})()</script>"""

FRONT_SUBS = [("#access", "Install"), ("#pillars", "Why Topping Out"), ("#route", "Order of works"), ("#shift", "The night shift"),
              ("#lost", "Nothing is lost"), ("#why", "But why not just?"),
              ("#needs", "Requirements"), ("#see", "See it")]

FRONT = {
    "title": "Topping Out",
    "description": "Topping Out, a software factory methodology for AI coding agents: a foreman plans, a cheap builder builds, two inspections check, and you give the word. Runs in your own repo.",
    "board_kicker": "A software factory methodology",
    "headline": ["Stop babysitting agents.", "Hire a foreman."],
    # the site board's list of who runs the site: (icon, role, the one line that sets it apart)
    "roles": [
        ("foreman", "Foreman", "Never writes product code."),
        ("builder", "Builder", "Never makes design decisions."),
        ("inspectors", "Inspectors", "Never fix: findings go back to the foreman."),
        ("you", "Owner: you", "Gives the word: on each merge, or once for the whole night."),
    ],
    # the owner's angle (requests file, 2026-10-26): long runs without drift, a cheap builder, a Claude Code limit that lasts.
    # The link preview (foreman-site-tools/og-card.mjs) carries this same line, read from the built page.
    "subline": "Runs for hours, even overnight, without drifting: every job starts fresh from files. A cheap model does the heavy coding, so your Claude Code limit lasts far longer.",
    # the strip under the hero: (point, its one line). No numbers until one is confirmed
    "edge": [
        ("No drift", "A fresh session for every job. The plan, work orders, reviews and handover are files, not chat memory."),
        ("Cheaper", "The builder does the token-heavy work. The foreman only plans, checks and decides."),
        ("Proof", "Every job ends with what was asked, what was built, what was tested and what was found."),
    ],
    "shift_cmd": "/goal night shift: 3 jobs, auto-pick",
    # why Topping Out, in four pillars: (title, the one line); the sign each one is posted as is in SIGNS, same order
    "pillars": [
        ("Cheaper", "The foreman decides, so a cheap model can build."),
        ("Checked end to end", "Two inspections and a checklist. “Done” has to be proven."),
        ("Runs the night shift", "Hand it a list at night. Wake up to merged jobs."),
        ("Nothing forgotten", "A new session picks up where the last one stopped."),
    ],
    # the hero's night, one caption per step: (clock from, clock to, step, what happens), hours past midnight of the first day
    "night_caps": [
        (9, 17.5, "You plan", "settle each job's ticket by day"),
        (19, 22.5, "One line starts the shift", "/goal night shift: jobs 11, 12, 13"),
        (23, 25.5, "Board 11", "built, inspected, merged"),
        (25.5, 27.5, "Board 12", "on top of board 11's merged code"),
        (27.5, 29.5, "Board 13", "the shift ends when the list does"),
        (30.5, 31.5, "One summary", "three jobs merged, waiting for you"),
    ],
    "shift_lede": "List the jobs before bed. Wake up to merged work.",
    # the shift clock: (when, title, text, command, kind)
    "shift": [
        ("By day", "You plan", "Settle each job's ticket and its open questions, so nothing stalls at night.", "", "you"),
        ("Evening", "One line starts the shift", "Name the jobs, or let it pick them. Add a spend cap if a walkthrough needs a live key.", "/goal night shift: jobs 11, 12, 13", "you"),
        ("Night", "Board 11", "A fresh foreman takes it from its opener to the merge, closes it, and writes the next opener.", "", "job"),
        ("Night", "Board 12", "Starts from the opener board 11 left, on top of its merged code.", "", "job"),
        ("Night", "Board 13", "Same again. The shift ends when the list does.", "", "job"),
        ("Morning", "One summary", "Each job merged or stopped, the PR links, the spend, and any verdict only you can give.", "", "you"),
    ],
    "shift_rules": [
        "Any problem stops the whole shift, with one line saying why. A usage limit only pauses it.",
        "Done means merged in the repo, never \"done\" in the chat.",
        "Nothing outside the ticket: no messages, migrations, force pushes or spend over the cap.",
        "Start small: two or three jobs a night.",
    ],
    "lost_lede": "Sessions forget. Topping Out writes down what each job learned and where it stopped, and the next session starts there.",
    # what carries over between sessions: (name, where, what)
    # Nothing is lost: where the method keeps memory, as a cutaway of the site.
    # (id, name, file, what it holds, written by, read by, how long it lasts, the time scale it belongs to)
    "memory": [
        ("job", "J12, being built", "the job file", "The plan, the decisions and the work orders, kept current as the job runs.",
         "The foreman, all through the job.", "`/f-signoff`, to write the cards and the handover.", "The job", "now"),
        ("handover", "The handover", "foreman/handovers/", "Where the job ended, what is owed, and a short quiz.",
         "`/f-signoff`, every job.", "The next foreman, which answers the quiz cold.", "One session", "next"),
        ("opener", "The next opener", "foreman/handovers/OPENER-JOB-<N>.txt", "Six lines that start the next job.",
         "`/f-signoff`, every job.", "A fresh session: you paste it, or the night shift does.", "One session", "next"),
        ("board", "The board", "foreman/projects/<slug>/BOARD.json", "Every job's state, and which job comes next.",
         "`/f-board`, one event at a time.", "You, on `board.html`; each close, to pick the next job.", "The project", "project"),
        ("card", "From lesson to card", "skills/f-card/ and /f-signoff step 3.2", "A lesson is found, checked for a twin, shown to you, then filed.",
         "`/f-card` any time; `/f-signoff` at the close.", "Filed without your yes.", "", "process"),
        ("logbook", "The Logbook", "foreman/logbook/", "Every lasting lesson as a card, with its evidence.",
         "`/f-card` any time; `/f-signoff` at the close.", "`/f-shift` at every job start; `/f-search` any time.", "The project", "project"),
        ("search", "/f-search", "skills/f-search/", "Finds the cards on a topic.",
         "Any time.", "Current cards only. For older ones: `/f-archive-search`.", "", "tool"),
        ("context", "/f-context", "skills/f-context/", "A cold read of a repo, with its matching cards.",
         "New to a repo, or before re-planning.", "`/f-shift` already does this for each job.", "", "tool"),
        ("catchup", "/f-catchup", "skills/f-catchup/", "Writes cards for past jobs that never got any.",
         "Once, or after a gap.", "Waits for your yes.", "", "tool"),
        ("dream", "/f-dream", "skills/f-dream/", "Merges repeated lessons and spots repeat mistakes.",
         "Now and then.", "Each change needs your yes and can be undone.", "", "tool"),
        ("rules", "The foundations", "AGENTS.md or CLAUDE.md, and RULES.md", "Lessons that keep coming back, made firm rules.",
         "`/f-distill`, with your approval.", "Every session, before any work.", "For good", "forever"),
        ("archive", "The archive", "foreman/logbook/archived/", "Old cards moved aside, with an index to find them.",
         "`/f-archive`, by itself past 250 cards.", "`/f-archive-search`, when a search finds nothing.", "For good, out of the way", "forever"),
    ],
    # the route in plain words: (step, who, needs your word, the skills that do it). Every skill on the
    # Atlas route must appear in exactly one step; the build checks it. Who: foreman, builder, inspectors, you.
    "route_once": [
        ("Shape the idea", "foreman", False, ["f-sketch", "f-survey"]),
        ("Write the plan", "foreman", False, ["f-blueprint"]),
        ("Check the plan", "inspectors", False, ["f-plancheck"]),
        ("Cut into tickets", "foreman", False, ["f-schedule"]),
    ],
    "route_loop": [
        ("Start the shift", "foreman", True, ["f-shift"]),
        ("Build", "builder", False, []),
        ("Inspect", "inspectors", False, ["f-inspect", "pack-review", "xreview", "adjudicate"]),
        ("Open the PR", "foreman", True, []),
        ("Review the PR", "foreman", True, ["f-greploop"]),
        ("Merge", "foreman", True, []),
        ("Close", "foreman", True, ["f-signoff", "f-board"]),
    ],
    "route_notes": {"Build": "one work order at a time, test-first; the foreman reviews each one",
                    "Inspect": "gate 2 first, then two inspections",
                    "Review the PR": "Greptile reviews it, three rounds at most",
                    "Close": "a day report, the next job picked and researched, the handover written"},
    # the six skills to start with, in the route's own words: (skill, route step, who, what it does, what you get)
    "featured": [
        ("f-survey", "Shape the idea", ["foreman", "you"], "Asks you only the questions that change the plan, and settles the rest from the code.", "a brief with every question answered"),
        ("f-shift", "Start the shift", ["foreman"], "Stands up a fresh session as the foreman, with the job's Logbook cards loaded, then confirms the job's facts.", "a foreman that knows the job before it touches it"),
        ("f-inspect", "Inspect", ["inspectors"], "Sends fresh specialist reviewers over the finished work, before any PR exists.", "a list of findings: no fixes, no verdict"),
        ("f-signoff", "Close", ["foreman"], "Closes a merged job only when every acceptance check has passed. Nothing is deferred.", "the job closed and archived, its lessons logged, then the board close"),
        ("f-board", "Track the work", ["foreman"], "Records every job on the project board, from started to merged. Each close names the next job.", "a board that always shows where the project stands"),
        ("f-card", "Keep the lesson", ["foreman"], "Writes one lasting lesson as a Logbook card. Later sessions load the cards that matter.", "a lesson the next session already knows"),
    ],
    # what the install needs, and what /f-setup lays out (the folders are SETUP.md section 1's)
    # the requirements: the setup this is built and run on, (name, what it is for); then the optional add-ons
    "needs": [
        ("Windows", "What it is built and run on every day, with Git Bash and PowerShell."),
        ("Claude Code", "The foreman runs here, and the skills are its commands."),
        ("Git and GitHub", "Work reaches `main` only through a pull request."),
        ("GitHub CLI", "`gh`: the night shift and the review rounds use it."),
        ("Node", "Runs the installer and the checks."),
        ("Python 3", "Draws the project board."),
        ("Pi, in Orca", "The builder's agent, in the pane beside the foreman."),
        ("Greptile", "Review rounds on each pull request."),
        ("OpenRouter", "Voice, and the councils."),
        ("A builder", "Any agent that can read a file, run a shell and write a report. I use GLM 5.3."),
    ],
    # the requirements sheet: (logo, brand colour, name, its job here, why); logo None draws its initials
    "req_core": [
        ("windows", "#0078D4", "Windows 11", "the machine", "Built and run here, every day."),
        ("gnubash", "#4EAA25", "Git Bash", "the shell", "Most commands run here."),
        ("powershell", "#5391FE", "PowerShell", "the other shell", "For the calls Git Bash rewrites."),
        ("claude", "#D97757", "Claude Code", "the foreman", "Plans, inspects, signs off."),
        ("pi", "", "Pi", "the builder's agent", "The builder runs here, beside the foreman."),
        ("img:orca", "", "Orca", "the workspace", "Foreman and builder, side by side."),
        ("img:greptile", "", "Greptile", "the review rounds", "Up to three review rounds per PR."),
        ("img:openrouter", "", "OpenRouter", "the key", "Voice, and the councils."),
        ("git", "#F03C2E", "Git", "the records", "Every job, plan and lesson is a file."),
        ("github", "", "GitHub and gh", "the merge", "Work reaches `main` only by pull request."),
        ("nodedotjs", "#5FA04E", "Node", "the installer", "Runs the installer and the checks."),
        ("python", "#3776AB", "Python 3", "the board", "Draws the project board."),
    ],
    "req_builders": [
        ("img:zai.svg", "", "GLM 5.3", "Z.ai, on subscription", "Builds each work order."),
    ],
    "needs_opt": [
        ("Greptile", "Review rounds on the pull request, when you say greploop."),
        ("Orca", "Puts the builder in the pane beside the foreman. Without it, you carry one-line pointers."),
        ("An OpenRouter key", "Voice, and the councils."),
    ],
    # the skeptic's questions: (question, the answer in one line, one short sentence of proof, the source)
    "skeptic": [
        ("Why not one agent for everything?",
         "The agent that made a mistake would be the one judging it.",
         "So an AI from another company checks the work cold. It once caught a race the foreman had passed.",
         "Foreman Playbook, \"The one idea\""),
        ("Why not just write better prompts?",
         "A prompt asks. A check proves.",
         "Each test must fail before the code and pass after it, and every requirement needs evidence before the job closes.",
         "`METHOD.md` sections 7 and 10"),
        ("Why does it need my OK?",
         "Merging and pushing reach beyond your machine.",
         "They wait for you. On a night shift, your /goal line is the OK, for those jobs only.",
         "`RULES.md`, \"Acts that need the owner's exact word\""),
        ("Isn't it slow and costly?",
         "More steps per job. Less of your time.",
         "A cheap model on a flat subscription does the building, the checks catch problems first, and jobs run while you sleep.",
         "the Requirements page; the night shift above"),
        ("Am I locked in?",
         "No. It is plain text files in your own repo.",
         "Stop using it, and the plans, the lessons and the board stay.",
         "`SETUP.md`, \"What Topping Out adds to your repo\""),
        ("What if it breaks at night?",
         "The shift stops, and says why.",
         "A red check, a failed walkthrough or a security finding halts it.",
         "the night shift above"),
        ("What if the builder cuts corners?",
         "Its report is never taken on its word.",
         "Every requirement needs a pass with evidence, or the job does not close.",
         "`METHOD.md` section 10, the acceptance ledger"),
        ("Will it fit my project?",
         "Yes. It adds files and overwrites nothing.",
         "Setup adds one foreman/ folder and a short profile of your project.",
         "`SETUP.md` section 1"),
        ("Does it work on Mac or Linux?",
         "Expected to, not yet verified.",
         "It is tested on Windows 11. The installer and checks are Node and Python, and the work orders are Bash.",
         "`SETUP.md` section 9, \"Tested setup\""),
    ],
    "install_lede": "My own setup, shared as it is. I can only support what I use.",
    "gaps": [
        "The example board is synthetic: a made-up project, labelled as one.",
    ],
    # the sheets, each with its preview image (docs/assets/see/<preview>-<light|dark>.webp, made by the site tools' previews.mjs)
    # and the page it was taken from, so the build can say when a preview is older than its page
    "see": [
        ("route.html", "Order of works", "Every step, who does it, where you say OK.", "", "route", "route.html"),
        ("repo.html", "Your repo", "Every folder it adds, and what writes it.", "", "repo", "repo.html"),
        ("logbook.html", "Logbook", "Every lesson a job learned, kept as a card.", "", "logbook", "logbook.html"),
        ("skills.html", "Skills and agents", "Each one: what it does, how to tell it worked.", "", "skills", "skills.html"),
        ("atlas.html", "Skill Atlas", "Every skill on one map, with its links.", "", "atlas", "raw/atlas.html"),
        ("playbooks.html", "Playbooks", "Every rule, with the mistake that made it.", "", "playbooks", "raw/foreman-playbook.html"),
        ("board.html", "Example board", "Ten jobs: merged, next, stuck.", "Synthetic data", "board", "raw/board.html"),
        ("requirements.html", "Requirements", "The kit, as a site induction.", "", "requirements", "requirements.html"),
    ],
}

# The install as it will work at launch (the owner's call, 2026-10-06: show it as if it exists).
# Confirmed by the development session on 2026-10-26 (requests-file entry 4, closed): a fresh clone of the public
# repo, the installer's 18/18 self-tests, and an install into an empty repo. If these commands change, set
# "confirmed" back to False until they are re-checked: every build then warns, so the site never shows a dead command.
INSTALL = {
    "confirmed": True,
    "repo": "kaithoughtarchitect/toppingout",
    "steps": [
        ("Get the package", "Anywhere on your machine. Needs git.", "git clone https://github.com/kaithoughtarchitect/toppingout"),
        ("Set up your repo", "In Claude Code, in the repo that will hold your records.", "Read <path to the package>/skills/f-setup/SKILL.md and follow it"),
        ("Update later", "Replaces the files your repo didn't adapt and lists the ones it did; it waits while a job is open.", "/f-setup"),
    ],
}

# D14: the Deep Agents add-on, one short line per part of addons/deep-agents/README.md (the build checks the parts still match)
ADDON_SHORT = {
    "skill/deep/": ("/deep", "Sends any agent to the reference before it plans, builds or reviews agent code."),
    "deepagents-ref/": ("deepagents-ref/", "A wiki checked against the real deepagents code, with checked recipes and a beginner's guide."),
    "mcp.json": (".mcp.json", "LangChain's live docs server, for what the reference doesn't cover."),
    "starter/": ("The skeleton", "A running agent with six tests and CI. Only for a new project."),
}


# D20: one job, start to finish, in the hero: five site stations, your part and its part. The lanes are the site's short words
# for README "One job, from your side"; each station names the README steps it comes from and the phrases those steps must
# still hold, so the build stops when the README changes. (role icon, station, README steps, phrases, you, it)
ONE_JOB = [
    ("foreman", "Site walk", [1, 2], ["Give the foreman a ticket", "It walks the site", '"go"'],
     'Give it a ticket, then say <q>go</q>.', "Walks the site: reads the ticket and the code."),
    ("builder", "Build", [3], ["It writes work orders", "you paste each pointer into the builder", "or the pane link does it"],
     "Paste each work order&rsquo;s pointer, or the pane link does.", "Writes the work orders; the builder builds them, test-first."),
    ("inspectors", "Inspect", [3], ["the two inspections and the acceptance ledger"],
     "", "Two inspections, then the acceptance ledger."),
    ("you", "Your word", [4], ['("open the PR")', 'on "greploop"', "up to three Greptile rounds", '**"merge"** when the evidence satisfies you'],
     '<q>Open the PR</q>, then <q>merge</q> when the evidence satisfies you.', 'Opens the PR; on <q>greploop</q>, up to three Greptile rounds.'),
    (None, "Merged", [5], ["It closes the job, saves the lessons", "proposes the next ticket for you to confirm"],
     "Confirm the next ticket.", "Closes the job, saves the lessons, proposes the next ticket."),
]


# D20 part 3: the same five stations under an explicit grant. (you, it or None to keep "With you"'s) per station, per mode.
# Source: README line 12 and "What it is not"; RULES.md "The one exception: an autonomous run" and "A night shift".
GOAL_AUTO = "/goal autonomous run: <opener>, until done or stopped"
GOAL_NIGHT = "/goal night shift: jobs 13, 17, until done or stopped"
ONE_JOB_MODES = {
    "auto": [
        (f"In a fresh session, one line: <code>{GOAL_AUTO.replace("<", "&lt;").replace(">", "&gt;")}</code>", "Walks the site, and answers its own survey questions with its starred pick."),
        ("Nothing: the pane link carries the pointers.", None),
        ("", "Two inspections, then the ledger. What goes red is repaired, not a stop."),
        ("Nothing to say: your goal covers the PR, up to three Greptile rounds, and the merge.", "Opens the PR, runs the rounds, merges."),
        ("Read the PR body and the dev report: every answer it gave itself is listed, for you to reverse.", "Closes the job, pushes the records, and stops. It never starts the next job."),
    ],
    "night": [
        (f"Before bed, one line: <code>{GOAL_NIGHT}</code>", "The shift boss opens a fresh foreman per job and types its goal for you."),
        ("Nothing: the pane link carries the pointers.", None),
        ("", "Two inspections, then the ledger. What goes red is repaired, not a stop."),
        ("Covered by each job&rsquo;s goal.", "Opens the PR, runs the rounds, merges."),
        ("Read the morning report.", "Closes the job; the boss starts the next. Several floors by morning."),
    ],
}
ONE_JOB_RULES = ["**What goes red is repaired, not a stop.**", "Ask only where these rules or `METHOD.md` name an owner step", "**two repair rounds**", "a security-class finding or an unresolved critical one",
                 "Greptile under 5/5 after three rounds", "spend reaching the cap", "**It never covers:**", "a fourth Greptile round", "or starting the next job",
                 "**Any stop in a job ends the shift, and so does a topping out**", "a job past 16 hours", "Every survey answer it gave itself",
                 "shift boss"]
ONE_JOB_STOPS = ("<b>It still stops and waits</b>, one line saying why, on: the same failure red after two repair rounds; a security finding or an "
                 "unresolved critical one; Greptile under 5/5 after three rounds; spend reaching your cap.")
ONE_JOB_NEVER = ("<b>Your goal never covers</b> tracker moves, messages, edits outside the ticket&rsquo;s files, migrations, a force push, "
                 "a fourth Greptile round, spend over the cap, or starting the next job.")
ONE_JOB_NIGHT = "<b>The shift ends</b> at any stop in a job, at a topping out, at the cap, or when a job passes 16 hours."


def one_job_check_rules() -> None:
    rules = (ROOT / "RULES.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for ph in ONE_JOB_RULES:
        if ph not in rules:
            raise SystemExit(f"build_site: RULES.md no longer says {ph!r}: re-check the one-job strip's modes")
    for ph in ("With an autonomous-run goal", "with the pane link carrying the pointers", "Any other standing goal grants nothing"):
        if ph not in readme:
            raise SystemExit(f"build_site: README no longer says {ph!r}: re-check the one-job strip's modes")


# D22: what comes after topping out, the same in every mode (README "Topping out", METHOD.md section 11b)
ONE_JOB_NEXT = (
    '<div class="ojnext"><span class="ojnl" aria-hidden="true">Then</span>'
    '<div class="ojb2 ojrep" data-b="0"><span class="ojtag i">It</span><b>The report</b>'
    '<p>The board is frozen as the record: what was built, what&rsquo;s carried over, and three to five next <em>heads</em>. '
    'A head is the next goal: what a new board will build toward.</p>'
    '<ul class="ojheads" aria-label="Candidate next heads">' + "".join(f'<li style="--h:{k}"{" class=\"pick\"" if k == 1 else ""}>Head {k + 1}</li>' for k in range(4)) + '</ul></div>'
    '<div class="ojb2 ojpick" data-b="1"><span class="ojtag y">You</span><b>You pick one</b>'
    '<p>Whenever you&rsquo;re ready. In every mode: an autonomous run or a night shift tops out and stops; the next head is always yours.</p></div>'
    '<div class="ojb2 ojnew" data-b="2"><span class="ojtag i">It</span><b>A new board</b>'
    '<svg viewBox="0 0 160 34" aria-hidden="true"><path d="M2 30h86" stroke="currentColor" stroke-width="3"/>'
    '<rect class="ojplot" x="12" y="6" width="64" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-dasharray="4 3"/>'
    '<text x="96" y="26" font-family="Martian Mono,monospace" font-weight="700" font-size="10" fill="currentColor">floor 0</text></svg>'
    '<p>An empty plot for the new head, and the job loop starts again.</p></div></div>')


def one_job_steps() -> list:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    sec = re.search(r"^### One job, from your side\s*\n(.*?)(?=^---|^## )", text, re.S | re.M)
    if not sec:
        raise SystemExit("build_site: README.md needs '### One job, from your side'")
    steps = re.findall(r"^\d+\. (.+)$", sec.group(1), re.M)
    if len(steps) != 5:
        raise SystemExit(f"build_site: README 'One job, from your side' has {len(steps)} steps, the front page draws 5")
    for _i, name, refs, phrases, _y, _t in ONE_JOB:
        src = " ".join(steps[r - 1] for r in refs)
        for ph in phrases:
            if ph not in src:
                raise SystemExit(f"build_site: README 'One job' step(s) {refs} no longer say {ph!r}: re-check ONE_JOB[{name!r}]")
    method = (ROOT / "METHOD.md").read_text(encoding="utf-8")
    for must in ("freezes it as the project's record", "writes what was built and what's carried over",
                 "offers three to five candidate next heads", "You pick one, whenever you're ready, and the cycle starts again on a new board"):
        if must not in text:
            raise SystemExit(f"build_site: README's topping out paragraph no longer says {must!r}: re-check the strip's last band")
    if "choosing the next head is always the owner's" not in method:
        raise SystemExit("build_site: METHOD.md section 11b no longer says choosing the next head is always the owner's")
    for must in ("Autonomy comes only from an explicit grant", "**How to start:**"):
        if must not in text:
            raise SystemExit(f"build_site: README no longer says {must!r}: re-check the one-job strip's footnote")
    return steps


ONE_JOB_VIS = [
    # what each station shows; at rest every one is in its finished state
    '<svg class="ojv" viewBox="0 0 64 40" aria-hidden="true"><rect x="16" y="3" width="30" height="35" fill="var(--ground)" stroke="currentColor" stroke-width="2.4"/>'
    '<path class="ojw" d="M21 12h20M21 19h20M21 26h13" stroke="currentColor" stroke-width="2.4"/></svg>',
    '<svg class="ojv" viewBox="0 0 64 40" aria-hidden="true">' + "".join(f'<circle class="ojt" style="--d:{k}" cx="{14 + 18 * k}" cy="20" r="7" stroke="currentColor" stroke-width="2.4"/>' for k in range(3))
    + '</svg>',
    '<svg class="ojv" viewBox="0 0 64 40" aria-hidden="true"><g class="ojs2" transform="rotate(-8 32 20)"><rect x="9" y="9" width="46" height="22" fill="none" stroke="#2F8F55" stroke-width="3"/>'
    '<text x="32" y="25.5" text-anchor="middle" font-family="Martian Mono,monospace" font-weight="800" font-size="12" fill="#2F8F55">PASS</text></g></svg>',
    '<svg class="ojv" viewBox="0 0 64 40" aria-hidden="true"><g class="ojq"><path d="M6 5h52v22H26l-9 9v-9H6Z" fill="#FBB401" stroke="#101316" stroke-width="2.4" stroke-linejoin="round"/>'
    '<text x="32" y="20.5" text-anchor="middle" font-family="Martian Mono,monospace" font-weight="800" font-size="11" fill="#101316">merge</text></g>'
    '<g class="ojq ojgoal" transform="rotate(-6 32 20)"><rect x="5" y="8" width="54" height="22" fill="none" stroke="#101316" stroke-width="3"/>'
    '<text x="32" y="23.5" text-anchor="middle" font-family="Martian Mono,monospace" font-weight="800" font-size="11" fill="#101316">/goal</text></g></svg>',
    '<svg class="ojv" viewBox="0 0 64 40" aria-hidden="true"><g class="ojm"><rect x="12" y="22" width="40" height="13" fill="#FBB401" stroke="currentColor" stroke-width="2.4"/>'
    '<path d="M32 4v13M25 11l7 7 7-7" fill="none" stroke="currentColor" stroke-width="2.6"/></g></svg>',
]


def one_job_html() -> str:
    one_job_steps()
    one_job_check_rules()

    def mv(you_html, auto_html, night_html):
        return (f'<span class="mv m-you">{you_html}</span><span class="mv m-auto">{auto_html}</span><span class="mv m-night">{night_html}</span>')
    floor = '<svg class="ri" viewBox="0 0 48 48" aria-hidden="true"><path d="M8 40h32M12 40V20h24v20" fill="none" stroke="currentColor" stroke-width="2.6"/><rect x="12" y="12" width="24" height="8" fill="#FBB401" stroke="#101316" stroke-width="2.4"/></svg>'
    cols = []
    for k, ((icon, name, _r, _p, you, it), vis) in enumerate(zip(ONE_JOB, ONE_JOB_VIS)):
        ic = ROLE_ICONS[icon] if icon else floor
        nothing = '<i class="ojnil">Nothing. It carries on.</i>'
        (ay, ai), (ny, ni) = ONE_JOB_MODES["auto"][k], ONE_JOB_MODES["night"][k]
        title = mv(esc(name), "Covered by your goal", "Covered by your goal") if k == 3 else esc(name)
        cols.append(f'<div class="ojst" data-s="{k}"><div class="ojhd"><span class="ojn">{k + 1}</span>{ic}<b>{title}</b>{vis}</div>'
                    f'<p class="ojy">{mv(you or nothing, ay or nothing, ny or nothing)}</p><p class="oji">{mv(it, ai or it, ni or it)}</p></div>')
    floors = "".join(f'<rect class="ojf" style="--f:{k}" x="22" y="{128 - 24 * k}" width="76" height="22" fill="var(--panel)" stroke="currentColor" stroke-width="3"/>'
                     f'<path class="ojf" style="--f:{k}" d="M32 {135 - 24 * k}h10M54 {135 - 24 * k}h10M76 {135 - 24 * k}h10" stroke="currentColor" stroke-width="3"/>' for k in range(4))
    bld = ('<div class="ojb"><svg viewBox="0 0 120 160" aria-hidden="true"><path d="M4 151h112" stroke="currentColor" stroke-width="3"/>'
           f'{floors}<g class="ojtop"><rect x="14" y="50" width="92" height="7" fill="#FBB401" stroke="#101316" stroke-width="2.4"/>'
           '<path d="M98 50V20" stroke="currentColor" stroke-width="2.6"/><path d="M98 21h18l-5 6 5 6H98Z" fill="#E0442F" stroke="#101316" stroke-width="2"/></g>'
           '<g class="ojfz" transform="rotate(-8 60 140)"><rect x="18" y="131" width="84" height="18" fill="var(--panel)" stroke="#E0442F" stroke-width="2.2"/>'
           '<text x="60" y="143.5" text-anchor="middle" font-family="Martian Mono,monospace" font-weight="800" font-size="7.6" fill="#E0442F" textLength="76" lengthAdjust="spacingAndGlyphs">FROZEN: THE RECORD</text></g></svg>'
           '<p class="ojcap"><b>Topped out</b><span>Each merged job adds a floor; the last one gets the beam and the flag.</span></p></div>')
    modes = "".join(f'<input type="radio" name="ojm" id="ojm-{m}" value="{m}"{" checked" if m == "you" else ""}><label for="ojm-{m}"><b>{t}</b><small>{c}</small></label>'
                    for m, t, c in (("you", "With you", "You give each word: go, open the PR, merge."),
                                    ("auto", "Autonomous run", "One /goal line takes one job to the merge."),
                                    ("night", "Night shift", "One line before bed: several jobs in a row.")))
    lim = (f'<div class="ojlim mvb m-auto m-night"><p>{ONE_JOB_STOPS} After a stop it goes on only on your word.</p><p>{ONE_JOB_NEVER}</p>'
           f'<p class="mvb m-night">{ONE_JOB_NIGHT} <a href="#shift">The night shift, in full &darr;</a></p></div>')
    return ('<div class="oj" id="oj"><div class="ojk"><b>Watch one job</b><span>Your part, and its part, from ticket to merge.</span></div>'
            f'<div class="ojways"><span class="ojwl" id="ojwl">Three ways to run a job:</span><div class="ojmode" role="radiogroup" aria-labelledby="ojwl">{modes}</div></div>'
            '<div class="ojg"><div class="ojlab" aria-hidden="true"><span></span><span class="y">You</span><span class="i">It</span></div>'
            + "".join(cols) + bld + ONE_JOB_NEXT + '</div>'
            '<div class="ojfoot"><div class="ojlim ojyou mvb m-you"><p><b>Every word is yours.</b> Nothing passes <q>go</q>, <q>open the PR</q>, <q>greploop</q> or <q>merge</q> without you, and the next ticket waits for your yes.</p>'
            '<p><b>It moves on without you only on an explicit grant:</b> an autonomous run for one job, or a night shift. Any other standing goal grants nothing.</p>'
            '<p><b>It asks you only where a step is yours:</b> the acts <code>RULES.md</code> lists, a deferral, the next ticket. Technical choices it makes on evidence, and writes down what it turned down.</p></div>'
            + lim + '</div></div>'
            + ONE_JOB_JS)


ONE_JOB_JS = (r"""<script>(function(){var r=document.getElementById("oj");if(!r||matchMedia("(prefers-reduced-motion:reduce)").matches||matchMedia("(max-width:640px)").matches||!window.IntersectionObserver)return;
var st=[].slice.call(r.querySelectorAll(".ojst")),g=r.querySelector(".ojg"),t=document.createElement("div");t.className="ojtk";t.setAttribute("aria-hidden","true");g.appendChild(t);
var job=0,s=-1,tm=null,on=false;function place(){var e=st[Math.max(s,0)],a=e.querySelector(".ojhd"),n=e.querySelector(".ojn");t.style.transform="translate("+Math.max(e.offsetLeft+a.offsetWidth-t.offsetWidth-8,e.offsetLeft+n.offsetLeft+n.offsetWidth+6)+"px,"+(e.offsetTop-25)+"px)"}
function reset(){job=0;s=-1;r.classList.remove("topped");[].forEach.call(r.querySelectorAll(".ojb2"),function(e){e.classList.remove("hit","now")});[].forEach.call(r.querySelectorAll(".ojf"),function(f){f.classList.remove("on")});st.forEach(function(e){e.classList.remove("hit","now")})}
function tick(){if(!on)return;var d=900;
 if(s===4){[].forEach.call(r.querySelectorAll('.ojf[style*="--f:'+job+'"]'),function(f){f.classList.add("on")});job++;
  if(job===4){r.classList.add("topped");st.forEach(function(e){e.classList.remove("now")});t.classList.remove("on");var bs=[].slice.call(r.querySelectorAll(".ojb2"));
   var beat=function(b){bs.forEach(function(e,k){e.classList.toggle("now",k===b);if(k<=b)e.classList.add("hit")});if(b<2){tm=setTimeout(function(){beat(b+1)},2200)}else{tm=setTimeout(function(){reset();tick()},2600)}};
   tm=setTimeout(function(){beat(0)},1400);return}
  s=-1;st.forEach(function(e){e.classList.remove("hit","now")});d=500}
 else{s++;st.forEach(function(e,k){e.classList.toggle("now",k===s)});st[s].classList.add("hit");t.textContent="Ticket 0"+(job+1);t.classList.add("on");place();d=s===4?1100:950}
 tm=setTimeout(tick,d)}
r.classList.add("play");reset();
new IntersectionObserver(function(es){var v=es[0].isIntersecting;if(v&&!on){on=true;tick()}else if(!v&&on){on=false;clearTimeout(tm)}},{threshold:.3}).observe(r);
addEventListener("resize",function(){if(s>=0)place()})})()</script>""")


def addon_parts() -> list:
    text = (ROOT / "addons" / "deep-agents" / "README.md").read_text(encoding="utf-8")
    parts = re.findall(r"^\| `([^`]+)` \|", text, re.M)
    if sorted(parts) != sorted(ADDON_SHORT):
        raise SystemExit(f"build_site: addons/deep-agents/README.md parts {parts} no longer match ADDON_SHORT")
    return [ADDON_SHORT[k] for k in parts]


# D19: the add-on's kit, with LangChain's own logos (langchain.com/brand-assets, as supplied: the light file on a light page,
# the dark one on a dark page, never recoloured or stretched, clear space kept). Shown as works-with, never as a partner badge.
# Facts: addons/deep-agents/starter/requirements.txt, .env.example, deepagents-ref/LEARN.md sections 1, 5 and 6.
ADDON_KIT = {
    "installed": [
        ("deepagents", "Deep Agents", "Version 0.7.29, pinned."),
        ("langchain", "LangChain", "Comes with Deep Agents."),
        ("langgraph", "LangGraph", "Comes with LangChain. The skeleton adds its SQLite and Postgres checkpoints."),
    ],
    "optional": ("langsmith", "LangSmith", "A free account for tracing and LangGraph Studio; paid hosting later. The add-on needs none of it."),
}


def lc_logo(key: str, name: str, ext_dark: str = "png") -> str:
    return (f'<span class="lcl"><img class="lt" src="assets/brands/langchain/{key}-light.svg" alt="{esc(name)}">'
            f'<img class="dk" src="assets/brands/langchain/{key}-dark.{ext_dark}" alt="{esc(name)}"></span>')


def addon_html(parts: bool = False) -> str:
    req = (ROOT / "addons" / "deep-agents" / "starter" / "requirements.txt").read_text(encoding="utf-8")
    if "deepagents==0.7.29" not in req:
        raise SystemExit("build_site: the skeleton no longer pins deepagents==0.7.29: update ADDON_KIT")
    inst = "".join(f'<li>{lc_logo(k, n)}<span>{d}</span></li>' for k, n, d in ADDON_KIT["installed"])
    ok, on, od = ADDON_KIT["optional"]
    tiles = "".join(f'<li><code>{esc(n)}</code><span>{esc(d)}</span></li>' for n, d in addon_parts()) if parts else ""
    return ('<div class="addon"><div class="adh"><span class="adt">Optional add-on</span><h3>Deep Agents</h3>'
            '<p>Only for an AI agent built on LangChain, LangGraph or Deep Agents. <code>/f-setup</code> asks first, and installs it only on yes. '
            'Topping Out itself needs none of it.</p></div>'
            '<div class="adkit">'
            f'<div class="adc"><h4>Needs</h4><div class="adpy">{brand_mark("python", "#3776AB")}<b>Python 3.11+</b><span>Deep Agents requires it.</span></div></div>'
            f'<div class="adc adin"><h4>Installed for you <small>on yes</small></h4><ul>{inst}</ul></div>'
            f'<div class="adc"><h4>Optional</h4><ul><li>{lc_logo(ok, on, "svg")}<span>{esc(od)}</span></li></ul></div></div>'
            + (f'<ul class="adparts">{tiles}</ul>' if parts else "")
            + '<p class="adneed">Works with LangChain&rsquo;s open-source tools. The logos are LangChain&rsquo;s own, shown as supplied; '
            'no partnership or endorsement is implied. The docs and the package the add-on cites are fetched at install, not shipped.</p></div>')


def enforced_rows() -> list:
    """README "What software enforces, and what is only instructed": (promise, enforced by, the rest of that cell, not prevented)."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    sec = re.search(r"^## What software enforces, and what is only instructed\s*\n(.*?)(?=^## )", text, re.S | re.M)
    if not sec:
        raise SystemExit("build_site: README.md needs '## What software enforces, and what is only instructed'")
    rows = []
    for ln in sec.group(1).splitlines():
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) != 3 or cells[0] in ("Promise", "") or set(cells[0]) <= set("-: "):
            continue
        m = re.match(r"\*\*(.+?)\*\*[:,]?\s*(.*)$", cells[1])
        if not m:
            raise SystemExit(f"build_site: README enforced table row {cells[0]!r} has no bold 'enforced by'")
        rows.append((cells[0], m.group(1).rstrip(":,"), m.group(2), cells[2]))
    if len(rows) < 4:
        raise SystemExit("build_site: README enforced table has too few rows")
    return rows


def enforced_html() -> str:
    lis = []
    for promise, by, rest, gap in enforced_rows():
        kind = "ins" if by.startswith("instruction") else "chk"
        lis.append(f'<li class="{kind}"><b>{inline(promise)}</b><span class="eby">{esc(by)}</span>'
                   f'<details><summary>What it doesn&rsquo;t stop</summary><p>{inline(rest[:1].upper() + rest[1:]) + " " if rest else ""}</p><p class="egap">{inline(gap[:1].upper() + gap[1:])}.</p></details></li>')
    return ('<div class="enf"><h3>Enforced, or only instructed <small>from the README</small></h3>'
            '<p>Most of the method is instructions the agents follow; a few checks are scripts that refuse.</p>'
            f'<ul>{"".join(lis)}</ul></div>')

BASE_CSS = r"""

/* the welcome: Kai's badge and a speech bubble, bottom right, first visit only */
.welcome{position:fixed;right:22px;bottom:22px;z-index:70;display:flex;align-items:flex-end;gap:10px;max-width:440px;transform:translateY(30px);opacity:0;transition:transform .45s cubic-bezier(.3,1.4,.5,1),opacity .3s}
.welcome.on{transform:none;opacity:1}
.welcome .wbadge{flex:none;width:96px;height:96px;filter:drop-shadow(3px 4px 0 rgba(0,0,0,.3))}
.welcome .wbub{position:relative;margin-bottom:34px;padding:16px 18px 14px;background:#FBB401;color:#101316;border:3px solid #101316;box-shadow:5px 5px 0 #101316}
.welcome .wbub::before{content:"";position:absolute;left:-15px;bottom:14px;border:12px solid transparent;border-right-color:#101316;border-left:0}
.welcome .wbub::after{content:"";position:absolute;left:-9px;bottom:16px;border:10px solid transparent;border-right-color:#FBB401;border-left:0}
.welcome p{margin:0 18px 0 0;font-size:14.5px;line-height:1.5}.welcome p b{font:800 19px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;display:block;margin-bottom:4px}
.welcome .wx{position:absolute;right:6px;top:4px;width:28px;height:28px;font:700 20px/1 "Public Sans",sans-serif;background:none;border:0;color:#101316;cursor:pointer}
.welcome .wact{display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px;margin-top:12px}
.welcome .wgo{font:700 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.06em;text-transform:uppercase;padding:9px 12px;background:#101316;color:#FBB401;border:2px solid #101316;cursor:pointer}
.welcome .wact a{font:700 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.06em;text-transform:uppercase;color:#101316}
@media (max-width:560px){.welcome{left:10px;right:10px;bottom:10px;max-width:none}.welcome .wbadge{width:64px;height:64px}.welcome .wbub{margin-bottom:22px}}
@media (prefers-reduced-motion:reduce){.welcome{transition:none}}
/* the title block names who drew the plans */
.tblock .drawn{grid-column:1/-1;display:flex;align-items:center;gap:10px;padding:10px 12px;border-top:2px solid var(--ink);text-decoration:none;color:var(--ink);background:var(--panel);transition:background .15s}
.tblock .drawn img{flex:none;width:34px;height:34px}
.tblock .drawn span{display:flex;flex-direction:column;gap:3px;min-width:0}
.tblock .drawn small{font:600 9px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.tblock .drawn b{font:800 15px/1 "Big Shoulders Display","Arial Narrow",sans-serif;letter-spacing:.03em;text-transform:uppercase;color:var(--ink)}
.tblock .drawn em{margin-left:auto;flex:none;font:700 9.5px/1 "Martian Mono",ui-monospace,monospace;font-style:normal;letter-spacing:.06em;text-transform:uppercase;padding:6px 7px;background:#FBB401;color:#101316;border:1.5px solid #101316}
.tblock .drawn:hover,.tblock .drawn:focus-visible{background:var(--panel-2)}.tblock .drawn:hover em{background:#101316;color:#FBB401}
/* moving between pages: a short cross-fade of the main area; the site plan and the phone bar hold still */
@view-transition{navigation:auto}
nav.plan{view-transition-name:siteplan}.mbar{view-transition-name:mbar}
::view-transition-old(root),::view-transition-new(root){animation-duration:.18s}
@media (prefers-reduced-motion:reduce){@view-transition{navigation:none}}
/* scrollbars in the site's colours: an ink thumb on the page's own ground, hi-vis yellow under the pointer; panels scroll thin */
html{scrollbar-color:var(--ink-3) var(--ground)}
.side,.reader,.mems,.stage,#stage,.byhand,pre{scrollbar-width:thin}
::-webkit-scrollbar{width:12px;height:12px}
::-webkit-scrollbar-track{background:var(--ground)}
::-webkit-scrollbar-thumb{background:var(--ink-3);border:3px solid var(--ground);border-radius:0}
::-webkit-scrollbar-thumb:hover{background:#FBB401;border-color:var(--ground)}
::-webkit-scrollbar-corner{background:var(--ground)}
/* the site hoist: a cage rides the mast beside the section list to the level you are on */
.subs.hoisted{position:relative}
.hmast{position:absolute;left:17px;top:2px;bottom:6px;width:10px;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='12'%3E%3Cpath d='M1 0v12M9 0v12' stroke='%238A9096' stroke-width='1.6'/%3E%3Cpath d='M1 0L9 6L1 12' fill='none' stroke='%238A9096' stroke-width='1'/%3E%3C/svg%3E") 0 0/10px 12px repeat-y;pointer-events:none}
.hmast::before{content:"";position:absolute;left:-3px;right:-3px;bottom:-4px;height:4px;background:#5B6368}
.hcage,.hcw{position:absolute;top:0;pointer-events:none;will-change:transform}
.hcage{left:29px;width:16px;height:19px;transition:transform .8s cubic-bezier(.45,0,.25,1)}
.hcage svg{display:block;width:16px;height:19px;overflow:visible}
.hcw{left:7px;width:7px;height:15px;background:linear-gradient(#5B6368,#5B6368) 0 0/100% 100%;border:1px solid #101316;transition:transform .8s cubic-bezier(.45,0,.25,1)}
.hcw::after{content:"";position:absolute;left:0;right:0;top:5px;height:4px;background:repeating-linear-gradient(-45deg,#FBB401 0 2px,#101316 2px 4px)}
.hcage .lamp{fill:#7A5A00}
.hcage.moving .lamp{animation:h-lamp .32s steps(2) infinite}
@keyframes h-lamp{0%{fill:#FFB400}100%{fill:#7A5A00}}
.subs.hoisted a.here{color:var(--ink);font-weight:700}
@media (prefers-reduced-motion:reduce){.hcage,.hcw{transition:none}.hcage.moving .lamp{animation:none}}
@media print{.hmast,.hcage,.hcw{display:none}}
:root{color-scheme:light;
 --ground:#ECEEEA;--panel:#F8F9F6;--panel-2:#E2E6E0;--line:#C9CFC7;--line-2:#DADFD8;
 --ink:#15181A;--ink-2:#454C50;--ink-3:#646C70;--hivis:#FBB401;--brand:#946400;
 --plan:#1D4E89;--run:#3B6D2F;--inspect:#8A3B8F;--close:#A5650F;--kit:#6A7378;--focus:#1D4E89;
 --code-bg:#101316;--code-ink:#E7EAE5}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
 --ground:#101316;--panel:#171B1E;--panel-2:#1F2427;--line:#2C3337;--line-2:#23292C;
 --ink:#E7EAE5;--ink-2:#B4BBB6;--ink-3:#8A938D;--brand:#FBB401;
 --plan:#80AFE9;--run:#8FCB7C;--inspect:#D79DDB;--close:#F0B04A;--kit:#9AA4A8;--focus:#80AFE9;
 --code-bg:#0A0C0E;--code-ink:#E7EAE5}}
:root[data-theme="dark"]{color-scheme:dark;
 --ground:#101316;--panel:#171B1E;--panel-2:#1F2427;--line:#2C3337;--line-2:#23292C;
 --ink:#E7EAE5;--ink-2:#B4BBB6;--ink-3:#8A938D;--brand:#FBB401;
 --plan:#80AFE9;--run:#8FCB7C;--inspect:#D79DDB;--close:#F0B04A;--kit:#9AA4A8;--focus:#80AFE9;
 --code-bg:#0A0C0E;--code-ink:#E7EAE5}
.f-plan{--c:var(--plan)}.f-run{--c:var(--run)}.f-inspect{--c:var(--inspect)}.f-close{--c:var(--close)}.f-kit{--c:var(--kit)}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-padding-top:16px}
body{margin:0;background:var(--ground);color:var(--ink);font:400 15.5px/1.55 "Public Sans",system-ui,-apple-system,"Segoe UI",sans-serif;overflow-x:hidden}
a{color:inherit}
:focus-visible{outline:2px solid var(--focus);outline-offset:2px}
code{font:500 .86em "Martian Mono",ui-monospace,monospace;background:var(--panel-2);padding:1px 5px;overflow-wrap:anywhere}
.mark{height:30px;width:auto;flex:none;display:block}
.haz{height:10px;background:repeating-linear-gradient(-45deg,var(--hivis) 0 10px,#101316 10px 20px)}
.kick{font:500 11.5px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--brand)}
.btn{display:inline-flex;align-items:center;gap:8px;font:700 14px/1 "Public Sans",system-ui,sans-serif;text-decoration:none;padding:13px 18px;border:2px solid var(--ink);color:var(--ink);background:transparent;cursor:pointer}
.btn.main{background:var(--hivis);border-color:#101316;color:#101316}
.btn:hover{background:var(--panel-2)}
.btn.main:hover{background:#FFC633}
.notice{background:#FBB401;border:2px solid #101316;display:flex;color:#101316}
.notice>b{flex:none;display:flex;align-items:flex-start;background:#101316;color:#FBB401;font:600 10.5px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;padding:11px 10px}
.notice>div{padding:9px 13px;font:600 14px/1.5 "Public Sans",system-ui,sans-serif;color:#101316;min-width:0}
.notice p{margin:0}
.notice ul{margin:0;padding-left:18px}
.notice li+li{margin-top:4px}
.notice code{background:rgba(16,19,22,.12);color:#101316}
.plate{display:inline-flex;align-items:stretch;background:#101316;border:1px solid #101316;max-width:100%}
.plate code{font:600 13px "Martian Mono",ui-monospace,monospace;color:#FBB401;padding:6px 10px;background:none}
.cmdline{display:flex;align-items:stretch;background:var(--code-bg);border:1px solid #101316;max-width:640px}
.cmdline code{flex:1;min-width:0;overflow-x:auto;white-space:nowrap;background:none;color:var(--code-ink);font:500 13.5px/1 "Martian Mono",ui-monospace,monospace;padding:15px 16px}
pre.cmd{margin:0;background:var(--code-bg);color:var(--code-ink);border:1px solid #101316;padding:16px;overflow-x:auto;font:500 12.5px/1.6 "Martian Mono",ui-monospace,monospace}
pre.cmd code{background:none;padding:0;font:inherit;color:inherit;overflow-wrap:normal}
.cmdbox{position:relative}
/* the shell: the site plan (a drawing index, one sheet per page) beside the page */
.site{display:grid;grid-template-columns:268px minmax(0,1fr);min-height:100vh;background:linear-gradient(90deg,var(--panel) 0 267px,var(--line) 267px 268px,transparent 268px)}
.plan{position:sticky;top:0;height:100vh;height:100dvh;overflow:auto;background:var(--panel);border-right:1px solid var(--line);display:flex;flex-direction:column}
.plan .ph{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:16px 18px 14px}
.brand{display:flex;align-items:center;gap:10px;text-decoration:none}
/* the words stand on the beam: the mark's flag rises above them */
.brand{align-items:flex-end}.brand .wm{padding-bottom:0;margin-bottom:-1px}
.brand .mark{height:42px;width:auto}
.mbar .brand .mark{height:34px;width:auto}
.brand .wm{display:inline-flex;flex-direction:row;align-items:baseline;line-height:1;white-space:nowrap}
.brand .wm b+b{margin-left:.24em;color:var(--brand)}
.brand b{font:800 26px/1 "Big Shoulders Display","Arial Narrow",Impact,sans-serif;letter-spacing:.04em;text-transform:uppercase}
.plan .haz{height:6px}
.plan .pl{padding:16px 18px 6px;font:600 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3)}
.plan ol{list-style:none;margin:0;padding:0 0 12px}
.sheet{display:grid;grid-template-columns:34px minmax(0,1fr);align-items:baseline;padding:9px 18px 9px 14px;text-decoration:none;border-left:4px solid transparent}
.sheet b{font:800 19px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;color:var(--ink-3);font-variant-numeric:tabular-nums}
.sheet span{font:600 14.5px/1.3 "Public Sans",system-ui,sans-serif}
.sheet:hover span{text-decoration:underline;text-underline-offset:3px}
.sheet[aria-current]{background:var(--ground);border-left-color:var(--hivis)}
.sheet[aria-current] b{color:var(--brand)}
.subs{list-style:none;margin:0;padding:2px 0 8px;background:var(--ground);border-left:4px solid var(--hivis)}
.subs a{display:block;padding:5px 14px 5px 48px;font:500 11.5px/1.35 "Martian Mono",ui-monospace,monospace;color:var(--ink-2);text-decoration:none}
.subs a:hover{color:var(--ink);text-decoration:underline;text-underline-offset:3px}
.tblock{margin-top:auto;border-top:2px solid var(--ink);display:grid;grid-template-columns:1fr auto;font:600 10px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-2)}
.tblock>*{padding:9px 12px;border-bottom:1px solid var(--line)}
.tblock>:nth-child(odd){border-right:1px solid var(--line)}
.tblock b{display:block;color:var(--ink);font-size:12px;letter-spacing:.06em}
.tblock .tt>span{padding-bottom:0;margin-bottom:-2px}
.tblock .tt .mark{height:22px;width:auto;flex:none}
.tblock .tt span b{display:inline;margin:0;font:inherit;color:inherit;letter-spacing:inherit}.tblock .tt span b.out{color:var(--brand)}
.tblock .tt{display:flex;align-items:flex-end;gap:8px;grid-column:1/-1;border-right:0;font:800 18px/1 "Big Shoulders Display","Arial Narrow",sans-serif;letter-spacing:.06em;color:var(--ink)}
.theme-toggle{font:600 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;padding:7px 10px;border:1px solid var(--line);border-radius:0;background:var(--ground);color:var(--ink);cursor:pointer}
.theme-toggle:hover{border-color:var(--ink)}
.mbar{display:none}
.planx{display:none}
.mainc{min-width:0}
footer.site-foot{border-top:1px solid var(--line);margin-top:64px;padding:18px 32px;display:flex;flex-wrap:wrap;gap:8px 24px;justify-content:space-between;font:500 11.5px/1.4 "Martian Mono",ui-monospace,monospace;color:var(--ink-3)}
@media (max-width:900px){
 .site{display:block;background:none}
 .mbar{display:flex;position:sticky;top:0;z-index:40;align-items:center;gap:10px;padding:10px 16px;background:var(--panel);border-bottom:1px solid var(--line);min-height:54px}
 .mbar .brand b{font-size:22px}
 .mbar .where{font:600 10.5px/1.2 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-2);min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
 .mbar button{margin-left:auto;flex:none;font:600 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;padding:9px 11px;border:2px solid #101316;background:var(--hivis);color:#101316;cursor:pointer}
 .plan{display:none;position:fixed;inset:0;z-index:60;width:100%;height:100dvh;border-right:0}
 .site.open .plan{display:flex}
 .planx{display:block;font:600 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;padding:9px 11px;border:2px solid var(--ink);background:var(--ground);color:var(--ink);cursor:pointer}
 footer.site-foot{padding:18px 16px}
}
@media (max-width:640px){.notice{flex-direction:column}.notice>b{padding:6px 10px}}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}

/* tested on, and what's coming */
.rno.rtest{background:var(--panel)}.rno.rtest h3{color:var(--ink)}.rno.rtest h3::before{display:none}
.rq .rno.rtest{background:var(--panel)}.rq .rno.rtest h3,:root[data-theme="dark"] .rno.rtest h3,:root[data-theme="dark"] .rq .rno.rtest h3{color:var(--ink)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .rno.rtest h3,:root:not([data-theme="light"]) .rq .rno.rtest h3{color:var(--ink)}}
.closer .cmdline code{line-height:1.5}
.rcloud{display:flex;align-items:center;gap:10px;margin-top:12px!important;padding-top:12px;border-top:2px dashed var(--line);font-weight:600}
.rcloud b{flex:none;padding:5px 8px;font:700 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;background:#FBB401;color:#101316;border:2px solid #101316}
.access .then2{margin:8px 0 0;font-size:13px;line-height:1.45;color:var(--ink-2)}
/* the Deep Agents add-on */
.addon{margin-top:22px;border:3px solid var(--ink);background:var(--panel);box-shadow:5px 5px 0 var(--ink)}
.addon .adh{padding:16px 18px 12px;border-bottom:2px solid var(--ink)}
.addon .adt{display:inline-block;margin-bottom:8px;padding:4px 7px;font:700 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;background:var(--ink);color:var(--ground)}
.addon h3{margin:0 0 6px;font:800 24px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.addon .adh p{margin:0;font-size:14.5px;line-height:1.5;max-width:68ch}
.addon .adparts{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}
.addon .adparts li{display:flex;flex-direction:column;gap:6px;padding:12px 16px;border-right:1px solid var(--line);border-bottom:1px solid var(--line)}
.addon .adparts code{align-self:flex-start;font:700 12.5px/1.2 "Martian Mono",ui-monospace,monospace;padding:4px 7px;background:#FBB401;color:#101316;border:2px solid #101316}
.addon .adparts span{font-size:13.5px;line-height:1.45;color:var(--ink-2)}
.addon .adneed{margin:0;padding:10px 18px;font:600 11.5px/1.5 "Martian Mono",ui-monospace,monospace;color:var(--ink-3)}
/* enforced, or only instructed: each promise, what keeps it, and what it doesn't stop */
.enf{margin-top:26px}
.enf h3{margin:0 0 6px;font:800 24px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.enf h3 small{margin-left:8px;font:600 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.08em;text-transform:none;color:var(--ink-3)}
.enf>p{margin:0 0 12px;color:var(--ink-2);font-size:14.5px}
.enf ul{list-style:none;margin:0;padding:0;border:2px solid var(--ink)}
.enf li{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px 14px;align-items:center;padding:11px 14px;border-bottom:1px solid var(--line);background:var(--panel)}
.enf li:last-child{border-bottom:0}
.enf li>b{font-weight:600;font-size:14.5px;line-height:1.4}
.enf .eby{justify-self:end;padding:5px 8px;font:700 10.5px/1.2 "Martian Mono",ui-monospace,monospace;letter-spacing:.04em;border:2px solid #101316;text-align:right}
.enf li.chk .eby{background:#1E7B4A;color:#F4F4EF}
.enf li.ins .eby{background:repeating-linear-gradient(-45deg,#FBB401 0 6px,#F4D47A 6px 12px);color:#101316}
.enf details{grid-column:1/-1}
.enf summary{cursor:pointer;font:600 11px/1.4 "Martian Mono",ui-monospace,monospace;letter-spacing:.04em;color:var(--ink-3)}
.enf details p{margin:6px 0 0;font-size:13.5px;line-height:1.5;color:var(--ink-2)}
.enf details p.egap{padding-left:10px;border-left:3px solid #C42B1C}
@media (max-width:560px){.enf li{grid-template-columns:1fr}.enf .eby{justify-self:start;text-align:left}}

/* the add-on's kit: needs, installed for you, optional; LangChain's logos, light or dark file by theme, with clear space */
.addon .adkit{display:grid;grid-template-columns:minmax(0,.8fr) minmax(0,1.6fr) minmax(0,1fr);border-bottom:2px solid var(--ink)}
.addon .adc{padding:14px 16px 16px;border-right:1px solid var(--line)}.addon .adc:last-child{border-right:0}
.addon .adc h4{margin:0 0 10px;font:700 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3)}
.addon .adc h4 small{margin-left:6px;padding:3px 5px;font-size:9px;letter-spacing:.08em;background:#FBB401;color:#101316}
.addon .adc ul{list-style:none;margin:0;padding:0;display:grid;gap:10px}
.addon .adc li{display:grid;gap:4px}.addon .adc li>span,.addon .adpy span{font-size:13px;line-height:1.45;color:var(--ink-2)}
.addon .lcl{display:block;padding:12px 0 8px}.addon .lcl img{display:block;height:22px;width:auto;max-width:100%}
.addon .lcl .dk{display:none}
:root[data-theme="dark"] .addon .lcl .lt{display:none}:root[data-theme="dark"] .addon .lcl .dk{display:block}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .addon .lcl .lt{display:none}:root:not([data-theme="light"]) .addon .lcl .dk{display:block}}
.addon .adpy{display:grid;grid-template-columns:auto minmax(0,1fr);gap:2px 10px;align-items:center}
.addon .adpy .lg{grid-row:1/span 2;width:40px;height:40px;display:grid;place-items:center;border:2px solid var(--ink);background:#fff}.addon .adpy .lg svg{width:24px;height:24px}
.addon .adpy b{font:800 18px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
@media (max-width:820px){.addon .adkit{grid-template-columns:1fr}.addon .adc{border-right:0;border-bottom:1px solid var(--line)}.addon .adc:last-child{border-bottom:0}}

/* watch one job: five stations, your lane and its lane, and the building it tops out; complete at rest */
.oj{padding:20px 28px 18px;border-bottom:3px solid var(--ink)}
.ojk{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 12px;margin-bottom:14px}
.ojk b{font:700 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;background:#101316;color:#FBB401;padding:7px 9px}
.ojk span{font-size:14px;color:var(--ink-2)}
.ojg{position:relative;display:grid;grid-template-columns:44px repeat(5,minmax(0,1fr)) 190px;grid-template-rows:auto auto auto;column-gap:8px}
.ojlab,.ojst{display:grid;grid-template-rows:subgrid;grid-row:1/span 3}
.ojlab span{display:flex;align-items:center;justify-content:center;writing-mode:vertical-rl;transform:rotate(180deg);font:700 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.16em;text-transform:uppercase}
.ojlab .y{background:#FBB401;color:#101316;border:2px solid #101316;margin-top:8px}.ojlab .i{background:var(--ink);color:var(--ground);margin-top:6px}
.ojhd{position:relative;display:grid;grid-template-columns:auto 1fr;grid-template-rows:auto auto;align-items:center;gap:4px 8px;padding:10px 10px 8px;border:2px solid var(--ink);background:var(--ground);transition:background .25s,box-shadow .25s,transform .25s}
.ojhd .ri{width:30px;height:30px;color:var(--ink)}.ojhd b{font:800 17px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.ojn{position:absolute;top:-9px;left:-9px;display:grid;place-items:center;width:20px;height:20px;background:#FBB401;color:#101316;border:2px solid #101316;font:700 10.5px/1 "Martian Mono",ui-monospace,monospace}
.ojv{grid-column:1/-1;width:64px;height:40px;color:var(--ink);justify-self:start}
.ojy,.oji{margin:0;padding:9px 10px;font-size:12.5px;line-height:1.4}
.ojy{margin-top:8px;background:rgba(251,180,1,.22);border-left:4px solid #FBB401}
.oji{margin-top:6px;background:var(--ground);border-left:4px solid var(--ink);color:var(--ink-2)}
.ojy q,.oji q{font:600 .92em "Martian Mono",ui-monospace,monospace;quotes:"\201C" "\201D"}
.ojt{fill:#3FAE6A}
.ojst[data-s="3"] .ojhd{border-bottom-width:0;padding-bottom:16px;background-image:repeating-linear-gradient(-45deg,#101316 0 6px,#FBB401 6px 12px);background-size:100% 8px;background-repeat:no-repeat;background-position:bottom}
.ojst[data-s="3"] .ojhd .ri [fill="#101316"]{fill:currentColor}.ojst[data-s="3"] .ojhd .ri [stroke="#101316"]{stroke:currentColor}
.ojgoal [stroke="#101316"]{stroke:currentColor}.ojgoal text{fill:currentColor}
.ojb{grid-row:1/span 3;align-self:stretch;display:flex;flex-direction:column;justify-content:flex-end;color:var(--ink)}
.ojb svg{width:100%;max-width:180px;height:auto;align-self:center}
.ojcap{margin:4px 0 0;text-align:center}.ojcap b{display:block;font:800 22px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;color:#E0442F}
.ojcap span{display:block;margin-top:4px;font-size:12px;line-height:1.35;color:var(--ink-2)}
:root[data-theme="dark"] .ojcap b{color:#FF7A66}@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .ojcap b{color:#FF7A66}}
.ojnote{margin:12px 0 0;align-self:start;font-size:13px;color:var(--ink-3)}.ojnote code{font:600 .92em "Martian Mono",ui-monospace,monospace}
/* playing: stations wait, the ticket moves, floors rise, the beam goes on last */
.ojtk{position:absolute;left:0;top:0;z-index:2;padding:5px 7px;font:700 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.06em;text-transform:uppercase;background:#FBB401;color:#101316;border:2px solid #101316;box-shadow:3px 3px 0 #101316;opacity:0;transition:transform .55s cubic-bezier(.5,0,.3,1),opacity .3s;pointer-events:none}
.ojtk.on{opacity:1}
.oj.play .ojst .ojw{stroke-dasharray:20;stroke-dashoffset:20;transition:stroke-dashoffset .6s}.oj.play .ojst.hit .ojw{stroke-dashoffset:0}
.oj.play .ojst .ojt{fill:var(--ground);transition:fill .2s calc(var(--d)*.22s)}.oj.play .ojst.hit .ojt{fill:#3FAE6A}
.oj.play .ojst .ojs2,.oj.play .ojst .ojq,.oj.play .ojst .ojm{transform-box:fill-box;transform-origin:center;transform:scale(.4);opacity:.15;transition:transform .3s cubic-bezier(.3,1.6,.5,1),opacity .2s}
.oj.play .ojst.hit .ojs2{transform:rotate(-8deg);opacity:1}.oj.play .ojst.hit .ojq,.oj.play .ojst.hit .ojm{transform:none;opacity:1}
.oj.play .ojst.now .ojhd{background:#FBB401;color:#101316;box-shadow:4px 4px 0 var(--ink);transform:translate(-2px,-2px)}
.oj.play .ojst.now .ojhd .ojv,.oj.play .ojst.now .ojhd .ri{color:#101316}
.oj.play .ojf{opacity:.3;transition:opacity .4s}.oj.play .ojf.on{opacity:1}
.oj.play .ojtop{transform:translateY(-26px);opacity:0;transition:transform .7s cubic-bezier(.3,1.3,.5,1),opacity .3s}.oj.play.topped .ojtop{transform:none;opacity:1}
.oj.play .ojcap b{opacity:.6;transition:opacity .3s}.oj.play.topped .ojcap b{opacity:1}
@media (min-width:901px) and (max-width:1240px){.ojhd{padding:10px 8px 8px;column-gap:6px}.ojhd b{font-size:15px}}
@media (max-width:900px){.ojg{grid-template-columns:repeat(5,minmax(0,1fr))}.ojlab{display:none}.ojb{grid-column:1/-1;grid-row:auto;flex-direction:row;align-items:center;justify-content:flex-start;gap:14px;margin-top:12px}.ojb svg{width:90px;flex:none}.ojcap{text-align:left}}
@media (max-width:640px){.oj{padding:18px 16px}.ojg{display:flex;flex-direction:column;gap:14px}.ojst{display:block}.ojtk{display:none}
 .ojhd{grid-template-columns:auto auto 1fr}.ojv{grid-column:auto;justify-self:end;height:32px}
 .ojy::before,.oji::before{grid-row:1;grid-column:1;align-self:start;display:inline-block;margin-right:7px;font:700 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;padding:3px 5px;vertical-align:1px}
 .ojy::before{content:"You";background:#FBB401;color:#101316}.oji::before{content:"It";background:var(--ink);color:var(--ground)}}

/* the mode switch: with you, an autonomous run, a night shift; plain radios, so it works without script */
/* three ways to run a job: equal, always visible; every mode's text sits in the same cell, so nothing changes size */
.ojways{display:grid;grid-template-columns:auto minmax(0,1fr);align-items:center;gap:8px 14px;margin:0 0 30px}
.ojwl{font:800 19px/1.05 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.ojmode{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border:2px solid var(--ink)}
.ojmode input{position:absolute;opacity:0;width:1px;height:1px}
.ojmode label{display:flex;flex-direction:column;gap:4px;padding:9px 12px;cursor:pointer;color:var(--ink-2);background:var(--ground)}
.ojmode label b{font:700 11px/1.1 "Martian Mono",ui-monospace,monospace;letter-spacing:.06em;text-transform:uppercase;color:var(--ink)}
.ojmode label small{font-size:12px;line-height:1.35}
.ojmode label+input+label{border-left:2px solid var(--ink)}
.ojmode label:hover{background:var(--panel)}
.ojmode input:checked+label,.ojmode input:checked+label b{background:#FBB401;color:#101316}
.ojmode input:focus-visible+label{outline:3px solid var(--focus);outline-offset:2px}
.ojy,.oji,.ojhd>b,.ojfoot{display:grid;grid-template-columns:auto minmax(0,1fr)}
.ojy>.mv,.oji>.mv,.ojhd>b>.mv{grid-row:1;grid-column:2}
.ojfoot>*{grid-row:1;grid-column:1/-1}
.oj .mv:not(.m-you),.oj .mvb:not(.m-you){visibility:hidden}
.oj:has(#ojm-auto:checked) .m-you,.oj:has(#ojm-night:checked) .m-you{visibility:hidden}
.oj:has(#ojm-auto:checked) .m-auto,.oj:has(#ojm-night:checked) .m-night{visibility:visible}
.oj .ojgoal{display:none}
.oj:has(#ojm-auto:checked) .ojgoal,.oj:has(#ojm-night:checked) .ojgoal{display:inline}
.oj:has(#ojm-auto:checked) .ojq:not(.ojgoal),.oj:has(#ojm-night:checked) .ojq:not(.ojgoal){display:none}
.ojy code{font:600 .9em "Martian Mono",ui-monospace,monospace;background:var(--ground);padding:1px 4px;overflow-wrap:anywhere}
.ojnil{color:var(--ink-3)}
.ojlim{margin-top:12px;padding:12px 14px;border:2px solid var(--ink);border-left:8px solid #E0442F;background:var(--ground)}
.ojlim p{margin:0;font-size:13px;line-height:1.5;color:var(--ink-2)}.ojlim p+p{margin-top:6px}.ojlim b{color:var(--ink)}
.ojlim.ojyou{border-left-color:#FBB401}.ojlim q{font:600 .92em "Martian Mono",ui-monospace,monospace;quotes:"\201C" "\201D"}
.ojlim a{font:700 11px/1 "Martian Mono",ui-monospace,monospace;color:var(--ink);white-space:nowrap}
@media (max-width:640px){.ojways{grid-template-columns:1fr}.ojmode label{padding:8px 7px}.ojmode label b{font-size:9.5px}.ojmode label small{font-size:11px}}

.board .toinst{display:inline-block;margin-top:14px;padding:7px 10px;font:700 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--ink);border:2px solid var(--ink);text-decoration:none}
.board .toinst:hover{background:#FBB401;color:#101316;border-color:#101316}
#install{scroll-margin-top:16px}

/* after the last job: the report and its next heads, your pick, a new board; complete at rest */
.ojnext{grid-column:1/-1;grid-row:4;display:grid;grid-template-columns:44px repeat(3,minmax(0,1fr));gap:8px 20px;margin-top:10px}
.ojnl{display:flex;align-items:center;justify-content:center;writing-mode:vertical-rl;transform:rotate(180deg);font:700 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.16em;text-transform:uppercase;border:2px solid var(--ink);color:var(--ink)}
.ojb2{position:relative;padding:11px 12px 12px;border:2px solid var(--ink);background:var(--ground);transition:background .25s,box-shadow .25s,transform .25s}
.ojb2+.ojb2::before{content:"\2192";position:absolute;left:-17px;top:50%;transform:translateY(-50%);font:700 13px/1 "Martian Mono",ui-monospace,monospace;color:var(--ink)}
.ojb2>b{display:block;margin:6px 0 4px;font:800 17px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.ojb2 p{margin:0;font-size:12.5px;line-height:1.4;color:var(--ink-2)}.ojb2 em{font-style:normal;font-weight:700;color:var(--ink)}
.ojtag{display:inline-block;padding:3px 5px;font:700 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase}
.ojtag.y{background:#FBB401;color:#101316}.ojtag.i{background:var(--ink);color:var(--ground)}
.ojpick{background:rgba(251,180,1,.22);border-left:6px solid #FBB401}
.ojheads{list-style:none;display:flex;flex-wrap:wrap;gap:6px;margin:9px 0 0;padding:0}
.ojheads li{padding:4px 7px;font:700 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.04em;border:2px solid var(--ink);background:var(--panel);color:var(--ink)}
.ojheads li.pick{background:#FBB401;color:#101316;border-color:#101316;box-shadow:2px 2px 0 var(--ink)}
.ojnew svg{display:block;width:160px;height:34px;margin:2px 0 6px;color:var(--ink)}
.ojfz{transform-box:fill-box}
.oj.play .ojfz{opacity:0;transition:opacity .3s}.oj.play.topped .ojfz{opacity:1}
.oj.play .ojb2{opacity:.45}.oj.play .ojb2.hit{opacity:1}
.oj.play .ojb2.now{box-shadow:4px 4px 0 var(--ink);transform:translate(-2px,-2px)}
.oj.play .ojheads li{opacity:.25;transition:opacity .3s calc(var(--h)*.25s)}.oj.play .ojrep.hit .ojheads li{opacity:1}
.oj.play .ojheads li.pick{background:var(--panel);color:var(--ink);border-color:var(--ink);box-shadow:none;transition:opacity .3s,background .2s,box-shadow .2s}
.oj.play .ojpick.hit~* .ojheads li.pick,.oj.play .ojnext:has(.ojpick.hit) .ojheads li.pick{background:#FBB401;color:#101316;border-color:#101316;box-shadow:2px 2px 0 var(--ink)}
.oj.play .ojplot{stroke-dashoffset:40;transition:stroke-dashoffset .8s}.oj.play .ojnew.hit .ojplot{stroke-dashoffset:0}
@media (max-width:900px){.ojnext{grid-row:auto;grid-template-columns:repeat(3,minmax(0,1fr))}.ojnl{display:none}}
@media (max-width:640px){.ojnext{display:flex;flex-direction:column;gap:14px}.ojb2+.ojb2::before{content:"\2193";left:50%;top:-14px;transform:translateX(-50%)}}

/* D24: "It's working if" is something to learn from, not to tick: plain lines, each with a small static check mark */
.kchk li::before,.dkt .kins ul.kchk li::before,.reader .body .kchk li::before{content:"\2713";width:auto;height:auto;border:0;margin:0;background:none;font:800 13px/1.5 "Public Sans",sans-serif;color:#1E7B4A}
:root[data-theme="dark"] .kins ul.kchk li::before{color:#5FC98A}@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .kins ul.kchk li::before{color:#5FC98A}}
"""

FRAME_CSS = r"""
html,body{height:100%}
body{overflow:hidden}
.mainc{display:flex;flex-direction:column;height:100vh;height:100dvh}
.frame{flex:1;width:100%;min-height:0;border:0;display:block;background:var(--ground)}
.tabs{display:flex;flex-wrap:wrap;gap:0;border-bottom:2px solid var(--ink);background:var(--panel)}
.tabs button{font:800 18px/1 "Big Shoulders Display","Arial Narrow",sans-serif;letter-spacing:.04em;text-transform:uppercase;padding:14px 20px 12px;border:0;border-right:1px solid var(--line);background:transparent;color:var(--ink-2);cursor:pointer}
.tabs button[aria-selected="true"]{background:var(--hivis);color:#101316}
.tabs button:hover{color:var(--ink)}
.tabs button[aria-selected="true"]:hover{color:#101316}
@media (max-width:900px){
 .mainc{height:calc(100dvh - 54px)}
 .tabs button{flex:1;font-size:16px;padding:12px 10px 10px}
}
"""

FRONT_CSS = r"""
.wrap{max-width:1080px;margin:0 auto;padding:0 32px}
/* the site board: the sign at a building site's gate, saying who runs the site */
.board{margin-top:32px;border:3px solid var(--ink);background:var(--panel)}
.board>.haz{height:14px}
.board .bh{display:grid;grid-template-columns:auto minmax(0,1fr) minmax(240px,360px);gap:20px;align-items:center;padding:26px 28px 24px;border-bottom:3px solid var(--ink)}
.board .bh .mark{height:64px;width:auto;align-self:start}
.board h1{margin:10px 0 0;font:800 clamp(36px,4.2vw,62px)/.9 "Big Shoulders Display","Arial Narrow",Impact,sans-serif;text-transform:uppercase;letter-spacing:.005em}
.board h1 span{display:block}
.board h1 span+span{color:var(--brand)}
.jhw{align-self:center;display:flex;flex-direction:column;margin:-14px -16px 0 0;padding-bottom:6px}
.jh{flex:none;height:280px;position:relative;align-self:center;width:100%}
.jhc{margin:6px auto 0;max-width:40ch;text-align:center;font:500 12px/1.45 "Public Sans",system-ui,sans-serif;color:var(--ink-3)}
.jhc span{font-weight:700}
.jhc .f,.board .sub .f{color:#B3261E;font-weight:700}.jhc .p,.board .sub .p{color:#2F6B3A;font-weight:700}
:root[data-theme="dark"] .jhc .f,:root[data-theme="dark"] .board .sub .f{color:#F2847A}:root[data-theme="dark"] .jhc .p,:root[data-theme="dark"] .board .sub .p{color:#8FCB7C}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .jhc .f,:root:not([data-theme="light"]) .board .sub .f{color:#F2847A}:root:not([data-theme="light"]) .jhc .p,:root:not([data-theme="light"]) .board .sub .p{color:#8FCB7C}}
.jh canvas{display:block;position:absolute;inset:0;width:100%!important;height:100%!important}
.jh{border:3px solid var(--ink);background:#0E1A2E;overflow:hidden}
/* under the hero scene: the clock, what is happening now, and where the night has got to */
.jcap{display:grid;grid-template-columns:auto minmax(0,1fr);gap:7px 10px;align-items:center;margin-top:9px}
.jcap .clk{font:700 13px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.06em;background:#101316;color:#FBB401;padding:6px 7px 5px;font-variant-numeric:tabular-nums}
.jcap .cap{font:500 12.5px/1.35 "Public Sans",system-ui,sans-serif;color:var(--ink-2);min-height:2.7em;display:flex;align-items:center}
.jcap .cap b{font:800 15px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;color:var(--ink);margin-right:7px;white-space:nowrap}
.jcap .cap span{display:block}
.jcap .pips{grid-column:1/-1;display:flex;gap:4px}.jcap .pips i{flex:1;height:4px;background:var(--line)}.jcap .pips i.on{background:var(--hivis)}
.board .sub{margin:16px 0 0;max-width:44ch;font-size:16px;line-height:1.45;color:var(--ink-3)}
.board .bb{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr)}
/* D26: three plain points under the hero, one line each */
.edge{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border-bottom:3px solid var(--ink)}
.edge li{padding:16px 20px 18px;border-left:3px solid var(--ink)}
.edge li:first-child{border-left:0}
.edge b{display:block;margin-bottom:6px;padding-left:10px;border-left:4px solid var(--hivis);font:800 21px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;letter-spacing:.02em;color:var(--ink)}
.edge span{display:block;font-size:15px;line-height:1.45;color:var(--ink-2)}
@media (max-width:720px){.edge{grid-template-columns:1fr}.edge li{border-left:0;border-top:3px solid var(--ink);padding:14px 16px 15px}.edge li:first-child{border-top:0}}
.roster{margin:0;padding:0;display:flex;flex-direction:column}
.roster>div{flex:1 1 auto}
.roster>div{display:grid;grid-template-columns:40px 132px minmax(0,1fr);gap:14px;padding:11px 28px;border-bottom:1px dashed var(--line);align-items:center}
.roster .ri{width:40px;height:40px;display:block}
.roster>div:last-child{border-bottom:0}
.roster dt{font:800 21px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;letter-spacing:.02em}
.roster dd{margin:0;font-size:14.5px;color:var(--ink-2)}
.roster .you{background:var(--hivis);color:#101316;border-bottom:0}
.roster .you dd{color:#101316}
.roster dd{font:500 12.5px/1.45 "Martian Mono",ui-monospace,monospace}
.access{border-left:3px solid var(--ink);padding:22px 26px 24px;display:flex;flex-direction:column;gap:10px}
.access .al{align-self:flex-start;background:#101316;color:#FBB401;font:600 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;padding:8px 10px}
.access p{margin:0;color:var(--ink-2);font-size:14.5px}
.access .then{margin-top:6px}
.access .cmdline code{white-space:normal;overflow-wrap:break-word;line-height:1.5;padding:12px 14px;font-size:12.5px}
.access .gh{margin-top:auto;position:relative;top:0;display:flex;align-items:center;gap:12px;padding:12px 14px;border:2px solid var(--ink);color:var(--ink);text-decoration:none}
.access .gh svg{width:26px;height:26px;flex:none}
.access .gh span{display:flex;flex-direction:column;gap:3px;min-width:0}
.access .gh b{font:600 13px/1.3 "Martian Mono",ui-monospace,monospace}
.access .gh small{font:500 11px/1.2 "Martian Mono",ui-monospace,monospace;color:var(--ink-3);letter-spacing:.02em}
.access .gh i{margin-left:auto;font-style:normal;font:600 16px/1 "Martian Mono",ui-monospace,monospace}
.access .gh:hover,.access .gh:focus-visible{border-color:var(--hivis);box-shadow:inset 4px 0 0 var(--hivis)}
.sec{padding-top:64px}
.sec-h{display:flex;align-items:baseline;gap:14px;border-bottom:1px solid var(--line);padding-bottom:10px;margin-bottom:12px}
.sec-h .n{flex:none;font:800 30px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;background:var(--hivis);color:#101316;padding:4px 7px 2px;font-variant-numeric:tabular-nums}
.sec-h h2{margin:0;font:800 clamp(30px,4.4vw,44px)/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;letter-spacing:.01em}
.sec .lede{max-width:70ch;color:var(--ink-2);margin:0 0 22px}
.more-row{margin-top:20px}
/* why Topping Out: four pillars */
/* the hoarding: plywood boards behind hazard tape; the signs are bolted on, each a little off true */
.hoard{overflow:hidden;border:3px solid var(--ink);background:var(--panel-2) repeating-linear-gradient(90deg,transparent 0 118px,var(--line) 118px 120px)}
.hoard>.haz{height:12px}
.pillars{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:22px;padding:28px 24px 30px}
.pil{position:relative;background:var(--panel);border:3px solid var(--ink);box-shadow:5px 6px 0 rgba(0,0,0,.18)}
.pil:nth-child(1){transform:rotate(-1.3deg)}.pil:nth-child(2){transform:rotate(.9deg) translateY(6px)}
.pil:nth-child(3){transform:rotate(-.6deg)}.pil:nth-child(4){transform:rotate(1.4deg) translateY(4px)}
.pil::before,.pil::after{content:"";position:absolute;top:7px;width:8px;height:8px;border-radius:50%;background:#8C949A;border:2px solid #101316;z-index:2}
.pil::before{left:7px}.pil::after{right:7px}
.pil .sgn{background:#F4F4EF;border-bottom:3px solid var(--ink)}
.pic{display:block;width:100%;height:auto;aspect-ratio:200/130}
.pil .cap{font:800 19px/1.05 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;letter-spacing:.03em;padding:9px 12px 8px;text-align:center}
.s-blue .cap{background:#1F5FA8;color:#fff}.s-yellow .cap{background:#FBB401;color:#101316}
.s-night .cap{background:#14233B;color:#FBB401}.s-green .cap{background:#1E7B4A;color:#fff}
.pil .pt{padding:14px 16px 18px}
.pic .tag{font:700 9px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em}
.pic *{transform-box:fill-box;transform-origin:center;animation-play-state:paused}
.hoard.live .pic *{animation-play-state:running}
.pic .brk{animation:brk 6s infinite both}
@keyframes brk{0%{opacity:0;transform:translateY(-18px)}9%{opacity:1;transform:none}80%{opacity:1;transform:none}90%,100%{opacity:0;transform:none}}
.pic .beam{animation:beam 5s infinite linear}
@keyframes beam{0%{transform:translateX(0);opacity:1}68%{transform:translateX(100px);opacity:1}72%,100%{transform:translateX(100px);opacity:0}}
.pic .bad{animation:bad 5s infinite}
@keyframes bad{0%,32%{fill:#101316;transform:none;opacity:1}36%,50%{fill:#C42B1C;transform:none;opacity:1}62%{fill:#C42B1C;transform:translate(26px,26px) rotate(40deg);opacity:0}63%,100%{opacity:0}}
.pic .fresh{opacity:0;animation:fresh 5s infinite}
@keyframes fresh{0%,62%{opacity:0;transform:translateY(-34px)}66%{opacity:1;transform:translateY(-34px)}76%{opacity:1;transform:none;fill:#1E9E57}90%{opacity:1;fill:#101316;transform:none}100%{opacity:0;transform:none}}
.pic .stamp{opacity:0;animation:stamp 5s infinite}
@keyframes stamp{0%,34%{opacity:0;transform:scale(1.6)}38%{opacity:1;transform:scale(1)}58%{opacity:1}64%,100%{opacity:0}}
.pic .sky{animation:sky 8s infinite ease-in-out;transform-box:view-box;transform-origin:100px 150px}
@keyframes sky{0%{transform:rotate(-58deg)}100%{transform:rotate(58deg)}}
.pic .star{animation:tw 2.6s infinite}
@keyframes tw{0%,100%{opacity:1}50%{opacity:.2}}
.pic .w1{animation:win1 8s infinite}.pic .w2{animation:win2 8s infinite}.pic .w3{animation:win3 8s infinite}
@keyframes win1{0%,14%{opacity:.12}18%,92%{opacity:1}100%{opacity:.12}}
@keyframes win2{0%,38%{opacity:.12}42%,92%{opacity:1}100%{opacity:.12}}
@keyframes win3{0%,62%{opacity:.12}66%,92%{opacity:1}100%{opacity:.12}}
.pic .j1{animation:jl1 8s infinite}.pic .j2{animation:jl2 8s infinite}.pic .j3{animation:jl3 8s infinite}
@keyframes jl1{0%,14%{fill:#4E627E}18%,92%{fill:#FBB401}100%{fill:#4E627E}}
@keyframes jl2{0%,38%{fill:#4E627E}42%,92%{fill:#FBB401}100%{fill:#4E627E}}
@keyframes jl3{0%,62%{fill:#4E627E}66%,92%{fill:#FBB401}100%{fill:#4E627E}}
.pic .flag{animation:flag 8s infinite;transform-origin:bottom center}
@keyframes flag{0%,72%{transform:scaleY(0);opacity:0}78%,92%{transform:scaleY(1);opacity:1}100%{transform:scaleY(1);opacity:0}}
.pic .pg{animation:page 4.5s infinite ease-in-out;transform-box:view-box;transform-origin:100px 67px}
@keyframes page{0%,30%{transform:scaleX(1)}55%,100%{transform:scaleX(-1)}}
.pic .cd{animation:card 4.5s infinite}
@keyframes card{0%,55%{transform:translate(40px,-20px);opacity:0}65%{opacity:1}80%,92%{transform:translate(-62px,42px);opacity:1}100%{transform:translate(-62px,42px);opacity:0}}
@media (prefers-reduced-motion:reduce){.pic *{animation:none!important}.pic .fresh,.pic .stamp,.pic .cd{opacity:0}}
.pil h3{margin:8px 0 10px;font:800 26px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.pil .pw{margin:0 0 8px;font-weight:600;font-size:15px}
.pil .ph{margin:0;color:var(--ink-2);font-size:14px}
/* the route's outer frame: the night shift, job after job */
.shiftbox{position:relative;margin-top:72px;border:2px dashed var(--ink-3);padding:30px 16px 14px}
.shiftbox .sl{position:absolute;top:-11px;right:14px;background:#101316;color:#FBB401;font:600 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;padding:5px 8px}
.shiftbox .feed{margin-top:0}
/* the night shift: a clock from day to morning */
.clock{list-style:none;margin:0 0 16px;padding:0;display:grid;grid-template-columns:repeat(6,minmax(0,1fr));border-top:3px solid var(--ink)}
.ck{position:relative;padding:18px 12px 14px 0;display:flex;flex-direction:column;gap:6px}
.ck::before{content:"";position:absolute;top:-9px;left:0;width:15px;height:15px;background:var(--hivis);border:2px solid #101316}
.ck.job::before{background:var(--ink);border-color:var(--ink)}
.ckw{font:600 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.ck b{font:800 21px/1.05 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.ck p{margin:0;font-size:13.5px;line-height:1.45;color:var(--ink-2)}
.ck .cmdline{margin-top:4px}
.ck .cmdline code{font-size:11.5px;padding:10px;white-space:normal;line-height:1.45}
.notice.rules{margin-top:6px}
/* the night shift as one strip: dusk on the left, the jobs through the night, the morning on the right */
.nstrip{position:relative;overflow:hidden;border:3px solid var(--ink);color:#F4F4EF;padding:38px 22px 26px;
 background:linear-gradient(90deg,#3A3F6B 0%,#151B33 22%,#0E1326 55%,#1B2440 78%,#C9783A 93%,#F2B45C 100%)}
.nstars{position:absolute;left:14%;right:24%;top:0;height:46%;pointer-events:none;opacity:.8;
 background:radial-gradient(1.4px 1.4px at 8% 30%,#fff,transparent),radial-gradient(1px 1px at 21% 62%,#fff,transparent),radial-gradient(1.6px 1.6px at 37% 22%,#fff,transparent),radial-gradient(1px 1px at 52% 70%,#fff,transparent),radial-gradient(1.3px 1.3px at 66% 35%,#fff,transparent),radial-gradient(1px 1px at 80% 18%,#fff,transparent),radial-gradient(1.2px 1.2px at 93% 58%,#fff,transparent)}
.nmoon{position:absolute;left:24%;top:10px;width:20px;height:20px;border-radius:50%;box-shadow:-6px 3px 0 0 #F4E9C8;transform:rotate(-20deg)}
.nsun{position:absolute;right:-26px;top:-26px;width:74px;height:74px;border-radius:50%;background:radial-gradient(#FFE29A 0 45%,rgba(255,226,154,0) 70%)}
.nextra{margin:14px 0 26px;font-size:14px;color:var(--ink-2)}.nextra code{font-size:12.5px}.nextra a{font-weight:700;color:var(--ink);white-space:nowrap}
/* the night on a clock: dawn lifts with --t (0 at 22:30, 1 at 06:30); the moon sets, the sun rises, each job's bar fills and is stamped */
.nstrip{padding:30px 22px 22px}
.nstrip::after{content:"";position:absolute;inset:0;pointer-events:none;background:linear-gradient(90deg,transparent 40%,rgba(242,180,92,.55));opacity:calc(var(--t) * var(--t))}
.nstrip>.nstars{left:0;right:30%;height:60%;opacity:calc(.9 - var(--t) * .6);animation:twinkle 3.2s ease-in-out infinite alternate}
@keyframes twinkle{to{filter:brightness(1.6)}}
.nstrip>.nmoon{left:calc(36% + var(--t) * 22%);top:calc(6px + var(--t) * 12px);opacity:calc(1 - var(--t) * .7)}
.nstrip>.nsun{top:calc(40px - var(--t) * 66px);width:90px;height:90px;opacity:calc(.25 + var(--t) * .75)}
.nrow{position:relative;z-index:1;display:grid;grid-template-columns:230px minmax(0,1fr) 210px;gap:22px;align-items:stretch}
.ntype,.nmorn{display:flex;flex-direction:column;gap:6px;padding:14px;border:2px solid rgba(244,244,239,.9);background:rgba(16,19,22,.6)}
.nrow .nt{font:700 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:#C9D2E8}
.ntype b,.nmorn b{font:800 21px/1.05 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.ntype code{display:block;min-height:3.1em;font:600 12.5px/1.45 "Martian Mono",ui-monospace,monospace;color:#FBB401;background:#101316;padding:8px 9px;border:1px solid #FBB401;word-break:break-word}
.ncar{display:inline-block;width:7px;height:1.1em;margin-left:2px;vertical-align:-2px;background:#FBB401;animation:caret 1s steps(1) infinite}
@keyframes caret{50%{opacity:0}}
.nstrip:not(.live) .ncar,.nstrip.typed .ncar{display:none}
.nmorn{background:#F4F4EF;color:#101316;border-color:#101316;box-shadow:4px 4px 0 rgba(0,0,0,.3);transition:transform .5s cubic-bezier(.3,1.5,.5,1),opacity .4s}
.nmorn .nt{color:#8A5A00}.nmorn>span:not(.nt){font-size:13px;line-height:1.4;color:#30363B}
.nmorn b{font-size:26px}
.nstrip.live:not(.dawn) .nmorn{opacity:.18;transform:translateY(10px)}
.nline{display:grid;grid-template-rows:auto 1fr auto;gap:8px;min-width:0}
.nclock{display:flex;justify-content:space-between;align-items:baseline}
.nclock span{font:700 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:#C9D2E8}
.nclock b{font:700 26px/1 "Martian Mono",ui-monospace,monospace;color:#FBB401;letter-spacing:.04em;font-variant-numeric:tabular-nums}
.ntrack{position:relative;min-height:96px;border-bottom:2px solid rgba(244,244,239,.7)}
.njob{position:absolute;top:6px;bottom:10px;left:calc(var(--a) * 100%);width:calc((var(--b) - var(--a)) * 100%);display:flex;flex-direction:column;gap:3px;padding:9px 10px 14px;
 border:2px solid rgba(244,244,239,.85);background:rgba(16,19,22,.6);transition:border-color .3s,background .3s}
.njob b{font:800 19px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.njob span{max-width:100%;font-size:12px;line-height:1.3;color:#DCE2EC;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.njob .nfill{position:absolute;left:0;bottom:0;height:7px;width:calc(var(--f, 1) * 100%);background:repeating-linear-gradient(-45deg,#FBB401 0 7px,#101316 7px 14px);background-size:20px 20px}
.njob.on .nfill{animation:nbuild .5s linear infinite}
@keyframes nbuild{to{background-position:20px 0}}
.njob.on{border-color:#FBB401}
.njob em{position:absolute;right:-5px;top:-11px;z-index:1;font:800 12px/1 "Big Shoulders Display",sans-serif;font-style:normal;letter-spacing:.1em;text-transform:uppercase;background:#3FAE6A;color:#101316;border:2px solid #101316;padding:4px 6px;transform:rotate(-8deg);opacity:0}
.njob:not(.on):not(.done) em{opacity:0}
.njob.done{border-color:#3FAE6A;background:rgba(30,123,74,.28)}.njob.done .nfill{background:#3FAE6A}
.njob.done em{opacity:1;animation:nstamp .35s cubic-bezier(.3,1.6,.5,1)}
@keyframes nstamp{from{transform:rotate(-8deg) scale(2.2);opacity:0}to{transform:rotate(-8deg) scale(1);opacity:1}}
.nstrip:not(.live) .njob{--f:1}
.ncur{position:absolute;top:0;bottom:-2px;left:calc(var(--t) * 100%);width:2px;background:#FBB401;box-shadow:0 0 10px 2px rgba(251,180,1,.6)}
.ncur::after{content:"";position:absolute;left:-5px;bottom:-6px;border:6px solid transparent;border-bottom-color:#FBB401;border-top:0}
.nstrip:not(.live) .ncur,.nstrip.dawn .ncur{opacity:0}
.nticks{display:flex;justify-content:space-around;font:600 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.06em;color:#AEB8CC}
.nreplay{position:absolute;z-index:2;right:12px;bottom:8px;font:700 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;color:#101316;background:#F4F4EF;border:2px solid #101316;padding:5px 8px;cursor:pointer}
.nstrip:not(.dawn) .nreplay{visibility:hidden}
.nstrip.dawn .nmorn{animation:nland .6s cubic-bezier(.3,1.5,.5,1)}
@keyframes nland{from{transform:translateY(10px) rotate(-2deg)}to{transform:none}}
.nstrip{padding-bottom:40px}
@media (min-width:981px) and (max-width:1240px){.nrow{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}.nline{grid-column:1/-1;grid-row:2}.nmorn{grid-column:2;grid-row:1}.ntype{grid-row:1}.ntrack{min-height:90px}}
@media (max-width:980px){.nstrip{padding:26px 16px 44px;background:linear-gradient(180deg,#3A3F6B 0%,#151B33 16%,#0E1326 55%,#1B2440 80%,#C9783A 93%,#F2B45C 100%)}
 .nstrip::after{background:linear-gradient(180deg,transparent 50%,rgba(242,180,92,.55))}
 .nrow{grid-template-columns:minmax(0,1fr);gap:16px}.nstrip>.nmoon{left:auto;right:22px}.nstrip>.nsun{right:auto;left:50%;top:auto;bottom:calc(-60px + var(--t) * 30px);margin-left:-45px}
 .ntrack{min-height:0;border-bottom:0;display:grid;gap:10px}.njob{position:relative;left:auto;top:auto;bottom:auto;width:auto;min-height:62px}
 .ncur,.nticks{display:none}}
@media (prefers-reduced-motion:reduce){.nstrip>.nstars,.njob.on .nfill,.ncar{animation:none}}
.npair{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:22px;margin:6px 0 26px}
.npair article{border:3px solid var(--ink);background:var(--panel);padding:0 0 18px;display:flex;flex-direction:column}
.npair .nh{display:flex;flex-direction:column;gap:6px;padding:14px 18px 12px;border-bottom:1px solid var(--line);margin-bottom:14px}
.npair .nh span{align-self:flex-start;font:700 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;padding:5px 8px;background:#14233B;color:#FBB401}
.npair .nmorn .nh span{background:#FBD38D;color:#101316}
.npair .nh b{font:800 26px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.nprep{margin:0 18px 12px;font-size:14px;color:var(--ink-2)}
.ncmd{margin:0 18px;background:#101316;color:#E7EAE5;padding:14px 16px;font:600 13.5px/1.5 "Martian Mono",ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere}
.ncmd code{background:none;color:inherit;padding:0;font:inherit}
.npair mark{background:none;color:#FBB401;border-bottom:2px solid #FBB401}.npair mark.opt{color:#7DB8F5;border-bottom:2px dashed #7DB8F5}
.nparts{margin:16px 18px 0;display:grid;grid-template-columns:auto minmax(0,1fr);gap:12px 16px;font-size:13.5px;align-items:start}
.nparts dt{font:600 12px/1.5 "Martian Mono",ui-monospace,monospace;background:#101316;padding:4px 8px;align-self:start;white-space:nowrap}.nparts dd{margin:0;color:var(--ink-2)}
.nlink{margin:14px 18px 0;font-size:13.5px;color:var(--ink-2)}.nlink a{color:var(--ink);font-weight:600}
.nnote{margin:auto 18px 0;padding-top:14px;font-size:13.5px;color:var(--ink-2)}
.nsum{margin:0 18px;background:#F4F4EF;color:#101316;border:2px solid #101316;box-shadow:6px 7px 0 rgba(0,0,0,.25)}
.nsum .nst{display:flex;justify-content:space-between;padding:8px 12px;border-bottom:2px solid #101316;font:700 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase}
.nsum .nst span+span{color:#646C70;font-weight:600}
.nsum ul{list-style:none;margin:0;padding:6px 12px}
.nsum li{display:grid;grid-template-columns:24px minmax(0,1fr);gap:10px;align-items:baseline;padding:8px 0;border-bottom:1px dashed #C9CFC7;font-size:14px}
.nsum li:last-child{border-bottom:0}.nsum li b{font:800 16px/1 "Public Sans",sans-serif;text-align:center}
.nsum .ok b{color:#1E7B4A}.nsum .no b{color:#C42B1C}.nsum .skip{color:#646C70}
.nsum .nfoot{display:flex;flex-direction:column;gap:4px;padding:10px 12px;border-top:2px solid #101316;font-size:13px;background:#E8ECE6}
@media (max-width:900px){.npair{grid-template-columns:minmax(0,1fr)}}
.watch{margin:0 0 22px;font:600 11.5px/1.4 "Martian Mono",ui-monospace,monospace;letter-spacing:.06em}
.watch a{color:var(--ink)}
/* the rules board: a white site board with a red header, a pictogram per rule */
.rboard{position:relative;background:#F4F4EF;color:#101316;border:3px solid #101316;box-shadow:5px 6px 0 rgba(0,0,0,.2)}
.rboard::before,.rboard::after{content:"";position:absolute;top:8px;width:9px;height:9px;border-radius:50%;background:#8C949A;border:2px solid #101316}
.rboard::before{left:8px}.rboard::after{right:8px}
.rbh{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:4px 16px;background:#C42B1C;color:#fff;padding:12px 30px 10px;border-bottom:3px solid #101316}
.rbh b{font:800 26px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;letter-spacing:.04em}
.rbh span{font:600 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase}
.rboard ul{list-style:none;margin:0;padding:6px 24px 10px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 28px}
.rboard li{display:grid;grid-template-columns:40px minmax(0,1fr);gap:14px;align-items:center;padding:12px 0;border-bottom:1px dashed #B9C0B8;font:600 14.5px/1.45 "Public Sans",system-ui,sans-serif}
.rboard li svg{width:40px;height:40px;display:block}
.rboard code{background:rgba(16,19,22,.1);color:#101316}
@media (max-width:900px){.rboard ul{grid-template-columns:1fr}}
/* nothing is lost: one session hands the next four things */
/* Nothing is lost: the site in cutaway, and the notice for the part you pick */
.memmap{display:grid;grid-template-columns:minmax(0,1fr);border:3px solid var(--ink);background:var(--panel)}
.memmap{--sky:#E6EDF0;--soil:#B9A58A;--grit:#9C8869;--ground:#5F6B4F;--tg:#101316;--wr:#8A5A00;--rd:#1F5FA8;--wl:#E3A300}
:root[data-theme="dark"] .memmap{--sky:#1B2733;--soil:#4A3E31;--grit:#5C4E3E;--ground:#3D4A35;--tg:#E7EAE5;--wr:#FBB401;--rd:#7DB8F5;--wl:#FBB401}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .memmap{--sky:#1B2733;--soil:#4A3E31;--grit:#5C4E3E;--ground:#3D4A35;--tg:#E7EAE5;--wr:#FBB401;--rd:#7DB8F5;--wl:#FBB401}}
.cutw{border-bottom:3px solid var(--ink);display:flex;flex-direction:column;min-width:0}
.cutsc{overflow-x:auto}
.cut{display:block;width:100%;height:auto}
@media (max-width:720px){.cut{min-width:660px}}
.cut .c-sky{fill:var(--sky)}.cut .c-soil{fill:var(--soil)}.cut .c-grit{fill:var(--grit)}.cut .c-ground{fill:var(--ground)}
.cut .c-band{stroke:var(--tg);stroke-width:1;stroke-dasharray:2 6;opacity:.35}
.cut .b-ses,.memmap .b-ses{fill:#5AA0F0;background:#5AA0F0}.cut .b-job,.memmap .b-job{fill:#FBB401;background:#FBB401}.cut .b-perm,.memmap .b-perm{fill:#9AA29C;background:#9AA29C}
.cut .rt{font:700 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;fill:#101316}
.cut .c-done{fill:#5A646B;stroke:#101316;stroke-width:2.5}.cut .c-now{fill:#2A3A52;stroke:#101316;stroke-width:2.5}.cut .c-win{fill:#FBB401}
.cut .c-next{fill:none;stroke:var(--tg);stroke-width:2.2;stroke-dasharray:7 5;opacity:.7}
.cut .c-paper{fill:#F4F4EF;stroke:#101316;stroke-width:2}.cut .c-lines{fill:none;stroke:#101316;stroke-width:1.6}.cut .c-dash{fill:#C9CFC7}
.cut .c-post{stroke:#101316;stroke-width:5}.cut .c-cabin{fill:#1F5FA8;stroke:#101316;stroke-width:2.5}
.cut .c-drawer{fill:#8C949A;stroke:#101316;stroke-width:2}
.cut .c-side{fill:#3A444B;stroke:#101316;stroke-width:2;stroke-linejoin:round}.cut .c-cabside{fill:#16406F;stroke:#101316;stroke-width:2;stroke-linejoin:round}.cut .c-roof{fill:#2B3137;stroke:#101316;stroke-width:2;stroke-linejoin:round}.cut .c-conside{fill:#7C847E;stroke:#101316;stroke-width:2}.cut .c-vside{fill:#1C2024;stroke:#101316;stroke-width:2}
.cut .tg-tool{font-size:9.5px;fill:#fff;letter-spacing:.04em}.cut .tool .hit{stroke-dasharray:4 3}
.cut .c-glow,.cut .c-winglow{opacity:0}.cut .c-winglow{fill:#FFD28A}
:root[data-theme="dark"] .cut .c-glow{opacity:1}:root[data-theme="dark"] .cut .c-winglow{opacity:.9}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .cut .c-glow{opacity:1}:root:not([data-theme="light"]) .cut .c-winglow{opacity:.9}}
:root[data-theme="dark"] .cut .c-win{filter:drop-shadow(0 0 3px #FBB401)}
.memmap .b-tool{background:#F4F4EF;border:1.5px solid #101316}.cut .c-vault{fill:#2B3137;stroke:#101316;stroke-width:2.5}.cut .c-box{fill:#C8A46A;stroke:#101316;stroke-width:1.8}
.cut .tg{font:700 11.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;fill:var(--tg)}
.cut .tg-files{font-size:9.5px;letter-spacing:.06em}.cut .tg-now{fill:#FBB401}.cut .tg-next{fill:var(--tg);opacity:.75}.cut .tg-plate{fill:#101316;font-size:10px}.cut .tg-dk{fill:#101316;font-size:12px}.cut .tg-key{fill:#fff}
.cut .lt{font:600 11px/1 "Martian Mono",ui-monospace,monospace;fill:var(--tg);opacity:.85}.cut .lt-w{fill:var(--wr);opacity:1}.cut .lt-r{fill:var(--rd);opacity:1}.cut .lt-s{font-size:10px}
.cut .lk{fill:none;stroke-width:2.4;transition:opacity .2s}
.cut .lk.w{stroke:var(--wl);opacity:.85}.cut .lk.r{stroke:#5AA0F0;stroke-dasharray:6 5;opacity:.8}
.cut.picked .lk[id]:not(.hot){opacity:.2}.cut .lk.hot{opacity:1;stroke-width:3.6}
.cut .pin circle{fill:#F4F4EF;stroke:#101316;stroke-width:2}.cut .pin text{font:700 11px/1 "Martian Mono",ui-monospace,monospace;fill:#101316}
.cut .nd{cursor:pointer;outline:none}.cut .nd .hit{fill:transparent;stroke:transparent;stroke-width:3;stroke-dasharray:6 4}
.cut .nd:hover .hit,.cut .nd:focus-visible .hit{stroke:var(--tg)}.cut .nd.on .hit{stroke:#FBB401}.cut .nd.on .pin circle{fill:#101316;stroke:#F4F4EF}.cut .nd.on .pin text{fill:#F4F4EF}
.cut.touring .amb{display:none}
.cutw .hint{display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px;padding:10px 14px;border-top:1px solid var(--line);font:600 10.5px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:.06em;color:var(--ink-3)}
.memmap button{font:700 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;padding:9px 12px;border:2px solid var(--ink);background:var(--panel);color:var(--ink);cursor:pointer}
.memmap button:hover,.memmap button:focus-visible{background:var(--hivis);color:#101316;border-color:#101316}
.memmap [data-tour]{background:#101316;color:#FBB401;border-color:#101316}
.memmap [data-tour][aria-pressed="true"]{background:var(--hivis);color:#101316}
.memmap:not(.js) .hint,.memmap:not(.js) .mnav{display:none}
.mems{padding:20px 24px 22px;display:flex;flex-direction:column;gap:16px}
.mem:not(.tour){display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:4px 32px}.mem:not(.tour)>.mh{grid-column:1/-1}.mem:not(.tour)>dl{grid-column:2;grid-row:2/span 3;align-self:start}
.mem[hidden]{display:none!important}
/* the ten plain cards share one cell, so the box keeps one size as you step through them; the two with
   a diagram (the Logbook and the card press) take their own height. The buttons sit on top and never move */
.memmap.js .mstack{display:grid}.memmap.js .mstack>.mem{grid-area:1/1;min-width:0}
.memmap.js .mstack>.mem:not(.tour)[hidden]{display:grid!important;visibility:hidden}
.mx{grid-column:1/-1}.memmap.js .mx .mxb{display:none}.memmap:not(.js) .mdiag{display:none}
.mdiag{margin-top:14px;justify-self:start}
.mdlg{width:min(1060px,94vw);max-height:90vh;padding:0;border:3px solid var(--ink);background:var(--panel);color:var(--ink);box-shadow:8px 8px 0 rgba(0,0,0,.3)}
.mdlg::backdrop{background:rgba(16,19,22,.62)}
.mdlg .mdh{position:sticky;top:0;z-index:1;display:flex;justify-content:space-between;align-items:center;gap:12px;background:#101316;color:#FBB401;padding:10px 14px;font:700 12px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase}
.mdlg .mdh button{font:inherit;letter-spacing:inherit;text-transform:inherit;color:#101316;background:#FBB401;border:2px solid #FBB401;padding:7px 10px;cursor:pointer}
.mdlg .mdb{padding:18px 20px 22px}.mdlg .mdb>*{margin-top:0}.mdlg .press{margin:0;padding:0;border-top:0}
.memmap.js .mstack>.mem:not(.tour){align-content:start}
.memmap.js .mems>.mnav{order:-1}
.memmap.js .mems:has(.tour:not([hidden]))>.mnav [data-go]{display:none}
/* wide screens: the card floats over the drawing beside the part you picked, so both are in view */
.marrow{display:none}
@media (min-width:1200px){
 .memmap.js{position:relative}
 .memmap.js .mems{position:absolute;z-index:6;left:0;top:0;width:410px;gap:10px;padding:12px 16px 14px;background:var(--panel);border:3px solid var(--ink);box-shadow:6px 7px 0 rgba(0,0,0,.3);overflow-y:auto;overscroll-behavior:contain;transition:left .32s cubic-bezier(.3,.7,.3,1),top .32s cubic-bezier(.3,.7,.3,1),opacity .2s}
 .memmap.js .mems .mem:not(.tour){grid-template-columns:minmax(0,1fr);gap:2px}.memmap.js .mems .mem:not(.tour)>dl{grid-column:1;grid-row:auto}
 .memmap.js .mems .mem h3{font-size:24px;margin:10px 0 6px}.memmap.js .mems .mem p{font-size:13.5px;line-height:1.5;margin-bottom:6px}.memmap.js .mems .mem dl{font-size:12.5px;line-height:1.4;margin-top:8px}.memmap.js .mems .mdiag{margin-top:8px}
 .memmap.js .mems .mnav button{padding:7px 10px}
 .memmap.js .marrow{display:block;position:absolute;z-index:7;width:0;height:0;border:11px solid transparent;pointer-events:none;transition:left .32s cubic-bezier(.3,.7,.3,1),top .32s cubic-bezier(.3,.7,.3,1),opacity .2s}
 .memmap.js .marrow.r{border-right-color:var(--ink)}.memmap.js .marrow.l{border-left-color:var(--ink)}
 .memmap.js.shut .mems,.memmap.js.shut .marrow{opacity:0;pointer-events:none;visibility:hidden}
 .memmap.js .mshut{margin-left:auto}
 .memmap.js .mnav{gap:8px}
}
.memmap .mshut{display:none}@media (min-width:1200px){.memmap.js .mshut{display:inline-block}}
.mem .mh{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:6px 12px}
.mem .chip{color:#101316;font:700 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;padding:7px 9px}
.mem .mn,.mem .tn{font:600 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;color:var(--ink-3)}
.mem h3{margin:14px 0 8px;font:800 30px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.mem>code{display:inline-block;justify-self:start;font-size:11.5px;margin-bottom:10px}
.mem p{margin:0 0 12px;font-size:15px;color:var(--ink)}
.mem dl{margin:14px 0 0;display:grid;grid-template-columns:auto minmax(0,1fr);gap:0;border:2px solid var(--ink);box-shadow:3px 3px 0 var(--ink)}
.mem dt{display:flex;align-items:center;font:700 9.5px/1.2 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;background:#101316;color:#FBB401;padding:7px 9px}
.mem dd{margin:0;padding:7px 10px;font-size:14px;color:var(--ink);background:var(--panel)}
.mem dd code{white-space:nowrap}.mem dt:first-of-type{border-bottom:1px solid #3A4046}.mem dd:first-of-type{border-bottom:2px solid var(--ink)}
.mnav{display:flex;gap:10px;justify-content:space-between;margin-top:auto}
.tour .mnav{justify-content:flex-end;margin-top:6px}
.tour h3,.mem.tl h3{text-transform:none;letter-spacing:.01em}
.cut .tg-slot{font-size:8.5px;fill:#101316;letter-spacing:.14em}
.cut .c-press{fill:#6F787C;stroke:#101316;stroke-width:2}.cut .c-pressrod{stroke:#101316;stroke-width:3}
.press{grid-column:1/-1;list-style:none;margin:16px 0 0;padding:16px 0 0;border-top:1px dashed var(--line);display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:14px;counter-reset:none}
.press li{position:relative;border:2px solid var(--ink);background:var(--panel);padding:12px 12px 14px;display:flex;flex-direction:column;gap:6px}
.press li+li::before{content:"";position:absolute;left:-14px;top:22px;width:14px;height:2px;background:var(--ink)}
.press .pn{align-self:flex-start;font:800 15px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;background:#FBB401;color:#101316;padding:3px 6px 2px}
.press li:last-child .pn{background:#3FAE6A}
.press b{font:800 18px/1.05 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.press .pt{font-size:12.5px;line-height:1.45;color:var(--ink-2)}
@media (max-width:1100px){.press{grid-template-columns:repeat(3,minmax(0,1fr))}.press li:nth-child(4)::before{display:none}}
@media (max-width:640px){.press{grid-template-columns:minmax(0,1fr)}.press li+li::before{left:22px;top:-14px;width:2px;height:14px}.press li:nth-child(4)::before{display:block}}
.lgraph{grid-column:1/-1;margin:16px 0 0;padding-top:14px;border-top:1px dashed var(--line);color:var(--ink-2)}
.lgraph .lgh{display:flex;flex-wrap:wrap;gap:6px 26px;margin-bottom:10px;font-size:13.5px}
.lgraph .lgh code,.lgraph figcaption code{font-size:12px}
.lgraph svg{display:block;width:100%;height:auto}
.lgraph .gcl{fill:none;stroke:var(--ink-3);stroke-width:1.4;stroke-dasharray:5 5}
.lgraph .gcn{font:600 11px/1 "Martian Mono",ui-monospace,monospace;fill:var(--ink-3);letter-spacing:.06em}
.lgraph .gc rect{fill:#F4F4EF;stroke:#101316;stroke-width:2}.lgraph .gnew>rect:first-child{fill:#FBB401}
.lgraph .gweak rect{fill:#DCDCD5;stroke:#7C8387;stroke-dasharray:5 4}.lgraph .gweak .gid,.lgraph .gweak .gk,.lgraph .gweak .gn{fill:#3A4044}
.lgraph .gid{font:700 15px/1 "Martian Mono",ui-monospace,monospace;fill:#101316}
.lgraph .gk,.lgraph .gn{font:600 10px/1 "Martian Mono",ui-monospace,monospace;fill:#454C50;letter-spacing:.08em}
.lgraph .gtag{fill:#101316}.lgraph .gtagt{font:700 9.5px/1 "Martian Mono",ui-monospace,monospace;fill:#FBB401;letter-spacing:.12em}
.lgraph .gweakt{font:700 10px/1 "Martian Mono",ui-monospace,monospace;fill:var(--ink-2);letter-spacing:.08em;text-transform:uppercase}
.lgraph .ge{fill:none;stroke:currentColor;stroke-width:2.2}.lgraph .ge.g-dash{stroke-dasharray:6 5}
.lgraph .ge.g-new{stroke:#B07A00}.lgraph .ge.g-bad{stroke:#C42B1C}
.lgraph .gl{font:700 11.5px/1 "Martian Mono",ui-monospace,monospace;fill:currentColor;letter-spacing:.03em;paint-order:stroke;stroke:var(--panel);stroke-width:5px;stroke-linejoin:round}
.lgraph .gl.g-new{fill:var(--brand)}.lgraph .gl.g-bad{fill:#C42B1C}
:root[data-theme="dark"] .lgraph .gl.g-bad{fill:#FF7A6E}:root[data-theme="dark"] .lgraph .ge.g-bad,:root[data-theme="dark"] .lgraph #gm-bad path{stroke:#FF7A6E}:root[data-theme="dark"] .lgraph .ge.g-new,:root[data-theme="dark"] .lgraph #gm-new path{stroke:#FBB401}:root[data-theme="dark"] .lgraph .gweak rect{fill:#3A4044;stroke:#8A938D}:root[data-theme="dark"] .lgraph .gweak .gid{fill:#E7EAE5}:root[data-theme="dark"] .lgraph .gweak .gk,:root[data-theme="dark"] .lgraph .gweak .gn{fill:#B4BBB6}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .lgraph .gl.g-bad{fill:#FF7A6E}:root:not([data-theme="light"]) .lgraph .ge.g-bad,:root:not([data-theme="light"]) .lgraph #gm-bad path{stroke:#FF7A6E}:root:not([data-theme="light"]) .lgraph .ge.g-new,:root:not([data-theme="light"]) .lgraph #gm-new path{stroke:#FBB401}:root:not([data-theme="light"]) .lgraph .gweak rect{fill:#3A4044;stroke:#8A938D}:root:not([data-theme="light"]) .lgraph .gweak .gid{fill:#E7EAE5}:root:not([data-theme="light"]) .lgraph .gweak .gk,:root:not([data-theme="light"]) .lgraph .gweak .gn{fill:#B4BBB6}}
.lgraph figcaption{margin-top:8px;font-size:13.5px;line-height:1.5}
@media (max-width:900px){.mem:not(.tour){grid-template-columns:minmax(0,1fr)}.mem:not(.tour)>dl{grid-column:1;grid-row:auto}}
.chain{display:grid;grid-template-columns:120px minmax(0,1fr) 120px;gap:14px;align-items:stretch}
.sess{display:flex;align-items:center;justify-content:center;text-align:center;border:2px solid var(--ink);background:var(--panel);font:800 20px/1.05 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;padding:10px}
.sess.next{background:var(--hivis);color:#101316;border-color:#101316}
.carry{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;position:relative}
.carry li{background:var(--panel);border:1px solid var(--line);padding:14px 14px 16px;display:flex;flex-direction:column;gap:6px}
.carry b{font:800 20px/1.05 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.carry code{align-self:flex-start;font-size:11px}
.carry p{margin:0;font-size:13.5px;color:var(--ink-2)}
/* the route: the plan runs once per project, then every job runs as a loop, once per ticket */
.rt-h{display:flex;flex-wrap:wrap;justify-content:space-between;gap:4px 12px;margin:34px 0 0;font:600 11px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink)}
.rt-h span{color:var(--ink-3);font-weight:500;letter-spacing:.06em;text-transform:none}
.once{position:relative;margin-top:28px}
.track{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));border-top:3px solid var(--ink);position:relative}
.track li{display:flex;min-width:0}
.phs{flex:1;display:flex;flex-direction:column;align-items:flex-start;gap:7px;padding:0 12px 4px 0;min-width:0}
.phs .mk{margin-top:-9px;width:15px;height:15px;background:var(--hivis);border:2px solid #101316}
.phs.word .mk{transform:rotate(45deg);width:17px;height:17px;margin-top:-10px}
.phs .vb{margin-top:6px;font:800 22px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;letter-spacing:.01em}
.phs .sico{width:30px;height:30px;padding:3px;background:#F4F4EF;border:2px solid #101316;flex:none}
.phs .sih{display:flex;align-items:center;gap:8px;margin-top:10px}.phs .sn{font:700 11px/1 "Martian Mono",ui-monospace,monospace;font-style:normal;letter-spacing:.06em;color:var(--ink-3)}
#route{position:relative}#route>*{position:relative;z-index:1}#route>svg.conv{position:absolute;left:0;top:0;z-index:0;pointer-events:none;overflow:visible}
.conv .cvl{fill:none;stroke:var(--ink);stroke-width:3;stroke-linejoin:miter}.conv .cvt{font:600 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;fill:var(--ink-3)}
.phs[data-step]{cursor:pointer;outline:none;box-shadow:0 0 0 0 transparent}
.phs[data-step]:hover .vb,.phs[data-step]:focus-visible .vb{color:var(--brand)}
.phs[data-step].on .vb{color:var(--brand)}.phs[data-step].on .mk{background:#101316;border-color:#101316;box-shadow:inset 0 0 0 3px var(--hivis)}.phs[data-step].on .sico{border-color:var(--hivis);box-shadow:0 0 0 2px var(--hivis)}
#stepbar{margin:18px 0 0;border:2px solid var(--ink)}
.strip{margin-top:16px;border:3px solid var(--ink);background:var(--panel);border-left:8px solid var(--hivis)}
.strip.pinned{border-left-color:var(--ink)}
.strip .stop{display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px;padding:8px 14px;border-bottom:1px solid var(--line)}
.strip .smode{font:700 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;background:#101316;color:#FBB401;padding:5px 8px}
.strip.pinned .smode{background:var(--ink);color:var(--ground)}
.strip .sctl{display:inline-flex;gap:4px}.strip .sctl button{display:inline-flex;align-items:center;justify-content:center;min-width:40px;height:32px;padding:0 9px;border:2px solid var(--ink);background:var(--panel);color:var(--ink);cursor:pointer}
.strip .sctl button svg{height:13px;width:auto;display:block}
.strip [data-play] .ic-play,.strip.pinned [data-play] .ic-pause{display:none}.strip.pinned [data-play] .ic-play{display:block}
.strip .sctl button:hover,.strip .sctl button:focus-visible{background:var(--hivis);color:#101316;border-color:#101316}
.strip .sfollow{font:700 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.06em;text-transform:uppercase;padding:6px 9px;border:2px solid var(--ink);background:var(--panel);color:var(--ink);cursor:pointer}
.strip .sfollow:hover,.strip .sfollow:focus-visible{background:var(--hivis);color:#101316;border-color:#101316}
.strip .sall{margin-left:auto;font:600 11px/1.3 "Martian Mono",ui-monospace,monospace;color:var(--ink)}
.sitem{display:grid;grid-template-columns:36px minmax(0,1fr) auto;gap:6px 14px;padding:12px 16px;align-items:center}
.sitems{display:grid}.sitem{grid-area:1/1}.sitem.off{visibility:hidden}
.sitem b{display:block;font:800 21px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;margin:2px 0 6px}
.sitem .snum{font:700 12px/1 "Martian Mono",ui-monospace,monospace;color:var(--ink-3);vertical-align:3px;margin-right:4px}
.sitem p{margin:0;font-size:14px;line-height:1.5;color:var(--ink);max-width:90ch}
/* the rule is a site sign: a hazard-striped edge, a black tab, the rule in stencil capitals on yellow */
.sitem .sgate{margin:0;display:flex;align-items:stretch;max-width:340px;border:2px solid #101316;background:#FBB401;color:#101316;box-shadow:3px 3px 0 #101316}
.sitem .sgate::before{content:"";flex:none;width:10px;background:repeating-linear-gradient(-45deg,#101316 0 5px,#FBB401 5px 10px);border-right:2px solid #101316}
.sitem .sgate span{flex:none;display:flex;align-items:center;font:700 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;background:#101316;color:#FBB401;padding:0 8px}
.sitem .sgate b{display:block;margin:0;padding:8px 12px;font:800 17px/1.1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;letter-spacing:.01em;color:#101316}
@media (max-width:720px){.sitem{grid-template-columns:36px minmax(0,1fr)}.sitem .sgate{grid-column:1/-1;max-width:none;margin-top:4px}
 #stepbox .sitem .mchips{grid-column:1/-1;gap:5px}#stepbox .sitem .mchip{font-size:9px;padding:4px 6px}}
.sitem .mchips{grid-column:2/-1;margin-top:0;gap:6px}.sitem .mchip{font-size:9.5px;padding:5px 7px;border-width:1.5px}
#route:not(.js) .strip{display:none}
.catalog{margin:14px 0 0;font:600 11.5px/1.4 "Martian Mono",ui-monospace,monospace;letter-spacing:.04em}.catalog a{color:var(--ink)}
#route>.strip{position:sticky;bottom:0;z-index:5;box-shadow:0 -8px 18px rgba(0,0,0,.18)}
@media (max-width:720px){#route>.strip{position:relative;box-shadow:none}}
@media (max-width:720px){.strip .sall{margin-left:0}}
.sbh{display:flex;flex-wrap:wrap;align-items:center;gap:8px 18px;padding:10px 14px;border-bottom:1px solid var(--line);font:600 10.5px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:.06em;color:var(--ink-3)}
.sbh button{font:700 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;padding:9px 12px;border:2px solid #101316;background:#101316;color:#FBB401;cursor:pointer}
.sbh button[aria-pressed="true"]{background:var(--hivis);color:#101316}
.sbh .key{display:inline-flex;align-items:center;gap:6px}.sbh .key i{display:inline-block;width:11px;height:11px;background:var(--hivis);border:2px solid #101316}
.sbh .key .k-di{transform:rotate(45deg);margin-left:10px}
.sbh .tip{margin-left:auto}
.snote{display:grid;grid-template-columns:44px minmax(0,1fr);gap:14px;padding:16px 44px 14px 18px}
.snote[hidden]{display:none}
.snico{width:36px;height:36px;padding:4px;background:#F4F4EF;border:2px solid #101316}
.snote h3{margin:0 0 8px;font:800 24px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.snote p{margin:0 0 12px;font-size:14px;color:var(--ink)}
.snote dl{margin:0;display:grid;grid-template-columns:auto minmax(0,1fr);gap:6px 16px;border-top:1px dashed var(--line);padding-top:12px}
.snote dt{font:600 10px/1.7 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.snote dd{margin:0;font-size:13px;color:var(--ink-2)}
.mchips{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:14px;font:600 10px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3)}
.mchip{font:700 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.04em;padding:7px 9px;border:2px solid #101316;cursor:pointer;color:#101316}
.mchip.m-writes{background:#FBB401}.mchip.m-reads{background:#7DB8F5}
.mchip:hover,.mchip:focus-visible{outline:3px solid var(--ink);outline-offset:1px}
@media (max-width:720px){.snote{grid-template-columns:minmax(0,1fr)}.snico{width:40px;height:40px}.sbh .tip{margin-left:0}}
.who{display:inline-flex;align-items:center;gap:6px;flex-wrap:wrap}
.who b{font:600 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;padding:4px 6px 3px;border:1.5px solid currentColor}
.r-foreman{color:var(--ink)}.r-builder{color:var(--run)}.r-inspectors{color:var(--inspect)}
.who b.r-you{background:var(--hivis);color:#101316;border-color:#101316}
.who em{flex-basis:100%;white-space:nowrap;font:600 9.5px/1.2 "Martian Mono",ui-monospace,monospace;font-style:normal;letter-spacing:.12em;text-transform:uppercase;color:var(--brand)}
.phs .nt{font-size:13px;line-height:1.35;color:var(--ink-3)}
.phs .cmds{display:flex;flex-wrap:wrap;gap:2px 9px;font:500 11.5px/1.5 "Martian Mono",ui-monospace,monospace}
.phs .cmds a{color:var(--ink-2);text-decoration:none;border-bottom:1px solid var(--line)}
.phs .cmds a:hover{color:var(--ink);border-bottom-color:var(--ink)}
.feed{display:flex;align-items:center;gap:10px;margin:26px 0 0;padding-left:18px;font:600 11px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink)}
.feed b{font:700 16px/1 "Public Sans",sans-serif}
.feed span{color:var(--ink-3);font-weight:500;letter-spacing:.06em;text-transform:none}
@media (max-width:720px){.feed{flex-wrap:wrap}.feed span{flex-basis:100%}}
@media (max-width:720px){.shiftbox{padding-top:40px}.shiftbox .sl{right:14px;line-height:1.35}}
.loop{position:relative;margin-top:30px;padding-bottom:44px}
.loop .track{padding:0 0 0 30px}
.loop .phs .vb{font-size:19px}
.loop .ret code{background:none;padding:0;text-transform:none;letter-spacing:0;font:600 11.5px/1 "Martian Mono",ui-monospace,monospace}
.loop::before{content:"";position:absolute;left:0;right:0;top:0;bottom:14px;border:3px solid var(--ink);border-top:0;pointer-events:none}
.loop::after{content:"";display:none;position:absolute}
/* which way round: open chevrons sitting on the frame (down the right, left along the bottom, up the left),
   each 15px square on whole pixels so it centres on the 3px line */
.loop .chev{position:absolute;width:15px;height:15px;color:var(--ink);pointer-events:none;overflow:visible}
.loop .cv-down{right:-6px;top:40%}
.loop .cv-left{left:22%;bottom:8px}
.loop .cv-up{left:-6px;top:40%}
.loop .ret{position:absolute;left:50%;bottom:4px;transform:translateX(-50%);background:var(--ground);padding:0 12px;white-space:nowrap;font:600 10.5px/1.6 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink)}
/* six skills to start with: six calm rows, one focal point each (the step), yellow only on hover */
.klist{list-style:none;margin:0;padding:0;border-top:2px solid var(--ink)}
.krow{display:grid;grid-template-columns:minmax(0,260px) minmax(0,1fr) 28px;gap:24px;align-items:center;padding:18px 12px 18px 0;border-bottom:1px solid var(--line);text-decoration:none;color:inherit}
.krow .st b{display:block;font:800 26px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;letter-spacing:.01em}
.krow .st code{display:inline-block;margin-top:7px;background:none;padding:0;font:500 13px/1 "Martian Mono",ui-monospace,monospace;color:var(--ink-2)}
.krow p{margin:0;font-size:15px;line-height:1.5}
.krow p+p{margin-top:4px;color:var(--ink-2);font-size:14px}
.krow p+p b{color:var(--ink);font-weight:600}
.krow i{font-style:normal;font:600 18px/1 "Public Sans",sans-serif;color:var(--ink-3);justify-self:end}
.krow:hover{background:var(--panel)}
.krow:hover i{color:#101316;background:var(--hivis);padding:4px 6px}
.krow:hover .st b{text-decoration:underline;text-decoration-color:var(--hivis);text-decoration-thickness:3px;text-underline-offset:4px}
@media (max-width:720px){.krow{grid-template-columns:minmax(0,1fr) 24px;gap:8px 12px}.krow .st{grid-column:1/-1}.krow p{grid-column:1}}
/* the skeptic's queries, as a site inspection report */
/* the route's walker */
.walker{position:absolute;left:0;top:0;width:36px;height:52px;z-index:3;pointer-events:none;will-change:transform}
.walker .wk{display:block;width:36px;height:52px;overflow:visible}
.walker .leg,.walker .arm{transform-box:fill-box;transform-origin:top center}
.walker.walking .l1,.walker.walking .a2{animation:stride .42s infinite alternate ease-in-out}
.walker.walking .l2,.walker.walking .a1{animation:stride .42s infinite alternate-reverse ease-in-out}
@keyframes stride{from{transform:rotate(-22deg)}to{transform:rotate(22deg)}}
.walker .bub{position:absolute;bottom:58px;left:50%;transform:translateX(-50%);white-space:nowrap;background:var(--ink);color:var(--ground);font:600 10px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;padding:6px 8px;opacity:0}
.walker .bub::after{content:"";position:absolute;left:50%;bottom:-6px;margin-left:-6px;border:6px solid transparent;border-bottom:0;border-top-color:var(--ink)}
.walker.talk .bub{opacity:1}
.loop{background-image:linear-gradient(var(--line-2) 1px,transparent 1px),linear-gradient(90deg,var(--line-2) 1px,transparent 1px);background-size:24px 24px}
.loop .phs{padding-top:0}
@media (min-width:1001px){.shiftbox .loop{margin-top:92px}}
@media (max-width:1000px){.walker{display:none}}
/* the skeptic's queries: stickers on the site office door, the answer pinned on the notice beside it */
.office{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1fr);gap:0;border:3px solid var(--ink)}
.cabin{--steel:#C6D0D5;--steel-2:#D6DEE2;--door:#5D6B73;position:relative;min-height:520px;background:repeating-linear-gradient(90deg,var(--steel) 0 12px,var(--steel-2) 12px 24px);border-right:3px solid var(--ink);overflow:hidden}
:root[data-theme="dark"] .cabin{--steel:#344047;--steel-2:#3D4A52;--door:#1F272B}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .cabin{--steel:#344047;--steel-2:#3D4A52;--door:#1F272B}}
.cabin .roof{position:absolute;left:0;right:0;top:0;height:16px;background:#101316}
.cabin .skid{position:absolute;left:0;right:0;bottom:0;height:14px;background:repeating-linear-gradient(-45deg,var(--hivis) 0 10px,#101316 10px 20px)}
.plate-so{position:absolute;top:30px;left:50%;transform:translateX(-50%);background:#1F5FA8;color:#fff;border:2px solid #101316;font:800 18px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;letter-spacing:.08em;padding:6px 14px}
.door{position:absolute;left:50%;transform:translateX(-50%);bottom:14px;width:34%;height:76%;background:var(--door);border:3px solid #101316;border-bottom:0}
.door{box-shadow:0 0 0 7px #2A3238,0 0 0 9px #101316;background-image:linear-gradient(90deg,rgba(255,255,255,.06),transparent 30%,rgba(0,0,0,.12))}
.door .win{position:absolute;left:22%;right:22%;top:9%;height:20%;background:linear-gradient(125deg,rgba(255,255,255,.45) 0 18%,transparent 18% 30%,rgba(255,255,255,.25) 30% 36%,transparent 36%),repeating-linear-gradient(180deg,#B9CCD6 0 7px,#8EA6B3 7px 9px);border:3px solid #101316}
.door .hinge{position:absolute;left:-4px;width:7px;height:22px;background:#2A3238;border:2px solid #101316}.door .h1{top:12%}.door .h2{top:70%}
.door .handle{position:absolute;right:8%;top:50%;width:20px;height:7px;background:#FBB401;border:2px solid #101316;border-radius:2px}
.door .handle::after{content:"";position:absolute;right:2px;top:9px;width:8px;height:12px;background:#C9CFD2;border:2px solid #101316}
.door .lamp{position:absolute;left:50%;top:-34px;transform:translateX(-50%);width:44px;height:16px;background:#FFE58A;border:3px solid #101316;border-radius:4px 4px 10px 10px;box-shadow:0 10px 26px 8px rgba(255,214,90,.35)}
.door .rule{position:absolute;left:10%;right:10%;bottom:19%;display:flex;align-items:center;gap:6px;background:#F4F4EF;color:#101316;border:2px solid #101316;font:700 8px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:.05em;text-transform:uppercase;text-align:left;padding:5px 6px}
.door .rule svg{flex:none;width:24px;height:24px}
.door .kick{position:absolute;left:0;right:0;bottom:0;height:13%;border-top:3px solid #101316;background:repeating-linear-gradient(45deg,#9AA4A8 0 3px,#B7C0C4 3px 7px),#AAB3B7;background-blend-mode:multiply}
.cabin .step{position:absolute;left:50%;transform:translateX(-50%);bottom:14px;width:40%;height:9px;background:#6F787C;border:3px solid #101316;z-index:1}
@media (max-width:900px){.cabin .step{display:none}}
.stks{position:absolute;inset:70px 0 30px 0}
.stk{position:absolute;max-width:128px;transition:opacity .2s;border:2px solid #101316;padding:8px 10px 9px;font:800 14.5px/1.05 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;text-align:left;cursor:pointer;box-shadow:3px 3px 0 rgba(0,0,0,.28),0 0 0 3px transparent,0 0 0 7px transparent;color:#101316}
.stk b{display:block;font:600 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;margin-bottom:5px;opacity:.7}
.stk[aria-pressed="true"]{box-shadow:3px 3px 0 rgba(0,0,0,.28),0 0 0 3px #101316,0 0 0 7px #F4F4EF}
.stk:focus-visible{outline:3px solid var(--focus);outline-offset:3px}
.stk{max-width:124px}
.st-yel{background:#FBB401;top:0;left:3%;transform:rotate(-6deg)}
.st-red{background:#E0442F;color:#fff;top:-3%;right:3%;transform:rotate(5deg);border-radius:50%;width:112px;height:112px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:14px}
.st-wht{background:#F4F4EF;top:25%;left:4%;transform:rotate(-2deg)}
.st-tape{background:#E6D9AE;top:50%;left:2%;transform:rotate(3deg);border-left:0;border-right:0;clip-path:polygon(0 0,100% 0,96% 18%,100% 36%,95% 54%,100% 72%,96% 88%,100% 100%,0 100%,4% 82%,0 64%,5% 46%,0 28%,4% 12%);padding-left:16px;padding-right:16px}
.st-haz{background:#FBB401;top:76%;left:5%;transform:rotate(4deg);border-left:10px solid #101316}
.st-oct{background:#101316;top:27%;right:3%;transform:rotate(-3deg);width:112px;height:112px;border:0;clip-path:polygon(29% 0,71% 0,100% 29%,100% 71%,71% 100%,29% 100%,0 71%,0 29%);isolation:isolate;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:4px 14px 24px;box-shadow:none}
.st-oct::before{content:"";position:absolute;inset:3px;z-index:-1;background:#F07A1A;clip-path:polygon(29% 0,71% 0,100% 29%,100% 71%,71% 100%,29% 100%,0 71%,0 29%)}
.st-blu{background:#2462B0;color:#fff;top:55%;right:3%;transform:rotate(2deg)}
.st-grn{background:#3FAE6A;top:78%;right:5%;transform:rotate(-4deg)}
.st-note{background:#FFF08A;top:40%;left:50%;transform:translateX(-50%) rotate(-3deg);border-color:#C9B84A;box-shadow:3px 4px 0 rgba(0,0,0,.22);clip-path:polygon(0 0,100% 0,100% 80%,84% 100%,0 100%)}
.st-oct[aria-pressed="true"],.st-tape[aria-pressed="true"],.st-note[aria-pressed="true"]{filter:drop-shadow(3px 3px 0 #101316)}
.stk.seen::after{content:"Answered";position:absolute;right:-6px;bottom:-9px;transform:rotate(-8deg);background:#101316;color:#F4F4EF;font:700 8px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;padding:3px 5px}
.st-oct.seen::after,.st-tape.seen::after,.st-note.seen::after,.st-red.seen::after{right:auto;left:50%;bottom:4px;transform:translateX(-50%) rotate(-8deg)}
.st-red.seen::after{bottom:-10px}.st-oct.seen::after{bottom:13px;transform:translateX(-50%) rotate(-3deg);font-size:7.5px;padding:3px 4px}
.st-tape,.st-note{padding-bottom:26px}
@media (min-width:901px) and (max-width:1280px){.office{grid-template-columns:minmax(0,1.3fr) minmax(0,1fr)}.stk{max-width:106px;font-size:13px;padding:6px 8px 7px}.stk b{margin-bottom:3px}
 .st-red{width:96px;height:96px;padding:10px}.st-oct{width:100px;height:100px;padding:4px 11px 22px}.st-oct.seen::after{bottom:11px}.st-tape,.st-note{padding-bottom:22px}.door{width:30%}}
.stk:hover:not([aria-pressed="true"]){filter:brightness(1.06)}
.ans:not([hidden]){animation:ans-in .28s ease-out}
@keyframes ans-in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){.ans:not([hidden]){animation:none}}
.ans .lead{font-weight:700;font-size:18px;line-height:1.35;margin-bottom:16px;padding:2px 0 2px 14px;border-left:6px solid #FBB401}
.ans p.pr{display:flex;align-items:stretch;border:2px solid var(--ink);box-shadow:3px 3px 0 var(--ink);max-width:none}
.ans p.pr span{flex:none;display:flex;align-items:center;font:700 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;background:#101316;color:#FBB401;padding:0 10px}
.ans p.pr b{font-weight:400;font-size:14.5px;line-height:1.5;padding:9px 12px;background:var(--panel)}
.answers{position:relative}
.answers::after{content:"Answered";position:absolute;right:26px;bottom:74px;transform:rotate(-9deg);font:800 30px/1 "Big Shoulders Display","Arial Narrow",sans-serif;letter-spacing:.12em;text-transform:uppercase;color:#C8382A;border:4px double #C8382A;padding:6px 12px;opacity:.5;pointer-events:none}
@media (max-width:1280px){.answers::after{display:none}}
:root[data-theme="dark"] .answers::after{color:#F0604A;border-color:#F0604A;opacity:.7}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .answers::after{color:#F0604A;border-color:#F0604A;opacity:.7}}
.anext{margin-top:auto;align-self:flex-start;display:flex;gap:14px;align-items:center;font:600 11.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3)}
.anext{flex-wrap:wrap}.anext button{white-space:nowrap;font:inherit;letter-spacing:inherit;text-transform:inherit;color:#101316;background:#FBB401;border:2px solid #101316;padding:9px 12px;cursor:pointer;box-shadow:3px 3px 0 rgba(0,0,0,.25)}
.anext button:hover,.anext button:focus-visible{background:#FFC93A}
.office:not(.js) .anext{display:none}
.answers{background:var(--panel);padding:22px 24px;display:flex;flex-direction:column;gap:18px}
.ans .ah span{white-space:nowrap}.ans .ah{display:flex;gap:12px;justify-content:space-between;background:#101316;color:#FBB401;font:600 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;padding:8px 10px}
.ans h3{margin:14px 0 10px;font:800 28px/1.02 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.ans p{margin:0;color:var(--ink);font-size:15px;max-width:62ch}
.ans p.ev{margin-top:12px;font:500 11.5px/1.5 "Martian Mono",ui-monospace,monospace;color:var(--ink-3)}
.office:not(.js) .cabin{display:none}.office:not(.js){grid-template-columns:1fr}
@media (max-width:900px){.office{grid-template-columns:1fr}.cabin{border-right:0;border-bottom:3px solid var(--ink);min-height:0;padding:70px 14px 34px}
 .stks{position:relative;inset:auto;display:flex;flex-wrap:wrap;gap:16px;justify-content:center;align-items:center;z-index:1}
 .stk{position:relative;inset:auto!important;top:auto;left:auto;right:auto;bottom:auto}
 .door{display:none}
 .stks{display:grid!important;grid-template-columns:1fr 1fr;gap:12px}.stk{max-width:none;width:auto!important;height:auto!important;border-radius:0!important;transform:none!important;clip-path:none!important;filter:none!important;border:2px solid #101316!important;top:auto!important;left:auto!important;right:auto!important}
 .stk.seen::after{left:auto!important;right:-6px!important;bottom:-9px!important;transform:rotate(-8deg)!important}
 .st-oct{background:#F07A1A}.st-oct::before{display:none}.st-oct:not([aria-pressed="true"]){box-shadow:3px 3px 0 rgba(0,0,0,.28)}}
.report{border:2px solid var(--ink);background:var(--panel)}
.report .rh{display:flex;flex-wrap:wrap;justify-content:space-between;gap:6px 16px;padding:10px 16px;background:#101316;color:#FBB401;font:600 11px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase}
.query{border-top:1px solid var(--line)}
.query:first-of-type{border-top:0}
.query summary{list-style:none;display:grid;grid-template-columns:96px minmax(0,1fr) 28px;gap:14px;align-items:center;padding:16px;cursor:pointer}
.query summary::-webkit-details-marker{display:none}
.query summary b{font:600 10.5px/1.2 "Martian Mono",monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.query summary b em{display:block;font:800 26px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;font-style:normal;color:var(--brand);letter-spacing:0;margin-top:2px}
.query summary span{font:700 19px/1.3 "Public Sans",system-ui,sans-serif}
.query summary i{font-style:normal;width:28px;height:28px;display:flex;align-items:center;justify-content:center;border:2px solid var(--ink);font:700 16px/1 "Public Sans",sans-serif}
.query summary i::before{content:"+"}
.query[open] summary i{background:var(--hivis);border-color:#101316;color:#101316}
.query[open] summary i::before{content:"\2212"}
.query .resp{display:grid;grid-template-columns:96px minmax(0,1fr) 28px;gap:14px;padding:0 16px 18px}
.query .resp>b{font:600 10.5px/1.6 "Martian Mono",monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.query .resp p{margin:0;color:var(--ink);font-size:15px;max-width:72ch}
.query .resp p.ev{margin-top:10px;font:500 11.5px/1.5 "Martian Mono",ui-monospace,monospace;color:var(--ink-3)}
.steps{list-style:none;margin:0 0 18px;padding:0;display:grid;gap:20px;counter-reset:s}
.steps>li{display:grid;grid-template-columns:48px minmax(0,1fr);gap:14px;align-items:start;counter-increment:s}
.steps>li::before{content:counter(s,decimal-leading-zero);font:800 30px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;color:var(--brand)}
.steps>li>div{min-width:0}
.steps h3{margin:2px 0 6px;font:700 16px/1.35 "Public Sans",sans-serif}
.steps p{margin:0 0 10px;color:var(--ink-2)}
/* requirements: my setup, what is not supported, and how to make it yours */
.req{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(0,1fr);gap:22px;margin-bottom:18px}
.req h3{margin:0 0 12px;font:800 24px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.req h3 small{font:700 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;vertical-align:middle;margin-left:8px;padding:5px 7px;background:#3FAE6A;color:#101316}
.req h4{margin:18px 0 8px;font:700 11px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.rmine{border:3px solid var(--ink);background:var(--panel);padding:18px 20px 20px}
/* the plant register: every tool on a hanging inspection tag, notched at the top and punched for its tie; they swing in once */
.ptags{list-style:none;margin:6px 0 0;padding:0;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));grid-auto-flow:row dense;gap:18px 14px}
.ptag{position:relative;display:grid;grid-template-columns:40px minmax(0,1fr);grid-template-rows:auto auto;column-gap:10px;align-items:center;padding:16px 10px 10px;
 background:var(--panel);border:2px solid var(--ink);border-radius:10px 10px 2px 2px;box-shadow:3px 3px 0 rgba(0,0,0,.22);
 transform-origin:50% 0;transform:rotate(-.8deg);transition:transform .25s}
.ptag:nth-child(even){transform:rotate(.7deg)}.ptag:nth-child(3n){transform:rotate(-.3deg)}
.ptag::before{content:"";position:absolute;left:50%;top:4px;width:8px;height:8px;margin-left:-4px;border-radius:50%;background:var(--ground);border:2px solid var(--ink)}
.ptag::after{content:"";position:absolute;right:0;top:0;bottom:0;width:6px;background:#3FAE6A;border-left:2px solid var(--ink);border-radius:0 8px 0 0}
.ptag:hover{transform:rotate(0) translateY(-2px)!important}
.ptag .lg{grid-row:1/span 2;width:40px;height:40px;display:grid;place-items:center;border:2px solid var(--ink);background:#fff}
.ptag .lg svg{width:24px;height:24px}.ptag .lg.mono{background:var(--ink)}.ptag .lg.mono svg{fill:var(--ground)}
.ptag .lg.img{overflow:hidden}.ptag .lg.img img{display:block;width:100%;height:100%}.ptag .lg .pi{fill:#111}
.ptag b{align-self:end;font:800 17px/1.05 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;padding-right:8px}
.ptag>span:not(.lg){align-self:start;font:600 9.5px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3);padding-right:8px}
.ptag.pb{grid-column:1/-1;background:#FBB401;color:#101316}.ptag.pb span{color:#3A3000}.ptag.pb::before{background:#FBB401}
.rmine.js:not(.live) .ptag{opacity:0;transform:translateY(-14px) rotate(-7deg)}
.rmine.js .ptag{transition:transform .5s cubic-bezier(.3,1.6,.5,1) calc(var(--i) * 45ms),opacity .3s calc(var(--i) * 45ms)}
@media (max-width:1100px){.ptags{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:560px){.ptags{gap:14px 10px}.ptag{grid-template-columns:34px minmax(0,1fr);column-gap:8px;padding:19px 8px 9px}.ptag .lg{width:34px;height:34px}.ptag .lg svg{width:20px;height:20px}.ptag b{font-size:15px}.ptag span{font-size:8.5px}}
@media (prefers-reduced-motion:reduce){.ptag,.rmine.js .ptag{transition:none;transform:none}}
.rlist{list-style:none;margin:0;padding:0;display:grid;gap:0}
.rlist li{display:grid;grid-template-columns:26px 130px minmax(0,1fr);gap:10px;align-items:baseline;padding:9px 0;border-top:1px dashed var(--line);font-size:14.5px}
.rlist li:first-child{border-top:0}
.rlist li::before{content:"\2713";display:grid;place-items:center;width:20px;height:20px;background:#3FAE6A;color:#101316;font:800 13px/1 "Public Sans",sans-serif;border:1.5px solid #101316;align-self:center}
.rlist li span{color:var(--ink-2)}
.ropt li::before{content:"+";background:var(--panel);color:var(--ink);border-color:var(--ink)}
.rside{display:flex;flex-direction:column;gap:18px}
.rno,.ryours{border:3px solid var(--ink);padding:16px 18px 18px}
.rno{background:repeating-linear-gradient(-45deg,rgba(224,68,47,.08) 0 10px,transparent 10px 20px),var(--panel)}
.rno h3{color:#C42B1C}.rno h3::before{content:"";display:inline-block;width:16px;height:16px;margin-right:9px;border-radius:50%;border:3px solid #C42B1C;background:linear-gradient(45deg,transparent 44%,#C42B1C 44% 56%,transparent 56%);vertical-align:-1px}
:root[data-theme="dark"] .rno h3{color:#FF7A66}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .rno h3{color:#FF7A66}}
.ryours{background:#1E7B4A;color:#F4F4EF;border-color:#101316}
.rno p,.ryours p{margin:0;font-size:14.5px;line-height:1.55}
.rfork{display:inline-block;margin-top:14px;padding:9px 13px;background:#FBB401;color:#101316;border:2px solid #101316;font:700 12px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.06em;text-transform:uppercase;text-decoration:none;box-shadow:3px 3px 0 rgba(0,0,0,.3)}
.rfork:hover,.rfork:focus-visible{background:#FFC93A}
.rmore{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px 12px;align-items:center;padding:16px 18px;border:3px solid var(--ink);background:var(--panel);color:var(--ink);text-decoration:none;box-shadow:4px 4px 0 var(--ink);transition:transform .15s,box-shadow .15s}
.rmore b{font:800 22px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}.rmore span{grid-column:1;font-size:13.5px;color:var(--ink-2)}
.rmore i{grid-row:1/span 2;grid-column:2;font:800 26px/1 "Public Sans",sans-serif;font-style:normal;width:44px;height:44px;display:grid;place-items:center;background:#FBB401;color:#101316;border:2px solid #101316}
.rmore:hover,.rmore:focus-visible{transform:translate(-2px,-2px);box-shadow:6px 6px 0 var(--ink)}
@media (max-width:900px){.req{grid-template-columns:minmax(0,1fr)}}
@media (max-width:560px){.rlist li{grid-template-columns:26px minmax(0,1fr)}.rlist li span{grid-column:2}}
.byhand{border:1px solid var(--line);background:var(--panel);padding:12px 16px;margin-top:4px}
.byhand summary{cursor:pointer;font:600 12px/1.4 "Martian Mono",ui-monospace,monospace;letter-spacing:.06em;color:var(--ink-2)}
.byhand p{color:var(--ink-2);margin:12px 0 10px}
.gaps{margin-top:28px}
/* install, in full: what you need, and what the setup lays out */
.inst{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(0,1fr);gap:22px;margin-bottom:16px;align-items:start}
.isteps{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:0;border-left:3px solid var(--ink)}
.isteps li{display:grid;grid-template-columns:38px minmax(0,1fr);gap:14px;padding:0 0 22px}
.isteps li:last-child{padding-bottom:0}
.isteps .in{margin-left:-20px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;background:var(--hivis);color:#101316;border:2px solid #101316;font:800 20px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif}
.isteps h4{margin:6px 0 10px;font:800 21px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.isteps p{margin:10px 0 0;font-size:14px;color:var(--ink-2);max-width:62ch}
.ineed{position:relative;border:2px solid var(--line);padding:18px 16px 16px}
.ialt{margin:16px 0 0;font-size:13.5px;color:var(--ink-2)}
@media (max-width:1000px){.inst{grid-template-columns:minmax(0,1fr)}}
.notice.gaps{background:var(--panel);border:2px solid var(--ink);color:var(--ink)}.notice.gaps>b{background:var(--ink);color:var(--ground)}.notice.gaps>div{color:var(--ink);font-weight:500}
.inst>div{border:1px solid var(--line);background:var(--panel);padding:18px 18px 16px;position:relative}
.ineed h3{position:absolute;top:-9px;left:12px;margin:0;background:var(--ground);padding:0 6px;font:600 10.5px/18px "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink)}
.ineed ul{list-style:none;margin:4px 0 0;padding:0;display:flex;flex-direction:column;gap:10px}
.ineed li{display:grid;grid-template-columns:14px minmax(0,1fr);gap:10px;font-size:14.5px}
.ineed li::before{content:"";width:9px;height:9px;transform:rotate(45deg);background:var(--hivis);border:1.5px solid #101316;margin-top:6px}
.ineed li span{color:var(--ink-2)}
.tree{margin:4px 0 0;font:500 12px/1.75 "Martian Mono",ui-monospace,monospace;color:var(--ink);white-space:pre;overflow-x:auto}
.tree i{font-style:normal;color:var(--ink-3)}
.treelink{display:inline-block;margin-top:12px;font:600 11.5px/1.4 "Martian Mono",ui-monospace,monospace;color:var(--ink)}
.upd{display:grid;grid-template-columns:minmax(0,auto) minmax(0,1fr);gap:14px;align-items:center;margin-bottom:16px}
.upd p{margin:0;color:var(--ink-2);font-size:14.5px}
/* see it: one card per sheet of the site */
.see{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}
.card{display:flex;flex-direction:column;background:var(--panel);border:1px solid var(--line);text-decoration:none;color:inherit}
.card:hover{border-color:var(--ink)}
.card .sh{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:9px 14px;border-bottom:1px solid var(--line);font:600 10px/1 "Martian Mono",monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.card .sh b{font:800 20px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;letter-spacing:0;color:var(--brand)}
/* each preview is a viewing window cut in the hoarding: a bolted frame; on hover the view pans slowly down the sheet */
.card .shot{position:relative;display:block;aspect-ratio:16/11;overflow:hidden;container-type:size;background:var(--panel-2);border:7px solid #2A3238;border-width:7px 7px 9px;box-shadow:inset 0 0 0 2px #101316}
.card .shot img{display:block;width:100%;height:auto;transform:translateY(0);transition:transform .9s cubic-bezier(.3,.7,.3,1)}
.card:hover .shot img,.card:focus-visible .shot img{transform:translateY(calc(-100% + 100cqh));transition:transform 6s cubic-bezier(.45,.05,.4,1)}
.card .shot .bolts{position:absolute;inset:0;pointer-events:none;background:radial-gradient(circle at 7px 7px,#9AA4A8 0 2.5px,#101316 3px,transparent 3.5px),radial-gradient(circle at calc(100% - 7px) 7px,#9AA4A8 0 2.5px,#101316 3px,transparent 3.5px),radial-gradient(circle at 7px calc(100% - 7px),#9AA4A8 0 2.5px,#101316 3px,transparent 3.5px),radial-gradient(circle at calc(100% - 7px) calc(100% - 7px),#9AA4A8 0 2.5px,#101316 3px,transparent 3.5px);box-shadow:inset 0 6px 12px rgba(0,0,0,.25)}
.card .shot::after{content:"Look inside";position:absolute;left:8px;bottom:8px;font:700 9px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;background:#FBB401;color:#101316;padding:4px 6px;border:1.5px solid #101316;transition:opacity .3s}
.card:hover .shot::after,.card:focus-visible .shot::after{opacity:0}
@media (hover:none){.card .shot::after{display:none}}
@media (prefers-reduced-motion:reduce){.card .shot img,.card:hover .shot img{transition:none;transform:none}}
.card .shot .pd{display:none}
:root[data-theme="dark"] .card .shot .pl{display:none}:root[data-theme="dark"] .card .shot .pd{display:block}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .card .shot .pl{display:none}:root:not([data-theme="light"]) .card .shot .pd{display:block}}
.card .cb{padding:14px 14px 16px;display:flex;flex-direction:column;gap:8px}
.closer{margin-top:56px;border:3px solid var(--ink);background:var(--panel)}
.closer>.haz{height:14px}
.closer .cl{display:grid;grid-template-columns:auto minmax(0,1fr);gap:24px;padding:28px 30px 30px;align-items:start}
.closer .cl>.mark{height:72px;width:auto}
.closer h2{margin:0 0 8px;font:800 clamp(34px,4vw,56px)/.95 "Big Shoulders Display","Arial Narrow",Impact,sans-serif;text-transform:uppercase}
.closer p{margin:0 0 16px;color:var(--ink-2);font-size:15.5px}
.closer .cmdline{max-width:640px}
.closer .clstep{display:flex;align-items:center;gap:8px;margin:14px 0 6px;font:700 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.closer .clstep b{display:grid;place-items:center;width:20px;height:20px;background:#FBB401;color:#101316;border:2px solid #101316;font-size:11px}
.closer .gh{margin-top:14px;max-width:640px;display:flex;align-items:center;gap:12px;padding:12px 14px;border:2px solid var(--ink);color:var(--ink);text-decoration:none}
.closer .gh svg{width:26px;height:26px;flex:none}.closer .gh span{display:flex;flex-direction:column;gap:3px;min-width:0}
.closer .gh b{font:600 13px/1.3 "Martian Mono",ui-monospace,monospace}.closer .gh small{font:500 11px/1.2 "Martian Mono",ui-monospace,monospace;color:var(--ink-3)}
.closer .gh i{margin-left:auto;font-style:normal;font:600 16px/1 "Martian Mono",ui-monospace,monospace}
.closer .gh:hover,.closer .gh:focus-visible{border-color:var(--hivis);box-shadow:inset 4px 0 0 var(--hivis)}
.closer .clnext{display:inline-block;margin-top:14px;font:600 11.5px/1.4 "Martian Mono",ui-monospace,monospace;color:var(--ink)}
@media (max-width:720px){.closer .cl{grid-template-columns:minmax(0,1fr);padding:20px 16px}.closer .cl>.mark{height:52px;width:auto}}
.card .cb>b{font:800 24px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.card .cb>span{color:var(--ink-2);font-size:14px}
.card em{align-self:flex-start;font:600 9.5px/1 "Martian Mono",monospace;letter-spacing:.12em;text-transform:uppercase;font-style:normal;background:var(--panel-2);border:1px solid var(--line);padding:4px 6px;color:var(--ink-2)}
@media (max-width:1000px){
 .track{grid-template-columns:1fr;border-top:0;border-left:3px solid var(--ink);margin-left:8px}

 .once{margin-top:16px}
 .phs{position:relative;padding:12px 0 14px 22px}
 .phs .mk,.phs.word .mk{position:absolute;left:-9px;top:15px;margin:0}
 .phs.word .mk{left:-10px}
 .phs .vb{margin-top:0}
 .loop{margin-top:16px;padding:0}
 .loop .track{margin-left:40px;padding:0}
 .loop::before{right:auto;width:40px;top:20px;bottom:46px;border:3px solid var(--ink);border-right:0}
 .loop::after{display:none}
 .loop .cv-down,.loop .cv-left{display:none}
 .loop .cv-up{top:auto;bottom:40%}
 .loop .ret{position:static;transform:none;display:block;margin:10px 0 0 0;padding:0;white-space:normal;background:none}
}
@media (max-width:1100px){.pillars,.carry{grid-template-columns:repeat(2,minmax(0,1fr))}.clock{grid-template-columns:repeat(3,minmax(0,1fr));row-gap:18px}.board .bb{grid-template-columns:1fr}.access{border-left:0;border-top:3px solid var(--ink)}.rack,.see{grid-template-columns:repeat(2,minmax(0,1fr))}.inst{grid-template-columns:1fr}}
@media (max-width:720px){
 .wrap{padding:0 16px}
 .board{margin-top:16px}
 .board .bh{grid-template-columns:1fr;gap:10px;padding:18px 16px}
 .jhw{order:-1;margin:0 -8px}
 .jh{min-height:230px}
 .jhc{margin:2px 0 14px}
 .board .bh .mark{display:none}
 .board .bh .mark{height:44px;width:auto}
 .roster>div{grid-template-columns:36px minmax(0,1fr);gap:2px 12px;padding:11px 16px}
 .roster .ri{width:36px;height:36px;grid-row:span 2}
 .access{padding:18px 16px}
 .sec{padding-top:48px}
 .pillars,.carry{grid-template-columns:1fr}
 .pillars{padding:22px 16px 24px;gap:26px}
 .clock{grid-template-columns:1fr;border-top:0;border-left:3px solid var(--ink);padding-left:18px}
 .ck::before{top:20px;left:-28px}
 .chain{grid-template-columns:1fr}
 .board .sub{font-size:16px}
 .rack,.see{grid-template-columns:1fr}
 .upd{grid-template-columns:1fr}
 .query summary,.query .resp{grid-template-columns:1fr 28px}
 .query summary b{grid-column:1/-1}
 .query .resp>b{display:none}
 .steps>li{grid-template-columns:1fr;gap:4px}
 .cmdline code{white-space:normal;overflow-wrap:break-word;font-size:12px;line-height:1.5;padding:12px}
}
"""

LIST_CSS = r"""
.wrap{max-width:1080px;margin:0 auto;padding:0 32px}
.lhead{padding:40px 0 30px}
.lhead h1{margin:12px 0 14px;font:800 clamp(44px,7vw,80px)/.9 "Big Shoulders Display","Arial Narrow",Impact,sans-serif;text-transform:uppercase}
.lhead .lede{max-width:66ch;color:var(--ink-2);margin:0;font-size:17px}
.grp{margin-top:40px;scroll-margin-top:16px}
.gh{border-bottom:3px solid var(--ink);padding-bottom:8px;margin-bottom:6px;display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 16px}
.gh span{font-size:14px;color:var(--ink-3)}
.gh h2{margin:4px 0 0;font:800 clamp(24px,3.4vw,32px)/1.05 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase}
.grp ul{list-style:none;margin:0;padding:0}
.row{display:grid;grid-template-columns:52px 230px minmax(0,1fr);gap:14px;align-items:baseline;padding:11px 8px;border-bottom:1px solid var(--line-2);text-decoration:none;color:inherit}
.row:hover{background:var(--panel)}
.row b{font:800 22px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;text-align:center;padding:4px 0 2px}
.row b.on{background:var(--hivis);color:#101316}
.row .ki{width:32px;height:32px;padding:3px;justify-self:center;background:#F4F4EF;border:2px solid #101316;align-self:center}
.row .st{display:block;margin-top:3px;font:500 11px/1.2 "Public Sans",system-ui,sans-serif;color:var(--ink-3);letter-spacing:0}
.find{display:flex;align-items:center;gap:12px;margin-top:22px;max-width:640px;border:2px solid var(--ink);background:var(--panel);padding:0 0 0 14px}
.find span{font:700 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-3)}
.find input{flex:1;min-width:0;border:0;background:none;color:var(--ink);font:500 15px/1 "Public Sans",system-ui,sans-serif;padding:13px 0;outline:none}
.find:focus-within{outline:3px solid var(--focus);outline-offset:2px}
.find output{font:600 11px/1 "Martian Mono",ui-monospace,monospace;color:var(--ink-3);padding-right:12px;white-space:nowrap}
.none{margin:30px 0;font-size:15px;color:var(--ink-2)}
.grp[hidden]{display:none}
.row .nm{font:600 14px/1.3 "Martian Mono",ui-monospace,monospace;overflow-wrap:anywhere}
.row .bl{color:var(--ink-2);font-size:14.5px}
.row em{font:600 9.5px/1 "Martian Mono",monospace;letter-spacing:.12em;text-transform:uppercase;font-style:normal;color:var(--c);border:1px solid var(--c);padding:4px 6px}
@media (max-width:720px){
 .wrap{padding:0 16px}
 .row{grid-template-columns:44px minmax(0,1fr);gap:4px 12px}
 .row .ki{width:28px;height:28px}
 .row b{grid-row:span 2}
 .row em{display:none}
}
"""

REPO_CSS = r"""
.wrap{max-width:1180px;margin:0 auto;padding:0 32px}
.rhead{padding:40px 0 22px}
.rhead h1{margin:12px 0 14px;font:800 clamp(44px,7vw,80px)/.9 "Big Shoulders Display","Arial Narrow",Impact,sans-serif;text-transform:uppercase}
.rhead .lede{max-width:70ch;color:var(--ink-2);margin:0;font-size:17px}
.rhead .mode-note{max-width:70ch;margin:10px 0 0;color:var(--ink-3);font-size:14px}
.modes{display:inline-flex;border:2px solid var(--ink);margin:6px 0 18px}
.modes button{font:800 17px/1 "Big Shoulders Display","Arial Narrow",sans-serif;letter-spacing:.04em;text-transform:uppercase;padding:12px 18px 10px;border:0;background:transparent;color:var(--ink-2);cursor:pointer}
.modes button+button{border-left:2px solid var(--ink)}
.modes button[aria-pressed="true"]{background:var(--hivis);color:#101316}
.rp{display:grid;grid-template-columns:minmax(0,1fr);gap:16px}
.bar2{display:flex;flex-wrap:wrap;align-items:center;gap:10px 18px;margin:0 0 16px}
.bar2 .modes{margin:0}
.bar2 .never{flex:1;min-width:280px;margin:0}
.fp{display:grid;grid-template-columns:minmax(0,2.3fr) minmax(0,1fr);gap:10px;padding:10px}
.fp .side{display:flex;flex-direction:column;gap:10px}
@media (max-width:1450px) and (min-width:981px){.fp{grid-template-columns:1fr}.fp .side{flex-direction:row;align-items:flex-start}.fp .side>.room{flex:1 1 0;min-width:0}}
.room{border:1.5px solid var(--ink-3);background:var(--ground)}
.room.top{border:2px solid var(--ink)}
.room .rb{padding:4px 0 6px}
.room .rb.grid{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr) minmax(0,1fr);grid-auto-flow:row dense;gap:10px;padding:10px}
.room .rb.grid .loose{border:1px dashed var(--line);padding:4px 0}
.room .span2{grid-row:span 2}
.room.sub{align-self:start}
.nd.rh{border-bottom:1px solid var(--line);font-weight:700}
.room.top>.nd.rh{border-bottom:2px solid var(--ink);font:700 13.5px/1.3 "Martian Mono",ui-monospace,monospace;padding-top:6px;padding-bottom:6px}
.room.top>.nd.rh .nm{font:inherit}
.dwg{border:2px solid var(--ink);background:var(--panel)}
.dwg .dh{display:flex;flex-wrap:wrap;justify-content:space-between;gap:4px 10px;padding:9px 14px;border-bottom:2px solid var(--ink);font:600 10.5px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-2)}
.dwg .dh b{color:var(--ink)}
.dwg ul{list-style:none;margin:0;padding:8px 0}
.nd{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;align-items:center;width:100%;text-align:left;border:0;border-left:4px solid transparent;background-color:transparent;color:var(--ink);cursor:pointer;padding:3px 10px 3px calc(8px + var(--i,0) * 16px);font:500 12.5px/1.35 "Martian Mono",ui-monospace,monospace}
.nd .nm{overflow-wrap:break-word}
.nd.dir .nm{font-weight:600}
.nd.file .nm{color:var(--ink-2)}
.nd.moment .nm{font-family:"Public Sans",system-ui,sans-serif;font-weight:600;font-size:14px}
.nd:hover{background-color:var(--ground)}
.nd[aria-pressed="true"]{border-left-color:var(--hivis);background-color:var(--ground)}
.wh{font:500 11px/1 "Martian Mono",ui-monospace,monospace;color:var(--ink-3);white-space:nowrap}
.wh.w-you{background:var(--hivis);color:#101316;font:600 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;padding:4px 6px 3px}
.inc{padding:0 14px 6px calc(36px + var(--d) * 22px);font:500 11px/1.5 "Martian Mono",ui-monospace,monospace;color:var(--ink-3)}
.follow .nd{color:var(--ink-3)}
.follow .nd .nm{color:var(--ink-3)}
.follow .nd.was,.follow .nd.was .nm{color:var(--ink)}
.follow .nd.was{background-color:var(--panel-2)}
.follow .nd.lit{color:#101316;background-color:var(--hivis);border-left-color:#101316}
.follow .nd.lit .nm{color:#101316}
.follow .nd.lit .wh{color:#101316;background:transparent}
.follow .nd:not(.lit) .wh.w-you{background:transparent;color:var(--ink-3)}
.panel{border:2px solid var(--ink);background:var(--panel)}
.pc{display:grid;grid-template-columns:minmax(0,320px) minmax(0,1fr);gap:8px 28px;align-content:start}
.pc dl{margin:0}
.pf .nav2{max-width:560px}
.panel .ph2{padding:9px 14px;border-bottom:2px solid var(--ink);background:#101316;color:#FBB401;font:600 10.5px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase}
.panel .pb{padding:16px 18px 18px;display:flex;flex-direction:column;gap:14px}
.pc{overflow:auto;min-height:0}
.pf{flex:none;display:flex;flex-direction:column;justify-content:flex-end}
.hint{margin:0;font-size:13.5px;color:var(--ink-3)}
.hint button{display:block;font:600 11px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:.06em;background:none;border:0;padding:0;color:var(--ink);text-decoration:underline;text-underline-offset:3px;cursor:pointer;text-align:left}
.panel h2{margin:0 0 4px;font:800 30px/1 "Big Shoulders Display","Arial Narrow",sans-serif;overflow-wrap:anywhere}
.panel .pth{font:500 12px/1.4 "Martian Mono",ui-monospace,monospace;color:var(--ink-3);overflow-wrap:anywhere}
.panel dl{margin:10px 0 0;display:grid;grid-template-columns:auto minmax(0,1fr);gap:10px 14px}
.panel dt{font:600 10px/1.6 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.panel dd{margin:0;font-size:14.5px}
.panel dd a{color:var(--ink)}
.panel .steps-in{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:4px}
.panel .steps-in button{font:500 13.5px/1.35 "Public Sans",sans-serif;text-align:left;background:none;border:0;padding:0;color:var(--ink);text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:3px;cursor:pointer}
.stepno{display:grid;grid-template-columns:auto minmax(0,1fr);align-items:center;gap:12px;margin-bottom:4px}
.stepno h2{margin:0;font-size:24px}
.panel h2.long{font:600 14px/1.4 "Martian Mono",ui-monospace,monospace}
.sn{display:flex;flex-direction:column;align-items:flex-start;gap:3px}
.sn button{border:0;background:none;padding:0;color:var(--ink);font:500 14px/1.4 "Public Sans",sans-serif;text-align:left;text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:3px;cursor:pointer}
.sn button:hover{text-decoration-color:var(--hivis)}
.places{display:flex;flex-wrap:wrap;gap:4px}
.stepno b{font:800 36px/.9 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;background:var(--hivis);color:#101316;padding:4px 8px 2px}
.stepno span{font:600 11px/1 "Martian Mono",monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.ticks{display:flex;gap:2px;margin:16px 0 0;border-left:2px solid var(--ink-3);border-right:2px solid var(--ink-3);padding:0 2px}
.ticks button{flex:1;height:26px;border:0;background:var(--panel-2);color:var(--ink-3);font:700 10px "Martian Mono",monospace;cursor:pointer;padding:0}
.ticks button.past{background:var(--line);color:var(--ink-2)}
.ticks button.here{background:#FBB401;color:#101316}
.nav2{display:flex;align-items:stretch;gap:6px}
.nav2 .ticks{flex:1;margin:0}
.nav2>button{font:700 14px/1 "Public Sans",sans-serif;padding:0 12px;border:2px solid var(--ink);background:var(--ground);color:var(--ink);cursor:pointer}
.nav2>button:disabled{opacity:.4;cursor:default}
.never{margin:0 0 18px}
@media (max-width:980px){
 .wrap{padding:0 16px}
 .rp{grid-template-columns:1fr}
 .fp{grid-template-columns:1fr}
 .room .rb.grid{grid-template-columns:1fr}
 .room .span2{grid-row:auto}
 .pc{grid-template-columns:1fr}
 .panel{position:sticky}
 .panel{order:-1;top:62px;z-index:5}
 .pc{max-height:30vh}
 .nd{grid-template-columns:minmax(0,1fr);gap:3px;padding-right:12px}
 .nd .wh{justify-self:start}
}
"""

DOCKET_CSS = r"""
.page{max-width:820px;margin:0 auto;padding:24px 24px 0}
.back{display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px;margin-bottom:14px}
.back a.bk{font:600 11.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;text-decoration:none;padding:9px 12px;border:2px solid var(--ink);background:var(--panel)}
.back a.bk:hover{background:var(--hivis);color:#101316;border-color:#101316}
.crumbs{font:500 11.5px/1.4 "Martian Mono",ui-monospace,monospace;color:var(--ink-3);display:flex;gap:8px;flex-wrap:wrap}
.crumbs a{color:var(--ink-2)}
.dkt{position:relative;background:var(--panel);border:1px solid var(--line);border-top:0;display:flex;flex-direction:column}
.dkt .band{height:6px;background:var(--c)}
.dkt .punch{height:14px;background:radial-gradient(circle at 12px 7px,var(--ground) 0 3.5px,transparent 4px) 0 0/24px 14px repeat-x;border-bottom:1px dashed var(--line)}
.dkt-h{display:grid;grid-template-columns:auto minmax(0,1fr);gap:16px;padding:18px 20px 10px;align-items:start;position:relative}
.dkt .no{display:flex;flex-direction:column;align-items:center;justify-content:center;min-width:74px;padding:10px 6px 8px;background:var(--hivis);color:#101316}
.dkt .no .kib{width:52px;height:52px;padding:5px;background:#F4F4EF;border:2px solid #101316;display:block;margin-bottom:6px}
.dkt .no b{font:800 48px/.9 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;font-variant-numeric:tabular-nums}
.dkt .no span{font:600 9.5px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;margin-top:3px}
.dkt .eyebrow{font:600 10.5px/1.3 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--c);padding-right:96px}
.dkt h1{margin:6px 0 12px;font:800 clamp(44px,7vw,64px)/.9 "Big Shoulders Display","Arial Narrow",sans-serif;letter-spacing:.005em;overflow-wrap:anywhere}
.dkt .stamp{position:absolute;right:18px;top:18px;transform:rotate(4deg);border:4px double var(--c);color:var(--c);font:800 21px/1 "Big Shoulders Stencil Display","Big Shoulders Display",sans-serif;letter-spacing:.14em;text-transform:uppercase;padding:5px 10px 4px}
.dkt .lead{padding:6px 20px 18px;margin:0;font-size:18px;line-height:1.45}
.dkt .bx{margin:8px 20px 18px;border:1px solid var(--line);padding:16px 15px 13px;position:relative}
.dkt .lbl{position:absolute;top:-8px;left:10px;background:var(--panel);padding:0 6px;font:600 10.5px/16px "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--c)}
.dkt .bx>p{margin:0;font-size:14.5px;line-height:1.55}
.dkt .bx>p.sub{margin-top:8px;color:var(--ink-3);font-size:13.5px}
.dkt .says{display:flex;flex-wrap:wrap;gap:6px}
.dkt .says span{font:500 13px/1.2 "Public Sans",system-ui,sans-serif;background:var(--panel-2);border-left:3px solid var(--c);padding:6px 9px}
.dkt .says span::before{content:"\201C";color:var(--ink-3)}
.dkt .says span::after{content:"\201D";color:var(--ink-3)}
.dkt .notice{margin:4px 20px 20px}
.dkt .check{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:9px}
.dkt .check li{display:grid;grid-template-columns:18px minmax(0,1fr);gap:10px;font-size:14.5px;line-height:1.5}
.dkt .check li::before{content:"";width:14px;height:14px;border:2px solid var(--c);margin-top:3px}
.dkt .faq{margin:0}
.dkt .faq dt{font:700 15px/1.4 "Public Sans",sans-serif;padding-top:12px;border-top:1px dashed var(--line)}
.dkt .faq dt:first-child{padding-top:0;border-top:0}
.dkt .faq dd{margin:4px 0 12px;color:var(--ink-2);font-size:14.5px}
.dkt .faq dd:last-child{margin-bottom:0}
.dkt .sample>p{margin:0 0 10px;color:var(--ink-3);font-size:13.5px}
.dkt .sample pre{margin:0;background:var(--code-bg);color:var(--code-ink);padding:14px;overflow-x:auto;font:500 12.5px/1.6 "Martian Mono",ui-monospace,monospace;border:1px solid #101316}
.dkt .tape{margin:4px 20px 18px}
.dkt .tl{display:flex;justify-content:space-between;align-items:baseline;font:600 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3);margin-bottom:8px}
.dkt .tl b{color:var(--ink)}
.dkt .ts{display:flex;gap:2px;border-left:2px solid var(--ink-3);border-right:2px solid var(--ink-3);padding:0 2px}
.dkt .ts>*{flex:1;min-width:0;height:26px;display:flex;align-items:center;justify-content:center;background:var(--panel-2);color:var(--ink-3);font:700 10px "Martian Mono",ui-monospace,monospace;text-decoration:none}
.dkt .ts>.past{background:var(--line)}
.dkt .ts>.here{background:#FBB401;color:#101316}
.dkt .ts>a{color:var(--ink)}
.dkt .ts>a:hover{outline:2px solid var(--c);outline-offset:-2px}
.dkt .tn{display:flex;justify-content:space-between;gap:10px;margin-top:8px;font:600 12px "Martian Mono",ui-monospace,monospace;color:var(--ink-2)}
.dkt .tn a{text-decoration:none}
.dkt .tn a:hover{color:var(--ink)}
.dkt .tear{border-top:2px dashed var(--line);position:relative;margin-top:4px}
.dkt .tear::before,.dkt .tear::after{content:"";position:absolute;top:-8px;width:14px;height:14px;border-radius:50%;background:var(--ground);border:1px solid var(--line)}
.dkt .tear::before{left:-8px}
.dkt .tear::after{right:-8px}
.dkt .stub{padding:18px 20px 8px;display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px}
.dkt .stub h2{margin:0 0 7px;font:600 10.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
.dkt .stub h2 b{color:var(--ink);font-weight:600}
.dkt .stub ul{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:4px}
.nb{display:flex;gap:7px;align-items:baseline;font:500 12.5px/1.35 "Martian Mono",ui-monospace,monospace;border:1px solid var(--line);background:var(--ground);color:var(--ink);padding:6px 8px;text-decoration:none}
a.nb:hover{border-color:var(--c)}
.nb i{flex:none;width:8px;height:8px;border-radius:50%;background:var(--c)}
.nb.ag i{border-radius:0}
.dkt .foot{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;padding:12px 20px 16px;font:500 11.5px "Martian Mono",ui-monospace,monospace;color:var(--ink-3)}
.dkt .foot a{color:var(--ink-2)}
@media (max-width:560px){
 .page{padding:16px 16px 0}
 .dkt-h{grid-template-columns:1fr;gap:12px;padding:16px 16px 8px}
 .dkt .no{flex-direction:row;gap:8px;justify-content:flex-start;align-items:baseline;min-width:0;justify-self:start;padding:6px 10px}
 .dkt .no b{font-size:34px}
 .dkt .eyebrow{padding-right:0}
 .dkt .stamp{top:20px;right:14px;font-size:17px}
 .dkt .lead,.dkt .foot,.dkt .stub{padding-inline:16px}
 .dkt .bx,.dkt .notice,.dkt .tape{margin-inline:16px}
}

/* the card in the site's newer language: the on site / when plate, the not-for sign, a checklist you tick that stamps itself passed */
.dkt .orw{display:grid;grid-template-columns:auto minmax(0,1fr);margin:4px 20px 18px;border:2px solid var(--ink);box-shadow:3px 3px 0 var(--ink)}
.dkt .orw dt{display:flex;align-items:center;font:700 9.5px/1.2 "Martian Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;background:#101316;color:#FBB401;padding:8px 10px;white-space:nowrap}
.dkt .orw dd{margin:0;padding:9px 12px;font-size:14.5px;line-height:1.5;color:var(--ink);background:var(--panel)}
.dkt .orw dd p{margin:0}.dkt .orw dd p.sub{margin-top:6px;font-size:13px;color:var(--ink-3)}
.dkt .orw dt:not(:last-of-type){border-bottom:1px solid #3A4046}.dkt .orw dd:not(:last-of-type){border-bottom:2px solid var(--ink)}
.dkt .knot{display:flex;align-items:stretch;margin:4px 20px 20px;padding:0;border:2px solid #101316;background:#F4F4EF;color:#101316;box-shadow:3px 3px 0 #101316}
.dkt .knot i{flex:none;width:40px;display:grid;place-items:center;background:#C42B1C;border-right:2px solid #101316}
.dkt .knot i::before{content:"";width:18px;height:18px;border-radius:50%;border:3px solid #fff;background:linear-gradient(45deg,transparent 42%,#fff 42% 58%,transparent 58%)}
.dkt .knot b{display:flex;align-items:center;padding:0 10px;font:800 15px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;letter-spacing:.04em;color:#C42B1C;white-space:nowrap}
.dkt .knot span{padding:9px 12px 9px 0;font-size:14px;line-height:1.5;color:#101316}
.dkt .knot code{background:#FBB401;color:#101316}
@media (max-width:560px){.dkt .knot{flex-wrap:wrap}.dkt .knot i{min-height:36px}.dkt .knot span{flex:1 1 100%;padding:9px 12px;border-top:2px solid #101316}.dkt .orw{grid-template-columns:minmax(0,1fr)}}
.dkt .kins{position:relative}

/* the flip bar: previous and next card at the top, sticky while you read, and the arrow keys do the same */
.flip{position:sticky;top:0;z-index:6;max-width:770px;margin:0 auto 14px;display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);align-items:stretch;gap:8px;padding:8px 0;background:var(--ground)}
.flip a{display:flex;flex-direction:column;justify-content:center;gap:3px;padding:8px 12px;border:2px solid var(--ink);background:var(--panel);color:var(--ink);text-decoration:none;box-shadow:3px 3px 0 var(--ink);min-width:0;transition:transform .12s,box-shadow .12s,background .15s}
.flip a:hover,.flip a:focus-visible{transform:translate(-2px,-2px);box-shadow:5px 5px 0 var(--ink);background:#FBB401;color:#101316}
.flip a.fn{text-align:right;align-items:flex-end}
.flip small{font:700 9.5px/1 "Martian Mono",ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;color:inherit;opacity:.75}
.flip b{font:700 15px/1.2 "Martian Mono",ui-monospace,monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
.flip .fc{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;padding:0 14px;background:#101316;color:#FBB401;border:2px solid #101316}
.flip .fc b{font:800 16px/1 "Big Shoulders Display","Arial Narrow",sans-serif;text-transform:uppercase;letter-spacing:.02em}
.flip .fc span{font:700 12px/1 "Martian Mono",ui-monospace,monospace;color:#F4F4EF}
.flip .fc small{font-size:8.5px;color:#9AA29C;opacity:1;letter-spacing:.06em}
@media (max-width:900px){.flip{top:54px}}
@media (max-width:560px){.flip{grid-template-columns:1fr 1fr;padding:6px 0}.flip .fc{grid-column:1/-1;grid-row:1;flex-direction:row;gap:10px;padding:6px 10px}.flip .fc small{display:none}.flip b{font-size:13px}}
.dkt .tape .ts span{display:grid;place-items:center}
.dkt .tape .tl a{color:inherit;text-decoration:underline;text-decoration-color:#FBB401;text-decoration-thickness:2px;text-underline-offset:3px}

/* click to copy: the command and the phrases; a small "Copied" note shows at the foot of the screen */
.dkt [data-copy]{cursor:copy;transition:background .15s,outline-color .15s}
.dkt .plate code[data-copy]:hover,.dkt .says [data-copy]:hover{outline:2px solid #FBB401;outline-offset:1px}
.dkt [data-copy]:focus-visible{outline:3px solid var(--focus);outline-offset:2px}
.dkt [data-copy].copied{outline:2px solid #3FAE6A;outline-offset:1px}
.dkt .cphint{margin-left:8px;font:600 9px/1 "Martian Mono",ui-monospace,monospace;font-style:normal;letter-spacing:.08em;text-transform:none;color:var(--ink-3)}
.cptip{position:fixed;left:50%;bottom:22px;z-index:60;transform:translate(-50%,20px);opacity:0;pointer-events:none;padding:9px 14px;background:#101316;color:#FBB401;border:2px solid #FBB401;
 font:700 12px/1 "Martian Mono",ui-monospace,monospace;box-shadow:4px 4px 0 rgba(0,0,0,.35);transition:opacity .2s,transform .2s}
.cptip.on{opacity:1;transform:translate(-50%,0)}
/* a linked skill or agent, with what it does under its name */
.dkt .stub .nb{align-items:flex-start}.dkt .stub .nb i{margin-top:5px}
.dkt .stub .nb span{display:flex;flex-direction:column;gap:2px;min-width:0}
.dkt .stub .nb span b{font:600 12.5px/1.3 "Martian Mono",ui-monospace,monospace}
.dkt .stub .nb span small{font:400 12px/1.35 "Public Sans",system-ui,sans-serif;color:var(--ink-3)}
.dkt .stub{grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}
.dkt .orw dd.cby{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.dkt .orw dd.cby a{font:600 12.5px/1 "Martian Mono",ui-monospace,monospace;color:var(--ink);text-decoration:none;padding:5px 8px;border:2px solid var(--ink);background:var(--ground)}
.dkt .orw dd.cby a:hover{background:#FBB401;color:#101316;border-color:#101316}
"""

# D23: dark first on every page. A first visit opens dark whatever the device says; a choice saved with the toggle
# (foreman-theme) wins after that. Set in the head, before any style, so light never flashes first.
THEME_HEAD = '<script>(function(){var t;try{t=localStorage.getItem("foreman-theme")}catch(e){}document.documentElement.setAttribute("data-theme",t==="light"?"light":"dark")})()</script>'
OLD_THEME_HEAD = '<script>try{var t=localStorage.getItem("foreman-theme");if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t);}catch(e){}</script>'
THEME_TAIL = ATLAS_TEMPLATE[ATLAS_TEMPLATE.rindex('<script>(function(){var r=document.documentElement;'):]
_LAB = 'b.textContent=to==="dark"?"Dark":"Light";'
if THEME_TAIL.count(_LAB) != 1:
    raise SystemExit("build_site: the theme button's label code changed in the Atlas; update the site's moon and sun labels")
THEME_TAIL = THEME_TAIL.replace(_LAB, 'b.textContent=to==="dark"?"☾ Dark":"☀ Light";')
# the shell's own behaviour: the phone site plan opens and closes; "Back" returns to the exact place you came
# from when that was a page of this site (else it follows its link); a framed page follows the site's theme
SHELL_JS = r"""<script>/* the site hoist: on every sheet whose plan entry lists its sections, a cage rides the mast to the one you are on.
   Sections that are tabs follow the open tab; sections down the page follow the scroll. */
(function(){var ul=document.querySelector("nav.plan .subs");if(!ul)return;
var links=[].slice.call(ul.querySelectorAll("a[href^='#']")),tg=links.map(function(a){return document.getElementById(decodeURIComponent(a.getAttribute("href").slice(1)))});
if(links.length<2||tg.indexOf(null)>=0)return;ul.classList.add("hoisted");
var m=document.createElement("span"),c=document.createElement("span"),w=document.createElement("span");m.className="hmast";c.className="hcage";w.className="hcw";
[m,w,c].forEach(function(e){e.setAttribute("aria-hidden","true");ul.appendChild(e)});c.innerHTML='<svg viewBox="0 0 16 19"><circle class="lamp" cx="8" cy="1.8" r="1.6" stroke="#101316" stroke-width=".8"/><rect x=".75" y="3.5" width="14.5" height="14.75" fill="#FBB401" stroke="#101316" stroke-width="1.5"/><rect x="3" y="6" width="10" height="9.5" fill="#E8EDF0" stroke="#101316" stroke-width=".8"/><path d="M5.5 6v9.5M8 6v9.5M10.5 6v9.5M3 8.4h10M3 10.8h10M3 13.2h10" stroke="#101316" stroke-width=".5" opacity=".55"/></svg>';
var tabs=tg.every(function(t){return t.getAttribute("role")==="tab"}),cur=-1,raf=0;
function place(){var a=links[cur];if(!a)return;var y=a.offsetTop+(a.offsetHeight-19)/2,H=ul.clientHeight;
 c.style.transform="translateY("+y+"px)";w.style.transform="translateY("+Math.max(2,H-y-30)+"px)"}
function which(){var k=0;if(tabs){tg.forEach(function(t,i){if(t.getAttribute("aria-selected")==="true")k=i});return k}
 var line=innerHeight*.35;tg.forEach(function(t,i){if(t.getBoundingClientRect().top<=line)k=i});
 if(innerHeight+scrollY>=document.documentElement.scrollHeight-4)k=tg.length-1;return k}
function spy(){raf=0;var k=which();if(k===cur)return;var first=cur<0;if(links[cur])links[cur].classList.remove("here");cur=k;links[k].classList.add("here");
 if(first){c.style.transition=w.style.transition="none";place();void c.offsetWidth;c.style.transition=w.style.transition="";return}
 c.classList.add("moving");place()}
c.addEventListener("transitionend",function(){c.classList.remove("moving")});
function soon(){if(!raf)raf=requestAnimationFrame(spy)}
if(tabs){var mo=new MutationObserver(soon);tg.forEach(function(t){mo.observe(t,{attributes:true,attributeFilter:["aria-selected"]})})}
else addEventListener("scroll",soon,{passive:true});
links.forEach(function(a){a.addEventListener("click",function(){setTimeout(soon,60)})});
addEventListener("resize",function(){place()});c.style.opacity=w.style.opacity="0";
setTimeout(function(){spy();c.style.opacity=w.style.opacity=""},0)})();
(function(){
var site=document.querySelector(".site");
document.querySelectorAll("[data-plan]").forEach(function(b){b.addEventListener("click",function(){var o=site.classList.toggle("open");document.querySelectorAll("[data-plan]").forEach(function(x){x.setAttribute("aria-expanded",o?"true":"false")})})});
document.querySelectorAll(".plan a").forEach(function(a){a.addEventListener("click",function(){site.classList.remove("open")})});
document.addEventListener("keydown",function(e){if(e.key==="Escape")site.classList.remove("open")});
var root=function(u){return u.split("/").slice(0,3).join("/")};
document.querySelectorAll("[data-back]").forEach(function(a){a.addEventListener("click",function(e){var r=document.referrer;if(r&&root(r)===root(location.href)&&history.length>1){e.preventDefault();history.back()}})});
function sync(f){try{var d=f.contentDocument;if(!d||!d.documentElement)return;var t=document.documentElement.getAttribute("data-theme");if(t)d.documentElement.setAttribute("data-theme",t);else d.documentElement.removeAttribute("data-theme");if(!d.getElementById("site-frame")){var s=d.createElement("style");s.id="site-frame";s.textContent="[data-theme-toggle],.theme-toggle{display:none!important}"+(/atlas/.test(f.getAttribute("src"))?"header .kick{display:none!important}":"");(d.head||d.documentElement).appendChild(s)}}catch(e){}}
var frames=[].slice.call(document.querySelectorAll("iframe.frame"));
frames.forEach(function(f){f.addEventListener("load",function(){sync(f)});sync(f)});
new MutationObserver(function(){frames.forEach(sync)}).observe(document.documentElement,{attributes:true,attributeFilter:["data-theme"]});
var tabs=[].slice.call(document.querySelectorAll("[data-tab]"));
if(tabs.length){var fr=frames[0];var pick=function(k){tabs.forEach(function(t){var on=t.getAttribute("data-tab")===k;t.setAttribute("aria-selected",on?"true":"false");if(on&&fr.getAttribute("src")!==t.getAttribute("data-src"))fr.setAttribute("src",t.getAttribute("data-src"))})};
 tabs.forEach(function(t){t.addEventListener("click",function(){var k=t.getAttribute("data-tab");pick(k);history.replaceState(null,"","#"+k)})});
 pick(location.hash==="#builder"?"builder":"foreman");window.addEventListener("hashchange",function(){pick(location.hash==="#builder"?"builder":"foreman")})}
})();</script>"""
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@700;800&family=Big+Shoulders+Stencil+Display:wght@800&family=Martian+Mono:wght@400;500;600&family=Public+Sans:wght@400;500;600;700&display=swap">')
FAMILY_CODE = {"plan": "PL", "run": "RN", "inspect": "IN", "close": "CL", "kit": "KT"}


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def atlas_route() -> list[list[str]]:
    """The route exactly as the Skill Atlas draws it, read from the Atlas's own template (one list, one place)."""
    m = re.search(r"const ROUTE=(\[.*?\]);", ATLAS_TEMPLATE, re.S)
    if not m:
        raise SystemExit("build_site: ROUTE not found in wiki_graph_html.TEMPLATE")
    return json.loads(m.group(1))


def says_and_when(use: str) -> tuple[list[str], str]:
    """The reading the Atlas docket makes in its page script: the quoted trigger phrases become "Say it",
    the when-sentences without them become "When to use it"."""
    says = list(dict.fromkeys(re.findall(r'"([^"]{2,60})"', use)))[:6]
    sents = re.split(r"(?<=[.!?])\s+", use)
    when = " ".join(s for s in sents if re.search(r"\b(use (when|for|this|it)|when the|before|after|typical triggers)\b", s, re.I)) or use
    when = re.sub(r',?\s*(?:says\s+)?"[^"]*"(?:\s*\([^)]*\))?', "", when)
    when = re.sub(r"\s*,\s*,", ",", when)
    when = re.sub(r",\s*(?=[.;])", "", when)
    when = re.sub(r"\s{2,}", " ", when)
    return says, re.sub(r",\s*or\s*,", ", or", when).strip()


def not_for(text: str) -> str:
    t = re.sub(r"^Not for\s*", "", text, flags=re.I)
    return cap(re.sub(r"^Not the\s*", "the ", t, flags=re.I))


def page_path(pid: str) -> str:
    """Where a skill or agent lives under docs/ (and under docs/content/): skills/<name> or agents/<name>."""
    return pid if pid.startswith("agents/") else f"skills/{pid}"


def read_content(pid: str) -> dict:
    """docs/content/<skills|agents>/<name>.md: a small front matter, then "## It's working if" and "## Common questions"."""
    path = CONTENT / f"{page_path(pid)}.md"
    text = path.read_text(encoding="utf-8")
    meta = {}
    m = re.match(r"---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if m:
        for line in m.group(1).splitlines():
            k, _, v = line.partition(":")
            if k.strip():
                meta[k.strip()] = v.strip()
        text = text[m.end():]
    secs = {h.strip(): b for h, b in re.findall(r"^## (.+?)\n(.*?)(?=^## |\Z)", text, re.S | re.M)}
    checks = [ln[2:].strip() for ln in secs.get("It's working if", "").splitlines() if ln.startswith("- ")]
    faq = [(q.strip(), " ".join(a.split())) for q, a in re.findall(r"^### (.+?)\n(.*?)(?=^### |\Z)", secs.get("Common questions", ""), re.S | re.M)]
    if not checks or not faq:
        raise SystemExit(f"build_site: {path} needs both \"## It's working if\" and \"## Common questions\"")
    return {"meta": meta, "checks": checks, "faq": faq}


def skill_sample(skill_path: Path, spec: str) -> str:
    """The Nth fenced block under a SKILL.md heading, verbatim. spec: "<heading> | <n>"."""
    heading, _, n = spec.partition("|")
    text = skill_path.read_text(encoding="utf-8")
    m = re.search(rf"^#+ {re.escape(heading.strip())}\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    if not m:
        raise SystemExit(f"build_site: sample heading {heading.strip()!r} not in {skill_path}")
    blocks = re.findall(r"^```[^\n]*\n(.*?)^```", m.group(1), re.S | re.M)
    i = int(n.strip() or 1) - 1
    if i >= len(blocks):
        raise SystemExit(f"build_site: no block {i + 1} under {heading.strip()!r} in {skill_path}")
    return blocks[i].rstrip("\n")


def install_facts() -> tuple[str, str]:
    """SETUP.md section 1: the copy script, its two paths shown as placeholders, and the install check."""
    text = (ROOT / "SETUP.md").read_text(encoding="utf-8")
    sec = re.search(r"^## 1 .*?(?=^## 2 )", text, re.S | re.M)
    if not sec:
        raise SystemExit("build_site: SETUP.md section 1 not found")
    m = re.search(r"^```bash\n(.*?)^```", sec.group(0), re.S | re.M)
    chk = re.search(r"\*\*Check the install:\*\*\s*`([^`]+)`", sec.group(0))
    if not m or not chk:
        raise SystemExit("build_site: install script or check command not found in SETUP.md section 1")
    script = m.group(1).rstrip("\n")
    # the placeholders read as words on the site; SETUP.md may already write the package one that way
    for olds, new in ((('"/path/to/Foreman"', '"<path to the Topping Out package>"'), '"<path to the Topping Out package>"'),
                      (('"/path/to/records-repo"', '"<path to the records repo>"'), '"<path to your records repo>"')):
        hit = [o for o in olds if o in script]
        if not hit:
            raise SystemExit(f"build_site: none of {olds} in the SETUP.md install script")
        script = script.replace(hit[0], new)
    return script, chk.group(1)


def cmd(text: str) -> str:
    """A command, shown to read: one line sits in a command plate, several in a block. No Copy buttons on this
    site (the owner's word, 2026-10-07: "why would people copy from a website")."""
    if "\n" not in text:
        return f'<div class="cmdline"><code>{esc(text).replace("/", "/<wbr>")}</code></div>'
    return f'<div class="cmdbox"><pre class="cmd"><code>{esc(text)}</code></pre></div>'



def repo_plan() -> dict:
    """SETUP.md section 2, read as data: the tree under "What Foreman adds to your repo" (each line: a name,
    what it holds, who or which step creates it) and the table under "A job's files, start to finish" (each row
    tied to the tree nodes its Where cell names). Nothing here is copied by hand: the page is built from this."""
    text = (ROOT / "SETUP.md").read_text(encoding="utf-8")
    sec = re.search(r"^### What (?:Foreman|Topping Out) adds to your repo\s*\n(.*?)(?=^### )", text, re.S | re.M)
    job = re.search(r"^### A job's files, start to finish\s*\n(.*?)(?=^## )", text, re.S | re.M)
    if not sec or not job:
        raise SystemExit("build_site: SETUP.md section 2 needs 'What Foreman adds to your repo' and 'A job's files, start to finish'")
    intro = sec.group(1).split("```")[0].strip()
    block = re.search(r"^```[^\n]*\n(.*?)^```", sec.group(1), re.S | re.M).group(1).rstrip("\n").splitlines()
    # the right-hand column says who or when: a fixed few, the skills, and any moment the job table names
    moments = {re.sub(r"\s*\(.*\)|`", "", c.split("|")[1]).strip().lower()
               for c in job.group(1).splitlines() if c.strip().startswith("|") and c.count("|") == 4}
    who_re = re.compile(r"^(install|you, at setup|work order \d+|end of each job|updated with .+|/f-[\w-]+.*|"
                        + "|".join(re.escape(m) for m in sorted(moments) if m and m != "when" and not set(m) <= set("-: ")) + r")$", re.I)
    nodes, stack = [], []
    root = block[0].strip()
    for line in block[1:]:
        m = re.match(r"^([│├└─\s]*)(.*)$", line)
        depth, segs = len(m.group(1)) // 4, re.split(r"\s{2,}", m.group(2).strip())
        if len(segs) >= 2 and segs[0].endswith("/") and segs[1].endswith("/"):
            parent = stack[depth - 2]  # a line listing the folders inside its parent
            parent["includes"] = (parent["includes"] + "  " if parent["includes"] else "") + "  ".join(segs)
            continue
        name, rest = segs[0], segs[1:]
        who = rest.pop() if rest and who_re.match(rest[-1]) and (len(rest) > 1 or len(segs) == 2) else ""
        if not who and rest and re.search(r"\s(install)$", rest[-1]):  # "... helpers) install": one space in the source
            rest[-1], who = rest[-1][: -len(" install")], "install"
        stack[depth - 1:] = []
        parent_path = stack[-1]["path"] if stack else ""
        node = {"id": len(nodes), "name": name, "path": parent_path + name, "depth": depth, "dir": name.endswith("/"),
                "desc": " ".join(rest), "who": who, "includes": "", "steps": []}
        nodes.append(node)
        stack.append(node)
    rows = []
    for line in job.group(1).splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 3 or cells[0] in ("When", "") or set(cells[0]) <= set("-: "):
            continue
        when, what, where = cells
        hit = set()
        if "day folder" in where:
            hit |= {n["id"] for n in nodes if n["name"].startswith("work-sessions/")}
        for tok in re.findall(r"`([^`]+)`", where):
            exact = [n for n in nodes if n["path"] == tok or (("/" not in tok.rstrip("/")) and n["name"] == tok)]
            prefix = sorted((n for n in nodes if n["dir"] and tok.startswith(n["path"])), key=lambda n: -len(n["path"]))
            if exact:
                hit.add(exact[0]["id"])
            elif prefix and prefix[0]["path"] != "foreman/":
                hit.add(prefix[0]["id"])
            elif tok.startswith("JOB-") or (tok.endswith("/") and "/" not in tok[:-1]):
                hit |= {n["id"] for n in nodes if tok in n["name"]}  # a day-folder file the tree lists by name
        if not hit:
            raise SystemExit(f"build_site: SETUP.md job step {when!r} names no place in the repo tree")
        for i in hit:
            nodes[i]["steps"].append(len(rows))
        rows.append({"when": when, "what": what, "where": where, "nodes": sorted(hit)})
    after = job.group(1).split("\n\n")
    tail = next((p.strip() for p in reversed(after) if p.strip() and not p.strip().startswith("|")), "")
    mode = re.search(r"(In single-repo mode[^.]*\.[^.]*\.)", intro)
    return {"root": root, "nodes": nodes, "steps": rows, "mode": mode.group(1) if mode else "", "tail": tail}


JS_REPO = r'''<script>(function(){const D=__DATA__;
const dwg=document.getElementById("dwg"),ph=document.getElementById("ph2"),pb=document.getElementById("pb");
pb.innerHTML='<div class="pc" id="pc"></div><div class="pf" id="pf"></div>';const pc=document.getElementById("pc"),pf=document.getElementById("pf");
const btns=[...dwg.querySelectorAll(".nd")];let mode="explore",sel=D.nodes.findIndex(n=>n.path==="foreman/"),step=0;
if(sel<0)sel=0;
function nodeHTML(i){const n=D.nodes[i];const loc=n.kind==="moment"?D.root+D.day:D.root+n.path;
 return '<div class="pa"><h2'+(n.long?' class="long"':'')+'>'+n.name+'</h2><div class="pth">'+loc+'</div></div><dl>'+
 (n.kind==="moment"?'<dt>Files</dt><dd class="places">'+n.files.map(f=>'<code>'+f+'</code>').join(" ")+'</dd>':
  (n.desc||n.kind==="dir"?'<dt>Holds</dt><dd>'+(n.desc||"the folders listed under it")+'</dd>':''))+
 (n.who?'<dt>Made by</dt><dd>'+n.who+'</dd>':'')+
 (n.when?'<dt>When</dt><dd>'+n.when+'</dd>':'')+
 (n.steps.length?'<dt>In a job</dt><dd class="sn">'+n.steps.map(k=>'<button type="button" data-step="'+k+'">'+(k+1)+' &middot; '+D.steps[k].when+'</button>').join("")+'</dd>':'')+'</dl>'}
function stepHTML(i){const s=D.steps[i];return '<div class="pa"><div class="stepno"><b>'+String(i+1).padStart(2,"0")+'</b><h2>'+s.when+'</h2></div></div><dl>'+
 '<dt>Appears</dt><dd>'+s.what+'</dd><dt>Where</dt><dd class="places">'+s.nodes.map(k=>'<code>'+D.nodes[k].short+'</code>').join(" ")+'</dd></dl>'}
function footHTML(i){return '<div class="nav2"><button type="button" data-go="'+(i-1)+'"'+(i===0?" disabled":"")+' aria-label="Back">&larr;</button><div class="ticks">'+
 D.steps.map((x,k)=>'<button type="button" class="'+(k<i?"past":k===i?"here":"")+'" data-go="'+k+'" title="'+x.when.replace(/<[^>]+>/g,"")+'">'+(k+1)+'</button>').join("")+'</div>'+
 '<button type="button" data-go="'+(i+1)+'"'+(i===D.steps.length-1?" disabled":"")+' aria-label="Next">&rarr;</button></div>'}
const EXPLORE_FOOT='<p class="hint"><button type="button" data-follow>Follow a job, step by step &rarr;</button></p>';
// one box size, compact: the content area fits nearly every entry (the 85th percentile); the few longer ones
// scroll inside it; the foot is one row; measured once, and again only when the width or the fonts change
function size(){const m=document.createElement("div");m.className="pb";m.style.cssText="position:absolute;visibility:hidden;left:-9999px;top:0;width:"+pb.clientWidth+"px;height:auto";
 m.innerHTML='<div class="pc"></div><div class="pf"></div>';pb.parentNode.appendChild(m);const mc=m.firstChild,mf=m.lastChild;const hs=[];let hf=0;
 D.nodes.forEach((_,i)=>{mc.innerHTML=nodeHTML(i);hs.push(mc.scrollHeight)});
 D.steps.forEach((_,i)=>{mc.innerHTML=stepHTML(i);hs.push(mc.scrollHeight);mf.innerHTML=footHTML(i);hf=Math.max(hf,mf.scrollHeight)});
 mf.innerHTML=EXPLORE_FOOT;hf=Math.max(hf,mf.scrollHeight);m.remove();hs.sort((x,y)=>x-y);
 pc.style.height=hs[Math.floor((hs.length-1)*0.85)]+"px";pf.style.height=hf+"px"}
function paint(){btns.forEach(b=>{const id=+b.dataset.id;b.setAttribute("aria-pressed",mode==="explore"&&id===sel?"true":"false");
 const lit=mode==="follow"&&D.steps[step].nodes.includes(id),was=mode==="follow"&&!lit&&D.steps.slice(0,step).some(s=>s.nodes.includes(id));
 b.classList.toggle("lit",lit);b.classList.toggle("was",was)});
 dwg.classList.toggle("follow",mode==="follow");
 document.querySelectorAll("[data-mode]").forEach(m=>m.setAttribute("aria-pressed",m.dataset.mode===mode?"true":"false"));
 if(mode==="explore"){ph.textContent="What is here";pc.innerHTML=nodeHTML(sel);pf.innerHTML=EXPLORE_FOOT;
  pc.querySelectorAll("[data-step]").forEach(b=>b.addEventListener("click",()=>{mode="follow";step=+b.dataset.step;paint()}));
  pf.querySelector("[data-follow]").addEventListener("click",()=>{mode="follow";paint()})}
 else{ph.textContent="Follow a job";pc.innerHTML=stepHTML(step);pf.innerHTML=footHTML(step);
  pf.querySelectorAll("[data-go]").forEach(b=>b.addEventListener("click",()=>{step=Math.max(0,Math.min(D.steps.length-1,+b.dataset.go));paint()}))}
 pc.scrollTop=0;
 try{history.replaceState(null,"",mode==="follow"?"#follow":"#explore")}catch(e){}}
btns.forEach(b=>b.addEventListener("click",()=>{mode="explore";sel=+b.dataset.id;paint()}));
document.querySelectorAll("[data-mode]").forEach(m=>m.addEventListener("click",()=>{mode=m.dataset.mode;paint()}));
if(location.hash==="#follow")mode="follow";
size();paint();
if(document.fonts&&document.fonts.ready)document.fonts.ready.then(size);
let rz,lastW=pb.clientWidth;window.addEventListener("resize",()=>{clearTimeout(rz);rz=setTimeout(()=>{if(pb.clientWidth!==lastW){lastW=pb.clientWidth;size()}},120)});
})();</script>'''


# The jackhammer on the site board: a low-poly breaker drilling a concrete slab, built from primitives in
# Three.js (no model file). Colours follow the site's theme; reduced motion gets one still frame; it pauses
# when the board is out of view; if Three.js can't load, the box hides and the board reads as before.
TOWER_JS = r"""<script>(function(){
var box=document.getElementById("jh");if(!box)return;
if(!window.THREE){box.style.display="none";return}
var T=THREE,root=document.documentElement;
var R=new T.WebGLRenderer({antialias:true,alpha:true});
R.setPixelRatio(Math.min(2,window.devicePixelRatio||1));R.shadowMap.enabled=true;R.shadowMap.type=T.PCFSoftShadowMap;
R.domElement.style.opacity="0";R.domElement.style.transition="opacity .7s";
var sky=document.createElement("canvas"),sg=sky.getContext("2d");box.appendChild(sky);box.appendChild(R.domElement);
var STARS=[];for(var si=0;si<46;si++)STARS.push([Math.random(),Math.random()*0.62,0.5+Math.random()*1.3,Math.random()*6]);
var cap=document.getElementById("jcap"),CAPS=__CAPS__,capAt=-1;
var S=new T.Scene(),C=new T.PerspectiveCamera(30,1,0.1,200);
function isDark(){var t=root.getAttribute("data-theme");if(t==="dark"||t==="light")return t==="dark";return !!(window.matchMedia&&matchMedia("(prefers-color-scheme: dark)").matches)}
function std(o){return new T.MeshStandardMaterial(Object.assign({roughness:0.82,metalness:0.05,flatShading:true},o||{}))}
function canvasTex(w,h,fn){var c=document.createElement("canvas");c.width=w;c.height=h;fn(c.getContext("2d"),w,h);var t=new T.CanvasTexture(c);t.anisotropy=4;return t}
function speckle(g,w,h,base,light,dark){g.fillStyle=base;g.fillRect(0,0,w,h);for(var i=0;i<w*h/22;i++){g.fillStyle=Math.random()<0.5?light:dark;g.globalAlpha=0.1+Math.random()*0.2;var s=1+Math.random()*1.8;g.fillRect(Math.random()*w,Math.random()*h,s,s)}g.globalAlpha=1}

/* ---------- textures that follow the theme ---------- */
var conCv=document.createElement("canvas");conCv.width=conCv.height=128;var conTex=new T.CanvasTexture(conCv);
var winCv=document.createElement("canvas");winCv.width=winCv.height=128;var winTex=new T.CanvasTexture(winCv);
var winEm=canvasTex(128,128,function(g){g.fillStyle="#000";g.fillRect(0,0,128,128);g.fillStyle="#ffd28a";g.fillRect(30,34,68,58);g.fillStyle="#000";g.fillRect(62,34,4,58);g.fillRect(30,60,68,3)});
var padCv=document.createElement("canvas");padCv.width=padCv.height=512;var padTex=new T.CanvasTexture(padCv);padTex.wrapS=padTex.wrapT=T.RepeatWrapping;padTex.repeat.set(1.5,1.2);padTex.anisotropy=8;
var lineCv=document.createElement("canvas");lineCv.width=lineCv.height=64;var lineTex=new T.CanvasTexture(lineCv);
/* the portacabin's ribbed steel walls */
var ribCv=document.createElement("canvas");ribCv.width=256;ribCv.height=128;var ribTex=new T.CanvasTexture(ribCv);ribTex.wrapS=T.RepeatWrapping;ribTex.anisotropy=8;
function ribs(d){var g=ribCv.getContext("2d");g.fillStyle=d?"#C9CEC8":"#E3E6E1";g.fillRect(0,0,256,128);
 for(var x=0;x<256;x+=16){var gr=g.createLinearGradient(x,0,x+16,0);gr.addColorStop(0,"rgba(0,0,0,.16)");gr.addColorStop(0.35,"rgba(255,255,255,.18)");gr.addColorStop(0.7,"rgba(0,0,0,.05)");gr.addColorStop(1,"rgba(0,0,0,.2)");g.fillStyle=gr;g.fillRect(x,0,16,128)}
 g.fillStyle="rgba(120,90,50,.12)";for(var i=0;i<14;i++)g.fillRect(Math.random()*256,96+Math.random()*30,2+Math.random()*3,4+Math.random()*10);ribTex.needsUpdate=true}
var mPortaWall=new T.MeshStandardMaterial({map:ribTex,roughness:0.6,metalness:0.2});
function drawTex(d){var c=d?{b:"#59616A",l:"#8B949B",k:"#30373C"}:{b:"#B9C0B7",l:"#DCE0DA",k:"#858D84"};
 speckle(conCv.getContext("2d"),128,128,c.b,c.l,c.k);conTex.needsUpdate=true;
 var g=winCv.getContext("2d");speckle(g,128,128,c.b,c.l,c.k);g.fillStyle=d?"#1B2125":"#2C3439";g.fillRect(28,32,72,62);g.fillStyle=d?"#2A3238":"#46505A";g.fillRect(30,34,68,58);
 g.fillStyle=d?"#1B2125":"#2C3439";g.fillRect(62,34,4,58);g.fillRect(30,60,68,3);winTex.needsUpdate=true;
 (function(g){speckle(g,512,512,d?"#3A4248":"#5C6259",d?"#59626A":"#71776C",d?"#22282C":"#444A41");   /* light mode: deeper than it looks here, since the renderer brightens canvas textures; it reads as mid-grey site concrete, never a white sheet */
  /* slight tone variation per slab */
  for(var sx=0;sx<4;sx++)for(var sy=0;sy<4;sy++){g.fillStyle=Math.random()<0.5?"rgba(255,255,255,.035)":"rgba(0,0,0,.05)";g.fillRect(sx*128,sy*128,128,128)}
  /* expansion joints */
  g.strokeStyle=d?"rgba(0,0,0,.55)":"rgba(60,66,60,.45)";g.lineWidth=2;for(var k=0;k<=512;k+=128){g.beginPath();g.moveTo(k,0);g.lineTo(k,512);g.moveTo(0,k);g.lineTo(512,k);g.stroke()}
  g.strokeStyle=d?"rgba(255,255,255,.07)":"rgba(255,255,255,.22)";g.lineWidth=1;for(var k2=1;k2<=512;k2+=128){g.beginPath();g.moveTo(k2+1,0);g.lineTo(k2+1,512);g.moveTo(0,k2+1);g.lineTo(512,k2+1);g.stroke()}
  /* oil and water stains */
  for(var s=0;s<7;s++){var x=Math.random()*512,y=Math.random()*512,r=14+Math.random()*34,gr=g.createRadialGradient(x,y,2,x,y,r);
   gr.addColorStop(0,d?"rgba(0,0,0,.35)":"rgba(40,46,40,.22)");gr.addColorStop(1,"rgba(0,0,0,0)");g.fillStyle=gr;g.beginPath();g.ellipse(x,y,r,r*0.7,Math.random()*3,0,7);g.fill()}
  /* hairline cracks */
  g.strokeStyle=d?"rgba(0,0,0,.4)":"rgba(70,76,70,.35)";g.lineWidth=1;for(var c2=0;c2<5;c2++){var cx=Math.random()*512,cy=Math.random()*512;g.beginPath();g.moveTo(cx,cy);
   for(var q=0;q<6;q++){cx+=(Math.random()-0.5)*40;cy+=(Math.random()-0.5)*40;g.lineTo(cx,cy)}g.stroke()}
  /* tyre tracks */
  g.strokeStyle=d?"rgba(0,0,0,.22)":"rgba(70,76,70,.14)";g.lineWidth=9;[150,178].forEach(function(o){g.beginPath();g.moveTo(-20,o+60);g.bezierCurveTo(140,o+20,300,o+120,540,o+40);g.stroke()});
 })(padCv.getContext("2d"));padTex.needsUpdate=true;
 (function(g){g.clearRect(0,0,64,64);g.fillStyle="#FBB401";g.fillRect(0,0,64,64);g.fillStyle="#101316";g.fillRect(0,0,64,6);g.fillRect(0,58,64,6)})(lineCv.getContext("2d"));lineTex.needsUpdate=true;
 ribs(d);mPortaWall.needsUpdate=true}
var lattice=canvasTex(64,256,function(g,w,h){g.clearRect(0,0,w,h);g.strokeStyle="#fff";g.lineWidth=5;g.strokeRect(2,0,w-4,h);g.lineWidth=3;
 for(var y=0;y<h;y+=64){g.beginPath();g.moveTo(2,y);g.lineTo(w-2,y+64);g.moveTo(w-2,y);g.lineTo(2,y+64);g.moveTo(2,y);g.lineTo(w-2,y);g.stroke()}});
lattice.wrapT=T.RepeatWrapping;
function labelTex(txt,col,bg){return canvasTex(560,96,function(g,w,h){g.fillStyle=bg;g.fillRect(0,0,w,h);g.fillStyle="#101316";g.fillRect(0,0,16,h);
 g.font='700 46px "Martian Mono",ui-monospace,monospace';g.textBaseline="middle";g.fillStyle=col;g.fillText(txt,34,h/2+3)})}

/* ---------- materials ---------- */
var mCon=std({map:conTex,color:"#fff"}),mWall=std({map:winTex,color:"#fff",emissive:"#ffffff",emissiveMap:winEm,emissiveIntensity:0}),
    mPad=std({map:padTex,color:"#fff"}),mYel=std({color:"#FBB401",roughness:0.55}),mInk=std({color:"#1B1F22",roughness:0.6}),
    mSteel=std({color:"#8A949A",roughness:0.45,metalness:0.4}),mLat=std({color:"#FBB401",map:lattice,alphaTest:0.5,side:T.DoubleSide,roughness:0.55}),
    mGlass=std({color:"#2C3439",emissive:"#ffd28a",emissiveIntensity:0.4}),mRed=std({color:"#ff3b30",emissive:"#ff2a1e",emissiveIntensity:1});
var shadowM=new T.ShadowMaterial({opacity:0.22});

/* ---------- lights: the day turns to night and back ---------- */
var hemi=new T.HemisphereLight(0xffffff,0x3a3f42,0.8);S.add(hemi);
var key=new T.DirectionalLight(0xfff1dc,1.0);key.position.set(6,11,7);key.castShadow=true;key.shadow.mapSize.set(1024,1024);
(function(c){c.left=-7;c.right=7;c.top=8;c.bottom=-4;c.near=1;c.far=40})(key.shadow.camera);key.shadow.bias=-0.0006;S.add(key);
var rim=new T.DirectionalLight(0xb9cfff,0.35);rim.position.set(-8,7,-6);S.add(rim);
var work=new T.SpotLight(0xffe2a8,0,14,0.75,0.6,1.4);work.position.set(-0.4,2.75,-2.3);work.target.position.set(0.5,0,0.6);S.add(work);S.add(work.target);   /* site floodlight, on at night */

/* ---------- the site: pad, ground shadow, barrier, office, block pile, skip ---------- */
var pad=new T.Mesh(new T.BoxGeometry(7.6,0.2,6.2),mPad);pad.position.set(-0.1,-0.1,0);pad.receiveShadow=true;S.add(pad);
var ground=new T.Mesh(new T.PlaneGeometry(40,40),shadowM);ground.rotation.x=-Math.PI/2;ground.position.y=-0.2;ground.receiveShadow=true;S.add(ground);
function add(geo,mat,x,y,z,parent){var m=new T.Mesh(geo,mat);m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;(parent||S).add(m);return m}
var hazard=canvasTex(256,32,function(g,w,h){g.fillStyle="#FBB401";g.fillRect(0,0,w,h);g.fillStyle="#101316";for(var x=-h;x<w+h;x+=32){g.beginPath();g.moveTo(x,h);g.lineTo(x+16,h);g.lineTo(x+16+h,0);g.lineTo(x+h,0);g.fill()}});
var mRail=std({map:hazard,roughness:0.6,flatShading:false});
[[-1.6,2.95,0],[1.0,2.95,0]].forEach(function(p){var g=new T.Group();g.position.set(p[0],0,p[1]);S.add(g);
 [-0.8,0.8].forEach(function(x){add(new T.BoxGeometry(0.08,0.75,0.08),mInk,x,0.37,0,g)});
 add(new T.BoxGeometry(1.8,0.14,0.04),mRail,0,0.62,0,g);add(new T.BoxGeometry(1.8,0.14,0.04),mRail,0,0.34,0,g)});
/* the site office: the foreman's cabin */
var office=new T.Group();office.position.set(2.75,0,-1.85);office.rotation.y=-0.35;S.add(office);
ribTex.repeat.set(4,1);
add(new T.BoxGeometry(1.6,0.12,0.92),mInk,0,0.06,0,office);                                   /* skids */
add(new T.BoxGeometry(1.5,0.74,0.85),mPortaWall,0,0.49,0,office);                              /* ribbed body */
add(new T.BoxGeometry(1.6,0.07,0.95),mInk,0,0.89,0,office);                                    /* roof */
add(new T.BoxGeometry(1.52,0.05,0.87),std({color:"#3A4248"}),0,0.15,0,office);                 /* base trim */
var offWin=add(new T.BoxGeometry(0.5,0.28,0.02),mGlass,-0.32,0.55,0.435,office);
add(new T.BoxGeometry(0.56,0.035,0.04),mInk,-0.32,0.7,0.44,office);add(new T.BoxGeometry(0.56,0.035,0.04),mInk,-0.32,0.4,0.44,office);
add(new T.BoxGeometry(0.035,0.31,0.04),mInk,-0.6,0.55,0.44,office);add(new T.BoxGeometry(0.035,0.31,0.04),mInk,-0.04,0.55,0.44,office);
add(new T.BoxGeometry(0.03,0.28,0.03),mInk,-0.32,0.55,0.445,office);                           /* window bar */
for(var bl=0;bl<4;bl++)add(new T.BoxGeometry(0.48,0.012,0.01),std({color:"#9AA4A8"}),-0.32,0.66-bl*0.06,0.448,office);   /* blinds */
add(new T.BoxGeometry(0.32,0.6,0.03),std({color:"#4A545B"}),0.38,0.47,0.44,office);            /* door */
add(new T.BoxGeometry(0.05,0.02,0.03),mYel,0.27,0.47,0.46,office);                               /* handle */
add(new T.BoxGeometry(0.44,0.06,0.26),std({color:"#6F787C",metalness:0.4}),0.38,0.13,0.6,office);/* step */
add(new T.BoxGeometry(0.44,0.06,0.2),std({color:"#6F787C",metalness:0.4}),0.38,0.05,0.82,office);
add(new T.BoxGeometry(0.025,0.42,0.025),mYel,0.61,0.3,0.78,office);add(new T.BoxGeometry(0.025,0.025,0.42),mYel,0.61,0.5,0.6,office);   /* handrail */
add(new T.BoxGeometry(0.22,0.24,0.18),std({color:"#D9DDD7"}),-0.84,0.5,0.1,office);             /* AC unit */
add(new T.BoxGeometry(0.02,0.16,0.14),std({color:"#5A646B"}),-0.955,0.5,0.1,office);
add(new T.CylinderGeometry(0.025,0.025,0.5,6),std({color:"#8A949A",metalness:0.5}),0.7,1.1,-0.3,office);  /* aerial */
var mSign=std({map:labelTex("FOREMAN","#101316","#FBB401"),flatShading:false});
add(new T.BoxGeometry(0.9,0.17,0.02),mSign,0.05,0.97,0.38,office);
add(new T.BoxGeometry(0.06,0.18,0.06),mInk,-0.55,0.95,0.38,office);add(new T.BoxGeometry(0.06,0.18,0.06),mInk,0.6,0.95,0.38,office);
/* painted walkway lines */
var mLine=new T.MeshStandardMaterial({map:lineTex,roughness:0.8,transparent:true,opacity:0.9});
[[0.9,1.15,4.6,0.09,0],[-2.95,0.2,0.09,4.6,0]].forEach(function(l){var m=new T.Mesh(new T.PlaneGeometry(l[2],l[3]),mLine);m.rotation.x=-Math.PI/2;m.position.set(l[0],0.004,l[1]);m.receiveShadow=true;S.add(m)});
/* timber pallets with bundled pipes */
var mWood=std({color:"#8A6A45",roughness:0.9}),mPipe=std({color:"#9AA4A8",roughness:0.4,metalness:0.5});
function pallet(x,z,ry){var g=new T.Group();g.position.set(x,0,z);g.rotation.y=ry;S.add(g);
 for(var i=0;i<5;i++)add(new T.BoxGeometry(0.11,0.025,0.7),mWood,-0.3+i*0.15,0.1,0,g);
 [-0.28,0,0.28].forEach(function(z2){add(new T.BoxGeometry(0.72,0.075,0.08),mWood,0,0.045,z2,g)});return g}
var pp=pallet(-3.15,0.45,0.2);for(var pi=0;pi<5;pi++){var pipe=add(new T.CylinderGeometry(0.055,0.055,0.72,10),mPipe,-0.22+pi*0.11,0.17,0,pp);pipe.rotation.x=Math.PI/2}
for(var pj=0;pj<4;pj++){var pipe2=add(new T.CylinderGeometry(0.055,0.055,0.72,10),mPipe,-0.165+pj*0.11,0.265,0,pp);pipe2.rotation.x=Math.PI/2}
add(new T.BoxGeometry(0.05,0.32,0.72),mYel,0.33,0.2,0,pp);                                      /* strap */
/* a generator, with its cable running to the floodlight mast */
var gen=new T.Group();gen.position.set(-3.2,0,-0.6);gen.rotation.y=0.3;S.add(gen);
add(new T.BoxGeometry(0.7,0.42,0.42),mYel,0,0.25,0,gen);add(new T.BoxGeometry(0.72,0.06,0.44),mInk,0,0.47,0,gen);
add(new T.BoxGeometry(0.22,0.2,0.02),std({color:"#101316"}),0.15,0.25,0.215,gen);
var ex=add(new T.CylinderGeometry(0.03,0.03,0.22,6),std({color:"#5A646B",metalness:0.5}),-0.22,0.6,0,gen);
[[-0.3,0.21],[0.3,0.21],[-0.3,-0.21],[0.3,-0.21]].forEach(function(w){add(new T.BoxGeometry(0.08,0.05,0.08),mInk,w[0],0.025,w[1],gen)});
var mCordage=std({color:"#101316",roughness:0.7});
add(new T.TubeGeometry(new T.CatmullRomCurve3([new T.Vector3(-2.9,0.2,-0.5),new T.Vector3(-2.4,0.02,-0.2),new T.Vector3(-1.5,0.02,-0.6),new T.Vector3(-0.9,0.02,-1.3),new T.Vector3(-0.4,0.02,-2.35)]),40,0.018,5,false),mCordage,0,0,0);
var mast=new T.Group();mast.position.set(-0.4,0,-2.4);S.add(mast);
add(new T.BoxGeometry(0.5,0.08,0.5),mInk,0,0.04,0,mast);
var mPole=std({color:"#B4BDC2",roughness:0.4,metalness:0.35});add(new T.CylinderGeometry(0.05,0.07,2.6,8),mPole,0,1.34,0,mast);for(var bd=0;bd<3;bd++)add(new T.CylinderGeometry(0.075,0.075,0.12,8),mYel,0,0.35+bd*0.85,0,mast);
var lampHead=add(new T.BoxGeometry(0.5,0.22,0.12),mYel,0,2.68,0.05,mast);lampHead.rotation.x=0.45;
var mLamp=std({color:"#FFF4D8",emissive:"#FFE8B0",emissiveIntensity:0});
[-0.14,0.14].forEach(function(x){var l=add(new T.BoxGeometry(0.2,0.14,0.02),mLamp,x,2.66,0.12,mast);l.rotation.x=0.45});
/* a small stack of rebar on timber bearers */
for(var rb=0;rb<7;rb++){var rbar=add(new T.CylinderGeometry(0.018,0.018,1.5,5),std({color:"#7A5434",roughness:0.9}),2.65+rb*0.045,0.08,0.45,null);rbar.rotation.x=Math.PI/2}
add(new T.BoxGeometry(0.42,0.05,0.07),mWood,2.78,0.025,-0.15);add(new T.BoxGeometry(0.42,0.05,0.07),mWood,2.78,0.025,1.05);
/* a pile of new blocks, and a skip for rejected ones */
var PILE=new T.Vector3(-2.35,0.55,1.55),SKIP=new T.Vector3(2.6,0,1.55);
var truck=new T.Group();truck.position.set(-2.35,0,1.55);truck.rotation.y=Math.PI/2+0.08;S.add(truck);
var mTruck=std({color:"#E6E9E4",roughness:0.5}),mTyre=std({color:"#15181A",roughness:0.9});
add(new T.BoxGeometry(1.7,0.12,0.9),mInk,0,0.34,0,truck);                                         /* chassis */
add(new T.BoxGeometry(1.5,0.06,0.92),std({color:"#5A646B",metalness:0.3}),0.05,0.42,0,truck);    /* flatbed */
add(new T.BoxGeometry(0.62,0.66,0.9),mTruck,-1.05,0.62,0,truck);                                    /* cab */
add(new T.BoxGeometry(0.03,0.3,0.78),std({color:"#2C3439",emissive:"#ffd28a",emissiveIntensity:0.15}),-1.37,0.72,0,truck); /* windscreen */
add(new T.BoxGeometry(0.62,0.09,0.92),mYel,-1.05,0.98,0,truck);                                     /* roof beacon bar */
[[-0.95,0.46],[-0.95,-0.46],[0.25,0.46],[0.25,-0.46],[0.62,0.46],[0.62,-0.46]].forEach(function(w){var wh=add(new T.CylinderGeometry(0.17,0.17,0.12,14),mTyre,w[0],0.17,w[1],truck);wh.rotation.x=Math.PI/2});
for(var i=0;i<6;i++){add(new T.BoxGeometry(0.4,0.3,0.4),mCon,-0.3+(i%3)*0.44,0.6+(i>2?0.31:0),(i>2?0.05:-0.02),truck)}
var skip=new T.Group();skip.position.copy(SKIP);S.add(skip);
add(new T.BoxGeometry(1.0,0.06,0.62),mYel,0,0.03,0,skip);
add(new T.BoxGeometry(1.0,0.42,0.06),mYel,0,0.24,0.29,skip);add(new T.BoxGeometry(1.0,0.42,0.06),mYel,0,0.24,-0.29,skip);
add(new T.BoxGeometry(0.06,0.42,0.62),mYel,0.5,0.24,0,skip);add(new T.BoxGeometry(0.06,0.42,0.62),mYel,-0.5,0.24,0,skip);

/* ---------- the tower crane: the builder ---------- */
var CB=new T.Vector3(-2.3,0,-1.7),MAST=4.3;
var crane=new T.Group();crane.position.copy(CB);S.add(crane);
add(new T.BoxGeometry(0.9,0.25,0.9),mInk,0,0.12,0,crane);
for(var f=0;f<4;f++){var face=new T.Mesh(new T.PlaneGeometry(0.34,MAST),mLat);face.position.set(f===0?0.17:f===1?-0.17:0,MAST/2,f===2?0.17:f===3?-0.17:0);face.rotation.y=f<2?Math.PI/2:0;face.castShadow=true;crane.add(face)}
lattice.repeat.set(1,MAST/1.4);
var slew=new T.Group();slew.position.y=MAST;crane.add(slew);
add(new T.BoxGeometry(0.42,0.32,0.42),mYel,0,0.16,0,slew);                 /* slewing ring and cab */
add(new T.BoxGeometry(0.34,0.3,0.32),mInk,0.25,-0.05,0.3,slew);
var jibF=new T.Mesh(new T.PlaneGeometry(4.6,0.3),mLat);jibF.position.set(2.4,0.42,0);jibF.castShadow=true;slew.add(jibF);
var jibF2=jibF.clone();jibF2.rotation.x=Math.PI/2;jibF2.position.y=0.28;slew.add(jibF2);
add(new T.BoxGeometry(1.8,0.12,0.24),mYel,-0.95,0.36,0,slew);              /* counter-jib */
add(new T.BoxGeometry(0.55,0.42,0.44),std({color:"#5A646B"}),-1.6,0.16,0,slew); /* counterweight */
add(new T.BoxGeometry(0.1,0.85,0.1),mYel,0,0.75,0,slew);                    /* apex */
var light=add(new T.SphereGeometry(0.06,8,6),mRed,0,1.22,0,slew);         /* aircraft warning light */
/* the jib as a real truss: solid chords so it reads from every angle */
var JL=4.7,mChord=std({color:"#FBB401",roughness:0.5,metalness:0.2});
[[0,0.58,0,0.07],[0,0.26,0.13,0.06],[0,0.26,-0.13,0.06]].forEach(function(c){add(new T.BoxGeometry(JL,c[3],c[3]),mChord,JL/2+0.1,c[1],c[2],slew)});
for(var dj=0.4;dj<JL;dj+=0.45){[0.13,-0.13].forEach(function(z){var br=add(new T.BoxGeometry(0.035,0.36,0.035),mChord,dj,0.42,z*0.5,slew);br.rotation.x=z>0?-0.42:0.42})}
add(new T.BoxGeometry(0.1,0.1,0.32),mChord,JL+0.1,0.3,0,slew);
/* the pendant ties from the apex down to the jib and counter-jib */
[[JL*0.62,0.58],[-1.5,0.42]].forEach(function(p2){var dx=p2[0],dy=1.2-p2[1],len=Math.hypot(dx,dy);var tie=add(new T.CylinderGeometry(0.014,0.014,len,4),mInk,dx/2,p2[1]+dy/2,0,slew);tie.rotation.z=Math.atan2(dx,dy)})
var trolley=add(new T.BoxGeometry(0.3,0.12,0.34),mInk,2,0.2,0,slew);
var mCable=new T.MeshBasicMaterial({color:'#D8DEE2'});var cable=new T.Mesh(new T.CylinderGeometry(0.026,0.026,1,6),mCable);S.add(cable);var cable2=new T.Mesh(new T.CylinderGeometry(0.026,0.026,1,6),mCable);S.add(cable2);
var hook=add(new T.BoxGeometry(0.2,0.14,0.18),mYel,0,1,0);
function setHook(p){var dx=p.x-CB.x,dz=p.z-CB.z,a=Math.atan2(-dz,dx),r=Math.max(0.9,Math.hypot(dx,dz));
 slew.rotation.y=a;trolley.position.x=r;hook.position.copy(p);
 var top=new T.Vector3(CB.x+Math.cos(a)*r,MAST+0.15,CB.z-Math.sin(a)*r),len=top.y-p.y-0.06;
 var ox=Math.sin(a)*0.05,oz=Math.cos(a)*0.05;cable.position.set(top.x+ox,p.y+0.06+len/2,top.z+oz);cable.scale.y=Math.max(0.01,len);cable2.position.set(top.x-ox,p.y+0.06+len/2,top.z-oz);cable2.scale.y=Math.max(0.01,len)}

/* ---------- the tower: one floor per job ---------- */
var FLOORS=3,FH=0.6,M=0.6,GRID=[[-1,-1],[0,-1],[1,-1],[-1,0],[1,0],[-1,1],[0,1],[1,1]],TX=0.4,TZ=-0.3;
var blueM=new T.LineBasicMaterial({color:0x5aa0f0,transparent:true,opacity:0});
var floors=[];
for(var fl=0;fl<FLOORS;fl++){var y0=fl*FH,F={y0:y0,mods:[],bad:0,state:0};
 F.slab=add(new T.BoxGeometry(2.04,0.08,2.04),mCon,TX,y0+0.04,TZ);
 GRID.forEach(function(g){var m=add(new T.BoxGeometry(M,0.52,M),[mWall,mWall,mCon,mCon,mWall,mWall],TX+g[0]*0.66,y0+0.08+0.26,TZ+g[1]*0.66);
  m.material=[mWall,mWall,mCon,mCon,mWall,mWall].map(function(x){return x});m.userData.home=m.position.clone();F.mods.push(m)});
 F.plan=new T.LineSegments(new T.EdgesGeometry(new T.BoxGeometry(2.04,FH,2.04)),blueM.clone());F.plan.position.set(TX,y0+FH/2,TZ);S.add(F.plan);
 var lab=new T.Sprite(new T.SpriteMaterial({transparent:true,depthTest:false}));lab.scale.set(1.95,0.34,1);lab.center.set(0,0.5);lab.position.set(TX+1.5,y0+0.34,TZ+0.55);var ld=new T.Line(new T.BufferGeometry().setFromPoints([new T.Vector3(TX+1.04,y0+0.3,TZ+0.55),new T.Vector3(TX+1.5,y0+0.34,TZ+0.55)]),new T.LineBasicMaterial({color:0x8FCB7C,transparent:true}));S.add(ld);F.leader=ld;lab.renderOrder=5;S.add(lab);F.label=lab;
 floors.push(F)}
var badM=std({color:"#c7372d",emissive:"#ff2a1e",emissiveIntensity:0.9});
var okFlash=std({color:"#7EE787",emissive:"#3fbf55",emissiveIntensity:0.8});
/* the inspection scan: a green ring that rises through the new floor */
var scanM=new T.LineBasicMaterial({color:0x7ee787,transparent:true,opacity:0}),scan=new T.LineSegments(new T.EdgesGeometry(new T.BoxGeometry(2.2,0.01,2.2)),scanM);scan.position.set(TX,0,TZ);S.add(scan);
var scanPlane=new T.Mesh(new T.PlaneGeometry(2.2,2.2),new T.MeshBasicMaterial({color:0x7ee787,transparent:true,opacity:0,depthWrite:false,side:T.DoubleSide}));scanPlane.rotation.x=-Math.PI/2;scanPlane.position.set(TX,0,TZ);S.add(scanPlane);
var spare=add(new T.BoxGeometry(M,0.52,M),mWall,0,-5,0);
var flag=new T.Group();flag.position.set(TX+0.7,FLOORS*FH,TZ+0.7);S.add(flag);
add(new T.CylinderGeometry(0.025,0.025,0.95,6),std({color:"#E7EAE5",metalness:0.3}),0,0.47,0,flag);
var flagCloth=add(new T.BoxGeometry(0.44,0.26,0.012),std({color:"#3FAE6A",emissive:"#1E7B4A",emissiveIntensity:0.25}),0.24,0.8,0,flag);

/* ---------- timing ---------- */
var PLAN=0.7,PER=0.52,BUILD=PLAN+8*PER,SCAN=BUILD+1.0,REPL=SCAN+1.5,ACC=REPL+0.7,FLOOR_T=ACC,HOLD=4.4;
var DAY=3.4,EVE=2.6,PRE=DAY+EVE,JE=PRE+FLOORS*FLOOR_T,LOOP=JE+HOLD;
/* the sky through one night: [time, top colour, horizon colour] */
var SKY=[[0,"#6FB2E4","#CFE7F4"],[DAY-0.3,"#6FB2E4","#CFE7F4"],[DAY+EVE*0.55,"#4B3F7A","#F2A15A"],[PRE+0.4,"#0A1424","#1B2B45"],[JE,"#0A1424","#1B2B45"],
 [JE+1.3,"#3E4677","#F6B26B"],[JE+2.6,"#7DB9E2","#F9DDA6"],[LOOP,"#6FB2E4","#CFE7F4"]];
function hex(c){return [parseInt(c.slice(1,3),16),parseInt(c.slice(3,5),16),parseInt(c.slice(5,7),16)]}
function mix(a,b,u){a=hex(a);b=hex(b);return "rgb("+[0,1,2].map(function(i){return Math.round(a[i]+(b[i]-a[i])*u)}).join(",")+")"}
function skyAt(lt){for(var i=1;i<SKY.length;i++)if(lt<=SKY[i][0]){var u=ease((lt-SKY[i-1][0])/Math.max(0.001,SKY[i][0]-SKY[i-1][0]));return [mix(SKY[i-1][1],SKY[i][1],u),mix(SKY[i-1][2],SKY[i][2],u)]}return [SKY[0][1],SKY[0][2]]}
var skyLT=0,skyNK=0;
function drawSky(lt,nk){skyLT=lt;skyNK=nk;var w=sky.width,h=sky.height;if(!w||!h)return;var c=skyAt(lt),g=sg.createLinearGradient(0,0,0,h);g.addColorStop(0,c[0]);g.addColorStop(1,c[1]);sg.fillStyle=g;sg.fillRect(0,0,w,h);
 var px=w/Math.max(1,box.clientWidth);
 if(nk>0.02){sg.fillStyle="#fff";STARS.forEach(function(s){sg.globalAlpha=nk*(0.55+0.45*Math.sin(lt*1.7+s[3]));sg.beginPath();sg.arc(s[0]*w,s[1]*h,s[2]*px,0,7);sg.fill()});sg.globalAlpha=1;
  var mu=Math.max(0,Math.min(1,(lt-PRE)/(JE-PRE))),mx=w*(0.18+0.64*mu),my=h*(0.24-0.1*Math.sin(Math.PI*mu)),mr=11*px;
  sg.globalAlpha=nk;sg.fillStyle="#F4E9C8";sg.beginPath();sg.arc(mx,my,mr,0,7);sg.fill();sg.fillStyle=c[0];sg.beginPath();sg.arc(mx+mr*0.45,my-mr*0.3,mr*0.85,0,7);sg.fill();sg.globalAlpha=1}
 function sun(x,y,a){if(a<=0.01)return;var r=16*px,gl=sg.createRadialGradient(x,y,r*0.6,x,y,r*2.6);gl.addColorStop(0,"rgba(255,214,90,"+0.5*a+")");gl.addColorStop(1,"rgba(255,214,90,0)");sg.fillStyle=gl;sg.beginPath();sg.arc(x,y,r*2.6,0,7);sg.fill();
  sg.globalAlpha=a;sg.fillStyle="#FFD34D";sg.beginPath();sg.arc(x,y,r,0,7);sg.fill();sg.globalAlpha=1}
 if(lt<PRE){var su=ease(lt/PRE);sun(w*(0.2-0.06*su),h*(0.2+0.75*su),1-ease((lt-DAY-EVE*0.6)/(EVE*0.4)))}
 if(lt>JE){var ru=ease((lt-JE)/HOLD);sun(w*0.86,h*(1.0-0.62*ru),ease((lt-JE)/1.2))}}
function clockAt(i,u){var c=CAPS[i],hr=(c[0]+(c[1]-c[0])*u)%24,hh=Math.floor(hr),mm=Math.floor((hr-hh)*60/10)*10;return (hh<10?"0":"")+hh+":"+(mm<10?"0":"")+mm}
function caption(lt,cur,ft,inHold){if(!cap)return;var i,u;if(lt<DAY){i=0;u=lt/DAY}else if(lt<PRE){i=1;u=(lt-DAY)/EVE}else if(!inHold){i=2+cur;u=ft/FLOOR_T}else{i=5;u=(lt-JE)/HOLD}
 cap.querySelector(".clk").textContent=clockAt(i,Math.max(0,Math.min(1,u)));
 if(i!==capAt){capAt=i;cap.querySelector(".cap").innerHTML="<b>"+CAPS[i][2]+"</b><span>"+CAPS[i][3].replace(/&/g,"&amp;").replace(/</g,"&lt;")+"</span>";
  [].forEach.call(cap.querySelectorAll(".pips i"),function(p,k){p.className=k<=i?"on":""})}}
function ease(x){x=Math.max(0,Math.min(1,x));return x*x*(3-2*x)}
function lerp(a,b,u){return a+(b-a)*u}
/* the hook's path: lift, swing around the mast, lower */
function travel(from,to,u,topY,out){var a0=Math.atan2(-(from.z-CB.z),from.x-CB.x),a1=Math.atan2(-(to.z-CB.z),to.x-CB.x),r0=Math.hypot(from.x-CB.x,from.z-CB.z),r1=Math.hypot(to.x-CB.x,to.z-CB.z);
 var y,a,r;if(u<0.25){var k=ease(u/0.25);y=lerp(from.y,topY,k);a=a0;r=r0}else if(u<0.75){var k2=ease((u-0.25)/0.5);y=topY;a=lerp(a0,a1,k2);r=lerp(r0,r1,k2)}else{var k3=ease((u-0.75)/0.25);y=lerp(topY,to.y,k3);a=a1;r=r1}
 out.set(CB.x+Math.cos(a)*r,y,CB.z-Math.sin(a)*r);return out}
var tmp=new T.Vector3(),pileTop=new T.Vector3(PILE.x,1.35,PILE.z),skipTop=new T.Vector3(SKIP.x,0.75,SKIP.z);
function labelFor(i,d){return labelTex("JOB "+(11+i)+" · MERGED",d?"#8FCB7C":"#2F6B3A",d?"rgba(16,19,22,.85)":"rgba(248,249,246,.92)")}

/* ---------- theme ---------- */
var night=0,running=false;
function paint(){var d=isDark();drawTex(d);mCable.color.set(d?'#4A5359':'#555E63');shadowM.opacity=d?0.4:0.22;
 floors.forEach(function(F,i){if(F.label.material.map)F.label.material.map.dispose();F.label.material.map=labelFor(i,d);F.label.material.needsUpdate=true});
 if(!running)draw()}

/* ---------- one frame of the loop ---------- */
function setState(t){var loopT=t%LOOP,d=isDark();
 night=loopT<DAY?0:loopT<PRE?ease((loopT-DAY)/EVE):loopT<JE?1:1-ease((loopT-JE)/1.6);var nk=d?night:night*0.8;drawSky(loopT,night);
 hemi.intensity=(d?0.6:0.85)-0.38*nk;key.intensity=1.0-0.6*nk;key.color.setHSL(0.09-0.02*nk,0.4+0.2*nk,0.92-0.18*nk);work.intensity=3.2*nk;mLamp.emissiveIntensity=0.2+1.6*nk;
 mGlass.emissiveIntensity=0.25+0.9*nk;light.material.emissiveIntensity=(Math.sin(t*4)>0.2?1.6:0.15);
 var jt=loopT-PRE,pre=jt<0,cur=pre?0:Math.min(FLOORS-1,Math.floor(jt/FLOOR_T)),ft=pre?-1:jt-cur*FLOOR_T,inHold=jt>=FLOORS*FLOOR_T;if(inHold){cur=FLOORS;ft=0}
 caption(loopT,cur,ft,inHold);
 flag.visible=inHold;if(inHold){var fu=ease((jt-FLOORS*FLOOR_T-0.3)/0.9);flag.scale.set(1,Math.max(0.01,fu),1);flagCloth.rotation.y=0.25*Math.sin(t*3)}
 camZ=lerp(camZ,pre?0:Math.min(FLOORS,cur+(inHold?0:ft/FLOOR_T)),0.04);
 var topY=(Math.min(cur,FLOORS-1)+1)*FH+1.0;
 spare.position.y=-5;spare.visible=false;scanM.opacity=0;scanPlane.material.opacity=0;
 floors.forEach(function(F,i){
  if(pre){F.slab.visible=false;F.mods.forEach(function(m){m.visible=false});F.label.visible=false;F.leader.visible=false;   /* by day: only the plan, every floor in outline */
   F.plan.material.opacity=0.55*ease((loopT-0.5-i*0.35)/0.8);return}
  if(i<cur){                                                      /* built and merged */
   F.slab.visible=true;F.mods.forEach(function(m,k){m.visible=true;m.position.copy(m.userData.home);m.material=[mWall,mWall,mCon,mCon,mWall,mWall]});
   F.plan.material.opacity=0;F.label.material.opacity=1;F.label.visible=true;F.leader.visible=true;F.leader.material.opacity=1}
  else if(i>cur){F.slab.visible=false;F.mods.forEach(function(m){m.visible=false});F.plan.material.opacity=0;F.label.visible=false;F.leader.visible=false}
  else{                                                            /* the floor being built now */
   if(ft<0.02&&F.state!==cycle){F.state=cycle;F.bad=Math.floor(Math.random()*8)}
   F.label.visible=ft>ACC-0.7;F.label.material.opacity=ease((ft-(ACC-0.7))/0.5);F.leader.visible=F.label.visible;F.leader.material.opacity=F.label.material.opacity;
   F.plan.material.opacity=ft<ACC-0.4?0.35+0.5*ease(ft/0.45):0.85*(1-ease((ft-(ACC-0.4))/0.4));
   F.slab.visible=ft>PLAN*0.6;
   F.mods.forEach(function(m,k){var s0=PLAN+k*PER,home=m.userData.home;m.material=[mWall,mWall,mCon,mCon,mWall,mWall];
    if(ft<s0){m.visible=false;return}m.visible=true;
    if(ft<s0+PER){var u=(ft-s0)/PER;var carry=u<0.7;if(carry){travel(pileTop,tmp.set(home.x,home.y+0.3,home.z),u/0.7,topY,tmp);m.position.set(tmp.x,tmp.y-0.32,tmp.z);setHook(tmp)}
     else{m.position.copy(home);travel(tmp.set(home.x,home.y+0.3,home.z),pileTop,(u-0.7)/0.3,topY,tmp);setHook(tmp)}return}
    m.position.copy(home);
    if(k===F.bad&&ft>=SCAN-0.55&&ft<REPL){m.material=badM}          /* the inspection finds one bad block */
    if(k===F.bad&&ft>=SCAN&&ft<SCAN+0.75){var u2=(ft-SCAN)/0.75;travel(tmp.set(home.x,home.y+0.3,home.z),skipTop,u2,topY,tmp);m.position.set(tmp.x,tmp.y-0.32,tmp.z);setHook(tmp);if(u2>0.97)m.visible=false}
    else if(k===F.bad&&ft>=SCAN+0.75&&ft<REPL){m.visible=false;var u3=(ft-SCAN-0.75)/0.75;travel(pileTop,tmp.set(home.x,home.y+0.3,home.z),u3,topY,tmp);
     spare.position.set(tmp.x,tmp.y-0.32,tmp.z);spare.visible=true;setHook(tmp)}
    if(ft>=REPL&&ft<ACC){m.material=okFlash}});
   if(ft>=BUILD&&ft<SCAN){var u4=(ft-BUILD)/(SCAN-BUILD);scan.position.y=F.y0+0.08+0.55*u4;scanPlane.position.y=scan.position.y;scanM.opacity=Math.sin(Math.PI*u4);scanPlane.material.opacity=0.18*Math.sin(Math.PI*u4)}
   if(ft>=REPL||ft<PLAN)setHook(tmp.set(lerp(pileTop.x,TX,0.5),topY,lerp(pileTop.z,TZ,0.5)))}
 });
 if(inHold||pre)setHook(tmp.set(-0.2,pre?1.6:topY,1.0));
 /* windows of finished floors light up at night */
 mWall.emissiveIntensity=0.85*nk;
 /* the foreman's office window flashes blue as each plan goes out */
 if(pre?loopT<DAY:(!inHold&&ft<PLAN)){mGlass.emissive.setHex(0x5aa0f0);mGlass.emissiveIntensity=1.2}else mGlass.emissive.setHex(0xffd28a);
 /* a soft fade at the end of the loop, back to an empty site */
 var fadeOut=loopT>LOOP-0.6?1-ease((loopT-(LOOP-0.6))/0.6):loopT<0.4?ease(loopT/0.4):1;R.domElement.style.opacity=shown?String(fadeOut):"0"}

/* ---------- camera and loop ---------- */
var camA=0.62;
var camZ=0,fitMemo={};
/* the camera frames the whole site at any box shape: it backs off until the pad's corners and the crane top all sit inside the frame */
var FIT_PTS=[[-3.95,-0.2,-3.1],[3.75,-0.2,-3.1],[-3.95,-0.2,3.1],[3.75,-0.2,3.1],[-3.95,0.9,3.1],[3.75,0.9,3.1]].map(function(p){return new T.Vector3(p[0],p[1],p[2])});
var FIT_TOP=[new T.Vector3(-2.3,MAST+1.3,-1.7),new T.Vector3(-2.3+4.9,MAST+0.7,-1.7),new T.Vector3(-2.3-2.0,MAST+0.7,-1.7)];
function place(a,k){var rad=13.5;C.position.set(Math.sin(a)*rad-0.1,6.2+0.8*k,Math.cos(a)*rad);C.lookAt(0.1,1.45+0.55*k,0.45);C.updateMatrixWorld();C.matrixWorldInverse.copy(C.matrixWorld).invert()}
/* frame the site once per box size: measure its corners and the crane top over the whole loop (every camera angle, every tower height),
   then hold one zoom and centre, so the camera's slow drift never makes the framing twitch */
var frameFit=null;
function measure(){var v=new T.Vector3(),pts=FIT_PTS.concat(FIT_TOP),x0=9,x1=-9,y0=9,y1=-9;C.clearViewOffset();C.zoom=1;C.updateProjectionMatrix();
 for(var ai=0;ai<=8;ai++)for(var ki=0;ki<=4;ki++){place(camA+0.1*Math.sin(-Math.PI/2+ai/8*Math.PI),ki/4);
  for(var i=0;i<pts.length;i++){v.copy(pts[i]).project(C);x0=Math.min(x0,v.x);x1=Math.max(x1,v.x);y0=Math.min(y0,v.y);y1=Math.max(y1,v.y)}}
 var z=Math.min(1.97/(x1-x0),1.95/(y1-y0))*1.04;frameFit={z:z,cx:(x0+x1)/2,cy:(y0+y1)/2}}
function aim(t){var k=camZ/FLOORS,a=camA+0.1*Math.sin(t*0.09);if(!frameFit)measure();
 var W=Math.max(1,box.clientWidth),Hh=Math.max(1,box.clientHeight);place(a,k);
 C.zoom=frameFit.z;C.setViewOffset(W,Hh,frameFit.cx*frameFit.z*W/2,-frameFit.cy*frameFit.z*Hh/2,W,Hh);C.updateProjectionMatrix()}
function size(){var w=box.clientWidth,h=box.clientHeight;if(!w||!h)return;R.setSize(w,h,false);var dp=Math.min(2,window.devicePixelRatio||1);sky.width=Math.round(w*dp);sky.height=Math.round(h*dp);drawSky(skyLT,skyNK);C.aspect=w/h;frameFit=null;C.updateProjectionMatrix()}
var still=!!(window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches),visible=true,t0=performance.now(),cycle=0,shown=false,lastLoop=0;
function draw(){R.render(S,C);if(!shown){shown=true;R.domElement.style.opacity="1"}}
function step(now){var t=(now-t0)/1000,lc=Math.floor(t/LOOP);if(lc!==lastLoop){lastLoop=lc;cycle++}setState(t);aim(t);draw();if(running)requestAnimationFrame(step)}
function play(){if(running||still||!visible||document.hidden)return;running=true;requestAnimationFrame(step)}
function pause(){running=false}
size();paint();
if(still){R.domElement.style.transition="none";setState(JE+3.2);camZ=FLOORS;aim(0);draw();R.domElement.style.opacity="1"}else play();
if(document.fonts&&document.fonts.load)document.fonts.load('700 46px "Martian Mono"').then(function(){paint()});
new MutationObserver(paint).observe(root,{attributes:true,attributeFilter:["data-theme"]});
if(window.matchMedia){var mq=matchMedia("(prefers-color-scheme: dark)");(mq.addEventListener?mq.addEventListener.bind(mq,"change"):mq.addListener.bind(mq))(paint)}
if(window.IntersectionObserver)new IntersectionObserver(function(es){visible=es[0].isIntersecting;visible?play():pause()}).observe(box);
document.addEventListener("visibilitychange",function(){document.hidden?pause():play()});
if(window.ResizeObserver)new ResizeObserver(function(){size();if(!running)draw()}).observe(box);
})();</script>"""

THREE_JS = '<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>'


def share_tags(rel: str, title: str, description: str) -> str:
    """Canonical link plus Open Graph and Twitter tags, so a shared link shows a title, a line and the card.
    `rel` is the page's path under docs/; the front page is the site root."""
    url = SITE_URL + ("" if rel == "index.html" else rel)
    return (f'<link rel="canonical" href="{url}">'
            f'<meta property="og:type" content="website"><meta property="og:site_name" content="Topping Out">'
            f'<meta property="og:url" content="{url}"><meta property="og:title" content="{esc(title)}">'
            f'<meta property="og:description" content="{esc(description)}">'
            f'<meta property="og:image" content="{SITE_URL}{OG_CARD}"><meta property="og:image:width" content="1200">'
            f'<meta property="og:image:height" content="630"><meta property="og:image:alt" content="Topping Out: Stop babysitting agents. Hire a foreman.">'
            f'<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{esc(title)}">'
            f'<meta name="twitter:description" content="{esc(description)}"><meta name="twitter:image" content="{SITE_URL}{OG_CARD}">')


SHARE_MARK = "<!--share-->"
# a generated page in raw/ shares as the site page that frames it
RAW_SHARE = {"raw/route.html": "route.html", "raw/atlas.html": "atlas.html", "raw/board.html": "board.html",
             "raw/foreman-playbook.html": "playbooks.html", "raw/builder-playbook.html": "playbooks.html"}


class Site:
    def __init__(self):
        self.data = build_data(ROOT / "skills-wiki")
        self.by = {n["id"]: n for n in self.data["nodes"]}
        self.route = atlas_route()
        self.steps = [r[0] for r in self.route if r[0] not in ("ph", "pl")]
        self.built = ({p.stem for p in CONTENT.glob("skills/*.md")} | {f"agents/{p.stem}" for p in CONTENT.glob("agents/*.md")}) & set(self.by)
        self.group_of = {pid: g["name"] for g in self.data["groups"] for pid in g["ids"]}
        # the brand: a steel beam with its flag up (topping out). The site keeps its own copies in docs/assets/brand/;
        # the hard hat stays as the foreman's role icon
        logo = logo_uri(OUT / "assets" / "brand" / "topping-out-mark-h96.png")
        icon = logo_uri(OUT / "assets" / "brand" / "topping-out-icon-128.png")
        self.icon = f'<link rel="icon" type="image/png" href="{icon}">' if icon else ""
        self.mark = f'<img class="mark" src="{logo}" alt="">' if logo else ""

    def href(self, pid: str, prefix: str) -> str:
        return f"{prefix}{page_path(pid)}.html" if pid in self.built else f"{prefix}atlas.html"

    def counts(self) -> tuple[int, int]:
        nodes = self.data["nodes"]
        return sum(1 for n in nodes if n["type"] == "skill"), sum(1 for n in nodes if n["type"] == "agent")

    # ---------- the shell ----------

    def page(self, title: str, description: str, css: str, sheet: str, body: str, prefix: str = "", subs=None) -> str:
        """One page: the site plan, the phone bar, then the body. `sheet` is the plan entry this page belongs to."""
        n = next((i for i, (h, _) in enumerate(SHEETS, 1) if h == sheet), 0)
        here = f"{n:02d} · {SHEETS[n - 1][1]}" if n else "About"
        items = []
        for i, (h, label) in enumerate(SHEETS, 1):
            cur = h == sheet
            items.append(f'<li><a class="sheet" href="{prefix}{h}"' + (' aria-current="page"' if cur else "") + f"><b>{i:02d}</b><span>{esc(label)}</span></a>")
            if cur and subs:
                items.append('<ul class="subs">' + "".join(f'<li><a href="{esc(href)}">{esc(lbl)}</a></li>' for href, lbl in subs) + "</ul>")
            items.append("</li>")
        n_skill, n_agent = self.counts()
        plan = (f'<nav class="plan" aria-label="Site plan"><div class="ph"><a class="brand" href="{prefix}index.html">{self.mark}<span class="wm" role="img" aria-label="Topping Out"><b aria-hidden="true">Topping</b><b class="out" aria-hidden="true">Out</b></span></a>'
                f'<button type="button" class="planx" data-plan aria-expanded="false">Close</button></div><div class="haz" role="presentation"></div>'
                f'<div class="pl">Site plan</div><ol>{"".join(items)}</ol>'
                f'<div class="tblock"><div class="tt">{self.mark}<span role="img" aria-label="Topping Out"><b aria-hidden="true">Topping</b> <b class="out" aria-hidden="true">Out</b></span></div><div>Sheet<b>{f"{n:02d} of {len(SHEETS):02d}" if n else "About"}</b></div><div>Licence<b>MIT</b></div>'
                f'<div>{n_skill} skills<b>{n_agent} agents</b></div><div><button type="button" class="theme-toggle" data-theme-toggle>Light</button></div>'
                f'<a class="drawn" href="{prefix}about.html"><img src="{prefix}assets/brand/kai-badge-160.png" alt="" width="34" height="34"><span><small>Drawn by</small><b>Kai Thought Architect</b></span><em>About me &rarr;</em></a></div></nav>')
        mbar = (f'<header class="mbar"><a class="brand" href="{prefix}index.html">{self.mark}<span class="wm" role="img" aria-label="Topping Out"><b aria-hidden="true">Topping</b><b class="out" aria-hidden="true">Out</b></span></a>'
                f'<span class="where">{esc(here)}</span><button type="button" data-plan aria-expanded="false">Site plan</button></header>')
        return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
                f'<title>{esc(title)}</title><meta name="description" content="{esc(description)}">{SHARE_MARK}'
                f'{self.icon}{THEME_HEAD}{FONTS}<style>{BASE_CSS}{css}</style></head><body>'
                f'<div class="site">{plan}<div class="mainc">{mbar}{body}</div></div>'
                + SHELL_JS + THEME_TAIL + WELCOME_JS + "</body></html>\n")

    def foot(self) -> str:
        return '<footer class="site-foot"><span>Topping Out</span><span>MIT licence</span><span>' + DOMAIN + '</span></footer>'

    def framed(self, sheet: str, title: str, description: str, raw: str) -> str:
        body = f'<iframe class="frame" src="{raw}" title="{esc(title)}"></iframe>'
        return self.page(f"{title} · Topping Out", description, FRAME_CSS, sheet, body)

    # ---------- the Order of works sheet ----------

    def order(self) -> str:
        """The Order of works on one screen, like the Playbooks: a tab per stage, its steps on the left, the step being read on
        the right: the step in short, then build_flow.py's smaller steps, unchanged."""
        phases = flow_phases()
        flat = {t: (a, d, tags, w) for _p, _n, _s, _o, st in phases for a, t, d, tags, w in st}
        placed = [x for v in ORDER_MAP.values() for x in v]
        if sorted(placed) != sorted(flat) or len(placed) != len(set(placed)):
            raise SystemExit(f"build_site: ORDER_MAP and build_flow.py disagree: {sorted(set(flat) ^ set(placed))}")
        role_name = {"foreman": "Foreman", "builder": "Builder", "inspectors": "Inspectors", "you": "You"}

        def tagh(kind, label):
            if kind == "skill" and label in self.by:
                return f'<a href="{self.href(label, "")}">/{esc(label)}</a>'
            if kind == "agent" and f"agents/{label}" in self.by:
                return f'<a href="{self.href("agents/" + label, "")}">{esc(label)}</a>'
            if kind == "opt":
                return f"<em>{esc(label)}</em>"
            return f"<code>{'$ ' if kind == 'tool' else ''}{esc(label)}</code>"

        def icon(ic, cls=""):
            return f'<svg{f" class={cls}" if cls else ""} viewBox="0 0 24 24" aria-hidden="true">{STEP_ICONS[ic]}</svg>'

        stages = [("once", "Once per project", "Plan, check, cut", FRONT["route_once"], "plan"),
                  ("every", "For every ticket", "One job, one PR", FRONT["route_loop"], "hat")]
        steps = []  # (stage key, stage title, number, step, slug)
        i = 0
        for key, title, _sub, items, _ic in stages:
            for step, _who, _w, _ids in items:
                i += 1
                steps.append((key, title, i, step, re.sub(r"[^a-z]+", "-", step.lower()).strip("-")))

        def nav_btn(j, left, label=None):
            _k, _t, num, step, slug = steps[j]
            return (f'<button type="button" data-open="{slug}"><span>{"&larr; Previous" if left else "Next &rarr;"}</span>'
                    f'<small>{esc(label or f"{num:02d} {step}")}</small></button>')

        pages, rows = {"once": [], "every": []}, {"once": [], "every": []}
        for j, (key, title, num, step, slug) in enumerate(steps):
            ic, _what, reads, writes, _rule, _mem = STEP_NOTES[step]
            what, rule = STEP_SHORT[step]
            roles, words, subs = [], [], []
            for k, ft in enumerate(ORDER_MAP[step], 1):
                a, _d, tags, w = flat[ft]
                d, w = ORDER_SHORT[ft], ORDER_WORDS.get(ft, w)
                r = ACTOR_ROLE[a]
                if r not in roles:
                    roles.append(r)
                if w:
                    words.append((ft, w))
                tg = "".join(tagh(x, l) for x, l in tags)
                subs.append(f'<li class="osub"><span class="sn"><span class="sh sh-{r}" aria-hidden="true"></span>{num:02d}.{k}</span><div><h6>{esc(ft)}<small>{role_name[r]}</small></h6><p>{esc(d)}</p>'
                            + (f'<div class="otags">{tg}</div>' if tg else "")
                            + (f'<div class="oword"><i>Your word</i>&ldquo;{esc(w)}&rdquo;</div>' if w else "") + "</div></li>")
            who = "".join(f'<b class="r-{r}"><span class="sh sh-{r}" aria-hidden="true"></span>{role_name[r]}</b>' for r in roles)
            note = ORDER_NOTES.get(step)
            first = j == 0 or steps[j - 1][0] != key
            mine = [s for s in steps if s[0] == key]
            prev_ = nav_btn(j - 1, True) if j > 0 else "<span></span>"
            next_ = nav_btn(j + 1, False) if j + 1 < len(steps) else nav_btn(len(stages[0][3]), False, f"{len(stages[0][3]) + 1:02d} Start the shift, next job")
            pages[key].append(
                f'<section class="spage" id="{slug}"{"" if first else " hidden"}><div class="sbar"><span>{esc(title)} · step {num:02d}</span>'
                f'<span>{mine.index(steps[j]) + 1} / {len(mine)}</span></div>'
                f'<div class="shd">{icon(ic)}<div><h4>{esc(step)}</h4><div class="who">{who}</div></div></div><div class="body">'
                f'<p class="lead">{inline(what)}</p>'
                f'<dl class="orw"><dt>Reads &larr;</dt><dd>{inline(reads)}</dd><dt>Writes &rarr;</dt><dd>{inline(writes)}</dd></dl>'
                f'<p class="orule"><b>Rule</b><span>{inline(rule)}</span></p>'
                + (f'<div class="oyour"><b>Your word <small>or your /goal</small></b><ul>' + "".join(f"<li><q>{esc(w)}</q><span>at {esc(ft)}</span></li>" for ft, w in words) + "</ul></div>" if words else "")
                + (f'<p class="oloop"><b>{esc(note[0])}</b><span>{esc(note[1])}</span></p>' if note else "")
                + f'<h5 class="osh">Step by step</h5><ol class="osubs">{"".join(subs)}</ol></div><div class="snav">{prev_}{next_}</div></section>')
            rows[key].append(f'<li><button type="button" class="srow{" on" if first else ""}" data-open="{slug}"><span class="sno">{num:02d}</span>{icon(ic)}'
                             f'<b>{esc(step)}</b>' + ('<i class="yw" title="Waits for your word"></i>' if words else "") + "</button></li>")

        def pane(key, title, first):
            side = (f'<ul>{"".join(rows[key])}</ul><p class="key"><i aria-hidden="true"></i>Waits for your word, or your /goal</p>')
            return (f'<div class="pane" data-role="{key}" role="tabpanel" aria-label="{title}"{"" if first else " hidden"}>'
                    f'<nav class="side" aria-label="{title}: steps">{side}</nav><div class="reader">{"".join(pages[key])}</div></div>')

        def tabb(key, title, sub, ic, first, extra=""):
            return (f'<button type="button" class="tab f{extra}" role="tab" id="{key}" data-rtab="{key}" aria-selected="{"true" if first else "false"}">'
                    f'{icon(ic, "si")}<span><b>{title}</b><span>{sub}</span></span></button>')

        arrow = '<svg viewBox="0 0 44 14" aria-hidden="true"><path d="M2 7h36" stroke="currentColor" stroke-width="2.5"/><path d="M34 2l6 5-6 5" fill="none" stroke="currentColor" stroke-width="2.5"/></svg>'
        flow = f'<div class="flow" aria-hidden="true"><div>{arrow}</div><div>Then each ticket</div></div>'
        book = '<rect x="4" y="3" width="16" height="18" fill="#F4F4EF" stroke="#101316" stroke-width="1.8"/><path d="M8 8h8M8 12h8M8 16h5" stroke="#101316" stroke-width="1.6"/>'
        STEP_ICONS.setdefault("book", book)
        words_pane = ('<div class="pane full" data-role="words" role="tabpanel" aria-label="Words used" hidden><div class="reader">'
                      '<section class="spage" id="words-list"><div class="sbar"><span>Words used on this page</span></div><h4>Words used</h4><dl class="gl">'
                      + "".join(f"<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>" for k, v in GLOSSARY) + "</dl></section></div></div>")
        body = (f'<main id="order" data-desk><div class="wrap"><header class="rhead2"><span class="eyebrow">Sheet {sheet_no("route.html")} · Order of works</span><h1>Order of works</h1>'
                f'<p class="lede">From idea to merged job: {len(stages[0][3])} steps once per project, then {len(stages[1][3])} per ticket. Pick one.</p></header>'
                f'<div class="tabs" role="tablist" aria-label="Stages">{tabb("once", "Once per project", stages[0][2], "plan", True)}{flow}'
                f'{tabb("every", "For every ticket", stages[1][2], "hat", False, " b")}'
                f'<button type="button" class="tab y" role="tab" id="words" data-rtab="words" aria-selected="false">{icon("book", "si")}<span><b>Words</b><span>Glossary</span></span></button></div>'
                f'<div class="desk">{pane("once", "Once per project", True)}{pane("every", "For every ticket", False)}{words_pane}</div>'
                '</div></main>' + self.foot() + ROLES_JS)
        return self.page("Order of works · Topping Out", "Every step from an idea to a merged job: the 11 steps, each opening into exactly what happens.",
                         ROLES_CSS + ORDER_DESK_CSS, "route.html", body, subs=[("#once", "Once per project"), ("#every", "For every ticket"), ("#words", "Words used")])

    def about(self) -> str:
        """Who drew the plans: the owner, and the systems Topping Out grew from, as the floors of a building."""
        A = ABOUT
        links = "".join(f'<a class="alink" href="{esc(u)}" rel="me noopener" target="_blank">{esc(t)} &#8599;</a>' for t, u in A["links"])
        body = (f'<main class="ab"><div class="wrap"><header class="abh"><img class="abadge" src="assets/brand/kai-badge-320.png" alt="Kai Thought Architect\'s badge" width="160" height="160">'
                f'<div><span class="eyebrow">Drawn by</span><h1>{esc(A["name"])}</h1><p class="abline">{esc(A["line"])}</p><div class="alinks">{links}</div></div></header>'
                f'<p class="lede">{esc(A["intro"])}</p>'
                f'<h2 class="abst">How they stack up</h2><p class="abfix">Each floor fixed what the one below couldn&rsquo;t.</p><div class="tower"><span class="tflag" aria-hidden="true">{self.mark}</span>'
                f'<ol class="floors">{about_floors()}</ol><div class="slab"><b>Foundations</b> · from early 2024: the systems before Pathfinder. Their names are buried; their lessons aren&rsquo;t.</div></div>'
                f'<p class="abnext">{esc(A["next"])} <a href="route.html">See how Topping Out works &rarr;</a></p>'
                '</div></main>' + self.foot())
        return self.page("About · Topping Out", "Kai Thought Architect, who drew Topping Out, and the systems it grew from.", ABOUT_CSS, "about.html", body)

    def board(self) -> str:
        keys = "".join(f'<li data-hl="{i}" tabindex="0"><svg viewBox="0 0 72 48" aria-hidden="true">{svg}</svg><div><b><span class="kn">{i}</span>{esc(h)}</b><span>{esc(d)}</span></div></li>'
                       for i, (h, d, svg) in enumerate(BOARD_KEYS, 1))
        raw = RAW["board"][0]
        body = (f'<main><div class="wrap"><header class="bhead"><span class="eyebrow">Sheet {sheet_no("board.html")}</span><h1>Example board</h1>'
                '<p class="lede">Your project board: one file, <code>BOARD.json</code>, drawn by <code>/f-board</code> after every event. Below is a made-up project a few weeks in, drawn by the real renderer.</p>'
                '<span class="bsyn">Made-up project · synthetic data</span></header>'
                f'<h2 class="bhow">How to read it <small>point at a card to light it up on the board</small></h2><ol class="bkeys">{keys}</ol>'
                '<p class="bkeep"><span class="bsign"><b>Rule</b><span>Nobody edits it by hand: every change is an event, and bumps the version.</span></span>'
                '<a href="skills/f-board.html">How /f-board keeps it &rarr;</a></p>'
                '<p class="btop"><b>When every bone is done</b> the board tops out: it is frozen as the project&rsquo;s record, and the next board starts from it.</p>'
                f'<div class="bframe"><div class="bfh"><span>The board itself</span><a href="{raw}">Open it full screen &#8599;</a></div>'
                f'<iframe class="frame" id="boardframe" src="{raw}" title="Example project board"></iframe></div></div></main>' + self.foot() + BOARD_JS)
        return self.page("Example board · Topping Out", "What a Topping Out project board looks like, and how to read it: a made-up project with synthetic data.",
                         BOARD_CSS, "board.html", body, subs=[("#boardframe", "The board itself")])

    def playbooks(self) -> str:
        """Who does what, on one screen: a tab per role, its job and playbook sections on the left, the one being read on the right.
        Only the reader scrolls, and nothing changes size when you pick something."""
        roles = method_roles()
        secs, ideas = pb_sections()

        def lst(xs):
            return "".join(f"<li>{inline(x)}</li>" for x in xs)

        def idea(bk):
            words = re.sub(r"\*\*", "", ideas[bk][0][1][0]).split()
            return f'{esc(" ".join(words[:3]))} <em>{esc(" ".join(words[3:]))}</em>'

        def job(role, never_h, note):
            def dn(does, never):
                return (f'<div class="dn"><div class="do"><h3>Does</h3><ul>{lst(does)}</ul></div>'
                        f'<div class="no"><h3>{never_h}</h3><ul>{lst(never)}</ul></div></div>')
            return (f'<div class="pl">{dn(*PLAIN_ROLES[role])}</div><div class="ex">{dn(*roles[role])}</div>'
                    + (f'<p class="jobnote">{note}</p>' if note else ""))

        # every page in reading order across the three roles: (role key, role title, id, short name, kicker, body html, rule count)
        order, sources = [], {}
        for key, role, bk, title in (("f", "foreman", "F", "Foreman"), ("b", "builder", "B", "Builder"), ("y", "owner", "", "You")):
            mine = [(name, kicker, bl) for k, name, kicker, bl in secs if k == bk] if bk else []
            note = f"Its playbook has {len(mine)} sections, listed on the left. It reads all of them at the start of every job." if bk else ""
            sources[f"{key}-job"] = repr(roles[role])
            order.append((key, title, f"{key}-job", "Job description", "", job(role, "Never" if bk else "Never has to", note), 0))
            for name, kicker, bl in mine:
                short = re.sub(r"\s*\(.*\)$", "", name)
                body, n = reader_html(bl)
                pid = f'{bk.lower()}-{re.sub(r"[^a-z]+", "-", short.lower()).strip("-")}'
                sources[pid] = repr(bl)
                order.append((key, title, pid, short, kicker, f'<div class="body"><div class="pl">{plain_html(PLAIN.get(pid, []))}</div><div class="ex">{body}</div></div>', n))

        plain_check(sources)
        flat = {t: w for _p, _n, _s, _o, st in flow_phases() for _a, t, _d, _tags, w in st}
        wrows = []
        for step, *_r in FRONT["route_once"] + FRONT["route_loop"]:
            for ft in ORDER_MAP[step]:
                w = ORDER_WORDS.get(ft, flat[ft])
                if w:
                    slug = re.sub(r"[^a-z]+", "-", step.lower()).strip("-")
                    tags = "".join(f"<q>{esc(x.strip())}</q>" for x in re.split(r"\s*[\u00b7]\s*", w))
                    wrows.append(f'<li><span class="wq">{tags}</span><a href="route.html#{slug}"><b>{esc(step)}</b> &middot; {esc(ft)}</a></li>')
        order.append(("y", "You", "y-words", "Your words", "",
                      '<div class="body"><p class="lead">Nothing on this list happens without your word. In an autonomous run, your <code>/goal</code> stands in for most of them; '
                      '<code>RULES.md</code> lists which.</p><ul class="ywords">' + "".join(wrows) + "</ul></div>", 0))

        def nav_btn(j, arrow_left):
            key, title, pid, short, *_ = order[j]
            name = f"{title}: job description" if short == "Job description" else short
            return (f'<button type="button" data-open="{pid}"><span>{"&larr; Previous" if arrow_left else "Next &rarr;"}</span><small>{esc(name)}</small></button>')

        pages = {"f": [], "b": [], "y": []}
        rows = {"f": [], "b": [], "y": []}
        for j, (key, title, pid, short, kicker, body, n) in enumerate(order):
            mine = [o for o in order if o[0] == key]
            i = [o[2] for o in mine].index(pid)
            first = i == 0
            head = (idea({"f": "F", "b": "B"}[key]) if key != "y" else "You <em>decide.</em>") if first else esc(short)
            label = f"{title} · job description" if first else (f"{title} · your part" if key == "y" else f"{title} · playbook" + (f" · {esc(kicker)}" if kicker else ""))
            prev_ = nav_btn(j - 1, True) if j > 0 else "<span></span>"
            next_ = nav_btn(j + 1, False) if j + 1 < len(order) else "<span></span>"
            pages[key].append(f'<section class="spage" id="{pid}"{"" if first else " hidden"}><div class="sbar"><span>{label}</span>'
                              + (f"<span>{i} / {len(mine) - 1}</span>" if not first else "") + f'</div><h4{" class=idea1" if first else ""}>{head}</h4>{body}'
                              + f'<div class="snav">{prev_}{next_}</div></section>')
            if first:
                rows[key].append(f'<li><button type="button" class="srow job on" data-open="{pid}"><b>Job description</b><i>does / never</i></button></li>')
            else:
                rows[key].append(f'<li><button type="button" class="srow" data-open="{pid}"><b>{esc(short)}</b></button></li>')

        def pane(key, src, title, first):
            exact = f"<code>{esc(src)}</code>, word for word" if src else "<code>METHOD.md</code>, word for word"
            side = (f'<div class="wsw" role="group" aria-label="Wording"><button type="button" data-w="pl" aria-pressed="true">Plain</button>'
                    f'<button type="button" data-w="ex" aria-pressed="false">Exact wording</button></div>'
                    f'<p class="wnote"><span class="pl">Short and plain, written for this page.</span><span class="ex">{exact}.</span></p>'
                    f'<ul>{rows[key][0]}</ul>')
            if len(rows[key]) > 1:
                side += f'<h3>{"Your part" if key == "y" else "Its playbook"}</h3><ul>{"".join(rows[key][1:])}</ul>'

            return (f'<div class="pane" data-role="{key}" role="tabpanel" aria-label="{title}"{"" if first else " hidden"}>'
                    f'<nav class="side" aria-label="{title}: job and playbook">{side}</nav><div class="reader">{"".join(pages[key])}</div></div>')

        def tabb(key, icon, title, sub, first):
            return (f'<button type="button" class="tab {key}" role="tab" data-rtab="{key}" aria-selected="{"true" if first else "false"}">'
                    f'{ROLE_ICONS[icon]}<span><b>{title}</b><span>{sub}</span></span></button>')

        arrow_r = '<svg viewBox="0 0 44 14" aria-hidden="true"><path d="M2 7h36" stroke="currentColor" stroke-width="2.5"/><path d="M34 2l6 5-6 5" fill="none" stroke="currentColor" stroke-width="2.5"/></svg>'
        arrow_l = '<svg viewBox="0 0 44 14" aria-hidden="true"><path d="M42 7H6" stroke="currentColor" stroke-width="2.5"/><path d="M10 2l-6 5 6 5" fill="none" stroke="currentColor" stroke-width="2.5"/></svg>'
        flow = f'<div class="flow" aria-hidden="true"><div>{arrow_r}Work order</div><div>{arrow_l}Report</div></div>'
        body = (f'<main id="roles" data-desk><div class="wrap"><header class="rhead2"><span class="eyebrow">Sheet {sheet_no("playbooks.html")} · Playbooks</span><h1>Who does what</h1>'
                '<p class="lede">Three roles: the foreman thinks and checks, the builder builds, you decide.</p></header>'
                f'<div class="tabs" role="tablist" aria-label="Roles">{tabb("f", "foreman", "Foreman", "Plans, writes, reviews", True)}{flow}'
                f'{tabb("b", "builder", "Builder", "Builds what is written", False)}{tabb("y", "you", "You", "Decides", False)}</div>'
                f'<div class="desk">{pane("f", "Foreman-Playbook.md", "Foreman", True)}'
                f'{pane("b", "Builder-Playbook.md", "Builder", False)}{pane("y", "", "You", False)}</div>'
                '</div></main>' + self.foot() + ROLES_JS)
        return self.page("Playbooks · Topping Out", "Who does what: the foreman's, the builder's and your job, and the playbook each role follows.",
                         ROLES_CSS, "playbooks.html", body, subs=[("#roles", "Who does what")])

    # ---------- your repo: a site plan of the folders Topping Out adds, from SETUP.md section 2 ----------

    def repo(self) -> str:
        """Your repo on one screen, like the other sheets: a Folders tab (an explorer on the left, the folder being read on the
        right: what it holds, who makes it, what is inside, which job moments touch it) and a Follow a job tab (the moments in order)."""
        R = repo_plan()
        nodes = R["nodes"]
        by_id = {n["id"]: n for n in nodes}
        kids = {n["id"]: [] for n in nodes}
        stack = []
        for n in nodes:
            while stack and stack[-1]["depth"] >= n["depth"]:
                stack.pop()
            n["parent"] = stack[-1]["id"] if stack else None
            if stack:
                kids[stack[-1]["id"]].append(n["id"])
            stack.append(n)

        def is_who(w):  # the right-hand column of SETUP.md's tree says who makes a thing, or when it appears
            return bool(w) and (w == "install" or w.startswith("you") or w.startswith("/"))

        def maker(w):
            out = []
            for part in [x.strip() for x in re.split(r",\s*(?=/|checked)", w) if x.strip()]:
                m = re.match(r"(checked by )?/(f-[\w-]+|[\w-]+)$", part)
                if m and m.group(2) in self.built:
                    out.append(f'<a href="{self.href(m.group(2), "")}">{esc(("checked by " if m.group(1) else "") + "/" + m.group(2))}</a>')
                elif part == "install":
                    out.append("<span>Installed</span>")
                elif part.startswith("you"):
                    out.append(f'<span class="you">{esc(cap(part))}</span>')
                else:
                    out.append(f"<span>{esc(part)}</span>")
            return "".join(out)

        side_ids = [n["id"] for n in nodes if n["depth"] <= 2]
        page_ids = set(side_ids)
        sid = {i: f"n{i}" for i in by_id}
        moments = R["steps"]
        mid = [f"job-{k}" for k in range(1, len(moments) + 1)]
        touch = {}
        for k, s in enumerate(moments):
            for i in s["nodes"]:
                touch.setdefault(i, []).append(k)

        folder = '<path d="M2 6h7l2 2h11v12H2Z" fill="#FBB401" stroke="#101316" stroke-width="1.8" stroke-linejoin="round"/>'
        file_ = '<path d="M5 2h10l4 4v16H5Z" fill="#F4F4EF" stroke="#101316" stroke-width="1.8" stroke-linejoin="round"/><path d="M8 11h8M8 15h8M8 19h5" stroke="#101316" stroke-width="1.4"/>'

        def ico(n, cls="ico"):
            return f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true">{folder if n["dir"] else file_}</svg>'

        def crumb(n):
            chain, x = [], n
            while x:
                chain.append(x)
                x = by_id.get(x["parent"]) if x["parent"] is not None else None
            out = [esc(R["root"])]
            for a in reversed(chain[1:]):
                nm = esc(a["name"].rstrip("/")) + "/"
                out.append(f'<button type="button" data-open="{sid[a["id"]]}">{nm}</button>' if a["id"] in page_ids else nm)
            return "".join(out) + esc(n["name"])

        def inside(i, d=0):
            rows = []
            for c in kids[i]:
                n = by_id[c]
                w = n["who"]
                ds = (inline(n["desc"]) if n["desc"] else "") + (f'<em>{"made by" if is_who(w) else "when"}: <span style="text-transform:none;letter-spacing:0;font-family:Public Sans,sans-serif;font-size:12.5px">{esc("the install" if w == "install" else w)}</span></em>' if w else "")
                nm = (f'<button type="button" class="nm{" dir" if n["dir"] else ""}" data-open="{sid[c]}">{esc(n["name"])} &rarr;</button>' if c in page_ids
                      else f'<span class="nm{" dir" if n["dir"] else ""}">{esc(n["name"])}</span>')
                rows.append(f'<li style="--d:{d}">{nm}<span class="ds">{ds}</span></li>')
                rows += inside(c, d + 1)
            return rows

        def nav_btn(ids, labels, j, left):  # a long file list shows its first name; the full name stays in the title
            full = labels[j]
            short = re.sub(r"\s*\(.*\)$", "", full).split(", ")[0] + (" &hellip;" if ", " in full else "")
            return (f'<button type="button" data-open="{ids[j]}" title="{esc(full)}"><span>{"&larr; Previous" if left else "Next &rarr;"}</span>'
                    f'<small class="navname">{esc(short).replace("&amp;hellip;", "&hellip;")}</small></button>')

        # the Folders pane
        f_ids = [sid[i] for i in side_ids]
        f_lab = [by_id[i]["name"] for i in side_ids]
        f_pages, f_rows = [], []
        for j, i in enumerate(side_ids):
            n = by_id[i]
            w = n["who"]
            chips = (maker(w) if is_who(w) else (f"<span>{esc(w)}</span>" if w else ""))
            ins = inside(i)
            jumps = "".join(f'<button type="button" data-open="{mid[k]}"><b>{k + 1:02d}</b>{inline(moments[k]["when"])}</button>' for k in touch.get(i, []))
            # a moment row inside the day folder is listed under its folder, so its jumps belong to the folder too
            prev_ = nav_btn(f_ids, f_lab, j - 1, True) if j > 0 else "<span></span>"
            next_ = nav_btn(f_ids, f_lab, j + 1, False) if j + 1 < len(f_ids) else "<span></span>"
            f_pages.append(
                f'<section class="spage" id="{sid[i]}"{" hidden" if j else ""}><div class="sbar"><span class="crumb">{crumb(n)}</span><span>{j + 1} / {len(f_ids)}</span></div>'
                f'<div class="rhd">{ico(n)}<div><h4>{esc(n["name"])}</h4></div></div><div class="body">'
                + ('<dl class="orw">' + (f'<dt>Holds</dt><dd>{inline(cap(n["desc"]))}.</dd>' if n["desc"] else "")
                   + (f'<dt>Made by</dt><dd class="chips">{chips}</dd>' if chips else "") + "</dl>" if n["desc"] or chips else "")
                + (f'<div class="kb2"><h5>Inside</h5><ul class="inside">{"".join(ins)}</ul></div>' if ins else "")
                + (f'<div class="kb2"><h5>Where a job touches it</h5><div class="jumps">{jumps}</div></div>' if jumps else "")
                + f'</div><div class="snav">{prev_}{next_}</div></section>')
            d = n["depth"]
            f_rows.append(f'<li><button type="button" class="srow d{d}{" on" if not j else ""}" data-open="{sid[i]}">{ico(n, "")}<b>{esc(n["name"])}</b>'
                          + (f'<i>{len(kids[i])}</i>' if kids[i] else "") + "</button></li>")

        # the Follow a job pane
        mname = [REPO_MOMENTS.get(s["when"], s["when"]) for s in moments]
        m_lab = [re.sub(r"[`()]", "", w) for w in mname]

        def listed(i):  # the nearest folder with its own page: a deeper file shows its parent
            while i is not None and i not in page_ids:
                i = by_id[i]["parent"]
            return i
        m_pages, m_rows = [], []
        for k, s in enumerate(moments):
            seen = []
            for i in s["nodes"]:
                f = listed(i)
                if f is not None and f not in seen:
                    seen.append(f)
            lands = "".join(f'<button type="button" data-open="{sid[i]}">{ico(by_id[i], "")}<code>{esc(by_id[i]["name"])}</code></button>' for i in seen)
            prev_ = nav_btn(mid, m_lab, k - 1, True) if k > 0 else "<span></span>"
            next_ = nav_btn(mid, m_lab, k + 1, False) if k + 1 < len(mid) else "<span></span>"
            m_pages.append(
                f'<section class="spage" id="{mid[k]}"{" hidden" if k else ""}><div class="sbar"><span>Follow a job · moment {k + 1}</span><span>{k + 1} / {len(mid)}</span></div>'
                f'<div class="rhd"><div class="mbig">{k + 1:02d}</div><h4 class="mt">{inline(mname[k])}</h4></div><div class="body">'
                f'<dl class="orw"><dt>What appears</dt><dd>{inline(cap(s["what"]))}.</dd><dt>Where</dt><dd>{inline(cap(s["where"]))}.</dd></dl>'
                + (f'<div class="kb2"><h5>Show in Folders &rarr;</h5><div class="jumps">{lands}</div></div>' if lands else "")
                + f'</div><div class="snav">{prev_}{next_}</div></section>')
            m_rows.append(f'<li><button type="button" class="srow mo{" on" if not k else ""}" data-open="{mid[k]}"><span class="mno">{k + 1:02d}</span><b>{inline(mname[k])}</b></button></li>')

        def pane(key, title, rows, pages, first):
            return (f'<div class="pane" data-role="{key}" role="tabpanel" aria-label="{title}"{"" if first else " hidden"}>'
                    f'<nav class="side" aria-label="{title}"><ul>{"".join(rows)}</ul></nav><div class="reader">{"".join(pages)}</div></div>')

        def tabb(key, title, sub, svg, first, cls):
            return (f'<button type="button" class="tab {cls}" role="tab" id="{key}" data-rtab="{key}" aria-selected="{"true" if first else "false"}">'
                    f'<svg class="si" viewBox="0 0 24 24" aria-hidden="true">{svg}</svg><span><b>{title}</b><span>{sub}</span></span></button>')

        hat = STEP_ICONS["hat"]
        body = (f'<main id="repo" class="rp" data-desk><div class="wrap"><header class="rhead2"><span class="eyebrow">Sheet {sheet_no("repo.html")} · Your repo</span><h1>Your repo</h1>'
                '<p class="lede">Every folder Topping Out adds, and what makes it.</p>'
                '<p class="never"><i aria-hidden="true"></i><b>Not in here</b><span>Your product\'s code. It&rsquo;s built in its own copy and reaches <code>main</code> only by pull request.</span></p>'
                '<p class="rmode">Two repos? <code>.claude/</code> and <code>foreman/</code> go in the records repo.</p></header>'
                f'<div class="tabs" role="tablist" aria-label="Views">{tabb("folders", "Folders", f"{len(side_ids)} places", folder, True, "f")}'
                f'{tabb("follow", "Follow a job", f"{len(moments)} moments, in order", hat, False, "b")}</div>'
                f'<div class="desk">{pane("folders", "Folders", f_rows, f_pages, True)}{pane("follow", "Follow a job", m_rows, m_pages, False)}</div>'
                '</div></main>' + self.foot() + ROLES_JS)
        return self.page("Your repo · Topping Out", "A site plan of every folder Topping Out adds to your repo, and where one job's files appear.",
                         ROLES_CSS + REPO_DESK_CSS, "repo.html", body, subs=[("#folders", "Folders"), ("#follow", "Follow a job")])

    def requirements(self) -> str:
        """The requirements as a site induction: the kit sits in four levels (the ground, the crew, the site, the paperwork),
        you tap what you have, and your pass fills; a full pass is cleared for site and hands you the two install lines.
        Without JavaScript it is a plain list of the kit."""
        F = FRONT
        by = {r[2]: r for r in F["req_core"]}
        levels = [("ground", "The ground", "The machine and its shells.", ["Windows 11", "Git Bash", "PowerShell"]),
                  ("crew", "The crew", "Who plans and who builds.", ["Claude Code", "Pi"]),
                  ("site", "The site", "Where they work, and who checks it.", ["Orca", "Greptile", "OpenRouter"]),
                  ("paper", "The paperwork", "Where the records live and what fetches them.", ["Git", "GitHub and gh", "Node", "Python 3"])]
        assert sorted(n for *_, ns in levels for n in ns) == sorted(by), "build_site: every requirement sits in one level"

        mark = brand_mark

        def tile(row, key):
            m, colour, name, role, why = row
            return (f'<li class="kit" data-k="{esc(key)}"><button type="button" aria-pressed="false">{mark(m, colour)}<b>{esc(name)}</b>'
                    f'<span class="role">{esc(role)}</span><p>{inline(why)}</p><i class="got" aria-hidden="true">Got it</i></button></li>')

        blocks = []
        for lid, title, sub, names in levels:
            rows = "".join(tile(by[n], n) for n in names)
            extra = ""
            if lid == "crew":
                builders = "".join(tile(b, "builder") for b in F["req_builders"])
                builders += tile((None, "", "Another builder", "your pick", "Any agent that reads files, runs a shell, writes a report."), "builder")
                extra = ('<div class="bpick"><h4>And one builder <small>pick one</small></h4>'
                         '<p>It only builds what the foreman settled, so a cheap model will do. I use GLM 5.3.</p>'
                         f'<ul class="kits">{builders}</ul></div>')
            blocks.append(f'<section class="lvl" id="{lid}"><div class="lvh"><span class="lvn">Level {len(blocks) + 1:02d}</span><h2>{esc(title)}</h2><p>{esc(sub)}</p></div>'
                          f'<ul class="kits">{rows}</ul>{extra}</section>')
        total = len(by) + 1
        repo = INSTALL["repo"]
        install = cmd(INSTALL["steps"][0][2]) + '<p class="pthen">Then, in Claude Code, in your repo:</p>' + cmd(INSTALL["steps"][1][2])
        pass_card = (f'<aside class="pass" id="pass" aria-live="polite"><div class="clip" aria-hidden="true"></div><div class="ph">Site induction <span>Topping Out</span></div>'
                     f'<div class="pb"><div class="pname">Kit check</div><div class="pcount"><b class="pn">0</b> / {total}</div>'
                     f'<div class="pbar" aria-hidden="true"><i></i></div><p class="pmsg">Tap each piece of kit you already have.</p>'
                     '<div class="pstamp" aria-hidden="true">Cleared<br>for site</div>'
                     f'<div class="pgo"><p>You&rsquo;re cleared. Two lines and you&rsquo;re on site:</p>{install}</div>'
                     '<button type="button" class="preset">Start again</button></div></aside>')
        body = (f'<main id="req" class="rq"><div class="wrap"><header class="rhead2"><span class="eyebrow">Sheet {sheet_no("requirements.html")} · Requirements</span>'
                f'<h1>Requirements</h1><p class="lede">{inline(F["install_lede"])}</p></header>'
                '<p class="intro"><b>Site induction.</b> Tap the kit you already have.</p>'
                f'<div class="ind"><div class="levels">{"".join(blocks)}</div>{pass_card}</div>'
                '<div class="two"><div class="rno rtest"><h3>Tested on</h3><p><b>Windows 11, with Claude Code as the foreman.</b> macOS and Linux are expected to work, not yet verified.</p><p class="rcloud"><b>Coming</b>A cloud option.</p></div>'
                '<div class="ryours"><h3>Make it yours</h3><p>It&rsquo;s all plain text. Fork it, swap any part, and it&rsquo;s your setup.</p>'
                f'<a class="rfork" href="https://github.com/{esc(repo)}/fork">Fork it on GitHub &#8599;</a></div></div>'
                f'<section id="addon">{addon_html(parts=True)}</section>'
                '<div class="wn" id="windows"><h3>Windows notes</h3><ul>'
                '<li><b>Line endings.</b> Pin LF in the repo (<code>* text=auto eol=lf</code> in <code>.gitattributes</code>) and set <code>core.autocrlf false</code> there.</li>'
                '<li><b>Git Bash rewrites paths,</b> even <code>HEAD:src/app.py</code>. Prefix with <code>MSYS_NO_PATHCONV=1</code>, or run that call from PowerShell.</li>'
                '<li><b>Headless Chrome screenshots</b> need an absolute output path.</li></ul></div>'
                '</div></main>' + REQ_JS + self.foot())
        return self.page("Requirements · Topping Out", "The setup Topping Out is built and run on, as a site induction: tick off the kit you have, and the pass hands you the install lines.",
                         ROLES_CSS + REQ_CSS, "requirements.html", body,
                         subs=[("#ground", "The ground"), ("#crew", "The crew"), ("#site", "The site"), ("#paper", "The paperwork"), ("#addon", "The add-on"), ("#windows", "Windows notes")])

    def logbook(self) -> str:
        """The Logbook on one screen, like the other sheets: the three card types (sections read from their templates), a card's
        life from lesson to rule, the memory skills, and the Logbook's files."""
        lb = ROOT / "foreman" / "logbook"
        readme = (lb / "README.md").read_text(encoding="utf-8")

        def template(kind, folder):
            text = (lb / "entries" / folder / f"{kind}-TEMPLATE.md").read_text(encoding="utf-8")
            secs = re.findall(r"^## (.+?)\n\n(.+?)(?=\n\n|\Z)", text, re.S | re.M)
            if not secs:
                raise SystemExit(f"build_site: no sections in the {kind} template")
            return [(h.strip(), " ".join(b.split())) for h, b in secs]

        insight, method, build = template("INSIGHT", "insights"), template("METHOD", "methods"), template("BUILD", "builds")
        ruled = next((b for h, b in insight if h.startswith("Ruled out")), "")
        insight = [(h, b) for h, b in insight if not h.startswith("Ruled out")]
        if [h for h, _ in insight] != [h for h, _ in INSIGHT_EXAMPLE]:
            raise SystemExit("build_site: the INSIGHT template's sections changed; update INSIGHT_EXAMPLE to match")
        insight = INSIGHT_EXAMPLE
        whens = {}
        for row in re.findall(r"^\| (`/f-.+?`) \| (.+?) \|$", readme, re.M):
            for s in re.findall(r"`/(f-[\w-]+)`", row[0]):
                whens[s] = row[1]
        by = self.by

        def nav_btn(ids, labels, j, left):
            cls = ' class="navname"' if re.fullmatch(r"\S*[/._]\S*", labels[j]) else ""  # a lone file or skill name, not a phrase
            return (f'<button type="button" data-open="{ids[j]}"><span>{"&larr; Previous" if left else "Next &rarr;"}</span>'
                    f'<small{cls}>{esc(labels[j])}</small></button>')

        def skill_chips(text):
            return "".join((f'<a href="{self.href(x, "")}">/{x}</a>' if x in self.built else f"<span>/{esc(x)}</span>") for x in re.findall(r"/(f-[\w-]+)", text))

        def pages_and_rows(items, row_html):
            """items: (id, label, sbar, head html, body html). Returns the reader pages and the side rows."""
            ids, labels = [x[0] for x in items], [x[1] for x in items]
            pages, rows = [], []
            for j, (pid, label, bar, head, body) in enumerate(items):
                prev_ = nav_btn(ids, labels, j - 1, True) if j > 0 else "<span></span>"
                next_ = nav_btn(ids, labels, j + 1, False) if j + 1 < len(ids) else "<span></span>"
                pages.append(f'<section class="spage" id="{pid}"{" hidden" if j else ""}><div class="sbar"><span>{bar}</span><span>{j + 1} / {len(ids)}</span></div>'
                             f'{head}<div class="body">{body}</div><div class="snav">{prev_}{next_}</div></section>')
                rows.append(f'<li><button type="button" class="srow{row_html[j][0]}{" on" if not j else ""}" data-open="{pid}">{row_html[j][1]}</button></li>')
            return pages, rows

        # the cards
        types = [("insight", "INSIGHT", "A lesson or a trap: why something happens.", "entries/insights/", "INSIGHT_20260220_REAIMED_PROBE_HIDES_GAP",
                  [("cluster", "testing"), ("impact", "HIGH"), ("confidence", "85")], insight,
                  "Confidence comes from the evidence: 75 for one instance, 85 for two or more, 95 when it was measured."),
                 ("method", "METHOD", "A way of doing something that worked and can be repeated: how.", "entries/methods/", "METHOD_20260220_BLUEPRINT_THEN_EXECUTE",
                  [("cluster", "development-workflow"), ("impact", "MEDIUM"), ("success_rate", "100")], method,
                  "Success rate: 100 when it was used once and worked, 80 when it is still untried."),
                 ("build", "BUILD", "A short record of what one job built, and what it taught.", "entries/builds/", "BUILD_YYYYMMDD_SHORT_NAME",
                  [("cluster", "billing"), ("impact", "HIGH"), ("scope", "SIGNIFICANT")], build,
                  "Scope is the job's size: MAJOR over 8 hours, SIGNIFICANT 4 to 8, MODERATE 2 to 4, MINOR under 2.")]
        c_items, c_rows = [], []
        for key, name, what, folder, cid, fm, secs, measure in types:
            card = (f'<div class="card ty-{key}"><div class="ch"><b>{name}</b><code>{esc(cid)}</code></div>'
                    f'<div class="fm">' + "".join(f"<span>{k}: <b>{esc(v)}</b></span>" for k, v in fm) + f'<span class="ex">{"an example card" if key == "insight" else "the template"}</span></div>'
                    f'<ol>' + "".join(f"<li><b>{esc(h)}</b><span>{inline(b)}</span></li>" for h, b in secs) + "</ol></div>")
            c_items.append((f"card-{key}", f"{name} card", f"The cards · {name.lower()}",
                            f'<div class="lhd"><span class="mbig" style="background:{ {"insight": "#FBB401", "method": "#9CC6F5", "build": "#9AD7AE"}[key] }">{name[0]}</span><div><h4>{name} card</h4>'
                            f'<div class="lchips"><span class="path">{esc("foreman/logbook/" + folder)}</span></div></div></div>',
                            f'<p class="lead">{esc(what)}</p>{card}<dl class="orw"><dt>How sure</dt><dd>{esc(measure)}</dd>'
                            '<dt>On every card</dt><dd><b>cluster</b>: the area of your product. <b>tags</b>: 3 to 6 keywords. <b>impact</b>: CRITICAL, HIGH, MEDIUM or LOW.</dd></dl>'))
            c_rows.append(("", f'<span class="ty ty-{key}" aria-hidden="true"></span><b>{name}</b>'))
        c_items.append(("card-score", "How a card is checked", "The cards · the check",
                        '<div class="lhd"><span class="mbig">75</span><div><h4>How a card is checked</h4><div class="lchips"><span>out of 100 to pass</span></div></div></div>',
                        '<p class="lead">Every card is scored before you see it. The score catches thin cards; the checks are what matter.</p>'
                        '<ul class="scale"><li><b>start at 50</b><span>Every card.</span></li><li><b>+20</b><span>Every section is filled in.</span></li>'
                        '<li><b>+15</b><span>The evidence is strong: confidence or success rate of 80 or more, or a BUILD card that cites its PR or commit.</span></li>'
                        '<li><b>+10</b><span>It has a concrete example.</span></li><li><b>+5</b><span>It has a counter-example (INSIGHT cards only).</span></li>'
                        '<li class="tot"><b>75 to pass</b><span>Below that, you see the score and what is missing, and choose to fix it or file it anyway.</span></li></ul>'
                        '<p class="lyour"><b>Your word</b><span>You see the whole card first. Nothing is written until you say yes.</span></p>'))
        c_rows.append(("", '<span class="ty ty-score" aria-hidden="true"></span><b>How a card is checked</b>'))
        if ruled:
            c_items.append(("card-ruled", "Ruled out", "The cards · a deliberate no",
                            '<div class="lhd"><span class="mbig" style="background:#C42B1C;color:#fff">&times;</span><div><h4>Ruled out</h4><div class="lchips"><span>an INSIGHT card</span></div></div></div>',
                            '<p class="lead">A card for a firm "no": an option that was weighed and turned down, and that could plausibly come back.</p>'
                            '<div class="kb3"><h5>It records</h5><p><b>Why</b> it was turned down, with the evidence, and <b>Revisit if</b>: the one thing that would reopen it.</p></div>'
                            '<div class="kb3"><h5>Why it matters</h5><p>A turned-down idea that isn\'t written down comes back in the next session as if it were new.</p></div>'))
            c_rows.append(("", '<span class="ty ty-ruled" aria-hidden="true"></span><b>Ruled out</b>'))
        c_pages, c_side = pages_and_rows(c_items, c_rows)

        # a card's life
        life_extra = {1: ("/f-card, or /f-signoff at every close", True, CARD_PRESS), 2: ("/f-card", False, LOGBOOK_GRAPH), 3: ("/f-shift, with /f-search", False, ""),
                      4: ("/f-search, /f-dream", False, ""), 5: ("/f-distill", True, ""), 6: ("/f-archive, /f-archive-search", True, "")}
        asks = {1: "You see the card first. Nothing is filed until you say yes.", 5: "The rule is shown to you first. It is written only with your OK.",
                6: "The archive runs as a dry run first; cards move only on your word."}
        l_items, l_rows = [], []
        for k, (_n, _p, _c, title, text) in enumerate(MEMORY_TOUR):
            sk, _a, extra = life_extra.get(k, ("", False, ""))
            chips = skill_chips(sk)
            track = ('<ol class="ltrack" aria-hidden="true">' + "".join(f'<li class="{"on" if j == k else "past" if j < k else ""}"><button type="button" tabindex="-1" data-open="life-{j + 1}">{j + 1:02d}</button></li>'
                                                                      for j in range(len(MEMORY_TOUR))) + "</ol>")
            l_items.append((f"life-{k + 1}", title, f"A card's life · {k + 1} of {len(MEMORY_TOUR)}",
                            f'{track}<div class="lhd"><span class="mbig">{k + 1:02d}</span><div><h4>{inline(title)}</h4></div></div>',
                            f'<dl class="orw"><dt>What happens</dt><dd>{inline(text)}</dd><dt>Done by</dt><dd class="lchips">{chips or "<span>the foreman</span>"}</dd></dl>'
                            + (f'<p class="lyour"><b>Your word</b><span>{asks[k]}</span></p>' if k in asks else "") + extra))
            l_rows.append(("", f'<span class="mno">{k + 1:02d}</span><b>{inline(title)}</b>'))
        l_pages, l_side = pages_and_rows(l_items, l_rows)

        # the tools: the memory skills, in the order the README lists them
        order = [s for s in dict.fromkeys(whens) if s in by]
        t_items, t_rows = [], []
        for s in order:
            n = by[s]
            t_items.append((f"tool-{s}", "/" + s, "The tools",
                            f'<div class="lhd"><svg class="mbig" viewBox="0 0 24 24" style="padding:9px;background:#F4F4EF" aria-hidden="true">{KIND_ICONS["memory"]}</svg><div><h4 class="mono">{esc(n["label"])}</h4>'
                            f'<div class="lchips">' + (f'<span class="cmd">{esc(n["slash"])}</span>' if n.get("slash") else "") + f'<a href="{self.href(s, "")}">Full page &rarr;</a></div></div></div>',
                            f'<dl class="orw"><dt>Does</dt><dd>{inline(cap(n["blurb"]))}.</dd><dt>When</dt><dd>{inline(cap(whens[s]))}.</dd></dl>'))
            t_rows.append(("", f"<code>/{esc(s)}</code>"))
        t_pages, t_side = pages_and_rows(t_items, t_rows)

        # the files: the logbook folder from SETUP.md's tree
        R = repo_plan()
        top = next(n for n in R["nodes"] if n["name"] == "logbook/")
        inside = []
        for n in R["nodes"][R["nodes"].index(top) + 1:]:
            if n["depth"] <= top["depth"]:
                break
            inside.append(n)
        f_items, f_rows = [], []
        for n in [top] + inside:
            w = n["who"]
            f_items.append((f"file-{n['id']}", n["name"], 'The files · <span class="pth">' + esc(n["path"] or ("foreman/logbook/" + n["name"])) + "</span>",
                            f'<div class="lhd"><svg class="mbig" viewBox="0 0 24 24" style="padding:10px;background:#F4F4EF" aria-hidden="true">'
                            + ('<path d="M2 6h7l2 2h11v12H2Z" fill="#FBB401" stroke="#101316" stroke-width="1.8" stroke-linejoin="round"/>' if n["dir"]
                               else '<path d="M5 2h10l4 4v16H5Z" fill="#F4F4EF" stroke="#101316" stroke-width="1.8" stroke-linejoin="round"/><path d="M8 11h8M8 15h8M8 19h5" stroke="#101316" stroke-width="1.4"/>')
                            + f'</svg><div><h4 class="mono">{esc(n["name"])}</h4></div></div>',
                            ('<dl class="orw">' + (f'<dt>Holds</dt><dd>{inline(cap(n["desc"]))}.</dd>' if n["desc"] else "")
                             + ((f'<dt>Made by</dt><dd class="lchips">{skill_chips(w)}</dd>' if skill_chips(w) else f'<dt>When</dt><dd>{esc(cap(w))}</dd>') if w else "")
                             + "</dl>") if n["desc"] or w else ""))
            f_rows.append((" fl", f'<b style="padding-left:{max(0, n["depth"] - top["depth"]) * 16}px">{esc(n["name"])}</b>'))
        f_pages, f_side = pages_and_rows(f_items, f_rows)

        def pane(key, title, side, pages, first):
            return (f'<div class="pane" data-role="{key}" role="tabpanel" aria-label="{title}"{"" if first else " hidden"}>'
                    f'<nav class="side" aria-label="{title}"><ul>{"".join(side)}</ul></nav><div class="reader">{"".join(pages)}</div></div>')

        def tabb(key, title, sub, svg, first, cls):
            return (f'<button type="button" class="tab {cls}" role="tab" id="{key}" data-rtab="{key}" aria-selected="{"true" if first else "false"}">'
                    f'<svg class="si" viewBox="0 0 24 24" aria-hidden="true">{svg}</svg><span><b>{title}</b><span>{sub}</span></span></button>')

        card_ic = '<rect x="4" y="3" width="16" height="18" fill="#FFFDF6" stroke="#101316" stroke-width="1.8"/><rect x="4" y="3" width="16" height="5" fill="#FBB401" stroke="#101316" stroke-width="1.8"/><path d="M7 12h10M7 15.5h10M7 19h6" stroke="#101316" stroke-width="1.4"/>'
        life_ic = '<circle cx="12" cy="12" r="9" fill="#F4F4EF" stroke="#101316" stroke-width="1.8"/><path d="M12 6v6l4 3" fill="none" stroke="#101316" stroke-width="2"/>'
        file_ic = '<path d="M2 6h7l2 2h11v12H2Z" fill="#FBB401" stroke="#101316" stroke-width="1.8" stroke-linejoin="round"/>'
        body = (f'<main id="logbook" class="lb" data-desk><div class="wrap"><header class="rhead2"><span class="eyebrow">Sheet {sheet_no("logbook.html")} · Logbook</span><h1>Logbook</h1>'
                '<p class="lede">What one job learns, the next starts with.</p>'
                '<ul class="rules3"><li><span><b>Rule</b>Every card carries its evidence and where it came from.</span></li>'
                '<li><span><b>Rule</b>A card never overrides <code>RULES.md</code>.</span></li>'
                '<li><span><b>Rule</b>A card becomes a firm rule only with your word.</span></li></ul></header>'
                f'<div class="tabs" role="tablist" aria-label="The Logbook">{tabb("cards", "The cards", "3 kinds", card_ic, True, "b")}'
                f'{tabb("life", "A card&#39;s life", f"{len(MEMORY_TOUR)} moments", life_ic, False, "f")}'
                f'{tabb("tools", "The tools", f"{len(order)} skills", KIND_ICONS["memory"], False, "f")}'
                f'{tabb("files", "The files", "foreman/logbook/", file_ic, False, "f")}</div>'
                f'<div class="desk">{pane("cards", "The cards", c_side, c_pages, True)}{pane("life", "A card&#39;s life", l_side, l_pages, False)}'
                f'{pane("tools", "The tools", t_side, t_pages, False)}{pane("files", "The files", f_side, f_pages, False)}</div>'
                '</div></main>' + self.foot() + ROLES_JS)
        return self.page("Logbook · Topping Out", "The Logbook: the cards Topping Out keeps, how a lesson becomes a card and then a rule, its skills and its files.",
                         ROLES_CSS + LOGBOOK_DESK_CSS, "logbook.html", body,
                         subs=[("#cards", "The cards"), ("#life", "A card's life"), ("#tools", "The tools"), ("#files", "The files")])

    # ---------- the front page ----------

    def front(self) -> str:
        F, by, steps = FRONT, self.by, self.steps
        script, check = install_facts()
        n_skill, n_agent = self.counts()
        out = ['<main><div class="wrap">']

        # the site board: who runs this site, and the way in
        roster = "".join(f'<div class="{"you" if k == "you" else ""}">{ROLE_ICONS[k]}<dt>{esc(r)}</dt><dd>{inline(line)}</dd></div>' for k, r, line in F["roles"])
        first, then = INSTALL["steps"][0][2], INSTALL["steps"][1][2]
        repo = INSTALL["repo"]
        # D26: three plain points straight under the headline, inside the board
        edge = '<ul class="edge" aria-label="What sets it apart">' + "".join(f'<li><b>{esc(k)}</b><span>{esc(line)}</span></li>' for k, line in F["edge"]) + '</ul>'
        out.append(f'<section class="board" id="access" aria-labelledby="h"><div class="haz" role="presentation"></div>'
                   f'<div class="bh">{self.mark}<div><div class="kick">{esc(F["board_kicker"])}</div>'
                   f'<h1 id="h">{"".join(f"<span>{esc(x)}</span>" for x in F["headline"])}</h1><p class="sub">{esc(F["subline"])}</p><a class="toinst" href="#install">Install &darr;</a></div>'
                   '<div class="jhw"><div class="jh" id="jh" role="img" aria-label="One night on site: by day you plan the floors; in the evening one line starts the shift; through the night a crane builds one floor per job, an inspection rejects a bad block and it is replaced, and each floor is merged; at dawn the tower is topped out with a flag"></div>'
                   '<div class="jcap" id="jcap" aria-hidden="true"><b class="clk">09:00</b><span class="cap"><b>You plan</b> settle each job\'s ticket by day</span>'
                   '<span class="pips"><i class="on"></i><i></i><i></i><i></i><i></i><i></i></span></div>'
                   '</div></div>'
                   f'{edge}{one_job_html()}'
                   f'<div class="bb"><dl class="roster">{roster}</dl>'
                   f'<div class="access" id="install"><span class="al">Install</span><p>Get the package. Needs git, Node and Python.</p>{cmd(first)}'
                   f'<p class="then">Then, in Claude Code, in your repo:</p>{cmd(then)}'
                   '<p class="then2"><code>/f-setup</code> installs what&rsquo;s missing, profiles your repo and asks only what it can&rsquo;t find. It never overwrites or commits.</p>'
                   f'<a class="gh" href="https://github.com/{esc(repo)}"><svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path fill="currentColor" d="{GH_MARK}"/></svg>'
                   f'<span><b>{esc(repo).replace("/", "/<wbr>")}</b><small>Open source on GitHub · MIT</small></span><i aria-hidden="true">&#8599;</i></a></div></div>'
                   f'</section>')

        def sec(n: int, sid: str, title: str, lede: str = "") -> str:
            return (f'<section class="sec" id="{sid}" aria-labelledby="{sid}-h"><div class="sec-h"><span class="n">{n:02d}</span>'
                    f'<h2 id="{sid}-h">{title}</h2>{hoard_sign(sid) if sid in HOARD_SIGNS else ""}</div>' + (f'<p class="lede">{inline(lede)}</p>' if lede else ""))

        # 01 why Topping Out: four pillars
        out.append(sec(1, "pillars", "Why Topping Out", "Named for the day a building's last beam goes on. Here, it's the day every job on a board is done: the project tops out, and the next one starts from it.") + '<div class="hoard" id="hoard"><div class="haz" role="presentation"></div><div class="pillars">' + "".join(
            f'<article class="pil s-{kind}"><div class="sgn"><svg class="pic" viewBox="0 0 200 130" role="img" aria-label="{esc(sign)}">{svg}</svg>'
            f'<div class="cap">{esc(sign)}</div></div>'
            f'<div class="pt"><h3>{esc(ti)}</h3><p class="pw">{inline(w)}</p></div></article>'
            for (ti, w), (kind, sign, svg) in zip(F["pillars"], SIGNS)) + "</div></div>"
            + '<script>(function(){var h=document.getElementById("hoard");if(!h)return;if(!window.IntersectionObserver){h.classList.add("live");return}'
              'new IntersectionObserver(function(es){h.classList.toggle("live",es[0].isIntersecting)}).observe(h)})()</script></section>')

        # 02 the route in plain words: four steps once per project, then seven per ticket, each with who does it
        out.append(sec(2, "route", "Order of works"))
        placed = [s for part in ("route_once", "route_loop") for *_, ids in F[part] for s in ids]
        if sorted(placed) != sorted(steps):
            raise SystemExit(f"build_site: the front page route and the Atlas route disagree: {sorted(set(steps) ^ set(placed))}")
        role_name = {"foreman": "Foreman", "builder": "Builder", "inspectors": "Inspectors", "you": "You"}

        def phases(items, first=1):
            li = []
            for n, (step, who, word, ids) in enumerate(items, first):
                # the owner's steps and the steps that need their word: in an autonomous run, the owner's /goal covers them
                tag = "<em>or your /goal</em>" if who == "you" else "<em>Your word</em><em>or your /goal</em>" if word else ""
                cmds = "".join(f'<a href="{self.href(s, "")}" title="{esc(cap(by[s]["blurb"]))}">/{esc(by[s]["label"])}</a>' for s in ids)
                note = F["route_notes"].get(step, "")
                slug = re.sub(r"[^a-z]+", "-", step.lower()).strip("-")
                ico = f'<svg class="sico" viewBox="0 0 24 24" aria-hidden="true" focusable="false">{STEP_ICONS[STEP_NOTES[step][0]]}</svg>'
                li.append(f'<li><div class="phs{" word" if word else ""}" data-step="{slug}" tabindex="0" role="button" aria-controls="sn-{slug}" aria-pressed="false">'
                          f'<span class="mk" aria-hidden="true"></span><span class="sih">{ico}<i class="sn">{n:02d}</i></span><b class="vb">{esc(step)}</b>'
                          f'<span class="who"><b class="r-{who}">{role_name[who]}</b>{tag}</span>'
                          + (f'<span class="nt">{esc(note)}</span>' if note else "")
                          + (f'<span class="cmds">{cmds}</span>' if cmds else "") + "</div></li>")
            return f'<ol class="track" style="--n:{len(li)}">{"".join(li)}</ol>'

        out.append(f'<div class="rt-h">Once per project: plan it, check it, cut it into tickets</div><div class="once">{phases(F["route_once"])}</div>'
                   f'<div class="shiftbox"><span class="sl">Night shift: job after job, until the list is done</span>'
                   f'<div class="feed">Then, for every ticket: one job, one branch, one PR</div>'
                   f'<div class="loop">{phases(F["route_loop"], len(F["route_once"]) + 1)}<span class="ret">&larr; Next job: a fresh foreman starts here</span><svg class="chev cv-down" viewBox="0 0 15 15" aria-hidden="true" focusable="false"><path d="M2.5 5.5L7.5 10.5L12.5 5.5" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="square"/></svg><svg class="chev cv-left" viewBox="0 0 15 15" aria-hidden="true" focusable="false"><path d="M9.5 2.5L4.5 7.5L9.5 12.5" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="square"/></svg><svg class="chev cv-up" viewBox="0 0 15 15" aria-hidden="true" focusable="false"><path d="M2.5 9.5L7.5 4.5L12.5 9.5" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="square"/></svg>'
                   + WALKER.replace("__WHO__", json.dumps([who for _, who, _, _ in F["route_loop"]])).replace("__SAYS__", json.dumps(WALK_SAYS)) + '</div></div>')
        mname = {k: nm for k, nm, *_ in F["memory"]}
        role_of = {s: w for s, w, *_ in F["route_once"] + F["route_loop"]}

        # one slim caption under the drawing: it follows the walker, or the step you tap
        items = []
        for n, (step, *_rest) in enumerate(F["route_once"] + F["route_loop"], 1):
            ic, _what, rd, wr, _gate, mem = STEP_NOTES[step]
            what, gate = STEP_SHORT[step]
            slug = re.sub(r"[^a-z]+", "-", step.lower()).strip("-")
            chips = "".join(f'<button type="button" class="mchip m-{d}" data-mem="{k}">{"reads" if d == "reads" else "writes"} {"&larr;" if d == "reads" else "&rarr;"} {esc(mname[k])}</button>' for d, k in mem)
            items.append(f'<div class="sitem off" data-step="{slug}"><svg class="snico" viewBox="0 0 24 24" aria-hidden="true">{STEP_ICONS[ic]}</svg>'
                         f'<div class="stx"><b><span class="snum">{n:02d}</span> {esc(step)}</b><p>{inline(what)}</p>'
                         + f'</div><p class="sgate"><span>Rule</span><b>{inline(gate)}</b></p>' + (f'<div class="mchips">{chips}</div>' if chips else "") + '</div>')
        out.append('<div class="strip" id="stepbox" aria-live="polite"><div class="stop"><span class="smode">Now</span>'
                   '<span class="sctl"><button type="button" data-sgo="-1" aria-label="Previous step"><svg viewBox="0 0 20 14" aria-hidden="true"><path d="M9 1L2 7l7 6Z M18 1l-7 6 7 6Z" fill="currentColor"/></svg></button>'
                   '<button type="button" data-play aria-label="Pause"><svg class="ic-pause" viewBox="0 0 14 14" aria-hidden="true"><rect x="2" y="1" width="3.5" height="12" fill="currentColor"/><rect x="8.5" y="1" width="3.5" height="12" fill="currentColor"/></svg><svg class="ic-play" viewBox="0 0 14 14" aria-hidden="true"><path d="M3 1l9 6-9 6Z" fill="currentColor"/></svg></button>'
                   '<button type="button" data-sgo="1" aria-label="Next step"><svg viewBox="0 0 20 14" aria-hidden="true"><path d="M2 1l7 6-7 6Z M11 1l7 6-7 6Z" fill="currentColor"/></svg></button></span>'
                   '<a class="sall" href="route.html">Every detail: the Order of works page &rarr;</a></div>'
                   + '<div class="sitems">' + "".join(items) + '</div></div>' + ORDER_JS + CONVEYOR
                   + f'<p class="catalog"><a href="skills.html">{n_skill} skills, {n_agent} agents: every one has its own page &rarr;</a></p></section>')

        # 03 the night shift: a clock from your plan by day to the summary in the morning
        clock = "".join(f'<li class="ck {kind}"><span class="ckw">{esc(when)}</span><b>{esc(title)}</b><p>{inline(text)}</p>' + (cmd(c) if c else "") + "</li>"
                        for when, title, text, c, kind in F["shift"])
        assert len(RULE_ICONS) == len(F["shift_rules"]), "build_site: one pictogram per shift rule"
        rules = "".join(f'<li>{icon}<span>{inline(r)}</span></li>' for icon, r in zip(RULE_ICONS, F["shift_rules"]))
        out.append(sec(3, "shift", "The night shift") + f'<p class="lede">{inline(F["shift_lede"])}</p>'
                   + NIGHT_STRIP
                   + '<div class="rboard"><div class="rbh"><b>Night shift rules</b><span>All workers · every night</span></div>'
                   + f'<ul>{rules}</ul></div></section>')

        # 04 nothing is lost: what one session hands the next
        band = {"now": "ses", "next": "ses", "project": "job", "forever": "perm", "tool": "tool", "process": "job"}
        nmem = len(F["memory"])
        diag = {"logbook": ("See the Logbook graph", LOGBOOK_GRAPH), "card": ("See the six steps", CARD_PRESS)}
        cards = "".join(f'<article class="mem{' tl' if sc in ('tool', 'process') else ''}" data-m="{k}" id="mem-{k}"><div class="mh"><span class="chip b-{band[sc]}">{"A Logbook tool" if sc == "tool" else "How a card is made" if sc == "process" else "Lasts: " + esc(last.lower())}</span><span class="mn">{i} / {nmem}</span></div>'
                        f'<h3>{esc(nm)}</h3><code>{esc(path)}</code><p>{inline(what)}</p>'
                        f'<dl><dt>{"When" if sc == "tool" else "Who" if sc == "process" else "Written by"}</dt><dd>{inline(wr)}</dd><dt>{"Note" if sc == "tool" else "Never" if sc == "process" else "Read by"}</dt><dd>{inline(rd)}</dd></dl>'
                        + (f'<div class="mx" data-title="{esc(nm)}"><button type="button" class="mdiag">{diag[k][0]} &rarr;</button><div class="mxb">{diag[k][1]}</div></div>' if k in diag else "") + '</article>'
                        for i, (k, nm, path, what, wr, rd, last, sc) in enumerate(F["memory"], 1))
        tourcard = ('<article class="mem tour" hidden><div class="mh"><span class="chip b-job">Follow one lesson</span><span class="tn"></span></div><h3></h3><p></p>'
                    '<div class="mnav"><button type="button" data-next>Next &rarr;</button></div></article>')
        out.append(sec(4, "lost", "Nothing is lost", F["lost_lede"])
                   + f'<div class="memmap" id="memmap"><div class="cutw"><div class="cutsc">{CUTAWAY}</div><div class="hint"><button type="button" data-tour aria-pressed="false">&#9654; Follow one lesson</button><span>or tap any part of the site, or a tool in the office</span></div></div>'
                   f'<div class="mems"><div class="mstack">{cards}{tourcard}</div><div class="mnav"><button type="button" data-go="-1">&larr; Previous</button><button type="button" data-go="1">Next &rarr;</button></div></div></div>'
                   + '<a class="treelink" href="logbook.html">The Logbook in full: the cards, their life, the tools, the files &rarr;</a>'
                   + MEMORY_JS.replace("__TOUR__", json.dumps(MEMORY_TOUR)) + CALLOUT_JS + '</section>')


        # 03 the skeptic, as a site inspection report
        assert len(STICKERS) == len(F["skeptic"]), "build_site: one sticker per skeptic query"
        stickers = "".join(f'<button type="button" class="stk {style}" data-q="{i}" aria-pressed="{"true" if i == 1 else "false"}" aria-controls="ans-{i}"><b>{i:02d}</b>{esc(short)}</button>'
                           for i, (short, style) in enumerate(STICKERS, 1))
        answers = "".join(f'<article class="ans" id="ans-{i}" data-a="{i}"><div class="ah"><span>Site office</span><span>Query {i:02d} of {len(F["skeptic"]):02d}</span></div>'
                          f'<h3>{esc(q)}</h3><p class="lead">{inline(a)}</p><p class="pr"><span>Proof</span><b>{inline(pr)}</b></p><p class="ev">Source: {inline(ev)}</p></article>'
                          for i, (q, a, pr, ev) in enumerate(F["skeptic"], 1))
        out.append(sec(5, "why", "But why not just&hellip;?")
                   + '<div class="office" id="office"><div class="cabin"><div class="roof" aria-hidden="true"></div>'
                   '<div class="plate-so" aria-hidden="true">Site office</div>'
                   '<div class="door" aria-hidden="true"><span class="lamp"></span><span class="win"></span><span class="hinge h1"></span><span class="hinge h2"></span><span class="handle"></span>'
                   '<span class="rule"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="11" fill="#1F5FA8"/><path d="M6 15c0-4 2.7-7 6-7s6 3 6 7Z" fill="#fff"/><rect x="5" y="15" width="14" height="2" fill="#fff"/></svg><span>All visitors<br>report here</span></span><span class="kick"></span></div><div class="step" aria-hidden="true"></div>'
                   f'<div class="stks" role="group" aria-label="Questions a skeptic stuck on the door">{stickers}</div>'
                   '<div class="skid" aria-hidden="true"></div></div>'
                   f'<div class="answers">{answers}<div class="anext"><button type="button">Next question &rarr;</button><span class="tally" aria-live="polite"></span></div></div></div>'
                   '<script>(function(){var o=document.getElementById("office");if(!o)return;o.classList.add("js");'
                   'var b=[].slice.call(o.querySelectorAll(".stk")),a=[].slice.call(o.querySelectorAll(".ans")),tl=o.querySelector(".tally"),cur=1;o.querySelector(".anext button").addEventListener("click",function(){show(String(cur%b.length+1))});'
                   'function show(n){b.forEach(function(x){var on=x.dataset.q===n;x.setAttribute("aria-pressed",on?"true":"false");if(on)x.classList.add("seen")});cur=+n;var k=o.querySelectorAll(".stk.seen").length;tl.textContent=k===b.length?"All "+k+" answered":k+" of "+b.length+" answered";a.forEach(function(x){x.hidden=x.dataset.a!==n})}'
                   'b.forEach(function(x){x.addEventListener("click",function(){show(x.dataset.q)})});show("1")})()</script></section>')

        # 04 install, in full: what the board's two commands need and lay out, then updating, then by hand
        needs = "".join(f"<li><div><b>{esc(k)}</b> <span>{inline(v)}</span></div></li>" for k, v in F["needs"])
        plan = repo_plan()
        fm = [n for n in plan["nodes"] if n["depth"] == 2 and n["path"].startswith("foreman/")]
        tree = "foreman/\n" + "\n".join("  " + esc(n["name"]) for n in fm)  # names only; the repo sheet carries the detail
        upd = INSTALL["steps"][2]
        first, then = INSTALL["steps"][0][2], INSTALL["steps"][1][2]
        by_req = {r[2]: r for r in F["req_core"]}
        tag_order = ["Windows 11", "Git Bash", "PowerShell", "Claude Code", "Pi", "Orca", "Greptile", "OpenRouter", "Git", "GitHub and gh", "Node", "Python 3"]
        assert sorted(tag_order) == sorted(by_req), "build_site: every requirement has a tag on the front page"
        bm, _bc, bname, _bwho, _bwhy = F["req_builders"][0]
        tag_rows = [by_req[n][:4] for n in tag_order]
        tag_rows.insert(tag_order.index("Pi") + 1, (bm, "", bname, "the builder, by Z.ai"))
        req = "".join(f'<li class="ptag{" pb" if nm == bname else ""}" style="--i:{k}">{brand_mark(m, c)}<b>{esc(nm)}</b><span>{esc(role)}</span></li>'
                      for k, (m, c, nm, role) in enumerate(tag_rows))
        opt = "".join(f'<li><b>{esc(k)}</b><span>{inline(v)}</span></li>' for k, v in F["needs_opt"])
        repo = INSTALL["repo"]
        out.append(sec(6, "needs", "Requirements", F["install_lede"])
                   + '<div class="req"><div class="rmine" id="ptags"><h3>My setup <small>Inspected, in use</small></h3>'
                   f'<ul class="ptags">{req}</ul></div>'
                   '<div class="rside"><div class="rno rtest"><h3>Tested on</h3><p><b>Windows 11, with Claude Code as the foreman.</b> macOS and Linux are expected to work, not yet verified.</p><p class="rcloud"><b>Coming</b>A cloud option.</p></div>'
                   '<div class="ryours"><h3>Make it yours</h3><p>It&rsquo;s all plain text. Fork it, swap any part, and it&rsquo;s your setup.</p>'
                   f'<a class="rfork" href="https://github.com/{esc(repo)}/fork">Fork it on GitHub &#8599;</a></div>'
                   '<a class="rmore" href="requirements.html"><b>Every tool, in detail</b><span>What each one does here, and the builders I&rsquo;ve used</span><i aria-hidden="true">&rarr;</i></a></div></div>'
                   + f'<div class="upd">{cmd(upd[2])}<p>{inline(upd[0])}: {inline(upd[1][:1].lower() + upd[1][1:])}</p></div>'
                   + '<details class="byhand"><summary>Prefer to copy the files by hand?</summary>'
                   '<p>This is the installer from <code>SETUP.md</code> section 1, the same on Windows, macOS and Linux. Fill in the two paths, run the dry run, then the install. It copies only what is missing and writes an install receipt.</p>'
                   f'{cmd(script)}<p>Then write the repo profile (<code>templates/REPO-PROFILE.md</code>) and the test adapter, and check the install:</p>{cmd(check)}'
                   '<p><a class="treelink" href="repo.html">Every folder it adds, and where a job&#39;s files go &rarr;</a></p></details>'
                   + addon_html() + enforced_html()
                   + '<div class="notice gaps"><b>Known gaps</b><div><ul>' + "".join(f"<li>{inline(g)}</li>" for g in F["gaps"]) + "</ul></div></div>"
                   '<script>(function(){var t=document.getElementById("ptags");if(!t)return;t.classList.add("js");'
                   'if(!window.IntersectionObserver||matchMedia("(prefers-reduced-motion:reduce)").matches){t.classList.add("live");return}'
                   'var io=new IntersectionObserver(function(es){if(es[0].isIntersecting){t.classList.add("live");io.disconnect()}},{threshold:.25});io.observe(t)})()</script></section>')

        # 05 see it: one card per sheet of the site
        out.append(sec(7, "see", "See it") + '<div class="see">')
        sheet_no = {h: i for i, (h, _) in enumerate(SHEETS, 1)}
        for h, name, what, flag, prev, _src in F["see"]:
            no = sheet_no.get(h.split("#")[0], 0)
            shot = (f'<span class="shot"><img class="pl" src="assets/see/{prev}-light.webp" alt="" loading="lazy" width="840" height="{1110 if prev == "atlas" else 1350}">'
                    f'<img class="pd" src="assets/see/{prev}-dark.webp" alt="" loading="lazy" width="840" height="{1110 if prev == "atlas" else 1350}"><i class="bolts" aria-hidden="true"></i></span>')
            out.append(f'<a class="card" href="{h}"><div class="sh"><span>Sheet</span><b>{no:02d}</b></div>{shot}<div class="cb"><b>{esc(name)}</b><span>{esc(what)}</span>'
                       + (f"<em>{esc(flag)}</em>" if flag else "") + "</div></a>")
        out.append('</div></section>' + CLOSER.replace("__CMD__", f'<span class="clstep"><b>1</b>Anywhere</span>{cmd(INSTALL["steps"][0][2])}<span class="clstep"><b>2</b>In Claude Code, in your repo</span>{cmd(INSTALL["steps"][1][2])}').replace("__REPOB__", esc(INSTALL["repo"]).replace("/", "/<wbr>")).replace("__REPO__", esc(INSTALL["repo"])).replace("__MARK__", self.mark).replace("__GH__", GH_MARK).replace("</div></div></section>", TOPOUT_NOTE + "</div>" + topout_svg(FRONT_FLOORS) + "</div></section>") + '</div></main>' + self.foot() + THREE_JS + TOWER_JS.replace("__CAPS__", json.dumps(F["night_caps"])))
        out.append(BUILD_JS)
        return self.page(F["title"], F["description"], FRONT_CSS + BUILD_CSS, "index.html", "".join(out), subs=FRONT_SUBS)

    # ---------- the skills index: every skill and agent, grouped as skills-wiki/index.md groups them ----------

    def listing(self) -> tuple[str, str]:
        """Skills and agents on one screen, like the Order of works and the Playbooks: a tab per group, its skills on the left,
        the one being read on the right with the key parts of its page. Find searches every group."""
        by = self.by
        n_skill, n_agent = self.counts()
        steps = step_of_skill()
        lede = "Every skill and agent: what it does, when to use it, how to tell it worked."
        md = ["# Topping Out skills and agents", "", f"{n_skill} skills and {n_agent} agents. {lede}", ""]
        groups = [("route", "Order of works", "By step, 01 to 11", "In order, numbered by the 11 steps of the Order of works."),
                  ("memory", "Memory", "The Logbook", "The Logbook: lessons saved, searched, tidied and turned into firm rules."),
                  ("toolkit", "Toolkit", "Helpers", "Help for settling choices, checking rules, hearing replies and seeing where things stand."),
                  ("agents", "Agents", "Called by skills", "Helpers the skills call on: reviewers, a plan checker, a handover writer.")]
        ids = [pid for g in self.data["groups"] for pid in g["ids"]]
        mine = {}
        for key, *_r in groups:
            ms = [pid for pid in ids if kind_of(pid, by[pid], steps) == key]
            if key == "route":
                ms.sort(key=lambda pid: (steps[pid][0], ids.index(pid)))
            mine[key] = ms
        flat = [(key, pid) for key, *_r in groups for pid in mine[key]]
        sid = {pid: re.sub(r"[^a-z0-9]+", "-", pid.replace("agents/", "agent-")).strip("-") for _k, pid in flat}

        def nav_btn(j, left):
            _k, pid = flat[j]
            return (f'<button type="button" data-open="{sid[pid]}"><span>{"&larr; Previous" if left else "Next &rarr;"}</span>'
                    f'<small style="text-transform:none;font-family:Martian Mono,monospace;font-size:13px">{esc(by[pid]["label"])}</small></button>')

        pages, rows, frows = {k: [] for k, *_r in groups}, {k: [] for k, *_r in groups}, {k: [] for k, *_r in groups}
        for j, (key, pid) in enumerate(flat):
            n = by[pid]
            gtitle = next(g[1] for g in groups if g[0] == key)
            first = j == 0 or flat[j - 1][0] != key
            says, derived = says_and_when(n.get("use", ""))
            when = n.get("when") or derived
            checks = read_content(pid)["checks"]
            if key == "route":
                k, sname, anchor = steps[pid]
                big = f'<div class="big" aria-hidden="true"><b>{k:02d}</b><span>of 11</span></div>'
                bar = f'{esc(gtitle)} · step {k:02d}, <a href="route.html#{anchor}">{esc(sname)}</a>'
                mark, sub = f'<span class="sno">{k:02d}</span>', f"<small>{esc(sname)}</small>"
            else:
                big = f'<svg class="big" viewBox="0 0 24 24" aria-hidden="true">{KIND_ICONS[key]}</svg>'
                bar, mark, sub = esc(gtitle), "", ""
            idx = mine[key].index(pid)
            prev_ = nav_btn(j - 1, True) if j > 0 else "<span></span>"
            next_ = nav_btn(j + 1, False) if j + 1 < len(flat) else "<span></span>"
            meta = (f'<code>{esc(n["slash"])}</code>' if n.get("slash") else "") + f'<em>{esc(n["type"])}</em>'
            pages[key].append(
                f'<section class="spage" id="{sid[pid]}"{"" if first else " hidden"}><div class="sbar"><span>{bar}</span><span>{idx + 1} / {len(mine[key])}</span></div>'
                f'<div class="shd2">{big}<div><h4>{esc(n["label"])}</h4><div class="meta">{meta}</div></div>'
                f'<a class="fullbtn" href="{self.href(pid, "")}"><span>Full page</span><small>sample, questions, links</small><i aria-hidden="true">&rarr;</i></a></div><div class="body">'
                f'<dl class="orw"><dt>Does</dt><dd>{inline(cap(n["blurb"]))}.</dd>' + (f'<dt>When</dt><dd>{inline(when)}</dd>' if when else "") + "</dl>"
                + (f'<div class="kb"><h5>Say it</h5><div class="says">' + "".join(f"<span>{esc(s)}</span>" for s in says) + "</div></div>" if says else "")
                + (f'<p class="knot"><i aria-hidden="true"></i><b>Not for</b><span>{inline(not_for(n["not"]))}</span></p>' if n.get("not") else "")
                + f'<div class="kb kins"><h5>It\'s working if</h5><ul class="kchk">'
                + "".join(f'<li><span>{inline(c)}</span></li>' for c in checks) + '</ul></div>'
                + f'<div class="kfull"><a class="go" href="{self.href(pid, "")}">The full page &rarr;</a><span>Sample, common questions and what it connects to.</span></div>'
                + f'</div><div class="snav">{prev_}{next_}</div></section>')
            rows[key].append(f'<li><button type="button" class="srow{" on" if first else ""}" data-open="{sid[pid]}">{mark}<b>{esc(n["label"])}{sub}</b></button></li>')
            frows[key].append(f'<li data-find="{esc((n["label"] + " " + n["blurb"] + " " + (when or "")).lower())}"><button type="button" class="srow" data-go="{sid[pid]}">{mark}'
                              f'<b>{esc(n["label"])}<small>{inline(cap(n["blurb"]))}</small></b></button></li>')
            md_row = f"- [{n['label']}]({page_path(pid)}.md): {cap(n['blurb'])}."
            if first:
                md += [f"## {gtitle if key != 'route' else 'The order of works'}", ""]
            md.append(md_row)
            if j + 1 == len(flat) or flat[j + 1][0] != key:
                md.append("")

        def pane(key, title, first):
            return (f'<div class="pane" data-role="{key}" role="tabpanel" aria-label="{title}"{"" if first else " hidden"}>'
                    f'<nav class="side" aria-label="{title}"><ul>{"".join(rows[key])}</ul></nav><div class="reader">{"".join(pages[key])}</div></div>')

        find_pane = ('<div class="pane fnd" data-role="find" aria-label="Search results" hidden><nav class="side" aria-label="Search results">'
                     + "".join(f'<p class="fgl">{esc(g[1])}</p><ul>{"".join(frows[g[0]])}</ul>' for g in groups)
                     + '</nav><div class="reader"><section class="spage"><h4>Matches</h4><p class="fhint">Pick one on the left to read it.</p>'
                     '<p class="fhint fnone" hidden>Nothing matches. Try another word, or open the <a href="atlas.html">Skill Atlas</a>.</p></section></div></div>')

        def tabb(key, title, sub, first):
            ic = '<span class="tn" aria-hidden="true">01</span>' if key == "route" else f'<svg class="si" viewBox="0 0 24 24" aria-hidden="true">{KIND_ICONS[key]}</svg>'
            return (f'<button type="button" class="tab {"b" if key == "route" else "f"}" role="tab" id="g-{key}" data-rtab="{key}" aria-selected="{"true" if first else "false"}">'
                    f'{ic}<span><b>{title}</b><span>{sub} · {len(mine[key])}</span></span></button>')

        body = (f'<main id="skills" class="sk" data-desk><div class="wrap"><header class="rhead2"><span class="eyebrow">Sheet {sheet_no("skills.html")} · '
                f'{n_skill} skills · {n_agent} agents</span><h1>Skills and agents</h1>'
                f'<p class="lede">{esc(lede)} All on one map: the <a href="atlas.html">Skill Atlas</a>.</p><p class="rmode">Coding agents can read a plain-text copy of each page.</p>'
                '<label class="find"><span>Find</span><input type="search" id="findbox" placeholder="What do you want to do? Try: review, plan, lesson" autocomplete="off">'
                '<output id="findn" aria-live="polite"></output></label></header>'
                '<div class="tabs" role="tablist" aria-label="Groups">' + "".join(tabb(k, ti, su, i == 0) for i, (k, ti, su, _d) in enumerate(groups)) + "</div>"
                f'<div class="desk">{"".join(pane(k, ti, i == 0) for i, (k, ti, _s, _d) in enumerate(groups))}{find_pane}</div>'
                '</div></main>' + self.foot() + ROLES_JS + SK_FIND_JS)
        subs = [(f"#g-{k}", ti) for k, ti, _s, _d in groups]
        page = self.page("Skills and agents · Topping Out", f"Every Topping Out skill and agent: {n_skill} skills and {n_agent} agents.",
                         ROLES_CSS + SKILLS_DESK_CSS, "skills.html", body, subs=subs)
        return page, "\n".join(md)

    # ---------- a skill or agent page, and its Markdown twin ----------

    def card_order(self) -> list:
        """Every skill and agent in the Skills and agents page's order: (group key, group title, id)."""
        if getattr(self, "_card_order", None) is None:
            steps, by = step_of_skill(), self.by
            ids = [x for g in self.data["groups"] for x in g["ids"]]
            out = []
            for key, title in (("route", "Order of works"), ("memory", "Memory"), ("toolkit", "Toolkit"), ("agents", "Agents")):
                ms = [x for x in ids if kind_of(x, by[x], steps) == key]
                if key == "route":
                    ms.sort(key=lambda x: (steps[x][0], ids.index(x)))
                out += [(key, title, x) for x in ms]
            self._card_order = out
        return self._card_order

    def skill(self, pid: str) -> tuple[str, str]:
        n, by, steps, p = self.by[pid], self.by, self.steps, "../"
        st11 = step_of_skill()
        kind = kind_of(pid, n, st11)
        gname = {"route": "Order of works", "memory": "Memory", "toolkit": "Toolkit", "agents": "Agents"}[kind]
        name = n["label"]
        i = steps.index(pid) if pid in steps else -1
        fam = self.data["families"].get(n["family"], n["family"])
        group = re.sub(r"\s*\(.*\)\s*$", "", n["group"].split(":")[0])
        says, derived = says_and_when(n.get("use", ""))
        when = n.get("when") or derived
        if not n.get("when"):
            print(f"WARN {pid}: no **When to use it:** line in its wiki page; built from the SKILL.md description instead")
        content = read_content(pid)
        meta = content["meta"]
        sample = skill_sample(ROOT / n["path"], meta["sample"]) if meta.get("sample") else ""
        rels = [(t, a, rs) for t, a, rs in (("Comes after", "&larr;", n["after"]), ("Leads to", "&rarr;", n["before"]),
                                             ("Uses", "&rarr;", n["uses"]), ("Used by", "&larr;", n["usedBy"])) if rs]

        def chip(r):
            m = by[r["id"]]
            return (f'<li><a class="nb f-{m["family"]}{" ag" if m["type"] == "agent" else ""}" href="{self.href(r["id"], p)}">'
                    f'<i></i><span><b>{esc(m["label"])}</b><small>{inline(cap(m["blurb"]))}</small></span></a></li>')

        conn = "".join(f'<div><h2>{a} {t} <b>{len(rs)}</b></h2><ul>{"".join(chip(r) for r in rs)}</ul></div>' for t, a, rs in rels)
        tape = ""
        if kind == "route":
            here = st11[pid][0]
            names = [s for s, *_ in FRONT["route_once"] + FRONT["route_loop"]]
            cells = [(f'<span class="{"past" if k < here else "here" if k == here else ""}" title="{esc(s)}">{k}</span>') for k, s in enumerate(names, 1)]
            tape = (f'<div class="tape"><div class="tl"><span>Order of works</span><span><b>step {here}</b> of 11 &middot; '
                    f'<a href="{p}route.html#{st11[pid][2]}">open step {here} &rarr;</a></span></div>'
                    f'<div class="ts">{"".join(cells)}</div></div>')
        if False:
            cells = []
            for k, sid in enumerate(steps):
                cls = "past" if k < i else "here" if k == i else ""
                lab = esc(by[sid]["label"])
                cells.append(f'<a class="{cls}" href="{self.href(sid, p)}" title="{lab}">{k + 1}</a>' if sid in self.built and sid != pid
                             else f'<span class="{cls}" title="{lab}">{k + 1}</span>')
            prev_ = f'<a href="{self.href(steps[i - 1], p)}">&larr; {esc(by[steps[i - 1]]["label"])}</a>' if i > 0 else "<span></span>"
            next_ = f'<a href="{self.href(steps[i + 1], p)}">{esc(by[steps[i + 1]]["label"])} &rarr;</a>' if i + 1 < len(steps) else ""
            tape = (f'<div class="tape"><div class="tl"><span>Order of works</span><span><b>step {i + 1}</b> of {len(steps)}</span></div>'
                    f'<div class="ts">{"".join(cells)}</div><div class="tn">{prev_}{next_}</div></div>')

        back = f'{p}skills.html#g-{kind}'
        crumb = (f'<a href="{p}route.html#{st11[pid][2]}">{st11[pid][0]:02d} {esc(st11[pid][1])}</a>' if kind == "route" else f'<a href="{back}">{esc(gname)}</a>')
        order = self.card_order()
        at = [x for _k, _t, x in order].index(pid)
        pk, _pt, prv = order[at - 1]
        nk, _nt, nxt = order[(at + 1) % len(order)]
        mine = [x for k, _t, x in order if k == kind]
        flip = (f'<nav class="flip" aria-label="Skills and agents, one by one">'
                f'<a class="fp" href="{self.href(prv, p)}" rel="prev" data-key="ArrowLeft"><small>&larr; Previous</small><b>{esc(by[prv]["label"])}</b></a>'
                f'<span class="fc"><b>{esc(gname)}</b><span>{mine.index(pid) + 1} / {len(mine)}</span><small>&larr; &rarr; keys</small></span>'
                f'<a class="fn" href="{self.href(nxt, p)}" rel="next" data-key="ArrowRight"><small>Next &rarr;</small><b>{esc(by[nxt]["label"])}</b></a></nav>')
        h = [f'<main class="page"><div class="back"><a class="bk" href="{back}" data-back>&larr; Back</a>'
             f'<nav class="crumbs" aria-label="Breadcrumb"><a href="{p}skills.html">Skills and agents</a><span>/</span>{crumb}<span>/</span><span>{esc(name)}</span></nav></div>' + flip]
        h.append(f'<article class="dkt f-{n["family"]}"><div class="haz"></div><div class="band"></div><div class="punch"></div><div class="dkt-h"><div class="no">'
                 + (f'<b>{st11[pid][0]:02d}</b><span>of 11</span>' if kind == "route" else f'<svg class="kib" viewBox="0 0 24 24" aria-hidden="true">{KIND_ICONS[kind]}</svg><span>{esc(n["type"])}</span>')
                 + f'</div><div><div class="eyebrow">{"Step " + format(st11[pid][0], "02d") + " · " + esc(st11[pid][1]) if kind == "route" else esc(gname)}</div><h1>{esc(name)}</h1>'
                 + (f'<div class="plate"><code data-copy="{esc(n["slash"])}" role="button" tabindex="0" title="Copy">{esc(n["slash"])}</code></div>' if n.get("slash") else "")
                 + f'</div><div class="stamp">{esc(n["type"])}</div></div>')
        h.append(f'<p class="lead">{inline(cap(n["blurb"]))}.</p>')
        # where it sits and when to use it on one plate; "not for" as the site's prohibition sign; a checklist you can tick,
        # sharing its ticks with the same skill on the Skills and agents page
        callers = n["usedBy"] if n["type"] == "agent" else []
        called = "".join(f'<a href="{self.href(r["id"], p)}">{esc(by[r["id"]]["label"])}</a>' for r in callers)
        if n.get("role") or when or called:
            h.append('<dl class="orw">' + (f'<dt>Called by</dt><dd class="cby">{called}</dd>' if called else "")
                     + (f'<dt>On site</dt><dd><p>{inline(n["role"])}</p>' + (f'<p class="sub">{inline(n["note"])}</p>' if n.get("note") else "") + "</dd>" if n.get("role") else "")
                     + (f"<dt>When</dt><dd><p>{inline(when)}</p></dd>" if when else "") + "</dl>")
        if says:
            h.append('<div class="bx"><span class="lbl">Say it <em class="cphint">tap to copy</em></span><div class="says">'
                     + "".join(f'<span data-copy="{esc(s)}" role="button" tabindex="0" title="Copy">{esc(s)}</span>' for s in says) + "</div></div>")
        if n.get("not"):
            h.append(f'<p class="knot"><i aria-hidden="true"></i><b>Not for</b><span>{inline(not_for(n["not"]))}</span></p>')
        h.append(f'<div class="bx kins"><span class="lbl">It\'s working if</span><ul class="check kchk">'
                 + "".join(f'<li><span>{inline(c)}</span></li>' for c in content["checks"]) + '</ul></div>')
        if sample:
            h.append(f'<div class="bx sample"><span class="lbl">{esc(meta.get("sample_title", "Sample"))}</span>'
                     + (f'<p>{inline(meta["sample_note"])}</p>' if meta.get("sample_note") else "") + f"<pre>{esc(sample)}</pre></div>")
        h.append('<div class="bx"><span class="lbl">Common questions</span><dl class="faq">' + "".join(f"<dt>{inline(q)}</dt><dd>{inline(a)}</dd>" for q, a in content["faq"]) + "</dl></div>")
        h.append(tape + '<div class="tear"></div>' + f'<div class="stub">{conn or "<p>No links to other skills or agents.</p>"}</div>')
        h.append(f'<div class="foot"><span>{esc(n.get("path", ""))}</span>' + (f'<span>old name {esc(n["old"])}</span>' if n.get("old") else "")
                 + f'<a href="{esc(name)}.md">This page as Markdown</a></div></article></main>' + self.foot() + FLIP_JS + COPY_JS)
        page = self.page(f"{name} · Topping Out", cap(n["blurb"]) + ".", DOCKET_CSS, "skills.html", "".join(h), prefix=p,
                         subs=[(back, f"Back to {gname}")])

        md = [f"# {name}", "", f"{cap(n['blurb'])}.", ""]
        if n.get("slash"):
            md += [f"Command: `{n['slash']}`" + (f" (old name `{n['old']}`)" if n.get("old") else ""), ""]
        md += [f"Stage: {fam} · {group}" + ((f" · step {step_of_skill()[pid][0]} of 11 in the order of works ({step_of_skill()[pid][1]})" if pid in step_of_skill() else "")), f"Source: `{n.get('path', '')}`", ""]
        if n.get("role"):
            md += ["## On site", "", n["role"] + (" " + n["note"] if n.get("note") else ""), ""]
        if says:
            md += ["## Say it", "", *[f'- "{s}"' for s in says], ""]
        if when:
            md += ["## When to use it", "", when, ""]
        if n.get("not"):
            md += ["## Not for", "", not_for(n["not"]), ""]
        md += ["## It's working if", "", *[f"- {c}" for c in content["checks"]], ""]
        if sample:
            md += [f"## {meta.get('sample_title', 'Sample')}", ""] + ([meta["sample_note"], ""] if meta.get("sample_note") else []) + ["```", sample, "```", ""]
        md += ["## Common questions", ""]
        for q, a in content["faq"]:
            md += [f"### {q}", "", a, ""]
        if rels:
            md += ["## Connections", ""] + [f"- {t}: " + ", ".join(by[r["id"]]["label"] for r in rs) for t, _, rs in rels] + [""]
        return page, "\n".join(md)


def stale_previews() -> list:
    """Sheets whose page changed since its preview was taken (previews.mjs records each page's hash in sources.json)."""
    man = OUT / "assets" / "see" / "sources.json"
    seen = json.loads(man.read_text(encoding="utf-8")) if man.exists() else {}
    out = []
    for _h, name, _w, _f, prev, src in FRONT["see"]:
        page = OUT / src
        now = hashlib.sha1(page.read_bytes()).hexdigest() if page.exists() else ""
        if not (OUT / "assets" / "see" / f"{prev}-light.webp").exists() or seen.get(src) != now:
            out.append(name)
    return out


def main() -> int:
    site = Site()
    # the build owns everything in docs/ but docs/content/ and docs/assets/ (the preview images): clear the rest, then write it all again
    OUT.mkdir(exist_ok=True)
    for child in OUT.iterdir():
        if child.name not in ("content", "assets"):
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    for d in ("skills", "agents", "raw"):
        (OUT / d).mkdir()
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    (OUT / "CNAME").write_text(DOMAIN + "\n", encoding="utf-8", newline="\n")

    written = []

    def write(rel: str, text: str) -> None:
        if rel.endswith(".html"):
            m = re.search(r'<title>(.*?)</title><meta name="description" content="(.*?)">' + SHARE_MARK, text)
            if not m:
                raise SystemExit(f"build_site: {rel} has no title and description to share")
            text = text.replace(SHARE_MARK, share_tags(rel, html.unescape(m.group(1)), html.unescape(m.group(2))), 1)
        (OUT / rel).write_text(text, encoding="utf-8", newline="\n")
        written.append(OUT / rel)

    for raw, src in RAW.values():
        if src == RAW["atlas"][1]:
            (OUT / raw).write_text(atlas_site_copy((ROOT / src).read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
        else:
            shutil.copyfile(ROOT / src, OUT / raw)
        # every generated page opens dark first too, also when opened on its own (D23), and in standards mode, not quirks
        text = (OUT / raw).read_text(encoding="utf-8").replace(OLD_THEME_HEAD, "")
        frame = RAW_SHARE[raw]
        m = re.search(r"<title>(.*?)</title>", text)
        text = (share_tags(frame, html.unescape(m.group(1)) + " · Topping Out", FRONT["description"]) if m else "") + text
        if not text.lstrip().lower().startswith("<!doctype"):
            text = "<!doctype html>" + THEME_HEAD + text
        else:
            text = text.replace(">", ">" + THEME_HEAD, 1)
        (OUT / raw).write_text(text, encoding="utf-8", newline="\n")
        written.append(OUT / raw)
    write("index.html", site.front())
    listing, listing_md = site.listing()
    write("skills.html", listing)
    write("skills.md", listing_md)
    write("route.html", site.order())
    write("atlas.html", site.framed("atlas.html", "Skill Atlas", "Every Topping Out skill and agent as a map, with the links between them.", RAW["atlas"][0]))
    write("board.html", site.board())
    write("playbooks.html", site.playbooks())
    write("repo.html", site.repo())
    write("logbook.html", site.logbook())
    write("requirements.html", site.requirements())
    write("about.html", site.about())
    for pid in sorted(site.built):
        page, md = site.skill(pid)
        write(f"{page_path(pid)}.html", page)
        write(f"{page_path(pid)}.md", md)

    missing = sorted(set(site.by) - site.built)
    print(f"wrote {OUT.relative_to(ROOT).as_posix()}/: {len(SHEETS)} sheets, {len(site.built)} skill and agent pages with their Markdown twins, {len(RAW)} generated pages in raw/")
    if missing:
        print(f"no content file yet (these link to the Atlas): {', '.join(missing)}")
    if not INSTALL["confirmed"]:
        print("WARN install commands on the front page are not confirmed yet (requests file, entry 4): do not launch until they work")
    stale = stale_previews()
    if stale:
        print(f"WARN previews taken before their pages last changed (re-run previews.mjs): {', '.join(stale)}")
    # DESIGN.md: no em dashes anywhere. The build never rewrites source text; it names each file still carrying one.
    for path in written:
        count = path.read_text(encoding="utf-8").count(chr(0x2014))
        if count:
            print(f"WARN em dash x{count} in {path.relative_to(ROOT).as_posix()}: fix at its source, then log it in the requests file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

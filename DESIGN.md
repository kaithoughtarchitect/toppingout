# Topping Out design

Every Topping Out page is one product: the board, the flow page, the Skill Atlas, the playbook and the three pickers. This file is the design they share. A new page follows it; a change to it is made here first, then in the sources below.

## Identity

- **The mark is the hard hat.** `assets/foreman-logo.png` (512px) and `assets/foreman-logo-128.png`. The board carries its own copy at `skills/f-board/foreman-logo.png` so the skill works when installed alone.
- It is the browser-tab icon of every page. **The lockup:** the hat beside the one-line wordmark **TOPPING OUT**, with **OUT** in `var(--brand)`. The pages' kickers name the product as "Topping Out"; the foreman is a role inside it, never the product name. Pages embed the mark as a `data:` URI, so each page stays one file.
- On a dark ground it gets a thin light rim (four `drop-shadow`s in `#ECEEEA`) so the black outline does not vanish.

## Colour

Colours come from the hat. Light is concrete, dark is asphalt.

| Token | Light | Dark | Use |
|---|---|---|---|
| ground | `#ECEEEA` | `#101316` | page background |
| panel | `#F8F9F6` | `#171B1E` | cards, bars |
| line | `#C9CFC7` / `#DADFD8` | `#2C3337` / `#23292C` | hairlines (strong / soft) |
| ink | `#15181A` | `#E7EAE5` | text, the spine |
| hivis | `#FBB401` | `#FBB401` | the hat yellow: next, selected, the main action, step numbers, hazard stripes |
| hivis-ink | `#101316` | `#101316` | text on hi-vis (the hat's outline) |
| brand text | `#946400` | `#FBB401` | small yellow text; light theme uses the deeper shade because the hat yellow is unreadable as small text on concrete |
| merged / good | `#2F6B3A` | `#8FCB7C` | done, $0, good figures |
| run | `#1D4E89` | `#80AFE9` | in progress, the chair / host / auditor edge |
| decision / warn | `#A5650F` | `#F0B04A` | to decide, metered, mid scores |
| fail | `#B3261E` | `#F2847A` | clashes, low scores |

**Every page has a light/dark switch** (top right; the three pickers call it Mode). Its label names the mode it switches to, the choice is saved in the browser under `foreman-theme`, and a two-line script at the top of the page applies it before the page draws. With no saved choice, the page follows the system setting.

Every page defines the light palette on `:root`, redefines it under `@media (prefers-color-scheme: dark)` guarded by `:root:not([data-theme="light"])`, and again under `:root[data-theme="dark"]`. `body` always paints its own background.

## Type

| Face | Role |
|---|---|
| **Big Shoulders Display** 800, uppercase | page titles, section titles, the TOPPING OUT wordmark, big numbers |
| **Public Sans** | body text, card names, buttons |
| **Martian Mono** | kickers, labels, ids, prices, tags, step numbers |

All three load from Google Fonts in one `<link>`. Running text stays under about 72 characters wide.

## Site details

Every element borrows something real from a building site and still does a job on the page.

- **Stencil numbers:** *Big Shoulders Stencil Display* for the big numbers: job numbers, the gauge, figures, stage and step numbers, seat-count tiles.
- **Site notices:** warnings, rules and anything that waits for a decision are a yellow sign with a black border, the label on a black plate (the board's alert strip, "To decide", the playbooks' checklists, the pickers' rule notes).
- **The stamp:** a job's status on its docket is a double-ruled rubber stamp, tilted 4°. Only there; lists stay straight.
- **The work docket:** the board's job ticket has a punched top edge and a dashed tear line to its notes stub.
- **The dimension line:** a surveyor's measure over the built part of the board's job tape.
- No cartoon cones, cranes or joke signs.

## Shape

- Square corners everywhere. No rounded pills, no soft shadows.
- Hairline borders mark objects; a solid fill marks state.
- The hazard stripe (hi-vis and hat-outline at -45°) marks the top of a page: under the picker top bar, under the playbook title block, on the board's alert strip and on the head sign.

## A page, top to bottom

1. **Top bar:** hat, **TOPPING OUT**, then the page's name as a square tag (`MODEL COUNCIL`). Status chips follow, values in caps (`HOST · ANTHROPIC`).
2. **Kicker** in Martian Mono caps, then the **title** in Big Shoulders caps, then a **lede** of two plain sentences.
3. **Numbered steps:** each section title carries a hi-vis step number (01, 02, 03) and a hairline under it.

## Interaction

- **Nothing moves when you click or hover.** No lift, no scale, no border that changes width. A state change only recolours.
- **One card size per grid.** A card reserves room for every state it can take. A clash message replaces a line; it never adds one.
- **Selected:** hi-vis inset outline, a light hi-vis tint, and a solid hi-vis tag top right (`SEAT 1`).
- **Can't pick:** the card's content dims to 40%, but the reason stays at full strength.
- **The main action** is a hi-vis button with hat-outline text, in both themes. Pickers label it by what the page does: **Record seats**.

## Writing

- Plain words, no marketing voice.
- **No em dashes.** Use a comma, a colon or a full stop. This includes text the foreman writes into `BOARD.json` (`/f-signoff` step 3.2b).
- Picker titles follow one pattern: **Seat the council / Seat the panel / Seat the cold read**.

## Every page, every screen

- Checked in both themes and at 390px phone width. No page scrolls sideways; only a wide drawing (the board's fishbone) scrolls inside its own box.
- A one-screen page (the board) fits without scrolling on a desktop.

## Where each page's design lives

Edit the source, never the page it writes.

| Page | Source | Rebuild |
|---|---|---|
| Project board | `skills/f-board/render_board.py` | `python skills/f-board/render_board.py <project>/BOARD.json render` |
| Flow page | `scripts/build_flow.py` | `python scripts/build_flow.py` |
| Skill Atlas | `scripts/wiki_graph_html.py` | `python scripts/wiki_graph_html.py skills-wiki` |
| The three pickers | `scripts/picker_style.py` (shared) and each console's own markup | `python scripts/picker_style.py` |
| Foreman Playbook | `Foreman-Playbook.md` via `scripts/build_foreman_playbook.py` | `python scripts/build_foreman_playbook.py` |
| Builder Playbook | `Builder-Playbook.md` | `scripts/build_foreman_playbook.py` |

The three pickers share one block of styles, `<style id="foreman-system">`, written by `scripts/picker_style.py`. Agent Council adds its own small block (`agent-council-layout`) for its card insides. Change the shared look in the script, then run it: it replaces the block in all three and never stacks a second copy.

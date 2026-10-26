# <Project title>: topping out report

**By:** the foreman, <date>, at the end of J<N>, the last job before the board's head (`METHOD.md` §11b). **Board:** `foreman/projects/<slug>/BOARD.json`, topped out at version <v>. **Head:** <the board's head outcome, verbatim>.

## What was built

| Job | Board id | What it delivered | PR / merge |
|---|---|---|---|
| <N> | <id> | <one line> | <#n / sha> |

The table and totals come from `render_board.py <project>/BOARD.json report` (paste its output). CI on main at the topping out: <green / red: which check>. Totals, pasted from command output (rule 16): <jobs merged> jobs, <PRs>, tests <first> → <last>, probes <n>/<n> bite.

## Did it reach the head? (yes, partly or no: the same answer `topout --head` recorded)
<The head's test, if the board has one, and the evidence it now passes; or what is still short of it and why the project tops out anyway (the owner's words).>

## What it learned
The three to five Logbook cards most worth carrying into the next head, each with its id and one line.

## Carried over
Everything not finished, so the next head starts from it rather than rediscovering it:
- **Jobs not built** (the board's `topped_out.carried`): <id, title, why it waits>.
- **Owed items** carried across jobs: <the item, since which job>.
- **Ruled-out ideas worth revisiting** (cards tagged `ruled-out` whose "Revisit if" may now hold): <card id, one line>.

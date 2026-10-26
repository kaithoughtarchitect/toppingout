# Next-ticket decision after J<N>: J<N+1> (board <id>), or topping out

**By:** the foreman, <date>, after J<N> merged (`<merge sha>`).

**Which branch** (keep one, delete the other two):
- **Next job:** fill every section below.
- **Topping out** (every job merged or resolved, or the owner's own words with jobs left): "Topping out: yes", the KEY line becomes "No next job: the head is reached", keep the board citation and "Owner confirmed", state the completion evidence (or quote the owner), and name the report and next-heads paths; delete "Evidence it is ready", "Candidates rejected", "Risk and size" and "What the shift handover must carry" (`METHOD.md` §11b).
- **Waiting** (work left, nothing eligible): name what waits on the owner (the decision job, or an empty iteration board), ask, and stop; the end game stays pending.

## Decision
**<KEY>: <title>.** <One sentence: why this one is the next job.> Chosen from the project board **v<n>** (`render_board.py BOARD.json check` gives the version; read it before the close, with `next --after-close <closing job>`) (`METHOD.md` §11). The end-game lock refuses a decision that doesn't name it.

**Topping out:** no | yes (yes when every job is merged or resolved: the board's head is reached; or on the owner's own words with jobs left, never a goal's. Then replace the KEY line above with "No next job: the head is reached" and keep "Chosen from the project board **v<n>**"; the end game tops the project out, `METHOD.md` §11b. Nothing to build because the rest wait on the owner is not a topping out: say so and ask)

**Picked by:** <unblocks the most · partial work already on disk · the project's order>. *Only the order left means the board is thin: say so, and add the planned work it's missing.*

**Owner confirmed:** <"the owner's words", or: decided under the standing goal "<the goal's words>">
*(Step 7a. Written before the board update and the handover; the end-game lock refuses both until this line is filled.)*

## Evidence it is ready (next-job branch)
- Eligible per the board: `render_board.py BOARD.json next --after-close <closing job>` listed it before the close (ready once that job merges: every need merged or resolved), and the close records it as `next` once the owner confirms.
- Every blocker is Done or merged: <KEY or job, state, read live today>.
- What the repository already holds for it: <file:line>.
- The board's own sequencing: <the phase/parent/"blocks" links, read live>.

## Candidates rejected, and why (next-job branch)

| Candidate | Why not now | Revisit when |
|---|---|---|
| <KEY> | <blocked by X / out of phase / needs a stakeholder decision> | <condition> |

## Risk and size (next-job branch)
<The hardest part, in one line. The expected size (files, whether a DB proof is needed, whether a migration is needed: say "no .sql expected" or why one is).>

## What the shift handover must carry (next-job branch)
The forks the next session has to settle (listed, not decided here), the gotchas, the red lines.

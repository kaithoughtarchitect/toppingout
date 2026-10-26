# <Project title>: candidate next heads

**By:** the foreman, <date>, after the topping out report (`<path>`). The owner picks one (or names another); the full cycle then starts again for it: `/f-survey` → `/f-blueprint` → `/f-plancheck` → `/f-schedule` → a new board in `foreman/projects/<new slug>/`; the foreman then writes the first job's opener from `templates/SESSION-OPENER-FIRST-JOB.txt` (`METHOD.md` §11b). Start it in a fresh foreman session.

| # | Head (the outcome, in one line) | Why now | Comes from | Shape |
|---|---|---|---|---|
| 1 | <outcome> | <one line> | <carried job, owed item, card, or the owner's stated direction> | project (a blueprint and a board) or iteration board (small jobs added as found) |

3 to 5 rows, the evidence's pick first. **To start one:** say "next head: <#>"; the foreman then runs `/f-survey` on it (a project), or starts an iteration board with `render_board.py foreman/projects/<slug>/BOARD.json init … --iteration` (small jobs).

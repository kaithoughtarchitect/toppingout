# f-board

Update the project board when a job starts, merges, gets stuck or is added.

Command: `/f-board`

Stage: Run a job · Starting and running a job · step 11 of 11 in the order of works (Close)
Source: `skills/f-board/SKILL.md`

## On site

Throughout a project: marks a job as started when you say go, merged after the merge, and stuck when it stops. It works out by itself which jobs are ready and which are waiting, counts each change as a new version, and republishes the board page at the same link. When every job is done the board tops out: it is frozen as the project's record, and the next head gets a new board. An iteration board takes small jobs as they are found.

## Say it

- "go"
- "what's next?"
- "show me the board"

## When to use it

Whenever a job starts, merges, gets stuck or is added, so the board stays true.

## Not for

Cutting a plan into jobs (f-schedule).

## It's working if

- Each event is one `render_board.py` command and bumps the board's version exactly once.
- Ready and blocked are worked out by the tool, never stored, and only one job is in progress at a time.
- The tool refuses bad data or an impossible event, such as starting a blocked job, closing without `--next` when a job becomes eligible, or a merged job without its SHA.
- A close is recorded only after the merge was checked in the repository, never on a report's word.
- `board.html` is regenerated from `BOARD.json` and never edited by hand.
- With no board link yet, it renders locally and asks you before the first publish; after that it republishes to the same private link.
- The builder is never named on the board.
- Every job carries a summary that says in plain words what it builds, and `check` warns on a summary that is only plan references.

## Common questions

### Who updates the board?

Only the foreman. Board updates are the foreman's own records, so they need no PR and no word from you, except the first publish of the page.

### What happens at the end of a job?

After the merge is verified, `close` records the job as merged and chooses the next job in one version. The next job is picked by what unblocks the most, then the most partial work, then the project's order.

### What is a job's summary?

The line on the Job tab that says what the job builds, so you know what it does without opening its ticket. It is one sentence, under about 20 words, with any plan references after it in brackets: "Loads the catalogue as a runtime block, so later jobs can use it. (T2, VP-6)". If one is unclear, `summary <job> --text "..."` replaces it, and `add` takes a `--summary` for a new job.

### What if one job turns out to be covered by another?

You say so, and a `covered` event records it with your words quoted: the job leaves the board, pointing at the job that covers it.

### What does exit code 4 mean?

The event was recorded in `BOARD.json` but the page wasn't written, usually a locked or missing path. Fix the cause and run `render_board.py BOARD.json` to refresh the page. Never replay the event, or it is recorded twice.

### Can I edit `BOARD.json` myself?

You can edit the text fields, such as lessons, alerts, debts and facts, and the next render picks them up. Don't change a job's state by hand: states change only through the tool's events.

### How do I start a board for a project that wasn't scheduled?

Run `render_board.py <project>/BOARD.json init` with the project's title, its outcome, how you'd know it worked and its first job. Then `add` each job, and `add --merged` with the PR and merge SHA for a job that merged before the board existed. `init` refuses to overwrite a board that's already there.

### Can a project go without a board?

No. Every project has one: the close-out's board step ticks only the project's `BOARD.json`.

### What happens when every job is done?

The board tops out. `topout` freezes it as the project's record: no event runs after it, and any job not finished is recorded as carried over. With jobs still unfinished, it tops out only on your own words (`--quote`), never a goal's. `--head yes`, `partly` or `no` records whether the project reached its head, and `report` prints the topping out report's table, the carried jobs and the owed items.

## Connections

- Comes after: f-signoff
- Used by: f-schedule, f-shift, f-setup

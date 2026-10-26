# f-night-shift

Run several jobs one after another without you: a shift boss opens a fresh foreman for each.

Command: `/f-night-shift`

Stage: Kit · Several jobs in a row
Source: `skills/f-night-shift/SKILL.md`

## On site

When you type /goal night shift with a list of jobs, or a number of jobs to pick: usually before you sleep. Each job is its own autonomous run; the boss only starts it and checks the repo. Any stop ends the shift, and so does a completed topping out (the next head is yours to pick); the morning summary is one file.

## Say it

- "/goal night shift: jobs 13, 17, until done or stopped"
- "/goal night shift: 2 jobs, auto-pick, until done or stopped"

## When to use it

Before you sleep, when the next jobs are on the board and you want them built one after another without you.

## Not for

One job (that is "/goal autonomous run: <opener>"), and never inside a job's own foreman session.

## It's working if

- It copies your exact /goal words into the shift record before doing anything else.
- It refuses to start unless main matches the remote, the last job's end game is finished and no job worktree is open.
- It never plans, builds, reviews or merges: each job runs in its own fresh foreman session.
- It decides a job is done from the repo (merged, end game clear, next opener written), never from what the chat says.
- The first stop ends the whole shift, with the foreman's stop line quoted in the shift record.
- In planned mode it stops if a job's end game picks a job that is not next on your list.

## Common questions

### How do I start one?

In a fresh session, type `/goal night shift: jobs 13, 14` to run a list you chose, or `/goal night shift: 2 jobs, auto-pick` to let each job's end game pick the next. Add `, spend up to 5 USD` to allow paid checks, one cap for the whole shift. Only your own typed line starts a shift.

### What does the shift boss do?

It opens a fresh foreman for each job, types that job's autonomous run, and checks the repo until the job is merged and closed. Then it starts the next. It never answers a job's questions or types into its session after the start line.

### What happens when a job stops?

The shift ends. The boss writes the reason into the shift record, quoting the foreman's own stop line, and tells you in one short reply. Nothing after the stop runs.

### What if the builder hits its usage limit?

The job pauses, it doesn't stop: the foreman waits for the limit to reset and carries on, and the shift waits with it. It never switches to a paid seat or another builder. A reset more than six hours away, or unknown, stops the job. If the foreman's own session hits its limit, the boss sends it one fixed line after the reset and it carries on.

### How is it different from one autonomous run?

`/goal autonomous run: <opener>` runs one job without you. A night shift runs several in a row, each one its own autonomous run in a fresh session.

### What does it need from my repo?

The foreman launch command in your repo profile (for example `claude`, with the flags you use), the first job's opener in `foreman/handovers/`, and Orca to open each foreman in its own tab. If the launch command is missing, it stops and asks rather than guessing.

### How long can a shift run?

Until the list is done, a job stops, a board tops out, the spend cap is reached, or a single job runs past 16 hours.

## Connections

- Comes after: f-signoff

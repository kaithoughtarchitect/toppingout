# lens-migrations

Review database changes: migrations, queries and access rules.

Stage: Inspect · Agents used as review lenses
Source: `agents/lens-migrations.md`

## On site

Used as a reviewer inside f-inspect when the changes touch the database. Every database change also needs your approval.

## When to use it

When the changes touch the database.

## Not for

General logic bugs (lens-code), not for swallowed errors (lens-errors), not for git (the caller owns it).

## It's working if

- It checks the diff against the binding traps: JSON written or read the wrong way, a list bound to a single-value column, an array bound without the conversion its column needs, and guessed table or column names.
- Each finding is one row with the `file:line`, a severity, what breaks and the fix.
- It states whether the migration must be applied to production before merging (yes, no or unknown) and cites the evidence for that answer.
- A policy finding cites the repo's own rule it breaks; where the rule is silent, it says so instead of inventing one.
- It lists what it could not check, such as a database it could not reach or a plan it did not run.
- It applied no migration and wrote to no database.

## One finding

Each finding is one row in this shape, exactly as the agent's instructions give it.

```
<file:line> | CRITICAL | IMPORTANT | NOTE | <trap or rule> | <what breaks, concretely> | <fix>
```

## Common questions

### Do I call it directly, or does `/f-inspect` run it?

`/f-inspect` runs it when the diff touches the repo profile's database change paths. It runs as a fresh subagent with no context from the job.

### Does it change code or the database?

It is told never to apply a migration, run the migrate command or write to any database, and to inspect read-only. It has no edit tools either.

### Who applies the migration, then?

Not this agent. Applying a migration anywhere but a disposable database needs your word.

### Does it treat a clean migration as a problem?

No. If the SQL is correct and the traps are avoided, it returns zero rows, and run on its own it closes with `APPROVE`. It is told not to manufacture findings.

## Connections

- Used by: f-inspect

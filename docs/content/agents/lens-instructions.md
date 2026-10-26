## It's working if

- It builds a map of which instruction file produces a name (a field, a flag, a section title, a file name) and which files read it, and checks those links first.
- Structural findings (counts, versions, paths, flag names) cite the search that proves them; meaning-level findings quote both passages word for word.
- Each conflict says how it resolves: a rule elsewhere settles it, both are right in different scopes, or you must decide.
- It reports only issues at 80 or above for confidence, ordered by severity.
- When nothing clears the bar it says "Documentation is aligned", lists the files and links it checked, and stops.
- It edited no files.

## Common questions

### Do I call it directly, or does `/f-inspect` run it?

`/f-inspect` runs it when the job changed skills, agents, prompts or templates. You can also run it on its own after editing instruction files.

### Does it change files?

It is told not to. Its tools are read and search, plus a shell it is told to use only for read-only git, so this rests on its instructions, not on a lock. It gives a concrete fix for each issue and leaves the edit to you or the builder.

### What is the most common problem it catches?

An agent file is rewritten and the skill that calls it keeps the old contract, so a gate in the skill can never fire.

### Will it flag "ticket" against "job"?

No. It keeps a list of pairs that look like drift but are intentional. For Topping Out, "ticket" and "job", and "blueprint" and "plan", are on that list.

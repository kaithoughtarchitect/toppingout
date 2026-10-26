## It's working if

- It reads the target type and two or three sibling types first, and judges against the repo's own way of expressing rules in types.
- It checks the boundaries first: where database rows, request bodies or parsed JSON enter typed code without being parsed.
- Each finding cites `file:line`, names the lens (boundary, expression, enforcement or usefulness), and gives a severity, a confidence and the smallest fix.
- It never reports a missing convention the repo does not use as a defect, such as branded types.
- A well-designed type gets a short paragraph naming what it does right, and nothing invented.
- It changed no code.

## Common questions

### Do I call it directly, or does `/f-inspect` run it?

`/f-inspect` runs it when the job changed types, schemas or invariants, as a fresh subagent with no context from the job.

### Does it change code?

It is told not to: it reports only. Its tools are read and search, plus a shell it is told to use only for read-only git, so this rests on its instructions, not on a lock.

### What does it look for?

Whether a type's shape forbids the states the business forbids, and whether outside data earns its type at the boundary. Typical findings are a cast that turns a plain string into a closed set, or an interface that copies a type already exported elsewhere.

### Does it only work for TypeScript?

No. Its examples are TypeScript, and it is told to translate each check to the type system and validation library of the language in front of it.

# The status block

(Not the bundled `f-status` skill: that's a longer catch-up summary for the owner. This block is the fixed 5-line footer.)

Every reply from the foreman ends with this. It is how the owner finds their place after a break.

```
f-status
where: <J-number and board number (e.g. J21, board 01 on the <board slug> board), ticket, which stage (work order m running / gate 1 / PR open ...)>
done:  <what this reply did>
state: <branch commits, pushed or not, captures, anything uncommitted>
owed:  <every decision or word the owner owes, and every pending act that needs the owner's word>
next:  <the next 2-3 steps, arrows between them>
```

Rules:
- `owed` never drops an item until it's done or the owner says drop it.
- `state` is measured (git, files), not remembered.
- Keep it to the heading plus five lines.

The pointer line the owner pastes into the builder:

```
Read the file <absolute path>, lines <A> to <B> only, and carry it out exactly as written.
```

## It's working if

- It shows a preview of short NEVER or ALWAYS bullets, each tagged with its destination and its source card ids, and writes nothing until you approve the exact bullets.
- Product lessons go to the repo's constitution; method lessons are shown as a diff to Topping Out's `RULES.md` or playbooks.
- A bullet that contradicts an existing rule is shown as a proposed change to that rule, with both texts.
- Approved bullets are merged into the existing NEVER/ALWAYS sections, with no new "Distillation" heading.
- Each source card gains a `distilled: <date> -> <destination>` line in its front matter.
- The report lists cards analysed, bullets written per destination, and the high-value cards that missed the cut on age or links.

## Common questions

### How does it pick which cards to promote?

It ranks cards on confidence, links, recency, how actionable they are and impact, with extra weight for anti-patterns and critical lessons. The number only orders candidates; it is not a percentage.

### Where do the rules end up?

Lessons about your codebase go to the constitution the repo profile names, `AGENTS.md` or `CLAUDE.md`. Lessons about how Topping Out works become a proposed change to the Topping Out package, made only on your word.

### Can a card overrule an existing rule?

Not by itself. A conflict is shown to you as a proposed change, with the old and new text.

### How many bullets will it propose?

There are caps per kind: 5 anti-patterns, 5 insights, 3 methods, 3 recent and 3 builds.

### How is it different from `/f-dream`?

This promotes the best cards upward into rules. `/f-dream` cleans up the cards themselves: duplicates, contradictions and repeated mistakes.

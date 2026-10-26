# Logbook

Topping Out's context management: durable, searchable lessons that outlive a job, so the next foreman doesn't relearn them. Cards are written at every `/f-signoff`, or on purpose with `/f-card`.

```
foreman/logbook/
├── logbook_index.md           # the card index, stats, clusters
├── logbook_links.md  # how cards relate (supersedes, refines, contradicts...)
├── entries/
│   ├── insights/             # INSIGHT: a reusable gotcha or principle (why)
│   ├── methods/              # METHOD: a repeatable procedure (how)
│   └── builds/             # BUILD: a compact record of what a job built
├── sessions/                 # frozen session archives
├── archived/                 # rotated card batches (and dreams/ proposals)
└── ARCHIVE-SYSTEM.md         # how rotation works
```

| Skill | When |
|---|---|
| `/f-shift` | every job start: loads the cards for the job's area ("cards in force"); runs `/f-archive` first past 250 cards |
| `/f-card` | mid-job, one durable lesson |
| `/f-signoff` | every close: writes the job's INSIGHT / METHOD / BUILD cards and updates the index |
| `/f-search`, `/f-archive-search` | find live or archived cards |
| `/f-context` | arriving at a repo cold, or before re-scoping: a full orientation with focus-matched cards |
| `/f-archive` | rotate past 250 live cards (keeps 50 index cards) |
| `/f-catchup` | once, to seed the Logbook from completed jobs that never got cards; or after a gap |
| `/f-dream` | now and then: merge duplicates, mark supersessions, find repeated mistakes (dry run first) |
| `/f-distill` | now and then: promote the best cards into the repo's constitution or Topping Out's rules, **on the owner's word** |

Rules: cards carry evidence and provenance; a card never overrides `RULES.md`; distilling into rules needs the owner's word.

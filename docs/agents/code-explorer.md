# code-explorer

Trace how an existing feature works through the code.

Stage: Kit · Agents that are optional
Source: `agents/code-explorer.md`

## On site

Optional: the foreman can use it while planning.

## When to use it

When the foreman needs to understand how an existing feature works.

## It's working if

- The report opens with the exploration ledger: one entry per step, each listing the files it actually opened and the `file:line` behind its key claim.
- Anything concluded from names, docs or string matches rather than read code is listed under `claims_inferred_not_verified`.
- The narrative cites `file:line` anchors instead of pasting code bodies.
- It states what it searched for and did not find, and the open questions it could not settle from code.
- It ends with the short list of files you need to understand the topic.
- It describes the code and gives no verdict on whether something is a bug; it changed nothing.

## How its report opens

The exploration ledger the agent fills before any narrative, shown exactly as the agent's instructions give it.

```
[
  {
    "step": "1-discovery",
    "files_examined": ["<path/to/file>", "..."],
    "evidence_anchor_for_key_claim": "<path/to/file>:<LINE>",
    "claims_inferred_not_verified": "none | <what you concluded without reading the code that proves it>"
  },
  {
    "step": "2-flow-tracing",
    "files_examined": ["..."],
    "evidence_anchor_for_key_claim": "...",
    "claims_inferred_not_verified": "..."
  },
  {
    "step": "3-architecture",
    "files_examined": ["..."],
    "evidence_anchor_for_key_claim": "...",
    "claims_inferred_not_verified": "..."
  },
  {
    "step": "4-implementation",
    "files_examined": ["..."],
    "evidence_anchor_for_key_claim": "...",
    "claims_inferred_not_verified": "..."
  }
]
```

## Common questions

### When does the foreman use it?

It is optional. While scoping or planning, the foreman may hand it bounded questions it cannot answer quickly itself, for example in `/f-survey` or `/f-blueprint`. Several explorers get questions that do not overlap.

### Does it change code?

No. It has no edit, write or shell tools, and it is told not to run git commands that write.

### Why does it stop before reading everything?

It reads on a budget: it maps the area first, then reads only the regions that matter. It stops as soon as it can trace the feature end to end, or when more reads only confirm what it already knows.

### Can it tell me whether something is a bug?

Not as a verdict. It returns the facts with their anchors and leaves the judgement to the caller, marking anything it could not anchor as inferred.

## Connections

- Used by: f-catchup, f-context

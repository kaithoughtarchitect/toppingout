---
name: f-card
description: >
  Create a single Logbook knowledge card from conversation context. Lightweight,
  no job required. Use when the user runs /f-card, says "capture this",
  "save this learning", "make a card for that", or when something just learned
  is worth persisting. One card from this conversation: not bulk extraction from
  completed jobs (f-catchup), and not promoting knowledge into the
  constitution (f-distill).
---

# Topping Out: Logbook quick card

Create a single knowledge card from conversation context. Lightweight, no job required.

---

## Usage

```
/f-card <type> <description>
```

**Examples:**

- `/f-card insight a re-aimed GREEN mutation probe hides a missing test`
- `/f-card method validated blueprint then execute`
- `/f-card build rate limiter for the login endpoint`

**Type:** `insight` | `method` | `build` (case-insensitive; `project` is accepted as an old alias and written as BUILD)

One card per invocation. Run again for additional cards.

---

## Instructions

You create a single Logbook knowledge card from the current conversation context. No session file needed. Fast and focused.

### Step 1: Parse Arguments

Extract `type` (first word) and `description` (rest of the line).

If no arguments provided, analyze the conversation and suggest up to 3 candidates:

```
What should I capture? I see these candidates in our conversation:

1. [INSIGHT] [description of something learned]
2. [METHOD] [description of a reusable approach]

Pick one (run /f-card again for additional cards).
```

### Step 2: Read Template

Read the matching template:

- INSIGHT → `foreman/logbook/entries/insights/INSIGHT-TEMPLATE.md`
- METHOD → `foreman/logbook/entries/methods/METHOD-TEMPLATE.md`
- BUILD → `foreman/logbook/entries/builds/BUILD-TEMPLATE.md`

### Step 3: Check for Duplicates

Extract 2-3 distinctive keywords from the description. Grep each in `foreman/logbook/entries/`, **excluding `*TEMPLATE*`** (the templates contain every field name and example cluster):

```
Grep "keyword1" in foreman/logbook/entries/ (files_with_matches, glob "!*TEMPLATE*")
Grep "keyword2" in foreman/logbook/entries/ (files_with_matches, glob "!*TEMPLATE*")
```

Check the first 5 results. If any match >80% of the card concept, warn:

```
Possible duplicate: INSIGHT_20260121_SIMILAR_NAME
- Read existing card to confirm overlap
- If confirmed: "This overlaps with [ID]. Add evidence to existing card instead? (y/n)"
- If not: proceed with new card
```

### Step 4: Generate Card ID

```
TYPE_YYYYMMDD_SHORT_NAME
```

- Date = today
- SHORT_NAME = 2-4 words from description, UPPER_SNAKE_CASE
- Examples: `INSIGHT_20260220_REAIMED_PROBE_HIDES_GAP`, `METHOD_20260220_BLUEPRINT_THEN_EXECUTE`

### Step 5: Generate Card Content

From the conversation context, fill in the template sections.

**For INSIGHT cards:**

- Overview, Impact (severity + evidence), Pattern Structure, Anti-Pattern, Evidence instances, Applications
- A **ruled-out** card (tag `ruled-out`, title "Ruled out: <option>"): a deliberate "no" on an option that could plausibly come back. It **must** fill the template's **Ruled out** section (**Why**, **Revisit if**). Other cards leave that section out, and the quality gate doesn't count it. Don't write one for an option nobody would propose again
- Set `confidence` based on evidence strength: 1 instance = 75%, 2+ instances = 85%, quantified = 95%

**For METHOD cards:**

- Overview, Impact (severity + evidence), Steps, Before/After Example, When to Use
- Set `success_rate` based on evidence: used once successfully = 100%, theoretical = 80%

**For BUILD cards:**

- Goal, Accomplished, Key Decisions, Methods Applied, Insights Discovered, Lessons Learned
- Set `scope`: MAJOR (8+h), SIGNIFICANT (4-8h), MODERATE (2-4h), MINOR (<2h)

**Frontmatter for all cards:**

- `cluster`: the repo's own list. Clusters **emerge from this repo's cards**: read the `## Clusters` section of `logbook_index.md` and the `cluster:` lines of existing cards, and reuse a slug already in use when the card fits it. A new Logbook starts from a few generic starter clusters:

| Cluster                | Topics                                          |
| ---------------------- | ----------------------------------------------- |
| `development-workflow` | Reviews, work orders, gates, iteration, tooling |
| `testing`              | Tests, probes, fixtures, flaky or slow suites   |
| `security`             | Auth, secrets, vulnerabilities, permissions     |
| `architecture`         | Module boundaries, data model, interfaces       |

Add a new slug (lowercase, hyphenated, named after the product area, e.g. `billing`, `search-index`, `db-migrations`) only when no existing one fits, and list it under `## Clusters` in `logbook_index.md` in the same pass as the card. When checking duplicates, search near-synonym slugs already in the corpus too (and array-valued clusters) rather than forcing a bad fit or minting a duplicate.

- `tags`: 3-6 specific keywords
- `impact`: CRITICAL (2-10x improvement) | HIGH (significant measurable) | MEDIUM (moderate) | LOW (minor)
- `session`: Use `conversation-YYYY-MM-DD` if no session exists

### Step 6: Quality Gate

Before showing the card, verify:

| Check                   | Requirement                          | If fails                                          |
| ----------------------- | ------------------------------------ | ------------------------------------------------- |
| All sections            | Every template section has content   | Fill from conversation or mark `[needs evidence]` |
| Confidence/success_rate | ≥ 70% (INSIGHT/METHOD; BUILD: n/a)   | Needs more evidence, warn user                   |
| Concrete example        | At least 1 specific instance         | Add from conversation context                     |
| Actionable              | Clear "when to use" / "applications" | Clarify                                           |

Score (a heuristic to catch thin cards, not a measurement; the checks above are what matter):

```
Base: 50
+20 all sections filled
+15 evidence strength: INSIGHT `confidence` ≥ 80% · METHOD `success_rate` ≥ 80% · BUILD: Accomplished cites a PR, merge sha or commit
+10 has concrete example
+5  has counter-example (INSIGHT only)
```

Minimum to create: **75/100**. If below, show score and missing items, ask user whether to fix or force-create.

### Step 7: Show Card and Confirm

Display the full card content to the user **before writing**:

```
## Card Preview: TYPE_YYYYMMDD_SHORT_NAME

[full card content]

---
Quality: 85/100
File: foreman/logbook/entries/{type}/TYPE_YYYYMMDD_SHORT_NAME.md

Create this card? (y/n)
```

Wait for confirmation. Do not write until approved.

### Step 8: Write Card File

After approval, save to:

```
foreman/logbook/entries/insights/INSIGHT_YYYYMMDD_NAME.md
foreman/logbook/entries/methods/METHOD_YYYYMMDD_NAME.md
foreman/logbook/entries/builds/BUILD_YYYYMMDD_NAME.md
```

Confirm:

```
Card created: TYPE_YYYYMMDD_SHORT_NAME
File: foreman/logbook/entries/{type}/TYPE_YYYYMMDD_SHORT_NAME.md
Cluster: [cluster] | Impact: [impact]

Run /f-distill to propose it for the constitution.
```

### Step 9: Update the index and links

A card isn't in the Logbook until the index lists it. In the same pass as the write:

1. Add a row to the right table in `foreman/logbook/logbook_index.md` (`| ID | Summary | Impact | Conf | Job |`; Conf is `confidence` or `success_rate`; Job is the card's `job:` or `none`), and bump that table's `(n)`.
2. **Recount from the files, never by adding one:** count `[A-Z]*_20*.md` under each of `entries/insights`, `entries/methods`, `entries/builds`, excluding `*TEMPLATE*`, and write `**Total Cards**: <sum> (<m> METHOD, <i> INSIGHT, <b> BUILD)` and `**Last Updated**`.
3. If the card names related cards (`related:`), add each edge to `foreman/logbook/logbook_links.md` (`| From | Type | To |`) and recount `**Total Links**` from the table rows.

If the live count is **greater than 250**, run `/f-archive` (dry-run). Do not `--execute` unless the owner says go.

---

## What This Does NOT Do

- Promote the card into the constitution (run `/f-distill` for that)
- Require or update a session file
- Create multiple cards (run again for more)

Intentionally lightweight: one card, in the right folder, listed in the index.

---
name: converse
description: >
  Sticky auto-speak mode for the current session: after every assistant reply, rewrite it into
  a short spoken explainer and play it via the same TTS pipeline as /speak, until turned off.
  Use when the user runs /converse, /converse on, /converse off, /converse status, or says
  "start converse mode", "converse on", "stop converse", "converse off", "stop auto speak",
  "stop speaking every reply", or wants hands-free listen-back for the whole session without
  typing /speak each time. Sticky and session-wide: for one reply read aloud once, use speak.
---

# Converse

Sticky **conversation listen-back**: once on, **every finished assistant reply** in this session
is spoken aloud (rewrite → TTS → play), until the user turns it off. No per-message `/speak`.

Uses the same engine as `/speak` (`scripts/speak.ts`, Grok Voice by default). Does **not**
replace a dictation tool for voice *input*, it only automates voice *output*.

---

## Usage

```
/converse              # turn ON (default)
/converse on           # turn ON
/converse off          # turn OFF
/converse status       # report whether mode is on
```

Natural-language equivalents (treat the same as the slash forms):

- ON: "start converse", "converse on", "auto speak from now on", "speak every reply"
- OFF: "stop converse", "converse off", "stop auto speak", "stop speaking every reply"

---

## State file

Persist mode in the repo root's `scratch/` working folder (keep `scratch/` gitignored):

- **Path:** `scratch/converse-mode`
- **ON contents:** a single line `on` (optionally a second line with ISO timestamp)
- **OFF / absent:** mode is off

Write or clear this file whenever you change mode so status and later turns can check it.

---

## Instructions

### 1. Parse intent

| User intent | Action |
|-------------|--------|
| `/converse`, `/converse on`, or ON phrases | Enable mode |
| `/converse off` or OFF phrases | Disable mode |
| `/converse status` | Report mode from the state file; do not change it |

If the user runs `/converse` with no args → **on**.

### 2. Turn ON

1. Write `scratch/converse-mode` with contents `on` (and optional timestamp line).
2. Reply with a short confirmation, e.g. `🔊 Converse on, every reply will be spoken until you say /converse off.`
3. Run the **speak pipeline** (below) on that confirmation so they hear that mode started.
4. **Stay sticky for the rest of this conversation** (see § Sticky duty).

### 3. Turn OFF

1. Delete `scratch/converse-mode`, or write a single line `off`.
2. Reply with a short confirmation, e.g. `Converse off, replies are silent again. Use /speak when you want one-off audio.`
3. Do **not** speak that confirmation (mode is already off).

### 4. Status

Read `scratch/converse-mode`. If missing or not starting with `on` → off. Report in one line. No TTS.

### 5. Sticky duty (the whole point)

**While converse is on** (state file is `on`, or you turned it on earlier this conversation and have not turned it off):

For **every subsequent assistant turn** that produces a real reply to the user:

1. Produce the **normal visible reply first** (full substance, do **not** collapse to only `🔊` like bare `/speak`).
2. Then run the **speak pipeline** on that reply (rewrite + play).
3. You may append a trailing `🔊` after the visible reply; optional.

Do **not** wait for the user to re-run `/converse` or `/speak`. Re-check the state file if unsure; if it says `on`, keep speaking every reply.

**Skip the speak pipeline only when:**

- Mode is off
- The turn is tool-only with no user-facing message
- The user is mid-turn only approving a dangerous action and you are asking a one-line confirm (still prefer speaking short confirms when mode is on)
- TTS already failed twice in a row this session, note once, keep replying in text, do not spam retries every turn

### 6. Speak pipeline (same rules as `/speak`)

**Rewrite, do not read the reply verbatim:**

- Plain, conversational tone, sharp friend over coffee. Warm, casual, not verbose.
- Gist and why in simple terms. Drop jargon, or define it in a few words if it matters.
- No code, no file paths, no markdown, no headings, no bullet lists read aloud, natural sentences only.
- Tight: ~20–60 seconds (~60–180 words). Key points only. Hard cap ~4000 characters.
- If the reply was already short, smooth it for speech; do not pad.

**Then:**

1. Write the rewritten explainer to `scratch/speak-input.txt` (overwrite).
2. Run: `npx tsx scripts/speak.ts scratch/speak-input.txt`
3. If the script errors, add a one-line note under the visible reply. Do not dump the rewritten explainer text unless the user asks.

Unlike bare `/speak`, the **visible chat reply stays the full answer**. Audio is an add-on.

### 7. Interaction with `/speak`

- `/speak` while converse is **on**: still works as a one-shot of whatever source `/speak` uses; then continue auto-speaking future replies.
- `/speak` while converse is **off**: unchanged (one-shot only).
- Prefer `/converse off` over telling the user to "ignore speak" when they want silence.

---

## Voice setup

Same as `/speak`, see `.claude/skills/speak/SKILL.md` (or its `.agents/skills/` mirror):

- `SPEAK_PROVIDER`, `grok` (default) or `hume`
- `SPEAK_GROK_VOICE`, `eve` | `ara` | `rex` | `sal` | `leo` (default)
- Hume: `SPEAK_VOICE_ID` via `scripts/speak-setup.ts`

---

## What this is not

- **Not** hands-free mic input (dictation / push-to-talk / always-listen tooling stays separate).
- **Not** multi-session routing.
- **Not** a permanent global preference across new sessions, each session starts **off** unless the user turns converse on again (stale `scratch/converse-mode` from a prior session: if the file says `on` at the start of a **new** conversation, treat it as off until the user explicitly re-enables, and clear or rewrite the file when they choose).

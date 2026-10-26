---
sample: Usage | 1
sample_title: How to call it
sample_note: The four forms it takes, shown exactly as the skill lists them.
---

## It's working if

- `/converse` writes `on` to `scratch/converse-mode`, confirms in one line, and you hear that confirmation.
- Every later reply shows its full text as usual and is also spoken as a short explainer.
- `/converse off` clears the state file and confirms in text, and that confirmation is not spoken.
- `/converse status` reports on or off in one line, without changing the mode or speaking.
- Turns that only run tools, with no message for you, are not spoken.
- After two failed speech attempts in a row it notes it once and carries on in text.

## Common questions

### How is it different from /speak?

`/speak` voices one reply and the chat shows only a speaker symbol. `/converse` speaks every reply until you turn it off, and the visible reply stays the full answer.

### Does it listen to me too?

No. It only automates voice output. Speaking to it needs a separate dictation tool.

### Does it stay on in a new session?

No. Each session starts off. If a stale `scratch/converse-mode` says `on` at the start of a new conversation, it is treated as off until you turn it on again.

### What does it need to run?

The same setup as `/speak`: `scripts/speak.ts`, `npx tsx` and the voice settings in `.env`, with Grok Voice through OpenRouter by default.

### Can I still use /speak while it is on?

Yes. `/speak` runs as a one-off, and converse carries on speaking later replies.

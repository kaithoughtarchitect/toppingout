---
name: speak
description: >
  Explain my last response aloud, rewrite it into a simple spoken explainer and
  play it via Grok Voice TTS. Use when the user runs /speak, says "say that out
  loud", "read that back", "explain that aloud", or when an output is dense and
  they want to listen instead of read. One reply at a time: to keep it on for
  every reply in the session, use converse.
---

# Speak

Turn my last message into a short **spoken explainer** and play it as audio. For when an output is
dense or complex and I want to *listen* to a plain-language version of it.

---

## Usage

```
/speak            # explain my previous message aloud
/speak <text>     # explain/voice the given text instead
```

Plays through the speakers. Default engine is **Grok Voice TTS** via OpenRouter (voice `leo`).
Configure it in the repo's `.env` (see "Voice setup" below). Needs Node with `npx tsx`, the bundled
`scripts/speak.ts` + `scripts/bootstrap-env.ts` in the repo, and Windows audio playback.
Run every command from the repo root; `scratch/` is a gitignored working folder there.

---

## Instructions

**Source text:** if arguments were passed to `/speak`, explain that text. Otherwise use your
**immediately preceding assistant message** (the one right before this `/speak` invocation).

**Rewrite it, do not read it verbatim:**

- Plain, conversational tone, like a sharp friend explaining it to me over coffee. Warm, casual, not verbose.
- Explain the *gist and the why* in simple terms. Drop jargon, or define it in a few words if it actually matters.
- No code, no file paths, no markdown, no headings, no bullet points read aloud, just natural spoken sentences.
- Keep it tight: ~20–60 seconds of speech (roughly 60–180 words). Hit the key point(s), not every detail. Hard cap ~4000 characters.
- If the source was already short and simple, just smooth it for speech rather than padding it.

**Then:**

1. Write the rewritten explainer to `scratch/speak-input.txt` in the repo root (overwrite it; create `scratch/` if missing).
2. Run: `npx tsx scripts/speak.ts scratch/speak-input.txt`

**Reply with only `🔊`** (plus a one-line note if the script printed an error). Do not show the
rewritten explainer text unless I ask for it.

---

## Voice setup / changing the narrator

`/speak` picks its engine from the repo-root `.env` (loaded by `scripts/bootstrap-env.ts`) and uses only that one (no fallback).

- **`SPEAK_PROVIDER`**, `grok` (default) or `hume`.
- **Grok** (default), xAI Grok Voice TTS via OpenRouter (`OPENROUTER_API_KEY`). ~10× cheaper than
  Hume, no setup step. Pick the voice with **`SPEAK_GROK_VOICE`**, one of `eve` (energetic),
  `ara` (warm), `rex` (confident), `sal` (balanced), or `leo` (authoritative, the default).
  These 5 are the only voices OpenRouter exposes; custom/cloned voices need xAI's native API.
- **Hume**, the saved Octave custom voice (`SPEAK_VOICE_ID`). Created once by
  `scripts/speak-setup.ts`, which designs + saves a Hume voice and prints a `SPEAK_VOICE_ID` for
  `.env`. Saved Hume voices are permanent (an id always resolves to the same voice), so
  switching/reverting is editing that one line. To mint a new one: edit `VOICE_DESCRIPTION` in that
  script, run `npx tsx scripts/speak-setup.ts`, then update `SPEAK_VOICE_ID`.

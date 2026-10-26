# speak

Read one reply out loud as a short spoken summary.

Command: `/speak`

Stage: Kit · Voice
Source: `skills/speak/SKILL.md`

## On site

Any time: the voice add-on. It can also read f-survey rounds aloud. Needs scripts/speak.ts, an OpenRouter key and Node.

## Say it

- "say that out loud"
- "read that back"
- "explain that aloud"

## When to use it

When you'd rather hear a reply than read it.

## It's working if

- You hear a short plain-language explainer, not the reply read out word for word.
- The spoken version has no code, file paths, headings or bullet points, and runs about 20 to 60 seconds.
- The rewritten text is saved to `scratch/speak-input.txt` and played with `npx tsx scripts/speak.ts scratch/speak-input.txt`.
- The chat reply is only a speaker symbol, plus a one-line note if the script printed an error.
- It speaks that one reply only, and later replies stay silent.

## How to call it

The two forms it takes, shown exactly as the skill lists them.

```
/speak            # explain my previous message aloud
/speak <text>     # explain/voice the given text instead
```

## Common questions

### What does it read out?

Your previous assistant reply, or the text you pass after `/speak`. It rewrites it as a short spoken explainer rather than reading it verbatim.

### What do I need to set it up?

Node with `npx tsx`, the bundled `scripts/speak.ts` and `scripts/bootstrap-env.ts`, Windows audio playback, and the repo's `.env`. The default engine is Grok Voice through OpenRouter, so it needs `OPENROUTER_API_KEY`.

### Can I change the voice?

Yes. Set `SPEAK_GROK_VOICE` to `eve`, `ara`, `rex`, `sal` or `leo` (the default). Setting `SPEAK_PROVIDER=hume` uses a saved Hume voice from `SPEAK_VOICE_ID` instead.

### Does it fall back to another engine if one fails?

No. It uses only the engine named in `.env`.

### How do I keep it on for every reply?

Use `/converse`. `/speak` is one reply at a time.

### Can I see the text it spoke?

Not by default. Ask and it will show it.

## Connections

- Used by: converse, f-survey

# Topping Out Gaffer (`addons/gaffer`)

Repo-only, hands-free site agent for your Topping Out boards and live Orca sessions: walk around with Bluetooth headphones on your PC, or carry your phone over Tailscale. Say `"Gaffer, ..."` (or `"Orca"` / `"Radio"`).

## Safety & Design

1. **Deterministic yes/cancel/repeat gate in code:** The LLM only has read, list, and `stage_reply` tools. It cannot call send. Once a reply is staged, the server speaks the exact session title and sanitized message back verbatim and parses explicit yes/cancel/repeat purely in code (90s expiry, 180s hard cap across repeats). Unclear answers re-prompt *"Say yes or cancel"* without calling the LLM. If TTS fails on the read-back, the staged reply is cancelled automatically.
2. **Voice provenance and gated-act guard:** Every dispatched message is prefixed with `[voice] ` so receiving coding agents can distinguish voice-relayed text from typed input. Standalone gated acts (`merge`, `push`, `open the PR`, `greploop`, migrations) and leading `/`, `!`, or `#` command prefixes are refused at staging and send time.
3. **Live target verification and receipt parsing:** Right before `orca terminal send`, the server runs `orca terminal show` to verify the terminal is still connected, writable, same `incarnationId`, and still running the expected agent. Send receipts parse `result.send.{accepted, refusedReason, prompt.{stages, observation}}`, report *"Accepted, turn not started"* when `turn_started` is absent, and retry unclear transport failures only with `--retry-request <id>`.
4. **Zero spend and zero polling while idle:** The UI does not open SSE until you tap **CONNECT GAFFER** (audio unlocked). When no audio-ready listener is connected (unless `GAFFER_LOCAL_AUDIO=1`), the watcher skips Orca polling and all paid LLM/TTS calls. Only decision stops alert by default (`GAFFER_ALL_STOPS=1` opts into all stops).
5. **Localhost-first with header/cookie remote auth:** Listens on `127.0.0.1:4111`, enforces `Host`/`Origin` + `X-ToppingOut-Gaffer: 1` CSRF protection, and locks remote/Tailscale connections unless `GAFFER_ALLOWED_TAILSCALE_USER` or `GAFFER_TOKEN` is set (`X-ToppingOut-Token` header exchanged for an `HttpOnly; SameSite=Strict` cookie via `POST /api/auth`; query-string tokens are rejected).
6. **Topping Out native awareness (Owner's Desk):** Classifies Foreman and managed Builder panes by shared Orca `tabId`, parses `f-status` `owed:` / `YOUR CALL` gates, reads `BOARD.json` (`read_board`, including single-lane and two-lane `next`) and active `JOB_*.md` files, and aggregates everything waiting on the owner (`list_owner_queue`). Suppresses routine managed-Builder work-order stops while its Foreman is working (never muting stops that show `owed:`, `YOUR CALL`, or a trust/permission prompt, and logging muted stops quietly to the UI), and routes replies aimed at a managed Builder safely to its owning Foreman prefixed with `[voice] (for builder <title>) ` unless direct builder targeting is explicitly requested. Non-Topping-Out Orca sessions continue working normally in the same channel.

## Data Sent to Models

When you ask about sessions, boards, or your owner queue, excerpts of `BOARD.json`, active `JOB_*.md` headers, and live session transcripts/terminal tails are sent to your configured Brain model (OpenRouter by default). Audio clips are sent to your configured STT provider, and spoken replies/alerts are sent to Grok Voice TTS via OpenRouter.

## Models & Settings

All `GAFFER_*` settings also accept legacy `ORCA_VOICE_*` names as fallbacks.

- **Brain:** `anthropic/claude-haiku-5.5` via OpenRouter (`GAFFER_LLM_MODEL`)
- **Voice (TTS):** `x-ai/grok-voice-tts-1.0` (`leo`) via OpenRouter (`SPEAK_GROK_VOICE`)
- **Ears (STT):** `gpt-4o-mini-transcribe` via OpenAI when `OPENAI_API_KEY` is set (unless `GAFFER_STT_PROVIDER=openrouter`), or OpenRouter audio (`openai/gpt-audio-mini` on 16kHz WAV/MP3, `google/gemini-3.8-flash` fallback for WebM/Ogg) on `OPENROUTER_API_KEY` alone

## Quick Start

### Around the house (PC Bluetooth headphones)

```bash
npx tsx addons/gaffer/server.ts
```

Open **`http://127.0.0.1:4111`**, choose your microphone and headphones under **AUDIO & MIC**, tap **CONNECT GAFFER**, and hit **TEST** once.

Optional headless Windows playback (alerts even with all browser tabs closed):
```bash
GAFFER_LOCAL_AUDIO=1 npx tsx addons/gaffer/server.ts
```

### Remote / Phone over Tailscale

Set either your Tailscale login identity or a shared access token before exposing over Tailscale Serve:

```bash
# Option A: allow your Tailscale identity header (recommended)
GAFFER_ALLOWED_TAILSCALE_USER="you@example.com" npx tsx addons/gaffer/server.ts

# Option B: require a shared access token (entered once under AUDIO & MIC on your phone)
GAFFER_TOKEN="your-random-secret" npx tsx addons/gaffer/server.ts
```

Then expose privately on your tailnet:
```bash
tailscale serve --bg --https=4111 http://127.0.0.1:4111
```

## Tests

```bash
npx tsx --test addons/gaffer/gaffer.test.ts
```

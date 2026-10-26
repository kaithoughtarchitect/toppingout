// ============================================
// /speak — synthesize + play text via TTS
// ============================================
// Reads a text file, synthesizes it, writes audio to scratch/, and plays it through
// the speakers (Windows, zero extra dependencies). Invoked by the /speak slash command:
//
//   npx tsx scripts/speak.ts scratch/speak-input.txt
//
// Provider is picked by SPEAK_PROVIDER (default "grok") — the selected one is used exclusively
// (no fallback; a failure fails loudly):
//   • grok — xAI Grok Voice TTS via OpenRouter (OPENROUTER_API_KEY). ~10x cheaper than Hume.
//            Voice via SPEAK_GROK_VOICE (default "leo"; one of eve/ara/rex/sal/leo). mp3 out.
//   • hume — Hume Octave custom voice (HUME_API_KEY + SPEAK_VOICE_ID). wav out.
//
// Env is loaded by ./bootstrap-env — a dependency-free loader for the repo-root .env
// (no `dotenv` needed). It MUST be the first import. Paths below are relative to the cwd,
// so run it from the repo root.
//
// TTS gate (optional coordination): writes scratch/tts-gate — `playing` before synth,
// `idle` on every exit after playing was set, including success, with a min dwell so
// pollers cannot miss a cycle. Any other local tool (e.g. a voice-input listener that
// should pause while audio plays) may poll it; nothing requires a reader.
import "./bootstrap-env";
import {
  readFileSync,
  writeFileSync,
  mkdirSync,
  renameSync,
  unlinkSync,
  existsSync,
} from "node:fs";
import { spawnSync } from "node:child_process";
import { resolve, dirname, join } from "node:path";

const SCRATCH_DIR = resolve("scratch");
const TTS_GATE_PATH = resolve(SCRATCH_DIR, "tts-gate");
const MAX_CHARS = 4800;

/** Default min time gate stays `playing` after the playing write (ms). Overridable via SPEAK_MIN_PLAYING_DWELL_MS. */
const DEFAULT_MIN_PLAYING_DWELL_MS = 1000;

type SynthResult = { ok: true; label: string } | { ok: false; reason: string };

let gateSetPlayingAt: number | null = null;

function sleepSync(ms: number): void {
  if (ms <= 0) return;
  spawnSync(process.execPath, ["-e", `Atomics.wait(new Int32Array(new SharedArrayBuffer(4)),0,0,${ms})`], {
    stdio: "ignore",
  });
}

/** Atomic write with EPERM/EBUSY retry (Windows). */
export function writeFileAtomicWithRetry(path: string, body: string, attempts = 5): void {
  mkdirSync(dirname(path), { recursive: true });
  const tmp = join(dirname(path), `.${Date.now()}-${Math.random().toString(16).slice(2)}.tmp`);
  let lastErr: unknown;
  for (let i = 0; i < attempts; i++) {
    try {
      writeFileSync(tmp, body, "utf8");
      renameSync(tmp, path);
      return;
    } catch (e) {
      lastErr = e;
      const code = (e as NodeJS.ErrnoException)?.code;
      try {
        if (existsSync(tmp)) unlinkSync(tmp);
      } catch {
        /* ignore */
      }
      if (code !== "EPERM" && code !== "EBUSY" && code !== "EACCES") throw e;
      sleepSync(20 * (i + 1));
    }
  }

  // ⚠️ Windows: renaming OVER an existing file fails with EPERM whenever anything
  // holds a handle on the destination — an indexer, antivirus, or a previous run that
  // has not released it yet. Observed repeatedly on scratch/tts-gate,
  // and ~300ms of backoff above was not enough. Atomicity is a nice-to-have for a
  // two-line advisory lock file; actually writing it is the point. Unlink the
  // destination and write directly as a last resort.
  try {
    if (existsSync(path)) unlinkSync(path);
    writeFileSync(path, body, "utf8");
    return;
  } catch {
    /* fall through to the original error, which is the more informative one */
  }
  throw lastErr instanceof Error ? lastErr : new Error(String(lastErr));
}

export function writeTtsGate(status: "playing" | "idle", path = TTS_GATE_PATH): void {
  const iso = new Date().toISOString();
  writeFileAtomicWithRetry(path, `${status}\n${iso}\n`);
  if (status === "playing") gateSetPlayingAt = Date.now();
}

export function restoreTtsGateIdle(path = TTS_GATE_PATH): void {
  if (gateSetPlayingAt == null) return;
  const dwell = Number(process.env.SPEAK_MIN_PLAYING_DWELL_MS || DEFAULT_MIN_PLAYING_DWELL_MS);
  const elapsed = Date.now() - gateSetPlayingAt;
  if (elapsed < dwell) sleepSync(dwell - elapsed);
  try {
    writeTtsGate("idle", path);
  } catch (e) {
    console.error(`⚠️  could not restore tts-gate idle: ${e}`);
  }
  gateSetPlayingAt = null;
}

function fail(msg: string): never {
  console.error(`❌ ${msg}`);
  restoreTtsGateIdle();
  process.exit(1);
}

async function synthGrok(text: string, outPath: string): Promise<SynthResult> {
  const apiKey = process.env.OPENROUTER_API_KEY;
  if (!apiKey) return { ok: false, reason: "OPENROUTER_API_KEY not set" };

  const voice = (process.env.SPEAK_GROK_VOICE || "leo").trim().toLowerCase();
  const res = await fetch("https://openrouter.ai/api/v1/audio/speech", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${apiKey}` },
    body: JSON.stringify({
      model: "x-ai/grok-voice-tts-1.0",
      input: text,
      voice,
      response_format: "mp3",
    }),
  });
  if (!res.ok) return { ok: false, reason: `Grok TTS ${res.status}: ${await res.text()}` };

  writeFileSync(outPath, Buffer.from(await res.arrayBuffer()));
  return { ok: true, label: `Grok (${voice})` };
}

async function synthHume(text: string, outPath: string): Promise<SynthResult> {
  const apiKey = process.env.HUME_API_KEY;
  const voiceId = process.env.SPEAK_VOICE_ID;
  if (!apiKey || !voiceId) return { ok: false, reason: "HUME_API_KEY / SPEAK_VOICE_ID not set" };

  const res = await fetch("https://api.hume.ai/v0/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Hume-Api-Key": apiKey },
    body: JSON.stringify({
      utterances: [
        { text, voice: { id: voiceId, provider: "CUSTOM_VOICE" }, trailing_silence: 0 },
      ],
      format: { type: "wav" },
      version: "1",
    }),
  });
  if (!res.ok) return { ok: false, reason: `Hume TTS ${res.status}: ${await res.text()}` };

  const data = (await res.json()) as { generations?: Array<{ audio?: string }> };
  const audio = data.generations?.[0]?.audio;
  if (!audio) return { ok: false, reason: "no audio in Hume response" };

  writeFileSync(outPath, Buffer.from(audio, "base64"));
  return { ok: true, label: "Hume (custom voice)" };
}

/** Injectable for tests — throws instead of process.exit. */
export type PlayFn = (file: string, estSecs: number) => void;

export function defaultPlay(file: string, estSecs: number): void {
  const isMp3 = file.toLowerCase().endsWith(".mp3");
  // NaturalDuration LIES on these mp3s — MediaPlayer reported 80.3s for a file that is really
  // ~112s (measured 2026-08-11), so sleeping for it clipped the last half-minute. Never use it
  // as the stop condition: play until $p.Position stops advancing, which is the only reliable
  // end-of-media signal here. NaturalDuration/estSecs survive only as a wall-clock safety cap.
  // If Position never advances at all (no position tracking), fall back to a padded blind sleep.
  const cmd = isMp3
    ? `Add-Type -AssemblyName presentationCore;` +
      `$p = New-Object System.Windows.Media.MediaPlayer;` +
      `$p.Open([System.Uri]::new('${file}'));` +
      `$t = 0; while (-not $p.NaturalDuration.HasTimeSpan -and $t -lt 25) { Start-Sleep -Milliseconds 100; $t++ };` +
      `$d = if ($p.NaturalDuration.HasTimeSpan) { $p.NaturalDuration.TimeSpan.TotalSeconds } else { 0 };` +
      `$cap = [math]::Max([double]$d, [double]${estSecs}) * 2 + 30;` +
      `$p.Play(); Start-Sleep -Milliseconds 1500;` +
      `if ($p.Position.TotalSeconds -le 0.05) { Start-Sleep -Seconds ([math]::Max([double]$d, [double]${estSecs}) + 3) }` +
      `else {` +
      `  $last = 0.0; $stall = 0; $deadline = (Get-Date).AddSeconds($cap);` +
      `  while ((Get-Date) -lt $deadline) {` +
      `    Start-Sleep -Milliseconds 250;` +
      `    $pos = $p.Position.TotalSeconds;` +
      `    if ($pos -gt $last + 0.05) { $last = $pos; $stall = 0 } else { $stall++ };` +
      `    if ($stall -ge 8) { break }` +
      `  }` +
      `};` +
      `Start-Sleep -Milliseconds 600; $p.Stop(); $p.Close()`
    : `(New-Object Media.SoundPlayer '${file}').PlaySync()`;

  const ps = spawnSync("powershell.exe", ["-NoProfile", "-Command", cmd], { stdio: "inherit" });
  if (ps.error) throw new Error(`could not launch player: ${ps.error.message}`);
  if (ps.status !== 0) throw new Error(`playback failed (player exit ${ps.status})`);
}

export type SpeakOptions = {
  inputPath: string;
  play?: PlayFn;
  gatePath?: string;
  skipSynth?: boolean;
  /** Test hook: skip network synth and write a tiny placeholder file */
  fixtureAudioPath?: string;
};

/**
 * Exported for offline tests. Writes tts-gate playing before synth, idle in finally.
 */
export async function runSpeak(opts: SpeakOptions): Promise<void> {
  const gatePath = opts.gatePath ?? TTS_GATE_PATH;
  gateSetPlayingAt = null;
  const playFn = opts.play ?? defaultPlay;

  const onSignal = () => {
    restoreTtsGateIdle(gatePath);
    process.exit(130);
  };
  process.once("SIGINT", onSignal);
  process.once("SIGTERM", onSignal);

  try {
    let text = readFileSync(opts.inputPath, "utf8").trim();
    if (!text) throw new Error(`input file is empty: ${opts.inputPath}`);
    if (text.length > MAX_CHARS) {
      console.warn(`⚠️  input ${text.length} chars > ${MAX_CHARS}; truncating`);
      text = text.slice(0, MAX_CHARS);
    }

    mkdirSync(SCRATCH_DIR, { recursive: true });

    // `playing` before synth, so a gate reader does not treat the synth wait as idle.
    //
    // ⚠️ ADVISORY, so a failure to write it must NOT kill playback. This used to abort
    // the whole run, which meant an unwritable two-line lock file silently cost the
    // user their audio — repeatedly on Windows, where renaming over a
    // held file fails routinely. The worst case if the gate is not set is that two
    // speaks overlap; the worst case of aborting is that the feature does not work.
    // Degrade, never lose the thing the user asked for.
    try {
      writeTtsGate("playing", gatePath);
    } catch (e) {
      console.warn(`⚠️  could not set tts-gate playing (continuing anyway): ${e}`);
    }

    const provider = (process.env.SPEAK_PROVIDER || "grok").trim().toLowerCase();
    console.log(`🗣️  Synthesizing ${text.length} chars…`);
    const outPath = opts.fixtureAudioPath
      ? opts.fixtureAudioPath
      : resolve(SCRATCH_DIR, provider === "hume" ? "speak.wav" : "speak.mp3");

    if (!opts.fixtureAudioPath) {
      const done = provider === "hume" ? await synthHume(text, outPath) : await synthGrok(text, outPath);
      if (!done.ok) throw new Error(`${provider} TTS failed: ${done.reason}`);
      console.log(`💾 ${outPath}  (${done.label})`);
    } else {
      writeFileSync(outPath, Buffer.from("RIFF")); // placeholder if missing — tests may pre-create
    }

    console.log("🔊 Playing…");
    playFn(outPath, Math.ceil(text.length / 13) + 2);
    console.log("✅ Done.");
  } finally {
    process.off("SIGINT", onSignal);
    process.off("SIGTERM", onSignal);
    restoreTtsGateIdle(gatePath);
  }
}

export async function main(argv = process.argv): Promise<void> {
  const inputPath = argv[2];
  if (!inputPath) throw new Error("usage: tsx scripts/speak.ts <text-file>");
  await runSpeak({ inputPath });
}

// Auto-run only when executed as the entry script (so tests can import it)
const isEntry =
  typeof process.argv[1] === "string" &&
  (process.argv[1].endsWith("speak.ts") || process.argv[1].endsWith("speak.js"));

if (isEntry && process.env.SPEAK_NO_AUTORUN !== "1") {
  main().catch((err) => fail(String(err?.stack || err)));
}

// Speech I/O:
// - STT: OpenAI gpt-4o-mini-transcribe when OPENAI_API_KEY is set (unless GAFFER_STT_PROVIDER=openrouter),
//   or OpenRouter native audio (openai/gpt-audio-mini on WAV/MP3; google/gemini-3.8-flash on WebM/Ogg)
// - TTS: xAI Grok Voice TTS via OpenRouter (voice "leo" default, same as scripts/speak.ts)
import { gafferEnv } from "./env.js";
import { writeFileSync, unlinkSync } from "node:fs";
import { spawn } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";

export interface TranscribeResult {
  text: string;
  ignored: boolean;
  reason?: string;
}

// Keep the STT vocabulary hint short and strictly NEUTRAL: NEVER include action words
// like "yes", "cancel", or "stop", because Whisper/transcribe can echo the prompt on low-volume audio.
const DOMAIN_PROMPT = "Gaffer, Orca, Topping Out, Foreman, Claude, Antigravity, Codex, Pi.";
const PROMPT_TOKENS = new Set(
  DOMAIN_PROMPT.toLowerCase()
    .replace(/[^a-z0-9\s]+/g, " ")
    .split(/\s+/)
    .filter((w) => w.length >= 3)
);

// Known Whisper hallucinations emitted on silence / background room noise.
const SILENCE_HALLUCINATIONS = new Set([
  "thank you",
  "thank you.",
  "thanks for watching",
  "thanks for watching.",
  "thank you for watching",
  "thank you for watching.",
  "you",
  "you.",
  "bye",
  "bye.",
  "bye-bye",
  "mbc",
  "mbc news",
  "subtitles by",
  "amara.org",
  "topping out",
  "topping out.",
  "mm-hmm",
  "mm-hmm.",
  "mmhmm",
  "mmhmm.",
  "mhm",
  "mhm.",
  "hmm",
  "hmm.",
  "hm",
  "hm.",
  "okay",
  "okay.",
  "ok",
  "ok.",
  "uh",
  "uh.",
  "um",
  "um.",
  "uh-huh",
  "uh-huh.",
  "...",
  ".",
]);

export function isPromptEcho(text: string): boolean {
  const norm = text
    .toLowerCase()
    .replace(/[^a-z0-9\s]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!norm) return false;
  const promptNorm = DOMAIN_PROMPT.toLowerCase()
    .replace(/[^a-z0-9\s]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (norm === promptNorm || promptNorm.includes(norm) && norm.split(" ").length >= 3) {
    return true;
  }
  const words = norm.split(" ").filter((w) => w.length >= 3);
  if (words.length >= 4) {
    const distinctHits = new Set(words.filter((w) => PROMPT_TOKENS.has(w))).size;
    const overlap = words.filter((w) => PROMPT_TOKENS.has(w)).length;
    if (overlap / words.length >= 0.65 || distinctHits >= 4) return true;
  }
  return false;
}

const NON_SPEECH_REFUSAL_RE =
  /^\[?silence\]?$|^\[?no speech\]?$|can(?:'t|not)\s+(?:transcribe|understand|hear|process|make out)(?:\s+the)?\s+audio|unable\s+to\s+(?:transcribe|understand|hear)|no\s+(?:audible|intelligible)?\s*speech|audio\s+(?:clip\s+)?(?:is\s+)?(?:silent|empty|blank)|i(?:'m| am)\s+sorry,?\s+(?:but\s+)?i\s+can(?:'t|not)|could you provide more details|please provide (?:the )?audio|let me know how you(?:'d| would) like to proceed/i;

export function isHallucinatedSilence(text: string): boolean {
  const norm = text
    .replace(/[\u2018\u2019]/g, "'")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
  if (!norm || norm.length < 2) return true;
  if (SILENCE_HALLUCINATIONS.has(norm)) return true;
  if (NON_SPEECH_REFUSAL_RE.test(norm)) return true;
  if (/^[\s.,!?…♪♫\[\]()-]+$/.test(norm)) return true;
  if (isPromptEcho(norm)) return true;
  return false;
}

/**
 * Correct common speech-to-text manglings of "Gaffer", "Orca", and "Radio" on Bluetooth mics
 * (e.g. "gaffa"/"gafa", "AUCA", "Orka", leading "Walker, ...", and leading "Radial, ...").
 */
export function normalizeTranscript(raw: string): string {
  return raw
    .trim()
    .replace(/\b(gaffa|gafa|gafer)\b/gi, "Gaffer")
    .replace(/\b(auca|orka|orcha|alk[ae]|awka|oka|oca)\b/gi, "Orca")
    .replace(/^(?:hey\s+|ok(?:ay)?\s+)?(walker|waka|worker)(?=[\s,.:;!?]|$)/i, (m, w) =>
      m.slice(0, m.length - w.length) + "Orca"
    )
    .replace(/^(?:hey\s+|ok(?:ay)?\s+)?(radial|radeo)(?=[\s,.:;!?]|$)/i, (m, w) =>
      m.slice(0, m.length - w.length) + "Radio"
    );
}

async function transcribeViaOpenRouter(
  audioBuffer: Buffer,
  mimeType: string,
  apiKey: string
): Promise<string> {
  const format = mimeType.includes("mp4") || mimeType.includes("m4a")
    ? "mp4"
    : mimeType.includes("ogg")
      ? "ogg"
      : mimeType.includes("wav")
        ? "wav"
        : mimeType.includes("mpeg") || mimeType.includes("mp3")
          ? "mp3"
          : "webm";

  const configuredModel = (gafferEnv("OR_STT_MODEL") || "openai/gpt-audio-mini").trim();
  // OpenAI audio models on OpenRouter accept only wav/mp3; fall back cleanly to Gemini 3.8 Flash for webm/ogg/mp4.
  const model =
    configuredModel.startsWith("openai/") && format !== "wav" && format !== "mp3"
      ? "google/gemini-3.8-flash"
      : configuredModel;
  const lang = (gafferEnv("LANGUAGE") ?? "en").trim();
  const langHint =
    lang && lang.toLowerCase() !== "auto"
      ? ` Primary language: ${lang}.`
      : "";
  const res = await fetch("https://openrouter.ai/api/v1/chat/completions", {
    method: "POST",
    signal: AbortSignal.timeout(25_000),
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model,
      temperature: 0,
      messages: [
        {
          role: "system",
          content:
            "Strict speech-to-text engine. Output ONLY the exact spoken words from the user's audio, with no quotes or commentary. If the audio contains only silence or noise with no clear speech, output ONLY [SILENCE]." +
            langHint,
        },
        {
          role: "user",
          content: [
            {
              type: "text",
              text: "Transcribe this audio clip verbatim.",
            },
            {
              type: "input_audio",
              input_audio: {
                data: audioBuffer.toString("base64"),
                format,
              },
            },
          ],
        },
      ],
    }),
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`OpenRouter STT failed (${res.status}): ${body.slice(0, 300)}`);
  }

  const data = (await res.json()) as {
    choices?: Array<{ message?: { content?: string | null } }>;
  };
  return (data.choices?.[0]?.message?.content || "").trim();
}

export async function transcribeAudio(
  audioBuffer: Buffer,
  mimeType = "audio/webm"
): Promise<TranscribeResult> {
  const openaiKey = process.env.OPENAI_API_KEY;
  const openrouterKey = process.env.OPENROUTER_API_KEY;
  const pref = (gafferEnv("STT_PROVIDER") || "").trim().toLowerCase();

  if (!openaiKey && !openrouterKey) {
    throw new Error("Set OPENROUTER_API_KEY or OPENAI_API_KEY for speech-to-text.");
  }
  if (!audioBuffer || audioBuffer.byteLength < 1200) {
    return { text: "", ignored: true, reason: "audio clip too short" };
  }

  const useOpenRouter =
    pref === "openrouter" || (pref !== "openai" && !openaiKey && Boolean(openrouterKey));
  let rawText = "";

  if (useOpenRouter && openrouterKey) {
    rawText = await transcribeViaOpenRouter(audioBuffer, mimeType, openrouterKey);
  } else {
    const ext = mimeType.includes("mp4")
      ? "m4a"
      : mimeType.includes("ogg")
        ? "ogg"
        : mimeType.includes("wav")
          ? "wav"
          : mimeType.includes("mpeg") || mimeType.includes("mp3")
            ? "mp3"
            : "webm";

    const model = (gafferEnv("STT_MODEL") || "gpt-4o-mini-transcribe").trim();

    const callStt = async (useModel: string) => {
      const form = new FormData();
      const blob = new Blob([new Uint8Array(audioBuffer)], { type: mimeType });
      form.append("file", blob, `utterance.${ext}`);
      form.append("model", useModel);
      form.append("prompt", DOMAIN_PROMPT);
      const lang = (gafferEnv("LANGUAGE") ?? "en").trim();
      if (lang && lang.toLowerCase() !== "auto") {
        form.append("language", lang);
      }
      return fetch("https://api.openai.com/v1/audio/transcriptions", {
        method: "POST",
        signal: AbortSignal.timeout(25_000),
        headers: { Authorization: `Bearer ${openaiKey!}` },
        body: form,
      });
    };

    let res = await callStt(model);
    if (!res.ok && model !== "whisper-1") {
      res = await callStt("whisper-1");
    }
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new Error(`STT failed (${res.status}): ${body.slice(0, 300)}`);
    }

    const data = (await res.json()) as { text?: string };
    rawText = (data.text || "").trim();
  }

  if (isHallucinatedSilence(rawText)) {
    return { text: "", ignored: true, reason: `filtered noise/echo: "${rawText.slice(0, 60)}"` };
  }

  return {
    text: normalizeTranscript(rawText),
    ignored: false,
  };
}

export async function synthesizeGrokSpeech(text: string): Promise<Buffer> {
  const apiKey = process.env.OPENROUTER_API_KEY;
  if (!apiKey) {
    throw new Error("OPENROUTER_API_KEY is not set (needed for Grok Voice TTS).");
  }

  const cleaned = text.trim().slice(0, 3800);
  if (!cleaned) {
    throw new Error("Cannot synthesize empty speech text.");
  }

  const voice = (process.env.SPEAK_GROK_VOICE || "leo").trim().toLowerCase();
  const res = await fetch("https://openrouter.ai/api/v1/audio/speech", {
    method: "POST",
    signal: AbortSignal.timeout(25_000),
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: "x-ai/grok-voice-tts-1.0",
      input: cleaned,
      voice,
      response_format: "mp3",
    }),
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Grok TTS failed (${res.status}): ${body.slice(0, 300)}`);
  }

  return Buffer.from(await res.arrayBuffer());
}

let localPlayQueue: Promise<void> = Promise.resolve();

/**
 * Play an MP3 buffer directly through the host's Windows audio device (headphones/speakers),
 * queued sequentially so overlapping alerts never talk over each other.
 */
export function playMp3Locally(mp3: Buffer): Promise<void> {
  if (process.platform !== "win32") return Promise.resolve();
  const run = () =>
    new Promise<void>((resolveDone) => {
      const tmpFile = join(
        tmpdir(),
        `gaffer-${Date.now()}-${Math.random().toString(16).slice(2, 6)}.mp3`
      );
      writeFileSync(tmpFile, mp3);
      const estSecs = Math.max(4, Math.ceil(mp3.byteLength / 16000) + 2);
      const escaped = tmpFile.replace(/'/g, "''");
      const cmd =
        `Add-Type -AssemblyName presentationCore;` +
        `$p = New-Object System.Windows.Media.MediaPlayer;` +
        `$p.Open([System.Uri]::new('${escaped}'));` +
        `$t = 0; while (-not $p.NaturalDuration.HasTimeSpan -and $t -lt 25) { Start-Sleep -Milliseconds 100; $t++ };` +
        `$d = if ($p.NaturalDuration.HasTimeSpan) { $p.NaturalDuration.TimeSpan.TotalSeconds } else { 0 };` +
        `$cap = [math]::Max([double]$d, [double]${estSecs}) * 2 + 15;` +
        `$p.Play(); Start-Sleep -Milliseconds 1000;` +
        `if ($p.Position.TotalSeconds -le 0.05) { Start-Sleep -Seconds ([math]::Max([double]$d, [double]${estSecs}) + 2) }` +
        `else {` +
        `  $last = 0.0; $stall = 0; $deadline = (Get-Date).AddSeconds($cap);` +
        `  while ((Get-Date) -lt $deadline) {` +
        `    Start-Sleep -Milliseconds 250;` +
        `    $pos = $p.Position.TotalSeconds;` +
        `    if ($pos -gt $last + 0.05) { $last = $pos; $stall = 0 } else { $stall++ };` +
        `    if ($stall -ge 6) { break }` +
        `  }` +
        `};` +
        `Start-Sleep -Milliseconds 400; $p.Stop(); $p.Close()`;

      const child = spawn("powershell.exe", ["-NoProfile", "-Command", cmd], {
        stdio: "ignore",
        windowsHide: true,
      });
      const cleanup = () => {
        try {
          unlinkSync(tmpFile);
        } catch {
          /* ignore */
        }
        resolveDone();
      };
      child.on("exit", cleanup);
      child.on("error", cleanup);
    });

  localPlayQueue = localPlayQueue.then(run, run);
  return localPlayQueue;
}

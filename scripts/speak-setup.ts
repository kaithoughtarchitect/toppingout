// ============================================
// /speak — one-time narrator voice setup
// ============================================
// Designs + saves a single Hume Octave voice (warm, casual female narrator) and
// prints the SPEAK_VOICE_ID to paste into .env. Run once; speak.ts reuses the
// saved voice on every /speak so the narrator timbre stays consistent.
//
//   npx tsx scripts/speak-setup.ts
//
// Env (HUME_API_KEY) is loaded by ./bootstrap-env — a dependency-free loader for the
// repo-root .env (no `dotenv` needed). It MUST be the first import.
import "./bootstrap-env";

const HUME_API_BASE = "https://api.hume.ai/v0/tts";

// ── MINTED VOICES ───────────────────────────────────────────────────────────
// Saved Hume voices are permanent — an id always resolves to that exact voice —
// so to switch or revert, just set SPEAK_VOICE_ID in .env to an id you minted.
// Voice ids belong to the Hume account that saved them; record yours here, e.g.
//   v0  <short description of the voice>   <SPEAK_VOICE_ID printed by this script>
// Re-running always mints a brand-new id from VOICE_DESCRIPTION below.
// ────────────────────────────────────────────────────────────────────────────

// The voice we're designing. Tweak this string + re-run to change the narrator.
const VOICE_DESCRIPTION =
  "A warm, friendly female narrator in her early thirties with a natural London accent — " +
  "contemporary Southern English, modern and relaxed, not posh or RP. Softly spoken and " +
  "gentle, but upbeat and chatty — like a sharp friend happily talking you through " +
  "something over coffee. Light, easy-going energy, natural conversational pacing, clear " +
  "and easy to follow, lightly expressive but never theatrical or harsh.";

// A neutral line used only to let Octave hear + fix the timbre during design.
const SAMPLE_TEXT =
  "Okay, so here's the gist of it in plain terms. Let me walk you through what's " +
  "actually going on, step by step, the way I'd explain it to a friend.";

function fail(msg: string): never {
  console.error(`❌ ${msg}`);
  process.exit(1);
}

async function main(): Promise<void> {
  const apiKey = process.env.HUME_API_KEY;
  if (!apiKey) fail("HUME_API_KEY is not set in .env");

  // 1) Design a voice from the description -> generation_id
  console.log("🎨 Designing narrator voice…");
  const designRes = await fetch(HUME_API_BASE, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Hume-Api-Key": apiKey },
    body: JSON.stringify({
      utterances: [{ text: SAMPLE_TEXT, description: VOICE_DESCRIPTION }],
      format: { type: "mp3" },
      version: "1",
    }),
  });
  if (!designRes.ok) fail(`Voice design failed: ${designRes.status} ${await designRes.text()}`);

  const designData = (await designRes.json()) as {
    generations?: Array<{ generation_id?: string }>;
  };
  const generationId = designData.generations?.[0]?.generation_id;
  if (!generationId) fail("No generation_id in Hume design response");

  // 2) Save the designed voice -> stable voiceId
  console.log("💾 Saving voice…");
  const name = `speak-narrator-${Date.now().toString(36)}`;
  const saveRes = await fetch(`${HUME_API_BASE}/voices`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Hume-Api-Key": apiKey },
    body: JSON.stringify({ name, generation_id: generationId }),
  });
  if (!saveRes.ok) fail(`Voice save failed: ${saveRes.status} ${await saveRes.text()}`);

  const saveData = (await saveRes.json()) as { id?: string };
  const voiceId = saveData.id;
  if (!voiceId) fail("No voice id in Hume save response");

  console.log("\n✅ Narrator voice created.");
  console.log(`   name: ${name}`);
  console.log(`   SPEAK_VOICE_ID=${voiceId}`);
  console.log("\nAdd that line to your .env (speak.ts reads it).");
}

main().catch((err) => fail(String(err?.stack || err)));

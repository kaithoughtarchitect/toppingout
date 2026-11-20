#!/usr/bin/env node
// Tests for the pure parts of plancheck-dispatch.mjs that read pi (the
// OpenRouter door): the catalog row, the output cap and the JSON event stream.
//   node skills/f-plancheck/plancheck-dispatch.test.mjs
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { validateRoster } from "./plancheck-pick.mjs";
import {
  AGY_DENY_RULES,
  agyModelListed,
  agySeatSettings,
  agyUsageLimitOf,
  buildArgvForSeat,
  parseAgyOutput,
  resolveSeats,
  seatEnv,
  findPiModelRow,
  MAX_SEAT_OUTPUT_TOKENS,
  overSeatOutputCap,
  parsePiJsonEvents,
  parseTokenCount,
  PI_CUSTOM_MODEL_ID_RE,
} from "./plancheck-dispatch.mjs";

let n = 0;
function t(name, fn) { fn(); n++; console.log(`ok ${n} ${name}`); }

const LIST_CAPPED = [
  "provider    model                         context  max-out  thinking  images",
  "openrouter  google/gemini-4-carbon        1.0M     65.5K    yes       yes   ",
  "openrouter  google/gemini-4-carbon:batch  1.0M     943.7K   yes       yes   ",
].join("\r\n");
const LIST_UNCAPPED = LIST_CAPPED.replace("65.5K ", "943.7K");

t("token counts", () => {
  assert.equal(parseTokenCount("65.5K"), 65500);
  assert.equal(parseTokenCount("943.7K"), 943700);
  assert.equal(parseTokenCount("1.0M"), 1000000);
  assert.equal(parseTokenCount("16384"), 16384);
  assert.equal(parseTokenCount("-"), null);
});

t("exact catalog row, not the :batch one", () => {
  assert.deepEqual(findPiModelRow(LIST_CAPPED, "google/gemini-4-carbon"), { found: true, maxOut: 65500 });
  assert.deepEqual(findPiModelRow(LIST_UNCAPPED, "google/gemini-4-carbon"), { found: true, maxOut: 943700 });
});

t("a missing model is not found (pi exits 0 either way)", () => {
  assert.equal(findPiModelRow('No models matching "google/gemini-9"', "google/gemini-9").found, false);
  assert.equal(findPiModelRow(LIST_CAPPED, "google/gemini-4").found, false);
});

t("the output cap", () => {
  assert.equal(overSeatOutputCap(65500), false);
  assert.equal(overSeatOutputCap(MAX_SEAT_OUTPUT_TOKENS), false);
  assert.equal(overSeatOutputCap(943700), true);
  assert.equal(overSeatOutputCap(null), false);
});

t("pi's custom-model-id warning", () => {
  assert.ok(PI_CUSTOM_MODEL_ID_RE.test('Model "google/gemini-4-carbon" not found for provider "openrouter". Using custom model id.'));
  assert.ok(!PI_CUSTOM_MODEL_ID_RE.test("Model catalogs refreshed"));
});

const ev = (o) => JSON.stringify(o);
const usage = (total) => ({ input: 1, output: 1, cost: { total } });
const FINISHED = [
  ev({ type: "session", version: 3, id: "x" }),
  ev({ type: "message_start", message: { role: "user", content: "go" } }),
  ev({ type: "message_end", message: { role: "user", content: "go" } }),
  ev({ type: "message_start", message: { role: "assistant", content: [] } }),
  ev({ type: "message_end", message: { role: "assistant", stopReason: "toolUse", content: [{ type: "thinking", thinking: "" }, { type: "toolCall" }], usage: usage(0.00077925) } }),
  ev({ type: "tool_execution_end", toolCallId: "c", toolName: "read", result: { content: [{ type: "text", text: "Error: 429 Too Many Requests in a file it read" }] } }),
  ev({ type: "message_start", message: { role: "assistant", content: [] } }),
  ev({ type: "message_update", usage: usage(0.0003), assistantMessageEvent: { type: "text_delta", contentIndex: 0, delta: "[MINOR] a.txt:1 " } }),
  ev({ type: "message_end", message: { role: "assistant", stopReason: "stop", content: [{ type: "text", text: "[MINOR] a.txt:1 says hello" }], usage: usage(0.00057) } }),
  ev({ type: "agent_settled", aborted: false }),
].join("\n") + "\n";

t("finished stream: final text and summed spend", () => {
  const r = parsePiJsonEvents(FINISHED);
  assert.equal(r.finalText, "[MINOR] a.txt:1 says hello");
  assert.equal(r.spendUsd, 0.001349);
  assert.equal(r.errorMessage, null);
  assert.ok(!r.partialText.includes("429"), "tool results are not the seat's text");
});

t("killed mid-answer: the trace so far and the running spend, no final text", () => {
  const killed = [
    ev({ type: "message_start", message: { role: "assistant", content: [] } }),
    ev({ type: "message_end", message: { role: "assistant", stopReason: "toolUse", content: [{ type: "thinking", thinking: "Read the plan first." }, { type: "toolCall", name: "read", arguments: { path: "plan.md" } }], usage: usage(0.5) } }),
    ev({ type: "message_start", message: { role: "assistant", content: [] } }),
    ev({ type: "message_update", usage: usage(0.05), assistantMessageEvent: { type: "thinking_delta", contentIndex: 0, delta: "Step 4 comes " } }),
    ev({ type: "message_update", usage: usage(0.08), assistantMessageEvent: { type: "thinking_delta", contentIndex: 0, delta: "before step 2." } }),
    ev({ type: "message_update", usage: usage(0.1), assistantMessageEvent: { type: "text_delta", contentIndex: 1, delta: "[CRITICAL] plan.md:4 " } }),
    ev({ type: "message_update", usage: usage(0.25), assistantMessageEvent: { type: "text_delta", contentIndex: 1, delta: "the step order is wrong" } }),
    '{"type":"message_update","usage":{"cost"', // cut off by the kill
  ].join("\n");
  const r = parsePiJsonEvents(killed);
  assert.equal(r.finalText, null);
  assert.equal(r.partialText, [
    "(thinking) Read the plan first.",
    '> read {"path":"plan.md"}',
    "(thinking) Step 4 comes before step 2.",
    "[CRITICAL] plan.md:4 the step order is wrong",
  ].join("\n\n"));
  assert.equal(r.spendUsd, 0.75);
});

t("killed while still thinking: the trace is the thinking and tool calls", () => {
  const thinking = [
    ev({ type: "message_start", message: { role: "assistant", content: [] } }),
    ev({ type: "message_update", usage: usage(0.01), assistantMessageEvent: { type: "thinking_delta", contentIndex: 0, delta: "Look around." } }),
    ev({ type: "message_update", assistantMessageEvent: { type: "toolcall_end", contentIndex: 1, toolCall: { type: "toolCall", name: "ls", arguments: { path: "." } } } }),
  ].join("\n");
  const r = parsePiJsonEvents(thinking);
  assert.equal(r.partialText, '(thinking) Look around.\n\n> ls {"path":"."}');
  assert.equal(r.spendUsd, 0.01);
});

t("a 402 is the error message, with no final text", () => {
  const refused = ev({ type: "message_end", message: { role: "assistant", stopReason: "error", content: [], errorMessage: "402 You requested up to 942756 tokens, but can only afford 695816", usage: usage(0) } });
  const r = parsePiJsonEvents(refused);
  assert.equal(r.finalText, null);
  assert.match(r.errorMessage, /can only afford/);
});

t("the OpenRouter argv streams JSON events", () => {
  const argv = buildArgvForSeat({ doorSlug: "openrouter", model: "google/gemini-4-carbon" }, { cwd: process.cwd(), absAssignmentPath: `${process.cwd()}/a.md` });
  assert.deepEqual(argv.slice(0, 3), ["-p", "--mode", "json"]);
  assert.ok(argv.includes("openrouter/google/gemini-4-carbon"));
});

t("the models.json template caps every OpenRouter row in the roster", () => {
  const read = (f) => JSON.parse(fs.readFileSync(new URL(f, import.meta.url), "utf8"));
  const caps = read("./plancheck-pi-models.json").providers.openrouter.modelOverrides;
  for (const m of read("./plancheck-roster.json").models.filter((r) => r.door === "OpenRouter")) {
    assert.ok(caps[m.slug], `no cap for ${m.slug}`);
    assert.ok(!overSeatOutputCap(caps[m.slug].maxTokens), `cap too high for ${m.slug}`);
  }
});

// ── the agy CLI door (Gemini on a Google AI Pro subscription) ──

t("the agy argv: assignment named in the prompt, bare model plus --effort, writes and commands denied", () => {
  const cwd = process.cwd();
  const argv = buildArgvForSeat({ doorSlug: "agy", model: "gemini-4-hydrogen" }, { cwd, absAssignmentPath: path.join(cwd, "scratch", "a.md") });
  assert.equal(argv[0], "-p");
  assert.ok(argv[1].includes(path.join("scratch", "a.md")), "the prompt names the assignment file");
  const at = (flag) => argv[argv.indexOf(flag) + 1];
  assert.equal(at("--model"), "gemini-4-hydrogen");
  assert.equal(at("--effort"), "high");
  assert.equal(at("--output-format"), "stream-json");
  assert.ok(argv.includes("--disable-slash-commands"));
  assert.ok(!argv.includes("--mode"), "plan mode is not used");
  assert.ok(!argv.includes("--dangerously-skip-permissions"));
  const settings = JSON.parse(at("--settings"));
  assert.deepEqual(settings.trustedWorkspaces, [cwd]);
  assert.equal(settings.agentMode, "");
  assert.deepEqual(settings.permissions.deny, [...AGY_DENY_RULES]);
  for (const rule of ["command(*)", "write_file(*)"]) assert.ok(AGY_DENY_RULES.includes(rule), rule);
  assert.equal(agySeatSettings(cwd), at("--settings"));
});

// The shapes below are agy 1.5.13's own output (probed 2026-11-20), trimmed.
const AGY_OK_JSON = ev({ conversation_id: "962281e3", status: "SUCCESS", response: "[MINOR] plan.md:5 says hello\n", duration_seconds: 3.2, num_turns: 1, usage: { input_tokens: 10087, output_tokens: 35, thinking_tokens: 33, cache_read_tokens: 0, total_tokens: 10122 } });

t("agy --output-format json: SUCCESS gives the response and the tokens", () => {
  const r = parseAgyOutput(AGY_OK_JSON);
  assert.equal(r.finalText, "[MINOR] plan.md:5 says hello\n");
  assert.equal(r.status, "SUCCESS");
  assert.equal(r.errorMessage, null);
  assert.equal(r.usage.total_tokens, 10122);
  assert.equal(r.conversationId, "962281e3");
});

const step = (o) => ev({ event: "step_update", step_update: { conversation_id: "c1", ...o } });
const AGY_STREAM = [
  ev({ event: "init", conversation_id: "c1", init: { model: "gemini-4-hydrogen", permission_mode: "request-review" } }),
  step({ step_index: 0, state: "DONE", step_type: "user_input" }),
  step({ step_index: 2, state: "ACTIVE", step_type: "tool", tool_name: "read_file", tool_info: { name: "read_file", parameters: { Path: "plan.md" } } }),
  step({ step_index: 2, state: "DONE", step_type: "tool", tool_name: "read_file", tool_info: { name: "read_file", parameters: { Path: "plan.md" }, output: "Error: 429 Too Many Requests in a file it read" } }),
  step({ step_index: 4, state: "ACTIVE", step_type: "agent_response", text_delta: "[CRITICAL] plan.md:5 " }),
  step({ step_index: 4, state: "ACTIVE", step_type: "agent_response", text_delta: "greet.shout does not exist" }),
];

t("agy stream-json: the result event gives the answer", () => {
  const done = [...AGY_STREAM, ev({ event: "result", result: { conversation_id: "c1", status: "SUCCESS", response: "[CRITICAL] plan.md:5 greet.shout does not exist", usage: { total_tokens: 900 } } })].join("\n");
  const r = parseAgyOutput(done);
  assert.equal(r.finalText, "[CRITICAL] plan.md:5 greet.shout does not exist");
  assert.equal(r.usage.total_tokens, 900);
  assert.equal(agyUsageLimitOf(r.errorMessage), null, "a 429 inside a file it read is not a usage limit");
});

t("agy stream-json killed mid-answer: the trace so far, no file contents, no final text", () => {
  const r = parseAgyOutput(`${AGY_STREAM.join("\n")}\n{"event":"step_upd`);
  assert.equal(r.finalText, null);
  assert.equal(r.status, null);
  assert.equal(r.conversationId, "c1");
  assert.equal(r.partialText, '> read_file {"Path":"plan.md"}\n\n[CRITICAL] plan.md:5 greet.shout does not exist');
  assert.ok(!r.partialText.includes("429"));
});

t("agy error and empty answers are failures with a reason", () => {
  const bad = parseAgyOutput(ev({ conversation_id: "", status: "ERROR", response: "", error: "invalid model selection (--model \"gemini-9\" --effort \"\"): model gemini-9 is not recognized", usage: { total_tokens: 0 }, finished_reason: "error" }));
  assert.equal(bad.finalText, null);
  assert.match(bad.errorMessage, /not recognized/);
  const empty = parseAgyOutput(ev({ conversation_id: "d", status: "SUCCESS", response: "", denied_actions: [{ action: "command", display_name: "Bash" }] }));
  assert.equal(empty.finalText, null);
  assert.equal(empty.errorMessage, "empty response (denied: Bash)");
  const blank = parseAgyOutput(ev({ status: "SUCCESS", response: "  \n" }));
  assert.equal(blank.finalText, null);
  assert.equal(blank.errorMessage, "empty response");
  const odd = parseAgyOutput(ev({ status: "CANCELLED", response: "half an answer" }));
  assert.equal(odd.finalText, null);
  assert.equal(odd.errorMessage, "agy status CANCELLED");
  assert.equal(parseAgyOutput("").finalText, null);
});

t("agy usage limits are caught from its error field", () => {
  // The first two are messages in the agy 1.5.13 binary.
  assert.ok(agyUsageLimitOf("You have exhausted your quota on this model."));
  assert.equal(agyUsageLimitOf("model request failed\nmodel gemini-4-hydrogen-high is out of quota until 18:00"), "model gemini-4-hydrogen-high is out of quota until 18:00");
  assert.ok(agyUsageLimitOf("RESOURCE_EXHAUSTED"));
  assert.ok(agyUsageLimitOf("HTTP 429 Too Many Requests"));
  assert.equal(agyUsageLimitOf("invalid model selection"), null);
  assert.equal(agyUsageLimitOf(null), null);
});

t("agy models: a bare id is listed when its effort-suffixed id is", () => {
  const list = "Fetching available models...\ngemini-4-hydrogen-high\tGemini 4 Hydrogen (High)\ngemini-4-hydrogen-low\tGemini 4 Hydrogen (Low)\n";
  assert.ok(agyModelListed(list, "gemini-4-hydrogen", "high"));
  assert.ok(!agyModelListed(list, "gemini-4-hydrogen", "medium"));
  assert.ok(!agyModelListed(list, "gemini-4-neon", "high"));
});

t("an agy seat never carries FOREMAN_AGY_SID; other seats keep the environment as is", () => {
  const env = { PATH: "x", FOREMAN_AGY_SID: "s1" };
  assert.deepEqual(seatEnv({ doorSlug: "agy" }, env), { PATH: "x" });
  assert.equal(env.FOREMAN_AGY_SID, "s1", "the dispatcher's own environment is not changed");
  assert.equal(seatEnv({ doorSlug: "codex" }, env), env);
});

t("the agy roster rows resolve, validate, and keep the OpenRouter Gemini fallback", () => {
  const roster = JSON.parse(fs.readFileSync(new URL("./plancheck-roster.json", import.meta.url), "utf8"));
  assert.equal(validateRoster(roster), null);
  const ids = ["gemini-hydrogen-agy", "gemini-neon-agy", "gemini-argon-agy"];
  const r = resolveSeats({ seats: ids.map((id) => ({ id, door: "agy CLI" })) }, roster);
  assert.ok(r.ok, r.reason);
  assert.deepEqual(r.seats.map((s) => [s.doorSlug, s.model, s.vendor, s.log]), [
    ["agy", "gemini-4-hydrogen", "Google", "read-agy-gemini-4-hydrogen.log"],
    ["agy", "gemini-4-neon", "Google", "read-agy-gemini-4-neon.log"],
    ["agy", "gemini-4-argon", "Google", "read-agy-gemini-4-argon.log"],
  ]);
  for (const id of ids) assert.equal(roster.models.find((m) => m.id === id).cost, "subscription");
  assert.equal(roster.models.find((m) => m.id === "gemini-hydrogen").door, "OpenRouter");
});

console.log(`PASS ${n}/${n}`);

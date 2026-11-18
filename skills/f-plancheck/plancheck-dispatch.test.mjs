#!/usr/bin/env node
// Tests for the pure parts of plancheck-dispatch.mjs that read pi (the
// OpenRouter door): the catalog row, the output cap and the JSON event stream.
//   node skills/f-plancheck/plancheck-dispatch.test.mjs
import assert from "node:assert/strict";
import fs from "node:fs";
import {
  buildArgvForSeat,
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

console.log(`PASS ${n}/${n}`);

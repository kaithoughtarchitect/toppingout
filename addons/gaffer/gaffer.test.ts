// Automated verification for Topping Out Gaffer (zero network required, zero private fixtures).
import test from "node:test";
import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  OrcaClient,
  OrcaRunner,
  detectBlockedLeadingPrefix,
  mergeOrcaState,
  resolveSessionStrict,
  sanitizeTerminalMessage,
} from "./orca.js";
import {
  CONFIRM_MAX_TTL_MS,
  CONFIRM_TTL_MS,
  LlmClient,
  VOICE_SEND_PREFIX,
  VoiceBrain,
  computeUnheardTail,
  isStandaloneGatedAct,
  parseConfirmationIntent,
  parseRepeatIntent,
  parseResumeIntent,
  parseStandbyIntent,
} from "./brain.js";
import {
  buildOwnerQueue,
  classifyTopology,
  discoverBoards,
  parseJStatus,
  readActiveJobs,
} from "./toppingout.js";
import {
  classifyFailure,
  forSpeech,
  isHallucinatedSilence,
  normalizeTranscript,
  spokenFailureMessage,
} from "./speech.js";
import { SessionWatcher, coalesceHeldAlerts, detectTransition } from "./watcher.js";
import {
  GAFFER_COOKIE_NAME,
  GAFFER_CSRF_HEADER,
  GAFFER_TOKEN_HEADER,
  createVoiceServer,
  isAllowedHost,
  isAllowedOrigin,
} from "./server.js";
import { gafferEnv, isNodeTestEnv, loadEnv } from "./env.js";

const HERE = dirname(fileURLToPath(import.meta.url));

function makeMockOrca(opts?: {
  onSend?: (handle: string, textArg: string, args: string[]) => void;
  sendOverride?: (args: string[]) => Promise<unknown> | unknown;
  terminalShowOverride?: () => unknown;
  extraAgents?: Array<Record<string, unknown>>;
  extraTerminals?: Array<Record<string, unknown>>;
}): OrcaRunner {
  return {
    async runJson(args: string[]) {
      if (args[0] === "agent" && args[1] === "list") {
        return {
          ok: true,
          result: {
            agents: [
              {
                orcaSessionId: "sess-head-1",
                kind: "terminal",
                agent: "claude",
                state: "done",
                repo: "my-app",
                workspace: "main",
                paneKey: "t1:l1",
                title: "Head 1: api groundwork",
                updatedAt: 5000,
              },
              ...(opts?.extraAgents ?? []),
            ],
          },
        };
      }
      if (args[0] === "terminal" && args[1] === "list") {
        return {
          ok: true,
          result: {
            terminals: [
              {
                handle: "term_head1",
                incarnationId: "inc-1",
                tabId: "t1",
                leafId: "l1",
                connected: true,
                writable: true,
                orphaned: false,
                agentIdentity: "claude",
              },
              ...(opts?.extraTerminals ?? []),
            ],
          },
        };
      }
      if (args[0] === "terminal" && args[1] === "show") {
        if (opts?.terminalShowOverride) return opts.terminalShowOverride();
        return {
          ok: true,
          result: {
            terminal: {
              handle: "term_head1",
              incarnationId: "inc-1",
              connected: true,
              writable: true,
              orphaned: false,
              agentIdentity: "claude",
            },
          },
        };
      }
      if (args[0] === "terminal" && args[1] === "send") {
        const handleIdx = args.indexOf("--terminal");
        const textArg = args.find((a) => a.startsWith("--text=")) || "";
        opts?.onSend?.(args[handleIdx + 1], textArg, args);
        if (opts?.sendOverride) return await opts.sendOverride(args);
        // Real Orca 1.4 `orca terminal send --json` shape: result.send.{accepted, refusedReason, prompt}
        return {
          ok: true,
          result: {
            send: {
              requestId: "req-mock-1",
              accepted: true,
              refusedReason: null,
              prompt: {
                stages: ["input_accepted", "turn_started"],
                observation: "turn_started",
              },
            },
          },
        };
      }
      return { ok: true, result: {} };
    },
  };
}

test("1. mergeOrcaState joins agent records with live terminals and records incarnationId", () => {
  const merged = mergeOrcaState(
    [
      {
        orcaSessionId: "sess-head-1",
        kind: "terminal",
        agent: "claude",
        state: "done",
        repo: "my-app",
        workspace: "main",
        paneKey: "tab-1:leaf-1",
        title: "Head 1: api groundwork",
        updatedAt: 2000,
      },
    ],
    [
      {
        handle: "term_abc",
        incarnationId: "inc-99",
        tabId: "tab-1",
        leafId: "leaf-1",
        connected: true,
        writable: true,
        orphaned: false,
        agentIdentity: "claude",
        branch: "refs/heads/main",
        lastOutputAt: 2500,
        preview: "owed: check tests",
      },
    ]
  );

  assert.equal(merged.length, 1);
  assert.equal(merged[0].id, "sess-head-1");
  assert.equal(merged[0].terminalHandle, "term_abc");
  assert.equal(merged[0].incarnationId, "inc-99");
  assert.equal(merged[0].writable, true);
});

test("2. resolveSessionStrict distinguishes Head 1 vs Head 10, maps number words, prefers writable sessions, and refuses unknown active", () => {
  const sessions = mergeOrcaState(
    [
      { orcaSessionId: "s1-dead", kind: "terminal", agent: "claude", state: "done", repo: "my-app", paneKey: "t0:l0", title: "Head 1: api", updatedAt: 9000 },
      { orcaSessionId: "s1-live", kind: "terminal", agent: "claude", state: "done", repo: "my-app", paneKey: "t1:l1", title: "Head 1: api", updatedAt: 3000 },
      { orcaSessionId: "s10", kind: "terminal", agent: "claude", state: "done", repo: "my-app", paneKey: "t2:l2", title: "Head 10: billing", updatedAt: 4000 },
      { orcaSessionId: "s3a", kind: "terminal", agent: "claude", state: "done", repo: "my-app", paneKey: "t3:l3", title: "Design lead", updatedAt: 2000 },
      { orcaSessionId: "s3b", kind: "terminal", agent: "claude", state: "done", repo: "my-app", paneKey: "t4:l4", title: "Design builder", updatedAt: 2500 },
    ],
    [
      { handle: "term_1", tabId: "t1", leafId: "l1", connected: true, writable: true, agentIdentity: "claude" },
      { handle: "term_10", tabId: "t2", leafId: "l2", connected: true, writable: true, agentIdentity: "claude" },
      { handle: "term_3a", tabId: "t3", leafId: "l3", connected: true, writable: true, agentIdentity: "claude" },
      { handle: "term_3b", tabId: "t4", leafId: "l4", connected: true, writable: true, agentIdentity: "claude" },
    ]
  );

  // "head one" maps number word -> "head 1" and prefers live writable s1-live over dead s1-dead
  const r1 = resolveSessionStrict(sessions, "head one", null, { preferWritable: true });
  assert.equal(r1.status, "match");
  if (r1.status === "match") assert.equal(r1.session.id, "s1-live");

  // "head ten" matches ONLY Head 10
  const r10 = resolveSessionStrict(sessions, "head ten", null, { preferWritable: true });
  assert.equal(r10.status, "match");
  if (r10.status === "match") assert.equal(r10.session.id, "s10");

  // "design" matches both Design lead and Design builder -> ambiguous!
  const amb = resolveSessionStrict(sessions, "design", null, { preferWritable: true });
  assert.equal(amb.status, "ambiguous");

  // "active" with no activeSessionId -> not_found (never silently picks newest session!)
  const noActive = resolveSessionStrict(sessions, "active", null, { allowFallbackLatest: false });
  assert.equal(noActive.status, "not_found");
});

test("3. sanitizeTerminalMessage strips newlines, ANSI, C1 controls, and bidi chars; blocks leading /, !, #", async () => {
  assert.equal(
    sanitizeTerminalMessage("\x1b[31mrun tests\nrm -rf /\r\x07\x1b[0m"),
    "run tests rm -rf /"
  );
  // Strips C1 controls (\x80-\x9f) and Unicode bidi overrides/isolates
  assert.equal(
    sanitizeTerminalMessage("hello\u0085\u009bworld \u202eevil\u202c \u2066iso\u2069 \u200fok"),
    "helloworld evil iso ok"
  );
  assert.equal(detectBlockedLeadingPrefix("/clear"), "slash (/)");
  assert.equal(detectBlockedLeadingPrefix("!rm -rf /"), "exclamation mark (!)");
  assert.equal(detectBlockedLeadingPrefix("#comment"), "hash (#)");
  assert.equal(detectBlockedLeadingPrefix("run tests"), null);

  let sendCalls = 0;
  let capturedTextArg = "";
  const orca = new OrcaClient(
    makeMockOrca({
      onSend: (_h, textArg) => {
        sendCalls += 1;
        capturedTextArg = textArg;
      },
    })
  );

  // Leading /, !, # refused at sendToTerminal without invoking Orca CLI
  const slashRes = await orca.sendToTerminal("term_head1", "/exit");
  assert.equal(slashRes.ok, false);
  assert.ok(slashRes.detail.includes("slash (/)"));
  const bangRes = await orca.sendToTerminal("term_head1", "!whoami");
  assert.equal(bangRes.ok, false);
  assert.ok(bangRes.detail.includes("exclamation mark (!)"));
  assert.equal(sendCalls, 0);

  // Normal text passes --text= safely
  const okRes = await orca.sendToTerminal("term_head1", "-v\nsecond line");
  assert.equal(okRes.ok, true);
  assert.equal(okRes.turnStarted, true);
  assert.equal(capturedTextArg, "--text=-v second line");
});

test("4. sendToTerminal parses result.send, handles refused/exit-1 without throwing, reports turn not started, and retries unclear failures only with --retry-request", async () => {
  // Case A: Refused send (result.send.accepted=false, refusedReason set)
  const refusedOrca = new OrcaClient(
    makeMockOrca({
      sendOverride: () => ({
        ok: true,
        result: {
          send: {
            accepted: false,
            refusedReason: "terminal busy with interactive prompt",
            prompt: { stages: [], observation: "refused" },
          },
        },
      }),
    })
  );
  const rRefused = await refusedOrca.sendToTerminal("term_head1", "run tests");
  assert.equal(rRefused.ok, false);
  assert.equal(rRefused.accepted, false);
  assert.ok(rRefused.detail.includes("terminal busy"));

  // Case B: CLI throws / exits 1 without retry ID -> returns ok:false cleanly, NEVER resends a plain send!
  let plainAttempts = 0;
  const throwOrca = new OrcaClient(
    makeMockOrca({
      sendOverride: () => {
        plainAttempts += 1;
        throw new Error("Command failed: exit code 1");
      },
    })
  );
  const rThrow = await throwOrca.sendToTerminal("term_head1", "run tests");
  assert.equal(rThrow.ok, false);
  assert.equal(plainAttempts, 1, "Must NEVER issue a second plain send without a retry request ID");

  // Case C: Accepted but turn_started missing -> reports "Accepted, turn not started."
  const queuedOrca = new OrcaClient(
    makeMockOrca({
      sendOverride: () => ({
        ok: true,
        result: {
          send: {
            requestId: "req-q1",
            accepted: true,
            refusedReason: null,
            prompt: { stages: ["input_accepted"], observation: "queued" },
          },
        },
      }),
    })
  );
  const rQueued = await queuedOrca.sendToTerminal("term_head1", "run tests");
  assert.equal(rQueued.ok, true);
  assert.equal(rQueued.accepted, true);
  assert.equal(rQueued.turnStarted, false);
  assert.equal(rQueued.detail, "Accepted, turn not started.");

  // Case D: Unclear/timed-out failure WITH retryRequestId -> retries ONCE using --retry-request <id>
  const seenArgs: string[][] = [];
  const retryOrca = new OrcaClient(
    makeMockOrca({
      sendOverride: (args) => {
        seenArgs.push(args);
        if (seenArgs.length === 1) {
          throw new Error("Transport timeout; reissue with --retry-request req-abc-42");
        }
        return {
          ok: true,
          result: {
            send: {
              requestId: "req-abc-42",
              accepted: true,
              refusedReason: null,
              prompt: { stages: ["input_accepted", "turn_started"], observation: "turn_started" },
            },
          },
        };
      },
    })
  );
  const rRetry = await retryOrca.sendToTerminal("term_head1", "run tests");
  assert.equal(rRetry.ok, true);
  assert.equal(rRetry.turnStarted, true);
  assert.equal(seenArgs.length, 2);
  const retryIdx = seenArgs[1].indexOf("--retry-request");
  assert.ok(retryIdx !== -1 && seenArgs[1][retryIdx + 1] === "req-abc-42");
});

test("5. env.ts skips loading under NODE_TEST and never overrides already-set empty variables", () => {
  assert.equal(isNodeTestEnv(), true, "Must detect running under node --test");

  const dir = mkdtempSync(join(tmpdir(), "orca-env-test-"));
  const envFile = join(dir, ".env");
  writeFileSync(envFile, 'OPENROUTER_API_KEY="sk-from-file"\nEXTRA_TEST_KEY="loaded"\n', "utf8");

  try {
    // Guard 1: Under NODE_TEST, loadEnv does nothing at all
    const underTestEnv: NodeJS.ProcessEnv = {};
    loadEnv({ env: underTestEnv, candidates: [envFile], force: true, respectTestGuard: true });
    assert.equal(underTestEnv.OPENROUTER_API_KEY, undefined);
    assert.equal(underTestEnv.EXTRA_TEST_KEY, undefined);

    // Guard 2: Even outside test guard, an already-set empty string "" (stripped key) is NEVER overridden!
    const strippedEnv: NodeJS.ProcessEnv = { OPENROUTER_API_KEY: "" };
    loadEnv({ env: strippedEnv, candidates: [envFile], force: true, respectTestGuard: false });
    assert.equal(strippedEnv.OPENROUTER_API_KEY, "", "Stripped empty key must not be overwritten");
    assert.equal(strippedEnv.EXTRA_TEST_KEY, "loaded", "Unset key loads normally outside tests");
    // Guard 3: gafferEnv() prefers GAFFER_* and falls back cleanly to legacy ORCA_VOICE_*
    assert.equal(gafferEnv("PORT", { GAFFER_PORT: "5000", ORCA_VOICE_PORT: "4111" }), "5000");
    assert.equal(gafferEnv("PORT", { ORCA_VOICE_PORT: "4111" }), "4111");
    assert.equal(gafferEnv("ALL_STOPS", { GAFFER_ALL_STOPS: "0", ORCA_VOICE_ALL_STOPS: "1" }), "0");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("6. speech normalizes wake variants and filters silence, backchannels, prompt echoes, and refusals", () => {
  assert.equal(normalizeTranscript("Hey AUCA, what is the status?"), "Hey Orca, what is the status?");
  assert.equal(normalizeTranscript("Orka check head 1"), "Orca check head 1");
  assert.equal(normalizeTranscript("Walker, can you hear me?"), "Orca, can you hear me?");
  assert.equal(normalizeTranscript("Radial, are you there?"), "Radio, are you there?");
  assert.equal(normalizeTranscript("gaffa, what needs my word?"), "Gaffer, what needs my word?");
  assert.equal(normalizeTranscript("oca"), "Orca");

  for (const noise of [
    "Thank you.",
    "Topping Out",
    "[SILENCE]",
    "mm-hmm",
    "hmm.",
    "okay",
    "uh",
    "Orca, Topping Out, Foreman, Claude, Antigravity, Codex, Pi.",
    "I'm sorry, but I can't transcribe audio.",
    "I'm sorry, but I can\u2019t understand the audio from the description provided.",
    "Hello, this is the Orca project. We are discussing the Topping Out ceremony. The foreman, Claude, mentioned antigravity and Codex.",
  ]) {
    assert.equal(isHallucinatedSilence(noise), true, `Expected noise filter to drop: ${noise}`);
  }
  assert.equal(isHallucinatedSilence("Yes"), false);
});

test("7. deterministic confirmation gate: prefixes [voice], refuses gated acts & leading /, accepts expanded yes, re-prompts on unclear without LLM", async () => {
  const sentCalls: Array<{ handle: string; textArg: string }> = [];
  let turnStartedNext = true;
  const orca = new OrcaClient(
    makeMockOrca({
      onSend: (handle, textArg) => sentCalls.push({ handle, textArg }),
      sendOverride: () => ({
        ok: true,
        result: {
          send: {
            requestId: "req-1",
            accepted: true,
            refusedReason: null,
            prompt: {
              stages: turnStartedNext ? ["input_accepted", "turn_started"] : ["input_accepted"],
              observation: turnStartedNext ? "turn_started" : "queued",
            },
          },
        },
      }),
    })
  );

  // Expanded yes/cancel/gated-act checks
  for (const y of [
    "Yes, send it.",
    "yep go ahead",
    "yes absolutely",
    "yes yes",
    "go for it",
    "sure",
    "Radio, yes",
    "Gaffer, yes",
    "Hey Gaffer, send it",
    "So, yes, did you get that?",
    "Well, yeah, send it please",
  ]) {
    assert.equal(parseConfirmationIntent(y), "yes", `Expected yes for: ${y}`);
  }
  assert.equal(parseConfirmationIntent("Radio, cancel"), "no");
  assert.equal(parseConfirmationIntent("Gaffer, cancel"), "no");
  assert.equal(parseRepeatIntent("Gaffer, repeat that"), true);
  assert.equal(parseStandbyIntent("Gaffer, stand by"), true);
  assert.equal(parseConfirmationIntent("Yes, wait, change it instead"), "other");
  assert.equal(parseConfirmationIntent("So, yes, but don't send yet"), "other");

  assert.equal(isStandaloneGatedAct("merge"), true);
  assert.equal(isStandaloneGatedAct("push"), true);
  assert.equal(isStandaloneGatedAct("open the PR"), true);
  assert.equal(isStandaloneGatedAct("greploop"), true);
  assert.equal(isStandaloneGatedAct("run tests and report back"), false);

  let nextStageMessage = "/clear";
  let llmCalls = 0;
  const mockLlm: LlmClient = {
    async chat(messages, tools) {
      llmCalls += 1;
      const toolNames = ((tools || []) as Array<{ function?: { name?: string } }>).map(
        (t) => t.function?.name
      );
      assert.ok(!toolNames.includes("confirm_send"), "LLM must not have a confirm_send tool");

      const lastMsg = messages[messages.length - 1];
      if (lastMsg.role === "tool") {
        const parsed = JSON.parse(lastMsg.content || "{}") as { error?: string };
        return { content: parsed.error || "Refused." };
      }

      return {
        content: null,
        tool_calls: [
          {
            id: `tc_${llmCalls}`,
            type: "function",
            function: {
              name: "stage_reply",
              arguments: JSON.stringify({ session_query: "Head 1", message: nextStageMessage }),
            },
          },
        ],
      };
    },
  };

  const brain = new VoiceBrain(orca, mockLlm);

  // 1. Leading "/" refused and spelled out ("slash (/)")
  const slashTurn = await brain.handleUserUtterance("Tell Head 1 /clear", "always");
  assert.equal(brain.hasPendingConfirmation(), false);
  assert.ok(slashTurn.replyText.includes("slash (/)"));

  // 2. Standalone gated act ("merge") refused
  nextStageMessage = "merge";
  const gatedTurn = await brain.handleUserUtterance("Tell Head 1 to merge", "always");
  assert.equal(brain.hasPendingConfirmation(), false);
  assert.ok(gatedTurn.replyText.toLowerCase().includes("gated"));

  // 3. Normal safe message stages cleanly; unclear answer re-prompts "Say yes or cancel" WITHOUT calling LLM or cancelling!
  nextStageMessage = "run tests\nnow";
  const t1 = await brain.handleUserUtterance("Tell Head 1 to run tests", "always");
  assert.equal(sentCalls.length, 0);
  assert.equal(brain.hasPendingConfirmation(), true);
  assert.ok(t1.replyText.includes('"run tests now"'));

  const llmBeforeUnclear = llmCalls;
  const tUnclear = await brain.handleUserUtterance("uh what was that again", "always");
  assert.equal(llmCalls, llmBeforeUnclear, "Unclear answer must NOT call LLM or re-stage");
  assert.equal(sentCalls.length, 0);
  assert.equal(brain.hasPendingConfirmation(), true, "Staged draft stays alive on unclear answer");
  assert.ok(tUnclear.replyText.includes("Say yes or cancel"));

  // 4. Confirming right after unclear re-prompt sends with "[voice] " prefix and reports turn not started when queued!
  turnStartedNext = false;
  const tYes = await brain.handleUserUtterance("go for it", "wake");
  assert.equal(llmCalls, llmBeforeUnclear, "Yes must execute purely in code without LLM");
  assert.equal(sentCalls.length, 1);
  assert.deepEqual(sentCalls[0], {
    handle: "term_head1",
    textArg: `--text=${VOICE_SEND_PREFIX}run tests now`,
  });
  assert.ok(tYes.replyText.includes("Accepted, turn not started."));
  assert.equal(tYes.sentDelivery?.ok, true);

  // 5. Stage again then explicit cancel -> cancels deterministically with ZERO LLM call
  await brain.handleUserUtterance("Tell Head 1 to run tests", "always");
  const llmBeforeCancel = llmCalls;
  const tCancel = await brain.handleUserUtterance("Cancel", "wake");
  assert.equal(llmCalls, llmBeforeCancel);
  assert.equal(brain.hasPendingConfirmation(), false);
  assert.ok(tCancel.replyText.includes("Cancelled"));
});

test("8. safety gate: 90s expiry, bare-shell refusal, standby command, and 2+ word follow-up rule without extending on noise", async () => {
  let fakeNow = 100_000;
  let sentCount = 0;
  let showResponse: unknown = {
    ok: true,
    result: {
      terminal: {
        handle: "term_head1",
        incarnationId: "inc-1",
        connected: true,
        writable: true,
        orphaned: false,
        agentIdentity: "claude",
      },
    },
  };

  const orca = new OrcaClient(
    makeMockOrca({
      onSend: () => {
        sentCount += 1;
      },
      terminalShowOverride: () => showResponse,
    })
  );

  let llmCalls = 0;
  const stageLlm: LlmClient = {
    async chat(messages) {
      llmCalls += 1;
      const u = messages[messages.length - 1]?.content || "";
      if (u.toLowerCase().includes("stage")) {
        return {
          content: null,
          tool_calls: [
            {
              id: "tc",
              type: "function",
              function: {
                name: "stage_reply",
                arguments: JSON.stringify({ session_query: "Head 1", message: "run unit tests" }),
              },
            },
          ],
        };
      }
      return { content: "All quiet." };
    },
  };

  const brain = new VoiceBrain(orca, stageLlm, () => fakeNow);

  // Case A: 90s expiry
  await brain.handleUserUtterance("Stage tests for Head 1", "always");
  fakeNow += CONFIRM_TTL_MS + 1000;
  const expired = await brain.handleUserUtterance("Yes", "always");
  assert.equal(sentCount, 0);
  assert.ok(expired.replyText.toLowerCase().includes("expired"));

  // Case B: 60s follow-up window requires 2+ words and does NOT extend window on 1-word noise
  await brain.handleUserUtterance("Radio, check status", "wake");
  assert.equal(brain.getState().followUpActive, true);
  fakeNow += 50_000; // 10s left in 60s window
  const oneWord = await brain.handleUserUtterance("right", "wake");
  assert.equal(oneWord.ignored, true);
  assert.equal(oneWord.reason, "follow-up requires 2+ words");
  fakeNow += 15_000; // now 65s since last valid turn -> window must have expired (NOT extended by "right"!)
  assert.equal(brain.getState().followUpActive, false);

  // Case C: Standby closes follow-up window immediately with zero LLM calls
  assert.equal(parseStandbyIntent("Stand by. Can you copy that trailing room chatter"), true);
  assert.equal(parseStandbyIntent("Over in Head 1 check tests"), false);
  await brain.handleUserUtterance("Radio, check status", "wake");
  const llmBeforeStandby = llmCalls;
  const slept = await brain.handleUserUtterance("Stand by", "wake");
  assert.equal(slept.followUpActive, false);
  assert.equal(llmCalls, llmBeforeStandby);

  // Case D: Agent exited leaving bare shell (agentIdentity: null) right before "Yes" -> REFUSED!
  await brain.handleUserUtterance("Stage tests for Head 1", "always");
  showResponse = {
    ok: true,
    result: {
      terminal: {
        handle: "term_head1",
        incarnationId: "inc-1",
        connected: true,
        writable: true,
        orphaned: false,
        agentIdentity: null,
      },
    },
  };
  const refused = await brain.handleUserUtterance("Yes", "always");
  assert.equal(sentCount, 0, "Must never send into a bare shell after agent exits");
  assert.ok(refused.replyText.includes("Refused to send"));
  assert.equal(refused.sentDelivery?.ok, false);
});

test("9. watcher: zero idle Orca polling, real terminal.tail mock, unknown state ignored, retries on error, holds alerts while staged", async () => {
  const sessionBase = {
    id: "s1",
    orcaSessionId: "s1",
    terminalHandle: "term_1",
    incarnationId: "inc-1",
    title: "Head 1",
    repo: "my-app",
    workspace: "main",
    branch: "main",
    agent: "claude",
    kind: "terminal",
    state: "unknown",
    writable: true,
    connected: true,
    hostId: "local",
    updatedAt: 15_000,
    preview: "",
  };

  // State "unknown" is NEVER treated as a stop
  const unknownFlip = detectTransition(
    { state: "working", updatedAt: 12_000, previewHash: "", lastAlertedAt: 0, lastAlertedTurnKey: "" },
    sessionBase,
    15_000,
    30_000
  );
  assert.equal(unknownFlip.triggered, false);

  // Zero Orca polling (listSessions not even called!) when nobody is listening
  let orcaListCalls = 0;
  let stateNow = "working";
  let updatedAtNow = 1000;
  let tuiReply = "First answer from assistant.";
  let failAlertOnce = true;
  let listenerOn = false;
  const staticFooter = "\n" + "=".repeat(60) + "\nType your message... [Tab] [Ctrl+C] status: ready ".repeat(6);

  const tuiOrca = new OrcaClient({
    async runJson(args) {
      if (args[0] === "agent" && args[1] === "list") {
        orcaListCalls += 1;
        return {
          ok: true,
          result: {
            agents: [
              {
                orcaSessionId: "s-tui",
                kind: "terminal",
                agent: "antigravity",
                state: stateNow,
                paneKey: "t9:l9",
                title: "app antigravity",
                updatedAt: updatedAtNow,
              },
            ],
          },
        };
      }
      if (args[0] === "terminal" && args[1] === "list") {
        return {
          ok: true,
          result: {
            terminals: [
              {
                handle: "term_tui",
                incarnationId: "inc-9",
                tabId: "t9",
                leafId: "l9",
                connected: true,
                writable: true,
                agentIdentity: "antigravity",
              },
            ],
          },
        };
      }
      if (args[0] === "terminal" && args[1] === "read") {
        // REAL Orca `terminal read --json` shape: result.terminal.tail (string[])!
        return {
          ok: true,
          result: {
            terminal: {
              tail: (tuiReply + staticFooter).split("\n"),
            },
          },
        };
      }
      return { ok: true, result: {} };
    },
  });

  // Confirm readSession actually reads non-empty screenTail from result.terminal.tail!
  const probeSessions = await tuiOrca.listSessions();
  const probeDetails = await tuiOrca.readSession(probeSessions[0], 6);
  assert.ok(probeDetails.screenTail.includes("First answer from assistant."));
  orcaListCalls = 0;

  let evalCalls = 0;
  const tuiBrain = new VoiceBrain(tuiOrca, {
    async chat(messages, tools) {
      if (tools && tools.length > 0) {
        return {
          content: null,
          tool_calls: [
            {
              id: "tc_stage",
              type: "function",
              function: {
                name: "stage_reply",
                arguments: JSON.stringify({ session_query: "app antigravity", message: "run checks" }),
              },
            },
          ],
        };
      }
      evalCalls += 1;
      if (failAlertOnce) {
        failAlertOnce = false;
        throw new Error("Transient LLM timeout");
      }
      return { content: `{"shouldAlert":true,"needsDecision":true,"spokenAlert":"${tuiReply}"}` };
    },
  });

  const alertsFired: string[] = [];
  const watcher = new SessionWatcher(tuiOrca, tuiBrain, {
    hasListener: () => listenerOn,
    onAlert: (a) => {
      alertsFired.push(a.spokenText);
    },
  });

  // 1. Nobody listening -> ZERO Orca polling calls!
  await watcher.tick();
  assert.equal(orcaListCalls, 0, "Watcher must not poll Orca when nobody is listening");

  // 2. Listener connects -> baseline working, then stop #1 hits transient LLM error -> next tick RETRIES!
  listenerOn = true;
  await watcher.tick(); // baseline: working
  stateNow = "done";
  updatedAtNow = 2000;
  await watcher.tick(); // transient LLM error -> must NOT lose the stop!
  assert.equal(alertsFired.length, 0);
  await watcher.tick(); // retry succeeds!
  assert.equal(alertsFired.length, 1);
  assert.equal(alertsFired[0], "First answer from assistant.");

  // 3. Stage a reply -> stop #2 is HELD (does not cancel pendingConfirmation or interrupt!), then flushes after cancel!
  await tuiBrain.handleUserUtterance("Stage checks for app antigravity", "always");
  assert.equal(tuiBrain.hasPendingConfirmation(), true);

  stateNow = "working";
  updatedAtNow = 3000;
  await watcher.tick();
  tuiReply = "Second answer from assistant.";
  stateNow = "done";
  updatedAtNow = 4000;
  await watcher.tick(); // stop #2 held while staged!
  assert.equal(tuiBrain.hasPendingConfirmation(), true, "Incoming alert must NOT cancel staged reply");
  assert.equal(alertsFired.length, 1, "Alert must be held until confirmation clears");
  assert.equal(watcher.getHeldAlertCount(), 1);

  await tuiBrain.handleUserUtterance("Cancel", "wake");
  assert.equal(tuiBrain.hasPendingConfirmation(), false);
  await watcher.flushHeldAlerts();
  assert.equal(alertsFired.length, 2, "Held alert must play once confirmation clears");
  assert.equal(alertsFired[1], "Second answer from assistant.");
  assert.ok(evalCalls >= 3);
});

test("10. HTTP server: CSRF, Host/Origin, header + HttpOnly cookie auth (rejecting ?token=), audio-unlocked listener count, and cancel staged reply on TTS error", async () => {
  const orca = new OrcaClient(makeMockOrca());
  let stageMode = false;
  const llm: LlmClient = {
    async chat() {
      if (stageMode) {
        return {
          content: null,
          tool_calls: [
            {
              id: "tc_1",
              type: "function",
              function: {
                name: "stage_reply",
                arguments: JSON.stringify({ session_query: "Head 1", message: "run unit tests" }),
              },
            },
          ],
        };
      }
      return { content: "Nothing waiting right now." };
    },
  };
  let failTts = false;
  const brain = new VoiceBrain(orca, llm);
  const app = createVoiceServer({
    orca,
    brain,
    startWatcher: false,
    auth: {
      token: "secret-test-token",
      allowedTailscaleUsers: ["owner@example.com"],
    },
    synthesize: async () => {
      if (failTts) throw new Error("Simulated TTS outage");
      return Buffer.from("FAKE_MP3");
    },
  });

  await new Promise<void>((res) => app.server.listen(0, "127.0.0.1", () => res()));
  const addr = app.server.address();
  assert.ok(addr && typeof addr === "object");
  const base = `http://127.0.0.1:${addr.port}`;
  const hdrs = { "Content-Type": "application/json", [GAFFER_CSRF_HEADER]: "1" };

  try {
    assert.equal(isAllowedHost("127.0.0.1:4111"), true);
    assert.equal(isAllowedHost("example-host.tailnet.ts.net:4111"), true);
    assert.equal(isAllowedHost("evil.example"), false);
    assert.equal(isAllowedOrigin("https://evil.example"), false);

    // CSRF guard
    const missingHdr = await fetch(`${base}/api/text`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: "sneaky" }),
    });
    assert.equal(missingHdr.status, 403);

    // Query-string ?token= MUST BE REJECTED on remote requests (no secrets in URLs!)
    const queryRejected = await fetch(`${base}/api/sessions?token=secret-test-token`, {
      headers: { "X-Forwarded-For": "100.64.0.2" },
    });
    assert.equal(queryRejected.status, 401);

    // Remote auth via Tailscale user header -> 200
    const remoteTsAllowed = await fetch(`${base}/api/sessions`, {
      headers: { "Tailscale-User-Login": "owner@example.com" },
    });
    assert.equal(remoteTsAllowed.status, 200);

    // Remote auth via header token -> POST /api/auth sets HttpOnly SameSite=Strict cookie -> cookie authorizes follow-up GET!
    const authRes = await fetch(`${base}/api/auth`, {
      method: "POST",
      headers: {
        "X-Forwarded-For": "100.64.0.2",
        [GAFFER_CSRF_HEADER]: "1",
        [GAFFER_TOKEN_HEADER]: "secret-test-token",
      },
    });
    assert.equal(authRes.status, 200);
    const setCookie = authRes.headers.get("set-cookie") || "";
    assert.ok(setCookie.includes(`${GAFFER_COOKIE_NAME}=`));
    assert.ok(setCookie.includes("HttpOnly"));
    assert.ok(setCookie.includes("SameSite=Strict"));
    const cookiePair = setCookie.split(";")[0];

    const cookieAllowed = await fetch(`${base}/api/sessions`, {
      headers: { "X-Forwarded-For": "100.64.0.2", Cookie: cookiePair },
    });
    assert.equal(cookieAllowed.status, 200);

    // Malformed JSON -> 400
    const badJson = await fetch(`${base}/api/text`, {
      method: "POST",
      headers: hdrs,
      body: "{not-json",
    });
    assert.equal(badJson.status, 400);

    // Read-back TTS failure MUST cancel staged reply so owner never holds an unspoken draft
    stageMode = true;
    failTts = true;
    const failedReadback = await fetch(`${base}/api/text`, {
      method: "POST",
      headers: hdrs,
      body: JSON.stringify({ text: "Tell Head 1 to run unit tests", speak: true }),
    }).then((r) => r.json());
    assert.equal(failedReadback.ok, true);
    assert.equal(failedReadback.pendingConfirmation, null);
    assert.equal(brain.hasPendingConfirmation(), false);
    assert.ok(String(failedReadback.ttsError || "").includes("Simulated TTS outage"));

    // Audio-unlocked SSE vs audio-locked SSE listener accounting
    stageMode = false;
    failTts = false;
    const ctrl = new AbortController();
    const sseLocked = await fetch(`${base}/events`, { signal: ctrl.signal });
    assert.equal(sseLocked.status, 200);
    const stLocked = await fetch(`${base}/api/state`).then((r) => r.json());
    assert.equal(stLocked.clients, 1);
    assert.equal(stLocked.audioClients, 0);
    ctrl.abort();

    // /api/test-alert + /api/audio/:id
    const alertRes = await fetch(`${base}/api/test-alert`, {
      method: "POST",
      headers: { [GAFFER_CSRF_HEADER]: "1" },
    }).then((r) => r.json());
    assert.equal(alertRes.ok, true);
    const audioBuf = await fetch(`${base}${alertRes.audioUrl}`).then((r) => r.text());
    assert.equal(audioBuf, "FAKE_MP3");
  } finally {
    await app.close();
  }
});

test("11. ui.html script parses cleanly and upholds zero-SSE-before-connect, 1000ms pre-roll, watchdog, manual cap, and no alert cancelRecording", () => {
  const html = readFileSync(resolve(HERE, "ui.html"), "utf8");
  const m = html.match(/<script>([\s\S]*?)<\/script>/);
  assert.ok(m && m[1], "ui.html must contain an inline <script>");
  // Parse JS syntax via Function constructor (throws on any SyntaxError)
  new Function(m[1]);
  const js = m[1];
  assert.ok(html.includes("<title>Topping Out Gaffer</title>") && html.includes("CONNECT GAFFER"), "UI must display Topping Out Gaffer branding");
  assert.ok(!js.includes("connectSse(false)"), "UI must not open audio-locked SSE on load or disconnect");
  assert.ok(!js.includes("withTokenQuery"), "UI must not place access tokens in URL query strings");
  assert.ok(js.includes("pcmSampleRate * 1.0"), "Pre-roll ring buffer must be 1000ms");
  assert.ok(js.includes("MAX_MANUAL_MS"), "Manual recording length must be capped");
  assert.ok(js.includes("armWatchdog"), "Audio playback must have a watchdog timer");
  assert.ok(js.includes("deferredAlertQueue"), "Incoming alerts during recording/staging must be deferred");
  assert.ok(js.includes("speakFallbackError"), "UI must speak a fallback error via speechSynthesis on TTS/fetch error");
  assert.ok(!js.includes("if (isRecording && !manualRecording) cancelRecording()"), "Alerts must never cancel active recording");
  assert.ok(js.includes("managedBuildersBtn") && js.includes("managed-child") && js.includes("OWED"), "UI must render Foreman/Builder hierarchy, OWED badge, and managed builder alert toggle");
  assert.ok(js.includes('addEventListener("quiet"') && js.includes("QUIET BUILDER STOP"), "UI must log muted builder stops cleanly");
  const readme = readFileSync(resolve(HERE, "README.md"), "utf8");
  assert.ok(readme.includes("Data Sent to Models") && readme.includes("BOARD.json"), "README must note that board and job excerpts go to the configured Brain model");
});

test("12. toppingout.ts parses f-status/YOUR CALL strictly, handles two-lane next, skips finished jobs, and classifies topology", () => {
  // Ordinary prose "that's your call" must NOT trigger a YOUR CALL card!
  assert.equal(parseJStatus("I finished the notes, that's your call on wording."), null);

  const noneStatus = parseJStatus("f-status\nwhere: J42, board 03\ndone: WO 1\nstate: clean\nowed: none\nnext: WO 2");
  assert.ok(noneStatus);
  assert.equal(noneStatus.hasRealOwed, false);
  assert.equal(noneStatus.hasYourCall, false);

  const owedStatus = parseJStatus(
    "🚧 YOUR CALL · how does job 4 run?\nf-status\nwhere: J42, board 04\ndone: closed J41\nstate: main pushed\nowed: owner word to start job 4\nnext: start job 4"
  );
  assert.ok(owedStatus);
  assert.equal(owedStatus.hasRealOwed, true);
  assert.equal(owedStatus.hasYourCall, true);
  assert.equal(owedStatus.owed, "owner word to start job 4");

  const dir = mkdtempSync(join(tmpdir(), "orca-to-test-"));
  try {
    mkdirSync(join(dir, "foreman", "projects", "demo-proj"), { recursive: true });
    mkdirSync(join(dir, "foreman", "projects", "two-lane-proj"), { recursive: true });
    mkdirSync(join(dir, "foreman", "projects", "old-frozen"), { recursive: true });
    mkdirSync(join(dir, "foreman", "jobs"), { recursive: true });
    writeFileSync(
      join(dir, "foreman", "projects", "old-frozen", "BOARD.json"),
      JSON.stringify({
        schema: 1,
        topped_out: { date: "2026-10-20", version: 12 },
        project: { slug: "old-frozen", title: "Old Frozen", owed: ["Historical owed line"] },
        jobs: [{ id: "01", title: "Done", kind: "build", state: "merged" }],
      }),
      "utf8"
    );
    writeFileSync(
      join(dir, "foreman", "projects", "two-lane-proj", "BOARD.json"),
      JSON.stringify({
        schema: 1,
        updated: "2026-11-20",
        next: { A: "04", B: "06" },
        project: {
          slug: "two-lane-proj",
          title: "Two-Lane Project",
          lanes: ["A", "B"],
          head: { outcome: "Parallel lanes" },
          standfirst: "Two lanes running.",
          owed: [],
          alerts: [],
        },
        jobs: [
          { id: "04", title: "Lane A job", kind: "build", state: "open", summary: "A" },
          { id: "06", title: "Lane B job", kind: "build", state: "open", summary: "B" },
        ],
      }),
      "utf8"
    );
    writeFileSync(
      join(dir, "foreman", "projects", "demo-proj", "BOARD.json"),
      JSON.stringify({
        schema: 1,
        updated: "2026-11-20",
        next: "04",
        project: {
          slug: "demo-proj",
          title: "Demo Project",
          head: { outcome: "Ship clean API" },
          standfirst: "Job 03 merged; Job 04 next.",
          owed: ["Owner approval on rate limits"],
          alerts: [],
        },
        jobs: [
          { id: "01", title: "Owner: pick hosting", kind: "decision", state: "decision", summary: "Pick region", decision: "Choose EU region" },
          { id: "03", title: "Auth module", kind: "build", state: "merged", summary: "Done" },
          { id: "04", title: "Billing webhooks", kind: "build", state: "in-progress", summary: "Running now" },
        ],
      }),
      "utf8"
    );
    // One active job and one finished job (with real Final head SHA) -> only active job returned!
    writeFileSync(
      join(dir, "foreman", "jobs", "JOB_2026-11-20_demo-proj-04.md"),
      "# Job 04: Billing webhooks\n\n**Project:** demo-proj\n**J-number:** J42 · **Board:** 04\n**Size:** STANDARD\n**Branch:** j42-billing\n**Final head:** <filled at Phase 7> · **Started:** 2026-11-20\n\n| Phase | Artifact | Status | Done |\n| --- | --- | --- | --- |\n| 0: Setup | WO1 | ✅ | yes |\n| 1: Build | WO2 | ⬜ | |\n",
      "utf8"
    );
    writeFileSync(
      join(dir, "foreman", "jobs", "JOB_2026-11-19_demo-proj-03.md"),
      "# Job 03: Auth module\n\n**Project:** demo-proj\n**J-number:** J41 · **Board:** 03\n**Size:** STANDARD\n**Branch:** j41-auth\n**Final head:** 9876543abcdef · **Started:** 2026-11-19\n\n| Phase | Artifact | Status | Done |\n| --- | --- | --- | --- |\n| 0: Setup | WO1 | ✅ | yes |\n| 7: Verification | Ledger | ✅ | yes |\n",
      "utf8"
    );

    const sessions = mergeOrcaState(
      [
        {
          orcaSessionId: "s-foreman",
          kind: "terminal",
          agent: "claude",
          state: "done",
          repo: "demo-repo",
          workspace: "main",
          paneKey: "tab-A:leaf-1",
          title: "Head 1: demo-proj",
          lastAssistantMessage: "f-status\nwhere: J42\ndone: WO1\nstate: clean\nowed: approve widen scope\nnext: WO2",
          updatedAt: 5000,
        },
        {
          orcaSessionId: "s-builder",
          kind: "terminal",
          agent: "pi",
          state: "working",
          repo: "demo-repo",
          workspace: "j42-billing",
          paneKey: "tab-A:leaf-2",
          title: "pi - j42-billing",
          updatedAt: 5100,
        },
        {
          orcaSessionId: "s-other",
          kind: "terminal",
          agent: "antigravity",
          state: "done",
          repo: "notes-repo",
          workspace: "main",
          paneKey: "tab-B:leaf-1",
          title: "notes antigravity",
          updatedAt: 4000,
        },
      ],
      [
        { handle: "t-f", tabId: "tab-A", leafId: "leaf-1", worktreePath: dir, connected: true, writable: true, agentIdentity: "claude" },
        { handle: "t-b", tabId: "tab-A", leafId: "leaf-2", worktreePath: dir, connected: true, writable: true, agentIdentity: "pi" },
        { handle: "t-o", tabId: "tab-B", leafId: "leaf-1", connected: true, writable: true, agentIdentity: "antigravity" },
      ]
    );

    const topo = classifyTopology(sessions);
    assert.equal(topo.get("s-foreman")?.role, "foreman");
    assert.equal(topo.get("s-foreman")?.pairedBuilderId, "s-builder");
    assert.equal(topo.get("s-foreman")?.jStatus?.hasRealOwed, true);
    assert.equal(topo.get("s-builder")?.role, "builder");
    assert.equal(topo.get("s-builder")?.pairedForemanId, "s-foreman");
    assert.equal(topo.get("s-other")?.role, "standalone");

    const boards = discoverBoards([dir]);
    assert.equal(boards.length, 3);
    const demo = boards.find((b) => b.slug === "demo-proj")!;
    const twoLane = boards.find((b) => b.slug === "two-lane-proj")!;
    const frozen = boards.find((b) => b.slug === "old-frozen")!;
    assert.equal(demo.toppedOut, false);
    assert.equal(demo.runningJobs.length, 1, "state: 'in-progress' must count as running");
    assert.equal(demo.nextLabel, "04");
    assert.deepEqual(demo.counts, { total: 3, done: 1, inProgress: 1, open: 0, decision: 1 });
    assert.equal(twoLane.nextLabel, "Lane A: 04, Lane B: 06", "Two-lane next must never render as [object Object]");
    assert.deepEqual(twoLane.nextJobIds, ["04", "06"]);
    assert.deepEqual(twoLane.nextByLane, { A: "04", B: "06" });
    assert.equal(twoLane.nextJobs.length, 2);
    assert.equal(frozen.toppedOut, true);

    const jobs = readActiveJobs(dir);
    assert.equal(jobs.length, 1, "Finished job with real Final head must be filtered out of active jobs");
    assert.equal(jobs[0].jNumber, "J42");
    assert.equal(jobs[0].completedPhases.length, 1);
    assert.equal(jobs[0].pendingPhases.length, 1);

    const queue = buildOwnerQueue(sessions, topo, boards);
    assert.equal(queue.length, 3, "Queue must include Foreman owed + active board decision/owed ONLY (skip topped-out boards)");
    assert.equal(queue[0].source, "foreman");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("13. watcher mutes routine Builder stops while Foreman works, NEVER mutes owed/YOUR CALL or Claude Code trust prompt", async () => {
  let foremanState = "working";
  let builderState = "working";
  let builderPreview = "running WO 2";
  let foremanPreview = "f-status\nwhere: J42\ndone: sent WO2\nstate: working\nowed: none\nnext: review WO2";
  let ts = 1000;

  const orca = new OrcaClient({
    async runJson(args) {
      if (args[0] === "agent" && args[1] === "list") {
        return {
          ok: true,
          result: {
            agents: [
              {
                orcaSessionId: "s-foreman",
                kind: "terminal",
                agent: "claude",
                state: foremanState,
                repo: "demo-repo",
                workspace: "main",
                paneKey: "tab-F:leaf-1",
                title: "OPENER-JOB-42 autonomous run",
                lastAssistantMessage: foremanPreview,
                updatedAt: ts,
              },
              {
                orcaSessionId: "s-builder",
                kind: "terminal",
                agent: "pi",
                state: builderState,
                repo: "demo-repo",
                workspace: "j42-api",
                paneKey: "tab-F:leaf-2",
                title: "pi - j42-api",
                updatedAt: ts,
              },
            ],
          },
        };
      }
      if (args[0] === "terminal" && args[1] === "list") {
        return {
          ok: true,
          result: {
            terminals: [
              { handle: "term-f", tabId: "tab-F", leafId: "leaf-1", connected: true, writable: true, agentIdentity: "claude", preview: foremanPreview, lastOutputAt: ts },
              { handle: "term-b", tabId: "tab-F", leafId: "leaf-2", connected: true, writable: true, agentIdentity: "pi", preview: builderPreview, lastOutputAt: ts },
            ],
          },
        };
      }
      if (args[0] === "terminal" && args[1] === "read") {
        const isF = args.includes("term-f");
        return {
          ok: true,
          result: { terminal: { tail: (isF ? foremanPreview : builderPreview).split("\n") } },
        };
      }
      return { ok: true, result: {} };
    },
  });

  let evalCalls = 0;
  const brain = new VoiceBrain(orca, {
    async chat() {
      evalCalls += 1;
      return {
        content: '{"shouldAlert":true,"needsDecision":true,"spokenAlert":"Owner decision needed."}',
      };
    },
  });

  const alerts: string[] = [];
  const quietStops: Array<{ builderTitle: string; foremanTitle: string }> = [];
  const watcher = new SessionWatcher(orca, brain, {
    hasListener: () => true,
    onAlert: (a) => {
      alerts.push(`${a.sessionTitle}: ${a.spokenText}`);
    },
    onQuietBuilderStop: (info) => quietStops.push(info),
  });

  await watcher.tick(); // baseline: both working

  // 1. Routine managed Builder stop while Foreman is working -> SILENT ($0 LLM!)
  ts = 2000;
  builderState = "done";
  await watcher.tick();
  assert.equal(quietStops.length, 1);
  assert.equal(evalCalls, 0, "Quiet managed Builder stop must spend $0 LLM");
  assert.equal(alerts.length, 0);

  // 2. Claude Code's exact trust prompt on a managed Builder stop -> NEVER muted!
  ts = 3000;
  builderState = "working";
  await watcher.tick();
  ts = 3500;
  builderState = "done";
  builderPreview = "Do you trust the files in this folder?\n1. Yes, proceed";
  await watcher.tick();
  assert.equal(alerts.length, 1, "Claude Code trust prompt must NEVER be muted");
  assert.ok(alerts[0].startsWith("pi - j42-api"));

  // 3. Even if topology misclassified a pane as "builder", a stop showing YOUR CALL / owed: is NEVER muted!
  ts = 4000;
  builderState = "working";
  await watcher.tick();
  ts = 4500;
  builderState = "done";
  builderPreview = "🚧 YOUR CALL · how does job 12 run?\nf-status\nwhere: J42\ndone: ready\nstate: clean\nowed: owner go\nnext: start";
  await watcher.tick();
  assert.equal(alerts.length, 2, "A stop showing owed:/YOUR CALL must NEVER be muted even if paired as builder");

  // 4. Foreman stops with real owed item -> alerts immediately!
  ts = 5000;
  foremanState = "done";
  foremanPreview = "f-status\nwhere: J42\ndone: WO2 reviewed\nstate: waiting\nowed: owner word to open PR\nnext: open PR";
  await watcher.tick();
  assert.equal(alerts.length, 3);
  assert.ok(alerts[2].startsWith("OPENER-JOB-42"));
});

test("14. brain v2: read_board, list_owner_queue, labeled Foreman routing, capped repeat TTL, and stacked fillers", async () => {
  // Stacked confirmation fillers & repeat intent
  assert.equal(parseConfirmationIntent("Uh, so, yes, please, did you get that?"), "yes");
  assert.equal(parseConfirmationIntent("Uh, so, yes, wait, change it please"), "other");
  assert.equal(parseRepeatIntent("Repeat that"), true);
  assert.equal(parseRepeatIntent("Radio, what did you say?"), true);
  assert.equal(parseRepeatIntent("Yes"), false);

  const dir = mkdtempSync(join(tmpdir(), "orca-brain-v2-"));
  try {
    mkdirSync(join(dir, "foreman", "projects", "demo-proj"), { recursive: true });
    writeFileSync(
      join(dir, "foreman", "projects", "demo-proj", "BOARD.json"),
      JSON.stringify({
        schema: 1,
        updated: "2026-11-20",
        next: { A: "05", B: null },
        project: {
          slug: "demo-proj",
          title: "Demo Project",
          lanes: ["A", "B"],
          head: { outcome: "Ship API" },
          standfirst: "Job 05 next.",
          owed: ["Decide billing cap"],
          alerts: [],
        },
        jobs: [{ id: "05", title: "Rate limits", kind: "build", state: "open", summary: "Next" }],
      }),
      "utf8"
    );

    const sent: Array<{ handle: string; textArg: string }> = [];
    const orca = new OrcaClient({
      async runJson(args) {
        if (args[0] === "agent" && args[1] === "list") {
          return {
            ok: true,
            result: {
              agents: [
                {
                  orcaSessionId: "s-foreman",
                  kind: "terminal",
                  agent: "claude",
                  state: "done",
                  repo: "demo-repo",
                  workspace: "main",
                  paneKey: "tab-1:leaf-1",
                  title: "Head 1: demo-proj",
                  lastAssistantMessage: "f-status\nwhere: J42\ndone: checks\nstate: waiting\nowed: pick plan A or B\nnext: WO 3",
                  updatedAt: 5000,
                },
                {
                  orcaSessionId: "s-builder",
                  kind: "terminal",
                  agent: "pi",
                  state: "done",
                  repo: "demo-repo",
                  workspace: "j42-api",
                  paneKey: "tab-1:leaf-2",
                  title: "pi - j42-api",
                  updatedAt: 5100,
                },
              ],
            },
          };
        }
        if (args[0] === "terminal" && args[1] === "list") {
          return {
            ok: true,
            result: {
              terminals: [
                { handle: "term-f", incarnationId: "inc-f", tabId: "tab-1", leafId: "leaf-1", worktreePath: dir, connected: true, writable: true, agentIdentity: "claude" },
                { handle: "term-b", incarnationId: "inc-b", tabId: "tab-1", leafId: "leaf-2", worktreePath: dir, connected: true, writable: true, agentIdentity: "pi" },
              ],
            },
          };
        }
        if (args[0] === "terminal" && args[1] === "show") {
          const isF = args.includes("term-f");
          return {
            ok: true,
            result: {
              terminal: {
                handle: isF ? "term-f" : "term-b",
                incarnationId: isF ? "inc-f" : "inc-b",
                connected: true,
                writable: true,
                orphaned: false,
                agentIdentity: isF ? "claude" : "pi",
              },
            },
          };
        }
        if (args[0] === "terminal" && args[1] === "send") {
          const hIdx = args.indexOf("--terminal");
          const textArg = args.find((a) => a.startsWith("--text=")) || "";
          sent.push({ handle: args[hIdx + 1], textArg });
          return {
            ok: true,
            result: {
              send: {
                requestId: "req-v2",
                accepted: true,
                refusedReason: null,
                prompt: { stages: ["input_accepted", "turn_started"], observation: "turn_started" },
              },
            },
          };
        }
        return { ok: true, result: {} };
      },
    });

    let fakeNow = 50_000;
    let toolToInvoke = "list_owner_queue";
    let toolArgs: Record<string, unknown> = {};
    let lastToolPayload: unknown = null;
    let llmCalls = 0;

    const brain = new VoiceBrain(
      orca,
      {
        async chat(messages) {
          llmCalls += 1;
          const last = messages[messages.length - 1];
          if (last.role === "tool") {
            lastToolPayload = JSON.parse(last.content || "{}");
            return { content: "Checked." };
          }
          return {
            content: null,
            tool_calls: [
              {
                id: `tc_${llmCalls}`,
                type: "function",
                function: { name: toolToInvoke, arguments: JSON.stringify(toolArgs) },
              },
            ],
          };
        },
      },
      () => fakeNow
    );

    // 1. list_owner_queue returns both Foreman owed and BOARD.json owed
    await brain.handleUserUtterance("What needs my word?", "always");
    const qPayload = lastToolPayload as { count: number; items: Array<{ source: string }> };
    assert.equal(qPayload.count, 2);
    assert.equal(qPayload.items[0].source, "foreman");

    // 2. read_board handles two-lane next cleanly (no [object Object])
    toolToInvoke = "read_board";
    toolArgs = { repo_query: "demo" };
    await brain.handleUserUtterance("Check the board", "always");
    const bPayload = lastToolPayload as { count: number; boards: Array<{ slug: string; next: string }> };
    assert.equal(bPayload.count, 1);
    assert.equal(bPayload.boards[0].slug, "demo-proj");
    assert.equal(bPayload.boards[0].next, "Lane A: 05, Lane B: none");

    // 3. Staging for managed Builder routes to owning Foreman WITH "(for builder X)" label in BOTH read-back & sent text!
    toolToInvoke = "stage_reply";
    toolArgs = { session_query: "pi - j42-api", message: "pick plan A" };
    const staged = await brain.handleUserUtterance("Tell j42 to pick plan A", "always");
    assert.ok(
      staged.replyText.includes('Routing to Foreman Head 1: demo-proj. Exact message: "(for builder pi - j42-api) pick plan A"'),
      `Read-back must include exact (for builder X) label; got: ${staged.replyText}`
    );
    assert.equal(brain.getState().pendingConfirmation?.terminalHandle, "term-f");

    // 4. "Repeat that" refreshes TTL within cap with ZERO LLM calls, then confirming sends labeled payload!
    const llmBeforeRepeat = llmCalls;
    fakeNow += 60_000;
    const repeated = await brain.handleUserUtterance("Repeat that", "wake");
    assert.equal(llmCalls, llmBeforeRepeat, "Repeat must not call LLM");
    assert.ok(repeated.replyText.includes('"(for builder pi - j42-api) pick plan A"'));
    assert.equal(brain.hasPendingConfirmation(), true);

    fakeNow += 40_000; // total 100s (< 180s max cap, valid after repeat)
    const confirmed = await brain.handleUserUtterance("Uh, so, yes, please", "wake");
    assert.equal(confirmed.sentDelivery?.ok, true);
    assert.equal(sent.length, 1);
    assert.deepEqual(sent[0], {
      handle: "term-f",
      textArg: `--text=${VOICE_SEND_PREFIX}(for builder pi - j42-api) pick plan A`,
    });

    // 5. Repeat CANNOT keep the yes window open forever: hard cap at CONFIRM_MAX_TTL_MS (180s) & max 2 repeats!
    await brain.handleUserUtterance("Tell j42 to pick plan A", "always");
    fakeNow += 70_000;
    await brain.handleUserUtterance("Repeat that", "wake"); // repeat 1
    fakeNow += 70_000;
    await brain.handleUserUtterance("Repeat that", "wake"); // repeat 2 (expiresAt clamped to createdAt + 180s)
    fakeNow += 45_000; // now 185s > CONFIRM_MAX_TTL_MS -> MUST BE EXPIRED!
    const expiredAfterRepeats = await brain.handleUserUtterance("Yes", "wake");
    assert.equal(sent.length, 1, "Repeat must not keep confirmation open past hard max TTL");
    assert.ok(expiredAfterRepeats.replyText.toLowerCase().includes("expired"));

    // 6. Explicit direct_to_builder=true stages directly to the Builder pane (term-b) without "(for builder ...)" label
    toolToInvoke = "stage_reply";
    toolArgs = { session_query: "pi - j42-api", message: "rerun unit test", direct_to_builder: true };
    const directStaged = await brain.handleUserUtterance("Send directly to builder", "always");
    assert.ok(directStaged.replyText.startsWith('Staged for pi - j42-api. Exact message: "rerun unit test"'));
    assert.equal(brain.getState().pendingConfirmation?.terminalHandle, "term-b");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("15. HTTP server enriches /api/sessions with Topping Out topology and toggles /api/managed-builders", async () => {
  const orca = new OrcaClient(
    makeMockOrca({
      extraAgents: [
        {
          orcaSessionId: "sess-builder-1",
          kind: "terminal",
          agent: "pi",
          state: "working",
          repo: "my-app",
          workspace: "j12-api",
          paneKey: "t1:l2",
          title: "pi - j12-api",
          updatedAt: 5100,
        },
      ],
      extraTerminals: [
        {
          handle: "term_builder1",
          incarnationId: "inc-b1",
          tabId: "t1",
          leafId: "l2",
          connected: true,
          writable: true,
          orphaned: false,
          agentIdentity: "pi",
        },
      ],
    })
  );
  const brain = new VoiceBrain(orca, { async chat() { return { content: "Ok." }; } });
  const app = createVoiceServer({
    orca,
    brain,
    startWatcher: false,
    synthesize: async () => Buffer.from("FAKE_MP3"),
  });
  await new Promise<void>((res) => app.server.listen(0, "127.0.0.1", () => res()));
  const addr = app.server.address();
  assert.ok(addr && typeof addr === "object");
  const base = `http://127.0.0.1:${addr.port}`;

  try {
    const sessRes = await fetch(`${base}/api/sessions`).then((r) => r.json());
    assert.equal(sessRes.ok, true);
    const foreman = sessRes.sessions.find((s: { id: string }) => s.id === "sess-head-1");
    const builder = sessRes.sessions.find((s: { id: string }) => s.id === "sess-builder-1");
    assert.equal(foreman.role, "foreman");
    assert.equal(foreman.pairedBuilderId, "sess-builder-1");
    assert.equal(builder.role, "builder");
    assert.equal(builder.pairedForemanId, "sess-head-1");

    const toggleRes = await fetch(`${base}/api/managed-builders`, {
      method: "POST",
      headers: { "Content-Type": "application/json", [GAFFER_CSRF_HEADER]: "1" },
      body: JSON.stringify({ enabled: true }),
    }).then((r) => r.json());
    assert.equal(toggleRes.ok, true);
    assert.equal(toggleRes.managedBuilderAlerts, true);
  } finally {
    await app.close();
  }
});

test("16. forSpeech sanitizer, closed failure phrases, and verbatim confirmation read-back invariant", async () => {
  const dirty = [
    "### **Head 1** finished J42 on WO-2 (PR-12).",
    "Session fix-login-2fa, work-order-12, and toppingout-release-2026 used 120000000000 tokens.",
    "See [the board](https://example.com/board) or https://internal.local/run/123.",
    "Commit b1323be and uuid 550e8400-e29b-41d4-a716-446655440000 and task:3f9a1b2c and sess-a1b2c3d4.",
    "```ts\nconst secret = 1;\n```",
    "This decade looks clean → ready for your word.",
  ].join("\n");

  const clean = forSpeech(dirty);
  assert.ok(clean.includes("Head 1 finished J42 on WO-2"));
  assert.ok(clean.includes("PR-12"));
  assert.ok(clean.includes("Session fix-login-2fa"), `Branch/session name stripped: ${clean}`);
  assert.ok(clean.includes("work-order-12"), `Hyphenated name stripped: ${clean}`);
  assert.ok(clean.includes("toppingout-release-2026"), `Repo/date name stripped: ${clean}`);
  assert.ok(clean.includes("120000000000 tokens"), `Pure number stripped: ${clean}`);
  assert.ok(clean.includes("See the board"));
  assert.ok(clean.includes("decade looks clean"));
  assert.ok(!clean.includes("https://"), `URL leaked: ${clean}`);
  assert.ok(!clean.includes("b1323be"), `Commit SHA leaked: ${clean}`);
  assert.ok(!clean.includes("550e8400"), `UUID leaked: ${clean}`);
  assert.ok(!clean.includes("task:3f9a1b2c"), `Prefixed ID leaked: ${clean}`);
  assert.ok(!clean.includes("sess-a1b2c3d4"), `Internal hyphenated ID leaked: ${clean}`);
  assert.ok(!clean.includes("const secret"), `Code fence leaked: ${clean}`);
  assert.ok(!clean.includes("**") && !clean.includes("###") && !clean.includes("→"));

  assert.equal(classifyFailure(new Error("OpenRouter STT failed (502): bad gateway")), "stt_failed");
  assert.equal(classifyFailure(new Error("Grok TTS failed (503): unavailable")), "tts_failed");
  assert.equal(classifyFailure(new Error("OPENROUTER_API_KEY is not set (needed for Grok Voice TTS).")), "tts_failed");
  assert.equal(classifyFailure(new Error("LLM request failed (429): rate limit")), "llm_failed");
  assert.equal(classifyFailure(new Error("Request timed out.")), "timeout");
  assert.equal(classifyFailure(new Error("Orca CLI exited 1")), "orca_unreachable");
  const spokenErr = spokenFailureMessage(new Error("OpenRouter STT failed (502): https://openrouter.ai/api"));
  assert.ok(!spokenErr.includes("502") && !spokenErr.includes("https://"));

  // Safety invariant: verbatim confirmation read-back MUST NOT be stripped by forSpeech
  const orca = new OrcaClient(makeMockOrca());
  let calls = 0;
  const brain = new VoiceBrain(orca, {
    async chat() {
      calls += 1;
      return {
        content: null,
        tool_calls: [
          {
            id: `tc_${calls}`,
            type: "function",
            function: {
              name: "stage_reply",
              arguments: JSON.stringify({ session_query: "Head 1", message: "cherry-pick b1323be" }),
            },
          },
        ],
      };
    },
  });
  const staged = await brain.handleUserUtterance("Tell Head 1 cherry-pick b1323be", "always");
  assert.ok(
    staged.replyText.includes('"cherry-pick b1323be"'),
    `Verbatim staged read-back must preserve exact text; got: ${staged.replyText}`
  );
});

test("17. watcher coalesces simultaneous and held alerts into one briefing and retries cleanly on TTS failure", async () => {
  let ts = 1000;
  let stateA = "working";
  let stateB = "working";
  const msgA = "f-status\nwhere: J10\ndone: build\nstate: waiting\nowed: approve deploy\nnext: ship";
  const msgB = "f-status\nwhere: J11\ndone: tests\nstate: waiting\nowed: pick option A or B\nnext: code";

  const orca = new OrcaClient({
    async runJson(args) {
      if (args[0] === "agent" && args[1] === "list") {
        return {
          ok: true,
          result: {
            agents: [
              {
                orcaSessionId: "s-a",
                kind: "terminal",
                agent: "claude",
                state: stateA,
                repo: "repo-a",
                workspace: "main",
                paneKey: "t1:l1",
                title: "Head 1",
                lastAssistantMessage: msgA,
                updatedAt: ts,
              },
              {
                orcaSessionId: "s-b",
                kind: "terminal",
                agent: "claude",
                state: stateB,
                repo: "repo-b",
                workspace: "main",
                paneKey: "t2:l1",
                title: "Head 2",
                lastAssistantMessage: msgB,
                updatedAt: ts + 5,
              },
            ],
          },
        };
      }
      if (args[0] === "terminal" && args[1] === "list") {
        return {
          ok: true,
          result: {
            terminals: [
              { handle: "term-a", tabId: "t1", leafId: "l1", connected: true, writable: true, agentIdentity: "claude", preview: msgA, lastOutputAt: ts },
              { handle: "term-b", tabId: "t2", leafId: "l1", connected: true, writable: true, agentIdentity: "claude", preview: msgB, lastOutputAt: ts + 5 },
            ],
          },
        };
      }
      if (args[0] === "terminal" && args[1] === "read") {
        const isA = args.includes("term-a");
        return { ok: true, result: { terminal: { tail: (isA ? msgA : msgB).split("\n") } } };
      }
      return { ok: true, result: {} };
    },
  });

  const brain = new VoiceBrain(orca, {
    async chat(messages) {
      const text = String(messages[messages.length - 1]?.content || "");
      if (text.includes("Head 2")) {
        return {
          content: '{"shouldAlert":true,"needsDecision":true,"spokenAlert":"Head 2 wants you to pick option A or B."}',
        };
      }
      return {
        content: '{"shouldAlert":true,"needsDecision":false,"spokenAlert":"Head 1 finished the build."}',
      };
    },
  });

  const emitted: Array<{ title: string; text: string; needsDecision: boolean }> = [];
  let failOnce = true;
  const watcher = new SessionWatcher(orca, brain, {
    hasListener: () => true,
    onAlert: async (a) => {
      if (failOnce) {
        failOnce = false;
        throw new Error("Grok TTS failed (503)");
      }
      emitted.push({ title: a.sessionTitle, text: a.spokenText, needsDecision: a.needsDecision });
    },
  });

  await watcher.tick(); // baseline: both working

  // Both stop in the same tick; first attempt fails TTS -> neither tracked state nor brain activeSessionId advances
  ts = 2000;
  stateA = "done";
  stateB = "done";
  await watcher.tick();
  assert.equal(emitted.length, 0);
  assert.equal(brain.getState().activeSessionId, null, "Failed TTS must not record proactive alert into brain state");

  // Next tick retries cleanly and coalesces BOTH into 1 single alert with decision-first ordering!
  await watcher.tick();
  assert.equal(emitted.length, 1, "Two simultaneous stops must coalesce into 1 briefing");
  assert.equal(brain.getState().activeSessionId, "s-b", "Successful alert delivery must update brain activeSessionId");
  assert.equal(emitted[0].needsDecision, true);
  assert.ok(emitted[0].text.startsWith("2 sessions need your attention."));
  assert.ok(
    emitted[0].text.indexOf("Head 2") < emitted[0].text.indexOf("Head 1"),
    `Decision session must be announced first; got: ${emitted[0].text}`
  );

  // Direct unit check on coalesceHeldAlerts dedup + 3-item cap
  const baseSession = {
    id: "id-1",
    kind: "terminal",
    agent: "claude",
    title: "S1",
    repo: "r",
    workspace: "main",
    branch: "main",
    state: "done",
    updatedAt: 1,
    preview: "",
    connected: true,
    writable: true,
    terminalHandle: "h1",
    incarnationId: null,
    hostId: null,
    tabId: null,
    leafId: null,
    worktreePath: null,
  };
  const { alert: capped } = coalesceHeldAlerts([
    { session: { ...baseSession, id: "s1", title: "S1" }, spokenAlert: "One.", needsDecision: false, timestamp: 10 },
    { session: { ...baseSession, id: "s2", title: "S2" }, spokenAlert: "Two.", needsDecision: true, timestamp: 20 },
    { session: { ...baseSession, id: "s3", title: "S3" }, spokenAlert: "Three.", needsDecision: false, timestamp: 30 },
    { session: { ...baseSession, id: "s4", title: "S4" }, spokenAlert: "Four.", needsDecision: false, timestamp: 40 },
  ]);
  assert.ok(capped.spokenText.includes("Plus 1 more in the log."));
});

test("18. SSE Last-Event-ID replays missed alerts within 90s and skips stale alerts", async () => {
  let fakeNow = 1_000_000;
  const orca = new OrcaClient(makeMockOrca());
  const brain = new VoiceBrain(orca, { async chat() { return { content: "Ok." }; } });
  const app = createVoiceServer({
    orca,
    brain,
    startWatcher: false,
    nowFn: () => fakeNow,
    synthesize: async () => Buffer.from("FAKE_MP3"),
  });
  await new Promise<void>((res) => app.server.listen(0, "127.0.0.1", () => res()));
  const addr = app.server.address();
  assert.ok(addr && typeof addr === "object");
  const base = `http://127.0.0.1:${addr.port}`;

  const readSseSnippet = async (path: string, headers: Record<string, string> = {}) => {
    const ctrl = new AbortController();
    const res = await fetch(`${base}${path}`, { headers, signal: ctrl.signal });
    const reader = res.body!.getReader();
    const dec = new TextDecoder();
    let out = "";
    const timer = setTimeout(() => ctrl.abort(), 120);
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        out += dec.decode(value, { stream: true });
      }
    } catch {
      /* aborted after snippet */
    } finally {
      clearTimeout(timer);
    }
    return out;
  };

  try {
    // Emit alert #1
    await fetch(`${base}/api/test-alert`, {
      method: "POST",
      headers: { [GAFFER_CSRF_HEADER]: "1" },
    });
    const firstSnap = await readSseSnippet("/events?audio=1");
    const connIdMatch = firstSnap.match(/id:\s*(\d+)\nevent:\s*connected/);
    assert.ok(connIdMatch, `Expected id on connected frame; got:\n${firstSnap}`);
    const lastSeenId = Number(connIdMatch[1]);
    assert.ok(lastSeenId >= 1);

    // Client disconnects; alert #2 fires 5s later while offline
    fakeNow += 5_000;
    await fetch(`${base}/api/test-alert`, {
      method: "POST",
      headers: { [GAFFER_CSRF_HEADER]: "1" },
    });

    // Reconnect with Last-Event-ID -> replays ONLY alert #2 with replayed: true,
    // and connected frame MUST NOT jump id ahead of alert #2 before replay finishes!
    const replayedSnap = await readSseSnippet("/events?audio=1", {
      "Last-Event-ID": String(lastSeenId),
    });
    assert.ok(
      !replayedSnap.includes(`id: ${lastSeenId + 1}\nevent: connected`),
      `connected frame must not advance cursor ahead of replayed alert; got:\n${replayedSnap}`
    );
    const alertMatches = replayedSnap.match(/event:\s*alert/g) || [];
    assert.equal(alertMatches.length, 1, `Expected 1 replayed alert; got:\n${replayedSnap}`);
    assert.ok(replayedSnap.includes(`id: ${lastSeenId + 1}\nevent: alert`));
    assert.ok(replayedSnap.includes('"replayed":true'));

    // Advance 95s past 90s staleness window -> reconnect with same Last-Event-ID gets 0 stale alerts
    fakeNow += 95_000;
    const staleSnap = await readSseSnippet("/events?audio=1", {
      "Last-Event-ID": String(lastSeenId),
    });
    assert.equal((staleSnap.match(/event:\s*alert/g) || []).length, 0, "Stale alerts must not replay");

    // Server restart recovery: client sends Last-Event-ID higher than server's sequence -> resets cursor to 0
    // and replays fresh (<90s) alerts emitted after restart!
    fakeNow += 1_000;
    await fetch(`${base}/api/test-alert`, {
      method: "POST",
      headers: { [GAFFER_CSRF_HEADER]: "1" },
    });
    const restartedSnap = await readSseSnippet("/events?audio=1", {
      "Last-Event-ID": "999",
    });
    assert.ok(restartedSnap.includes("id: 0\nevent: connected"), `Expected id: 0 reset on restart; got:\n${restartedSnap}`);
    assert.ok(restartedSnap.includes('"cursorReset":true'));
    assert.equal(
      (restartedSnap.match(/event:\s*alert/g) || []).length,
      1,
      `Expected fresh post-restart alert to replay; got:\n${restartedSnap}`
    );
  } finally {
    await app.close();
  }
});

test("19. cut-playback resume ('finish that') speaks unheard tail with zero LLM calls and never bypasses confirmation", async () => {
  const briefing =
    "Head 1 finished all tests. The diff touched four files cleanly. It is waiting on your word to open the PR.";
  assert.equal(computeUnheardTail(briefing, 0.05), briefing);
  assert.equal(computeUnheardTail(briefing, 0.96), "");
  const midTail = computeUnheardTail(briefing, 0.55);
  assert.ok(midTail.includes("waiting on your word to open the PR."));
  assert.ok(!midTail.startsWith("Head 1 finished all tests."));
  assert.equal(parseResumeIntent("Gaffer, finish that"), true);
  assert.equal(parseResumeIntent("continue"), true);
  assert.equal(parseResumeIntent("continue", { hasCutSpeech: false }), false);
  assert.equal(parseResumeIntent("what did I miss", { hasCutSpeech: true }), true);
  assert.equal(parseResumeIntent("what did I miss", { hasCutSpeech: false }), false);
  assert.equal(parseResumeIntent("what got cut off", { hasCutSpeech: false }), true);
  assert.equal(parseResumeIntent("yes"), false);

  const orca = new OrcaClient(makeMockOrca());
  let llmCalls = 0;
  let shouldThrowLlm = false;
  let stageReplyMode = true;
  const brain = new VoiceBrain(orca, {
    async chat() {
      llmCalls += 1;
      if (shouldThrowLlm) throw new Error("LLM request failed (503): upstream https://openrouter.ai down");
      if (!stageReplyMode) return { content: "Continuing with the walkthrough." };
      return {
        content: null,
        tool_calls: [
          {
            id: `tc_${llmCalls}`,
            type: "function",
            function: {
              name: "stage_reply",
              arguments: JSON.stringify({ session_query: "Head 1", message: "looks good" }),
            },
          },
        ],
      };
    },
  });

  const app = createVoiceServer({
    orca,
    brain,
    startWatcher: false,
    synthesize: async () => Buffer.from("FAKE_MP3"),
  });
  await new Promise<void>((res) => app.server.listen(0, "127.0.0.1", () => res()));
  const addr = app.server.address();
  assert.ok(addr && typeof addr === "object");
  const base = `http://127.0.0.1:${addr.port}`;

  try {
    // 1. Report cut playback via HTTP endpoint
    const cutRes = await fetch(`${base}/api/playback-cut`, {
      method: "POST",
      headers: { "Content-Type": "application/json", [GAFFER_CSRF_HEADER]: "1" },
      body: JSON.stringify({ text: briefing, playedRatio: 0.65, sessionTitle: "Head 1" }),
    }).then((r) => r.json());
    assert.equal(cutRes.ok, true);
    assert.equal(cutRes.hasRemainder, true);

    // 2. "Gaffer, finish that" resumes unheard tail with ZERO LLM calls
    const before = llmCalls;
    const resumed = await fetch(`${base}/api/text`, {
      method: "POST",
      headers: { "Content-Type": "application/json", [GAFFER_CSRF_HEADER]: "1" },
      body: JSON.stringify({ text: "Gaffer, finish that", mode: "wake", speak: false }),
    }).then((r) => r.json());
    assert.equal(llmCalls, before, "Resume must not invoke LLM");
    assert.ok(resumed.replyText.startsWith("Here is the rest:"));
    assert.ok(resumed.replyText.includes("waiting on your word to open the PR."));

    // 2b. With NO cut speech, generic "continue" and "what did I miss" go to the LLM (not hijacked!),
    // while explicit "what got cut off" still answers directly
    stageReplyMode = false;
    const beforeGeneric = llmCalls;
    const genericCont = await brain.handleUserUtterance("Gaffer, continue", "wake");
    assert.equal(llmCalls, beforeGeneric + 1, "Generic 'continue' with no cut speech must reach LLM");
    assert.equal(genericCont.replyText, "Continuing with the walkthrough.");

    const beforeMiss = llmCalls;
    const missStatus = await brain.handleUserUtterance("Gaffer, what did I miss?", "wake");
    assert.equal(llmCalls, beforeMiss + 1, "'What did I miss' with no cut speech must reach LLM for a status update");
    assert.equal(missStatus.replyText, "Continuing with the walkthrough.");

    const beforeStrict = llmCalls;
    const strictEmpty = await brain.handleUserUtterance("Gaffer, what got cut off?", "wake");
    assert.equal(llmCalls, beforeStrict, "Explicit 'what got cut off' must not call LLM");
    assert.equal(strictEmpty.replyText, "Nothing was cut off just now.");
    stageReplyMode = true;

    // 3. While a staged reply is pending, "continue" hits confirmation gate, NOT resume
    await brain.handleUserUtterance("Tell Head 1 looks good", "always");
    brain.recordInterruptedSpeech(briefing, 0.5, "Head 1");
    const duringConfirm = await brain.handleUserUtterance("continue", "wake");
    assert.ok(duringConfirm.replyText.includes("Say yes or cancel"));
    assert.equal(brain.hasPendingConfirmation(), true);
    brain.cancelPendingConfirmation();

    // 4. Server 500 includes a clean spokenError without raw HTTP status/URL
    shouldThrowLlm = true;
    const errRes = await fetch(`${base}/api/text`, {
      method: "POST",
      headers: { "Content-Type": "application/json", [GAFFER_CSRF_HEADER]: "1" },
      body: JSON.stringify({ text: "What is happening?", mode: "manual", speak: false }),
    });
    assert.equal(errRes.status, 500);
    const errBody = await errRes.json();
    assert.equal(errBody.ok, false);
    assert.ok(typeof errBody.spokenError === "string" && errBody.spokenError.length > 0);
    assert.ok(!errBody.spokenError.includes("503") && !errBody.spokenError.includes("https://"));
  } finally {
    await app.close();
  }
});

// Orca CLI adapter: structured session discovery, transcript + screen reading,
// unambiguous session matching, live target re-verification, and safe prompt delivery.
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

export interface OrcaAgentRecord {
  orcaSessionId: string;
  kind: string; // "terminal" | "chat"
  agent: string; // "claude" | "pi" | "antigravity" | "codex" | ...
  state: string; // "working" | "done" | "waiting" | ...
  worktreeId?: string;
  workspace?: string;
  repo?: string;
  hostId?: string;
  paneKey?: string | null;
  title?: string | null;
  lastAssistantMessage?: string | null;
  updatedAt?: number;
}

export interface OrcaTerminalRecord {
  handle: string;
  ptyId?: string;
  incarnationId?: string;
  orphaned?: boolean;
  worktreeId?: string;
  worktreePath?: string;
  branch?: string;
  tabId?: string;
  leafId?: string;
  title?: string;
  connected?: boolean;
  writable?: boolean;
  lastOutputAt?: number;
  preview?: string;
  executionHostId?: string;
  agentIdentity?: string | null;
}

export interface SessionSummary {
  id: string; // orcaSessionId (or terminal handle if no agent record)
  orcaSessionId: string | null;
  terminalHandle: string | null;
  incarnationId: string | null;
  tabId?: string | null;
  leafId?: string | null;
  worktreePath?: string | null;
  title: string;
  repo: string;
  workspace: string;
  branch: string;
  agent: string;
  kind: string;
  state: string;
  writable: boolean;
  connected: boolean;
  hostId: string;
  updatedAt: number;
  preview: string;
}

export interface SessionDetails {
  session: SessionSummary;
  transcriptState: string | null;
  recentMessages: Array<{ role: string; text: string }>;
  screenTail: string;
  readErrors: string[];
}

export interface SendResult {
  ok: boolean;
  terminalHandle: string;
  accepted: boolean;
  submitted: boolean;
  turnStarted: boolean;
  refusedReason?: string | null;
  retryRequestId?: string | null;
  detail: string;
  raw?: unknown;
}

export interface VerifyTargetResult {
  ok: boolean;
  reason?: string;
}

export type SessionResolution =
  | { status: "match"; session: SessionSummary }
  | { status: "ambiguous"; candidates: SessionSummary[] }
  | { status: "not_found"; reason: string };

export interface OrcaRunner {
  runJson(args: string[], timeoutMs?: number): Promise<unknown>;
}

const DEFAULT_ORCA_BIN = process.env.ORCA_BIN || "orca";

export function createCliRunner(environment?: string): OrcaRunner {
  const envArgs = environment ? ["--environment", environment] : [];
  return {
    async runJson(args: string[], timeoutMs = 15000): Promise<unknown> {
      const fullArgs = [...args, ...envArgs, "--json"];
      try {
        const { stdout } = await execFileAsync(DEFAULT_ORCA_BIN, fullArgs, {
          timeout: timeoutMs,
          maxBuffer: 8 * 1024 * 1024,
          windowsHide: true,
        });
        const trimmed = stdout.trim();
        if (!trimmed) throw new Error(`Empty JSON from orca ${args.join(" ")}`);
        return JSON.parse(trimmed);
      } catch (err) {
        // Orca CLI may exit non-zero while still emitting structured JSON on stdout (e.g. refused send).
        const e = err as { stdout?: string | Buffer; stderr?: string | Buffer; message?: string };
        const out = typeof e?.stdout === "string" ? e.stdout.trim() : Buffer.isBuffer(e?.stdout) ? e.stdout.toString("utf8").trim() : "";
        if (out.startsWith("{")) {
          try {
            return JSON.parse(out);
          } catch {
            /* fall through to original error */
          }
        }
        throw err;
      }
    },
  };
}

/**
 * Strip ANSI escapes, collapse newlines into single spaces, remove ASCII/C1 control characters
 * and Unicode bidi control characters, and cap length so a spoken reply can never submit
 * multiple lines or raw terminal/bidi control bytes.
 */
export function sanitizeTerminalMessage(raw: string, maxLen = 2000): string {
  return String(raw || "")
    .replace(/\x1b\[[0-9;?]*[ -/]*[@-~]/g, "")
    .replace(/\x1b[@-_]/g, "")
    .replace(/[\r\n\t]+/g, " ")
    .replace(/[\x00-\x1f\x7f-\x9f]/g, "")
    .replace(/[\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, maxLen);
}

const LEADING_CMD_CHAR_NAMES: Record<string, string> = {
  "/": "slash (/)",
  "!": "exclamation mark (!)",
  "#": "hash (#)",
};

/**
 * Check if a sanitized message begins with a terminal/agent command prefix (/, !, #).
 * Returns the spelled-out character name if blocked, or null if safe.
 */
export function detectBlockedLeadingPrefix(cleanMessage: string): string | null {
  const first = cleanMessage.trim()[0];
  return first && LEADING_CMD_CHAR_NAMES[first] ? LEADING_CMD_CHAR_NAMES[first] : null;
}

const NUMBER_WORD_MAP: Record<string, string> = {
  zero: "0",
  one: "1",
  two: "2",
  three: "3",
  four: "4",
  five: "5",
  six: "6",
  seven: "7",
  eight: "8",
  nine: "9",
  ten: "10",
  eleven: "11",
  twelve: "12",
  thirteen: "13",
  fourteen: "14",
  fifteen: "15",
  sixteen: "16",
  seventeen: "17",
  eighteen: "18",
  nineteen: "19",
  twenty: "20",
};

export function normalizeSessionQuery(query: string): string {
  return query
    .trim()
    .toLowerCase()
    .replace(/\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)\b/gi, (w) => {
      return NUMBER_WORD_MAP[w.toLowerCase()] ?? w;
    });
}

function repoNameFromPath(p?: string): string {
  if (!p) return "";
  const norm = p.replace(/\\/g, "/").replace(/\/+$/, "");
  const parts = norm.split("/");
  return parts[parts.length - 1] || norm;
}

function cleanBranch(b?: string): string {
  if (!b) return "";
  return b.replace(/^refs\/heads\//, "");
}

function humanTitle(agent?: OrcaAgentRecord, term?: OrcaTerminalRecord): string {
  const aTitle = agent?.title?.trim();
  if (aTitle) return aTitle;
  const tTitle = term?.title?.trim();
  if (tTitle && !/pwsh\.exe|powershell|cmd\.exe|bash$/i.test(tTitle)) {
    return tTitle;
  }
  const repo = agent?.repo || repoNameFromPath(term?.worktreePath);
  const ws = agent?.workspace || cleanBranch(term?.branch);
  const who = agent?.agent || term?.agentIdentity || "terminal";
  if (repo && ws && ws !== "main") return `${repo} (${ws})`;
  if (repo) return `${repo} ${who}`;
  return term?.handle || agent?.orcaSessionId || "unnamed session";
}

export function mergeOrcaState(
  agents: OrcaAgentRecord[],
  terminals: OrcaTerminalRecord[]
): SessionSummary[] {
  const termByPaneKey = new Map<string, OrcaTerminalRecord>();
  const matchedTerminals = new Set<string>();

  for (const t of terminals) {
    if (t.tabId && t.leafId) {
      termByPaneKey.set(`${t.tabId}:${t.leafId}`, t);
    }
  }

  const sessions: SessionSummary[] = [];

  for (const a of agents) {
    const term = a.paneKey ? termByPaneKey.get(a.paneKey) : undefined;
    if (term) matchedTerminals.add(term.handle);

    const updatedAt = Math.max(a.updatedAt || 0, term?.lastOutputAt || 0);
    const hasLiveAgent = Boolean(term?.connected && term?.writable && !term?.orphaned && term?.agentIdentity);
    const paneParts = a.paneKey ? a.paneKey.split(":") : [];
    const worktreeFromId =
      a.worktreeId && a.worktreeId.includes("::") ? a.worktreeId.split("::").slice(1).join("::") : null;
    sessions.push({
      id: a.orcaSessionId,
      orcaSessionId: a.orcaSessionId,
      terminalHandle: term?.handle ?? null,
      incarnationId: term?.incarnationId ?? null,
      tabId: term?.tabId ?? paneParts[0] ?? null,
      leafId: term?.leafId ?? paneParts[1] ?? null,
      worktreePath: term?.worktreePath ?? worktreeFromId ?? null,
      title: humanTitle(a, term),
      repo: a.repo || repoNameFromPath(term?.worktreePath) || "",
      workspace: a.workspace || cleanBranch(term?.branch) || "",
      branch: cleanBranch(term?.branch) || a.workspace || "",
      agent: a.agent || term?.agentIdentity || "unknown",
      kind: a.kind || "terminal",
      state: a.state || "unknown",
      writable: hasLiveAgent,
      connected: Boolean(term?.connected),
      hostId: a.hostId || term?.executionHostId || "local",
      updatedAt,
      preview: term?.preview || a.lastAssistantMessage || "",
    });
  }

  // Include live agent terminals that did not appear in `orca agent list`
  for (const t of terminals) {
    if (matchedTerminals.has(t.handle)) continue;
    if (!t.connected || t.orphaned) continue;
    if (!t.agentIdentity) continue;
    sessions.push({
      id: t.handle,
      orcaSessionId: null,
      terminalHandle: t.handle,
      incarnationId: t.incarnationId ?? null,
      tabId: t.tabId ?? null,
      leafId: t.leafId ?? null,
      worktreePath: t.worktreePath ?? null,
      title: humanTitle(undefined, t),
      repo: repoNameFromPath(t.worktreePath),
      workspace: cleanBranch(t.branch),
      branch: cleanBranch(t.branch),
      agent: t.agentIdentity,
      kind: "terminal",
      state: "unknown",
      writable: Boolean(t.connected && t.writable && !t.orphaned && t.agentIdentity),
      connected: Boolean(t.connected),
      hostId: t.executionHostId || "local",
      updatedAt: t.lastOutputAt || 0,
      preview: t.preview || "",
    });
  }

  sessions.sort((x, y) => {
    if (x.connected !== y.connected) return x.connected ? -1 : 1;
    return y.updatedAt - x.updatedAt;
  });

  return sessions;
}

function escapeRe(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function containsWholePhrase(haystack: string, phrase: string): boolean {
  if (!phrase) return false;
  const re = new RegExp(`(?:^|[^a-z0-9])${escapeRe(phrase)}(?:$|[^a-z0-9])`, "i");
  return re.test(haystack);
}

/**
 * Unambiguous session matcher:
 * - Uses word-boundary matching so "Head 1" never matches "Head 10".
 * - Never quietly falls back to the newest session when "active" is unset or stale.
 * - Reports ambiguity when multiple sessions match closely.
 */
export function resolveSessionStrict(
  sessions: SessionSummary[],
  query: string | null | undefined,
  activeSessionId?: string | null,
  options?: { allowFallbackLatest?: boolean; preferWritable?: boolean }
): SessionResolution {
  if (!sessions.length) {
    return { status: "not_found", reason: "No Orca sessions are available." };
  }

  const q = normalizeSessionQuery(query || "");
  if (!q || q === "active" || q === "current" || q === "that" || q === "it" || q === "latest") {
    if (activeSessionId) {
      const active = sessions.find(
        (s) => s.id === activeSessionId || s.terminalHandle === activeSessionId
      );
      if (active) return { status: "match", session: active };
    }
    if (options?.allowFallbackLatest && q === "latest") {
      const pool = options.preferWritable ? sessions.filter((s) => s.writable) : sessions;
      return { status: "match", session: pool[0] || sessions[0] };
    }
    return {
      status: "not_found",
      reason: "No active session is currently selected. Name the session explicitly.",
    };
  }

  // When staging a reply (preferWritable=true), prefer live writable sessions first so dead/closed
  // historical sessions with the same name never shadow an active pane.
  const searchPools = options?.preferWritable
    ? [sessions.filter((s) => s.writable), sessions]
    : [sessions];

  for (const pool of searchPools) {
    if (!pool.length) continue;

    // 1. Exact id, handle, or title match
    const exactMatches = pool.filter(
      (s) =>
        s.id.toLowerCase() === q ||
        s.orcaSessionId?.toLowerCase() === q ||
        s.terminalHandle?.toLowerCase() === q ||
        s.title.toLowerCase() === q
    );
    if (exactMatches.length === 1) return { status: "match", session: exactMatches[0] };
    if (exactMatches.length > 1) return { status: "ambiguous", candidates: exactMatches };

    // 2. Whole-phrase / word-boundary token scoring (so "head 1" cannot match "head 10")
    const tokens = q.split(/[^a-z0-9]+/).filter((t) => t.length >= 1);
    if (!tokens.length) {
      return { status: "not_found", reason: `Could not understand session name "${query}".` };
    }

    const scored: Array<{ session: SessionSummary; score: number }> = [];

    for (const s of pool) {
      const titleLow = s.title.toLowerCase();
      const metaLow = `${s.repo} ${s.workspace} ${s.branch} ${s.agent}`.toLowerCase();
      const allLow = `${titleLow} ${metaLow}`;

      // Every query token must match as a whole word/number in title or metadata
      const allTokensMatch = tokens.every((tok) => containsWholePhrase(allLow, tok));
      if (!allTokensMatch) continue;

      let score = 0;
      if (containsWholePhrase(titleLow, q)) score += 120;
      else if (containsWholePhrase(allLow, q)) score += 80;

      for (const tok of tokens) {
        if (containsWholePhrase(titleLow, tok)) score += 30;
        else if (containsWholePhrase(metaLow, tok)) score += 12;
      }

      if (score > 0) {
        scored.push({ session: s, score });
      }
    }

    if (scored.length === 0) continue;

    scored.sort((a, b) => b.score - a.score);
    const topScore = scored[0].score;
    const nearTop = scored.filter((x) => topScore - x.score <= 15);
    if (nearTop.length > 1) {
      return { status: "ambiguous", candidates: nearTop.map((x) => x.session) };
    }

    return { status: "match", session: scored[0].session };
  }

  return { status: "not_found", reason: `No session matched "${query}".` };
}

export function resolveSession(
  sessions: SessionSummary[],
  query: string | null | undefined,
  activeSessionId?: string | null
): SessionSummary | null {
  const res = resolveSessionStrict(sessions, query, activeSessionId);
  return res.status === "match" ? res.session : null;
}

export class OrcaClient {
  private runner: OrcaRunner;

  constructor(runner?: OrcaRunner) {
    this.runner = runner ?? createCliRunner(process.env.ORCA_ENVIRONMENT);
  }

  async listSessions(): Promise<SessionSummary[]> {
    const [agentRes, termRes] = await Promise.allSettled([
      this.runner.runJson(["agent", "list"], 15000),
      this.runner.runJson(["terminal", "list"], 15000),
    ]);

    const agents: OrcaAgentRecord[] =
      agentRes.status === "fulfilled"
        ? ((agentRes.value as { result?: { agents?: OrcaAgentRecord[] } })?.result?.agents ?? [])
        : [];
    const terminals: OrcaTerminalRecord[] =
      termRes.status === "fulfilled"
        ? ((termRes.value as { result?: { terminals?: OrcaTerminalRecord[] } })?.result?.terminals ??
          [])
        : [];

    if (agentRes.status === "rejected" && termRes.status === "rejected") {
      throw new Error(
        `Orca unreachable: ${String(agentRes.reason)}; ${String(termRes.reason)}`
      );
    }

    return mergeOrcaState(agents, terminals);
  }

  async readSession(session: SessionSummary, limit = 12): Promise<SessionDetails> {
    const readErrors: string[] = [];
    let transcriptState: string | null = null;
    const recentMessages: Array<{ role: string; text: string }> = [];
    let screenTail = "";

    const tasks: Promise<void>[] = [];

    if (session.orcaSessionId) {
      tasks.push(
        this.runner
          .runJson(
            ["agent", "read", `orca_session_id:${session.orcaSessionId}`, "--limit", String(limit)],
            15000
          )
          .then((raw) => {
            const r = (raw as {
              result?: {
                state?: string;
                entries?: Array<{ kind?: string; role?: string; text?: string }>;
              };
            })?.result;
            if (r?.state) transcriptState = r.state;
            for (const entry of r?.entries ?? []) {
              const txt = (entry.text || "").trim();
              if (!txt) continue;
              recentMessages.push({
                role: entry.role || entry.kind || "unknown",
                text: txt.length > 3500 ? `${txt.slice(0, 3500)}...` : txt,
              });
            }
          })
          .catch((err) => {
            readErrors.push(`agent read failed: ${err instanceof Error ? err.message : String(err)}`);
          })
      );
    }

    if (session.terminalHandle && session.connected) {
      tasks.push(
        this.runner
          .runJson(
            ["terminal", "read", "--terminal", session.terminalHandle, "--screen", "--limit", "120"],
            12000
          )
          .then((raw) => {
            const tail =
              (raw as { result?: { terminal?: { tail?: string[] } } })?.result?.terminal?.tail ?? [];
            const nonEmpty = tail.map((l) => l.replace(/\s+$/, "")).filter((l) => l.length > 0);
            screenTail = nonEmpty.slice(-90).join("\n");
          })
          .catch((err) => {
            readErrors.push(
              `terminal screen read failed: ${err instanceof Error ? err.message : String(err)}`
            );
          })
      );
    }

    await Promise.all(tasks);

    if (!screenTail && session.preview) {
      screenTail = session.preview;
    }

    return {
      session,
      transcriptState,
      recentMessages: recentMessages.slice(-8),
      screenTail,
      readErrors,
    };
  }

  /**
   * Re-check live terminal state right before dispatching a confirmed reply:
   * refuses if the terminal closed, restarted (incarnationId changed), or dropped to a bare shell.
   */
  async verifyTerminalTarget(
    terminalHandle: string,
    expectedIncarnationId: string | null,
    expectedAgent: string
  ): Promise<VerifyTargetResult> {
    try {
      const raw = (await this.runner.runJson(
        ["terminal", "show", "--terminal", terminalHandle],
        10000
      )) as {
        ok?: boolean;
        result?: { terminal?: OrcaTerminalRecord };
        error?: { message?: string };
      };

      const term = raw?.result?.terminal;
      if (!raw?.ok || !term) {
        return {
          ok: false,
          reason: raw?.error?.message || "Target terminal is no longer open.",
        };
      }
      if (!term.connected || !term.writable || term.orphaned) {
        return { ok: false, reason: "Target terminal is disconnected or not writable." };
      }
      if (expectedIncarnationId && term.incarnationId && term.incarnationId !== expectedIncarnationId) {
        return { ok: false, reason: "Target terminal process restarted since staging." };
      }
      if (!term.agentIdentity) {
        return {
          ok: false,
          reason: "No running agent is detected in that pane anymore (may be a bare shell).",
        };
      }
      if (
        expectedAgent &&
        expectedAgent !== "unknown" &&
        term.agentIdentity.toLowerCase() !== expectedAgent.toLowerCase()
      ) {
        return {
          ok: false,
          reason: `Agent in that pane changed from ${expectedAgent} to ${term.agentIdentity}.`,
        };
      }

      return { ok: true };
    } catch (err) {
      return {
        ok: false,
        reason: `Could not verify target terminal: ${err instanceof Error ? err.message : String(err)}`,
      };
    }
  }

  async sendToTerminal(terminalHandle: string, text: string): Promise<SendResult> {
    const clean = sanitizeTerminalMessage(text);
    if (!clean) {
      return {
        ok: false,
        terminalHandle,
        accepted: false,
        submitted: false,
        turnStarted: false,
        detail: "Refused to send empty text.",
      };
    }

    const blockedChar = detectBlockedLeadingPrefix(clean);
    if (blockedChar) {
      return {
        ok: false,
        terminalHandle,
        accepted: false,
        submitted: false,
        turnStarted: false,
        refusedReason: `Blocked leading ${blockedChar}`,
        detail: `Refused to send: messages cannot start with ${blockedChar}.`,
      };
    }

    type OrcaSendRaw = {
      ok?: boolean;
      result?: {
        send?: {
          accepted?: boolean;
          refusedReason?: string | null;
          requestId?: string | null;
          retryRequestId?: string | null;
          prompt?: {
            stages?: string[];
            observation?: string | null;
          } | null;
        };
      };
      error?: {
        code?: string;
        message?: string;
        retryRequestId?: string | null;
        details?: { retryRequestId?: string | null; requestId?: string | null };
      };
    };

    const parseRawSend = (raw: OrcaSendRaw): SendResult => {
      const send = raw?.result?.send;
      const retryId =
        send?.retryRequestId ??
        send?.requestId ??
        raw?.error?.retryRequestId ??
        raw?.error?.details?.retryRequestId ??
        raw?.error?.details?.requestId ??
        null;

      if (!raw?.ok || !send || send.refusedReason || send.accepted === false) {
        const reason =
          send?.refusedReason ||
          raw?.error?.message ||
          (!send ? "Orca returned an unclear send receipt." : "Orca refused the terminal send.");
        return {
          ok: false,
          terminalHandle,
          accepted: false,
          submitted: false,
          turnStarted: false,
          refusedReason: send?.refusedReason ?? raw?.error?.message ?? null,
          retryRequestId: retryId,
          detail: reason,
          raw,
        };
      }

      const stages = Array.isArray(send.prompt?.stages)
        ? send.prompt!.stages.map((s) => String(s).toLowerCase())
        : [];
      const observation = String(send.prompt?.observation || "").toLowerCase();
      const accepted = Boolean(send.accepted);
      const turnStarted =
        accepted &&
        (observation === "turn_started" ||
          stages.includes("turn_started") ||
          observation.includes("turn_started"));
      const submitted =
        accepted &&
        (turnStarted ||
          observation === "submitted" ||
          stages.includes("submitted") ||
          stages.includes("prompt_submitted"));

      return {
        ok: accepted,
        terminalHandle,
        accepted,
        submitted,
        turnStarted,
        refusedReason: null,
        retryRequestId: retryId,
        detail: !accepted
          ? "Prompt was not accepted."
          : turnStarted
            ? "Prompt delivered and turn started."
            : "Accepted, turn not started.",
        raw,
      };
    };

    const extractRetryIdFromError = (err: unknown): string | null => {
      const msg = err instanceof Error ? err.message : String(err);
      const m = msg.match(/--retry-request\s+([a-zA-Z0-9._:-]+)/i) || msg.match(/retryRequestId["']?\s*[:=]\s*["']?([a-zA-Z0-9._:-]+)/i);
      return m ? m[1] : null;
    };

    const baseArgs = [
      "terminal",
      "send",
      "--terminal",
      terminalHandle,
      `--text=${clean}`,
      "--enter",
      "--wait-submit",
      "8",
    ];

    let firstResult: SendResult | null = null;
    let retryId: string | null = null;
    let unclearFailure = false;

    try {
      const raw = (await this.runner.runJson(baseArgs, 20000)) as OrcaSendRaw;
      firstResult = parseRawSend(raw);
      retryId = firstResult.retryRequestId ?? null;
      // Retry ONLY on an unclear/timed-out receipt when Orca gave a retry request ID (never resend plain).
      const errMsg = `${raw?.error?.code || ""} ${raw?.error?.message || ""} ${firstResult.detail}`.toLowerCase();
      if (
        !firstResult.ok &&
        !raw?.result?.send?.refusedReason &&
        retryId &&
        (!raw?.result?.send || /timeout|timed out|ambiguous|unclear|transport/.test(errMsg))
      ) {
        unclearFailure = true;
      }
    } catch (err) {
      retryId = extractRetryIdFromError(err);
      unclearFailure = Boolean(retryId);
      if (!retryId) {
        return {
          ok: false,
          terminalHandle,
          accepted: false,
          submitted: false,
          turnStarted: false,
          detail: `Terminal send failed: ${err instanceof Error ? err.message : String(err)}`,
        };
      }
    }

    if (unclearFailure && retryId) {
      try {
        const retryRaw = (await this.runner.runJson(
          [...baseArgs, "--retry-request", retryId],
          20000
        )) as OrcaSendRaw;
        return parseRawSend(retryRaw);
      } catch (retryErr) {
        return {
          ok: false,
          terminalHandle,
          accepted: false,
          submitted: false,
          turnStarted: false,
          retryRequestId: retryId,
          detail: `Terminal send retry failed: ${retryErr instanceof Error ? retryErr.message : String(retryErr)}`,
        };
      }
    }

    return (
      firstResult ?? {
        ok: false,
        terminalHandle,
        accepted: false,
        submitted: false,
        turnStarted: false,
        detail: "Terminal send returned no result.",
      }
    );
  }
}

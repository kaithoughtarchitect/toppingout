// Topping Out Gaffer Brain:
// - Conversational LLM loop with read/stage tools ONLY (model cannot execute sends)
// - Deterministic code-enforced confirmation gate: explicit yes/no parsed in code on exact next turn
// - Server-generated verbatim read-back of staged target + sanitized message
// - Live target re-verification right before delivery
import { gafferEnv } from "./env.js";
import {
  OrcaClient,
  SessionDetails,
  SessionSummary,
  detectBlockedLeadingPrefix,
  resolveSessionStrict,
  sanitizeTerminalMessage,
} from "./orca.js";
import {
  SessionTopology,
  buildOwnerQueue,
  classifyTopology,
  discoverBoards,
  extractRepoRoots,
  parseJStatus,
  readActiveJobs,
} from "./toppingout.js";

export type ListenMode = "wake" | "always" | "manual";
export type ReplyStyle = "brief" | "speak";

export interface PendingConfirmation {
  sessionId: string;
  sessionTitle: string;
  terminalHandle: string;
  incarnationId: string | null;
  agent: string;
  message: string;
  stagedAtTurn: number;
  createdAt: number;
  expiresAt: number;
  maxExpiresAt: number;
  repeatCount: number;
}

export interface ChatMessage {
  role: "system" | "user" | "assistant" | "tool";
  content: string | null;
  tool_call_id?: string;
  tool_calls?: ToolCall[];
}

export interface ToolCall {
  id: string;
  type: "function";
  function: {
    name: string;
    arguments: string;
  };
}

export interface LlmResponse {
  content: string | null;
  tool_calls?: ToolCall[];
}

export interface LlmClient {
  chat(messages: ChatMessage[], tools?: unknown[]): Promise<LlmResponse>;
}

export interface TurnOutcome {
  ignored: boolean;
  reason?: string;
  replyText: string;
  activeSessionId: string | null;
  activeSessionTitle: string | null;
  pendingConfirmation: PendingConfirmation | null;
  followUpActive: boolean;
  sentDelivery?: { sessionTitle: string; message: string; ok: boolean; detail: string };
}

export interface AlertEvaluation {
  shouldAlert: boolean;
  spokenAlert: string;
  needsDecision: boolean;
}

export const CONFIRM_TTL_MS = 90_000;
export const CONFIRM_MAX_TTL_MS = 180_000;
export const CONFIRM_MAX_REPEATS = 2;
const FOLLOWUP_WINDOW_MS = 60_000;
const WAKE_REGEX =
  /\b(hey\s+gaffer|ok(?:ay)?\s+gaffer|gaffer|hey\s+orca|ok(?:ay)?\s+orca|orca|operator|radio)\b/i;
const WAKE_PREFIX_RE =
  /^(?:hey\s+gaffer|ok(?:ay)?\s+gaffer|gaffer|hey\s+orca|ok(?:ay)?\s+orca|orca|operator|radio)[\s,.:;-]*/i;

export const VOICE_SEND_PREFIX = "[voice] ";

const STANDALONE_GATED_ACT_RE =
  /^(?:(?:please|yes|yeah|ok|okay|go ahead and)\s+)*(?:merge(?:\s+(?:it|that|this|the\s+pr|pr))?|push(?:\s+(?:it|that|this|to\s+\S+))?|git\s+push|open(?:\s+(?:the\s+)?pr)|create(?:\s+(?:the\s+)?pr)|(?:run\s+(?:a\s+fourth\s+)?)?greploop|delete(?:\s+(?:the\s+)?(?:branch|worktree))|(?:run\s+)?migrations?|migrate)$/i;

export function isStandaloneGatedAct(cleanMessage: string): boolean {
  const norm = cleanMessage
    .trim()
    .toLowerCase()
    .replace(/[.,!?¡¿"']+/g, "")
    .replace(/\s+/g, " ")
    .trim();
  if (!norm) return false;
  return STANDALONE_GATED_ACT_RE.test(norm);
}

const EXPLICIT_YES_PHRASES = new Set([
  "yes",
  "yes please",
  "yes yes",
  "yes absolutely",
  "yes sure",
  "yeah",
  "yeah please",
  "yep",
  "yep go ahead",
  "yup",
  "si",
  "sí",
  "sure",
  "sure send it",
  "sure go ahead",
  "absolutely",
  "go for it",
  "confirm",
  "confirmed",
  "send",
  "send it",
  "send that",
  "yes send",
  "yes send it",
  "yes send that",
  "yes to send",
  "yes to send it",
  "yeah send it",
  "ok send",
  "okay send",
  "ok send it",
  "okay send it",
  "go ahead",
  "yes go ahead",
  "do it",
  "yes do it",
  "approve",
  "approved",
  "yes approve",
  "yes confirm",
  "affirmative",
]);

const EXPLICIT_NO_PHRASES = new Set([
  "no",
  "nope",
  "cancel",
  "cancel it",
  "cancel that",
  "stop",
  "abort",
  "never mind",
  "nevermind",
  "dont send",
  "don't send",
  "do not send",
  "discard",
  "hold on",
  "wait",
]);

const EXPLICIT_STANDBY_PHRASES = new Set([
  "stand by",
  "standby",
  "go to sleep",
  "sleep",
  "sleep now",
  "over",
  "over and out",
  "quiet",
  "stop listening",
  "that is all",
  "thats all",
  "that's all",
]);

const CONFIRM_NEGATION_RE =
  /\b(no|not|nope|cancel|stop|abort|wait|hold|change|instead|actually|but|dont|don't|never|discard|wrong|different|edit)\b/i;

export function parseConfirmationIntent(transcript: string): "yes" | "no" | "other" {
  const cleaned = transcript
    .trim()
    .toLowerCase()
    .replace(WAKE_PREFIX_RE, "")
    .replace(/[.,!?¡¿"']+/g, "")
    .replace(/\s+/g, " ")
    .trim();

  if (!cleaned) return "other";
  if (EXPLICIT_NO_PHRASES.has(cleaned)) return "no";
  if (EXPLICIT_YES_PHRASES.has(cleaned)) return "yes";

  // Allow stacked natural conversational wrappers around an unambiguous confirmation,
  // e.g. "Uh, so, yes, please, did you get that?", ONLY if zero negation, hesitation,
  // or edit words appear anywhere in the utterance.
  if (!CONFIRM_NEGATION_RE.test(cleaned)) {
    let unwrapped = cleaned;
    for (let i = 0; i < 4; i++) {
      const next = unwrapped
        .replace(/^(?:so|well|um+|uh+|alright|all right|okay|ok)\s+/i, "")
        .replace(
          /\s+(?:did you get that|you get that|got that|did you hear me|you hear me|please|thanks|thank you|for me)$/i,
          ""
        )
        .trim();
      if (next === unwrapped) break;
      unwrapped = next;
    }
    if (unwrapped && EXPLICIT_YES_PHRASES.has(unwrapped)) {
      return "yes";
    }
  }

  return "other";
}

const EXPLICIT_REPEAT_PHRASES = new Set([
  "repeat",
  "repeat that",
  "repeat please",
  "repeat that please",
  "say that again",
  "say again",
  "read it back",
  "read that back",
  "what",
  "what did you say",
  "what did you stage",
  "pardon",
  "sorry what",
]);

export function parseRepeatIntent(transcript: string): boolean {
  const cleaned = transcript
    .trim()
    .toLowerCase()
    .replace(WAKE_PREFIX_RE, "")
    .replace(/[.,!?¡¿"']+/g, "")
    .replace(/\s+/g, " ")
    .trim();
  return Boolean(cleaned) && EXPLICIT_REPEAT_PHRASES.has(cleaned);
}

const LEADING_STANDBY_RE = /^(?:stand\s*by|go\s+to\s+sleep|over\s+and\s+out)(?:\s|$)/i;

export function parseStandbyIntent(transcript: string): boolean {
  const cleaned = transcript
    .trim()
    .toLowerCase()
    .replace(WAKE_PREFIX_RE, "")
    .replace(/[.,!?¡¿"']+/g, "")
    .replace(/\s+/g, " ")
    .trim();

  if (!cleaned) return false;
  return EXPLICIT_STANDBY_PHRASES.has(cleaned) || LEADING_STANDBY_RE.test(cleaned);
}

function describeRuntimeStack(): { stt: string; brain: string; tts: string } {
  const openrouterKey = process.env.OPENROUTER_API_KEY;
  const openaiKey = process.env.OPENAI_API_KEY;
  const useOpenRouterBrain = Boolean(openrouterKey) && gafferEnv("LLM_PROVIDER") !== "openai";
  const brainModel =
    gafferEnv("LLM_MODEL") ||
    (useOpenRouterBrain ? "anthropic/claude-haiku-5.5" : "gpt-4.1-mini");
  const brain = `${brainModel} via ${useOpenRouterBrain ? "OpenRouter" : "OpenAI"}`;

  const sttPref = (gafferEnv("STT_PROVIDER") || "").trim().toLowerCase();
  const useOpenRouterStt =
    sttPref === "openrouter" || (sttPref !== "openai" && !openaiKey && Boolean(openrouterKey));
  const stt = useOpenRouterStt
    ? `${(gafferEnv("OR_STT_MODEL") || "openai/gpt-audio-mini").trim()} via OpenRouter`
    : `${(gafferEnv("STT_MODEL") || "gpt-4o-mini-transcribe").trim()} via OpenAI`;

  const voice = (process.env.SPEAK_GROK_VOICE || "leo").trim().toLowerCase();
  const tts = `xAI Grok Voice (x-ai/grok-voice-tts-1.0, voice ${voice}) via OpenRouter`;
  return { stt, brain, tts };
}

const SYSTEM_PROMPT = `You are Topping Out Gaffer, a hands-free spoken site agent for the owner's Topping Out work and live coding agent sessions in Orca.
The owner is listening through Bluetooth headphones while away from the desk, with no screen and no keyboard.

HOW TO SPEAK (STRICT):
- Talk like a sharp, natural colleague over coffee. Warm, direct, zero robotic phrasing.
- Output ONLY natural spoken sentences. NEVER use markdown, asterisks, bullet points, backticks, code blocks, file paths, git hashes, or session IDs.
- ACTUALLY ANSWER WHAT THE OWNER JUST ASKED. If they ask a conversational or meta question ("Did you hear me?", "What got cut off?", "Give me more detail"), answer THAT directly and NEVER robotically repeat the exact same summary you just gave on the previous turn.
- If the utterance looks cut off mid-sentence, briefly acknowledge what you caught and ask them to finish rather than guessing blindly.
- Never narrate your own tool calls ("One moment, I'll check that now"). Execute tools silently and speak the final result cleanly in one go.
- Keep normal updates tight: 1 to 3 short sentences (10 to 25 seconds spoken). If asked for more detail or a fuller summary, give a richer 3 to 5 sentence spoken walkthrough of ALL key points in the last reply, not just the last line.
- Name sessions cleanly by their short human title (e.g., "Head 1" or "landing builder"), never raw UUIDs or handles.

TOPPING OUT SITE KNOWLEDGE:
- You are Topping Out Gaffer, the Owner's Voice Desk for Topping Out (and you also see non-Topping-Out Orca sessions).
- Roles: a Foreman plans a job, checks disk evidence, and drives a Builder; a Builder (Pi, Claude, or agy in a split pane in the same tab) implements work orders; the Owner gives the word for gated acts and YOUR CALL cards.
- Every Foreman reply ends with an f-status block whose "owed:" line lists what waits on the owner. During an autonomous run or active Foreman turn, a managed Builder stopping between work orders is normal progress for the Foreman to review, NOT an owner decision. Never tell the owner to poke a managed Builder behind an active Foreman's back.
- Use read_board to inspect project boards (BOARD.json: head, standfirst, owed, next/running/blocked jobs) and list_owner_queue when asked what needs the owner's word across all Foremen and boards.

STRICT SAFETY RULE FOR SENDING TO SESSIONS:
- You have NO tool to send directly. ONLY call stage_reply(session_query, message) when the owner explicitly asks you to send, reply, tell, answer, or pass a message to a session. Never stage a reply for mic checks, casual remarks, or questions aimed at Gaffer itself.
- The server itself handles the verbatim read-back, routes managed-Builder replies safely to the owning Foreman (unless direct_to_builder=true was explicitly requested), and waits for the owner's spoken "yes" or "cancel" on the next turn.
- If a session name is ambiguous or not found, tell the owner the matching session titles and ask them to pick one.
- Never invent session status. Always call list_sessions, read_session, read_board, or list_owner_queue when asked about live state.
- Never describe what a session is doing internally or claim it is drafting/waiting on something specific unless you called read_session on that session first.
- When asked about a specific session or "what did it just say?" / "check again", ALWAYS call read_session fresh rather than relying on earlier chat history.`;

// NOTE: The LLM is intentionally given ONLY read/list/stage tools.
// Confirmation and terminal sending are executed purely in deterministic TypeScript code.
const TOOLS = [
  {
    type: "function",
    function: {
      name: "list_sessions",
      description:
        "List all live and recent Orca agent sessions with their titles, repos, state (working/done/waiting), Topping Out role (foreman/builder/standalone), paired Foreman/Builder, owed status, and whether they can receive replies.",
      parameters: { type: "object", properties: {}, additionalProperties: false },
    },
  },
  {
    type: "function",
    function: {
      name: "read_session",
      description:
        "Read the recent conversation transcript, live terminal screen, Topping Out f-status, paired Foreman/Builder status, and active job files for one Orca session.",
      parameters: {
        type: "object",
        properties: {
          session_query: {
            type: "string",
            description:
              "Session title, repo name, or 'active' for the currently focused session.",
          },
        },
        required: ["session_query"],
        additionalProperties: false,
      },
    },
  },
  {
    type: "function",
    function: {
      name: "read_board",
      description:
        "Read Topping Out project boards (BOARD.json) discovered from live Orca session repos: head outcome, standfirst, owed items, running/next/blocked jobs, and open owner decisions.",
      parameters: {
        type: "object",
        properties: {
          repo_query: {
            type: "string",
            description: "Optional repo or board slug filter; omit to read all discovered boards.",
          },
        },
        additionalProperties: false,
      },
    },
  },
  {
    type: "function",
    function: {
      name: "list_owner_queue",
      description:
        "List every item currently waiting on the owner's word across all live Foremen (owed: / YOUR CALL) and all Topping Out project boards (BOARD.json owed and unresolved decision jobs).",
      parameters: { type: "object", properties: {}, additionalProperties: false },
    },
  },
  {
    type: "function",
    function: {
      name: "stage_reply",
      description:
        "Stage a plain-text reply for a live, writable Orca agent session. Does NOT send: the server immediately reads the exact target and message back to the owner and waits for an explicit 'yes'. If targeting a managed Builder whose Foreman is live, the server routes safely to the owning Foreman unless direct_to_builder is true.",
      parameters: {
        type: "object",
        properties: {
          session_query: {
            type: "string",
            description: "Unambiguous session title, repo name, or 'active' for the current session.",
          },
          message: {
            type: "string",
            description: "The exact single-line plain text instruction to type into the agent session.",
          },
          direct_to_builder: {
            type: "boolean",
            description:
              "Set true ONLY when the owner explicitly asks to bypass the Foreman and type directly into the managed Builder pane.",
          },
        },
        required: ["session_query", "message"],
        additionalProperties: false,
      },
    },
  },
];

export function stripMarkdownForSpeech(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/^#+\s+/gm, "")
    .replace(/^[-*•]\s+/gm, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function createDefaultLlmClient(): LlmClient {
  const openrouterKey = process.env.OPENROUTER_API_KEY;
  const openaiKey = process.env.OPENAI_API_KEY;

  if (!openrouterKey && !openaiKey) {
    throw new Error("Neither OPENROUTER_API_KEY nor OPENAI_API_KEY is set.");
  }

  const useOpenRouter = Boolean(openrouterKey) && gafferEnv("LLM_PROVIDER") !== "openai";
  const endpoint = useOpenRouter
    ? "https://openrouter.ai/api/v1/chat/completions"
    : "https://api.openai.com/v1/chat/completions";
  const apiKey = useOpenRouter ? openrouterKey! : openaiKey!;
  const model =
    gafferEnv("LLM_MODEL") ||
    (useOpenRouter ? "anthropic/claude-haiku-5.5" : "gpt-4.1-mini");

  return {
    async chat(messages: ChatMessage[], tools?: unknown[]): Promise<LlmResponse> {
      const body: Record<string, unknown> = {
        model,
        messages,
        temperature: 0.25,
      };
      if (tools && tools.length > 0) {
        body.tools = tools;
        body.tool_choice = "auto";
      }

      const res = await fetch(endpoint, {
        method: "POST",
        signal: AbortSignal.timeout(25_000),
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${apiKey}`,
        },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const errText = await res.text().catch(() => "");
        throw new Error(`LLM request failed (${res.status}): ${errText.slice(0, 300)}`);
      }

      const data = (await res.json()) as {
        choices?: Array<{
          message?: {
            content?: string | null;
            tool_calls?: ToolCall[];
          };
        }>;
      };
      const msg = data.choices?.[0]?.message;
      return {
        content: msg?.content ?? null,
        tool_calls: msg?.tool_calls,
      };
    },
  };
}

export class VoiceBrain {
  private orca: OrcaClient;
  private llm: LlmClient;
  private nowFn: () => number;
  private history: ChatMessage[] = [];
  private turnCounter = 0;
  private activeSessionId: string | null = null;
  private activeSessionTitle: string | null = null;
  private pendingConfirmation: PendingConfirmation | null = null;
  private followUpUntil = 0;
  private replyStyle: ReplyStyle =
    gafferEnv("STYLE") === "speak" ? "speak" : "brief";

  constructor(orca: OrcaClient, llm?: LlmClient, nowFn: () => number = () => Date.now()) {
    this.orca = orca;
    this.llm = llm ?? createDefaultLlmClient();
    this.nowFn = nowFn;
  }

  getReplyStyle(): ReplyStyle {
    return this.replyStyle;
  }

  setReplyStyle(style: ReplyStyle): void {
    this.replyStyle = style;
  }

  getState() {
    this.pruneExpiredPending();
    return {
      activeSessionId: this.activeSessionId,
      activeSessionTitle: this.activeSessionTitle,
      pendingConfirmation: this.pendingConfirmation,
      followUpActive: this.nowFn() < this.followUpUntil,
      turnCounter: this.turnCounter,
      replyStyle: this.replyStyle,
    };
  }

  hasPendingConfirmation(): boolean {
    this.pruneExpiredPending();
    return Boolean(this.pendingConfirmation);
  }

  cancelPendingConfirmation(): PendingConfirmation | null {
    const prev = this.pendingConfirmation;
    this.pendingConfirmation = null;
    return prev;
  }

  private pruneExpiredPending(): boolean {
    const now = this.nowFn();
    if (
      this.pendingConfirmation &&
      (now > this.pendingConfirmation.expiresAt || now > this.pendingConfirmation.maxExpiresAt)
    ) {
      this.pendingConfirmation = null;
      return true;
    }
    return false;
  }

  /**
   * Called by the unprompted watcher when it speaks an alert.
   * Any pending staged reply is IMMEDIATELY CANCELLED so saying "yes" to a new alert
   * can never fire a previously staged reply for another pane.
   */
  recordProactiveAlert(session: SessionSummary, spokenAlert: string): { cancelledPendingTitle: string | null } {
    let cancelledPendingTitle: string | null = null;
    if (this.pendingConfirmation) {
      cancelledPendingTitle = this.pendingConfirmation.sessionTitle;
      this.pendingConfirmation = null;
    }
    this.activeSessionId = session.id;
    this.activeSessionTitle = session.title;
    this.followUpUntil = this.nowFn() + FOLLOWUP_WINDOW_MS;
    const note = cancelledPendingTitle
      ? `[Unprompted alert about "${session.title}" (previous staged reply for "${cancelledPendingTitle}" was cancelled)]: ${spokenAlert}`
      : `[Unprompted alert about "${session.title}"]: ${spokenAlert}`;
    this.history.push({ role: "assistant", content: note });
    this.trimHistory();
    return { cancelledPendingTitle };
  }

  shouldAcceptUtterance(
    transcript: string,
    mode: ListenMode
  ): { accept: boolean; cleaned: string; reason?: string } {
    const text = transcript.trim();
    if (!text) return { accept: false, cleaned: "", reason: "empty" };

    if (mode === "always" || mode === "manual") {
      return { accept: true, cleaned: text };
    }

    const now = this.nowFn();
    const hasPending = Boolean(this.pendingConfirmation) && now <= this.pendingConfirmation!.expiresAt;
    if (hasPending) {
      return { accept: true, cleaned: text };
    }

    if (WAKE_REGEX.test(text)) {
      const stripped = text.replace(WAKE_REGEX, "").replace(/^[\s,.:;-]+/, "").trim();
      return { accept: true, cleaned: stripped || "Give me a quick status check." };
    }

    if (now < this.followUpUntil) {
      // Allow explicit standby commands ("standby", "over") as 1 word; otherwise require 2+ words
      // in the 60s follow-up window so stray backchannels never trigger LLM calls or extend the window.
      if (parseStandbyIntent(text)) {
        return { accept: true, cleaned: text };
      }
      const words = text
        .replace(/[^a-z0-9\s'-]+/gi, " ")
        .trim()
        .split(/\s+/)
        .filter(Boolean);
      if (words.length >= 2) {
        return { accept: true, cleaned: text };
      }
      return { accept: false, cleaned: "", reason: "follow-up requires 2+ words" };
    }

    return { accept: false, cleaned: "", reason: "no wake word" };
  }

  async handleUserUtterance(
    transcript: string,
    mode: ListenMode = "always"
  ): Promise<TurnOutcome> {
    const hadPendingBeforePrune = this.pendingConfirmation;
    const expiredJustNow = this.pruneExpiredPending();

    // If a staged reply JUST expired and the owner says "yes" (even in wake mode),
    // always surface the honest expiry refusal rather than dropping a 1-word "yes" silently.
    if (expiredJustNow && hadPendingBeforePrune && parseConfirmationIntent(transcript) === "yes") {
      this.turnCounter += 1;
      const reply = `That staged reply for ${hadPendingBeforePrune.sessionTitle} expired, so nothing was sent. Tell me again if you still want to send it.`;
      this.history.push({ role: "user", content: transcript.trim() }, { role: "assistant", content: reply });
      this.trimHistory();
      this.followUpUntil = this.nowFn() + FOLLOWUP_WINDOW_MS;
      return {
        ignored: false,
        replyText: reply,
        activeSessionId: this.activeSessionId,
        activeSessionTitle: this.activeSessionTitle,
        pendingConfirmation: null,
        followUpActive: true,
      };
    }

    const gate = this.shouldAcceptUtterance(transcript, mode);
    if (!gate.accept) {
      return {
        ignored: true,
        reason: gate.reason,
        replyText: "",
        activeSessionId: this.activeSessionId,
        activeSessionTitle: this.activeSessionTitle,
        pendingConfirmation: this.pendingConfirmation,
        followUpActive: this.nowFn() < this.followUpUntil,
      };
    }

    this.turnCounter += 1;
    const currentTurn = this.turnCounter;

    // If the staged reply expired right before the owner said "yes", tell them honestly and refuse.
    if (expiredJustNow && hadPendingBeforePrune && parseConfirmationIntent(gate.cleaned) === "yes") {
      const reply = `That staged reply for ${hadPendingBeforePrune.sessionTitle} expired after 90 seconds, so nothing was sent. Tell me again if you still want to send it.`;
      this.history.push({ role: "user", content: gate.cleaned }, { role: "assistant", content: reply });
      this.trimHistory();
      this.followUpUntil = this.nowFn() + FOLLOWUP_WINDOW_MS;
      return {
        ignored: false,
        replyText: reply,
        activeSessionId: this.activeSessionId,
        activeSessionTitle: this.activeSessionTitle,
        pendingConfirmation: null,
        followUpActive: true,
      };
    }

    // DETERMINISTIC SAFETY GATE: when a reply is staged, handle yes/no/unclear purely in code
    // (never passes an unclear answer into the LLM so it can never re-stage behind the owner's back).
    if (this.pendingConfirmation) {
      const pending = this.pendingConfirmation;
      const isExactNextTurn = currentTurn === pending.stagedAtTurn + 1;
      const intent = parseConfirmationIntent(gate.cleaned);

      if (intent === "yes" && isExactNextTurn) {
        this.pendingConfirmation = null;
        // Re-verify live terminal target right before sending (refuses exited agent / bare shell)
        const check = await this.orca.verifyTerminalTarget(
          pending.terminalHandle,
          pending.incarnationId,
          pending.agent
        );
        if (!check.ok) {
          const reply = `Refused to send to ${pending.sessionTitle}: ${check.reason || "the agent is no longer active in that pane."}`;
          this.history.push({ role: "user", content: gate.cleaned }, { role: "assistant", content: reply });
          this.trimHistory();
          this.followUpUntil = this.nowFn() + FOLLOWUP_WINDOW_MS;
          return {
            ignored: false,
            replyText: reply,
            activeSessionId: this.activeSessionId,
            activeSessionTitle: this.activeSessionTitle,
            pendingConfirmation: null,
            followUpActive: true,
            sentDelivery: {
              sessionTitle: pending.sessionTitle,
              message: pending.message,
              ok: false,
              detail: check.reason || "Target verification failed.",
            },
          };
        }

        // Prefix every voice-relayed message with "[voice] " so receiving agents distinguish it from typed input.
        const prefixed = pending.message.startsWith(VOICE_SEND_PREFIX)
          ? pending.message
          : `${VOICE_SEND_PREFIX}${pending.message}`;
        const result = await this.orca.sendToTerminal(pending.terminalHandle, prefixed);
        const reply = !result.ok
          ? `Failed to send to ${pending.sessionTitle}: ${result.detail}`
          : result.turnStarted
            ? `Sent to ${pending.sessionTitle}: "${pending.message}".`
            : `Sent to ${pending.sessionTitle}: "${pending.message}". Accepted, turn not started.`;
        this.history.push({ role: "user", content: gate.cleaned }, { role: "assistant", content: reply });
        this.trimHistory();
        this.followUpUntil = this.nowFn() + FOLLOWUP_WINDOW_MS;
        return {
          ignored: false,
          replyText: reply,
          activeSessionId: this.activeSessionId,
          activeSessionTitle: this.activeSessionTitle,
          pendingConfirmation: null,
          followUpActive: true,
          sentDelivery: {
            sessionTitle: pending.sessionTitle,
            message: prefixed,
            ok: result.ok,
            detail: result.detail,
          },
        };
      }

      if (intent === "no") {
        this.pendingConfirmation = null;
        const reply = `Cancelled. Nothing was sent to ${pending.sessionTitle}.`;
        this.history.push({ role: "user", content: gate.cleaned }, { role: "assistant", content: reply });
        this.trimHistory();
        this.followUpUntil = this.nowFn() + FOLLOWUP_WINDOW_MS;
        return {
          ignored: false,
          replyText: reply,
          activeSessionId: this.activeSessionId,
          activeSessionTitle: this.activeSessionTitle,
          pendingConfirmation: null,
          followUpActive: true,
        };
      }

      if (parseStandbyIntent(gate.cleaned)) {
        this.pendingConfirmation = null;
        this.followUpUntil = 0;
        const reply = `Cancelled the staged reply for ${pending.sessionTitle} and standing by. Say Gaffer or Orca when you need me.`;
        this.history.push({ role: "user", content: gate.cleaned }, { role: "assistant", content: reply });
        this.trimHistory();
        return {
          ignored: false,
          replyText: reply,
          activeSessionId: this.activeSessionId,
          activeSessionTitle: this.activeSessionTitle,
          pendingConfirmation: null,
          followUpActive: false,
        };
      }

      if (parseRepeatIntent(gate.cleaned)) {
        // Re-read verbatim without cancelling, capped strictly by CONFIRM_MAX_TTL_MS and CONFIRM_MAX_REPEATS.
        pending.stagedAtTurn = currentTurn;
        const now = this.nowFn();
        let reply: string;
        if (pending.repeatCount >= CONFIRM_MAX_REPEATS || now >= pending.maxExpiresAt) {
          reply = `Final repeat for ${pending.sessionTitle}. Exact message: "${pending.message}". Say yes, or cancel.`;
        } else {
          pending.repeatCount += 1;
          pending.expiresAt = Math.min(now + CONFIRM_TTL_MS, pending.maxExpiresAt);
          reply = `Repeating: staged for ${pending.sessionTitle}. Exact message: "${pending.message}". Say yes, or cancel.`;
        }
        this.history.push({ role: "user", content: gate.cleaned }, { role: "assistant", content: reply });
        this.trimHistory();
        this.followUpUntil = now + FOLLOWUP_WINDOW_MS;
        return {
          ignored: false,
          replyText: reply,
          activeSessionId: this.activeSessionId,
          activeSessionTitle: this.activeSessionTitle,
          pendingConfirmation: this.pendingConfirmation,
          followUpActive: true,
        };
      }

      // Unclear answer: keep the staged draft alive (bounded by original 90s expiresAt),
      // ask explicitly for yes or cancel, and NEVER invoke the LLM to re-stage.
      pending.stagedAtTurn = currentTurn;
      const reply = `Say yes or cancel for ${pending.sessionTitle}. Exact message: "${pending.message}".`;
      this.history.push({ role: "user", content: gate.cleaned }, { role: "assistant", content: reply });
      this.trimHistory();
      this.followUpUntil = this.nowFn() + FOLLOWUP_WINDOW_MS;
      return {
        ignored: false,
        replyText: reply,
        activeSessionId: this.activeSessionId,
        activeSessionTitle: this.activeSessionTitle,
        pendingConfirmation: this.pendingConfirmation,
        followUpActive: true,
      };
    } else if (parseStandbyIntent(gate.cleaned)) {
      this.followUpUntil = 0;
      const reply = "Standing by. Say Gaffer or Orca when you need me.";
      this.history.push({ role: "user", content: gate.cleaned }, { role: "assistant", content: reply });
      this.trimHistory();
      return {
        ignored: false,
        replyText: reply,
        activeSessionId: this.activeSessionId,
        activeSessionTitle: this.activeSessionTitle,
        pendingConfirmation: null,
        followUpActive: false,
      };
    }

    const cancelledNotice = "";

    const styleDirective =
      this.replyStyle === "speak"
        ? `REPLY LENGTH & STYLE (/speak mode is ON): Give a warm, rich spoken explainer like a sharp colleague over coffee (30 to 60 seconds, roughly 80 to 180 words). Explain the gist AND the why of all key points from the session's last reply in smooth natural sentences, without reading verbatim, dropping jargon or defining it in a few words, with zero markdown/bullets/paths/SHAs.`
        : `REPLY LENGTH & STYLE (Brief mode): Keep answers tight: 1 to 3 short spoken sentences (10 to 20 seconds) hitting only the headline and what is needed from the owner, unless they explicitly ask for more detail.`;

    const ownerName = (gafferEnv("OWNER_NAME") || "").trim();
    const stack = describeRuntimeStack();
    const followUpSec = Math.round(FOLLOWUP_WINDOW_MS / 1000);
    const selfFacts = `GAFFER SELF-FACTS (never guess or invent models or timers): Listen mode is "${mode}". Wake words are "Gaffer", "Hey Gaffer", "Orca", "Radio", or "Operator". After each reply or alert, a ${followUpSec}-second follow-up window stays open, and saying "stand by", "over", or "go to sleep" closes it immediately. This voice agent runs STT on ${stack.stt}, Brain on ${stack.brain}, and TTS on ${stack.tts}. Coding agents inside Orca run their own separate models; never guess a coding agent's model name unless it is explicitly shown in read_session output.`;
    const stateContext = [
      ownerName ? `Owner name: ${ownerName}.` : "",
      selfFacts,
      this.activeSessionTitle
        ? `Current active session: "${this.activeSessionTitle}" (id: ${this.activeSessionId}).`
        : "No active session selected yet.",
      cancelledNotice
        ? `IMPORTANT: ${cancelledNotice.trim()} NOTHING WAS SENT and there is NO active staged draft anymore. Never claim anything was sent, and NEVER tell the owner to "say yes" unless you call stage_reply in this turn to stage a fresh draft.`
        : "No pending reply staged.",
      styleDirective,
    ]
      .filter(Boolean)
      .join(" ");

    const userMsg: ChatMessage = { role: "user", content: gate.cleaned };
    const workingMessages: ChatMessage[] = [
      { role: "system", content: `${SYSTEM_PROMPT}\n\nRUNTIME CONTEXT: ${stateContext}` },
      ...this.history,
      userMsg,
    ];

    let finalReply = "";
    let serverStagedReadback: string | null = null;

    for (let step = 0; step < 6; step++) {
      const resp = await this.llm.chat(workingMessages, TOOLS);
      const toolCalls = resp.tool_calls ?? [];

      if (toolCalls.length === 0) {
        finalReply = stripMarkdownForSpeech(resp.content || "Done.");
        break;
      }

      workingMessages.push({
        role: "assistant",
        content: resp.content,
        tool_calls: toolCalls,
      });

      for (const tc of toolCalls) {
        let args: Record<string, unknown> = {};
        try {
          args = tc.function.arguments ? JSON.parse(tc.function.arguments) : {};
        } catch {
          args = {};
        }

        const toolOutput = await this.executeTool(tc.function.name, args, currentTurn, (readback) => {
          serverStagedReadback = readback;
        });

        workingMessages.push({
          role: "tool",
          tool_call_id: tc.id,
          content: JSON.stringify(toolOutput),
        });

        // Stop immediately on successful stage_reply so the SERVER speaks the verbatim read-back!
        if (serverStagedReadback) break;
      }

      if (serverStagedReadback) {
        finalReply = serverStagedReadback;
        break;
      }
    }

    if (!finalReply) {
      finalReply = "Sorry, I couldn't finish checking Orca just now. Try asking again.";
    }

    const fullReply = cancelledNotice ? `${cancelledNotice}${finalReply}` : finalReply;

    // Commit user + assistant pair together only after the turn finishes cleanly.
    this.history.push(userMsg, { role: "assistant", content: fullReply });
    this.trimHistory();
    this.followUpUntil = this.nowFn() + FOLLOWUP_WINDOW_MS;

    return {
      ignored: false,
      replyText: fullReply,
      activeSessionId: this.activeSessionId,
      activeSessionTitle: this.activeSessionTitle,
      pendingConfirmation: this.pendingConfirmation,
      followUpActive: true,
    };
  }

  private async executeTool(
    name: string,
    args: Record<string, unknown>,
    currentTurn: number,
    onStagedReadback: (readback: string) => void
  ): Promise<unknown> {
    if (name === "list_sessions") {
      const sessions = await this.orca.listSessions();
      const topology = classifyTopology(sessions);
      return {
        count: sessions.length,
        sessions: sessions.slice(0, 15).map((s) => {
          const topo = topology.get(s.id);
          return {
            id: s.id,
            title: s.title,
            repo: s.repo,
            branch: s.branch,
            agent: s.agent,
            state: s.state,
            writable: s.writable,
            connected: s.connected,
            hostId: s.hostId,
            role: topo?.role ?? "standalone",
            pairedWith: topo?.pairedForemanTitle ?? topo?.pairedBuilderTitle ?? null,
            owed: topo?.jStatus?.hasRealOwed ? topo.jStatus.owed || "YOUR CALL" : null,
            hasYourCall: Boolean(topo?.jStatus?.hasYourCall),
          };
        }),
      };
    }

    if (name === "read_board") {
      const sessions = await this.orca.listSessions();
      const repoRoots = extractRepoRoots(sessions);
      const allBoards = discoverBoards(repoRoots);
      const q = String(args.repo_query || "").trim().toLowerCase();
      const filtered = q
        ? allBoards.filter(
            (b) =>
              b.slug.toLowerCase().includes(q) ||
              b.title.toLowerCase().includes(q) ||
              b.repoName.toLowerCase().includes(q)
          )
        : allBoards.filter((b) => !b.toppedOut);
      return {
        ok: true,
        count: filtered.length,
        archivedCount: allBoards.filter((b) => b.toppedOut).length,
        boards: filtered.map((b) => ({
          repo: b.repoName,
          slug: b.slug,
          title: b.title,
          updated: b.updated,
          toppedOut: b.toppedOut,
          next: b.nextLabel,
          nextByLane: b.nextByLane,
          nextJobIds: b.nextJobIds,
          headOutcome: b.headOutcome,
          standfirst: b.standfirst,
          counts: b.counts,
          owed: b.owed.slice(0, 8),
          alerts: b.alerts.slice(0, 5),
          runningJobs: b.runningJobs.slice(0, 5),
          nextJobs: b.nextJobs.slice(0, 5),
          openDecisions: b.openDecisions.slice(0, 5),
        })),
      };
    }

    if (name === "list_owner_queue") {
      const sessions = await this.orca.listSessions();
      const topology = classifyTopology(sessions);
      const boards = discoverBoards(extractRepoRoots(sessions));
      const queue = buildOwnerQueue(sessions, topology, boards);
      return {
        ok: true,
        count: queue.length,
        items: queue.slice(0, 20),
      };
    }

    if (name === "read_session") {
      const sessions = await this.orca.listSessions();
      const topology = classifyTopology(sessions);
      const query = String(args.session_query || "active");
      const res = resolveSessionStrict(sessions, query, this.activeSessionId, {
        allowFallbackLatest: true,
      });
      if (res.status === "ambiguous") {
        return {
          ok: false,
          ambiguous: true,
          error: `Multiple sessions matched "${query}": ${res.candidates
            .map((s) => s.title)
            .join(", ")}. Ask the owner which one they mean.`,
        };
      }
      if (res.status === "not_found") {
        return {
          ok: false,
          error: `${res.reason} Available titles: ${sessions
            .slice(0, 8)
            .map((s) => s.title)
            .join(", ")}`,
        };
      }

      const target = res.session;
      this.activeSessionId = target.id;
      this.activeSessionTitle = target.title;
      const details = await this.orca.readSession(target, 12);
      const topo = topology.get(target.id);
      const lastAssistant =
        [...details.recentMessages].reverse().find((m) => m.role === "assistant")?.text || "";
      const jStatus = parseJStatus(lastAssistant || details.screenTail) ?? topo?.jStatus ?? null;

      const pairedId = topo?.pairedForemanId ?? topo?.pairedBuilderId ?? null;
      const pairedRaw = pairedId ? sessions.find((s) => s.id === pairedId) : undefined;
      const pairedSession = pairedRaw
        ? {
            role: topo?.pairedForemanId ? "foreman" : "builder",
            title: pairedRaw.title,
            agent: pairedRaw.agent,
            state: pairedRaw.state,
            writable: pairedRaw.writable,
            preview: pairedRaw.preview.slice(-400),
          }
        : null;

      const activeJobs = target.worktreePath ? readActiveJobs(target.worktreePath, 3) : [];

      return {
        ok: true,
        title: target.title,
        repo: target.repo,
        branch: target.branch,
        agent: target.agent,
        state: details.transcriptState || target.state,
        writable: target.writable,
        role: topo?.role ?? "standalone",
        jStatus,
        pairedSession,
        activeJobs,
        recentMessages: details.recentMessages,
        screenTail: details.screenTail.slice(-3600),
        readErrors: details.readErrors,
      };
    }

    if (name === "stage_reply") {
      const sessions = await this.orca.listSessions();
      const topology = classifyTopology(sessions);
      const query = String(args.session_query || "active");
      const directToBuilder = args.direct_to_builder === true;
      const message = sanitizeTerminalMessage(String(args.message || ""));
      if (!message) {
        return { ok: false, error: "Message text cannot be empty." };
      }

      // Refuse leading /, !, # (terminal/agent slash or shell commands) and spell out the blocked char.
      const blockedPrefix = detectBlockedLeadingPrefix(message);
      if (blockedPrefix) {
        return {
          ok: false,
          refused: true,
          error: `Refused to stage: messages cannot start with ${blockedPrefix} because coding agents run slash and bang prefixes as commands. Rephrase without the leading ${blockedPrefix}.`,
        };
      }

      // Refuse standalone gated acts (merge, push, open the PR, greploop, migrations) until RULES.md decides voice authority.
      if (isStandaloneGatedAct(message)) {
        return {
          ok: false,
          refused: true,
          error: `Refused to stage "${message}": gated acts like merge, push, open the PR, and greploop must be typed directly by the owner.`,
        };
      }

      // STRICT unambiguous match preferring live writable sessions: never falls back to newest session on unknown active!
      const res = resolveSessionStrict(sessions, query, this.activeSessionId, {
        allowFallbackLatest: false,
        preferWritable: true,
      });
      if (res.status === "ambiguous") {
        return {
          ok: false,
          ambiguous: true,
          error: `Multiple sessions matched "${query}": ${res.candidates
            .map((s) => s.title)
            .join(", ")}. Ask the owner to name the exact session before staging.`,
        };
      }
      if (res.status === "not_found") {
        return {
          ok: false,
          error: `${res.reason} Available sessions: ${sessions
            .slice(0, 8)
            .map((s) => s.title)
            .join(", ")}`,
        };
      }

      let target = res.session;
      let routedFromBuilderTitle: string | null = null;

      // Layer 2 Foreman-safe routing: if targeting a managed Builder whose owning Foreman is live & writable,
      // route to the Foreman by default so voice never pokes a managed Builder behind its Foreman's back.
      const targetTopo = topology.get(target.id);
      if (targetTopo?.role === "builder" && targetTopo.pairedForemanId && !directToBuilder) {
        const foreman = sessions.find((s) => s.id === targetTopo.pairedForemanId);
        if (foreman && foreman.writable && foreman.terminalHandle) {
          routedFromBuilderTitle = target.title;
          target = foreman;
        }
      }

      if (!target.writable || !target.terminalHandle) {
        return {
          ok: false,
          error: `Session "${target.title}" does not have a live writable agent terminal right now (kind=${target.kind}, connected=${target.connected}).`,
        };
      }

      // When routed from a managed Builder to its owning Foreman, explicitly label the payload
      // "(for builder <title>)" in BOTH the sent text and verbatim read-back so a Foreman with
      // its own YOUR CALL waiting can never mistake it for an answer to the Foreman's own gate.
      const stagedMessage = routedFromBuilderTitle
        ? `(for builder ${routedFromBuilderTitle}) ${message}`
        : message;

      const now = this.nowFn();
      this.activeSessionId = target.id;
      this.activeSessionTitle = target.title;
      this.pendingConfirmation = {
        sessionId: target.id,
        sessionTitle: target.title,
        terminalHandle: target.terminalHandle,
        incarnationId: target.incarnationId,
        agent: target.agent,
        message: stagedMessage,
        stagedAtTurn: currentTurn,
        createdAt: now,
        expiresAt: now + CONFIRM_TTL_MS,
        maxExpiresAt: now + CONFIRM_MAX_TTL_MS,
        repeatCount: 0,
      };

      // Server writes the exact spoken read-back verbatim (never paraphrased by the LLM).
      const readback = routedFromBuilderTitle
        ? `Routing to Foreman ${target.title}. Exact message: "${stagedMessage}". Say yes, or cancel.`
        : `Staged for ${target.title}. Exact message: "${stagedMessage}". Say yes, or cancel.`;
      onStagedReadback(readback);

      return {
        ok: true,
        staged: true,
        routedToForeman: Boolean(routedFromBuilderTitle),
        sessionTitle: target.title,
        message: stagedMessage,
      };
    }

    return { ok: false, error: `Unknown tool: ${name}` };
  }

  /**
   * Decide whether a stopped session merits speaking up unprompted into headphones,
   * and craft a crisp spoken alert if so.
   */
  async evaluateAlert(
    details: SessionDetails,
    notifyOnAllStops = false,
    topology?: SessionTopology | null
  ): Promise<AlertEvaluation> {
    const lastMsgs = details.recentMessages
      .slice(-3)
      .map((m) => `${m.role}: ${m.text}`)
      .join("\n\n");
    const lastAssistant =
      [...details.recentMessages].reverse().find((m) => m.role === "assistant")?.text || "";
    const parsedStatus = parseJStatus(lastAssistant || details.screenTail) ?? topology?.jStatus ?? null;
    const roleLine = topology
      ? `Topping Out role: ${topology.role}${topology.pairedForemanTitle ? ` (managed by Foreman "${topology.pairedForemanTitle}")` : topology.pairedBuilderTitle ? ` (manages Builder "${topology.pairedBuilderTitle}")` : ""}.`
      : "";
    const statusLine = parsedStatus
      ? `Parsed f-status: where="${parsedStatus.where}" | owed="${parsedStatus.owed || "none"}" | hasYourCall=${parsedStatus.hasYourCall} | hasRealOwed=${parsedStatus.hasRealOwed}.`
      : "";

    const prompt = [
      `An Orca session named "${details.session.title}" (repo: ${details.session.repo}, state: ${details.transcriptState || details.session.state}) just stopped or changed state.`,
      roleLine,
      statusLine,
      "",
      "RECENT MESSAGES:",
      lastMsgs || "(none)",
      "",
      "LIVE SCREEN TAIL:",
      details.screenTail.slice(-1400) || "(none)",
      "",
      `Decide if the owner needs to hear about this right now in their headphones.`,
      `needsDecision = true if the agent is asking a question, waiting on permission/approval/merge/PR, blocked, hit an error, has a non-empty "owed:" item or YOUR CALL card, or says it is waiting for their next brief.`,
      parsedStatus?.hasRealOwed
        ? `This Foreman has a real owed/YOUR CALL item waiting on the owner, so set shouldAlert=true and needsDecision=true, and state the exact decision clearly.`
        : notifyOnAllStops
          ? `notifyOnAllStops is ON, so set shouldAlert=true unless this looks like empty noise.`
          : `Set shouldAlert=true ONLY when needsDecision is true or the task completed a meaningful milestone the owner should know about.`,
      this.replyStyle === "speak"
        ? `Write spokenAlert in /speak explainer style: 3 to 6 warm, natural, conversational sentences (25 to 55 seconds, 70 to 160 words) like a sharp colleague explaining over coffee. Start with the session title, explain the gist and the why of what it just finished or found, drop jargon, zero markdown/file paths/hashes, and end clearly with what (if anything) it needs from the owner.`
        : `Write spokenAlert as 1 to 2 tight, warm, plain-English spoken sentences (NO markdown, NO file paths, NO hashes). Start with the session title, e.g. "Head 1 just stopped. It finished the tests and is waiting on your word to merge. What do you want to do?"`,
      `Respond with strict JSON only: {"shouldAlert": boolean, "needsDecision": boolean, "spokenAlert": string}`,
    ].join("\n");

    const resp = await this.llm.chat(
      [
        {
          role: "system",
          content: "You evaluate coding-agent stops for spoken alerts. Output valid JSON only.",
        },
        { role: "user", content: prompt },
      ],
      []
    );

    const raw = (resp.content || "").trim();
    const jsonMatch = raw.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      return {
        shouldAlert: notifyOnAllStops,
        needsDecision: false,
        spokenAlert: `${details.session.title} just stopped. Want me to check what it says?`,
      };
    }

    try {
      const parsed = JSON.parse(jsonMatch[0]) as Partial<AlertEvaluation>;
      return {
        shouldAlert: Boolean(parsed.shouldAlert),
        needsDecision: Boolean(parsed.needsDecision),
        spokenAlert: stripMarkdownForSpeech(
          parsed.spokenAlert || `${details.session.title} just paused and may need your word.`
        ),
      };
    } catch {
      return {
        shouldAlert: notifyOnAllStops,
        needsDecision: false,
        spokenAlert: `${details.session.title} just stopped. Want a quick summary?`,
      };
    }
  }

  private trimHistory(): void {
    if (this.history.length > 16) {
      this.history = this.history.slice(-16);
    }
  }
}

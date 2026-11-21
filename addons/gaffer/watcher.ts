// Unprompted Stop Watcher:
// - Polls Orca (2.5s default) ONLY while alerts are enabled and an audio-ready listener is connected
// - Topping Out aware: suppresses routine managed-Builder work-order stops while its paired Foreman
//   is working (still alerts on interactive trust/permission prompts or Foreman owed/YOUR CALL stops)
// - Deduplicates by turn key (timestamp + message/screen signature), retries on read/LLM/TTS errors,
//   ignores state "unknown", and holds alerts while a voice reply is staged for confirmation
import { watch as fsWatch, existsSync, FSWatcher } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { OrcaClient, SessionSummary } from "./orca.js";
import { VoiceBrain } from "./brain.js";
import { classifyTopology, parseJStatus } from "./toppingout.js";
import { gafferEnv } from "./env.js";

export interface WatchAlert {
  id: string;
  sessionId: string;
  sessionTitle: string;
  spokenText: string;
  needsDecision: boolean;
  timestamp: number;
}

export interface WatcherOptions {
  pollMs?: number;
  cooldownMs?: number;
  notifyOnAllStops?: boolean;
  managedBuilderAlerts?: boolean;
  onAlert: (alert: WatchAlert) => Promise<void> | void;
  onQuietBuilderStop?: (info: { builderTitle: string; foremanTitle: string }) => void;
  onError?: (err: unknown) => void;
  serialize?: <T>(fn: () => Promise<T>) => Promise<T>;
  hasListener?: () => boolean;
  nowFn?: () => number;
}

// Strict mid-turn permission / trust prompt cues (covers Pi, Claude Code, and agy wording)
const LIVE_PROMPT_CUE_RE =
  /(allow once|always allow|do you want to proceed|trust (?:the files in )?this folder|do you trust the (?:files|contents)|approve this tool|requires your approval)/i;

const FOREMAN_GRACE_MS = 20_000;

export interface TrackedSession {
  state: string;
  updatedAt: number;
  previewHash: string;
  lastAlertedAt: number;
  lastAlertedTurnKey: string;
  lastWorkingAt: number;
}

export function detectTransition(
  prev: TrackedSession | undefined,
  curr: SessionSummary,
  now: number,
  cooldownMs: number
): { triggered: boolean; kind: "stop" | "prompt" | "none"; reason: string } {
  if (!prev) {
    // Baseline sighting: never alert on already-stopped sessions at startup.
    return { triggered: false, kind: "none", reason: "baseline" };
  }

  const prevState = prev.state.toLowerCase();
  const currState = curr.state.toLowerCase();

  // 1. Primary signal: genuine turn end (working -> done / waiting / idle / stopped).
  // Treat state "unknown" as NOT a stop (avoids false alerts during transient disconnects).
  if (prevState === "working" && currState !== "working" && currState !== "unknown") {
    return { triggered: true, kind: "stop", reason: `state ${prevState} -> ${currState}` };
  }

  // 2. Secondary signal: actively working session hits an explicit interactive permission prompt.
  // Cooldown applies here so screen repaints while waiting on permission don't repeat-alert.
  if (prev.lastAlertedAt > 0 && now - prev.lastAlertedAt < cooldownMs) {
    return { triggered: false, kind: "none", reason: "cooldown" };
  }

  const currHash = curr.preview.slice(-260);
  if (
    currState === "working" &&
    curr.connected &&
    currHash &&
    currHash !== prev.previewHash &&
    curr.updatedAt > prev.updatedAt &&
    LIVE_PROMPT_CUE_RE.test(currHash)
  ) {
    return { triggered: true, kind: "prompt", reason: "live permission prompt" };
  }

  return { triggered: false, kind: "none", reason: "no transition" };
}

interface HeldAlert {
  session: SessionSummary;
  spokenAlert: string;
  needsDecision: boolean;
  timestamp: number;
}

export class SessionWatcher {
  private orca: OrcaClient;
  private brain: VoiceBrain;
  private opts: Required<
    Pick<WatcherOptions, "pollMs" | "cooldownMs" | "notifyOnAllStops" | "managedBuilderAlerts">
  > &
    Pick<WatcherOptions, "onAlert" | "onQuietBuilderStop" | "onError" | "serialize" | "hasListener">;
  private nowFn: () => number;
  private tracked = new Map<string, TrackedSession>();
  private heldAlerts: HeldAlert[] = [];
  private timer: NodeJS.Timeout | null = null;
  private fileWatchers: FSWatcher[] = [];
  private wakeDebounce: NodeJS.Timeout | null = null;
  private polling = false;
  private queuedImmediate = false;
  private enabled = true;
  private managedBuilderAlerts: boolean;
  private initialized = false;

  constructor(orca: OrcaClient, brain: VoiceBrain, opts: WatcherOptions) {
    this.orca = orca;
    this.brain = brain;
    this.nowFn = opts.nowFn ?? (() => Date.now());
    const managedDefault =
      opts.managedBuilderAlerts ?? gafferEnv("MANAGED_BUILDER_ALERTS") === "1";
    this.managedBuilderAlerts = managedDefault;
    this.opts = {
      pollMs: opts.pollMs ?? Math.max(2500, Number(gafferEnv("POLL_MS") || 2500)),
      cooldownMs: opts.cooldownMs ?? Number(gafferEnv("ALERT_COOLDOWN_MS") || 30_000),
      // Default OFF: only alert on stops that need the owner's decision unless GAFFER_ALL_STOPS=1.
      notifyOnAllStops: opts.notifyOnAllStops ?? gafferEnv("ALL_STOPS") === "1",
      managedBuilderAlerts: managedDefault,
      onAlert: opts.onAlert,
      onQuietBuilderStop: opts.onQuietBuilderStop,
      onError: opts.onError,
      serialize: opts.serialize,
      hasListener: opts.hasListener,
    };
  }

  isEnabled(): boolean {
    return this.enabled;
  }

  setEnabled(on: boolean): void {
    this.enabled = on;
    if (!on) {
      this.initialized = false;
    }
  }

  isManagedBuilderAlertsEnabled(): boolean {
    return this.managedBuilderAlerts;
  }

  setManagedBuilderAlerts(on: boolean): void {
    this.managedBuilderAlerts = Boolean(on);
  }

  getHeldAlertCount(): number {
    return this.heldAlerts.length;
  }

  start(): void {
    if (this.timer) return;
    void this.tick();
    this.timer = setInterval(() => {
      void this.tick();
    }, this.opts.pollMs);
    this.attachStopLogWatchers();
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    if (this.wakeDebounce) {
      clearTimeout(this.wakeDebounce);
      this.wakeDebounce = null;
    }
    for (const fw of this.fileWatchers) {
      try {
        fw.close();
      } catch {
        /* ignore */
      }
    }
    this.fileWatchers = [];
  }

  private attachStopLogWatchers(): void {
    const home = homedir();
    const dirs = [join(home, ".pi", "agent"), join(home, ".claude"), join(home, ".gemini")];
    for (const dir of dirs) {
      if (!existsSync(dir)) continue;
      try {
        const fw = fsWatch(dir, (_ev, filename) => {
          if (!filename || !String(filename).includes("foreman-stops")) return;
          if (this.wakeDebounce) clearTimeout(this.wakeDebounce);
          this.wakeDebounce = setTimeout(() => {
            this.wakeDebounce = null;
            this.triggerImmediateTick();
          }, 150);
        });
        fw.on("error", () => {
          /* non-fatal */
        });
        this.fileWatchers.push(fw);
      } catch {
        /* ignore unsupported fs.watch */
      }
    }
  }

  private triggerImmediateTick(): void {
    if (this.polling) {
      this.queuedImmediate = true;
      return;
    }
    void this.tick();
  }

  private async deliverAlert(item: HeldAlert): Promise<void> {
    const emit = async () => {
      if (this.brain.hasPendingConfirmation()) {
        this.heldAlerts.push(item);
        return;
      }
      this.brain.recordProactiveAlert(item.session, item.spokenAlert);
      await this.opts.onAlert({
        id: `alert_${item.timestamp}_${Math.random().toString(16).slice(2, 8)}`,
        sessionId: item.session.id,
        sessionTitle: item.session.title,
        spokenText: item.spokenAlert,
        needsDecision: item.needsDecision,
        timestamp: item.timestamp,
      });
    };
    if (this.opts.serialize) {
      await this.opts.serialize(emit);
    } else {
      await emit();
    }
  }

  async flushHeldAlerts(): Promise<void> {
    if (!this.heldAlerts.length) return;
    if (this.brain.hasPendingConfirmation()) return;
    const queued = this.heldAlerts.splice(0, this.heldAlerts.length);
    for (const item of queued) {
      if (this.brain.hasPendingConfirmation()) {
        this.heldAlerts.unshift(item);
        break;
      }
      try {
        await this.deliverAlert(item);
      } catch (err) {
        this.heldAlerts.unshift(item);
        this.opts.onError?.(err);
        break;
      }
    }
  }

  async tick(): Promise<void> {
    if (this.polling) return;
    const someoneListening = this.opts.hasListener ? this.opts.hasListener() : true;
    // Zero idle load: do not even poll Orca when alerts are off or nobody is listening.
    if (!this.enabled || !someoneListening) {
      this.initialized = false;
      this.tracked.clear();
      return;
    }

    this.polling = true;
    try {
      await this.flushHeldAlerts();

      const sessions = await this.orca.listSessions();
      const topology = classifyTopology(sessions);
      const sessionById = new Map(sessions.map((s) => [s.id, s]));
      const now = this.nowFn();

      for (const s of sessions) {
        const prev = this.tracked.get(s.id);
        const currHash = s.preview.slice(-260);
        const isWorkingNow = s.state.toLowerCase() === "working";
        const lastWorkingAt = isWorkingNow ? now : prev?.lastWorkingAt ?? 0;

        if (!this.initialized) {
          this.tracked.set(s.id, {
            state: s.state,
            updatedAt: s.updatedAt,
            previewHash: currHash,
            lastAlertedAt: 0,
            lastAlertedTurnKey: "",
            lastWorkingAt,
          });
          continue;
        }

        const check = detectTransition(prev, s, now, this.opts.cooldownMs);
        const nextEntry: TrackedSession = {
          state: s.state,
          updatedAt: s.updatedAt,
          previewHash: currHash,
          lastAlertedAt: prev?.lastAlertedAt ?? 0,
          lastAlertedTurnKey: prev?.lastAlertedTurnKey ?? "",
          lastWorkingAt,
        };

        if (check.triggered) {
          const topo = topology.get(s.id);

          try {
            const details = await this.orca.readSession(s, 6);
            const lastAssistant =
              [...details.recentMessages].reverse().find((m) => m.role === "assistant")?.text || "";

            // If every read channel failed and we have no content at all, keep the old state so the next tick retries.
            if (details.readErrors.length > 0 && !lastAssistant && !details.screenTail) {
              this.opts.onError?.(new Error(details.readErrors.join("; ")));
              continue;
            }

            // Topping Out safety invariant: NEVER mute a stop that shows a real owed: item,
            // a YOUR CALL card, or a trust/permission prompt (even if Foreman/Builder pairing guessed wrong!).
            const fullText = `${lastAssistant}\n${details.screenTail}\n${currHash}`;
            const liveJStatus = parseJStatus(lastAssistant || details.screenTail) ?? topo?.jStatus ?? null;
            const hasOwnerDecision = Boolean(liveJStatus?.hasRealOwed);
            const hasTrustOrPermPrompt = LIVE_PROMPT_CUE_RE.test(fullText);

            if (
              !this.managedBuilderAlerts &&
              check.kind === "stop" &&
              topo?.role === "builder" &&
              topo.pairedForemanId &&
              !hasOwnerDecision &&
              !hasTrustOrPermPrompt
            ) {
              const foreman = sessionById.get(topo.pairedForemanId);
              const foremanPrev = this.tracked.get(topo.pairedForemanId);
              const foremanActive =
                Boolean(foreman?.connected) &&
                (foreman?.state.toLowerCase() === "working" ||
                  (foremanPrev !== undefined &&
                    foremanPrev.lastWorkingAt > 0 &&
                    now - foremanPrev.lastWorkingAt <= FOREMAN_GRACE_MS));

              if (foremanActive) {
                console.log(
                  `   (quiet builder stop: ${s.title}, managed by ${topo.pairedForemanTitle || "Foreman"})`
                );
                this.opts.onQuietBuilderStop?.({
                  builderTitle: s.title,
                  foremanTitle: topo.pairedForemanTitle || "Foreman",
                });
                this.tracked.set(s.id, nextEntry);
                continue;
              }
            }

            // Dedupe on turn identity (state + updatedAt + message count + full screen/message signature).
            const contentSig = lastAssistant
              ? `msg:${details.recentMessages.length}:${lastAssistant.length}:${lastAssistant.slice(0, 120)}`
              : `tui:${details.screenTail.length}:${details.screenTail.slice(-1800).trim()}`;
            const turnKey = `${details.transcriptState || s.state}|${s.updatedAt}|${contentSig}`;

            if (turnKey === nextEntry.lastAlertedTurnKey) {
              this.tracked.set(s.id, nextEntry);
              continue;
            }

            const verdict = await this.brain.evaluateAlert(details, this.opts.notifyOnAllStops, topo);
            if (verdict.shouldAlert && verdict.spokenAlert) {
              nextEntry.lastAlertedAt = now;
              nextEntry.lastAlertedTurnKey = turnKey;
              const alertItem: HeldAlert = {
                session: s,
                spokenAlert: verdict.spokenAlert,
                needsDecision: verdict.needsDecision,
                timestamp: now,
              };
              if (this.brain.hasPendingConfirmation()) {
                this.heldAlerts.push(alertItem);
              } else {
                await this.deliverAlert(alertItem);
              }
            }
          } catch (err) {
            // Leave prev state untouched so the very next poll tick retries this stop cleanly.
            this.opts.onError?.(err);
            continue;
          }
        }

        // Preserve previous working state if state transiently flickers to "unknown"
        if (prev?.state.toLowerCase() === "working" && s.state.toLowerCase() === "unknown") {
          continue;
        }

        this.tracked.set(s.id, nextEntry);
      }

      this.initialized = true;
    } catch (err) {
      this.opts.onError?.(err);
    } finally {
      this.polling = false;
      if (this.queuedImmediate) {
        this.queuedImmediate = false;
        setTimeout(() => void this.tick(), 50);
      }
    }
  }
}

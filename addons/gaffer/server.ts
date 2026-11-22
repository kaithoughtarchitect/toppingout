// Topping Out Gaffer: zero-dependency HTTP + SSE server.
// Listens on 127.0.0.1 by default; enforces Host/Origin/CSRF checks and remote Tailscale/token auth.
import { gafferEnv } from "./env.js";
import http, { IncomingMessage, ServerResponse } from "node:http";
import { timingSafeEqual } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { OrcaClient } from "./orca.js";
import { ListenMode, VoiceBrain } from "./brain.js";
import { SessionWatcher, WatchAlert } from "./watcher.js";
import { playMp3Locally, spokenFailureMessage, synthesizeGrokSpeech, transcribeAudio } from "./speech.js";
import { classifyTopology } from "./toppingout.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const UI_PATH = resolve(HERE, "ui.html");
export const GAFFER_CSRF_HEADER = "x-toppingout-gaffer";
export const GAFFER_TOKEN_HEADER = "x-toppingout-token";
export const GAFFER_COOKIE_NAME = "gaffer_session";
// Backwards-compatible exports
export const RADIO_CSRF_HEADER = GAFFER_CSRF_HEADER;
export const RADIO_TOKEN_HEADER = GAFFER_TOKEN_HEADER;
export const RADIO_COOKIE_NAME = GAFFER_COOKIE_NAME;

function parseCookieHeader(cookieHeader: string | undefined): Record<string, string> {
  const out: Record<string, string> = {};
  if (!cookieHeader) return out;
  for (const part of cookieHeader.split(";")) {
    const eq = part.indexOf("=");
    if (eq === -1) continue;
    const k = part.slice(0, eq).trim();
    const v = part.slice(eq + 1).trim();
    if (k) {
      try {
        out[k] = decodeURIComponent(v);
      } catch {
        out[k] = v;
      }
    }
  }
  return out;
}

export interface AuthConfig {
  token?: string;
  allowedTailscaleUsers?: string[];
  requireLocalAuth?: boolean;
}

export interface ServerDeps {
  orca?: OrcaClient;
  brain?: VoiceBrain;
  transcribe?: typeof transcribeAudio;
  synthesize?: typeof synthesizeGrokSpeech;
  startWatcher?: boolean;
  localAudioFallback?: boolean;
  auth?: AuthConfig;
  port?: number;
  host?: string;
  nowFn?: () => number;
}

class HttpError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function isAllowedHost(hostHeader: string | undefined): boolean {
  if (!hostHeader) return true;
  const host = hostHeader.trim().toLowerCase();
  const bare = host.startsWith("[")
    ? host.slice(0, host.indexOf("]") + 1)
    : host.split(":")[0];
  return (
    bare === "127.0.0.1" ||
    bare === "localhost" ||
    bare === "[::1]" ||
    bare.endsWith(".ts.net") ||
    /^100\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(bare)
  );
}

export function isAllowedOrigin(originHeader: string | undefined): boolean {
  if (!originHeader) return true;
  try {
    const u = new URL(originHeader);
    if (u.protocol !== "http:" && u.protocol !== "https:") return false;
    return isAllowedHost(u.hostname);
  } catch {
    return false;
  }
}

function isLoopbackAddress(addr: string | undefined): boolean {
  if (!addr) return false;
  return addr === "127.0.0.1" || addr === "::1" || addr === "::ffff:127.0.0.1";
}

function safeTokenEquals(a: string, b: string): boolean {
  const ab = Buffer.from(a, "utf8");
  const bb = Buffer.from(b, "utf8");
  if (ab.length !== bb.length || ab.length === 0) return false;
  return timingSafeEqual(ab, bb);
}

export function isRemoteRequest(req: IncomingMessage): boolean {
  if (!isLoopbackAddress(req.socket?.remoteAddress)) return true;
  if (req.headers["tailscale-user-login"] || req.headers["x-forwarded-for"]) return true;
  const host = String(req.headers.host || "").toLowerCase();
  const bare = host.startsWith("[") ? host.slice(0, host.indexOf("]") + 1) : host.split(":")[0];
  if (bare && bare !== "127.0.0.1" && bare !== "localhost" && bare !== "[::1]") return true;
  return false;
}

export function authorizeRequest(
  req: IncomingMessage,
  url: URL,
  auth: AuthConfig
): { ok: true } | { ok: false; status: number; error: string } {
  const remote = isRemoteRequest(req);
  if (!remote && !auth.requireLocalAuth) {
    return { ok: true };
  }

  const configuredToken = (auth.token || "").trim();
  const allowedUsers = (auth.allowedTailscaleUsers || [])
    .map((u) => u.trim().toLowerCase())
    .filter(Boolean);

  // 1. Check Tailscale Serve identity header (only trusted when arriving over loopback proxy)
  const tsUser = String(req.headers["tailscale-user-login"] || "")
    .trim()
    .toLowerCase();
  if (
    tsUser &&
    isLoopbackAddress(req.socket?.remoteAddress) &&
    allowedUsers.length > 0 &&
    allowedUsers.includes(tsUser)
  ) {
    return { ok: true };
  }

  // 2. Check shared secret token via header (X-ToppingOut-Token / Bearer) or HttpOnly session cookie.
  // Never accept tokens in URL query strings (avoids leaking secrets in browser history/proxy logs).
  if (configuredToken) {
    const hdrToken = String(req.headers[RADIO_TOKEN_HEADER] || "").trim();
    const authHdr = String(req.headers.authorization || "").trim();
    const bearer = authHdr.toLowerCase().startsWith("bearer ") ? authHdr.slice(7).trim() : "";
    const cookies = parseCookieHeader(req.headers.cookie);
    const cookieToken = (cookies[RADIO_COOKIE_NAME] || "").trim();
    const candidate = hdrToken || bearer || cookieToken;
    if (candidate && safeTokenEquals(candidate, configuredToken)) {
      return { ok: true };
    }
    return {
      ok: false,
      status: 401,
      error: "Unauthorized: valid access token required.",
    };
  }

  if (allowedUsers.length > 0) {
    return {
      ok: false,
      status: 403,
      error: "Forbidden: Tailscale user is not in GAFFER_ALLOWED_TAILSCALE_USER.",
    };
  }

  return {
    ok: false,
    status: 401,
    error:
      "Remote access is locked: set GAFFER_TOKEN or GAFFER_ALLOWED_TAILSCALE_USER before exposing over Tailscale.",
  };
}

function readBody(req: IncomingMessage, maxBytes = 12 * 1024 * 1024): Promise<Buffer> {
  return new Promise((resolveBuf, reject) => {
    const chunks: Buffer[] = [];
    let total = 0;
    let settled = false;
    req.on("data", (chunk: Buffer) => {
      if (settled) return;
      total += chunk.length;
      if (total > maxBytes) {
        settled = true;
        req.pause();
        reject(new HttpError(413, "Request payload too large."));
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => {
      if (!settled) {
        settled = true;
        resolveBuf(Buffer.concat(chunks));
      }
    });
    req.on("error", (err) => {
      if (!settled) {
        settled = true;
        reject(err);
      }
    });
  });
}

function parseJsonBody<T>(raw: Buffer): T {
  const str = raw.toString("utf8").trim();
  if (!str) return {} as T;
  try {
    return JSON.parse(str) as T;
  } catch {
    throw new HttpError(400, "Invalid JSON request body.");
  }
}

function sendJson(res: ServerResponse, status: number, payload: unknown): void {
  if (res.writableEnded || res.destroyed) return;
  const body = JSON.stringify(payload);
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  });
  res.end(body);
}

export function createVoiceServer(deps: ServerDeps = {}) {
  const orca = deps.orca ?? new OrcaClient();
  const brain = deps.brain ?? new VoiceBrain(orca);
  const transcribeFn = deps.transcribe ?? transcribeAudio;
  const synthesizeFn = deps.synthesize ?? synthesizeGrokSpeech;
  const authConfig: AuthConfig = deps.auth ?? {
    token: gafferEnv("TOKEN"),
    allowedTailscaleUsers: (gafferEnv("ALLOWED_TAILSCALE_USER") || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
    requireLocalAuth: gafferEnv("REQUIRE_LOCAL_AUTH") === "1",
  };

  const sseClients = new Set<ServerResponse>();
  const audioUnlockedClients = new Set<ServerResponse>();
  const audioCache = new Map<string, Buffer>();
  const audioOrder: string[] = [];
  const nowFn = deps.nowFn ?? (() => Date.now());
  const SSE_REPLAY_MAX = 25;
  const SSE_REPLAY_MAX_AGE_MS = 90_000;
  let sseEventSeq = 0;
  const sseReplayBuffer: Array<{ id: number; event: string; data: Record<string, unknown>; timestamp: number }> = [];
  // Local Windows playback is opt-in (GAFFER_LOCAL_AUDIO=1) so closing the browser
  // pauses all paid alert LLM + TTS calls automatically ($0 idle spend).
  const pcAudioFallback = deps.localAudioFallback ?? gafferEnv("LOCAL_AUDIO") === "1";

  let turnQueue: Promise<void> = Promise.resolve();
  function serialize<T>(fn: () => Promise<T>): Promise<T> {
    const next = turnQueue.then(fn, fn);
    turnQueue = next.then(
      () => undefined,
      () => undefined
    );
    return next;
  }

  function cacheAudio(id: string, buf: Buffer): string {
    audioCache.set(id, buf);
    audioOrder.push(id);
    while (audioOrder.length > 25) {
      const oldest = audioOrder.shift();
      if (oldest) audioCache.delete(oldest);
    }
    return `/api/audio/${encodeURIComponent(id)}`;
  }

  function broadcastSse(event: string, data: unknown): number {
    const id = ++sseEventSeq;
    const frame = `id: ${id}\nevent: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
    if (event === "alert" && data && typeof data === "object") {
      sseReplayBuffer.push({
        id,
        event,
        data: data as Record<string, unknown>,
        timestamp: nowFn(),
      });
      while (sseReplayBuffer.length > SSE_REPLAY_MAX) {
        sseReplayBuffer.shift();
      }
    }
    for (const client of sseClients) {
      try {
        client.write(frame);
      } catch {
        sseClients.delete(client);
        audioUnlockedClients.delete(client);
      }
    }
    return id;
  }

  async function emitSpokenAlert(
    alert: WatchAlert,
    opts?: { throwOnTtsError?: boolean }
  ): Promise<{ audioUrl: string | null; playedLocally: boolean }> {
    let audioUrl: string | null = null;
    let mp3: Buffer | null = null;
    try {
      mp3 = await synthesizeFn(alert.spokenText);
      audioUrl = cacheAudio(alert.id, mp3);
    } catch (err) {
      console.error(`[gaffer] TTS failed for alert: ${err instanceof Error ? err.message : err}`);
      if (opts?.throwOnTtsError) throw err;
    }

    const playedLocally = Boolean(
      mp3 && pcAudioFallback && audioUnlockedClients.size === 0 && deps.startWatcher !== false
    );

    console.log(`🔔 [ALERT] (${alert.sessionTitle}) ${alert.spokenText}`);
    const baseState = brain.getState();
    broadcastSse("alert", {
      ...alert,
      audioUrl,
      playedLocally,
      state: {
        ...baseState,
        activeSessionId: alert.sessionId,
        activeSessionTitle: alert.sessionTitle,
        pendingConfirmation: null,
        followUpActive: true,
      },
    });

    if (playedLocally && mp3) {
      void playMp3Locally(mp3).catch(() => {});
    }

    return { audioUrl, playedLocally };
  }

  const watcher = new SessionWatcher(orca, brain, {
    serialize,
    // Count ONLY connected clients that unlocked audio (or explicit PC fallback): zero spend before Connect.
    hasListener: () => audioUnlockedClients.size > 0 || pcAudioFallback,
    onAlert: async (alert) => {
      await emitSpokenAlert(alert, { throwOnTtsError: true });
    },
    onQuietBuilderStop: (info) => {
      broadcastSse("quiet", { ...info, timestamp: Date.now() });
    },
    onError: (err) => {
      console.error(`[gaffer] watcher error: ${err instanceof Error ? err.message : err}`);
    },
  });

  const server = http.createServer(async (req, res) => {
    try {
      if (!isAllowedHost(req.headers.host)) {
        sendJson(res, 403, { ok: false, error: "Forbidden host." });
        return;
      }

      const origin = typeof req.headers.origin === "string" ? req.headers.origin : undefined;
      if (!isAllowedOrigin(origin)) {
        sendJson(res, 403, { ok: false, error: "Forbidden origin." });
        return;
      }

      if (req.method === "OPTIONS") {
        sendJson(res, 403, { ok: false, error: "Cross-origin requests are not allowed." });
        return;
      }

      const url = new URL(req.url || "/", `http://${req.headers.host || "127.0.0.1"}`);
      const pathname = url.pathname;

      // Static UI shell & minimal health check stay reachable so remote users can enter a token
      if (req.method === "GET" && (pathname === "/" || pathname === "/index.html")) {
        const html = readFileSync(UI_PATH, "utf8");
        res.writeHead(200, {
          "Content-Type": "text/html; charset=utf-8",
          "Cache-Control": "no-store",
        });
        res.end(html);
        return;
      }

      if (req.method === "GET" && pathname === "/health") {
        sendJson(res, 200, { ok: true, clients: sseClients.size, watchEnabled: watcher.isEnabled() });
        return;
      }

      // Authenticate all API and SSE endpoints on remote / Tailscale connections
      const authCheck = authorizeRequest(req, url, authConfig);
      if (!authCheck.ok) {
        sendJson(res, authCheck.status, { ok: false, error: authCheck.error });
        return;
      }

      // Require custom header on all mutating POST endpoints (blocks simple cross-site POST CSRF)
      if (req.method === "POST") {
        const csrfHeader = String(req.headers[RADIO_CSRF_HEADER] || "").trim();
        if (csrfHeader !== "1") {
          sendJson(res, 403, {
            ok: false,
            error: `Missing required ${RADIO_CSRF_HEADER}: 1 header.`,
          });
          return;
        }
      }

      // Exchange header token for an HttpOnly SameSite=Strict cookie so EventSource and <audio>
      // authenticate without ever putting secrets in URL query strings.
      if (req.method === "POST" && pathname === "/api/auth") {
        const configuredToken = (authConfig.token || "").trim();
        if (configuredToken) {
          const isHttps =
            String(req.headers["x-forwarded-proto"] || "").toLowerCase() === "https" ||
            String(req.headers.host || "").toLowerCase().includes(".ts.net");
          const cookie = [
            `${RADIO_COOKIE_NAME}=${encodeURIComponent(configuredToken)}`,
            "HttpOnly",
            "SameSite=Strict",
            "Path=/",
            ...(isHttps ? ["Secure"] : []),
          ].join("; ");
          res.setHeader("Set-Cookie", cookie);
        }
        sendJson(res, 200, { ok: true });
        return;
      }

      if (req.method === "GET" && pathname === "/events") {
        const audioReady = url.searchParams.get("audio") === "1";
        const lastIdRaw = String(req.headers["last-event-id"] || url.searchParams.get("lastEventId") || "").trim();
        const rawLastEventId = /^\d+$/.test(lastIdRaw) ? Number(lastIdRaw) : 0;
        const serverRestarted = rawLastEventId > sseEventSeq;
        const lastEventId = serverRestarted ? 0 : rawLastEventId;
        res.writeHead(200, {
          "Content-Type": "text/event-stream; charset=utf-8",
          "Cache-Control": "no-cache, no-transform",
          Connection: "keep-alive",
          "X-Accel-Buffering": "no",
        });
        // Fresh client (rawLastEventId === 0): stamp id: sseEventSeq so cursor starts at head.
        // Server restart (rawLastEventId > sseEventSeq): reset cursor to id: 0 (cursorReset: true)
        // and replay any fresh (<90s) alerts emitted since restart.
        // Normal reconnect (0 < lastEventId <= sseEventSeq): omit id on connected so cursor only
        // advances as each replayed alert actually arrives.
        const connectedIdLine = serverRestarted
          ? "id: 0\n"
          : rawLastEventId === 0
            ? `id: ${sseEventSeq}\n`
            : "";
        res.write(
          `${connectedIdLine}event: connected\ndata: ${JSON.stringify({
            ok: true,
            lastEventId: serverRestarted ? 0 : lastEventId > 0 ? lastEventId : sseEventSeq,
            cursorReset: serverRestarted,
            state: brain.getState(),
            watchEnabled: watcher.isEnabled(),
            managedBuilderAlerts: watcher.isManagedBuilderAlertsEnabled(),
            voice: (process.env.SPEAK_GROK_VOICE || "leo").trim().toLowerCase(),
          })}\n\n`
        );
        if (lastEventId > 0 || serverRestarted) {
          const cutoff = nowFn() - SSE_REPLAY_MAX_AGE_MS;
          for (const item of sseReplayBuffer) {
            if (item.id > lastEventId && item.timestamp >= cutoff) {
              res.write(
                `id: ${item.id}\nevent: ${item.event}\ndata: ${JSON.stringify({
                  ...item.data,
                  replayed: true,
                })}\n\n`
              );
            }
          }
        }
        sseClients.add(res);
        if (audioReady) audioUnlockedClients.add(res);

        const hb = setInterval(() => {
          try {
            res.write(`: ping ${Date.now()}\n\n`);
          } catch {
            clearInterval(hb);
            sseClients.delete(res);
            audioUnlockedClients.delete(res);
          }
        }, 20_000);

        req.on("close", () => {
          clearInterval(hb);
          sseClients.delete(res);
          audioUnlockedClients.delete(res);
        });
        return;
      }

      if (req.method === "GET" && pathname === "/api/state") {
        sendJson(res, 200, {
          ok: true,
          brain: brain.getState(),
          watchEnabled: watcher.isEnabled(),
          managedBuilderAlerts: watcher.isManagedBuilderAlertsEnabled(),
          clients: sseClients.size,
          audioClients: audioUnlockedClients.size,
          pcAudioFallback,
          voice: (process.env.SPEAK_GROK_VOICE || "leo").trim().toLowerCase(),
        });
        return;
      }

      if (req.method === "GET" && pathname === "/api/sessions") {
        const sessions = await orca.listSessions();
        const topology = classifyTopology(sessions);
        const enriched = sessions.map((s) => {
          const topo = topology.get(s.id);
          return {
            ...s,
            role: topo?.role ?? "standalone",
            pairedForemanId: topo?.pairedForemanId ?? null,
            pairedForemanTitle: topo?.pairedForemanTitle ?? null,
            pairedBuilderId: topo?.pairedBuilderId ?? null,
            pairedBuilderTitle: topo?.pairedBuilderTitle ?? null,
            owed: topo?.jStatus?.hasRealOwed ? topo.jStatus.owed || "YOUR CALL" : null,
            hasYourCall: Boolean(topo?.jStatus?.hasYourCall),
          };
        });
        sendJson(res, 200, { ok: true, sessions: enriched });
        return;
      }

      if (req.method === "GET" && pathname.startsWith("/api/audio/")) {
        const id = decodeURIComponent(pathname.slice("/api/audio/".length));
        const buf = audioCache.get(id);
        if (!buf) {
          sendJson(res, 404, { ok: false, error: "Audio clip expired or not found." });
          return;
        }
        res.writeHead(200, {
          "Content-Type": "audio/mpeg",
          "Content-Length": String(buf.length),
          "Cache-Control": "no-store",
        });
        res.end(buf);
        return;
      }

      if (req.method === "POST" && pathname === "/api/watch") {
        const raw = await readBody(req, 64 * 1024);
        const parsed = parseJsonBody<{ enabled?: boolean }>(raw);
        if (typeof parsed.enabled === "boolean") {
          watcher.setEnabled(parsed.enabled);
        }
        broadcastSse("watch", { enabled: watcher.isEnabled() });
        sendJson(res, 200, { ok: true, watchEnabled: watcher.isEnabled() });
        return;
      }

      if (req.method === "POST" && pathname === "/api/managed-builders") {
        const raw = await readBody(req, 64 * 1024);
        const parsed = parseJsonBody<{ enabled?: boolean }>(raw);
        if (typeof parsed.enabled === "boolean") {
          watcher.setManagedBuilderAlerts(parsed.enabled);
        }
        const enabled = watcher.isManagedBuilderAlertsEnabled();
        broadcastSse("managedBuilders", { enabled });
        sendJson(res, 200, { ok: true, managedBuilderAlerts: enabled });
        return;
      }

      if (req.method === "POST" && pathname === "/api/style") {
        const raw = await readBody(req, 64 * 1024);
        const parsed = parseJsonBody<{ style?: string }>(raw);
        if (parsed.style === "brief" || parsed.style === "speak") {
          brain.setReplyStyle(parsed.style);
        }
        const replyStyle = brain.getReplyStyle();
        broadcastSse("style", { style: replyStyle });
        sendJson(res, 200, { ok: true, replyStyle });
        return;
      }

      if (req.method === "POST" && pathname === "/api/playback-cut") {
        const raw = await readBody(req, 64 * 1024);
        const parsed = parseJsonBody<{ text?: string; playedRatio?: number; sessionTitle?: string }>(raw);
        const hasRemainder = await serialize(async () =>
          typeof parsed.text === "string" && parsed.text.trim().length > 0
            ? brain.recordInterruptedSpeech(
                parsed.text,
                typeof parsed.playedRatio === "number" ? parsed.playedRatio : 0,
                parsed.sessionTitle ?? null
              )
            : false
        );
        sendJson(res, 200, { ok: true, hasRemainder });
        return;
      }

      if (req.method === "POST" && pathname === "/api/test-alert") {
        const ownerName = (gafferEnv("OWNER_NAME") || "").trim();
        const greeting = ownerName ? `Hey ${ownerName}` : "Gaffer check";
        const alert: WatchAlert = {
          id: `test_${Date.now()}`,
          sessionId: "test",
          sessionTitle: "Topping Out Gaffer",
          spokenText: `${greeting}, Topping Out Gaffer is live. Your headphones and unprompted alerts are ready.`,
          needsDecision: false,
          timestamp: Date.now(),
        };
        const { audioUrl, playedLocally } = await emitSpokenAlert(alert);
        sendJson(res, 200, { ok: true, alert, audioUrl, playedLocally });
        return;
      }

      if (req.method === "POST" && pathname === "/api/text") {
        const raw = await readBody(req, 256 * 1024);
        const body = parseJsonBody<{ text?: string; mode?: ListenMode; speak?: boolean }>(raw);
        const text = (body.text || "").trim();
        const mode: ListenMode = body.mode || "manual";
        const wantAudio = body.speak !== false;

        const result = await serialize(async () => {
          const outcome = await brain.handleUserUtterance(text, mode);
          let audioBase64: string | null = null;
          let ttsError: string | null = null;
          if (!outcome.ignored && outcome.replyText && wantAudio) {
            try {
              const mp3 = await synthesizeFn(outcome.replyText);
              audioBase64 = mp3.toString("base64");
            } catch (err) {
              ttsError = err instanceof Error ? err.message : String(err);
              // Safety: if TTS fails on a read-back for a staged reply, cancel the staged reply
              // so the owner is never left holding an unspoken draft.
              if (outcome.pendingConfirmation) {
                brain.cancelPendingConfirmation();
                outcome.pendingConfirmation = null;
                outcome.replyText = `${outcome.replyText} (Cancelled staged reply because read-back audio failed.)`;
              }
            }
          }
          return { outcome, audioBase64, ttsError };
        });

        if (!result.outcome.pendingConfirmation) {
          void watcher.flushHeldAlerts();
        }

        sendJson(res, 200, {
          ok: true,
          transcript: text,
          ...result.outcome,
          audioBase64: result.audioBase64,
          ttsError: result.ttsError,
        });
        return;
      }

      if (req.method === "POST" && pathname === "/api/voice") {
        const audioBuf = await readBody(req, 12 * 1024 * 1024);
        const mimeType = String(req.headers["content-type"] || "audio/webm");
        const modeParam = url.searchParams.get("mode");
        const mode: ListenMode =
          modeParam === "wake" || modeParam === "always" || modeParam === "manual"
            ? modeParam
            : "wake";

        const result = await serialize(async () => {
          const stt = await transcribeFn(audioBuf, mimeType);
          if (stt.ignored || !stt.text) {
            return {
              transcript: "",
              ignored: true,
              reason: stt.reason || "empty transcript",
              replyText: "",
              audioBase64: null as string | null,
              ttsError: null as string | null,
              ...brain.getState(),
            };
          }

          console.log(`🎤 [YOU] ${stt.text}`);
          const outcome = await brain.handleUserUtterance(stt.text, mode);
          if (outcome.ignored) {
            console.log(`   (ignored: ${outcome.reason})`);
            return {
              transcript: stt.text,
              ...outcome,
              audioBase64: null as string | null,
              ttsError: null as string | null,
            };
          }

          console.log(`🗣️  [GAFFER] ${outcome.replyText}`);
          let audioBase64: string | null = null;
          let ttsError: string | null = null;
          try {
            const mp3 = await synthesizeFn(outcome.replyText);
            audioBase64 = mp3.toString("base64");
          } catch (err) {
            ttsError = err instanceof Error ? err.message : String(err);
            console.error(`[gaffer] TTS error: ${ttsError}`);
            // Safety: never keep a staged reply if its spoken read-back failed to synthesize.
            if (outcome.pendingConfirmation) {
              brain.cancelPendingConfirmation();
              outcome.pendingConfirmation = null;
              outcome.replyText = `${outcome.replyText} (Cancelled staged reply because read-back audio failed.)`;
            }
          }

          return {
            transcript: stt.text,
            ...outcome,
            audioBase64,
            ttsError,
          };
        });

        if (!result.pendingConfirmation) {
          void watcher.flushHeldAlerts();
        }

        sendJson(res, 200, { ok: true, ...result });
        return;
      }

      sendJson(res, 404, { ok: false, error: `Not found: ${pathname}` });
    } catch (err) {
      const status = err instanceof HttpError ? err.status : 500;
      const msg = err instanceof Error ? err.message : String(err);
      if (status >= 500) console.error(`[gaffer] HTTP error: ${msg}`);
      sendJson(res, status, { ok: false, error: msg, spokenError: spokenFailureMessage(err) });
    }
  });

  if (deps.startWatcher !== false) {
    watcher.start();
  }

  return {
    server,
    watcher,
    brain,
    orca,
    close(): Promise<void> {
      watcher.stop();
      for (const client of sseClients) {
        try {
          client.end();
        } catch {
          /* ignore */
        }
      }
      sseClients.clear();
      audioUnlockedClients.clear();
      audioCache.clear();
      audioOrder.length = 0;
      return new Promise((resolveClose) => {
        server.close(() => resolveClose());
        server.closeAllConnections?.();
      });
    },
  };
}

const isEntry =
  typeof process.argv[1] === "string" &&
  (process.argv[1].endsWith("server.ts") || process.argv[1].endsWith("server.js"));

if (isEntry) {
  const host = gafferEnv("HOST") || "127.0.0.1";
  const port = Number(gafferEnv("PORT") || 4111);
  const app = createVoiceServer({ host, port });

  app.server.listen(port, host, () => {
    const voice = (process.env.SPEAK_GROK_VOICE || "leo").trim().toLowerCase();
    const brainModel = gafferEnv("LLM_MODEL") || "anthropic/claude-haiku-5.5";
    const sttPref = (gafferEnv("STT_PROVIDER") || "").trim().toLowerCase();
    const useOpenRouterStt =
      sttPref === "openrouter" ||
      (sttPref !== "openai" && !process.env.OPENAI_API_KEY && Boolean(process.env.OPENROUTER_API_KEY));
    const sttLabel = useOpenRouterStt
      ? `${gafferEnv("OR_STT_MODEL") || "openai/gpt-audio-mini"} via OpenRouter`
      : `${gafferEnv("STT_MODEL") || "gpt-4o-mini-transcribe"} via OpenAI`;
    console.log("");
    console.log(`🎙️  Topping Out Gaffer listening on http://${host}:${port}`);
    console.log(`   Brain: ${brainModel} via OpenRouter`);
    console.log(`   TTS:   Grok Voice (${voice}) via OpenRouter`);
    console.log(`   STT:   ${sttLabel}`);
    console.log(`   Mobile (Tailscale): set GAFFER_TOKEN or GAFFER_ALLOWED_TAILSCALE_USER, then run:`);
    console.log(`                       tailscale serve --bg --https=${port} http://127.0.0.1:${port}`);
    console.log("");
  });

  const shutdown = () => {
    console.log("\nShutting down Topping Out Gaffer...");
    void app.close().then(() => process.exit(0));
  };
  process.once("SIGINT", shutdown);
  process.once("SIGTERM", shutdown);
}

#!/usr/bin/env node

import { spawn, spawnSync } from "node:child_process";
import { createHash, randomBytes, randomUUID } from "node:crypto";
import fs from "node:fs";
import { request as httpsRequest } from "node:https";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { fileURLToPath, pathToFileURL } from "node:url";

import {
  AGENT_COUNCIL_LIMITS,
  AGENT_COUNCIL_MILESTONES,
  AGENT_COUNCIL_PANEL_PROFILES,
  AGENT_COUNCIL_SCHEMA_VERSION,
  BROKER_GATE_CATALOG,
  STOP_REASON_MAX_CHARS,
  AgentCouncilValidationError,
  adapterContract,
  assessTerminationProof,
  buildAuditClaimReferenceIndex,
  canonicalJson,
  canonicalSha256,
  deriveConsequentialDisagreements,
  evaluateRound3,
  filterEnvironment,
  nextMilestone,
  normalizeProbeReceipt,
  normalizeRelativePosixPath,
  parseAuditResponse,
  parseRunStateV2,
  validateAuditRevision,
  validateChairResponse,
  validateDisclosureManifest,
  validateResolvedProbeSpec,
  validateRoster,
  validateSeatResponse,
} from "./agent-council-core.mjs";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const SKILL_ROOT = path.resolve(SCRIPT_DIR, "..");
const DEFAULT_ROSTER_FILE = path.join(SKILL_ROOT, "references", "default-roster.json");
const RUN_FILE = ".agent-council-run.json";
const RESPONSE_FILE = ".agent-council-response.json";
const PROMPT_FILE = "AGENT_COUNCIL_PROMPT.md";
// Bounded outbound context the prompt points at instead of embedding. These sit
// in the seat root beside the prompt, never inside `workspace/`, whose bytes are
// digest-verified against the disclosure manifest before and after every copy.
// Every one of them is deleted before each attempt materializes a new set, so a
// retry can never read a previous attempt's context.
const DISCLOSURE_FILE = "AGENT_COUNCIL_DISCLOSURE.json";
const AUDIT_BUNDLE_FILE = "AGENT_COUNCIL_AUDIT_BUNDLE.json";
const ROUND_CONTEXT_FILE = "AGENT_COUNCIL_ROUND_CONTEXT.json";
const SEAT_CONTEXT_FILES = Object.freeze([DISCLOSURE_FILE, AUDIT_BUNDLE_FILE, ROUND_CONTEXT_FILE]);
const RAW_DIR = "raw";
const POSITIONS_DIR = "positions";
const CORPUS_DIR = "corpus";
const SEATS_DIR = "seats";
const AUDITOR_DIR = "auditor";
const WORKSPACE_DIR = "workspace";
const NATIVE_RUNTIME_DIR = "native-runtime";
// Runner-generated evidence lives here; a repository file under this path is
// never copied into a seat corpus, so generated evidence can never be forged.
const EVIDENCE_ROOT = ".agent-council-evidence";
const PROCESS_RECOVERY_MARKER = "agent-council-process-recovery";
const PROCESS_RECOVERY_OWNER_MARKER = "agent-council-process-recovery-owner";
const PROCESS_RECOVERY_OWNER_FILE = "owner.json";
const EXTERNAL_NETWORK_PREFLIGHT_TIMEOUT_MS = 10_000;

const SECRET_DETECTORS = Object.freeze([
  ["private-key-block", /-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----/],
  ["openrouter-key", /\bsk-or-v1-[A-Za-z0-9_-]{20,}\b/],
  ["openai-key", /\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b/],
  ["anthropic-key", /\bsk-ant-[A-Za-z0-9_-]{20,}\b/],
  ["github-token", /\bgh[pousr]_[A-Za-z0-9]{20,}\b/],
  ["aws-access-key", /\bAKIA[0-9A-Z]{16}\b/],
  ["slack-token", /\bxox[baprs]-[A-Za-z0-9-]{20,}\b/],
  ["bearer-token", /\bBearer\s+[A-Za-z0-9._~-]{32,}\b/i],
]);

const LOCAL_SECRET_BASENAMES = new Set([
  ".mcp.json",
  "credentials.json",
  "secrets.json",
  "settings.local.json",
  "id_rsa",
  "id_ed25519",
]);

const DANGEROUS_EXTENSIONS = new Set([
  ".7z", ".a", ".apk", ".app", ".bin", ".bz2", ".class", ".db", ".dll", ".dmg",
  ".dylib", ".ear", ".exe", ".gz", ".iso", ".jar", ".lib", ".mdb", ".msi", ".o",
  ".obj", ".p12", ".pfx", ".pyc", ".rar", ".so", ".sqlite", ".sqlite3", ".tar",
  ".war", ".xz", ".zip",
]);

const BENIGN_BINARY_EXTENSIONS = new Set([
  ".avif", ".gif", ".ico", ".jpeg", ".jpg", ".pdf", ".png", ".ttf", ".webp", ".woff", ".woff2",
]);

export class AgentCouncilRunnerError extends Error {
  constructor(code, details = {}) {
    super(code);
    this.name = "AgentCouncilRunnerError";
    this.code = code;
    this.details = details;
  }
}

function runnerFail(code, details) {
  throw new AgentCouncilRunnerError(code, details);
}

export function checkExternalModelNetwork(options = {}) {
  const requestFactory = options.request ?? httpsRequest;
  const timeoutMs = Number.isFinite(options.timeoutMs) && options.timeoutMs > 0
    ? options.timeoutMs
    : EXTERNAL_NETWORK_PREFLIGHT_TIMEOUT_MS;
  return new Promise((resolve) => {
    let settled = false;
    let timer = null;
    const finish = (observation) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(observation);
    };
    let request;
    try {
      request = requestFactory({
        hostname: "openrouter.ai",
        port: 443,
        path: "/api/v1/models",
        method: "HEAD",
        headers: { "User-Agent": "agent-council-preflight" },
      }, (response) => {
        response.resume();
        finish({ reachable: true, statusCode: Number.isInteger(response.statusCode) ? response.statusCode : null });
      });
    } catch (error) {
      finish({ reachable: false, failureCode: safeFailureToken(error?.code ?? error?.name ?? "REQUEST_FAILED") });
      return;
    }
    timer = setTimeout(() => {
      finish({ reachable: false, failureCode: "TIMEOUT" });
      request.destroy();
    }, timeoutMs);
    request.once("error", (error) => {
      finish({ reachable: false, failureCode: safeFailureToken(error?.code ?? error?.name ?? "REQUEST_FAILED") });
    });
    request.end();
  });
}

function sha256Bytes(value) {
  return `sha256:${createHash("sha256").update(value).digest("hex")}`;
}

function parseJsonBytes(buffer, label) {
  try {
    return JSON.parse(buffer.toString("utf8"));
  } catch {
    runnerFail("INVALID_JSON_FILE", { label });
  }
}

function stableWriteJson(io, file, value) {
  io.writeFileAtomic(file, `${JSON.stringify(value, null, 2)}\n`);
}

function stableWriteRecoveryJson(io, file, value) {
  io.writeFileAtomicExact(file, `${JSON.stringify(value, null, 2)}\n`);
}

export function writeFileAtomicWithRetry(file, value, options = {}) {
  const filesystem = options.filesystem ?? fs;
  const newId = options.newId ?? randomUUID;
  const sleep = options.sleep ?? ((milliseconds) => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, milliseconds));
  const renameAttempts = options.renameAttempts ?? 5;
  const retryDelayMs = options.retryDelayMs ?? 10;
  const createParent = options.createParent ?? true;
  const temporary = `${file}.tmp-${newId()}`;
  let renamed = false;
  try {
    if (createParent) filesystem.mkdirSync(path.dirname(file), { recursive: true });
    filesystem.writeFileSync(temporary, value);
    for (let attempt = 1; attempt <= renameAttempts; attempt += 1) {
      try {
        filesystem.renameSync(temporary, file);
        renamed = true;
        return;
      } catch (error) {
        const retryable = error?.code === "EPERM" || error?.code === "EBUSY";
        if (!retryable || attempt === renameAttempts) throw error;
        sleep(retryDelayMs * attempt);
      }
    }
  } finally {
    if (!renamed) {
      try { filesystem.rmSync(temporary, { force: true }); } catch { /* preserve the atomic-write error */ }
    }
  }
}

function mutableData(value) {
  return JSON.parse(canonicalJson(value));
}

function pathInside(root, candidate) {
  const normalize = (value) => process.platform === "win32" ? path.resolve(value).toLowerCase() : path.resolve(value);
  const base = normalize(root);
  const resolved = normalize(candidate);
  return resolved === base || resolved.startsWith(`${base}${path.sep}`);
}

function exactTempChild(runDirectory, tempRoot) {
  const resolved = path.resolve(runDirectory);
  const temp = path.resolve(tempRoot);
  return resolved !== temp && pathInside(temp, resolved);
}

function parseCliArgs(tokens) {
  const output = { _: [] };
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    if (!token.startsWith("--")) {
      output._.push(token);
      continue;
    }
    const key = token.slice(2);
    const next = tokens[index + 1];
    const value = next !== undefined && !next.startsWith("--") ? tokens[++index] : true;
    if (output[key] === undefined) output[key] = value;
    else if (Array.isArray(output[key])) output[key].push(value);
    else output[key] = [output[key], value];
  }
  return output;
}

export { parseCliArgs };

function cliValues(args, key) {
  if (args[key] === undefined) return [];
  return Array.isArray(args[key]) ? args[key] : [args[key]];
}

function cliValue(args, key, { required = false } = {}) {
  const value = args[key];
  if (Array.isArray(value)) runnerFail("DUPLICATE_CLI_OPTION", { option: key });
  if (required && (value === undefined || value === true || value === "")) runnerFail("MISSING_CLI_OPTION", { option: key });
  return value;
}

function rejectV1Cli(args) {
  if (args["host-family"] !== undefined) runnerFail("V1_HOST_FAMILY_UNSUPPORTED_USE_HOST_ID");
  if (args["approve-source-sharing"] !== undefined) runnerFail("V1_BOOLEAN_APPROVAL_UNSUPPORTED_USE_MANIFEST_SHA");
  if (args["allow-command"] !== undefined) runnerFail("V1_SEAT_COMMAND_UNSUPPORTED_USE_PROBE_GATE");
}

function readRequiredText(io, file, label, maxBytes = 1024 * 1024) {
  const resolved = path.resolve(file);
  const bytes = io.readFile(resolved);
  if (bytes.length === 0 || bytes.length > maxBytes) runnerFail("INVALID_TEXT_FILE_SIZE", { label, maxBytes });
  const textValue = bytes.toString("utf8");
  if (!textValue.trim()) runnerFail("EMPTY_TEXT_FILE", { label });
  return { resolved, bytes, text: textValue };
}

function scanSecretBytes(bytes) {
  const textValue = bytes.toString("utf8");
  for (const [detector, pattern] of SECRET_DETECTORS) if (pattern.test(textValue)) return detector;
  return null;
}

function gitChecked(repo, args, options = {}) {
  const safeDirectory = path.resolve(repo).replaceAll("\\", "/");
  const result = spawnSync("git", ["-c", `safe.directory=${safeDirectory}`, "-C", repo, ...args], {
    encoding: options.encoding === null ? null : "utf8",
    maxBuffer: options.maxBuffer ?? 128 * 1024 * 1024,
    windowsHide: true,
  });
  if (result.error || result.status !== 0) runnerFail("GIT_COMMAND_FAILED", { operation: args[0], status: result.status });
  return result.stdout;
}

function executableFromPath(name, environment) {
  const pathValue = environment.PATH ?? environment.Path ?? environment.path ?? "";
  const extensions = process.platform === "win32"
    ? (environment.PATHEXT ?? ".COM;.EXE;.BAT;.CMD").split(";")
    : [""];
  for (const directory of pathValue.split(path.delimiter).filter(Boolean)) {
    for (const extension of extensions) {
      const candidate = path.resolve(directory, process.platform === "win32" ? `${name}${extension}` : name);
      if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) return candidate;
    }
  }
  return null;
}

function resolveNpmInstallation(environment) {
  const launcherPath = executableFromPath("npm", environment);
  if (!launcherPath) runnerFail("NPM_LAUNCHER_NOT_FOUND");
  const launcherBytes = fs.readFileSync(launcherPath);
  const launcherText = launcherBytes.toString("utf8");
  const candidates = [
    path.resolve(path.dirname(launcherPath), "node_modules", "npm", "bin", "npm-cli.js"),
    path.resolve(path.dirname(process.execPath), "node_modules", "npm", "bin", "npm-cli.js"),
    path.resolve(path.dirname(launcherPath), "..", "lib", "node_modules", "npm", "bin", "npm-cli.js"),
  ];
  const embedded = launcherText.match(/(?:node_modules[\\/]npm[\\/]bin[\\/]npm-cli\.js|npm[\\/]bin[\\/]npm-cli\.js)/i)?.[0];
  if (embedded) candidates.unshift(path.resolve(path.dirname(launcherPath), embedded.replaceAll("%dp0%", "")));
  const npmCliPath = candidates.find((candidate) => fs.existsSync(candidate) && fs.statSync(candidate).isFile());
  if (!npmCliPath) runnerFail("NPM_CLI_NOT_FOUND");
  const npmPackage = path.resolve(npmCliPath, "..", "..", "package.json");
  const npmVersion = fs.existsSync(npmPackage) ? JSON.parse(fs.readFileSync(npmPackage, "utf8")).version : "unknown";
  return {
    launcherPath,
    launcherSha256: sha256Bytes(launcherBytes),
    npmCliPath,
    npmCliSha256: sha256Bytes(fs.readFileSync(npmCliPath)),
    npmVersion,
  };
}

function nativeCliExecutable(adapterName, environment) {
  if (adapterName === "claude-cli" && process.platform === "win32") {
    const appData = environment.APPDATA;
    const executable = appData
      ? path.resolve(appData, "npm", "node_modules", "@anthropic-ai", "claude-code", "bin", "claude.exe")
      : null;
    if (executable && fs.existsSync(executable) && fs.statSync(executable).isFile()) return executable;
  }
  const command = adapterName === "claude-cli" ? "claude" : adapterName === "grok-cli" ? "grok" : null;
  if (!command) runnerFail("UNKNOWN_SEAT_ADAPTER", { adapterName });
  const executable = executableFromPath(command, environment);
  if (!executable) runnerFail("NATIVE_CLI_LAUNCHER_NOT_FOUND", { adapterName });
  return executable;
}

function nativeCliInvocation(adapterName, args, environment) {
  return { command: nativeCliExecutable(adapterName, environment), args };
}

function spawnSyncChecked(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: options.cwd,
    env: options.env,
    encoding: "utf8",
    maxBuffer: options.maxBuffer ?? 16 * 1024 * 1024,
    windowsHide: true,
    shell: false,
    timeout: options.timeoutMs,
  });
  // Preflight failures are diagnosed from the child's own words, and the pi
  // preflight child *does* hold OPENROUTER_API_KEY, so its stderr is not
  // credential-free by construction: a CLI that echoes the key it rejected
  // would otherwise print that key to the operator's terminal and into every
  // captured log. The slice is safe only because it is scanned first — on a
  // match the bytes are dropped and only the detector name survives, which
  // still separates "the CLI is absent" from "the CLI is installed and
  // complaining". The scan reads the child's whole stderr rather than the
  // retained 512 bytes, because a credential straddling that boundary would
  // otherwise survive as a sub-detector-length prefix no pattern matches.
  if (result.error || result.status !== 0) {
    const full = String(result.stderr ?? "").trim();
    const raw = full.slice(0, 512);
    const detector = scanSecretBytes(Buffer.from(full, "utf8"));
    runnerFail(options.errorCode ?? "PROCESS_FAILED", {
      status: result.status,
      spawn: result.error ? safeFailureToken(result.error.code ?? result.error.name) : null,
      ...(detector ? { stderrRedacted: detector } : { stderr: raw }),
    });
  }
  return result.stdout;
}

function parsedCliVersion(adapterName, output) {
  const text = String(output ?? "").trim();
  const match = adapterName === "claude-cli"
    ? text.match(/^(\d+\.\d+\.\d+)(?:\s|$)/)
    : text.match(/^grok\s+(\d+\.\d+\.\d+)(?:\s|$)/i);
  if (!match) runnerFail("NATIVE_CLI_VERSION_SCHEMA_INVALID", { adapterName });
  return match[1];
}

function nativeAuthEnvironment(environment) {
  const output = { ...filterEnvironment(environment) };
  for (const key of ["USERPROFILE", "HOME", "APPDATA", "LOCALAPPDATA", "GROK_HOME"]) {
    if (typeof environment[key] === "string" && environment[key]) output[key] = environment[key];
  }
  output.NO_COLOR = "1";
  return output;
}

export function buildClaudeModelPreflightArgs(model = "claude-opus-5") {
  const modelSchema = JSON.stringify({
    type: "object",
    properties: { status: { type: "string", const: "available" } },
    required: ["status"],
    additionalProperties: false,
  });
  return [
    "-p", "Return the structured status value available.",
    "--model", model,
    "--safe-mode",
    "--disable-slash-commands",
    "--strict-mcp-config",
    "--tools", "",
    "--permission-mode", "plan",
    "--no-session-persistence",
    "--output-format", "json",
    "--json-schema", modelSchema,
  ];
}

function verifyClaudeModelEntitlement(io, model) {
  const environment = nativeAuthEnvironment(io.hostEnvironment);
  const modelArgs = buildClaudeModelPreflightArgs(model);
  const modelInvocation = nativeCliInvocation("claude-cli", modelArgs, io.hostEnvironment);
  const modelOutput = spawnSyncChecked(modelInvocation.command, modelInvocation.args, {
    env: environment,
    errorCode: "CLAUDE_MODEL_PREFLIGHT_FAILED",
    timeoutMs: 120_000,
  });
  const modelResponse = parseNativeStructuredResponse("claude-cli", modelOutput);
  if (modelResponse?.status !== "available") runnerFail("NATIVE_CLI_MODEL_UNAVAILABLE", { adapterName: "claude-cli", model });
}

function preflightNativeAdapter(io, adapterName) {
  const environment = nativeAuthEnvironment(io.hostEnvironment);
  const versionOutput = spawnSyncChecked(
    nativeCliInvocation(adapterName, ["--version"], io.hostEnvironment).command,
    ["--version"],
    { env: environment, errorCode: "NATIVE_CLI_VERSION_PREFLIGHT_FAILED", timeoutMs: 30_000 },
  );
  const version = parsedCliVersion(adapterName, versionOutput);
  // Fails closed on an adapter with no declared row: no pin, no qualification.
  if (adapterContract(adapterName)?.version !== version) {
    runnerFail("NATIVE_CLI_VERSION_MISMATCH", { adapterName, version });
  }
  if (adapterName === "claude-cli") {
    const invocation = nativeCliInvocation(adapterName, ["auth", "status", "--json"], io.hostEnvironment);
    const authOutput = spawnSyncChecked(invocation.command, invocation.args, {
      env: environment,
      errorCode: "CLAUDE_AUTH_PREFLIGHT_FAILED",
      timeoutMs: 30_000,
    });
    let status;
    try {
      status = JSON.parse(authOutput);
    } catch {
      // The CLI answered, but not in the contracted shape. That is a named
      // preflight failure, not a raw SyntaxError escaping the transport table.
      runnerFail("CLAUDE_AUTH_SCHEMA_INVALID", { adapterName });
    }
    if (status?.loggedIn !== true || status?.authMethod !== "claude.ai") runnerFail("CLAUDE_SUBSCRIPTION_AUTH_REQUIRED");
    const model = "claude-opus-5";
    return { adapterName, version, models: [model] };
  }
  const invocation = nativeCliInvocation(adapterName, ["models"], io.hostEnvironment);
  const output = spawnSyncChecked(invocation.command, invocation.args, {
    env: environment,
    errorCode: "NATIVE_CLI_MODEL_PREFLIGHT_FAILED",
    maxBuffer: 64 * 1024 * 1024,
    timeoutMs: 60_000,
  });
  const requiredModel = "grok-4.6";
  if (!String(output).includes(requiredModel)) runnerFail("NATIVE_CLI_MODEL_UNAVAILABLE", { adapterName, model: requiredModel });
  return { adapterName, version, models: [requiredModel] };
}

/**
 * Whole-panel transport preflight. The pi door is mandatory: every
 * OpenRouter-hosted seat rides it, so a pi failure is a hard runner failure.
 * Native subscription CLIs are optional — an unavailable one is a named,
 * recorded degradation that removes only its own rows from the model set.
 */
function preflightAllTransports(io, environment) {
  const transports = [io.preflightPi(environment)];
  const unavailable = [];
  for (const adapterName of ["claude-cli", "grok-cli"]) {
    try {
      transports.push(preflightNativeAdapter(io, adapterName));
    } catch (error) {
      // Only a runner/validation failure is a *named* transport degradation. An
      // internal defect (a TypeError, a programming error) must never be
      // laundered into "this CLI is unavailable" — it propagates and fails
      // prepare so the defect is seen instead of silently shrinking the panel.
      if (!(error instanceof AgentCouncilRunnerError || error instanceof AgentCouncilValidationError)) throw error;
      unavailable.push({
        adapterName,
        failureCode: safeFailureToken(error.code),
        ...(error.details ? { details: error.details } : {}),
      });
    }
  }
  return {
    transports,
    unavailable,
    models: [...new Set(transports.flatMap((transport) => transport.models))],
  };
}

const WINDOWS_PROCESS_SNAPSHOT_SCRIPT = [
  "$ErrorActionPreference='Stop';",
  "$source=@'",
  "using System;",
  "using System.Collections.Generic;",
  "using System.Runtime.InteropServices;",
  "public static class AgentCouncilProcessSnapshot {",
  "  [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]",
  "  private struct PROCESSENTRY32 {",
  "    public uint dwSize; public uint cntUsage; public uint th32ProcessID; public IntPtr th32DefaultHeapID;",
  "    public uint th32ModuleID; public uint cntThreads; public uint th32ParentProcessID; public int pcPriClassBase; public uint dwFlags;",
  "    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string szExeFile;",
  "  }",
  "  [DllImport(\"kernel32.dll\", SetLastError = true)] private static extern IntPtr CreateToolhelp32Snapshot(uint flags, uint processId);",
  "  [DllImport(\"kernel32.dll\", SetLastError = true, CharSet = CharSet.Unicode)] private static extern bool Process32FirstW(IntPtr snapshot, ref PROCESSENTRY32 entry);",
  "  [DllImport(\"kernel32.dll\", SetLastError = true, CharSet = CharSet.Unicode)] private static extern bool Process32NextW(IntPtr snapshot, ref PROCESSENTRY32 entry);",
  "  [DllImport(\"kernel32.dll\")] private static extern bool CloseHandle(IntPtr handle);",
  "  public static string Json() {",
  "    IntPtr snapshot = CreateToolhelp32Snapshot(2, 0);",
  "    if (snapshot == new IntPtr(-1)) throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());",
  "    try {",
  "      var rows = new List<string>(); var entry = new PROCESSENTRY32(); entry.dwSize = (uint)Marshal.SizeOf(typeof(PROCESSENTRY32));",
  "      if (Process32FirstW(snapshot, ref entry)) do { rows.Add(\"{\\\"pid\\\":\" + entry.th32ProcessID + \",\\\"parent\\\":\" + entry.th32ParentProcessID + \"}\"); } while (Process32NextW(snapshot, ref entry));",
  "      return \"[\" + string.Join(\",\", rows) + \"]\";",
  "    } finally { CloseHandle(snapshot); }",
  "  }",
  "}",
  "'@;",
  "Add-Type -TypeDefinition $source;",
  "[AgentCouncilProcessSnapshot]::Json()",
].join("\n");

function windowsProcessSnapshot(environment) {
  const powerShell = path.resolve(environment.SystemRoot ?? "C:\\Windows", "System32", "WindowsPowerShell", "v1.0", "powershell.exe");
  const result = spawnSync(powerShell, ["-NoProfile", "-NonInteractive", "-Command", WINDOWS_PROCESS_SNAPSHOT_SCRIPT], { encoding: "utf8", windowsHide: true, timeout: 10_000 });
  if (result.error || result.status !== 0) return { complete: false, rows: [] };
  try {
    const parsed = JSON.parse(result.stdout.trim() || "[]");
    if (!Array.isArray(parsed)) return { complete: false, rows: [] };
    const rows = parsed.map((row) => ({ pid: Number(row?.pid), parent: Number(row?.parent) }))
      .filter((row) => Number.isSafeInteger(row.pid) && Number.isSafeInteger(row.parent));
    return { complete: true, rows };
  } catch {
    return { complete: false, rows: [] };
  }
}

function windowsProcessTree(rootPid, environment) {
  const snapshot = windowsProcessSnapshot(environment);
  if (!snapshot.complete) return { complete: false, pids: [rootPid], failureCode: "PROCESS_DISCOVERY_FAILED" };
  const children = new Map();
  for (const row of snapshot.rows) {
    const list = children.get(row.parent) ?? [];
    list.push(row.pid);
    children.set(row.parent, list);
  }
  const seen = new Set();
  const todo = [rootPid];
  while (todo.length) {
    const pid = todo.shift();
    if (seen.has(pid)) continue;
    seen.add(pid);
    todo.push(...(children.get(pid) ?? []));
  }
  return { complete: true, pids: [...seen] };
}

function posixProcessTree(rootPid) {
  const result = spawnSync("ps", ["-eo", "pid=,ppid="], { encoding: "utf8", windowsHide: true, timeout: 10_000 });
  if (result.error || result.status !== 0) return { complete: false, pids: [rootPid], failureCode: "PROCESS_DISCOVERY_FAILED" };
  const children = new Map();
  for (const line of result.stdout.split(/\r?\n/)) {
    const [pid, parent] = line.trim().split(/\s+/).map(Number);
    if (!Number.isSafeInteger(pid) || !Number.isSafeInteger(parent)) continue;
    const list = children.get(parent) ?? [];
    list.push(pid);
    children.set(parent, list);
  }
  const seen = new Set();
  const todo = [rootPid];
  while (todo.length) {
    const pid = todo.shift();
    if (seen.has(pid)) continue;
    seen.add(pid);
    todo.push(...(children.get(pid) ?? []));
  }
  return { complete: true, pids: [...seen] };
}

function pidAlive(pid) {
  try {
    process.kill(pid, 0);
    return { complete: true, alive: true };
  } catch (error) {
    if (error?.code === "ESRCH") return { complete: true, alive: false };
    return { complete: false, alive: true, failureCode: "PROCESS_LIVENESS_FAILED" };
  }
}

function windowsAlivePids(pids, environment) {
  if (!pids.length) return { complete: true, alivePids: [] };
  const snapshot = windowsProcessSnapshot(environment);
  if (!snapshot.complete) return { complete: false, alivePids: [...pids], failureCode: "PROCESS_LIVENESS_FAILED" };
  const observed = new Set(snapshot.rows.map((row) => row.pid));
  return { complete: true, alivePids: [...new Set(pids.filter((pid) => observed.has(pid)))] };
}

function defaultProcessAdapter(platform, environment) {
  return {
    discover(rootPid) {
      return platform === "win32" ? windowsProcessTree(rootPid, environment) : posixProcessTree(rootPid);
    },
    observeIdentity(pid) {
      if (!Number.isSafeInteger(pid) || pid <= 0) return { complete: false, exists: false, failureCode: "PROCESS_IDENTITY_PID_INVALID" };
      if (platform === "win32") {
        const powerShell = path.resolve(environment.SystemRoot ?? "C:\\Windows", "System32", "WindowsPowerShell", "v1.0", "powershell.exe");
        const script = `$ErrorActionPreference='Stop';$p=Get-Process -Id ${pid} -ErrorAction SilentlyContinue|Select-Object StartTime,Path;if($null -eq $p){'null'}else{[pscustomobject]@{CreationDate=$p.StartTime.ToUniversalTime().ToString('o');ExecutablePath=$p.Path}|ConvertTo-Json -Compress}`;
        const result = spawnSync(powerShell, ["-NoProfile", "-NonInteractive", "-Command", script], { encoding: "utf8", windowsHide: true, timeout: 10_000 });
        if (result.error || result.status !== 0) return { complete: false, exists: true, failureCode: "PROCESS_IDENTITY_FAILED" };
        try {
          const value = JSON.parse(result.stdout.trim() || "null");
          if (value === null) return { complete: true, exists: false };
          if (typeof value.CreationDate !== "string" || typeof value.ExecutablePath !== "string") return { complete: false, exists: true, failureCode: "PROCESS_IDENTITY_SCHEMA_INVALID" };
          return { complete: true, exists: true, processIdentity: { creationId: value.CreationDate, executable: value.ExecutablePath } };
        } catch {
          return { complete: false, exists: true, failureCode: "PROCESS_IDENTITY_SCHEMA_INVALID" };
        }
      }
      if (platform === "linux") {
        try {
          const stat = fs.readFileSync(`/proc/${pid}/stat`, "utf8");
          const fields = stat.slice(stat.lastIndexOf(")") + 2).trim().split(/\s+/);
          const creationId = fields[19];
          const executable = fs.realpathSync(`/proc/${pid}/exe`);
          if (!creationId || !executable) return { complete: false, exists: true, failureCode: "PROCESS_IDENTITY_SCHEMA_INVALID" };
          return { complete: true, exists: true, processIdentity: { creationId, executable } };
        } catch (error) {
          if (["ENOENT", "ESRCH"].includes(error?.code)) return { complete: true, exists: false };
          return { complete: false, exists: true, failureCode: "PROCESS_IDENTITY_FAILED" };
        }
      }
      const result = spawnSync("ps", ["-p", String(pid), "-o", "lstart=", "-o", "comm="], { encoding: "utf8", windowsHide: true, timeout: 10_000 });
      if (result.status === 1 && !result.error) return { complete: true, exists: false };
      if (result.error || result.status !== 0) return { complete: false, exists: true, failureCode: "PROCESS_IDENTITY_FAILED" };
      const value = result.stdout.trim();
      if (!value) return { complete: true, exists: false };
      return { complete: true, exists: true, processIdentity: { creationId: value.slice(0, 24).trim(), executable: value.slice(24).trim() } };
    },
    terminate(expected) {
      if (platform === "win32") {
        const result = spawnSync("taskkill", ["/PID", String(expected.pid), "/T", "/F"], { encoding: "utf8", windowsHide: true, timeout: 15_000 });
        // taskkill may return nonzero when a discovered descendant exits during
        // the kill. Preserve that failure while still letting the mandatory
        // post-attempt snapshot prove a benign all-absent race.
        if (result.error) return { complete: false, failureCode: "PROCESS_TERMINATION_FAILED" };
        return result.status === 0
          ? { complete: true }
          : { complete: true, failureCode: "PROCESS_TERMINATION_COMMAND_FAILED" };
      }
      try {
        process.kill(-(expected.processGroupId ?? expected.pid), "SIGKILL");
        return { complete: true };
      } catch (groupError) {
        if (groupError?.code !== "ESRCH") return { complete: false, failureCode: "PROCESS_TERMINATION_FAILED" };
        try {
          process.kill(expected.pid, "SIGKILL");
          return { complete: true };
        } catch (rootError) {
          if (rootError?.code === "ESRCH") return { complete: true };
          return { complete: false, failureCode: "PROCESS_TERMINATION_FAILED" };
        }
      }
    },
    alive(pids) {
      if (platform === "win32") return windowsAlivePids(pids, environment);
      const alivePids = [];
      for (const pid of pids) {
        const observation = pidAlive(pid);
        if (!observation.complete) return { complete: false, alivePids: [...pids], failureCode: observation.failureCode };
        if (observation.alive) alivePids.push(pid);
      }
      return { complete: true, alivePids };
    },
  };
}

function sameProcessIdentity(left, right) {
  return left && right && left.creationId === right.creationId && left.executable === right.executable;
}

async function terminateOwnedTree(expected, environment, options = {}) {
  const adapter = options.processAdapter ?? defaultProcessAdapter(process.platform, environment);
  const handleOwned = options.ownedHandle != null;
  let identityVerified = false;
  if (!handleOwned) {
    const identity = await adapter.observeIdentity(expected.pid);
    if (identity?.complete && identity.exists === false) {
      return { complete: true, rootPid: expected.pid, processGroupId: expected.processGroupId, descendantPids: [], alivePids: [], identityVerified: false, handleOwned: false, processAbsent: true };
    }
    if (!identity?.complete || !sameProcessIdentity(expected.processIdentity, identity.processIdentity)) {
      return { complete: false, rootPid: expected.pid, processGroupId: expected.processGroupId, descendantPids: [], alivePids: [expected.pid], identityVerified: false, handleOwned: false, failureCode: !identity?.complete ? identity?.failureCode ?? "PROCESS_IDENTITY_FAILED" : "PROCESS_IDENTITY_MISMATCH" };
    }
    identityVerified = true;
  }
  const discovery = await adapter.discover(expected.pid);
  const descendants = Array.isArray(discovery?.pids) ? discovery.pids : [expected.pid];
  if (!discovery?.complete) {
    if (handleOwned) {
      await adapter.terminate(expected, options.ownedHandle);
      try { options.ownedHandle.kill("SIGKILL"); } catch { /* termination remains explicitly unverified below */ }
    }
    return { complete: false, rootPid: expected.pid, processGroupId: expected.processGroupId, descendantPids: descendants.filter((pid) => pid !== expected.pid), alivePids: descendants, identityVerified, handleOwned, failureCode: discovery?.failureCode ?? "PROCESS_DISCOVERY_FAILED" };
  }
  const termination = await adapter.terminate(expected, options.ownedHandle);
  if (!termination?.complete) return { complete: false, rootPid: expected.pid, processGroupId: expected.processGroupId, descendantPids: descendants.filter((pid) => pid !== expected.pid), alivePids: descendants, identityVerified, handleOwned, failureCode: termination?.failureCode ?? "PROCESS_TERMINATION_FAILED" };
  let liveness = await adapter.alive(descendants);
  if (!liveness?.complete) return { complete: false, rootPid: expected.pid, processGroupId: expected.processGroupId, descendantPids: descendants.filter((pid) => pid !== expected.pid), alivePids: liveness?.alivePids ?? descendants, identityVerified, handleOwned, failureCode: liveness?.failureCode ?? "PROCESS_LIVENESS_FAILED" };
  let alivePids = liveness.alivePids;
  // Windows process snapshots start a fresh bounded PowerShell/Add-Type helper.
  // Under load, a single liveness observation can consume most of two seconds
  // even after taskkill has accepted the tree. Keep polling an accepted kill
  // long enough to distinguish observation lag from a genuine survivor; a
  // failed kill receives only the immediate all-absent race proof above.
  const deadline = Date.now() + (termination.failureCode ? 0 : process.platform === "win32" ? 10_000 : 2_000);
  while (alivePids.length && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 50));
    liveness = await adapter.alive(descendants);
    if (!liveness?.complete) return { complete: false, rootPid: expected.pid, processGroupId: expected.processGroupId, descendantPids: descendants.filter((pid) => pid !== expected.pid), alivePids: liveness?.alivePids ?? descendants, identityVerified, handleOwned, failureCode: liveness?.failureCode ?? "PROCESS_LIVENESS_FAILED" };
    alivePids = liveness.alivePids;
  }
  return {
    complete: true,
    rootPid: expected.pid,
    processGroupId: expected.processGroupId,
    descendantPids: descendants.filter((pid) => pid !== expected.pid),
    alivePids,
    identityVerified,
    handleOwned,
    ...(termination.failureCode ? { failureCode: termination.failureCode } : {}),
  };
}

const WINDOWS_PROCESS_BROKER_SOURCE = [
  "const { spawn } = require('node:child_process');",
  "const command = process.env.AGENT_COUNCIL_BROKER_COMMAND;",
  "const args = JSON.parse(process.env.AGENT_COUNCIL_BROKER_ARGS || '[]');",
  "delete process.env.AGENT_COUNCIL_BROKER_COMMAND;",
  "delete process.env.AGENT_COUNCIL_BROKER_ARGS;",
  "let settled = false;",
  "setTimeout(() => {",
  "  const target = spawn(command, args, { cwd: process.cwd(), env: process.env, windowsHide: true, shell: false, stdio: ['ignore', 'inherit', 'inherit'] });",
  "  target.once('error', () => { if (!settled) { settled = true; process.exitCode = 1; } });",
  "  target.once('close', (code) => { if (!settled) { settled = true; process.exitCode = Number.isInteger(code) ? code : 1; } });",
  "}, 750);",
].join("\n");

function processInvocation(invocation, environment) {
  if (process.platform !== "win32") return { ...invocation, environment };
  return {
    command: process.execPath,
    args: ["--input-type=commonjs", "-e", WINDOWS_PROCESS_BROKER_SOURCE],
    environment: {
      ...environment,
      AGENT_COUNCIL_BROKER_COMMAND: invocation.command,
      AGENT_COUNCIL_BROKER_ARGS: JSON.stringify(invocation.args),
    },
  };
}

/**
 * How much raw stdout a *filtered* caller may push through before the same
 * `OUTPUT_LIMIT` kill fires, as a multiple of its retained `maxOutputBytes`.
 *
 * Measured, not guessed. Two live pi seat runs (on the workspace this skill was
 * built in) died at the
 * 4 MiB raw cap, and both had the same composition: 2026-09-02 kept ~582 KiB of
 * 4,178,920 raw bytes (7.2x) and 2026-09-03 kept ~536 KiB of 4,190,384 (7.8x),
 * the rest being `message_update` deltas plus `message_start`, `turn_end`, and
 * `tool_execution_end` events the runner never reads. 8x is the next whole
 * multiple above the worse observed ratio, so a seat with that composition can
 * spend its entire 4 MiB retained budget without the raw ceiling firing first,
 * while a model that emits nothing but unread deltas is still killed and named
 * at 32 MiB instead of streaming forever. The ceiling is not a softening of the
 * cap: crossing it is the identical fail-closed `OUTPUT_LIMIT` path.
 */
const FILTERED_RAW_INPUT_MULTIPLE = 8;

/**
 * Spawn a bounded child. `options.lineFilter`, when supplied, is a per-line
 * stdout predicate: only retained lines are kept and only retained bytes count
 * against `options.maxOutputBytes`. With no filter this is unchanged — whole
 * chunks are counted and kept exactly as before, for stdout and stderr alike.
 * stderr is never filtered; it is small, it is the operator's transport channel,
 * and it keeps counting against the retained cap on both paths.
 */
async function spawnBounded(invocation, options) {
  return new Promise((resolve, reject) => {
    const launched = processInvocation(invocation, options.env);
    const child = spawn(launched.command, launched.args, {
      cwd: options.cwd,
      env: launched.environment,
      windowsHide: true,
      shell: false,
      detached: process.platform !== "win32",
      stdio: ["ignore", "pipe", "pipe"],
    });
    const stdout = [];
    const stderr = [];
    let outputBytes = 0;
    let outputLimited = false;
    let settled = false;
    let timer = null;
    let finish;
    let identityUnverified = false;
    let identityTerminationObservation = null;
    const capture = (target) => (chunk) => {
      if (outputLimited) return;
      outputBytes += chunk.length;
      if (outputBytes > options.maxOutputBytes) {
        outputLimited = true;
        void finish({ code: null, timedOut: false, spawnError: null });
        return;
      }
      target.push(Buffer.from(chunk));
    };
    // Optional stdout line filter. Absent one, `capture` above is the only
    // reader and nothing below runs.
    const lineFilter = typeof options.lineFilter === "function" ? options.lineFilter : null;
    const maxRawInputBytes = lineFilter ? options.maxOutputBytes * FILTERED_RAW_INPUT_MULTIPLE : options.maxOutputBytes;
    let rawInputBytes = 0;
    let retainedBytes = 0;
    let droppedLines = 0;
    let droppedBytes = 0;
    // The incomplete tail, held as chunks and joined only when a newline
    // arrives, so a long unterminated run costs one concatenation instead of
    // one per chunk.
    let pendingChunks = [];
    let pendingBytes = 0;
    const tripOutputLimit = () => {
      outputLimited = true;
      void finish({ code: null, timedOut: false, spawnError: null });
    };
    // A complete line, newline included. Retained lines are pushed as the exact
    // bytes the child wrote; a line that would cross the retained cap is not
    // pushed, which is what an unfiltered over-cap chunk already does.
    const consumeLine = (line) => {
      if (!lineFilter(line.toString("utf8"))) {
        droppedLines += 1;
        droppedBytes += line.length;
        return true;
      }
      outputBytes += line.length;
      if (outputBytes > options.maxOutputBytes) return false;
      retainedBytes += line.length;
      stdout.push(line);
      return true;
    };
    const captureFiltered = (chunk) => {
      if (outputLimited) return;
      // The raw ceiling is checked before any parsing: a child that emits
      // nothing the runner reads must still die, and die by name.
      rawInputBytes += chunk.length;
      if (rawInputBytes > maxRawInputBytes) return tripOutputLimit();
      // stdout arrives in arbitrary chunks and a JSON line can straddle two, so
      // the incomplete tail is buffered and only complete lines are decided.
      // Splitting on 0x0a is byte-safe: a newline can never occur inside a
      // multi-byte UTF-8 sequence, so every decided line decodes whole.
      const incoming = Buffer.from(chunk);
      if (incoming.indexOf(0x0a) === -1) {
        pendingChunks.push(incoming);
        pendingBytes += incoming.length;
        return;
      }
      const buffer = pendingBytes ? Buffer.concat([...pendingChunks, incoming], pendingBytes + incoming.length) : incoming;
      pendingChunks = [];
      pendingBytes = 0;
      let start = 0;
      for (let index = buffer.indexOf(0x0a, start); index !== -1; index = buffer.indexOf(0x0a, start)) {
        if (!consumeLine(buffer.subarray(start, index + 1))) return tripOutputLimit();
        start = index + 1;
      }
      if (start < buffer.length) {
        pendingChunks = [buffer.subarray(start)];
        pendingBytes = buffer.length - start;
      }
    };
    // A trailing partial line at EOF is decided by the same predicate as a
    // complete one and retained when it passes: it is the last thing the
    // transport said before it stopped, and `parsePiJsonStream` already skips a
    // line it cannot parse. It is never exempt from the retained cap.
    const flushPendingLine = () => {
      if (!lineFilter || outputLimited || !pendingBytes) return;
      const tail = Buffer.concat(pendingChunks, pendingBytes);
      pendingChunks = [];
      pendingBytes = 0;
      if (!consumeLine(tail)) outputLimited = true;
    };
    child.stdout.on("data", lineFilter ? captureFiltered : capture(stdout));
    child.stderr.on("data", capture(stderr));
    const identityPromise = Number.isSafeInteger(child.pid)
      ? Promise.resolve(options.processAdapter.observeIdentity(child.pid)).catch(() => ({ complete: false }))
      : Promise.resolve({ complete: false });
    const ownershipPromise = identityPromise.then(async (identity) => {
      const verifiedIdentity = identity?.complete === true && identity.exists === true
        && typeof identity.processIdentity?.creationId === "string" && identity.processIdentity.creationId
        && typeof identity.processIdentity?.executable === "string" && identity.processIdentity.executable;
      const expected = { pid: child.pid, processGroupId: process.platform === "win32" ? undefined : child.pid, processIdentity: verifiedIdentity ? identity.processIdentity : null, runId: options.runId };
      if (Number.isSafeInteger(expected.pid)) {
        try {
          await options.onProcessStarted?.(expected);
        } catch (persistenceError) {
          let terminationObservation;
          try {
            terminationObservation = await terminateOwnedTree(expected, options.hostEnvironment, { ownedHandle: child, processAdapter: options.processAdapter });
          } catch (terminationError) {
            terminationObservation = {
              complete: false,
              rootPid: expected.pid,
              processGroupId: expected.processGroupId,
              descendantPids: [],
              alivePids: [expected.pid],
              identityVerified: false,
              handleOwned: true,
              failureCode: `PROCESS_TERMINATION_${safeFailureToken(terminationError?.code ?? terminationError?.name ?? "FAILED")}`,
            };
          }
          const proof = assessTerminationProof(expected, terminationObservation);
          let recoveryCleanupError = null;
          if (proof.kind === "terminated") {
            try {
              await options.onProcessRecoverySettled?.(expected);
            } catch (error) {
              recoveryCleanupError = error;
            }
          }
          const error = new AgentCouncilRunnerError(
            recoveryCleanupError
              ? "PROCESS_OWNERSHIP_PERSISTENCE_AND_RECOVERY_CLEANUP_FAILED"
              : proof.kind === "terminated"
                ? "PROCESS_OWNERSHIP_PERSISTENCE_FAILED"
                : "PROCESS_OWNERSHIP_PERSISTENCE_AND_TERMINATION_UNVERIFIED",
            {
              persistenceCode: safeFailureToken(persistenceError?.code ?? persistenceError?.name ?? "FAILED"),
              terminationCode: proof.kind === "terminated" ? "TERMINATED" : safeFailureToken(terminationObservation?.failureCode ?? "UNVERIFIED"),
              recoveryCode: recoveryCleanupError ? safeFailureToken(recoveryCleanupError?.code ?? recoveryCleanupError?.name ?? "FAILED") : "CLEAN",
            },
          );
          error.agentCouncilExpectedProcess = expected;
          error.agentCouncilTerminationObservation = terminationObservation;
          if (proof.kind !== "terminated" || recoveryCleanupError) error.agentCouncilProcessOwnership = expected;
          throw error;
        }
      }
      if (!verifiedIdentity) {
        identityUnverified = true;
        identityTerminationObservation = await terminateOwnedTree(expected, options.hostEnvironment, { ownedHandle: child, processAdapter: options.processAdapter });
        void finish({ code: null, timedOut: false, spawnError: null });
      }
      return expected;
    });
    void ownershipPromise.catch(() => {});
    finish = async (result) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      flushPendingLine();
      try {
        const expected = await ownershipPromise;
        let terminationObservation = identityTerminationObservation;
        if (!terminationObservation && (result.timedOut || outputLimited)) terminationObservation = await terminateOwnedTree(expected, options.hostEnvironment, { ownedHandle: child, processAdapter: options.processAdapter });
        const settledResult = {
          ...result,
          identityUnverified,
          outputLimited,
          stdout: Buffer.concat(stdout).toString("utf8"),
          stderr: Buffer.concat(stderr).toString("utf8"),
          processOwnership: expected,
          terminationObservation,
          // Present only when a filter ran, so an unfiltered caller's result
          // keeps exactly the shape it had. This is what makes the attempt's
          // raw evidence honest about having been filtered.
          ...(lineFilter ? { streamFilter: { rawBytes: rawInputBytes, retainedBytes, droppedLines, droppedBytes } } : {}),
        };
        const proof = terminationObservation ? assessTerminationProof(expected, terminationObservation) : null;
        const cleanSettlement = !identityUnverified && ((!result.spawnError && !result.timedOut && !outputLimited && result.code !== null) || proof?.kind === "terminated");
        if (cleanSettlement) await options.onProcessSettled?.(expected);
        resolve(settledResult);
      } catch (error) {
        reject(error);
      }
    };
    timer = setTimeout(() => finish({ code: null, timedOut: true, spawnError: null }), options.timeoutMs);
    child.on("error", (error) => finish({ code: null, timedOut: false, spawnError: error.name }));
    child.on("close", (code) => finish({ code, timedOut: false, spawnError: null }));
  });
}

function nativeSeatPrompt() {
  return `Read ${PROMPT_FILE} and the ${DISCLOSURE_FILE} inventory it names, perform the bounded repository investigation, and return only the required JSON record. Repository evidence is below ${WORKSPACE_DIR}/; cite the approved logical paths from ${DISCLOSURE_FILE}, not the ${WORKSPACE_DIR}/ prefix.`;
}

export function buildNativeSeatArgs(request) {
  const prompt = nativeSeatPrompt();
  if (request.adapterName === "claude-cli") {
    return [
      "-p", prompt,
      "--model", request.model,
      "--effort", request.variant === "max" ? "max" : "high",
      "--safe-mode",
      "--disable-slash-commands",
      "--strict-mcp-config",
      "--tools", "Read,Grep,Glob,Edit",
      "--permission-mode", "acceptEdits",
      "--no-session-persistence",
      "--output-format", "json",
      "--json-schema", JSON.stringify(request.responseSchema),
    ];
  }
  if (request.adapterName === "grok-cli") {
    return [
      "--single", prompt,
      "--model", request.model,
      "--reasoning-effort", request.variant === "max" ? "max" : "high",
      "--permission-mode", "acceptEdits",
      "--no-memory",
      "--no-subagents",
      "--disable-web-search",
      "--tools", "read,grep,glob,edit",
      "--output-format", "json",
      "--json-schema", JSON.stringify(request.responseSchema),
      "--system-prompt-override", "You are an isolated Agent Council repository investigator. Follow only AGENT_COUNCIL_PROMPT.md. Do not use shell, web, MCP, plugins, skills, hooks, nested agents, external directories, or package installation.",
      "--leader-socket", path.join(request.runtimeRoot, `grok-${request.seatId}.sock`),
      "--cwd", request.cwd,
    ];
  }
  runnerFail("UNKNOWN_SEAT_ADAPTER", { adapterName: request.adapterName });
}

// Every seat transport is spawned under the same bounds and the same process
// lifecycle callbacks; only the resolved invocation and the optional stdout
// line filter differ. `overrides` is empty for every native door.
function spawnSeatProcess(io, invocation, request, overrides = {}) {
  return spawnBounded(invocation, {
    ...overrides,
    cwd: request.cwd,
    env: request.environment,
    timeoutMs: request.timeoutMs,
    maxOutputBytes: request.maxOutputBytes,
    runId: request.runId,
    hostEnvironment: io.hostEnvironment,
    processAdapter: io.processAdapter,
    onProcessStarted: request.onProcessStarted,
    onProcessSettled: request.onProcessSettled,
    onProcessRecoverySettled: request.onProcessRecoverySettled,
  });
}

async function invokeNativeSeat(io, request) {
  const args = buildNativeSeatArgs(request);
  return spawnSeatProcess(io, nativeCliInvocation(request.adapterName, args, io.hostEnvironment), request);
}

// The native CLI answered, but not in the contracted shape. Same idiom as the
// sibling `CLAUDE_AUTH_SCHEMA_INVALID` preflight guard: a named transport
// failure, not a raw SyntaxError whose V8 message would embed a snippet of the
// child's stdout — and this function is reached from the Claude entitlement
// preflight outside any catch, where an unnamed throw would be printed as an
// internal defect with a stack.
function parseNativeJson(text, adapterName) {
  try {
    return JSON.parse(text);
  } catch {
    runnerFail("NATIVE_STRUCTURED_RESPONSE_SCHEMA_INVALID", { adapterName });
  }
}

export function parseNativeStructuredResponse(adapterName, output) {
  const envelope = parseNativeJson(String(output ?? "").trim(), adapterName);
  if (adapterName === "claude-cli") {
    if (envelope?.is_error === true) runnerFail("CLAUDE_STRUCTURED_RESPONSE_ERROR");
    if (envelope?.structured_output && typeof envelope.structured_output === "object") return envelope.structured_output;
    if (typeof envelope?.result === "string") return parseNativeJson(envelope.result, adapterName);
    runnerFail("CLAUDE_STRUCTURED_RESPONSE_MISSING");
  }
  if (adapterName === "grok-cli") {
    if (envelope?.structuredOutput && typeof envelope.structuredOutput === "object") return envelope.structuredOutput;
    if (typeof envelope?.text === "string") return parseNativeJson(envelope.text, adapterName);
    runnerFail("GROK_STRUCTURED_RESPONSE_MISSING");
  }
  runnerFail("UNKNOWN_SEAT_ADAPTER", { adapterName });
}

// pi built-in tool allowlist for a council seat. `bash` and `powershell` are
// pi built-ins and are deliberately absent; pi has no `glob` tool (`find` is
// the glob equivalent). `--tools` is a strict allowlist, so anything not
// named here — including extension and custom tools — stays off.
const PI_SEAT_TOOLS = "read,grep,find,ls,edit,write";

// Every discovery surface pi would otherwise load from the seat's cwd or the
// host profile. `--no-approve` refuses project-local trust for the run.
const PI_ISOLATION_ARGS = Object.freeze([
  "--no-session",
  "--no-context-files",
  "--no-extensions",
  "--no-skills",
  "--no-prompt-templates",
  "--no-approve",
]);

const PI_SEAT_SYSTEM_PROMPT = "You are an isolated Agent Council repository investigator. Follow only AGENT_COUNCIL_PROMPT.md. Do not use shell, web, MCP, plugins, skills, hooks, nested agents, external directories, or package installation.";

function piThinkingLevel(variant) {
  if (variant === "max") return "max";
  if (variant === "xhigh") return "xhigh";
  return "high";
}

/**
 * Exact pi argv for one seat attempt. No output-cap flag of any kind — no
 * max-tokens, no output budget: the seat gets the model catalog's full output
 * allowance (max leeway) and truncation is detected after the fact from the
 * JSON stream's final assistant `stopReason`. `--thinking` is not such a cap;
 * it sets the reasoning level, which is a depth knob, not an output ceiling.
 */
export function buildPiSeatArgs(request) {
  return [
    "-p",
    "--mode", "json",
    ...PI_ISOLATION_ARGS,
    "--tools", PI_SEAT_TOOLS,
    "--model", request.model,
    "--thinking", piThinkingLevel(request.variant),
    "--append-system-prompt", PI_SEAT_SYSTEM_PROMPT,
    `Read ${PROMPT_FILE}, perform the bounded investigation, and write only the required JSON record to ${RESPONSE_FILE}.`,
  ];
}

/**
 * Win32-aware pi launcher resolution, in the exact order it is attempted:
 *
 * 1. Off Windows, the first `pi` executable on the child environment's `PATH`;
 *    an absent one is `PI_LAUNCHER_NOT_FOUND` with reason `no_path_executable`.
 * 2. On Windows, the canonical global-install bundle under `%APPDATA%\npm`
 *    (`node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js`), run
 *    through this process's own node. `PATH` is never consulted on Windows.
 * 3. If that file is absent, the `%APPDATA%\npm\pi.cmd` shim's own `cli.js`
 *    target, read out of the shim text and run the same way.
 *
 * The shim is unwrapped rather than spawned because node refuses to spawn a
 * `.cmd` with `shell: false` (EINVAL, CVE-2024-27980 mitigation) and this
 * runner never uses `shell: true`.
 */
export function piInvocation(args, environment) {
  if (process.platform !== "win32") {
    const executable = executableFromPath("pi", environment);
    if (!executable) runnerFail("PI_LAUNCHER_NOT_FOUND", { reason: "no_path_executable" });
    return { command: executable, args };
  }
  if (!environment.APPDATA) runnerFail("PI_LAUNCHER_NOT_FOUND", { reason: "no_appdata" });
  const npmRoot = path.resolve(environment.APPDATA, "npm");
  const isBundleFile = (candidate) => fs.existsSync(candidate) && fs.statSync(candidate).isFile();
  const bundled = path.resolve(npmRoot, "node_modules", "@earendil-works", "pi-coding-agent", "dist", "bundle", "cli.js");
  if (isBundleFile(bundled)) return { command: process.execPath, args: [bundled, ...args] };
  const shim = path.resolve(npmRoot, "pi.cmd");
  if (fs.existsSync(shim)) {
    let shimText = "";
    try {
      shimText = fs.readFileSync(shim, "utf8");
    } catch (error) {
      runnerFail("PI_LAUNCHER_NOT_FOUND", { reason: "shim_unreadable", cause: safeFailureToken(error?.code ?? error?.name) });
    }
    const match = shimText.match(/node_modules[\\/][^\r\n"]*?cli\.js/i);
    const resolved = match ? path.resolve(npmRoot, match[0]) : null;
    if (resolved && isBundleFile(resolved)) return { command: process.execPath, args: [resolved, ...args] };
    // The shim exists but names nothing runnable: a broken or partial install,
    // which is a different operator action from "pi was never installed". The
    // reason alone is the whole diagnosis; the resolved path is an environment
    // value (`%APPDATA%`, so a real user name) and never enters a detail.
    runnerFail("PI_LAUNCHER_NOT_FOUND", { reason: "shim_target_missing" });
  }
  runnerFail("PI_LAUNCHER_NOT_FOUND", { reason: "no_bundle_or_shim" });
}

/**
 * Child environment for a pi seat: the shared allowlist plus the OpenRouter
 * credential (absent key throws MISSING_ADAPTER_CREDENTIAL — intentionally
 * fail-loud, a seat without a key cannot produce a record) plus the host's
 * profile-location variables so pi finds its own `~/.pi/agent` model catalog.
 * No HOME redirect and no config overrides: pi isolation is argv-only.
 */
export function piChildEnvironment(hostEnvironment) {
  const environment = {
    ...filterEnvironment(hostEnvironment, {
      credentialKey: "OPENROUTER_API_KEY",
      credentialValue: hostEnvironment.OPENROUTER_API_KEY,
    }),
  };
  for (const key of ["USERPROFILE", "HOME", "APPDATA", "LOCALAPPDATA"]) {
    if (typeof hostEnvironment[key] === "string" && hostEnvironment[key]) environment[key] = hostEnvironment[key];
  }
  environment.NO_COLOR = "1";
  return environment;
}

/**
 * Pure reduction of a pi `--mode json` stdout stream. Unparseable lines are
 * skipped rather than fatal: pi may interleave non-JSON warnings, and a
 * parse failure on one line must not hide the authoritative `message_end`.
 * `stopReason` is the truncation signal (`"length"`). It is `null` both when no
 * final assistant message was observed at all and when the observed one carried
 * no string stop reason; `sawAssistantMessage` is what separates the two, so a
 * seat that spoke without a label is never reported as a seat that never spoke.
 */
export function parsePiJsonStream(stdout) {
  const summary = { stopReason: null, toolCalls: 0, toolNames: [], finalText: "", events: 0, sawAssistantMessage: false };
  const toolNames = new Set();
  let lastAssistantMessage = null;
  for (const line of String(stdout ?? "").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    let event;
    try {
      event = JSON.parse(trimmed);
    } catch {
      continue;
    }
    summary.events += 1;
    if (!event || typeof event !== "object") continue;
    if (event.type === "tool_execution_start") {
      summary.toolCalls += 1;
      if (typeof event.toolName === "string" && event.toolName) toolNames.add(event.toolName);
    }
    if (event.type === "message_end" && event.message?.role === "assistant") lastAssistantMessage = event.message;
  }
  summary.toolNames = [...toolNames].sort();
  summary.sawAssistantMessage = Boolean(lastAssistantMessage);
  if (lastAssistantMessage) {
    summary.stopReason = typeof lastAssistantMessage.stopReason === "string" ? lastAssistantMessage.stopReason : null;
    const content = Array.isArray(lastAssistantMessage.content) ? lastAssistantMessage.content : [];
    summary.finalText = content
      .filter((block) => block?.type === "text" && typeof block.text === "string")
      .map((block) => block.text)
      .join("");
  }
  return summary;
}

/**
 * The pi `--mode json` event types `parsePiJsonStream` above actually consumes,
 * and therefore the entire retained set of `retainPiStreamLine` below. It is
 * written here, beside that consumption, because the two must not drift: an
 * event type the parser starts reading while this set still drops it is a
 * silent regression, and `pi-stream-filter-retains-exactly-what-the-parser-reads`
 * fails if they part company.
 *
 * - `message_end` carries the authoritative final assistant turn and its
 *   `stopReason`, which is the whole truncation trigger.
 * - `tool_execution_start` is the tool call count and names.
 * - `session` is the stream's header; a stream that carries it and nothing else
 *   is precisely the `PI_NO_ASSISTANT_TURN` diagnosis, so it stays.
 *
 * Everything else pi streams — `message_update` deltas above all, then
 * `message_start`, `turn_end`, `tool_execution_end` — is never read. The deltas
 * are incremental text that arrives again, whole, in the following
 * `message_end`, so discarding them loses nothing the runner or the operator
 * can see.
 */
export const PI_STREAM_RETAINED_EVENT_TYPES = Object.freeze(["message_end", "session", "tool_execution_start"]);

/**
 * Whitelist predicate for one pi stdout line. A line is dropped only when it is
 * a JSON object carrying a string `type` that is not retained. Everything else
 * survives: blank lines, unparseable lines (pi interleaves non-JSON warning
 * banners, and `parsePiJsonStream` deliberately skips them rather than failing
 * — an operator still needs to see a transport error in `raw/`), non-object
 * JSON, and any object with no string `type`. Fail-open by construction: an
 * unrecognized shape is kept, never discarded.
 */
export function retainPiStreamLine(line) {
  const trimmed = String(line ?? "").trim();
  if (!trimmed) return true;
  let event;
  try {
    event = JSON.parse(trimmed);
  } catch {
    return true;
  }
  if (!event || typeof event !== "object" || typeof event.type !== "string") return true;
  return PI_STREAM_RETAINED_EVENT_TYPES.includes(event.type);
}

/**
 * Pure reduction of `pi --list-models openrouter`. The real catalog prints a
 * `provider model context max-out thinking images` header and then one row per
 * model with the provider in its own first column. Alias rows (`~name-latest`)
 * are skipped: they are not stable roster slugs. Ids are normalized to the
 * `openrouter/<slug>` form the roster and `--model` argv both use.
 */
export function parsePiModelCatalog(output) {
  const models = [];
  const seen = new Set();
  for (const line of String(output ?? "").split(/\r?\n/)) {
    const match = line.match(/^openrouter\s+(\S+)/);
    if (!match || match[1].startsWith("~")) continue;
    const id = `openrouter/${match[1]}`;
    if (seen.has(id)) continue;
    seen.add(id);
    models.push(id);
  }
  return models;
}

// How much the transport actually said, for a failure that would otherwise be
// indistinguishable from silence. A count, never the catalog text itself.
function countNonEmptyLines(output) {
  return String(output ?? "").split(/\r?\n/).filter((line) => line.trim()).length;
}

function preflightPi(io, environment) {
  const versionInvocation = piInvocation(["--version"], io.hostEnvironment);
  const version = spawnSyncChecked(versionInvocation.command, versionInvocation.args, {
    env: environment,
    errorCode: "PI_VERSION_PREFLIGHT_FAILED",
    timeoutMs: 30_000,
  }).trim();
  if (version !== adapterContract("pi-headless").version) runnerFail("PI_VERSION_MISMATCH", { version });
  const modelInvocation = piInvocation(["--list-models", "openrouter"], io.hostEnvironment);
  const output = spawnSyncChecked(modelInvocation.command, modelInvocation.args, {
    env: environment,
    errorCode: "PI_MODEL_PREFLIGHT_FAILED",
    maxBuffer: 64 * 1024 * 1024,
    timeoutMs: 60_000,
  });
  const models = parsePiModelCatalog(output);
  // An empty catalog is a transport fault, not an empty roster. Left unnamed it
  // surfaces much later as NO_DIVERSE_QUALIFIED_ROSTER and points the operator
  // at the roster instead of at pi's model list.
  if (!models.length) runnerFail("PI_MODEL_CATALOG_EMPTY", { rows: countNonEmptyLines(output) });
  return { adapterName: "pi-headless", version, models };
}

/**
 * The one door that filters. A pi seat streams `--mode json`, and roughly seven
 * eighths of those bytes are events the runner never reads, so they are dropped
 * per line before the seat's output budget is applied. The retained stream is
 * what the caller sees and what lands in `raw/`; the discarded bytes are still
 * bounded by `FILTERED_RAW_INPUT_MULTIPLE` so a runaway is killed and named.
 */
async function invokePiSeat(io, request) {
  return spawnSeatProcess(io, piInvocation(buildPiSeatArgs(request), io.hostEnvironment), request, { lineFilter: retainPiStreamLine });
}

/**
 * Real I/O implementation. Tests replace any or all methods; constructing it has no side effects.
 */
export function createDefaultIo(overrides = {}) {
  const io = {
    hostEnvironment: { ...process.env },
    tempRoot: fs.realpathSync.native(os.tmpdir()),
    nodeExecutable: process.execPath,
    nodeVersion: process.version,
    platform: process.platform,
    now: () => new Date().toISOString(),
    newRunId: () => `ac_${new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14)}_${randomUUID().slice(0, 8)}`,
    newNonce: (label) => `b64url:${label}:${randomBytes(24).toString("base64url")}`,
    readFile: (file) => fs.readFileSync(file),
    writeFile: (file, value) => fs.writeFileSync(file, value),
    removeFile: (file) => fs.rmSync(file, { force: true }),
    writeFileAtomic: (file, value) => writeFileAtomicWithRetry(file, value),
    writeFileAtomicExact: (file, value) => writeFileAtomicWithRetry(file, value, { createParent: false }),
    exists: (file) => fs.existsSync(file),
    stat: (file) => fs.lstatSync(file),
    lstat: (file) => fs.lstatSync(file, { bigint: true }),
    realpath: (file) => fs.realpathSync.native(file),
    readDirectory: (directory) => fs.readdirSync(directory),
    mkdir: (directory) => fs.mkdirSync(directory, { recursive: true }),
    mkdirExact: (directory) => fs.mkdirSync(directory, { recursive: false }),
    copyTree: (source, destination) => fs.cpSync(source, destination, { recursive: true, force: false, dereference: false }),
    removeTree: (directory) => fs.rmSync(directory, { recursive: true, force: false, maxRetries: 5, retryDelay: 100 }),
    removeEmptyDirectory: (directory) => fs.rmdirSync(directory),
    walkFiles: (directory) => {
      const output = [];
      const visit = (current, prefix = "") => {
        for (const entry of fs.readdirSync(current, { withFileTypes: true }).sort((left, right) => left.name.localeCompare(right.name))) {
          const relative = prefix ? `${prefix}/${entry.name}` : entry.name;
          const absolute = path.join(current, entry.name);
          if (entry.isDirectory()) visit(absolute, relative);
          else if (entry.isFile()) output.push(relative);
          else runnerFail("DURABLE_NON_FILE_ENTRY", { path: relative });
        }
      };
      visit(directory);
      return output;
    },
    rename: (source, destination) => fs.renameSync(source, destination),
    chmod: (file, mode) => fs.chmodSync(file, mode),
    listRepositoryFiles: (repo) => gitChecked(repo, ["ls-files", "-z", "--cached", "--others", "--exclude-standard"], { encoding: null }).toString("utf8").split("\0").filter(Boolean).sort(),
    resolveRepositoryRoot: (repo) => path.resolve(gitChecked(repo, ["rev-parse", "--show-toplevel"]).trim()),
    repositoryHead: (repo) => gitChecked(repo, ["rev-parse", "HEAD"]).trim(),
    repositoryDirty: (repo) => gitChecked(repo, ["status", "--porcelain"]).trim().length > 0,
    readHistory: (repo, approvedDiffPaths) => readBoundedHistory(repo, approvedDiffPaths),
    initializeSyntheticGit: (directory) => {
      gitChecked(directory, ["init", "-q"]);
      gitChecked(directory, ["add", "--all"]);
      gitChecked(directory, ["-c", "user.name=Agent Council", "-c", "user.email=agent-council@invalid", "commit", "-q", "-m", "frozen sanitized snapshot"]);
    },
    seatDiff: (directory) => collectSeatDiff(directory),
    validateAuditResponse: (args) => parseAuditResponse(args),
    checkExternalNetwork: () => checkExternalModelNetwork(),
    preflightPi: (environment) => preflightPi(io, environment),
    preflightTransports: (environment) => preflightAllTransports(io, environment),
    preflightSelectedNativeModels: (roster) => {
      const claude = roster.externalDecisionSeats.find((seat) => seat.qualification.adapter.name === "claude-cli");
      if (claude) verifyClaudeModelEntitlement(io, claude.model);
    },
    resolveNpm: () => resolveNpmInstallation(io.hostEnvironment),
    invokePiSeat: (request) => invokePiSeat(io, request),
    // The pi door is the one that writes its own response file; every other
    // qualified adapter is a native CLI. Read from the table so a new transport
    // declares its door once instead of being added here by name.
    invokeSeat: (request) => adapterContract(request.adapterName)?.writesResponseFile === true
      ? io.invokePiSeat(request)
      : invokeNativeSeat(io, request),
    terminateProcessTree: (expected) => terminateOwnedTree(expected, io.hostEnvironment, { processAdapter: io.processAdapter }),
    runProbe: async (spec, request) => spawnBounded({ command: spec.executable, args: spec.argv }, {
      cwd: request.cwd,
      env: request.environment,
      timeoutMs: AGENT_COUNCIL_LIMITS.probeTimeoutMs,
      maxOutputBytes: AGENT_COUNCIL_LIMITS.probeOutputBytes,
      runId: request.runId,
      hostEnvironment: io.hostEnvironment,
      processAdapter: io.processAdapter,
      onProcessStarted: request.onProcessStarted,
      onProcessSettled: request.onProcessSettled,
      onProcessRecoverySettled: request.onProcessRecoverySettled,
    }),
  };
  Object.assign(io, overrides);
  io.processAdapter ??= defaultProcessAdapter(io.platform, io.hostEnvironment);
  return io;
}

function readBoundedHistory(repo, approvedDiffPaths) {
  const format = "%H%x1f%P%x1f%aI%x1f%s%x1e";
  const raw = gitChecked(repo, ["log", `-${AGENT_COUNCIL_LIMITS.historyCommits}`, `--format=${format}`]);
  const commits = raw.split("\x1e").map((record) => record.trim()).filter(Boolean).map((record) => {
    const [sha, parents, authorTimestamp, subject] = record.split("\x1f");
    return { sha, parents: parents ? parents.split(" ").filter(Boolean) : [], authorTimestamp, subject: subject ?? "" };
  });
  const pathRaw = gitChecked(repo, ["log", `-${AGENT_COUNCIL_LIMITS.historyCommits}`, "--name-only", "--format="]);
  const paths = [...new Set(pathRaw.split(/\r?\n/).map((value) => value.trim()).filter(Boolean).map(normalizeRelativePosixPath))].sort().slice(0, AGENT_COUNCIL_LIMITS.historyPathEntries);
  const approvedDiffs = [];
  for (const logicalPath of approvedDiffPaths) {
    const bytes = Buffer.from(gitChecked(repo, ["show", "--format=", "--no-ext-diff", "HEAD", "--", logicalPath]), "utf8");
    if (bytes.length > AGENT_COUNCIL_LIMITS.historicalDiffPathBytes) runnerFail("HISTORICAL_DIFF_PATH_TOO_LARGE", { path: logicalPath });
    const detector = scanSecretBytes(bytes);
    if (detector) runnerFail("SECRET_IN_HISTORICAL_DIFF", { path: logicalPath, detector });
    approvedDiffs.push({ logicalPath, bytes: bytes.length, sha256: sha256Bytes(bytes), body: bytes });
  }
  if (approvedDiffs.reduce((sum, entry) => sum + entry.bytes, 0) > AGENT_COUNCIL_LIMITS.historicalDiffTotalBytes) runnerFail("HISTORICAL_DIFF_TOTAL_TOO_LARGE");
  return { commits, paths, approvedDiffs };
}

function validateHistoryEvidence(historyIo) {
  for (const commit of historyIo.commits ?? []) {
    const detector = scanSecretBytes(Buffer.from(String(commit.subject ?? ""), "utf8"));
    if (detector) runnerFail("SECRET_IN_HISTORY_METADATA", { field: "commit-subject", detector });
  }
  for (const logicalPath of historyIo.paths ?? []) {
    const detector = scanSecretBytes(Buffer.from(String(logicalPath), "utf8"));
    if (detector) runnerFail("SECRET_IN_HISTORY_METADATA", { field: "path", detector });
  }
  for (const approvedDiff of historyIo.approvedDiffs ?? []) {
    const pathDetector = scanSecretBytes(Buffer.from(String(approvedDiff.logicalPath), "utf8"));
    if (pathDetector) runnerFail("SECRET_IN_HISTORY_METADATA", { field: "approved-diff-path", detector: pathDetector });
    const body = Buffer.isBuffer(approvedDiff.body) ? approvedDiff.body : Buffer.from(approvedDiff.body ?? "");
    const detector = scanSecretBytes(body);
    if (detector) runnerFail("SECRET_IN_HISTORICAL_DIFF", { path: approvedDiff.logicalPath, detector });
    if (body.length !== approvedDiff.bytes || sha256Bytes(body) !== approvedDiff.sha256) runnerFail("HISTORICAL_DIFF_METADATA_MISMATCH", { path: approvedDiff.logicalPath });
  }
}

function collectSeatDiff(directory) {
  const names = gitChecked(directory, ["diff", "--name-only", "-z", "HEAD"], { encoding: null }).toString("utf8").split("\0").filter(Boolean).sort();
  return names.slice(0, AGENT_COUNCIL_LIMITS.historyPathEntries).map((logicalPath) => {
    const resolved = path.resolve(directory, logicalPath);
    if (!pathInside(directory, resolved) || !fs.existsSync(resolved) || !fs.statSync(resolved).isFile()) return { logicalPath: normalizeRelativePosixPath(logicalPath), deleted: true };
    const bytes = fs.readFileSync(resolved);
    return { logicalPath: normalizeRelativePosixPath(logicalPath), bytes: bytes.length, sha256: sha256Bytes(bytes) };
  });
}

function excludedSourceReason(logicalPath, userExclusions) {
  const basename = path.posix.basename(logicalPath).toLowerCase();
  const lower = logicalPath.toLowerCase();
  if (logicalPath.split("/").includes(".git")) return "git-metadata";
  if (lower === EVIDENCE_ROOT || lower.startsWith(`${EVIDENCE_ROOT}/`)) return "reserved-evidence-tree";
  if (basename === ".env" || (basename.startsWith(".env.") && basename !== ".env.example")) return "environment-file";
  if (LOCAL_SECRET_BASENAMES.has(basename)) return "local-secret-config";
  if (/\.(?:pem|key)$/i.test(basename)) return "key-material-extension";
  if (userExclusions.has(logicalPath)) return "user-exclusion";
  return null;
}

function copySanitizedCorpus(io, repo, corpusDirectory, options) {
  const names = io.listRepositoryFiles(repo);
  if (!names.length) runnerFail("EMPTY_REPOSITORY_CORPUS");
  const included = [];
  const excluded = [];
  const caseFolded = new Set();
  let totalBytes = 0;
  io.mkdir(corpusDirectory);
  for (const sourceName of names) {
    const logicalPath = normalizeRelativePosixPath(sourceName);
    const caseKey = logicalPath.toLowerCase();
    if (caseFolded.has(caseKey)) runnerFail("SOURCE_CASE_COLLISION", { path: logicalPath });
    caseFolded.add(caseKey);
    const exclusion = excludedSourceReason(logicalPath, options.userExclusions);
    if (exclusion) {
      excluded.push({ logicalPath, reason: exclusion });
      continue;
    }
    const source = path.resolve(repo, logicalPath);
    if (!pathInside(repo, source)) runnerFail("SOURCE_PATH_ESCAPE", { path: logicalPath });
    const stat = io.stat(source);
    if (stat.isSymbolicLink()) runnerFail("SOURCE_SYMLINK_REJECTED", { path: logicalPath });
    if (!stat.isFile()) runnerFail("SOURCE_NON_FILE_REJECTED", { path: logicalPath });
    const extension = path.posix.extname(logicalPath).toLowerCase();
    if (DANGEROUS_EXTENSIONS.has(extension)) runnerFail("DANGEROUS_SOURCE_FORMAT", { path: logicalPath });
    const bytes = io.readFile(source);
    const binary = bytes.includes(0) || BENIGN_BINARY_EXTENSIONS.has(extension);
    const binaryApproved = options.approvedBinaries.has(logicalPath);
    if (binary && !binaryApproved) runnerFail("UNAPPROVED_BINARY_SOURCE", { path: logicalPath });
    if (binaryApproved && !BENIGN_BINARY_EXTENSIONS.has(extension)) runnerFail("UNAPPROVABLE_BINARY_SOURCE", { path: logicalPath });
    const maxBytes = binaryApproved ? AGENT_COUNCIL_LIMITS.approvedBinaryBytes : AGENT_COUNCIL_LIMITS.normalFileBytes;
    if (bytes.length > maxBytes) runnerFail("SOURCE_FILE_TOO_LARGE", { path: logicalPath, maxBytes });
    const detector = scanSecretBytes(bytes);
    if (detector) runnerFail("SECRET_IN_SOURCE", { path: logicalPath, detector });
    totalBytes += bytes.length;
    if (totalBytes > AGENT_COUNCIL_LIMITS.corpusBytes) runnerFail("SOURCE_CORPUS_TOO_LARGE");
    const destination = path.resolve(corpusDirectory, logicalPath);
    if (!pathInside(corpusDirectory, destination)) runnerFail("CORPUS_PATH_ESCAPE", { path: logicalPath });
    io.mkdir(path.dirname(destination));
    io.writeFile(destination, bytes);
    included.push({ logicalPath, physicalPath: logicalPath, disposition: "copied", bytes: bytes.length, sha256: sha256Bytes(bytes), binaryApproved });
  }
  return { included, excluded };
}

function addGeneratedCorpusEvidence(io, corpus, corpusDirectory, logicalPath, bytes) {
  const normalized = normalizeRelativePosixPath(logicalPath);
  if (corpus.included.some((entry) => entry.logicalPath.toLowerCase() === normalized.toLowerCase())) runnerFail("GENERATED_EVIDENCE_PATH_COLLISION", { path: normalized });
  if (bytes.length > AGENT_COUNCIL_LIMITS.normalFileBytes) runnerFail("GENERATED_EVIDENCE_TOO_LARGE", { path: normalized });
  const detector = scanSecretBytes(bytes);
  if (detector) runnerFail("SECRET_IN_GENERATED_EVIDENCE", { path: normalized, detector });
  const totalBytes = corpus.included.reduce((sum, entry) => sum + entry.bytes, 0) + bytes.length;
  if (totalBytes > AGENT_COUNCIL_LIMITS.corpusBytes) runnerFail("SOURCE_CORPUS_TOO_LARGE");
  const destination = path.resolve(corpusDirectory, normalized);
  if (!pathInside(corpusDirectory, destination)) runnerFail("CORPUS_PATH_ESCAPE", { path: normalized });
  io.mkdir(path.dirname(destination));
  io.writeFile(destination, bytes);
  corpus.included.push({ logicalPath: normalized, physicalPath: normalized, disposition: "copied", bytes: bytes.length, sha256: sha256Bytes(bytes), binaryApproved: false });
}

function materializeHistoryPacket(io, corpus, corpusDirectory, history, historyIo) {
  addGeneratedCorpusEvidence(io, corpus, corpusDirectory, ".agent-council-evidence/history/manifest.json", Buffer.from(`${canonicalJson(history)}\n`, "utf8"));
  for (const approvedDiff of historyIo.approvedDiffs) {
    const encodedPath = Buffer.from(approvedDiff.logicalPath, "utf8").toString("base64url");
    addGeneratedCorpusEvidence(io, corpus, corpusDirectory, `.agent-council-evidence/history/approved-diffs/${encodedPath}.diff`, Buffer.from(approvedDiff.body));
  }
  corpus.included.sort((left, right) => left.logicalPath.localeCompare(right.logicalPath));
}

function provisionGrokRuntimeHome(io, state) {
  const sourceHome = io.hostEnvironment.GROK_HOME
    ? path.resolve(io.hostEnvironment.GROK_HOME)
    : path.resolve(io.hostEnvironment.USERPROFILE ?? io.hostEnvironment.HOME ?? "", ".grok");
  const sourceAuth = path.join(sourceHome, "auth.json");
  if (!io.exists(sourceAuth) || !io.stat(sourceAuth).isFile()) runnerFail("GROK_SUBSCRIPTION_AUTH_REQUIRED");
  const authBytes = io.readFile(sourceAuth);
  if (!authBytes.length || authBytes.length > 256 * 1024) runnerFail("GROK_AUTH_FILE_INVALID");
  const runtimeHome = path.join(runRoot(state), NATIVE_RUNTIME_DIR, "grok-home");
  io.mkdir(runtimeHome);
  const runtimeAuth = path.join(runtimeHome, "auth.json");
  if (!io.exists(runtimeAuth)) {
    io.writeFile(runtimeAuth, authBytes);
    try { io.chmod(runtimeAuth, 0o600); } catch { /* Windows ACLs remain the authority. */ }
  }
  const config = [
    "disable_plugins = true",
    "",
    "[cli]",
    'installer = "internal"',
    "",
    "[workflows]",
    "enabled = false",
    "",
    "[compat.cursor]",
    "skills = false",
    "rules = false",
    "agents = false",
    "mcps = false",
    "hooks = false",
    "sessions = false",
    "",
    "[compat.claude]",
    "skills = false",
    "rules = false",
    "agents = false",
    "mcps = false",
    "hooks = false",
    "sessions = false",
    "",
    "[compat.codex]",
    "sessions = false",
    "",
  ].join("\n");
  io.writeFile(path.join(runtimeHome, "config.toml"), config);
  return runtimeHome;
}

function seatEnvironmentFor(io, state, profile) {
  const adapterName = profile.qualification.adapter.name;
  if (adapterName === "pi-headless") return piChildEnvironment(io.hostEnvironment);
  const environment = nativeAuthEnvironment(io.hostEnvironment);
  if (adapterName !== "grok-cli") return environment;
  const runtimeHome = provisionGrokRuntimeHome(io, state);
  return {
    ...environment,
    GROK_HOME: runtimeHome,
    HOME: runtimeHome,
    USERPROFILE: runtimeHome,
    GROK_WORKFLOWS: "0",
    GROK_CURSOR_SKILLS_ENABLED: "false",
    GROK_CURSOR_RULES_ENABLED: "false",
    GROK_CURSOR_AGENTS_ENABLED: "false",
    GROK_CURSOR_MCPS_ENABLED: "false",
    GROK_CURSOR_HOOKS_ENABLED: "false",
    GROK_CURSOR_SESSIONS_ENABLED: "false",
    GROK_CLAUDE_SKILLS_ENABLED: "false",
    GROK_CLAUDE_RULES_ENABLED: "false",
    GROK_CLAUDE_AGENTS_ENABLED: "false",
    GROK_CLAUDE_MCPS_ENABLED: "false",
    GROK_CLAUDE_HOOKS_ENABLED: "false",
    GROK_CLAUDE_SESSIONS_ENABLED: "false",
  };
}

function probeEnvironmentFor(io) {
  return filterEnvironment(io.hostEnvironment);
}

function resolveProbeSpecs(io, declarations, corpusSha256) {
  let npm = null;
  const nodeDigest = sha256Bytes(io.readFile(io.nodeExecutable));
  return declarations.map((declaration) => {
    const gate = BROKER_GATE_CATALOG[declaration.gateId];
    if (!gate) runnerFail("UNKNOWN_PROBE_GATE", { gateId: declaration.gateId });
    const base = {
      schemaVersion: 1,
      id: declaration.id,
      gateId: declaration.gateId,
      platform: io.platform,
      executable: io.nodeExecutable,
      shell: false,
      nodeExecutable: io.nodeExecutable,
      nodeVersion: io.nodeVersion,
      executableSha256: nodeDigest,
      corpusSha256,
    };
    if (gate.kind === "npm") {
      npm ??= io.resolveNpm();
      const launcherSha256 = sha256Bytes(io.readFile(npm.launcherPath));
      const npmCliSha256 = sha256Bytes(io.readFile(npm.npmCliPath));
      return validateResolvedProbeSpec({
        ...base,
        argv: [npm.npmCliPath, ...gate.argv],
        launcherPath: npm.launcherPath,
        launcherSha256,
        npmCliPath: npm.npmCliPath,
        npmCliSha256,
        npmVersion: npm.npmVersion,
      });
    }
    return validateResolvedProbeSpec({
      ...base,
      argv: [...gate.argv],
      launcherPath: io.nodeExecutable,
      launcherSha256: nodeDigest,
    });
  });
}

export { resolveProbeSpecs };

function resolveLiveProbeSpecs(io, state) {
  const corpusSha256 = canonicalSha256(state.disclosureManifest.included);
  const expected = resolveProbeSpecs(io, state.disclosureManifest.probeDeclarations, corpusSha256);
  if (canonicalJson(expected) !== canonicalJson(state.probeSpecs)) runnerFail("LIVE_PROBE_SPEC_DRIFT");
  return expected;
}

/**
 * The three dispositions of a run file on disk.
 *
 * - `v1`: a run from the previous schema. Never resumed, but inspectable and
 *   abortable, because abort is exactly the command whose job is to wind down a
 *   run this build cannot drive.
 * - `stale`: a payload that claims the *current* schema version and carries the
 *   Agent Council marker, but no longer parses under this build's validator —
 *   a run prepared by an earlier build of the same schema, whose state carries
 *   fields this parser has since retired. Without this disposition it failed
 *   `inspect` and `abort` with a bare structural `UNKNOWN_FIELD`, stranding the
 *   disposable tree. `parsed` is null and `staleError` names the field.
 * - neither: a healthy current run. `parsed` holds it, so the happy path
 *   validates once rather than once per caller.
 *
 * The schema version is deliberately not bumped for this: version 2 is pinned
 * by the roster pool, the disclosure manifest, and every seat, chair, audit,
 * and revision record, and a bump would invalidate all of them.
 */
function readRawRun(io, runFile) {
  const resolved = path.resolve(runFile);
  const value = parseJsonBytes(io.readFile(resolved), "run");
  const none = { resolved, value, v1: false, stale: false, parsed: null, staleError: null };
  if (value?.version === 1 || value?.schemaVersion === 1) return { ...none, v1: true };
  if (value?.schemaVersion !== AGENT_COUNCIL_SCHEMA_VERSION || value?.marker !== "agent-council") return none;
  try {
    return { ...none, parsed: parseRunStateV2(value) };
  } catch (error) {
    // Only a structural rejection makes this a stale run of a known shape. An
    // internal defect inside the validator must propagate rather than be
    // laundered into "restart required".
    if (!(error instanceof AgentCouncilValidationError)) throw error;
    return { ...none, stale: true, staleError: error };
  }
}

/**
 * The operator-facing detail for a stale run: which validator rejected it,
 * where, and the offending field names it carried. Already sanitized —
 * `AgentCouncilValidationError` bounds its own details and path.
 */
function staleRunDetails(raw) {
  const error = raw.staleError;
  // The validator's own code and path are spread last so a future structural
  // detail key can never shadow which validator refused, or where.
  return {
    ...(error?.details && typeof error.details === "object" ? error.details : {}),
    validationCode: safeFailureToken(error?.code, "UNKNOWN_VALIDATION_FAILURE"),
    ...(typeof error?.path === "string" ? { path: error.path } : {}),
  };
}

function readRun(io, runFile) {
  const raw = readRawRun(io, runFile);
  if (raw.v1) runnerFail("V1_RUN_RESTART_REQUIRED");
  // A stale payload re-raises its own structural validation code here, so every
  // driving command keeps reporting exactly the field that is wrong. `inspect`
  // and `abort` consult `raw.stale` instead and refuse or wind down by name.
  const state = raw.parsed ?? parseRunStateV2(raw.value);
  if (path.resolve(state.runFile) !== raw.resolved) runnerFail("RUN_FILE_IDENTITY_MISMATCH");
  const root = path.dirname(raw.resolved);
  for (const seat of state.resolvedRoster.externalDecisionSeats) {
    const expected = path.resolve(root, SEATS_DIR, seat.id);
    if (path.resolve(state.seatDirectories[seat.id]) !== expected) runnerFail("SEAT_DIRECTORY_IDENTITY_MISMATCH", { seatId: seat.id });
  }
  return mergeProcessRecoveryRecords(io, mutableData(state));
}

function writeRun(io, state) {
  const parsed = parseRunStateV2(state);
  stableWriteJson(io, parsed.runFile, parsed);
  return mutableData(parsed);
}

function runRoot(state) {
  return path.dirname(state.runFile);
}

function verifyCorpusDirectory(io, state, corpusDirectory) {
  const expected = [...state.disclosureManifest.included]
    .sort((left, right) => left.physicalPath.localeCompare(right.physicalPath));
  const actual = io.walkFiles(corpusDirectory).map(normalizeRelativePosixPath).sort();
  const expectedPaths = expected.map((entry) => entry.physicalPath).sort();
  if (canonicalJson(actual) !== canonicalJson(expectedPaths)) runnerFail("CORPUS_INVENTORY_DRIFT");
  for (const entry of expected) {
    const file = path.resolve(corpusDirectory, entry.physicalPath);
    if (!pathInside(corpusDirectory, file) || !io.exists(file)) runnerFail("CORPUS_DRIFT", { path: entry.logicalPath });
    const stat = io.stat(file);
    if (stat.isSymbolicLink() || !stat.isFile()) runnerFail("CORPUS_ENTRY_TYPE_DRIFT", { path: entry.logicalPath });
    const bytes = io.readFile(file);
    if (bytes.length !== entry.bytes || sha256Bytes(bytes) !== entry.sha256) runnerFail("CORPUS_DRIFT", { path: entry.logicalPath });
  }
  return expected.map((entry) => ({ physicalPath: entry.physicalPath, bytes: entry.bytes, sha256: entry.sha256 }));
}

function verifyCurrentCorpus(io, state) {
  const corpusDirectory = path.join(runRoot(state), CORPUS_DIR);
  verifyCorpusDirectory(io, state, corpusDirectory);
  const revalidated = validateDisclosureManifest(state.disclosureManifest);
  if (revalidated.manifestSha256 !== state.disclosureManifest.manifestSha256) runnerFail("MANIFEST_DRIFT");
  const boundCorpusSha256 = canonicalSha256({ files: state.disclosureManifest.included, probeSpecs: state.probeSpecs });
  if (boundCorpusSha256 !== state.disclosureManifest.corpusSha256) runnerFail("CORPUS_BINDING_MISMATCH");
  return corpusDirectory;
}

function copyVerifiedCorpus(io, state, destination) {
  const source = verifyCurrentCorpus(io, state);
  if (io.exists(destination)) io.removeTree(destination);
  io.mkdir(path.dirname(destination));
  io.copyTree(source, destination);
  verifyCorpusDirectory(io, state, destination);
  return destination;
}

function copyCorpusForSeat(io, state, seatId, destinationRoot = SEATS_DIR) {
  const root = runRoot(state);
  const destination = path.join(root, destinationRoot, seatId);
  if (io.exists(destination)) io.removeTree(destination);
  io.mkdir(destination);
  copyVerifiedCorpus(io, state, path.join(destination, WORKSPACE_DIR));
  io.initializeSyntheticGit(destination);
  return destination;
}

function responseExpected(state, seatId, round) {
  return { runId: state.runId, round, seatId, nonce: state.nonces.rounds[String(round)][seatId] };
}

/**
 * Materialize one attempt's outbound bytes in a seat root: the prompt, plus the
 * bounded context files the prompt points at.
 *
 * A context file the runner hands a model is outbound disclosure exactly as
 * prompt bytes are, so it goes through the same secret scan. Every scan runs
 * before any write, so a refused attempt never leaves a half-materialized set
 * behind.
 *
 * Removal is total and unconditional: the stale response file, and every name in
 * `SEAT_CONTEXT_FILES` whether or not this attempt writes it. A seat directory
 * is reused across rounds and across the automatic truncation retry, so a
 * Round-1 attempt must not be able to read the round context an earlier round
 * left, and a retry must never read the previous attempt's copy.
 */
function writePrompt(io, directory, prompt, context = {}) {
  const detector = scanSecretBytes(Buffer.from(prompt, "utf8"));
  if (detector) runnerFail("SECRET_IN_OUTBOUND_PROMPT", { detector });
  const contextFiles = Object.entries(context).map(([name, value]) => {
    const body = `${JSON.stringify(value, null, 2)}\n`;
    const found = scanSecretBytes(Buffer.from(body, "utf8"));
    // A corpus path, an exclusion reason, or a persisted record can carry a
    // detector-shaped string even when every disclosed file body passed the
    // source scan, because the source scan reads bytes and not names.
    if (found) runnerFail("SECRET_IN_OUTBOUND_CONTEXT", { file: name, detector: found });
    return [name, body];
  });
  const responseFile = path.join(directory, RESPONSE_FILE);
  if (io.exists(responseFile)) io.removeFile(responseFile);
  for (const name of SEAT_CONTEXT_FILES) {
    const staleFile = path.join(directory, name);
    if (io.exists(staleFile)) io.removeFile(staleFile);
  }
  io.writeFile(path.join(directory, PROMPT_FILE), `${prompt.trim()}\n`);
  for (const [name, body] of contextFiles) io.writeFile(path.join(directory, name), body);
  return responseFile;
}

function responseSchemaInstruction(expected, role) {
  const movement = role === "chair"
    ? expected.round === 1
      ? '"movement": null,'
      : '"movement": {"kind":"changed","fromChoiceId":"...","toChoiceId":"...","reasonClaimIds":["claim-id"]} OR {"kind":"unchanged","choiceId":"...","rationale":"...","reasonClaimIds":["claim-id"]},'
    : "";
  const allowedTopLevel = role === "chair"
    ? "schemaVersion,runId,round,seatId,role,nonce,recommendation,claims,risks,alternatives,selfCounterargument,unresolvedQuestions,movement"
    : "schemaVersion,runId,round,seatId,role,nonce,recommendation,claims,risks,alternatives,selfCounterargument,unresolvedQuestions";
  const externalMovement = role === "external-decision" ? " Do not include movement." : "";
  return `Write JSON only to ${RESPONSE_FILE}. Required identity: schemaVersion=2, runId=${expected.runId}, round=${expected.round}, seatId=${expected.seatId}, role=${role}, nonce=${expected.nonce}. Required fields: ${movement} recommendation {choiceId,summary,confidence}; one or more substantive claims [{id,kind,statement,confidence,citations:[{path,lineStart,lineEnd,fileSha256}],probeReceiptIds:[]}], each backed by an approved citation or runner-issued receipt; one or more risks [{id,statement,impact,likelihood,claimIds,mitigation}], each linked to a claim, where impact and likelihood are JSON integers from 1 through 5 with no decimals; one or more alternatives [{id,summary,rejectionReason}]; selfCounterargument {statement,answer}; unresolvedQuestions [strings]. Every recommendation confidence and claim confidence must be a JSON number from 0 through 1 inclusive, never a percentage or a 0-to-100 score. The exact allowed top-level keys are: ${allowedTopLevel}. No other top-level key is permitted.${externalMovement} Citation lineStart and lineEnd are positive JSON integers. Do not return prose as the record.`;
}

function externalResponseJsonSchema(expected) {
  const string = { type: "string", minLength: 1 };
  const stringArray = { type: "array", items: string };
  return {
    type: "object",
    additionalProperties: false,
    required: ["schemaVersion", "runId", "round", "seatId", "role", "nonce", "recommendation", "claims", "risks", "alternatives", "selfCounterargument", "unresolvedQuestions"],
    properties: {
      schemaVersion: { type: "integer", const: 2 },
      runId: { type: "string", const: expected.runId },
      round: { type: "integer", const: expected.round },
      seatId: { type: "string", const: expected.seatId },
      role: { type: "string", const: "external-decision" },
      nonce: { type: "string", const: expected.nonce },
      recommendation: {
        type: "object",
        additionalProperties: false,
        required: ["choiceId", "summary", "confidence"],
        properties: {
          choiceId: string,
          summary: string,
          confidence: { type: "number", minimum: 0, maximum: 1 },
        },
      },
      claims: {
        type: "array",
        minItems: 1,
        items: {
          type: "object",
          additionalProperties: false,
          required: ["id", "kind", "statement", "confidence", "citations", "probeReceiptIds"],
          properties: {
            id: string,
            kind: string,
            statement: string,
            confidence: { type: "number", minimum: 0, maximum: 1 },
            citations: {
              type: "array",
              items: {
                type: "object",
                additionalProperties: false,
                required: ["path", "lineStart", "lineEnd", "fileSha256"],
                properties: {
                  path: string,
                  lineStart: { type: "integer", minimum: 1 },
                  lineEnd: { type: "integer", minimum: 1 },
                  fileSha256: string,
                },
              },
            },
            probeReceiptIds: stringArray,
          },
        },
      },
      risks: {
        type: "array",
        minItems: 1,
        items: {
          type: "object",
          additionalProperties: false,
          required: ["id", "statement", "impact", "likelihood", "claimIds", "mitigation"],
          properties: {
            id: string,
            statement: string,
            impact: { type: "integer", minimum: 1, maximum: 5 },
            likelihood: { type: "integer", minimum: 1, maximum: 5 },
            claimIds: { ...stringArray, minItems: 1 },
            mitigation: string,
          },
        },
      },
      alternatives: {
        type: "array",
        minItems: 1,
        items: {
          type: "object",
          additionalProperties: false,
          required: ["id", "summary", "rejectionReason"],
          properties: { id: string, summary: string, rejectionReason: string },
        },
      },
      selfCounterargument: {
        type: "object",
        additionalProperties: false,
        required: ["statement", "answer"],
        properties: { statement: string, answer: string },
      },
      unresolvedQuestions: stringArray,
    },
  };
}

export function schemaCorrectionPrompt(basePrompt, failureCode) {
  return `# Schema-correction retry\n\nYour previous record was rejected with validation code ${safeFailureToken(failureCode)}. Preserve your substantive investigation and recommendation, but replace the response file with a corrected record. This is your only correction attempt. Follow the exact allowed-key and integer constraints in the Required record section; do not add commentary, convenience fields, metadata, or movement for an external-decision seat.\n\n${basePrompt}`;
}

/**
 * The compact-record prompt for every retry after the previous attempt produced
 * too much output. Four call sites: the seat's automatic in-round retry after a
 * `length` stop, the operator's `retry` after any overlong seat failure, the
 * auditor's automatic in-cycle retry, and the operator's next `audit` after
 * `AUDIT_RESPONSE_SIZE_LIMIT`. The prior record was therefore either never
 * written (the model ran out of budget first) or written but oversized; either
 * way there is nothing to repair, so unlike a schema correction the instruction
 * is simply to spend the budget on the record instead of on narration.
 */
export function truncationRetryPrompt(basePrompt) {
  return `# Truncation retry\n\nYour previous attempt produced too much output: the model either reached its maximum output length (stop reason: length) or wrote a record past the response-size limit. This is your only retry. Keep the investigation bounded: do not narrate, do not echo file contents into your reply, write the JSON record to the response file FIRST with compact summaries and only the claims and citations you need, then stop.\n\n${basePrompt}`;
}

function approvedDisclosureView(state) {
  return {
    manifestSha256: state.disclosureManifest.manifestSha256,
    corpusSha256: state.disclosureManifest.corpusSha256,
    included: state.disclosureManifest.included.map((entry) => ({
      logicalPath: entry.logicalPath,
      physicalPath: `${WORKSPACE_DIR}/${entry.physicalPath}`,
      disposition: entry.disposition,
      bytes: entry.bytes,
      sha256: entry.sha256,
    })),
    excluded: state.disclosureManifest.excluded,
    probeDeclarations: state.disclosureManifest.probeDeclarations,
  };
}

/**
 * The prompt's pointer at the approved disclosure inventory, which is now a file
 * the seat reads rather than prompt text.
 *
 * Embedding it cost 707 KB of prompt on a ~2,000-entry repository — 2,030 entries,
 * measured on a live run — and every one of those bytes has to be paged through
 * the model's context and echoed back through pi's `--mode json` event stream,
 * which is part of how a live seat crossed the 4 MiB raw-output cap. A seat has
 * `read` in its tool allowlist and its cwd is the seat root, so the inventory
 * costs nothing until the seat opens it.
 *
 * The pointer stays self-sufficient: it names the file, says what is in it, and
 * carries the entry count and the corpus digest so a seat can prove it read the
 * inventory for this run rather than a stale one.
 */
function disclosurePointer(view) {
  const included = view.included.length;
  const excluded = view.excluded.length;
  return `The approved disclosure inventory is the JSON file ${DISCLOSURE_FILE} in this directory, beside ${PROMPT_FILE} and outside ${WORKSPACE_DIR}/. Read it before you cite anything. It holds "included" — every disclosed repository file as {logicalPath, physicalPath, disposition, bytes, sha256} — plus "excluded", "probeDeclarations", "manifestSha256", and "corpusSha256". It has exactly ${included} included ${included === 1 ? "entry" : "entries"} and ${excluded} ${excluded === 1 ? "exclusion" : "exclusions"}, its corpusSha256 is ${view.corpusSha256}, and its manifestSha256 is ${view.manifestSha256}. If the file you read does not carry that corpusSha256, stop and report it instead of citing. Cite only the approved logical paths and exact sha256 digests found there; repository bytes are below ${WORKSPACE_DIR}/ and citation paths never carry that prefix.`;
}

function disclosureContext(state) {
  const view = approvedDisclosureView(state);
  return { pointer: disclosurePointer(view), files: { [DISCLOSURE_FILE]: view } };
}

function roundOnePrompt(state, seat) {
  const expected = responseExpected(state, seat.id, 1);
  const externalSeatCount = state.resolvedRoster.externalDecisionSeats.length;
  const assuranceLevel = state.resolvedRoster.panelSpec?.assuranceLevel ?? "full";
  const disclosure = disclosureContext(state);
  return {
    text: `# Agent Council v3 — blind Round 1\n\nYou are one of ${externalSeatCount} external decision seats in a ${assuranceLevel}-assurance panel. The chair and other seats are independently producing records. You see no peer or chair recommendation. Inspect/search/edit only this disposable snapshot. You have no shell, web, LSP, MCP, plugins, skills, commands, nested agents, external directories, or package installation. Cite only the approved logical paths and exact digests from the disclosure inventory file named below. Runner-issued probe receipts are in the run context below; do not fabricate evidence.\n\n## Neutral decision brief\n\n${state.brief.text}\n\n## Approved disclosure inventory\n\n${disclosure.pointer}\n\n## Probe receipts\n\n${JSON.stringify(state.probeReceipts, null, 2)}\n\n## Required record\n\n${responseSchemaInstruction(expected, "external-decision")}`,
    context: disclosure.files,
  };
}

function roundTwoPrompt(state, seat, ownRoundOne) {
  const expected = responseExpected(state, seat.id, 2);
  const disclosure = disclosureContext(state);
  return {
    text: `# Agent Council v3 — peer-blind falsification Round 2\n\nRe-investigate independently. You receive only the neutral brief and your own validated Round-1 record. You do not receive peer positions or the chair recommendation. Try to falsify your prior claims and recommendation with repository evidence. Preserve or change your conclusion only for explicit reasons.\n\n## Brief\n\n${state.brief.text}\n\n## Approved disclosure inventory\n\n${disclosure.pointer}\n\n## Your Round-1 record\n\nYour own validated Round-1 record is the JSON file ${ROUND_CONTEXT_FILE} in this directory, under the key "ownRoundOneRecord". It is your prior position and nobody else's: no peer position and no chair recommendation is disclosed to you in this round.\n\n## Probe receipts\n\n${JSON.stringify(state.probeReceipts, null, 2)}\n\n## Required record\n\n${responseSchemaInstruction(expected, "external-decision")}`,
    context: {
      ...disclosure.files,
      [ROUND_CONTEXT_FILE]: { round: 2, seatId: seat.id, ownRoundOneRecord: ownRoundOne },
    },
  };
}

function roundThreePrompt(state, seat) {
  const expected = responseExpected(state, seat.id, 3);
  const disclosure = disclosureContext(state);
  const conflicts = state.round3.disagreements;
  const roundTwo = state.rounds.find((round) => round.number === 2);
  return {
    text: `# Agent Council v3 — conditional cross-examination Round 3\n\nThe core derived unresolved consequential disagreement. The conflicts are neutrally labelled. Recheck the repository, directly address the strongest conflicting evidence, and defend, revise, or concede with reasons. There is no fourth round.\n\n## Approved disclosure inventory\n\n${disclosure.pointer}\n\n## Derived conflicts\n\nThe ${conflicts.length} neutrally labelled derived ${conflicts.length === 1 ? "conflict is" : "conflicts are"} in the JSON file ${ROUND_CONTEXT_FILE} in this directory, under the key "derivedConflicts". The labels are neutral by construction; do not infer which seat holds which position.\n\n## Validated Round-2 records\n\nThe complete validated Round-2 round record, including every seat's position, is in the same file under the key "validatedRoundTwo".\n\n## Required record\n\n${responseSchemaInstruction(expected, "external-decision")}`,
    context: {
      ...disclosure.files,
      [ROUND_CONTEXT_FILE]: { round: 3, seatId: seat.id, derivedConflicts: conflicts, validatedRoundTwo: roundTwo },
    },
  };
}

function safeFailureToken(value, fallback = "UNKNOWN") {
  const token = String(value ?? fallback).toUpperCase().replace(/[^A-Z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  return token || fallback;
}

function classifyTransportResult(result) {
  if (result?.identityUnverified) {
    const proof = result.terminationObservation ? assessTerminationProof(result.processOwnership, result.terminationObservation) : null;
    return { ok: false, status: "transport_failed", probeStatus: "FAILED", failureCode: "PROCESS_IDENTITY_UNVERIFIED", proof };
  }
  if (result?.terminationObservation) {
    const proof = assessTerminationProof(result.processOwnership, result.terminationObservation);
    if (proof.kind !== "terminated") return { ok: false, status: "transport_failed", probeStatus: "FAILED", failureCode: "PROCESS_TREE_UNVERIFIED", proof };
  }
  if (result?.spawnError) return { ok: false, status: "transport_failed", probeStatus: "SPAWN_FAILED", failureCode: `SPAWN_${safeFailureToken(result.spawnError)}` };
  if (result?.timedOut) return { ok: false, status: "timed_out", probeStatus: "TIMED_OUT", failureCode: "TIMED_OUT" };
  if (result?.outputLimited) return { ok: false, status: "output_limit", probeStatus: "OUTPUT_LIMIT", failureCode: "OUTPUT_LIMIT" };
  if (result?.code !== 0) return { ok: false, status: "transport_failed", probeStatus: "FAILED", failureCode: `EXIT_${result?.code === null || result?.code === undefined ? "NULL" : safeFailureToken(result.code)}` };
  return { ok: true, status: "completed", probeStatus: "PASSED", failureCode: null };
}

function comparableOwnedPath(value, platform) {
  const resolved = path.resolve(value);
  return platform === "win32" ? resolved.toLowerCase() : resolved;
}

function processRecoveryDirectory(io, state) {
  const configuredTempRoot = path.resolve(io.tempRoot);
  const tempStat = recoveryLstat(io, configuredTempRoot, "UNSAFE_PROCESS_RECOVERY_TEMP_ROOT");
  if (typeof tempStat.isSymbolicLink !== "function" || typeof tempStat.isDirectory !== "function"
    || tempStat.isSymbolicLink() || !tempStat.isDirectory()) runnerFail("UNSAFE_PROCESS_RECOVERY_TEMP_ROOT");
  const tempRoot = path.resolve(recoveryRealpath(io, configuredTempRoot, "UNSAFE_PROCESS_RECOVERY_TEMP_ROOT"));
  const runFile = comparableOwnedPath(state.runFile, io.platform);
  const suffix = sha256Bytes(Buffer.from(canonicalJson({ runFile, runId: state.runId }), "utf8")).slice(7);
  const directory = path.join(tempRoot, `.agent-council-process-recovery-${suffix}`);
  if (comparableOwnedPath(path.dirname(directory), io.platform) !== comparableOwnedPath(tempRoot, io.platform)) runnerFail("UNSAFE_PROCESS_RECOVERY_DIRECTORY");
  return directory;
}

function processRecoveryFile(io, state, pid) {
  if (!Number.isSafeInteger(pid) || pid <= 0) runnerFail("INVALID_PROCESS_RECOVERY_PID");
  return path.join(processRecoveryDirectory(io, state), `${pid}.json`);
}

function processRecoveryOwnerFile(io, state) {
  return path.join(processRecoveryDirectory(io, state), PROCESS_RECOVERY_OWNER_FILE);
}

function processRecoveryOwnerRecord(state) {
  return {
    schemaVersion: 1,
    marker: PROCESS_RECOVERY_OWNER_MARKER,
    runFile: path.resolve(state.runFile),
    runId: state.runId,
    manifestSha256: state.disclosureManifest.manifestSha256,
  };
}

function processRecoveryRecord(state, ownership) {
  return {
    schemaVersion: 1,
    marker: PROCESS_RECOVERY_MARKER,
    runFile: path.resolve(state.runFile),
    runDirectory: path.dirname(path.resolve(state.runFile)),
    runId: state.runId,
    manifestSha256: state.disclosureManifest.manifestSha256,
    pid: ownership.pid,
    ...(ownership.processGroupId === undefined ? {} : { processGroupId: ownership.processGroupId }),
    processIdentity: ownership.processIdentity ?? null,
  };
}

function normalizedProcessRecoveryOwnership(state, ownership) {
  return {
    pid: ownership.pid,
    ...(ownership.processGroupId === undefined ? {} : { processGroupId: ownership.processGroupId }),
    processIdentity: ownership.processIdentity ?? null,
    runId: state.runId,
    manifestSha256: state.disclosureManifest.manifestSha256,
  };
}

function recoveryLstat(io, target, errorCode, { allowMissing = false } = {}) {
  try {
    return io.lstat(target);
  } catch (error) {
    if (allowMissing && error?.code === "ENOENT") return null;
    runnerFail(errorCode, { cause: safeFailureToken(error?.code ?? error?.name ?? "FAILED") });
  }
}

function recoveryRealpath(io, target, errorCode) {
  try {
    return io.realpath(target);
  } catch (error) {
    runnerFail(errorCode, { cause: safeFailureToken(error?.code ?? error?.name ?? "FAILED") });
  }
}

function validateProcessRecoveryDirectoryEntry(io, state, { allowMissing = false } = {}) {
  const directory = processRecoveryDirectory(io, state);
  const stat = recoveryLstat(io, directory, "UNSAFE_PROCESS_RECOVERY_DIRECTORY", { allowMissing });
  if (stat === null) return null;
  if (typeof stat.isSymbolicLink !== "function" || typeof stat.isDirectory !== "function"
    || stat.isSymbolicLink() || !stat.isDirectory()) runnerFail("UNSAFE_PROCESS_RECOVERY_DIRECTORY");
  const real = recoveryRealpath(io, directory, "UNSAFE_PROCESS_RECOVERY_DIRECTORY");
  if (comparableOwnedPath(real, io.platform) !== comparableOwnedPath(directory, io.platform)) runnerFail("UNSAFE_PROCESS_RECOVERY_DIRECTORY");
  return directory;
}

function validateProcessRecoveryRegularFile(io, state, file, errorCode, { allowMissing = false } = {}) {
  const directory = validateProcessRecoveryDirectoryEntry(io, state, { allowMissing: false });
  if (comparableOwnedPath(path.dirname(file), io.platform) !== comparableOwnedPath(directory, io.platform)) runnerFail(errorCode);
  const stat = recoveryLstat(io, file, errorCode, { allowMissing });
  if (stat === null) return null;
  if (typeof stat.isSymbolicLink !== "function" || typeof stat.isFile !== "function"
    || stat.isSymbolicLink() || !stat.isFile()) runnerFail(errorCode);
  const real = recoveryRealpath(io, file, errorCode);
  if (comparableOwnedPath(real, io.platform) !== comparableOwnedPath(file, io.platform)) runnerFail(errorCode);
  validateProcessRecoveryDirectoryEntry(io, state);
  return stat;
}

function readProcessRecoveryJson(io, state, file, label, errorCode) {
  validateProcessRecoveryRegularFile(io, state, file, errorCode);
  let bytes;
  try {
    bytes = io.readFile(file);
  } catch (error) {
    runnerFail(errorCode, { cause: safeFailureToken(error?.code ?? error?.name ?? "FAILED") });
  }
  validateProcessRecoveryRegularFile(io, state, file, errorCode);
  return parseJsonBytes(bytes, label);
}

function validateProcessRecoveryOwner(io, state, value) {
  if (!value || typeof value !== "object" || Array.isArray(value)
    || Object.keys(value).sort().join(",") !== "manifestSha256,marker,runFile,runId,schemaVersion"
    || value.schemaVersion !== 1
    || value.marker !== PROCESS_RECOVERY_OWNER_MARKER
    || typeof value.runFile !== "string" || !value.runFile
    || comparableOwnedPath(value.runFile, io.platform) !== comparableOwnedPath(state.runFile, io.platform)
    || value.runId !== state.runId
    || value.manifestSha256 !== state.disclosureManifest.manifestSha256) {
    runnerFail("INVALID_PROCESS_RECOVERY_OWNER");
  }
  return value;
}

function validateOwnedProcessRecoveryDirectory(io, state) {
  const directory = validateProcessRecoveryDirectoryEntry(io, state);
  const ownerFile = processRecoveryOwnerFile(io, state);
  const owner = readProcessRecoveryJson(io, state, ownerFile, "process-recovery-owner", "INVALID_PROCESS_RECOVERY_OWNER_ENTRY");
  validateProcessRecoveryOwner(io, state, owner);
  validateProcessRecoveryDirectoryEntry(io, state);
  return directory;
}

function processRecoveryInventory(io, state) {
  const directory = validateOwnedProcessRecoveryDirectory(io, state);
  let names;
  try {
    names = io.readDirectory(directory);
  } catch (error) {
    runnerFail("INVALID_PROCESS_RECOVERY_INVENTORY", { cause: safeFailureToken(error?.code ?? error?.name ?? "FAILED") });
  }
  if (!Array.isArray(names) || names.some((name) => typeof name !== "string" || path.basename(name) !== name)) runnerFail("INVALID_PROCESS_RECOVERY_INVENTORY");
  const sorted = [...names].sort();
  const recordNames = sorted.filter((name) => /^[1-9][0-9]*\.json$/.test(name));
  if (recordNames.length > 256 || sorted.length !== recordNames.length + 1 || !sorted.includes(PROCESS_RECOVERY_OWNER_FILE)) {
    runnerFail("INVALID_PROCESS_RECOVERY_INVENTORY");
  }
  validateProcessRecoveryRegularFile(io, state, processRecoveryOwnerFile(io, state), "INVALID_PROCESS_RECOVERY_OWNER_ENTRY");
  for (const name of recordNames) validateProcessRecoveryRegularFile(io, state, path.join(directory, name), "INVALID_PROCESS_RECOVERY_RECORD_ENTRY");
  validateOwnedProcessRecoveryDirectory(io, state);
  return recordNames;
}

function processRecoveryDirectoryIdentity(stat) {
  const valid = (value) => typeof value === "number" && Number.isSafeInteger(value) && value >= 0 || typeof value === "bigint" && value >= 0n;
  if (!stat || !valid(stat.dev) || !valid(stat.ino)) runnerFail("PROCESS_RECOVERY_DIRECTORY_IDENTITY_UNAVAILABLE");
  return `${String(stat.dev)}:${String(stat.ino)}`;
}

function captureCreatedProcessRecoveryDirectory(io, state) {
  const directory = validateProcessRecoveryDirectoryEntry(io, state);
  const stat = recoveryLstat(io, directory, "PROCESS_RECOVERY_DIRECTORY_IDENTITY_UNAVAILABLE");
  return { directory, identity: processRecoveryDirectoryIdentity(stat) };
}

function rollbackCreatedProcessRecoveryDirectory(io, state, createdDirectory) {
  const directory = validateProcessRecoveryDirectoryEntry(io, state);
  const assertSameDirectory = () => {
    const stat = recoveryLstat(io, directory, "PROCESS_RECOVERY_DIRECTORY_ROLLBACK_FAILED");
    if (processRecoveryDirectoryIdentity(stat) !== createdDirectory.identity) runnerFail("PROCESS_RECOVERY_DIRECTORY_ROLLBACK_OWNERSHIP_MISMATCH");
    validateProcessRecoveryDirectoryEntry(io, state);
  };
  if (comparableOwnedPath(directory, io.platform) !== comparableOwnedPath(createdDirectory.directory, io.platform)) {
    runnerFail("PROCESS_RECOVERY_DIRECTORY_ROLLBACK_OWNERSHIP_MISMATCH");
  }
  assertSameDirectory();
  let entries;
  try {
    entries = io.readDirectory(directory);
  } catch (error) {
    runnerFail("PROCESS_RECOVERY_DIRECTORY_ROLLBACK_FAILED", { cause: safeFailureToken(error?.code ?? error?.name ?? "FAILED") });
  }
  if (!Array.isArray(entries) || entries.length !== 0) runnerFail("PROCESS_RECOVERY_DIRECTORY_ROLLBACK_NOT_EMPTY");
  assertSameDirectory();
  try {
    io.removeEmptyDirectory(directory);
  } catch (error) {
    runnerFail("PROCESS_RECOVERY_DIRECTORY_ROLLBACK_FAILED", { cause: safeFailureToken(error?.code ?? error?.name ?? "FAILED") });
  }
  if (recoveryLstat(io, directory, "PROCESS_RECOVERY_DIRECTORY_ROLLBACK_DELETE_UNVERIFIED", { allowMissing: true }) !== null) {
    runnerFail("PROCESS_RECOVERY_DIRECTORY_ROLLBACK_DELETE_UNVERIFIED");
  }
}

function ensureOwnedProcessRecoveryDirectory(io, state) {
  const directory = processRecoveryDirectory(io, state);
  let created = false;
  try {
    io.mkdirExact(directory);
    created = true;
  } catch (error) {
    if (error?.code !== "EEXIST") runnerFail("PROCESS_RECOVERY_DIRECTORY_CREATE_FAILED", { cause: safeFailureToken(error?.code ?? error?.name ?? "FAILED") });
  }
  validateProcessRecoveryDirectoryEntry(io, state);
  const createdDirectory = created ? captureCreatedProcessRecoveryDirectory(io, state) : null;
  const ownerFile = processRecoveryOwnerFile(io, state);
  if (created) {
    if (recoveryLstat(io, ownerFile, "INVALID_PROCESS_RECOVERY_OWNER_ENTRY", { allowMissing: true }) !== null) runnerFail("PROCESS_RECOVERY_OWNER_CONFLICT");
    validateProcessRecoveryDirectoryEntry(io, state);
    try {
      stableWriteRecoveryJson(io, ownerFile, processRecoveryOwnerRecord(state));
    } catch (primaryError) {
      try {
        rollbackCreatedProcessRecoveryDirectory(io, state, createdDirectory);
      } catch (rollbackError) {
        throw new AgentCouncilRunnerError("PROCESS_RECOVERY_OWNER_WRITE_AND_DIRECTORY_ROLLBACK_FAILED", {
          primaryCode: safeFailureToken(primaryError?.code ?? primaryError?.name ?? "FAILED"),
          rollbackCode: safeFailureToken(rollbackError?.code ?? rollbackError?.name ?? "FAILED"),
        });
      }
      throw primaryError;
    }
  }
  validateOwnedProcessRecoveryDirectory(io, state);
  processRecoveryInventory(io, state);
  return directory;
}

function validateProcessRecoveryRecord(io, state, value, expectedPid) {
  if (!value || typeof value !== "object" || Array.isArray(value)) runnerFail("INVALID_PROCESS_RECOVERY_RECORD");
  const expectedKeys = ["manifestSha256", "marker", "pid", "processIdentity", "runDirectory", "runFile", "runId", "schemaVersion", ...(value.processGroupId === undefined ? [] : ["processGroupId"])].sort();
  if (Object.keys(value).sort().join(",") !== expectedKeys.join(",")
    || value.schemaVersion !== 1
    || value.marker !== PROCESS_RECOVERY_MARKER
    || typeof value.runFile !== "string" || !value.runFile
    || typeof value.runDirectory !== "string" || !value.runDirectory
    || typeof value.runId !== "string" || !value.runId
    || typeof value.manifestSha256 !== "string" || !/^sha256:[0-9a-f]{64}$/.test(value.manifestSha256)
    || comparableOwnedPath(value.runFile, io.platform) !== comparableOwnedPath(state.runFile, io.platform)
    || comparableOwnedPath(value.runDirectory, io.platform) !== comparableOwnedPath(path.dirname(state.runFile), io.platform)
    || value.runId !== state.runId
    || value.manifestSha256 !== state.disclosureManifest.manifestSha256
    || value.pid !== expectedPid
    || !Number.isSafeInteger(value.pid) || value.pid <= 0
    || value.processGroupId !== undefined && (!Number.isSafeInteger(value.processGroupId) || value.processGroupId <= 0)) {
    runnerFail("INVALID_PROCESS_RECOVERY_RECORD");
  }
  let processIdentity = null;
  if (value.processIdentity !== null) {
    const identity = value.processIdentity;
    if (!identity || typeof identity !== "object" || Array.isArray(identity)
      || Object.keys(identity).sort().join(",") !== "creationId,executable"
      || typeof identity.creationId !== "string" || !identity.creationId
      || typeof identity.executable !== "string" || !identity.executable) runnerFail("INVALID_PROCESS_RECOVERY_RECORD");
    processIdentity = { creationId: identity.creationId, executable: identity.executable };
  }
  return {
    pid: value.pid,
    ...(value.processGroupId === undefined ? {} : { processGroupId: value.processGroupId }),
    processIdentity,
    runId: state.runId,
    manifestSha256: state.disclosureManifest.manifestSha256,
  };
}

function readProcessRecoveryRecords(io, state) {
  const directory = validateProcessRecoveryDirectoryEntry(io, state, { allowMissing: true });
  if (directory === null) return [];
  const files = processRecoveryInventory(io, state);
  return files.map((file) => {
    const pid = Number(file.slice(0, -5));
    const recordFile = path.join(directory, file);
    const record = readProcessRecoveryJson(io, state, recordFile, "process-recovery", "INVALID_PROCESS_RECOVERY_RECORD_ENTRY");
    return validateProcessRecoveryRecord(io, state, record, pid);
  });
}

function mergeProcessRecoveryRecords(io, state) {
  for (const ownership of readProcessRecoveryRecords(io, state)) {
    const existing = state.processes.find((record) => record.pid === ownership.pid);
    if (existing && canonicalSha256(existing) !== canonicalSha256(ownership)) runnerFail("PROCESS_RECOVERY_STATE_MISMATCH", { pid: ownership.pid });
    if (!existing) state.processes.push(ownership);
  }
  return state;
}

function persistProcessRecoveryRecord(io, state, ownership) {
  const directory = ensureOwnedProcessRecoveryDirectory(io, state);
  const file = processRecoveryFile(io, state, ownership.pid);
  const record = processRecoveryRecord(state, ownership);
  const existingEntry = validateProcessRecoveryRegularFile(io, state, file, "INVALID_PROCESS_RECOVERY_RECORD_ENTRY", { allowMissing: true });
  if (existingEntry !== null) {
    const existing = validateProcessRecoveryRecord(io, state, readProcessRecoveryJson(io, state, file, "process-recovery", "INVALID_PROCESS_RECOVERY_RECORD_ENTRY"), ownership.pid);
    if (canonicalSha256(existing) !== canonicalSha256(normalizedProcessRecoveryOwnership(state, ownership))) runnerFail("PROCESS_RECOVERY_RECORD_CONFLICT", { pid: ownership.pid });
    return;
  }
  processRecoveryInventory(io, state);
  stableWriteRecoveryJson(io, file, record);
  processRecoveryInventory(io, state);
  const persisted = validateProcessRecoveryRecord(io, state, readProcessRecoveryJson(io, state, file, "process-recovery", "INVALID_PROCESS_RECOVERY_RECORD_ENTRY"), ownership.pid);
  if (canonicalSha256(persisted) !== canonicalSha256(normalizedProcessRecoveryOwnership(state, ownership))) runnerFail("PROCESS_RECOVERY_RECORD_MISMATCH", { pid: ownership.pid });
}

function removeProcessRecoveryRecord(io, state, ownership) {
  const directory = validateProcessRecoveryDirectoryEntry(io, state, { allowMissing: true });
  if (directory === null) return;
  processRecoveryInventory(io, state);
  const file = processRecoveryFile(io, state, ownership.pid);
  const existingEntry = validateProcessRecoveryRegularFile(io, state, file, "INVALID_PROCESS_RECOVERY_RECORD_ENTRY", { allowMissing: true });
  if (existingEntry !== null) {
    const existing = validateProcessRecoveryRecord(io, state, readProcessRecoveryJson(io, state, file, "process-recovery", "INVALID_PROCESS_RECOVERY_RECORD_ENTRY"), ownership.pid);
    const expected = normalizedProcessRecoveryOwnership(state, ownership);
    if (canonicalSha256(existing) !== canonicalSha256(expected)) runnerFail("PROCESS_RECOVERY_RECORD_MISMATCH", { pid: ownership.pid });
    validateOwnedProcessRecoveryDirectory(io, state);
    validateProcessRecoveryRegularFile(io, state, file, "INVALID_PROCESS_RECOVERY_RECORD_ENTRY");
    try {
      io.removeFile(file);
    } catch (error) {
      runnerFail("PROCESS_RECOVERY_RECORD_REMOVE_FAILED", { pid: ownership.pid, cause: safeFailureToken(error?.code ?? error?.name ?? "FAILED") });
    }
    if (recoveryLstat(io, file, "PROCESS_RECOVERY_DELETE_UNVERIFIED", { allowMissing: true }) !== null) runnerFail("PROCESS_RECOVERY_DELETE_UNVERIFIED", { pid: ownership.pid });
  }
  const remaining = processRecoveryInventory(io, state);
  if (remaining.length === 0) {
    const ownerFile = processRecoveryOwnerFile(io, state);
    validateOwnedProcessRecoveryDirectory(io, state);
    validateProcessRecoveryRegularFile(io, state, ownerFile, "INVALID_PROCESS_RECOVERY_OWNER_ENTRY");
    try {
      io.removeFile(ownerFile);
    } catch (error) {
      runnerFail("PROCESS_RECOVERY_OWNER_REMOVE_FAILED", { cause: safeFailureToken(error?.code ?? error?.name ?? "FAILED") });
    }
    if (recoveryLstat(io, ownerFile, "PROCESS_RECOVERY_OWNER_DELETE_UNVERIFIED", { allowMissing: true }) !== null) runnerFail("PROCESS_RECOVERY_OWNER_DELETE_UNVERIFIED");
    validateProcessRecoveryDirectoryEntry(io, state);
    let finalEntries;
    try {
      finalEntries = io.readDirectory(directory);
    } catch (error) {
      runnerFail("PROCESS_RECOVERY_DIRECTORY_REMOVE_FAILED", { cause: safeFailureToken(error?.code ?? error?.name ?? "FAILED") });
    }
    if (!Array.isArray(finalEntries) || finalEntries.length !== 0) runnerFail("PROCESS_RECOVERY_DIRECTORY_NOT_EMPTY");
    validateProcessRecoveryDirectoryEntry(io, state);
    try {
      io.removeEmptyDirectory(directory);
    } catch (error) {
      runnerFail("PROCESS_RECOVERY_DIRECTORY_REMOVE_FAILED", { cause: safeFailureToken(error?.code ?? error?.name ?? "FAILED") });
    }
    if (recoveryLstat(io, directory, "PROCESS_RECOVERY_DIRECTORY_DELETE_UNVERIFIED", { allowMissing: true }) !== null) runnerFail("PROCESS_RECOVERY_DIRECTORY_DELETE_UNVERIFIED");
  }
}

function persistProcessOwnership(state, ownership) {
  if (!Number.isSafeInteger(ownership?.pid) || ownership.pid <= 0 || state.processes.some((record) => record.pid === ownership.pid)) return;
  state.processes.push({
    pid: ownership.pid,
    ...(ownership.processGroupId === undefined ? {} : { processGroupId: ownership.processGroupId }),
    processIdentity: ownership.processIdentity ?? null,
    runId: state.runId,
    manifestSha256: state.disclosureManifest.manifestSha256,
  });
}

function invocationLifecycle(io, state) {
  return {
    onProcessStarted: async (ownership) => {
      persistProcessRecoveryRecord(io, state, ownership);
      const previousUpdatedAt = state.updatedAt;
      const existed = state.processes.some((record) => record.pid === ownership.pid);
      persistProcessOwnership(state, ownership);
      state.updatedAt = io.now();
      try {
        writeRun(io, state);
      } catch (error) {
        if (!existed) state.processes = state.processes.filter((record) => record.pid !== ownership.pid);
        state.updatedAt = previousUpdatedAt;
        throw error;
      }
    },
    onProcessSettled: async (ownership) => {
      const index = state.processes.findIndex((record) => record.pid === ownership.pid
        && (record.processGroupId ?? null) === (ownership.processGroupId ?? null)
        && record.runId === ownership.runId
        && canonicalSha256(record.processIdentity) === canonicalSha256(ownership.processIdentity ?? null));
      if (index < 0) runnerFail("PROCESS_OWNERSHIP_SETTLEMENT_MISMATCH", { pid: ownership.pid });
      const [removed] = state.processes.splice(index, 1);
      const previousUpdatedAt = state.updatedAt;
      state.updatedAt = io.now();
      try {
        writeRun(io, state);
      } catch (error) {
        state.processes.splice(index, 0, removed);
        state.updatedAt = previousUpdatedAt;
        throw error;
      }
      removeProcessRecoveryRecord(io, state, ownership);
    },
    onProcessRecoverySettled: async (ownership) => removeProcessRecoveryRecord(io, state, ownership),
  };
}

async function executeExternalAttempt(io, state, seat, round, attempt, prompt, context) {
  const root = runRoot(state);
  const directory = state.seatDirectories[seat.id];
  const responseFile = writePrompt(io, directory, prompt, context);
  const title = `${state.runId}:${seat.id}:r${round}:a${attempt}`;
  const expected = responseExpected(state, seat.id, round);
  const adapterName = seat.qualification.adapter.name;
  // Which door writes the record is a declared adapter fact, not a name
  // comparison: a `writesResponseFile` transport writes the response file at
  // the seat root itself, and every other adapter returns a structured envelope
  // the runner materializes. The offline fake adapter declares the same
  // contract explicitly through `invokeSeatWritesResponseFile`. An unknown
  // adapter has no declared row and takes the materialization path, which then
  // fails by name in `parseNativeStructuredResponse`.
  const fileWritingAdapter = adapterContract(adapterName)?.writesResponseFile === true || io.invokeSeatWritesResponseFile === true;
  const result = await io.invokeSeat({
    cwd: directory,
    model: seat.model,
    variant: seat.variant,
    adapterName,
    seatId: seat.id,
    runtimeRoot: runRoot(state),
    responseSchema: externalResponseJsonSchema(expected),
    title,
    environment: seatEnvironmentFor(io, state, seat),
    timeoutMs: AGENT_COUNCIL_LIMITS.seatTimeoutMs,
    maxOutputBytes: AGENT_COUNCIL_LIMITS.rawModelOutputBytes,
    runId: state.runId,
    ...invocationLifecycle(io, state),
  });
  const rawPrefix = path.join(root, RAW_DIR, `${seat.id}-r${round}-a${attempt}`);
  io.writeFile(`${rawPrefix}.stdout.txt`, result.stdout ?? "");
  io.writeFile(`${rawPrefix}.stderr.txt`, result.stderr ?? "");
  // A filtered door leaves a retained stream in `.stdout.txt`, not the child's
  // whole stdout. Saying so beside it is the difference between disposable
  // evidence and misleading evidence; the counts are the transport's own, and
  // the attempt record's closed schema carries no such field.
  if (result.streamFilter) io.writeFile(`${rawPrefix}.stdout.filter.json`, `${JSON.stringify(result.streamFilter)}\n`);
  const transport = classifyTransportResult(result);
  if (!transport.ok) return { ...transport, attempt, processOwnership: ["PROCESS_TREE_UNVERIFIED", "PROCESS_IDENTITY_UNVERIFIED"].includes(transport.failureCode) ? result.processOwnership : null };
  // A file-writing seat is a pi seat (or the offline fake that declares the same
  // contract), so its stdout is a `--mode json` stream that names why the model
  // stopped. `length` is the only truncation signal: a length stop
  // inside the `write` tool call leaves no response file, which is otherwise
  // indistinguishable from a refusal. Native seats have no such stream.
  const stream = fileWritingAdapter ? parsePiJsonStream(result.stdout) : null;
  const truncatedStop = stream?.stopReason === "length";
  const stopReason = ledgerStopReason(stream?.stopReason);
  if (!fileWritingAdapter) {
    try {
      stableWriteJson(io, responseFile, parseNativeStructuredResponse(adapterName, result.stdout));
    } catch (error) {
      // Every throw from this path is a named runner failure: `parseNativeJson`
      // converts a raw `SyntaxError` into `NATIVE_STRUCTURED_RESPONSE_SCHEMA_INVALID`
      // so a V8 parser message can never carry a slice of the child's stdout
      // into the ledger. Anything else is an internal defect and propagates.
      if (error instanceof AgentCouncilRunnerError) {
        return { status: "invalid_response", attempt, failureCode: safeFailureToken(error?.code ?? "INVALID_NATIVE_STRUCTURED_RESPONSE") };
      }
      throw error;
    }
  }
  if (!io.exists(responseFile)) {
    if (truncatedStop) return { status: "truncated", attempt, failureCode: "TRUNCATED", stopReason };
    // A file-writing stream that never produced an assistant message_end did not
    // run out of budget, it never spoke. Naming it separately keeps the automatic
    // truncation retry for the failure a retry can actually fix and sends this
    // one to the operator with the cause on the record. The gate is the presence
    // of the turn, not the presence of a stop-reason label: a seat that answered
    // with an unlabelled stop is a missing record, not silence.
    if (stream && !stream.sawAssistantMessage) return { status: "invalid_response", attempt, failureCode: "PI_NO_ASSISTANT_TURN" };
    return { status: "invalid_response", attempt, failureCode: "MISSING_STRUCTURED_RESPONSE", stopReason };
  }
  const bytes = io.readFile(responseFile);
  if (bytes.length > AGENT_COUNCIL_LIMITS.seatResponseBytes) return { status: "invalid_response", attempt, failureCode: "RESPONSE_SIZE_LIMIT", stopReason };
  let response;
  try {
    response = validateSeatResponse({ expected, response: parseJsonBytes(bytes, "seat-response"), disclosure: state.disclosureManifest, receipts: state.probeReceipts });
  } catch (error) {
    if (error instanceof AgentCouncilRunnerError && error.code === "INVALID_JSON_FILE" && truncatedStop) {
      // A half-written record plus an explicit length stop is the same failure
      // as no record at all. A *schema* rejection is not: the model finished a
      // well-formed record and got the shape wrong, which is the operator's
      // schema-correction retry, not this one.
      return { status: "truncated", attempt, failureCode: "TRUNCATED", stopReason };
    }
    if (error instanceof AgentCouncilValidationError || error instanceof AgentCouncilRunnerError && error.code === "INVALID_JSON_FILE") return { status: "invalid_response", attempt, failureCode: error.code, stopReason };
    throw error;
  }
  const positionFile = path.join(root, POSITIONS_DIR, `${seat.id}-r${round}.json`);
  stableWriteJson(io, positionFile, response);
  const diff = io.seatDiff(directory);
  // A validated record wins over a `length` stop: the seat produced its evidence
  // before running out of budget. The stop reason is still named in the ledger.
  return { status: "completed", attempt, response, positionFile, diff, stopReason };
}

/**
 * The transport's stop reason as the ledger may record it, or `undefined`.
 *
 * Classification above compares the raw stream value exactly; this bounds only
 * what is persisted, because the run state is re-validated on every write and an
 * unbounded vendor string would fail the whole write. Designed degradation: an
 * absent, empty, or over-long label is dropped rather than truncated or widened
 * — the attempt still carries its status and failure code, which is what any
 * verdict reads.
 */
function ledgerStopReason(value) {
  if (typeof value !== "string" || value.trim().length === 0 || value.length > STOP_REASON_MAX_CHARS) return undefined;
  return value;
}

export function externalAttemptContext(record, seatId) {
  const priorAttempts = record.attempts.filter((entry) => entry.seatId === seatId);
  return { attempt: priorAttempts.length + 1, previousAttempt: priorAttempts.at(-1) ?? null };
}

function readChair(io, state, file, round) {
  const host = state.resolvedRoster.host;
  const expected = responseExpected(state, host.id, round);
  const { bytes } = readRequiredText(io, file, `chair-r${round}`, AGENT_COUNCIL_LIMITS.seatResponseBytes);
  return validateChairResponse({ expected, response: parseJsonBytes(bytes, `chair-r${round}`), disclosure: state.disclosureManifest, receipts: state.probeReceipts });
}

async function executeOpenedRound(io, state, round, chair, selectedSeats = null) {
  if (state.processes.length) runnerFail("UNRESOLVED_PROCESS_OWNERSHIP");
  const seats = selectedSeats ?? state.resolvedRoster.externalDecisionSeats;
  let record = state.rounds.find((candidate) => candidate.number === round);
  if (!record) {
    record = { number: round, status: "running", chair: null, externals: [], attempts: [] };
    state.rounds.push(record);
  }
  if (record.attempts.some((attempt) => attempt.status === "running" && seats.some((seat) => seat.id === attempt.seatId))) {
    runnerFail("UNRESOLVED_RUNNING_ATTEMPT", { round });
  }
  record.status = "running";
  record.chair = chair;
  const unexpected = [];
  // One dispatch pass per iteration. The first pass is the seats the caller
  // opened the round with; every later pass is the automatic truncation retry
  // — the only failure the runner retries without the operator. Every
  // other failure status keeps today's operator-driven `retry` command.
  let pending = seats;
  while (pending.length) {
    const taskSpecs = pending.map((seat) => {
      const { attempt, previousAttempt } = externalAttemptContext(record, seat.id);
      if (attempt > AGENT_COUNCIL_LIMITS.attemptsPerSeatPerRound) runnerFail("SEAT_ATTEMPT_LIMIT", { seatId: seat.id, round });
      const previousRound = state.rounds.find((candidate) => candidate.number === round - 1);
      // The round prompt and the bounded context files it points at are built
      // together: a retry wrapper only ever prefixes the prompt text, and the
      // context the seat reads must stay the round's own.
      const built = round === 1
        ? roundOnePrompt(state, seat)
        : round === 2
          ? roundTwoPrompt(state, seat, previousRound.externals.find((response) => response.seatId === seat.id))
          : roundThreePrompt(state, seat);
      const basePrompt = built.text;
      let prompt = basePrompt;
      // Retry-prompt selection, mirroring `executeAuditAttempt` exactly. The
      // persisted ledger lowercases both status and failure code, so compare
      // normalized rather than against the runner's raised uppercase form.
      const previousCode = String(previousAttempt?.failureCode ?? "").toLowerCase();
      // Wrote no record at all: a schema lecture would claim a record was
      // rejected when none was ever written.
      const previousWroteNoRecord = previousAttempt?.status === "invalid_response"
        && MISSING_SEAT_RECORD_CODES.includes(previousCode);
      if (attempt > 1) {
        if (previousAttemptOverflowed(previousAttempt)) prompt = truncationRetryPrompt(basePrompt);
        else if (previousWroteNoRecord) prompt = `${MISSING_SEAT_RECORD_CORRECTION}\n\n${basePrompt}`;
        // A schema correction is only meaningful when a record existed and was
        // wrong. Everything left over — `timed_out`, `transport_failed` — is a
        // transport fault the seat cannot correct, so it gets the bare prompt.
        else if (previousAttempt?.status === "invalid_response") prompt = schemaCorrectionPrompt(basePrompt, previousAttempt.failureCode);
      }
      const attemptRecord = { status: "running", round, seatId: seat.id, attempt, startedAt: io.now() };
      record.attempts.push(attemptRecord);
      return { seat, attempt, prompt, context: built.context };
    });
    state.attempts = state.rounds.flatMap((roundRecord) => roundRecord.attempts);
    state.updatedAt = io.now();
    state = writeRun(io, state);
    record = state.rounds.find((candidate) => candidate.number === round);
    const tasks = taskSpecs.map((task) => ({
      ...task,
      promise: executeExternalAttempt(io, state, task.seat, round, task.attempt, task.prompt, task.context),
    }));
    const settled = await Promise.allSettled(tasks.map((task) => task.promise));
    const results = settled.map((entry, index) => {
      const task = tasks[index];
      if (entry.status === "fulfilled") return [task.seat, entry.value];
      unexpected.push(entry.reason);
      // Name the cause on the attempt record. A bare UNEXPECTED_ATTEMPT_FAILURE
      // told the operator only that something inside the runner threw; the
      // aggregate error already carries this token, so the ledger and the raised
      // error now agree on which internal failure consumed the attempt.
      return [task.seat, {
        status: "transport_failed",
        failureCode: `UNEXPECTED_${safeFailureToken(entry.reason?.code ?? entry.reason?.name ?? "ATTEMPT_FAILURE")}`,
        attempt: task.attempt,
        processOwnership: entry.reason?.agentCouncilProcessOwnership ?? null,
      }];
    });
    for (const [seat, result] of results) {
      const attemptRecord = record.attempts.find((entry) => entry.seatId === seat.id && entry.attempt === result.attempt);
      if (!attemptRecord || attemptRecord.status !== "running") runnerFail("ATTEMPT_RECORD_TRANSITION_MISMATCH", { seatId: seat.id, round, attempt: result.attempt });
      attemptRecord.status = result.status;
      attemptRecord.completedAt = io.now();
      if (result.failureCode) attemptRecord.failureCode = result.failureCode;
      if (result.stopReason) attemptRecord.stopReason = result.stopReason;
      persistProcessOwnership(state, result.processOwnership);
      if (result.status === "completed") {
        record.externals = record.externals.filter((response) => response.seatId !== seat.id);
        record.externals.push(result.response);
        state.seatDiffs.push({ seatId: seat.id, round, diff: result.diff });
      }
    }
    state.attempts = state.rounds.flatMap((roundRecord) => roundRecord.attempts);
    // A seat already at the per-round attempt limit is not retried: it stays a
    // named `truncated` attempt and the round fails on completeness (no
    // degraded panel). Filtering here also keeps the `SEAT_ATTEMPT_LIMIT` throw
    // above reachable only from the operator-opened first pass.
    // An unresolved process survivor closes the round instead of throwing here:
    // a throw inside this loop would abandon the terminal writeRun below and
    // strand this pass settled attempts as running in the persisted ledger,
    // which blocks every later command. The survivor still blocks relaunch at
    // the top of the next opened round.
    pending = state.processes.length ? [] : results
      .filter(([, result]) => result.status === "truncated")
      .map(([seat]) => seat)
      .filter((seat) => externalAttemptContext(record, seat.id).attempt <= AGENT_COUNCIL_LIMITS.attemptsPerSeatPerRound);
  }
  const complete = state.resolvedRoster.externalDecisionSeats.every((seat) => record.externals.some((response) => response.seatId === seat.id));
  record.status = complete ? "complete" : "failed";
  if (complete) {
    const event = round === 1 ? "COMPLETE_R1" : round === 2 ? "COMPLETE_R2" : "COMPLETE_R3";
    state.milestone = nextMilestone(state.milestone, event);
    if (round === 2) {
      const round2 = [chair, ...record.externals];
      const disagreements = deriveConsequentialDisagreements({ round2, roster: state.resolvedRoster, annotations: state.disagreementAnnotations ?? [] });
      state.round3 = { ...evaluateRound3({ round2, disagreements, roster: state.resolvedRoster }), disagreements };
    }
  }
  state.updatedAt = io.now();
  state = writeRun(io, state);
  if (unexpected.length) {
    throw new AgentCouncilRunnerError("UNEXPECTED_PARALLEL_SEAT_FAILURE", {
      failures: unexpected.map((error) => safeFailureToken(error?.code ?? error?.name ?? "UNKNOWN")),
    });
  }
  return state;
}

async function executeProbes(io, state) {
  if (state.probesExecuted) return state;
  if (state.processes.length) runnerFail("UNRESOLVED_PROCESS_OWNERSHIP");
  const root = runRoot(state);
  const probeRoot = path.join(root, "probes");
  io.mkdir(probeRoot);
  for (const spec of state.probeSpecs) {
    if (state.probeReceipts.some((receipt) => receipt.payload.id === spec.id)) continue;
    const copy = path.join(probeRoot, spec.id);
    copyVerifiedCorpus(io, state, copy);
    const runtimeSpecs = resolveLiveProbeSpecs(io, state);
    const runtimeSpec = runtimeSpecs.find((candidate) => candidate.id === spec.id);
    if (!runtimeSpec) runnerFail("LIVE_PROBE_SPEC_MISSING", { probeId: spec.id });
    const started = Date.parse(io.now());
    const result = await io.runProbe(runtimeSpec, { cwd: copy, environment: probeEnvironmentFor(io), runId: state.runId, ...invocationLifecycle(io, state) });
    const durationMs = Math.max(0, Date.parse(io.now()) - started);
    const transport = classifyTransportResult(result);
    let status = transport.probeStatus;
    let disclosedOutput = `${result.stdout ?? ""}${result.stderr ?? ""}`.slice(0, AGENT_COUNCIL_LIMITS.probeOutputBytes);
    const detector = scanSecretBytes(Buffer.from(disclosedOutput, "utf8"));
    if (detector) {
      status = "REJECTED_SECRET";
      disclosedOutput = null;
    }
    const hasOutputDigest = !["SPAWN_FAILED", "REJECTED_SECRET"].includes(status);
    const payload = {
      schemaVersion: 1,
      id: runtimeSpec.id,
      specSha256: runtimeSpec.specSha256,
      corpusSha256: runtimeSpec.corpusSha256,
      status,
      exitCode: status === "PASSED" ? 0 : status === "FAILED" ? (Number.isInteger(result.code) && result.code !== 0 ? result.code : -1) : null,
      durationMs: status === "TIMED_OUT" ? Math.max(durationMs, AGENT_COUNCIL_LIMITS.probeTimeoutMs) : durationMs,
      outputSha256: hasOutputDigest ? sha256Bytes(Buffer.from(`${result.stdout ?? ""}${result.stderr ?? ""}`, "utf8")) : null,
      disclosedOutput,
      truncated: status === "OUTPUT_LIMIT",
    };
    const receipt = normalizeProbeReceipt({ payload, receiptSha256: canonicalSha256(payload) });
    state.probeReceipts.push(receipt);
    if (transport.failureCode === "PROCESS_IDENTITY_UNVERIFIED") {
      persistProcessOwnership(state, result.processOwnership);
      state.probesExecuted = false;
      state = writeRun(io, state);
      runnerFail("PROBE_PROCESS_IDENTITY_UNVERIFIED", { probeId: spec.id });
    }
    if (transport.failureCode === "PROCESS_TREE_UNVERIFIED") {
      persistProcessOwnership(state, result.processOwnership);
      state.probesExecuted = false;
      state = writeRun(io, state);
      runnerFail("PROBE_PROCESS_TREE_UNVERIFIED", { probeId: spec.id });
    }
  }
  state.probesExecuted = true;
  return writeRun(io, state);
}

function auditBundle(state, synthesis, chair) {
  return {
    schemaVersion: 2,
    runId: state.runId,
    brief: state.brief,
    disclosureManifest: state.disclosureManifest,
    resolvedRoster: state.resolvedRoster,
    authorization: state.authorization,
    probeSpecs: state.probeSpecs,
    probeReceipts: state.probeReceipts,
    attempts: state.attempts,
    rounds: state.rounds,
    seatDiffs: state.seatDiffs,
    round3: state.round3,
    disagreementAnnotations: state.disagreementAnnotations,
    auditAttempts: state.auditAttempts,
    auditHistory: state.auditHistory,
    auditRevision: state.auditRevision,
    claimReferenceIndex: buildAuditClaimReferenceIndex(state.rounds),
    chair,
    synthesis,
  };
}

export { auditBundle as buildAuditBundle };

function auditReferenceUniverses(bundle) {
  return {
    claimIds: bundle.claimReferenceIndex.map((reference) => reference.qualifiedId),
    evidenceRefs: [
      ...bundle.disclosureManifest.included.map((entry) => `citation:${entry.logicalPath}`),
      ...bundle.probeReceipts.map((receipt) => `receipt:${receipt.payload.id}`),
      ...bundle.seatDiffs.flatMap((diff) => diff.diff.map((entry) => `diff:${diff.seatId}:${diff.round}:${entry.logicalPath}`)),
      ...(bundle.round3?.disagreements ?? []).flatMap((entry) => entry.evidenceRefs ?? []),
    ],
  };
}

function auditInputSha256(bundle, revision, nonce, cycle) {
  return canonicalSha256({ schemaVersion: 1, cycle, nonce, bundle, revision: revision ?? null });
}

function auditBundleBeforeAttempt(bundle, cycle, attempt) {
  return {
    ...bundle,
    auditAttempts: bundle.auditAttempts.filter((record) => !(record.cycle === cycle && record.attempt === attempt)),
  };
}

function auditAttemptMatchesInput(attempt, bundle, revision, nonce, cycle) {
  return attempt.cycle === cycle && attempt.status === "completed"
    && attempt.auditInputSha256 === auditInputSha256(auditBundleBeforeAttempt(bundle, cycle, attempt.attempt), revision, nonce, cycle);
}

function adoptCompletedAuditResponse(io, state, bundle, revision) {
  const cycle = revision ? 2 : 1;
  const nonce = state.nonces.audit[String(cycle)];
  const completedAttempt = state.auditAttempts.find((attempt) => auditAttemptMatchesInput(attempt, bundle, revision, nonce, cycle));
  if (state.auditHistory.length >= cycle || !completedAttempt) return null;
  const responseFile = path.join(runRoot(state), AUDITOR_DIR, state.resolvedRoster.auditor.id, RESPONSE_FILE);
  if (!io.exists(responseFile)) return null;
  try {
    const bytes = io.readFile(responseFile);
    if (bytes.length > AGENT_COUNCIL_LIMITS.seatResponseBytes) return null;
    const universes = auditReferenceUniverses(bundle);
    return io.validateAuditResponse({
      expectedRunId: state.runId,
      expectedNonce: nonce,
      expectedSeatId: state.resolvedRoster.auditor.id,
      expectedClaimIds: universes.claimIds,
      expectedEvidenceRefs: universes.evidenceRefs,
      value: parseJsonBytes(bytes, "audit-response-adoption"),
    });
  } catch (error) {
    if (error instanceof AgentCouncilValidationError || error instanceof AgentCouncilRunnerError && error.code === "INVALID_JSON_FILE") return null;
    throw error;
  }
}

/**
 * The audit prompt and its bounded context file.
 *
 * The bundle is larger than any seat's disclosure inventory — it embeds the
 * whole disclosure manifest plus every attempt, position, receipt, and diff —
 * and the evidence-reference universe carries one entry per included file, so
 * on a real repository the correction retry was the largest prompt the runner
 * produced. Both are now keys of ${AUDIT_BUNDLE_FILE} in the auditor root. The
 * response-file contract, the identity block, and every instruction about
 * citation shape stay inline: the auditor must not have to open a file to learn
 * what it is being asked to produce.
 */
function auditPrompt(state, bundle, nonce, revision = null, correction = null) {
  const universes = auditReferenceUniverses(bundle);
  const correctionBlock = correction
    ? `\n\n## Required schema correction\n\nThe prior response failed validation with code ${JSON.stringify(correction.failureCode)}. Replace the entire response file. Every claimIds entry and every evidenceRefs entry MUST be a JSON string, never an object. evidenceRefs strings MUST be selected exactly from the allowed universe in ${AUDIT_BUNDLE_FILE} under the key "evidenceUniverse.evidenceRefs" (${universes.evidenceRefs.length} ${universes.evidenceRefs.length === 1 ? "entry" : "entries"}), for example "citation:<approved logical path>" or "receipt:<runner-issued receipt id>". claimIds strings MUST be selected exactly from claimReferenceIndex qualifiedId values. All id, statement, summary, and nonce fields are strings.`
    : "";
  const bundlePointer = `The complete audit bundle is the JSON file ${AUDIT_BUNDLE_FILE} in this directory, beside ${PROMPT_FILE} and outside ${WORKSPACE_DIR}/. Read it before you judge anything. Its "bundle" key holds the run id, brief, disclosure and roster manifests, probe specs and receipts, every attempt from every opened round, seat diffs, derived disagreements, the claim reference index, the chair record, and the synthesis. Its "evidenceUniverse" key holds the only accepted claimIds (${universes.claimIds.length}) and evidenceRefs (${universes.evidenceRefs.length}). The bundle's disclosureManifest.corpusSha256 is ${state.disclosureManifest.corpusSha256}; if the file you read does not carry that digest, stop and report it instead of judging.`;
  return {
    text: `# Agent Council v3 — independent evidence and synthesis audit\n\nYou are the independent auditor, never a decision seat. Verify cited repository evidence in this fresh canonical snapshot; repository bytes are below ${WORKSPACE_DIR}/, while citations retain their approved logical paths without that prefix. Inspect every attempt, failure, retry, position, movement, receipt, diff, conflict, dissent, and synthesis statement. Do not add a vote. Finding claimIds must use only qualified ids from claimReferenceIndex (r{round}:sha256:{digest}); raw claim ids are invalid. Finding evidenceRefs must be string identifiers from the allowed evidence-reference universe, not citation objects.\n\n## Complete audit bundle\n\n${bundlePointer}\n\n${revision ? `## Chair revision\n\nThe chair's revision response is in the same file under the key "chairRevision".\n\n` : ""}Write JSON only to ${RESPONSE_FILE}: {schemaVersion:2,runId:${JSON.stringify(state.runId)},seatId:${JSON.stringify(state.resolvedRoster.auditor.id)},role:"auditor",nonce:${JSON.stringify(nonce)},verdict:"FAITHFUL"|"NEEDS-REVISION",summary:string,findings:[{id:string,statement:string,severity:"advisory"|"material"|"fatal",claimIds:["r2:sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"],evidenceRefs:["citation:logical/path.ext"],remedy:"SYNTHESIS_REVISION"|"NEW_EVIDENCE_REQUIRED"}],omittedDissentIds:[]}. A FAITHFUL verdict may contain advisory findings only.${correctionBlock}`,
    context: {
      [AUDIT_BUNDLE_FILE]: { bundle, evidenceUniverse: universes, chairRevision: revision ?? null },
    },
  };
}

// The "too much output" family, however it was detected: a `length` stop with
// no usable record, a record that arrived whole but past the response limit, or
// the raw-output ceiling that killed the child. Whichever side raised it the
// honest instruction is identical — spend the budget on the record — so both
// the seat and the audit selector route it to `truncationRetryPrompt` instead
// of a schema lecture about a shape that was never the fault. Statuses and
// codes are listed in the persisted lowercase form; a seat never carries the
// audit code and the auditor never carries the seat one.
const OVERLONG_OUTPUT_STATUSES = Object.freeze(["truncated", "output_limit"]);
const OVERLONG_OUTPUT_CODES = Object.freeze(["response_size_limit", "audit_response_size_limit", "output_limit"]);

function previousAttemptOverflowed(previousAttempt) {
  const status = String(previousAttempt?.status ?? "").toLowerCase();
  const failureCode = String(previousAttempt?.failureCode ?? "").toLowerCase();
  return OVERLONG_OUTPUT_STATUSES.includes(status) || OVERLONG_OUTPUT_CODES.includes(failureCode);
}

// A schema lecture is the wrong correction when there was no record to reject.
// Both prompts say the same thing to their own reader: there is nothing to
// correct, so write the record first and stop.
const MISSING_SEAT_RECORD_CORRECTION = "# Missing record retry\n\nYour previous attempt wrote no record at all: the response file was never created, so nothing was rejected and there is nothing to correct. Write the JSON record for your decision seat to the response file FIRST, compactly, before any further investigation, then stop.";

const MISSING_AUDIT_RECORD_CORRECTION = "# Missing record retry\n\nYour previous attempt wrote no audit record at all: the response file was never created. No record was written, so there is nothing to correct. Write the JSON record to the response file FIRST, compactly, before any further investigation, then stop.";

// Failure codes whose correct retry instruction is the missing-record prompt
// rather than the schema-correction block. Stored lowercase in the ledger,
// which is what a previous attempt carries by the time it is read here.
const MISSING_SEAT_RECORD_CODES = Object.freeze(["missing_structured_response", "pi_no_assistant_turn"]);
const MISSING_AUDIT_RECORD_CODES = Object.freeze(["missing_structured_response", "pi_no_assistant_turn"]);

// The crash-adoption window re-settles a *valid* completed attempt as
// `invalid_response` because the bundle moved, not because the record was
// wrong. Nothing failed validation, so a schema lecture would name a fault that
// did not happen — and nothing the auditor writes could have prevented the
// input from changing, so the retry gets the bare prompt. Its sibling
// `AUDIT_ADOPTION_RESPONSE_INVALID` stays on the schema path: that record
// really was rejected.
const AUDIT_INPUT_DRIFT_CODES = Object.freeze(["audit_input_changed"]);

async function executeAuditAttempt(io, state, bundle, revision) {
  if (state.processes.length) runnerFail("UNRESOLVED_PROCESS_OWNERSHIP");
  const root = runRoot(state);
  verifyCurrentCorpus(io, state);
  const auditor = state.resolvedRoster.auditor;
  const directory = copyCorpusForSeat(io, state, auditor.id, AUDITOR_DIR);
  const cycle = revision ? 2 : 1;
  if (state.auditAttempts.some((attemptRecord) => attemptRecord.cycle === cycle && attemptRecord.status === "running")) runnerFail("UNRESOLVED_RUNNING_AUDIT_ATTEMPT", { cycle });
  const attempts = state.auditAttempts.filter((attempt) => attempt.cycle === cycle).length;
  if (attempts >= AGENT_COUNCIL_LIMITS.auditAttemptsPerCycle) runnerFail("AUDIT_ATTEMPT_LIMIT", { cycle });
  const attempt = attempts + 1;
  const nonce = state.nonces.audit[String(cycle)];
  const auditInputDigest = auditInputSha256(bundle, revision, nonce, cycle);
  const previousAttempt = attempts > 0
    ? state.auditAttempts.filter((record) => record.cycle === cycle).at(-1)
    : null;
  const previousFailureCode = String(previousAttempt?.failureCode ?? "").toLowerCase();
  const previousWroteNoRecord = previousAttempt?.status === "invalid_response"
    && MISSING_AUDIT_RECORD_CODES.includes(previousFailureCode);
  // `AUDIT_RESPONSE_SIZE_LIMIT` lands as `invalid_response`, but it is the same
  // too-much-output failure the seat's size limit is, so it leaves the schema
  // block out and takes the compact-record prompt below.
  const previousOverflowed = previousAttemptOverflowed(previousAttempt);
  const previousInputDrifted = AUDIT_INPUT_DRIFT_CODES.includes(previousFailureCode);
  // A schema correction is only meaningful when a record existed and was wrong.
  const correction = previousAttempt?.status === "invalid_response" && !previousWroteNoRecord && !previousOverflowed && !previousInputDrifted
    ? { failureCode: previousAttempt.failureCode ?? "INVALID_RESPONSE" }
    : null;
  const built = auditPrompt(state, bundle, nonce, revision, correction);
  const basePrompt = built.text;
  const prompt = previousOverflowed
    ? truncationRetryPrompt(basePrompt)
    : previousWroteNoRecord
      ? `${MISSING_AUDIT_RECORD_CORRECTION}\n\n${basePrompt}`
      : basePrompt;
  const responseFile = writePrompt(io, directory, prompt, built.context);
  const title = `${state.runId}:${auditor.id}:audit-c${cycle}:a${attempt}`;
  // Same declaration seam the seat path uses, read from the same adapter table:
  // an `auditCapable` auditor rides a `writesResponseFile` door and writes its
  // own record, and the offline fake adapter declares the identical contract
  // explicitly.
  const auditWritesResponseFile = adapterContract(auditor.qualification.adapter.name)?.writesResponseFile === true
    || io.invokeSeatWritesResponseFile === true;
  state.auditAttempts.push({ cycle, attempt, status: "running", startedAt: io.now(), auditInputSha256: auditInputDigest });
  state.updatedAt = io.now();
  state = writeRun(io, state);
  let attemptRecord = state.auditAttempts.find((candidate) => candidate.cycle === cycle && candidate.attempt === attempt);
  let result;
  try {
    result = await io.invokeSeat({
      cwd: directory,
      model: auditor.model,
      variant: auditor.variant,
      adapterName: auditor.qualification.adapter.name,
      seatId: auditor.id,
      runtimeRoot: runRoot(state),
      responseSchema: {},
      title,
      environment: seatEnvironmentFor(io, state, auditor),
      timeoutMs: AGENT_COUNCIL_LIMITS.auditTimeoutMs,
      maxOutputBytes: AGENT_COUNCIL_LIMITS.rawModelOutputBytes,
      runId: state.runId,
      ...invocationLifecycle(io, state),
    });
  } catch (error) {
    persistProcessOwnership(state, error?.agentCouncilProcessOwnership);
    attemptRecord.status = "transport_failed";
    attemptRecord.completedAt = io.now();
    attemptRecord.failureCode = `INVOKE_${safeFailureToken(error?.code ?? error?.name ?? "UNEXPECTED_FAILURE")}`;
    state.updatedAt = io.now();
    writeRun(io, state);
    throw error;
  }
  const transport = classifyTransportResult(result);
  state = writeRun(io, state);
  attemptRecord = state.auditAttempts.find((candidate) => candidate.cycle === cycle && candidate.attempt === attempt);
  attemptRecord.completedAt = io.now();
  if (!transport.ok) {
    attemptRecord.status = transport.status;
    attemptRecord.failureCode = transport.failureCode;
    if (["PROCESS_TREE_UNVERIFIED", "PROCESS_IDENTITY_UNVERIFIED"].includes(transport.failureCode)) persistProcessOwnership(state, result.processOwnership);
    return { state: writeRun(io, state), parsed: null };
  }
  // The auditor rides the same file-writing pi door as a seat, so its stdout is
  // a --mode json stream that names why the model stopped. Truncation detection
  // is therefore symmetric with executeExternalAttempt: a length stop with no
  // usable record is TRUNCATED, not an unexplained missing file.
  const stream = auditWritesResponseFile ? parsePiJsonStream(result.stdout) : null;
  const truncatedStop = stream?.stopReason === "length";
  const stopReason = ledgerStopReason(stream?.stopReason);
  if (stopReason) attemptRecord.stopReason = stopReason;
  if (!io.exists(responseFile)) {
    attemptRecord.status = truncatedStop ? "truncated" : "invalid_response";
    attemptRecord.failureCode = truncatedStop
      ? "TRUNCATED"
      : stream && !stream.sawAssistantMessage ? "PI_NO_ASSISTANT_TURN" : "MISSING_STRUCTURED_RESPONSE";
    return { state: writeRun(io, state), parsed: null };
  }
  let bytes;
  try {
    bytes = io.readFile(responseFile);
  } catch (error) {
    attemptRecord.status = "transport_failed";
    attemptRecord.failureCode = "UNEXPECTED_AUDIT_IO_FAILURE";
    writeRun(io, state);
    throw error;
  }
  if (bytes.length > AGENT_COUNCIL_LIMITS.seatResponseBytes) {
    attemptRecord.status = "invalid_response";
    attemptRecord.failureCode = "AUDIT_RESPONSE_SIZE_LIMIT";
    return { state: writeRun(io, state), parsed: null };
  }
  try {
    const universes = auditReferenceUniverses(bundle);
    const parsed = io.validateAuditResponse({ expectedRunId: state.runId, expectedNonce: nonce, expectedSeatId: auditor.id, expectedClaimIds: universes.claimIds, expectedEvidenceRefs: universes.evidenceRefs, value: parseJsonBytes(bytes, "audit-response") });
    attemptRecord.status = "completed";
    return { state: writeRun(io, state), parsed };
  } catch (error) {
    if (!(error instanceof AgentCouncilValidationError) && !(error instanceof AgentCouncilRunnerError && error.code === "INVALID_JSON_FILE")) {
      attemptRecord.status = "transport_failed";
      attemptRecord.failureCode = "UNEXPECTED_AUDIT_VALIDATION_FAILURE";
      writeRun(io, state);
      throw error;
    }
    if (error instanceof AgentCouncilRunnerError && error.code === "INVALID_JSON_FILE" && truncatedStop) {
      // Half a record plus an explicit length stop is the same failure as no
      // record. A schema rejection is not: that record was complete and wrong.
      attemptRecord.status = "truncated";
      attemptRecord.failureCode = "TRUNCATED";
      return { state: writeRun(io, state), parsed: null };
    }
    attemptRecord.status = "invalid_response";
    attemptRecord.failureCode = error.code;
    return { state: writeRun(io, state), parsed: null };
  }
}

function ensureAuditReady(state) {
  if (!state.rounds.find((round) => round.number === 2 && round.status === "complete")) runnerFail("ROUND2_INCOMPLETE");
  if (state.round3?.required && !state.rounds.find((round) => round.number === 3 && round.status === "complete")) runnerFail("REQUIRED_ROUND3_INCOMPLETE");
  if (!["R2_FALSIFICATION_COMPLETE", "R3_CROSS_EXAM_COMPLETE", "AUDIT_NEEDS_REVISION"].includes(state.milestone)) runnerFail("AUDIT_NOT_AVAILABLE", { milestone: state.milestone });
}

function durablePayloadDigest(io, directory) {
  const files = io.walkFiles(directory)
    .filter((relative) => normalizeRelativePosixPath(relative) !== "run-state.json")
    .map((relative) => ({ path: normalizeRelativePosixPath(relative), sha256: sha256Bytes(io.readFile(path.join(directory, relative))) }));
  return canonicalSha256(files);
}

function verifyDurablePayload(io, state) {
  if (!state.durability || !io.exists(state.durability.destination)) runnerFail("DURABLE_PAYLOAD_MISSING");
  if (durablePayloadDigest(io, state.durability.destination) !== state.durability.sha256) runnerFail("DURABLE_PAYLOAD_DRIFT");
}

function durableMarker(state) {
  return { schemaVersion: 1, marker: "agent-council-durable", runId: state.runId, manifestSha256: state.disclosureManifest.manifestSha256 };
}

function ownsDurableDirectory(io, directory, expected) {
  const markerFile = path.join(directory, "durable-marker.json");
  if (!io.exists(markerFile)) return false;
  try {
    const actual = JSON.parse(io.readFile(markerFile).toString("utf8"));
    return canonicalSha256(actual) === canonicalSha256(expected);
  } catch {
    return false;
  }
}

function copyDurablePayload(io, state, recordFile, destinationParent) {
  const root = runRoot(state);
  const destination = path.join(path.resolve(destinationParent), state.runId);
  const staging = path.join(path.resolve(destinationParent), `.${state.runId}.tmp`);
  for (const candidate of [destination, staging]) {
    if (pathInside(root, candidate) || pathInside(candidate, root)) runnerFail("DURABLE_RUN_OVERLAP", { candidate });
  }
  const marker = durableMarker(state);
  if (io.exists(staging)) {
    if (!ownsDurableDirectory(io, staging, marker)) runnerFail("DURABLE_STAGING_NOT_OWNED");
    io.removeTree(staging);
  }
  io.mkdir(staging);
  try {
    stableWriteJson(io, path.join(staging, "durable-marker.json"), marker);
  } catch (error) {
    try {
      io.removeTree(staging);
    } catch (cleanupError) {
      throw new AgentCouncilRunnerError("DURABLE_MARKER_CLEANUP_FAILURE", {
        primaryCode: error?.code ?? error?.name ?? "UNKNOWN_MARKER_FAILURE",
        cleanupCode: cleanupError?.code ?? cleanupError?.name ?? "UNKNOWN_CLEANUP_FAILURE",
      });
    }
    throw error;
  }
  io.copyTree(path.join(root, POSITIONS_DIR), path.join(staging, POSITIONS_DIR));
  io.writeFile(path.join(staging, "final-record.md"), io.readFile(recordFile));
  stableWriteJson(io, path.join(staging, "disclosure-manifest.json"), state.disclosureManifest);
  stableWriteJson(io, path.join(staging, "resolved-roster.json"), state.resolvedRoster);
  stableWriteJson(io, path.join(staging, "rounds.json"), state.rounds);
  stableWriteJson(io, path.join(staging, "attempts.json"), state.attempts);
  stableWriteJson(io, path.join(staging, "probe-receipts.json"), state.probeReceipts);
  stableWriteJson(io, path.join(staging, "seat-diffs.json"), state.seatDiffs);
  stableWriteJson(io, path.join(staging, "round3.json"), state.round3);
  stableWriteJson(io, path.join(staging, "audit-attempts.json"), state.auditAttempts);
  stableWriteJson(io, path.join(staging, "audit-history.json"), state.auditHistory);
  stableWriteJson(io, path.join(staging, "audit.json"), state.audit);
  if (state.auditRevision) stableWriteJson(io, path.join(staging, "audit-revision.json"), state.auditRevision);
  io.writeFile(path.join(staging, "synthesis.md"), state.synthesis);
  const sha256 = durablePayloadDigest(io, staging);
  if (io.exists(destination)) {
    if (!ownsDurableDirectory(io, destination, marker) || durablePayloadDigest(io, destination) !== sha256) runnerFail("DURABLE_DESTINATION_CONFLICT");
    io.removeTree(staging);
    return { destination, sha256 };
  }
  io.rename(staging, destination);
  if (durablePayloadDigest(io, destination) !== sha256) runnerFail("DURABLE_COPY_VERIFICATION_FAILED");
  return { destination, sha256 };
}

async function cleanupOwnedProcesses(io, state) {
  if (!state.processes.length) return "not_required";
  while (state.processes.length) {
    const expected = state.processes[0];
    const observation = await io.terminateProcessTree(expected);
    if (assessTerminationProof(expected, observation).kind !== "terminated") runnerFail("PROCESS_TREE_SURVIVORS");
    state.processes.shift();
    const previousUpdatedAt = state.updatedAt;
    state.updatedAt = io.now();
    try {
      writeRun(io, state);
    } catch (error) {
      state.processes.unshift(expected);
      state.updatedAt = previousUpdatedAt;
      throw error;
    }
    removeProcessRecoveryRecord(io, state, expected);
  }
  return "complete";
}

async function finalizeCleanup(io, state) {
  const root = runRoot(state);
  if (state.milestone === "DURABLE") {
    state.cleanup = { status: "in_progress", checkpoints: { processes: "pending", filesystem: "pending" }, manifestSha256: state.disclosureManifest.manifestSha256 };
    state.milestone = nextMilestone(state.milestone, "START_CLEANUP");
    state = writeRun(io, state);
  }
  if (state.milestone !== "CLEANING") runnerFail("CLEANUP_RESUME_MILESTONE_MISMATCH", { milestone: state.milestone });
  const runCheckpoint = async (name, operation, persistSuccess = true) => {
    if (["complete", "not_required"].includes(state.cleanup.checkpoints[name])) return;
    state.cleanup.checkpoints[name] = "pending";
    state = writeRun(io, state);
    try {
      state.cleanup.checkpoints[name] = await operation();
      if (persistSuccess) state = writeRun(io, state);
    } catch (error) {
      state.cleanup.checkpoints[name] = "failed";
      state.cleanup.status = "in_progress";
      state = writeRun(io, state);
      throw error;
    }
  };
  await runCheckpoint("processes", async () => cleanupOwnedProcesses(io, state));
  await runCheckpoint("filesystem", async () => {
    for (const name of [SEATS_DIR, AUDITOR_DIR, CORPUS_DIR, RAW_DIR, NATIVE_RUNTIME_DIR, "probes"]) {
      const target = path.join(root, name);
      if (io.exists(target)) io.removeTree(target);
    }
    return "complete";
  }, false);
  verifyDurablePayload(io, state);
  state.cleanup.status = "complete";
  state.milestone = nextMilestone(state.milestone, "COMPLETE_CLEANUP");
  state.updatedAt = io.now();
  state = writeRun(io, state);
  stableWriteJson(io, path.join(state.durability.destination, "run-state.json"), state);
  verifyDurablePayload(io, state);
  return state;
}

function currentRoundRecord(state, number) {
  return state.rounds.find((round) => round.number === number);
}

function prepareCommand(io, args) {
  rejectV1Cli(args);
  const repo = io.resolveRepositoryRoot(cliValue(args, "repo", { required: true }));
  const hostId = cliValue(args, "host-id", { required: true });
  const brief = readRequiredText(io, cliValue(args, "brief", { required: true }), "decision-brief", AGENT_COUNCIL_LIMITS.seatResponseBytes);
  const rosterFile = path.resolve(cliValue(args, "roster") || DEFAULT_ROSTER_FILE);
  const pool = parseJsonBytes(io.readFile(rosterFile), "roster");
  if (pool.version === 1 || pool.schemaVersion === 1 || pool.schemaVersion === undefined) runnerFail("V1_ROSTER_RESTART_REQUIRED");
  const runId = io.newRunId();
  const runDirectory = path.resolve(cliValue(args, "run-dir") || path.join(io.tempRoot, runId));
  if (!exactTempChild(runDirectory, io.tempRoot) || io.exists(runDirectory)) runnerFail("UNSAFE_RUN_DIRECTORY");
  try {
  io.mkdir(runDirectory);
  for (const name of [CORPUS_DIR, SEATS_DIR, RAW_DIR, POSITIONS_DIR]) io.mkdir(path.join(runDirectory, name));
  const preflight = io.preflightTransports(piChildEnvironment(io.hostEnvironment));
  // The pi door carries every OpenRouter seat, so a missing or off-pin pi is a
  // hard stop here even when the transport table came from an injected adapter.
  const pi = preflight.transports.find((transport) => transport.adapterName === "pi-headless");
  if (!pi || pi.version !== adapterContract("pi-headless").version) runnerFail("PI_VERSION_MISMATCH", { version: pi?.version ?? "missing" });
  const resolvedRoster = validateRoster({
    pool,
    hostId,
    profile: cliValue(args, "profile") ?? "full",
    selectedExternalIds: cliValues(args, "seat"),
    preferredExternalIds: cliValues(args, "prefer-seat"),
    excludedExternalIds: cliValues(args, "exclude-seat"),
    transportPolicy: cliValue(args, "transport-policy") ?? "subscription-first",
    auditorId: cliValue(args, "auditor"),
    availableModelIds: preflight.models,
    now: io.now(),
  });
  // Belt and braces over the roster validator rejection, off the same table:
  // the audit path reads the auditor response file directly, so a resolved
  // auditor whose adapter is not declared `auditCapable` must never reach a
  // seat directory.
  if (adapterContract(resolvedRoster.auditor.qualification.adapter.name)?.auditCapable !== true) {
    runnerFail("AUDITOR_TRANSPORT_UNSUPPORTED", { adapterName: resolvedRoster.auditor.qualification.adapter.name });
  }
  const approvedBinaries = new Set(cliValues(args, "approve-binary").map(normalizeRelativePosixPath));
  const userExclusions = new Set(cliValues(args, "exclude").map(normalizeRelativePosixPath));
  const approvedDiffPaths = cliValues(args, "approve-history-diff").map(normalizeRelativePosixPath);
  if (approvedDiffPaths.length > AGENT_COUNCIL_LIMITS.historicalDiffPaths) runnerFail("HISTORICAL_DIFF_PATH_LIMIT");
  const historyIo = io.readHistory(repo, approvedDiffPaths);
  validateHistoryEvidence(historyIo);
  const history = {
    headSha: io.repositoryHead(repo),
    dirty: io.repositoryDirty(repo),
    commits: historyIo.commits,
    paths: historyIo.paths,
    approvedDiffs: historyIo.approvedDiffs.map(({ logicalPath, bytes, sha256 }) => ({ logicalPath, bytes, sha256 })),
  };
  const corpusDirectory = path.join(runDirectory, CORPUS_DIR);
  const corpus = copySanitizedCorpus(io, repo, corpusDirectory, { approvedBinaries, userExclusions });
  materializeHistoryPacket(io, corpus, corpusDirectory, history, historyIo);
  const provisionalCorpusSha = canonicalSha256(corpus.included);
  const probeDeclarations = cliValues(args, "probe").map((gateId, index) => ({ id: `probe-${index + 1}-${gateId}`, gateId }));
  const probeSpecs = resolveProbeSpecs(io, probeDeclarations, provisionalCorpusSha);
  const boundCorpusSha = canonicalSha256({ files: corpus.included, probeSpecs });
  const manifest = validateDisclosureManifest({
    schemaVersion: 2,
    runId,
    brief: { sha256: sha256Bytes(brief.bytes), bytes: brief.bytes.length },
    included: corpus.included,
    excluded: corpus.excluded,
    history,
    rosterSha256: canonicalSha256(resolvedRoster),
    adapter: { name: "mixed-seat-transports", version: "pi-headless-v1" },
    probeDeclarations,
    limits: AGENT_COUNCIL_LIMITS,
    corpusSha256: boundCorpusSha,
  });
  const runFile = path.join(runDirectory, RUN_FILE);
  const seatDirectories = Object.fromEntries(resolvedRoster.externalDecisionSeats.map((seat) => [seat.id, path.join(runDirectory, SEATS_DIR, seat.id)]));
  const roundNonces = {};
  for (const round of [1, 2, 3]) {
    roundNonces[String(round)] = {};
    for (const seat of resolvedRoster.decisionSeats) roundNonces[String(round)][seat.id] = io.newNonce(`${seat.id}-r${round}`);
  }
  const preparedAt = io.now();
  const initialState = {
    schemaVersion: AGENT_COUNCIL_SCHEMA_VERSION,
    marker: "agent-council",
    runId,
    runFile,
    milestone: "PREPARED",
    createdAt: preparedAt,
    updatedAt: preparedAt,
    repository: { root: repo, headSha: history.headSha, dirty: history.dirty },
    brief: { path: brief.resolved, text: brief.text, sha256: sha256Bytes(brief.bytes), bytes: brief.bytes.length },
    disclosureManifest: manifest,
    resolvedRoster,
    probeSpecs,
    probeReceipts: [],
    probesExecuted: false,
    credentialKey: "OPENROUTER_API_KEY",
    seatDirectories,
    nonces: { rounds: roundNonces, audit: { "1": io.newNonce("audit-cycle-1"), "2": io.newNonce("audit-cycle-2") }, auditRevision: io.newNonce("audit-revision") },
    authorization: null,
    rounds: [],
    attempts: [],
    processes: [],
    seatDiffs: [],
    round3: null,
    disagreementAnnotations: [],
    auditAttempts: [],
    audit: null,
    auditHistory: [],
    auditRevision: null,
    synthesis: null,
    durability: null,
    cleanup: null,
    restart: null,
    abort: null,
  };
  for (const seat of resolvedRoster.externalDecisionSeats) copyCorpusForSeat(io, initialState, seat.id);
  const state = writeRun(io, initialState);
  return {
    status: "prepared",
    runFile,
    runId,
    manifestSha256: manifest.manifestSha256,
    host: resolvedRoster.host.id,
    panelSpec: resolvedRoster.panelSpec,
    externalSeats: resolvedRoster.externalDecisionSeats.map((seat) => seat.id),
    auditor: resolvedRoster.auditor.id,
    seatTransports: resolvedRoster.externalDecisionSeats.map((seat) => ({
      seatId: seat.id,
      adapterName: seat.qualification.adapter.name,
      model: seat.model,
    })),
    auditorTransport: {
      seatId: resolvedRoster.auditor.id,
      adapterName: resolvedRoster.auditor.qualification.adapter.name,
      model: resolvedRoster.auditor.model,
    },
    transports: preflight.transports.map((transport) => ({
      adapterName: transport.adapterName,
      version: transport.version,
      modelCount: Array.isArray(transport.models) ? transport.models.length : 0,
    })),
    unavailableTransports: preflight.unavailable,
    chairRound1Nonce: state.nonces.rounds["1"][resolvedRoster.host.id],
  };
  } catch (primaryError) {
    if (exactTempChild(runDirectory, io.tempRoot) && io.exists(runDirectory)) {
      try {
        io.removeTree(runDirectory);
      } catch (cleanupError) {
        throw new AgentCouncilRunnerError("PREPARE_FAILURE_CLEANUP_FAILURE", {
          primaryCode: primaryError?.code ?? primaryError?.name ?? "UNKNOWN_PRIMARY_FAILURE",
          cleanupCode: cleanupError?.code ?? cleanupError?.name ?? "UNKNOWN_CLEANUP_FAILURE",
        });
      }
    }
    throw primaryError;
  }
}

async function authorizeIfNeeded(io, state, args) {
  const pendingAuthorizedProbes = state.milestone === "AUTHORIZED" && !state.probesExecuted && state.probeSpecs.length > 0;
  const approval = cliValue(args, "approve-manifest-sha", { required: state.milestone === "PREPARED" || pendingAuthorizedProbes });
  if (state.milestone === "PREPARED") {
    verifyCurrentCorpus(io, state);
    if (approval !== state.disclosureManifest.manifestSha256) runnerFail("MANIFEST_APPROVAL_MISMATCH");
    state.authorization = { manifestSha256: approval, approvedAt: io.now() };
    state.milestone = nextMilestone(state.milestone, "AUTHORIZE");
    state.updatedAt = io.now();
    state = writeRun(io, state);
  } else if (approval !== undefined && approval !== state.disclosureManifest.manifestSha256) {
    runnerFail("MANIFEST_APPROVAL_MISMATCH");
  }
  if (state.milestone === "AUTHORIZED" && !state.probesExecuted) {
    if (state.probeSpecs.length > 0 && approval !== state.disclosureManifest.manifestSha256) runnerFail("MANIFEST_REAPPROVAL_REQUIRED");
    state = await executeProbes(io, state);
  }
  return state;
}

async function requireExternalNetwork(io) {
  let observation;
  try {
    observation = await io.checkExternalNetwork();
  } catch (error) {
    observation = { reachable: false, failureCode: safeFailureToken(error?.code ?? error?.name ?? "CHECK_FAILED") };
  }
  const positive = observation?.reachable === true
    && Number.isInteger(observation.statusCode)
    && observation.statusCode >= 100
    && observation.statusCode <= 599;
  if (!positive) {
    runnerFail("EXTERNAL_NETWORK_PREFLIGHT_FAILED", {
      endpointId: "openrouter-model-catalog",
      failureCode: safeFailureToken(observation?.reachable === true ? "OBSERVATION_INVALID" : observation?.failureCode ?? "UNREACHABLE"),
    });
  }
}

async function roundOneCommand(io, args) {
  rejectV1Cli(args);
  let state = readRun(io, cliValue(args, "run", { required: true }));
  state = await authorizeIfNeeded(io, state, args);
  if (state.milestone !== "AUTHORIZED" || currentRoundRecord(state, 1)?.status === "complete") runnerFail("ROUND1_NOT_AVAILABLE");
  const chair = readChair(io, state, cliValue(args, "chair", { required: true }), 1);
  await requireExternalNetwork(io);
  io.preflightSelectedNativeModels(state.resolvedRoster);
  state = await executeOpenedRound(io, state, 1, chair);
  return { status: currentRoundRecord(state, 1).status, milestone: state.milestone, round: 1 };
}

async function laterRoundCommand(io, args) {
  rejectV1Cli(args);
  let state = readRun(io, cliValue(args, "run", { required: true }));
  state = await authorizeIfNeeded(io, state, args);
  const round = Number(cliValue(args, "number", { required: true }));
  if (![2, 3].includes(round)) runnerFail("INVALID_ROUND_NUMBER");
  const prior = currentRoundRecord(state, round - 1);
  if (!prior || prior.status !== "complete") runnerFail("PRIOR_ROUND_INCOMPLETE");
  if (round === 2 && state.milestone !== "R1_COMPLETE") runnerFail("ROUND2_NOT_AVAILABLE");
  if (round === 3 && (state.milestone !== "R2_FALSIFICATION_COMPLETE" || !state.round3?.required)) runnerFail("ROUND3_NOT_REQUIRED");
  const chair = readChair(io, state, cliValue(args, "chair", { required: true }), round);
  await requireExternalNetwork(io);
  state = await executeOpenedRound(io, state, round, chair);
  return { status: currentRoundRecord(state, round).status, milestone: state.milestone, round, round3: state.round3 };
}

async function retryCommand(io, args) {
  rejectV1Cli(args);
  let state = readRun(io, cliValue(args, "run", { required: true }));
  state = await authorizeIfNeeded(io, state, args);
  const round = Number(cliValue(args, "round", { required: true }));
  const seatId = cliValue(args, "seat", { required: true });
  const record = currentRoundRecord(state, round);
  const seat = state.resolvedRoster.externalDecisionSeats.find((candidate) => candidate.id === seatId);
  if (!record || !seat || record.status !== "failed" || record.externals.some((response) => response.seatId === seatId)) runnerFail("SEAT_RETRY_NOT_AVAILABLE");
  const chair = record.chair;
  await requireExternalNetwork(io);
  state = await executeOpenedRound(io, state, round, chair, [seat]);
  return { status: currentRoundRecord(state, round).status, milestone: state.milestone, round, seatId };
}

async function auditCommand(io, args) {
  rejectV1Cli(args);
  let state = readRun(io, cliValue(args, "run", { required: true }));
  state = await authorizeIfNeeded(io, state, args);
  ensureAuditReady(state);
  const latestRound = state.rounds.filter((round) => round.status === "complete").sort((left, right) => right.number - left.number)[0];
  const chair = readChair(io, state, cliValue(args, "chair", { required: true }), latestRound.number);
  let revision = null;
  let synthesis;
  if (state.milestone === "AUDIT_NEEDS_REVISION") {
    const revisionFile = cliValue(args, "revision", { required: true });
    const evidenceIds = [
      ...state.probeReceipts.map((receipt) => `receipt:${receipt.payload.id}`),
      ...state.disclosureManifest.included.map((entry) => `citation:${entry.logicalPath}`),
    ];
    revision = validateAuditRevision({
      expectedRunId: state.runId,
      expectedNonce: state.nonces.auditRevision,
      audit: state.audit,
      value: parseJsonBytes(readRequiredText(io, revisionFile, "audit-revision", AGENT_COUNCIL_LIMITS.seatResponseBytes).bytes, "audit-revision"),
      evidenceIds,
    });
    state.auditRevision = revision;
    synthesis = revision.replacementSynthesis;
  } else {
    synthesis = readRequiredText(io, cliValue(args, "synthesis", { required: true }), "synthesis", AGENT_COUNCIL_LIMITS.seatResponseBytes).text;
  }
  let bundle = auditBundle(state, synthesis, chair);
  const cycle = revision ? 2 : 1;
  const orphanedAttempt = state.auditAttempts.find((attempt) => attempt.cycle === cycle && attempt.status === "completed") ?? null;
  const adopted = adoptCompletedAuditResponse(io, state, bundle, revision);
  if (!adopted && orphanedAttempt) {
    const inputMatches = auditAttemptMatchesInput(orphanedAttempt, bundle, revision, state.nonces.audit[String(cycle)], cycle);
    orphanedAttempt.status = "invalid_response";
    orphanedAttempt.failureCode = inputMatches ? "AUDIT_ADOPTION_RESPONSE_INVALID" : "AUDIT_INPUT_CHANGED";
    state.updatedAt = io.now();
    state = writeRun(io, state);
    bundle = auditBundle(state, synthesis, chair);
  }
  let executed;
  if (adopted) {
    executed = { state, parsed: adopted };
  } else {
    await requireExternalNetwork(io);
    executed = await executeAuditAttempt(io, state, bundle, revision);
    // One automatic retry after a truncated audit attempt, mirroring the seat
    // path: an audit that ran out of output budget produced no verdict at all,
    // and the retry is the whole allowance. The bundle is rebuilt from the
    // written state so the second attempt binds the ledger it actually saw.
    const attemptsInCycle = executed.state.auditAttempts.filter((record) => record.cycle === cycle);
    if (!executed.parsed
      && attemptsInCycle.at(-1)?.status === "truncated"
      && attemptsInCycle.length < AGENT_COUNCIL_LIMITS.auditAttemptsPerCycle) {
      executed = await executeAuditAttempt(io, executed.state, auditBundle(executed.state, synthesis, chair), revision);
    }
  }
  state = executed.state;
  if (!executed.parsed) return { status: "failed", milestone: state.milestone, attempts: state.auditAttempts };
  state.audit = executed.parsed;
  state.auditHistory.push(executed.parsed);
  state.synthesis = synthesis;
  if (revision) {
    state.milestone = nextMilestone(state.milestone, executed.parsed.verdict === "FAITHFUL" ? "REVISION_AUDIT_FAITHFUL" : "REVISION_AUDIT_NEEDS_REVISION");
    if (state.milestone === "RESTART_REQUIRED") state.restart = { reason: "SECOND_ADVERSE_AUDIT", recordedAt: io.now() };
  } else {
    state.milestone = nextMilestone(state.milestone, executed.parsed.verdict === "FAITHFUL" ? "AUDIT_FAITHFUL" : "AUDIT_NEEDS_REVISION");
    if (executed.parsed.findings.some((finding) => finding.remedy === "NEW_EVIDENCE_REQUIRED")) {
      state.milestone = "RESTART_REQUIRED";
      state.restart = { reason: "AUDIT_REQUIRES_NEW_EVIDENCE", recordedAt: io.now() };
    }
  }
  state.updatedAt = io.now();
  state = writeRun(io, state);
  return { status: executed.parsed.verdict, milestone: state.milestone, findings: executed.parsed.findings.length };
}

async function finalizeCommand(io, args) {
  let state = readRun(io, cliValue(args, "run", { required: true }));
  if (["AUDIT_FAITHFUL", "FINALIZED"].includes(state.milestone) && state.processes.length) runnerFail("UNRESOLVED_PROCESS_OWNERSHIP");
  if (state.milestone === "FINALIZED") {
    verifyDurablePayload(io, state);
    stableWriteJson(io, path.join(state.durability.destination, "run-state.json"), state);
    verifyDurablePayload(io, state);
    return { status: "finalized", retained: state.durability.destination, payloadSha256: state.durability.sha256, deletedSourceHeavyArtifacts: true, resumed: true };
  }
  const resumed = ["DURABLE", "CLEANING"].includes(state.milestone);
  if (resumed) {
    verifyDurablePayload(io, state);
  } else {
    if (state.milestone !== "AUDIT_FAITHFUL" || state.audit?.verdict !== "FAITHFUL") runnerFail("FINALIZE_REQUIRES_FAITHFUL_AUDIT");
    verifyCurrentCorpus(io, state);
    const recordFile = path.resolve(cliValue(args, "record", { required: true }));
    readRequiredText(io, recordFile, "final-record", AGENT_COUNCIL_LIMITS.seatResponseBytes);
    const durable = copyDurablePayload(io, state, recordFile, cliValue(args, "destination", { required: true }));
    state.durability = { status: "verified", destination: durable.destination, sha256: durable.sha256, manifestSha256: state.disclosureManifest.manifestSha256 };
    state.milestone = nextMilestone(state.milestone, "VERIFY_DURABILITY");
    state.updatedAt = io.now();
    state = writeRun(io, state);
    stableWriteJson(io, path.join(durable.destination, "run-state.json"), state);
  }
  state = await finalizeCleanup(io, state);
  verifyDurablePayload(io, state);
  return { status: "finalized", retained: state.durability.destination, payloadSha256: state.durability.sha256, deletedSourceHeavyArtifacts: true, resumed };
}

function inspectCommand(io, args) {
  const raw = readRawRun(io, cliValue(args, "run", { required: true }));
  if (raw.v1) return { status: "v1-restart-required", inspectable: true, abortable: true, runId: raw.value.runId ?? null, rounds: raw.value.rounds ?? {}, audit: raw.value.audit ?? null };
  // A stale run cannot be reported as state, because none of it validated. It
  // is refused by name with the offending field, and the operator's next move
  // is `abort --confirm-generated-run`, which still cleans the disposable tree.
  if (raw.stale) runnerFail("STALE_RUN_STATE_RESTART_REQUIRED", { ...staleRunDetails(raw), abortable: true });
  const state = readRun(io, raw.resolved);
  return {
    schemaVersion: state.schemaVersion,
    runId: state.runId,
    milestone: state.milestone,
    manifestSha256: state.disclosureManifest.manifestSha256,
    disclosureManifest: state.disclosureManifest,
    included: state.disclosureManifest.included,
    excluded: state.disclosureManifest.excluded,
    probeDeclarations: state.disclosureManifest.probeDeclarations,
    roster: state.resolvedRoster,
    rounds: state.rounds,
    attempts: state.attempts,
    processes: state.processes,
    probeReceipts: state.probeReceipts,
    // The derived Round-3 trigger. The skill tells the operator to open Round 3
    // only when `inspect` reports `round3.required: true`, so it has to be here.
    // `null` until Round 2 completes.
    round3: state.round3,
    audit: state.audit,
    durability: state.durability,
    cleanup: state.cleanup,
  };
}

function abortTombstoneFile(io, runFile) {
  const identity = io.platform === "win32" ? path.resolve(runFile).toLowerCase() : path.resolve(runFile);
  return path.join(path.resolve(io.tempRoot), `.agent-council-abort-${sha256Bytes(Buffer.from(identity, "utf8")).slice(7)}.json`);
}

function abortTombstoneValue(runFile, raw) {
  // A healthy v2 run always carries a validated manifest digest. A v1 run has
  // none, and a stale run's digest never passed a validator, so bind it only
  // when it is literally the canonical shape the tombstone reader accepts —
  // otherwise the tombstone this abort writes would fail its own reader on the
  // resume path and strand the very run it was meant to wind down.
  const candidate = raw.v1 ? null : raw.value?.disclosureManifest?.manifestSha256;
  return {
    schemaVersion: 1,
    marker: "agent-council-abort",
    runFile: path.resolve(runFile),
    runDirectory: path.dirname(path.resolve(runFile)),
    runId: String(raw.value.runId),
    manifestSha256: typeof candidate === "string" && /^sha256:[0-9a-f]{64}$/.test(candidate) ? candidate : null,
  };
}

function readAbortTombstone(io, tombstoneFile, runFile) {
  const value = parseJsonBytes(io.readFile(tombstoneFile), "abort-tombstone");
  const keys = Object.keys(value).sort().join(",");
  if (keys !== "manifestSha256,marker,runDirectory,runFile,runId,schemaVersion"
    || value.schemaVersion !== 1
    || value.marker !== "agent-council-abort"
    || typeof value.runFile !== "string"
    || typeof value.runDirectory !== "string"
    || path.resolve(value.runFile) !== path.resolve(runFile)
    || path.resolve(value.runDirectory) !== path.dirname(path.resolve(runFile))
    || typeof value.runId !== "string" || !value.runId
    || !(value.manifestSha256 === null || /^sha256:[0-9a-f]{64}$/.test(value.manifestSha256))) {
    runnerFail("INVALID_ABORT_TOMBSTONE");
  }
  return value;
}

async function abortCommand(io, args) {
  if (args["confirm-generated-run"] !== true) runnerFail("ABORT_CONFIRMATION_REQUIRED");
  const runFile = path.resolve(cliValue(args, "run", { required: true }));
  const root = path.dirname(runFile);
  if (!exactTempChild(root, io.tempRoot) || path.basename(runFile) !== RUN_FILE) runnerFail("UNSAFE_ABORT_TARGET");
  const tombstoneFile = abortTombstoneFile(io, runFile);
  if (!io.exists(runFile)) {
    if (!io.exists(tombstoneFile)) runnerFail("RUN_FILE_NOT_FOUND");
    const tombstone = readAbortTombstone(io, tombstoneFile, runFile);
    if (io.exists(root)) io.removeTree(root);
    if (io.exists(root)) runnerFail("ABORT_DELETE_UNVERIFIED");
    io.removeFile(tombstoneFile);
    return { status: "aborted", deletedDirectory: root, resumed: true, runId: tombstone.runId };
  }
  const raw = readRawRun(io, runFile);
  const parsedV2 = raw.v1 || raw.stale ? null : raw.parsed ?? parseRunStateV2(raw.value);
  if (parsedV2 && comparableOwnedPath(parsedV2.runFile, io.platform) !== comparableOwnedPath(raw.resolved, io.platform)) {
    runnerFail("RUN_FILE_IDENTITY_MISMATCH");
  }
  const expectedTombstone = abortTombstoneValue(runFile, raw);
  // Unresumable state, one wind-down path. A v1 run and a stale v2 run are both
  // runs this build cannot drive: neither can be validated into a `RunStateV2`,
  // so neither can take the normal abort path's process cleanup or milestone
  // transition. Both get the tombstone-and-delete that removes the disposable
  // tree — seat, auditor, corpus, probe, and raw copies — and both keep the
  // tombstone until root absence is verified, so a partial delete stays
  // resumable. Designed degradation, named in the result: process ownership
  // recorded by a stale run cannot be re-proved from unvalidated state, so
  // `ownedProcessRecords` reports how many PIDs it claimed and the operator
  // confirms those are gone. `null` means the field was not even an array.
  // ceiling: a stale run's owned processes are counted, not terminated, because
  // termination reads run identity and the recovery ledger out of a state that
  // never passed a validator; upgrade: validate the `processes` array alone
  // against the core's process-record rules and run the healthy abort's
  // `cleanupOwnedProcesses` path on exactly those records.
  if (raw.v1 || raw.stale) {
    if (io.exists(tombstoneFile)) {
      if (canonicalSha256(readAbortTombstone(io, tombstoneFile, runFile)) !== canonicalSha256(expectedTombstone)) runnerFail("ABORT_TOMBSTONE_MISMATCH");
    } else stableWriteJson(io, tombstoneFile, expectedTombstone);
    io.removeTree(root);
    if (io.exists(root)) runnerFail("ABORT_DELETE_UNVERIFIED");
    io.removeFile(tombstoneFile);
    if (raw.v1) return { status: "aborted-v1", deletedDirectory: root };
    return {
      status: "aborted-stale",
      deletedDirectory: root,
      reason: "STALE_RUN_STATE_RESTART_REQUIRED",
      staleField: staleRunDetails(raw),
      ownedProcessRecords: Array.isArray(raw.value?.processes) ? raw.value.processes.length : null,
    };
  }
  let state = mergeProcessRecoveryRecords(io, mutableData(parsedV2));
  if (["DURABLE", "CLEANING", "FINALIZED"].includes(state.milestone)) runnerFail("ABORT_NOT_AVAILABLE_AFTER_DURABILITY");
  if (io.exists(tombstoneFile)) {
    if (canonicalSha256(readAbortTombstone(io, tombstoneFile, runFile)) !== canonicalSha256(expectedTombstone)) runnerFail("ABORT_TOMBSTONE_MISMATCH");
  } else stableWriteJson(io, tombstoneFile, expectedTombstone);
  if (state.milestone === "ABORTED") {
    io.removeTree(root);
    if (io.exists(root)) runnerFail("ABORT_DELETE_UNVERIFIED");
    io.removeFile(tombstoneFile);
    return { status: "aborted", deletedDirectory: root, resumed: true };
  }
  await cleanupOwnedProcesses(io, state);
  for (const round of state.rounds) {
    for (const attempt of round.attempts) {
      if (attempt.status !== "running") continue;
      attempt.status = "transport_failed";
      attempt.completedAt = io.now();
      attempt.failureCode = "OPERATOR_ABORTED_ATTEMPT";
    }
    if (round.status === "running") round.status = "failed";
  }
  for (const attempt of state.auditAttempts) {
    if (attempt.status !== "running") continue;
    attempt.status = "transport_failed";
    attempt.completedAt = io.now();
    attempt.failureCode = "OPERATOR_ABORTED_ATTEMPT";
  }
  state.attempts = state.rounds.flatMap((round) => round.attempts);
  state.abort = { recordedAt: io.now(), reason: "OPERATOR_ABORT" };
  state.milestone = nextMilestone(state.milestone, "ABORT");
  state = writeRun(io, state);
  io.removeTree(root);
  if (io.exists(root)) runnerFail("ABORT_DELETE_UNVERIFIED");
  io.removeFile(tombstoneFile);
  return { status: "aborted", deletedDirectory: root };
}

function selfTestCommand(io) {
  const pool = parseJsonBytes(io.readFile(DEFAULT_ROSTER_FILE), "default-roster");
  if (canonicalJson(pool).toLowerCase().includes("fable")) runnerFail("TEMPORARY_SUBSTITUTION_IN_ROSTER");
  const availableModelIds = [...pool.participants, ...pool.auditors].map((profile) => profile.model);
  for (const [profile, contract] of Object.entries(AGENT_COUNCIL_PANEL_PROFILES)) {
    for (const host of pool.hosts) {
      const roster = validateRoster({ pool, hostId: host.id, profile, availableModelIds, now: "2026-09-03T12:00:00.000Z" });
      if (roster.decisionSeats.length !== contract.externalSeatCount + 1 || roster.externalDecisionSeats.length !== contract.externalSeatCount || roster.auditor.role !== "auditor") {
        runnerFail("SELF_TEST_ROSTER_FAILURE");
      }
    }
  }
  let migrationRejected = false;
  try { rejectV1Cli({ "host-family": "openai" }); } catch (error) { migrationRejected = error.code === "V1_HOST_FAMILY_UNSUPPORTED_USE_HOST_ID"; }
  if (!migrationRejected) runnerFail("SELF_TEST_V1_MIGRATION_FAILURE");
  const filtered = filterEnvironment({ PATH: "fixture", OPENROUTER_API_KEY: "fixture-secret", PRODUCT_DATABASE_URL: "must-not-pass" }, { credentialKey: "OPENROUTER_API_KEY" });
  if (filtered.PRODUCT_DATABASE_URL || filtered.OPENROUTER_API_KEY !== "fixture-secret") runnerFail("SELF_TEST_ENVIRONMENT_FAILURE");
  return { status: "PASS", hosts: pool.hosts.length, profiles: Object.keys(AGENT_COUNCIL_PANEL_PROFILES).length, coreMilestones: AGENT_COUNCIL_MILESTONES.length, brokerGates: Object.keys(BROKER_GATE_CATALOG).length };
}

function usageText() {
  return `Agent Council v3 runner

Commands:
  prepare --repo <path> --brief <file> --host-id <qualified-id> [--profile <focused|balanced|full>] [--seat <profile-id>] [--prefer-seat <profile-id>] [--exclude-seat <profile-id>] [--transport-policy <subscription-first>] [--auditor <profile-id>] [--roster <json>] [--exclude <path>] [--approve-binary <path>] [--approve-history-diff <path>] [--probe <logical-gate-id>]
  round1 --run <run.json> --chair <chair-r1.json> --approve-manifest-sha <sha256>
  round --run <run.json> --number <2|3> --chair <chair-rN.json> [--approve-manifest-sha <sha256>]
  retry --run <run.json> --round <1|2|3> --seat <id> [--approve-manifest-sha <sha256>]
  audit --run <run.json> --chair <chair-final.json> --synthesis <file>
  audit --run <run.json> --chair <chair-final.json> --revision <audit-revision.json>
  finalize --run <run.json> [--record <file> --destination <directory>]  # record/destination required only before durability
  inspect --run <run.json>
  abort --run <run.json> --confirm-generated-run
  self-test`;
}

export function createAgentCouncilRunner(ioOverrides = {}) {
  const io = createDefaultIo(ioOverrides);
  return {
    io,
    async execute(argv) {
      const [command, ...tokens] = argv;
      const args = parseCliArgs(tokens);
      switch (command) {
        case "prepare": return prepareCommand(io, args);
        case "round1": return roundOneCommand(io, args);
        case "round": return laterRoundCommand(io, args);
        case "retry": return retryCommand(io, args);
        case "audit": return auditCommand(io, args);
        case "finalize": return finalizeCommand(io, args);
        case "inspect": return inspectCommand(io, args);
        case "abort": return abortCommand(io, args);
        case "self-test": return selfTestCommand(io);
        case "help":
        case "--help":
        case "-h":
        case undefined: return { status: "help", text: usageText() };
        default: runnerFail("UNKNOWN_COMMAND", { command });
      }
    },
  };
}

export async function main(argv = process.argv.slice(2), ioOverrides = {}) {
  const runner = createAgentCouncilRunner(ioOverrides);
  try {
    const result = await runner.execute(argv);
    if (result?.status === "help") process.stdout.write(`${result.text}\n`);
    else process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    if (["failed"].includes(result?.status)) process.exitCode = 2;
    return result;
  } catch (error) {
    const named = error instanceof AgentCouncilValidationError || error instanceof AgentCouncilRunnerError;
    const code = named ? error.code : "UNEXPECTED_RUNNER_FAILURE";
    // A bare code is not actionable: PI_LAUNCHER_NOT_FOUND alone cannot tell an
    // operator whether pi is absent or half-installed, and EXPECTED_BOUNDED_INTEGER
    // alone cannot say which field of a hand-written chair record is wrong, so a
    // validation error also prints the structural path it carries.
    // Details must be runner-built and structural (reason, adapterName, status,
    // bounded secret-scanned child stderr) — that is a rule every `runnerFail`
    // call site honours, not an enforced one: `AgentCouncilValidationError`
    // sanitizes its details in the constructor, while `AgentCouncilRunnerError`
    // stores them verbatim, and a few (`DURABLE_RUN_OVERLAP`) deliberately name
    // the absolute destination path the operator just supplied, because which
    // path overlapped is the whole diagnosis.
    // Never put a credential, prompt, model output, or source byte in either.
    // An unexpected failure is an internal defect, so it prints its own message
    // and stack instead.
    const details = named
      ? (error.details && typeof error.details === "object" && Object.keys(error.details).length ? ` ${JSON.stringify(error.details)}` : "")
      : ` ${error?.message ?? String(error)}`;
    const location = error instanceof AgentCouncilValidationError && typeof error.path === "string" ? ` at ${error.path}` : "";
    process.stderr.write(`Agent Council error: ${code}${details}${location}\n`);
    if (!named && error?.stack) process.stderr.write(`${error.stack}\n`);
    process.exitCode = 1;
    return { status: "error", code };
  }
}

const IS_DIRECT = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (IS_DIRECT) await main();

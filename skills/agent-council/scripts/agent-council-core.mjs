// Agent Council v3 orchestration with v2 response and run-state schema compatibility.
//
// This module deliberately owns decisions, never observations. It may use deterministic
// cryptographic primitives, but it must not read files, environment, clocks, processes, Git,
// pi state, the network, or product data. Callers pass every runtime fact explicitly.

import { createHash } from "node:crypto";

export const AGENT_COUNCIL_SCHEMA_VERSION = 2;
export const AGENT_COUNCIL_RUN_VERSION = 2;
export const AGENT_COUNCIL_ROSTER_VERSION = 2;
export const PROBE_SCHEMA_VERSION = 1;
export const REQUIRED_EXTERNAL_DECISION_SEATS = 5;
export const REQUIRED_DECISION_SEATS = 6;
export const REQUIRED_AUDITORS = 1;
export const AGENT_COUNCIL_PANEL_SPEC_VERSION = 1;
export const AGENT_COUNCIL_PANEL_PROFILES = deepFreeze({
  focused: { externalSeatCount: 2, assuranceLevel: "focused" },
  balanced: { externalSeatCount: 3, assuranceLevel: "balanced" },
  full: { externalSeatCount: 5, assuranceLevel: "full" },
});
export const AGENT_COUNCIL_TRANSPORT_POLICIES = deepFreeze(["subscription-first"]);
// Maximum persisted length of a transport-reported stop reason. One constant so
// the seat validator, the audit validator, and the runner's ledger bound agree
// by construction rather than by three copies of the same literal.
export const STOP_REASON_MAX_CHARS = 32;
/**
 * Every qualified external adapter declares its own facts once, here. The
 * adapter name is a discriminated-union tag, and it used to be re-read as a
 * string literal at every site that needed one of these facts, so adding a
 * transport meant an edit at each. A row declares:
 *
 * - `version` — the exact qualified CLI version; anything else is
 *   `ADAPTER_QUALIFICATION_MISMATCH`. Re-qualification receipts and the bump
 *   procedure live in `references/qualification-receipts.md`.
 * - `writesResponseFile` — the transport writes `.agent-council-response.json`
 *   at the seat root itself, so the runner must not materialize a native
 *   structured envelope into that same file.
 * - `auditCapable` — the transport may hold the auditor seat. The audit path
 *   reads the auditor's response file directly, so only a file-writing door
 *   qualifies; anything else is `AUDITOR_TRANSPORT_UNSUPPORTED`.
 * - `subscriptionTransport` — the door rides the host's own subscription rather
 *   than pay-per-token OpenRouter. This is the fact `subscription-first`
 *   ranking orders on; it is deliberately not derived from `writesResponseFile`,
 *   which is a response-contract fact that only happens to coincide today.
 *
 * Read it through `adapterContract`, never by direct index: the table is a
 * plain object, so a prototype-shaped name must not resolve to an inherited
 * value and be treated as a qualified transport.
 */
export const QUALIFIED_EXTERNAL_ADAPTERS = deepFreeze({
  "claude-cli": { version: "2.1.312", writesResponseFile: false, auditCapable: false, subscriptionTransport: true },
  "grok-cli": { version: "1.0.13", writesResponseFile: false, auditCapable: false, subscriptionTransport: true },
  "pi-headless": { version: "1.4.0", writesResponseFile: true, auditCapable: true, subscriptionTransport: false },
});

/**
 * The declared contract for one adapter name, or `null` when the name is not a
 * qualified adapter. Fails closed: every caller treats `null` as "not qualified
 * for this", so an unknown, non-string, or prototype key can never satisfy a
 * version check, open the auditor seat, skip response-file materialization, or
 * outrank a subscription seat.
 */
export function adapterContract(adapterName) {
  if (typeof adapterName !== "string") return null;
  if (!Object.hasOwn(QUALIFIED_EXTERNAL_ADAPTERS, adapterName)) return null;
  return QUALIFIED_EXTERNAL_ADAPTERS[adapterName];
}

export const AGENT_COUNCIL_LIMITS = deepFreeze({
  attemptsPerSeatPerRound: 2,
  auditAttemptsPerCycle: 2,
  synthesisRevisionCycles: 1,
  seatTimeoutMs: 30 * 60 * 1000,
  auditTimeoutMs: 30 * 60 * 1000,
  probeTimeoutMs: 10 * 60 * 1000,
  maxProbeDeclarations: 8,
  seatResponseBytes: 256 * 1024,
  rawModelOutputBytes: 4 * 1024 * 1024,
  probeOutputBytes: 1024 * 1024,
  disclosedFiles: 25_000,
  normalFileBytes: 2 * 1024 * 1024,
  approvedBinaryBytes: 5 * 1024 * 1024,
  corpusBytes: 256 * 1024 * 1024,
  historyCommits: 50,
  historyPathEntries: 5_000,
  historicalDiffPaths: 10,
  historicalDiffPathBytes: 512 * 1024,
  historicalDiffTotalBytes: 2 * 1024 * 1024,
  qualificationMaxAgeMs: 90 * 24 * 60 * 60 * 1000,
  consequentialConfidence: 0.65,
});

export const PROBE_STATUSES = deepFreeze([
  "PASSED",
  "FAILED",
  "TIMED_OUT",
  "OUTPUT_LIMIT",
  "REJECTED_SECRET",
  "SPAWN_FAILED",
]);

// `truncated` is a failed attempt like every other non-`completed` status: it
// requires a completion instant and a failure code, and it never satisfies a
// round's completeness or `RESPONSE_WITHOUT_COMPLETED_ATTEMPT` rule. It names
// the one failure the runner can retry inside the round (stop reason `length`).
//
// Every member here is reachable: `refused` was removed because no producer
// could emit it. A model that declines to answer writes no record or writes
// prose, which settles as `invalid_response` with its own failure code — the
// union must not claim a ledger state the runner cannot reach.
export const ATTEMPT_STATUSES = deepFreeze([
  "running",
  "completed",
  "transport_failed",
  "timed_out",
  "output_limit",
  "truncated",
  "invalid_response",
]);

export const ROUND_STATUSES = deepFreeze(["pending", "running", "complete", "failed"]);

export const AGENT_COUNCIL_MILESTONES = deepFreeze([
  "PREPARED",
  "AUTHORIZED",
  "R1_COMPLETE",
  "R2_FALSIFICATION_COMPLETE",
  "R3_CROSS_EXAM_COMPLETE",
  "AUDIT_NEEDS_REVISION",
  "AUDIT_FAITHFUL",
  "RESTART_REQUIRED",
  "DURABLE",
  "CLEANING",
  "FINALIZED",
  "ABORTED",
]);

export const RUN_MILESTONES = AGENT_COUNCIL_MILESTONES;
export const RUN_STATUSES = AGENT_COUNCIL_MILESTONES;

export const CONSEQUENTIAL_DISAGREEMENT_CATEGORIES = deepFreeze([
  "security_privacy",
  "irreversible_or_migration",
  "public_interface_or_data",
  "correctness_or_gate",
  "architecture_boundary",
]);

export const DISCLOSURE_DISPOSITIONS = deepFreeze(["copied"]);
export const AUDIT_VERDICTS = deepFreeze(["FAITHFUL", "NEEDS-REVISION"]);
export const AUDIT_REMEDIES = deepFreeze(["SYNTHESIS_REVISION", "NEW_EVIDENCE_REQUIRED"]);

// Topping Out's catalog: only gates that exist wherever the package is installed (the skill's own
// scripts under .claude/skills/) plus the two conventional npm scripts. Repo-specific gates from
// the workspace this skill was built in (an .agents mirror, its own test and readiness scripts)
// are removed, so a council in another repo can't select a probe that can only fail.
export const BROKER_GATE_CATALOG = deepFreeze({
  "node-check-claude-core": {
    kind: "node",
    argv: ["--check", ".claude/skills/agent-council/scripts/agent-council-core.mjs"],
  },
  "node-check-claude-runner": {
    kind: "node",
    argv: ["--check", ".claude/skills/agent-council/scripts/agent-council.mjs"],
  },
  typecheck: { kind: "npm", argv: ["run", "typecheck"] },
  test: { kind: "npm", argv: ["test"] },
});

export const BROKER_GATES = BROKER_GATE_CATALOG;
export const SCHEMA_VERSIONS = deepFreeze({
  run: AGENT_COUNCIL_SCHEMA_VERSION,
  roster: AGENT_COUNCIL_ROSTER_VERSION,
  response: AGENT_COUNCIL_SCHEMA_VERSION,
  audit: AGENT_COUNCIL_SCHEMA_VERSION,
  probe: PROBE_SCHEMA_VERSION,
});

const DIGEST_PATTERN = /^sha256:[a-f0-9]{64}$/;
const SAFE_ID_PATTERN = /^[a-z0-9][a-z0-9._:-]{0,127}$/;
const WINDOWS_ABSOLUTE_PATTERN = /^[a-zA-Z]:[\\/]/;
const CHOICE_CONFLICT_ID = "derived-choice-conflict";
const DERIVED_DISAGREEMENT_SETS = new WeakSet();

/**
 * A stable protocol failure. Messages contain only the error code and structural path; callers
 * must not put source bytes, secret values, prompts, output, or arbitrary adapter text in details.
 */
export class AgentCouncilValidationError extends Error {
  constructor(code, path, details) {
    const safeCode = typeof code === "string" && /^[A-Z0-9_]+$/.test(code)
      ? code
      : "INVALID_VALIDATION_ERROR";
    const safePath = typeof path === "string" && /^[A-Za-z0-9_.\[\]-]+$/.test(path)
      ? path
      : undefined;
    super(safePath ? `${safeCode} at ${safePath}` : safeCode);
    this.name = "AgentCouncilValidationError";
    this.code = safeCode;
    if (safePath) this.path = safePath;
    if (details !== undefined) this.details = sanitizeErrorDetails(details);
  }
}

function sanitizeErrorDetails(value) {
  if (value === null || typeof value === "boolean") return value;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && /^[A-Za-z0-9_.:/ -]{0,160}$/.test(value)) return value;
  if (Array.isArray(value)) return value.slice(0, 20).map(sanitizeErrorDetails);
  if (isPlainObject(value)) {
    const output = {};
    for (const key of Object.keys(value).sort().slice(0, 20)) {
      if (/^(?:actual|content|credential|expectedValue|message|output|prompt|secret|source|text|token|value)$/i.test(key)) continue;
      output[key] = sanitizeErrorDetails(value[key]);
    }
    return output;
  }
  return "<redacted>";
}

function invalid(code, path, details) {
  throw new AgentCouncilValidationError(code, path, details);
}

function isPlainObject(value) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function object(value, path) {
  if (!isPlainObject(value)) invalid("EXPECTED_OBJECT", path);
  return value;
}

function array(value, path) {
  if (!Array.isArray(value)) invalid("EXPECTED_ARRAY", path);
  return value;
}

function text(value, path, { allowEmpty = false, max = 1_000_000 } = {}) {
  if (typeof value !== "string") invalid("EXPECTED_STRING", path);
  if ((!allowEmpty && value.trim().length === 0) || value.length > max) {
    invalid("INVALID_STRING_LENGTH", path, { max });
  }
  return value;
}

function integer(value, path, { min = Number.MIN_SAFE_INTEGER, max = Number.MAX_SAFE_INTEGER } = {}) {
  if (!Number.isSafeInteger(value) || value < min || value > max) {
    invalid("EXPECTED_BOUNDED_INTEGER", path, { min, max });
  }
  return value;
}

function finiteNumber(value, path, { min = -Infinity, max = Infinity } = {}) {
  if (typeof value !== "number" || !Number.isFinite(value) || value < min || value > max) {
    invalid("EXPECTED_BOUNDED_NUMBER", path, { min, max });
  }
  return value;
}

function bool(value, path) {
  if (typeof value !== "boolean") invalid("EXPECTED_BOOLEAN", path);
  return value;
}

function oneOf(value, allowed, path) {
  if (!allowed.includes(value)) invalid("UNSUPPORTED_ENUM_VALUE", path, { allowed });
  return value;
}

function safeId(value, path) {
  const normalized = normalizeComparableId(text(value, path, { max: 128 }));
  if (!SAFE_ID_PATTERN.test(normalized)) invalid("INVALID_IDENTIFIER", path);
  return normalized;
}

function digest(value, path) {
  if (typeof value !== "string" || !DIGEST_PATTERN.test(value)) invalid("INVALID_SHA256", path);
  return value;
}

function isoInstant(value, path) {
  text(value, path, { max: 64 });
  const milliseconds = Date.parse(value);
  if (!Number.isFinite(milliseconds) || new Date(milliseconds).toISOString() !== value) {
    invalid("INVALID_ISO_INSTANT", path);
  }
  return milliseconds;
}

function assertOnlyKeys(value, allowed, path) {
  const extras = Object.keys(value).filter((key) => !allowed.includes(key));
  if (extras.length) invalid("UNKNOWN_FIELD", path, { fields: extras.sort() });
}

function assertUnique(values, path, code = "DUPLICATE_VALUE") {
  const seen = new Set();
  for (const value of values) {
    if (seen.has(value)) invalid(code, path);
    seen.add(value);
  }
}

function canonicalize(value, path = "$", stack = new Set()) {
  if (value === null || typeof value === "string" || typeof value === "boolean") return value;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) invalid("NON_FINITE_CANONICAL_NUMBER", path);
    return Object.is(value, -0) ? 0 : value;
  }
  if (typeof value === "undefined" || typeof value === "bigint" || typeof value === "function" || typeof value === "symbol") {
    invalid("UNSUPPORTED_CANONICAL_VALUE", path);
  }
  if (stack.has(value)) invalid("CYCLIC_CANONICAL_VALUE", path);
  stack.add(value);
  let result;
  if (Array.isArray(value)) {
    result = value.map((entry, index) => canonicalize(entry, `${path}[${index}]`, stack));
  } else {
    object(value, path);
    const normalizedKeys = Object.keys(value).map((key) => [key, key.normalize("NFC")]);
    assertUnique(normalizedKeys.map(([, normalized]) => normalized), path, "CANONICAL_KEY_COLLISION");
    normalizedKeys.sort((left, right) => left[1].localeCompare(right[1], "en"));
    result = {};
    for (const [original, normalized] of normalizedKeys) {
      result[normalized] = canonicalize(value[original], `${path}.${normalized}`, stack);
    }
  }
  stack.delete(value);
  return result;
}

export function canonicalJson(value) {
  return JSON.stringify(canonicalize(value));
}

export function canonicalSha256(value) {
  return `sha256:${createHash("sha256").update(canonicalJson(value), "utf8").digest("hex")}`;
}

export function normalizeComparableId(value) {
  if (typeof value !== "string") invalid("EXPECTED_STRING", "comparableId");
  return value.normalize("NFC").trim().toLowerCase();
}

export function normalizeRelativePosixPath(value) {
  text(value, "path", { max: 4_096 });
  if (value.includes("\0")) invalid("PATH_CONTAINS_NUL", "path");
  let normalized = value.normalize("NFC").replaceAll("\\", "/");
  if (normalized.startsWith("/") || normalized.startsWith("//") || WINDOWS_ABSOLUTE_PATTERN.test(value)) {
    invalid("ABSOLUTE_PATH", "path");
  }
  while (normalized.startsWith("./")) normalized = normalized.slice(2);
  const parts = normalized.split("/");
  if (!parts.length || parts.some((part) => !part || part === "." || part === "..")) {
    invalid("INVALID_RELATIVE_PATH", "path");
  }
  if (parts.some((part) => part.includes(":"))) invalid("ALTERNATE_DATA_STREAM_PATH", "path");
  return parts.join("/");
}

function deepFreeze(value, seen = new Set()) {
  if (value === null || typeof value !== "object" || seen.has(value)) return value;
  seen.add(value);
  for (const child of Object.values(value)) deepFreeze(child, seen);
  return Object.freeze(value);
}

function dataCopy(value) {
  return JSON.parse(canonicalJson(value));
}

function validateDigestRecord(value, path) {
  const record = object(value, path);
  assertOnlyKeys(record, ["sha256", "bytes"], path);
  return { sha256: digest(record.sha256, `${path}.sha256`), bytes: integer(record.bytes, `${path}.bytes`, { min: 0 }) };
}

function validateIncludedDisclosureEntry(value, path) {
  const entry = object(value, path);
  assertOnlyKeys(entry, ["logicalPath", "physicalPath", "disposition", "bytes", "sha256", "binaryApproved"], path);
  const logicalPath = normalizeRelativePosixPath(entry.logicalPath);
  const physicalPath = normalizeRelativePosixPath(entry.physicalPath);
  const disposition = oneOf(entry.disposition, DISCLOSURE_DISPOSITIONS, `${path}.disposition`);
  const bytes = integer(entry.bytes, `${path}.bytes`, { min: 0, max: AGENT_COUNCIL_LIMITS.approvedBinaryBytes });
  const binaryApproved = bool(entry.binaryApproved, `${path}.binaryApproved`);
  if (!binaryApproved && bytes > AGENT_COUNCIL_LIMITS.normalFileBytes) invalid("NORMAL_FILE_SIZE_LIMIT", `${path}.bytes`);
  if (logicalPath !== physicalPath) invalid("COPIED_PATH_MISMATCH", `${path}.physicalPath`);
  return { logicalPath, physicalPath, disposition, bytes, sha256: digest(entry.sha256, `${path}.sha256`), binaryApproved };
}

function validateExcludedDisclosureEntry(value, path) {
  const entry = object(value, path);
  assertOnlyKeys(entry, ["logicalPath", "reason"], path);
  const reason = safeId(entry.reason, `${path}.reason`);
  if (/secret|token|credential|content|match/i.test(reason) && reason.includes(":")) {
    invalid("SECRET_BEARING_EXCLUSION_REASON", `${path}.reason`);
  }
  return { logicalPath: normalizeRelativePosixPath(entry.logicalPath), reason };
}

function validateHistoryManifest(value, path) {
  const history = object(value, path);
  assertOnlyKeys(history, ["headSha", "dirty", "commits", "paths", "approvedDiffs", "sha256"], path);
  const commits = array(history.commits, `${path}.commits`).map((entry, index) => {
    const row = object(entry, `${path}.commits[${index}]`);
    assertOnlyKeys(row, ["sha", "parents", "authorTimestamp", "subject"], `${path}.commits[${index}]`);
    return {
      sha: text(row.sha, `${path}.commits[${index}].sha`, { max: 64 }),
      parents: array(row.parents, `${path}.commits[${index}].parents`).map((parent, parentIndex) => text(parent, `${path}.commits[${index}].parents[${parentIndex}]`, { max: 64 })),
      authorTimestamp: text(row.authorTimestamp, `${path}.commits[${index}].authorTimestamp`, { max: 64 }),
      subject: text(row.subject, `${path}.commits[${index}].subject`, { allowEmpty: true, max: 512 }),
    };
  });
  if (commits.length > AGENT_COUNCIL_LIMITS.historyCommits) invalid("HISTORY_COMMIT_LIMIT", `${path}.commits`);
  const paths = array(history.paths, `${path}.paths`).map(normalizeRelativePosixPath);
  if (paths.length > AGENT_COUNCIL_LIMITS.historyPathEntries) invalid("HISTORY_PATH_LIMIT", `${path}.paths`);
  assertUnique(paths.map((entry) => entry.toLowerCase()), `${path}.paths`, "HISTORY_PATH_COLLISION");
  const approvedDiffs = array(history.approvedDiffs, `${path}.approvedDiffs`).map((entry, index) => {
    const row = object(entry, `${path}.approvedDiffs[${index}]`);
    assertOnlyKeys(row, ["logicalPath", "bytes", "sha256"], `${path}.approvedDiffs[${index}]`);
    return {
      logicalPath: normalizeRelativePosixPath(row.logicalPath),
      bytes: integer(row.bytes, `${path}.approvedDiffs[${index}].bytes`, { min: 0, max: AGENT_COUNCIL_LIMITS.historicalDiffPathBytes }),
      sha256: digest(row.sha256, `${path}.approvedDiffs[${index}].sha256`),
    };
  });
  if (approvedDiffs.length > AGENT_COUNCIL_LIMITS.historicalDiffPaths) invalid("HISTORICAL_DIFF_PATH_LIMIT", `${path}.approvedDiffs`);
  if (approvedDiffs.reduce((sum, row) => sum + row.bytes, 0) > AGENT_COUNCIL_LIMITS.historicalDiffTotalBytes) {
    invalid("HISTORICAL_DIFF_TOTAL_LIMIT", `${path}.approvedDiffs`);
  }
  const normalized = {
    headSha: text(history.headSha, `${path}.headSha`, { max: 64 }),
    dirty: bool(history.dirty, `${path}.dirty`),
    commits,
    paths,
    approvedDiffs,
  };
  const calculated = canonicalSha256(normalized);
  if (history.sha256 !== undefined && digest(history.sha256, `${path}.sha256`) !== calculated) invalid("HISTORY_DIGEST_MISMATCH", `${path}.sha256`);
  return { ...normalized, sha256: calculated };
}

/** @typedef {{logicalPath:string,physicalPath:string,disposition:"copied",bytes:number,sha256:string,binaryApproved:boolean}} IncludedDisclosureEntryV2 */
/** @typedef {{logicalPath:string,reason:string}} ExcludedDisclosureEntryV2 */
/** @typedef {{headSha:string,dirty:boolean,commits:object[],paths:string[],approvedDiffs:object[],sha256:string}} HistoryManifestV2 */
/** @typedef {{schemaVersion:2,runId:string,brief:object,included:IncludedDisclosureEntryV2[],excluded:ExcludedDisclosureEntryV2[],history:HistoryManifestV2,rosterSha256:string,adapter:object,probeDeclarations:object[],limits:object,corpusSha256:string,manifestSha256:string}} DisclosureManifestV2 */

export function validateDisclosureManifest(value) {
  const manifest = object(value, "manifest");
  assertOnlyKeys(manifest, [
    "schemaVersion", "runId", "brief", "included", "excluded", "history", "rosterSha256",
    "adapter", "probeDeclarations", "limits", "corpusSha256", "manifestSha256",
  ], "manifest");
  if (manifest.schemaVersion !== AGENT_COUNCIL_SCHEMA_VERSION) invalid("UNSUPPORTED_MANIFEST_VERSION", "manifest.schemaVersion");
  const included = array(manifest.included, "manifest.included").map(validateIncludedDisclosureEntry);
  if (included.length > AGENT_COUNCIL_LIMITS.disclosedFiles) invalid("DISCLOSED_FILE_LIMIT", "manifest.included");
  const excluded = array(manifest.excluded, "manifest.excluded").map(validateExcludedDisclosureEntry);
  const logical = included.map((entry) => entry.logicalPath.toLowerCase());
  const physical = included.map((entry) => entry.physicalPath.toLowerCase());
  assertUnique(logical, "manifest.included", "LOGICAL_PATH_COLLISION");
  assertUnique(physical, "manifest.included", "PHYSICAL_PATH_COLLISION");
  const excludedPaths = excluded.map((entry) => entry.logicalPath.toLowerCase());
  assertUnique(excludedPaths, "manifest.excluded", "EXCLUDED_PATH_COLLISION");
  if (excludedPaths.some((entry) => logical.includes(entry))) invalid("INCLUDED_EXCLUDED_PATH_COLLISION", "manifest");
  const corpusBytes = included.reduce((sum, entry) => sum + entry.bytes, 0);
  if (corpusBytes > AGENT_COUNCIL_LIMITS.corpusBytes) invalid("CORPUS_SIZE_LIMIT", "manifest.included");
  const probeDeclarations = array(manifest.probeDeclarations, "manifest.probeDeclarations").map((declaration, index) => {
    const row = object(declaration, `manifest.probeDeclarations[${index}]`);
    assertOnlyKeys(row, ["id", "gateId"], `manifest.probeDeclarations[${index}]`);
    const gateId = safeId(row.gateId, `manifest.probeDeclarations[${index}].gateId`);
    if (!BROKER_GATE_CATALOG[gateId]) invalid("UNKNOWN_BROKER_GATE", `manifest.probeDeclarations[${index}].gateId`);
    return { id: safeId(row.id, `manifest.probeDeclarations[${index}].id`), gateId };
  });
  if (probeDeclarations.length > AGENT_COUNCIL_LIMITS.maxProbeDeclarations) invalid("PROBE_DECLARATION_LIMIT", "manifest.probeDeclarations");
  assertUnique(probeDeclarations.map((entry) => entry.id), "manifest.probeDeclarations", "DUPLICATE_PROBE_ID");
  const adapter = object(manifest.adapter, "manifest.adapter");
  assertOnlyKeys(adapter, ["name", "version"], "manifest.adapter");
  const normalized = {
    schemaVersion: AGENT_COUNCIL_SCHEMA_VERSION,
    runId: safeId(manifest.runId, "manifest.runId"),
    brief: validateDigestRecord(manifest.brief, "manifest.brief"),
    included,
    excluded,
    history: validateHistoryManifest(manifest.history, "manifest.history"),
    rosterSha256: digest(manifest.rosterSha256, "manifest.rosterSha256"),
    adapter: {
      name: safeId(adapter.name, "manifest.adapter.name"),
      version: text(adapter.version, "manifest.adapter.version", { max: 64 }),
    },
    probeDeclarations,
    limits: dataCopy(AGENT_COUNCIL_LIMITS),
    corpusSha256: digest(manifest.corpusSha256, "manifest.corpusSha256"),
  };
  if (canonicalJson(manifest.limits) !== canonicalJson(AGENT_COUNCIL_LIMITS)) invalid("LIMIT_CONTRACT_MISMATCH", "manifest.limits");
  const manifestSha256 = canonicalSha256(normalized);
  if (manifest.manifestSha256 !== undefined && digest(manifest.manifestSha256, "manifest.manifestSha256") !== manifestSha256) {
    invalid("MANIFEST_DIGEST_MISMATCH", "manifest.manifestSha256");
  }
  return deepFreeze({ ...normalized, manifestSha256 });
}

/** @typedef {{providerId:string,vendorId:string,familyId:string,baseModelId:string,correlationGroupIds:readonly string[]}} LineageV2 */
/** @typedef {{status:"qualified",method:"manual-static",checkedAt:string,expiresAt:string,adapter:object,capabilities:object,evidenceRef:string}} QualificationV2 */
/** @typedef {{id:string,allowedRoles:readonly ["decision"],runtimeDescriptor:string,lineage:LineageV2,qualification:QualificationV2}} QualifiedHostProfileV2 */
/** @typedef {{id:string,allowedRoles:readonly string[],model:string,variant:string,lineage:LineageV2,qualification:QualificationV2}} QualifiedExternalProfileV2 */
/** @typedef {{schemaVersion:2,version:2,hosts:QualifiedHostProfileV2[],participants:QualifiedExternalProfileV2[],auditors:QualifiedExternalProfileV2[]}} RosterPoolV2 */
/** @typedef {{version:1,profile:"focused"|"balanced"|"full",assuranceLevel:"focused"|"balanced"|"full",externalSeatCount:2|3|5,transportPolicy:"subscription-first",selectionMode:"automatic"|"explicit",requestedExternalIds:readonly string[],preferredExternalIds:readonly string[],excludedExternalIds:readonly string[],requestedAuditorId:string|null}} PanelSpecV1 */
/** @typedef {{schemaVersion:2,poolVersion:2,host:object,externalDecisionSeats:readonly object[],auditor:object,decisionSeats:readonly object[],panelSpec?:PanelSpecV1}} ResolvedRosterV2 */

function validateLineage(value, path) {
  const lineage = object(value, path);
  assertOnlyKeys(lineage, ["providerId", "vendorId", "familyId", "baseModelId", "correlationGroupIds"], path);
  const groups = array(lineage.correlationGroupIds, `${path}.correlationGroupIds`).map((entry, index) => safeId(entry, `${path}.correlationGroupIds[${index}]`));
  if (!groups.length) invalid("EMPTY_CORRELATION_GROUPS", `${path}.correlationGroupIds`);
  assertUnique(groups, `${path}.correlationGroupIds`, "DUPLICATE_CORRELATION_GROUP");
  return {
    providerId: safeId(lineage.providerId, `${path}.providerId`),
    vendorId: safeId(lineage.vendorId, `${path}.vendorId`),
    familyId: safeId(lineage.familyId, `${path}.familyId`),
    baseModelId: safeId(lineage.baseModelId, `${path}.baseModelId`),
    correlationGroupIds: groups,
  };
}

function validateQualification(value, path, nowMs, role) {
  const qualification = object(value, path);
  assertOnlyKeys(qualification, ["status", "method", "checkedAt", "expiresAt", "adapter", "capabilities", "evidenceRef"], path);
  if (qualification.status !== "qualified" || qualification.method !== "manual-static") invalid("UNQUALIFIED_PROFILE", path);
  const checkedAtMs = isoInstant(qualification.checkedAt, `${path}.checkedAt`);
  const expiresAtMs = isoInstant(qualification.expiresAt, `${path}.expiresAt`);
  if (expiresAtMs <= checkedAtMs || expiresAtMs - checkedAtMs > AGENT_COUNCIL_LIMITS.qualificationMaxAgeMs) invalid("INVALID_QUALIFICATION_WINDOW", path);
  if (nowMs < checkedAtMs || nowMs >= expiresAtMs) invalid("EXPIRED_OR_FUTURE_QUALIFICATION", path);
  const adapter = object(qualification.adapter, `${path}.adapter`);
  assertOnlyKeys(adapter, ["name", "version"], `${path}.adapter`);
  const adapterName = safeId(adapter.name, `${path}.adapter.name`);
  const adapterVersion = text(adapter.version, `${path}.adapter.version`, { max: 64 });
  const capabilities = object(qualification.capabilities, `${path}.capabilities`);
  const requiredCapabilities = role === "host"
    ? ["structuredChairRecord"]
    : [
        "repositoryRead",
        "repositorySearch",
        "snapshotEdit",
        "structuredResponseFile",
        "statelessRoundContext",
      ];
  for (const capability of requiredCapabilities) {
    if (capabilities[capability] !== true) invalid("MISSING_QUALIFIED_CAPABILITY", `${path}.capabilities.${capability}`);
  }
  // `capabilities` is copied verbatim into the resolved roster, the manifest
  // digest, and the durable audit record, so an unclosed key set would let an
  // operator-supplied `--roster` smuggle a retired or invented capability all
  // the way through. The required set is exactly the shipped set for both roles.
  assertOnlyKeys(capabilities, requiredCapabilities, `${path}.capabilities`);
  // One table lookup answers both adapter questions. `null` (unknown name,
  // non-string, prototype key) fails both closed.
  const contract = adapterContract(adapterName);
  if (role !== "host" && contract?.version !== adapterVersion) {
    invalid("ADAPTER_QUALIFICATION_MISMATCH", `${path}.adapter`);
  }
  // ceiling: an auditor must ride a `auditCapable` file-writing door, because
  // the audit path reads the auditor's response file directly and native seat
  // argv carries no write tool; upgrade: materialize the audit envelope from
  // native stdout against an audit JSON schema, the way native decision seats
  // are handled, and flip that adapter's `auditCapable` in the table.
  if (role === "auditor" && contract?.auditCapable !== true) invalid("AUDITOR_TRANSPORT_UNSUPPORTED", `${path}.adapter.name`);
  return {
    status: "qualified",
    method: "manual-static",
    checkedAt: qualification.checkedAt,
    expiresAt: qualification.expiresAt,
    adapter: { name: adapterName, version: adapterVersion },
    capabilities: dataCopy(capabilities),
    evidenceRef: safeId(qualification.evidenceRef, `${path}.evidenceRef`),
  };
}

function validateProfile(value, path, nowMs, role) {
  const profile = object(value, path);
  const isHost = role === "host";
  assertOnlyKeys(profile, isHost
    ? ["id", "allowedRoles", "runtimeDescriptor", "lineage", "qualification"]
    : ["id", "allowedRoles", "model", "variant", "lineage", "qualification"], path);
  const expectedRole = isHost ? "decision" : role === "auditor" ? "audit" : "decision";
  const roles = array(profile.allowedRoles, `${path}.allowedRoles`).map((entry, index) => safeId(entry, `${path}.allowedRoles[${index}]`));
  if (roles.length !== 1 || roles[0] !== expectedRole) invalid("PROFILE_ROLE_MISMATCH", `${path}.allowedRoles`);
  const common = {
    id: safeId(profile.id, `${path}.id`),
    allowedRoles: [expectedRole],
    lineage: validateLineage(profile.lineage, `${path}.lineage`),
    qualification: validateQualification(profile.qualification, `${path}.qualification`, nowMs, isHost ? "host" : role),
  };
  if (isHost) return { ...common, runtimeDescriptor: text(profile.runtimeDescriptor, `${path}.runtimeDescriptor`, { max: 256 }) };
  return {
    ...common,
    model: text(profile.model, `${path}.model`, { max: 256 }),
    variant: safeId(profile.variant, `${path}.variant`),
  };
}

/**
 * Every reason two profiles may not sit at the same table. Exported because the
 * seat picker must refuse exactly what the resolver refuses — a second, weaker
 * "distinct vendor" check in the picker would hand `prepare` a pick it rejects
 * with SELECTED_ROSTER_COLLISION after the operator had already chosen.
 */
export function profileCollisions(left, right) {
  const reasons = [];
  if (left.id === right.id) reasons.push("seat_id");
  if (left.model && right.model && normalizeComparableId(left.model) === normalizeComparableId(right.model)) reasons.push("model");
  for (const key of ["vendorId", "familyId", "baseModelId"]) {
    if (left.lineage[key] === right.lineage[key]) reasons.push(key);
  }
  const rightGroups = new Set(right.lineage.correlationGroupIds);
  if (left.lineage.correlationGroupIds.some((group) => rightGroups.has(group))) reasons.push("correlation_group");
  return reasons;
}

function allPairwiseDistinct(profiles) {
  for (let left = 0; left < profiles.length; left += 1) {
    for (let right = left + 1; right < profiles.length; right += 1) {
      if (profileCollisions(profiles[left], profiles[right]).length) return false;
    }
  }
  return true;
}

function combinations(values, size, start = 0, prefix = []) {
  if (prefix.length === size) return [prefix];
  const output = [];
  for (let index = start; index <= values.length - (size - prefix.length); index += 1) {
    output.push(...combinations(values, size, index + 1, [...prefix, values[index]]));
  }
  return output;
}

function normalizeAvailableModels(value) {
  if (value instanceof Set) return new Set([...value].map(String));
  if (Array.isArray(value)) return new Set(value.map(String));
  invalid("EXPECTED_MODEL_SET", "availableModelIds");
}

function normalizedUniqueIds(value, path) {
  const ids = array(value ?? [], path).map((entry, index) => safeId(entry, `${path}[${index}]`));
  assertUnique(ids, path, "DUPLICATE_PANEL_PROFILE_ID");
  return ids;
}

export function normalizePanelSpec(input = {}) {
  const args = object(input, "panelSpecInput");
  if (args.panelSpec !== undefined) {
    const value = object(args.panelSpec, "panelSpec");
    assertOnlyKeys(value, [
      "version",
      "profile",
      "assuranceLevel",
      "externalSeatCount",
      "transportPolicy",
      "selectionMode",
      "requestedExternalIds",
      "preferredExternalIds",
      "excludedExternalIds",
      "requestedAuditorId",
    ], "panelSpec");
    if (value.version !== AGENT_COUNCIL_PANEL_SPEC_VERSION) invalid("UNSUPPORTED_PANEL_SPEC_VERSION", "panelSpec.version");
    const profile = oneOf(value.profile, Object.keys(AGENT_COUNCIL_PANEL_PROFILES), "panelSpec.profile");
    const profileContract = AGENT_COUNCIL_PANEL_PROFILES[profile];
    const assuranceLevel = oneOf(value.assuranceLevel, Object.values(AGENT_COUNCIL_PANEL_PROFILES).map((entry) => entry.assuranceLevel), "panelSpec.assuranceLevel");
    const externalSeatCount = integer(value.externalSeatCount, "panelSpec.externalSeatCount", { min: 2, max: REQUIRED_EXTERNAL_DECISION_SEATS });
    if (assuranceLevel !== profileContract.assuranceLevel || externalSeatCount !== profileContract.externalSeatCount) {
      invalid("PANEL_PROFILE_CONTRACT_MISMATCH", "panelSpec");
    }
    const transportPolicy = oneOf(value.transportPolicy, AGENT_COUNCIL_TRANSPORT_POLICIES, "panelSpec.transportPolicy");
    const selectionMode = oneOf(value.selectionMode, ["automatic", "explicit"], "panelSpec.selectionMode");
    const requestedExternalIds = normalizedUniqueIds(value.requestedExternalIds, "panelSpec.requestedExternalIds");
    const preferredExternalIds = normalizedUniqueIds(value.preferredExternalIds, "panelSpec.preferredExternalIds");
    const excludedExternalIds = normalizedUniqueIds(value.excludedExternalIds, "panelSpec.excludedExternalIds");
    const requestedAuditorId = value.requestedAuditorId === null
      ? null
      : safeId(value.requestedAuditorId, "panelSpec.requestedAuditorId");
    if (selectionMode === "explicit" && requestedExternalIds.length !== externalSeatCount) {
      invalid("WRONG_EXTERNAL_SEAT_COUNT", "panelSpec.requestedExternalIds");
    }
    if (selectionMode === "automatic" && requestedExternalIds.length) {
      invalid("AUTOMATIC_PANEL_WITH_EXPLICIT_SEATS", "panelSpec.requestedExternalIds");
    }
    if (selectionMode === "explicit" && preferredExternalIds.length) {
      invalid("EXPLICIT_PANEL_WITH_PREFERENCES", "panelSpec.preferredExternalIds");
    }
    const excluded = new Set(excludedExternalIds);
    if (requestedExternalIds.some((id) => excluded.has(id)) || preferredExternalIds.some((id) => excluded.has(id))) {
      invalid("CONTRADICTORY_PANEL_SELECTION", "panelSpec");
    }
    return deepFreeze({
      version: AGENT_COUNCIL_PANEL_SPEC_VERSION,
      profile,
      assuranceLevel,
      externalSeatCount,
      transportPolicy,
      selectionMode,
      requestedExternalIds,
      preferredExternalIds,
      excludedExternalIds,
      requestedAuditorId,
    });
  }
  const profile = oneOf(args.profile ?? "full", Object.keys(AGENT_COUNCIL_PANEL_PROFILES), "profile");
  const profileContract = AGENT_COUNCIL_PANEL_PROFILES[profile];
  const requestedExternalIds = normalizedUniqueIds(args.selectedExternalIds, "selectedExternalIds");
  const preferredExternalIds = normalizedUniqueIds(args.preferredExternalIds, "preferredExternalIds");
  const excludedExternalIds = normalizedUniqueIds(args.excludedExternalIds, "excludedExternalIds");
  const selectionMode = requestedExternalIds.length ? "explicit" : "automatic";
  const requestedAuditorId = args.auditorId === undefined || args.auditorId === null
    ? null
    : safeId(args.auditorId, "auditorId");
  return normalizePanelSpec({
    panelSpec: {
      version: AGENT_COUNCIL_PANEL_SPEC_VERSION,
      profile,
      assuranceLevel: profileContract.assuranceLevel,
      externalSeatCount: profileContract.externalSeatCount,
      transportPolicy: args.transportPolicy ?? "subscription-first",
      selectionMode,
      requestedExternalIds,
      preferredExternalIds,
      excludedExternalIds,
      requestedAuditorId,
    },
  });
}

function orderParticipantsForPanel(participants, panelSpec) {
  const preferred = new Map(panelSpec.preferredExternalIds.map((id, index) => [id, index]));
  return participants
    .map((profile, index) => ({ profile, index }))
    .sort((left, right) => {
      const leftPreferred = preferred.has(left.profile.id) ? preferred.get(left.profile.id) : Number.MAX_SAFE_INTEGER;
      const rightPreferred = preferred.has(right.profile.id) ? preferred.get(right.profile.id) : Number.MAX_SAFE_INTEGER;
      if (leftPreferred !== rightPreferred) return leftPreferred - rightPreferred;
      if (panelSpec.transportPolicy === "subscription-first") {
        // Native subscription CLIs rank ahead of every pay-per-token seat. The
        // fact comes from the adapter table, not from a name literal; an
        // unknown adapter has no declared subscription door and ranks last.
        const leftRank = adapterContract(left.profile.qualification.adapter.name)?.subscriptionTransport === true ? 0 : 1;
        const rightRank = adapterContract(right.profile.qualification.adapter.name)?.subscriptionTransport === true ? 0 : 1;
        if (leftRank !== rightRank) return leftRank - rightRank;
      }
      return left.index - right.index;
    })
    .map(({ profile }) => profile);
}

/**
 * Parses a roster pool into validated host, participant and auditor profiles.
 *
 * The one place roster rows are type-checked. `validateRoster` calls it, and so
 * does the seat picker — which previously hand-rolled a looser check over the
 * same file and would accept rows this one rejects. Role scoping is the part
 * that matters: `validateProfile` closes the key set per role, so a host row
 * carrying a `model` key or a seat row carrying a `runtimeDescriptor` is an
 * UNKNOWN_FIELD here rather than a row that silently changes which collision
 * axes apply later.
 *
 * Throws AgentCouncilValidationError. `nowMs` is passed in; nothing reads a clock.
 */
export function validateRosterPool(pool, nowMs) {
  object(pool, "pool");
  if (pool.schemaVersion !== AGENT_COUNCIL_SCHEMA_VERSION || pool.version !== AGENT_COUNCIL_ROSTER_VERSION) {
    invalid("UNSUPPORTED_ROSTER_VERSION", "pool.version");
  }
  const hosts = array(pool.hosts, "pool.hosts").map((entry, index) => validateProfile(entry, `pool.hosts[${index}]`, nowMs, "host"));
  const participants = array(pool.participants, "pool.participants").map((entry, index) => validateProfile(entry, `pool.participants[${index}]`, nowMs, "participant"));
  const auditors = array(pool.auditors, "pool.auditors").map((entry, index) => validateProfile(entry, `pool.auditors[${index}]`, nowMs, "auditor"));
  assertUnique([...hosts, ...participants, ...auditors].map((profile) => profile.id), "pool", "DUPLICATE_PROFILE_ID");
  return { hosts, participants, auditors };
}

export function validateRoster(input) {
  const args = object(input, "rosterInput");
  const pool = args.pool ?? {
    schemaVersion: AGENT_COUNCIL_SCHEMA_VERSION,
    version: args.poolVersion,
    hosts: args.host ? [args.host] : [],
    participants: args.candidates ?? [],
    auditors: args.auditors ?? [],
  };
  const nowMs = typeof args.now === "number" ? finiteNumber(args.now, "now") : isoInstant(args.now, "now");
  const { hosts, participants, auditors } = validateRosterPool(pool, nowMs);
  const hostId = args.hostId ?? args.host?.id;
  const host = hosts.find((profile) => profile.id === normalizeComparableId(text(hostId, "hostId", { max: 128 })));
  if (!host) invalid("HOST_PROFILE_NOT_FOUND", "hostId");
  const panelSpec = normalizePanelSpec(args);
  if (args.allowUnresolvedPanelReferences !== true) {
    const participantIds = new Set(participants.map((profile) => profile.id));
    for (const profileId of [
      ...panelSpec.requestedExternalIds,
      ...panelSpec.preferredExternalIds,
      ...panelSpec.excludedExternalIds,
    ]) {
      if (!participantIds.has(profileId)) invalid("UNKNOWN_PANEL_PROFILE_ID", "panelSpec");
    }
  }
  const available = normalizeAvailableModels(args.availableModelIds);
  const excluded = new Set(panelSpec.excludedExternalIds);
  const availableParticipants = orderParticipantsForPanel(participants.filter((profile) => (
    available.has(profile.model) && !excluded.has(profile.id)
  )), panelSpec);
  const availableAuditors = auditors.filter((profile) => available.has(profile.model));
  let selection = null;
  const selectedIds = args.selectedExternalIds !== undefined
    ? normalizedUniqueIds(args.selectedExternalIds, "selectedExternalIds")
    : panelSpec.requestedExternalIds;
  const requestedAuditorId = args.auditorId !== undefined
    ? safeId(args.auditorId, "auditorId")
    : panelSpec.requestedAuditorId;
  if (selectedIds.length) {
    if (selectedIds.length !== panelSpec.externalSeatCount) invalid("WRONG_EXTERNAL_SEAT_COUNT", "selectedExternalIds");
    const selected = selectedIds.map((id) => availableParticipants.find((profile) => profile.id === id));
    if (selected.some((profile) => !profile)) invalid("SELECTED_MODEL_UNAVAILABLE", "selectedExternalIds");
    if (!allPairwiseDistinct([host, ...selected])) invalid("SELECTED_ROSTER_COLLISION", "roster");
    const auditor = requestedAuditorId
      ? availableAuditors.find((profile) => profile.id === requestedAuditorId)
      : availableAuditors.find((candidate) => allPairwiseDistinct([host, ...selected, candidate]));
    if (!auditor) invalid("SELECTED_AUDITOR_UNAVAILABLE", "auditorId");
    if (!allPairwiseDistinct([host, ...selected, auditor])) invalid("SELECTED_ROSTER_COLLISION", "roster");
    selection = { external: selected, auditor };
  } else {
    for (const external of combinations(availableParticipants, panelSpec.externalSeatCount)) {
      if (!allPairwiseDistinct([host, ...external])) continue;
      const auditor = requestedAuditorId
        ? availableAuditors.find((candidate) => candidate.id === requestedAuditorId && allPairwiseDistinct([host, ...external, candidate]))
        : availableAuditors.find((candidate) => allPairwiseDistinct([host, ...external, candidate]));
      if (auditor) {
        selection = { external, auditor };
        break;
      }
    }
  }
  if (!selection) invalid("NO_DIVERSE_QUALIFIED_ROSTER", "roster");
  const resolvedHost = { ...host, role: "chair" };
  const externalDecisionSeats = selection.external.map((profile) => ({ ...profile, role: "external-decision" }));
  const resolvedAuditor = { ...selection.auditor, role: "auditor" };
  const resolved = {
    schemaVersion: AGENT_COUNCIL_SCHEMA_VERSION,
    poolVersion: AGENT_COUNCIL_ROSTER_VERSION,
    host: resolvedHost,
    externalDecisionSeats,
    auditor: resolvedAuditor,
    decisionSeats: [resolvedHost, ...externalDecisionSeats],
    panelSpec,
  };
  return deepFreeze(dataCopy(resolved));
}

function disclosureEntries(disclosure) {
  if (!disclosure) return new Map();
  const included = Array.isArray(disclosure) ? disclosure : disclosure.included;
  return new Map(array(included, "disclosure.included").map((entry, index) => {
    const normalized = validateIncludedDisclosureEntry(entry, `disclosure.included[${index}]`);
    return [normalized.logicalPath, normalized];
  }));
}

function receiptIds(receipts) {
  const output = new Set();
  for (const [index, receipt] of array(receipts ?? [], "receipts").entries()) {
    const row = object(receipt, `receipts[${index}]`);
    const id = row.payload?.id ?? row.id;
    output.add(safeId(id, `receipts[${index}].id`));
  }
  return output;
}

/** @typedef {{path:string,lineStart:number,lineEnd:number,fileSha256:string}} CitationV2 */
/** @typedef {{choiceId:string,summary:string,confidence:number}} RecommendationV2 */
/** @typedef {{id:string,kind:string,statement:string,confidence:number,citations:CitationV2[],probeReceiptIds:string[]}} ClaimV2 */
/** @typedef {{id:string,statement:string,impact:number,likelihood:number,claimIds:string[],mitigation:string}} RiskV2 */
/** @typedef {{id:string,summary:string,rejectionReason:string}} AlternativeV2 */
/** @typedef {{statement:string,answer:string}} SelfCounterargumentV2 */
/** @typedef {{schemaVersion:2,runId:string,round:number,seatId:string,role:"external-decision",nonce:string,recommendation:RecommendationV2,claims:ClaimV2[],risks:RiskV2[],alternatives:AlternativeV2[],selfCounterargument:SelfCounterargumentV2,unresolvedQuestions:string[]}} SeatResponseV2 */
/** @typedef {{kind:"changed",fromChoiceId:string,toChoiceId:string,reasonClaimIds:string[]}|{kind:"unchanged",choiceId:string,rationale:string,reasonClaimIds:string[]}|null} ChairMovementV2 */
/** @typedef {SeatResponseV2 & {role:"chair",movement:ChairMovementV2}} ChairResponseV2 */

function validateExpectedResponse(expected, path) {
  const value = object(expected, path);
  return {
    runId: safeId(value.runId, `${path}.runId`),
    round: integer(value.round, `${path}.round`, { min: 1, max: 3 }),
    seatId: safeId(value.seatId, `${path}.seatId`),
    nonce: text(value.nonce, `${path}.nonce`, { max: 512 }),
  };
}

function validateRecommendation(value, path) {
  const record = object(value, path);
  assertOnlyKeys(record, ["choiceId", "summary", "confidence"], path);
  return {
    choiceId: safeId(record.choiceId, `${path}.choiceId`),
    summary: text(record.summary, `${path}.summary`, { max: 4_096 }),
    confidence: finiteNumber(record.confidence, `${path}.confidence`, { min: 0, max: 1 }),
  };
}

function validateCitation(value, path, entries) {
  const citation = object(value, path);
  assertOnlyKeys(citation, ["path", "lineStart", "lineEnd", "fileSha256"], path);
  const logicalPath = normalizeRelativePosixPath(citation.path);
  const entry = entries.get(logicalPath);
  if (!entry) invalid("CITATION_OUTSIDE_DISCLOSURE", `${path}.path`);
  const lineStart = integer(citation.lineStart, `${path}.lineStart`, { min: 1 });
  const lineEnd = integer(citation.lineEnd, `${path}.lineEnd`, { min: lineStart });
  const fileSha256 = digest(citation.fileSha256, `${path}.fileSha256`);
  if (fileSha256 !== entry.sha256) invalid("CITATION_DIGEST_MISMATCH", `${path}.fileSha256`);
  return { path: logicalPath, lineStart, lineEnd, fileSha256 };
}

function validateCommonResponse(response, expected, disclosure, receipts, role) {
  const path = "response";
  object(response, path);
  const allowed = [
    "schemaVersion", "runId", "round", "seatId", "role", "nonce", "recommendation", "claims",
    "risks", "alternatives", "selfCounterargument", "unresolvedQuestions",
  ];
  if (role === "chair") allowed.push("movement");
  assertOnlyKeys(response, allowed, path);
  if (response.schemaVersion !== AGENT_COUNCIL_SCHEMA_VERSION) invalid("UNSUPPORTED_RESPONSE_VERSION", `${path}.schemaVersion`);
  for (const key of ["runId", "round", "seatId", "nonce"]) {
    if (response[key] !== expected[key]) invalid("RESPONSE_IDENTITY_MISMATCH", `${path}.${key}`);
  }
  if (response.role !== role) invalid("RESPONSE_ROLE_MISMATCH", `${path}.role`);
  const entries = disclosureEntries(disclosure);
  const issuedReceipts = receiptIds(receipts);
  const claims = array(response.claims, `${path}.claims`).map((claim, index) => {
    const claimPath = `${path}.claims[${index}]`;
    const row = object(claim, claimPath);
    assertOnlyKeys(row, ["id", "kind", "statement", "confidence", "citations", "probeReceiptIds"], claimPath);
    const citations = array(row.citations, `${claimPath}.citations`).map((citation, citationIndex) => validateCitation(citation, `${claimPath}.citations[${citationIndex}]`, entries));
    const probeReceiptIds = array(row.probeReceiptIds, `${claimPath}.probeReceiptIds`).map((id, receiptIndex) => safeId(id, `${claimPath}.probeReceiptIds[${receiptIndex}]`));
    for (const id of probeReceiptIds) if (!issuedReceipts.has(id)) invalid("FABRICATED_PROBE_RECEIPT", `${claimPath}.probeReceiptIds`);
    if (!citations.length && !probeReceiptIds.length) invalid("CLAIM_WITHOUT_EVIDENCE", claimPath);
    return {
      id: safeId(row.id, `${claimPath}.id`),
      kind: safeId(row.kind, `${claimPath}.kind`),
      statement: text(row.statement, `${claimPath}.statement`, { max: 16_384 }),
      confidence: finiteNumber(row.confidence, `${claimPath}.confidence`, { min: 0, max: 1 }),
      citations,
      probeReceiptIds,
    };
  });
  if (!claims.length) invalid("RESPONSE_WITHOUT_CLAIMS", `${path}.claims`);
  assertUnique(claims.map((claim) => claim.id), `${path}.claims`, "DUPLICATE_CLAIM_ID");
  const claimIds = new Set(claims.map((claim) => claim.id));
  const risks = array(response.risks, `${path}.risks`).map((risk, index) => {
    const riskPath = `${path}.risks[${index}]`;
    const row = object(risk, riskPath);
    assertOnlyKeys(row, ["id", "statement", "impact", "likelihood", "claimIds", "mitigation"], riskPath);
    const references = array(row.claimIds, `${riskPath}.claimIds`).map((id, claimIndex) => safeId(id, `${riskPath}.claimIds[${claimIndex}]`));
    if (!references.length) invalid("RISK_WITHOUT_CLAIM", `${riskPath}.claimIds`);
    if (references.some((id) => !claimIds.has(id))) invalid("UNKNOWN_CLAIM_REFERENCE", `${riskPath}.claimIds`);
    return {
      id: safeId(row.id, `${riskPath}.id`),
      statement: text(row.statement, `${riskPath}.statement`, { max: 8_192 }),
      impact: integer(row.impact, `${riskPath}.impact`, { min: 1, max: 5 }),
      likelihood: integer(row.likelihood, `${riskPath}.likelihood`, { min: 1, max: 5 }),
      claimIds: references,
      mitigation: text(row.mitigation, `${riskPath}.mitigation`, { max: 8_192 }),
    };
  });
  if (!risks.length) invalid("RESPONSE_WITHOUT_RISKS", `${path}.risks`);
  assertUnique(risks.map((risk) => risk.id), `${path}.risks`, "DUPLICATE_RISK_ID");
  const alternatives = array(response.alternatives, `${path}.alternatives`).map((alternative, index) => {
    const alternativePath = `${path}.alternatives[${index}]`;
    const row = object(alternative, alternativePath);
    assertOnlyKeys(row, ["id", "summary", "rejectionReason"], alternativePath);
    return {
      id: safeId(row.id, `${alternativePath}.id`),
      summary: text(row.summary, `${alternativePath}.summary`, { max: 4_096 }),
      rejectionReason: text(row.rejectionReason, `${alternativePath}.rejectionReason`, { max: 4_096 }),
    };
  });
  if (!alternatives.length) invalid("RESPONSE_WITHOUT_ALTERNATIVES", `${path}.alternatives`);
  assertUnique(alternatives.map((alternative) => alternative.id), `${path}.alternatives`, "DUPLICATE_ALTERNATIVE_ID");
  const selfCounterargument = object(response.selfCounterargument, `${path}.selfCounterargument`);
  assertOnlyKeys(selfCounterargument, ["statement", "answer"], `${path}.selfCounterargument`);
  const unresolvedQuestions = array(response.unresolvedQuestions, `${path}.unresolvedQuestions`).map((question, index) => text(question, `${path}.unresolvedQuestions[${index}]`, { max: 4_096 }));
  return {
    schemaVersion: AGENT_COUNCIL_SCHEMA_VERSION,
    runId: expected.runId,
    round: expected.round,
    seatId: expected.seatId,
    role,
    nonce: expected.nonce,
    recommendation: validateRecommendation(response.recommendation, `${path}.recommendation`),
    claims,
    risks,
    alternatives,
    selfCounterargument: {
      statement: text(selfCounterargument.statement, `${path}.selfCounterargument.statement`, { max: 8_192 }),
      answer: text(selfCounterargument.answer, `${path}.selfCounterargument.answer`, { max: 8_192 }),
    },
    unresolvedQuestions,
  };
}

export function validateSeatResponse({ expected, response, disclosure, receipts = [] }) {
  const normalizedExpected = validateExpectedResponse(expected, "expected");
  const normalized = validateCommonResponse(response, normalizedExpected, disclosure, receipts, "external-decision");
  return deepFreeze(normalized);
}

export function validateChairResponse({ expected, response, disclosure, receipts = [] }) {
  const normalizedExpected = validateExpectedResponse(expected, "expected");
  const normalized = validateCommonResponse(response, normalizedExpected, disclosure, receipts, "chair");
  const claimIds = new Set(normalized.claims.map((claim) => claim.id));
  let movement;
  if (normalizedExpected.round === 1) {
    if (response.movement !== null) invalid("ROUND1_CHAIR_MOVEMENT", "response.movement");
    movement = null;
  } else {
    const value = object(response.movement, "response.movement");
    if (value.kind === "changed") {
      assertOnlyKeys(value, ["kind", "fromChoiceId", "toChoiceId", "reasonClaimIds"], "response.movement");
      const reasonClaimIds = array(value.reasonClaimIds, "response.movement.reasonClaimIds").map((id, index) => safeId(id, `response.movement.reasonClaimIds[${index}]`));
      if (!reasonClaimIds.length || reasonClaimIds.some((id) => !claimIds.has(id))) invalid("INVALID_MOVEMENT_CLAIM_REFERENCE", "response.movement.reasonClaimIds");
      movement = {
        kind: "changed",
        fromChoiceId: safeId(value.fromChoiceId, "response.movement.fromChoiceId"),
        toChoiceId: safeId(value.toChoiceId, "response.movement.toChoiceId"),
        reasonClaimIds,
      };
      if (movement.fromChoiceId === movement.toChoiceId) invalid("NON_MOVING_CHANGED_RECORD", "response.movement");
    } else if (value.kind === "unchanged") {
      assertOnlyKeys(value, ["kind", "choiceId", "rationale", "reasonClaimIds"], "response.movement");
      const reasonClaimIds = array(value.reasonClaimIds, "response.movement.reasonClaimIds").map((id, index) => safeId(id, `response.movement.reasonClaimIds[${index}]`));
      if (reasonClaimIds.some((id) => !claimIds.has(id))) invalid("INVALID_MOVEMENT_CLAIM_REFERENCE", "response.movement.reasonClaimIds");
      movement = {
        kind: "unchanged",
        choiceId: safeId(value.choiceId, "response.movement.choiceId"),
        rationale: text(value.rationale, "response.movement.rationale", { max: 8_192 }),
        reasonClaimIds,
      };
    } else {
      invalid("INVALID_CHAIR_MOVEMENT", "response.movement.kind");
    }
  }
  return deepFreeze({ ...normalized, movement });
}

function roundTwoResponses(value, roster) {
  const responses = array(value, "round2");
  const externalSeatCount = array(roster?.externalDecisionSeats, "roster.externalDecisionSeats").length;
  if (responses.length !== externalSeatCount + 1) invalid("ROUND2_RESPONSE_COUNT", "round2");
  if (responses.filter((response) => response?.role === "chair").length !== 1) invalid("ROUND2_CHAIR_COUNT", "round2");
  if (responses.filter((response) => response?.role === "external-decision").length !== externalSeatCount) invalid("ROUND2_EXTERNAL_COUNT", "round2");
  if (responses.some((response) => response?.round !== 2)) invalid("ROUND2_RESPONSE_ROUND", "round2");
  assertUnique(responses.map((response) => response.seatId), "round2", "ROUND2_DUPLICATE_SEAT");
  return responses;
}

function rosterSeatMap(roster) {
  const resolved = object(roster, "roster");
  const externalSeats = array(resolved.externalDecisionSeats, "roster.externalDecisionSeats");
  const expectedExternalCount = resolved.panelSpec === undefined
    ? REQUIRED_EXTERNAL_DECISION_SEATS
    : normalizePanelSpec({ panelSpec: resolved.panelSpec }).externalSeatCount;
  if (externalSeats.length !== expectedExternalCount) invalid("RESOLVED_ROSTER_CARDINALITY", "roster");
  const seats = [resolved.host, ...externalSeats];
  return new Map(seats.map((seat) => [seat.id, seat]));
}

/** @typedef {{id:string,kind:"choice_conflict"|"semantic",category?:string,involvedSeatIds:string[],claimIds:string[],confidence:number,evidenceRefs:string[],resolved:false}} ConsequentialDisagreementV2 */

function qualifiedClaimReferenceId(round, seatId, claimId) {
  const roundNumber = integer(round, "claimReference.round", { min: 1, max: 3 });
  const normalizedSeatId = safeId(seatId, "claimReference.seatId");
  const normalizedClaimId = safeId(claimId, "claimReference.claimId");
  return `r${roundNumber}:${canonicalSha256({ seatId: normalizedSeatId, claimId: normalizedClaimId })}`;
}

export function validateDisagreementAnnotation({ annotation, round2, roster }) {
  const responses = roundTwoResponses(round2, roster);
  const seats = rosterSeatMap(roster);
  const value = object(annotation, "annotation");
  assertOnlyKeys(value, ["id", "category", "statement", "involvedSeatIds", "claimIds", "confidence", "citationPaths", "probeReceiptIds", "resolved"], "annotation");
  const involvedSeatIds = array(value.involvedSeatIds, "annotation.involvedSeatIds").map((id, index) => safeId(id, `annotation.involvedSeatIds[${index}]`));
  assertUnique(involvedSeatIds, "annotation.involvedSeatIds", "DUPLICATE_INVOLVED_SEAT");
  if (involvedSeatIds.length < 2 || involvedSeatIds.some((id) => !seats.has(id))) invalid("INVALID_DISAGREEMENT_SEATS", "annotation.involvedSeatIds");
  const familyIds = new Set(involvedSeatIds.map((id) => seats.get(id).lineage.familyId));
  if (familyIds.size < 2) invalid("CORRELATED_DISAGREEMENT_SEATS", "annotation.involvedSeatIds");
  const claimMap = new Map();
  for (const response of responses) {
    for (const claim of response.claims) claimMap.set(qualifiedClaimReferenceId(2, response.seatId, claim.id), { seatId: response.seatId, claim });
  }
  const claimIds = array(value.claimIds, "annotation.claimIds").map((id, index) => safeId(id, `annotation.claimIds[${index}]`));
  if (!claimIds.length || claimIds.some((id) => !claimMap.has(id))) invalid("UNKNOWN_DISAGREEMENT_CLAIM", "annotation.claimIds");
  for (const id of claimIds) {
    const { seatId, claim } = claimMap.get(id);
    if (!involvedSeatIds.includes(seatId)) invalid("DISAGREEMENT_CLAIM_OUTSIDE_INVOLVED_SEATS", "annotation.claimIds");
    if (claim.confidence < AGENT_COUNCIL_LIMITS.consequentialConfidence || (!claim.citations.length && !claim.probeReceiptIds.length)) {
      invalid("INSUFFICIENT_DISAGREEMENT_EVIDENCE", "annotation.claimIds");
    }
  }
  const citationPaths = array(value.citationPaths ?? [], "annotation.citationPaths").map(normalizeRelativePosixPath);
  const probeReceiptIds = array(value.probeReceiptIds ?? [], "annotation.probeReceiptIds").map((id, index) => safeId(id, `annotation.probeReceiptIds[${index}]`));
  if (!citationPaths.length && !probeReceiptIds.length) invalid("ANNOTATION_WITHOUT_EVIDENCE", "annotation");
  const referencedClaims = claimIds.map((id) => claimMap.get(id).claim);
  const allowedCitationPaths = new Set(referencedClaims.flatMap((claim) => claim.citations.map((citation) => citation.path)));
  const allowedProbeReceiptIds = new Set(referencedClaims.flatMap((claim) => claim.probeReceiptIds));
  if (citationPaths.some((citationPath) => !allowedCitationPaths.has(citationPath))
    || probeReceiptIds.some((receiptId) => !allowedProbeReceiptIds.has(receiptId))) {
    invalid("DISAGREEMENT_EVIDENCE_NOT_IN_REFERENCED_CLAIMS", "annotation");
  }
  if (value.resolved !== false) invalid("RESOLVED_DISAGREEMENT_ANNOTATION", "annotation.resolved");
  return deepFreeze({
    id: safeId(value.id, "annotation.id"),
    kind: "semantic",
    category: oneOf(value.category, CONSEQUENTIAL_DISAGREEMENT_CATEGORIES, "annotation.category"),
    statement: text(value.statement, "annotation.statement", { max: 8_192 }),
    involvedSeatIds,
    claimIds,
    confidence: finiteNumber(value.confidence, "annotation.confidence", { min: AGENT_COUNCIL_LIMITS.consequentialConfidence, max: 1 }),
    evidenceRefs: [...citationPaths.map((entry) => `citation:${entry}`), ...probeReceiptIds.map((entry) => `receipt:${entry}`)],
    resolved: false,
  });
}

export function deriveConsequentialDisagreements({ round2, roster, annotations = [] }) {
  const responses = roundTwoResponses(round2, roster);
  const seats = rosterSeatMap(roster);
  for (const response of responses) if (!seats.has(response.seatId)) invalid("ROUND2_SEAT_OUTSIDE_ROSTER", "round2");
  const disagreements = [];
  const confident = responses.filter((response) => response.recommendation.confidence >= AGENT_COUNCIL_LIMITS.consequentialConfidence);
  const choices = new Map();
  for (const response of confident) {
    const list = choices.get(response.recommendation.choiceId) ?? [];
    list.push(response.seatId);
    choices.set(response.recommendation.choiceId, list);
  }
  if (choices.size >= 2) {
    disagreements.push({
      id: CHOICE_CONFLICT_ID,
      kind: "choice_conflict",
      involvedSeatIds: [...new Set([...choices.values()].flat())].sort(),
      claimIds: [],
      confidence: Math.min(...confident.map((response) => response.recommendation.confidence)),
      evidenceRefs: [...choices.keys()].sort().map((choice) => `choice:${choice}`),
      resolved: false,
    });
  }
  for (const annotation of array(annotations, "annotations")) {
    disagreements.push(validateDisagreementAnnotation({ annotation, round2: responses, roster }));
  }
  assertUnique(disagreements.map((entry) => entry.id), "disagreements", "DUPLICATE_DISAGREEMENT_ID");
  const result = deepFreeze(disagreements.map(dataCopy));
  DERIVED_DISAGREEMENT_SETS.add(result);
  return result;
}

export function evaluateRound3({ round2, disagreements, roster }) {
  roundTwoResponses(round2, roster);
  if (!DERIVED_DISAGREEMENT_SETS.has(disagreements)) invalid("UNTRUSTED_DISAGREEMENT_SET", "disagreements");
  const reasons = disagreements.map((entry) => entry.id).sort();
  return deepFreeze({ required: reasons.length > 0, reasons });
}

function normalizeAuditArguments(input) {
  const args = object(input, "auditInput");
  return {
    expectedRunId: safeId(args.expectedRunId ?? args.expected?.runId, "auditInput.expectedRunId"),
    expectedNonce: text(args.expectedNonce ?? args.expected?.nonce, "auditInput.expectedNonce", { max: 512 }),
    expectedSeatId: args.expectedSeatId ?? args.expected?.seatId,
    expectedClaimIds: args.expectedClaimIds,
    expectedEvidenceRefs: args.expectedEvidenceRefs,
    value: args.value ?? args.response,
  };
}

export function buildAuditClaimReferenceIndex(rounds) {
  const references = [];
  for (const round of array(rounds, "rounds")) {
    const roundNumber = integer(round?.number, "round.number", { min: 1, max: 3 });
    for (const response of [round?.chair, ...array(round?.externals ?? [], "round.externals")].filter(Boolean)) {
      const seatId = safeId(response.seatId, "response.seatId");
      for (const claim of array(response.claims, "response.claims")) {
        const claimId = safeId(claim?.id, "claim.id");
        references.push({ qualifiedId: qualifiedClaimReferenceId(roundNumber, seatId, claimId), round: roundNumber, seatId, claimId });
      }
    }
  }
  assertUnique(references.map((reference) => reference.qualifiedId), "claimReferenceIndex", "DUPLICATE_QUALIFIED_CLAIM_REFERENCE");
  return deepFreeze(references);
}

/** @typedef {{schemaVersion:2,runId:string,seatId:string,role:"auditor",nonce:string,verdict:"FAITHFUL"|"NEEDS-REVISION",summary:string,findings:object[],omittedDissentIds:string[]}} AuditResponseV2 */

export function parseAuditResponse(input) {
  const { expectedRunId, expectedNonce, expectedSeatId, expectedClaimIds, expectedEvidenceRefs, value } = normalizeAuditArguments(input);
  const allowedClaims = expectedClaimIds === undefined ? null : new Set(array(expectedClaimIds, "auditInput.expectedClaimIds").map((id, index) => safeId(id, `auditInput.expectedClaimIds[${index}]`)));
  const allowedEvidence = expectedEvidenceRefs === undefined ? null : new Set(array(expectedEvidenceRefs, "auditInput.expectedEvidenceRefs").map(String));
  const response = object(value, "auditResponse");
  assertOnlyKeys(response, ["schemaVersion", "runId", "seatId", "role", "nonce", "verdict", "summary", "findings", "omittedDissentIds"], "auditResponse");
  if (response.schemaVersion !== AGENT_COUNCIL_SCHEMA_VERSION) invalid("UNSUPPORTED_AUDIT_VERSION", "auditResponse.schemaVersion");
  if (response.runId !== expectedRunId || response.nonce !== expectedNonce) invalid("AUDIT_IDENTITY_MISMATCH", "auditResponse");
  if (expectedSeatId !== undefined && response.seatId !== expectedSeatId) invalid("AUDIT_SEAT_MISMATCH", "auditResponse.seatId");
  if (response.role !== "auditor") invalid("AUDIT_ROLE_MISMATCH", "auditResponse.role");
  const findings = array(response.findings, "auditResponse.findings").map((finding, index) => {
    const findingPath = `auditResponse.findings[${index}]`;
    const row = object(finding, findingPath);
    assertOnlyKeys(row, ["id", "statement", "severity", "claimIds", "evidenceRefs", "remedy"], findingPath);
    const claimIds = array(row.claimIds, `${findingPath}.claimIds`).map((id, claimIndex) => safeId(id, `${findingPath}.claimIds[${claimIndex}]`));
    const evidenceRefs = array(row.evidenceRefs, `${findingPath}.evidenceRefs`).map((reference, referenceIndex) => text(reference, `${findingPath}.evidenceRefs[${referenceIndex}]`, { max: 512 }));
    if (allowedClaims && claimIds.some((id) => !allowedClaims.has(id))) invalid("UNKNOWN_AUDIT_CLAIM", `${findingPath}.claimIds`);
    if (allowedEvidence && evidenceRefs.some((reference) => !allowedEvidence.has(reference))) invalid("UNKNOWN_AUDIT_EVIDENCE", `${findingPath}.evidenceRefs`);
    return {
      id: safeId(row.id, `${findingPath}.id`),
      statement: text(row.statement, `${findingPath}.statement`, { max: 16_384 }),
      severity: oneOf(row.severity, ["advisory", "material", "fatal"], `${findingPath}.severity`),
      claimIds,
      evidenceRefs,
      remedy: oneOf(row.remedy, AUDIT_REMEDIES, `${findingPath}.remedy`),
    };
  });
  assertUnique(findings.map((finding) => finding.id), "auditResponse.findings", "DUPLICATE_AUDIT_FINDING");
  const verdict = oneOf(response.verdict, AUDIT_VERDICTS, "auditResponse.verdict");
  if (verdict === "FAITHFUL" && findings.some((finding) => finding.severity !== "advisory")) invalid("FAITHFUL_WITH_BLOCKING_FINDING", "auditResponse.findings");
  if (verdict === "NEEDS-REVISION" && !findings.length) invalid("ADVERSE_AUDIT_WITHOUT_FINDING", "auditResponse.findings");
  return deepFreeze({
    schemaVersion: AGENT_COUNCIL_SCHEMA_VERSION,
    runId: expectedRunId,
    seatId: safeId(response.seatId, "auditResponse.seatId"),
    role: "auditor",
    nonce: expectedNonce,
    verdict,
    summary: text(response.summary, "auditResponse.summary", { max: 16_384 }),
    findings,
    omittedDissentIds: array(response.omittedDissentIds, "auditResponse.omittedDissentIds").map((id, index) => safeId(id, `auditResponse.omittedDissentIds[${index}]`)),
  });
}

/** @typedef {{schemaVersion:2,runId:string,role:"chair",nonce:string,responses:object[],replacementSynthesis:string}} AuditRevisionV2 */

export function validateAuditRevision({ expectedRunId, expectedNonce, audit, value, evidenceIds = [] }) {
  const revision = object(value, "auditRevision");
  assertOnlyKeys(revision, ["schemaVersion", "runId", "role", "nonce", "responses", "replacementSynthesis"], "auditRevision");
  if (revision.schemaVersion !== AGENT_COUNCIL_SCHEMA_VERSION || revision.runId !== expectedRunId || revision.nonce !== expectedNonce || revision.role !== "chair") {
    invalid("AUDIT_REVISION_IDENTITY_MISMATCH", "auditRevision");
  }
  const parsedAudit = object(audit, "audit");
  if (parsedAudit.verdict !== "NEEDS-REVISION") invalid("REVISION_WITHOUT_ADVERSE_AUDIT", "audit.verdict");
  const findings = new Map(array(parsedAudit.findings, "audit.findings").map((finding) => [finding.id, finding]));
  const allowedEvidence = new Set(array(evidenceIds, "evidenceIds").map(String));
  const responses = array(revision.responses, "auditRevision.responses").map((entry, index) => {
    const responsePath = `auditRevision.responses[${index}]`;
    const row = object(entry, responsePath);
    assertOnlyKeys(row, ["findingId", "disposition", "rationale", "evidenceRefs"], responsePath);
    const findingId = safeId(row.findingId, `${responsePath}.findingId`);
    if (!findings.has(findingId)) invalid("UNKNOWN_AUDIT_FINDING", `${responsePath}.findingId`);
    const references = array(row.evidenceRefs, `${responsePath}.evidenceRefs`).map((reference, referenceIndex) => text(reference, `${responsePath}.evidenceRefs[${referenceIndex}]`, { max: 512 }));
    if (references.some((reference) => !allowedEvidence.has(reference))) invalid("NEW_EVIDENCE_IN_AUDIT_REVISION", `${responsePath}.evidenceRefs`);
    return {
      findingId,
      disposition: oneOf(row.disposition, ["ACCEPT", "DEFEND"], `${responsePath}.disposition`),
      rationale: text(row.rationale, `${responsePath}.rationale`, { max: 16_384 }),
      evidenceRefs: references,
    };
  });
  assertUnique(responses.map((response) => response.findingId), "auditRevision.responses", "DUPLICATE_AUDIT_REVISION_RESPONSE");
  if (responses.length !== findings.size) invalid("INCOMPLETE_AUDIT_REVISION", "auditRevision.responses");
  if ([...findings.values()].some((finding) => finding.remedy === "NEW_EVIDENCE_REQUIRED")) invalid("AUDIT_REQUIRES_RESTART", "audit.findings");
  return deepFreeze({
    schemaVersion: AGENT_COUNCIL_SCHEMA_VERSION,
    runId: expectedRunId,
    role: "chair",
    nonce: expectedNonce,
    responses,
    replacementSynthesis: text(revision.replacementSynthesis, "auditRevision.replacementSynthesis", { max: 256 * 1024 }),
  });
}

const TRANSITIONS = deepFreeze({
  PREPARED: { AUTHORIZE: "AUTHORIZED", ABORT: "ABORTED" },
  AUTHORIZED: { COMPLETE_R1: "R1_COMPLETE", ABORT: "ABORTED" },
  R1_COMPLETE: { COMPLETE_R2: "R2_FALSIFICATION_COMPLETE", ABORT: "ABORTED" },
  R2_FALSIFICATION_COMPLETE: {
    COMPLETE_R3: "R3_CROSS_EXAM_COMPLETE",
    AUDIT_FAITHFUL: "AUDIT_FAITHFUL",
    AUDIT_NEEDS_REVISION: "AUDIT_NEEDS_REVISION",
    ABORT: "ABORTED",
  },
  R3_CROSS_EXAM_COMPLETE: {
    AUDIT_FAITHFUL: "AUDIT_FAITHFUL",
    AUDIT_NEEDS_REVISION: "AUDIT_NEEDS_REVISION",
    ABORT: "ABORTED",
  },
  AUDIT_NEEDS_REVISION: {
    REVISION_AUDIT_FAITHFUL: "AUDIT_FAITHFUL",
    REVISION_AUDIT_NEEDS_REVISION: "RESTART_REQUIRED",
    RESTART_REQUIRED: "RESTART_REQUIRED",
    ABORT: "ABORTED",
  },
  AUDIT_FAITHFUL: { VERIFY_DURABILITY: "DURABLE", ABORT: "ABORTED" },
  RESTART_REQUIRED: { ABORT: "ABORTED" },
  DURABLE: { START_CLEANUP: "CLEANING" },
  CLEANING: { COMPLETE_CLEANUP: "FINALIZED" },
  FINALIZED: {},
  ABORTED: {},
});

export function nextMilestone(current, event) {
  const currentMilestone = typeof current === "string" ? current : current?.milestone;
  oneOf(currentMilestone, AGENT_COUNCIL_MILESTONES, "current.milestone");
  const eventType = typeof event === "string" ? event : event?.type;
  const next = TRANSITIONS[currentMilestone]?.[eventType];
  if (!next) invalid("INVALID_MILESTONE_TRANSITION", "event", { current: currentMilestone, event: eventType });
  return next;
}

function withoutRole(profile) {
  const copy = dataCopy(profile);
  delete copy.role;
  return copy;
}

function validateResolvedRosterShape(value, preparedAt) {
  const roster = object(value, "state.resolvedRoster");
  assertOnlyKeys(roster, ["schemaVersion", "poolVersion", "host", "externalDecisionSeats", "auditor", "decisionSeats", "panelSpec"], "state.resolvedRoster");
  if (roster.schemaVersion !== AGENT_COUNCIL_SCHEMA_VERSION || roster.poolVersion !== AGENT_COUNCIL_ROSTER_VERSION) {
    invalid("INVALID_RESOLVED_ROSTER_VERSION", "state.resolvedRoster");
  }
  const hasPanelSpec = Object.hasOwn(roster, "panelSpec");
  const panelSpec = hasPanelSpec
    ? normalizePanelSpec({ panelSpec: roster.panelSpec })
    : normalizePanelSpec({ profile: "full" });
  const host = object(roster.host, "state.resolvedRoster.host");
  const externals = array(roster.externalDecisionSeats, "state.resolvedRoster.externalDecisionSeats");
  const auditor = object(roster.auditor, "state.resolvedRoster.auditor");
  if (host.role !== "chair" || externals.length !== panelSpec.externalSeatCount || externals.some((seat) => seat?.role !== "external-decision") || auditor.role !== "auditor") {
    invalid("INVALID_RESOLVED_ROSTER_SHAPE", "state.resolvedRoster");
  }
  const pool = {
    schemaVersion: AGENT_COUNCIL_SCHEMA_VERSION,
    version: AGENT_COUNCIL_ROSTER_VERSION,
    hosts: [withoutRole(host)],
    participants: externals.map(withoutRole),
    auditors: [withoutRole(auditor)],
  };
  const normalized = validateRoster({
    pool,
    hostId: host.id,
    selectedExternalIds: externals.map((seat) => seat.id),
    auditorId: auditor.id,
    panelSpec,
    allowUnresolvedPanelReferences: true,
    availableModelIds: [...externals.map((seat) => seat.model), auditor.model],
    now: preparedAt,
  });
  const compatibilityNormalized = dataCopy(normalized);
  if (!hasPanelSpec) delete compatibilityNormalized.panelSpec;
  if (canonicalJson(compatibilityNormalized) !== canonicalJson(roster)) invalid("RESOLVED_ROSTER_NORMALIZATION_MISMATCH", "state.resolvedRoster");
  return compatibilityNormalized;
}

function validateAuthorization(value, manifest) {
  if (value === null || value === undefined) return null;
  const authorization = object(value, "state.authorization");
  assertOnlyKeys(authorization, ["manifestSha256", "approvedAt"], "state.authorization");
  if (digest(authorization.manifestSha256, "state.authorization.manifestSha256") !== manifest.manifestSha256) {
    invalid("AUTHORIZATION_MANIFEST_MISMATCH", "state.authorization.manifestSha256");
  }
  isoInstant(authorization.approvedAt, "state.authorization.approvedAt");
  return dataCopy(authorization);
}

function validateRepositoryRecord(value, manifest) {
  const repository = object(value, "state.repository");
  assertOnlyKeys(repository, ["root", "headSha", "dirty"], "state.repository");
  const normalized = {
    root: text(repository.root, "state.repository.root", { max: 4_096 }),
    headSha: text(repository.headSha, "state.repository.headSha", { max: 64 }),
    dirty: bool(repository.dirty, "state.repository.dirty"),
  };
  if (normalized.headSha !== manifest.history.headSha || normalized.dirty !== manifest.history.dirty) {
    invalid("REPOSITORY_MANIFEST_MISMATCH", "state.repository");
  }
  return normalized;
}

function validateBriefRecord(value, manifest) {
  const brief = object(value, "state.brief");
  assertOnlyKeys(brief, ["path", "text", "sha256", "bytes"], "state.brief");
  const content = text(brief.text, "state.brief.text", { max: AGENT_COUNCIL_LIMITS.seatResponseBytes });
  const bytes = Buffer.from(content, "utf8");
  const normalized = {
    path: text(brief.path, "state.brief.path", { max: 4_096 }),
    text: content,
    sha256: digest(brief.sha256, "state.brief.sha256"),
    bytes: integer(brief.bytes, "state.brief.bytes", { min: 1, max: AGENT_COUNCIL_LIMITS.seatResponseBytes }),
  };
  const contentSha256 = `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
  if (normalized.bytes !== bytes.length || normalized.sha256 !== contentSha256 || normalized.sha256 !== manifest.brief.sha256 || normalized.bytes !== manifest.brief.bytes) {
    invalid("BRIEF_MANIFEST_MISMATCH", "state.brief");
  }
  return normalized;
}

function validateProbeState(specValues, receiptValues, probesExecuted, manifest) {
  const declarations = new Map(manifest.probeDeclarations.map((declaration) => [declaration.id, declaration]));
  const provisionalCorpusSha256 = canonicalSha256(manifest.included);
  const probeSpecs = array(specValues, "state.probeSpecs").map((value, index) => {
    const original = object(value, `state.probeSpecs[${index}]`);
    if (original.specSha256 === undefined) invalid("MISSING_PROBE_SPEC_DIGEST", `state.probeSpecs[${index}].specSha256`);
    const spec = validateResolvedProbeSpec(original);
    const declaration = declarations.get(spec.id);
    if (!declaration || declaration.gateId !== spec.gateId) invalid("PROBE_DECLARATION_SPEC_MISMATCH", `state.probeSpecs[${index}]`);
    if (spec.corpusSha256 !== provisionalCorpusSha256) invalid("PROBE_SPEC_CORPUS_MISMATCH", `state.probeSpecs[${index}].corpusSha256`);
    return spec;
  });
  assertUnique(probeSpecs.map((spec) => spec.id), "state.probeSpecs", "DUPLICATE_PROBE_SPEC_ID");
  if (probeSpecs.length !== declarations.size) invalid("PROBE_SPEC_CARDINALITY_MISMATCH", "state.probeSpecs");
  const boundCorpusSha256 = canonicalSha256({ files: manifest.included, probeSpecs });
  if (boundCorpusSha256 !== manifest.corpusSha256) invalid("CORPUS_BINDING_MISMATCH", "state.disclosureManifest.corpusSha256");
  const byId = new Map(probeSpecs.map((spec) => [spec.id, spec]));
  const probeReceipts = array(receiptValues, "state.probeReceipts").map((value, index) => {
    const id = value?.payload?.id;
    const spec = byId.get(id);
    if (!spec) invalid("RECEIPT_WITHOUT_PROBE_SPEC", `state.probeReceipts[${index}]`);
    return normalizeProbeReceipt({ input: value, expectedSpecSha256: spec.specSha256, expectedCorpusSha256: spec.corpusSha256 });
  });
  assertUnique(probeReceipts.map((receipt) => receipt.payload.id), "state.probeReceipts", "DUPLICATE_PROBE_RECEIPT_ID");
  const executed = bool(probesExecuted, "state.probesExecuted");
  if (executed && probeReceipts.length !== probeSpecs.length) invalid("INCOMPLETE_PROBE_EXECUTION", "state.probeReceipts");
  return { probeSpecs: probeSpecs.map(dataCopy), probeReceipts: probeReceipts.map(dataCopy), probesExecuted: executed };
}

function validateNonceState(value, roster) {
  const nonces = object(value, "state.nonces");
  assertOnlyKeys(nonces, ["rounds", "audit", "auditRevision"], "state.nonces");
  const seats = roster.decisionSeats.map((seat) => seat.id);
  const roundsInput = object(nonces.rounds, "state.nonces.rounds");
  assertOnlyKeys(roundsInput, ["1", "2", "3"], "state.nonces.rounds");
  const rounds = {};
  const allNonces = [];
  for (const round of [1, 2, 3]) {
    const input = object(roundsInput[String(round)], `state.nonces.rounds.${round}`);
    assertOnlyKeys(input, seats, `state.nonces.rounds.${round}`);
    rounds[String(round)] = {};
    for (const seatId of seats) {
      const nonce = text(input[seatId], `state.nonces.rounds.${round}.${seatId}`, { max: 512 });
      rounds[String(round)][seatId] = nonce;
      allNonces.push(nonce);
    }
  }
  const auditInput = object(nonces.audit, "state.nonces.audit");
  assertOnlyKeys(auditInput, ["1", "2"], "state.nonces.audit");
  const audit = {
    "1": text(auditInput["1"], "state.nonces.audit.1", { max: 512 }),
    "2": text(auditInput["2"], "state.nonces.audit.2", { max: 512 }),
  };
  const auditRevision = text(nonces.auditRevision, "state.nonces.auditRevision", { max: 512 });
  allNonces.push(audit["1"], audit["2"], auditRevision);
  assertUnique(allNonces, "state.nonces", "DUPLICATE_RUN_NONCE");
  return { rounds, audit, auditRevision };
}

function validateAttempt(value, path, expectedRound, externalSeatIds) {
  const attempt = object(value, path);
  assertOnlyKeys(attempt, ["status", "round", "seatId", "attempt", "startedAt", "completedAt", "failureCode", "stopReason"], path);
  const status = oneOf(attempt.status, ATTEMPT_STATUSES, `${path}.status`);
  const round = integer(attempt.round, `${path}.round`, { min: 1, max: 3 });
  if (round !== expectedRound) invalid("ATTEMPT_ROUND_MISMATCH", `${path}.round`);
  const seatId = safeId(attempt.seatId, `${path}.seatId`);
  if (!externalSeatIds.has(seatId)) invalid("ATTEMPT_SEAT_OUTSIDE_ROSTER", `${path}.seatId`);
  const normalized = {
    status,
    round,
    seatId,
    attempt: integer(attempt.attempt, `${path}.attempt`, { min: 1, max: AGENT_COUNCIL_LIMITS.attemptsPerSeatPerRound }),
    startedAt: text(attempt.startedAt, `${path}.startedAt`, { max: 64 }),
  };
  isoInstant(normalized.startedAt, `${path}.startedAt`);
  if (status === "running") {
    if (attempt.completedAt !== undefined || attempt.failureCode !== undefined) invalid("RUNNING_ATTEMPT_WITH_SETTLEMENT", path);
  } else {
    normalized.completedAt = text(attempt.completedAt, `${path}.completedAt`, { max: 64 });
    isoInstant(normalized.completedAt, `${path}.completedAt`);
  }
  if (attempt.failureCode !== undefined) normalized.failureCode = safeId(attempt.failureCode, `${path}.failureCode`);
  // Optional transport label: what the model's own stream said about why it
  // stopped (pi `--mode json` `message_end.message.stopReason`). Descriptive
  // only — bounded plain text, never normalized into an identifier, and never a
  // classification input. The runner classifies from the raw stream value.
  if (attempt.stopReason !== undefined) normalized.stopReason = text(attempt.stopReason, `${path}.stopReason`, { max: STOP_REASON_MAX_CHARS });
  if (status === "completed" && normalized.failureCode !== undefined) invalid("COMPLETED_ATTEMPT_WITH_FAILURE", path);
  if (!["completed", "running"].includes(status) && normalized.failureCode === undefined) invalid("FAILED_ATTEMPT_WITHOUT_CODE", path);
  return normalized;
}

function normalizeRounds(roundValues, context) {
  const externalSeatIds = new Set(context.roster.externalDecisionSeats.map((seat) => seat.id));
  const rounds = array(roundValues, "state.rounds").map((value, index) => {
    const roundPath = `state.rounds[${index}]`;
    const row = object(value, roundPath);
    assertOnlyKeys(row, ["number", "status", "chair", "externals", "attempts"], roundPath);
    const number = integer(row.number, `${roundPath}.number`, { min: 1, max: 3 });
    const status = oneOf(row.status, ROUND_STATUSES, `${roundPath}.status`);
    const chair = row.chair === null || row.chair === undefined
      ? null
      : validateChairResponse({
          expected: { runId: context.runId, round: number, seatId: context.roster.host.id, nonce: context.nonces.rounds[String(number)][context.roster.host.id] },
          response: row.chair,
          disclosure: context.manifest,
          receipts: context.receipts,
        });
    const externals = array(row.externals, `${roundPath}.externals`).map((response, responseIndex) => {
      const seatId = safeId(response?.seatId, `${roundPath}.externals[${responseIndex}].seatId`);
      if (!externalSeatIds.has(seatId)) invalid("ROUND_SEAT_OUTSIDE_ROSTER", `${roundPath}.externals[${responseIndex}].seatId`);
      return validateSeatResponse({
        expected: { runId: context.runId, round: number, seatId, nonce: context.nonces.rounds[String(number)][seatId] },
        response,
        disclosure: context.manifest,
        receipts: context.receipts,
      });
    });
    assertUnique(externals.map((response) => response.seatId), `${roundPath}.externals`, "DUPLICATE_ROUND_SEAT");
    const attempts = array(row.attempts, `${roundPath}.attempts`).map((attempt, attemptIndex) => validateAttempt(attempt, `${roundPath}.attempts[${attemptIndex}]`, number, externalSeatIds));
    assertUnique(attempts.map((attempt) => `${attempt.seatId}:${attempt.attempt}`), `${roundPath}.attempts`, "DUPLICATE_SEAT_ATTEMPT");
    for (const response of externals) {
      if (!attempts.some((attempt) => attempt.seatId === response.seatId && attempt.status === "completed")) invalid("RESPONSE_WITHOUT_COMPLETED_ATTEMPT", `${roundPath}.externals`);
    }
    if (status === "complete") {
      if (!chair) invalid("COMPLETE_ROUND_WITHOUT_CHAIR", roundPath);
      if (externals.length !== context.roster.externalDecisionSeats.length) invalid("COMPLETE_ROUND_EXTERNAL_CARDINALITY", roundPath);
      if (attempts.some((attempt) => attempt.status === "running")) invalid("COMPLETE_ROUND_WITH_RUNNING_ATTEMPT", roundPath);
    } else if (status === "pending" && (chair || externals.length || attempts.length)) {
      invalid("PENDING_ROUND_WITH_EVIDENCE", roundPath);
    } else if (status === "failed") {
      if (!attempts.length || attempts.some((attempt) => attempt.status === "running")) invalid("INVALID_FAILED_ROUND_EVIDENCE", roundPath);
    } else if (status === "running" && !chair) {
      invalid("RUNNING_ROUND_WITHOUT_CHAIR", roundPath);
    }
    return { number, status, chair: chair ? dataCopy(chair) : null, externals: externals.map(dataCopy), attempts };
  });
  assertUnique(rounds.map((round) => round.number), "state.rounds", "DUPLICATE_ROUND_NUMBER");
  return rounds;
}

function validateProcessRecords(values, runId, manifestSha256) {
  const processes = array(values, "state.processes").map((value, index) => {
    const processPath = `state.processes[${index}]`;
    const record = object(value, processPath);
    assertOnlyKeys(record, ["pid", "processGroupId", "processIdentity", "runId", "manifestSha256"], processPath);
    const normalized = {
      pid: integer(record.pid, `${processPath}.pid`, { min: 1 }),
      runId: safeId(record.runId, `${processPath}.runId`),
      manifestSha256: digest(record.manifestSha256, `${processPath}.manifestSha256`),
    };
    if (record.processGroupId !== undefined) normalized.processGroupId = integer(record.processGroupId, `${processPath}.processGroupId`, { min: 1 });
    if (record.processIdentity === null) {
      normalized.processIdentity = null;
    } else {
      const identityPath = `${processPath}.processIdentity`;
      const identity = object(record.processIdentity, identityPath);
      assertOnlyKeys(identity, ["creationId", "executable"], identityPath);
      normalized.processIdentity = {
        creationId: text(identity.creationId, `${identityPath}.creationId`, { max: 512 }),
        executable: text(identity.executable, `${identityPath}.executable`, { max: 4_096 }),
      };
    }
    if (normalized.runId !== runId || normalized.manifestSha256 !== manifestSha256) invalid("PROCESS_RUN_MISMATCH", processPath);
    return normalized;
  });
  assertUnique(processes.map((record) => record.pid), "state.processes", "DUPLICATE_PROCESS_PID");
  return processes;
}

function validateSeatDiffs(values, roster) {
  const seats = new Set(roster.externalDecisionSeats.map((seat) => seat.id));
  return array(values, "state.seatDiffs").map((value, index) => {
    const diffPath = `state.seatDiffs[${index}]`;
    const record = object(value, diffPath);
    assertOnlyKeys(record, ["seatId", "round", "diff"], diffPath);
    const seatId = safeId(record.seatId, `${diffPath}.seatId`);
    if (!seats.has(seatId)) invalid("DIFF_SEAT_OUTSIDE_ROSTER", `${diffPath}.seatId`);
    const diff = array(record.diff, `${diffPath}.diff`).map((entry, entryIndex) => {
      const entryPath = `${diffPath}.diff[${entryIndex}]`;
      const row = object(entry, entryPath);
      const logicalPath = normalizeRelativePosixPath(row.logicalPath);
      if (row.deleted === true) {
        assertOnlyKeys(row, ["logicalPath", "deleted"], entryPath);
        return { logicalPath, deleted: true };
      }
      assertOnlyKeys(row, ["logicalPath", "bytes", "sha256"], entryPath);
      return { logicalPath, bytes: integer(row.bytes, `${entryPath}.bytes`, { min: 0, max: AGENT_COUNCIL_LIMITS.approvedBinaryBytes }), sha256: digest(row.sha256, `${entryPath}.sha256`) };
    });
    assertUnique(diff.map((entry) => entry.logicalPath.toLowerCase()), `${diffPath}.diff`, "DIFF_PATH_COLLISION");
    return { seatId, round: integer(record.round, `${diffPath}.round`, { min: 1, max: 3 }), diff };
  });
}

function validateRoundThree(value, rounds, roster, annotations) {
  const round2 = rounds.find((round) => round.number === 2 && round.status === "complete");
  if (!round2) {
    if (value !== null || annotations.length) invalid("ROUND3_STATE_BEFORE_ROUND2", "state.round3");
    return null;
  }
  const derived = deriveConsequentialDisagreements({ round2: [round2.chair, ...round2.externals], roster, annotations });
  const expected = { ...evaluateRound3({ round2: [round2.chair, ...round2.externals], disagreements: derived, roster }), disagreements: dataCopy(derived) };
  const supplied = object(value, "state.round3");
  assertOnlyKeys(supplied, ["required", "reasons", "disagreements"], "state.round3");
  if (canonicalJson(supplied) !== canonicalJson(expected)) invalid("ROUND3_DERIVATION_MISMATCH", "state.round3");
  return expected;
}

function completeRound(rounds, number) {
  return rounds.some((round) => round.number === number && round.status === "complete");
}

function validateDurability(value, manifestSha256) {
  const record = object(value, "state.durability");
  assertOnlyKeys(record, ["status", "destination", "sha256", "manifestSha256"], "state.durability");
  if (record.status !== "verified") invalid("UNVERIFIED_DURABILITY", "state.durability.status");
  digest(record.sha256, "state.durability.sha256");
  text(record.destination, "state.durability.destination", { max: 4_096 });
  if (digest(record.manifestSha256, "state.durability.manifestSha256") !== manifestSha256) invalid("DURABILITY_MANIFEST_MISMATCH", "state.durability.manifestSha256");
  return dataCopy(record);
}

function validateCleanup(value, manifestSha256) {
  const record = object(value, "state.cleanup");
  assertOnlyKeys(record, ["status", "checkpoints", "manifestSha256"], "state.cleanup");
  if (digest(record.manifestSha256, "state.cleanup.manifestSha256") !== manifestSha256) invalid("CLEANUP_MANIFEST_MISMATCH", "state.cleanup.manifestSha256");
  oneOf(record.status, ["in_progress", "complete"], "state.cleanup.status");
  const checkpoints = object(record.checkpoints, "state.cleanup.checkpoints");
  assertOnlyKeys(checkpoints, ["processes", "filesystem"], "state.cleanup.checkpoints");
  for (const name of ["processes", "filesystem"]) oneOf(checkpoints[name], ["pending", "complete", "not_required", "failed"], `state.cleanup.checkpoints.${name}`);
  const allComplete = Object.values(checkpoints).every((status) => status === "complete" || status === "not_required");
  if ((record.status === "complete") !== allComplete) invalid("CLEANUP_STATUS_MISMATCH", "state.cleanup");
  return dataCopy(record);
}

function validateAuditAttempts(values) {
  const attempts = array(values, "state.auditAttempts").map((value, index) => {
    const attemptPath = `state.auditAttempts[${index}]`;
    const attempt = object(value, attemptPath);
    assertOnlyKeys(attempt, ["cycle", "attempt", "status", "startedAt", "completedAt", "failureCode", "stopReason", "auditInputSha256"], attemptPath);
    const normalized = {
      cycle: integer(attempt.cycle, `${attemptPath}.cycle`, { min: 1, max: AGENT_COUNCIL_LIMITS.synthesisRevisionCycles + 1 }),
      attempt: integer(attempt.attempt, `${attemptPath}.attempt`, { min: 1, max: AGENT_COUNCIL_LIMITS.auditAttemptsPerCycle }),
      status: oneOf(attempt.status, ATTEMPT_STATUSES, `${attemptPath}.status`),
      startedAt: text(attempt.startedAt, `${attemptPath}.startedAt`, { max: 64 }),
      auditInputSha256: digest(attempt.auditInputSha256, `${attemptPath}.auditInputSha256`),
    };
    isoInstant(normalized.startedAt, `${attemptPath}.startedAt`);
    if (normalized.status === "running") {
      if (attempt.completedAt !== undefined || attempt.failureCode !== undefined) invalid("RUNNING_AUDIT_ATTEMPT_WITH_SETTLEMENT", attemptPath);
    } else {
      normalized.completedAt = text(attempt.completedAt, `${attemptPath}.completedAt`, { max: 64 });
      isoInstant(normalized.completedAt, `${attemptPath}.completedAt`);
    }
    if (attempt.failureCode !== undefined) normalized.failureCode = safeId(attempt.failureCode, `${attemptPath}.failureCode`);
    // Same optional transport label as a seat attempt, under the same bound: the
    // auditor rides the same file-writing door, so its stream reports a stop
    // reason too. Descriptive only, never a classification input.
    if (attempt.stopReason !== undefined) normalized.stopReason = text(attempt.stopReason, `${attemptPath}.stopReason`, { max: STOP_REASON_MAX_CHARS });
    if (normalized.status === "completed" && normalized.failureCode !== undefined) invalid("COMPLETED_AUDIT_ATTEMPT_WITH_FAILURE", attemptPath);
    if (!["completed", "running"].includes(normalized.status) && normalized.failureCode === undefined) invalid("FAILED_AUDIT_ATTEMPT_WITHOUT_CODE", attemptPath);
    return normalized;
  });
  assertUnique(attempts.map((attempt) => `${attempt.cycle}:${attempt.attempt}`), "state.auditAttempts", "DUPLICATE_AUDIT_ATTEMPT");
  return attempts;
}

function validateAuditState(state, context) {
  const history = array(state.auditHistory, "state.auditHistory").map((value, index) => parseAuditResponse({
    expectedRunId: context.runId,
    expectedNonce: context.nonces.audit[String(index + 1)],
    expectedSeatId: context.roster.auditor.id,
    expectedClaimIds: context.claimIds,
    expectedEvidenceRefs: context.evidenceRefs,
    value,
  }));
  if (history.length > AGENT_COUNCIL_LIMITS.synthesisRevisionCycles + 1) invalid("AUDIT_HISTORY_LIMIT", "state.auditHistory");
  if (history.length > 1 && history[0].verdict !== "NEEDS-REVISION") invalid("SECOND_AUDIT_WITHOUT_ADVERSE_FIRST", "state.auditHistory");
  if (state.audit !== null && state.audit !== undefined && history.length === 0) invalid("CURRENT_AUDIT_WITHOUT_HISTORY", "state.audit");
  const audit = state.audit === null || state.audit === undefined ? null : parseAuditResponse({
    expectedRunId: context.runId,
    expectedNonce: context.nonces.audit[String(history.length)],
    expectedSeatId: context.roster.auditor.id,
    expectedClaimIds: context.claimIds,
    expectedEvidenceRefs: context.evidenceRefs,
    value: state.audit,
  });
  if (Boolean(audit) !== Boolean(history.length) || (audit && canonicalJson(audit) !== canonicalJson(history.at(-1)))) {
    invalid("CURRENT_AUDIT_HISTORY_MISMATCH", "state.audit");
  }
  let auditRevision = null;
  if (state.auditRevision !== null && state.auditRevision !== undefined) {
    if (!history.length || history[0].verdict !== "NEEDS-REVISION") invalid("REVISION_WITHOUT_ADVERSE_AUDIT", "state.auditRevision");
    auditRevision = validateAuditRevision({
      expectedRunId: context.runId,
      expectedNonce: context.nonces.auditRevision,
      audit: history[0],
      value: state.auditRevision,
      evidenceIds: [
        ...context.receipts.map((receipt) => `receipt:${receipt.payload.id}`),
        ...context.manifest.included.map((entry) => `citation:${entry.logicalPath}`),
      ],
    });
  }
  if (history.length > 1 && !auditRevision) invalid("SECOND_AUDIT_WITHOUT_REVISION", "state.auditRevision");
  return { audit: audit ? dataCopy(audit) : null, auditHistory: history.map(dataCopy), auditRevision: auditRevision ? dataCopy(auditRevision) : null };
}

function validateTimedReason(value, path, allowedReasons) {
  if (value === null || value === undefined) return null;
  const record = object(value, path);
  assertOnlyKeys(record, ["reason", "recordedAt"], path);
  return {
    reason: oneOf(record.reason, allowedReasons, `${path}.reason`),
    recordedAt: (isoInstant(record.recordedAt, `${path}.recordedAt`), record.recordedAt),
  };
}

/** @typedef {{schemaVersion:2,marker:"agent-council",runId:string,milestone:string,disclosureManifest:DisclosureManifestV2,resolvedRoster:ResolvedRosterV2,authorization:object|null,rounds:object[],attempts:object[],probeReceipts:ProbeReceiptV1[],audit:AuditResponseV2|null,auditHistory:AuditResponseV2[],auditRevision:AuditRevisionV2|null,durability:object|null,cleanup:object|null,restart:object|null,abort:object|null}} RunStateV2 */

export function parseRunStateV2(value) {
  const state = object(value, "state");
  assertOnlyKeys(state, [
    "schemaVersion", "marker", "runId", "runFile", "milestone", "createdAt", "updatedAt",
    "repository", "brief", "disclosureManifest", "resolvedRoster", "probeSpecs", "probeReceipts",
    "probesExecuted", "credentialKey", "seatDirectories", "nonces", "authorization",
    "rounds", "attempts", "processes", "seatDiffs", "round3", "disagreementAnnotations",
    "auditAttempts", "audit", "auditHistory", "auditRevision", "synthesis", "durability", "cleanup",
    "restart", "abort",
  ], "state");
  if (state.schemaVersion !== AGENT_COUNCIL_SCHEMA_VERSION || state.marker !== "agent-council") invalid("UNSUPPORTED_RUN_STATE", "state");
  const runId = safeId(state.runId, "state.runId");
  const runFile = text(state.runFile, "state.runFile", { max: 4_096 });
  const createdAtMs = isoInstant(state.createdAt, "state.createdAt");
  const updatedAtMs = isoInstant(state.updatedAt, "state.updatedAt");
  if (updatedAtMs < createdAtMs) invalid("RUN_TIME_REVERSED", "state.updatedAt");
  const milestone = oneOf(state.milestone, AGENT_COUNCIL_MILESTONES, "state.milestone");
  const manifest = validateDisclosureManifest(state.disclosureManifest);
  if (manifest.runId !== runId) invalid("RUN_MANIFEST_ID_MISMATCH", "state.disclosureManifest.runId");
  const roster = validateResolvedRosterShape(state.resolvedRoster, state.createdAt);
  if (canonicalSha256(roster) !== manifest.rosterSha256) invalid("ROSTER_MANIFEST_MISMATCH", "state.disclosureManifest.rosterSha256");
  const repository = validateRepositoryRecord(state.repository, manifest);
  const brief = validateBriefRecord(state.brief, manifest);
  const probeState = validateProbeState(state.probeSpecs, state.probeReceipts, state.probesExecuted, manifest);
  if (state.credentialKey !== "OPENROUTER_API_KEY") invalid("UNSUPPORTED_CREDENTIAL_KEY", "state.credentialKey");
  const seatDirectoriesInput = object(state.seatDirectories, "state.seatDirectories");
  const externalIds = roster.externalDecisionSeats.map((seat) => seat.id);
  assertOnlyKeys(seatDirectoriesInput, externalIds, "state.seatDirectories");
  const seatDirectories = Object.fromEntries(externalIds.map((seatId) => [seatId, text(seatDirectoriesInput[seatId], `state.seatDirectories.${seatId}`, { max: 4_096 })]));
  const nonces = validateNonceState(state.nonces, roster);
  const authorization = validateAuthorization(state.authorization, manifest);
  const rounds = normalizeRounds(state.rounds, { runId, roster, manifest, receipts: probeState.probeReceipts, nonces });
  const flattenedAttempts = rounds.flatMap((round) => round.attempts);
  const externalSeatIds = new Set(roster.externalDecisionSeats.map((seat) => seat.id));
  const topAttempts = array(state.attempts, "state.attempts").map((attempt, index) => {
    const expectedRound = integer(attempt?.round, `state.attempts[${index}].round`, { min: 1, max: 3 });
    return validateAttempt(attempt, `state.attempts[${index}]`, expectedRound, externalSeatIds);
  });
  if (canonicalJson(topAttempts) !== canonicalJson(flattenedAttempts)) invalid("ATTEMPT_LEDGER_MISMATCH", "state.attempts");
  const attempts = flattenedAttempts.map(dataCopy);
  const processes = validateProcessRecords(state.processes, runId, manifest.manifestSha256);
  const seatDiffs = validateSeatDiffs(state.seatDiffs, roster);
  const annotations = array(state.disagreementAnnotations, "state.disagreementAnnotations").map(dataCopy);
  const round3 = validateRoundThree(state.round3, rounds, roster, annotations);
  const auditAttempts = validateAuditAttempts(state.auditAttempts);
  const claimReferenceIndex = buildAuditClaimReferenceIndex(rounds);
  const claimIds = claimReferenceIndex.map((reference) => reference.qualifiedId);
  const evidenceRefs = [
    ...manifest.included.map((entry) => `citation:${entry.logicalPath}`),
    ...probeState.probeReceipts.map((receipt) => `receipt:${receipt.payload.id}`),
    ...seatDiffs.flatMap((diff) => diff.diff.map((entry) => `diff:${diff.seatId}:${diff.round}:${entry.logicalPath}`)),
    ...(round3?.disagreements ?? []).flatMap((entry) => entry.evidenceRefs ?? []),
  ];
  const auditState = validateAuditState(state, { runId, roster, manifest, receipts: probeState.probeReceipts, nonces, claimIds, evidenceRefs });
  const synthesis = state.synthesis === null || state.synthesis === undefined ? null : text(state.synthesis, "state.synthesis", { max: AGENT_COUNCIL_LIMITS.seatResponseBytes });
  const durability = state.durability === null || state.durability === undefined ? null : validateDurability(state.durability, manifest.manifestSha256);
  const cleanup = state.cleanup === null || state.cleanup === undefined ? null : validateCleanup(state.cleanup, manifest.manifestSha256);
  const restart = validateTimedReason(state.restart, "state.restart", ["SECOND_ADVERSE_AUDIT", "AUDIT_REQUIRES_NEW_EVIDENCE"]);
  const abort = validateTimedReason(state.abort, "state.abort", ["OPERATOR_ABORT"]);
  const hasR1 = completeRound(rounds, 1);
  const hasR2 = completeRound(rounds, 2);
  const hasR3 = completeRound(rounds, 3);
  const rank = {
    PREPARED: 0,
    AUTHORIZED: 1,
    R1_COMPLETE: 2,
    R2_FALSIFICATION_COMPLETE: 3,
    R3_CROSS_EXAM_COMPLETE: 4,
    AUDIT_NEEDS_REVISION: 5,
    AUDIT_FAITHFUL: 5,
    RESTART_REQUIRED: 5,
    DURABLE: 6,
    CLEANING: 7,
    FINALIZED: 8,
    ABORTED: -1,
  }[milestone];
  const runningSeatAttempts = attempts.some((attempt) => attempt.status === "running");
  const runningAuditAttempts = auditAttempts.some((attempt) => attempt.status === "running");
  if (["AUDIT_FAITHFUL", "DURABLE", "CLEANING", "FINALIZED", "ABORTED", "RESTART_REQUIRED"].includes(milestone) && (runningSeatAttempts || runningAuditAttempts)) {
    invalid("TERMINAL_WITH_RUNNING_ATTEMPT", "state");
  }
  if (milestone === "AUDIT_FAITHFUL" && processes.length) invalid("AUDIT_FAITHFUL_WITH_PROCESS_OWNERSHIP", "state.processes");
  if (milestone === "FINALIZED" && processes.length) invalid("FINALIZED_WITH_PROCESS_OWNERSHIP", "state.processes");
  if (milestone === "ABORTED" && processes.length) invalid("ABORTED_WITH_PROCESS_OWNERSHIP", "state.processes");
  if (milestone === "CLEANING" && ["complete", "not_required"].includes(cleanup?.checkpoints.processes) && processes.length) {
    invalid("CLEANING_PROCESS_CHECKPOINT_MISMATCH", "state.processes");
  }
  if (milestone === "ABORTED" && (durability || cleanup)) invalid("ABORTED_WITH_DURABILITY_EVIDENCE", "state");
  if (milestone !== "ABORTED") {
    if ((rank >= 1) !== Boolean(authorization)) invalid("MILESTONE_AUTHORIZATION_EVIDENCE", "state.authorization");
    if (rank >= 2 && !probeState.probesExecuted) invalid("ROUND_BEFORE_PROBES_COMPLETE", "state.probesExecuted");
    if ((rank >= 2) !== hasR1) invalid("MILESTONE_R1_EVIDENCE", "state.rounds");
    if ((rank >= 3) !== hasR2) invalid("MILESTONE_R2_EVIDENCE", "state.rounds");
    if (milestone === "R3_CROSS_EXAM_COMPLETE" && !hasR3) invalid("MILESTONE_R3_EVIDENCE", "state.rounds");
    if (rank < 4 && hasR3) invalid("PREMATURE_R3_EVIDENCE", "state.rounds");
    if (rounds.some((round) => round.number === 3) && !round3?.required) invalid("UNREQUIRED_ROUND3_EVIDENCE", "state.rounds");
    if (rank >= 5 && round3?.required && !hasR3) invalid("AUDIT_BEFORE_REQUIRED_ROUND3", "state.rounds");
    const auditMilestone = ["AUDIT_NEEDS_REVISION", "AUDIT_FAITHFUL", "RESTART_REQUIRED", "DURABLE", "CLEANING", "FINALIZED"].includes(milestone);
    if (auditMilestone !== Boolean(auditState.audit)) invalid("MILESTONE_AUDIT_EVIDENCE", "state.audit");
    if (auditMilestone !== Boolean(synthesis)) invalid("MILESTONE_SYNTHESIS_EVIDENCE", "state.synthesis");
    if (auditState.audit) {
      if (milestone === "AUDIT_NEEDS_REVISION" && auditState.audit.verdict !== "NEEDS-REVISION") invalid("AUDIT_VERDICT_MILESTONE_MISMATCH", "state.audit.verdict");
      if (["AUDIT_FAITHFUL", "DURABLE", "CLEANING", "FINALIZED"].includes(milestone) && auditState.audit.verdict !== "FAITHFUL") invalid("AUDIT_VERDICT_MILESTONE_MISMATCH", "state.audit.verdict");
    }
    if ((rank >= 6) !== Boolean(durability)) invalid("MILESTONE_DURABILITY_EVIDENCE", "state.durability");
    if ((rank >= 7) !== Boolean(cleanup)) invalid("MILESTONE_CLEANUP_EVIDENCE", "state.cleanup");
    if (milestone === "CLEANING" && cleanup?.status === "complete") invalid("CLEANING_ALREADY_COMPLETE", "state.cleanup.status");
    if (milestone === "FINALIZED" && cleanup?.status !== "complete") invalid("FINALIZED_WITHOUT_CLEANUP", "state.cleanup.status");
    if (milestone === "PREPARED" && (
      authorization || rounds.length || attempts.length || processes.length || seatDiffs.length
      || probeState.probeReceipts.length || probeState.probesExecuted || round3 || annotations.length
      || auditAttempts.length || auditState.audit || auditState.auditHistory.length || auditState.auditRevision
      || synthesis || durability || cleanup || restart
    )) invalid("PREPARED_WITH_LATER_EVIDENCE", "state");
    const completedAuditAttempts = auditAttempts.filter((attempt) => attempt.status === "completed");
    const pendingAuditSettlement = completedAuditAttempts.length === auditState.auditHistory.length + 1
      && ["R2_FALSIFICATION_COMPLETE", "R3_CROSS_EXAM_COMPLETE", "AUDIT_NEEDS_REVISION"].includes(milestone)
      && completedAuditAttempts.some((attempt) => attempt.cycle === auditState.auditHistory.length + 1);
    if (completedAuditAttempts.length !== auditState.auditHistory.length && !pendingAuditSettlement) invalid("AUDIT_ATTEMPT_HISTORY_MISMATCH", "state.auditAttempts");
    for (let index = 0; index < auditState.auditHistory.length; index += 1) {
      if (!completedAuditAttempts.some((attempt) => attempt.cycle === index + 1)) invalid("AUDIT_HISTORY_WITHOUT_COMPLETED_ATTEMPT", "state.auditHistory");
    }
    if (milestone === "RESTART_REQUIRED") {
      if (auditState.audit?.verdict !== "NEEDS-REVISION") invalid("RESTART_WITHOUT_ADVERSE_AUDIT", "state.audit");
      if (restart?.reason === "SECOND_ADVERSE_AUDIT" && (auditState.auditHistory.length !== 2 || !auditState.auditRevision)) invalid("SECOND_ADVERSE_RESTART_EVIDENCE", "state");
      if (restart?.reason === "AUDIT_REQUIRES_NEW_EVIDENCE" && !auditState.audit.findings.some((finding) => finding.remedy === "NEW_EVIDENCE_REQUIRED")) invalid("NEW_EVIDENCE_RESTART_EVIDENCE", "state.audit.findings");
    }
  } else if (!abort) {
    invalid("ABORTED_WITHOUT_RECORD", "state.abort");
  }
  if ((milestone === "RESTART_REQUIRED") !== Boolean(restart)) invalid("RESTART_REASON_MILESTONE_MISMATCH", "state.restart");
  if ((milestone === "ABORTED") !== Boolean(abort)) invalid("ABORT_REASON_MILESTONE_MISMATCH", "state.abort");
  return deepFreeze({
    schemaVersion: AGENT_COUNCIL_SCHEMA_VERSION,
    marker: "agent-council",
    runId,
    runFile,
    milestone,
    createdAt: state.createdAt,
    updatedAt: state.updatedAt,
    repository,
    brief,
    disclosureManifest: manifest,
    resolvedRoster: roster,
    probeSpecs: probeState.probeSpecs,
    probeReceipts: probeState.probeReceipts,
    probesExecuted: probeState.probesExecuted,
    credentialKey: "OPENROUTER_API_KEY",
    seatDirectories,
    nonces,
    authorization,
    rounds,
    attempts,
    processes,
    seatDiffs,
    round3,
    disagreementAnnotations: annotations,
    auditAttempts,
    audit: auditState.audit,
    auditHistory: auditState.auditHistory,
    auditRevision: auditState.auditRevision,
    synthesis,
    durability,
    cleanup,
    restart,
    abort,
  });
}

/** @typedef {{pid:number,processGroupId?:number,processIdentity:{creationId:string,executable:string}|null,runId:string,manifestSha256:string}} ProcessOwnershipV2 */
/** @typedef {{schemaVersion:1,marker:"agent-council-process-recovery-owner",runFile:string,runId:string,manifestSha256:string}} ProcessRecoveryOwnerV1 */
/** @typedef {{schemaVersion:1,marker:"agent-council-process-recovery",runFile:string,runDirectory:string,runId:string,manifestSha256:string,pid:number,processGroupId?:number,processIdentity:{creationId:string,executable:string}|null}} ProcessRecoveryRecordV1 */
/** @typedef {{status:"verified",destination:string,sha256:string,manifestSha256:string}} DurabilityRecordV2 */
/** @typedef {{status:"in_progress"|"complete",checkpoints:{processes:"pending"|"complete"|"not_required"|"failed",filesystem:"pending"|"complete"|"not_required"|"failed"},manifestSha256:string}} CleanupRecordV2 */

export function assessTerminationProof(expected, observed) {
  if (!isPlainObject(expected) || !Number.isSafeInteger(expected.pid) || expected.pid <= 0 || !isPlainObject(observed) || observed.complete !== true) {
    return deepFreeze({ kind: "survivors", survivors: [Number.isSafeInteger(expected?.pid) ? expected.pid : -1] });
  }
  if (observed.rootPid !== expected.pid || (expected.processGroupId !== undefined && observed.processGroupId !== expected.processGroupId)) {
    return deepFreeze({ kind: "survivors", survivors: [expected.pid] });
  }
  const handleOwned = observed.handleOwned === true;
  const processAbsent = observed.processAbsent === true;
  const identityVerified = processAbsent || expected.processIdentity !== null
    && isPlainObject(expected.processIdentity)
    && observed.identityVerified === true;
  if (!handleOwned && !identityVerified) return deepFreeze({ kind: "survivors", survivors: [expected.pid] });
  const owned = new Set([expected.pid, ...array(observed.descendantPids ?? [], "observed.descendantPids").filter(Number.isSafeInteger)]);
  const alive = array(observed.alivePids ?? [], "observed.alivePids").filter((pid) => Number.isSafeInteger(pid) && owned.has(pid));
  if (alive.length) return deepFreeze({ kind: "survivors", survivors: [...new Set(alive)].sort((left, right) => left - right) });
  return deepFreeze({
    kind: "terminated",
    proof: {
      rootPid: expected.pid,
      processGroupId: expected.processGroupId ?? null,
      processIdentity: expected.processIdentity ?? null,
      identityVerified,
      handleOwned,
      processAbsent,
      observedPids: [...owned].sort((left, right) => left - right),
      runId: expected.runId,
    },
  });
}

const CHILD_ENV_ALLOWLIST = new Set([
  "PATH", "PATHEXT", "SystemRoot", "WINDIR", "ComSpec", "TEMP", "TMP", "TMPDIR",
  "LANG", "LC_ALL", "LC_CTYPE", "TERM", "COLORTERM", "NO_COLOR", "FORCE_COLOR", "CI",
]);

/**
 * Child environment for an external adapter: the fixed allowlist plus at most
 * one named credential. There is no override channel — an `overrides` key is a
 * rejected smuggling attempt, never a partially honoured request.
 */
export function filterEnvironment(source, adapterSecrets = {}) {
  const environment = object(source, "sourceEnvironment");
  const policy = object(adapterSecrets, "adapterSecrets");
  if (Object.hasOwn(policy, "overrides")) invalid("UNSAFE_ENVIRONMENT_OVERRIDE", "adapterSecrets.overrides");
  const output = {};
  for (const key of CHILD_ENV_ALLOWLIST) if (typeof environment[key] === "string") output[key] = environment[key];
  const credentialKey = policy.credentialKey;
  if (credentialKey !== undefined) {
    if (typeof credentialKey !== "string" || !/^[A-Z][A-Z0-9_]{1,127}$/.test(credentialKey)) invalid("INVALID_ADAPTER_CREDENTIAL_KEY", "adapterSecrets.credentialKey");
    const credentialValue = policy.credentialValue ?? environment[credentialKey];
    if (typeof credentialValue !== "string" || !credentialValue) invalid("MISSING_ADAPTER_CREDENTIAL", "adapterSecrets.credentialValue");
    output[credentialKey] = credentialValue;
  }
  return deepFreeze({ ...output });
}

function absoluteExecutable(value, path) {
  text(value, path, { max: 4_096 });
  if (!(value.startsWith("/") || WINDOWS_ABSOLUTE_PATTERN.test(value))) invalid("EXECUTABLE_NOT_ABSOLUTE", path);
  return value;
}

/** @typedef {{schemaVersion:1,id:string,gateId:string}} ProbeDeclarationV1 */
/** @typedef {{schemaVersion:1,id:string,gateId:string,platform:string,executable:string,argv:string[],shell:false,nodeExecutable:string,nodeVersion:string,executableSha256:string,npmCliPath?:string,npmCliSha256?:string,npmVersion?:string,launcherPath:string,launcherSha256:string,corpusSha256:string,specSha256:string}} ResolvedProbeSpecV1 */

export function validateResolvedProbeSpec(input) {
  const args = input?.spec ? input : { spec: input };
  const spec = object(args.spec, "probeSpec");
  const gateId = safeId(spec.gateId, "probeSpec.gateId");
  const gate = BROKER_GATE_CATALOG[gateId];
  if (!gate) invalid("UNKNOWN_BROKER_GATE", "probeSpec.gateId");
  assertOnlyKeys(spec, gate.kind === "npm"
    ? ["schemaVersion", "id", "gateId", "platform", "executable", "argv", "shell", "nodeExecutable", "nodeVersion", "executableSha256", "npmCliPath", "npmCliSha256", "npmVersion", "launcherPath", "launcherSha256", "corpusSha256", "specSha256"]
    : ["schemaVersion", "id", "gateId", "platform", "executable", "argv", "shell", "nodeExecutable", "nodeVersion", "executableSha256", "launcherPath", "launcherSha256", "corpusSha256", "specSha256"], "probeSpec");
  if (spec.schemaVersion !== PROBE_SCHEMA_VERSION || spec.shell !== false) invalid("UNSAFE_PROBE_EXECUTION_MODE", "probeSpec");
  const platform = oneOf(spec.platform, ["win32", "linux", "darwin"], "probeSpec.platform");
  const nodeExecutable = absoluteExecutable(spec.nodeExecutable, "probeSpec.nodeExecutable");
  const executable = absoluteExecutable(spec.executable, "probeSpec.executable");
  if (executable !== nodeExecutable) invalid("PROBE_EXECUTABLE_NOT_NODE", "probeSpec.executable");
  const argv = array(spec.argv, "probeSpec.argv").map((entry, index) => text(entry, `probeSpec.argv[${index}]`, { max: 4_096 }));
  let expectedArgv;
  const normalized = {
    schemaVersion: PROBE_SCHEMA_VERSION,
    id: safeId(spec.id, "probeSpec.id"),
    gateId,
    platform,
    executable,
    argv,
    shell: false,
    nodeExecutable,
    nodeVersion: text(spec.nodeVersion, "probeSpec.nodeVersion", { max: 64 }),
    executableSha256: digest(spec.executableSha256, "probeSpec.executableSha256"),
    launcherPath: absoluteExecutable(spec.launcherPath, "probeSpec.launcherPath"),
    launcherSha256: digest(spec.launcherSha256, "probeSpec.launcherSha256"),
    corpusSha256: digest(spec.corpusSha256, "probeSpec.corpusSha256"),
  };
  if (gate.kind === "npm") {
    const npmCliPath = absoluteExecutable(spec.npmCliPath, "probeSpec.npmCliPath");
    expectedArgv = [npmCliPath, ...gate.argv];
    normalized.npmCliPath = npmCliPath;
    normalized.npmCliSha256 = digest(spec.npmCliSha256, "probeSpec.npmCliSha256");
    normalized.npmVersion = text(spec.npmVersion, "probeSpec.npmVersion", { max: 64 });
  } else {
    expectedArgv = [...gate.argv];
    if (spec.npmCliPath !== undefined || spec.npmCliSha256 !== undefined || spec.npmVersion !== undefined) invalid("NODE_GATE_WITH_NPM_METADATA", "probeSpec");
  }
  if (canonicalJson(argv) !== canonicalJson(expectedArgv)) invalid("PROBE_ARGV_DRIFT", "probeSpec.argv");
  const specSha256 = canonicalSha256(normalized);
  if (spec.specSha256 !== undefined && digest(spec.specSha256, "probeSpec.specSha256") !== specSha256) invalid("PROBE_SPEC_DIGEST_MISMATCH", "probeSpec.specSha256");
  const result = deepFreeze({ ...normalized, specSha256 });
  if (args.expected && canonicalJson(result) !== canonicalJson(args.expected)) invalid("RUNTIME_PROBE_SPEC_DRIFT", "probeSpec");
  return result;
}

/** @typedef {{schemaVersion:1,id:string,specSha256:string,corpusSha256:string,status:string,exitCode:number|null,durationMs:number,outputSha256:string|null,disclosedOutput:string|null,truncated:boolean}} ProbeReceiptPayloadV1 */
/** @typedef {{payload:ProbeReceiptPayloadV1,receiptSha256:string}} ProbeReceiptV1 */

export function normalizeProbeReceipt(input) {
  const args = input?.input || input?.receipt ? input : { input };
  const receipt = object(args.input ?? args.receipt, "probeReceipt");
  const payload = object(receipt.payload, "probeReceipt.payload");
  assertOnlyKeys(payload, ["schemaVersion", "id", "specSha256", "corpusSha256", "status", "exitCode", "durationMs", "outputSha256", "disclosedOutput", "truncated"], "probeReceipt.payload");
  if (payload.schemaVersion !== PROBE_SCHEMA_VERSION) invalid("UNSUPPORTED_PROBE_RECEIPT_VERSION", "probeReceipt.payload.schemaVersion");
  const normalized = {
    schemaVersion: PROBE_SCHEMA_VERSION,
    id: safeId(payload.id, "probeReceipt.payload.id"),
    specSha256: digest(payload.specSha256, "probeReceipt.payload.specSha256"),
    corpusSha256: digest(payload.corpusSha256, "probeReceipt.payload.corpusSha256"),
    status: oneOf(payload.status, PROBE_STATUSES, "probeReceipt.payload.status"),
    exitCode: payload.exitCode === null ? null : integer(payload.exitCode, "probeReceipt.payload.exitCode", { min: -2_147_483_648, max: 2_147_483_647 }),
    durationMs: integer(payload.durationMs, "probeReceipt.payload.durationMs", { min: 0, max: AGENT_COUNCIL_LIMITS.probeTimeoutMs + 60_000 }),
    outputSha256: payload.outputSha256 === null ? null : digest(payload.outputSha256, "probeReceipt.payload.outputSha256"),
    disclosedOutput: payload.disclosedOutput === null ? null : text(payload.disclosedOutput, "probeReceipt.payload.disclosedOutput", { allowEmpty: true, max: AGENT_COUNCIL_LIMITS.probeOutputBytes }),
    truncated: bool(payload.truncated, "probeReceipt.payload.truncated"),
  };
  if (args.expectedSpecSha256 && normalized.specSha256 !== args.expectedSpecSha256) invalid("PROBE_RECEIPT_SPEC_MISMATCH", "probeReceipt.payload.specSha256");
  if (args.expectedCorpusSha256 && normalized.corpusSha256 !== args.expectedCorpusSha256) invalid("PROBE_RECEIPT_CORPUS_MISMATCH", "probeReceipt.payload.corpusSha256");
  switch (normalized.status) {
    case "PASSED":
      if (normalized.exitCode !== 0 || normalized.outputSha256 === null) invalid("INVALID_PASSED_RECEIPT", "probeReceipt.payload");
      break;
    case "FAILED":
      if (normalized.exitCode === null || normalized.exitCode === 0 || normalized.outputSha256 === null) invalid("INVALID_FAILED_RECEIPT", "probeReceipt.payload");
      break;
    case "TIMED_OUT":
      if (normalized.exitCode !== null || normalized.durationMs < AGENT_COUNCIL_LIMITS.probeTimeoutMs || normalized.truncated) invalid("INVALID_TIMEOUT_RECEIPT", "probeReceipt.payload");
      break;
    case "OUTPUT_LIMIT":
      if (!normalized.truncated || normalized.outputSha256 === null) invalid("INVALID_OUTPUT_LIMIT_RECEIPT", "probeReceipt.payload");
      break;
    case "SPAWN_FAILED":
      if (normalized.exitCode !== null || normalized.outputSha256 !== null || normalized.disclosedOutput !== null || normalized.truncated) invalid("INVALID_SPAWN_FAILURE_RECEIPT", "probeReceipt.payload");
      break;
    case "REJECTED_SECRET":
      if (normalized.disclosedOutput !== null || normalized.outputSha256 !== null) invalid("SECRET_OUTPUT_DISCLOSED", "probeReceipt.payload");
      break;
  }
  const receiptSha256 = canonicalSha256(normalized);
  if (digest(receipt.receiptSha256, "probeReceipt.receiptSha256") !== receiptSha256) invalid("PROBE_RECEIPT_DIGEST_MISMATCH", "probeReceipt.receiptSha256");
  return deepFreeze({ payload: normalized, receiptSha256 });
}

/** @typedef {{status:string,round:1|2|3,seatId:string,attempt:number,startedAt:string,completedAt?:string,failureCode?:string,stopReason?:string}} AttemptRecordV2 */
/** @typedef {{cycle:number,attempt:number,status:string,startedAt:string,completedAt?:string,failureCode?:string,stopReason?:string,auditInputSha256:string}} AuditAttemptRecordV2 */
/** @typedef {{number:1|2|3,status:string,chair:ChairResponseV2|null,externals:SeatResponseV2[],attempts:AttemptRecordV2[]}} RoundRecordV2 */
/** @typedef {{schemaVersion:2,runId:string,brief:object,disclosureManifest:DisclosureManifestV2,resolvedRoster:ResolvedRosterV2,authorization:object,probeSpecs:object[],probeReceipts:ProbeReceiptV1[],attempts:AttemptRecordV2[],rounds:RoundRecordV2[],seatDiffs:object[],round3:object|null,disagreementAnnotations:object[],auditAttempts:AuditAttemptRecordV2[],auditHistory:AuditResponseV2[],auditRevision:AuditRevisionV2|null,claimReferenceIndex:{qualifiedId:string,round:number,seatId:string,claimId:string}[],chair:ChairResponseV2,synthesis:string}} AuditBundleV2 */
/** @typedef {{hostEnvironment:object,tempRoot:string,nodeExecutable:string,nodeVersion:string,platform:string,now:Function,newRunId:Function,newNonce:Function,readFile:Function,writeFile:Function,removeFile:Function,writeFileAtomic:Function,writeFileAtomicExact:Function,exists:Function,stat:Function,lstat:Function,realpath:Function,readDirectory:Function,mkdir:Function,mkdirExact:Function,copyTree:Function,removeTree:Function,removeEmptyDirectory:Function,walkFiles:Function,rename:Function,chmod:Function,listRepositoryFiles:Function,resolveRepositoryRoot:Function,repositoryHead:Function,repositoryDirty:Function,readHistory:Function,initializeSyntheticGit:Function,seatDiff:Function,validateAuditResponse:Function,checkExternalNetwork:Function,preflightPi:Function,preflightTransports:Function,preflightSelectedNativeModels:Function,resolveNpm:Function,invokePiSeat:Function,invokeSeat:Function,invokeSeatWritesResponseFile?:boolean,terminateProcessTree:Function,runProbe:Function,processAdapter:object}} AgentCouncilIo */

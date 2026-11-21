// Topping Out Site Awareness (read-only, zero LLM, zero dependencies):
// - Parses fixed 5-line `f-status` footers and `YOUR CALL` cards
// - Classifies Foreman <-> managed Builder pairs deterministically by shared Orca tabId
// - Reads `foreman/projects/*/BOARD.json` and `foreman/jobs/JOB_*.md` from live session repos
// - Builds a unified Owner's Word queue across live Foremen and project boards
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { basename, join, resolve } from "node:path";
import { SessionSummary } from "./orca.js";

export type SessionRole = "foreman" | "builder" | "standalone";

export interface ParsedJStatus {
  where: string;
  done: string;
  state: string;
  owed: string;
  next: string;
  hasYourCall: boolean;
  hasRealOwed: boolean;
}

export interface SessionTopology {
  sessionId: string;
  role: SessionRole;
  pairedForemanId: string | null;
  pairedForemanTitle: string | null;
  pairedBuilderId: string | null;
  pairedBuilderTitle: string | null;
  jStatus: ParsedJStatus | null;
}

export interface BoardJobEntry {
  id: string;
  title: string;
  kind: string;
  state: string;
  summary: string;
  decision?: string;
}

export interface BoardSummary {
  repoRoot: string;
  repoName: string;
  slug: string;
  title: string;
  updated: string;
  toppedOut: boolean;
  nextLabel: string | null;
  nextJobIds: string[];
  nextByLane: Record<string, string | null> | null;
  headOutcome: string;
  standfirst: string;
  owed: string[];
  alerts: string[];
  runningJobs: BoardJobEntry[];
  nextJobs: BoardJobEntry[];
  openDecisions: BoardJobEntry[];
  counts: {
    total: number;
    done: number;
    inProgress: number;
    open: number;
    decision: number;
  };
}

export interface ActiveJobSummary {
  file: string;
  title: string;
  project: string;
  jNumber: string;
  boardId: string;
  size: string;
  branch: string;
  started: string;
  completedPhases: string[];
  pendingPhases: string[];
}

export interface OwnerQueueItem {
  source: "foreman" | "board_owed" | "board_decision";
  title: string;
  detail: string;
  sessionId?: string;
  sessionTitle?: string;
  repo?: string;
  boardSlug?: string;
  jobId?: string;
}

const EMPTY_OWED_RE =
  /^(?:none|nothing|nothing owed|nothing from you|no|n\/a|nil|-+|\.+|\(none\))\.?$/i;

export function isNonEmptyOwed(owed: string): boolean {
  const cleaned = owed.trim().replace(/^[*_`]+|[*_`]+$/g, "").trim();
  if (!cleaned) return false;
  return !EMPTY_OWED_RE.test(cleaned);
}

// Strict card-marker match so ordinary prose like "that's your call" never false-triggers a YOUR CALL card.
const YOUR_CALL_CARD_RE =
  /🚧\s*YOUR CALL|(?:^|\r?\n)\s*(?:\*\*|#+)?\s*YOUR CALL(?:\s*[·:\-]|\s*$)|\bYOUR CALL\s*[·:]/;

/**
 * Parse Topping Out's 5-line `f-status` footer and `YOUR CALL` markers from a message or screen tail.
 */
export function parseJStatus(text: string): ParsedJStatus | null {
  if (!text) return null;
  const hasYourCall = YOUR_CALL_CARD_RE.test(text);

  // Extract the last occurrence of each f-status field line
  const matchLast = (key: string): string => {
    const re = new RegExp(`(?:^|\\r?\\n)\\s*${key}\\s*:\\s*(.+)`, "gi");
    let found = "";
    let m: RegExpExecArray | null;
    while ((m = re.exec(text)) !== null) {
      found = m[1].trim();
    }
    return found;
  };

  const where = matchLast("where");
  const done = matchLast("done");
  const state = matchLast("state");
  const owed = matchLast("owed");
  const next = matchLast("next");

  const fieldCount = [where, done, state, owed, next].filter(Boolean).length;
  if (fieldCount < 2 && !hasYourCall) {
    return null;
  }

  return {
    where,
    done,
    state,
    owed,
    next,
    hasYourCall,
    hasRealOwed: hasYourCall || isNonEmptyOwed(owed),
  };
}

const FOREMAN_TITLE_RE =
  /\b(?:head\s+\d+|opener(?:-job-\d+)?|foreman|autonomous\s+run|night\s+shift)\b/i;
const BUILDER_HINT_RE = /(?:^|\s|[-_/])(?:j\d+-|builder|pi\b|π\b)/i;

function foremanScore(s: SessionSummary, jStatus: ParsedJStatus | null): number {
  let score = 0;
  if (jStatus) score += 5;
  if (FOREMAN_TITLE_RE.test(s.title)) score += 4;
  if (s.agent.toLowerCase() === "claude") score += 2;
  if (s.branch === "main" || s.workspace === "main") score += 1;
  if (s.agent.toLowerCase() === "pi") score -= 3;
  if (BUILDER_HINT_RE.test(s.title) && !FOREMAN_TITLE_RE.test(s.title)) score -= 2;
  return score;
}

/**
 * Deterministically classify sessions into foreman / managed builder / standalone.
 * Per skills/orca-pi-connect/SKILL.md, a managed builder runs in a split pane inside the
 * same Orca tabId as its Foreman.
 */
export function classifyTopology(sessions: SessionSummary[]): Map<string, SessionTopology> {
  const result = new Map<string, SessionTopology>();
  const jStatusById = new Map<string, ParsedJStatus | null>();

  for (const s of sessions) {
    const js = parseJStatus(s.preview);
    jStatusById.set(s.id, js);
    result.set(s.id, {
      sessionId: s.id,
      role: "standalone",
      pairedForemanId: null,
      pairedForemanTitle: null,
      pairedBuilderId: null,
      pairedBuilderTitle: null,
      jStatus: js,
    });
  }

  // Group sessions by shared Orca tabId
  const byTab = new Map<string, SessionSummary[]>();
  for (const s of sessions) {
    const tab = (s.tabId || "").trim();
    if (!tab) continue;
    const list = byTab.get(tab) ?? [];
    list.push(s);
    byTab.set(tab, list);
  }

  for (const group of byTab.values()) {
    if (group.length < 2) continue;

    // Score candidates in the tab to pick the owning Foreman
    const ranked = group
      .map((s) => ({ session: s, score: foremanScore(s, jStatusById.get(s.id) ?? null) }))
      .sort((a, b) => b.score - a.score);

    const top = ranked[0];
    const second = ranked[1];
    // Require a clear Foreman signal (positive score and strictly ahead of the sibling)
    if (top.score >= 2 && top.score > second.score) {
      const foreman = top.session;
      const foremanTopo = result.get(foreman.id)!;
      foremanTopo.role = "foreman";

      // Prefer a connected/live sibling as the primary paired builder
      const builders = ranked
        .slice(1)
        .map((r) => r.session)
        .sort((a, b) => Number(b.connected) - Number(a.connected));

      for (const b of builders) {
        const bTopo = result.get(b.id)!;
        bTopo.role = "builder";
        bTopo.pairedForemanId = foreman.id;
        bTopo.pairedForemanTitle = foreman.title;
        if (!foremanTopo.pairedBuilderId) {
          foremanTopo.pairedBuilderId = b.id;
          foremanTopo.pairedBuilderTitle = b.title;
        }
      }
    }
  }

  // Mark standalone single-pane Foremen (e.g. between jobs or before splitting a builder pane)
  for (const s of sessions) {
    const topo = result.get(s.id)!;
    if (topo.role !== "standalone") continue;
    if (topo.jStatus || FOREMAN_TITLE_RE.test(s.title)) {
      topo.role = "foreman";
    }
  }

  return result;
}

export function extractRepoRoots(sessions: SessionSummary[]): string[] {
  const seen = new Set<string>();
  const roots: string[] = [];
  for (const s of sessions) {
    const p = (s.worktreePath || "").trim();
    if (!p) continue;
    const norm = resolve(p);
    const key = process.platform === "win32" ? norm.toLowerCase() : norm;
    if (seen.has(key)) continue;
    if (existsSync(norm)) {
      seen.add(key);
      roots.push(norm);
    }
  }
  return roots;
}

interface RawBoardJson {
  schema?: number;
  updated?: string;
  next?: string | Record<string, string | null> | null;
  topped_out?: unknown;
  project?: {
    slug?: string;
    title?: string;
    lanes?: string[];
    head?: { outcome?: string; test?: string };
    owed?: string[];
    alerts?: string[];
    standfirst?: string;
  };
  jobs?: Array<{
    id?: string;
    title?: string;
    kind?: string;
    state?: string;
    summary?: string;
    decision?: string;
  }>;
}

function parseNextField(rawNext: RawBoardJson["next"]): {
  nextLabel: string | null;
  nextJobIds: string[];
  nextByLane: Record<string, string | null> | null;
} {
  if (typeof rawNext === "string") {
    const id = rawNext.trim();
    return {
      nextLabel: id || null,
      nextJobIds: id ? [id] : [],
      nextByLane: null,
    };
  }
  if (rawNext && typeof rawNext === "object" && !Array.isArray(rawNext)) {
    const byLane: Record<string, string | null> = {};
    const ids: string[] = [];
    const parts: string[] = [];
    for (const [lane, val] of Object.entries(rawNext)) {
      const id = typeof val === "string" && val.trim() ? val.trim() : null;
      byLane[lane] = id;
      if (id) {
        ids.push(id);
        parts.push(`Lane ${lane}: ${id}`);
      } else {
        parts.push(`Lane ${lane}: none`);
      }
    }
    return {
      nextLabel: parts.length ? parts.join(", ") : null,
      nextJobIds: ids,
      nextByLane: byLane,
    };
  }
  return { nextLabel: null, nextJobIds: [], nextByLane: null };
}

/**
 * Discover and parse all `foreman/projects/<slug>/BOARD.json` files across live repo roots.
 * Returns active (non-topped-out) boards sorted before frozen/topped-out historical boards.
 * Keeps only exact stored states (ready/blocked are derived by render_board.py from needs/gates).
 */
export function discoverBoards(repoRoots: string[]): BoardSummary[] {
  const boards: BoardSummary[] = [];
  const seenFiles = new Set<string>();

  for (const root of repoRoots) {
    const projectsDir = join(root, "foreman", "projects");
    if (!existsSync(projectsDir)) continue;

    let entries: string[];
    try {
      entries = readdirSync(projectsDir);
    } catch {
      continue;
    }

    for (const slug of entries) {
      const boardPath = join(projectsDir, slug, "BOARD.json");
      const key = process.platform === "win32" ? boardPath.toLowerCase() : boardPath;
      if (seenFiles.has(key) || !existsSync(boardPath)) continue;
      seenFiles.add(key);

      let parsed: RawBoardJson;
      try {
        parsed = JSON.parse(readFileSync(boardPath, "utf8")) as RawBoardJson;
      } catch {
        continue;
      }

      const jobs: BoardJobEntry[] = (parsed.jobs ?? []).map((j) => ({
        id: String(j.id || ""),
        title: String(j.title || ""),
        kind: String(j.kind || "build"),
        state: String(j.state || "open").toLowerCase(),
        summary: String(j.summary || ""),
        decision: j.decision ? String(j.decision) : undefined,
      }));

      const doneStates = new Set(["merged", "resolved", "done", "closed", "dropped"]);
      const runningStates = new Set(["running", "in-progress", "in_progress", "active"]);

      const toppedOut = Boolean(parsed.topped_out);
      const runningJobs = jobs.filter((j) => runningStates.has(j.state));
      const { nextLabel, nextJobIds, nextByLane } = parseNextField(parsed.next);
      const nextIdSet = new Set(nextJobIds);
      const nextJobs = jobs.filter((j) => nextIdSet.has(j.id));
      const openDecisions = jobs.filter(
        (j) => (j.kind === "decision" || j.state === "decision") && !doneStates.has(j.state)
      );

      const doneCount = jobs.filter((j) => doneStates.has(j.state)).length;
      const decisionCount = openDecisions.length;
      const openCount = jobs.filter(
        (j) => !doneStates.has(j.state) && !runningStates.has(j.state) && j.state !== "decision"
      ).length;

      boards.push({
        repoRoot: root,
        repoName: basename(root),
        slug: parsed.project?.slug || slug,
        title: parsed.project?.title || slug,
        updated: parsed.updated || "",
        toppedOut,
        nextLabel,
        nextJobIds,
        nextByLane,
        headOutcome: parsed.project?.head?.outcome || "",
        standfirst: parsed.project?.standfirst || "",
        owed: Array.isArray(parsed.project?.owed) ? parsed.project!.owed.map(String) : [],
        alerts: Array.isArray(parsed.project?.alerts) ? parsed.project!.alerts.map(String) : [],
        runningJobs,
        nextJobs,
        openDecisions,
        counts: {
          total: jobs.length,
          done: doneCount,
          inProgress: runningJobs.length,
          open: openCount,
          decision: decisionCount,
        },
      });
    }
  }

  boards.sort((a, b) => Number(a.toppedOut) - Number(b.toppedOut));
  return boards;
}

/**
 * Read active `foreman/jobs/JOB_*.md` headers from a repo root (newest first).
 */
export function readActiveJobs(repoRoot: string, maxJobs = 5): ActiveJobSummary[] {
  const jobsDir = join(repoRoot, "foreman", "jobs");
  if (!existsSync(jobsDir)) return [];

  let files: Array<{ name: string; full: string; mtime: number }> = [];
  try {
    files = readdirSync(jobsDir)
      .filter((f) => /^JOB_.*\.md$/i.test(f))
      .map((name) => {
        const full = join(jobsDir, name);
        let mtime = 0;
        try {
          mtime = statSync(full).mtimeMs;
        } catch {
          mtime = 0;
        }
        return { name, full, mtime };
      })
      .sort((a, b) => b.mtime - a.mtime)
      .slice(0, maxJobs);
  } catch {
    return [];
  }

  const results: ActiveJobSummary[] = [];
  for (const f of files) {
    let text: string;
    try {
      text = readFileSync(f.full, "utf8").slice(0, 6000);
    } catch {
      continue;
    }
    const titleMatch = text.match(/^#\s+(.+)$/m);
    const grab = (label: string): string => {
      const m = text.match(new RegExp(`\\*\\*${label}:\\*\\*\\s*([^·\\r\\n]+)`, "i"));
      return m ? m[1].trim() : "";
    };
    const completedPhases: string[] = [];
    const pendingPhases: string[] = [];
    for (const line of text.split(/\r?\n/)) {
      if (!line.trim().startsWith("|")) continue;
      const cols = line.split("|").map((c) => c.trim()).filter(Boolean);
      if (cols.length < 3 || !/^\d+:/.test(cols[0])) continue;
      if (/[✅✔]|done|pass/i.test(cols[2])) {
        completedPhases.push(cols[0]);
      } else {
        pendingPhases.push(cols[0]);
      }
    }

    const finalHead = grab("Final head");
    const statusField = grab("Status");
    const hasRealFinalHead =
      Boolean(finalHead) && !/^<.*>$|^tbd$|^pending$|^none$/i.test(finalHead);
    const isClosedStatus = /\b(?:closed|merged|done|complete|completed|finished)\b/i.test(
      statusField
    );
    const allPhasesDone = completedPhases.length > 0 && pendingPhases.length === 0;
    if (hasRealFinalHead || isClosedStatus || allPhasesDone) {
      continue;
    }

    results.push({
      file: f.name,
      title: titleMatch ? titleMatch[1].trim() : f.name,
      project: grab("Project"),
      jNumber: grab("J-number"),
      boardId: grab("Board"),
      size: grab("Size"),
      branch: grab("Branch"),
      started: grab("Started"),
      completedPhases,
      pendingPhases,
    });
  }

  return results;
}

/**
 * Aggregate every pending Owner's Word item across live Foremen (`owed:` / `YOUR CALL`)
 * and project boards (`BOARD.json` `owed[]` + unresolved `decision` jobs).
 */
export function buildOwnerQueue(
  sessions: SessionSummary[],
  topology: Map<string, SessionTopology>,
  boards: BoardSummary[]
): OwnerQueueItem[] {
  const items: OwnerQueueItem[] = [];

  for (const s of sessions) {
    const topo = topology.get(s.id);
    if (!topo || topo.role !== "foreman" || !topo.jStatus?.hasRealOwed) continue;
    items.push({
      source: "foreman",
      title: s.title,
      detail: topo.jStatus.owed || (topo.jStatus.hasYourCall ? "YOUR CALL card waiting on owner" : ""),
      sessionId: s.id,
      sessionTitle: s.title,
      repo: s.repo,
    });
  }

  for (const b of boards) {
    // Skip frozen / topped-out historical boards so the live owner queue stays focused on active work.
    if (b.toppedOut) continue;
    for (const d of b.openDecisions) {
      items.push({
        source: "board_decision",
        title: `${b.title} · Job ${d.id}: ${d.title}`,
        detail: d.decision || d.summary,
        repo: b.repoName,
        boardSlug: b.slug,
        jobId: d.id,
      });
    }
    for (const owedLine of b.owed) {
      if (!isNonEmptyOwed(owedLine)) continue;
      items.push({
        source: "board_owed",
        title: `${b.title} (board owed)`,
        detail: owedLine,
        repo: b.repoName,
        boardSlug: b.slug,
      });
    }
  }

  return items;
}

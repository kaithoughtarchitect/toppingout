// Topping Out stop signal for pi: one durable log line per genuine turn end.
//
// pi has no config-level hooks (settings.json carries none), so the Stop signal
// has to be an extension. Install it globally: copy this file to
// ~/.pi/agent/extensions/ and restart pi so it loads.
//
// Fires on `agent_settled`, which pi documents as the point where "no automatic
// retry, compaction retry, or queued continuation remains": a genuine turn end.
//
// NOT `agent_end`. pi's own docs: after agent_end "Pi may still auto-retry,
// auto-compact and retry, or continue with queued follow-up messages." Wiring
// this to agent_end produces a wake signal that fires mid-cycle, which is the
// exact failure the durable Stop log exists to eliminate. Likewise never swap
// this for a terminal-idle wait: screen-quiet is produced just as well by a
// long tool call as by a finished turn.
//
// FAILS OPEN, deliberately: this is a GLOBAL extension running in every pi
// session, so the tempting design (parse the session and log only the runs
// you care about) fails CLOSED, silencing the signal on any parse problem. A
// missed stop costs hours of wall-clock; a spurious line costs nothing. So it
// always logs, and records the cwd's folder name best-effort as a tag.
//
// Line format: `<iso-stamp> STOP tag=<tag> session=<id>`. The controller's
// watcher (orca-pi-connect/stop-watch.mjs) filters on the `session=<id>`
// substring. Watch it with:
//   node .claude/skills/orca-pi-connect/stop-watch.mjs --session <id> --seen <n> \
//     --log "$HOME/.pi/agent/foreman-stops.log"
//
// It reports no other state, on purpose: whatever drives pi keeps its own
// records and is the authority on them. This hook's only job is to say that a
// turn ended, when, and in which session.
//
// Must never block or fail the pi run: every step is guarded.

import { appendFileSync } from 'node:fs'
import { homedir } from 'node:os'

const LOG = `${homedir()}/.pi/agent/foreman-stops.log`

// Why: the last path segment, not a strict path parse: the Windows path is
// backslashed and a strict parse is the fragile part. Characters outside a safe
// set become `_`, so the tag can never break the space-separated line format.
function tagFor(cwd: string): string {
  const leaf = cwd.split(/[\\/]/).filter(Boolean).pop() ?? ''
  const safe = leaf.replace(/[^A-Za-z0-9._-]/g, '_').slice(0, 64)
  return safe || 'other'
}

function sessionIdFrom(ctx: unknown): string {
  try {
    const sm = (ctx as { sessionManager?: { getSessionId?: () => unknown } } | null)?.sessionManager
    const id = sm?.getSessionId?.()
    return typeof id === 'string' && id ? id : '?'
  } catch {
    return '?'
  }
}

export default function (pi): void {
  // Why: child agents inherit the lead pane's environment. Without a PID guard
  // every sub-agent process would append its own STOP line for one turn end,
  // and --seen arithmetic in the controller would silently over-count.
  const owner = process.env.FOREMAN_PI_STOP_OWNED
  const self = String(process.pid)
  if (owner && owner !== self) return
  process.env.FOREMAN_PI_STOP_OWNED = self

  pi.on('agent_settled', (_event: unknown, ctx: unknown) => {
    try {
      let cwd = ''
      try {
        cwd = process.cwd()
      } catch {
        cwd = ''
      }
      const stamp = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z')
      appendFileSync(LOG, `${stamp} STOP tag=${tagFor(cwd)} session=${sessionIdFrom(ctx)}\n`)
    } catch {
      // Why: status reporting must never fail the pi run. Swallow and continue.
    }
  })
}

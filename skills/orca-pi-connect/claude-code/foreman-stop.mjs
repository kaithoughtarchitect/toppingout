// Topping Out stop signal for a Claude Code builder: one durable log line per turn end.
//
// The Claude Code counterpart of pi-extension/foreman-stop.ts. Claude Code fires its `Stop` hook once each
// time the main session finishes answering; a subagent's end fires `SubagentStop` instead, so child agents
// never add lines here. The hook is loaded only by a builder started with the builder settings file
// (`claude --settings <file>`, written by claude-builder.mjs), never by the foreman or any other session.
//
// Line format, the same as pi's: `<iso-stamp> STOP tag=<cwd folder> session=<id>`, appended to
// ~/.claude/foreman-stops.log (FOREMAN_CC_STOP_LOG overrides it, for tests). The watcher filters on the
// `session=<id>` substring:
//   node .claude/skills/orca-pi-connect/stop-watch.mjs --session <id> --seen <n> --log "$HOME/.claude/foreman-stops.log"
//
// FAILS OPEN, like pi's: a missed stop costs hours, a spurious line costs nothing. It never blocks the stop,
// never prints, and always exits 0. Input it can't read is still logged, as session=?.

import { appendFileSync, readFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

const LOG = process.env.FOREMAN_CC_STOP_LOG || join(homedir(), '.claude', 'foreman-stops.log')

// The last path segment, characters outside a safe set as `_`, so the tag never breaks the line format.
function tagFor(cwd) {
  const leaf = String(cwd || '').split(/[\\/]/).filter(Boolean).pop() ?? ''
  const safe = leaf.replace(/[^A-Za-z0-9._-]/g, '_').slice(0, 64)
  return safe || 'other'
}

try {
  let input = {}
  try {
    input = JSON.parse(readFileSync(0, 'utf8') || '{}') || {}
  } catch {
    input = {}
  }
  const id = typeof input.session_id === 'string' && /^[A-Za-z0-9-]+$/.test(input.session_id) ? input.session_id : '?'
  let cwd = typeof input.cwd === 'string' ? input.cwd : ''
  if (!cwd) {
    try { cwd = process.cwd() } catch { cwd = '' }
  }
  const stamp = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z')
  appendFileSync(LOG, `${stamp} STOP tag=${tagFor(cwd)} session=${id}\n`)
} catch {
  // a stop signal must never fail the builder's run
}
process.exit(0)

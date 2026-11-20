// Topping Out stop signal for an Antigravity (agy) builder: one durable log line per finished turn.
//
// The agy counterpart of pi-extension/foreman-stop.ts and claude-code/foreman-stop.mjs. agy runs its `Stop`
// hooks (~/.gemini/config/hooks.json, entry "foreman-stop", written by agy-builder.mjs) when a turn ends, for
// every agy session on the machine. This hook writes a line only for a builder started by
// `agy-builder.mjs --launch --sid <SID>`, which puts FOREMAN_AGY_SID in agy's environment; agy passes its
// environment to hooks, so every other agy session (the owner's own, Orca's) adds nothing.
//
// Line format, the pi and Claude Code one plus agy's conversation id (for a resume):
//   `<iso-stamp> STOP tag=<cwd folder> session=<SID> conv=<agy conversation id>`
// appended to ~/.gemini/foreman-stops.log (FOREMAN_AGY_STOP_LOG overrides it, for tests). The watcher filters
// on the `session=<SID>` word:
//   node .claude/skills/orca-pi-connect/stop-watch.mjs --session <SID> --seen <n> --log "$HOME/.gemini/foreman-stops.log"
//
// A turn that agy continues by itself (`continuationActive: true`, or `fullyIdle: false`) is not the end of
// the builder's answer, so it writes nothing then. Otherwise it FAILS OPEN, like the others: a missed stop
// costs hours, a spurious line costs nothing. It never blocks the stop, prints `{}` (an empty hook answer)
// and always exits 0. Input it can't read is still logged, with conv=?.

import { appendFileSync, readFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

const LOG = process.env.FOREMAN_AGY_STOP_LOG || join(homedir(), '.gemini', 'foreman-stops.log')
const ID = /^[A-Za-z0-9-]+$/

// The last path segment, characters outside a safe set as `_`, so the tag never breaks the line format.
function tagFor(cwd) {
  const leaf = String(cwd || '').split(/[\\/]/).filter(Boolean).pop() ?? ''
  const safe = leaf.replace(/[^A-Za-z0-9._-]/g, '_').slice(0, 64)
  return safe || 'other'
}

try {
  const sid = process.env.FOREMAN_AGY_SID
  if (sid && ID.test(sid)) {
    let input = {}
    try {
      input = JSON.parse(readFileSync(0, 'utf8').replace(/^﻿/, '') || '{}') || {}
    } catch {
      input = {}
    }
    const unfinished = input.continuationActive === true || input.fullyIdle === false
    if (!unfinished) {
      const conv = typeof input.conversationId === 'string' && ID.test(input.conversationId) ? input.conversationId : '?'
      let cwd = typeof input.cwd === 'string' ? input.cwd : ''
      if (!cwd) {
        try { cwd = process.cwd() } catch { cwd = '' }
      }
      const stamp = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z')
      appendFileSync(LOG, `${stamp} STOP tag=${tagFor(cwd)} session=${sid} conv=${conv}\n`)
    }
  }
} catch {
  // a stop signal must never fail the builder's run
}
process.stdout.write('{}')
process.exit(0)

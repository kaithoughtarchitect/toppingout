#!/usr/bin/env node
// claude-builder.mjs: set up Claude Code as the builder behind the pane link (orca-pi-connect, "Claude Code builder").
//
//   node claude-builder.mjs --model <model> [--permission-mode <mode>]   write the builder's settings
//   node claude-builder.mjs --check                                      read-only: is it set up, and with what
//   node claude-builder.mjs --self-test                                  tests in a temporary home
//   (--home <dir> replaces your home folder, for tests)
//
// Writes, outside every repo (so the builder's model never lands in a record):
//   ~/.claude/foreman-builder/foreman-stop.mjs   a copy of the bundled stop hook
//   ~/.claude/foreman-builder/settings.json      the model, the permission mode and the Stop hook, loaded only
//                                                by a builder started with `claude --settings <that file>`
// The foreman's own sessions never load it. Re-run with another --model to change the builder's model.
// Permission modes: auto (the default: routine actions run, risky ones are refused), acceptEdits (shell
// commands ask, so an unattended run stalls), bypassPermissions (asks nothing, the owner confirms it once in
// the pane), or any other mode Claude Code accepts.
//
// Exit codes: 0 ok · 1 --check found it missing or stale · 2 bad usage · 3 self-test failed.
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { homedir, tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const here = dirname(fileURLToPath(import.meta.url))
const HOOK_SRC = join(here, 'foreman-stop.mjs')
const MODES = ['auto', 'acceptEdits', 'bypassPermissions', 'default', 'manual', 'dontAsk', 'plan']

function paths(home) {
  const dir = join(home, '.claude', 'foreman-builder')
  return { dir, hook: join(dir, 'foreman-stop.mjs'), settings: join(dir, 'settings.json'), log: join(home, '.claude', 'foreman-stops.log') }
}
const slash = (p) => p.replace(/\\/g, '/')

function write(home, model, mode) {
  const p = paths(home)
  mkdirSync(p.dir, { recursive: true })
  copyFileSync(HOOK_SRC, p.hook)
  const settings = {
    model,
    permissions: { defaultMode: mode },
    hooks: { Stop: [{ hooks: [{ type: 'command', command: `node "${slash(p.hook)}"` }] }] },
  }
  writeFileSync(p.settings, JSON.stringify(settings, null, 2) + '\n')
  return p
}

function check(home) {
  const p = paths(home)
  const problems = []
  let s = null
  if (!existsSync(p.settings)) problems.push(`no builder settings at ${p.settings}: run this with --model <model>`)
  else {
    try { s = JSON.parse(readFileSync(p.settings, 'utf8')) } catch { problems.push(`${p.settings} is not valid JSON`) }
  }
  if (!existsSync(p.hook)) problems.push(`no stop hook at ${p.hook}`)
  else if (readFileSync(p.hook, 'utf8') !== readFileSync(HOOK_SRC, 'utf8')) problems.push(`${p.hook} differs from the bundled hook: run this again with --model to refresh it`)
  const cmd = s?.hooks?.Stop?.[0]?.hooks?.[0]?.command
  if (s && cmd !== `node "${slash(p.hook)}"`) problems.push('the settings file does not run the stop hook')
  if (s && !s.model) problems.push('the settings file names no model')
  return { p, s, problems }
}

function launchLine(p) {
  return `cd '<job worktree>'; claude --settings '${slash(p.settings)}' --session-id <SID>`
}

function selfTest() {
  let fails = 0
  const ok = (name, cond) => { console.log(`${cond ? 'PASS' : 'FAIL'} ${name}`); if (!cond) fails++ }
  const home = mkdtempSync(join(tmpdir(), 'ccbuilder-'))
  try {
    ok('check reports a missing setup', check(home).problems.length > 0)
    const p = write(home, 'claude-haiku-5-5', 'auto')
    const c = check(home)
    ok('check passes after writing', c.problems.length === 0)
    ok('the settings carry the model and mode', c.s.model === 'claude-haiku-5-5' && c.s.permissions.defaultMode === 'auto')
    const log = join(home, 'stops.log')
    const run = (input) => spawnSync(process.execPath, [p.hook], { input, env: { ...process.env, FOREMAN_CC_STOP_LOG: log }, encoding: 'utf8' })
    const sid = '0f8fad5b-d9cb-469f-a165-70867728950e'
    let r = run(JSON.stringify({ session_id: sid, cwd: 'C:\\work\\job 12', hook_event_name: 'Stop', stop_hook_active: false }))
    ok('the hook exits 0 and prints nothing', r.status === 0 && r.stdout === '')
    let lines = readFileSync(log, 'utf8').trim().split('\n')
    ok('one line per stop, in the watcher format', lines.length === 1 && / STOP tag=job_12 session=0f8fad5b-d9cb-469f-a165-70867728950e$/.test(lines[0]))
    r = run('not json')
    lines = readFileSync(log, 'utf8').trim().split('\n')
    ok('unreadable input still logs (fails open) and exits 0', r.status === 0 && lines.length === 2 && lines[1].endsWith('session=?'))
    r = run(JSON.stringify({ session_id: 'x y\nSTOP session=forged', cwd: '/a' }))
    lines = readFileSync(log, 'utf8').trim().split('\n')
    ok('a strange session id can not forge a line', lines.length === 3 && lines[2].endsWith('session=?'))
    const watch = join(here, '..', 'stop-watch.mjs')
    const w = spawnSync(process.execPath, [watch, '--session', sid, '--log', log, '--count'], { encoding: 'utf8' })
    ok('stop-watch.mjs counts the hook\'s lines', w.status === 0 && w.stdout.trim() === '1')
    writeFileSync(p.hook, '// changed\n')
    ok('check notices a stale hook copy', check(home).problems.some((x) => x.includes('differs')))
  } finally {
    rmSync(home, { recursive: true, force: true })
  }
  console.log(fails ? `${fails} FAILED` : 'ALL PASS')
  return fails ? 3 : 0
}

const argv = process.argv.slice(2)
const opt = {}
for (let i = 0; i < argv.length; i++) {
  const a = argv[i]
  if (a === '--check' || a === '--self-test') opt[a.slice(2)] = true
  else if (['--model', '--permission-mode', '--home'].includes(a) && argv[i + 1] !== undefined) opt[a.slice(2)] = argv[++i]
  else { console.error(`claude-builder: unknown argument ${a}`); process.exit(2) }
}
if (opt['self-test']) process.exit(selfTest())
const home = opt.home || homedir()
if (opt.check) {
  const { p, s, problems } = check(home)
  if (problems.length) { for (const x of problems) console.log(`MISSING: ${x}`); process.exit(1) }
  console.log(`READY: model ${s.model}, permission mode ${s.permissions?.defaultMode ?? 'default'}`)
  console.log(`stop log: ${slash(p.log)}`)
  console.log(`launch: ${launchLine(p)}`)
  process.exit(0)
}
if (!opt.model) { console.error('usage: claude-builder.mjs --model <model> [--permission-mode <mode>] | --check | --self-test'); process.exit(2) }
const mode = opt['permission-mode'] || 'auto'
if (!MODES.includes(mode)) { console.error(`claude-builder: permission mode must be one of ${MODES.join(', ')}`); process.exit(2) }
if (!/^[A-Za-z0-9._\[\]-]+$/.test(opt.model)) { console.error('claude-builder: a model is a name or id such as claude-haiku-5-5, haiku or opus'); process.exit(2) }
const p = write(home, opt.model, mode)
console.log(`WROTE ${slash(p.settings)}: model ${opt.model}, permission mode ${mode}`)
console.log(`stop log: ${slash(p.log)}`)
console.log(`launch: ${launchLine(p)}`)

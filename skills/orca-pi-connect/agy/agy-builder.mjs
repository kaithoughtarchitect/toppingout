#!/usr/bin/env node
// agy-builder.mjs: set up Antigravity's CLI (agy) as the builder behind the pane link (orca-pi-connect,
// "An Antigravity builder").
//
//   node agy-builder.mjs --model <model> [--mode auto|accept-edits|plan]   write the builder's setup
//   node agy-builder.mjs --check                                         read-only: is it set up, and with what
//   node agy-builder.mjs --launch --sid <SID> [--conversation <id>]      start agy as the builder (the pane command)
//   node agy-builder.mjs --self-test                                     tests in a temporary home
//   (--home <dir> replaces your home folder, for tests; --dry-run with --launch prints the command instead)
//
// Writes, outside every repo (so the builder's model never lands in a record):
//   ~/.gemini/foreman-builder/foreman-stop.mjs   a copy of the bundled stop hook
//   ~/.gemini/foreman-builder/config.json        the model and the mode
//   ~/.gemini/config/hooks.json                  one entry, "foreman-stop", added beside the owner's own
//                                                entries (Orca's "orca-status", say), which stay as they are
// agy runs hooks.json for every agy session, so the hook writes a line only when FOREMAN_AGY_SID is in its
// environment, and only `--launch` sets it. Re-run with another --model to change the builder's model
// (`agy models` lists them, e.g. gemini-4-hydrogen-high, claude-sonnet-5-5-high).
// Modes: auto (the default: agy reviews risky commands itself, routine ones run), accept-edits (shell
// commands ask, so an unattended run stalls), plan (plans only, never builds: not for a builder).
//
// Exit codes: 0 ok · 1 --check found it missing or stale · 2 bad usage · 3 self-test failed · otherwise agy's.
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { homedir, tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawn, spawnSync } from 'node:child_process'

const here = dirname(fileURLToPath(import.meta.url))
const SELF = fileURLToPath(import.meta.url)
const HOOK_SRC = join(here, 'foreman-stop.mjs')
const MODES = ['auto', 'accept-edits', 'plan']
const ENTRY = 'foreman-stop'
const UUID = /^[0-9a-f]{8}-[0-9a-f-]{27,}$/i
const CONV = /^[A-Za-z0-9-]+$/

function paths(home) {
  const dir = join(home, '.gemini', 'foreman-builder')
  return {
    dir,
    hook: join(dir, 'foreman-stop.mjs'),
    config: join(dir, 'config.json'),
    hooks: join(home, '.gemini', 'config', 'hooks.json'),
    log: join(home, '.gemini', 'foreman-stops.log'),
  }
}
const slash = (p) => p.replace(/\\/g, '/')
const hookCommand = (p) => `node "${slash(p.hook)}"`
const readJson = (file) => JSON.parse(readFileSync(file, 'utf8').replace(/^\uFEFF/, ''))

function write(home, model, mode) {
  const p = paths(home)
  mkdirSync(p.dir, { recursive: true })
  copyFileSync(HOOK_SRC, p.hook)
  writeFileSync(p.config, JSON.stringify({ model, mode }, null, 2) + '\n')
  mkdirSync(dirname(p.hooks), { recursive: true })
  let hooks = {}
  if (existsSync(p.hooks)) {
    try { hooks = readJson(p.hooks) } catch { throw new Error(`${p.hooks} is not valid JSON: fix or move it, then run this again (nothing was changed in it)`) }
    if (!hooks || typeof hooks !== 'object' || Array.isArray(hooks)) throw new Error(`${p.hooks} is not a JSON object: nothing was changed in it`)
  }
  hooks[ENTRY] = { Stop: [{ type: 'command', command: hookCommand(p), timeout: 10 }] }
  writeFileSync(p.hooks, JSON.stringify(hooks, null, 2) + '\n')
  return p
}

function check(home) {
  const p = paths(home)
  const problems = []
  let c = null
  if (!existsSync(p.config)) problems.push(`no builder setup at ${p.config}: run this with --model <model>`)
  else {
    try { c = readJson(p.config) } catch { problems.push(`${p.config} is not valid JSON`) }
  }
  if (c && !c.model) problems.push('the builder setup names no model')
  if (c && !MODES.includes(c.mode)) problems.push(`the builder setup has no valid mode (${MODES.join(', ')})`)
  if (!existsSync(p.hook)) problems.push(`no stop hook at ${p.hook}`)
  else if (readFileSync(p.hook, 'utf8') !== readFileSync(HOOK_SRC, 'utf8')) problems.push(`${p.hook} differs from the bundled hook: run this again with --model to refresh it`)
  let h = null
  try { h = readJson(p.hooks) } catch {}
  const cmd = h?.[ENTRY]?.Stop?.[0]?.command
  if (cmd !== hookCommand(p)) problems.push(`${p.hooks} has no "${ENTRY}" Stop hook running the copy: run this again with --model`)
  return { p, c, problems }
}

// The job's own worktree is trusted for this session only (`--settings` is never saved), the up-front trust
// `pi --approve` gives: agy otherwise stops a new folder at "Do you trust the contents of this project?".
function agyArgs(c, conversation, cwd) {
  const a = ['--model', c.model, '--mode', c.mode, '--settings', JSON.stringify({ trustedWorkspaces: [cwd] })]
  if (conversation) a.push('--conversation', conversation)
  return a
}

const launchLine = () => `cd '<job worktree>'; node .claude/skills/orca-pi-connect/agy/agy-builder.mjs --launch --sid <SID>`

function selfTest() {
  let fails = 0
  const ok = (name, cond) => { console.log(`${cond ? 'PASS' : 'FAIL'} ${name}`); if (!cond) fails++ }
  const home = mkdtempSync(join(tmpdir(), 'agybuilder-'))
  const cli = (...a) => spawnSync(process.execPath, [SELF, '--home', home, ...a], { encoding: 'utf8' })
  try {
    ok('check reports a missing setup', check(home).problems.length > 0)
    const p = paths(home)
    mkdirSync(dirname(p.hooks), { recursive: true })
    const owners = { 'orca-status': { Stop: [{ type: 'command', command: 'orca.cmd', timeout: 10 }] } }
    writeFileSync(p.hooks, '\uFEFF' + JSON.stringify(owners))
    write(home, 'gemini-4-hydrogen-high', 'auto')
    const c = check(home)
    ok('check passes after writing', c.problems.length === 0)
    const hooks = readJson(p.hooks)
    ok('the owner\'s own hook entries stay as they were (a BOM file too)', JSON.stringify(hooks['orca-status']) === JSON.stringify(owners['orca-status']))
    ok('one foreman-stop entry runs the copy', hooks[ENTRY].Stop.length === 1 && hooks[ENTRY].Stop[0].command === hookCommand(p))
    write(home, 'claude-sonnet-5-5-high', 'auto')
    ok('writing again replaces the entry, never doubles it', readJson(p.hooks)[ENTRY].Stop.length === 1 && Object.keys(readJson(p.hooks)).length === 2)
    let out = cli('--check').stdout.split(/\r?\n/)
    ok('--check prints the model, the mode and the stop log', out.includes('READY: model claude-sonnet-5-5-high, mode auto') && out.includes(`stop log: ${slash(p.log)}`))
    const dry = cli('--launch', '--sid', '0f8fad5b-d9cb-469f-a165-70867728950e', '--dry-run').stdout
    ok('--launch starts agy with the model and mode, the SID in its environment', dry.includes('FOREMAN_AGY_SID=0f8fad5b-d9cb-469f-a165-70867728950e') && dry.includes('agy --model claude-sonnet-5-5-high --mode auto'))
    const dryR = cli('--launch', '--sid', '0f8fad5b-d9cb-469f-a165-70867728950e', '--conversation', '6b8d5e37-4233-4f6e-9ca2-f3d612d388a1', '--dry-run').stdout
    ok('--launch --conversation resumes that conversation', dryR.includes('--conversation 6b8d5e37-4233-4f6e-9ca2-f3d612d388a1'))
    ok('--launch trusts only the folder it starts in, for that session', dry.includes('--settings') && dry.includes('trustedWorkspaces') && dry.includes(JSON.stringify(JSON.stringify([process.cwd()])).slice(3, -3)))
    ok('--launch refuses a SID that is not a uuid', cli('--launch', '--sid', 'abc', '--dry-run').status === 2)
    ok('--mode must be one agy takes', cli('--model', 'x', '--mode', 'yolo').status === 2)
    writeFileSync(p.hooks, '{not json')
    const bad = cli('--model', 'gemini-4-hydrogen-high')
    ok('an unreadable hooks.json is left alone and reported', bad.status === 2 && readFileSync(p.hooks, 'utf8') === '{not json')
    writeFileSync(p.hooks, '{}')
    write(home, 'gemini-4-hydrogen-high', 'auto')
  } catch (e) {
    ok(`setup tests ran without an exception (${e.message})`, false)
  }
  try {
    const p = paths(home)
    const log = join(home, 'stops.log')
    const sid = '0f8fad5b-d9cb-469f-a165-70867728950e'
    const run = (input, env = {}) => spawnSync(process.execPath, [p.hook], { input, env: { ...process.env, FOREMAN_AGY_SID: '', FOREMAN_AGY_STOP_LOG: log, ...env }, encoding: 'utf8' })
    const stop = (o = {}) => JSON.stringify({ conversationId: '6b8d5e37-4233-4f6e-9ca2-f3d612d388a1', cwd: 'C:\\work\\job 12', hookEventName: 'Stop', fullyIdle: true, continuationActive: false, ...o })
    let r = run(stop())
    ok('another agy session (no FOREMAN_AGY_SID) adds no line', r.status === 0 && !existsSync(log))
    r = run(stop(), { FOREMAN_AGY_SID: sid })
    ok('the hook exits 0 and answers {}', r.status === 0 && r.stdout === '{}')
    let lines = readFileSync(log, 'utf8').trim().split('\n')
    ok('one line per stop, in the watcher format, with the conversation id', lines.length === 1 && / STOP tag=job_12 session=0f8fad5b-d9cb-469f-a165-70867728950e conv=6b8d5e37-4233-4f6e-9ca2-f3d612d388a1$/.test(lines[0]))
    run(stop({ continuationActive: true }), { FOREMAN_AGY_SID: sid })
    run(stop({ fullyIdle: false }), { FOREMAN_AGY_SID: sid })
    lines = readFileSync(log, 'utf8').trim().split('\n')
    ok('a turn agy continues by itself writes nothing', lines.length === 1)
    r = run('not json', { FOREMAN_AGY_SID: sid })
    lines = readFileSync(log, 'utf8').trim().split('\n')
    ok('unreadable input still logs (fails open) and exits 0', r.status === 0 && lines.length === 2 && lines[1].endsWith('conv=?'))
    run(stop({ conversationId: 'x y\nSTOP session=forged' }), { FOREMAN_AGY_SID: sid })
    run(stop(), { FOREMAN_AGY_SID: 'x\nSTOP session=forged' })
    lines = readFileSync(log, 'utf8').trim().split('\n')
    ok('a strange id can not forge a line', lines.length === 3 && lines[2].endsWith('conv=?') && !lines.some((l) => l.includes('forged')))
    const watch = join(here, '..', 'stop-watch.mjs')
    const w = spawnSync(process.execPath, [watch, '--session', sid, '--log', log, '--count'], { encoding: 'utf8' })
    ok('stop-watch.mjs counts the hook\'s lines', w.status === 0 && w.stdout.trim() === '3')
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
  if (['--check', '--self-test', '--launch', '--dry-run'].includes(a)) opt[a.slice(2)] = true
  else if (['--model', '--mode', '--home', '--sid', '--conversation'].includes(a) && argv[i + 1] !== undefined) opt[a.slice(2)] = argv[++i]
  else { console.error(`agy-builder: unknown argument ${a}`); process.exit(2) }
}
if (opt['self-test']) process.exit(selfTest())
const home = opt.home || homedir()

if (opt.check || opt.launch) {
  const { p, c, problems } = check(home)
  if (problems.length) { for (const x of problems) console.log(`MISSING: ${x}`); process.exit(1) }
  if (opt.check) {
    console.log(`READY: model ${c.model}, mode ${c.mode}`)
    console.log(`config: ${slash(p.config)}`)
    console.log(`hooks: ${slash(p.hooks)} (entry "${ENTRY}")`)
    console.log(`stop log: ${slash(p.log)}`)
    console.log(`launch: ${launchLine()}`)
    process.exit(0)
  }
  if (!UUID.test(opt.sid ?? '')) { console.error('agy-builder: --launch needs --sid <uuid>, the SID the foreman chose'); process.exit(2) }
  if (opt.conversation !== undefined && !CONV.test(opt.conversation)) { console.error('agy-builder: --conversation is an agy conversation id (the conv= of the last stop line)'); process.exit(2) }
  const args = agyArgs(c, opt.conversation, process.cwd())
  if (opt['dry-run']) { console.log(`FOREMAN_AGY_SID=${opt.sid} agy ${args.map((x) => (/[\s"{]/.test(x) ? JSON.stringify(x) : x)).join(' ')}`); process.exit(0) }
  const child = spawn('agy', args, { stdio: 'inherit', env: { ...process.env, FOREMAN_AGY_SID: opt.sid } })
  child.on('error', (e) => { console.error(`agy-builder: could not start agy (${e.message}): is it on PATH? (agy --version)`); process.exit(127) })
  child.on('exit', (code, signal) => process.exit(code ?? (signal ? 1 : 0)))
} else {
  if (!opt.model) { console.error('usage: agy-builder.mjs --model <model> [--mode auto|accept-edits|plan] | --check | --launch --sid <SID> [--conversation <id>] | --self-test'); process.exit(2) }
  const mode = opt.mode || 'auto'
  if (!MODES.includes(mode)) { console.error(`agy-builder: --mode must be one of ${MODES.join(', ')}`); process.exit(2) }
  if (!/^[A-Za-z0-9._-]+$/.test(opt.model)) { console.error('agy-builder: a model is a name from `agy models`, such as gemini-4-hydrogen-high'); process.exit(2) }
  let p
  try { p = write(home, opt.model, mode) } catch (e) { console.error(`agy-builder: ${e.message}`); process.exit(2) }
  console.log(`WROTE ${slash(p.config)}: model ${opt.model}, mode ${mode}`)
  console.log(`hooks: ${slash(p.hooks)} (entry "${ENTRY}")`)
  console.log(`stop log: ${slash(p.log)}`)
  console.log(`launch: ${launchLine()}`)
}

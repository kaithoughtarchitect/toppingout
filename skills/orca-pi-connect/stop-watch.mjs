// Wait for a NEW Pi agent_settled entry for one confirmed session only.
// Exit: 0 = new stop, 2 = timeout, 3 = usage/read error.
// Default log: ~/.pi/agent/foreman-stops.log (written by pi-extension/foreman-stop.ts).
// A pi that still loads an older stop extension writes a different path; pass --log.
import { readFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

const usage = 'Usage: node stop-watch.mjs --session <uuid> [--log <path>] (--count | --seen <nonnegative-integer>) [--timeout-seconds <positive-integer>]'
const args = {}
for (let i = 2; i < process.argv.length; i++) {
  const key = process.argv[i]
  if (!key.startsWith('--') || key.slice(2) in args) {
    console.error(usage)
    process.exit(3)
  }
  if (key === '--count') {
    args.count = true
  } else if (['--session', '--log', '--seen', '--timeout-seconds', '--timeout'].includes(key) && process.argv[i + 1] !== undefined) {
    // --timeout is an alias (greptile-wait.mjs spells it that way); giving both is an error
    const name = key === '--timeout' ? 'timeout-seconds' : key.slice(2)
    if (name in args) { console.error(usage); process.exit(3) }
    args[name] = process.argv[++i]
  } else {
    console.error(usage)
    process.exit(3)
  }
}
const session = args.session
const seen = Number(args.seen)
const timeout = Number(args['timeout-seconds'] ?? 3600)
if (!/^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(session ?? '') || Boolean(args.count) === ('seen' in args) ||
    (!args.count && (!Number.isSafeInteger(seen) || seen < 0)) ||
    !Number.isSafeInteger(timeout) || timeout <= 0) {
  console.error(usage)
  process.exit(3)
}
const log = args.log ?? join(homedir(), '.pi', 'agent', 'foreman-stops.log')
const exact = new RegExp(`(?:^|\\s)session=${session}(?:\\s|$)`)
function matchingLines() {
  try {
    return readFileSync(log, 'utf8').split(/\r?\n/).filter(line => exact.test(line))
  } catch (error) {
    if (error.code === 'ENOENT') return []
    console.error(`Cannot read stop log: ${error.message}`)
    process.exit(3)
  }
}
if (args.count) {
  console.log(matchingLines().length)
} else {
  const deadline = Date.now() + timeout * 1000
  function poll() {
    const lines = matchingLines()
    if (lines.length > seen) {
      console.log(`TURN END: session=${session} ${seen} -> ${lines.length}`)
      console.log(lines.at(-1))
      return
    }
    if (Date.now() >= deadline) {
      console.error(`TIMEOUT: session=${session} count=${lines.length}`)
      process.exitCode = 2
      return
    }
    setTimeout(poll, 1000)
  }
  poll()
}

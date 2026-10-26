---
title: Extending dcode (memory, skills, subagents, hooks, plugins, extensions, MCP)
id: dcode-extending
type: how-to
status: sourced
product: dcode
keywords: dcode extensions, AGENTS.md, memory, skills, SKILL.md, subagents, sub-agent, MCP servers, .mcp.json, hooks, hooks.json, PreToolUse, plugins, marketplace, ExtensionAPI, Python extension, register_tool, allowedTools
read_when: Read when adding memory, skills, subagents, MCP servers, hooks, plugins or Python extensions to dcode, or when a project MCP server or extension does not load.
updated: 2026-10-21
sources_hash: c1d12529298b
---

# Extending dcode (memory, skills, subagents, hooks, plugins, extensions, MCP)

The seven ways to change what [[dcode]] knows and can do. From least to most power: `AGENTS.md` memory, skills, markdown subagents, MCP servers, hooks, plugins, and (experimental) Python extensions. Use this page to decide which one fits and to get the exact file shapes.

## Quick reference

- Order of power: AGENTS.md memory, skills, markdown subagents, MCP, hooks, plugins, then experimental Python extensions.
- Instructions combine, never override: base prompt, then `~/.deepagents/<agent>/AGENTS.md`, `.deepagents/AGENTS.md`, root `AGENTS.md`.
- Skill precedence (low to high): `~/.deepagents/<agent>/skills/`, `~/.agents/skills/`, `.deepagents/skills/`, `.agents/skills/`; same name means the higher one wins entirely.
- Subagent `AGENTS.md` frontmatter supports only `name`, `description`, `model`; they inherit the main agent's tools. `general-purpose` is fork mode by default since 0.1.66.
- MCP config files: `~/.deepagents/.mcp.json`, `.deepagents/.mcp.json`, project `.mcp.json` (highest). Project servers are default-deny. `allowedTools` and `disabledTools` are mutually exclusive.
- Hooks: only `type: command`, JSON on stdin; exit 2 blocks, exit 0 applies stdout JSON. Hooks cannot mutate tool input.
- Python extensions need `DEEPAGENTS_CODE_EXPERIMENTAL=1`; the module defines `async def extension(d: ExtensionAPI)`.
- Extension tools are not in the approval map; enforce policy through middleware.
- Gotcha: use `/restart` (not `/reload`) for anything graph-bound such as extension middleware and routes.
- Async subagents are not available to dcode end users.

## Choose a mechanism

| Need | Use | Reload |
| - | - | - |
| Always-on conventions and preferences | `AGENTS.md` / auto-memory | New session |
| On-demand workflow or reference doc | Skill (`SKILL.md`) | `/reload` |
| Specialist delegate with its own prompt or model | Subagent `AGENTS.md` | New session |
| External tools (APIs, DBs, SaaS) | MCP server in `.mcp.json` | `/reload` |
| Allow or deny tools, inject context, keep a turn going | Hook in `hooks.json` | `/reload` |
| Distribute any of the above | Plugin + marketplace | `/reload` (`/restart` for extensions) |
| Custom Python tools, middleware, storage routes | Python extension (experimental) | Tools: next request. Middleware and routes: rebuild the graph |

## Memory

- Auto-memory lives in `~/.deepagents/<agent>/memories/*.md`. The agent researches it before tasks and saves learnings. `[memory].auto_save = false` (or `DEEPAGENTS_CODE_MEMORY_AUTO_SAVE=0`) keeps loading memory but stops unprompted saves. `/remember [context]` forces a memory update.
- Instructions are **combined**, never overridden: the package base prompt, then `~/.deepagents/<agent>/AGENTS.md`, then `.deepagents/AGENTS.md`, then root `AGENTS.md`. All are appended to the system prompt at startup.
- Other files in `.deepagents/` are read only if `AGENTS.md` references them.
- `-a NAME` gives a fully separate memory, skills and subagent tree. See [[memory]] for the SDK's `MemoryMiddleware`.

## Skills

```bash
dcode skills create test-skill            # ~/.deepagents/<agent>/skills/test-skill/SKILL.md
dcode skills create test-skill --project  # .deepagents/skills/
dcode --skill code-review -n 'review this patch' -q
```

- Discovery order, lowest to highest precedence: `~/.deepagents/<agent>/skills/`, `~/.agents/skills/`, `.deepagents/skills/`, `.agents/skills/`. `~/.claude/skills/` and `.claude/skills/` are also scanned (experimental). A higher-precedence skill with the same name wins completely; there is no merging.
- At startup only the frontmatter (`name`, `description`) is read. The body is read when a task matches. Invoke directly with `/skill:<name> [args]`.
- Symlinks that resolve outside the skill roots are rejected unless the target is in `[skills].extra_allowed_dirs` (or `DEEPAGENTS_CODE_EXTRA_SKILLS_DIRS`, colon-separated) or you approve the target directory at the interactive trust prompt. Headless runs cannot prompt, so they deny the turn and need the allowlist. This allowlist does not add discovery locations.
- `/skill:<name>` is resolved on the agent server, which loads the `SKILL.md` before the first model call (0.1.84).
- `npx skills add <repo> --skill <s> -a deepagents -g` installs into the default `agent` directory only. See [[skills]] for the Agent Skills format.

## Subagents

```markdown
<!-- .deepagents/agents/researcher/AGENTS.md  (or ~/.deepagents/<agent>/agents/researcher/AGENTS.md) -->
---
name: researcher
description: Research topics on the web before writing content
model: anthropic:claude-haiku-5-5
---
You are a research assistant...
```

- Frontmatter supports only `name`, `description` and optional `model`. The body becomes `system_prompt`. `tools`, `middleware`, `interrupt_on` and `skills` cannot be set, and these subagents inherit the main agent's tools. Use the SDK for full control ([[subagents]]).
- Project subagents override user subagents with the same name. Naming one `general-purpose` overrides the built-in, for example to send delegation to a cheaper model.
- The built-in `general-purpose` subagent runs in **fork** mode by default (since 0.1.66): it inherits the parent conversation and system prompt. `DEEPAGENTS_CODE_FORKED_SUBAGENTS=false` switches to isolated mode. Set it in the shell or global `.env`; a project `.env` cannot set it. This maps to the SDK's `mode: "fork"`, which is beta. In SDK 0.7.29, `mode` accepts `"isolated"` or `"fork"`, and fork cannot also set `skills`.
- [[dynamic-subagents]] work out of the box because `js_eval` is on. Ask for a "workflow" and the agent writes a script that calls `task()` in the interpreter. Progress shows in the dynamic subagents panel (`Ctrl+T`).
- [[async-subagents]] are **not** available to dcode end users.

## MCP servers

```json
// ~/.deepagents/.mcp.json  (user)  |  .deepagents/.mcp.json  |  .mcp.json (project root, highest)
{
  "mcpServers": {
    "fs":     {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "${DIR:-/tmp}"],
               "allowedTools": ["read_file", "list_directory"]},
    "linear": {"type": "http", "url": "https://mcp.linear.app/mcp", "auth": "oauth"},
    "api":    {"type": "sse", "url": "https://api.example.com/mcp",
               "headers": {"Authorization": "Bearer ${API_TOKEN}"}}
  }
}
```

- stdio servers accept an optional `cwd`. Approved project servers and `--mcp-config` servers start in the session working directory; user-level and plugin servers inherit the backend process directory.
- Each MCP tool call times out after 120 s by default (`[mcp].tool_timeout`, 1 to 900 s, or `DEEPAGENTS_CODE_MCP_TOOL_TIMEOUT`). A timeout does not cancel the call on the server.
- The transport is stdio by default, or `type` (alias `transport`) set to `sse` or `http` (`streamable_http` is accepted). Server names must match `[A-Za-z0-9_-]+`. Configs merge by server name, and a higher-precedence file replaces the whole server object. `--mcp-config PATH` adds a highest-precedence file. `--no-mcp` disables MCP.
- `allowedTools` and `disabledTools` are mutually exclusive and must be non-empty. Entries are fnmatch globs matched against both `tool` and `{server}_{tool}`.
- For OAuth: `dcode mcp login` lists servers that need login; `dcode mcp login <name>` runs the flow (DCR + PKCE paste-back, Slack's variant, or GitHub device flow). Tokens are stored in `.state/mcp-tokens/<server>-<sha16(url)>.json` (mode 0600). `auth: "oauth"` cannot be combined with an `Authorization` header or used on stdio servers.
- Project `.mcp.json` servers are **default-deny**. See [[dcode-safety]] for trust handling. User-level configs are always trusted. The startup prompt can also deny a server for the session or permanently (permanent denials apply across all projects and live in `[mcp].disabled_project_servers`).
- In Auto mode, a tool skips classifier review only when `readOnlyHint` is exactly `true` and `destructiveHint` is not `true`.
- Since 0.1.71, MCP runs on FastMCP and `langchain.mcp`. See [[mcp]] and [[tools]].

## Hooks

```json
// ~/.deepagents/hooks.json   (project: .deepagents/hooks.json, needs workspace trust)
{"hooks": {"PreToolUse": [{"matcher": "Bash",
  "hooks": [{"type": "command", "command": "~/.deepagents/hooks/block-rm.sh", "timeout": 600}]}]}}
```

- Events: client-owned are `SessionStart`, `UserPromptSubmit`, `SessionEnd`, `PermissionRequest`, `Notification`. Server-owned are `PreToolUse`, `PostToolUse`, `PreCompact`, `Stop`, `SubagentStart`, `SubagentStop`.
- Handlers: only `type: "command"`. The payload arrives as JSON on stdin. Optional fields are `argv` (skips the shell), `timeout` (default 600 s, 30 s for `UserPromptSubmit`) and `statusMessage`. `"async": true` is an error.
- Exit codes: `0` means stdout JSON is applied. `2` blocks or feeds back, depending on the event (deny tool, block prompt, block compaction, continue a `Stop`), with stderr as the reason. Any other code is a non-blocking diagnostic.
- `PreToolUse` → `hookSpecificOutput.permissionDecision`: `allow`, `ask` or `deny`, combined as deny > ask > allow. `Stop` → `{"decision": "block", "reason": ...}` keeps working, capped at 8 consecutive continuations; check `stop_hook_active`. `additionalContext` works for `SessionStart`, `UserPromptSubmit` and `SubagentStart`.
- Hooks see Claude-Code-style public tool names: `Bash`, `Write`, `Edit`, `Read`, `Glob`, `Grep`, `LS`, `mcp__<server>__<tool>`. The internal names (`execute`, `write_file`, and so on) are not used.
- Precedence: project, then user, then plugin. All matching handlers run concurrently; precedence only decides which result wins. The handler environment drops any variable whose name contains KEY, TOKEN, SECRET, PASSWORD or APIKEY.
- `Notification` with `matcher: "cache_expiring"` fires once per thread and cache window in the last 60 seconds before the prompt cache expires (0.1.80).
- Not applied: `updatedInput`, `defer`, `updatedToolOutput`, `updatedPermissions`, `SubagentStop` block. Hooks cannot mutate tool input.

## Plugins and marketplaces

- Manage with `/plugins` or `dcode plugin marketplace add owner/repo[@ref]`, `dcode plugin install name@marketplace`, and `enable`, `disable`, `uninstall`.
- Plugin layout: `.claude-plugin/plugin.json` or `.codex-plugin/plugin.json` (optional; must have `name`), `skills/`, `hooks/hooks.json`, `.mcp.json`. Custom paths must start with `./`.
- Plugin skills are namespaced: `/skill:plugin@marketplace:skill`.
- Path variables: `${CLAUDE_PLUGIN_ROOT}`/`${PLUGIN_ROOT}`, `${CLAUDE_PLUGIN_DATA}`/`${PLUGIN_DATA}`, `${CLAUDE_PROJECT_DIR}`.
- A marketplace is a JSON file with `name` and a `plugins[]` array (`name`, `source`). It is found at `.claude-plugin/marketplace.json` or `.agents/plugins/marketplace.json`. Sources: `./local`, `github`, `url`, `git-subdir`.
- Auto-update is opt-in per plugin via `extensions."com.langchain.deepagents.code".autoUpdate: true`. Turn it off globally with `[plugins].auto_update = false`.
- The agent can search your configured marketplace catalogs for plugins (`dcode plugin list --json`, `dcode plugin marketplace list --json`); it does not search marketplaces you have not added.
- Enabling a plugin is the consent gate for its hooks, MCP servers and extensions. Workspace trust does not apply to plugins.

## Python extensions (experimental)

```python
# ~/.deepagents/extensions/memories.py  -- requires DEEPAGENTS_CODE_EXPERIMENTAL=1
from deepagents.backends import StoreBackend          # SDK; namespace is keyword-only
from deepagents_code.extensions import ExtensionAPI   # dcode package, not the SDK

async def extension(d: ExtensionAPI) -> None:          # must be async and named `extension`
    d.register_backend_route("/memories/", StoreBackend(namespace=lambda _rt: ("filesystem",)))
    d.register_tool(lambda: str(d.cwd))                # callable or BaseTool
    # d.register_middleware(MyMiddleware())            # AgentMiddleware instance or zero-arg class
    # d.on_shutdown(cb)                                # sync or async
```

- Context available on the registrar: `d.cwd`, `d.mode` (`interactive` or `headless`), `d.has_ui`, `d.path`.
- Sources are loaded in this order: `~/.deepagents/extensions/`, `[extensions].extra_paths`, `-e/--extension`, versioned plugins (`pythonExtensions`), the `dcode.extensions` entry point, and trusted `.deepagents/extensions/` (policy `[extensions].trust` = `ask`/`always`/`never`; headless runs need `--trust-project-extensions`).
- Extension tools and middleware replace built-ins with the same name. Between extensions, the first registration wins. Setup is transactional: a failed extension is rolled back.
- Route prefixes must be lowercase with leading and trailing `/`. Routed content is visible to file tools but **not** to shell `execute`. See [[backends]] and [[middleware]].
- Extension tools are **not** added to the approval map. Enforce policy yourself through middleware.

## Gotchas

- In `extensions.md`, the "Apply runtime changes" section says middleware and route changes "require `/reload`". The same page's plugin section, `plugins.md` and `/extensions` output say `/restart` rebuilds the graph. Use `/restart` for anything graph-bound.
- `hooks.md` documents a `--trust-project-hooks` flag for headless runs, but the `cli-reference.md` options table does not list it.
- The hook payload `permission_mode` uses Claude Code values (`default`, `acceptEdits`, `bypassPermissions`, ...), not dcode's Manual, Auto and YOLO.
- The subagents doc notes ACP ([[protocols]]) as a way to use dynamic subagents from other editors such as Zed.

## Sources

- `../sources/docs/oss/deepagents/code/memory-and-skills.md`
- `../sources/docs/oss/deepagents/code/subagents.md`
- `../sources/docs/oss/deepagents/code/hooks.md`
- `../sources/docs/oss/deepagents/code/plugins.md`
- `../sources/docs/oss/deepagents/code/extensions.md`
- `../sources/docs/oss/deepagents/code/mcp-tools.md`
- `../sources/docs/oss/deepagents/code/configuration.md` (data locations, precedence)
- `../sources/package/deepagents/backends/store.py` (`StoreBackend(*, namespace, store=None)`)
- `../sources/package/deepagents/middleware/subagents.py` (`mode: "isolated" | "fork"`)

## See also

- [[index]]
- [[dcode]]
- [[dcode-config]]
- [[dcode-safety]]

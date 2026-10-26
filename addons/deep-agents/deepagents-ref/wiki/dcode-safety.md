---
title: dcode approval modes and remote sandboxes
id: dcode-safety
type: reference
status: sourced
product: dcode
keywords: approval modes, manual mode, auto mode, YOLO, --yolo, auto-approve, human in the loop, HITL, approval, shell allow list, -S, allow-fs-tools, sandbox, remote sandbox, daytona, modal, runloop, untrusted repo, project trust, SandboxProvider
read_when: Read when running dcode unattended or in an untrusted repo, choosing an approval mode, allowing shell commands, or setting up a remote sandbox.
updated: 2026-10-21
sources_hash: 0e6bbecc8fad
---

# dcode approval modes and remote sandboxes

How [[dcode]] limits what the agent can do. Three approval modes (Manual, Auto, YOLO) decide who reviews gated tool calls. Shell and filesystem allowlists narrow what is callable. Remote sandboxes move tool execution off your machine. Read this before running dcode unattended or in an untrusted repository.

## Quick reference

- Gated: `write_file`, `edit_file`, `delete`, `execute`, `web_search`, `fetch_url`, `task`, plus non-read-only MCP tools. `ls`, `read_file`, `glob`, `grep` never prompt.
- Modes: Manual (default, prompts on every gated action), Auto (`-y`, classifier reviews non-routine batches), YOLO (`--yolo`, no review, needs a one-time acknowledgement). `Shift+Tab` cycles them.
- Auto and YOLO are interactive only; in `-n` or piped runs `-y` and `--yolo` are ignored. A remote `--sandbox` forces Manual.
- Auto is an authorization heuristic, not containment; it does not review subagent actions or `js_eval` fan-out, and trusts MCP `readOnlyHint`.
- Auto classifier time budget is 20 s (`[models].auto_classifier_timeout`, 1..300); misses are denied.
- Headless shell is off unless `-S` is set: `-S "pytest,git"`, `-S recommended`, or `-S all`; pair with `--allow-fs-tools ...,execute`.
- Project `.mcp.json` servers are default-deny; headless skips unapproved ones unless `--trust-project-mcp`. Project hooks need workspace trust.
- For untrusted repos set `DEEPAGENTS_CODE_READ_PROJECT_DOTENV=0` and use a remote sandbox.
- Remote sandbox: `dcode --sandbox daytona|modal|runloop|langsmith|agentcore|vercel`; LLM loop stays local, tools run in the sandbox. Bare `--sandbox` goes last.
- Gotcha: a sandbox isolates execution, not prompt injection; setup scripts expand `${VAR}` from your local env.

## Gated vs ungated actions

- Gated: `write_file`, `edit_file`, `delete`, `execute`, `web_search`, `fetch_url`, `task`. Non-read-only MCP tools are gated too.
- Never prompted: `ls`, `read_file`, `glob`, `grep`.
- This is the dcode product version of the SDK's `interrupt_on` [[human-in-the-loop]]. The SDK's declarative filesystem rules are in [[permissions]].

## Approval modes

| Mode | Launch | Behaviour |
| - | - | - |
| Manual (default) | Nothing, or `[startup].mode = "manual"` | Prompts before every gated action. Fails closed |
| Auto | `-y/--auto-approve`, `[startup].mode = "auto"`, `Shift+Tab` | Deterministic allow for routine actions. Otherwise an LLM classifier reviews the batch. Hands back to you after repeated denials or failures |
| YOLO | `--yolo`, `[startup].mode = "yolo"` | No review. Needs a one-time local risk acknowledgement |

- `Shift+Tab` cycles YOLO → Manual → Auto. `[startup].yolo_switcher = false` removes YOLO from the cycle.
- When no flag or config applies, dcode restores the last Manual or Auto choice. YOLO is never restored implicitly.
- Auto and YOLO are **interactive only**. In `-n` or piped runs, `-y` and `--yolo` are ignored with a warning. A remote `--sandbox` forces Manual. YOLO still needs the acknowledgement inside a sandbox.
- Auto stage 1: routine actions such as a source-file write or `git status` run with no classifier call. Sensitive targets such as `.github/workflows/*` and mutating commands such as `git commit` go to stage 2.
- Auto stage 2: the classifier checks the batch against the user's requested outcome. On deny, the agent gets an error result and can re-plan. When classifier review is unavailable, the tool returns a compact "unavailable" result instead. A total-denial threshold opens the human approval UI.
- Decisions are bound to the thread, mode, batch and exact calls. A mode change, replay or missing state falls back to human review.
- Classifier model precedence: `/auto model [p:m|clear]` > `--auto-classifier-model` (TUI only) > `DEEPAGENTS_CODE_AUTO_CLASSIFIER_MODEL` (not from a project `.env`) > `[models].auto_classifier` > provider default > main model.
- Provider defaults: Anthropic → `anthropic:claude-sonnet-5`. Google AI → `google_genai:gemini-3.8-flash`. Vertex → `google_vertexai:gemini-3.8-flash`. OpenAI → `openai:gpt-5.6-luna`. Codex → `openai_codex:gpt-5.6-luna`.
- The classifier time budget per batch is 20 s by default (`[models].auto_classifier_timeout`, clamped 1..300). Misses are denied as `classifier_unavailable`.
- Auto is an authorization heuristic, **not** containment. Parent-level Auto does not review actions inside delegated subagents or broadly configured `js_eval` fan-out. MCP `readOnlyHint` annotations are trusted without verification.

## Shell and filesystem allowlists

```bash
dcode -n "Fix the failing tests" --allow-fs-tools execute,read_file,edit_file -S "pytest,git,make"
dcode -n "Build" -S recommended       # curated safe read-only list
dcode -n "Fix the build" -S all       # any command, no confirmation
```

- `-S/--shell-allow-list` (or `DEEPAGENTS_CODE_SHELL_ALLOW_LIST`, or `[shell].allow_list`) pre-approves commands that run through `execute`. It works in both modes. Headless shell is **off** unless this is set.
- `--allow-fs-tools` picks which of `ls, read_file, write_file, edit_file, delete, glob, grep, execute` exist. It must include `read_file`. It applies to the main agent and synchronous subagents, not to async subagents or non-filesystem tools.
- Both flags are needed for headless shell. `-S` without `execute` has nothing to gate. `execute` without `-S` pre-approves nothing.
- `js_eval` programmatic tool calls bypass approvals. The default `ptc = "safe"` exposes only `read_file`, `glob` and `grep`. `ptc = "all"` requires `ptc_acknowledge_unsafe = true` (see [[interpreters]], [[dcode-config]]).

## Project trust gates (untrusted repos)

- Project `.mcp.json` servers are default-deny, whether stdio or remote (remote servers could SSRF or exfiltrate `${VAR}` headers). The interactive prompt offers "Allow once" or "Allow for this project — until changed". Saved approvals go to `[mcp].enabled_project_server_approvals` as `{project_root, name, fingerprint}` entries; any change to the definition triggers a new prompt.
- Headless runs silently skip unapproved project servers unless `--trust-project-mcp` is passed. Deny lists (`[mcp].disabled_project_servers`, `DEEPAGENTS_CODE_DISABLED_PROJECT_MCP_SERVERS`) always win. `DEEPAGENTS_CODE_DANGEROUSLY_ENABLE_PROJECT_MCP_SERVERS` approves by name across projects and replaces saved approvals.
- Project hooks need workspace trust, stored in `.state/hooks_trust.json`. Project extensions need extension trust. Plugins are trusted by enabling them.
- The project `.env` loads by default. Dangerous variables are blocked from dotenv, but `.env`, `Makefile` and build scripts can still influence what runs. Use `DEEPAGENTS_CODE_READ_PROJECT_DOTENV=0` and a remote sandbox for untrusted repositories.

## Remote sandboxes

This is the SDK's "sandbox as tool" pattern (see [[sandboxes]]). The LLM loop, memory and dispatch stay local. `read_file`, `write_file`, `execute` and the other tools target the sandbox.

```bash
dcode --install daytona                      # or: all-sandboxes; LangSmith is bundled
export DAYTONA_API_KEY=...
dcode --sandbox daytona --sandbox-setup ./setup.sh
dcode --sandbox runloop --sandbox-id dbx_abc123    # reattach; skips create and cleanup
dcode --sandbox langsmith --sandbox-snapshot-name base
dcode --sandbox daytona --sandbox-snapshot-name my-env
dcode --sandbox                              # uses [sandboxes].default; keep the bare flag LAST
```

| Provider | Install | Credentials | Working dir |
| - | - | - | - |
| `langsmith` | Bundled | `LANGSMITH_API_KEY` | `/root` |
| `agentcore` | `agentcore` extra | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` (and `AWS_SESSION_TOKEN`) | `/tmp` |
| `daytona` | extra | `DAYTONA_API_KEY` | `/home/daytona` |
| `modal` | extra | `modal setup` | `/workspace` |
| `runloop` | extra | `RUNLOOP_API_KEY` | `/home/user` |
| `vercel` | extra | `VERCEL_TOKEN`, `VERCEL_PROJECT_ID`, `VERCEL_TEAM_ID` (OIDC on Vercel) | `/vercel/sandbox` |
| `e2b` (third party) | `dcode --install langchain-e2b --package` | `E2B_API_KEY` | `/home/user` |

- `--sandbox-snapshot-name` works with `langsmith`, `daytona` (since 0.1.84), `runloop` and providers that advertise snapshot support. It cannot be combined with `--sandbox-id`.
- Setup scripts run in the working dir after creation. `${VAR}` references are expanded from your **local** environment, so be careful which secrets you forward.
- The 0.1.86 changelog adds NVIDIA OpenShell as a sandbox provider; the remote-sandboxes page does not document it yet.
- Provider discovery precedence: config-declared > third-party entry point (`deepagents_code.sandbox_providers`) > built-in.

```toml
[sandboxes]
default = "acme"                      # used by a bare --sandbox; does NOT force sandboxing
[sandboxes.providers.acme]
class_path = "acme_sandbox.provider:AcmeProvider"   # imports arbitrary code
working_dir = "/workspace"            # default /workspace
package = "acme-dcode-sandbox"
supports_sandbox_id = true            # default true
supports_snapshot_name = false        # default false
[sandboxes.providers.acme.params]     # forwarded to get_or_create()
region = "us-east-1"
```

A provider subclasses `deepagents_code.integrations.sandbox_provider.SandboxProvider`. It implements `get_or_create(*, sandbox_id=None, **kw)`, which returns an SDK `SandboxBackendProtocol`, and `delete(*, sandbox_id, **kw)`. It can optionally define a `metadata` property returning `SandboxProviderMetadata`. `SandboxBackendProtocol` exists in SDK 0.7.29 `backends/protocol.py`. The `deepagents_code` classes are docs only.

## Gotchas

- A sandbox isolates execution, not prompt injection. Keep approvals on and use short-lived secrets.
- Extension tools are not in the approval map, and backend routes backed by `FilesystemBackend` are rejected when a sandbox is active (see [[dcode-extending]]).
- `managed_config.toml` can pin `startup.mode`, `startup.yolo_switcher` and `shell.allow_list`. Invalid values fail closed.
- Goals in Auto can auto-accept criteria only with `goals.auto_accept_criteria = true`. YOLO always auto-accepts (see [[dcode-goals]]).

## Sources

- `../sources/docs/oss/deepagents/code/approval-modes.md`
- `../sources/docs/oss/deepagents/code/remote-sandboxes.md`
- `../sources/docs/oss/deepagents/code/cli-reference.md` (allowlist interplay)
- `../sources/docs/oss/deepagents/code/mcp-tools.md` (project trust)
- `../sources/docs/oss/deepagents/code/configuration.md` (dotenv blocking, managed policy)
- `../sources/docs/github/deepagents-code-CHANGELOG.md` (OpenShell provider, Daytona snapshots)
- `../sources/package/deepagents/backends/protocol.py` (`SandboxBackendProtocol`)

## See also

- [[index]]
- [[dcode]]
- [[dcode-config]]
- [[human-in-the-loop]]
- [[sandboxes]]

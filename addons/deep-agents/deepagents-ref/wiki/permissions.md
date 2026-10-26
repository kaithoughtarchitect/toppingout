---
title: Filesystem permissions (FilesystemPermission)
id: permissions
type: api
status: code
product: sdk
keywords: permissions, FilesystemPermission, read-only agent, deny write, allow deny, path restrictions, restrict paths, approval, interrupt mode, HITL, human in the loop, first match wins, access control, guardrails
read_when: Read when making paths read-only, confining the agent to a directory, requiring approval for sensitive writes, or hitting NotImplementedError combining permissions with a shell backend.
updated: 2026-10-21
sources_hash: 2888e24759f0
---

# Filesystem permissions (FilesystemPermission)

Declarative first-match-wins allow/deny/interrupt rules on the built-in file tools, passed as `create_deep_agent(permissions=[...])`; reach for it to make paths read-only, sandbox the agent to a directory, or require approval for sensitive writes.

## Quick reference

- `create_deep_agent(permissions=[FilesystemPermission(operations=["read"|"write"], paths=[...], mode="allow"|"deny"|"interrupt")])`; default mode is `allow`.
- `read` covers `ls, read_file, glob, grep`; `write` covers `write_file, edit_file, delete`; `execute` is not covered.
- Rules are first-match-wins in order; no matching rule means allowed. Put specific rules before broad; end with a `/**` deny for an allowlist.
- Paths must start with `/`; `..` raises `ValueError`; patterns use `**` and `{a,b}` globs on virtual paths.
- Enforced only in the built-in file tools, not custom tools, MCP tools, `execute` or direct backend calls.
- `mode="interrupt"` needs a checkpointer and `deepagents>=0.6.8`; it merges into `interrupt_on`.
- With an execute-capable backend, every permission path must start with a Composite route prefix or `NotImplementedError` is raised.
- Subagent `permissions` replace (not extend) the parent's; subagents otherwise inherit.
- A pathless `glob` is checked against `/`, so an allowlist can deny it; pass `path`.
- With `FilesystemBackend` (directly or behind a Composite route), rules are matched against the requested path **and** its symlink-resolved target (0.7.25+); a deny on either blocks.

## API

```python
from deepagents import FilesystemPermission, create_deep_agent
# also importable from deepagents.middleware.filesystem and (legacy re-export) deepagents.middleware.permissions

@dataclass
class FilesystemPermission:
    operations: list[Literal["read", "write"]]
    paths: list[str]                                    # glob patterns, must start with "/"
    mode: Literal["allow", "deny", "interrupt"] = "allow"
```

- `"read"` covers `ls`, `read_file`, `glob`, `grep`. `"write"` covers `write_file`, `edit_file`, `delete`. `execute` is not covered.
- Patterns are matched with `wcmatch.glob.globmatch(path, pattern, flags=BRACE | GLOBSTAR)`: `**` recursive, `{a,b}` alternation, `*` within a segment.
- Validation in `__post_init__`: path not starting with `/` -> `ValueError`; a `..` component -> `ValueError`; a `~` component -> `NotImplementedError`.
- Evaluation (`_check_fs_permission`): iterate rules in order; skip rules whose `operations` lack the op; first rule with any matching pattern returns its `mode`; no match -> **allow**.
- Passed via [[create-deep-agent]] `permissions=` (main agent + inherited by subagents). For multi-tenant hardening see [[production]].
- Requires `deepagents>=0.5.2`; `mode="interrupt"` requires `>=0.6.8`; exact-match delete semantics `>=0.7.3`.

## Enforcement (where and how)

- Enforced by `FilesystemMiddleware` inside each tool, before the backend is called (see [[filesystem-tools]]). Denied calls return `Error: permission denied for <op> on <path>` with `status="error"`.
- Bulk results are filtered: `ls`, `glob`, `grep` drop entries/matches whose path is denied, so the agent never sees them.
- Not enforced for direct backend calls, custom tools, MCP tools, or `execute`. For those use backend policy wrappers ([[backends]]) or [[sandboxes]].
- Symlinks (0.7.25+): with `FilesystemBackend`, directly or behind a `CompositeBackend` route, each check also resolves the path through symlinks (`FilesystemBackend._real_path`) and matches the target. A deny on either path blocks, with `Error: permission denied for <op> on <path> (resolves to <target>)`. A path that can't be resolved (it escapes the root in virtual mode, or is a symlink loop) returns `Error: cannot resolve <path>` once any rule is set. Bulk results drop entries whose target is denied. Before 0.7.25 the backend followed symlinks after the check, so a link inside an allowed folder could reach a denied one. Other backends have no symlinks and are checked on the requested path only.
- `glob` without `path` is authorized against `/`. With a `/**` deny + `/workspace/**` allow, a pathless glob is denied; the error hint tells the model to pass `path`.

## Recipes

```python
# Read-only agent
permissions=[FilesystemPermission(operations=["write"], paths=["/**"], mode="deny")]

# Confine to /workspace, hide a secret file (specific rules first!)
permissions=[
    FilesystemPermission(operations=["read", "write"], paths=["/workspace/.env"], mode="deny"),
    FilesystemPermission(operations=["read", "write"], paths=["/workspace/**"], mode="allow"),
    FilesystemPermission(operations=["read", "write"], paths=["/**"], mode="deny"),
]

# Read-only memories/policies stored in StoreBackend routes
permissions=[FilesystemPermission(operations=["write"], paths=["/memories/**", "/policies/**"], mode="deny")]
```

The read-only-memories pattern is the standard way to ship org policies the agent can read but not rewrite (see [[memory]]).

Order bug to avoid: putting `allow /workspace/**` before `deny /workspace/.env` means the deny is never reached.

## Interrupt mode (approval)

```python
from langgraph.checkpoint.memory import InMemorySaver

agent = create_deep_agent(
    model="anthropic:claude-sonnet-5",
    permissions=[FilesystemPermission(operations=["write"], paths=["/secrets/**"], mode="interrupt")],
    checkpointer=InMemorySaver(),  # required to pause/resume
)
```

- `create_deep_agent` converts interrupt rules into `interrupt_on` entries (`_build_interrupt_on_from_permissions`) for `HumanInTheLoopMiddleware`, each with a `when` predicate so only matching calls pause. Decisions allowed: `approve`, `edit`, `reject`, `respond`. Merged with your `interrupt_on`; your entries win per tool name. Resume flow: [[human-in-the-loop]].
- Works for `"read"` rules too (code builds entries for `ls/read_file/glob/grep` when an interrupt rule includes `"read"`), although docs only describe writes.
- Scope: `read_file/write_file/edit_file` fire on exact path match. `ls/glob/grep/delete` are "bulk": they fire if their search subtree could overlap the rule's literal anchor; `grep` with no `path` fires for any interrupt rule. Unanchored patterns like `/**/secrets` collapse to `/` and over-fire. Anchor patterns (`/secrets/**`, `/projects/*/secrets/**`).
- Interrupt rules also match the symlink-resolved target (0.7.25+); a call that a deny rule blocks on either path does not pause, it fails.
- Approved results are not filtered afterward (interrupt paths pass the result filter); `edit`ed calls re-enter the tool and still hit deny checks.

## delete semantics

- Directory (or empty directory, or any target that may have descendants): all-or-nothing. `write` permission is checked on the target and every descendant pattern; any deny refuses the whole delete with the matching deny patterns listed.
- Plain file: evaluated like `write_file` (first-match-wins), so an earlier narrow `allow` beats a later catch-all `deny` (`>=0.7.3`).

## Subagents

- Declarative subagents inherit the parent `permissions` unless their spec has `"permissions": [...]`, which **replaces** (not merges) the parent list. The general-purpose subagent uses the parent's rules. See [[subagents]].

```python
subagents=[{
    "name": "auditor",
    "description": "Read-only code reviewer",
    "system_prompt": "Review the code for issues.",
    "permissions": [
        FilesystemPermission(operations=["write"], paths=["/**"], mode="deny"),
        FilesystemPermission(operations=["read"], paths=["/workspace/**"], mode="allow"),
        FilesystemPermission(operations=["read"], paths=["/**"], mode="deny"),
    ],
}]
```

## Execution-capable backends

If the backend supports `execute` (a sandbox, `LocalShellBackend`, or a `CompositeBackend` whose default is a sandbox), `FilesystemMiddleware` raises `NotImplementedError` at construction unless **every** permission path starts with one of the composite's route prefixes. A shell could bypass path rules, so only route-scoped rules are accepted.

```python
composite = CompositeBackend(default=sandbox, routes={"/memories/": memories_backend})
create_deep_agent(model=m, backend=composite,
    permissions=[FilesystemPermission(operations=["write"], paths=["/memories/**"], mode="deny")])  # OK
# paths=["/workspace/**"] or ["/**"] -> NotImplementedError
# Plain LocalShellBackend / sandbox (not composite) + any permissions -> NotImplementedError
```

## Permissions vs other controls

| Need | Use |
| - | - |
| Path allow/deny on built-in tools | `permissions` |
| Approval before sensitive file ops | `mode="interrupt"` or `interrupt_on` ([[human-in-the-loop]]) |
| Audit, rate limits, content checks, custom tools | Backend wrapper / subclass ([[backends]]) |
| Shell containment | [[sandboxes]]; for Deep Agents Code see [[dcode-safety]] |

## Gotchas

- Default is permissive: no matching rule = allowed. Add a trailing `/**` deny to make an allowlist.
- Rules are ordered; specific before broad.
- Docs say permissions "do not apply to sandbox backends"; code is stricter: combining non-route-scoped permissions with any execute-capable backend raises `NotImplementedError` at agent build time.
- Permission matching is on the virtual path (after `validate_path` normalization). The one exception is `FilesystemBackend`: its symlink target is matched too, as a virtual path in `virtual_mode=True`, or as the real host path without its drive in `virtual_mode=False`. Write rules for the target as well as the link.
- A custom backend's `glob` that returns relative paths bypasses deny filtering.
- Subagent `permissions` replace, not extend, the parent's.

## Sources

- `../sources/docs/oss/python/deepagents/permissions.md`
- `../sources/docs/oss/python/deepagents/backends.md`
- `../sources/package/deepagents/middleware/filesystem.py`
- `../sources/package/deepagents/middleware/_fs_interrupt.py`
- `../sources/package/deepagents/middleware/permissions.py`
- `../sources/package/deepagents/graph.py`

## See also

- [[index]]
- [[backends]]
- [[filesystem-tools]]
- [[sandboxes]]
- [[human-in-the-loop]]
- [[subagents]]
- [[memory]]
- [[create-deep-agent]]
- [[dcode-safety]]
- [[production]]

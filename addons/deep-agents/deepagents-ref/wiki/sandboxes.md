---
title: Sandboxes (execute tool, BaseSandbox, providers)
id: sandboxes
type: how-to
status: code
product: sdk
keywords: grep_exclude_dirs, sandbox, sandboxes, execute tool, run code, shell access, BaseSandbox, LangSmithSandbox, DaytonaSandbox, ModalSandbox, E2BSandbox, RunloopSandbox, isolated environment, run shell commands, install packages, SandboxBackendProtocol
read_when: Read when the agent must run shell commands, tests or install packages, when choosing or writing a sandbox provider, or when execute is missing or file ops fail in a custom image.
updated: 2026-10-21
sources_hash: 4618d77e3162
---

# Sandboxes (execute tool, BaseSandbox, providers)

A sandbox is a [[backends]] backend that also implements `execute`, so the agent gets a shell in an isolated remote environment; use it whenever the agent must run code, install packages, or run tests without touching your host.

## Quick reference

- A sandbox is a backend implementing `execute`; `execute` is exposed only if the backend or Composite `default` is a `SandboxBackendProtocol`.
- Built in: `LangSmithSandbox(sandbox=client.create_sandbox())` (the docs now say `pip install langsmith`; the package still mentions the `langsmith[sandbox]` extra for `timeout=0`); others are external packages (Daytona, Modal, E2B, Runloop, etc.).
- Always delete the sandbox in `try/finally` or use `idle_ttl_seconds`; leaked sandboxes cost money.
- Custom `BaseSandbox` must implement `execute(command, *, timeout=None)`, `id`, `upload_files`, `download_files`; image needs `python3` and POSIX coreutils.
- Agent plane is the file tools via `execute`; app plane is `upload_files`/`download_files` (absolute paths, bytes).
- `execute` per-call `timeout` must be `0 <= t <= 3600`; exit code is in `ToolMessage.artifact["exit_code"]`, `status` stays `success`.
- Sandbox default in a `CompositeBackend`: routed paths (e.g. `/memories/`) go to the store and the shell cannot see them.
- Isolation does not stop prompt injection or egress; never put secrets in the sandbox.
- `permissions` cannot constrain the shell; only route-scoped paths are accepted, else `NotImplementedError`.
- Never share a sandbox across threads/users (file leakage); scope one per thread.

## What the agent gets

- All file tools (`ls, read_file, write_file, edit_file, delete, glob, grep`) implemented inside the sandbox, plus `execute(command, timeout=None)` (see [[filesystem-tools]]).
- `execute` appears only if the backend is a `SandboxBackendProtocol` (or a `CompositeBackend` whose `default` is). `LocalShellBackend` also qualifies but is **not** isolated.
- Sandboxes are for acting on an environment. For in-loop code that composes tools and data without a shell, see [[interpreters]].

## Basic usage (LangSmith, built in)

```python
# pip install langsmith   (docs, 2026-10; older docs said "langsmith[sandbox]")
from deepagents import create_deep_agent
from deepagents.backends import LangSmithSandbox   # also deepagents.backends.langsmith
from langsmith.sandbox import SandboxClient

client = SandboxClient()
ls_sandbox = client.create_sandbox()               # name=..., idle_ttl_seconds=... supported
backend = LangSmithSandbox(sandbox=ls_sandbox)

agent = create_deep_agent(model="anthropic:claude-sonnet-5", backend=backend,
                          system_prompt="You are a Python coding assistant with sandbox access.")
try:
    agent.invoke({"messages": [{"role": "user", "content": "Create a small package and run pytest"}]})
finally:
    client.delete_sandbox(ls_sandbox.name)          # sandboxes cost money until deleted
```

`LangSmithSandbox`: default command timeout 1800 s (`timeout=0` disables it when the `langsmith[sandbox]` extra is installed, per the code), `enable_capture_offload = True`, `id` = sandbox name, native async via the SDK async client (call `await backend.aclose()` to release it; one event loop per instance).

## Providers (external packages)

| Class | Package | Wraps |
| - | - | - |
| `DaytonaSandbox` | `langchain-daytona` | `DaytonaSandbox(sandbox=Daytona().create())`; stop with `sandbox.stop()` |
| `ModalSandbox` | `langchain-modal` | `ModalSandbox(sandbox=modal.Sandbox.create(app=modal.App.lookup("your-app")))`; `terminate()` |
| `AgentCoreSandbox` | `langchain-agentcore-codeinterpreter` | `AgentCoreSandbox(interpreter=CodeInterpreter(region="us-west-2"))` after `interpreter.start()` |
| `RunloopSandbox` | `langchain-runloop` | `RunloopSandbox(devbox=RunloopSDK(bearer_token=...).devbox.create())`; `devbox.shutdown()` |
| `E2BSandbox` | `langchain-e2b` | `E2BSandbox(sandbox=e2b.Sandbox.create())`; `kill()` |
| `VercelSandbox` | `langchain-vercel-sandbox` | `VercelSandbox(sandbox=vercel.sandbox.Sandbox.create(runtime="python3.13"))`; `stop()` |
| `OpenShellSandbox` | `langchain-nvidia-openshell` | `OpenShellSandbox(sandbox=openshell.Sandbox(delete_on_exit=True))` |

Also listed in the integrations index: OpenSandbox, Opsen, Runtime, Kubernetes, Nono, Islo, Baponi, Upstash Box, Leap0, Novita, Superserve, Lizard. These are docs only; none ship in the 0.7.29 package except `LangSmithSandbox`. Deep Agents Code wires sandboxes with `--sandbox` ([[dcode]]); managed hosting: [[managed-capabilities]].

## How it works: BaseSandbox

`deepagents.backends.sandbox.BaseSandbox(SandboxBackendProtocol, ABC)` implements every file operation by running generated scripts through `execute()`:

- `ls`, `read`, `glob`, grep-with-path-glob, edit, write-preflight run `python3 -c "..."` scripts (args base64-encoded); plain `grep` (0.7.25+) runs `rg -HnF0` when the sandbox has `rg` and the root is a directory, else GNU `grep -rHnFZ`; both are fixed-string, and a genuine failure such as an unreadable root is swallowed and looks like "no matches". Directories in the class attribute `grep_exclude_dirs` (default `(".git",)`) are skipped at any depth; extend it (for example with `node_modules`) or set `()` in a subclass. **The sandbox image needs `python3` and POSIX coreutils.**
- `read`: server-side pagination; text page capped at 500 KiB (`MAX_OUTPUT_BYTES`) with a "continue with larger offset" note; binary returned base64 up to 500 KiB (`MAX_BINARY_BYTES`), else error.
- `write`: mkdir parents via preflight, then `upload_files([(path, bytes)])` (overwrites).
- `edit`: inline script for payloads up to 50,000 bytes, else old/new strings uploaded as temp files and replaced server-side.
- `glob`: walk budget 5 s, max 10,000 matches, max 1000 brace expansions; prunes `/proc`, `/sys`, `/dev` at root.

Abstract methods you must implement: `execute(command, *, timeout=None) -> ExecuteResponse`, `id` (property), `upload_files`, `download_files`. (Docs say "only `execute()`"; code also requires the other three.)

```python
from deepagents.backends.sandbox import BaseSandbox
from deepagents.backends.protocol import ExecuteResponse, FileUploadResponse, FileDownloadResponse

class DockerSandbox(BaseSandbox):
    enable_capture_offload = False   # opt in only if image has POSIX sh + coreutils

    def __init__(self, container): self._c = container
    @property
    def id(self) -> str: return self._c.id
    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        code, out = self._c.exec_run(["sh", "-c", command])      # your SDK
        return ExecuteResponse(output=out.decode(), exit_code=code, truncated=False)
    def upload_files(self, files):   # list[tuple[str, bytes]] -> list[FileUploadResponse]
        ...
    def download_files(self, paths): # list[str] -> list[FileDownloadResponse]
        ...
```

Accept the `timeout` kwarg on `execute`; if absent, the `execute` tool rejects per-call timeouts (`execute_accepts_timeout`). `ExecuteResponse(output, exit_code=None, truncated=False)`.

## The execute tool output

```
4
[Command succeeded with exit code 0]
```
```
bash: foobar: command not found
[Command failed with exit code 127]
```

Per-call `timeout` must be `0 <= t <= max_execute_timeout` (3600). Large output is offloaded to `/large_tool_results/<tool_call_id>` (inside the sandbox when capture offload is on) and the model gets a preview plus a `read_file` pointer. Exit code is on `ToolMessage.artifact["exit_code"]`; `status` stays `"success"`.

## Two planes of file access

- Agent plane: the tools above, which run through `execute()` in the sandbox.
- App plane: `backend.upload_files([("/src/index.py", b"...")])` to seed (absolute paths, `bytes`), and `backend.download_files(["/output.txt"])` to retrieve artifacts. These use provider-native transfer APIs; each response has `.path`, `.content` (download) and `.error`.

```python
for r in backend.download_files(["/src/index.py", "/output.txt"]):
    print(r.path, r.content.decode() if r.content is not None else r.error)
```

## Lifecycle and scoping

- Thread-scoped (default choice): one sandbox per thread, looked up by name (`f"thread-{thread_id}"`) inside an async graph factory `async def agent(config: RunnableConfig)`, with `idle_ttl_seconds` so idle ones get cleaned up.
- Assistant-scoped: one per `assistant_id`; state (files, packages, clones) accumulates, so use TTLs/snapshots/cleanup.
- Patterns: "sandbox as tool" (agent on your server, calls provider API; keys stay outside; used in all docs examples) vs "agent in sandbox" (image with `deepagents-code` installed, needs your own comms layer, keys inside sandbox). More in [[production]].

## Composite with a sandbox default

`CompositeBackend(default=sandbox, routes={"/memories/": StoreBackend(...)})`: file ops under `/memories/` go to the store; everything else and all `execute` calls go to the sandbox. The shell cannot see routed paths. Offload capture works only when `/large_tool_results/` falls through to the sandbox default.

## Security

- Isolation protects the host, not against prompt/context injection: an injected agent has full control inside the sandbox and can exfiltrate over the network unless the provider blocks egress.
- Never put secrets in a sandbox (env vars, files, provider `secrets`). Keep authenticated calls in host-side [[tools]], or use a credential-injecting proxy where the provider supports it.
- If you must: [[human-in-the-loop]] on all tools, block network, narrow short-lived creds, monitor egress.
- [[permissions]] cannot constrain the shell; with a sandbox backend only route-scoped permission paths are accepted (else `NotImplementedError`).

## Gotchas

- Forgetting teardown leaks paid sandboxes; wrap `invoke` in `try/finally` or use TTLs.
- Custom images without `python3` break `read/ls/glob/edit` even though `execute` works.
- `grep` no longer finds matches under `.git/` unless the search is rooted there (0.7.25). Set `grep_exclude_dirs = ()` on your subclass if you need them.
- `enable_capture_offload` defaults to `False` on `BaseSandbox`; only `LangSmithSandbox` opts in.
- AgentCore examples use relative paths for `upload_files` (`"hello.py"`); other providers expect absolute paths.
- A sandbox reused across threads leaks one user's files to another.

## Sources

- `../sources/docs/oss/python/deepagents/sandboxes.md`
- `../sources/docs/oss/python/integrations/sandboxes/index.md`
- `../sources/package/deepagents/backends/sandbox.py`
- `../sources/package/deepagents/backends/langsmith.py`
- `../sources/package/deepagents/backends/protocol.py`
- `../sources/package/deepagents/backends/composite.py`
- `../sources/package/deepagents/middleware/filesystem.py`

## See also

- [[index]]
- [[backends]]
- [[filesystem-tools]]
- [[permissions]]
- [[interpreters]]
- [[human-in-the-loop]]
- [[production]]
- [[dcode]]
- [[managed-capabilities]]
- [[tools]]

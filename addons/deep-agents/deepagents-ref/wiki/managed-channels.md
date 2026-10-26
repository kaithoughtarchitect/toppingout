---
title: MDA channels, identity, schedules and MCP endpoint
id: managed-channels
type: how-to
status: sourced
product: managed
keywords: MDA Slack, channels.slack, channels.http, webhook, HTTP channel, define_identity, identity.py, Supabase, define_schedule, cron, schedules, runtime.schedules, reminders, scheduled agent, Slack reactions, MCP endpoint, /mcp, interrupt_on Slack, attach_file, user_prompt_response, INTERRUPT_CORRELATION_KEY
read_when: Read when wiring a Managed Deep Agent to Slack or a webhook, controlling who can call it, adding a cron schedule, or exposing it over MCP.
updated: 2026-10-21
sources_hash: 78878a317948
---

# MDA channels, identity, schedules and MCP endpoint

Everything that decides who can start a Managed Deep Agent run and how: Slack and HTTP channels (`channels/`), agent-owned Slack interrupts, caller identity (`identity.py`), cron schedules (`schedules/`), and the `/mcp` endpoint that lets other agents call yours. Overview: [[managed]]; file rules: [[managed-project]].

## Quick reference

- Slack: `channel = channels.slack(name=..., description=...)` in `channels/slack.py`; one per deployment; `mda channels init slack` adds it; deploy cannot use `--no-wait`.
- Slack HITL supports only approve and reject; channel messages need an @mention unless `trigger_on_all_messages=True`, DMs always trigger.
- Slack file transfer (>=0.8.0) needs a sandbox; incoming files land in `/workspace/attachments/`, send back with `attach_file(path)`, and say so in `instructions.md`.
- HTTP channel (>=0.8.0): `channels.http(provider=..., verify=..., parse=...)` serves `POST /channels/<name>/events`; `verify` is the only auth, so check a signature on `raw_body`.
- HTTP `thread_id` must be a UUID (map external IDs with `uuid.uuid5`); 202 means accepted, not finished.
- Identity: `define_identity(auth=...)` with `auth.langsmith_api_key()` (default), `auth.supabase(...)`, or 'backend' plus `MDA_INGRESS_SECRET`. API-key callers are services with no private threads.
- Schedules: `define_schedule(cron=..., timezone=..., prompt=...)`; 5-field cron only, static literals only, exactly one of `prompt` or `input`.
- Since 0.9.3 `mda dev` creates the schedules on the local server, so they fire locally (`--no-schedules` stops that); on deploy, crons are created only after `DEPLOYED` and recreated on every deploy.
- Runtime schedules (>=0.9.0): tools you write call `runtime.schedules.create(owner=..., cron=... or at=..., prompt=...)`; max 20 per owner per agent by default.
- Every deployment serves `<DEPLOYMENT_API_URL>/mcp` with the agent as one tool named after `name`; send an `x-api-key` header, since URL-only clients hit a misleading OAuth error.
- Gotcha: agent-owned interrupt tools re-run from the top on resume; guard side effects.

## Channels (`channels/<name>.py`)

- One module per channel, module-level `channel`; file stem = channel name (unique; `channels/channel.py` forbidden). Only direct children of `channels/` count.
- Flow: provider event -> verify/normalize -> resolve identity + thread -> run -> post final reply.
- Runs carry `runtime.channel` (name, `provider`, normalized `event`, optional `raw_event`, optional `post`). Since 0.9.0 (breaking) that is the only place for delivery data: on channel runs `runtime.context` is `None`, and the reply target is private (no code can read or change it). Replace `runtime.context.channel["event"]` with `runtime.channel.event`. Direct API runs keep `context` validated against your `context_schema`; check `runtime.channel` to tell the two apart.
- `post({"type": "content", "content": "..."})` or `post({"type": "native", "native": {...}})` sends an *additional* message; the final agent reply is still automatic.
- A channel thread is owned by its source conversation (`mda:source-thread:{provider}:{key}`), not by the first sender (0.7.0).
- Channel vs MCP connector: channels start runs; connectors give tools ([[managed-capabilities]]).

### Slack

```bash
uvx --from managed-deepagents mda init my-agent --channel slack   # new project
uv run mda channels init slack                                     # existing project
```

```python
# channels/slack.py
from managed_deepagents import channels

channel = channels.slack(
    name="Support Agent",                  # 1-35 chars
    description="Answers order questions", # <=139 chars
    icon="support-agent.png",              # relative to channels/, 512x512 PNG <=1MB; auto-generated if omitted
    background_color="#1d4ed8",
    trigger_on_all_messages=False,         # False: channel msgs need an @mention; DMs always trigger
    allow_bot_triggers=False,
)
```

- Reactions (0.9.0): the bot reacts to the message that starts a run with `eyes` by default. `channels.slack(..., reactions=False)` turns it off; a short name picks another emoji; a sync or async callable gets `{"text": ...}` and returns a short name (errors, or more than five seconds, fall back to the default).
- One Slack channel per deployment. `mda deploy` provisions the Slack app; if LangSmith is not yet authorized it prints an HTTPS link, you approve, press Enter. After first deploy the bot DMs you. Cannot use `--no-wait`. Redeploy to apply name/icon changes.
- HITL from `interrupt_on` renders in Slack with **only `approve` and `reject`** ([[human-in-the-loop]]).
- File transfer (>=0.8.0, requires a sandbox): incoming files land in `/workspace/attachments/`; agent sends files via the `attach_file(path)` tool (path under `/workspace`). Never automatic, so say it in `instructions.md`. 200 MiB each way; files scoped to the Slack thread's sandbox; everyone in the thread can reach them.
- Slack user-owned connections: Slack renders the OAuth connect link and resumes the run.

### HTTP webhook channel (>=0.8.0)

```python
# channels/orders.py  ->  POST https://<deployment-url>/channels/orders/events
import hashlib, hmac, json, os, uuid
from managed_deepagents import HttpChannelParseResult, HttpChannelRequest, channels

NS = uuid.UUID("6f0c9a3e-8f1a-4f5e-9c2b-7d4e1a2b3c4d")

def verify(ctx: HttpChannelRequest) -> bool:        # may be async; False -> 401, raise -> 500
    digest = hmac.new(os.environ["ORDERS_WEBHOOK_SECRET"].encode(), ctx.raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={digest}", ctx.request.headers.get("x-orders-signature", ""))

def parse(ctx: HttpChannelRequest) -> HttpChannelParseResult:
    event = json.loads(ctx.raw_body)
    if event.get("type") != "order.comment":
        return {"type": "ignore"}
    return {"type": "message",
            "message": {"user_id": str(event["actor"]["id"]),
                        "thread_id": str(uuid.uuid5(NS, str(event["order"]["id"]))),  # MUST be a UUID
                        "content": event["comment"]["body"],
                        "target": str(event["order"]["id"])},
            "raw_event": event}

channel = channels.http(provider="orders", verify=verify, parse=parse)  # optional post=, on_error=
```

- `verify` is the only auth on this public route; always check a signature against `raw_body`.
- `provider` namespaces caller IDs for Agent Auth (same provider across channels = same principal).
- Either result shape may include `"response"` (Starlette `Response`), e.g. to answer a verification challenge.
- `post(input: HttpChannelPostInput) -> HttpPostedMessage` (async): `input["type"]` is `"content"` or `"native"`, `input["target"]`; return `{"id": ..., "url"?: ...}`. No reply if the run paused on an interrupt or already delivered its final message. `on_error(error, target)` replaces the default error reply.
- Responses: `202 accepted` (with `deliveryId`) / `202 ignored`; `400` bad payload/shape/message; `401` bad signature; `500` verify raised / runtime not configured / run failed to start. 202 means accepted, not finished.
- Use env vars for channel secrets; `connections.get` needs a run.

### Agent-owned interrupts (Slack forms, >=0.8.0)

Your tool posts Block Kit and calls `interrupt()`; the button/modal answer arrives as a `user_prompt_response` event and resumes the run.

```python
from langchain.tools import tool
from langgraph.types import interrupt
from langsmith import uuid7
from managed_deepagents import INTERRUPT_CORRELATION_KEY, ManagedDeepAgentRuntime, connections

@tool(parse_docstring=True)
async def request_approval(amount: str, runtime: ManagedDeepAgentRuntime) -> str:
    """Ask the requester to approve a spend.

    Args:
        amount: The spend, e.g. "$1,200".
    """
    ch = runtime.channel
    if ch is None or ch.provider != "slack":
        return "Approval forms are available only in Slack."
    cid = str(uuid7())
    if ch.event["type"] != "user_prompt_response":     # tool re-runs on resume: post once
        token = await connections.get("mda/slack-bot-token", {"type": "agent"})
        ...  # chat.postMessage into raw_event thread; button value = json.dumps({INTERRUPT_CORRELATION_KEY: cid})
    response = interrupt({INTERRUPT_CORRELATION_KEY: cid, "amount": amount})
    return f"The requester chose {response['action']} for {amount}."
```

- Response fields: `provider`, `action` (button `action_id` / modal `callback_id`), `value`, `correlation_id` (`INTERRUPT_CORRELATION_KEY == "mda_correlation_id"`).
- Matching: one parked + no id -> resumes it; id matches exactly one -> resumes it; several parked + no id, or id matches none/several -> nothing runs; none parked -> fresh run, answer only on `runtime.channel.event`.
- Modal: button `action_id` starting `mda_modal::` with the full view JSON as `value` (<=2000 chars); platform sets `callback_id` and `private_metadata` (setting it yourself blocks the modal). Modals never carry a correlation id.
- Failure modes: dismissed modal leaves interrupt parked forever; replying in thread abandons the checkpoint; double-press = resume + fresh turn.
- `runtime.channel.post` for built-in Slack is text-only; use the Web API for blocks. Studio shows the raw interrupt value.

## Identity (`identity.py`)

`mda init` scaffolds the API-key default. `define_identity` takes only `auth=` (scope/credentials/connect were removed in 0.5.0).

| Mode | Declaration | Client sends | Per-user private threads |
| - | - | - | - |
| LangSmith API key (default) | `define_identity(auth=auth.langsmith_api_key())` | `x-api-key` | No (service principal) |
| Supabase | `define_identity(auth=auth.supabase(project_ref="..."))` (or `url=`) | `Authorization: Bearer <access_token>` | Yes |
| Your backend | `define_identity(auth="backend")` + `MDA_INGRESS_SECRET` in `.env` | `x-mda-ingress-secret` + `x-mda-user-id` | Yes |

```python
from managed_deepagents import auth, define_identity
identity = define_identity(auth=auth.supabase(project_ref="your-project-ref"))
```

- No `identity.py` = no managed auth (`mda dev` shows `Identity none`).
- Backend mode: deploy preflight fails if `MDA_INGRESS_SECRET` is missing; any secret holder can act as any user, so never ship it to clients. Keep `x-mda-user-id` stable.
- Workspace members with LangSmith API access can read/search every thread regardless of mode; privacy is against end users only.
- Adding Supabase to an existing deployment does not back-fill owner metadata on old threads.
- Errors: 401 missing/invalid credential; 403 cross-user thread access.
- Only persons get user memory ([[memory]]) and user-owned connections; API-key callers are services.

## Schedules (`schedules/<name>.py`)

```python
from managed_deepagents import define_schedule

schedule = define_schedule(
    cron="0 8 * * 1-5",                    # 5-field only; UTC if no timezone
    timezone="America/Los_Angeles",
    prompt="Write the daily digest.",      # exactly one of prompt= / input=
    # input={"messages": [{"role": "user", "content": "..."}]},
    # thread={"mode": "persistent", "id": "<existing-thread-uuid>"},
    # deliver_to={"channel": "slack", "to": {"type": "provider_conversation", "conversation_id": "C0123456789"}},
)
```

- Values must be static literals or top-level literal constants: no env reads, function calls, `**kwargs`.
- Default threads are ephemeral (new thread, deleted after run). Persistent mode needs a UUID of a thread that already exists (create it in Studio; MDA will not).
- Provisioned as LangSmith crons only after `DEPLOYED`; each deploy deletes the crons that earlier `schedules/` files created and recreates them from current files (runtime schedules are untouched). `--no-wait` skips this.
- `mda dev` (>=0.9.3) creates a local cron for each schedule and recreates them when `schedules/` changes; pass `--no-schedules` while iterating. Before 0.9.3 schedules were listed in the banner but never fired locally.
- Errors: `Schedule limit reached`, `must export a named schedule declaration`, `must define exactly one of prompt or input`, `cron must be a standard 5-field expression`, `schedule is not static`, `Invalid thread ID: must be a UUID (HTTP 422)`.

### Runtime schedules (>=0.9.0)

`runtime.schedules` (on the runtime tools and middleware receive) creates schedules while the agent runs, acting for the current caller. The agent reaches it only through tools you write.

```python
from langchain.tools import tool
from managed_deepagents import ManagedDeepAgentRuntime

@tool
async def remind_me(prompt: str, cron: str, runtime: ManagedDeepAgentRuntime, timezone: str = "UTC") -> str:
    """Run a prompt for the current user on a cron schedule."""
    item = await runtime.schedules.create(owner={"type": "user"}, cron=cron, timezone=timezone, prompt=prompt)
    return f"Created schedule {item['id']}."
```

- `owner`: `{"type": "user"}` (the authenticated person, runs as them) or `{"type": "agent"}` (runs as the agent's service identity).
- Exactly one of `cron` (5-field, with optional `timezone`) or `at` (timezone-aware datetime or ISO 8601 with offset; rounded up to the minute; 1 minute to 365 days ahead). Exactly one of `prompt` or `input`. Also `new_thread` (default `True` for `cron`, `False` for `at`), `paused`, `metadata` (`mda_` keys reserved).
- Created during a channel run, the schedule inherits that channel and posts each answer there. Scheduled runs can't create more schedules (0.9.0 changelog).
- `list`, `get`, `update` (`cron`, `at`, `timezone`, `prompt`, `input`, `paused`, `metadata`), `delete`, each with `owner=`. Channel and thread choice are fixed at creation.
- Limit: 20 per owner per agent, paused ones included; override with `MDA_MAX_AGENT_SCHEDULES` / `MDA_MAX_USER_SCHEDULES` (>=0.9.3).

## MCP endpoint (`<DEPLOYMENT_API_URL>/mcp`)

Every deployment serves Agent Server's Streamable HTTP MCP endpoint; the agent appears as one tool named after `define_deep_agent(name=...)`. Opposite direction from MCP connectors ([[mcp]]).

```python
from fastmcp.client import Client
from fastmcp.client.transports import StreamableHttpTransport
from langchain.mcp import MCPAdapter

async with MCPAdapter(Client(StreamableHttpTransport(
    "<DEPLOYMENT_API_URL>/mcp",
    headers={"x-api-key": os.environ["LANGSMITH_API_KEY"]},
))) as adapter:
    tools = await adapter.list_tools()   # docs switched from langchain_mcp_adapters on 2026-09-30 ([[mcp]])
```

Any MCP client that can send a custom header works the same way: Streamable HTTP transport, the `/mcp` URL, and an `x-api-key` header.

- Auth follows identity mode. Use the API-key default for MCP clients (they cannot mint Supabase tokens). Key must belong to the deployment's workspace. Errors: 401 `missing x-api-key`, 403 `API key is forbidden`, 403 `API key tenant mismatch`.
- A URL-only client falls back to OAuth and reports a misleading Dynamic Client Registration failure; set the header.
- Stateless: calls share no thread state; use agent memory for cross-call knowledge.
- `mda dev` serves `/mcp` with no auth (unscoped local service principal).

## Gotchas

- Slack HITL supports only approve/reject; edit decisions are unavailable there.
- HTTP `thread_id` must be a UUID (400 otherwise); map external IDs with `uuid.uuid5`.
- Agent-owned interrupt tools re-execute from the top on resume; guard side effects.
- Upgrading to 0.7.0 orphaned in-flight Slack conversations (thread ownership change).
- Supabase is the only validated-token provider (auth0/okta/etc. removed in 0.5.0).
- The HTTP channel docs' `parse` example imports `uuid7` from `langsmith` but calls `uuid.UUID` and `uuid.uuid5` without `import uuid`, so it fails with `NameError`. Import `uuid` as the example above does.

## Sources

- `../sources/docs/langsmith/python/managed-deep-agents-channels.md`
- `../sources/docs/langsmith/python/managed-deep-agents-channels-slack.md`
- `../sources/docs/langsmith/python/managed-deep-agents-channels-http.md`
- `../sources/docs/langsmith/python/managed-deep-agents-agent-owned-interrupts.md`
- `../sources/docs/langsmith/python/managed-deep-agents-identity.md`
- `../sources/docs/langsmith/python/managed-deep-agents-schedules.md`
- `../sources/docs/langsmith/python/managed-deep-agents-mcp-endpoint.md`
- `../sources/docs/langsmith/python/managed-deep-agents-runtime.md`
- `../sources/docs/github/managed-deepagents-CHANGELOG.md`

## See also

- [[index]]
- [[managed]]
- [[managed-project]]
- [[managed-capabilities]]
- [[managed-dev]]

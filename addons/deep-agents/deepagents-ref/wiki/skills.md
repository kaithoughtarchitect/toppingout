---
title: Skills (SKILL.md, progressive disclosure)
id: skills
type: how-to
status: code
product: sdk
keywords: skills, SKILL.md, SkillsMiddleware, skills=, pinned_skills, pin a skill, include_tools, skill tools, SkillToolResolver, disclosed_skill_tool_names, progressive disclosure, agent skills, reusable procedures, playbooks, skills_metadata, reload skills, task-specific instructions, skill directory, allowed-tools
read_when: Read when adding task-specific procedures the agent loads on demand, when skills load zero, a new or edited skill does not appear, or a subagent lacks skills.
updated: 2026-10-21
sources_hash: 6c4d247ae301
---

# Skills (SKILL.md, progressive disclosure)

One-line truth: a skill is a directory with a `SKILL.md` (YAML frontmatter + instructions); `skills=[...]` points `SkillsMiddleware` at *parent* directories, it lists every skill's name/description in the system prompt, and the agent `read_file`s the full body only when a task matches. Reach for it for task-specific procedures too big to live in [[memory]].

## Quick reference

- `create_deep_agent(skills=["/skills/"])` points at the parent directory of skill folders, each containing `SKILL.md`; pointing at the skill folder itself silently loads zero.
- `SKILL.md` needs YAML frontmatter with `name` and `description` (else skipped); name must equal directory name (only warns); description truncated at 1024 chars.
- Only name and description sit in the prompt; the agent `read_file`s the body on demand. Discovery is one level deep.
- Later source wins on a name clash; the SDK never auto-scans `~/.deepagents` (that is Deep Agents Code).
- StateBackend seeding: `invoke({"files": {path: create_file_data(text)}})`; raw strings are not accepted.
- Skills load once per thread when a checkpointer exists; reload with `{"skills_metadata": None}` (needs `deepagents>=0.7.16`), never `[]`.
- General-purpose subagent inherits `skills=`; custom declarative subagents get none unless their spec sets `"skills"`.
- Pin a skill the user named: pass `pinned_skills=["name"]` in the input (`>=0.7.23`).
- Skill-only tools: list them under `metadata.include_tools` and pass them as `SkillsMiddleware(tools=...)` (`>=0.7.22`); the model sees them only after reading the skill.
- Running `scripts/*.py` needs a sandbox backend; StoreBackend skill files are not inside the sandbox.
- Make a library read-only with `FilesystemPermission(operations=["write"], paths=["/skills/**"], mode="deny")`.

## Layout and format

```
/skills/                      <- this is what you pass in skills=[...]
  langgraph-docs/             <- directory name == frontmatter name
    SKILL.md
    scripts/fetch_docs.py     <- optional, agent reads/runs only if SKILL.md says so
    references/api.md
    assets/template.md
```

```md
---
name: langgraph-docs
description: Fetch LangGraph docs to answer LangGraph questions. Use when the user asks about LangGraph APIs, graphs, checkpointers.
license: MIT                      # optional
compatibility: Requires internet  # optional, <=500 chars
metadata: {author: me, version: "1.0"}   # optional, values coerced to str
allowed-tools: fetch_url          # optional, experimental; space/comma string or YAML list
---
# langgraph-docs
1. fetch https://docs.langchain.com/llms.txt ...
```

Parsing rules (code, `middleware/skills.py`):
- Frontmatter must match `^---\s*\n(.*?)\n---\s*\n` at file start and be a YAML mapping; else skipped (warning logged).
- `name` and `description` required, else skipped.
- Name rules (1-64 chars, lowercase alnum + single hyphens, must equal directory name) only **warn**; the skill still loads.
- `description` > 1024 chars is truncated; `compatibility` > 500 truncated.
- `SKILL.md` > 10 MB (`MAX_SKILL_FILE_SIZE`) skipped.
- Discovery = `ls(source)` -> each subdirectory -> download `<dir>/SKILL.md`. Only one level deep. Passing a skill directory itself finds nothing and raises nothing.

## Passing skills

```python
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    skills=["/skills/org/", "/skills/user/"],       # later source wins on name clash
    backend=CompositeBackend(
        default=StateBackend(),
        routes={
            "/skills/org/":  StoreBackend(namespace=lambda rt: ("skills", rt.context.org_id)),
            "/skills/user/": StoreBackend(namespace=lambda rt: ("skills", rt.context.user_id)),
        },
    ),
)
```

- Paths are backend paths, POSIX, forward slashes.
- `StateBackend` (default): seed via `agent.invoke({"messages": [...], "files": {"/skills/x/SKILL.md": create_file_data(text)}})`; raw strings are not accepted, use `deepagents.backends.utils.create_file_data`.
- `StoreBackend` / `FilesystemBackend`: `backend.upload_files([("/skills/x/SKILL.md", text.encode())])` before creating the agent, or seed the store directly. Route prefixes are stripped: skill at `/skills/x/SKILL.md` under route `/skills/` is store key `"/x/SKILL.md"`.
- `FilesystemBackend(root_dir=..., virtual_mode=True)` to keep paths under `root_dir`.
- The SDK never auto-scans `~/.deepagents/...` or `~/.agents/...`; that is Deep Agents Code behaviour ([[dcode-extending]]). Emulate CLI layering by passing sources lowest-to-highest precedence.
- Hand-built middleware also accepts `(path, label)` tuples: `SkillsMiddleware(backend=b, sources=[("/repo/.claude/skills", "Project Claude")])`. The label renders as `**{label} Skills**`; default label is the capitalized last path segment (a trailing `skills` climbs to its parent).

## What the model sees

`SKILLS_SYSTEM_PROMPT` appended to the system message: source locations (last marked "(higher priority)"), then per skill:

```
- **langgraph-docs**: <description> (License: MIT, Compatibility: ...)
  -> Allowed tools: fetch_url
  -> Read `/skills/org/langgraph-docs/SKILL.md` for full instructions
```

plus instructions to `read_file(path, limit=1000)` (default read is 100 lines). With no skills: "(No skills available yet. You can create skills in ...)". Source-level `ls` errors appear as an escaped `<skill_load_warnings>` block (max 20, 1000 chars each). There is no dedicated skill-reading tool; level 2/3 loading is ordinary `read_file` ([[filesystem-tools]]). Stack position (0.7.29): after your middleware and profile extras, right before prompt caching, on the main agent and in subagents ([[middleware]]). Your own middleware therefore runs before it and can't see this turn's freshly loaded `skills_metadata` or edit the skills prompt section; replace `SkillsMiddleware` by name if you need that.

## Loading lifecycle and reload

- `before_agent` loads only when `skills_metadata` is missing or `None`; a list (even `[]`) means "already loaded". So with a checkpointer skills load **once per thread**; without one, every run.
- Reload (needs `deepagents>=0.7.16`):

```python
agent.invoke({"messages": msgs, "skills_metadata": None}, config)   # reload + run
agent.update_state(config, {"skills_metadata": None})               # reload on next run
```

- Use `None`, never `[]` (empty list = "no skills" for the rest of the thread).
- A middleware can request reload from `after_agent` (not `after_model`: mid-run it would blank the list for remaining calls). `SkillsState` is importable from `deepagents.middleware`.
- Changed skill list changes the system prompt and busts the prompt cache for that thread.

## Pin a skill (`pinned_skills`)

When the user or your app already knows which skill applies (a `/skill-name` command, a menu pick), pin it instead of hoping the model picks it. Needs `deepagents>=0.7.23`.

```python
result = agent.invoke(
    {
        "messages": [{"role": "user", "content": "/langgraph-docs How do I add a checkpointer?"}],
        "pinned_skills": ["langgraph-docs"],
    },
    config={"configurable": {"thread_id": "1"}},
)
```

- `pinned_skills` is a state key on `SkillsState` (names only, matched exactly against `skills_metadata`). In `before_model`, `SkillsMiddleware` reads each named `SKILL.md`, strips the frontmatter, and appends one `HumanMessage` per skill in the order named: `<skill name="..." path="...">body</skill>`.
- Each pinned message has `additional_kwargs["lc_source"] == "pinned_skill"` and `additional_kwargs["skill"] == {"name", "path", "description"}`, so a UI can show a label instead of the text.
- The message is a snapshot: editing `SKILL.md` later doesn't change it; pinning again appends a new copy. Earlier messages never change, so the prompt cache holds.
- Unknown names and unreadable (or over 10 MB, or non-UTF-8) files are skipped with a debug log, no error. The key is cleared once used (reducer appends, so parallel tool calls can each pin).
- Deep Agents does not parse skill names out of messages. Your app finds them (e.g. a regex for `/name`) and passes them in `pinned_skills`.
- `pinned_skills` is not passed to or from subagents, and a fork does not resume the parent's pending pins.

## Skill tools (`metadata.include_tools`)

A skill can bring tools the model only sees after it reads that skill. Needs `deepagents>=0.7.22`. This is a Deep Agents feature, unrelated to the spec's `allowed-tools` field.

```yaml
---
name: linear
description: Triage and file Linear issues. Use when the user reports a bug.
metadata:
  include_tools: list_issues create_issue    # space-separated string, NOT a YAML list
---
```

```python
from deepagents import create_deep_agent
from deepagents.middleware import SkillsMiddleware

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    backend=backend,
    middleware=[SkillsMiddleware(backend=backend, sources=["/skills/"], tools=[list_issues, create_issue])],
)   # no skills= needed: the passed SkillsMiddleware supplies it
```

- `SkillsMiddleware(..., tools=...)` takes a list of tools (plain functions are converted) or a `SkillToolResolver`: `(name: str, runtime: Runtime) -> Sequence[BaseTool]`, sync or async (async needs `ainvoke`). A resolver maps a readable name to generated tool names (MCP) or to many tools. It runs on every model call after the read and again before each skill tool call, so keep it cheap and return the same tools for the same name within a thread or the prompt cache breaks.
- Gated: until the model `read_file`s the skill's `SKILL.md` (or the skill is pinned), a call to a skill tool fails as an unknown tool. When summarization drops that read or pinned message, the tool disappears again.
- Skill tools are kept off `self.tools`, so they are not registered with the tool node on their own. Passing a tool to the agent's `tools=` instead makes it always visible, so `include_tools` then has no effect, unless the tool is deferred (`extras={"defer_loading": True}`), in which case reading the skill reveals it without a search.
- When a skill lists a tool the agent already has (including built-ins such as `edit_file`), the agent's tool wins.
- How a disclosed tool reaches the model: on Anthropic and OpenAI chat models whose profile sets `mid_conversation_tools`, it is inserted mid-conversation (cache stays valid); otherwise it is added to the request's `tools` (cache invalidated).
- `include_tools` as a YAML list, or with commas, logs a warning and matches nothing. Unmatched names log at DEBUG only.
- `disclosed_skill_tool_names(state)` (from `deepagents.middleware.skills`) returns the skill tools shown to the latest model call, for middleware that gates tool calls itself.

## Subagents

- General-purpose subagent: inherits the main `skills=` (code: GP stack appends `SkillsMiddleware(sources=skills)`). If you passed a `SkillsMiddleware` in `middleware=` instead of `skills=`, its sources become `skills` and the GP subagent inherits your instance by name (tools included).
- Custom declarative subagent: gets **none** unless its spec has `"skills": [...]` or a `SkillsMiddleware` in its own `middleware`.
- `mode="fork"` subagents inherit the parent's skills and may not set `skills` (`ValueError`).
- `skills_metadata`, `pinned_skills` and the private `_skill_tools_disclosed` record are excluded from state passed to/from subagents, so they never leak either way. See [[subagents]].

## Permissions

- Read-only library: `FilesystemPermission(operations=["write"], paths=["/skills/**"], mode="deny")`.
- Mixed: route `/skills/approved/` (org, denied) and `/skills/editable/` (user, writable), pass both in `skills=`; put specific rules before broad ones (first match wins).
- Approve writes: `mode="interrupt"` (`deepagents>=0.6.8`, needs checkpointer) or `interrupt_on={"write_file": True, "edit_file": True}`. See [[permissions]], [[human-in-the-loop]].
- Agents can author their own skills with `write_file` under writable paths; this is "progressive-disclosure memory". Pair with the reload pattern or the new skill only appears in the next thread.

## Executing skill scripts

Reading works on any backend; running `scripts/*.py` needs a shell, i.e. a sandbox backend ([[sandboxes]]). Skill files stored in a `StoreBackend` route are not inside the sandbox: copy them in with a `before_agent` middleware (`backend.aupload_files([...])`) and copy edits back in `after_agent` (docs' full skills+memory sync example lives in the production guide, see [[production]]).

## Skills vs memory vs tools

| | Skills | Memory | Tools |
| - | - | - | - |
| Loading | name+description always; body on demand | full content every call | schema every call |
| Layering | later source wins by name | concatenated in order | fixed at creation |
| Use for | task-specific, possibly long procedures | always-relevant conventions/preferences | programmatic actions |

## Authoring guidance (docs)
- Description is the only thing used for selection: say what + when + keywords; differentiate overlapping skills or merge them.
- Body under ~5,000 tokens / 500 lines; push detail to `references/`, keep references one level deep, say when to open each file.
- Fewer well-scoped skills beat many overlapping ones.

## Gotchas
- Pointing `skills=` at the skill directory instead of its parent silently loads zero skills.
- Name/directory mismatch only warns; spec validators (`skills-ref`) will still flag it.
- Deployed agents always checkpoint, so edited skills do not appear in ongoing threads until you reset `skills_metadata` to `None`.
- Custom subagents do not inherit skills; GP subagent does.
- The skills prompt fragment is kept even though other built-in tool prose was removed in 0.7; it is the only channel for the skill index.
- In the assembled prompt, the skills block still comes before the memory block (Skills runs before caching, Memory after).
- Before 0.7.29 Skills was first in the main stack. Custom middleware that read `skills_metadata` in `before_model` (expecting it loaded) or edited the skills prompt in `wrap_model_call` now runs before Skills and sees neither.
- `include_tools` must be one space-separated string; a YAML list silently matches no tool (only a warning in the log).
- A skill tool passed to the agent's `tools=` (not deferred) is always visible; gating only works for tools passed to `SkillsMiddleware(tools=...)`.

## Sources
- `../sources/docs/oss/python/deepagents/skills.md`
- `../sources/docs/oss/python/deepagents/memory.md`
- `../sources/package/deepagents/middleware/skills.py`
- `../sources/package/deepagents/graph.py`
- `../sources/package/deepagents/middleware/subagents.py`

## See also
- [[index]]
- [[memory]]
- [[backends]]
- [[permissions]]
- [[subagents]]
- [[sandboxes]]
- [[context-engineering]]
- [[dcode-extending]]
- [[managed-capabilities]]
- [[agent-builder-memory]]

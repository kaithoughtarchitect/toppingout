---
title: Models and profiles
id: models
type: how-to
status: code
product: sdk
keywords: model, provider:model, init_chat_model, choose model, switch model, OpenRouter, Ollama, Bedrock, Azure OpenAI, harness profile, HarnessProfile, provider profile, ProviderProfile, register_harness_profile, register_provider_profile, use_responses_api, excluded_tools, runtime model switching
read_when: Read when picking or configuring a model, tuning behaviour per model, excluding a tool or middleware for one model, or a profile does not apply.
updated: 2026-10-21
sources_hash: 898ffbacb6f7
---

# Models and profiles

Deep Agents runs on any LangChain chat model that supports tool calling. Pass a `"provider:model"` string (resolved with `init_chat_model` plus a *provider profile*) or a pre-built `BaseChatModel`; after the model exists, a *harness profile* keyed by provider/model reshapes prompts, tools and middleware. Reach for this page when choosing, configuring, or per-model-tuning the model.

## Quick reference

- Model = `"provider:model"` string (only the first colon splits) or a `BaseChatModel` instance; strings resolve via `init_chat_model` + provider profile.
- Set model kwargs (e.g. `thinking_level`, `use_responses_api`) by building the instance yourself; provider profiles apply only to strings.
- OpenAI strings default to `use_responses_api=True`; pass an instance for Chat Completions or zero data retention.
- OpenRouter needs `langchain-openrouter>=0.2.0`; it ignores Azure upstream unless `DEEPAGENTS_OPENROUTER_ALLOW_AZURE=1`.
- Harness profile (`HarnessProfile`, beta) reshapes prompts/tools/middleware per model; register with `register_harness_profile("openai:gpt-5.5", ...)`.
- Fields include `system_prompt_suffix`, `excluded_tools` (frozenset), `excluded_middleware`, `extra_middleware`, `general_purpose_subagent`.
- Re-registering a key merges, not replaces; there is no wildcard key.
- Runtime model swap via `@wrap_model_call` + `context_schema`; profile and summarization thresholds stay fixed to the build-time model.
- Gotcha: a bare string like `"claude-sonnet-4-6"` gets no harness profile; always use `provider:model`.
- Gotcha: `FilesystemMiddleware` and `SubAgentMiddleware` cannot be excluded.

## Model strings

- Format `provider:model`; only the **first** colon separates (e.g. `ollama:minimax-m2.7:cloud` -> provider `ollama`, model `minimax-m2.7:cloud`). Valid providers = `init_chat_model`'s `model_provider` values.
- Examples from docs: `openai:gpt-5.5`, `anthropic:claude-sonnet-4-6`, `google_genai:gemini-3.6-flash`, `azure_openai:gpt-5.5`, `openrouter:z-ai/glm-5.2`, `fireworks:accounts/fireworks/models/glm-5p2`, `baseten:zai-org/GLM-5.2`, `ollama:...`.
- Install the integration: `pip install -U "langchain[openai]"` / `[anthropic]` / `[google-genai]` / `[aws]`, `langchain-openrouter>=0.2.0`, etc. (`langchain-anthropic` and `langchain-google-genai` ship as deepagents deps.)
- Suggested (pass the Deep Agents eval suite): Google `gemini-3.1-pro-preview`, `gemini-3.6-flash`; OpenAI `gpt-5.5`, `gpt-5.4`; Anthropic `claude-opus-4-8`, `claude-opus-4-7`, `claude-opus-4-6`; open-weight `GLM-5.2`, `Kimi-K2.7 Code`, `MiniMax-M3` (via Baseten, Fireworks, OpenRouter, Ollama).

## How a string is resolved (code: `deepagents/_models.py`)

```python
def resolve_model(model: str | BaseChatModel) -> BaseChatModel:
    if isinstance(model, BaseChatModel):
        return model
    return init_chat_model(model, **apply_provider_profile(model))
```

Provider-profile kwargs apply **only** to strings. A pre-built instance is used unchanged.

## Configure parameters: build the model yourself

```python
from langchain.chat_models import init_chat_model
from deepagents import create_deep_agent

model = init_chat_model("google_genai:gemini-3.6-flash", thinking_level="medium")
agent = create_deep_agent(model=model)
```

OpenAI: strings get `use_responses_api=True` from the built-in provider profile. For Chat Completions or zero data retention, pass an instance:

```python
model = init_chat_model("openai:gpt-5.5", use_responses_api=False)            # chat completions
model = init_chat_model("openai:gpt-5.5", use_responses_api=True, store=False,
                        include=["reasoning.encrypted_content"])            # no retention
```

## OpenRouter

`create_deep_agent(model="openrouter:z-ai/glm-5.2")` with `OPENROUTER_API_KEY`. The built-in `openrouter` provider profile (`profiles/provider/_openrouter.py`):
- `pre_init` raises `ImportError` if `langchain-openrouter` < `0.2.0` (skipped if not installed; `init_chat_model` then errors itself).
- Injects `app_url="https://github.com/langchain-ai/deepagents"` and `app_title="Deep Agents"` unless env `OPENROUTER_APP_URL` / `OPENROUTER_APP_TITLE` are set (empty string counts as set = opt out).
- Injects `openrouter_provider={"ignore": ["azure"]}` (Azure upstream breaks multi-turn reasoning replay). Re-allow with `DEEPAGENTS_OPENROUTER_ALLOW_AZURE=1|true|yes|on`.

**Model ids.** Format is `openrouter:<vendor>/<slug>`, with the slug exactly as on openrouter.ai (`https://openrouter.ai/<vendor>/<slug>`). Only the first colon splits provider from model. List every slug with `curl -s https://openrouter.ai/api/v1/models`.

**Starter default: GPT-6 Luna** (checked against the OpenRouter models API, 2026-09-29):
- `create_deep_agent(model="openrouter:openai/gpt-6-luna")`, `pip install "langchain-openrouter>=0.2.0"`, env `OPENROUTER_API_KEY`.
- Context 1,050,000 tokens. Supported params include `tools`, `tool_choice`, `reasoning`, `reasoning_effort`, `response_format`, `structured_outputs`, `max_tokens`, `seed`. **`temperature` isn't listed.**
- Related slugs: `openai/gpt-6-luna-pro`; `:batch` variants; `~openai/gpt-luna-latest` (floating alias, so avoid it for reproducibility).
- Harness profile: none built in for this string, so there's no prompt suffix and no extra middleware. The `openrouter` provider profile above still applies (Azure ignore, attribution) because it's a string. Register your own with `register_harness_profile("openrouter:openai/gpt-6-luna", HarnessProfile(...))` if needed.
- The Deep Agents docs never mention GPT-6 Luna (the dcode docs show `openai:gpt-5.6-luna`). Since 0.7.29 the `SummarizationMiddleware` docstring uses `openai:gpt-6-luna` as a cheaper `summarizer=` example ([[summarization]]). The rest of this entry comes from OpenRouter, not LangChain.

Other built-in provider profiles: `openai` (`use_responses_api=True`), `nvidia` (header `X-BILLING-INVOKE-ORIGIN: DeepAgents`).

## Provider profiles (model construction)

```python
from deepagents import ProviderProfile, register_provider_profile

register_provider_profile("openai", ProviderProfile(init_kwargs={"temperature": 0}))
register_provider_profile("openai:gpt-5.5", ProviderProfile(init_kwargs={"reasoning_effort": "medium"}))
```

Fields: `init_kwargs: Mapping` (merged key-wise, new wins), `pre_init: Callable[[str], None]` (chained, existing first), `init_kwargs_factory: Callable[[], dict]` (chained, outputs merged per construction). Model-level key merges on top of provider-level key. Caller kwargs beat profile kwargs.

## Harness profiles (agent shaping)

```python
from deepagents import GeneralPurposeSubagentProfile, HarnessProfile, register_harness_profile

register_harness_profile(
    "openai:gpt-5.5",
    HarnessProfile(
        system_prompt_suffix="Respond in under 100 words.",
        excluded_tools=frozenset({"execute"}),
        excluded_middleware=frozenset({"SummarizationMiddleware"}),
        general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
    ),
)
```

`HarnessProfile` fields (frozen dataclass, beta API):

| Field | Type / default | Effect | Merge |
| - | - | - | - |
| `base_system_prompt` | `str or None` | Main agent: `BASE` after caller prompt. Declarative subagent: **replaces** its authored prompt. | new wins |
| `system_prompt_suffix` | `str or None` | Appended last on main, declarative subagents and GP subagent | new wins |
| `tool_description_overrides` | `Mapping[str,str]` (read-only proxy) | Rewrites fs tools, `task` (keep `{available_agents}`!), `BaseTool`/dict tools | per key |
| `excluded_tools` | `frozenset[str]` | Hidden and non-executable (post-injection filter); not a security surface | union |
| `excluded_middleware` | `frozenset[type or str]` | Strip by exact class or `.name`; `FilesystemMiddleware` / `SubAgentMiddleware` rejected; unmatched entries raise | union |
| `extra_middleware` | sequence or zero-arg factory | Appended to main, GP and declarative subagent stacks (not compiled/async) | by concrete type |
| `general_purpose_subagent` | `GeneralPurposeSubagentProfile or None` | `enabled` (None/True/False), `description`, `system_prompt` | field-wise |

Built-in harness profiles in 0.7.29 (registered lazily on first registry access):
- `anthropic:claude-sonnet-4-6`, `anthropic:claude-haiku-4-5`: suffix with parallel-tool-calls, investigate-before-answering, tool-result-reflection blocks.
- `anthropic:claude-opus-4-7`: same plus `<tool_usage>` and `<subagent_usage>` blocks.
- `openai:gpt-5.1-codex`, `gpt-5.2-codex`, `gpt-5.3-codex`: Codex behaviour suffix + `extra_middleware=[TodoListMiddleware()]` (so these models get `write_todos`, see [[planning]]).
- Nemotron 3 Ultra specs (`nvidia:`, `NVIDIA:`, `baseten:`, `fireworks:`, `openrouter:`, `nebius:`, `together:`): suffix, `read_file` description override, 12 extra middleware (retry, tool-call parsing, final-answer guards).

No provider-wide built-in for `anthropic` or `openai`; other models (e.g. `claude-sonnet-5`, `gpt-5.5`) get an empty profile.

### Lookup

- String model: the string itself is the key. Exact `provider:model`, merged over the bare `provider` profile if both exist; else provider only; else empty profile.
- Model instance: try `f"{ls_provider}:{model_name}"`, then identifier if it contains `:`, then the provider's profile. Provider comes from `model._get_ls_params()["ls_provider"]`.
- Subagents resolve their own profile from their own model.
- Re-registering a key merges (does not replace). Load order: built-ins, then entry-point plugins (`deepagents.harness_profiles`, `deepagents.provider_profiles` groups), then your calls. No wildcard key.

### Config files

`HarnessProfileConfig.from_dict(yaml.safe_load(f))` covers the declarative subset (prompts, overrides, excluded tools/middleware as strings incl. `module:Class`, GP edits); `register_harness_profile` accepts either type. `HarnessProfileConfig.from_harness_profile(p)` exports; raises if `extra_middleware` is set.

## Runtime model switching

```python
from dataclasses import dataclass
from langchain.agents.middleware import wrap_model_call
from langchain.chat_models import init_chat_model

@dataclass
class Context:
    model: str

@wrap_model_call
def configurable_model(request, handler):
    return handler(request.override(model=init_chat_model(request.runtime.context.model)))

agent = create_deep_agent(model="google_genai:gemini-3.6-flash",
                          middleware=[configurable_model], context_schema=Context)
agent.invoke({"messages": [...]}, context=Context(model="openai:gpt-5.5"))
```

Note: the harness profile, summarization thresholds and prompt are fixed at build time for the construction model, not the swapped one ([[context-engineering]]).

## Gotchas

- **Profiles are beta.** The API reference (refreshed 2026-09-30) marks `deepagents.profiles` (`HarnessProfile`, `ProviderProfile`, `register_*_profile`) as beta: they "may receive minor changes in future releases". Re-check this page on every version bump.

- A bare string without provider (e.g. `"claude-sonnet-4-6"`, used in some docs snippets) still resolves via `init_chat_model` inference, but profile lookup keys on the raw string, so **no harness profile applies**. Always use `provider:model`.
- Provider profiles (OpenAI Responses default, OpenRouter attribution/Azure ignore) are skipped for model instances.
- Summarization defaults depend on `model.profile["max_input_tokens"]`: fraction triggers (0.85 / keep 0.10) when present, else 170k tokens / keep 6 messages ([[summarization]]).
- `excluded_tools` in docs examples is sometimes a plain `set`; the field is typed `frozenset[str]`; use `frozenset(...)`.
- Profiles docs say the "internal permission middleware" cannot be excluded; in code only `FilesystemMiddleware` and `SubAgentMiddleware` are protected (permissions live inside `FilesystemMiddleware`).
- Chat models auto-retry transient API failures; tune `max_retries` / `timeout` on the model instance.

## Sources

- `../sources/docs/oss/python/deepagents/models.md`
- `../sources/docs/oss/python/deepagents/profiles.md`
- `../sources/docs/oss/python/deepagents/quickstart.md`
- `../sources/package/deepagents/_models.py`
- `../sources/package/deepagents/middleware/summarization.py` (`summarizer` docstring example)
- `../sources/package/deepagents/profiles/_builtin_profiles.py`
- `../sources/package/deepagents/profiles/harness/harness_profiles.py`
- `../sources/package/deepagents/profiles/harness/_anthropic_opus_4_7.py`
- `../sources/package/deepagents/profiles/harness/_openai_codex.py`
- `../sources/package/deepagents/profiles/harness/_nvidia_nemotron_3_ultra.py`
- `../sources/package/deepagents/profiles/provider/_openrouter.py`
- `../sources/package/deepagents/profiles/provider/_openai.py`
- `../sources/package/deepagents/profiles/provider/_nvidia.py`

## See also

- [[index]]
- [[harness]]
- [[create-deep-agent]]
- [[customization]]
- [[middleware]]
- [[subagents]]

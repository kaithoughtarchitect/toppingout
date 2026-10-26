---
title: Multimodal input, read_file media, video frames
id: multimodal
type: concept
status: code
product: sdk
keywords: multimodal, image input, images, audio, video, PDF, file blocks, content blocks, read_file media, video frames, UnsupportedContentMiddleware, deepagents[video], screenshot, vision, unsupported content
read_when: Read when passing images/audio/video/files to an agent, read_file media fails, or blocks are replaced by a text notice.
updated: 2026-10-21
sources_hash: 9a2af3b84d45
---

# Multimodal input, read_file media, video frames

One-line truth: Deep Agents pass LangChain standard content blocks (image/audio/video/file) through unchanged when the model supports them; `read_file` turns media files into content blocks (videos into sampled JPEG frames with the `[video]` extra), and `UnsupportedContentMiddleware` (auto-added, last in the stack) swaps blocks the active model can't accept for a text notice.

## User input

```python
agent.invoke({"messages": [{"role": "user", "content": [
    {"type": "text", "text": "What is in this screenshot?"},
    {"type": "image", "url": "https://example.com/screenshot.png"},
    # or {"type": "image", "base64": B64, "mime_type": "image/png"}
]}]})
```

## Custom tool output

Return a list of content blocks (see [[tools]]); it becomes a `ToolMessage` whose `.content_blocks` the model reads next turn. MCP tools can do the same ([[mcp]]).

```python
from langchain.tools import tool

@tool
def capture_screenshot() -> list[dict]:
    """Capture a screenshot of the current page."""
    return [{"type": "text", "text": "Screenshot:"},
            {"type": "image", "url": "https://example.com/page.png"}]
```

Prefer saving large media to the backend and returning a short description + path ([[backends]]).

## read_file on media (`FilesystemMiddleware`)

Extension map (`backends/utils.py _EXTENSION_TO_FILE_TYPE`):

| Block | Extensions |
| - | - |
| `image` | `.png .jpg .jpeg .gif .webp .heic .heif` |
| `video` | `.mp4 .mpeg .mov .avi .flv .mpg .webm .wmv .3gpp` (+ `.mkv` only when `[video]` extra installed) |
| `audio` | `.wav .mp3 .aiff .aac .ogg .flac` |
| `file` | `.pdf .ppt .pptx` |

- Non-text result = single block `{"type": <block>, "base64": ..., "mime_type": mimetypes.guess_type(...) or "application/octet-stream"}` in a `ToolMessage` with `additional_kwargs={"read_file_path", "read_file_media_type"}`.
- Any backend result with `encoding == "base64"` is treated as binary even if the extension is unknown → generic `file` block.
- `offset`/`limit` are ignored for images/PDFs (text-only pagination).
- `edit_file` on a binary file stored in `StateBackend`/`StoreBackend` returns `Error: Cannot edit binary files with text replacements.` (0.7.29); `grep` there skips binary files.

## Video: sampled frames (`middleware/_video.py`)

Install: `pip install "deepagents[video]"` (PyAV `av>=18,<19` + `pillow>=12.3,<13`). Detection is `find_spec("av")` and `find_spec("PIL.Image")`; when present, `read_file` switches to a video-aware schema/description.

- `offset` = seconds to skip, `limit` = seconds to sample (default `limit=100` → first 100 s). `limit <= 0` → tool error.
- Fixed sampling rate `0.5` fps (one frame every 2 s); not configurable by the agent.
- Output: `ToolMessage` "Read video X: sampled N frames. The sampled frames are attached in the following message." **plus** a synthetic `HumanMessage` (returned via `Command`) holding a header text block and interleaved `"Frame at t=HH:MM:SS.mmm"` text + JPEG `image` blocks (quality 85).
- Caps: ≤64 frames, ≤4 MiB encoded output, 10 s decode wall-clock, frames downscaled to fit 1920x1080, frames with a side >4096 px rejected, input file ≤1 GiB (`MAX_VIDEO_INPUT_BYTES`). Hitting frame/byte cap appends "Coverage truncated at t=... Continue from offset=...".
- Errors (bad base64, no video stream, decode failure, missing deps) come back as `status="error"` `ToolMessage`s so the agent can retry with a smaller window.
- Without the extra, videos are returned as a raw `video` base64 block (whole file).
- `FilesystemMiddleware` reorders so these synthetic media `HumanMessage`s always follow the full `ToolMessage` batch of that turn (provider tool-call ordering rules).

## When the model can't take it

Two layers:

1. `UnsupportedContentMiddleware` (`deepagents.middleware`), appended last on the main agent **and** every declarative subagent. On each model call it inspects `HumanMessage`/`ToolMessage` blocks against `model.profile`:
   - `image`→`image_inputs`, `audio`→`audio_inputs`, `video`→`video_inputs`, `file`→`pdf_inputs`; inside a `ToolMessage` also `image_tool_message` / `pdf_tool_message`.
   - Missing profile field = supported; only an explicit `False` rejects.
   - `file` blocks that are URL/ID-backed, or non-base64, are always passed. Base64 non-PDF documents (`.docx`, `.pptx`, ...) are passed only to `ChatOpenAI`/`AzureChatOpenAI` with `use_responses_api` truthy and a MIME in `_OPENAI_FILE_MIME_TYPES`; otherwise replaced.
   - Replacement text: `[read_file: <path> was not attached because this model does not support <type> content (<mime>).]`. Request-only: the thread keeps the original, so switching to a capable model resends it.
2. `FilesystemMiddleware.wrap_model_call` catches `ModelInvalidRequestError`; if the failing request contains `read_file` media added since the last AI message, it replaces those messages' content with "Unsupported content. The file may be invalid, too large, or of an unsupported mime-type." and retries once. This replacement **is written to state** (permanent).

Manual use with plain LangChain:

```python
from langchain.agents import create_agent
from deepagents.middleware import FilesystemMiddleware, UnsupportedContentMiddleware
agent = create_agent(model, middleware=[FilesystemMiddleware(), UnsupportedContentMiddleware()])  # keep it last
```

## Context compression

- Tool-result offloading measures text only; image blocks are preserved, and an image-only message is never offloaded for size.
- Summarization produces text-only summaries: media in summarized turns is gone from active context (the model sees only what the summarizer wrote). Recent kept messages are untouched. See [[summarization]], [[context-engineering]].
- Checkpoint size: `FilesystemMiddleware(offload_binary_content=True)` (0.7.21+) moves binary `read_file` results and inline user media to `blobs/` on the backend and keeps only a reference in history; each model request is rehydrated. It needs a non-state backend for `blobs/` ([[backends]]).
- For media-heavy work: store in backend, pass paths/URLs, delegate image inspection to a subagent that returns text ([[subagents]]), tune summarization thresholds / token counter for image-heavy providers.

## Gotchas

- **Before 0.7.20**, `StateBackend.upload_files` stored binary files as base64 text but tagged them `encoding: "utf-8"`, so `read_file` treated an uploaded image or PDF as text. Fixed in 0.7.20 (2026-09-29): binary uploads are tagged `base64` and come back as media blocks. If you're on 0.7.19, upload binaries through a store or sandbox backend instead.

- The unsupported-content placeholder always says `read_file:` — even for a user-attached image (path falls back to "the requested file"). Don't mistake it for a tool bug.
- `_VIDEO_SAMPLING_RATE = 0.5` is documented in code as "seconds between sampled frames" but is used as frames-per-second (header says "at 0.5 fps"): effective spacing is 2 s. Code behavior wins.
- Docs' extension table omits `.mkv` (video-extra only) and don't mention the video extra at all; the code's `read_file` description does.
- Model profiles are incomplete; an unknown model with no profile gets everything passed through and may 400 — layer 2 only rescues `read_file` media, not user-attached media. See [[models]].
- Video frames are sent as a `HumanMessage`, so they count as user input for provider gating (`image_inputs`), not `image_tool_message`.
- Offloaded large human messages (`human_message_token_limit_before_evict`, default 50000 tokens) are a separate `FilesystemMiddleware` feature; see [[filesystem-tools]].

## Sources
- `../sources/docs/oss/python/deepagents/multimodal.md`
- `../sources/docs/oss/python/deepagents/tools.md` (multimodal tool outputs)
- `../sources/package/deepagents/middleware/_video.py`
- `../sources/package/deepagents/middleware/unsupported_content.py`
- `../sources/package/deepagents/middleware/filesystem.py`
- `../sources/package/deepagents/middleware/subagents.py`
- `../sources/package/deepagents/backends/utils.py`
- `../sources/package/deepagents/graph.py`
- `../sources/package/deepagents/middleware/_blob_offload.py`
- `../sources/package/deepagents/backends/state.py`
- `../sources/package/deepagents-0.7.29.dist-info/METADATA` (`video` extra)

## See also
- [[index]]
- [[tools]]
- [[filesystem-tools]]
- [[backends]]
- [[summarization]]
- [[context-engineering]]
- [[subagents]]
- [[models]]
- [[middleware]]
- [[mcp]]
- [[versions]]

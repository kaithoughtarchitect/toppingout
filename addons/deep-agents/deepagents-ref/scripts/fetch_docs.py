"""Refresh sources/docs/ from the live LangChain docs (Python Deep Agents + Deep Agents Code + Managed).

Discovery reads docs.langchain.com's llms.txt indexes, so new pages are picked up automatically.
Raw pages are overwritten in place; git shows what changed. Manifest: sources/docs/MANIFEST.md.

    python scripts/fetch_docs.py            (fetch everything)
    python scripts/fetch_docs.py --list     (print the URL set only)
"""

from __future__ import annotations

import datetime as dt
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "sources" / "docs"
BASE = "https://docs.langchain.com"
INDEXES = (
    f"{BASE}/_llms/agent-development-lifecycle/build/python.md",
    f"{BASE}/_llms/agent-development-lifecycle/build.md",
    f"{BASE}/_llms/products-and-setup.md",
)
KEEP = (
    re.compile(r"^/oss/python/deepagents/"),
    re.compile(r"^/oss/deepagents/code/"),
    re.compile(r"^/langsmith/python/managed-deep-agents"),
)
EXTRA = (
    "/oss/python/integrations/backends/index.md",
    "/oss/python/integrations/sandboxes/index.md",
    "/oss/python/langchain/deep-agent-from-scratch.md",
    "/oss/python/concepts/products.md",
    "/oss/python/reference/deepagents-python.md",
    # Pages that moved out of the Deep Agents section (the old URLs redirect here).
    "/oss/python/langchain/mcp/index.md",
    "/oss/python/langchain/mcp/tools.md",
    "/langsmith/server-a2a.md",
    "/oss/openwiki/overview.md",
)
OFF_SITE = {
    # Upstream repo README, LangChain's Agent Builder memory blog post, and the changelogs.
    "github/deepagents-README.md": "https://raw.githubusercontent.com/langchain-ai/deepagents/main/README.md",
    "blog/agent-builder-memory.md": "https://www.langchain.com/blog/how-we-built-agent-builders-memory-system",
    # Changelogs: the docs pages now redirect to these GitHub files.
    "github/deepagents-CHANGELOG.md": "https://raw.githubusercontent.com/langchain-ai/deepagents/main/libs/deepagents/CHANGELOG.md",
    "github/deepagents-code-CHANGELOG.md": "https://raw.githubusercontent.com/langchain-ai/deepagents/main/libs/code/CHANGELOG.md",
    "github/managed-deepagents-CHANGELOG.md": "https://raw.githubusercontent.com/langchain-ai/managed-deepagents/main/CHANGELOG.md",
}
# Doc URLs that redirect to HTML; fetch the original instead.
REPLACE = {
    "/oss/python/reference/deepagents-python.md": "https://reference.langchain.com/python/deepagents",
}
LINK_RE = re.compile(r"\((https://docs\.langchain\.com(/[^)\s]+?\.md))\)")


def get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "deepagents-context-repo/1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


INDEX_NOTE_RE = re.compile(r"\A> ## Documentation Index\n(?:>.*\n)*\n?")
JS_BLOCK_RE = re.compile(r"^export const .*?^\};?[ \t]*\n", re.S | re.M)
CSS_LINE_RE = re.compile(r"^(?:\[data-lc-|\.lc-|<PatternEmbed ).*\n", re.M)


def clean(text: str, url: str) -> str:
    """Drop the docs-site preamble and embedded JS UI components; keep prose and code."""
    if url.startswith(BASE):
        text = INDEX_NOTE_RE.sub("", text)
        text = JS_BLOCK_RE.sub("", text)
        text = CSS_LINE_RE.sub("", text)
    if "<html" in text[:2000].lower():
        text = html_to_text(text)
    return f"<!-- source: {url} -->\n{text.lstrip()}"


def html_to_text(html: str) -> str:
    from html.parser import HTMLParser

    skip_tags = ("script", "style", "nav", "footer", "svg", "head")

    class P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.out, self.skip = [], 0

        def handle_starttag(self, tag, attrs):
            if tag in skip_tags:
                self.skip += 1
            elif tag in ("p", "br", "li", "h1", "h2", "h3", "h4", "pre", "div"):
                self.out.append("\n")
                if tag in ("h1", "h2", "h3", "h4"):
                    self.out.append("#" * int(tag[1]) + " ")
                elif tag == "li":
                    self.out.append("- ")

        def handle_endtag(self, tag):
            if tag in skip_tags:
                self.skip = max(0, self.skip - 1)

        def handle_data(self, data):
            if not self.skip:
                self.out.append(data)

    parser = P()
    parser.feed(html)
    return re.sub(r"\n\s*\n+", "\n\n", "".join(parser.out)).strip() + "\n"


def discover() -> list[str]:
    paths = set(EXTRA)
    for idx in INDEXES:
        for _, path in LINK_RE.findall(get(idx)):
            if any(k.match(path) for k in KEEP):
                paths.add(path)
    return sorted(paths)


def local_name(path: str) -> Path:
    # /oss/python/deepagents/backends.md -> oss/python/deepagents/backends.md
    return OUT / path.lstrip("/")


def fetch(path: str) -> tuple[str, int | str]:
    url = REPLACE.get(path, BASE + path)
    try:
        text = clean(get(url), url)
    except Exception as e:  # noqa: BLE001 - report and continue
        return path, f"FAILED {e}"
    dest = local_name(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8", newline="\n")
    return path, len(text)


def main() -> int:
    paths = discover()
    if "--list" in sys.argv:
        print("\n".join(paths))
        return 0
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(fetch, paths))
    for rel, url in OFF_SITE.items():
        try:
            dest = OUT / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(clean(get(url), url), encoding="utf-8", newline="\n")
            results.append((url, dest.stat().st_size))
        except Exception as e:  # noqa: BLE001
            results.append((url, f"FAILED {e}"))
    today = dt.date.today().isoformat()
    lines = [
        "# Docs manifest",
        "",
        f"Fetched {today} by `scripts/fetch_docs.py`. Raw, immutable between fetches. Local path mirrors the URL path.",
        "",
        "| Source | Bytes |",
        "|---|---|",
    ]
    lines += [f"| {BASE + p if p.startswith('/') else p} | {n} |" for p, n in results]
    (OUT / "MANIFEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    failed = [p for p, n in results if isinstance(n, str)]
    print(f"{len(results) - len(failed)} fetched, {len(failed)} failed")
    for p in failed:
        print("  ", p)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

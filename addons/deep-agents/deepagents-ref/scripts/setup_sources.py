"""Fetch the reference's sources: the deepagents package source and the LangChain docs.

Topping Out ships the wiki, not the third-party material it cites. This puts that material in sources/:

    python scripts/setup_sources.py                  fetch the package (the pinned version) and the docs
    python scripts/setup_sources.py --if-missing     only what isn't there yet (CI uses this)
    python scripts/setup_sources.py --version 0.7.30 a new package version (then follow MAINTAINING.md)

- sources/package/: `pip download deepagents==<version> --no-deps`, the wheel unpacked (deepagents/ and its
  dist-info, MIT licence included). The version is the one this reference was checked against (VERSION below).
- sources/docs/: scripts/fetch_docs.py (the live docs at docs.langchain.com).
Then it runs the wiki lint. Freshly fetched docs may differ from the ones the wiki was checked against: the lint
lists those pages as STALE, which is information, not a failure (MAINTAINING.md says how to re-check them).
Needs Python 3.11+, network access and pip. Exit 0 done (single doc pages that fail are drift, not a failure);
1 the package fetch failed, no docs arrived, or Python is too old; 2 usage.
"""
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

VERSION = "0.7.29"  # the version wiki/versions.md and the recipes were checked against
ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "sources" / "package"
DOCS = ROOT / "sources" / "docs"


def fetch_package(version):
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run([sys.executable, "-m", "pip", "download", f"deepagents=={version}", "--no-deps",
                            "--only-binary", ":all:", "-d", tmp, "-q"], capture_output=True, text=True)
        wheels = list(Path(tmp).glob("deepagents-*.whl"))
        if r.returncode or not wheels:
            print(f"FAILED: pip download deepagents=={version}: {(r.stderr or r.stdout).strip()[-400:]}")
            return False
        if PKG.exists():
            shutil.rmtree(PKG)
        PKG.mkdir(parents=True)
        with zipfile.ZipFile(wheels[0]) as z:
            z.extractall(PKG)
    print(f"package: deepagents {version} in {PKG.relative_to(ROOT).as_posix()}/", flush=True)
    return True


def fetch_docs():
    # Single pages that fail (moved or removed upstream) are drift, reported by fetch_docs.py and the lint;
    # only no docs at all is a failure.
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "fetch_docs.py")])
    pages = sum(1 for _ in DOCS.rglob("*.md")) if DOCS.is_dir() else 0
    if not pages:
        print("FAILED: scripts/fetch_docs.py fetched no docs (network?)")
        return False
    if r.returncode:
        print(f"docs: {pages} pages; some pages failed to fetch (drift: the lint below shows what the wiki misses)", flush=True)
    return True


def main(argv):
    version, if_missing = VERSION, False
    i = 0
    while i < len(argv):
        if argv[i] == "--if-missing":
            if_missing = True
        elif argv[i] == "--version" and i + 1 < len(argv):
            version = argv[i + 1]
            i += 1
        else:
            print(__doc__)
            return 2
        i += 1
    if sys.version_info < (3, 11):
        print(f"FAILED: deepagents needs Python 3.11 or later; this is {sys.version.split()[0]}")
        return 1
    ok = True
    if not (if_missing and (PKG / "deepagents").is_dir()):
        ok = fetch_package(version) and ok
    else:
        print("package: already there", flush=True)
    if not (if_missing and DOCS.is_dir() and any(DOCS.rglob("*.md"))):
        ok = fetch_docs() and ok
    else:
        print("docs: already there", flush=True)
    if not ok:
        return 1
    subprocess.run([sys.executable, str(ROOT / "scripts" / "wiki_lint.py")])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

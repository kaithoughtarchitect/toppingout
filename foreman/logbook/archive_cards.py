#!/usr/bin/env python3
"""Archive, verify and restore Logbook cards with a hash manifest.

Python 3 standard library only. Run from the repository root:

    python foreman/logbook/archive_cards.py plan    --archive NNN [--keep FILE]
    python foreman/logbook/archive_cards.py archive --archive NNN --keep FILE
    python foreman/logbook/archive_cards.py verify  --archive NNN
    python foreman/logbook/archive_cards.py restore --archive NNN

Paths in MANIFEST.json are relative to foreman/logbook/ and use POSIX
separators. Every DESTINATION copy is hashed and compared with the manifest
before any source card is deleted. The archive is never deleted. A manifest path
that could leave the logbook (backslash, colon, leading slash, empty/./.. part, or
resolving outside) is refused. Re-running `archive` after a crash resumes: an
identical earlier attempt is copied and verified again; one whose deletes were
interrupted (archive verifies, some live cards already gone) finishes the deletes.

Exit codes: 0 ok, 1 verification failure or data problem, 2 usage.
"""

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

LOGBOOK_REL = Path("foreman") / "logbook"
CARD_PATTERN = "[A-Z]*_20*.md"
CORE_FILES = ("logbook_index.md", "logbook_links.md")
MANIFEST_NAME = "MANIFEST.json"
# Files the archive folder may hold besides the manifest's own files.
ALLOWED_EXTRAS = {MANIFEST_NAME, MANIFEST_NAME + ".tmp", "MANIFEST.md"}

EXIT_OK, EXIT_DATA, EXIT_USAGE = 0, 1, 2


class UsageError(Exception):
    pass


class DataError(Exception):
    pass


# --- seams (tests replace these to inject faults) ---------------------------

def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def after_copy_hook(dst: Path) -> None:
    """Called after each copy, before destinations are verified."""


def unlink_file(path: Path) -> None:
    path.unlink()


# --- helpers -----------------------------------------------------------------

def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def is_card_name(name: str) -> bool:
    return fnmatch.fnmatchcase(name, CARD_PATTERN) and "TEMPLATE" not in name


def logbook_dir(root: Path) -> Path:
    lb = root / LOGBOOK_REL
    if not lb.is_dir():
        raise UsageError(f"no {LOGBOOK_REL.as_posix()}/ under {root}: run from the repository root")
    return lb


def archive_dir(lb: Path, number: str) -> Path:
    if not re.fullmatch(r"\d{3,}", number):
        raise UsageError(f"--archive must be digits like 001, got {number!r}")
    return lb / "archived" / number


def to_local(base: Path, rel: str) -> Path:
    """Map a manifest path to a file under base; refuse anything that could leave base.

    A manifest path is relative POSIX: no backslash (a separator on Windows), no colon
    (a drive or stream), no leading slash, and no empty, "." or ".." part. The joined
    path must also resolve inside base (catches a symlinked folder pointing out).
    """
    if not isinstance(rel, str) or not rel or "\\" in rel or ":" in rel or rel.startswith("/"):
        raise DataError(f"unsafe path in manifest: {rel!r}")
    parts = rel.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise DataError(f"unsafe path in manifest: {rel!r}")
    path = base.joinpath(*parts)
    try:
        inside = path.resolve().is_relative_to(base.resolve())
    except (OSError, RuntimeError, ValueError):
        inside = False
    if not inside:
        raise DataError(f"unsafe path in manifest (resolves outside {base}): {rel!r}")
    return path


def scan_cards(lb: Path) -> list:
    entries = lb / "entries"
    if not entries.is_dir():
        return []
    found = []
    for path in entries.rglob("*.md"):
        if path.is_file() and is_card_name(path.name):
            found.append(path.relative_to(lb).as_posix())
    return sorted(found)


def build_file_list(lb: Path) -> list:
    """Card files plus index and links, each with sha256 and size."""
    rels = scan_cards(lb)
    for core in CORE_FILES:
        if not (lb / core).is_file():
            raise DataError(f"missing {core}: the Logbook index and links must exist to archive")
        rels.append(core)
    out = []
    for rel in rels:
        p = to_local(lb, rel)
        out.append({"path": rel, "sha256": sha256_of(p), "size": p.stat().st_size})
    return out


def load_manifest(adir: Path) -> dict:
    mpath = adir / MANIFEST_NAME
    if not mpath.is_file():
        raise DataError(f"no {MANIFEST_NAME} in {adir}")
    try:
        data = json.loads(mpath.read_text(encoding="utf-8"))
        files = data["files"]
        for f in files:
            f["path"], f["sha256"], f["size"]
    except (ValueError, KeyError, TypeError) as exc:
        raise DataError(f"unreadable {MANIFEST_NAME}: {exc}")
    return data


def check_archive_dir(adir: Path, files: list):
    """Return (state, old_manifest); raise DataError if the folder holds something else.

    'new'    - no folder, or an empty one.
    'resume' - an earlier attempt with the identical file list (copy and verify again).
    'finish' - an earlier attempt whose deletes were interrupted: its manifest verifies
               against the archived copies and every live file is one the manifest lists
               (the missing live cards are the ones already deleted). The manifest is
               kept as written and only the remaining deletes run.
    """
    if not adir.exists():
        return "new", None
    if not adir.is_dir():
        raise DataError(f"{adir} exists and is not a folder")
    contents = [p for p in adir.rglob("*") if p.is_file()]
    if not contents:
        return "new", None
    if not (adir / MANIFEST_NAME).is_file():
        raise DataError(f"{adir} already holds files and no {MANIFEST_NAME}: refusing (pick the next archive number)")
    old = load_manifest(adir)
    for f in old["files"]:
        to_local(adir, f["path"])  # refuse an unsafe manifest before anything else
    expected = {PurePosixPath(f["path"]) for f in old["files"]} | {PurePosixPath(n) for n in ALLOWED_EXTRAS}
    for p in contents:
        rel = PurePosixPath(p.relative_to(adir).as_posix())
        if rel not in expected:
            raise DataError(f"{adir} holds an unexpected file {rel}: refusing")
    key = lambda fs: sorted((f["path"], f["sha256"], f["size"]) for f in fs)
    if key(old["files"]) == key(files):
        return "resume", old
    old_paths = {f["path"] for f in old["files"]}
    live_paths = {f["path"] for f in files}
    if live_paths <= old_paths and not verify_files(adir, old["files"]):
        return "finish", old
    raise DataError(f"{adir} holds a different archive: refusing (pick the next archive number)")


def read_keep(path_str: str) -> list:
    path = Path(path_str)
    if not path.is_file():
        raise UsageError(f"--keep file not found: {path_str}")
    ids = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            ids.append(line[:-3] if line.endswith(".md") else line)
    return ids


def card_id(lb: Path, rel: str) -> str:
    return PurePosixPath(rel).stem


def frontmatter_id(path: Path):
    try:
        with open(path, encoding="utf-8") as fh:
            if fh.readline().strip() != "---":
                return None
            for line in fh:
                if line.strip() == "---":
                    return None
                m = re.match(r"id:\s*(\S+)", line)
                if m:
                    return m.group(1).strip("\"'")
    except (OSError, UnicodeDecodeError):
        return None
    return None


def resolve_keep(lb: Path, files: list, keep_ids: list) -> set:
    """Map kept ids to card paths; an unknown or ambiguous id is a data problem.

    Filename ids are mapped first, frontmatter `id:` values second. An id naming two
    different cards (a frontmatter id equal to another card's filename id, or two cards
    sharing a filename) is refused rather than resolved to either one.
    """
    by_id = {}

    def add(key, path):
        prev = by_id.get(key)
        if prev is not None and prev != path:
            raise DataError(f"id {key} names two cards ({prev} and {path}): fix the duplicate before archiving")
        by_id[key] = path

    cards = [f["path"] for f in files if f["path"] not in CORE_FILES]
    for rel in cards:
        add(card_id(lb, rel), rel)
    for rel in cards:
        fid = frontmatter_id(to_local(lb, rel))
        if fid:
            add(fid, rel)
    unknown = [k for k in keep_ids if k not in by_id]
    if unknown:
        raise DataError("kept ids match no card: " + ", ".join(unknown))
    return {by_id[k] for k in keep_ids}


def verify_files(root_dir: Path, files: list) -> list:
    """Return a list of problem lines for files under root_dir."""
    problems = []
    for f in files:
        p = to_local(root_dir, f["path"])
        if not p.is_file():
            problems.append(f"MISSING  {f['path']}")
        elif sha256_of(p) != f["sha256"]:
            problems.append(f"MISMATCH {f['path']}")
    return problems


def type_counts(files: list) -> str:
    counts = {}
    for f in files:
        if f["path"] in CORE_FILES:
            continue
        kind = PurePosixPath(f["path"]).name.split("_", 1)[0]
        counts[kind] = counts.get(kind, 0) + 1
    return ", ".join(f"{n} {k}" for k, n in sorted(counts.items())) or "none"


# --- commands ----------------------------------------------------------------

def cmd_plan(root: Path, args) -> int:
    lb = logbook_dir(root)
    adir = archive_dir(lb, args.archive)
    files = build_file_list(lb)
    cards = [f for f in files if f["path"] not in CORE_FILES]
    kept = resolve_keep(lb, files, read_keep(args.keep)) if args.keep else set()
    print(f"plan: archive {args.archive} -> {adir.relative_to(root).as_posix()}/ (dry run, nothing written)")
    if not cards:
        print("plan: no cards in entries/: nothing to archive")
        return EXIT_OK
    state, _ = check_archive_dir(adir, files)
    print("plan: archive folder " + {
        "new": "is new",
        "resume": "holds an identical earlier attempt (will resume)",
        "finish": "holds a verified earlier attempt whose deletes were interrupted (will finish the deletes)",
    }[state])
    for f in cards:
        tag = "keep " if f["path"] in kept else "card "
        print(f"{tag}{f['path']}")
    for core in CORE_FILES:
        print(f"core {core} (copied, never deleted; regenerated by /f-archive)")
    print(f"plan: {len(cards)} cards ({type_counts(files)}) + {len(CORE_FILES)} core files")
    if args.keep:
        print(f"plan: keep {len(kept)} index cards in entries/, delete {len(cards) - len(kept)} after verification")
    return EXIT_OK


def cmd_archive(root: Path, args) -> int:
    lb = logbook_dir(root)
    adir = archive_dir(lb, args.archive)
    keep_ids = read_keep(args.keep)
    files = build_file_list(lb)
    cards = [f for f in files if f["path"] not in CORE_FILES]
    if not cards:
        print("archive: no cards in entries/: nothing to archive, nothing written")
        return EXIT_OK
    kept = resolve_keep(lb, files, keep_ids)
    state, old = check_archive_dir(adir, files)

    if state == "finish":
        if sorted(old.get("kept", [])) != sorted(card_id(lb, p) for p in kept):
            raise DataError(f"{adir} was written with a different keep list: refusing (use the same --keep file)")
        print(f"archive: resuming interrupted deletes; archive verified ({len(old['files'])} files match the manifest)")
        old_cards = [f for f in old["files"] if f["path"] not in CORE_FILES]
        return delete_sources(lb, old_cards, kept, args.archive)

    # 1. Manifest first.
    adir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "archive": args.archive,
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base": LOGBOOK_REL.as_posix(),
        "files": files,
        "kept": sorted(card_id(lb, p) for p in kept),
    }
    tmp = adir / (MANIFEST_NAME + ".tmp")
    tmp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, adir / MANIFEST_NAME)
    print(f"archive: manifest written ({len(files)} files){' - resuming an identical earlier attempt' if state == 'resume' else ''}")

    # 2. Copy, preserving entries/<type>/.
    for f in files:
        dst = to_local(adir, f["path"])
        copy_file(to_local(lb, f["path"]), dst)
        after_copy_hook(dst)
    print(f"archive: copied {len(files)} files")

    # 3. Hash every destination against the manifest.
    problems = verify_files(adir, files)
    if problems:
        for line in problems:
            print(f"VERIFY FAILED {line}")
        print("archive: verification failed: nothing deleted; the archive folder is kept")
        return EXIT_DATA
    print(f"archive: verified {len(files)} destination hashes")

    # 4. Delete only non-kept manifest cards whose source is unchanged.
    return delete_sources(lb, cards, kept, args.archive)


def delete_sources(lb: Path, cards: list, kept: set, number: str) -> int:
    """Unlink each non-kept card whose live bytes still match the manifest hash."""
    deleted, skipped = 0, []
    for f in cards:
        if f["path"] in kept:
            continue
        src = to_local(lb, f["path"])
        if not src.is_file():
            continue
        if sha256_of(src) != f["sha256"]:
            skipped.append(f["path"])
            continue
        unlink_file(src)
        deleted += 1
    print(f"archive: deleted {deleted} cards, kept {len(kept)} index cards; templates, index and links untouched")
    if skipped:
        for p in skipped:
            print(f"CHANGED  {p} (edited during the archive: left in place)")
        return EXIT_DATA
    print(f"archive: {number} complete; now regenerate logbook_index.md and logbook_links.md")
    return EXIT_OK


def cmd_verify(root: Path, args) -> int:
    lb = logbook_dir(root)
    adir = archive_dir(lb, args.archive)
    if not adir.is_dir():
        raise DataError(f"no archive folder {adir}")
    files = load_manifest(adir)["files"]
    problems = verify_files(adir, files)
    for line in problems:
        print(f"VERIFY FAILED {line}")
    if problems:
        print(f"verify: archive {args.archive} DAMAGED ({len(problems)} of {len(files)} files)")
        return EXIT_DATA
    print(f"verify: archive {args.archive} ok ({len(files)} files match the manifest)")
    return EXIT_OK


def cmd_restore(root: Path, args) -> int:
    lb = logbook_dir(root)
    adir = archive_dir(lb, args.archive)
    if not adir.is_dir():
        raise DataError(f"no archive folder {adir}")
    files = load_manifest(adir)["files"]
    problems = verify_files(adir, files)
    if problems:
        for line in problems:
            print(f"VERIFY FAILED {line}")
        print("restore: ARCHIVE DAMAGED: nothing restored; stop and tell the owner")
        return EXIT_DATA

    restored, present, differing, failed = [], 0, [], []
    for f in files:
        live = to_local(lb, f["path"])
        if f["path"] in CORE_FILES:
            if live.is_file() and sha256_of(live) != f["sha256"]:
                print(f"core     {f['path']} differs from the archive (left in place; the archived copy is in the archive folder)")
            continue
        if live.is_file():
            if sha256_of(live) == f["sha256"]:
                present += 1
            else:
                differing.append(f["path"])
            continue
        copy_file(to_local(adir, f["path"]), live)
        restored.append(f)
    for f in restored:
        live = to_local(lb, f["path"])
        if not live.is_file() or sha256_of(live) != f["sha256"]:
            failed.append(f["path"])
    for p in differing:
        print(f"DIFFERS  {p} (live card differs from the archive: not overwritten)")
    for p in failed:
        print(f"RESTORE FAILED {p}")
    print(f"restore: {len(restored)} restored, {present} already present, {len(differing)} differing live cards left in place")
    if failed:
        print("restore: a restored file does not match its hash: stop and tell the owner")
        return EXIT_DATA
    print(f"restore: every restored card matches its hash; archive {args.archive} kept")
    return EXIT_OK


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Archive, verify and restore Logbook cards.")
    parser.add_argument("--root", default=".", help="repository root (default: current directory)")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "archive", "verify", "restore"):
        p = sub.add_parser(name)
        p.add_argument("--archive", required=True, metavar="NNN")
        if name in ("plan", "archive"):
            p.add_argument("--keep", required=(name == "archive"), metavar="FILE",
                           help="file of index-card ids to keep, one per line")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return EXIT_USAGE if exc.code else EXIT_OK
    root = Path(args.root).resolve()
    handler = {"plan": cmd_plan, "archive": cmd_archive, "verify": cmd_verify, "restore": cmd_restore}[args.command]
    try:
        return handler(root, args)
    except UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except DataError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_DATA
    except OSError as exc:
        print(f"error: {exc} (stopped part-way; re-run the same command to resume)", file=sys.stderr)
        return EXIT_DATA


if __name__ == "__main__":
    sys.exit(main())

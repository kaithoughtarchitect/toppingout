"""Fail if skills/ folders and skills-wiki pages disagree."""

from __future__ import annotations

import sys
from pathlib import Path

EXCLUDE_PAGES = {"index", "_template"}
EXCLUDE_NAMES = {"_template.md", "readme.md"}


def repo_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    if here.is_file():
        here = here.parent
    for p in [here, *here.parents]:
        if (p / "skills").is_dir() and (p / "skills-wiki").is_dir():
            return p
    raise FileNotFoundError("repo with skills/ and skills-wiki/ not found")


def skill_folders(root: Path) -> set[str]:
    return {p.parent.name for p in (root / "skills").glob("*/SKILL.md")}


def wiki_skill_pages(root: Path) -> set[str]:
    wiki = root / "skills-wiki"
    names: set[str] = set()
    for p in wiki.glob("*.md"):
        if p.name.lower() in EXCLUDE_NAMES:
            continue
        if p.stem in EXCLUDE_PAGES:
            continue
        names.add(p.stem)
    return names


def sync_errors(root: Path) -> list[str]:
    folders = skill_folders(root)
    pages = wiki_skill_pages(root)
    errors: list[str] = []
    for name in sorted(folders - pages):
        errors.append(f"MISSING_PAGE: skills/{name}/ has no skills-wiki/{name}.md")
    for name in sorted(pages - folders):
        errors.append(f"MISSING_SKILL: skills-wiki/{name}.md has no skills/{name}/SKILL.md")
    return errors


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else repo_root()
    if (root / "skills-wiki").is_dir() is False and (root / "index.md").is_file():
        root = root.parent
    errors = sync_errors(root)
    if errors:
        sys.stdout.write("FAIL\n" + "\n".join(errors) + "\n")
        return 1
    folders = skill_folders(root)
    sys.stdout.write(f"PASS\n{len(folders)} skills mirrored\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

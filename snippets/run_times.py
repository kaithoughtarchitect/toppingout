"""How much time did a job spend running tests? For the dev report's "Test time" line.

Usage:
    python run_times.py <folder> [<folder> ...]

Reads every .txt file under the folders (the day folder, or a job's capture and work-order folders), takes each
run's closing summary line (pytest: "== 12 passed, 1 failed in 34.56s ==", unittest: "Ran 12 tests in 3.4s"),
skips identical copies (a saved base copied into a base-vs-head folder is one run, not two), and prints:

    runs <n>, <h:mm> in all
    whole-suite runs <n>, <h:mm>   (a run with at least 90% of the largest test count seen)
    other runs <n>, <h:mm>
    slowest tests (from --durations): <seconds> <test id>   (the five slowest, if any output has them)

Stdlib only. A file with no summary line is not a run and is left out.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

PYTEST = re.compile(r"=+ (?P<body>[^=\n]*?) in (?P<secs>[0-9.]+)s(?: \([0-9:]+\))? =+\s*$", re.M)
UNITTEST = re.compile(r"^Ran (?P<n>\d+) tests? in (?P<secs>[0-9.]+)s\s*$", re.M)
COUNT = re.compile(r"(\d+) (passed|failed|error|errors|skipped|xfailed|xpassed)")
DURATION = re.compile(r"^(?P<secs>[0-9.]+)s (?:call|setup|teardown)\s+(?P<id>\S+)\s*$", re.M)


def run_of(text: str):
    """(tests, seconds) of the run's last summary line, or None when the file holds no run."""
    m = list(PYTEST.finditer(text))
    if m:
        body = m[-1].group("body")
        n = sum(int(c.group(1)) for c in COUNT.finditer(body) if c.group(2) != "skipped")
        return n, float(m[-1].group("secs"))
    m = list(UNITTEST.finditer(text))
    if m:
        return int(m[-1].group("n")), float(m[-1].group("secs"))
    return None


def hm(secs: float) -> str:
    m = int(round(secs / 60))
    return f"{m // 60}:{m % 60:02d}"


def report(folders: list[Path]) -> str:
    seen, runs, slow = set(), [], {}
    for folder in folders:
        for f in sorted(folder.rglob("*.txt")):
            text = f.read_text(encoding="utf-8", errors="replace")
            digest = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()
            if digest in seen:
                continue
            r = run_of(text)
            if r is None:
                continue
            seen.add(digest)
            runs.append(r)
            for d in DURATION.finditer(text):
                slow[d.group("id")] = max(slow.get(d.group("id"), 0.0), float(d.group("secs")))
    if not runs:
        return "runs 0"
    top = max(n for n, _ in runs)
    whole = [s for n, s in runs if n >= 0.9 * top]
    other = [s for n, s in runs if n < 0.9 * top]
    lines = [f"runs {len(runs)}, {hm(sum(s for _, s in runs))} in all",
             f"whole-suite runs {len(whole)}, {hm(sum(whole))}   (at least 90% of {top} tests)",
             f"other runs {len(other)}, {hm(sum(other))}"]
    if slow:
        lines.append("slowest tests (from --durations):")
        lines += [f"  {s:8.2f}s {i}" for i, s in sorted(slow.items(), key=lambda x: -x[1])[:5]]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__.strip().splitlines()[2])
        return 2
    folders = [Path(a) for a in argv]
    missing = [str(f) for f in folders if not f.is_dir()]
    if missing:
        print("not a folder: " + ", ".join(missing))
        return 2
    print(report(folders))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

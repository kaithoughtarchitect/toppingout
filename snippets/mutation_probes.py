"""Does each guard actually bite? A mutation-probe harness to copy, one per job.

Copy it into the target repo (for example tests/acceptance/<ticket>_mutation_probes.py), set the CONFIG
block, and add one Probe per guard in the work order that adds the guard (WORK-ORDER.txt B.2b).

Each probe finds its guard by a unique anchor read from the file (never a hand-copied line number),
breaks it in place, runs the named tests, and restores the file byte for byte. The result is one of:

  BITES  the named tests went red: the guard is tested. When the run never said the expected thing
         (the test raised instead of asserting), it still bites, and the line shows the first error
         so the reviewer can see why (METHOD.md: a probe bites when its test fails for any reason)
  GREEN  the tests still pass without the guard: a missing test (report and STOP; never re-aim the probe)
  DIRTY  the restored file is not green again
  UNRUN  the run errored or every test skipped: the probe proved nothing

Safety machinery, kept from the harness it was generalised from:
  - an atomic rescue copy before any change, and a refusal to start if an old rescue is lying around;
  - the restore is verified by sha256, and stale bytecode is dropped on both legs;
  - apply() runs inside the restore's try, so a rotten anchor cannot strand the rescue;
  - an expect_in_output that pytest would print anyway (a path or test name) is refused;
  - an empty PROBES list exits non-zero, because an empty harness would otherwise pass.
Never restore with `git checkout --`; the rescue copy is the restore.

Run:  python <this file>            every probe
      python <this file> P01 P03    only those probes
      PROBE_ROOT=<tree> python <this file> --check-anchors
                                    no tests: check every anchor matches exactly once in <tree>
                                    (run it on the tree as it will be after a work order's edits,
                                    before sending the work order)
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---- CONFIG -----------------------------------------------------------------------------
ROOT = Path(os.environ.get("PROBE_ROOT") or Path(__file__).resolve().parents[2])  # the repo root (PROBE_ROOT overrides, for --check-anchors)
TEST_CMD = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=line"]
RESULTS = "pytest"        # how to read TEST_CMD's output: "pytest", or "unittest" with
                          # TEST_CMD = [sys.executable, "-m", "unittest", "-v"] and dotted test ids
PAID_KEYS = ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")
TAG = Path(__file__).stem                             # names the rescue files, so harnesses never collide
TIMEOUT = 600
# -----------------------------------------------------------------------------------------


def _line_in(path: str, pattern: str) -> str:
    text = (ROOT / path).read_text(encoding="utf-8")
    matches = re.findall(pattern, text)
    if len(matches) != 1:
        raise SystemExit(f"could not derive a unique mutation target from {path}: {pattern} matched {len(matches)} time(s)")
    return matches[0]


def anchor(path: str, literal: str) -> str:
    """The exact text of the guard, read from disk and required to be unique."""
    return _line_in(path, re.escape(literal))


@dataclass
class Probe:
    name: str                  # "P01 short description"; the first word selects it on the command line
    guards: str                # what the guard protects, in one line
    path: str                  # the file holding the guard, relative to ROOT
    old: str                   # the guard's text, from anchor()
    new: str                   # what replaces it (the mutation)
    expect_in_output: str      # what the failing test must say
    tests: list[str] = field(default_factory=list)   # test ids to run
    delete: bool = False       # mutation = delete the whole file
    env: dict[str, str] = field(default_factory=dict)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def drop_bytecode(path: Path) -> None:
    cache = path.parent / "__pycache__"
    if cache.is_dir():
        for stale in cache.glob(f"{path.stem}.*.pyc"):
            stale.unlink(missing_ok=True)


def run_tests(tests: list[str], extra: dict[str, str] | None = None) -> tuple[bool, str]:
    env = {k: v for k, v in os.environ.items() if k not in PAID_KEYS}
    if extra:
        env.update(extra)
    try:
        result = subprocess.run([*TEST_CMD, *tests], capture_output=True, text=True, encoding="utf-8",
                                errors="replace", cwd=ROOT, env=env, timeout=TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as exc:
        # a missing tool or a hang is "nothing ran", reported as UNRUN after the file is restored
        return False, f"TEST COMMAND DID NOT RUN: {type(exc).__name__}: {exc}"
    return result.returncode == 0, f"{result.stdout}\n{result.stderr}"


def apply(path: Path, old: str, new: str, *, delete: bool = False) -> None:
    if delete:
        path.unlink()
        return
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"INJECTION TARGET {'NOT FOUND' if old not in text else 'NOT UNIQUE'} in {path}:\n{old[:200]}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
    drop_bytecode(path)


def _test_names(rel: str) -> list[str]:
    return re.findall(r"^(?:async )?def (test_\w+)", (ROOT / rel).read_text(encoding="utf-8"), re.M)


def audit(probes: list[Probe]) -> None:
    """Refuse an expect_in_output that is part of the probe path, a test id or a test name:
    pytest prints those on every failure, so such a needle passes for the wrong reason."""
    for p in probes:
        haystacks = [p.path, *p.tests]
        for rel in {t.split("::", 1)[0] for t in p.tests}:
            haystacks.append(rel)
            if (ROOT / rel).is_file():
                haystacks.extend(_test_names(rel))
        for hay in haystacks:
            if p.expect_in_output in hay:
                raise SystemExit(f"SELF-SATISFYING expect_in_output {p.expect_in_output!r} is part of {hay!r} (probe {p.name})")


def counts(output: str) -> dict[str, int]:
    """What the run reported, read the way RESULTS says: tests run, failed, errored and skipped."""
    c = {"ran": 0, "failed": 0, "errors": 0, "skipped": 0}
    if RESULTS == "unittest":
        ran = re.findall(r"^Ran (\d+) tests?", output, re.M)
        if not ran:
            return c
        c["ran"] = int(ran[-1])
        for key, word in (("failed", "failures"), ("errors", "errors"), ("skipped", "skipped")):
            m = re.findall(rf"\b{word}=(\d+)", output)
            c[key] = int(m[-1]) if m else 0
        return c
    if RESULTS != "pytest":
        raise SystemExit(f"unknown RESULTS {RESULTS!r}: use 'pytest' or 'unittest'")
    for n, word in re.findall(r"\b(\d+) (passed|failed|errors?|skipped|xfailed|xpassed)\b", output):
        key = {"passed": None, "failed": "failed", "error": "errors", "errors": "errors", "skipped": "skipped"}.get(word)
        c["ran"] += int(n)
        if key:
            c[key] += int(n)
    return c


def _ran(output: str) -> bool:
    """True when the test command reported results at all (a missing tool or a bad path reports none)."""
    return counts(output)["ran"] > 0


def _errored(output: str) -> bool:
    c = counts(output)
    return c["errors"] > 0 and c["failed"] == 0


def first_error(output: str) -> str:
    """The first line that says why the run failed: pytest's E/FAILED/ERROR lines, or an exception line."""
    for pattern in (r"^E\s+\S.*$", r"^FAILED .*$", r"^ERROR .*$", r"^\S+:\d+: \w*(?:Error|Exception)\b.*$"):
        m = re.search(pattern, output, re.M)
        if m:
            return m.group(0).strip()[:300]
    return "(no error line found)"


def check_anchors(probes: list[Probe]) -> int:
    """Every probe's guard text must appear exactly once in its file under ROOT. Runs no tests."""
    bad = 0
    for p in probes:
        path = ROOT / p.path
        n = path.read_text(encoding="utf-8").count(p.old) if path.is_file() else -1
        if n != 1:
            bad += 1
            print(f"  ANCHOR   {p.name}: {'file missing' if n < 0 else f'matches {n} times'} in {p.path}")
    print(f"\n{len(probes) - bad}/{len(probes)} anchors unique under {ROOT}")
    return bad


def probe(p: Probe) -> str:
    path = ROOT / p.path
    rescue = ROOT / f"{path.name}.{TAG}-rescue"
    if rescue.exists():
        # Read the rescue before saying anything about it.
        if not path.exists():
            raise SystemExit(f"REFUSING TO START: {path} is MISSING while {rescue} exists. A delete-mode probe did not "
                             f"finish. The rescue IS the pristine copy: copy it back by hand, delete the rescue, run again.")
        if sha256(rescue) == sha256(path):
            raise SystemExit(f"REFUSING TO START: {rescue} is identical to {path}, so it is only stale. Delete it and run again.")
        raise SystemExit(f"REFUSING TO START: {rescue} exists and DIFFERS from {path}. An earlier probe did not finish. "
                         f"Compare them by hand and decide which is pristine; do not blindly copy either over the other.")
    # Write the rescue atomically, so its existence implies its completeness.
    part = rescue.with_name(rescue.name + ".part")
    part.unlink(missing_ok=True)
    try:
        with open(part, "xb") as handle:
            handle.write(path.read_bytes())
        os.replace(part, rescue)
    except OSError as err:
        part.unlink(missing_ok=True)
        raise SystemExit(f"could not write the rescue for {path}: {err}") from err
    digest = sha256(path)
    try:
        apply(path, p.old, p.new, delete=p.delete)
        took = (not path.exists()) if p.delete else (p.new in path.read_text(encoding="utf-8"))
        if not took:
            raise SystemExit(f"MUTATION DID NOT TAKE in {path}")
        red_ok, output = run_tests(p.tests, p.env)
        named = p.expect_in_output in output
        seen = counts(output)
        skipped_only = seen["ran"] > 0 and seen["skipped"] == seen["ran"]
        errored = _errored(output)
    finally:
        try:
            shutil.copy2(rescue, path)
            restored = sha256(path) == digest
        except OSError as err:
            raise SystemExit(f"RESTORE FAILED for {path} ({err}). The pristine copy is at {rescue}: restore it by hand first.") from err
        drop_bytecode(path)
        if not restored:
            raise SystemExit(f"RESTORE FAILED for {path}: sha256 changed. The pristine copy is at {rescue}: restore it by hand.")
        try:
            rescue.unlink()
        except OSError as err:
            print(f"source restored and verified; stale rescue left at {rescue} ({err})", flush=True)

    green_ok, green_output = run_tests(p.tests, p.env)
    green_errored = _errored(green_output)

    # The two legs answer different questions. The MUTATED leg: did the guard bite? The RESTORED leg:
    # is the tree green again? The restore is sha256-verified above, so an errored restored leg is a
    # caveat on a bite, never a discarded result. (This order was wrong three times before it settled.)
    if not _ran(output):
        return f"UNRUN    {p.name}: no test ran (is the test tool installed? are the test ids right?). Nothing proved.\n{output[-400:]}"
    if errored:
        return f"UNRUN    {p.name}: the mutated run ERRORED instead of failing on the guard (a service down? a collection error?). Nothing proved.\n{output[-400:]}"
    if skipped_only:
        return f"UNRUN    {p.name}: every test skipped; nothing proved"
    if not green_ok and not green_errored:
        return f"DIRTY    {p.name}: the restored file is not green again:\n{green_output[-400:]}"
    if red_ok:
        return f"GREEN    {p.name}: THE GUARD DID NOT BITE. A missing test: report it and STOP."
    note = "" if named else f" (never said {p.expect_in_output!r}; first error: {first_error(output)})"
    if green_errored:
        return f"BITES    {p.name}: bit{note}; the post-restore re-check ERRORED, so 'green again' is unproven (file sha256-verified)."
    return f"BITES    {p.name}{note}"


# ---- PROBES: one per guard, added in the work order that adds the guard -------------------
# Example (replace with the job's own):
#
# SRC = "src/orders/validate.py"
# SRC_TEST = "tests/test_validate.py"
# PROBES = [
#     Probe(
#         name="P01 accept a negative quantity",
#         guards="a negative quantity is refused with a typed error",
#         path=SRC,
#         old=anchor(SRC, "if quantity < 0:"),
#         new="if False:",
#         expect_in_output="DID NOT RAISE",
#         tests=[f"{SRC_TEST}::test_negative_quantity_is_refused"],
#     ),
# ]
PROBES: list[Probe] = []
# -----------------------------------------------------------------------------------------


def main() -> None:
    if not PROBES:
        raise SystemExit("the probe list is empty; an empty harness would otherwise exit 0")
    wanted = {a.upper() for a in sys.argv[1:] if a.upper().startswith("P")}
    known = {p.name.split()[0].upper() for p in PROBES}
    unknown = sorted(wanted - known)
    if unknown:
        raise SystemExit(f"unknown probe id(s): {', '.join(unknown)} (known: {', '.join(sorted(known))})")
    selected = [p for p in PROBES if not wanted or p.name.split()[0].upper() in wanted]
    if not selected:
        raise SystemExit("no probe selected; a run that tests nothing must not pass")
    if "--check-anchors" in sys.argv[1:]:
        raise SystemExit(1 if check_anchors(selected) else 0)
    audit(selected)
    print(f"mutation probes - {len(selected)} of {len(PROBES)}\n")
    results = []
    for p in selected:
        line = probe(p)
        print(" ", line, flush=True)
        results.append(line)
    bit = sum(1 for line in results if line.startswith("BITES"))
    print(f"\n{bit}/{len(results)} bite")
    if bit != len(results) or len(results) != len(selected):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

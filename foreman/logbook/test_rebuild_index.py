#!/usr/bin/env python3
"""Tests for rebuild_index.py. Standard library only:

    python foreman/logbook/test_rebuild_index.py

Every test works in a temporary folder. The last test runs against a copy of a
real Logbook when REAL_LOGBOOK names one (its foreman/logbook folder) and is
skipped otherwise.
"""

import contextlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rebuild_index as rb  # noqa: E402

REAL_LOGBOOK = Path(os.environ.get("REAL_LOGBOOK", "") or "/nonexistent-logbook")
FOLDER = {"METHOD": "methods", "INSIGHT": "insights", "BUILD": "builds"}
CONF_KEY = {"METHOD": "success_rate", "INSIGHT": "confidence"}


def run(root, *args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = rb.main(["--root", str(root), "--date", "2030-01-02", *args])
    return code, out.getvalue(), err.getvalue()


def new_root(tmp):
    """A records root holding the package's empty Logbook (index, links, templates)."""
    lb = Path(tmp) / "foreman" / "logbook"
    for name in ("logbook_index.md", "logbook_links.md"):
        lb.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(HERE / name, lb / name)
    for t, folder in FOLDER.items():
        (lb / "entries" / folder).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(HERE / "entries" / folder / f"{t}-TEMPLATE.md", lb / "entries" / folder / f"{t}-TEMPLATE.md")
    return Path(tmp), lb


def card(lb, cid, cluster="testing", impact="HIGH", conf=85, job="null", related=None, title=None, extra=""):
    ctype = cid.split("_", 1)[0]
    lines = ["---", f"id: {cid}", f"type: {ctype}", "created: 2030-01-01", f"job: {job}",
             "session: conversation-2030-01-01", f"cluster: {cluster}", "tags: [a, b]"]
    if impact is not None:
        lines.append(f"impact: {impact}")
    if conf is not None and ctype in CONF_KEY:
        lines.append(f"{CONF_KEY[ctype]}: {conf}")
    if related is not None:
        lines.append(f"related: [{', '.join(related)}]")
    lines += ["---", "", f"# {title or 'Title of ' + cid}", "", "## Overview", "", "Text.", extra]
    path = lb / "entries" / FOLDER[ctype] / f"{cid}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def undated(text):
    return [l for l in text.splitlines() if not l.startswith("**Last Updated**")]


def table_rows(text, heading):
    block = text.split(heading, 1)[1]
    block = re.split(r"\n#{2,3} ", block, maxsplit=1)[0]
    return [l for l in block.splitlines() if re.match(r"\| [A-Z]+_\d{8}_", l)]


class Rebuild(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root, self.lb = new_root(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def read(self, name):
        return (self.lb / name).read_text(encoding="utf-8")

    def test_empty_logbook_rebuilds_to_the_package_files(self):
        before = {n: (self.lb / n).read_bytes() for n in ("logbook_index.md", "logbook_links.md")}
        code, out, err = run(self.root)
        self.assertEqual(code, 0, err)
        self.assertIn("nothing written", out)
        for n, b in before.items():
            self.assertEqual((self.lb / n).read_bytes(), b, n)
        files, _ = rb.build(self.lb, "2030-01-02")
        for n, (old, new) in files.items():
            self.assertEqual(undated(old), undated(new), n)
            self.assertIn("**Last Updated**: 2030-01-02", new)
            self.assertEqual(new, old.replace("**Last Updated**: 2026-09-25", "**Last Updated**: 2030-01-02"), n)

    def test_each_type_gives_its_rows_and_counts(self):
        card(self.lb, "METHOD_20300101_STEP_ONE", conf=80, job="foreman/completed-jobs/2030-01/JOB_a.md")
        card(self.lb, "INSIGHT_20300101_B_LESSON", cluster="billing", impact="LOW", conf=75)
        card(self.lb, "INSIGHT_20300101_A_LESSON", cluster="[billing, testing]", title="A | piped title")
        card(self.lb, "BUILD_20300101_THE_THING", impact="MEDIUM")
        code, out, err = run(self.root)
        self.assertEqual(code, 0, err)
        text = self.read("logbook_index.md")
        self.assertIn("**Total Cards**: 4 (1 METHOD, 2 INSIGHT, 1 BUILD)", text)
        self.assertIn("**Last Updated**: 2030-01-02", text)
        self.assertIn("### METHOD Cards (1)", text)
        self.assertIn("### INSIGHT Cards (2)", text)
        self.assertIn("### BUILD Cards (1)", text)
        self.assertEqual(table_rows(text, "### METHOD Cards"),
                         ["| METHOD_20300101_STEP_ONE | Title of METHOD_20300101_STEP_ONE | HIGH | 80 | `foreman/completed-jobs/2030-01/JOB_a.md` |"])
        self.assertEqual(table_rows(text, "### INSIGHT Cards"), [
            "| INSIGHT_20300101_A_LESSON | A \\| piped title | HIGH | 85 | none |",
            "| INSIGHT_20300101_B_LESSON | Title of INSIGHT_20300101_B_LESSON | LOW | 75 | none |",
        ])
        self.assertEqual(table_rows(text, "### BUILD Cards"),
                         ["| BUILD_20300101_THE_THING | Title of BUILD_20300101_THE_THING | MEDIUM | n/a | none |"])
        clusters = text.split("## Clusters", 1)[1]
        self.assertNotIn(rb.CLUSTER_PLACEHOLDER, clusters)
        self.assertIn("| billing | INSIGHT_20300101_A_LESSON, INSIGHT_20300101_B_LESSON |", clusters)
        self.assertIn("| testing | BUILD_20300101_THE_THING, INSIGHT_20300101_A_LESSON, METHOD_20300101_STEP_ONE |", clusters)
        # A second run changes nothing.
        code, out, _ = run(self.root)
        self.assertIn("nothing written", out)
        self.assertEqual(run(self.root, "--check")[0], 0)

    def test_existing_summary_kept_and_card_fields_win(self):
        card(self.lb, "INSIGHT_20300101_A_LESSON", impact="HIGH", conf=90, job="foreman/completed-jobs/x.md")
        card(self.lb, "BUILD_20300101_THE_THING", impact=None)
        run(self.root)
        text = self.read("logbook_index.md")
        text = text.replace("| INSIGHT_20300101_A_LESSON | Title of INSIGHT_20300101_A_LESSON | HIGH | 90 | `foreman/completed-jobs/x.md` |",
                            "| INSIGHT_20300101_A_LESSON | a hand-written summary | LOW | 90% | foreman/completed-jobs/x.md |")
        text = text.replace("| BUILD_20300101_THE_THING | Title of BUILD_20300101_THE_THING | n/a | n/a | none |",
                            "| BUILD_20300101_THE_THING | build summary | MEDIUM | 95 | none |")
        (self.lb / "logbook_index.md").write_text(text, encoding="utf-8")
        self.assertEqual(run(self.root)[0], 0)
        text = self.read("logbook_index.md")
        # Summary kept; Impact from the card; Conf and Job say the same as the card, so kept as written.
        self.assertIn("| INSIGHT_20300101_A_LESSON | a hand-written summary | HIGH | 90% | foreman/completed-jobs/x.md |", text)
        # The card has no impact or conf: the cells are kept.
        self.assertIn("| BUILD_20300101_THE_THING | build summary | MEDIUM | 95 | none |", text)

    def test_related_edges_give_links_and_totals(self):
        card(self.lb, "INSIGHT_20300101_A_LESSON", related=["INSIGHT_20300101_B_LESSON", "refines:METHOD_20300101_STEP_ONE"])
        card(self.lb, "INSIGHT_20300101_B_LESSON")
        card(self.lb, "METHOD_20300101_STEP_ONE")
        links = self.read("logbook_links.md") + "| BUILD_20290101_OLD | derived-from | INSIGHT_20300101_B_LESSON |\n"
        (self.lb / "logbook_links.md").write_text(links, encoding="utf-8")
        code, out, err = run(self.root)
        self.assertEqual(code, 0, err)
        self.assertIn("kept 1 links naming a card not in entries/", out)
        text = self.read("logbook_links.md")
        rows = [l for l in text.splitlines() if re.match(r"\| [A-Z]+_\d", l)]
        self.assertEqual(rows, [
            "| BUILD_20290101_OLD | derived-from | INSIGHT_20300101_B_LESSON |",
            "| INSIGHT_20300101_A_LESSON | refines | METHOD_20300101_STEP_ONE |",
            "| INSIGHT_20300101_A_LESSON | relates | INSIGHT_20300101_B_LESSON |",
        ])
        self.assertIn("**Total Links**: 3", text)
        self.assertIn("**Last Updated**: 2030-01-02", text)
        self.assertIn("**Total Links**: 3", self.read("logbook_index.md"))
        # An untyped edge already present under another type is not added twice.
        text = text.replace("| INSIGHT_20300101_A_LESSON | relates | INSIGHT_20300101_B_LESSON |",
                            "| INSIGHT_20300101_A_LESSON | supersedes | INSIGHT_20300101_B_LESSON |")
        (self.lb / "logbook_links.md").write_text(text, encoding="utf-8")
        run(self.root)
        text = self.read("logbook_links.md")
        self.assertIn("**Total Links**: 3", text)
        self.assertNotIn("| relates |", text)

    def test_malformed_cards_fail_loudly(self):
        cases = {
            "no frontmatter": "# just a title\n",
            "never closed": "---\nid: X\n",
            "not key value": None,
            "id differs": None,
            "conflict marker": None,
        }
        for label in cases:
            with self.subTest(label):
                shutil.rmtree(self.tmp)
                self.root, self.lb = new_root(self.tmp)
                card(self.lb, "INSIGHT_20300101_GOOD_ONE")
                bad = card(self.lb, "INSIGHT_20300101_BAD_ONE")
                text = bad.read_text(encoding="utf-8")
                if label in ("no frontmatter", "never closed"):
                    text = cases[label]
                elif label == "not key value":
                    text = text.replace("tags: [a, b]", "tags [a, b]")
                elif label == "id differs":
                    text = text.replace("id: INSIGHT_20300101_BAD_ONE", "id: INSIGHT_20300101_OTHER")
                else:
                    text += "<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> lane\n"
                bad.write_text(text, encoding="utf-8")
                before = self.read("logbook_index.md")
                code, out, err = run(self.root)
                self.assertEqual(code, 1)
                self.assertIn("entries/insights/INSIGHT_20300101_BAD_ONE.md", err)
                self.assertIn("nothing written", err)
                self.assertEqual(self.read("logbook_index.md"), before)
                self.assertEqual(run(self.root, "--check")[0], 1)

    def test_duplicate_id_fails(self):
        card(self.lb, "INSIGHT_20300101_TWICE")
        (self.lb / "entries" / "insights" / "sub").mkdir()
        shutil.copyfile(self.lb / "entries/insights/INSIGHT_20300101_TWICE.md",
                        self.lb / "entries/insights/sub/INSIGHT_20300101_TWICE.md")
        code, _, err = run(self.root)
        self.assertEqual(code, 1)
        self.assertIn("two cards with id INSIGHT_20300101_TWICE", err)

    def test_check_exit_codes(self):
        self.assertEqual(run(self.root, "--check")[0], 0)
        card(self.lb, "INSIGHT_20300101_A_LESSON")
        before = self.read("logbook_index.md")
        code, out, _ = run(self.root, "--check")
        self.assertEqual(code, 1)
        self.assertIn("differs: logbook_index.md", out)
        self.assertIn("+| INSIGHT_20300101_A_LESSON", out)
        self.assertEqual(self.read("logbook_index.md"), before, "--check wrote")
        self.assertEqual(run(self.root)[0], 0)
        self.assertEqual(run(self.root, "--check")[0], 0)
        # Only the date differs: still up to date.
        text = self.read("logbook_index.md").replace("**Last Updated**: 2030-01-02", "**Last Updated**: 2029-05-05")
        (self.lb / "logbook_index.md").write_text(text, encoding="utf-8")
        self.assertEqual(run(self.root, "--check")[0], 0)
        self.assertEqual(run(Path(self.tmp) / "nowhere")[0], 2)

    def test_hand_written_cluster_text_survives(self):
        card(self.lb, "INSIGHT_20300101_A_LESSON", cluster="billing")
        text = self.read("logbook_index.md").replace(
            rb.CLUSTER_PLACEHOLDER,
            "Aliases: `bill` is now `billing`.\n\n"
            "| Cluster | Description | Cards |\n| --- | --- | --- |\n"
            "| billing | Invoices and refunds | OLD_LIST |\n"
            "| search-index | The search service (no cards yet) | |\n\n"
            "Written by hand below the table.")
        (self.lb / "logbook_index.md").write_text(text, encoding="utf-8")
        card(self.lb, "INSIGHT_20300101_B_LESSON", cluster="testing")
        self.assertEqual(run(self.root)[0], 0)
        clusters = self.read("logbook_index.md").split("## Clusters", 1)[1]
        self.assertEqual(clusters, "\n\nAliases: `bill` is now `billing`.\n\n"
                         "| Cluster | Description | Cards |\n| --- | --- | --- |\n"
                         "| billing | Invoices and refunds | INSIGHT_20300101_A_LESSON |\n"
                         "| search-index | The search service (no cards yet) |  |\n"
                         "| testing |  | INSIGHT_20300101_B_LESSON |\n\n"
                         "Written by hand below the table.\n")

    def test_row_for_a_missing_card_refuses_unless_archived(self):
        card(self.lb, "INSIGHT_20300101_A_LESSON")
        run(self.root)
        (self.lb / "entries/insights/INSIGHT_20300101_A_LESSON.md").unlink()
        code, _, err = run(self.root)
        self.assertEqual(code, 1)
        self.assertIn("would lose them): INSIGHT_20300101_A_LESSON", err)
        arch = self.lb / "archived" / "001" / "entries" / "insights"
        arch.mkdir(parents=True)
        card(self.lb, "INSIGHT_20300101_A_LESSON").replace(arch / "INSIGHT_20300101_A_LESSON.md")
        code, out, err = run(self.root)
        self.assertEqual(code, 0, err)
        self.assertIn("left out 1 rows for archived cards", out)
        self.assertIn("**Total Cards**: 0 (0 METHOD, 0 INSIGHT, 0 BUILD)", self.read("logbook_index.md"))

    def test_unknown_line_in_a_generated_table_refuses(self):
        text = self.read("logbook_index.md").replace("### BUILD Cards (0)", "### BUILD Cards (0)\n\nA note someone wrote.")
        (self.lb / "logbook_index.md").write_text(text, encoding="utf-8")
        code, _, err = run(self.root)
        self.assertEqual(code, 1)
        self.assertIn("would lose this line under ## Index Cards: 'A note someone wrote.'", err)


@unittest.skipUnless(shutil.which("git"), "git is not on PATH")
class TwoLanes(unittest.TestCase):
    """Two lanes add different cards; merging records gives conflicts the rebuild resolves."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def lane(self, name, cards):
        root, lb = new_root(self.tmp / name)
        card(lb, "INSIGHT_20300101_SHARED", related=[])
        for cid, kw in cards:
            card(lb, cid, **kw)
        self.assertEqual(run(root)[0], 0)
        return root, lb

    def merged(self, base, first, second, cards_from):
        """Merge second into first the way git does, then rebuild."""
        root, lb = new_root(self.tmp / f"merge-{first[1].parent.parent.name}")
        for src in cards_from:
            for p in (src / "entries").rglob("*_20*.md"):
                dst = lb / p.relative_to(src)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, dst)
        for name in ("logbook_index.md", "logbook_links.md"):
            res = subprocess.run(["git", "merge-file", "-p", str(first[1] / name), str(base / name), str(second[1] / name)],
                                 capture_output=True, text=True, encoding="utf-8")
            (lb / name).write_text(res.stdout, encoding="utf-8")
        return root, lb

    def test_order_does_not_matter(self):
        base_root, base = new_root(self.tmp / "base")
        card(base, "INSIGHT_20300101_SHARED")
        run(base_root)
        a = self.lane("a", [("METHOD_20300102_LANE_A", {"related": ["INSIGHT_20300101_SHARED"], "cluster": "alpha"})])
        b = self.lane("b", [("INSIGHT_20300103_LANE_B", {"related": ["derived-from:INSIGHT_20300101_SHARED"]}),
                            ("BUILD_20300103_LANE_B_BUILD", {})])
        # Lane B's foreman wrote its own summary into the index row.
        idx = (b[1] / "logbook_index.md").read_text(encoding="utf-8").replace(
            "| INSIGHT_20300103_LANE_B | Title of INSIGHT_20300103_LANE_B |", "| INSIGHT_20300103_LANE_B | lane b's own words |")
        (b[1] / "logbook_index.md").write_text(idx, encoding="utf-8")
        ab = self.merged(base, a, b, [a[1], b[1]])
        ba = self.merged(base, b, a, [b[1], a[1]])
        self.assertIn("<<<<<<<", (ab[1] / "logbook_index.md").read_text(encoding="utf-8"), "the test needs a real conflict")
        for root, _ in (ab, ba):
            code, out, err = run(root)
            self.assertEqual(code, 0, err)
        for name in ("logbook_index.md", "logbook_links.md"):
            one = (ab[1] / name).read_text(encoding="utf-8")
            two = (ba[1] / name).read_text(encoding="utf-8")
            self.assertEqual(one, two, name)
            self.assertNotIn("<<<<<<<", one)
        text = (ab[1] / "logbook_index.md").read_text(encoding="utf-8")
        self.assertIn("**Total Cards**: 4 (1 METHOD, 2 INSIGHT, 1 BUILD)", text)
        self.assertIn("**Total Links**: 2", text)
        self.assertIn("| INSIGHT_20300103_LANE_B | lane b's own words |", text)
        self.assertEqual(run(ab[0], "--check")[0], 0)

    def test_sides_that_disagree_on_a_summary_refuse(self):
        base_root, base = new_root(self.tmp / "base")
        card(base, "INSIGHT_20300101_SHARED")
        run(base_root)
        a = self.lane("a", [])
        b = self.lane("b", [])
        for lane, words in ((a, "said by a"), (b, "said by b")):
            p = lane[1] / "logbook_index.md"
            p.write_text(p.read_text(encoding="utf-8").replace("Title of INSIGHT_20300101_SHARED", words), encoding="utf-8")
        root, lb = self.merged(base, a, b, [a[1]])
        code, _, err = run(root)
        self.assertEqual(code, 1)
        self.assertIn("INSIGHT_20300101_SHARED different summaries", err)


@unittest.skipUnless((REAL_LOGBOOK / "logbook_index.md").is_file(), "no real Logbook on this machine")
class RealLogbookCopy(unittest.TestCase):
    """A copy of a real Logbook rebuilds to the same card IDs and totals as its committed index."""

    def test_same_ids_and_totals(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            lb = tmp / "foreman" / "logbook"
            shutil.copytree(REAL_LOGBOOK, lb, ignore=shutil.ignore_patterns("__pycache__", "*.py"))
            committed = (lb / "logbook_index.md").read_text(encoding="utf-8")
            committed_links = (lb / "logbook_links.md").read_text(encoding="utf-8")
            code, out, err = run(tmp)
            self.assertEqual(code, 0, err)
            rebuilt = (lb / "logbook_index.md").read_text(encoding="utf-8")
            ids = lambda t: {m.group(1) for m in re.finditer(r"^\| ((?:METHOD|INSIGHT|BUILD)_\d{8}_[A-Z0-9_]+) \|", t, re.M)}
            self.assertEqual(ids(rebuilt), ids(committed))
            for key in ("Total Cards", "Total Links"):
                line = lambda t: re.search(rf"^\*\*{key}\*\*:.*$", t, re.M).group(0)
                self.assertEqual(line(rebuilt), line(committed), key)
            links = (lb / "logbook_links.md").read_text(encoding="utf-8")
            rows = lambda t: {l for l in t.splitlines() if re.match(r"\| [A-Z]+_\d", l)}
            self.assertEqual(rows(links), rows(committed_links))
            self.assertEqual(run(tmp, "--check")[0], 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)

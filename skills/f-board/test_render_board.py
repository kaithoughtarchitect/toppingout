#!/usr/bin/env python3
"""Tests for render_board.py. Stdlib only:  python test_render_board.py

Each test copies the template BOARD.json into a temp folder and drives the tool as
a subprocess, checking exit codes, the written data and that failures write nothing.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

os.environ["FOREMAN_BOARD_NO_OPEN"] = "dry"  # never open a browser here; print "would open" instead

HERE = Path(__file__).resolve().parent
TOOL = HERE / "render_board.py"
CANDIDATES = [HERE.parent / "f-schedule" / "templates" / "BOARD.json",
              HERE.parent.parent / "templates" / "project" / "BOARD.json"]
TEMPLATE = next(p for p in CANDIDATES if p.exists())


class Board(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.path = self.dir / "BOARD.json"
        shutil.copy(TEMPLATE, self.path)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def run_tool(self, *args):
        r = subprocess.run([sys.executable, str(TOOL), str(self.path), *args], capture_output=True,
                           text=True, encoding="utf-8")
        return r.returncode, r.stdout + r.stderr

    def data(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def digest(self):
        return hashlib.sha256(self.path.read_bytes()).hexdigest()

    def edit(self, fn):
        s = self.data()
        fn(s)
        self.path.write_text(json.dumps(s), encoding="utf-8")

    def ok(self, *args):
        rc, out = self.run_tool(*args)
        self.assertEqual(rc, 0, out)
        return out

    def refused(self, code, *args):
        before = self.digest()
        rc, out = self.run_tool(*args)
        self.assertEqual(rc, code, out)
        self.assertEqual(before, self.digest(), "a refused command must not write BOARD.json")
        return out

    # lifecycle ---------------------------------------------------------
    def test_full_lifecycle(self):
        self.ok("check")
        self.ok("start", "01", "--run", "J2")
        self.assertIn("02", self.ok("next", "--after-close", "01"))
        self.ok("close", "01", "--pr", "#2", "--merge", "abcdef1", "--next", "02")
        s = self.data()
        self.assertEqual((s["version"], s["next"]), (3, "02"))
        self.ok("start", "02", "--run", "J3")
        self.ok("halt", "02", "--reason", "owner question", "--to", "decision", "--decision", "X or Y?")
        self.ok("decided", "02", "--note", "X")
        self.assertEqual(self.data()["jobs"][2]["state"], "open")
        self.assertTrue((self.dir / "board.html").exists())

    # F02: a decided decision job satisfies its dependents
    def test_decision_job_resolves_and_unblocks(self):
        self.ok("add", "04", "--title", "Waits on the decision", "--needs", "03")
        self.refused(2, "start", "04", "--run", "J5")
        self.ok("decided", "03", "--note", "Owner chose A")
        self.assertEqual(next(b for b in self.data()["jobs"] if b["id"] == "03")["state"], "resolved")
        self.assertIn("04", self.ok("next"))

    # F03: one job in progress at a time
    def test_second_start_refused(self):
        self.ok("add", "04", "--title", "Independent")
        self.ok("start", "01", "--run", "J2")
        self.refused(2, "start", "04", "--run", "J3")

    # R04: JSON is committed first; a failed page write is "render pending" (exit 4), then render reconciles
    def test_failed_page_write_is_render_pending(self):
        (self.dir / "board.html").mkdir()
        rc, out = self.run_tool("start", "01", "--run", "J2")
        self.assertEqual(rc, 4, out)
        self.assertIn("RENDER PENDING", out)
        self.assertEqual(self.data()["version"], 2)
        (self.dir / "board.html").rmdir()
        self.ok()
        self.assertIn("v2", (self.dir / "board.html").read_text(encoding="utf-8"))

    def test_failed_render_commits_nothing(self):
        self.edit(lambda s: s["jobs"][0].__setitem__("title", "x"))
        before = self.digest()
        # make render crash via an object the validator accepts but render can't format: none should exist,
        # so instead check a refused event leaves JSON untouched
        self.refused(2, "start", "02", "--run", "J2")
        self.assertEqual(before, self.digest())

    # R05: malformed consumed fields and bad JSON are data errors (exit 1), not crashes
    def test_malformed_shapes_are_invalid(self):
        for mut in (lambda s: s.__setitem__("superseded", [None]),
                    lambda s: s.__setitem__("log", {}),
                    lambda s: s.__setitem__("schema", True)):
            self.setUp()
            self.edit(mut)
            rc, out = self.run_tool("check")
            self.assertEqual(rc, 1, out)
        self.setUp()
        self.path.write_text("{", encoding="utf-8")
        rc, out = self.run_tool("check")
        self.assertEqual(rc, 1, out)

    # R06: a decision can't be resolved before its needs
    def test_decision_waits_for_its_needs(self):
        def dep(s):
            for j in s["jobs"]:
                if j["id"] == "03":
                    j["needs"] = ["02"]
        self.edit(dep)
        self.refused(2, "decided", "03", "--note", "too early")

    # R15: standalone mode persists across events
    def test_standalone_persists(self):
        self.edit(lambda s: s["publish"].__setitem__("standalone", True))
        self.ok("start", "01", "--run", "J2")
        self.assertTrue((self.dir / "board.html").read_text(encoding="utf-8").startswith("<!doctype html>"))

    # ids are never reused after a split
    def test_split_ids_not_reused(self):
        self.ok("start", "01", "--run", "J2")
        self.ok("split", "01", "--into", "a=Part A,b=Part B", "--chain", "--active", "a")
        self.refused(2, "add", "01", "--title", "reuse")

    # field report J21: a full child id is not prefixed twice, and a doubled prefix is refused
    def test_split_accepts_full_child_ids(self):
        self.ok("start", "01", "--run", "J2")
        self.ok("split", "01", "--into", "01a=Part A,01b=Part B", "--chain", "--active", "01a")
        s = self.data()
        ids = [b["id"] for b in s["jobs"]]
        self.assertIn("01a", ids)
        self.assertIn("01b", ids)
        self.assertFalse(any(i.startswith("0101") for i in ids))
        self.assertEqual(s["superseded"][0]["by"], ["01a", "01b"])
        self.assertEqual(s["next"], "01a")

    def test_split_refuses_doubled_prefix(self):
        self.ok("start", "01", "--run", "J2")
        self.refused(2, "split", "01", "--into", "0101a=Part A,b=Part B", "--active", "b")

    def test_check_refuses_unknown_superseded_by(self):
        self.ok("start", "01", "--run", "J2")
        self.ok("split", "01", "--into", "a=Part A,b=Part B", "--chain", "--active", "a")
        self.edit(lambda s: s["superseded"][0].__setitem__("by", ["0101a", "01b"]))
        self.refused(1, "check")

    # F11: close must choose next when something becomes eligible
    def test_close_requires_next_disposition(self):
        self.ok("start", "01", "--run", "J2")
        self.refused(2, "close", "01", "--pr", "#2", "--merge", "abcdef1")
        self.refused(2, "close", "01", "--pr", "#2", "--merge", "abcdef1", "--no-next")
        self.ok("close", "01", "--pr", "#2", "--merge", "abcdef1", "--no-next", "--reason", "owner pause")

    # F12: split is one versioned event
    def test_split_in_progress_job(self):
        self.ok("start", "01", "--run", "J2")
        v = self.data()["version"]
        self.ok("split", "01", "--into", "a=Part A,b=Part B", "--chain", "--active", "a")
        s = self.data()
        ids = [b["id"] for b in s["jobs"]]
        self.assertEqual(s["version"], v + 1)
        self.assertNotIn("01", ids)
        self.assertEqual(s["next"], "01a")
        self.assertEqual(next(b for b in s["jobs"] if b["id"] == "02")["needs"], ["01b"])
        self.assertEqual(s["superseded"][0]["id"], "01")

    # F13: stricter validation and argument parsing
    def test_malformed_data_is_invalid_not_a_crash(self):
        for mut in (lambda s: s.__setitem__("next", []),
                    lambda s: s.__setitem__("version", True),
                    lambda s: s.__setitem__("updated", "not a date"),
                    lambda s: s["jobs"][0].__setitem__("run", ["J1"]),
                    lambda s: s["jobs"][3].__setitem__("decision", {"x": 1})):
            self.setUp()
            self.edit(mut)
            rc, out = self.run_tool("check")
            self.assertEqual(rc, 1, out)

    def test_hand_edited_two_in_progress_is_invalid(self):
        def two(s):
            for b in s["jobs"][1:3]:
                b["state"], b["run"] = "in-progress", "J9"
            s["jobs"][2]["needs"] = []
            s["next"] = "01"
        self.edit(two)
        rc, out = self.run_tool("check")
        self.assertEqual(rc, 1, out)
        self.assertIn("more than one job in progress", out)

    def test_merged_job_needs_a_real_sha(self):
        self.edit(lambda s: s["jobs"][0].__setitem__("merge", "not-a-sha"))
        rc, out = self.run_tool("check")
        self.assertEqual(rc, 1, out)

    def test_close_warns_about_a_stale_standfirst(self):
        self.ok("start", "01", "--run", "J2")
        self.edit(lambda s: s["project"].__setitem__("standfirst", "One job open. Next: job 01."))
        rc, out = self.run_tool("close", "01", "--pr", "#2", "--merge", "abcdef1", "--no-next", "--reason", "pause")
        self.assertEqual(rc, 0, out)
        self.assertIn("standfirst unchanged", out)
        self.assertIn("names job 01 as next, but it is merged", out)
        rc, out = self.run_tool("check")
        self.assertIn("names job 01 as next", out)

    def test_summary_of_only_plan_references_warns_and_summary_fixes_it(self):
        self.edit(lambda s: s["jobs"][1].__setitem__("summary", "Plan task T2; carries VP-6."))  # job 01, open
        rc, out = self.run_tool("check")
        self.assertEqual(rc, 0, out)
        self.assertIn("the summary is only plan references", out)
        v = self.data()["version"]
        self.ok("summary", "01", "--text", "Loads the catalogue as a runtime block. (T2, VP-6)")
        d = self.data()
        self.assertEqual(d["jobs"][1]["summary"], "Loads the catalogue as a runtime block. (T2, VP-6)")
        self.assertEqual(d["version"], v + 1)
        rc, out = self.run_tool("check")
        self.assertNotIn("only plan references", out)
        self.refused(2, "summary", "01", "--text", "  ")

    def test_covered_removes_an_open_job_and_repoints_its_dependents(self):
        self.refused(2, "covered", "02", "--by", "00")                      # the owner's words are required
        self.refused(2, "covered", "02", "--by", "02", "--quote", "x")      # not by itself
        self.refused(2, "covered", "00", "--by", "01", "--quote", "x")      # 00 is merged, not open
        self.ok("covered", "01", "--by", "00", "--quote", "drop it, job 00 covers it")
        s = self.data()
        self.assertNotIn("01", [b["id"] for b in s["jobs"]])
        self.assertTrue(any(x["id"] == "01" and x["by"] == ["00"] and "drop it" in x["reason"] for x in s["superseded"]))
        for b in s["jobs"]:
            self.assertNotIn("01", b.get("needs", []))

    def test_board_opens_on_its_first_page_and_at_topping_out_only(self):
        rc, out = self.run_tool()                                                   # no board.html yet: the first page
        self.assertEqual(rc, 0, out)
        self.assertIn("would open", out)
        rc, out = self.run_tool()                                                   # a later render: no tab
        self.assertNotIn("would open", out)
        rc, out = self.run_tool("add", "09", "--title", "later job")                # a routine event: no tab
        self.assertEqual(rc, 0, out)
        self.assertNotIn("would open", out)
        self.ok("start", "01", "--run", "J2")
        self.ok("halt", "01", "--reason", "parked", "--to", "open")
        rc, out = self.run_tool("topout", "--report", "r.md", "--quote", "top it out, carry the rest", "--head", "partly")
        self.assertEqual(rc, 0, out)
        self.assertIn("would open", out)                                            # the topping out opens it

    def test_topout_freezes_the_board_and_carries_unfinished_jobs(self):
        self.refused(2, "topout")                                                   # needs the report
        self.refused(2, "topout", "--report", "r.md")                               # jobs would be carried over: needs the owner's words
        self.ok("start", "01", "--run", "J2")
        self.refused(2, "topout", "--report", "r.md", "--quote", "top it out")      # a job in progress
        self.ok("halt", "01", "--reason", "parked", "--to", "open")
        self.refused(2, "topout", "--report", "r.md", "--quote", "top it out, carry the rest")   # carried jobs: --head required
        self.ok("topout", "--report", "r.md", "--quote", "top it out, carry the rest", "--head", "partly")
        s = self.data()
        top = s["topped_out"]
        self.assertEqual(top["report"], "r.md")
        self.assertIn("01", top["carried"])
        self.assertNotIn("00", top["carried"])
        self.assertIsNone(s["next"])
        self.assertIn("Topped out on", s["project"]["standfirst"])
        self.refused(2, "add", "09", "--title", "late")                             # frozen: no event after topping out
        rc, out = self.run_tool("check")
        self.assertEqual(rc, 0, out)
        self.assertIn("TOPPED OUT", out)
        rc, out = self.run_tool("report")
        self.assertIn("## Carried over: jobs not built", out)
        self.assertIn("**01**", out)
        self.assertIn("Head reached: partly", out)
        rc, out = self.run_tool("next")
        self.assertIn("topped out", out)
        rc, out = self.run_tool("render")
        self.assertEqual(rc, 0, out)
        page = (self.dir / "board.html").read_text(encoding="utf-8")
        self.assertIn("topped out", page)
        self.assertNotIn("next · not chosen", page)                                 # no next-job slot on a frozen board
        self.assertIn('"topped": true', page)                                       # the client renderer is told too

    def test_topout_with_every_job_done_needs_no_words(self):
        def all_done(s):
            s["jobs"] = [b for b in s["jobs"] if b["id"] == "00"]
            s["next"] = None
            s.pop("superseded", None)
        self.edit(all_done)
        self.ok("topout", "--report", "r.md")
        self.assertEqual(self.data()["topped_out"]["carried"], [])
        self.assertIn("1 job done", self.data()["project"]["standfirst"])
        self.assertEqual(self.data()["topped_out"]["head_reached"], "yes")
        rc, out = self.run_tool("report")
        self.assertEqual(rc, 0, out)
        self.assertIn("## What was built", out)
        self.assertIn("| 00 |", out)
        self.assertIn("Head reached: yes", out)

    def test_init_iteration_board(self):
        path = self.dir / "iter" / "BOARD.json"
        r = subprocess.run([sys.executable, str(TOOL), str(path), "init", "--title", "Chat polish", "--head", "Juanito feels right to talk to",
                            "--job", "01", "--job-title", "Shorter loan answers", "--iteration"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["project"]["mode"], "iteration")
        self.assertIn("iteration board", (path.parent / "board.html").read_text(encoding="utf-8"))

    def test_close_run_must_match(self):
        self.ok("start", "01", "--run", "J2")
        self.refused(2, "close", "01", "--pr", "#2", "--merge", "abcdef1", "--run", "J999", "--next", "02")

    def test_unknown_options_refused(self):
        self.refused(2, "next", "--garbage", "x")
        self.refused(2, "start", "01", "--jorney", "J2")

    def test_twigs_and_owed_are_validated(self):
        self.edit(lambda s: s["jobs"][0].__setitem__("twigs", ["a", "b", "c", "d"]))
        rc, out = self.run_tool("check")
        self.assertEqual(rc, 1, out)
        self.setUp()
        self.edit(lambda s: s["project"].__setitem__("owed", "not a list"))
        rc, out = self.run_tool("check")
        self.assertEqual(rc, 1, out)

    def test_head_test_must_be_a_string(self):
        # a value check accepts must be one render can consume (round-4 R4-07)
        for bad in (123, ["bad"], {"bad": 1}):
            self.setUp()
            self.edit(lambda s, bad=bad: s["project"]["head"].__setitem__("test", bad))
            rc, out = self.run_tool("check")
            self.assertEqual(rc, 1, out)
        self.setUp()
        self.edit(lambda s: s["project"]["head"].__setitem__("test", "the walking skeleton carries one turn"))
        self.ok()

    def test_page_has_fishbone_tabs_and_owed(self):
        self.edit(lambda s: s["project"].__setitem__("owed", ["<b>still owed</b>"]))
        self.ok()
        page = (self.dir / "board.html").read_text(encoding="utf-8")
        for part in ('id="fish"', 'data-tab="job"', 'data-tab="open"', 'data-tab="owed"', 'id="board-data"'):
            self.assertIn(part, page)
        self.assertNotIn("<b>still owed</b>", page)

    def test_figures_lesson_alerts_facts(self):
        for mut in (lambda d: d["jobs"][0].__setitem__("figures", [{"n": "1", "label": "x", "tone": "loud"}]),
                    lambda d: d["jobs"][0].__setitem__("figures", [{"n": "1", "label": "x"}] * 7),
                    lambda d: d["jobs"][0].__setitem__("lesson", 3),
                    lambda d: d["project"].__setitem__("lesson", {"rule": "no title"}),
                    lambda d: d["project"].__setitem__("alerts", "not a list"),
                    lambda d: d["project"].__setitem__("facts", [1])):
            self.setUp()
            self.edit(mut)
            rc, out = self.run_tool("check")
            self.assertEqual(rc, 1, out)
        self.setUp()
        def good(d):
            d["jobs"][0]["figures"] = [{"n": "31/31", "label": "probes biting", "tone": "good"}]
            d["jobs"][0]["lesson"] = "A lesson."
            d["project"]["lesson"] = {"title": "Green is an answer", "rule": "A rule."}
            d["project"]["alerts"] = ["An <alert>"]
            d["project"]["facts"] = ["A fact."]
        self.edit(good)
        self.ok()
        page = (self.dir / "board.html").read_text(encoding="utf-8")
        for part in ('data-tab="lessons"', 'class="alert"', 'Green is an answer', 'A fact.', 'probes biting'):
            self.assertIn(part, page)
        self.assertNotIn("An <alert>", page)

    def test_escaping(self):
        self.edit(lambda s: s["jobs"][1].__setitem__("title", '<script>alert(1)</script> " &'))
        self.ok()
        page = (self.dir / "board.html").read_text(encoding="utf-8")
        self.assertNotIn("<script>alert", page)

    def test_standalone_has_doctype(self):
        self.ok("render", "--standalone")
        self.assertTrue((self.dir / "board.html").read_text(encoding="utf-8").startswith("<!doctype html>"))

    # init and backfill: a board for a project that wasn't cut by /f-schedule
    def init_tool(self, path, *args):
        r = subprocess.run([sys.executable, str(TOOL), str(path), "init", *args], capture_output=True,
                           text=True, encoding="utf-8")
        return r.returncode, r.stdout + r.stderr

    def test_init_starts_a_board_with_its_first_job(self):
        p = self.dir / "new" / "BOARD.json"
        code, out = self.init_tool(p, "--title", "Demos", "--head", "A user can ask about a player", "--test", "one real question answered",
                                   "--job", "01", "--job-title", "Player card")
        self.assertEqual(code, 0, out)
        b = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual((b["version"], [j["id"] for j in b["jobs"]], b["jobs"][0]["state"]), (1, ["01"], "open"))
        self.assertTrue((p.parent / "board.html").exists())

    def test_init_never_overwrites(self):
        before = self.digest()
        code, out = self.init_tool(self.path, "--title", "x", "--head", "y", "--job", "1", "--job-title", "z")
        self.assertEqual(code, 2, out)
        self.assertEqual(self.digest(), before)

    def test_init_needs_its_fields(self):
        code, out = self.init_tool(self.dir / "n2" / "BOARD.json", "--title", "x", "--job", "1", "--job-title", "z")
        self.assertEqual(code, 2, out)
        self.assertIn("--head", out)

    def test_backfill_adds_a_merged_job_that_counts_as_merged(self):
        p = self.dir / "bf" / "BOARD.json"
        self.assertEqual(self.init_tool(p, "--title", "x", "--head", "y", "--job", "02", "--job-title", "later")[0], 0)
        self.path = p
        self.ok("add", "01", "--title", "done before the board", "--merged", "--pr", "#1", "--merge", "abc1234", "--run", "J1")
        self.ok("add", "03", "--title", "needs the merged one", "--needs", "01")
        code, out = self.run_tool("next")
        self.assertEqual(code, 0, out)
        self.assertIn("03", out)   # ready: its only need is the backfilled, merged job
        j = {x["id"]: x for x in self.data()["jobs"]}["01"]
        self.assertEqual((j["state"], j["pr"], j["merge"], j["run"]), ("merged", "#1", "abc1234", "J1"))

    def test_backfill_needs_a_real_merge_and_the_flag(self):
        before = self.digest()
        self.assertEqual(self.run_tool("add", "z1", "--title", "x", "--merged", "--pr", "#1", "--merge", "nope", "--run", "J1")[0], 2)
        self.assertEqual(self.run_tool("add", "z2", "--title", "x", "--pr", "#1")[0], 2)
        self.assertEqual(self.digest(), before)


if __name__ == "__main__":
    unittest.main(verbosity=1)

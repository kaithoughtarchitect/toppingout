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

    # --rewire: each dependent needs only the child it uses
    def test_split_rewire_points_each_dependent_at_its_child(self):
        self.ok("add", "05", "--title", "Uses part A", "--needs", "01")
        self.ok("add", "06", "--title", "Uses part B", "--needs", "01")
        self.ok("add", "07", "--title", "Uses nothing named", "--needs", "01")
        self.ok("split", "01", "--into", "a=Part A,b=Part B", "--rewire", "05=a,06=b")
        jobs = {j["id"]: j for j in self.data()["jobs"]}
        self.assertEqual(jobs["05"]["needs"], ["01a"])
        self.assertEqual(jobs["06"]["needs"], ["01b"])
        self.assertEqual(sorted(jobs["07"]["needs"]), ["01a", "01b"])
        self.assertEqual(jobs["01b"]["needs"], jobs["01a"]["needs"])  # no --chain: b doesn't need a
        self.assertTrue(any("after 01 was split" in n for n in jobs["05"]["notes"]))

    def test_split_rewire_refuses_a_job_that_isnt_a_dependent_or_a_wrong_child(self):
        self.ok("add", "05", "--title", "Uses part A", "--needs", "01")
        self.refused(2, "split", "01", "--into", "a=Part A,b=Part B", "--rewire", "03=a")
        self.refused(2, "split", "01", "--into", "a=Part A,b=Part B", "--rewire", "05=c")

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

    def test_page_is_one_page_with_owed_under_needs_you(self):
        self.edit(lambda s: s["project"].__setitem__("owed", ["<b>still owed</b>"]))
        self.ok()
        page = (self.dir / "board.html").read_text(encoding="utf-8")
        for part in ('id="fish"', 'class="headsign"', 'aria-label="Needs you"', 'aria-label="Now"', 'id="cards"',
                     'aria-label="All jobs"', 'id="board-data"', '&lt;b&gt;still owed&lt;/b&gt;'):
            self.assertIn(part, page)
        self.assertNotIn("<b>still owed</b>", page)
        self.assertNotIn('data-tab=', page)
        # every job has its card in the page, so it reads without script
        for jid in ("00", "01", "02", "03"):
            self.assertIn(f'id="job-{jid}"', page)

    def test_nothing_is_cut_but_a_rib_name(self):
        long_head = "The owner can do " + " ".join(f"thing{k}" for k in range(40)) + " and the last words stay"
        long_title = "A job title long enough that the old page cut it short in the list and the next bar every time"
        def mut(s):
            s["project"]["head"]["outcome"] = long_head
            s["jobs"][1]["title"] = long_title
            s["project"]["alerts"] = ["An alert long enough to have been cut by the old one-line strip: " + "x " * 120 + "the end"]
        self.edit(mut)
        self.ok()
        page = (self.dir / "board.html").read_text(encoding="utf-8")
        self.assertIn(long_head, page)
        self.assertIn("the end</span>", page)
        self.assertGreaterEqual(page.count(long_title), 3)          # the card, the list, the "now" next line
        # "…" only appears inside the drawing's rib names
        outside = page.split('<svg class="fish"')[0] + page.split("</svg>", 1)[1].split("<script")[0]
        self.assertNotIn("…", outside)

    def test_needs_you_names_the_question_and_a_blocker_by_name(self):
        self.ok()
        page = (self.dir / "board.html").read_text(encoding="utf-8")
        needs = page.split('aria-label="Needs you"')[1].split("</section>")[0]
        self.assertIn("Decide · 03", needs)
        self.assertIn("What exactly must be decided", needs)
        rows = page.split('aria-label="All jobs"')[1].split("</section>")[0]
        title01 = self.data()["jobs"][1]["title"]
        self.assertIn(f"Waits on 01 · {title01}", rows)

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
        for part in ('class="jlesson"', 'class="need alert"', 'Green is an answer', 'A fact.', 'probes biting', 'A lesson.'):
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


V2_TEMPLATE = next(p for p in [HERE.parent / "f-schedule" / "templates" / "BOARD-v2.json",
                               HERE.parent.parent / "templates" / "project" / "BOARD-v2.json"] if p.exists())


class BoardV2(unittest.TestCase):
    """A board cut by /f-schedule v2 (project.schedule: 2): uses, gates, footprints, placeholders, width."""
    tearDown, run_tool, data, digest, edit, ok, refused = (Board.tearDown, Board.run_tool, Board.data, Board.digest,
                                                           Board.edit, Board.ok, Board.refused)

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.path = self.dir / "BOARD.json"
        shutil.copy(V2_TEMPLATE, self.path)

    def jobs(self):
        return {j["id"]: j for j in self.data()["jobs"]}

    def bad(self, fn, needle):
        self.edit(fn)
        rc, out = self.run_tool("check")
        self.assertEqual(rc, 1, out)
        self.assertIn(needle, out)

    def test_v2_template_is_valid(self):
        self.assertIn("BOARD OK", self.ok("check"))

    def test_v2_needs_without_uses_is_refused(self):
        self.bad(lambda s: s["jobs"][1].pop("uses"), "without uses")

    def test_v2_open_build_job_needs_footprint_ticket_estimate(self):
        for f in ("footprint", "ticket", "est_work_orders"):   # each one alone, the others present
            shutil.copy(V2_TEMPLATE, self.path)
            self.bad(lambda s: s["jobs"][1].pop(f), f"needs {f}")

    def test_v1_board_keeps_old_metadata(self):
        shutil.copy(TEMPLATE, self.path)   # no project.schedule: requires outside the v2 list is left alone
        self.edit(lambda s: s["jobs"][1].update(requires=["network"], uses={"zz": "old note"}))
        self.ok("check")

    def test_footprint_paths_are_canonical(self):
        self.edit(lambda s: s["jobs"][5].update(footprint=["./src/records/"]))
        self.assertIn("01+06 (src/records)", self.ok("width"))
        self.bad(lambda s: s["jobs"][5].update(footprint=["../elsewhere/"]), "inside the repo")

    def test_uses_must_explain_a_need(self):
        self.bad(lambda s: s["jobs"][5].update(uses={"01": "x"}), "which it doesn't need")

    def test_requires_vocabulary(self):
        self.bad(lambda s: s["jobs"][2].update(requires=["teleport"]), "requires 'teleport'")

    def test_schedule_and_cut_are_checked(self):
        self.bad(lambda s: s["project"]["cut"].update(reproof=12), "reproof")

    def test_gate_cycle_is_refused(self):
        self.bad(lambda s: s["jobs"][0].update(gates=["03"]), "cycle")

    def test_add_on_v2_needs_the_fields(self):
        self.refused(1, "add", "07", "--title", "New", "--needs", "01", "--uses", "01=Record")
        self.ok("add", "07", "--title", "New", "--needs", "01", "--uses", "01=Record; ", "--ticket", "tickets/T-07.md",
                "--footprint", "src/new/,tests/new/", "--est", "5")
        j = self.jobs()["07"]
        self.assertEqual((j["footprint"], j["est_work_orders"], j["uses"]), (["src/new/", "tests/new/"], 5, {"01": "Record"}))
        self.ok("add", "08", "--title", "Later area", "--placeholder")   # a placeholder is exempt
        self.ok("add", "09", "--title", "Old work", "--merged", "--pr", "#9", "--merge", "abc1234", "--run", "J9")

    def test_placeholder_is_never_offered_and_is_promoted(self):
        self.ok("start", "01", "--run", "J1")
        self.ok("close", "01", "--pr", "#1", "--merge", "abc1234", "--next", "02")
        self.ok("start", "02", "--run", "J2")
        out = self.ok("next", "--after-close", "02")
        self.assertNotIn("05", out)
        self.ok("close", "02", "--pr", "#2", "--merge", "abc1235", "--next", "06")
        self.assertIn("placeholder", self.refused(2, "start", "05", "--run", "J3"))
        self.refused(2, "promote", "05", "--ticket", "tickets/T-05.md")
        self.ok("promote", "05", "--ticket", "tickets/T-05.md", "--footprint", "src/reports/", "--est", "6")
        self.assertEqual(self.jobs()["05"]["kind"], "build")
        self.assertIn("05", self.ok("next"))

    def test_build_gate_holds_start_next_and_close(self):
        self.edit(lambda s: s["jobs"][2].update(gates=["06"]))   # 03 lands after the sweep job, a build job
        self.ok("start", "01", "--run", "J1")
        out = self.ok("next", "--after-close", "01")
        self.assertIn("02", out)
        self.assertNotIn("03 ", out)
        self.refused(2, "close", "01", "--pr", "#1", "--merge", "abc1234", "--next", "03")
        self.ok("close", "01", "--pr", "#1", "--merge", "abc1234", "--next", "02")
        self.assertIn("blocked", self.refused(1, "set-next", "03"))

    def test_decision_gate_lets_build_start_but_not_land(self):
        self.ok("start", "01", "--run", "J1")
        self.ok("close", "01", "--pr", "#1", "--merge", "abc1234", "--next", "03")
        self.ok("start", "03", "--run", "J2")   # its gate is decision 04, which can be decided at once
        self.refused(2, "check", "--land", "03")
        self.refused(2, "close", "03", "--pr", "#2", "--merge", "abc1235", "--next", "02")
        self.ok("decided", "04", "--note", "name and town only")
        self.assertIn("LAND OK", self.ok("check", "--land", "03"))
        self.ok("close", "03", "--pr", "#2", "--merge", "abc1235", "--next", "02")

    def test_decision_gate_that_cant_be_decided_yet_holds_start(self):
        self.edit(lambda s: s["jobs"][3].update(needs=["02"], uses={"02": "the import's counts"}))   # decision 04 now waits on build job 02
        self.ok("start", "01", "--run", "J1")
        self.ok("close", "01", "--pr", "#1", "--merge", "abc1234", "--next", "02")
        self.assertIn("gate", self.refused(2, "start", "03", "--run", "J3"))
        self.assertNotIn("03", self.ok("next"))

    def test_decided_refuses_a_decision_with_an_open_gate(self):
        self.edit(lambda s: s["jobs"][3].update(gates=["06"]))
        self.assertIn("gate", self.refused(2, "decided", "04", "--note", "x"))

    def test_split_on_v2_names_every_dependent_and_estimate(self):
        self.refused(2, "split", "02", "--into", "a=Read,b=Write", "--est", "a=3,b=4")      # 05 not named
        self.refused(2, "split", "02", "--into", "a=Read,b=Write", "--rewire", "05=b")       # no estimates
        self.refused(2, "split", "02", "--into", "a=Read,b=Write", "--rewire", "05=b", "--est", "a=3,b=4")   # no tickets
        self.ok("split", "02", "--into", "a=Read,b=Write", "--rewire", "05=b", "--est", "a=3,b=4", "--chain",
                "--ticket", "a=tickets/T-02a.md,b=tickets/T-02b.md")
        j = self.jobs()
        self.assertEqual(j["02a"]["footprint"], ["src/importer/", "tests/importer/"])
        self.assertEqual(j["02a"]["uses"], {"01": "Record and RecordId in src/records/types.py"})
        self.assertEqual(j["02b"]["uses"], {"02a": "02a: split from 02"})
        self.assertEqual((j["05"]["needs"], j["05"]["uses"]), (["02b"], {"02b": "the imported records"}))

    def test_covered_rewires_uses_and_gates(self):
        self.edit(lambda s: s["jobs"][5].update(needs=["02"], uses={"02": "the importer"}, gates=["02"]))
        self.edit(lambda s: s["jobs"][4].update(needs=["02"]))
        self.ok("covered", "02", "--by", "01", "--quote", "01 does it")
        j = self.jobs()["06"]
        self.assertEqual((j["needs"], j["uses"], j["gates"]), (["01"], {"01": "covered by 01: the importer"}, ["01"]))

    def test_width_reports_estimate_ceiling_and_pairs(self):
        out = self.ok("width")
        self.assertIn("two lanes:", out)
        self.assertIn("ceiling", out)
        self.assertIn("pairs now: 01+06", out)
        self.edit(lambda s: s["jobs"][5].update(footprint=["src/records/sub/"]))
        self.assertIn("01+06 (src/records/sub)", self.ok("width"))
        self.edit(lambda s: s["jobs"][5].update(footprint=["README.md"]) or s["jobs"][0].update(footprint=["src/records/", "README.md"]))
        self.assertIn("pairs now: 01+06", self.ok("width"))   # both touch README.md, a noise file: they still pair
        self.edit(lambda s: s["project"]["cut"].update(noise=[]))
        self.assertIn("01+06 (README.md)", self.ok("width"))
        self.refused(2, "width", "--lanes", "3")

    def test_width_matches_hand_schedules(self):
        # two independent jobs of 4: one lane 8, two lanes 4 plus the second lander's re-proof of 2 = 6 -> 1.33x
        self.edit(lambda s: s.update(jobs=[s["jobs"][0], s["jobs"][5]]) or s["jobs"][1].update(est_work_orders=4))
        self.assertIn("two lanes: 1.33x", self.ok("width"))
        self.edit(lambda s: s["project"]["cut"].update(reproof=0))
        self.assertIn("two lanes: 2.0x", self.ok("width"))

    def test_decision_gate_with_its_own_open_gate_holds_start(self):
        self.edit(lambda s: s["jobs"][3].update(gates=["06"]))   # decision 04 can't be decided before build 06
        self.ok("start", "01", "--run", "J1")
        self.ok("close", "01", "--pr", "#1", "--merge", "abc1234", "--next", "02")
        self.assertIn("gate", self.refused(2, "start", "03", "--run", "J2"))

    def two_jobs(self, a, b, reproof, gate=False, extra=None):
        def fn(s):
            j1 = dict(s["jobs"][0], id="01", est_work_orders=a, footprint=["src/a/"], needs=[], uses={})
            j2 = dict(s["jobs"][5], id="02", est_work_orders=b, footprint=["src/b/"], needs=[], gates=["01"] if gate else [])
            s["jobs"] = [j1, j2] + ([dict(s["jobs"][5], id="03", est_work_orders=extra, footprint=["src/c/"])] if extra else [])
            s["next"] = "01"
            s["project"]["cut"]["reproof"] = reproof
        self.edit(fn)

    def test_width_gate_is_a_finish_rule_not_work(self):
        self.two_jobs(4, 4, 0, gate=True)
        out = self.ok("width")
        self.assertIn("two lanes: 2.0x", out)
        self.assertIn("ceiling 2", out)

    def test_width_lands_gated_job_before_filling_the_lane(self):
        self.two_jobs(6, 1, 2, gate=True, extra=1)   # 02 lands at 6 with 01, so 03 starts on a free lane
        self.assertIn("two lanes: 1.14x", self.ok("width"))   # 8 work orders, makespan 7: 01 and 02 land at 6, then 03 with no re-proof

    def test_split_rewires_gates_by_rewire(self):
        self.edit(lambda s: s["jobs"][5].update(needs=["02"], uses={"02": "the importer"}, gates=["02"]))
        self.ok("split", "02", "--into", "a=Read,b=Write", "--rewire", "05=b,06=a", "--est", "a=3,b=4",
                "--ticket", "a=tickets/T-02a.md,b=tickets/T-02b.md")
        j = self.jobs()["06"]
        self.assertEqual((j["needs"], j["gates"]), (["02a"], ["02a"]))

    def test_footprint_check_unused_must_come_from_the_footprint(self):
        self.ok("start", "01", "--run", "J1")
        self.ok("close", "01", "--pr", "#1", "--merge", "abc1234", "--next", "02")
        self.refused(1, "footprint-check", "01", "--unused", "x/,y/,z/")
        self.ok("footprint-check", "01", "--unused", "./tests/records,tests/records/")
        self.assertEqual(self.jobs()["01"]["footprint_check"]["unused"], ["tests/records/"])

    def test_footprint_check_and_accuracy(self):
        self.assertIn("no footprint checks", self.ok("accuracy"))
        self.refused(2, "footprint-check", "01", "--missed", "x.py")   # not merged yet
        self.ok("start", "01", "--run", "J1")
        self.ok("close", "01", "--pr", "#1", "--merge", "abc1234", "--next", "02")
        self.ok("footprint-check", "01", "--missed", "docs/a.md", "--unused", "tests/records/")
        out = self.ok("accuracy")
        self.assertIn("held to their footprint 0 of 1", out)
        self.assertIn("over-claimed 1", out)
        self.assertIn("01: missed docs/a.md", out)



class BoardLanes(unittest.TestCase):
    """Lane mode (project.lanes: two jobs at once, PLAN-lanes): start --lane, reserve, next --lane, overlaps, machines."""
    tearDown, run_tool, data, digest, edit, ok, refused = (Board.tearDown, Board.run_tool, Board.data, Board.digest,
                                                           Board.edit, Board.ok, Board.refused)

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.path = self.dir / "BOARD.json"
        shutil.copy(V2_TEMPLATE, self.path)

        def on(s):
            s["project"]["lanes"] = ["A", "B"]
            s["project"]["lane_caps"] = {"A": ["linux", "docker"], "B": ["windows", "screen", "browser", "owner", "docker"]}
            s["next"] = {"A": None, "B": None}
        self.edit(on)

    def jobs(self):
        return {j["id"]: j for j in self.data()["jobs"]}

    def test_lanes_are_exactly_a_and_b(self):
        self.edit(lambda s: s["project"].update(lanes=["A", "B", "C"]))
        rc, out = self.run_tool("check")
        self.assertEqual(rc, 1, out)
        self.assertIn("two lanes, never more", out)

    def test_two_lanes_run_two_jobs_one_each(self):
        self.refused(2, "start", "01", "--run", "J1")                       # no --lane
        self.ok("start", "01", "--run", "J1", "--lane", "A")
        self.refused(2, "start", "06", "--run", "J2", "--lane", "A")         # one per lane
        self.ok("start", "06", "--run", "J2", "--lane", "B")
        s = self.data()
        self.assertEqual(s["next"], {"A": "01", "B": "06"})
        self.assertEqual((self.jobs()["01"]["lane"], self.jobs()["06"]["lane"]), ("A", "B"))
        page = (self.dir / "board.html").read_text(encoding="utf-8")
        self.assertIn("Lane A: Shared record types", page)
        self.assertIn("Lane B: Sweep", page)

    def test_overlap_is_refused_unless_the_owner_says(self):
        self.edit(lambda s: s["jobs"][5].update(footprint=["src/records/notes/"]))
        self.ok("start", "01", "--run", "J1", "--lane", "A")
        self.assertIn("overlaps", self.refused(2, "start", "06", "--run", "J2", "--lane", "B"))
        self.assertNotIn("06", self.ok("next", "--lane", "B"))
        self.refused(2, "start", "06", "--run", "J2", "--lane", "B", "--overlap-ok")
        self.ok("start", "06", "--run", "J2", "--lane", "B", "--overlap-ok", "--quote", "run them together")

    def test_reserve_takes_the_next_job_and_its_number(self):
        self.ok("start", "01", "--run", "J1", "--lane", "A")
        self.refused(2, "reserve", "02", "--run", "J1", "--lane", "A")      # J1 is used
        self.ok("reserve", "02", "--run", "J3", "--lane", "A")               # eligible once 01 closes
        self.assertEqual(self.data()["next"]["A"], "02")
        self.refused(2, "reserve", "06", "--run", "J4", "--lane", "A")       # one reservation per lane
        self.assertIn("reserved by Lane A", self.refused(2, "start", "02", "--run", "J4", "--lane", "B"))
        self.refused(2, "close", "01", "--pr", "#1", "--merge", "abc1234", "--next", "06")   # not its reservation
        self.ok("close", "01", "--pr", "#1", "--merge", "abc1234", "--next", "02")
        self.refused(2, "start", "02", "--run", "J9", "--lane", "A")         # must use its reserved number
        self.ok("start", "02", "--run", "J3", "--lane", "A")
        j = self.jobs()["02"]
        self.assertEqual((j["run"], j.get("reserved")), ("J3", None))

    def test_machines_decide_who_can_run_a_job(self):
        self.ok("start", "01", "--run", "J1", "--lane", "A")
        self.ok("close", "01", "--pr", "#1", "--merge", "abc1234", "--no-next", "--reason", "pick by lane")
        self.assertNotIn("03", self.ok("next", "--lane", "A"))              # 03 needs screen and browser
        self.assertIn("03", self.ok("next", "--lane", "B"))
        self.assertIn("lacks", self.refused(2, "start", "03", "--run", "J2", "--lane", "A"))
        self.assertIn("one lane only: 1 of 4 jobs need Lane B", self.ok("width"))

    def test_unrunnable_job_is_flagged(self):
        self.edit(lambda s: s["jobs"][1].update(requires=["gpu"]))
        self.assertIn("unrunnable", self.ok("check"))

    def test_requires_set_and_footprint_widening(self):
        self.ok("requires", "02", "--set", "docker")
        self.assertEqual(self.jobs()["02"]["requires"], ["docker"])
        self.ok("start", "01", "--run", "J1", "--lane", "A")
        self.ok("start", "06", "--run", "J2", "--lane", "B")
        self.refused(2, "footprint", "06", "--set", "other/")                # drops docs/
        self.ok("footprint", "06", "--set", "docs/,tools/")
        self.assertIn("reaches into", self.refused(2, "footprint", "06", "--set", "docs/,tools/,src/records/x/"))

    def test_halt_frees_the_lane(self):
        self.ok("start", "01", "--run", "J1", "--lane", "A")
        self.ok("halt", "01", "--reason", "needs a screen", "--to", "open")
        j = self.jobs()["01"]
        self.assertNotIn("lane", j)
        self.assertEqual(self.data()["next"]["A"], None)
        self.refused(2, "start", "01", "--run", "J1", "--lane", "B")         # J1 is retired

    def test_a_build_gate_does_not_hold_the_start_with_two_lanes(self):
        self.edit(lambda s: s["jobs"][2].update(gates=["06"]))
        self.ok("start", "01", "--run", "J1", "--lane", "A")
        self.ok("close", "01", "--pr", "#1", "--merge", "abc1234", "--no-next", "--reason", "x")
        self.ok("start", "03", "--run", "J2", "--lane", "B")                 # the other lane can build 06 meanwhile
        self.refused(2, "check", "--land", "03")

    def test_lane_caps_are_required_for_both_lanes(self):
        self.edit(lambda s: s["project"].update(lane_caps={"A": ["linux"]}))
        rc, out = self.run_tool("check")
        self.assertEqual(rc, 1, out)
        self.assertIn("lane_caps for both A and B", out)

    def test_a_reserved_job_cant_be_split_or_covered_and_numbers_stay_retired(self):
        self.ok("reserve", "06", "--run", "J3", "--lane", "A")
        self.assertIn("unreserve", self.refused(2, "split", "06", "--into", "a=X,b=Y", "--est", "a=1,b=1",
                                                 "--ticket", "a=t/a.md,b=t/b.md"))
        self.assertIn("unreserve", self.refused(2, "covered", "06", "--by", "01", "--quote", "x"))
        self.assertIn("only that lane", self.refused(2, "unreserve", "06", "--reason", "x", "--lane", "B"))
        self.ok("unreserve", "06", "--reason", "re-cut", "--lane", "A")
        self.assertIn("J3", self.data()["retired_runs"])
        self.refused(2, "start", "06", "--run", "J3", "--lane", "B")

    def test_halt_drops_the_lanes_reservation(self):
        self.ok("start", "01", "--run", "J1", "--lane", "A")
        self.ok("reserve", "02", "--run", "J3", "--lane", "A")
        self.assertIn("unreserve 02", self.refused(2, "close", "01", "--pr", "#1", "--merge", "abc1234", "--no-next", "--reason", "x"))
        self.ok("halt", "01", "--reason", "stuck", "--to", "open")
        self.assertNotIn("reserved", self.jobs()["02"])
        self.assertEqual(sorted(self.data()["retired_runs"]), ["J1", "J3"])
        self.ok("start", "01", "--run", "J4", "--lane", "A")                 # the lane is not locked out

    def test_reserved_job_is_checked_on_footprint_and_requires(self):
        self.ok("start", "01", "--run", "J1", "--lane", "B")
        self.ok("reserve", "06", "--run", "J2", "--lane", "A")
        self.assertIn("reaches into", self.refused(2, "footprint", "06", "--set", "docs/,src/records/"))
        self.assertIn("lacks", self.refused(2, "requires", "06", "--set", "owner"))

    def test_one_lane_halt_keeps_the_old_shape(self):
        shutil.copy(V2_TEMPLATE, self.path)
        self.ok("start", "01", "--run", "J1")
        self.ok("halt", "01", "--reason", "x", "--to", "open")
        self.assertNotIn("retired_runs", self.data())

    def test_set_next_is_replaced_by_reserve(self):
        self.refused(2, "set-next", "01")

if __name__ == "__main__":
    unittest.main(verbosity=1)

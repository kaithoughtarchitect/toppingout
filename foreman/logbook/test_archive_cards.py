#!/usr/bin/env python3
"""Tests for archive_cards.py. Temp dirs only; the real Logbook is never touched.

Run from the repository root:  python foreman/logbook/test_archive_cards.py
"""

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import archive_cards as ac  # noqa: E402

CARDS = {
    "entries/methods/METHOD_20260101_ALPHA.md": "---\nid: METHOD_20260101_ALPHA\ncluster: testing\n---\nalpha\n",
    "entries/methods/METHOD_20260102_BETA.md": "---\nid: METHOD_20260102_BETA\ncluster: testing\n---\nbeta\n",
    "entries/insights/INSIGHT_20260103_GAMMA.md": "---\nid: INSIGHT_20260103_GAMMA\ncluster: security\n---\ngamma\n",
    "entries/builds/BUILD_20260104_DELTA.md": "---\nid: BUILD_20260104_DELTA\ncluster: architecture\n---\ndelta\n",
}
TEMPLATES = {
    "entries/methods/METHOD-TEMPLATE.md": "method template\n",
    "entries/insights/INSIGHT-TEMPLATE.md": "insight template\n",
    "entries/builds/BUILD-TEMPLATE.md": "build template\n",
}
CORE = {"logbook_index.md": "# index\n", "logbook_links.md": "# links\n"}


class ArchiveCardsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="archive-cards-test-"))
        self.lb = self.tmp / "foreman" / "logbook"
        for rel, text in {**CARDS, **TEMPLATES, **CORE}.items():
            p = self.lb / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8", newline="\n")
        (self.lb / "archived").mkdir()
        self.keep = self.tmp / "keep.txt"
        self.keep.write_text("METHOD_20260101_ALPHA\n", encoding="utf-8")
        self.adir = self.lb / "archived" / "001"
        self._orig_copy, self._orig_hook, self._orig_unlink = ac.copy_file, ac.after_copy_hook, ac.unlink_file

    def tearDown(self):
        ac.copy_file, ac.after_copy_hook, ac.unlink_file = self._orig_copy, self._orig_hook, self._orig_unlink
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ac.main(["--root", str(self.tmp), *argv])
        return code, out.getvalue() + err.getvalue()

    def archive(self):
        return self.run_cli("archive", "--archive", "001", "--keep", str(self.keep))

    def live(self, rel):
        return self.lb / rel

    # --- happy path -----------------------------------------------------------

    def test_happy_path_archive_verify_restore(self):
        code, out = self.run_cli("plan", "--archive", "001", "--keep", str(self.keep))
        self.assertEqual(code, 0, out)
        self.assertFalse(self.adir.exists(), "plan must write nothing")

        code, out = self.archive()
        self.assertEqual(code, 0, out)
        for rel in CARDS:
            self.assertTrue((self.adir / rel).is_file(), rel)
        for rel in CORE:
            self.assertTrue((self.adir / rel).is_file(), rel)
        self.assertTrue(self.live("entries/methods/METHOD_20260101_ALPHA.md").is_file(), "kept card stays")
        for rel in CARDS:
            if "ALPHA" not in rel:
                self.assertFalse(self.live(rel).exists(), f"{rel} should be deleted")
        for rel in CORE:
            self.assertTrue(self.live(rel).is_file(), "index/links never deleted")

        code, out = self.run_cli("verify", "--archive", "001")
        self.assertEqual(code, 0, out)

        code, out = self.run_cli("restore", "--archive", "001")
        self.assertEqual(code, 0, out)
        for rel, text in CARDS.items():
            self.assertEqual(self.live(rel).read_text(encoding="utf-8"), text)
        self.assertTrue(self.adir.is_dir(), "archive is never deleted")

    def test_manifest_uses_relative_posix_paths(self):
        self.assertEqual(self.archive()[0], 0)
        manifest = json.loads((self.adir / "MANIFEST.json").read_text(encoding="utf-8"))
        paths = [f["path"] for f in manifest["files"]]
        self.assertEqual(sorted(paths), sorted(list(CARDS) + list(CORE)))
        for f in manifest["files"]:
            self.assertNotIn("\\", f["path"])
            self.assertFalse(f["path"].startswith("/") or ":" in f["path"] or "*" in f["path"])
            self.assertRegex(f["sha256"], r"^[0-9a-f]{64}$")
            self.assertIsInstance(f["size"], int)
        self.assertEqual(manifest["kept"], ["METHOD_20260101_ALPHA"])

    # --- faults ---------------------------------------------------------------

    def test_destination_corrupted_before_verify_deletes_nothing(self):
        def corrupt(dst):
            if dst.name == "INSIGHT_20260103_GAMMA.md":
                dst.write_text("corrupted\n", encoding="utf-8")
        ac.after_copy_hook = corrupt
        code, out = self.archive()
        self.assertEqual(code, 1, out)
        self.assertIn("MISMATCH entries/insights/INSIGHT_20260103_GAMMA.md", out)
        for rel in CARDS:
            self.assertTrue(self.live(rel).is_file(), f"{rel} must survive a failed verify")
        self.assertTrue(self.adir.is_dir(), "archive folder kept on failure")

    def test_missing_copy_deletes_nothing(self):
        orig = ac.copy_file

        def skip_one(src, dst):
            if src.name != "BUILD_20260104_DELTA.md":
                orig(src, dst)
        ac.copy_file = skip_one
        code, out = self.archive()
        self.assertEqual(code, 1, out)
        self.assertIn("MISSING  entries/builds/BUILD_20260104_DELTA.md", out)
        for rel in CARDS:
            self.assertTrue(self.live(rel).is_file(), rel)

    def test_failed_attempt_can_be_resumed(self):
        ac.after_copy_hook = lambda dst: dst.write_text("bad\n", encoding="utf-8")
        self.assertEqual(self.archive()[0], 1)
        ac.after_copy_hook = self._orig_hook
        code, out = self.archive()
        self.assertEqual(code, 0, out)
        self.assertIn("resuming", out)

    def test_restore_refuses_corrupted_archive(self):
        self.assertEqual(self.archive()[0], 0)
        (self.adir / "entries/insights/INSIGHT_20260103_GAMMA.md").write_text("rot\n", encoding="utf-8")
        code, out = self.run_cli("verify", "--archive", "001")
        self.assertEqual(code, 1, out)
        code, out = self.run_cli("restore", "--archive", "001")
        self.assertEqual(code, 1, out)
        self.assertIn("ARCHIVE DAMAGED", out)
        self.assertFalse(self.live("entries/methods/METHOD_20260102_BETA.md").exists(), "nothing restored")
        self.assertTrue(self.adir.is_dir())

    def test_restore_does_not_overwrite_differing_live_card(self):
        self.assertEqual(self.archive()[0], 0)
        kept = self.live("entries/methods/METHOD_20260101_ALPHA.md")
        kept.write_text("edited after the archive\n", encoding="utf-8")
        code, out = self.run_cli("restore", "--archive", "001")
        self.assertEqual(code, 0, out)
        self.assertIn("DIFFERS  entries/methods/METHOD_20260101_ALPHA.md", out)
        self.assertEqual(kept.read_text(encoding="utf-8"), "edited after the archive\n")
        self.assertTrue(self.live("entries/methods/METHOD_20260102_BETA.md").is_file())

    def test_templates_never_touched(self):
        before = {rel: self.live(rel).read_bytes() for rel in TEMPLATES}
        self.assertEqual(self.archive()[0], 0)
        self.assertEqual(self.run_cli("restore", "--archive", "001")[0], 0)
        for rel, data in before.items():
            self.assertEqual(self.live(rel).read_bytes(), data)
            self.assertFalse((self.adir / rel).exists(), f"{rel} must not be archived")

    def test_existing_different_archive_dir_refused(self):
        self.adir.mkdir(parents=True)
        (self.adir / "MANIFEST.json").write_text(
            json.dumps({"files": [{"path": "entries/methods/OTHER_20250101_X.md", "sha256": "0" * 64, "size": 1}]}),
            encoding="utf-8")
        code, out = self.archive()
        self.assertEqual(code, 1, out)
        self.assertIn("different archive", out)
        for rel in CARDS:
            self.assertTrue(self.live(rel).is_file())

    def test_existing_dir_without_manifest_refused(self):
        self.adir.mkdir(parents=True)
        (self.adir / "stray.md").write_text("x\n", encoding="utf-8")
        code, out = self.archive()
        self.assertEqual(code, 1, out)
        code, out = self.run_cli("plan", "--archive", "001")
        self.assertEqual(code, 1, out)

    def test_unknown_keep_id_refused_before_writing(self):
        self.keep.write_text("METHOD_20260101_ALHPA\n", encoding="utf-8")
        code, out = self.archive()
        self.assertEqual(code, 1, out)
        self.assertFalse(self.adir.exists())

    def test_empty_logbook_archives_nothing(self):
        for rel in CARDS:
            self.live(rel).unlink()
        code, out = self.run_cli("archive", "--archive", "001", "--keep", str(self.keep))
        self.assertEqual(code, 0, out)
        self.assertIn("nothing to archive", out)
        self.assertFalse(self.adir.exists())

    # --- review fixes ---------------------------------------------------------

    def outside_files(self):
        """Every file under the temp root that is not inside the logbook (keep.txt aside)."""
        return sorted(p for p in self.tmp.rglob("*")
                      if p.is_file() and p != self.keep and self.lb not in p.parents)

    def test_tampered_manifest_paths_refused(self):
        self.assertEqual(self.archive()[0], 0)
        mpath = self.adir / "MANIFEST.json"
        good = json.loads(mpath.read_text(encoding="utf-8"))
        # Plant a file the traversal resolves to from the archive folder (adir/../.. is the
        # logbook), so an unguarded restore would find a matching "archived copy" and write
        # it to <logbook>/../../ESCAPED.md, outside the logbook.
        planted = self.lb / "ESCAPED.md"
        planted.write_text("escape\n", encoding="utf-8", newline="\n")
        beta = {"sha256": ac.sha256_of(planted), "size": planted.stat().st_size}
        drive = "C:/ESCAPED.md" if sys.platform == "win32" else "C:ESCAPED.md"
        for bad in ("..\\..\\ESCAPED.md", "entries\\..\\..\\..\\ESCAPED.md", "/ESCAPED.md",
                    str(self.tmp / "ESCAPED.md"), drive, "C:ESCAPED.md", "../ESCAPED.md",
                    "entries/./x.md", "entries//x.md", ""):
            with self.subTest(path=bad):
                data = json.loads(json.dumps(good))
                data["files"].append({"path": bad, "sha256": beta["sha256"], "size": beta["size"]})
                mpath.write_text(json.dumps(data), encoding="utf-8")
                for cmd in (("restore", "--archive", "001"), ("verify", "--archive", "001")):
                    code, out = self.run_cli(*cmd)
                    self.assertEqual(code, 1, out)
                    self.assertIn("unsafe path", out)
                code, out = self.archive()
                self.assertEqual(code, 1, out)
                self.assertEqual(self.outside_files(), [], "nothing written outside the logbook")
                self.assertFalse(self.live("entries/methods/METHOD_20260102_BETA.md").exists(), "nothing restored")

    def test_keep_id_collision_refused(self):
        # BETA's frontmatter id equals ALPHA's filename id: ambiguous, never guessed.
        self.live("entries/methods/METHOD_20260102_BETA.md").write_text(
            "---\nid: METHOD_20260101_ALPHA\n---\nbeta\n", encoding="utf-8", newline="\n")
        code, out = self.archive()
        self.assertEqual(code, 1, out)
        self.assertIn("names two cards", out)
        self.assertFalse(self.adir.exists(), "nothing written")
        for rel in CARDS:
            self.assertTrue(self.live(rel).is_file(), rel)

    def test_interrupted_delete_resumes(self):
        calls = []

        def fail_second(path):
            calls.append(path)
            if len(calls) == 2:
                raise OSError("injected unlink failure")
            path.unlink()
        ac.unlink_file = fail_second
        try:
            code, out = self.archive()
        finally:
            ac.unlink_file = self._orig_unlink
        self.assertEqual(code, 1, out)
        self.assertIn("injected unlink failure", out)
        survivors = [rel for rel in CARDS if "ALPHA" not in rel and self.live(rel).exists()]
        self.assertEqual(len(survivors), 2, "one deleted, the failing one and one more left")

        code, out = self.run_cli("plan", "--archive", "001", "--keep", str(self.keep))
        self.assertEqual(code, 0, out)
        self.assertIn("will finish the deletes", out)
        code, out = self.archive()
        self.assertEqual(code, 0, out)
        self.assertIn("resuming interrupted deletes", out)
        for rel in CARDS:
            self.assertEqual(self.live(rel).exists(), "ALPHA" in rel, rel)
        self.assertEqual(self.run_cli("verify", "--archive", "001")[0], 0)
        code, out = self.run_cli("restore", "--archive", "001")
        self.assertEqual(code, 0, out)
        for rel, text in CARDS.items():
            self.assertEqual(self.live(rel).read_text(encoding="utf-8"), text)

    def test_interrupted_delete_changed_card_left_in_place(self):
        calls = []

        def fail_first(path):
            calls.append(path)
            if len(calls) == 1:
                raise OSError("injected unlink failure")
            path.unlink()
        ac.unlink_file = fail_first
        try:
            self.assertEqual(self.archive()[0], 1)
        finally:
            ac.unlink_file = self._orig_unlink
        # all three non-kept cards are still live; delete one by hand, edit another
        self.live("entries/builds/BUILD_20260104_DELTA.md").unlink()
        gamma = self.live("entries/insights/INSIGHT_20260103_GAMMA.md")
        gamma.write_text("edited\n", encoding="utf-8")
        code, out = self.archive()
        self.assertEqual(code, 1, out)
        self.assertIn("CHANGED  entries/insights/INSIGHT_20260103_GAMMA.md", out)
        self.assertEqual(gamma.read_text(encoding="utf-8"), "edited\n")
        self.assertFalse(self.live("entries/methods/METHOD_20260102_BETA.md").exists())

    def test_interrupted_delete_with_new_live_card_refused(self):
        self.assertEqual(self.archive()[0], 0)
        new = self.live("entries/methods/METHOD_20260105_NEW.md")
        new.write_text("---\nid: METHOD_20260105_NEW\n---\nnew\n", encoding="utf-8")
        code, out = self.archive()
        self.assertEqual(code, 1, out)
        self.assertIn("different archive", out)
        self.assertTrue(new.is_file())

    def test_usage_errors_exit_2(self):
        self.assertEqual(self.run_cli("archive", "--archive", "001")[0], 2)  # --keep missing
        self.assertEqual(self.run_cli("verify", "--archive", "1a")[0], 2)
        self.assertEqual(self.run_cli("archive", "--archive", "001", "--keep", str(self.tmp / "nope"))[0], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)

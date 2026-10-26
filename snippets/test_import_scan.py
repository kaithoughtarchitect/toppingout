"""Tests for import_scan.py. Temp dirs only.

Run:  python snippets/test_import_scan.py
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import import_scan  # noqa: E402


class ImportScanTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="import-scan-test-"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, files):
        for rel, text in files.items():
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8", newline="\n")

    def scan(self, *targets, roots=()):
        return [p.relative_to(self.root).as_posix() for p in import_scan.scan(self.root, list(roots), list(targets))]

    def test_absolute_and_flat_relative_imports(self):
        self.write({
            "app/__init__.py": "",
            "app/billing/__init__.py": "",
            "app/billing/invoice.py": "X = 1\n",
            "tests/__init__.py": "",
            "tests/test_abs.py": "from app.billing.invoice import X\n",
            "tests/test_mod.py": "import app.billing.invoice\n",
            "tests/test_from_pkg.py": "from app.billing import invoice\n",
            "tests/test_other.py": "import os\n",
            "app/billing/test_inpkg.py": "from .invoice import X\n",
            "app/billing/test_inpkg_dot.py": "from . import invoice\n",
        })
        self.assertEqual(self.scan("app.billing.invoice"), [
            "app/billing/test_inpkg.py",
            "app/billing/test_inpkg_dot.py",
            "tests/test_abs.py",
            "tests/test_from_pkg.py",
            "tests/test_mod.py",
        ])

    def test_relative_level_above_one(self):
        self.write({
            "app/__init__.py": "",
            "app/billing/__init__.py": "",
            "app/billing/invoice.py": "",
            "app/tests/__init__.py": "",
            "app/tests/unit/__init__.py": "",
            "app/tests/test_rel2.py": "from ..billing import invoice\n",
            "app/tests/unit/test_rel3.py": "from ...billing.invoice import X\n",
            "app/tests/unit/test_miss.py": "from ..billing import invoice\n",  # resolves to app.tests.billing
        })
        self.assertEqual(self.scan("app.billing.invoice"), [
            "app/tests/test_rel2.py",
            "app/tests/unit/test_rel3.py",
        ])

    def test_package_init_reexport(self):
        self.write({
            "app/__init__.py": "",
            "app/billing/__init__.py": "from . import invoice\n",
            "app/billing/invoice.py": "",
            "app/billing/tax.py": "",
            "tests/test_pkg.py": "import app.billing\n",
            "tests/test_tax.py": "from app.billing.tax import rate\n",  # runs app/billing/__init__ too
            "tests/test_unrelated.py": "import json\n",
        })
        self.assertEqual(self.scan("app.billing.invoice"), ["tests/test_pkg.py", "tests/test_tax.py"])

    def test_src_layout(self):
        self.write({
            "src/app/__init__.py": "",
            "src/app/billing/__init__.py": "",
            "src/app/billing/invoice.py": "",
            "src/app/tests/__init__.py": "",
            "src/app/tests/test_rel.py": "from ..billing import invoice\n",
            "tests/test_abs.py": "from app.billing.invoice import X\n",
            "tests/test_src_prefixed.py": "import src.app.billing.invoice\n",
            "tests/test_none.py": "import app.billing.tax\n",
        })
        self.assertEqual(import_scan.module_name(self.root / "src/app/tests/test_rel.py", self.root), "app.tests.test_rel")
        self.assertEqual(self.scan("app.billing.invoice"), [
            "src/app/tests/test_rel.py",
            "tests/test_abs.py",
            "tests/test_src_prefixed.py",
        ])

    def test_helper_intermediate(self):
        self.write({
            "app/__init__.py": "",
            "app/billing/__init__.py": "",
            "app/billing/invoice.py": "",
            "tests/helpers.py": "from app.billing.invoice import make\n",
            "tests/deeper.py": "from helpers import *\n",
            "tests/test_x.py": "from helpers import *\n",
            "tests/test_y.py": "import deeper\n",
            "tests/test_z.py": "import json\n",
            "other/test_far.py": "from helpers import *\n",  # a different folder's helpers, not this one
        })
        self.assertEqual(self.scan("app.billing.invoice"), ["tests/test_x.py", "tests/test_y.py"])

    def test_sibling_fixed_point_and_no_over_selection(self):
        self.write({
            "app/__init__.py": "",
            "app/core.py": "",
            "a/test_a.py": "import app.core\n",
            "a/test_a2.py": "import test_a\n",          # sibling of a selected test: selected
            "a/test_a3.py": "from test_a2 import *\n",  # transitively: selected
            "b/test_b.py": "import app.core\n",
            # Counterexample: b/ holds a selected test (test_b) and a/ holds one named test_a,
            # but b/test_c imports b's own unrelated test_a. Separate stem/parent sets selected it.
            "b/test_a.py": "import json\n",
            "b/test_c.py": "import test_a\n",
        })
        self.assertEqual(self.scan("app.core"), [
            "a/test_a.py", "a/test_a2.py", "a/test_a3.py", "b/test_b.py",
        ])

    def test_unparsable_test_is_selected(self):
        self.write({"tests/test_broken.py": "def (:\n", "tests/test_ok.py": "import json\n"})
        self.assertEqual(self.scan("app.core"), ["tests/test_broken.py"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

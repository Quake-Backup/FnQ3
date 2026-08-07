from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import generate_docs


class GenerateDocsTests(unittest.TestCase):
    def test_render_reports_missing_template_keys_with_template_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            template = Path(tmp) / "README.md.in"
            template.write_text("FnQ3 $version $missing_key\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "missing_key"):
                generate_docs.render(template, {"version": "0.1.0"})

    def test_generated_docs_are_written_with_lf_endings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "nested" / "README.html"

            self.assertTrue(generate_docs.write_if_changed(target, "first\nsecond\n"))
            self.assertEqual(target.read_bytes(), b"first\nsecond\n")
            # Unchanged content must not rewrite the file.
            self.assertFalse(generate_docs.write_if_changed(target, "first\nsecond\n"))

    def test_writer_avoids_apis_the_release_container_python_lacks(self) -> None:
        """The Linux release lanes run this in an ubuntu:20.04 container, whose
        Python 3.8 has no newline argument on Path.write_text(). Adding one there
        fails only on those lanes, long after the change looks fine locally."""
        source = (ROOT / "scripts" / "generate_docs.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"write_text\([^)]*newline", source))
        self.assertIn('path.open("w", encoding="utf-8", newline="\\n")', source)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts import changelog


class ChangelogTests(unittest.TestCase):
    def test_clean_section_dedupes_and_sorts_legacy_headings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CHANGELOG.md"
            path.write_text(
                "\n".join(
                    [
                        "# Changelog",
                        "",
                        "## [Unreleased]",
                        "",
                        "### Added",
                        "- Added `r_picmipFilter` to control texture picmip.",
                        "- Added `r_picmipFilter` to control texture picmip.",
                        "",
                        "### Changed",
                        "- Release archives no longer include debug build products.",
                        "",
                        "### Fixed",
                        "- Fixed a crash when loading a renderer.",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            cleaned = changelog.clean_section_text(path, "Unreleased")

        self.assertIn("### Rendering and Display", cleaned)
        self.assertIn("- Added `r_picmipFilter` to control texture picmip.", cleaned)
        self.assertEqual(cleaned.count("r_picmipFilter"), 1)
        self.assertIn("### Builds and Packaging", cleaned)
        self.assertIn("### Fixes", cleaned)

    def test_clear_unreleased_resets_to_empty_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CHANGELOG.md"
            path.write_text(
                "\n".join(
                    [
                        "# Changelog",
                        "",
                        "## [Unreleased]",
                        "",
                        "### Highlights",
                        "- Something ready for release.",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            changelog.clear_unreleased(path)
            cleared = path.read_text(encoding="utf-8")

        self.assertNotIn("Something ready for release", cleared)
        for category in changelog.CHANGELOG_CATEGORIES:
            self.assertIn(f"### {category}", cleared)
        self.assertEqual(cleared.count("- _None yet._"), len(changelog.CHANGELOG_CATEGORIES))


if __name__ == "__main__":
    unittest.main()

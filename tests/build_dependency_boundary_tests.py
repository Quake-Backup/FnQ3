from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY_BUILD_FILES = (
    ROOT / "CMakeLists.txt",
    ROOT / "Makefile",
    ROOT / "make-macosx-app.sh",
    ROOT / "make-macosx-ub2.sh",
)
REMOVED_VENDOR_DIRS = (
    "libcurl",
    "libjpeg",
    "libogg",
    "libvorbis",
    "libsdl",
    "openal",
)


class BuildDependencyBoundaryTests(unittest.TestCase):
    def test_legacy_builds_do_not_reference_removed_vendor_trees(self) -> None:
        removed_path = re.compile(
            r"(?:code|\$\(MOUNT_DIR\))[\\/]"
            rf"(?:{'|'.join(REMOVED_VENDOR_DIRS)})(?:[\\/]|\b)",
            flags=re.IGNORECASE,
        )

        offenders: list[str] = []
        for path in LEGACY_BUILD_FILES:
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if removed_path.search(line):
                    offenders.append(f"{path.name}:{line_number}: {line.strip()}")

        self.assertEqual(offenders, [])

    def test_cmake_runtime_staging_is_explicit(self) -> None:
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")

        self.assertIn('SET(FNQ3_OPENAL_RUNTIME "" CACHE FILEPATH', cmake)
        self.assertIn('if(FNQ3_OPENAL_RUNTIME AND NOT EXISTS', cmake)
        self.assertIn('find_package(OpenAL QUIET)', cmake)

    def test_make_runtime_staging_uses_caller_supplied_paths(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("CLIENT_EXTRA_FILES += $(SDL_RUNTIME)", makefile)
        self.assertIn("CLIENT_EXTRA_FILES += $(OPENAL_RUNTIME)", makefile)
        self.assertIn("CLIENT_LDFLAGS += $(SDL_LIBS)", makefile)


if __name__ == "__main__":
    unittest.main()

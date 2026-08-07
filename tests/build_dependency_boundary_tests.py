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


def workflow_job_block(workflow: str, job_name: str) -> str:
    lines = workflow.splitlines()
    heading = f"  {job_name}:"
    try:
        start = lines.index(heading)
    except ValueError as exc:
        raise AssertionError(f"missing workflow job: {job_name}") from exc

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if re.fullmatch(r"  [A-Za-z0-9_-]+:", lines[index]):
            end = index
            break
    return "\n".join(lines[start:end])


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

    def test_meson_runtime_installs_exclude_development_and_subproject_artifacts(
        self,
    ) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )
        for job_name in ("windows-msys32", "windows-msvc"):
            with self.subTest(job=job_name):
                job = workflow_job_block(workflow, job_name)
                install_commands = [
                    line.strip()
                    for line in job.splitlines()
                    if "meson install -C meson" in line
                ]
                self.assertEqual(len(install_commands), 1)
                self.assertIn("--tags runtime", install_commands[0])
                self.assertIn("--skip-subprojects", install_commands[0])

        build_script = (ROOT / ".vscode" / "build-release.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("[string]$InstallTags = 'runtime'", build_script)
        self.assertIn("'--no-rebuild', '--skip-subprojects'", build_script)

        build_guide = (ROOT / "BUILD.md").read_text(encoding="utf-8")
        self.assertIn(
            "--destdir dist --tags runtime --skip-subprojects",
            build_guide,
        )

    def test_meson_runtime_install_includes_required_release_docs(self) -> None:
        meson = (ROOT / "meson.build").read_text(encoding="utf-8")
        required_docs = {
            "LICENSE": ".",
            "THIRD_PARTY_NOTICES.md": ".",
            ".install/README.html": ".",
            "docs/GLX.md": "docs",
            "docs/RTX.md": "docs",
            "docs/fnquake3/TECHNICAL.md": "docs/fnquake3",
        }

        for source, install_dir in required_docs.items():
            with self.subTest(source=source):
                pattern = re.compile(
                    rf"install_data\('{re.escape(source)}',\s*"
                    rf"install_dir: '{re.escape(install_dir)}',\s*"
                    r"install_tag: 'runtime',\s*\)",
                    re.MULTILINE,
                )
                self.assertRegex(meson, pattern)

    def test_third_party_notice_bundle_covers_bundled_dependencies(self) -> None:
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")

        for required_notice in (
            "COPYRIGHT AND PERMISSION NOTICE",
            "Independent JPEG Group",
            "Copyright (c) 2002, Xiph.org Foundation",
            "Copyright (c) 2002-2020 Xiph.org Foundation",
            "GNU LIBRARY GENERAL PUBLIC LICENSE",
            "Copyright (C) 1997-2025 Sam Lantinga",
        ):
            with self.subTest(required_notice=required_notice):
                self.assertIn(required_notice, notices)


if __name__ == "__main__":
    unittest.main()

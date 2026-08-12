"""Gates for the "the Windows package ships everything it needs" guarantee.

`meson install` stages the engine binaries, the renderer modules, the data pack
and the docs -- and no runtime libraries. Any other DLL a produced binary
imports has to already exist on the player's machine, and when it does not the
only symptom is a launch-time message box. A published build once shipped with
a libzstd import because the bundled curl left its optional features on `auto`
and the MSYS2 runner happened to have libzstd installed as a gcc dependency.

Two things keep that from recurring, and both are gated here: the build is
configured so nothing outside the OS can be linked in, and the artifact is
audited afterwards for imports it cannot satisfy.
"""

from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_windows_dll_deps as audit


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class BundledCurlIsSelfContainedTests(unittest.TestCase):
    def test_optional_curl_features_cannot_pick_up_host_libraries(self) -> None:
        meson = read_text("meson.build")
        start = meson.index("curl_fallback_defaults = ")
        block = meson[start:meson.index("openal_fallback_defaults", start)]

        # zstd is the one that actually shipped broken; the rest are the same
        # class of 'auto' feature and would each have become a missing DLL.
        for feature in (
            "brotli",
            "gsasl",
            "gss-api",
            "http2",
            "idn",
            "libuv",
            "libz",
            "psl",
            "rtmp",
            "ssh",
            "zstd",
        ):
            with self.subTest(feature=feature):
                self.assertIn(f"'{feature}=disabled'", block)

        # Windows takes TLS from Schannel, which is part of the OS. Elsewhere
        # the fallback is only reached with --wrap-mode=forcefallback, where
        # dropping OpenSSL would silently produce an HTTP-only curl.
        self.assertIn("'openssl=disabled'", block)
        self.assertIn("if host_machine.system() == 'windows'", block)

        # Static subprojects are what make the disabled features moot at link
        # time rather than merely unrequested.
        self.assertIn("fallback_defaults = ['default_library=static']", meson)


def workflow_jobs(workflow: str) -> dict[str, str]:
    """Split the workflow into job bodies without needing a YAML parser.

    The Linux validation lane installs meson from apt and runs these tests with
    the system interpreter, so PyYAML is not guaranteed to be importable.
    """
    jobs: dict[str, str] = {}
    name: str | None = None
    lines: list[str] = []
    for line in workflow.splitlines():
        if (
            line.startswith("  ")
            and not line.startswith("   ")
            and line.rstrip().endswith(":")
            and line.strip(" :").replace("-", "").isalnum()
        ):
            if name is not None:
                jobs[name] = "\n".join(lines)
            name = line.strip().rstrip(":")
            lines = []
        elif name is not None:
            lines.append(line)
    if name is not None:
        jobs[name] = "\n".join(lines)
    return jobs


def strip_comments(body: str) -> str:
    """Drop full-line YAML comments so prose about a flag is not mistaken for
    the flag being set."""
    return "\n".join(line for line in body.splitlines() if not line.strip().startswith("#"))


class ReleaseWorkflowIsSelfContainedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = read_text(".github/workflows/release.yml")
        self.jobs = workflow_jobs(self.workflow)
        self.windows_jobs = ("windows-msys32", "windows-msvc")

    def test_the_workflow_still_has_the_jobs_these_gates_describe(self) -> None:
        for job in self.windows_jobs + ("publish",):
            self.assertIn(job, self.jobs)

    def test_both_windows_lanes_refuse_host_libraries(self) -> None:
        """Without this a dependency resolves against whatever the runner has
        installed, and the package ships no runtime libraries to match."""
        for job in self.windows_jobs:
            body = strip_comments(self.jobs[job])
            with self.subTest(job=job):
                self.assertIn("--wrap-mode=forcefallback", body)
        # Non-Windows lanes deliberately use their distributions' libraries.
        for job in ("ubuntu-x86", "ubuntu-arm64", "macos-x86", "meson-validation"):
            with self.subTest(job=job):
                self.assertNotIn("--wrap-mode=forcefallback", strip_comments(self.jobs[job]))

    def test_windows_lanes_link_their_runtime_statically(self) -> None:
        # MinGW would otherwise need libgcc_s_seh-1.dll, libstdc++-6.dll and
        # libwinpthread-1.dll, none of which the package stages.
        mingw = strip_comments(self.jobs["windows-msys32"])
        self.assertIn("-Dc_link_args=-static", mingw)
        self.assertIn("-Dcpp_link_args=-static", mingw)
        # MSVC would otherwise need the Visual C++ redistributable. Both the
        # arm64 cross branch and the native branch have to carry it.
        msvc = strip_comments(self.jobs["windows-msvc"])
        self.assertEqual(msvc.count("-Db_vscrt=static_from_buildtype"), 2)
        self.assertEqual(msvc.count("--wrap-mode=forcefallback"), 2)

    def test_every_windows_artifact_is_audited_before_upload(self) -> None:
        for job in self.windows_jobs:
            body = self.jobs[job]
            with self.subTest(job=job):
                self.assertIn("check_windows_dll_deps.py bin", body)
                self.assertLess(
                    body.index("check_windows_dll_deps.py bin"),
                    body.index("actions/upload-artifact"),
                )

    def test_generated_docs_are_rendered_after_the_version_is_stamped(self) -> None:
        """release.py ships .install/README.html, which is generated from the
        stamped version, so a lane that skips this documents the previous build
        number."""
        for job in self.windows_jobs + ("publish",):
            body = self.jobs[job]
            with self.subTest(job=job):
                self.assertIn("scripts/generate_docs.py", body)
                self.assertLess(
                    body.index("manual_release.py stamp-version"),
                    body.index("scripts/generate_docs.py"),
                )
        publish = self.jobs["publish"]
        self.assertLess(
            publish.index("scripts/generate_docs.py"), publish.index("scripts/release.py")
        )


def _minimal_pe(imports: tuple[str, ...]) -> bytes:
    """Build the smallest PE32+ image with a usable import directory."""
    section_rva = 0x1000
    section_raw = 0x200

    # Lay the import descriptors out first so the name RVAs are known.
    descriptor_bytes = 20 * (len(imports) + 1)
    names_offset = descriptor_bytes
    blob = bytearray(descriptor_bytes)
    name_rvas = []
    for name in imports:
        name_rvas.append(section_rva + names_offset + len(blob) - descriptor_bytes)
        blob += name.encode("ascii") + b"\x00"
    for index, name_rva in enumerate(name_rvas):
        struct.pack_into("<I", blob, index * 20 + 12, name_rva)

    image = bytearray(section_raw + max(len(blob), 0x200))
    image[0:2] = b"MZ"
    struct.pack_into("<I", image, 0x3C, 0x80)
    pe = 0x80
    image[pe:pe + 4] = b"PE\x00\x00"
    struct.pack_into("<H", image, pe + 4, 0x8664)     # machine
    struct.pack_into("<H", image, pe + 6, 1)          # section count
    struct.pack_into("<H", image, pe + 20, 240)       # optional header size
    optional = pe + 24
    struct.pack_into("<H", image, optional, 0x20B)    # PE32+
    struct.pack_into("<I", image, optional + 108, 16)  # directory count
    directories = optional + 112
    struct.pack_into("<I", image, directories + 8, section_rva)      # import RVA
    struct.pack_into("<I", image, directories + 12, len(blob))

    section = optional + 240
    image[section:section + 8] = b".idata\x00\x00"
    struct.pack_into("<I", image, section + 8, len(blob))     # virtual size
    struct.pack_into("<I", image, section + 12, section_rva)  # virtual address
    struct.pack_into("<I", image, section + 16, len(blob))    # raw size
    struct.pack_into("<I", image, section + 20, section_raw)  # raw pointer

    image[section_raw:section_raw + len(blob)] = blob
    return bytes(image)


class DependencyAuditTests(unittest.TestCase):
    def test_os_libraries_and_sibling_modules_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "fnquake3.x64.exe").write_bytes(
                _minimal_pe(
                    (
                        "KERNEL32.dll",
                        "OPENGL32.dll",
                        "api-ms-win-crt-runtime-l1-1-0.dll",
                        "ucrtbase.dll",
                        # A renderer module shipped in the same package.
                        "fnquake3_glx_x86_64.dll",
                    )
                )
            )
            (root / "fnquake3_glx_x86_64.dll").write_bytes(_minimal_pe(("KERNEL32.dll",)))

            self.assertEqual(audit.check_root(root, []), [])

    def test_an_unshipped_import_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "fnquake3.x64.exe").write_bytes(
                _minimal_pe(("KERNEL32.dll", "libzstd.dll"))
            )

            problems = audit.check_root(root, [])
            self.assertEqual(len(problems), 1)
            self.assertIn("libzstd.dll", problems[0])
            self.assertNotIn("KERNEL32", problems[0])

            # ...and an explicit allowance silences it, so the gate can be
            # relaxed deliberately rather than by deleting the step.
            self.assertEqual(audit.check_root(root, ["libzstd.dll"]), [])

    def test_an_empty_stage_directory_is_a_failure_not_a_pass(self) -> None:
        """A packaging change that stops producing binaries must not read as a
        clean dependency audit."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            problems = audit.check_root(root, [])
            self.assertEqual(len(problems), 1)
            self.assertIn("no .exe or .dll files", problems[0])

    def test_a_non_pe_file_is_reported_rather_than_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "broken.dll").write_bytes(b"not a pe image at all")

            problems = audit.check_root(root, [])
            self.assertEqual(len(problems), 1)
            self.assertIn("not a PE image", problems[0])

    def test_system_dll_matching_ignores_case_and_covers_api_sets(self) -> None:
        self.assertTrue(audit.is_system_dll("KERNEL32.dll"))
        self.assertTrue(audit.is_system_dll("kernel32.DLL"))
        self.assertTrue(audit.is_system_dll("api-ms-win-core-synch-l1-2-0.dll"))
        self.assertTrue(audit.is_system_dll("ucrtbase.dll"))
        # The MinGW lanes target the legacy CRT rather than the UCRT the MSVC
        # lane uses; both are part of Windows.
        self.assertTrue(audit.is_system_dll("msvcrt.dll"))
        self.assertFalse(audit.is_system_dll("libzstd.dll"))
        self.assertFalse(audit.is_system_dll("zlib1.dll"))
        self.assertFalse(audit.is_system_dll("VCRUNTIME140.dll"))
        self.assertFalse(audit.is_system_dll("libstdc++-6.dll"))


if __name__ == "__main__":
    unittest.main()

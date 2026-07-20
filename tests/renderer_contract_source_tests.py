from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RENDERERS = ("glx", "vk", "rtx")


class RendererContractSourceTests(unittest.TestCase):
    def test_meson_exposes_exactly_three_renderers(self) -> None:
        options = (ROOT / "meson_options.txt").read_text(encoding="utf-8")
        match = re.search(
            r"option\('renderers'.*?choices:\s*\[(?P<choices>[^]]+)\]",
            options,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(tuple(re.findall(r"'([^']+)'", match.group("choices"))), RENDERERS)
        self.assertIsNotNone(
            re.search(r"option\('renderer-default'.*?value:\s*'glx'", options, re.DOTALL)
        )

    def test_cmake_exposes_exactly_three_renderers(self) -> None:
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn("set(FNQ3_CMAKE_RENDERERS glx vk rtx)", cmake)
        for renderer in RENDERERS:
            self.assertIn(f"${{RENDERER_PREFIX}}_{renderer}${{RENDEXT}}", cmake)

    def test_make_exposes_exactly_three_renderers(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertRegex(makefile, r"(?m)^RENDERER_DEFAULT\s*=\s*glx$")
        self.assertRegex(makefile, r"(?m)^USE_GLX\s*=\s*1$")
        self.assertRegex(makefile, r"(?m)^USE_VK\s*=\s*1$")
        self.assertRegex(makefile, r"(?m)^USE_RTX\s*=\s*1$")
        for renderer in RENDERERS:
            self.assertIn(f"ifeq ($(RENDERER_DEFAULT),{renderer})", makefile)

    def test_client_accepts_only_exact_renderer_selectors(self) -> None:
        client = (ROOT / "code" / "client" / "cl_main.cpp").read_text(encoding="utf-8")
        allowlist = re.search(
            r"static bool isValidRenderer\( const char \*s \) \{(?P<body>.*?)\n\}",
            client,
            re.DOTALL,
        )
        self.assertIsNotNone(allowlist)
        assert allowlist is not None
        self.assertEqual(
            tuple(re.findall(r'strcmp\( s, "([^"]+)" \) == 0', allowlist.group("body"))),
            RENDERERS,
        )
        self.assertIn('Cvar_Get( "cl_renderer", "glx", CVAR_ARCHIVE | CVAR_LATCH )', client)

    def test_vscode_entry_points_use_exact_renderer_selectors(self) -> None:
        build_script = (ROOT / ".vscode" / "build-release.ps1").read_text(
            encoding="utf-8"
        )
        launch_script = (ROOT / ".vscode" / "launch-release.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("ValidateSet('all', 'glx', 'vk', 'rtx')", build_script)
        self.assertIn("else { 'glx,vk,rtx' }", build_script)
        self.assertIn("ValidateSet('glx', 'vk', 'rtx')", launch_script)

        tasks = json.loads((ROOT / ".vscode" / "tasks.json").read_text(encoding="utf-8"))
        build_task = next(task for task in tasks["tasks"] if task["label"] == "meson: build")
        renderer_option = build_task["args"].index("-Renderers")
        self.assertEqual(build_task["args"][renderer_option + 1], ",".join(RENDERERS))

        launch = json.loads((ROOT / ".vscode" / "launch.json").read_text(encoding="utf-8"))
        selectors = tuple(
            configuration["args"][-1]
            for configuration in launch["configurations"]
            if configuration.get("args", [])[:2] == ["+set", "cl_renderer"]
        )
        self.assertEqual(selectors, RENDERERS)

    def test_removed_renderer2_tree_is_absent(self) -> None:
        self.assertFalse((ROOT / "code" / "renderer2").exists())

    def test_x11_display_output_query_is_shared_by_static_renderers(self) -> None:
        linux_glimp = (ROOT / "code" / "unix" / "linux_glimp.cpp").read_text(
            encoding="utf-8"
        )
        shared_start = linux_glimp.index("static void InitCvars")
        query = linux_glimp.index("void GLimp_QueryDisplayOutput")
        opengl_guard = linux_glimp.index("#ifdef USE_OPENGL_API", shared_start)
        self.assertLess(shared_start, query)
        self.assertLess(query, opengl_guard)

    def test_win32_display_output_query_is_shared_by_static_vulkan_family_renderers(
        self,
    ) -> None:
        win_glimp = (ROOT / "code" / "win32" / "win_glimp.cpp").read_text(
            encoding="utf-8"
        )
        query = win_glimp.index("void GLimp_QueryDisplayOutput")
        opengl_loader_guard = win_glimp.index(
            "#ifdef USE_OPENGL_API\n/*\n** GLW_LoadOpenGL"
        )
        self.assertLess(query, opengl_loader_guard)

        meson = (ROOT / "meson.build").read_text(encoding="utf-8")
        self.assertIn(
            "use_vulkan_api = renderer_default in ['vk', 'rtx']",
            meson,
        )
        static_start = meson.index("static_renderer_objects = []")
        static_end = meson.index("client_c_args = common_c_args", static_start)
        static_renderers = meson[static_start:static_end]
        self.assertIn("static_library('renderer_static_vk'", static_renderers)
        self.assertIn("static_library('renderer_static_rtx'", static_renderers)

    def test_rtx_sources_follow_project_gplv2_license(self) -> None:
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("GNU GENERAL PUBLIC LICENSE", license_text)
        self.assertIn("Version 2, June 1991", license_text)
        rtx_license = (ROOT / "code" / "rendererrtx" / "LICENSE.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("GNU General Public License, version 2", rtx_license)
        self.assertIn("RTX-specific changes and shader sources", rtx_license)
        notices = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in (ROOT / "code" / "rendererrtx").rglob("*")
            if path.is_file()
        )
        self.assertNotRegex(notices, r"GPL(?:-|\s).*?3|Version 3")


if __name__ == "__main__":
    unittest.main()

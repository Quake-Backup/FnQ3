from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CMAKE = ROOT / "CMakeLists.txt"


class CMakeConfigSourceTests(unittest.TestCase):
    def test_glx_logic_test_links_executor_source_like_meson(self) -> None:
        cmake = CMAKE.read_text(encoding="utf-8")
        target = re.search(
            r"ADD_EXECUTABLE\(fnq3_glx_logic_tests(?P<body>.*?)\)",
            cmake,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(target)
        assert target is not None
        self.assertIn("tests/glx/glx_logic_tests.cpp", target.group("body"))
        self.assertIn("code/rendererglx/glx_executor.cpp", target.group("body"))

    def test_msvc_libjpeg_import_uses_per_config_locations(self) -> None:
        cmake = CMAKE.read_text(encoding="utf-8")

        self.assertIn("IMPORTED_LOCATION_DEBUG", cmake)
        self.assertIn("Debug/jpeg-static.lib", cmake)
        self.assertIn("IMPORTED_LOCATION_RELEASE", cmake)
        self.assertIn("Release/jpeg-static.lib", cmake)
        self.assertIn("FNQ3_LIBJPEG_TURBO_BUILD_COMMAND", cmake)
        self.assertIn(
            "if(FNQ3_LIBJPEG_TURBO_MSVC_ABI AND CMAKE_CONFIGURATION_TYPES)",
            cmake,
        )
        self.assertIn(
            'set(FNQ3_LIBJPEG_TURBO_BYPRODUCTS "${FNQ3_LIBJPEG_TURBO_LIBRARY}")',
            cmake,
        )

    def test_vulkan_module_respects_use_vulkan(self) -> None:
        cmake = CMAKE.read_text(encoding="utf-8")
        dynamic_renderers = re.search(
            r"IF\(USE_RENDERER_DLOPEN\)(?P<body>.*?)ELSE\(\)",
            cmake,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(dynamic_renderers)
        assert dynamic_renderers is not None
        self.assertRegex(
            dynamic_renderers.group("body"),
            r"(?s)IF\(USE_VULKAN\).*?ADD_LIBRARY\(\$\{RENDERER_PREFIX\}_vulkan",
        )

    def test_static_renderer_selection_uses_renderer_default(self) -> None:
        cmake = CMAKE.read_text(encoding="utf-8")

        self.assertGreaterEqual(
            cmake.count('ELSEIF(RENDERER_DEFAULT STREQUAL "vulkan")'),
            2,
        )
        self.assertNotIn("ELSEIF(USE_VULKAN)", cmake)

    def test_cmake_rejects_renderer_choices_it_cannot_build(self) -> None:
        cmake = CMAKE.read_text(encoding="utf-8")

        self.assertIn("set(FNQ3_CMAKE_RENDERERS opengl glx vulkan)", cmake)
        self.assertIn("Unsupported CMake RENDERER_DEFAULT", cmake)
        self.assertIn("use Meson for opengl2", cmake)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorldDlightSourceTests(unittest.TestCase):
    def test_shared_versioned_format_contract(self) -> None:
        header = (ROOT / "code/renderercommon/tr_world_dlights.h").read_text(
            encoding="utf-8"
        )
        self.assertIn('#define WORLD_DLIGHT_FORMAT_NAME "fnquake3-world-dlights"', header)
        self.assertIn("#define WORLD_DLIGHT_FORMAT_VERSION 1", header)
        self.assertIn('#define WORLD_DLIGHT_FILE_EXTENSION ".dlight"', header)
        self.assertIn(
            '#define WORLD_DLIGHT_LEGACY_FILE_EXTENSION ".lights.json"', header
        )
        self.assertIn("#define WORLD_DLIGHT_MAX_FILE_SIZE ( 512 * 1024 )", header)
        self.assertIn("#define WORLD_DLIGHT_MAX_LIGHTS 256", header)
        self.assertIn("#define WORLD_DLIGHT_DEFAULT_RADIUS 300.0f", header)
        self.assertIn("#define WORLD_DLIGHT_DEFAULT_INTENSITY 300.0f", header)
        self.assertIn("#define WORLD_DLIGHT_DEFAULT_INNER_ANGLE 35.0f", header)
        self.assertIn("#define WORLD_DLIGHT_DEFAULT_OUTER_ANGLE 50.0f", header)
        self.assertIn("#define WORLD_DLIGHT_DEFAULT_SHADOW_RESOLUTION 256", header)

    def test_all_renderers_load_and_generate_world_dlights(self) -> None:
        renderers = (
            ("OpenGL", "code/renderer", True),
            ("Vulkan", "code/renderervk", True),
            ("RTX", "code/rendererrtx", False),
        )
        for label, directory, raster_shadows in renderers:
            with self.subTest(renderer=label):
                local = (ROOT / directory / "tr_local.h").read_text(encoding="utf-8")
                bsp = (ROOT / directory / "tr_bsp.c").read_text(encoding="utf-8")
                scene = (ROOT / directory / "tr_scene.c").read_text(encoding="utf-8")
                init = (ROOT / directory / "tr_init.c").read_text(encoding="utf-8")

                self.assertIn('../renderercommon/tr_world_dlights.h', local)
                self.assertIn(
                    "#define MAX_STATIC_MAP_LIGHTS WORLD_DLIGHT_MAX_LIGHTS", local
                )
                self.assertIn("extern cvar_t\t*r_dlightLoadWorld;", local)

                self.assertIn(
                    'ri.Cvar_Get( "r_dlightLoadWorld", "1", CVAR_ARCHIVE_ND )', init
                )
                self.assertIn('ri.Cmd_AddCommand( "r_dlightReloadWorld"', init)
                self.assertIn('ri.Cmd_AddCommand( "r_dlightGenerateWorld"', init)
                self.assertIn('ri.Cmd_RemoveCommand( "r_dlightReloadWorld"', init)
                self.assertIn('ri.Cmd_RemoveCommand( "r_dlightGenerateWorld"', init)
                if raster_shadows:
                    self.assertIn(
                        'ri.Cvar_Get( "r_spotShadows", "1", CVAR_ARCHIVE_ND | CVAR_LATCH )',
                        init,
                    )

                self.assertRegex(
                    scene,
                    re.compile(
                        r"r_dlightLoadWorld[^\n]*\n(?:.*\n){0,3}.*r_dlightMode->integer\s*!=\s*2",
                        re.MULTILINE,
                    ),
                )

                self.assertIn("WORLD_DLIGHT_FILE_EXTENSION", bsp)
                self.assertIn("WORLD_DLIGHT_LEGACY_FILE_EXTENSION", bsp)
                self.assertLess(
                    bsp.find("WORLD_DLIGHT_FILE_EXTENSION"),
                    bsp.find("WORLD_DLIGHT_LEGACY_FILE_EXTENSION"),
                )
                self.assertIn("WORLD_DLIGHT_MAX_FILE_SIZE", bsp)
                self.assertIn("WORLD_DLIGHT_FORMAT_NAME", bsp)
                self.assertIn("WORLD_DLIGHT_FORMAT_VERSION", bsp)
                self.assertIn('!Q_stricmp( key, "format" )', bsp)
                self.assertIn('!Q_stricmp( key, "shadowResolution" )', bsp)
                self.assertIn("WORLD_DLIGHT_DEFAULT_RADIUS", bsp)
                self.assertIn("WORLD_DLIGHT_DEFAULT_INTENSITY", bsp)
                self.assertIn("WORLD_DLIGHT_DEFAULT_INNER_ANGLE", bsp)
                self.assertIn("WORLD_DLIGHT_DEFAULT_OUTER_ANGLE", bsp)
                self.assertIn("WORLD_DLIGHT_DEFAULT_SHADOW_RESOLUTION", bsp)

                self.assertIn("tr.surfaceLightProxies.count", bsp)
                self.assertIn('\\"type\\": \\"spot\\"', bsp)
                self.assertIn("proxy->origin", bsp)
                self.assertIn("proxy->normal", bsp)
                self.assertIn("proxy->color", bsp)
                self.assertIn('\\"surfacelight_%03i_surface_%i\\"', bsp)
                self.assertIn("VectorNormalize2( proxy->normal, direction )", bsp)
                self.assertIn("ri.FS_ReadFile( filename, NULL ) >= 0", bsp)
                self.assertIn("ri.FS_FileExists", bsp)
                self.assertIn('Q_stricmp( ri.Cmd_Argv( 1 ), "force" )', bsp)
                self.assertIn("ri.FS_WriteFile", bsp)
                self.assertIn("R_LoadStaticMapLightsForWorld();", bsp)

    def test_raster_spot_shadow_collection_obeys_world_gate(self) -> None:
        for directory in ("code/renderer", "code/renderervk"):
            main = (ROOT / directory / "tr_main.c").read_text(encoding="utf-8")
            start = main.index("static void R_ShadowManagerCollectStaticSpotCandidates")
            end = main.index(
                "static void R_ShadowManagerCollectSurfaceSpotCandidates", start
            )
            section = main[start:end]
            self.assertIn("r_dlightLoadWorld", section)
            self.assertIn("r_dlightMode->integer != 2", section)

    def test_root_archive_allows_world_dlight_sidecars(self) -> None:
        files = (ROOT / "code/qcommon/files.c").read_text(encoding="utf-8")
        self.assertIn('COM_CompareExtension( qpath, ".dlight" )', files)

    def test_format_and_generator_are_documented(self) -> None:
        docs = (ROOT / "docs/fnquake3/WORLD_DLIGHTS.md").read_text(encoding="utf-8")
        self.assertIn("maps/example.dlight", docs)
        self.assertIn('"format": "fnquake3-world-dlights"', docs)
        self.assertIn("r_dlightMode 2", docs)
        self.assertIn("r_dlightLoadWorld 1", docs)
        self.assertIn("r_dlightGenerateWorld force", docs)
        self.assertIn("area-weights triangle centroids", docs)


if __name__ == "__main__":
    unittest.main()

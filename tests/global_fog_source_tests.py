from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASEQ3_MAPS = {
    "pro-q3dm13", "pro-q3dm6", "pro-q3tourney2", "pro-q3tourney4",
    "q3ctf1", "q3ctf2", "q3ctf3", "q3ctf4", "q3ctf5",
    *(f"q3dm{number}" for number in range(20)),
    "q3tourney1", "q3tourney2", "q3tourney3", "q3tourney4", "q3tourney6",
}
MISSIONPACK_MAPS = {
    "mpq3ctf1", "mpq3ctf2", "mpq3ctf3", "mpq3ctf4", "mpq3tourney6",
    *(f"mpteam{number}" for number in range(1, 9)),
    *(f"mpterra{number}" for number in range(1, 4)),
    *(f"mptourney{number}" for number in range(1, 5)),
}


def parse_sidecar(path: Path) -> dict[str, list[str]]:
    directives: dict[str, list[str]] = {}
    for line in path.read_text(encoding="ascii").splitlines():
        line = line.split("//", maxsplit=1)[0].strip()
        if not line:
            continue
        tokens = line.split()
        if tokens[0] in directives:
            raise AssertionError(f"{path}: duplicate {tokens[0]} directive")
        directives[tokens[0]] = tokens[1:]
    return directives


class GlobalFogSourceTests(unittest.TestCase):
    def test_stock_sidecars_are_complete_and_subtle(self) -> None:
        self.assertEqual(
            {path.stem for path in (ROOT / "pkg/baseq3/maps").glob("*.fog")}, BASEQ3_MAPS
        )
        self.assertEqual(
            {path.stem for path in (ROOT / "pkg/missionpack/maps").glob("*.fog")}, MISSIONPACK_MAPS
        )
        self.assertFalse((ROOT / "pkg/baseq3/maps/q3tourney5.fog").exists())

        for folder, maps in (("baseq3", BASEQ3_MAPS), ("missionpack", MISSIONPACK_MAPS)):
            for map_name in maps:
                path = ROOT / "pkg" / folder / "maps" / f"{map_name}.fog"
                directives = parse_sidecar(path)
                self.assertEqual(
                    set(directives), {"color", "mode", "density", "start", "opacity", "sky"},
                    path.as_posix(),
                )
                self.assertIn(directives["mode"], (["exp"], ["exp2"]), path.as_posix())
                self.assertEqual(len(directives["color"]), 3, path.as_posix())
                color = [float(value) for value in directives["color"]]
                self.assertTrue(all(0.0 <= value <= 1.0 for value in color), path.as_posix())
                self.assertLessEqual(max(color) - min(color), 0.08, path.as_posix())
                self.assertGreater(float(directives["density"][0]), 0.0, path.as_posix())
                if path.name == "q3dm12.fog":
                    self.assertLessEqual(float(directives["density"][0]), 0.00150, path.as_posix())
                else:
                    self.assertLessEqual(float(directives["density"][0]), 0.00105, path.as_posix())
                self.assertGreaterEqual(float(directives["start"][0]), 0.0, path.as_posix())
                self.assertGreater(float(directives["opacity"][0]), 0.0, path.as_posix())
                if path.name == "q3dm12.fog":
                    self.assertLessEqual(float(directives["opacity"][0]), 0.40, path.as_posix())
                else:
                    self.assertLessEqual(float(directives["opacity"][0]), 0.35, path.as_posix())
                self.assertEqual(directives["sky"], ["1"], path.as_posix())

    def test_parser_contract_is_shared_and_bounded(self) -> None:
        header = (ROOT / "code/renderercommon/tr_global_fog.h").read_text(encoding="utf-8")
        for keyword in ("color", "mode", "density", "start", "end", "opacity", "sky"):
            self.assertIn(f'"{keyword}"', header)
        self.assertIn("GLOBAL_FOG_SIDECAR_MAX_BYTES 16384", header)
        self.assertIn("GLOBAL_FOG_EXP", header)
        self.assertIn("GLOBAL_FOG_EXP2", header)
        self.assertIn("GLOBAL_FOG_LINEAR", header)

        # The tokenizer takes an explicit end pointer and a byte count instead
        # of relying on a NUL terminator, so an embedded NUL or a truncated
        # read cannot widen parsing past what FS_ReadFile returned.
        self.assertIn("GLOBAL_FOG_TOKEN_MAX_BYTES 64", header)
        self.assertIn("R_GlobalFogNextToken( const char **cursor, const char *end,", header)
        self.assertIn("textLength > GLOBAL_FOG_SIDECAR_MAX_BYTES", header)
        self.assertIn("R_GlobalFogSetError", header)
        self.assertIn("malformed or overlong token", header)

        # 0.1 has no exact binary form and x87 evaluates float expressions at
        # excess precision, so the documented maximum density needs a cast to
        # land on the same float the parser stores for an authored "0.1".
        self.assertIn("#define GLOBAL_FOG_DENSITY_MAX ( (float)0.1f )", header)
        self.assertIn("fog->density > GLOBAL_FOG_DENSITY_MAX", header)
        self.assertNotIn("fog->density > 0.1f", header)

    def test_all_raster_capable_backends_load_the_current_map_sidecar(self) -> None:
        for renderer in ("renderer", "renderervk", "rendererrtx"):
            bsp = (ROOT / "code" / renderer / "tr_bsp.c").read_text(encoding="utf-8")
            self.assertIn('"maps/%s.fog"', bsp)
            self.assertIn("R_GlobalFogParse", bsp)
            self.assertIn("R_LoadGlobalFogForWorld();", bsp)

    def test_sidecar_loading_is_gated_and_sized_before_it_is_read(self) -> None:
        """An oversized sidecar must be rejected on its declared size, not
        allocated first and measured afterwards, and a disabled r_globalFog
        must not read the file at all."""
        for renderer in ("renderer", "renderervk", "rendererrtx"):
            bsp = (ROOT / "code" / renderer / "tr_bsp.c").read_text(encoding="utf-8")
            start = bsp.index("static void R_LoadGlobalFogForWorld( void )")
            loader = bsp[start:bsp.index("\nstatic ", start + 1)]
            with self.subTest(renderer=renderer):
                self.assertLess(
                    loader.index("R_GlobalFogClear"), loader.index("r_globalFog->integer")
                )
                self.assertLess(
                    loader.index("r_globalFog->integer"), loader.index("ri.FS_ReadFile")
                )
                preflight = loader.index("ri.FS_ReadFile( filename, NULL )")
                buffered = loader.index("ri.FS_ReadFile( filename, &buffer.v )")
                first_limit = loader.index("size > GLOBAL_FOG_SIDECAR_MAX_BYTES")
                second_limit = loader.index(
                    "size > GLOBAL_FOG_SIDECAR_MAX_BYTES", first_limit + 1
                )
                self.assertLess(preflight, first_limit)
                self.assertLess(first_limit, buffered)
                self.assertLess(buffered, second_limit)
                # The parser is handed the byte count it was read with.
                self.assertIn(
                    "R_GlobalFogParse( &s_worldData.globalFog, buffer.c, size,", loader
                )

    def test_authored_color_is_converted_into_the_scene_buffer_domain(self) -> None:
        """The compositor blends into the scene color buffer, which the output
        transform still scales by overbright (and by the tone-map exposure in
        scene-linear mode). Without the conversion an authored mid-grey reaches
        the display at twice its brightness and the layer reads as a uniform
        wash instead of distance fog."""
        header = (ROOT / "code/renderercommon/tr_global_fog.h").read_text(encoding="utf-8")
        self.assertIn("R_GlobalFogSceneColor", header)
        self.assertIn("R_GlobalFogSrgbToLinear", header)

        uses = {
            "code/renderer/tr_arb.c": "sceneColor[0], sceneColor[1], sceneColor[2], opacity",
            "code/renderervk/vk.c": "constants[0] = sceneColor[0];",
            "code/rendererrtx/vk.c": "constants[0] = sceneColor[0];",
        }
        for path, consumed in uses.items():
            source = (ROOT / path).read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn(
                    "R_GlobalFogSceneColor( fog, outputScale, sceneLinear, sceneColor );",
                    source,
                )
                self.assertIn(consumed, source)
                # The authored value must not reach the shader unconverted.
                self.assertNotIn("constants[0] = fog->color[0];", source)
                self.assertNotIn("fog->color[0], fog->color[1], fog->color[2], opacity", source)

    def test_compositors_use_resolved_scene_depth(self) -> None:
        arb = (ROOT / "code/renderer/tr_arb.c").read_text(encoding="utf-8")
        self.assertIn("GLOBAL_FOG_FRAGMENT", arb)
        self.assertIn("FBO_DrawGlobalFog", arb)
        self.assertIn("depthFadeTexture", arb)
        self.assertIn("FBO_BlitMS( qfalse )", arb)
        self.assertIn("destination->fbo", arb)
        self.assertIn("Existing bloom and motion-blur paths", arb)

        global_fog = (ROOT / "code/renderervk/shaders/global_fog.frag").read_text(
            encoding="utf-8"
        )
        vk = (ROOT / "code/renderervk/vk.c").read_text(encoding="utf-8")
        self.assertIn("depth_texture", global_fog)
        self.assertIn("scene_distance", global_fog)
        self.assertIn("global_fog_pipeline", vk)
        self.assertIn("vk_draw_global_fog", vk)
        self.assertIn("vk_depth_fade_requested", vk)
        self.assertIn("r_globalFog", vk)

        rtx_global_fog = (
            ROOT / "code/rendererrtx/shaders/global_fog.frag"
        ).read_text(encoding="utf-8")
        rtx_vk = (ROOT / "code/rendererrtx/vk.c").read_text(encoding="utf-8")
        rtx_backend = (ROOT / "code/rendererrtx/tr_backend.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("depth_texture", rtx_global_fog)
        self.assertIn("scene_distance", rtx_global_fog)
        self.assertIn("global_fog_pipeline", rtx_vk)
        self.assertIn("vk_draw_global_fog", rtx_vk)
        self.assertIn("vk_global_fog_enabled", rtx_vk)
        self.assertIn("depth_sample_descriptor", rtx_vk)
        self.assertIn("vk.cmd->descriptor_set.start = 0", rtx_vk)
        self.assertIn("vk_draw_global_fog();", rtx_backend)

    def test_package_root_permits_only_the_new_map_sidecar_extension(self) -> None:
        files = (ROOT / "code/qcommon/files.c").read_text(encoding="utf-8")
        self.assertIn('COM_CompareExtension( qpath, ".fog" )', files)
        meson = (ROOT / "meson.build").read_text(encoding="utf-8")
        self.assertIn("standard_global_fog_baseq3_maps", meson)
        self.assertIn("standard_global_fog_missionpack_maps", meson)


if __name__ == "__main__":
    unittest.main()

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

    def test_both_raster_backends_load_the_current_map_sidecar(self) -> None:
        for renderer in ("renderer", "renderervk"):
            bsp = (ROOT / "code" / renderer / "tr_bsp.c").read_text(encoding="utf-8")
            self.assertIn('"maps/%s.fog"', bsp)
            self.assertIn("R_GlobalFogParse", bsp)
            self.assertIn("R_LoadGlobalFogForWorld();", bsp)

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

    def test_package_root_permits_only_the_new_map_sidecar_extension(self) -> None:
        files = (ROOT / "code/qcommon/files.c").read_text(encoding="utf-8")
        self.assertIn('COM_CompareExtension( qpath, ".fog" )', files)
        meson = (ROOT / "meson.build").read_text(encoding="utf-8")
        self.assertIn("standard_global_fog_baseq3_maps", meson)
        self.assertIn("standard_global_fog_missionpack_maps", meson)


if __name__ == "__main__":
    unittest.main()

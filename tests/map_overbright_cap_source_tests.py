from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RENDERERS = ("renderer", "renderervk", "rendererrtx")


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class MapOverBrightCapSourceTests(unittest.TestCase):
    def test_cap_cvar_contract_is_shared_by_all_renderers(self) -> None:
        for renderer in RENDERERS:
            with self.subTest(renderer=renderer):
                init = read_text(f"code/{renderer}/tr_init.c")
                header = read_text(f"code/{renderer}/tr_local.h")

                self.assertIn("cvar_t\t*r_mapOverBrightCap;", init)
                self.assertIn("extern\tcvar_t\t*r_mapOverBrightCap;", header)
                self.assertIn(
                    'ri.Cvar_Get( "r_mapOverBrightCap", "255", CVAR_ARCHIVE_ND | CVAR_LATCH )',
                    init,
                )
                self.assertIn(
                    'ri.Cvar_CheckRange( r_mapOverBrightCap, "0", "255", CV_INTEGER )',
                    init,
                )

    def test_cap_is_applied_during_rgb_preserving_normalization(self) -> None:
        for renderer in RENDERERS:
            with self.subTest(renderer=renderer):
                bsp = read_text(f"code/{renderer}/tr_bsp.c")
                color_shift_start = bsp.index("void R_ColorShiftLightingBytes(")
                color_shift_end = bsp.index("\n\n#define LIGHTMAP_SIZE", color_shift_start)
                color_shift = bsp[color_shift_start:color_shift_end]

                self.assertIn("int\t\tshift, r, g, b, cap;", color_shift)
                self.assertIn(
                    "cap = r_mapOverBrightCap ? r_mapOverBrightCap->integer : 255;",
                    color_shift,
                )
                self.assertIn("r = r * cap / max;", color_shift)
                self.assertIn("g = g * cap / max;", color_shift)
                self.assertIn("b = b * cap / max;", color_shift)
                self.assertNotIn("r = r * 255 / max;", color_shift)


if __name__ == "__main__":
    unittest.main()

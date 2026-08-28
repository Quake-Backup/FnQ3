from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RENDERERS = ("renderer", "renderervk", "rendererrtx")


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class ModelTessellationSourceTests(unittest.TestCase):
    def test_runtime_smoothing_cvar_is_consistent_and_defaults_to_medium(self) -> None:
        registration = (
            'r_modelTessellation = ri.Cvar_Get( '
            '"r_modelTessellation", "1", CVAR_ARCHIVE_ND );'
        )
        range_check = (
            'ri.Cvar_CheckRange( r_modelTessellation, "0", "2", CV_INTEGER );'
        )

        for renderer in RENDERERS:
            source = read(f"code/{renderer}/tr_init.c")
            with self.subTest(renderer=renderer):
                self.assertIn(registration, source)
                self.assertIn(range_check, source)
                self.assertIn(
                    "ri.Cvar_SetGroup( r_modelTessellation, CVG_RENDERER );",
                    source,
                )
                self.assertIn("0: Low (original triangles)", source)
                self.assertIn("1: Medium (4 smoothed triangles", source)
                self.assertIn("2: High (9 smoothed triangles", source)

    def test_authored_lod_control_remains_independent(self) -> None:
        legacy_registration = (
            'r_lodbias = ri.Cvar_Get( "r_lodbias", "-2", CVAR_ARCHIVE_ND );'
        )
        for renderer in RENDERERS:
            source = read(f"code/{renderer}/tr_init.c")
            with self.subTest(renderer=renderer):
                self.assertIn(legacy_registration, source)
                self.assertNotIn("Cvar_CheckRange( r_lodbias", source)

    def test_all_animated_model_formats_feed_runtime_tessellation(self) -> None:
        for renderer in RENDERERS:
            md3 = read(f"code/{renderer}/tr_surface.c")
            mdr = read(f"code/{renderer}/tr_animation.c")
            iqm = read(f"code/{renderer}/tr_model_iqm.c")
            with self.subTest(renderer=renderer):
                self.assertIn("RB_TessellateModelSurface( Doug", md3)
                self.assertIn("RB_TessellateModelSurface( baseVertex", mdr)
                self.assertIn("RB_TessellateModelSurface( base", iqm)
                self.assertIn(
                    "r_modelTessellation && r_modelTessellation->integer > MODEL_TESSELLATION_LOW",
                    mdr,
                )


if __name__ == "__main__":
    unittest.main()

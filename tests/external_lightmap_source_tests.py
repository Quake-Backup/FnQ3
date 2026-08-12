"""Gates for external lightmap atlases (maps/<mapname>/lm_XXXX).

BSP-internal lightmaps go through R_LoadLightmaps(), which applies the
overbright/greyscale shift and keeps the atlas at its authored size. External
atlases arrive through the regular shader/image path instead, so nothing gives
them that treatment unless R_CreateImage() forces it. Getting that wrong is not
a crash, it is a map that lights differently from an otherwise identical one
with its lightmaps inside the BSP -- which is exactly the sort of thing that
goes unnoticed, so it gets a gate.
"""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RENDERERS = ("renderer", "renderervk", "rendererrtx")


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def external_lightmap_block(source: str) -> str:
    start = source.index('Q_stristr( image->imgName + 6, "/lm_" ) != NULL )')
    return source[start:source.index("\n\t}", start)]


class ExternalLightmapSourceTests(unittest.TestCase):
    def test_atlases_are_put_on_the_bsp_lightmap_contract(self) -> None:
        for renderer in RENDERERS:
            with self.subTest(renderer=renderer):
                block = external_lightmap_block(read_text(f"code/{renderer}/tr_image.c"))

                # The shift R_ProcessLightmap() bakes into internal lightmaps.
                # Without it an external atlas ignores r_mapOverBrightBits,
                # r_mapOverBrightCap, and r_mapGreyScale.
                self.assertIn("IMGFLAG_COLORSHIFT", block)
                # Intensity and gamma are already in the diffuse texture's
                # scaling; applying them again double-brightens the surface.
                self.assertIn("IMGFLAG_NOLIGHTSCALE", block)
                # A packed atlas has no border padding, so a mip or a picmip
                # reduction blurs and bleeds neighbouring lightmap tiles.
                self.assertIn("image->flags &= ~( IMGFLAG_MIPMAP | IMGFLAG_PICMIP );", block)
                self.assertIn("IMGFLAG_NOSCALE", block)
                self.assertIn("IMGFLAG_NO_COMPRESSION", block)
                self.assertIn("IMGFLAG_COLORSPACE_LINEAR", block)
                self.assertIn("image->colorSpace = IMAGE_COLORSPACE_LINEAR;", block)

    def test_the_three_renderers_agree(self) -> None:
        """A per-renderer divergence here shows up as the same map lighting
        differently under cl_renderer glx, vk, and rtx."""
        blocks = {
            renderer: external_lightmap_block(read_text(f"code/{renderer}/tr_image.c"))
            for renderer in RENDERERS
        }
        flags = {
            renderer: sorted(
                token
                for token in block.replace("(", " ").replace(")", " ").split()
                if token.startswith("IMGFLAG_")
            )
            for renderer, block in blocks.items()
        }
        reference = flags[RENDERERS[0]]
        for renderer in RENDERERS[1:]:
            self.assertEqual(flags[renderer], reference, renderer)


if __name__ == "__main__":
    unittest.main()

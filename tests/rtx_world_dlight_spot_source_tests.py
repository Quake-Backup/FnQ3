from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class RtxWorldDlightSpotSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.local = read_text("code/rendererrtx/tr_local.h")
        cls.scene = read_text("code/rendererrtx/tr_scene.c")
        cls.shade = read_text("code/rendererrtx/tr_shade.c")
        cls.vk = read_text("code/rendererrtx/vk.c")
        cls.raster_frag = read_text("code/rendererrtx/shaders/light_frag.tmpl")
        cls.rt_hit = read_text("code/rendererrtx/shaders/rt_main.rchit")

    def test_world_spot_tag_does_not_reclassify_legacy_lights(self) -> None:
        self.assertIn("int\t\tworldSpotIndex;", self.local)
        self.assertGreaterEqual(self.scene.count("dl->worldSpotIndex = -1;"), 2)
        self.assertIn("dl->worldSpotIndex = bestIndex;", self.scene)

    def test_raster_light_uses_authored_cone_and_keeps_capsule_fallback(self) -> None:
        self.assertIn("R_WorldSpotForDlight", self.shade)
        self.assertIn("cosf( innerAngle", self.shade)
        self.assertIn("cosf( outerAngle", self.shade)
        self.assertIn("bool worldSpot = dlightFactors.y > 0.5;", self.raster_frag)
        self.assertIn("coneFactor = smoothstep(outerCos, innerCos, cosTheta);", self.raster_frag)
        self.assertIn("LL = L;", self.raster_frag)
        self.assertIn("project fragment on the legacy linear light vector", self.raster_frag)

    def test_rt_light_has_distinct_spot_type_and_visible_attenuation(self) -> None:
        self.assertIn("#define RTX_RT_LIGHT_TYPE_SPOT 3.0f", self.vk)
        self.assertIn("dst->metadata[1] = innerCos.u;", self.vk)
        self.assertIn("dst->metadata[2] = outerCos.u;", self.vk)
        self.assertIn("bool linearLight = light.colorType.w >= 1.5", self.rt_hit)
        self.assertIn("bool spotLight = light.colorType.w >= 2.5", self.rt_hit)
        self.assertIn("uintBitsToFloat(light.metadata.y)", self.rt_hit)
        self.assertIn("uintBitsToFloat(light.metadata.z)", self.rt_hit)
        self.assertIn("radianceScale *= coneFactor;", self.rt_hit)


if __name__ == "__main__":
    unittest.main()

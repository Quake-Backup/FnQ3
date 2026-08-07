from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class VulkanWorldDlightSpotConeSourceTests(unittest.TestCase):
    def test_only_static_world_spots_publish_cone_parameters(self) -> None:
        source = (ROOT / "code/renderervk/tr_shade.c").read_text(encoding="utf-8")
        start = source.index("static const mapLightDef_t *VK_WorldSpotForDlight")
        end = source.index("static void VK_SetLightParams", start)
        helper = source[start:end]

        self.assertIn("dl->linear", helper)
        self.assertIn("SHADOW_SPOT_SOURCE_STATIC_MAP", helper)
        self.assertIn("light->type == MAP_LIGHT_SPOT", helper)

        params_start = end
        params_end = source.index("uint32_t VK_PushUniform", params_start)
        params = source[params_start:params_end]
        self.assertIn("uniform->depthFadeBias[2] = 2.0f;", params)
        self.assertIn("uniform->depthFadeBias[3] = 2.0f;", params)
        self.assertIn("worldSpot = VK_WorldSpotForDlight( dl );", params)
        self.assertIn("cosf( innerAngle", params)
        self.assertIn("cosf( outerAngle", params)

    def test_line_shader_clips_world_spots_but_keeps_legacy_capsules(self) -> None:
        shader = (ROOT / "code/renderervk/shaders/light_frag.tmpl").read_text(
            encoding="utf-8"
        )
        line_start = shader.index("#ifdef USE_LINE", shader.index("void main()"))
        line_end = shader.index("#else", line_start)
        line_path = shader[line_start:line_end]

        self.assertIn("bool worldSpot", line_path)
        self.assertIn("smoothstep(outerCos, innerCos, cosTheta)", line_path)
        self.assertIn("LL = L;", line_path)
        self.assertIn("project fragment on the legacy linear light vector", line_path)
        self.assertIn("lightVector * scale + L", line_path)
        self.assertIn("* coneFactor", line_path)


if __name__ == "__main__":
    unittest.main()

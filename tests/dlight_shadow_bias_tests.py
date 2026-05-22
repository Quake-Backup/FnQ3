import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


class DlightShadowBiasTests(unittest.TestCase):
    def assert_cvar_default(self, source, name, value):
        self.assertRegex(
            source,
            rf'ri\.Cvar_Get\(\s*"{re.escape(name)}",\s*"{re.escape(value)}",',
        )

    def test_dlight_shadow_bias_defaults_match_between_renderers(self):
        for path in ("code/renderer/tr_init.c", "code/renderervk/tr_init.c"):
            with self.subTest(path=path):
                source = read_text(path)
                self.assert_cvar_default(source, "r_dlightShadowBias", "4")
                self.assert_cvar_default(source, "r_dlightShadowCasterDepthBias", "1")
                self.assert_cvar_default(source, "r_dlightShadowCasterSlopeBias", "1")
                self.assert_cvar_default(source, "r_dlightShadowCasterNormalBias", "0.25")
                self.assertIn("angle-aware, texel-aware dynamic-light shadow-map sampling", source)

    def test_vulkan_receiver_bias_is_angle_aware_and_texel_limited(self):
        source = read_text("code/renderervk/shaders/light_frag.tmpl")

        self.assertIn("float receiverSlope = 1.0 - receiverNDotL;", source)
        self.assertIn("float receiverBias = depthFadeInfo.z * (0.125 + 0.375 * receiverSlope);", source)
        self.assertIn("float texelWorldBias = max(2.0 * faceDist / faceSize, 0.125);", source)
        self.assertIn("receiverBias = min(receiverBias, texelWorldBias);", source)

    def test_glx_receiver_bias_matches_vulkan_policy(self):
        source = read_text("code/renderer/tr_arb.c")

        self.assertIn("shadowReceiverBiasScale =", source)
        self.assertIn("r_dlightShadowBias ? r_dlightShadowBias->value : 4.0f ) / shadowAtlas[0]", source)
        self.assertIn('"MAD local.x, local.x, -half.x, one.x; \\n"', source)
        self.assertIn('"MUL local.x, local.x, half.x; \\n"', source)
        self.assertIn('"MUL local.x, local.x, dlightShadow.w; \\n"', source)
        self.assertIn('"MUL local.x, local.x, faceInfo.x; \\n"', source)
        self.assertNotIn("biasShape", source)

    def test_glx_shadow_program_avoids_short_source_swizzles(self):
        source = read_text("code/renderer/tr_arb.c")

        self.assertIn('"MAX tile.x, tile.x, local.z; \\n"', source)
        self.assertIn('"MAX tile.y, tile.y, local.z; \\n"', source)
        self.assertIn('"MIN tile.x, tile.x, local.w; \\n"', source)
        self.assertIn('"MIN tile.y, tile.y, local.w; \\n"', source)
        self.assertIn('"MUL tile.x, tile.x, dlightShadow.x; \\n"', source)
        self.assertIn('"MUL tile.y, tile.y, dlightShadow.y; \\n"', source)
        self.assertNotIn('"MAX tile.xy, tile.xy, local.zzzz; \\n"', source)
        self.assertNotIn('"MIN tile.xy, tile.xy, local.wwww; \\n"', source)
        self.assertNotIn('"MUL tile.xy, tile.xy, dlightShadow.xy; \\n"', source)

    def test_caster_bias_fallbacks_are_contact_preserving(self):
        expected_normal_scale = (
            "normalScale = 0.25f + 0.50f * ( 1.0f - "
            "Com_Clamp( 0.0f, 1.0f, fabsf( lightSide ) ) );"
        )
        for path in ("code/renderer/tr_shade.c", "code/renderervk/tr_shade.c"):
            with self.subTest(path=path):
                source = read_text(path)
                self.assertIn("r_dlightShadowCasterNormalBias->value : 0.25f", source)
                self.assertIn(expected_normal_scale, source)

        glx_backend = read_text("code/renderer/tr_backend.c")
        self.assertIn("r_dlightShadowCasterSlopeBias->value : 1.0f", glx_backend)
        self.assertIn("r_dlightShadowCasterDepthBias->value : 1.0f", glx_backend)

        vk_backend = read_text("code/renderervk/vk.c")
        self.assertIn("r_dlightShadowCasterDepthBias->value : 1.0f", vk_backend)
        self.assertIn("r_dlightShadowCasterSlopeBias->value : 1.0f", vk_backend)


if __name__ == "__main__":
    unittest.main()

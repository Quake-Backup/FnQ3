from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def section(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    finish = source.index(end, begin)
    return source[begin:finish]


class RtxFogDlightSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.init = read("code/rendererrtx/tr_init.c")
        cls.local = read("code/rendererrtx/tr_local.h")
        cls.image = read("code/rendererrtx/tr_image.c")
        cls.scene = read("code/rendererrtx/tr_scene.c")
        cls.shade = read("code/rendererrtx/tr_shade.c")
        cls.generic_frag = read("code/rendererrtx/shaders/gen_frag.tmpl")
        cls.light_frag = read("code/rendererrtx/shaders/light_frag.tmpl")
        cls.fog_frag = read("code/rendererrtx/shaders/fog.frag")

    def test_renderer_defaults_and_controls_match_the_vk_parity_tier(self) -> None:
        defaults = {
            "r_intensity": "1.25",
            "r_fogMode": "1",
            "r_dlightSpecPower": "10",
            "r_dlightSpecColor": "-0.2",
            "r_dlightFalloff": "1",
            "r_dlightSaturation": "0.8",
            "r_dlightOverbrightGamut": "1",
            "r_bloom_threshold": "0.75",
        }
        for name, value in defaults.items():
            with self.subTest(cvar=name):
                self.assertRegex(
                    self.init,
                    rf'ri\.Cvar_Get\(\s*"{re.escape(name)}",\s*"{re.escape(value)}"',
                )
                self.assertIn(f"*{name}", self.local)

        self.assertRegex(
            self.init,
            r'ri\.Cvar_Get\(\s*"r_fogMode",\s*"1",\s*CVAR_ARCHIVE_ND\s*\)',
        )
        for name in (
            "r_fogMode",
            "r_dlightSpecPower",
            "r_dlightSpecColor",
            "r_dlightFalloff",
            "r_dlightSaturation",
            "r_dlightOverbrightGamut",
        ):
            with self.subTest(group=name):
                registration = self.init.index(f'"{name}"')
                self.assertIn(
                    f"ri.Cvar_SetGroup( {name}, CVG_RENDERER );",
                    self.init[registration : registration + 1500],
                )

    def test_cpu_and_raster_fog_share_analytic_math_with_legacy_fallback(self) -> None:
        self.assertIn('#include "../renderercommon/tr_fog_math.h"', self.image)

        fog_factor = section(
            self.image,
            "float R_FogFactor( float s, float t ) {",
            "static void R_CreateFogImage",
        )
        self.assertIn("r_fogMode && r_fogMode->integer", fog_factor)
        self.assertIn("R_AnalyticFogFactor( s, t )", fog_factor)
        self.assertIn(
            "R_LegacyFogFactor( s, t, tr.fogTable, FOG_TABLE_SIZE )",
            fog_factor,
        )

        fog_image = section(
            self.image,
            "static void R_CreateFogImage( void ) {",
            "static void R_CreateDefaultImage",
        )
        self.assertIn("R_LegacyFogFactor(", fog_image)
        self.assertNotIn("R_FogFactor(", fog_image)

        fog_params = section(
            self.shade,
            "void VK_SetFogParams( vkUniform_t *uniform, int *fogStage )",
            "#ifdef USE_PMLIGHT",
        )
        self.assertIn(
            "uniform->fogEyeT[2] = r_fogMode && r_fogMode->integer ? 1.0f : 0.0f;",
            fog_params,
        )

        for shader, sampler in (
            (self.generic_frag, "texture(fog_texture, fogCoord).a"),
            (self.light_frag, "texture(fogtexture, fogCoord).a"),
            (self.fog_frag, "texture(fog_texture, fogCoord).a"),
        ):
            with self.subTest(sampler=sampler):
                self.assertIn("float FogFactor(vec2 fogCoord)", shader)
                self.assertIn("if (fogEyeT.z < 0.5)", shader)
                self.assertIn(sampler, shader)
                self.assertIn(
                    "sqrt(clamp(fogDistance * 8.0, 0.0, 1.0))",
                    shader,
                )

        self.assertIn(
            "vec4 fog = vec4(1.0, 1.0, 1.0, FogFactor(fog_tex_coord));",
            self.generic_frag,
        )
        self.assertIn("float fogFactor = FogFactor(fog_tex_coord);", self.light_frag)
        self.assertIn(
            "out_color = vec4(fogColor.rgb, fogColor.a * fogFactor);",
            self.fog_frag,
        )

    def test_texture_intensity_is_applied_per_stage_not_baked_twice(self) -> None:
        upload_scale = section(
            self.image,
            "static void R_LightScaleTexture",
            "static void R_MipMap2",
        )
        self.assertIn("(void)only_gamma;", upload_scale)
        self.assertIn("glConfig.deviceSupportsGamma || vk.fboActive", upload_scale)
        self.assertIn("s_gammatable[p[0]]", upload_scale)
        self.assertNotIn("s_intensitytable", upload_scale)

        texture_scale = section(
            self.shade,
            "static float VK_ComputeTextureIntensityScale",
            "/*\n===================\nRB_FogPass",
        )
        self.assertIn("IMGFLAG_NOLIGHTSCALE", texture_scale)
        self.assertIn("IMGFLAG_MIPMAP", texture_scale)
        self.assertIn("image->uploadWidth != image->width", texture_scale)
        self.assertIn("return r_intensity->value;", texture_scale)
        self.assertGreaterEqual(
            self.shade.count("VK_SetTextureFactors( &uniform, pStage,"),
            2,
        )
        self.assertIn("color0.rgb *= texFactors.x;", self.generic_frag)
        self.assertIn("base.rgb *= texFactors.x;", self.light_frag)

    def test_dynamic_light_color_falloff_and_specular_controls_are_wired(self) -> None:
        controls = section(
            self.scene,
            "static float R_DlightSrgbToLinear",
            "/*\n=====================\nRE_AddRefEntityToScene",
        )
        self.assertIn("R_DlightLinearToSrgb", controls)
        self.assertIn("R_CompressDlightOverbrightGamut", controls)
        self.assertIn("r_dlightSaturation", controls)
        self.assertIn("r_dlightOverbrightGamut", controls)
        self.assertIn("LUMA( linearColor[0], linearColor[1], linearColor[2] )", controls)
        self.assertEqual(
            self.scene.count("R_ApplyDlightColorControls( &r, &g, &b );"),
            2,
        )

        set_factors = section(
            self.shade,
            "static void VK_SetTextureFactors",
            "/*\n===================\nRB_FogPass",
        )
        self.assertIn("r_dlightSpecPower", set_factors)
        self.assertIn("r_dlightSpecColor", set_factors)

        set_light = section(
            self.shade,
            "static void VK_SetLightParams",
            "uint32_t VK_PushUniform",
        )
        self.assertIn(
            "uniform->dlightFactors[0] = r_dlightFalloff ? r_dlightFalloff->value : 1.0f;",
            set_light,
        )

        self.assertIn(
            "intensFactor = mix(intensFactor, smoothFactor, "
            "clamp(dlightFactors.x, 0.0, 1.0));",
            self.light_frag,
        )
        self.assertIn(
            "vec4 specBase = base * texFactors.z + vec4(texFactors.w);",
            self.light_frag,
        )
        self.assertIn(
            "pow(specFactor, max(texFactors.y, 1.0))",
            self.light_frag,
        )

    def test_lighting_uniforms_are_refreshed_per_surface(self) -> None:
        lighting_pass = section(
            self.shade,
            "void VK_LightingPass( void )",
            "#endif // USE_PMLIGHT",
        )
        fog = lighting_pass.index("VK_SetFogParams( &uniform, &fog_stage );")
        light = lighting_pass.index("VK_SetLightParams( &uniform, tess.light );")
        texture = lighting_pass.index(
            "VK_SetTextureFactors( &uniform, pStage, tess.shader->lightingBundle );"
        )
        push = lighting_pass.index("uniform_offset = VK_PushUniform( &uniform );")
        self.assertLess(fog, light)
        self.assertLess(light, texture)
        self.assertLess(texture, push)
        self.assertNotIn("if ( tess.dlightUpdateParams )", lighting_pass)

    def test_parity_tier_does_not_import_shadow_atlas_or_csm_shader_code(self) -> None:
        for forbidden in (
            "dlight_shadow",
            "shadow_texture",
            "DlightShadowFactor",
            "shadowAtlas",
            "csm",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.light_frag)

        set_light = section(
            self.shade,
            "static void VK_SetLightParams",
            "uint32_t VK_PushUniform",
        )
        for forbidden in (
            "ShadowParams",
            "shadowPlan",
            "shadowAtlas",
            "R_ShadowManager",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, set_light)


if __name__ == "__main__":
    unittest.main()

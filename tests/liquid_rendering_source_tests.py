from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class LiquidRenderingSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gl = read("code/renderer/tr_shade.c")
        cls.vk = read("code/renderervk/tr_shade.c")
        cls.gl_init = read("code/renderer/tr_init.c")
        cls.vk_init = read("code/renderervk/tr_init.c")
        cls.gl_shader = read("code/rendererglx/glx_material.cpp")
        gl_liquid_start = cls.gl_shader.index("static const char kLiquidFragmentSource[]")
        gl_liquid_end = cls.gl_shader.index("static GLuint GLX_Material_CompileShader", gl_liquid_start)
        cls.gl_liquid_shader = cls.gl_shader[gl_liquid_start:gl_liquid_end]
        cls.vk_shader = read("code/renderervk/shaders/liquid.frag")
        cls.vk_vertex_shader = read("code/renderervk/shaders/liquid.vert")
        cls.gl_backend = read("code/renderer/tr_backend.c")
        cls.vk_backend = read("code/renderervk/tr_backend.c")
        cls.vk_impl = read("code/renderervk/vk.c")
        cls.gl_shader_system = read("code/renderer/tr_shader.c")
        cls.vk_shader_system = read("code/renderervk/tr_shader.c")

    def test_refraction_is_drawn_before_authored_stages_in_both_backends(self) -> None:
        gl_pre = self.gl.index("RB_DrawLiquidPass( &tess, qtrue )")
        gl_authored = self.gl.index("RB_IterateStagesGeneric( input )", gl_pre)
        gl_post = self.gl.index("RB_DrawLiquidPass( &tess, qfalse )", gl_authored)
        self.assertLess(gl_pre, gl_authored)
        self.assertLess(gl_authored, gl_post)

        vk_pre = self.vk.index("VK_DrawLiquidPass( &tess, qtrue )")
        vk_authored = self.vk.index("RB_IterateStagesGeneric( &tess, fogCollapse )", vk_pre)
        vk_post = self.vk.index("VK_DrawLiquidPass( &tess, qfalse )", vk_authored)
        self.assertLess(vk_pre, vk_authored)
        self.assertLess(vk_authored, vk_post)

    def test_refraction_strength_is_a_live_cross_backend_cvar(self) -> None:
        registration = 'Cvar_Get( "r_liquidRefraction", "0.65", CVAR_ARCHIVE_ND )'
        range_check = 'Cvar_CheckRange( r_liquidRefraction, "0.0", "1.0", CV_FLOAT )'
        for source in (self.gl_init, self.vk_init):
            self.assertIn(registration, source)
            self.assertIn(range_check, source)

    def test_ambient_warp_is_pixel_scaled_and_live(self) -> None:
        registration = 'Cvar_Get( "r_liquidWarp", "0.012", CVAR_ARCHIVE_ND )'
        range_check = 'Cvar_CheckRange( r_liquidWarp, "0.0", "0.05", CV_FLOAT )'
        for source in (self.gl_init, self.vk_init):
            self.assertIn(registration, source)
            self.assertIn(range_check, source)
        self.assertIn("(ambientPixels + ripplePixels) * u_TargetInverse.xy", self.gl_shader)
        self.assertIn("(ambient_pixels + ripple_pixels) * inverse_view", self.vk_shader)
        self.assertIn("LIQUID_WARP_TO_PIXELS", self.gl)
        self.assertIn("LIQUID_WARP_TO_PIXELS", self.vk)

    def test_refraction_uses_projective_face_coordinates(self) -> None:
        self.assertIn("v_ScreenPosition = clipPosition", self.gl_shader)
        self.assertIn(
            "v_ScreenPosition.xy / v_ScreenPosition.w * 0.5 + 0.5",
            self.gl_liquid_shader,
        )
        self.assertNotIn("gl_FragCoord", self.gl_liquid_shader)

        self.assertIn("frag_screen = vec4(clip.xy * 0.5 + clip.ww * 0.5", self.vk_vertex_shader)
        self.assertIn("frag_screen.xy / frag_screen.w", self.vk_shader)
        self.assertNotIn("gl_FragCoord", self.vk_shader)

    def test_original_liquid_contents_survive_shader_remaps(self) -> None:
        combined = "shader->contentFlags | state->contentFlags"
        self.assertGreaterEqual(self.gl.count(combined), 2)
        self.assertGreaterEqual(self.vk.count(combined), 2)
        self.assertIn("tess.liquidContentFlags = " + combined, self.gl)
        self.assertIn("tess.liquidContentFlags = " + combined, self.vk)

    def test_gl_fallback_does_not_overwrite_authored_stage_colors(self) -> None:
        begin = self.gl.index("static void RB_DrawLiquidPass")
        end = self.gl.index("#endif /* USE_FBO */", begin)
        liquid_pass = self.gl[begin:end]
        self.assertIn("rb_liquidColors[i].rgba", liquid_pass)
        self.assertNotIn("input->svars.colors[i].rgba", liquid_pass)

    def test_shaders_have_distinct_refraction_and_fresnel_alpha_paths(self) -> None:
        self.assertIn("u_Params.w < 0.0", self.gl_shader)
        self.assertIn("typeScale * clamp(u_Params.z, 0.0, 1.0)", self.gl_shader)
        self.assertEqual(self.gl_liquid_shader.count("texture2D(u_Texture0"), 1)
        self.assertIn("gl_FragColor = vec4(sheenColor, alpha)", self.gl_liquid_shader)
        self.assertIn("liquid_info.w > 0.5", self.vk_shader)
        self.assertIn("liquid_info.x * clamp(liquid_params.z, 0.0, 1.0)", self.vk_shader)
        self.assertEqual(self.vk_shader.count("texture(scene_color"), 1)
        self.assertIn("out_color = vec4(sheen_color, alpha)", self.vk_shader)

    def test_snapshot_capture_is_at_a_deterministic_sort_boundary(self) -> None:
        trigger = "liquidSnapshotPending && shader->sort >= SS_FOG"
        lookahead = "RB_DrawSurfListNeedsLiquidSnapshot"
        for source in (self.gl_backend, self.vk_backend):
            self.assertIn(lookahead, source)
            self.assertIn(trigger, source)

    def test_early_or_masked_liquids_keep_the_authored_path(self) -> None:
        for shade in (self.gl, self.vk):
            self.assertIn("input->liquidSort >= SS_FOG", shade)
            self.assertIn("R_LiquidShaderSupported( input->shader )", shade)
        for shader_system in (self.gl_shader_system, self.vk_shader_system):
            self.assertIn("GLS_ATEST_BITS | GLS_DEPTHTEST_DISABLE", shader_system)
            self.assertIn("GLS_DEPTHFUNC_EQUAL", shader_system)
            self.assertIn("GLS_POLYMODE_LINE", shader_system)
            self.assertIn("shader->dfType != DFT_NONE", shader_system)

    def test_vulkan_snapshot_downsample_has_a_dedicated_linear_sampler(self) -> None:
        self.assertIn("vk.liquidSnapshot.source_descriptor", self.vk_impl)
        self.assertIn("sd.gl_mag_filter = sd.gl_min_filter = GL_LINEAR", self.vk_impl)
        self.assertIn("&vk.liquidSnapshot.source_descriptor, 0, NULL", self.vk_impl)

    def test_vulkan_snapshot_dependencies_are_full_image(self) -> None:
        self.assertIn("liquidDeps[0].dependencyFlags = 0", self.vk_impl)
        self.assertIn("liquidDeps[1].dependencyFlags = 0", self.vk_impl)
        capture = self.vk_impl.index("qboolean vk_capture_liquid_scene")
        resume = self.vk_impl.index("vk_begin_main_render_pass_load();", capture)
        self.assertNotIn("VK_DEPENDENCY_BY_REGION_BIT", self.vk_impl[capture:resume])

    def test_liquid_passes_preserve_destination_alpha(self) -> None:
        self.assertIn("GL_ColorMask( previousColorMask[0]", self.gl)
        self.assertIn("def->shader_type == TYPE_LIQUID", self.vk_impl)
        self.assertIn("VK_COLOR_COMPONENT_G_BIT | VK_COLOR_COMPONENT_B_BIT", self.vk_impl)


if __name__ == "__main__":
    unittest.main()

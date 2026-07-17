from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class RtxLiquidRenderingSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.init = read("code/rendererrtx/tr_init.c")
        cls.local = read("code/rendererrtx/tr_local.h")
        cls.scene = read("code/rendererrtx/tr_scene.c")
        cls.shader_system = read("code/rendererrtx/tr_shader.c")
        cls.shade = read("code/rendererrtx/tr_shade.c")
        cls.backend = read("code/rendererrtx/tr_backend.c")
        cls.vk_header = read("code/rendererrtx/vk.h")
        cls.vk = read("code/rendererrtx/vk.c")
        cls.liquid_vert = read("code/rendererrtx/shaders/liquid.vert")
        cls.liquid_frag = read("code/rendererrtx/shaders/liquid.frag")
        cls.liquid_copy = read("code/rendererrtx/shaders/liquid_copy.frag")
        cls.shader_data = read(
            "code/rendererrtx/shaders/spirv/shader_data.c"
        )
        cls.reflection = json.loads(
            read("code/rendererrtx/shaders/spirv/shader_reflection.json")
        )

    def test_cvars_and_interaction_feed_match_vk_surface(self) -> None:
        expected = (
            'Cvar_Get( "r_liquid", "2", CVAR_ARCHIVE_ND | CVAR_LATCH )',
            'Cvar_Get( "r_liquidResolution", "1.0", CVAR_ARCHIVE_ND | CVAR_LATCH )',
            'Cvar_Get( "r_liquidRefraction", "0.65", CVAR_ARCHIVE_ND )',
            'Cvar_Get( "r_liquidWarpScale", "1.0", CVAR_ARCHIVE_ND )',
            'Cvar_Get( "r_liquidReflection", "0.65", CVAR_ARCHIVE_ND )',
            'Cvar_Get( "r_liquidRipples", "1.0", CVAR_ARCHIVE_ND )',
        )
        for registration in expected:
            self.assertIn(registration, self.init)
        self.assertIn("r_liquidRipples->value <= 0.0f", self.scene)
        self.assertIn("RE_AddLiquidInteractionToScene", self.scene)
        self.assertIn("liquidInteractions", self.local)

    def test_snapshot_boundary_respects_rt_overlay_order(self) -> None:
        self.assertIn("RB_DrawSurfListNeedsLiquidSnapshot", self.backend)
        self.assertIn(
            "liquidSnapshotPending && shader->sort >= SS_FOG",
            self.backend,
        )
        self.assertIn("RB_DRAWSURFS_RT_OVERLAY", self.backend)
        draw_surfs = self.backend.index("static const void *RB_DrawSurfs")
        trace = self.backend.index("vk_rt_trace_frame()", draw_surfs)
        overlay = self.backend.index(
            "RB_DRAWSURFS_RT_OVERLAY", trace
        )
        self.assertLess(trace, overlay)
        self.assertIn("vk_capture_liquid_scene()", self.backend)
        self.assertIn(
            "vk.renderPassIndex != RENDER_PASS_POST_BLOOM", self.backend
        )

    def test_liquid_pass_wraps_authored_material(self) -> None:
        pre = self.shade.index("VK_DrawLiquidPass( &tess, qtrue )")
        authored = self.shade.index(
            "RB_IterateStagesGeneric( &tess, fogCollapse )", pre
        )
        post = self.shade.index(
            "VK_DrawLiquidPass( &tess, qfalse )", authored
        )
        self.assertLess(pre, authored)
        self.assertLess(authored, post)
        self.assertIn(
            "tess.liquidContentFlags = shader->contentFlags | state->contentFlags",
            self.shade,
        )
        self.assertIn("R_LiquidShaderSupported", self.shader_system)
        for bit in (
            "GLS_ATEST_BITS",
            "GLS_DEPTHTEST_DISABLE",
            "GLS_DEPTHFUNC_EQUAL",
            "GLS_POLYMODE_LINE",
        ):
            self.assertIn(bit, self.shader_system)

    def test_vulkan_resources_and_depth_are_private(self) -> None:
        for token in (
            "VkRenderPass liquid_snapshot",
            "liquidSnapshot",
            "liquidDepth",
            "liquid_snapshot_pipeline",
            "liquid_pipelines[3][2][2]",
            "liquidSnapshotWidth",
            "liquidSnapshotHeight",
        ):
            self.assertIn(token, self.vk_header)
        self.assertIn("VK_IMAGE_USAGE_TRANSFER_SRC_BIT", self.vk)
        self.assertIn("VK_IMAGE_USAGE_TRANSFER_DST_BIT", self.vk)
        self.assertIn("create_liquid_depth_attachment", self.vk)
        self.assertIn("vk_liquid_depth_ready", self.vk)
        self.assertIn("vk.depth_sample_descriptor", self.vk)
        self.assertIn("vk.liquidDepth.descriptor", self.vk)
        self.assertNotEqual(
            self.vk_header.index("depth_sample_descriptor"),
            self.vk_header.index("liquidDepth"),
        )

    def test_capture_resumes_shared_post_main_load_pass(self) -> None:
        start = self.vk.index("qboolean vk_capture_liquid_scene")
        end = self.vk.index("void vk_draw_global_fog", start)
        capture = self.vk[start:end]
        self.assertIn("vk_end_render_pass();", capture)
        self.assertIn("vk_begin_liquid_snapshot_render_pass();", capture)
        self.assertIn("vk_begin_post_bloom_render_pass();", capture)
        self.assertIn("vk.renderPassIndex != RENDER_PASS_MAIN", capture)
        self.assertIn("vk.renderPassIndex != RENDER_PASS_POST_BLOOM", capture)
        self.assertIn(
            "MIN( VK_DESC_COUNT, vk.maxBoundDescriptorSets ) - 1",
            capture,
        )

    def test_depth_stencil_barriers_cover_both_aspects(self) -> None:
        start = self.vk.index("static void record_image_layout_transition")
        end = self.vk.index("// debug markers", start)
        transition = self.vk[start:end]
        self.assertIn(
            "image == vk.depth_image || image == vk.liquidDepth.image",
            transition,
        )
        self.assertIn(
            "image_aspect_flags |= VK_IMAGE_ASPECT_STENCIL_BIT",
            transition,
        )

        start = self.vk.index("qboolean vk_capture_liquid_scene")
        end = self.vk.index("void vk_draw_global_fog", start)
        capture = self.vk[start:end]
        self.assertIn(
            "region.srcSubresource.aspectMask = VK_IMAGE_ASPECT_DEPTH_BIT",
            capture,
        )
        self.assertIn(
            "region.dstSubresource.aspectMask = VK_IMAGE_ASPECT_DEPTH_BIT",
            capture,
        )

    def test_post_main_pass_preserves_and_synchronizes_liquid_depth(self) -> None:
        start = self.vk.index("static void vk_create_render_passes")
        end = self.vk.index("static void vk_create_framebuffers", start)
        render_passes = self.vk[start:end]

        self.assertIn(
            "globalFogEnabled || depthFadeActive",
            render_passes,
        )
        self.assertIn("liquidCaptureActive", render_passes)
        self.assertIn(
            "VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT",
            render_passes,
        )
        self.assertIn(
            "VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_READ_BIT",
            render_passes,
        )
        self.assertGreaterEqual(
            render_passes.count("VK_PIPELINE_STAGE_EARLY_FRAGMENT_TESTS_BIT"),
            2,
        )
        self.assertGreaterEqual(
            render_passes.count("VK_PIPELINE_STAGE_LATE_FRAGMENT_TESTS_BIT"),
            2,
        )

    def test_post_process_restore_never_binds_a_null_uniform_set(self) -> None:
        start = self.vk.index("void vk_bind_descriptor_sets")
        end = self.vk.index("void vk_bind_pipeline", start)
        binder = self.vk[start:end]
        self.assertIn("for ( i = start; i <= end; i++ )", binder)
        self.assertIn("if ( i == VK_DESC_UNIFORM )", binder)
        self.assertIn("vk.cmd->uniform_descriptor", binder)
        self.assertIn("vk.cmd->uniform_read_offset", binder)
        self.assertIn("tr.whiteImage->descriptor", binder)

    def test_liquid_pipeline_uses_rgb_only_and_no_generic_specs(self) -> None:
        self.assertIn("case TYPE_LIQUID:", self.vk)
        self.assertIn(
            "def->shader_type == TYPE_LIQUID ? NULL : &frag_spec_info",
            self.vk,
        )
        self.assertIn(
            "program_index == 4 || program_index == 5",
            self.vk,
        )
        color_mask = self.vk.index(
            "else if ( def->shader_type == TYPE_LIQUID )"
        )
        rgba = self.vk.index(
            "VK_COLOR_COMPONENT_A_BIT", color_mask
        )
        liquid_branch = self.vk[color_mask:rgba]
        self.assertIn("VK_COLOR_COMPONENT_R_BIT", liquid_branch)
        self.assertIn("VK_COLOR_COMPONENT_G_BIT", liquid_branch)
        self.assertIn("VK_COLOR_COMPONENT_B_BIT", liquid_branch)
        self.assertNotIn("VK_COLOR_COMPONENT_A_BIT", liquid_branch)

    def test_shaders_and_generated_bundle_are_integrated(self) -> None:
        self.assertIn("layout(set = 1", self.liquid_frag)
        self.assertIn("layout(set = 2", self.liquid_frag)
        self.assertIn("gl_FragCoord.z + 0.00003", self.liquid_frag)
        self.assertIn("liquid_mvp", self.liquid_vert)
        self.assertIn("current_scene", self.liquid_copy)
        for symbol in (
            "liquid_vert_spv",
            "liquid_frag_spv",
            "liquid_copy_frag_spv",
        ):
            self.assertIn(symbol, self.shader_data)
        reflected_sources = {
            entry["source"] for entry in self.reflection["shaders"]
        }
        self.assertTrue(
            {"liquid.vert", "liquid.frag", "liquid_copy.frag"}
            <= reflected_sources
        )

    def test_uniform_prefix_covers_liquid_shader_contract(self) -> None:
        for field in (
            "texFactors",
            "depthFadeInfo",
            "depthFadeScale",
            "depthFadeBias",
            "dlightFactors",
            "csmModelX",
            "csmModelY",
            "csmModelZ",
            "csmAxisX",
            "csmAxisY",
            "csmAxisZ",
        ):
            self.assertIn(field, self.vk_header)
        self.assertIn("vec_t *slots[18]", self.shade)
        self.assertIn("vk_get_liquid_mvp", self.shade)


if __name__ == "__main__":
    unittest.main()

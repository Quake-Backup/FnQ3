from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def section(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    finish = source.index(end, begin)
    return source[begin:finish]


class RtxRasterOverlayParitySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.init = read("code/rendererrtx/tr_init.c")
        cls.local = read("code/rendererrtx/tr_local.h")
        cls.shader = read("code/rendererrtx/tr_shader.c")
        cls.shade = read("code/rendererrtx/tr_shade.c")
        cls.backend = read("code/rendererrtx/tr_backend.c")
        cls.vk_header = read("code/rendererrtx/vk.h")
        cls.vk = read("code/rendererrtx/vk.c")
        cls.generic_frag = read("code/rendererrtx/shaders/gen_frag.tmpl")

    def test_parity_cvars_are_default_on_and_depth_fade_is_latched(self) -> None:
        self.assertRegex(
            self.init,
            r'Cvar_Get\(\s*"r_depthFade",\s*"1",\s*'
            r"CVAR_ARCHIVE_ND\s*\|\s*CVAR_LATCH\s*\)",
        )
        self.assertRegex(
            self.init,
            r'Cvar_Get\(\s*"r_hudExcludePostProcess",\s*"1",\s*'
            r"CVAR_ARCHIVE_ND\s*\)",
        )
        self.assertIn("extern cvar_t\t*r_depthFade", self.local)
        self.assertIn("extern cvar_t\t*r_hudExcludePostProcess", self.local)

    def test_shader_metadata_and_builtin_particles_match_vk_contract(self) -> None:
        self.assertIn('"q3map_depthFade"', self.shader)
        self.assertIn("ParseDepthFade( text );", self.shader)
        for fade_type in ("DFT_BLEND", "DFT_ADD", "DFT_MULT", "DFT_PMA"):
            self.assertIn(fade_type, self.shader)
        for builtin in (
            '"rocketExplosion"',
            '"sprites/particleSmoke"',
            '"plasmaExplosion"',
            '"shotgunSmokePuffNPM"',
        ):
            self.assertIn(builtin, self.shader)

        finish = section(
            self.shader,
            "static shader_t *FinishShader( void )",
            "//========================================================================================",
        )
        process = finish.index("ProcessDepthFade();")
        pipelines = finish.index("Vk_Pipeline_Def def;", process)
        self.assertLess(process, pipelines)
        self.assertIn("def.depth_fade", finish)
        self.assertIn("pStage->bundle[1].image[0] == NULL", finish)
        self.assertIn("!pStage->depthFragment", finish)

    def test_generic_pipeline_samples_depth_only_for_supported_single_texture_stages(
        self,
    ) -> None:
        self.assertIn("#define USE_DEPTH_FADE", self.generic_frag)
        self.assertIn("uniform sampler2D depth_texture", self.generic_frag)
        self.assertIn("vec4 depthFadeInfo", self.generic_frag)
        self.assertIn("constant_id = 11", self.generic_frag)
        self.assertIn("ApplyDepthFade", self.generic_frag)
        self.assertIn("depthFadeInfo.z <= 0.0", self.generic_frag)
        self.assertIn("base = ApplyDepthFade(base);", self.generic_frag)

        self.assertIn("int depth_fade;", self.vk_header)
        pipeline = section(
            self.vk,
            "VkPipeline create_pipeline(",
            "static void get_mvp_transform",
        )
        self.assertIn("frag_spec_data[11].i = def->depth_fade;", pipeline)
        self.assertIn("constantID = 11", pipeline)
        self.assertIn("mapEntryCount = 12", pipeline)

    def test_runtime_uniform_path_preserves_authored_fallback(self) -> None:
        depth_fade = section(
            self.shade,
            "static qboolean RB_DepthFadeShaderSupported",
            "/*\n** RB_IterateStagesGeneric",
        )
        self.assertIn("RDF_NOWORLDMODEL", depth_fade)
        self.assertIn("RF_DEPTHHACK", depth_fade)
        self.assertIn("vk_depth_fade_ready()", depth_fade)
        self.assertIn("Com_Memset( uniform.depthFadeInfo, 0", depth_fade)
        self.assertIn("tess.shader->dfInvDist", depth_fade)
        self.assertIn("tess.shader->dfBias", depth_fade)
        self.assertIn("vk.liquidDepth.descriptor", depth_fade)
        self.assertIn("RB_SetDepthFade( pStage );", self.shade)

    def test_shared_scene_depth_snapshot_covers_rt_and_raster_overlay_passes(
        self,
    ) -> None:
        self.assertIn("vk_scene_depth_snapshot_requested", self.vk)
        self.assertIn(
            "vk_liquid_requested() || vk_depth_fade_requested()",
            self.vk,
        )
        self.assertIn("VK_IMAGE_USAGE_TRANSFER_SRC_BIT", self.vk)
        self.assertIn("VK_IMAGE_USAGE_TRANSFER_DST_BIT", self.vk)
        self.assertIn("vk_depth_fade_supported", self.vk_header)
        self.assertIn("vk_depth_fade_available", self.vk_header)
        self.assertIn("vk_depth_fade_ready", self.vk_header)

        copy = section(
            self.vk,
            "void vk_copy_depth_fade( void )",
            "qboolean vk_capture_liquid_scene",
        )
        self.assertIn("RENDER_PASS_MAIN", copy)
        self.assertIn("RENDER_PASS_POST_BLOOM", copy)
        self.assertIn("qvkCmdCopyImage", copy)
        self.assertIn("vk.liquidDepth.copied = qtrue;", copy)
        self.assertIn("vk_begin_post_bloom_render_pass();", copy)

        render_passes = section(
            self.vk,
            "static void vk_create_render_passes",
            "static void vk_create_framebuffers",
        )
        self.assertIn("const qboolean depthFadeActive", render_passes)
        self.assertIn("depthFadeActive", render_passes)
        self.assertIn("VK_ATTACHMENT_STORE_OP_STORE", render_passes)

        capture = section(
            self.vk,
            "qboolean vk_capture_liquid_scene",
            "void vk_draw_global_fog",
        )
        self.assertIn("!vk.liquidDepth.copied", capture)

    def test_depth_snapshot_is_invalidated_for_every_view_depth_clear(self) -> None:
        clear = section(
            self.vk,
            "void vk_clear_depth( qboolean clear_stencil )",
            "void vk_update_mvp",
        )
        invalidate = clear.index("vk.liquidDepth.copied = qfalse;")
        clean_return = clear.index("vk_world.dirty_depth_attachment == 0")
        self.assertLess(invalidate, clean_return)

    def test_depth_snapshot_capture_is_primary_full_view_only(self) -> None:
        helper = section(
            self.backend,
            "static qboolean RB_IsPrimaryFullView",
            "static qboolean RB_ShaderNeedsLiquidSnapshot",
        )
        for guard in (
            "RDF_NOWORLDMODEL",
            "portalView == PV_NONE",
            "stereoFrame == STEREO_CENTER",
            "viewportX == 0",
            "viewportY == 0",
            "viewportWidth == glConfig.vidWidth",
            "viewportHeight == glConfig.vidHeight",
        ):
            self.assertIn(guard, helper)

        draw_list = section(
            self.backend,
            "static void RB_RenderDrawSurfList",
            "static void RB_RenderLitSurfList",
        )
        self.assertIn("RB_IsPrimaryFullView()", draw_list)

        copy = section(
            self.vk,
            "void vk_copy_depth_fade( void )",
            "qboolean vk_capture_liquid_scene",
        )
        for guard in (
            "RDF_NOWORLDMODEL",
            "portalView != PV_NONE",
            "stereoFrame != STEREO_CENTER",
            "viewportX != 0",
            "viewportY != 0",
            "viewportWidth != glConfig.vidWidth",
            "viewportHeight != glConfig.vidHeight",
        ):
            self.assertIn(guard, copy)

    def test_rt_raster_bridge_has_explicit_read_and_overlay_dependencies(
        self,
    ) -> None:
        trace = section(
            self.vk,
            "qboolean vk_rt_trace_frame( void )",
            "static const char *vk_capability_value",
        )
        self.assertIn("VkImageMemoryBarrier sceneColorBarrier;", trace)
        self.assertIn(
            "sceneColorBarrier.srcAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;",
            trace,
        )
        self.assertIn(
            "sceneColorBarrier.dstAccessMask = VK_ACCESS_SHADER_READ_BIT;",
            trace,
        )
        self.assertIn("VK_PIPELINE_STAGE_RAY_TRACING_SHADER_BIT_KHR", trace)
        self.assertIn("VK_ACCESS_TRANSFER_WRITE_BIT", trace)
        self.assertIn("VK_ACCESS_COLOR_ATTACHMENT_READ_BIT", trace)
        self.assertIn("VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT", trace)
        self.assertIn("VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT", trace)

    def test_bloom_invalidates_main_pipeline_and_descriptor_state(self) -> None:
        bloom = section(
            self.vk,
            "qboolean vk_bloom( void )",
            "return qtrue;\n}",
        )
        self.assertIn("vk.cmd->last_pipeline = VK_NULL_HANDLE;", bloom)
        self.assertIn("vk.cmd->depth_range = DEPTH_RANGE_COUNT;", bloom)
        self.assertIn("vk.cmd->descriptor_set.start = 0;", bloom)
        self.assertIn(
            "MIN( VK_DESC_COUNT, vk.maxBoundDescriptorSets ) - 1;",
            bloom,
        )
        self.assertIn(
            "Com_Memset( &vk.cmd->scissor_rect, 0xff",
            bloom,
        )
        self.assertNotIn(
            "if ( vk.cmd->last_pipeline != VK_NULL_HANDLE )",
            bloom,
        )

    def test_single_texture_draws_bind_depth_fade_fallback_set(self) -> None:
        bind = section(
            self.vk,
            "void vk_bind_descriptor_sets( void )",
            "void vk_bind_pipeline",
        )
        self.assertIn("start <= VK_DESC_DEPTH_FADE", bind)
        self.assertIn("end < VK_DESC_DEPTH_FADE", bind)
        self.assertIn("end = VK_DESC_DEPTH_FADE;", bind)
        self.assertIn("tr.whiteImage->descriptor", bind)

    def test_depth_snapshot_occurs_before_translucency_after_rt_trace(self) -> None:
        draw_list = section(
            self.backend,
            "static void RB_RenderDrawSurfList",
            "static void RB_RenderLitSurfList",
        )
        self.assertIn("shader->sort > SS_OPAQUE", draw_list)
        self.assertIn("RB_IsPrimaryFullView()", draw_list)
        self.assertIn("RENDER_PASS_MAIN", draw_list)
        self.assertIn("RENDER_PASS_POST_BLOOM", draw_list)
        self.assertIn("vk_copy_depth_fade();", draw_list)
        self.assertIn("depthFadeSnapshot = vk_depth_fade_ready();", draw_list)

        draw_surfs = section(
            self.backend,
            "static const void *RB_DrawSurfs",
            "static const void *RB_DrawBuffer",
        )
        trace = draw_surfs.index("vk_rt_trace_frame();")
        overlay = draw_surfs.index("RB_DRAWSURFS_RT_OVERLAY", trace)
        self.assertLess(trace, overlay)

    def test_later_3d_hud_forces_world_bloom_before_switching_refdef(self) -> None:
        helper = section(
            self.backend,
            "static void RB_PreparePostProcessForHud3D",
            "static const void *RB_DrawSurfs",
        )
        self.assertIn("backEnd.doneSurfaces", helper)
        self.assertIn("r_hudExcludePostProcess->integer", helper)
        self.assertIn("RDF_NOWORLDMODEL", helper)
        self.assertIn("!backEnd.doneBloom", helper)
        self.assertIn("vk_bloom();", helper)

        draw_surfs = section(
            self.backend,
            "static const void *RB_DrawSurfs",
            "static const void *RB_DrawBuffer",
        )
        prepare = draw_surfs.index("RB_PreparePostProcessForHud3D")
        assign = draw_surfs.index("backEnd.refdef = cmd->refdef")
        self.assertLess(prepare, assign)

    def test_depth_fade_single_sample_requirement_is_explicit(self) -> None:
        sample_selection = section(
            self.vk,
            "vk_set_render_scale();",
            "vk.screenMapSamples =",
        )
        self.assertIn("depthFadeSingleSampleComposition", sample_selection)
        self.assertIn("vk_depth_fade_requested()", sample_selection)
        self.assertIn(
            "props.limits.maxBoundDescriptorSets > VK_DESC_DEPTH_FADE",
            sample_selection,
        )
        self.assertIn("disabling raster MSAA so soft-particle", sample_selection)
        self.assertIn("authored particle blending remains active", sample_selection)


if __name__ == "__main__":
    unittest.main()

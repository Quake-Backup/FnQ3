from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def source_section(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    finish = source.index(end, begin)
    return source[begin:finish]


class RtxRendererParitySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.init = read_text("code/rendererrtx/tr_init.c")
        cls.backend = read_text("code/rendererrtx/tr_backend.c")
        cls.commands = read_text("code/rendererrtx/tr_cmds.c")
        cls.local_header = read_text("code/rendererrtx/tr_local.h")
        cls.shader = read_text("code/rendererrtx/tr_shader.c")
        cls.vk_header = read_text("code/rendererrtx/vk.h")
        cls.vk = read_text("code/rendererrtx/vk.c")

    def test_rt_pipeline_is_the_safe_default_and_dynamic_blas_is_opt_in(self) -> None:
        self.assertRegex(
            self.init,
            r'ri\.Cvar_Get\(\s*"rtx_rt_mode",\s*"2",\s*'
            r"CVAR_ARCHIVE_ND\s*\|\s*CVAR_LATCH\s*\)",
        )
        self.assertRegex(
            self.init,
            r'ri\.Cvar_Get\(\s*"rtx_rt_require",\s*"0",\s*'
            r"CVAR_ARCHIVE_ND\s*\|\s*CVAR_LATCH\s*\)",
        )
        self.assertRegex(
            self.init,
            r'ri\.Cvar_Get\(\s*"rtx_rt_legacy_color_compat",\s*"1",\s*'
            r"CVAR_ARCHIVE_ND\s*\)",
        )
        self.assertRegex(
            self.init,
            r'ri\.Cvar_Get\(\s*"rtx_rt_raster_reference",\s*"0",\s*'
            r"CVAR_ARCHIVE_ND\s*\)",
        )
        self.assertRegex(
            self.init,
            r'ri\.Cvar_Get\(\s*"rtx_rt_dynamic_blas",\s*"0",\s*CVAR_ARCHIVE_ND\s*\)',
        )
        self.assertRegex(
            self.init,
            r'ri\.Cvar_Get\(\s*"rtx_rt_dynamic_resolution",\s*"0",\s*CVAR_ARCHIVE_ND\s*\)',
        )
        self.assertRegex(
            self.init,
            r'ri\.Cvar_Get\(\s*"rtx_rt_spatial_denoise",\s*"0",\s*CVAR_ARCHIVE_ND\s*\)',
        )

        capability_gate = source_section(
            self.vk,
            "const int requestedRtModeRaw = vk_requested_rt_mode();",
            "device_extension_list[ device_extension_count++ ] = VK_KHR_SWAPCHAIN_EXTENSION_NAME;",
        )
        self.assertIn("else if ( vk_rt_mode_required() )", capability_gate)
        self.assertIn("ri.Error( ERR_FATAL", capability_gate)
        fallback = capability_gate.index(
            "falling back to disabled mode."
        )
        fallback_assignment = capability_gate.index(
            "activeRtMode = RTX_RT_MODE_DISABLED;", fallback
        )
        self.assertLess(fallback, fallback_assignment)

        dynamic_gate = source_section(
            self.vk,
            "static qboolean vk_rt_ensure_dynamic_blas"
            "( VkDeviceSize *frameBudgetBytesUsed, VkDeviceSize frameBudgetBytes )\n{",
            "static uint32_t vk_rt_collect_instances",
        )
        self.assertIn("if ( !vk_rt_dynamic_blas_enabled() )", dynamic_gate)
        self.assertIn("using world-only TLAS instances", dynamic_gate)
        self.assertIn("vk_rt_destroy_as( &vk.rt.dynamic_blas );", dynamic_gate)

    def test_rt_replaces_only_opaque_world_and_replays_raster_overlays(self) -> None:
        overlay_filter = source_section(
            self.backend,
            "static qboolean RB_DrawSurfIncluded",
            "static void RB_RenderDrawSurfList",
        )
        self.assertIn("entityNum == REFENTITYNUM_WORLD", overlay_filter)
        self.assertIn("R_RtShaderNativeSupported( shader )", overlay_filter)
        self.assertIn("fogNum == 0", overlay_filter)
        self.assertIn("mode == RB_DRAWSURFS_RT_BASE", overlay_filter)
        self.assertIn("return rtBaseSurface ? qfalse : qtrue;", overlay_filter)

        draw_list = source_section(
            self.backend,
            "static void RB_RenderDrawSurfList",
            "static void RB_RenderLitSurfList",
        )
        self.assertIn("oldSort ^ drawSurf->sort", draw_list)
        self.assertNotIn("oldSort ^ drawSurfs->sort", draw_list)
        self.assertIn("mode != RB_DRAWSURFS_ALL", draw_list)

        draw_surfs = source_section(
            self.backend,
            "static const void *RB_DrawSurfs",
            "static const void *RB_DrawBuffer",
        )
        raster_pass = draw_surfs.index("RB_DRAWSURFS_RT_BASE")
        trace = draw_surfs.index("vk_rt_trace_frame();")
        overlay_pass = draw_surfs.index("RB_DRAWSURFS_RT_OVERLAY", trace)
        self.assertLess(raster_pass, trace)
        self.assertLess(trace, overlay_pass)
        for preserved_effect in (
            "RB_DrawSun",
            "RB_ShadowFinish",
            "RB_RenderFlares",
            "RB_DebugGraphics",
        ):
            self.assertIn(preserved_effect, draw_surfs[overlay_pass:])

        world_extraction = source_section(
            self.vk,
            "static qboolean vk_rt_extract_world_geometry"
            "( rtxRtCpuGeometry_t *geometry )\n{",
            "static qboolean vk_rt_build_triangles_blas",
        )
        self.assertIn(
            "shader->sort != SS_OPAQUE && shader->sort != SS_SEE_THROUGH",
            world_extraction,
        )
        self.assertIn("materialFlags |= RTX_RT_MATFLAG_RASTER_OVERLAY", world_extraction)
        self.assertIn("rasterOverlayOccluderCount++", world_extraction)
        self.assertIn("surface->fogIndex != 0", world_extraction)
        self.assertIn("fogOverlayOccluderCount++", world_extraction)
        self.assertIn("nonOccludingOverlaySkipCount++", world_extraction)

    def test_static_world_blas_excludes_inline_brush_models(self) -> None:
        world_extraction = source_section(
            self.vk,
            "static qboolean vk_rt_extract_world_geometry"
            "( rtxRtCpuGeometry_t *geometry )\n{",
            "static qboolean vk_rt_build_triangles_blas",
        )
        self.assertIn("worldModel = &tr.world->bmodels[0];", world_extraction)
        self.assertIn(
            "for ( i = 0; i < worldModel->numSurfaces; i++ )",
            world_extraction,
        )
        self.assertIn(
            "const msurface_t *surface = &worldModel->firstSurface[i];",
            world_extraction,
        )
        self.assertNotIn("tr.world->numsurfaces", world_extraction)
        self.assertNotIn("tr.world->surfaces[i]", world_extraction)

        sky_scan = source_section(
            self.vk,
            "static qboolean vk_rt_world_has_sky_surface( void )\n{",
            "static void vk_rt_estimate_world_bounds",
        )
        self.assertIn("worldModel = &tr.world->bmodels[0];", sky_scan)
        self.assertIn(
            "for ( i = 0; i < worldModel->numSurfaces; i++ )",
            sky_scan,
        )
        self.assertIn(
            "const msurface_t *surf = &worldModel->firstSurface[i];",
            sky_scan,
        )
        self.assertNotIn("tr.world->numsurfaces", sky_scan)
        self.assertNotIn("tr.world->surfaces[i]", sky_scan)

        dynamic_brush = source_section(
            self.vk,
            "static qboolean vk_rt_append_brush_entity_geometry"
            "( rtxRtCpuGeometry_t *geometry, const trRefEntity_t *ent, "
            "const model_t *model )\n{",
            "static void vk_rt_decode_md3_normal",
        )
        self.assertIn("bmodel = model->bmodel;", dynamic_brush)
        self.assertIn(
            "for ( s = 0; s < bmodel->numSurfaces; s++ )",
            dynamic_brush,
        )
        self.assertIn(
            "const msurface_t *surface = &bmodel->firstSurface[s];",
            dynamic_brush,
        )

    def test_trace_dispatch_is_limited_to_one_full_primary_view(self) -> None:
        primary = source_section(
            self.vk,
            "qboolean vk_rt_primary_view_eligible( void )\n{",
            "qboolean vk_rt_trace_frame( void )",
        )
        trace = source_section(
            self.vk,
            "qboolean vk_rt_trace_frame( void )\n{",
            "static const char *vk_capability_value",
        )
        required_gates = (
            "vk.renderPassIndex == RENDER_PASS_MAIN",
            "backEnd.viewParms.portalView == PV_NONE",
            "backEnd.viewParms.stereoFrame == STEREO_CENTER",
            "backEnd.viewParms.viewportX == 0",
            "backEnd.viewParms.viewportY == 0",
            "backEnd.viewParms.viewportWidth == glConfig.vidWidth",
            "backEnd.viewParms.viewportHeight == glConfig.vidHeight",
            "vk.rt.lastFrameBuilt == (uint32_t)tr.frameCount",
            "RDF_HYPERSPACE",
        )
        for gate in required_gates:
            with self.subTest(gate=gate):
                self.assertIn(gate, primary)
        self.assertIn("if ( !vk_rt_primary_view_eligible() )", trace)
        self.assertIn("rtComposition = vk_rt_primary_view_eligible();", self.backend)
        self.assertIn("return copiedToColor;", trace)
        self.assertIn(
            "if ( copiedToColor && vk_rt_post_validate_enabled()",
            trace,
        )
        self.assertIn(
            "vkCmdTraceRaysKHR output copied to scene color; shading=%s",
            trace,
        )
        self.assertIn("qboolean vk_rt_trace_frame( void );", self.vk_header)

    def test_masked_geometry_uses_any_hit_for_primary_and_shadow_rays(self) -> None:
        build_script = read_text("code/rendererrtx/shaders/build_shaders.py")
        any_hit = read_text("code/rendererrtx/shaders/rt_main.rahit")
        raygen = read_text("code/rendererrtx/shaders/rt_main.rgen")
        closest_hit = read_text("code/rendererrtx/shaders/rt_main.rchit")

        self.assertIn('"rahit"', build_script)
        self.assertRegex(
            any_hit,
            r"RTX_RT_MATFLAG_ALPHA_LT.*?\?\s*alpha >= cutoff\s*:\s*alpha < cutoff",
        )
        self.assertIn("texture(u_sceneTextures[nonuniformEXT(textureIndex)], uv).a", any_hit)
        self.assertIn("ignoreIntersectionEXT;", any_hit)
        self.assertNotIn("gl_RayFlagsOpaqueEXT", raygen)
        self.assertNotIn("gl_RayFlagsOpaqueEXT", closest_hit)
        self.assertIn(
            "( stage->stateBits & GLS_ATEST_BITS ) == GLS_ATEST_LT_80",
            self.vk,
        )
        self.assertIn("material->flags |= RTX_RT_MATFLAG_ALPHA_LT", self.vk)

        pipeline = source_section(
            self.vk,
            "static qboolean vk_rt_ensure_pipeline( void )\n{",
            "static qboolean vk_rt_update_descriptor_set( void )",
        )
        self.assertIn("VkPipelineShaderStageCreateInfo stages[5]", pipeline)
        self.assertIn("VK_SHADER_STAGE_ANY_HIT_BIT_KHR", pipeline)
        self.assertIn("stages[4].module = vk.modules.rt_rahit", pipeline)
        self.assertIn("groups[3].anyHitShader = 4", pipeline)

        descriptor_layout = source_section(
            self.vk,
            "static qboolean vk_rt_ensure_descriptor_resources( void )\n{",
            "static void vk_rt_destroy_output_image",
        )
        self.assertGreaterEqual(
            descriptor_layout.count("VK_SHADER_STAGE_ANY_HIT_BIT_KHR"),
            7,
        )

        query_geometry = source_section(
            self.vk,
            "static VkDeviceSize vk_rt_query_triangles_build_bytes"
            "( uint32_t vertexCount, uint32_t indexCount, "
            "qboolean opaqueGeometry, "
            "VkBuildAccelerationStructureFlagsKHR buildFlags )\n{",
            "static VkDeviceSize vk_rt_query_tlas_build_bytes",
        )
        build_geometry = source_section(
            self.vk,
            "static qboolean vk_rt_build_triangles_blas"
            "( rtxVkRtAccelerationStructure_t *outAs, "
            "const rtxVkRtBuffer_t *vertexBuffer, uint32_t vertexCount, "
            "VkDeviceSize vertexStride, const rtxVkRtBuffer_t *indexBuffer, "
            "uint32_t indexCount, qboolean opaqueGeometry, "
            "qboolean allowCompaction, "
            "const char *debugName )\n{",
            "static qboolean vk_rt_append_md3_entity_geometry",
        )
        for geometry_path in (query_geometry, build_geometry):
            self.assertIn(
                "geometry.flags = opaqueGeometry ? VK_GEOMETRY_OPAQUE_BIT_KHR : 0;",
                geometry_path,
            )

        reflection = json.loads(
            read_text("code/rendererrtx/shaders/spirv/shader_reflection.json")
        )
        any_hit_entry = next(
            entry for entry in reflection["shaders"]
            if entry["source"] == "rt_main.rahit"
        )
        self.assertEqual(any_hit_entry["stage"], "rahit")
        self.assertIn(
            "const unsigned char rt_main_rahit_spv[",
            read_text("code/rendererrtx/shaders/spirv/shader_data.c"),
        )

    def test_native_material_ownership_is_conservative_and_overlay_geometry_still_occludes(
        self,
    ) -> None:
        any_hit = read_text("code/rendererrtx/shaders/rt_main.rahit")
        native_predicate = source_section(
            self.shader,
            "qboolean R_RtShaderNativeSupported( const shader_t *shader )",
            "/*\n==================\nR_FindShaderByName",
        )
        for unsupported_semantic in (
            "shader->remappedShader",
            "shader->polygonOffset",
            "shader->numDeforms != 0",
            "shader->hasScreenMap",
            "shader->numUnfoggedPasses != 1",
            "bundle->numImageAnimations > 1",
            "bundle->numTexMods != 0",
            "bundle->isVideoMap",
            "bundle->isScreenMap",
        ):
            with self.subTest(unsupported_semantic=unsupported_semantic):
                self.assertIn(unsupported_semantic, native_predicate)
        self.assertIn("baseBundleCount == 1", native_predicate)
        self.assertIn("lightmapBundleCount <= 1", native_predicate)

        material_translation = source_section(
            self.vk,
            "static void vk_rt_translate_shader_to_material",
            "static qboolean vk_rt_cpu_geometry_find_or_add_material_ex",
        )
        self.assertIn("bundleCount = stage->numTexBundles;", material_translation)
        self.assertIn("bundleIndex < bundleCount", material_translation)
        self.assertIn("bundle->tcGen == TCGEN_LIGHTMAP", material_translation)
        self.assertIn("if ( !albedoImage && image && !lightmap )", material_translation)
        self.assertIn("shader = shader->remappedShader;", material_translation)

        world_extraction = source_section(
            self.vk,
            "static qboolean vk_rt_extract_world_geometry"
            "( rtxRtCpuGeometry_t *geometry )\n{",
            "static qboolean vk_rt_build_triangles_blas",
        )
        self.assertIn("!R_RtShaderNativeSupported( shader )", world_extraction)
        self.assertIn("RTX_RT_MATFLAG_RASTER_OVERLAY", world_extraction)

        self.assertIn("gl_IncomingRayFlagsEXT", any_hit)
        self.assertIn("gl_RayFlagsSkipClosestHitShaderEXT", any_hit)
        self.assertIn("if (!shadowRay)", any_hit)
        self.assertIn("ignoreIntersectionEXT;", any_hit)
        self.assertIn("RTX_RT_MATFLAG_RASTER_OVERLAY", any_hit)

        dynamic_extraction = source_section(
            self.vk,
            "static qboolean vk_rt_extract_dynamic_geometry"
            "( rtxRtCpuGeometry_t *geometry )\n{",
            "static qboolean vk_rt_build_dynamic_scene_blas",
        )
        self.assertIn(
            "geometry->materials[i].flags |= RTX_RT_MATFLAG_RASTER_OVERLAY",
            dynamic_extraction,
        )
        self.assertIn(
            "geometry->anyHitTriangleCount = geometry->sourceTriangleCount",
            dynamic_extraction,
        )

    def test_rt_culling_map_cache_and_live_resource_changes_are_coherent(self) -> None:
        any_hit = read_text("code/rendererrtx/shaders/rt_main.rahit")
        self.assertIn("RTX_RT_MATFLAG_CULL_FRONT", any_hit)
        self.assertIn("RTX_RT_MATFLAG_CULL_BACK", any_hit)
        self.assertIn("gl_HitKindFrontFacingTriangleEXT", any_hit)

        material_translation = source_section(
            self.vk,
            "static void vk_rt_translate_shader_to_material",
            "static qboolean vk_rt_cpu_geometry_find_or_add_material_ex",
        )
        self.assertIn("shader->cullType == CT_TWO_SIDED", material_translation)
        self.assertIn("shader->cullType == CT_BACK_SIDED", material_translation)
        self.assertIn("RTX_RT_MATFLAG_CULL_FRONT", material_translation)
        self.assertIn("RTX_RT_MATFLAG_CULL_BACK", material_translation)

        instances = source_section(
            self.vk,
            "static uint32_t vk_rt_collect_instances",
            "static qboolean vk_rt_build_tlas",
        )
        self.assertGreaterEqual(
            instances.count("VK_GEOMETRY_INSTANCE_TRIANGLE_FLIP_FACING_BIT_KHR"),
            2,
        )
        self.assertGreaterEqual(
            instances.count(
                "VK_GEOMETRY_INSTANCE_TRIANGLE_FACING_CULL_DISABLE_BIT_KHR"
            ),
            2,
        )

        cached_changes = source_section(
            self.vk,
            "static qboolean vk_rt_consume_cvar_modified( cvar_t *cvar )\n{",
            "static qboolean vk_rt_cpu_geometry_find_or_add_material"
            "( rtxRtCpuGeometry_t *geometry",
        )
        for cvar_name in (
            "rtx_rt_masked_mode",
            "rtx_rt_masked_cutoff",
            "rtx_rt_material_override",
            "rtx_rt_material_roughness_override",
            "rtx_rt_material_metallic_override",
            "rtx_rt_material_emissive_override",
            "rtx_rt_emissive_scale",
            "rtx_rt_emissive_keyword_boost",
            "rtx_rt_world_light_scale",
        ):
            with self.subTest(cvar_name=cvar_name):
                self.assertIn(cvar_name, cached_changes)
        self.assertIn(
            'vk_rt_invalidate( "RT material/geometry configuration changed" )',
            cached_changes,
        )
        self.assertIn("vk_rt_reset_world_light_cache();", cached_changes)

        invalidation = source_section(
            self.vk,
            "void vk_rt_invalidate( const char *reason )",
            "static void vk_rt_shutdown",
        )
        self.assertIn("vk_rt_reset_world_light_cache();", invalidation)
        self.assertIn("vk.rt.world_masked_triangle_count = 0;", invalidation)
        self.assertIn("vk.rt.dynamic_masked_triangle_count = 0;", invalidation)
        self.assertIn("vk.rt.stats.masked_triangles = 0;", invalidation)

        remap = source_section(
            self.shader,
            "void RE_RemapShader",
            "/*\n===============\nParseVector",
        )
        self.assertIn('vk_rt_invalidate( "shader remap" );', remap)

    def test_frame_mutable_buffers_and_history_replacement_are_synchronized(self) -> None:
        self.assertRegex(
            self.vk_header,
            r"light_buffer\s*\[\s*NUM_COMMAND_BUFFERS\s*\]",
        )
        self.assertRegex(
            self.vk_header,
            r"temporal_params_buffer\s*\[\s*NUM_COMMAND_BUFFERS\s*\]",
        )

        descriptors = source_section(
            self.vk,
            "static qboolean vk_rt_update_descriptor_set( void )\n{",
            "static qboolean vk_rt_ensure_dynamic_blas",
        )
        self.assertIn("vk.cmd_index % NUM_COMMAND_BUFFERS", descriptors)
        self.assertIn("light_buffer[descriptorIndex]", descriptors)
        self.assertIn("temporal_params_buffer[descriptorIndex]", descriptors)

        output_resize = source_section(
            self.vk,
            "static qboolean vk_rt_ensure_output_image( void )\n{",
            "static qboolean vk_rt_ensure_pipeline( void )",
        )
        wait = output_resize.index('vk_rt_wait_for_inflight_frames( "RT output resize" )')
        destroy = output_resize.index("vk_rt_destroy_output_image();", wait)
        self.assertLess(wait, destroy)

        dynamic_upload = source_section(
            self.vk,
            "static qboolean vk_rt_build_dynamic_scene_blas"
            "( VkDeviceSize *frameBudgetBytesUsed, VkDeviceSize frameBudgetBytes, "
            "VkDeviceSize *outBuildBytes )\n{",
            "static qboolean vk_rt_ensure_descriptor_resources",
        )
        wait = dynamic_upload.index(
            'vk_rt_wait_for_inflight_frames( "dynamic geometry upload" )'
        )
        first_upload = dynamic_upload.index("vk_rt_upload_buffer_data(", wait)
        self.assertLess(wait, first_upload)

        trace = source_section(
            self.vk,
            "qboolean vk_rt_trace_frame( void )\n{",
            "static const char *vk_capability_value",
        )
        self.assertIn("VkImageMemoryBarrier traceBarriers[3]", trace)
        self.assertIn("vk.rt.history_image[historyReadIndex]", trace)
        self.assertIn("vk.rt.history_image[historyWriteIndex]", trace)
        self.assertIn("VK_ACCESS_SHADER_READ_BIT", trace)
        self.assertIn("VK_ACCESS_SHADER_WRITE_BIT", trace)

        main_descriptor_bind = source_section(
            self.vk,
            "void vk_bind_descriptor_sets( void )",
            "void vk_bind_pipeline",
        )
        self.assertIn("i <= end", main_descriptor_bind)

    def test_upload_semaphore_waits_cover_transfer_and_ray_consumers(self) -> None:
        immediate_submit = source_section(
            self.vk,
            "static qboolean end_command_buffer_internal",
            "static void end_command_buffer(",
        )
        staging_submit = source_section(
            self.vk,
            "static void vk_submit_staging_buffer( qboolean final )",
            "static void ensure_staging_buffer_allocation",
        )
        frame_submit = source_section(
            self.vk,
            "void vk_end_frame( void )",
            "void vk_present_frame( void )",
        )

        self.assertIn(
            "wait_dst_stage_mask = VK_PIPELINE_STAGE_ALL_COMMANDS_BIT",
            immediate_submit,
        )
        self.assertIn(
            "wait_dst_stage_mask = VK_PIPELINE_STAGE_ALL_COMMANDS_BIT",
            staging_submit,
        )
        self.assertRegex(
            frame_submit,
            r"wait_dst_stage_mask\[2\]\s*=\s*\{\s*"
            r"VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,\s*"
            r"VK_PIPELINE_STAGE_ALL_COMMANDS_BIT",
        )

    def test_keep_context_restart_rebuilds_binary_upload_sync(self) -> None:
        release = source_section(
            self.vk,
            "void vk_release_resources( refShutdownCode_t code )",
            "#if 0",
        )

        self.assertIn("if ( code == REF_KEEP_CONTEXT )", release)
        wait = release.index("vk_wait_staging_buffer();")
        reset = release.index(
            "qvkResetCommandBuffer( vk.staging_command_buffer, 0 )",
            wait,
        )
        destroy = release.index("vk_destroy_sync_primitives();", reset)
        create = release.index("vk_create_sync_primitives();", destroy)
        self.assertLess(wait, reset)
        self.assertLess(reset, destroy)
        self.assertLess(destroy, create)
        self.assertIn(
            "vk_release_resources( code );",
            self.init,
        )
        self.assertIn(
            "void vk_release_resources( refShutdownCode_t code );",
            self.vk_header,
        )

    def test_capability_and_copy_paths_gate_features_limits_and_formats(self) -> None:
        feature_query = source_section(
            self.vk,
            "static qboolean vk_query_rt_device_features(",
            "static qboolean vk_create_device",
        )
        for feature in (
            "bufferDeviceAddressFeatures.bufferDeviceAddress",
            "descriptorIndexingFeatures.shaderSampledImageArrayNonUniformIndexing",
            "accelerationStructureFeatures.accelerationStructure",
            "rayQueryFeatures.rayQuery",
            "rayTracingPipelineFeatures.rayTracingPipeline",
        ):
            with self.subTest(feature=feature):
                self.assertIn(feature, feature_query)
        self.assertIn("qvkGetPhysicalDeviceFeatures2( physical_device, &features2 )", feature_query)
        self.assertIn(
            "qvkGetPhysicalDeviceFeatures2KHR( physical_device, &features2 )",
            feature_query,
        )

        device_gate = source_section(
            self.vk,
            "static qboolean vk_create_device",
            "static void vk_destroy_instance",
        )
        self.assertIn(
            "devAddrFeat = ( devAddrFeat && bufferDeviceAddressFeature )",
            device_gate,
        )
        self.assertIn(
            "rayTracingPipeline = ( rayTracingPipeline && rayTracingPipelineFeature )",
            device_gate,
        )
        self.assertIn("maxPushConstantsSize < sizeof( rtxRtPushConstants_t )", device_gate)
        self.assertIn("maxPerStageDescriptorSampledImages", device_gate)
        self.assertIn("maxDescriptorSetSamplers", device_gate)
        self.assertIn("maxPerStageDescriptorStorageBuffers < 8", device_gate)
        self.assertIn("maxPerStageDescriptorStorageImages < 3", device_gate)
        self.assertIn("maxPerStageResources", device_gate)
        self.assertIn("maxRayRecursionDepth < 2", device_gate)
        self.assertIn(
            "maxPerStageDescriptorAccelerationStructures < 1",
            device_gate,
        )
        self.assertIn("qvkGetPhysicalDeviceProperties2KHR", device_gate)
        self.assertIn("rayTraversalPrimitiveCulling = VK_FALSE", device_gate)
        self.assertIn("VK_FORMAT_FEATURE_STORAGE_IMAGE_BIT", device_gate)
        self.assertIn("VK_FORMAT_FEATURE_TRANSFER_SRC_BIT", device_gate)
        self.assertIn("rgba16f storage/blit format support", device_gate)

        format_gate = source_section(
            self.vk,
            "static qboolean vk_rt_supports_reconstruction_blit( void )",
            "static qboolean vk_rt_ensure_timing_query_pool",
        )
        self.assertIn("VK_FORMAT_FEATURE_BLIT_SRC_BIT", format_gate)
        self.assertIn("VK_FORMAT_FEATURE_BLIT_DST_BIT", format_gate)
        self.assertIn("VK_FORMAT_FEATURE_SAMPLED_IMAGE_FILTER_LINEAR_BIT", format_gate)

        trace = source_section(
            self.vk,
            "qboolean vk_rt_trace_frame( void )\n{",
            "static const char *vk_capability_value",
        )
        self.assertIn("needsFormatConversion", trace)
        self.assertIn("vk_rt_supports_reconstruction_blit()", trace)
        self.assertIn("else if ( !needsBlit )", trace)
        self.assertIn("preserving the complete raster frame", trace)
        self.assertNotIn("MIN( vk.rt.output_width", trace)

    def test_native_rt_is_default_and_authored_raster_bridge_is_opt_in(self) -> None:
        raygen = read_text("code/rendererrtx/shaders/rt_main.rgen")
        closest_hit = read_text("code/rendererrtx/shaders/rt_main.rchit")
        miss = read_text("code/rendererrtx/shaders/rt_main.rmiss")

        self.assertRegex(
            self.init,
            r'ri\.Cvar_Get\(\s*"rtx_rt_legacy_color_compat",\s*"1"',
        )
        self.assertRegex(
            self.init,
            r'ri\.Cvar_Get\(\s*"rtx_rt_raster_reference",\s*"0"',
        )
        compat_helper = source_section(
            self.vk,
            "static qboolean vk_rt_raster_reference_enabled( void )",
            "static float vk_rt_world_light_scale",
        )
        self.assertIn("return qfalse;", compat_helper)
        self.assertIn(
            "return max(rtColor * max(u_temporal.legacyColorParams.y, 0.0)",
            raygen,
        )
        self.assertIn("rasterReference = texture(u_sceneColor, uv).rgb;", raygen)
        self.assertIn("rasterReference * resolvedShadow", raygen)
        self.assertIn("highlights * (0.25 * contributionStrength)", raygen)
        self.assertIn("center.shadowFactor", raygen)
        self.assertIn("float shadowFactor;", raygen)
        self.assertIn("float shadowFactor;", closest_hit)
        self.assertIn("float shadowFactor;", miss)
        self.assertIn("float shadowResponse;", raygen)
        self.assertIn("float shadowResponse;", closest_hit)
        self.assertIn("float shadowResponse;", miss)
        self.assertIn("vec3 shadowLoss;", raygen)
        self.assertIn("vec3 shadowLoss;", closest_hit)
        self.assertIn("vec3 shadowLoss;", miss)
        self.assertIn(
            "contributionStrength * clamp(shadowResponse, 0.0, 1.0)",
            raygen,
        )
        self.assertIn(
            "(materialFlags & RTX_RT_MATFLAG_EMISSIVE) != 0u ? 0.0 : 1.0",
            closest_hit,
        )
        self.assertNotIn("u_sceneColor", closest_hit)
        self.assertIn("Lo += evaluate_environment(N)", closest_hit)
        self.assertIn("albedo * (1.0 - metallic)", closest_hit)
        self.assertIn("pc.indirectStrength", closest_hit)
        self.assertIn("environmentDiffuseVisibility", closest_hit)
        self.assertIn("environmentSpecularVisibility", closest_hit)
        self.assertIn("trace_shadow_visibility(", closest_hit)
        self.assertRegex(
            self.init,
            r'ri\.Cvar_Get\(\s*"rtx_rt_indirect_strength",\s*"0\.35"',
        )
        self.assertGreaterEqual(raygen.count("center.shadowResponse"), 2)
        self.assertGreaterEqual(raygen.count("center.shadowLoss"), 2)
        self.assertIn(
            "payloadRadiance.shadowFactor = clamp("
            "visibleShadowWeight / shadowWeightTotal",
            closest_hit,
        )
        self.assertIn("L = normalize(light.directionSoftness.xyz);", closest_hit)
        self.assertIn("RTX_RT_MODE_FLAG_RASTER_REFERENCE", closest_hit)
        self.assertRegex(
            closest_hit,
            r"rasterReferenceCompat\s*\?\s*0u\s*:\s*pc\.frameIndex",
        )
        stable_shadow_seed = re.search(
            r"uint shadowSeed = rasterReferenceCompat \?\s*(.*?)\s*:\s*seed;",
            closest_hit,
            re.DOTALL,
        )
        self.assertIsNotNone(stable_shadow_seed)
        stable_shadow_branch = stable_shadow_seed.group(1)
        self.assertIn("stableGeometrySeed", stable_shadow_branch)
        self.assertIn("lightIndex", stable_shadow_branch)
        self.assertNotIn("frameIndex", stable_shadow_branch)
        self.assertNotIn("gl_HitTEXT", stable_shadow_branch)
        self.assertNotIn("worldPos", stable_shadow_branch)
        self.assertIn(
            "shadowDir0 = sample_cone(L, coneAngle, shadowSeed);",
            closest_hit,
        )
        self.assertIn(
            "shadowDir1 = sample_cone(L, coneAngle, shadowSeed);",
            closest_hit,
        )
        self.assertIn("if (!rasterReferenceCompat)", closest_hit)
        self.assertIn("seed = shadowSeed;", closest_hit)

        light_update = source_section(
            self.vk,
            "static qboolean vk_rt_update_light_buffer( void )\n{",
            "static void vk_rt_destroy_as",
        )
        self.assertIn(
            "qboolean rasterReference = vk_rt_raster_reference_enabled();",
            light_update,
        )
        self.assertIn("qboolean shadowOnly = rasterReference;", light_update)
        self.assertIn("RTX_RT_LIGHT_FLAG_CASTS_SHADOWS", light_update)
        self.assertIn("RTX_RT_LIGHT_FLAG_SHADOW_ONLY", light_update)
        self.assertRegex(
            self.init,
            r'ri\.Cvar_Get\(\s*"rtx_rt_world_light_scale",\s*"0\.35"',
        )

        backend_draw = source_section(
            self.backend,
            "static const void *RB_DrawSurfs",
            "static const void *RB_DrawBuffer",
        )
        base_lights = backend_draw.index(
            "RB_LightingPass( RB_DRAWSURFS_RT_BASE, qfalse )"
        )
        trace = backend_draw.index("rtTraceCompleted = vk_rt_trace_frame();")
        overlay = backend_draw.index("RB_DRAWSURFS_RT_OVERLAY", trace)
        self.assertLess(base_lights, trace)
        self.assertLess(trace, overlay)
        self.assertIn(
            "!rasterOwnsRtBaseLights && !rtTraceCompleted",
            backend_draw,
        )
        self.assertIn("requiredPrimaryTrace =", backend_draw)
        self.assertIn(
            "rtx_rt_require && rtx_rt_require->integer",
            backend_draw,
        )
        self.assertIn(
            "if ( requiredPrimaryTrace && !rtTraceCompleted )",
            backend_draw,
        )
        self.assertIn(
            "refusing silent raster fallback",
            backend_draw,
        )
        self.assertIn(
            "rtComposition ? RB_DRAWSURFS_RT_OVERLAY : RB_DRAWSURFS_ALL",
            backend_draw,
        )

    def test_ray_tracing_mode_disables_incompatible_raster_msaa(self) -> None:
        msaa_selection = source_section(
            self.vk,
            "vk_set_render_scale();\n\n\tif ( r_fbo->integer ) {",
            "// multisampling",
        )
        self.assertIn(
            "vk.caps.activeRtMode == RTX_RT_MODE_RAY_TRACING_PIPELINE",
            msaa_selection,
        )
        self.assertIn("!singleSampleComposition", msaa_selection)
        self.assertIn("singleSampleComposition", msaa_selection)
        self.assertIn("disabling raster MSAA", msaa_selection)

        sample_selection = source_section(
            self.vk,
            "// multisampling",
            "vk.screenMapSamples =",
        )
        self.assertIn("if ( /*vk.fboActive &&*/ vk.msaaActive )", sample_selection)
        self.assertIn("vkSamples = VK_SAMPLE_COUNT_1_BIT", sample_selection)

    def test_fov_first_person_and_liquid_feed_match_public_contracts(self) -> None:
        scene = read_text("code/rendererrtx/tr_scene.c")
        main = read_text("code/rendererrtx/tr_main.c")

        self.assertRegex(
            self.init,
            r'ri\.Cvar_Get\(\s*"r_fovCorrection",\s*"1"',
        )
        self.assertIn("R_ApplyViewportFovCorrection", scene)
        self.assertIn("RDF_NOFOVCORRECTION", scene)
        self.assertIn("RDF_NOFIRSTPERSON", main)
        self.assertIn("RDF_NOFIRSTPERSON", self.vk)

        self.assertIn("void RE_AddLiquidInteractionToScene", scene)
        self.assertIn("R_CopyLiquidInteractionsToRefdef", scene)
        self.assertIn(
            "re.AddLiquidInteractionToScene = RE_AddLiquidInteractionToScene",
            self.init,
        )
        self.assertIn("liquidInteraction_t liquidInteractions", self.local_header)

    def test_static_map_light_sidecars_feed_raster_and_full_rt_lighting(self) -> None:
        bsp = read_text("code/rendererrtx/tr_bsp.c")
        scene = read_text("code/rendererrtx/tr_scene.c")
        world = read_text("code/rendererrtx/tr_world.c")

        self.assertIn("#define MAX_STATIC_MAP_LIGHTS 128", self.local_header)
        self.assertIn("mapLightDef_t lights[MAX_STATIC_MAP_LIGHTS]", self.local_header)
        self.assertIn("staticMapLights_t\t\tstaticMapLights;", self.local_header)

        self.assertRegex(
            self.init,
            r'ri\.Cvar_Get\(\s*"r_staticLights",\s*"1",\s*CVAR_ARCHIVE_ND\s*\)',
        )
        self.assertRegex(
            self.init,
            r'ri\.Cvar_Get\(\s*"r_staticLightMaxLights",\s*"8",\s*CVAR_ARCHIVE_ND\s*\)',
        )
        self.assertIn(
            'ri.Cmd_AddCommand( "r_staticLightReload", R_StaticMapLightsReload_f );',
            self.init,
        )
        self.assertIn(
            'ri.Cmd_RemoveCommand( "r_staticLightReload" );',
            self.init,
        )
        self.assertNotIn("r_staticLightShadows", self.init)
        self.assertNotIn("r_staticLightShadowMaxLights", self.init)

        for helper in (
            "qboolean R_PointLeafClusterArea",
            "qboolean R_LeafClusterInCurrentPVS",
            "qboolean R_PointInCurrentPVS",
        ):
            with self.subTest(helper=helper):
                self.assertIn(helper, world)

        loader = source_section(
            bsp,
            "static void R_LoadStaticMapLightsForWorld",
            "void R_StaticMapLightsReload_f",
        )
        self.assertIn('"maps/%s.lights.json"', loader)
        self.assertIn("R_ParseStaticMapLights", loader)
        self.assertIn("tr.staticMapLights.parseFailed = qtrue;", loader)

        world_load = source_section(
            bsp,
            "void RE_LoadWorldMap( const char *name ) {",
            "\n}",
        )
        world_assignment = world_load.index("tr.world = &s_worldData;")
        global_fog_load = world_load.index("R_LoadGlobalFogForWorld();", world_assignment)
        static_light_load = world_load.index(
            "R_LoadStaticMapLightsForWorld();", global_fog_load
        )
        self.assertLess(world_assignment, global_fog_load)
        self.assertLess(global_fog_load, static_light_load)

        promotion = source_section(
            scene,
            "static void R_AddStaticMapLightsToScene",
            "\n\n\n/*\n=====================\nRE_AddLightToScene",
        )
        self.assertIn("R_StaticMapLightVisibleInPVS", promotion)
        self.assertIn("r_staticLightMaxLights", promotion)
        self.assertIn("selected[MAX_STATIC_MAP_LIGHTS]", promotion)
        self.assertIn("RE_AddDynamicLightToScene", promotion)
        self.assertIn("RE_AddLinearLightToScene", promotion)
        self.assertNotIn("R_ResetStaticMapLightFrameCounters();", promotion)
        self.assertIn(
            "tr.staticMapLights.skippedDisabledThisFrame += tr.staticMapLights.count;",
            promotion,
        )
        self.assertIn(
            "tr.staticMapLights.skippedBudgetThisFrame +=",
            promotion,
        )
        self.assertNotIn("shadowEligible", promotion)
        self.assertNotIn("shadowAtlas", promotion)

        next_frame = source_section(
            scene,
            "void R_InitNextFrame( void )",
            "\n}\n\n\n/*\n====================\nRE_ClearScene",
        )
        self.assertIn("R_ResetStaticMapLightFrameCounters();", next_frame)

        render_scene = source_section(
            scene,
            "void RE_RenderScene( const refdef_t *fd )",
            "tr.frontEndMsec += ri.Milliseconds() - startTime;",
        )
        promote = render_scene.index("R_AddStaticMapLightsToScene( fd );")
        snapshot = render_scene.index("tr.refdef.num_dlights =")
        self.assertLess(promote, snapshot)

        light_update = source_section(
            self.vk,
            "static qboolean vk_rt_update_light_buffer( void )\n{",
            "static void vk_rt_destroy_as",
        )
        self.assertIn("dst->colorType[3] = dl->linear ? 2.0f : 0.0f;", light_update)
        self.assertIn(
            "dst->directionSoftness[0] = dl->linear ? dl->origin2[0] : 0.0f;",
            light_update,
        )
        self.assertIn("dl->castsRtShadows", light_update)

        self.assertIn("static lights file:%s loaded:%i parsefail:%i", self.commands)

    def test_picmip_filter_matches_the_vulkan_shader_category_contract(self) -> None:
        self.assertRegex(
            self.init,
            r'ri\.Cvar_Get\(\s*"r_picmipFilter",\s*"1",\s*'
            r"CVAR_ARCHIVE\s*\|\s*CVAR_LATCH\s*\)",
        )
        self.assertIn(
            'ri.Cvar_CheckRange( r_picmipFilter, "0", "15", CV_INTEGER );',
            self.init,
        )
        self.assertIn("extern\tcvar_t\t*r_picmipFilter;", self.local_header)

        filter_helpers = source_section(
            self.shader,
            "#define PICMIP_FILTER_TEXTURES",
            "void RE_RemapShader",
        )
        for category, path in (
            ("PICMIP_FILTER_TEXTURES", '"textures"'),
            ("PICMIP_FILTER_MODELS", '"models"'),
            ("PICMIP_FILTER_SPRITES", '"sprites"'),
            ("PICMIP_FILTER_2D", '"gfx"'),
        ):
            with self.subTest(category=category):
                self.assertIn(category, filter_helpers)
                self.assertIn(path, filter_helpers)
        for ui_path in ('"icons"', '"menu"', '"ui"', '"fonts"'):
            self.assertIn(ui_path, filter_helpers)
        self.assertIn("if ( filter <= 0 )", filter_helpers)
        self.assertIn("shader.noPicMip = qtrue;", filter_helpers)

        init_shader = source_section(
            self.shader,
            "static void InitShader( const char *name, int lightmapIndex )",
            "static void DetectNeeds",
        )
        name_copy = init_shader.index("Q_strncpyz( shader.name")
        apply_filter = init_shader.index("R_ApplyShaderPicMipFilter();")
        self.assertLess(name_copy, apply_filter)

        sky = source_section(
            self.shader,
            "static void ParseSkyParms",
            "static void ParseSort",
        )
        self.assertIn("imgFlags_t imgFlags = IMGFLAG_MIPMAP;", sky)
        self.assertIn("if ( !shader.noPicMip )", sky)
        self.assertIn("imgFlags |= IMGFLAG_PICMIP;", sky)

        implicit_image = source_section(
            self.shader,
            "shader_t *R_FindShader(",
            "qhandle_t RE_RegisterShaderFromImage",
        )
        self.assertIn("flags |= IMGFLAG_MIPMAP;", implicit_image)
        self.assertIn("if ( !shader.noPicMip )", implicit_image)
        self.assertNotIn(
            "flags |= IMGFLAG_MIPMAP | IMGFLAG_PICMIP;",
            implicit_image,
        )

    def test_levelshots_use_configurable_viewport_resampling(self) -> None:
        expected_defaults = {
            "r_levelshotSize": "",
            "r_levelshotDownscale": "1",
            "r_levelshotSourceAspect": "",
        }
        for name, default in expected_defaults.items():
            with self.subTest(cvar=name):
                self.assertRegex(
                    self.init,
                    rf'ri\.Cvar_Get\(\s*"{name}",\s*"{re.escape(default)}"',
                )

        helpers = source_section(
            self.init,
            "typedef struct {\n\tint sourceX;",
            "static void R_SetCaptureActive",
        )
        self.assertIn("params->sourceWidth = viewportWidth;", helpers)
        self.assertIn("params->sourceHeight = viewportHeight;", helpers)
        self.assertIn("R_ParseLevelshotAspect", helpers)
        self.assertIn("R_GetLevelshotCenteredRect", helpers)
        self.assertIn("R_ParseLevelshotSize", helpers)
        self.assertIn("r_levelshotDownscale->value", helpers)
        self.assertIn("R_ResampleLevelshot", helpers)

        capture = source_section(
            self.init,
            "void RB_TakeLevelShot( void )",
            "static void R_ScheduleLevelShot",
        )
        self.assertIn(
            "R_ResolveLevelshotParams( gls.captureWidth, gls.captureHeight, &params );",
            capture,
        )
        self.assertIn(
            "R_ResampleLevelshot( source, gls.captureWidth, padlen, &params, rgb );",
            capture,
        )
        self.assertIn("buffer[13] = params.outputWidth >> 8;", capture)
        self.assertIn("buffer[15] = params.outputHeight >> 8;", capture)
        self.assertNotIn("128 * 128", capture)

        self.assertIn("qboolean levelshotPending;", self.local_header)
        self.assertIn("void RB_TakeLevelShot( void );", self.local_header)

    def test_levelshot_capture_is_deferred_until_hud_and_weapon_are_hidden(self) -> None:
        client_main = read_text("code/client/cl_main.cpp")
        client_hud = read_text("code/client/cl_hud.cpp")
        client_cgame = read_text("code/client/cl_cgame.cpp")

        schedule = source_section(
            self.init,
            "static void R_ScheduleLevelShot( void )",
            "/*\n==================\nR_ScreenShot_f",
        )
        pending = schedule.index("backEnd.levelshotPending = qtrue;")
        capture_active = schedule.index("R_SetCaptureActive( qtrue );")
        self.assertLess(pending, capture_active)

        screenshot = source_section(
            self.init,
            "static void R_ScreenShot_f( void )",
            "static void GfxInfo_f( void )",
        )
        self.assertIn("R_ScheduleLevelShot();", screenshot)
        self.assertNotIn("RB_TakeLevelShot();", screenshot)

        issue = source_section(
            self.commands,
            "static void R_IssueRenderCommands( void )",
            "R_GetCommandBufferReserved",
        )
        self.assertIn(
            "backEnd.screenshotMask == 0 && !backEnd.levelshotPending",
            issue,
        )
        self.assertIn("backEnd.levelshotPending = qfalse;", issue)
        self.assertIn('ri.Cvar_Set( "cl_captureActive", "0" );', issue)

        swap = source_section(
            self.backend,
            "static const void *RB_SwapBuffers",
            "RB_ExecuteRenderCommands",
        )
        self.assertIn(
            "backEnd.screenshotMask || backEnd.levelshotPending",
            swap,
        )
        take = swap.index("RB_TakeLevelShot();")
        clear_pending = swap.index("backEnd.levelshotPending = qfalse;", take)
        clear_capture = swap.index('ri.Cvar_Set( "cl_captureActive", "0" );')
        self.assertLess(take, clear_pending)
        self.assertLess(clear_pending, clear_capture)

        self.assertIn(
            'Cvar_Get( "r_levelshotHideHud", "1"',
            client_main,
        )
        self.assertIn("cl_captureActive->integer", client_hud)
        self.assertIn("cl_captureActive->integer", client_cgame)

    def test_screenshot_aliases_and_menu_dof_match_the_renderer_contract(self) -> None:
        vk_init = read_text("code/renderervk/tr_init.c")
        core_commands = {
            "screenshot",
            "screenshotPNG",
            "screenshotTGA",
            "screenshotJPEG",
            "screenshotBMP",
        }

        def registered_core_commands(source: str) -> set[str]:
            return {
                command
                for command in re.findall(
                    r'ri\.Cmd_AddCommand\(\s*"(screenshot[^"]*)"', source
                )
                if command in core_commands
            }

        self.assertEqual(registered_core_commands(self.init), core_commands)
        self.assertEqual(
            registered_core_commands(self.init),
            registered_core_commands(vk_init),
        )

        screenshot = source_section(
            self.init,
            "static void R_ScreenShot_f( void )",
            "static void GfxInfo_f( void )",
        )
        self.assertIn("typeMask = SCREENSHOT_PNG", screenshot)
        self.assertIn('ext = "png"', screenshot)
        self.assertIn("backEnd.screenshotPNG", screenshot)
        self.assertIn("R_SavePNG(", self.init)
        self.assertIn("RB_TakeScreenshotPNG", self.backend)

        self.assertIn("void RE_DrawMenuDepthOfField( float amount )", self.commands)
        self.assertIn(
            "re.DrawMenuDepthOfField = RE_DrawMenuDepthOfField",
            self.init,
        )
        self.assertIn(
            "void RE_DrawMenuDepthOfField( float amount );",
            self.local_header,
        )

    def test_win32_display_output_query_is_outside_the_opengl_guard(self) -> None:
        win_glimp = read_text("code/win32/win_glimp.cpp")
        query = win_glimp.index("void GLimp_QueryDisplayOutput")
        opengl_guard = win_glimp.index(
            "#ifdef USE_OPENGL_API\n/*\n** GLW_LoadOpenGL"
        )
        self.assertLess(query, opengl_guard)


if __name__ == "__main__":
    unittest.main()

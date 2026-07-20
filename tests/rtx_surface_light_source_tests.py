import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def source_section(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


class RtxSurfaceLightSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.header = read_text("code/rendererrtx/tr_local.h")
        cls.shader = read_text("code/rendererrtx/tr_shader.c")
        cls.image = read_text("code/rendererrtx/tr_image.c")
        cls.bsp = read_text("code/rendererrtx/tr_bsp.c")
        cls.scene = read_text("code/rendererrtx/tr_scene.c")
        cls.init = read_text("code/rendererrtx/tr_init.c")
        cls.commands = read_text("code/rendererrtx/tr_cmds.c")
        cls.vk = read_text("code/rendererrtx/vk.c")
        cls.closest_hit = read_text("code/rendererrtx/shaders/rt_main.rchit")

    def test_retail_surface_light_metadata_is_parsed_before_generic_q3map_skip(self) -> None:
        for field in (
            "surfaceLightValid",
            "surfaceLight",
            "surfaceLightSubdivide",
            "surfaceLightColorValid",
            "surfaceLightColor",
            "surfaceLightImageColorValid",
            "surfaceLightImageColor",
        ):
            self.assertIn(field, self.header)

        parse_shader = source_section(
            self.shader,
            "static qboolean ParseShader( const char **text )",
            "static void ComputeStageIteratorFunc",
        )
        expected = (
            "q3map_surfaceLight",
            "q3map_lightSubdivide",
            "q3map_lightRGB",
            "q3map_lightColor",
            "q3map_lightImage",
        )
        for directive in expected:
            self.assertIn(directive, parse_shader)
            self.assertLess(
                parse_shader.index(directive),
                parse_shader.index('!Q_stricmpn( token, "q3map", 5 )'),
            )

        init_shader = source_section(
            self.shader,
            "static void InitShader( const char *name, int lightmapIndex )",
            "static void DetectNeeds",
        )
        self.assertIn(
            "VectorSet( shader.surfaceLightColor, 1.0f, 1.0f, 1.0f );",
            init_shader,
        )
        self.assertIn(
            "VectorSet( shader.surfaceLightImageColor, 1.0f, 1.0f, 1.0f );",
            init_shader,
        )

    def test_light_image_hue_uses_bounded_alpha_weighted_average(self) -> None:
        average = source_section(
            self.image,
            "qboolean R_ImageAverageColor",
            "R_FindImageFile",
        )
        self.assertIn("alpha = pixel[3] / 255.0;", average)
        self.assertIn("alphaRgbSum[0] += pixel[0] * alpha;", average)
        self.assertIn("if ( alphaSum > 0.001 )", average)
        self.assertIn("Com_Clamp( 0.0f, 1.0f, color[0] )", average)
        self.assertIn("ri.Free( pic );", average)

        parse_image = source_section(
            self.shader,
            "static void ParseQ3MapLightImage",
            "ParseShader",
        )
        self.assertIn("R_ImageAverageColor( token, color )", parse_image)
        self.assertIn("shader.surfaceLightImageColorValid = qtrue;", parse_image)

    def test_proxy_generation_is_bounded_geometric_and_not_lightmap_authoritative(self) -> None:
        for contract in (
            "#define MAX_SURFACELIGHT_PROXIES 256",
            "#define MAX_RT_SURFACELIGHT_LIGHTS 16",
            "#define SURFACELIGHT_PROXY_SUBDIVIDE_MIN_SIZE 64.0f",
            "#define SURFACELIGHT_PROXY_SUBDIVIDE_MAX_SIZE 1024.0f",
            "#define SURFACELIGHT_PROXY_SUBDIVIDE_MAX_AXIS 4",
        ):
            self.assertIn(contract, self.header + self.bsp)

        radius = source_section(
            self.bsp,
            "static float R_SurfaceLightProxyRadius",
            "static surfaceLightProxyProjection_t R_SurfaceLightProxyProjection",
        )
        self.assertIn(
            "radius = extent * 2.0f + sqrtf( shader->surfaceLight ) * 8.0f;",
            radius,
        )
        self.assertIn("return Com_Clamp( 64.0f, 4096.0f, radius );", radius)

        color = source_section(
            self.bsp,
            "static void R_SurfaceLightResolveColor",
            "static qboolean R_SurfaceLightTriangleInfo",
        )
        explicit = color.index("shader->surfaceLightColorValid")
        image = color.index("shader->surfaceLightImageColorValid")
        vertex = color.index("VectorScale( colorAccum")
        white = color.index("VectorSet( color, 1.0f, 1.0f, 1.0f )")
        self.assertLess(explicit, image)
        self.assertLess(image, vertex)
        self.assertLess(vertex, white)
        self.assertNotIn("lightmapAverage", color)
        self.assertNotIn("shader->lightmapIndex", color)

        add_proxy = source_section(
            self.bsp,
            "static qboolean R_AddSurfaceLightProxy",
            "static qboolean R_SurfaceLightBeginSubdivision",
        )
        self.assertIn(
            "if ( tr.surfaceLightProxies.count >= MAX_SURFACELIGHT_PROXIES )",
            add_proxy,
        )
        self.assertIn("proxy->intensity = shader->surfaceLight;", add_proxy)
        self.assertIn("proxy->radius = R_SurfaceLightProxyRadius", add_proxy)
        self.assertNotIn("VectorScale( proxy->color", add_proxy)
        self.assertNotIn("shadowCaster", add_proxy)
        self.assertNotIn("shadowCone", add_proxy)

    def test_proxy_generation_covers_world_surface_types_and_resets_per_map(self) -> None:
        dispatch = source_section(
            self.bsp,
            "static void R_BuildSurfaceLightProxyForSurface",
            "static void R_BuildSurfaceLightProxiesForWorld",
        )
        for surface_type in ("SF_FACE", "SF_GRID", "SF_TRIANGLES"):
            self.assertIn(surface_type, dispatch)
        self.assertIn("shader->isSky", dispatch)
        self.assertIn("shader->surfaceFlags & SURF_SKY", dispatch)
        self.assertIn("tr.surfaceLightProxies.skippedSky++;", dispatch)

        load = self.bsp[self.bsp.index("void RE_LoadWorldMap( const char *name )") :]
        self.assertLess(
            load.index("R_ClearSurfaceLightProxies();"),
            load.index("tr.worldMapLoaded = qtrue;"),
        )
        self.assertLess(
            load.index("tr.world = &s_worldData;"),
            load.index("R_BuildSurfaceLightProxiesForWorld();"),
        )

    def test_frontend_selection_is_stable_pvs_bounded_and_not_a_dlight_promotion(self) -> None:
        self.assertIn(
            "surfaceLightProxy_t rtSurfaceLights[MAX_RT_SURFACELIGHT_LIGHTS];",
            self.header,
        )
        selection = source_section(
            self.scene,
            "static void R_SelectSurfaceLightProxiesForRt",
            "RE_AddLightToScene",
        )
        self.assertIn("selected[MAX_SURFACELIGHT_PROXIES]", selection)
        self.assertIn("visible[MAX_SURFACELIGHT_PROXIES]", selection)
        self.assertIn("priorities[MAX_SURFACELIGHT_PROXIES]", selection)
        self.assertIn("R_SurfaceLightProxyVisibleInPVS", selection)
        self.assertIn("MAX_RT_SURFACELIGHT_LIGHTS", selection)
        self.assertIn("if ( priorities[i] > bestPriority )", selection)
        self.assertIn(
            "tr.refdef.rtSurfaceLights[selectedThisScene++] =",
            selection,
        )
        self.assertIn("rtx_rt_raster_reference->integer", selection)
        self.assertNotIn("RE_AddDynamicLightToScene", selection)
        self.assertNotIn("RE_AddLinearLightToScene", selection)
        self.assertNotIn("backEndData->dlights", selection)

        visible = source_section(
            self.scene,
            "static qboolean R_SurfaceLightProxyVisibleInPVS",
            "static void R_SelectSurfaceLightProxiesForRt",
        )
        self.assertIn("R_LightCandidateVisibleInPVS", visible)
        self.assertIn("SURFACE_LIGHT_PROXY_LINEAR", visible)
        self.assertIn("R_SurfaceLightProxyLinearEnd", visible)

        render_scene = source_section(
            self.scene,
            "void RE_RenderScene( const refdef_t *fd )",
            "R_RenderView( &parms );",
        )
        self.assertLess(
            render_scene.index("((int *)tr.refdef.areamask)[i] ="),
            render_scene.index("R_SelectSurfaceLightProxiesForRt( fd );"),
        )

    def test_cvars_enable_native_rt_proxies_without_shadowmap_controls(self) -> None:
        self.assertIn(
            'ri.Cvar_Get( "r_surfaceLightProxies", "1", CVAR_ARCHIVE_ND )',
            self.init,
        )
        self.assertIn(
            'ri.Cvar_Get( "r_surfaceLightProxyMaxLights", "16", CVAR_ARCHIVE_ND )',
            self.init,
        )
        self.assertIn("MAX_RT_SURFACELIGHT_LIGHTS", self.init)
        self.assertIn("native RTX analytic lights with ray-traced visibility", self.init)
        self.assertIn("r_surfaceLightProxyDebug", self.commands)
        self.assertNotIn("r_surfaceLightProxyShadows", self.header + self.init)
        self.assertNotIn("r_surfaceLightProxyShadowMaxLights", self.header + self.init)

    def test_native_rt_buffer_consumes_proxies_with_ray_visibility(self) -> None:
        append = source_section(
            self.vk,
            "static uint32_t vk_rt_append_surface_lights",
            "static qboolean vk_rt_update_light_buffer",
        )
        self.assertIn("vk_rt_raster_reference_enabled()", append)
        self.assertIn("backEnd.refdef.numRtSurfaceLights", append)
        self.assertIn("backEnd.refdef.rtSurfaceLights[i]", append)
        self.assertIn("SURFACE_LIGHT_PROXY_LINEAR", append)
        self.assertIn("? 2.0f : 0.0f", append)
        self.assertIn(
            "VectorMA( proxy->origin, proxy->radius, proxy->normal, end );",
            append,
        )
        self.assertIn(
            "dst->metadata[0] = RTX_RT_LIGHT_FLAG_CASTS_SHADOWS;",
            append,
        )
        self.assertNotIn("proxy->intensity", append)
        self.assertNotIn("RTX_RT_LIGHT_FLAG_SHADOW_ONLY", append)
        self.assertNotIn("shadowMap", append)
        self.assertNotIn("shadowAtlas", append)

        update = source_section(
            self.vk,
            "static qboolean vk_rt_update_light_buffer( void )\n{",
            "static void vk_rt_destroy_as",
        )
        surface_append = update.index("vk_rt_append_surface_lights")
        world_append = update.index("vk_rt_append_world_entity_lights")
        self.assertLess(surface_append, world_append)

        self.assertIn(
            "if (castsShadows && pc.shadowMode > 0u)",
            self.closest_hit,
        )
        self.assertIn("trace_shadow_visibility(", self.closest_hit)

    def test_reduced_rt_budgets_reserve_only_a_small_native_surface_share(self) -> None:
        reservation = source_section(
            self.vk,
            "static uint32_t vk_rt_surface_light_reservation( uint32_t maxLights, uint32_t usedLights )\n{",
            "static uint32_t vk_rt_append_surface_lights( rtxRtGpuLight_t *lights,",
        )
        self.assertIn("vk_rt_raster_reference_enabled()", reservation)
        self.assertIn("backEnd.refdef.numRtSurfaceLights <= 0", reservation)
        self.assertIn("usedLights >= maxLights", reservation)
        self.assertIn("reservationCap = maxLights / 4u;", reservation)
        self.assertIn("reservationCap < 1u", reservation)
        self.assertIn("reservationCap = 1u;", reservation)
        self.assertIn("reservationCap > 2u", reservation)
        self.assertIn("reservationCap = 2u;", reservation)
        self.assertIn(
            "return MIN( selectedCount, MIN( reservationCap, available ) );",
            reservation,
        )

        update = source_section(
            self.vk,
            "static qboolean vk_rt_update_light_buffer( void )\n{",
            "static void vk_rt_destroy_as",
        )
        reserve = update.index(
            "reservedSurfaceLights = vk_rt_surface_light_reservation"
        )
        gameplay_limit = update.index(
            "gameplayLightLimit = maxLights - reservedSurfaceLights;"
        )
        dlight_limit = update.index("count < gameplayLightLimit")
        append = update.index("vk_rt_append_surface_lights")
        self.assertLess(reserve, gameplay_limit)
        self.assertLess(gameplay_limit, dlight_limit)
        self.assertLess(dlight_limit, append)

    def test_compile_surface_light_metadata_does_not_force_fullbright_materials(self) -> None:
        translation = source_section(
            self.vk,
            "static void vk_rt_translate_shader_to_material( const shader_t *shader, rtxRtMaterial_t *material )\n{",
            "static qboolean vk_rt_cpu_geometry_find_or_add_material_ex( rtxRtCpuGeometry_t *geometry,",
        )
        self.assertNotIn("surfaceLightValid", translation)
        self.assertNotIn("surfaceLight", translation)


if __name__ == "__main__":
    unittest.main()

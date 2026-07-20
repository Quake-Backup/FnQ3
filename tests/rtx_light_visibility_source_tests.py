from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def source_section(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


class RtxLightVisibilitySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.local_header = read_text("code/rendererrtx/tr_local.h")
        cls.scene = read_text("code/rendererrtx/tr_scene.c")
        cls.backend = read_text("code/rendererrtx/tr_backend.c")
        cls.bsp = read_text("code/rendererrtx/tr_bsp.c")
        cls.shader = read_text("code/rendererrtx/tr_shader.c")
        cls.vk = read_text("code/rendererrtx/vk.c")
        cls.closest_hit = read_text("code/rendererrtx/shaders/rt_main.rchit")
        cls.raygen = read_text("code/rendererrtx/shaders/rt_main.rgen")

    def test_scene_dlights_default_to_ray_traced_visibility(self) -> None:
        self.assertIn("qboolean castsRtShadows;", self.local_header)

        point_add = source_section(
            self.scene,
            "static void RE_AddDynamicLightToScene",
            "void RE_AddLinearLightToScene",
        )
        linear_add = source_section(
            self.scene,
            "void RE_AddLinearLightToScene",
            "static qboolean R_LightCandidateVisibleInPVS",
        )
        self.assertIn("dl->castsRtShadows = qtrue;", point_add)
        self.assertIn("dl->castsRtShadows = qtrue;", linear_add)

    def test_static_sidecar_shadow_intent_survives_deterministic_promotion(self) -> None:
        promotion = source_section(
            self.scene,
            "static void R_AddStaticMapLightsToScene",
            "RE_AddLightToScene",
        )
        self.assertIn("selected[MAX_STATIC_MAP_LIGHTS]", promotion)
        self.assertIn("priorities[MAX_STATIC_MAP_LIGHTS]", promotion)
        self.assertIn("r_staticLightMaxLights", promotion)
        self.assertIn("dl = &backEndData->dlights[before];", promotion)
        self.assertIn("dl->castsRtShadows = light->castsShadows;", promotion)
        self.assertNotIn("shadowAtlas", promotion)
        self.assertNotIn("r_staticLightShadowMaxLights", promotion)

    def test_cpu_upload_marks_compatibility_lights_shadow_only(self) -> None:
        light_struct = source_section(
            self.vk,
            "typedef struct {\n\tfloat positionRadius[4]",
            "#define RTX_RT_MAX_WORLD_ENTITY_LIGHTS",
        )
        light_update = source_section(
            self.vk,
            "static qboolean vk_rt_update_light_buffer( void )\n{",
            "static void vk_rt_destroy_as",
        )

        self.assertIn("uint32_t metadata[4];", light_struct)
        self.assertIn("RTX_RT_LIGHT_FLAG_CASTS_SHADOWS", light_struct)
        self.assertIn("RTX_RT_LIGHT_FLAG_SHADOW_ONLY", light_struct)
        self.assertIn(
            "qboolean rasterReference = vk_rt_raster_reference_enabled();",
            light_update,
        )
        self.assertIn("qboolean shadowOnly = rasterReference;", light_update)
        self.assertIn(
            "shadowOnly && ( !traceLightShadows || !dl->castsRtShadows )",
            light_update,
        )
        self.assertIn(
            "dl->castsRtShadows ? RTX_RT_LIGHT_FLAG_CASTS_SHADOWS : 0u",
            light_update,
        )
        self.assertIn(
            "shadowOnly ? RTX_RT_LIGHT_FLAG_SHADOW_ONLY : 0u",
            light_update,
        )
        self.assertNotIn(
            "if ( !vk_rt_raster_reference_enabled() )",
            light_update,
        )

    def test_closest_hit_traces_only_opted_in_lights_without_double_lighting(self) -> None:
        self.assertIn("uvec4 metadata;", self.closest_hit)
        self.assertIn("RTX_RT_LIGHT_FLAG_CASTS_SHADOWS", self.closest_hit)
        self.assertIn("RTX_RT_LIGHT_FLAG_SHADOW_ONLY", self.closest_hit)
        self.assertIn("if (castsShadows && pc.shadowMode > 0u)", self.closest_hit)
        self.assertIn("if (castsShadows && !shadowOnly)", self.closest_hit)
        self.assertIn("payloadRadiance.shadowLoss +=", self.closest_hit)
        self.assertIn("directContribution * (1.0 - visibility)", self.closest_hit)
        self.assertIn("if (shadowOnly)", self.closest_hit)

        trace = self.closest_hit.index("trace_shadow_visibility(")
        direct = self.closest_hit.index("Lo += directContribution * visibility;")
        self.assertLess(trace, direct)

    def test_shadow_only_lights_do_not_enter_the_global_raster_multiplier(self) -> None:
        light_loop = source_section(
            self.closest_hit,
            "for (uint lightIndex = 0u;",
            "vec3 reflectDir = reflect(-V, N);",
        )
        self.assertGreaterEqual(
            light_loop.count("if (castsShadows && !shadowOnly)"),
            2,
        )
        self.assertIn("shadowWeightTotal += shadowWeight;", light_loop)
        self.assertIn("visibleShadowWeight +=", light_loop)
        self.assertIn("payloadRadiance.shadowLoss +=", light_loop)

        self.assertIn("vec3 shadowLoss,", self.raygen)
        self.assertIn(
            "rasterReference = max(rasterReference - shadowLoss, vec3(0.0));",
            self.raygen,
        )
        self.assertIn(
            "contributionStrength * clamp(shadowResponse, 0.0, 1.0)",
            self.raygen,
        )

    def test_analytic_environment_specular_requires_ray_visible_sky(self) -> None:
        reflection = source_section(
            self.closest_hit,
            "vec3 reflectDir = reflect(-V, N);",
            "if (pc.indirectBounce != 0u)",
        )

        self.assertIn("vec3 glossyDir = sample_cone(", reflection)
        self.assertIn("environmentSpecularVisibility", reflection)
        self.assertIn("trace_shadow_visibility(", reflection)
        self.assertIn("evaluate_environment(glossyDir)", reflection)
        self.assertIn("pc.reflectionStrength", reflection)
        self.assertRegex(
            reflection,
            r"pc\.reflectionStrength\s*\*\s*"
            r"environmentSpecularVisibility",
        )

    def test_environment_diffuse_is_native_and_optional_ray_is_occlusion_only(
        self,
    ) -> None:
        indirect = source_section(
            self.closest_hit,
            "if (pc.indirectBounce != 0u)",
            "/*\n\t * Direct lights and their shadow rays remain authoritative",
        )
        environment_diffuse = source_section(
            self.closest_hit,
            "/*\n\t * Direct lights and their shadow rays remain authoritative",
            "Lo += emissive;",
        )

        self.assertIn("float environmentDiffuseVisibility = 1.0;", self.closest_hit)
        self.assertIn("sample_cosine_hemisphere(N, seed)", indirect)
        self.assertIn("trace_shadow_visibility(", indirect)
        self.assertIn(
            "environmentDiffuseVisibility = mix(0.25, 1.0, sampledVisibility);",
            indirect,
        )
        self.assertNotIn("evaluate_environment(", indirect)
        self.assertNotIn("Lo +=", indirect)
        self.assertIn("Lo += evaluate_environment(N)", environment_diffuse)
        self.assertIn("albedo * (1.0 - metallic)", environment_diffuse)
        self.assertIn("pc.indirectStrength", environment_diffuse)
        self.assertIn("environmentDiffuseVisibility", environment_diffuse)

    def test_raster_owned_base_lighting_is_visible_to_raygen_before_trace(self) -> None:
        draw = source_section(
            self.backend,
            "static const void *RB_DrawSurfs",
            "static const void *RB_DrawBuffer",
        )
        pretrace_light = draw.index(
            "RB_LightingPass( RB_DRAWSURFS_RT_BASE, qfalse )"
        )
        trace = draw.index("rtTraceCompleted = vk_rt_trace_frame();")
        overlay = draw.index("RB_DRAWSURFS_RT_OVERLAY", trace)

        self.assertLess(pretrace_light, trace)
        self.assertLess(trace, overlay)
        self.assertIn(
            "!rasterOwnsRtBaseLights && !rtTraceCompleted",
            draw,
        )

    def test_emissive_safe_shadow_modulation_is_preserved(self) -> None:
        self.assertIn(
            "(materialFlags & RTX_RT_MATFLAG_EMISSIVE) != 0u ? 0.0 : 1.0",
            self.closest_hit,
        )
        self.assertIn(
            "contributionStrength * clamp(shadowResponse, 0.0, 1.0)",
            self.raygen,
        )

    def test_authored_sun_is_selected_from_used_sky_shaders_and_normalized(self) -> None:
        for field in (
            "qboolean\tskySunValid;",
            "vec3_t\t\tskySunColor;",
            "vec3_t\t\tskySunDirection;",
            "vec3_t\t\tskySunLight;",
            "float\t\tskySunIntensity;",
        ):
            self.assertIn(field, self.local_header)

        parser = source_section(
            self.shader,
            "static qboolean ParseSkySunParms",
            "/*\n=================\nParseShader",
        )
        self.assertIn("maxColor = MAX(", parser)
        self.assertIn("VectorScale( color, intensity, sunLight );", parser)

        parse_shader = source_section(
            self.shader,
            "static qboolean ParseShader",
            "SHADER OPTIMIZATION AND FOGGING",
        )
        self.assertIn('"q3map_sunExt2"', parse_shader)
        self.assertIn("if ( shader.isSky && skySunValid )", parse_shader)
        self.assertNotIn("tr.sunLight[0] =", parse_shader)

        bsp_selection = source_section(
            self.bsp,
            "static void R_ClearWorldSun",
            "#ifdef USE_PMLIGHT",
        )
        self.assertIn("VectorClear( tr.sunLight );", bsp_selection)
        self.assertIn("R_SetWorldSunFromShader( shader );", bsp_selection)
        self.assertIn("VectorCopy( shader->skySunLight, tr.sunLight );", bsp_selection)

        sun_resolve = source_section(
            self.vk,
            "static void vk_rt_resolve_sun_params",
            "static void vk_rt_reset_world_light_cache",
        )
        self.assertIn("RTX_RT_LEGACY_SUN_UNIT_SCALE", sun_resolve)
        self.assertIn("if ( !authoredSun && outDirection[2] < minElevation )", sun_resolve)
        self.assertIn(
            "VectorScale( tr.sunLight, RTX_RT_LEGACY_SUN_UNIT_SCALE, outColor );",
            sun_resolve,
        )


if __name__ == "__main__":
    unittest.main()

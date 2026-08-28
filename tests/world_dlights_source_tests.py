from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorldDlightSourceTests(unittest.TestCase):
    def test_shared_versioned_format_contract(self) -> None:
        header = (ROOT / "code/renderercommon/tr_world_dlights.h").read_text(
            encoding="utf-8"
        )
        self.assertIn('#define WORLD_DLIGHT_FORMAT_NAME "fnquake3-world-dlights"', header)
        self.assertIn("#define WORLD_DLIGHT_FORMAT_VERSION 1", header)
        self.assertIn('#define WORLD_DLIGHT_FILE_EXTENSION ".dlight"', header)
        self.assertIn(
            '#define WORLD_DLIGHT_LEGACY_FILE_EXTENSION ".lights.json"', header
        )
        self.assertIn("#define WORLD_DLIGHT_MAX_FILE_SIZE ( 512 * 1024 )", header)
        self.assertIn("#define WORLD_DLIGHT_MAX_LIGHTS 256", header)
        self.assertIn("#define WORLD_DLIGHT_DEFAULT_RADIUS 300.0f", header)
        self.assertIn("#define WORLD_DLIGHT_DEFAULT_INTENSITY 300.0f", header)
        self.assertIn("#define WORLD_DLIGHT_DEFAULT_INNER_ANGLE 35.0f", header)
        self.assertIn("#define WORLD_DLIGHT_DEFAULT_OUTER_ANGLE 50.0f", header)
        self.assertIn("#define WORLD_DLIGHT_DEFAULT_SHADOW_RESOLUTION 256", header)
        self.assertIn("#define WORLD_DLIGHT_MIN_SHADOW_RESOLUTION 64", header)
        self.assertIn("#define WORLD_DLIGHT_MAX_SHADOW_RESOLUTION 1024", header)
        self.assertIn("#define WORLD_DLIGHT_DEFAULT_FADE_START 0.0f", header)
        self.assertIn("#define WORLD_DLIGHT_DEFAULT_FADE_END 0.0f", header)
        self.assertIn("R_WorldDlightClampShadowResolution", header)
        self.assertIn("R_WorldDlightShadowResolutionForRadius", header)
        self.assertIn("R_WorldDlightDistanceFade", header)

    def test_distance_fade_defaults_to_disabled(self) -> None:
        header = (ROOT / "code/renderercommon/tr_world_dlights.h").read_text(
            encoding="utf-8"
        )
        fade = header[header.index("R_WorldDlightDistanceFade") :]
        # a sidecar written before the fade keys existed carries 0/0, which has
        # to mean "fully lit everywhere" rather than "extinguished everywhere"
        self.assertIn("if ( !( fadeEnd > 0.0f ) || !( fadeEnd > fadeStart ) ) {", fade)
        self.assertIn("return 1.0f;", fade)

    def test_all_renderers_load_and_generate_world_dlights(self) -> None:
        renderers = (
            ("OpenGL", "code/renderer", True),
            ("Vulkan", "code/renderervk", True),
            ("RTX", "code/rendererrtx", False),
        )
        for label, directory, raster_shadows in renderers:
            with self.subTest(renderer=label):
                local = (ROOT / directory / "tr_local.h").read_text(encoding="utf-8")
                bsp = (ROOT / directory / "tr_bsp.c").read_text(encoding="utf-8")
                scene = (ROOT / directory / "tr_scene.c").read_text(encoding="utf-8")
                init = (ROOT / directory / "tr_init.c").read_text(encoding="utf-8")

                self.assertIn('../renderercommon/tr_world_dlights.h', local)
                self.assertIn(
                    "#define MAX_STATIC_MAP_LIGHTS WORLD_DLIGHT_MAX_LIGHTS", local
                )
                self.assertIn("extern cvar_t\t*r_dlightLoadWorld;", local)

                self.assertIn(
                    'ri.Cvar_Get( "r_dlightLoadWorld", "1", CVAR_ARCHIVE_ND )', init
                )
                self.assertIn('ri.Cmd_AddCommand( "r_dlightReloadWorld"', init)
                self.assertIn('ri.Cmd_AddCommand( "r_dlightGenerateWorld"', init)
                self.assertIn('ri.Cmd_RemoveCommand( "r_dlightReloadWorld"', init)
                self.assertIn('ri.Cmd_RemoveCommand( "r_dlightGenerateWorld"', init)
                if raster_shadows:
                    self.assertIn(
                        'ri.Cvar_Get( "r_spotShadows", "1", CVAR_ARCHIVE_ND | CVAR_LATCH )',
                        init,
                    )

                self.assertRegex(
                    scene,
                    re.compile(
                        r"r_dlightLoadWorld[^\n]*\n(?:.*\n){0,3}.*r_dlightMode->integer\s*!=\s*2",
                        re.MULTILINE,
                    ),
                )

                self.assertIn("WORLD_DLIGHT_FILE_EXTENSION", bsp)
                self.assertIn("WORLD_DLIGHT_LEGACY_FILE_EXTENSION", bsp)
                self.assertLess(
                    bsp.find("WORLD_DLIGHT_FILE_EXTENSION"),
                    bsp.find("WORLD_DLIGHT_LEGACY_FILE_EXTENSION"),
                )
                self.assertIn("WORLD_DLIGHT_MAX_FILE_SIZE", bsp)
                self.assertIn("WORLD_DLIGHT_FORMAT_NAME", bsp)
                self.assertIn("WORLD_DLIGHT_FORMAT_VERSION", bsp)
                self.assertIn('!Q_stricmp( key, "format" )', bsp)
                self.assertIn('!Q_stricmp( key, "shadowResolution" )', bsp)
                self.assertIn("WORLD_DLIGHT_DEFAULT_RADIUS", bsp)
                self.assertIn("WORLD_DLIGHT_DEFAULT_INTENSITY", bsp)
                self.assertIn("WORLD_DLIGHT_DEFAULT_INNER_ANGLE", bsp)
                self.assertIn("WORLD_DLIGHT_DEFAULT_OUTER_ANGLE", bsp)
                self.assertIn("WORLD_DLIGHT_DEFAULT_SHADOW_RESOLUTION", bsp)

                self.assertIn("tr.surfaceLightProxies.count", bsp)
                self.assertIn("proxy->origin", bsp)
                self.assertIn("proxy->normal", bsp)
                self.assertIn("proxy->color", bsp)
                self.assertIn('\\"surfacelight_%03i_surface_%i\\"', bsp)

                # the generator must spell each proxy's own projection.  Writing
                # every entry as a spot demotes a point proxy to a linear light
                # on reload, which the raster point-shadow planner drops.
                self.assertNotIn('\\"type\\": \\"spot\\"', bsp)
                self.assertIn('\\"type\\": \\"%s\\"', bsp)
                self.assertIn("R_WorldDlightProxyTypeName( proxy )", bsp)
                self.assertIn("R_WorldDlightShadowResolutionForRadius", bsp)
                self.assertIn("R_WorldDlightQuoteName( proxy->shaderName", bsp)
                self.assertIn("R_WorldDlightClampShadowResolution( light->resolution )", bsp)
                self.assertIn("R_StaticMapLightsNormalizeFade( light );", bsp)
                self.assertIn('!Q_stricmp( key, "fadeStart" )', bsp)
                self.assertIn('!Q_stricmp( key, "fadeEnd" )', bsp)
                # silent truncation would read as "everything was exported"
                self.assertIn("world dlight generation truncated", bsp)
                self.assertIn("VectorNormalize2( proxy->normal, direction )", bsp)
                self.assertIn("ri.FS_ReadFile( filename, NULL ) >= 0", bsp)
                self.assertIn("ri.FS_FileExists", bsp)
                self.assertIn('Q_stricmp( ri.Cmd_Argv( 1 ), "force" )', bsp)
                self.assertIn("ri.FS_WriteFile", bsp)
                self.assertIn("R_LoadStaticMapLightsForWorld();", bsp)

    def test_generator_preserves_point_projections(self) -> None:
        # SURFACE_LIGHT_PROXY_POINT proxies are the only surface lights the
        # raster point-shadow planner accepts, so the exported type has to
        # follow the proxy rather than a constant.
        for directory, spot_projection in (
            ("code/renderer", "SURFACE_LIGHT_PROXY_SPOT"),
            ("code/renderervk", "SURFACE_LIGHT_PROXY_SPOT"),
            ("code/rendererrtx", "SURFACE_LIGHT_PROXY_LINEAR"),
        ):
            with self.subTest(renderer=directory):
                bsp = (ROOT / directory / "tr_bsp.c").read_text(encoding="utf-8")
                start = bsp.index("static const char *R_WorldDlightProxyTypeName")
                helper = bsp[start : bsp.index("}", start)]
                self.assertIn(f"proxy->projection == {spot_projection}", helper)
                self.assertIn('"spot"', helper)
                self.assertIn('"point"', helper)

    def test_promotion_applies_distance_fade(self) -> None:
        for directory in ("code/renderer", "code/renderervk", "code/rendererrtx"):
            with self.subTest(renderer=directory):
                scene = (ROOT / directory / "tr_scene.c").read_text(encoding="utf-8")
                self.assertIn("R_WorldDlightDistanceFade( light->fadeStart, light->fadeEnd", scene)
                # the fade dims radiance; the lit volume must not change shape
                self.assertIn("VectorScale( light->color, fade, color );", scene)
                self.assertIn("fade = R_StaticMapLightFade( light, fd );", scene)

    def test_faded_lights_release_raster_shadow_budget(self) -> None:
        for directory in ("code/renderer", "code/renderervk"):
            with self.subTest(renderer=directory):
                main = (ROOT / directory / "tr_main.c").read_text(encoding="utf-8")
                start = main.index("static float R_ShadowSpotStaticPriority")
                section = main[start : main.index("\n}", start)]
                self.assertIn("R_WorldDlightDistanceFade", section)
                self.assertIn("if ( fade <= 0.0f ) {", section)

                scene = (ROOT / directory / "tr_scene.c").read_text(encoding="utf-8")
                self.assertIn(
                    "dl->shadowPriorityMultiplier = fade * light->designerPriority", scene
                )

    def test_proxy_facing_comes_from_the_authored_normal(self) -> None:
        # Q3 culls GL's front face for CT_FRONT_SIDED, so a visible BSP face is
        # wound clockwise from outside and (b-a)x(c-a) is the negation of the
        # plane normal.  Offsetting a light along the winding cross buries it in
        # the brush it came from, which is what this guards against.
        for directory in ("code/renderer", "code/renderervk", "code/rendererrtx"):
            with self.subTest(renderer=directory):
                bsp = (ROOT / directory / "tr_bsp.c").read_text(encoding="utf-8")

                self.assertIn("vec3_t orientAccum;", bsp)
                self.assertIn("VectorClear( accum->orientAccum );", bsp)

                resolve = bsp[bsp.index("static qboolean R_SurfaceLightResolveNormal") :]
                resolve = resolve[: resolve.index("\n}")]
                self.assertIn("VectorNormalize2( accum->orientAccum, authored )", resolve)
                self.assertIn("DotProduct( normal, authored ) < 0.0f", resolve)
                self.assertIn("VectorNegate( normal, normal );", resolve)

                # the authored normal must be gathered unconditionally, not only
                # as a fallback for a degenerate winding
                self.assertIn(
                    "VectorScale( face->plane.normal, accum.area, accum.orientAccum );", bsp
                )
                self.assertIn(
                    "VectorAdd( accum.orientAccum, grid->verts[i].normal, accum.orientAccum );",
                    bsp,
                )
                self.assertIn(
                    "VectorAdd( accum.orientAccum, tri->verts[i].normal, accum.orientAccum );",
                    bsp,
                )
                # subdivision buckets share their parent surface's facing
                self.assertIn(
                    "VectorCopy( total->orientAccum, buckets[i].orientAccum );", bsp
                )

                # the proxy builder must go through the resolver
                add_proxy = bsp[bsp.index("static qboolean R_AddSurfaceLightProxy( int surfaceIndex") :]
                add_proxy = add_proxy[: add_proxy.index("\n}")]
                self.assertIn("R_SurfaceLightResolveNormal( accum, normal )", add_proxy)
                self.assertNotIn("VectorNormalize2( accum->normalAccum, normal )", add_proxy)

    def test_proxy_origin_hugs_its_surface(self) -> None:
        # the offset only has to break the coplanar tie; pushing further moves
        # the apparent source off the fixture and through a recessed brush
        for directory in ("code/renderer", "code/renderervk", "code/rendererrtx"):
            with self.subTest(renderer=directory):
                bsp = (ROOT / directory / "tr_bsp.c").read_text(encoding="utf-8")
                self.assertIn("#define SURFACELIGHT_PROXY_ORIGIN_OFFSET 4.0f", bsp)
                self.assertNotIn("Com_Clamp( 8.0f, 64.0f, proxy->radius * 0.05f )", bsp)

                place = bsp[bsp.index("static void R_SurfaceLightPlaceProxyOrigin") :]
                place = place[: place.index("\n}\n")]
                self.assertIn(
                    "VectorMA( centroid, SURFACELIGHT_PROXY_ORIGIN_OFFSET, normal, origin );",
                    place,
                )

    def test_proxies_in_solid_are_discarded(self) -> None:
        for directory in ("code/renderer", "code/renderervk", "code/rendererrtx"):
            with self.subTest(renderer=directory):
                bsp = (ROOT / directory / "tr_bsp.c").read_text(encoding="utf-8")
                solid = bsp[bsp.index("static qboolean R_SurfaceLightOriginInSolid") :]
                solid = solid[: solid.index("\n}\n")]

                self.assertIn("R_PointLeafClusterArea( origin, cluster, area )", solid)
                # a map without vis has no cluster to test against
                self.assertIn("tr.world->numClusters <= 0", solid)

                add_proxy = bsp[bsp.index("static qboolean R_AddSurfaceLightProxy( int surfaceIndex") :]
                add_proxy = add_proxy[: add_proxy.index("\n}\n")]
                self.assertIn("R_SurfaceLightOriginInSolid( proxy->origin", add_proxy)
                # the proxy is rolled back, not merely flagged
                self.assertIn("tr.surfaceLightProxies.count--;", add_proxy)
                self.assertIn("tr.surfaceLightProxies.skippedSolid++;", add_proxy)
                self.assertIn("return qfalse;", add_proxy)
                self.assertIn("flipped:%i solid:%i", bsp)

    def test_shadow_culling_uses_the_light_volume(self) -> None:
        # culling on the light's origin projection dropped the shadow plan the
        # moment the source left the screen, which is when a light beside the
        # viewer is throwing its longest shadows into view
        for directory in ("code/renderer", "code/renderervk"):
            with self.subTest(renderer=directory):
                main = (ROOT / directory / "tr_main.c").read_text(encoding="utf-8")
                self.assertNotIn("R_DlightShadowProjectionValid", main)

                visible = main[main.index("static qboolean R_DlightShadowVolumeVisible") :]
                visible = visible[: visible.index("\n}\n")]
                self.assertIn("R_CullPointAndRadius( dl->origin, radius ) != CULL_OUT", visible)
                # a linear light spans origin..origin2
                self.assertIn("dl->linear && R_CullPointAndRadius( dl->origin2", visible)

    def test_off_frustum_models_still_cast(self) -> None:
        for directory in ("code/renderer", "code/renderervk"):
            with self.subTest(renderer=directory):
                main = (ROOT / directory / "tr_main.c").read_text(encoding="utf-8")
                mesh = (ROOT / directory / "tr_mesh.c").read_text(encoding="utf-8")

                helper = main[main.index("qboolean R_EntityCastsFrameShadow") :]
                helper = helper[: helper.index("\n}\n")]
                self.assertIn("dl->shadowEligible", helper)
                self.assertIn("R_LightCullBounds( dl, mins, maxs )", helper)
                self.assertIn("RF_NOSHADOW | RF_FIRST_PERSON | RF_DEPTHHACK", helper)

                # a frustum-rejected model becomes a shadow-only caster
                self.assertIn("R_EntityCastsFrameShadow( ent, bounds[0], bounds[1] )", mesh)
                self.assertIn("shadowCasterOnly = qtrue;", mesh)
                self.assertIn("if ( !personalModel && !shadowCasterOnly ) {", mesh)

    def test_emitter_colour_comes_from_its_own_texture(self) -> None:
        # most retail light shaders declare only q3map_surfaceLight; without a
        # texture average the resolver fell through to the lightmap and vertex
        # averages, which on a light panel are blown out to near-white
        for directory in ("code/renderer", "code/renderervk", "code/rendererrtx"):
            with self.subTest(renderer=directory):
                shader = (ROOT / directory / "tr_shader.c").read_text(encoding="utf-8")
                resolve = shader[shader.index("static void R_ResolveSurfaceLightImageColor") :]
                resolve = resolve[: resolve.index("\n}\n")]

                self.assertIn("shader.surfaceLightColorValid", resolve)
                self.assertIn("R_ImageAverageColor( pStage->bundle[0].image[0]->imgName", resolve)
                # the lightmap stage carries the bake, not the fixture's colour
                self.assertIn("pStage->bundle[0].lightmap != LIGHTMAP_INDEX_NONE", resolve)
                # must run once the stage list is final
                self.assertIn(
                    "R_ResolveSurfaceLightImageColor();\n\n"
                    "\t// determine which stage iterator function is appropriate",
                    shader,
                )

    def test_proxy_radiance_is_emission_relative_and_tunable(self) -> None:
        for directory in ("code/renderer", "code/renderervk", "code/rendererrtx"):
            with self.subTest(renderer=directory):
                bsp = (ROOT / directory / "tr_bsp.c").read_text(encoding="utf-8")
                init = (ROOT / directory / "tr_init.c").read_text(encoding="utf-8")

                self.assertIn("#define SURFACELIGHT_PROXY_REFERENCE_EMISSION 300.0f", bsp)
                self.assertIn("#define SURFACELIGHT_PROXY_DEFAULT_RADIANCE 0.15f", bsp)

                radiance = bsp[bsp.index("static float R_SurfaceLightProxyRadiance") :]
                radiance = radiance[: radiance.index("\n}\n")]
                self.assertIn("r_surfaceLightProxyRadiance", radiance)
                # relative to the authored emission, not to the baked lightmap
                self.assertIn(
                    "sqrtf( emission / SURFACELIGHT_PROXY_REFERENCE_EMISSION )", radiance
                )

                # hue is normalized to unit peak so texture brightness does not
                # double as emitter strength
                apply = bsp[bsp.index("static void R_SurfaceLightApplyRadiance") :]
                apply = apply[: apply.index("\n}\n")]
                self.assertIn("R_SurfaceLightProxyRadiance( shader ) / peak", apply)
                self.assertIn("R_SurfaceLightApplyRadiance( shader, proxy->color );", bsp)

                self.assertIn(
                    'r_surfaceLightProxyRadiance = ri.Cvar_Get( "r_surfaceLightProxyRadiance", "0.15"',
                    init,
                )

    def test_debug_overlay_is_limited_to_the_current_pvs(self) -> None:
        for directory in ("code/renderer", "code/renderervk"):
            with self.subTest(renderer=directory):
                scene = (ROOT / directory / "tr_scene.c").read_text(encoding="utf-8")
                backend = (ROOT / directory / "tr_backend.c").read_text(encoding="utf-8")

                # stamped where the promotion pass already ran the PVS test, so
                # the overlay reuses that predicate instead of re-deriving one
                self.assertIn(
                    "tr.staticMapLights.lights[i].pvsFrame = tr.frameCount;", scene
                )
                self.assertIn(
                    "if ( light->pvsFrame != backEnd.viewParms.frameCount ) {", backend
                )

    def test_debug_overlay_geometry_is_shared(self) -> None:
        header = (ROOT / "code/renderercommon/tr_dlight_debug.h").read_text(
            encoding="utf-8"
        )
        for symbol in (
            "R_DlightDebugBegin",
            "R_DlightDebugLine",
            "R_DlightDebugCross",
            "R_DlightDebugCircle",
            "R_DlightDebugSphere",
            "R_DlightDebugCone",
        ):
            self.assertIn(symbol, header)
        self.assertIn("#define DLIGHT_DEBUG_ALL 2", header)
        # the buffer must always have room for a whole light so a flush never
        # splits one light's wireframe across two colours
        self.assertIn(
            "#define DLIGHT_DEBUG_MAX_VERTS ( DLIGHT_DEBUG_VERTS_PER_LIGHT * 8 )", header
        )

    def test_raster_renderers_expose_the_debug_overlay(self) -> None:
        for directory in ("code/renderer", "code/renderervk"):
            with self.subTest(renderer=directory):
                local = (ROOT / directory / "tr_local.h").read_text(encoding="utf-8")
                init = (ROOT / directory / "tr_init.c").read_text(encoding="utf-8")
                backend = (ROOT / directory / "tr_backend.c").read_text(encoding="utf-8")
                bsp = (ROOT / directory / "tr_bsp.c").read_text(encoding="utf-8")
                scene = (ROOT / directory / "tr_scene.c").read_text(encoding="utf-8")

                self.assertIn("../renderercommon/tr_dlight_debug.h", local)
                self.assertIn("extern cvar_t\t*r_dlightDebugDraw;", local)
                self.assertIn(
                    'r_dlightDebugDraw = ri.Cvar_Get( "r_dlightDebugDraw", "0", CVAR_CHEAT )',
                    init,
                )
                self.assertIn('ri.Cmd_AddCommand( "r_dlightWorldStatus"', init)
                self.assertIn('ri.Cmd_RemoveCommand( "r_dlightWorldStatus"', init)

                # the overlay has to run before the r_debugSurface early-out
                start = backend.index("static void RB_DebugGraphics( void ) {")
                head = backend[start : backend.index("r_debugSurface->integer", start)]
                self.assertIn("RB_DrawWorldDlightDebug();", head)

                self.assertIn("R_DlightDebugSphere( &lines, light->origin", backend)
                self.assertIn("light->type == MAP_LIGHT_SPOT", backend)
                self.assertIn("R_DlightDebugCone( &lines, light->origin", backend)

                self.assertIn("void R_WorldDlightsStatus_f( void )", bsp)
                # the status line has to name every gate that can suppress a light
                for cvar in (
                    "r_dlightMode",
                    "r_dlightLoadWorld",
                    "r_dynamiclight",
                    "r_staticLightMaxLights",
                    "r_dlightShadows",
                    "r_spotShadows",
                ):
                    self.assertIn(cvar, bsp)

                self.assertIn(
                    "tr.staticMapLights.lights[bestIndex].promotedFrame = tr.frameCount;",
                    scene,
                )

    def test_raster_spot_shadow_collection_obeys_world_gate(self) -> None:
        for directory in ("code/renderer", "code/renderervk"):
            main = (ROOT / directory / "tr_main.c").read_text(encoding="utf-8")
            start = main.index("static void R_ShadowManagerCollectStaticSpotCandidates")
            end = main.index(
                "static void R_ShadowManagerCollectSurfaceSpotCandidates", start
            )
            section = main[start:end]
            self.assertIn("r_dlightLoadWorld", section)
            self.assertIn("r_dlightMode->integer != 2", section)

    def test_root_archive_allows_world_dlight_sidecars(self) -> None:
        files = (ROOT / "code/qcommon/files.c").read_text(encoding="utf-8")
        self.assertIn('COM_CompareExtension( qpath, ".dlight" )', files)

    def test_format_and_generator_are_documented(self) -> None:
        docs = (ROOT / "docs/fnquake3/WORLD_DLIGHTS.md").read_text(encoding="utf-8")
        self.assertIn("maps/example.dlight", docs)
        self.assertIn('"format": "fnquake3-world-dlights"', docs)
        self.assertIn("r_dlightMode 2", docs)
        self.assertIn("r_dlightLoadWorld 1", docs)
        self.assertIn("r_dlightGenerateWorld force", docs)
        self.assertIn("area-weights triangle centroids", docs)
        self.assertIn("fadeStart", docs)
        self.assertIn("fadeEnd", docs)


if __name__ == "__main__":
    unittest.main()

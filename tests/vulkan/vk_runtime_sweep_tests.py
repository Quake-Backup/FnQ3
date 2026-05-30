from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SWEEP_PATH = ROOT / "scripts" / "vk_runtime_sweep.py"

spec = importlib.util.spec_from_file_location("vk_runtime_sweep", SWEEP_PATH)
assert spec is not None
vk_runtime_sweep = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(vk_runtime_sweep)


class VkRuntimeSweepParseTests(unittest.TestCase):
    def test_vkinfo_parser_extracts_modern_diagnostics(self) -> None:
        text = "\n".join(
            [
                "pipeline cache: cache/vkpc_123.bin, loaded: 64Kb, saved: 96Kb",
                "display HDR: requested unavailable, metadata: disabled, paper white 203 nits, max 1000 nits",
                "output backend: request hdr10-pq, selected sdr-srgb, native windows-scrgb, display HDR enabled, headroom 4.00, SDR white 203 nits, display max 812 nits, ICC yes/2048, driver windows, display HDR Panel, reason: test",
                "tone map: ACES, exposure 1.00",
                "bloom: threshold 0.75, soft knee 0.50, intensity 0.50",
                "modern Vulkan: sync2 enabled, dynamic rendering feature enabled, render-pass backend active",
                "barriers: 12 sync2 / 0 legacy",
                "descriptor writes: 4, binds: 8 calls / 10 sets, material cache: 6 hits / 2 misses",
                "command pool resets: 2 frame / 3 upload",
                "memory: 9 allocs (11 peak), 2048Kb live / 4096Kb peak",
                "Vulkan GPU timings:",
                "  frame begin -> main render pass begin: 0.125 ms",
            ]
        )

        info = vk_runtime_sweep.parse_vkinfo_text(text)

        self.assertTrue(info["found"])
        self.assertEqual(info["modernVulkan"]["sync2"], "enabled")
        self.assertEqual(info["barriers"]["sync2"], 12)
        self.assertEqual(info["displayHdr"]["state"], "requested unavailable")
        self.assertEqual(info["outputBackend"]["request"], "hdr10-pq")
        self.assertEqual(info["outputBackend"]["native"], "windows-scrgb")
        self.assertEqual(info["outputBackend"]["displayMax"], 812.0)
        self.assertEqual(info["toneMap"]["mode"], "ACES")
        self.assertEqual(info["bloom"]["softKnee"], 0.5)
        self.assertEqual(len(info["gpuTimings"]), 1)

    def test_vk_log_analysis_flags_missing_sync2_barriers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "vk.log"
            log.write_text(
                "\n".join(
                    [
                        "pipeline cache: cache/vkpc_123.bin, loaded: 1Kb, saved: 1Kb",
                        "display HDR: disabled, metadata: disabled, paper white 203 nits, max 1000 nits",
                        "output backend: request auto, selected sdr-srgb, native sdr-srgb, display HDR disabled, headroom 1.00, SDR white 203 nits, display max 203 nits, ICC no/0, driver windows, display SDR Panel, reason: test",
                        "tone map: legacy, exposure 1.00",
                        "bloom: threshold 0.75, soft knee 0.00, intensity 0.50",
                        "modern Vulkan: sync2 enabled, dynamic rendering disabled",
                        "barriers: 0 sync2 / 4 legacy",
                        "descriptor writes: 1, binds: 1 calls / 1 sets, material cache: 0 hits / 1 misses",
                        "command pool resets: 1 frame / 0 upload",
                        "memory: 1 allocs (1 peak), 1Kb live / 1Kb peak",
                    ]
                ),
                encoding="utf-8",
            )

            analysis = vk_runtime_sweep.analyze_vk_log(log, "vk-modern")

            self.assertTrue(
                any("sync2 is enabled" in failure for failure in analysis["failures"])
            )

    def test_hdr_profile_requires_visible_hdr_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "vk.log"
            log.write_text(
                "\n".join(
                    [
                        "pipeline cache: cache/vkpc_123.bin, loaded: 1Kb, saved: 1Kb",
                        "display HDR: disabled, metadata: disabled, paper white 203 nits, max 1000 nits",
                        "output backend: request hdr10-pq, selected sdr-srgb, native sdr-srgb, display HDR disabled, headroom 1.00, SDR white 203 nits, display max 203 nits, ICC no/0, driver windows, display SDR Panel, reason: test",
                        "tone map: ACES, exposure 1.00",
                        "bloom: threshold 0.75, soft knee 0.50, intensity 0.50",
                        "modern Vulkan: sync2 disabled, dynamic rendering disabled",
                        "barriers: 0 sync2 / 4 legacy",
                        "descriptor writes: 1, binds: 1 calls / 1 sets, material cache: 0 hits / 1 misses",
                        "command pool resets: 1 frame / 0 upload",
                        "memory: 1 allocs (1 peak), 1Kb live / 1Kb peak",
                    ]
                ),
                encoding="utf-8",
            )

            analysis = vk_runtime_sweep.analyze_vk_log(log, "vk-hdr")

            self.assertTrue(
                any("requested HDR display" in failure for failure in analysis["failures"])
            )


class VkRuntimeSweepGateTests(unittest.TestCase):
    def test_modern_gate_requires_gpu_timings_and_timedemo_metrics(self) -> None:
        manifest = {
            "gate": "vk-modern",
            "dryRun": False,
            "demos": ["demo1"],
            "runs": [
                {
                    "type": "map-screenshots",
                    "status": "passed",
                    "screenshots": [{"name": "shot", "found": True}],
                    "vkinfo": {
                        "failures": [],
                        "gpuTimings": [],
                    },
                },
                {
                    "type": "timedemo",
                    "status": "passed",
                    "demo": "demo1",
                },
            ],
        }

        failures = vk_runtime_sweep.evaluate_gate(manifest)

        self.assertTrue(any("GPU timing" in failure for failure in failures))
        self.assertTrue(any("Missing timedemo metrics" in failure for failure in failures))

    def test_dry_run_gate_is_planning_only(self) -> None:
        manifest = {
            "gate": "vk-modern",
            "dryRun": True,
            "demos": ["demo1"],
            "runs": [],
        }

        self.assertEqual(vk_runtime_sweep.evaluate_gate(manifest), [])

    def test_map_config_contains_vkinfo_and_timestamp_sampling(self) -> None:
        class Args:
            profile = "vk-modern"
            startup_wait = 30
            map_wait = 180
            screenshot_wait = 8
            perf_sample_wait = 4
            no_perf_samples = False

        cfg, screenshots = vk_runtime_sweep.build_map_cfg(
            Args(),
            {"r_fbo": "1"},
            ["q3dm1"],
            "run",
        )

        self.assertIn("vkinfo", cfg)
        self.assertIn('set r_speeds "7"', cfg)
        self.assertEqual(screenshots[0]["baselineKey"], "vk-modern-map1-q3dm1-vulkan")

    def test_modern_gate_requires_dlight_shadow_scene(self) -> None:
        manifest = {
            "gate": "vk-modern",
            "dryRun": False,
            "demos": ["demo1"],
            "runs": [
                {
                    "type": "map-screenshots",
                    "status": "passed",
                    "screenshots": [{"name": "shot", "found": True}],
                    "vkinfo": {
                        "failures": [],
                        "gpuTimings": [{"from": "a", "to": "b", "msec": 0.1}],
                    },
                },
                {
                    "type": "timedemo",
                    "status": "passed",
                    "demo": "demo1",
                    "timedemoMetrics": {"fps": 100.0},
                },
            ],
        }

        failures = vk_runtime_sweep.evaluate_gate(manifest)

        self.assertTrue(any("dlight shadow scene run" in failure for failure in failures))

    def test_dlight_shadow_config_uses_startup_cvars_and_test_lights(self) -> None:
        class Args:
            profile = "vk-modern"
            startup_wait = 30
            map_wait = 180
            screenshot_wait = 8
            perf_sample_wait = 4
            no_perf_samples = False

        cvars = vk_runtime_sweep.dlight_shadow_scene_cvars({"r_fbo": "1"})
        startup = vk_runtime_sweep.launch_cvars(cvars)
        scenes = vk_runtime_sweep.dlight_shadow_evidence_scenes()
        cfg, screenshots = vk_runtime_sweep.build_dlight_shadow_cfg(
            Args(),
            cvars,
            scenes,
            "run",
        )

        self.assertEqual(startup["r_dlightShadows"], "1")
        self.assertEqual(startup["r_dlightShadowMaxLights"], "8")
        self.assertIn("echo DLIGHT_SHADOW_SCENE_BEGIN world-geometry", cfg)
        self.assertIn("devmap q3dm6", cfg)
        self.assertIn("devmap q3dm11", cfg)
        self.assertIn("r_dlightTest 8 720 224 48 0", cfg)
        self.assertIn("r_dlightTest 16 900 256 72 0", cfg)
        self.assertIn('set r_speeds "4"', cfg)
        self.assertTrue(all(shot["shadowScene"] for shot in screenshots))
        self.assertEqual(
            vk_runtime_sweep.dlight_shadow_scene_categories(screenshots),
            set(vk_runtime_sweep.DLIGHT_SHADOW_EVIDENCE_CATEGORIES),
        )
        self.assertTrue(
            any(
                shot["baselineKey"] == "vk-modern-dlight-shadows-stress-light-budget-q3dm6-vulkan"
                for shot in screenshots
            )
        )

    def test_dlight_shadow_log_analysis_extracts_active_samples(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "vk.log"
            log.write_text(
                "\n".join(
                    [
                        "DLIGHT_SHADOW_SCENE_BEGIN world-geometry",
                        "dlight shadows plan:2/4 cand:3 atlas:1024x512/128 fill:75% "
                        "render lights:2 faces:10 batches:5 draws:5 surfs:20 cpu:1ms",
                        "DLIGHT_SHADOW_SCENE_END world-geometry",
                    ]
                ),
                encoding="utf-8",
            )

            analysis = vk_runtime_sweep.analyze_dlight_shadow_log(log)

        self.assertTrue(analysis["found"])
        self.assertEqual(analysis["max"]["planned"], 2)
        self.assertEqual(analysis["max"]["renderLights"], 2)
        self.assertEqual(analysis["scenes"]["world-geometry"]["max"]["planned"], 2)

    def test_modern_gate_requires_dlight_shadow_category_evidence(self) -> None:
        screenshots = [
            {
                "name": f"shot-{category}",
                "found": True,
                "shadowScene": True,
                "scene": category,
                "evidenceCategories": [category],
            }
            for category in vk_runtime_sweep.DLIGHT_SHADOW_EVIDENCE_CATEGORIES
        ]
        screenshots = [
            shot for shot in screenshots
            if shot["evidenceCategories"] != ["stress-light-budget"]
        ]
        manifest = {
            "gate": "vk-modern",
            "dryRun": False,
            "demos": ["demo1"],
            "runs": [
                {
                    "type": "map-screenshots",
                    "status": "passed",
                    "screenshots": [{"name": "shot", "found": True}],
                    "vkinfo": {
                        "failures": [],
                        "gpuTimings": [{"from": "a", "to": "b", "msec": 0.1}],
                    },
                },
                {
                    "type": "dlight-shadow-scenes",
                    "status": "passed",
                    "screenshots": screenshots,
                    "dlightShadow": {
                        "found": True,
                        "max": {"planned": 2, "renderLights": 2},
                        "scenes": {
                            str(shot["scene"]): {
                                "max": {"planned": 2, "renderLights": 2}
                            }
                            for shot in screenshots
                        },
                    },
                },
                {
                    "type": "timedemo",
                    "status": "passed",
                    "demo": "demo1",
                    "timedemoMetrics": {"fps": 100.0},
                },
            ],
        }

        failures = vk_runtime_sweep.evaluate_gate(manifest)

        self.assertTrue(any("stress-light-budget" in failure for failure in failures))


class VkRendererSourceTests(unittest.TestCase):
    def test_vulkan_depth_fade_msaa_fallback_and_depth_resolve_scaffolding(self) -> None:
        vk_c = (ROOT / "code" / "renderervk" / "vk.c").read_text(encoding="utf-8")
        vk_h = (ROOT / "code" / "renderervk" / "vk.h").read_text(encoding="utf-8")

        self.assertIn("VK_KHR_DEPTH_STENCIL_RESOLVE_EXTENSION_NAME", vk_c)
        self.assertIn("vkCreateRenderPass2KHR", vk_c)
        self.assertIn("vk_depth_fade_uses_depth_resolve", vk_c)
        self.assertIn("vk.depthStencilResolve", vk_c)
        self.assertIn("VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT", vk_c)
        self.assertIn("RENDER_PASS_MAIN_LOAD", vk_h)
        self.assertIn("vk_pipeline_render_pass_index", vk_c)
        self.assertIn("disabling MSAA so depth fade can use the single-sample depth copy path", vk_c)
        self.assertIn("vkSamples = VK_SAMPLE_COUNT_1_BIT", vk_c)
        self.assertIn("#define VK_DESC_DEPTH_FADE   VK_DESC_TEXTURE1", vk_h)

    def test_vulkan_depth_fade_matches_glx_single_texture_stage_rule(self) -> None:
        vk_shader = (ROOT / "code" / "renderervk" / "tr_shader.c").read_text(encoding="utf-8")
        vk_shade = (ROOT / "code" / "renderervk" / "tr_shade.c").read_text(encoding="utf-8")
        gen_frag = (ROOT / "code" / "renderervk" / "shaders" / "gen_frag.tmpl").read_text(encoding="utf-8")

        self.assertIn("pStage->bundle[1].image[0] == NULL && !pStage->depthFragment", vk_shader)
        self.assertIn("pStage->bundle[1].image[0] == NULL", vk_shade)
        self.assertIn("#define USE_DEPTH_FADE", gen_frag)
        self.assertIn("layout(set = 2, binding = 0) uniform sampler2D depth_texture", gen_frag)

    def test_vulkan_world_cel_outline_uses_opaque_cutoff(self) -> None:
        backend = (ROOT / "code" / "renderervk" / "tr_backend.c").read_text(encoding="utf-8")

        self.assertIn("if ( shader->sort > SS_OPAQUE ) {", backend)
        self.assertNotIn("if ( shader->sort >= SS_BLEND0 ) {", backend)


if __name__ == "__main__":
    unittest.main()

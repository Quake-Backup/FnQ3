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


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import importlib.util
import io
import json
import struct
import subprocess
import tempfile
import unittest
import zlib
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "rtx_runtime_smoke.py"

spec = importlib.util.spec_from_file_location("rtx_runtime_smoke", SCRIPT_PATH)
assert spec is not None
rtx_runtime_smoke = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(rtx_runtime_smoke)


def png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(payload, zlib.crc32(chunk_type)) & 0xFFFFFFFF
    return (
        struct.pack(">I", len(payload))
        + chunk_type
        + payload
        + struct.pack(">I", checksum)
    )


def paeth_predictor(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    distances = (
        abs(estimate - left),
        abs(estimate - above),
        abs(estimate - upper_left),
    )
    return (left, above, upper_left)[distances.index(min(distances))]


def encode_filtered_row(
    row: bytes,
    previous: bytes,
    filter_type: int,
    bytes_per_pixel: int,
) -> bytes:
    filtered = bytearray(len(row))
    for index, value in enumerate(row):
        left = row[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
        above = previous[index]
        upper_left = (
            previous[index - bytes_per_pixel] if index >= bytes_per_pixel else 0
        )
        if filter_type == 0:
            predictor = 0
        elif filter_type == 1:
            predictor = left
        elif filter_type == 2:
            predictor = above
        elif filter_type == 3:
            predictor = (left + above) // 2
        elif filter_type == 4:
            predictor = paeth_predictor(left, above, upper_left)
        else:
            raise ValueError(filter_type)
        filtered[index] = (value - predictor) & 0xFF
    return bytes([filter_type]) + filtered


def make_test_png(
    width: int,
    height: int,
    *,
    uniform: int | None = None,
    filter_types: tuple[int, ...] = (0,),
    white_fraction: float = 0.0,
    invert: bool = False,
) -> bytes:
    previous = bytes(width * 3)
    scanlines: list[bytes] = []
    white_pixels = int(width * height * white_fraction)
    for y in range(height):
        row = bytearray()
        for x in range(width):
            if y * width + x < white_pixels:
                red = green = blue = 255
            elif uniform is not None:
                red = green = blue = uniform
            else:
                red = (x * 31 + y * 17) & 0xFF
                green = (x * 13 + y * 47) & 0xFF
                blue = (x * 61 + y * 7) & 0xFF
                if invert:
                    red = 255 - red
                    green = 255 - green
                    blue = 255 - blue
            row.extend((red, green, blue))
        filter_type = filter_types[y % len(filter_types)]
        scanlines.append(
            encode_filtered_row(bytes(row), previous, filter_type, 3)
        )
        previous = bytes(row)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        rtx_runtime_smoke.PNG_SIGNATURE
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"IDAT", zlib.compress(b"".join(scanlines)))
        + png_chunk(b"IEND", b"")
    )


def healthy_log(profile_name: str) -> str:
    profile = rtx_runtime_smoke.PROFILE_SPECS[profile_name]
    lines = [
        "----- finished R_Init -----",
        "Vulkan: validation layer enabled (VK_LAYER_KHRONOS_validation)",
        (
            "RTX capability gate: "
            f"requested={profile['activeModeName']} ({profile['requestedMode']}), "
            f"active={profile['activeModeName']} ({profile['activeMode']}), "
            f"require={profile['require']}"
        ),
        f"RTX_SMOKE_PROFILE_BEGIN {profile_name}",
    ]
    for map_name in rtx_runtime_smoke.MAPS:
        lines.extend(
            [
                f"Server: {map_name}",
                f"RTX_SMOKE_SCENE_READY {profile_name} {map_name}",
            ]
        )
    lines.extend(
        [
            (
                rtx_runtime_smoke.Q3DM1_GLOBAL_FOG_MARKER
                + " (exp, density 0.000850, start 144.0, opacity 0.30, sky 1)"
            ),
            rtx_runtime_smoke.Q3DM1_STATIC_LIGHTS_MARKER,
        ]
    )
    if profile["requestedMode"] == 2:
        lines.extend(
            [
                rtx_runtime_smoke.RT_POST_STACK_MARKER,
                rtx_runtime_smoke.RT_NATIVE_DISPATCH_MARKER,
            ]
        )
    lines.append(f"RTX_SMOKE_PROFILE_END {profile_name}")
    return "\n".join(lines) + "\n"


def screenshot_records(found: bool = True, valid_png: bool = True) -> list[dict[str, object]]:
    return [
        {
            "name": f"shot-{map_name}",
            "map": map_name,
            "found": found,
            "validPng": valid_png,
            "pngMetrics": (
                {
                    "width": 960,
                    "height": 540,
                    "dimensionsMatch": True,
                    "nontrivial": True,
                    "luminanceRange": 180.0,
                    "luminanceVariance": 1200.0,
                    "valid": valid_png,
                    "error": None if valid_png else "validation failed",
                }
                if found
                else None
            ),
        }
        for map_name in rtx_runtime_smoke.MAPS
    ]


def passing_run(profile_name: str) -> dict[str, object]:
    profile = rtx_runtime_smoke.PROFILE_SPECS[profile_name]
    return {
        "profile": profile_name,
        "requestedMode": profile["requestedMode"],
        "require": profile["require"],
        "processStatus": "evidence_complete",
        "screenshots": screenshot_records(),
        "materialAudit": (
            {
                "status": "passed",
                "valid": True,
                "correlation": 0.9,
                "albedoDetailRms": 12.0,
                "error": None,
            }
            if profile["requestedMode"] == 2
            else {
                "status": "not_applicable",
                "valid": True,
            }
        ),
        "analysis": rtx_runtime_smoke.analyze_log_text(
            healthy_log(profile_name), profile_name
        ),
    }


class RtxRuntimeSmokeGateTests(unittest.TestCase):
    def test_gate_listing_is_deterministic(self) -> None:
        self.assertEqual(rtx_runtime_smoke.list_gate_names(), ["rtx-smoke"])

        output = io.StringIO()
        with redirect_stdout(output):
            rtx_runtime_smoke.print_gate_list()

        self.assertEqual(
            output.getvalue().splitlines(),
            [
                (
                    "rtx-smoke: Cross-platform RTX renderer smoke gate covering "
                    "raster fallback and strict native ray-tracing-pipeline operation."
                ),
                "  profiles=raster-fallback, rt-pipeline",
            ],
        )

    def test_dry_run_writes_isolated_profile_artifacts_and_feature_cvars(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            output_dir = temp / "output root"
            requested_summary = temp / "reports" / "rtx summary.md"
            args = rtx_runtime_smoke.create_parser().parse_args(
                [
                    "--dry-run",
                    "--output-dir",
                    str(output_dir),
                    "--summary-markdown",
                    str(requested_summary),
                    "--startup-wait",
                    "1",
                    "--map-wait",
                    "2",
                    "--screenshot-wait",
                    "3",
                    "--disconnect-wait",
                    "4",
                    "--width",
                    "800",
                    "--height",
                    "450",
                ]
            )

            exit_code, manifest_path, manifest = rtx_runtime_smoke.run_smoke(
                args, run_id="unit-dry-run"
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(manifest["status"], "planned")
            self.assertTrue(manifest_path.is_file())
            self.assertEqual(
                json.loads(manifest_path.read_text(encoding="utf-8"))["runId"],
                "unit-dry-run",
            )
            runs = manifest["runs"]
            self.assertEqual(
                [run["profile"] for run in runs],
                ["raster-fallback", "rt-pipeline"],
            )
            self.assertEqual(len({run["homepath"] for run in runs}), 2)
            self.assertEqual(len({run["fsGame"] for run in runs}), 2)

            expected_features = {
                "r_fbo": "1",
                "r_hdr": "1",
                "r_bloom": "1",
                "r_hudExcludePostProcess": "1",
                "r_depthFade": "1",
                "r_liquid": "2",
                "r_globalFog": "1",
                "r_staticLightDebug": "1",
                "r_staticLights": "1",
                "r_surfaceLightProxies": "1",
                "r_surfaceLightProxyMaxLights": "16",
                "r_tonemap": "1",
                "rtx_debug_vk_validation": "1",
                "rtx_rt_debug_visualizer": "0",
                "rtx_rt_indirect_bounce": "0",
                "rtx_rt_indirect_strength": "0.35",
                "rtx_rt_legacy_color_compat": "1",
                "rtx_rt_post_validate": "1",
                "rtx_rt_raster_reference": "0",
                "rtx_rt_reflection_strength": "1.0",
                "rtx_rt_sun_intensity": "2.5",
                "rtx_rt_world_light_scale": "0.35",
            }
            for run in runs:
                cvars = run["cvars"]
                for name, value in expected_features.items():
                    self.assertEqual(cvars[name], value)
                self.assertEqual(cvars["r_customWidth"], "800")
                self.assertEqual(cvars["r_customHeight"], "450")
                self.assertEqual(
                    cvars["rtx_rt_mode"], str(run["requestedMode"])
                )
                self.assertEqual(cvars["rtx_rt_require"], str(run["require"]))

                config_path = Path(run["config"])
                live_config_path = Path(run["liveConfig"])
                self.assertTrue(config_path.is_file())
                self.assertTrue(live_config_path.is_file())
                self.assertEqual(live_config_path.parent.name, run["fsGame"])
                config_text = config_path.read_text(encoding="utf-8")
                for map_name in rtx_runtime_smoke.MAPS:
                    self.assertIn(f"map {map_name}", config_text)
                    self.assertIn(
                        f"screenshotPNG rtxsmoke-"
                        f"{rtx_runtime_smoke.PROFILE_SPECS[run['profile']]['slug']}-"
                        f"{map_name}",
                        config_text,
                    )
                self.assertIn('set r_hdr "1"', config_text)
                self.assertIn('set r_bloom "1"', config_text)
                self.assertIn('set r_depthFade "1"', config_text)
                self.assertIn('set r_liquid "2"', config_text)
                self.assertIn('set r_surfaceLightProxies "1"', config_text)
                self.assertIn('set r_surfaceLightProxyMaxLights "16"', config_text)
                self.assertIn('set rtx_rt_legacy_color_compat "1"', config_text)
                self.assertIn('set rtx_rt_raster_reference "0"', config_text)
                self.assertIn("r_staticLightReload", config_text)
                if run["profile"] == "rt-pipeline":
                    self.assertIn(
                        'set rtx_rt_debug_visualizer "4"',
                        config_text,
                    )
                    self.assertIn(
                        "screenshotPNG rtxsmoke-rt-q3dm1-albedo",
                        config_text,
                    )
                    self.assertIn(
                        'set rtx_rt_debug_visualizer "0"',
                        config_text,
                    )
                    self.assertEqual(
                        run["materialAudit"]["status"],
                        "planned",
                    )
                    self.assertEqual(
                        run["materialAudit"]["screenshot"]["kind"],
                        "material-albedo",
                    )
                else:
                    self.assertEqual(
                        run["materialAudit"]["status"],
                        "not_applicable",
                    )

                self.assertEqual(len(run["sidecars"]), 2)
                sidecars_by_kind = {
                    sidecar["kind"]: sidecar for sidecar in run["sidecars"]
                }
                fog_path = Path(sidecars_by_kind["globalFog"]["path"])
                lights_path = Path(sidecars_by_kind["staticLights"]["path"])
                self.assertEqual(fog_path.parent, live_config_path.parent / "maps")
                self.assertEqual(lights_path.parent, live_config_path.parent / "maps")
                self.assertIn(
                    "density 0.00085",
                    fog_path.read_text(encoding="utf-8"),
                )
                lights = json.loads(lights_path.read_text(encoding="utf-8"))
                self.assertEqual(lights["version"], 1)
                self.assertEqual(len(lights["lights"]), 2)
                self.assertEqual(
                    sidecars_by_kind["staticLights"]["lightCount"],
                    2,
                )

                self.assertTrue(Path(run["processLog"]).is_file())
                self.assertTrue(Path(run["qconsoleLog"]).is_file())
                self.assertTrue(Path(run["combinedLog"]).is_file())
                self.assertEqual(len(run["screenshots"]), 2)
                for screenshot in run["screenshots"]:
                    self.assertEqual(screenshot["status"], "planned")
                    self.assertFalse(screenshot["found"])
                    self.assertFalse(Path(screenshot["artifactPath"]).exists())

                command = run["command"]
                self.assertIsInstance(command, list)
                self.assertIn("cl_renderer", command)
                self.assertIn("rtx", command)
                self.assertIn(run["fsGame"], command)
                self.assertIn("fs_steampath", command)
                self.assertIn("fs_cdpath", command)
                for name in rtx_runtime_smoke.STARTUP_CVARS:
                    index = command.index(name)
                    self.assertEqual(command[index - 1], "+set")
                    self.assertEqual(command[index + 1], cvars[name])
                self.assertLessEqual(
                    sum(
                        1
                        for argument in command
                        if argument.startswith("+")
                    ),
                    rtx_runtime_smoke.MAX_STARTUP_COMMANDS,
                )

            raster, ray_traced = runs
            self.assertEqual((raster["requestedMode"], raster["require"]), (0, 0))
            self.assertEqual((ray_traced["requestedMode"], ray_traced["require"]), (2, 1))

            for summary_path in manifest["summaryMarkdown"]:
                self.assertTrue(Path(summary_path).is_file())
            self.assertTrue(requested_summary.is_file())
            self.assertIn(
                "| raster-fallback | 0 | 0 | planned | 2 planned |",
                requested_summary.read_text(encoding="utf-8"),
            )

    def test_log_analysis_and_gate_evaluation_accept_complete_evidence(self) -> None:
        runs = []
        for profile_name in ("raster-fallback", "rt-pipeline"):
            analysis = rtx_runtime_smoke.analyze_log_text(
                healthy_log(profile_name), profile_name
            )
            self.assertEqual(analysis["failures"], [])
            self.assertTrue(analysis["validationEnabled"])
            self.assertEqual(
                analysis["rtPostStack"], profile_name == "rt-pipeline"
            )
            self.assertEqual(
                analysis["rtNativeDispatch"], profile_name == "rt-pipeline"
            )
            runs.append(passing_run(profile_name))

        manifest = {
            "gate": "rtx-smoke",
            "dryRun": False,
            "runs": runs,
        }
        self.assertEqual(rtx_runtime_smoke.evaluate_gate(manifest), [])

    def test_evaluation_rejects_missing_screenshot_validation_and_rt_markers(self) -> None:
        raster = passing_run("raster-fallback")
        raster["screenshots"] = screenshot_records(found=False)

        rt = passing_run("rt-pipeline")
        broken_log = healthy_log("rt-pipeline").replace(
            "Vulkan: validation layer enabled (VK_LAYER_KHRONOS_validation)\n", ""
        ).replace(
            rtx_runtime_smoke.RT_POST_STACK_MARKER + "\n", ""
        ).replace(
            rtx_runtime_smoke.RT_NATIVE_DISPATCH_MARKER + "\n", ""
        )
        rt["analysis"] = rtx_runtime_smoke.analyze_log_text(
            broken_log, "rt-pipeline"
        )

        failures = rtx_runtime_smoke.evaluate_gate(
            {
                "gate": "rtx-smoke",
                "dryRun": False,
                "runs": [raster, rt],
            }
        )
        joined = "\n".join(failures)
        self.assertIn("Missing screenshots", joined)
        self.assertIn("validation-layer enablement marker", joined)
        self.assertIn("RT post-stack validation marker", joined)
        self.assertIn("Native RTX primary-dispatch/copy", joined)

    def test_evaluation_rejects_failed_native_material_detail_audit(self) -> None:
        raster = passing_run("raster-fallback")
        rt = passing_run("rt-pipeline")
        rt["materialAudit"] = {
            "status": "failed",
            "valid": False,
            "correlation": 0.01,
            "albedoDetailRms": 18.0,
            "error": "authored albedo detail did not survive native RT shading",
        }

        failures = rtx_runtime_smoke.evaluate_gate(
            {
                "gate": "rtx-smoke",
                "dryRun": False,
                "runs": [raster, rt],
            }
        )

        self.assertIn(
            "RT material-detail audit failed",
            "\n".join(failures),
        )

    def test_log_analysis_rejects_missing_startup_and_map_markers(self) -> None:
        broken_log = healthy_log("raster-fallback").replace(
            "----- finished R_Init -----\n", ""
        ).replace("Server: q3dm8\n", "")
        analysis = rtx_runtime_smoke.analyze_log_text(
            broken_log, "raster-fallback"
        )
        joined = "\n".join(analysis["failures"])
        self.assertIn("Missing startup markers", joined)
        self.assertIn("Missing map-load markers: q3dm8", joined)

    def test_log_analysis_requires_deterministic_sidecar_load_evidence(self) -> None:
        broken_log = healthy_log("rt-pipeline").replace(
            rtx_runtime_smoke.Q3DM1_GLOBAL_FOG_MARKER,
            "Global fog marker removed",
        ).replace(
            rtx_runtime_smoke.Q3DM1_STATIC_LIGHTS_MARKER,
            "Static light marker removed",
        )

        analysis = rtx_runtime_smoke.analyze_log_text(
            broken_log,
            "rt-pipeline",
        )

        self.assertEqual(
            analysis["sidecarEvidence"],
            {
                "q3dm1GlobalFog": False,
                "q3dm1StaticLights": False,
            },
        )
        joined = "\n".join(analysis["failures"])
        self.assertIn("Missing deterministic sidecar evidence", joined)


class RtxRuntimeSmokeSafetyTests(unittest.TestCase):
    def test_launch_command_keeps_paths_as_individual_arguments(self) -> None:
        exe = Path(r"C:\Program Files\FnQ3;test\fnquake3.exe")
        basepath = Path(r"D:\Games\Quake III Arena;retail")
        homepath = Path(r"E:\scratch homes\rtx;isolated")
        cvars = rtx_runtime_smoke.profile_cvars("rt-pipeline", 960, 540)
        command = rtx_runtime_smoke.build_launch_command(
            exe,
            basepath,
            homepath,
            "rtx_smoke_rt",
            "rtx-smoke-rt.cfg",
            cvars,
        )

        self.assertIsInstance(command, list)
        self.assertEqual(command[0], str(exe))
        self.assertIn(str(basepath), command)
        self.assertIn(str(homepath), command)
        self.assertNotIn("shell", command)
        for name in rtx_runtime_smoke.STARTUP_CVARS:
            index = command.index(name)
            self.assertEqual(command[index - 1], "+set")
            self.assertEqual(command[index + 1], cvars[name])
        self.assertLessEqual(
            sum(1 for argument in command if argument.startswith("+")),
            rtx_runtime_smoke.MAX_STARTUP_COMMANDS,
        )
        self.assertEqual(command[-2:], ["+exec", "rtx-smoke-rt.cfg"])

    def test_launch_command_rejects_missing_lifecycle_sensitive_cvars(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "Missing lifecycle-sensitive startup cvars"
        ):
            rtx_runtime_smoke.build_launch_command(
                Path("fnquake3"),
                Path("base"),
                Path("home"),
                "rtx_smoke_rt",
                "rtx-smoke-rt.cfg",
                {"rtx_rt_mode": "2", "rtx_rt_require": "1"},
            )

    def test_engine_launch_uses_subprocess_argument_list_without_shell(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "process.log"
            command = ["fnquake3", "+set", "fs_homepath", "path with spaces;safe"]
            process = mock.Mock()
            process.pid = 1234
            process.poll.return_value = 0

            with mock.patch.object(
                rtx_runtime_smoke.subprocess, "Popen", return_value=process
            ) as popen_mock:
                result = rtx_runtime_smoke.run_engine(
                    command,
                    Path(temp_dir),
                    10.0,
                    log_path,
                    dry_run=False,
                    evidence_probe=lambda: False,
                    poll_interval=0.0,
                )

            called_command = popen_mock.call_args.args[0]
            called_options = popen_mock.call_args.kwargs
            self.assertEqual(called_command, command)
            self.assertIsInstance(called_command, list)
            self.assertNotIn("shell", called_options)
            self.assertEqual(result["status"], "exited_before_evidence")
            self.assertEqual(result["pid"], 1234)
            self.assertTrue(log_path.is_file())

    def test_process_exit_rechecks_final_flushed_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "process.log"
            process = mock.Mock()
            process.pid = 2468
            process.poll.return_value = 0
            evidence_probe = mock.Mock(side_effect=[False, True])

            with mock.patch.object(
                rtx_runtime_smoke.subprocess, "Popen", return_value=process
            ):
                result = rtx_runtime_smoke.run_engine(
                    ["fnquake3"],
                    Path(temp_dir),
                    10.0,
                    log_path,
                    dry_run=False,
                    evidence_probe=evidence_probe,
                    poll_interval=0.0,
                )

            self.assertEqual(result["status"], "evidence_complete")
            self.assertEqual(result["cleanupAction"], "already_exited")
            self.assertEqual(result["returncode"], 0)
            self.assertEqual(evidence_probe.call_count, 2)
            process.terminate.assert_not_called()
            process.kill.assert_not_called()

    def test_nonzero_process_exit_cannot_pass_with_complete_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "process.log"
            process = mock.Mock()
            process.pid = 1357
            process.poll.return_value = 7

            with mock.patch.object(
                rtx_runtime_smoke.subprocess, "Popen", return_value=process
            ):
                result = rtx_runtime_smoke.run_engine(
                    ["fnquake3"],
                    Path(temp_dir),
                    10.0,
                    log_path,
                    dry_run=False,
                    evidence_probe=lambda: True,
                    poll_interval=0.0,
                )

            self.assertEqual(result["status"], "exited_with_error")
            self.assertEqual(result["cleanupAction"], "already_exited")
            self.assertEqual(result["returncode"], 7)
            process.terminate.assert_not_called()
            process.kill.assert_not_called()

    def test_final_evidence_probe_oserror_remains_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "process.log"
            process = mock.Mock()
            process.pid = 8642
            process.poll.return_value = 0
            evidence_probe = mock.Mock(
                side_effect=[False, OSError("screenshot still locked")]
            )

            with mock.patch.object(
                rtx_runtime_smoke.subprocess, "Popen", return_value=process
            ):
                result = rtx_runtime_smoke.run_engine(
                    ["fnquake3"],
                    Path(temp_dir),
                    10.0,
                    log_path,
                    dry_run=False,
                    evidence_probe=evidence_probe,
                    poll_interval=0.0,
                )

            self.assertEqual(result["status"], "exited_before_evidence")
            self.assertEqual(result["cleanupAction"], "already_exited")
            self.assertEqual(result["returncode"], 0)
            self.assertEqual(evidence_probe.call_count, 2)

    def test_nonzero_natural_exit_after_evidence_is_a_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "process.log"
            process = mock.Mock()
            process.pid = 9753
            process.poll.side_effect = [None, None, 9, 9]
            process.wait.return_value = 9

            with mock.patch.object(
                rtx_runtime_smoke.subprocess, "Popen", return_value=process
            ):
                result = rtx_runtime_smoke.run_engine(
                    ["fnquake3"],
                    Path(temp_dir),
                    10.0,
                    log_path,
                    dry_run=False,
                    evidence_probe=lambda: True,
                    poll_interval=0.0,
                    exit_grace=0.0,
                )

            self.assertEqual(result["status"], "exited_with_error")
            self.assertEqual(result["cleanupAction"], "natural_exit")
            self.assertEqual(result["returncode"], 9)
            process.terminate.assert_not_called()
            process.kill.assert_not_called()

    def test_engine_launch_error_is_recorded_instead_of_escaping(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "process.log"
            with mock.patch.object(
                rtx_runtime_smoke.subprocess,
                "Popen",
                side_effect=OSError("not executable"),
            ):
                result = rtx_runtime_smoke.run_engine(
                    ["fnquake3"],
                    Path(temp_dir),
                    10.0,
                    log_path,
                    dry_run=False,
                )

            self.assertEqual(result["status"], "failed")
            self.assertIn("OSError: not executable", result["launchError"])
            self.assertIn(
                "LAUNCH ERROR: OSError: not executable",
                log_path.read_text(encoding="utf-8"),
            )

    def test_complete_evidence_terminates_only_the_launched_process(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "process.log"
            process = mock.Mock()
            process.pid = 4321
            process.poll.return_value = None
            process.wait.side_effect = [
                subprocess.TimeoutExpired(["fnquake3"], 0.0),
                0,
            ]

            with mock.patch.object(
                rtx_runtime_smoke.subprocess, "Popen", return_value=process
            ):
                result = rtx_runtime_smoke.run_engine(
                    ["fnquake3"],
                    Path(temp_dir),
                    10.0,
                    log_path,
                    dry_run=False,
                    evidence_probe=lambda: True,
                    poll_interval=0.0,
                    exit_grace=0.0,
                    cleanup_timeout=0.0,
                )

            self.assertEqual(result["status"], "evidence_complete")
            self.assertEqual(result["cleanupAction"], "terminated")
            self.assertEqual(result["pid"], 4321)
            process.terminate.assert_called_once_with()
            process.kill.assert_not_called()

    def test_timeout_without_evidence_cleans_up_and_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "process.log"
            process = mock.Mock()
            process.pid = 9876
            process.poll.return_value = None
            process.wait.return_value = 0

            with mock.patch.object(
                rtx_runtime_smoke.subprocess, "Popen", return_value=process
            ), mock.patch.object(
                rtx_runtime_smoke.time, "monotonic", side_effect=[0.0, 2.0]
            ):
                result = rtx_runtime_smoke.run_engine(
                    ["fnquake3"],
                    Path(temp_dir),
                    1.0,
                    log_path,
                    dry_run=False,
                    evidence_probe=lambda: False,
                    poll_interval=0.0,
                    cleanup_timeout=0.0,
                )

            self.assertEqual(result["status"], "timed_out_before_evidence")
            self.assertEqual(result["cleanupAction"], "terminated")
            process.terminate.assert_called_once_with()
            self.assertIn(
                "TIMEOUT before evidence",
                log_path.read_text(encoding="utf-8"),
            )

    def test_runtime_option_validation_rejects_invalid_timeout_and_waits(self) -> None:
        parser = rtx_runtime_smoke.create_parser()
        for argv in (
            ["--dry-run", "--timeout", "nan"],
            ["--dry-run", "--timeout", "0"],
            ["--dry-run", "--map-wait", "-1"],
            ["--dry-run", "--width", "0"],
        ):
            with self.subTest(argv=argv):
                args = parser.parse_args(argv)
                with self.assertRaises(ValueError):
                    rtx_runtime_smoke.validate_options(args)


class RtxRuntimeSmokeErrorDetectionTests(unittest.TestCase):
    def test_error_patterns_are_promoted_to_profile_failures(self) -> None:
        cases = {
            "vuid": "VUID-vkCmdDraw-renderPass-02684",
            "vulkan-validation": "Vulkan validation (error): descriptor mismatch",
            "fatal": "Fatal error: renderer startup aborted",
            "device-loss": "GPU device lost while submitting the frame",
            "vk-error": "vkQueueSubmit returned VK_ERROR_OUT_OF_DEVICE_MEMORY",
            "raster-fallback": (
                "RTX RT: output blit path unavailable; preserving the complete "
                "raster frame"
            ),
        }
        base = healthy_log("rt-pipeline")
        for expected_kind, error_line in cases.items():
            with self.subTest(expected_kind=expected_kind):
                analysis = rtx_runtime_smoke.analyze_log_text(
                    base + error_line + "\n", "rt-pipeline"
                )
                kinds = [error["kind"] for error in analysis["errorLines"]]
                self.assertIn(expected_kind, kinds)
                self.assertTrue(
                    any(error_line in failure for failure in analysis["failures"])
                )

    def test_png_validation_decodes_all_scanline_filters_and_reports_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            png = root / "valid.png"
            png.write_bytes(
                make_test_png(
                    16,
                    10,
                    filter_types=(0, 1, 2, 3, 4),
                )
            )

            metrics = rtx_runtime_smoke.inspect_png(png, 16, 10)

            self.assertTrue(metrics["valid"])
            self.assertTrue(metrics["structurallyValid"])
            self.assertTrue(metrics["crcValidated"])
            self.assertTrue(metrics["dimensionsMatch"])
            self.assertTrue(metrics["nontrivial"])
            self.assertTrue(metrics["notBlownOut"])
            self.assertEqual(metrics["scanlineFilters"], [0, 1, 2, 3, 4])
            self.assertEqual(metrics["pixelCount"], 160)
            self.assertGreaterEqual(
                metrics["luminanceRange"],
                rtx_runtime_smoke.PNG_MIN_LUMINANCE_RANGE,
            )
            self.assertGreaterEqual(
                metrics["luminanceVariance"],
                rtx_runtime_smoke.PNG_MIN_LUMINANCE_VARIANCE,
            )
            self.assertTrue(rtx_runtime_smoke.is_valid_png(png, 16, 10))

    def test_png_validation_rejects_excessive_near_white_clipping(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            png = Path(temp_dir) / "clipped.png"
            png.write_bytes(make_test_png(20, 20, white_fraction=0.40))

            metrics = rtx_runtime_smoke.inspect_png(png, 20, 20)

            self.assertTrue(metrics["structurallyValid"])
            self.assertTrue(metrics["nontrivial"])
            self.assertFalse(metrics["notBlownOut"])
            self.assertFalse(metrics["valid"])
            self.assertGreater(
                metrics["nearWhiteFraction"],
                rtx_runtime_smoke.PNG_MAX_NEAR_WHITE_FRACTION,
            )
            self.assertIn("near-white clipping", metrics["error"])

    def test_png_validation_rejects_bad_structure_crc_and_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            empty = root / "empty.png"
            empty.write_bytes(b"")
            text = root / "text.png"
            text.write_bytes(b"not a png")
            valid_bytes = make_test_png(16, 10)
            crc_bad = root / "crc-bad.png"
            corrupt = bytearray(valid_bytes)
            corrupt[-1] ^= 0xFF
            crc_bad.write_bytes(corrupt)
            partial = root / "partial.png"
            partial.write_bytes(valid_bytes[:-4])
            wrong_size = root / "wrong-size.png"
            wrong_size.write_bytes(valid_bytes)

            self.assertFalse(rtx_runtime_smoke.is_valid_png(empty))
            self.assertFalse(rtx_runtime_smoke.is_valid_png(text))
            self.assertFalse(rtx_runtime_smoke.is_valid_png(partial))
            self.assertFalse(rtx_runtime_smoke.is_valid_png(crc_bad))
            dimensions = rtx_runtime_smoke.inspect_png(wrong_size, 15, 10)
            self.assertFalse(dimensions["valid"])
            self.assertFalse(dimensions["dimensionsMatch"])
            self.assertIn("dimensions", dimensions["error"])

    def test_png_validation_rejects_uniform_frames_and_collects_evidence_metrics(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            homepath = root / "home"
            fs_game = "rtx_smoke_rt"
            screenshot_dir = homepath / fs_game / "screenshots"
            screenshot_dir.mkdir(parents=True)
            expected = []
            for index, map_name in enumerate(rtx_runtime_smoke.MAPS):
                name = f"evidence-{map_name}"
                expected.append(
                    {
                        "name": name,
                        "map": map_name,
                        "profile": "rt-pipeline",
                    }
                )
                (screenshot_dir / f"{name}.png").write_bytes(
                    make_test_png(
                        16,
                        10,
                        uniform=32 if index == 0 else None,
                    )
                )

            records = rtx_runtime_smoke.collect_screenshots(
                homepath,
                fs_game,
                "rt-pipeline",
                expected,
                root / "artifacts",
                False,
                16,
                10,
            )

            self.assertEqual(len(records), 2)
            uniform, varied = records
            self.assertTrue(uniform["found"])
            self.assertFalse(uniform["validPng"])
            self.assertFalse(uniform["pngMetrics"]["nontrivial"])
            self.assertEqual(uniform["pngMetrics"]["luminanceRange"], 0.0)
            self.assertIn("too uniform", uniform["pngMetrics"]["error"])
            self.assertTrue(varied["validPng"])
            self.assertTrue(varied["pngMetrics"]["dimensionsMatch"])
            self.assertGreater(varied["pngMetrics"]["luminanceVariance"], 0.0)
            self.assertTrue(Path(varied["artifactPath"]).is_file())

    def test_material_audit_correlates_authored_detail_without_raster_identity(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            beauty = root / "beauty.png"
            albedo = root / "albedo.png"
            flat = root / "flat.png"
            inverted = root / "inverted.png"
            beauty.write_bytes(make_test_png(128, 72))
            albedo.write_bytes(make_test_png(128, 72))
            flat.write_bytes(make_test_png(128, 72, uniform=48))
            inverted.write_bytes(make_test_png(128, 72, invert=True))

            audit = rtx_runtime_smoke.inspect_material_audit(
                beauty,
                albedo,
                128,
                72,
            )
            flat_audit = rtx_runtime_smoke.inspect_material_audit(
                beauty,
                flat,
                128,
                72,
            )
            inverted_audit = rtx_runtime_smoke.inspect_material_audit(
                beauty,
                inverted,
                128,
                72,
            )

            self.assertTrue(audit["valid"])
            self.assertGreaterEqual(
                audit["correlation"],
                rtx_runtime_smoke.MATERIAL_AUDIT_MIN_CORRELATION,
            )
            self.assertGreaterEqual(
                audit["albedoDetailRms"],
                rtx_runtime_smoke.MATERIAL_AUDIT_MIN_ALBEDO_DETAIL_RMS,
            )
            self.assertFalse(flat_audit["valid"])
            self.assertIn(
                "requires valid beauty and albedo PNG evidence",
                flat_audit["error"],
            )
            self.assertFalse(inverted_audit["valid"])
            self.assertFalse(inverted_audit["correlationPass"])


if __name__ == "__main__":
    unittest.main()

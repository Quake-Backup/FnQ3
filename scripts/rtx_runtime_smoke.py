from __future__ import annotations

import argparse
import json
import math
import os
import platform
import re
import shlex
import shutil
import struct
import subprocess
import sys
import time
import zlib
from array import array
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / ".tmp" / "rtx-runtime-smoke"
MAPS = ("q3dm8", "q3dm1")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_MAX_PIXELS = 64 * 1024 * 1024
PNG_MIN_LUMINANCE_RANGE = 8.0
PNG_MIN_LUMINANCE_VARIANCE = 4.0
PNG_MAX_NEAR_WHITE_FRACTION = 0.25
MATERIAL_AUDIT_ROI = (0.5521, 0.5093, 0.6510, 0.7037)
MATERIAL_AUDIT_REFERENCE_HEIGHT = 540
MATERIAL_AUDIT_BLUR_RADIUS = 4
MATERIAL_AUDIT_ALIGNMENT_RADIUS = 2
MATERIAL_AUDIT_MIN_CORRELATION = 0.40
MATERIAL_AUDIT_MIN_ALBEDO_DETAIL_RMS = 3.0
PNG_COLOR_CHANNELS = {
    0: 1,  # grayscale
    2: 3,  # RGB
    4: 2,  # grayscale + alpha
    6: 4,  # RGBA
}
_PNG_METRIC_CACHE: dict[tuple[str, int, int], dict[str, object]] = {}
_PNG_LUMINANCE_CACHE: dict[
    tuple[str, int, int],
    tuple[int, int, array],
] = {}

Q3DM1_FOG_SIDECAR = """// Isolated RTX parity smoke profile.
color 0.22 0.27 0.34
mode exp
density 0.00085
start 144
opacity 0.30
sky 1
"""
Q3DM1_LIGHTS_SIDECAR: dict[str, object] = {
    "format": "fnquake3-world-dlights",
    "version": 1,
    "metadata": {
        "purpose": "isolated RTX parity runtime validation",
    },
    "lights": [
        {
            "name": "validation-point",
            "type": "point",
            "origin": [0, 0, 256],
            "color": [255, 96, 32],
            "intensity": 1536,
            "radius": 2048,
            "priority": 8,
            "castsShadows": True,
        },
        {
            "name": "validation-linear",
            "type": "spot",
            "origin": [128, 0, 512],
            "direction": [0, 0, -1],
            "color": [0.25, 0.5, 1.0],
            "intensity": 1024,
            "radius": 2048,
            "innerAngle": 18,
            "outerAngle": 48,
            "priority": 4,
            "castsShadows": False,
        },
    ],
}

COMMON_CVARS = {
    "com_introplayed": "1",
    "developer": "1",
    "logfile": "2",
    "r_bloom": "1",
    "r_bloom_intensity": "0.5",
    "r_bloom_soft_knee": "0.5",
    "r_bloom_threshold": "0.75",
    "r_customHeight": "540",
    "r_customWidth": "960",
    "r_depthFade": "1",
    "r_ext_multisample": "0",
    "r_fbo": "1",
    "r_fullscreen": "0",
    "r_globalFog": "1",
    "r_globalFogStrength": "1.0",
    "r_hdr": "1",
    "r_hdrPrecision": "0",
    "r_hudExcludePostProcess": "1",
    "r_liquid": "2",
    "r_liquidResolution": "1.0",
    "r_liquidRipples": "1.0",
    "r_mode": "-1",
    "r_srgbTextures": "1",
    "r_staticLightDebug": "1",
    "r_dlightLoadWorld": "1",
    "r_surfaceLightProxies": "1",
    "r_surfaceLightProxyMaxLights": "16",
    "r_swapInterval": "0",
    "r_tonemap": "1",
    "r_tonemapExposure": "1.0",
    "rtx_caps_report": "2",
    "rtx_debug_vk_validation": "1",
    "rtx_rt_debug_visualizer": "0",
    "rtx_rt_dynamic_blas": "0",
    "rtx_rt_dynamic_resolution": "0",
    "rtx_rt_indirect_bounce": "0",
    "rtx_rt_indirect_strength": "0.35",
    "rtx_rt_legacy_color_compat": "1",
    "rtx_rt_post_validate": "1",
    "rtx_rt_raster_reference": "0",
    "rtx_rt_reflection_strength": "1.0",
    "rtx_rt_spatial_denoise": "0",
    "rtx_rt_sun_intensity": "2.5",
    "rtx_rt_world_light_scale": "0.35",
    "s_initsound": "0",
}

# Quake III applies +set commands before client/renderer initialization, while
# the later +exec runs after the first renderer has already been created. Keep
# lifecycle-sensitive settings on the bounded startup line as well as in the
# generated profile so the first renderer instance is the one under test.
STARTUP_CVARS = (
    "com_introplayed",
    "developer",
    "logfile",
    "s_initsound",
    "r_mode",
    "r_customWidth",
    "r_customHeight",
    "r_fullscreen",
    "r_fbo",
    "r_hdr",
    "r_hdrPrecision",
    "r_srgbTextures",
    "r_ext_multisample",
    "r_swapInterval",
    "rtx_debug_vk_validation",
    "rtx_caps_report",
    "rtx_rt_mode",
    "rtx_rt_require",
)
MAX_STARTUP_COMMANDS = 32

PROFILE_SPECS: dict[str, dict[str, object]] = {
    "raster-fallback": {
        "slug": "raster",
        "description": "RTX renderer raster fallback with optional RT capabilities disabled.",
        "requestedMode": 0,
        "activeMode": 0,
        "activeModeName": "disabled",
        "require": 0,
    },
    "rt-pipeline": {
        "slug": "rt",
        "description": "Strict native hardware ray-tracing pipeline with the shared post stack.",
        "requestedMode": 2,
        "activeMode": 2,
        "activeModeName": "ray_tracing_pipeline",
        "require": 1,
    },
}

GATE_PRESETS: dict[str, dict[str, object]] = {
    "rtx-smoke": {
        "description": (
            "Cross-platform RTX renderer smoke gate covering raster fallback and "
            "strict native ray-tracing-pipeline operation."
        ),
        "profiles": ("raster-fallback", "rt-pipeline"),
    },
}

CAPABILITY_RE = re.compile(
    r"RTX capability gate:\s*"
    r"requested=(?P<requestedName>[A-Za-z0-9_]+)\s+\((?P<requested>\d+)\),\s*"
    r"active=(?P<activeName>[A-Za-z0-9_]+)\s+\((?P<active>\d+)\),\s*"
    r"require=(?P<require>\d+)",
    re.IGNORECASE,
)
VALIDATION_ENABLED_RE = re.compile(
    r"Vulkan:\s*validation layer enabled\s*\((?P<layer>[^)]+)\)",
    re.IGNORECASE,
)
RT_POST_STACK_MARKER = "RTX RT post stack validation: trace->copy->post_bloom->gamma ordering active"
RT_NATIVE_DISPATCH_MARKER = (
    "RTX RT primary dispatch validation: vkCmdTraceRaysKHR output copied to "
    "scene color; shading=native_rt; raster_role=depth_fallback_overlay"
)
Q3DM1_GLOBAL_FOG_MARKER = "Global fog: loaded maps/q3dm1.fog"
Q3DM1_STATIC_LIGHTS_MARKER = (
    "Reloaded 2 world dlights from maps/q3dm1.dlight"
)

ERROR_PATTERNS = (
    ("vuid", re.compile(r"\bVUID-[A-Za-z0-9_.-]+", re.IGNORECASE)),
    (
        "vulkan-validation",
        re.compile(r"\bVulkan validation\s*\(|\bvalidation error\b", re.IGNORECASE),
    ),
    (
        "fatal",
        re.compile(r"\bERR_FATAL\b|\bfatal(?: error)?\b|\brecursive error\b", re.IGNORECASE),
    ),
    (
        "device-loss",
        re.compile(r"\bdevice[- ]?lost\b|VK_ERROR_DEVICE_LOST", re.IGNORECASE),
    ),
    ("vk-error", re.compile(r"\bVK_ERROR_[A-Z0-9_]+\b", re.IGNORECASE)),
    (
        "raster-fallback",
        re.compile(r"preserving the complete raster frame", re.IGNORECASE),
    ),
)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run or plan the focused FnQuake3 RTX runtime smoke gate."
    )
    parser.add_argument("--gate", choices=sorted(GATE_PRESETS), default="rtx-smoke")
    parser.add_argument("--list-gates", action="store_true")
    parser.add_argument("--exe", type=Path, help="FnQuake3 executable to launch.")
    parser.add_argument(
        "--basepath",
        type=Path,
        help="Retail Quake III asset basepath. Defaults to the executable directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Root for isolated homes, configs, logs, screenshots, and reports.",
    )
    parser.add_argument(
        "--summary-markdown",
        type=Path,
        help="Optional second location for the generated Markdown summary.",
    )
    parser.add_argument("--timeout", type=float, default=240.0, help="Seconds per profile.")
    parser.add_argument(
        "--startup-wait",
        type=int,
        default=30,
        help="Quake wait frames before the first map.",
    )
    parser.add_argument(
        "--map-wait",
        type=int,
        default=180,
        help="Quake wait frames after each map command.",
    )
    parser.add_argument(
        "--screenshot-wait",
        type=int,
        default=12,
        help="Quake wait frames after each screenshot request.",
    )
    parser.add_argument(
        "--disconnect-wait",
        type=int,
        default=20,
        help="Quake wait frames between maps.",
    )
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write every planned artifact without launching the engine.",
    )
    return parser


def list_gate_names() -> list[str]:
    return sorted(GATE_PRESETS)


def print_gate_list() -> None:
    for name in list_gate_names():
        gate = GATE_PRESETS[name]
        profiles = ", ".join(str(item) for item in gate["profiles"])
        print(f"{name}: {gate['description']}")
        print(f"  profiles={profiles}")


def validate_options(args: argparse.Namespace) -> None:
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ValueError("--timeout must be finite and positive")
    for name in ("startup_wait", "map_wait", "screenshot_wait", "disconnect_wait"):
        if getattr(args, name) < 0:
            raise ValueError(f"--{name.replace('_', '-')} must be non-negative")
    if args.width <= 0 or args.height <= 0:
        raise ValueError("--width and --height must be positive")


def resolve_executable(path: Path | None, dry_run: bool) -> Path:
    if path is None:
        if not dry_run:
            raise ValueError("--exe is required unless --dry-run is used")
        placeholder = "fnquake3.x64.exe" if os.name == "nt" else "fnquake3"
        return (DEFAULT_OUTPUT_DIR / placeholder).resolve()

    resolved = path.resolve()
    if not dry_run and not resolved.is_file():
        raise FileNotFoundError(f"Executable does not exist: {resolved}")
    return resolved


def resolve_basepath(path: Path | None, exe: Path, dry_run: bool) -> Path:
    resolved = path.resolve() if path else exe.parent.resolve()
    if not dry_run and not resolved.is_dir():
        raise FileNotFoundError(f"Asset basepath does not exist: {resolved}")
    return resolved


def make_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    return f"rtx-smoke-{timestamp}-p{os.getpid()}"


def q3_quote(value: object) -> str:
    text = str(value).replace("\\", "/").replace('"', '\\"')
    return f'"{text}"'


def command_to_string(command: Sequence[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(list(command))
    return shlex.join(command)


def profile_cvars(profile_name: str, width: int, height: int) -> dict[str, str]:
    spec = PROFILE_SPECS[profile_name]
    cvars = dict(COMMON_CVARS)
    cvars["r_customWidth"] = str(width)
    cvars["r_customHeight"] = str(height)
    cvars["rtx_rt_mode"] = str(spec["requestedMode"])
    cvars["rtx_rt_require"] = str(spec["require"])
    return cvars


def build_profile_cfg(
    profile_name: str,
    cvars: dict[str, str],
    startup_wait: int,
    map_wait: int,
    screenshot_wait: int,
    disconnect_wait: int,
) -> tuple[str, list[dict[str, object]]]:
    slug = str(PROFILE_SPECS[profile_name]["slug"])
    lines = [
        "// Generated by scripts/rtx_runtime_smoke.py",
        f"// RTX smoke profile: {profile_name}",
    ]
    for name in sorted(cvars):
        lines.append(f"set {name} {q3_quote(cvars[name])}")

    lines.extend(
        [
            'set timedemo "0"',
            'set nextdemo ""',
            f"echo RTX_SMOKE_PROFILE_BEGIN {profile_name}",
            f"wait {startup_wait}",
            "gfxinfo",
            "vkinfo",
        ]
    )

    screenshots: list[dict[str, object]] = []
    for map_name in MAPS:
        screenshot_name = f"rtxsmoke-{slug}-{map_name}"
        lines.extend(
            [
                f"map {map_name}",
                f"wait {map_wait}",
                f"echo RTX_SMOKE_SCENE_READY {profile_name} {map_name}",
                "gfxinfo",
                "vkinfo",
                "r_dlightReloadWorld",
                f"screenshotPNG {screenshot_name}",
                f"wait {screenshot_wait}",
                f"echo RTX_SMOKE_SCREENSHOT_REQUESTED {profile_name} {map_name} {screenshot_name}",
            ]
        )
        screenshots.append(
            {
                "name": screenshot_name,
                "map": map_name,
                "profile": profile_name,
                "kind": "scene",
            }
        )
        if profile_name == "rt-pipeline" and map_name == "q3dm1":
            audit_name = f"{screenshot_name}-albedo"
            lines.extend(
                [
                    'set rtx_rt_debug_visualizer "4"',
                    f"wait {screenshot_wait}",
                    f"screenshotPNG {audit_name}",
                    f"wait {screenshot_wait}",
                    f"echo RTX_SMOKE_MATERIAL_AUDIT_REQUESTED {profile_name} {map_name} {audit_name}",
                    'set rtx_rt_debug_visualizer "0"',
                    "wait 1",
                ]
            )
            screenshots.append(
                {
                    "name": audit_name,
                    "map": map_name,
                    "profile": profile_name,
                    "kind": "material-albedo",
                    "beautyName": screenshot_name,
                }
            )
        lines.extend(
            [
                "disconnect",
                f"wait {disconnect_wait}",
            ]
        )

    lines.extend(
        [
            f"echo RTX_SMOKE_PROFILE_END {profile_name}",
            "quit",
            "",
        ]
    )
    return "\n".join(lines), screenshots


def write_config(homepath: Path, fs_game: str, cfg_name: str, contents: str) -> Path:
    game_dir = homepath / fs_game
    game_dir.mkdir(parents=True, exist_ok=True)
    config_path = game_dir / cfg_name
    config_path.write_text(contents, encoding="utf-8", newline="\n")
    return config_path


def write_runtime_sidecars(
    homepath: Path,
    fs_game: str,
) -> list[dict[str, object]]:
    maps_dir = homepath / fs_game / "maps"
    maps_dir.mkdir(parents=True, exist_ok=True)

    fog_path = maps_dir / "q3dm1.fog"
    fog_path.write_text(Q3DM1_FOG_SIDECAR, encoding="utf-8", newline="\n")

    lights_path = maps_dir / "q3dm1.dlight"
    lights_path.write_text(
        json.dumps(Q3DM1_LIGHTS_SIDECAR, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    lights = Q3DM1_LIGHTS_SIDECAR["lights"]
    return [
        {
            "map": "q3dm1",
            "kind": "globalFog",
            "path": str(fog_path),
        },
        {
            "map": "q3dm1",
            "kind": "staticLights",
            "path": str(lights_path),
            "lightCount": len(lights) if isinstance(lights, list) else 0,
        },
    ]


def build_launch_command(
    exe: Path,
    basepath: Path,
    homepath: Path,
    fs_game: str,
    cfg_name: str,
    cvars: dict[str, str],
) -> list[str]:
    missing = [name for name in STARTUP_CVARS if name not in cvars]
    if missing:
        raise ValueError(
            "Missing lifecycle-sensitive startup cvars: " + ", ".join(missing)
        )

    # Keep this launch line below the engine's MAX_CONSOLE_LINES limit. The
    # generated config still owns the complete feature profile; this subset
    # must exist before the first renderer initialization.
    command = [
        str(exe),
        "+set",
        "fs_homepath",
        str(homepath),
        "+set",
        "fs_basepath",
        str(basepath),
        "+set",
        "fs_steampath",
        "",
        "+set",
        "fs_cdpath",
        "",
        "+set",
        "fs_game",
        fs_game,
        "+set",
        "cl_renderer",
        "rtx",
    ]
    for name in STARTUP_CVARS:
        command.extend(["+set", name, cvars[name]])
    command.extend(["+exec", cfg_name])
    startup_commands = sum(
        1 for argument in command if argument.startswith("+")
    )
    if startup_commands > MAX_STARTUP_COMMANDS:
        raise ValueError(
            "RTX smoke startup command count "
            f"{startup_commands} exceeds engine limit {MAX_STARTUP_COMMANDS}"
        )
    return command


def run_engine(
    command: list[str],
    cwd: Path,
    timeout: float,
    log_path: Path,
    dry_run: bool,
    evidence_probe: Callable[[], bool] | None = None,
    *,
    poll_interval: float = 0.1,
    exit_grace: float = 2.0,
    cleanup_timeout: float = 5.0,
) -> dict[str, object]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command_line = command_to_string(command)

    if dry_run:
        log_path.write_text(
            "DRY RUN: engine was not launched.\n" + command_line + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return {
            "status": "planned",
            "returncode": None,
            "command": command,
            "commandLine": command_line,
            "pid": None,
            "cleanupAction": "not_launched",
        }

    process: subprocess.Popen[str] | None = None
    process_status = "failed"
    cleanup_action = "not_started"
    launch_error: str | None = None

    try:
        with log_path.open("w", encoding="utf-8", errors="replace", newline="\n") as log:
            process = subprocess.Popen(
                command,
                cwd=str(cwd),
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            deadline = time.monotonic() + timeout
            evidence_complete = False

            while True:
                if evidence_probe is not None:
                    try:
                        evidence_complete = evidence_probe()
                    except OSError:
                        evidence_complete = False
                    if evidence_complete:
                        returncode = process.poll()
                        if returncode is not None:
                            process_status = (
                                "evidence_complete"
                                if returncode == 0
                                else "exited_with_error"
                            )
                            cleanup_action = "already_exited"
                        else:
                            process_status = "evidence_complete"
                        break

                returncode = process.poll()
                if returncode is not None:
                    # A clean process exit closes and flushes qconsole.log and
                    # screenshot files after the preceding probe may have
                    # observed them in-flight. Recheck once after process
                    # completion before classifying the run as incomplete.
                    if evidence_probe is not None:
                        try:
                            evidence_complete = evidence_probe()
                        except OSError:
                            evidence_complete = False

                    if evidence_complete and returncode == 0:
                        process_status = "evidence_complete"
                    elif returncode != 0:
                        process_status = "exited_with_error"
                    else:
                        process_status = (
                            "passed"
                            if evidence_probe is None
                            else "exited_before_evidence"
                        )
                    cleanup_action = "already_exited"
                    break

                if time.monotonic() >= deadline:
                    process_status = "timed_out_before_evidence"
                    log.write(f"\nTIMEOUT before evidence after {timeout:.1f} seconds\n")
                    log.flush()
                    break

                time.sleep(poll_interval)

            if evidence_complete:
                returncode = process.poll()
                if returncode is None:
                    try:
                        returncode = process.wait(timeout=exit_grace)
                        cleanup_action = "natural_exit"
                    except subprocess.TimeoutExpired:
                        returncode = None
                elif cleanup_action == "not_started":
                    cleanup_action = "already_exited"

                if returncode is not None and returncode != 0:
                    process_status = "exited_with_error"

            if process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=cleanup_timeout)
                    cleanup_action = "terminated"
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        process.kill()
                        process.wait(timeout=cleanup_timeout)
                        cleanup_action = "killed"
                    except (OSError, subprocess.TimeoutExpired):
                        cleanup_action = "cleanup_failed"
                        process_status = "cleanup_failed"

            log.flush()
    except OSError as exc:
        launch_error = f"{type(exc).__name__}: {exc}"
        log_path.write_text(
            f"LAUNCH ERROR: {launch_error}\n",
            encoding="utf-8",
            newline="\n",
        )
        cleanup_action = "launch_failed"

    result: dict[str, object] = {
        "status": process_status,
        "returncode": process.poll() if process is not None else None,
        "command": command,
        "commandLine": command_line,
        "pid": process.pid if process is not None else None,
        "cleanupAction": cleanup_action,
    }
    if launch_error is not None:
        result["launchError"] = launch_error
    return result


def collect_logs(
    process_log: Path,
    qconsole_source: Path,
    qconsole_artifact: Path,
    combined_log: Path,
    dry_run: bool,
) -> None:
    qconsole_artifact.parent.mkdir(parents=True, exist_ok=True)
    if dry_run:
        qconsole_artifact.write_text(
            f"DRY RUN: expected qconsole source is {qconsole_source}\n",
            encoding="utf-8",
            newline="\n",
        )
    elif qconsole_source.is_file():
        shutil.copy2(qconsole_source, qconsole_artifact)
    else:
        qconsole_artifact.write_text(
            f"QCONSOLE LOG NOT FOUND: {qconsole_source}\n",
            encoding="utf-8",
            newline="\n",
        )

    process_text = process_log.read_text(encoding="utf-8", errors="replace")
    qconsole_text = qconsole_artifact.read_text(encoding="utf-8", errors="replace")
    combined_log.write_text(
        "===== PROCESS OUTPUT =====\n"
        + process_text
        + "\n===== QCONSOLE OUTPUT =====\n"
        + qconsole_text,
        encoding="utf-8",
        newline="\n",
    )


def _paeth_predictor(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    left_distance = abs(estimate - left)
    above_distance = abs(estimate - above)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= above_distance and left_distance <= upper_left_distance:
        return left
    if above_distance <= upper_left_distance:
        return above
    return upper_left


def _cache_png_metrics(
    cache_key: tuple[str, int, int],
    metrics: dict[str, object],
) -> dict[str, object]:
    path_key = cache_key[0]
    for existing_key in list(_PNG_METRIC_CACHE):
        if existing_key[0] == path_key and existing_key != cache_key:
            del _PNG_METRIC_CACHE[existing_key]
    for existing_key in list(_PNG_LUMINANCE_CACHE):
        if existing_key[0] == path_key and existing_key != cache_key:
            del _PNG_LUMINANCE_CACHE[existing_key]
    if len(_PNG_METRIC_CACHE) >= 64:
        del _PNG_METRIC_CACHE[next(iter(_PNG_METRIC_CACHE))]
    _PNG_METRIC_CACHE[cache_key] = dict(metrics)
    return dict(metrics)


def _cache_png_luminance(
    cache_key: tuple[str, int, int],
    width: int,
    height: int,
    luminance: array,
) -> None:
    path_key = cache_key[0]
    for existing_key in list(_PNG_LUMINANCE_CACHE):
        if existing_key[0] == path_key and existing_key != cache_key:
            del _PNG_LUMINANCE_CACHE[existing_key]
    if len(_PNG_LUMINANCE_CACHE) >= 8:
        del _PNG_LUMINANCE_CACHE[next(iter(_PNG_LUMINANCE_CACHE))]
    _PNG_LUMINANCE_CACHE[cache_key] = (width, height, luminance)


def _decode_png_metrics(path: Path) -> dict[str, object]:
    resolved = path.resolve()
    try:
        before = path.stat()
    except OSError as exc:
        return {
            "structurallyValid": False,
            "error": f"{type(exc).__name__}: {exc}",
            "path": str(resolved),
        }

    cache_key = (str(resolved), before.st_mtime_ns, before.st_size)
    cached = _PNG_METRIC_CACHE.get(cache_key)
    if cached is not None:
        return dict(cached)

    try:
        data = path.read_bytes()
        after = path.stat()
    except OSError as exc:
        return {
            "structurallyValid": False,
            "error": f"{type(exc).__name__}: {exc}",
            "path": str(resolved),
        }

    if (
        before.st_mtime_ns != after.st_mtime_ns
        or before.st_size != after.st_size
        or len(data) != after.st_size
    ):
        return {
            "structurallyValid": False,
            "error": "PNG changed while it was being read",
            "path": str(resolved),
            "fileBytes": len(data),
        }

    cache_key = (str(resolved), after.st_mtime_ns, after.st_size)
    base_metrics: dict[str, object] = {
        "path": str(resolved),
        "fileBytes": len(data),
        "structurallyValid": False,
    }

    def fail(message: str) -> dict[str, object]:
        return {
            **base_metrics,
            "error": message,
        }

    if len(data) < len(PNG_SIGNATURE) or data[: len(PNG_SIGNATURE)] != PNG_SIGNATURE:
        return fail("invalid PNG signature")

    offset = len(PNG_SIGNATURE)
    chunk_count = 0
    ihdr: tuple[int, int, int, int, int, int, int] | None = None
    idat_parts: list[bytes] = []
    saw_iend = False
    chunk_names: list[str] = []

    while offset < len(data):
        if len(data) - offset < 12:
            return fail("truncated PNG chunk framing")

        chunk_length = struct.unpack_from(">I", data, offset)[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_end = offset + 12 + chunk_length
        if chunk_end > len(data):
            return fail("truncated PNG chunk payload")
        if not all(
            65 <= value <= 90 or 97 <= value <= 122 for value in chunk_type
        ):
            return fail("invalid PNG chunk type")

        chunk_data = data[offset + 8 : offset + 8 + chunk_length]
        stored_crc = struct.unpack_from(">I", data, offset + 8 + chunk_length)[0]
        computed_crc = zlib.crc32(chunk_data, zlib.crc32(chunk_type)) & 0xFFFFFFFF
        if stored_crc != computed_crc:
            return fail(
                f"CRC mismatch in {chunk_type.decode('ascii')} chunk"
            )

        chunk_name = chunk_type.decode("ascii")
        chunk_names.append(chunk_name)
        if chunk_count == 0 and chunk_type != b"IHDR":
            return fail("IHDR is not the first PNG chunk")

        if chunk_type == b"IHDR":
            if ihdr is not None or chunk_length != 13:
                return fail("invalid or duplicate IHDR chunk")
            ihdr = struct.unpack(">IIBBBBB", chunk_data)
        elif chunk_type == b"IDAT":
            if ihdr is None:
                return fail("IDAT precedes IHDR")
            idat_parts.append(chunk_data)
        elif chunk_type == b"IEND":
            if chunk_length != 0:
                return fail("IEND chunk is not empty")
            saw_iend = True
            offset = chunk_end
            chunk_count += 1
            if offset != len(data):
                return fail("trailing bytes after IEND")
            break
        elif (chunk_type[0] & 0x20) == 0 and chunk_type != b"PLTE":
            return fail(f"unsupported critical PNG chunk {chunk_name}")

        offset = chunk_end
        chunk_count += 1

    if ihdr is None:
        return fail("IHDR chunk was not found")
    if not idat_parts:
        return fail("IDAT chunk was not found")
    if not saw_iend:
        return fail("IEND chunk was not found")

    (
        width,
        height,
        bit_depth,
        color_type,
        compression_method,
        filter_method,
        interlace_method,
    ) = ihdr
    base_metrics.update(
        {
            "width": width,
            "height": height,
            "bitDepth": bit_depth,
            "colorType": color_type,
            "compressionMethod": compression_method,
            "filterMethod": filter_method,
            "interlaceMethod": interlace_method,
            "chunkCount": chunk_count,
            "chunks": chunk_names,
        }
    )

    if width <= 0 or height <= 0:
        return fail("PNG dimensions must be positive")
    if width * height > PNG_MAX_PIXELS:
        return fail(
            f"PNG exceeds the {PNG_MAX_PIXELS}-pixel smoke-evidence limit"
        )
    if bit_depth != 8:
        return fail(f"unsupported PNG bit depth {bit_depth}; expected 8")
    channels = PNG_COLOR_CHANNELS.get(color_type)
    if channels is None:
        return fail(
            f"unsupported PNG color type {color_type}; expected grayscale, RGB, or RGBA"
        )
    if compression_method != 0 or filter_method != 0 or interlace_method != 0:
        return fail(
            "unsupported PNG compression, filter, or interlace method"
        )

    stride = width * channels
    expected_decoded_bytes = height * (stride + 1)
    compressed = b"".join(idat_parts)
    try:
        decompressor = zlib.decompressobj()
        decoded = decompressor.decompress(
            compressed,
            expected_decoded_bytes + 1,
        )
        if decompressor.unconsumed_tail:
            return fail("PNG decompressed data exceeds the expected dimensions")
        decoded += decompressor.flush()
    except zlib.error as exc:
        return fail(f"invalid PNG zlib stream: {exc}")

    if not decompressor.eof or decompressor.unused_data:
        return fail("PNG contains an incomplete or trailing zlib stream")
    if len(decoded) != expected_decoded_bytes:
        return fail(
            "PNG decoded byte count does not match IHDR dimensions "
            f"({len(decoded)} != {expected_decoded_bytes})"
        )

    previous = bytearray(stride)
    decoded_offset = 0
    filter_types: set[int] = set()
    luminance_min = 255.0
    luminance_max = 0.0
    luminance_sum = 0.0
    luminance_square_sum = 0.0
    near_white_count = 0
    pixel_count = width * height
    luminance_values = array("f")

    for _row_index in range(height):
        filter_type = decoded[decoded_offset]
        decoded_offset += 1
        if filter_type > 4:
            return fail(f"unsupported PNG scanline filter {filter_type}")
        filter_types.add(filter_type)

        filtered = decoded[decoded_offset : decoded_offset + stride]
        decoded_offset += stride
        reconstructed = bytearray(stride)
        for index, value in enumerate(filtered):
            left = reconstructed[index - channels] if index >= channels else 0
            above = previous[index]
            upper_left = previous[index - channels] if index >= channels else 0
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = above
            elif filter_type == 3:
                predictor = (left + above) // 2
            else:
                predictor = _paeth_predictor(left, above, upper_left)
            reconstructed[index] = (value + predictor) & 0xFF

        for pixel_offset in range(0, stride, channels):
            if color_type in (0, 4):
                red = green = blue = reconstructed[pixel_offset]
                luminance = float(red)
                alpha = (
                    reconstructed[pixel_offset + 1] if color_type == 4 else 255
                )
            else:
                red = reconstructed[pixel_offset]
                green = reconstructed[pixel_offset + 1]
                blue = reconstructed[pixel_offset + 2]
                luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
                alpha = (
                    reconstructed[pixel_offset + 3] if color_type == 6 else 255
                )
            if alpha >= 250 and min(red, green, blue) >= 250:
                near_white_count += 1
            if alpha != 255:
                luminance *= alpha / 255.0
            luminance_min = min(luminance_min, luminance)
            luminance_max = max(luminance_max, luminance)
            luminance_sum += luminance
            luminance_square_sum += luminance * luminance
            luminance_values.append(luminance)

        previous = reconstructed

    luminance_mean = luminance_sum / pixel_count
    luminance_variance = max(
        0.0,
        luminance_square_sum / pixel_count - luminance_mean * luminance_mean,
    )
    luminance_range = luminance_max - luminance_min
    near_white_fraction = near_white_count / pixel_count
    _cache_png_luminance(
        cache_key,
        width,
        height,
        luminance_values,
    )
    return _cache_png_metrics(
        cache_key,
        {
            **base_metrics,
            "structurallyValid": True,
            "error": None,
            "width": width,
            "height": height,
            "bitDepth": bit_depth,
            "colorType": color_type,
            "channels": channels,
            "compressionMethod": compression_method,
            "filterMethod": filter_method,
            "interlaceMethod": interlace_method,
            "chunkCount": chunk_count,
            "chunks": chunk_names,
            "crcValidated": True,
            "compressedBytes": len(compressed),
            "decodedBytes": len(decoded),
            "pixelCount": pixel_count,
            "scanlineFilters": sorted(filter_types),
            "luminanceMin": round(luminance_min, 6),
            "luminanceMax": round(luminance_max, 6),
            "luminanceMean": round(luminance_mean, 6),
            "luminanceVariance": round(luminance_variance, 6),
            "luminanceRange": round(luminance_range, 6),
            "nearWhitePixels": near_white_count,
            "nearWhiteFraction": round(near_white_fraction, 6),
        },
    )


def inspect_png(
    path: Path,
    expected_width: int | None = None,
    expected_height: int | None = None,
) -> dict[str, object]:
    metrics = _decode_png_metrics(path)
    metrics["expectedWidth"] = expected_width
    metrics["expectedHeight"] = expected_height

    structural = bool(metrics.get("structurallyValid"))
    dimensions_match = (
        structural
        and (expected_width is None or metrics.get("width") == expected_width)
        and (expected_height is None or metrics.get("height") == expected_height)
    )
    luminance_range = float(metrics.get("luminanceRange", 0.0))
    luminance_variance = float(metrics.get("luminanceVariance", 0.0))
    nontrivial = (
        structural
        and luminance_range >= PNG_MIN_LUMINANCE_RANGE
        and luminance_variance >= PNG_MIN_LUMINANCE_VARIANCE
    )
    near_white_fraction = float(metrics.get("nearWhiteFraction", 0.0))
    not_blown_out = (
        structural and near_white_fraction <= PNG_MAX_NEAR_WHITE_FRACTION
    )
    metrics["dimensionsMatch"] = dimensions_match
    metrics["nontrivial"] = nontrivial
    metrics["notBlownOut"] = not_blown_out
    metrics["minimumLuminanceRange"] = PNG_MIN_LUMINANCE_RANGE
    metrics["minimumLuminanceVariance"] = PNG_MIN_LUMINANCE_VARIANCE
    metrics["maximumNearWhiteFraction"] = PNG_MAX_NEAR_WHITE_FRACTION
    metrics["valid"] = (
        structural and dimensions_match and nontrivial and not_blown_out
    )

    if structural and not dimensions_match:
        metrics["error"] = (
            "PNG dimensions do not match the requested render size "
            f"({metrics.get('width')}x{metrics.get('height')} != "
            f"{expected_width}x{expected_height})"
        )
    elif structural and not nontrivial:
        metrics["error"] = (
            "PNG luminance is too uniform for runtime evidence "
            f"(range {luminance_range:.3f}, variance {luminance_variance:.3f})"
        )
    elif structural and not not_blown_out:
        metrics["error"] = (
            "PNG has excessive near-white clipping for runtime evidence "
            f"({near_white_fraction:.3%} > "
            f"{PNG_MAX_NEAR_WHITE_FRACTION:.3%})"
        )
    return metrics


def _decode_png_luminance(
    path: Path,
) -> tuple[int, int, array] | None:
    try:
        stat = path.stat()
    except OSError:
        return None

    cache_key = (str(path.resolve()), stat.st_mtime_ns, stat.st_size)
    cached = _PNG_LUMINANCE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    metrics = _decode_png_metrics(path)
    if not metrics.get("structurallyValid"):
        return None
    cached = _PNG_LUMINANCE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    # Metric entries are normally populated alongside luminance. If a caller
    # deliberately retained only the small metric cache, force one bounded
    # decode so material-audit data cannot silently disappear.
    _PNG_METRIC_CACHE.pop(cache_key, None)
    metrics = _decode_png_metrics(path)
    if not metrics.get("structurallyValid"):
        return None
    return _PNG_LUMINANCE_CACHE.get(cache_key)


def _high_pass_roi(
    luminance: Sequence[float],
    width: int,
    height: int,
    bounds: tuple[int, int, int, int],
    blur_radius: int,
) -> list[float]:
    x0, y0, x1, y1 = bounds
    sample_x0 = max(0, x0 - blur_radius)
    sample_y0 = max(0, y0 - blur_radius)
    sample_x1 = min(width, x1 + blur_radius)
    sample_y1 = min(height, y1 + blur_radius)
    sample_width = sample_x1 - sample_x0
    sample_height = sample_y1 - sample_y0
    integral_stride = sample_width + 1
    integral = [0.0] * ((sample_height + 1) * integral_stride)

    for local_y in range(sample_height):
        row_sum = 0.0
        source_offset = (sample_y0 + local_y) * width + sample_x0
        integral_row = (local_y + 1) * integral_stride
        previous_row = local_y * integral_stride
        for local_x in range(sample_width):
            row_sum += float(luminance[source_offset + local_x])
            integral[integral_row + local_x + 1] = (
                integral[previous_row + local_x + 1] + row_sum
            )

    residuals: list[float] = []
    for y in range(y0, y1):
        blur_y0 = max(0, y - blur_radius)
        blur_y1 = min(height, y + blur_radius + 1)
        local_blur_y0 = blur_y0 - sample_y0
        local_blur_y1 = blur_y1 - sample_y0
        for x in range(x0, x1):
            blur_x0 = max(0, x - blur_radius)
            blur_x1 = min(width, x + blur_radius + 1)
            local_blur_x0 = blur_x0 - sample_x0
            local_blur_x1 = blur_x1 - sample_x0
            total = (
                integral[local_blur_y1 * integral_stride + local_blur_x1]
                - integral[local_blur_y0 * integral_stride + local_blur_x1]
                - integral[local_blur_y1 * integral_stride + local_blur_x0]
                + integral[local_blur_y0 * integral_stride + local_blur_x0]
            )
            sample_count = (blur_x1 - blur_x0) * (blur_y1 - blur_y0)
            residuals.append(
                float(luminance[y * width + x]) - total / sample_count
            )
    return residuals


def _pearson_correlation(
    left: Sequence[float],
    right: Sequence[float],
) -> float | None:
    if len(left) != len(right) or not left:
        return None
    count = len(left)
    left_mean = sum(left) / count
    right_mean = sum(right) / count
    covariance = 0.0
    left_energy = 0.0
    right_energy = 0.0
    for left_value, right_value in zip(left, right):
        left_centered = left_value - left_mean
        right_centered = right_value - right_mean
        covariance += left_centered * right_centered
        left_energy += left_centered * left_centered
        right_energy += right_centered * right_centered
    denominator = math.sqrt(left_energy * right_energy)
    if denominator <= 1e-9:
        return None
    return covariance / denominator


def inspect_material_audit(
    beauty_path: Path,
    albedo_path: Path,
    expected_width: int,
    expected_height: int,
) -> dict[str, object]:
    result: dict[str, object] = {
        "status": "failed",
        "valid": False,
        "beautyPath": str(beauty_path.resolve()),
        "albedoPath": str(albedo_path.resolve()),
        "normalizedRoi": list(MATERIAL_AUDIT_ROI),
        "minimumCorrelation": MATERIAL_AUDIT_MIN_CORRELATION,
        "minimumAlbedoDetailRms": MATERIAL_AUDIT_MIN_ALBEDO_DETAIL_RMS,
    }
    beauty_metrics = inspect_png(beauty_path, expected_width, expected_height)
    albedo_metrics = inspect_png(albedo_path, expected_width, expected_height)
    if not beauty_metrics.get("valid") or not albedo_metrics.get("valid"):
        result["error"] = (
            "material audit requires valid beauty and albedo PNG evidence"
        )
        return result

    beauty = _decode_png_luminance(beauty_path)
    albedo = _decode_png_luminance(albedo_path)
    if beauty is None or albedo is None:
        result["error"] = "material audit could not decode PNG luminance"
        return result
    beauty_width, beauty_height, beauty_luminance = beauty
    albedo_width, albedo_height, albedo_luminance = albedo
    if (beauty_width, beauty_height) != (albedo_width, albedo_height):
        result["error"] = "material audit PNG dimensions do not match"
        return result

    width = beauty_width
    height = beauty_height
    x0 = max(0, min(width - 1, int(MATERIAL_AUDIT_ROI[0] * width)))
    y0 = max(0, min(height - 1, int(MATERIAL_AUDIT_ROI[1] * height)))
    x1 = max(x0 + 1, min(width, int(MATERIAL_AUDIT_ROI[2] * width)))
    y1 = max(y0 + 1, min(height, int(MATERIAL_AUDIT_ROI[3] * height)))
    blur_radius = max(
        1,
        round(
            MATERIAL_AUDIT_BLUR_RADIUS
            * height
            / MATERIAL_AUDIT_REFERENCE_HEIGHT
        ),
    )
    alignment_radius = max(
        0,
        round(
            MATERIAL_AUDIT_ALIGNMENT_RADIUS
            * height
            / MATERIAL_AUDIT_REFERENCE_HEIGHT
        ),
    )
    albedo_residual = _high_pass_roi(
        albedo_luminance,
        width,
        height,
        (x0, y0, x1, y1),
        blur_radius,
    )
    albedo_detail_rms = math.sqrt(
        sum(value * value for value in albedo_residual)
        / len(albedo_residual)
    )

    best_correlation: float | None = None
    best_offset = (0, 0)
    best_beauty_detail_rms = 0.0
    for offset_y in range(-alignment_radius, alignment_radius + 1):
        for offset_x in range(-alignment_radius, alignment_radius + 1):
            shifted = (
                x0 + offset_x,
                y0 + offset_y,
                x1 + offset_x,
                y1 + offset_y,
            )
            if (
                shifted[0] < 0
                or shifted[1] < 0
                or shifted[2] > width
                or shifted[3] > height
            ):
                continue
            beauty_residual = _high_pass_roi(
                beauty_luminance,
                width,
                height,
                shifted,
                blur_radius,
            )
            correlation = _pearson_correlation(
                beauty_residual,
                albedo_residual,
            )
            if correlation is None:
                continue
            if best_correlation is None or correlation > best_correlation:
                best_correlation = correlation
                best_offset = (offset_x, offset_y)
                best_beauty_detail_rms = math.sqrt(
                    sum(value * value for value in beauty_residual)
                    / len(beauty_residual)
                )

    correlation_pass = (
        best_correlation is not None
        and best_correlation >= MATERIAL_AUDIT_MIN_CORRELATION
    )
    detail_pass = (
        albedo_detail_rms >= MATERIAL_AUDIT_MIN_ALBEDO_DETAIL_RMS
    )
    valid = correlation_pass and detail_pass
    result.update(
        {
            "status": "passed" if valid else "failed",
            "valid": valid,
            "pixelRoi": [x0, y0, x1, y1],
            "blurKernel": blur_radius * 2 + 1,
            "alignmentRadius": alignment_radius,
            "bestAlignment": list(best_offset),
            "correlation": (
                round(best_correlation, 6)
                if best_correlation is not None
                else None
            ),
            "correlationPass": correlation_pass,
            "albedoDetailRms": round(albedo_detail_rms, 6),
            "beautyDetailRms": round(best_beauty_detail_rms, 6),
            "detailPass": detail_pass,
            "error": None,
        }
    )
    if not valid:
        result["error"] = (
            "authored albedo detail did not survive native RT shading "
            f"(correlation {best_correlation!r}, albedo detail RMS "
            f"{albedo_detail_rms:.3f})"
        )
    return result


def is_valid_png(
    path: Path,
    expected_width: int | None = None,
    expected_height: int | None = None,
) -> bool:
    return bool(inspect_png(path, expected_width, expected_height)["valid"])


def collect_screenshots(
    homepath: Path,
    fs_game: str,
    profile_name: str,
    expected: list[dict[str, object]],
    output_root: Path,
    dry_run: bool,
    expected_width: int,
    expected_height: int,
) -> list[dict[str, object]]:
    destination_dir = output_root / "screenshots" / profile_name
    destination_dir.mkdir(parents=True, exist_ok=True)
    source_dir = homepath / fs_game / "screenshots"
    results: list[dict[str, object]] = []

    for planned in expected:
        name = str(planned["name"])
        source_path = source_dir / f"{name}.png"
        artifact_path = destination_dir / f"{name}.png"
        found = source_path.is_file() and source_path.stat().st_size > 0
        png_metrics = (
            inspect_png(source_path, expected_width, expected_height)
            if found
            else None
        )
        valid_png = bool(png_metrics and png_metrics["valid"])
        if found and not dry_run:
            shutil.copy2(source_path, artifact_path)
        results.append(
            {
                **planned,
                "status": "planned" if dry_run else ("captured" if found else "missing"),
                "found": found,
                "validPng": valid_png,
                "pngMetrics": png_metrics,
                "sourcePath": str(source_path),
                "artifactPath": str(artifact_path),
            }
        )
    return results


def detect_error_lines(text: str) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line in seen:
            continue
        for kind, pattern in ERROR_PATTERNS:
            if pattern.search(line):
                errors.append({"kind": kind, "line": line})
                seen.add(line)
                break
    return errors


def analyze_log_text(text: str, profile_name: str) -> dict[str, object]:
    spec = PROFILE_SPECS[profile_name]
    capability_matches = list(CAPABILITY_RE.finditer(text))
    capability: dict[str, object] | None = None
    if capability_matches:
        match = capability_matches[-1]
        capability = {
            "requestedName": match.group("requestedName").lower(),
            "requestedMode": int(match.group("requested")),
            "activeName": match.group("activeName").lower(),
            "activeMode": int(match.group("active")),
            "require": int(match.group("require")),
        }

    validation_match = VALIDATION_ENABLED_RE.search(text)
    scene_ready = {
        map_name: (
            f"RTX_SMOKE_SCENE_READY {profile_name} {map_name}" in text
            and re.search(rf"\bServer:\s*{re.escape(map_name)}\b", text, re.IGNORECASE)
            is not None
        )
        for map_name in MAPS
    }
    startup_markers = {
        "rendererInitFinished": "----- finished R_Init -----" in text,
        "profileBegin": f"RTX_SMOKE_PROFILE_BEGIN {profile_name}" in text,
        "profileEnd": f"RTX_SMOKE_PROFILE_END {profile_name}" in text,
    }
    sidecar_evidence = {
        "q3dm1GlobalFog": Q3DM1_GLOBAL_FOG_MARKER in text,
        "q3dm1StaticLights": Q3DM1_STATIC_LIGHTS_MARKER in text,
    }
    errors = detect_error_lines(text)
    failures: list[str] = []

    missing_startup = [
        name for name, found in startup_markers.items() if not found
    ]
    if missing_startup:
        failures.append("Missing startup markers: " + ", ".join(missing_startup) + ".")

    missing_maps = [map_name for map_name, found in scene_ready.items() if not found]
    if missing_maps:
        failures.append("Missing map-load markers: " + ", ".join(missing_maps) + ".")

    missing_sidecars = [
        name for name, found in sidecar_evidence.items() if not found
    ]
    if missing_sidecars:
        failures.append(
            "Missing deterministic sidecar evidence: "
            + ", ".join(missing_sidecars)
            + "."
        )

    if capability is None:
        failures.append("RTX capability gate marker was not found.")
    else:
        expected = (
            int(spec["requestedMode"]),
            int(spec["activeMode"]),
            int(spec["require"]),
        )
        observed = (
            int(capability["requestedMode"]),
            int(capability["activeMode"]),
            int(capability["require"]),
        )
        if observed != expected:
            failures.append(
                "RTX capability gate mismatch: "
                f"expected requested/active/require {expected}, observed {observed}."
            )
        if capability["activeName"] != spec["activeModeName"]:
            failures.append(
                "RTX capability active-mode name mismatch: "
                f"expected {spec['activeModeName']}, observed {capability['activeName']}."
            )

    if validation_match is None:
        failures.append("Vulkan validation-layer enablement marker was not found.")

    rt_post_stack = RT_POST_STACK_MARKER in text
    rt_native_dispatch = RT_NATIVE_DISPATCH_MARKER in text
    if int(spec["requestedMode"]) == 2 and not rt_post_stack:
        failures.append("RTX RT post-stack validation marker was not found.")
    if int(spec["requestedMode"]) == 2 and not rt_native_dispatch:
        failures.append(
            "Native RTX primary-dispatch/copy validation marker was not found."
        )

    for error in errors:
        failures.append(f"{error['kind']} error marker: {error['line']}")

    return {
        "profile": profile_name,
        "startupMarkers": startup_markers,
        "sceneReady": scene_ready,
        "sidecarEvidence": sidecar_evidence,
        "capability": capability,
        "validationEnabled": validation_match is not None,
        "validationLayer": validation_match.group("layer") if validation_match else None,
        "rtPostStack": rt_post_stack,
        "rtNativeDispatch": rt_native_dispatch,
        "errorLines": errors,
        "failures": failures,
    }


def analyze_log_file(path: Path, profile_name: str) -> dict[str, object]:
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    return analyze_log_text(text, profile_name)


def profile_evidence_complete(
    qconsole_path: Path,
    profile_name: str,
    screenshot_paths: Sequence[Path],
    expected_width: int,
    expected_height: int,
    material_audit_paths: tuple[Path, Path] | None = None,
) -> bool:
    try:
        analysis = analyze_log_file(qconsole_path, profile_name)
        screenshots_valid = all(
            is_valid_png(path, expected_width, expected_height)
            for path in screenshot_paths
        )
        material_valid = (
            True
            if material_audit_paths is None
            else bool(
                inspect_material_audit(
                    material_audit_paths[0],
                    material_audit_paths[1],
                    expected_width,
                    expected_height,
                )["valid"]
            )
        )
        return (
            not analysis["failures"]
            and screenshots_valid
            and material_valid
        )
    except OSError:
        return False


def evaluate_profile(
    run: dict[str, object],
    spec: dict[str, object],
    dry_run: bool,
) -> list[str]:
    if dry_run:
        return []

    failures: list[str] = []
    if run.get("processStatus") != "evidence_complete":
        failures.append(f"Engine process status was {run.get('processStatus', 'missing')}.")

    screenshots = run.get("screenshots")
    if not isinstance(screenshots, list) or len(screenshots) != len(MAPS):
        failures.append(f"Expected {len(MAPS)} screenshot records.")
    else:
        missing = [
            str(shot.get("name"))
            for shot in screenshots
            if isinstance(shot, dict) and not shot.get("found")
        ]
        invalid = [
            (
                f"{shot.get('name')} "
                f"({shot.get('pngMetrics', {}).get('error', 'validation failed')})"
                if isinstance(shot.get("pngMetrics"), dict)
                else str(shot.get("name"))
            )
            for shot in screenshots
            if isinstance(shot, dict) and shot.get("found") and not shot.get("validPng")
        ]
        missing_metrics = [
            str(shot.get("name"))
            for shot in screenshots
            if isinstance(shot, dict)
            and shot.get("found")
            and not isinstance(shot.get("pngMetrics"), dict)
        ]
        if missing:
            failures.append("Missing screenshots: " + ", ".join(missing) + ".")
        if invalid:
            failures.append("Invalid PNG screenshots: " + ", ".join(invalid) + ".")
        if missing_metrics:
            failures.append(
                "Missing PNG evidence metrics: "
                + ", ".join(missing_metrics)
                + "."
            )

    analysis = run.get("analysis")
    if not isinstance(analysis, dict):
        failures.append("Runtime log analysis is missing.")
    else:
        analysis_failures = analysis.get("failures")
        if isinstance(analysis_failures, list):
            failures.extend(str(item) for item in analysis_failures)
        else:
            failures.append("Runtime log analysis failures field is missing.")

    if int(spec["requestedMode"]) == 2:
        material_audit = run.get("materialAudit")
        if not isinstance(material_audit, dict):
            failures.append("RT material-detail audit is missing.")
        elif not material_audit.get("valid"):
            failures.append(
                "RT material-detail audit failed: "
                f"{material_audit.get('error', 'validation failed')}."
            )

    if run.get("requestedMode") != spec["requestedMode"]:
        failures.append("Manifest requested mode does not match the profile contract.")
    if run.get("require") != spec["require"]:
        failures.append("Manifest require policy does not match the profile contract.")
    return failures


def evaluate_gate(manifest: dict[str, object]) -> list[str]:
    if manifest.get("dryRun"):
        return []

    gate_name = str(manifest.get("gate", ""))
    gate = GATE_PRESETS.get(gate_name)
    if gate is None:
        return [f"Unknown gate in manifest: {gate_name or '<missing>'}."]

    runs = manifest.get("runs")
    if not isinstance(runs, list):
        return ["Manifest runs field is not a list."]

    runs_by_profile = {
        str(run.get("profile")): run for run in runs if isinstance(run, dict)
    }
    failures: list[str] = []
    for profile_name in gate["profiles"]:
        profile_name = str(profile_name)
        run = runs_by_profile.get(profile_name)
        if run is None:
            failures.append(f"Required profile is missing: {profile_name}.")
            continue
        for failure in evaluate_profile(run, PROFILE_SPECS[profile_name], False):
            failures.append(f"{profile_name}: {failure}")
    return failures


def markdown_summary(manifest: dict[str, object], manifest_path: Path) -> str:
    lines = [
        "# RTX Runtime Smoke",
        "",
        f"- Gate: `{manifest.get('gate')}`",
        f"- Status: `{manifest.get('status')}`",
        f"- Dry run: `{manifest.get('dryRun')}`",
        f"- Manifest: `{manifest_path}`",
        "",
        "## Profiles",
        "",
        "| Profile | Mode | Require | Status | Screenshots | Material audit | Validation | RT post stack | Native RT copied |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    runs = manifest.get("runs", [])
    if isinstance(runs, list):
        for run in runs:
            if not isinstance(run, dict):
                continue
            screenshots = run.get("screenshots", [])
            valid = 0
            planned = 0
            if isinstance(screenshots, list):
                planned = len(screenshots)
                valid = sum(
                    1
                    for shot in screenshots
                    if isinstance(shot, dict) and shot.get("validPng")
                )
            analysis = run.get("analysis", {})
            if manifest.get("dryRun"):
                validation = rt_post = native_rt = "planned"
            else:
                validation = (
                    analysis.get("validationEnabled", "-")
                    if isinstance(analysis, dict)
                    else "-"
                )
                rt_post = (
                    analysis.get("rtPostStack", "-")
                    if isinstance(analysis, dict)
                    else "-"
                )
                native_rt = (
                    analysis.get("rtNativeDispatch", "-")
                    if isinstance(analysis, dict)
                    else "-"
                )
            material_audit = run.get("materialAudit", {})
            if int(run.get("requestedMode", 0)) != 2:
                audit_text = "n/a"
            elif manifest.get("dryRun"):
                audit_text = "planned"
            elif isinstance(material_audit, dict):
                correlation = material_audit.get("correlation")
                audit_text = (
                    f"{'pass' if material_audit.get('valid') else 'fail'} "
                    f"{float(correlation):.3f}"
                    if isinstance(correlation, (int, float))
                    else str(material_audit.get("status", "missing"))
                )
            else:
                audit_text = "missing"
            shot_text = f"{planned} planned" if manifest.get("dryRun") else f"{valid}/{planned}"
            lines.append(
                f"| {run.get('profile')} | {run.get('requestedMode')} | "
                f"{run.get('require')} | {run.get('status')} | {shot_text} | "
                f"{audit_text} | {validation} | {rt_post} | {native_rt} |"
            )

    gate_failures = manifest.get("gateFailures", [])
    if isinstance(gate_failures, list) and gate_failures:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {failure}" for failure in gate_failures)

    lines.extend(["", "## Artifacts", ""])
    if isinstance(runs, list):
        for run in runs:
            if not isinstance(run, dict):
                continue
            lines.append(
                f"- `{run.get('profile')}`: config `{run.get('config')}`, "
                f"log `{run.get('combinedLog')}`, home `{run.get('homepath')}`, "
                f"sidecars `{len(run.get('sidecars', []))}`"
            )
    return "\n".join(lines).rstrip() + "\n"


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run_smoke(
    args: argparse.Namespace,
    run_id: str | None = None,
) -> tuple[int, Path, dict[str, object]]:
    validate_options(args)
    exe = resolve_executable(args.exe, args.dry_run)
    basepath = resolve_basepath(args.basepath, exe, args.dry_run)
    run_id = run_id or make_run_id()
    output_root = args.output_dir.resolve() / run_id
    output_root.mkdir(parents=True, exist_ok=False)
    logs_dir = output_root / "logs"
    configs_dir = output_root / "configs"
    logs_dir.mkdir(parents=True)
    configs_dir.mkdir(parents=True)

    runs: list[dict[str, object]] = []
    gate = GATE_PRESETS[args.gate]
    for profile_name_value in gate["profiles"]:
        profile_name = str(profile_name_value)
        spec = PROFILE_SPECS[profile_name]
        slug = str(spec["slug"])
        fs_game = f"rtx_smoke_{slug}"
        homepath = output_root / "homes" / slug
        cfg_name = f"rtx-smoke-{slug}.cfg"
        cvars = profile_cvars(profile_name, args.width, args.height)
        cfg, expected_screenshots = build_profile_cfg(
            profile_name,
            cvars,
            args.startup_wait,
            args.map_wait,
            args.screenshot_wait,
            args.disconnect_wait,
        )
        config_path = write_config(homepath, fs_game, cfg_name, cfg)
        sidecars = write_runtime_sidecars(homepath, fs_game)
        report_config_path = configs_dir / cfg_name
        shutil.copy2(config_path, report_config_path)
        command = build_launch_command(
            exe,
            basepath,
            homepath,
            fs_game,
            cfg_name,
            cvars,
        )
        qconsole_source = homepath / fs_game / "qconsole.log"
        screenshot_sources = [
            homepath / fs_game / "screenshots" / f"{planned['name']}.png"
            for planned in expected_screenshots
        ]
        material_beauty_plan = next(
            (
                planned
                for planned in expected_screenshots
                if planned.get("kind") == "scene"
                and planned.get("map") == "q3dm1"
            ),
            None,
        )
        material_albedo_plan = next(
            (
                planned
                for planned in expected_screenshots
                if planned.get("kind") == "material-albedo"
            ),
            None,
        )
        material_audit_sources = (
            (
                homepath
                / fs_game
                / "screenshots"
                / f"{material_beauty_plan['name']}.png",
                homepath
                / fs_game
                / "screenshots"
                / f"{material_albedo_plan['name']}.png",
            )
            if material_beauty_plan is not None
            and material_albedo_plan is not None
            else None
        )

        process_log = logs_dir / f"{slug}-process.log"
        process_result = run_engine(
            command,
            exe.parent,
            args.timeout,
            process_log,
            args.dry_run,
            evidence_probe=(
                None
                if args.dry_run
                else lambda: profile_evidence_complete(
                    qconsole_source,
                    profile_name,
                    screenshot_sources,
                    args.width,
                    args.height,
                    material_audit_sources,
                )
            ),
        )
        qconsole_artifact = logs_dir / f"{slug}-qconsole.log"
        combined_log = logs_dir / f"{slug}.log"
        collect_logs(
            process_log,
            qconsole_source,
            qconsole_artifact,
            combined_log,
            args.dry_run,
        )
        collected_screenshots = collect_screenshots(
            homepath,
            fs_game,
            profile_name,
            expected_screenshots,
            output_root,
            args.dry_run,
            args.width,
            args.height,
        )
        screenshots = [
            screenshot
            for screenshot in collected_screenshots
            if screenshot.get("kind") == "scene"
        ]
        material_albedo_record = next(
            (
                screenshot
                for screenshot in collected_screenshots
                if screenshot.get("kind") == "material-albedo"
            ),
            None,
        )
        material_beauty_record = next(
            (
                screenshot
                for screenshot in screenshots
                if screenshot.get("map") == "q3dm1"
            ),
            None,
        )
        if int(spec["requestedMode"]) != 2:
            material_audit: dict[str, object] = {
                "status": "not_applicable",
                "valid": True,
            }
        elif args.dry_run:
            material_audit = {
                "status": "planned",
                "valid": None,
                "normalizedRoi": list(MATERIAL_AUDIT_ROI),
                "minimumCorrelation": MATERIAL_AUDIT_MIN_CORRELATION,
                "minimumAlbedoDetailRms": MATERIAL_AUDIT_MIN_ALBEDO_DETAIL_RMS,
                "screenshot": material_albedo_record,
            }
        elif (
            isinstance(material_beauty_record, dict)
            and isinstance(material_albedo_record, dict)
        ):
            material_audit = inspect_material_audit(
                Path(str(material_beauty_record["artifactPath"])),
                Path(str(material_albedo_record["artifactPath"])),
                args.width,
                args.height,
            )
            material_audit["screenshot"] = material_albedo_record
        else:
            material_audit = {
                "status": "failed",
                "valid": False,
                "error": "material audit screenshot records are missing",
                "screenshot": material_albedo_record,
            }
        analysis = (
            {
                "profile": profile_name,
                "validationEnabled": False,
                "rtPostStack": False,
                "failures": [],
                "planned": True,
            }
            if args.dry_run
            else analyze_log_file(combined_log, profile_name)
        )

        run: dict[str, object] = {
            "profile": profile_name,
            "description": spec["description"],
            "requestedMode": spec["requestedMode"],
            "expectedActiveMode": spec["activeMode"],
            "require": spec["require"],
            "status": "planned",
            "processStatus": process_result["status"],
            "returncode": process_result["returncode"],
            "pid": process_result["pid"],
            "cleanupAction": process_result["cleanupAction"],
            "command": process_result["command"],
            "commandLine": process_result["commandLine"],
            "cvars": cvars,
            "fsGame": fs_game,
            "homepath": str(homepath),
            "config": str(report_config_path),
            "liveConfig": str(config_path),
            "processLog": str(process_log),
            "qconsoleLog": str(qconsole_artifact),
            "combinedLog": str(combined_log),
            "sidecars": sidecars,
            "screenshots": screenshots,
            "materialAudit": material_audit,
            "analysis": analysis,
        }
        profile_failures = evaluate_profile(run, spec, args.dry_run)
        run["failures"] = profile_failures
        if not args.dry_run:
            run["status"] = "passed" if not profile_failures else "failed"
        runs.append(run)

    manifest_path = output_root / "manifest.json"
    canonical_summary = output_root / "summary.md"
    summary_paths = [str(canonical_summary)]
    if args.summary_markdown:
        requested_summary = args.summary_markdown.resolve()
        if requested_summary != canonical_summary:
            summary_paths.append(str(requested_summary))

    manifest: dict[str, object] = {
        "schemaVersion": 1,
        "gate": args.gate,
        "description": gate["description"],
        "runId": run_id,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "dryRun": args.dry_run,
        "status": "planned",
        "exe": str(exe),
        "basepath": str(basepath),
        "outputRoot": str(output_root),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "maps": list(MAPS),
        "summaryMarkdown": summary_paths,
        "runs": runs,
    }
    gate_failures = evaluate_gate(manifest)
    manifest["gateFailures"] = gate_failures
    if not args.dry_run:
        manifest["status"] = "passed" if not gate_failures else "failed"

    write_json(manifest_path, manifest)
    summary = markdown_summary(manifest, manifest_path)
    for summary_path_text in summary_paths:
        summary_path = Path(summary_path_text)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(summary, encoding="utf-8", newline="\n")

    return (0 if args.dry_run or not gate_failures else 1), manifest_path, manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)
    if args.list_gates:
        print_gate_list()
        return 0

    try:
        exit_code, manifest_path, manifest = run_smoke(args)
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        print(f"rtx runtime smoke: {exc}", file=sys.stderr)
        return 2

    print(f"RTX runtime smoke: {manifest['status']}")
    print(f"Manifest: {manifest_path}")
    for summary_path in manifest["summaryMarkdown"]:
        print(f"Summary: {summary_path}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

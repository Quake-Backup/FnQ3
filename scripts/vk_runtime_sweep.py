from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SWEEP_ROOT = ROOT / ".tmp" / "vk-runtime-sweeps"
TIMEDEMO_FPS_RE = re.compile(
    r"(?P<frames>\d+)\s+frames[, ]+\s*"
    r"(?P<seconds>\d+(?:\.\d+)?)\s+seconds:?\s*"
    r"(?P<fps>\d+(?:\.\d+)?)\s+fps",
    re.IGNORECASE,
)
PIPELINE_CACHE_RE = re.compile(
    r"pipeline cache:\s*(?P<path>.*?),\s*loaded:\s*(?P<loaded>\d+)Kb,\s*saved:\s*(?P<saved>\d+)Kb",
    re.IGNORECASE,
)
DISPLAY_HDR_RE = re.compile(
    r"display HDR:\s*(?P<state>.*?),\s*metadata:\s*(?P<metadata>\w+),\s*"
    r"paper white\s*(?P<paperWhite>\d+(?:\.\d+)?)\s*nits,\s*max\s*(?P<maxLuminance>\d+(?:\.\d+)?)\s*nits",
    re.IGNORECASE,
)
TONE_MAP_RE = re.compile(
    r"tone map:\s*(?P<mode>.*?),\s*exposure\s*(?P<exposure>\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
BLOOM_RE = re.compile(
    r"bloom:\s*threshold\s*(?P<threshold>\d+(?:\.\d+)?),\s*"
    r"soft knee\s*(?P<softKnee>\d+(?:\.\d+)?),\s*"
    r"intensity\s*(?P<intensity>\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
MODERN_VULKAN_RE = re.compile(
    r"modern Vulkan:\s*sync2\s*(?P<sync2>\w+),\s*dynamic rendering\s*(?P<dynamic>.*)",
    re.IGNORECASE,
)
BARRIERS_RE = re.compile(
    r"barriers:\s*(?P<sync2>\d+)\s*sync2\s*/\s*(?P<legacy>\d+)\s*legacy",
    re.IGNORECASE,
)
DESCRIPTORS_RE = re.compile(
    r"descriptor writes:\s*(?P<writes>\d+),\s*binds:\s*(?P<bindCalls>\d+)\s*calls\s*/\s*"
    r"(?P<bindSets>\d+)\s*sets,\s*material cache:\s*(?P<hits>\d+)\s*hits\s*/\s*(?P<misses>\d+)\s*misses",
    re.IGNORECASE,
)
COMMAND_POOLS_RE = re.compile(
    r"command pool resets:\s*(?P<frame>\d+)\s*frame\s*/\s*(?P<upload>\d+)\s*upload",
    re.IGNORECASE,
)
MEMORY_RE = re.compile(
    r"memory:\s*(?P<allocs>\d+)\s*allocs\s*\((?P<peakAllocs>\d+)\s*peak\),\s*"
    r"(?P<liveKb>\d+)Kb\s*live\s*/\s*(?P<peakKb>\d+)Kb\s*peak",
    re.IGNORECASE,
)
GPU_TIMING_RE = re.compile(
    r"\s*(?P<from>.*?)\s*->\s*(?P<to>.*?):\s*(?P<msec>\d+(?:\.\d+)?)\s*ms",
    re.IGNORECASE,
)
VULKAN_FAILURE_RE = re.compile(
    r"(VK_ERROR_[A-Z0-9_]+|device lost|validation error|returned VK_ERROR)",
    re.IGNORECASE,
)

DEFAULT_OPTIONS = {
    "profile": "vk-modern",
    "maps": "q3dm1",
    "demos": "",
    "width": 640,
    "height": 480,
    "startup_wait": 30,
    "map_wait": 180,
    "screenshot_wait": 8,
    "perf_sample_wait": 4,
    "timeout": 240.0,
}

COMMON_CVARS = {
    "r_fullscreen": "0",
    "r_mode": "-1",
    "r_swapInterval": "0",
    "r_screenshotWriteViewpos": "1",
}

PROFILE_CVARS = {
    "baseline": {
        "r_fbo": "0",
        "r_vbo": "1",
    },
    "vk-modern": {
        "r_fbo": "1",
        "r_vbo": "1",
        "r_hdr": "1",
        "r_bloom": "1",
        "r_bloom_soft_knee": "0.5",
        "r_ext_multisample": "4",
        "r_tonemap": "2",
        "r_tonemapExposure": "1.0",
    },
    "vk-hdr": {
        "r_fbo": "1",
        "r_vbo": "1",
        "r_hdr": "1",
        "r_bloom": "1",
        "r_bloom_soft_knee": "0.5",
        "r_ext_multisample": "4",
        "r_tonemap": "2",
        "r_tonemapExposure": "1.0",
        "r_hdrDisplay": "1",
        "r_hdrDisplayPaperWhite": "203",
        "r_hdrDisplayMaxLuminance": "1000",
        "r_hdrDisplayMaxCLL": "1000",
        "r_hdrDisplayMaxFALL": "400",
    },
}

RC_GATE_PRESETS = {
    "vk-smoke": {
        "description": "Vulkan renderer lifecycle smoke gate for module load, map load, screenshots, and vkinfo diagnostics.",
        "defaults": {
            "profile": "baseline",
            "maps": "q3dm1",
            "demos": "",
            "timeout": 240.0,
        },
        "requirements": {
            "require_screenshots": True,
            "require_vkinfo": True,
        },
    },
    "vk-modern": {
        "description": "Modern Vulkan gate for FBO/HDR/bloom/MSAA path, vkinfo counters, GPU timings, and timedemo metrics.",
        "defaults": {
            "profile": "vk-modern",
            "maps": "q3dm1,q3dm17",
            "demos": "demo1",
            "timeout": 360.0,
        },
        "requirements": {
            "require_screenshots": True,
            "require_vkinfo": True,
            "require_gpu_timings": True,
            "require_timedemo_metrics": True,
        },
    },
    "vk-hdr": {
        "description": "Native-HDR request gate for the HDR10 swapchain path on capable runtime runners.",
        "defaults": {
            "profile": "vk-hdr",
            "maps": "q3dm1",
            "demos": "",
            "timeout": 300.0,
        },
        "requirements": {
            "require_screenshots": True,
            "require_vkinfo": True,
            "require_hdr_request": True,
        },
    },
}


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def sanitize(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    return cleaned.strip("-") or "item"


def q3_quote(value: object) -> str:
    text = str(value).replace("\\", "/").replace('"', '\\"')
    return f'"{text}"'


def q3_path(path: Path) -> str:
    return str(path).replace("\\", "/")


def command_to_string(command: list[str]) -> str:
    quoted: list[str] = []
    for part in command:
        if re.search(r"\s", part):
            quoted.append('"' + part.replace('"', '\\"') + '"')
        else:
            quoted.append(part)
    return " ".join(quoted)


def game_dir(fs_game: str) -> str:
    return fs_game if fs_game else "baseq3"


def parse_extra_sets(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise ValueError(f"--extra-set expects NAME=VALUE, got {item!r}")
        name, value = item.split("=", 1)
        name = name.strip()
        if not name:
            raise ValueError("--extra-set cvar name must not be empty")
        result[name] = value.strip()
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run or plan FnQuake3 Vulkan runtime verification gates."
    )
    parser.add_argument("--gate", choices=sorted(RC_GATE_PRESETS))
    parser.add_argument("--list-gates", action="store_true")
    parser.add_argument("--exe", type=Path, help="Client executable to launch.")
    parser.add_argument(
        "--basepath",
        type=Path,
        help="Game asset basepath. Defaults to the executable directory.",
    )
    parser.add_argument(
        "--homepath",
        type=Path,
        help="Temporary fs_homepath. Defaults under .tmp/vk-runtime-sweeps/<run-id>/home.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_SWEEP_ROOT,
        help="Sweep output root for configs, logs, manifests, and default homepath.",
    )
    parser.add_argument("--fs-game", default="")
    parser.add_argument("--profile", choices=sorted(PROFILE_CVARS))
    parser.add_argument("--maps")
    parser.add_argument("--demos")
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--startup-wait", type=int)
    parser.add_argument("--map-wait", type=int)
    parser.add_argument("--screenshot-wait", type=int)
    parser.add_argument("--perf-sample-wait", type=int)
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--extra-set", action="append", default=[], metavar="NAME=VALUE")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-map-sweep", action="store_true")
    parser.add_argument("--no-demo-sweep", action="store_true")
    parser.add_argument("--no-perf-samples", action="store_true")
    parser.add_argument("--summary-markdown", type=Path)
    return parser.parse_args()


def apply_gate_defaults(args: argparse.Namespace) -> None:
    defaults = dict(DEFAULT_OPTIONS)
    if args.gate:
        defaults.update(RC_GATE_PRESETS[args.gate]["defaults"])  # type: ignore[arg-type]

    for name, value in defaults.items():
        attr = name
        if getattr(args, attr, None) is None:
            setattr(args, attr, value)


def print_gate_list() -> None:
    for name in sorted(RC_GATE_PRESETS):
        gate = RC_GATE_PRESETS[name]
        defaults = gate["defaults"]
        print(f"{name}: {gate['description']}")
        print(
            "  "
            f"profile={defaults['profile']} maps={defaults['maps']} demos={defaults['demos'] or '-'}"
        )


def make_cvars(args: argparse.Namespace) -> dict[str, str]:
    cvars = dict(COMMON_CVARS)
    cvars.update(PROFILE_CVARS[args.profile])
    cvars.update(
        {
            "r_customWidth": str(args.width),
            "r_customHeight": str(args.height),
        }
    )
    cvars.update(parse_extra_sets(args.extra_set))
    return cvars


def cfg_preamble(cvars: dict[str, str], title: str) -> list[str]:
    lines = [f"// Generated by scripts/vk_runtime_sweep.py for {title}"]
    for name in sorted(cvars):
        lines.append(f"set {name} {q3_quote(cvars[name])}")
    lines.append('set timedemo "0"')
    lines.append('set nextdemo ""')
    return lines


def build_map_cfg(
    args: argparse.Namespace,
    cvars: dict[str, str],
    maps: list[str],
    run_id: str,
) -> tuple[str, list[dict[str, object]]]:
    lines = cfg_preamble(cvars, "Vulkan map screenshot sweep")
    screenshots: list[dict[str, object]] = []

    lines.append(f"wait {args.startup_wait}")
    for map_index, map_name in enumerate(maps, start=1):
        safe_map = sanitize(map_name)
        shot_name = f"{run_id}-map{map_index}-{safe_map}-vulkan"
        lines.append(f"map {map_name}")
        lines.append(f"wait {args.map_wait}")
        lines.append("vkinfo")
        if not args.no_perf_samples:
            lines.append('set r_speeds "7"')
            lines.append(f"wait {args.perf_sample_wait}")
        lines.append(f"screenshotPNG {shot_name}")
        lines.append(f"wait {args.screenshot_wait}")
        if not args.no_perf_samples:
            lines.append('set r_speeds "0"')
            lines.append("wait 1")
        lines.append("vkinfo")
        lines.append("disconnect")
        lines.append("wait 30")
        screenshots.append(
            {
                "name": shot_name,
                "baselineKey": f"{args.profile}-map{map_index}-{safe_map}-vulkan",
                "renderer": "vulkan",
                "map": map_name,
                "mapIndex": map_index,
            }
        )

    lines.append("quit")
    lines.append("")
    return "\n".join(lines), screenshots


def build_demo_cfg(args: argparse.Namespace, cvars: dict[str, str], demo: str) -> str:
    lines = cfg_preamble(cvars, f"Vulkan timedemo sweep for {demo}")
    lines.extend(
        [
            f"wait {args.startup_wait}",
            "vkinfo",
            'set timedemo "1"',
            'set nextdemo "quit"',
            f"demo {demo}",
            "",
        ]
    )
    return "\n".join(lines)


def write_cfg(homepath: Path, fs_game: str, cfg_name: str, contents: str) -> Path:
    cfg_dir = homepath / game_dir(fs_game)
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = cfg_dir / cfg_name
    cfg_path.write_text(contents, encoding="utf-8", newline="\n")
    return cfg_path


def resolve_exe(path: Path | None, allow_missing: bool) -> Path:
    if path is None:
        if allow_missing:
            return (ROOT / ".tmp" / "vk-runtime-sweeps" / "fnquake3").resolve()
        raise ValueError("--exe is required unless --dry-run is used")
    resolved = path.resolve()
    if not allow_missing and not resolved.exists():
        raise FileNotFoundError(f"Executable does not exist: {resolved}")
    return resolved


def base_launch_args(
    exe: Path,
    basepath: Path,
    homepath: Path,
    fs_game: str,
    cfg_name: str,
    startup_cvars: dict[str, str],
) -> list[str]:
    command = [
        str(exe),
        "+set",
        "fs_homepath",
        q3_path(homepath),
        "+set",
        "fs_basepath",
        q3_path(basepath),
        "+set",
        "cl_renderer",
        "vulkan",
    ]

    for name in sorted(startup_cvars):
        command.extend(["+set", name, startup_cvars[name]])

    if fs_game:
        command.extend(["+set", "fs_game", fs_game])

    command.extend(["+exec", cfg_name])
    return command


def run_engine(
    command: list[str],
    cwd: Path,
    timeout: float,
    log_path: Path,
    dry_run: bool,
) -> dict[str, object]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    printable = command_to_string(command)

    if dry_run:
        log_path.write_text(f"DRY RUN\n{printable}\n", encoding="utf-8")
        return {
            "status": "planned",
            "returncode": None,
            "command": command,
            "commandLine": printable,
            "log": str(log_path),
        }

    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        log_path.write_text(completed.stdout or "", encoding="utf-8")
        return {
            "status": "passed" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "command": command,
            "commandLine": printable,
            "log": str(log_path),
        }
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        log_path.write_text(
            output + f"\nTIMEOUT after {timeout:.1f} seconds\n",
            encoding="utf-8",
        )
        return {
            "status": "timed_out",
            "returncode": None,
            "command": command,
            "commandLine": printable,
            "log": str(log_path),
        }


def screenshot_results(homepath: Path, fs_game: str, expected: list[dict[str, object]]) -> list[dict[str, object]]:
    screenshot_dir = homepath / game_dir(fs_game) / "screenshots"
    results: list[dict[str, object]] = []
    for item in expected:
        name = str(item["name"])
        path = screenshot_dir / f"{name}.png"
        result = dict(item)
        result.update(
            {
                "path": str(path),
                "found": path.exists(),
                "size": path.stat().st_size if path.exists() else 0,
            }
        )
        results.append(result)
    return results


def timedemo_metrics(log_path: Path) -> dict[str, object] | None:
    if not log_path.exists():
        return None
    text = log_path.read_text(encoding="utf-8", errors="replace")
    matches = list(TIMEDEMO_FPS_RE.finditer(text))
    if not matches:
        return None
    match = matches[-1]
    return {
        "frames": int(match.group("frames")),
        "seconds": float(match.group("seconds")),
        "fps": float(match.group("fps")),
    }


def parse_vkinfo_text(text: str) -> dict[str, object]:
    info: dict[str, object] = {
        "found": False,
        "gpuTimings": [],
        "vulkanFailures": [],
    }
    lines = text.splitlines()

    for line in lines:
        if match := PIPELINE_CACHE_RE.search(line):
            info["found"] = True
            info["pipelineCache"] = {
                "path": match.group("path").strip(),
                "loadedKb": int(match.group("loaded")),
                "savedKb": int(match.group("saved")),
            }
        elif match := DISPLAY_HDR_RE.search(line):
            info["found"] = True
            info["displayHdr"] = {
                "state": match.group("state").strip(),
                "metadata": match.group("metadata").lower(),
                "paperWhite": float(match.group("paperWhite")),
                "maxLuminance": float(match.group("maxLuminance")),
            }
        elif match := TONE_MAP_RE.search(line):
            info["found"] = True
            info["toneMap"] = {
                "mode": match.group("mode").strip(),
                "exposure": float(match.group("exposure")),
            }
        elif match := BLOOM_RE.search(line):
            info["found"] = True
            info["bloom"] = {
                "threshold": float(match.group("threshold")),
                "softKnee": float(match.group("softKnee")),
                "intensity": float(match.group("intensity")),
            }
        elif match := MODERN_VULKAN_RE.search(line):
            info["found"] = True
            info["modernVulkan"] = {
                "sync2": match.group("sync2").lower(),
                "dynamicRendering": match.group("dynamic").strip(),
            }
        elif match := BARRIERS_RE.search(line):
            info["found"] = True
            info["barriers"] = {
                "sync2": int(match.group("sync2")),
                "legacy": int(match.group("legacy")),
            }
        elif match := DESCRIPTORS_RE.search(line):
            info["found"] = True
            info["descriptors"] = {
                "writes": int(match.group("writes")),
                "bindCalls": int(match.group("bindCalls")),
                "bindSets": int(match.group("bindSets")),
                "materialHits": int(match.group("hits")),
                "materialMisses": int(match.group("misses")),
            }
        elif match := COMMAND_POOLS_RE.search(line):
            info["found"] = True
            info["commandPools"] = {
                "frameResets": int(match.group("frame")),
                "uploadResets": int(match.group("upload")),
            }
        elif match := MEMORY_RE.search(line):
            info["found"] = True
            info["memory"] = {
                "allocs": int(match.group("allocs")),
                "peakAllocs": int(match.group("peakAllocs")),
                "liveKb": int(match.group("liveKb")),
                "peakKb": int(match.group("peakKb")),
            }
        elif match := GPU_TIMING_RE.search(line):
            timings = info["gpuTimings"]
            assert isinstance(timings, list)
            timings.append(
                {
                    "from": match.group("from").strip(),
                    "to": match.group("to").strip(),
                    "msec": float(match.group("msec")),
                }
            )

        if VULKAN_FAILURE_RE.search(line):
            failures = info["vulkanFailures"]
            assert isinstance(failures, list)
            failures.append(line.strip())

    return info


def analyze_vk_log(log_path: Path, profile: str) -> dict[str, object]:
    text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    info = parse_vkinfo_text(text)
    failures: list[str] = []

    if not info.get("found"):
        failures.append("vkinfo output was not found.")

    for required_key in ("pipelineCache", "displayHdr", "toneMap", "bloom", "modernVulkan", "barriers", "descriptors", "commandPools", "memory"):
        if required_key not in info:
            failures.append(f"vkinfo field is missing: {required_key}.")

    modern = info.get("modernVulkan")
    barriers = info.get("barriers")
    if isinstance(modern, dict) and isinstance(barriers, dict):
        if modern.get("sync2") == "enabled" and int(barriers.get("sync2", 0)) == 0:
            failures.append("sync2 is enabled but no sync2 barriers were observed.")

    if profile == "vk-hdr":
        display_hdr = info.get("displayHdr")
        if isinstance(display_hdr, dict):
            state = str(display_hdr.get("state", "")).lower()
            if state == "disabled":
                failures.append("vk-hdr profile requested HDR display, but vkinfo reported it disabled.")

    vulkan_failures = info.get("vulkanFailures", [])
    if isinstance(vulkan_failures, list) and vulkan_failures:
        failures.append(f"Vulkan error lines were found: {len(vulkan_failures)}.")

    info["failures"] = failures
    return info


def evaluate_gate(manifest: dict[str, object]) -> list[str]:
    if manifest.get("dryRun"):
        return []

    gate_name = str(manifest.get("gate") or "")
    requirements = (
        RC_GATE_PRESETS.get(gate_name, {}).get("requirements", {}) if gate_name else {}
    )
    runs = manifest.get("runs", [])
    failures: list[str] = []

    if not isinstance(runs, list):
        return ["Manifest runs field is not a list."]

    failed_runs = [
        str(run.get("type", "run"))
        for run in runs
        if isinstance(run, dict) and run.get("status") != "passed"
    ]
    if failed_runs:
        failures.append("Runtime runs failed: " + ", ".join(failed_runs[:8]))

    if requirements.get("require_screenshots"):
        screenshots = [
            shot
            for run in runs
            if isinstance(run, dict)
            for shot in run.get("screenshots", [])  # type: ignore[union-attr]
            if isinstance(shot, dict)
        ]
        if not screenshots:
            failures.append("No screenshots were planned or captured.")
        missing = [str(shot.get("name")) for shot in screenshots if not shot.get("found")]
        if missing:
            failures.append(
                f"Missing screenshots: {len(missing)}/{len(screenshots)} "
                + ", ".join(missing[:8])
            )

    analyses = [
        run.get("vkinfo")
        for run in runs
        if isinstance(run, dict) and isinstance(run.get("vkinfo"), dict)
    ]
    if requirements.get("require_vkinfo"):
        if not analyses:
            failures.append("No vkinfo analysis was collected.")
        for analysis in analyses:
            assert isinstance(analysis, dict)
            analysis_failures = analysis.get("failures", [])
            if isinstance(analysis_failures, list) and analysis_failures:
                failures.append(
                    "Vulkan diagnostic failures: "
                    + "; ".join(str(failure) for failure in analysis_failures[:8])
                )

    if requirements.get("require_gpu_timings"):
        timing_count = sum(
            len(analysis.get("gpuTimings", []))
            for analysis in analyses
            if isinstance(analysis.get("gpuTimings", []), list)
        )
        if timing_count <= 0:
            failures.append("No Vulkan GPU timing samples were found.")

    if requirements.get("require_timedemo_metrics"):
        demos = manifest.get("demos", [])
        if not isinstance(demos, list) or not demos:
            failures.append("No demos were configured for a timedemo gate.")
        for demo in demos if isinstance(demos, list) else []:
            found = any(
                isinstance(run, dict)
                and run.get("type") == "timedemo"
                and str(run.get("demo", "")).lower() == str(demo).lower()
                and isinstance(run.get("timedemoMetrics"), dict)
                for run in runs
            )
            if not found:
                failures.append(f"Missing timedemo metrics for {demo}.")

    if requirements.get("require_hdr_request"):
        hdr_states = [
            str(analysis.get("displayHdr", {}).get("state", "")).lower()
            for analysis in analyses
            if isinstance(analysis.get("displayHdr"), dict)
        ]
        if hdr_states and all(state == "disabled" for state in hdr_states):
            failures.append("HDR display request was not visible in vkinfo.")

    return failures


def markdown_summary(manifest: dict[str, object], manifest_path: Path) -> str:
    lines = [
        f"# Vulkan Runtime Sweep: {manifest.get('gate') or 'custom'}",
        "",
        f"- Manifest: `{manifest_path}`",
        f"- Profile: `{manifest.get('profile')}`",
        f"- Dry run: `{manifest.get('dryRun')}`",
        "",
    ]

    gate_failures = manifest.get("gateFailures", [])
    if isinstance(gate_failures, list) and gate_failures:
        lines.append("## Gate Failures")
        lines.append("")
        for failure in gate_failures:
            lines.append(f"- {failure}")
        lines.append("")

    runs = manifest.get("runs", [])
    if isinstance(runs, list):
        lines.append("## Runs")
        lines.append("")
        lines.append("| Type | Status | Log |")
        lines.append("|---|---:|---|")
        for run in runs:
            if not isinstance(run, dict):
                continue
            lines.append(
                f"| {run.get('type', '-')} | {run.get('status', '-')} | `{run.get('log', '-')}` |"
            )
        lines.append("")

        analyses = [
            run.get("vkinfo")
            for run in runs
            if isinstance(run, dict) and isinstance(run.get("vkinfo"), dict)
        ]
        if analyses:
            lines.append("## Vulkan Diagnostics")
            lines.append("")
            for index, analysis in enumerate(analyses, start=1):
                assert isinstance(analysis, dict)
                modern = analysis.get("modernVulkan", {})
                barriers = analysis.get("barriers", {})
                display_hdr = analysis.get("displayHdr", {})
                tone_map = analysis.get("toneMap", {})
                bloom = analysis.get("bloom", {})
                timings = analysis.get("gpuTimings", [])
                lines.append(
                    f"- Log {index}: sync2 `{modern.get('sync2', '-') if isinstance(modern, dict) else '-'}`, "
                    f"dynamic rendering `{modern.get('dynamicRendering', '-') if isinstance(modern, dict) else '-'}`, "
                    f"barriers `{barriers.get('sync2', '-') if isinstance(barriers, dict) else '-'}/"
                    f"{barriers.get('legacy', '-') if isinstance(barriers, dict) else '-'}`, "
                    f"HDR `{display_hdr.get('state', '-') if isinstance(display_hdr, dict) else '-'}`, "
                    f"tone map `{tone_map.get('mode', '-') if isinstance(tone_map, dict) else '-'}`, "
                    f"bloom knee `{bloom.get('softKnee', '-') if isinstance(bloom, dict) else '-'}`, "
                    f"GPU timing spans `{len(timings) if isinstance(timings, list) else 0}`"
                )
            lines.append("")

        screenshots = [
            shot
            for run in runs
            if isinstance(run, dict)
            for shot in run.get("screenshots", [])  # type: ignore[union-attr]
            if isinstance(shot, dict)
        ]
        if screenshots:
            found = sum(1 for shot in screenshots if shot.get("found"))
            planned = len(screenshots)
            label = "Planned" if manifest.get("dryRun") else "Found"
            lines.append(f"## Screenshots\n\n- {label}: `{found if not manifest.get('dryRun') else planned}/{planned}`\n")

        timedemos = [
            run
            for run in runs
            if isinstance(run, dict) and run.get("type") == "timedemo"
        ]
        if timedemos:
            lines.append("## Timedemos")
            lines.append("")
            lines.append("| Demo | Status | FPS | Frames | Seconds |")
            lines.append("|---|---:|---:|---:|---:|")
            for run in timedemos:
                metrics = run.get("timedemoMetrics")
                if isinstance(metrics, dict):
                    fps = f"{float(metrics.get('fps', 0.0)):.1f}"
                    frames = str(metrics.get("frames", "-"))
                    seconds = f"{float(metrics.get('seconds', 0.0)):.2f}"
                else:
                    fps = frames = seconds = "-"
                lines.append(
                    f"| {run.get('demo', '-')} | {run.get('status', '-')} | {fps} | {frames} | {seconds} |"
                )
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    if args.list_gates:
        print_gate_list()
        return 0

    apply_gate_defaults(args)

    if args.width <= 0 or args.height <= 0:
        raise ValueError("--width and --height must be positive")
    if args.perf_sample_wait < 0:
        raise ValueError("--perf-sample-wait must be non-negative")

    exe = resolve_exe(args.exe, allow_missing=args.dry_run)
    basepath = args.basepath.resolve() if args.basepath else exe.parent.resolve()
    maps = split_csv(args.maps)
    demos = split_csv(args.demos)
    cvars = make_cvars(args)
    startup_cvars = {
        name: value
        for name, value in cvars.items()
        if name
        in {
            "r_fullscreen",
            "r_mode",
            "r_customWidth",
            "r_customHeight",
            "r_fbo",
            "r_hdr",
            "r_hdrDisplay",
            "r_bloom",
            "r_bloom_soft_knee",
            "r_ext_multisample",
            "r_tonemap",
            "r_tonemapExposure",
            "r_vbo",
        }
    }

    run_id = (
        datetime.now(timezone.utc).strftime("vk-sweep-%Y%m%d-%H%M%S-%f")
        + f"-p{Path.cwd().name}-{sanitize(str(Path.cwd().drive or 'root'))}"
    )
    output_root = args.output_dir.resolve() / run_id
    homepath = args.homepath.resolve() if args.homepath else output_root / "home"
    logs_dir = output_root / "logs"
    runs: list[dict[str, object]] = []

    if maps and not args.no_map_sweep:
        cfg_name = f"{run_id}-maps.cfg"
        cfg, expected_screenshots = build_map_cfg(args, cvars, maps, run_id)
        cfg_path = write_cfg(homepath, args.fs_game, cfg_name, cfg)
        command = base_launch_args(exe, basepath, homepath, args.fs_game, cfg_name, startup_cvars)
        log_path = logs_dir / "maps.log"
        result = run_engine(command, exe.parent, args.timeout, log_path, args.dry_run)
        shots = screenshot_results(homepath, args.fs_game, expected_screenshots)
        if not args.dry_run:
            result["vkinfo"] = analyze_vk_log(log_path, args.profile)
        result.update(
            {
                "type": "map-screenshots",
                "config": str(cfg_path),
                "maps": maps,
                "screenshots": shots,
            }
        )
        runs.append(result)

    if demos and not args.no_demo_sweep:
        for demo in demos:
            safe_demo = sanitize(demo)
            cfg_name = f"{run_id}-demo-{safe_demo}.cfg"
            cfg_path = write_cfg(homepath, args.fs_game, cfg_name, build_demo_cfg(args, cvars, demo))
            command = base_launch_args(exe, basepath, homepath, args.fs_game, cfg_name, startup_cvars)
            log_path = logs_dir / f"demo-{safe_demo}.log"
            result = run_engine(command, exe.parent, args.timeout, log_path, args.dry_run)
            metrics = timedemo_metrics(log_path)
            if metrics:
                result["timedemoMetrics"] = metrics
            if not args.dry_run:
                result["vkinfo"] = analyze_vk_log(log_path, args.profile)
            result.update(
                {
                    "type": "timedemo",
                    "config": str(cfg_path),
                    "demo": demo,
                }
            )
            runs.append(result)

    manifest: dict[str, object] = {
        "runId": run_id,
        "createdUtc": datetime.now(timezone.utc).isoformat(),
        "dryRun": args.dry_run,
        "gate": args.gate or "",
        "gateDescription": RC_GATE_PRESETS[args.gate]["description"] if args.gate else "",
        "gateRequirements": RC_GATE_PRESETS[args.gate]["requirements"] if args.gate else {},
        "exe": str(exe),
        "cwd": str(exe.parent),
        "basepath": str(basepath),
        "homepath": str(homepath),
        "fsGame": args.fs_game,
        "profile": args.profile,
        "cvars": cvars,
        "startupCvars": startup_cvars,
        "maps": maps,
        "demos": demos,
        "runs": runs,
    }
    manifest["gateFailures"] = evaluate_gate(manifest)

    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if args.summary_markdown:
        summary_path = args.summary_markdown.resolve()
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            markdown_summary(manifest, manifest_path),
            encoding="utf-8",
            newline="\n",
        )

    run_count = len(runs)
    passed_runs = sum(1 for run in runs if run["status"] in {"passed", "planned"})
    screenshots = [
        shot
        for run in runs
        for shot in run.get("screenshots", [])  # type: ignore[attr-defined]
    ]
    found_screenshots = sum(1 for shot in screenshots if shot["found"])
    missing_screenshots = len(screenshots) - found_screenshots
    gate_failures = manifest["gateFailures"]

    print(f"Run id: {run_id}")
    if args.gate:
        gate_status = "planned" if args.dry_run else ("passed" if not gate_failures else "failed")
        print(f"Gate: {args.gate} ({gate_status})")
        for failure in gate_failures:
            print(f"  - {failure}")
    print(f"Manifest: {manifest_path}")
    print(f"Runs: {passed_runs}/{run_count} passed or planned")
    if screenshots:
        if args.dry_run:
            print(f"Screenshots: {len(screenshots)} planned")
        else:
            print(f"Screenshots: {found_screenshots}/{len(screenshots)} found")

    if args.dry_run:
        return 0
    if gate_failures or passed_runs != run_count or missing_screenshots:
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"vk_runtime_sweep.py: {exc}", file=sys.stderr)
        raise SystemExit(2)

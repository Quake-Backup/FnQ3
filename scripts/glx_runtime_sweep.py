from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "code" / "win32" / "msvc2017" / "output"
DEFAULT_SWEEP_ROOT = ROOT / ".tmp" / "runtime-sweeps"
RENDERER_NAME_RE = re.compile(r"^[A-Za-z1-9]+$")

COMMON_CVARS = {
    "r_fullscreen": "0",
    "r_mode": "-1",
    "r_swapInterval": "0",
    "r_screenshotWriteViewpos": "1",
}

PROFILE_CVARS = {
    "baseline": {},
    "glx-world": {
        "r_vbo": "1",
        "r_glxWorldRenderer": "1",
        "r_glxGpuTiming": "1",
    },
    "glx-material": {
        "r_glxStreamDraw": "1",
        "r_glxStreamDrawMultitexture": "1",
        "r_glxStreamDrawFog": "1",
        "r_glxStreamDrawDepthFragment": "1",
        "r_glxMaterialRenderer": "1",
        "r_glxGpuTiming": "1",
    },
    "glx-bloom": {
        "r_fbo": "1",
        "r_bloom": "2",
        "r_bloom_passes": "2",
        "r_glxGpuTiming": "1",
    },
    "glx-parity": {
        "r_fbo": "1",
        "r_bloom": "2",
        "r_bloom_passes": "2",
        "r_vbo": "1",
        "r_glxWorldRenderer": "1",
        "r_glxStreamDraw": "1",
        "r_glxStreamDrawMultitexture": "1",
        "r_glxStreamDrawFog": "1",
        "r_glxStreamDrawDepthFragment": "1",
        "r_glxMaterialRenderer": "1",
        "r_glxGpuTiming": "1",
    },
    "glx-stress": {
        "r_fbo": "1",
        "r_bloom": "2",
        "r_bloom_passes": "2",
        "r_vbo": "1",
        "r_glxWorldRenderer": "1",
        "r_glxStreamDraw": "1",
        "r_glxStreamDrawMultitexture": "1",
        "r_glxStreamDrawFog": "1",
        "r_glxStreamDrawDepthFragment": "1",
        "r_glxMaterialRenderer": "1",
        "r_glxStaticWorldIndirectBuffer": "1",
        "r_glxStaticWorldIndirectDraw": "1",
        "r_glxStaticWorldMultiDraw": "1",
        "r_glxStaticWorldMultiDrawIndirect": "1",
        "r_glxStaticWorldMultiDrawIndirectCompact": "1",
        "r_glxStaticWorldMultiDrawIndirectSpans": "1",
        "r_glxGpuTiming": "1",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run isolated FnQuake3 renderer-switch, screenshot, and demo sweeps."
    )
    parser.add_argument("--exe", type=Path, help="Client executable to launch.")
    parser.add_argument(
        "--basepath",
        type=Path,
        help="Game asset basepath. Defaults to the executable directory.",
    )
    parser.add_argument(
        "--homepath",
        type=Path,
        help="Temporary fs_homepath. Defaults under .tmp/runtime-sweeps/<run-id>/home.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_SWEEP_ROOT,
        help="Sweep output root for configs, logs, manifests, and default homepath.",
    )
    parser.add_argument(
        "--fs-game",
        default="",
        help="Optional fs_game mod directory. Leave empty for baseq3.",
    )
    parser.add_argument(
        "--renderers",
        default="opengl,glx",
        help="Comma-separated renderers for screenshots and demos.",
    )
    parser.add_argument(
        "--switch-sequence",
        help="Comma-separated renderer order for runtime switching. Defaults to --renderers.",
    )
    parser.add_argument(
        "--maps",
        default="q3dm1",
        help="Comma-separated maps for screenshot sweeps. Empty disables map screenshots.",
    )
    parser.add_argument(
        "--demos",
        default="",
        help="Comma-separated demos for timedemo sweeps. Empty disables demo playback.",
    )
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILE_CVARS),
        default="glx-parity",
        help="Cvar profile to apply in generated sweep configs.",
    )
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--map-wait", type=int, default=180)
    parser.add_argument("--switch-wait", type=int, default=120)
    parser.add_argument("--screenshot-wait", type=int, default=8)
    parser.add_argument("--startup-wait", type=int, default=30)
    parser.add_argument("--switch-rounds", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument(
        "--extra-set",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Additional cvar assignment for generated configs. Can be repeated.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Write configs and manifest only.")
    parser.add_argument(
        "--no-switch-sweep",
        action="store_true",
        help="Skip the runtime renderer-switch screenshot sweep.",
    )
    parser.add_argument(
        "--no-demo-sweep",
        action="store_true",
        help="Skip per-renderer timedemo sweeps.",
    )
    return parser.parse_args()


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def sanitize(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return value.strip("._-") or "item"


def q3_path(path: Path) -> str:
    return path.resolve().as_posix()


def q3_quote(value: object) -> str:
    text = str(value).replace("\\", "/").replace('"', '\\"')
    return f'"{text}"'


def command_to_string(command: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(command)
    return " ".join(subprocess.list2cmdline([part]) for part in command)


def resolve_exe(explicit: Path | None) -> Path:
    if explicit:
        exe = explicit.resolve()
        if not exe.exists():
            raise FileNotFoundError(f"Executable does not exist: {exe}")
        return exe

    machine = platform.machine().lower()
    if os.name == "nt":
        arch_suffixes = ["x64"] if machine in {"amd64", "x86_64"} else [machine, "x64"]
        names: list[str] = []
        for arch in arch_suffixes:
            names.extend(
                [
                    f"fnquake3.glx.{arch}.exe",
                    f"fnquake3.opengl.{arch}.exe",
                    f"fnquake3.{arch}.exe",
                ]
            )
        names.append("fnquake3.exe")
    else:
        names = ["fnquake3.glx", "fnquake3.opengl", "fnquake3"]

    for name in names:
        candidate = DEFAULT_OUTPUT / name
        if candidate.exists():
            return candidate.resolve()

    raise FileNotFoundError(
        "Unable to locate a built client executable. Pass --exe explicitly."
    )


def validate_renderers(renderers: list[str]) -> None:
    if not renderers:
        raise ValueError("At least one renderer is required.")

    for renderer in renderers:
        if not RENDERER_NAME_RE.fullmatch(renderer):
            raise ValueError(
                f"Renderer name {renderer!r} does not match the engine renderer-name rule."
            )


def parse_extra_sets(items: list[str]) -> dict[str, str]:
    cvars: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"--extra-set expects NAME=VALUE, got {item!r}")
        name, value = item.split("=", 1)
        name = name.strip()
        if not name:
            raise ValueError(f"--extra-set has an empty cvar name: {item!r}")
        cvars[name] = value
    return cvars


def make_cvars(args: argparse.Namespace) -> dict[str, str]:
    cvars = dict(COMMON_CVARS)
    cvars["r_customWidth"] = str(args.width)
    cvars["r_customHeight"] = str(args.height)
    cvars.update(PROFILE_CVARS[args.profile])
    cvars.update(parse_extra_sets(args.extra_set))
    return cvars


def game_dir(fs_game: str) -> str:
    return fs_game if fs_game else "baseq3"


def cfg_preamble(cvars: dict[str, str], title: str) -> list[str]:
    lines = [
        f"// Generated by scripts/glx_runtime_sweep.py for {title}",
    ]
    for name in sorted(cvars):
        lines.append(f"set {name} {q3_quote(cvars[name])}")
    lines.append("set timedemo \"0\"")
    lines.append("set nextdemo \"\"")
    return lines


def glx_diagnostic_commands() -> list[str]:
    return [
        "glxinfo",
        "glxmaterial",
        "glxpostprocess",
        "glxstaticworld 8",
    ]


def build_switch_cfg(
    args: argparse.Namespace,
    cvars: dict[str, str],
    maps: list[str],
    switch_sequence: list[str],
    run_id: str,
) -> tuple[str, list[str]]:
    lines = cfg_preamble(cvars, "renderer switch screenshot sweep")
    expected_shots: list[str] = []

    lines.append(f"wait {args.startup_wait}")
    for map_index, map_name in enumerate(maps, start=1):
        safe_map = sanitize(map_name)
        lines.append(f"map {map_name}")
        lines.append(f"wait {args.map_wait}")

        for round_index in range(1, args.switch_rounds + 1):
            for renderer in switch_sequence:
                safe_renderer = sanitize(renderer)
                shot_name = (
                    f"{run_id}-map{map_index}-{safe_map}-round{round_index}-{safe_renderer}"
                )

                lines.append(f"renderer_switch {renderer} fast")
                lines.append(f"wait {args.switch_wait}")
                lines.append(f"screenshotPNG {shot_name}")
                lines.append(f"wait {args.screenshot_wait}")
                if renderer.lower() == "glx":
                    lines.extend(glx_diagnostic_commands())
                    lines.append("wait 1")
                expected_shots.append(shot_name)

        lines.append("disconnect")
        lines.append("wait 30")

    lines.append("quit")
    lines.append("")
    return "\n".join(lines), expected_shots


def build_demo_cfg(args: argparse.Namespace, cvars: dict[str, str], demo: str) -> str:
    lines = cfg_preamble(cvars, f"timedemo sweep for {demo}")
    lines.extend(
        [
            f"wait {args.startup_wait}",
            "set timedemo \"1\"",
            "set nextdemo \"quit\"",
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


def base_launch_args(
    exe: Path,
    basepath: Path,
    homepath: Path,
    fs_game: str,
    renderer: str,
    cfg_name: str,
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
        "r_fullscreen",
        "0",
        "+set",
        "r_mode",
        "-1",
        "+set",
        "cl_renderer",
        renderer,
    ]

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
        status = "passed" if completed.returncode == 0 else "failed"
        return {
            "status": status,
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


def screenshot_results(homepath: Path, fs_game: str, expected_shots: list[str]) -> list[dict[str, object]]:
    screenshot_dir = homepath / game_dir(fs_game) / "screenshots"
    results = []
    for shot in expected_shots:
        path = screenshot_dir / f"{shot}.png"
        results.append(
            {
                "name": shot,
                "path": str(path),
                "found": path.exists(),
                "bytes": path.stat().st_size if path.exists() else 0,
            }
        )
    return results


def main() -> int:
    args = parse_args()
    exe = resolve_exe(args.exe)
    basepath = args.basepath.resolve() if args.basepath else exe.parent.resolve()
    renderers = split_csv(args.renderers)
    switch_sequence = split_csv(args.switch_sequence) if args.switch_sequence else list(renderers)
    maps = split_csv(args.maps)
    demos = split_csv(args.demos)

    validate_renderers(renderers)
    validate_renderers(switch_sequence)

    run_id = datetime.now(timezone.utc).strftime("glx-sweep-%Y%m%d-%H%M%S-%f")
    output_root = args.output_dir.resolve() / run_id
    homepath = args.homepath.resolve() if args.homepath else output_root / "home"
    logs_dir = output_root / "logs"
    cvars = make_cvars(args)
    runs: list[dict[str, object]] = []

    if not args.no_switch_sweep and maps:
        switch_cfg_name = f"{run_id}-switch.cfg"
        switch_cfg, expected_shots = build_switch_cfg(args, cvars, maps, switch_sequence, run_id)
        cfg_path = write_cfg(homepath, args.fs_game, switch_cfg_name, switch_cfg)
        command = base_launch_args(
            exe,
            basepath,
            homepath,
            args.fs_game,
            switch_sequence[0],
            switch_cfg_name,
        )
        result = run_engine(
            command,
            exe.parent,
            args.timeout,
            logs_dir / "switch-screenshots.log",
            args.dry_run,
        )
        shots = screenshot_results(homepath, args.fs_game, expected_shots)
        result.update(
            {
                "type": "switch-screenshots",
                "config": str(cfg_path),
                "maps": maps,
                "switchSequence": switch_sequence,
                "screenshots": shots,
            }
        )
        runs.append(result)

    if not args.no_demo_sweep and demos:
        for renderer in renderers:
            for demo in demos:
                safe_renderer = sanitize(renderer)
                safe_demo = sanitize(demo)
                cfg_name = f"{run_id}-demo-{safe_renderer}-{safe_demo}.cfg"
                cfg_path = write_cfg(homepath, args.fs_game, cfg_name, build_demo_cfg(args, cvars, demo))
                command = base_launch_args(
                    exe,
                    basepath,
                    homepath,
                    args.fs_game,
                    renderer,
                    cfg_name,
                )
                result = run_engine(
                    command,
                    exe.parent,
                    args.timeout,
                    logs_dir / f"demo-{safe_renderer}-{safe_demo}.log",
                    args.dry_run,
                )
                result.update(
                    {
                        "type": "timedemo",
                        "config": str(cfg_path),
                        "renderer": renderer,
                        "demo": demo,
                    }
                )
                runs.append(result)

    manifest = {
        "runId": run_id,
        "createdUtc": datetime.now(timezone.utc).isoformat(),
        "dryRun": args.dry_run,
        "exe": str(exe),
        "cwd": str(exe.parent),
        "basepath": str(basepath),
        "homepath": str(homepath),
        "fsGame": args.fs_game,
        "profile": args.profile,
        "cvars": cvars,
        "renderers": renderers,
        "switchSequence": switch_sequence,
        "maps": maps,
        "demos": demos,
        "runs": runs,
    }

    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    run_count = len(runs)
    passed_runs = sum(1 for run in runs if run["status"] in {"passed", "planned"})
    screenshots = [
        shot for run in runs for shot in run.get("screenshots", [])  # type: ignore[attr-defined]
    ]
    found_screenshots = sum(1 for shot in screenshots if shot["found"])
    missing_screenshots = len(screenshots) - found_screenshots

    print(f"Run id: {run_id}")
    print(f"Manifest: {manifest_path}")
    print(f"Runs: {passed_runs}/{run_count} passed or planned")
    if screenshots:
        if args.dry_run:
            print(f"Screenshots: {len(screenshots)} planned")
        else:
            print(f"Screenshots: {found_screenshots}/{len(screenshots)} found")
    if args.dry_run:
        return 0
    if passed_runs != run_count or missing_screenshots:
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"glx_runtime_sweep.py: {exc}", file=sys.stderr)
        raise SystemExit(2)

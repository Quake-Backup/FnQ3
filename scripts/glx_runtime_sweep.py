from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import struct
import subprocess
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "code" / "win32" / "msvc2017" / "output"
DEFAULT_SWEEP_ROOT = ROOT / ".tmp" / "runtime-sweeps"
RENDERER_NAME_RE = re.compile(r"^[A-Za-z1-9]+$")
DEFAULT_PERFORMANCE_MAX_GROWTH_RATIO = 0.20
PERFORMANCE_BASELINE_GROWTH_KEYS = (
    "batches",
    "draws",
    "drawIndexes",
    "streamMegabytes",
    "streamRejects",
    "streamDrawAttempts",
    "streamDrawIndexes",
    "streamDrawFallbacks",
    "streamDrawSkips",
    "staticDrawAttempts",
    "staticDrawIndexes",
    "staticDrawFallbacks",
    "staticMdiAttempts",
    "staticMdiErrors",
)
DEFAULT_PERFORMANCE_BUDGET = {
    "max": {
        "streamRejects": 0,
        "materialCompileFailures": 0,
        "materialLinkFailures": 0,
        "materialPrecacheFailures": 0,
        "materialBindFailures": 0,
        "streamDrawFallbacks": 0,
        "staticDrawFallbacks": 0,
        "staticMdiErrors": 0,
    },
}
TIMEDEMO_FPS_RE = re.compile(
    r"(?P<frames>\d+)\s+frames[, ]+\s*"
    r"(?P<seconds>\d+(?:\.\d+)?)\s+seconds:?\s*"
    r"(?P<fps>\d+(?:\.\d+)?)\s+fps",
    re.IGNORECASE,
)
MATERIAL_RENDERER_RE = re.compile(
    r"material renderer:\s*(?P<mode>\w+),\s*ready\s*(?P<ready>\w+)",
    re.IGNORECASE,
)
MATERIAL_COMPILES_RE = re.compile(
    r"material compiles:\s*(?P<attempts>\d+)\s+attempts,\s*"
    r"(?P<compile>\d+)\s+compile failures,\s*"
    r"(?P<link>\d+)\s+link failures,\s*"
    r"precache\s+(?P<precacheFailures>\d+)/(?P<precacheAttempts>\d+),\s*"
    r"bind failures\s+(?P<bind>\d+)",
    re.IGNORECASE,
)
MATERIAL_FALLBACKS_RE = re.compile(
    r"material fallbacks:\s*unsupported\s+(?P<unsupported>\d+),\s*"
    r"disabled\s+(?P<disabled>\d+),\s*not-ready\s+(?P<notReady>\d+),\s*"
    r"full\s+(?P<full>\d+),\s*discarded without GL delete\s+(?P<discarded>\d+)",
    re.IGNORECASE,
)
POSTPROCESS_FBO_RE = re.compile(
    r"FBO:\s*requested\s+(?P<requested>\w+),\s*ready\s+(?P<ready>\w+),\s*"
    r"programs\s+(?P<programs>\w+),\s*framebuffer funcs\s+(?P<framebuffer>\w+)",
    re.IGNORECASE,
)
POSTPROCESS_FBO_LIFECYCLE_RE = re.compile(
    r"FBO lifecycle:\s*(?P<attempts>\d+)\s+init attempts,\s*"
    r"(?P<ready>\d+)\s+ready,\s*(?P<failed>\d+)\s+failed,\s*"
    r"(?P<disabled>\d+)\s+disabled",
    re.IGNORECASE,
)
POSTPROCESS_BLOOM_CREATE_RE = re.compile(
    r"bloom create:\s*last\s+(?P<last>[A-Za-z0-9_-]+),\s*"
    r"(?P<ready>\d+)/(?P<attempts>\d+)\s+ready,\s*"
    r"texture-unit failures\s+(?P<textureFailures>\d+),\s*"
    r"FBO failures\s+(?P<fboFailures>\d+)",
    re.IGNORECASE,
)
POSTPROCESS_BLOOM_PASSES_RE = re.compile(
    r"bloom passes:\s*calls\s+(?P<calls>\d+),\s*rendered\s+(?P<rendered>\d+),\s*"
    r"final\s+(?P<final>\d+),\s*pre-final\s+(?P<preFinal>\d+),\s*"
    r"skipped\s+(?P<skipped>\d+),\s*failures\s+(?P<failures>\d+)",
    re.IGNORECASE,
)
POSTPROCESS_OUTPUT_RE = re.compile(
    r"copies/blits:.*last output\s+(?P<output>[A-Za-z0-9_-]+)",
    re.IGNORECASE,
)
STREAM_BUFFER_RE = re.compile(r"dynamic stream buffer:\s*(?P<ready>\w+)", re.IGNORECASE)
STREAM_SYNC_RE = re.compile(
    r"dynamic stream sync:\s*(?P<ready>\w+),\s*fences\s+(?P<fences>\d+),\s*"
    r"waits\s+(?P<waits>\d+),\s*timeouts\s+(?P<timeouts>\d+),\s*"
    r"failures\s+(?P<failures>\d+),\s*pending skips\s+(?P<pendingSkips>\d+)",
    re.IGNORECASE,
)
STREAM_RESERVATIONS_RE = re.compile(
    r"dynamic stream reservations:\s*(?P<reservations>\d+),\s*commits:\s*(?P<commits>\d+),\s*"
    r"wraps:\s*(?P<wraps>\d+),\s*same-frame wrap rejects:\s*(?P<sameFrameRejects>\d+)",
    re.IGNORECASE,
)
STREAM_UPLOADS_RE = re.compile(
    r"dynamic stream uploads:\s*(?P<calls>\d+)\s+calls,\s*"
    r"(?P<megabytes>\d+(?:\.\d+)?)\s+MB,\s*failures\s+(?P<failures>\d+)",
    re.IGNORECASE,
)
STREAM_DRAWS_RE = re.compile(
    r"dynamic stream draws:\s*(?P<draws>\d+)/(?P<attempts>\d+)\s+attempts,.*"
    r"fallbacks\s+(?P<fallbacks>\d+)",
    re.IGNORECASE,
)
STREAM_FAILURE_RE = re.compile(
    r"dynamic stream (?P<name>allocation|map|unmap|reservation) failures:\s*(?P<count>\d+)",
    re.IGNORECASE,
)
STATIC_RENDERER_RE = re.compile(
    r"static world GLx renderer:\s*(?P<renderer>\w+),\s*arena upload\s+(?P<arena>\w+),\s*arena draw\s+(?P<draw>\w+)",
    re.IGNORECASE,
)
STATIC_ARENA_RE = re.compile(
    r"static world GLx arena:\s*(?P<ready>\w+),\s*builds\s+(?P<builds>\d+),\s*"
    r"skips\s+(?P<skips>\d+),\s*failures\s+(?P<failures>\d+)",
    re.IGNORECASE,
)
STATIC_INDIRECT_BUFFER_RE = re.compile(
    r"static world indirect buffer:\s*(?P<ready>\w+),\s*builds\s+(?P<builds>\d+),\s*"
    r"skips\s+(?P<skips>\d+),\s*unsupported\s+(?P<unsupported>\d+),\s*"
    r"failures\s+(?P<failures>\d+)",
    re.IGNORECASE,
)
STATIC_PACKET_BATCH_RE = re.compile(
    r"static world GLx packet batches:\s*(?P<enabled>\w+),\s*attempts\s+(?P<attempts>\d+),\s*"
    r"batches\s+(?P<batches>\d+),.*fallback runs\s+(?P<fallbackRuns>\d+)",
    re.IGNORECASE,
)
STATIC_ERRORS_RE = re.compile(
    r"static world .*?(?:errors|GL errors)\s+(?P<errors>\d+)",
    re.IGNORECASE,
)
STATIC_FAILURES_RE = re.compile(
    r"static world .*?failures\s+(?P<failures>\d+)",
    re.IGNORECASE,
)
GLX_FRAME_COUNTER_RE = re.compile(
    r"glx:\s*tier\s+(?P<tier>\S+),\s*batches\s+(?P<batches>\d+),\s*"
    r"draws\s+(?P<draws>\d+)/(?P<drawIndexes>\d+)\s+idx,\s*"
    r"stream\s+(?P<streamStrategy>[^/,\s]+)/(?P<streamReady>\S+)\s+"
    r"(?P<streamMegabytes>\d+(?:\.\d+)?)MB/(?P<streamWraps>\d+)wraps/"
    r"(?P<streamRejects>\d+)rejects\s+shadow\s+(?P<shadowUploads>\d+),\s*"
    r"frames\s+(?P<frames>\d+),\s*backend queries\s+(?P<backendQueries>\d+),\s*"
    r"gpu\s+(?P<gpu>.*?),\s*static\s+(?P<staticBatches>\d+)\s+batches/"
    r"(?P<staticPackets>\d+)\s+packets/(?P<staticSurfaces>\d+)\s+surfaces/"
    r"(?P<staticVerts>\d+)\s+verts/(?P<staticIndexes>\d+)\s+indexes\s+"
    r"(?P<staticMegabytes>\d+(?:\.\d+)?)\s+MB,\s*arena\s+(?P<arenaReady>\S+)\s+"
    r"(?P<arenaMegabytes>\d+(?:\.\d+)?)\s+MB",
    re.IGNORECASE,
)
GLX_MATERIAL_RENDERER_SUMMARY_RE = re.compile(
    r"glx:\s*material renderer\s+(?P<enabled>[^/]+)/(?P<ready>\S+)\s+"
    r"programs\s+(?P<programs>\d+),\s*binds\s+(?P<binds>\d+)/(?P<bindAttempts>\d+)\s+attempts,\s*"
    r"switches\s+(?P<switches>\d+),\s*cache\s+(?P<cacheHits>\d+)/(?P<cacheMisses>\d+),\s*"
    r"failures\s+(?P<compileFailures>\d+)\s+compile/(?P<linkFailures>\d+)\s+link/"
    r"(?P<precacheFailures>\d+)\s+precache/(?P<bindFailures>\d+)\s+bind,\s*"
    r"labels\s+(?P<labels>\d+)",
    re.IGNORECASE,
)
GLX_POSTPROCESS_SUMMARY_RE = re.compile(
    r"glx:\s*postprocess fbo\s+(?P<fbo>\S+)\s+(?P<width>\d+)x(?P<height>\d+)\s+"
    r"capture\s+(?P<captureWidth>\d+)x(?P<captureHeight>\d+)\s+bloom\s+(?P<bloom>\d+),\s*"
    r"frames\s+(?P<frames>\d+)\s+final\s+(?P<final>\d+)\s+prefinal\s+(?P<prefinal>\d+)\s+"
    r"gamma\s+(?P<gammaDirect>\d+)/(?P<gammaBlit>\d+),\s*copies\s+(?P<copies>\d+),\s*"
    r"msaa\s+(?P<msaa>\d+),\s*ssaa\s+(?P<ssaa>\d+),\s*last\s+(?P<last>\S+)",
    re.IGNORECASE,
)
GLX_STREAM_DRAW_SUMMARY_RE = re.compile(
	r"glx:\s*stream draws\s+(?P<draws>\d+)/(?P<attempts>\d+)\s+attempts,\s*"
	r"(?P<indexes>\d+)\s+idx,\s*(?P<megabytes>\d+(?:\.\d+)?)MB/index\s+"
	r"(?P<indexMegabytes>\d+(?:\.\d+)?)MB/tex1\s+(?P<tex1Megabytes>\d+(?:\.\d+)?)MB,.*?"
	r"(?:shadow\s+(?P<shadows>\d+),\s*)?(?:beam\s+(?P<beams>\d+),\s*)?"
	r"(?:post\s+(?P<postprocess>\d+),\s*)?"
	r"fallbacks\s+(?P<fallbacks>\d+),\s*skips\s+(?P<skips>\d+)",
	re.IGNORECASE,
)
GLX_STATIC_DRAW_SUMMARY_RE = re.compile(
    r"glx:\s*static draw\s+(?P<calls>\d+)/(?P<attempts>\d+)\s+calls,\s*"
    r"(?P<indexes>\d+)\s+idx,.*fallbacks\s+(?P<fallbacks>\d+),\s*"
    r"policy skips\s+(?P<policySkips>\d+)",
    re.IGNORECASE,
)
GLX_STATIC_MDI_SUMMARY_RE = re.compile(
    r"glx:\s*static MDI\s+(?P<calls>\d+)/(?P<attempts>\d+)\s+calls,\s*"
    r"(?P<runs>\d+)\s+runs/(?P<indexes>\d+)\s+idx,\s*fallbacks\s+(?P<fallbacks>\d+),\s*"
    r"skips\s+(?P<skips>\d+),\s*errors\s+(?P<errors>\d+),\s*largest\s+(?P<largest>\d+)",
    re.IGNORECASE,
)

DEFAULT_OPTIONS = {
    "renderers": "opengl,glx",
    "switch_sequence": None,
    "maps": None,
    "demos": "",
    "profile": "glx-parity",
    "width": 640,
    "height": 480,
    "map_wait": 180,
    "switch_wait": 120,
    "screenshot_wait": 8,
    "startup_wait": 30,
    "switch_rounds": 1,
    "timeout": 180.0,
    "perf_sample_wait": 4,
    "screenshot_max_rms": 2.0,
    "screenshot_max_pixel_ratio": 0.005,
}

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
        "r_glxStreamDrawTexMods": "1",
        "r_glxStreamDrawEnvironment": "1",
        "r_glxStreamDrawDynamicLights": "0",
        "r_glxStreamDrawScreenMaps": "0",
        "r_glxStreamDrawVideoMaps": "0",
        "r_glxStreamDrawShadows": "0",
        "r_glxStreamDrawBeams": "0",
        "r_glxStreamDrawPostProcess": "0",
        "r_glxMaterialRenderer": "1",
        "r_glxGpuTiming": "1",
    },
    "glx-bloom": {
        "r_fbo": "1",
        "r_bloom": "2",
        "r_bloom_passes": "3",
        "r_glxGpuTiming": "1",
    },
    "glx-parity": {
        "r_glxProfile": "rc",
        "r_fbo": "1",
        "r_bloom": "2",
        "r_bloom_passes": "3",
        "r_vbo": "1",
        "r_glxWorldRenderer": "1",
        "r_glxStreamDraw": "1",
        "r_glxStreamDrawKeyMode": "0",
        "r_glxStreamDrawMultitexture": "1",
        "r_glxStreamDrawFog": "1",
        "r_glxStreamDrawDepthFragment": "1",
        "r_glxStreamDrawTexMods": "1",
        "r_glxStreamDrawEnvironment": "1",
        "r_glxStreamDrawDynamicLights": "0",
        "r_glxStreamDrawScreenMaps": "0",
        "r_glxStreamDrawVideoMaps": "0",
        "r_glxStreamDrawShadows": "0",
        "r_glxStreamDrawBeams": "0",
        "r_glxStreamDrawPostProcess": "0",
        "r_glxMaterialRenderer": "1",
        "r_glxMaterialPrecache": "1",
        "r_glxStaticWorldArena": "0",
        "r_glxStaticWorldArenaDraw": "0",
        "r_glxStaticWorldDraw": "0",
        "r_glxStaticWorldSoftDraw": "0",
        "r_glxStaticWorldDrawPolicy": "full",
        "r_glxStaticWorldMultiDraw": "0",
        "r_glxStaticWorldPacketBatch": "1",
        "r_glxStaticWorldIndirectBuffer": "0",
        "r_glxStaticWorldIndirectDraw": "0",
        "r_glxStaticWorldMultiDrawIndirect": "0",
        "r_glxStaticWorldMultiDrawIndirectCompact": "0",
        "r_glxStaticWorldMultiDrawIndirectSpans": "0",
        "r_glxGpuTiming": "1",
    },
    "glx-stress": {
        "r_glxProfile": "stress",
        "r_fbo": "1",
        "r_bloom": "2",
        "r_bloom_passes": "3",
        "r_vbo": "1",
        "r_glxWorldRenderer": "1",
        "r_glxStreamDraw": "1",
        "r_glxStreamDrawKeyMode": "0",
        "r_glxStreamDrawMultitexture": "1",
        "r_glxStreamDrawFog": "1",
        "r_glxStreamDrawDepthFragment": "1",
        "r_glxStreamDrawTexMods": "1",
        "r_glxStreamDrawEnvironment": "1",
        "r_glxStreamDrawDynamicLights": "0",
        "r_glxStreamDrawScreenMaps": "0",
        "r_glxStreamDrawVideoMaps": "0",
        "r_glxStreamDrawShadows": "0",
        "r_glxStreamDrawBeams": "0",
        "r_glxStreamDrawPostProcess": "0",
        "r_glxMaterialRenderer": "1",
        "r_glxMaterialPrecache": "1",
        "r_glxStaticWorldArena": "0",
        "r_glxStaticWorldArenaDraw": "0",
        "r_glxStaticWorldDraw": "0",
        "r_glxStaticWorldSoftDraw": "0",
        "r_glxStaticWorldDrawPolicy": "full",
        "r_glxStaticWorldMultiDraw": "1",
        "r_glxStaticWorldPacketBatch": "1",
        "r_glxStaticWorldIndirectBuffer": "1",
        "r_glxStaticWorldIndirectDraw": "1",
        "r_glxStaticWorldMultiDrawIndirect": "1",
        "r_glxStaticWorldMultiDrawIndirectCompact": "1",
        "r_glxStaticWorldMultiDrawIndirectSpans": "1",
        "r_glxGpuTiming": "1",
    },
}

PROFILE_MAPS = {
    "baseline": "q3dm1",
    "glx-world": "q3dm1",
    "glx-material": "q3dm1",
    "glx-bloom": "q3dm1",
    "glx-parity": "q3dm1",
    "glx-stress": "q3dm1,q3dm17",
}

STARTUP_CVARS = {
    "r_fullscreen",
    "r_mode",
    "r_swapInterval",
    "r_customWidth",
    "r_customHeight",
    "r_fbo",
    "r_bloom",
    "r_bloom_passes",
    "r_vbo",
    "r_glxProfile",
}

GLX_PROFILE_FORCED_CVARS = {
    name
    for profile in ("glx-parity", "glx-stress")
    for name in PROFILE_CVARS[profile]
    if name.startswith("r_glx") and name != "r_glxProfile"
}

RC_GATE_PRESETS = {
    "rc-smoke": {
        "description": "Renderer lifecycle smoke gate for module load, map load, screenshots, and repeated in-process switches.",
        "defaults": {
            "profile": "baseline",
            "maps": "q3dm1",
            "demos": "",
            "renderers": "opengl,glx",
            "switch_sequence": "opengl,glx,opengl,glx",
            "switch_rounds": 2,
            "timeout": 240.0,
        },
        "requirements": {
            "require_screenshots": True,
            "require_glx_diagnostics": True,
            "require_glx_performance_samples": True,
        },
    },
    "rc-parity": {
        "description": "Blocking GLx RC parity gate for the conservative world, stream, material, bloom, and timing profile.",
        "defaults": {
            "profile": "glx-parity",
            "maps": "q3dm1,q3dm17",
            "demos": "demo1",
            "renderers": "opengl,glx",
            "switch_sequence": "opengl,glx,opengl,glx",
            "switch_rounds": 1,
            "timeout": 300.0,
        },
        "requirements": {
            "require_screenshots": True,
            "require_timedemo_metrics": True,
            "baseline_renderer": "opengl",
            "candidate_renderer": "glx",
            "min_timedemo_fps_ratio": 0.90,
            "screenshot_max_rms": 2.0,
            "screenshot_max_pixel_ratio": 0.005,
            "require_glx_diagnostics": True,
            "require_glx_performance_samples": True,
        },
    },
    "rc-stress": {
        "description": "Developer stress gate for indirect static-world paths before promoting advanced GLx defaults.",
        "defaults": {
            "profile": "glx-stress",
            "maps": "q3dm1,q3dm17",
            "demos": "demo1",
            "renderers": "opengl,glx",
            "switch_sequence": "opengl,glx",
            "switch_rounds": 1,
            "timeout": 360.0,
        },
        "requirements": {
            "require_screenshots": True,
            "require_timedemo_metrics": True,
            "screenshot_max_rms": 2.0,
            "screenshot_max_pixel_ratio": 0.005,
            "require_glx_diagnostics": True,
            "require_glx_performance_samples": True,
        },
    },
}

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run isolated FnQuake3 renderer-switch, screenshot, and demo sweeps."
    )
    parser.add_argument(
        "--gate",
        choices=sorted(RC_GATE_PRESETS),
        help="Apply a named GLx RC gate preset. Explicit command-line values override preset defaults.",
    )
    parser.add_argument(
        "--list-gates",
        action="store_true",
        help="Print available GLx RC gate presets and exit.",
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
        default=None,
        help="Comma-separated renderers for screenshots and demos.",
    )
    parser.add_argument(
        "--switch-sequence",
        help="Comma-separated renderer order for runtime switching. Defaults to --renderers.",
    )
    parser.add_argument(
        "--maps",
        default=None,
        help=(
            "Comma-separated maps for screenshot sweeps. Defaults to the selected "
            "profile map set; empty disables map screenshots."
        ),
    )
    parser.add_argument(
        "--demos",
        default=None,
        help="Comma-separated demos for timedemo sweeps. Empty disables demo playback.",
    )
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILE_CVARS),
        default=None,
        help="Cvar profile to apply in generated sweep configs.",
    )
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument("--map-wait", type=int, default=None)
    parser.add_argument("--switch-wait", type=int, default=None)
    parser.add_argument("--screenshot-wait", type=int, default=None)
    parser.add_argument(
        "--screenshot-baseline-dir",
        type=Path,
        help=(
            "Directory containing approved PNG baselines named by stable screenshot "
            "keys. When provided, captured screenshots are compared against it."
        ),
    )
    parser.add_argument(
        "--approve-screenshot-baselines",
        action="store_true",
        help=(
            "Write captured screenshots into --screenshot-baseline-dir instead of "
            "comparing them. Intended for deliberate baseline refreshes only."
        ),
    )
    parser.add_argument(
        "--screenshot-diff-dir",
        type=Path,
        help="Optional directory for generated PNG difference images.",
    )
    parser.add_argument(
        "--screenshot-max-rms",
        type=float,
        default=None,
        help="Maximum allowed RGB RMS difference when screenshot baselines are enabled.",
    )
    parser.add_argument(
        "--screenshot-max-pixel-ratio",
        type=float,
        default=None,
        help="Maximum allowed ratio of changed pixels when screenshot baselines are enabled.",
    )
    parser.add_argument("--startup-wait", type=int, default=None)
    parser.add_argument("--switch-rounds", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument(
        "--perf-sample-wait",
        type=int,
        default=None,
        help="Frames to leave r_speeds 7 enabled around each GLx screenshot capture.",
    )
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
    parser.add_argument(
        "--no-perf-samples",
        action="store_true",
        help="Do not enable r_speeds 7 around GLx screenshot captures.",
    )
    parser.add_argument(
        "--performance-budget",
        type=Path,
        help=(
            "Optional JSON budget file with max/min metric thresholds. It is "
            "merged with the built-in RC fallback/error budget."
        ),
    )
    parser.add_argument(
        "--no-performance-budget",
        action="store_true",
        help="Disable the built-in GLx performance budget for focused local experiments.",
    )
    parser.add_argument(
        "--performance-baseline",
        type=Path,
        help=(
            "Approved performance-baseline JSON to compare against, or to write "
            "when --approve-performance-baseline is supplied."
        ),
    )
    parser.add_argument(
        "--approve-performance-baseline",
        action="store_true",
        help="Write the current aggregate performance sample as --performance-baseline.",
    )
    parser.add_argument(
        "--performance-max-growth-ratio",
        type=float,
        default=None,
        help=(
            "Maximum allowed growth versus --performance-baseline for tracked "
            f"counter metrics. Defaults to {DEFAULT_PERFORMANCE_MAX_GROWTH_RATIO:.0%}."
        ),
    )
    parser.add_argument(
        "--summary-markdown",
        type=Path,
        help="Optional Markdown summary path for CI logs and artifact review.",
    )
    return parser.parse_args()


def print_gate_list() -> None:
    print("Available GLx RC gates:")
    for name in sorted(RC_GATE_PRESETS):
        preset = RC_GATE_PRESETS[name]
        defaults = dict(DEFAULT_OPTIONS)
        defaults.update(preset["defaults"])  # type: ignore[arg-type]
        requirements = preset["requirements"]  # type: ignore[index]
        startup_profile = PROFILE_CVARS[defaults["profile"]].get("r_glxProfile", "manual")
        print(f"  {name}: {preset['description']}")
        print(
            "    "
            f"profile={defaults['profile']} startup={startup_profile} maps={defaults['maps']} "
            f"demos={defaults['demos'] or '-'} "
            f"switch={defaults['switch_sequence'] or defaults['renderers']}"
        )
        if "min_timedemo_fps_ratio" in requirements:
            print(
                "    "
                f"timedemo floor: {requirements['candidate_renderer']} >= "
                f"{requirements['min_timedemo_fps_ratio']:.0%} of "
                f"{requirements['baseline_renderer']}"
            )


def apply_gate_defaults(args: argparse.Namespace) -> None:
    options = dict(DEFAULT_OPTIONS)
    if args.gate:
        options.update(RC_GATE_PRESETS[args.gate]["defaults"])  # type: ignore[arg-type]

    for name, value in options.items():
        if getattr(args, name) is None:
            setattr(args, name, value)


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


def resolve_exe(explicit: Path | None, allow_missing: bool = False) -> Path:
    if explicit:
        exe = explicit.resolve()
        if not exe.exists() and not allow_missing:
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

    if allow_missing:
        return (DEFAULT_OUTPUT / names[0]).resolve()

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


def launch_cvars(cvars: dict[str, str]) -> dict[str, str]:
    return {name: value for name, value in cvars.items() if name in STARTUP_CVARS}


def config_cvars(args: argparse.Namespace, cvars: dict[str, str]) -> dict[str, str]:
    filtered = dict(cvars)
    profile_values = PROFILE_CVARS.get(args.profile, {})

    if profile_values.get("r_glxProfile"):
        for name in GLX_PROFILE_FORCED_CVARS:
            if filtered.get(name) == profile_values.get(name):
                filtered.pop(name, None)

    return filtered


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
) -> tuple[str, list[dict[str, object]]]:
    lines = cfg_preamble(cvars, "renderer switch screenshot sweep")
    expected_shots: list[dict[str, object]] = []

    lines.append(f"wait {args.startup_wait}")
    for map_index, map_name in enumerate(maps, start=1):
        safe_map = sanitize(map_name)
        lines.append(f"map {map_name}")
        lines.append(f"wait {args.map_wait}")

        for round_index in range(1, args.switch_rounds + 1):
            for switch_index, renderer in enumerate(switch_sequence, start=1):
                safe_renderer = sanitize(renderer)
                shot_name = (
                    f"{run_id}-map{map_index}-{safe_map}-round{round_index}-"
                    f"step{switch_index}-{safe_renderer}"
                )
                baseline_key = (
                    f"{args.profile}-map{map_index}-{safe_map}-round{round_index}-"
                    f"step{switch_index}-{safe_renderer}"
                )

                lines.append(f"renderer_switch {renderer} fast")
                lines.append(f"wait {args.switch_wait}")
                if renderer.lower() == "glx" and not args.no_perf_samples:
                    lines.append("set r_speeds \"7\"")
                    lines.append(f"wait {args.perf_sample_wait}")
                lines.append(f"screenshotPNG {shot_name}")
                lines.append(f"wait {args.screenshot_wait}")
                if renderer.lower() == "glx" and not args.no_perf_samples:
                    lines.append("set r_speeds \"0\"")
                    lines.append("wait 1")
                if renderer.lower() == "glx":
                    lines.extend(glx_diagnostic_commands())
                    lines.append("wait 1")
                expected_shots.append(
                    {
                        "name": shot_name,
                        "baselineKey": baseline_key,
                        "renderer": renderer,
                        "map": map_name,
                        "mapIndex": map_index,
                        "round": round_index,
                        "switchStep": switch_index,
                    }
                )

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
        "r_fullscreen",
        "0",
        "+set",
        "r_mode",
        "-1",
    ]

    for name in sorted(startup_cvars):
        if name in {"r_fullscreen", "r_mode"}:
            continue
        command.extend(["+set", name, startup_cvars[name]])

    command.extend(
        [
            "+set",
            "cl_renderer",
            renderer,
        ]
    )

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


def png_unfilter(filter_type: int, row: bytes, previous: bytes, bpp: int) -> bytes:
    if filter_type == 0:
        return row

    out = bytearray(row)
    for i, value in enumerate(row):
        left = out[i - bpp] if i >= bpp else 0
        up = previous[i] if previous else 0
        up_left = previous[i - bpp] if previous and i >= bpp else 0

        if filter_type == 1:
            predictor = left
        elif filter_type == 2:
            predictor = up
        elif filter_type == 3:
            predictor = (left + up) // 2
        elif filter_type == 4:
            p = left + up - up_left
            pa = abs(p - left)
            pb = abs(p - up)
            pc = abs(p - up_left)
            if pa <= pb and pa <= pc:
                predictor = left
            elif pb <= pc:
                predictor = up
            else:
                predictor = up_left
        else:
            raise ValueError(f"Unsupported PNG filter type {filter_type}.")

        out[i] = (value + predictor) & 0xFF
    return bytes(out)


def read_png_rgba(path: Path) -> tuple[int, int, bytes]:
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError(f"{path} is not a PNG file.")

    offset = len(PNG_SIGNATURE)
    width = height = bit_depth = color_type = interlace = None
    palette: bytes | None = None
    transparency: bytes | None = None
    compressed = bytearray()

    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        chunk_type = data[offset + 4:offset + 8]
        chunk_data = data[offset + 8:offset + 8 + length]
        offset += 12 + length

        if chunk_type == b"IHDR":
            (
                width,
                height,
                bit_depth,
                color_type,
                _compression,
                _filter_method,
                interlace,
            ) = struct.unpack(">IIBBBBB", chunk_data)
        elif chunk_type == b"PLTE":
            palette = chunk_data
        elif chunk_type == b"tRNS":
            transparency = chunk_data
        elif chunk_type == b"IDAT":
            compressed.extend(chunk_data)
        elif chunk_type == b"IEND":
            break

    if width is None or height is None or bit_depth is None or color_type is None:
        raise ValueError(f"{path} is missing a PNG IHDR chunk.")
    if bit_depth != 8:
        raise ValueError(f"{path} uses unsupported PNG bit depth {bit_depth}.")
    if interlace:
        raise ValueError(f"{path} uses unsupported interlaced PNG encoding.")

    channels_by_type = {
        0: 1,  # grayscale
        2: 3,  # RGB
        3: 1,  # indexed color
        4: 2,  # grayscale + alpha
        6: 4,  # RGBA
    }
    channels = channels_by_type.get(color_type)
    if channels is None:
        raise ValueError(f"{path} uses unsupported PNG color type {color_type}.")

    raw = zlib.decompress(bytes(compressed))
    stride = width * channels
    source_rows: list[bytes] = []
    previous = b""
    source_offset = 0
    for _row_index in range(height):
        if source_offset >= len(raw):
            raise ValueError(f"{path} ended before all PNG rows were decoded.")
        filter_type = raw[source_offset]
        source_offset += 1
        row = raw[source_offset:source_offset + stride]
        source_offset += stride
        if len(row) != stride:
            raise ValueError(f"{path} has a truncated PNG row.")
        decoded = png_unfilter(filter_type, row, previous, channels)
        source_rows.append(decoded)
        previous = decoded

    pixels = bytearray(width * height * 4)
    out = 0
    for row in source_rows:
        if color_type == 0:
            for gray in row:
                pixels[out:out + 4] = bytes((gray, gray, gray, 255))
                out += 4
        elif color_type == 2:
            for i in range(0, len(row), 3):
                pixels[out:out + 4] = row[i:i + 3] + b"\xff"
                out += 4
        elif color_type == 3:
            if palette is None:
                raise ValueError(f"{path} is an indexed PNG without a palette.")
            for index in row:
                palette_offset = index * 3
                if palette_offset + 3 > len(palette):
                    raise ValueError(f"{path} references palette index {index} out of range.")
                alpha = transparency[index] if transparency and index < len(transparency) else 255
                pixels[out:out + 4] = palette[palette_offset:palette_offset + 3] + bytes((alpha,))
                out += 4
        elif color_type == 4:
            for i in range(0, len(row), 2):
                gray = row[i]
                alpha = row[i + 1]
                pixels[out:out + 4] = bytes((gray, gray, gray, alpha))
                out += 4
        elif color_type == 6:
            pixels[out:out + len(row)] = row
            out += len(row)

    return width, height, bytes(pixels)


def png_filter_none_rows(width: int, height: int, pixels: bytes) -> bytes:
    stride = width * 4
    rows = bytearray()
    for row_index in range(height):
        start = row_index * stride
        rows.append(0)
        rows.extend(pixels[start:start + stride])
    return bytes(rows)


def write_png_rgba(path: Path, width: int, height: int, pixels: bytes) -> None:
    if width <= 0 or height <= 0:
        raise ValueError("PNG dimensions must be positive.")
    if len(pixels) != width * height * 4:
        raise ValueError("RGBA pixel data does not match the requested PNG dimensions.")

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload)) +
            kind +
            payload +
            struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    raw = png_filter_none_rows(width, height, pixels)
    encoded = bytearray(PNG_SIGNATURE)
    encoded.extend(
        chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0),
        )
    )
    encoded.extend(chunk(b"IDAT", zlib.compress(raw)))
    encoded.extend(chunk(b"IEND", b""))
    path.write_bytes(bytes(encoded))


def compare_rgba_pixels(
    width: int,
    height: int,
    baseline_pixels: bytes,
    candidate_pixels: bytes,
) -> tuple[dict[str, object], bytes]:
    if len(baseline_pixels) != len(candidate_pixels):
        raise ValueError("PNG pixel buffers have different lengths.")

    diff_pixels = bytearray(width * height * 4)
    squared_error = 0
    absolute_error = 0
    max_delta = 0
    changed_pixels = 0
    pixel_count = width * height
    channel_count = pixel_count * 3

    for pixel_index in range(pixel_count):
        base_offset = pixel_index * 4
        pixel_changed = False
        for channel in range(3):
            delta = abs(
                baseline_pixels[base_offset + channel] -
                candidate_pixels[base_offset + channel]
            )
            squared_error += delta * delta
            absolute_error += delta
            max_delta = max(max_delta, delta)
            diff_pixels[base_offset + channel] = min(255, delta * 4)
            if delta:
                pixel_changed = True
        diff_pixels[base_offset + 3] = 255
        if pixel_changed:
            changed_pixels += 1

    rms = (squared_error / channel_count) ** 0.5 if channel_count else 0.0
    mean_absolute = absolute_error / channel_count if channel_count else 0.0
    changed_ratio = changed_pixels / pixel_count if pixel_count else 0.0
    metrics = {
        "width": width,
        "height": height,
        "pixels": pixel_count,
        "changedPixels": changed_pixels,
        "changedPixelRatio": changed_ratio,
        "rms": rms,
        "meanAbsolute": mean_absolute,
        "maxDelta": max_delta,
    }
    return metrics, bytes(diff_pixels)


def compare_png_files(
    baseline_path: Path,
    candidate_path: Path,
    max_rms: float,
    max_pixel_ratio: float,
    diff_path: Path | None = None,
) -> dict[str, object]:
    base_width, base_height, base_pixels = read_png_rgba(baseline_path)
    candidate_width, candidate_height, candidate_pixels = read_png_rgba(candidate_path)

    if (base_width, base_height) != (candidate_width, candidate_height):
        return {
            "status": "failed",
            "reason": "size-mismatch",
            "baselineWidth": base_width,
            "baselineHeight": base_height,
            "candidateWidth": candidate_width,
            "candidateHeight": candidate_height,
        }

    metrics, diff_pixels = compare_rgba_pixels(
        base_width,
        base_height,
        base_pixels,
        candidate_pixels,
    )
    passed = (
        float(metrics["rms"]) <= max_rms and
        float(metrics["changedPixelRatio"]) <= max_pixel_ratio
    )

    if diff_path:
        write_png_rgba(diff_path, base_width, base_height, diff_pixels)

    metrics.update(
        {
            "status": "passed" if passed else "failed",
            "baselinePath": str(baseline_path),
            "candidatePath": str(candidate_path),
            "diffPath": str(diff_path) if diff_path else "",
            "maxRms": max_rms,
            "maxChangedPixelRatio": max_pixel_ratio,
        }
    )
    return metrics


def screenshot_results(
    homepath: Path,
    fs_game: str,
    expected_shots: list[dict[str, object]],
) -> list[dict[str, object]]:
    screenshot_dir = homepath / game_dir(fs_game) / "screenshots"
    results = []
    for shot in expected_shots:
        name = str(shot["name"])
        path = screenshot_dir / f"{name}.png"
        result = dict(shot)
        result.update(
            {
                "path": str(path),
                "found": path.exists(),
                "bytes": path.stat().st_size if path.exists() else 0,
            }
        )
        results.append(result)
    return results


def apply_screenshot_baselines(
    screenshots: list[dict[str, object]],
    baseline_dir: Path | None,
    approve_baselines: bool,
    diff_dir: Path | None,
    max_rms: float,
    max_pixel_ratio: float,
) -> None:
    if baseline_dir is None:
        return

    baseline_root = baseline_dir.resolve()
    for shot in screenshots:
        baseline_key = str(shot.get("baselineKey") or shot.get("name") or "screenshot")
        baseline_path = baseline_root / f"{baseline_key}.png"
        shot["baselinePath"] = str(baseline_path)

        candidate_path = Path(str(shot.get("path", "")))
        if not shot.get("found"):
            shot["baselineStatus"] = "not-compared"
            continue

        if approve_baselines:
            baseline_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate_path, baseline_path)
            shot["baselineStatus"] = "approved"
            continue

        if not baseline_path.exists():
            shot["baselineStatus"] = "missing"
            continue

        diff_path = None
        if diff_dir is not None:
            diff_path = diff_dir.resolve() / f"{baseline_key}.diff.png"

        try:
            comparison = compare_png_files(
                baseline_path,
                candidate_path,
                max_rms,
                max_pixel_ratio,
                diff_path,
            )
        except Exception as exc:
            comparison = {
                "status": "failed",
                "reason": str(exc),
                "baselinePath": str(baseline_path),
                "candidatePath": str(candidate_path),
                "diffPath": str(diff_path) if diff_path else "",
                "maxRms": max_rms,
                "maxChangedPixelRatio": max_pixel_ratio,
            }
        shot["baselineStatus"] = comparison["status"]
        shot["comparison"] = comparison


def q3_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on", "enabled", "ready"}


def rc_profile_requires_glx_paths(profile: str) -> bool:
    return profile in {"glx-parity", "glx-stress", "glx-material"}


def metric_section(metrics: dict[str, object], name: str) -> dict[str, object]:
    section = metrics.get(name)
    if not isinstance(section, dict):
        section = {}
        metrics[name] = section
    return section


def record_metric_max(metrics: dict[str, object], section_name: str, key: str, value: object) -> None:
    section = metric_section(metrics, section_name)
    if isinstance(value, str):
        section[key] = value
        return

    numeric = float(value) if isinstance(value, float) else int(value)
    previous = section.get(key)
    if isinstance(previous, (int, float)):
        section[key] = max(previous, numeric)
    else:
        section[key] = numeric


def int_group(match: re.Match[str], name: str) -> int:
    return int(match.group(name))


def analyze_glx_diagnostics(log_path: Path, profile: str) -> dict[str, object]:
    diagnostics: dict[str, object] = {
        "log": str(log_path),
        "found": False,
        "failures": [],
        "metrics": {},
    }
    failures: list[str] = diagnostics["failures"]  # type: ignore[assignment]
    metrics: dict[str, object] = diagnostics["metrics"]  # type: ignore[assignment]

    if not log_path.exists():
        failures.append("Diagnostic log is missing.")
        return diagnostics

    text = log_path.read_text(encoding="utf-8", errors="replace")
    requires_glx_paths = rc_profile_requires_glx_paths(profile)

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("GLx ") or line.startswith("glx: ") or line.startswith("dynamic stream ") or line.startswith("static world ") or line.startswith("material "):
            diagnostics["found"] = True

        match = MATERIAL_RENDERER_RE.search(line)
        if match:
            mode = match.group("mode").lower()
            ready = q3_bool(match.group("ready"))
            record_metric_max(metrics, "material", "enabled", 1 if mode == "enabled" else 0)
            record_metric_max(metrics, "material", "ready", 1 if ready else 0)
            if requires_glx_paths and mode == "enabled" and not ready:
                failures.append("GLx material renderer is enabled but not ready.")
            continue

        match = MATERIAL_COMPILES_RE.search(line)
        if match:
            for key in ("attempts", "compile", "link", "precacheFailures", "precacheAttempts", "bind"):
                record_metric_max(metrics, "material", key, int_group(match, key))
            if int_group(match, "compile") > 0:
                failures.append(f"GLx material compile failures: {int_group(match, 'compile')}.")
            if int_group(match, "link") > 0:
                failures.append(f"GLx material link failures: {int_group(match, 'link')}.")
            if int_group(match, "precacheFailures") > 0:
                failures.append(f"GLx material precache failures: {int_group(match, 'precacheFailures')}.")
            if int_group(match, "bind") > 0:
                failures.append(f"GLx material bind failures: {int_group(match, 'bind')}.")
            continue

        match = MATERIAL_FALLBACKS_RE.search(line)
        if match:
            for key in ("unsupported", "disabled", "notReady", "full", "discarded"):
                record_metric_max(metrics, "materialFallbacks", key, int_group(match, key))
            if int_group(match, "notReady") > 0:
                failures.append(f"GLx material not-ready fallbacks: {int_group(match, 'notReady')}.")
            if int_group(match, "full") > 0:
                failures.append(f"GLx material program-limit fallbacks: {int_group(match, 'full')}.")
            continue

        match = POSTPROCESS_FBO_RE.search(line)
        if match:
            requested = q3_bool(match.group("requested"))
            ready = q3_bool(match.group("ready"))
            record_metric_max(metrics, "postprocess", "fboRequested", 1 if requested else 0)
            record_metric_max(metrics, "postprocess", "fboReady", 1 if ready else 0)
            if requested and not ready:
                failures.append("GLx postprocess FBO was requested but not ready.")
            continue

        match = POSTPROCESS_FBO_LIFECYCLE_RE.search(line)
        if match:
            for key in ("attempts", "ready", "failed", "disabled"):
                record_metric_max(metrics, "postprocess", f"fbo{key[0].upper()}{key[1:]}", int_group(match, key))
            if int_group(match, "failed") > 0:
                failures.append(f"GLx postprocess FBO init failures: {int_group(match, 'failed')}.")
            continue

        match = POSTPROCESS_BLOOM_CREATE_RE.search(line)
        if match:
            record_metric_max(metrics, "postprocess", "bloomCreateLast", match.group("last"))
            for key in ("ready", "attempts", "textureFailures", "fboFailures"):
                record_metric_max(metrics, "postprocess", f"bloomCreate{key[0].upper()}{key[1:]}", int_group(match, key))
            if int_group(match, "textureFailures") > 0:
                failures.append(f"GLx bloom texture-unit failures: {int_group(match, 'textureFailures')}.")
            if int_group(match, "fboFailures") > 0:
                failures.append(f"GLx bloom FBO failures: {int_group(match, 'fboFailures')}.")
            continue

        match = POSTPROCESS_BLOOM_PASSES_RE.search(line)
        if match:
            for key in ("calls", "rendered", "final", "preFinal", "skipped", "failures"):
                record_metric_max(metrics, "postprocess", f"bloom{key[0].upper()}{key[1:]}", int_group(match, key))
            if int_group(match, "failures") > 0:
                failures.append(f"GLx bloom pass failures: {int_group(match, 'failures')}.")
            continue

        match = POSTPROCESS_OUTPUT_RE.search(line)
        if match:
            output = match.group("output").lower()
            record_metric_max(metrics, "postprocess", "lastOutput", output)
            if output == "minimized":
                failures.append("GLx postprocess last output was minimized.")
            continue

        match = STREAM_BUFFER_RE.search(line)
        if match:
            ready = q3_bool(match.group("ready"))
            record_metric_max(metrics, "stream", "ready", 1 if ready else 0)
            if requires_glx_paths and not ready:
                failures.append("GLx dynamic stream buffer is not ready.")
            continue

        match = STREAM_SYNC_RE.search(line)
        if match:
            for key in ("fences", "waits", "timeouts", "failures", "pendingSkips"):
                record_metric_max(metrics, "stream", f"sync{key[0].upper()}{key[1:]}", int_group(match, key))
            if int_group(match, "failures") > 0:
                failures.append(f"GLx dynamic stream sync failures: {int_group(match, 'failures')}.")
            continue

        match = STREAM_RESERVATIONS_RE.search(line)
        if match:
            for key in ("reservations", "commits", "wraps", "sameFrameRejects"):
                record_metric_max(metrics, "stream", key, int_group(match, key))
            if int_group(match, "sameFrameRejects") > 0:
                failures.append(f"GLx dynamic stream same-frame wrap rejects: {int_group(match, 'sameFrameRejects')}.")
            continue

        match = STREAM_UPLOADS_RE.search(line)
        if match:
            record_metric_max(metrics, "stream", "uploadCalls", int_group(match, "calls"))
            record_metric_max(metrics, "stream", "uploadFailures", int_group(match, "failures"))
            if int_group(match, "failures") > 0:
                failures.append(f"GLx dynamic stream upload failures: {int_group(match, 'failures')}.")
            continue

        match = STREAM_DRAWS_RE.search(line)
        if match:
            for key in ("draws", "attempts", "fallbacks"):
                record_metric_max(metrics, "streamDraw", key, int_group(match, key))
            if int_group(match, "fallbacks") > 0:
                failures.append(f"GLx streamed draw fallbacks: {int_group(match, 'fallbacks')}.")
            continue

        match = STREAM_FAILURE_RE.search(line)
        if match:
            count = int_group(match, "count")
            key = f"{match.group('name').lower()}Failures"
            record_metric_max(metrics, "stream", key, count)
            if count > 0:
                failures.append(f"GLx dynamic stream {match.group('name').lower()} failures: {count}.")
            continue

        match = STATIC_RENDERER_RE.search(line)
        if match:
            renderer_enabled = q3_bool(match.group("renderer"))
            packet_profile = profile in {"glx-parity", "glx-stress"}
            record_metric_max(metrics, "staticWorld", "rendererEnabled", 1 if renderer_enabled else 0)
            if packet_profile and not renderer_enabled:
                failures.append("GLx static world renderer is not enabled under the RC profile.")
            continue

        match = STATIC_ARENA_RE.search(line)
        if match:
            record_metric_max(metrics, "staticWorld", "arenaReady", 1 if q3_bool(match.group("ready")) else 0)
            for key in ("builds", "skips", "failures"):
                record_metric_max(metrics, "staticWorld", f"arena{key[0].upper()}{key[1:]}", int_group(match, key))
            if int_group(match, "failures") > 0:
                failures.append(f"GLx static world arena failures: {int_group(match, 'failures')}.")
            continue

        match = STATIC_INDIRECT_BUFFER_RE.search(line)
        if match:
            record_metric_max(metrics, "staticWorld", "indirectBufferReady", 1 if q3_bool(match.group("ready")) else 0)
            for key in ("builds", "skips", "unsupported", "failures"):
                record_metric_max(metrics, "staticWorld", f"indirectBuffer{key[0].upper()}{key[1:]}", int_group(match, key))
            if int_group(match, "failures") > 0:
                failures.append(f"GLx static world indirect-buffer failures: {int_group(match, 'failures')}.")
            continue

        match = STATIC_PACKET_BATCH_RE.search(line)
        if match:
            enabled = q3_bool(match.group("enabled"))
            record_metric_max(metrics, "staticWorld", "packetBatchEnabled", 1 if enabled else 0)
            for key in ("attempts", "batches", "fallbackRuns"):
                record_metric_max(metrics, "staticWorld", f"packetBatch{key[0].upper()}{key[1:]}", int_group(match, key))
            if profile in {"glx-parity", "glx-stress"} and not enabled:
                failures.append("GLx static world packet batching is not enabled under the RC profile.")
            continue

        match = STATIC_ERRORS_RE.search(line)
        if match:
            errors = int_group(match, "errors")
            record_metric_max(metrics, "staticWorld", "glErrors", errors)
            if errors > 0:
                failures.append(f"GLx static-world GL errors: {errors}.")
            continue

        match = STATIC_FAILURES_RE.search(line)
        if match:
            failures_count = int_group(match, "failures")
            record_metric_max(metrics, "staticWorld", "failures", failures_count)
            if failures_count > 0:
                failures.append(f"GLx static-world failures: {failures_count}.")
            continue

    if requires_glx_paths and not diagnostics.get("found"):
        failures.append("No GLx diagnostic output was found in the run log.")

    diagnostics["failures"] = list(dict.fromkeys(failures))
    return diagnostics


def perf_set_latest(performance: dict[str, object], key: str, value: object) -> None:
    latest = performance.get("latest")
    if not isinstance(latest, dict):
        latest = {}
        performance["latest"] = latest
    latest[key] = value


def perf_record_numeric(performance: dict[str, object], key: str, value: object) -> None:
    numeric = float(value) if isinstance(value, float) else int(value)
    perf_set_latest(performance, key, numeric)

    maxima = performance.get("max")
    if not isinstance(maxima, dict):
        maxima = {}
        performance["max"] = maxima
    previous = maxima.get(key)
    maxima[key] = max(previous, numeric) if isinstance(previous, (int, float)) else numeric


def perf_record_string(performance: dict[str, object], key: str, value: object) -> None:
    perf_set_latest(performance, key, str(value))


def perf_record_match_numbers(
    performance: dict[str, object],
    match: re.Match[str],
    names: tuple[str, ...],
) -> None:
    for name in names:
        perf_record_numeric(performance, name, int_group(match, name))


def prefixed_key(prefix: str, name: str) -> str:
    return f"{prefix}{name[0].upper()}{name[1:]}"


def perf_record_match_numbers_prefixed(
    performance: dict[str, object],
    match: re.Match[str],
    prefix: str,
    names: tuple[str, ...],
) -> None:
    for name in names:
        perf_record_numeric(performance, prefixed_key(prefix, name), int_group(match, name))


def analyze_glx_performance(log_path: Path) -> dict[str, object]:
    performance: dict[str, object] = {
        "log": str(log_path),
        "found": False,
        "sampleCount": 0,
        "latest": {},
        "max": {},
    }

    if not log_path.exists():
        return performance

    text = log_path.read_text(encoding="utf-8", errors="replace")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("glx:"):
            continue

        performance["found"] = True

        match = GLX_FRAME_COUNTER_RE.search(line)
        if match:
            performance["sampleCount"] = int(performance["sampleCount"]) + 1
            perf_record_string(performance, "tier", match.group("tier"))
            perf_record_string(performance, "streamStrategy", match.group("streamStrategy"))
            perf_record_string(performance, "streamReady", match.group("streamReady"))
            perf_record_string(performance, "gpu", match.group("gpu").strip())
            perf_record_string(performance, "arenaReady", match.group("arenaReady"))
            for key in (
                "batches",
                "draws",
                "drawIndexes",
                "streamWraps",
                "streamRejects",
                "shadowUploads",
                "frames",
                "backendQueries",
                "staticBatches",
                "staticPackets",
                "staticSurfaces",
                "staticVerts",
                "staticIndexes",
            ):
                perf_record_numeric(performance, key, int_group(match, key))
            for key in ("streamMegabytes", "staticMegabytes", "arenaMegabytes"):
                perf_record_numeric(performance, key, float(match.group(key)))
            continue

        match = GLX_MATERIAL_RENDERER_SUMMARY_RE.search(line)
        if match:
            perf_record_string(performance, "materialRenderer", match.group("enabled"))
            perf_record_string(performance, "materialReady", match.group("ready"))
            perf_record_match_numbers_prefixed(
                performance,
                match,
                "material",
                (
                    "programs",
                    "binds",
                    "bindAttempts",
                    "switches",
                    "cacheHits",
                    "cacheMisses",
                    "compileFailures",
                    "linkFailures",
                    "precacheFailures",
                    "bindFailures",
                    "labels",
                ),
            )
            continue

        match = GLX_POSTPROCESS_SUMMARY_RE.search(line)
        if match:
            perf_record_string(performance, "fbo", match.group("fbo"))
            perf_record_string(performance, "postprocessLast", match.group("last"))
            perf_record_match_numbers_prefixed(
                performance,
                match,
                "postprocess",
                (
                    "width",
                    "height",
                    "captureWidth",
                    "captureHeight",
                    "bloom",
                    "frames",
                    "final",
                    "prefinal",
                    "gammaDirect",
                    "gammaBlit",
                    "copies",
                    "msaa",
                    "ssaa",
                ),
            )
            continue

        match = GLX_STREAM_DRAW_SUMMARY_RE.search(line)
        if match:
            perf_record_match_numbers_prefixed(
                performance,
                match,
                "streamDraw",
                ("draws", "attempts", "indexes", "fallbacks", "skips"),
            )
            if match.group("shadows") is not None:
                perf_record_numeric(performance, "streamDrawShadows", int(match.group("shadows")))
            if match.group("beams") is not None:
                perf_record_numeric(performance, "streamDrawBeams", int(match.group("beams")))
            if match.group("postprocess") is not None:
                perf_record_numeric(performance, "streamDrawPostProcess", int(match.group("postprocess")))
            for key in ("megabytes", "indexMegabytes", "tex1Megabytes"):
                perf_record_numeric(performance, prefixed_key("streamDraw", key), float(match.group(key)))
            continue

        match = GLX_STATIC_DRAW_SUMMARY_RE.search(line)
        if match:
            perf_record_match_numbers_prefixed(
                performance,
                match,
                "staticDraw",
                ("calls", "attempts", "indexes", "fallbacks", "policySkips"),
            )
            continue

        match = GLX_STATIC_MDI_SUMMARY_RE.search(line)
        if match:
            perf_record_match_numbers_prefixed(
                performance,
                match,
                "staticMdi",
                ("calls", "attempts", "runs", "indexes", "fallbacks", "skips", "errors", "largest"),
            )
            continue

    return performance


def merge_budget(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    merged: dict[str, object] = {}
    for section in ("max", "min"):
        values: dict[str, object] = {}
        base_section = base.get(section)
        override_section = override.get(section)
        if isinstance(base_section, dict):
            values.update(base_section)
        if isinstance(override_section, dict):
            values.update(override_section)
        if values:
            merged[section] = values
    return merged


def load_json_file(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return data


def load_performance_budget(path: Path | None, include_default: bool) -> dict[str, object]:
    budget = dict(DEFAULT_PERFORMANCE_BUDGET) if include_default else {}
    if path is not None:
        loaded = load_json_file(path.resolve())
        budget = merge_budget(budget, loaded)
    return budget


def aggregate_performance_samples(samples: list[dict[str, object]]) -> dict[str, object]:
    aggregate: dict[str, object] = {
        "sampleCount": 0,
        "latest": {},
        "max": {},
    }
    latest: dict[str, object] = aggregate["latest"]  # type: ignore[assignment]
    maxima: dict[str, object] = aggregate["max"]  # type: ignore[assignment]

    for sample in samples:
        aggregate["sampleCount"] = int(aggregate["sampleCount"]) + int(sample.get("sampleCount", 0))
        sample_latest = sample.get("latest", {})
        sample_max = sample.get("max", {})

        if isinstance(sample_latest, dict):
            latest.update(sample_latest)
        if isinstance(sample_max, dict):
            for key, value in sample_max.items():
                if isinstance(value, (int, float)):
                    previous = maxima.get(key)
                    maxima[key] = max(previous, value) if isinstance(previous, (int, float)) else value
                else:
                    maxima[key] = value

    return aggregate


def performance_metric(aggregate: dict[str, object], key: str) -> object | None:
    maxima = aggregate.get("max", {})
    latest = aggregate.get("latest", {})
    if isinstance(maxima, dict) and key in maxima:
        return maxima[key]
    if isinstance(latest, dict) and key in latest:
        return latest[key]
    if key in aggregate:
        return aggregate[key]
    return None


def numeric_metric(aggregate: dict[str, object], key: str) -> float | None:
    value = performance_metric(aggregate, key)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def evaluate_performance_budget(
    aggregate: dict[str, object],
    budget: dict[str, object],
) -> list[str]:
    failures: list[str] = []

    max_budget = budget.get("max", {})
    if isinstance(max_budget, dict):
        for key, threshold in sorted(max_budget.items()):
            value = numeric_metric(aggregate, str(key))
            if value is None or not isinstance(threshold, (int, float)):
                continue
            if value > float(threshold):
                failures.append(f"Performance budget max {key} exceeded: {value:g} > {float(threshold):g}.")

    min_budget = budget.get("min", {})
    if isinstance(min_budget, dict):
        for key, threshold in sorted(min_budget.items()):
            value = numeric_metric(aggregate, str(key))
            if value is None or not isinstance(threshold, (int, float)):
                continue
            if value < float(threshold):
                failures.append(f"Performance budget min {key} missed: {value:g} < {float(threshold):g}.")

    return failures


def baseline_performance_object(data: dict[str, object]) -> dict[str, object]:
    performance = data.get("performance")
    if isinstance(performance, dict):
        return performance
    return data


def compare_performance_baseline(
    aggregate: dict[str, object],
    baseline: dict[str, object],
    max_growth_ratio: float,
) -> tuple[list[str], list[dict[str, object]]]:
    failures: list[str] = []
    comparisons: list[dict[str, object]] = []
    baseline_perf = baseline_performance_object(baseline)

    for key in PERFORMANCE_BASELINE_GROWTH_KEYS:
        current = numeric_metric(aggregate, key)
        previous = numeric_metric(baseline_perf, key)
        if current is None or previous is None:
            continue

        allowed = previous * (1.0 + max_growth_ratio)
        comparison = {
            "metric": key,
            "baseline": previous,
            "current": current,
            "allowed": allowed,
            "growthRatio": (current - previous) / previous if previous > 0.0 else (0.0 if current <= 0.0 else None),
            "status": "passed",
        }
        if previous <= 0.0:
            if current > 0.0:
                comparison["status"] = "failed"
                failures.append(f"Performance baseline {key} grew from 0 to {current:g}.")
        elif current > allowed:
            comparison["status"] = "failed"
            failures.append(
                f"Performance baseline {key} grew by {((current - previous) / previous):.1%}: "
                f"{current:g} > {allowed:g}."
            )
        comparisons.append(comparison)

    return failures, comparisons


def write_performance_baseline(
    path: Path,
    aggregate: dict[str, object],
    manifest: dict[str, object],
) -> None:
    payload = {
        "version": 1,
        "createdUtc": datetime.now(timezone.utc).isoformat(),
        "runId": manifest.get("runId", ""),
        "gate": manifest.get("gate", ""),
        "profile": manifest.get("profile", ""),
        "maps": manifest.get("maps", []),
        "demos": manifest.get("demos", []),
        "performance": aggregate,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8", newline="\n")


def evaluate_gate(manifest: dict[str, object]) -> list[str]:
    gate_name = manifest.get("gate")
    if manifest.get("dryRun"):
        return []

    preset = RC_GATE_PRESETS[str(gate_name)] if gate_name else {"requirements": {}}
    requirements = preset["requirements"]  # type: ignore[index]
    failures: list[str] = []
    runs = manifest.get("runs", [])
    if not isinstance(runs, list):
        return ["Manifest does not contain a run list."]

    failed_runs = [
        run for run in runs
        if isinstance(run, dict) and run.get("status") != "passed"
    ]
    if failed_runs:
        labels = [
            f"{run.get('type', 'run')}:{run.get('status', 'unknown')}"
            for run in failed_runs
        ]
        failures.append("Process failures: " + ", ".join(labels))

    diagnostics = [
        run.get("diagnostics")
        for run in runs
        if isinstance(run, dict) and isinstance(run.get("diagnostics"), dict)
    ]
    diagnostic_failures = [
        str(failure)
        for diagnostics_result in diagnostics
        for failure in diagnostics_result.get("failures", [])  # type: ignore[union-attr]
        if str(failure).strip()
    ]
    if diagnostic_failures:
        failures.append(
            "GLx diagnostic failures: " +
            "; ".join(dict.fromkeys(diagnostic_failures))
        )

    if requirements.get("require_glx_diagnostics"):
        if not diagnostics:
            failures.append("No GLx diagnostics were collected for a diagnostic gate.")
        elif not any(diagnostics_result.get("found") for diagnostics_result in diagnostics):
            failures.append("No GLx diagnostic output was found in collected logs.")

    performance_samples = [
        run.get("performance")
        for run in runs
        if isinstance(run, dict) and isinstance(run.get("performance"), dict)
    ]
    if requirements.get("require_glx_performance_samples"):
        if not performance_samples:
            failures.append("No GLx performance samples were collected for a performance gate.")
        elif not any(int(sample.get("sampleCount", 0)) > 0 for sample in performance_samples):
            failures.append("No r_speeds 7 GLx frame-counter samples were found in collected logs.")

    performance_failures = [
        str(failure)
        for failure in manifest.get("performanceFailures", [])
        if str(failure).strip()
    ]
    if performance_failures:
        failures.append(
            "GLx performance budget failures: " +
            "; ".join(dict.fromkeys(performance_failures))
        )

    if requirements.get("require_screenshots") or manifest.get("screenshotBaselineDir"):
        screenshots = [
            shot
            for run in runs
            if isinstance(run, dict)
            for shot in run.get("screenshots", [])
            if isinstance(shot, dict)
        ]
        if requirements.get("require_screenshots") and not screenshots:
            failures.append("No screenshots were planned or captured.")
        missing = [shot["name"] for shot in screenshots if not shot.get("found")]
        if (requirements.get("require_screenshots") or manifest.get("screenshotBaselineDir")) and missing:
            failures.append(
                f"Missing screenshots: {len(missing)}/{len(screenshots)} "
                f"({', '.join(str(name) for name in missing[:6])}"
                f"{'...' if len(missing) > 6 else ''})"
            )

        if manifest.get("screenshotBaselineDir") and not manifest.get("approveScreenshotBaselines"):
            missing_baselines = [
                shot.get("baselineKey", shot.get("name", "screenshot"))
                for shot in screenshots
                if shot.get("found") and shot.get("baselineStatus") == "missing"
            ]
            if missing_baselines:
                failures.append(
                    f"Missing screenshot baselines: {len(missing_baselines)}/{len(screenshots)} "
                    f"({', '.join(str(name) for name in missing_baselines[:6])}"
                    f"{'...' if len(missing_baselines) > 6 else ''})"
                )

            failed_comparisons = [
                shot
                for shot in screenshots
                if isinstance(shot.get("comparison"), dict) and
                shot["comparison"].get("status") != "passed"  # type: ignore[index]
            ]
            if failed_comparisons:
                labels = []
                for shot in failed_comparisons[:6]:
                    comparison = shot.get("comparison", {})
                    reason = (
                        comparison.get("reason")
                        if isinstance(comparison, dict)
                        else "diff-threshold"
                    )
                    labels.append(
                        f"{shot.get('baselineKey', shot.get('name', 'screenshot'))}:{reason or 'diff-threshold'}"
                    )
                failures.append(
                    f"Screenshot baseline comparisons failed: {len(failed_comparisons)}/{len(screenshots)} "
                    f"({', '.join(labels)}{'...' if len(failed_comparisons) > 6 else ''})"
                )

    timedemos: dict[tuple[str, str], dict[str, object]] = {}
    for run in runs:
        if not isinstance(run, dict) or run.get("type") != "timedemo":
            continue
        renderer = str(run.get("renderer", ""))
        demo = str(run.get("demo", ""))
        metrics = run.get("timedemoMetrics")
        if isinstance(metrics, dict):
            timedemos[(renderer.lower(), demo.lower())] = metrics

    demos = [
        str(demo).lower()
        for demo in manifest.get("demos", [])
        if str(demo).strip()
    ]
    renderers = [
        str(renderer).lower()
        for renderer in manifest.get("renderers", [])
        if str(renderer).strip()
    ]

    if requirements.get("require_timedemo_metrics"):
        if not demos:
            failures.append("No demos were configured for a timedemo gate.")
        missing_metrics: list[str] = []
        for renderer in renderers:
            for demo in demos:
                if (renderer, demo) not in timedemos:
                    missing_metrics.append(f"{renderer}/{demo}")
        if missing_metrics:
            failures.append(
                "Missing timedemo metrics: " + ", ".join(missing_metrics[:8]) +
                ("..." if len(missing_metrics) > 8 else "")
            )

    min_ratio = requirements.get("min_timedemo_fps_ratio")
    if min_ratio is not None:
        baseline = str(requirements.get("baseline_renderer", "opengl")).lower()
        candidate = str(requirements.get("candidate_renderer", "glx")).lower()
        for demo in demos:
            base = timedemos.get((baseline, demo))
            cand = timedemos.get((candidate, demo))
            if not base or not cand:
                continue

            base_fps = float(base.get("fps", 0.0))
            cand_fps = float(cand.get("fps", 0.0))
            if base_fps <= 0.0:
                failures.append(f"Invalid baseline timedemo FPS for {baseline}/{demo}.")
                continue

            ratio = cand_fps / base_fps
            if ratio < float(min_ratio):
                failures.append(
                    f"Timedemo FPS ratio for {candidate}/{demo} is {ratio:.1%}; "
                    f"required >= {float(min_ratio):.1%} of {baseline} "
                    f"({cand_fps:.1f} vs {base_fps:.1f} fps)."
                )

    return failures


def run_status(manifest: dict[str, object]) -> str:
    if manifest.get("dryRun"):
        return "planned"

    failures = manifest.get("gateFailures", [])
    if isinstance(failures, list) and failures:
        return "failed"

    runs = manifest.get("runs", [])
    if not isinstance(runs, list):
        return "failed"

    if any(isinstance(run, dict) and run.get("status") != "passed" for run in runs):
        return "failed"
    return "passed"


def markdown_summary(manifest: dict[str, object], manifest_path: Path) -> str:
    runs = [run for run in manifest.get("runs", []) if isinstance(run, dict)]
    screenshots = [
        shot
        for run in runs
        for shot in run.get("screenshots", [])
        if isinstance(shot, dict)
    ]
    timedemos = [
        run
        for run in runs
        if run.get("type") == "timedemo"
    ]
    diagnostics = [
        run.get("diagnostics")
        for run in runs
        if isinstance(run.get("diagnostics"), dict)
    ]
    performance_samples = [
        run.get("performance")
        for run in runs
        if isinstance(run.get("performance"), dict)
    ]
    status = run_status(manifest)
    gate = str(manifest.get("gate") or "custom")
    profile = str(manifest.get("profile") or "")

    lines = [
        f"# GLx Sweep {manifest.get('runId', '')}",
        "",
        f"- Status: `{status}`",
        f"- Gate: `{gate}`",
        f"- Profile: `{profile}`",
        f"- Dry run: `{str(bool(manifest.get('dryRun'))).lower()}`",
        f"- Manifest: `{manifest_path}`",
        f"- Renderers: `{', '.join(str(item) for item in manifest.get('renderers', []))}`",
        f"- Maps: `{', '.join(str(item) for item in manifest.get('maps', [])) or '-'}`",
        f"- Demos: `{', '.join(str(item) for item in manifest.get('demos', [])) or '-'}`",
        "",
    ]

    gate_failures = manifest.get("gateFailures", [])
    if isinstance(gate_failures, list) and gate_failures:
        lines.append("## Gate Failures")
        lines.append("")
        for failure in gate_failures:
            lines.append(f"- {failure}")
        lines.append("")

    if runs:
        planned_or_passed = sum(1 for run in runs if run.get("status") in {"passed", "planned"})
        lines.append("## Runs")
        lines.append("")
        lines.append(f"- Passed or planned: `{planned_or_passed}/{len(runs)}`")
        for run in runs:
            label = str(run.get("type", "run"))
            renderer = run.get("renderer")
            demo = run.get("demo")
            if renderer or demo:
                label += f" `{renderer or '-'}/{demo or '-'}`"
            lines.append(f"- `{run.get('status', 'unknown')}` {label}")
        lines.append("")

    if diagnostics:
        lines.append("## GLx Diagnostics")
        lines.append("")
        for index, diagnostics_result in enumerate(diagnostics, start=1):
            if not isinstance(diagnostics_result, dict):
                continue
            failures = [
                str(failure)
                for failure in diagnostics_result.get("failures", [])
                if str(failure).strip()
            ]
            lines.append(
                f"- Log {index}: found `"
                f"{str(bool(diagnostics_result.get('found'))).lower()}`, "
                f"failures `{len(failures)}`"
            )
            for failure in failures[:8]:
                lines.append(f"- {failure}")

            metrics = diagnostics_result.get("metrics", {})
            if isinstance(metrics, dict) and metrics:
                material = metrics.get("material", {}) if isinstance(metrics.get("material"), dict) else {}
                postprocess = metrics.get("postprocess", {}) if isinstance(metrics.get("postprocess"), dict) else {}
                stream = metrics.get("stream", {}) if isinstance(metrics.get("stream"), dict) else {}
                stream_draw = metrics.get("streamDraw", {}) if isinstance(metrics.get("streamDraw"), dict) else {}
                static_world = metrics.get("staticWorld", {}) if isinstance(metrics.get("staticWorld"), dict) else {}
                lines.append(
                    "- Key metrics: "
                    f"material ready `{material.get('ready', '-')}`, "
                    f"material compile/link/precache/bind failures "
                    f"`{material.get('compile', '-')}/{material.get('link', '-')}/"
                    f"{material.get('precacheFailures', '-')}/{material.get('bind', '-')}`, "
                    f"FBO failures `{postprocess.get('fboFailed', '-')}`, "
                    f"stream ready `{stream.get('ready', '-')}`, "
                    f"stream upload/reservation/draw fallbacks "
                    f"`{stream.get('uploadFailures', '-')}/{stream.get('reservationFailures', '-')}/"
                    f"{stream_draw.get('fallbacks', '-')}`, "
                    f"static errors/failures `{static_world.get('glErrors', '-')}/"
                    f"{static_world.get('failures', '-')}`"
                )
        lines.append("")

    if performance_samples:
        lines.append("## GLx Performance Samples")
        lines.append("")
        for index, sample in enumerate(performance_samples, start=1):
            if not isinstance(sample, dict):
                continue
            latest = sample.get("latest", {})
            maxima = sample.get("max", {})
            if not isinstance(latest, dict):
                latest = {}
            if not isinstance(maxima, dict):
                maxima = {}
            lines.append(
                f"- Log {index}: samples `{sample.get('sampleCount', 0)}`, "
                f"tier `{latest.get('tier', '-')}`, gpu `{latest.get('gpu', '-')}`, "
                f"draws/indexes `{latest.get('draws', '-')}/{latest.get('drawIndexes', '-')}`, "
                f"stream `{latest.get('streamStrategy', '-')}/{latest.get('streamReady', '-')}`, "
                f"stream draw attempts `{latest.get('streamDrawDraws', '-')}/"
                f"{latest.get('streamDrawAttempts', '-')}`, "
                f"static packets `{latest.get('staticPackets', '-')}`"
            )
            lines.append(
                "- Max counters: "
                f"backend queries `{maxima.get('backendQueries', '-')}`, "
                f"stream rejects `{maxima.get('streamRejects', '-')}`, "
                f"material failures compile/link/precache/bind "
                f"`{maxima.get('materialCompileFailures', '-')}/"
                f"{maxima.get('materialLinkFailures', '-')}/"
                f"{maxima.get('materialPrecacheFailures', '-')}/"
                f"{maxima.get('materialBindFailures', '-')}`, "
                f"stream draw fallbacks `{maxima.get('streamDrawFallbacks', '-')}`, "
                f"static draw fallbacks `{maxima.get('staticDrawFallbacks', '-')}`, "
                f"static MDI errors `{maxima.get('staticMdiErrors', '-')}`"
            )
        performance_failures = [
            str(failure)
            for failure in manifest.get("performanceFailures", [])
            if str(failure).strip()
        ]
        baseline_status = str(manifest.get("performanceBaselineStatus", ""))
        if performance_failures or baseline_status:
            lines.append("")
            if baseline_status:
                lines.append(f"- Performance baseline: `{baseline_status}`")
            for failure in performance_failures[:12]:
                lines.append(f"- {failure}")

        comparisons = [
            comparison
            for comparison in manifest.get("performanceComparisons", [])
            if isinstance(comparison, dict)
        ]
        failed_comparisons = [
            comparison
            for comparison in comparisons
            if comparison.get("status") != "passed"
        ]
        if failed_comparisons:
            lines.append("")
            lines.append("| Metric | Baseline | Current | Allowed |")
            lines.append("|---|---:|---:|---:|")
            for comparison in failed_comparisons[:12]:
                lines.append(
                    "| "
                    f"{comparison.get('metric', '-')} | "
                    f"{comparison.get('baseline', '-')} | "
                    f"{comparison.get('current', '-')} | "
                    f"{comparison.get('allowed', '-')} |"
                )
        lines.append("")

    if screenshots:
        found = sum(1 for shot in screenshots if shot.get("found"))
        if manifest.get("dryRun"):
            lines.append(f"## Screenshots\n\n- Planned: `{len(screenshots)}`\n")
        else:
            lines.append(
                f"## Screenshots\n\n- Found: `{found}/{len(screenshots)}`\n"
            )

        baseline_statuses = [
            str(shot.get("baselineStatus"))
            for shot in screenshots
            if shot.get("baselineStatus")
        ]
        if baseline_statuses:
            counts = {
                status: baseline_statuses.count(status)
                for status in sorted(set(baseline_statuses))
            }
            lines.append("## Screenshot Baselines")
            lines.append("")
            lines.append(
                "- Thresholds: "
                f"`rms <= {manifest.get('screenshotThresholds', {}).get('maxRms', '-')}`, "
                "`changed pixels <= "
                f"{manifest.get('screenshotThresholds', {}).get('maxChangedPixelRatio', '-')}`"
            )
            for status, count in counts.items():
                lines.append(f"- `{status}`: `{count}`")

            failed = [
                shot
                for shot in screenshots
                if shot.get("baselineStatus") in {"failed", "missing"}
            ]
            if failed:
                lines.append("")
                lines.append("| Screenshot | Status | RMS | Changed Pixels |")
                lines.append("|---|---:|---:|---:|")
                for shot in failed[:12]:
                    comparison = shot.get("comparison")
                    if isinstance(comparison, dict):
                        rms = comparison.get("rms", "-")
                        ratio = comparison.get("changedPixelRatio", "-")
                        if isinstance(rms, (int, float)):
                            rms = f"{float(rms):.3f}"
                        if isinstance(ratio, (int, float)):
                            ratio = f"{float(ratio):.3%}"
                    else:
                        rms = ratio = "-"
                    lines.append(
                        "| "
                        f"{shot.get('baselineKey', shot.get('name', '-'))} | "
                        f"{shot.get('baselineStatus', '-')} | "
                        f"{rms} | {ratio} |"
                    )
            lines.append("")

    if timedemos:
        lines.append("## Timedemos")
        lines.append("")
        lines.append("| Renderer | Demo | Status | FPS | Frames | Seconds |")
        lines.append("|---|---|---:|---:|---:|---:|")
        for run in timedemos:
            metrics = run.get("timedemoMetrics")
            if isinstance(metrics, dict):
                fps = f"{float(metrics.get('fps', 0.0)):.1f}"
                frames = str(metrics.get("frames", "-"))
                seconds = f"{float(metrics.get('seconds', 0.0)):.2f}"
            else:
                fps = frames = seconds = "-"
            lines.append(
                "| "
                f"{run.get('renderer', '-')} | "
                f"{run.get('demo', '-')} | "
                f"{run.get('status', 'unknown')} | "
                f"{fps} | {frames} | {seconds} |"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    if args.list_gates:
        print_gate_list()
        return 0

    apply_gate_defaults(args)

    exe = resolve_exe(args.exe, allow_missing=args.dry_run)
    basepath = args.basepath.resolve() if args.basepath else exe.parent.resolve()
    renderers = split_csv(args.renderers)
    switch_sequence = split_csv(args.switch_sequence) if args.switch_sequence else list(renderers)
    maps_value = args.maps if args.maps is not None else PROFILE_MAPS.get(args.profile, "q3dm1")
    maps = split_csv(maps_value)
    demos = split_csv(args.demos)

    validate_renderers(renderers)
    validate_renderers(switch_sequence)

    run_id = (
        datetime.now(timezone.utc).strftime("glx-sweep-%Y%m%d-%H%M%S-%f") +
        f"-p{os.getpid()}"
    )
    output_root = args.output_dir.resolve() / run_id
    homepath = args.homepath.resolve() if args.homepath else output_root / "home"
    logs_dir = output_root / "logs"
    cvars = make_cvars(args)
    cfg_cvars = config_cvars(args, cvars)
    startup_cvars = launch_cvars(cvars)
    runs: list[dict[str, object]] = []
    screenshot_baseline_dir = args.screenshot_baseline_dir.resolve() if args.screenshot_baseline_dir else None
    screenshot_diff_dir = args.screenshot_diff_dir.resolve() if args.screenshot_diff_dir else None
    screenshot_max_rms = float(args.screenshot_max_rms)
    screenshot_max_pixel_ratio = float(args.screenshot_max_pixel_ratio)
    if args.approve_screenshot_baselines and screenshot_baseline_dir is None:
        raise ValueError("--approve-screenshot-baselines requires --screenshot-baseline-dir.")
    if screenshot_diff_dir is not None and screenshot_baseline_dir is None:
        raise ValueError("--screenshot-diff-dir requires --screenshot-baseline-dir.")
    if screenshot_max_rms < 0.0:
        raise ValueError("--screenshot-max-rms must be non-negative.")
    if not 0.0 <= screenshot_max_pixel_ratio <= 1.0:
        raise ValueError("--screenshot-max-pixel-ratio must be between 0 and 1.")
    if args.perf_sample_wait < 0:
        raise ValueError("--perf-sample-wait must be non-negative.")
    if args.approve_performance_baseline and args.performance_baseline is None:
        raise ValueError("--approve-performance-baseline requires --performance-baseline.")
    if args.performance_max_growth_ratio is not None and args.performance_max_growth_ratio < 0.0:
        raise ValueError("--performance-max-growth-ratio must be non-negative.")
    performance_growth_ratio = (
        DEFAULT_PERFORMANCE_MAX_GROWTH_RATIO
        if args.performance_max_growth_ratio is None
        else args.performance_max_growth_ratio
    )
    performance_budget = load_performance_budget(
        args.performance_budget,
        include_default=bool(args.gate) and not args.no_performance_budget,
    )

    if not args.no_switch_sweep and maps:
        switch_cfg_name = f"{run_id}-switch.cfg"
        switch_cfg, expected_shots = build_switch_cfg(args, cfg_cvars, maps, switch_sequence, run_id)
        cfg_path = write_cfg(homepath, args.fs_game, switch_cfg_name, switch_cfg)
        command = base_launch_args(
            exe,
            basepath,
            homepath,
            args.fs_game,
            switch_sequence[0],
            switch_cfg_name,
            startup_cvars,
        )
        switch_log_path = logs_dir / "switch-screenshots.log"
        result = run_engine(
            command,
            exe.parent,
            args.timeout,
            switch_log_path,
            args.dry_run,
        )
        shots = screenshot_results(homepath, args.fs_game, expected_shots)
        if not args.dry_run:
            apply_screenshot_baselines(
                shots,
                screenshot_baseline_dir,
                args.approve_screenshot_baselines,
                screenshot_diff_dir,
                screenshot_max_rms,
                screenshot_max_pixel_ratio,
            )
            if any(renderer.lower() == "glx" for renderer in switch_sequence):
                result["diagnostics"] = analyze_glx_diagnostics(switch_log_path, args.profile)
                result["performance"] = analyze_glx_performance(switch_log_path)
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
                cfg_path = write_cfg(homepath, args.fs_game, cfg_name, build_demo_cfg(args, cfg_cvars, demo))
                command = base_launch_args(
                    exe,
                    basepath,
                    homepath,
                    args.fs_game,
                    renderer,
                    cfg_name,
                    startup_cvars,
                )
                log_path = logs_dir / f"demo-{safe_renderer}-{safe_demo}.log"
                result = run_engine(
                    command,
                    exe.parent,
                    args.timeout,
                    log_path,
                    args.dry_run,
                )
                metrics = timedemo_metrics(log_path)
                result.update(
                    {
                        "type": "timedemo",
                        "config": str(cfg_path),
                        "renderer": renderer,
                        "demo": demo,
                    }
                )
                if metrics:
                    result["timedemoMetrics"] = metrics
                runs.append(result)

    manifest = {
        "runId": run_id,
        "createdUtc": datetime.now(timezone.utc).isoformat(),
        "dryRun": args.dry_run,
        "gate": args.gate or "",
        "gateDescription": (
            RC_GATE_PRESETS[args.gate]["description"] if args.gate else ""
        ),
        "gateRequirements": (
            RC_GATE_PRESETS[args.gate]["requirements"] if args.gate else {}
        ),
        "exe": str(exe),
        "cwd": str(exe.parent),
        "basepath": str(basepath),
        "homepath": str(homepath),
        "fsGame": args.fs_game,
        "profile": args.profile,
        "cvars": cvars,
        "startupCvars": startup_cvars,
        "configCvars": cfg_cvars,
        "renderers": renderers,
        "switchSequence": switch_sequence,
        "maps": maps,
        "demos": demos,
        "perfSamplesEnabled": not args.no_perf_samples,
        "perfSampleWait": args.perf_sample_wait,
        "performanceBudget": performance_budget,
        "performanceBaselinePath": str(args.performance_baseline.resolve()) if args.performance_baseline else "",
        "approvePerformanceBaseline": args.approve_performance_baseline,
        "performanceMaxGrowthRatio": performance_growth_ratio,
        "screenshotBaselineDir": str(screenshot_baseline_dir) if screenshot_baseline_dir else "",
        "screenshotDiffDir": str(screenshot_diff_dir) if screenshot_diff_dir else "",
        "approveScreenshotBaselines": args.approve_screenshot_baselines,
        "screenshotThresholds": {
            "maxRms": screenshot_max_rms,
            "maxChangedPixelRatio": screenshot_max_pixel_ratio,
        },
        "runs": runs,
    }

    performance_samples = [
        run.get("performance")
        for run in runs
        if isinstance(run, dict) and isinstance(run.get("performance"), dict)
    ]
    performance_aggregate = aggregate_performance_samples(  # type: ignore[arg-type]
        [sample for sample in performance_samples if isinstance(sample, dict)]
    )
    manifest["performanceAggregate"] = performance_aggregate
    has_performance_samples = int(performance_aggregate.get("sampleCount", 0)) > 0

    performance_failures: list[str] = []
    performance_comparisons: list[dict[str, object]] = []
    if has_performance_samples and performance_budget:
        performance_failures.extend(
            evaluate_performance_budget(performance_aggregate, performance_budget)
        )

    if has_performance_samples and args.performance_baseline:
        baseline_path = args.performance_baseline.resolve()
        if args.approve_performance_baseline:
            write_performance_baseline(baseline_path, performance_aggregate, manifest)
            manifest["performanceBaselineStatus"] = "approved"
        elif baseline_path.exists():
            baseline = load_json_file(baseline_path)
            baseline_failures, performance_comparisons = compare_performance_baseline(
                performance_aggregate,
                baseline,
                performance_growth_ratio,
            )
            performance_failures.extend(baseline_failures)
            manifest["performanceBaselineStatus"] = "compared"
        else:
            performance_failures.append(f"Performance baseline is missing: {baseline_path}")
            manifest["performanceBaselineStatus"] = "missing"
    elif args.performance_baseline:
        manifest["performanceBaselineStatus"] = "not-sampled"

    manifest["performanceComparisons"] = performance_comparisons
    manifest["performanceFailures"] = list(dict.fromkeys(performance_failures))

    gate_failures = evaluate_gate(manifest)
    manifest["gateFailures"] = gate_failures

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
        shot for run in runs for shot in run.get("screenshots", [])  # type: ignore[attr-defined]
    ]
    found_screenshots = sum(1 for shot in screenshots if shot["found"])
    missing_screenshots = len(screenshots) - found_screenshots

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
            baseline_statuses = [
                str(shot.get("baselineStatus"))
                for shot in screenshots
                if shot.get("baselineStatus")
            ]
            if baseline_statuses:
                counts = {
                    status: baseline_statuses.count(status)
                    for status in sorted(set(baseline_statuses))
                }
                summary = ", ".join(f"{status}={count}" for status, count in counts.items())
                print(f"Screenshot baselines: {summary}")
    performance_samples_count = int(performance_aggregate.get("sampleCount", 0))
    if performance_samples_count:
        print(f"GLx performance samples: {performance_samples_count}")
        baseline_status = manifest.get("performanceBaselineStatus")
        if baseline_status:
            print(f"Performance baseline: {baseline_status}")
        if manifest["performanceFailures"]:
            print(f"Performance budget/baseline failures: {len(manifest['performanceFailures'])}")
    if args.dry_run:
        return 0
    if gate_failures or passed_runs != run_count or missing_screenshots:
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"glx_runtime_sweep.py: {exc}", file=sys.stderr)
        raise SystemExit(2)

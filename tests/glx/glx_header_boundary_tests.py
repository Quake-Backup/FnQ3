from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

PURE_HEADERS = (
    "code/renderercommon/tr_glx_public.h",
    "code/rendererglx/glx_types.h",
    "code/rendererglx/glx_caps_logic.h",
    "code/rendererglx/glx_material_key.h",
    "code/rendererglx/glx_stream_logic.h",
    "code/rendererglx/glx_static_world_logic.h",
)

MODULE_BRIDGE_HEADERS = (
    "code/rendererglx/glx_module.h",
)

PURE_BANNED_INCLUDE_FRAGMENTS = (
    "../renderer/",
    "renderer/qgl.h",
    "qcommon.h",
    "tr_public.h",
    "qgl.h",
    "glx_local.h",
    "glx_module.h",
    "glx_caps.h",
    "glx_material.h",
    "glx_stream.h",
    "glx_static_world.h",
    "glx_profiler.h",
    "glx_postprocess.h",
)

MODULE_BANNED_INCLUDE_FRAGMENTS = (
    "../renderer/",
    "renderer/qgl.h",
    "qcommon.h",
    "tr_public.h",
    "qgl.h",
    "glx_local.h",
)

PURE_BANNED_TYPE_PATTERNS = (
    r"\bGLenum\b",
    r"\bGLuint\b",
    r"\bGLint\b",
    r"\bGLsizei\b",
    r"\bGLchar\b",
    r"\bGLfloat\b",
    r"\bGLvoid\b",
    r"\bglconfig_t\b",
    r"\brefimport_t\b",
    r"\brefexport_t\b",
    r"\brefShutdownCode_t\b",
    r"\bcvar_t\b",
    r"\bshader_t\b",
    r"\bshaderStage_t\b",
    r"\bmsurface_t\b",
)

MODULE_BANNED_TYPE_PATTERNS = (
    r"\bGLenum\b",
    r"\bGLuint\b",
    r"\bGLint\b",
    r"\bGLsizei\b",
    r"\bGLchar\b",
    r"\bGLfloat\b",
    r"\bGLvoid\b",
    r"\brefShutdownCode_t\b",
    r"\bcvar_t\b",
    r"\bshader_t\b",
    r"\bshaderStage_t\b",
    r"\bmsurface_t\b",
)


def scan_header(
    path: Path,
    banned_include_fragments: tuple[str, ...],
    banned_type_patterns: tuple[str, ...],
) -> list[str]:
    failures: list[str] = []
    text = path.read_text(encoding="utf-8")

    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#include"):
            for fragment in banned_include_fragments:
                if fragment in stripped:
                    failures.append(f"{path}:{line_no}: banned include dependency: {stripped}")

        if "qgl" in line:
            failures.append(f"{path}:{line_no}: banned qgl reference: {stripped}")

        for pattern in banned_type_patterns:
            if re.search(pattern, line):
                failures.append(f"{path}:{line_no}: banned renderer/OpenGL type: {stripped}")

    return failures


def main() -> int:
    failures: list[str] = []

    for relative in PURE_HEADERS:
        path = ROOT / relative
        if not path.exists():
            failures.append(f"{path}: missing pure GLx header")
            continue
        failures.extend(scan_header(path, PURE_BANNED_INCLUDE_FRAGMENTS, PURE_BANNED_TYPE_PATTERNS))

    for relative in MODULE_BRIDGE_HEADERS:
        path = ROOT / relative
        if not path.exists():
            failures.append(f"{path}: missing GLx module bridge header")
            continue
        failures.extend(scan_header(path, MODULE_BANNED_INCLUDE_FRAGMENTS, MODULE_BANNED_TYPE_PATTERNS))

    if failures:
        print("Pure GLx header boundary violations:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1

    print(
        f"Checked {len(PURE_HEADERS)} pure GLx headers and "
        f"{len(MODULE_BRIDGE_HEADERS)} module bridge header; no legacy renderer dependencies found."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

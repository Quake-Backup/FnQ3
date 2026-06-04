from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(text: str, needle: str, label: str, failures: list[str]) -> None:
    if needle not in text:
        failures.append(f"missing {label}: {needle}")


def require_order(text: str, needles: list[str], label: str, failures: list[str]) -> None:
    position = 0
    for needle in needles:
        found = text.find(needle, position)
        if found < 0:
            failures.append(f"missing ordered {label}: {needle}")
            return
        position = found + len(needle)


def section(text: str, start: str, end: str, label: str, failures: list[str]) -> str:
    start_index = text.find(start)
    if start_index < 0:
        failures.append(f"missing section start {label}: {start}")
        return ""
    end_index = text.find(end, start_index)
    if end_index < 0:
        failures.append(f"missing section end {label}: {end}")
        return text[start_index:]
    return text[start_index:end_index]


def check_source(label: str, relative_path: str, failures: list[str]) -> None:
    source = (ROOT / relative_path).read_text(encoding="utf-8")
    snap = section(
        source,
        "static float R_CSMSnapLightCoord",
        "static void R_CSMBuildLightAxis",
        f"{label} CSM snap helper",
        failures,
    )
    cascade = section(
        source,
        "static void R_CSMPlanCascade",
        "static void R_PlanCascadedShadows",
        f"{label} CSM cascade planner",
        failures,
    )
    planner = section(
        source,
        "static void R_PlanCascadedShadows",
        "/*\n=============\nR_PlaneForSurface",
        f"{label} CSM planner",
        failures,
    )

    require(snap, "return floorf( value / texelSize + 0.5f ) * texelSize;", f"{label} texel snap rounding", failures)
    require_order(
        cascade,
        [
            "cascade->texelSize = ( cascade->radius * 2.0f ) / (float)resolution;",
            "halfExtent = ceilf( ( cascade->radius + cascade->texelSize * 0.5f ) /",
            "cascade->texelSize ) * cascade->texelSize;",
            "cascade->texelSize = ( halfExtent * 2.0f ) / (float)resolution;",
        ],
        f"{label} padded stable cascade extent",
        failures,
    )
    require_order(
        cascade,
        [
            "lightCenter[i] = DotProduct( center, lightAxis[i] );",
            "VectorCopy( lightAxis[i], cascade->axis[i] );",
            "lightCenter[0] = R_CSMSnapLightCoord( lightCenter[0], cascade->texelSize );",
            "lightCenter[1] = R_CSMSnapLightCoord( lightCenter[1], cascade->texelSize );",
            "lightCenter[2] = R_CSMSnapLightCoord( lightCenter[2], cascade->texelSize );",
            "VectorClear( cascade->origin );",
        ],
        f"{label} all light-space coordinates snapped before origin/bounds",
        failures,
    )
    require_order(
        cascade,
        [
            "cascade->bounds[0][0] = lightCenter[0] - halfExtent;",
            "cascade->bounds[1][0] = lightCenter[0] + halfExtent;",
            "cascade->bounds[0][1] = lightCenter[1] - halfExtent;",
            "cascade->bounds[1][1] = lightCenter[1] + halfExtent;",
            "cascade->bounds[0][2] = lightCenter[2] - halfExtent;",
            "cascade->bounds[1][2] = lightCenter[2] + halfExtent;",
        ],
        f"{label} bounds use snapped center",
        failures,
    )
    require(planner, "R_CSMBuildLightAxis( lightDirection, lightAxis );", f"{label} light axis planning", failures)
    require(planner, "tr.csmDebugPlan = tr.csm;", f"{label} debug plan publication", failures)


def main() -> int:
    failures: list[str] = []
    for label, relative_path in (
        ("OpenGL", "code/renderer/tr_main.c"),
        ("Vulkan", "code/renderervk/tr_main.c"),
    ):
        check_source(label, relative_path, failures)

    if failures:
        print("CSM planning source contract violations:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1

    print("Checked CSM planning source contract.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

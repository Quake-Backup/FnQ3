from __future__ import annotations

import argparse
import hashlib
import json
import math
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
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "meson" / "build"
DEFAULT_SWEEP_ROOT = ROOT / ".tmp" / "runtime-sweeps"
TEXTURE_CLASSIFICATION_MANIFEST_PATH = ROOT / "docs" / "fnquake3" / "GLX_TEXTURE_CLASSIFICATION_MANIFEST.json"
RENDERER_NAME_RE = re.compile(r"^[A-Za-z1-9]+$")
DEFAULT_PERFORMANCE_MAX_GROWTH_RATIO = 0.20
GLX_EXPECTED_PASS_SCHEDULE = (
    "frame-setup>sky-opaque-world>opaque-entities>dynamic-scene>transparent-layers>"
    "first-person-weapon>hud-2d>postprocess>output-export"
)
GLX_EXPECTED_PASS_SCHEDULE_COUNT = 9
GLX_EXPECTED_PASS_SCHEDULE_HASH = "0c6d7632"
GLX_PRODUCT_TIERS = {"GL12", "GL2X", "GL3X", "GL41", "GL46"}
GLX_BLOCKING_RELEASE_PLATFORMS = ("windows-x64", "linux-x86_64")
GLX_RELEASE_REQUIRED_GATES = ("rc-smoke", "rc-parity", "rc-proof")
GLX_RELEASE_PROOF_VERSION = 1
GLX_COLOR_CONTRACT_VERSION = "2026-05-10-p0"
GLX_VISUAL_DOSSIER_VERSION = "2026-05-10-visual-dossier-v1"
GLX_IMAGE_EVIDENCE_VERSION = "2026-05-12-p2-image-evidence-v1"
GLX_SHADER_REFERENCE_RAMP_WIDTH = 256
GLX_SHADER_REFERENCE_RAMP_HEIGHT = 16
GLX_SHADER_REFERENCE_RAMP_ROWS = (
    "linear-gray-ramp",
    "linear-step-wedge",
    "saturated-primaries",
    "hdr-highlight-ramp",
)
GLX_IMAGE_EVIDENCE_SIDECARS = (
    "histogram-json",
    "luma-falsecolor-png",
    "exposure-falsecolor-png",
)
GLX_SWITCH_LIFECYCLE_VERSION = 1
GLX_OWNERSHIP_PROOF_VERSION = 3
GLX_WORLD_PROOF_VERSION = 1
GLX_MATERIAL_PROOF_VERSION = 1
GLX_DYNAMIC_PROOF_VERSION = 1
GLX_POST_PROOF_VERSION = 2
GLX_POST_OUTPUT_FALLBACK_EXECUTOR_NOT_IMPLEMENTED = 0x00000400
GLX_POST_OUTPUT_FALLBACK_EXECUTOR_DISABLED = 0x00000800
GLX_POST_OUTPUT_FALLBACK_EXECUTOR_NOT_BOUND = 0x00001000
GLX_PRODUCT_TIER_ORDER = ("GL12", "GL2X", "GL3X", "GL41", "GL46")
GLX_WORLD_PROOF_TAGS = ("stock-map", "high-geometry", "lightmap", "fog-heavy", "visibility")
GLX_MATERIAL_PROOF_TAGS = (
    "shader-heavy",
    "material-stage",
    "animated-image",
    "screen-map",
    "video-map",
    "tcgen-lightmap",
    "tcgen-environment",
    "tcgen-fog",
    "tcgen-vector",
)
GLX_DYNAMIC_PROOF_TAGS = (
    "dynamic-entity",
    "weapon-model",
    "particle",
    "transient-poly",
    "mark-decal",
    "beam",
    "dynamic-light",
    "planar-shadow",
    "particle-heavy-demo",
)
GLX_DYNAMIC_CATEGORY_TAGS = {
    "entity": "dynamic-entity",
    "weapon": "weapon-model",
    "particle": "particle",
    "poly": "transient-poly",
    "mark": "mark-decal",
    "beam": "beam",
}
GLX_DYNAMIC_STREAM_FEATURE_TAGS = {
    "shadow": "planar-shadow",
    "beam": "beam",
    "dynamicLight": "dynamic-light",
}
GLX_DYNAMIC_SUPPORT_KEYS = {
    "dynamicEntities",
    "sprites",
    "beams",
    "dynamicLights",
    "stencilShadows",
}
GLX_POST_PROOF_TAGS = (
    "greyscale-proof",
    "render-scale-proof",
)
GLX_POST_FEATURE_TAGS = {
    "greyscale": "greyscale-proof",
    "renderScale": "render-scale-proof",
}
GLX_MATERIAL_STAGE_FLAGS = {
    "multitexture": 0x0001,
    "depthFragment": 0x0002,
    "blend": 0x0004,
    "alphaTest": 0x0008,
    "depthWrite": 0x0010,
    "lightmap": 0x0020,
    "animatedImage": 0x0040,
    "videoMap": 0x0080,
    "screenMap": 0x0100,
    "dynamicLightMap": 0x0200,
    "texMod": 0x0400,
    "environment": 0x0800,
    "st0": 0x1000,
    "st1": 0x2000,
    "shadowPass": 0x4000,
    "beamPass": 0x8000,
    "postprocessPass": 0x10000,
    "detail": 0x20000,
}
GLX_MATERIAL_TCGEN_IDS = {
    "bad": 0,
    "identity": 1,
    "lightmap": 2,
    "texture": 3,
    "environment": 4,
    "environmentFp": 5,
    "fog": 6,
    "vector": 7,
}
GLX_MATERIAL_STAGE_FLAG_TAGS = {
    "animatedImage": "animated-image",
    "screenMap": "screen-map",
    "videoMap": "video-map",
}
Q3_MAX_QPATH = 64
PROOF_PLATFORM_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")
PERFORMANCE_BASELINE_GROWTH_KEYS = (
    "batches",
    "draws",
    "drawIndexes",
    "streamMegabytes",
    "streamRejects",
    "streamDrawAttempts",
    "streamDrawIndexes",
    "streamDrawMultitexture",
    "streamDrawFog",
    "streamDrawDepthFragment",
    "streamDrawTexMods",
    "streamDrawEnvironment",
    "streamDrawDynamicLights",
    "streamDrawScreenMaps",
    "streamDrawVideoMaps",
    "streamDrawShadows",
    "streamDrawBeams",
    "streamDrawPostProcess",
    "streamDrawFallbacks",
    "streamDrawSkips",
    "streamCategoryEntityDraws",
    "streamCategoryParticleDraws",
    "streamCategoryPolyDraws",
    "streamCategoryMarkDraws",
    "streamCategoryWeaponDraws",
    "streamCategoryUiDraws",
    "streamCategoryBeamDraws",
    "streamCategorySpecialDraws",
    "staticDrawAttempts",
    "staticDrawIndexes",
    "staticDrawFallbacks",
    "staticMdiAttempts",
    "staticMdiErrors",
    "gl3xDraws",
    "gl3xSyncUploads",
    "gl3xStaticBuffers",
    "gl3xDynamicBuffers",
    "gl3xMaterials",
    "gl3xFboPost",
    "gl3xUnsupportedPersistentUploads",
    "gl41Draws",
    "gl41SyncUploads",
    "gl41StaticBuffers",
    "gl41DynamicBuffers",
    "gl41Materials",
    "gl41Post",
    "gl41UnsupportedPersistentUploads",
    "gl46Draws",
    "gl46PersistentUploads",
    "gl46SyncUploads",
    "gl46DsaProducts",
    "gl46MdiProducts",
    "gl46AggressiveStatic",
    "gl46Materials",
    "gl46Post",
    "gl46GpuCounters",
    "gl46StaticMdiCalls",
    "gl46StaticMdiAttempts",
    "gl46StaticMdiIndexes",
    "gpuFrameMs",
    "gpuPassBlits",
    "gpuPassBinds",
    "gpuPassClears",
    "gpuPassFullscreen",
    "gpuPassQueries",
    "gpuPassUnavailable",
    "gpuPassRingSkips",
    "gpuPassBackendMs",
    "gpuPassPostprocessMs",
    "gpuPassBloomMs",
    "gpuPassBloomExtractMs",
    "gpuPassBloomDownscaleMs",
    "gpuPassBloomBlurMs",
    "gpuPassBloomBlendMs",
    "gpuPassBloomFinalMs",
    "gpuPassBloomLensReflectionMs",
    "gpuPassGammaDirectMs",
    "gpuPassGammaBlitMs",
    "gpuPassFboBlitMs",
    "gpuPassCopyScreenMs",
    "gpuPassFlareMs",
    "materialBinds",
    "materialBindAttempts",
    "materialSwitches",
    "materialCacheMisses",
    "materialParameterBlocks",
    "materialParameterHash",
    "materialInvalidParameterBlocks",
    "postOutputPostNodes",
    "postOutputOutputs",
    "postOutputExecutableNodes",
    "postOutputExecutableOutputs",
    "postOutputPostHash",
    "postOutputOutputHash",
    "streamSameFrameWrapRejects",
    "streamBindingQueries",
    "streamBindingCacheHits",
    "streamBindingRestores",
    "streamBindingInvalidations",
    "streamBindingExternalUpdates",
    "streamDrawMegabytes",
    "streamDrawIndexMegabytes",
    "streamDrawTex1Megabytes",
    "staticDrawPacketMisses",
    "staticQueuePacketMisses",
    "staticPacketLookupMisses",
)
DEFAULT_PERFORMANCE_BUDGET = {
    "max": {
        "streamRejects": 0,
        "streamSameFrameWrapRejects": 0,
        "materialCompileFailures": 0,
        "materialLinkFailures": 0,
        "materialPrecacheFailures": 0,
        "materialBindFailures": 0,
        "materialInvalidParameterBlocks": 0,
        "streamDrawFallbacks": 0,
        "streamDrawDynamicLights": 0,
        "streamDrawScreenMaps": 0,
        "streamDrawVideoMaps": 0,
        "staticDrawFallbacks": 0,
        "staticMdiErrors": 0,
        "gl3xUnsupportedPersistentUploads": 0,
        "gl41UnsupportedPersistentUploads": 0,
        "staticPacketLookupOverflows": 0,
    },
    "tiers": {
        "GL12": {
            "max": {
                "draws": 20000,
                "drawIndexes": 4000000,
                "streamMegabytes": 8.0,
                "streamDrawMegabytes": 8.0,
                "materialBinds": 0,
                "materialSwitches": 0,
                "staticDrawPacketMisses": 20000,
                "staticQueuePacketMisses": 20000,
                "staticPacketLookupMisses": 20000,
                "gpuFrameMs": 66.7,
            },
        },
        "GL2X": {
            "max": {
                "draws": 12000,
                "drawIndexes": 4000000,
                "streamMegabytes": 128.0,
                "streamDrawMegabytes": 128.0,
                "materialBinds": 12000,
                "materialSwitches": 12000,
                "staticDrawPacketMisses": 12000,
                "staticQueuePacketMisses": 12000,
                "staticPacketLookupMisses": 12000,
                "gpuFrameMs": 50.0,
            },
        },
        "GL3X": {
            "required": (
                "gpuFrameMs",
                "postOutputPostNodes",
                "postOutputOutputs",
                "postOutputLegacyFallback",
                "postOutputPostHash",
                "postOutputOutputHash",
                "postOutputPlanHash",
                "postOutputFallbackMask",
                "materialPrograms",
                "materialBindAttempts",
                "materialCacheMisses",
                "materialCompileFailures",
                "materialLinkFailures",
                "materialPrecacheFailures",
                "materialBindFailures",
                "materialParameterBlocks",
                "materialParameterHash",
                "materialInvalidParameterBlocks",
                "streamBindingQueries",
                "streamBindingCacheHits",
                "streamBindingRestores",
            ),
            "min": {
                "postOutputPostNodes": 1,
                "postOutputOutputs": 1,
                "postOutputPostHash": 1,
                "postOutputOutputHash": 1,
                "postOutputPlanHash": 1,
                "materialPrograms": 1,
                "materialBindAttempts": 1,
                "materialParameterBlocks": 1,
                "materialParameterHash": 1,
                "streamBindingRestores": 1,
            },
            "max": {
                "draws": 10000,
                "drawIndexes": 3500000,
                "streamMegabytes": 96.0,
                "streamDrawMegabytes": 96.0,
                "materialBinds": 10000,
                "materialSwitches": 10000,
                "staticDrawPacketMisses": 10000,
                "staticQueuePacketMisses": 10000,
                "staticPacketLookupMisses": 10000,
                "postOutputLegacyFallback": 0,
                "postOutputFallbackMask": 0,
                "gpuFrameMs": 40.0,
            },
        },
        "GL41": {
            "required": (
                "gpuFrameMs",
                "postOutputPostNodes",
                "postOutputOutputs",
                "postOutputLegacyFallback",
                "postOutputPostHash",
                "postOutputOutputHash",
                "postOutputPlanHash",
                "postOutputFallbackMask",
                "materialPrograms",
                "materialBindAttempts",
                "materialCacheMisses",
                "materialCompileFailures",
                "materialLinkFailures",
                "materialPrecacheFailures",
                "materialBindFailures",
                "materialParameterBlocks",
                "materialParameterHash",
                "materialInvalidParameterBlocks",
                "streamBindingQueries",
                "streamBindingCacheHits",
                "streamBindingRestores",
            ),
            "min": {
                "postOutputPostNodes": 1,
                "postOutputOutputs": 1,
                "postOutputPostHash": 1,
                "postOutputOutputHash": 1,
                "postOutputPlanHash": 1,
                "materialPrograms": 1,
                "materialBindAttempts": 1,
                "materialParameterBlocks": 1,
                "materialParameterHash": 1,
                "streamBindingRestores": 1,
            },
            "max": {
                "draws": 9000,
                "drawIndexes": 3000000,
                "streamMegabytes": 96.0,
                "streamDrawMegabytes": 96.0,
                "materialBinds": 9000,
                "materialSwitches": 9000,
                "staticDrawPacketMisses": 9000,
                "staticQueuePacketMisses": 9000,
                "staticPacketLookupMisses": 9000,
                "postOutputLegacyFallback": 0,
                "postOutputFallbackMask": 0,
                "gpuFrameMs": 33.4,
            },
        },
        "GL46": {
            "required": (
                "gpuFrameMs",
                "postOutputPostNodes",
                "postOutputOutputs",
                "postOutputLegacyFallback",
                "postOutputPostHash",
                "postOutputOutputHash",
                "postOutputPlanHash",
                "postOutputFallbackMask",
                "materialPrograms",
                "materialBindAttempts",
                "materialCacheMisses",
                "materialCompileFailures",
                "materialLinkFailures",
                "materialPrecacheFailures",
                "materialBindFailures",
                "materialParameterBlocks",
                "materialParameterHash",
                "materialInvalidParameterBlocks",
                "streamBindingQueries",
                "streamBindingCacheHits",
                "streamBindingRestores",
            ),
            "min": {
                "postOutputPostNodes": 1,
                "postOutputOutputs": 1,
                "postOutputPostHash": 1,
                "postOutputOutputHash": 1,
                "postOutputPlanHash": 1,
                "materialPrograms": 1,
                "materialBindAttempts": 1,
                "materialParameterBlocks": 1,
                "materialParameterHash": 1,
                "streamBindingRestores": 1,
            },
            "max": {
                "draws": 8000,
                "drawIndexes": 2500000,
                "streamMegabytes": 96.0,
                "streamDrawMegabytes": 96.0,
                "materialBinds": 8000,
                "materialSwitches": 8000,
                "staticDrawPacketMisses": 8000,
                "staticQueuePacketMisses": 8000,
                "staticPacketLookupMisses": 8000,
                "postOutputLegacyFallback": 0,
                "postOutputFallbackMask": 0,
                "gpuFrameMs": 25.0,
            },
        },
    },
}
GLX_GATE_PERFORMANCE_BUDGET_OVERRIDES = {
    "rc-stress": {
        "max": {
            "streamDrawScreenMaps": 8000,
            "streamDrawVideoMaps": 8000,
        },
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
MATERIAL_COMPILER_PLANS_RE = re.compile(
    r"material compiler plans:\s*compiled\s+(?P<compiled>\d+),\s*"
    r"unsupported\s+(?P<unsupported>\d+),\s*"
    r"last unsupported\s+0x(?P<lastUnsupported>[0-9a-fA-F]+)\s*"
    r"\((?P<lastUnsupportedReason>[^)]*)\)",
    re.IGNORECASE,
)
MATERIAL_PARAMETER_DETAIL_RE = re.compile(
    r"(?:glx:\s*)?material parameter(?:s| blocks):?\s*"
    r"(?:blocks\s+)?(?P<blocks>\d+)\s+(?:built,\s*)?"
    r"invalid\s+(?P<invalid>\d+)"
    r"(?:,?\s+hash\s+0x(?P<hash>[0-9a-fA-F]+))?,?\s*"
    r"last\s+sort\s+(?P<sort>-?\d+)\s+passes\s+(?P<passes>\d+)\s+"
    r"features\s+0x(?P<features>[0-9a-fA-F]+)\s+"
    r"flags\s+0x(?P<flags>[0-9a-fA-F]+)\s+"
    r"state\s+0x(?P<state>[0-9a-fA-F]+)"
    r"(?:\s+object\s+rgb\s+(?P<rgbGen>-?\d+):(?P<rgbWave>-?\d+)\s+"
    r"alpha\s+(?P<alphaGen>-?\d+):(?P<alphaWave>-?\d+)\s+"
    r"tc\s+(?P<tcGen0>-?\d+)/(?P<tcGen1>-?\d+))?",
    re.IGNORECASE,
)
MATERIAL_PARAMETER_BLOCKS_RE = re.compile(
    r"(?:glx:\s*)?material parameter(?:s| blocks):?\s*"
    r"(?:blocks\s+)?(?P<blocks>\d+)\s+(?:built,\s*)?"
    r"invalid\s+(?P<invalid>\d+)"
    r"(?:,?\s+hash\s+0x(?P<hash>[0-9a-fA-F]+))?",
    re.IGNORECASE,
)
MATERIAL_LAST_KEY_RE = re.compile(
    r"material last key:\s*(?P<name>[^,]+),\s*"
    r"flags\s+0x(?P<flags>[0-9a-fA-F]+),\s*"
    r"state\s+0x(?P<state>[0-9a-fA-F]+),\s*"
    r"rgb\s+(?P<rgbGen>-?\d+):(?P<rgbWave>-?\d+)\s+"
    r"alpha\s+(?P<alphaGen>-?\d+):(?P<alphaWave>-?\d+)\s+"
    r"tc\s+(?P<tcGen0>-?\d+)/(?P<tcGen1>-?\d+)\s+"
    r"texmods\s+(?P<texMods0>-?\d+)/(?P<texMods1>-?\d+)\s+"
    r"combine\s+(?P<combine>-?\d+)\s+fog\s+(?P<fog>\w+)",
    re.IGNORECASE,
)
MATERIAL_LAST_LANGUAGE_RE = re.compile(
    r"material last language:\s*flags\s+0x(?P<flags>[0-9a-fA-F]+),\s*"
    r"state\s+0x(?P<state>[0-9a-fA-F]+),\s*"
    r"tmasks\s+0x(?P<texModMask0>[0-9a-fA-F]+)/0x(?P<texModMask1>[0-9a-fA-F]+),\s*"
    r"tseq\s+0x(?P<texModSequence0>[0-9a-fA-F]+)/0x(?P<texModSequence1>[0-9a-fA-F]+),\s*"
    r"twf\s+0x(?P<texModWaveFuncs0>[0-9a-fA-F]+)/0x(?P<texModWaveFuncs1>[0-9a-fA-F]+),\s*"
    r"fogadjust\s+(?P<fogAdjust>-?\d+)",
    re.IGNORECASE,
)
MATERIAL_FLAGS_COMMON_RE = re.compile(
    r"material flags mt/depthfrag/blend/atest/depthwrite/lightmap:\s*"
    r"(?P<multitexture>\d+)/(?P<depthFragment>\d+)/(?P<blend>\d+)/"
    r"(?P<alphaTest>\d+)/(?P<depthWrite>\d+)/(?P<lightmap>\d+)",
    re.IGNORECASE,
)
MATERIAL_FLAGS_SPECIAL_RE = re.compile(
    r"material flags anim/video/screen/dlight/texmod/env/st0/st1:\s*"
    r"(?P<animatedImage>\d+)/(?P<videoMap>\d+)/(?P<screenMap>\d+)/"
    r"(?P<dynamicLightMap>\d+)/(?P<texMod>\d+)/(?P<environment>\d+)/"
    r"(?P<st0>\d+)/(?P<st1>\d+)",
    re.IGNORECASE,
)
OWNERSHIP_RE = re.compile(
    r"ownership legacy delegation\s+(?P<calls>\d+)\s+calls/(?P<items>\d+)\s+items,\s*"
    r"generic\s+(?P<generic>\d+),\s*vbo-device\s+(?P<vboDevice>\d+),\s*"
    r"vbo-soft\s+(?P<vboSoft>\d+),\s*arrays\s+(?P<arrays>\d+)",
    re.IGNORECASE,
)
OWNERSHIP_INFO_RE = re.compile(
    r"ownership legacy delegation:\s*(?P<calls>\d+)\s+calls,\s*(?P<items>\d+)\s+items",
    re.IGNORECASE,
)
GLX_TIER_INFO_RE = re.compile(
    r"(?:product|capability)\s+tier(?::|\s)\s*(?P<tier>[^\s,]+)",
    re.IGNORECASE,
)
GLX_GL12_EXECUTOR_RE = re.compile(
    r"GL12 fixed-function executor:\s*active\s+(?P<active>\w+),\s*"
    r"client-memory draws\s+(?P<clientMemoryDraws>\w+),\s*"
    r"stream uploads\s+(?P<streamUploads>\w+),\s*"
    r"material compiler\s+(?P<materialCompiler>\w+),\s*"
    r"modern post chain\s+(?P<modernPostChain>\w+)",
    re.IGNORECASE,
)
GLX_GL12_SUPPORT_RE = re.compile(
    r"GL12 fixed-function support:\s*lightmaps\s+(?P<lightmaps>\w+),\s*"
    r"multitexture\s+(?P<multitexture>\w+),\s*fog\s+(?P<fog>\w+),\s*"
    r"sprites\s+(?P<sprites>\w+),\s*beams\s+(?P<beams>\w+),\s*"
    r"dynamic lights\s+(?P<dynamicLights>\w+),\s*"
    r"stencil shadows if available\s+(?P<stencilShadows>\w+),\s*"
    r"screenshots\s+(?P<screenshots>\w+),\s*demos\s+(?P<demos>\w+)",
    re.IGNORECASE,
)
GLX_GL2X_EXECUTOR_RE = re.compile(
    r"GL2X programmable executor:\s*active\s+(?P<active>\w+),\s*"
    r"client-memory fallback\s+(?P<clientMemoryFallback>\w+),\s*"
    r"stream uploads\s+(?P<streamUploads>\w+),\s*"
    r"material compiler\s+(?P<materialCompiler>\w+),\s*"
    r"postprocess-lite\s+(?P<postprocessLite>\w+),\s*"
    r"modern post chain\s+(?P<modernPostChain>\w+),\s*"
    r"scene-linear output\s+(?P<sceneLinearOutput>\w+)",
    re.IGNORECASE,
)
GLX_GL2X_SUPPORT_RE = re.compile(
    r"GL2X programmable support:\s*common materials\s+(?P<commonMaterials>\w+),\s*"
    r"dynamic entities\s+(?P<dynamicEntities>\w+),\s*"
    r"lightmaps\s+(?P<lightmaps>\w+),\s*multitexture\s+(?P<multitexture>\w+),\s*"
    r"fog\s+(?P<fog>\w+),\s*sprites\s+(?P<sprites>\w+),\s*"
    r"beams\s+(?P<beams>\w+),\s*screenshots\s+(?P<screenshots>\w+),\s*"
    r"demos\s+(?P<demos>\w+)",
    re.IGNORECASE,
)
GLX_GL3X_EXECUTOR_RE = re.compile(
    r"GL3X performance executor:\s*active\s+(?P<active>\w+),\s*"
    r"FBO postprocess\s+(?P<fboPostProcess>\w+),\s*"
    r"UBO frame/object constants\s+(?P<uboFrameObjectConstants>\w+),\s*"
    r"timer queries\s+(?P<timerQueries>\w+),\s*"
    r"sync-aware uploads\s+(?P<syncAwareUploads>\w+),\s*"
    r"static buffer ownership\s+(?P<staticBufferOwnership>\w+),\s*"
    r"dynamic buffer ownership\s+(?P<dynamicBufferOwnership>\w+),\s*"
    r"persistent uploads\s+(?P<persistentUploads>\w+),\s*"
    r"indirect submission\s+(?P<indirectSubmission>\w+),\s*"
    r"direct state access\s+(?P<directStateAccess>\w+)",
    re.IGNORECASE,
)
GLX_GL3X_SUPPORT_RE = re.compile(
    r"GL3X performance support:\s*material compiler\s+(?P<materialCompiler>\w+),\s*"
    r"common materials\s+(?P<commonMaterials>\w+),\s*"
    r"dynamic entities\s+(?P<dynamicEntities>\w+),\s*"
    r"modern post chain\s+(?P<modernPostChain>\w+),\s*"
    r"scene-linear output\s+(?P<sceneLinearOutput>\w+),\s*"
    r"screenshots\s+(?P<screenshots>\w+),\s*demos\s+(?P<demos>\w+)",
    re.IGNORECASE,
)
GLX_GL41_EXECUTOR_RE = re.compile(
    r"GL41 mac-modern executor:\s*active\s+(?P<active>\w+),\s*"
    r"FBO postprocess\s+(?P<fboPostProcess>\w+),\s*"
    r"UBO frame/object constants\s+(?P<uboFrameObjectConstants>\w+),\s*"
    r"timer queries\s+(?P<timerQueries>\w+),\s*"
    r"sync-aware uploads\s+(?P<syncAwareUploads>\w+),\s*"
    r"static buffer ownership\s+(?P<staticBufferOwnership>\w+),\s*"
    r"dynamic buffer ownership\s+(?P<dynamicBufferOwnership>\w+),\s*"
    r"macOS 4\.1 ceiling\s+(?P<macOS41Ceiling>\w+)",
    re.IGNORECASE,
)
GLX_GL41_SUPPORT_RE = re.compile(
    r"GL41 mac-modern support:\s*material compiler\s+(?P<materialCompiler>\w+),\s*"
    r"common materials\s+(?P<commonMaterials>\w+),\s*"
    r"dynamic entities\s+(?P<dynamicEntities>\w+),\s*"
    r"modern post chain\s+(?P<modernPostChain>\w+),\s*"
    r"scene-linear output\s+(?P<sceneLinearOutput>\w+),\s*"
    r"high-quality SDR\s+(?P<highQualitySdr>\w+),\s*"
    r"optional hardware HDR\s+(?P<optionalHardwareHdr>\w+),\s*"
    r"screenshots\s+(?P<screenshots>\w+),\s*demos\s+(?P<demos>\w+)",
    re.IGNORECASE,
)
GLX_GL41_LIMITS_RE = re.compile(
    r"GL41 mac-modern GL4\+ requirements:\s*debug output\s+(?P<debugOutputRequired>\w+),\s*"
    r"buffer storage\s+(?P<bufferStorageRequired>\w+),\s*"
    r"direct state access\s+(?P<directStateAccessRequired>\w+),\s*"
    r"multi-draw indirect\s+(?P<multiDrawIndirectRequired>\w+),\s*"
    r"persistent uploads\s+(?P<persistentUploadsRequired>\w+)",
    re.IGNORECASE,
)
GLX_GL46_EXECUTOR_RE = re.compile(
    r"GL46 high-end executor:\s*active\s+(?P<active>\w+),\s*"
    r"persistent uploads\s+(?P<persistentUploads>\w+),\s*"
    r"buffer storage uploads\s+(?P<bufferStorageUploads>\w+),\s*"
    r"sync-heavy streaming\s+(?P<syncHeavyStreaming>\w+),\s*"
    r"direct state access\s+(?P<directStateAccess>\w+),\s*"
    r"multi-draw indirect\s+(?P<multiDrawIndirect>\w+),\s*"
    r"aggressive static-world submission\s+(?P<aggressiveStaticWorldSubmission>\w+),\s*"
    r"detailed GPU counters\s+(?P<detailedGpuCounters>\w+)",
    re.IGNORECASE,
)
GLX_GL46_SUPPORT_RE = re.compile(
    r"GL46 high-end support:\s*material compiler\s+(?P<materialCompiler>\w+),\s*"
    r"common materials\s+(?P<commonMaterials>\w+),\s*"
    r"dynamic entities\s+(?P<dynamicEntities>\w+),\s*"
    r"modern post chain\s+(?P<modernPostChain>\w+),\s*"
    r"scene-linear output\s+(?P<sceneLinearOutput>\w+),\s*"
    r"hardware HDR output\s+(?P<hardwareHdrOutput>\w+),\s*"
    r"screenshots\s+(?P<screenshots>\w+),\s*demos\s+(?P<demos>\w+)",
    re.IGNORECASE,
)
GLX_GL46_REQUIREMENTS_RE = re.compile(
    r"GL46 high-end requirements:\s*debug output\s+(?P<debugOutputRequired>\w+),\s*"
    r"buffer storage\s+(?P<bufferStorageRequired>\w+),\s*"
    r"direct state access\s+(?P<directStateAccessRequired>\w+),\s*"
    r"multi-draw indirect\s+(?P<multiDrawIndirectRequired>\w+)",
    re.IGNORECASE,
)
GLX_PASS_SCHEDULE_RE = re.compile(
    r"(?:glx:\s*)?(?:GLx\s+)?pass schedule:?\s*(?P<valid>valid|invalid)\s+"
    r"(?P<count>\d+)/(?P<hash>[0-9a-fA-F]+)\s+(?P<order>[A-Za-z0-9_>\-]+)",
    re.IGNORECASE,
)
GLX_RENDER_IR_PRODUCTS_RE = re.compile(
    r"(?:glx:\s*)?render IR products:?\s*"
    r"passes\s+(?P<passes>\d+),?\s+world packets\s+(?P<worldPackets>\d+),?\s+"
    r"dynamic draws\s+(?P<dynamicDraws>\d+),?\s+materials\s+(?P<materials>\d+),?\s+"
    r"uploads\s+(?P<uploads>\d+),?\s+post nodes\s+(?P<postNodes>\d+),?\s+"
    r"outputs\s+(?P<outputs>\d+),?\s+rejects\s+(?P<rejects>\d+)",
    re.IGNORECASE,
)
GLX_POST_OUTPUT_OWNERSHIP_RE = re.compile(
    r"(?:glx:\s*)?post/output ownership:?\s*"
    r"mode\s+(?P<mode>[A-Za-z0-9_-]+),?\s+post nodes\s+(?P<postNodes>\d+),?\s+"
    r"outputs\s+(?P<outputs>\d+),?\s+legacy fallback\s+(?P<legacyFallback>\w+)"
    r"(?:,?\s+executable nodes\s+(?P<executableNodes>\d+),?\s+"
    r"executable outputs\s+(?P<executableOutputs>\d+))?"
    r"(?:,?\s+post hash\s+0x(?P<postHash>[0-9a-fA-F]+),?\s+"
    r"output hash\s+0x(?P<outputHash>[0-9a-fA-F]+))?"
    r"(?:,?\s+plan hash\s+0x(?P<planHash>[0-9a-fA-F]+),?\s+"
    r"fallback\s+0x(?P<fallbackMask>[0-9a-fA-F]+))?",
    re.IGNORECASE,
)
GLX_POST_SHADER_PLAN_RE = re.compile(
    r"(?:glx:\s*)?post shader plan:?\s*"
    r"valid\s+(?P<valid>\w+),?\s+features\s+0x(?P<features>[0-9a-fA-F]+),?\s+"
    r"hash\s+0x(?P<hash>[0-9a-fA-F]+),?\s+textures\s+(?P<textures>\d+),?\s+"
    r"uniforms\s+(?P<uniforms>\d+)"
    r"(?:,?\s+frames\s+(?P<frames>\d+),?\s+invalid\s+(?P<invalidFrames>\d+))?",
    re.IGNORECASE,
)
GLX_POST_SHADER_CACHE_RE = re.compile(
    r"(?:glx:\s*)?post shader cache:?\s*"
    r"ready\s+(?P<ready>\w+),?\s+programs\s+(?P<programs>\d+)/(?P<programLimit>\d+),?\s+"
    r"plans\s+(?P<validPlans>\d+)\s+valid/(?P<invalidPlans>\d+)\s+invalid,?\s+"
    r"cache\s+(?P<cacheHits>\d+)\s+hits/(?P<cacheMisses>\d+)\s+misses,?\s+"
    r"compile\s+(?P<compileAttempts>\d+)\s+attempts/(?P<compileFailures>\d+)\s+failures,?\s+"
    r"link failures\s+(?P<linkFailures>\d+),?\s+source failures\s+(?P<sourceFailures>\d+),?\s+"
    r"source hash\s+0x(?P<sourceHash>[0-9a-fA-F]+),?\s+program\s+(?P<program>\d+)",
    re.IGNORECASE,
)
GLX_POST_SHADER_DIRECT_FINAL_RE = re.compile(
    r"(?:glx:\s*)?post shader direct-final:?\s*"
    r"execute\s+(?P<execute>\w+),?\s+eligible\s+(?P<eligible>\w+),?\s+"
    r"bound\s+(?P<bound>\w+),?\s+reject\s+0x(?P<reject>[0-9a-fA-F]+),?\s+"
    r"candidates\s+(?P<candidates>\d+),?\s+eligible frames\s+(?P<eligibleFrames>\d+),?\s+"
    r"attempts\s+(?P<attempts>\d+),?\s+binds\s+(?P<binds>\d+),?\s+"
    r"fallbacks\s+(?P<fallbacks>\d+),?\s+rejects\s+(?P<rejects>\d+)"
    r"(?:,?\s+program misses\s+(?P<programMisses>\d+),?\s+"
    r"uniform failures\s+(?P<uniformFailures>\d+))?",
    re.IGNORECASE,
)
POSTPROCESS_FBO_RE = re.compile(
    r"FBO:\s*requested\s+(?P<requested>\w+),\s*ready\s+(?P<ready>\w+),\s*"
    r"programs\s+(?P<programs>\w+),\s*framebuffer funcs\s+(?P<framebuffer>\w+)",
    re.IGNORECASE,
)
POSTPROCESS_TARGET_FORMAT_RE = re.compile(
    r"(?:glx:\s*)?target:\s*render\s+(?P<renderWidth>\d+)x(?P<renderHeight>\d+),\s*"
    r"capture\s+(?P<captureWidth>\d+)x(?P<captureHeight>\d+),\s*"
    r"window\s+(?P<windowWidth>\d+)x(?P<windowHeight>\d+),\s*"
    r"format\s+(?P<internalFormat>0x[0-9a-fA-F]+)\s*"
    r"\((?P<textureFormat>0x[0-9a-fA-F]+):(?P<textureType>0x[0-9a-fA-F]+)\)",
    re.IGNORECASE,
)
POSTPROCESS_CONTROLS_RE = re.compile(
    r"controls:\s*scene-linear HDR\s+(?P<sceneLinearHdr>\w+),\s*"
    r"precision\s+(?P<precision>\d+),\s*renderScale\s+(?P<renderScale>\d+),\s*"
    r"bloom\s+(?P<bloom>\d+),\s*MSAA\s+(?P<msaa>\w+),\s*"
    r"supersample\s+(?P<supersample>\w+),\s*adjusted window\s+(?P<windowAdjusted>\w+),\s*"
    r"greyscale\s+(?P<greyscale>-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
POSTPROCESS_FRAMES_RE = re.compile(
    r"frames:\s*(?P<frames>\d+)\s+post,\s*(?P<bloomFinal>\d+)\s+bloom-final,\s*"
    r"(?P<gammaDirect>\d+)\s+gamma-direct,\s*(?P<gammaBlit>\d+)\s+gamma-blit,\s*"
    r"(?P<minimizedOutput>\d+)\s+minimized output,\s*(?P<screenshots>\d+)\s+screenshots",
    re.IGNORECASE,
)
POSTPROCESS_FRAME_FEATURES_RE = re.compile(
    r"frame features:\s*(?P<bloomAvailable>\d+)\s+bloom-available,\s*"
    r"(?P<sceneLinear>\d+)\s+scene-linear,\s*(?P<toneMapped>\d+)\s+tone-mapped,\s*"
    r"(?P<graded>\d+)\s+graded,\s*(?P<renderScale>\d+)\s+render-scale,\s*"
    r"(?P<greyscale>\d+)\s+greyscale,\s*(?P<windowAdjusted>\d+)\s+window-adjusted,\s*"
    r"(?P<minimized>\d+)\s+minimized",
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
POSTPROCESS_BLOOM_STORAGE_RE = re.compile(
    r"(?:glx:\s*)?bloom storage:?\s*policy\s+(?P<policy>[A-Za-z0-9_-]+),?\s*"
    r"format\s+(?P<internalFormat>0x[0-9a-fA-F]+)\s*"
    r"\((?P<textureFormat>0x[0-9a-fA-F]+):(?P<textureType>0x[0-9a-fA-F]+)\)",
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
GLX_PASS_COUNTERS_RE = re.compile(
    r"(?:glx:\s*)?(?:post\s+)?pass counters:?\s*"
    r"blits\s+(?P<blits>\d+),\s*binds\s+(?P<binds>\d+),\s*"
    r"clears\s+(?P<clears>\d+),\s*fullscreen(?:\s+passes)?\s+(?P<fullscreen>\d+)"
    r"(?:,\s*pass queries\s+(?P<queries>\d+),\s*unavailable\s+(?P<unavailable>\d+),\s*"
    r"ring skips\s+(?P<ringSkips>\d+))?",
    re.IGNORECASE,
)
GLX_PASS_TIMER_RE = re.compile(
    r"pass timer queries:\s*active\s+(?P<active>\w+),\s*queries\s+(?P<queries>\d+),\s*"
    r"unavailable frames\s+(?P<unavailable>\d+),\s*ring-full skips\s+(?P<ringSkips>\d+)",
    re.IGNORECASE,
)
GLX_PASS_GPU_RE = re.compile(
    r"(?:glx:\s*)?pass GPU(?: timings)?(?::)?\s*(?P<body>.*)",
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
STREAM_BINDING_CACHE_RE = re.compile(
    r"(?:glx:\s*)?(?:dynamic\s+)?stream binding cache:?\s*"
    r"queries\s+(?P<queries>\d+),?\s+hits\s+(?P<hits>\d+),?\s+"
    r"restores\s+(?P<restores>\d+),?\s+invalidations\s+(?P<invalidations>\d+)"
    r"(?:,?\s+external\s+(?P<external>\d+))?",
    re.IGNORECASE,
)
STREAM_DRAWS_RE = re.compile(
    r"dynamic stream draws:\s*(?P<draws>\d+)/(?P<attempts>\d+)\s+attempts,.*?"
    r"mt\s+(?P<multitexture>\d+),\s*fog\s+(?P<fog>\d+),\s*"
    r"depthfrag\s+(?P<depthFragment>\d+),\s*texmod\s+(?P<texMods>\d+),\s*"
    r"env\s+(?P<environment>\d+),\s*dlight\s+(?P<dynamicLights>\d+),\s*"
    r"screen\s+(?P<screenMaps>\d+),\s*video\s+(?P<videoMaps>\d+),\s*"
    r"(?:shadow\s+(?P<shadows>\d+),\s*)?(?:beam\s+(?P<beams>\d+),\s*)?"
    r"(?:post\s+(?P<postprocess>\d+),\s*)?"
    r"fallbacks\s+(?P<fallbacks>\d+)",
    re.IGNORECASE,
)
STREAM_CATEGORIES_RE = re.compile(
    r"dynamic stream categories:\s*"
    r"entity\s+(?P<entityDraws>\d+)/(?P<entityAttempts>\d+),\s*"
    r"particle\s+(?P<particleDraws>\d+)/(?P<particleAttempts>\d+),\s*"
    r"poly\s+(?P<polyDraws>\d+)/(?P<polyAttempts>\d+),\s*"
    r"mark\s+(?P<markDraws>\d+)/(?P<markAttempts>\d+),\s*"
    r"weapon\s+(?P<weaponDraws>\d+)/(?P<weaponAttempts>\d+),\s*"
    r"ui\s+(?P<uiDraws>\d+)/(?P<uiAttempts>\d+),\s*"
    r"beam\s+(?P<beamDraws>\d+)/(?P<beamAttempts>\d+),\s*"
    r"special\s+(?P<specialDraws>\d+)/(?P<specialAttempts>\d+)",
    re.IGNORECASE,
)
STREAM_CATEGORY_FALLBACKS_RE = re.compile(
    r"dynamic stream category fallbacks:\s*"
    r"entity\s+(?P<entity>\d+),\s*particle\s+(?P<particle>\d+),\s*"
    r"poly\s+(?P<poly>\d+),\s*mark\s+(?P<mark>\d+),\s*"
    r"weapon\s+(?P<weapon>\d+),\s*ui\s+(?P<ui>\d+),\s*"
    r"beam\s+(?P<beam>\d+),\s*special\s+(?P<special>\d+)",
    re.IGNORECASE,
)
STREAM_DRAW_SKIPS_RE = re.compile(
    r"dynamic stream draw skips:\s*(?P<total>\d+)\s*"
    r"\(bind\s+(?P<bind>\d+),\s*input\s+(?P<input>\d+),\s*"
    r"mt\s+(?P<multitexture>\d+),\s*depthfrag\s+(?P<depthFragment>\d+),\s*"
    r"texcoord\s+(?P<texcoord>\d+),\s*empty\s+(?P<empty>\d+),\s*"
    r"key\s+(?P<key>\d+),\s*fog\s+(?P<fog>\d+),\s*"
    r"program\s+(?P<program>\d+)\)",
    re.IGNORECASE,
)
STREAM_MATERIAL_COMPILER_RE = re.compile(
    r"dynamic stream material compiler:\s*rejected\s+(?P<rejected>\d+),\s*"
    r"last unsupported\s+0x(?P<lastUnsupported>[0-9a-fA-F]+)\s*"
    r"\((?P<lastUnsupportedReason>[^)]*)\)",
    re.IGNORECASE,
)
STREAM_MATERIAL_GATE_RE = re.compile(
    r"dynamic stream (?P<name>multitexture|depth-fragment|texmod|environment|dynamic-light|screen-map|video-map) "
    r"gate:\s*(?P<enabled>\w+),\s*accepted\s+(?P<accepted>\d+),\s*rejected\s+(?P<rejected>\d+)",
    re.IGNORECASE,
)
STREAM_MATERIAL_GATE_KEYS = {
    "multitexture": "multitexture",
    "depth-fragment": "depthFragment",
    "texmod": "texMod",
    "environment": "environment",
    "dynamic-light": "dynamicLight",
    "screen-map": "screenMap",
    "video-map": "videoMap",
}
STREAM_CATEGORY_KEYS = (
    "entity",
    "particle",
    "poly",
    "mark",
    "weapon",
    "ui",
    "beam",
    "special",
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
GLX_COLOR_PIPELINE_RE = re.compile(
    r"(?:glx:\s*)?color pipeline:?\s*"
    r"(?:space\s+)?(?P<space>[A-Za-z0-9_-]+),?\s+"
    r"(?:precision\s+(?P<precision>-?\d+)\s+)?"
    r"transfer\s+(?P<transfer>[A-Za-z0-9_-]+),?\s+"
    r"tone-map\s+(?P<toneMap>[A-Za-z0-9_-]+),?\s+"
    r"exposure\s+(?P<exposure>-?\d+(?:\.\d+)?),?\s+"
    r"(?:bloom-threshold\s+(?P<bloomThreshold>-?\d+(?:\.\d+)?)/(?P<bloomThresholdMode>\d+),?\s+"
    r"knee\s+(?P<bloomSoftKnee>-?\d+(?:\.\d+)?),?\s+)?"
    r"grade\s+(?P<grade>[A-Za-z0-9_-]+),?\s+"
    r"(?:paper-white\s+(?P<paperWhite>-?\d+(?:\.\d+)?)\s*(?:nits)?,?\s+)?"
    r"max\s+(?P<maxOutput>-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
GLX_AUTO_EXPOSURE_RE = re.compile(
    r"(?:glx:\s*)?(?:auto exposure|exposure reduction):?\s*"
    r"mode\s+(?P<mode>-?\d+),?\s+"
    r"algorithm\s+(?P<algorithm>[A-Za-z0-9_-]+),?\s+"
    r"enabled\s+(?P<enabled>\w+),?\s+"
    r"fallback\s+(?P<fallback>\w+),?\s+"
    r"samples\s+(?P<sampleCount>\d+)/(?P<sampleWidth>\d+)x(?P<sampleHeight>\d+),?\s+"
    r"percentile\s+(?P<percentile>-?\d+(?:\.\d+)?),?\s+"
    r"target-luma\s+(?P<targetLuma>-?\d+(?:\.\d+)?),?\s+"
    r"measured-log2\s+(?P<measuredLog2>-?\d+(?:\.\d+)?),?\s+"
    r"measured-luma\s+(?P<measuredLuma>-?\d+(?:\.\d+)?),?\s+"
    r"manual\s+(?P<manual>-?\d+(?:\.\d+)?),?\s+"
    r"scale\s+(?P<scale>-?\d+(?:\.\d+)?),?\s+"
    r"target\s+(?P<target>-?\d+(?:\.\d+)?),?\s+"
    r"frames\s+(?P<frames>\d+)"
    r"(?:\s+histogram/(?P<histogramFramesSlash>\d+)\s+simple/(?P<simpleFramesSlash>\d+)\s+"
    r"failures/(?P<sampleFailuresSlash>\d+)|"
    r"\s+histogram\s+(?P<histogramFrames>\d+)\s+simple\s+(?P<simpleFrames>\d+)\s+"
    r"sample-failures\s+(?P<sampleFailures>\d+))",
    re.IGNORECASE,
)
GLX_TONE_MAP_ALIASES = {
    "reinhard": "reinhard-simple",
    "aces": "aces-fitted",
}


def normalize_tone_map_name(name: object) -> str:
    value = str(name).strip().lower()
    return GLX_TONE_MAP_ALIASES.get(value, value)


GLX_COLOR_GRADE_RE = re.compile(
    r"(?:glx:\s*)?color grade(?: stage)?:?\s*"
    r"mode\s+(?P<mode>[A-Za-z0-9_-]+),?\s+"
    r"lift\s+(?P<liftR>-?\d+(?:\.\d+)?)/(?P<liftG>-?\d+(?:\.\d+)?)/(?P<liftB>-?\d+(?:\.\d+)?),?\s+"
    r"gamma\s+(?P<gammaR>-?\d+(?:\.\d+)?)/(?P<gammaG>-?\d+(?:\.\d+)?)/(?P<gammaB>-?\d+(?:\.\d+)?),?\s+"
    r"gain\s+(?P<gainR>-?\d+(?:\.\d+)?)/(?P<gainG>-?\d+(?:\.\d+)?)/(?P<gainB>-?\d+(?:\.\d+)?),?\s+"
    r"white-point\s+(?P<whiteSource>-?\d+(?:\.\d+)?)->(?P<whiteTarget>-?\d+(?:\.\d+)?)\s*(?:K)?,?\s+"
    r"lut-size\s+(?P<lutSize>-?\d+(?:\.\d+)?),?\s+"
    r"lut-scale\s+(?P<lutScale>-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
GLX_OUTPUT_COLORIMETRY_RE = re.compile(
    r"(?:glx:\s*)?output colorimetry:?\s*"
    r"primaries\s+(?P<primaries>[A-Za-z0-9_-]+),?\s+"
    r"gamut-map\s+(?P<gamutMap>[A-Za-z0-9_-]+),?\s+"
    r"precision(?:-| )request(?:ed)?\s+(?P<precisionRequest>-?\d+),?\s+"
    r"(?:precision-)?resolved\s+(?P<precisionResolved>-?\d+)",
    re.IGNORECASE,
)
GLX_COLOR_AUDIT_RE = re.compile(
    r"(?:glx:\s*)?color audit:?\s*"
    r"srgb-decode\s+(?P<srgbDecode>\w+)\s+"
    r"requested\s+(?P<srgbRequested>\w+)\s+"
    r"available\s+(?P<srgbAvailable>\w+),?\s+"
    r"framebuffer-srgb\s+(?P<framebufferSrgb>\w+)\s+"
    r"requested\s+(?P<framebufferRequested>\w+)\s+"
    r"available\s+(?P<framebufferAvailable>\w+),?\s+"
    r"capture\s+(?P<capture>[A-Za-z0-9_-]+)"
    r"(?:,?\s+capture-request\s+(?P<captureRequest>[A-Za-z0-9_-]+),?"
    r"\s+capture-hdr-aware\s+(?P<captureHdrAware>\w+),?"
    r"\s+capture-supported\s+(?P<captureSupported>\w+))?"
    r"(?:,?\s+target-float\s+(?P<targetFloat>\w+),?"
    r"\s+final-encode\s+(?P<finalEncode>[A-Za-z0-9_-]+),?"
    r"\s+contract\s+(?P<contract>\w+))?",
    re.IGNORECASE,
)
GLX_TEXTURE_AUDIT_RE = re.compile(
    r"(?:glx:\s*)?texture audit:?\s*"
    r"srgb\s+(?P<srgb>\d+)\s+decode\s+(?P<srgbDecode>\d+),?\s+"
    r"linear\s+(?P<linear>\d+)\s+decode\s+(?P<linearDecode>\d+),?\s+"
    r"data\s+(?P<data>\d+)\s+decode\s+(?P<dataDecode>\d+),?\s+"
    r"unknown\s+(?P<unknown>\d+)\s+decode\s+(?P<unknownDecode>\d+),?\s+"
    r"missing-srgb-decode\s+(?P<missingSrgbDecode>\d+),?\s+"
    r"unexpected-decode\s+(?P<unexpectedDecode>\d+)",
    re.IGNORECASE,
)
GLX_COLOR_FRAME_JSON_RE = re.compile(
    r"glx:\s*color-frame-json\s+(?P<payload>\{.*\})",
    re.IGNORECASE,
)
GLX_COLOR_FRAME_CSV_RE = re.compile(
    r"glx:\s*color-frame-csv\s+"
    r"(?P<frame>\d+),"
    r"(?P<backend>[^,]+),"
    r"(?P<space>[^,]+),"
    r"(?P<transfer>[^,]+),"
    r"(?P<exposure>-?\d+(?:\.\d+)?),"
    r"(?P<paperWhiteNits>-?\d+(?:\.\d+)?),"
    r"(?P<maxOutputNits>-?\d+(?:\.\d+)?),"
    r"(?P<srgbDecode>[^,]+),"
    r"(?P<framebufferSrgb>[^,]+),"
    r"(?P<internalFormat>0x[0-9a-fA-F]+),"
    r"(?P<textureFormat>0x[0-9a-fA-F]+),"
    r"(?P<textureType>0x[0-9a-fA-F]+),"
    r"(?P<sceneTargetFloat>[^,]+),"
    r"(?P<shaderSrgbEncode>[^,]+),"
    r"(?P<contractValid>[^,\s]+)",
    re.IGNORECASE,
)
GLX_OUTPUT_BACKEND_RE = re.compile(
    r"(?:glx:\s*)?output backend:?\s*"
    r"request\s+(?P<request>[A-Za-z0-9_-]+),?\s+"
    r"selected\s+(?P<selected>[A-Za-z0-9_-]+),?\s+"
    r"native\s+(?P<native>[A-Za-z0-9_-]+),?\s+"
    r"hardware\s+(?P<hardware>\w+),?\s+"
    r"experimental\s+(?P<experimental>\w+),?\s+"
    r"display-hdr\s+(?P<displayHdr>\w+),?\s+"
    r"headroom\s+(?P<headroom>-?\d+(?:\.\d+)?),?\s+"
    r"sdr-white\s+(?P<sdrWhite>-?\d+(?:\.\d+)?)(?:\s+nits)?,?\s+"
    r"display-max\s+(?P<displayMax>-?\d+(?:\.\d+)?)(?:\s+nits)?,?\s+"
    r"icc\s+(?P<icc>\w+)/(?P<iccBytes>\d+)",
    re.IGNORECASE,
)
GLX_DISPLAY_STATE_RE = re.compile(
    r"(?:glx:\s*)?display state:?\s*"
    r"queries\s+(?P<queries>\d+),?\s+"
    r"changes\s+(?P<changes>\d+),?\s+"
    r"capability\s+(?P<capability>\d+),?\s+"
    r"backend\s+(?P<backend>\d+),?\s+"
    r"hdr\s+(?P<hdr>\d+),?\s+"
    r"headroom\s+(?P<headroom>\d+),?\s+"
    r"luminance\s+(?P<luminance>\d+),?\s+"
    r"icc\s+(?P<icc>\d+),?\s+"
    r"last-frame\s+(?P<lastFrame>\d+),?\s+"
    r"flags\s+(?P<flags>0x[0-9a-fA-F]+),?\s+"
    r"hash\s+(?P<hash>0x[0-9a-fA-F]+),?\s+"
    r"previous\s+(?P<previous>0x[0-9a-fA-F]+)",
    re.IGNORECASE,
)
GLX_STREAM_DRAW_SUMMARY_RE = re.compile(
    r"glx:\s*stream draws\s+(?P<draws>\d+)/(?P<attempts>\d+)\s+attempts,\s*"
    r"(?P<indexes>\d+)\s+idx,\s*(?P<megabytes>\d+(?:\.\d+)?)MB/index\s+"
    r"(?P<indexMegabytes>\d+(?:\.\d+)?)MB/tex1\s+(?P<tex1Megabytes>\d+(?:\.\d+)?)MB,\s*"
    r"mt\s+(?P<multitexture>\d+),\s*fog\s+(?P<fog>\d+),\s*"
    r"depthfrag\s+(?P<depthFragment>\d+),\s*texmod\s+(?P<texMods>\d+),\s*"
    r"env\s+(?P<environment>\d+),\s*dlight\s+(?P<dynamicLights>\d+),\s*"
    r"screen\s+(?P<screenMaps>\d+),\s*video\s+(?P<videoMaps>\d+),\s*"
    r"(?:shadow\s+(?P<shadows>\d+),\s*)?(?:beam\s+(?P<beams>\d+),\s*)?"
    r"(?:post\s+(?P<postprocess>\d+),\s*)?"
    r"fallbacks\s+(?P<fallbacks>\d+),\s*skips\s+(?P<skips>\d+)",
    re.IGNORECASE,
)
GLX_STREAM_CATEGORY_SUMMARY_RE = re.compile(
    r"glx:\s*stream categories\s*"
    r"entity\s+(?P<entityDraws>\d+)/(?P<entityAttempts>\d+),\s*"
    r"particle\s+(?P<particleDraws>\d+)/(?P<particleAttempts>\d+),\s*"
    r"poly\s+(?P<polyDraws>\d+)/(?P<polyAttempts>\d+),\s*"
    r"mark\s+(?P<markDraws>\d+)/(?P<markAttempts>\d+),\s*"
    r"weapon\s+(?P<weaponDraws>\d+)/(?P<weaponAttempts>\d+),\s*"
    r"ui\s+(?P<uiDraws>\d+)/(?P<uiAttempts>\d+),\s*"
    r"beam\s+(?P<beamDraws>\d+)/(?P<beamAttempts>\d+),\s*"
    r"special\s+(?P<specialDraws>\d+)/(?P<specialAttempts>\d+)",
    re.IGNORECASE,
)
GLX_STREAM_RESERVATION_SUMMARY_RE = re.compile(
    r"glx:\s*stream reservation last\s+(?P<lastBytes>\d+)\s+bytes\s+at\s+"
    r"(?P<lastOffset>\d+)\s+using\s+(?P<strategy>\S+),\s*"
    r"largest\s+(?P<largestBytes>\d+)\s+bytes,\s*"
    r"same-frame wrap rejects\s+(?P<sameFrameRejects>\d+)",
    re.IGNORECASE,
)
GLX_STATIC_DRAW_SUMMARY_RE = re.compile(
    r"glx:\s*static draw\s+(?P<calls>\d+)/(?P<attempts>\d+)\s+calls,\s*"
    r"(?P<indexes>\d+)\s+idx,\s*packets\s+(?P<packetFull>\d+)\s+full/"
    r"(?P<packetPartial>\d+)\s+partial/(?P<packetMisses>\d+)\s+miss,\s*"
    r"manifest\s+(?P<manifestCalls>\d+)/(?P<manifestIndexes>\d+)\s+idx,\s*"
    r"soft\s+(?P<softCalls>\d+)/(?P<softAttempts>\d+)\s+calls/"
    r"(?P<softIndexes>\d+)\s+idx,\s*arena\s+(?P<arenaCalls>\d+),\s*"
    r"legacy\s+(?P<legacyCalls>\d+),\s*fallbacks\s+(?P<fallbacks>\d+),\s*"
    r"policy skips\s+(?P<policySkips>\d+)",
    re.IGNORECASE,
)
GLX_STATIC_QUEUE_PACKETS_SUMMARY_RE = re.compile(
    r"glx:\s*static queue packets last\s+(?P<lastFull>\d+)\s+full/"
    r"(?P<lastPartial>\d+)\s+partial/(?P<lastMisses>\d+)\s+miss/"
    r"(?P<lastMismatches>\d+)\s+mismatch,\s*total\s+(?P<full>\d+)\s+full/"
    r"(?P<partial>\d+)\s+partial/(?P<misses>\d+)\s+miss",
    re.IGNORECASE,
)
GLX_STATIC_PACKET_LOOKUP_SUMMARY_RE = re.compile(
    r"glx:\s*static packet lookup\s+(?P<mapped>\d+)\s+mapped/max\s+"
    r"(?P<maxItem>-?\d+),\s*hits\s+(?P<hits>\d+),\s*"
    r"misses\s+(?P<misses>\d+),\s*fallbacks\s+(?P<fallbacks>\d+),\s*"
    r"mismatches\s+(?P<mismatches>\d+),\s*overflows\s+(?P<overflows>\d+)",
    re.IGNORECASE,
)
GLX_STATIC_MDI_SUMMARY_RE = re.compile(
    r"glx:\s*static MDI\s+(?P<calls>\d+)/(?P<attempts>\d+)\s+calls,\s*"
    r"(?P<runs>\d+)\s+runs/(?P<indexes>\d+)\s+idx,\s*fallbacks\s+(?P<fallbacks>\d+),\s*"
    r"skips\s+(?P<skips>\d+),\s*errors\s+(?P<errors>\d+),\s*largest\s+(?P<largest>\d+)",
    re.IGNORECASE,
)
GLX_GL3X_PERFORMANCE_SUMMARY_RE = re.compile(
    r"glx:\s*GL3X performance draws\s+(?P<draws>\d+)\s+"
    r"sync-uploads\s+(?P<syncUploads>\d+)\s+"
    r"static-buffers\s+(?P<staticBuffers>\d+)\s+"
    r"dynamic-buffers\s+(?P<dynamicBuffers>\d+)\s+"
    r"materials\s+(?P<materials>\d+)\s+"
    r"fbo-post\s+(?P<fboPost>\d+)\s+"
    r"unsupported persistent-upload\s+(?P<unsupportedPersistentUploads>\d+)",
    re.IGNORECASE,
)
GLX_GL41_MAC_MODERN_SUMMARY_RE = re.compile(
    r"glx:\s*GL41 mac-modern draws\s+(?P<draws>\d+)\s+"
    r"sync-uploads\s+(?P<syncUploads>\d+)\s+"
    r"static-buffers\s+(?P<staticBuffers>\d+)\s+"
    r"dynamic-buffers\s+(?P<dynamicBuffers>\d+)\s+"
    r"materials\s+(?P<materials>\d+)\s+"
    r"post\s+(?P<post>\d+)\s+"
    r"unsupported persistent-upload\s+(?P<unsupportedPersistentUploads>\d+)\s+"
    r"gl43-required\s+(?P<gl43Required>\d+)\s+"
    r"gl44-required\s+(?P<gl44Required>\d+)\s+"
    r"gl45-required\s+(?P<gl45Required>\d+)",
    re.IGNORECASE,
)
GLX_GL46_HIGH_END_SUMMARY_RE = re.compile(
    r"glx:\s*GL46 high-end draws\s+(?P<draws>\d+)\s+"
    r"persistent-uploads\s+(?P<persistentUploads>\d+)\s+"
    r"sync-uploads\s+(?P<syncUploads>\d+)\s+"
    r"dsa-products\s+(?P<dsaProducts>\d+)\s+"
    r"mdi-products\s+(?P<mdiProducts>\d+)\s+"
    r"aggressive-static\s+(?P<aggressiveStatic>\d+)\s+"
    r"materials\s+(?P<materials>\d+)\s+"
    r"post\s+(?P<post>\d+)\s+"
    r"gpu-counters\s+(?P<gpuCounters>\d+)\s+"
    r"static-mdi\s+(?P<staticMdiCalls>\d+)/(?P<staticMdiAttempts>\d+)\s+"
    r"calls/(?P<staticMdiIndexes>\d+)\s+idx",
    re.IGNORECASE,
)

DEFAULT_OPTIONS = {
    "renderers": "opengl,glx",
    "switch_sequence": None,
    "maps": None,
    "demos": "",
    "corpus_scenes": None,
    "profile": "glx-parity",
    "color_sweep": False,
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
    "r_screenshotCaptureMode": "0",
    "r_screenshotWriteViewpos": "1",
}

# Frozen GLx startup profiles. Keep these in sync with GLX_PROFILE_CVARS in
# code/rendererglx/glx_module.cpp; the GLx runtime sweep tests parse that table
# so the launch profile cannot drift quietly from the renderer-owned profile.
GLX_RC_PROFILE_CVARS = {
    "r_fbo": "1",
    "r_bloom": "2",
    "r_bloom_passes": "3",
    "r_hdrBloomFormat": "0",
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
    "r_glxStreamDrawShadows": "1",
    "r_glxStreamDrawBeams": "1",
    "r_glxStreamDrawPostProcess": "1",
    "r_glxMaterialRenderer": "1",
    "r_glxMaterialPrecache": "1",
    "r_glxGpuTiming": "1",
    "r_glxGpuPassTiming": "1",
    "r_glxStaticWorldArena": "1",
    "r_glxStaticWorldArenaDraw": "1",
    "r_glxStaticWorldDraw": "1",
    "r_glxStaticWorldSoftDraw": "1",
    "r_glxStaticWorldDrawPolicy": "full",
    "r_glxStaticWorldMultiDraw": "1",
    "r_glxStaticWorldPacketBatch": "1",
    "r_glxStaticWorldIndirectBuffer": "1",
    "r_glxStaticWorldIndirectDraw": "1",
    "r_glxStaticWorldMultiDrawIndirect": "1",
    "r_glxStaticWorldMultiDrawIndirectCompact": "0",
    "r_glxStaticWorldMultiDrawIndirectSpans": "1",
}

GLX_STRESS_PROFILE_CVARS = {
    **GLX_RC_PROFILE_CVARS,
    "r_glxStaticWorldMultiDrawIndirectCompact": "1",
}

GLX_COLOR_PROFILE_CVARS = {
    "r_fbo": "1",
    "r_bloom": "0",
    "r_hdr": "1",
    "r_tonemap": "2",
    "r_tonemapExposure": "1.0",
    "r_srgbTextures": "1",
    "r_framebufferSRGB": "1",
    "r_outputBackend": "1",
    "r_glxColorPipelineDebug": "2",
    "r_colorGrade": "3",
    "r_colorGradeLift": "0 0 0",
    "r_colorGradeGamma": "1 1 1",
    "r_colorGradeGain": "1 1 1",
    "r_colorGradeWhitePoint": "6504",
    "r_colorGradeAdaptWhitePoint": "6504",
    "r_colorGradeLUTScale": "4.0",
}

PROFILE_CVARS = {
    "baseline": {},
    "glx-world": {
        "r_vbo": "1",
        "r_glxWorldRenderer": "1",
        "r_glxGpuTiming": "1",
        "r_glxGpuPassTiming": "1",
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
        "r_glxMaterialPrecache": "1",
        "r_glxGpuTiming": "1",
        "r_glxGpuPassTiming": "1",
    },
    "glx-bloom": {
        "r_fbo": "1",
        "r_bloom": "2",
        "r_bloom_passes": "3",
        "r_glxGpuTiming": "1",
        "r_glxGpuPassTiming": "1",
    },
    "glx-color": GLX_COLOR_PROFILE_CVARS,
    "glx-parity": {
        "r_glxProfile": "rc",
        **GLX_RC_PROFILE_CVARS,
    },
    "glx-ownership": {
        "r_glxProfile": "rc",
        **GLX_RC_PROFILE_CVARS,
        "r_glxRequireOwnership": "1",
    },
    "glx-stress": {
        "r_glxProfile": "stress",
        **GLX_STRESS_PROFILE_CVARS,
    },
}

GLX_PROOF_CORPUS_VERSION = "2026-05-12-image-evidence-v1"
GLX_PROOF_CORPUS_DOC = "docs/fnquake3/GLX_PROOF_CORPUS.md"
GLX_PARITY_SUITE_VERSION = "2026-05-11-post-v1"

GLX_PROOF_CORPUS_SCENES: dict[str, dict[str, object]] = {
    "stock-q3dm1-hud": {
        "kind": "map",
        "target": "q3dm1",
        "assetTier": "retail-baseq3",
        "tags": (
            "stock-map",
            "baseline-map",
            "ui-hud-sensitive",
            "screenshot-parity",
            "hud-parity",
            "lightmap",
            "tcgen-lightmap",
            "dynamic-entity",
            "weapon-model",
            "greyscale-proof",
        ),
        "description": "Small retail map used for renderer-switch, weapon/HUD, and baseline-lighting comparisons.",
    },
    "stock-q3dm17-open": {
        "kind": "map",
        "target": "q3dm17",
        "assetTier": "retail-baseq3",
        "tags": (
            "stock-map",
            "open-map",
            "shader-heavy",
            "sky",
            "screenshot-parity",
            "bloom-parity",
            "tone-map-proof",
            "render-scale-proof",
        ),
        "description": "Open retail arena that keeps sky, portal-culling, and broad visibility paths in the RC set.",
    },
    "stock-q3dm6-geometry": {
        "kind": "map",
        "target": "q3dm6",
        "assetTier": "retail-baseq3",
        "tags": (
            "stock-map",
            "high-geometry",
            "large-map",
            "screenshot-parity",
            "shadow-parity",
            "performance-comparison",
            "dynamic-entity",
            "planar-shadow",
        ),
        "description": "Retail large-map geometry probe for static-world packet and draw-pressure comparisons.",
    },
    "stock-q3dm11-shader": {
        "kind": "map",
        "target": "q3dm11",
        "assetTier": "retail-baseq3",
        "tags": (
            "stock-map",
            "shader-heavy",
            "material-stage",
            "tcgen-environment",
            "screenshot-parity",
            "cel-shading-parity",
            "outline-parity",
            "color-grade-proof",
            "tone-map-proof",
            "dynamic-entity",
        ),
        "description": "Retail shader-stage probe for material ordering, blend, texmod, and environment paths.",
    },
    "stock-q3dm15-fog": {
        "kind": "map",
        "target": "q3dm15",
        "assetTier": "retail-baseq3",
        "tags": (
            "stock-map",
            "fog-heavy",
            "visibility",
            "tcgen-fog",
            "screenshot-parity",
            "color-grade-proof",
        ),
        "description": "Retail fog/visibility probe that keeps fog-sensitive world and stream paths represented.",
    },
    "modern-fnq3glx-heavy01": {
        "kind": "map",
        "target": "fnq3_glx_heavy01",
        "assetTier": "glx-proof-corpus",
        "tags": (
            "modern-map",
            "high-geometry",
            "large-map",
            "screenshot-parity",
            "performance-comparison",
        ),
        "description": "Optional GLx proof-corpus stress map for dense modern static-world geometry.",
    },
    "modern-fnq3glx-shader01": {
        "kind": "map",
        "target": "fnq3_glx_shader01",
        "assetTier": "glx-proof-corpus",
        "tags": (
            "modern-map",
            "shader-heavy",
            "material-stage",
            "animated-image",
            "tcgen-vector",
            "screen-map",
            "video-map",
            "screenshot-parity",
            "cel-shading-parity",
            "outline-parity",
        ),
        "description": "Optional GLx proof-corpus stress map for broad shader-stage, animated-image, screen-map, video-map, and material-key coverage.",
    },
    "modern-fnq3glx-fog01": {
        "kind": "map",
        "target": "fnq3_glx_fog01",
        "assetTier": "glx-proof-corpus",
        "tags": (
            "modern-map",
            "fog-heavy",
            "visibility",
            "screenshot-parity",
        ),
        "description": "Optional GLx proof-corpus stress map for layered fog and visibility comparisons.",
    },
    "timedemo-demo1": {
        "kind": "demo",
        "target": "demo1",
        "assetTier": "retail-baseq3",
        "tags": (
            "stock-demo",
            "demo-playback-parity",
            "performance-comparison",
            "dynamic-entity",
            "dynamic-light",
        ),
        "description": "Retail timedemo used for legacy OpenGL versus GLx performance comparisons.",
    },
    "timedemo-fnq3glx-particles01": {
        "kind": "demo",
        "target": "fnq3_glx_particles01",
        "assetTier": "glx-proof-corpus",
        "tags": (
            "particle-heavy-demo",
            "demo-playback-parity",
            "modern-map",
            "performance-comparison",
            "particle",
            "transient-poly",
            "mark-decal",
            "beam",
            "dynamic-light",
        ),
        "description": "Optional GLx proof-corpus timedemo for particles, marks, transient polys, and UI churn.",
    },
}

GLX_IMAGE_EVIDENCE_CORPUS: dict[str, dict[str, object]] = {
    "stock-q3dm1-hud": {
        "role": "hud-over-lit-world",
        "probes": ("hud-over-bright-world", "baseline-luma", "greyscale-final"),
        "expectedSidecars": GLX_IMAGE_EVIDENCE_SIDECARS,
    },
    "stock-q3dm17-open": {
        "role": "open-bright-bloom",
        "probes": ("bloom-threshold", "sky-highlight", "tone-map-highlight-rolloff"),
        "expectedSidecars": GLX_IMAGE_EVIDENCE_SIDECARS,
    },
    "stock-q3dm6-geometry": {
        "role": "geometry-and-specular-contrast",
        "probes": ("high-contrast-geometry", "planar-shadow", "specular-highlight"),
        "expectedSidecars": GLX_IMAGE_EVIDENCE_SIDECARS,
    },
    "stock-q3dm11-shader": {
        "role": "saturated-materials",
        "probes": ("saturated-primaries", "color-grade", "out-of-gamut-risk"),
        "expectedSidecars": GLX_IMAGE_EVIDENCE_SIDECARS,
    },
    "stock-q3dm15-fog": {
        "role": "low-contrast-fog",
        "probes": ("fog-luma-compression", "low-light-exposure", "histogram-spread"),
        "expectedSidecars": GLX_IMAGE_EVIDENCE_SIDECARS,
    },
    "modern-fnq3glx-heavy01": {
        "role": "stress-geometry",
        "probes": ("large-scene-histogram", "performance-correlation"),
        "expectedSidecars": GLX_IMAGE_EVIDENCE_SIDECARS,
    },
    "modern-fnq3glx-shader01": {
        "role": "stress-material-color",
        "probes": ("animated-materials", "saturated-primaries", "screen-video-map-color"),
        "expectedSidecars": GLX_IMAGE_EVIDENCE_SIDECARS,
    },
    "modern-fnq3glx-fog01": {
        "role": "stress-fog-exposure",
        "probes": ("fog-luma-compression", "exposure-transition"),
        "expectedSidecars": GLX_IMAGE_EVIDENCE_SIDECARS,
    },
    "timedemo-demo1": {
        "role": "retail-demo-motion",
        "probes": ("timedemo-parity", "dynamic-light-reference"),
        "expectedSidecars": (),
    },
    "timedemo-fnq3glx-particles01": {
        "role": "emissive-particles",
        "probes": ("emissive-bursts", "exposure-transition", "bloom-threshold"),
        "expectedSidecars": GLX_IMAGE_EVIDENCE_SIDECARS,
    },
}

GLX_GATE_CORPUS_SCENES = {
    "rc-smoke": (
        "stock-q3dm1-hud",
    ),
    "rc-parity": (
        "stock-q3dm1-hud",
        "stock-q3dm17-open",
        "timedemo-demo1",
    ),
    "rc-proof": (
        "stock-q3dm1-hud",
        "stock-q3dm17-open",
        "stock-q3dm6-geometry",
        "stock-q3dm11-shader",
        "stock-q3dm15-fog",
        "timedemo-demo1",
    ),
    "rc-stress": (
        "stock-q3dm1-hud",
        "stock-q3dm17-open",
        "stock-q3dm6-geometry",
        "stock-q3dm11-shader",
        "stock-q3dm15-fog",
        "modern-fnq3glx-heavy01",
        "modern-fnq3glx-shader01",
        "modern-fnq3glx-fog01",
        "timedemo-demo1",
        "timedemo-fnq3glx-particles01",
    ),
}

GLX_PARITY_SUITES: dict[str, dict[str, object]] = {
    "screenshot": {
        "artifact": "screenshot",
        "sceneIds": (
            "stock-q3dm1-hud",
            "stock-q3dm17-open",
            "stock-q3dm6-geometry",
            "stock-q3dm11-shader",
            "stock-q3dm15-fog",
        ),
        "requiredTags": ("screenshot-parity",),
        "cvars": {},
        "description": "Retail map screenshot suite used for OpenGL versus GLx image parity baselines.",
    },
    "demo-playback": {
        "artifact": "timedemo",
        "sceneIds": ("timedemo-demo1",),
        "requiredTags": ("demo-playback-parity", "stock-demo"),
        "cvars": {},
        "description": "Retail demo playback suite used for deterministic timedemo parity and performance floors.",
    },
    "hud": {
        "artifact": "screenshot",
        "sceneIds": ("stock-q3dm1-hud",),
        "requiredTags": ("hud-parity", "ui-hud-sensitive"),
        "cvars": {},
        "description": "HUD and 2D stretch-pic suite anchored to the small retail renderer-switch map.",
    },
    "shadow": {
        "artifact": "screenshot",
        "sceneIds": ("stock-q3dm6-geometry",),
        "requiredTags": ("shadow-parity",),
        "cvars": {
            "cg_shadows": "2",
        },
        "description": "Stencil shadow parity suite using a retail geometry-heavy map and explicit shadow cvar state.",
    },
    "bloom": {
        "artifact": "screenshot",
        "sceneIds": ("stock-q3dm17-open",),
        "requiredTags": ("bloom-parity",),
        "cvars": {},
        "description": "Final-pass bloom parity suite on an open retail scene with the RC bloom profile enabled.",
    },
    "cel-shading": {
        "artifact": "screenshot",
        "sceneIds": ("stock-q3dm11-shader",),
        "requiredTags": ("cel-shading-parity", "outline-parity"),
        "cvars": {
            "r_celShading": "1",
            "r_celOutline": "1",
            "r_celShadingSteps": "4",
        },
        "description": "Cel-shading and outline parity suite with explicit banding and outline cvars.",
    },
    "greyscale": {
        "artifact": "screenshot",
        "sceneIds": ("stock-q3dm1-hud",),
        "requiredTags": ("greyscale-proof",),
        "cvars": {
            "r_fbo": "1",
            "r_greyscale": "1",
        },
        "description": "Greyscale final-pass proof suite using the HUD baseline scene and explicit FBO greyscale cvar.",
    },
    "render-scale": {
        "artifact": "screenshot",
        "sceneIds": ("stock-q3dm17-open",),
        "requiredTags": ("render-scale-proof",),
        "cvars": {
            "r_fbo": "1",
            "r_renderScale": "1",
            "r_renderWidth": "512",
            "r_renderHeight": "384",
        },
        "description": "Render-scale proof suite using an open retail scene and explicit custom render dimensions.",
    },
}

GLX_PARITY_CVAR_DEFAULTS = {
    "cg_shadows": "1",
    "r_celShading": "0",
    "r_celOutline": "1",
    "r_celShadingSteps": "4",
    "r_greyscale": "0",
    "r_renderScale": "0",
}

GLX_GATE_PARITY_SUITES = {
    "rc-smoke": (),
    "rc-parity": (),
    "rc-proof": (
        "screenshot",
        "demo-playback",
        "hud",
        "shadow",
        "bloom",
        "cel-shading",
        "greyscale",
        "render-scale",
    ),
    "rc-stress": (
        "screenshot",
        "demo-playback",
        "hud",
        "shadow",
        "bloom",
        "cel-shading",
        "greyscale",
        "render-scale",
    ),
}

GLX_PROFILE_CORPUS_SCENES = {
    "baseline": ("stock-q3dm1-hud",),
    "glx-world": ("stock-q3dm1-hud",),
    "glx-material": ("stock-q3dm1-hud", "stock-q3dm11-shader"),
    "glx-bloom": ("stock-q3dm1-hud",),
    "glx-color": ("stock-q3dm17-open", "stock-q3dm11-shader", "stock-q3dm15-fog"),
    "glx-parity": ("stock-q3dm1-hud",),
    "glx-ownership": ("stock-q3dm1-hud", "stock-q3dm17-open"),
    "glx-stress": GLX_GATE_CORPUS_SCENES["rc-stress"],
}

GLX_SCENE_TARGET_FORMAT_CONTRACT = {
    "internalFormat": "0x881a",
    "internalFormatName": "GL_RGBA16F",
    "textureFormat": "0x1908",
    "textureFormatName": "GL_RGBA",
    "textureType": "0x140b",
    "textureTypeName": "GL_HALF_FLOAT",
}

GLX_SDR_OUTPUT_CONTRACT = {
    "transfer": "sdr-srgb",
    "encode": "shader-srgb",
    "framebufferSrgb": False,
    "paperWhiteNits": 203.0,
    "maxOutputNits": 203.0,
}

GLX_SCREENSHOT_CAPTURE_POLICY_CONTRACT = {
    "version": 1,
    "defaultMode": "sdr-srgb",
    "defaultColorSpace": "sdr-srgb",
    "hdrAwareModes": ("hdr-scene-linear", "hdr-output"),
    "hdrExportStatus": "explicit-reserved",
}

GLX_TEXTURE_CLASSIFICATION_DOC = "docs/fnquake3/GLX_COLORSPACE_AUDIT.md"
GLX_TEXTURE_CLASSIFICATION_CONTRACT = {
    "authored-color": {
        "declaredSpace": "srgb",
        "sceneLinearDecode": "srgb-once",
    },
    "lightmap": {
        "declaredSpace": "linear",
        "sceneLinearDecode": "never",
    },
    "procedural-linear": {
        "declaredSpace": "linear",
        "sceneLinearDecode": "never",
    },
    "data": {
        "declaredSpace": "data",
        "sceneLinearDecode": "never",
    },
    "capture-target": {
        "declaredSpace": "linear-or-output-declared",
        "sceneLinearDecode": "not-authored-srgb",
    },
}
GLX_REQUIRED_TEXTURE_CLASS_ROWS = tuple(GLX_TEXTURE_CLASSIFICATION_CONTRACT)

GLX_COLOR_SWEEP_MATRIX: tuple[dict[str, object], ...] = (
    {
        "id": "sdr-legacy-bloom-off",
        "purpose": "Legacy SDR compatibility reference with bloom disabled.",
        "probe": "gray-ramp-ui-bloom-off",
        "cvars": {
            "r_fbo": "1",
            "r_bloom": "0",
            "r_hdr": "0",
            "r_tonemap": "0",
            "r_tonemapExposure": "1.0",
            "r_srgbTextures": "0",
            "r_framebufferSRGB": "0",
            "r_outputBackend": "1",
            "r_glxColorPipelineDebug": "2",
        },
        "expect": {
            "space": "display-referred-sdr",
            "transfer": "sdr-srgb",
            "toneMap": "legacy",
            "exposure": 1.0,
            "paperWhiteNits": 203.0,
            "maxOutputNits": 203.0,
            "sceneTargetFloat": 0,
            "finalEncode": "none",
            "contract": 1,
            "framebufferSrgb": 0,
            "srgbDecode": 0,
            "outputRequest": "sdr-srgb",
        },
    },
    {
        "id": "scene-linear-sdr-legacy",
        "purpose": "Scene-linear SDR output using legacy tone scale, shader sRGB encode, and bloom disabled.",
        "probe": "gray-ramp-output-contract",
        "cvars": {
            "r_fbo": "1",
            "r_bloom": "0",
            "r_hdr": "1",
            "r_hdrPrecision": "0",
            "r_tonemap": "0",
            "r_tonemapExposure": "1.0",
            "r_srgbTextures": "1",
            "r_framebufferSRGB": "1",
            "r_outputBackend": "1",
            "r_glxColorPipelineDebug": "2",
        },
        "expect": {
            "space": "scene-linear",
            "transfer": "sdr-srgb",
            "toneMap": "legacy",
            "exposure": 1.0,
            "paperWhiteNits": 203.0,
            "maxOutputNits": 203.0,
            "sceneTargetFloat": 1,
            "finalEncode": "shader-srgb",
            "contract": 1,
            "framebufferSrgb": 0,
            "srgbDecode": 1,
            "outputRequest": "sdr-srgb",
            "internalFormat": "0x881a",
            "textureFormat": "0x1908",
            "textureType": "0x140b",
        },
    },
    {
        "id": "scene-linear-sdr-reinhard-exposure-low",
        "purpose": "Scene-linear SDR output through simple Reinhard tone mapping at low exposure for mid-gray placement.",
        "probe": "mid-gray-exposure-low",
        "cvars": {
            "r_fbo": "1",
            "r_bloom": "0",
            "r_hdr": "1",
            "r_hdrPrecision": "0",
            "r_tonemap": "1",
            "r_tonemapExposure": "0.5",
            "r_srgbTextures": "1",
            "r_framebufferSRGB": "1",
            "r_outputBackend": "1",
            "r_glxColorPipelineDebug": "2",
        },
        "expect": {
            "space": "scene-linear",
            "transfer": "sdr-srgb",
            "toneMap": "reinhard-simple",
            "exposure": 0.5,
            "paperWhiteNits": 203.0,
            "maxOutputNits": 203.0,
            "sceneTargetFloat": 1,
            "finalEncode": "shader-srgb",
            "contract": 1,
            "framebufferSrgb": 0,
            "srgbDecode": 1,
            "outputRequest": "sdr-srgb",
            "internalFormat": "0x881a",
            "textureFormat": "0x1908",
            "textureType": "0x140b",
        },
    },
    {
        "id": "scene-linear-sdr-aces",
        "purpose": "Scene-linear SDR output through the ACES-fitted curve and shader sRGB encode.",
        "probe": "color-checker-tone-map",
        "cvars": {
            "r_fbo": "1",
            "r_bloom": "0",
            "r_hdr": "1",
            "r_hdrPrecision": "0",
            "r_tonemap": "2",
            "r_tonemapExposure": "1.0",
            "r_srgbTextures": "1",
            "r_framebufferSRGB": "1",
            "r_outputBackend": "1",
            "r_glxColorPipelineDebug": "2",
        },
        "expect": {
            "space": "scene-linear",
            "transfer": "sdr-srgb",
            "toneMap": "aces-fitted",
            "exposure": 1.0,
            "paperWhiteNits": 203.0,
            "maxOutputNits": 203.0,
            "sceneTargetFloat": 1,
            "finalEncode": "shader-srgb",
            "contract": 1,
            "framebufferSrgb": 0,
            "srgbDecode": 1,
            "outputRequest": "sdr-srgb",
            "internalFormat": "0x881a",
            "textureFormat": "0x1908",
            "textureType": "0x140b",
        },
    },
    {
        "id": "scene-linear-sdr-aces-exposure-high",
        "purpose": "Scene-linear SDR output through the ACES-fitted curve at high exposure for highlight clipping evidence.",
        "probe": "highlight-clipping-exposure-high",
        "cvars": {
            "r_fbo": "1",
            "r_bloom": "0",
            "r_hdr": "1",
            "r_hdrPrecision": "0",
            "r_tonemap": "2",
            "r_tonemapExposure": "2.0",
            "r_srgbTextures": "1",
            "r_framebufferSRGB": "1",
            "r_outputBackend": "1",
            "r_glxColorPipelineDebug": "2",
        },
        "expect": {
            "space": "scene-linear",
            "transfer": "sdr-srgb",
            "toneMap": "aces-fitted",
            "exposure": 2.0,
            "paperWhiteNits": 203.0,
            "maxOutputNits": 203.0,
            "sceneTargetFloat": 1,
            "finalEncode": "shader-srgb",
            "contract": 1,
            "framebufferSrgb": 0,
            "srgbDecode": 1,
            "outputRequest": "sdr-srgb",
            "internalFormat": "0x881a",
            "textureFormat": "0x1908",
            "textureType": "0x140b",
        },
    },
    {
        "id": "scene-linear-srgb-decode-off",
        "purpose": "Scene-linear SDR control row with authored-texture sRGB decode disabled.",
        "probe": "texture-decode-control",
        "cvars": {
            "r_fbo": "1",
            "r_bloom": "0",
            "r_hdr": "1",
            "r_hdrPrecision": "0",
            "r_tonemap": "2",
            "r_tonemapExposure": "1.0",
            "r_srgbTextures": "0",
            "r_framebufferSRGB": "1",
            "r_outputBackend": "1",
            "r_glxColorPipelineDebug": "2",
        },
        "expect": {
            "space": "scene-linear",
            "transfer": "sdr-srgb",
            "toneMap": "aces-fitted",
            "exposure": 1.0,
            "paperWhiteNits": 203.0,
            "maxOutputNits": 203.0,
            "sceneTargetFloat": 1,
            "finalEncode": "shader-srgb",
            "contract": 1,
            "framebufferSrgb": 0,
            "srgbDecode": 0,
            "srgbRequested": 0,
            "outputRequest": "sdr-srgb",
            "internalFormat": "0x881a",
            "textureFormat": "0x1908",
            "textureType": "0x140b",
        },
    },
    {
        "id": "scene-linear-auto-output",
        "purpose": "Scene-linear output-backend auto-selection row for SDR/HDR platform evidence.",
        "probe": "hdr-backend-selection",
        "cvars": {
            "r_fbo": "1",
            "r_bloom": "0",
            "r_hdr": "1",
            "r_hdrPrecision": "0",
            "r_tonemap": "2",
            "r_tonemapExposure": "1.0",
            "r_srgbTextures": "1",
            "r_framebufferSRGB": "1",
            "r_outputBackend": "0",
            "r_glxColorPipelineDebug": "2",
        },
        "expect": {
            "space": "scene-linear",
            "toneMap": "aces-fitted",
            "exposure": 1.0,
            "sceneTargetFloat": 1,
            "contract": 1,
            "srgbDecode": 1,
            "outputRequest": "auto",
            "internalFormat": "0x881a",
            "textureFormat": "0x1908",
            "textureType": "0x140b",
        },
    },
    {
        "id": "scene-linear-windows-scrgb-request",
        "purpose": "Scene-linear explicit Windows scRGB backend request, with safe SDR fallback when HDR output is unavailable.",
        "probe": "hdr-backend-request-scrgb",
        "cvars": {
            "r_fbo": "1",
            "r_bloom": "0",
            "r_hdr": "1",
            "r_hdrPrecision": "0",
            "r_tonemap": "2",
            "r_tonemapExposure": "1.0",
            "r_srgbTextures": "1",
            "r_framebufferSRGB": "1",
            "r_outputBackend": "2",
            "r_glxColorPipelineDebug": "2",
        },
        "expect": {
            "space": "scene-linear",
            "toneMap": "aces-fitted",
            "exposure": 1.0,
            "sceneTargetFloat": 1,
            "contract": 1,
            "srgbDecode": 1,
            "outputRequest": "windows-scrgb",
            "internalFormat": "0x881a",
            "textureFormat": "0x1908",
            "textureType": "0x140b",
        },
    },
)


def _dedupe(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(items))


def corpus_scene_ids_csv(scene_ids: Iterable[str]) -> str:
    return ",".join(scene_ids)


def validate_corpus_scene_ids(scene_ids: Iterable[str]) -> list[str]:
    scene_list = [str(scene_id).strip() for scene_id in scene_ids if str(scene_id).strip()]
    unknown = [scene_id for scene_id in scene_list if scene_id not in GLX_PROOF_CORPUS_SCENES]
    if unknown:
        raise ValueError(
            "Unknown GLx proof corpus scene id(s): " + ", ".join(unknown)
        )
    return scene_list


def corpus_targets_csv(scene_ids: Iterable[str], kind: str) -> str:
    return ",".join(corpus_targets(scene_ids, kind))


def corpus_targets(scene_ids: Iterable[str], kind: str) -> list[str]:
    targets: list[str] = []
    for scene_id in validate_corpus_scene_ids(scene_ids):
        scene = GLX_PROOF_CORPUS_SCENES[scene_id]
        if scene.get("kind") == kind:
            targets.append(str(scene["target"]))
    return _dedupe(targets)


def corpus_tags(scene_ids: Iterable[str]) -> list[str]:
    tags: list[str] = []
    for scene_id in validate_corpus_scene_ids(scene_ids):
        scene_tags = GLX_PROOF_CORPUS_SCENES[scene_id].get("tags", ())
        tags.extend(str(tag) for tag in scene_tags if str(tag).strip())
    return sorted(set(tags))


def corpus_scene_records(scene_ids: Iterable[str]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for scene_id in validate_corpus_scene_ids(scene_ids):
        scene = GLX_PROOF_CORPUS_SCENES[scene_id]
        image_evidence = GLX_IMAGE_EVIDENCE_CORPUS.get(scene_id, {})
        records.append(
            {
                "id": scene_id,
                "kind": scene["kind"],
                "target": scene["target"],
                "assetTier": scene["assetTier"],
                "tags": list(scene.get("tags", ())),
                "description": scene["description"],
                "imageEvidence": {
                    "role": image_evidence.get("role", ""),
                    "probes": list(image_evidence.get("probes", ())),
                    "expectedSidecars": list(image_evidence.get("expectedSidecars", ())),
                },
            }
        )
    return records


def validate_parity_suite_ids(suite_ids: Iterable[str]) -> list[str]:
    suite_list = [str(suite_id).strip() for suite_id in suite_ids if str(suite_id).strip()]
    unknown = [suite_id for suite_id in suite_list if suite_id not in GLX_PARITY_SUITES]
    if unknown:
        raise ValueError(
            "Unknown GLx parity suite id(s): " + ", ".join(unknown)
        )
    return suite_list


def parity_suite_records(suite_ids: Iterable[str]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for suite_id in validate_parity_suite_ids(suite_ids):
        suite = GLX_PARITY_SUITES[suite_id]
        records.append(
            {
                "id": suite_id,
                "artifact": suite["artifact"],
                "sceneIds": list(validate_corpus_scene_ids(suite.get("sceneIds", ()))),
                "requiredTags": list(suite.get("requiredTags", ())),
                "cvars": dict(suite.get("cvars", {})),
                "description": suite["description"],
            }
        )
    return records


def parity_suite_ids_for_scene_ids(
    scene_ids: Iterable[str],
    suite_ids: Iterable[str],
) -> list[str]:
    selected_scene_ids = set(validate_corpus_scene_ids(scene_ids))
    matched_suite_ids: list[str] = []
    for suite_id in validate_parity_suite_ids(suite_ids):
        suite_scene_ids = set(validate_corpus_scene_ids(GLX_PARITY_SUITES[suite_id].get("sceneIds", ())))
        if selected_scene_ids.intersection(suite_scene_ids):
            matched_suite_ids.append(suite_id)
    return matched_suite_ids


def parity_suite_cvars_for_scene_ids(
    scene_ids: Iterable[str],
    suite_ids: Iterable[str],
) -> dict[str, str]:
    cvars: dict[str, str] = {}
    for suite_id in parity_suite_ids_for_scene_ids(scene_ids, suite_ids):
        suite_cvars = GLX_PARITY_SUITES[suite_id].get("cvars", {})
        if not isinstance(suite_cvars, dict):
            continue
        for name, value in suite_cvars.items():
            cvar_name = str(name).strip()
            cvar_value = str(value)
            if not cvar_name:
                continue
            existing = cvars.get(cvar_name)
            if existing is not None and existing != cvar_value:
                raise ValueError(
                    "Conflicting GLx parity suite cvar "
                    f"{cvar_name}: {existing} versus {cvar_value}."
                )
            cvars[cvar_name] = cvar_value
    return cvars


def corpus_scene_ids_for_profile(profile: str) -> tuple[str, ...]:
    return tuple(GLX_PROFILE_CORPUS_SCENES.get(profile, ("stock-q3dm1-hud",)))


def corpus_scene_ids_for_gate(gate: str | None, profile: str) -> tuple[str, ...]:
    if gate and gate in GLX_GATE_CORPUS_SCENES:
        return tuple(GLX_GATE_CORPUS_SCENES[gate])
    return corpus_scene_ids_for_profile(profile)


def corpus_scene_ids_for_target(scene_ids: Iterable[str], kind: str, target: str) -> list[str]:
    target_lower = target.lower()
    return [
        scene_id
        for scene_id in validate_corpus_scene_ids(scene_ids)
        if GLX_PROOF_CORPUS_SCENES[scene_id].get("kind") == kind and
        str(GLX_PROOF_CORPUS_SCENES[scene_id].get("target", "")).lower() == target_lower
    ]


def proof_corpus_manifest(
    scene_ids: Iterable[str],
    required_tags: Iterable[str] = (),
    required_parity_suites: Iterable[str] = (),
) -> dict[str, object]:
    selected_scene_ids = validate_corpus_scene_ids(scene_ids)
    selected_parity_suite_ids = validate_parity_suite_ids(required_parity_suites)
    return {
        "version": GLX_PROOF_CORPUS_VERSION,
        "document": GLX_PROOF_CORPUS_DOC,
        "selectedSceneIds": selected_scene_ids,
        "selectedScenes": corpus_scene_records(selected_scene_ids),
        "selectedTags": corpus_tags(selected_scene_ids),
        "requiredTags": sorted(set(str(tag) for tag in required_tags if str(tag).strip())),
        "paritySuiteVersion": GLX_PARITY_SUITE_VERSION,
        "paritySuiteIds": selected_parity_suite_ids,
        "paritySuites": parity_suite_records(selected_parity_suite_ids),
        "imageEvidenceVersion": GLX_IMAGE_EVIDENCE_VERSION,
        "imageEvidenceSceneIds": sorted(GLX_IMAGE_EVIDENCE_CORPUS),
        "allSceneIds": sorted(GLX_PROOF_CORPUS_SCENES),
    }


def release_corpus_manifest() -> dict[str, object]:
    return {
        "version": GLX_PROOF_CORPUS_VERSION,
        "document": GLX_PROOF_CORPUS_DOC,
        "sceneCount": len(GLX_PROOF_CORPUS_SCENES),
        "allSceneIds": sorted(GLX_PROOF_CORPUS_SCENES),
        "gateSceneIds": {
            gate: list(scene_ids)
            for gate, scene_ids in sorted(GLX_GATE_CORPUS_SCENES.items())
        },
        "paritySuiteVersion": GLX_PARITY_SUITE_VERSION,
        "paritySuites": parity_suite_records(GLX_PARITY_SUITES.keys()),
        "gateParitySuiteIds": {
            gate: list(suite_ids)
            for gate, suite_ids in sorted(GLX_GATE_PARITY_SUITES.items())
        },
        "imageEvidenceVersion": GLX_IMAGE_EVIDENCE_VERSION,
        "imageEvidenceSceneIds": sorted(GLX_IMAGE_EVIDENCE_CORPUS),
        "tags": corpus_tags(GLX_PROOF_CORPUS_SCENES.keys()),
    }


def normalize_proof_platform(value: str) -> str:
    platform_id = value.strip().lower().replace("amd64", "x64")
    if not PROOF_PLATFORM_RE.match(platform_id):
        raise ValueError(
            "Proof platform must be a stable id such as windows-x64 or linux-x86_64."
        )
    return platform_id


def runtime_platform_id(
    system_name: str | None = None,
    machine_name: str | None = None,
) -> str:
    system_value = (system_name or platform.system() or "unknown").strip().lower()
    machine_value = (machine_name or platform.machine() or "unknown").strip().lower()
    machine_aliases = {
        "amd64": "x64",
        "x86_64": "x86_64",
        "i386": "x86",
        "i686": "x86",
        "arm64": "arm64",
        "aarch64": "arm64",
    }
    arch = machine_aliases.get(machine_value, re.sub(r"[^a-z0-9_]+", "-", machine_value))
    if system_value.startswith("win"):
        os_id = "windows"
        if arch == "x86_64":
            arch = "x64"
    elif system_value.startswith("linux"):
        os_id = "linux"
    elif system_value.startswith("darwin") or system_value.startswith("mac"):
        os_id = "macos"
    else:
        os_id = re.sub(r"[^a-z0-9_]+", "-", system_value) or "unknown"
    return normalize_proof_platform(f"{os_id}-{arch}")


def host_platform_manifest() -> dict[str, object]:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "proofPlatform": runtime_platform_id(),
        "python": platform.python_version(),
    }


PROFILE_MAPS = {
    profile: corpus_targets_csv(scene_ids, "map")
    for profile, scene_ids in GLX_PROFILE_CORPUS_SCENES.items()
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
    "r_hdr",
    "r_hdrPrecision",
    "r_hdrBloomFormat",
    "r_srgbTextures",
    "r_framebufferSRGB",
    "r_tonemap",
    "r_tonemapExposure",
    "r_outputBackend",
    "r_glxColorPipelineDebug",
    "r_vbo",
    "r_glxProfile",
    "r_glxRequireOwnership",
}

GLX_PROFILE_FORCED_CVARS = {
    name
    for profile in ("glx-parity", "glx-ownership", "glx-stress")
    for name in PROFILE_CVARS[profile]
    if name.startswith("r_glx") and name not in {"r_glxProfile", "r_glxRequireOwnership"}
}

RC_GATE_PRESETS = {
    "rc-smoke": {
        "description": "Renderer lifecycle smoke gate for module load, map load, screenshots, and repeated in-process switches.",
        "defaults": {
            "profile": "baseline",
            "corpus_scenes": corpus_scene_ids_csv(GLX_GATE_CORPUS_SCENES["rc-smoke"]),
            "maps": corpus_targets_csv(GLX_GATE_CORPUS_SCENES["rc-smoke"], "map"),
            "demos": "",
            "renderers": "opengl,glx",
            "switch_sequence": "opengl,glx,opengl,glx",
            "switch_rounds": 2,
            "timeout": 240.0,
        },
        "requirements": {
            "require_proof_corpus": True,
            "required_corpus_tags": (
                "stock-map",
                "ui-hud-sensitive",
                "screenshot-parity",
                "hud-parity",
            ),
            "require_screenshots": True,
            "require_renderer_switch_lifecycle": True,
            "require_renderer_switch_roundtrip": True,
            "require_glx_diagnostics": True,
            "require_glx_performance_samples": True,
        },
    },
    "rc-parity": {
        "description": "Blocking GLx RC parity gate for the conservative world, stream, dynamic-scene, material, bloom, and timing profile.",
        "defaults": {
            "profile": "glx-parity",
            "corpus_scenes": corpus_scene_ids_csv(GLX_GATE_CORPUS_SCENES["rc-parity"]),
            "maps": corpus_targets_csv(GLX_GATE_CORPUS_SCENES["rc-parity"], "map"),
            "demos": corpus_targets_csv(GLX_GATE_CORPUS_SCENES["rc-parity"], "demo"),
            "renderers": "opengl,glx",
            "switch_sequence": "opengl,glx,opengl,glx",
            "switch_rounds": 1,
            "color_sweep": True,
            "timeout": 300.0,
        },
        "requirements": {
            "require_proof_corpus": True,
            "required_corpus_tags": (
                "stock-map",
                "stock-demo",
                "ui-hud-sensitive",
                "screenshot-parity",
                "demo-playback-parity",
                "hud-parity",
                "bloom-parity",
                "performance-comparison",
            ),
            "require_screenshots": True,
            "require_timedemo_metrics": True,
            "baseline_renderer": "opengl",
            "candidate_renderer": "glx",
            "min_timedemo_fps_ratio": 0.90,
            "screenshot_max_rms": 2.0,
            "screenshot_max_pixel_ratio": 0.005,
            "require_renderer_switch_lifecycle": True,
            "require_renderer_switch_roundtrip": True,
            "require_glx_diagnostics": True,
            "require_glx_performance_samples": True,
            "require_glx_color_sweep": True,
            "require_world_proof": True,
            "required_world_tags": (
                "stock-map",
                "lightmap",
            ),
        },
    },
    "rc-proof": {
        "description": "Blocking GLx RC proof gate requiring reviewed screenshot and performance baselines.",
        "defaults": {
            "profile": "glx-parity",
            "corpus_scenes": corpus_scene_ids_csv(GLX_GATE_CORPUS_SCENES["rc-proof"]),
            "maps": corpus_targets_csv(GLX_GATE_CORPUS_SCENES["rc-proof"], "map"),
            "demos": corpus_targets_csv(GLX_GATE_CORPUS_SCENES["rc-proof"], "demo"),
            "renderers": "opengl,glx",
            "switch_sequence": "opengl,glx,opengl,glx",
            "switch_rounds": 1,
            "color_sweep": True,
            "timeout": 300.0,
        },
        "requirements": {
            "require_proof_corpus": True,
            "required_corpus_tags": (
                "stock-map",
                "high-geometry",
                "shader-heavy",
                "fog-heavy",
                "color-grade-proof",
                "tone-map-proof",
                "ui-hud-sensitive",
                "screenshot-parity",
                "demo-playback-parity",
                "hud-parity",
                "shadow-parity",
                "bloom-parity",
                "cel-shading-parity",
                "outline-parity",
                "material-stage",
                "dynamic-entity",
                "weapon-model",
                "dynamic-light",
                "planar-shadow",
                "greyscale-proof",
                "render-scale-proof",
                "tcgen-lightmap",
                "tcgen-environment",
                "tcgen-fog",
                "performance-comparison",
            ),
            "required_parity_suites": GLX_GATE_PARITY_SUITES["rc-proof"],
            "require_screenshots": True,
            "require_visual_baseline": True,
            "require_performance_baseline": True,
            "require_timedemo_metrics": True,
            "baseline_renderer": "opengl",
            "candidate_renderer": "glx",
            "min_timedemo_fps_ratio": 0.90,
            "screenshot_max_rms": 2.0,
            "screenshot_max_pixel_ratio": 0.005,
            "require_renderer_switch_lifecycle": True,
            "require_renderer_switch_roundtrip": True,
            "require_glx_diagnostics": True,
            "require_glx_performance_samples": True,
            "require_glx_color_sweep": True,
            "require_world_proof": True,
            "required_world_tags": (
                "stock-map",
                "high-geometry",
                "lightmap",
                "fog-heavy",
                "visibility",
            ),
            "require_material_proof": True,
            "required_material_tags": (
                "shader-heavy",
                "material-stage",
                "tcgen-lightmap",
                "tcgen-environment",
                "tcgen-fog",
            ),
            "required_material_stream_features": (
                "multitexture",
                "depthFragment",
                "texMod",
                "environment",
            ),
            "required_material_stream_guards": (
                "dynamicLight",
                "screenMap",
                "videoMap",
            ),
            "forbidden_material_stream_features": (
                "dynamicLight",
                "screenMap",
                "videoMap",
            ),
            "required_material_tcgens": (
                "texture",
                "lightmap",
                "environment",
                "fog",
            ),
            "require_dynamic_proof": True,
            "required_dynamic_tags": (
                "dynamic-entity",
                "weapon-model",
                "dynamic-light",
                "planar-shadow",
            ),
            "required_dynamic_categories": (
                "entity",
                "weapon",
            ),
            "required_dynamic_stream_features": (
                "shadow",
            ),
            "required_dynamic_support": (
                "dynamicEntities",
                "sprites",
                "dynamicLights",
                "stencilShadows",
            ),
            "required_dynamic_stream_guards": (
                "dynamicLight",
            ),
            "forbidden_dynamic_stream_features": (
                "dynamicLight",
            ),
            "require_post_proof": True,
            "required_post_tags": (
                "greyscale-proof",
                "render-scale-proof",
            ),
            "required_post_features": (
                "greyscale",
                "renderScale",
            ),
        },
    },
    "rc-stress": {
        "description": "Developer stress gate for compact static-world MDI command uploads before promoting advanced GLx defaults.",
        "defaults": {
            "profile": "glx-stress",
            "corpus_scenes": corpus_scene_ids_csv(GLX_GATE_CORPUS_SCENES["rc-stress"]),
            "maps": corpus_targets_csv(GLX_GATE_CORPUS_SCENES["rc-stress"], "map"),
            "demos": corpus_targets_csv(GLX_GATE_CORPUS_SCENES["rc-stress"], "demo"),
            "renderers": "opengl,glx",
            "switch_sequence": "opengl,glx",
            "switch_rounds": 1,
            "timeout": 360.0,
        },
        "requirements": {
            "require_proof_corpus": True,
            "required_corpus_tags": (
                "stock-map",
                "modern-map",
                "high-geometry",
                "shader-heavy",
                "fog-heavy",
                "color-grade-proof",
                "tone-map-proof",
                "particle-heavy-demo",
                "ui-hud-sensitive",
                "screenshot-parity",
                "demo-playback-parity",
                "hud-parity",
                "shadow-parity",
                "bloom-parity",
                "cel-shading-parity",
                "outline-parity",
                "material-stage",
                "dynamic-entity",
                "weapon-model",
                "particle",
                "transient-poly",
                "mark-decal",
                "beam",
                "dynamic-light",
                "planar-shadow",
                "greyscale-proof",
                "render-scale-proof",
                "animated-image",
                "tcgen-lightmap",
                "tcgen-environment",
                "tcgen-fog",
                "tcgen-vector",
                "screen-map",
                "video-map",
                "performance-comparison",
            ),
            "required_parity_suites": GLX_GATE_PARITY_SUITES["rc-stress"],
            "require_screenshots": True,
            "require_timedemo_metrics": True,
            "screenshot_max_rms": 2.0,
            "screenshot_max_pixel_ratio": 0.005,
            "require_renderer_switch_lifecycle": True,
            "require_renderer_switch_roundtrip": False,
            "require_glx_diagnostics": True,
            "require_glx_performance_samples": True,
            "require_world_proof": True,
            "required_world_tags": (
                "stock-map",
                "modern-map",
                "high-geometry",
                "lightmap",
                "fog-heavy",
                "visibility",
            ),
            "require_material_proof": True,
            "required_material_tags": (
                "shader-heavy",
                "material-stage",
                "animated-image",
                "tcgen-lightmap",
                "tcgen-environment",
                "tcgen-fog",
                "tcgen-vector",
                "screen-map",
                "video-map",
            ),
            "required_material_stage_flags": (
                "animatedImage",
                "screenMap",
                "videoMap",
            ),
            "required_material_stream_features": (
                "multitexture",
                "depthFragment",
                "texMod",
                "environment",
                "screenMap",
                "videoMap",
            ),
            "required_material_stream_guards": (
                "dynamicLight",
                "screenMap",
                "videoMap",
            ),
            "required_material_tcgens": (
                "texture",
                "lightmap",
                "environment",
                "fog",
                "vector",
            ),
            "require_dynamic_proof": True,
            "required_dynamic_tags": (
                "dynamic-entity",
                "weapon-model",
                "particle",
                "transient-poly",
                "mark-decal",
                "beam",
                "dynamic-light",
                "planar-shadow",
            ),
            "required_dynamic_categories": (
                "entity",
                "particle",
                "poly",
                "mark",
                "weapon",
                "beam",
            ),
            "required_dynamic_stream_features": (
                "shadow",
                "beam",
            ),
            "required_dynamic_support": (
                "dynamicEntities",
                "sprites",
                "beams",
                "dynamicLights",
                "stencilShadows",
            ),
            "required_dynamic_stream_guards": (
                "dynamicLight",
            ),
            "forbidden_dynamic_stream_features": (
                "dynamicLight",
            ),
            "require_post_proof": True,
            "required_post_tags": (
                "greyscale-proof",
                "render-scale-proof",
            ),
            "required_post_features": (
                "greyscale",
                "renderScale",
            ),
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
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="Print exact GLx sweep cvar profiles and exit.",
    )
    parser.add_argument(
        "--list-corpus",
        action="store_true",
        help="Print the official GLx proof corpus scene ids and exit.",
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
        "--corpus-scenes",
        default=None,
        help=(
            "Comma-separated GLx proof corpus scene ids. Named gates use this "
            "to derive maps and demos unless --maps or --demos are explicit."
        ),
    )
    parser.add_argument(
        "--color-sweep",
        action="store_true",
        default=None,
        help="Run the P0 GLx color-contract sweep matrix as separate GLx launches.",
    )
    parser.add_argument(
        "--no-color-sweep",
        action="store_true",
        help="Disable a color sweep requested by a gate preset.",
    )
    parser.add_argument(
        "--write-image-evidence",
        action="store_true",
        help=(
            "Write deterministic offline shader-reference ramp PNGs plus histogram, "
            "luma false-color, and exposure false-color sidecars."
        ),
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
        "--proof-dir",
        type=Path,
        help=(
            "Directory containing approved proof inputs. When set, defaults screenshot "
            "baselines to <dir>/screenshots, the performance baseline to "
            "<dir>/performance-baseline.json, screenshot diffs to the run artifacts, "
            "and the summary to summary.md."
        ),
    )
    parser.add_argument(
        "--proof-platform",
        help=(
            "Stable runtime proof platform id to write into the manifest, such as "
            "windows-x64 or linux-x86_64. Defaults to the current host platform."
        ),
    )
    parser.add_argument(
        "--approve-proof",
        action="store_true",
        help=(
            "Refresh both screenshot and performance proof baselines under --proof-dir. "
            "Use only during deliberate reviewed baseline approval runs."
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
            f"counter metrics. Defaults to {DEFAULT_PERFORMANCE_MAX_GROWTH_RATIO * 100:.0f} percent."
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
        corpus_scene_ids = split_csv(str(defaults.get("corpus_scenes") or ""))
        print(f"  {name}: {preset['description']}")
        print(
            "    "
            f"profile={defaults['profile']} startup={startup_profile} maps={defaults['maps']} "
            f"demos={defaults['demos'] or '-'} "
            f"switch={defaults['switch_sequence'] or defaults['renderers']}"
        )
        if corpus_scene_ids:
            print(
                "    "
                f"corpus={GLX_PROOF_CORPUS_VERSION} "
                f"scenes={','.join(corpus_scene_ids)} "
                f"tags={','.join(corpus_tags(corpus_scene_ids))}"
            )
        parity_suite_ids = validate_parity_suite_ids(
            requirements.get("required_parity_suites", ())  # type: ignore[union-attr]
        )
        if parity_suite_ids:
            print(
                "    "
                f"parity-suites={GLX_PARITY_SUITE_VERSION} "
                f"suites={','.join(parity_suite_ids)}"
            )
        if "min_timedemo_fps_ratio" in requirements:
            print(
                "    "
                f"timedemo floor: {requirements['candidate_renderer']} >= "
                f"{requirements['min_timedemo_fps_ratio']:.0%} of "
                f"{requirements['baseline_renderer']}"
            )


def print_corpus_list() -> None:
    print(f"GLx proof corpus: {GLX_PROOF_CORPUS_VERSION}")
    print(f"Document: {GLX_PROOF_CORPUS_DOC}")
    print(f"Parity suite version: {GLX_PARITY_SUITE_VERSION}")
    print("Scenes:")
    for scene_id, scene in sorted(GLX_PROOF_CORPUS_SCENES.items()):
        print(
            "  "
            f"{scene_id}: kind={scene['kind']} target={scene['target']} "
            f"assetTier={scene['assetTier']} tags={','.join(scene.get('tags', ())) }"
        )
    print("Parity suites:")
    for suite_id, suite in sorted(GLX_PARITY_SUITES.items()):
        scene_ids = validate_corpus_scene_ids(suite.get("sceneIds", ()))
        tags = [str(tag) for tag in suite.get("requiredTags", ()) if str(tag).strip()]
        cvars = dict(suite.get("cvars", {}))
        cvar_text = ",".join(f"{name}={value}" for name, value in sorted(cvars.items()))
        print(
            "  "
            f"{suite_id}: artifact={suite['artifact']} scenes={','.join(scene_ids)} "
            f"tags={','.join(tags)} cvars={cvar_text or '-'}"
        )


def print_profile_list() -> None:
    print("Available GLx sweep profiles:")
    for name in sorted(PROFILE_CVARS):
        profile = PROFILE_CVARS[name]
        startup_profile = profile.get("r_glxProfile", "manual")
        print(f"  {name}: startup={startup_profile}")
        if not profile:
            print("    (no profile cvars)")
            continue
        for cvar_name in sorted(profile):
            print(f"    {cvar_name}={profile[cvar_name]}")


def apply_gate_defaults(args: argparse.Namespace) -> None:
    options = dict(DEFAULT_OPTIONS)
    if args.gate:
        options.update(RC_GATE_PRESETS[args.gate]["defaults"])  # type: ignore[arg-type]

    for name, value in options.items():
        if getattr(args, name) is None:
            setattr(args, name, value)
    if getattr(args, "no_color_sweep", False):
        args.color_sweep = False


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def sanitize(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return value.strip("._-") or "item"


def qpath_token(value: str, max_length: int) -> str:
    token = sanitize(value).lower()
    if len(token) > max_length:
        token = token[:max_length].rstrip("._-")
    return token or "x"


def runtime_token(run_id: str) -> str:
    return "gs" + hashlib.sha1(run_id.encode("utf-8")).hexdigest()[:8]


def validate_runtime_qpath(name: str) -> str:
    if len(name) >= Q3_MAX_QPATH:
        raise ValueError(
            f"Generated runtime qpath '{name}' is {len(name)} characters; "
            f"Quake III paths must stay below {Q3_MAX_QPATH}."
        )
    return name


def q3_path(path: Path) -> str:
    return path.resolve().as_posix()


def q3_quote(value: object) -> str:
    text = str(value).replace("\\", "/").replace('"', '\\"')
    return f'"{text}"'


def command_to_string(command: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(command)
    return " ".join(subprocess.list2cmdline([part]) for part in command)


def candidate_exe_names() -> list[str]:
    machine = platform.machine().lower()
    if os.name == "nt":
        if machine in {"amd64", "x86_64"}:
            arch_suffixes = ["x64", "x86_64"]
        elif machine in {"arm64", "aarch64"}:
            arch_suffixes = ["arm64", "aarch64"]
        elif machine in {"x86", "i386", "i686"}:
            arch_suffixes = ["x86"]
        else:
            arch_suffixes = [machine]
        names = [f"fnquake3.{arch}.exe" for arch in arch_suffixes]
        names.append("fnquake3.exe")
        return names

    if machine in {"amd64", "x86_64"}:
        arch_suffixes = ["x86_64", "x64"]
    elif machine in {"arm64", "aarch64"}:
        arch_suffixes = ["aarch64", "arm64"]
    elif machine.startswith("arm"):
        arch_suffixes = ["arm"]
    elif machine in {"ppc64le", "ppc64"}:
        arch_suffixes = [machine]
    else:
        arch_suffixes = [machine]
    return [f"fnquake3.{arch}" for arch in arch_suffixes] + ["fnquake3"]


def resolve_exe(explicit: Path | None, allow_missing: bool = False) -> Path:
    if explicit:
        exe = explicit.resolve()
        if not exe.exists() and not allow_missing:
            raise FileNotFoundError(f"Executable does not exist: {exe}")
        return exe

    names = candidate_exe_names()

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


def apply_proof_defaults(args: argparse.Namespace, output_root: Path) -> None:
    if args.approve_proof and args.proof_dir is None:
        raise ValueError("--approve-proof requires --proof-dir.")

    proof_dir = args.proof_dir.resolve() if args.proof_dir else None
    if args.approve_proof:
        args.approve_screenshot_baselines = True
        args.approve_performance_baseline = True

    if proof_dir is None:
        return

    if args.screenshot_baseline_dir is None:
        args.screenshot_baseline_dir = proof_dir / "screenshots"
    if args.screenshot_diff_dir is None and not args.approve_screenshot_baselines:
        args.screenshot_diff_dir = output_root / "screenshot-diffs"
    if args.performance_baseline is None:
        args.performance_baseline = proof_dir / "performance-baseline.json"
    if args.summary_markdown is None:
        args.summary_markdown = output_root / "summary.md"


def validate_proof_approval_mode(args: argparse.Namespace) -> None:
    if args.gate != "rc-proof":
        return
    if not (
        args.approve_proof or
        args.approve_screenshot_baselines or
        args.approve_performance_baseline
    ):
        return
    raise ValueError(
        "--gate rc-proof compares reviewed baselines; approve refreshed proof "
        "baselines in a separate rc-parity run."
    )


def make_cvars(args: argparse.Namespace) -> dict[str, str]:
    cvars = dict(COMMON_CVARS)
    cvars["r_customWidth"] = str(args.width)
    cvars["r_customHeight"] = str(args.height)
    cvars.update(PROFILE_CVARS[args.profile])
    if args.gate and RC_GATE_PRESETS[args.gate]["requirements"].get("require_glx_diagnostics"):  # type: ignore[index]
        cvars["r_glxColorPipelineDebug"] = "2"
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


def map_load_command(args: argparse.Namespace, map_name: str) -> str:
    command = "map" if getattr(args, "no_perf_samples", False) else "devmap"
    return f"{command} {map_name}"


def build_switch_cfg(
    args: argparse.Namespace,
    cvars: dict[str, str],
    maps: list[str],
    switch_sequence: list[str],
    run_id: str,
    qpath_run_token: str,
    corpus_scene_ids: Iterable[str] = (),
    parity_suite_ids: Iterable[str] = (),
) -> tuple[str, list[dict[str, object]]]:
    lines = cfg_preamble(cvars, "renderer switch screenshot sweep")
    expected_shots: list[dict[str, object]] = []
    selected_corpus_scene_ids = validate_corpus_scene_ids(corpus_scene_ids)
    selected_parity_suite_ids = validate_parity_suite_ids(parity_suite_ids)
    selected_parity_cvar_names = {
        str(cvar_name)
        for suite_id in selected_parity_suite_ids
        for cvar_name in dict(GLX_PARITY_SUITES[suite_id].get("cvars", {}))
        if str(cvar_name).strip()
    }

    lines.append(f"wait {args.startup_wait}")
    for map_index, map_name in enumerate(maps, start=1):
        safe_map = sanitize(map_name)
        shot_map = qpath_token(map_name, 12)
        map_corpus_scene_ids = corpus_scene_ids_for_target(
            selected_corpus_scene_ids,
            "map",
            map_name,
        )
        map_parity_suite_ids = parity_suite_ids_for_scene_ids(
            map_corpus_scene_ids,
            selected_parity_suite_ids,
        )
        map_parity_cvars = parity_suite_cvars_for_scene_ids(
            map_corpus_scene_ids,
            selected_parity_suite_ids,
        )
        if selected_parity_cvar_names:
            for cvar_name, cvar_value in sorted(GLX_PARITY_CVAR_DEFAULTS.items()):
                if cvar_name in selected_parity_cvar_names:
                    lines.append(f"set {cvar_name} \"{cvar_value}\"")
            for cvar_name, cvar_value in sorted(map_parity_cvars.items()):
                lines.append(f"set {cvar_name} \"{cvar_value}\"")
        lines.append(map_load_command(args, map_name))
        lines.append(f"wait {args.map_wait}")

        for round_index in range(1, args.switch_rounds + 1):
            for switch_index, renderer in enumerate(switch_sequence, start=1):
                safe_renderer = sanitize(renderer)
                shot_name = validate_runtime_qpath(
                    f"{qpath_run_token}-m{map_index}{shot_map}-"
                    f"r{round_index}s{switch_index}-{qpath_token(safe_renderer, 8)}"
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
                        "corpusSceneIds": map_corpus_scene_ids,
                        "corpusTags": corpus_tags(map_corpus_scene_ids),
                        "paritySuiteIds": map_parity_suite_ids,
                        "parityCvars": map_parity_cvars,
                    }
                )

        lines.append("disconnect")
        lines.append("wait 30")

    lines.append("quit")
    lines.append("")
    return "\n".join(lines), expected_shots


def build_color_sweep_cfg(
    args: argparse.Namespace,
    cvars: dict[str, str],
    map_name: str,
    row: dict[str, object],
    run_id: str,
    qpath_run_token: str,
    row_index: int,
) -> tuple[str, list[dict[str, object]]]:
    row_id = str(row["id"])
    safe_row = sanitize(row_id)
    safe_map = sanitize(map_name)
    shot_name = validate_runtime_qpath(
        f"{qpath_run_token}-c{row_index:02d}-{qpath_token(safe_map, 12)}"
    )
    baseline_key = f"glx-color-{safe_row}-{safe_map}"
    lines = cfg_preamble(cvars, f"GLx color sweep {row_id}")
    lines.extend(
        [
            f"wait {args.startup_wait}",
            map_load_command(args, map_name),
            f"wait {args.map_wait}",
        ]
    )
    if not args.no_perf_samples:
        lines.extend(["set r_speeds \"7\"", f"wait {args.perf_sample_wait}"])
    lines.extend([f"screenshotPNG {shot_name}", f"wait {args.screenshot_wait}"])
    if not args.no_perf_samples:
        lines.extend(["set r_speeds \"0\"", "wait 1"])
    lines.extend(glx_diagnostic_commands())
    lines.extend(["wait 1", "quit", ""])
    return "\n".join(lines), [
        {
            "name": shot_name,
            "baselineKey": baseline_key,
            "renderer": "glx",
            "map": map_name,
            "colorSweepRowId": row_id,
            "colorSweepProbe": row.get("probe", ""),
        }
    ]


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

    if "logfile" not in startup_cvars:
        command.extend(["+set", "logfile", "2"])
    if "developer" not in startup_cvars:
        command.extend(["+set", "developer", "1"])

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


def engine_console_log_path(homepath: Path, fs_game: str) -> Path:
    return homepath / game_dir(fs_game) / "qconsole.log"


def merge_engine_output(stdout: str, engine_log_path: Path | None) -> str:
    if engine_log_path is None or not engine_log_path.exists():
        return stdout

    engine_output = engine_log_path.read_text(encoding="utf-8", errors="replace")
    if not stdout:
        return engine_output
    if not engine_output:
        return stdout
    return stdout.rstrip() + "\n\n--- qconsole.log ---\n" + engine_output


def run_engine(
    command: list[str],
    cwd: Path,
    timeout: float,
    log_path: Path,
    dry_run: bool,
    engine_log_path: Path | None = None,
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

    if engine_log_path is not None:
        try:
            engine_log_path.unlink(missing_ok=True)
        except OSError:
            pass

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
        output = merge_engine_output(completed.stdout or "", engine_log_path)
        log_path.write_text(output, encoding="utf-8")
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
        output = merge_engine_output(output, engine_log_path)
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


def png_luma_histogram(path: Path) -> dict[str, object]:
    width, height, pixels = read_png_rgba(path)
    luma_histogram = [0] * 256
    red_histogram = [0] * 256
    green_histogram = [0] * 256
    blue_histogram = [0] * 256
    pixel_count = width * height
    total_luma = 0
    total_red = 0
    total_green = 0
    total_blue = 0

    for offset in range(0, len(pixels), 4):
        r, g, b = pixels[offset], pixels[offset + 1], pixels[offset + 2]
        luma = int(round(0.2126 * r + 0.7152 * g + 0.0722 * b))
        luma = max(0, min(255, luma))
        luma_histogram[luma] += 1
        red_histogram[r] += 1
        green_histogram[g] += 1
        blue_histogram[b] += 1
        total_luma += luma
        total_red += r
        total_green += g
        total_blue += b

    def percentile_value(histogram: list[int], percentile: float) -> int:
        target = max(1, int(round(pixel_count * percentile)))
        seen = 0
        for value, count in enumerate(histogram):
            seen += count
            if seen >= target:
                return value
        return 255

    clipped_black = luma_histogram[0]
    clipped_white = luma_histogram[255]
    histogram_payload = json.dumps(
        {
            "luma": luma_histogram,
            "red": red_histogram,
            "green": green_histogram,
            "blue": blue_histogram,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "status": "passed",
        "width": width,
        "height": height,
        "pixels": pixel_count,
        "histogramHash": hashlib.sha256(histogram_payload).hexdigest()[:16],
        "meanLuma": round(total_luma / pixel_count, 3) if pixel_count else 0.0,
        "meanRed": round(total_red / pixel_count, 3) if pixel_count else 0.0,
        "meanGreen": round(total_green / pixel_count, 3) if pixel_count else 0.0,
        "meanBlue": round(total_blue / pixel_count, 3) if pixel_count else 0.0,
        "p01Luma": percentile_value(luma_histogram, 0.01),
        "p50Luma": percentile_value(luma_histogram, 0.50),
        "p99Luma": percentile_value(luma_histogram, 0.99),
        "p50Red": percentile_value(red_histogram, 0.50),
        "p50Green": percentile_value(green_histogram, 0.50),
        "p50Blue": percentile_value(blue_histogram, 0.50),
        "clippedBlackRatio": round(clipped_black / pixel_count, 6) if pixel_count else 0.0,
        "clippedWhiteRatio": round(clipped_white / pixel_count, 6) if pixel_count else 0.0,
    }


def false_color_luma_rgb(luma: int) -> tuple[int, int, int]:
    value = max(0, min(255, luma)) / 255.0
    if value < 0.25:
        t = value / 0.25
        return 0, int(round(255 * t)), 255
    if value < 0.5:
        t = (value - 0.25) / 0.25
        return 0, 255, int(round(255 * (1.0 - t)))
    if value < 0.75:
        t = (value - 0.5) / 0.25
        return int(round(255 * t)), 255, 0
    t = (value - 0.75) / 0.25
    return 255, int(round(255 * (1.0 - t))), 0


def false_color_exposure_rgb(luma: int) -> tuple[int, int, int]:
    value = max(1, min(255, luma))
    stops = max(-4.0, min(4.0, math.log2(value / 128.0)))
    if stops < -2.0:
        t = (stops + 4.0) / 2.0
        return 0, int(round(96 * t)), int(round(192 + 63 * t))
    if stops < 0.0:
        t = (stops + 2.0) / 2.0
        return int(round(96 * t)), int(round(96 + 64 * t)), 255
    if stops < 2.0:
        t = stops / 2.0
        return int(round(128 + 127 * t)), int(round(128 + 96 * t)), int(round(128 * (1.0 - t)))
    t = (stops - 2.0) / 2.0
    return 255, int(round(224 * (1.0 - t))), 0


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


def write_luma_false_color_png(source_path: Path, output_path: Path) -> None:
    width, height, pixels = read_png_rgba(source_path)
    out = bytearray(width * height * 4)
    for offset in range(0, len(pixels), 4):
        r, g, b, a = pixels[offset], pixels[offset + 1], pixels[offset + 2], pixels[offset + 3]
        luma = int(round(0.2126 * r + 0.7152 * g + 0.0722 * b))
        false_r, false_g, false_b = false_color_luma_rgb(luma)
        out[offset:offset + 4] = bytes((false_r, false_g, false_b, a))
    write_png_rgba(output_path, width, height, bytes(out))


def write_exposure_false_color_png(source_path: Path, output_path: Path) -> None:
    width, height, pixels = read_png_rgba(source_path)
    out = bytearray(width * height * 4)
    for offset in range(0, len(pixels), 4):
        r, g, b, a = pixels[offset], pixels[offset + 1], pixels[offset + 2], pixels[offset + 3]
        luma = int(round(0.2126 * r + 0.7152 * g + 0.0722 * b))
        false_r, false_g, false_b = false_color_exposure_rgb(luma)
        out[offset:offset + 4] = bytes((false_r, false_g, false_b, a))
    write_png_rgba(output_path, width, height, bytes(out))


def rgba_psnr(squared_error: int, channel_count: int) -> float | str:
    if channel_count <= 0:
        return 0.0
    if squared_error == 0:
        return "inf"
    mse = squared_error / channel_count
    return round(20.0 * math.log10(255.0 / math.sqrt(mse)), 6)


def rgba_luma_ssim(width: int, height: int, baseline_pixels: bytes, candidate_pixels: bytes) -> float:
    pixel_count = width * height
    if pixel_count <= 0:
        return 1.0

    base_luma: list[float] = []
    candidate_luma: list[float] = []
    for offset in range(0, len(baseline_pixels), 4):
        br, bg, bb = baseline_pixels[offset], baseline_pixels[offset + 1], baseline_pixels[offset + 2]
        cr, cg, cb = candidate_pixels[offset], candidate_pixels[offset + 1], candidate_pixels[offset + 2]
        base_luma.append(0.2126 * br + 0.7152 * bg + 0.0722 * bb)
        candidate_luma.append(0.2126 * cr + 0.7152 * cg + 0.0722 * cb)

    mean_base = sum(base_luma) / pixel_count
    mean_candidate = sum(candidate_luma) / pixel_count
    variance_base = sum((value - mean_base) ** 2 for value in base_luma) / pixel_count
    variance_candidate = sum((value - mean_candidate) ** 2 for value in candidate_luma) / pixel_count
    covariance = sum(
        (base_luma[index] - mean_base) * (candidate_luma[index] - mean_candidate)
        for index in range(pixel_count)
    ) / pixel_count
    c1 = (0.01 * 255.0) ** 2
    c2 = (0.03 * 255.0) ** 2
    denominator = (mean_base ** 2 + mean_candidate ** 2 + c1) * (
        variance_base + variance_candidate + c2
    )
    if denominator <= 0.0:
        return 1.0
    ssim = ((2.0 * mean_base * mean_candidate + c1) * (2.0 * covariance + c2)) / denominator
    return round(max(-1.0, min(1.0, ssim)), 6)


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def srgb_encode_linear(value: float) -> float:
    value = clamp01(value)
    if value <= 0.0031308:
        return 12.92 * value
    return 1.055 * (value ** (1.0 / 2.4)) - 0.055


def aces_fitted(value: float) -> float:
    value = max(0.0, value)
    return clamp01((value * (2.51 * value + 0.03)) / (value * (2.43 * value + 0.59) + 0.14))


def reference_tonemap(value: float, tone_map: str) -> float:
    if tone_map == "reinhard-simple":
        value = max(0.0, value)
        return value / (1.0 + value)
    if tone_map == "aces-fitted":
        return aces_fitted(value)
    return clamp01(value)


def reference_ramp_source_rgb(x: int, y: int, width: int, height: int) -> tuple[float, float, float]:
    del height
    t = x / max(1, width - 1)
    row = y * len(GLX_SHADER_REFERENCE_RAMP_ROWS) // GLX_SHADER_REFERENCE_RAMP_HEIGHT
    row = max(0, min(len(GLX_SHADER_REFERENCE_RAMP_ROWS) - 1, row))
    row_id = GLX_SHADER_REFERENCE_RAMP_ROWS[row]
    if row_id == "linear-step-wedge":
        step = math.floor(t * 16.0) / 15.0
        return step, step, step
    if row_id == "saturated-primaries":
        segment = int(t * 6.0)
        local = (t * 6.0) - segment
        primaries = (
            (1.0, local, 0.0),
            (1.0 - local, 1.0, 0.0),
            (0.0, 1.0, local),
            (0.0, 1.0 - local, 1.0),
            (local, 0.0, 1.0),
            (1.0, 0.0, 1.0 - local),
        )
        return primaries[min(segment, len(primaries) - 1)]
    if row_id == "hdr-highlight-ramp":
        value = t * 4.0
        return value, value * 0.75, value * 0.5
    return t, t, t


def reference_transform_rgb(rgb: tuple[float, float, float], row: dict[str, object]) -> tuple[int, int, int]:
    expect = row.get("expect", {}) if isinstance(row.get("expect"), dict) else {}
    exposure = float(expect.get("exposure", 1.0)) if isinstance(expect.get("exposure", 1.0), (int, float)) else 1.0
    tone_map = str(expect.get("toneMap", "legacy"))
    final_encode = str(expect.get("finalEncode", "none"))
    out: list[int] = []
    for channel in rgb:
        value = reference_tonemap(channel * exposure, tone_map)
        if final_encode == "shader-srgb":
            value = srgb_encode_linear(value)
        out.append(int(round(clamp01(value) * 255.0)))
    return out[0], out[1], out[2]


def shader_reference_ramp_pixels(row: dict[str, object]) -> bytes:
    width = GLX_SHADER_REFERENCE_RAMP_WIDTH
    height = GLX_SHADER_REFERENCE_RAMP_HEIGHT
    pixels = bytearray(width * height * 4)
    for y in range(height):
        for x in range(width):
            r, g, b = reference_transform_rgb(reference_ramp_source_rgb(x, y, width, height), row)
            offset = (y * width + x) * 4
            pixels[offset:offset + 4] = bytes((r, g, b, 255))
    return bytes(pixels)


def write_shader_reference_ramp(output_dir: Path, row: dict[str, object]) -> dict[str, object]:
    row_id = str(row["id"])
    path = output_dir / f"{sanitize(row_id)}.reference-ramp.png"
    write_png_rgba(
        path,
        GLX_SHADER_REFERENCE_RAMP_WIDTH,
        GLX_SHADER_REFERENCE_RAMP_HEIGHT,
        shader_reference_ramp_pixels(row),
    )
    histogram_path = path.with_name(f"{path.stem}.histogram.json")
    luma_path = path.with_name(f"{path.stem}.luma-falsecolor.png")
    exposure_path = path.with_name(f"{path.stem}.exposure-falsecolor.png")
    histogram = png_luma_histogram(path)
    histogram_path.write_text(json.dumps(histogram, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_luma_false_color_png(path, luma_path)
    write_exposure_false_color_png(path, exposure_path)
    return {
        "rowId": row_id,
        "path": str(path),
        "width": GLX_SHADER_REFERENCE_RAMP_WIDTH,
        "height": GLX_SHADER_REFERENCE_RAMP_HEIGHT,
        "rampRows": list(GLX_SHADER_REFERENCE_RAMP_ROWS),
        "histogram": histogram,
        "histogramPath": str(histogram_path),
        "falseColorPath": str(luma_path),
        "exposureFalseColorPath": str(exposure_path),
    }


def write_shader_reference_ramps(output_dir: Path) -> list[dict[str, object]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    return [write_shader_reference_ramp(output_dir, row) for row in GLX_COLOR_SWEEP_MATRIX]


def color_sweep_row_by_id(row_id: str) -> dict[str, object]:
    for row in GLX_COLOR_SWEEP_MATRIX:
        if str(row["id"]) == row_id:
            return dict(row)
    raise ValueError(f"Unknown GLx color sweep row id: {row_id}")


def compare_shader_reference_ramp(
    row_id: str,
    shader_capture_path: Path,
    output_dir: Path,
    max_rms: float = 1.0,
    max_pixel_ratio: float = 0.01,
) -> dict[str, object]:
    reference = write_shader_reference_ramp(output_dir, color_sweep_row_by_id(row_id))
    diff_path = output_dir / f"{sanitize(row_id)}.shader-vs-reference.diff.png"
    comparison = compare_png_files(
        Path(str(reference["path"])),
        shader_capture_path,
        max_rms,
        max_pixel_ratio,
        diff_path,
    )
    return {
        "rowId": row_id,
        "status": comparison.get("status", "failed"),
        "reference": reference,
        "shaderCapturePath": str(shader_capture_path),
        "comparison": comparison,
    }


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
        "psnr": rgba_psnr(squared_error, channel_count),
        "ssim": rgba_luma_ssim(width, height, baseline_pixels, candidate_pixels),
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
                "capturePolicy": dict(GLX_SCREENSHOT_CAPTURE_POLICY_CONTRACT),
            }
        )
        if path.exists():
            histogram_path = path.with_name(f"{path.stem}.histogram.json")
            false_color_path = path.with_name(f"{path.stem}.luma-falsecolor.png")
            exposure_false_color_path = path.with_name(f"{path.stem}.exposure-falsecolor.png")
            try:
                histogram = png_luma_histogram(path)
                result["histogram"] = histogram
                histogram_path.write_text(
                    json.dumps(histogram, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                result["histogramPath"] = str(histogram_path)
            except Exception as exc:
                result["histogram"] = {"status": "failed", "reason": str(exc)}
            try:
                write_luma_false_color_png(path, false_color_path)
                result["falseColor"] = {"status": "passed"}
                result["falseColorPath"] = str(false_color_path)
            except Exception as exc:
                result["falseColor"] = {"status": "failed", "reason": str(exc)}
            try:
                write_exposure_false_color_png(path, exposure_false_color_path)
                result["exposureFalseColor"] = {"status": "passed"}
                result["exposureFalseColorPath"] = str(exposure_false_color_path)
            except Exception as exc:
                result["exposureFalseColor"] = {"status": "failed", "reason": str(exc)}
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
    return profile in {"glx-parity", "glx-ownership", "glx-stress", "glx-material"}


def profile_requires_glx_ownership(profile: str) -> bool:
    return profile in {"glx-ownership", "glx-final"}


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


def int_group_any(match: re.Match[str], *names: str) -> int:
    for name in names:
        value = match.group(name)
        if value is not None:
            return int(value)
    raise KeyError(names)


def normalize_color_frame_payload(payload: dict[str, object]) -> dict[str, object]:
    normalized = dict(payload)
    for key in ("backend", "space", "transfer"):
        if key in normalized:
            normalized[key] = str(normalized[key]).strip().lower()
    for key in ("internalFormat", "textureFormat", "textureType"):
        if key in normalized:
            try:
                normalized[key] = normalized_hex(normalized[key])
            except (TypeError, ValueError):
                normalized[key] = str(normalized[key]).strip().lower()
    return normalized


def color_frame_payload_from_csv(match: re.Match[str]) -> dict[str, object]:
    return normalize_color_frame_payload(
        {
            "frame": int_group(match, "frame"),
            "backend": match.group("backend"),
            "space": match.group("space"),
            "transfer": match.group("transfer"),
            "exposure": float(match.group("exposure")),
            "paperWhiteNits": float(match.group("paperWhiteNits")),
            "maxOutputNits": float(match.group("maxOutputNits")),
            "srgbDecode": q3_bool(match.group("srgbDecode")),
            "framebufferSrgb": q3_bool(match.group("framebufferSrgb")),
            "internalFormat": match.group("internalFormat"),
            "textureFormat": match.group("textureFormat"),
            "textureType": match.group("textureType"),
            "sceneTargetFloat": q3_bool(match.group("sceneTargetFloat")),
            "shaderSrgbEncode": q3_bool(match.group("shaderSrgbEncode")),
            "contractValid": q3_bool(match.group("contractValid")),
        }
    )


def record_color_frame_diagnostics(
    metrics: dict[str, object],
    payload: dict[str, object],
    failures: list[str],
) -> None:
    normalized = normalize_color_frame_payload(payload)
    color_frames = metrics.setdefault("colorFrame", {})
    if isinstance(color_frames, dict):
        color_frames["samples"] = int(color_frames.get("samples", 0)) + 1
        color_frames["latest"] = normalized
    if normalized.get("contractValid") is False:
        failures.append("GLx color-frame reported an invalid output contract.")
    if (
        normalized.get("transfer") == GLX_SDR_OUTPUT_CONTRACT["transfer"]
        and float(normalized.get("maxOutputNits", 0.0)) >
        float(normalized.get("paperWhiteNits", GLX_SDR_OUTPUT_CONTRACT["paperWhiteNits"])) + 0.01
    ):
        failures.append(
            "GLx color-frame SDR output used HDR max-output headroom while hardware HDR is inactive."
        )


def record_color_frame_performance(
    performance: dict[str, object],
    payload: dict[str, object],
) -> None:
    normalized = normalize_color_frame_payload(payload)
    perf_record_numeric(performance, "colorFrameSamples", 1)
    for key, value in normalized.items():
        metric_key = f"colorFrame{key[0].upper()}{key[1:]}"
        if isinstance(value, bool):
            perf_record_numeric(performance, metric_key, 1 if value else 0)
        elif isinstance(value, (int, float)):
            perf_record_numeric(performance, metric_key, float(value))
        else:
            perf_record_string(performance, metric_key, str(value).lower())


def pass_schedule_valid_from_match(match: re.Match[str]) -> bool:
    return (
        match.group("valid").lower() == "valid"
        and int_group(match, "count") == GLX_EXPECTED_PASS_SCHEDULE_COUNT
        and match.group("hash").lower() == GLX_EXPECTED_PASS_SCHEDULE_HASH
        and match.group("order") == GLX_EXPECTED_PASS_SCHEDULE
    )


def pass_schedule_failure_from_values(valid: object, count: object, schedule_hash: object, order: object) -> str | None:
    if (
        valid == 1
        and count == GLX_EXPECTED_PASS_SCHEDULE_COUNT
        and schedule_hash == GLX_EXPECTED_PASS_SCHEDULE_HASH
        and order == GLX_EXPECTED_PASS_SCHEDULE
    ):
        return None
    return (
        "GLx pass schedule is not locked to the final contract: "
        f"valid {valid}, count {count}, hash {schedule_hash!r}, order {order!r}."
    )


def record_diagnostic_pass_schedule(
    metrics: dict[str, object],
    match: re.Match[str],
) -> None:
    valid = 1 if match.group("valid").lower() == "valid" else 0
    section = metric_section(metrics, "passSchedule")
    if valid != 1 and section.get("valid") == 1:
        return
    section["valid"] = valid
    section["count"] = int_group(match, "count")
    section["hash"] = match.group("hash").lower()
    section["order"] = match.group("order")


def product_tier_failure(tier: object) -> str | None:
    if isinstance(tier, str) and tier in GLX_PRODUCT_TIERS:
        return None
    return f"GLx product tier is not one of the final five tiers: {tier!r}."


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
    requires_glx_ownership = profile_requires_glx_ownership(profile)
    requires_tier_contract = profile != "glx-color"
    saw_ownership = False
    saw_stream_categories = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if (
            line.startswith("GLx ")
            or line.startswith("glx: ")
            or line.startswith("dynamic stream ")
            or line.startswith("static world ")
            or line.startswith("material ")
            or line.startswith("color pipeline")
            or line.startswith("color grade")
            or line.startswith("color audit")
            or line.startswith("texture audit")
            or line.startswith("color-frame-json")
            or line.startswith("color-frame-csv")
            or line.startswith("output backend")
            or line.startswith("display state")
            or line.startswith("target:")
            or line.startswith("product tier ")
            or line.startswith("capability hint ")
            or line.startswith("GL12 fixed-function ")
            or line.startswith("GL2X programmable ")
            or line.startswith("GL3X performance ")
            or line.startswith("GL41 mac-modern ")
            or line.startswith("GL46 high-end ")
        ):
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

        match = MATERIAL_COMPILER_PLANS_RE.search(line)
        if match:
            for key in ("compiled", "unsupported"):
                record_metric_max(metrics, "materialCompilerPlans", key, int_group(match, key))
            record_metric_max(
                metrics,
                "materialCompilerPlans",
                "lastUnsupported",
                int(match.group("lastUnsupported"), 16),
            )
            record_metric_max(
                metrics,
                "materialCompilerPlans",
                "lastUnsupportedReason",
                match.group("lastUnsupportedReason"),
            )
            if requires_glx_paths and int_group(match, "unsupported") > 0:
                failures.append(
                    "GLx material compiler unsupported plans: "
                    f"{int_group(match, 'unsupported')} "
                    f"({match.group('lastUnsupportedReason')})."
                )
            continue

        match = MATERIAL_PARAMETER_DETAIL_RE.search(line)
        if match:
            record_metric_max(metrics, "materialParameters", "blocks", int_group(match, "blocks"))
            record_metric_max(metrics, "materialParameters", "invalid", int_group(match, "invalid"))
            if match.group("hash") is not None:
                record_metric_max(metrics, "materialParameters", "hash", int(match.group("hash"), 16))
            record_metric_max(metrics, "materialParameters", "sort", int_group(match, "sort"))
            record_metric_max(metrics, "materialParameters", "passes", int_group(match, "passes"))
            record_metric_max(metrics, "materialParameters", "features", int(match.group("features"), 16))
            record_metric_max(metrics, "materialParameters", "flags", int(match.group("flags"), 16))
            record_metric_max(metrics, "materialParameters", "state", int(match.group("state"), 16))
            for key in ("rgbGen", "rgbWave", "alphaGen", "alphaWave", "tcGen0", "tcGen1"):
                if match.group(key) is not None:
                    record_metric_max(metrics, "materialParameters", key, int_group(match, key))
            if int_group(match, "invalid") > 0:
                failures.append(f"GLx material parameter blocks invalid: {int_group(match, 'invalid')}.")
            continue

        match = MATERIAL_PARAMETER_BLOCKS_RE.search(line)
        if match:
            record_metric_max(metrics, "materialParameters", "blocks", int_group(match, "blocks"))
            record_metric_max(metrics, "materialParameters", "invalid", int_group(match, "invalid"))
            if match.group("hash") is not None:
                record_metric_max(metrics, "materialParameters", "hash", int(match.group("hash"), 16))
            if int_group(match, "invalid") > 0:
                failures.append(f"GLx material parameter blocks invalid: {int_group(match, 'invalid')}.")
            continue

        match = MATERIAL_LAST_KEY_RE.search(line)
        if match:
            record_metric_max(metrics, "materialLastKey", "name", match.group("name").strip())
            record_metric_max(metrics, "materialLastKey", "flags", int(match.group("flags"), 16))
            record_metric_max(metrics, "materialLastKey", "state", int(match.group("state"), 16))
            for key in (
                "rgbGen",
                "rgbWave",
                "alphaGen",
                "alphaWave",
                "tcGen0",
                "tcGen1",
                "texMods0",
                "texMods1",
                "combine",
            ):
                record_metric_max(metrics, "materialLastKey", key, int_group(match, key))
            record_metric_max(metrics, "materialLastKey", "fogPass", 1 if q3_bool(match.group("fog")) else 0)
            continue

        match = MATERIAL_LAST_LANGUAGE_RE.search(line)
        if match:
            record_metric_max(metrics, "materialLanguage", "flags", int(match.group("flags"), 16))
            record_metric_max(metrics, "materialLanguage", "state", int(match.group("state"), 16))
            for key in (
                "texModMask0",
                "texModMask1",
                "texModSequence0",
                "texModSequence1",
                "texModWaveFuncs0",
                "texModWaveFuncs1",
            ):
                record_metric_max(metrics, "materialLanguage", key, int(match.group(key), 16))
            record_metric_max(metrics, "materialLanguage", "fogAdjust", int_group(match, "fogAdjust"))
            continue

        match = MATERIAL_FLAGS_COMMON_RE.search(line)
        if match:
            for key in (
                "multitexture",
                "depthFragment",
                "blend",
                "alphaTest",
                "depthWrite",
                "lightmap",
            ):
                record_metric_max(metrics, "materialStageFlags", key, int_group(match, key))
            continue

        match = MATERIAL_FLAGS_SPECIAL_RE.search(line)
        if match:
            for key in (
                "animatedImage",
                "videoMap",
                "screenMap",
                "dynamicLightMap",
                "texMod",
                "environment",
                "st0",
                "st1",
            ):
                record_metric_max(metrics, "materialStageFlags", key, int_group(match, key))
            continue

        match = OWNERSHIP_RE.search(line)
        if match:
            saw_ownership = True
            for key in ("calls", "items", "generic", "vboDevice", "vboSoft", "arrays"):
                record_metric_max(metrics, "ownership", key, int_group(match, key))
            if requires_glx_ownership and int_group(match, "calls") > 0:
                failures.append(
                    f"GLx legacy draw delegation is still active: "
                    f"{int_group(match, 'calls')} calls / {int_group(match, 'items')} items."
                )
            continue

        match = OWNERSHIP_INFO_RE.search(line)
        if match:
            saw_ownership = True
            for key in ("calls", "items"):
                record_metric_max(metrics, "ownership", key, int_group(match, key))
            if requires_glx_ownership and int_group(match, "calls") > 0:
                failures.append(
                    f"GLx legacy draw delegation is still active: "
                    f"{int_group(match, 'calls')} calls / {int_group(match, 'items')} items."
                )
            continue

        match = GLX_TIER_INFO_RE.search(line)
        if match:
            tier = match.group("tier")
            record_metric_max(metrics, "productTier", "tier", tier)
            failure = product_tier_failure(tier)
            if failure:
                failures.append(failure)
            continue

        match = GLX_GL12_EXECUTOR_RE.search(line)
        if match:
            for key in ("active", "clientMemoryDraws", "streamUploads", "materialCompiler", "modernPostChain"):
                record_metric_max(
                    metrics,
                    "gl12Executor",
                    key,
                    1 if q3_bool(match.group(key)) else 0,
                )
            continue

        match = GLX_GL12_SUPPORT_RE.search(line)
        if match:
            for key in (
                "lightmaps",
                "multitexture",
                "fog",
                "sprites",
                "beams",
                "dynamicLights",
                "stencilShadows",
                "screenshots",
                "demos",
            ):
                record_metric_max(
                    metrics,
                    "gl12Support",
                    key,
                    1 if q3_bool(match.group(key)) else 0,
                )
            continue

        match = GLX_GL2X_EXECUTOR_RE.search(line)
        if match:
            for key in (
                "active",
                "clientMemoryFallback",
                "streamUploads",
                "materialCompiler",
                "postprocessLite",
                "modernPostChain",
                "sceneLinearOutput",
            ):
                record_metric_max(
                    metrics,
                    "gl2xExecutor",
                    key,
                    1 if q3_bool(match.group(key)) else 0,
                )
            continue

        match = GLX_GL2X_SUPPORT_RE.search(line)
        if match:
            for key in (
                "commonMaterials",
                "dynamicEntities",
                "lightmaps",
                "multitexture",
                "fog",
                "sprites",
                "beams",
                "screenshots",
                "demos",
            ):
                record_metric_max(
                    metrics,
                    "gl2xSupport",
                    key,
                    1 if q3_bool(match.group(key)) else 0,
                )
            continue

        match = GLX_GL3X_EXECUTOR_RE.search(line)
        if match:
            for key in (
                "active",
                "fboPostProcess",
                "uboFrameObjectConstants",
                "timerQueries",
                "syncAwareUploads",
                "staticBufferOwnership",
                "dynamicBufferOwnership",
                "persistentUploads",
                "indirectSubmission",
                "directStateAccess",
            ):
                record_metric_max(
                    metrics,
                    "gl3xExecutor",
                    key,
                    1 if q3_bool(match.group(key)) else 0,
                )
            continue

        match = GLX_GL3X_SUPPORT_RE.search(line)
        if match:
            for key in (
                "materialCompiler",
                "commonMaterials",
                "dynamicEntities",
                "modernPostChain",
                "sceneLinearOutput",
                "screenshots",
                "demos",
            ):
                record_metric_max(
                    metrics,
                    "gl3xSupport",
                    key,
                    1 if q3_bool(match.group(key)) else 0,
                )
            continue

        match = GLX_GL41_EXECUTOR_RE.search(line)
        if match:
            for key in (
                "active",
                "fboPostProcess",
                "uboFrameObjectConstants",
                "timerQueries",
                "syncAwareUploads",
                "staticBufferOwnership",
                "dynamicBufferOwnership",
                "macOS41Ceiling",
            ):
                record_metric_max(
                    metrics,
                    "gl41Executor",
                    key,
                    1 if q3_bool(match.group(key)) else 0,
                )
            continue

        match = GLX_GL41_SUPPORT_RE.search(line)
        if match:
            for key in (
                "materialCompiler",
                "commonMaterials",
                "dynamicEntities",
                "modernPostChain",
                "sceneLinearOutput",
                "highQualitySdr",
                "optionalHardwareHdr",
                "screenshots",
                "demos",
            ):
                record_metric_max(
                    metrics,
                    "gl41Support",
                    key,
                    1 if q3_bool(match.group(key)) else 0,
                )
            continue

        match = GLX_GL41_LIMITS_RE.search(line)
        if match:
            for key in (
                "debugOutputRequired",
                "bufferStorageRequired",
                "directStateAccessRequired",
                "multiDrawIndirectRequired",
                "persistentUploadsRequired",
            ):
                record_metric_max(
                    metrics,
                    "gl41Limits",
                    key,
                    1 if q3_bool(match.group(key)) else 0,
                )
            continue

        match = GLX_GL46_EXECUTOR_RE.search(line)
        if match:
            for key in (
                "active",
                "persistentUploads",
                "bufferStorageUploads",
                "syncHeavyStreaming",
                "directStateAccess",
                "multiDrawIndirect",
                "aggressiveStaticWorldSubmission",
                "detailedGpuCounters",
            ):
                record_metric_max(
                    metrics,
                    "gl46Executor",
                    key,
                    1 if q3_bool(match.group(key)) else 0,
                )
            continue

        match = GLX_GL46_SUPPORT_RE.search(line)
        if match:
            for key in (
                "materialCompiler",
                "commonMaterials",
                "dynamicEntities",
                "modernPostChain",
                "sceneLinearOutput",
                "hardwareHdrOutput",
                "screenshots",
                "demos",
            ):
                record_metric_max(
                    metrics,
                    "gl46Support",
                    key,
                    1 if q3_bool(match.group(key)) else 0,
                )
            continue

        match = GLX_GL46_REQUIREMENTS_RE.search(line)
        if match:
            for key in (
                "debugOutputRequired",
                "bufferStorageRequired",
                "directStateAccessRequired",
                "multiDrawIndirectRequired",
            ):
                record_metric_max(
                    metrics,
                    "gl46Requirements",
                    key,
                    1 if q3_bool(match.group(key)) else 0,
                )
            continue

        match = GLX_PASS_SCHEDULE_RE.search(line)
        if match:
            record_diagnostic_pass_schedule(metrics, match)
            continue

        match = GLX_RENDER_IR_PRODUCTS_RE.search(line)
        if match:
            for key in (
                "passes",
                "worldPackets",
                "dynamicDraws",
                "materials",
                "uploads",
                "postNodes",
                "outputs",
                "rejects",
            ):
                record_metric_max(metrics, "renderIRProducts", key, int_group(match, key))
            continue

        match = GLX_POST_OUTPUT_OWNERSHIP_RE.search(line)
        if match:
            record_metric_max(metrics, "postOutputOwnership", "mode", match.group("mode").lower())
            record_metric_max(metrics, "postOutputOwnership", "postNodes", int_group(match, "postNodes"))
            record_metric_max(metrics, "postOutputOwnership", "outputs", int_group(match, "outputs"))
            record_metric_max(
                metrics,
                "postOutputOwnership",
                "legacyFallback",
                1 if q3_bool(match.group("legacyFallback")) else 0,
            )
            if match.group("executableNodes") is not None:
                record_metric_max(
                    metrics,
                    "postOutputOwnership",
                    "executableNodes",
                    int_group(match, "executableNodes"),
                )
            if match.group("executableOutputs") is not None:
                record_metric_max(
                    metrics,
                    "postOutputOwnership",
                    "executableOutputs",
                    int_group(match, "executableOutputs"),
                )
            if match.group("postHash") is not None:
                record_metric_max(metrics, "postOutputOwnership", "postHash", int(match.group("postHash"), 16))
            if match.group("outputHash") is not None:
                record_metric_max(metrics, "postOutputOwnership", "outputHash", int(match.group("outputHash"), 16))
            if match.group("planHash") is not None:
                record_metric_max(metrics, "postOutputOwnership", "planHash", int(match.group("planHash"), 16))
            if match.group("fallbackMask") is not None:
                record_metric_max(metrics, "postOutputOwnership", "fallbackMask", int(match.group("fallbackMask"), 16))
            continue

        match = GLX_POST_SHADER_PLAN_RE.search(line)
        if match:
            record_metric_max(metrics, "postShaderPlan", "valid", 1 if q3_bool(match.group("valid")) else 0)
            record_metric_max(metrics, "postShaderPlan", "features", int(match.group("features"), 16))
            record_metric_max(metrics, "postShaderPlan", "hash", int(match.group("hash"), 16))
            record_metric_max(metrics, "postShaderPlan", "textures", int_group(match, "textures"))
            record_metric_max(metrics, "postShaderPlan", "uniforms", int_group(match, "uniforms"))
            if match.group("frames") is not None:
                record_metric_max(metrics, "postShaderPlan", "frames", int_group(match, "frames"))
            if match.group("invalidFrames") is not None:
                record_metric_max(metrics, "postShaderPlan", "invalidFrames", int_group(match, "invalidFrames"))
            continue

        match = GLX_POST_SHADER_CACHE_RE.search(line)
        if match:
            record_metric_max(metrics, "postShaderCache", "ready", 1 if q3_bool(match.group("ready")) else 0)
            for key in (
                "programs",
                "programLimit",
                "validPlans",
                "invalidPlans",
                "cacheHits",
                "cacheMisses",
                "compileAttempts",
                "compileFailures",
                "linkFailures",
                "sourceFailures",
                "program",
            ):
                record_metric_max(metrics, "postShaderCache", key, int_group(match, key))
            record_metric_max(metrics, "postShaderCache", "sourceHash", int(match.group("sourceHash"), 16))
            continue

        match = GLX_POST_SHADER_DIRECT_FINAL_RE.search(line)
        if match:
            record_metric_max(metrics, "postShaderDirectFinal", "execute", 1 if q3_bool(match.group("execute")) else 0)
            record_metric_max(metrics, "postShaderDirectFinal", "eligible", 1 if q3_bool(match.group("eligible")) else 0)
            record_metric_max(metrics, "postShaderDirectFinal", "bound", 1 if q3_bool(match.group("bound")) else 0)
            record_metric_max(metrics, "postShaderDirectFinal", "reject", int(match.group("reject"), 16))
            for key in (
                "candidates",
                "eligibleFrames",
                "attempts",
                "binds",
                "fallbacks",
                "rejects",
            ):
                record_metric_max(metrics, "postShaderDirectFinal", key, int_group(match, key))
            if match.group("programMisses") is not None:
                record_metric_max(metrics, "postShaderDirectFinal", "programMisses", int_group(match, "programMisses"))
            if match.group("uniformFailures") is not None:
                record_metric_max(metrics, "postShaderDirectFinal", "uniformFailures", int_group(match, "uniformFailures"))
            continue

        match = POSTPROCESS_FBO_RE.search(line)
        if match:
            requested = q3_bool(match.group("requested"))
            ready = q3_bool(match.group("ready"))
            record_metric_max(metrics, "postprocess", "fboRequested", 1 if requested else 0)
            record_metric_max(metrics, "postprocess", "fboReady", 1 if ready else 0)
            if requires_glx_paths and requested and not ready:
                failures.append("GLx postprocess FBO was requested but not ready.")
            continue

        match = POSTPROCESS_TARGET_FORMAT_RE.search(line)
        if match:
            for key in ("renderWidth", "renderHeight", "captureWidth", "captureHeight", "windowWidth", "windowHeight"):
                record_metric_max(metrics, "targetFormat", key, int_group(match, key))
            for key in ("internalFormat", "textureFormat", "textureType"):
                record_metric_max(metrics, "targetFormat", key, int(match.group(key), 16))
            continue

        match = POSTPROCESS_CONTROLS_RE.search(line)
        if match:
            for key in ("sceneLinearHdr", "msaa", "supersample", "windowAdjusted"):
                record_metric_max(
                    metrics,
                    "postprocessControls",
                    key,
                    1 if q3_bool(match.group(key)) else 0,
                )
            for key in ("precision", "renderScale", "bloom"):
                record_metric_max(metrics, "postprocessControls", key, int_group(match, key))
            record_metric_max(metrics, "postprocessControls", "greyscale", float(match.group("greyscale")))
            continue

        match = POSTPROCESS_FRAMES_RE.search(line)
        if match:
            for key in ("frames", "bloomFinal", "gammaDirect", "gammaBlit", "minimizedOutput", "screenshots"):
                record_metric_max(metrics, "postprocessFrames", key, int_group(match, key))
            if int_group(match, "minimizedOutput") > 0:
                failures.append(f"GLx postprocess minimized output frames: {int_group(match, 'minimizedOutput')}.")
            continue

        match = POSTPROCESS_FRAME_FEATURES_RE.search(line)
        if match:
            for key in ("bloomAvailable", "sceneLinear", "toneMapped", "graded", "renderScale", "greyscale", "windowAdjusted", "minimized"):
                record_metric_max(metrics, "postprocessFrameFeatures", key, int_group(match, key))
            if int_group(match, "minimized") > 0:
                failures.append(f"GLx postprocess minimized frames: {int_group(match, 'minimized')}.")
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

        match = POSTPROCESS_BLOOM_STORAGE_RE.search(line)
        if match:
            record_metric_max(metrics, "postprocess", "bloomStoragePolicy", match.group("policy").lower())
            for key in ("internalFormat", "textureFormat", "textureType"):
                record_metric_max(metrics, "postprocess", f"bloomStorage{key[0].upper()}{key[1:]}", int(match.group(key), 16))
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

        match = GLX_PASS_COUNTERS_RE.search(line)
        if match:
            for key in ("blits", "binds", "clears", "fullscreen"):
                record_metric_max(metrics, "gpuPassCounters", key, int_group(match, key))
            for key in ("queries", "unavailable", "ringSkips"):
                if match.group(key) is not None:
                    record_metric_max(metrics, "gpuPassCounters", key, int_group(match, key))
            continue

        match = GLX_PASS_TIMER_RE.search(line)
        if match:
            record_metric_max(metrics, "gpuPassTiming", "active", 1 if q3_bool(match.group("active")) else 0)
            for key in ("queries", "unavailable", "ringSkips"):
                record_metric_max(metrics, "gpuPassTiming", key, int_group(match, key))
            continue

        match = GLX_PASS_GPU_RE.search(line)
        if match:
            timings = parse_pass_gpu_tokens(match.group("body"))
            if timings:
                metric_section(metrics, "gpuPassTimings").update(timings)
            continue

        match = GLX_COLOR_PIPELINE_RE.search(line)
        if match:
            record_metric_max(metrics, "colorPipeline", "space", match.group("space").lower())
            record_metric_max(metrics, "colorPipeline", "transfer", match.group("transfer").lower())
            record_metric_max(metrics, "colorPipeline", "toneMap", normalize_tone_map_name(match.group("toneMap")))
            record_metric_max(metrics, "colorPipeline", "grade", match.group("grade").lower())
            record_metric_max(metrics, "colorPipeline", "exposure", float(match.group("exposure")))
            if match.group("precision") is not None:
                record_metric_max(metrics, "colorPipeline", "precision", int_group(match, "precision"))
            if match.group("bloomThreshold") is not None:
                record_metric_max(metrics, "colorPipeline", "bloomThreshold", float(match.group("bloomThreshold")))
            if match.group("bloomThresholdMode") is not None:
                record_metric_max(metrics, "colorPipeline", "bloomThresholdMode", int_group(match, "bloomThresholdMode"))
            if match.group("bloomSoftKnee") is not None:
                record_metric_max(metrics, "colorPipeline", "bloomSoftKnee", float(match.group("bloomSoftKnee")))
            if match.group("paperWhite") is not None:
                record_metric_max(metrics, "colorPipeline", "paperWhite", float(match.group("paperWhite")))
            record_metric_max(metrics, "colorPipeline", "maxOutput", float(match.group("maxOutput")))
            if float(match.group("exposure")) <= 0.0:
                failures.append("GLx color pipeline exposure must be positive.")
            if (
                match.group("transfer").lower() == GLX_SDR_OUTPUT_CONTRACT["transfer"]
                and float(match.group("maxOutput")) > float(match.group("paperWhite") or GLX_SDR_OUTPUT_CONTRACT["paperWhiteNits"]) + 0.01
            ):
                failures.append(
                    "GLx SDR output contract used HDR max-output headroom while hardware HDR is inactive."
                )
            continue

        match = GLX_AUTO_EXPOSURE_RE.search(line)
        if match:
            algorithm = match.group("algorithm").lower()
            enabled = 1 if q3_bool(match.group("enabled")) else 0
            fallback = 1 if q3_bool(match.group("fallback")) else 0
            record_metric_max(metrics, "autoExposure", "mode", int_group(match, "mode"))
            record_metric_max(metrics, "autoExposure", "algorithm", algorithm)
            record_metric_max(metrics, "autoExposure", "enabled", enabled)
            record_metric_max(metrics, "autoExposure", "fallback", fallback)
            for key in ("sampleCount", "sampleWidth", "sampleHeight", "frames"):
                record_metric_max(metrics, "autoExposure", key, int_group(match, key))
            for key in (
                "percentile",
                "targetLuma",
                "measuredLog2",
                "measuredLuma",
                "manual",
                "scale",
                "target",
            ):
                record_metric_max(metrics, "autoExposure", key, float(match.group(key)))
            record_metric_max(
                metrics,
                "autoExposure",
                "histogramFrames",
                int_group_any(match, "histogramFrames", "histogramFramesSlash"),
            )
            record_metric_max(
                metrics,
                "autoExposure",
                "simpleFrames",
                int_group_any(match, "simpleFrames", "simpleFramesSlash"),
            )
            record_metric_max(
                metrics,
                "autoExposure",
                "sampleFailures",
                int_group_any(match, "sampleFailures", "sampleFailuresSlash"),
            )
            if enabled and algorithm not in {"simple-average", "histogram-percentile"}:
                failures.append(f"GLx auto exposure reported unsupported algorithm {algorithm}.")
            if enabled and float(match.group("target")) <= 0.0:
                failures.append("GLx auto exposure target exposure must be positive.")
            continue

        match = GLX_COLOR_GRADE_RE.search(line)
        if match:
            record_metric_max(metrics, "colorGrade", "mode", match.group("mode").lower())
            for key in ("liftR", "liftG", "liftB", "gammaR", "gammaG", "gammaB", "gainR", "gainG", "gainB"):
                record_metric_max(metrics, "colorGrade", key, float(match.group(key)))
            record_metric_max(metrics, "colorGrade", "whiteSource", float(match.group("whiteSource")))
            record_metric_max(metrics, "colorGrade", "whiteTarget", float(match.group("whiteTarget")))
            record_metric_max(metrics, "colorGrade", "lutSize", float(match.group("lutSize")))
            record_metric_max(metrics, "colorGrade", "lutScale", float(match.group("lutScale")))
            if float(match.group("gammaR")) <= 0.0 or float(match.group("gammaG")) <= 0.0 or float(match.group("gammaB")) <= 0.0:
                failures.append("GLx color-grade gamma values must be positive.")
            if float(match.group("lutScale")) <= 0.0:
                failures.append("GLx color-grade LUT scale must be positive.")
            continue

        match = GLX_COLOR_AUDIT_RE.search(line)
        if match:
            record_metric_max(metrics, "colorAudit", "srgbDecode", 1 if q3_bool(match.group("srgbDecode")) else 0)
            record_metric_max(metrics, "colorAudit", "srgbRequested", 1 if q3_bool(match.group("srgbRequested")) else 0)
            record_metric_max(metrics, "colorAudit", "srgbAvailable", 1 if q3_bool(match.group("srgbAvailable")) else 0)
            record_metric_max(metrics, "colorAudit", "framebufferSrgb", 1 if q3_bool(match.group("framebufferSrgb")) else 0)
            record_metric_max(metrics, "colorAudit", "framebufferRequested", 1 if q3_bool(match.group("framebufferRequested")) else 0)
            record_metric_max(metrics, "colorAudit", "framebufferAvailable", 1 if q3_bool(match.group("framebufferAvailable")) else 0)
            record_metric_max(metrics, "colorAudit", "capture", match.group("capture").lower())
            if match.group("captureRequest") is not None:
                record_metric_max(metrics, "colorAudit", "captureRequest", match.group("captureRequest").lower())
            if match.group("captureHdrAware") is not None:
                record_metric_max(metrics, "colorAudit", "captureHdrAware", 1 if q3_bool(match.group("captureHdrAware")) else 0)
            if match.group("captureSupported") is not None:
                capture_supported = q3_bool(match.group("captureSupported"))
                record_metric_max(metrics, "colorAudit", "captureSupported", 1 if capture_supported else 0)
            if match.group("targetFloat") is not None:
                record_metric_max(metrics, "colorAudit", "targetFloat", 1 if q3_bool(match.group("targetFloat")) else 0)
            if match.group("finalEncode") is not None:
                record_metric_max(metrics, "colorAudit", "finalEncode", match.group("finalEncode").lower())
            if match.group("contract") is not None:
                contract_valid = q3_bool(match.group("contract"))
                record_metric_max(metrics, "colorAudit", "contract", 1 if contract_valid else 0)
                if not contract_valid:
                    failures.append("GLx color output contract is invalid.")
            if q3_bool(match.group("framebufferSrgb")):
                failures.append("GLx framebuffer sRGB state is active on the shader-encoded SDR output path.")
            continue

        match = GLX_TEXTURE_AUDIT_RE.search(line)
        if match:
            for key in (
                "srgb",
                "srgbDecode",
                "linear",
                "linearDecode",
                "data",
                "dataDecode",
                "unknown",
                "unknownDecode",
                "missingSrgbDecode",
                "unexpectedDecode",
            ):
                record_metric_max(metrics, "textureAudit", key, int_group(match, key))
            if int_group(match, "missingSrgbDecode") > 0:
                failures.append(
                    f"GLx texture audit missing sRGB decode rows: {int_group(match, 'missingSrgbDecode')}."
                )
            if int_group(match, "unexpectedDecode") > 0:
                failures.append(
                    f"GLx texture audit unexpected decode rows: {int_group(match, 'unexpectedDecode')}."
                )
            continue

        match = GLX_COLOR_FRAME_JSON_RE.search(line)
        if match:
            try:
                payload = json.loads(match.group("payload"))
            except json.JSONDecodeError as exc:
                failures.append(f"GLx color-frame JSON is invalid: {exc}.")
                continue
            if isinstance(payload, dict):
                record_color_frame_diagnostics(metrics, payload, failures)
            else:
                failures.append("GLx color-frame JSON payload is not an object.")
            continue

        match = GLX_COLOR_FRAME_CSV_RE.search(line)
        if match:
            record_color_frame_diagnostics(metrics, color_frame_payload_from_csv(match), failures)
            continue

        match = GLX_OUTPUT_BACKEND_RE.search(line)
        if match:
            record_metric_max(metrics, "outputBackend", "request", match.group("request").lower())
            record_metric_max(metrics, "outputBackend", "selected", match.group("selected").lower())
            record_metric_max(metrics, "outputBackend", "native", match.group("native").lower())
            record_metric_max(metrics, "outputBackend", "hardware", 1 if q3_bool(match.group("hardware")) else 0)
            record_metric_max(metrics, "outputBackend", "experimental", 1 if q3_bool(match.group("experimental")) else 0)
            record_metric_max(metrics, "outputBackend", "displayHdr", 1 if q3_bool(match.group("displayHdr")) else 0)
            record_metric_max(metrics, "outputBackend", "headroom", float(match.group("headroom")))
            record_metric_max(metrics, "outputBackend", "sdrWhite", float(match.group("sdrWhite")))
            record_metric_max(metrics, "outputBackend", "displayMax", float(match.group("displayMax")))
            record_metric_max(metrics, "outputBackend", "icc", 1 if q3_bool(match.group("icc")) else 0)
            record_metric_max(metrics, "outputBackend", "iccBytes", int_group(match, "iccBytes"))
            if float(match.group("headroom")) <= 0.0:
                failures.append("GLx output backend headroom must be positive.")
            if float(match.group("sdrWhite")) <= 0.0 or float(match.group("displayMax")) <= 0.0:
                failures.append("GLx output backend luminance values must be positive.")
            if q3_bool(match.group("experimental")) and match.group("selected").lower() != "linux-experimental-hdr":
                failures.append("GLx output backend reported experimental state without selecting the Linux experimental backend.")
            continue

        match = GLX_DISPLAY_STATE_RE.search(line)
        if match:
            for key in ("queries", "changes", "capability", "backend", "hdr", "headroom", "luminance", "icc", "lastFrame"):
                record_metric_max(metrics, "displayState", key, int_group(match, key))
            record_metric_max(metrics, "displayState", "flags", int(match.group("flags"), 16))
            record_metric_max(metrics, "displayState", "hash", int(match.group("hash"), 16))
            record_metric_max(metrics, "displayState", "previous", int(match.group("previous"), 16))
            if int_group(match, "queries") <= 0:
                failures.append("GLx display-state diagnostics did not record any output queries.")
            if int(match.group("hash"), 16) == 0:
                failures.append("GLx display-state diagnostics reported a zero output hash.")
            if int_group(match, "changes") > 0 and int(match.group("flags"), 16) == 0:
                failures.append("GLx display-state diagnostics reported changes without change flags.")
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

        match = STREAM_BINDING_CACHE_RE.search(line)
        if match:
            for key in ("queries", "hits", "restores", "invalidations"):
                record_metric_max(metrics, "streamBindingCache", key, int_group(match, key))
            if match.group("external") is not None:
                record_metric_max(metrics, "streamBindingCache", "external", int_group(match, "external"))
            continue

        match = STREAM_DRAWS_RE.search(line)
        if match:
            for key in ("draws", "attempts", "fallbacks"):
                record_metric_max(metrics, "streamDraw", key, int_group(match, key))
            for group, key in (
                ("multitexture", "multitexture"),
                ("fog", "fog"),
                ("depthFragment", "depthFragment"),
                ("texMods", "texMods"),
                ("environment", "environment"),
                ("dynamicLights", "dynamicLights"),
                ("screenMaps", "screenMaps"),
                ("videoMaps", "videoMaps"),
            ):
                record_metric_max(metrics, "streamDraw", key, int_group(match, group))
            for group, key in (
                ("shadows", "shadows"),
                ("beams", "beams"),
                ("postprocess", "postprocess"),
            ):
                if match.group(group) is not None:
                    record_metric_max(metrics, "streamDraw", key, int_group(match, group))
            if int_group(match, "fallbacks") > 0:
                failures.append(f"GLx streamed draw fallbacks: {int_group(match, 'fallbacks')}.")
            if requires_glx_paths:
                for group, label in (
                    ("dynamicLights", "dynamic-light"),
                    ("screenMaps", "screen-map"),
                    ("videoMaps", "video-map"),
                ):
                    count = int_group(match, group)
                    if count > 0:
                        failures.append(f"GLx streamed high-risk {label} material draws: {count}.")
            continue

        match = STREAM_CATEGORIES_RE.search(line)
        if match:
            saw_stream_categories = True
            for category in STREAM_CATEGORY_KEYS:
                record_metric_max(metrics, "streamCategory", f"{category}Draws", int_group(match, f"{category}Draws"))
                record_metric_max(
                    metrics,
                    "streamCategory",
                    f"{category}Attempts",
                    int_group(match, f"{category}Attempts"),
                )
                record_metric_max(
                    metrics,
                    "streamCategory",
                    f"{category}Observed",
                    1 if int_group(match, f"{category}Attempts") > 0 else 0,
                )
            continue

        match = STREAM_CATEGORY_FALLBACKS_RE.search(line)
        if match:
            for category in STREAM_CATEGORY_KEYS:
                count = int_group(match, category)
                record_metric_max(metrics, "streamCategory", f"{category}Fallbacks", count)
                if count > 0:
                    failures.append(f"GLx streamed {category} category fallbacks: {count}.")
            continue

        match = STREAM_DRAW_SKIPS_RE.search(line)
        if match:
            record_metric_max(metrics, "streamDraw", "skips", int_group(match, "total"))
            for key in (
                "bind",
                "input",
                "multitexture",
                "depthFragment",
                "texcoord",
                "empty",
                "key",
                "fog",
                "program",
            ):
                record_metric_max(metrics, "streamDrawSkip", key, int_group(match, key))
            if int_group(match, "program") > 0:
                failures.append(f"GLx streamed draw material-program skips: {int_group(match, 'program')}.")
            continue

        match = STREAM_MATERIAL_COMPILER_RE.search(line)
        if match:
            record_metric_max(metrics, "streamMaterialCompiler", "rejected", int_group(match, "rejected"))
            record_metric_max(
                metrics,
                "streamMaterialCompiler",
                "lastUnsupported",
                int(match.group("lastUnsupported"), 16),
            )
            record_metric_max(
                metrics,
                "streamMaterialCompiler",
                "lastUnsupportedReason",
                match.group("lastUnsupportedReason"),
            )
            if requires_glx_paths and int_group(match, "rejected") > 0:
                failures.append(
                    "GLx stream material compiler rejections: "
                    f"{int_group(match, 'rejected')} "
                    f"({match.group('lastUnsupportedReason')})."
                )
            continue

        match = STREAM_MATERIAL_GATE_RE.search(line)
        if match:
            key = STREAM_MATERIAL_GATE_KEYS[match.group("name").lower()]
            record_metric_max(metrics, "streamMaterialGate", f"{key}Enabled", 1 if q3_bool(match.group("enabled")) else 0)
            record_metric_max(metrics, "streamMaterialGate", f"{key}Accepted", int_group(match, "accepted"))
            record_metric_max(metrics, "streamMaterialGate", f"{key}Rejected", int_group(match, "rejected"))
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
            packet_profile = profile in {"glx-parity", "glx-ownership", "glx-stress"}
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
            if profile in {"glx-parity", "glx-ownership", "glx-stress"} and not enabled:
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
    if requires_glx_paths and not saw_stream_categories:
        failures.append("No GLx dynamic stream category diagnostics were found in the run log.")
    if requires_glx_ownership and not saw_ownership:
        failures.append("No GLx ownership diagnostic output was found in the run log.")
    if requires_glx_paths:
        pass_schedule = metric_section(metrics, "passSchedule")
        schedule_failure = pass_schedule_failure_from_values(
            pass_schedule.get("valid"),
            pass_schedule.get("count"),
            pass_schedule.get("hash"),
            pass_schedule.get("order"),
        )
        if schedule_failure:
            failures.append(schedule_failure)

    product_tier = metric_section(metrics, "productTier").get("tier")
    if requires_tier_contract and product_tier == "GL12":
        gl12_executor = metric_section(metrics, "gl12Executor")
        gl12_support = metric_section(metrics, "gl12Support")
        if gl12_executor.get("active") != 1:
            failures.append("GL12 product tier did not report the fixed-function executor contract.")
        for key in ("clientMemoryDraws",):
            if gl12_executor.get(key) != 1:
                failures.append("GL12 fixed-function executor did not report required client-memory draw support.")
        for key in ("streamUploads", "materialCompiler", "modernPostChain"):
            if gl12_executor.get(key) not in (0, None):
                failures.append(f"GL12 fixed-function executor incorrectly reports {key} support.")
        for key in (
            "lightmaps",
            "multitexture",
            "fog",
            "sprites",
            "beams",
            "dynamicLights",
            "stencilShadows",
            "screenshots",
            "demos",
        ):
            if gl12_support.get(key) != 1:
                failures.append(f"GL12 fixed-function support is missing required {key} coverage.")
    if requires_tier_contract and product_tier == "GL2X":
        gl2x_executor = metric_section(metrics, "gl2xExecutor")
        gl2x_support = metric_section(metrics, "gl2xSupport")
        if gl2x_executor.get("active") != 1:
            failures.append("GL2X product tier did not report the programmable executor contract.")
        for key in ("clientMemoryFallback", "streamUploads", "materialCompiler", "postprocessLite"):
            if gl2x_executor.get(key) != 1:
                failures.append(f"GL2X programmable executor did not report required {key} support.")
        for key in ("modernPostChain", "sceneLinearOutput"):
            if gl2x_executor.get(key) not in (0, None):
                failures.append(f"GL2X programmable executor incorrectly reports {key} support.")
        for key in (
            "commonMaterials",
            "dynamicEntities",
            "lightmaps",
            "multitexture",
            "fog",
            "sprites",
            "beams",
            "screenshots",
            "demos",
        ):
            if gl2x_support.get(key) != 1:
                failures.append(f"GL2X programmable support is missing required {key} coverage.")
    if requires_tier_contract and product_tier == "GL3X":
        gl3x_executor = metric_section(metrics, "gl3xExecutor")
        gl3x_support = metric_section(metrics, "gl3xSupport")
        if gl3x_executor.get("active") != 1:
            failures.append("GL3X product tier did not report the performance executor contract.")
        for key in (
            "fboPostProcess",
            "uboFrameObjectConstants",
            "timerQueries",
            "syncAwareUploads",
            "staticBufferOwnership",
            "dynamicBufferOwnership",
        ):
            if gl3x_executor.get(key) != 1:
                failures.append(f"GL3X performance executor did not report required {key} support.")
        for key in ("persistentUploads", "indirectSubmission", "directStateAccess"):
            if gl3x_executor.get(key) not in (0, None):
                failures.append(f"GL3X performance executor incorrectly reports {key} as required.")
        for key in (
            "materialCompiler",
            "commonMaterials",
            "dynamicEntities",
            "modernPostChain",
            "sceneLinearOutput",
            "screenshots",
            "demos",
        ):
            if gl3x_support.get(key) != 1:
                failures.append(f"GL3X performance support is missing required {key} coverage.")
    if requires_tier_contract and product_tier == "GL41":
        gl41_executor = metric_section(metrics, "gl41Executor")
        gl41_support = metric_section(metrics, "gl41Support")
        gl41_limits = metric_section(metrics, "gl41Limits")
        if gl41_executor.get("active") != 1:
            failures.append("GL41 product tier did not report the mac-modern executor contract.")
        for key in (
            "fboPostProcess",
            "uboFrameObjectConstants",
            "timerQueries",
            "syncAwareUploads",
            "staticBufferOwnership",
            "dynamicBufferOwnership",
            "macOS41Ceiling",
        ):
            if gl41_executor.get(key) != 1:
                failures.append(f"GL41 mac-modern executor did not report required {key} support.")
        for key in (
            "materialCompiler",
            "commonMaterials",
            "dynamicEntities",
            "modernPostChain",
            "sceneLinearOutput",
            "highQualitySdr",
            "screenshots",
            "demos",
        ):
            if gl41_support.get(key) != 1:
                failures.append(f"GL41 mac-modern support is missing required {key} coverage.")
        for key in (
            "debugOutputRequired",
            "bufferStorageRequired",
            "directStateAccessRequired",
            "multiDrawIndirectRequired",
            "persistentUploadsRequired",
        ):
            if gl41_limits.get(key) not in (0, None):
                failures.append(f"GL41 mac-modern executor incorrectly requires {key}.")
    if requires_tier_contract and product_tier == "GL46":
        gl46_executor = metric_section(metrics, "gl46Executor")
        gl46_support = metric_section(metrics, "gl46Support")
        gl46_requirements = metric_section(metrics, "gl46Requirements")
        if gl46_executor.get("active") != 1:
            failures.append("GL46 product tier did not report the high-end executor contract.")
        for key in (
            "persistentUploads",
            "bufferStorageUploads",
            "syncHeavyStreaming",
            "directStateAccess",
            "multiDrawIndirect",
            "aggressiveStaticWorldSubmission",
            "detailedGpuCounters",
        ):
            if gl46_executor.get(key) != 1:
                failures.append(f"GL46 high-end executor did not report required {key} support.")
        for key in (
            "materialCompiler",
            "commonMaterials",
            "dynamicEntities",
            "modernPostChain",
            "sceneLinearOutput",
            "hardwareHdrOutput",
            "screenshots",
            "demos",
        ):
            if gl46_support.get(key) != 1:
                failures.append(f"GL46 high-end support is missing required {key} coverage.")
        for key in (
            "debugOutputRequired",
            "bufferStorageRequired",
            "directStateAccessRequired",
            "multiDrawIndirectRequired",
        ):
            if gl46_requirements.get(key) != 1:
                failures.append(f"GL46 high-end executor did not report required {key}.")

    if requires_glx_ownership and product_tier in {"GL3X", "GL41", "GL46"}:
        post_output = metric_section(metrics, "postOutputOwnership")
        render_products = metric_section(metrics, "renderIRProducts")
        post_nodes = post_output.get("postNodes", render_products.get("postNodes"))
        outputs = post_output.get("outputs", render_products.get("outputs"))
        executable_nodes = post_output.get("executableNodes")
        executable_outputs = post_output.get("executableOutputs")
        post_hash = post_output.get("postHash")
        output_hash = post_output.get("outputHash")
        plan_hash = post_output.get("planHash")
        fallback_mask = post_output.get("fallbackMask")
        if post_output.get("mode") not in ("glx-owned", None):
            failures.append("GLx post/output ownership is not in glx-owned mode on a modern tier.")
        if post_output.get("legacyFallback") not in (0, None):
            failures.append("GLx post/output ownership still reports legacy fallback on a modern tier.")
        if fallback_mask not in (0, None):
            failures.append("GLx post/output ownership plan reports a fallback reason on a modern tier.")
        if executable_nodes is not None and (
            not isinstance(executable_nodes, int) or executable_nodes <= 0
        ):
            failures.append("GLx post/output ownership did not report executable GLx post nodes on a modern tier.")
        if executable_outputs is not None and (
            not isinstance(executable_outputs, int) or executable_outputs <= 0
        ):
            failures.append("GLx post/output ownership did not report executable GLx output transforms on a modern tier.")
        if not isinstance(post_nodes, int) or post_nodes <= 0:
            failures.append("GLx ownership proof did not execute any GLx post nodes on a modern tier.")
        if not isinstance(outputs, int) or outputs <= 0:
            failures.append("GLx ownership proof did not execute any GLx output transforms on a modern tier.")
        if not isinstance(post_hash, int) or post_hash <= 0:
            failures.append("GLx ownership proof did not report a post-node fingerprint on a modern tier.")
        if not isinstance(output_hash, int) or output_hash <= 0:
            failures.append("GLx ownership proof did not report an output-transform fingerprint on a modern tier.")
        if not isinstance(plan_hash, int) or plan_hash <= 0:
            failures.append("GLx ownership proof did not report a post/output plan fingerprint on a modern tier.")

    color_pipeline = metrics.get("colorPipeline")
    target_format = metrics.get("targetFormat")
    if (
        isinstance(color_pipeline, dict)
        and color_pipeline.get("space") == "scene-linear"
    ):
        if not isinstance(target_format, dict):
            failures.append("GLx scene-linear target format metadata is missing.")
        else:
            for key, expected in (
                ("internalFormat", GLX_SCENE_TARGET_FORMAT_CONTRACT["internalFormat"]),
                ("textureFormat", GLX_SCENE_TARGET_FORMAT_CONTRACT["textureFormat"]),
                ("textureType", GLX_SCENE_TARGET_FORMAT_CONTRACT["textureType"]),
            ):
                try:
                    actual_hex = normalized_hex(target_format.get(key))
                except (TypeError, ValueError):
                    actual_hex = str(target_format.get(key))
                if actual_hex != expected:
                    failures.append(
                        f"GLx scene-linear target {key} is {actual_hex}; expected {expected}."
                    )

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


def parse_gpu_milliseconds(text: str) -> float | None:
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*ms\b", text, re.IGNORECASE)
    if not match:
        return None
    return float(match.group(1))


def pass_metric_suffix(name: str) -> str:
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", name) if part]
    return "".join(part[:1].upper() + part[1:] for part in parts)


def parse_pass_gpu_tokens(body: str) -> dict[str, dict[str, object]]:
    timings: dict[str, dict[str, object]] = {}
    for token in body.split():
        if "=" not in token or "/" not in token:
            continue
        name, rest = token.split("=", 1)
        value, samples_text = rest.rsplit("/", 1)
        try:
            samples = int(samples_text)
        except ValueError:
            continue
        entry: dict[str, object] = {"text": value, "samples": samples}
        milliseconds = parse_gpu_milliseconds(value)
        if milliseconds is not None:
            entry["lastMs"] = milliseconds
        timings[name.strip().lower()] = entry
    return timings


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
        if not (
            line.startswith("glx:")
            or line.startswith("target:")
            or line.startswith("controls:")
            or line.startswith("frames:")
            or line.startswith("frame features:")
            or line.startswith("pass ")
            or line.startswith("post pass ")
        ):
            continue

        performance["found"] = True

        match = GLX_FRAME_COUNTER_RE.search(line)
        if match:
            performance["sampleCount"] = int(performance["sampleCount"]) + 1
            perf_record_string(performance, "tier", match.group("tier"))
            perf_record_string(performance, "productTier", match.group("tier"))
            perf_record_string(performance, "streamStrategy", match.group("streamStrategy"))
            perf_record_string(performance, "streamReady", match.group("streamReady"))
            perf_record_string(performance, "gpu", match.group("gpu").strip())
            gpu_ms = parse_gpu_milliseconds(match.group("gpu"))
            if gpu_ms is not None:
                perf_record_numeric(performance, "gpuFrameMs", gpu_ms)
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
            perf_record_numeric(performance, "streamSameFrameWrapRejects", int_group(match, "streamRejects"))
            for key in ("streamMegabytes", "staticMegabytes", "arenaMegabytes"):
                perf_record_numeric(performance, key, float(match.group(key)))
            continue

        match = GLX_PASS_COUNTERS_RE.search(line)
        if match:
            for key, metric in (
                ("blits", "gpuPassBlits"),
                ("binds", "gpuPassBinds"),
                ("clears", "gpuPassClears"),
                ("fullscreen", "gpuPassFullscreen"),
            ):
                perf_record_numeric(performance, metric, int_group(match, key))
            for key, metric in (
                ("queries", "gpuPassQueries"),
                ("unavailable", "gpuPassUnavailable"),
                ("ringSkips", "gpuPassRingSkips"),
            ):
                if match.group(key) is not None:
                    perf_record_numeric(performance, metric, int_group(match, key))
            continue

        match = GLX_PASS_TIMER_RE.search(line)
        if match:
            perf_record_numeric(performance, "gpuPassTimerActive", 1 if q3_bool(match.group("active")) else 0)
            perf_record_numeric(performance, "gpuPassQueries", int_group(match, "queries"))
            perf_record_numeric(performance, "gpuPassUnavailable", int_group(match, "unavailable"))
            perf_record_numeric(performance, "gpuPassRingSkips", int_group(match, "ringSkips"))
            continue

        match = GLX_PASS_GPU_RE.search(line)
        if match:
            for pass_name, timing in parse_pass_gpu_tokens(match.group("body")).items():
                suffix = pass_metric_suffix(pass_name)
                if "lastMs" in timing:
                    perf_record_numeric(performance, f"gpuPass{suffix}Ms", timing["lastMs"])
                perf_record_numeric(performance, f"gpuPass{suffix}Samples", timing["samples"])
            continue

        match = GLX_PASS_SCHEDULE_RE.search(line)
        if match:
            valid = 1 if match.group("valid").lower() == "valid" else 0
            latest = performance.get("latest", {})
            if valid == 1 or not (isinstance(latest, dict) and latest.get("passScheduleValid") == 1):
                perf_record_numeric(performance, "passScheduleValid", valid)
                perf_record_numeric(performance, "passScheduleCount", int_group(match, "count"))
                perf_record_string(performance, "passScheduleHash", match.group("hash").lower())
                perf_record_string(performance, "passScheduleOrder", match.group("order"))
            continue

        match = GLX_RENDER_IR_PRODUCTS_RE.search(line)
        if match:
            perf_record_match_numbers_prefixed(
                performance,
                match,
                "renderIR",
                (
                    "passes",
                    "worldPackets",
                    "dynamicDraws",
                    "materials",
                    "uploads",
                    "postNodes",
                    "outputs",
                    "rejects",
                ),
            )
            continue

        match = GLX_POST_OUTPUT_OWNERSHIP_RE.search(line)
        if match:
            perf_record_string(performance, "postOutputMode", match.group("mode").lower())
            perf_record_numeric(performance, "postOutputPostNodes", int_group(match, "postNodes"))
            perf_record_numeric(performance, "postOutputOutputs", int_group(match, "outputs"))
            perf_record_numeric(performance, "postOutputLegacyFallback",
                1 if q3_bool(match.group("legacyFallback")) else 0)
            if match.group("executableNodes") is not None:
                perf_record_numeric(performance, "postOutputExecutableNodes", int_group(match, "executableNodes"))
            if match.group("executableOutputs") is not None:
                perf_record_numeric(performance, "postOutputExecutableOutputs", int_group(match, "executableOutputs"))
            if match.group("postHash") is not None:
                perf_record_numeric(performance, "postOutputPostHash", int(match.group("postHash"), 16))
            if match.group("outputHash") is not None:
                perf_record_numeric(performance, "postOutputOutputHash", int(match.group("outputHash"), 16))
            if match.group("planHash") is not None:
                perf_record_numeric(performance, "postOutputPlanHash", int(match.group("planHash"), 16))
            if match.group("fallbackMask") is not None:
                perf_record_numeric(performance, "postOutputFallbackMask", int(match.group("fallbackMask"), 16))
            continue

        match = GLX_POST_SHADER_PLAN_RE.search(line)
        if match:
            perf_record_numeric(performance, "postShaderPlanValid", 1 if q3_bool(match.group("valid")) else 0)
            perf_record_numeric(performance, "postShaderFeatures", int(match.group("features"), 16))
            perf_record_numeric(performance, "postShaderHash", int(match.group("hash"), 16))
            perf_record_numeric(performance, "postShaderTextures", int_group(match, "textures"))
            perf_record_numeric(performance, "postShaderUniforms", int_group(match, "uniforms"))
            if match.group("frames") is not None:
                perf_record_numeric(performance, "postShaderFrames", int_group(match, "frames"))
            if match.group("invalidFrames") is not None:
                perf_record_numeric(performance, "postShaderInvalidFrames", int_group(match, "invalidFrames"))
            continue

        match = GLX_POST_SHADER_CACHE_RE.search(line)
        if match:
            perf_record_numeric(performance, "postShaderCacheReady", 1 if q3_bool(match.group("ready")) else 0)
            for key, metric in (
                ("programs", "postShaderPrograms"),
                ("programLimit", "postShaderProgramLimit"),
                ("validPlans", "postShaderValidPlans"),
                ("invalidPlans", "postShaderInvalidPlans"),
                ("cacheHits", "postShaderCacheHits"),
                ("cacheMisses", "postShaderCacheMisses"),
                ("compileAttempts", "postShaderCompileAttempts"),
                ("compileFailures", "postShaderCompileFailures"),
                ("linkFailures", "postShaderLinkFailures"),
                ("sourceFailures", "postShaderSourceFailures"),
                ("program", "postShaderProgram"),
            ):
                perf_record_numeric(performance, metric, int_group(match, key))
            perf_record_numeric(performance, "postShaderSourceHash", int(match.group("sourceHash"), 16))
            continue

        match = GLX_POST_SHADER_DIRECT_FINAL_RE.search(line)
        if match:
            perf_record_numeric(performance, "postShaderDirectFinalExecute", 1 if q3_bool(match.group("execute")) else 0)
            perf_record_numeric(performance, "postShaderDirectFinalEligible", 1 if q3_bool(match.group("eligible")) else 0)
            perf_record_numeric(performance, "postShaderDirectFinalBound", 1 if q3_bool(match.group("bound")) else 0)
            perf_record_numeric(performance, "postShaderDirectFinalReject", int(match.group("reject"), 16))
            for key, metric in (
                ("candidates", "postShaderDirectFinalCandidates"),
                ("eligibleFrames", "postShaderDirectFinalEligibleFrames"),
                ("attempts", "postShaderDirectFinalAttempts"),
                ("binds", "postShaderDirectFinalBinds"),
                ("fallbacks", "postShaderDirectFinalFallbacks"),
                ("rejects", "postShaderDirectFinalRejects"),
            ):
                perf_record_numeric(performance, metric, int_group(match, key))
            if match.group("programMisses") is not None:
                perf_record_numeric(performance, "postShaderDirectFinalProgramMisses", int_group(match, "programMisses"))
            if match.group("uniformFailures") is not None:
                perf_record_numeric(performance, "postShaderDirectFinalUniformFailures", int_group(match, "uniformFailures"))
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

        match = MATERIAL_PARAMETER_DETAIL_RE.search(line)
        if match:
            perf_record_numeric(performance, "materialParameterBlocks", int_group(match, "blocks"))
            perf_record_numeric(performance, "materialInvalidParameterBlocks", int_group(match, "invalid"))
            if match.group("hash") is not None:
                perf_record_numeric(performance, "materialParameterHash", int(match.group("hash"), 16))
            perf_record_numeric(performance, "materialParameterSort", int_group(match, "sort"))
            perf_record_numeric(performance, "materialParameterPasses", int_group(match, "passes"))
            perf_record_numeric(performance, "materialParameterFeatures", int(match.group("features"), 16))
            perf_record_numeric(performance, "materialParameterFlags", int(match.group("flags"), 16))
            perf_record_numeric(performance, "materialParameterState", int(match.group("state"), 16))
            for key in ("rgbGen", "rgbWave", "alphaGen", "alphaWave", "tcGen0", "tcGen1"):
                if match.group(key) is not None:
                    perf_record_numeric(
                        performance,
                        f"materialParameter{key[0].upper()}{key[1:]}",
                        int_group(match, key),
                    )
            continue

        match = MATERIAL_PARAMETER_BLOCKS_RE.search(line)
        if match:
            perf_record_numeric(performance, "materialParameterBlocks", int_group(match, "blocks"))
            perf_record_numeric(performance, "materialInvalidParameterBlocks", int_group(match, "invalid"))
            if match.group("hash") is not None:
                perf_record_numeric(performance, "materialParameterHash", int(match.group("hash"), 16))
            continue

        match = MATERIAL_FLAGS_COMMON_RE.search(line)
        if match:
            for key in (
                "multitexture",
                "depthFragment",
                "blend",
                "alphaTest",
                "depthWrite",
                "lightmap",
            ):
                perf_record_numeric(
                    performance,
                    f"materialStageFlag{key[0].upper()}{key[1:]}",
                    int_group(match, key),
                )
            continue

        match = MATERIAL_FLAGS_SPECIAL_RE.search(line)
        if match:
            for key in (
                "animatedImage",
                "videoMap",
                "screenMap",
                "dynamicLightMap",
                "texMod",
                "environment",
                "st0",
                "st1",
            ):
                perf_record_numeric(
                    performance,
                    f"materialStageFlag{key[0].upper()}{key[1:]}",
                    int_group(match, key),
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

        match = POSTPROCESS_TARGET_FORMAT_RE.search(line)
        if match:
            for key in ("renderWidth", "renderHeight", "captureWidth", "captureHeight", "windowWidth", "windowHeight"):
                perf_record_numeric(performance, f"target{key[0].upper()}{key[1:]}", int_group(match, key))
            for key in ("internalFormat", "textureFormat", "textureType"):
                perf_record_numeric(performance, f"target{key[0].upper()}{key[1:]}", int(match.group(key), 16))
            continue

        match = POSTPROCESS_CONTROLS_RE.search(line)
        if match:
            perf_record_numeric(performance, "postprocessSceneLinearHdr", 1 if q3_bool(match.group("sceneLinearHdr")) else 0)
            perf_record_numeric(performance, "postprocessPrecision", int_group(match, "precision"))
            perf_record_numeric(performance, "postprocessRenderScaleMode", int_group(match, "renderScale"))
            perf_record_numeric(performance, "postprocessBloomMode", int_group(match, "bloom"))
            perf_record_numeric(performance, "postprocessMsaa", 1 if q3_bool(match.group("msaa")) else 0)
            perf_record_numeric(performance, "postprocessSupersample", 1 if q3_bool(match.group("supersample")) else 0)
            perf_record_numeric(performance, "postprocessWindowAdjusted", 1 if q3_bool(match.group("windowAdjusted")) else 0)
            perf_record_numeric(performance, "postprocessGreyscale", float(match.group("greyscale")))
            continue

        match = POSTPROCESS_BLOOM_STORAGE_RE.search(line)
        if match:
            perf_record_string(performance, "bloomStoragePolicy", match.group("policy").lower())
            for key in ("internalFormat", "textureFormat", "textureType"):
                perf_record_numeric(performance, f"bloomStorage{key[0].upper()}{key[1:]}", int(match.group(key), 16))
            continue

        match = POSTPROCESS_FRAMES_RE.search(line)
        if match:
            for key in ("frames", "bloomFinal", "gammaDirect", "gammaBlit", "minimizedOutput", "screenshots"):
                perf_record_numeric(performance, f"postprocess{key[0].upper()}{key[1:]}", int_group(match, key))
            continue

        match = POSTPROCESS_FRAME_FEATURES_RE.search(line)
        if match:
            for key in ("bloomAvailable", "sceneLinear", "toneMapped", "graded", "renderScale", "greyscale", "windowAdjusted", "minimized"):
                perf_record_numeric(performance, f"postprocessFeature{key[0].upper()}{key[1:]}", int_group(match, key))
            continue

        match = GLX_COLOR_PIPELINE_RE.search(line)
        if match:
            perf_record_string(performance, "colorSpace", match.group("space").lower())
            perf_record_string(performance, "outputTransfer", match.group("transfer").lower())
            perf_record_string(performance, "toneMap", normalize_tone_map_name(match.group("toneMap")))
            perf_record_string(performance, "colorGrade", match.group("grade").lower())
            perf_record_numeric(performance, "toneMapExposure", float(match.group("exposure")))
            if match.group("precision") is not None:
                perf_record_numeric(performance, "hdrPrecision", int_group(match, "precision"))
            if match.group("bloomThreshold") is not None:
                perf_record_numeric(performance, "bloomThreshold", float(match.group("bloomThreshold")))
            if match.group("bloomThresholdMode") is not None:
                perf_record_numeric(performance, "bloomThresholdMode", int_group(match, "bloomThresholdMode"))
            if match.group("bloomSoftKnee") is not None:
                perf_record_numeric(performance, "bloomSoftKnee", float(match.group("bloomSoftKnee")))
            if match.group("paperWhite") is not None:
                perf_record_numeric(performance, "paperWhiteNits", float(match.group("paperWhite")))
            perf_record_numeric(performance, "maxOutputNits", float(match.group("maxOutput")))
            continue

        match = GLX_AUTO_EXPOSURE_RE.search(line)
        if match:
            perf_record_numeric(performance, "autoExposureMode", int_group(match, "mode"))
            perf_record_string(performance, "autoExposureAlgorithm", match.group("algorithm").lower())
            perf_record_numeric(performance, "autoExposureEnabled", 1 if q3_bool(match.group("enabled")) else 0)
            perf_record_numeric(performance, "autoExposureFallback", 1 if q3_bool(match.group("fallback")) else 0)
            for key, metric in (
                ("sampleCount", "autoExposureSampleCount"),
                ("sampleWidth", "autoExposureSampleWidth"),
                ("sampleHeight", "autoExposureSampleHeight"),
                ("frames", "autoExposureFrames"),
            ):
                perf_record_numeric(performance, metric, int_group(match, key))
            for key, metric in (
                ("percentile", "autoExposurePercentile"),
                ("targetLuma", "autoExposureTargetLuma"),
                ("measuredLog2", "autoExposureMeasuredLog2"),
                ("measuredLuma", "autoExposureMeasuredLuma"),
                ("manual", "autoExposureManual"),
                ("scale", "autoExposureScale"),
                ("target", "autoExposureTarget"),
            ):
                perf_record_numeric(performance, metric, float(match.group(key)))
            perf_record_numeric(
                performance,
                "autoExposureHistogramFrames",
                int_group_any(match, "histogramFrames", "histogramFramesSlash"),
            )
            perf_record_numeric(
                performance,
                "autoExposureSimpleFrames",
                int_group_any(match, "simpleFrames", "simpleFramesSlash"),
            )
            perf_record_numeric(
                performance,
                "autoExposureSampleFailures",
                int_group_any(match, "sampleFailures", "sampleFailuresSlash"),
            )
            continue

        match = GLX_COLOR_GRADE_RE.search(line)
        if match:
            perf_record_string(performance, "colorGradeMode", match.group("mode").lower())
            for key in ("liftR", "liftG", "liftB", "gammaR", "gammaG", "gammaB", "gainR", "gainG", "gainB"):
                perf_record_numeric(performance, f"colorGrade{key[0].upper()}{key[1:]}", float(match.group(key)))
            perf_record_numeric(performance, "colorGradeWhiteSource", float(match.group("whiteSource")))
            perf_record_numeric(performance, "colorGradeWhiteTarget", float(match.group("whiteTarget")))
            perf_record_numeric(performance, "colorGradeLutSize", float(match.group("lutSize")))
            perf_record_numeric(performance, "colorGradeLutScale", float(match.group("lutScale")))
            continue

        match = GLX_OUTPUT_COLORIMETRY_RE.search(line)
        if match:
            perf_record_string(performance, "outputPrimaries", match.group("primaries").lower())
            perf_record_string(performance, "gamutMap", match.group("gamutMap").lower())
            perf_record_numeric(performance, "hdrPrecisionRequested", int_group(match, "precisionRequest"))
            perf_record_numeric(performance, "hdrPrecisionResolved", int_group(match, "precisionResolved"))
            continue

        match = GLX_COLOR_AUDIT_RE.search(line)
        if match:
            perf_record_numeric(performance, "colorSrgbDecode", 1 if q3_bool(match.group("srgbDecode")) else 0)
            perf_record_numeric(performance, "colorSrgbRequested", 1 if q3_bool(match.group("srgbRequested")) else 0)
            perf_record_numeric(performance, "colorSrgbAvailable", 1 if q3_bool(match.group("srgbAvailable")) else 0)
            perf_record_numeric(performance, "colorFramebufferSrgb", 1 if q3_bool(match.group("framebufferSrgb")) else 0)
            perf_record_numeric(performance, "colorFramebufferSrgbAvailable", 1 if q3_bool(match.group("framebufferAvailable")) else 0)
            perf_record_string(performance, "captureColorSpace", match.group("capture").lower())
            if match.group("captureRequest") is not None:
                perf_record_string(performance, "capturePolicyRequest", match.group("captureRequest").lower())
            if match.group("captureHdrAware") is not None:
                perf_record_numeric(performance, "captureHdrAware", 1 if q3_bool(match.group("captureHdrAware")) else 0)
            if match.group("captureSupported") is not None:
                perf_record_numeric(performance, "capturePolicySupported", 1 if q3_bool(match.group("captureSupported")) else 0)
            if match.group("targetFloat") is not None:
                perf_record_numeric(performance, "colorSceneTargetFloat", 1 if q3_bool(match.group("targetFloat")) else 0)
            if match.group("finalEncode") is not None:
                perf_record_string(performance, "colorFinalEncode", match.group("finalEncode").lower())
            if match.group("contract") is not None:
                perf_record_numeric(performance, "colorOutputContract", 1 if q3_bool(match.group("contract")) else 0)
            continue

        match = GLX_TEXTURE_AUDIT_RE.search(line)
        if match:
            for key in (
                "srgb",
                "srgbDecode",
                "linear",
                "linearDecode",
                "data",
                "dataDecode",
                "unknown",
                "unknownDecode",
                "missingSrgbDecode",
                "unexpectedDecode",
            ):
                perf_record_numeric(performance, f"textureAudit{key[0].upper()}{key[1:]}", int_group(match, key))
            continue

        match = GLX_COLOR_FRAME_JSON_RE.search(line)
        if match:
            try:
                payload = json.loads(match.group("payload"))
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                record_color_frame_performance(performance, payload)
            continue

        match = GLX_COLOR_FRAME_CSV_RE.search(line)
        if match:
            record_color_frame_performance(performance, color_frame_payload_from_csv(match))
            continue

        match = GLX_OUTPUT_BACKEND_RE.search(line)
        if match:
            perf_record_string(performance, "outputBackendRequest", match.group("request").lower())
            perf_record_string(performance, "outputBackendSelected", match.group("selected").lower())
            perf_record_string(performance, "outputBackendNative", match.group("native").lower())
            perf_record_numeric(performance, "outputBackendHardware", 1 if q3_bool(match.group("hardware")) else 0)
            perf_record_numeric(performance, "outputBackendExperimental", 1 if q3_bool(match.group("experimental")) else 0)
            perf_record_numeric(performance, "outputDisplayHdr", 1 if q3_bool(match.group("displayHdr")) else 0)
            perf_record_numeric(performance, "outputHeadroom", float(match.group("headroom")))
            perf_record_numeric(performance, "outputSdrWhiteNits", float(match.group("sdrWhite")))
            perf_record_numeric(performance, "outputDisplayMaxNits", float(match.group("displayMax")))
            perf_record_numeric(performance, "outputIccProfile", 1 if q3_bool(match.group("icc")) else 0)
            perf_record_numeric(performance, "outputIccProfileBytes", int_group(match, "iccBytes"))
            continue

        match = GLX_STREAM_DRAW_SUMMARY_RE.search(line)
        if match:
            perf_record_match_numbers_prefixed(
                performance,
                match,
                "streamDraw",
                ("draws", "attempts", "indexes", "fallbacks", "skips"),
            )
            for group, key in (
                ("multitexture", "streamDrawMultitexture"),
                ("fog", "streamDrawFog"),
                ("depthFragment", "streamDrawDepthFragment"),
                ("texMods", "streamDrawTexMods"),
                ("environment", "streamDrawEnvironment"),
                ("dynamicLights", "streamDrawDynamicLights"),
                ("screenMaps", "streamDrawScreenMaps"),
                ("videoMaps", "streamDrawVideoMaps"),
            ):
                perf_record_numeric(performance, key, int_group(match, group))
            if match.group("shadows") is not None:
                perf_record_numeric(performance, "streamDrawShadows", int(match.group("shadows")))
            if match.group("beams") is not None:
                perf_record_numeric(performance, "streamDrawBeams", int(match.group("beams")))
            if match.group("postprocess") is not None:
                perf_record_numeric(performance, "streamDrawPostProcess", int(match.group("postprocess")))
            for key in ("megabytes", "indexMegabytes", "tex1Megabytes"):
                perf_record_numeric(performance, prefixed_key("streamDraw", key), float(match.group(key)))
            continue

        match = GLX_STREAM_CATEGORY_SUMMARY_RE.search(line)
        if match:
            for category in STREAM_CATEGORY_KEYS:
                suffix = f"{category[0].upper()}{category[1:]}"
                perf_record_numeric(
                    performance,
                    f"streamCategory{suffix}Draws",
                    int_group(match, f"{category}Draws"),
                )
                perf_record_numeric(
                    performance,
                    f"streamCategory{suffix}Attempts",
                    int_group(match, f"{category}Attempts"),
                )
            continue

        match = GLX_STREAM_RESERVATION_SUMMARY_RE.search(line)
        if match:
            perf_record_string(performance, "streamReservationStrategy", match.group("strategy"))
            perf_record_numeric(performance, "streamReservationLastBytes", int_group(match, "lastBytes"))
            perf_record_numeric(performance, "streamReservationLargestBytes", int_group(match, "largestBytes"))
            perf_record_numeric(performance, "streamSameFrameWrapRejects", int_group(match, "sameFrameRejects"))
            continue

        match = STREAM_BINDING_CACHE_RE.search(line)
        if match:
            perf_record_numeric(performance, "streamBindingQueries", int_group(match, "queries"))
            perf_record_numeric(performance, "streamBindingCacheHits", int_group(match, "hits"))
            perf_record_numeric(performance, "streamBindingRestores", int_group(match, "restores"))
            perf_record_numeric(performance, "streamBindingInvalidations", int_group(match, "invalidations"))
            if match.group("external") is not None:
                perf_record_numeric(performance, "streamBindingExternalUpdates", int_group(match, "external"))
            continue

        match = GLX_STATIC_DRAW_SUMMARY_RE.search(line)
        if match:
            perf_record_match_numbers_prefixed(
                performance,
                match,
                "staticDraw",
                (
                    "calls",
                    "attempts",
                    "indexes",
                    "packetFull",
                    "packetPartial",
                    "packetMisses",
                    "manifestCalls",
                    "manifestIndexes",
                    "softCalls",
                    "softAttempts",
                    "softIndexes",
                    "arenaCalls",
                    "legacyCalls",
                    "fallbacks",
                    "policySkips",
                ),
            )
            continue

        match = GLX_STATIC_QUEUE_PACKETS_SUMMARY_RE.search(line)
        if match:
            perf_record_match_numbers_prefixed(
                performance,
                match,
                "staticQueuePackets",
                (
                    "lastFull",
                    "lastPartial",
                    "lastMisses",
                    "lastMismatches",
                    "full",
                    "partial",
                    "misses",
                ),
            )
            perf_record_numeric(performance, "staticQueuePacketMisses", int_group(match, "misses"))
            continue

        match = GLX_STATIC_PACKET_LOOKUP_SUMMARY_RE.search(line)
        if match:
            perf_record_match_numbers_prefixed(
                performance,
                match,
                "staticPacketLookup",
                ("mapped", "maxItem", "hits", "misses", "fallbacks", "mismatches", "overflows"),
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

        match = GLX_GL3X_PERFORMANCE_SUMMARY_RE.search(line)
        if match:
            perf_record_match_numbers_prefixed(
                performance,
                match,
                "gl3x",
                (
                    "draws",
                    "syncUploads",
                    "staticBuffers",
                    "dynamicBuffers",
                    "materials",
                    "fboPost",
                    "unsupportedPersistentUploads",
                ),
            )
            continue

        match = GLX_GL41_MAC_MODERN_SUMMARY_RE.search(line)
        if match:
            perf_record_match_numbers_prefixed(
                performance,
                match,
                "gl41",
                (
                    "draws",
                    "syncUploads",
                    "staticBuffers",
                    "dynamicBuffers",
                    "materials",
                    "post",
                    "unsupportedPersistentUploads",
                    "gl43Required",
                    "gl44Required",
                    "gl45Required",
                ),
            )
            continue

        match = GLX_GL46_HIGH_END_SUMMARY_RE.search(line)
        if match:
            perf_record_match_numbers_prefixed(
                performance,
                match,
                "gl46",
                (
                    "draws",
                    "persistentUploads",
                    "syncUploads",
                    "dsaProducts",
                    "mdiProducts",
                    "aggressiveStatic",
                    "materials",
                    "post",
                    "gpuCounters",
                    "staticMdiCalls",
                    "staticMdiAttempts",
                    "staticMdiIndexes",
                ),
            )
            continue

    return performance


def merge_budget(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    merged: dict[str, object] = {}
    for section in ("max", "min", "required"):
        values: dict[str, object] = {}
        base_section = base.get(section)
        override_section = override.get(section)
        if section == "required":
            required_values: list[object] = []
            if isinstance(base_section, (list, tuple)):
                required_values.extend(base_section)
            if isinstance(override_section, (list, tuple)):
                required_values.extend(override_section)
            if required_values:
                merged[section] = list(dict.fromkeys(required_values))
            continue
        if isinstance(base_section, dict):
            values.update(base_section)
        if isinstance(override_section, dict):
            values.update(override_section)
        if values:
            merged[section] = values

    tiers: dict[str, object] = {}
    base_tiers = base.get("tiers")
    override_tiers = override.get("tiers")
    if isinstance(base_tiers, dict):
        tiers.update(base_tiers)
    if isinstance(override_tiers, dict):
        for tier, tier_budget in override_tiers.items():
            if isinstance(tier_budget, dict) and isinstance(tiers.get(str(tier)), dict):
                tiers[str(tier)] = merge_budget(tiers[str(tier)], tier_budget)  # type: ignore[arg-type]
            else:
                tiers[str(tier)] = tier_budget
    if tiers:
        merged["tiers"] = tiers
    return merged


def load_json_file(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return data


def normalized_hex(value: object) -> str:
    if isinstance(value, int):
        return f"0x{value:04x}"
    text = str(value).strip().lower()
    if text.startswith("0x"):
        return f"0x{int(text, 16):04x}"
    return f"0x{int(text):04x}"


def texture_classification_manifest() -> dict[str, object]:
    manifest = load_json_file(TEXTURE_CLASSIFICATION_MANIFEST_PATH)
    rows = manifest.get("rows", [])
    if not isinstance(rows, list):
        rows = []
    manifest["rows"] = [row for row in rows if isinstance(row, dict)]
    return manifest


def color_sweep_matrix_manifest() -> list[dict[str, object]]:
    return [dict(row) for row in GLX_COLOR_SWEEP_MATRIX]


def color_contract_manifest() -> dict[str, object]:
    return {
        "version": GLX_COLOR_CONTRACT_VERSION,
        "sceneTargetFormat": dict(GLX_SCENE_TARGET_FORMAT_CONTRACT),
        "sdrOutput": dict(GLX_SDR_OUTPUT_CONTRACT),
        "imageEvidence": {
            "version": GLX_IMAGE_EVIDENCE_VERSION,
            "shaderReferenceRamp": {
                "width": GLX_SHADER_REFERENCE_RAMP_WIDTH,
                "height": GLX_SHADER_REFERENCE_RAMP_HEIGHT,
                "rows": list(GLX_SHADER_REFERENCE_RAMP_ROWS),
                "source": "deterministic-cpu-reference",
            },
            "requiredSidecars": list(GLX_IMAGE_EVIDENCE_SIDECARS),
            "metrics": ("psnr", "ssim", "histogram", "luma-false-color", "exposure-false-color"),
        },
        "textureClassificationManifest": texture_classification_manifest(),
        "colorSweepMatrix": color_sweep_matrix_manifest(),
    }


def validate_color_contract_manifest(manifest: dict[str, object]) -> list[str]:
    failures: list[str] = []
    contracts = manifest.get("colorContracts")
    if not isinstance(contracts, dict):
        return ["GLx color contract manifest is missing."]

    scene_target = contracts.get("sceneTargetFormat")
    if not isinstance(scene_target, dict):
        failures.append("GLx scene-target format contract is missing.")
    else:
        for key, expected in GLX_SCENE_TARGET_FORMAT_CONTRACT.items():
            actual = scene_target.get(key)
            if str(actual).lower() != str(expected).lower():
                failures.append(
                    f"GLx scene-target format contract {key} is {actual!r}; expected {expected!r}."
                )

    sdr_output = contracts.get("sdrOutput")
    if not isinstance(sdr_output, dict):
        failures.append("GLx SDR output contract is missing.")
    else:
        for key, expected in GLX_SDR_OUTPUT_CONTRACT.items():
            if sdr_output.get(key) != expected:
                failures.append(
                    f"GLx SDR output contract {key} is {sdr_output.get(key)!r}; expected {expected!r}."
                )

    image_evidence = contracts.get("imageEvidence")
    if not isinstance(image_evidence, dict):
        failures.append("GLx image evidence contract is missing.")
    else:
        if image_evidence.get("version") != GLX_IMAGE_EVIDENCE_VERSION:
            failures.append(
                "GLx image evidence contract version is "
                f"{image_evidence.get('version')!r}; expected {GLX_IMAGE_EVIDENCE_VERSION!r}."
            )
        ramp = image_evidence.get("shaderReferenceRamp")
        if not isinstance(ramp, dict):
            failures.append("GLx shader reference ramp contract is missing.")
        else:
            if ramp.get("width") != GLX_SHADER_REFERENCE_RAMP_WIDTH:
                failures.append("GLx shader reference ramp width does not match the deterministic contract.")
            if ramp.get("height") != GLX_SHADER_REFERENCE_RAMP_HEIGHT:
                failures.append("GLx shader reference ramp height does not match the deterministic contract.")
            if tuple(ramp.get("rows", ())) != GLX_SHADER_REFERENCE_RAMP_ROWS:
                failures.append("GLx shader reference ramp rows do not match the deterministic contract.")
        required_sidecars = tuple(image_evidence.get("requiredSidecars", ()))
        if required_sidecars != GLX_IMAGE_EVIDENCE_SIDECARS:
            failures.append("GLx image evidence required sidecars do not match the deterministic contract.")

    texture_manifest = contracts.get("textureClassificationManifest")
    rows = texture_manifest.get("rows", []) if isinstance(texture_manifest, dict) else []
    if not isinstance(rows, list):
        rows = []
    if not isinstance(texture_manifest, dict):
        failures.append("Texture color classification manifest is missing.")
    else:
        if texture_manifest.get("version") != GLX_COLOR_CONTRACT_VERSION:
            failures.append(
                "Texture color classification manifest version is "
                f"{texture_manifest.get('version')!r}; expected {GLX_COLOR_CONTRACT_VERSION!r}."
            )
        if texture_manifest.get("document") != GLX_TEXTURE_CLASSIFICATION_DOC:
            failures.append(
                "Texture color classification manifest document is "
                f"{texture_manifest.get('document')!r}; expected {GLX_TEXTURE_CLASSIFICATION_DOC!r}."
            )
    row_by_id = {
        str(row.get("id")): row
        for row in rows
        if isinstance(row, dict) and str(row.get("id", "")).strip()
    }
    missing_rows = [
        row_id for row_id in GLX_REQUIRED_TEXTURE_CLASS_ROWS if row_id not in row_by_id
    ]
    if missing_rows:
        failures.append(
            "Texture color classification manifest is missing row(s): " +
            ", ".join(missing_rows) + "."
        )
    for row_id in GLX_REQUIRED_TEXTURE_CLASS_ROWS:
        row = row_by_id.get(row_id)
        if not row:
            continue
        for key in ("declaredSpace", "sceneLinearDecode", "examples", "codePath"):
            if key not in row or row.get(key) in ("", [], None):
                failures.append(
                    f"Texture color classification manifest row {row_id} is missing {key}."
                )
        for key, expected in GLX_TEXTURE_CLASSIFICATION_CONTRACT[row_id].items():
            actual = row.get(key)
            if actual != expected:
                failures.append(
                    f"Texture color classification manifest row {row_id} {key} "
                    f"is {actual!r}; expected {expected!r}."
                )

    matrix = contracts.get("colorSweepMatrix")
    matrix_rows = matrix if isinstance(matrix, list) else []
    matrix_ids = {
        str(row.get("id"))
        for row in matrix_rows
        if isinstance(row, dict) and str(row.get("id", "")).strip()
    }
    expected_ids = {str(row["id"]) for row in GLX_COLOR_SWEEP_MATRIX}
    if matrix_ids != expected_ids:
        failures.append(
            "GLx color sweep matrix contract does not match the required P0 rows: "
            f"{','.join(sorted(matrix_ids)) or '-'}; expected {','.join(sorted(expected_ids))}."
        )

    return failures


def validate_image_evidence_manifest(manifest: dict[str, object]) -> list[str]:
    failures: list[str] = []
    evidence = manifest.get("imageEvidence")
    if not isinstance(evidence, dict):
        return ["GLx image evidence manifest is missing."]
    if evidence.get("version") != GLX_IMAGE_EVIDENCE_VERSION:
        failures.append(
            "GLx image evidence manifest version is "
            f"{evidence.get('version')!r}; expected {GLX_IMAGE_EVIDENCE_VERSION!r}."
        )
    if tuple(evidence.get("requiredSidecars", ())) != GLX_IMAGE_EVIDENCE_SIDECARS:
        failures.append("GLx image evidence manifest sidecar contract does not match the deterministic registry.")

    ramps = evidence.get("shaderReferenceRamps")
    ramp_rows = ramps if isinstance(ramps, list) else []
    expected_row_ids = {str(row["id"]) for row in GLX_COLOR_SWEEP_MATRIX}
    actual_row_ids = {
        str(row.get("rowId"))
        for row in ramp_rows
        if isinstance(row, dict) and str(row.get("rowId", "")).strip()
    }
    if actual_row_ids != expected_row_ids:
        failures.append(
            "GLx shader-vs-reference ramp evidence does not cover every color-sweep row: "
            f"{','.join(sorted(actual_row_ids)) or '-'}; expected {','.join(sorted(expected_row_ids))}."
        )
    for row in ramp_rows:
        if not isinstance(row, dict):
            continue
        row_id = str(row.get("rowId", ""))
        if row.get("width") != GLX_SHADER_REFERENCE_RAMP_WIDTH or row.get("height") != GLX_SHADER_REFERENCE_RAMP_HEIGHT:
            failures.append(f"GLx shader reference ramp {row_id or '-'} has unexpected dimensions.")
        if tuple(row.get("rampRows", ())) != GLX_SHADER_REFERENCE_RAMP_ROWS:
            failures.append(f"GLx shader reference ramp {row_id or '-'} has unexpected ramp-row metadata.")
        histogram = row.get("histogram")
        if not isinstance(histogram, dict) or histogram.get("status") != "passed":
            failures.append(f"GLx shader reference ramp {row_id or '-'} is missing histogram metadata.")
        for key in ("path", "histogramPath", "falseColorPath", "exposureFalseColorPath"):
            if not str(row.get(key, "")).strip():
                failures.append(f"GLx shader reference ramp {row_id or '-'} is missing {key}.")
    return failures


def load_performance_budget(path: Path | None, include_default: bool) -> dict[str, object]:
    budget = dict(DEFAULT_PERFORMANCE_BUDGET) if include_default else {}
    if path is not None:
        loaded = load_json_file(path.resolve())
        budget = merge_budget(budget, loaded)
    return budget


def performance_budget_for_gate(
    gate: str | None,
    budget: dict[str, object],
) -> dict[str, object]:
    gate_name = str(gate or "").strip()
    override = GLX_GATE_PERFORMANCE_BUDGET_OVERRIDES.get(gate_name)
    if isinstance(override, dict):
        return merge_budget(budget, override)
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


def performance_budget_tier(aggregate: dict[str, object]) -> str:
    latest = aggregate.get("latest", {})
    value: object | None = None
    if isinstance(latest, dict):
        value = latest.get("productTier", latest.get("tier"))
    if value is None:
        value = aggregate.get("productTier", aggregate.get("tier"))
    return str(value or "").upper()


def evaluate_performance_budget_section(
    aggregate: dict[str, object],
    section_budget: dict[str, object],
    label: str = "",
) -> list[str]:
    failures: list[str] = []
    prefix = f"Performance budget {label} " if label else "Performance budget "

    required = section_budget.get("required", ())
    if isinstance(required, (list, tuple)):
        for key in required:
            metric_key = str(key)
            if performance_metric(aggregate, metric_key) is None:
                failures.append(f"{prefix}required metric {metric_key} is missing.")

    max_budget = section_budget.get("max", {})
    if isinstance(max_budget, dict):
        for key, threshold in sorted(max_budget.items()):
            value = numeric_metric(aggregate, str(key))
            if value is None or not isinstance(threshold, (int, float)):
                continue
            if value > float(threshold):
                failures.append(f"{prefix}max {key} exceeded: {value:g} > {float(threshold):g}.")

    min_budget = section_budget.get("min", {})
    if isinstance(min_budget, dict):
        for key, threshold in sorted(min_budget.items()):
            value = numeric_metric(aggregate, str(key))
            if value is None or not isinstance(threshold, (int, float)):
                continue
            if value < float(threshold):
                failures.append(f"{prefix}min {key} missed: {value:g} < {float(threshold):g}.")

    return failures


def evaluate_performance_budget(
    aggregate: dict[str, object],
    budget: dict[str, object],
) -> list[str]:
    failures = evaluate_performance_budget_section(aggregate, budget)

    tier = performance_budget_tier(aggregate)
    tiers = budget.get("tiers", {})
    if tier and isinstance(tiers, dict):
        tier_budget = tiers.get(tier)
        if isinstance(tier_budget, dict):
            failures.extend(evaluate_performance_budget_section(aggregate, tier_budget, tier))

    return list(dict.fromkeys(failures))


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
        "proofCorpus": manifest.get("proofCorpus", {}),
        "performance": aggregate,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8", newline="\n")


def manifest_screenshots(manifest: dict[str, object]) -> list[dict[str, object]]:
    runs = manifest.get("runs", [])
    if not isinstance(runs, list):
        return []
    return [
        shot
        for run in runs
        if isinstance(run, dict)
        for shot in run.get("screenshots", [])
        if isinstance(shot, dict)
    ]


def proof_status(manifest: dict[str, object]) -> dict[str, object]:
    dry_run = bool(manifest.get("dryRun"))
    screenshots = manifest_screenshots(manifest)
    visual = {
        "status": "not-configured",
        "baselineDir": str(manifest.get("screenshotBaselineDir", "")),
        "diffDir": str(manifest.get("screenshotDiffDir", "")),
        "screenshots": len(screenshots),
        "found": sum(1 for shot in screenshots if shot.get("found")),
        "approved": sum(1 for shot in screenshots if shot.get("baselineStatus") == "approved"),
        "passed": sum(1 for shot in screenshots if shot.get("baselineStatus") == "passed"),
        "missing": sum(1 for shot in screenshots if shot.get("baselineStatus") == "missing"),
        "failed": sum(
            1
            for shot in screenshots
            if shot.get("baselineStatus") == "failed" or
            (isinstance(shot.get("comparison"), dict) and shot["comparison"].get("status") == "failed")  # type: ignore[index]
        ),
    }
    if visual["baselineDir"]:
        if dry_run:
            visual["status"] = "planned"
        elif manifest.get("approveScreenshotBaselines"):
            visual["status"] = (
                "approved"
                if visual["screenshots"] and
                visual["found"] == visual["screenshots"] and
                visual["approved"] == visual["screenshots"]
                else "failed"
            )
        elif visual["missing"] or visual["failed"] or visual["found"] != visual["screenshots"]:
            visual["status"] = "failed"
        elif visual["screenshots"] and visual["passed"] == visual["screenshots"]:
            visual["status"] = "passed"
        else:
            visual["status"] = "not-compared"

    comparisons = [
        comparison
        for comparison in manifest.get("performanceComparisons", [])
        if isinstance(comparison, dict)
    ]
    performance_failures = [
        failure
        for failure in manifest.get("performanceFailures", [])
        if str(failure).strip()
    ]
    failed_comparisons = [
        comparison
        for comparison in comparisons
        if comparison.get("status") != "passed"
    ]
    performance = {
        "status": "not-configured",
        "baselinePath": str(manifest.get("performanceBaselinePath", "")),
        "sampleCount": int(
            manifest.get("performanceAggregate", {}).get("sampleCount", 0)  # type: ignore[union-attr]
            if isinstance(manifest.get("performanceAggregate"), dict)
            else 0
        ),
        "comparisons": len(comparisons),
        "failedComparisons": len(failed_comparisons),
        "failures": len(performance_failures),
        "baselineStatus": str(manifest.get("performanceBaselineStatus", "")),
    }
    if performance["baselinePath"]:
        if dry_run:
            performance["status"] = "planned"
        elif manifest.get("approvePerformanceBaseline"):
            performance["status"] = "approved" if performance["baselineStatus"] == "approved" else "failed"
        elif performance_failures:
            performance["status"] = "failed"
        elif performance["baselineStatus"] == "compared" and not comparisons:
            performance["status"] = "not-compared"
        elif performance["baselineStatus"] == "compared" and not failed_comparisons:
            performance["status"] = "passed"
        elif performance["baselineStatus"] in {"missing", "not-sampled"} or failed_comparisons:
            performance["status"] = "failed"
        else:
            performance["status"] = performance["baselineStatus"] or "not-compared"

    configured_statuses = [
        str(item.get("status"))
        for item in (visual, performance)
        if item.get("status") != "not-configured"
    ]
    if dry_run and configured_statuses:
        status = "planned"
    elif configured_statuses and all(item in {"passed", "approved"} for item in configured_statuses):
        status = "passed"
    elif any(item == "failed" for item in configured_statuses):
        status = "failed"
    else:
        status = "incomplete" if configured_statuses else "not-configured"

    return {
        "status": status,
        "visual": visual,
        "performance": performance,
    }


def evaluate_proof_corpus(
    manifest: dict[str, object],
    requirements: dict[str, object],
) -> list[str]:
    if not requirements.get("require_proof_corpus"):
        return []

    failures: list[str] = []
    proof_corpus = manifest.get("proofCorpus")
    if not isinstance(proof_corpus, dict):
        return ["GLx proof corpus metadata is missing from the gate manifest."]

    if proof_corpus.get("version") != GLX_PROOF_CORPUS_VERSION:
        failures.append(
            "GLx proof corpus version mismatch: "
            f"{proof_corpus.get('version', '-')}; expected {GLX_PROOF_CORPUS_VERSION}."
        )
    if proof_corpus.get("document") != GLX_PROOF_CORPUS_DOC:
        failures.append(
            "GLx proof corpus document mismatch: "
            f"{proof_corpus.get('document', '-')}; expected {GLX_PROOF_CORPUS_DOC}."
        )
    if proof_corpus.get("paritySuiteVersion") != GLX_PARITY_SUITE_VERSION:
        failures.append(
            "GLx parity suite version mismatch: "
            f"{proof_corpus.get('paritySuiteVersion', '-')}; expected {GLX_PARITY_SUITE_VERSION}."
        )
    if proof_corpus.get("imageEvidenceVersion") != GLX_IMAGE_EVIDENCE_VERSION:
        failures.append(
            "GLx image evidence version mismatch: "
            f"{proof_corpus.get('imageEvidenceVersion', '-')}; expected {GLX_IMAGE_EVIDENCE_VERSION}."
        )

    selected_scene_ids = [
        str(scene_id)
        for scene_id in proof_corpus.get("selectedSceneIds", [])
        if str(scene_id).strip()
    ]
    try:
        selected_scene_ids = validate_corpus_scene_ids(selected_scene_ids)
    except ValueError as exc:
        failures.append(str(exc))
        selected_scene_ids = []

    if not selected_scene_ids:
        failures.append("GLx proof corpus selection is empty.")

    selected_tags = {
        str(tag)
        for tag in proof_corpus.get("selectedTags", [])
        if str(tag).strip()
    }
    expected_tags = set(corpus_tags(selected_scene_ids)) if selected_scene_ids else set()
    if selected_tags != expected_tags:
        failures.append(
            "GLx proof corpus selected tags do not match selected scene ids: "
            f"{','.join(sorted(selected_tags)) or '-'}; expected "
            f"{','.join(sorted(expected_tags)) or '-'}."
        )

    required_tags = {
        str(tag)
        for tag in requirements.get("required_corpus_tags", [])
        if str(tag).strip()
    }
    missing_tags = sorted(required_tags.difference(selected_tags))
    if missing_tags:
        failures.append(
            "GLx proof corpus is missing required tag(s): " +
            ", ".join(missing_tags)
        )

    selected_parity_suite_ids = [
        str(suite_id)
        for suite_id in proof_corpus.get("paritySuiteIds", [])
        if str(suite_id).strip()
    ]
    try:
        selected_parity_suite_ids = validate_parity_suite_ids(selected_parity_suite_ids)
    except ValueError as exc:
        failures.append(str(exc))
        selected_parity_suite_ids = []

    required_parity_suite_ids = {
        str(suite_id)
        for suite_id in requirements.get("required_parity_suites", [])
        if str(suite_id).strip()
    }
    missing_parity_suite_ids = sorted(required_parity_suite_ids.difference(selected_parity_suite_ids))
    if missing_parity_suite_ids:
        failures.append(
            "GLx parity suite(s) missing from proof corpus: " +
            ", ".join(missing_parity_suite_ids)
        )

    actual_suite_records = proof_corpus.get("paritySuites", [])
    expected_suite_records = parity_suite_records(selected_parity_suite_ids)
    if actual_suite_records != expected_suite_records:
        failures.append("GLx parity suite records do not match the versioned suite registry.")

    selected_scene_records = proof_corpus.get("selectedScenes", [])
    expected_scene_records = corpus_scene_records(selected_scene_ids)
    if selected_scene_records != expected_scene_records:
        failures.append("GLx proof corpus scene records do not match the versioned scene/image-evidence registry.")

    selected_scene_id_set = set(selected_scene_ids)
    for suite_id in selected_parity_suite_ids:
        suite = GLX_PARITY_SUITES[suite_id]
        suite_scene_ids = validate_corpus_scene_ids(suite.get("sceneIds", ()))
        missing_suite_scene_ids = sorted(set(suite_scene_ids).difference(selected_scene_id_set))
        if missing_suite_scene_ids:
            failures.append(
                f"GLx parity suite {suite_id} scene(s) not selected: " +
                ", ".join(missing_suite_scene_ids)
            )

        suite_required_tags = {
            str(tag)
            for tag in suite.get("requiredTags", ())
            if str(tag).strip()
        }
        missing_suite_tags = sorted(suite_required_tags.difference(selected_tags))
        if missing_suite_tags:
            failures.append(
                f"GLx parity suite {suite_id} is missing required tag(s): " +
                ", ".join(missing_suite_tags)
            )

    manifest_maps = {
        str(map_name).lower()
        for map_name in manifest.get("maps", [])
        if str(map_name).strip()
    }
    manifest_demos = {
        str(demo).lower()
        for demo in manifest.get("demos", [])
        if str(demo).strip()
    }
    missing_maps = [
        str(GLX_PROOF_CORPUS_SCENES[scene_id]["target"])
        for scene_id in selected_scene_ids
        if GLX_PROOF_CORPUS_SCENES[scene_id].get("kind") == "map" and
        str(GLX_PROOF_CORPUS_SCENES[scene_id].get("target", "")).lower() not in manifest_maps
    ]
    missing_demos = [
        str(GLX_PROOF_CORPUS_SCENES[scene_id]["target"])
        for scene_id in selected_scene_ids
        if GLX_PROOF_CORPUS_SCENES[scene_id].get("kind") == "demo" and
        str(GLX_PROOF_CORPUS_SCENES[scene_id].get("target", "")).lower() not in manifest_demos
    ]
    if missing_maps:
        failures.append(
            "GLx proof corpus map scene(s) were not included in the sweep maps: " +
            ", ".join(_dedupe(missing_maps))
        )
    if missing_demos:
        failures.append(
            "GLx proof corpus demo scene(s) were not included in the sweep demos: " +
            ", ".join(_dedupe(missing_demos))
        )

    return failures


def color_sweep_runs(manifest: dict[str, object]) -> list[dict[str, object]]:
    runs = manifest.get("runs", [])
    if not isinstance(runs, list):
        return []
    return [
        run
        for run in runs
        if isinstance(run, dict) and run.get("type") == "color-sweep"
    ]


def color_sweep_row_id(run: dict[str, object]) -> str:
    row = run.get("colorSweepRow")
    return str(row.get("id", "")) if isinstance(row, dict) else ""


def color_sweep_metric(run: dict[str, object], section: str, key: str) -> object | None:
    diagnostics = run.get("diagnostics")
    if isinstance(diagnostics, dict):
        metrics = diagnostics.get("metrics")
        if isinstance(metrics, dict):
            metric_section = metrics.get(section)
            if isinstance(metric_section, dict) and key in metric_section:
                return metric_section[key]

    performance = run.get("performance")
    if isinstance(performance, dict):
        latest = performance.get("latest")
        if isinstance(latest, dict):
            performance_key = {
                ("colorPipeline", "space"): "colorSpace",
                ("colorPipeline", "transfer"): "outputTransfer",
                ("colorPipeline", "toneMap"): "toneMap",
                ("colorPipeline", "exposure"): "toneMapExposure",
                ("colorPipeline", "paperWhite"): "paperWhiteNits",
                ("colorPipeline", "maxOutput"): "maxOutputNits",
                ("colorAudit", "targetFloat"): "colorSceneTargetFloat",
                ("colorAudit", "finalEncode"): "colorFinalEncode",
                ("colorAudit", "contract"): "colorOutputContract",
                ("colorAudit", "framebufferSrgb"): "colorFramebufferSrgb",
                ("colorAudit", "srgbRequested"): "colorSrgbRequested",
                ("outputBackend", "request"): "outputBackendRequest",
                ("outputBackend", "selected"): "outputBackendSelected",
                ("targetFormat", "internalFormat"): "targetInternalFormat",
                ("targetFormat", "textureFormat"): "targetTextureFormat",
                ("targetFormat", "textureType"): "targetTextureType",
            }.get((section, key))
            if performance_key and performance_key in latest:
                return latest[performance_key]

    return None


def screenshot_luma_false_color_passed(shot: dict[str, object]) -> bool:
    false_color = shot.get("falseColor")
    if isinstance(false_color, dict):
        status = str(false_color.get("status", "")).strip().lower()
        if status == "failed":
            return False
        if status == "passed":
            return True
    path = shot.get("falseColorPath")
    return isinstance(path, str) and bool(path.strip())


def screenshot_exposure_false_color_passed(shot: dict[str, object]) -> bool:
    false_color = shot.get("exposureFalseColor")
    if isinstance(false_color, dict):
        status = str(false_color.get("status", "")).strip().lower()
        if status == "failed":
            return False
        if status == "passed":
            return True
    path = shot.get("exposureFalseColorPath")
    return isinstance(path, str) and bool(path.strip())


def renderer_switch_lifecycle_evidence(manifest: dict[str, object]) -> dict[str, object]:
    maps = [
        str(map_name)
        for map_name in manifest.get("maps", [])
        if str(map_name).strip()
    ]
    sequence = [
        str(renderer).strip().lower()
        for renderer in manifest.get("switchSequence", [])
        if str(renderer).strip()
    ]
    switch_rounds = int(manifest.get("switchRounds", 1) or 1)
    dry_run = bool(manifest.get("dryRun"))
    runs = [
        run
        for run in manifest.get("runs", [])
        if isinstance(run, dict) and run.get("type") == "switch-screenshots"
    ]

    expected_records = [
        {
            "map": map_name,
            "round": round_index,
            "step": switch_index,
            "renderer": renderer,
        }
        for map_name in maps
        for round_index in range(1, switch_rounds + 1)
        for switch_index, renderer in enumerate(sequence, start=1)
    ]
    expected_keys = {
        (
            str(record["map"]),
            int(record["round"]),
            int(record["step"]),
            str(record["renderer"]).lower(),
        )
        for record in expected_records
    }
    expected_transitions = len(expected_records)
    screenshots: list[dict[str, object]] = []
    run_statuses: list[str] = []
    restart_modes: set[str] = set()
    restart_paths: set[str] = set()
    vid_restart_equivalent = False
    glx_diagnostics_found = False
    glx_performance_samples = 0
    transitions: list[dict[str, object]] = []

    for run in runs:
        run_statuses.append(str(run.get("status", "unknown")))
        restart_mode = str(run.get("restartMode", "fast")).strip().lower() or "fast"
        restart_modes.add(restart_mode)
        restart_path = str(run.get("vidRestartPath", "")).strip()
        if restart_path:
            restart_paths.add(restart_path)
        if run.get("vidRestartEquivalent") or restart_mode in {"fast", "keep_window", "full", "destroy_window"}:
            vid_restart_equivalent = True
        diagnostics = run.get("diagnostics")
        if isinstance(diagnostics, dict) and diagnostics.get("found"):
            glx_diagnostics_found = True
        performance = run.get("performance")
        if isinstance(performance, dict):
            try:
                glx_performance_samples += int(performance.get("sampleCount", 0))
            except (TypeError, ValueError):
                pass
        for shot in run.get("screenshots", []):
            if isinstance(shot, dict):
                screenshots.append(shot)

    completed_expected_keys: set[tuple[str, int, int, str]] = set()
    unexpected_transitions: list[dict[str, object]] = []
    for shot in screenshots:
        try:
            shot_key = (
                str(shot.get("map", "")),
                int(shot.get("round", 0) or 0),
                int(shot.get("switchStep", 0) or 0),
                str(shot.get("renderer", "")).strip().lower(),
            )
        except (TypeError, ValueError):
            shot_key = ("", 0, 0, "")
        if not shot.get("found"):
            continue
        if expected_keys:
            if shot_key in expected_keys:
                completed_expected_keys.add(shot_key)
            else:
                unexpected_transitions.append(
                    {
                        "map": shot.get("map", ""),
                        "round": shot.get("round", 0),
                        "step": shot.get("switchStep", 0),
                        "renderer": str(shot.get("renderer", "")).lower(),
                        "screenshot": shot.get("name", ""),
                    }
                )

    observed_transitions = (
        len(completed_expected_keys)
        if expected_keys
        else sum(1 for shot in screenshots if shot.get("found"))
    )
    planned_transitions = expected_transitions if expected_transitions else len(screenshots)
    missing_transition_records = [
        record
        for record in expected_records
        if (
            str(record["map"]),
            int(record["round"]),
            int(record["step"]),
            str(record["renderer"]).lower(),
        ) not in completed_expected_keys
    ]
    missing_transitions = [] if dry_run else missing_transition_records
    if dry_run:
        status = "planned"
    else:
        status = "passed"
        if not runs or planned_transitions <= 0:
            status = "failed"
        if any(run_status != "passed" for run_status in run_statuses):
            status = "failed"
        if observed_transitions < planned_transitions or missing_transition_records:
            status = "failed"

    renderer_set = set(sequence)
    transition_pairs = [
        (sequence[index], sequence[index + 1])
        for index in range(len(sequence) - 1)
    ]
    transitions_into_glx = sum(1 for source, target in transition_pairs if target == "glx" and source != "glx")
    transitions_out_of_glx = sum(1 for source, target in transition_pairs if source == "glx" and target != "glx")

    for shot in screenshots:
        transitions.append(
            {
                "map": shot.get("map", ""),
                "round": shot.get("round", 0),
                "step": shot.get("switchStep", 0),
                "renderer": str(shot.get("renderer", "")).lower(),
                "screenshot": shot.get("name", ""),
                "found": bool(shot.get("found")),
                "baselineStatus": shot.get("baselineStatus", ""),
            }
        )

    return {
        "version": GLX_SWITCH_LIFECYCLE_VERSION,
        "status": status,
        "command": "renderer_switch",
        "restartMode": ",".join(sorted(restart_modes)) if restart_modes else "fast",
        "vidRestartPath": ",".join(sorted(restart_paths)) if restart_paths else "",
        "vidRestartEquivalent": vid_restart_equivalent,
        "plannedTransitions": planned_transitions,
        "expectedTransitions": expected_transitions,
        "completedTransitions": observed_transitions,
        "maps": maps,
        "switchRounds": switch_rounds,
        "sequence": sequence,
        "sawLegacyRenderer": any(renderer != "glx" for renderer in renderer_set),
        "sawGlxRenderer": "glx" in renderer_set,
        "transitionsIntoGlx": transitions_into_glx,
        "transitionsOutOfGlx": transitions_out_of_glx,
        "glxDiagnosticsFound": glx_diagnostics_found,
        "glxPerformanceSamples": glx_performance_samples,
        "missingTransitions": missing_transitions,
        "unexpectedTransitions": unexpected_transitions,
        "runStatuses": run_statuses,
        "transitions": transitions,
    }


def evaluate_renderer_switch_lifecycle(manifest: dict[str, object], requirements: dict[str, object]) -> list[str]:
    if not requirements.get("require_renderer_switch_lifecycle"):
        return []

    evidence = manifest.get("rendererSwitchEvidence")
    if not isinstance(evidence, dict):
        return ["No renderer-switch lifecycle evidence was recorded."]

    failures: list[str] = []
    if evidence.get("version") != GLX_SWITCH_LIFECYCLE_VERSION:
        failures.append(
            "Renderer-switch lifecycle evidence has unsupported version "
            f"{evidence.get('version')!r}."
        )
    if evidence.get("status") != "passed":
        failures.append(
            "Renderer-switch lifecycle evidence status is "
            f"{evidence.get('status')!r}, expected 'passed'."
        )
    if not evidence.get("vidRestartEquivalent"):
        failures.append("Renderer-switch lifecycle did not record vid_restart-equivalent restart mode.")
    if int(evidence.get("plannedTransitions", 0) or 0) <= 0:
        failures.append("Renderer-switch lifecycle did not plan any transitions.")
    if int(evidence.get("completedTransitions", 0) or 0) < int(evidence.get("plannedTransitions", 0) or 0):
        failures.append(
            "Renderer-switch lifecycle did not complete every planned transition "
            f"({evidence.get('completedTransitions', 0)}/{evidence.get('plannedTransitions', 0)})."
        )
    if not evidence.get("sawLegacyRenderer"):
        failures.append("Renderer-switch lifecycle did not include a legacy renderer leg.")
    if not evidence.get("sawGlxRenderer"):
        failures.append("Renderer-switch lifecycle did not include a GLx renderer leg.")
    if int(evidence.get("transitionsIntoGlx", 0) or 0) <= 0:
        failures.append("Renderer-switch lifecycle did not switch into GLx.")
    if requirements.get("require_renderer_switch_roundtrip") and int(evidence.get("transitionsOutOfGlx", 0) or 0) <= 0:
        failures.append("Renderer-switch lifecycle did not switch back out of GLx.")
    if requirements.get("require_glx_diagnostics") and not evidence.get("glxDiagnosticsFound"):
        failures.append("Renderer-switch lifecycle did not collect GLx diagnostics after a GLx leg.")
    if requirements.get("require_glx_performance_samples") and int(evidence.get("glxPerformanceSamples", 0) or 0) <= 0:
        failures.append("Renderer-switch lifecycle did not collect GLx performance samples after a GLx leg.")
    return failures


def int_metric(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def float_metric(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def manifest_requires_world_proof(
    manifest: dict[str, object],
    requirements: dict[str, object],
) -> bool:
    return bool(requirements.get("require_world_proof"))


def manifest_selected_scene_ids(manifest: dict[str, object]) -> list[str]:
    proof_corpus = manifest.get("proofCorpus")
    scene_ids: list[str] = []
    if isinstance(proof_corpus, dict):
        scene_ids = [
            str(scene_id)
            for scene_id in proof_corpus.get("selectedSceneIds", [])
            if str(scene_id).strip()
        ]
    if not scene_ids:
        gate = str(manifest.get("gate", ""))
        scene_ids = [str(scene_id) for scene_id in GLX_GATE_CORPUS_SCENES.get(gate, ())]
    return [
        scene_id
        for scene_id in scene_ids
        if scene_id in GLX_PROOF_CORPUS_SCENES
    ]


def world_scene_records(
    manifest: dict[str, object],
    requirements: dict[str, object],
) -> list[dict[str, object]]:
    required_tags = {
        str(tag)
        for tag in requirements.get("required_world_tags", ())
        if str(tag).strip()
    }
    world_tags = set(GLX_WORLD_PROOF_TAGS)
    records: list[dict[str, object]] = []
    for scene_id in manifest_selected_scene_ids(manifest):
        scene = GLX_PROOF_CORPUS_SCENES[scene_id]
        if scene.get("kind") != "map":
            continue
        tags = {str(tag) for tag in scene.get("tags", ()) if str(tag).strip()}
        if not tags.intersection(world_tags) and not tags.intersection(required_tags):
            continue
        records.append(
            {
                "sceneId": scene_id,
                "map": str(scene.get("target", "")).strip().lower(),
                "assetTier": scene.get("assetTier", ""),
                "tags": sorted(tags),
                "required": bool(tags.intersection(required_tags)),
            }
        )
    return records


def manifest_glx_screenshot_records(manifest: dict[str, object]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    runs = manifest.get("runs", [])
    if not isinstance(runs, list):
        return records

    for run_index, run in enumerate(runs, start=1):
        if not isinstance(run, dict):
            continue
        run_renderer = str(run.get("renderer", "")).strip().lower()
        run_map = str(run.get("map", "")).strip().lower()
        run_type = str(run.get("type", f"run-{run_index}"))
        screenshots = run.get("screenshots", [])
        if not isinstance(screenshots, list):
            continue
        for shot in screenshots:
            if not isinstance(shot, dict):
                continue
            renderer = str(shot.get("renderer", run_renderer)).strip().lower()
            map_name = str(shot.get("map", run_map)).strip().lower()
            if renderer != "glx" or not map_name:
                continue
            histogram = shot.get("histogram")
            records.append(
                {
                    "run": run_type,
                    "map": map_name,
                    "name": shot.get("name", ""),
                    "found": bool(shot.get("found")),
                    "baselineStatus": shot.get("baselineStatus", ""),
                    "histogramPassed": (
                        isinstance(histogram, dict)
                        and histogram.get("status") == "passed"
                    ),
                    "comparisonStatus": (
                        shot.get("comparison", {}).get("status", "")
                        if isinstance(shot.get("comparison"), dict)
                        else ""
                    ),
                }
            )
    return records


def performance_numeric_value(performance: dict[str, object], key: str) -> int:
    for section_name in ("max", "latest"):
        section = performance.get(section_name)
        if isinstance(section, dict) and key in section:
            return int_metric(section.get(key))
    return int_metric(performance.get(key))


def world_proof_evidence(
    manifest: dict[str, object],
    requirements: dict[str, object],
) -> dict[str, object]:
    dry_run = bool(manifest.get("dryRun"))
    require_world = manifest_requires_world_proof(manifest, requirements)
    required_tags = sorted(
        {
            str(tag)
            for tag in requirements.get("required_world_tags", ())
            if str(tag).strip()
        }
    )
    proof_corpus = manifest.get("proofCorpus")
    selected_tags = sorted(
        {
            str(tag)
            for tag in (
                proof_corpus.get("selectedTags", [])
                if isinstance(proof_corpus, dict)
                else []
            )
            if str(tag).strip()
        }
    )
    scene_records = world_scene_records(manifest, requirements)
    required_scene_records = [
        record for record in scene_records if bool(record.get("required"))
    ]
    required_maps = sorted(
        {
            str(record.get("map", ""))
            for record in required_scene_records
            if str(record.get("map", "")).strip()
        }
    )
    lightmap_maps = sorted(
        {
            str(record.get("map", ""))
            for record in scene_records
            if "lightmap" in record.get("tags", ())
        }
    )
    fog_maps = sorted(
        {
            str(record.get("map", ""))
            for record in scene_records
            if "fog-heavy" in record.get("tags", ())
        }
    )

    screenshots = manifest_glx_screenshot_records(manifest)
    found_screenshot_maps = sorted(
        {
            str(record.get("map", ""))
            for record in screenshots
            if record.get("found")
        }
    )
    histogram_maps = sorted(
        {
            str(record.get("map", ""))
            for record in screenshots
            if record.get("found") and record.get("histogramPassed")
        }
    )
    screenshot_map_set = set(found_screenshot_maps)
    histogram_map_set = set(histogram_maps)

    static_renderer_enabled = 0
    static_arena_ready = 0
    static_packet_batch_enabled = 0
    static_packet_batches = 0
    static_indirect_ready = 0
    static_gl_errors = 0
    static_failures = 0
    static_draw_attempts = 0
    static_draw_indexes = 0
    static_draw_fallbacks = 0
    static_packet_full = 0
    static_packet_partial = 0
    static_packet_misses = 0
    static_queue_packet_misses = 0
    static_packet_lookup_misses = 0
    static_mdi_errors = 0
    stream_fog_draws = 0
    stream_draw_fallbacks = 0
    material_parameter_blocks = 0
    material_parameter_hash = 0
    material_invalid_parameters = 0
    tier_lightmap_support: set[str] = set()
    tier_fog_support: set[str] = set()
    product_tiers: set[str] = set()
    source_runs: set[str] = set()

    runs = manifest.get("runs", [])
    if isinstance(runs, list):
        for run_index, run in enumerate(runs, start=1):
            if not isinstance(run, dict):
                continue
            run_label = str(run.get("type", f"run-{run_index}"))
            world_run = run_label == "switch-screenshots" or isinstance(run.get("maps"), list)
            diagnostics = run.get("diagnostics")
            metrics: dict[str, object] = {}
            if isinstance(diagnostics, dict):
                raw_metrics = diagnostics.get("metrics")
                if world_run and isinstance(raw_metrics, dict):
                    metrics = raw_metrics
                    source_runs.add(run_label)

            product_tier = metrics.get("productTier")
            if isinstance(product_tier, dict):
                tier = str(product_tier.get("tier", "")).strip().upper()
                if tier:
                    product_tiers.add(tier)

            static_world = metrics.get("staticWorld")
            if isinstance(static_world, dict):
                static_renderer_enabled = max(static_renderer_enabled, int_metric(static_world.get("rendererEnabled")))
                static_arena_ready = max(static_arena_ready, int_metric(static_world.get("arenaReady")))
                static_packet_batch_enabled = max(static_packet_batch_enabled, int_metric(static_world.get("packetBatchEnabled")))
                static_packet_batches = max(static_packet_batches, int_metric(static_world.get("packetBatchBatches")))
                static_indirect_ready = max(static_indirect_ready, int_metric(static_world.get("indirectBufferReady")))
                static_gl_errors = max(static_gl_errors, int_metric(static_world.get("glErrors")))
                static_failures = max(static_failures, int_metric(static_world.get("failures")))

            for support_name, tier_label in (
                ("gl12Support", "GL12"),
                ("gl2xSupport", "GL2X"),
            ):
                support = metrics.get(support_name)
                if not isinstance(support, dict):
                    continue
                if int_metric(support.get("lightmaps")) > 0:
                    tier_lightmap_support.add(tier_label)
                if int_metric(support.get("fog")) > 0:
                    tier_fog_support.add(tier_label)

            for support_name, tier_label in (
                ("gl3xSupport", "GL3X"),
                ("gl41Support", "GL41"),
                ("gl46Support", "GL46"),
            ):
                support = metrics.get(support_name)
                if not isinstance(support, dict):
                    continue
                if int_metric(support.get("materialCompiler")) > 0 or int_metric(support.get("commonMaterials")) > 0:
                    product_tiers.add(tier_label)

            stream_draw = metrics.get("streamDraw")
            if isinstance(stream_draw, dict):
                stream_fog_draws = max(stream_fog_draws, int_metric(stream_draw.get("fog")))
                stream_draw_fallbacks = max(stream_draw_fallbacks, int_metric(stream_draw.get("fallbacks")))

            material_parameters = metrics.get("materialParameters")
            if isinstance(material_parameters, dict):
                material_parameter_blocks = max(material_parameter_blocks, int_metric(material_parameters.get("blocks")))
                material_parameter_hash = max(material_parameter_hash, int_metric(material_parameters.get("hash")))
                material_invalid_parameters = max(material_invalid_parameters, int_metric(material_parameters.get("invalid")))

            performance = run.get("performance")
            if world_run and isinstance(performance, dict):
                source_runs.add(run_label)
                latest = performance.get("latest")
                if isinstance(latest, dict):
                    tier = str(latest.get("productTier", latest.get("tier", ""))).strip().upper()
                    if tier:
                        product_tiers.add(tier)
                static_draw_attempts = max(static_draw_attempts, performance_numeric_value(performance, "staticDrawAttempts"))
                static_draw_indexes = max(static_draw_indexes, performance_numeric_value(performance, "staticDrawIndexes"))
                static_draw_fallbacks = max(static_draw_fallbacks, performance_numeric_value(performance, "staticDrawFallbacks"))
                static_packet_full = max(static_packet_full, performance_numeric_value(performance, "staticDrawPacketFull"))
                static_packet_partial = max(static_packet_partial, performance_numeric_value(performance, "staticDrawPacketPartial"))
                static_packet_misses = max(static_packet_misses, performance_numeric_value(performance, "staticDrawPacketMisses"))
                static_queue_packet_misses = max(static_queue_packet_misses, performance_numeric_value(performance, "staticQueuePacketMisses"))
                static_packet_lookup_misses = max(static_packet_lookup_misses, performance_numeric_value(performance, "staticPacketLookupMisses"))
                static_mdi_errors = max(static_mdi_errors, performance_numeric_value(performance, "staticMdiErrors"))
                stream_fog_draws = max(stream_fog_draws, performance_numeric_value(performance, "streamDrawFog"))
                stream_draw_fallbacks = max(stream_draw_fallbacks, performance_numeric_value(performance, "streamDrawFallbacks"))
                material_parameter_blocks = max(material_parameter_blocks, performance_numeric_value(performance, "materialParameterBlocks"))
                material_parameter_hash = max(material_parameter_hash, performance_numeric_value(performance, "materialParameterHash"))
                material_invalid_parameters = max(material_invalid_parameters, performance_numeric_value(performance, "materialInvalidParameterBlocks"))

    performance_aggregate = manifest.get("performanceAggregate")
    if isinstance(performance_aggregate, dict):
        static_draw_attempts = max(static_draw_attempts, performance_numeric_value(performance_aggregate, "staticDrawAttempts"))
        static_draw_indexes = max(static_draw_indexes, performance_numeric_value(performance_aggregate, "staticDrawIndexes"))
        static_draw_fallbacks = max(static_draw_fallbacks, performance_numeric_value(performance_aggregate, "staticDrawFallbacks"))
        static_packet_full = max(static_packet_full, performance_numeric_value(performance_aggregate, "staticDrawPacketFull"))
        static_packet_partial = max(static_packet_partial, performance_numeric_value(performance_aggregate, "staticDrawPacketPartial"))
        static_packet_misses = max(static_packet_misses, performance_numeric_value(performance_aggregate, "staticDrawPacketMisses"))
        static_queue_packet_misses = max(static_queue_packet_misses, performance_numeric_value(performance_aggregate, "staticQueuePacketMisses"))
        static_packet_lookup_misses = max(static_packet_lookup_misses, performance_numeric_value(performance_aggregate, "staticPacketLookupMisses"))
        static_mdi_errors = max(static_mdi_errors, performance_numeric_value(performance_aggregate, "staticMdiErrors"))
        stream_fog_draws = max(stream_fog_draws, performance_numeric_value(performance_aggregate, "streamDrawFog"))
        stream_draw_fallbacks = max(stream_draw_fallbacks, performance_numeric_value(performance_aggregate, "streamDrawFallbacks"))
        material_parameter_blocks = max(material_parameter_blocks, performance_numeric_value(performance_aggregate, "materialParameterBlocks"))
        material_parameter_hash = max(material_parameter_hash, performance_numeric_value(performance_aggregate, "materialParameterHash"))
        material_invalid_parameters = max(material_invalid_parameters, performance_numeric_value(performance_aggregate, "materialInvalidParameterBlocks"))

    static_packets = static_packet_full + static_packet_partial
    if static_packets <= 0:
        static_packets = static_packet_batches
    lightmap_required = "lightmap" in required_tags
    fog_required = "fog-heavy" in required_tags or "visibility" in required_tags
    lightmap_path_found = bool(tier_lightmap_support) or material_parameter_blocks > 0
    fog_path_found = bool(tier_fog_support) or stream_fog_draws > 0

    missing_required_tags = sorted(set(required_tags) - set(selected_tags))
    missing_screenshot_maps = sorted(set(required_maps) - screenshot_map_set)
    missing_histogram_maps = sorted(set(required_maps) - histogram_map_set)
    missing_lightmap_maps = sorted(set(lightmap_maps) - screenshot_map_set)
    missing_fog_maps = sorted(set(fog_maps) - screenshot_map_set)

    failures: list[str] = []
    if require_world and not dry_run:
        if missing_required_tags:
            failures.append("World proof corpus is missing required tag(s): " + ", ".join(missing_required_tags) + ".")
        if required_tags and not required_maps:
            failures.append("World proof did not select any map scene for the required world tags.")
        if missing_screenshot_maps:
            failures.append("World proof is missing GLx screenshots for map(s): " + ", ".join(missing_screenshot_maps) + ".")
        if missing_histogram_maps:
            failures.append("World proof is missing histogram metadata for map(s): " + ", ".join(missing_histogram_maps) + ".")
        if static_renderer_enabled <= 0:
            failures.append("World proof did not observe the GLx static-world renderer enabled.")
        if static_arena_ready <= 0 and static_packets <= 0:
            failures.append("World proof did not observe a ready static arena or queued static packets.")
        if static_draw_attempts <= 0:
            failures.append("World proof did not observe static-world draw attempts.")
        if static_draw_indexes <= 0:
            failures.append("World proof did not observe static-world submitted indexes.")
        if static_draw_fallbacks > 0:
            failures.append(f"World proof reported static draw fallbacks: {static_draw_fallbacks}.")
        if static_packet_misses or static_queue_packet_misses or static_packet_lookup_misses:
            failures.append(
                "World proof reported static packet misses: "
                f"draw={static_packet_misses}, queue={static_queue_packet_misses}, "
                f"lookup={static_packet_lookup_misses}."
            )
        if static_gl_errors > 0 or static_failures > 0 or static_mdi_errors > 0:
            failures.append(
                "World proof reported static-world errors: "
                f"gl={static_gl_errors}, failures={static_failures}, mdi={static_mdi_errors}."
            )
        if lightmap_required:
            if not lightmap_maps:
                failures.append("World proof requires lightmap coverage but selected no lightmap-tagged map.")
            if missing_lightmap_maps:
                failures.append("World proof is missing GLx lightmap screenshot map(s): " + ", ".join(missing_lightmap_maps) + ".")
            if not lightmap_path_found:
                failures.append("World proof did not observe lightmap support or material parameter-block evidence.")
        if fog_required:
            if not fog_maps:
                failures.append("World proof requires fog/visibility coverage but selected no fog-heavy map.")
            if missing_fog_maps:
                failures.append("World proof is missing GLx fog-heavy screenshot map(s): " + ", ".join(missing_fog_maps) + ".")
            if "fog-heavy" in required_tags and not fog_path_found:
                failures.append("World proof did not observe fog support or fog stream-draw evidence.")
        if stream_draw_fallbacks > 0:
            failures.append(f"World proof reported stream draw fallbacks: {stream_draw_fallbacks}.")
        if material_invalid_parameters > 0:
            failures.append(f"World proof reported invalid material parameter blocks: {material_invalid_parameters}.")

    status = "not-configured"
    if require_world:
        status = "planned" if dry_run else ("passed" if not failures else "failed")

    return {
        "version": GLX_WORLD_PROOF_VERSION,
        "status": status,
        "requiresWorldProof": require_world,
        "requiredTags": required_tags,
        "selectedTags": selected_tags,
        "scenes": scene_records,
        "requiredMaps": required_maps,
        "glxScreenshotMaps": found_screenshot_maps,
        "histogramMaps": histogram_maps,
        "missingScreenshotMaps": [] if dry_run else missing_screenshot_maps,
        "staticWorld": {
            "rendererEnabled": static_renderer_enabled,
            "arenaReady": static_arena_ready,
            "packetBatchEnabled": static_packet_batch_enabled,
            "indirectBufferReady": static_indirect_ready,
            "packets": static_packets,
            "drawAttempts": static_draw_attempts,
            "drawIndexes": static_draw_indexes,
            "drawFallbacks": static_draw_fallbacks,
            "packetMisses": static_packet_misses,
            "queuePacketMisses": static_queue_packet_misses,
            "lookupMisses": static_packet_lookup_misses,
            "glErrors": static_gl_errors,
            "failures": static_failures,
            "mdiErrors": static_mdi_errors,
        },
        "lightmaps": {
            "required": lightmap_required,
            "maps": lightmap_maps,
            "tierSupport": sorted(tier_lightmap_support),
            "materialParameterBlocks": material_parameter_blocks,
            "materialParameterHash": material_parameter_hash,
            "ok": (not lightmap_required) or (not missing_lightmap_maps and lightmap_path_found),
        },
        "fog": {
            "required": fog_required,
            "maps": fog_maps,
            "tierSupport": sorted(tier_fog_support),
            "streamDraws": stream_fog_draws,
            "ok": (not fog_required) or (not missing_fog_maps and fog_path_found),
        },
        "productTiers": sorted(product_tiers),
        "sourceRuns": sorted(source_runs),
        "failures": list(dict.fromkeys(failures)),
    }


def evaluate_world_proof(
    manifest: dict[str, object],
    requirements: dict[str, object],
) -> list[str]:
    if not manifest_requires_world_proof(manifest, requirements):
        return []

    evidence = manifest.get("worldProofEvidence")
    if not isinstance(evidence, dict):
        return ["No world proof evidence was recorded."]

    failures: list[str] = []
    if evidence.get("version") != GLX_WORLD_PROOF_VERSION:
        failures.append(
            "World proof evidence has unsupported version "
            f"{evidence.get('version')!r}."
        )
    if evidence.get("status") != "passed":
        failures.append(
            "World proof evidence status is "
            f"{evidence.get('status')!r}, expected 'passed'."
        )
    for failure in evidence.get("failures", []):
        if str(failure).strip():
            failures.append(str(failure))
    return list(dict.fromkeys(failures))


def manifest_requires_material_proof(
    manifest: dict[str, object],
    requirements: dict[str, object],
) -> bool:
    return bool(requirements.get("require_material_proof"))


def material_scene_records(
    manifest: dict[str, object],
    requirements: dict[str, object],
) -> list[dict[str, object]]:
    required_tags = {
        str(tag)
        for tag in requirements.get("required_material_tags", ())
        if str(tag).strip()
    }
    material_tags = set(GLX_MATERIAL_PROOF_TAGS)
    records: list[dict[str, object]] = []
    for scene_id in manifest_selected_scene_ids(manifest):
        scene = GLX_PROOF_CORPUS_SCENES[scene_id]
        if scene.get("kind") != "map":
            continue
        tags = {str(tag) for tag in scene.get("tags", ()) if str(tag).strip()}
        if not tags.intersection(material_tags) and not tags.intersection(required_tags):
            continue
        records.append(
            {
                "sceneId": scene_id,
                "map": str(scene.get("target", "")).strip().lower(),
                "assetTier": scene.get("assetTier", ""),
                "tags": sorted(tags),
                "required": bool(tags.intersection(required_tags)),
            }
        )
    return records


def material_flag_names(flags: int) -> list[str]:
    return [
        name
        for name, bit in sorted(GLX_MATERIAL_STAGE_FLAGS.items())
        if flags & bit
    ]


def material_tcgen_name(value: object) -> str:
    tcgen = int_metric(value, -1)
    for name, known_value in GLX_MATERIAL_TCGEN_IDS.items():
        if tcgen == known_value:
            return name
    return f"unknown-{tcgen}"


def material_proof_evidence(
    manifest: dict[str, object],
    requirements: dict[str, object],
) -> dict[str, object]:
    dry_run = bool(manifest.get("dryRun"))
    require_material = manifest_requires_material_proof(manifest, requirements)
    required_tags = sorted(
        {
            str(tag)
            for tag in requirements.get("required_material_tags", ())
            if str(tag).strip()
        }
    )
    required_stream_features = [
        str(feature)
        for feature in requirements.get("required_material_stream_features", ())
        if str(feature).strip()
    ]
    required_tcgens = [
        str(tcgen)
        for tcgen in requirements.get("required_material_tcgens", ())
        if str(tcgen).strip()
    ]
    required_stage_flags = [
        str(flag)
        for flag in requirements.get("required_material_stage_flags", ())
        if str(flag).strip()
    ]
    required_stream_guards = [
        str(feature)
        for feature in requirements.get("required_material_stream_guards", ())
        if str(feature).strip()
    ]
    forbidden_stream_features = [
        str(feature)
        for feature in requirements.get("forbidden_material_stream_features", ())
        if str(feature).strip()
    ]
    proof_corpus = manifest.get("proofCorpus")
    selected_tags = sorted(
        {
            str(tag)
            for tag in (
                proof_corpus.get("selectedTags", [])
                if isinstance(proof_corpus, dict)
                else []
            )
            if str(tag).strip()
        }
    )
    scene_records = material_scene_records(manifest, requirements)
    required_scene_records = [
        record for record in scene_records if bool(record.get("required"))
    ]
    required_maps = sorted(
        {
            str(record.get("map", ""))
            for record in required_scene_records
            if str(record.get("map", "")).strip()
        }
    )
    screenshots = manifest_glx_screenshot_records(manifest)
    found_screenshot_maps = sorted(
        {
            str(record.get("map", ""))
            for record in screenshots
            if record.get("found")
        }
    )
    histogram_maps = sorted(
        {
            str(record.get("map", ""))
            for record in screenshots
            if record.get("found") and record.get("histogramPassed")
        }
    )

    material_enabled = 0
    material_ready = 0
    compile_attempts = 0
    compile_failures = 0
    link_failures = 0
    precache_failures = 0
    bind_failures = 0
    programs = 0
    binds = 0
    bind_attempts = 0
    switches = 0
    cache_misses = 0
    fallback_unsupported = 0
    fallback_disabled = 0
    fallback_not_ready = 0
    fallback_full = 0
    compiler_plans = 0
    unsupported_plans = 0
    last_unsupported = 0
    parameter_blocks = 0
    invalid_parameter_blocks = 0
    parameter_hash = 0
    parameter_features = 0
    parameter_flags = 0
    parameter_state = 0
    observed_tcgens: set[str] = set()
    observed_flags = 0
    language_flags = 0
    language_texmod_mask = 0
    language_texmod_sequence = 0
    language_texmod_wave_funcs = 0
    language_fog_adjust = 0
    stage_flag_counts = {name: 0 for name in GLX_MATERIAL_STAGE_FLAGS}
    stream_feature_counts = {
        "multitexture": 0,
        "depthFragment": 0,
        "texMod": 0,
        "environment": 0,
        "dynamicLight": 0,
        "screenMap": 0,
        "videoMap": 0,
    }
    stream_fallbacks = 0
    stream_skips = 0
    stream_program_skips = 0
    stream_gate_records: dict[str, dict[str, int]] = {}
    source_runs: set[str] = set()

    def record_material_metrics(metrics: dict[str, object], run_label: str) -> None:
        nonlocal material_enabled, material_ready, compile_attempts
        nonlocal compile_failures, link_failures, precache_failures, bind_failures
        nonlocal fallback_unsupported, fallback_disabled, fallback_not_ready, fallback_full
        nonlocal compiler_plans, unsupported_plans, last_unsupported
        nonlocal parameter_blocks, invalid_parameter_blocks, parameter_hash
        nonlocal parameter_features, parameter_flags, parameter_state, observed_flags
        nonlocal language_flags, language_texmod_mask, language_texmod_sequence
        nonlocal language_texmod_wave_funcs, language_fog_adjust
        nonlocal stage_flag_counts
        nonlocal stream_fallbacks, stream_skips, stream_program_skips

        source_runs.add(run_label)
        material = metrics.get("material")
        if isinstance(material, dict):
            material_enabled = max(material_enabled, int_metric(material.get("enabled")))
            material_ready = max(material_ready, int_metric(material.get("ready")))
            compile_attempts = max(compile_attempts, int_metric(material.get("attempts")))
            compile_failures = max(compile_failures, int_metric(material.get("compile")))
            link_failures = max(link_failures, int_metric(material.get("link")))
            precache_failures = max(precache_failures, int_metric(material.get("precacheFailures")))
            bind_failures = max(bind_failures, int_metric(material.get("bind")))

        fallbacks = metrics.get("materialFallbacks")
        if isinstance(fallbacks, dict):
            fallback_unsupported = max(fallback_unsupported, int_metric(fallbacks.get("unsupported")))
            fallback_disabled = max(fallback_disabled, int_metric(fallbacks.get("disabled")))
            fallback_not_ready = max(fallback_not_ready, int_metric(fallbacks.get("notReady")))
            fallback_full = max(fallback_full, int_metric(fallbacks.get("full")))

        compiler = metrics.get("materialCompilerPlans")
        if isinstance(compiler, dict):
            compiler_plans = max(compiler_plans, int_metric(compiler.get("compiled")))
            unsupported_plans = max(unsupported_plans, int_metric(compiler.get("unsupported")))
            last_unsupported = max(last_unsupported, int_metric(compiler.get("lastUnsupported")))

        parameters = metrics.get("materialParameters")
        if isinstance(parameters, dict):
            parameter_blocks = max(parameter_blocks, int_metric(parameters.get("blocks")))
            invalid_parameter_blocks = max(invalid_parameter_blocks, int_metric(parameters.get("invalid")))
            parameter_hash = max(parameter_hash, int_metric(parameters.get("hash")))
            parameter_features = max(parameter_features, int_metric(parameters.get("features")))
            parameter_flags = max(parameter_flags, int_metric(parameters.get("flags")))
            parameter_state = max(parameter_state, int_metric(parameters.get("state")))
            for key in ("tcGen0", "tcGen1"):
                if key in parameters:
                    observed_tcgens.add(material_tcgen_name(parameters.get(key)))
            observed_flags |= int_metric(parameters.get("flags"))

        last_key = metrics.get("materialLastKey")
        if isinstance(last_key, dict):
            observed_flags |= int_metric(last_key.get("flags"))
            for key in ("tcGen0", "tcGen1"):
                if key in last_key:
                    observed_tcgens.add(material_tcgen_name(last_key.get(key)))

        language = metrics.get("materialLanguage")
        if isinstance(language, dict):
            language_flags |= int_metric(language.get("flags"))
            language_texmod_mask |= int_metric(language.get("texModMask0")) | int_metric(language.get("texModMask1"))
            language_texmod_sequence |= int_metric(language.get("texModSequence0")) | int_metric(language.get("texModSequence1"))
            language_texmod_wave_funcs |= int_metric(language.get("texModWaveFuncs0")) | int_metric(language.get("texModWaveFuncs1"))
            language_fog_adjust = max(language_fog_adjust, int_metric(language.get("fogAdjust")))

        stage_flags = metrics.get("materialStageFlags")
        if isinstance(stage_flags, dict):
            for flag_name in stage_flag_counts:
                count = int_metric(stage_flags.get(flag_name))
                stage_flag_counts[flag_name] = max(stage_flag_counts[flag_name], count)
                if count > 0:
                    observed_flags |= GLX_MATERIAL_STAGE_FLAGS[flag_name]

        stream_draw = metrics.get("streamDraw")
        if isinstance(stream_draw, dict):
            stream_feature_counts["multitexture"] = max(
                stream_feature_counts["multitexture"],
                int_metric(stream_draw.get("multitexture")),
            )
            stream_feature_counts["depthFragment"] = max(
                stream_feature_counts["depthFragment"],
                int_metric(stream_draw.get("depthFragment")),
            )
            stream_feature_counts["texMod"] = max(
                stream_feature_counts["texMod"],
                int_metric(stream_draw.get("texMods")),
            )
            stream_feature_counts["environment"] = max(
                stream_feature_counts["environment"],
                int_metric(stream_draw.get("environment")),
            )
            stream_feature_counts["dynamicLight"] = max(
                stream_feature_counts["dynamicLight"],
                int_metric(stream_draw.get("dynamicLights")),
            )
            stream_feature_counts["screenMap"] = max(
                stream_feature_counts["screenMap"],
                int_metric(stream_draw.get("screenMaps")),
            )
            stream_feature_counts["videoMap"] = max(
                stream_feature_counts["videoMap"],
                int_metric(stream_draw.get("videoMaps")),
            )
            stream_fallbacks = max(stream_fallbacks, int_metric(stream_draw.get("fallbacks")))
            stream_skips = max(stream_skips, int_metric(stream_draw.get("skips")))

        stream_skip = metrics.get("streamDrawSkip")
        if isinstance(stream_skip, dict):
            stream_program_skips = max(stream_program_skips, int_metric(stream_skip.get("program")))

        gates = metrics.get("streamMaterialGate")
        if isinstance(gates, dict):
            for gate_name in (
                "multitexture",
                "depthFragment",
                "texMod",
                "environment",
                "dynamicLight",
                "screenMap",
                "videoMap",
            ):
                record = stream_gate_records.setdefault(
                    gate_name,
                    {"enabled": 0, "accepted": 0, "rejected": 0},
                )
                prefix = gate_name
                record["enabled"] = max(record["enabled"], int_metric(gates.get(f"{prefix}Enabled")))
                record["accepted"] = max(record["accepted"], int_metric(gates.get(f"{prefix}Accepted")))
                record["rejected"] = max(record["rejected"], int_metric(gates.get(f"{prefix}Rejected")))
                stream_feature_counts[gate_name] = max(
                    stream_feature_counts[gate_name],
                    record["accepted"],
                )

    def record_material_performance(performance: dict[str, object], run_label: str) -> None:
        nonlocal material_enabled, material_ready
        nonlocal programs, binds, bind_attempts, switches, cache_misses
        nonlocal compile_failures, link_failures, precache_failures, bind_failures
        nonlocal parameter_blocks, invalid_parameter_blocks, parameter_hash
        nonlocal parameter_features, parameter_flags, parameter_state, observed_flags
        nonlocal stage_flag_counts
        nonlocal stream_fallbacks, stream_skips

        source_runs.add(run_label)
        if str(performance_metric(performance, "materialRenderer") or "").lower() == "enabled":
            material_enabled = max(material_enabled, 1)
        if str(performance_metric(performance, "materialReady") or "").lower() == "ready":
            material_ready = max(material_ready, 1)
        programs = max(programs, performance_numeric_value(performance, "materialPrograms"))
        binds = max(binds, performance_numeric_value(performance, "materialBinds"))
        bind_attempts = max(bind_attempts, performance_numeric_value(performance, "materialBindAttempts"))
        switches = max(switches, performance_numeric_value(performance, "materialSwitches"))
        cache_misses = max(cache_misses, performance_numeric_value(performance, "materialCacheMisses"))
        compile_failures = max(compile_failures, performance_numeric_value(performance, "materialCompileFailures"))
        link_failures = max(link_failures, performance_numeric_value(performance, "materialLinkFailures"))
        precache_failures = max(precache_failures, performance_numeric_value(performance, "materialPrecacheFailures"))
        bind_failures = max(bind_failures, performance_numeric_value(performance, "materialBindFailures"))
        parameter_blocks = max(parameter_blocks, performance_numeric_value(performance, "materialParameterBlocks"))
        invalid_parameter_blocks = max(invalid_parameter_blocks, performance_numeric_value(performance, "materialInvalidParameterBlocks"))
        parameter_hash = max(parameter_hash, performance_numeric_value(performance, "materialParameterHash"))
        parameter_features = max(parameter_features, performance_numeric_value(performance, "materialParameterFeatures"))
        parameter_flags = max(parameter_flags, performance_numeric_value(performance, "materialParameterFlags"))
        parameter_state = max(parameter_state, performance_numeric_value(performance, "materialParameterState"))
        observed_flags |= parameter_flags
        stream_feature_counts["multitexture"] = max(
            stream_feature_counts["multitexture"],
            performance_numeric_value(performance, "streamDrawMultitexture"),
        )
        stream_feature_counts["depthFragment"] = max(
            stream_feature_counts["depthFragment"],
            performance_numeric_value(performance, "streamDrawDepthFragment"),
        )
        stream_feature_counts["texMod"] = max(
            stream_feature_counts["texMod"],
            performance_numeric_value(performance, "streamDrawTexMods"),
        )
        stream_feature_counts["environment"] = max(
            stream_feature_counts["environment"],
            performance_numeric_value(performance, "streamDrawEnvironment"),
        )
        stream_feature_counts["dynamicLight"] = max(
            stream_feature_counts["dynamicLight"],
            performance_numeric_value(performance, "streamDrawDynamicLights"),
        )
        stream_feature_counts["screenMap"] = max(
            stream_feature_counts["screenMap"],
            performance_numeric_value(performance, "streamDrawScreenMaps"),
        )
        stream_feature_counts["videoMap"] = max(
            stream_feature_counts["videoMap"],
            performance_numeric_value(performance, "streamDrawVideoMaps"),
        )
        stream_fallbacks = max(stream_fallbacks, performance_numeric_value(performance, "streamDrawFallbacks"))
        stream_skips = max(stream_skips, performance_numeric_value(performance, "streamDrawSkips"))
        for key in ("materialParameterTcGen0", "materialParameterTcGen1"):
            value = performance_metric(performance, key)
            if value is not None:
                observed_tcgens.add(material_tcgen_name(value))
        for flag_name in stage_flag_counts:
            metric_key = f"materialStageFlag{flag_name[0].upper()}{flag_name[1:]}"
            count = performance_numeric_value(performance, metric_key)
            stage_flag_counts[flag_name] = max(stage_flag_counts[flag_name], count)
            if count > 0:
                observed_flags |= GLX_MATERIAL_STAGE_FLAGS[flag_name]

    runs = manifest.get("runs", [])
    if isinstance(runs, list):
        for run_index, run in enumerate(runs, start=1):
            if not isinstance(run, dict):
                continue
            run_label = str(run.get("type", f"run-{run_index}"))
            material_run = (
                run_label == "switch-screenshots"
                or isinstance(run.get("maps"), list)
                or str(run.get("map", "")).strip().lower() in required_maps
            )
            diagnostics = run.get("diagnostics")
            if material_run and isinstance(diagnostics, dict):
                raw_metrics = diagnostics.get("metrics")
                if isinstance(raw_metrics, dict):
                    record_material_metrics(raw_metrics, run_label)
            performance = run.get("performance")
            if material_run and isinstance(performance, dict):
                record_material_performance(performance, run_label)

    performance_aggregate = manifest.get("performanceAggregate")
    if isinstance(performance_aggregate, dict):
        record_material_performance(performance_aggregate, "performanceAggregate")

    missing_required_tags = sorted(set(required_tags) - set(selected_tags))
    screenshot_map_set = set(found_screenshot_maps)
    histogram_map_set = set(histogram_maps)
    missing_screenshot_maps = sorted(set(required_maps) - screenshot_map_set)
    missing_histogram_maps = sorted(set(required_maps) - histogram_map_set)
    missing_stream_features = [
        feature
        for feature in required_stream_features
        if stream_feature_counts.get(feature, 0) <= 0
    ]
    missing_tcgens = [
        tcgen
        for tcgen in required_tcgens
        if tcgen not in GLX_MATERIAL_TCGEN_IDS
    ]
    tag_backed_tcgens = {
        "lightmap": "tcgen-lightmap",
        "environment": "tcgen-environment",
        "fog": "tcgen-fog",
        "vector": "tcgen-vector",
    }
    missing_tcgen_tags = [
        tag
        for tcgen, tag in tag_backed_tcgens.items()
        if tcgen in required_tcgens and tag not in selected_tags
    ]
    unknown_stage_flags = [
        flag for flag in required_stage_flags if flag not in GLX_MATERIAL_STAGE_FLAGS
    ]
    missing_stage_flags = [
        flag
        for flag in required_stage_flags
        if flag in GLX_MATERIAL_STAGE_FLAGS
        and stage_flag_counts.get(flag, 0) <= 0
        and (observed_flags & GLX_MATERIAL_STAGE_FLAGS[flag]) == 0
    ]
    missing_stage_flag_tags = [
        tag
        for flag, tag in GLX_MATERIAL_STAGE_FLAG_TAGS.items()
        if flag in required_stage_flags and tag not in selected_tags
    ]
    missing_stream_guards = [
        feature for feature in required_stream_guards if feature not in stream_gate_records
    ]
    unsafe_stream_guards = [
        feature
        for feature in required_stream_guards
        if stream_gate_records.get(feature, {}).get("accepted", 0) > 0
        and feature in forbidden_stream_features
    ]
    forbidden_stream_draws = [
        feature
        for feature in forbidden_stream_features
        if stream_feature_counts.get(feature, 0) > 0
    ]

    failures: list[str] = []
    if require_material and not dry_run:
        if missing_required_tags:
            failures.append("Material proof corpus is missing required tag(s): " + ", ".join(missing_required_tags) + ".")
        if required_tags and not required_maps:
            failures.append("Material proof did not select any map scene for the required material tags.")
        if missing_screenshot_maps:
            failures.append("Material proof is missing GLx screenshots for map(s): " + ", ".join(missing_screenshot_maps) + ".")
        if missing_histogram_maps:
            failures.append("Material proof is missing histogram metadata for map(s): " + ", ".join(missing_histogram_maps) + ".")
        if material_enabled <= 0:
            failures.append("Material proof did not observe the GLx material renderer enabled.")
        if material_ready <= 0:
            failures.append("Material proof did not observe the GLx material renderer ready.")
        if compile_attempts <= 0 and programs <= 0 and compiler_plans <= 0:
            failures.append("Material proof did not observe material compile/program activity.")
        if compile_failures or link_failures or precache_failures or bind_failures:
            failures.append(
                "Material proof reported material failures: "
                f"compile={compile_failures}, link={link_failures}, "
                f"precache={precache_failures}, bind={bind_failures}."
            )
        if fallback_unsupported or fallback_disabled or fallback_not_ready or fallback_full:
            failures.append(
                "Material proof reported material fallbacks: "
                f"unsupported={fallback_unsupported}, disabled={fallback_disabled}, "
                f"notReady={fallback_not_ready}, full={fallback_full}."
            )
        if unsupported_plans or last_unsupported:
            failures.append(
                "Material proof reported unsupported compiler plans: "
                f"unsupported={unsupported_plans}, last=0x{last_unsupported:08x}."
            )
        if parameter_blocks <= 0:
            failures.append("Material proof did not observe material parameter blocks.")
        if invalid_parameter_blocks:
            failures.append(f"Material proof reported invalid parameter blocks: {invalid_parameter_blocks}.")
        if parameter_hash <= 0:
            failures.append("Material proof did not record a material parameter fingerprint.")
        if missing_stream_features:
            failures.append("Material proof is missing stream feature evidence: " + ", ".join(missing_stream_features) + ".")
        if unknown_stage_flags:
            failures.append("Material proof requires unknown stage flag(s): " + ", ".join(unknown_stage_flags) + ".")
        if missing_stage_flags:
            failures.append("Material proof is missing stage-flag evidence: " + ", ".join(missing_stage_flags) + ".")
        if missing_stage_flag_tags:
            failures.append("Material proof corpus is missing stage-flag tag(s): " + ", ".join(missing_stage_flag_tags) + ".")
        if missing_stream_guards:
            failures.append("Material proof is missing stream guard evidence: " + ", ".join(missing_stream_guards) + ".")
        if unsafe_stream_guards:
            failures.append("Material proof stream guards accepted forbidden feature(s): " + ", ".join(unsafe_stream_guards) + ".")
        if stream_fallbacks > 0:
            failures.append(f"Material proof reported stream draw fallbacks: {stream_fallbacks}.")
        if stream_program_skips > 0:
            failures.append(f"Material proof reported material-program stream skips: {stream_program_skips}.")
        if forbidden_stream_draws:
            failures.append(
                "Material proof saw high-risk material stream draws in the RC proof surface: "
                + ", ".join(
                    f"{feature}={stream_feature_counts.get(feature, 0)}"
                    for feature in forbidden_stream_draws
                )
                + "."
            )
        if missing_tcgens:
            failures.append("Material proof requires unknown tcgen id(s): " + ", ".join(missing_tcgens) + ".")
        if missing_tcgen_tags:
            failures.append("Material proof corpus is missing tcgen tag(s): " + ", ".join(missing_tcgen_tags) + ".")

    status = "not-configured"
    if require_material:
        status = "planned" if dry_run else ("passed" if not failures else "failed")

    return {
        "version": GLX_MATERIAL_PROOF_VERSION,
        "status": status,
        "requiresMaterialProof": require_material,
        "requiredTags": required_tags,
        "selectedTags": selected_tags,
        "requiredStageFlags": required_stage_flags,
        "requiredStreamFeatures": required_stream_features,
        "requiredStreamGuards": required_stream_guards,
        "forbiddenStreamFeatures": forbidden_stream_features,
        "requiredTcgens": required_tcgens,
        "tcgenContract": dict(GLX_MATERIAL_TCGEN_IDS),
        "stageFlagContract": dict(GLX_MATERIAL_STAGE_FLAGS),
        "scenes": scene_records,
        "requiredMaps": required_maps,
        "glxScreenshotMaps": found_screenshot_maps,
        "histogramMaps": histogram_maps,
        "missingScreenshotMaps": [] if dry_run else missing_screenshot_maps,
        "renderer": {
            "enabled": material_enabled,
            "ready": material_ready,
            "compileAttempts": compile_attempts,
            "programs": programs,
            "binds": binds,
            "bindAttempts": bind_attempts,
            "switches": switches,
            "cacheMisses": cache_misses,
            "compileFailures": compile_failures,
            "linkFailures": link_failures,
            "precacheFailures": precache_failures,
            "bindFailures": bind_failures,
        },
        "compilerPlans": {
            "compiled": compiler_plans,
            "unsupported": unsupported_plans,
            "lastUnsupported": last_unsupported,
        },
        "fallbacks": {
            "unsupported": fallback_unsupported,
            "disabled": fallback_disabled,
            "notReady": fallback_not_ready,
            "full": fallback_full,
        },
        "parameters": {
            "blocks": parameter_blocks,
            "invalid": invalid_parameter_blocks,
            "hash": parameter_hash,
            "features": parameter_features,
            "flags": parameter_flags,
            "flagNames": material_flag_names(parameter_flags or observed_flags),
            "state": parameter_state,
            "observedTcgens": sorted(observed_tcgens),
        },
        "stageFlags": {
            "counts": dict(stage_flag_counts),
            "observedMask": observed_flags,
            "observedNames": material_flag_names(observed_flags),
        },
        "language": {
            "flags": language_flags,
            "flagNames": material_flag_names(language_flags),
            "texModMask": language_texmod_mask,
            "texModSequence": language_texmod_sequence,
            "texModWaveFuncs": language_texmod_wave_funcs,
            "fogAdjust": language_fog_adjust,
        },
        "streamFeatures": dict(stream_feature_counts),
        "streamMaterialGates": stream_gate_records,
        "streamFallbacks": stream_fallbacks,
        "streamSkips": stream_skips,
        "streamProgramSkips": stream_program_skips,
        "sourceRuns": sorted(source_runs),
        "failures": list(dict.fromkeys(failures)),
    }


def evaluate_material_proof(
    manifest: dict[str, object],
    requirements: dict[str, object],
) -> list[str]:
    if not manifest_requires_material_proof(manifest, requirements):
        return []

    evidence = manifest.get("materialProofEvidence")
    if not isinstance(evidence, dict):
        return ["No material proof evidence was recorded."]

    failures: list[str] = []
    if evidence.get("version") != GLX_MATERIAL_PROOF_VERSION:
        failures.append(
            "Material proof evidence has unsupported version "
            f"{evidence.get('version')!r}."
        )
    if evidence.get("status") != "passed":
        failures.append(
            "Material proof evidence status is "
            f"{evidence.get('status')!r}, expected 'passed'."
        )
    for failure in evidence.get("failures", []):
        if str(failure).strip():
            failures.append(str(failure))
    return list(dict.fromkeys(failures))


def manifest_requires_dynamic_proof(
    manifest: dict[str, object],
    requirements: dict[str, object],
) -> bool:
    return bool(requirements.get("require_dynamic_proof"))


def dynamic_scene_records(
    manifest: dict[str, object],
    requirements: dict[str, object],
) -> list[dict[str, object]]:
    required_tags = {
        str(tag)
        for tag in requirements.get("required_dynamic_tags", ())
        if str(tag).strip()
    }
    dynamic_tags = set(GLX_DYNAMIC_PROOF_TAGS)
    records: list[dict[str, object]] = []
    for scene_id in manifest_selected_scene_ids(manifest):
        scene = GLX_PROOF_CORPUS_SCENES[scene_id]
        kind = str(scene.get("kind", "")).strip().lower()
        if kind not in {"map", "demo"}:
            continue
        tags = {str(tag) for tag in scene.get("tags", ()) if str(tag).strip()}
        if not tags.intersection(dynamic_tags) and not tags.intersection(required_tags):
            continue
        target = str(scene.get("target", "")).strip().lower()
        record: dict[str, object] = {
            "sceneId": scene_id,
            "kind": kind,
            "target": target,
            "assetTier": scene.get("assetTier", ""),
            "tags": sorted(tags),
            "required": bool(tags.intersection(required_tags)),
        }
        if kind == "map":
            record["map"] = target
        elif kind == "demo":
            record["demo"] = target
        records.append(record)
    return records


def manifest_glx_timedemo_records(manifest: dict[str, object]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    runs = manifest.get("runs", [])
    if not isinstance(runs, list):
        return records

    for run_index, run in enumerate(runs, start=1):
        if not isinstance(run, dict) or run.get("type") != "timedemo":
            continue
        renderer = str(run.get("renderer", "")).strip().lower()
        demo = str(run.get("demo", "")).strip().lower()
        if renderer != "glx" or not demo:
            continue
        metrics = run.get("timedemoMetrics")
        records.append(
            {
                "run": f"timedemo-{run_index}",
                "demo": demo,
                "found": isinstance(metrics, dict),
                "fps": metrics.get("fps", 0.0) if isinstance(metrics, dict) else 0.0,
            }
        )
    return records


def dynamic_proof_evidence(
    manifest: dict[str, object],
    requirements: dict[str, object],
) -> dict[str, object]:
    dry_run = bool(manifest.get("dryRun"))
    require_dynamic = manifest_requires_dynamic_proof(manifest, requirements)
    required_tags = sorted(
        {
            str(tag)
            for tag in requirements.get("required_dynamic_tags", ())
            if str(tag).strip()
        }
    )
    required_categories = [
        str(category)
        for category in requirements.get("required_dynamic_categories", ())
        if str(category).strip()
    ]
    required_stream_features = [
        str(feature)
        for feature in requirements.get("required_dynamic_stream_features", ())
        if str(feature).strip()
    ]
    required_support = [
        str(item)
        for item in requirements.get("required_dynamic_support", ())
        if str(item).strip()
    ]
    required_stream_guards = [
        str(feature)
        for feature in requirements.get("required_dynamic_stream_guards", ())
        if str(feature).strip()
    ]
    forbidden_stream_features = [
        str(feature)
        for feature in requirements.get("forbidden_dynamic_stream_features", ())
        if str(feature).strip()
    ]
    proof_corpus = manifest.get("proofCorpus")
    selected_tags = sorted(
        {
            str(tag)
            for tag in (
                proof_corpus.get("selectedTags", [])
                if isinstance(proof_corpus, dict)
                else []
            )
            if str(tag).strip()
        }
    )
    scene_records = dynamic_scene_records(manifest, requirements)
    required_scene_records = [
        record for record in scene_records if bool(record.get("required"))
    ]
    required_maps = sorted(
        {
            str(record.get("map", ""))
            for record in required_scene_records
            if str(record.get("kind", "")) == "map" and str(record.get("map", "")).strip()
        }
    )
    required_demos = sorted(
        {
            str(record.get("demo", ""))
            for record in required_scene_records
            if str(record.get("kind", "")) == "demo" and str(record.get("demo", "")).strip()
        }
    )

    screenshots = manifest_glx_screenshot_records(manifest)
    found_screenshot_maps = sorted(
        {
            str(record.get("map", ""))
            for record in screenshots
            if record.get("found")
        }
    )
    histogram_maps = sorted(
        {
            str(record.get("map", ""))
            for record in screenshots
            if record.get("found") and record.get("histogramPassed")
        }
    )
    timedemos = manifest_glx_timedemo_records(manifest)
    found_timedemo_demos = sorted(
        {
            str(record.get("demo", ""))
            for record in timedemos
            if record.get("found")
        }
    )

    dynamic_categories: dict[str, dict[str, int]] = {
        category: {"draws": 0, "attempts": 0, "fallbacks": 0, "observed": 0}
        for category in STREAM_CATEGORY_KEYS
    }
    stream_features = {
        "shadow": 0,
        "beam": 0,
        "dynamicLight": 0,
        "postProcess": 0,
    }
    stream_draws = 0
    stream_attempts = 0
    stream_indexes = 0
    stream_fallbacks = 0
    stream_skips = 0
    stream_gate_records: dict[str, dict[str, int]] = {}
    support_tiers: dict[str, set[str]] = {
        key: set() for key in GLX_DYNAMIC_SUPPORT_KEYS
    }
    product_tiers: set[str] = set()
    source_runs: set[str] = set()

    def record_support(metrics: dict[str, object], section_name: str, tier_label: str) -> None:
        support = metrics.get(section_name)
        if not isinstance(support, dict):
            return
        for key in GLX_DYNAMIC_SUPPORT_KEYS:
            if int_metric(support.get(key)) > 0:
                support_tiers.setdefault(key, set()).add(tier_label)

    def record_dynamic_metrics(metrics: dict[str, object], run_label: str) -> None:
        nonlocal stream_draws, stream_attempts, stream_indexes
        nonlocal stream_fallbacks, stream_skips

        source_runs.add(run_label)
        product_tier = metrics.get("productTier")
        if isinstance(product_tier, dict):
            tier = str(product_tier.get("tier", "")).strip().upper()
            if tier:
                product_tiers.add(tier)

        for section_name, tier_label in (
            ("gl12Support", "GL12"),
            ("gl2xSupport", "GL2X"),
            ("gl3xSupport", "GL3X"),
            ("gl41Support", "GL41"),
            ("gl46Support", "GL46"),
        ):
            record_support(metrics, section_name, tier_label)

        stream_draw = metrics.get("streamDraw")
        if isinstance(stream_draw, dict):
            stream_draws = max(stream_draws, int_metric(stream_draw.get("draws")))
            stream_attempts = max(stream_attempts, int_metric(stream_draw.get("attempts")))
            stream_indexes = max(stream_indexes, int_metric(stream_draw.get("indexes")))
            stream_features["dynamicLight"] = max(
                stream_features["dynamicLight"],
                int_metric(stream_draw.get("dynamicLights")),
            )
            stream_features["shadow"] = max(
                stream_features["shadow"],
                int_metric(stream_draw.get("shadows")),
            )
            stream_features["beam"] = max(
                stream_features["beam"],
                int_metric(stream_draw.get("beams")),
            )
            stream_features["postProcess"] = max(
                stream_features["postProcess"],
                int_metric(stream_draw.get("postprocess")),
            )
            stream_fallbacks = max(stream_fallbacks, int_metric(stream_draw.get("fallbacks")))
            stream_skips = max(stream_skips, int_metric(stream_draw.get("skips")))

        stream_category = metrics.get("streamCategory")
        if isinstance(stream_category, dict):
            for category, record in dynamic_categories.items():
                draws = int_metric(stream_category.get(f"{category}Draws"))
                attempts = int_metric(stream_category.get(f"{category}Attempts"))
                fallbacks = int_metric(stream_category.get(f"{category}Fallbacks"))
                observed = int_metric(stream_category.get(f"{category}Observed"))
                record["draws"] = max(record["draws"], draws)
                record["attempts"] = max(record["attempts"], attempts)
                record["fallbacks"] = max(record["fallbacks"], fallbacks)
                record["observed"] = max(record["observed"], observed, 1 if draws or attempts else 0)

        gates = metrics.get("streamMaterialGate")
        if isinstance(gates, dict):
            for gate_name in ("dynamicLight",):
                record = stream_gate_records.setdefault(
                    gate_name,
                    {"enabled": 0, "accepted": 0, "rejected": 0},
                )
                record["enabled"] = max(record["enabled"], int_metric(gates.get(f"{gate_name}Enabled")))
                record["accepted"] = max(record["accepted"], int_metric(gates.get(f"{gate_name}Accepted")))
                record["rejected"] = max(record["rejected"], int_metric(gates.get(f"{gate_name}Rejected")))

    def record_dynamic_performance(performance: dict[str, object], run_label: str) -> None:
        nonlocal stream_draws, stream_attempts, stream_indexes
        nonlocal stream_fallbacks, stream_skips

        source_runs.add(run_label)
        tier = str(performance_metric(performance, "productTier") or performance_metric(performance, "tier") or "").strip().upper()
        if tier:
            product_tiers.add(tier)
        stream_draws = max(stream_draws, performance_numeric_value(performance, "draws"))
        stream_attempts = max(stream_attempts, performance_numeric_value(performance, "streamDrawAttempts"))
        stream_indexes = max(stream_indexes, performance_numeric_value(performance, "streamDrawIndexes"))
        stream_features["dynamicLight"] = max(
            stream_features["dynamicLight"],
            performance_numeric_value(performance, "streamDrawDynamicLights"),
        )
        stream_features["shadow"] = max(
            stream_features["shadow"],
            performance_numeric_value(performance, "streamDrawShadows"),
        )
        stream_features["beam"] = max(
            stream_features["beam"],
            performance_numeric_value(performance, "streamDrawBeams"),
        )
        stream_features["postProcess"] = max(
            stream_features["postProcess"],
            performance_numeric_value(performance, "streamDrawPostProcess"),
        )
        stream_fallbacks = max(stream_fallbacks, performance_numeric_value(performance, "streamDrawFallbacks"))
        stream_skips = max(stream_skips, performance_numeric_value(performance, "streamDrawSkips"))
        for category, record in dynamic_categories.items():
            suffix = category[0].upper() + category[1:]
            draws = performance_numeric_value(performance, f"streamCategory{suffix}Draws")
            attempts = performance_numeric_value(performance, f"streamCategory{suffix}Attempts")
            record["draws"] = max(record["draws"], draws)
            record["attempts"] = max(record["attempts"], attempts)
            record["observed"] = max(record["observed"], 1 if draws or attempts else 0)

    runs = manifest.get("runs", [])
    if isinstance(runs, list):
        for run_index, run in enumerate(runs, start=1):
            if not isinstance(run, dict):
                continue
            run_label = str(run.get("type", f"run-{run_index}"))
            diagnostics = run.get("diagnostics")
            if isinstance(diagnostics, dict):
                raw_metrics = diagnostics.get("metrics")
                if isinstance(raw_metrics, dict):
                    record_dynamic_metrics(raw_metrics, run_label)
            performance = run.get("performance")
            if isinstance(performance, dict):
                record_dynamic_performance(performance, run_label)

    performance_aggregate = manifest.get("performanceAggregate")
    if isinstance(performance_aggregate, dict):
        record_dynamic_performance(performance_aggregate, "performanceAggregate")

    missing_required_tags = sorted(set(required_tags) - set(selected_tags))
    screenshot_map_set = set(found_screenshot_maps)
    histogram_map_set = set(histogram_maps)
    timedemo_demo_set = set(found_timedemo_demos)
    missing_screenshot_maps = sorted(set(required_maps) - screenshot_map_set)
    missing_histogram_maps = sorted(set(required_maps) - histogram_map_set)
    missing_timedemo_demos = sorted(set(required_demos) - timedemo_demo_set)
    unknown_categories = [
        category for category in required_categories if category not in dynamic_categories
    ]
    missing_category_tags = [
        tag
        for category, tag in GLX_DYNAMIC_CATEGORY_TAGS.items()
        if category in required_categories and tag not in selected_tags
    ]
    missing_categories = [
        category
        for category in required_categories
        if category in dynamic_categories
        and dynamic_categories[category].get("draws", 0) <= 0
    ]
    unknown_stream_features = [
        feature for feature in required_stream_features if feature not in stream_features
    ]
    missing_stream_feature_tags = [
        tag
        for feature, tag in GLX_DYNAMIC_STREAM_FEATURE_TAGS.items()
        if feature in required_stream_features and tag not in selected_tags
    ]
    missing_stream_features = [
        feature
        for feature in required_stream_features
        if feature in stream_features and stream_features.get(feature, 0) <= 0
    ]
    unknown_support = [
        item for item in required_support if item not in GLX_DYNAMIC_SUPPORT_KEYS
    ]
    missing_support = [
        item
        for item in required_support
        if item in GLX_DYNAMIC_SUPPORT_KEYS and not support_tiers.get(item)
    ]
    missing_stream_guards = [
        feature for feature in required_stream_guards if feature not in stream_gate_records
    ]
    unsafe_stream_guards = [
        feature
        for feature in required_stream_guards
        if stream_gate_records.get(feature, {}).get("accepted", 0) > 0
        and feature in forbidden_stream_features
    ]
    forbidden_stream_draws = [
        feature
        for feature in forbidden_stream_features
        if stream_features.get(feature, 0) > 0
    ]
    category_fallbacks = {
        category: record["fallbacks"]
        for category, record in dynamic_categories.items()
        if record.get("fallbacks", 0) > 0
    }

    failures: list[str] = []
    if require_dynamic and not dry_run:
        if missing_required_tags:
            failures.append("Dynamic proof corpus is missing required tag(s): " + ", ".join(missing_required_tags) + ".")
        if required_tags and not required_scene_records:
            failures.append("Dynamic proof did not select any scene for the required dynamic tags.")
        if missing_screenshot_maps:
            failures.append("Dynamic proof is missing GLx screenshots for map(s): " + ", ".join(missing_screenshot_maps) + ".")
        if missing_histogram_maps:
            failures.append("Dynamic proof is missing histogram metadata for map(s): " + ", ".join(missing_histogram_maps) + ".")
        if missing_timedemo_demos:
            failures.append("Dynamic proof is missing GLx timedemo metrics for demo(s): " + ", ".join(missing_timedemo_demos) + ".")
        if unknown_categories:
            failures.append("Dynamic proof requires unknown stream category(s): " + ", ".join(unknown_categories) + ".")
        if missing_category_tags:
            failures.append("Dynamic proof corpus is missing category tag(s): " + ", ".join(missing_category_tags) + ".")
        if missing_categories:
            failures.append("Dynamic proof is missing stream category evidence: " + ", ".join(missing_categories) + ".")
        if unknown_stream_features:
            failures.append("Dynamic proof requires unknown stream feature(s): " + ", ".join(unknown_stream_features) + ".")
        if missing_stream_feature_tags:
            failures.append("Dynamic proof corpus is missing stream feature tag(s): " + ", ".join(missing_stream_feature_tags) + ".")
        if missing_stream_features:
            failures.append("Dynamic proof is missing stream feature evidence: " + ", ".join(missing_stream_features) + ".")
        if unknown_support:
            failures.append("Dynamic proof requires unknown support key(s): " + ", ".join(unknown_support) + ".")
        if missing_support:
            failures.append("Dynamic proof is missing tier-support evidence: " + ", ".join(missing_support) + ".")
        if missing_stream_guards:
            failures.append("Dynamic proof is missing stream guard evidence: " + ", ".join(missing_stream_guards) + ".")
        if unsafe_stream_guards:
            failures.append("Dynamic proof stream guards accepted forbidden feature(s): " + ", ".join(unsafe_stream_guards) + ".")
        if forbidden_stream_draws:
            failures.append(
                "Dynamic proof saw high-risk stream draws in the proof surface: "
                + ", ".join(
                    f"{feature}={stream_features.get(feature, 0)}"
                    for feature in forbidden_stream_draws
                )
                + "."
            )
        if stream_attempts <= 0 and stream_draws <= 0:
            failures.append("Dynamic proof did not observe dynamic stream draw attempts.")
        if stream_indexes <= 0 and stream_draws <= 0:
            failures.append("Dynamic proof did not observe submitted dynamic stream indexes or draws.")
        if stream_fallbacks > 0:
            failures.append(f"Dynamic proof reported stream draw fallbacks: {stream_fallbacks}.")
        if stream_skips > 0:
            failures.append(f"Dynamic proof reported stream draw skips: {stream_skips}.")
        if category_fallbacks:
            failures.append(
                "Dynamic proof reported category fallbacks: "
                + ", ".join(
                    f"{category}={count}"
                    for category, count in sorted(category_fallbacks.items())
                )
                + "."
            )

    status = "not-configured"
    if require_dynamic:
        status = "planned" if dry_run else ("passed" if not failures else "failed")

    return {
        "version": GLX_DYNAMIC_PROOF_VERSION,
        "status": status,
        "requiresDynamicProof": require_dynamic,
        "requiredTags": required_tags,
        "selectedTags": selected_tags,
        "requiredCategories": required_categories,
        "requiredStreamFeatures": required_stream_features,
        "requiredSupport": required_support,
        "requiredStreamGuards": required_stream_guards,
        "forbiddenStreamFeatures": forbidden_stream_features,
        "scenes": scene_records,
        "requiredMaps": required_maps,
        "requiredDemos": required_demos,
        "glxScreenshotMaps": found_screenshot_maps,
        "histogramMaps": histogram_maps,
        "glxTimedemoDemos": found_timedemo_demos,
        "missingScreenshotMaps": [] if dry_run else missing_screenshot_maps,
        "missingTimedemos": [] if dry_run else missing_timedemo_demos,
        "streamDraw": {
            "draws": stream_draws,
            "attempts": stream_attempts,
            "indexes": stream_indexes,
            "fallbacks": stream_fallbacks,
            "skips": stream_skips,
        },
        "streamCategories": dynamic_categories,
        "streamFeatures": dict(stream_features),
        "streamGuards": stream_gate_records,
        "tierSupport": {
            key: sorted(values)
            for key, values in sorted(support_tiers.items())
        },
        "productTiers": sorted(product_tiers),
        "sourceRuns": sorted(source_runs),
        "failures": list(dict.fromkeys(failures)),
    }


def evaluate_dynamic_proof(
    manifest: dict[str, object],
    requirements: dict[str, object],
) -> list[str]:
    if not manifest_requires_dynamic_proof(manifest, requirements):
        return []

    evidence = manifest.get("dynamicProofEvidence")
    if not isinstance(evidence, dict):
        return ["No dynamic proof evidence was recorded."]

    failures: list[str] = []
    if evidence.get("version") != GLX_DYNAMIC_PROOF_VERSION:
        failures.append(
            "Dynamic proof evidence has unsupported version "
            f"{evidence.get('version')!r}."
        )
    if evidence.get("status") != "passed":
        failures.append(
            "Dynamic proof evidence status is "
            f"{evidence.get('status')!r}, expected 'passed'."
        )
    for failure in evidence.get("failures", []):
        if str(failure).strip():
            failures.append(str(failure))
    return list(dict.fromkeys(failures))


def manifest_requires_post_proof(
    manifest: dict[str, object],
    requirements: dict[str, object],
) -> bool:
    return bool(requirements.get("require_post_proof"))


def post_scene_records(
    manifest: dict[str, object],
    requirements: dict[str, object],
) -> list[dict[str, object]]:
    required_tags = {
        str(tag)
        for tag in requirements.get("required_post_tags", ())
        if str(tag).strip()
    }
    post_tags = set(GLX_POST_PROOF_TAGS)
    records: list[dict[str, object]] = []
    for scene_id in manifest_selected_scene_ids(manifest):
        scene = GLX_PROOF_CORPUS_SCENES[scene_id]
        if scene.get("kind") != "map":
            continue
        tags = {str(tag) for tag in scene.get("tags", ()) if str(tag).strip()}
        if not tags.intersection(post_tags) and not tags.intersection(required_tags):
            continue
        records.append(
            {
                "sceneId": scene_id,
                "map": str(scene.get("target", "")).strip().lower(),
                "assetTier": scene.get("assetTier", ""),
                "tags": sorted(tags),
                "required": bool(tags.intersection(required_tags)),
            }
        )
    return records


def post_proof_evidence(
    manifest: dict[str, object],
    requirements: dict[str, object],
) -> dict[str, object]:
    dry_run = bool(manifest.get("dryRun"))
    require_post = manifest_requires_post_proof(manifest, requirements)
    required_tags = sorted(
        {
            str(tag)
            for tag in requirements.get("required_post_tags", ())
            if str(tag).strip()
        }
    )
    required_features = [
        str(feature)
        for feature in requirements.get("required_post_features", ())
        if str(feature).strip()
    ]
    proof_corpus = manifest.get("proofCorpus")
    selected_tags = sorted(
        {
            str(tag)
            for tag in (
                proof_corpus.get("selectedTags", [])
                if isinstance(proof_corpus, dict)
                else []
            )
            if str(tag).strip()
        }
    )
    scene_records = post_scene_records(manifest, requirements)
    required_scene_records = [
        record for record in scene_records if bool(record.get("required"))
    ]
    required_maps = sorted(
        {
            str(record.get("map", ""))
            for record in required_scene_records
            if str(record.get("map", "")).strip()
        }
    )

    screenshots = manifest_glx_screenshot_records(manifest)
    found_screenshot_maps = sorted(
        {
            str(record.get("map", ""))
            for record in screenshots
            if record.get("found")
        }
    )
    histogram_maps = sorted(
        {
            str(record.get("map", ""))
            for record in screenshots
            if record.get("found") and record.get("histogramPassed")
        }
    )

    fbo_requested = 0
    fbo_ready = 0
    fbo_programs = 0
    fbo_framebuffer = 0
    fbo_init_attempts = 0
    fbo_init_failed = 0
    frames = 0
    screenshots_count = 0
    minimized_output = 0
    feature_frames = {
        "renderScale": 0,
        "greyscale": 0,
        "windowAdjusted": 0,
        "minimized": 0,
    }
    controls = {
        "renderScale": 0,
        "greyscale": 0.0,
        "windowAdjusted": 0,
    }
    target = {
        "renderWidth": 0,
        "renderHeight": 0,
        "captureWidth": 0,
        "captureHeight": 0,
        "windowWidth": 0,
        "windowHeight": 0,
    }
    post_output = {
        "mode": "",
        "postNodes": 0,
        "outputs": 0,
        "executableNodes": 0,
        "executableOutputs": 0,
        "legacyFallback": 0,
        "postHash": 0,
        "outputHash": 0,
        "planHash": 0,
        "fallbackMask": 0,
    }
    post_shader_direct = {
        "found": False,
        "execute": 0,
        "eligible": 0,
        "bound": 0,
        "reject": 0,
        "candidates": 0,
        "eligibleFrames": 0,
        "attempts": 0,
        "binds": 0,
        "fallbacks": 0,
        "rejects": 0,
        "programMisses": 0,
        "uniformFailures": 0,
    }
    color_contract = 0
    source_runs: set[str] = set()

    def record_post_metrics(metrics: dict[str, object], run_label: str) -> None:
        nonlocal fbo_requested, fbo_ready, fbo_programs, fbo_framebuffer
        nonlocal fbo_init_attempts, fbo_init_failed, frames, screenshots_count
        nonlocal minimized_output, color_contract

        source_runs.add(run_label)
        postprocess = metrics.get("postprocess")
        if isinstance(postprocess, dict):
            fbo_requested = max(fbo_requested, int_metric(postprocess.get("fboRequested")))
            fbo_ready = max(fbo_ready, int_metric(postprocess.get("fboReady")))
            fbo_programs = max(fbo_programs, int_metric(postprocess.get("fboPrograms")))
            fbo_framebuffer = max(fbo_framebuffer, int_metric(postprocess.get("fboFramebuffer")))
            fbo_init_attempts = max(fbo_init_attempts, int_metric(postprocess.get("fboAttempts")))
            fbo_init_failed = max(fbo_init_failed, int_metric(postprocess.get("fboFailed")))
            if str(postprocess.get("lastOutput", "")).lower() == "minimized":
                minimized_output = max(minimized_output, 1)

        post_controls = metrics.get("postprocessControls")
        if isinstance(post_controls, dict):
            controls["renderScale"] = max(controls["renderScale"], int_metric(post_controls.get("renderScale")))
            controls["greyscale"] = max(controls["greyscale"], float_metric(post_controls.get("greyscale")))
            controls["windowAdjusted"] = max(controls["windowAdjusted"], int_metric(post_controls.get("windowAdjusted")))

        post_frames = metrics.get("postprocessFrames")
        if isinstance(post_frames, dict):
            frames = max(frames, int_metric(post_frames.get("frames")))
            screenshots_count = max(screenshots_count, int_metric(post_frames.get("screenshots")))
            minimized_output = max(minimized_output, int_metric(post_frames.get("minimizedOutput")))

        features = metrics.get("postprocessFrameFeatures")
        if isinstance(features, dict):
            feature_frames["renderScale"] = max(feature_frames["renderScale"], int_metric(features.get("renderScale")))
            feature_frames["greyscale"] = max(feature_frames["greyscale"], int_metric(features.get("greyscale")))
            feature_frames["windowAdjusted"] = max(feature_frames["windowAdjusted"], int_metric(features.get("windowAdjusted")))
            feature_frames["minimized"] = max(feature_frames["minimized"], int_metric(features.get("minimized")))

        target_format = metrics.get("targetFormat")
        if isinstance(target_format, dict):
            for key in target:
                target[key] = max(target[key], int_metric(target_format.get(key)))

        ownership = metrics.get("postOutputOwnership")
        if isinstance(ownership, dict):
            post_output["mode"] = str(ownership.get("mode", post_output["mode"]))
            for key in (
                "postNodes",
                "outputs",
                "executableNodes",
                "executableOutputs",
                "legacyFallback",
                "postHash",
                "outputHash",
                "planHash",
                "fallbackMask",
            ):
                post_output[key] = max(int_metric(post_output.get(key)), int_metric(ownership.get(key)))

        direct_final = metrics.get("postShaderDirectFinal")
        if isinstance(direct_final, dict):
            post_shader_direct["found"] = True
            for key in (
                "execute",
                "eligible",
                "bound",
                "reject",
                "candidates",
                "eligibleFrames",
                "attempts",
                "binds",
                "fallbacks",
                "rejects",
                "programMisses",
                "uniformFailures",
            ):
                post_shader_direct[key] = max(
                    int_metric(post_shader_direct.get(key)),
                    int_metric(direct_final.get(key)),
                )

        audit = metrics.get("colorAudit")
        if isinstance(audit, dict):
            color_contract = max(color_contract, int_metric(audit.get("contract")))

    def record_post_performance(performance: dict[str, object], run_label: str) -> None:
        nonlocal fbo_ready, frames, screenshots_count, minimized_output, color_contract

        source_runs.add(run_label)
        fbo = str(performance_metric(performance, "fbo") or "").lower()
        if fbo == "ready":
            fbo_ready = max(fbo_ready, 1)
        controls["renderScale"] = max(controls["renderScale"], performance_numeric_value(performance, "postprocessRenderScaleMode"))
        controls["greyscale"] = max(controls["greyscale"], float_metric(performance_metric(performance, "postprocessGreyscale")))
        controls["windowAdjusted"] = max(controls["windowAdjusted"], performance_numeric_value(performance, "postprocessWindowAdjusted"))
        frames = max(frames, performance_numeric_value(performance, "postprocessFrames"))
        screenshots_count = max(screenshots_count, performance_numeric_value(performance, "postprocessScreenshots"))
        minimized_output = max(minimized_output, performance_numeric_value(performance, "postprocessMinimizedOutput"))
        feature_frames["renderScale"] = max(feature_frames["renderScale"], performance_numeric_value(performance, "postprocessFeatureRenderScale"))
        feature_frames["greyscale"] = max(feature_frames["greyscale"], performance_numeric_value(performance, "postprocessFeatureGreyscale"))
        feature_frames["windowAdjusted"] = max(feature_frames["windowAdjusted"], performance_numeric_value(performance, "postprocessFeatureWindowAdjusted"))
        feature_frames["minimized"] = max(feature_frames["minimized"], performance_numeric_value(performance, "postprocessFeatureMinimized"))
        for key in target:
            metric_key = f"target{key[0].upper()}{key[1:]}"
            target[key] = max(target[key], performance_numeric_value(performance, metric_key))
        mode = performance_metric(performance, "postOutputMode")
        if mode is not None:
            post_output["mode"] = str(mode)
        post_output["postNodes"] = max(post_output["postNodes"], performance_numeric_value(performance, "postOutputPostNodes"))
        post_output["outputs"] = max(post_output["outputs"], performance_numeric_value(performance, "postOutputOutputs"))
        post_output["executableNodes"] = max(
            post_output["executableNodes"],
            performance_numeric_value(performance, "postOutputExecutableNodes"),
        )
        post_output["executableOutputs"] = max(
            post_output["executableOutputs"],
            performance_numeric_value(performance, "postOutputExecutableOutputs"),
        )
        post_output["legacyFallback"] = max(post_output["legacyFallback"], performance_numeric_value(performance, "postOutputLegacyFallback"))
        post_output["postHash"] = max(post_output["postHash"], performance_numeric_value(performance, "postOutputPostHash"))
        post_output["outputHash"] = max(post_output["outputHash"], performance_numeric_value(performance, "postOutputOutputHash"))
        post_output["planHash"] = max(post_output["planHash"], performance_numeric_value(performance, "postOutputPlanHash"))
        post_output["fallbackMask"] = max(post_output["fallbackMask"], performance_numeric_value(performance, "postOutputFallbackMask"))
        if any(
            performance_metric(performance, key) is not None for key in (
                "postShaderDirectFinalExecute",
                "postShaderDirectFinalCandidates",
                "postShaderDirectFinalBinds",
            )
        ):
            post_shader_direct["found"] = True
        for metric_key, target_key in (
            ("postShaderDirectFinalExecute", "execute"),
            ("postShaderDirectFinalEligible", "eligible"),
            ("postShaderDirectFinalBound", "bound"),
            ("postShaderDirectFinalReject", "reject"),
            ("postShaderDirectFinalCandidates", "candidates"),
            ("postShaderDirectFinalEligibleFrames", "eligibleFrames"),
            ("postShaderDirectFinalAttempts", "attempts"),
            ("postShaderDirectFinalBinds", "binds"),
            ("postShaderDirectFinalFallbacks", "fallbacks"),
            ("postShaderDirectFinalRejects", "rejects"),
            ("postShaderDirectFinalProgramMisses", "programMisses"),
            ("postShaderDirectFinalUniformFailures", "uniformFailures"),
        ):
            post_shader_direct[target_key] = max(
                int_metric(post_shader_direct.get(target_key)),
                performance_numeric_value(performance, metric_key),
            )
        color_contract = max(color_contract, performance_numeric_value(performance, "colorOutputContract"))

    runs = manifest.get("runs", [])
    if isinstance(runs, list):
        for run_index, run in enumerate(runs, start=1):
            if not isinstance(run, dict):
                continue
            run_label = str(run.get("type", f"run-{run_index}"))
            diagnostics = run.get("diagnostics")
            if isinstance(diagnostics, dict):
                raw_metrics = diagnostics.get("metrics")
                if isinstance(raw_metrics, dict):
                    record_post_metrics(raw_metrics, run_label)
            performance = run.get("performance")
            if isinstance(performance, dict):
                record_post_performance(performance, run_label)

    performance_aggregate = manifest.get("performanceAggregate")
    if isinstance(performance_aggregate, dict):
        record_post_performance(performance_aggregate, "performanceAggregate")

    selected_tag_set = set(selected_tags)
    missing_required_tags = sorted(set(required_tags) - selected_tag_set)
    screenshot_map_set = set(found_screenshot_maps)
    histogram_map_set = set(histogram_maps)
    missing_screenshot_maps = sorted(set(required_maps) - screenshot_map_set)
    missing_histogram_maps = sorted(set(required_maps) - histogram_map_set)
    unknown_features = [
        feature for feature in required_features if feature not in GLX_POST_FEATURE_TAGS
    ]
    missing_feature_tags = [
        tag
        for feature, tag in GLX_POST_FEATURE_TAGS.items()
        if feature in required_features and tag not in selected_tag_set
    ]
    render_scale_dimension_evidence = (
        target["renderWidth"] > 0
        and target["renderHeight"] > 0
        and target["captureWidth"] > 0
        and target["captureHeight"] > 0
        and target["windowWidth"] > 0
        and target["windowHeight"] > 0
        and (
            target["renderWidth"] != target["windowWidth"]
            or target["renderHeight"] != target["windowHeight"]
            or target["captureWidth"] != target["windowWidth"]
            or target["captureHeight"] != target["windowHeight"]
        )
    )
    feature_evidence = {
        "greyscale": {
            "control": controls["greyscale"],
            "frames": feature_frames["greyscale"],
            "ok": controls["greyscale"] > 0.0 and feature_frames["greyscale"] > 0,
        },
        "renderScale": {
            "control": controls["renderScale"],
            "frames": feature_frames["renderScale"],
            "dimensionEvidence": render_scale_dimension_evidence,
            "ok": (
                controls["renderScale"] > 0
                and feature_frames["renderScale"] > 0
                and render_scale_dimension_evidence
            ),
        },
    }
    missing_features = [
        feature
        for feature in required_features
        if feature in feature_evidence and not feature_evidence[feature]["ok"]
    ]

    failures: list[str] = []
    if require_post and not dry_run:
        if missing_required_tags:
            failures.append("Post proof corpus is missing required tag(s): " + ", ".join(missing_required_tags) + ".")
        if required_tags and not required_maps:
            failures.append("Post proof did not select any map scene for the required post tags.")
        if missing_screenshot_maps:
            failures.append("Post proof is missing GLx screenshots for map(s): " + ", ".join(missing_screenshot_maps) + ".")
        if missing_histogram_maps:
            failures.append("Post proof is missing histogram metadata for map(s): " + ", ".join(missing_histogram_maps) + ".")
        if unknown_features:
            failures.append("Post proof requires unknown feature(s): " + ", ".join(unknown_features) + ".")
        if missing_feature_tags:
            failures.append("Post proof corpus is missing feature tag(s): " + ", ".join(missing_feature_tags) + ".")
        if missing_features:
            failures.append("Post proof is missing feature evidence: " + ", ".join(missing_features) + ".")
        if fbo_requested <= 0:
            failures.append("Post proof did not observe postprocess FBO requested.")
        if fbo_ready <= 0:
            failures.append("Post proof did not observe a ready postprocess FBO.")
        if fbo_init_failed > 0:
            failures.append(f"Post proof reported FBO init failures: {fbo_init_failed}.")
        if frames <= 0:
            failures.append("Post proof did not observe postprocess frames.")
        if minimized_output > 0 or feature_frames["minimized"] > 0:
            failures.append(
                "Post proof reported minimized output/frame evidence: "
                f"output={minimized_output}, frames={feature_frames['minimized']}."
            )
        if color_contract <= 0:
            failures.append("Post proof did not observe a valid output color contract.")

    status = "not-configured"
    if require_post:
        status = "planned" if dry_run else ("passed" if not failures else "failed")

    return {
        "version": GLX_POST_PROOF_VERSION,
        "status": status,
        "requiresPostProof": require_post,
        "requiredTags": required_tags,
        "selectedTags": selected_tags,
        "requiredFeatures": required_features,
        "scenes": scene_records,
        "requiredMaps": required_maps,
        "glxScreenshotMaps": found_screenshot_maps,
        "histogramMaps": histogram_maps,
        "missingScreenshotMaps": [] if dry_run else missing_screenshot_maps,
        "fbo": {
            "requested": fbo_requested,
            "ready": fbo_ready,
            "programs": fbo_programs,
            "framebufferFns": fbo_framebuffer,
            "initAttempts": fbo_init_attempts,
            "initFailures": fbo_init_failed,
        },
        "controls": dict(controls),
        "frames": {
            "post": frames,
            "screenshots": screenshots_count,
            "minimizedOutput": minimized_output,
        },
        "frameFeatures": dict(feature_frames),
        "featureEvidence": feature_evidence,
        "target": dict(target),
        "postOutputOwnership": dict(post_output),
        "postShaderDirectFinal": dict(post_shader_direct),
        "colorContract": color_contract,
        "sourceRuns": sorted(source_runs),
        "failures": list(dict.fromkeys(failures)),
    }


def evaluate_post_proof(
    manifest: dict[str, object],
    requirements: dict[str, object],
) -> list[str]:
    if not manifest_requires_post_proof(manifest, requirements):
        return []

    evidence = manifest.get("postProofEvidence")
    if not isinstance(evidence, dict):
        return ["No post proof evidence was recorded."]

    failures: list[str] = []
    if evidence.get("version") != GLX_POST_PROOF_VERSION:
        failures.append(
            "Post proof evidence has unsupported version "
            f"{evidence.get('version')!r}."
        )
    if evidence.get("status") != "passed":
        failures.append(
            "Post proof evidence status is "
            f"{evidence.get('status')!r}, expected 'passed'."
        )
    for failure in evidence.get("failures", []):
        if str(failure).strip():
            failures.append(str(failure))
    return list(dict.fromkeys(failures))


def manifest_requires_ownership_proof(manifest: dict[str, object]) -> bool:
    profile = str(manifest.get("profile", ""))
    if profile_requires_glx_ownership(profile):
        return True

    for section_name in ("cvars", "startupCvars", "configCvars"):
        section = manifest.get(section_name)
        if isinstance(section, dict) and q3_bool(section.get("r_glxRequireOwnership", 0)):
            return True
    return False


def ownership_tier_diagnostics(metrics: dict[str, object]) -> dict[str, object]:
    product_tier = metrics.get("productTier")
    tier = ""
    if isinstance(product_tier, dict):
        tier = str(product_tier.get("tier", "")).strip().upper()

    if tier == "GL3X":
        executor_name = "gl3xExecutor"
        support_name = "gl3xSupport"
        require_fbo_post = True
    elif tier == "GL41":
        executor_name = "gl41Executor"
        support_name = "gl41Support"
        require_fbo_post = True
    elif tier == "GL46":
        executor_name = "gl46Executor"
        support_name = "gl46Support"
        require_fbo_post = False
    else:
        return {
            "tier": tier,
            "modern": False,
            "found": False,
            "active": False,
            "fboPostProcess": False,
            "modernPostChain": False,
            "sceneLinearOutput": False,
            "ok": False,
        }

    executor = metrics.get(executor_name)
    support = metrics.get(support_name)
    found = isinstance(executor, dict) or isinstance(support, dict)
    active = isinstance(executor, dict) and int_metric(executor.get("active")) > 0
    fbo_post = (
        not require_fbo_post
        or (isinstance(executor, dict) and int_metric(executor.get("fboPostProcess")) > 0)
    )
    modern_post = isinstance(support, dict) and int_metric(support.get("modernPostChain")) > 0
    scene_linear = isinstance(support, dict) and int_metric(support.get("sceneLinearOutput")) > 0
    return {
        "tier": tier,
        "modern": True,
        "found": found,
        "active": active,
        "fboPostProcess": fbo_post,
        "modernPostChain": modern_post,
        "sceneLinearOutput": scene_linear,
        "ok": bool(found and active and fbo_post and modern_post and scene_linear),
    }


def ownership_proof_evidence(manifest: dict[str, object]) -> dict[str, object]:
    dry_run = bool(manifest.get("dryRun"))
    profile = str(manifest.get("profile", ""))
    require_ownership = manifest_requires_ownership_proof(manifest)
    ownership_found = False
    product_tiers: set[str] = set()
    post_output_found = False
    post_output_modes: set[str] = set()
    post_nodes = 0
    outputs = 0
    executable_nodes = 0
    executable_outputs = 0
    executable_counts_found = False
    legacy_fallback = 0
    fallback_mask = 0
    post_hash = 0
    output_hash = 0
    plan_hash = 0
    post_shader_direct = {
        "found": False,
        "execute": 0,
        "eligible": 0,
        "bound": 0,
        "reject": 0,
        "candidates": 0,
        "eligibleFrames": 0,
        "attempts": 0,
        "binds": 0,
        "fallbacks": 0,
        "rejects": 0,
        "programMisses": 0,
        "uniformFailures": 0,
    }
    diagnostic_failures = 0
    max_calls = 0
    max_items = 0
    delegation_breakdown = {
        "generic": 0,
        "vboDevice": 0,
        "vboSoft": 0,
        "arrays": 0,
    }
    tier_records: list[dict[str, object]] = []
    source_runs: list[str] = []

    def record_tier(value: object) -> None:
        tier = str(value or "").strip().upper()
        if tier in GLX_PRODUCT_TIERS:
            product_tiers.add(tier)

    def record_post_output(
        mode: object,
        node_count: object,
        output_count: object,
        fallback: object,
        node_hash: object = None,
        transform_hash: object = None,
        graph_hash: object = None,
        mask: object = None,
        executable_node_count: object = None,
        executable_output_count: object = None,
    ) -> None:
        nonlocal executable_counts_found, executable_nodes, executable_outputs
        nonlocal post_output_found, post_nodes, outputs, legacy_fallback
        nonlocal fallback_mask, post_hash, output_hash, plan_hash

        if (
            mode is None and node_count is None and output_count is None and
            fallback is None and node_hash is None and transform_hash is None and
            graph_hash is None and mask is None and executable_node_count is None and
            executable_output_count is None
        ):
            return
        post_output_found = True
        if mode is not None:
            post_output_modes.add(str(mode).strip().lower())
        post_nodes = max(post_nodes, int_metric(node_count))
        outputs = max(outputs, int_metric(output_count))
        if executable_node_count is not None or executable_output_count is not None:
            executable_counts_found = True
        executable_nodes = max(executable_nodes, int_metric(executable_node_count))
        executable_outputs = max(executable_outputs, int_metric(executable_output_count))
        legacy_fallback = max(legacy_fallback, int_metric(fallback))
        fallback_mask = max(fallback_mask, int_metric(mask))
        post_hash = max(post_hash, int_metric(node_hash))
        output_hash = max(output_hash, int_metric(transform_hash))
        plan_hash = max(plan_hash, int_metric(graph_hash))

    runs = manifest.get("runs", [])
    if isinstance(runs, list):
        for run_index, run in enumerate(runs, start=1):
            if not isinstance(run, dict):
                continue
            run_label = str(run.get("type", f"run-{run_index}"))
            diagnostics = run.get("diagnostics")
            metrics: dict[str, object] = {}
            if isinstance(diagnostics, dict):
                failures = diagnostics.get("failures", [])
                if isinstance(failures, list):
                    diagnostic_failures += len([failure for failure in failures if str(failure).strip()])
                raw_metrics = diagnostics.get("metrics")
                if isinstance(raw_metrics, dict):
                    metrics = raw_metrics
            if metrics:
                source_runs.append(run_label)

            ownership = metrics.get("ownership")
            if isinstance(ownership, dict):
                ownership_found = True
                max_calls = max(max_calls, int_metric(ownership.get("calls")))
                max_items = max(max_items, int_metric(ownership.get("items")))
                for key in delegation_breakdown:
                    delegation_breakdown[key] = max(
                        delegation_breakdown[key],
                        int_metric(ownership.get(key)),
                    )

            product_tier = metrics.get("productTier")
            if isinstance(product_tier, dict):
                record_tier(product_tier.get("tier"))
            tier_record = ownership_tier_diagnostics(metrics)
            if tier_record.get("tier"):
                tier_records.append(tier_record)

            post_output = metrics.get("postOutputOwnership")
            if isinstance(post_output, dict):
                record_post_output(
                    post_output.get("mode"),
                    post_output.get("postNodes"),
                    post_output.get("outputs"),
                    post_output.get("legacyFallback"),
                    post_output.get("postHash"),
                    post_output.get("outputHash"),
                    post_output.get("planHash"),
                    post_output.get("fallbackMask"),
                    post_output.get("executableNodes"),
                    post_output.get("executableOutputs"),
                )

            direct_final = metrics.get("postShaderDirectFinal")
            if isinstance(direct_final, dict):
                post_shader_direct["found"] = True
                for key in (
                    "execute",
                    "eligible",
                    "bound",
                    "reject",
                    "candidates",
                    "eligibleFrames",
                    "attempts",
                    "binds",
                    "fallbacks",
                    "rejects",
                    "programMisses",
                    "uniformFailures",
                ):
                    post_shader_direct[key] = max(
                        int_metric(post_shader_direct.get(key)),
                        int_metric(direct_final.get(key)),
                    )

            performance = run.get("performance")
            if isinstance(performance, dict):
                latest = performance.get("latest")
                if isinstance(latest, dict):
                    record_tier(latest.get("productTier", latest.get("tier")))
                    record_post_output(
                        latest.get("postOutputMode"),
                        latest.get("postOutputPostNodes"),
                        latest.get("postOutputOutputs"),
                        latest.get("postOutputLegacyFallback"),
                        latest.get("postOutputPostHash"),
                        latest.get("postOutputOutputHash"),
                        latest.get("postOutputPlanHash"),
                        latest.get("postOutputFallbackMask"),
                        latest.get("postOutputExecutableNodes"),
                        latest.get("postOutputExecutableOutputs"),
                    )
                    if any(
                        latest.get(key) is not None for key in (
                            "postShaderDirectFinalExecute",
                            "postShaderDirectFinalCandidates",
                            "postShaderDirectFinalBinds",
                        )
                    ):
                        post_shader_direct["found"] = True
                    for metric_key, target_key in (
                        ("postShaderDirectFinalExecute", "execute"),
                        ("postShaderDirectFinalEligible", "eligible"),
                        ("postShaderDirectFinalBound", "bound"),
                        ("postShaderDirectFinalReject", "reject"),
                        ("postShaderDirectFinalCandidates", "candidates"),
                        ("postShaderDirectFinalEligibleFrames", "eligibleFrames"),
                        ("postShaderDirectFinalAttempts", "attempts"),
                        ("postShaderDirectFinalBinds", "binds"),
                        ("postShaderDirectFinalFallbacks", "fallbacks"),
                        ("postShaderDirectFinalRejects", "rejects"),
                        ("postShaderDirectFinalProgramMisses", "programMisses"),
                        ("postShaderDirectFinalUniformFailures", "uniformFailures"),
                    ):
                        post_shader_direct[target_key] = max(
                            int_metric(post_shader_direct.get(target_key)),
                            int_metric(latest.get(metric_key)),
                        )

    modern_tier = bool(product_tiers.intersection({"GL3X", "GL41", "GL46"}))
    modern_tier_diagnostics_found = any(bool(record.get("found")) for record in tier_records)
    modern_tier_diagnostics_ok = any(bool(record.get("ok")) for record in tier_records)
    zero_delegation = ownership_found and max_calls == 0 and max_items == 0 and diagnostic_failures == 0
    modern_post_output = (
        post_output_found
        and post_output_modes == {"glx-owned"}
        and post_nodes > 0
        and outputs > 0
        and legacy_fallback == 0
        and fallback_mask == 0
        and (not executable_counts_found or (executable_nodes > 0 and executable_outputs > 0))
        and post_hash > 0
        and output_hash > 0
        and plan_hash > 0
        and modern_tier
    )

    failures: list[str] = []
    if require_ownership and not dry_run:
        if not ownership_found:
            failures.append("Ownership proof did not include legacy-delegation diagnostics.")
        if max_calls or max_items:
            failures.append(
                f"Ownership proof still reported legacy delegation: {max_calls} calls / {max_items} items."
            )
        if diagnostic_failures:
            failures.append(f"Ownership proof diagnostics reported {diagnostic_failures} failure(s).")
        if not modern_tier:
            failures.append("Ownership proof did not run on a GL3X+ product tier.")
        if not modern_tier_diagnostics_found:
            failures.append("Ownership proof did not include modern-tier diagnostics.")
        elif not modern_tier_diagnostics_ok:
            failures.append("Ownership proof modern-tier diagnostics did not prove post-chain and scene-linear support.")
        if not post_output_found:
            failures.append("Ownership proof did not include post/output ownership diagnostics.")
        elif post_output_modes != {"glx-owned"}:
            failures.append(
                "Ownership proof post/output mode was not exclusively glx-owned "
                f"({','.join(sorted(post_output_modes)) or '-'})."
            )
        if legacy_fallback:
            failures.append("Ownership proof post/output still reported legacy fallback.")
        if fallback_mask:
            failures.append(f"Ownership proof post/output plan reported fallback mask 0x{fallback_mask:08x}.")
        if executable_counts_found and executable_nodes <= 0:
            failures.append("Ownership proof did not report executable GLx post nodes.")
        if executable_counts_found and executable_outputs <= 0:
            failures.append("Ownership proof did not report executable GLx output transforms.")
        if post_nodes <= 0:
            failures.append("Ownership proof did not execute GLx post nodes.")
        if outputs <= 0:
            failures.append("Ownership proof did not execute GLx output transforms.")
        if post_hash <= 0:
            failures.append("Ownership proof did not report a post-node fingerprint.")
        if output_hash <= 0:
            failures.append("Ownership proof did not report an output-transform fingerprint.")
        if plan_hash <= 0:
            failures.append("Ownership proof did not report a post/output plan fingerprint.")

    status = "not-configured"
    if require_ownership:
        status = "planned" if dry_run else ("passed" if not failures else "failed")

    return {
        "version": GLX_OWNERSHIP_PROOF_VERSION,
        "status": status,
        "profile": profile,
        "requiresOwnership": require_ownership,
        "zeroDelegation": zero_delegation,
        "delegation": {
            "found": ownership_found,
            "calls": max_calls,
            "items": max_items,
            **delegation_breakdown,
        },
        "diagnosticFailures": diagnostic_failures,
        "productTiers": sorted(product_tiers),
        "modernPostOutputTier": modern_tier,
        "modernTierDiagnosticsFound": modern_tier_diagnostics_found,
        "modernTierDiagnosticsOk": modern_tier_diagnostics_ok,
        "tierDiagnostics": tier_records,
        "postOutputOwnership": {
            "found": post_output_found,
            "modes": sorted(post_output_modes),
            "postNodes": post_nodes,
            "outputs": outputs,
            "executableCountsFound": executable_counts_found,
            "executableNodes": executable_nodes,
            "executableOutputs": executable_outputs,
            "legacyFallback": legacy_fallback,
            "postHash": post_hash,
            "outputHash": output_hash,
            "planHash": plan_hash,
            "fallbackMask": fallback_mask,
        },
        "postShaderDirectFinal": dict(post_shader_direct),
        "modernPostOutput": modern_post_output,
        "sourceRuns": sorted(set(source_runs)),
        "failures": list(dict.fromkeys(failures)),
    }


def color_sweep_metric_matches(actual: object, expected: object) -> bool:
    if isinstance(expected, str) and expected.startswith("0x"):
        try:
            return normalized_hex(actual) == normalized_hex(expected)
        except (TypeError, ValueError):
            return False
    if isinstance(expected, bool):
        return bool(actual) == expected
    if isinstance(expected, int):
        return actual == expected
    if isinstance(expected, float):
        try:
            return abs(float(actual) - expected) <= 0.0001
        except (TypeError, ValueError):
            return False
    return str(actual).lower() == str(expected).lower()


def color_frame_metric_matches(actual: object, expectation_key: str, expected: object) -> bool:
    if expectation_key == "finalEncode":
        expected_shader_encode = str(expected).lower() == "shader-srgb"
        return color_sweep_metric_matches(actual, expected_shader_encode)
    return color_sweep_metric_matches(actual, expected)


def evaluate_color_sweep(manifest: dict[str, object]) -> list[str]:
    failures: list[str] = []
    runs_by_id = {color_sweep_row_id(run): run for run in color_sweep_runs(manifest)}
    expected_rows = {str(row["id"]): row for row in GLX_COLOR_SWEEP_MATRIX}
    missing_rows = [row_id for row_id in expected_rows if row_id not in runs_by_id]
    if missing_rows:
        failures.append(
            "GLx color sweep is missing required row(s): " + ", ".join(missing_rows) + "."
        )

    for row_id, row in expected_rows.items():
        run = runs_by_id.get(row_id)
        if not run:
            continue
        if run.get("status") not in {"passed", "planned"}:
            failures.append(f"GLx color sweep row {row_id} did not pass: {run.get('status')}.")

        screenshots_value = run.get("screenshots", [])
        screenshots = [
            shot for shot in screenshots_value if isinstance(shot, dict)
        ] if isinstance(screenshots_value, list) else []
        if not screenshots:
            failures.append(f"GLx color sweep row {row_id} did not capture a screenshot.")
        for shot in screenshots:
            histogram = shot.get("histogram")
            if not shot.get("found") or not isinstance(histogram, dict) or histogram.get("status") != "passed":
                failures.append(f"GLx color sweep row {row_id} is missing screenshot histogram metadata.")
            if shot.get("found") and not screenshot_luma_false_color_passed(shot):
                failures.append(f"GLx color sweep row {row_id} is missing luma false-color sidecar metadata.")
            if shot.get("found") and not screenshot_exposure_false_color_passed(shot):
                failures.append(f"GLx color sweep row {row_id} is missing exposure false-color sidecar metadata.")

        diagnostics = run.get("diagnostics")
        if not isinstance(diagnostics, dict) or not diagnostics.get("found"):
            failures.append(f"GLx color sweep row {row_id} is missing GLx diagnostics.")
        performance = run.get("performance")
        if not isinstance(performance, dict) or int(performance.get("sampleCount", 0)) <= 0:
            failures.append(f"GLx color sweep row {row_id} is missing r_speeds 7 performance metadata.")
        color_frame_samples = color_sweep_metric(run, "colorFrame", "samples")
        performance_latest = performance.get("latest", {}) if isinstance(performance, dict) else {}
        if (
            not isinstance(color_frame_samples, (int, float))
            or int(color_frame_samples) <= 0
        ) and (
            not isinstance(performance_latest, dict)
            or int(performance_latest.get("colorFrameSamples", 0)) <= 0
        ):
            failures.append(f"GLx color sweep row {row_id} is missing per-frame color-pipeline metadata.")

        expectations = row.get("expect", {})
        if not isinstance(expectations, dict):
            continue
        checks = {
            "space": ("colorPipeline", "space"),
            "transfer": ("colorPipeline", "transfer"),
            "toneMap": ("colorPipeline", "toneMap"),
            "exposure": ("colorPipeline", "exposure"),
            "paperWhiteNits": ("colorPipeline", "paperWhite"),
            "maxOutputNits": ("colorPipeline", "maxOutput"),
            "sceneTargetFloat": ("colorAudit", "targetFloat"),
            "finalEncode": ("colorAudit", "finalEncode"),
            "contract": ("colorAudit", "contract"),
            "framebufferSrgb": ("colorAudit", "framebufferSrgb"),
            "srgbDecode": ("colorAudit", "srgbDecode"),
            "srgbRequested": ("colorAudit", "srgbRequested"),
            "capture": ("colorAudit", "capture"),
            "captureRequest": ("colorAudit", "captureRequest"),
            "captureHdrAware": ("colorAudit", "captureHdrAware"),
            "captureSupported": ("colorAudit", "captureSupported"),
            "outputRequest": ("outputBackend", "request"),
            "outputSelected": ("outputBackend", "selected"),
            "internalFormat": ("targetFormat", "internalFormat"),
            "textureFormat": ("targetFormat", "textureFormat"),
            "textureType": ("targetFormat", "textureType"),
        }
        for expectation_key, metric_key in checks.items():
            if expectation_key not in expectations:
                continue
            actual = color_sweep_metric(run, metric_key[0], metric_key[1])
            if actual is None:
                failures.append(
                    f"GLx color sweep row {row_id} is missing {metric_key[0]}.{metric_key[1]}."
                )
            elif not color_sweep_metric_matches(actual, expectations[expectation_key]):
                failures.append(
                    f"GLx color sweep row {row_id} {metric_key[0]}.{metric_key[1]} "
                    f"is {actual!r}; expected {expectations[expectation_key]!r}."
                )

        color_frame = color_sweep_metric(run, "colorFrame", "latest")
        if isinstance(color_frame, dict):
            frame_checks = {
                "space": "space",
                "transfer": "transfer",
                "exposure": "exposure",
                "paperWhiteNits": "paperWhiteNits",
                "maxOutputNits": "maxOutputNits",
                "sceneTargetFloat": "sceneTargetFloat",
                "finalEncode": "shaderSrgbEncode",
                "contract": "contractValid",
                "framebufferSrgb": "framebufferSrgb",
                "srgbDecode": "srgbDecode",
                "internalFormat": "internalFormat",
                "textureFormat": "textureFormat",
                "textureType": "textureType",
            }
            for expectation_key, frame_key in frame_checks.items():
                if expectation_key not in expectations:
                    continue
                actual = color_frame.get(frame_key)
                if actual is None:
                    failures.append(
                        f"GLx color sweep row {row_id} is missing colorFrame.{frame_key}."
                    )
                elif not color_frame_metric_matches(actual, expectation_key, expectations[expectation_key]):
                    failures.append(
                        f"GLx color sweep row {row_id} colorFrame.{frame_key} "
                        f"is {actual!r}; expected {expectations[expectation_key]!r}."
                    )

    return failures


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

    require_color_sweep = bool(
        requirements.get("require_glx_color_sweep") or manifest.get("colorSweepEnabled")
    )
    failures.extend(evaluate_proof_corpus(manifest, requirements))  # type: ignore[arg-type]
    failures.extend(evaluate_renderer_switch_lifecycle(manifest, requirements))  # type: ignore[arg-type]
    failures.extend(evaluate_world_proof(manifest, requirements))  # type: ignore[arg-type]
    failures.extend(evaluate_material_proof(manifest, requirements))  # type: ignore[arg-type]
    failures.extend(evaluate_dynamic_proof(manifest, requirements))  # type: ignore[arg-type]
    failures.extend(evaluate_post_proof(manifest, requirements))  # type: ignore[arg-type]
    if requirements.get("require_glx_diagnostics") or require_color_sweep:
        failures.extend(validate_color_contract_manifest(manifest))
    if require_color_sweep:
        failures.extend(validate_image_evidence_manifest(manifest))
        failures.extend(evaluate_color_sweep(manifest))

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
        else:
            required_sections = ("colorPipeline", "colorAudit", "outputBackend", "textureAudit", "targetFormat", "colorFrame")
            for section in required_sections:
                if not any(
                    isinstance(result.get("metrics"), dict)
                    and isinstance(result["metrics"].get(section), dict)  # type: ignore[index]
                    for result in diagnostics
                ):
                    failures.append(f"Missing GLx color metadata section: {section}.")

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
        else:
            saw_locked_schedule = False
            schedule_failures: list[str] = []
            for sample in performance_samples:
                if int(sample.get("sampleCount", 0)) <= 0:
                    continue
                latest = sample.get("latest", {})
                if not isinstance(latest, dict):
                    continue
                failure = pass_schedule_failure_from_values(
                    latest.get("passScheduleValid"),
                    latest.get("passScheduleCount"),
                    latest.get("passScheduleHash"),
                    latest.get("passScheduleOrder"),
                )
                if failure is None:
                    saw_locked_schedule = True
                else:
                    schedule_failures.append(failure)
            if not saw_locked_schedule:
                failures.append("No valid GLx pass schedule was found in r_speeds 7 capture logs.")
                failures.extend(schedule_failures)
            tier_failures = [
                failure
                for sample in performance_samples
                if int(sample.get("sampleCount", 0)) > 0
                for latest in [sample.get("latest", {})]
                if isinstance(latest, dict)
                for failure in [product_tier_failure(latest.get("productTier", latest.get("tier")))]
                if failure
            ]
            failures.extend(tier_failures)
            color_metadata_keys = (
                "colorSpace",
                "outputTransfer",
                "toneMap",
                "toneMapExposure",
                "paperWhiteNits",
                "maxOutputNits",
                "colorSrgbDecode",
                "colorFramebufferSrgb",
                "colorOutputContract",
                "captureColorSpace",
                "capturePolicyRequest",
                "captureHdrAware",
                "capturePolicySupported",
                "outputBackendSelected",
                "textureAuditSrgb",
                "textureAuditSrgbDecode",
                "textureAuditMissingSrgbDecode",
                "textureAuditUnexpectedDecode",
                "targetInternalFormat",
                "targetTextureFormat",
                "targetTextureType",
                "colorFrameSamples",
                "colorFrameBackend",
                "colorFrameSpace",
                "colorFrameTransfer",
                "colorFrameExposure",
                "colorFramePaperWhiteNits",
                "colorFrameMaxOutputNits",
                "colorFrameSrgbDecode",
                "colorFrameFramebufferSrgb",
                "colorFrameInternalFormat",
                "colorFrameTextureFormat",
                "colorFrameTextureType",
                "colorFrameSceneTargetFloat",
                "colorFrameShaderSrgbEncode",
                "colorFrameContractValid",
            )
            if not any(
                int(sample.get("sampleCount", 0)) > 0
                and isinstance(sample.get("latest"), dict)
                and all(key in sample["latest"] for key in color_metadata_keys)  # type: ignore[operator]
                for sample in performance_samples
            ):
                failures.append("No GLx performance sample included complete color-pipeline metadata.")

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

    if requirements.get("require_visual_baseline"):
        if not manifest.get("screenshotBaselineDir"):
            failures.append("Visual proof requires --screenshot-baseline-dir or --proof-dir.")
        if manifest.get("approveScreenshotBaselines"):
            failures.append("Visual proof must compare against reviewed screenshot baselines, not approve them.")

    if requirements.get("require_performance_baseline"):
        if not manifest.get("performanceBaselinePath"):
            failures.append("Performance proof requires --performance-baseline or --proof-dir.")
        if manifest.get("approvePerformanceBaseline"):
            failures.append("Performance proof must compare against a reviewed performance baseline, not approve it.")
        comparisons = [
            comparison
            for comparison in manifest.get("performanceComparisons", [])
            if isinstance(comparison, dict)
        ]
        if (
            manifest.get("performanceBaselinePath") and
            not manifest.get("approvePerformanceBaseline") and
            not comparisons
        ):
            failures.append("Performance proof did not produce baseline comparisons.")

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
        missing_histograms = [
            shot.get("name", "screenshot")
            for shot in screenshots
            if shot.get("found")
            and (
                not isinstance(shot.get("histogram"), dict)
                or shot["histogram"].get("status") != "passed"  # type: ignore[index]
            )
        ]
        if (requirements.get("require_screenshots") or manifest.get("screenshotBaselineDir")) and missing_histograms:
            failures.append(
                f"Screenshot color histogram metadata is missing or invalid: {len(missing_histograms)}/{len(screenshots)} "
                f"({', '.join(str(name) for name in missing_histograms[:6])}"
                f"{'...' if len(missing_histograms) > 6 else ''})"
            )
        invalid_capture_policy = [
            shot.get("name", "screenshot")
            for shot in screenshots
            if shot.get("found")
            and (
                not isinstance(shot.get("capturePolicy"), dict)
                or shot["capturePolicy"].get("defaultColorSpace") != "sdr-srgb"  # type: ignore[index]
                or shot["capturePolicy"].get("hdrExportStatus") != "explicit-reserved"  # type: ignore[index]
            )
        ]
        if (requirements.get("require_screenshots") or manifest.get("screenshotBaselineDir")) and invalid_capture_policy:
            failures.append(
                f"Screenshot capture policy metadata is missing or not SDR-default: {len(invalid_capture_policy)}/{len(screenshots)} "
                f"({', '.join(str(name) for name in invalid_capture_policy[:6])}"
                f"{'...' if len(invalid_capture_policy) > 6 else ''})"
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

            if requirements.get("require_visual_baseline"):
                unproved = [
                    shot.get("baselineKey", shot.get("name", "screenshot"))
                    for shot in screenshots
                    if shot.get("found") and shot.get("baselineStatus") != "passed"
                ]
                if unproved:
                    failures.append(
                        f"Visual proof did not compare cleanly: {len(unproved)}/{len(screenshots)} "
                        f"({', '.join(str(name) for name in unproved[:6])}"
                        f"{'...' if len(unproved) > 6 else ''})"
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


def infer_proof_platform_from_path(manifest_path: Path) -> str:
    for part in reversed(manifest_path.resolve().parts):
        candidate = part.strip().lower()
        if not candidate:
            continue
        try:
            candidate = normalize_proof_platform(candidate)
        except ValueError:
            continue
        if candidate in GLX_BLOCKING_RELEASE_PLATFORMS:
            return candidate
    return ""


def proof_platform_for_manifest(
    manifest: dict[str, object],
    manifest_path: Path,
) -> str:
    platform_value = str(manifest.get("proofPlatform", "")).strip()
    if platform_value:
        return normalize_proof_platform(platform_value)
    return infer_proof_platform_from_path(manifest_path)


def release_proof_manifest_failures(
    manifest: dict[str, object],
    manifest_path: Path,
) -> list[str]:
    gate = str(manifest.get("gate", ""))
    failures: list[str] = []

    if manifest.get("dryRun"):
        failures.append(f"{manifest_path}: dry-run manifests do not count as release proof.")
    if gate not in GLX_RELEASE_REQUIRED_GATES:
        failures.append(f"{manifest_path}: unsupported release proof gate '{gate or '-'}'.")

    gate_failures = evaluate_gate(manifest)
    if gate_failures:
        failures.extend(f"{manifest_path}: {failure}" for failure in gate_failures)

    status = run_status(manifest)
    if status != "passed":
        failures.append(f"{manifest_path}: gate status is {status}, expected passed.")

    if gate == "rc-proof":
        proof = proof_status(manifest)
        visual = proof.get("visual", {}) if isinstance(proof.get("visual"), dict) else {}
        performance_result = (
            proof.get("performance", {})
            if isinstance(proof.get("performance"), dict)
            else {}
        )
        if proof.get("status") != "passed":
            failures.append(
                f"{manifest_path}: rc-proof status is {proof.get('status')}, expected passed."
            )
        if visual.get("status") != "passed":
            failures.append(
                f"{manifest_path}: rc-proof visual status is {visual.get('status')}, expected passed."
            )
        if performance_result.get("status") != "passed":
            failures.append(
                f"{manifest_path}: rc-proof performance status is "
                f"{performance_result.get('status')}, expected passed."
            )

    return list(dict.fromkeys(failures))


def release_proof_manifest_record(
    manifest: dict[str, object],
    manifest_path: Path,
    proof_root: Path,
) -> dict[str, object]:
    proof = proof_status(manifest)
    relative_path = (
        manifest_path.resolve().relative_to(proof_root.resolve()).as_posix()
        if manifest_path.resolve().is_relative_to(proof_root.resolve())
        else str(manifest_path.resolve())
    )
    return {
        "platform": proof_platform_for_manifest(manifest, manifest_path),
        "gate": str(manifest.get("gate", "")),
        "path": relative_path,
        "runId": str(manifest.get("runId", "")),
        "createdUtc": str(manifest.get("createdUtc", "")),
        "status": run_status(manifest),
        "proofStatus": proof.get("status", "not-configured")
        if isinstance(proof, dict)
        else "not-configured",
        "proofCorpusVersion": (
            manifest.get("proofCorpus", {}).get("version", "")
            if isinstance(manifest.get("proofCorpus"), dict)
            else ""
        ),
        "paritySuiteVersion": (
            manifest.get("proofCorpus", {}).get("paritySuiteVersion", "")
            if isinstance(manifest.get("proofCorpus"), dict)
            else ""
        ),
    }


def markdown_escape_cell(value: object) -> str:
    text = str(value if value is not None else "-")
    return text.replace("|", "\\|").replace("\n", " ").strip() or "-"


def markdown_artifact_link(value: object, base_path: Path) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    path = Path(text)
    label = path.name or text
    try:
        if path.is_absolute():
            target = os.path.relpath(path, base_path.parent).replace("\\", "/")
        else:
            target = text.replace("\\", "/")
    except ValueError:
        target = text.replace("\\", "/")
    return f"[`{markdown_escape_cell(label)}`]({target})"


def iter_manifest_runs(manifest: dict[str, object]) -> list[dict[str, object]]:
    return [
        run
        for run in manifest.get("runs", [])
        if isinstance(run, dict)
    ]


def iter_manifest_screenshots(manifest: dict[str, object]) -> list[dict[str, object]]:
    return [
        shot
        for run in iter_manifest_runs(manifest)
        for shot in run.get("screenshots", [])
        if isinstance(shot, dict)
    ]


def collect_visual_backend_rows(manifest: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for run in iter_manifest_runs(manifest):
        diagnostics = run.get("diagnostics")
        if not isinstance(diagnostics, dict):
            continue
        metrics = diagnostics.get("metrics")
        if not isinstance(metrics, dict):
            continue
        pipeline = metrics.get("colorPipeline", {}) if isinstance(metrics.get("colorPipeline"), dict) else {}
        audit = metrics.get("colorAudit", {}) if isinstance(metrics.get("colorAudit"), dict) else {}
        backend = metrics.get("outputBackend", {}) if isinstance(metrics.get("outputBackend"), dict) else {}
        target = metrics.get("targetFormat", {}) if isinstance(metrics.get("targetFormat"), dict) else {}
        color_frame = metrics.get("colorFrame", {}) if isinstance(metrics.get("colorFrame"), dict) else {}
        latest_frame = color_frame.get("latest", {}) if isinstance(color_frame.get("latest"), dict) else {}
        if not any((pipeline, audit, backend, target, latest_frame)):
            continue
        internal_format = target.get("internalFormat", latest_frame.get("internalFormat", "-"))
        if isinstance(internal_format, int):
            internal_format = f"0x{internal_format:04x}"
        rows.append(
            {
                "run": run.get("type", "-"),
                "renderer": run.get("renderer", "-"),
                "space": pipeline.get("space", latest_frame.get("space", "-")),
                "transfer": pipeline.get("transfer", latest_frame.get("transfer", "-")),
                "backendRequest": backend.get("request", "-"),
                "backendSelected": backend.get("selected", latest_frame.get("backend", "-")),
                "hardware": backend.get("hardware", "-"),
                "headroom": backend.get("headroom", "-"),
                "exposure": pipeline.get("exposure", latest_frame.get("exposure", "-")),
                "framebufferSrgb": audit.get("framebufferSrgb", latest_frame.get("framebufferSrgb", "-")),
                "srgbDecode": audit.get("srgbDecode", latest_frame.get("srgbDecode", "-")),
                "targetFloat": audit.get("targetFloat", latest_frame.get("sceneTargetFloat", "-")),
                "internalFormat": internal_format,
                "finalEncode": audit.get("finalEncode", "-"),
                "contract": audit.get("contract", latest_frame.get("contractValid", "-")),
            }
        )
    return rows


def collect_visual_tier_rows(manifest: dict[str, object]) -> list[dict[str, object]]:
    records: dict[str, dict[str, object]] = {
        tier: {
            "tier": tier,
            "observed": "no",
            "executor": "-",
            "modernPost": "-",
            "sceneLinear": "-",
            "postOutputMode": "-",
            "postNodes": "-",
            "outputs": "-",
            "executableNodes": "-",
            "executableOutputs": "-",
            "fallbackMask": "-",
            "outputTransfer": "-",
            "gpuFrameMs": "-",
        }
        for tier in GLX_PRODUCT_TIER_ORDER
    }

    def record_tier(tier_value: object) -> dict[str, object] | None:
        tier = str(tier_value or "").strip().upper()
        if tier not in records:
            return None
        records[tier]["observed"] = "yes"
        return records[tier]

    for run in iter_manifest_runs(manifest):
        diagnostics = run.get("diagnostics")
        if isinstance(diagnostics, dict) and isinstance(diagnostics.get("metrics"), dict):
            metrics = diagnostics["metrics"]
            product_tier = metrics.get("productTier", {})
            tier_value = product_tier.get("tier") if isinstance(product_tier, dict) else product_tier
            record = record_tier(tier_value)
            if record is not None:
                post = metrics.get("postOutputOwnership", {})
                if isinstance(post, dict):
                    record["postOutputMode"] = post.get("mode", record["postOutputMode"])
                    record["postNodes"] = post.get("postNodes", record["postNodes"])
                    record["outputs"] = post.get("outputs", record["outputs"])
                    record["executableNodes"] = post.get("executableNodes", record["executableNodes"])
                    record["executableOutputs"] = post.get("executableOutputs", record["executableOutputs"])
                    record["fallbackMask"] = post.get("fallbackMask", record["fallbackMask"])
                for prefix, label in (
                    ("gl3x", "GL3X"),
                    ("gl41", "GL41"),
                    ("gl46", "GL46"),
                ):
                    if record["tier"] != label:
                        continue
                    executor = metrics.get(f"{prefix}Executor", {})
                    support = metrics.get(f"{prefix}Support", {})
                    if isinstance(executor, dict):
                        record["executor"] = executor.get("active", record["executor"])
                    if isinstance(support, dict):
                        record["modernPost"] = support.get("modernPostChain", record["modernPost"])
                        record["sceneLinear"] = support.get("sceneLinearOutput", record["sceneLinear"])

        performance = run.get("performance")
        if isinstance(performance, dict):
            latest = performance.get("latest", {})
            if isinstance(latest, dict):
                record = record_tier(latest.get("productTier", latest.get("tier")))
                if record is not None:
                    record["postOutputMode"] = latest.get("postOutputMode", record["postOutputMode"])
                    record["postNodes"] = latest.get("postOutputPostNodes", record["postNodes"])
                    record["outputs"] = latest.get("postOutputOutputs", record["outputs"])
                    record["executableNodes"] = latest.get("postOutputExecutableNodes", record["executableNodes"])
                    record["executableOutputs"] = latest.get("postOutputExecutableOutputs", record["executableOutputs"])
                    record["fallbackMask"] = latest.get("postOutputFallbackMask", record["fallbackMask"])
                    record["outputTransfer"] = latest.get("outputTransfer", record["outputTransfer"])
                    record["gpuFrameMs"] = latest.get("gpuFrameMs", latest.get("gpu", record["gpuFrameMs"]))

    return [records[tier] for tier in GLX_PRODUCT_TIER_ORDER]


def glx_visual_dossier(manifest: dict[str, object], manifest_path: Path) -> str:
    runs = iter_manifest_runs(manifest)
    screenshots = iter_manifest_screenshots(manifest)
    backend_rows = collect_visual_backend_rows(manifest)
    tier_rows = collect_visual_tier_rows(manifest)
    status = run_status(manifest)

    lines = [
        f"# GLx Visual Dossier {manifest.get('runId', '')}",
        "",
        f"- Version: `{GLX_VISUAL_DOSSIER_VERSION}`",
        f"- Status: `{status}`",
        f"- Gate: `{manifest.get('gate') or 'custom'}`",
        f"- Profile: `{manifest.get('profile') or '-'}`",
        f"- Proof platform: `{manifest.get('proofPlatform', '-')}`",
        f"- Manifest: {markdown_artifact_link(manifest_path, manifest_path)}",
        "",
        "## Current Pipeline Flow",
        "",
        "```mermaid",
        "flowchart LR",
        "    A[Authored textures and lightmaps] --> B[Compatibility scene preparation]",
        "    B --> C[GLx stream/material/static products]",
        "    C --> D[Shared OpenGL/FBO postprocess substrate]",
        "    D --> E[GLx OutputTransform diagnostics]",
        "    E --> F[SDR or hardware HDR presentation]",
        "```",
        "",
        "## Target Pipeline Flow",
        "",
        "```mermaid",
        "flowchart LR",
        "    A[Authored-color textures decode to linear once] --> B[Linear lighting and blending]",
        "    B --> C[Float scene target]",
        "    C --> D[Optional bloom chain in linear]",
        "    C --> E[Optional grading in linear]",
        "    D --> F[Single final composite]",
        "    E --> F",
        "    F --> G[Single output transform]",
        "    G --> H[SDR sRGB or hardware HDR present]",
        "```",
        "",
    ]

    switch_evidence = manifest.get("rendererSwitchEvidence")
    if isinstance(switch_evidence, dict):
        lines.extend(
            [
                "## Renderer Switch Lifecycle",
                "",
                "| Status | Command | Restart Mode | Vid Restart Path | Planned | Completed | Into GLx | Out Of GLx | Diagnostics | Perf Samples |",
                "|---:|---|---|---|---:|---:|---:|---:|---:|---:|",
                "| "
                f"{markdown_escape_cell(switch_evidence.get('status', '-'))} | "
                f"{markdown_escape_cell(switch_evidence.get('command', '-'))} | "
                f"{markdown_escape_cell(switch_evidence.get('restartMode', '-'))} | "
                f"{markdown_escape_cell(switch_evidence.get('vidRestartPath', '-'))} | "
                f"{markdown_escape_cell(switch_evidence.get('plannedTransitions', '-'))} | "
                f"{markdown_escape_cell(switch_evidence.get('completedTransitions', '-'))} | "
                f"{markdown_escape_cell(switch_evidence.get('transitionsIntoGlx', '-'))} | "
                f"{markdown_escape_cell(switch_evidence.get('transitionsOutOfGlx', '-'))} | "
                f"{markdown_escape_cell(switch_evidence.get('glxDiagnosticsFound', '-'))} | "
                f"{markdown_escape_cell(switch_evidence.get('glxPerformanceSamples', '-'))} |",
                "",
            ]
        )

    world_evidence = manifest.get("worldProofEvidence")
    if isinstance(world_evidence, dict) and world_evidence.get("requiresWorldProof"):
        static_world = (
            world_evidence.get("staticWorld", {})
            if isinstance(world_evidence.get("staticWorld"), dict)
            else {}
        )
        lightmaps = (
            world_evidence.get("lightmaps", {})
            if isinstance(world_evidence.get("lightmaps"), dict)
            else {}
        )
        fog = (
            world_evidence.get("fog", {})
            if isinstance(world_evidence.get("fog"), dict)
            else {}
        )
        lines.extend(
            [
                "## World Proof",
                "",
                "| Status | Required Maps | Screenshot Maps | Static Attempts | Static Indexes | Static Fallbacks | Lightmaps | Fog |",
                "|---:|---|---|---:|---:|---:|---:|---:|",
                "| "
                f"{markdown_escape_cell(world_evidence.get('status', '-'))} | "
                f"{markdown_escape_cell(', '.join(str(item) for item in world_evidence.get('requiredMaps', [])) or '-')} | "
                f"{markdown_escape_cell(', '.join(str(item) for item in world_evidence.get('glxScreenshotMaps', [])) or '-')} | "
                f"{markdown_escape_cell(static_world.get('drawAttempts', '-'))} | "
                f"{markdown_escape_cell(static_world.get('drawIndexes', '-'))} | "
                f"{markdown_escape_cell(static_world.get('drawFallbacks', '-'))} | "
                f"{markdown_escape_cell(lightmaps.get('ok', '-'))} | "
                f"{markdown_escape_cell(fog.get('ok', '-'))} |",
                "",
            ]
        )

    material_evidence = manifest.get("materialProofEvidence")
    if isinstance(material_evidence, dict) and material_evidence.get("requiresMaterialProof"):
        renderer = (
            material_evidence.get("renderer", {})
            if isinstance(material_evidence.get("renderer"), dict)
            else {}
        )
        parameters = (
            material_evidence.get("parameters", {})
            if isinstance(material_evidence.get("parameters"), dict)
            else {}
        )
        stream_features = (
            material_evidence.get("streamFeatures", {})
            if isinstance(material_evidence.get("streamFeatures"), dict)
            else {}
        )
        stage_flags = (
            material_evidence.get("stageFlags", {})
            if isinstance(material_evidence.get("stageFlags"), dict)
            else {}
        )
        stage_flag_counts = (
            stage_flags.get("counts", {})
            if isinstance(stage_flags.get("counts"), dict)
            else {}
        )
        lines.extend(
            [
                "## Material Proof",
                "",
                "| Status | Required Maps | Programs | Parameter Blocks | Parameter Hash | Animated | Screen | Video | MT | DepthFrag | TexMod | Env | Failures |",
                "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
                "| "
                f"{markdown_escape_cell(material_evidence.get('status', '-'))} | "
                f"{markdown_escape_cell(', '.join(str(item) for item in material_evidence.get('requiredMaps', [])) or '-')} | "
                f"{markdown_escape_cell(renderer.get('programs', '-'))} | "
                f"{markdown_escape_cell(parameters.get('blocks', '-'))} | "
                f"{markdown_escape_cell(parameters.get('hash', '-'))} | "
                f"{markdown_escape_cell(stage_flag_counts.get('animatedImage', '-'))} | "
                f"{markdown_escape_cell(stage_flag_counts.get('screenMap', '-'))} | "
                f"{markdown_escape_cell(stage_flag_counts.get('videoMap', '-'))} | "
                f"{markdown_escape_cell(stream_features.get('multitexture', '-'))} | "
                f"{markdown_escape_cell(stream_features.get('depthFragment', '-'))} | "
                f"{markdown_escape_cell(stream_features.get('texMod', '-'))} | "
                f"{markdown_escape_cell(stream_features.get('environment', '-'))} | "
                f"{markdown_escape_cell(len(material_evidence.get('failures', [])) if isinstance(material_evidence.get('failures'), list) else '-')} |",
                "",
            ]
        )

    dynamic_evidence = manifest.get("dynamicProofEvidence")
    if isinstance(dynamic_evidence, dict) and dynamic_evidence.get("requiresDynamicProof"):
        stream_draw = (
            dynamic_evidence.get("streamDraw", {})
            if isinstance(dynamic_evidence.get("streamDraw"), dict)
            else {}
        )
        stream_features = (
            dynamic_evidence.get("streamFeatures", {})
            if isinstance(dynamic_evidence.get("streamFeatures"), dict)
            else {}
        )
        stream_categories = (
            dynamic_evidence.get("streamCategories", {})
            if isinstance(dynamic_evidence.get("streamCategories"), dict)
            else {}
        )

        def dynamic_category_draws(name: str) -> object:
            category = stream_categories.get(name)
            if isinstance(category, dict):
                return category.get("draws", "-")
            return "-"

        lines.extend(
            [
                "## Dynamic Proof",
                "",
                "| Status | Required Maps | Required Demos | Entity | Particle | Poly | Mark | Weapon | Beam Cat | Shadows | Beams | DLight | Fallbacks |",
                "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
                "| "
                f"{markdown_escape_cell(dynamic_evidence.get('status', '-'))} | "
                f"{markdown_escape_cell(', '.join(str(item) for item in dynamic_evidence.get('requiredMaps', [])) or '-')} | "
                f"{markdown_escape_cell(', '.join(str(item) for item in dynamic_evidence.get('requiredDemos', [])) or '-')} | "
                f"{markdown_escape_cell(dynamic_category_draws('entity'))} | "
                f"{markdown_escape_cell(dynamic_category_draws('particle'))} | "
                f"{markdown_escape_cell(dynamic_category_draws('poly'))} | "
                f"{markdown_escape_cell(dynamic_category_draws('mark'))} | "
                f"{markdown_escape_cell(dynamic_category_draws('weapon'))} | "
                f"{markdown_escape_cell(dynamic_category_draws('beam'))} | "
                f"{markdown_escape_cell(stream_features.get('shadow', '-'))} | "
                f"{markdown_escape_cell(stream_features.get('beam', '-'))} | "
                f"{markdown_escape_cell(stream_features.get('dynamicLight', '-'))} | "
                f"{markdown_escape_cell(stream_draw.get('fallbacks', '-'))} |",
                "",
            ]
        )

    post_evidence = manifest.get("postProofEvidence")
    if isinstance(post_evidence, dict) and post_evidence.get("requiresPostProof"):
        fbo = (
            post_evidence.get("fbo", {})
            if isinstance(post_evidence.get("fbo"), dict)
            else {}
        )
        frames = (
            post_evidence.get("frames", {})
            if isinstance(post_evidence.get("frames"), dict)
            else {}
        )
        controls = (
            post_evidence.get("controls", {})
            if isinstance(post_evidence.get("controls"), dict)
            else {}
        )
        feature_evidence = (
            post_evidence.get("featureEvidence", {})
            if isinstance(post_evidence.get("featureEvidence"), dict)
            else {}
        )
        greyscale = (
            feature_evidence.get("greyscale", {})
            if isinstance(feature_evidence.get("greyscale"), dict)
            else {}
        )
        render_scale = (
            feature_evidence.get("renderScale", {})
            if isinstance(feature_evidence.get("renderScale"), dict)
            else {}
        )
        lines.extend(
            [
                "## Post Proof",
                "",
                "| Status | Required Maps | FBO Ready | Post Frames | Screenshots | Greyscale | Render Scale | Dimension Evidence | Color Contract | Failures |",
                "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
                "| "
                f"{markdown_escape_cell(post_evidence.get('status', '-'))} | "
                f"{markdown_escape_cell(', '.join(str(item) for item in post_evidence.get('requiredMaps', [])) or '-')} | "
                f"{markdown_escape_cell(fbo.get('ready', '-'))} | "
                f"{markdown_escape_cell(frames.get('post', '-'))} | "
                f"{markdown_escape_cell(frames.get('screenshots', '-'))} | "
                f"{markdown_escape_cell(greyscale.get('ok', '-'))} | "
                f"{markdown_escape_cell(render_scale.get('ok', '-'))} | "
                f"{markdown_escape_cell(render_scale.get('dimensionEvidence', '-'))} | "
                f"{markdown_escape_cell(post_evidence.get('colorContract', '-'))} | "
                f"{markdown_escape_cell(len(post_evidence.get('failures', [])) if isinstance(post_evidence.get('failures'), list) else '-')} |",
                "",
                "| Render Scale Control | Greyscale Control | Window Adjusted | Minimized Output |",
                "|---:|---:|---:|---:|",
                "| "
                f"{markdown_escape_cell(controls.get('renderScale', '-'))} | "
                f"{markdown_escape_cell(controls.get('greyscale', '-'))} | "
                f"{markdown_escape_cell(controls.get('windowAdjusted', '-'))} | "
                f"{markdown_escape_cell(frames.get('minimizedOutput', '-'))} |",
                "",
            ]
        )

    ownership_evidence = manifest.get("ownershipProofEvidence")
    if isinstance(ownership_evidence, dict) and ownership_evidence.get("requiresOwnership"):
        delegation = (
            ownership_evidence.get("delegation", {})
            if isinstance(ownership_evidence.get("delegation"), dict)
            else {}
        )
        post_output = (
            ownership_evidence.get("postOutputOwnership", {})
            if isinstance(ownership_evidence.get("postOutputOwnership"), dict)
            else {}
        )
        lines.extend(
            [
                "## Ownership Proof",
                "",
                "| Status | Profile | Calls | Items | Product Tiers | Modern Tier | Post/Output | Post Nodes | Outputs | Fallback |",
                "|---:|---|---:|---:|---|---:|---:|---:|---:|---:|",
                "| "
                f"{markdown_escape_cell(ownership_evidence.get('status', '-'))} | "
                f"{markdown_escape_cell(ownership_evidence.get('profile', '-'))} | "
                f"{markdown_escape_cell(delegation.get('calls', '-'))} | "
                f"{markdown_escape_cell(delegation.get('items', '-'))} | "
                f"{markdown_escape_cell(', '.join(str(tier) for tier in ownership_evidence.get('productTiers', [])) or '-')} | "
                f"{markdown_escape_cell(ownership_evidence.get('modernTierDiagnosticsOk', '-'))} | "
                f"{markdown_escape_cell(ownership_evidence.get('modernPostOutput', '-'))} | "
                f"{markdown_escape_cell(post_output.get('postNodes', '-'))} | "
                f"{markdown_escape_cell(post_output.get('outputs', '-'))} | "
                f"{markdown_escape_cell(post_output.get('fallbackMask', '-'))} |",
                "",
            ]
        )

    if backend_rows:
        lines.extend(
            [
                "## Backend State Overlay",
                "",
                "| Run | Renderer | Space | Transfer | Request | Selected | HDR | Headroom | Exposure | sRGB Decode | FB sRGB | Float Target | Format | Encode | Contract |",
                "|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|",
            ]
        )
        for row in backend_rows:
            lines.append(
                "| "
                f"{markdown_escape_cell(row['run'])} | "
                f"{markdown_escape_cell(row['renderer'])} | "
                f"{markdown_escape_cell(row['space'])} | "
                f"{markdown_escape_cell(row['transfer'])} | "
                f"{markdown_escape_cell(row['backendRequest'])} | "
                f"{markdown_escape_cell(row['backendSelected'])} | "
                f"{markdown_escape_cell(row['hardware'])} | "
                f"{markdown_escape_cell(row['headroom'])} | "
                f"{markdown_escape_cell(row['exposure'])} | "
                f"{markdown_escape_cell(row['srgbDecode'])} | "
                f"{markdown_escape_cell(row['framebufferSrgb'])} | "
                f"{markdown_escape_cell(row['targetFloat'])} | "
                f"{markdown_escape_cell(row['internalFormat'])} | "
                f"{markdown_escape_cell(row['finalEncode'])} | "
                f"{markdown_escape_cell(row['contract'])} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Driver Tier Matrix",
            "",
            "| Tier | Observed | Executor | Modern Post | Scene Linear | Post/Output | Nodes | Outputs | Executable Nodes | Executable Outputs | Fallback Mask | Transfer | GPU ms |",
            "|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---|---:|",
        ]
    )
    for row in tier_rows:
        lines.append(
            "| "
            f"{markdown_escape_cell(row['tier'])} | "
            f"{markdown_escape_cell(row['observed'])} | "
            f"{markdown_escape_cell(row['executor'])} | "
            f"{markdown_escape_cell(row['modernPost'])} | "
            f"{markdown_escape_cell(row['sceneLinear'])} | "
            f"{markdown_escape_cell(row['postOutputMode'])} | "
            f"{markdown_escape_cell(row['postNodes'])} | "
            f"{markdown_escape_cell(row['outputs'])} | "
            f"{markdown_escape_cell(row['executableNodes'])} | "
            f"{markdown_escape_cell(row['executableOutputs'])} | "
            f"{markdown_escape_cell(row['fallbackMask'])} | "
            f"{markdown_escape_cell(row['outputTransfer'])} | "
            f"{markdown_escape_cell(row['gpuFrameMs'])} |"
        )
    lines.append("")

    if screenshots:
        lines.extend(
            [
                "## Histogram And False-Color Evidence",
                "",
                "| Screenshot | Found | Mean Luma | P01 | P50 | P99 | Black Clip | White Clip | Histogram | Luma Map | Exposure Map |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|",
            ]
        )
        for shot in screenshots:
            histogram = shot.get("histogram", {}) if isinstance(shot.get("histogram"), dict) else {}
            black = histogram.get("clippedBlackRatio", "-")
            white = histogram.get("clippedWhiteRatio", "-")
            if isinstance(black, (int, float)):
                black = f"{float(black):.3%}"
            if isinstance(white, (int, float)):
                white = f"{float(white):.3%}"
            lines.append(
                "| "
                f"{markdown_escape_cell(shot.get('name', '-'))} | "
                f"{markdown_escape_cell(shot.get('found', '-'))} | "
                f"{markdown_escape_cell(histogram.get('meanLuma', '-'))} | "
                f"{markdown_escape_cell(histogram.get('p01Luma', '-'))} | "
                f"{markdown_escape_cell(histogram.get('p50Luma', '-'))} | "
                f"{markdown_escape_cell(histogram.get('p99Luma', '-'))} | "
                f"{markdown_escape_cell(black)} | "
                f"{markdown_escape_cell(white)} | "
                f"{markdown_artifact_link(shot.get('histogramPath'), manifest_path)} | "
                f"{markdown_artifact_link(shot.get('falseColorPath'), manifest_path)} | "
                f"{markdown_artifact_link(shot.get('exposureFalseColorPath'), manifest_path)} |"
            )
        lines.append("")

        lines.extend(
            [
                "## Parity Diff Sheet",
                "",
                "| Screenshot | Baseline Status | Candidate | Baseline | Diff | RMS | PSNR | SSIM | Changed Pixels |",
                "|---|---:|---|---|---|---:|---:|---:|---:|",
            ]
        )
        for shot in screenshots:
            comparison = shot.get("comparison", {}) if isinstance(shot.get("comparison"), dict) else {}
            changed = comparison.get("changedPixelRatio", "-")
            if isinstance(changed, (int, float)):
                changed = f"{float(changed):.3%}"
            rms = comparison.get("rms", "-")
            if isinstance(rms, (int, float)):
                rms = f"{float(rms):.3f}"
            psnr = comparison.get("psnr", "-")
            if isinstance(psnr, (int, float)):
                psnr = f"{float(psnr):.3f}"
            ssim = comparison.get("ssim", "-")
            if isinstance(ssim, (int, float)):
                ssim = f"{float(ssim):.6f}"
            lines.append(
                "| "
                f"{markdown_escape_cell(shot.get('baselineKey', shot.get('name', '-')))} | "
                f"{markdown_escape_cell(shot.get('baselineStatus', '-'))} | "
                f"{markdown_artifact_link(shot.get('path'), manifest_path)} | "
                f"{markdown_artifact_link(shot.get('baselinePath'), manifest_path)} | "
                f"{markdown_artifact_link(comparison.get('diffPath'), manifest_path)} | "
                f"{markdown_escape_cell(rms)} | "
                f"{markdown_escape_cell(psnr)} | "
                f"{markdown_escape_cell(ssim)} | "
                f"{markdown_escape_cell(changed)} |"
            )
        lines.append("")

    color_runs = [run for run in runs if run.get("type") == "color-sweep"]
    if color_runs:
        lines.extend(
            [
                "## SDR/HDR Color Sweep Review",
                "",
                "| Row | Probe | Status | Expected Transfer | Expected Exposure | Screenshot Count |",
                "|---|---|---:|---|---:|---:|",
            ]
        )
        for run in color_runs:
            row = run.get("colorSweepRow", {}) if isinstance(run.get("colorSweepRow"), dict) else {}
            expect = row.get("expect", {}) if isinstance(row.get("expect"), dict) else {}
            run_shots = [
                shot for shot in run.get("screenshots", [])
                if isinstance(shot, dict)
            ]
            lines.append(
                "| "
                f"{markdown_escape_cell(row.get('id', '-'))} | "
                f"{markdown_escape_cell(row.get('probe', '-'))} | "
                f"{markdown_escape_cell(run.get('status', '-'))} | "
                f"{markdown_escape_cell(expect.get('transfer', '-'))} | "
                f"{markdown_escape_cell(expect.get('exposure', '-'))} | "
                f"{len(run_shots)} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Review Checklist",
            "",
            "- Confirm the backend state overlay matches the expected SDR/HDR request for the run.",
            "- Compare histogram mid-gray and clipping values before trusting visual parity by eye.",
            "- Use the luma false-color sidecars to spot crushed shadows, clipped highlights, and flat tone mapping.",
            "- Use the exposure false-color sidecars to spot stop-scale drift across tone-map and HDR-output rows.",
            "- Inspect parity diffs for structured changes before accepting screenshot threshold passes.",
            "- Confirm modern tiers show executable GLx-owned post/output evidence before treating the run as promotion evidence.",
            "",
        ]
    )

    return "\n".join(lines).rstrip() + "\n"


def validate_release_proof_root(
    proof_root: Path,
    required_platforms: Iterable[str] = GLX_BLOCKING_RELEASE_PLATFORMS,
    required_gates: Iterable[str] = GLX_RELEASE_REQUIRED_GATES,
) -> dict[str, object]:
    root = proof_root.resolve()
    required_platform_list = [normalize_proof_platform(platform_id) for platform_id in required_platforms]
    required_gate_list = [str(gate) for gate in required_gates]
    summary: dict[str, object] = {
        "version": GLX_RELEASE_PROOF_VERSION,
        "status": "failed",
        "root": str(root),
        "requiredPlatforms": required_platform_list,
        "requiredGates": required_gate_list,
        "manifests": [],
        "failures": [],
    }
    failures: list[str] = []

    if not root.exists():
        summary["failures"] = [f"GLx proof root does not exist: {root}"]
        return summary
    if not root.is_dir():
        summary["failures"] = [f"GLx proof root is not a directory: {root}"]
        return summary

    candidates: dict[tuple[str, str], list[tuple[Path, dict[str, object], list[str]]]] = {}
    for manifest_path in sorted(root.rglob("manifest.json")):
        try:
            manifest = load_json_file(manifest_path)
        except Exception as exc:
            failures.append(f"{manifest_path}: could not read manifest: {exc}")
            continue
        if not isinstance(manifest, dict):
            failures.append(f"{manifest_path}: manifest root must be a JSON object.")
            continue
        gate = str(manifest.get("gate", ""))
        if gate not in required_gate_list:
            continue
        try:
            proof_platform = proof_platform_for_manifest(manifest, manifest_path)
        except ValueError as exc:
            failures.append(f"{manifest_path}: {exc}")
            continue
        if proof_platform not in required_platform_list:
            continue
        manifest_failures = release_proof_manifest_failures(manifest, manifest_path)
        candidates.setdefault((proof_platform, gate), []).append(
            (manifest_path, manifest, manifest_failures)
        )

    selected_records: list[dict[str, object]] = []
    for platform_id in required_platform_list:
        for gate in required_gate_list:
            gate_candidates = candidates.get((platform_id, gate), [])
            if not gate_candidates:
                failures.append(f"Missing GLx {gate} runtime proof for {platform_id}.")
                continue
            passing = [
                (manifest_path, manifest, manifest_failures)
                for manifest_path, manifest, manifest_failures in gate_candidates
                if not manifest_failures
            ]
            if not passing:
                failures.append(f"No passing GLx {gate} runtime proof for {platform_id}.")
                for manifest_path, _manifest, manifest_failures in gate_candidates[:2]:
                    failures.extend(
                        manifest_failures
                        or [f"{manifest_path}: manifest did not pass release proof validation."]
                    )
                continue
            chosen_path, chosen_manifest, _chosen_failures = sorted(
                passing,
                key=lambda item: (
                    str(item[1].get("createdUtc", "")),
                    str(item[1].get("runId", "")),
                    str(item[0]),
                ),
            )[-1]
            selected_records.append(release_proof_manifest_record(chosen_manifest, chosen_path, root))

    summary["manifests"] = selected_records
    summary["failures"] = list(dict.fromkeys(failures))
    summary["status"] = "passed" if not failures else "failed"
    return summary


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
    color_sweep_runs_for_summary = [
        run
        for run in runs
        if run.get("type") == "color-sweep"
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
        f"- Proof platform: `{manifest.get('proofPlatform', '-')}`",
        f"- Manifest: `{manifest_path}`",
        f"- Visual dossier: `{manifest.get('visualDossier', {}).get('path', '-') if isinstance(manifest.get('visualDossier'), dict) else '-'}`",
        f"- Renderers: `{', '.join(str(item) for item in manifest.get('renderers', []))}`",
        f"- Maps: `{', '.join(str(item) for item in manifest.get('maps', [])) or '-'}`",
        f"- Demos: `{', '.join(str(item) for item in manifest.get('demos', [])) or '-'}`",
        "",
    ]

    proof_corpus = manifest.get("proofCorpus")
    if isinstance(proof_corpus, dict):
        selected_scene_ids = [
            str(scene_id)
            for scene_id in proof_corpus.get("selectedSceneIds", [])
            if str(scene_id).strip()
        ]
        selected_tags = [
            str(tag)
            for tag in proof_corpus.get("selectedTags", [])
            if str(tag).strip()
        ]
        required_tags = [
            str(tag)
            for tag in proof_corpus.get("requiredTags", [])
            if str(tag).strip()
        ]
        parity_suite_ids = [
            str(suite_id)
            for suite_id in proof_corpus.get("paritySuiteIds", [])
            if str(suite_id).strip()
        ]
        lines.append("## GLx Proof Corpus")
        lines.append("")
        lines.append(f"- Version: `{proof_corpus.get('version', '-')}`")
        lines.append(f"- Document: `{proof_corpus.get('document', '-')}`")
        lines.append(f"- Scenes: `{', '.join(selected_scene_ids) or '-'}`")
        lines.append(f"- Tags: `{', '.join(selected_tags) or '-'}`")
        if required_tags:
            lines.append(f"- Required tags: `{', '.join(required_tags)}`")
        lines.append(f"- Parity suite version: `{proof_corpus.get('paritySuiteVersion', '-')}`")
        lines.append(f"- Parity suites: `{', '.join(parity_suite_ids) or '-'}`")
        lines.append("")

    switch_evidence = manifest.get("rendererSwitchEvidence")
    if isinstance(switch_evidence, dict):
        lines.append("## Renderer Switch Lifecycle")
        lines.append("")
        lines.append(f"- Version: `{switch_evidence.get('version', '-')}`")
        lines.append(f"- Status: `{switch_evidence.get('status', '-')}`")
        lines.append(f"- Command: `{switch_evidence.get('command', '-')}`")
        lines.append(f"- Restart mode: `{switch_evidence.get('restartMode', '-')}`")
        lines.append(f"- Vid restart path: `{switch_evidence.get('vidRestartPath', '-')}`")
        lines.append(
            "- Transitions: "
            f"`{switch_evidence.get('completedTransitions', 0)}/"
            f"{switch_evidence.get('plannedTransitions', 0)}`"
        )
        lines.append(
            "- GLx legs: "
            f"`into={switch_evidence.get('transitionsIntoGlx', 0)}, "
            f"out={switch_evidence.get('transitionsOutOfGlx', 0)}`"
        )
        lines.append(
            "- GLx diagnostics/performance: "
            f"`diagnostics={switch_evidence.get('glxDiagnosticsFound', False)}, "
            f"samples={switch_evidence.get('glxPerformanceSamples', 0)}`"
        )
        lines.append("")

    world_evidence = manifest.get("worldProofEvidence")
    if isinstance(world_evidence, dict) and world_evidence.get("requiresWorldProof"):
        static_world = (
            world_evidence.get("staticWorld", {})
            if isinstance(world_evidence.get("staticWorld"), dict)
            else {}
        )
        lightmaps = (
            world_evidence.get("lightmaps", {})
            if isinstance(world_evidence.get("lightmaps"), dict)
            else {}
        )
        fog = (
            world_evidence.get("fog", {})
            if isinstance(world_evidence.get("fog"), dict)
            else {}
        )
        lines.append("## World Proof")
        lines.append("")
        lines.append(f"- Version: `{world_evidence.get('version', '-')}`")
        lines.append(f"- Status: `{world_evidence.get('status', '-')}`")
        lines.append(
            "- Required maps: "
            f"`{', '.join(str(item) for item in world_evidence.get('requiredMaps', [])) or '-'}`"
        )
        lines.append(
            "- GLx screenshots: "
            f"`{', '.join(str(item) for item in world_evidence.get('glxScreenshotMaps', [])) or '-'}`"
        )
        lines.append(
            "- Static world: "
            f"`enabled={static_world.get('rendererEnabled', 0)}, "
            f"arena={static_world.get('arenaReady', 0)}, "
            f"attempts={static_world.get('drawAttempts', 0)}, "
            f"indexes={static_world.get('drawIndexes', 0)}, "
            f"fallbacks={static_world.get('drawFallbacks', 0)}`"
        )
        lines.append(
            "- Lightmaps/fog: "
            f"`lightmaps={lightmaps.get('ok', False)}, "
            f"fog={fog.get('ok', False)}, "
            f"fogDraws={fog.get('streamDraws', 0)}`"
        )
        failures = [
            str(failure)
            for failure in world_evidence.get("failures", [])
            if str(failure).strip()
        ]
        if failures:
            lines.append(f"- Failures: `{'; '.join(failures)}`")
        lines.append("")

    material_evidence = manifest.get("materialProofEvidence")
    if isinstance(material_evidence, dict) and material_evidence.get("requiresMaterialProof"):
        renderer = (
            material_evidence.get("renderer", {})
            if isinstance(material_evidence.get("renderer"), dict)
            else {}
        )
        parameters = (
            material_evidence.get("parameters", {})
            if isinstance(material_evidence.get("parameters"), dict)
            else {}
        )
        stream_features = (
            material_evidence.get("streamFeatures", {})
            if isinstance(material_evidence.get("streamFeatures"), dict)
            else {}
        )
        stage_flags = (
            material_evidence.get("stageFlags", {})
            if isinstance(material_evidence.get("stageFlags"), dict)
            else {}
        )
        stage_flag_counts = (
            stage_flags.get("counts", {})
            if isinstance(stage_flags.get("counts"), dict)
            else {}
        )
        lines.append("## Material Proof")
        lines.append("")
        lines.append(f"- Version: `{material_evidence.get('version', '-')}`")
        lines.append(f"- Status: `{material_evidence.get('status', '-')}`")
        lines.append(
            "- Required maps: "
            f"`{', '.join(str(item) for item in material_evidence.get('requiredMaps', [])) or '-'}`"
        )
        lines.append(
            "- Renderer: "
            f"`enabled={renderer.get('enabled', 0)}, "
            f"ready={renderer.get('ready', 0)}, "
            f"programs={renderer.get('programs', 0)}, "
            f"binds={renderer.get('binds', 0)}, "
            f"failures={renderer.get('compileFailures', 0)}/"
            f"{renderer.get('linkFailures', 0)}/"
            f"{renderer.get('precacheFailures', 0)}/"
            f"{renderer.get('bindFailures', 0)}`"
        )
        lines.append(
            "- Parameter block: "
            f"`blocks={parameters.get('blocks', 0)}, "
            f"invalid={parameters.get('invalid', 0)}, "
            f"hash={parameters.get('hash', 0)}, "
            f"flags={','.join(str(flag) for flag in parameters.get('flagNames', [])) or '-'}`"
        )
        lines.append(
            "- Stage flags: "
            f"`required={','.join(str(flag) for flag in material_evidence.get('requiredStageFlags', [])) or '-'}, "
            f"observed={','.join(str(flag) for flag in stage_flags.get('observedNames', [])) or '-'}, "
            f"animated={stage_flag_counts.get('animatedImage', 0)}, "
            f"screen={stage_flag_counts.get('screenMap', 0)}, "
            f"video={stage_flag_counts.get('videoMap', 0)}`"
        )
        lines.append(
            "- Stream material features: "
            f"`mt={stream_features.get('multitexture', 0)}, "
            f"depth={stream_features.get('depthFragment', 0)}, "
            f"texmod={stream_features.get('texMod', 0)}, "
            f"env={stream_features.get('environment', 0)}, "
            f"screen={stream_features.get('screenMap', 0)}, "
            f"video={stream_features.get('videoMap', 0)}, "
            f"fallbacks={material_evidence.get('streamFallbacks', 0)}`"
        )
        lines.append(
            "- Stream guards: "
            f"`required={','.join(str(item) for item in material_evidence.get('requiredStreamGuards', [])) or '-'}, "
            f"forbidden={','.join(str(item) for item in material_evidence.get('forbiddenStreamFeatures', [])) or '-'}`"
        )
        failures = [
            str(failure)
            for failure in material_evidence.get("failures", [])
            if str(failure).strip()
        ]
        if failures:
            lines.append(f"- Failures: `{'; '.join(failures)}`")
        lines.append("")

    dynamic_evidence = manifest.get("dynamicProofEvidence")
    if isinstance(dynamic_evidence, dict) and dynamic_evidence.get("requiresDynamicProof"):
        stream_draw = (
            dynamic_evidence.get("streamDraw", {})
            if isinstance(dynamic_evidence.get("streamDraw"), dict)
            else {}
        )
        stream_features = (
            dynamic_evidence.get("streamFeatures", {})
            if isinstance(dynamic_evidence.get("streamFeatures"), dict)
            else {}
        )
        stream_categories = (
            dynamic_evidence.get("streamCategories", {})
            if isinstance(dynamic_evidence.get("streamCategories"), dict)
            else {}
        )
        tier_support = (
            dynamic_evidence.get("tierSupport", {})
            if isinstance(dynamic_evidence.get("tierSupport"), dict)
            else {}
        )

        def summary_category_draws(name: str) -> object:
            category = stream_categories.get(name)
            if isinstance(category, dict):
                return category.get("draws", 0)
            return 0

        lines.append("## Dynamic Proof")
        lines.append("")
        lines.append(f"- Version: `{dynamic_evidence.get('version', '-')}`")
        lines.append(f"- Status: `{dynamic_evidence.get('status', '-')}`")
        lines.append(
            "- Required scenes: "
            f"`maps={','.join(str(item) for item in dynamic_evidence.get('requiredMaps', [])) or '-'}, "
            f"demos={','.join(str(item) for item in dynamic_evidence.get('requiredDemos', [])) or '-'}`"
        )
        lines.append(
            "- Stream categories: "
            f"`entity={summary_category_draws('entity')}, "
            f"particle={summary_category_draws('particle')}, "
            f"poly={summary_category_draws('poly')}, "
            f"mark={summary_category_draws('mark')}, "
            f"weapon={summary_category_draws('weapon')}, "
            f"beam={summary_category_draws('beam')}`"
        )
        lines.append(
            "- Stream features: "
            f"`shadow={stream_features.get('shadow', 0)}, "
            f"beam={stream_features.get('beam', 0)}, "
            f"dynamicLight={stream_features.get('dynamicLight', 0)}, "
            f"fallbacks={stream_draw.get('fallbacks', 0)}, "
            f"skips={stream_draw.get('skips', 0)}`"
        )
        lines.append(
            "- Tier support: "
            f"`dynamicEntities={','.join(str(item) for item in tier_support.get('dynamicEntities', [])) or '-'}, "
            f"sprites={','.join(str(item) for item in tier_support.get('sprites', [])) or '-'}, "
            f"beams={','.join(str(item) for item in tier_support.get('beams', [])) or '-'}, "
            f"dynamicLights={','.join(str(item) for item in tier_support.get('dynamicLights', [])) or '-'}, "
            f"stencilShadows={','.join(str(item) for item in tier_support.get('stencilShadows', [])) or '-'}`"
        )
        failures = [
            str(failure)
            for failure in dynamic_evidence.get("failures", [])
            if str(failure).strip()
        ]
        if failures:
            lines.append(f"- Failures: `{'; '.join(failures)}`")
        lines.append("")

    post_evidence = manifest.get("postProofEvidence")
    if isinstance(post_evidence, dict) and post_evidence.get("requiresPostProof"):
        fbo = (
            post_evidence.get("fbo", {})
            if isinstance(post_evidence.get("fbo"), dict)
            else {}
        )
        frames = (
            post_evidence.get("frames", {})
            if isinstance(post_evidence.get("frames"), dict)
            else {}
        )
        controls = (
            post_evidence.get("controls", {})
            if isinstance(post_evidence.get("controls"), dict)
            else {}
        )
        feature_evidence = (
            post_evidence.get("featureEvidence", {})
            if isinstance(post_evidence.get("featureEvidence"), dict)
            else {}
        )
        greyscale = (
            feature_evidence.get("greyscale", {})
            if isinstance(feature_evidence.get("greyscale"), dict)
            else {}
        )
        render_scale = (
            feature_evidence.get("renderScale", {})
            if isinstance(feature_evidence.get("renderScale"), dict)
            else {}
        )
        lines.append("## Post Proof")
        lines.append("")
        lines.append(f"- Version: `{post_evidence.get('version', '-')}`")
        lines.append(f"- Status: `{post_evidence.get('status', '-')}`")
        lines.append(
            "- Required maps: "
            f"`{', '.join(str(item) for item in post_evidence.get('requiredMaps', [])) or '-'}`"
        )
        lines.append(
            "- FBO/frames: "
            f"`requested={fbo.get('requested', 0)}, ready={fbo.get('ready', 0)}, "
            f"failures={fbo.get('initFailures', 0)}, frames={frames.get('post', 0)}, "
            f"screenshots={frames.get('screenshots', 0)}, minimized={frames.get('minimizedOutput', 0)}`"
        )
        lines.append(
            "- Controls: "
            f"`renderScale={controls.get('renderScale', 0)}, "
            f"greyscale={controls.get('greyscale', 0)}, "
            f"windowAdjusted={controls.get('windowAdjusted', 0)}`"
        )
        lines.append(
            "- Feature evidence: "
            f"`greyscale={greyscale.get('ok', False)}, "
            f"renderScale={render_scale.get('ok', False)}, "
            f"dimensionEvidence={render_scale.get('dimensionEvidence', False)}, "
            f"colorContract={post_evidence.get('colorContract', 0)}`"
        )
        failures = [
            str(failure)
            for failure in post_evidence.get("failures", [])
            if str(failure).strip()
        ]
        if failures:
            lines.append(f"- Failures: `{'; '.join(failures)}`")
        lines.append("")

    ownership_evidence = manifest.get("ownershipProofEvidence")
    if isinstance(ownership_evidence, dict) and ownership_evidence.get("requiresOwnership"):
        delegation = (
            ownership_evidence.get("delegation", {})
            if isinstance(ownership_evidence.get("delegation"), dict)
            else {}
        )
        post_output = (
            ownership_evidence.get("postOutputOwnership", {})
            if isinstance(ownership_evidence.get("postOutputOwnership"), dict)
            else {}
        )
        lines.append("## Ownership Proof")
        lines.append("")
        lines.append(f"- Version: `{ownership_evidence.get('version', '-')}`")
        lines.append(f"- Status: `{ownership_evidence.get('status', '-')}`")
        lines.append(f"- Profile: `{ownership_evidence.get('profile', '-')}`")
        lines.append(
            "- Legacy delegation: "
            f"`calls={delegation.get('calls', 0)}, items={delegation.get('items', 0)}`"
        )
        lines.append(
            "- Product tiers: "
            f"`{', '.join(str(tier) for tier in ownership_evidence.get('productTiers', [])) or '-'}`"
        )
        lines.append(
            "- Modern tier diagnostics: "
            f"`found={ownership_evidence.get('modernTierDiagnosticsFound', False)}, "
            f"ok={ownership_evidence.get('modernTierDiagnosticsOk', False)}`"
        )
        lines.append(
            "- Post/output ownership: "
            f"`modern={ownership_evidence.get('modernPostOutput', False)}, "
            f"nodes={post_output.get('postNodes', 0)}, "
            f"outputs={post_output.get('outputs', 0)}, "
            f"fallback=0x{int_metric(post_output.get('fallbackMask', 0)):08x}`"
        )
        failures = [
            str(failure)
            for failure in ownership_evidence.get("failures", [])
            if str(failure).strip()
        ]
        if failures:
            lines.append(f"- Failures: `{'; '.join(failures)}`")
        lines.append("")

    color_contracts = manifest.get("colorContracts")
    if isinstance(color_contracts, dict) or color_sweep_runs_for_summary:
        lines.append("## GLx Color Sweep")
        lines.append("")
        if isinstance(color_contracts, dict):
            matrix = (
                color_contracts.get("colorSweepMatrix", [])
                if isinstance(color_contracts.get("colorSweepMatrix"), list)
                else []
            )
            lines.append(f"- Contract version: `{color_contracts.get('version', '-')}`")
            lines.append(
                f"- Enabled: `{str(bool(manifest.get('colorSweepEnabled'))).lower()}`"
            )
            lines.append(f"- Matrix rows: `{len(matrix)}`")
        if color_sweep_runs_for_summary:
            lines.append("")
            lines.append("| Row | Status | Probe | Screenshots | Output Request | Target | Final Encode |")
            lines.append("|---|---:|---|---:|---:|---:|---:|")
            for run in color_sweep_runs_for_summary:
                row = run.get("colorSweepRow")
                row_id = str(row.get("id", "-")) if isinstance(row, dict) else "-"
                row_probe = str(row.get("probe", "-")) if isinstance(row, dict) else "-"
                row_expect = row.get("expect", {}) if isinstance(row, dict) else {}
                run_shots = [
                    shot
                    for shot in run.get("screenshots", [])
                    if isinstance(shot, dict)
                ]
                found_shots = sum(1 for shot in run_shots if shot.get("found"))
                diagnostics_result = (
                    run.get("diagnostics")
                    if isinstance(run.get("diagnostics"), dict)
                    else {}
                )
                metrics = (
                    diagnostics_result.get("metrics", {})
                    if isinstance(diagnostics_result, dict)
                    else {}
                )
                target_format = (
                    metrics.get("targetFormat", {})
                    if isinstance(metrics, dict) and isinstance(metrics.get("targetFormat"), dict)
                    else {}
                )
                color_audit = (
                    metrics.get("colorAudit", {})
                    if isinstance(metrics, dict) and isinstance(metrics.get("colorAudit"), dict)
                    else {}
                )
                output_backend = (
                    metrics.get("outputBackend", {})
                    if isinstance(metrics, dict) and isinstance(metrics.get("outputBackend"), dict)
                    else {}
                )
                internal_format = target_format.get("internalFormat", "-")
                if isinstance(internal_format, int):
                    internal_format = f"0x{internal_format:x}"
                output_request = output_backend.get("request", "-")
                if output_request == "-" and isinstance(row_expect, dict):
                    output_request = row_expect.get("outputRequest", "-")
                lines.append(
                    "| "
                    f"`{row_id}` | "
                    f"`{run.get('status', 'unknown')}` | "
                    f"`{row_probe}` | "
                    f"`{found_shots}/{len(run_shots)}` | "
                    f"`{output_request}` | "
                    f"`{internal_format}` | "
                    f"`{color_audit.get('finalEncode', '-')}` |"
                )
        lines.append("")

    gate_failures = manifest.get("gateFailures", [])
    if isinstance(gate_failures, list) and gate_failures:
        lines.append("## Gate Failures")
        lines.append("")
        for failure in gate_failures:
            lines.append(f"- {failure}")
        lines.append("")

    proof = manifest.get("proof")
    if isinstance(proof, dict):
        visual = proof.get("visual", {}) if isinstance(proof.get("visual"), dict) else {}
        performance = proof.get("performance", {}) if isinstance(proof.get("performance"), dict) else {}
        lines.append("## Proof")
        lines.append("")
        lines.append(f"- Overall: `{proof.get('status', '-')}`")
        if manifest.get("proofDir"):
            lines.append(f"- Proof dir: `{manifest.get('proofDir')}`")
        lines.append(
            "- Visual: "
            f"`{visual.get('status', '-')}` "
            f"found `{visual.get('found', '-')}/{visual.get('screenshots', '-')}`, "
            f"passed `{visual.get('passed', '-')}`, missing `{visual.get('missing', '-')}`, "
            f"failed `{visual.get('failed', '-')}`"
        )
        lines.append(
            "- Performance: "
            f"`{performance.get('status', '-')}` samples `{performance.get('sampleCount', '-')}`, "
            f"comparisons `{performance.get('comparisons', '-')}`, "
            f"failed comparisons `{performance.get('failedComparisons', '-')}`, "
            f"failures `{performance.get('failures', '-')}`"
        )
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
                stream_draw_skip = (
                    metrics.get("streamDrawSkip", {})
                    if isinstance(metrics.get("streamDrawSkip"), dict)
                    else {}
                )
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
                    f"stream high-risk dlight/screen/video "
                    f"`{stream_draw.get('dynamicLights', '-')}/"
                    f"{stream_draw.get('screenMaps', '-')}/"
                    f"{stream_draw.get('videoMaps', '-')}`, "
                    f"stream skip bind/key/fog/program "
                    f"`{stream_draw_skip.get('bind', '-')}/"
                    f"{stream_draw_skip.get('key', '-')}/"
                    f"{stream_draw_skip.get('fog', '-')}/"
                    f"{stream_draw_skip.get('program', '-')}`, "
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
                f"product tier `{latest.get('productTier', latest.get('tier', '-'))}`, "
                f"gpu `{latest.get('gpu', '-')}`, "
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
                f"stream draw material mt/depth/tex/env/dlight/screen/video "
                f"`{maxima.get('streamDrawMultitexture', '-')}/"
                f"{maxima.get('streamDrawDepthFragment', '-')}/"
                f"{maxima.get('streamDrawTexMods', '-')}/"
                f"{maxima.get('streamDrawEnvironment', '-')}/"
                f"{maxima.get('streamDrawDynamicLights', '-')}/"
                f"{maxima.get('streamDrawScreenMaps', '-')}/"
                f"{maxima.get('streamDrawVideoMaps', '-')}`, "
                f"categories ent/part/poly/mark/weapon/ui/beam/special "
                f"`{maxima.get('streamCategoryEntityDraws', '-')}/"
                f"{maxima.get('streamCategoryParticleDraws', '-')}/"
                f"{maxima.get('streamCategoryPolyDraws', '-')}/"
                f"{maxima.get('streamCategoryMarkDraws', '-')}/"
                f"{maxima.get('streamCategoryWeaponDraws', '-')}/"
                f"{maxima.get('streamCategoryUiDraws', '-')}/"
                f"{maxima.get('streamCategoryBeamDraws', '-')}/"
                f"{maxima.get('streamCategorySpecialDraws', '-')}`, "
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
    if args.list_profiles:
        print_profile_list()
        return 0
    if args.list_corpus:
        print_corpus_list()
        return 0

    explicit_maps = args.maps is not None
    explicit_demos = args.demos is not None
    explicit_corpus_scenes = args.corpus_scenes is not None
    apply_gate_defaults(args)

    exe = resolve_exe(args.exe, allow_missing=args.dry_run)
    basepath = args.basepath.resolve() if args.basepath else exe.parent.resolve()
    renderers = split_csv(args.renderers)
    switch_sequence = split_csv(args.switch_sequence) if args.switch_sequence else list(renderers)
    default_corpus_scene_ids = corpus_scene_ids_for_gate(args.gate, args.profile)
    corpus_scene_ids = validate_corpus_scene_ids(
        split_csv(args.corpus_scenes)
        if explicit_corpus_scenes
        else default_corpus_scene_ids
    )
    maps_value = (
        args.maps
        if explicit_maps or not corpus_scene_ids
        else corpus_targets_csv(corpus_scene_ids, "map")
    )
    if maps_value is None:
        maps_value = PROFILE_MAPS.get(args.profile, "q3dm1")
    maps = split_csv(maps_value)
    demos_value = (
        args.demos
        if explicit_demos or not corpus_scene_ids
        else corpus_targets_csv(corpus_scene_ids, "demo")
    )
    demos = split_csv(demos_value or "")

    validate_renderers(renderers)
    validate_renderers(switch_sequence)

    run_id = (
        datetime.now(timezone.utc).strftime("glx-sweep-%Y%m%d-%H%M%S-%f") +
        f"-p{os.getpid()}"
    )
    qpath_run_token = runtime_token(run_id)
    output_root = args.output_dir.resolve() / run_id
    homepath = args.homepath.resolve() if args.homepath else output_root / "home"
    logs_dir = output_root / "logs"
    apply_proof_defaults(args, output_root)
    validate_proof_approval_mode(args)
    cvars = make_cvars(args)
    cfg_cvars = config_cvars(args, cvars)
    startup_cvars = launch_cvars(cvars)
    qconsole_log_path = engine_console_log_path(homepath, args.fs_game)
    runs: list[dict[str, object]] = []
    screenshot_baseline_dir = args.screenshot_baseline_dir.resolve() if args.screenshot_baseline_dir else None
    screenshot_diff_dir = args.screenshot_diff_dir.resolve() if args.screenshot_diff_dir else None
    proof_dir = args.proof_dir.resolve() if args.proof_dir else None
    proof_platform = (
        normalize_proof_platform(args.proof_platform)
        if args.proof_platform
        else runtime_platform_id()
    )
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
    performance_budget = performance_budget_for_gate(args.gate, performance_budget)
    gate_requirements = (
        RC_GATE_PRESETS[args.gate]["requirements"] if args.gate else {}
    )
    proof_corpus = proof_corpus_manifest(
        corpus_scene_ids,
        gate_requirements.get("required_corpus_tags", ()),  # type: ignore[union-attr]
        gate_requirements.get("required_parity_suites", ()),  # type: ignore[union-attr]
    )
    parity_suite_ids = validate_parity_suite_ids(
        gate_requirements.get("required_parity_suites", ())  # type: ignore[union-attr]
    )

    if not args.no_switch_sweep and maps:
        switch_cfg_name = validate_runtime_qpath(f"{qpath_run_token}-switch.cfg")
        switch_cfg, expected_shots = build_switch_cfg(
            args,
            cfg_cvars,
            maps,
            switch_sequence,
            run_id,
            qpath_run_token,
            corpus_scene_ids,
            parity_suite_ids,
        )
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
            qconsole_log_path,
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
                "restartMode": "fast",
                "vidRestartEquivalent": True,
                "vidRestartPath": "CL_Vid_Restart(REF_KEEP_WINDOW)",
                "screenshots": shots,
            }
        )
        runs.append(result)

    if args.color_sweep:
        color_map = maps[0] if maps else "q3dm1"
        for row_index, row in enumerate(GLX_COLOR_SWEEP_MATRIX, start=1):
            row_id = str(row["id"])
            row_cvars = dict(cvars)
            row_values = row.get("cvars", {})
            if isinstance(row_values, dict):
                row_cvars.update({str(name): str(value) for name, value in row_values.items()})
            row_cfg_cvars = config_cvars(args, row_cvars)
            cfg_name = validate_runtime_qpath(f"{qpath_run_token}-c{row_index:02d}.cfg")
            color_cfg, expected_shots = build_color_sweep_cfg(
                args,
                row_cfg_cvars,
                color_map,
                row,
                run_id,
                qpath_run_token,
                row_index,
            )
            cfg_path = write_cfg(homepath, args.fs_game, cfg_name, color_cfg)
            command = base_launch_args(
                exe,
                basepath,
                homepath,
                args.fs_game,
                "glx",
                cfg_name,
                launch_cvars(row_cvars),
            )
            log_path = logs_dir / f"color-{sanitize(row_id)}.log"
            result = run_engine(
                command,
                exe.parent,
                args.timeout,
                log_path,
                args.dry_run,
                qconsole_log_path,
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
                result["diagnostics"] = analyze_glx_diagnostics(log_path, args.profile)
                result["performance"] = analyze_glx_performance(log_path)
            result.update(
                {
                    "type": "color-sweep",
                    "config": str(cfg_path),
                    "renderer": "glx",
                    "map": color_map,
                    "colorSweepRow": dict(row),
                    "screenshots": shots,
                }
            )
            runs.append(result)

    if not args.no_demo_sweep and demos:
        for renderer_index, renderer in enumerate(renderers, start=1):
            for demo_index, demo in enumerate(demos, start=1):
                safe_renderer = sanitize(renderer)
                safe_demo = sanitize(demo)
                cfg_name = validate_runtime_qpath(
                    f"{qpath_run_token}-d{renderer_index:02d}-{demo_index:02d}.cfg"
                )
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
                    qconsole_log_path,
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

    shader_reference_ramps: list[dict[str, object]] = []
    if args.write_image_evidence or args.color_sweep:
        shader_reference_ramps = write_shader_reference_ramps(output_root / "image-evidence" / "shader-reference-ramps")

    manifest = {
        "runId": run_id,
        "runtimeQpathToken": qpath_run_token,
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
        "hostPlatform": host_platform_manifest(),
        "proofPlatform": proof_platform,
        "profile": args.profile,
        "cvars": cvars,
        "startupCvars": startup_cvars,
        "configCvars": cfg_cvars,
        "renderers": renderers,
        "switchSequence": switch_sequence,
        "switchRounds": args.switch_rounds,
        "maps": maps,
        "demos": demos,
        "proofCorpus": proof_corpus,
        "colorContracts": color_contract_manifest(),
        "colorSweepEnabled": bool(args.color_sweep),
        "imageEvidence": {
            "version": GLX_IMAGE_EVIDENCE_VERSION,
            "shaderReferenceRamps": shader_reference_ramps,
            "requiredSidecars": list(GLX_IMAGE_EVIDENCE_SIDECARS),
        },
        "perfSamplesEnabled": not args.no_perf_samples,
        "perfSampleWait": args.perf_sample_wait,
        "performanceBudget": performance_budget,
        "performanceBaselinePath": str(args.performance_baseline.resolve()) if args.performance_baseline else "",
        "approvePerformanceBaseline": args.approve_performance_baseline,
        "performanceMaxGrowthRatio": performance_growth_ratio,
        "proofDir": str(proof_dir) if proof_dir else "",
        "screenshotBaselineDir": str(screenshot_baseline_dir) if screenshot_baseline_dir else "",
        "screenshotDiffDir": str(screenshot_diff_dir) if screenshot_diff_dir else "",
        "approveScreenshotBaselines": args.approve_screenshot_baselines,
        "screenshotThresholds": {
            "maxRms": screenshot_max_rms,
            "maxChangedPixelRatio": screenshot_max_pixel_ratio,
        },
        "runs": runs,
    }
    manifest["rendererSwitchEvidence"] = renderer_switch_lifecycle_evidence(manifest)

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
    if manifest_requires_world_proof(manifest, gate_requirements):  # type: ignore[arg-type]
        manifest["worldProofEvidence"] = world_proof_evidence(manifest, gate_requirements)  # type: ignore[arg-type]
    if manifest_requires_material_proof(manifest, gate_requirements):  # type: ignore[arg-type]
        manifest["materialProofEvidence"] = material_proof_evidence(manifest, gate_requirements)  # type: ignore[arg-type]
    if manifest_requires_dynamic_proof(manifest, gate_requirements):  # type: ignore[arg-type]
        manifest["dynamicProofEvidence"] = dynamic_proof_evidence(manifest, gate_requirements)  # type: ignore[arg-type]
    if manifest_requires_post_proof(manifest, gate_requirements):  # type: ignore[arg-type]
        manifest["postProofEvidence"] = post_proof_evidence(manifest, gate_requirements)  # type: ignore[arg-type]
    if manifest_requires_ownership_proof(manifest):
        manifest["ownershipProofEvidence"] = ownership_proof_evidence(manifest)
    manifest["proof"] = proof_status(manifest)

    gate_failures = evaluate_gate(manifest)
    manifest["gateFailures"] = gate_failures
    if isinstance(manifest.get("proof"), dict):
        manifest["proof"]["gateStatus"] = "planned" if args.dry_run else ("passed" if not gate_failures else "failed")  # type: ignore[index]

    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / "manifest.json"
    visual_dossier_path = output_root / "glx-visual-dossier.md"
    manifest["visualDossier"] = {
        "version": GLX_VISUAL_DOSSIER_VERSION,
        "path": str(visual_dossier_path),
        "sections": [
            "current-pipeline-flow",
            "target-pipeline-flow",
            "renderer-switch-lifecycle",
            "backend-state-overlay",
            "driver-tier-matrix",
            "histogram-and-false-color-evidence",
            "parity-diff-sheet",
        ],
    }
    if isinstance(manifest.get("worldProofEvidence"), dict):
        manifest["visualDossier"]["sections"].insert(3, "world-proof")  # type: ignore[index]
    if isinstance(manifest.get("materialProofEvidence"), dict):
        manifest["visualDossier"]["sections"].insert(4, "material-proof")  # type: ignore[index]
    if isinstance(manifest.get("dynamicProofEvidence"), dict):
        manifest["visualDossier"]["sections"].insert(5, "dynamic-proof")  # type: ignore[index]
    if isinstance(manifest.get("postProofEvidence"), dict):
        manifest["visualDossier"]["sections"].insert(6, "post-proof")  # type: ignore[index]
    if isinstance(manifest.get("ownershipProofEvidence"), dict):
        manifest["visualDossier"]["sections"].insert(3, "ownership-proof")  # type: ignore[index]
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    visual_dossier_path.write_text(
        glx_visual_dossier(manifest, manifest_path),
        encoding="utf-8",
        newline="\n",
    )

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
    print(f"Proof platform: {proof_platform}")
    print(
        "Corpus: "
        f"{GLX_PROOF_CORPUS_VERSION} "
        f"({len(corpus_scene_ids)} selected scene{'s' if len(corpus_scene_ids) != 1 else ''})"
    )
    if parity_suite_ids:
        print(
            "Parity suites: "
            f"{GLX_PARITY_SUITE_VERSION} ({', '.join(parity_suite_ids)})"
        )
    print(f"Manifest: {manifest_path}")
    print(f"Visual dossier: {visual_dossier_path}")
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
    proof = manifest.get("proof")
    if isinstance(proof, dict) and proof.get("status") != "not-configured":
        visual = proof.get("visual", {}) if isinstance(proof.get("visual"), dict) else {}
        performance = proof.get("performance", {}) if isinstance(proof.get("performance"), dict) else {}
        print(
            "Proof: "
            f"{proof.get('status')} "
            f"(visual {visual.get('status', '-')}, performance {performance.get('status', '-')})"
        )
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

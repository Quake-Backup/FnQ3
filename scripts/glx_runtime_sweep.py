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
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "code" / "win32" / "msvc2017" / "output"
DEFAULT_SWEEP_ROOT = ROOT / ".tmp" / "runtime-sweeps"
RENDERER_NAME_RE = re.compile(r"^[A-Za-z1-9]+$")
DEFAULT_PERFORMANCE_MAX_GROWTH_RATIO = 0.20
GLX_EXPECTED_PASS_SCHEDULE = (
    "frame-setup>sky-opaque-world>opaque-entities>dynamic-scene>transparent-layers>"
    "first-person-weapon>hud-2d>postprocess>output-export"
)
GLX_EXPECTED_PASS_SCHEDULE_COUNT = 9
GLX_EXPECTED_PASS_SCHEDULE_HASH = "0c6d7632"
GLX_PRODUCT_TIERS = {"GL12", "GL2X", "GL3X", "GL41", "GL46"}
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
)
DEFAULT_PERFORMANCE_BUDGET = {
    "max": {
        "streamRejects": 0,
        "materialCompileFailures": 0,
        "materialLinkFailures": 0,
        "materialPrecacheFailures": 0,
        "materialBindFailures": 0,
        "streamDrawFallbacks": 0,
        "streamDrawDynamicLights": 0,
        "streamDrawScreenMaps": 0,
        "streamDrawVideoMaps": 0,
        "staticDrawFallbacks": 0,
        "staticMdiErrors": 0,
        "gl3xUnsupportedPersistentUploads": 0,
        "gl41UnsupportedPersistentUploads": 0,
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
    r"(?:glx:\s*)?pass schedule:?\s*(?P<valid>valid|invalid)\s+"
    r"(?P<count>\d+)/(?P<hash>[0-9a-fA-F]+)\s+(?P<order>[A-Za-z0-9_>\-]+)",
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
GLX_COLOR_AUDIT_RE = re.compile(
    r"(?:glx:\s*)?color audit:?\s*"
    r"srgb-decode\s+(?P<srgbDecode>\w+)\s+"
    r"requested\s+(?P<srgbRequested>\w+)\s+"
    r"available\s+(?P<srgbAvailable>\w+),?\s+"
    r"framebuffer-srgb\s+(?P<framebufferSrgb>\w+)\s+"
    r"requested\s+(?P<framebufferRequested>\w+)\s+"
    r"available\s+(?P<framebufferAvailable>\w+),?\s+"
    r"capture\s+(?P<capture>[A-Za-z0-9_-]+)",
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

# Frozen GLx startup profiles. Keep these in sync with GLX_PROFILE_CVARS in
# code/rendererglx/glx_module.cpp; the GLx runtime sweep tests parse that table
# so the launch profile cannot drift quietly from the renderer-owned profile.
GLX_RC_PROFILE_CVARS = {
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
    "r_glxStreamDrawShadows": "1",
    "r_glxStreamDrawBeams": "1",
    "r_glxStreamDrawPostProcess": "1",
    "r_glxMaterialRenderer": "1",
    "r_glxMaterialPrecache": "1",
    "r_glxGpuTiming": "1",
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
    "r_hdr": "1",
    "r_tonemap": "2",
    "r_tonemapExposure": "1.0",
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

GLX_PROOF_CORPUS_VERSION = "2026-05-09-task-r"
GLX_PROOF_CORPUS_DOC = "docs/fnquake3/GLX_PROOF_CORPUS.md"

GLX_PROOF_CORPUS_SCENES: dict[str, dict[str, object]] = {
    "stock-q3dm1-hud": {
        "kind": "map",
        "target": "q3dm1",
        "assetTier": "retail-baseq3",
        "tags": (
            "stock-map",
            "baseline-map",
            "ui-hud-sensitive",
            "lightmap",
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
            "tone-map-proof",
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
            "performance-comparison",
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
            "color-grade-proof",
            "tone-map-proof",
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
        ),
        "description": "Optional GLx proof-corpus stress map for broad shader-stage and material-key coverage.",
    },
    "modern-fnq3glx-fog01": {
        "kind": "map",
        "target": "fnq3_glx_fog01",
        "assetTier": "glx-proof-corpus",
        "tags": (
            "modern-map",
            "fog-heavy",
            "visibility",
        ),
        "description": "Optional GLx proof-corpus stress map for layered fog and visibility comparisons.",
    },
    "timedemo-demo1": {
        "kind": "demo",
        "target": "demo1",
        "assetTier": "retail-baseq3",
        "tags": (
            "stock-demo",
            "performance-comparison",
        ),
        "description": "Retail timedemo used for legacy OpenGL versus GLx performance comparisons.",
    },
    "timedemo-fnq3glx-particles01": {
        "kind": "demo",
        "target": "fnq3_glx_particles01",
        "assetTier": "glx-proof-corpus",
        "tags": (
            "particle-heavy-demo",
            "modern-map",
            "performance-comparison",
        ),
        "description": "Optional GLx proof-corpus timedemo for particles, marks, transient polys, and UI churn.",
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

GLX_PROFILE_CORPUS_SCENES = {
    "baseline": ("stock-q3dm1-hud",),
    "glx-world": ("stock-q3dm1-hud",),
    "glx-material": ("stock-q3dm1-hud",),
    "glx-bloom": ("stock-q3dm1-hud",),
    "glx-color": ("stock-q3dm17-open", "stock-q3dm11-shader", "stock-q3dm15-fog"),
    "glx-parity": ("stock-q3dm1-hud",),
    "glx-ownership": ("stock-q3dm1-hud", "stock-q3dm17-open"),
    "glx-stress": GLX_GATE_CORPUS_SCENES["rc-stress"],
}


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
        records.append(
            {
                "id": scene_id,
                "kind": scene["kind"],
                "target": scene["target"],
                "assetTier": scene["assetTier"],
                "tags": list(scene.get("tags", ())),
                "description": scene["description"],
            }
        )
    return records


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
) -> dict[str, object]:
    selected_scene_ids = validate_corpus_scene_ids(scene_ids)
    return {
        "version": GLX_PROOF_CORPUS_VERSION,
        "document": GLX_PROOF_CORPUS_DOC,
        "selectedSceneIds": selected_scene_ids,
        "selectedScenes": corpus_scene_records(selected_scene_ids),
        "selectedTags": corpus_tags(selected_scene_ids),
        "requiredTags": sorted(set(str(tag) for tag in required_tags if str(tag).strip())),
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
        "tags": corpus_tags(GLX_PROOF_CORPUS_SCENES.keys()),
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
            ),
            "require_screenshots": True,
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
            "timeout": 300.0,
        },
        "requirements": {
            "require_proof_corpus": True,
            "required_corpus_tags": (
                "stock-map",
                "stock-demo",
                "ui-hud-sensitive",
                "performance-comparison",
            ),
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
                "performance-comparison",
            ),
            "require_screenshots": True,
            "require_visual_baseline": True,
            "require_performance_baseline": True,
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
                "performance-comparison",
            ),
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
    print("Scenes:")
    for scene_id, scene in sorted(GLX_PROOF_CORPUS_SCENES.items()):
        print(
            "  "
            f"{scene_id}: kind={scene['kind']} target={scene['target']} "
            f"assetTier={scene['assetTier']} tags={','.join(scene.get('tags', ())) }"
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


def candidate_exe_names() -> list[str]:
    machine = platform.machine().lower()
    if os.name == "nt":
        arch_suffixes = ["x64"] if machine in {"amd64", "x86_64"} else [machine, "x64"]
        names: list[str] = []
        for arch in arch_suffixes:
            names.extend(
                [
                    f"fnquake3.glx.{arch}.exe",
                    f"fnquake3.{arch}.exe",
                ]
            )
        names.append("fnquake3.exe")
        return names

    return ["fnquake3.glx", "fnquake3"]


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
    corpus_scene_ids: Iterable[str] = (),
) -> tuple[str, list[dict[str, object]]]:
    lines = cfg_preamble(cvars, "renderer switch screenshot sweep")
    expected_shots: list[dict[str, object]] = []
    selected_corpus_scene_ids = validate_corpus_scene_ids(corpus_scene_ids)

    lines.append(f"wait {args.startup_wait}")
    for map_index, map_name in enumerate(maps, start=1):
        safe_map = sanitize(map_name)
        map_corpus_scene_ids = corpus_scene_ids_for_target(
            selected_corpus_scene_ids,
            "map",
            map_name,
        )
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
                        "corpusSceneIds": map_corpus_scene_ids,
                        "corpusTags": corpus_tags(map_corpus_scene_ids),
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
            or line.startswith("output backend")
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
            valid = 1 if match.group("valid").lower() == "valid" else 0
            record_metric_max(metrics, "passSchedule", "valid", valid)
            record_metric_max(metrics, "passSchedule", "count", int_group(match, "count"))
            record_metric_max(metrics, "passSchedule", "hash", match.group("hash").lower())
            record_metric_max(metrics, "passSchedule", "order", match.group("order"))
            if not pass_schedule_valid_from_match(match):
                failures.append(
                    "GLx pass schedule is not locked to the final contract: "
                    f"{match.group('valid')} {match.group('count')}/{match.group('hash')} "
                    f"{match.group('order')}."
                )
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

        match = GLX_COLOR_PIPELINE_RE.search(line)
        if match:
            record_metric_max(metrics, "colorPipeline", "space", match.group("space").lower())
            record_metric_max(metrics, "colorPipeline", "transfer", match.group("transfer").lower())
            record_metric_max(metrics, "colorPipeline", "toneMap", match.group("toneMap").lower())
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
            if q3_bool(match.group("framebufferSrgb")):
                failures.append("GLx framebuffer sRGB state is active on the shader-encoded SDR output path.")
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

    product_tier = metric_section(metrics, "productTier").get("tier")
    if product_tier == "GL12":
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
    if product_tier == "GL2X":
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
    if product_tier == "GL3X":
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
    if product_tier == "GL41":
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
    if product_tier == "GL46":
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
            perf_record_string(performance, "productTier", match.group("tier"))
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

        match = GLX_PASS_SCHEDULE_RE.search(line)
        if match:
            perf_record_numeric(performance, "passScheduleValid",
                1 if match.group("valid").lower() == "valid" else 0)
            perf_record_numeric(performance, "passScheduleCount", int_group(match, "count"))
            perf_record_string(performance, "passScheduleHash", match.group("hash").lower())
            perf_record_string(performance, "passScheduleOrder", match.group("order"))
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

        match = GLX_COLOR_PIPELINE_RE.search(line)
        if match:
            perf_record_string(performance, "colorSpace", match.group("space").lower())
            perf_record_string(performance, "outputTransfer", match.group("transfer").lower())
            perf_record_string(performance, "toneMap", match.group("toneMap").lower())
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

        match = GLX_COLOR_AUDIT_RE.search(line)
        if match:
            perf_record_numeric(performance, "colorSrgbDecode", 1 if q3_bool(match.group("srgbDecode")) else 0)
            perf_record_numeric(performance, "colorSrgbAvailable", 1 if q3_bool(match.group("srgbAvailable")) else 0)
            perf_record_numeric(performance, "colorFramebufferSrgb", 1 if q3_bool(match.group("framebufferSrgb")) else 0)
            perf_record_numeric(performance, "colorFramebufferSrgbAvailable", 1 if q3_bool(match.group("framebufferAvailable")) else 0)
            perf_record_string(performance, "captureColorSpace", match.group("capture").lower())
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

    failures.extend(evaluate_proof_corpus(manifest, requirements))  # type: ignore[arg-type]

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
        lines.append("## GLx Proof Corpus")
        lines.append("")
        lines.append(f"- Version: `{proof_corpus.get('version', '-')}`")
        lines.append(f"- Document: `{proof_corpus.get('document', '-')}`")
        lines.append(f"- Scenes: `{', '.join(selected_scene_ids) or '-'}`")
        lines.append(f"- Tags: `{', '.join(selected_tags) or '-'}`")
        if required_tags:
            lines.append(f"- Required tags: `{', '.join(required_tags)}`")
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
    output_root = args.output_dir.resolve() / run_id
    homepath = args.homepath.resolve() if args.homepath else output_root / "home"
    logs_dir = output_root / "logs"
    apply_proof_defaults(args, output_root)
    validate_proof_approval_mode(args)
    cvars = make_cvars(args)
    cfg_cvars = config_cvars(args, cvars)
    startup_cvars = launch_cvars(cvars)
    runs: list[dict[str, object]] = []
    screenshot_baseline_dir = args.screenshot_baseline_dir.resolve() if args.screenshot_baseline_dir else None
    screenshot_diff_dir = args.screenshot_diff_dir.resolve() if args.screenshot_diff_dir else None
    proof_dir = args.proof_dir.resolve() if args.proof_dir else None
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
    gate_requirements = (
        RC_GATE_PRESETS[args.gate]["requirements"] if args.gate else {}
    )
    proof_corpus = proof_corpus_manifest(
        corpus_scene_ids,
        gate_requirements.get("required_corpus_tags", ()),  # type: ignore[union-attr]
    )

    if not args.no_switch_sweep and maps:
        switch_cfg_name = f"{run_id}-switch.cfg"
        switch_cfg, expected_shots = build_switch_cfg(
            args,
            cfg_cvars,
            maps,
            switch_sequence,
            run_id,
            corpus_scene_ids,
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
        "proofCorpus": proof_corpus,
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
    manifest["proof"] = proof_status(manifest)

    gate_failures = evaluate_gate(manifest)
    manifest["gateFailures"] = gate_failures
    if isinstance(manifest.get("proof"), dict):
        manifest["proof"]["gateStatus"] = "planned" if args.dry_run else ("passed" if not gate_failures else "failed")  # type: ignore[index]

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
    print(
        "Corpus: "
        f"{GLX_PROOF_CORPUS_VERSION} "
        f"({len(corpus_scene_ids)} selected scene{'s' if len(corpus_scene_ids) != 1 else ''})"
    )
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

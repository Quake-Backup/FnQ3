from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SWEEP_PATH = ROOT / "scripts" / "glx_runtime_sweep.py"
PROMOTION_PATH = ROOT / "scripts" / "glx_promotion.py"
RELEASE_PATH = ROOT / "scripts" / "release.py"
FEATURE_MATRIX_PATH = ROOT / "docs" / "fnquake3" / "GLX_FEATURE_MATRIX.md"
COLORSPACE_AUDIT_PATH = ROOT / "docs" / "fnquake3" / "GLX_COLORSPACE_AUDIT.md"
FEATURE_MATRIX_ALLOWED_STATUSES = {"covered", "partially covered", "missing"}
FEATURE_MATRIX_REQUIRED_IDS = {
    "CORE-ABI",
    "CORE-SWITCH",
    "CORE-PASS-ORDER",
    "CORE-TIERS",
    "CORE-OWNERSHIP",
    "WORLD-BSP",
    "WORLD-LIGHTMAPS",
    "WORLD-FOG",
    "WORLD-SKY",
    "WORLD-PORTALS",
    "MATERIAL-STAGES",
    "MATERIAL-TEXMODS",
    "MATERIAL-TCGEN",
    "MATERIAL-VIDEOMAP",
    "MATERIAL-SCREENMAP",
    "MATERIAL-DEPTHFRAG",
    "DYN-ENTITIES",
    "DYN-PARTICLES",
    "DYN-BEAMS",
    "DYN-DLIGHTS",
    "DYN-SHADOWS-STENCIL",
    "DYN-SHADOWS-PLANAR",
    "DYN-CEL",
    "DYN-OUTLINE",
    "POST-FBO",
    "POST-BLOOM1",
    "POST-BLOOM2",
    "POST-GAMMA",
    "POST-GREYSCALE",
    "POST-RENDERSCALE",
    "POST-MSAA",
    "POST-SSAA",
    "POST-HDR-PRECISION",
    "COLOR-SCENE-LINEAR",
    "COLOR-TONEMAP-GRADE",
    "OUTPUT-SDR",
    "OUTPUT-HDR-HARDWARE",
    "UI-HUD",
    "UI-CINEMATICS",
    "CAPTURE-SCREENSHOTS",
    "CAPTURE-CUBEMAPS",
    "DEMO-PLAYBACK",
    "MODERN-NORMALMAP",
    "MODERN-SPECULAR",
    "MODERN-PARALLAX",
    "MODERN-CUBEMAP-LIGHTING",
    "MODERN-SUNLIGHT",
    "MODERN-SHADOWMAPS",
    "MODERN-SSAO",
    "PERF-STATIC-CACHE",
    "PERF-STATIC-SHIPPED",
    "PERF-STATIC-MDI",
    "PERF-DYNAMIC-STREAM",
    "PERF-GPU-TIMING",
    "DEBUG-DIAGNOSTICS",
    "PROOF-RUNTIME",
}

spec = importlib.util.spec_from_file_location("glx_runtime_sweep", SWEEP_PATH)
assert spec is not None
glx_runtime_sweep = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(glx_runtime_sweep)
sys.path.insert(0, str(ROOT / "scripts"))

promotion_spec = importlib.util.spec_from_file_location("glx_promotion", PROMOTION_PATH)
assert promotion_spec is not None
glx_promotion = importlib.util.module_from_spec(promotion_spec)
assert promotion_spec.loader is not None
promotion_spec.loader.exec_module(glx_promotion)

release_spec = importlib.util.spec_from_file_location("fnq3_release", RELEASE_PATH)
assert release_spec is not None
fnq3_release = importlib.util.module_from_spec(release_spec)
assert release_spec.loader is not None
release_spec.loader.exec_module(fnq3_release)


def parse_runtime_glx_profiles() -> dict[str, dict[str, str]]:
    source = (ROOT / "code" / "rendererglx" / "glx_module.cpp").read_text(encoding="utf-8")
    match = re.search(
        r"static const ProfileCvarSetting GLX_PROFILE_CVARS\[\] = \{(?P<body>.*?)\n\};",
        source,
        re.DOTALL,
    )
    assert match is not None
    profiles: dict[str, dict[str, str]] = {
        "off": {},
        "rc": {},
        "stress": {},
    }

    for name, off, rc, stress in re.findall(
        r'\{\s*"([^"]+)"\s*,\s*"([^"]*)"\s*,\s*"([^"]*)"\s*,\s*"([^"]*)"\s*\}',
        match.group("body"),
    ):
        profiles["off"][name] = off
        profiles["rc"][name] = rc
        profiles["stress"][name] = stress

    assert profiles["rc"]
    return profiles


def locked_pass_schedule_latest() -> dict[str, object]:
    return {
        "tier": "GL2X",
        "productTier": "GL2X",
        "passScheduleValid": 1,
        "passScheduleCount": glx_runtime_sweep.GLX_EXPECTED_PASS_SCHEDULE_COUNT,
        "passScheduleHash": glx_runtime_sweep.GLX_EXPECTED_PASS_SCHEDULE_HASH,
        "passScheduleOrder": glx_runtime_sweep.GLX_EXPECTED_PASS_SCHEDULE,
    }


def screenshot_histogram() -> dict[str, object]:
    return {
        "status": "passed",
        "width": 1,
        "height": 1,
        "pixels": 1,
        "meanLuma": 128.0,
        "meanRed": 128.0,
        "meanGreen": 128.0,
        "meanBlue": 128.0,
        "p01Luma": 128,
        "p50Luma": 128,
        "p99Luma": 128,
        "p50Red": 128,
        "p50Green": 128,
        "p50Blue": 128,
        "clippedBlackRatio": 0.0,
        "clippedWhiteRatio": 0.0,
    }


def sdr_capture_policy() -> dict[str, object]:
    return dict(glx_runtime_sweep.GLX_SCREENSHOT_CAPTURE_POLICY_CONTRACT)


def color_diagnostics_metrics() -> dict[str, object]:
    return {
        "colorPipeline": {
            "space": "scene-linear",
            "transfer": "sdr-srgb",
            "toneMap": "aces-fitted",
            "grade": "none",
            "exposure": 1.0,
            "paperWhite": 203.0,
            "maxOutput": 203.0,
        },
        "colorAudit": {
            "srgbDecode": 1,
            "srgbRequested": 1,
            "srgbAvailable": 1,
            "framebufferSrgb": 0,
            "framebufferRequested": 1,
            "framebufferAvailable": 1,
            "capture": "sdr-srgb",
            "captureRequest": "sdr-srgb",
            "captureHdrAware": 0,
            "captureSupported": 1,
            "targetFloat": 1,
            "finalEncode": "shader-srgb",
            "contract": 1,
        },
        "outputBackend": {
            "request": "auto",
            "selected": "sdr-srgb",
            "native": "sdr-srgb",
            "hardware": 0,
            "experimental": 0,
            "displayHdr": 0,
            "headroom": 1.0,
            "sdrWhite": 203.0,
            "displayMax": 203.0,
            "icc": 0,
            "iccBytes": 0,
        },
        "textureAudit": {
            "srgb": 4,
            "srgbDecode": 4,
            "linear": 2,
            "linearDecode": 0,
            "data": 2,
            "dataDecode": 0,
            "unknown": 0,
            "unknownDecode": 0,
            "missingSrgbDecode": 0,
            "unexpectedDecode": 0,
        },
        "targetFormat": {
            "renderWidth": 512,
            "renderHeight": 384,
            "captureWidth": 512,
            "captureHeight": 384,
            "windowWidth": 640,
            "windowHeight": 480,
            "internalFormat": 0x881A,
            "textureFormat": 0x1908,
            "textureType": 0x140B,
        },
        "postprocess": {
            "fboRequested": 1,
            "fboReady": 1,
            "fboPrograms": 1,
            "fboFramebuffer": 1,
            "fboAttempts": 1,
            "fboFailed": 0,
            "lastOutput": "gamma-blit",
        },
        "postprocessControls": {
            "sceneLinearHdr": 1,
            "precision": 16,
            "renderScale": 1,
            "bloom": 2,
            "msaa": 0,
            "supersample": 0,
            "windowAdjusted": 1,
            "greyscale": 1.0,
        },
        "postprocessFrames": {
            "frames": 3,
            "bloomFinal": 1,
            "gammaDirect": 0,
            "gammaBlit": 3,
            "minimizedOutput": 0,
            "screenshots": 1,
        },
        "postprocessFrameFeatures": {
            "bloomAvailable": 1,
            "sceneLinear": 1,
            "toneMapped": 1,
            "graded": 1,
            "renderScale": 1,
            "greyscale": 1,
            "windowAdjusted": 1,
            "minimized": 0,
        },
        "gl12Support": {
            "lightmaps": 1,
            "multitexture": 1,
            "fog": 1,
            "sprites": 1,
            "beams": 1,
            "dynamicLights": 1,
            "stencilShadows": 1,
            "screenshots": 1,
            "demos": 1,
        },
        "gl2xSupport": {
            "commonMaterials": 1,
            "dynamicEntities": 1,
            "lightmaps": 1,
            "multitexture": 1,
            "fog": 1,
            "sprites": 1,
            "beams": 1,
            "screenshots": 1,
            "demos": 1,
        },
        "staticWorld": {
            "rendererEnabled": 1,
            "arenaReady": 1,
            "packetBatchEnabled": 1,
            "packetBatchBatches": 4,
            "indirectBufferReady": 1,
            "glErrors": 0,
            "failures": 0,
        },
        "streamDraw": {
            "draws": 3,
            "attempts": 3,
            "indexes": 1024,
            "multitexture": 2,
            "fog": 2,
            "depthFragment": 1,
            "texMods": 2,
            "environment": 1,
            "dynamicLights": 0,
            "screenMaps": 0,
            "videoMaps": 0,
            "shadows": 2,
            "beams": 0,
            "postprocess": 0,
            "fallbacks": 0,
            "skips": 0,
        },
        "streamCategory": {
            "entityDraws": 2,
            "entityAttempts": 2,
            "entityObserved": 1,
            "entityFallbacks": 0,
            "particleDraws": 0,
            "particleAttempts": 0,
            "particleObserved": 0,
            "particleFallbacks": 0,
            "polyDraws": 0,
            "polyAttempts": 0,
            "polyObserved": 0,
            "polyFallbacks": 0,
            "markDraws": 0,
            "markAttempts": 0,
            "markObserved": 0,
            "markFallbacks": 0,
            "weaponDraws": 1,
            "weaponAttempts": 1,
            "weaponObserved": 1,
            "weaponFallbacks": 0,
            "uiDraws": 0,
            "uiAttempts": 0,
            "uiObserved": 0,
            "uiFallbacks": 0,
            "beamDraws": 0,
            "beamAttempts": 0,
            "beamObserved": 0,
            "beamFallbacks": 0,
            "specialDraws": 0,
            "specialAttempts": 0,
            "specialObserved": 0,
            "specialFallbacks": 0,
        },
        "streamDrawSkip": {
            "program": 0,
        },
        "materialParameters": {
            "blocks": 4,
            "invalid": 0,
            "hash": 0x00F00D,
            "sort": 0,
            "passes": 2,
            "features": 0x0C23,
            "flags": 0x0C23,
            "state": 0x30,
            "rgbGen": 2,
            "rgbWave": 0,
            "alphaGen": 1,
            "alphaWave": 0,
            "tcGen0": 3,
            "tcGen1": 2,
        },
        "material": {
            "enabled": 1,
            "ready": 1,
            "attempts": 24,
            "compile": 0,
            "link": 0,
            "precacheFailures": 0,
            "precacheAttempts": 24,
            "bind": 0,
        },
        "materialFallbacks": {
            "unsupported": 0,
            "disabled": 0,
            "notReady": 0,
            "full": 0,
            "discarded": 0,
        },
        "materialCompilerPlans": {
            "compiled": 12,
            "unsupported": 0,
            "lastUnsupported": 0,
            "lastUnsupportedReason": "none",
        },
        "materialLastKey": {
            "name": "test",
            "flags": 0x0C23,
            "state": 0x30,
            "rgbGen": 2,
            "rgbWave": 0,
            "alphaGen": 1,
            "alphaWave": 0,
            "tcGen0": 3,
            "tcGen1": 2,
            "texMods0": 1,
            "texMods1": 0,
            "combine": 1,
            "fogPass": 0,
        },
        "materialLanguage": {
            "flags": 0x0C23,
            "state": 0x30,
            "texModMask0": 0x8,
            "texModMask1": 0,
            "texModSequence0": 0x3,
            "texModSequence1": 0,
            "texModWaveFuncs0": 0,
            "texModWaveFuncs1": 0,
            "fogAdjust": 0,
        },
        "streamMaterialGate": {
            "multitextureEnabled": 1,
            "multitextureAccepted": 2,
            "multitextureRejected": 0,
            "depthFragmentEnabled": 1,
            "depthFragmentAccepted": 1,
            "depthFragmentRejected": 0,
            "texModEnabled": 1,
            "texModAccepted": 2,
            "texModRejected": 0,
            "environmentEnabled": 1,
            "environmentAccepted": 1,
            "environmentRejected": 0,
            "dynamicLightEnabled": 0,
            "dynamicLightAccepted": 0,
            "dynamicLightRejected": 0,
            "screenMapEnabled": 0,
            "screenMapAccepted": 0,
            "screenMapRejected": 0,
            "videoMapEnabled": 0,
            "videoMapAccepted": 0,
            "videoMapRejected": 0,
        },
        "colorFrame": {
            "samples": 1,
            "latest": {
                "frame": 1,
                "backend": "sdr-srgb",
                "space": "scene-linear",
                "transfer": "sdr-srgb",
                "exposure": 1.0,
                "paperWhiteNits": 203.0,
                "maxOutputNits": 203.0,
                "srgbDecode": True,
                "framebufferSrgb": False,
                "internalFormat": "0x881a",
                "textureFormat": "0x1908",
                "textureType": "0x140b",
                "sceneTargetFloat": True,
                "shaderSrgbEncode": True,
                "contractValid": True,
            },
        },
    }


def stress_material_diagnostics_metrics() -> dict[str, object]:
    metrics = copy.deepcopy(color_diagnostics_metrics())
    material_flags = (
        0x0C23
        | glx_runtime_sweep.GLX_MATERIAL_STAGE_FLAGS["animatedImage"]
        | glx_runtime_sweep.GLX_MATERIAL_STAGE_FLAGS["screenMap"]
        | glx_runtime_sweep.GLX_MATERIAL_STAGE_FLAGS["videoMap"]
    )
    metrics["streamDraw"].update(  # type: ignore[index, union-attr]
        {
            "screenMaps": 1,
            "videoMaps": 1,
            "beams": 3,
            "shadows": 2,
        }
    )
    metrics["streamCategory"].update(  # type: ignore[index, union-attr]
        {
            "particleDraws": 2,
            "particleAttempts": 2,
            "particleObserved": 1,
            "polyDraws": 2,
            "polyAttempts": 2,
            "polyObserved": 1,
            "markDraws": 1,
            "markAttempts": 1,
            "markObserved": 1,
            "beamDraws": 3,
            "beamAttempts": 3,
            "beamObserved": 1,
        }
    )
    metrics["materialParameters"].update(  # type: ignore[index, union-attr]
        {
            "features": material_flags,
            "flags": material_flags,
        }
    )
    metrics["materialLastKey"].update(  # type: ignore[index, union-attr]
        {
            "flags": material_flags,
        }
    )
    metrics["materialLanguage"].update(  # type: ignore[index, union-attr]
        {
            "flags": material_flags,
        }
    )
    metrics["materialStageFlags"] = {
        "multitexture": 2,
        "depthFragment": 1,
        "blend": 1,
        "alphaTest": 1,
        "depthWrite": 1,
        "lightmap": 2,
        "animatedImage": 1,
        "videoMap": 1,
        "screenMap": 1,
        "dynamicLightMap": 0,
        "texMod": 2,
        "environment": 1,
        "st0": 2,
        "st1": 1,
    }
    metrics["streamMaterialGate"].update(  # type: ignore[index, union-attr]
        {
            "screenMapEnabled": 1,
            "screenMapAccepted": 1,
            "screenMapRejected": 0,
            "videoMapEnabled": 1,
            "videoMapAccepted": 1,
            "videoMapRejected": 0,
        }
    )
    return metrics


def color_contracts() -> dict[str, object]:
    return glx_runtime_sweep.color_contract_manifest()


def image_evidence_manifest() -> dict[str, object]:
    return {
        "version": glx_runtime_sweep.GLX_IMAGE_EVIDENCE_VERSION,
        "requiredSidecars": list(glx_runtime_sweep.GLX_IMAGE_EVIDENCE_SIDECARS),
        "shaderReferenceRamps": [
            {
                "rowId": str(row["id"]),
                "path": f"image-evidence/{row['id']}.reference-ramp.png",
                "width": glx_runtime_sweep.GLX_SHADER_REFERENCE_RAMP_WIDTH,
                "height": glx_runtime_sweep.GLX_SHADER_REFERENCE_RAMP_HEIGHT,
                "rampRows": list(glx_runtime_sweep.GLX_SHADER_REFERENCE_RAMP_ROWS),
                "histogram": screenshot_histogram(),
                "histogramPath": f"image-evidence/{row['id']}.histogram.json",
                "falseColorPath": f"image-evidence/{row['id']}.luma-falsecolor.png",
                "exposureFalseColorPath": f"image-evidence/{row['id']}.exposure-falsecolor.png",
            }
            for row in glx_runtime_sweep.GLX_COLOR_SWEEP_MATRIX
        ],
    }


def color_diagnostics_metrics_for_row(row: dict[str, object]) -> dict[str, object]:
    metrics = color_diagnostics_metrics()
    expect = row.get("expect", {})
    if isinstance(expect, dict):
        metrics["colorPipeline"]["space"] = expect.get("space", "scene-linear")  # type: ignore[index]
        metrics["colorPipeline"]["transfer"] = expect.get("transfer", "sdr-srgb")  # type: ignore[index]
        metrics["colorPipeline"]["toneMap"] = expect.get("toneMap", "aces-fitted")  # type: ignore[index]
        metrics["colorPipeline"]["exposure"] = expect.get("exposure", 1.0)  # type: ignore[index]
        metrics["colorAudit"]["targetFloat"] = expect.get("sceneTargetFloat", 1)  # type: ignore[index]
        metrics["colorAudit"]["finalEncode"] = expect.get("finalEncode", "shader-srgb")  # type: ignore[index]
        metrics["colorAudit"]["contract"] = expect.get("contract", 1)  # type: ignore[index]
        metrics["colorAudit"]["framebufferSrgb"] = expect.get("framebufferSrgb", 0)  # type: ignore[index]
        metrics["colorAudit"]["srgbDecode"] = expect.get("srgbDecode", 1)  # type: ignore[index]
        metrics["colorAudit"]["srgbRequested"] = expect.get("srgbRequested", 1)  # type: ignore[index]
        metrics["outputBackend"]["request"] = expect.get("outputRequest", "sdr-srgb")  # type: ignore[index]
        if "internalFormat" in expect:
            metrics["targetFormat"]["internalFormat"] = int(str(expect["internalFormat"]), 16)  # type: ignore[index]
        if "textureFormat" in expect:
            metrics["targetFormat"]["textureFormat"] = int(str(expect["textureFormat"]), 16)  # type: ignore[index]
        if "textureType" in expect:
            metrics["targetFormat"]["textureType"] = int(str(expect["textureType"]), 16)  # type: ignore[index]
        color_frame = metrics["colorFrame"]["latest"]  # type: ignore[index]
        color_frame["space"] = metrics["colorPipeline"]["space"]  # type: ignore[index]
        color_frame["transfer"] = metrics["colorPipeline"]["transfer"]  # type: ignore[index]
        color_frame["exposure"] = metrics["colorPipeline"]["exposure"]  # type: ignore[index]
        color_frame["sceneTargetFloat"] = bool(metrics["colorAudit"]["targetFloat"])  # type: ignore[index]
        color_frame["shaderSrgbEncode"] = metrics["colorAudit"]["finalEncode"] == "shader-srgb"  # type: ignore[index]
        color_frame["contractValid"] = bool(metrics["colorAudit"]["contract"])  # type: ignore[index]
        color_frame["framebufferSrgb"] = bool(metrics["colorAudit"]["framebufferSrgb"])  # type: ignore[index]
        color_frame["srgbDecode"] = bool(metrics["colorAudit"]["srgbDecode"])  # type: ignore[index]
        color_frame["internalFormat"] = f"0x{int(metrics['targetFormat']['internalFormat']):04x}"  # type: ignore[index]
        color_frame["textureFormat"] = f"0x{int(metrics['targetFormat']['textureFormat']):04x}"  # type: ignore[index]
        color_frame["textureType"] = f"0x{int(metrics['targetFormat']['textureType']):04x}"  # type: ignore[index]
    return metrics


def locked_performance_sample(row: dict[str, object] | None = None) -> dict[str, object]:
    latest = locked_pass_schedule_latest()
    metrics = color_diagnostics_metrics_for_row(row) if row is not None else color_diagnostics_metrics()
    color_pipeline = metrics["colorPipeline"]
    color_audit = metrics["colorAudit"]
    target_format = metrics["targetFormat"]
    post_controls = metrics["postprocessControls"]
    post_frames = metrics["postprocessFrames"]
    post_features = metrics["postprocessFrameFeatures"]
    color_frame = metrics["colorFrame"]["latest"]  # type: ignore[index]
    latest.update(
        {
            "colorSpace": color_pipeline["space"],
            "outputTransfer": color_pipeline["transfer"],
            "toneMap": color_pipeline["toneMap"],
            "toneMapExposure": 1.0,
            "paperWhiteNits": 203.0,
            "maxOutputNits": color_pipeline["maxOutput"],
            "colorSrgbDecode": color_audit["srgbDecode"],
            "colorSrgbRequested": color_audit["srgbRequested"],
            "colorFramebufferSrgb": color_audit["framebufferSrgb"],
            "colorSceneTargetFloat": color_audit["targetFloat"],
            "colorFinalEncode": color_audit["finalEncode"],
            "colorOutputContract": color_audit["contract"],
            "captureColorSpace": color_audit["capture"],
            "capturePolicyRequest": color_audit["captureRequest"],
            "captureHdrAware": color_audit["captureHdrAware"],
            "capturePolicySupported": color_audit["captureSupported"],
            "outputBackendRequest": metrics["outputBackend"]["request"],  # type: ignore[index]
            "outputBackendSelected": "sdr-srgb",
            "textureAuditSrgb": 4,
            "textureAuditSrgbDecode": 4,
            "textureAuditMissingSrgbDecode": 0,
            "textureAuditUnexpectedDecode": 0,
            "targetInternalFormat": target_format["internalFormat"],
            "targetTextureFormat": target_format["textureFormat"],
            "targetTextureType": target_format["textureType"],
            "targetRenderWidth": target_format["renderWidth"],
            "targetRenderHeight": target_format["renderHeight"],
            "targetCaptureWidth": target_format["captureWidth"],
            "targetCaptureHeight": target_format["captureHeight"],
            "targetWindowWidth": target_format["windowWidth"],
            "targetWindowHeight": target_format["windowHeight"],
            "fbo": "ready",
            "postprocessRenderScaleMode": post_controls["renderScale"],
            "postprocessGreyscale": post_controls["greyscale"],
            "postprocessWindowAdjusted": post_controls["windowAdjusted"],
            "postprocessFrames": post_frames["frames"],
            "postprocessScreenshots": post_frames["screenshots"],
            "postprocessMinimizedOutput": post_frames["minimizedOutput"],
            "postprocessFeatureRenderScale": post_features["renderScale"],
            "postprocessFeatureGreyscale": post_features["greyscale"],
            "postprocessFeatureWindowAdjusted": post_features["windowAdjusted"],
            "postprocessFeatureMinimized": post_features["minimized"],
            "postOutputMode": "glx-owned",
            "postOutputPostNodes": 2,
            "postOutputOutputs": 1,
            "postOutputExecutableNodes": 2,
            "postOutputExecutableOutputs": 1,
            "postOutputLegacyFallback": 0,
            "postOutputPostHash": 0x10203,
            "postOutputOutputHash": 0x40506,
            "postOutputPlanHash": 0x70809,
            "postOutputFallbackMask": 0,
            "colorFrameSamples": 1,
            "colorFrameBackend": color_frame["backend"],
            "colorFrameSpace": color_frame["space"],
            "colorFrameTransfer": color_frame["transfer"],
            "colorFrameExposure": color_frame["exposure"],
            "colorFramePaperWhiteNits": color_frame["paperWhiteNits"],
            "colorFrameMaxOutputNits": color_frame["maxOutputNits"],
            "colorFrameSrgbDecode": 1 if color_frame["srgbDecode"] else 0,
            "colorFrameFramebufferSrgb": 1 if color_frame["framebufferSrgb"] else 0,
            "colorFrameInternalFormat": color_frame["internalFormat"],
            "colorFrameTextureFormat": color_frame["textureFormat"],
            "colorFrameTextureType": color_frame["textureType"],
            "colorFrameSceneTargetFloat": 1 if color_frame["sceneTargetFloat"] else 0,
            "colorFrameShaderSrgbEncode": 1 if color_frame["shaderSrgbEncode"] else 0,
            "colorFrameContractValid": 1 if color_frame["contractValid"] else 0,
            "staticDrawAttempts": 4,
            "staticDrawIndexes": 2048,
            "staticDrawFallbacks": 0,
            "staticDrawPacketFull": 3,
            "staticDrawPacketPartial": 1,
            "staticDrawPacketMisses": 0,
            "staticQueuePacketMisses": 0,
            "staticPacketLookupMisses": 0,
            "staticMdiErrors": 0,
            "draws": 3,
            "streamDrawAttempts": 3,
            "streamDrawIndexes": 1024,
            "streamDrawFog": 2,
            "streamDrawMultitexture": 2,
            "streamDrawDepthFragment": 1,
            "streamDrawTexMods": 2,
            "streamDrawEnvironment": 1,
            "streamDrawDynamicLights": 0,
            "streamDrawScreenMaps": 0,
            "streamDrawVideoMaps": 0,
            "streamDrawShadows": 2,
            "streamDrawBeams": 0,
            "streamDrawPostProcess": 0,
            "streamDrawFallbacks": 0,
            "streamDrawSkips": 0,
            "streamCategoryEntityDraws": 2,
            "streamCategoryEntityAttempts": 2,
            "streamCategoryParticleDraws": 0,
            "streamCategoryParticleAttempts": 0,
            "streamCategoryPolyDraws": 0,
            "streamCategoryPolyAttempts": 0,
            "streamCategoryMarkDraws": 0,
            "streamCategoryMarkAttempts": 0,
            "streamCategoryWeaponDraws": 1,
            "streamCategoryWeaponAttempts": 1,
            "streamCategoryUiDraws": 0,
            "streamCategoryUiAttempts": 0,
            "streamCategoryBeamDraws": 0,
            "streamCategoryBeamAttempts": 0,
            "streamCategorySpecialDraws": 0,
            "streamCategorySpecialAttempts": 0,
            "materialRenderer": "enabled",
            "materialReady": "ready",
            "materialPrograms": 3,
            "materialBinds": 4,
            "materialBindAttempts": 4,
            "materialSwitches": 2,
            "materialCacheMisses": 1,
            "materialCompileFailures": 0,
            "materialLinkFailures": 0,
            "materialPrecacheFailures": 0,
            "materialBindFailures": 0,
            "materialParameterBlocks": 4,
            "materialParameterHash": 0x00F00D,
            "materialInvalidParameterBlocks": 0,
            "materialParameterFeatures": 0x0C23,
            "materialParameterFlags": 0x0C23,
            "materialParameterState": 0x30,
            "materialParameterTcGen0": 3,
            "materialParameterTcGen1": 2,
        }
    )
    return {
        "found": True,
        "sampleCount": 1,
        "latest": latest,
        "max": {},
    }


def color_sweep_runs(gate: str) -> list[dict[str, object]]:
    runs: list[dict[str, object]] = []
    for row in glx_runtime_sweep.GLX_COLOR_SWEEP_MATRIX:
        row = dict(row)
        row_id = str(row["id"])
        runs.append(
            {
                "type": "color-sweep",
                "status": "passed",
                "renderer": "glx",
                "map": "q3dm1",
                "colorSweepRow": row,
                "screenshots": [
                    {
                        "name": f"color-{row_id}",
                        "found": True,
                        "baselineKey": f"glx-color-{row_id}-q3dm1",
                        "baselineStatus": "passed" if gate == "rc-proof" else "not-compared",
                        "comparison": {"status": "passed"} if gate == "rc-proof" else {},
                        "histogram": screenshot_histogram(),
                        "capturePolicy": sdr_capture_policy(),
                        "falseColor": {"status": "passed"},
                        "exposureFalseColor": {"status": "passed"},
                    }
                ],
                "diagnostics": {
                    "found": True,
                    "failures": [],
                    "metrics": color_diagnostics_metrics_for_row(row),
                },
                "performance": locked_performance_sample(row),
            }
        )
    return runs


def proof_corpus_for_gate(gate: str) -> dict[str, object]:
    requirements = glx_runtime_sweep.RC_GATE_PRESETS[gate]["requirements"]
    return glx_runtime_sweep.proof_corpus_manifest(
        glx_runtime_sweep.GLX_GATE_CORPUS_SCENES[gate],
        requirements.get("required_corpus_tags", ()),
        requirements.get("required_parity_suites", ()),
    )


def release_proof_manifest(gate: str, platform_id: str) -> dict[str, object]:
    maps = glx_runtime_sweep.corpus_targets(
        glx_runtime_sweep.GLX_GATE_CORPUS_SCENES[gate],
        "map",
    )
    demos = glx_runtime_sweep.corpus_targets(
        glx_runtime_sweep.GLX_GATE_CORPUS_SCENES[gate],
        "demo",
    )
    switch_sequence = ["opengl", "glx", "opengl", "glx"]
    diagnostic_metrics = (
        stress_material_diagnostics_metrics()
        if gate == "rc-stress"
        else color_diagnostics_metrics()
    )
    switch_screenshots = [
        {
            "name": f"{gate}-{platform_id}-map{map_index}-step{switch_index}-{renderer}",
            "found": True,
            "renderer": renderer,
            "map": map_name,
            "mapIndex": map_index,
            "round": 1,
            "switchStep": switch_index,
            "baselineKey": (
                f"{gate}-{platform_id}-{map_name}-round1-step{switch_index}-{renderer}"
            ),
            "baselineStatus": "passed" if gate == "rc-proof" else "not-compared",
            "comparison": {"status": "passed"} if gate == "rc-proof" else {},
            "histogram": screenshot_histogram(),
            "capturePolicy": sdr_capture_policy(),
            "falseColor": {"status": "passed"},
            "exposureFalseColor": {"status": "passed"},
        }
        for map_index, map_name in enumerate(maps, start=1)
        for switch_index, renderer in enumerate(switch_sequence, start=1)
    ]
    manifest = {
        "runId": f"{platform_id}-{gate}",
        "createdUtc": "2026-05-10T12:00:00+00:00",
        "gate": gate,
        "dryRun": False,
        "proofPlatform": platform_id,
        "maps": maps,
        "demos": demos,
        "renderers": ["opengl", "glx"],
        "switchSequence": switch_sequence,
        "switchRounds": 1,
        "proofCorpus": proof_corpus_for_gate(gate),
        "colorContracts": color_contracts(),
        "imageEvidence": image_evidence_manifest(),
        "performanceFailures": [],
        "runs": [
            {
                "type": "switch-screenshots",
                "status": "passed",
                "restartMode": "fast",
                "vidRestartEquivalent": True,
                "vidRestartPath": "CL_Vid_Restart(REF_KEEP_WINDOW)",
                "screenshots": switch_screenshots,
                "diagnostics": {
                    "found": True,
                    "failures": [],
                    "metrics": diagnostic_metrics,
                },
                "performance": locked_performance_sample(),
            },
        ],
    }
    if glx_runtime_sweep.RC_GATE_PRESETS[gate]["requirements"].get("require_dlight_shadow_scenes"):
        dlight_scenes = glx_runtime_sweep.dlight_shadow_evidence_scenes()
        manifest["runs"].append(
            {
                "type": "dlight-shadow-scenes",
                "status": "passed",
                "renderer": "glx",
                "maps": sorted({str(scene["map"]) for scene in dlight_scenes}),
                "scenes": dlight_scenes,
                "screenshots": [
                    {
                        "name": f"{gate}-{platform_id}-dlight-{scene['id']}",
                        "found": True,
                        "renderer": "glx",
                        "map": scene["map"],
                        "mapIndex": scene_index,
                        "baselineKey": (
                            f"{gate}-{platform_id}-dlight-shadows-{scene['id']}-glx"
                        ),
                        "baselineStatus": "not-compared",
                        "histogram": screenshot_histogram(),
                        "capturePolicy": sdr_capture_policy(),
                        "falseColor": {"status": "passed"},
                        "exposureFalseColor": {"status": "passed"},
                        "scene": scene["id"],
                        "evidenceCategories": list(scene["categories"]),
                        "shadowScene": True,
                    }
                    for scene_index, scene in enumerate(dlight_scenes, start=1)
                ],
                "dlightShadow": {
                    "found": True,
                    "sampleCount": 1,
                    "latest": {"planned": 2, "renderLights": 2},
                    "max": {"planned": 2, "renderLights": 2},
                    "scenes": {
                        str(scene["id"]): {
                            "sampleCount": 1,
                            "latest": {"planned": 2, "renderLights": 2},
                            "max": {"planned": 2, "renderLights": 2},
                        }
                        for scene in dlight_scenes
                    },
                },
            }
        )
    if glx_runtime_sweep.RC_GATE_PRESETS[gate]["requirements"].get("require_glx_color_sweep"):
        manifest["runs"].extend(color_sweep_runs(gate))
    for demo in manifest["demos"]:
        manifest["runs"].extend(
            [
                {
                    "type": "timedemo",
                    "status": "passed",
                    "renderer": "opengl",
                    "demo": demo,
                    "timedemoMetrics": {"fps": 100.0},
                },
                {
                    "type": "timedemo",
                    "status": "passed",
                    "renderer": "glx",
                    "demo": demo,
                    "timedemoMetrics": {"fps": 95.0},
                },
            ]
        )
    if gate == "rc-proof":
        manifest.update(
            {
                "screenshotBaselineDir": "proof/screenshots",
                "performanceBaselinePath": "proof/performance-baseline.json",
                "performanceBaselineStatus": "compared",
                "performanceComparisons": [{"metric": "draws", "status": "passed"}],
                "performanceAggregate": {"sampleCount": 1, "latest": {}, "max": {}},
            }
        )
    requirements = glx_runtime_sweep.RC_GATE_PRESETS[gate]["requirements"]
    manifest["rendererSwitchEvidence"] = glx_runtime_sweep.renderer_switch_lifecycle_evidence(manifest)
    if requirements.get("require_world_proof"):
        manifest["worldProofEvidence"] = glx_runtime_sweep.world_proof_evidence(
            manifest,
            requirements,
        )
    if requirements.get("require_material_proof"):
        manifest["materialProofEvidence"] = glx_runtime_sweep.material_proof_evidence(
            manifest,
            requirements,
        )
    if requirements.get("require_dynamic_proof"):
        manifest["dynamicProofEvidence"] = glx_runtime_sweep.dynamic_proof_evidence(
            manifest,
            requirements,
        )
    if requirements.get("require_post_proof"):
        manifest["postProofEvidence"] = glx_runtime_sweep.post_proof_evidence(
            manifest,
            requirements,
        )
    return manifest


def ownership_proof_manifest(
    platform_id: str,
    calls: int = 0,
    items: int = 0,
    tier: str = "GL3X",
    modern_tier_diagnostics: bool = True,
    post_mode: str | None = "glx-owned",
    post_nodes: int = 2,
    outputs: int = 1,
    executable_nodes: int | None = 2,
    executable_outputs: int | None = 1,
    legacy_fallback: int = 0,
    post_hash: int = 1,
    output_hash: int = 1,
) -> dict[str, object]:
    metrics: dict[str, object] = {
        "ownership": {
            "calls": calls,
            "items": items,
        },
        "productTier": {
            "tier": tier,
        },
        "postShaderDirectFinal": {
            "execute": 1,
            "eligible": 1,
            "bound": 1,
            "reject": 0,
            "candidates": 2,
            "eligibleFrames": 2,
            "attempts": 2,
            "binds": 2,
            "fallbacks": 0,
            "rejects": 0,
        },
    }
    if modern_tier_diagnostics and tier == "GL3X":
        metrics["gl3xExecutor"] = {
            "active": 1,
            "fboPostProcess": 1,
        }
        metrics["gl3xSupport"] = {
            "modernPostChain": 1,
            "sceneLinearOutput": 1,
        }
    elif modern_tier_diagnostics and tier == "GL41":
        metrics["gl41Executor"] = {
            "active": 1,
            "fboPostProcess": 1,
        }
        metrics["gl41Support"] = {
            "modernPostChain": 1,
            "sceneLinearOutput": 1,
        }
    elif modern_tier_diagnostics and tier == "GL46":
        metrics["gl46Executor"] = {
            "active": 1,
        }
        metrics["gl46Support"] = {
            "modernPostChain": 1,
            "sceneLinearOutput": 1,
        }
    if post_mode is not None:
        metrics["postOutputOwnership"] = {
            "mode": post_mode,
            "postNodes": post_nodes,
            "outputs": outputs,
            "legacyFallback": legacy_fallback,
            "postHash": post_hash,
            "outputHash": output_hash,
            "planHash": 0x090A0B0C,
            "fallbackMask": 0,
        }
        if executable_nodes is not None:
            metrics["postOutputOwnership"]["executableNodes"] = executable_nodes  # type: ignore[index]
        if executable_outputs is not None:
            metrics["postOutputOwnership"]["executableOutputs"] = executable_outputs  # type: ignore[index]

    manifest = {
        "runId": f"{platform_id}-glx-ownership",
        "createdUtc": "2026-05-10T12:30:00+00:00",
        "gate": "",
        "profile": "glx-ownership",
        "dryRun": False,
        "proofPlatform": platform_id,
        "maps": ["q3dm1", "q3dm17"],
        "demos": [],
        "renderers": ["opengl", "glx"],
        "performanceFailures": [],
        "runs": [
            {
                "type": "switch-screenshots",
                "status": "passed",
                "screenshots": [
                    {
                        "name": "ownership-shot",
                        "found": True,
                        "histogram": screenshot_histogram(),
                    },
                ],
                "diagnostics": {
                    "found": True,
                    "failures": [],
                    "metrics": metrics,
                },
            },
        ],
    }
    manifest["ownershipProofEvidence"] = glx_runtime_sweep.ownership_proof_evidence(manifest)
    return manifest


def rollback_package_metadata(
    artifact_dir: str = "fnquake3-legacy-opengl",
    platforms: list[str] | None = None,
    legacy_renderers: list[str] | None = None,
    required_artifacts: dict[str, bool] | None = None,
    triggers: list[str] | None = None,
) -> dict[str, object]:
    return {
        "version": glx_promotion.PROMOTION_ROLLBACK_METADATA_VERSION,
        "status": "reviewed",
        "promotedRenderer": "glx",
        "aliasRenderer": "opengl",
        "migrationInstructions": "Use cl_renderer opengl for the promoted GLx alias.",
        "rollbackInstructions": "Use the rollback package, set cl_renderer opengl, and run vid_restart.",
        "requiredArtifacts": required_artifacts
        if required_artifacts is not None
        else {
            "proofCorpus": True,
            "promotionReport": True,
            "releaseProofSummary": True,
            "checksums": True,
        },
        "rollbackTriggers": triggers
        if triggers is not None
        else [
            "unexplained demo playback regression",
            "unexplained screenshot parity regression",
            "driver startup or presentation regression",
            "confirmed performance regression",
        ],
        "rollbackPackages": [
            {
                "id": "fnquake3-legacy-opengl",
                "type": "rollback",
                "artifactDir": artifact_dir,
                "platforms": platforms
                if platforms is not None
                else list(glx_runtime_sweep.GLX_BLOCKING_RELEASE_PLATFORMS),
                "legacyRenderers": legacy_renderers
                if legacy_renderers is not None
                else ["opengl", "opengl2"],
                "selectionInstructions": "Select the legacy opengl renderer from this package.",
            }
        ],
    }


def parse_glx_feature_matrix() -> list[dict[str, str]]:
    text = FEATURE_MATRIX_PATH.read_text(encoding="utf-8")
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line.startswith("| "):
            continue
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if len(cells) != 6 or cells[0] in {"ID", "---"} or set(cells[0]) <= {"-"}:
            continue
        rows.append(
            {
                "id": cells[0],
                "category": cells[1],
                "feature": cells[2],
                "status": cells[3],
                "evidence": cells[4],
                "closure": cells[5],
            }
        )
    return rows


class GlxArchitecturalCutoverPlanTests(unittest.TestCase):
    @staticmethod
    def _plan_section(start: str, end: str) -> str:
        plan = (ROOT / "docs" / "plans" / "glx-review-9-5-26.md").read_text(encoding="utf-8")
        return plan.split(start, 1)[1].split(end, 1)[0]

    def assert_tasks_are_implemented(self, section: str, tasks: tuple[str, ...]) -> None:
        for task in tasks:
            match = re.search(rf"\*\*{task} .*?(?=\n\*\*Task [A-Z]|$)", section, re.DOTALL)
            self.assertIsNotNone(match, task)
            self.assertIn("**Implemented by:**", match.group(0))

    def test_architectural_cutover_tasks_are_marked_implemented(self) -> None:
        section = self._plan_section("### Architectural cutover tasks", "### Tiered execution tasks")

        self.assertIn("All architectural cutover tasks are now implemented.", section)
        self.assert_tasks_are_implemented(section, ("Task A", "Task B", "Task C", "Task D"))

    def test_tiered_execution_tasks_are_marked_implemented(self) -> None:
        section = self._plan_section("### Tiered execution tasks", "### Material, map-scale, and feature-closure tasks")

        self.assertIn("All tiered execution tasks are now implemented.", section)
        self.assert_tasks_are_implemented(section, ("Task E", "Task F", "Task G", "Task H", "Task I", "Task J"))

    def test_material_map_scale_tasks_are_marked_implemented(self) -> None:
        section = self._plan_section("### Material, map-scale, and feature-closure tasks", "### HDR")

        self.assertIn("All material, map-scale, and feature-closure tasks are now implemented.", section)
        self.assert_tasks_are_implemented(section, ("Task K", "Task L", "Task M", "Task N", "Task O"))

    def test_task_k_is_marked_implemented(self) -> None:
        section = self._plan_section("### Material, map-scale, and feature-closure tasks", "**Task L")

        self.assert_tasks_are_implemented(section, ("Task K",))

    def test_task_l_is_marked_implemented(self) -> None:
        section = self._plan_section("### Material, map-scale, and feature-closure tasks", "**Task M")

        self.assert_tasks_are_implemented(section, ("Task L",))

    def test_task_m_is_marked_implemented(self) -> None:
        section = self._plan_section("### Material, map-scale, and feature-closure tasks", "**Task N")

        self.assert_tasks_are_implemented(section, ("Task M",))

    def test_task_n_is_marked_implemented(self) -> None:
        section = self._plan_section("### Material, map-scale, and feature-closure tasks", "**Task O")

        self.assert_tasks_are_implemented(section, ("Task N",))

    def test_task_o_is_marked_implemented(self) -> None:
        section = self._plan_section("### Material, map-scale, and feature-closure tasks", "### HDR")

        self.assert_tasks_are_implemented(section, ("Task O",))

    def test_task_p_is_marked_implemented(self) -> None:
        section = self._plan_section("### HDR, color grading, and output tasks", "**Task Q")

        self.assert_tasks_are_implemented(section, ("Task P",))

    def test_task_q_is_marked_implemented(self) -> None:
        section = self._plan_section("### HDR, color grading, and output tasks", "**Task R")

        self.assert_tasks_are_implemented(section, ("Task Q",))

    def test_task_r_is_marked_implemented(self) -> None:
        section = self._plan_section("### HDR, color grading, and output tasks", "**Task S")

        self.assert_tasks_are_implemented(section, ("Task R",))

    def test_task_s_is_marked_implemented(self) -> None:
        section = self._plan_section("### HDR, color grading, and output tasks", "### Performance, testing, and release tasks")

        self.assert_tasks_are_implemented(section, ("Task S",))

    def test_task_t_is_marked_implemented(self) -> None:
        section = self._plan_section("### Performance, testing, and release tasks", "**Task U")

        self.assert_tasks_are_implemented(section, ("Task T",))

    def test_task_u_is_marked_implemented(self) -> None:
        section = self._plan_section("### Performance, testing, and release tasks", "**Task V")

        self.assert_tasks_are_implemented(section, ("Task U",))

    def test_task_v_is_marked_implemented(self) -> None:
        section = self._plan_section("### Performance, testing, and release tasks", "**Task W")

        self.assert_tasks_are_implemented(section, ("Task V",))

    def test_task_w_is_marked_implemented(self) -> None:
        section = self._plan_section("### Performance, testing, and release tasks", "**Task X")

        self.assert_tasks_are_implemented(section, ("Task W",))

    def test_task_x_is_marked_implemented(self) -> None:
        section = self._plan_section("### Performance, testing, and release tasks", "## Release gates")

        self.assert_tasks_are_implemented(section, ("Task X",))

    def test_feature_closure_matrix_has_zero_ambiguous_rows(self) -> None:
        rows = parse_glx_feature_matrix()
        self.assertGreaterEqual(len(rows), 40)

        seen: set[str] = set()
        statuses: set[str] = set()
        for row in rows:
            self.assertNotIn(row["id"], seen)
            seen.add(row["id"])
            self.assertIn(row["status"], FEATURE_MATRIX_ALLOWED_STATUSES, row)
            self.assertTrue(row["category"], row)
            self.assertTrue(row["feature"], row)
            self.assertTrue(row["evidence"], row)
            self.assertTrue(row["closure"], row)
            self.assertNotRegex(row["status"], r"(?i)\b(tbd|unknown|unclear|maybe|n/a)\b")
            self.assertNotRegex(row["evidence"], r"(?i)\b(tbd|unknown|unclear|maybe|n/a)\b")
            self.assertNotRegex(row["closure"], r"(?i)\b(tbd|unknown|unclear|maybe|n/a)\b")
            statuses.add(row["status"])

        self.assertEqual(statuses, FEATURE_MATRIX_ALLOWED_STATUSES)
        self.assertTrue(FEATURE_MATRIX_REQUIRED_IDS.issubset(seen))


class GlxRuntimeSweepExecutableTests(unittest.TestCase):
    def test_default_executable_candidates_use_unified_client_names(self) -> None:
        names = glx_runtime_sweep.candidate_exe_names()

        self.assertTrue(any(name.startswith("fnquake3") for name in names))
        self.assertFalse(any(".glx" in name for name in names))
        self.assertFalse(any(".opengl" in name for name in names))
        self.assertFalse(any(".vulkan" in name for name in names))

    def test_launch_args_enable_engine_logfile_by_default(self) -> None:
        command = glx_runtime_sweep.base_launch_args(
            Path("fnquake3.exe"),
            Path("base"),
            Path("home"),
            "",
            "glx",
            "sweep.cfg",
            {},
        )

        logfile_index = command.index("logfile")
        self.assertEqual(command[logfile_index + 1], "2")
        developer_index = command.index("developer")
        self.assertEqual(command[developer_index + 1], "1")

        command = glx_runtime_sweep.base_launch_args(
            Path("fnquake3.exe"),
            Path("base"),
            Path("home"),
            "",
            "glx",
            "sweep.cfg",
            {"developer": "0", "logfile": "4"},
        )

        self.assertEqual(command.count("logfile"), 1)
        logfile_index = command.index("logfile")
        self.assertEqual(command[logfile_index + 1], "4")
        self.assertEqual(command.count("developer"), 1)
        developer_index = command.index("developer")
        self.assertEqual(command[developer_index + 1], "0")

    def test_run_engine_preserves_qconsole_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            engine_log = root / "home" / "baseq3" / "qconsole.log"
            artifact_log = root / "artifact.log"
            script = (
                "from pathlib import Path\n"
                "import sys\n"
                "path = Path(sys.argv[1])\n"
                "path.parent.mkdir(parents=True, exist_ok=True)\n"
                "path.write_text('engine color metadata\\n', encoding='utf-8')\n"
                "print('stdout metadata')\n"
            )

            result = glx_runtime_sweep.run_engine(
                [sys.executable, "-c", script, str(engine_log)],
                root,
                10.0,
                artifact_log,
                False,
                engine_log,
            )

            text = artifact_log.read_text(encoding="utf-8")
            self.assertEqual(result["status"], "passed")
            self.assertIn("stdout metadata", text)
            self.assertIn("engine color metadata", text)

    def test_default_executable_resolution_ignores_renderer_wrappers(self) -> None:
        old_output = glx_runtime_sweep.DEFAULT_OUTPUT

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            names = glx_runtime_sweep.candidate_exe_names()
            unified_name = names[0]
            stale_names = (
                ["fnquake3.glx.x64.exe", "fnquake3.opengl.x64.exe"]
                if glx_runtime_sweep.os.name == "nt"
                else ["fnquake3.glx", "fnquake3.opengl"]
            )

            glx_runtime_sweep.DEFAULT_OUTPUT = root
            try:
                for stale_name in stale_names:
                    (root / stale_name).touch()
                with self.assertRaises(FileNotFoundError):
                    glx_runtime_sweep.resolve_exe(None)

                (root / unified_name).touch()
                self.assertEqual(
                    glx_runtime_sweep.resolve_exe(None),
                    (root / unified_name).resolve(),
                )
            finally:
                glx_runtime_sweep.DEFAULT_OUTPUT = old_output

    def test_color_sweep_dry_run_plans_all_p0_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(
                [
                    sys.executable,
                    str(SWEEP_PATH),
                    "--dry-run",
                    "--exe",
                    str(root / "fnquake3.exe"),
                    "--output-dir",
                    str(root / "sweeps"),
                    "--profile",
                    "glx-color",
                    "--renderers",
                    "glx",
                    "--switch-sequence",
                    "glx",
                    "--maps",
                    "q3dm1",
                    "--demos",
                    "",
                    "--no-demo-sweep",
                    "--color-sweep",
                ],
                cwd=str(ROOT),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
            )
            manifest_path = next((root / "sweeps").rglob("manifest.json"))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            color_runs = [
                run for run in manifest["runs"] if run.get("type") == "color-sweep"
            ]

            self.assertEqual(len(color_runs), len(glx_runtime_sweep.GLX_COLOR_SWEEP_MATRIX))
            self.assertEqual(manifest["colorContracts"]["version"], glx_runtime_sweep.GLX_COLOR_CONTRACT_VERSION)
            self.assertEqual(manifest["imageEvidence"]["version"], glx_runtime_sweep.GLX_IMAGE_EVIDENCE_VERSION)
            self.assertEqual(
                len(manifest["imageEvidence"]["shaderReferenceRamps"]),
                len(glx_runtime_sweep.GLX_COLOR_SWEEP_MATRIX),
            )
            self.assertEqual(
                {run["colorSweepRow"]["id"] for run in color_runs},
                {row["id"] for row in glx_runtime_sweep.GLX_COLOR_SWEEP_MATRIX},
            )
            self.assertEqual(
                manifest["visualDossier"]["version"],
                glx_runtime_sweep.GLX_VISUAL_DOSSIER_VERSION,
            )
            switch_evidence = manifest["rendererSwitchEvidence"]
            self.assertEqual(
                switch_evidence["version"],
                glx_runtime_sweep.GLX_SWITCH_LIFECYCLE_VERSION,
            )
            self.assertEqual(switch_evidence["status"], "planned")
            self.assertEqual(switch_evidence["plannedTransitions"], 1)
            self.assertIn("renderer-switch-lifecycle", manifest["visualDossier"]["sections"])
            visual_dossier_path = Path(manifest["visualDossier"]["path"])
            self.assertTrue(visual_dossier_path.exists())
            visual_dossier = visual_dossier_path.read_text(encoding="utf-8")
            self.assertIn("Current Pipeline Flow", visual_dossier)
            self.assertIn("Target Pipeline Flow", visual_dossier)
            self.assertIn("Renderer Switch Lifecycle", visual_dossier)
            self.assertIn("Driver Tier Matrix", visual_dossier)
            self.assertIn("SDR/HDR Color Sweep Review", visual_dossier)
            self.assertTrue(
                any("+set r_srgbTextures 0" in run["commandLine"] for run in color_runs)
            )
            self.assertTrue(manifest["runtimeQpathToken"].startswith("gs"))
            for run in manifest["runs"]:
                self.assertLess(len(Path(run["config"]).name), glx_runtime_sweep.Q3_MAX_QPATH)
                self.assertIn("devmap q3dm1", Path(run["config"]).read_text(encoding="utf-8"))
                for shot in run.get("screenshots", []):
                    self.assertLess(len(shot["name"]), glx_runtime_sweep.Q3_MAX_QPATH)


class GlxRendererSourceCoverageTests(unittest.TestCase):
    def test_requested_glx_renderer_load_failure_is_fatal(self) -> None:
        client_source = (ROOT / "code" / "client" / "cl_main.cpp").read_text(encoding="utf-8")
        start = client_source.index("static void CL_InitRef")
        failure_start = client_source.index("if ( !rendererLib )", start)
        failure_end = client_source.index("rendererLib = Sys_LoadLibrary( ospath );", failure_start)
        load_failure_body = client_source[failure_start:failure_end]

        self.assertIn("CL_RendererLoadFailureIsFatal", client_source)
        self.assertIn('!Q_stricmp( rendererName, "glx" )', client_source)
        self.assertIn("requestedRenderer = cl_renderer->string", client_source)
        self.assertIn("CL_RendererLoadFailureIsFatal( requestedRenderer )", load_failure_body)
        self.assertIn("Com_Error( ERR_FATAL", load_failure_body)
        self.assertNotIn("OpenGL " + "fallback", load_failure_body)

    def test_depth_fragment_does_not_block_multitexture_collapse(self) -> None:
        shader_source = (ROOT / "code" / "renderer" / "tr_shader.c").read_text(encoding="utf-8")
        start = shader_source.index("static qboolean CollapseMultitexture")
        end = shader_source.index("#ifdef USE_PMLIGHT", start)
        collapse_body = shader_source[start:end]

        self.assertNotIn("st0->depthFragment", collapse_body)
        self.assertNotRegex(collapse_body, r"depthFragment[\s\S]{0,120}return\s+qfalse")

    def test_hdr_docs_and_cvars_use_scene_linear_semantics(self) -> None:
        display_doc = (ROOT / "docs" / "DISPLAY.md").read_text(encoding="utf-8")
        glx_doc = (ROOT / "docs" / "fnquake3" / "GLX_RENDERER.md").read_text(encoding="utf-8")
        renderer_init = (ROOT / "code" / "renderer" / "tr_init.c").read_text(encoding="utf-8")
        vulkan_init = (ROOT / "code" / "renderervk" / "tr_init.c").read_text(encoding="utf-8")
        glx_ir = (ROOT / "code" / "rendererglx" / "glx_render_ir.h").read_text(encoding="utf-8")

        self.assertIn("`r_hdr`: Selects the HDR-capable FBO render pipeline.", display_doc)
        self.assertIn("`r_hdrPrecision`", display_doc)
        self.assertIn("legacy tone mapping preserves Quake III display-referred lighting", glx_doc)
        self.assertNotIn("`r_hdr`: Controls framebuffer precision.", display_doc)
        self.assertNotIn("HDR precision mode", glx_doc)
        self.assertIn("Selects the HDR-capable FBO render pipeline", renderer_init)
        self.assertIn("Selects the scene-linear HDR render pipeline", vulkan_init)
        for source in (renderer_init, vulkan_init):
            self.assertIn("r_hdrPrecision", source)
            self.assertNotIn("Enables high dynamic range frame buffer texture format", source)
        self.assertIn("SceneColorSpace::SceneLinear", glx_ir)
        self.assertIn("ToneMapOperator::AcesFitted", glx_ir)
        self.assertIn("Aces = AcesFitted", glx_ir)

    def test_renderer2_auto_exposure_has_time_constant_mode_and_legacy_parity(self) -> None:
        source = (ROOT / "code" / "renderer2" / "tr_postprocess.c").read_text(encoding="utf-8")
        header = (ROOT / "code" / "renderer2" / "tr_postprocess.h").read_text(encoding="utf-8")
        display_doc = (ROOT / "docs" / "DISPLAY.md").read_text(encoding="utf-8")
        audit_doc = COLORSPACE_AUDIT_PATH.read_text(encoding="utf-8")

        legacy_start = source.index("static void RB_CalculateAutoExposureTargetLegacy")
        robust_start = source.index("static void RB_CalculateAutoExposureTargetRobust")
        histogram_start = source.index("static void RB_CalculateAutoExposureTargetHistogramPercentile")
        robust_end = source.index("static void RB_CalculateAutoExposureTargetHistogramPercentile", robust_start)
        histogram_end = source.index("static void RB_BlendAutoExposureTarget", histogram_start)
        legacy_body = source[legacy_start:robust_start]
        robust_body = source[robust_start:robust_end]
        histogram_body = source[histogram_start:histogram_end]

        self.assertIn("AUTO_EXPOSURE_MODE_TIME_CONSTANT = 1", header)
        self.assertIn("AUTO_EXPOSURE_MODE_LEGACY = 2", header)
        self.assertIn("AUTO_EXPOSURE_MODE_HISTOGRAM_PERCENTILE = 3", header)
        self.assertIn("RB_AutoExposureHistogramPercentileAvailable", source)
        self.assertIn("RB_TimeConstantAutoExposureAlpha", source)
        self.assertIn("ri.Milliseconds()", source)
        self.assertIn("AUTO_EXPOSURE_MAX_DELTA_SECONDS", source)
        self.assertIn("Q_exp2f((-deltaSeconds * AUTO_EXPOSURE_EXP2_E) / tauSeconds)", source)
        self.assertIn("RB_SanitizeToneMapInputs();", source)
        self.assertIn("RB_CameraExposureScale(autoExposureEnabled)", source)
        self.assertIn("FBO_FastBlit", legacy_body)
        self.assertIn("&tr.calclevels4xShader[1]", robust_body)
        self.assertNotIn("FBO_FastBlit", robust_body)
        self.assertIn("&tr.calclevels4xShader[2]", histogram_body)
        self.assertIn("AUTO_EXPOSURE_MODE_HISTOGRAM_PERCENTILE", source)
        self.assertIn("`r_autoExposure`: Automatic exposure", display_doc)
        self.assertIn("`1`: Time-constant adaptation.", display_doc)
        self.assertIn("`2`: Legacy parity mode", display_doc)
        self.assertIn("`3`: Modern-tier histogram percentile reduction", display_doc)
        self.assertIn("elapsed-time time-constant adaptation", audit_doc)
        self.assertIn("histogram percentile reduction", audit_doc)

    def test_renderer2_auto_exposure_has_percentile_reduction_shader(self) -> None:
        shader = (ROOT / "code" / "renderer2" / "glsl" / "calclevels4x_fp.glsl").read_text(encoding="utf-8")
        glsl = (ROOT / "code" / "renderer2" / "tr_glsl.c").read_text(encoding="utf-8")
        local = (ROOT / "code" / "renderer2" / "tr_local.h").read_text(encoding="utf-8")

        self.assertIn("#ifdef HISTOGRAM_PERCENTILE", shader)
        self.assertIn("SortPercentileSamples", shader)
        self.assertIn("ReducePercentileChannel(0, 1)", shader)
        self.assertIn("ReducePercentileChannel(1, 8)", shader)
        self.assertIn("ReducePercentileChannel(2, 14)", shader)
        self.assertIn("GetHistogramPercentileValues", shader)
        self.assertIn("calclevels4xShader[3]", local)
        self.assertIn("for (i = 0; i < 3; i++)", glsl)
        self.assertIn("#define HISTOGRAM_PERCENTILE", glsl)

    def test_glx_auto_exposure_has_tiered_histogram_percentile_path(self) -> None:
        color_math = (ROOT / "code" / "rendererglx" / "glx_color_math.h").read_text(encoding="utf-8")
        render_ir = (ROOT / "code" / "rendererglx" / "glx_render_ir.h").read_text(encoding="utf-8")
        postprocess = (ROOT / "code" / "rendererglx" / "glx_postprocess.cpp").read_text(encoding="utf-8")
        renderer_arb = (ROOT / "code" / "renderer" / "tr_arb.c").read_text(encoding="utf-8")

        self.assertIn("GLX_COLOR_MATH_EXPOSURE_HISTOGRAM_BINS", color_math)
        self.assertIn("GLX_ColorMath_ExposureHistogramPercentile", color_math)
        self.assertIn("ExposureReductionAlgorithm::HistogramPercentile", render_ir)
        self.assertIn("GLX_AUTO_EXPOSURE_HISTOGRAM", postprocess)
        self.assertIn("r_glxAutoExposurePercentile", postprocess)
        self.assertIn("GLX_PostProcess_ModernExposureTier", postprocess)
        self.assertIn("ExposureReductionAlgorithm::SimpleAverage", postprocess)
        self.assertIn("autoExposureHistogramFrames", postprocess)
        self.assertIn("GLX_CompatAutoExposureNeedsSamples", renderer_arb)
        self.assertIn("qglReadPixels( 0, 0, width, height, GL_RGBA, GL_FLOAT", renderer_arb)

    def test_glx_depth_fade_arb_program_preserves_vertex_color(self) -> None:
        renderer_arb = (ROOT / "code" / "renderer" / "tr_arb.c").read_text(encoding="utf-8")
        dummy_vp = renderer_arb[
            renderer_arb.index("static const char *dummyVP"):
            renderer_arb.index("static const char *spriteFP")
        ]
        depth_fade_fp = renderer_arb[
            renderer_arb.index("static const char *depthFadeFP"):
            renderer_arb.index("qboolean GL_DepthFadeProgramAvailable")
        ]

        self.assertIn("MUL base, base, fragment.color", depth_fade_fp)
        self.assertIn("MOV result.color, vertex.color", dummy_vp)

    def test_glx_depth_fade_skips_noworldmodel_hud_views(self) -> None:
        backend = (ROOT / "code" / "renderer" / "tr_backend.c").read_text(encoding="utf-8")
        shade = (ROOT / "code" / "renderer" / "tr_shade.c").read_text(encoding="utf-8")
        depth_snapshot = backend[
            backend.index("if ( !depthFadeSnapshot"):
            backend.index("FBO_CopyDepthFade();")
        ]
        depth_active = shade[
            shade.index("static qboolean RB_DepthFadeActive"):
            shade.index("static void RB_DrawDepthFadeStage")
        ]

        self.assertIn("( backEnd.refdef.rdflags & RDF_NOWORLDMODEL ) == 0", depth_snapshot)
        self.assertIn("( backEnd.refdef.rdflags & RDF_NOWORLDMODEL ) == 0", depth_active)

    def test_glx_world_cel_outline_uses_opaque_cutoff(self) -> None:
        backend = (ROOT / "code" / "renderer" / "tr_backend.c").read_text(encoding="utf-8")

        self.assertIn("if ( shader->sort > SS_OPAQUE ) {", backend)
        self.assertNotIn("if ( shader->sort >= SS_BLEND0 ) {", backend)

    def test_hdr_screenshot_capture_policy_stays_sdr_by_default(self) -> None:
        renderer_init = (ROOT / "code" / "renderer" / "tr_init.c").read_text(encoding="utf-8")
        glx_render_ir = (ROOT / "code" / "rendererglx" / "glx_render_ir.h").read_text(encoding="utf-8")
        glx_module = (ROOT / "code" / "rendererglx" / "glx_module.cpp").read_text(encoding="utf-8")
        glx_postprocess = (ROOT / "code" / "rendererglx" / "glx_postprocess.cpp").read_text(encoding="utf-8")
        screenshots_doc = (ROOT / "docs" / "SCREENSHOTS.md").read_text(encoding="utf-8")
        audit_doc = COLORSPACE_AUDIT_PATH.read_text(encoding="utf-8")
        sweep = (ROOT / "scripts" / "glx_runtime_sweep.py").read_text(encoding="utf-8")

        self.assertIn('r_screenshotCaptureMode = ri.Cvar_Get( "r_screenshotCaptureMode", "0"', renderer_init)
        self.assertIn("R_ScreenshotCaptureModeName", renderer_init)
        self.assertIn('return "sdr-srgb";', renderer_init)
        self.assertIn("R_WarnExplicitHdrScreenshotCapture", renderer_init)
        self.assertIn("captureMode %s", renderer_init)
        self.assertIn("captureColorSpace %s", renderer_init)
        self.assertIn("CaptureExportPolicy", glx_render_ir)
        self.assertIn("GLX_RenderIR_CaptureOutputTransform", glx_render_ir)
        self.assertIn("OutputTransfer::ScreenshotSrgb", glx_render_ir)
        self.assertIn("capture-request", glx_module)
        self.assertIn("capture policy", glx_postprocess)
        self.assertIn("default to SDR sRGB byte output", screenshots_doc)
        self.assertIn("`r_screenshotCaptureMode` records the explicit capture policy", screenshots_doc)
        self.assertIn("Reserved scene-linear HDR export request", screenshots_doc)
        self.assertIn("reserved HDR-output request", renderer_init)
        self.assertIn("Screenshot capture/export", audit_doc)
        self.assertIn("capture-request", audit_doc)
        self.assertIn("GLX_SCREENSHOT_CAPTURE_POLICY_CONTRACT", sweep)
        self.assertIn("capturePolicyRequest", sweep)
        self.assertIn('"defaultColorSpace": "sdr-srgb"', sweep)
        self.assertIn('"hdr-scene-linear"', sweep)
        self.assertIn('"hdr-output"', sweep)
        self.assertIn('"hdrExportStatus": "explicit-reserved"', sweep)

    def test_hdr_bloom_intermediates_have_role_based_format_policy(self) -> None:
        fbo_source = (ROOT / "code" / "renderer" / "tr_arb.c").read_text(encoding="utf-8")
        init_source = (ROOT / "code" / "renderer" / "tr_init.c").read_text(encoding="utf-8")
        cmds_source = (ROOT / "code" / "renderer" / "tr_cmds.c").read_text(encoding="utf-8")
        glx_postprocess = (ROOT / "code" / "rendererglx" / "glx_postprocess.cpp").read_text(encoding="utf-8")
        display_doc = (ROOT / "docs" / "DISPLAY.md").read_text(encoding="utf-8")
        audit_doc = COLORSPACE_AUDIT_PATH.read_text(encoding="utf-8")

        self.assertIn("return GL_RGBA16F;", fbo_source[fbo_source.index("static GLint FBO_MainInternalFormat"):])
        self.assertIn("FBO_PositiveIntermediateCandidates( qtrue", fbo_source)
        self.assertIn("GL_R11F_G11F_B10F", fbo_source)
        self.assertIn("GL_RG16F", fbo_source)
        self.assertIn("FBO_AddFormatCandidate( formats, count, GL_RGBA16F );", fbo_source)
        self.assertIn("FBO_CreateWithFormat", fbo_source)
        self.assertIn("fboBloomInternalFormat = fb->internalFormat;", fbo_source)
        self.assertIn("r_hdrBloomFormat", init_source)
        self.assertIn("r_hdrBloomFormat->modified", cmds_source)
        self.assertIn("bloom storage: policy", glx_postprocess)
        self.assertIn("`r_hdrBloomFormat`", display_doc)
        self.assertIn("positive-only bloom/extract", audit_doc)

    def test_task_q_color_pipeline_sources_are_audited(self) -> None:
        renderer_common = (ROOT / "code" / "renderer" / "tr_common.h").read_text(encoding="utf-8")
        renderer_image = (ROOT / "code" / "renderer" / "tr_image.c").read_text(encoding="utf-8")
        renderer_arb = (ROOT / "code" / "renderer" / "tr_arb.c").read_text(encoding="utf-8")
        vulkan_image = (ROOT / "code" / "renderervk" / "tr_image.c").read_text(encoding="utf-8")
        glx_module = (ROOT / "code" / "rendererglx" / "glx_module.cpp").read_text(encoding="utf-8")
        audit_doc = COLORSPACE_AUDIT_PATH.read_text(encoding="utf-8")
        texture_manifest = json.loads(
            (ROOT / "docs" / "fnquake3" / "GLX_TEXTURE_CLASSIFICATION_MANIFEST.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertIn("IMGFLAG_COLORSPACE_SRGB", renderer_common)
        self.assertIn("IMAGE_COLORSPACE_SRGB", renderer_common)
        self.assertIn("GL_SRGB8_ALPHA8", renderer_image)
        self.assertIn("textureSrgbAvailable", renderer_image)
        self.assertIn("GL_FRAMEBUFFER_SRGB", renderer_arb)
        self.assertIn("srgbCutoff", renderer_arb)
        self.assertIn("GL_RGBA16F", renderer_arb)
        self.assertIn("VK_FORMAT_R8G8B8A8_SRGB", vulkan_image)
        self.assertIn("glx: color audit srgb-decode", glx_module)
        self.assertIn("glx: texture audit", glx_module)
        for text in (
            "Authored color maps",
            "Lightmaps",
            "GL_FRAMEBUFFER_SRGB",
            "Screenshot/video capture",
            "r_glxColorPipelineDebug",
            "RGBA16F",
        ):
            self.assertIn(text, audit_doc)
        row_ids = {row["id"] for row in texture_manifest["rows"]}
        self.assertTrue(set(glx_runtime_sweep.GLX_REQUIRED_TEXTURE_CLASS_ROWS).issubset(row_ids))
        rows_by_id = {row["id"]: row for row in texture_manifest["rows"]}
        for row_id, expected in glx_runtime_sweep.GLX_TEXTURE_CLASSIFICATION_CONTRACT.items():
            self.assertEqual(rows_by_id[row_id]["declaredSpace"], expected["declaredSpace"])
            self.assertEqual(rows_by_id[row_id]["sceneLinearDecode"], expected["sceneLinearDecode"])

    def test_task_r_color_grading_sources_are_covered(self) -> None:
        renderer_arb = (ROOT / "code" / "renderer" / "tr_arb.c").read_text(encoding="utf-8")
        vulkan_gamma = (ROOT / "code" / "renderervk" / "shaders" / "gamma.frag").read_text(encoding="utf-8")
        vulkan_backend = (ROOT / "code" / "renderervk" / "vk.c").read_text(encoding="utf-8")
        glx_color_math = (ROOT / "code" / "rendererglx" / "glx_color_math.h").read_text(encoding="utf-8")
        glx_post_output = (ROOT / "code" / "rendererglx" / "glx_post_output_reference.h").read_text(encoding="utf-8")
        glx_post_shader_plan = (ROOT / "code" / "rendererglx" / "glx_post_shader_plan.h").read_text(encoding="utf-8")
        glx_post_shader_source = (ROOT / "code" / "rendererglx" / "glx_post_shader_source.h").read_text(encoding="utf-8")
        glx_post_shader = (ROOT / "code" / "rendererglx" / "glx_post_shader.cpp").read_text(encoding="utf-8")
        glx_ir = (ROOT / "code" / "rendererglx" / "glx_render_ir.h").read_text(encoding="utf-8")
        glx_module = (ROOT / "code" / "rendererglx" / "glx_module.cpp").read_text(encoding="utf-8")
        display_doc = (ROOT / "docs" / "DISPLAY.md").read_text(encoding="utf-8")

        for text in (
            "ARB_BuildColorGradeProgram",
            "FBO_BuildBradfordAdaptation",
            "*colorGradeIdentityLUT",
            "texture[2]",
        ):
            self.assertIn(text, renderer_arb)
        for text in (
            "colorGradeLut",
            "applyLiftGammaGainAndWhitePoint",
            "sampleColorGradeLut",
        ):
            self.assertIn(text, vulkan_gamma)
        for text in (
            "GLX_ColorMath_SrgbToLinear",
            "GLX_ColorMath_ToneMapAcesFitted",
            "GLX_ColorMath_PqEncodeNits",
            "GLX_ColorMath_LutAtlasSize",
            "GLX_ColorMath_AdaptWhitePointBradford",
            "GLX_ColorMath_BuildBradfordAdaptationMatrix",
            "GLX_ColorMath_SampleLutAtlas",
        ):
            self.assertIn(text, glx_color_math)
        for text in (
            "GLX_PostOutputReference_Evaluate",
            "GLX_PostOutputReference_ApplyColorGrade",
            "GLX_PostOutputReference_EncodeHdr10Pq",
            "OutputTransform",
        ):
            self.assertIn(text, glx_post_output)
        for text in (
            "GLX_PostShader_BuildPlan",
            "GLX_POST_SHADER_FEATURE_LIFT_GAMMA_GAIN",
            "GLX_POST_SHADER_FEATURE_ENCODE_HDR10_PQ",
            "PostShaderPlan",
        ):
            self.assertIn(text, glx_post_shader_plan)
        for text in (
            "GLX_PostShaderSource_WriteFragment",
            "glxToneMapAces",
            "glxPqEncode",
            "glxSampleLutAtlas",
            "GLX_POST_SHADER_SOURCE_VERSION",
        ):
            self.assertIn(text, glx_post_shader_source)
        for text in (
            "GLX_PostShader_RecordPlan",
            "GLX_PostShader_CacheProgram",
            "GLX_PostShader_CreateProgram",
            "GLX_ColorMath_BuildBradfordAdaptationMatrix",
            "r_glxPostShaderCache",
            "r_glxPostShaderExecute",
            "GLX_PostShader_TryBindDirectFinal",
        ):
            self.assertIn(text, glx_post_shader)
        self.assertIn("vk_color_grade_lut_descriptor", vulkan_backend)
        self.assertIn("color_grade_mode", vulkan_backend)
        self.assertIn("LiftGammaGainLut3D", glx_ir)
        self.assertIn("RecordColorGradeLut", glx_module)
        self.assertIn("PostNodeKind::Grade", glx_ir)
        self.assertIn("GLX_RenderIR_BuildPostOutputPlan", glx_module)
        self.assertIn("TryBindPostShaderDirectFinal", glx_module)
        self.assertIn("post shader cache", glx_module)
        for cvar in (
            "r_colorGrade",
            "r_colorGradeLift",
            "r_colorGradeGamma",
            "r_colorGradeGain",
            "r_colorGradeWhitePoint",
            "r_colorGradeAdaptWhitePoint",
            "r_colorGradeLUT",
            "r_colorGradeLUTScale",
        ):
            self.assertIn(cvar, display_doc)

    def test_task_s_output_backend_sources_are_covered(self) -> None:
        tr_types = (ROOT / "code" / "renderercommon" / "tr_types.h").read_text(encoding="utf-8")
        tr_public = (ROOT / "code" / "renderercommon" / "tr_public.h").read_text(encoding="utf-8")
        sdl_glimp_path = ROOT / "code" / "sdl" / "sdl_glimp.cpp"
        if not sdl_glimp_path.exists():
            sdl_glimp_path = ROOT / "code" / "sdl" / "sdl_glimp.c"
        if not sdl_glimp_path.exists():
            self.fail("Expected SDL GL implementation source at code/sdl/sdl_glimp.cpp or code/sdl/sdl_glimp.c")
        sdl_glimp = sdl_glimp_path.read_text(encoding="utf-8")
        glx_postprocess = (ROOT / "code" / "rendererglx" / "glx_postprocess.cpp").read_text(encoding="utf-8")
        glx_ir = (ROOT / "code" / "rendererglx" / "glx_render_ir.h").read_text(encoding="utf-8")
        vulkan_backend = (ROOT / "code" / "renderervk" / "vk.c").read_text(encoding="utf-8")
        display_doc = (ROOT / "docs" / "DISPLAY.md").read_text(encoding="utf-8")

        for text in (
            "rendererDisplayOutput_t",
            "ROUTPUT_BACKEND_WINDOWS_SCRGB",
            "ROUTPUT_BACKEND_HDR10_PQ",
            "ROUTPUT_BACKEND_MACOS_EDR",
            "ROUTPUT_BACKEND_LINUX_EXPERIMENTAL_HDR",
        ):
            self.assertIn(text, tr_types)
        self.assertIn("GLimp_QueryDisplayOutput", tr_public)
        for text in (
            "SDL_PROP_WINDOW_HDR_HEADROOM_FLOAT",
            "SDL_GetWindowICCProfile",
            "SDL_PROP_DISPLAY_HDR_ENABLED_BOOLEAN",
            "SDL_GL_FLOATBUFFERS",
        ):
            self.assertIn(text, sdl_glimp)
        self.assertIn("r_outputBackend", glx_postprocess)
        self.assertIn("outputHardwareActive", glx_ir)
        self.assertIn("OutputPrimaries::Bt2020", glx_ir)
        self.assertIn("vk_output_request_wants_hdr10", vulkan_backend)
        self.assertIn("precision-request", (ROOT / "code" / "rendererglx" / "glx_module.cpp").read_text(encoding="utf-8"))
        self.assertIn("output backend", glx_runtime_sweep.__dict__["GLX_OUTPUT_BACKEND_RE"].pattern)
        for cvar in ("r_outputBackend", "r_outputAllowExperimentalLinuxHDR"):
            self.assertIn(cvar, display_doc)

    def test_p1_glx_ownership_stream_and_material_sources_are_covered(self) -> None:
        compat = (ROOT / "code" / "renderer" / "tr_glx_compat.h").read_text(encoding="utf-8")
        tr_arb = (ROOT / "code" / "renderer" / "tr_arb.c").read_text(encoding="utf-8")
        tr_backend = (ROOT / "code" / "renderer" / "tr_backend.c").read_text(encoding="utf-8")
        tr_shade = (ROOT / "code" / "renderer" / "tr_shade.c").read_text(encoding="utf-8")
        tr_shadows = (ROOT / "code" / "renderer" / "tr_shadows.c").read_text(encoding="utf-8")
        tr_vbo = (ROOT / "code" / "renderer" / "tr_vbo.c").read_text(encoding="utf-8")
        bridge = (ROOT / "code" / "renderercommon" / "tr_glx_bridge.h").read_text(encoding="utf-8")
        api = (ROOT / "code" / "renderercommon" / "tr_glx_api.h").read_text(encoding="utf-8")
        glx_module = (ROOT / "code" / "rendererglx" / "glx_module.cpp").read_text(encoding="utf-8")
        glx_stream = (ROOT / "code" / "rendererglx" / "glx_stream.cpp").read_text(encoding="utf-8")
        glx_static_world = (ROOT / "code" / "rendererglx" / "glx_static_world.cpp").read_text(encoding="utf-8")
        glx_ir = (ROOT / "code" / "rendererglx" / "glx_render_ir.h").read_text(encoding="utf-8")
        glx_material_key = (ROOT / "code" / "rendererglx" / "glx_material_key.h").read_text(encoding="utf-8")
        glx_material = (ROOT / "code" / "rendererglx" / "glx_material.cpp").read_text(encoding="utf-8")

        for streamed_source in (compat, tr_arb, tr_shade, tr_shadows):
            self.assertNotIn("qglGetIntegerv( GL_ARRAY_BUFFER_BINDING_ARB", streamed_source)
            self.assertNotIn("qglGetIntegerv( GL_ELEMENT_ARRAY_BUFFER_BINDING_ARB", streamed_source)
        self.assertNotIn("qglGetBooleanv( GL_COLOR_WRITEMASK", tr_shadows)
        self.assertIn("GLX_CompatBindStreamArrayBuffer", compat)
        self.assertIn("GLX_CompatBindStreamElementArrayBuffer", bridge)
        self.assertIn("GLX_Renderer_BindStreamArrayBuffer", api)
        self.assertIn("GLX_Renderer_BindStreamElementArrayBuffer", api)
        self.assertIn("GLX_CompatRestoreStreamArrayBuffer", bridge)
        self.assertIn("GLX_CompatRestoreStreamElementArrayBuffer", bridge)
        self.assertIn("GLX_CompatRecordStreamBufferBind", bridge)
        self.assertIn("GLX_Stream_BindArrayBufferCached", glx_stream)
        self.assertIn("GLX_Stream_BindElementArrayBufferCached", glx_stream)
        self.assertIn("GLX_Stream_RecordExternalBufferBind", glx_stream)
        self.assertIn("bufferBindingExternalUpdates", glx_stream)
        self.assertIn("GLX_Stream_BindPreserving( StreamState *state", glx_stream)
        self.assertIn("GLX_Stream_RestoreBinding( StreamState *state", glx_stream)
        self.assertNotIn("GLX_Stream_BindPreserving( GLuint buffer", glx_stream)
        self.assertNotIn("GLX_Stream_RestoreBinding( GLint", glx_stream)
        self.assertNotIn("GL_ARRAY_BUFFER_BINDING, &oldArrayBuffer", glx_stream)
        self.assertNotIn("frameBufferMultiSampling && !depthFadeTexture", tr_arb)
        self.assertIn("if ( !depthFadeTexture &&", tr_arb)
        self.assertIn("if ( depthFadeTextureShared ) {", tr_arb)
        self.assertIn("GL_GetColorMask( rgba );", tr_shadows)
        self.assertIn("GL_ColorMask( cmd->rgba[0], cmd->rgba[1], cmd->rgba[2], cmd->rgba[3] );", tr_backend)
        self.assertIn("GL_ColorMask( GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE );", tr_arb)
        self.assertIn("restoreArrayBuffer = oldArrayBuffer == state->buffer ? 0u : oldArrayBuffer", glx_stream)
        self.assertIn("arrayBufferBindingCacheHits", glx_stream)
        self.assertIn("elementArrayBufferBindingKnown", glx_stream)
        self.assertIn("GLX_StaticWorld_CurrentIndirectBufferBinding", glx_static_world)
        self.assertIn("GLX_StaticWorld_BindIndirectBufferTracked", glx_static_world)
        self.assertIn("GLX_StaticWorld_RestoreIndirectBufferBinding", glx_static_world)
        self.assertIn("indirectBufferBindingKnown", glx_static_world)
        self.assertLessEqual(glx_static_world.count("s_fns.GetIntegerv( GL_DRAW_INDIRECT_BUFFER_BINDING"), 1)
        self.assertIn("GLX_Renderer_RecordStreamBufferBind", api)
        self.assertIn("VBO_BindBufferTracked", tr_vbo)
        self.assertIn("GLX_CompatRecordStreamBufferBind", tr_vbo)
        self.assertIn("post/output ownership", glx_module)
        self.assertIn("GLX_RenderIR_BuildPostOutputPlan", glx_module)
        self.assertIn("GLX_Executor_ConsumeOutputTransform", glx_module)
        self.assertIn("MaterialParameterBlock", glx_ir)
        self.assertIn("PostOutputPlan", glx_ir)
        self.assertIn("GLX_POST_OUTPUT_FALLBACK_EXECUTOR_REJECT", glx_ir)
        self.assertIn("GLX_POST_OUTPUT_FALLBACK_EXECUTOR_NOT_IMPLEMENTED", glx_ir)
        self.assertIn("GLX_RenderIR_PostNodeExecutorImplemented", glx_ir)
        self.assertIn("executable nodes", glx_module)
        self.assertIn("post shader plan", glx_module)
        self.assertIn("GLX_PostProcess_RecordPostShaderPlan", glx_module)
        self.assertIn("postShaderFeatures", SWEEP_PATH.read_text(encoding="utf-8"))
        self.assertIn("postShaderDirectFinalBound", SWEEP_PATH.read_text(encoding="utf-8"))
        self.assertIn("postOutputExecutableNodes", SWEEP_PATH.read_text(encoding="utf-8"))
        self.assertIn("GLX_RenderIR_HashMaterialParameterBlock", glx_ir)
        self.assertIn("GLX_RenderIR_HashPostNode", glx_ir)
        self.assertIn("GLX_RenderIR_HashOutputTransform", glx_ir)
        self.assertIn("GLX_Material_StatePlanForTierAndParameterBlock", glx_material_key)
        self.assertIn("material parameter blocks", glx_material)
        self.assertIn("lastParameterBlockHash", glx_material)
        self.assertIn("lastPostNodeHash", glx_module)
        self.assertIn("lastOutputTransformHash", glx_module)
        self.assertIn("MATERIAL_PARAMETER_BLOCKS_RE", SWEEP_PATH.read_text(encoding="utf-8"))

    def test_keep_window_renderer_restart_reinitializes_glx_caps(self) -> None:
        source = (ROOT / "code" / "renderer" / "tr_init.c").read_text(encoding="utf-8")
        init_start = source.index("static void InitOpenGL")
        first_init = source.index("if ( glConfig.vidWidth == 0 )", init_start)
        keep_window_start = source.index("else", first_init)
        keep_window_end = source.index("if ( !qglViewport )", keep_window_start)
        keep_window_block = source[keep_window_start:keep_window_end]

        self.assertIn("GLX_CompatOnOpenGLReady( &glConfig, gl_extensions );", keep_window_block)

    def test_task_t_release_proof_policy_sources_are_covered(self) -> None:
        sweep_script = SWEEP_PATH.read_text(encoding="utf-8")
        release_script = (ROOT / "scripts" / "release.py").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "glx-verification.yml").read_text(encoding="utf-8")
        rc_gates = (ROOT / "docs" / "fnquake3" / "GLX_RC_GATES.md").read_text(encoding="utf-8")

        for text in (
            "GLX_BLOCKING_RELEASE_PLATFORMS",
            "GLX_RELEASE_REQUIRED_GATES",
            "validate_release_proof_root",
            "GLX_VISUAL_DOSSIER_VERSION",
            "glx_visual_dossier",
            "visualDossier",
            "GLX_SWITCH_LIFECYCLE_VERSION",
            "renderer_switch_lifecycle_evidence",
            "evaluate_renderer_switch_lifecycle",
            "rendererSwitchEvidence",
            "GLX_WORLD_PROOF_VERSION",
            "world_proof_evidence",
            "evaluate_world_proof",
            "worldProofEvidence",
            "GLX_MATERIAL_PROOF_VERSION",
            "material_proof_evidence",
            "evaluate_material_proof",
            "materialProofEvidence",
            "GLX_DYNAMIC_PROOF_VERSION",
            "dynamic_proof_evidence",
            "evaluate_dynamic_proof",
            "dynamicProofEvidence",
            "GLX_POST_PROOF_VERSION",
            "post_proof_evidence",
            "evaluate_post_proof",
            "postProofEvidence",
            "GLX_OWNERSHIP_PROOF_VERSION",
            "ownership_proof_evidence",
            "ownershipProofEvidence",
            "proofPlatform",
            "performance_budget_tier",
            "gpuFrameMs",
            "staticDrawPacketMisses",
            "streamSameFrameWrapRejects",
        ):
            self.assertIn(text, sweep_script)
        self.assertIn("--glx-proof-root", release_script)
        self.assertIn("resolve_glx_runtime_proof", release_script)
        self.assertIn("glx_runtime_proof", release_script)
        self.assertIn("cron: '35 4 * * 1'", workflow)
        self.assertIn("FNQ3_GLX_PROOF_PLATFORM", workflow)
        self.assertIn("Release Proof Root", rc_gates)

    def test_task_v_parity_suite_sources_are_covered(self) -> None:
        sweep_script = SWEEP_PATH.read_text(encoding="utf-8")
        corpus_doc = (ROOT / glx_runtime_sweep.GLX_PROOF_CORPUS_DOC).read_text(encoding="utf-8")
        rc_gates = (ROOT / "docs" / "fnquake3" / "GLX_RC_GATES.md").read_text(encoding="utf-8")

        for text in (
            "GLX_PARITY_SUITES",
            "GLX_GATE_PARITY_SUITES",
            "GLX_PARITY_SUITE_VERSION",
            "required_parity_suites",
            "paritySuiteVersion",
            "paritySuiteIds",
            "paritySuites",
            "cg_shadows",
            "r_celShading",
            "r_greyscale",
            "r_renderScale",
        ):
            self.assertIn(text, sweep_script)

        for suite_id in (
            "screenshot",
            "demo-playback",
            "hud",
            "shadow",
            "bloom",
            "cel-shading",
            "greyscale",
            "render-scale",
        ):
            self.assertIn(f"`{suite_id}`", corpus_doc)
            self.assertIn(suite_id, rc_gates)

    def test_task_w_promotion_policy_sources_are_covered(self) -> None:
        promotion_script = PROMOTION_PATH.read_text(encoding="utf-8")
        release_script = (ROOT / "scripts" / "release.py").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "glx-verification.yml").read_text(encoding="utf-8")
        promotion_doc = (ROOT / "docs" / "fnquake3" / "GLX_PROMOTION.md").read_text(encoding="utf-8")
        final_contract = (ROOT / "docs" / "fnquake3" / "GLX_FINAL_CONTRACT.md").read_text(encoding="utf-8")

        for text in (
            "PROMOTION_REQUIRED_TIERS",
            "PROMOTION_OWNERSHIP_PROFILE",
            "GLX_OWNERSHIP_PROOF_VERSION",
            "check_feature_matrix",
            "check_release_proof_root",
            "check_ownership_proof",
            "check_renderer_source_policy",
            "check_legacy_coupling_inventory",
            "check_rollback_package_metadata",
            "PROMOTION_LEGACY_RENDERER_SOURCE_BUDGET",
            "PROMOTION_ROLLBACK_METADATA_VERSION",
            "policyViolation",
        ):
            self.assertIn(text, promotion_script)

        self.assertIn("promotion_report", release_script)
        self.assertIn("glx_promotion", release_script)
        self.assertIn("--glx-rollback-metadata", release_script)
        self.assertIn("glx_rollback_package", release_script)
        self.assertIn("attach_glx_rollback_archives", release_script)
        self.assertIn("scripts/glx_promotion.py", workflow)
        self.assertIn("glx-promotion.json", workflow)
        self.assertIn("GLX_ROLLBACK_PACKAGE.md", workflow)
        self.assertIn("GLX_VISUAL_DOSSIER.md", workflow)
        for text in (
            "Migration Alias Plan",
            "OpenGL2 Legacy Flag Plan",
            "Rollback Package Contract",
            "Rollback Package Metadata",
            "Legacy Coupling Ledger",
        ):
            self.assertIn(text, promotion_doc)
        self.assertIn("scripts/glx_promotion.py --require-ready --proof-root <dir> --rollback-metadata <json>", final_contract)

    def test_task_x_productization_sources_are_covered(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        meson_options = (ROOT / "meson_options.txt").read_text(encoding="utf-8")
        meson_build = (ROOT / "meson.build").read_text(encoding="utf-8")
        build_doc = (ROOT / "BUILD.md").read_text(encoding="utf-8")
        display_doc = (ROOT / "docs" / "DISPLAY.md").read_text(encoding="utf-8")
        screenshots_doc = (ROOT / "docs" / "SCREENSHOTS.md").read_text(encoding="utf-8")
        glx_doc = (ROOT / "docs" / "GLX.md").read_text(encoding="utf-8")
        renderer_doc = (ROOT / "docs" / "fnquake3" / "GLX_RENDERER.md").read_text(encoding="utf-8")
        readme_template = (ROOT / "docs" / "templates" / "README.md.in").read_text(encoding="utf-8")
        release_script = (ROOT / "scripts" / "release.py").read_text(encoding="utf-8")

        self.assertRegex(makefile, r"(?m)^USE_GLX\s*=\s*1$")
        self.assertIn("'glx'", meson_options)
        self.assertIn("renderer_prefix + '_glx_'", meson_build)
        self.assertIn("renderer_gl_src + renderer_glx_src", meson_build)
        self.assertIn("single client executable", build_doc)
        for text in (
            "canonical OpenGL-lineage renderer",
            "GLx Renderer Guide",
        ):
            self.assertIn(text, glx_doc)
        self.assertIn("troubleshooting", glx_doc.lower())
        self.assertIn("Canonical OpenGL-lineage renderer", display_doc)
        self.assertIn("canonical OpenGL-lineage renderer", renderer_doc)
        self.assertIn("docs/GLX.md", readme_template)
        self.assertIn('ROOT / "docs" / "GLX.md"', release_script)
        for current_text in (build_doc, display_doc, screenshots_doc, renderer_doc, glx_doc):
            self.assertNotRegex(current_text, r"(?i)\bexperimental\s+glx\b")
            self.assertNotRegex(current_text, r"(?i)glx\s+is\s+an\s+experimental")


class GlxRuntimeSweepImageTests(unittest.TestCase):
    def test_png_round_trip_and_exact_compare(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "baseline.png"
            pixels = bytes(
                (
                    255, 0, 0, 255,
                    0, 255, 0, 255,
                    0, 0, 255, 255,
                    255, 255, 255, 255,
                )
            )

            glx_runtime_sweep.write_png_rgba(path, 2, 2, pixels)
            width, height, decoded = glx_runtime_sweep.read_png_rgba(path)
            self.assertEqual((width, height), (2, 2))
            self.assertEqual(decoded, pixels)

            comparison = glx_runtime_sweep.compare_png_files(path, path, 0.0, 0.0)
            self.assertEqual(comparison["status"], "passed")
            self.assertEqual(comparison["changedPixels"], 0)
            self.assertEqual(comparison["psnr"], "inf")
            self.assertEqual(comparison["ssim"], 1.0)

    def test_screenshot_results_attach_color_histogram(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            screenshot = root / "baseq3" / "screenshots" / "proof.png"
            glx_runtime_sweep.write_png_rgba(
                screenshot,
                1,
                1,
                bytes((10, 20, 30, 255)),
            )

            results = glx_runtime_sweep.screenshot_results(
                root,
                "",
                [
                    {
                        "name": "proof",
                    }
                ],
            )

            histogram = results[0]["histogram"]
            self.assertEqual(histogram["status"], "passed")
            self.assertEqual(histogram["meanRed"], 10.0)
            self.assertEqual(histogram["meanGreen"], 20.0)
            self.assertEqual(histogram["meanBlue"], 30.0)
            self.assertTrue(Path(results[0]["histogramPath"]).exists())
            self.assertEqual(results[0]["falseColor"]["status"], "passed")
            false_color_path = Path(results[0]["falseColorPath"])
            self.assertTrue(false_color_path.exists())
            width, height, _pixels = glx_runtime_sweep.read_png_rgba(false_color_path)
            self.assertEqual((width, height), (1, 1))
            self.assertEqual(results[0]["exposureFalseColor"]["status"], "passed")
            exposure_path = Path(results[0]["exposureFalseColorPath"])
            self.assertTrue(exposure_path.exists())
            width, height, _pixels = glx_runtime_sweep.read_png_rgba(exposure_path)
            self.assertEqual((width, height), (1, 1))
            self.assertEqual(results[0]["capturePolicy"]["defaultColorSpace"], "sdr-srgb")
            self.assertEqual(results[0]["capturePolicy"]["hdrExportStatus"], "explicit-reserved")

    def test_png_compare_reports_threshold_failure_and_writes_diff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline.png"
            candidate = root / "candidate.png"
            diff = root / "diff.png"

            glx_runtime_sweep.write_png_rgba(
                baseline,
                1,
                1,
                bytes((20, 40, 60, 255)),
            )
            glx_runtime_sweep.write_png_rgba(
                candidate,
                1,
                1,
                bytes((21, 40, 60, 255)),
            )

            comparison = glx_runtime_sweep.compare_png_files(
                baseline,
                candidate,
                max_rms=0.0,
                max_pixel_ratio=0.0,
                diff_path=diff,
            )
            self.assertEqual(comparison["status"], "failed")
            self.assertEqual(comparison["changedPixels"], 1)
            self.assertIn("psnr", comparison)
            self.assertIn("ssim", comparison)
            self.assertTrue(diff.exists())

    def test_shader_reference_ramps_are_deterministic_offline_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = glx_runtime_sweep.write_shader_reference_ramps(root)

            self.assertEqual(len(records), len(glx_runtime_sweep.GLX_COLOR_SWEEP_MATRIX))
            first = records[0]
            self.assertTrue(Path(first["path"]).exists())
            self.assertTrue(Path(first["histogramPath"]).exists())
            self.assertTrue(Path(first["falseColorPath"]).exists())
            self.assertTrue(Path(first["exposureFalseColorPath"]).exists())
            width, height, _pixels = glx_runtime_sweep.read_png_rgba(Path(first["path"]))
            self.assertEqual((width, height), (
                glx_runtime_sweep.GLX_SHADER_REFERENCE_RAMP_WIDTH,
                glx_runtime_sweep.GLX_SHADER_REFERENCE_RAMP_HEIGHT,
            ))

            failures = glx_runtime_sweep.validate_image_evidence_manifest(
                {
                    "imageEvidence": {
                        "version": glx_runtime_sweep.GLX_IMAGE_EVIDENCE_VERSION,
                        "requiredSidecars": list(glx_runtime_sweep.GLX_IMAGE_EVIDENCE_SIDECARS),
                        "shaderReferenceRamps": records,
                    }
                }
            )
            self.assertEqual(failures, [])

    def test_shader_reference_ramp_compare_reports_psnr_and_ssim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            row_id = str(glx_runtime_sweep.GLX_COLOR_SWEEP_MATRIX[0]["id"])
            reference = glx_runtime_sweep.write_shader_reference_ramp(
                root / "candidate-source",
                dict(glx_runtime_sweep.GLX_COLOR_SWEEP_MATRIX[0]),
            )

            result = glx_runtime_sweep.compare_shader_reference_ramp(
                row_id,
                Path(reference["path"]),
                root / "comparison",
                max_rms=0.0,
                max_pixel_ratio=0.0,
            )

            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["comparison"]["psnr"], "inf")
            self.assertEqual(result["comparison"]["ssim"], 1.0)

    def test_screenshot_baseline_approval_then_compare(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / "capture.png"
            baseline_dir = root / "baselines"
            glx_runtime_sweep.write_png_rgba(
                candidate,
                1,
                1,
                bytes((10, 20, 30, 255)),
            )
            screenshots = [
                {
                    "name": "capture",
                    "baselineKey": "profile-map-round-step-renderer",
                    "path": str(candidate),
                    "found": True,
                }
            ]

            glx_runtime_sweep.apply_screenshot_baselines(
                screenshots,
                baseline_dir,
                approve_baselines=True,
                diff_dir=None,
                max_rms=0.0,
                max_pixel_ratio=0.0,
            )
            self.assertEqual(screenshots[0]["baselineStatus"], "approved")
            self.assertTrue((baseline_dir / "profile-map-round-step-renderer.png").exists())

            glx_runtime_sweep.apply_screenshot_baselines(
                screenshots,
                baseline_dir,
                approve_baselines=False,
                diff_dir=root / "diffs",
                max_rms=0.0,
                max_pixel_ratio=0.0,
            )
            self.assertEqual(screenshots[0]["baselineStatus"], "passed")
            self.assertEqual(screenshots[0]["comparison"]["status"], "passed")

    def test_visual_dossier_summarizes_review_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = release_proof_manifest("rc-parity", "windows-x64")
            manifest_path = Path(tmp) / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            dossier = glx_runtime_sweep.glx_visual_dossier(manifest, manifest_path)

            self.assertIn("GLx Visual Dossier", dossier)
            self.assertIn("Current Pipeline Flow", dossier)
            self.assertIn("Target Pipeline Flow", dossier)
            self.assertIn("Backend State Overlay", dossier)
            self.assertIn("Driver Tier Matrix", dossier)
            self.assertIn("Histogram And False-Color Evidence", dossier)
            self.assertIn("Parity Diff Sheet", dossier)
            self.assertIn("SDR/HDR Color Sweep Review", dossier)
            self.assertIn("scene-linear", dossier)
            self.assertIn("shader-srgb", dossier)


class GlxRuntimeSweepDiagnosticTests(unittest.TestCase):
    def test_glx_diagnostics_accept_clean_rc_log(self) -> None:
        self.assertEqual(glx_runtime_sweep.normalize_tone_map_name("aces"), "aces-fitted")
        self.assertEqual(glx_runtime_sweep.normalize_tone_map_name("reinhard"), "reinhard-simple")

        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "switch.log"
            log.write_text(
                "\n".join(
                    [
                        "  material renderer: enabled, ready yes, GLSL 1.20",
                        "  material compiles: 24 attempts, 0 compile failures, 0 link failures, precache 0/24, bind failures 0, labels 0",
                        "  material fallbacks: unsupported 0, disabled 0, not-ready 0, full 0, discarded without GL delete 0",
                        "  material compiler plans: compiled 12, unsupported 0, last unsupported 0x0 (none)",
                        "  material parameter blocks: blocks 12 invalid 0 hash 0x1234abcd, last sort 0 passes 1 features 0x0 flags 0x0 state 0x0 object rgb 2:0 alpha 1:0 tc 3/0",
                        "  product tier: GL2X",
                        "  GL2X programmable executor: active yes, client-memory fallback yes, stream uploads yes, material compiler yes, postprocess-lite yes, modern post chain no, scene-linear output no",
                        "  GL2X programmable support: common materials yes, dynamic entities yes, lightmaps yes, multitexture yes, fog yes, sprites yes, beams yes, screenshots yes, demos yes",
                        "  glx: ownership legacy delegation 0 calls/0 items, generic 0, vbo-device 0, vbo-soft 0, arrays 0",
                        f"  GLx pass schedule: valid 9/{glx_runtime_sweep.GLX_EXPECTED_PASS_SCHEDULE_HASH} {glx_runtime_sweep.GLX_EXPECTED_PASS_SCHEDULE}",
                        "  pass schedule: invalid 0/00000000 none",
                        "  render IR products: passes 9, world packets 1, dynamic draws 2, materials 3, uploads 4, post nodes 1, outputs 1, rejects 0",
                        "  post/output ownership: mode legacy-fallback, post nodes 1, outputs 1, legacy fallback yes, executable nodes 0, executable outputs 0, post hash 0x01020304, output hash 0x05060708, plan hash 0x090a0b0c, fallback 0x00000001",
                        "  post shader plan: valid yes, features 0x000000de, hash 0x0badcafe, textures 2, uniforms 12, frames 3, invalid 0",
                        "  post shader cache: ready yes, programs 3/32, plans 4 valid/0 invalid, cache 2 hits/3 misses, compile 3 attempts/0 failures, link failures 0, source failures 0, source hash 0x12345678, program 99",
                        "  post shader direct-final: execute no, eligible yes, bound no, reject 0x00000001, candidates 2, eligible frames 2, attempts 0, binds 0, fallbacks 2, rejects 2, program misses 0, uniform failures 0",
                        "  FBO: requested yes, ready yes, programs yes, framebuffer funcs yes, reason: FBO ready",
                        "  target: render 640x480, capture 640x480, window 640x480, format 0x881a (0x1908:0x140b)",
                        "  controls: scene-linear HDR yes, precision 16, renderScale 1, bloom 2, MSAA no, supersample no, adjusted window yes, greyscale 1.00",
                        "  frames: 3 post, 1 bloom-final, 0 gamma-direct, 3 gamma-blit, 0 minimized output, 1 screenshots",
                        "  frame features: 1 bloom-available, 1 scene-linear, 1 tone-mapped, 1 graded, 1 render-scale, 1 greyscale, 1 window-adjusted, 0 minimized",
                        "  FBO lifecycle: 1 init attempts, 1 ready, 0 failed, 0 disabled, 0 shutdowns",
                        "  color pipeline: space scene-linear, transfer sdr-srgb, tone-map aces-fitted, exposure 1.00, grade lgg-lut3d, paper-white 203 nits, max 203 nits",
                        "  exposure reduction: mode 1, algorithm simple-average, enabled yes, fallback yes, samples 1024/32x32, percentile 80.0, target-luma 0.180, measured-log2 -1.000, measured-luma 0.5000, manual 1.00, scale 0.360, target 0.36, frames 3 histogram/0 simple/3 failures/0",
                        "  color grade stage: mode lgg-lut3d, lift 0.01/0.02/0.03, gamma 1.10/1.00/0.95, gain 1.05/1.00/0.98, white-point 6504->6000 K, lut-size 16, lut-scale 4.00",
                        "  color audit: srgb-decode yes requested yes available yes, framebuffer-srgb no requested yes available yes, capture sdr-srgb, capture-request sdr-srgb, capture-hdr-aware no, capture-supported yes, target-float yes, final-encode shader-srgb, contract yes",
                        "  texture audit: srgb 4 decode 4, linear 2 decode 0, data 2 decode 0, unknown 0 decode 0, missing-srgb-decode 0, unexpected-decode 0",
                        '  glx: color-frame-json {"frame":1,"backend":"sdr-srgb","space":"scene-linear","transfer":"sdr-srgb","exposure":1.0000,"paperWhiteNits":203.0,"maxOutputNits":203.0,"srgbDecode":true,"framebufferSrgb":false,"internalFormat":"0x881a","textureFormat":"0x1908","textureType":"0x140b","sceneTargetFloat":true,"shaderSrgbEncode":true,"contractValid":true}',
                        "  output backend: request auto, selected sdr-srgb, native windows-scrgb, hardware no, experimental no, display-hdr yes, headroom 4.00, sdr-white 203 nits, display-max 812 nits, icc yes/2048, driver windows, display HDR Panel, reason: test",
                        "  display state: queries 4, changes 1, capability 1, backend 1, hdr 1, headroom 1, luminance 1, icc 1, last-frame 2, flags 0x000000fe, hash 0x12345678, previous 0x01020304",
                        "  bloom create: last success, 1/1 ready, texture-unit failures 0, FBO failures 0",
                        "  bloom storage: policy auto, format 0x8c3a (0x1907:0x140b)",
                        "  bloom passes: calls 1, rendered 1, final 1, pre-final 0, skipped 0, failures 0, mode1 0, mode2 1, reflections 0",
                        "  copies/blits: screen-map copies 0, MSAA blits 0 (0 depth), SSAA blits 0, last output bloom-final",
                        "  post pass counters: blits 4, binds 9, clears 1, fullscreen passes 6",
                        "  pass timer queries: active yes, queries 7, unavailable frames 0, ring-full skips 0",
                        "  pass GPU timings: backend=0.270ms/1 postprocess=0.420ms/1 bloom=0.250ms/1 bloom-extract=0.030ms/1 bloom-downscale=0.010ms/3 bloom-blur=0.090ms/2 bloom-blend=0.080ms/1 bloom-final=0.060ms/1 bloom-lens-reflection=n/a/0 gamma-direct=n/a/0 gamma-blit=0.110ms/1 fbo-blit=0.040ms/2 copy-screen=n/a/0 flare=0.020ms/1",
                        "  dynamic stream buffer: yes",
                        "  dynamic stream sync: yes, fences 1, waits 0, timeouts 0, failures 0, pending skips 0",
                        "  dynamic stream reservations: 1, commits: 1, wraps: 0, same-frame wrap rejects: 0, orphans: 0",
                        "  dynamic stream uploads: 1 calls, 0.01 MB, failures 0",
                        "  dynamic stream binding cache: queries 1, hits 3, restores 2, invalidations 1, external 4, array known no buffer 0, element known no buffer 0",
                        "  dynamic stream draws: 1/1 attempts, 3 verts, 3 indexes, 0.01 MB, index 0.01 MB, tex1 0.00 MB, mt 0, fog 0, depthfrag 0, texmod 0, env 0, dlight 0, screen 0, video 0, shadow 0, beam 0, post 0, fallbacks 0",
                        "  dynamic stream categories: entity 1/1, particle 0/0, poly 0/0, mark 0/0, weapon 0/0, ui 0/0, beam 0/0, special 0/0",
                        "  dynamic stream category fallbacks: entity 0, particle 0, poly 0, mark 0, weapon 0, ui 0, beam 0, special 0",
                        "  dynamic stream draw skips: 2 (bind 0, input 0, mt 0, depthfrag 0, texcoord 0, empty 0, key 1, fog 1, program 0)",
                        "  dynamic stream material compiler: rejected 0, last unsupported 0x0 (none)",
                        "  dynamic stream multitexture gate: yes, accepted 2, rejected 0",
                        "  dynamic stream depth-fragment gate: yes, accepted 1, rejected 0",
                        "  dynamic stream reservation failures: 0",
                        "  static world GLx renderer: yes, arena upload yes, arena draw yes",
                        "  static world GLx arena: yes, builds 1, skips 0, failures 0, binds v1/i1, draw skips 0, 1.00 MB",
                        "  static world GLx packet batches: yes, attempts 1, batches 1, packet runs 1/3 indexes, fallback runs 0, singles 0",
                        "  static world GLx multidraw indirect: yes, 0/0 calls, 0 runs, 0 indexes, fallbacks 0, skips 0, errors 0, largest 0",
                    ]
                ),
                encoding="utf-8",
            )

            diagnostics = glx_runtime_sweep.analyze_glx_diagnostics(log, "glx-parity")
            self.assertTrue(diagnostics["found"])
            self.assertEqual(diagnostics["failures"], [])
            self.assertEqual(diagnostics["metrics"]["materialParameters"]["blocks"], 12)
            self.assertEqual(diagnostics["metrics"]["materialParameters"]["invalid"], 0)
            self.assertEqual(diagnostics["metrics"]["materialParameters"]["hash"], 0x1234ABCD)
            self.assertEqual(diagnostics["metrics"]["materialParameters"]["tcGen0"], 3)
            self.assertEqual(diagnostics["metrics"]["materialParameters"]["tcGen1"], 0)
            self.assertEqual(diagnostics["metrics"]["materialParameters"]["features"], 0)
            self.assertEqual(diagnostics["metrics"]["postOutputOwnership"]["legacyFallback"], 1)
            self.assertEqual(diagnostics["metrics"]["postOutputOwnership"]["executableNodes"], 0)
            self.assertEqual(diagnostics["metrics"]["postOutputOwnership"]["executableOutputs"], 0)
            self.assertEqual(diagnostics["metrics"]["postOutputOwnership"]["postHash"], 0x01020304)
            self.assertEqual(diagnostics["metrics"]["postOutputOwnership"]["outputHash"], 0x05060708)
            self.assertEqual(diagnostics["metrics"]["postOutputOwnership"]["planHash"], 0x090A0B0C)
            self.assertEqual(diagnostics["metrics"]["postOutputOwnership"]["fallbackMask"], 1)
            self.assertEqual(diagnostics["metrics"]["postShaderPlan"]["valid"], 1)
            self.assertEqual(diagnostics["metrics"]["postShaderPlan"]["features"], 0x000000DE)
            self.assertEqual(diagnostics["metrics"]["postShaderPlan"]["hash"], 0x0BADCAFE)
            self.assertEqual(diagnostics["metrics"]["postShaderPlan"]["textures"], 2)
            self.assertEqual(diagnostics["metrics"]["postShaderPlan"]["uniforms"], 12)
            self.assertEqual(diagnostics["metrics"]["postShaderPlan"]["frames"], 3)
            self.assertEqual(diagnostics["metrics"]["postShaderPlan"]["invalidFrames"], 0)
            self.assertEqual(diagnostics["metrics"]["postShaderCache"]["ready"], 1)
            self.assertEqual(diagnostics["metrics"]["postShaderCache"]["programs"], 3)
            self.assertEqual(diagnostics["metrics"]["postShaderCache"]["programLimit"], 32)
            self.assertEqual(diagnostics["metrics"]["postShaderCache"]["validPlans"], 4)
            self.assertEqual(diagnostics["metrics"]["postShaderCache"]["compileFailures"], 0)
            self.assertEqual(diagnostics["metrics"]["postShaderCache"]["linkFailures"], 0)
            self.assertEqual(diagnostics["metrics"]["postShaderCache"]["sourceFailures"], 0)
            self.assertEqual(diagnostics["metrics"]["postShaderCache"]["sourceHash"], 0x12345678)
            self.assertEqual(diagnostics["metrics"]["postShaderCache"]["program"], 99)
            self.assertEqual(diagnostics["metrics"]["postShaderDirectFinal"]["execute"], 0)
            self.assertEqual(diagnostics["metrics"]["postShaderDirectFinal"]["eligible"], 1)
            self.assertEqual(diagnostics["metrics"]["postShaderDirectFinal"]["bound"], 0)
            self.assertEqual(diagnostics["metrics"]["postShaderDirectFinal"]["reject"], 1)
            self.assertEqual(diagnostics["metrics"]["postShaderDirectFinal"]["candidates"], 2)
            self.assertEqual(diagnostics["metrics"]["postShaderDirectFinal"]["eligibleFrames"], 2)
            self.assertEqual(diagnostics["metrics"]["postShaderDirectFinal"]["attempts"], 0)
            self.assertEqual(diagnostics["metrics"]["postShaderDirectFinal"]["binds"], 0)
            self.assertEqual(diagnostics["metrics"]["postShaderDirectFinal"]["fallbacks"], 2)
            self.assertEqual(diagnostics["metrics"]["postShaderDirectFinal"]["rejects"], 2)
            stream_draw = diagnostics["metrics"]["streamDraw"]
            self.assertEqual(stream_draw["draws"], 1)
            self.assertEqual(stream_draw["dynamicLights"], 0)
            self.assertEqual(stream_draw["screenMaps"], 0)
            self.assertEqual(stream_draw["videoMaps"], 0)
            self.assertEqual(stream_draw["shadows"], 0)
            self.assertEqual(stream_draw["skips"], 2)
            stream_binding = diagnostics["metrics"]["streamBindingCache"]
            self.assertEqual(stream_binding["queries"], 1)
            self.assertEqual(stream_binding["hits"], 3)
            self.assertEqual(stream_binding["external"], 4)
            stream_category = diagnostics["metrics"]["streamCategory"]
            self.assertEqual(stream_category["entityDraws"], 1)
            self.assertEqual(stream_category["entityAttempts"], 1)
            self.assertEqual(stream_category["particleDraws"], 0)
            self.assertEqual(stream_category["specialDraws"], 0)
            self.assertEqual(stream_category["entityFallbacks"], 0)
            stream_draw_skips = diagnostics["metrics"]["streamDrawSkip"]
            self.assertEqual(stream_draw_skips["key"], 1)
            self.assertEqual(stream_draw_skips["fog"], 1)
            self.assertEqual(stream_draw_skips["program"], 0)
            stream_gates = diagnostics["metrics"]["streamMaterialGate"]
            self.assertEqual(stream_gates["multitextureEnabled"], 1)
            self.assertEqual(stream_gates["multitextureAccepted"], 2)
            self.assertEqual(stream_gates["depthFragmentEnabled"], 1)
            self.assertEqual(stream_gates["depthFragmentAccepted"], 1)
            material_plans = diagnostics["metrics"]["materialCompilerPlans"]
            self.assertEqual(material_plans["compiled"], 12)
            self.assertEqual(material_plans["unsupported"], 0)
            self.assertEqual(material_plans["lastUnsupported"], 0)
            self.assertEqual(material_plans["lastUnsupportedReason"], "none")
            stream_compiler = diagnostics["metrics"]["streamMaterialCompiler"]
            self.assertEqual(stream_compiler["rejected"], 0)
            self.assertEqual(stream_compiler["lastUnsupported"], 0)
            self.assertEqual(stream_compiler["lastUnsupportedReason"], "none")
            ownership = diagnostics["metrics"]["ownership"]
            self.assertEqual(ownership["calls"], 0)
            self.assertEqual(ownership["items"], 0)
            self.assertEqual(diagnostics["metrics"]["productTier"]["tier"], "GL2X")
            executor = diagnostics["metrics"]["gl2xExecutor"]
            self.assertEqual(executor["active"], 1)
            self.assertEqual(executor["streamUploads"], 1)
            self.assertEqual(executor["materialCompiler"], 1)
            self.assertEqual(executor["postprocessLite"], 1)
            self.assertEqual(executor["modernPostChain"], 0)
            pass_schedule = diagnostics["metrics"]["passSchedule"]
            self.assertEqual(pass_schedule["valid"], 1)
            self.assertEqual(pass_schedule["count"], 9)
            self.assertEqual(pass_schedule["hash"], glx_runtime_sweep.GLX_EXPECTED_PASS_SCHEDULE_HASH)
            self.assertEqual(pass_schedule["order"], glx_runtime_sweep.GLX_EXPECTED_PASS_SCHEDULE)
            color_pipeline = diagnostics["metrics"]["colorPipeline"]
            self.assertEqual(color_pipeline["space"], "scene-linear")
            self.assertEqual(color_pipeline["transfer"], "sdr-srgb")
            self.assertEqual(color_pipeline["toneMap"], "aces-fitted")
            self.assertEqual(color_pipeline["grade"], "lgg-lut3d")
            self.assertEqual(color_pipeline["exposure"], 1.0)
            self.assertEqual(color_pipeline["paperWhite"], 203.0)
            self.assertEqual(color_pipeline["maxOutput"], 203.0)
            auto_exposure = diagnostics["metrics"]["autoExposure"]
            self.assertEqual(auto_exposure["mode"], 1)
            self.assertEqual(auto_exposure["algorithm"], "simple-average")
            self.assertEqual(auto_exposure["enabled"], 1)
            self.assertEqual(auto_exposure["fallback"], 1)
            self.assertEqual(auto_exposure["sampleCount"], 1024)
            self.assertEqual(auto_exposure["sampleWidth"], 32)
            self.assertEqual(auto_exposure["sampleHeight"], 32)
            self.assertEqual(auto_exposure["targetLuma"], 0.18)
            self.assertEqual(auto_exposure["measuredLuma"], 0.5)
            self.assertEqual(auto_exposure["sampleFailures"], 0)
            color_grade = diagnostics["metrics"]["colorGrade"]
            self.assertEqual(color_grade["mode"], "lgg-lut3d")
            self.assertEqual(color_grade["liftR"], 0.01)
            self.assertEqual(color_grade["gammaR"], 1.10)
            self.assertEqual(color_grade["gainR"], 1.05)
            self.assertEqual(color_grade["whiteTarget"], 6000.0)
            self.assertEqual(color_grade["lutSize"], 16.0)
            self.assertEqual(color_grade["lutScale"], 4.0)
            color_audit = diagnostics["metrics"]["colorAudit"]
            self.assertEqual(color_audit["srgbDecode"], 1)
            self.assertEqual(color_audit["srgbRequested"], 1)
            self.assertEqual(color_audit["srgbAvailable"], 1)
            self.assertEqual(color_audit["framebufferSrgb"], 0)
            self.assertEqual(color_audit["framebufferRequested"], 1)
            self.assertEqual(color_audit["framebufferAvailable"], 1)
            self.assertEqual(color_audit["capture"], "sdr-srgb")
            self.assertEqual(color_audit["captureRequest"], "sdr-srgb")
            self.assertEqual(color_audit["captureHdrAware"], 0)
            self.assertEqual(color_audit["captureSupported"], 1)
            self.assertEqual(color_audit["targetFloat"], 1)
            self.assertEqual(color_audit["finalEncode"], "shader-srgb")
            self.assertEqual(color_audit["contract"], 1)
            texture_audit = diagnostics["metrics"]["textureAudit"]
            self.assertEqual(texture_audit["srgb"], 4)
            self.assertEqual(texture_audit["srgbDecode"], 4)
            self.assertEqual(texture_audit["missingSrgbDecode"], 0)
            self.assertEqual(texture_audit["unexpectedDecode"], 0)
            target_format = diagnostics["metrics"]["targetFormat"]
            self.assertEqual(target_format["internalFormat"], 0x881A)
            self.assertEqual(target_format["textureFormat"], 0x1908)
            self.assertEqual(target_format["textureType"], 0x140B)
            post_controls = diagnostics["metrics"]["postprocessControls"]
            self.assertEqual(post_controls["renderScale"], 1)
            self.assertEqual(post_controls["greyscale"], 1.0)
            self.assertEqual(post_controls["windowAdjusted"], 1)
            post_frames = diagnostics["metrics"]["postprocessFrames"]
            self.assertEqual(post_frames["frames"], 3)
            self.assertEqual(post_frames["screenshots"], 1)
            self.assertEqual(post_frames["minimizedOutput"], 0)
            post_features = diagnostics["metrics"]["postprocessFrameFeatures"]
            self.assertEqual(post_features["renderScale"], 1)
            self.assertEqual(post_features["greyscale"], 1)
            self.assertEqual(post_features["windowAdjusted"], 1)
            self.assertEqual(post_features["minimized"], 0)
            postprocess = diagnostics["metrics"]["postprocess"]
            self.assertEqual(postprocess["bloomStoragePolicy"], "auto")
            self.assertEqual(postprocess["bloomStorageInternalFormat"], 0x8C3A)
            self.assertEqual(postprocess["bloomStorageTextureFormat"], 0x1907)
            self.assertEqual(postprocess["bloomStorageTextureType"], 0x140B)
            pass_counters = diagnostics["metrics"]["gpuPassCounters"]
            self.assertEqual(pass_counters["blits"], 4)
            self.assertEqual(pass_counters["binds"], 9)
            self.assertEqual(pass_counters["clears"], 1)
            self.assertEqual(pass_counters["fullscreen"], 6)
            pass_timing = diagnostics["metrics"]["gpuPassTiming"]
            self.assertEqual(pass_timing["active"], 1)
            self.assertEqual(pass_timing["queries"], 7)
            pass_timings = diagnostics["metrics"]["gpuPassTimings"]
            self.assertEqual(pass_timings["backend"]["lastMs"], 0.27)
            self.assertEqual(pass_timings["postprocess"]["lastMs"], 0.42)
            self.assertEqual(pass_timings["bloom-downscale"]["samples"], 3)
            self.assertEqual(pass_timings["bloom-blur"]["samples"], 2)
            self.assertEqual(pass_timings["flare"]["lastMs"], 0.02)
            color_frame = diagnostics["metrics"]["colorFrame"]
            self.assertEqual(color_frame["samples"], 1)
            self.assertEqual(color_frame["latest"]["backend"], "sdr-srgb")
            self.assertEqual(color_frame["latest"]["internalFormat"], "0x881a")
            self.assertTrue(color_frame["latest"]["contractValid"])
            output_backend = diagnostics["metrics"]["outputBackend"]
            self.assertEqual(output_backend["request"], "auto")
            self.assertEqual(output_backend["selected"], "sdr-srgb")
            self.assertEqual(output_backend["native"], "windows-scrgb")
            self.assertEqual(output_backend["displayHdr"], 1)
            self.assertEqual(output_backend["headroom"], 4.0)
            self.assertEqual(output_backend["displayMax"], 812.0)
            self.assertEqual(output_backend["icc"], 1)
            display_state = diagnostics["metrics"]["displayState"]
            self.assertEqual(display_state["queries"], 4)
            self.assertEqual(display_state["changes"], 1)
            self.assertEqual(display_state["capability"], 1)
            self.assertEqual(display_state["backend"], 1)
            self.assertEqual(display_state["hdr"], 1)
            self.assertEqual(display_state["headroom"], 1)
            self.assertEqual(display_state["luminance"], 1)
            self.assertEqual(display_state["icc"], 1)
            self.assertEqual(display_state["lastFrame"], 2)
            self.assertEqual(display_state["flags"], 0x000000FE)
            self.assertEqual(display_state["hash"], 0x12345678)
            self.assertEqual(display_state["previous"], 0x01020304)

    def test_glx_color_frame_csv_is_gate_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "color.csv.log"
            log.write_text(
                "\n".join(
                    [
                        "glx: color-frame-csv frame,backend,space,transfer,exposure,paperWhiteNits,maxOutputNits,srgbDecode,framebufferSrgb,internalFormat,textureFormat,textureType,sceneTargetFloat,shaderSrgbEncode,contractValid",
                        "glx: color-frame-csv 7,sdr-srgb,scene-linear,sdr-srgb,1.2500,203.0,203.0,yes,no,0x881a,0x1908,0x140b,yes,yes,yes",
                    ]
                ),
                encoding="utf-8",
            )

            diagnostics = glx_runtime_sweep.analyze_glx_diagnostics(log, "glx-color")
            performance = glx_runtime_sweep.analyze_glx_performance(log)

            self.assertTrue(diagnostics["found"])
            self.assertEqual(diagnostics["failures"], [])
            color_frame = diagnostics["metrics"]["colorFrame"]
            self.assertEqual(color_frame["samples"], 1)
            self.assertEqual(color_frame["latest"]["frame"], 7)
            self.assertEqual(color_frame["latest"]["space"], "scene-linear")
            self.assertEqual(color_frame["latest"]["internalFormat"], "0x881a")
            self.assertTrue(color_frame["latest"]["contractValid"])
            self.assertEqual(performance["latest"]["colorFrameSamples"], 1)
            self.assertEqual(performance["latest"]["colorFrameSpace"], "scene-linear")
            self.assertEqual(performance["latest"]["colorFrameInternalFormat"], "0x881a")

    def test_glx_diagnostics_reject_sdr_output_with_hdr_headroom(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "sdr-headroom.log"
            log.write_text(
                "glx: color pipeline scene-linear precision 16 transfer sdr-srgb "
                "tone-map aces-fitted exposure 1.00 bloom-threshold 0.75/2 knee 0.50 "
                "grade none paper-white 203 max 1000\n",
                encoding="utf-8",
            )

            diagnostics = glx_runtime_sweep.analyze_glx_diagnostics(log, "glx-color")

            self.assertTrue(diagnostics["found"])
            self.assertTrue(
                any("HDR max-output headroom" in failure for failure in diagnostics["failures"])
            )

    def test_glx_display_state_diagnostics_allow_sdr_fallback_after_hdr_loss(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "display-state.log"
            log.write_text(
                "\n".join(
                    [
                        "glx: output backend request auto selected sdr-srgb native sdr-srgb hardware no experimental no display-hdr no headroom 1.00 sdr-white 203 display-max 203 icc no/0",
                        "glx: display state queries 6 changes 2 capability 2 backend 1 hdr 1 headroom 1 luminance 1 icc 0 last-frame 5 flags 0x0000003e hash 0x22222222 previous 0x11111111",
                    ]
                ),
                encoding="utf-8",
            )

            diagnostics = glx_runtime_sweep.analyze_glx_diagnostics(log, "glx-color")

            self.assertTrue(diagnostics["found"])
            self.assertEqual(diagnostics["failures"], [])
            display_state = diagnostics["metrics"]["displayState"]
            self.assertEqual(display_state["changes"], 2)
            self.assertEqual(display_state["capability"], 2)
            self.assertEqual(display_state["backend"], 1)
            self.assertEqual(display_state["flags"], 0x0000003E)
            output_backend = diagnostics["metrics"]["outputBackend"]
            self.assertEqual(output_backend["selected"], "sdr-srgb")
            self.assertEqual(output_backend["hardware"], 0)

    def test_glx_ownership_profile_reports_legacy_delegation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "switch.log"
            log.write_text(
                "glx: ownership legacy delegation 3 calls/96 items, generic 1, vbo-device 1, vbo-soft 0, arrays 1\n",
                encoding="utf-8",
            )

            diagnostics = glx_runtime_sweep.analyze_glx_diagnostics(log, "glx-ownership")
            failures = "\n".join(diagnostics["failures"])
            ownership = diagnostics["metrics"]["ownership"]

            self.assertIn("legacy draw delegation", failures)
            self.assertEqual(ownership["calls"], 3)
            self.assertEqual(ownership["items"], 96)
            self.assertEqual(ownership["generic"], 1)
            self.assertEqual(ownership["vboDevice"], 1)
            self.assertEqual(ownership["arrays"], 1)

    def test_glx_ownership_profile_accepts_glxinfo_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "switch.log"
            log.write_text(
                "  ownership legacy delegation: 2 calls, 12 items\n",
                encoding="utf-8",
            )

            diagnostics = glx_runtime_sweep.analyze_glx_diagnostics(log, "glx-ownership")
            failures = "\n".join(diagnostics["failures"])
            ownership = diagnostics["metrics"]["ownership"]

            self.assertIn("legacy draw delegation", failures)
            self.assertNotIn("No GLx ownership diagnostic", failures)
            self.assertEqual(ownership["calls"], 2)
            self.assertEqual(ownership["items"], 12)

    def test_ownership_proof_evidence_passes_for_modern_zero_delegation(self) -> None:
        manifest = ownership_proof_manifest("windows-x64")
        evidence = manifest["ownershipProofEvidence"]

        self.assertEqual(evidence["version"], glx_runtime_sweep.GLX_OWNERSHIP_PROOF_VERSION)
        self.assertEqual(evidence["status"], "passed")
        self.assertTrue(evidence["zeroDelegation"])
        self.assertEqual(evidence["delegation"]["calls"], 0)
        self.assertEqual(evidence["delegation"]["items"], 0)
        self.assertEqual(evidence["productTiers"], ["GL3X"])
        self.assertTrue(evidence["modernTierDiagnosticsOk"])
        self.assertTrue(evidence["modernPostOutput"])
        self.assertEqual(evidence["postOutputOwnership"]["modes"], ["glx-owned"])
        self.assertTrue(evidence["postOutputOwnership"]["executableCountsFound"])
        self.assertEqual(evidence["postOutputOwnership"]["executableNodes"], 2)
        self.assertEqual(evidence["postOutputOwnership"]["executableOutputs"], 1)
        self.assertEqual(evidence["postOutputOwnership"]["fallbackMask"], 0)
        self.assertTrue(evidence["postShaderDirectFinal"]["found"])
        self.assertEqual(evidence["postShaderDirectFinal"]["bound"], 1)
        self.assertEqual(evidence["postShaderDirectFinal"]["binds"], 2)
        self.assertEqual(evidence["postShaderDirectFinal"]["reject"], 0)
        self.assertEqual(evidence["failures"], [])

    def test_ownership_proof_evidence_fails_on_delegation_and_missing_fingerprint(self) -> None:
        manifest = ownership_proof_manifest(
            "windows-x64",
            calls=2,
            items=64,
            post_hash=0,
        )
        evidence = manifest["ownershipProofEvidence"]
        failures = "\n".join(evidence["failures"])

        self.assertEqual(evidence["status"], "failed")
        self.assertFalse(evidence["zeroDelegation"])
        self.assertFalse(evidence["modernPostOutput"])
        self.assertIn("legacy delegation", failures)
        self.assertIn("post-node fingerprint", failures)

    def test_gl12_diagnostics_report_fixed_function_executor_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "switch.log"
            log.write_text(
                "\n".join(
                    [
                        "  product tier: GL12",
                        "  GL12 fixed-function executor: active yes, client-memory draws yes, stream uploads no, material compiler no, modern post chain no",
                        "  GL12 fixed-function support: lightmaps yes, multitexture yes, fog yes, sprites yes, beams yes, dynamic lights yes, stencil shadows if available yes, screenshots yes, demos yes",
                    ]
                ),
                encoding="utf-8",
            )

            diagnostics = glx_runtime_sweep.analyze_glx_diagnostics(log, "glx-off")
            executor = diagnostics["metrics"]["gl12Executor"]
            support = diagnostics["metrics"]["gl12Support"]

            self.assertEqual(diagnostics["failures"], [])
            self.assertEqual(executor["active"], 1)
            self.assertEqual(executor["clientMemoryDraws"], 1)
            self.assertEqual(executor["streamUploads"], 0)
            self.assertEqual(executor["materialCompiler"], 0)
            self.assertEqual(executor["modernPostChain"], 0)
            self.assertEqual(support["lightmaps"], 1)
            self.assertEqual(support["multitexture"], 1)
            self.assertEqual(support["screenshots"], 1)
            self.assertEqual(support["demos"], 1)

    def test_gl12_diagnostics_reject_missing_fixed_function_support(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "switch.log"
            log.write_text(
                "\n".join(
                    [
                        "  product tier: GL12",
                        "  GL12 fixed-function executor: active yes, client-memory draws no, stream uploads yes, material compiler yes, modern post chain yes",
                        "  GL12 fixed-function support: lightmaps yes, multitexture no, fog yes, sprites yes, beams yes, dynamic lights yes, stencil shadows if available yes, screenshots yes, demos yes",
                    ]
                ),
                encoding="utf-8",
            )

            diagnostics = glx_runtime_sweep.analyze_glx_diagnostics(log, "glx-off")
            failures = "\n".join(diagnostics["failures"])

            self.assertIn("client-memory", failures)
            self.assertIn("streamUploads", failures)
            self.assertIn("materialCompiler", failures)
            self.assertIn("modernPostChain", failures)
            self.assertIn("multitexture", failures)

    def test_gl2x_diagnostics_report_programmable_executor_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "switch.log"
            log.write_text(
                "\n".join(
                    [
                        "  product tier: GL2X",
                        "  GL2X programmable executor: active yes, client-memory fallback yes, stream uploads yes, material compiler yes, postprocess-lite yes, modern post chain no, scene-linear output no",
                        "  GL2X programmable support: common materials yes, dynamic entities yes, lightmaps yes, multitexture yes, fog yes, sprites yes, beams yes, screenshots yes, demos yes",
                    ]
                ),
                encoding="utf-8",
            )

            diagnostics = glx_runtime_sweep.analyze_glx_diagnostics(log, "glx-off")
            executor = diagnostics["metrics"]["gl2xExecutor"]
            support = diagnostics["metrics"]["gl2xSupport"]

            self.assertEqual(diagnostics["failures"], [])
            self.assertEqual(executor["active"], 1)
            self.assertEqual(executor["clientMemoryFallback"], 1)
            self.assertEqual(executor["streamUploads"], 1)
            self.assertEqual(executor["materialCompiler"], 1)
            self.assertEqual(executor["postprocessLite"], 1)
            self.assertEqual(executor["modernPostChain"], 0)
            self.assertEqual(executor["sceneLinearOutput"], 0)
            self.assertEqual(support["commonMaterials"], 1)
            self.assertEqual(support["dynamicEntities"], 1)
            self.assertEqual(support["lightmaps"], 1)
            self.assertEqual(support["demos"], 1)

    def test_gl2x_diagnostics_reject_modern_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "switch.log"
            log.write_text(
                "\n".join(
                    [
                        "  product tier: GL2X",
                        "  GL2X programmable executor: active yes, client-memory fallback no, stream uploads no, material compiler no, postprocess-lite no, modern post chain yes, scene-linear output yes",
                        "  GL2X programmable support: common materials no, dynamic entities no, lightmaps yes, multitexture yes, fog yes, sprites yes, beams yes, screenshots yes, demos yes",
                    ]
                ),
                encoding="utf-8",
            )

            diagnostics = glx_runtime_sweep.analyze_glx_diagnostics(log, "glx-off")
            failures = "\n".join(diagnostics["failures"])

            self.assertIn("clientMemoryFallback", failures)
            self.assertIn("streamUploads", failures)
            self.assertIn("materialCompiler", failures)
            self.assertIn("postprocessLite", failures)
            self.assertIn("modernPostChain", failures)
            self.assertIn("sceneLinearOutput", failures)
            self.assertIn("commonMaterials", failures)
            self.assertIn("dynamicEntities", failures)

    def test_gl3x_diagnostics_report_performance_executor_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "switch.log"
            log.write_text(
                "\n".join(
                    [
                        "  product tier: GL3X",
                        "  GL3X performance executor: active yes, FBO postprocess yes, UBO frame/object constants yes, timer queries yes, sync-aware uploads yes, static buffer ownership yes, dynamic buffer ownership yes, persistent uploads no, indirect submission no, direct state access no",
                        "  GL3X performance support: material compiler yes, common materials yes, dynamic entities yes, modern post chain yes, scene-linear output yes, screenshots yes, demos yes",
                    ]
                ),
                encoding="utf-8",
            )

            diagnostics = glx_runtime_sweep.analyze_glx_diagnostics(log, "glx-off")
            executor = diagnostics["metrics"]["gl3xExecutor"]
            support = diagnostics["metrics"]["gl3xSupport"]

            self.assertEqual(diagnostics["failures"], [])
            self.assertEqual(executor["active"], 1)
            self.assertEqual(executor["fboPostProcess"], 1)
            self.assertEqual(executor["uboFrameObjectConstants"], 1)
            self.assertEqual(executor["timerQueries"], 1)
            self.assertEqual(executor["syncAwareUploads"], 1)
            self.assertEqual(executor["staticBufferOwnership"], 1)
            self.assertEqual(executor["dynamicBufferOwnership"], 1)
            self.assertEqual(executor["persistentUploads"], 0)
            self.assertEqual(executor["indirectSubmission"], 0)
            self.assertEqual(executor["directStateAccess"], 0)
            self.assertEqual(support["materialCompiler"], 1)
            self.assertEqual(support["modernPostChain"], 1)
            self.assertEqual(support["sceneLinearOutput"], 1)

    def test_gl3x_diagnostics_reject_gl4_only_requirements_and_missing_modern_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "switch.log"
            log.write_text(
                "\n".join(
                    [
                        "  product tier: GL3X",
                        "  GL3X performance executor: active yes, FBO postprocess no, UBO frame/object constants no, timer queries no, sync-aware uploads no, static buffer ownership no, dynamic buffer ownership no, persistent uploads yes, indirect submission yes, direct state access yes",
                        "  GL3X performance support: material compiler no, common materials no, dynamic entities no, modern post chain no, scene-linear output no, screenshots yes, demos yes",
                    ]
                ),
                encoding="utf-8",
            )

            diagnostics = glx_runtime_sweep.analyze_glx_diagnostics(log, "glx-off")
            failures = "\n".join(diagnostics["failures"])

            self.assertIn("fboPostProcess", failures)
            self.assertIn("uboFrameObjectConstants", failures)
            self.assertIn("timerQueries", failures)
            self.assertIn("syncAwareUploads", failures)
            self.assertIn("staticBufferOwnership", failures)
            self.assertIn("dynamicBufferOwnership", failures)
            self.assertIn("persistentUploads", failures)
            self.assertIn("indirectSubmission", failures)
            self.assertIn("directStateAccess", failures)
            self.assertIn("materialCompiler", failures)
            self.assertIn("modernPostChain", failures)
            self.assertIn("sceneLinearOutput", failures)

    def test_gl41_diagnostics_report_mac_modern_executor_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "switch.log"
            log.write_text(
                "\n".join(
                    [
                        "  product tier: GL41",
                        "  GL41 mac-modern executor: active yes, FBO postprocess yes, UBO frame/object constants yes, timer queries yes, sync-aware uploads yes, static buffer ownership yes, dynamic buffer ownership yes, macOS 4.1 ceiling yes",
                        "  GL41 mac-modern support: material compiler yes, common materials yes, dynamic entities yes, modern post chain yes, scene-linear output yes, high-quality SDR yes, optional hardware HDR yes, screenshots yes, demos yes",
                        "  GL41 mac-modern GL4+ requirements: debug output no, buffer storage no, direct state access no, multi-draw indirect no, persistent uploads no",
                    ]
                ),
                encoding="utf-8",
            )

            diagnostics = glx_runtime_sweep.analyze_glx_diagnostics(log, "glx-off")
            executor = diagnostics["metrics"]["gl41Executor"]
            support = diagnostics["metrics"]["gl41Support"]
            limits = diagnostics["metrics"]["gl41Limits"]

            self.assertEqual(diagnostics["failures"], [])
            self.assertEqual(executor["active"], 1)
            self.assertEqual(executor["fboPostProcess"], 1)
            self.assertEqual(executor["uboFrameObjectConstants"], 1)
            self.assertEqual(executor["timerQueries"], 1)
            self.assertEqual(executor["syncAwareUploads"], 1)
            self.assertEqual(executor["staticBufferOwnership"], 1)
            self.assertEqual(executor["dynamicBufferOwnership"], 1)
            self.assertEqual(executor["macOS41Ceiling"], 1)
            self.assertEqual(support["modernPostChain"], 1)
            self.assertEqual(support["sceneLinearOutput"], 1)
            self.assertEqual(support["highQualitySdr"], 1)
            self.assertEqual(limits["debugOutputRequired"], 0)
            self.assertEqual(limits["bufferStorageRequired"], 0)
            self.assertEqual(limits["directStateAccessRequired"], 0)
            self.assertEqual(limits["multiDrawIndirectRequired"], 0)
            self.assertEqual(limits["persistentUploadsRequired"], 0)

    def test_gl41_diagnostics_reject_accidental_gl43_gl44_gl45_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "switch.log"
            log.write_text(
                "\n".join(
                    [
                        "  product tier: GL41",
                        "  GL41 mac-modern executor: active yes, FBO postprocess no, UBO frame/object constants no, timer queries no, sync-aware uploads no, static buffer ownership no, dynamic buffer ownership no, macOS 4.1 ceiling no",
                        "  GL41 mac-modern support: material compiler no, common materials no, dynamic entities no, modern post chain no, scene-linear output no, high-quality SDR no, optional hardware HDR yes, screenshots yes, demos yes",
                        "  GL41 mac-modern GL4+ requirements: debug output yes, buffer storage yes, direct state access yes, multi-draw indirect yes, persistent uploads yes",
                    ]
                ),
                encoding="utf-8",
            )

            diagnostics = glx_runtime_sweep.analyze_glx_diagnostics(log, "glx-off")
            failures = "\n".join(diagnostics["failures"])

            self.assertIn("fboPostProcess", failures)
            self.assertIn("uboFrameObjectConstants", failures)
            self.assertIn("timerQueries", failures)
            self.assertIn("syncAwareUploads", failures)
            self.assertIn("staticBufferOwnership", failures)
            self.assertIn("dynamicBufferOwnership", failures)
            self.assertIn("macOS41Ceiling", failures)
            self.assertIn("materialCompiler", failures)
            self.assertIn("modernPostChain", failures)
            self.assertIn("sceneLinearOutput", failures)
            self.assertIn("highQualitySdr", failures)
            self.assertIn("debugOutputRequired", failures)
            self.assertIn("bufferStorageRequired", failures)
            self.assertIn("directStateAccessRequired", failures)
            self.assertIn("multiDrawIndirectRequired", failures)
            self.assertIn("persistentUploadsRequired", failures)

    def test_gl46_diagnostics_report_high_end_executor_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "switch.log"
            log.write_text(
                "\n".join(
                    [
                        "  product tier: GL46",
                        "  GL46 high-end executor: active yes, persistent uploads yes, buffer storage uploads yes, sync-heavy streaming yes, direct state access yes, multi-draw indirect yes, aggressive static-world submission yes, detailed GPU counters yes",
                        "  GL46 high-end support: material compiler yes, common materials yes, dynamic entities yes, modern post chain yes, scene-linear output yes, hardware HDR output yes, screenshots yes, demos yes",
                        "  GL46 high-end requirements: debug output yes, buffer storage yes, direct state access yes, multi-draw indirect yes",
                    ]
                ),
                encoding="utf-8",
            )

            diagnostics = glx_runtime_sweep.analyze_glx_diagnostics(log, "glx-off")
            executor = diagnostics["metrics"]["gl46Executor"]
            support = diagnostics["metrics"]["gl46Support"]
            requirements = diagnostics["metrics"]["gl46Requirements"]

            self.assertEqual(diagnostics["failures"], [])
            self.assertEqual(executor["active"], 1)
            self.assertEqual(executor["persistentUploads"], 1)
            self.assertEqual(executor["bufferStorageUploads"], 1)
            self.assertEqual(executor["syncHeavyStreaming"], 1)
            self.assertEqual(executor["directStateAccess"], 1)
            self.assertEqual(executor["multiDrawIndirect"], 1)
            self.assertEqual(executor["aggressiveStaticWorldSubmission"], 1)
            self.assertEqual(executor["detailedGpuCounters"], 1)
            self.assertEqual(support["hardwareHdrOutput"], 1)
            self.assertEqual(requirements["debugOutputRequired"], 1)
            self.assertEqual(requirements["bufferStorageRequired"], 1)
            self.assertEqual(requirements["directStateAccessRequired"], 1)
            self.assertEqual(requirements["multiDrawIndirectRequired"], 1)

    def test_gl46_diagnostics_reject_missing_high_end_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "switch.log"
            log.write_text(
                "\n".join(
                    [
                        "  product tier: GL46",
                        "  GL46 high-end executor: active yes, persistent uploads no, buffer storage uploads no, sync-heavy streaming no, direct state access no, multi-draw indirect no, aggressive static-world submission no, detailed GPU counters no",
                        "  GL46 high-end support: material compiler no, common materials no, dynamic entities no, modern post chain no, scene-linear output no, hardware HDR output no, screenshots yes, demos yes",
                        "  GL46 high-end requirements: debug output no, buffer storage no, direct state access no, multi-draw indirect no",
                    ]
                ),
                encoding="utf-8",
            )

            diagnostics = glx_runtime_sweep.analyze_glx_diagnostics(log, "glx-off")
            failures = "\n".join(diagnostics["failures"])

            self.assertIn("persistentUploads", failures)
            self.assertIn("bufferStorageUploads", failures)
            self.assertIn("syncHeavyStreaming", failures)
            self.assertIn("directStateAccess", failures)
            self.assertIn("multiDrawIndirect", failures)
            self.assertIn("aggressiveStaticWorldSubmission", failures)
            self.assertIn("detailedGpuCounters", failures)
            self.assertIn("materialCompiler", failures)
            self.assertIn("hardwareHdrOutput", failures)
            self.assertIn("debugOutputRequired", failures)
            self.assertIn("bufferStorageRequired", failures)
            self.assertIn("directStateAccessRequired", failures)
            self.assertIn("multiDrawIndirectRequired", failures)

    def test_glx_diagnostics_report_high_risk_stream_material_draws(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "switch.log"
            log.write_text(
                "\n".join(
                    [
                        "  dynamic stream draws: 3/3 attempts, 9 verts, 9 indexes, 0.01 MB, index 0.01 MB, tex1 0.00 MB, mt 0, fog 0, depthfrag 0, texmod 0, env 0, dlight 1, screen 1, video 1, shadow 0, beam 0, post 0, fallbacks 0",
                    ]
                ),
                encoding="utf-8",
            )

            diagnostics = glx_runtime_sweep.analyze_glx_diagnostics(log, "glx-parity")
            failures = "\n".join(diagnostics["failures"])
            stream_draw = diagnostics["metrics"]["streamDraw"]

            self.assertIn("dynamic-light", failures)
            self.assertIn("screen-map", failures)
            self.assertIn("video-map", failures)
            self.assertEqual(stream_draw["dynamicLights"], 1)
            self.assertEqual(stream_draw["screenMaps"], 1)
            self.assertEqual(stream_draw["videoMaps"], 1)

    def test_glx_diagnostics_report_material_program_stream_skip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "switch.log"
            log.write_text(
                "\n".join(
                    [
                        "  dynamic stream draw skips: 1 (bind 0, input 0, mt 0, depthfrag 0, texcoord 0, empty 0, key 0, fog 0, program 1)",
                    ]
                ),
                encoding="utf-8",
            )

            diagnostics = glx_runtime_sweep.analyze_glx_diagnostics(log, "glx-parity")
            failures = "\n".join(diagnostics["failures"])
            stream_draw = diagnostics["metrics"]["streamDraw"]
            stream_draw_skips = diagnostics["metrics"]["streamDrawSkip"]

            self.assertIn("material-program", failures)
            self.assertEqual(stream_draw["skips"], 1)
            self.assertEqual(stream_draw_skips["program"], 1)

    def test_glx_diagnostics_report_renderer_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "switch.log"
            log.write_text(
                "\n".join(
                    [
                        "  material renderer: enabled, ready no, GLSL 1.20",
                        "  material compiles: 1 attempts, 1 compile failures, 1 link failures, precache 1/1, bind failures 1, labels 0",
                        "  FBO: requested yes, ready no, programs yes, framebuffer funcs yes, reason: FBO creation failed",
                        "  FBO lifecycle: 1 init attempts, 0 ready, 1 failed, 0 disabled, 0 shutdowns",
                        "  bloom create: last fbo, 0/1 ready, texture-unit failures 0, FBO failures 1",
                        "  dynamic stream buffer: no",
                        "  dynamic stream uploads: 1 calls, 0.01 MB, failures 1",
                        "  dynamic stream reservation failures: 1",
                        "  static world GLx renderer: no, arena upload no, arena draw no",
                        "  static world GLx multidraw indirect: yes, 0/1 calls, 0 runs, 0 indexes, fallbacks 0, skips 0, errors 1, largest 0",
                    ]
                ),
                encoding="utf-8",
            )

            diagnostics = glx_runtime_sweep.analyze_glx_diagnostics(log, "glx-parity")
            failures = "\n".join(diagnostics["failures"])
            self.assertIn("material renderer", failures)
            self.assertIn("compile failures", failures)
            self.assertIn("FBO was requested", failures)
            self.assertIn("dynamic stream buffer", failures)
            self.assertIn("static world renderer", failures)

    def test_gate_evaluation_fails_on_diagnostic_failures(self) -> None:
        manifest = {
            "gate": "rc-parity",
            "dryRun": False,
            "runs": [
                {
                    "type": "switch-screenshots",
                    "status": "passed",
                    "screenshots": [
                        {"name": "shot", "found": True, "histogram": screenshot_histogram()},
                    ],
                    "diagnostics": {
                        "found": True,
                        "failures": ["GLx material compile failures: 1."],
                        "metrics": color_diagnostics_metrics(),
                    },
                },
                {
                    "type": "timedemo",
                    "status": "passed",
                    "renderer": "opengl",
                    "demo": "demo1",
                    "timedemoMetrics": {"fps": 100.0},
                },
                {
                    "type": "timedemo",
                    "status": "passed",
                    "renderer": "glx",
                    "demo": "demo1",
                    "timedemoMetrics": {"fps": 100.0},
                },
            ],
            "renderers": ["opengl", "glx"],
            "demos": ["demo1"],
        }

        failures = glx_runtime_sweep.evaluate_gate(manifest)
        self.assertTrue(any("GLx diagnostic failures" in failure for failure in failures))

    def test_gate_evaluation_requires_per_frame_color_metadata(self) -> None:
        metrics = color_diagnostics_metrics()
        metrics.pop("colorFrame")
        manifest = {
            "gate": "rc-smoke",
            "dryRun": False,
            "runs": [
                {
                    "type": "switch-screenshots",
                    "status": "passed",
                    "screenshots": [
                        {"name": "shot", "found": True, "histogram": screenshot_histogram()},
                    ],
                    "diagnostics": {
                        "found": True,
                        "failures": [],
                        "metrics": metrics,
                    },
                    "performance": locked_performance_sample(),
                },
            ],
            "renderers": ["opengl", "glx"],
            "demos": [],
        }

        failures = glx_runtime_sweep.evaluate_gate(manifest)
        self.assertTrue(any("colorFrame" in failure for failure in failures))

    def test_gate_evaluation_requires_detailed_performance_color_frame_metadata(self) -> None:
        performance = locked_performance_sample()
        performance["latest"].pop("colorFrameContractValid")
        manifest = {
            "gate": "rc-smoke",
            "dryRun": False,
            "runs": [
                {
                    "type": "switch-screenshots",
                    "status": "passed",
                    "screenshots": [
                        {"name": "shot", "found": True, "histogram": screenshot_histogram()},
                    ],
                    "diagnostics": {
                        "found": True,
                        "failures": [],
                        "metrics": color_diagnostics_metrics(),
                    },
                    "performance": performance,
                },
            ],
            "renderers": ["opengl", "glx"],
            "demos": [],
        }

        failures = glx_runtime_sweep.evaluate_gate(manifest)

        self.assertTrue(any("complete color-pipeline metadata" in failure for failure in failures))

    def test_release_gates_require_renderer_switch_lifecycle_evidence(self) -> None:
        manifest = release_proof_manifest("rc-smoke", "windows-x64")
        manifest.pop("rendererSwitchEvidence")

        failures = glx_runtime_sweep.evaluate_gate(manifest)

        self.assertTrue(
            any("No renderer-switch lifecycle evidence" in failure for failure in failures)
        )

    def test_renderer_switch_lifecycle_requires_completed_transitions(self) -> None:
        manifest = release_proof_manifest("rc-smoke", "windows-x64")
        switch_run = next(
            run for run in manifest["runs"] if run.get("type") == "switch-screenshots"
        )
        switch_run["screenshots"][0]["found"] = False
        manifest["rendererSwitchEvidence"] = (
            glx_runtime_sweep.renderer_switch_lifecycle_evidence(manifest)
        )

        failures = glx_runtime_sweep.evaluate_gate(manifest)

        self.assertTrue(
            any("did not complete every planned transition" in failure for failure in failures)
        )

    def test_renderer_switch_lifecycle_requires_round_trip_for_blocking_gates(self) -> None:
        manifest = release_proof_manifest("rc-proof", "windows-x64")
        switch_run = next(
            run for run in manifest["runs"] if run.get("type") == "switch-screenshots"
        )
        manifest["switchSequence"] = ["opengl", "glx"]
        switch_run["switchSequence"] = manifest["switchSequence"]
        switch_run["screenshots"] = [
            shot for shot in switch_run["screenshots"] if int(shot["switchStep"]) <= 2
        ]
        manifest["rendererSwitchEvidence"] = (
            glx_runtime_sweep.renderer_switch_lifecycle_evidence(manifest)
        )

        failures = glx_runtime_sweep.evaluate_gate(manifest)

        self.assertTrue(any("switch back out of GLx" in failure for failure in failures))

    def test_renderer_switch_lifecycle_records_restart_and_glx_leg_evidence(self) -> None:
        manifest = release_proof_manifest("rc-parity", "linux-x86_64")
        evidence = manifest["rendererSwitchEvidence"]

        self.assertEqual(evidence["status"], "passed")
        self.assertEqual(evidence["restartMode"], "fast")
        self.assertEqual(evidence["vidRestartPath"], "CL_Vid_Restart(REF_KEEP_WINDOW)")
        self.assertTrue(evidence["vidRestartEquivalent"])
        self.assertEqual(
            evidence["plannedTransitions"],
            len(manifest["maps"]) * manifest["switchRounds"] * len(manifest["switchSequence"]),
        )
        self.assertEqual(evidence["completedTransitions"], evidence["plannedTransitions"])
        self.assertGreater(evidence["transitionsIntoGlx"], 0)
        self.assertGreater(evidence["transitionsOutOfGlx"], 0)
        self.assertTrue(evidence["glxDiagnosticsFound"])
        self.assertGreater(evidence["glxPerformanceSamples"], 0)

    def test_world_proof_evidence_passes_for_blocking_rc_surface(self) -> None:
        manifest = release_proof_manifest("rc-proof", "windows-x64")
        evidence = manifest["worldProofEvidence"]

        self.assertEqual(evidence["version"], glx_runtime_sweep.GLX_WORLD_PROOF_VERSION)
        self.assertEqual(evidence["status"], "passed")
        self.assertIn("q3dm17", evidence["requiredMaps"])
        self.assertIn("q3dm15", evidence["requiredMaps"])
        self.assertIn("q3dm15", evidence["glxScreenshotMaps"])
        self.assertGreater(evidence["staticWorld"]["drawAttempts"], 0)
        self.assertEqual(evidence["staticWorld"]["drawFallbacks"], 0)
        self.assertTrue(evidence["lightmaps"]["ok"])
        self.assertTrue(evidence["fog"]["ok"])
        self.assertEqual(glx_runtime_sweep.evaluate_gate(manifest), [])

    def test_world_proof_evidence_requires_versioned_object(self) -> None:
        manifest = release_proof_manifest("rc-parity", "windows-x64")
        manifest.pop("worldProofEvidence")

        failures = glx_runtime_sweep.evaluate_gate(manifest)

        self.assertTrue(any("No world proof evidence" in failure for failure in failures))

    def test_world_proof_evidence_rejects_stale_version_and_missing_fog(self) -> None:
        manifest = release_proof_manifest("rc-proof", "windows-x64")
        requirements = glx_runtime_sweep.RC_GATE_PRESETS["rc-proof"]["requirements"]
        for run in manifest["runs"]:
            diagnostics = run.get("diagnostics")
            if isinstance(diagnostics, dict) and isinstance(diagnostics.get("metrics"), dict):
                metrics = diagnostics["metrics"]
                if isinstance(metrics.get("staticWorld"), dict):
                    metrics["staticWorld"].update(
                        {
                            "rendererEnabled": 0,
                            "arenaReady": 0,
                            "packetBatchBatches": 0,
                        }
                    )
                if isinstance(metrics.get("gl2xSupport"), dict):
                    metrics["gl2xSupport"].update({"lightmaps": 0, "fog": 0})
                if isinstance(metrics.get("gl12Support"), dict):
                    metrics["gl12Support"].update({"lightmaps": 0, "fog": 0})
                if isinstance(metrics.get("streamDraw"), dict):
                    metrics["streamDraw"]["fog"] = 0
                if isinstance(metrics.get("materialParameters"), dict):
                    metrics["materialParameters"].update({"blocks": 0, "hash": 0})

            performance = run.get("performance")
            if isinstance(performance, dict) and isinstance(performance.get("latest"), dict):
                performance["latest"].update(
                    {
                        "staticDrawAttempts": 0,
                        "staticDrawIndexes": 0,
                        "staticDrawPacketFull": 0,
                        "staticDrawPacketPartial": 0,
                        "streamDrawFog": 0,
                        "materialParameterBlocks": 0,
                        "materialParameterHash": 0,
                    }
                )

            for shot in run.get("screenshots", []):
                if (
                    isinstance(shot, dict)
                    and str(shot.get("renderer", "")).lower() == "glx"
                    and str(shot.get("map", "")).lower() == "q3dm15"
                ):
                    shot["found"] = False

        manifest["performanceAggregate"] = {"sampleCount": 1, "latest": {}, "max": {}}
        manifest["worldProofEvidence"] = glx_runtime_sweep.world_proof_evidence(
            manifest,
            requirements,
        )
        manifest["worldProofEvidence"]["version"] = 0
        failures = glx_runtime_sweep.evaluate_world_proof(manifest, requirements)
        text = "\n".join(failures)

        self.assertIn("unsupported version", text)
        self.assertIn("static-world renderer", text)
        self.assertIn("fog-heavy screenshot", text)
        self.assertIn("fog support", text)

    def test_material_proof_evidence_passes_for_rc_proof_surface(self) -> None:
        manifest = release_proof_manifest("rc-proof", "windows-x64")
        evidence = manifest["materialProofEvidence"]

        self.assertEqual(evidence["version"], glx_runtime_sweep.GLX_MATERIAL_PROOF_VERSION)
        self.assertEqual(evidence["status"], "passed")
        self.assertIn("q3dm11", evidence["requiredMaps"])
        self.assertEqual(evidence["renderer"]["enabled"], 1)
        self.assertEqual(evidence["renderer"]["ready"], 1)
        self.assertGreater(evidence["renderer"]["programs"], 0)
        self.assertGreater(evidence["parameters"]["blocks"], 0)
        self.assertGreater(evidence["parameters"]["hash"], 0)
        self.assertEqual(evidence["parameters"]["invalid"], 0)
        self.assertGreater(evidence["streamFeatures"]["multitexture"], 0)
        self.assertGreater(evidence["streamFeatures"]["depthFragment"], 0)
        self.assertGreater(evidence["streamFeatures"]["texMod"], 0)
        self.assertGreater(evidence["streamFeatures"]["environment"], 0)
        self.assertEqual(glx_runtime_sweep.evaluate_gate(manifest), [])

    def test_material_proof_evidence_proves_staged_animated_screen_video_surface(self) -> None:
        manifest = release_proof_manifest("rc-stress", "windows-x64")
        evidence = manifest["materialProofEvidence"]
        stage_flags = evidence["stageFlags"]

        self.assertEqual(evidence["status"], "passed")
        self.assertIn("animatedImage", evidence["requiredStageFlags"])
        self.assertIn("screenMap", evidence["requiredStageFlags"])
        self.assertIn("videoMap", evidence["requiredStageFlags"])
        self.assertGreater(stage_flags["counts"]["animatedImage"], 0)
        self.assertGreater(stage_flags["counts"]["screenMap"], 0)
        self.assertGreater(stage_flags["counts"]["videoMap"], 0)
        self.assertGreater(evidence["streamFeatures"]["screenMap"], 0)
        self.assertGreater(evidence["streamFeatures"]["videoMap"], 0)
        self.assertEqual(glx_runtime_sweep.evaluate_gate(manifest), [])

    def test_material_proof_evidence_keeps_screen_video_guarded_out_of_rc_proof(self) -> None:
        manifest = release_proof_manifest("rc-proof", "windows-x64")
        evidence = manifest["materialProofEvidence"]

        self.assertIn("screenMap", evidence["forbiddenStreamFeatures"])
        self.assertIn("videoMap", evidence["forbiddenStreamFeatures"])
        self.assertEqual(evidence["streamFeatures"]["screenMap"], 0)
        self.assertEqual(evidence["streamFeatures"]["videoMap"], 0)
        self.assertEqual(evidence["streamMaterialGates"]["screenMap"]["accepted"], 0)
        self.assertEqual(evidence["streamMaterialGates"]["videoMap"]["accepted"], 0)
        self.assertEqual(glx_runtime_sweep.evaluate_gate(manifest), [])

    def test_material_proof_evidence_requires_versioned_object(self) -> None:
        manifest = release_proof_manifest("rc-proof", "windows-x64")
        manifest.pop("materialProofEvidence")

        failures = glx_runtime_sweep.evaluate_gate(manifest)

        self.assertTrue(any("No material proof evidence" in failure for failure in failures))

    def test_material_proof_evidence_rejects_stale_version_and_unsafe_counters(self) -> None:
        manifest = release_proof_manifest("rc-proof", "windows-x64")
        requirements = glx_runtime_sweep.RC_GATE_PRESETS["rc-proof"]["requirements"]
        for run in manifest["runs"]:
            diagnostics = run.get("diagnostics")
            if isinstance(diagnostics, dict) and isinstance(diagnostics.get("metrics"), dict):
                metrics = diagnostics["metrics"]
                if isinstance(metrics.get("material"), dict):
                    metrics["material"].update(
                        {
                            "ready": 0,
                            "compile": 1,
                            "link": 1,
                            "precacheFailures": 1,
                            "bind": 1,
                        }
                    )
                if isinstance(metrics.get("materialCompilerPlans"), dict):
                    metrics["materialCompilerPlans"].update(
                        {"unsupported": 1, "lastUnsupported": 0x80}
                    )
                if isinstance(metrics.get("materialFallbacks"), dict):
                    metrics["materialFallbacks"].update({"disabled": 1})
                if isinstance(metrics.get("materialParameters"), dict):
                    metrics["materialParameters"].update(
                        {"blocks": 0, "invalid": 1, "hash": 0}
                    )
                if isinstance(metrics.get("streamDraw"), dict):
                    metrics["streamDraw"].update(
                        {
                            "multitexture": 0,
                            "depthFragment": 0,
                            "texMods": 0,
                            "environment": 0,
                            "fallbacks": 1,
                        }
                    )
                if isinstance(metrics.get("streamMaterialGate"), dict):
                    metrics["streamMaterialGate"].update(
                        {
                            "multitextureAccepted": 0,
                            "depthFragmentAccepted": 0,
                            "texModAccepted": 0,
                            "environmentAccepted": 0,
                        }
                    )

            performance = run.get("performance")
            if isinstance(performance, dict) and isinstance(performance.get("latest"), dict):
                performance["latest"].update(
                    {
                        "materialReady": "not-ready",
                        "materialPrograms": 0,
                        "materialCompileFailures": 1,
                        "materialLinkFailures": 1,
                        "materialPrecacheFailures": 1,
                        "materialBindFailures": 1,
                        "materialParameterBlocks": 0,
                        "materialParameterHash": 0,
                        "materialInvalidParameterBlocks": 1,
                        "streamDrawMultitexture": 0,
                        "streamDrawDepthFragment": 0,
                        "streamDrawTexMods": 0,
                        "streamDrawEnvironment": 0,
                        "streamDrawFallbacks": 1,
                    }
                )

        manifest["performanceAggregate"] = {"sampleCount": 1, "latest": {}, "max": {}}
        manifest["materialProofEvidence"] = glx_runtime_sweep.material_proof_evidence(
            manifest,
            requirements,
        )
        manifest["materialProofEvidence"]["version"] = 0
        failures = glx_runtime_sweep.evaluate_material_proof(manifest, requirements)
        text = "\n".join(failures)

        self.assertIn("unsupported version", text)
        self.assertIn("material renderer ready", text)
        self.assertIn("material failures", text)
        self.assertIn("disabled=1", text)
        self.assertIn("unsupported compiler plans", text)
        self.assertIn("invalid parameter blocks", text)
        self.assertIn("stream feature evidence", text)

    def test_material_proof_evidence_rejects_missing_staged_stage_flags_and_guards(self) -> None:
        manifest = release_proof_manifest("rc-stress", "windows-x64")
        requirements = glx_runtime_sweep.RC_GATE_PRESETS["rc-stress"]["requirements"]
        for run in manifest["runs"]:
            diagnostics = run.get("diagnostics")
            if isinstance(diagnostics, dict) and isinstance(diagnostics.get("metrics"), dict):
                metrics = diagnostics["metrics"]
                if isinstance(metrics.get("materialParameters"), dict):
                    metrics["materialParameters"]["flags"] = 0x0C23
                    metrics["materialParameters"]["features"] = 0x0C23
                if isinstance(metrics.get("materialLastKey"), dict):
                    metrics["materialLastKey"]["flags"] = 0x0C23
                if isinstance(metrics.get("materialLanguage"), dict):
                    metrics["materialLanguage"]["flags"] = 0x0C23
                if isinstance(metrics.get("materialStageFlags"), dict):
                    metrics["materialStageFlags"]["animatedImage"] = 0
                    metrics["materialStageFlags"]["screenMap"] = 0
                    metrics["materialStageFlags"]["videoMap"] = 0
                if isinstance(metrics.get("streamDraw"), dict):
                    metrics["streamDraw"]["screenMaps"] = 0
                    metrics["streamDraw"]["videoMaps"] = 0
                metrics.pop("streamMaterialGate", None)

        manifest["performanceAggregate"] = {"sampleCount": 1, "latest": {}, "max": {}}
        manifest["materialProofEvidence"] = glx_runtime_sweep.material_proof_evidence(
            manifest,
            requirements,
        )
        failures = glx_runtime_sweep.evaluate_material_proof(manifest, requirements)
        text = "\n".join(failures)

        self.assertIn("stage-flag evidence", text)
        self.assertIn("animatedImage", text)
        self.assertIn("screenMap", text)
        self.assertIn("videoMap", text)
        self.assertIn("stream feature evidence", text)
        self.assertIn("stream guard evidence", text)

    def test_dynamic_proof_evidence_passes_for_rc_proof_surface(self) -> None:
        manifest = release_proof_manifest("rc-proof", "windows-x64")
        evidence = manifest["dynamicProofEvidence"]

        self.assertEqual(evidence["version"], glx_runtime_sweep.GLX_DYNAMIC_PROOF_VERSION)
        self.assertEqual(evidence["status"], "passed")
        self.assertIn("q3dm1", evidence["requiredMaps"])
        self.assertIn("q3dm6", evidence["requiredMaps"])
        self.assertIn("demo1", evidence["requiredDemos"])
        self.assertGreater(evidence["streamCategories"]["entity"]["draws"], 0)
        self.assertGreater(evidence["streamCategories"]["weapon"]["draws"], 0)
        self.assertGreater(evidence["streamFeatures"]["shadow"], 0)
        self.assertEqual(evidence["streamFeatures"]["dynamicLight"], 0)
        self.assertIn("GL2X", evidence["tierSupport"]["dynamicEntities"])
        self.assertIn("GL12", evidence["tierSupport"]["dynamicLights"])
        self.assertEqual(evidence["streamGuards"]["dynamicLight"]["accepted"], 0)
        self.assertEqual(glx_runtime_sweep.evaluate_gate(manifest), [])

    def test_dynamic_proof_evidence_proves_staged_particles_and_beams(self) -> None:
        manifest = release_proof_manifest("rc-stress", "windows-x64")
        evidence = manifest["dynamicProofEvidence"]

        self.assertEqual(evidence["status"], "passed")
        self.assertIn("fnq3_glx_particles01", evidence["requiredDemos"])
        self.assertGreater(evidence["streamCategories"]["particle"]["draws"], 0)
        self.assertGreater(evidence["streamCategories"]["poly"]["draws"], 0)
        self.assertGreater(evidence["streamCategories"]["mark"]["draws"], 0)
        self.assertGreater(evidence["streamCategories"]["beam"]["draws"], 0)
        self.assertGreater(evidence["streamFeatures"]["beam"], 0)
        self.assertEqual(evidence["streamFeatures"]["dynamicLight"], 0)
        self.assertEqual(glx_runtime_sweep.evaluate_gate(manifest), [])

    def test_dynamic_proof_evidence_requires_versioned_object(self) -> None:
        manifest = release_proof_manifest("rc-proof", "windows-x64")
        manifest.pop("dynamicProofEvidence")

        failures = glx_runtime_sweep.evaluate_gate(manifest)

        self.assertTrue(any("No dynamic proof evidence" in failure for failure in failures))

    def test_dynamic_proof_rejects_stale_version_and_unsafe_counters(self) -> None:
        manifest = release_proof_manifest("rc-proof", "windows-x64")
        requirements = glx_runtime_sweep.RC_GATE_PRESETS["rc-proof"]["requirements"]
        for run in manifest["runs"]:
            diagnostics = run.get("diagnostics")
            if isinstance(diagnostics, dict) and isinstance(diagnostics.get("metrics"), dict):
                metrics = diagnostics["metrics"]
                if isinstance(metrics.get("gl12Support"), dict):
                    metrics["gl12Support"].update(  # type: ignore[index, union-attr]
                        {
                            "sprites": 0,
                            "dynamicLights": 0,
                            "stencilShadows": 0,
                        }
                    )
                if isinstance(metrics.get("gl2xSupport"), dict):
                    metrics["gl2xSupport"].update(  # type: ignore[index, union-attr]
                        {
                            "dynamicEntities": 0,
                            "sprites": 0,
                        }
                    )
                if isinstance(metrics.get("streamDraw"), dict):
                    metrics["streamDraw"].update(  # type: ignore[index, union-attr]
                        {
                            "draws": 0,
                            "attempts": 0,
                            "indexes": 0,
                            "dynamicLights": 1,
                            "shadows": 0,
                            "fallbacks": 1,
                            "skips": 1,
                        }
                    )
                if isinstance(metrics.get("streamCategory"), dict):
                    metrics["streamCategory"].update(  # type: ignore[index, union-attr]
                        {
                            "entityDraws": 0,
                            "entityAttempts": 0,
                            "entityFallbacks": 1,
                            "weaponDraws": 0,
                            "weaponAttempts": 0,
                        }
                    )
                if isinstance(metrics.get("streamMaterialGate"), dict):
                    metrics["streamMaterialGate"].update(  # type: ignore[index, union-attr]
                        {
                            "dynamicLightEnabled": 1,
                            "dynamicLightAccepted": 1,
                            "dynamicLightRejected": 0,
                        }
                    )

            performance = run.get("performance")
            if isinstance(performance, dict) and isinstance(performance.get("latest"), dict):
                performance["latest"].update(
                    {
                        "draws": 0,
                        "streamDrawAttempts": 0,
                        "streamDrawIndexes": 0,
                        "streamDrawDynamicLights": 1,
                        "streamDrawShadows": 0,
                        "streamDrawFallbacks": 1,
                        "streamDrawSkips": 1,
                        "streamCategoryEntityDraws": 0,
                        "streamCategoryEntityAttempts": 0,
                        "streamCategoryWeaponDraws": 0,
                        "streamCategoryWeaponAttempts": 0,
                    }
                )

        manifest["performanceAggregate"] = {"sampleCount": 1, "latest": {}, "max": {}}
        manifest["dynamicProofEvidence"] = glx_runtime_sweep.dynamic_proof_evidence(
            manifest,
            requirements,
        )
        manifest["dynamicProofEvidence"]["version"] = 0
        failures = glx_runtime_sweep.evaluate_dynamic_proof(manifest, requirements)
        text = "\n".join(failures)

        self.assertIn("unsupported version", text)
        self.assertIn("stream category evidence", text)
        self.assertIn("stream feature evidence", text)
        self.assertIn("tier-support evidence", text)
        self.assertIn("accepted forbidden", text)
        self.assertIn("high-risk stream draws", text)
        self.assertIn("stream draw fallbacks", text)
        self.assertIn("stream draw skips", text)

    def test_post_proof_evidence_passes_for_rc_proof_surface(self) -> None:
        manifest = release_proof_manifest("rc-proof", "windows-x64")
        evidence = manifest["postProofEvidence"]

        self.assertEqual(evidence["version"], glx_runtime_sweep.GLX_POST_PROOF_VERSION)
        self.assertEqual(evidence["status"], "passed")
        self.assertIn("q3dm1", evidence["requiredMaps"])
        self.assertIn("q3dm17", evidence["requiredMaps"])
        self.assertIn("q3dm1", evidence["glxScreenshotMaps"])
        self.assertIn("q3dm17", evidence["glxScreenshotMaps"])
        self.assertEqual(evidence["fbo"]["requested"], 1)
        self.assertEqual(evidence["fbo"]["ready"], 1)
        self.assertEqual(evidence["fbo"]["initFailures"], 0)
        self.assertGreater(evidence["frames"]["post"], 0)
        self.assertGreater(evidence["frames"]["screenshots"], 0)
        self.assertEqual(evidence["frames"]["minimizedOutput"], 0)
        self.assertTrue(evidence["featureEvidence"]["greyscale"]["ok"])
        self.assertTrue(evidence["featureEvidence"]["renderScale"]["ok"])
        self.assertTrue(evidence["featureEvidence"]["renderScale"]["dimensionEvidence"])
        self.assertEqual(evidence["colorContract"], 1)
        self.assertEqual(glx_runtime_sweep.evaluate_gate(manifest), [])

    def test_post_proof_evidence_requires_versioned_object(self) -> None:
        manifest = release_proof_manifest("rc-proof", "windows-x64")
        manifest.pop("postProofEvidence")

        failures = glx_runtime_sweep.evaluate_gate(manifest)

        self.assertTrue(any("No post proof evidence" in failure for failure in failures))

    def test_post_proof_rejects_stale_version_and_missing_feature_evidence(self) -> None:
        manifest = release_proof_manifest("rc-proof", "windows-x64")
        requirements = glx_runtime_sweep.RC_GATE_PRESETS["rc-proof"]["requirements"]
        for run in manifest["runs"]:
            diagnostics = run.get("diagnostics")
            if isinstance(diagnostics, dict) and isinstance(diagnostics.get("metrics"), dict):
                metrics = diagnostics["metrics"]
                if isinstance(metrics.get("postprocess"), dict):
                    metrics["postprocess"].update(
                        {
                            "fboRequested": 1,
                            "fboReady": 0,
                            "fboAttempts": 1,
                            "fboFailed": 1,
                            "lastOutput": "minimized",
                        }
                    )
                if isinstance(metrics.get("postprocessControls"), dict):
                    metrics["postprocessControls"].update(
                        {
                            "renderScale": 0,
                            "greyscale": 0.0,
                            "windowAdjusted": 0,
                        }
                    )
                if isinstance(metrics.get("postprocessFrames"), dict):
                    metrics["postprocessFrames"].update(
                        {
                            "frames": 0,
                            "screenshots": 0,
                            "minimizedOutput": 1,
                        }
                    )
                if isinstance(metrics.get("postprocessFrameFeatures"), dict):
                    metrics["postprocessFrameFeatures"].update(
                        {
                            "renderScale": 0,
                            "greyscale": 0,
                            "windowAdjusted": 0,
                            "minimized": 1,
                        }
                    )
                if isinstance(metrics.get("targetFormat"), dict):
                    metrics["targetFormat"].update(
                        {
                            "renderWidth": 640,
                            "renderHeight": 480,
                            "captureWidth": 640,
                            "captureHeight": 480,
                            "windowWidth": 640,
                            "windowHeight": 480,
                        }
                    )
                if isinstance(metrics.get("colorAudit"), dict):
                    metrics["colorAudit"]["contract"] = 0

            performance = run.get("performance")
            if isinstance(performance, dict) and isinstance(performance.get("latest"), dict):
                performance["latest"].update(
                    {
                        "fbo": "failed",
                        "postprocessRenderScaleMode": 0,
                        "postprocessGreyscale": 0,
                        "postprocessWindowAdjusted": 0,
                        "postprocessFrames": 0,
                        "postprocessScreenshots": 0,
                        "postprocessMinimizedOutput": 1,
                        "postprocessFeatureRenderScale": 0,
                        "postprocessFeatureGreyscale": 0,
                        "postprocessFeatureWindowAdjusted": 0,
                        "postprocessFeatureMinimized": 1,
                        "targetRenderWidth": 640,
                        "targetRenderHeight": 480,
                        "targetCaptureWidth": 640,
                        "targetCaptureHeight": 480,
                        "targetWindowWidth": 640,
                        "targetWindowHeight": 480,
                        "colorOutputContract": 0,
                    }
                )

        manifest["postProofEvidence"] = glx_runtime_sweep.post_proof_evidence(
            manifest,
            requirements,
        )
        manifest["postProofEvidence"]["version"] = 0
        failures = glx_runtime_sweep.evaluate_post_proof(manifest, requirements)
        text = "\n".join(failures)

        self.assertIn("unsupported version", text)
        self.assertIn("ready postprocess FBO", text)
        self.assertIn("FBO init failures", text)
        self.assertIn("postprocess frames", text)
        self.assertIn("feature evidence", text)
        self.assertIn("greyscale", text)
        self.assertIn("renderScale", text)
        self.assertIn("minimized output", text)
        self.assertIn("valid output color contract", text)

    def test_color_sweep_rejects_frame_dump_that_disagrees_with_row(self) -> None:
        manifest = release_proof_manifest("rc-parity", "windows-x64")
        color_run = next(
            run
            for run in manifest["runs"]
            if run.get("type") == "color-sweep"
            and run["colorSweepRow"]["id"] == "scene-linear-sdr-aces"
        )
        color_frame = color_run["diagnostics"]["metrics"]["colorFrame"]["latest"]
        color_frame["space"] = "display-referred-sdr"

        failures = glx_runtime_sweep.evaluate_gate(manifest)

        self.assertTrue(any("colorFrame.space" in failure for failure in failures))

    def test_color_sweep_rejects_invalid_frame_contract(self) -> None:
        manifest = release_proof_manifest("rc-parity", "windows-x64")
        color_run = next(
            run
            for run in manifest["runs"]
            if run.get("type") == "color-sweep"
            and run["colorSweepRow"]["id"] == "scene-linear-sdr-aces"
        )
        color_frame = color_run["diagnostics"]["metrics"]["colorFrame"]["latest"]
        color_frame["contractValid"] = False

        failures = glx_runtime_sweep.evaluate_gate(manifest)

        self.assertTrue(any("colorFrame.contractValid" in failure for failure in failures))

    def test_color_sweep_rejects_srgb_decode_state_drift(self) -> None:
        manifest = release_proof_manifest("rc-parity", "windows-x64")
        color_run = next(
            run
            for run in manifest["runs"]
            if run.get("type") == "color-sweep"
            and run["colorSweepRow"]["id"] == "hdr-srgb-decode-off"
        )
        metrics = color_run["diagnostics"]["metrics"]
        metrics["colorAudit"]["srgbDecode"] = 1
        metrics["colorFrame"]["latest"]["srgbDecode"] = True

        failures = glx_runtime_sweep.evaluate_gate(manifest)

        self.assertTrue(any("colorAudit.srgbDecode" in failure for failure in failures))
        self.assertTrue(any("colorFrame.srgbDecode" in failure for failure in failures))

    def test_color_contract_rejects_texture_classification_policy_drift(self) -> None:
        contracts = color_contracts()
        manifest_rows = contracts["textureClassificationManifest"]["rows"]
        authored = next(row for row in manifest_rows if row["id"] == "authored-color")
        authored["sceneLinearDecode"] = "never"

        failures = glx_runtime_sweep.validate_color_contract_manifest(
            {"colorContracts": contracts}
        )

        self.assertTrue(any("authored-color sceneLinearDecode" in failure for failure in failures))

    def test_color_sweep_requires_luma_false_color_sidecars(self) -> None:
        manifest = release_proof_manifest("rc-parity", "windows-x64")
        color_run = next(
            run
            for run in manifest["runs"]
            if run.get("type") == "color-sweep"
        )
        color_run["screenshots"][0].pop("falseColor")

        failures = glx_runtime_sweep.evaluate_gate(manifest)

        self.assertTrue(any("luma false-color sidecar" in failure for failure in failures))

    def test_color_sweep_requires_exposure_false_color_sidecars(self) -> None:
        manifest = release_proof_manifest("rc-parity", "windows-x64")
        color_run = next(
            run
            for run in manifest["runs"]
            if run.get("type") == "color-sweep"
        )
        color_run["screenshots"][0].pop("exposureFalseColor")

        failures = glx_runtime_sweep.evaluate_gate(manifest)

        self.assertTrue(any("exposure false-color sidecar" in failure for failure in failures))

    def test_color_sweep_requires_shader_reference_ramps(self) -> None:
        manifest = release_proof_manifest("rc-parity", "windows-x64")
        manifest["imageEvidence"]["shaderReferenceRamps"].pop()

        failures = glx_runtime_sweep.evaluate_gate(manifest)

        self.assertTrue(any("shader-vs-reference ramp evidence" in failure for failure in failures))


class GlxRuntimeSweepProfileTests(unittest.TestCase):
    def test_frozen_profiles_match_runtime_module_table(self) -> None:
        runtime_profiles = parse_runtime_glx_profiles()

        self.assertEqual(glx_runtime_sweep.GLX_RC_PROFILE_CVARS, runtime_profiles["rc"])
        self.assertEqual(glx_runtime_sweep.GLX_STRESS_PROFILE_CVARS, runtime_profiles["stress"])
        self.assertEqual(
            glx_runtime_sweep.PROFILE_CVARS["glx-parity"],
            {"r_glxProfile": "rc", **glx_runtime_sweep.GLX_RC_PROFILE_CVARS},
        )
        self.assertEqual(
            glx_runtime_sweep.PROFILE_CVARS["glx-ownership"],
            {
                "r_glxProfile": "rc",
                **glx_runtime_sweep.GLX_RC_PROFILE_CVARS,
                "r_glxRequireOwnership": "1",
            },
        )
        self.assertEqual(
            glx_runtime_sweep.PROFILE_CVARS["glx-stress"],
            {"r_glxProfile": "stress", **glx_runtime_sweep.GLX_STRESS_PROFILE_CVARS},
        )

    def test_official_proof_corpus_covers_task_o_scene_families(self) -> None:
        all_tags = set(glx_runtime_sweep.corpus_tags(glx_runtime_sweep.GLX_PROOF_CORPUS_SCENES))
        self.assertTrue(
            {
                "stock-map",
                "high-geometry",
                "shader-heavy",
                "fog-heavy",
                "modern-map",
                "particle-heavy-demo",
                "ui-hud-sensitive",
                "color-grade-proof",
                "tone-map-proof",
                "screenshot-parity",
                "demo-playback-parity",
                "hud-parity",
                "shadow-parity",
                "bloom-parity",
                "cel-shading-parity",
                "outline-parity",
                "greyscale-proof",
                "render-scale-proof",
                "performance-comparison",
            }.issubset(all_tags)
        )

        stress_tags = set(
            glx_runtime_sweep.corpus_tags(
                glx_runtime_sweep.GLX_GATE_CORPUS_SCENES["rc-stress"]
            )
        )
        self.assertTrue({"modern-map", "particle-heavy-demo"}.issubset(stress_tags))
        self.assertEqual(
            glx_runtime_sweep.PROFILE_MAPS["glx-color"],
            "q3dm17,q3dm11,q3dm15",
        )
        self.assertEqual(
            glx_runtime_sweep.PROFILE_MAPS["glx-material"],
            "q3dm1,q3dm11",
        )
        self.assertEqual(glx_runtime_sweep.PROFILE_CVARS["glx-color"]["r_colorGrade"], "3")

    def test_task_v_parity_suites_are_versioned_and_gate_enforced(self) -> None:
        required_suites = (
            "screenshot",
            "demo-playback",
            "hud",
            "shadow",
            "bloom",
            "cel-shading",
            "greyscale",
            "render-scale",
        )
        self.assertEqual(set(glx_runtime_sweep.GLX_PARITY_SUITES), set(required_suites))

        proof_corpus = proof_corpus_for_gate("rc-proof")
        self.assertEqual(
            proof_corpus["paritySuiteVersion"],
            glx_runtime_sweep.GLX_PARITY_SUITE_VERSION,
        )
        self.assertEqual(
            set(proof_corpus["paritySuiteIds"]),
            set(glx_runtime_sweep.GLX_GATE_PARITY_SUITES["rc-proof"]),
        )
        self.assertTrue(
            all(
                set(record["sceneIds"]).issubset(set(proof_corpus["selectedSceneIds"]))
                for record in proof_corpus["paritySuites"]
            )
        )

        switch_args = argparse.Namespace(
            startup_wait=1,
            map_wait=1,
            switch_wait=1,
            screenshot_wait=1,
            perf_sample_wait=0,
            switch_rounds=1,
            profile="glx-parity",
            no_perf_samples=True,
        )
        switch_cfg, expected_shots = glx_runtime_sweep.build_switch_cfg(
            switch_args,
            {},
            ["q3dm6", "q3dm11"],
            ["opengl", "glx"],
            "parity-suite-test",
            "gs12345678",
            glx_runtime_sweep.GLX_GATE_CORPUS_SCENES["rc-proof"],
            glx_runtime_sweep.GLX_GATE_PARITY_SUITES["rc-proof"],
        )
        self.assertIn('set cg_shadows "2"', switch_cfg)
        self.assertIn('set r_celShading "1"', switch_cfg)
        q3dm6_shots = [shot for shot in expected_shots if shot["map"] == "q3dm6"]
        q3dm11_shots = [shot for shot in expected_shots if shot["map"] == "q3dm11"]
        self.assertTrue(all("shadow" in shot["paritySuiteIds"] for shot in q3dm6_shots))
        self.assertTrue(all("cel-shading" in shot["paritySuiteIds"] for shot in q3dm11_shots))

        broken = dict(proof_corpus)
        broken["paritySuiteIds"] = ["screenshot"]
        broken["paritySuites"] = glx_runtime_sweep.parity_suite_records(["screenshot"])
        manifest = {
            "proofCorpus": broken,
            "maps": glx_runtime_sweep.corpus_targets(
                glx_runtime_sweep.GLX_GATE_CORPUS_SCENES["rc-proof"],
                "map",
            ),
            "demos": ["demo1"],
        }
        failures = glx_runtime_sweep.evaluate_proof_corpus(
            manifest,
            glx_runtime_sweep.RC_GATE_PRESETS["rc-proof"]["requirements"],
        )
        self.assertTrue(any("parity suite(s) missing" in failure for failure in failures))

    def test_gate_presets_derive_scene_targets_from_proof_corpus(self) -> None:
        for gate, scene_ids in glx_runtime_sweep.GLX_GATE_CORPUS_SCENES.items():
            with self.subTest(gate=gate):
                defaults = glx_runtime_sweep.RC_GATE_PRESETS[gate]["defaults"]
                self.assertEqual(
                    defaults["corpus_scenes"],
                    glx_runtime_sweep.corpus_scene_ids_csv(scene_ids),
                )
                self.assertEqual(
                    defaults["maps"],
                    glx_runtime_sweep.corpus_targets_csv(scene_ids, "map"),
                )
                self.assertEqual(
                    defaults["demos"],
                    glx_runtime_sweep.corpus_targets_csv(scene_ids, "demo"),
                )

    def test_corpus_manifest_is_gate_enforced(self) -> None:
        proof_corpus = proof_corpus_for_gate("rc-proof")

        self.assertEqual(proof_corpus["version"], glx_runtime_sweep.GLX_PROOF_CORPUS_VERSION)
        self.assertEqual(proof_corpus["document"], glx_runtime_sweep.GLX_PROOF_CORPUS_DOC)
        self.assertIn("stock-q3dm6-geometry", proof_corpus["selectedSceneIds"])
        self.assertIn("fog-heavy", proof_corpus["selectedTags"])

        broken = dict(proof_corpus)
        broken["selectedTags"] = ["stock-map"]
        manifest = {
            "proofCorpus": broken,
            "maps": glx_runtime_sweep.corpus_targets(
                glx_runtime_sweep.GLX_GATE_CORPUS_SCENES["rc-proof"],
                "map",
            ),
            "demos": ["demo1"],
        }
        failures = glx_runtime_sweep.evaluate_proof_corpus(
            manifest,
            glx_runtime_sweep.RC_GATE_PRESETS["rc-proof"]["requirements"],
        )
        self.assertTrue(any("missing required tag" in failure for failure in failures))

    def test_frozen_rc_profile_promotes_static_world_acceleration(self) -> None:
        profile = glx_runtime_sweep.GLX_RC_PROFILE_CVARS

        self.assertEqual(profile["r_glxWorldRenderer"], "1")
        self.assertEqual(profile["r_glxStreamDraw"], "1")
        self.assertEqual(profile["r_glxMaterialRenderer"], "1")
        self.assertEqual(profile["r_glxMaterialPrecache"], "1")
        self.assertEqual(profile["r_glxStaticWorldArena"], "1")
        self.assertEqual(profile["r_glxStaticWorldArenaDraw"], "1")
        self.assertEqual(profile["r_glxStaticWorldDraw"], "1")
        self.assertEqual(profile["r_glxStaticWorldSoftDraw"], "1")
        self.assertEqual(profile["r_glxStaticWorldPacketBatch"], "1")
        self.assertEqual(profile["r_glxStaticWorldMultiDraw"], "1")
        self.assertEqual(profile["r_glxStaticWorldIndirectBuffer"], "1")
        self.assertEqual(profile["r_glxStaticWorldIndirectDraw"], "1")
        self.assertEqual(profile["r_glxStaticWorldMultiDrawIndirect"], "1")
        self.assertEqual(profile["r_glxStaticWorldMultiDrawIndirectCompact"], "0")
        self.assertEqual(profile["r_glxStaticWorldMultiDrawIndirectSpans"], "1")

    def test_stress_profile_only_adds_compact_static_world_mdi(self) -> None:
        rc_profile = dict(glx_runtime_sweep.GLX_RC_PROFILE_CVARS)
        stress_profile = dict(glx_runtime_sweep.GLX_STRESS_PROFILE_CVARS)

        rc_profile["r_glxStaticWorldMultiDrawIndirectCompact"] = "1"
        self.assertEqual(stress_profile, rc_profile)

    def test_material_profile_requests_compile_cache_stress(self) -> None:
        profile = glx_runtime_sweep.PROFILE_CVARS["glx-material"]

        self.assertEqual(profile["r_glxMaterialRenderer"], "1")
        self.assertEqual(profile["r_glxMaterialPrecache"], "1")
        self.assertEqual(profile["r_glxGpuTiming"], "1")
        self.assertEqual(profile["r_glxGpuPassTiming"], "1")

    def test_diagnostic_gates_force_per_frame_color_debug(self) -> None:
        args = argparse.Namespace(
            width=640,
            height=480,
            profile="glx-parity",
            gate="rc-smoke",
            extra_set=[],
        )
        cvars = glx_runtime_sweep.make_cvars(args)
        self.assertEqual(cvars["r_glxColorPipelineDebug"], "2")

        args.extra_set = ["r_glxColorPipelineDebug=0"]
        cvars = glx_runtime_sweep.make_cvars(args)
        self.assertEqual(cvars["r_glxColorPipelineDebug"], "0")

    def test_rc_parity_gate_enables_dlight_shadow_scenes(self) -> None:
        defaults = glx_runtime_sweep.RC_GATE_PRESETS["rc-parity"]["defaults"]
        requirements = glx_runtime_sweep.RC_GATE_PRESETS["rc-parity"]["requirements"]

        self.assertTrue(defaults["dlight_shadow_scenes"])
        self.assertTrue(requirements["require_dlight_shadow_scenes"])

    def test_dlight_shadow_config_uses_startup_cvars_and_test_lights(self) -> None:
        args = argparse.Namespace(
            startup_wait=1,
            map_wait=1,
            screenshot_wait=1,
            perf_sample_wait=1,
            profile="glx-parity",
            no_perf_samples=False,
        )
        cvars = glx_runtime_sweep.dlight_shadow_scene_cvars({"r_fbo": "1"})
        startup = glx_runtime_sweep.launch_cvars(cvars)
        scenes = glx_runtime_sweep.dlight_shadow_evidence_scenes()

        cfg, expected_shots = glx_runtime_sweep.build_dlight_shadow_cfg(
            args,
            cvars,
            scenes,
            "shadow-test",
            "gs12345678",
        )

        self.assertEqual(startup["r_dlightShadows"], "1")
        self.assertEqual(startup["r_dlightShadowMaxLights"], "8")
        self.assertIn("echo DLIGHT_SHADOW_SCENE_BEGIN world-geometry", cfg)
        self.assertIn("devmap q3dm6", cfg)
        self.assertIn("devmap q3dm11", cfg)
        self.assertIn("r_dlightTest 8 720 224 48 0", cfg)
        self.assertIn("r_dlightTest 16 900 256 72 0", cfg)
        self.assertIn("set r_speeds \"4\"", cfg)
        self.assertTrue(all(shot["shadowScene"] for shot in expected_shots))
        self.assertEqual(
            glx_runtime_sweep.dlight_shadow_scene_categories(expected_shots),
            set(glx_runtime_sweep.DLIGHT_SHADOW_EVIDENCE_CATEGORIES),
        )
        self.assertTrue(
            any(
                shot["baselineKey"] == "glx-parity-dlight-shadows-stress-light-budget-q3dm6-glx"
                for shot in expected_shots
            )
        )

    def test_dlight_shadow_log_analysis_extracts_active_samples(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "glx.log"
            log.write_text(
                "\n".join(
                    [
                        "DLIGHT_SHADOW_SCENE_BEGIN world-geometry",
                        "dlight shadows plan:2/4 cand:3 atlas:1024x512/128 fill:75% "
                        "render lights:2 faces:10 batches:5 draws:5 surfs:20 cpu:1ms",
                        "DLIGHT_SHADOW_SCENE_END world-geometry",
                    ]
                ),
                encoding="utf-8",
            )

            analysis = glx_runtime_sweep.analyze_dlight_shadow_log(log)

        self.assertTrue(analysis["found"])
        self.assertEqual(analysis["max"]["planned"], 2)
        self.assertEqual(analysis["max"]["renderLights"], 2)
        self.assertEqual(analysis["scenes"]["world-geometry"]["max"]["planned"], 2)

    def test_gate_evaluation_requires_dlight_shadow_scene_evidence(self) -> None:
        manifest = release_proof_manifest("rc-parity", "linux-x86_64")
        manifest["runs"] = [
            run for run in manifest["runs"] if run.get("type") != "dlight-shadow-scenes"
        ]

        failures = glx_runtime_sweep.evaluate_gate(manifest)

        self.assertTrue(any("dlight shadow scene run" in failure for failure in failures))

    def test_gate_evaluation_requires_dlight_shadow_category_evidence(self) -> None:
        manifest = release_proof_manifest("rc-parity", "linux-x86_64")
        shadow_run = next(
            run for run in manifest["runs"] if run.get("type") == "dlight-shadow-scenes"
        )
        shadow_run["screenshots"] = [
            shot for shot in shadow_run["screenshots"]
            if shot.get("evidenceCategories") != ["stress-light-budget"]
        ]
        shadow_run["dlightShadow"]["scenes"].pop("stress-light-budget")

        failures = glx_runtime_sweep.evaluate_gate(manifest)

        self.assertTrue(any("stress-light-budget" in failure for failure in failures))

    def test_ownership_profile_preserves_independent_ownership_cvar(self) -> None:
        profile = dict(glx_runtime_sweep.PROFILE_CVARS["glx-ownership"])
        args = argparse.Namespace(profile="glx-ownership")

        startup = glx_runtime_sweep.launch_cvars(profile)
        filtered = glx_runtime_sweep.config_cvars(args, profile)

        self.assertEqual(startup["r_glxRequireOwnership"], "1")
        self.assertEqual(filtered["r_glxRequireOwnership"], "1")
        self.assertNotIn("r_glxStreamDraw", filtered)
        self.assertEqual(profile["r_glxStreamDrawDynamicLights"], "0")
        self.assertEqual(profile["r_glxStreamDrawScreenMaps"], "0")
        self.assertEqual(profile["r_glxStreamDrawVideoMaps"], "0")

    def test_proof_dir_defaults_wire_visual_and_performance_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = argparse.Namespace(
                proof_dir=root / "proof",
                approve_proof=False,
                screenshot_baseline_dir=None,
                screenshot_diff_dir=None,
                approve_screenshot_baselines=False,
                performance_baseline=None,
                approve_performance_baseline=False,
                summary_markdown=None,
            )

            glx_runtime_sweep.apply_proof_defaults(args, root / "run")

            self.assertEqual(args.screenshot_baseline_dir, root / "proof" / "screenshots")
            self.assertEqual(args.screenshot_diff_dir, root / "run" / "screenshot-diffs")
            self.assertEqual(args.performance_baseline, root / "proof" / "performance-baseline.json")
            self.assertEqual(args.summary_markdown, root / "run" / "summary.md")

    def test_proof_dir_defaults_support_individual_approval_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = argparse.Namespace(
                proof_dir=root / "proof",
                approve_proof=False,
                screenshot_baseline_dir=None,
                screenshot_diff_dir=None,
                approve_screenshot_baselines=True,
                performance_baseline=None,
                approve_performance_baseline=True,
                summary_markdown=None,
            )

            glx_runtime_sweep.apply_proof_defaults(args, root / "run")

            self.assertEqual(args.screenshot_baseline_dir, root / "proof" / "screenshots")
            self.assertIsNone(args.screenshot_diff_dir)
            self.assertEqual(args.performance_baseline, root / "proof" / "performance-baseline.json")
            self.assertEqual(args.summary_markdown, root / "run" / "summary.md")

    def test_rc_proof_approval_mode_is_rejected_before_runtime_work(self) -> None:
        args = argparse.Namespace(
            gate="rc-proof",
            approve_proof=False,
            approve_screenshot_baselines=True,
            approve_performance_baseline=False,
        )

        with self.assertRaisesRegex(ValueError, "rc-proof compares"):
            glx_runtime_sweep.validate_proof_approval_mode(args)

        args.gate = "rc-parity"
        glx_runtime_sweep.validate_proof_approval_mode(args)

    def test_proof_status_fails_incomplete_visual_approval(self) -> None:
        manifest = {
            "dryRun": False,
            "screenshotBaselineDir": "proof/screenshots",
            "approveScreenshotBaselines": True,
            "runs": [
                {
                    "type": "switch-screenshots",
                    "status": "passed",
                    "screenshots": [
                        {"name": "shot", "found": False, "baselineStatus": "approved"},
                    ],
                },
            ],
        }

        proof = glx_runtime_sweep.proof_status(manifest)
        self.assertEqual(proof["status"], "failed")
        self.assertEqual(proof["visual"]["status"], "failed")

        empty = {**manifest, "runs": [{"type": "switch-screenshots", "status": "passed", "screenshots": []}]}
        proof = glx_runtime_sweep.proof_status(empty)
        self.assertEqual(proof["status"], "failed")
        self.assertEqual(proof["visual"]["status"], "failed")

    def test_rc_proof_gate_requires_reviewed_visual_and_performance_baselines(self) -> None:
        manifest = release_proof_manifest("rc-proof", "windows-x64")

        self.assertEqual(glx_runtime_sweep.evaluate_gate(manifest), [])
        proof = glx_runtime_sweep.proof_status(
            {
                **manifest,
                "performanceAggregate": {"sampleCount": 1},
            }
        )
        self.assertEqual(proof["status"], "passed")
        self.assertEqual(proof["visual"]["status"], "passed")
        self.assertEqual(proof["performance"]["status"], "passed")

        missing = dict(manifest)
        missing["screenshotBaselineDir"] = ""
        missing["performanceBaselinePath"] = ""
        failures = glx_runtime_sweep.evaluate_gate(missing)

        self.assertTrue(any("Visual proof requires" in failure for failure in failures))
        self.assertTrue(any("Performance proof requires" in failure for failure in failures))

    def test_rc_proof_gate_rejects_baseline_approval_mode(self) -> None:
        manifest = {
            "gate": "rc-proof",
            "dryRun": False,
            "performanceFailures": [],
            "runs": [
                {
                    "type": "switch-screenshots",
                    "status": "passed",
                    "screenshots": [
                        {
                            "name": "shot",
                            "found": True,
                            "baselineStatus": "approved",
                            "histogram": screenshot_histogram(),
                        }
                    ],
                    "diagnostics": {
                        "found": True,
                        "failures": [],
                        "metrics": color_diagnostics_metrics(),
                    },
                    "performance": locked_performance_sample(),
                },
            ],
            "renderers": ["opengl", "glx"],
            "demos": [],
            "screenshotBaselineDir": "proof/screenshots",
            "performanceBaselinePath": "proof/performance-baseline.json",
            "approveScreenshotBaselines": True,
            "approvePerformanceBaseline": True,
            "performanceBaselineStatus": "approved",
        }

        failures = glx_runtime_sweep.evaluate_gate(manifest)

        self.assertTrue(any("not approve" in failure for failure in failures))

    def test_release_proof_root_requires_all_blocking_platform_gates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for platform_id in glx_runtime_sweep.GLX_BLOCKING_RELEASE_PLATFORMS:
                for gate in glx_runtime_sweep.GLX_RELEASE_REQUIRED_GATES:
                    manifest_dir = root / platform_id / gate / "run"
                    manifest_dir.mkdir(parents=True)
                    (manifest_dir / "manifest.json").write_text(
                        json.dumps(release_proof_manifest(gate, platform_id), indent=2),
                        encoding="utf-8",
                    )

            summary = glx_runtime_sweep.validate_release_proof_root(root)

            self.assertEqual(summary["status"], "passed")
            self.assertEqual(summary["failures"], [])
            self.assertEqual(
                len(summary["manifests"]),
                len(glx_runtime_sweep.GLX_BLOCKING_RELEASE_PLATFORMS)
                * len(glx_runtime_sweep.GLX_RELEASE_REQUIRED_GATES),
            )

    def test_release_proof_root_rejects_missing_platform_or_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for gate in glx_runtime_sweep.GLX_RELEASE_REQUIRED_GATES:
                manifest = release_proof_manifest(gate, "windows-x64")
                if gate == "rc-proof":
                    manifest["dryRun"] = True
                manifest_dir = root / "windows-x64" / gate / "run"
                manifest_dir.mkdir(parents=True)
                (manifest_dir / "manifest.json").write_text(
                    json.dumps(manifest, indent=2),
                    encoding="utf-8",
                )

            summary = glx_runtime_sweep.validate_release_proof_root(root)
            failures = "\n".join(str(failure) for failure in summary["failures"])

            self.assertEqual(summary["status"], "failed")
            self.assertIn("Missing GLx rc-smoke runtime proof for linux-x86_64", failures)
            self.assertIn("No passing GLx rc-proof runtime proof for windows-x64", failures)
            self.assertIn("dry-run manifests do not count as release proof", failures)


class GlxWorkflowTests(unittest.TestCase):
    def test_runtime_workflow_proof_dir_preserves_threshold_inputs(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "glx-verification.yml").read_text(encoding="utf-8")

        self.assertIn("cron: '35 4 * * 1'", workflow)
        self.assertIn("github.event_name == 'schedule'", workflow)
        self.assertIn("FNQ3_GLX_PROOF_PLATFORM", workflow)
        self.assertIn("--proof-platform", workflow)
        self.assertIn("if baseline_dir or proof_dir:", workflow)
        self.assertIn('"--screenshot-max-rms",', workflow)
        self.assertIn('os.environ["FNQ3_GLX_SCREENSHOT_MAX_RMS"]', workflow)
        self.assertIn('"--screenshot-max-pixel-ratio",', workflow)
        self.assertIn('os.environ["FNQ3_GLX_SCREENSHOT_MAX_PIXEL_RATIO"]', workflow)
        self.assertIn("if performance_baseline or proof_dir:", workflow)
        self.assertIn('"--performance-max-growth-ratio",', workflow)
        self.assertIn('os.environ["FNQ3_GLX_PERFORMANCE_MAX_GROWTH_RATIO"]', workflow)

    def test_ci_and_release_artifacts_reference_proof_corpus(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "glx-verification.yml").read_text(encoding="utf-8")
        release_script = (ROOT / "scripts" / "release.py").read_text(encoding="utf-8")
        corpus_doc = (ROOT / glx_runtime_sweep.GLX_PROOF_CORPUS_DOC).read_text(encoding="utf-8")

        self.assertIn("--list-corpus", workflow)
        self.assertIn("GLX_PROOF_CORPUS.md", workflow)
        self.assertIn("release_corpus_manifest", release_script)
        self.assertIn("glx_proof_corpus", release_script)
        self.assertIn("--glx-proof-root", release_script)
        self.assertIn("validate_release_proof_root", release_script)
        self.assertIn("glx_runtime_proof", release_script)
        self.assertIn("GLX_PROMOTION.md", workflow)
        self.assertIn("glx-promotion.json", workflow)
        self.assertIn("glx_promotion", release_script)
        self.assertIn("GLX_VISUAL_DOSSIER.md", workflow)
        self.assertIn("GLX_VISUAL_DOSSIER.md", release_script)
        self.assertIn(glx_runtime_sweep.GLX_PROOF_CORPUS_VERSION, corpus_doc)


class GlxPromotionTests(unittest.TestCase):
    def write_manifest(
        self,
        root: Path,
        platform_id: str,
        name: str,
        manifest: dict[str, object],
    ) -> None:
        manifest_dir = root / platform_id / name / "run"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )

    def write_complete_proof_root(self, root: Path) -> None:
        for platform_id in glx_runtime_sweep.GLX_BLOCKING_RELEASE_PLATFORMS:
            for gate in glx_runtime_sweep.GLX_RELEASE_REQUIRED_GATES:
                self.write_manifest(
                    root,
                    platform_id,
                    gate,
                    release_proof_manifest(gate, platform_id),
                )
            self.write_manifest(
                root,
                platform_id,
                "glx-ownership",
                ownership_proof_manifest(platform_id),
            )

    def write_rollback_metadata(
        self,
        root: Path,
        metadata: dict[str, object] | None = None,
    ) -> Path:
        path = root / "rollback-package.json"
        path.write_text(
            json.dumps(metadata or rollback_package_metadata(), indent=2),
            encoding="utf-8",
        )
        return path

    def test_current_tree_is_blocked_but_not_promoted(self) -> None:
        report = glx_promotion.promotion_report()

        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["policyViolation"])
        self.assertEqual(report["sourcePolicy"]["makeDefault"], "opengl")
        self.assertEqual(report["sourcePolicy"]["mesonDefault"], "opengl")
        self.assertEqual(report["sourcePolicy"]["makeUseGlxDefault"], "1")
        self.assertEqual(report["sourcePolicy"]["mesonUseGlxDefault"], "glx")
        checks = {check["name"]: check for check in report["checks"]}
        self.assertEqual(checks["feature-matrix-green"]["status"], "blocked")
        self.assertGreater(len(checks["feature-matrix-green"]["blockers"]), 0)
        self.assertEqual(checks["legacy-coupling-inventory"]["status"], "passed")
        self.assertEqual(checks["rollback-package-metadata"]["status"], "blocked")
        self.assertEqual(checks["migration-and-rollback-doc"]["status"], "passed")

    def test_complete_runtime_and_ownership_proof_still_waits_for_green_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_complete_proof_root(root)
            rollback_metadata = self.write_rollback_metadata(root)

            report = glx_promotion.promotion_report(root, rollback_metadata)
            checks = {check["name"]: check for check in report["checks"]}

            self.assertEqual(checks["blocking-runtime-proof"]["status"], "passed")
            self.assertEqual(checks["ownership-proof"]["status"], "passed")
            self.assertEqual(checks["rollback-package-metadata"]["status"], "passed")
            self.assertEqual(checks["feature-matrix-green"]["status"], "blocked")
            self.assertEqual(report["status"], "blocked")

    def test_legacy_coupling_inventory_matches_build_systems_and_doc(self) -> None:
        check = glx_promotion.check_legacy_coupling_inventory()

        self.assertEqual(check["status"], "passed")
        self.assertEqual(check["remainingLegacyRendererSources"], 24)
        self.assertEqual(check["ratchetBudget"], 24)
        self.assertEqual(check["documentedCount"], 24)
        self.assertEqual(check["blockers"], [])
        self.assertIn("code/renderer/tr_arb.c", check["sources"])
        self.assertIn("code/renderer/tr_shade.c", check["sources"])

        builds = check["builds"]
        self.assertEqual(builds["meson"]["sources"], check["sources"])
        self.assertEqual(builds["makefile"]["sources"], check["sources"])
        self.assertEqual(builds["msvc"]["sources"], check["sources"])

    def test_legacy_coupling_inventory_blocks_missing_doc_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "GLX_LEGACY_COUPLING.md"
            doc.write_text(
                "\n".join(
                    [
                        "| Source | Compatibility role | Extraction target |",
                        "|---|---|---|",
                        "| `code/renderer/tr_arb.c` | FBO substrate. | Split GLx postprocess. |",
                    ]
                ),
                encoding="utf-8",
            )

            check = glx_promotion.check_legacy_coupling_inventory(doc_path=doc)
            failures = "\n".join(str(failure) for failure in check["blockers"])

            self.assertEqual(check["status"], "blocked")
            self.assertIn("Legacy coupling ledger is missing source", failures)
            self.assertIn("code/renderer/tr_shade.c", failures)

    def test_rollback_package_metadata_validates_platform_artifacts_and_triggers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            metadata_path = self.write_rollback_metadata(Path(tmp))

            check = glx_promotion.check_rollback_package_metadata(metadata_path)

            self.assertEqual(check["status"], "passed")
            self.assertEqual(check["metadataStatus"], "reviewed")
            self.assertEqual(
                check["coveredPlatforms"],
                sorted(glx_runtime_sweep.GLX_BLOCKING_RELEASE_PLATFORMS),
            )
            self.assertEqual(check["packageCount"], 1)
            self.assertEqual(check["packages"][0]["artifactDir"], "fnquake3-legacy-opengl")
            self.assertEqual(check["blockers"], [])

    def test_rollback_package_metadata_blocks_incomplete_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            metadata_path = self.write_rollback_metadata(
                Path(tmp),
                rollback_package_metadata(
                    platforms=["windows-x64"],
                    legacy_renderers=["glx"],
                    required_artifacts={"proofCorpus": True},
                    triggers=["driver regression only"],
                ),
            )

            check = glx_promotion.check_rollback_package_metadata(metadata_path)
            failures = "\n".join(str(failure) for failure in check["blockers"])

            self.assertEqual(check["status"], "blocked")
            self.assertIn("legacy opengl renderer", failures)
            self.assertIn("promotionReport", failures)
            self.assertIn("releaseProofSummary", failures)
            self.assertIn("checksums", failures)
            self.assertIn("demo regressions", failures)
            self.assertIn("screenshot regressions", failures)
            self.assertIn("performance regressions", failures)
            self.assertIn("linux-x86_64", failures)

    def test_release_rollback_package_policy_is_not_required_until_source_promotion(self) -> None:
        args = argparse.Namespace(channel="release", glx_rollback_metadata=None)

        current = fnq3_release.resolve_glx_rollback_package(
            args,
            {"sourcePolicy": {"promoted": False}},
        )
        promoted = fnq3_release.resolve_glx_rollback_package(
            args,
            {"sourcePolicy": {"promoted": True}},
        )

        self.assertEqual(current["status"], "not-required")
        self.assertFalse(current["required"])
        self.assertEqual(promoted["status"], "missing")
        self.assertTrue(promoted["required"])

    def test_release_rollback_package_metadata_must_match_staged_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            metadata_path = self.write_rollback_metadata(Path(tmp))
            args = argparse.Namespace(channel="release", glx_rollback_metadata=metadata_path)
            rollback = fnq3_release.resolve_glx_rollback_package(
                args,
                {"sourcePolicy": {"promoted": True}},
            )
            archives = [
                {
                    "artifact_dir": "fnquake3-legacy-opengl",
                    "archive": "fnquake3-legacy-opengl.zip",
                    "path": ".install/packages/fnquake3-legacy-opengl.zip",
                    "sha256": "abc123",
                }
            ]

            rollback = fnq3_release.attach_glx_rollback_archives(rollback, archives)

            self.assertEqual(rollback["matchedArchives"][0]["archive"], "fnquake3-legacy-opengl.zip")
            self.assertEqual(rollback["matchedArchives"][0]["sha256"], "abc123")

            with self.assertRaisesRegex(ValueError, "did not match a staged release archive"):
                fnq3_release.attach_glx_rollback_archives(rollback, [])

    def test_ownership_proof_requires_zero_legacy_delegation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for platform_id in glx_runtime_sweep.GLX_BLOCKING_RELEASE_PLATFORMS:
                self.write_manifest(
                    root,
                    platform_id,
                    "glx-ownership",
                    ownership_proof_manifest(
                        platform_id,
                        calls=1 if platform_id == "windows-x64" else 0,
                        items=4 if platform_id == "windows-x64" else 0,
                    ),
                )

            proof = glx_promotion.check_ownership_proof(root)
            failures = "\n".join(str(failure) for failure in proof["blockers"])

            self.assertEqual(proof["status"], "blocked")
            self.assertIn("windows-x64", failures)
            self.assertNotIn("linux-x86_64 did not report zero", failures)

    def test_ownership_proof_requires_versioned_evidence_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for platform_id in glx_runtime_sweep.GLX_BLOCKING_RELEASE_PLATFORMS:
                manifest = ownership_proof_manifest(platform_id)
                if platform_id == "windows-x64":
                    manifest.pop("ownershipProofEvidence")
                self.write_manifest(
                    root,
                    platform_id,
                    "glx-ownership",
                    manifest,
                )

            proof = glx_promotion.check_ownership_proof(root)
            failures = "\n".join(str(failure) for failure in proof["blockers"])

            self.assertEqual(proof["status"], "blocked")
            self.assertIn("windows-x64", failures)
            self.assertIn("versioned ownership proof evidence", failures)
            self.assertNotIn("linux-x86_64 did not include versioned", failures)

    def test_ownership_proof_rejects_stale_evidence_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for platform_id in glx_runtime_sweep.GLX_BLOCKING_RELEASE_PLATFORMS:
                manifest = ownership_proof_manifest(platform_id)
                if platform_id == "windows-x64":
                    manifest["ownershipProofEvidence"]["version"] = 0
                self.write_manifest(
                    root,
                    platform_id,
                    "glx-ownership",
                    manifest,
                )

            proof = glx_promotion.check_ownership_proof(root)
            failures = "\n".join(str(failure) for failure in proof["blockers"])

            self.assertEqual(proof["status"], "blocked")
            self.assertIn("unsupported ownership proof evidence version", failures)

    def test_ownership_proof_requires_modern_post_output_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for platform_id in glx_runtime_sweep.GLX_BLOCKING_RELEASE_PLATFORMS:
                self.write_manifest(
                    root,
                    platform_id,
                    "glx-ownership",
                    ownership_proof_manifest(
                        platform_id,
                        post_mode="legacy-fallback" if platform_id == "windows-x64" else "glx-owned",
                        post_nodes=0 if platform_id == "windows-x64" else 2,
                        outputs=0 if platform_id == "windows-x64" else 1,
                        legacy_fallback=1 if platform_id == "windows-x64" else 0,
                    ),
                )

            proof = glx_promotion.check_ownership_proof(root)
            failures = "\n".join(str(failure) for failure in proof["blockers"])

            self.assertEqual(proof["status"], "blocked")
            self.assertIn("windows-x64", failures)
            self.assertIn("did not prove executable GLx-owned modern post/output", failures)

    def test_ownership_proof_requires_modern_post_output_tier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for platform_id in glx_runtime_sweep.GLX_BLOCKING_RELEASE_PLATFORMS:
                self.write_manifest(
                    root,
                    platform_id,
                    "glx-ownership",
                    ownership_proof_manifest(
                        platform_id,
                        tier="GL2X" if platform_id == "windows-x64" else "GL3X",
                    ),
                )

            proof = glx_promotion.check_ownership_proof(root)
            failures = "\n".join(str(failure) for failure in proof["blockers"])

            self.assertEqual(proof["status"], "blocked")
            self.assertIn("windows-x64", failures)
            self.assertIn("did not prove a GL3X+ modern post/output tier", failures)
            self.assertNotIn("linux-x86_64 did not prove a GL3X+", failures)

    def test_ownership_proof_requires_modern_tier_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for platform_id in glx_runtime_sweep.GLX_BLOCKING_RELEASE_PLATFORMS:
                self.write_manifest(
                    root,
                    platform_id,
                    "glx-ownership",
                    ownership_proof_manifest(
                        platform_id,
                        modern_tier_diagnostics=platform_id != "windows-x64",
                    ),
                )

            proof = glx_promotion.check_ownership_proof(root)
            failures = "\n".join(str(failure) for failure in proof["blockers"])

            self.assertEqual(proof["status"], "blocked")
            self.assertIn("windows-x64", failures)
            self.assertIn("did not prove modern post-chain and scene-linear tier diagnostics", failures)
            self.assertNotIn("linux-x86_64 did not prove modern post-chain", failures)


class GlxRuntimeSweepPerformanceTests(unittest.TestCase):
    def test_rc_profiles_promote_state_only_dynamic_submission(self) -> None:
        for profile_name in ("glx-parity", "glx-stress"):
            with self.subTest(profile=profile_name):
                profile = glx_runtime_sweep.PROFILE_CVARS[profile_name]

                self.assertEqual(profile["r_glxStreamDrawShadows"], "1")
                self.assertEqual(profile["r_glxStreamDrawBeams"], "1")
                self.assertEqual(profile["r_glxStreamDrawPostProcess"], "1")
                self.assertEqual(profile["r_glxStreamDrawDynamicLights"], "0")
                self.assertEqual(profile["r_glxStreamDrawScreenMaps"], "0")
                self.assertEqual(profile["r_glxStreamDrawVideoMaps"], "0")

    def test_glx_performance_samples_parse_compact_frame_counters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "switch.log"
            log.write_text(
                "\n".join(
                    [
                        "glx: tier GL2X, batches 10, draws 20/300 idx, stream map-range/ready 1.25MB/2wraps/0rejects shadow 3, frames 4, backend queries 5, gpu 0.27 ms, static 6 batches/7 packets/8 surfaces/9 verts/10 indexes 2.50 MB, arena ready 3.75 MB",
                        f"glx: pass schedule valid 9/{glx_runtime_sweep.GLX_EXPECTED_PASS_SCHEDULE_HASH} {glx_runtime_sweep.GLX_EXPECTED_PASS_SCHEDULE}",
                        "pass schedule: invalid 0/00000000 none",
                        "glx: post/output ownership mode glx-owned, post nodes 4, outputs 2, legacy fallback no, executable nodes 4, executable outputs 2, post hash 0x01020304, output hash 0x05060708, plan hash 0x090a0b0c, fallback 0x00000000",
                        "glx: post shader plan valid yes, features 0x00000d5e, hash 0x0badcafe, textures 2, uniforms 13, frames 4, invalid 0",
                        "glx: post shader cache ready yes, programs 3/32, plans 4 valid/0 invalid, cache 2 hits/3 misses, compile 3 attempts/0 failures, link failures 0, source failures 0, source hash 0x12345678, program 99",
                        "glx: post shader direct-final execute yes, eligible yes, bound yes, reject 0x00000000, candidates 4, eligible frames 4, attempts 4, binds 4, fallbacks 0, rejects 0, program misses 0, uniform failures 0",
                        "glx: material renderer on/ready programs 25, binds 12/13 attempts, switches 4, cache 5/6, failures 0 compile/0 link/0 precache/0 bind, labels 8",
                        "glx: material parameters blocks 12 invalid 0 hash 0x1234abcd, last sort 0 passes 1 features 0x0 flags 0x0 state 0x0",
                        "glx: postprocess fbo ready 640x480 capture 640x480 bloom 2, frames 3 final 2 prefinal 1 gamma 0/3, copies 4, msaa 5, ssaa 6, last bloom-final",
                        "glx: pass counters blits 7, binds 11, clears 2, fullscreen 8, pass queries 9, unavailable 1, ring skips 0",
                        "glx: pass gpu: backend=0.270ms/1 postprocess=0.420ms/1 bloom=0.250ms/1 bloom-extract=0.030ms/1 bloom-downscale=0.010ms/3 bloom-blur=0.090ms/2 bloom-blend=0.080ms/1 bloom-final=0.060ms/1 bloom-lens-reflection=n/a/0 gamma-direct=n/a/0 gamma-blit=0.110ms/1 fbo-blit=0.040ms/2 copy-screen=n/a/0 flare=0.020ms/1",
                        "glx: bloom storage policy auto format 0x8c3a (0x1907:0x140b)",
                        "target: render 640x480, capture 640x480, window 640x480, format 0x881a (0x1908:0x140b)",
                        "controls: scene-linear HDR yes, precision 16, renderScale 1, bloom 2, MSAA no, supersample no, adjusted window yes, greyscale 1.00",
                        "frames: 3 post, 1 bloom-final, 0 gamma-direct, 3 gamma-blit, 0 minimized output, 1 screenshots",
                        "frame features: 1 bloom-available, 1 scene-linear, 1 tone-mapped, 1 graded, 1 render-scale, 1 greyscale, 1 window-adjusted, 0 minimized",
                        "glx: color pipeline scene-linear precision 16 transfer hdr10-pq tone-map aces-fitted exposure 1.00 bloom-threshold 0.75/2 knee 0.50 grade lgg-lut3d paper-white 203 max 812",
                        "glx: auto exposure mode 3 algorithm histogram-percentile enabled yes fallback no samples 1024/32x32 percentile 80.0 target-luma 0.180 measured-log2 -1.000 measured-luma 0.5000 manual 1.00 scale 0.360 target 0.36 frames 3 histogram 3 simple 0 sample-failures 0",
                        "glx: color grade mode lgg-lut3d lift 0.01/0.02/0.03 gamma 1.10/1.00/0.95 gain 1.05/1.00/0.98 white-point 6504->6000 lut-size 16 lut-scale 4.00",
                        "glx: output colorimetry primaries bt2020 gamut-map compress precision-request 0 precision-resolved 16",
                        "glx: color audit srgb-decode yes requested yes available yes framebuffer-srgb no requested yes available yes capture sdr-srgb capture-request sdr-srgb capture-hdr-aware no capture-supported yes target-float yes final-encode shader-srgb contract yes",
                        "glx: texture audit srgb 4 decode 4, linear 2 decode 0, data 2 decode 0, unknown 0 decode 0, missing-srgb-decode 0, unexpected-decode 0",
                        'glx: color-frame-json {"frame":1,"backend":"hdr10-pq","space":"scene-linear","transfer":"hdr10-pq","exposure":1.0000,"paperWhiteNits":203.0,"maxOutputNits":812.0,"srgbDecode":true,"framebufferSrgb":false,"internalFormat":"0x881a","textureFormat":"0x1908","textureType":"0x140b","sceneTargetFloat":true,"shaderSrgbEncode":true,"contractValid":true}',
                        "glx: output backend request hdr10-pq selected hdr10-pq native windows-scrgb hardware yes experimental no display-hdr yes headroom 4.00 sdr-white 203 display-max 812 icc yes/2048",
                        "glx: stream draws 7/8 attempts, 90 idx, 0.50MB/index 0.10MB/tex1 0.20MB, mt 1, fog 2, depthfrag 3, texmod 4, env 5, dlight 0, screen 0, video 0, shadow 2, beam 3, post 4, fallbacks 0, skips 1",
                        "glx: stream categories entity 2/2, particle 1/1, poly 1/1, mark 1/1, weapon 1/1, ui 1/1, beam 3/3, special 4/4",
                        "glx: stream reservation last 256 bytes at 1024 using map-range, largest 4096 bytes, same-frame wrap rejects 0",
                        "glx: stream binding cache queries 1 hits 6 restores 8 invalidations 2 external 4 array-known yes array-buffer 0 element-known yes element-buffer 0",
                        "glx: static queue packets last 1 full/2 partial/3 miss/4 mismatch, total 5 full/6 partial/7 miss",
                        "glx: static packet lookup 64 mapped/max 63, hits 30, misses 9, fallbacks 2, mismatches 1, overflows 0",
                        "glx: static draw 11/12 calls, 130 idx, packets 1 full/2 partial/3 miss, manifest 4/5 idx, soft 6/7 calls/8 idx, arena 9, legacy 10, fallbacks 0, policy skips 1",
                        "glx: static MDI 1/2 calls, 3 runs/4 idx, fallbacks 0, skips 5, errors 0, largest 6",
                        "glx: GL3X performance draws 14 sync-uploads 3 static-buffers 2 dynamic-buffers 5 materials 7 fbo-post 4 unsupported persistent-upload 0",
                        "glx: GL41 mac-modern draws 15 sync-uploads 4 static-buffers 3 dynamic-buffers 6 materials 8 post 5 unsupported persistent-upload 0 gl43-required 0 gl44-required 0 gl45-required 0",
                        "glx: GL46 high-end draws 16 persistent-uploads 2 sync-uploads 5 dsa-products 6 mdi-products 7 aggressive-static 8 materials 9 post 10 gpu-counters 11 static-mdi 12/13 calls/140 idx",
                    ]
                ),
                encoding="utf-8",
            )

            performance = glx_runtime_sweep.analyze_glx_performance(log)
            self.assertTrue(performance["found"])
            self.assertEqual(performance["sampleCount"], 1)
            self.assertEqual(performance["latest"]["tier"], "GL2X")
            self.assertEqual(performance["latest"]["productTier"], "GL2X")
            self.assertEqual(performance["latest"]["drawIndexes"], 300)
            self.assertEqual(performance["latest"]["gpuFrameMs"], 0.27)
            self.assertEqual(performance["latest"]["gpuPassBlits"], 7)
            self.assertEqual(performance["latest"]["gpuPassBinds"], 11)
            self.assertEqual(performance["latest"]["gpuPassClears"], 2)
            self.assertEqual(performance["latest"]["gpuPassFullscreen"], 8)
            self.assertEqual(performance["latest"]["gpuPassQueries"], 9)
            self.assertEqual(performance["latest"]["gpuPassUnavailable"], 1)
            self.assertEqual(performance["latest"]["gpuPassBackendMs"], 0.27)
            self.assertEqual(performance["latest"]["gpuPassPostprocessSamples"], 1)
            self.assertEqual(performance["latest"]["gpuPassBloomDownscaleSamples"], 3)
            self.assertEqual(performance["latest"]["gpuPassFlareMs"], 0.02)
            self.assertEqual(performance["latest"]["passScheduleValid"], 1)
            self.assertEqual(performance["latest"]["passScheduleCount"], 9)
            self.assertEqual(performance["latest"]["passScheduleHash"], glx_runtime_sweep.GLX_EXPECTED_PASS_SCHEDULE_HASH)
            self.assertEqual(performance["latest"]["passScheduleOrder"], glx_runtime_sweep.GLX_EXPECTED_PASS_SCHEDULE)
            self.assertEqual(performance["latest"]["postOutputMode"], "glx-owned")
            self.assertEqual(performance["latest"]["postOutputPostNodes"], 4)
            self.assertEqual(performance["latest"]["postOutputOutputs"], 2)
            self.assertEqual(performance["latest"]["postOutputExecutableNodes"], 4)
            self.assertEqual(performance["latest"]["postOutputExecutableOutputs"], 2)
            self.assertEqual(performance["latest"]["postOutputPostHash"], 0x01020304)
            self.assertEqual(performance["latest"]["postOutputOutputHash"], 0x05060708)
            self.assertEqual(performance["latest"]["postOutputPlanHash"], 0x090A0B0C)
            self.assertEqual(performance["latest"]["postOutputFallbackMask"], 0)
            self.assertEqual(performance["latest"]["postShaderPlanValid"], 1)
            self.assertEqual(performance["latest"]["postShaderFeatures"], 0x00000D5E)
            self.assertEqual(performance["latest"]["postShaderHash"], 0x0BADCAFE)
            self.assertEqual(performance["latest"]["postShaderTextures"], 2)
            self.assertEqual(performance["latest"]["postShaderUniforms"], 13)
            self.assertEqual(performance["latest"]["postShaderFrames"], 4)
            self.assertEqual(performance["latest"]["postShaderInvalidFrames"], 0)
            self.assertEqual(performance["latest"]["postShaderCacheReady"], 1)
            self.assertEqual(performance["latest"]["postShaderPrograms"], 3)
            self.assertEqual(performance["latest"]["postShaderProgramLimit"], 32)
            self.assertEqual(performance["latest"]["postShaderValidPlans"], 4)
            self.assertEqual(performance["latest"]["postShaderInvalidPlans"], 0)
            self.assertEqual(performance["latest"]["postShaderCacheHits"], 2)
            self.assertEqual(performance["latest"]["postShaderCacheMisses"], 3)
            self.assertEqual(performance["latest"]["postShaderCompileAttempts"], 3)
            self.assertEqual(performance["latest"]["postShaderCompileFailures"], 0)
            self.assertEqual(performance["latest"]["postShaderLinkFailures"], 0)
            self.assertEqual(performance["latest"]["postShaderSourceFailures"], 0)
            self.assertEqual(performance["latest"]["postShaderSourceHash"], 0x12345678)
            self.assertEqual(performance["latest"]["postShaderProgram"], 99)
            self.assertEqual(performance["latest"]["postShaderDirectFinalExecute"], 1)
            self.assertEqual(performance["latest"]["postShaderDirectFinalEligible"], 1)
            self.assertEqual(performance["latest"]["postShaderDirectFinalBound"], 1)
            self.assertEqual(performance["latest"]["postShaderDirectFinalReject"], 0)
            self.assertEqual(performance["latest"]["postShaderDirectFinalCandidates"], 4)
            self.assertEqual(performance["latest"]["postShaderDirectFinalEligibleFrames"], 4)
            self.assertEqual(performance["latest"]["postShaderDirectFinalAttempts"], 4)
            self.assertEqual(performance["latest"]["postShaderDirectFinalBinds"], 4)
            self.assertEqual(performance["latest"]["postShaderDirectFinalFallbacks"], 0)
            self.assertEqual(performance["latest"]["postShaderDirectFinalRejects"], 0)
            self.assertEqual(performance["latest"]["materialPrograms"], 25)
            self.assertEqual(performance["latest"]["materialParameterBlocks"], 12)
            self.assertEqual(performance["latest"]["materialParameterHash"], 0x1234ABCD)
            self.assertEqual(performance["latest"]["materialInvalidParameterBlocks"], 0)
            self.assertEqual(performance["latest"]["colorSpace"], "scene-linear")
            self.assertEqual(performance["latest"]["hdrPrecision"], 16)
            self.assertEqual(performance["latest"]["outputTransfer"], "hdr10-pq")
            self.assertEqual(performance["latest"]["toneMap"], "aces-fitted")
            self.assertEqual(performance["latest"]["toneMapExposure"], 1.0)
            self.assertEqual(performance["latest"]["bloomThreshold"], 0.75)
            self.assertEqual(performance["latest"]["bloomThresholdMode"], 2)
            self.assertEqual(performance["latest"]["bloomSoftKnee"], 0.5)
            self.assertEqual(performance["latest"]["autoExposureMode"], 3)
            self.assertEqual(performance["latest"]["autoExposureAlgorithm"], "histogram-percentile")
            self.assertEqual(performance["latest"]["autoExposureEnabled"], 1)
            self.assertEqual(performance["latest"]["autoExposureFallback"], 0)
            self.assertEqual(performance["latest"]["autoExposureSampleCount"], 1024)
            self.assertEqual(performance["latest"]["autoExposureSampleWidth"], 32)
            self.assertEqual(performance["latest"]["autoExposureSampleHeight"], 32)
            self.assertEqual(performance["latest"]["autoExposureTargetLuma"], 0.18)
            self.assertEqual(performance["latest"]["autoExposureMeasuredLuma"], 0.5)
            self.assertEqual(performance["latest"]["autoExposureSampleFailures"], 0)
            self.assertEqual(performance["latest"]["colorGrade"], "lgg-lut3d")
            self.assertEqual(performance["latest"]["colorGradeMode"], "lgg-lut3d")
            self.assertEqual(performance["latest"]["colorGradeLiftR"], 0.01)
            self.assertEqual(performance["latest"]["colorGradeGammaR"], 1.10)
            self.assertEqual(performance["latest"]["colorGradeGainR"], 1.05)
            self.assertEqual(performance["latest"]["colorGradeWhiteTarget"], 6000.0)
            self.assertEqual(performance["latest"]["colorGradeLutSize"], 16.0)
            self.assertEqual(performance["latest"]["colorGradeLutScale"], 4.0)
            self.assertEqual(performance["latest"]["outputPrimaries"], "bt2020")
            self.assertEqual(performance["latest"]["gamutMap"], "compress")
            self.assertEqual(performance["latest"]["hdrPrecisionRequested"], 0)
            self.assertEqual(performance["latest"]["hdrPrecisionResolved"], 16)
            self.assertEqual(performance["latest"]["paperWhiteNits"], 203.0)
            self.assertEqual(performance["latest"]["maxOutputNits"], 812.0)
            self.assertEqual(performance["latest"]["colorSrgbDecode"], 1)
            self.assertEqual(performance["latest"]["colorSrgbAvailable"], 1)
            self.assertEqual(performance["latest"]["colorFramebufferSrgb"], 0)
            self.assertEqual(performance["latest"]["colorSceneTargetFloat"], 1)
            self.assertEqual(performance["latest"]["colorFinalEncode"], "shader-srgb")
            self.assertEqual(performance["latest"]["colorOutputContract"], 1)
            self.assertEqual(performance["latest"]["captureColorSpace"], "sdr-srgb")
            self.assertEqual(performance["latest"]["capturePolicyRequest"], "sdr-srgb")
            self.assertEqual(performance["latest"]["captureHdrAware"], 0)
            self.assertEqual(performance["latest"]["capturePolicySupported"], 1)
            self.assertEqual(performance["latest"]["textureAuditSrgb"], 4)
            self.assertEqual(performance["latest"]["textureAuditSrgbDecode"], 4)
            self.assertEqual(performance["latest"]["textureAuditMissingSrgbDecode"], 0)
            self.assertEqual(performance["latest"]["textureAuditUnexpectedDecode"], 0)
            self.assertEqual(performance["latest"]["targetInternalFormat"], 0x881A)
            self.assertEqual(performance["latest"]["targetTextureFormat"], 0x1908)
            self.assertEqual(performance["latest"]["targetTextureType"], 0x140B)
            self.assertEqual(performance["latest"]["postprocessRenderScaleMode"], 1)
            self.assertEqual(performance["latest"]["postprocessGreyscale"], 1.0)
            self.assertEqual(performance["latest"]["postprocessWindowAdjusted"], 1)
            self.assertEqual(performance["latest"]["postprocessFrames"], 3)
            self.assertEqual(performance["latest"]["postprocessScreenshots"], 1)
            self.assertEqual(performance["latest"]["postprocessMinimizedOutput"], 0)
            self.assertEqual(performance["latest"]["postprocessFeatureRenderScale"], 1)
            self.assertEqual(performance["latest"]["postprocessFeatureGreyscale"], 1)
            self.assertEqual(performance["latest"]["postprocessFeatureWindowAdjusted"], 1)
            self.assertEqual(performance["latest"]["postprocessFeatureMinimized"], 0)
            self.assertEqual(performance["latest"]["gpuPassBlits"], 7)
            self.assertEqual(performance["latest"]["gpuPassBinds"], 11)
            self.assertEqual(performance["latest"]["gpuPassClears"], 2)
            self.assertEqual(performance["latest"]["gpuPassFullscreen"], 8)
            self.assertEqual(performance["latest"]["gpuPassQueries"], 9)
            self.assertEqual(performance["latest"]["gpuPassUnavailable"], 1)
            self.assertEqual(performance["latest"]["gpuPassPostprocessMs"], 0.42)
            self.assertEqual(performance["latest"]["gpuPassBloomBlurSamples"], 2)
            self.assertEqual(performance["latest"]["bloomStoragePolicy"], "auto")
            self.assertEqual(performance["latest"]["bloomStorageInternalFormat"], 0x8C3A)
            self.assertEqual(performance["latest"]["bloomStorageTextureFormat"], 0x1907)
            self.assertEqual(performance["latest"]["bloomStorageTextureType"], 0x140B)
            self.assertEqual(performance["latest"]["colorFrameSamples"], 1)
            self.assertEqual(performance["latest"]["colorFrameBackend"], "hdr10-pq")
            self.assertEqual(performance["latest"]["colorFrameTransfer"], "hdr10-pq")
            self.assertEqual(performance["latest"]["colorFrameInternalFormat"], "0x881a")
            self.assertEqual(performance["latest"]["colorFrameContractValid"], 1)
            self.assertEqual(performance["latest"]["outputBackendRequest"], "hdr10-pq")
            self.assertEqual(performance["latest"]["outputBackendSelected"], "hdr10-pq")
            self.assertEqual(performance["latest"]["outputBackendNative"], "windows-scrgb")
            self.assertEqual(performance["latest"]["outputBackendHardware"], 1)
            self.assertEqual(performance["latest"]["streamBindingQueries"], 1)
            self.assertEqual(performance["latest"]["streamBindingCacheHits"], 6)
            self.assertEqual(performance["latest"]["streamBindingExternalUpdates"], 4)
            self.assertEqual(performance["latest"]["outputHeadroom"], 4.0)
            self.assertEqual(performance["latest"]["outputIccProfileBytes"], 2048)
            self.assertEqual(performance["latest"]["streamDrawAttempts"], 8)
            self.assertEqual(performance["latest"]["streamDrawMegabytes"], 0.5)
            self.assertEqual(performance["latest"]["streamSameFrameWrapRejects"], 0)
            self.assertEqual(performance["latest"]["streamDrawMultitexture"], 1)
            self.assertEqual(performance["latest"]["streamDrawFog"], 2)
            self.assertEqual(performance["latest"]["streamDrawDepthFragment"], 3)
            self.assertEqual(performance["latest"]["streamDrawTexMods"], 4)
            self.assertEqual(performance["latest"]["streamDrawEnvironment"], 5)
            self.assertEqual(performance["latest"]["streamDrawDynamicLights"], 0)
            self.assertEqual(performance["latest"]["streamDrawScreenMaps"], 0)
            self.assertEqual(performance["latest"]["streamDrawVideoMaps"], 0)
            self.assertEqual(performance["latest"]["streamDrawShadows"], 2)
            self.assertEqual(performance["latest"]["streamDrawBeams"], 3)
            self.assertEqual(performance["latest"]["streamDrawPostProcess"], 4)
            self.assertEqual(performance["latest"]["streamCategoryEntityDraws"], 2)
            self.assertEqual(performance["latest"]["streamCategoryParticleDraws"], 1)
            self.assertEqual(performance["latest"]["streamCategoryPolyDraws"], 1)
            self.assertEqual(performance["latest"]["streamCategoryMarkDraws"], 1)
            self.assertEqual(performance["latest"]["streamCategoryWeaponDraws"], 1)
            self.assertEqual(performance["latest"]["streamCategoryUiDraws"], 1)
            self.assertEqual(performance["latest"]["streamCategoryBeamDraws"], 3)
            self.assertEqual(performance["latest"]["streamCategorySpecialDraws"], 4)
            self.assertEqual(performance["latest"]["staticDrawPacketMisses"], 3)
            self.assertEqual(performance["latest"]["staticQueuePacketMisses"], 7)
            self.assertEqual(performance["latest"]["staticPacketLookupMisses"], 9)
            self.assertEqual(performance["latest"]["staticPacketLookupFallbacks"], 2)
            self.assertEqual(performance["latest"]["staticPacketLookupOverflows"], 0)
            self.assertEqual(performance["latest"]["gl3xDraws"], 14)
            self.assertEqual(performance["latest"]["gl3xSyncUploads"], 3)
            self.assertEqual(performance["latest"]["gl3xStaticBuffers"], 2)
            self.assertEqual(performance["latest"]["gl3xDynamicBuffers"], 5)
            self.assertEqual(performance["latest"]["gl3xMaterials"], 7)
            self.assertEqual(performance["latest"]["gl3xFboPost"], 4)
            self.assertEqual(performance["latest"]["gl3xUnsupportedPersistentUploads"], 0)
            self.assertEqual(performance["latest"]["gl41Draws"], 15)
            self.assertEqual(performance["latest"]["gl41SyncUploads"], 4)
            self.assertEqual(performance["latest"]["gl41StaticBuffers"], 3)
            self.assertEqual(performance["latest"]["gl41DynamicBuffers"], 6)
            self.assertEqual(performance["latest"]["gl41Materials"], 8)
            self.assertEqual(performance["latest"]["gl41Post"], 5)
            self.assertEqual(performance["latest"]["gl41UnsupportedPersistentUploads"], 0)
            self.assertEqual(performance["latest"]["gl41Gl43Required"], 0)
            self.assertEqual(performance["latest"]["gl41Gl44Required"], 0)
            self.assertEqual(performance["latest"]["gl41Gl45Required"], 0)
            self.assertEqual(performance["latest"]["gl46Draws"], 16)
            self.assertEqual(performance["latest"]["gl46PersistentUploads"], 2)
            self.assertEqual(performance["latest"]["gl46SyncUploads"], 5)
            self.assertEqual(performance["latest"]["gl46DsaProducts"], 6)
            self.assertEqual(performance["latest"]["gl46MdiProducts"], 7)
            self.assertEqual(performance["latest"]["gl46AggressiveStatic"], 8)
            self.assertEqual(performance["latest"]["gl46Materials"], 9)
            self.assertEqual(performance["latest"]["gl46Post"], 10)
            self.assertEqual(performance["latest"]["gl46GpuCounters"], 11)
            self.assertEqual(performance["latest"]["gl46StaticMdiCalls"], 12)
            self.assertEqual(performance["latest"]["gl46StaticMdiAttempts"], 13)
            self.assertEqual(performance["latest"]["gl46StaticMdiIndexes"], 140)
            self.assertEqual(performance["max"]["staticMdiLargest"], 6)

    def test_gate_evaluation_requires_performance_samples(self) -> None:
        manifest = {
            "gate": "rc-smoke",
            "dryRun": False,
            "runs": [
                {
                    "type": "switch-screenshots",
                    "status": "passed",
                    "screenshots": [
                        {"name": "shot", "found": True, "histogram": screenshot_histogram()},
                    ],
                    "diagnostics": {
                        "found": True,
                        "failures": [],
                        "metrics": color_diagnostics_metrics(),
                    },
                },
            ],
            "renderers": ["opengl", "glx"],
            "demos": [],
        }

        failures = glx_runtime_sweep.evaluate_gate(manifest)
        self.assertTrue(any("performance samples" in failure for failure in failures))

    def test_gate_evaluation_requires_locked_pass_schedule_in_capture_logs(self) -> None:
        manifest = {
            "gate": "rc-smoke",
            "dryRun": False,
            "runs": [
                {
                    "type": "switch-screenshots",
                    "status": "passed",
                    "screenshots": [
                        {"name": "shot", "found": True, "histogram": screenshot_histogram()},
                    ],
                    "diagnostics": {
                        "found": True,
                        "failures": [],
                        "metrics": color_diagnostics_metrics(),
                    },
                    "performance": {
                        "found": True,
                        "sampleCount": 1,
                        "latest": {
                            "passScheduleValid": 1,
                            "passScheduleCount": 8,
                            "passScheduleHash": glx_runtime_sweep.GLX_EXPECTED_PASS_SCHEDULE_HASH,
                            "passScheduleOrder": "frame-setup>postprocess",
                        },
                        "max": {},
                    },
                },
            ],
            "renderers": ["opengl", "glx"],
            "demos": [],
        }

        failures = glx_runtime_sweep.evaluate_gate(manifest)
        self.assertTrue(any("pass schedule" in failure for failure in failures))

    def test_gate_evaluation_rejects_old_capability_tier_names(self) -> None:
        manifest = {
            "gate": "rc-smoke",
            "dryRun": False,
            "runs": [
                {
                    "type": "switch-screenshots",
                    "status": "passed",
                    "screenshots": [
                        {"name": "shot", "found": True, "histogram": screenshot_histogram()},
                    ],
                    "diagnostics": {
                        "found": True,
                        "failures": [],
                        "metrics": color_diagnostics_metrics(),
                    },
                    "performance": {
                        "found": True,
                        "sampleCount": 1,
                        "latest": {
                            **locked_pass_schedule_latest(),
                            "tier": "compat",
                            "productTier": "compat",
                        },
                        "max": {},
                    },
                },
            ],
            "renderers": ["opengl", "glx"],
            "demos": [],
        }

        failures = glx_runtime_sweep.evaluate_gate(manifest)
        self.assertTrue(any("final five tiers" in failure for failure in failures))

    def test_performance_budget_flags_fallback_counters(self) -> None:
        aggregate = {
            "sampleCount": 1,
            "latest": {"productTier": "GL2X"},
            "max": {
                "streamDrawFallbacks": 2,
                "streamDrawDynamicLights": 1,
                "streamDrawScreenMaps": 0,
                "streamDrawVideoMaps": 0,
                "staticDrawFallbacks": 0,
                "streamSameFrameWrapRejects": 1,
            },
        }
        budget = glx_runtime_sweep.merge_budget(
            glx_runtime_sweep.DEFAULT_PERFORMANCE_BUDGET,
            {"min": {"sampleCount": 1}},
        )

        failures = glx_runtime_sweep.evaluate_performance_budget(aggregate, budget)

        self.assertTrue(any("streamDrawFallbacks" in failure for failure in failures))
        self.assertTrue(any("streamDrawDynamicLights" in failure for failure in failures))
        self.assertTrue(any("streamSameFrameWrapRejects" in failure for failure in failures))
        self.assertFalse(any("staticDrawFallbacks" in failure for failure in failures))

    def test_performance_budget_applies_tier_draw_upload_bind_miss_and_gpu_limits(self) -> None:
        aggregate = {
            "sampleCount": 1,
            "latest": {"productTier": "GL2X"},
            "max": {
                "draws": 12001,
                "streamMegabytes": 129.0,
                "materialBinds": 12001,
                "staticDrawPacketMisses": 12001,
                "staticQueuePacketMisses": 12001,
                "staticPacketLookupMisses": 12001,
                "gpuFrameMs": 51.0,
            },
        }

        failures = glx_runtime_sweep.evaluate_performance_budget(
            aggregate,
            glx_runtime_sweep.DEFAULT_PERFORMANCE_BUDGET,
        )

        for key in (
            "GL2X max draws",
            "GL2X max streamMegabytes",
            "GL2X max materialBinds",
            "GL2X max staticDrawPacketMisses",
            "GL2X max staticQueuePacketMisses",
            "GL2X max staticPacketLookupMisses",
            "GL2X max gpuFrameMs",
        ):
            self.assertTrue(any(key in failure for failure in failures), key)

    def test_performance_budget_requires_p1_metrics_on_modern_tiers(self) -> None:
        aggregate = {
            "sampleCount": 1,
            "latest": {"productTier": "GL46"},
            "max": {
                "draws": 1,
                "streamMegabytes": 1.0,
                "materialBinds": 1,
                "staticDrawPacketMisses": 0,
            },
        }

        failures = glx_runtime_sweep.evaluate_performance_budget(
            aggregate,
            glx_runtime_sweep.DEFAULT_PERFORMANCE_BUDGET,
        )

        self.assertTrue(any("GL46 required metric gpuFrameMs is missing" in failure for failure in failures))
        self.assertTrue(any("GL46 required metric postOutputLegacyFallback is missing" in failure for failure in failures))
        self.assertTrue(any("GL46 required metric postOutputPostHash is missing" in failure for failure in failures))
        self.assertTrue(any("GL46 required metric postOutputOutputHash is missing" in failure for failure in failures))
        self.assertTrue(any("GL46 required metric postOutputPlanHash is missing" in failure for failure in failures))
        self.assertTrue(any("GL46 required metric postOutputFallbackMask is missing" in failure for failure in failures))
        self.assertTrue(any("GL46 required metric materialCacheMisses is missing" in failure for failure in failures))
        self.assertTrue(any("GL46 required metric materialParameterBlocks is missing" in failure for failure in failures))
        self.assertTrue(any("GL46 required metric materialParameterHash is missing" in failure for failure in failures))
        self.assertTrue(any("GL46 required metric streamBindingQueries is missing" in failure for failure in failures))

    def test_performance_budget_requires_positive_p1_evidence_on_modern_tiers(self) -> None:
        aggregate = {
            "sampleCount": 1,
            "latest": {
                "productTier": "GL46",
                "gpuFrameMs": 1.0,
                "postOutputPostNodes": 0,
                "postOutputOutputs": 0,
                "postOutputLegacyFallback": 0,
                "postOutputPostHash": 0,
                "postOutputOutputHash": 0,
                "postOutputPlanHash": 0,
                "postOutputFallbackMask": 0,
                "materialPrograms": 0,
                "materialBindAttempts": 0,
                "materialCacheMisses": 0,
                "materialCompileFailures": 0,
                "materialLinkFailures": 0,
                "materialPrecacheFailures": 0,
                "materialBindFailures": 0,
                "materialParameterBlocks": 0,
                "materialParameterHash": 0,
                "materialInvalidParameterBlocks": 0,
                "streamBindingQueries": 0,
                "streamBindingCacheHits": 0,
                "streamBindingRestores": 0,
            },
            "max": {},
        }

        failures = glx_runtime_sweep.evaluate_performance_budget(
            aggregate,
            glx_runtime_sweep.DEFAULT_PERFORMANCE_BUDGET,
        )

        self.assertTrue(any("GL46 min postOutputPostNodes missed" in failure for failure in failures))
        self.assertTrue(any("GL46 min postOutputPostHash missed" in failure for failure in failures))
        self.assertTrue(any("GL46 min postOutputOutputHash missed" in failure for failure in failures))
        self.assertTrue(any("GL46 min postOutputPlanHash missed" in failure for failure in failures))
        self.assertTrue(any("GL46 min materialPrograms missed" in failure for failure in failures))
        self.assertTrue(any("GL46 min materialParameterHash missed" in failure for failure in failures))
        self.assertTrue(any("GL46 min streamBindingRestores missed" in failure for failure in failures))

    def test_performance_budget_allows_legacy_post_output_fallback_on_gl2x_only(self) -> None:
        gl2x = {
            "sampleCount": 1,
            "latest": {
                "productTier": "GL2X",
                "postOutputLegacyFallback": 1,
            },
            "max": {},
        }

        self.assertEqual(
            glx_runtime_sweep.evaluate_performance_budget(
                gl2x,
                glx_runtime_sweep.DEFAULT_PERFORMANCE_BUDGET,
            ),
            [],
        )

        gl46 = {
            "sampleCount": 1,
            "latest": {
                "productTier": "GL46",
                "gpuFrameMs": 1.0,
                "postOutputPostNodes": 2,
                "postOutputOutputs": 1,
                "postOutputLegacyFallback": 1,
                "postOutputPostHash": 1,
                "postOutputOutputHash": 1,
                "postOutputPlanHash": 1,
                "postOutputFallbackMask": 1,
                "materialPrograms": 1,
                "materialBindAttempts": 1,
                "materialCacheMisses": 0,
                "materialCompileFailures": 0,
                "materialLinkFailures": 0,
                "materialPrecacheFailures": 0,
                "materialBindFailures": 0,
                "materialParameterBlocks": 1,
                "materialParameterHash": 1,
                "materialInvalidParameterBlocks": 0,
                "streamBindingQueries": 1,
                "streamBindingCacheHits": 1,
                "streamBindingRestores": 1,
            },
            "max": {},
        }

        failures = glx_runtime_sweep.evaluate_performance_budget(
            gl46,
            glx_runtime_sweep.DEFAULT_PERFORMANCE_BUDGET,
        )

        self.assertTrue(any("GL46 max postOutputLegacyFallback exceeded" in failure for failure in failures))
        self.assertTrue(any("GL46 max postOutputFallbackMask exceeded" in failure for failure in failures))

    def test_rc_stress_budget_allows_staged_screen_video_material_streams(self) -> None:
        aggregate = {
            "sampleCount": 1,
            "latest": {},
            "max": {
                "streamDrawScreenMaps": 2,
                "streamDrawVideoMaps": 2,
                "streamDrawDynamicLights": 0,
            },
        }

        rc_proof_failures = glx_runtime_sweep.evaluate_performance_budget(
            aggregate,
            glx_runtime_sweep.performance_budget_for_gate(
                "rc-proof",
                glx_runtime_sweep.DEFAULT_PERFORMANCE_BUDGET,
            ),
        )
        rc_stress_failures = glx_runtime_sweep.evaluate_performance_budget(
            aggregate,
            glx_runtime_sweep.performance_budget_for_gate(
                "rc-stress",
                glx_runtime_sweep.DEFAULT_PERFORMANCE_BUDGET,
            ),
        )

        self.assertTrue(any("streamDrawScreenMaps" in failure for failure in rc_proof_failures))
        self.assertTrue(any("streamDrawVideoMaps" in failure for failure in rc_proof_failures))
        self.assertEqual(rc_stress_failures, [])

    def test_performance_budget_merges_tier_overrides(self) -> None:
        budget = glx_runtime_sweep.merge_budget(
            glx_runtime_sweep.DEFAULT_PERFORMANCE_BUDGET,
            {
                "tiers": {
                    "GL2X": {
                        "max": {
                            "draws": 5,
                        }
                    }
                }
            },
        )

        self.assertEqual(budget["tiers"]["GL2X"]["max"]["draws"], 5)  # type: ignore[index]
        self.assertEqual(budget["tiers"]["GL2X"]["max"]["materialBinds"], 12000)  # type: ignore[index]

    def test_performance_baseline_approval_then_compare(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "glx-performance.json"
            manifest = {
                "runId": "baseline-run",
                "gate": "rc-parity",
                "profile": "glx-parity",
                "maps": ["q3dm1"],
                "demos": ["demo1"],
                "proofCorpus": proof_corpus_for_gate("rc-parity"),
            }
            baseline_aggregate = {
                "sampleCount": 1,
                "latest": {"tier": "GL2X"},
                "max": {
                    "draws": 100,
                    "drawIndexes": 200,
                    "streamDrawDepthFragment": 3,
                    "streamDrawFallbacks": 0,
                },
            }
            current_aggregate = {
                "sampleCount": 1,
                "latest": {"tier": "GL2X"},
                "max": {
                    "draws": 121,
                    "drawIndexes": 200,
                    "streamDrawDepthFragment": 3,
                    "streamDrawFallbacks": 0,
                },
            }

            glx_runtime_sweep.write_performance_baseline(path, baseline_aggregate, manifest)
            baseline = glx_runtime_sweep.load_json_file(path)
            self.assertEqual(
                baseline["proofCorpus"]["version"],
                glx_runtime_sweep.GLX_PROOF_CORPUS_VERSION,
            )
            failures, comparisons = glx_runtime_sweep.compare_performance_baseline(
                current_aggregate,
                baseline,
                0.20,
            )

            self.assertTrue(any("draws" in failure for failure in failures))
            self.assertTrue(
                any(
                    comparison["metric"] == "draws" and comparison["status"] == "failed"
                    for comparison in comparisons
                )
            )
            self.assertTrue(
                any(
                    comparison["metric"] == "streamDrawDepthFragment" and comparison["status"] == "passed"
                    for comparison in comparisons
                )
            )

            failures, comparisons = glx_runtime_sweep.compare_performance_baseline(
                baseline_aggregate,
                baseline,
                0.20,
            )
            self.assertEqual(failures, [])
            self.assertTrue(all(comparison["status"] == "passed" for comparison in comparisons))

    def test_gate_evaluation_reports_performance_budget_failures(self) -> None:
        manifest = {
            "gate": "rc-smoke",
            "dryRun": False,
            "performanceFailures": [
                "Performance budget max streamDrawFallbacks exceeded: 1 > 0.",
            ],
            "runs": [
                {
                    "type": "switch-screenshots",
                    "status": "passed",
                    "screenshots": [
                        {"name": "shot", "found": True, "histogram": screenshot_histogram()},
                    ],
                    "diagnostics": {
                        "found": True,
                        "failures": [],
                        "metrics": color_diagnostics_metrics(),
                    },
                    "performance": locked_performance_sample(),
                },
            ],
            "renderers": ["opengl", "glx"],
            "demos": [],
        }

        failures = glx_runtime_sweep.evaluate_gate(manifest)
        self.assertTrue(any("performance budget failures" in failure for failure in failures))


if __name__ == "__main__":
    unittest.main()

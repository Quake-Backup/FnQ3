from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SWEEP_PATH = ROOT / "scripts" / "glx_runtime_sweep.py"
PROMOTION_PATH = ROOT / "scripts" / "glx_promotion.py"
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


def locked_performance_sample() -> dict[str, object]:
    return {
        "found": True,
        "sampleCount": 1,
        "latest": locked_pass_schedule_latest(),
        "max": {},
    }


def proof_corpus_for_gate(gate: str) -> dict[str, object]:
    requirements = glx_runtime_sweep.RC_GATE_PRESETS[gate]["requirements"]
    return glx_runtime_sweep.proof_corpus_manifest(
        glx_runtime_sweep.GLX_GATE_CORPUS_SCENES[gate],
        requirements.get("required_corpus_tags", ()),
        requirements.get("required_parity_suites", ()),
    )


def release_proof_manifest(gate: str, platform_id: str) -> dict[str, object]:
    manifest = {
        "runId": f"{platform_id}-{gate}",
        "createdUtc": "2026-05-10T12:00:00+00:00",
        "gate": gate,
        "dryRun": False,
        "proofPlatform": platform_id,
        "maps": glx_runtime_sweep.corpus_targets(
            glx_runtime_sweep.GLX_GATE_CORPUS_SCENES[gate],
            "map",
        ),
        "demos": glx_runtime_sweep.corpus_targets(
            glx_runtime_sweep.GLX_GATE_CORPUS_SCENES[gate],
            "demo",
        ),
        "renderers": ["opengl", "glx"],
        "proofCorpus": proof_corpus_for_gate(gate),
        "performanceFailures": [],
        "runs": [
            {
                "type": "switch-screenshots",
                "status": "passed",
                "screenshots": [
                    {
                        "name": "shot",
                        "found": True,
                        "baselineKey": f"{gate}-{platform_id}-shot",
                        "baselineStatus": "passed" if gate == "rc-proof" else "not-compared",
                        "comparison": {"status": "passed"} if gate == "rc-proof" else {},
                    },
                ],
                "diagnostics": {"found": True, "failures": []},
                "performance": locked_performance_sample(),
            },
        ],
    }
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
    return manifest


def ownership_proof_manifest(platform_id: str, calls: int = 0, items: int = 0) -> dict[str, object]:
    return {
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
                    },
                ],
                "diagnostics": {
                    "found": True,
                    "failures": [],
                    "metrics": {
                        "ownership": {
                            "calls": calls,
                            "items": items,
                        },
                    },
                },
            },
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
    def test_default_executable_candidates_do_not_include_opengl_wrappers(self) -> None:
        names = glx_runtime_sweep.candidate_exe_names()

        self.assertTrue(any(name.startswith("fnquake3.glx") for name in names))
        self.assertTrue(any(not name.startswith("fnquake3.glx") for name in names))
        self.assertFalse(any("opengl" in name for name in names))

    def test_default_executable_resolution_does_not_pick_opengl_wrapper(self) -> None:
        old_output = glx_runtime_sweep.DEFAULT_OUTPUT

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            names = glx_runtime_sweep.candidate_exe_names()
            neutral_name = next(name for name in names if not name.startswith("fnquake3.glx"))
            opengl_name = (
                "fnquake3.opengl.x64.exe"
                if glx_runtime_sweep.os.name == "nt"
                else "fnquake3.opengl"
            )

            glx_runtime_sweep.DEFAULT_OUTPUT = root
            try:
                (root / opengl_name).touch()
                with self.assertRaises(FileNotFoundError):
                    glx_runtime_sweep.resolve_exe(None)

                (root / neutral_name).touch()
                self.assertEqual(
                    glx_runtime_sweep.resolve_exe(None),
                    (root / neutral_name).resolve(),
                )
            finally:
                glx_runtime_sweep.DEFAULT_OUTPUT = old_output


class GlxRendererSourceCoverageTests(unittest.TestCase):
    def test_requested_glx_renderer_load_failure_is_fatal(self) -> None:
        client_source = (ROOT / "code" / "client" / "cl_main.c").read_text(encoding="utf-8")
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

        self.assertIn("`r_hdr`: Selects the scene-linear HDR render pipeline.", display_doc)
        self.assertIn("`r_hdrPrecision`", display_doc)
        self.assertIn("r_hdr` now means scene-linear pipeline intent", glx_doc)
        self.assertNotIn("`r_hdr`: Controls framebuffer precision.", display_doc)
        self.assertNotIn("HDR precision mode", glx_doc)
        for source in (renderer_init, vulkan_init):
            self.assertIn("Selects the scene-linear HDR render pipeline", source)
            self.assertIn("r_hdrPrecision", source)
            self.assertNotIn("Enables high dynamic range frame buffer texture format", source)
        self.assertIn("SceneColorSpace::SceneLinear", glx_ir)
        self.assertIn("ToneMapOperator::Aces", glx_ir)

    def test_task_q_color_pipeline_sources_are_audited(self) -> None:
        renderer_common = (ROOT / "code" / "renderer" / "tr_common.h").read_text(encoding="utf-8")
        renderer_image = (ROOT / "code" / "renderer" / "tr_image.c").read_text(encoding="utf-8")
        renderer_arb = (ROOT / "code" / "renderer" / "tr_arb.c").read_text(encoding="utf-8")
        vulkan_image = (ROOT / "code" / "renderervk" / "tr_image.c").read_text(encoding="utf-8")
        glx_module = (ROOT / "code" / "rendererglx" / "glx_module.cpp").read_text(encoding="utf-8")
        audit_doc = COLORSPACE_AUDIT_PATH.read_text(encoding="utf-8")

        self.assertIn("IMGFLAG_COLORSPACE_SRGB", renderer_common)
        self.assertIn("IMAGE_COLORSPACE_SRGB", renderer_common)
        self.assertIn("GL_SRGB8_ALPHA8", renderer_image)
        self.assertIn("textureSrgbAvailable", renderer_image)
        self.assertIn("GL_FRAMEBUFFER_SRGB", renderer_arb)
        self.assertIn("srgbCutoff", renderer_arb)
        self.assertIn("VK_FORMAT_R8G8B8A8_SRGB", vulkan_image)
        self.assertIn("glx: color audit srgb-decode", glx_module)
        for text in ("Authored color maps", "Lightmaps", "GL_FRAMEBUFFER_SRGB", "Screenshot/video capture"):
            self.assertIn(text, audit_doc)

    def test_task_r_color_grading_sources_are_covered(self) -> None:
        renderer_arb = (ROOT / "code" / "renderer" / "tr_arb.c").read_text(encoding="utf-8")
        vulkan_gamma = (ROOT / "code" / "renderervk" / "shaders" / "gamma.frag").read_text(encoding="utf-8")
        vulkan_backend = (ROOT / "code" / "renderervk" / "vk.c").read_text(encoding="utf-8")
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
        self.assertIn("vk_color_grade_lut_descriptor", vulkan_backend)
        self.assertIn("color_grade_mode", vulkan_backend)
        self.assertIn("LiftGammaGainLut3D", glx_ir)
        self.assertIn("PostNodeKind::Grade", glx_module)
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
        sdl_glimp = (ROOT / "code" / "sdl" / "sdl_glimp.c").read_text(encoding="utf-8")
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
        self.assertIn("vk_output_request_wants_hdr10", vulkan_backend)
        self.assertIn("output backend", glx_runtime_sweep.__dict__["GLX_OUTPUT_BACKEND_RE"].pattern)
        for cvar in ("r_outputBackend", "r_outputAllowExperimentalLinuxHDR"):
            self.assertIn(cvar, display_doc)

    def test_task_t_release_proof_policy_sources_are_covered(self) -> None:
        sweep_script = SWEEP_PATH.read_text(encoding="utf-8")
        release_script = (ROOT / "scripts" / "release.py").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "glx-verification.yml").read_text(encoding="utf-8")
        rc_gates = (ROOT / "docs" / "fnquake3" / "GLX_RC_GATES.md").read_text(encoding="utf-8")

        for text in (
            "GLX_BLOCKING_RELEASE_PLATFORMS",
            "GLX_RELEASE_REQUIRED_GATES",
            "validate_release_proof_root",
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
        ):
            self.assertIn(text, sweep_script)

        for suite_id in ("screenshot", "demo-playback", "hud", "shadow", "bloom", "cel-shading"):
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
            "check_feature_matrix",
            "check_release_proof_root",
            "check_ownership_proof",
            "check_renderer_source_policy",
            "policyViolation",
        ):
            self.assertIn(text, promotion_script)

        self.assertIn("promotion_report", release_script)
        self.assertIn("glx_promotion", release_script)
        self.assertIn("scripts/glx_promotion.py", workflow)
        self.assertIn("glx-promotion.json", workflow)
        for text in ("Migration Alias Plan", "OpenGL2 Legacy Flag Plan", "Rollback Package Contract"):
            self.assertIn(text, promotion_doc)
        self.assertIn("scripts/glx_promotion.py --require-ready", final_contract)

    def test_task_x_productization_sources_are_covered(self) -> None:
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        build_doc = (ROOT / "BUILD.md").read_text(encoding="utf-8")
        display_doc = (ROOT / "docs" / "DISPLAY.md").read_text(encoding="utf-8")
        screenshots_doc = (ROOT / "docs" / "SCREENSHOTS.md").read_text(encoding="utf-8")
        glx_doc = (ROOT / "docs" / "GLX.md").read_text(encoding="utf-8")
        renderer_doc = (ROOT / "docs" / "fnquake3" / "GLX_RENDERER.md").read_text(encoding="utf-8")
        readme_template = (ROOT / "docs" / "templates" / "README.md.in").read_text(encoding="utf-8")
        release_script = (ROOT / "scripts" / "release.py").read_text(encoding="utf-8")

        self.assertIn('OPTION(USE_GLX "Build the GLx OpenGL-lineage renderer module" ON)', cmake)
        self.assertRegex(makefile, r"(?m)^USE_GLX\s*=\s*1$")
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
            self.assertTrue(diff.exists())

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


class GlxRuntimeSweepDiagnosticTests(unittest.TestCase):
    def test_glx_diagnostics_accept_clean_rc_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "switch.log"
            log.write_text(
                "\n".join(
                    [
                        "  material renderer: enabled, ready yes, GLSL 1.20",
                        "  material compiles: 24 attempts, 0 compile failures, 0 link failures, precache 0/24, bind failures 0, labels 0",
                        "  material fallbacks: unsupported 0, disabled 0, not-ready 0, full 0, discarded without GL delete 0",
                        "  material compiler plans: compiled 12, unsupported 0, last unsupported 0x0 (none)",
                        "  product tier: GL2X",
                        "  GL2X programmable executor: active yes, client-memory fallback yes, stream uploads yes, material compiler yes, postprocess-lite yes, modern post chain no, scene-linear output no",
                        "  GL2X programmable support: common materials yes, dynamic entities yes, lightmaps yes, multitexture yes, fog yes, sprites yes, beams yes, screenshots yes, demos yes",
                        "  glx: ownership legacy delegation 0 calls/0 items, generic 0, vbo-device 0, vbo-soft 0, arrays 0",
                        f"  pass schedule: valid 9/{glx_runtime_sweep.GLX_EXPECTED_PASS_SCHEDULE_HASH} {glx_runtime_sweep.GLX_EXPECTED_PASS_SCHEDULE}",
                        "  FBO: requested yes, ready yes, programs yes, framebuffer funcs yes, reason: FBO ready",
                        "  FBO lifecycle: 1 init attempts, 1 ready, 0 failed, 0 disabled, 0 shutdowns",
                        "  color pipeline: space scene-linear, transfer sdr-srgb, tone-map aces, exposure 1.00, grade lgg-lut3d, paper-white 203 nits, max 1000 nits",
                        "  color grade stage: mode lgg-lut3d, lift 0.01/0.02/0.03, gamma 1.10/1.00/0.95, gain 1.05/1.00/0.98, white-point 6504->6000 K, lut-size 16, lut-scale 4.00",
                        "  color audit: srgb-decode yes requested yes available yes, framebuffer-srgb no requested yes available yes, capture sdr-srgb",
                        "  output backend: request auto, selected sdr-srgb, native windows-scrgb, hardware no, experimental no, display-hdr yes, headroom 4.00, sdr-white 203 nits, display-max 812 nits, icc yes/2048, driver windows, display HDR Panel, reason: test",
                        "  bloom create: last success, 1/1 ready, texture-unit failures 0, FBO failures 0",
                        "  bloom passes: calls 1, rendered 1, final 1, pre-final 0, skipped 0, failures 0, mode1 0, mode2 1, reflections 0",
                        "  copies/blits: screen-map copies 0, MSAA blits 0 (0 depth), SSAA blits 0, last output bloom-final",
                        "  dynamic stream buffer: yes",
                        "  dynamic stream sync: yes, fences 1, waits 0, timeouts 0, failures 0, pending skips 0",
                        "  dynamic stream reservations: 1, commits: 1, wraps: 0, same-frame wrap rejects: 0, orphans: 0",
                        "  dynamic stream uploads: 1 calls, 0.01 MB, failures 0",
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
            stream_draw = diagnostics["metrics"]["streamDraw"]
            self.assertEqual(stream_draw["draws"], 1)
            self.assertEqual(stream_draw["dynamicLights"], 0)
            self.assertEqual(stream_draw["screenMaps"], 0)
            self.assertEqual(stream_draw["videoMaps"], 0)
            self.assertEqual(stream_draw["shadows"], 0)
            self.assertEqual(stream_draw["skips"], 2)
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
            self.assertEqual(color_pipeline["toneMap"], "aces")
            self.assertEqual(color_pipeline["grade"], "lgg-lut3d")
            self.assertEqual(color_pipeline["exposure"], 1.0)
            self.assertEqual(color_pipeline["paperWhite"], 203.0)
            self.assertEqual(color_pipeline["maxOutput"], 1000.0)
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
            output_backend = diagnostics["metrics"]["outputBackend"]
            self.assertEqual(output_backend["request"], "auto")
            self.assertEqual(output_backend["selected"], "sdr-srgb")
            self.assertEqual(output_backend["native"], "windows-scrgb")
            self.assertEqual(output_backend["displayHdr"], 1)
            self.assertEqual(output_backend["headroom"], 4.0)
            self.assertEqual(output_backend["displayMax"], 812.0)
            self.assertEqual(output_backend["icc"], 1)

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
                        {"name": "shot", "found": True},
                    ],
                    "diagnostics": {
                        "found": True,
                        "failures": ["GLx material compile failures: 1."],
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
        self.assertEqual(glx_runtime_sweep.PROFILE_CVARS["glx-color"]["r_colorGrade"], "3")

    def test_task_v_parity_suites_are_versioned_and_gate_enforced(self) -> None:
        required_suites = (
            "screenshot",
            "demo-playback",
            "hud",
            "shadow",
            "bloom",
            "cel-shading",
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
                            "baselineStatus": "passed",
                            "comparison": {"status": "passed"},
                        },
                    ],
                    "diagnostics": {"found": True, "failures": []},
                    "performance": locked_performance_sample(),
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
                    "timedemoMetrics": {"fps": 95.0},
                },
            ],
            "renderers": ["opengl", "glx"],
            "maps": glx_runtime_sweep.corpus_targets(
                glx_runtime_sweep.GLX_GATE_CORPUS_SCENES["rc-proof"],
                "map",
            ),
            "demos": ["demo1"],
            "proofCorpus": proof_corpus_for_gate("rc-proof"),
            "screenshotBaselineDir": "proof/screenshots",
            "performanceBaselinePath": "proof/performance-baseline.json",
            "performanceBaselineStatus": "compared",
            "performanceComparisons": [{"metric": "draws", "status": "passed"}],
        }

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
                    "screenshots": [{"name": "shot", "found": True, "baselineStatus": "approved"}],
                    "diagnostics": {"found": True, "failures": []},
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

    def test_current_tree_is_blocked_but_not_promoted(self) -> None:
        report = glx_promotion.promotion_report()

        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["policyViolation"])
        self.assertEqual(report["sourcePolicy"]["cmakeDefault"], "opengl")
        self.assertEqual(report["sourcePolicy"]["makeDefault"], "opengl")
        self.assertEqual(report["sourcePolicy"]["cmakeUseGlxDefault"], "ON")
        self.assertEqual(report["sourcePolicy"]["makeUseGlxDefault"], "1")
        checks = {check["name"]: check for check in report["checks"]}
        self.assertEqual(checks["feature-matrix-green"]["status"], "blocked")
        self.assertGreater(len(checks["feature-matrix-green"]["blockers"]), 0)
        self.assertEqual(checks["migration-and-rollback-doc"]["status"], "passed")

    def test_complete_runtime_and_ownership_proof_still_waits_for_green_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_complete_proof_root(root)

            report = glx_promotion.promotion_report(root)
            checks = {check["name"]: check for check in report["checks"]}

            self.assertEqual(checks["blocking-runtime-proof"]["status"], "passed")
            self.assertEqual(checks["ownership-proof"]["status"], "passed")
            self.assertEqual(checks["feature-matrix-green"]["status"], "blocked")
            self.assertEqual(report["status"], "blocked")

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
                        "glx: material renderer on/ready programs 25, binds 12/13 attempts, switches 4, cache 5/6, failures 0 compile/0 link/0 precache/0 bind, labels 8",
                        "glx: postprocess fbo ready 640x480 capture 640x480 bloom 2, frames 3 final 2 prefinal 1 gamma 0/3, copies 4, msaa 5, ssaa 6, last bloom-final",
                        "glx: color pipeline scene-linear precision 16 transfer sdr-srgb tone-map aces exposure 1.00 bloom-threshold 0.75/2 knee 0.50 grade lgg-lut3d paper-white 203 max 1000",
                        "glx: color grade mode lgg-lut3d lift 0.01/0.02/0.03 gamma 1.10/1.00/0.95 gain 1.05/1.00/0.98 white-point 6504->6000 lut-size 16 lut-scale 4.00",
                        "glx: color audit srgb-decode yes requested yes available yes framebuffer-srgb no requested yes available yes capture sdr-srgb",
                        "glx: output backend request hdr10-pq selected hdr10-pq native windows-scrgb hardware yes experimental no display-hdr yes headroom 4.00 sdr-white 203 display-max 812 icc yes/2048",
                        "glx: stream draws 7/8 attempts, 90 idx, 0.50MB/index 0.10MB/tex1 0.20MB, mt 1, fog 2, depthfrag 3, texmod 4, env 5, dlight 0, screen 0, video 0, shadow 2, beam 3, post 4, fallbacks 0, skips 1",
                        "glx: stream categories entity 2/2, particle 1/1, poly 1/1, mark 1/1, weapon 1/1, ui 1/1, beam 3/3, special 4/4",
                        "glx: stream reservation last 256 bytes at 1024 using map-range, largest 4096 bytes, same-frame wrap rejects 0",
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
            self.assertEqual(performance["latest"]["passScheduleValid"], 1)
            self.assertEqual(performance["latest"]["passScheduleCount"], 9)
            self.assertEqual(performance["latest"]["passScheduleHash"], glx_runtime_sweep.GLX_EXPECTED_PASS_SCHEDULE_HASH)
            self.assertEqual(performance["latest"]["passScheduleOrder"], glx_runtime_sweep.GLX_EXPECTED_PASS_SCHEDULE)
            self.assertEqual(performance["latest"]["materialPrograms"], 25)
            self.assertEqual(performance["latest"]["colorSpace"], "scene-linear")
            self.assertEqual(performance["latest"]["hdrPrecision"], 16)
            self.assertEqual(performance["latest"]["outputTransfer"], "sdr-srgb")
            self.assertEqual(performance["latest"]["toneMap"], "aces")
            self.assertEqual(performance["latest"]["toneMapExposure"], 1.0)
            self.assertEqual(performance["latest"]["bloomThreshold"], 0.75)
            self.assertEqual(performance["latest"]["bloomThresholdMode"], 2)
            self.assertEqual(performance["latest"]["bloomSoftKnee"], 0.5)
            self.assertEqual(performance["latest"]["colorGrade"], "lgg-lut3d")
            self.assertEqual(performance["latest"]["colorGradeMode"], "lgg-lut3d")
            self.assertEqual(performance["latest"]["colorGradeLiftR"], 0.01)
            self.assertEqual(performance["latest"]["colorGradeGammaR"], 1.10)
            self.assertEqual(performance["latest"]["colorGradeGainR"], 1.05)
            self.assertEqual(performance["latest"]["colorGradeWhiteTarget"], 6000.0)
            self.assertEqual(performance["latest"]["colorGradeLutSize"], 16.0)
            self.assertEqual(performance["latest"]["colorGradeLutScale"], 4.0)
            self.assertEqual(performance["latest"]["paperWhiteNits"], 203.0)
            self.assertEqual(performance["latest"]["maxOutputNits"], 1000.0)
            self.assertEqual(performance["latest"]["colorSrgbDecode"], 1)
            self.assertEqual(performance["latest"]["colorSrgbAvailable"], 1)
            self.assertEqual(performance["latest"]["colorFramebufferSrgb"], 0)
            self.assertEqual(performance["latest"]["captureColorSpace"], "sdr-srgb")
            self.assertEqual(performance["latest"]["outputBackendRequest"], "hdr10-pq")
            self.assertEqual(performance["latest"]["outputBackendSelected"], "hdr10-pq")
            self.assertEqual(performance["latest"]["outputBackendNative"], "windows-scrgb")
            self.assertEqual(performance["latest"]["outputBackendHardware"], 1)
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
                        {"name": "shot", "found": True},
                    ],
                    "diagnostics": {
                        "found": True,
                        "failures": [],
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
                        {"name": "shot", "found": True},
                    ],
                    "diagnostics": {
                        "found": True,
                        "failures": [],
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
                        {"name": "shot", "found": True},
                    ],
                    "diagnostics": {
                        "found": True,
                        "failures": [],
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

    def test_performance_budget_requires_gpu_time_on_modern_tiers(self) -> None:
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
                        {"name": "shot", "found": True},
                    ],
                    "diagnostics": {
                        "found": True,
                        "failures": [],
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

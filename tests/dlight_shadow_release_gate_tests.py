from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE_PATH = ROOT / "scripts" / "dlight_shadow_release_gate.py"

spec = importlib.util.spec_from_file_location("dlight_shadow_release_gate", GATE_PATH)
assert spec is not None
dlight_shadow_release_gate = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(dlight_shadow_release_gate)


def write_source_defaults(root: Path, glx: str = "0", vulkan: str = "0") -> None:
    sources = {
        "code/renderer/tr_init.c": glx,
        "code/renderervk/tr_init.c": vulkan,
    }
    for relative, value in sources.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f'r_dlightShadows = ri.Cvar_Get( "r_dlightShadows", "{value}", CVAR_ARCHIVE_ND | CVAR_LATCH );\n',
            encoding="utf-8",
        )


def dlight_shadow_run(renderer: str) -> dict[str, object]:
    categories = dlight_shadow_release_gate.REQUIRED_DLIGHT_SHADOW_CATEGORIES
    return {
        "type": "dlight-shadow-scenes",
        "status": "passed",
        "renderer": renderer,
        "screenshots": [
            {
                "name": f"{renderer}-dlight-{category}",
                "found": True,
                "shadowScene": True,
                "scene": category,
                "evidenceCategories": [category],
            }
            for category in categories
        ],
        "dlightShadow": {
            "found": True,
            "max": {"planned": 2, "renderLights": 2},
            "scenes": {
                category: {"max": {"planned": 2, "renderLights": 2}}
                for category in categories
            },
        },
    }


def runtime_manifest(renderer: str) -> dict[str, object]:
    return {
        "gate": dlight_shadow_release_gate.EXPECTED_RUNTIME_GATES[renderer],
        "dryRun": False,
        "runs": [
            {
                "type": "map-screenshots",
                "status": "passed",
                "screenshots": [{"name": f"{renderer}-map", "found": True}],
            },
            dlight_shadow_run(renderer),
        ],
        "gateFailures": [],
    }


def renderdoc_record(renderer: str) -> dict[str, object]:
    return {
        "status": "passed",
        "captureFile": f"{renderer}.rdc",
        "checks": {
            check: True
            for check in dlight_shadow_release_gate.REQUIRED_RENDERDOC_CHECKS[renderer]
        },
    }


def complete_evidence() -> dict[str, object]:
    return {
        "version": 1,
        "build": {
            "glx": {"status": "passed"},
            "vulkan": {"status": "passed"},
        },
        "shaders": {
            "glx": {"status": "passed"},
            "vulkan": {
                "status": "passed",
                "variants": list(dlight_shadow_release_gate.VULKAN_SHADER_VARIANTS),
            },
        },
        "runtimeSweeps": {
            "glx": "glx-manifest.json",
            "vulkan": "vulkan-manifest.json",
        },
        "renderdoc": {
            "glx": renderdoc_record("glx"),
            "vulkan": renderdoc_record("vulkan"),
        },
    }


def write_evidence(root: Path, evidence: dict[str, object]) -> Path:
    (root / "glx-manifest.json").write_text(
        json.dumps(runtime_manifest("glx")),
        encoding="utf-8",
    )
    (root / "vulkan-manifest.json").write_text(
        json.dumps(runtime_manifest("vulkan")),
        encoding="utf-8",
    )
    path = root / "evidence.json"
    path.write_text(json.dumps(evidence), encoding="utf-8")
    return path


class DlightShadowReleaseGateTests(unittest.TestCase):
    def test_complete_evidence_allows_default_enable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_source_defaults(root)
            evidence_path = write_evidence(root, complete_evidence())

            report = dlight_shadow_release_gate.release_gate_report(
                evidence_path,
                source_root=root,
            )

        self.assertEqual(report["status"], "ready")
        self.assertTrue(report["defaultEnableAllowed"])
        self.assertEqual(report["failures"], [])

    def test_missing_renderdoc_check_blocks_default_enable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_source_defaults(root)
            evidence = complete_evidence()
            renderdoc = evidence["renderdoc"]  # type: ignore[index]
            assert isinstance(renderdoc, dict)
            vulkan = renderdoc["vulkan"]
            assert isinstance(vulkan, dict)
            checks = vulkan["checks"]
            assert isinstance(checks, dict)
            checks.pop("layoutTransitions")
            evidence_path = write_evidence(root, evidence)

            report = dlight_shadow_release_gate.release_gate_report(
                evidence_path,
                source_root=root,
            )

        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["defaultEnableAllowed"])
        self.assertTrue(
            any("layoutTransitions" in failure for failure in report["failures"])
        )

    def test_runtime_sweep_requires_screenshot_and_log_categories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_source_defaults(root)
            evidence = complete_evidence()
            (root / "glx-manifest.json").write_text(
                json.dumps(runtime_manifest("glx")),
                encoding="utf-8",
            )
            manifest = runtime_manifest("vulkan")
            shadow_run = manifest["runs"][1]  # type: ignore[index]
            assert isinstance(shadow_run, dict)
            shadow_run["screenshots"] = [
                shot
                for shot in shadow_run["screenshots"]  # type: ignore[index]
                if shot["evidenceCategories"] != ["stress-light-budget"]
            ]
            dlight_shadow = shadow_run["dlightShadow"]
            assert isinstance(dlight_shadow, dict)
            scenes = dlight_shadow["scenes"]
            assert isinstance(scenes, dict)
            scenes.pop("stress-light-budget")
            (root / "vulkan-manifest.json").write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )
            evidence_path = root / "evidence.json"
            evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

            report = dlight_shadow_release_gate.release_gate_report(
                evidence_path,
                source_root=root,
            )

        self.assertEqual(report["status"], "blocked")
        self.assertTrue(
            any("stress-light-budget" in failure for failure in report["failures"])
        )

    def test_source_default_enabled_before_gate_is_policy_violation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_source_defaults(root, glx="1", vulkan="1")
            evidence = complete_evidence()
            renderdoc = evidence["renderdoc"]  # type: ignore[index]
            assert isinstance(renderdoc, dict)
            renderdoc.pop("vulkan")
            evidence_path = write_evidence(root, evidence)

            report = dlight_shadow_release_gate.release_gate_report(
                evidence_path,
                source_root=root,
            )

        self.assertEqual(report["status"], "failed")
        self.assertTrue(report["policyViolation"])
        self.assertTrue(
            any("enabled by default before" in failure for failure in report["failures"])
        )

    def test_cli_writes_ready_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_source_defaults(root)
            evidence_path = write_evidence(root, complete_evidence())
            summary_path = root / "summary.json"

            exit_code = dlight_shadow_release_gate.main(
                [
                    "--evidence",
                    str(evidence_path),
                    "--source-root",
                    str(root),
                    "--summary",
                    str(summary_path),
                    "--require-ready",
                ]
            )
            summary = json.loads(summary_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(summary["status"], "ready")


if __name__ == "__main__":
    unittest.main()

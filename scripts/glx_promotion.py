from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

from glx_runtime_sweep import (
    GLX_BLOCKING_RELEASE_PLATFORMS,
    GLX_PRODUCT_TIERS,
    evaluate_gate,
    load_json_file,
    normalize_proof_platform,
    proof_platform_for_manifest,
    run_status,
    validate_release_proof_root,
)


ROOT = Path(__file__).resolve().parents[1]
FEATURE_MATRIX_PATH = ROOT / "docs" / "fnquake3" / "GLX_FEATURE_MATRIX.md"
FINAL_CONTRACT_PATH = ROOT / "docs" / "fnquake3" / "GLX_FINAL_CONTRACT.md"
PROMOTION_DOC_PATH = ROOT / "docs" / "fnquake3" / "GLX_PROMOTION.md"
CMAKE_PATH = ROOT / "CMakeLists.txt"
MAKEFILE_PATH = ROOT / "Makefile"

PROMOTION_CHECK_VERSION = 1
PROMOTION_REQUIRED_TIERS = ("GL12", "GL2X", "GL3X", "GL41", "GL46")
PROMOTION_REQUIRED_FEATURE_STATUS = "covered"
PROMOTION_OWNERSHIP_PROFILE = "glx-ownership"
PROMOTION_DOC_REQUIRED_TEXT = (
    "Migration Alias Plan",
    "OpenGL2 Legacy Flag Plan",
    "Rollback Package Contract",
)


def parse_feature_matrix(path: Path = FEATURE_MATRIX_PATH) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| ") or line.startswith("|---"):
            continue
        columns = [column.strip() for column in line.strip().strip("|").split("|")]
        if len(columns) != 6 or columns[0] == "ID":
            continue
        rows.append(
            {
                "id": columns[0],
                "category": columns[1],
                "feature": columns[2],
                "status": columns[3],
                "evidence": columns[4],
                "closure": columns[5],
            }
        )
    return rows


def check_feature_matrix(path: Path = FEATURE_MATRIX_PATH) -> dict[str, object]:
    rows = parse_feature_matrix(path)
    blockers = [
        {
            "id": row["id"],
            "status": row["status"],
            "feature": row["feature"],
        }
        for row in rows
        if row["status"] != PROMOTION_REQUIRED_FEATURE_STATUS
    ]
    return {
        "name": "feature-matrix-green",
        "status": "passed" if rows and not blockers else "blocked",
        "path": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),
        "requiredStatus": PROMOTION_REQUIRED_FEATURE_STATUS,
        "rowCount": len(rows),
        "coveredCount": sum(1 for row in rows if row["status"] == PROMOTION_REQUIRED_FEATURE_STATUS),
        "blockers": blockers,
    }


def check_product_tiers(path: Path = FINAL_CONTRACT_PATH) -> dict[str, object]:
    documented = path.read_text(encoding="utf-8")
    actual_tiers = tuple(sorted(GLX_PRODUCT_TIERS))
    expected_tiers = tuple(sorted(PROMOTION_REQUIRED_TIERS))
    missing_code = sorted(set(expected_tiers).difference(actual_tiers))
    extra_code = sorted(set(actual_tiers).difference(expected_tiers))
    missing_docs = [tier for tier in expected_tiers if f"`{tier}`" not in documented]
    blockers = []
    if missing_code:
        blockers.append("missing code tier(s): " + ", ".join(missing_code))
    if extra_code:
        blockers.append("unexpected code tier(s): " + ", ".join(extra_code))
    if missing_docs:
        blockers.append("missing documented tier(s): " + ", ".join(missing_docs))
    return {
        "name": "five-product-tiers",
        "status": "passed" if not blockers else "blocked",
        "expectedTiers": list(expected_tiers),
        "actualTiers": list(actual_tiers),
        "blockers": blockers,
    }


def _regex_group(path: Path, pattern: str, default: str = "") -> str:
    match = re.search(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
    return match.group(1) if match else default


def check_renderer_source_policy(
    cmake_path: Path = CMAKE_PATH,
    makefile_path: Path = MAKEFILE_PATH,
) -> dict[str, object]:
    cmake_default = _regex_group(
        cmake_path,
        r"SET\s*\(\s*RENDERER_DEFAULT\s+([A-Za-z0-9_]+)\s+CACHE\s+STRING",
    )
    make_default = _regex_group(
        makefile_path,
        r"^RENDERER_DEFAULT\s*=\s*([A-Za-z0-9_]+)\s*$",
    )
    cmake_use_glx_default = _regex_group(
        cmake_path,
        r"OPTION\s*\(\s*USE_GLX\s+\"[^\"]*\"\s+(ON|OFF)\s*\)",
    )
    make_use_glx_default = _regex_group(
        makefile_path,
        r"^USE_GLX\s*=\s*([01])\s*$",
    )
    promoted = any(default and default != "opengl" for default in (cmake_default, make_default))
    blockers = []
    if not cmake_default:
        blockers.append("CMake renderer default could not be read.")
    if not make_default:
        blockers.append("Makefile renderer default could not be read.")
    if cmake_use_glx_default != "ON":
        blockers.append("CMake modular builds must include GLx by default.")
    if make_use_glx_default != "1":
        blockers.append("Make modular builds must include GLx by default.")
    return {
        "name": "renderer-source-policy",
        "status": "promoted" if promoted else ("passed" if not blockers else "blocked"),
        "promoted": promoted,
        "cmakeDefault": cmake_default,
        "makeDefault": make_default,
        "cmakeUseGlxDefault": cmake_use_glx_default,
        "makeUseGlxDefault": make_use_glx_default,
        "blockers": blockers,
    }


def check_release_proof_root(proof_root: Path | None) -> dict[str, object]:
    if proof_root is None:
        return {
            "name": "blocking-runtime-proof",
            "status": "blocked",
            "requiredPlatforms": list(GLX_BLOCKING_RELEASE_PLATFORMS),
            "blockers": ["No GLx proof root was provided."],
        }

    try:
        proof = validate_release_proof_root(proof_root)
    except Exception as exc:  # pragma: no cover - defensive CLI surface
        return {
            "name": "blocking-runtime-proof",
            "status": "blocked",
            "root": str(proof_root),
            "blockers": [str(exc)],
        }

    return {
        "name": "blocking-runtime-proof",
        "status": "passed" if proof.get("status") == "passed" else "blocked",
        "root": str(proof_root),
        "requiredPlatforms": proof.get("requiredPlatforms", []),
        "requiredGates": proof.get("requiredGates", []),
        "blockers": proof.get("failures", []),
        "proof": proof,
    }


def manifest_ownership_metrics(manifest: dict[str, object]) -> dict[str, object]:
    found = False
    max_calls = 0
    max_items = 0
    diagnostic_failures = 0
    for run in manifest.get("runs", []):
        if not isinstance(run, dict):
            continue
        diagnostics = run.get("diagnostics")
        if not isinstance(diagnostics, dict):
            continue
        failures = diagnostics.get("failures", [])
        if isinstance(failures, list):
            diagnostic_failures += len(failures)
        metrics = diagnostics.get("metrics")
        if not isinstance(metrics, dict):
            continue
        ownership = metrics.get("ownership")
        if not isinstance(ownership, dict):
            continue
        found = True
        max_calls = max(max_calls, int(ownership.get("calls", 0)))
        max_items = max(max_items, int(ownership.get("items", 0)))
    return {
        "found": found,
        "calls": max_calls,
        "items": max_items,
        "diagnosticFailures": diagnostic_failures,
        "zeroDelegation": found and max_calls == 0 and max_items == 0 and diagnostic_failures == 0,
    }


def iter_manifest_paths(root: Path) -> Iterable[Path]:
    if not root.exists():
        return ()
    return root.rglob("manifest.json")


def check_ownership_proof(
    proof_root: Path | None,
    required_platforms: Iterable[str] = GLX_BLOCKING_RELEASE_PLATFORMS,
) -> dict[str, object]:
    required_platform_list = [
        normalize_proof_platform(platform_id)
        for platform_id in required_platforms
    ]
    if proof_root is None:
        return {
            "name": "ownership-proof",
            "status": "blocked",
            "requiredProfile": PROMOTION_OWNERSHIP_PROFILE,
            "requiredPlatforms": required_platform_list,
            "blockers": ["No GLx proof root was provided."],
        }

    platform_records: dict[str, dict[str, object]] = {}
    blockers: list[str] = []
    for path in iter_manifest_paths(proof_root):
        try:
            manifest = load_json_file(path)
        except Exception:
            continue
        if not isinstance(manifest, dict):
            continue
        if manifest.get("profile") != PROMOTION_OWNERSHIP_PROFILE:
            continue
        try:
            platform_id = proof_platform_for_manifest(manifest, path)
        except ValueError:
            continue
        if platform_id not in required_platform_list or manifest.get("dryRun"):
            continue
        if run_status(manifest) != "passed":
            continue
        gate_failures = evaluate_gate(manifest)
        if gate_failures:
            continue
        ownership = manifest_ownership_metrics(manifest)
        record = {
            "path": str(path),
            "runId": manifest.get("runId", ""),
            "ownership": ownership,
        }
        existing = platform_records.get(platform_id)
        if existing is None or str(record["runId"]) > str(existing.get("runId", "")):
            platform_records[platform_id] = record

    for platform_id in required_platform_list:
        record = platform_records.get(platform_id)
        if not record:
            blockers.append(
                f"Missing non-dry-run {PROMOTION_OWNERSHIP_PROFILE} proof for {platform_id}."
            )
            continue
        ownership = record.get("ownership", {})
        if not isinstance(ownership, dict) or not ownership.get("zeroDelegation"):
            blockers.append(
                f"{PROMOTION_OWNERSHIP_PROFILE} proof for {platform_id} did not report zero legacy delegation."
            )

    return {
        "name": "ownership-proof",
        "status": "passed" if not blockers else "blocked",
        "requiredProfile": PROMOTION_OWNERSHIP_PROFILE,
        "requiredPlatforms": required_platform_list,
        "platforms": platform_records,
        "blockers": blockers,
    }


def check_migration_doc(path: Path = PROMOTION_DOC_PATH) -> dict[str, object]:
    blockers: list[str] = []
    if not path.exists():
        return {
            "name": "migration-and-rollback-doc",
            "status": "blocked",
            "path": str(path),
            "blockers": ["GLx promotion migration/rollback document is missing."],
        }
    text = path.read_text(encoding="utf-8")
    missing = [required for required in PROMOTION_DOC_REQUIRED_TEXT if required not in text]
    if missing:
        blockers.append("Missing section(s): " + ", ".join(missing))
    return {
        "name": "migration-and-rollback-doc",
        "status": "passed" if not blockers else "blocked",
        "path": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),
        "blockers": blockers,
    }


def promotion_report(proof_root: Path | None = None) -> dict[str, object]:
    checks = [
        check_feature_matrix(),
        check_product_tiers(),
        check_release_proof_root(proof_root),
        check_ownership_proof(proof_root),
        check_migration_doc(),
    ]
    source_policy = check_renderer_source_policy()
    ready = all(check.get("status") == "passed" for check in checks)
    source_promoted = bool(source_policy.get("promoted"))
    policy_violation = source_promoted and not ready
    status = "ready" if ready else "blocked"
    if policy_violation:
        status = "failed"

    blockers = [
        blocker
        for check in checks
        if check.get("status") != "passed"
        for blocker in check.get("blockers", [])  # type: ignore[union-attr]
    ]
    if policy_violation:
        blockers.append(
            "Renderer defaults were promoted before the GLx promotion gate passed."
        )

    return {
        "version": PROMOTION_CHECK_VERSION,
        "status": status,
        "ready": ready,
        "policyViolation": policy_violation,
        "sourcePolicy": source_policy,
        "checks": checks,
        "blockers": blockers,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check whether GLx is ready for renderer promotion.")
    parser.add_argument(
        "--proof-root",
        type=Path,
        help="Directory containing reviewed GLx proof manifests.",
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return a failing exit code unless every promotion requirement passes.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full machine-readable promotion report.",
    )
    return parser.parse_args()


def print_text_report(report: dict[str, object]) -> None:
    def format_blocker(blocker: object) -> str:
        if isinstance(blocker, dict) and "id" in blocker:
            return (
                f"{blocker.get('id')}: {blocker.get('status', 'blocked')} "
                f"({blocker.get('feature', '-')})"
            )
        return str(blocker)

    print(f"GLx promotion status: {report['status']}")
    print(f"Policy violation: {str(bool(report.get('policyViolation'))).lower()}")
    for check in report.get("checks", []):
        if not isinstance(check, dict):
            continue
        print(f"- {check.get('name')}: {check.get('status')}")
        blockers = check.get("blockers", [])
        if isinstance(blockers, list):
            for blocker in blockers[:8]:
                print(f"  - {format_blocker(blocker)}")
    source = report.get("sourcePolicy", {})
    if isinstance(source, dict):
        print(
            "- renderer-source-policy: "
            f"{source.get('status')} "
            f"(cmake={source.get('cmakeDefault')}, make={source.get('makeDefault')}, "
            f"use_glx={source.get('cmakeUseGlxDefault')}/{source.get('makeUseGlxDefault')})"
        )


def main() -> int:
    args = parse_args()
    report = promotion_report(args.proof_root)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_text_report(report)
    if report.get("policyViolation"):
        return 1
    if args.require_ready and report.get("status") != "ready":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fnq3_meta import ROOT, channel_metadata, package_archive_name
from glx_runtime_sweep import (
    GLX_PROOF_CORPUS_DOC,
    release_corpus_manifest,
    validate_release_proof_root,
)
from glx_promotion import (
    PROMOTION_DOC_PATH,
    ROLLBACK_PACKAGE_DOC_PATH,
    check_rollback_package_metadata,
    promotion_report,
)


DEFAULT_DOCS = [
    (ROOT / "LICENSE", Path("LICENSE")),
    (ROOT / "docs" / "fnquake3" / "TECHNICAL.md", Path("docs") / "fnquake3" / "TECHNICAL.md"),
    (
        ROOT / GLX_PROOF_CORPUS_DOC,
        Path(GLX_PROOF_CORPUS_DOC),
    ),
    (
        PROMOTION_DOC_PATH,
        Path("docs") / "fnquake3" / "GLX_PROMOTION.md",
    ),
    (
        ROLLBACK_PACKAGE_DOC_PATH,
        Path("docs") / "fnquake3" / "GLX_ROLLBACK_PACKAGE.md",
    ),
    (
        ROOT / "docs" / "fnquake3" / "GLX_VISUAL_DOSSIER.md",
        Path("docs") / "fnquake3" / "GLX_VISUAL_DOSSIER.md",
    ),
    (
        ROOT / "docs" / "GLX.md",
        Path("docs") / "GLX.md",
    ),
    (ROOT / ".install" / "README.html", Path("README.html")),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package FnQuake3 manual or tagged release artifacts")
    parser.add_argument("--channel", choices=("manual", "release"), required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".install")
    parser.add_argument("--temp-dir", type=Path, default=ROOT / ".tmp" / "release")
    parser.add_argument("--build-date")
    parser.add_argument("--build-number", type=int)
    parser.add_argument("--commit")
    parser.add_argument("--ref-name")
    parser.add_argument(
        "--glx-proof-root",
        type=Path,
        help=(
            "Directory containing non-dry-run GLx runtime proof manifests. "
            "Required for tagged release packaging."
        ),
    )
    parser.add_argument(
        "--glx-rollback-metadata",
        type=Path,
        help=(
            "Reviewed JSON metadata describing the promoted-release rollback "
            "package that keeps the legacy OpenGL renderer available."
        ),
    )
    return parser.parse_args()


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_tree_contents(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        destination = target / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)


def copy_docs(stage_root: Path) -> None:
    for source, dest_relative in DEFAULT_DOCS:
        destination = stage_root / dest_relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def resolve_glx_runtime_proof(args: argparse.Namespace) -> dict[str, object]:
    if args.glx_proof_root is None:
        if args.channel == "release":
            raise ValueError(
                "--glx-proof-root is required for --channel release; "
                "tagged releases need reviewed non-dry-run GLx runtime proof."
            )
        return {
            "required": False,
            "status": "not-required",
            "reason": "manual release packaging records the corpus but does not promote GLx.",
        }

    proof = validate_release_proof_root(args.glx_proof_root)
    proof["required"] = args.channel == "release"
    if proof.get("status") != "passed":
        failures = proof.get("failures", [])
        detail = "; ".join(str(item) for item in failures[:8]) if isinstance(failures, list) else ""
        raise ValueError(
            "GLx runtime proof validation failed"
            + (f": {detail}" if detail else ".")
        )
    return proof


def resolve_glx_rollback_package(
    args: argparse.Namespace,
    glx_promotion: dict[str, object],
) -> dict[str, object]:
    source_policy = glx_promotion.get("sourcePolicy", {})
    promoted_source = (
        isinstance(source_policy, dict)
        and bool(source_policy.get("promoted"))
    )
    required = args.channel == "release" and promoted_source

    if args.glx_rollback_metadata is None:
        return {
            "required": required,
            "status": "missing" if required else "not-required",
            "reason": (
                "promoted GLx release packaging requires rollback metadata"
                if required
                else "current source tree has not promoted GLx as the renderer default"
            ),
        }

    rollback = check_rollback_package_metadata(args.glx_rollback_metadata)
    rollback["required"] = required
    if rollback.get("status") != "passed":
        blockers = rollback.get("blockers", [])
        detail = "; ".join(str(item) for item in blockers[:8]) if isinstance(blockers, list) else ""
        raise ValueError(
            "GLx rollback package metadata validation failed"
            + (f": {detail}" if detail else ".")
        )
    return rollback


def attach_glx_rollback_archives(
    glx_rollback_package: dict[str, object],
    archives: list[dict[str, object]],
) -> dict[str, object]:
    if glx_rollback_package.get("status") != "passed":
        return glx_rollback_package

    archives_by_artifact_dir = {
        str(archive.get("artifact_dir", "")): archive
        for archive in archives
    }
    archives_by_name = {
        str(archive.get("archive", "")): archive
        for archive in archives
    }
    matched_archives: list[dict[str, object]] = []
    blockers: list[str] = []

    for package in glx_rollback_package.get("packages", []):
        if not isinstance(package, dict):
            continue
        package_id = str(package.get("id", "rollback-package"))
        archive = None
        artifact_dir = str(package.get("artifactDir", ""))
        archive_name = str(package.get("archive", ""))
        if artifact_dir:
            archive = archives_by_artifact_dir.get(artifact_dir)
        if archive is None and archive_name:
            archive = archives_by_name.get(archive_name)
        if archive is None:
            blockers.append(
                f"{package_id} did not match a staged release archive."
            )
            continue
        matched_archives.append(
            {
                "package": package_id,
                "artifact_dir": archive.get("artifact_dir", ""),
                "archive": archive.get("archive", ""),
                "path": archive.get("path", ""),
                "sha256": archive.get("sha256", ""),
            }
        )

    if blockers:
        raise ValueError(
            "GLx rollback package archive validation failed: "
            + "; ".join(blockers)
        )

    glx_rollback_package = dict(glx_rollback_package)
    glx_rollback_package["matchedArchives"] = matched_archives
    return glx_rollback_package


def build_archives(args: argparse.Namespace) -> dict[str, object]:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_docs.py")], check=True)

    meta = channel_metadata(
        args.channel,
        build_number=args.build_number,
        build_date=args.build_date,
        commit=args.commit,
        ref_name=args.ref_name,
    )
    glx_runtime_proof = resolve_glx_runtime_proof(args)
    glx_promotion = promotion_report(args.glx_proof_root, args.glx_rollback_metadata)
    glx_rollback_package = resolve_glx_rollback_package(args, glx_promotion)
    if glx_promotion.get("policyViolation"):
        raise ValueError(
            "GLx promotion policy failed: renderer defaults were promoted "
            "before the promotion gate passed."
        )

    artifact_root = args.artifact_root.resolve()
    if not artifact_root.exists():
        raise FileNotFoundError(f"Artifact root does not exist: {artifact_root}")

    output_dir = args.output_dir.resolve()
    packages_dir = output_dir / "packages"
    temp_dir = args.temp_dir.resolve() / args.channel

    packages_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    archives: list[dict[str, object]] = []

    for artifact_dir in sorted(path for path in artifact_root.iterdir() if path.is_dir()):
        archive_name = package_archive_name(meta, artifact_dir.name)
        archive_base = packages_dir / archive_name[:-4]
        stage_root = temp_dir / archive_name[:-4]

        if stage_root.exists():
            shutil.rmtree(stage_root)
        stage_root.mkdir(parents=True, exist_ok=True)
        copy_tree_contents(artifact_dir, stage_root)
        copy_docs(stage_root)

        archive_path = Path(shutil.make_archive(str(archive_base), "zip", root_dir=stage_root))
        checksum = sha256sum(archive_path)
        archives.append(
            {
                "artifact_dir": artifact_dir.name,
                "archive": archive_path.name,
                "path": archive_path.relative_to(ROOT).as_posix(),
                "sha256": checksum,
            }
        )
        print(archive_path.relative_to(ROOT).as_posix())

    glx_rollback_package = attach_glx_rollback_archives(glx_rollback_package, archives)

    manifest = {
        "project": meta["project_name"],
        "channel": meta["channel"],
        "base_version": meta["base_version"],
        "version": meta["version"],
        "version_label": meta["version_label"],
        "release_tag": meta["release_tag"],
        "release_title": meta["release_title"],
        "build_date": meta["build_date"],
        "commit": meta["commit"],
        "glx_proof_corpus": release_corpus_manifest(),
        "glx_runtime_proof": glx_runtime_proof,
        "glx_promotion": glx_promotion,
        "glx_rollback_package": glx_rollback_package,
        "archives": archives,
    }

    (output_dir / "release-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    checksum_lines = [f"{archive['sha256']}  {Path(archive['path']).name}" for archive in archives]
    (output_dir / "SHA256SUMS.txt").write_text(
        "\n".join(checksum_lines) + ("\n" if checksum_lines else ""),
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main() -> int:
    args = parse_args()
    build_archives(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import io
import os
import shutil
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import release
from scripts import root_archive
from scripts import verify_release_layout


def add_zip_symlink(archive: zipfile.ZipFile, name: str, target: str = "target") -> None:
    info = zipfile.ZipInfo(name)
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    archive.writestr(info, target)


class ReleasePackagingTests(unittest.TestCase):
    def test_release_zip_is_deterministic_and_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "stage"
            source.mkdir()
            (source / "z-last.txt").write_text("last", encoding="utf-8")
            (source / "nested").mkdir()
            (source / "nested" / "first.txt").write_text("first", encoding="utf-8")
            first_archive = root / "first.zip"
            second_archive = root / "second.zip"

            release.write_deterministic_zip(first_archive, source)
            os.utime(source / "z-last.txt", (2_000_000_000, 2_000_000_000))
            os.utime(source / "nested" / "first.txt", (1_000_000_000, 1_000_000_000))
            release.write_deterministic_zip(second_archive, source)

            with zipfile.ZipFile(first_archive) as archive:
                infos = archive.infolist()

            self.assertEqual(first_archive.read_bytes(), second_archive.read_bytes())
            self.assertEqual(
                [info.filename for info in infos],
                ["nested/first.txt", "z-last.txt"],
            )
            self.assertTrue(all(info.date_time == release.DETERMINISTIC_ZIP_DATE for info in infos))

    def test_release_zip_rejects_output_inside_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "stage"
            source.mkdir()
            (source / "file.txt").write_text("content", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "inside source tree"):
                release.write_deterministic_zip(source / "release.zip", source)

    def test_copy_release_artifact_contents_filters_build_garbage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "artifact"
            target = root / "stage"
            source.mkdir()
            (source / "fnquake3.x86_64").write_text("binary", encoding="utf-8")
            (source / "README.txt").write_text("keep", encoding="utf-8")
            (source / "baseq3" / "maps").mkdir(parents=True)
            (source / "baseq3" / "maps" / "q3dm1.azb").write_bytes(b"zones")
            (source / "missionpack" / "vm").mkdir(parents=True)
            (source / "missionpack" / "vm" / "cgame.qvm").write_text(
                "mod data",
                encoding="utf-8",
            )
            (source / "renderer.pdb").write_text("debug", encoding="utf-8")
            (source / ".DS_Store").write_text("finder", encoding="utf-8")
            (source / "meson-info").mkdir()
            (source / "meson-info" / "intro-targets.json").write_text("{}", encoding="utf-8")
            (source / "__pycache__").mkdir()
            (source / "__pycache__" / "junk.pyc").write_bytes(b"\0")
            (source / "FnQuake3.dSYM" / "Contents").mkdir(parents=True)
            (source / "FnQuake3.dSYM" / "Contents" / "Info.plist").write_text("debug", encoding="utf-8")

            skipped = release.copy_release_artifact_contents(source, target)

            kept = sorted(path.relative_to(target).as_posix() for path in target.rglob("*") if path.is_file())

        self.assertEqual(
            kept,
            [
                "README.txt",
                "baseq3/maps/q3dm1.azb",
                "fnquake3.x86_64",
                "missionpack/vm/cgame.qvm",
            ],
        )
        self.assertIn("renderer.pdb", skipped)
        self.assertIn(".DS_Store", skipped)
        self.assertIn("meson-info", skipped)
        self.assertIn("__pycache__", skipped)
        self.assertIn("FnQuake3.dSYM", skipped)

    def test_packaged_docs_are_minimal_player_archive_docs(self) -> None:
        destinations = {destination.as_posix() for _source, destination in release.DEFAULT_DOCS}

        self.assertIn("LICENSE", destinations)
        self.assertIn("README.html", destinations)
        self.assertIn("docs/fnquake3/TECHNICAL.md", destinations)
        self.assertIn("docs/GLX.md", destinations)
        self.assertIn("docs/RTX.md", destinations)
        self.assertNotIn("docs/fnquake3/GLX_PROMOTION.md", destinations)
        self.assertNotIn("docs/fnquake3/GLX_ROLLBACK_PACKAGE.md", destinations)
        self.assertNotIn("docs/fnquake3/GLX_VISUAL_DOSSIER.md", destinations)

    def test_standard_q3a_audio_zone_assets_are_packaged_in_root_archive(self) -> None:
        destinations = {
            destination.as_posix()
            for _source, destination in release.DEFAULT_AUDIO_ZONE_ASSETS
        }
        required_destinations = {
            destination.as_posix()
            for _source, destination in root_archive.DEFAULT_ROOT_ARCHIVE_REQUIRED_ASSETS
        }
        sources = {
            source.relative_to(ROOT).as_posix()
            for source, _destination in release.DEFAULT_AUDIO_ZONE_ASSETS
        }

        self.assertEqual(len(destinations), 35)
        self.assertEqual(len(required_destinations), 37)
        self.assertIn("pkg/baseq3/maps/q3dm1.azb", sources)
        self.assertIn("baseq3/maps/q3dm1.azb", destinations)
        self.assertIn("baseq3/maps/q3dm17.azb", destinations)
        self.assertIn("baseq3/maps/q3tourney6_ctf.azb", destinations)
        self.assertIn("baseq3/maps/pro-q3dm6.azb", destinations)
        self.assertIn("baseq3/sound/fnq3-weapon-sounds.sndshd", required_destinations)
        self.assertIn("missionpack/sound/fnq3-weapon-sounds.sndshd", required_destinations)
        self.assertNotIn("baseq3/maps/test_bigbox.azb", destinations)

        with tempfile.TemporaryDirectory() as tmp:
            archive_path = Path(tmp) / release.ROOT_ARCHIVE_NAME

            release.write_root_archive(archive_path)
            release.validate_root_archive(archive_path)

            with zipfile.ZipFile(archive_path) as archive:
                packaged = set(archive.namelist())

        expected_packaged = {
            destination.as_posix()
            for _source, destination in root_archive.iter_package_assets()
        }
        self.assertTrue(required_destinations.issubset(packaged))
        self.assertEqual(packaged, expected_packaged)
        self.assertIn("baseq3/fnq3-hud.json", packaged)

    def test_meson_root_archive_inputs_include_non_map_pkg_assets(self) -> None:
        meson_build = (ROOT / "meson.build").read_text(encoding="utf-8")

        self.assertIn("'pkg/baseq3/fnq3-hud.json'", meson_build)
        self.assertIn("'pkg/baseq3/sound/fnq3-weapon-sounds.sndshd'", meson_build)
        self.assertIn("'pkg/missionpack/sound/fnq3-weapon-sounds.sndshd'", meson_build)

    def test_root_archive_rejects_unsafe_custom_archive_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_root = root / "pkg"
            package_root.mkdir()
            source = package_root / "asset.txt"
            source.write_text("asset", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "unsafe path component"):
                root_archive.write_root_archive(
                    root / release.ROOT_ARCHIVE_NAME,
                    package_root=package_root,
                    assets=[(source, Path("..") / "asset.txt")],
                )

        unsafe_names = (
            "baseq3/maps/bad:name.azb",
            "baseq3/maps/bad\nname.azb",
            "baseq3/maps/CON.azb",
            "baseq3/maps/trailing-dot.",
        )
        for name in unsafe_names:
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "unsafe|stream|reserved"):
                    root_archive.validate_archive_member_names([name], archive_name="pkg.fnz")

        with self.assertRaisesRegex(ValueError, "duplicate"):
            root_archive.validate_archive_member_names(
                ["baseq3/maps/q3dm1.azb", "baseq3/maps/Q3DM1.azb"],
                archive_name="pkg.fnz",
            )

    def test_root_archive_validation_rejects_zip_symlink_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_path = Path(tmp) / release.ROOT_ARCHIVE_NAME
            with zipfile.ZipFile(archive_path, "w") as archive:
                add_zip_symlink(archive, "baseq3/maps/q3dm1.azb")

            with self.assertRaisesRegex(ValueError, "symbolic link entry"):
                root_archive.validate_root_archive(archive_path)

    def test_root_archive_rejects_custom_sources_outside_package_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_root = root / "pkg"
            package_root.mkdir()
            outside = root / "outside.txt"
            outside.write_text("do not package", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "escapes package root"):
                root_archive.write_root_archive(
                    root / release.ROOT_ARCHIVE_NAME,
                    package_root=package_root,
                    assets=[(outside, Path("baseq3") / "outside.txt")],
                )

    def test_root_archive_packs_the_whole_pkg_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_root = root / "pkg"
            (package_root / "baseq3" / "maps").mkdir(parents=True)
            (package_root / "baseq3" / "maps" / "q3dm1.azb").write_bytes(b"zone")
            (package_root / "baseq3" / "fnq3-hud.json").write_text(
                "{}",
                encoding="utf-8",
            )
            (package_root / "missionpack" / "fnq3-hud.json").parent.mkdir(parents=True)
            (package_root / "missionpack" / "fnq3-hud.json").write_text(
                "{}",
                encoding="utf-8",
            )
            (package_root / "baseq2" / "maps").mkdir(parents=True)
            (package_root / "baseq2" / "maps" / "q2dm1.azb").write_bytes(b"q2 zone")
            archive_path = root / release.ROOT_ARCHIVE_NAME

            root_archive.write_root_archive(archive_path, package_root=package_root)
            with zipfile.ZipFile(archive_path) as archive:
                names = set(archive.namelist())

        self.assertIn("baseq3/maps/q3dm1.azb", names)
        self.assertIn("baseq3/fnq3-hud.json", names)
        self.assertIn("missionpack/fnq3-hud.json", names)
        self.assertIn("baseq2/maps/q2dm1.azb", names)
        self.assertNotIn("pkg/baseq3/fnq3-hud.json", names)

    def test_release_layout_verifier_requires_root_package_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            release.copy_docs(root)
            archive_path = release.build_root_archive(root)

            verify_release_layout.verify_release_layout(root)

            archive_path.unlink()
            with self.assertRaises(FileNotFoundError):
                verify_release_layout.verify_release_layout(root)

    def test_release_layout_verifier_requires_package_docs_for_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            release.build_root_archive(root)

            with self.assertRaisesRegex(FileNotFoundError, "missing required release files"):
                verify_release_layout.verify_release_layout(root)

    def test_release_archive_keeps_game_dirs_at_archive_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stage_root = root / "stage"
            stage_root.mkdir()
            (stage_root / "fnquake3.x64.exe").write_text("binary", encoding="utf-8")
            (stage_root / "missionpack" / "vm").mkdir(parents=True)
            (stage_root / "missionpack" / "vm" / "cgame.qvm").write_text(
                "mod data",
                encoding="utf-8",
            )
            release.copy_docs(stage_root)
            release.build_root_archive(stage_root)
            archive_path = Path(
                shutil.make_archive(str(root / "fnq3-root"), "zip", root_dir=stage_root)
            )

            release.validate_release_archive_contents(archive_path)
            with zipfile.ZipFile(archive_path) as archive:
                names = set(archive.namelist())
                root_archive_bytes = archive.read(release.ROOT_ARCHIVE_NAME)
            with zipfile.ZipFile(io.BytesIO(root_archive_bytes)) as root_archive:
                root_archive_names = set(root_archive.namelist())

        self.assertIn(release.ROOT_ARCHIVE_NAME, names)
        self.assertIn("missionpack/vm/cgame.qvm", names)
        self.assertNotIn("baseq3/maps/q3dm1.azb", names)
        self.assertIn("baseq3/maps/q3dm1.azb", root_archive_names)
        self.assertIn("baseq3/maps/q3dm17.azb", root_archive_names)
        self.assertIn("baseq3/sound/fnq3-weapon-sounds.sndshd", root_archive_names)
        self.assertIn("missionpack/sound/fnq3-weapon-sounds.sndshd", root_archive_names)
        self.assertNotIn("maps/q3dm1.azb", names)

    def test_release_archive_validation_requires_package_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stage_root = root / "stage"
            stage_root.mkdir()
            (stage_root / "fnquake3.x64.exe").write_text("binary", encoding="utf-8")
            release.build_root_archive(stage_root)
            archive_path = Path(
                shutil.make_archive(str(root / "fnq3-missing-docs"), "zip", root_dir=stage_root)
            )

            with self.assertRaisesRegex(ValueError, "missing required release files"):
                release.validate_release_archive_contents(archive_path)

    def test_release_archive_validation_rejects_filtered_build_byproducts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stage_root = root / "stage"
            stage_root.mkdir()
            (stage_root / "fnquake3.x64.exe").write_text("binary", encoding="utf-8")
            (stage_root / "renderer.pdb").write_text("debug", encoding="utf-8")
            release.copy_docs(stage_root)
            release.build_root_archive(stage_root)
            archive_path = Path(
                shutil.make_archive(str(root / "fnq3-with-debug"), "zip", root_dir=stage_root)
            )

            with self.assertRaisesRegex(ValueError, "filtered build byproducts"):
                release.validate_release_archive_contents(archive_path)

    def test_release_archive_validation_rejects_zip_symlink_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive_path = root / "fnq3-symlink.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                add_zip_symlink(archive, "linked.txt")

            with self.assertRaisesRegex(ValueError, "symbolic link entry"):
                release.validate_release_archive_contents(archive_path)

    def test_release_archive_validation_bounds_embedded_root_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive_path = root / "oversized-root.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                for required_name in release.REQUIRED_RELEASE_ARCHIVE_ENTRIES:
                    archive.writestr(required_name, b"root payload" if required_name == release.ROOT_ARCHIVE_NAME else b"doc")

            with mock.patch.object(release, "MAX_EMBEDDED_ROOT_ARCHIVE_SIZE", 4):
                with self.assertRaisesRegex(ValueError, "validation limit"):
                    release.validate_release_archive_contents(archive_path)

    def test_release_layout_verifier_rejects_filtered_build_byproducts_in_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "fnquake3.x64.exe").write_text("binary", encoding="utf-8")
            (root / "renderer.pdb").write_text("debug", encoding="utf-8")
            release.copy_docs(root)
            release.build_root_archive(root)

            with self.assertRaisesRegex(ValueError, "filtered build byproducts"):
                verify_release_layout.verify_release_layout(root)

    def test_release_layout_rejects_renderer_modules_outside_public_three(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "fnquake3.x64.exe").write_text("binary", encoding="utf-8")
            (root / "fnquake3_opengl_x86_64.dll").write_text("old renderer", encoding="utf-8")
            release.copy_docs(root)
            release.build_root_archive(root)

            with self.assertRaisesRegex(ValueError, "only glx, vk, and rtx"):
                verify_release_layout.verify_release_layout(root)

    def test_release_layout_accepts_the_public_renderer_modules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "fnquake3.x64.exe").write_text("binary", encoding="utf-8")
            for renderer in ("glx", "vk", "rtx"):
                (root / f"fnquake3_{renderer}_x86_64.dll").write_text(
                    renderer,
                    encoding="utf-8",
                )
            release.copy_docs(root)
            release.build_root_archive(root)

            verify_release_layout.verify_release_layout(root)

    def test_release_layout_verifier_rejects_symlinks_in_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.txt"
            target.write_text("target", encoding="utf-8")
            link = root / "linked.txt"
            try:
                link.symlink_to(target)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation is unavailable: {exc}")
            release.copy_docs(root)
            release.build_root_archive(root)

            with self.assertRaisesRegex(ValueError, "symbolic link"):
                verify_release_layout.verify_release_layout(root)

    def test_copy_release_artifact_contents_rejects_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "artifact"
            target = root / "stage"
            source.mkdir()
            outside = root / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            link = source / "outside-link.txt"
            try:
                link.symlink_to(outside)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation is unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "symbolic link"):
                release.copy_release_artifact_contents(source, target)

    def test_release_artifact_dirs_rejects_symlink_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_root = root / "artifacts"
            artifact_root.mkdir()
            target = root / "outside-artifact"
            target.mkdir()
            link = artifact_root / "linked-artifact"
            try:
                link.symlink_to(target, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation is unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "symbolic link"):
                release.release_artifact_dirs(artifact_root)

    def test_prepare_stage_root_rejects_artifact_source_descendants_before_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "artifact"
            artifact.mkdir()
            stage = artifact / "manual" / "stage"
            stage.mkdir(parents=True)
            marker = stage / "keep.txt"
            marker.write_text("do not delete", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "inside artifact source"):
                release.prepare_stage_root(stage, artifact)

            self.assertTrue(marker.exists())

    def test_prepare_stage_root_rejects_artifact_source_ancestors_before_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp) / "stage"
            artifact = stage / "artifact"
            artifact.mkdir(parents=True)
            marker = artifact / "keep.txt"
            marker.write_text("do not delete", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "contain artifact source"):
                release.prepare_stage_root(stage, artifact)

            self.assertTrue(marker.exists())

    def test_copy_release_artifact_contents_rejects_target_inside_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "artifact"
            source.mkdir()
            (source / "fnquake3.x64.exe").write_text("binary", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "inside artifact source"):
                release.copy_release_artifact_contents(source, source / "stage")

    def test_copy_release_artifact_contents_rejects_target_containing_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "stage"
            source = target / "artifact"
            source.mkdir(parents=True)
            (source / "fnquake3.x64.exe").write_text("binary", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "contain artifact source"):
                release.copy_release_artifact_contents(source, target)

    def test_release_artifact_dirs_rejects_empty_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            with self.assertRaisesRegex(ValueError, "does not contain any artifact directories"):
                release.release_artifact_dirs(root)

    def test_release_cli_parser_rejects_negative_build_numbers(self) -> None:
        with self.assertRaisesRegex(Exception, "non-negative"):
            release.non_negative_int("-1")

    def test_build_archives_supports_output_dir_outside_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_root = root / "artifacts"
            artifact_dir = artifact_root / "windows-x86_64"
            artifact_dir.mkdir(parents=True)
            (artifact_dir / "fnquake3.x64.exe").write_text("binary", encoding="utf-8")
            output_dir = root / "external-output"
            stale_archive = output_dir / "packages" / "stale-release.zip"
            stale_archive.parent.mkdir(parents=True)
            stale_archive.write_bytes(b"stale")

            manifest = release.build_archives(
                argparse.Namespace(
                    channel="manual",
                    artifact_root=artifact_root,
                    output_dir=output_dir,
                    temp_dir=root / "stage",
                    build_date="2026-06-20",
                    build_number=7,
                    commit="abcdef1234567890",
                    ref_name=None,
                    glx_proof_root=None,
                    glx_rollback_metadata=None,
                )
            )

            archive_path = Path(str(manifest["archives"][0]["path"]))
            self.assertTrue(archive_path.is_absolute())
            self.assertTrue(archive_path.is_file())
            self.assertFalse(stale_archive.exists())
            self.assertTrue((output_dir / "release-manifest.json").is_file())
            self.assertTrue((output_dir / "SHA256SUMS.txt").is_file())


if __name__ == "__main__":
    unittest.main()

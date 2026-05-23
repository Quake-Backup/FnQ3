from __future__ import annotations

import shutil
import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import release
from scripts import root_archive
from scripts import verify_release_layout


class ReleasePackagingTests(unittest.TestCase):
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
                packaged = sorted(archive.namelist())

        self.assertEqual(packaged, sorted(required_destinations))

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

            archive_path = release.build_root_archive(root)

            verify_release_layout.verify_release_layout(root)

            archive_path.unlink()
            with self.assertRaises(FileNotFoundError):
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


if __name__ == "__main__":
    unittest.main()

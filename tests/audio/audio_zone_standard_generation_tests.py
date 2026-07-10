from __future__ import annotations

import importlib.util
import contextlib
import io
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "generate_standard_audio_zones.py"

spec = importlib.util.spec_from_file_location("generate_standard_audio_zones", SCRIPT_PATH)
assert spec is not None
generate_standard_audio_zones = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = generate_standard_audio_zones
assert spec.loader is not None
spec.loader.exec_module(generate_standard_audio_zones)


def write_pk3(path: Path, entries: dict[str, bytes | str]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in entries.items():
            data = payload.encode("utf-8") if isinstance(payload, str) else payload
            archive.writestr(name, data)


class StandardAudioZoneGenerationTests(unittest.TestCase):
    def test_discovers_arena_maps_and_extracts_latest_bsp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pak_root = root / "baseq3"
            pak_root.mkdir()
            write_pk3(
                pak_root / "pak0.pk3",
                {
                    "scripts/arenas.txt": 'map "q3dm1"\nmap "q3dm2"\n',
                    "maps/q3dm1.bsp": b"old q3dm1",
                    "maps/q3dm2.bsp": b"q3dm2",
                },
            )
            write_pk3(
                pak_root / "pak2.pk3",
                {
                    "scripts/q3bonus.arena": 'map "q3tourney6_ctf"\n',
                    "maps/q3dm1.bsp": b"new q3dm1",
                    "maps/q3tourney6_ctf.bsp": b"ctf",
                },
            )
            write_pk3(
                pak_root / "local-custom.pk3",
                {
                    "scripts/custom.arena": 'map "not-standard"\n',
                    "maps/not-standard.bsp": b"custom",
                },
            )

            paks = generate_standard_audio_zones.discover_official_paks(pak_root)
            map_names = generate_standard_audio_zones.discover_standard_map_names(paks)
            source_root = root / "scratch" / "baseq3"
            generate_standard_audio_zones.extract_standard_bsp_files(
                paks,
                map_names,
                source_root,
            )

            self.assertEqual([path.name for path in paks], ["pak0.pk3", "pak2.pk3"])
            self.assertEqual(map_names, ("q3dm1", "q3dm2", "q3tourney6_ctf"))
            self.assertEqual((source_root / "maps" / "q3dm1.bsp").read_bytes(), b"new q3dm1")
            self.assertEqual((source_root / "maps" / "q3dm2.bsp").read_bytes(), b"q3dm2")
            self.assertEqual((source_root / "maps" / "q3tourney6_ctf.bsp").read_bytes(), b"ctf")
            self.assertFalse((source_root / "maps" / "not-standard.bsp").exists())

    def test_rejects_unsafe_arena_map_names_before_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pak_root = root / "baseq3"
            pak_root.mkdir()
            write_pk3(
                pak_root / "pak0.pk3",
                {
                    "scripts/arenas.txt": 'map "../outside"\n',
                    "maps/../outside.bsp": b"outside",
                },
            )

            paks = generate_standard_audio_zones.discover_official_paks(pak_root)
            with self.assertRaisesRegex(ValueError, "unsafe arena map name"):
                generate_standard_audio_zones.discover_standard_map_names(paks)

            source_root = root / "scratch" / "baseq3"
            with self.assertRaisesRegex(ValueError, "unsafe arena map name"):
                generate_standard_audio_zones.extract_standard_bsp_files(
                    paks,
                    ("../outside",),
                    source_root,
                )
            for name in ("CON", "COM1.txt", "q3dm1."):
                with self.subTest(name=name):
                    with self.assertRaisesRegex(ValueError, "unsafe arena map name"):
                        generate_standard_audio_zones.validate_arena_map_name(name)

    def test_rejects_case_ambiguous_pk3_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pak_root = root / "baseq3"
            pak_root.mkdir()
            write_pk3(
                pak_root / "pak0.pk3",
                {
                    "scripts/arenas.txt": 'map "q3dm1"\n',
                    "maps/q3dm1.bsp": b"lower",
                    "MAPS/Q3DM1.BSP": b"upper",
                },
            )

            paks = generate_standard_audio_zones.discover_official_paks(pak_root)
            with self.assertRaisesRegex(ValueError, "case-ambiguous"):
                generate_standard_audio_zones.discover_standard_map_names(paks)
            with self.assertRaisesRegex(ValueError, "case-ambiguous"):
                generate_standard_audio_zones.extract_standard_bsp_files(
                    paks,
                    ("q3dm1",),
                    root / "scratch" / "baseq3",
                )

    def test_rejects_duplicate_pk3_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pak = root / "pak0.pk3"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(pak, "w") as archive:
                    archive.writestr("scripts/arenas.txt", 'map "q3dm1"\n')
                    archive.writestr("scripts/arenas.txt", 'map "q3dm2"\n')

            with zipfile.ZipFile(pak) as archive:
                with self.assertRaisesRegex(ValueError, "duplicate entries"):
                    generate_standard_audio_zones.archive_entry_map(archive)

    def test_work_root_must_not_overlap_retail_pak_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pak_root = root / "baseq3"
            pak_root.mkdir()

            with self.assertRaisesRegex(ValueError, "must not overlap"):
                generate_standard_audio_zones.validate_generation_roots(
                    pak_root,
                    root,
                )

            with self.assertRaisesRegex(ValueError, "must not overlap"):
                generate_standard_audio_zones.validate_generation_roots(
                    pak_root,
                    pak_root / "scratch",
                )
            with self.assertRaisesRegex(ValueError, "output-root"):
                generate_standard_audio_zones.validate_generation_roots(
                    pak_root,
                    root / "scratch",
                    pak_root / "maps",
                )

            generate_standard_audio_zones.validate_generation_roots(
                pak_root,
                root / "scratch",
                root / "pkg" / "baseq3",
            )

    def test_parse_args_caps_audit_samples_to_compiler_limit(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                generate_standard_audio_zones.parse_args(
                    [
                        "baseq3",
                        "--samples",
                        str(generate_standard_audio_zones.MAX_AUDIT_SAMPLES + 1),
                    ]
                )

        args = generate_standard_audio_zones.parse_args(
            ["baseq3", "--samples", str(generate_standard_audio_zones.MAX_AUDIT_SAMPLES)]
        )
        self.assertEqual(args.samples, generate_standard_audio_zones.MAX_AUDIT_SAMPLES)


if __name__ == "__main__":
    unittest.main()

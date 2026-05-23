from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

from release import validate_release_archive_contents
from root_archive import (
    DEFAULT_AUDIO_ZONE_ASSETS,
    DEFAULT_WEAPON_SOUND_SHADER_ASSETS,
    ROOT_ARCHIVE_NAME,
    validate_root_archive,
)


def verify_release_layout(root: Path) -> None:
    if root.is_file() and root.suffix.lower() == ".fnz":
        validate_root_archive(root)
        return

    if root.is_file() and root.suffix.lower() == ".zip":
        validate_release_archive_contents(root)
        return

    root_archive = root / ROOT_ARCHIVE_NAME
    if not root_archive.is_file():
        raise FileNotFoundError(
            f"{root} is missing required root package archive: {ROOT_ARCHIVE_NAME}"
        )
    validate_root_archive(root_archive)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify that a FnQuake3 install/release root has required data layout.",
    )
    parser.add_argument(
        "root",
        type=Path,
        help="FnQuake3 install or release root, for example a CI bin directory.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    root = args.root.expanduser().resolve()
    try:
        verify_release_layout(root)
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        print(f"verify_release_layout.py: {exc}", file=sys.stderr)
        return 1

    if root.is_file():
        archive_kind = "root package archive" if root.suffix.lower() == ".fnz" else "release archive"
        print(
            f"{archive_kind} layout ok: "
            f"{len(DEFAULT_AUDIO_ZONE_ASSETS)} audio-zone sidecars under "
            f"{ROOT_ARCHIVE_NAME}/baseq3/maps and "
            f"{len(DEFAULT_WEAPON_SOUND_SHADER_ASSETS)} sound shaders under "
            f"{ROOT_ARCHIVE_NAME}/<game>/sound"
        )
    else:
        print(
            "release layout ok: "
            f"{ROOT_ARCHIVE_NAME} contains {len(DEFAULT_AUDIO_ZONE_ASSETS)} "
            "audio-zone sidecars under baseq3/maps and "
            f"{len(DEFAULT_WEAPON_SOUND_SHADER_ASSETS)} sound shaders under <game>/sound"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

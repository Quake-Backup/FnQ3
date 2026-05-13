from __future__ import annotations

import argparse
import itertools
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


GLIBC_VERSION_RE = re.compile(r"\bGLIBC_(\d+(?:\.\d+)*)\b")


@dataclass(frozen=True)
class ElfGlibcReport:
    path: Path
    versions: tuple[str, ...]

    @property
    def max_version(self) -> str | None:
        if not self.versions:
            return None
        return max(self.versions, key=parse_version)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail when ELF files require a newer glibc than the release baseline."
    )
    parser.add_argument("paths", nargs="+", type=Path, help="ELF files or directories to scan")
    parser.add_argument(
        "--max-glibc",
        required=True,
        help="Highest allowed GLIBC symbol version, for example 2.31",
    )
    parser.add_argument(
        "--require-elf",
        action="store_true",
        help="Fail if no ELF files are found under the supplied paths.",
    )
    return parser.parse_args()


def parse_version(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def version_greater(left: str, right: str) -> bool:
    left_parts = parse_version(left)
    right_parts = parse_version(right)
    width = max(len(left_parts), len(right_parts))
    padded_left = tuple(itertools.islice(itertools.chain(left_parts, itertools.repeat(0)), width))
    padded_right = tuple(itertools.islice(itertools.chain(right_parts, itertools.repeat(0)), width))
    return padded_left > padded_right


def is_elf(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(4) == b"\x7fELF"
    except OSError:
        return False


def candidate_files(paths: list[Path]) -> list[Path]:
    candidates: list[Path] = []
    for path in paths:
        if path.is_dir():
            candidates.extend(item for item in path.rglob("*") if item.is_file())
        elif path.is_file():
            candidates.append(path)
    return sorted(path for path in candidates if is_elf(path))


def read_glibc_versions(path: Path) -> tuple[str, ...]:
    result = subprocess.run(
        ["readelf", "--version-info", str(path)],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "readelf failed"
        raise RuntimeError(f"{path}: {detail}")

    versions = {
        match.group(1)
        for match in GLIBC_VERSION_RE.finditer(result.stdout + "\n" + result.stderr)
    }
    return tuple(sorted(versions, key=parse_version))


def scan(paths: list[Path]) -> list[ElfGlibcReport]:
    return [
        ElfGlibcReport(path=path, versions=read_glibc_versions(path))
        for path in candidate_files(paths)
    ]


def main() -> int:
    args = parse_args()
    max_allowed = args.max_glibc
    if max_allowed.startswith("GLIBC_"):
        max_allowed = max_allowed[len("GLIBC_") :]
    try:
        parse_version(max_allowed)
    except ValueError:
        print(f"Invalid --max-glibc value: {args.max_glibc}", file=sys.stderr)
        return 2

    try:
        reports = scan(args.paths)
    except (OSError, RuntimeError) as exc:
        print(exc, file=sys.stderr)
        return 1

    if args.require_elf and not reports:
        print("No ELF files found to scan.", file=sys.stderr)
        return 1

    violations = [
        report
        for report in reports
        if report.max_version is not None and version_greater(report.max_version, max_allowed)
    ]
    if violations:
        print(f"GLIBC baseline violations; maximum allowed is GLIBC_{max_allowed}:", file=sys.stderr)
        for report in violations:
            print(f"  {report.path}: requires GLIBC_{report.max_version}", file=sys.stderr)
        return 1

    highest = max(
        (report.max_version for report in reports if report.max_version is not None),
        key=parse_version,
        default=None,
    )
    if highest is None:
        print(f"Checked {len(reports)} ELF file(s); no GLIBC version requirements found.")
    else:
        print(
            f"Checked {len(reports)} ELF file(s); highest requirement is "
            f"GLIBC_{highest}, within GLIBC_{max_allowed}."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Fail a Windows release build that depends on a DLL it does not ship.

Nothing in the release layout installs runtime libraries: `meson install` stages
the engine binaries, the renderer modules, the data pack, and the docs. Anything
else a produced PE imports has to already be present on the player's machine, so
the only safe imports are Windows' own system libraries.

That is not a theoretical concern. The bundled curl leaves most of its optional
features on `auto`, and on an MSYS2 runner `libzstd.pc` is always installed --
it is a dependency of the mingw gcc package. curl found it, linked it, and the
published client died on launch with "libzstd.dll was not found". A missing
import is invisible to every build and packaging step and only shows up when a
player double-clicks the executable, so it is worth an explicit gate.

The import table is parsed directly rather than shelling out to dumpbin or
objdump, because the two Windows lanes run under different toolchains (MSVC and
MSYS2/MinGW) and neither tool is guaranteed on both.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path
from typing import Iterable, Sequence


# Libraries that ship with Windows itself, so importing them needs nothing from
# the release archive. Matching is case-insensitive on the full file name.
SYSTEM_DLLS = frozenset(
    name.lower()
    for name in (
        "advapi32.dll",
        "avrt.dll",
        "bcrypt.dll",
        "cfgmgr32.dll",
        "comctl32.dll",
        "comdlg32.dll",
        "crypt32.dll",
        "d3d11.dll",
        "d3d12.dll",
        "dbghelp.dll",
        "dinput8.dll",
        "dsound.dll",
        "dwmapi.dll",
        "dxgi.dll",
        "gdi32.dll",
        "hid.dll",
        "imm32.dll",
        "iphlpapi.dll",
        "kernel32.dll",
        "mswsock.dll",
        "normaliz.dll",
        "ntdll.dll",
        "ole32.dll",
        "oleaut32.dll",
        "opengl32.dll",
        "psapi.dll",
        "rpcrt4.dll",
        "secur32.dll",
        "setupapi.dll",
        "shell32.dll",
        "shlwapi.dll",
        "user32.dll",
        "userenv.dll",
        "uuid.dll",
        "version.dll",
        "wldap32.dll",
        "winmm.dll",
        "ws2_32.dll",
        "wsock32.dll",
        "xinput1_4.dll",
    )
)

# Prefixes covering the Universal CRT and the API-set forwarders every modern
# Windows carries. `ucrtbase.dll` and the `api-ms-win-*` set are part of the OS.
SYSTEM_DLL_PREFIXES = ("api-ms-win-", "ext-ms-win-")
SYSTEM_DLL_NAMES_UCRT = frozenset({"ucrtbase.dll", "ucrtbased.dll"})

PE_SUFFIXES = frozenset({".exe", ".dll"})


class PeFormatError(ValueError):
    """The file is not a PE image this reader understands."""


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _read_sections(data: bytes, section_table: int, count: int) -> list[tuple[int, int, int, int]]:
    """Return (virtual_address, virtual_size, raw_pointer, raw_size) per section."""
    sections = []
    for index in range(count):
        entry = section_table + index * 40
        if entry + 40 > len(data):
            raise PeFormatError("section table runs past end of file")
        virtual_size = _u32(data, entry + 8)
        virtual_address = _u32(data, entry + 12)
        raw_size = _u32(data, entry + 16)
        raw_pointer = _u32(data, entry + 20)
        sections.append((virtual_address, virtual_size, raw_pointer, raw_size))
    return sections


def _rva_to_offset(sections: Sequence[tuple[int, int, int, int]], rva: int) -> int | None:
    for virtual_address, virtual_size, raw_pointer, raw_size in sections:
        # A section's mapped size can exceed its raw size (bss-like tails); only
        # the raw part is readable from the file.
        span = max(virtual_size, raw_size)
        if virtual_address <= rva < virtual_address + span:
            offset = rva - virtual_address + raw_pointer
            if offset < raw_pointer + raw_size:
                return offset
            return None
    return None


def _read_cstring(data: bytes, offset: int, limit: int = 512) -> str:
    end = data.find(b"\x00", offset, offset + limit)
    if end == -1:
        raise PeFormatError("unterminated import name")
    return data[offset:end].decode("ascii", errors="replace")


def imported_dlls(path: Path) -> set[str]:
    """Return the DLL names in a PE image's import and delay-import tables."""
    data = path.read_bytes()
    if len(data) < 64 or data[:2] != b"MZ":
        raise PeFormatError(f"{path} is not a PE image")

    pe_offset = _u32(data, 0x3C)
    if pe_offset + 24 > len(data) or data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise PeFormatError(f"{path} has no PE signature")

    coff = pe_offset + 4
    section_count = _u16(data, coff + 2)
    optional_size = _u16(data, coff + 16)
    optional = coff + 20
    if optional + optional_size > len(data):
        raise PeFormatError(f"{path} optional header runs past end of file")

    magic = _u16(data, optional)
    if magic == 0x10B:  # PE32
        directories = optional + 96
    elif magic == 0x20B:  # PE32+
        directories = optional + 112
    else:
        raise PeFormatError(f"{path} has unknown optional header magic 0x{magic:x}")

    directory_count = _u32(data, directories - 4)
    sections = _read_sections(data, optional + optional_size, section_count)

    names: set[str] = set()
    # Directory 1 is the import table (20-byte descriptors, DLL name at +12).
    # Directory 13 is the delay-load table (32-byte descriptors, name at +4).
    for index, entry_size, name_field in ((1, 20, 12), (13, 32, 4)):
        if index >= directory_count:
            continue
        table_rva = _u32(data, directories + index * 8)
        if table_rva == 0:
            continue
        cursor = _rva_to_offset(sections, table_rva)
        if cursor is None:
            continue
        while cursor + entry_size <= len(data):
            descriptor = data[cursor : cursor + entry_size]
            if descriptor == b"\x00" * entry_size:
                break
            name_rva = _u32(data, cursor + name_field)
            if name_rva:
                name_offset = _rva_to_offset(sections, name_rva)
                if name_offset is not None:
                    names.add(_read_cstring(data, name_offset))
            cursor += entry_size

    return names


def is_system_dll(name: str) -> bool:
    lowered = name.lower()
    if lowered in SYSTEM_DLLS or lowered in SYSTEM_DLL_NAMES_UCRT:
        return True
    return lowered.startswith(SYSTEM_DLL_PREFIXES)


def collect_pe_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in PE_SUFFIXES
    )


def check_root(root: Path, extra_allowed: Iterable[str]) -> list[str]:
    """Return a problem report, empty when every import is satisfiable."""
    shipped = {path.name.lower() for path in collect_pe_files(root)}
    allowed = {name.lower() for name in extra_allowed}
    problems: list[str] = []

    files = collect_pe_files(root)
    if not files:
        return [f"{root}: no .exe or .dll files found to check"]

    for path in files:
        try:
            imports = imported_dlls(path)
        except PeFormatError as exc:
            problems.append(f"{path}: {exc}")
            continue
        missing = sorted(
            name
            for name in imports
            if not is_system_dll(name)
            and name.lower() not in shipped
            and name.lower() not in allowed
        )
        if missing:
            problems.append(
                f"{path.relative_to(root) if path != root else path.name}"
                f" imports unshipped libraries: {', '.join(missing)}"
            )

    return problems


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify that every Windows binary in a staged release only imports "
            "OS libraries or other files in the same package."
        ),
    )
    parser.add_argument("root", type=Path, help="staged release directory, or a single PE file")
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        metavar="NAME.DLL",
        help="additional DLL name to accept; repeatable",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    root = args.root.expanduser().resolve()
    if not root.exists():
        print(f"check_windows_dll_deps.py: {root} does not exist", file=sys.stderr)
        return 1

    problems = check_root(root, args.allow)
    if problems:
        print("check_windows_dll_deps.py: unsatisfiable runtime dependencies", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(
            "\nThe release ships no runtime libraries. Either link the dependency "
            "statically (see curl_fallback_defaults in meson.build) or drop it.",
            file=sys.stderr,
        )
        return 1

    checked = len(collect_pe_files(root))
    print(f"windows dependency check ok: {checked} binaries import only OS libraries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

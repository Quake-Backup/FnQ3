from __future__ import annotations

import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


BSP_HEADER_LUMPS = 17
BSP_HEADER_SIZE = 8 + BSP_HEADER_LUMPS * 8
BSP_LUMP_SHADERS = 1
BSP_LUMP_LEAFS = 4
BSP_LUMP_LEAF_SURFACES = 5
BSP_LUMP_SURFACES = 13


def i32(value: int) -> bytes:
    return struct.pack("<i", value)


def fixed_qpath(name: str) -> bytes:
    encoded = name.encode("ascii")
    if len(encoded) >= 64:
        raise ValueError("qpath is too long for the test BSP")
    return encoded + b"\0" * (64 - len(encoded))


def build_minimal_bsp(shader_name: str) -> bytes:
    shader = fixed_qpath(shader_name) + i32(0) + i32(0)
    leaf = b"".join(
        [
            i32(0),  # cluster
            i32(0),  # area
            i32(0),
            i32(0),
            i32(0),
            i32(128),
            i32(128),
            i32(128),
            i32(0),  # firstLeafSurface
            i32(1),  # numLeafSurfaces
            i32(0),  # firstLeafBrush
            i32(0),  # numLeafBrushes
        ]
    )
    leaf_surfaces = i32(0)
    surface = bytearray(104)
    surface[0:4] = i32(0)  # shaderNum
    surface[8:12] = i32(1)  # surfaceType

    lump_data: dict[int, bytes] = {
        BSP_LUMP_SHADERS: shader,
        BSP_LUMP_LEAFS: leaf,
        BSP_LUMP_LEAF_SURFACES: leaf_surfaces,
        BSP_LUMP_SURFACES: bytes(surface),
    }
    lumps: list[tuple[int, int]] = []
    body = bytearray()
    offset = BSP_HEADER_SIZE
    for index in range(BSP_HEADER_LUMPS):
        payload = lump_data.get(index, b"")
        lumps.append((offset, len(payload)))
        body.extend(payload)
        offset += len(payload)

    header = bytearray()
    header.extend(b"IBSP")
    header.extend(i32(46))
    for lump_offset, lump_length in lumps:
        header.extend(i32(lump_offset))
        header.extend(i32(lump_length))
    return bytes(header + body)


class AudioZoneMaterialMapTests(unittest.TestCase):
    def test_material_map_overrides_shader_classification(self) -> None:
        if len(sys.argv) < 2:
            self.fail("missing fnq3-audiozonesc path")
        tool = Path(sys.argv[1])

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bsp = root / "material_map.bsp"
            bsp.write_bytes(build_minimal_bsp("textures/custom/mystery_panel"))
            material_map = root / "audio-materials.txt"
            material_map.write_text(
                "textures/custom/* metal preset hallway flag outdoor weight 8\n",
                encoding="utf-8",
            )
            output = root / "material_map.azb"

            generated = subprocess.run(
                [
                    str(tool),
                    "--from-bsp",
                    "--material-map",
                    str(material_map),
                    "-o",
                    str(output),
                    str(bsp),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertIn("using 1 material rule", generated.stdout)

            dumped = subprocess.run(
                [str(tool), "--dump", str(output)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            self.assertEqual(dumped.returncode, 0, dumped.stderr)
            self.assertIn("audiozones version 3", dumped.stdout)
            self.assertIn("preset hallway", dumped.stdout)
            self.assertIn("material metal", dumped.stdout)
            self.assertIn("flags 3", dumped.stdout)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])

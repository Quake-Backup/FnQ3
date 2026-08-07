from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DemoMessageBoundsSourceTests(unittest.TestCase):
    def test_client_rejects_invalid_lengths_before_reading_demo_payload(self) -> None:
        source = (ROOT / "code" / "client" / "cl_main.cpp").read_text(
            encoding="utf-8"
        )
        start = source.index("void CL_ReadDemoMessage( void )")
        end = source.index("\n/*\n====================", start)
        reader = source[start:end]

        endian_swap = reader.index("buf.cursize = LittleLong( buf.cursize );")
        terminator = reader.index("if ( buf.cursize == -1 )")
        bounds_check = reader.index(
            "if ( buf.cursize < 0 || buf.cursize > buf.maxsize )"
        )
        payload_read = reader.index(
            "FileRead( clc.demofile, buf.data, buf.cursize )"
        )

        self.assertLess(endian_swap, terminator)
        self.assertLess(terminator, bounds_check)
        self.assertLess(bounds_check, payload_read)

    def test_client_and_server_demo_readers_enforce_the_same_length_bounds(self) -> None:
        client = (ROOT / "code" / "client" / "cl_main.cpp").read_text(
            encoding="utf-8"
        )
        server = (ROOT / "code" / "server" / "sv_demo_play.cpp").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "buf.cursize < 0 || buf.cursize > buf.maxsize",
            client,
        )
        self.assertIn("length < 0 || length > bufSize", server)


if __name__ == "__main__":
    unittest.main()

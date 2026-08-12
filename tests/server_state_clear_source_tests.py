from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ServerStateClearSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "code" / "server" / "sv_init.cpp").read_text(
            encoding="utf-8"
        )
        cls.client_source = (
            ROOT / "code" / "server" / "sv_client.cpp"
        ).read_text(encoding="utf-8")

    def function(self, signature: str, next_signature: str) -> str:
        start = self.source.index(signature)
        end = self.source.index(next_signature, start + len(signature))
        return self.source[start:end]

    def test_per_map_state_is_cleared_in_place(self) -> None:
        clear_server = self.function("void SV_ClearServer", "void SV_SpawnServer")

        self.assertEqual(
            clear_server.count("Com_Memset( &sv, 0, sizeof( sv ) );"), 2
        )
        self.assertNotIn("sv = {};", clear_server)

    def test_persistent_server_state_is_cleared_in_place(self) -> None:
        shutdown = self.source[self.source.index("void SV_Shutdown") :]

        self.assertIn("Com_Memset( &svs, 0, sizeof( svs ) );", shutdown)
        self.assertNotIn("svs = {};", shutdown)

    def test_client_slot_state_is_cleared_in_place(self) -> None:
        self.assertIn("Com_Memset( &client, 0, sizeof( client ) );", self.source)
        self.assertIn(
            "Com_Memset( &oldClients[slot.index], 0, "
            "sizeof( oldClients[slot.index] ) );",
            self.source,
        )
        self.assertIn(
            "Com_Memset( newcl, 0, sizeof( *newcl ) );", self.client_source
        )


if __name__ == "__main__":
    unittest.main()

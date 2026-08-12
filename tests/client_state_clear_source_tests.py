from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ClientStateClearSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "code" / "client" / "cl_main.cpp").read_text(
            encoding="utf-8"
        )

    def test_large_client_state_is_cleared_in_place(self) -> None:
        start = self.source.index("void CL_ClearState( void )")
        end = self.source.index("\n/*", start)
        clear_state = self.source[start:end]

        self.assertIn("Com_Memset( &cl, 0, sizeof( cl ) );", clear_state)
        self.assertNotIn("cl = {};", clear_state)

    def test_connection_state_is_cleared_in_place(self) -> None:
        start = self.source.index("qboolean CL_Disconnect")
        end = self.source.index("void CL_ForwardCommandToServer", start)
        disconnect = self.source[start:end]

        self.assertIn("Com_Memset( &clc, 0, sizeof( clc ) );", disconnect)
        self.assertNotIn("clc = {};", disconnect)

    def test_static_client_state_is_cleared_in_place(self) -> None:
        start = self.source.index("void CL_Shutdown")
        end = self.source.index("static void CL_SetServerInfo", start)
        shutdown = self.source[start:end]

        self.assertIn("Com_Memset( &cls, 0, sizeof( cls ) );", shutdown)
        self.assertNotIn("cls = {};", shutdown)

    def test_server_address_hash_uses_element_sized_fill(self) -> None:
        start = self.source.index("static void hash_reset")
        end = self.source.index("static hash_chain_t *hash_find", start)
        reset = self.source[start:end]

        self.assertIn("hash_list.fill( {} );", reset)
        self.assertNotIn("hash_list = {};", reset)


if __name__ == "__main__":
    unittest.main()

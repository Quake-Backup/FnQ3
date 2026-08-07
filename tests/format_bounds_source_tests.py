from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "code" / "qcommon" / "q_shared.c"


def function_body(source: str, signature: str) -> str:
    match = re.search(signature, source)
    if not match:
        raise AssertionError(f"missing function matching {signature}")

    start = source.find("{", match.end())
    if start < 0:
        raise AssertionError(f"missing function body matching {signature}")

    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"unterminated function body matching {signature}")


class FormatBoundsSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE.read_text(encoding="utf-8")

    def test_com_sprintf_formats_with_the_bounded_wrapper(self) -> None:
        body = function_body(self.source, r"\bint\s+QDECL\s+Com_sprintf\s*\(")

        self.assertIn("Q_vsnprintf( bigbuffer, sizeof( bigbuffer ), fmt, argptr )", body)
        self.assertNotIn("vsprintf(", body)

    def test_va_formats_with_the_bounded_wrapper(self) -> None:
        body = function_body(self.source, r"\bconst\s+char\s*\*\s*QDECL\s+va\s*\(")

        self.assertIn("Q_vsnprintf( buf, sizeof( string[0] ), format, argptr )", body)
        self.assertNotIn("vsprintf(", body)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: stringify_shader.py <input.glsl> <output.c>", file=sys.stderr)
        return 1

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    symbol = f"fallbackShader_{input_path.stem}"

    with input_path.open("r", encoding="utf-8") as src, output_path.open(
        "w", encoding="utf-8", newline="\n"
    ) as dst:
        dst.write(f"const char *{symbol} =\n")
        for line in src:
            escaped = line.rstrip().replace("\\", "\\\\").replace('"', '\\"')
            dst.write(f'"{escaped}\\n"\n')
        dst.write(";\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

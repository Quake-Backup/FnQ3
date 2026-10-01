"""Compile the production descriptor binder with a mock Vulkan command sink."""

from pathlib import Path
import sys


source = Path(sys.argv[1]).read_text(encoding="utf-8")
signature = "void vk_bind_descriptor_sets( void )"
start = source.index(signature)
opening = source.index("{", start)
depth = 1
end = opening + 1
while depth:
    if source[end] == "{":
        depth += 1
    elif source[end] == "}":
        depth -= 1
    end += 1

Path(sys.argv[2]).write_text(
    "/* Generated from vk.c; do not edit. */\n" + source[start:end] + "\n",
    encoding="utf-8",
)

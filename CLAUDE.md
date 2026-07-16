# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

FnQ3 (FnQuake3) is a modernized Quake III Arena source port. Its lineage is: id Software Q3A → ioquake3 → Quake3e → FnQ3. The top constraint is **retail Quake III Arena compatibility**: demo playback, network protocol, filesystem/pak search order, and VM ABI are all compatibility surfaces and must not regress silently.

## Build

Meson is the preferred build system. The legacy Makefile remains functional but new local work should use Meson.

```sh
meson setup meson/build
meson compile -C meson/build
meson test -C meson/build
```

Useful Meson options:
- `-Drenderers=glx,vk,rtx` — which of the three renderer modules to build
- `-Drenderer-default=glx` — default `cl_renderer` value
- `-Drenderer-dlopen=false -Drenderer-default=vk` — link one renderer statically for testing
- `-Daudio-tests=true` / `-Dglx-tests=true` — include C++ test binaries
- `--wrap-mode=nofallback` — force system libraries only; `--wrap-mode=forcefallback` — force subproject fallbacks

Makefile equivalents for quick Linux builds:
```sh
make                                          # full default build
make BUILD_SERVER=0 USE_GLX=1                 # client + GLx module, no dedicated server
make BUILD_SERVER=0 USE_RENDERER_DLOPEN=0 RENDERER_DEFAULT=vk  # static Vulkan client
```

Output binaries: `fnquake3[.x86_64]` (client), `fnquake3.ded[.x86_64]` (server), `fnquake3_{glx,vk,rtx}_x86_64` (renderer modules).

## Tests

Most tests are Python source-contract scripts that grep/parse source files — no game assets or GL context needed. Run a single test:

```sh
python3 tests/shadow_manager_source_tests.py
python3 tests/version_metadata_tests.py
```

Run all Python tests at once:

```sh
python3 -m unittest discover -s tests -p "*_tests.py"
```

The GLx logic tests are C++ and require a Meson build:

```sh
meson compile -C meson/build fnq3_glx_logic_tests
meson test -C meson/build fnq3_glx_logic fnq3_glx_header_boundary --print-errorlogs
```

Audio C++ tests are built with `-Daudio-tests=true` and run via `meson test`.

## Architecture

### Renderer system

Three backends coexist as runtime-selectable dynamic modules, chosen via `cl_renderer`:

- `glx` — default OpenGL-lineage renderer. GLx-specific code lives in `code/rendererglx/`; `code/renderer/*.c` is its compatibility implementation base, not a separately selectable module.
- `vk` — Vulkan raster backend. Lives in `code/renderervk/`.
- `rtx` — Vulkan ray-tracing backend. Lives in `code/rendererrtx/`.

Shared renderer types and image loaders are in `code/renderercommon/`. All renderers implement the same `refexport_t` / `refimport_t` ABI (`REF_API_VERSION 8`, single `GetRefAPI` export).

**GLx product tiers** (selected once at GL init, used throughout hot paths):
- `GL12` — fixed-function floor, no GLSL, conservative feature surface
- `GL2X` — first programmable tier, GLSL material execution
- `GL3X` — first performance tier: FBO, UBO, timer queries, sync-aware streaming
- `GL41` — macOS ceiling: modern path without GL4.3+ requirements
- `GL46` — high-end Windows/Linux: persistent mapping, DSA, multi-draw-indirect

Key GLx modules in `code/rendererglx/`: `glx_caps.cpp` (tier selection), `glx_material.cpp` (GLSL key/compile), `glx_draw.cpp` (submission), `glx_static_world.cpp` (VBO cache), `glx_stream.cpp` (dynamic ring buffer), `glx_postprocess.cpp` (post-chain), `glx_module.cpp` (entry point, profile table).

### Audio system

Modern audio lives in `code/client/audio/`. OpenAL Soft is the default backend; the original software mixer (`legacy/`) is the deterministic fallback via `s_backend legacy`. Advanced map tuning uses `.azb` audio-zone sidecars — missing sidecars must never break a map.

### VM and game code

`code/game/` (server-side game), `code/cgame/` (client game), `code/ui/` (menus) are QVM bytecode modules. They communicate with the engine through a stable ABI. Do not change VM ABI or protocol behavior without explicit intent.

## Key Conventions

**Version:** `version/fnq3_version.h` is the single source of truth. It feeds runtime strings, Windows resources, Meson, Make, and doc generation. Always update it first for release work.

**Docs generation:** `README.md` and `.install/README.html` are generated — edit the templates in `docs/templates/`, then run `python scripts/generate_docs.py`.

**Changelog:** Pending release notes live in `docs/fnquake3/CHANGELOG.md` under `Unreleased`. Use `scripts/changelog.py` to manage sections.

**Third-party dependencies:** Managed through Meson `subprojects/*.wrap` files (SDL3, OpenAL Soft, libcurl, libjpeg-turbo, Ogg/Vorbis). Do not add new in-tree vendor source trees under `code/lib*/`.

**Scratch space:** Use `.tmp/` for temporary investigation files and intermediate staging. `.install/` is the tracked distribution area for release artifacts.

## Maintainer Docs

Technical docs that require reading before making significant changes to a subsystem:

- `docs/fnquake3/TECHNICAL.md` — repo structure, versioning, release flow
- `docs/fnquake3/GLX_RENDERER.md` — GLx architecture and tier definitions
- `docs/fnquake3/GLX_FEATURE_MATRIX.md` — coverage ledger for each legacy feature
- `docs/fnquake3/GLX_LEGACY_COUPLING.md` — which `code/renderer/*.c` files GLx still compiles and why
- `docs/RTX.md` — RTX requirements, selection, and diagnostics
- `docs/fnquake3/AUDIO_ENGINE.md` — modern audio architecture and compatibility boundaries
- `docs/fnquake3/DLIGHT_SHADOWMAP_ROADMAP.md` — shadow system roadmap
- `AGENTS.md` — project constraints and guardrails for automated agents

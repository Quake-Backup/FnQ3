# Changelog

This is the pending release-note queue for the next FnQuake3 release.

Keep short user-facing bullets under `Unreleased` as changes land. During release publishing, the workflow asks GitHub Copilot to dedupe and categorize the notes for the GitHub release details, then clears this section for the next cycle.

## [Unreleased]

### Highlights
- _None yet._

### Compatibility
- _None yet._

### Rendering and Display
- Enhanced liquids now produce a clearly visible effect: the refraction warp uses a per-pixel multi-octave wave model scaled to the view height (roughly six times stronger than before at 1080 lines, fading with distance), the Fresnel pass gained a bounded screen-space reflection of the captured scene with a clean sheen fallback, and the default OpenGL renderer evaluates the effect per pixel through ARB programs instead of per vertex. Fresnel-only configurations now capture the scene snapshot they need.
- Fixed the Vulkan liquid snapshot capture leaving stale scissor and descriptor-set state behind, which made every enhanced liquid surface disappear entirely on the Vulkan renderer whenever the effect was enabled.
- New in-game menu soft focus (`cl_menuBlur`, on by default): while an in-game menu is open the scene and HUD behind it are replaced with a softened copy of themselves, fading in and out over 140 ms, so the menu reads as the foreground. Gameplay, the connect and loading screens, cgame overlays such as the scoreboard, and the console are all left sharp. It works on all three renderers from one shared sampling plan, so they look the same. Replaces `cl_menuDepthOfField` and `cl_menuDepthOfFieldTime`, which only ever did anything on the OpenGL renderer and failed silently when they could not run; the new effect explains itself under `developer 1` instead.
- Maps that ship external lightmap atlases (`maps/<mapname>/lm_*`) are now lit the same way as maps with their lightmaps inside the BSP. They previously ignored `r_mapOverBrightBits`, `r_mapOverBrightCap`, and `r_mapGreyScale`, took `r_intensity` and gamma a second time on top of the diffuse texture's, and were blurred and bled across tile edges by `r_picmip` and mipmapping.
- Global fog now converts its authored colour into the scene buffer's domain before compositing, accounting for the overbright factor and, in scene-linear mode, the tone-map exposure. An authored mid-grey previously reached the display at roughly twice its brightness, which made the layer read as a flat wash instead of distance fog.
- Enhanced liquid quality pass: the snapshot now defaults to full resolution, the refraction rejects foreground samples against the opaque scene depth so waterlines stay crisp instead of smearing in stepped bands, and the wave distortion fades at grazing angles to stop horizon shimmer. The cvar set was renamed to a self-describing surface — `r_liquid`, `r_liquidResolution`, `r_liquidRefraction`, `r_liquidWarpScale`, `r_liquidReflection`, and `r_liquidRipples` — replacing the old `r_liquidReflections`/`r_liquidReflectionScale`/`r_liquidWarp`/`r_liquidFresnel`/`r_liquidRippleStrength` names, which are no longer read.

### Audio
- _None yet._

### Builds and Packaging
- Meson now links libcurl into Windows clients by default (`-Dcurl-dlopen=auto`), fixing "Error initializing cURL library" download failures in local builds that shipped no `libcurl-3.dll`.
- Fixed the Windows release builds failing to start with "The code execution cannot proceed because libzstd.dll was not found". The bundled curl left its optional features on `auto`, so it linked whatever the build runner happened to have installed, and the release ships no runtime libraries. Every optional curl transfer encoding and protocol is now pinned off, both Windows lanes build with `--wrap-mode=forcefallback` and a statically linked C/C++ runtime, and each artifact is audited before upload so an unshippable dependency fails the build instead of the player's launch.
- Fixed the release workflow being unable to publish anything since June. `make install` staged only the binaries and the data pack, so every Linux and macOS lane failed the release-layout gate that the Meson-built Windows lanes passed; a staged install now carries the same LICENSE, third-party notices, README and docs set that a Meson install does, and is checked against it.
- Removed a `zlib1.dll` dependency from the MinGW Windows client — the same failure mode as the `libzstd.dll` one above, from the one bundled curl compression feature still left on `auto`. Nothing in the engine asks for a compressed transfer encoding, so it is now pinned off. The dependency audit also no longer rejects `msvcrt.dll`, which is part of Windows and is the C runtime the MinGW lanes target.

### Fixes
- Windowed mode no longer confines the mouse cursor to the window while a menu or the console is open, so the pointer can move to the desktop or another monitor and back seamlessly. The cursor stays locked during actual gameplay. In menus and the console the OS cursor is hidden and the in-game cursor snaps 1:1 to the real pointer position within the window.
- Fixed the expanded vanilla HUD so long pickup and mini-score strings stay together, and the attacker head/name remains aligned to the right edge.
- Global fog sidecars are now parsed against the byte count they were read with rather than a NUL terminator, and an oversized file is rejected on its declared size instead of being loaded first. A `density 0.1` sidecar — the documented maximum — is no longer rejected on 32-bit x86 builds, where x87 excess precision put the two sides of the comparison on different values.

### Documentation and Tooling
- Added [`docs/fnquake3/MENU_SOFT_FOCUS.md`](./MENU_SOFT_FOCUS.md) covering the menu soft-focus sampling plan, the layers deliberately left sharp, and the per-backend preconditions.
- Added `scripts/check_windows_dll_deps.py`, which reads the import tables of a staged Windows release and fails if any binary needs a library the package does not ship.

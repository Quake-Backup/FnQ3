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
- Enhanced liquid quality pass: the snapshot now defaults to full resolution, the refraction rejects foreground samples against the opaque scene depth so waterlines stay crisp instead of smearing in stepped bands, and the wave distortion fades at grazing angles to stop horizon shimmer. The cvar set was renamed to a self-describing surface — `r_liquid`, `r_liquidResolution`, `r_liquidRefraction`, `r_liquidWarpScale`, `r_liquidReflection`, and `r_liquidRipples` — replacing the old `r_liquidReflections`/`r_liquidReflectionScale`/`r_liquidWarp`/`r_liquidFresnel`/`r_liquidRippleStrength` names, which are no longer read.

### Audio
- _None yet._

### Builds and Packaging
- Meson now links libcurl into Windows clients by default (`-Dcurl-dlopen=auto`), fixing "Error initializing cURL library" download failures in local builds that shipped no `libcurl-3.dll`.

### Fixes
- Windowed mode no longer confines the mouse cursor to the window while a menu or the console is open, so the pointer can move to the desktop or another monitor and back seamlessly. The cursor stays locked during actual gameplay. In menus and the console the OS cursor is hidden and the in-game cursor snaps 1:1 to the real pointer position within the window.
- Fixed a dedicated-server crash (`VM_Call with NULL vm`) triggered by typing any unrecognized console command while `sv_playdemo` demo cinema playback was active. Also added a new read-only `sv_playingDemo` cvar (visible locally and to remote `getinfo`/`getstatus` queries) so it's now possible to tell whether a server is currently replaying a demo.
- `sv_playdemo` now checks that the demo's map is actually present on the server before starting cinema playback, instead of starting anyway and leaving every connecting client to discover the missing map on its own and disconnect.

### Documentation and Tooling
- _None yet._

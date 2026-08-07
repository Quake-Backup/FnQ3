# Fog Rendering

## Compatibility Contract

Map fog remains the Quake III brush-volume effect authored through shader
`fogParms`. The renderer may improve how that effect is evaluated, but it must
not change BSP fog assignment, fog-volume clipping, `depthForOpaque`, surface
sorts, blend/depth state, demo data, protocol data, or VM behavior.

The canonical density function is the original curve:

1. subtract the historical `1 / 512` distance-coordinate bias;
2. reject fragments outside the fog depth interval;
3. shorten the distance when the eye-to-fragment segment crosses a fog plane;
4. scale the authored distance coordinate by eight and clamp it to `[0, 1]`;
5. take the square root.

`code/renderercommon/tr_fog_math.h` owns the CPU reference implementation.
The GLx, Vulkan, and RTX programmable helpers intentionally use the same
constants.

## Runtime Mode

`r_fogMode` is archived, range-checked, and applies immediately:

| Value | Behavior |
| --- | --- |
| `0` | Exact legacy path: 256 by 32 RGBA8 lookup, table-quantized CPU translucent fog, GLx client-array overlay, and legacy GLx fogged dynamic-light execution. |
| `1` | Analytic path (default): continuous CPU and shader density, GLx position-only streamed overlay, and analytic GLx/Vulkan dynamic-light attenuation. |

Changing the value does not reload the map or require `vid_restart`. The fog
texture is always generated from the legacy table rather than the active mode,
so switching back to `0` restores the original lookup instead of a quantized
copy of the analytic curve.

## Optional Global Map Fog

Global fog is a separate, optional per-map visual layer. It does not replace
retail BSP fog and it does not alter fog assignment, shader data, collision,
visibility, demo playback, protocol, VM behavior, or game state. The archived,
latched cvar defaults to `r_globalFog 1`, but missing sidecars have no effect;
the active game must provide `maps/<map>.fog` for a layer to appear. It needs
the modern framebuffer/depth path, so changing `r_fbo` or `r_globalFog`
requires `vid_restart`. `r_globalFogStrength` is archived, ranges from `0.0`
to `1.0`, and multiplies the sidecar opacity live.

At world load, GLx, Vulkan, and RTX resolve
`maps/<world-basename>.fog` through the normal virtual filesystem. Thus
`q3dm17.bsp` uses `maps/q3dm17.fog`, and a mod may provide an override in its
pk3 without modifying the BSP. Missing files have no effect. A sidecar larger
than 16 KiB or one with invalid input is rejected and reported as a warning;
the level proceeds without the layer. The root FnQuake3 package permits only
`maps/*.fog` (and existing `.azb` audio sidecars), keeping the package-file
allowlist narrow.

The format is ASCII, whitespace-delimited, and accepts `//` comments. Each
directive may appear once:

| Directive | Required | Meaning and valid range |
| --- | --- | --- |
| `color r g b` | Yes | Normalized fog RGB; each component is in `[0, 1]`. |
| `density value` | Yes | Positive exponential coefficient, at most `0.1`. |
| `mode exp\|exp2\|linear` | No | Falloff curve. The default is `exp2`. |
| `start units` | No | Non-negative distance before the falloff begins; default `0`. |
| `end units` | Linear only | Positive terminal distance, strictly greater than `start`. |
| `opacity value` | No | Final layer multiplier in `[0, 1]`; default `1`. |
| `sky 0\|1` | No | Whether clear-depth sky pixels receive fog; default `1`. |

For a scene distance `d = max(viewDistance - start, 0)`, the layer amount is
`1 - exp(-density * d)` for `exp`, `1 - exp(-(density * d)^2)` for `exp2`, or
`clamp(d / (end - start), 0, 1)` for `linear`. The amount is multiplied by
`opacity * r_globalFogStrength` and then mixes the completed scene color toward
`color`.

`color` is authored as a display-referred value, but the compositor writes into
the scene colour buffer, which the final output transform still scales by the
overbright factor and, in scene-linear mode, by the tone-map exposure.
`R_GlobalFogSceneColor` converts the authored colour into that pre-output
domain first (linearizing the sRGB value as well when the scene buffer is
linear-light). Without the conversion an authored mid-grey reaches the display
at roughly twice its brightness and the layer reads as a uniform wash rather
than distance fog.

Parsing is bounded by the byte count `FS_ReadFile` returned rather than by a
NUL terminator, so an embedded NUL or a truncated read cannot widen it past the
file, and a sidecar over 16 KiB is rejected on its declared size before it is
allocated. The `0.1` density ceiling is compared through
`GLOBAL_FOG_DENSITY_MAX`, a casted constant: on 32-bit x86 the x87 unit
evaluates float expressions at excess precision, and a bare `0.1f` literal
there keeps a value just below the float the parser stores for an authored
`0.1`, which rejected the documented maximum.

The checked-in Quake III Arena and Team Arena presets use
low-saturation colors and deliberately readable densities. The supplied
profiles use `exp`, with opacity caps keeping the layer atmospheric rather
than opaque. `q3tourney5` (Fatal Instinct) has no
sidecar because its native map content is already fully fogged.

OpenGL/GLx composites the layer into the framebuffer after opaque and
translucent scene rendering, including the existing BSP fog, and before final
bloom/gamma. Vulkan keeps a resolved copy of the completed world depth and
blends the same formula into the main scene render pass before optional motion
blur, bloom, and later HUD/console draws. RTX uses the same depth-aware
world-layer contract after hybrid RT/raster scene composition and before
world bloom and later HUD/console draws. HUD and console draws are excluded in
all three cases. This is intentionally a depth-aware atmospheric grade, not a
BSP fog replacement or a protocol-visible feature.

## Analytic Programmable Path

The original renderer rasterized the density function into a 256 by 32 RGBA8
texture. Every fogged fragment then performed a dependent lookup. The alpha
channel limited density to 256 stored values, with additional approximation
from the distance/depth grid and bilinear filtering.

With `r_fogMode 1`, GLx, Vulkan, and RTX evaluate the same curve in floating
point. This has two practical benefits:

- continuous fog density removes lookup-grid banding, especially on shallow
  gradients and large `depthForOpaque` values;
- fog-only, collapsed-material, and dynamic-light fragments no longer perform
  a fog texture fetch. Vulkan and RTX retain the legacy resource/layout path
  needed for mode `0`, but the analytic branch does not sample the lookup.

The GLx streamed fog overlay goes further. Its vertex shader derives fog
coordinates from object position and uniform fog vectors, and its fragment
shader supplies the fog color. The stream therefore uploads position and
indices only. Relative to the old position/color/fog-UV payload, that removes
12 bytes per vertex (4 color bytes and 8 UV bytes), a 43 percent reduction in
per-vertex attribute upload, and skips the two CPU loops that prepared those
attributes. If `r_fogMode 0` is selected, GLSL material execution is
unavailable, or fog streaming fails, GLx returns to the existing
client-array fog texture path.

CPU fog adjustment for translucent stages follows the selected mode. The
compatibility fog image and 256-entry density table remain available for
`r_fogMode 0`, GL12, fixed-function, and other legacy fallback paths.

## Why This Is Not Froxel Volumetric Fog

A screen-space froxel volume can add light shafts and heterogeneous density,
but it is not a drop-in replacement for Quake III fog brushes. A production
implementation would need deterministic handling for overlapping fog brushes,
portals and mirrors, transparent surfaces, view weapons, sky, MSAA/depth
resolve, HDR composition, and renderer switching. It would also require a
separate authored density/light model because retail BSP fog contains only a
color and opaque distance.

That remains a possible opt-in effect, but it should be built as a later
lighting layer after depth/portal parity is proven. The analytic change is the
high-value baseline: it improves every existing fog volume without inventing
map data or weakening the fixed-function fallback.

## Verification

The renderer-independent logic test checks zero-density clipping, partial
depth clipping, authored-curve midpoints, opaque saturation, and the preserved
legacy lookup quantization. Vulkan shader sources are compiled for fog-only,
single/triple-texture collapsed fog, and dynamic-light fog permutations before
the checked-in SPIR-V is refreshed.

Recommended local checks:

```powershell
meson compile -C .tmp/build
meson test -C .tmp/build fnq3_glx_logic fnq3_glx_header_boundary fnq3_global_fog_source --print-errorlogs
python tests/global_fog_source_tests.py
python tests/rtx_fog_dlight_source_tests.py
python tests/rtx_raster_overlay_parity_source_tests.py
python tests/glx/glx_runtime_sweep_tests.py
python tests/vulkan/vk_runtime_sweep_tests.py
```

Runtime screenshot review should include `q3dm15` plus a fog-plane crossing
view, a translucent particle/model inside fog, and a fogged dynamic light.
Capture each camera with `r_fogMode 0` and `r_fogMode 1` in GLx, Vulkan, and
RTX. Mode `0` is the lookup reference; mode `1` is expected to differ at
quantization boundaries while preserving fog-plane clipping and opaque
distance. RTX review must also confirm that fogged surfaces remain in the
raster overlay, the depth-aware global layer affects the completed world, and
later HUD/console draws remain unfogged.

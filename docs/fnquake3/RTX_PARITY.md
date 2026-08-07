# RTX Renderer Parity Contract

## Outcome

The RTX renderer now implements the Vulkan renderer's relevant, default-visible
functional surface through an explicit hybrid composition model without
turning RTX into a raster renderer. Eligible primary-view opaque world geometry
is natively ray traced: primary rays, closest-hit material/direct-light
evaluation, self-emissive material appearance, bounded albedo-tinted analytic
environment diffuse, ray-visibility-gated analytic-environment specular, and
ray-tested direct-light shadow visibility are authoritative. This does not
imply scene-radiance reflection rays, full secondary diffuse bounces, or
emissive light transport from arbitrary materials. Authored
`q3map_surfaceLight` metadata is bridged through bounded analytic RT emitters
rather than raster proxy lights. Content whose Quake III semantics are not yet
RT-owned is composited afterward by the mature raster path.

When fallback is permitted, a failed, skipped, or unsupported RT dispatch
retains a complete raster frame rather than missing geometry. Required RT is
different: `rtx_rt_require 1` fails closed when capability activation fails or
an eligible primary-view RT pass cannot complete, so a raster-only frame is
never reported as successful required-RT output.

This is a functional-parity claim, not a pixel-identity claim and not a claim
that every optional Vulkan effect or diagnostic cvar exists in RTX. It means
retail and mod content remains visible, correctly ordered, and usable with the
normal renderer API while RTX supplies the lighting and visibility changes
that are relevant to ray tracing.

Runtime promotion across the full maintained hardware and driver matrix
remains release-validation work. Source tests, shader checks, modular/static
builds, and focused runtime smoke tests establish the implementation baseline;
they do not replace that matrix.

## What Relevant Parity Means

RTX must preserve:

- retail Quake III Arena and Team Arena maps, shaders, lightmaps, demos, UI,
  renderer exports, and asset-loading behavior;
- BSP/PVS visibility, entities, models, sprites, beams, particles, marks,
  flares, portals, mirrors, sky, fog, liquids, first-person content, and HUD
  ordering;
- point and linear dynamic-light meaning, plus renderer-only static map lights;
- authored `q3map_surfaceLight` reach, color hints, subdivision, PVS selection,
  and nearby illumination without importing raster shadow-map machinery;
- safe fallback on unsupported or partially capable Vulkan devices when
  `rtx_rt_require 0`, and deterministic fail-closed behavior when it is `1`;
- stable resize, map-change, `vid_restart`, screenshot, levelshot, modular
  renderer, and static-renderer behavior;
- scene-linear HDR, bloom, final tone mapping, and SDR capture semantics used
  by the default Vulkan path.

Parity does not require identical pixels. Ray-traced shadows, primary
visibility, temporal reconstruction, and lighting will differ from raster
output. A difference is acceptable when it is an intentional rendering-model
change, not missing content, broken draw order, double blending, stale history,
or a lost engine feature.

## Final-Frame Ownership

The primary-view frame is deliberately split:

1. Rasterize the eligible opaque, unfogged world base to establish compatible
   depth and a complete fallback. The color result is not authoritative in
   normal native-RT mode.
2. Trace the full-size, center-eye, non-portal main view. Native primary rays
   and closest-hit material evaluation own the eligible world color, including
   direct lighting, self-emissive appearance, bounded analytic environment
   diffuse, ray-visible analytic-environment specular, and ray-tested shadow
   visibility. If tracing or copying is unavailable, keep the complete raster
   base only when fallback is permitted; required mode fails closed.
3. Draw the exact complementary raster overlay: entities, sky, portals,
   decals, alpha-tested or translucent stages, fogged world surfaces, liquids,
   sprites, beams, particles, marks, flares, and other special effects.
4. Apply depth-aware global fog and world post-processing, then draw later
   `RDF_NOWORLDMODEL` HUD scenes when `r_hudExcludePostProcess 1`.
5. Apply the shared final output transform and present or capture the frame.

The base and overlay predicates are complements. Every draw surface therefore
has final-frame color ownership even when RT is unavailable. Opaque
raster-owned surfaces may still participate as shadow-ray occluders to avoid
light leaks, while primary rays ignore them so authored color remains
raster-owned. Translucent and effect surfaces do not become solid shadow
occluders merely because they are present in acceleration geometry.

`rtx_rt_raster_reference 1` is an optional compatibility mode, not the default
RTX identity. It promotes authored raster scene color and lightmaps to a
reference and layers bounded RT visibility and analytic-environment specular
cues over it only where the glossy RT visibility ray can escape. This supports
content that depends strongly on the original raster balance. With the default
value `0`, native RT shading remains authoritative.

`rtx_rt_legacy_color_compat` retains its narrower compatibility purpose. Its
default value `1` applies legacy `r_intensity` brightness shaping to native RT
output before the shared final pass. It does not control raster-reference
composition or primary-world ownership.

Native RT dispatch is restricted to the compatible primary view. Portals,
mirrors, stereo eyes, cube-map faces, partial viewports, and duplicate or
secondary views keep complete raster output until they have independent
extent, history, and composition ownership.

## Implemented Parity Matrix

| Area | RTX behavior |
| --- | --- |
| Capability and fallback | Vulkan extension names, feature structures, descriptor/limit requirements, formats, and RT pipeline support are checked before activation. `rtx_rt_require 0` permits a complete raster fallback. `1` refuses unsupported activation and fails closed if an eligible primary-view RT pass fails at runtime. |
| Default operating mode | `rtx_rt_mode 2` requests the RT pipeline and `rtx_rt_raster_reference 0` keeps native RT shading authoritative. `rtx_rt_legacy_color_compat 1` only preserves `r_intensity` brightness shaping. Dynamic resolution, spatial filtering, and dynamic BLAS remain default-off stability choices. |
| Opaque world | Eligible static opaque, unfogged world surfaces populate the native primary-ray subset of the world BLAS. Primary rays and closest-hit shading own direct lighting, ray-tested shadow visibility, self-emissive appearance, bounded albedo-tinted analytic environment diffuse, and ray-visible analytic-environment specular. Raster supplies compatible depth and fallback color, not the normal authoritative result. Opaque surfaces with shader semantics that remain raster-owned may still occlude shadow rays without owning primary color. |
| Native shader subset | Native primary-color ownership is conservative: one static opaque base texture, optionally modulated by a lightmap, without animation, texture transforms, deformation, blending, alpha testing, or unusual depth behavior. Unsupported authored semantics remain raster-owned instead of being approximated as ordinary opaque RT materials. Closest-hit albedo uses explicit ray-footprint mip selection from geometry, texture extent, hit distance, view parameters, and incidence angle rather than forced LOD zero. |
| Entities and effects | Models, inline movers, players, weapons, sprites, beams, particles, marks, flares, decals, and other non-world surfaces are always visible through the raster overlay. Inline BSP movers are excluded from the static world BLAS so their original map position cannot become ghost geometry. |
| Alpha-tested geometry | RT any-hit evaluation honors the shader alpha-test comparator, including the distinction between `LT_80` and `GE_80`/`GT_0`, so masked geometry does not become an opaque rectangle. |
| Portals and mirrors | Portal surfaces and all secondary views retain Vulkan-derived raster semantics. A full-frame RT image is never reused for an incompatible view. |
| Dynamic lights | Point and linear lights preserve their engine-side forms. Native RT mode shades them through closest-hit light evaluation and ray visibility. In optional raster-reference mode, raster-reference lights may be uploaded as shadow-only RT lights and the RT pass removes only a bounded estimate of their occluded additive contribution. |
| BSP compile-time lights | `rtx_rt_world_light_scale` promotes BSP light entities into native RT direct lights. Native mode uses those live lights rather than treating baked lightmap energy as native lighting; raster-reference mode retains authored lightmaps. |
| BSP surface lights | Used non-sky faces, grids, and triangle soups carrying `q3map_surfaceLight` metadata produce bounded, subdividable analytic point/linear emitters. They are PVS/view/hemisphere ranked into a fixed RT-only budget and use closest-hit shadow rays. Raw compiler intensities affect bounded reach and priority, never RGB radiance; raster-reference mode skips the emitters to avoid double lighting. |
| World dlights | Versioned `maps/<map>.dlight` point/spot definitions are loaded, PVS/area filtered, budgeted, reloadable, and promoted into the existing light path. Their `castsShadows` policy is retained for RT visibility without adding a raster shadow atlas. |
| Sky and authored special stages | Sky and other special/multi-stage surfaces stay in the overlay, preserving authored animation, texture transforms, blend ordering, and portal behavior. Used BSP sky shaders select per-shader `q3map_sun`, `q3map_sunExt`, or `q3map_sunExt2` metadata; RTX preserves authored low-elevation directions and converts legacy q3map intensity units only at the native RT lighting boundary. |
| BSP fog | `r_fogMode 1` uses the shared analytic Quake III fog curve; mode `0` retains the legacy lookup behavior. Fogged world surfaces remain raster-owned and correctly ordered. |
| Global map fog | Optional `maps/<map>.fog` sidecars are loaded by RTX and composited as a depth-aware world layer before later HUD/console draws. |
| Enhanced liquids | RTX consumes the shared visual ripple feed, captures a private pre-transparency color/depth snapshot, preserves every authored liquid stage, and adds the same screen-space refraction/reflection treatment as Vulkan. This is separate from native scene-radiance RT rays. |
| Soft depth fade | `r_depthFade 1` classifies eligible translucent effects and samples the captured scene depth to soften hard world intersections. |
| Scene-linear HDR | `r_hdr 1` requests RGBA16F scene and bloom targets, uses sRGB decode for authored color textures, keeps data/lightmap/fog resources linear, and carries native RT output, history, and hybrid composition in the scene-linear domain. The shared final pass applies exposure, tone mapping, linear-to-sRGB encoding, and user gamma. Capability failure produces an explicit effective-SDR fallback; `r_hdrPrecision` controls SDR storage only. |
| Bloom and HUD | Bloom extraction uses shared exposure and soft-knee behavior. With `r_hudExcludePostProcess 1`, world bloom is completed before later 3D HUD scenes so HUD elements remain sharp. |
| Picmip policy | `r_picmipFilter` matches Vulkan path categories: world textures may be reduced while models, sprites, UI, icons, menus, and fonts remain protected by the default filter. |
| Screenshots and levelshots | PNG is the default screenshot format and `screenshotPNG` is available. Ordinary screenshots, AVI frames, and levelshots use a dedicated SDR target that runs the same final exposure/tone/gamma transform as presentation even when supersampling is disabled. Levelshots support full-viewport output, centered aspect crop, explicit sizing, downscale, and the client hide-HUD/hide-weapon capture controls. |
| Renderer API and platform | Relevant renderer exports, FOV correction, `RDF_NOFIRSTPERSON`, IQM behavior, the menu depth-of-field no-op, and shared Windows display-output querying match the Vulkan-family contract. |
| Build and generated shaders | Modular and static RTX and Vulkan regression configurations build from the same dependency model. Generated RT and raster shader bundles have a freshness check. |

## Intentional RTX Exclusions

These are not missing relevant functionality:

- Raster dlight/static shadow maps, cascaded shadow maps, PCF kernels, raster
  depth/slope biases, and their debug modes. RTX uses ray visibility instead
  of reproducing shadow-map machinery.
- Raster MSAA while the RT pipeline is active. The hybrid target is
  single-sample and RT reconstruction owns anti-aliasing. Raster fallback may
  still use the normal raster controls.
- Scene-radiance reflection/refraction rays, multi-bounce diffuse global
  illumination, and general emissive light transport. The current native
  material model uses a bounded albedo-tinted analytic environment diffuse
  baseline, ray-visible analytic sky/sun specular, direct-light shadow rays,
  self-emissive appearance, and a bounded analytic bridge for authored
  `q3map_surfaceLight` metadata. That bridge does not turn arbitrary glowing
  pixels into light sources. `rtx_rt_indirect_bounce 1` traces one experimental
  hemisphere visibility ray to occlusion-refine the diffuse baseline; it does
  not sample secondary radiance.
- Native RT rendering for portals, mirrors, stereo eyes, cube-map faces,
  partial viewports, and other secondary views. Their complete raster fallback
  is the parity behavior until per-view RT history and composition are
  designed.
- Raster-pipeline cache counters and diagnostics with no useful RTX analogue.
  RTX exposes capability, acceleration-structure, fallback, and RT timing
  diagnostics instead.

## Known Limits of the Hybrid Contract

- `rtx_rt_dynamic_blas 0` is the stable default. Dynamic entities remain fully
  visible but do not enter RT visibility or cast RT shadows.
- `rtx_rt_dynamic_blas 1` is experimental. It changes ray participation, not
  ownership of visible entity pixels, and must survive the promotion stress
  matrix before default enablement is considered.
- Raster-overlay pixels are composited after tracing and are not
  retroactively ray-shadowed. Ray-visible lights therefore affect eligible RT
  world geometry; overlay entities and effects retain their raster lighting.
- Optional `rtx_rt_raster_reference 1` uses a deliberately bounded
  light-shadow correction. It subtracts an estimated occluded additive light
  contribution from the raster reference and protects emissive surfaces; it is
  not a second physically based re-evaluation of every Quake III shader stage.
- `rtx_rt_legacy_color_compat 1` only applies legacy `r_intensity` brightness
  shaping to native RT output. It does not select the compatibility
  composition path.
- Enhanced-liquid depth rejection is available on the single-sample active-RT
  path. A fallback configuration that retains raster MSAA may use the
  color-only liquid fallback rather than sampling a multisampled depth target.
- Secondary-view raster fallback is intentional and complete. Portal and
  mirror content is not recursively RT-rendered inside the primary view.

## Optional Vulkan Features Outside This Sign-Off

The following non-default or presentation-oriented Vulkan features are
possible future RTX work. Their absence does not remove ordinary map,
gameplay, UI, or capture content and therefore does not block relevant parity:

- native HDR10 swapchain output and HDR display metadata;
- color-grading/LUT passes;
- CRT distortion;
- camera motion blur;
- cel shading and outlines;
- extended screenshot naming, watermark, and view-position sidecars;
- native RTX cube-map capture and other specialized multi-view capture modes.

This list is why the project claims relevant/default-visible parity rather than
strict cvar-for-cvar parity.

## Executed Plan of Action

### 1. Audit and Define Ownership

- Compared Vulkan renderer entry points, cvars, scene categories, post stack,
  build targets, and capture behavior against RTX.
- Defined the relevant parity contract and classified raster shadow-map
  implementation details as irrelevant to RTX.
- Split draw surfaces into exact RT-base and raster-overlay complements.
- Kept native primary-world rays and closest-hit shading authoritative while
  retaining raster scene color only through the explicit
  `rtx_rt_raster_reference 1` compatibility mode.

### 2. Harden RT Activation and Frame Lifetime

- Added feature, limit, format, descriptor, and push-constant gates.
- Added strict/fallback behavior and primary-view dispatch guards.
- Made writable frame resources per command-buffer slot.
- Hardened barriers, query reset/destruction, descriptor invalidation,
  resize/recreation waits, and depth/stencil dependencies.
- Rebuilt binary upload/frame synchronization across keep-context
  `vid_restart` so a signaled staging semaphore cannot leak into the retained
  Vulkan device's next renderer lifetime.
- Disabled incompatible raster MSAA when active RT requires the single-sample
  hybrid path.

### 3. Restore Complete Content Composition

- Preserved entities, effects, portals, sky, special shader stages, fogged
  world, and translucent content through the complementary overlay.
- Added correct any-hit alpha testing.
- Fixed draw-surface batching and fallback ordering.
- Preserved authored raster lightmap/material color as the optional bounded RT
  compatibility reference without making it the default RTX identity.
- Replaced implicit closest-hit LOD-zero albedo sampling with explicit
  ray-footprint mip selection so distant native materials retain stable
  authored detail.

### 4. Port Relevant Vulkan Features

- Added analytic BSP fog and depth-aware global fog.
- Ported enhanced liquids and the shared ripple interaction feed.
- Added soft-particle depth fade.
- Added static map lights, ray-visible dynamic/static light policy, and
  bounded compatibility shadow removal.
- Added native `q3map_surfaceLight` parsing, bounded BSP proxy construction,
  stable PVS/priority selection, and direct point/linear RT-light upload with
  shadow rays and no shadow-map dependency.
- Added bounded albedo-tinted analytic environment diffuse for native material
  readability, kept its optional hemisphere ray as an occlusion-only
  refinement, and made analytic environment specular require a glossy
  ray-visible escape instead of leaking the sky through indoor geometry.
- Matched picmip filtering, FOV/API behavior, PNG capture, and flexible
  levelshots.

### 5. Align Color and Post Processing

- Made `r_hdr 1` select a capability-gated RGBA16F scene and bloom path, with
  `r_hdrPrecision` retained for SDR storage choices.
- Applied sRGB decode only to authored color textures.
- Kept RT history and the raster bridge in the scene-linear domain.
- Moved exposure/tone mapping to the final pass, added the required
  linear-to-sRGB output transform and user gamma, and aligned bloom extraction.
- Made screenshots, AVI frames, and levelshots capture that final transformed
  SDR image rather than the pre-tone scene target.
- Split world post-processing from later HUD scenes.

### 6. Add Regression Gates

- Added focused source tests for composition, RT light visibility, fog,
  liquids, HDR, depth fade, screenshots/levelshots, static lights, and renderer
  contracts.
- Added modular RTX, static RTX, and static Vulkan regression builds.
- Added generated-shader freshness validation.
- Added the focused `rtx-smoke` harness with isolated raster-fallback and
  required mode-2 profiles, validation-log scanning, and screenshot evidence.
- Added a native material-detail audit that pairs the normally lit q3dm1 RT
  frame with an albedo-debug companion and requires correlated high-pass
  texture structure without comparing RT lighting to raster pixels.
- Kept harness launch commands below Quake III's fixed startup-command limit,
  applied lifecycle-sensitive renderer settings before first initialization,
  rejected non-zero natural exits even when evidence files exist, rechecked
  flushed evidence after clean process exit, and added decoded-image rejection
  for excessive near-white clipping.
- Performed focused mode-2 runtime smoke tests with Vulkan validation enabled,
  including fog comparison, enhanced liquids, and static-light
  load/reload/promotion.

## Validation

The focused source gates are:

```powershell
python tests/rtx_renderer_parity_source_tests.py
python tests/rtx_raster_overlay_parity_source_tests.py
python tests/rtx_light_visibility_source_tests.py
python tests/rtx_surface_light_source_tests.py
python tests/rtx_fog_dlight_source_tests.py
python tests/rtx_hdr_source_tests.py
python tests/rtx_liquid_rendering_source_tests.py
python tests/global_fog_source_tests.py
python tests/liquid_rendering_source_tests.py
python tests/liquid_interaction_source_tests.py
python tests/static_map_lights_source_tests.py
python tests/renderer_contract_source_tests.py
python tests/rtx_runtime_smoke_tests.py
python code/rendererrtx/shaders/build_shaders.py --check
```

Build gates are:

```powershell
meson setup .tmp/build-rtx -Drenderers=rtx
meson compile -C .tmp/build-rtx

meson setup .tmp/build-static-rtx -Drenderer-dlopen=false -Drenderer-default=rtx
meson compile -C .tmp/build-static-rtx

meson setup .tmp/build-static-vk -Drenderer-dlopen=false -Drenderer-default=vk
meson compile -C .tmp/build-static-vk
```

Reuse or reconfigure existing build directories rather than discarding
unrelated `.tmp/` evidence.

Generate deterministic gate plans without launching the engine:

```powershell
python scripts/rtx_runtime_smoke.py --list-gates
python scripts/rtx_runtime_smoke.py --gate rtx-smoke --dry-run `
  --exe .tmp/rtx-gate-plans/fnquake3 `
  --basepath .tmp/rtx-gate-plans/basepath `
  --output-dir .tmp/rtx-gate-plans `
  --summary-markdown .tmp/rtx-gate-plans/rtx-smoke.md
```

Run the hardware gate against a built client and retail assets:

```powershell
python scripts/rtx_runtime_smoke.py --gate rtx-smoke `
  --exe <path-to-fnquake3> `
  --basepath <path-containing-retail-baseq3> `
  --output-dir .tmp/rtx-runtime-smoke `
  --summary-markdown .tmp/rtx-runtime-smoke/rtx-smoke.md
```

The gate runs a mode-0 fallback profile and a strict
`rtx_rt_mode 2`/`rtx_rt_require 1` profile over `q3dm8` and `q3dm1`. It records
isolated configs, logs, screenshots, a JSON manifest, and a Markdown summary;
the RT profile must prove validation-layer activation and the RT post-stack
marker, plus correlated native material detail against its albedo-debug
companion, with no VUID, validation, fatal, or device-loss errors.

The [`vulkan-verification`](../../.github/workflows/vulkan-verification.yml)
workflow builds modular and static VK and RTX configurations, runs the RTX
source/shader/harness tests, generates dry-run Vulkan-family gate artifacts,
and exposes manual VK and `rtx-smoke` execution on self-hosted GPU runners.
Dry-run artifacts are planning evidence; promotion still requires reviewed
non-dry-run hardware evidence.

## Remaining Hardware Promotion Matrix

Before RTX is described as broadly promoted rather than fit-for-purpose, run
and archive the following matrix:

| Axis | Required coverage |
| --- | --- |
| Platform | Maintained Windows and Linux configurations, modular and static RTX. |
| GPU/driver | Maintained desktop and laptop RT-capable driver floors; at least one lower-limit or partial-capability Vulkan implementation; an unsupported device for fallback diagnostics. |
| Activation | Modes `0`, `1`, and `2`; `rtx_rt_require 0` and `1`; dynamic BLAS off for the supported baseline and on for experimental stress. |
| Content | Retail Quake III Arena and Team Arena map/demo sweeps plus selected mod maps with alpha tests, multi-stage shaders, portals, fog, liquids, MDR/MD3/IQM models, and dense effects. |
| Lifecycle | Repeated resize, minimize/restore, fullscreen changes, map changes, demo restart/seek, renderer switches, `vid_restart`, and shutdown/relaunch. |
| Presentation | Common resolutions and aspect ratios, scene-linear HDR on/off, bloom/HUD split, all ordinary screenshot formats, and levelshot crop/resize modes. |
| Stress | Long demo loops, dense dynamic lights, static-light and surface-light budget changes/reload, dynamic BLAS opt-in, large texture sets, and validation layers enabled. |

Each blocking run should retain the capability report, `vkinfo`, active mode,
GPU/driver/OS, resolution, cvar overrides, validation log, screenshots, and
timing summary. Promotion requires no device loss or Vulkan validation errors,
no missing or reordered relevant content, deterministic fallback, and
documented performance/memory budgets for the supported quality tiers.

## Maintenance Rules

- Keep RT-base and raster-overlay predicates exact complements.
- Keep native RT shading authoritative for eligible primary-world pixels;
  raster color may become authoritative only in the explicit
  `rtx_rt_raster_reference 1` compatibility mode.
- Keep the bounded native environment diffuse and ray-visible analytic
  specular independent of raster scene color and baked lightmap authority.
- Keep `q3map_surfaceLight` proxies in the native analytic-light path. Do not
  promote them through raster dlights or shadow maps, and do not multiply RGB
  by unbounded compiler intensity values.
- Keep `rtx_rt_legacy_color_compat` limited to legacy `r_intensity` brightness
  shaping; do not overload it with frame-ownership policy.
- Keep visible entity ownership independent of dynamic BLAS success.
- Do not transfer primary-color ownership of translucent or special surfaces
  to RT simply to increase coverage. If acceleration geometry is used only for
  visibility, preserve its alpha, cull, and raster-overlay ownership semantics.
- Invalidate per-view depth snapshots and temporal history conservatively.
- Preserve demo, protocol, VM, BSP/PVS, shader parsing, and asset compatibility.
- Regenerate and verify SPIR-V/reflection data whenever shader sources change.
- Add a source/build regression for every repaired contract and a runtime
  corpus case for every visual, synchronization, or lifetime failure.
- Update this document when a limitation is removed or a new intentional
  difference is accepted.
